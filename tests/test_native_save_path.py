import unittest
from pathlib import Path

from avpe.native_save_path import resolve_native_save_path


class NativeSavePathTests(unittest.TestCase):
    def test_linux_honors_xdg_data_home(self) -> None:
        self.assertEqual(
            resolve_native_save_path(
                {"XDG_DATA_HOME": "/xdg/data"},
                system="Linux",
                home=Path("/home/test"),
            ),
            Path("/xdg/data/AVPE/avpe-saves.avpesave"),
        )

    def test_linux_defaults_to_home_data_directory(self) -> None:
        self.assertEqual(
            resolve_native_save_path({}, system="Linux", home=Path("/home/test")),
            Path("/home/test/.local/share/AVPE/avpe-saves.avpesave"),
        )

    def test_macos_uses_application_support(self) -> None:
        self.assertEqual(
            resolve_native_save_path({}, system="Darwin", home=Path("/Users/test")),
            Path("/Users/test/Library/Application Support/AVPE/avpe-saves.avpesave"),
        )

    def test_windows_prefers_local_appdata(self) -> None:
        self.assertEqual(
            resolve_native_save_path(
                {"LOCALAPPDATA": "C:/Users/test/AppData/Local", "APPDATA": "ignored"},
                system="Windows",
                home=Path("C:/Users/test"),
            ),
            Path("C:/Users/test/AppData/Local/AVPE/avpe-saves.avpesave"),
        )

    def test_unknown_platform_fails_by_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported save-path platform"):
            resolve_native_save_path({}, system="Plan9", home=Path("/home/test"))
