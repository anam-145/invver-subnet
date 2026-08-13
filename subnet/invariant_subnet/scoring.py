"""The scoring rule.

This is the whole claim of the subnet, so it is written to be read:

  * It is a **pure function** of ``ExecutionResult`` plus a ledger of findings
    already claimed. No clocks, no randomness, no network, no model call.
  * It never decides whether something *is* a vulnerability. That question was
    settled when the target's invariant set was published.
  * Two validators holding the same results and the same ledger produce
    identical numbers, which is what makes consensus tight.

Run the tests:  python -m unittest discover tests -v
"""

from __future__ import annotations

from typing import Iterable, Sequence

from .protocol import (
    SEVERITY_WEIGHT,
    ExecutionResult,
    NoveltyKey,
    ScoredSubmission,
    Target,
)

#: A proof-of-concept shorter than this gets no extra credit for being short —
#: below a few calls the difference is noise, not skill.
MINIMALITY_FLOOR_CALLS = 3

#: Floor on the minimality factor, so a long-but-real exploit still pays.
MINIMALITY_MIN_FACTOR = 0.4


class FindingLedger:
    """Novelty keys already claimed, and by whom.

    Seeded before a target opens with every publicly known exploit for it, so
    replaying a published attack earns nothing.
    """

    def __init__(self, claimed: Iterable[tuple[NoveltyKey, str]] = ()) -> None:
        self._claimed: dict[str, str] = {str(k): who for k, who in claimed}

    def is_claimed(self, key: NoveltyKey) -> bool:
        return str(key) in self._claimed

    def claimant(self, key: NoveltyKey) -> str | None:
        return self._claimed.get(str(key))

    def claim(self, key: NoveltyKey, miner_hotkey: str) -> bool:
        """Record a first discovery. Returns False if someone already had it."""
        if str(key) in self._claimed:
            return False
        self._claimed[str(key)] = miner_hotkey
        return True

    def __len__(self) -> int:
        return len(self._claimed)


def minimality_factor(call_count: int) -> float:
    """Shorter proof-of-concept, slightly higher score. Bounded both ways.

    Cheap to compute and impossible to argue with: it is a call count.
    """
    if call_count <= MINIMALITY_FLOOR_CALLS:
        return 1.0
    factor = MINIMALITY_FLOOR_CALLS / call_count
    return max(MINIMALITY_MIN_FACTOR, factor)


def score_submission(
    result: ExecutionResult,
    target: Target,
    ledger: FindingLedger,
) -> ScoredSubmission:
    """Score one execution result and claim any novel findings in the ledger.

    Mutates ``ledger`` — a validator processes submissions in a defined order
    (block, then submission id) so that first-discovery is unambiguous.
    """
    if result.error is not None:
        return ScoredSubmission(
            submission_id=result.submission_id,
            miner_hotkey=result.miner_hotkey,
            score=0.0,
            reasons=(f"execution failed: {result.error}",),
        )

    if not result.broken_invariant_ids:
        return ScoredSubmission(
            submission_id=result.submission_id,
            miner_hotkey=result.miner_hotkey,
            score=0.0,
            reasons=("no invariant broke",),
        )

    novel: list[NoveltyKey] = []
    duplicate: list[NoveltyKey] = []
    reasons: list[str] = []
    best_weight = 0.0

    # Sorted so the result never depends on dict or set ordering.
    for invariant_id in sorted(set(result.broken_invariant_ids)):
        try:
            invariant = target.invariant(invariant_id)
        except KeyError:
            reasons.append(f"{invariant_id}: not published for this target, ignored")
            continue

        key = NoveltyKey(
            target_id=result.target_id,
            invariant_id=invariant_id,
            state_delta_hash=result.state_delta_hash,
        )

        if ledger.claim(key, result.miner_hotkey):
            novel.append(key)
            weight = SEVERITY_WEIGHT[invariant.severity]
            best_weight = max(best_weight, weight)
            reasons.append(f"{invariant_id}: novel, severity={invariant.severity}")
        else:
            duplicate.append(key)
            reasons.append(
                f"{invariant_id}: already claimed by {ledger.claimant(key)}"
            )

    if not novel:
        return ScoredSubmission(
            submission_id=result.submission_id,
            miner_hotkey=result.miner_hotkey,
            score=0.0,
            duplicate_findings=tuple(duplicate),
            reasons=tuple(reasons),
        )

    factor = minimality_factor(result.call_count)
    reasons.append(f"minimality: {result.call_count} calls → x{factor:.2f}")

    return ScoredSubmission(
        submission_id=result.submission_id,
        miner_hotkey=result.miner_hotkey,
        score=best_weight * factor,
        novel_findings=tuple(novel),
        duplicate_findings=tuple(duplicate),
        reasons=tuple(reasons),
    )


def score_round(
    results: Sequence[ExecutionResult],
    target: Target,
    ledger: FindingLedger,
) -> list[ScoredSubmission]:
    """Score a whole round.

    Processing order is fixed by submission id so that "who was first" does not
    depend on the order a validator happened to receive things in.
    """
    ordered = sorted(results, key=lambda r: r.submission_id)
    return [score_submission(r, target, ledger) for r in ordered]


def normalize_weights(scored: Sequence[ScoredSubmission]) -> dict[str, float]:
    """Collapse per-submission scores into per-miner weights summing to 1.0.

    A miner's weight is the sum of their submission scores. Returns an empty
    mapping when nothing scored, rather than dividing by zero.
    """
    totals: dict[str, float] = {}
    for s in scored:
        if s.score > 0:
            totals[s.miner_hotkey] = totals.get(s.miner_hotkey, 0.0) + s.score

    grand = sum(totals.values())
    if grand <= 0:
        return {}
    return {k: v / grand for k, v in sorted(totals.items())}
