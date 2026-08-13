# InvVer — Miner Task, Validator Task, and the Scoring Rule

A standalone description of what miners and validators actually do, with the
implemented scoring code inline. Nothing here requires reading the rest of the
repository.

Repository: `github.com/anam-145/invver-subnet` · Anam145 · MIT

---

## 1. The miner task

Each open target is a contract published together with a **set of
machine-checkable invariants** — safety conditions that must always hold, each
expressed as one executable Solidity `assert`.

> **Target** `SimpleBank` (DeFiVulnLabs, ERC777 reentrancy)
> `INV-1` critical — `assert(bank._mints(account) <= bank.maxMints());`
> `INV-2` high — `assert(token.balanceOf(account) <= bank.maxMints());`
> `impact_reference` 1000 tokens

**The miner's job is to find a transaction sequence that makes one of those
assertions fail.** That is the whole task statement.

How the search happens is the competitive surface, and we expect it to diverge:

- reinforcement learning over transaction sequences, using the invariant set as
  the reward signal — unusually, the reward here is already dense and
  deterministic;
- LLM-driven candidate generation seeded with the invariant statement, then
  concretized by a fuzzer;
- classical property fuzzing (Echidna, Medusa) with the published invariant
  compiled straight in as the property.

The subnet does not care which. The check is identical either way.

```python
# neurons/miner.py — skeleton
def search(target: Target) -> list[str]:
    """Find transaction sequences that break one of the target's invariants.

    TODO. This is the competitive surface of the subnet.
    Returns Solidity proof-of-concept sources.
    """
    raise NotImplementedError


def run() -> None:
    for target in fetch_open_targets():
        for poc in search(target):
            submit(target, poc)
```

Unimplemented functions raise rather than returning a plausible-looking value.
A skeleton that appears to work is worse than one that obviously does not.

---

## 2. The validator task

**The validator runs the assertion. That is all it does.**

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

No branching. No heuristic. No model call. No logic that decides whether
something *is* a vulnerability — that question was settled when the target's
invariant set was published.

The validator replays the miner's proof-of-concept with each published
invariant compiled in as an `assert`, and records which ones reverted with
`Panic(0x01)`. Those execution results, plus the measured state change, are the
only inputs to scoring.

```python
# neurons/validator.py — skeleton, but note how little belongs in here
def run_round(target_id: str, ledger: FindingLedger) -> dict[str, float]:
    target      = load_target(target_id)
    submissions = collect_submissions(target)
    results     = [execute(s, target) for s in submissions]   # the only I/O
    scored      = score_round(results, target, ledger)        # pure function
    weights     = normalize_weights(scored)                   # pure function
    set_weights(weights)
    return weights
```

Nothing between `execute` and `set_weights` is a judgment call.

**Consequence: two honest validators holding the same execution results produce
bit-identical weights.** A dishonest validator is not expressing a different
opinion — it is producing a result every other validator can immediately
contradict by running the same bytecode.

---

## 3. What the validator observes

The single input type to scoring. Everything is read off the post-state; none
of it is asserted by the miner.

```python
@dataclass(frozen=True)
class ExecutionResult:
    submission_id:        str
    target_id:            str
    miner_hotkey:         str
    broken_invariant_ids: tuple[str, ...]   # which asserts reverted
    call_count:           int               # length of the PoC
    state_delta_hash:     str               # hash of the minimized state diff
    impact:               float = 0.0       # magnitude of state change
    error:                Optional[str] = None
```

`state_delta_hash` is what makes two functionally identical exploits collapse
to one finding even when their source differs. `impact` is the measured
magnitude — net asset loss, tokens minted without authorization, value frozen —
in the unit the target published.

---

## 4. The scoring rule

Implemented as a pure function with **25 passing tests and zero dependencies**.

```
score = severity_weight × impact_factor × minimality_factor
```

with novelty as a gate: a duplicate finding scores zero regardless of the
factors above.

| Factor | Rule | Why it cannot be argued with |
|---|---|---|
| **Validity** | Did an invariant break? | An assert reverted or it did not. Nothing below this line scores at all |
| **Severity** | Attached to the invariant class, fixed when the target is published | Never assigned per submission, so never negotiated after the fact |
| **Novelty** | Key = `(target, invariant, hash of minimized state delta)` | Two miners who rediscover the same bug produce the same key; only the first is paid |
| **Known exploits** | Seeded into the ledger before the target opens | Replaying a public attack scores zero |
| **Impact** | Measured state change, log-scaled against a published reference | Read off the post-state by the harness, never claimed by the miner |
| **Minimality** | Call count, bounded both ways | An integer |
| **Ordering** | Submissions processed sorted by id | "Who was first" does not depend on arrival order |

### Impact ranking

Log-scaled, because the difference between draining 1% and 10% of a protocol
matters more than the difference between 90% and 99%.

