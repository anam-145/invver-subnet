"""Pipeline tests. Stdlib only, offline — network adapters are exercised against
fixtures by monkeypatching each adapter's module-level http_get.

    cd pipeline && python -m unittest discover tests -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from invver_pipeline import mutate, safety                     # noqa: E402
from invver_pipeline.model import RawContract, SourceFile      # noqa: E402
from invver_pipeline.sources import etherscan, sourcify, LocalRepo  # noqa: E402

VULNERABLE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Vault {
    mapping(address => uint256) public balance;

    function deposit() external payable {
        balance[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 amount = balance[msg.sender];
        require(amount <= address(this).balance);
        balance[msg.sender] = 0;
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok);
    }
}
"""


def raw(source="sourcify", chain=1, content=VULNERABLE, name="Vault", ident="0xabc",
        meta=None):
    return RawContract(
        source=source, identifier=ident, name=name, chain_id=chain,
        files=(SourceFile(path="Vault.sol", content=content),),
        metadata=meta or {},
    )


class TestSourcifyParsing(unittest.TestCase):
    def test_fetch_parses_files(self):
        fixture = json.dumps({
            "status": "full",
            "files": [
                {"name": "Vault.sol", "path": "contracts/Vault.sol", "content": VULNERABLE},
                {"name": "metadata.json", "path": "metadata.json", "content": "{}"},
            ],
        })
        orig = sourcify.http_get
        sourcify.http_get = lambda url, timeout=30.0: fixture
        try:
            c = sourcify.Sourcify().fetch("0xabc", 1)
        finally:
            sourcify.http_get = orig
        self.assertEqual(c.name, "Vault")
        self.assertEqual(len(c.files), 1)          # metadata.json filtered out
        self.assertEqual(c.metadata["match"], "full")

    def test_requires_chain(self):
        with self.assertRaises(Exception):
            sourcify.Sourcify().fetch("0xabc", None)


class TestEtherscanParsing(unittest.TestCase):
    def _fetch(self, source_code):
        fixture = json.dumps({
            "status": "1", "message": "OK",
            "result": [{"SourceCode": source_code, "ContractName": "Vault",
                        "CompilerVersion": "v0.8.20"}],
        })
        orig = etherscan.http_get
        etherscan.http_get = lambda url, timeout=30.0: fixture
        try:
            return etherscan.Etherscan("KEY").fetch("0xabc", 1)
        finally:
            etherscan.http_get = orig

    def test_plain_flattened(self):
        c = self._fetch(VULNERABLE)
        self.assertEqual(len(c.files), 1)
        self.assertIn("contract Vault", c.combined_source)

    def test_double_brace_standard_json(self):
        wrapped = "{" + json.dumps({
            "language": "Solidity",
            "sources": {"src/Vault.sol": {"content": VULNERABLE}},
            "settings": {},
        }) + "}"
        c = self._fetch(wrapped)
        self.assertEqual(c.files[0].path, "src/Vault.sol")

    def test_bare_json_map(self):
        obj = json.dumps({"src/Vault.sol": {"content": VULNERABLE}})
        c = self._fetch(obj)
        self.assertEqual(c.files[0].path, "src/Vault.sol")

    def test_unverified_raises(self):
        with self.assertRaises(Exception):
            self._fetch("")


class TestLocalRepo(unittest.TestCase):
    def test_discover_skips_tests_and_mocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "src").mkdir()
            (root / "test").mkdir()
            (root / "src" / "Vault.sol").write_text(VULNERABLE, encoding="utf-8")
            (root / "test" / "VaultTest.sol").write_text(VULNERABLE, encoding="utf-8")
            (root / "src" / "IVault.sol").write_text(
                "interface IVault { function withdraw() external; }", encoding="utf-8")
            found = list(LocalRepo(root).discover())
            paths = {c.identifier for c in found}
            self.assertIn("src/Vault.sol", paths)
            self.assertNotIn("test/VaultTest.sol", paths)  # test dir skipped


class TestSafety(unittest.TestCase):
    def test_live_contract_unknown_funds_is_not_eligible(self):
        r = safety.screen(raw(chain=1))
        self.assertFalse(r.eligible)
        self.assertEqual(r.checks["no_live_funds"], "unknown")

    def test_asserting_external_checks_makes_it_eligible(self):
        r = safety.screen(raw(chain=1),
                          assume={"no_live_funds", "exploited_or_patched", "no_live_clone"})
        self.assertTrue(r.eligible)

    def test_synthetic_contract_passes_external_checks(self):
        c = raw(source="local:repo", chain=None)
        c = RawContract(source=c.source, identifier=c.identifier, name=c.name,
                        chain_id=None, files=c.files, metadata=c.metadata)
        r = safety.screen(c)
        self.assertTrue(r.eligible)

    def test_interface_only_rejected(self):
        c = raw(content="interface IVault { function withdraw() external; }", chain=None)
        r = safety.screen(c)
        self.assertFalse(r.eligible)
        self.assertEqual(r.checks["is_real_target"], "fail")

    def test_mock_by_filename_rejected(self):
        c = raw(chain=None, meta={"looks_like_support": True})
        r = safety.screen(c)
        self.assertFalse(r.eligible)


class TestMutation(unittest.TestCase):
    def test_swap_cei_produces_a_mutant(self):
        muts = mutate.mutants_for(VULNERABLE, ["swap_cei"])
        self.assertTrue(muts)
        self.assertNotIn("balance[msg.sender] = 0;\n        (bool ok",
                         muts[0].source)  # order changed

    def test_remove_require_one_per_guard(self):
        muts = mutate.mutants_for(VULNERABLE, ["remove_require"])
        self.assertEqual(len(muts), 2)  # two require() lines

    def test_flip_boundary(self):
        muts = mutate.mutants_for(VULNERABLE, ["flip_boundary"])
        self.assertTrue(muts)
        self.assertIn("amount < address(this).balance", muts[0].source)

    def test_deterministic(self):
        a = mutate.mutants_for(VULNERABLE)
        b = mutate.mutants_for(VULNERABLE)
        self.assertEqual([m.source for m in a], [m.source for m in b])

    def test_to_targets_carries_provenance(self):
        c = raw(chain=None)
        recs = mutate.to_targets(c, ["swap_cei"])
        self.assertTrue(recs)
        self.assertEqual(recs[0].kind, "mutant")
        self.assertFalse(recs[0].provenance["compile_checked"])
        self.assertEqual(recs[0].provenance["operator"], "swap_cei")

    def test_compile_gate_is_explicit_stub(self):
        with self.assertRaises(NotImplementedError):
            mutate.compiles(VULNERABLE)


if __name__ == "__main__":
    unittest.main()
