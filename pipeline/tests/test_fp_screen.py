"""FP-screening tests. Stdlib only, offline — the EVM replayer is a fake built
from a fires-on set, so the decision logic is exercised without Foundry.

    cd pipeline && python -m unittest discover -s tests -p test_fp_screen.py -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from invver_pipeline import fp_screen  # noqa: E402
from invver_pipeline.fp_screen import (  # noqa: E402
    BenignTx,
    CandidateInvariant,
    ForgeReplayer,
    screen,
    screen_invariant,
)


class FakeReplayer:
    """A replayer that fires on a fixed set of (invariant_id, tx_id) pairs.

    `holds` returns False exactly for those pairs, True otherwise — so a test
    declares which benign transactions a given invariant is a false positive on.
    """

    def __init__(self, fires_on: set[tuple[str, str]]):
        self.fires_on = fires_on

    def holds(self, invariant, tx) -> bool:
        return (invariant.id, tx.id) not in self.fires_on


CORPUS = tuple(BenignTx(id=f"tx{i}") for i in range(100))

STRUCTURAL = CandidateInvariant("reentrancy/NonReentrantLock", "reentrancy",
                                "assert(depth == 0);")
ORACLE = CandidateInvariant("oracle/PriceDeviationBound", "oracle",
                            "assert(dev <= 5);")


class TestSingleInvariant(unittest.TestCase):
    def test_clean_invariant_passes(self):
        r = screen_invariant(STRUCTURAL, CORPUS, FakeReplayer(set()))
        self.assertTrue(r.passed)
        self.assertEqual(r.fires, 0)
        self.assertEqual(r.fp_rate, 0.0)

    def test_high_fp_invariant_is_rejected(self):
        # oracle fires on 22 of 100 benign tx — the reproduced 22.3% class
        fires = {("oracle/PriceDeviationBound", f"tx{i}") for i in range(22)}
        r = screen_invariant(ORACLE, CORPUS, FakeReplayer(fires))
        self.assertFalse(r.passed)
        self.assertEqual(r.fires, 22)
        self.assertAlmostEqual(r.fp_rate, 0.22)
        self.assertEqual(len(r.fired_on), 22)

    def test_single_false_positive_rejects_at_zero_tolerance(self):
        fires = {("oracle/PriceDeviationBound", "tx7")}
        r = screen_invariant(ORACLE, CORPUS, FakeReplayer(fires))
        self.assertFalse(r.passed)  # default tolerance is 0
        self.assertEqual(r.fired_on, ("tx7",))

    def test_tolerance_can_admit_a_low_rate(self):
        fires = {("oracle/PriceDeviationBound", "tx7")}  # 1% FP
        r = screen_invariant(ORACLE, CORPUS, FakeReplayer(fires), max_fp_rate=0.05)
        self.assertTrue(r.passed)

    def test_reason_is_populated_both_ways(self):
        ok = screen_invariant(STRUCTURAL, CORPUS, FakeReplayer(set()))
        bad = screen_invariant(ORACLE, CORPUS,
                               FakeReplayer({("oracle/PriceDeviationBound", "tx1")}))
        self.assertIn("held", ok.reason)
        self.assertIn("fired", bad.reason)


class TestFailClosed(unittest.TestCase):
    def test_empty_corpus_never_passes(self):
        r = screen_invariant(STRUCTURAL, (), FakeReplayer(set()))
        self.assertFalse(r.passed)
        self.assertIn("corpus too small", r.reason)

    def test_below_min_corpus_never_passes(self):
        small = (BenignTx("tx0"), BenignTx("tx1"))
        r = screen_invariant(STRUCTURAL, small, FakeReplayer(set()), min_corpus=10)
        self.assertFalse(r.passed)

    def test_empty_corpus_is_not_a_clean_pass_even_with_no_fires(self):
        # No fires AND no traffic must still fail — absence of evidence.
        r = screen_invariant(STRUCTURAL, (), FakeReplayer(set()))
        self.assertEqual(r.fires, 0)
        self.assertFalse(r.passed)


class TestBatch(unittest.TestCase):
    def _mixed_report(self):
        fires = {("oracle/PriceDeviationBound", f"tx{i}") for i in range(22)}
        return screen((STRUCTURAL, ORACLE), CORPUS, FakeReplayer(fires))

    def test_keeps_structural_rejects_oracle(self):
        rep = self._mixed_report()
        self.assertEqual(rep.kept_ids, ("reentrancy/NonReentrantLock",))
        self.assertEqual(rep.rejected_ids, ("oracle/PriceDeviationBound",))

    def test_manifest_flag_true_when_kept_set_is_clean(self):
        rep = self._mixed_report()
        # oracle rejected + dropped; the kept set (structural) is clean → ready
        self.assertTrue(rep.fp_screened)

    def test_manifest_flag_false_when_nothing_screened(self):
        rep = screen((), CORPUS, FakeReplayer(set()))
        self.assertFalse(rep.fp_screened)

    def test_manifest_flag_false_when_every_candidate_rejected(self):
        # Both candidates fire on benign traffic -> kept set empty -> not ready.
        fires = {("reentrancy/NonReentrantLock", "tx0"),
                 ("oracle/PriceDeviationBound", "tx0")}
        rep = screen((STRUCTURAL, ORACLE), CORPUS, FakeReplayer(fires))
        self.assertEqual(rep.kept_ids, ())
        self.assertFalse(rep.fp_screened)

    def test_results_in_candidate_order(self):
        rep = self._mixed_report()
        self.assertEqual([r.invariant_id for r in rep.results],
                         ["reentrancy/NonReentrantLock", "oracle/PriceDeviationBound"])

    def test_kept_helper_returns_candidates(self):
        rep = self._mixed_report()
        survivors = fp_screen.kept(rep, (STRUCTURAL, ORACLE))
        self.assertEqual(survivors, (STRUCTURAL,))

    def test_result_for_lookup(self):
        rep = self._mixed_report()
        self.assertFalse(rep.result_for("oracle/PriceDeviationBound").passed)
        with self.assertRaises(KeyError):
            rep.result_for("nope")


class TestForgeReplayerStub(unittest.TestCase):
    """Negative control: the real replayer must fail closed, never fake a pass."""

    def test_forge_replayer_raises_rather_than_passing(self):
        with self.assertRaises(NotImplementedError):
            ForgeReplayer().holds(STRUCTURAL, CORPUS[0])

    def test_forge_replayer_satisfies_the_protocol(self):
        from invver_pipeline.fp_screen import Replayer
        self.assertIsInstance(ForgeReplayer(), Replayer)


if __name__ == "__main__":
    unittest.main()
