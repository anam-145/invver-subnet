"""Data types for the target-ingestion pipeline.

A contract travels through three shapes:

    RawContract   pulled from a source, not yet screened
        ↓  safety.screen()
    (eligible?)   a RawContract plus an EligibilityResult
        ↓  mutate.mutate()  (optional)
    TargetRecord  ready to be published as a challenge target

Everything is plain stdlib so the pipeline runs with no pip install, the same
posture as the scoring rule in ../subnet.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SourceFile:
    path: str
    content: str


@dataclass
class RawContract:
    """A contract pulled from some source, before eligibility screening.

    `identifier` is an on-chain address for verified-source adapters, or a repo
    path for the audit-repo adapter. `chain_id` is None for repo sources.
    """

    source: str  # "sourcify" | "etherscan" | "local:code4rena" | ...
    identifier: str
    name: str
    chain_id: Optional[int]
    files: tuple[SourceFile, ...]
    metadata: dict = field(default_factory=dict)

    @property
    def combined_source(self) -> str:
        """All Solidity concatenated, in a stable order, for scanning."""
        sol = sorted(
            (f for f in self.files if f.path.endswith(".sol")),
            key=lambda f: f.path,
        )
        return "\n\n".join(f"// ===== {f.path} =====\n{f.content}" for f in sol)

    @property
    def primary_file(self) -> Optional[SourceFile]:
        """The .sol file whose name matches `name`, else the largest .sol."""
        sol = [f for f in self.files if f.path.endswith(".sol")]
        if not sol:
            return None
        for f in sol:
            if f.path.rsplit("/", 1)[-1] in (f"{self.name}.sol", self.name):
                return f
        return max(sol, key=lambda f: len(f.content))

    @property
    def id(self) -> str:
        key = f"{self.source}|{self.chain_id}|{self.identifier}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass
class EligibilityResult:
    """Whether a RawContract may be used as a target, and why.

    `checks` maps each gate to "pass" / "fail" / "unknown". A gate that needs
    data we do not have (an RPC balance query, a clone index) is "unknown", and
    the contract is not eligible until that gate is satisfied — we never let an
    unscreened live contract through by default.
    """

    eligible: bool
    checks: dict[str, str]
    reasons: tuple[str, ...] = ()


@dataclass
class TargetRecord:
    """A challenge target ready for a manifest.

    `provenance` records where it came from and, for a mutant, what was changed
    — so a target is always traceable back to a real, screened contract.
    """

    target_id: str
    name: str
    origin: RawContract
    solidity: str
    kind: str  # "as_is" | "mutant"
    provenance: dict = field(default_factory=dict)
