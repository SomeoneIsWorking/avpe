#!/usr/bin/env python3
"""Compare ignored AVPE ISO-oracle and native-delivery byte traces."""

import argparse
import copy
import json
import sys
from pathlib import Path

from avpe.asset_byte_compare import REQUIRED_FILES, compare_asset_byte_traces


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRACE_DIR = ROOT / "scratch" / "control-test"


def load_trace(path: Path) -> object:
    try:
        return json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"could not read byte trace {path}: {error}") from error


def force_digest_mismatch(trace: object) -> tuple[object, str, int, int]:
    changed = copy.deepcopy(trace)
    if not isinstance(changed, dict) or not isinstance(changed.get("files"), list):
        raise RuntimeError("native trace has no files array for the negative control")
    for file in changed["files"]:
        if not isinstance(file, dict) or file.get("path") not in REQUIRED_FILES:
            continue
        chunks = file.get("chunks")
        if not isinstance(chunks, list) or not chunks or not isinstance(chunks[0], dict):
            continue
        chunk = chunks[0]
        digest = chunk.get("sha256")
        offset = chunk.get("offset")
        size = chunk.get("size")
        if not isinstance(digest, str) or len(digest) != 64 \
                or not isinstance(offset, int) or not isinstance(size, int):
            continue
        chunk["sha256"] = ("0" if digest[0] != "0" else "1") + digest[1:]
        return changed, file["path"], offset, size
    raise RuntimeError("native trace has no required chunk for the negative control")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--oracle",
        type=Path,
        default=DEFAULT_TRACE_DIR / "asset-byte-trace-oracle.json",
    )
    parser.add_argument(
        "--native",
        type=Path,
        default=DEFAULT_TRACE_DIR / "asset-byte-trace-native.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_TRACE_DIR / "asset-byte-comparison.json",
    )
    args = parser.parse_args()

    try:
        oracle = load_trace(args.oracle)
        native = load_trace(args.native)
        comparison = compare_asset_byte_traces(oracle, native)
        changed, path, offset, size = force_digest_mismatch(native)
        negative = compare_asset_byte_traces(oracle, changed)
    except (RuntimeError, ValueError) as error:
        print(f"FATAL asset byte comparison: {error}", file=sys.stderr)
        return 2

    expected_mismatch = any(
        error.get("code") == "chunk_digest_mismatch"
        and error.get("path") == path
        and error.get("offset") == offset
        and error.get("size") == size
        for error in negative["errors"]
    )
    report = {
        "comparison": comparison,
        "negative_control": {
            "verified_rejection": negative["verified"] is False and expected_mismatch,
            "changed_path": path,
            "changed_offset": offset,
            "changed_size": size,
            "result": negative,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    if not comparison["verified"] or not report["negative_control"]["verified_rejection"]:
        print(f"FATAL asset byte comparison rejected; see {args.output}", file=sys.stderr)
        return 1
    matched = sum(file["matched_chunks"] for file in comparison["files"])
    print(
        f"asset byte comparison verified {matched} chunks; "
        f"negative control rejected {path}@{offset}+{size}; output={args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
