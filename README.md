# Invariant Subnet

**A Bittensor subnet where validators score exploits by executing an assertion, not by judging a report.**

Live demo → **[TODO: paste the deployed URL here]?lang=en** · Built by **Anam145**, an operating smart contract security audit firm, with the Intelligence Computing Lab at Hansung University.

---

## The problem this exists to solve

Security is an obvious fit for a Bittensor subnet right up until you ask how validators score a submission.

If a miner submits a free-form vulnerability report, some validator has to read it and decide whether it is real, novel, and severe. That requires the validator to be at least as capable as the miner, which inverts the trust model a subnet depends on. Every mechanism you bolt on from there — reputation, committees, LLM juries — is an attempt to patch a scoring function that was never deterministic to begin with.

Exploit discovery itself has exactly the asymmetry a subnet wants. Finding a working exploit is open-ended, creative, expensive. Checking one is a few milliseconds of deterministic EVM execution. The open question was never *whether* to reward exploit search — it was **what to make the check out of.**

## The answer

Make the unit of scoring an **executable assertion**.

Every target contract ships with a published set of machine-checkable invariants. A submission counts only if it makes a specific invariant revert on-chain.

| Actor | Does | Implemented in |
|---|---|---|
| **Miner** | Searches for a transaction sequence that breaks an invariant. Open-ended, creative work. | [`generator/test/InvariantCheck.t.sol`](generator/test/InvariantCheck.t.sol) → `Attacker` |
| **Validator** | Runs the assertion. No branching, no heuristic, no verdict logic. | same file → `InvariantChecker` |
| **Firm / RAG** | Supplies the invariants. Standard classes generated from source; protocol-specific ones written by auditors. | [`generator/src/generate_invariants.mjs`](generator/src/generate_invariants.mjs) |

Every honest validator computes a bit-identical result from the same inputs. Cheating stops being a grading dispute and becomes a failed execution.

Design detail — novelty keys, severity weighting, and the anti-collusion properties — is in **[docs/architecture.md](docs/architecture.md)**.

---

## What is actually verified

We separate what we measured from what we are citing. The same distinction is enforced in the demo page and in every subdirectory README.

| Claim | Source | Status |
|---|---|---|
| Invariants would have blocked 23 of 27 real historical exploits at 3.99% FP; 20 of 27 at 0.28% FP | We reproduced [Trace2Inv](https://github.com/Franklinzhekaiwang/Trace2Inv) (ISSTA'24) in Docker; output matches the authors' expected files | **Reproduced by us** |
| Retrieval ranks `reentrancy` first on a contract with zero transaction history, and locates the check-effect-interaction violation automatically | This repository; runs live in the browser | **Measured** |
| Properties can be generated from source alone at 80% recall, finding 12 zero-days | [PropertyGPT](https://github.com/Pr0pertyGPT/PropertyGPT) (NDSS'25) reported figures. The prototype is commercialized and closed, so we cannot reproduce it | **Cited, not reproducible** |
| LLM-generated invariant output | Implemented; not yet run against a billed endpoint | **Not yet measured** |
| Foundry measurement of the exploit/assert loop | Harness written and committed; not yet executed | **Not yet measured** |

Full table with reasoning: **[docs/evidence.md](docs/evidence.md)**.

We validated the scoring mechanism before spending on inference, because a security subnet whose reward signal is gameable is worse than no subnet. Nothing in this repository reports a number we did not measure.

---

## Repository map

```
generator/   Node.js — invariant generation and the Foundry verification harness
subnet/      Python  — miner, validator, and network activity monitoring   [in progress]
web/         Static  — the public demo page (KO/EN)
docs/        Architecture and evidence
```

Each directory has its own README with run instructions.

---

## Quickstart

**Retrieval stage — no API key, no network, deterministic:**

```bash
cd generator
npm install
npm run step1
```

```
check-effect-interaction violation:
  ! claim(): token.transfer(...)  →  _mints += ...

reference property ranking:
  → [score  7] reentrancy/NonReentrantLock
  → [score  6] reentrancy/CheckEffectInteraction
  → [score  5] money_flow/PerAccountUpperBound
  → [score  4] money_flow/AccountingConservation
  → [score  2] gas_control/GasUpperBound
    [score  1] access_control/OnlyEOA
    [score  0] oracle/PriceDeviationBound … and 3 more
```

Zero transaction history, no model call — and the vulnerable function is located from structure alone.

**Demo page:**

```bash
cd web && python -m http.server 8080     # → http://localhost:8080/?lang=en
```

**Generation and verification stages:** see [`generator/README.md`](generator/README.md). Both are implemented; neither has been run against a billed endpoint or a Foundry install yet, and the repository says so wherever they appear.

---

## The target contract

[DeFiVulnLabs / `SimpleBank`](https://github.com/SunWeb3Sec/DeFiVulnLabs/blob/main/src/test/ERC777-reentrancy.sol) — ERC777 reentrancy. Logic is unmodified; we removed only the upstream comment that names the bug, so the generator gets no hint.

```solidity
function claim(address account, uint256 amount) public returns (bool) {
    require(_mints[account] + amount <= maxMintsPerAddress, "Exceeds max mints per address");

    token.transfer(account, amount);   // interaction first
    _mints[account] += amount;         // effect second   ← CEI violation

    return true;
}
```

The per-account cap is 1,000 and the attacker asks for 900. The ERC777 hook fires mid-transfer, the attacker reenters `claim`, and `require` reads a `_mints` value that has not been updated yet. Final balance: 1,900.

We chose DeFiVulnLabs over DeFiHackLabs deliberately: real-incident replays need a mainnet fork with an archive RPC, which would make "generated from source alone" untestable.

---

## Known limitations

1. **The retriever is lexical, not embedding-based.** Deterministic and offline, which suits a demo, but it does not generalize to classes absent from the reference corpus. PropertyGPT's approach (embedding real Certora reports) is different and stronger.
2. **The reference corpus is a stand-in.** Eleven properties written by hand following Trace2Inv's eight-category taxonomy — not an embedding of real audit reports.
3. **Output clusters in standard categories.** Protocol-specific economic invariants do not come out, because they are not in the corpus. That tier is the auditor's job — which is precisely the business case, not a gap we are hiding.
4. **Single-contract demo.** A real subnet needs miners doing this across many contracts; scaling is open.
5. **Not yet on-chain.** No testnet subnet running. See [docs/architecture.md](docs/architecture.md) for the plan.

---

## References

- Trace2Inv — *Do Smart Contract Invariants Hold?*, ISSTA 2024 (MIT)
- PropertyGPT — *LLM-driven Formal Verification of Smart Contracts*, NDSS 2025
- DeFiVulnLabs (MIT)

## License

MIT — see [LICENSE](LICENSE). Vendored references keep their own licenses.
