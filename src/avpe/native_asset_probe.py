"""Surfaceless native-asset diagnostic polling and proof orchestration."""

import json
import time
from collections.abc import Callable
from pathlib import Path

from avpe.asset_byte_compare import asset_byte_trace_is_ready
from avpe.control_http import request_bytes, request_json
from avpe.control_test import (
    ABSENT_NATIVE_ASSET_SENTINEL,
    native_asset_reads_are_verified,
    native_movie_reads_are_verified,
    native_stream_reads_are_verified,
    oracle_asset_fallback_is_verified,
)
from avpe.load_timing import load_timing_sample_is_ready
from avpe.native_asset_cache_probe import await_asset_cache, build_cache_proof

NATIVE_IOMAN_RECOVERY_PATH = "movies/intro.pss"
NATIVE_CDVD_RECOVERY_PATH = "streams/menu01.ziv"
NATIVE_RESET_PATHS = {
    "ioman": NATIVE_IOMAN_RECOVERY_PATH,
    "cdvd": NATIVE_CDVD_RECOVERY_PATH,
}


def await_asset_trace(
    port: int,
    deadline: float,
    verifier: Callable[[dict[str, object] | None], bool],
    description: str,
) -> dict[str, object]:
    trace: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, body = request_bytes(port, "GET", "/assets/opens")
        if status != 200:
            raise RuntimeError(f"{description} returned HTTP {status}")
        candidate = json.loads(body)
        if isinstance(candidate, dict):
            trace = candidate
            if verifier(trace):
                return trace
        time.sleep(0.05)
    raise RuntimeError(f"{description} was not observed: {trace}")


def await_asset_byte_trace(port: int, deadline: float, mode: str) -> dict[str, object]:
    trace: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, body = request_bytes(port, "GET", "/assets/byte-trace")
        if status != 200:
            raise RuntimeError(f"asset byte trace returned HTTP {status}")
        candidate = json.loads(body)
        if isinstance(candidate, dict):
            trace = candidate
            if asset_byte_trace_is_ready(trace, mode):
                return trace
        time.sleep(0.05)
    raise RuntimeError(f"complete {mode} asset byte trace was not observed: {trace}")


def write_asset_byte_trace(
    trace: dict[str, object], mode: str, output: Path | None, log_dir: Path
) -> Path:
    actual_output = output or (log_dir / f"asset-byte-trace-{mode}.json")
    actual_output.parent.mkdir(parents=True, exist_ok=True)
    actual_output.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return actual_output


def await_load_timing(port: int, deadline: float, mode: str) -> dict[str, object]:
    timing: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, body = request_bytes(port, "GET", "/assets/load-timing")
        if status != 200:
            raise RuntimeError(f"asset load timing returned HTTP {status}")
        candidate = json.loads(body)
        if isinstance(candidate, dict):
            timing = candidate
            if load_timing_sample_is_ready(timing, mode):
                return timing
        time.sleep(0.05)
    raise RuntimeError(f"complete {mode} asset load timing was not observed: {timing}")


def await_native_stream_reads(
    port: int,
    deadline: float,
    description: str,
) -> dict[str, object]:
    return await_asset_trace(
        port,
        deadline,
        native_stream_reads_are_verified,
        description,
    )


def _normalized_guest_path(value: object) -> str:
    return str(value).replace("\\", "/").casefold().removesuffix(";1")


def _path_observation(
    trace: dict[str, object], expected_path: str
) -> dict[str, object] | None:
    paths = trace.get("paths")
    if not isinstance(paths, list):
        return None
    return next(
        (
            entry
            for entry in paths
            if isinstance(entry, dict)
            and _normalized_guest_path(entry.get("path")).endswith(expected_path)
        ),
        None,
    )


def _completion(trace: dict[str, object]) -> dict[str, object] | None:
    value = trace.get("cdvd_completion")
    return value if isinstance(value, dict) else None


def _active_native_path(
    trace: dict[str, object] | None, expected_path: str
) -> bool:
    if trace is None:
        return False
    observation = _path_observation(trace, expected_path)
    return bool(
        observation is not None
        and int(observation.get("native_open_count", 0)) > 0
        and int(observation.get("original_fallback_count", -1)) == 0
        and int(observation.get("close_count", 0))
        < int(observation.get("native_open_count", 0))
    )


