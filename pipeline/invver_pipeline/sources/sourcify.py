"""Sourcify adapter — verified source by chain + address, no API key.

Sourcify is the path of least resistance: open, free, and it returns the exact
source files that were verified against the deployed bytecode. That last part
matters — we want the code that actually runs on-chain, not a repo that may have
drifted from the deployment.

  GET https://sourcify.dev/server/files/any/{chainId}/{address}
  → {"status": "full|partial", "files": [{"name","path","content"}, ...]}

`full` means the bytecode matched exactly (including metadata hash); `partial`
means it matched modulo metadata. We keep both but record which in metadata.
"""

from __future__ import annotations

import json

from ..model import RawContract, SourceFile
from .base import Source, SourceError, http_get

DEFAULT_SERVER = "https://sourcify.dev/server"


class Sourcify(Source):
    name = "sourcify"

    def __init__(self, server: str = DEFAULT_SERVER):
        self.server = server.rstrip("/")

    def fetch(self, identifier: str, chain_id: int | None = None) -> RawContract:
        if chain_id is None:
            raise SourceError("sourcify.fetch requires chain_id")
        address = identifier
        url = f"{self.server}/files/any/{chain_id}/{address}"
        payload = json.loads(http_get(url))

        raw_files = payload.get("files", [])
        if not raw_files:
            raise SourceError(f"no verified source for {address} on chain {chain_id}")

        files = tuple(
            SourceFile(path=f.get("path") or f.get("name", "unknown.sol"),
                       content=f.get("content", ""))
            for f in raw_files
            if f.get("name", "").endswith(".sol")
        )
        if not files:
            raise SourceError(f"verified entry for {address} has no .sol files")

        return RawContract(
            source=self.name,
            identifier=address,
            name=_infer_name(files),
            chain_id=chain_id,
            files=files,
            metadata={
                "match": payload.get("status", "unknown"),
                "server": self.server,
            },
        )


def _infer_name(files: tuple[SourceFile, ...]) -> str:
    """Best-effort primary-contract name from the largest file's first
    `contract X` declaration. Only a label; the manifest author confirms it."""
    import re

    biggest = max(files, key=lambda f: len(f.content))
    m = re.search(r"\bcontract\s+(\w+)", biggest.content)
    if m:
        return m.group(1)
    return biggest.path.rsplit("/", 1)[-1].removesuffix(".sol")
