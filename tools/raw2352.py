#!/usr/bin/env python3
"""Strip a MODE2/2352 raw CD image down to a 2048-byte-sector ISO.

Verifies EVERY sector's sync pattern and reports the mix of sector kinds;
a silent skip is a failure, so mismatches abort loudly with the sector index.
"""

import argparse
import sys

SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
RAW = 2352
USER = 2048


def strip(raw_path: str, iso_path: str) -> int:
    data = open(raw_path, "rb").read()
    if len(data) % RAW != 0:
        print(f"FATAL size {len(data)} not a multiple of {RAW}", file=sys.stderr)
        return 1
    sectors = len(data) // RAW
    kinds: dict[str, int] = {}
    out = bytearray()
    for i in range(sectors):
        s = data[i * RAW:(i + 1) * RAW]
        if s[:12] != SYNC:
            print(f"FATAL sector {i}: bad sync prefix {s[:12].hex()} — refusing to guess",
                  file=sys.stderr)
            return 1
        mode = s[15]
        if mode == 1:          # Mode1: 16-byte header then 2048 user bytes
            kinds["mode1"] = kinds.get("mode1", 0) + 1
            out += s[16:16 + USER]
        elif mode == 2:        # Mode2 XA Form1/2: 24-byte header+subheader
            form = 2 if s[18] & 0x20 else 1
            key = f"mode2_form{form}"
            kinds[key] = kinds.get(key, 0) + 1
            if form == 1:
                out += s[24:24 + USER]
            else:
                out += b"\x00" * USER  # form2 (audio/str) — keep addressing stable
        else:
            print(f"FATAL sector {i}: unknown mode byte {mode}", file=sys.stderr)
            return 1
    open(iso_path, "wb").write(out)
    print(f"wrote {iso_path}: {sectors} sectors -> {len(out)} bytes; mix={kinds}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_bin")
    ap.add_argument("out_iso")
    sys.exit(strip(ap.parse_args().raw_bin, ap.parse_args().out_iso))