def _mapped_native_path(
    trace: dict[str, object] | None, expected_path: str
) -> bool:
    if trace is None:
        return False
    observation = _path_observation(trace, expected_path)
    completion = _completion(trace)
    return bool(
        observation is not None
        and int(observation.get("native_open_count", 0)) > 0
        and int(observation.get("original_fallback_count", -1)) == 0
        and completion is not None
        and int(completion.get("rejected_records", -1)) == 0
        and int(completion.get("active_tokens", -1)) == 0
    )


def _state_snapshot(
    response: dict[str, object] | None, success_field: str, operation: str
) -> dict[str, object]:
    if response is None or response.get(success_field) is not True:
        raise RuntimeError(f"{operation} did not report {success_field}=true")
    snapshot = response.get("native_asset_state")
    if not isinstance(snapshot, dict):
        raise RuntimeError(f"{operation} omitted its atomic native asset state")
    descriptors = snapshot.get("descriptors")
    mappings = snapshot.get("cdvd_mappings")
    if not isinstance(descriptors, list) or not isinstance(mappings, list):
        raise RuntimeError(f"{operation} returned malformed native asset collections")
    if int(snapshot.get("next_lsn", -1)) < 0:
        raise RuntimeError(f"{operation} returned an invalid native CDVD allocator")
    if int(snapshot.get("cdvd_completion_active_tokens", -1)) != 0:
        raise RuntimeError(f"{operation} crossed a transient native completion")
    return snapshot


def _request_state(
    port: int, operation: str, state_path: Path
) -> dict[str, object]:
    status, response, detail = request_json(
        port, "POST", f"/state/{operation}", {"path": str(state_path.resolve())}
    )
    if status != 200:
        raise RuntimeError(f"state {operation} returned HTTP {status}: {detail}")
    return _state_snapshot(
        response,
        "saved" if operation == "save" else "loaded",
        f"state {operation}",
    )


def _request_guest_reset(port: int) -> dict[str, object]:
    status, response, detail = request_json(port, "POST", "/guest/reset", {})
    if status != 200 or response is None or response.get("reset") is not True:
        raise RuntimeError(f"guest reset returned HTTP {status}: {detail}")
    before = response.get("before")
    after = response.get("after")
    cache = response.get("cache")
    if not isinstance(before, dict) or not isinstance(after, dict) \
            or not isinstance(cache, dict):
        raise RuntimeError("guest reset omitted its native state or cache snapshot")
    before_epoch = int(before.get("guest_reset_epoch", -1))
    after_epoch = int(after.get("guest_reset_epoch", -1))
    if after_epoch <= before_epoch:
        raise RuntimeError(
            f"guest reset epoch did not advance: {before_epoch} -> {after_epoch}")
    if after.get("descriptors") != [] or after.get("cdvd_mappings") != []:
        raise RuntimeError(f"guest reset retained active native state: {after}")
    if int(after.get("cdvd_completion_active_tokens", -1)) != 0:
        raise RuntimeError(f"guest reset retained a completion token: {after}")
    if int(cache.get("transient_handles", -1)) != 0:
        raise RuntimeError(f"guest reset retained a transient cache handle: {cache}")
    if int(cache.get("resident_pages", -1)) > 512 \
            or int(cache.get("resident_bytes", -1)) > 32 * 1024 * 1024:
        raise RuntimeError(f"guest reset exceeded the bounded cache: {cache}")
    return response


def _descriptor(
    snapshot: dict[str, object], expected_path: str
) -> dict[str, object] | None:
    descriptors = snapshot["descriptors"]
    assert isinstance(descriptors, list)
    return next(
        (
            descriptor
            for descriptor in descriptors
            if isinstance(descriptor, dict)
            and _normalized_guest_path(descriptor.get("path")).endswith(
                expected_path
            )
        ),
        None,
    )


def _mapping(
    snapshot: dict[str, object], expected_path: str
) -> dict[str, object] | None:
    mappings = snapshot["cdvd_mappings"]
    assert isinstance(mappings, list)
    return next(
        (
            mapping
            for mapping in mappings
            if isinstance(mapping, dict)
            and _normalized_guest_path(mapping.get("path")).endswith(expected_path)
        ),
        None,
    )


