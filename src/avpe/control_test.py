"""Launch and acceptance policy for the isolated AVPE control-test process."""

from collections.abc import Mapping
from pathlib import Path

EXPECTED_SERIAL = "SLUS-20147"
EXPECTED_NATIVE_ASSET = "tbd/tbf.tbf"
ABSENT_NATIVE_ASSET_SENTINEL = "__avpe_absent_asset__"


def build_argv(
    pcsx2: Path,
    data_dir: Path,
    log_path: Path,
    chd: Path,
    statefile: Path | None = None,
) -> list[str]:
    argv = [
        str(pcsx2),
        "-batch",
        "-nogui",
        "-avpe-control-test",
        "-datapath",
        str(data_dir),
        "-logfile",
        str(log_path),
        "-fastboot",
        "-earlyconsolelog",
    ]
    if statefile is not None:
        argv += ["-statefile", str(statefile.resolve())]
    argv += ["--", str(chd)]
    return argv


def build_environment(base: Mapping[str, str], port: int, nonce: str) -> dict[str, str]:
    env = dict(base)
    env.update({
        "AVPE_HTTP_PORT": str(port),
        "AVPE_CONTROL_NONCE": nonce,
        "QT_QPA_PLATFORM": "offscreen",
        "SDL_AUDIODRIVER": "dummy",
    })
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    return env


def status_is_verified(status: dict[str, object] | None, nonce: str) -> bool:
    return bool(
        status is not None
        and status.get("vm") == "Running"
        and status.get("serial") == EXPECTED_SERIAL
        and status.get("nonce") == nonce
        and status.get("host_mode") == "control-test"
        and status.get("surface") == "surfaceless"
        and status.get("audio") == "null-muted"
    )


def asset_trace_is_verified(trace: dict[str, object] | None) -> bool:
    if trace is None or trace.get("enabled") is not True \
            or trace.get("target_recognized") is not True \
            or int(trace.get("total_open_calls", 0)) <= 0 \
            or int(trace.get("dropped_unique_paths", -1)) != 0:
        return False
    paths = trace.get("paths")
    if not isinstance(paths, list):
        return False

    normalized: list[str] = []
    for entry in paths:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) \
                or int(entry.get("count", 0)) <= 0:
            return False
        normalized.append(entry["path"].replace("\\", "/").casefold())
    return (
        any(path.startswith("cdrom0:") and EXPECTED_NATIVE_ASSET in path
            for path in normalized)
        and all(ABSENT_NATIVE_ASSET_SENTINEL not in path for path in normalized)
    )
