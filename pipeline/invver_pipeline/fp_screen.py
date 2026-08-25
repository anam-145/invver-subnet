"""False-positive screening — the gate that stops a farmable invariant from
reaching a manifest.

The problem, in one sentence: an automatically extracted invariant can be
*wrong*, and a wrong invariant is free money. Our Trace2Inv reproduction
measured it directly — structural invariants sit near 0% false positives, but
the oracle class fires on 22.3% of legitimate transactions. Publish that oracle
invariant as-is and a miner never has to find a bug: they replay ordinary
traffic, one in five trips the assertion, and they collect. Miners always take
the cheapest valid path, so one high-FP invariant in the set turns the whole
subnet into a machine that pays for normal trades.

The fix reuses Trace2Inv's own false-positive computation, but as a *filter*
rather than a reported statistic:

    candidate invariant
      → replay the target's past benign transactions against it
      → if it fires on any (above a threshold), it is not a safety property,
        it is a false positive → reject it before publication
      → only survivors go into the manifest, marked fp_screened

Actually replaying a transaction against a Solidity assertion needs an EVM
(forge). This module owns the *decision*: the corpus model, the aggregation, the
threshold, the fail-closed rules, and the manifest flag. The EVM step is behind
a `Replayer` seam so the decision logic is fully testable with a fake, and the
real forge-backed replayer is an explicit stub (`ForgeReplayer`) — same posture
as `mutate.compiles()` and the external checks in `safety.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

#: Default tolerance. Zero: an invariant that fires on *any* benign transaction
#: is rejected. This matches the design decision that a published set is a
#: conjunction of low-FP structural checks — see docs/evidence.md.
DEFAULT_MAX_FP_RATE = 0.0

#: A pass is only trustworthy if it was tested against real traffic. Screening
#: an invariant against fewer than this many benign transactions cannot clear
#: it — absence of evidence is not evidence of safety (cf. safety.py, where an
#: unchecked gate never counts as pass).
MIN_CORPUS = 1


@dataclass(frozen=True)
class BenignTx:
    """One transaction believed to be legitimate.

    Sourced from the target's own history *before* any exploit block — exactly
    the traffic that must never trip a real safety invariant. For an
    already-exploited or patched target (the kinds the pipeline admits), this
    history already exists on-chain, which is what makes screening possible
    without inventing traffic.
    """

    id: str
    description: str = ""


@dataclass(frozen=True)
class CandidateInvariant:
    """An invariant proposed for a target, before it has earned publication."""

    id: str
    category: str
    solidity_assert: str


@runtime_checkable
class Replayer(Protocol):
    """Replays a candidate invariant against one benign transaction.

    Returns True if the invariant still HOLDS after the transaction (no false
    positive), False if it FIRED on legitimate traffic (a false positive).
    """

    def holds(self, invariant: CandidateInvariant, tx: BenignTx) -> bool: ...


class ForgeReplayer:
    """The real replayer: fork, replay the benign tx, evaluate the assertion.

    Not implemented here — it needs a Foundry install, which this environment
    does not have. It raises rather than returning a value so a missing EVM can
    never be mistaken for "the invariant held". Wire this to `forge` in the
    environment that runs screening for real.
    """

    def holds(self, invariant: CandidateInvariant, tx: BenignTx) -> bool:
        raise NotImplementedError(
            "ForgeReplayer needs a Foundry install: fork at the manifest block, "
            "replay the benign tx, and check whether the invariant assertion "
            "reverts. Until then, inject a Replayer explicitly."
        )


@dataclass(frozen=True)
class ScreeningResult:
    """The outcome of screening one candidate invariant."""

    invariant_id: str
    benign_count: int
    fires: int
    fired_on: tuple[str, ...]
    max_fp_rate: float
    passed: bool
    reason: str = ""

    @property
    def fp_rate(self) -> float:
        return self.fires / self.benign_count if self.benign_count else 0.0


@dataclass(frozen=True)
class ScreeningReport:
    """The outcome of screening a whole candidate set against one corpus."""

    results: tuple[ScreeningResult, ...]

    @property
    def kept_ids(self) -> tuple[str, ...]:
        return tuple(r.invariant_id for r in self.results if r.passed)

    @property
    def rejected_ids(self) -> tuple[str, ...]:
        return tuple(r.invariant_id for r in self.results if not r.passed)

    def result_for(self, invariant_id: str) -> ScreeningResult:
        for r in self.results:
            if r.invariant_id == invariant_id:
                return r
        raise KeyError(invariant_id)

    @property
    def fp_screened(self) -> bool:
        """The flag a manifest needs before publication.

        True iff screening ran and left at least one clean invariant to publish.
        The kept set is what gets published — rejected candidates are dropped,
        not published-with-a-warning — so a run where every candidate was
        rejected has nothing to publish and is not screened-ready.
        """
        return len(self.kept_ids) > 0


def screen_invariant(
    invariant: CandidateInvariant,
    corpus: tuple[BenignTx, ...],
    replayer: Replayer,
    max_fp_rate: float = DEFAULT_MAX_FP_RATE,
    min_corpus: int = MIN_CORPUS,
) -> ScreeningResult:
    """Replay one invariant against the benign corpus and decide pass/reject.

    Fails closed: a corpus smaller than `min_corpus` cannot clear an invariant,
    regardless of `max_fp_rate`, because there is not enough legitimate traffic
    to trust the absence of a false positive.
    """
    n = len(corpus)
    if n < min_corpus:
        return ScreeningResult(
            invariant_id=invariant.id,
            benign_count=n,
            fires=0,
            fired_on=(),
            max_fp_rate=max_fp_rate,
            passed=False,
            reason=f"corpus too small ({n} < {min_corpus}); cannot clear",
        )

    fired_on = tuple(tx.id for tx in corpus if not replayer.holds(invariant, tx))
    fires = len(fired_on)
    fp_rate = fires / n
    passed = fp_rate <= max_fp_rate
    reason = (
        "held on all benign traffic"
        if passed
        else f"fired on {fires}/{n} benign tx ({fp_rate:.1%} > {max_fp_rate:.1%})"
    )
    return ScreeningResult(
        invariant_id=invariant.id,
        benign_count=n,
        fires=fires,
        fired_on=fired_on,
        max_fp_rate=max_fp_rate,
        passed=passed,
        reason=reason,
    )


def screen(
    candidates: tuple[CandidateInvariant, ...],
    corpus: tuple[BenignTx, ...],
    replayer: Replayer,
    max_fp_rate: float = DEFAULT_MAX_FP_RATE,
    min_corpus: int = MIN_CORPUS,
) -> ScreeningReport:
    """Screen a candidate set; results are in candidate order."""
    return ScreeningReport(
        results=tuple(
            screen_invariant(c, corpus, replayer, max_fp_rate, min_corpus)
            for c in candidates
        )
    )


def kept(report: ScreeningReport, candidates: tuple[CandidateInvariant, ...]) -> tuple[CandidateInvariant, ...]:
    """The candidates that survived screening, ready for a manifest."""
    keep = set(report.kept_ids)
    return tuple(c for c in candidates if c.id in keep)
