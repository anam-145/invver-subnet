"""Headline scenario: FP screening blocks the oracle-farming attack.

Run:  cd pipeline && python examples/fp_demo.py

Constructs a candidate set with one structural invariant (0% FP) and one oracle
invariant (fires on 22% of benign traffic, the reproduced rate), screens both
against a benign corpus, and shows that the oracle invariant is rejected while
the structural one is kept. Also shows that an empty corpus refuses to clear
anything. Prints the decisive token only if every assertion holds, so the gate
fails loudly on any regression.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from invver_pipeline.fp_screen import BenignTx, CandidateInvariant, screen, screen_invariant


def main() -> int:
    corpus = tuple(BenignTx(id=f"tx{i}") for i in range(100))

    structural = CandidateInvariant(
        "reentrancy/NonReentrantLock", "reentrancy", "assert(depth == 0);"
    )
    oracle = CandidateInvariant(
        "oracle/PriceDeviationBound", "oracle", "assert(dev <= 5);"
    )

    # The oracle invariant fires on 22 of 100 legitimate transactions.
    oracle_fires = {("oracle/PriceDeviationBound", f"tx{i}") for i in range(22)}

    class Replayer:
        def holds(self, invariant, tx):
            return (invariant.id, tx.id) not in oracle_fires

    report = screen((structural, oracle), corpus, Replayer())

    print("candidate screening against 100 benign transactions:")
    for r in report.results:
        verdict = "KEEP  " if r.passed else "REJECT"
        print(f"  {verdict} {r.invariant_id:<32} {r.reason}")

    # Assertions that make the token meaningful.
    assert report.kept_ids == ("reentrancy/NonReentrantLock",), report.kept_ids
    assert report.rejected_ids == ("oracle/PriceDeviationBound",), report.rejected_ids
    assert report.fp_screened is True

    empty = screen_invariant(structural, (), Replayer())
    assert empty.passed is False, "empty corpus must not clear an invariant"

    print()
    print(f"  kept:     {list(report.kept_ids)}")
    print(f"  rejected: {list(report.rejected_ids)}")
    print("  empty-corpus screen refused to clear the invariant (fail-closed)")
    print()
    print("FP-SCREEN-DEMO-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
