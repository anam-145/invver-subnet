"""Bridge tests — the generator↔pipeline seam.

The parsing path runs against a committed fixture (offline). The live-node path
runs the real generator if node is on PATH, and is skipped otherwise; the
missing-node behaviour is tested directly by pointing the adapter at a
nonexistent executable.

    cd pipeline && python -m unittest discover -s tests -p test_bridge.py -v
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from invver_pipeline import bridge  # noqa: E402
from invver_pipeline.bridge import (  # noqa: E402
    BridgeError,
    GeneratorUnavailable,
    load_candidates,
    parse_candidates,
)
from invver_pipeline.fp_screen import CandidateInvariant  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "candidates_simplebank.json"
REPO = HERE.parents[1]                 # invver-subnet/
GEN_DIR = REPO / "generator"


class TestParse(unittest.TestCase):
    def test_fixture_parses_to_candidates(self):
        cands = load_candidates(FIXTURE)
        self.assertTrue(cands)
        self.assertTrue(all(isinstance(c, CandidateInvariant) for c in cands))

    def test_reentrancy_ranked_first_survives_the_seam(self):
        cands = load_candidates(FIXTURE)
        self.assertEqual(cands[0].id, "reentrancy/NonReentrantLock")
        self.assertEqual(cands[0].category, "reentrancy")
        self.assertTrue(cands[0].solidity_assert)  # sketch mapped to assert

    def test_rejects_unknown_schema(self):
        with self.assertRaises(BridgeError):
            parse_candidates({"schema": "something/else", "candidates": []})

    def test_rejects_missing_candidates_array(self):
        with self.assertRaises(BridgeError):
            parse_candidates({"schema": bridge.SCHEMA})

    def test_rejects_candidate_missing_fields(self):
        with self.assertRaises(BridgeError):
            parse_candidates({
                "schema": bridge.SCHEMA,
                "candidates": [{"id": "x", "category": "y"}],  # no solidity_sketch
            })

    def test_missing_file_raises(self):
        with self.assertRaises(BridgeError):
            load_candidates(HERE / "fixtures" / "does_not_exist.json")


class TestContract(unittest.TestCase):
    """G2: the emitted document conforms to the documented contract."""

    def test_emitted_document_conforms_to_contract(self):
        doc = __import__("json").loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], "invver.candidates/1")
        self.assertIn("signals", doc)
        self.assertIn("cei_violations", doc)
        self.assertIsInstance(doc["candidates"], list)
        self.assertTrue(doc["candidates"])
        for c in doc["candidates"]:
            self.assertIn("id", c)
            self.assertIn("category", c)
            self.assertIn("solidity_sketch", c)
        # SimpleBank is an ERC777 reentrancy target: the CEI violation must be
        # present and reentrancy must lead.
        self.assertTrue(doc["cei_violations"])
        self.assertEqual(doc["candidates"][0]["id"], "reentrancy/NonReentrantLock")


class TestLiveNode(unittest.TestCase):
    @unittest.skipIf(shutil.which("node") is None, "node not on PATH")
    def test_invoke_generator_matches_committed_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            live = bridge.invoke_generator(
                "src/SimpleBank.sol", generator_dir=GEN_DIR, out_dir=d
            )
        committed = load_candidates(FIXTURE)
        self.assertEqual([c.id for c in live], [c.id for c in committed])

    def test_missing_node_raises_rather_than_faking(self):
        with self.assertRaises(GeneratorUnavailable):
            bridge.invoke_generator(
                "src/SimpleBank.sol", generator_dir=GEN_DIR, out_dir="out",
                node="definitely-not-a-real-node-binary-xyz",
            )


if __name__ == "__main__":
    unittest.main()
