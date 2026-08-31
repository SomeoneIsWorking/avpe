#!/usr/bin/env python3
"""Inventory static IOP import tables in user-supplied PS2 IRX modules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from avpe.iop_imports import IopModule, scan_iop_module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+", help="IRX files or directories")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        paths = _expand_paths(args.paths)
        modules = [scan_iop_module(path.read_bytes()) for path in paths]
        result = _serialize(paths, modules)
        encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output is None:
            print(encoded, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded)
    except (OSError, ValueError, UnicodeError) as error:
        print(f"FATAL IOP module inventory failed: {error}", file=sys.stderr)
        return 1
    return 0


def _expand_paths(inputs: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for path in inputs:
        if path.is_dir():
            paths.extend(
                sorted(
                    candidate for candidate in path.rglob("*") if candidate.is_file()
                )
            )
        elif path.is_file():
            paths.append(path)
        else:
            raise ValueError(f"input path does not exist: {path}")
    if not paths:
        raise ValueError("input paths contain no files")
    return paths


def _serialize(paths: list[Path], modules: list[IopModule]) -> dict[str, object]:
    return {
        "schema": "avpe-iop-static-inventory-v1",
        "module_count": len(modules),
        "modules": [
            {
                "path": path.name,
                "name": module.name,
                "version": module.version,
                "entry_address": module.entry_address,
                "libraries": [
                    {
                        "name": library.name,
                        "version": library.version,
                        "address": library.address,
                        "imports": [
                            {
                                "ordinal": imported.ordinal,
                                "address": imported.address,
                                "symbol": imported.symbol,
                            }
                            for imported in library.imports
                        ],
                    }
                    for library in module.libraries
                ],
            }
            for path, module in zip(paths, modules)
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
