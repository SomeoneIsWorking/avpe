import tempfile
import unittest
from pathlib import Path
from struct import pack

from avpe.control_test import (
    asset_trace_is_verified,
    build_argv,
    build_environment,
    find_bios,
    native_asset_reads_are_verified,
    native_movie_reads_are_verified,
    native_stream_reads_are_verified,
    oracle_asset_fallback_is_verified,
    status_is_verified,
)
from avpe.cursor import detect_cursor
from avpe.launch import (
    build_argv as build_product_argv,
    build_environment as build_product_environment,
)
from avpe.memory_card_probe import PS2_CARD_MAGIC, prepare_memory_card_probe
from avpe.pcsx2_config import (
    ensure_product_config,
    ensure_test_config,
    timing_config_identity,
)


class ControlTestPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.nonce = "different-every-run"
        self.status = {
            "vm": "Running",
            "serial": "SLUS-20147",
            "nonce": self.nonce,
            "host_mode": "control-test",
            "surface": "surfaceless",
            "audio": "null-muted",
        }

    def test_accepts_verified_runtime(self) -> None:
        self.assertTrue(status_is_verified(self.status, self.nonce))

    def test_rejects_native_surface(self) -> None:
        self.status["surface"] = "wayland"
        self.assertFalse(status_is_verified(self.status, self.nonce))

    def test_rejects_real_audio_backend(self) -> None:
        self.status["audio"] = "cubeb"
        self.assertFalse(status_is_verified(self.status, self.nonce))

    def test_rejects_another_process(self) -> None:
        self.status["nonce"] = "some-other-process"
        self.assertFalse(status_is_verified(self.status, self.nonce))

    def test_launch_contract_has_no_desktop_access_or_product_mode(self) -> None:
        argv = build_argv(
            Path("/project/build/pcsx2-qt"),
            Path("/project/test-profile"),
            Path("/project/logs/emulog.txt"),
            Path("/assets/game.chd"),
        )
        env = build_environment(
            {"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0", "UNRELATED": "kept",
             "AVPE_NATIVE_ASSET_ROOT": "/ambient/untrusted",
             "AVPE_NATIVE_ASSET_MANIFEST_SHA256": "ambient-untrusted",
             "AVPE_ASSET_BYTE_TRACE": "ambient-untrusted",
             "AVPE_LOAD_TIMING": "ambient-untrusted"},
            31234,
            self.nonce,
        )

        self.assertIn("-avpe-control-test", argv)
        self.assertIn("-nogui", argv)
        self.assertNotIn("-avpe-host", argv)
        self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")
        self.assertEqual(env["SDL_AUDIODRIVER"], "dummy")
        self.assertNotIn("DISPLAY", env)
        self.assertNotIn("WAYLAND_DISPLAY", env)
        self.assertNotIn("AVPE_NATIVE_ASSET_ROOT", env)
        self.assertNotIn("AVPE_NATIVE_ASSET_MANIFEST_SHA256", env)
        self.assertNotIn("AVPE_ASSET_BYTE_TRACE", env)
        self.assertNotIn("AVPE_LOAD_TIMING", env)
        self.assertEqual(env["UNRELATED"], "kept")

    def test_byte_trace_mode_is_explicitly_scoped(self) -> None:
        env = build_environment({}, 31234, self.nonce, asset_byte_trace_mode="native")
        self.assertEqual(env["AVPE_ASSET_BYTE_TRACE"], "native")

    def test_load_timing_mode_is_explicitly_scoped(self) -> None:
        env = build_environment({}, 31234, self.nonce,
                                asset_load_timing_mode="oracle")
        self.assertEqual(env["AVPE_LOAD_TIMING"], "oracle")

    def test_native_asset_root_requires_admission_token(self) -> None:
        with self.assertRaisesRegex(ValueError, "manifest admission token"):
            build_environment(
                {}, 31234, self.nonce, native_asset_root=Path("/validated/files")
            )

    def test_accepts_grounded_native_asset_trace(self) -> None:
        trace = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 3,
            "dropped_unique_paths": 0,
            "paths": [
                {"path": r"cdrom0:\TBD\TBF.TBF;1", "flags": 1, "count": 2},
                {"path": r"cdrom0:\MOVIES\INTRO.PSS;1", "flags": 1, "count": 1},
            ],
        }

        self.assertTrue(asset_trace_is_verified(trace))

    def test_rejects_uniform_or_contaminated_native_asset_trace(self) -> None:
        empty = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 0,
            "dropped_unique_paths": 0,
            "paths": [],
        }
        contaminated = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 2,
            "dropped_unique_paths": 0,
            "paths": [
                {"path": "cdrom0:/TBD/TBF.TBF;1", "flags": 1, "count": 1},
                {"path": "cdrom0:/__avpe_absent_asset__", "flags": 1, "count": 1},
            ],
        }

        self.assertFalse(asset_trace_is_verified(empty))
        self.assertFalse(asset_trace_is_verified(contaminated))

    def test_accepts_native_tbf_reads_with_unclaimed_bootstrap(self) -> None:
        trace = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 3,
            "dropped_unique_paths": 0,
            "paths": [
                {"path": "cdrom0:/SLUS_201.47;1", "count": 1,
                 "native_open_count": 0, "original_fallback_count": 1},
                {"path": "cdrom0:/TBD/TBF.TBF;1", "count": 2,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 2, "bytes_read": 4096},
            ],
        }

        self.assertTrue(native_asset_reads_are_verified(trace))

    def test_rejects_native_trace_that_claims_no_reads(self) -> None:
        trace = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 2,
            "dropped_unique_paths": 0,
            "paths": [
                {"path": "cdrom0:/SLUS_201.47;1", "count": 1,
                 "native_open_count": 0, "original_fallback_count": 1},
                {"path": "cdrom0:/TBD/TBF.TBF;1", "count": 1,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 0, "bytes_read": 0},
            ],
        }

        self.assertFalse(native_asset_reads_are_verified(trace))

    def test_accepts_explicit_tbf_oracle_fallback(self) -> None:
        trace = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 2,
            "dropped_unique_paths": 0,
            "paths": [
                {"path": "cdrom0:/TBD/TBF.TBF;1", "count": 2,
                 "native_open_count": 0, "original_fallback_count": 2},
            ],
        }

        self.assertTrue(oracle_asset_fallback_is_verified(trace))

    def test_rejects_tbf_oracle_trace_without_fallback(self) -> None:
        trace = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 2,
            "dropped_unique_paths": 0,
            "paths": [
                {"path": "cdrom0:/TBD/TBF.TBF;1", "count": 2,
                 "native_open_count": 0, "original_fallback_count": 0},
            ],
        }

        self.assertFalse(oracle_asset_fallback_is_verified(trace))

    def test_accepts_complete_native_movie_lifecycle(self) -> None:
        trace = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 4,
            "dropped_unique_paths": 0,
            "paths": [
                {"path": "cdrom0:/SLUS_201.47;1", "count": 1,
                 "native_open_count": 0, "original_fallback_count": 1},
                {"path": "cdrom0:/TBD/TBF.TBF;1", "count": 2,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 2, "bytes_read": 4096},
                {"path": r"cdrom0:\MOVIES\EALOGO.PSS;1", "count": 1,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 104,
                 "bytes_read": 1_687_556, "seek_calls": 2, "close_count": 1},
            ],
        }

        self.assertTrue(native_movie_reads_are_verified(trace))

    def test_rejects_incomplete_native_movie_lifecycle(self) -> None:
        trace = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 4,
            "dropped_unique_paths": 0,
            "paths": [
                {"path": "cdrom0:/SLUS_201.47;1", "count": 1,
                 "native_open_count": 0, "original_fallback_count": 1},
                {"path": "cdrom0:/TBD/TBF.TBF;1", "count": 2,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 2, "bytes_read": 4096},
                {"path": "cdrom0:/MOVIES/EALOGO.PSS;1", "count": 1,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 103,
                 "bytes_read": 1_671_168, "seek_calls": 2, "close_count": 0},
            ],
        }

        self.assertFalse(native_movie_reads_are_verified(trace))

    def test_accepts_native_stream_sector_reads(self) -> None:
        trace = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 4,
            "dropped_unique_paths": 0,
            "paths": [
                {"path": "cdrom0:/SLUS_201.47;1", "count": 1,
                 "native_open_count": 0, "original_fallback_count": 1},
                {"path": "cdrom0:/TBD/TBF.TBF;1", "count": 1,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 2, "bytes_read": 4096},
                {"path": r"cdrom0:\STREAMS\MENU01.ZIV;1", "count": 1,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 3,
                 "bytes_read": 49_152, "seek_calls": 1},
            ],
        }

        self.assertTrue(native_stream_reads_are_verified(trace))

    def test_rejects_unaligned_or_optical_stream_reads(self) -> None:
        trace = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 4,
            "dropped_unique_paths": 0,
            "paths": [
                {"path": "cdrom0:/SLUS_201.47;1", "count": 1,
                 "native_open_count": 0, "original_fallback_count": 1},
                {"path": "cdrom0:/TBD/TBF.TBF;1", "count": 1,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 2, "bytes_read": 4096},
                {"path": "cdrom0:/STREAMS/MENU01.ZIV;1", "count": 1,
                 "native_open_count": 0, "original_fallback_count": 1,
                 "read_calls": 3,
                 "bytes_read": 49_151, "seek_calls": 1},
            ],
        }

        self.assertFalse(native_stream_reads_are_verified(trace))


