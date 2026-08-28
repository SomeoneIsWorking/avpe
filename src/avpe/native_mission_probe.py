"""Clean-boot Marine M1 loader trigger and native-asset evidence."""

import json
import time
from pathlib import Path

from avpe.control_http import request_bytes, request_json
from avpe.load_timing import mission_load_timing_sample_is_ready
from avpe.native_asset_cache_probe import cache_snapshot_is_verified

SET_NEXT_LEVEL = 0x0016F8E0
SHELL_SINGLETON_ADDRESS = 0x003672F0
SHELL_LOAD_FLAGS_OFFSET = 0x808
AVP_WORLD_ADDRESS = 0x00367780
M1_BACKGROUND_PATH = "M01/background.tbd"
TBF_PATH = "tbd/tbf.tbf"


def await_mission_load_timing(
    port: int,
    deadline: float,
    mode: str,
) -> dict[str, object]:
    timing: dict[str, object] | None = None
    while time.monotonic() < deadline:
        timing = _json_snapshot(port, "/assets/mission-load-timing")
        if mission_load_timing_sample_is_ready(timing, mode):
            return timing
        time.sleep(0.05)
    raise RuntimeError(
        f"complete {mode} mission load timing was not observed: {timing}"
    )


def probe_marine_m1_transition(
    port: int,
    deadline: float,
    output_dir: Path,
    *,
    require_native_assets: bool = False,
) -> dict[str, object]:
    """Trigger the real MainLoop loader without depending on the menu-input seam."""
    shell = _read_u32(port, SHELL_SINGLETON_ADDRESS)
    if shell <= 0:
        raise RuntimeError("CShell singleton is unavailable")
    world_before = _read_u32(port, AVP_WORLD_ADDRESS)
    if world_before != 0:
        raise RuntimeError("pThe GAvPWorld was populated before the M1 trigger")
    native_before = _native_snapshots(port) if require_native_assets else None

    path_bytes = M1_BACKGROUND_PATH.encode() + b"\0"
    status, call, detail = request_json(
        port,
        "POST",
        "/ee/call",
        {
            "function": f"0x{SET_NEXT_LEVEL:08X}",
            "stack_argument": 0,
            "stack_hex": path_bytes.hex(),
            "cycle_budget": 3_000_000,
        },
    )
    if status != 200 or call is None:
        raise RuntimeError(
            f"CShell::SetNextLevel returned HTTP {status}: {detail}"
        )

    staged_path = _read_bytes(port, shell, len(path_bytes))
    flags = _read_u32(port, shell + SHELL_LOAD_FLAGS_OFFSET)
    endpoint = _await_m1_endpoint(port, deadline)
    native_after = _native_snapshots(port) if require_native_assets else None

    proof: dict[str, object] = {
        "input_route": "shell-set-next-level",
        "pad_injection": False,
        "input_savestate": False,
        "native_assets_required": require_native_assets,
        "trigger": {
            "function": _pointer(SET_NEXT_LEVEL),
            "shell": _pointer(shell),
            "path": M1_BACKGROUND_PATH,
            "path_bytes_hex": path_bytes.hex(),
            "staged_path_bytes_hex": staged_path.hex(),
            "flags_after": flags,
            "call": call,
        },
        "world_before": _pointer(world_before),
        "endpoint": endpoint,
    }
    if require_native_assets:
        proof["native_assets"] = {"before": native_before, "after": native_after}

    errors = validate_marine_m1_evidence(
        proof, require_native_assets=require_native_assets
    )
    if errors:
        raise RuntimeError("Marine M1 transition proof failed: " + "; ".join(errors))

    proof["verified"] = True
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_name = (
        "native-marine-m1-transition-proof.json"
        if require_native_assets
        else "marine-m1-transition-proof.json"
    )
    (output_dir / artifact_name).write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    )
    return proof


def validate_marine_m1_evidence(
    proof: dict[str, object],
    *,
    require_native_assets: bool = False,
) -> list[str]:
    errors: list[str] = []
    if proof.get("input_route") != "shell-set-next-level":
        errors.append("transition did not use the grounded SetNextLevel route")
    if proof.get("pad_injection") is not False:
        errors.append("transition did not exclude pad injection")
    if proof.get("input_savestate") is not False:
        errors.append("transition did not exclude an input savestate")

    trigger = proof.get("trigger")
    if not isinstance(trigger, dict):
        errors.append("M1 trigger evidence is missing")
    else:
        if trigger.get("function") != _pointer(SET_NEXT_LEVEL):
            errors.append("M1 trigger used the wrong guest function")
        if trigger.get("path") != M1_BACKGROUND_PATH:
            errors.append("M1 trigger path is not exact")
        expected_hex = (M1_BACKGROUND_PATH.encode() + b"\0").hex()
        if trigger.get("path_bytes_hex") != expected_hex \
                or trigger.get("staged_path_bytes_hex") != expected_hex:
            errors.append("M1 trigger did not stage the exact NUL-terminated path")
        if _integer(trigger.get("flags_after")) & 1 == 0:
            errors.append("CShell pending-level flag was not set")
        call = trigger.get("call")
        shell = _parse_pointer(trigger.get("shell"))
        if not isinstance(call, dict):
            errors.append("SetNextLevel guest-call evidence is missing")
        else:
            if call.get("stack_restored") is not True \
                    or _parse_pointer(call.get("staging_address")) <= 0:
                errors.append("SetNextLevel did not restore its guest staging")
            if _parse_pointer(call.get("v0")) != shell or shell <= 0:
                errors.append("SetNextLevel did not return the grounded CShell object")

    if _parse_pointer(proof.get("world_before")) != 0:
        errors.append("pThe GAvPWorld was already populated before the M1 trigger")
    endpoint = proof.get("endpoint")
    if not isinstance(endpoint, dict) or _parse_pointer(endpoint.get("world")) <= 0:
        errors.append("Marine M1 endpoint did not populate pThe GAvPWorld")

    native_assets = proof.get("native_assets")
    if require_native_assets:
        if not isinstance(native_assets, dict):
            errors.append("native asset evidence is missing")
        else:
            errors.extend(_native_asset_errors(native_assets))
    return errors


