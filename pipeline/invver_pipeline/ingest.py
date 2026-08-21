"""Orchestrator + CLI: source -> screen -> (mutate) -> target records on disk.

    # pull one verified contract, screen it, do not mutate
    python -m invver_pipeline.ingest --source sourcify --chain 1 --address 0xABC...

    # walk a cloned audit repo, screen everything, emit mutants of what passes
    python -m invver_pipeline.ingest --source repo --path ./2024-xx-project --mutate

    # etherscan needs a key
    ETHERSCAN_API_KEY=... python -m invver_pipeline.ingest \
        --source etherscan --chain 1 --address 0xABC... --mutate

Screened-out contracts are reported, never silently dropped. Nothing is
published — output is written to ./targets/ for a human (or the publish step) to
review, because the compile gate and the manifest author still sit between here
and a live challenge.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path

from . import mutate, safety
from .model import RawContract, TargetRecord
from .sources import Etherscan, LocalRepo, Sourcify, SourceError


def _collect(args) -> list[RawContract]:
    if args.source == "sourcify":
        _require(args.address and args.chain, "sourcify needs --address and --chain")
        return [Sourcify().fetch(args.address, args.chain)]
    if args.source == "etherscan":
        key = os.environ.get("ETHERSCAN_API_KEY", "")
        _require(key, "set ETHERSCAN_API_KEY")
        _require(args.address and args.chain, "etherscan needs --address and --chain")
        return [Etherscan(key).fetch(args.address, args.chain)]
    if args.source == "repo":
        _require(args.path, "repo needs --path")
        return list(LocalRepo(args.path, label=Path(args.path).name).discover())
    raise SystemExit(f"unknown source {args.source!r}")


def _require(cond, msg: str) -> None:
    if not cond:
        raise SystemExit(f"error: {msg}")


def _record_to_dict(rec: TargetRecord) -> dict:
    d = dataclasses.asdict(rec)
    # RawContract is bulky; keep a pointer, not the whole file set.
    d["origin"] = {
        "source": rec.origin.source,
        "identifier": rec.origin.identifier,
        "chain_id": rec.origin.chain_id,
        "name": rec.origin.name,
    }
    return d


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="invver_pipeline.ingest")
    p.add_argument("--source", required=True, choices=["sourcify", "etherscan", "repo"])
    p.add_argument("--chain", type=int, default=None)
    p.add_argument("--address", default=None)
    p.add_argument("--path", default=None)
    p.add_argument("--mutate", action="store_true", help="emit mutants of eligible contracts")
    p.add_argument("--operators", default=None,
                   help="comma-separated mutator names (default: all)")
    p.add_argument("--assume", default="",
                   help="comma-separated external checks you have verified by "
                        "hand, e.g. no_live_funds,exploited_or_patched")
    p.add_argument("--out", default="targets")
    args = p.parse_args(argv)

    try:
        contracts = _collect(args)
    except SourceError as e:
        print(f"source error: {e}", file=sys.stderr)
        return 2

    assume = {s for s in args.assume.split(",") if s}
    operators = args.operators.split(",") if args.operators else None
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    eligible = 0
    written = 0
    print(f"pulled {len(contracts)} contract(s) from {args.source}\n")

    for c in contracts:
        result = safety.screen(c, assume=assume)
        mark = "ELIGIBLE" if result.eligible else "rejected"
        print(f"[{mark}] {c.name}  ({c.source}:{c.identifier})")
        for check, status in result.checks.items():
            print(f"      {status:<16} {check}")
        for reason in result.reasons:
            print(f"      → {reason}")

        if not result.eligible:
            continue
        eligible += 1

        records: list[TargetRecord] = []
        if args.mutate:
            records = mutate.to_targets(c, operators)
            print(f"      generated {len(records)} mutant target(s) "
                  f"(compile-check pending before publish)")
        else:
            primary = c.primary_file
            if primary:
                records = [TargetRecord(
                    target_id=c.id, name=c.name, origin=c,
                    solidity=primary.content, kind="as_is",
                    provenance={"source": c.source, "identifier": c.identifier},
                )]

        for rec in records:
            (out_dir / f"{rec.target_id}.json").write_text(
                json.dumps(_record_to_dict(rec), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            written += 1
        print()

    print(f"summary: {eligible}/{len(contracts)} eligible, {written} target file(s) "
          f"written to {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
