# Evidence

Every claim this project makes, with its provenance and how you can check it.

Three status levels, and we do not blur them:

- **Reproduced** — we ran it ourselves and the output matched a published reference.
- **Measured** — we ran it ourselves; it is this repository's own output.
- **Cited** — a published figure we did not reproduce. Stated as someone else's number.
- **Not yet measured** — implemented but not executed. Never presented as a result.

---

## Reproduced

### Trace2Inv (ISSTA 2024) — invariants block real historical exploits

| | |
|---|---|
| **Claim** | Combining invariants would have blocked **23 of 27** real historical exploits at a **3.99%** false-positive rate; a more conservative combination blocks **20 of 27** at **0.28%** FP. |
| **How** | Ran the authors' Docker artifact end to end. Our `RQ2-Results.txt` matched the authors' `RQ2-Expected.txt` exactly. |
| **Winning combination** | `onlyEOA ∧ require(gasStart-gasEnd<=c) ∧ dataFlowUpperBound` (23 blocked, 3.99% FP) · `onlyEOA ∧ (SHA(origin,block) ∨ dataFlowUpperBound)` (20 blocked, 0.28% FP) |
| **Per-category FP** | `NonReentrantLocks` 0.0% · `onlyEOA` 0.2% · `dataFlowUpperBound` 0.7% · `totalSupply` 12.6% · `oracle` 22.3% |
| **Source** | https://github.com/Franklinzhekaiwang/Trace2Inv (MIT) |

**Why this shaped the design.** The highest-yield invariants are *generic defensive patterns*, not protocol-specific logic — which is what makes Tier 1 automatable at all. The FP spread is equally instructive: structural invariants (`NonReentrantLocks`, `onlyEOA`) sit near zero, while threshold-based ones (`oracle` at 22.3%) are unusable alone. Good invariant sets are conjunctions of low-FP structural checks.

**Caveat.** Six of eight categories produced near-empty result files in our run (≈280 bytes vs 304 KB for `Oracle`), so the aggregate FP-rate script divided by zero. The figures above are read from the authors' expected-output file, which our completed categories matched. We reproduced the methodology and the categories that ran; we did not independently recompute the aggregate from a full local run.

---

## Measured

### Retrieval from source alone, zero transaction history

| | |
|---|---|
| **Claim** | On a contract with no transaction history, static retrieval ranks `reentrancy/NonReentrantLock` first (score 7) and automatically locates the check-effect-interaction violation in `claim()`. |
| **How** | `cd generator && npm run step1`. No network, no model call, deterministic. |
| **Also verifiable** | Open the demo page, press **Fix the CEI order**. The violation disappears and reentrancy drops from 7 to 4 — the retriever responds to structure, not to keywords. |

```
detected signals:  erc777_hook · external_call_before_state_write ·
                   no_reentrancy_guard · per_account_cap · value_transfer ·
                   payable_receive

CEI violation:     claim(): token.transfer(...) → _mints += ...

ranking:           7  reentrancy/NonReentrantLock
                   6  reentrancy/CheckEffectInteraction
                   5  money_flow/PerAccountUpperBound
                   4  money_flow/AccountingConservation
                   2  gas_control/GasUpperBound
                   2  special_storage/MonotonicCounter
                   1  access_control/OnlyEOA
                   0  access_control/OnlySenderOwner
                   0  money_flow/TotalSupplyConsistency
                   0  oracle/PriceDeviationBound
                   0  time_lock/MinDelay
```

This is the claim that matters for the subnet: **Trace2Inv-style tools structurally cannot run on a fresh contract, and this stage can.**

### Deterministic scoring rule

| | |
|---|---|
| **Claim** | The scoring rule is a pure function of execution results — same inputs, same score, on every validator. |
| **How** | `cd subnet && python -m unittest discover tests -v`. Stdlib only, no dependencies. |

---

## Cited, not reproducible

### PropertyGPT (NDSS 2025) — properties from source alone

| | |
|---|---|
| **Reported** | 80% recall against expert-written properties; 12 zero-days found. |
| **Why we did not reproduce it** | The repository publishes the benchmark contracts, human-written and LLM-written properties, and raw experiment data — but **not the prototype**. The tool is being commercialized by MetaTrust Labs and is closed. |
| **Consequence** | Unlike Trace2Inv, we cannot put our hands on this one. We treat 80% recall as the authors' figure, not ours. The generator in this repository is our own implementation of the same idea, not a port. |
| **Source** | https://github.com/Pr0pertyGPT/PropertyGPT |

---

## Not yet measured

Implemented, committed, and readable — but not executed. These appear nowhere in this project as results.

| Item | Blocked on | Location |
|---|---|---|
| LLM invariant generation output | No billed API endpoint | `generator/src/generate_invariants.mjs` |
| Foundry exploit/assert measurement | `forge` not installed in the build environment | `generator/test/InvariantCheck.t.sol` |
| Miner / validator neurons | Not written beyond skeletons | `subnet/neurons/` |
| Testnet subnet | Not started | — |

**On the exploit trace.** The demo page animates the reentrancy path ending at a balance of 1,900 against a cap of 1,000. That trace is derived by hand from the source, and it is labelled as such on the page. It agrees with the upstream DeFiVulnLabs comment — *"Expect 900 (the claim amount), but we will get the 1,900 due to reenter to claim 1,000"* — but agreement with a comment is not a measurement, and we do not present it as one.

**Reproducing the generation stage without an API key.** `cd generator && npm run prompt` writes the exact prompt the pipeline would send to `out/prompt.md`. Paste it into any chat interface running the same model and you get a real result — obtained manually rather than through the API. If a figure obtained that way is ever quoted here, it will say so.

---

## How to check any of this yourself

```bash
git clone <this repo> && cd invver-subnet

cd generator && npm install && npm run step1     # retrieval, measured above
cd ../subnet  && python -m unittest discover tests -v   # scoring rule
cd ../web     && python -m http.server 8080      # demo page
```

Nothing above needs an API key, a wallet, or a fork.
