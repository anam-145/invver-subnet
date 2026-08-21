"""Audit-repo adapter — read contracts from a cloned audit-contest repository.

Code4rena, Sherlock, and Cantina publish each contest's in-scope contracts as a
public git repository. The workflow is:

    git clone https://github.com/code-423n4/2024-xx-project
    python -m invver_pipeline.ingest --source repo --path ./2024-xx-project

so this adapter never fetches over the network itself — it walks a directory
that git already put on disk. That keeps credentials, rate limits, and the
question of which host we trust out of this module.

`discover()` enumerates every contract-bearing .sol under the repo, skipping the
usual non-target directories (tests, mocks, node_modules, libraries).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ..model import RawContract, SourceFile
from .base import Source, SourceError

SKIP_DIRS = {
    "node_modules", "lib", "test", "tests", "mock", "mocks",
    "script", "scripts", ".git", "out", "cache", "artifacts",
}
# Files that are not themselves audit targets even when they contain `contract`.
SKIP_NAME_HINTS = ("mock", "test", "harness", "interface")


class LocalRepo(Source):
    def __init__(self, root: str | Path, label: str = "repo"):
        self.root = Path(root)
        if not self.root.is_dir():
            raise SourceError(f"{self.root} is not a directory")
        self.name = f"local:{label}"

    def fetch(self, identifier: str, chain_id: int | None = None) -> RawContract:
        """`identifier` is a repo-relative path to a .sol file."""
        path = self.root / identifier
        if not path.is_file():
            raise SourceError(f"{path} not found")
        return self._to_contract(path)

    def discover(self) -> Iterator[RawContract]:
        for path in sorted(self.root.rglob("*.sol")):
            rel_parts = {p.lower() for p in path.relative_to(self.root).parts[:-1]}
            if rel_parts & SKIP_DIRS:
                continue
            content = _read(path)
            if not _defines_contract(content):
                continue
            yield self._to_contract(path)

    def _to_contract(self, path: Path) -> RawContract:
        content = _read(path)
        rel = str(path.relative_to(self.root)).replace("\\", "/")
        name = _first_contract(content) or path.stem
        return RawContract(
            source=self.name,
            identifier=rel,
            name=name,
            chain_id=None,
            files=(SourceFile(path=rel, content=content),),
            metadata={
                "looks_like_support": any(h in path.name.lower() for h in SKIP_NAME_HINTS),
            },
        )


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _defines_contract(text: str) -> bool:
    return re.search(r"\bcontract\s+\w+", text) is not None


def _first_contract(text: str) -> str | None:
    m = re.search(r"\bcontract\s+(\w+)", text)
    return m.group(1) if m else None
