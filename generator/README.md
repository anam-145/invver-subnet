# generator

Generates machine-checkable invariants for a contract that has **no transaction history**, and provides the Foundry harness that turns one into a pass/fail check.

This is the Tier 1 supply side of the subnet: the standard invariant classes a validator can be handed without a human writing them.

---

## Why this exists

`Trace2Inv` and similar tools mine invariants out of a contract's past transactions. They work well — we reproduced 23 of 27 real exploits blocked at 3.99% FP — but they structurally cannot run on a contract that was deployed yesterday. There is nothing to mine.

This pipeline reads source only.

| Stage | What it does | Needs an API key | State |
|---|---|---|---|
| **1 — Retrieval** | Extract static signals, rank a reference property corpus against them | No | ✅ Working, measured |
| **2 — Generation** | Give the retrieved properties to a model as in-context examples; get back invariants, each carrying one executable `assert` | Yes (or paste the prompt into a chat UI) | Implemented, not yet run |
| **3 — Verification** | Plant the assert, run an exploit against it in a forked EVM | No (needs Foundry) | Harness written, not yet executed |

---

## Setup

```bash
npm install
```

## Stage 1 — retrieval, no key required

```bash
npm run step1
```

Measured output:

```
detected signals:
  ✓ erc777_hook
  ✓ external_call_before_state_write
  ✓ no_reentrancy_guard
  ✓ per_account_cap
  ✓ value_transfer
  · tx_origin / owner_check / price_oracle / timestamp_dep / total_supply
  ✓ payable_receive

check-effect-interaction violation:
  ! claim(): token.transfer(...)  →  _mints += ...

reference property ranking:
  → [score  7] reentrancy/NonReentrantLock
  → [score  6] reentrancy/CheckEffectInteraction
  → [score  5] money_flow/PerAccountUpperBound
  → [score  4] money_flow/AccountingConservation
  → [score  2] gas_control/GasUpperBound
    [score  2] special_storage/MonotonicCounter
    [score  1] access_control/OnlyEOA
    [score  0] access_control/OnlySenderOwner
    [score  0] money_flow/TotalSupplyConsistency
    [score  0] oracle/PriceDeviationBound
    [score  0] time_lock/MinDelay
```

Zero transaction history, no model call, deterministic — and the vulnerable function is located from structure alone. The top five are passed to stage 2 as in-context examples.

## Stage 2 — generation

Two paths. Same result.

**(a) With an API key**

```bash
# PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
npm run generate

# bash
export ANTHROPIC_API_KEY=sk-ant-...
npm run generate
```

An `ant auth login` profile also works with no environment variable. Output goes to the console and to `out/invariants.json`.

**(b) Without API credits — run it by hand**

```bash
npm run prompt
```

Writes `out/prompt.md`, containing byte-for-byte what the API would receive. Paste the system prompt, user message, and schema block into a chat interface running the same model, then save the returned JSON as `out/invariants.json`. The rest of the pipeline continues unchanged.

Same prompt, same model, so the result is a real result — but note that the web interface has no `output_config.format`, so the schema is **requested rather than enforced**. Check the returned JSON against the schema by eye, and if you quote a figure obtained this way, say how it was obtained.

## Stage 3 — verification with Foundry

```bash
curl -L https://foundry.paradigm.xyz | bash && foundryup

forge install foundry-rs/forge-std --no-commit
forge install OpenZeppelin/openzeppelin-contracts@v4.9.6 --no-commit

forge test --match-contract InvariantCheckTest -vv
```

> ⚠️ OpenZeppelin **v4.9.x is required**. ERC777 was removed in v5, so v5 will not compile.

Three tests, all expected to pass:

| Test | Meaning |
|---|---|
| `testExploitSucceedsWithoutInvariant` | Without an assert, the exploit succeeds silently — final balance 1,900 against a cap of 1,000 |
| `testInvariantCatchesExploit` | With the invariant planted, the exploit breaks it — `Panic(0x01)` |
| `testInvariantAllowsBenign` | Normal traffic does not break it — no false positive |

`testInvariantCatchesExploit` is wrapped in `vm.expectRevert(stdError.assertionError)`, so **detection succeeding means the test passes.** There is no "FAIL is expected" trap here.

---

## The target contract

[DeFiVulnLabs / `SimpleBank`](https://github.com/SunWeb3Sec/DeFiVulnLabs/blob/main/src/test/ERC777-reentrancy.sol) — ERC777 reentrancy.

`src/SimpleBank.sol` is the `SimpleBank` contract extracted from that file. **The logic is unmodified.** We removed one thing: the upstream comment `// Do not follow check-effect-interaction`, so the generator gets no hint about where the bug is.

We chose DeFiVulnLabs over DeFiHackLabs on purpose. DeFiHackLabs replays real incidents, which needs a mainnet fork with an archive RPC and API keys — that would make "generated from source alone" impossible to test honestly.

### The bug

```solidity
function claim(address account, uint256 amount) public returns (bool) {
    require(_mints[account] + amount <= maxMintsPerAddress, "Exceeds max mints per address");

    token.transfer(account, amount);   // interaction first
    _mints[account] += amount;         // effect second   ← CEI violation

    return true;
}
```

Cap is 1,000; the attacker requests 900. During `transfer`, the ERC777 hook fires, the attacker reenters `claim(this, 1000)`, and `require` reads a `_mints` that is still zero. Both calls pass. Final balance: 1,900.

---

## Files

```
src/SimpleBank.sol            the target contract (extracted from DeFiVulnLabs, logic unmodified)
src/reference_db.json         reference property corpus — 11 entries, written by hand
src/retrieve.mjs              stage 1: static signals, CEI detection, ranking
src/generate_invariants.mjs   CLI: stage 1 + stage 2
test/InvariantCheck.t.sol     stage 3: Attacker / InvariantChecker / BenignUser
```

`retrieve.mjs` is ported to the browser in [`../web/assets/app.js`](../web/assets/app.js). **They must be kept in sync** — do not change one without the other.

---

## What is not measured

The build environment for this repository had neither an API key nor `forge` installed, so:

- **Stage 2 has never been executed.** No generated invariant appears anywhere in this repository as a result.
- **Stage 3 has never been compiled.** The expected outcomes above are derived by hand from the source. The final balance of 1,900 agrees with the upstream DeFiVulnLabs comment — *"Expect 900 (the claim amount), but we will get the 1,900 due to reenter to claim 1,000"* — but agreement with a comment is not a measurement.
- The first `forge test` may well fail to compile (OZ v4 paths, pragma). That is a normal first run, not a hidden result.

See [`../docs/evidence.md`](../docs/evidence.md) for the full accounting.

## Design limitations

1. **The retriever is lexical, not embedding-based.** Deterministic and offline, which suits a demo, but it does not generalize to classes absent from the corpus. PropertyGPT's actual method — embedding real Certora reports and searching by similarity — is different and stronger.
2. **The corpus is a stand-in for human properties.** Eleven entries written by hand following Trace2Inv's eight-category taxonomy, not an embedding of real audit reports.
3. **Output clusters in standard categories.** Protocol-specific economic invariants do not come out, because they are not in the corpus. That tier belongs to auditors.
