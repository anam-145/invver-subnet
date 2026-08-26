# pipeline

Target ingestion: pull contracts from where audits and deployments live, screen
them so a public target cannot harm anyone, and mutate the survivors into fresh
targets that have no transaction history.

This is the plumbing behind the two design decisions in
[`../docs`](../docs): invariants are extracted automatically (not hand-written),
and targets are only ever contracts with nothing left to steal — so a validator
replaying an exploit has no reason to run it for real.

Stdlib only. Python 3.10+. No pip install.

---

## Where contracts come from

Three adapters, one interface (`sources/base.py`).

| Adapter | Pulls from | Needs | Enumerate? |
|---|---|---|---|
| **Sourcify** | verified source by chain + address | nothing (open) | no — give it an address |
| **Etherscan** | verified source by chain + address | `ETHERSCAN_API_KEY` | no |
| **LocalRepo** | a cloned audit-contest repo (Code4rena, Sherlock, Cantina) | the repo on disk | yes — walks it |

Sourcify and Etherscan return the source that was verified against the deployed
**bytecode**, so we get the code that actually runs on-chain, not a repo that
may have drifted. The repo adapter never touches the network — you `git clone`
the contest, it reads the directory. That keeps host trust, credentials, and
rate limits out of this code.

```bash
# one verified contract, no key
python -m invver_pipeline.ingest --source sourcify --chain 1 --address 0xABC...

# a whole audit contest you already cloned
python -m invver_pipeline.ingest --source repo --path ./2024-xx-project --mutate

# etherscan fallback for contracts Sourcify hasn't indexed
ETHERSCAN_API_KEY=... python -m invver_pipeline.ingest \
    --source etherscan --chain 1 --address 0xABC... --mutate
```

Output is written to `targets/` as one JSON per target — nothing is published.
The compile gate and a manifest author still sit between here and a live
challenge.

---

## The flow

```text
Source adapter          RawContract        pulled, not yet screened
     ↓ safety.screen()
Eligibility gate        eligible?           may this be a public target?
     ↓ mutate.to_targets()  (optional)
Mutation engine         TargetRecord[]      fresh targets, no history
     ↓
targets/*.json                              reviewed, then published
```

## Eligibility — why a validator never needs to exploit

`safety.screen()` decides whether a contract can be a public target. The rule:
a target must be one where running the exploit for real would harm no one.

| Check | Kind | Now |
|---|---|---|
| `has_source` | pure | ✅ runs |
| `is_real_target` (not an interface / library / mock) | pure | ✅ runs |
| `no_live_funds` | needs RPC balance | ◐ **unknown** until checked |
| `exploited_or_patched` | needs an exploit/patch feed | ◐ **unknown** |
| `no_live_clone` | needs a bytecode index | ◐ **unknown** |

> **"unknown" never counts as pass.** A live contract whose funds we have not
> checked is *not* eligible. To use one, the caller asserts the fact explicitly
> after checking by hand: `--assume no_live_funds,exploited_or_patched`. Safe
> default over convenient default — this is the enforcement point for the whole
> "no reason to exploit" posture.

Synthetic and repo contracts (`chain_id is None`) pass the external checks
automatically — they are not live deployments, so there is nothing to drain.

The three RPC/feed-dependent checks are the honest gaps. They raise no false
confidence: they report `unknown`, and the design fails closed.

## FP screening — the gate that stops a farmable invariant

`fp_screen.py` is the reason an automatically extracted invariant is safe to
publish. An extractor can produce a *wrong* invariant, and a wrong invariant is
free money: our Trace2Inv reproduction measured the oracle class firing on
**22.3%** of legitimate transactions. Publish that as-is and a miner never finds
a bug — they replay ordinary traffic, one in five trips the assertion, they get
paid. Miners take the cheapest valid path, so one high-FP invariant turns the
subnet into a machine that pays for normal trades.

The gate reuses Trace2Inv's own false-positive computation as a **filter**, not
a statistic:

```text
candidate invariant
  → replay the target's past benign transactions against it
  → fires on any (above threshold)? it is a false positive, not a safety
    property → reject before publication
  → survivors go into the manifest, marked fp_screened
```

```python
from invver_pipeline.fp_screen import BenignTx, CandidateInvariant, screen

report = screen(candidates, benign_corpus, replayer)   # replayer runs the EVM
report.kept_ids        # ('reentrancy/NonReentrantLock',)  -> publish these
report.rejected_ids    # ('oracle/PriceDeviationBound',)   -> dropped
report.fp_screened     # True iff a clean, non-empty set survived
```

