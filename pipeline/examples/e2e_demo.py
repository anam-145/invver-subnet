"""End to end: a contract flows from the generator's candidates through FP
screening into a manifest-ready set.

Run:  cd pipeline && python examples/e2e_demo.py

Steps, all real components:
  1. load the generator's candidate invariants for SimpleBank (the JSON contract
     it emits from STEP1 retrieval — no API key);
  2. screen them against a benign corpus with FP screening;
  3. show the kept set and the manifest flag.

SimpleBank's real candidates are all structural or money-flow — the low-FP
classes — so screening correctly keeps all of them. To show the screen actually
rejecting a farmable invariant, we append one clearly-labelled *injected* oracle
candidate (the 22.3%-FP class from our Trace2Inv reproduction). The benign corpus
and replay verdict are the synthetic part: real replay against an EVM is the
stage-2 + forge work, tracked separately. This demo proves the seam — the
generator's real candidate set flowing through the real screening logic — and
that a high-FP invariant is dropped before it can reach a manifest.

Prints the decisive token only if the flow completes as expected.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from invver_pipeline import fp_screen
from invver_pipeline.bridge import load_candidates
from invver_pipeline.fp_screen import BenignTx, CandidateInvariant

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "tests" / "fixtures" / "candidates_simplebank.json"

INJECTED_ORACLE = CandidateInvariant(
    id="oracle/PriceDeviationBound",
    category="oracle",
    solidity_assert="invariant |price_t - price_{t-1}| / price_{t-1} <= DEV",
)


def main() -> int:
    # 1. candidates straight from the generator's JSON contract
    real = load_candidates(FIXTURE)
    print(f"loaded {len(real)} candidate invariants from the generator:")
    for c in real:
        print(f"  {c.id}")
    print(f"  + injected for illustration: {INJECTED_ORACLE.id} (high-FP class)")

    candidates = real + (INJECTED_ORACLE,)

    # 2. screen against a benign corpus. The fake replayer marks the oracle-class
    #    candidate as firing on 22 of 100 benign tx — the reproduced 22.3% rate.
    corpus = tuple(BenignTx(id=f"tx{i}") for i in range(100))
    oracle_fires = {
        (c.id, f"tx{i}")
        for c in candidates if c.category == "oracle"
        for i in range(22)
    }

    class Replayer:
        def holds(self, invariant, tx):
            return (invariant.id, tx.id) not in oracle_fires

    report = fp_screen.screen(candidates, corpus, Replayer())

    print("\nscreening result:")
    for r in report.results:
        verdict = "KEEP  " if r.passed else "REJECT"
        print(f"  {verdict} {r.invariant_id:<34} {r.reason}")

    kept = fp_screen.kept(report, candidates)

    # 3. assertions that make the token meaningful
    assert kept, "expected at least one invariant to survive"
    assert report.fp_screened, "manifest flag should be set on a non-empty clean set"
    assert all(c.id in report.kept_ids for c in real), \
        "a real low-FP candidate was wrongly rejected"
    assert INJECTED_ORACLE.id in report.rejected_ids, \
        "the high-FP oracle candidate survived — farming still possible"

    print(f"\n  kept for manifest: {[c.id for c in kept]}")
    print(f"  rejected:          {list(report.rejected_ids)}")
    print(f"  fp_screened: {report.fp_screened}")
    print("\nE2E-DEMO-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
