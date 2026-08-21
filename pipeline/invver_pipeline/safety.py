"""Eligibility screening — decides whether a pulled contract may become a target.

This gate is the enforcement point for the whole "validators never have a reason
to exploit" decision. A contract is eligible only if using it as a public
target cannot harm anyone: no live funds, or already exploited, or patched, or
not a real deployment (a mutant/synthetic).

Some checks are pure and run here. Some need data we do not have in-process —
an on-chain balance, an exploit/patch feed, a bytecode-clone index. Those return
"unknown", and **unknown never counts as pass**: a contract with an unresolved
live-funds check is not eligible unless the caller explicitly asserts the fact
(e.g. `--assume-no-funds` after checking manually). Safe default over convenient
default, on purpose.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from .model import EligibilityResult, RawContract

# ── pure checks ──────────────────────────────────────────────────────────────


def _has_source(c: RawContract) -> tuple[str, str]:
    return ("pass", "") if c.combined_source.strip() else ("fail", "no source")


def _is_real_target(c: RawContract) -> tuple[str, str]:
    """Reject interfaces, libraries, and support scaffolding — nothing to break."""
    src = c.primary_file.content if c.primary_file else ""
    if not re.search(r"\bcontract\s+\w+", src):
        return ("fail", "no concrete contract (interface/library only)")
    if c.metadata.get("looks_like_support"):
        return ("fail", "looks like a mock/test/harness by filename")
    # Needs at least one state variable and one function to be exploitable.
    has_state = re.search(r"\b(mapping|uint\d*|address|bool)\b[^;{]*;", src)
    has_fn = re.search(r"\bfunction\s+\w+", src)
    if not (has_state and has_fn):
        return ("fail", "no state + function; nothing to violate")
    return ("pass", "")


# ── checks that need external data (stubbed, return "unknown") ───────────────


def _no_live_funds(c: RawContract) -> tuple[str, str]:
    # TODO: query balance + tracked-token holdings at the fork block via RPC.
    # Until then this is unknown, and unknown does not pass.
    if c.chain_id is None:
        return ("pass", "synthetic/repo contract, not a live deployment")
    return ("unknown", "live balance not checked (needs RPC)")


def _exploited_or_patched(c: RawContract) -> tuple[str, str]:
    # TODO: cross-reference an exploit feed (DeFiHackLabs, rekt) and a patch/
    # upgrade check. A contract that was already drained, or whose current
    # deployment is patched, is safe to publish.
    if c.chain_id is None:
        return ("pass", "synthetic/repo contract")
    return ("unknown", "exploit/patch status not checked (needs external feed)")


def _no_live_clone(c: RawContract) -> tuple[str, str]:
    # TODO: scan a bytecode/source index for un-patched deployments of the same
    # code. A PoC against a patched contract can still hit an un-patched fork.
    if c.chain_id is None:
        return ("pass", "synthetic/repo contract")
    return ("unknown", "clone scan not performed (needs bytecode index)")


PURE_CHECKS: dict[str, Callable[[RawContract], tuple[str, str]]] = {
    "has_source": _has_source,
    "is_real_target": _is_real_target,
}

EXTERNAL_CHECKS: dict[str, Callable[[RawContract], tuple[str, str]]] = {
    "no_live_funds": _no_live_funds,
    "exploited_or_patched": _exploited_or_patched,
    "no_live_clone": _no_live_clone,
}


def screen(contract: RawContract, assume: set[str] | None = None) -> EligibilityResult:
    """Run every gate. `assume` names external checks the caller has verified by
    hand (e.g. {"no_live_funds"}); those are recorded as "pass (asserted)".

    Eligible iff every pure check passes and every external check is either pass
    or asserted. An "unknown" that is not asserted blocks eligibility.
    """
    assume = assume or set()
    checks: dict[str, str] = {}
    reasons: list[str] = []

    for name, fn in PURE_CHECKS.items():
        status, why = fn(contract)
        checks[name] = status
        if status != "pass":
            reasons.append(f"{name}: {why}")

    for name, fn in EXTERNAL_CHECKS.items():
        status, why = fn(contract)
        if status == "unknown" and name in assume:
            checks[name] = "pass (asserted)"
            continue
        checks[name] = status
        if status != "pass":
            reasons.append(f"{name}: {why}")

    eligible = all(s.startswith("pass") for s in checks.values())
    return EligibilityResult(eligible=eligible, checks=checks, reasons=tuple(reasons))
