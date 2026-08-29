#!/usr/bin/env python3
"""Inventory direct EE BIOS syscall use in a user-supplied ELF32 MIPS file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

from avpe.ee_syscalls import EeSyscallInventory, SyscallSite, scan_ee_syscalls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = _serialize(scan_ee_syscalls(args.elf.read_bytes()))
        encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output is None:
            print(encoded, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded)
    except (OSError, ValueError, struct.error) as error:
        print(f"FATAL EE syscall inventory failed: {error}", file=sys.stderr)
        return 1
    return 0


def _serialize(inventory: EeSyscallInventory) -> dict[str, object]:
    wrapper_calls = [_site_to_dict(site) for site in inventory.wrapper_calls]
    direct_syscalls = [_site_to_dict(site) for site in inventory.direct_syscalls]
    candidates = sorted(
        {
            site.call_number
            for site in (*inventory.wrapper_calls, *inventory.direct_syscalls)
            if site.call_number is not None
        }
    )
    return {
        "schema": "avpe-ee-syscall-static-inventory-v1",
        "executable_segments": [
            {
                "file_offset": segment.file_offset,
                "virtual_address": segment.virtual_address,
                "file_size": segment.file_size,
                "flags": segment.flags,
            }
            for segment in inventory.executable_segments
        ],
        "wrappers": [
            {"address": wrapper.address, "call_number": wrapper.call_number}
            for wrapper in inventory.wrappers
        ],
        "wrapper_calls": wrapper_calls,
        "direct_syscalls": direct_syscalls,
        "candidate_call_numbers": candidates,
    }


def _site_to_dict(site: SyscallSite) -> dict[str, int | None]:
    return {
        "address": site.address,
        "call_number": site.call_number,
        "wrapper_address": site.wrapper_address,
    }

if __name__ == "__main__":
    raise SystemExit(main())
