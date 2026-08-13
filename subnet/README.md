# subnet

Miner, validator, and network monitoring.

---

## Status

| Module | State | Notes |
|---|---|---|
| `invariant_subnet/protocol.py` | ✅ Implemented | Wire types. All frozen, because scoring has to be a pure function of them |
| `invariant_subnet/scoring.py` | ✅ Implemented · 18 tests passing | **The scoring rule.** This is where the project's central claim lives |
| `invariant_subnet/monitor.py` | ◐ Partial | Local aggregation works. Chain queries raise `NotImplementedError` |
| `neurons/validator.py` | ⬜ Skeleton | Loop shape only; every unimplemented step raises |
| `neurons/miner.py` | ⬜ Skeleton | Same |

**Unimplemented functions raise rather than returning a plausible-looking value.** A skeleton that appears to work is worse than one that obviously does not.

## Run

No dependencies. Python 3.10+.

```bash
cd subnet
python -m unittest discover tests -v
```

```
Ran 18 tests in 0.002s
OK
```

---

## What the scoring rule guarantees

`scoring.py` is a **pure function**. No clock, no randomness, no network, no model call. Two validators holding the same `ExecutionResult` values and the same ledger produce **the same number**.

| Factor | Rule |
|---|---|
| **Severity** | Attached to the invariant class and fixed when the target is published — never assigned per submission |
| **Novelty** | Key is `(target_id, invariant_id, hash of the minimized state delta)`. Rediscovering the same bug yields the same key, so only the first miner is paid |
| **Known exploits** | Seeded into the ledger before the target opens. Replaying a public attack scores zero |
| **Minimality** | Call count, bounded above and below. Shorter scores slightly higher. An integer, so it cannot be argued with |
| **Processing order** | Sorted by submission id, so "who was first" does not depend on the order a validator happened to receive things in |

If a validator produces a different result, that is **not a difference of opinion — it is a bug or a defector.** That property is why `monitor.validator_disagreement()` exists.

## Monitoring

```python
from invariant_subnet.monitor import summarize_round, render_report, validator_disagreement

report = summarize_round("simplebank", scored_submissions)
print(render_report(report))

# Scoring is deterministic, so an honest pair of validators must differ by exactly 0
for a, b, delta in validator_disagreement(weights_by_validator):
    print(f"DIVERGENCE {a} vs {b}: {delta:.6f}")
```

When `network_novelty_rate` trends toward zero, miners did not get worse — **the target's invariant set is exhausted.** Use it as the signal to rotate targets.

---

## Layout

```
invariant_subnet/
  protocol.py    Invariant, Target, Submission, ExecutionResult, NoveltyKey
  scoring.py     the scoring rule and the finding ledger
  monitor.py     round aggregation and validator-agreement checking
neurons/
  miner.py       skeleton — search is the competitive surface
  validator.py   skeleton — execute, score, set weights
tests/
  test_scoring.py
```

## Next

1. **`execute()`** — shell out to `forge test` to produce real execution results. The harness already exists: [`../generator/test/InvariantCheck.t.sol`](../generator/test/InvariantCheck.t.sol)
2. **`search()`** — miner-side exploit search. RL over transaction sequences, LLM candidate generation, or Echidna/Medusa property fuzzing.
3. **Chain integration** — `bittensor` SDK, netuid registration, metagraph queries.
4. **Testnet** — run the full loop against a fixed corpus of known-vulnerable contracts.

Design background: [`../docs/architecture.md`](../docs/architecture.md)
