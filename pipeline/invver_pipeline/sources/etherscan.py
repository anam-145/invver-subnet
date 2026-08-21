"""Etherscan adapter — verified source by address, needs an API key.

Etherscan covers contracts Sourcify has not indexed, so it is the fallback. The
awkward part is the `SourceCode` field, which arrives in three shapes depending
on how the contract was verified:

  1. plain flattened Solidity;
  2. a JSON map  {"path": {"content": "..."}}  (older multi-file);
  3. a standard-json-input wrapped in an extra pair of braces
     {{ "language": "Solidity", "sources": {"path": {"content": "..."}}, ... }}

`_parse_source_code` handles all three. Etherscan v2 uses one host with a
`chainid` query parameter for every chain.
"""

from __future__ import annotations

import json

from ..model import RawContract, SourceFile
from .base import Source, SourceError, http_get

V2_ENDPOINT = "https://api.etherscan.io/v2/api"


class Etherscan(Source):
    name = "etherscan"

    def __init__(self, api_key: str, endpoint: str = V2_ENDPOINT):
        if not api_key:
            raise SourceError("etherscan adapter requires an API key")
        self.api_key = api_key
        self.endpoint = endpoint

    def fetch(self, identifier: str, chain_id: int | None = None) -> RawContract:
        chain = chain_id or 1
        url = (
            f"{self.endpoint}?chainid={chain}&module=contract"
            f"&action=getsourcecode&address={identifier}&apikey={self.api_key}"
        )
        payload = json.loads(http_get(url))
        if payload.get("status") != "1" or not payload.get("result"):
            raise SourceError(
                f"etherscan: {payload.get('message')} / {payload.get('result')}"
            )
        entry = payload["result"][0]
        source_code = entry.get("SourceCode", "")
        if not source_code.strip():
            raise SourceError(f"{identifier} is not verified on chain {chain}")

        files = _parse_source_code(source_code, entry.get("ContractName", "Contract"))
        return RawContract(
            source=self.name,
            identifier=identifier,
            name=entry.get("ContractName") or _first_contract(files),
            chain_id=chain,
            files=files,
            metadata={
                "compiler": entry.get("CompilerVersion", ""),
                "optimization": entry.get("OptimizationUsed", ""),
                "runs": entry.get("Runs", ""),
                "license": entry.get("LicenseType", ""),
            },
        )


def _parse_source_code(source_code: str, fallback_name: str) -> tuple[SourceFile, ...]:
    text = source_code.strip()

    # Shape 3: standard-json-input wrapped in an extra brace pair.
    if text.startswith("{{") and text.endswith("}}"):
        inner = json.loads(text[1:-1])
        sources = inner.get("sources", {})
        return tuple(
            SourceFile(path=path, content=body.get("content", ""))
            for path, body in sources.items()
        )

    # Shape 2: a bare JSON map of path -> {content}.
    if text.startswith("{"):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict) and obj:
            # Either {"sources": {...}} or {path: {content}} directly.
            sources = obj.get("sources", obj)
            files = []
            for path, body in sources.items():
                if isinstance(body, dict) and "content" in body:
                    files.append(SourceFile(path=path, content=body["content"]))
            if files:
                return tuple(files)

    # Shape 1: plain flattened Solidity.
    return (SourceFile(path=f"{fallback_name}.sol", content=source_code),)


def _first_contract(files: tuple[SourceFile, ...]) -> str:
    import re

    for f in files:
        m = re.search(r"\bcontract\s+(\w+)", f.content)
        if m:
            return m.group(1)
    return "Contract"
