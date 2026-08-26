#!/usr/bin/env python3
"""AVPE control-channel client — drives the in-emulator lucent HTTP server.

Subcommands:
  status
  memread --addr 0x00367720 --len 16 [--fmt hex|u32|f32]
  memwrite --addr 0x... --hex aabbcc
  statesave --path scratch/states/x.p2s
  stateload --path scratch/states/x.p2s
  eecall --function 0x00137b30 [--a0 0x... --cycle-budget 3000000]
  moveabsolute --x 0.2 --y 0.2
  mousebutton primary|secondary press|release
  waitpointer --addr 0x00367720 --timeout 120   (polls u32 until non-zero)

Negative responses are loud: HTTP errors raise with status + body printed.
"""

import argparse
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request

DEFAULT_PORT = 28447
BASE = f"http://127.0.0.1:{DEFAULT_PORT}"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def req(method: str, path: str, body: dict | None = None) -> dict | bytes:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Connection": "close"}
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
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


BUTTONS = {  # PadDualshock2::Inputs bit space (bit index = enum order)
    "up": 1 << 0, "right": 1 << 1, "down": 1 << 2, "left": 1 << 3,
    "triangle": 1 << 4, "circle": 1 << 5, "cross": 1 << 6, "square": 1 << 7,
    "select": 1 << 8, "start": 1 << 9, "l1": 1 << 10, "l2": 1 << 11,
    "r1": 1 << 12, "r2": 1 << 13, "l3": 1 << 14, "r3": 1 << 15,
}


def main() -> int:
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help="loopback control port (default: 28447)")
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
    p = sub.add_parser("hold")
    p.add_argument("--addr", required=True)
    p.add_argument("--hex", required=True, help="bytes to keep rewritten while held")
    p.add_argument("--ms", type=float, default=250.0, help="hold duration")
    p.add_argument("--release", default=None,
                   help="optional hex to write once after release")
    p.add_argument("--period", type=float, default=4.0, help="rewrite period ms")
    p = sub.add_parser("press")
    p.add_argument("buttons", help="comma-separated names: " + ",".join(BUTTONS))
    p.add_argument("--ms", type=int, default=250)
    p = sub.add_parser("eecall")
    p.add_argument("--function", required=True)
    for register in ("a0", "a1", "a2", "a3"):
        p.add_argument(f"--{register}", type=lambda x: int(x, 0), default=0)
    p.add_argument("--cycle-budget", type=int, default=3_000_000)
    p = sub.add_parser("moveabsolute")
    p.add_argument("--x", type=float, required=True, help="normalized horizontal coordinate in 0..1")
    p.add_argument("--y", type=float, required=True, help="normalized vertical coordinate in 0..1")
    p = sub.add_parser("mousebutton")
    p.add_argument("button", choices=("primary", "secondary"))
    p.add_argument("edge", choices=("press", "release"))
    p = sub.add_parser("watch")
    p.add_argument("--addrs", required=True,
                   help="comma list addr[:len[:fmt]] (fmt hex|u32|f32), e.g. "
                        "0x49717e:2,0x3687fc:4:u32")
    p.add_argument("--hz", type=float, default=5.0)
    p.add_argument("--secs", type=float, default=10.0)
    p = sub.add_parser("pthe")
    p.add_argument("--syms", default="tools/pthe_syms.txt",
                   help="file of 'addr name' lines (pThe singletons)")
    p = sub.add_parser("snap")
    p.add_argument("--out", required=True, help="write BMP here")
    p = sub.add_parser("waitpointer")
    p.add_argument("--addr", required=True)
    p.add_argument("--timeout", type=float, default=120.0)

    a = ap.parse_args()
    BASE = f"http://127.0.0.1:{a.port}"
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
    elif a.cmd == "hold":
        # Keep rewriting the same bytes so per-frame pad refills can't clear
        # the press. Negative-duration or failed writes abort loudly.
        payload = {"addr": a.addr, "hex": a.hex}
        end = time.monotonic() + a.ms / 1000.0
        n = 0
        while time.monotonic() < end:
            req("POST", "/mem/write", payload)
            n += 1
            time.sleep(a.period / 1000.0)
        if a.release is not None:
            req("POST", "/mem/write", {"addr": a.addr, "hex": a.release})
        print(json.dumps({"held_ms": a.ms, "writes": n}))
    elif a.cmd == "press":
        mask = 0
        for name in a.buttons.split(","):
            name = name.strip().lower()
            if name not in BUTTONS:
                print(f"FATAL unknown button {name!r}", file=sys.stderr)
                return 1
            mask |= BUTTONS[name]
        print(json.dumps(req("POST", "/input/press", {"mask": mask, "ms": a.ms})))
    elif a.cmd == "eecall":
        payload = {
            "function": a.function,
            "a0": a.a0,
            "a1": a.a1,
            "a2": a.a2,
            "a3": a.a3,
            "cycle_budget": a.cycle_budget,
        }
        print(json.dumps(req("POST", "/ee/call", payload)))
    elif a.cmd == "moveabsolute":
        print(json.dumps(req("POST", "/input/move-absolute", {"x": a.x, "y": a.y})))
    elif a.cmd == "mousebutton":
        print(json.dumps(req(
            "POST", "/input/mouse-button", {"button": a.button, "edge": a.edge})))
    elif a.cmd == "pthe":
        # Dump every singleton pointer; non-null = live manager. Feed two
        # dumps to diff to see what a button press brought to life.
        syms = []
        path = a.syms if os.path.isabs(a.syms) else os.path.join(ROOT, a.syms)
        for line in open(path):
            parts = line.split()
            if len(parts) == 2:
                syms.append((parts[0], parts[1]))
        out = {}
        for addr, name in syms:
            r = req("GET", f"/mem/read?addr=0x{addr}&len=4")
            raw = bytes.fromhex(r["hex"])
            val = struct.unpack("<I", raw)[0]
            if val:
                out[name] = f"0x{val:08X}"
        print(json.dumps(out, indent=None))
    elif a.cmd == "snap":
        r = urllib.request.Request(BASE + "/snap")
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                data = resp.read()
        except urllib.error.HTTPError as e:
            print(f"FATAL http {e.code}: {e.read().decode(errors='replace')}", file=sys.stderr)
            return 1
        with open(a.out, "wb") as f:
            f.write(data)
        print(f"{a.out}: {len(data)} bytes")
    elif a.cmd == "watch":
        targets = []
        for spec in a.addrs.split(","):
            parts = spec.split(":")
            addr = parts[0]
            ln = int(parts[1], 0) if len(parts) > 1 and parts[1] else 4
            fmt = parts[2] if len(parts) > 2 and parts[2] else "hex"
            targets.append((addr, ln, fmt))
        end = time.monotonic() + a.secs
        n = 0
        while time.monotonic() < end:
            cells = []
            dbg = None
            try:
                dbg = req("GET", "/debug")
                for addr, ln, fmt in targets:
                    r = req("GET", f"/mem/read?addr={addr}&len={ln:x}")
                    cells.append(fmt_mem(r["hex"], fmt).replace("\n", " | "))
            except SystemExit:
                break
            t = time.strftime("%H:%M:%S")
            print(f"{t} xfer={dbg.get('transfers')} inj={dbg.get('inject')} "
                  f"fifo={dbg.get('lastfifo','')} || " + "  ".join(cells), flush=True)
            n += 1
            time.sleep(1.0 / a.hz)
        if n == 0:
            print("watch: no samples taken", file=sys.stderr)
            return 1
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