```python
IMPACT_MIN_FACTOR = 0.2   # an invariant can break without moving value
IMPACT_DECADES    = 3.0   # three decades below reference reaches the floor

def impact_factor(impact: float, reference: float) -> float:
    if impact <= 0 or reference <= 0:
        return IMPACT_MIN_FACTOR if impact <= 0 else 1.0
    decades = math.log10(impact / reference)
    scaled  = 1.0 + decades / IMPACT_DECADES
    return max(IMPACT_MIN_FACTOR, min(1.0, scaled))
```

Draining the reference amount or more scores 1.0. Zero impact still scores at
the floor — an invariant can break without moving value, and that is still a
real finding, just not a headline one.

### The core function

```python
def score_submission(result, target, ledger) -> ScoredSubmission:
    if result.error is not None:
        return zero("execution failed: " + result.error)
    if not result.broken_invariant_ids:
        return zero("no invariant broke")

    novel, duplicate, best_weight = [], [], 0.0

    # sorted() so the result never depends on dict or set ordering
    for invariant_id in sorted(set(result.broken_invariant_ids)):
        invariant = target.invariant(invariant_id)   # unpublished ids are ignored
        key = NoveltyKey(result.target_id, invariant_id, result.state_delta_hash)

        if ledger.claim(key, result.miner_hotkey):
            novel.append(key)
            best_weight = max(best_weight, SEVERITY_WEIGHT[invariant.severity])
        else:
            duplicate.append(key)

    if not novel:
        return zero("already claimed")

    impact     = impact_factor(result.impact, target.impact_reference)
    minimality = minimality_factor(result.call_count)

    return ScoredSubmission(
        score = best_weight * impact * minimality,
        novel_findings     = tuple(novel),
        duplicate_findings = tuple(duplicate),
        reasons            = ...,   # every factor, so a miner can see why
    )
```

`reasons` exists so a miner can see exactly why they got what they got, without
anyone having to explain a judgment call.

### Round processing

```python
def score_round(results, target, ledger):
    # fixed order, so "who was first" does not depend on arrival order
    return [score_submission(r, target, ledger)
            for r in sorted(results, key=lambda r: r.submission_id)]

def normalize_weights(scored) -> dict[str, float]:
    totals = accumulate_per_miner(scored)
    grand  = sum(totals.values())
    return {} if grand <= 0 else {k: v / grand for k, v in sorted(totals.items())}
```

No clock, no randomness, no network, no model call anywhere in this path.

---

## 5. Mechanism attack surface

| Attack | Defense |
|---|---|
| Miner plants a contract alongside a prepared exploit | Miners cannot submit targets. Targets are curated from audit deal flow, our CTF corpus, and public vulnerability datasets |
| Miner floods trivial or duplicate submissions | Duplicates collapse under the novelty key to the first discoverer |
| Miner resubmits a known public exploit | Known exploits are seeded into the ledger before the target opens |
| Miner inflates the reported impact | Impact is read off the post-state by the harness, never taken from the submission |
| Miner games severity | Severity is attached to the invariant class at publication time |
| Validator collides or grades dishonestly | Scoring is execution. A dishonest result is contradicted by every validator running the same bytecode |
| Validator cost blows up | One forked-EVM execution per submission — cheap enough that validators converge rather than sample |

---

## 6. Monitoring the network

Because scoring is deterministic, honest validators must agree **exactly**. Any
divergence is a bug or a defector, never a difference of opinion — so it is the
first thing worth instrumenting.

```python
def validator_disagreement(weights_by_validator, tolerance=1e-9):
    """Validator pairs whose weight vectors differ. An honest pair differs by 0."""
    ...  # returns (validator_a, validator_b, max_abs_difference), largest first
```

`network_novelty_rate` trending toward zero does not mean miners got worse — it
means the target's invariant set is exhausted, and is the signal to rotate
targets.

---

## 7. Verify it yourself

No API key, no wallet, no network, no dependencies:

```bash
git clone https://github.com/anam-145/invver-subnet
cd invver-subnet/subnet
python -m unittest discover tests -v
```

```
Ran 25 tests in 0.002s
OK
```

The tests cover: severity ordering, unpublished invariants being ignored rather
than rewarded, novelty collapse across miners, seeded known exploits paying
nothing, impact bounds and ranking, minimality bounds, and — the property the
whole design rests on — that round outcomes do not change when submissions
arrive in a different order.

---

## 8. What is not implemented

Stated plainly, because a technical conversation will ask.

| Component | State |
|---|---|
| Scoring rule | **Implemented**, 25 tests |
| Invariant generation from source (no transaction history) | **Implemented and measured** |
| Trace2Inv reproduction — 23/27 exploits blocked at 3.99% FP, 20/27 at 0.28% | **Reproduced by us**, matching the authors' expected output |
| PoC / invariant harness | Written, **not yet executed** — no Foundry in the build environment |
| LLM invariant generation | Implemented, **not yet run** against a billed endpoint |
| Fork replay against live chain state | **Designed, not implemented** — the current harness deploys locally |
| Miner and validator neurons | **Skeletons** |
| Testnet subnet | **Not started** |

Nothing in this project reports a number we did not measure.
