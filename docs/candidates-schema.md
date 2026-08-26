# Candidates JSON — the generator ↔ pipeline contract

Schema tag: `invver.candidates/1`

The Node generator ([`../generator`](../generator)) extracts candidate
invariants from a contract's source and writes them here; the Python pipeline
([`../pipeline`](../pipeline)) reads them, runs FP screening, and publishes the
survivors. The file is the seam — each half is tested against this shape, so
neither depends on the other's language.

## Producing it

```bash
cd generator
node src/generate_invariants.mjs src/SimpleBank.sol --emit-candidates --out out
# → CANDIDATES-EMITTED 5 → out/candidates.json
```

No API key. This is STEP1 (static retrieval), so the candidates are
reference-property **sketches** ranked by the signals found in the source, not
the concrete per-contract asserts STEP2 (LLM) produces. That distinction is
deliberate and visible in the field name: `solidity_sketch`, not
`solidity_assert`.

## Shape

```json
{
  "schema": "invver.candidates/1",
  "target": "src/SimpleBank.sol",
  "generated_by": "step1-retrieval",
  "note": "…sketches, not concrete asserts; stage 2 needs an API key",
  "signals": {
    "erc777_hook": true,
    "external_call_before_state_write": true,
    "no_reentrancy_guard": true,
    "per_account_cap": true,
    "value_transfer": true,
    "...": false
  },
  "cei_violations": [
    { "fn": "claim", "call": "token.transfer(...)", "write": "_mints += ..." }
  ],
  "candidates": [
    {
      "id": "reentrancy/NonReentrantLock",
      "category": "reentrancy",
      "score": 7,
      "matched": ["external_call_before_state_write(+3)", "erc777_hook(+2)", "..."],
      "solidity_sketch": "invariant reentrancyDepth() == 0 at function entry",
      "statement": "No externally reachable function may be reentered …"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `schema` | contract version; the pipeline rejects anything it does not recognize |
| `target` | source path the candidates were derived from |
| `signals` | static signals detected in the source (map of name → bool) |
| `cei_violations` | check-effect-interaction ordering violations located in the source |
| `candidates[].id` | reference-property id, e.g. `money_flow/PerAccountUpperBound` |
| `candidates[].category` | invariant class (reentrancy, money_flow, access_control, …) |
| `candidates[].score` | retrieval score (higher = more signals matched) |
| `candidates[].solidity_sketch` | the invariant sketch — becomes the pipeline's assertion |
| `candidates[].statement` | the human-readable property |

## Consuming it

```python
from invver_pipeline.bridge import load_candidates
from invver_pipeline import fp_screen

candidates = load_candidates("generator/out/candidates.json")
report = fp_screen.screen(candidates, benign_corpus, replayer)
report.kept_ids     # survivors -> manifest
```

`bridge.load_candidates` maps each `solidity_sketch` to a
`fp_screen.CandidateInvariant.solidity_assert`. `bridge.invoke_generator` runs
the generator live over a node subprocess and reads the same file; it raises
`GeneratorUnavailable` if node is absent rather than returning an empty set.

## The full flow

```text
pipeline: ingest contract  ─▶  generator: emit candidates (STEP1)
                                        │  candidates.json  (this contract)
                                        ▼
pipeline: bridge.load_candidates  ─▶  fp_screen.screen  ─▶  kept set + fp_screened
                                                              │
                                                              ▼  (STEP2 + forge, later)
                                                        concrete asserts, replayed
```
