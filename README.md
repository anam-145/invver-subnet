# Invariant Subnet

**A Bittensor subnet for smart contract exploit discovery, where validators score a submission by executing an assertion instead of judging a report.**

Early-stage design by [Anam145](https://sites.google.com/view/iclab-hansung), an operating smart contract security audit firm, with the Intelligence Computing Lab at Hansung University. This repository is the design plus a working core — not a deployed subnet. [What is real and what is not](#status).

---

## Why most security subnets do not work

Security looks like an obvious fit for a subnet right up until you ask how a validator scores a submission.

If a miner submits a free-form vulnerability report, some validator has to read it and decide whether it is real, novel, and severe. That requires the validator to be at least as capable as the miner — which inverts the trust model a subnet depends on. Everything bolted on from there (reputation, committees, LLM juries) is a patch on a scoring function that was never deterministic.

Exploit discovery itself has exactly the asymmetry a subnet wants:

| | Cost | Who bears it |
|---|---|---|
| Finding a working exploit | Open-ended search, expensive, creative | **Miner** |
| Checking one | One EVM execution, milliseconds, deterministic | **Validator** |

Hard to produce, trivial to verify. The open question was never *whether* to reward exploit search — it was **what to make the check out of.**

---

## The miner task

Each open target is a contract published together with a **set of machine-checkable invariants** — properties that must always hold, each expressed as one executable Solidity `assert`.

> Target: `SimpleBank`
> `INV-1` (critical) — `assert(bank._mints(account) <= bank.maxMints());`
> `INV-2` (high) — `assert(token.balanceOf(account) <= bank.maxMints());`

**A miner's job: find a transaction sequence that makes one of those assertions fail.**

That is the entire task. It is open-ended and creative — how you search is the competitive surface, and we expect divergent approaches:

- RL over transaction sequences, using the invariant set as the reward signal. Unusually, the reward here is already dense and deterministic.
- LLM-driven candidate generation seeded with the invariant statement, then concretized by a fuzzer.
- Classical property fuzzing (Echidna / Medusa) with the published invariant compiled straight in as the property.

The subnet does not care which. The check is identical either way.

Miners submit a Solidity proof-of-concept. Skeleton: [`subnet/neurons/miner.py`](subnet/neurons/miner.py).

## The validator task

**A validator runs the assertion. That is all it does.**

```solidity
contract InvariantChecker {
    function checkPerAccountUpperBound(address account) external view {
        assert(bank._mints(account) <= bank.maxMints());
    }
    function checkBalanceUpperBound(address account) external view {
        assert(token.balanceOf(account) <= bank.maxMints());
    }
}
```

No branching. No heuristic. No model call. No logic that decides whether something *is* a vulnerability — that question was settled when the target's invariant set was published.

The validator forks the chain, replays the miner's proof-of-concept with each published invariant compiled in as an `assert`, and records which ones reverted with `Panic(0x01)`. Those execution results are the only input to scoring.

**Consequence: two honest validators holding the same results produce bit-identical weights.** A dishonest validator is not expressing a different opinion — it is producing a result every other validator can immediately contradict by running the same bytecode.

Loop: [`subnet/neurons/validator.py`](subnet/neurons/validator.py) · Harness: [`generator/test/InvariantCheck.t.sol`](generator/test/InvariantCheck.t.sol)

## How submissions are scored

Implemented as a pure function with 18 passing tests: [`subnet/invariant_subnet/scoring.py`](subnet/invariant_subnet/scoring.py).

| Factor | Rule | Why it cannot be argued with |
|---|---|---|
| **Broke anything** | Binary, from execution | An assert reverted or it did not |
| **Severity** | Attached to the invariant class, fixed when the target is published | Never assigned per submission, so it is never negotiated after the fact |
| **Novelty** | Key = `(target, invariant, hash of minimized state delta)` | Two miners who rediscover the same bug produce the same key; only the first is paid |
| **Known exploits** | Seeded into the ledger before the target opens | Replaying a public attack scores zero |
| **Minimality** | Call count, bounded both ways | An integer |
| **Ordering** | Submissions processed sorted by id | "Who was first" does not depend on arrival order |

```bash
cd subnet && python -m unittest discover tests -v    # no dependencies
```

## Where invariants come from

Two tiers, and the split is the business model.

**Tier 1 — standard classes, generated from source.** Reentrancy, money-flow bounds, access control, gas bounds. Our reproduction of Trace2Inv (ISSTA'24) found this tier alone would have blocked 23 of 27 real historical exploits. Automatable — implemented in [`generator/`](generator).

**Tier 2 — protocol-specific economic invariants, written by auditors.** Deliberately not automated. This is what an audit firm already produces, and it is the part a competing subnet cannot bootstrap without one.

A subnet with only Tier 1 is a nicer Slither. A subnet with both is a market for the thing that actually causes large losses.

Full design — attack surface of the mechanism, target rotation, what is still undecided: **[docs/architecture.md](docs/architecture.md)**.

---

## Status

An early-stage submission with a working core. We keep the line between the two visible rather than blurred.

| | State |
|---|---|
| Scoring rule | **Implemented**, 18 passing tests, zero dependencies |
| Invariant retrieval from source | **Implemented and measured** — ranks `reentrancy` first on a contract with no transaction history, and locates the check-effect-interaction violation automatically |
| Trace2Inv reproduction | **Reproduced by us** — 23/27 exploits blocked at 3.99% FP; 20/27 at 0.28% FP, matching the authors' expected output |
| LLM invariant generation | Implemented, **not yet run** against a billed endpoint |
| Foundry exploit/assert measurement | Harness written, **not yet executed** |
| Miner / validator neurons | **Skeletons.** Unimplemented functions raise rather than returning plausible values |
| Testnet subnet | **Not started** |

Nothing in this repository reports a number we did not measure. Reasoning and sources: **[docs/evidence.md](docs/evidence.md)**.

---

## Repository map

```
subnet/      Python — scoring rule, miner/validator skeletons, network monitoring
generator/   Node.js — invariant generation from source + the Foundry harness
web/         A static page walking through the pipeline (runs locally, KO/EN)
docs/        Architecture and evidence
```

## Try it

Both run with no API key, no wallet, no network.

```bash
# the scoring rule
cd subnet && python -m unittest discover tests -v

# invariant retrieval on a contract with zero transaction history
cd generator && npm install && npm run step1
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
    [score  1] access_control/OnlyEOA … and 4 more at 0
```

Optional walkthrough page: `cd web && python -m http.server 8080` → `localhost:8080/?lang=en`

## The target contract

[DeFiVulnLabs / `SimpleBank`](https://github.com/SunWeb3Sec/DeFiVulnLabs/blob/main/src/test/ERC777-reentrancy.sol) — ERC777 reentrancy. Logic unmodified; we removed only the upstream comment naming the bug, so the generator gets no hint.

```solidity
function claim(address account, uint256 amount) public returns (bool) {
    require(_mints[account] + amount <= maxMintsPerAddress, "Exceeds max mints per address");

    token.transfer(account, amount);   // interaction first
    _mints[account] += amount;         // effect second   ← CEI violation

    return true;
}
```

The cap is 1,000 and the attacker asks for 900. The ERC777 hook fires mid-transfer, the attacker reenters `claim`, and `require` reads a `_mints` value that has not been updated yet. Final balance: 1,900 — which is what `INV-1` and `INV-2` above catch.

## Known limitations

1. **The retriever is lexical, not embedding-based.** Deterministic and offline, but it does not generalize to classes absent from the reference corpus.
2. **The reference corpus is a stand-in** — eleven properties written by hand following Trace2Inv's taxonomy, not an embedding of real audit reports.
3. **Output clusters in standard categories.** Protocol-specific economic invariants do not come out, because they are not in the corpus. That tier is the auditor's job — the business case, not a gap we are hiding.
4. **Single-contract demo.** A real subnet needs miners working across many contracts; scaling is open.
5. **Emission split, reward curve, and target rotation cadence are undecided.** See [docs/architecture.md](docs/architecture.md) §6.

## References

- Trace2Inv — *Do Smart Contract Invariants Hold?*, ISSTA 2024 (MIT)
- PropertyGPT — *LLM-driven Formal Verification of Smart Contracts*, NDSS 2025
- DeFiVulnLabs (MIT)

## License

MIT — see [LICENSE](LICENSE). Vendored references keep their own licenses.
