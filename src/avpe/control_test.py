"""Launch and acceptance policy for the isolated AVPE control-test process."""

from collections.abc import Mapping
from pathlib import Path

EXPECTED_SERIAL = "SLUS-20147"
EXPECTED_NATIVE_ASSET = "tbd/tbf.tbf"
EXPECTED_NATIVE_MOVIE = "movies/ealogo.pss"
EXPECTED_NATIVE_MOVIE_SIZE = 1_687_556
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


def build_environment(
    base: Mapping[str, str],
    port: int,
    nonce: str,
    native_asset_root: Path | None = None,
) -> dict[str, str]:
    env = dict(base)
    env.update({
        "AVPE_HTTP_PORT": str(port),
        "AVPE_CONTROL_NONCE": nonce,
        "QT_QPA_PLATFORM": "offscreen",
        "SDL_AUDIODRIVER": "dummy",
    })
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    if native_asset_root is None:
        env.pop("AVPE_NATIVE_ASSET_ROOT", None)
    else:
        env["AVPE_NATIVE_ASSET_ROOT"] = str(native_asset_root.resolve())
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


def native_asset_reads_are_verified(trace: dict[str, object] | None) -> bool:
    if not asset_trace_is_verified(trace):
        return False
    assert trace is not None
    paths = trace["paths"]
    assert isinstance(paths, list)
    tbf = next((
        entry for entry in paths
        if isinstance(entry, dict)
        and isinstance(entry.get("path"), str)
        and EXPECTED_NATIVE_ASSET in entry["path"].replace("\\", "/").casefold()
    ), None)
    bootstrap = next((
        entry for entry in paths
        if isinstance(entry, dict)
        and isinstance(entry.get("path"), str)
        and "slus_201.47" in entry["path"].casefold()
    ), None)
    return bool(
        isinstance(tbf, dict)
        and int(tbf.get("native_open_count", 0)) > 0
        and int(tbf.get("read_calls", 0)) > 0
        and int(tbf.get("bytes_read", 0)) > 0
        and isinstance(bootstrap, dict)
        and int(bootstrap.get("native_open_count", 0)) == 0
    )


def native_movie_reads_are_verified(trace: dict[str, object] | None) -> bool:
    if not native_asset_reads_are_verified(trace):
        return False
    assert trace is not None
    paths = trace["paths"]
    assert isinstance(paths, list)
    movie = next((
        entry for entry in paths
        if isinstance(entry, dict)
        and isinstance(entry.get("path"), str)
        and EXPECTED_NATIVE_MOVIE in entry["path"].replace("\\", "/").casefold()
    ), None)
    return bool(
        isinstance(movie, dict)
        and int(movie.get("native_open_count", 0)) == 1
        and int(movie.get("read_calls", 0)) > 0
        and int(movie.get("bytes_read", 0)) == EXPECTED_NATIVE_MOVIE_SIZE
        and int(movie.get("seek_calls", 0)) == 2
        and int(movie.get("close_count", 0)) == 1
    )


def native_stream_reads_are_verified(trace: dict[str, object] | None) -> bool:
    if not native_asset_reads_are_verified(trace):
        return False
    assert trace is not None
    paths = trace["paths"]
    assert isinstance(paths, list)
    for entry in paths:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        normalized = entry["path"].replace("\\", "/").casefold()
        bytes_read = int(entry.get("bytes_read", 0))
        if (
            "/streams/" in normalized
            and normalized.removesuffix(";1").endswith((".vag", ".ziv"))
            and int(entry.get("native_open_count", 0)) > 0
            and int(entry.get("read_calls", 0)) > 0
            and bytes_read > 0
            and bytes_read % 2048 == 0
            and int(entry.get("seek_calls", 0)) > 0
        ):
            return True
    return False
