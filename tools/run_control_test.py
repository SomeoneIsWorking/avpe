#!/usr/bin/env python3
"""Run AVPE control tests without a native window or audio device."""

import argparse
import hashlib
import http.client
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from avpe.cli import load_env
from avpe.control_test import (
    EXPECTED_SERIAL,
    build_argv,
    build_environment,
    status_is_verified,
)
from avpe.cursor import CursorObservation, detect_cursor
from avpe.pcsx2_config import ensure_test_config

ROOT = Path(__file__).resolve().parent.parent
PCSX2 = ROOT / "scratch" / "build" / "bin" / "pcsx2-qt"
DATA_DIR = ROOT / "scratch" / "control-test" / "pcsx2-home"
LOG_DIR = ROOT / "scratch" / "control-test" / "logs"


def find_bios(directory: str) -> Path | None:
    if not directory:
        return None
    root = Path(directory)
    if not root.is_dir():
        return None
    preferred = root / "scph39001.bin"
    if preferred.is_file():
        return preferred
    candidates = sorted(root.glob("*.bin")) + sorted(root.glob("*.BIN"))
    return next((path for path in candidates if path.stat().st_size >= 2_000_000), None)


def stop_process_group(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def read_status(port: int) -> dict[str, str] | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=0.5) as response:
            body = json.loads(response.read())
    except (OSError, UnicodeError, ValueError, http.client.HTTPException,
            urllib.error.URLError, json.JSONDecodeError):
        return None
    return body if isinstance(body, dict) else None


def request_shutdown(port: int) -> bool:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/shutdown", data=b"{}", method="POST",
        headers={"Content-Type": "application/json", "Connection": "close"})
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status == 202
    except (OSError, http.client.HTTPException, urllib.error.URLError):
        return False