class ConfigurationIsolationTests(unittest.TestCase):
    def test_timing_identity_excludes_only_qt_layout_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.ini"
            second = Path(directory) / "second.ini"
            first.write_text(
                "[EmuCore/GS]\nRenderer = 13\n[UI]\n"
                "SetupWizardIncomplete = False\nMainWindowGeometry = one\n"
                "[GameListTableView]\nHeaderState = one\n"
            )
            second.write_text(
                "[EmuCore/GS]\nRenderer = 13\n[UI]\n"
                "SetupWizardIncomplete = False\nMainWindowGeometry = two\n"
                "MainWindowState = two\n[GameListTableView]\nHeaderState = two\n"
            )

            self.assertEqual(
                timing_config_identity(first), timing_config_identity(second)
            )
            second.write_text(second.read_text().replace("Renderer = 13", "Renderer = 12"))
            self.assertNotEqual(
                timing_config_identity(first), timing_config_identity(second)
            )
    def test_existing_product_ini_is_byte_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "product"
            ini = data_dir / "PCSX2" / "inis" / "PCSX2.ini"
            ini.parent.mkdir(parents=True)
            original = b"; user comment\n[Unknown]\nRepeated = one\nRepeated = two\n"
            ini.write_bytes(original)

            ensure_product_config(data_dir)

            self.assertEqual(ini.read_bytes(), original)

    def test_test_profile_does_not_touch_product_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            product_dir = root / "product"
            product_ini = product_dir / "PCSX2" / "inis" / "PCSX2.ini"
            product_ini.parent.mkdir(parents=True)
            product_ini.write_bytes(b"[User]\nChoice = preserved\n")
            bios = root / "bios.bin"
            bios.write_bytes(b"bios fixture")

            ensure_test_config(root / "test", bios)

            self.assertEqual(product_ini.read_bytes(), b"[User]\nChoice = preserved\n")

    def test_memory_card_probe_uses_an_isolated_copy_and_reports_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.ps2"
            source.write_bytes(PS2_CARD_MAGIC + bytes(512 - len(PS2_CARD_MAGIC)))
            original = source.read_bytes()

            probe = prepare_memory_card_probe(source, root / "test-profile")
            changed = bytearray(probe.working.read_bytes())
            changed[100] = 0x5A
            probe.working.write_bytes(changed)
            evidence = probe.observe()

            self.assertEqual(source.read_bytes(), original)
            self.assertNotEqual(probe.working, source)
            self.assertEqual(evidence["changed_bytes"], 1)
            self.assertEqual(evidence["first_changed_offset"], 100)
            self.assertEqual(evidence["last_changed_offset"], 100)

    def test_test_config_enables_only_the_supplied_working_card(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bios = root / "bios.bin"
            bios.write_bytes(b"bios fixture")

            ensure_test_config(root / "test", bios, "probe.ps2")
            text = (root / "test" / "PCSX2" / "inis" / "PCSX2.ini").read_text()

            self.assertIn("Slot1_Enable = true", text)
            self.assertIn("Slot1_Filename = probe.ps2", text)
            self.assertIn("Slot2_Enable = false", text)


class ProductLaunchPolicyTests(unittest.TestCase):
    def test_product_uses_the_standalone_avpe_frontend(self) -> None:
        argv = build_product_argv("/assets/game.chd")

        self.assertEqual(Path(argv[0]).name, "avpe")
        self.assertNotIn("pcsx2-qt", argv[0])
        self.assertNotIn("-avpe-host", argv)
        self.assertNotIn("-avpe-control-test", argv)
        self.assertNotIn("-nogui", argv)

    def test_product_receives_only_the_validated_native_asset_root(self) -> None:
        environment = build_product_environment(
            {"AVPE_CONTROL_NONCE": "test-only", "UNRELATED": "kept"},
            Path("/validated/avpe-native-assets-v1/files"),
            "a" * 64,
        )

        self.assertNotIn("AVPE_CONTROL_NONCE", environment)
        self.assertEqual(
            environment["AVPE_NATIVE_ASSET_ROOT"],
            "/validated/avpe-native-assets-v1/files",
        )
        self.assertEqual(
            environment["AVPE_NATIVE_ASSET_MANIFEST_SHA256"], "a" * 64
        )
        self.assertEqual(environment["UNRELATED"], "kept")


def make_bmp(width: int, height: int, gold_pixels: set[tuple[int, int]]) -> bytes:
    row_stride = (width * 3 + 3) & ~3
    pixels = bytearray(row_stride * height)
    for x, y in gold_pixels:
        stored_y = height - y - 1
        offset = stored_y * row_stride + x * 3
        pixels[offset:offset + 3] = bytes((60, 150, 210))
    header = b"BM" + pack("<IHHI", 54 + len(pixels), 0, 0, 54)
    dib = pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0,
               len(pixels), 0, 0, 0, 0)
    return header + dib + pixels


