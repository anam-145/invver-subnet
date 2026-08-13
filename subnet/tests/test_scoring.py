"""Tests for the scoring rule. Stdlib only:

    cd subnet && python -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from invariant_subnet.protocol import (  # noqa: E402
    ExecutionResult,
    Invariant,
    NoveltyKey,
    Target,
)
from invariant_subnet.scoring import (  # noqa: E402
    FindingLedger,
    minimality_factor,
    normalize_weights,
    score_round,
    score_submission,
)

TARGET = Target(
    id="simplebank",
    name="DeFiVulnLabs / SimpleBank",
    source_uri="generator/src/SimpleBank.sol",
    invariants=(
        Invariant(
            id="INV-1",
            category="money_flow",
            severity="critical",
            solidity_assert="assert(bank._mints(account) <= bank.maxMints());",
            statement="Per-account accumulation never exceeds the published cap.",
        ),
        Invariant(
            id="INV-2",
            category="money_flow",
            severity="high",
            solidity_assert="assert(token.balanceOf(account) <= bank.maxMints());",
            statement="Delivered balance never exceeds the published cap.",
        ),
    ),
)


def result(
    sub_id="s1",
    miner="miner_a",
    broken=("INV-1",),
    calls=4,
    delta="deadbeefcafe0001",
    error=None,
):
    return ExecutionResult(
        submission_id=sub_id,
        target_id=TARGET.id,
        miner_hotkey=miner,
        broken_invariant_ids=broken,
        call_count=calls,
        state_delta_hash=delta,
        error=error,
    )


class TestInvariantValidation(unittest.TestCase):
    def test_invariant_must_carry_an_assert(self):
        with self.assertRaises(ValueError):
            Invariant(
                id="BAD",
                category="money_flow",
                severity="high",
                solidity_assert="the contract should be safe",
            )

    def test_unknown_severity_rejected(self):
        with self.assertRaises(ValueError):
            Invariant(
                id="BAD",
                category="money_flow",
                severity="catastrophic",
                solidity_assert="assert(x <= y);",
            )


class TestScoreSubmission(unittest.TestCase):
    def test_breaking_a_critical_invariant_scores(self):
        s = score_submission(result(calls=3), TARGET, FindingLedger())
        self.assertAlmostEqual(s.score, 1.0)
        self.assertEqual(len(s.novel_findings), 1)

    def test_nothing_broken_scores_zero(self):
        s = score_submission(result(broken=()), TARGET, FindingLedger())
        self.assertEqual(s.score, 0.0)
        self.assertIn("no invariant broke", s.reasons)

    def test_failed_execution_scores_zero(self):
        s = score_submission(result(error="revert: setup failed"), TARGET, FindingLedger())
        self.assertEqual(s.score, 0.0)

    def test_severity_is_taken_from_the_published_invariant(self):
        crit = score_submission(result(broken=("INV-1",), calls=3), TARGET, FindingLedger())
        high = score_submission(result(broken=("INV-2",), calls=3), TARGET, FindingLedger())
        self.assertGreater(crit.score, high.score)

    def test_unpublished_invariant_is_ignored_not_rewarded(self):
        s = score_submission(result(broken=("INV-99",)), TARGET, FindingLedger())
        self.assertEqual(s.score, 0.0)
        self.assertTrue(any("not published" in r for r in s.reasons))

    def test_highest_severity_wins_when_several_break(self):
        s = score_submission(
            result(broken=("INV-1", "INV-2"), calls=3), TARGET, FindingLedger()
        )
        self.assertAlmostEqual(s.score, 1.0)
        self.assertEqual(len(s.novel_findings), 2)


class TestNovelty(unittest.TestCase):
    def test_second_miner_with_the_same_finding_gets_nothing(self):
        ledger = FindingLedger()
        first = score_submission(result(sub_id="s1", miner="a"), TARGET, ledger)
        second = score_submission(result(sub_id="s2", miner="b"), TARGET, ledger)
        self.assertGreater(first.score, 0.0)
        self.assertEqual(second.score, 0.0)
        self.assertEqual(len(second.duplicate_findings), 1)

    def test_a_different_exploit_path_is_still_novel(self):
        ledger = FindingLedger()
        score_submission(result(sub_id="s1", delta="aaaa1111"), TARGET, ledger)
        other = score_submission(
            result(sub_id="s2", miner="b", delta="bbbb2222", calls=3), TARGET, ledger
        )
        self.assertGreater(other.score, 0.0)

    def test_seeded_known_exploit_pays_nothing(self):
        known = NoveltyKey(TARGET.id, "INV-1", "deadbeefcafe0001")
        ledger = FindingLedger([(known, "public_disclosure")])
        s = score_submission(result(), TARGET, ledger)
        self.assertEqual(s.score, 0.0)
        self.assertTrue(any("public_disclosure" in r for r in s.reasons))


class TestMinimality(unittest.TestCase):
    def test_shorter_is_not_worse(self):
        self.assertGreaterEqual(minimality_factor(3), minimality_factor(10))

    def test_factor_is_bounded(self):
        self.assertEqual(minimality_factor(1), 1.0)
        self.assertGreaterEqual(minimality_factor(10_000), 0.4)


class TestDeterminism(unittest.TestCase):
    def test_round_order_does_not_change_outcomes(self):
        rs = [
            result(sub_id="s3", miner="c", delta="cccc"),
            result(sub_id="s1", miner="a", delta="aaaa"),
            result(sub_id="s2", miner="b", delta="bbbb"),
        ]
        a = normalize_weights(score_round(rs, TARGET, FindingLedger()))
        b = normalize_weights(score_round(list(reversed(rs)), TARGET, FindingLedger()))
        self.assertEqual(a, b)

    def test_identical_rediscovery_resolves_the_same_way_either_order(self):
        """Two miners submit the *same* finding. Whoever has the lower
        submission id is first, regardless of arrival order."""
        rs = [
            result(sub_id="s2", miner="b", delta="same"),
            result(sub_id="s1", miner="a", delta="same"),
        ]
        a = normalize_weights(score_round(rs, TARGET, FindingLedger()))
        b = normalize_weights(score_round(list(reversed(rs)), TARGET, FindingLedger()))
        self.assertEqual(a, b)
        self.assertEqual(list(a), ["a"])  # s1 < s2, so miner "a" claimed it first


class TestWeights(unittest.TestCase):
    def test_weights_sum_to_one(self):
        rs = [
            result(sub_id="s1", miner="a", delta="aaaa", calls=3),
            result(sub_id="s2", miner="b", delta="bbbb", broken=("INV-2",), calls=3),
        ]
        w = normalize_weights(score_round(rs, TARGET, FindingLedger()))
        self.assertAlmostEqual(sum(w.values()), 1.0)
        self.assertGreater(w["a"], w["b"])  # critical outranks high

    def test_empty_round_yields_no_weights(self):
        self.assertEqual(normalize_weights([]), {})

    def test_all_zero_round_yields_no_weights(self):
        rs = [result(sub_id="s1", broken=())]
        self.assertEqual(normalize_weights(score_round(rs, TARGET, FindingLedger())), {})


if __name__ == "__main__":
    unittest.main()
