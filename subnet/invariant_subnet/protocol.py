"""Wire types shared by miners and validators.

Everything here is frozen and hashable on purpose: a submission's score has to
be a pure function of these values, so that two validators holding the same
objects compute the same number without talking to each other.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

# Severity is a property of the *invariant class*, fixed when the target is
# published — never assigned per submission. That is what stops severity from
# becoming an argument after the fact.
SEVERITY_WEIGHT: dict[str, float] = {
    "critical": 1.00,
    "high": 0.60,
    "medium": 0.30,
    "low": 0.10,
}


@dataclass(frozen=True)
class Invariant:
    """A property that must hold, expressed as one executable assertion."""

    id: str
    category: str  # reentrancy | money_flow | access_control | ...
    severity: str  # key of SEVERITY_WEIGHT, fixed at publication time
    solidity_assert: str
    statement: str = ""

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_WEIGHT:
            raise ValueError(f"unknown severity {self.severity!r}")
        if "assert(" not in self.solidity_assert:
            raise ValueError(
                f"{self.id}: an invariant must carry an executable assert, "
                f"got {self.solidity_assert!r}"
            )


@dataclass(frozen=True)
class Target:
    """A contract opened for exploitation, with its published invariant set.

    ``impact_reference`` is the state-change magnitude that counts as a full-credit
    exploit for this target — total value at risk, total supply, whatever the unit
    of ``ExecutionResult.impact`` is. Published with the target so that impact
    ranking is fixed before competition rather than fitted to submissions.
    """

    id: str
    name: str
    source_uri: str
    invariants: tuple[Invariant, ...]
    impact_unit: str = "wei"
    impact_reference: float = 0.0

    def invariant(self, invariant_id: str) -> Invariant:
        for inv in self.invariants:
            if inv.id == invariant_id:
                return inv
        raise KeyError(f"{invariant_id!r} is not published for target {self.id!r}")


@dataclass(frozen=True)
class Submission:
    """A miner's proof-of-concept against one target."""

    miner_hotkey: str
    target_id: str
    poc_source: str
    submitted_at_block: int

    @property
    def id(self) -> str:
        digest = hashlib.sha256(
            f"{self.miner_hotkey}|{self.target_id}|{self.poc_source}".encode()
        ).hexdigest()
        return digest[:16]


@dataclass(frozen=True)
class ExecutionResult:
    """What the validator's harness observed. The only input to scoring.

    ``state_delta_hash`` is a hash of the minimized post-execution state diff.
    It is what makes two functionally identical exploits collapse to one
    novelty key even when their source differs.

    ``impact`` is the measured magnitude of the state change, in the target's
    ``impact_unit`` — net asset loss, tokens minted without authorization, value
    frozen. It is read off the post-state, never asserted by the miner. Zero is
    legitimate: an invariant can break without moving value.
    """

    submission_id: str
    target_id: str
    miner_hotkey: str
    broken_invariant_ids: tuple[str, ...]
    call_count: int
    state_delta_hash: str
    impact: float = 0.0
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if self.impact < 0:
            raise ValueError("impact is a magnitude and cannot be negative")

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.broken_invariant_ids)


@dataclass(frozen=True)
class NoveltyKey:
    """Identity of a *finding*, not of a submission.

    Two miners who independently rediscover the same bug produce the same key,
    so only the first one is paid for it.
    """

    target_id: str
    invariant_id: str
    state_delta_hash: str

    def __str__(self) -> str:
        return f"{self.target_id}:{self.invariant_id}:{self.state_delta_hash[:12]}"


@dataclass
class ScoredSubmission:
    """Scoring output. ``reasons`` exists so a miner can see why they got what
    they got without anyone having to explain a judgment call."""

    submission_id: str
    miner_hotkey: str
    score: float
    novel_findings: tuple[NoveltyKey, ...] = field(default_factory=tuple)
    duplicate_findings: tuple[NoveltyKey, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
