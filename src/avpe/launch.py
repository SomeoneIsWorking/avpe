"""Launch the built PCSX2 with the AVPE private settings dir.

Windowed by default (the user's launcher). Agent/headless mode (--headless):
-nogui -batch, Null audio backend — touches neither desktop focus nor any
audio device.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from avpe.log import log

ROOT = Path(__file__).resolve().parent.parent.parent

PCSX2_BIN = ROOT / "scratch" / "build" / "bin" / "pcsx2-qt"
DATA_DIR = ROOT / "scratch" / "pcsx2-home"
# -datapath <dir> stores config under <dir>/PCSX2/
CFG_DIR = DATA_DIR / "PCSX2"
INI_PATH = CFG_DIR / "inis" / "PCSX2.ini"
LOG_PATH = ROOT / "scratch" / "logs" / "emulog.txt"


def _load_ini() -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    cur = ""
    if INI_PATH.exists():
        for raw in INI_PATH.read_text().splitlines():
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                cur = line[1:-1]
                sections.setdefault(cur, {})
            elif "=" in line and cur:
                k, _, v = line.partition("=")
                sections[cur][k.strip()] = v.strip()
    return sections


def _save_ini(sections: dict[str, dict[str, str]]) -> None:
    out = []
    for sec, kv in sections.items():
        out.append(f"[{sec}]")
        out.extend(f"{k} = {v}" for k, v in kv.items())
        out.append("")
    INI_PATH.parent.mkdir(parents=True, exist_ok=True)
    INI_PATH.write_text("\n".join(out))


def ensure_config(windowed: bool) -> None:
    """Idempotently pin the settings headless mode depends on."""
    if not INI_PATH.exists():
        INI_PATH.parent.mkdir(parents=True, exist_ok=True)
        INI_PATH.write_text(
            "[Folders]\nBios = bios\nSnapshots = snaps\nSavestates = sstates\n"
            "MemoryCards = memcards\n\n[Filenames]\nBIOS = scph39001.bin\n\n"
            "[EmuCore]\nEnablePatches = true\n")
    sections = _load_ini()
    ui = sections.setdefault("UI", {})
    # A fresh datapath gets this flagged true by PCSX2 itself; in -nogui the
    # wizard dialog then blocks startup invisibly. We always complete "setup"
    # by construction (seeded ini + symlinked BIOS).
    ui["SetupWizardIncomplete"] = "False"
    spu2 = sections.setdefault("SPU2/Output", {})
    gs = sections.setdefault("EmuCore/GS", {})
    if windowed:
        # leave whatever the user last chose; only make sure values exist
        spu2.setdefault("Backend", "Cubeb")
        gs.setdefault("Renderer", "-1")  # Auto
    else:
        spu2["Backend"] = "Null"
        spu2["OutputMuted"] = "True"
        # 13 = Software: presents via CPU blit, no Vulkan/GL surface needed
        # (Null renderer still triggers a hardware device probe which deadlocks
        # under the offscreen platform).
        gs["Renderer"] = "13"
    _save_ini(sections)


def build_argv(windowed: bool, chd: str, seconds: float | None) -> list[str]:
    argv = [str(PCSX2_BIN), "-batch"]
    if not windowed:
        argv.append("-nogui")
    argv += ["-datapath", str(DATA_DIR)]
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    argv += ["-logfile", str(LOG_PATH), "-fastboot"]
    if seconds is not None:
        argv.append("-earlyconsolelog")
    argv += ["--", chd]
    return argv


def launch(windowed: bool, chd: str, seconds: float | None) -> int:
    if not PCSX2_BIN.exists():
        log("error", "launch", f"{PCSX2_BIN} missing — build first (see docs/codemap.md)")
        return 1
    if not Path(chd).exists():
        log("error", "launch", f"game CHD missing: {chd} — fix AVPE_CHD in .env")
        return 1

    ensure_config(windowed)
    argv = build_argv(windowed, chd, seconds)
    env = os.environ.copy()
    if not windowed:
        # -nogui keeps every surface inside the hidden main window; nothing maps.
        # (QPA offscreen deadlocks VM init; Xvfb+xcb exits instantly — both
        # documented in docs/re/headless.md. Wayland+nogui is the working recipe.)
        # lucent logs to stdout; force line buffering so log files stay live
        argv = ["stdbuf", "-oL", "-eL"] + argv

    log("info", "launch", "exec: " + " ".join(argv))
    out_path = ROOT / "scratch" / "logs" / "pcsx2-stdout.log"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_fh = open(out_path, "w")
    proc = subprocess.Popen(argv, env=env, stdout=out_fh,
                            stderr=subprocess.STDOUT)

    def _terminate(signum, _frame):
        log("warn", "launch", f"signal {signum} -> terminating pcsx2 pid {proc.pid}")
        proc.terminate()
    signal.signal(signal.SIGINT, _terminate)
    signal.signal(signal.SIGTERM, _terminate)

    deadline = time.monotonic() + seconds if seconds is not None else None
    while True:
        rc = proc.poll()
        if rc is not None:
            log("info", "launch", f"pcsx2 exited rc={rc} pid={proc.pid}")
            return rc
        if deadline is not None and time.monotonic() > deadline:
            log("info", "launch", f"timeboxed run over -> terminating pid {proc.pid}")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log("warn", "launch", "SIGTERM ignored -> SIGKILL")
                proc.kill()
                proc.wait()
            return 0
        time.sleep(0.25)


if __name__ == "__main__":
    sys.exit(launch(False, os.environ.get("AVPE_CHD", ""), 20))
