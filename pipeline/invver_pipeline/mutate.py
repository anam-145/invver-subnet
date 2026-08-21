"""Mutation engine — turn a screened contract into fresh targets with no
transaction history.

Why this is safe to do without knowing the answer: a mutation changes *how* a
contract does something, not *what it must guarantee*. The invariant set comes
from the original (via Trace2Inv), and the mutant inherits it. Whether a given
mutation is actually exploitable is unknown to us and to the generator — which
is exactly why it does not become an answer key (the ReinforcedAI failure mode).

These are **heuristic, textual** mutators, in the same spirit as the lexical
retriever in ../../generator. They are deterministic and dependency-free, and
each returns at most one mutant per applicable site. A textual mutation can
produce code that does not compile; that is caught downstream by a compile gate
(needs solc — see `compiles()` below, currently a stub) before a mutant is ever
published.

Each mutator is a function (source) -> list[(description, mutated_source)].
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .model import RawContract, TargetRecord


@dataclass(frozen=True)
class Mutant:
    operator: str
    description: str
    source: str


# ── mutators ─────────────────────────────────────────────────────────────────


def _swap_cei(src: str) -> list[tuple[str, str]]:
    """Move a state write to *after* the next external call in the same block,
    reintroducing a check-effect-interaction violation.

    Matches the pattern  <stateVar> ... = ...;  immediately followed by an
    external call, and swaps the two lines.
    """
    out = []
    lines = src.split("\n")
    call_re = re.compile(r"\.\s*(transfer|send|call|safeTransfer|safeTransferFrom)\s*[({]")
    write_re = re.compile(r"^\s*\w+\s*(\[[^\]]*\])?\s*(\+=|-=|=)(?!=)")
    for i in range(len(lines) - 1):
        if write_re.search(lines[i]) and call_re.search(lines[i + 1]):
            swapped = lines[:]
            swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
            out.append((
                f"moved state write below external call at line {i + 1}",
                "\n".join(swapped),
            ))
    return out


def _remove_require(src: str) -> list[tuple[str, str]]:
    """Delete a single `require(...)` guard, one mutant per require."""
    out = []
    for m in re.finditer(r"^[ \t]*require\s*\([^;]*\);[ \t]*$", src, re.MULTILINE):
        mutated = src[: m.start()] + src[m.end():]
        snippet = m.group(0).strip()[:60]
        out.append((f"removed guard: {snippet}", mutated))
    return out


def _flip_boundary(src: str) -> list[tuple[str, str]]:
    """Flip an inclusive/exclusive comparison in a require/if: <= to <, >= to >.
    Off-by-one boundary bugs."""
    out = []
    for m in re.finditer(r"(<=|>=)", src):
        op = m.group(1)
        new = "<" if op == "<=" else ">"
        mutated = src[: m.start()] + new + src[m.end():]
        out.append((f"tightened boundary {op} -> {new} at offset {m.start()}", mutated))
    return out


def _drop_nonreentrant(src: str) -> list[tuple[str, str]]:
    """Remove a `nonReentrant` modifier from a function signature."""
    out = []
    for m in re.finditer(r"\bnonReentrant\b\s*", src):
        mutated = src[: m.start()] + src[m.end():]
        out.append(("removed nonReentrant modifier", mutated))
    return out


MUTATORS: dict[str, Callable[[str], list[tuple[str, str]]]] = {
    "swap_cei": _swap_cei,
    "remove_require": _remove_require,
    "flip_boundary": _flip_boundary,
    "drop_nonreentrant": _drop_nonreentrant,
}


def mutants_for(source: str, operators: list[str] | None = None) -> list[Mutant]:
    """All mutants of one Solidity source, deterministic order."""
    ops = operators or list(MUTATORS)
    found: list[Mutant] = []
    for op in ops:
        for desc, mutated in MUTATORS[op](source):
            if mutated != source:
                found.append(Mutant(operator=op, description=desc, source=mutated))
    return found


def compiles(source: str) -> bool:
    """Compile gate. A textual mutant may be invalid Solidity; only compiling
    mutants may be published.

    TODO: shell out to `solc --standard-json` (or forge build) and return
    success. Not implemented in this environment — no solc — so callers must
    run this before publishing rather than trusting the mutant blindly.
    """
    raise NotImplementedError("compile gate requires solc; run before publishing")


def to_targets(contract: RawContract, operators: list[str] | None = None) -> list[TargetRecord]:
    """Produce TargetRecords for every mutant of a contract's primary file.

    Does not call `compiles()` — that gate belongs in the publish step, where a
    solc install exists, so this stays pure and testable.
    """
    primary = contract.primary_file
    if primary is None:
        return []
    records = []
    for i, mut in enumerate(mutants_for(primary.content, operators)):
        records.append(TargetRecord(
            target_id=f"{contract.id}-m{i:03d}",
            name=f"{contract.name}__{mut.operator}",
            origin=contract,
            solidity=mut.source,
            kind="mutant",
            provenance={
                "operator": mut.operator,
                "change": mut.description,
                "origin_source": contract.source,
                "origin_identifier": contract.identifier,
                "compile_checked": False,  # set True only after compiles() passes
            },
        ))
    return records