def _await_path_progress(
    port: int,
    deadline: float,
    expected_path: str,
    baseline: dict[str, object],
    require_completion_progress: bool,
) -> dict[str, object]:
    baseline_path = _path_observation(baseline, expected_path)
    if baseline_path is None:
        raise RuntimeError(f"baseline omitted {expected_path}")
    baseline_completion = _completion(baseline)

    def progressed(candidate: dict[str, object] | None) -> bool:
        if candidate is None:
            return False
        observation = _path_observation(candidate, expected_path)
        if observation is None:
            return False
        if (
            int(observation.get("native_open_count", -1))
            != int(baseline_path.get("native_open_count", -2))
            or int(observation.get("original_fallback_count", -1)) != 0
            or int(observation.get("read_calls", 0))
            <= int(baseline_path.get("read_calls", 0))
            or int(observation.get("bytes_read", 0))
            <= int(baseline_path.get("bytes_read", 0))
        ):
            return False
        if not require_completion_progress:
            return True
        completion = _completion(candidate)
        if completion is None or baseline_completion is None:
            return False
        recorded = int(completion.get("recorded", 0))
        return bool(
            recorded > int(baseline_completion.get("recorded", 0))
            and int(completion.get("consumed", -1)) == recorded
            and int(completion.get("rejected_records", -1)) == 0
            and int(completion.get("active_tokens", -1)) == 0
        )

    return await_asset_trace(
        port,
        deadline,
        progressed,
        f"continued native reads for {expected_path}",
    )


def _current_asset_trace(port: int) -> dict[str, object]:
    return await_asset_trace(
        port,
        time.monotonic() + 2.0,
        lambda candidate: candidate is not None,
        "native asset observations",
    )


def _runtime_status(port: int) -> dict[str, object]:
    status, body = request_bytes(port, "GET", "/status")
    if status != 200:
        raise RuntimeError(f"post-load status returned HTTP {status}")
    candidate = json.loads(body)
    if (
        not isinstance(candidate, dict)
        or candidate.get("vm") != "Running"
        or candidate.get("host_mode") != "control-test"
        or candidate.get("surface") != "surfaceless"
        or candidate.get("audio") != "null-muted"
    ):
        raise RuntimeError(f"post-load runtime status is invalid: {candidate}")
    return candidate


