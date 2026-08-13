# Architecture

How a submission becomes a score, and why that score cannot be argued with.

---

## 1. The three roles

```
                    ┌──────────────────────────────────────┐
   target contract  │  INVARIANT SUPPLY                    │
        ──────────► │  standard classes  → generated       │
                    │  protocol-specific → auditors        │
                    └──────────────┬───────────────────────┘
                                   │ published invariant set
                                   ▼
   ┌──────────────┐        ┌───────────────┐        ┌──────────────────┐
   │    MINER     │  PoC   │   VALIDATOR   │ revert │      SCORE       │
   │ search for a │ ─────► │ plant assert, │ ─────► │ deterministic,   │
   │ breaking tx  │        │ execute, done │        │ identical across │
   └──────────────┘        └───────────────┘        │ all validators   │
                                                    └──────────────────┘
```

The validator does one thing: run the submitted proof-of-concept in a forked EVM with the invariant compiled in as an `assert`, and record whether it reverts. It never decides whether something *is* a vulnerability.

## 2. Why the asymmetry matters

| | Cost | Who bears it |
|---|---|---|
| Finding a working exploit | Open-ended search, expensive, creative | Miner |
| Checking one | One EVM execution, milliseconds, deterministic | Validator |

This is the shape of problem an incentive market solves better than a payroll — the same reason bug bounties work. Bittensor makes the market continuous, permissionless, and machine-scored instead of ticket-based.

The failure mode of most security-subnet proposals is the opposite property: free-form reports need a validator smarter than the miner. Making the invariant the unit of scoring removes that requirement entirely.

## 3. What miners compete on

Given a target contract and its published invariant set, miners search for a transaction sequence that makes at least one invariant fail. Ranking factors, in order:

1. **Did an invariant break at all** — binary, from execution.
2. **Which one** — severity is a property of the invariant class, fixed and published *before* submissions open. Nobody argues severity after the fact.
3. **Novelty** — first to break a given invariant on a given target. Duplicates collapse under the novelty key (§5).
4. **Minimality** — shorter proof-of-concept wins ties. Also cheap to measure: count the calls.

## 4. Where invariants come from

Two tiers, and the split is the business model.

**Tier 1 — standard classes, generated from source.** Reentrancy, money-flow bounds, access control, gas bounds. Our Trace2Inv reproduction showed this tier alone would have blocked 23 of 27 real historical exploits. Automatable, and implemented in [`generator/`](../generator).

**Tier 2 — protocol-specific economic invariants, written by auditors.** Deliberately not automated. This is what an audit firm already produces, and it is the part a competing subnet cannot bootstrap without one.

A subnet that only had Tier 1 would be a nicer Slither. A subnet that had both is a market for the thing that actually causes large losses.

## 5. Mechanism attack surface

| Attack | Defense |
|---|---|
| Miner plants a contract alongside a prepared exploit | Miners cannot submit targets. Targets are curated from audit deal flow, our CTF corpus, and public vulnerability datasets. |
| Miner floods trivial or duplicate submissions | Novelty key = `(target_id, invariant_id, hash of the minimized state delta)`. Duplicates collapse to the first submission. |
| Miner resubmits a known public exploit | Same novelty key. Known exploits are seeded into the ledger before the target opens. |
| Validator collides or grades dishonestly | Scoring is execution. A dishonest result is immediately contradicted by every other validator running the same bytecode. |
| Miner games severity | Severity is attached to the invariant class at publication time, not assigned per submission. |
| Validator cost blows up | One forked-EVM execution per submission. Cheap enough that validators converge rather than sampling. |

## 6. What still has to be designed

Stated plainly rather than glossed:

- **Emission split and the miner reward curve.** Not fixed yet.
- **Target rotation cadence** — how long a target stays open before its invariant set is considered exhausted.
- **Tier-2 supply rate.** Auditor-written invariants are the scarce input; the subnet's ceiling is set by how fast we can produce them.
- **Cross-contract and economic-composition exploits**, which single-contract invariants do not express.

## 7. Component status

| Component | State | Location |
|---|---|---|
| Invariant retrieval from source | Working, measured | [`generator/src/retrieve.mjs`](../generator/src/retrieve.mjs) |
| LLM invariant generation | Implemented, not yet run | [`generator/src/generate_invariants.mjs`](../generator/src/generate_invariants.mjs) |
| Exploit / assert harness | Written, not yet executed | [`generator/test/InvariantCheck.t.sol`](../generator/test/InvariantCheck.t.sol) |
| Scoring rule | Implemented as a pure function | [`subnet/invariant_subnet/scoring.py`](../subnet/invariant_subnet/scoring.py) |
| Miner / validator neurons | Skeleton only | [`subnet/neurons/`](../subnet/neurons) |
| Network activity monitoring | Skeleton only | [`subnet/invariant_subnet/monitor.py`](../subnet/invariant_subnet/monitor.py) |
| Testnet deployment | Not started | — |

## 8. Path to mainnet

1. **Testnet subnet running the full loop** against a fixed corpus of known-vulnerable contracts, so the reward curve can be tuned against ground truth we already own.
2. **Mainnet** once miner behavior on testnet stops surprising us — within 60 to 90 days of a funded slot.

The ordering is deliberate. We would rather calibrate the reward signal against contracts whose bugs we already know than discover on mainnet that it was gameable.
