"""A private Xvfb display for windowed control tests, and captures of what it shows."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

INSTALL_HINT = (
    "Fedora: sudo dnf install xorg-x11-server-Xvfb ImageMagick; "
    "Debian/Ubuntu: sudo apt install xvfb imagemagick"
)


class VirtualDisplay:
    """Owns one Xvfb server; stop() ends it by its own PID."""

    def __init__(self, width: int = 1280, height: int = 960) -> None:
        xvfb = shutil.which("Xvfb")
        capture = shutil.which("import")
        if xvfb is None or capture is None:
            raise RuntimeError(f"windowed control tests need Xvfb and ImageMagick ({INSTALL_HINT})")
        self._xvfb = xvfb
        self._capture = capture
        self._size = f"{width}x{height}x24"
        self._proc: subprocess.Popen[bytes] | None = None
        self.name = ""

    def start(self) -> str:
        read_fd, write_fd = os.pipe()
        try:
            self._proc = subprocess.Popen(
                [self._xvfb, "-displayfd", str(write_fd), "-screen", "0", self._size,
                 "-nolisten", "tcp"],
                pass_fds=(write_fd,),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        finally:
            os.close(write_fd)
        with os.fdopen(read_fd, "rb") as announced:
            number = announced.readline().strip()
        if not number.isdigit():
            self.stop()
            raise RuntimeError("Xvfb did not announce a display number")
        self.name = f":{number.decode()}"
        return self.name

    def capture(self, path: Path) -> Path:
        subprocess.run(
            [self._capture, "-display", self.name, "-window", "root", str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return path

    def stop(self) -> None:
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        self._proc = None