| Property | Rule |
|---|---|
| Threshold | `DEFAULT_MAX_FP_RATE = 0.0` — any fire on benign traffic rejects (a published set is a conjunction of low-FP structural checks) |
| Fail closed | a corpus below `MIN_CORPUS` cannot clear an invariant — absence of traffic is not evidence of safety |
| Every candidate rejected | `fp_screened` is False — nothing to publish is not "screened-ready" |
| EVM step | behind a `Replayer` seam; `ForgeReplayer` is an explicit stub (needs forge) that raises rather than faking a pass |

See it block the oracle-farming attack:

```bash
python examples/fp_demo.py
#   KEEP   reentrancy/NonReentrantLock   held on all benign traffic
#   REJECT oracle/PriceDeviationBound    fired on 22/100 benign tx (22.0% > 0.0%)
#   FP-SCREEN-DEMO-OK
```

The benign corpus comes from the target's own pre-exploit history — which the
already-exploited and patched targets the pipeline admits already have on-chain,
so screening needs no invented traffic.

## Mutation — fresh targets without an answer key

`mutate.py` perturbs a screened contract. A mutation changes *how* the contract
behaves, not *what it must guarantee* — the invariant set comes from the
original (via Trace2Inv) and the mutant inherits it. Whether a given mutant is
actually exploitable is unknown to us **and to the generator**, which is exactly
why it does not become an answer key (the ReinforcedAI failure mode).

Heuristic, textual, deterministic — the same spirit as the lexical retriever in
[`../generator`](../generator):

| Operator | Change |
|---|---|
| `swap_cei` | move a state write below the next external call (reintroduce a CEI violation) |
| `remove_require` | delete one guard, one mutant per `require` |
| `flip_boundary` | `<=` → `<`, `>=` → `>` (off-by-one) |
| `drop_nonreentrant` | strip a `nonReentrant` modifier |

A textual mutation can produce code that does not compile. `mutate.compiles()`
is the gate that filters those before publishing — it needs `solc` and is a
clear stub in this environment (`NotImplementedError`), so the publish step runs
it where solc exists. Mutant records carry `compile_checked: false` until it
passes.

---

## Run the tests

```bash
cd pipeline
python -m unittest discover tests -v
```

```
Ran 18 tests in 0.05s
OK
```

Network adapters are tested offline against fixtures (each adapter's
`http_get` is monkeypatched); the repo adapter, safety gates, and mutators run
directly.

## What is not built yet

| Item | Blocked on |
|---|---|
| `no_live_funds` / `exploited_or_patched` / `no_live_clone` | RPC, an exploit feed, a bytecode-clone index |
| `mutate.compiles()` | a `solc` install |
| Multi-file mutation (mutants use the primary file only) | flattening or per-file handling |
| Invariant extraction on the pulled contract | that is `../generator` — this pipeline feeds it |

Nothing here reports a check as passed when it was only skipped.

---

## Layout

```
invver_pipeline/
  model.py            RawContract, EligibilityResult, TargetRecord
  sources/
    base.py           Source ABC + injectable http_get
    sourcify.py       verified source, no key
    etherscan.py      verified source, api key; handles all 3 SourceCode shapes
    local_repo.py     walk a cloned audit repo, skip tests/mocks/libs
  safety.py           eligibility gates (fails closed on unknown)
  mutate.py           mutation operators + compile gate (stub)
  fp_screen.py        false-positive screening; ForgeReplayer is a stub
  bridge.py           reads the generator's candidates JSON; live node adapter
  ingest.py           orchestrator + CLI
examples/
  fp_demo.py          the oracle-farming scenario, blocked
  e2e_demo.py         generator candidates → FP screening, end to end
tests/
  test_pipeline.py
  test_fp_screen.py
  test_bridge.py
  fixtures/           committed candidates.json from a real generator run
```

## The generator seam

The Node generator ([`../generator`](../generator)) emits candidate invariants
for a contract as `invver.candidates/1` JSON; `bridge.py` reads them into the
pipeline and FP screening filters them. The file is the interface — documented
in [`../docs/candidates-schema.md`](../docs/candidates-schema.md) — so the
Python side is tested against a committed fixture, and `bridge.invoke_generator`
runs the generator live over a node subprocess when you want the real thing.

```bash
python examples/e2e_demo.py
#   loaded 5 candidate invariants from the generator …
#   KEEP   reentrancy/NonReentrantLock …
#   REJECT oracle/PriceDeviationBound   fired on 22/100 benign tx (22.0% > 0.0%)
#   E2E-DEMO-OK
```