def request_bytes(
    port: int,
    method: str,
    path: str,
    payload: dict[str, float] | None = None,
    timeout: float = 2.0,
) -> tuple[int, bytes]:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=body, method=method,
        headers={"Content-Type": "application/json", "Connection": "close"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except (OSError, http.client.HTTPException, urllib.error.URLError) as error:
        raise RuntimeError(f"{method} {path} failed: {error}") from error


def stable_cursor_snapshot(
    port: int,
    expected_x: float,
    expected_y: float,
    deadline: float,
    artifact_name: str,
) -> tuple[CursorObservation, bytes]:
    previous: CursorObservation | None = None
    for _ in range(12):
        if time.monotonic() >= deadline:
            break
        status, bmp = request_bytes(port, "GET", "/snap")
        if status != 200:
            continue
        observation = detect_cursor(bmp, expected_x, expected_y)
        if observation is None:
            previous = None
            continue
        if previous is not None and abs(observation.x - previous.x) <= 2.0 \
                and abs(observation.y - previous.y) <= 2.0:
            artifact = LOG_DIR.parent / artifact_name
            artifact.write_bytes(bmp)
            return observation, bmp
        previous = observation
    raise RuntimeError(
        f"cursor did not stabilize near ({expected_x:.1f}, {expected_y:.1f})")


def probe_native_pointer(port: int, deadline: float) -> dict[str, object]:
    targets = (("p1", 128.0, 96.0), ("p2", 512.0, 96.0))
    results: dict[str, object] = {}
    observations: dict[str, CursorObservation] = {}
    for name, screen_x, screen_y in targets:
        normalized = {"x": screen_x / 639.0, "y": screen_y / 447.0}
        status, body = request_bytes(port, "POST", "/input/move-absolute", normalized)
        if status != 200:
            raise RuntimeError(
                f"native move {name} returned HTTP {status}: {body.decode(errors='replace').strip()}")
        response = json.loads(body)
        if not isinstance(response, dict):
            raise RuntimeError(f"native move {name} returned non-object JSON")
        if not response.get("stack_restored") or response.get("staging_address") == "0x00000000":
            raise RuntimeError(f"native move {name} did not attest restored guest staging: {response}")
        for field, expected in (("screen_x", screen_x), ("screen_y", screen_y),
                                ("observed_x", screen_x), ("observed_y", screen_y)):
            if abs(float(response.get(field, float("inf"))) - expected) > 0.05:
                raise RuntimeError(f"native move {name} returned unexpected {field}: {response}")
        observation, bmp = stable_cursor_snapshot(
            port, screen_x, screen_y, deadline, f"pointer-{name}.bmp")
        observations[name] = observation
        results[name] = {
            "request": normalized,
            "response": response,
            "cursor": observation.__dict__,
            "snapshot_sha256": hashlib.sha256(bmp).hexdigest(),
        }

    first = observations["p1"]
    second = observations["p2"]
    if second.x - first.x <= 300.0 or abs(second.y - first.y) > 8.0:
        raise RuntimeError(f"cursor positions are not distinct horizontal targets: {first}, {second}")

    status, body = request_bytes(
        port, "POST", "/input/move-absolute", {"x": 1.25, "y": 0.2})
    if status != 400:
        raise RuntimeError(
            f"out-of-range native move returned HTTP {status}, expected 400: "
            f"{body.decode(errors='replace').strip()}")
    negative, negative_bmp = stable_cursor_snapshot(
        port, 512.0, 96.0, deadline, "pointer-negative.bmp")
    if abs(negative.x - second.x) > 2.0 or abs(negative.y - second.y) > 2.0:
        raise RuntimeError(f"rejected move changed the rendered cursor: {second}, {negative}")
    results["negative"] = {
        "http_status": status,
        "cursor": negative.__dict__,
        "snapshot_sha256": hashlib.sha256(negative_bmp).hexdigest(),
    }
    proof_path = LOG_DIR.parent / "pointer-proof.json"
    proof_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    return results


def reserve_port(requested: int) -> tuple[int, socket.socket]:
    reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    reservation.bind(("127.0.0.1", requested))
    return reservation.getsockname()[1], reservation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--statefile", type=Path)
    parser.add_argument("--probe-native-pointer", action="store_true",
                        help="prove two native cursor positions; requires --statefile")
    parser.add_argument("--http-port", type=int, default=0,
                        help="control port; zero allocates an available loopback port")
    args = parser.parse_args()

    if args.seconds <= 0:
        parser.error("--seconds must be greater than zero")
    if not 0 <= args.http_port <= 65535:
        parser.error("--http-port must be between 0 and 65535")
    if args.statefile is not None and not args.statefile.is_file():
        parser.error(f"--statefile is not a file: {args.statefile}")
    if args.probe_native_pointer and args.statefile is None:
        parser.error("--probe-native-pointer requires --statefile")

    if not PCSX2.is_file():
        print(f"FATAL built PCSX2 missing: {PCSX2}", file=sys.stderr)
        return 2

    project_env = load_env()
    chd = Path(project_env.get("AVPE_CHD", ""))
    bios = find_bios(project_env.get("AVPE_BIOS_DIR", ""))
    if not chd.is_file():
        print(f"FATAL AVPE_CHD missing or invalid: {chd}", file=sys.stderr)
        return 2
    if bios is None:
        print("FATAL no usable BIOS in AVPE_BIOS_DIR", file=sys.stderr)
        return 2

    ensure_test_config(DATA_DIR, bios)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        port, port_reservation = reserve_port(args.http_port)
    except OSError as error:
        print(f"FATAL control port {args.http_port} is unavailable: {error}", file=sys.stderr)
        return 2
    nonce = secrets.token_hex(16)
    argv = build_argv(PCSX2, DATA_DIR, LOG_DIR / "emulog.txt", chd, args.statefile)
    env = build_environment(os.environ, port, nonce)
    stdout = (LOG_DIR / "stdout.log").open("wb")
    try:
        port_reservation.close()
        proc = subprocess.Popen(argv, env=env, stdout=stdout, stderr=subprocess.STDOUT,
                                start_new_session=True)
    except OSError as error:
        stdout.close()
        print(f"FATAL could not start control test: {error}", file=sys.stderr)
        return 2
    print(f"control-test pid={proc.pid} port={port} display=surfaceless audio=null", flush=True)

    def handle_signal(_signum: int, _frame: object) -> None:
        stop_process_group(proc)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    deadline = time.monotonic() + args.seconds
    boot_status: dict[str, str] | None = None
    pointer_proof: dict[str, object] | None = None
    probe_error: str | None = None
    graceful_shutdown = False
    try:
        while proc.poll() is None and time.monotonic() < deadline:
            status = read_status(port)
            if status_is_verified(status, nonce):
                boot_status = status
                if args.probe_native_pointer:
                    try:
                        pointer_proof = probe_native_pointer(port, deadline)
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                    break
            time.sleep(0.1)
        if proc.poll() is None and request_shutdown(port):
            try:
                proc.wait(timeout=10)
                graceful_shutdown = True
            except subprocess.TimeoutExpired:
                pass
    finally:
        stop_process_group(proc)
        stdout.close()

    if proc.returncode != 0:
        print(f"FATAL control test exited rc={proc.returncode}; see {LOG_DIR}", file=sys.stderr)
        return 1
    if not graceful_shutdown:
        print(f"FATAL control test did not complete graceful shutdown; see {LOG_DIR}", file=sys.stderr)
        return 1
    if boot_status is None:
        print(f"FATAL {EXPECTED_SERIAL} never reached Running state; see {LOG_DIR}", file=sys.stderr)
        return 1
    print(f"control-test verified status={json.dumps(boot_status, sort_keys=True)}", flush=True)
    if args.probe_native_pointer:
        if pointer_proof is None:
            detail = probe_error or "probe did not run"
            print(f"FATAL native pointer probe failed: {detail}; see {LOG_DIR}", file=sys.stderr)
            return 1
        print(f"control-test native-pointer proof={json.dumps(pointer_proof, sort_keys=True)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
