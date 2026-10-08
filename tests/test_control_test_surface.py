import tempfile
import unittest
from pathlib import Path

from avpe.control_test import build_argv, build_environment, status_is_verified
from avpe.pcsx2_config import ensure_test_config, ini_path, load_ini


class ControlTestSurfaceTests(unittest.TestCase):
    def test_window_mode_presents_to_the_private_display(self) -> None:
        argv = build_argv(Path("pcsx2"), Path("data"), Path("log"), Path("game.chd"), window=True)
        env = build_environment({"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0"}, 1, "n", display=":7")

        self.assertIn("-avpe-control-test-window", argv)
        self.assertNotIn("-avpe-control-test", argv)
        self.assertEqual(env["DISPLAY"], ":7")
        self.assertEqual(env["QT_QPA_PLATFORM"], "xcb")
        self.assertNotIn("WAYLAND_DISPLAY", env)

    def test_default_mode_keeps_desktop_displays_out(self) -> None:
        argv = build_argv(Path("pcsx2"), Path("data"), Path("log"), Path("game.chd"))
        env = build_environment({"DISPLAY": ":0"}, 1, "n")

        self.assertIn("-avpe-control-test", argv)
        self.assertNotIn("DISPLAY", env)
        self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")

    def test_status_must_report_the_requested_surface(self) -> None:
        status = {
            "vm": "Running",
            "serial": "SLUS-20147",
            "nonce": "n",
            "host_mode": "control-test",
            "surface": "window",
            "audio": "null-muted",
        }
        self.assertTrue(status_is_verified(status, "n", "window"))
        self.assertFalse(status_is_verified(status, "n"))

    def test_window_mode_renders_with_opengl(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            bios = Path(root) / "bios.bin"
            bios.write_bytes(b"")
            ensure_test_config(Path(root) / "window", bios, window=True)
            ensure_test_config(Path(root) / "surfaceless", bios)

            window = load_ini(ini_path(Path(root) / "window"))
            surfaceless = load_ini(ini_path(Path(root) / "surfaceless"))
        self.assertEqual(window["EmuCore/GS"]["Renderer"], "12")
        self.assertEqual(surfaceless["EmuCore/GS"]["Renderer"], "13")