def _await_m1_endpoint(port: int, deadline: float) -> dict[str, object]:
    last = 0
    while time.monotonic() < deadline:
        last = _read_u32(port, AVP_WORLD_ADDRESS)
        if last != 0:
            return {"world": _pointer(last)}
        time.sleep(0.05)
    raise RuntimeError(
        f"Marine M1 briefing/gameplay endpoint was not observed: {_pointer(last)}"
    )


def _read_bytes(port: int, address: int, length: int) -> bytes:
    status, body = request_bytes(
        port, "GET", f"/mem/read?addr=0x{address:08x}&len={length:x}"
    )
    if status != 200:
        raise RuntimeError(
            f"guest memory read 0x{address:08X}+{length} returned HTTP {status}"
        )
    candidate = json.loads(body)
    if not isinstance(candidate, dict) or candidate.get("len") != length:
        raise RuntimeError(f"guest memory read returned malformed evidence: {candidate}")
    try:
        value = bytes.fromhex(str(candidate.get("hex", "")))
    except ValueError as error:
        raise RuntimeError("guest memory read returned invalid hex") from error
    if len(value) != length:
        raise RuntimeError(
            f"guest memory read returned {len(value)} bytes instead of {length}"
        )
    return value


def _read_u32(port: int, address: int) -> int:
    return int.from_bytes(_read_bytes(port, address, 4), "little")


def _native_snapshots(port: int) -> dict[str, object]:
    return {
        "opens": _json_snapshot(port, "/assets/opens"),
        "cache": _json_snapshot(port, "/assets/cache"),
    }


def _json_snapshot(port: int, path: str) -> dict[str, object]:
    status, body = request_bytes(port, "GET", path)
    if status != 200:
        raise RuntimeError(f"{path} snapshot returned HTTP {status}")
    candidate = json.loads(body)
    if not isinstance(candidate, dict):
        raise RuntimeError(f"{path} snapshot was not a JSON object")
    return candidate


def _native_asset_errors(native_assets: dict[str, object]) -> list[str]:
    errors: list[str] = []
    before = native_assets.get("before")
    after = native_assets.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return ["native before/after snapshots are missing"]
    before_opens = before.get("opens")
    after_opens = after.get("opens")
    before_cache = before.get("cache")
    after_cache = after.get("cache")
    if not isinstance(before_opens, dict) or not isinstance(after_opens, dict):
        errors.append("native open snapshots are missing")
    else:
        before_tbf = _path_observation(before_opens, TBF_PATH)
        after_tbf = _path_observation(after_opens, TBF_PATH)
        if before_tbf is None or after_tbf is None:
            errors.append("TBF native open evidence is missing")
        else:
            for field in (
                "count",
                "native_open_count",
                "close_count",
                "original_fallback_count",
            ):
                if _counter(before_tbf, field) != _counter(after_tbf, field):
                    errors.append(f"TBF {field} changed during the M1 transition")
            if _counter(before_tbf, "native_open_count") <= 0:
                errors.append("TBF was not open through the native asset store")
            if _counter(before_tbf, "original_fallback_count") != 0:
                errors.append("TBF used the original optical fallback")
            for field in ("read_calls", "seek_calls", "bytes_read"):
                if _counter(after_tbf, field) <= _counter(before_tbf, field):
                    errors.append(
                        f"TBF {field} did not increase during the M1 transition"
                    )
    if not cache_snapshot_is_verified(
        before_cache if isinstance(before_cache, dict) else None
    ):
        errors.append("pre-transition cache snapshot is not bounded and quiescent")
    if not cache_snapshot_is_verified(
        after_cache if isinstance(after_cache, dict) else None
    ):
        errors.append("post-transition cache snapshot is not bounded and quiescent")
    return errors


def _path_observation(
    snapshot: dict[str, object], expected_path: str
) -> dict[str, object] | None:
    paths = snapshot.get("paths")
    if not isinstance(paths, list):
        return None
    return next(
        (
            item
            for item in paths
            if isinstance(item, dict)
            and str(item.get("path", ""))
            .replace("\\", "/")
            .casefold()
            .removesuffix(";1")
            .endswith(expected_path)
        ),
        None,
    )


def _parse_pointer(value: object) -> int:
    if isinstance(value, bool):
        return -1
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return -1
    try:
        return int(value, 16)
    except ValueError:
        return -1


def _integer(value: object) -> int:
    if isinstance(value, bool):
        return -1
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return -1


def _counter(value: dict[str, object], field: str) -> int:
    return _integer(value.get(field))


def _pointer(value: int) -> str:
    return f"0x{value:08X}"
