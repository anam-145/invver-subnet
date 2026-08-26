"""The seam between the Node generator and the Python pipeline.

The generator (../generator) extracts candidate invariants from a contract's
source and writes them as a JSON contract — schema `invver.candidates/1`, see
docs/candidates-schema.md. This module reads that file into the pipeline's
`CandidateInvariant` type, so the two halves meet at a documented file rather
than at a language boundary.

Two ways in:

  load_candidates(path)      read a candidates.json the generator already wrote
  invoke_generator(sol, ...) run the generator now (needs node) and read the
                             result — a thin adapter over the same file

`load_candidates` is pure and is the tested path. `invoke_generator` shells out;
if node is absent it raises `GeneratorUnavailable` rather than returning an empty
set, so a missing toolchain can never look like "this contract has no invariants".
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .fp_screen import CandidateInvariant

SCHEMA = "invver.candidates/1"


class BridgeError(RuntimeError):
    pass


class GeneratorUnavailable(BridgeError):
    pass


def parse_candidates(doc: dict) -> tuple[CandidateInvariant, ...]:
    """Turn a parsed candidates document into CandidateInvariant objects.

    Each candidate's `solidity_sketch` becomes the invariant's assertion. These
    are reference-property sketches, not concrete per-contract asserts (that is
    the generator's stage 2, which needs an API key) — the field name in the
    contract says `sketch` for exactly that reason.
    """
    if doc.get("schema") != SCHEMA:
        raise BridgeError(
            f"unexpected schema {doc.get('schema')!r}, expected {SCHEMA!r}"
        )
    candidates = doc.get("candidates")
    if not isinstance(candidates, list):
        raise BridgeError("candidates document has no `candidates` array")

    out = []
    for i, c in enumerate(candidates):
        missing = [k for k in ("id", "category", "solidity_sketch") if k not in c]
        if missing:
            raise BridgeError(f"candidate {i} missing {missing}")
        out.append(CandidateInvariant(
            id=c["id"],
            category=c["category"],
            solidity_assert=c["solidity_sketch"],
        ))
    return tuple(out)


def load_candidates(path: str | Path) -> tuple[CandidateInvariant, ...]:
    """Read a candidates.json the generator wrote."""
    p = Path(path)
    if not p.is_file():
        raise BridgeError(f"{p} not found")
    return parse_candidates(json.loads(p.read_text(encoding="utf-8")))


def invoke_generator(
    sol_path: str | Path,
    generator_dir: str | Path,
    out_dir: str | Path,
    node: str = "node",
    timeout: float = 60.0,
) -> tuple[CandidateInvariant, ...]:
    """Run the generator's emit-candidates step now and read the result.

    `sol_path` is relative to `generator_dir` (the generator resolves targets
    against its own cwd). Raises GeneratorUnavailable if node is not on PATH, and
    BridgeError if the generator fails or writes nothing — never a silent empty.
    """
    gen_dir = Path(generator_dir)
    if shutil.which(node) is None:
        raise GeneratorUnavailable(
            f"{node!r} not found on PATH; install Node or use load_candidates() "
            f"with a pre-generated candidates.json"
        )
    cmd = [
        node, "src/generate_invariants.mjs", str(sol_path),
        "--emit-candidates", "--out", str(out_dir),
    ]
    # Force UTF-8 decoding: the generator prints box-drawing and arrow glyphs,
    # and Windows would otherwise decode the child's stdout with the locale
    # codec (e.g. cp949) and crash the reader thread.
    proc = subprocess.run(
        cmd, cwd=str(gen_dir), capture_output=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if proc.returncode != 0 or "CANDIDATES-EMITTED" not in proc.stdout:
        raise BridgeError(
            f"generator failed (exit {proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
        )
    written = gen_dir / out_dir / "candidates.json"
    return load_candidates(written)