def rectangle_outline(left: int, top: int, width: int, height: int) -> set[tuple[int, int]]:
    return {
        (x, y)
        for x in range(left, left + width)
        for y in range(top, top + height)
        if x in (left, left + width - 1) or y in (top, top + height - 1)
    }


class CursorDetectorTests(unittest.TestCase):
    def test_finds_paired_gold_cursor_arcs_near_expected_position(self) -> None:
        first = rectangle_outline(42, 30, 8, 12)
        second = rectangle_outline(53, 36, 8, 12)
        unrelated = rectangle_outline(110, 70, 8, 12)
        observation = detect_cursor(
            make_bmp(160, 100, first | second | unrelated), 51.0, 39.0
        )

        self.assertIsNotNone(observation)
        assert observation is not None
        self.assertAlmostEqual(observation.x, 51.0)
        self.assertAlmostEqual(observation.y, 38.5)
        self.assertEqual(observation.pixel_count, 72)

    def test_rejects_a_single_arc(self) -> None:
        bmp = make_bmp(80, 60, rectangle_outline(20, 20, 8, 12))

        self.assertIsNone(detect_cursor(bmp, 24.0, 26.0))

    def test_rejects_malformed_snapshot(self) -> None:
        with self.assertRaisesRegex(ValueError, "not a BMP"):
            detect_cursor(b"not an image", 0.0, 0.0)


if __name__ == "__main__":
    unittest.main()
