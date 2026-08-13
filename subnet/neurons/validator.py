"""Validator neuron — SKELETON.

Not runnable. It exists to make the shape of the loop reviewable, and every
unimplemented step raises rather than returning a plausible-looking value.

The point of the design is how little belongs in here. A validator does not
analyze, rank, or judge. It executes, and the scoring rule in
``invariant_subnet.scoring`` — which is implemented and tested — turns
execution results into weights.
"""

from __future__ import annotations

from invariant_subnet.protocol import ExecutionResult, Submission, Target
from invariant_subnet.scoring import FindingLedger, normalize_weights, score_round


def load_target(target_id: str) -> Target:
    """TODO: load the target contract and its published invariant set."""
    raise NotImplementedError


def collect_submissions(target: Target) -> list[Submission]:
    """TODO: pull miner submissions for this round off the network."""
    raise NotImplementedError


def execute(submission: Submission, target: Target) -> ExecutionResult:
    """Run the proof-of-concept in a forked EVM with each published invariant
    compiled in as an ``assert``, and report which ones reverted.

    TODO: shell out to `forge test` against a generated harness. The harness
    itself is already written — see generator/test/InvariantCheck.t.sol.

    This is the only place a validator touches the submission, and it makes no
    decisions: an assert either reverted with Panic(0x01) or it did not.
    """
    raise NotImplementedError


def set_weights(weights: dict[str, float]) -> None:
    """TODO: submit weights to the subnet."""
    raise NotImplementedError


def run_round(target_id: str, ledger: FindingLedger) -> dict[str, float]:
    """The whole validator loop. Note that nothing between `execute` and
    `set_weights` is a judgment call."""
    target = load_target(target_id)
    submissions = collect_submissions(target)
    results = [execute(s, target) for s in submissions]
    scored = score_round(results, target, ledger)
    weights = normalize_weights(scored)
    set_weights(weights)
    return weights


if __name__ == "__main__":
    raise SystemExit("validator neuron is a skeleton; see docs/architecture.md")
