#!/usr/bin/env python3
"""AVPE control-channel client — drives the in-emulator lucent HTTP server.

Subcommands:
  status
  memread --addr 0x00367720 --len 16 [--fmt hex|u32|f32]
  memwrite --addr 0x... --hex aabbcc
  statesave --path scratch/states/x.p2s
  stateload --path scratch/states/x.p2s
  waitpointer --addr 0x00367720 --timeout 120   (polls u32 until non-zero)

Negative responses are loud: HTTP errors raise with status + body printed.
"""

import argparse
import json
import struct
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:28447"


def req(method: str, path: str, body: dict | None = None) -> dict | bytes:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"FATAL http {e.code}: {e.read().decode(errors='replace')}", file=sys.stderr)
        raise SystemExit(1)
    except urllib.error.URLError as e:
        print(f"FATAL cannot reach {BASE}: {e.reason}", file=sys.stderr)
        raise SystemExit(2)


def fmt_mem(hexstr: str, fmt: str) -> str:
    raw = bytes.fromhex(hexstr)
    if fmt == "hex":
        return hexstr
    out = []
    for i in range(0, len(raw) - len(raw) % 4, 4):
        w = raw[i:i + 4]
        if fmt == "u32":
            out.append(f"{i:04x}: {struct.unpack('<I', w)[0]:08d}")
        elif fmt == "f32":
            out.append(f"{i:04x}: {struct.unpack('<f', w)[0]:.4f}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("memread")
    p.add_argument("--addr", required=True)
    p.add_argument("--len", type=lambda x: int(x, 0), default=16)
    p.add_argument("--fmt", choices=["hex", "u32", "f32"], default="hex")
    p = sub.add_parser("memwrite")
    p.add_argument("--addr", required=True)
    p.add_argument("--hex", required=True)
    p = sub.add_parser("statesave")
    p.add_argument("--path", required=True)
    p = sub.add_parser("stateload")
    p.add_argument("--path", required=True)
    p = sub.add_parser("waitpointer")
    p.add_argument("--addr", required=True)
    p.add_argument("--timeout", type=float, default=120.0)

    a = ap.parse_args()
    if a.cmd == "status":
        print(json.dumps(req("GET", "/status")))
    elif a.cmd == "memread":
        r = req("GET", f"/mem/read?addr={a.addr}&len={a.len:x}")
        print(fmt_mem(r["hex"], a.fmt))
    elif a.cmd == "memwrite":
        print(json.dumps(req("POST", "/mem/write", {"addr": a.addr, "hex": a.hex})))
    elif a.cmd == "statesave":
        print(json.dumps(req("POST", "/state/save", {"path": a.path})))
    elif a.cmd == "stateload":
        print(json.dumps(req("POST", "/state/load", {"path": a.path})))
    elif a.cmd == "waitpointer":
        deadline = time.monotonic() + a.timeout
        polls = 0
        while time.monotonic() < deadline:
            r = req("GET", f"/mem/read?addr={a.addr}&len=4")
            polls += 1
            val = struct.unpack(">I", bytes.fromhex(r["hex"]))[0]  # BE hex display of LE word
            if val != 0:
                print(f"non-zero after {polls} polls: {val:08x}")
                return 0
            time.sleep(1.0)
        print(f"STILL ZERO after {polls} polls / {a.timeout:.0f}s at {a.addr} — "
              f"either never constructed or wrong address")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
