"""Miner neuron — SKELETON.

Not runnable. Unimplemented steps raise rather than returning something
plausible.

Unlike the validator, this side is deliberately open-ended: everything
interesting a miner does happens inside `search`, and competing
implementations are the point. A miner can fuzz, run symbolic execution,
prompt a model, or replay patterns from a private corpus — the subnet does not
care, because the check is the same either way.
"""

from __future__ import annotations

from invariant_subnet.protocol import Submission, Target


def fetch_open_targets() -> list[Target]:
    """TODO: read currently open targets and their published invariant sets."""
    raise NotImplementedError


def search(target: Target) -> list[str]:
    """Find transaction sequences that break one of the target's invariants.

    TODO. This is the competitive surface of the subnet. Directions we expect
    to pursue, in rough order of how much of the lab's existing work applies:

      - RL over transaction sequences, with the invariant set as the reward
        signal (reward is already dense and deterministic, which is unusual).
      - LLM-driven candidate generation seeded with the invariant statement,
        then concretized by a fuzzer.
      - Classical: Echidna / Medusa style property fuzzing, with the published
        invariant compiled straight in as the property.

    Returns Solidity proof-of-concept sources.
    """
    raise NotImplementedError


def submit(target: Target, poc_source: str) -> Submission:
    """TODO: publish a proof-of-concept to the network."""
    raise NotImplementedError


def run() -> None:
    for target in fetch_open_targets():
        for poc in search(target):
            submit(target, poc)


if __name__ == "__main__":
    raise SystemExit("miner neuron is a skeleton; see docs/architecture.md")
