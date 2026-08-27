"""Launch the user-facing AVPE product."""

from collections.abc import Mapping
import os
import signal
import subprocess
import sys
from pathlib import Path

from avpe.log import log
from avpe.native_assets import (
    MANIFEST_SHA256_ENVIRONMENT,
    NativeAssetError,
    manifest_sha256,
    provision_native_assets,
)
from avpe.pcsx2_config import ensure_product_config

ROOT = Path(__file__).resolve().parent.parent.parent

AVPE_BIN = ROOT / "scratch" / "build" / "bin" / "avpe"
DATA_DIR = ROOT / "scratch" / "pcsx2-home"
LOG_PATH = ROOT / "scratch" / "logs" / "emulog.txt"
NATIVE_ASSET_DIR = ROOT / "scratch" / "native-assets"


def build_argv(chd: str) -> list[str]:
    argv = [str(AVPE_BIN)]
    argv += ["-datapath", str(DATA_DIR)]
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    argv += ["-logfile", str(LOG_PATH), "-fastboot"]
    argv += ["--", chd]
    return argv


def build_environment(
    base: Mapping[str, str],
    native_asset_root: Path,
    native_asset_manifest_sha256: str,
) -> dict[str, str]:
    env = dict(base)
    env.pop("AVPE_CONTROL_NONCE", None)
    env["AVPE_NATIVE_ASSET_ROOT"] = str(native_asset_root.resolve())
    env[MANIFEST_SHA256_ENVIRONMENT] = native_asset_manifest_sha256
    return env


def launch(chd: str) -> int:
    if not AVPE_BIN.exists():
        log("error", "launch", f"{AVPE_BIN} missing — run ./run.sh doctor for the exact blocker")
        return 1
    if not Path(chd).exists():
        log("error", "launch", f"game CHD missing: {chd} — fix AVPE_CHD in .env")
        return 1

    try:
        native_asset_root = provision_native_assets(Path(chd), NATIVE_ASSET_DIR)
        native_asset_manifest_sha256 = manifest_sha256(native_asset_root)
    except (NativeAssetError, OSError) as error:
        log("error", "launch", f"native asset provisioning failed: {error}")
        return 1

    ensure_product_config(DATA_DIR)
    argv = build_argv(chd)
    env = build_environment(
        os.environ, native_asset_root, native_asset_manifest_sha256
    )

    log("info", "launch", "exec: " + " ".join(argv))
    out_path = ROOT / "scratch" / "logs" / "avpe-stdout.log"
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
        log("warn", "launch", f"signal {signum} -> terminating AVPE pid {proc.pid}")
        proc.terminate()
    signal.signal(signal.SIGINT, _terminate)
    signal.signal(signal.SIGTERM, _terminate)

    rc = proc.wait()
    out_fh.close()
    log("info", "launch", f"AVPE exited rc={rc} pid={proc.pid}")
    return rc


if __name__ == "__main__":
    sys.exit(launch(os.environ.get("AVPE_CHD", "")))
