"""Network activity monitoring for miners and validators.

STATUS: partial. The aggregation below runs today against local scoring
records. Chain queries (metagraph, weights, stake) are marked TODO and are
not implemented — nothing here silently fabricates on-chain data.

What we want to watch, and why:

  miners      submission rate, novelty hit rate, score concentration.
              A miner whose novelty rate collapses is replaying; a network
              whose novelty rate collapses has an exhausted target.

  validators  agreement. Because scoring is deterministic, two honest
              validators on the same round MUST produce identical weights.
              Any divergence is a bug or a defector — never a difference of
              opinion. This is the property the whole design buys us, so it
              is the first thing to instrument.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .protocol import ScoredSubmission


@dataclass
class MinerStats:
    hotkey: str
    submissions: int = 0
    scoring_submissions: int = 0
    novel_findings: int = 0
    duplicate_findings: int = 0
    total_score: float = 0.0

    @property
    def novelty_rate(self) -> float:
        found = self.novel_findings + self.duplicate_findings
        return self.novel_findings / found if found else 0.0

    @property
    def hit_rate(self) -> float:
        return self.scoring_submissions / self.submissions if self.submissions else 0.0


@dataclass
class RoundReport:
    target_id: str
    miners: dict[str, MinerStats] = field(default_factory=dict)

    @property
    def total_submissions(self) -> int:
        return sum(m.submissions for m in self.miners.values())

    @property
    def novel_findings(self) -> int:
        return sum(m.novel_findings for m in self.miners.values())

    @property
    def network_novelty_rate(self) -> float:
        """Fraction of findings that were first discoveries.

        Trending toward zero means the target's invariant set is exhausted and
        should be rotated out — not that miners got worse.
        """
        found = sum(m.novel_findings + m.duplicate_findings for m in self.miners.values())
        return self.novel_findings / found if found else 0.0

    def top_miners(self, n: int = 10) -> list[MinerStats]:
        return sorted(self.miners.values(), key=lambda m: -m.total_score)[:n]


def summarize_round(target_id: str, scored: Iterable[ScoredSubmission]) -> RoundReport:
    """Aggregate one round of scoring records. Pure, no I/O."""
    report = RoundReport(target_id=target_id)
    for s in scored:
        st = report.miners.setdefault(s.miner_hotkey, MinerStats(hotkey=s.miner_hotkey))
        st.submissions += 1
        st.total_score += s.score
        st.novel_findings += len(s.novel_findings)
        st.duplicate_findings += len(s.duplicate_findings)
        if s.score > 0:
            st.scoring_submissions += 1
    return report


def validator_disagreement(
    weights_by_validator: Mapping[str, Mapping[str, float]],
    tolerance: float = 1e-9,
) -> list[tuple[str, str, float]]:
    """Find validator pairs whose weight vectors differ.

    Deterministic scoring means an honest pair differs by 0. Any non-empty
    result is a signal, not noise: a bug, a stale ledger, or a defector.

    Returns ``(validator_a, validator_b, max_abs_difference)`` for each
    disagreeing pair, sorted by magnitude.
    """
    names = sorted(weights_by_validator)
    out: list[tuple[str, str, float]] = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            wa, wb = weights_by_validator[a], weights_by_validator[b]
            keys = set(wa) | set(wb)
            delta = max((abs(wa.get(k, 0.0) - wb.get(k, 0.0)) for k in keys), default=0.0)
            if delta > tolerance:
                out.append((a, b, delta))
    return sorted(out, key=lambda t: -t[2])


def render_report(report: RoundReport) -> str:
    """Plain-text summary, for a terminal or a log line."""
    lines = [
        f"target        {report.target_id}",
        f"submissions   {report.total_submissions}",
        f"novel         {report.novel_findings}",
        f"novelty rate  {report.network_novelty_rate:.1%}",
        "",
        f"{'miner':<24}{'subs':>6}{'novel':>7}{'dup':>6}{'hit':>8}{'score':>9}",
    ]
    for m in report.top_miners():
        lines.append(
            f"{m.hotkey:<24}{m.submissions:>6}{m.novel_findings:>7}"
            f"{m.duplicate_findings:>6}{m.hit_rate:>8.0%}{m.total_score:>9.3f}"
        )
    return "\n".join(lines)


# ── not implemented ──────────────────────────────────────────────────────────

def fetch_metagraph(netuid: int):  # pragma: no cover
    """TODO: read miner/validator registration, stake, and emission from chain.

    Needs the `bittensor` SDK and a registered netuid. Not implemented — do
    not call this expecting data.
    """
    raise NotImplementedError("chain queries are not implemented yet")


def fetch_set_weights_history(netuid: int, blocks: int):  # pragma: no cover
    """TODO: read each validator's submitted weights over a block range, so
    `validator_disagreement` can run against on-chain values rather than
    locally computed ones."""
    raise NotImplementedError("chain queries are not implemented yet")
