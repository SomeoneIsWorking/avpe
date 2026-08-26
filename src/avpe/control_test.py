"""Launch and acceptance policy for the isolated AVPE control-test process."""

from collections.abc import Mapping
from pathlib import Path

EXPECTED_SERIAL = "SLUS-20147"


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