def probe_native_ioman_state_recovery(
    port: int, deadline: float, output_dir: Path
) -> dict[str, object]:
    await_asset_trace(
        port,
        deadline,
        lambda trace: _active_native_path(trace, NATIVE_IOMAN_RECOVERY_PATH),
        "live native INTRO.PSS descriptor",
    )
    state_dir = output_dir / "states"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "native-ioman-recovery.p2s"
    saved = _request_state(port, "save", state_path)
    descriptor = _descriptor(saved, NATIVE_IOMAN_RECOVERY_PATH)
    if (
        descriptor is None
        or int(descriptor.get("fd", -1)) < 0
        or int(descriptor.get("cursor", 0)) <= 0
    ):
        raise RuntimeError("state save did not capture a live INTRO.PSS descriptor")
    after_save = _current_asset_trace(port)
    before_load = _await_path_progress(
        port, deadline, NATIVE_IOMAN_RECOVERY_PATH, after_save, False
    )
    loaded = _request_state(port, "load", state_path)
    if loaded != saved:
        raise RuntimeError("loaded native asset state differs from the saved state")
    after_load = _await_path_progress(
        port, deadline, NATIVE_IOMAN_RECOVERY_PATH, before_load, False
    )
    cache = await_asset_cache(port, deadline)
    status_after_load = _runtime_status(port)
    proof = {
        "path": NATIVE_IOMAN_RECOVERY_PATH,
        "saved_state": saved,
        "loaded_state": loaded,
        "before_load": before_load,
        "after_load": after_load,
        "cache": cache,
        "status_after_load": status_after_load,
    }
    (output_dir / "native-ioman-state-recovery-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    )
    return proof


def probe_native_cdvd_state_recovery(
    port: int, deadline: float, output_dir: Path
) -> dict[str, object]:
    await_asset_trace(
        port,
        deadline,
        lambda trace: _mapped_native_path(trace, NATIVE_CDVD_RECOVERY_PATH),
        "live native MENU01.ZIV mapping",
    )
    state_dir = output_dir / "states"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "native-cdvd-recovery.p2s"
    saved = _request_state(port, "save", state_path)
    mapping = _mapping(saved, NATIVE_CDVD_RECOVERY_PATH)
    if (
        mapping is None
        or int(mapping.get("base_lsn", 0)) <= 0
        or int(mapping.get("size", 0)) <= 0
        or len(str(mapping.get("sha256", ""))) != 64
    ):
        raise RuntimeError("state save did not capture the live MENU01.ZIV mapping")
    after_save = _current_asset_trace(port)
    before_load = _await_path_progress(
        port, deadline, NATIVE_CDVD_RECOVERY_PATH, after_save, True
    )
    loaded = _request_state(port, "load", state_path)
    if loaded != saved:
        raise RuntimeError("loaded native CDVD state differs from the saved state")
    after_load = _await_path_progress(
        port, deadline, NATIVE_CDVD_RECOVERY_PATH, before_load, True
    )
    cache = await_asset_cache(port, deadline)
    status_after_load = _runtime_status(port)
    proof = {
        "path": NATIVE_CDVD_RECOVERY_PATH,
        "saved_state": saved,
        "loaded_state": loaded,
        "before_load": before_load,
        "after_load": after_load,
        "cache": cache,
        "status_after_load": status_after_load,
    }
    (output_dir / "native-cdvd-state-recovery-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    )
    return proof


def probe_native_asset_guest_reset(
    port: int,
    deadline: float,
    output_dir: Path,
    mode: str,
) -> dict[str, object]:
    expected_path = NATIVE_RESET_PATHS[mode]
    verifier = _active_native_path if mode == "ioman" else _mapped_native_path
    await_asset_trace(
        port,
        deadline,
        lambda trace: verifier(trace, expected_path),
        f"live native {expected_path} before guest reset",
    )
    state_dir = output_dir / "states"
    state_dir.mkdir(parents=True, exist_ok=True)
    saved = _request_state(port, "save", state_dir / f"native-{mode}-reset.p2s")
    target = _descriptor(saved, expected_path) if mode == "ioman" else _mapping(saved, expected_path)
    if target is None:
        raise RuntimeError(f"state save did not capture {expected_path} before guest reset")

    reset = _request_guest_reset(port)
    before = reset["before"]
    after = reset["after"]
    assert isinstance(before, dict)
    assert isinstance(after, dict)
    before_target = _descriptor(before, expected_path) if mode == "ioman" else _mapping(before, expected_path)
    if before_target is None:
        raise RuntimeError(f"guest reset boundary omitted active {expected_path}")

    baseline_trace = _current_asset_trace(port)
    baseline_path = _path_observation(baseline_trace, expected_path)
    if baseline_path is None:
        raise RuntimeError(f"reset baseline omitted {expected_path}")
    baseline_completion = _completion(baseline_trace)

    def resumed(candidate: dict[str, object] | None) -> bool:
        if candidate is None:
            return False
        observation = _path_observation(candidate, expected_path)
        if observation is None \
                or int(observation.get("native_open_count", 0)) \
                <= int(baseline_path.get("native_open_count", 0)) \
                or int(observation.get("read_calls", 0)) \
                <= int(baseline_path.get("read_calls", 0)) \
                or int(observation.get("bytes_read", 0)) \
                <= int(baseline_path.get("bytes_read", 0)) \
                or int(observation.get("original_fallback_count", -1)) != 0:
            return False
        if mode != "cdvd":
            return True
        completion = _completion(candidate)
        if completion is None or baseline_completion is None:
            return False
        return (
            int(completion.get("recorded", 0)) > int(baseline_completion.get("recorded", 0))
            and int(completion.get("consumed", -1)) == int(completion.get("recorded", -2))
            and int(completion.get("rejected_records", -1)) == 0
            and int(completion.get("active_tokens", -1)) == 0
        )

    resumed_trace = await_asset_trace(
        port, deadline, resumed, f"native {expected_path} reads after guest reset"
    )
    status_after_reset = _runtime_status(port)
    proof = {
        "mode": mode,
        "path": expected_path,
        "saved_state": saved,
        "reset": reset,
        "resumed_trace": resumed_trace,
        "status_after_reset": status_after_reset,
    }
    (output_dir / f"native-{mode}-guest-reset-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    )
    return proof


def capture_iso_oracle(port: int) -> None:
    status, body = request_bytes(port, "POST", "/assets/capture-iso-oracle", {})
    if status != 200:
        raise RuntimeError(
            f"ISO oracle capture returned HTTP {status}: "
            f"{body.decode(errors='replace').strip()}"
        )


def probe_native_assets(
    port: int,
    deadline: float,
    require_native_reads: bool,
    output_dir: Path,
) -> dict[str, object]:
    verifier = (
        native_asset_reads_are_verified
        if require_native_reads
        else oracle_asset_fallback_is_verified
    )
    expected = "native TBF reads" if require_native_reads else "the TBF archive"
    trace = await_asset_trace(port, deadline, verifier, expected)
    policy: dict[str, str] | None = None
    if require_native_reads:
        cases = {
            "native": ("cdrom0:/TBD/TBF.TBF;1", "read", "native-file"),
            "write": ("cdrom0:/TBD/TBF.TBF;1", "write", "refused-access"),
            "traversal": (
                "cdrom0:/TBD/../SLUS_201.47;1",
                "read",
                "refused-access",
            ),
            "missing": (
                "cdrom0:/TBD/__AVPE_MISSING__.TBD;1",
                "read",
                "refused-missing",
            ),
            "bootstrap": ("cdrom0:/SLUS_201.47;1", "read", "unhandled"),
        }
        policy = {}
        for name, (path, access, expected_disposition) in cases.items():
            status, result, detail = request_json(
                port, "POST", "/assets/resolve", {"path": path, "access": access}
            )
            if (
                status != 200
                or result is None
                or result.get("disposition") != expected_disposition
            ):
                raise RuntimeError(
                    f"native asset policy {name} expected {expected_disposition}, "
                    f"got HTTP {status}: {detail}"
                )
            policy[name] = expected_disposition
    proof = {
        "trace": trace,
        "positive": (
            "TBD/TBF.TBF opened and read through native host storage"
            if require_native_reads
            else "TBD/TBF.TBF returned to the original IOP implementation"
        ),
        "oracle_bootstrap": "SLUS_201.47 returned to the original IOP implementation",
        "policy": policy,
        "negative": {
            "sentinel": ABSENT_NATIVE_ASSET_SENTINEL,
            "observed_count": 0,
        },
    }
    (output_dir / "native-assets-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    )
    return proof


def probe_native_asset_cache(
    port: int,
    deadline: float,
    output_dir: Path,
) -> dict[str, object]:
    asset_proof = probe_native_assets(port, deadline, True, output_dir)
    snapshot = await_asset_cache(port, deadline)
    proof = build_cache_proof(asset_proof, snapshot)
    (output_dir / "native-asset-cache-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    )
    return proof


def probe_native_movie_reads(
    port: int,
    deadline: float,
    output_dir: Path,
) -> dict[str, object]:
    asset_proof = probe_native_assets(port, deadline, True, output_dir)
    trace = await_asset_trace(
        port,
        deadline,
        native_movie_reads_are_verified,
        "complete native EALOGO.PSS lifecycle",
    )
    proof = {
        "boot_asset_boundary": asset_proof,
        "movie": "MOVIES/EALOGO.PSS",
        "expected_bytes": 1_687_556,
        "trace": trace,
    }
    (output_dir / "native-movie-reads-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    )
    return proof


def probe_native_stream_reads(
    port: int,
    deadline: float,
    output_dir: Path,
) -> dict[str, object]:
    asset_proof = probe_native_assets(port, deadline, True, output_dir)
    trace = await_native_stream_reads(
        port,
        deadline,
        "native STREAMS VAG/ZIV sector reads",
    )
    proof = {
        "boot_asset_boundary": asset_proof,
        "sector_size": 2048,
        "trace": trace,
    }
    (output_dir / "native-stream-reads-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    )
    return proof
