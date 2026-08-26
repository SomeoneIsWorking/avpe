"""Launch the user-facing AVPE product."""

import os
import signal
import subprocess
import sys
from pathlib import Path

from avpe.log import log
from avpe.pcsx2_config import ensure_product_config

ROOT = Path(__file__).resolve().parent.parent.parent

PCSX2_BIN = ROOT / "scratch" / "build" / "bin" / "pcsx2-qt"
DATA_DIR = ROOT / "scratch" / "pcsx2-home"
LOG_PATH = ROOT / "scratch" / "logs" / "emulog.txt"


def build_argv(chd: str) -> list[str]:
    argv = [str(PCSX2_BIN), "-batch", "-avpe-host"]
    argv += ["-datapath", str(DATA_DIR)]
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    argv += ["-logfile", str(LOG_PATH), "-fastboot"]
    argv += ["--", chd]
    return argv


def launch(chd: str) -> int:
    if not PCSX2_BIN.exists():
        log("error", "launch", f"{PCSX2_BIN} missing — run ./run.sh doctor for the exact blocker")
        return 1
    if not Path(chd).exists():
        log("error", "launch", f"game CHD missing: {chd} — fix AVPE_CHD in .env")
        return 1

    ensure_product_config(DATA_DIR)
    argv = build_argv(chd)
    env = os.environ.copy()
    env.pop("AVPE_CONTROL_NONCE", None)

    log("info", "launch", "exec: " + " ".join(argv))
    out_path = ROOT / "scratch" / "logs" / "pcsx2-stdout.log"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_fh = open(out_path, "w")
    try:
        proc = subprocess.Popen(argv, env=env, stdout=out_fh,
                                stderr=subprocess.STDOUT)
    except OSError as error:
        out_fh.close()
        log("error", "launch", f"could not start AVPE host: {error}")
        return 1

    def _terminate(signum, _frame):
        log("warn", "launch", f"signal {signum} -> terminating pcsx2 pid {proc.pid}")
        proc.terminate()
    signal.signal(signal.SIGINT, _terminate)
    signal.signal(signal.SIGTERM, _terminate)

    rc = proc.wait()
    out_fh.close()
    log("info", "launch", f"pcsx2 exited rc={rc} pid={proc.pid}")
    return rc


if __name__ == "__main__":
    sys.exit(launch(os.environ.get("AVPE_CHD", "")))
