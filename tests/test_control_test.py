import json
import tempfile
import time
import unittest
from pathlib import Path
from struct import pack
from types import SimpleNamespace
from unittest.mock import call, patch

from avpe.control_test import (
    asset_trace_is_verified,
    build_argv,
    build_environment,
    find_bios,
    native_asset_reads_are_verified,
    native_movie_reads_are_verified,
    native_stream_reads_are_verified,
    oracle_asset_fallback_is_verified,
    report_json_probe,
    status_is_verified,
)
from avpe.cursor import detect_cursor
from avpe.launch import (
    build_argv as build_product_argv,
    build_environment as build_product_environment,
)
from avpe.memory_card_probe import PS2_CARD_MAGIC, prepare_memory_card_probe
from avpe.native_bios_probe import (
    BIOS_TRACE_SCHEMA,
    GAME_SAVE_TRACE_ENTRY_PC,
    GAME_SAVE_TRACE_RETURN_PC,
    PROFILE_MENU_VTABLE,
    SHELL_SHUTDOWN_MAIN_LOOP_RETURN_PC,
    SHELL_SHUTDOWN_QUIT_ENTRY_PC,
    BiosGameSaveCaptureError,
    BiosMissionCaptureError,
    MISSION_TRACE_ENTRY_PC,
    MISSION_TRACE_RETURN_PC,
    bios_trace_failure_detail,
    bios_trace_is_verified,
    capture_bios_trace,
    capture_bios_game_save_boundary,
    capture_bios_mission_boundary,
    game_save_boundary_is_verified,
    mission_boundary_is_verified,
    report_bios_trace,
    run_bios_phase,
    run_requested_bios_probe,
    shell_shutdown_boundary_is_verified,
    start_bios_mission_phase,
    start_bios_trace,
    write_bios_trace,
)
from avpe.pcsx2_config import (
    ensure_product_config,
    ensure_test_config,
    timing_config_identity,
)
from avpe.native_asset_cache_probe import cache_snapshot_is_verified
from avpe.native_menu_pointer_dispatch_probe import _move_through_dispatch, focus_dispatched_menu_pointer_at


def make_bios_import_event(sequence: int) -> dict[str, object]:
    return {
        "sequence": sequence,
        "kind": "import",
        "library": "ioman",
        "ordinal": 6,
        "function": "read",
        "first_arguments": [1, 2, 3, 4],
        "outcome": "hle",
        "result_valid": True,
        "result": 0,
        "hle_available": True,
        "debug_available": False,
        "calls": 1,
    }


def make_bios_syscall_event(sequence: int) -> dict[str, object]:
    return {
        "sequence": sequence,
        "kind": "ee_syscall",
        "number": 127,
        "name": "GetMemorySize",
        "first_arguments": [0, 0, 0, 0],
        "outcome": "direct",
        "result_valid": True,
        "result": 0,
        "result_expected": True,
        "return_expected": True,
        "calls": 1,
    }


def make_ee_syscall_pairing(
    entries: int = 0, returns: int = 0, pending: int = 0
) -> dict[str, int]:
    return {
        "entries": entries,
        "returns": returns,
        "pending": pending,
        "sequence_errors": 0,
        "overflow": 0,
    }


def make_iop_import_pairing(
    entries: int = 0, returns: int = 0, pending: int = 0
) -> dict[str, int]:
    return {
        "entries": entries,
        "returns": returns,
        "pending": pending,
        "overflow": 0,
    }


class ControlTestPolicyTests(unittest.TestCase):
    def test_dispatched_pointer_probe_waits_for_injection_and_applied_coordinates(self) -> None:
        response = {
            "deferred": True,
            "deferred_call_id": 17,
            "dispatch_pointer_id": 71,
            "pointer": "0x015FE940",
            "screen_x": 280.0,
            "screen_y": 378.0,
        }
        stale_state = {
            "pointer": "0x015FE940",
            "menu_x": 363.65,
            "menu_y": 278.40,
        }
        state = {
            "pointer": "0x015FE940",
            "menu_x": 280.0,
            "menu_y": 378.0,
        }
        with patch(
            "avpe.native_menu_pointer_dispatch_probe.request_json",
            return_value=(202, response, "queued"),
        ), patch(
            "avpe.native_menu_pointer_dispatch_probe.await_dispatched_pointer_motion",
            return_value={"injected_pointer_id": 71},
        ) as await_dispatch, patch(
            "avpe.native_menu_pointer_dispatch_probe.menu_pointer_state",
            side_effect=((200, stale_state, "stale"), (200, state, "state")),
        ):
            deadline = time.monotonic() + 1.0
            move, dispatch, observed = _move_through_dispatch(
                31234, deadline, 280.0 / 639.0, 378.0 / 447.0
            )

        self.assertEqual(move, response)
        self.assertEqual(dispatch, {"injected_pointer_id": 71})
        self.assertEqual(observed, state)
        await_dispatch.assert_called_once_with(31234, deadline, 71)

    def test_coordinate_pointer_focus_uses_the_dispatch_owner(self) -> None:
        proof_state = {"before": {"focus_object": "0x015DFB60"}}
        with patch(
            "avpe.native_menu_pointer_dispatch_probe.menu_state",
            return_value=(200, {"menu": "0x012e85a0"}, "OK"),
        ), patch(
            "avpe.native_menu_pointer_dispatch_probe._move_through_dispatch",
            return_value=({"move": True}, {"dispatch": True}, proof_state),
        ) as move:
            proof = focus_dispatched_menu_pointer_at(31234, time.monotonic() + 1.0, 500.0, 390.0)

        self.assertEqual(proof["state"], proof_state)
        self.assertEqual(move.call_args.args[2:], (500.0 / 639.0, 390.0 / 447.0))

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
             "AVPE_LOAD_TIMING": "ambient-untrusted",
             "AVPE_LOAD_TIMING_TARGET": "ambient-untrusted"},
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
        self.assertNotIn("AVPE_LOAD_TIMING_TARGET", env)
        self.assertEqual(env["UNRELATED"], "kept")

    def test_byte_trace_mode_is_explicitly_scoped(self) -> None:
        env = build_environment({}, 31234, self.nonce, asset_byte_trace_mode="native")
        self.assertEqual(env["AVPE_ASSET_BYTE_TRACE"], "native")

    def test_load_timing_mode_is_explicitly_scoped(self) -> None:
        env = build_environment({}, 31234, self.nonce,
                                asset_load_timing_mode="oracle")
        self.assertEqual(env["AVPE_LOAD_TIMING"], "oracle")

    def test_accepts_ordered_bounded_bios_trace(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [
                make_bios_import_event(1),
            ],
        }

        self.assertTrue(bios_trace_is_verified(trace))

    def test_rejects_legacy_or_ungrounded_bios_service_results(self) -> None:
        legacy = {
            "schema": "avpe-bios-trace-v2",
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [make_bios_import_event(1)],
        }
        ungrounded = {
            **legacy,
            "schema": BIOS_TRACE_SCHEMA,
            "events": [{
                **make_bios_import_event(1),
                "outcome": "oracle",
                "result_valid": False,
            }],
        }
        mismatched = {
            **ungrounded,
            "events": [{
                **make_bios_syscall_event(1),
                "outcome": "bios",
            }],
        }

        self.assertFalse(bios_trace_is_verified(legacy))
        self.assertFalse(bios_trace_is_verified(ungrounded))
        self.assertFalse(bios_trace_is_verified(mismatched))

    def test_accepts_exactly_paired_iop_oracle_return(self) -> None:
        entry = make_bios_import_event(1)
        entry.update({"outcome": "oracle", "result_valid": False})
        del entry["result"]
        entry.update(
            {"first_stack_pointer": 0x001FF000, "first_resume_pc": 0x00010200}
        )
        returned = {
            "sequence": 2,
            "kind": "iop_import_return",
            "library": "ioman",
            "ordinal": 6,
            "function": "read",
            "result_valid": True,
            "result": -5,
            "hle_available": True,
            "debug_available": False,
            "first_stack_pointer": 0x001FF000,
            "first_resume_pc": 0x00010200,
            "calls": 1,
        }
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(1, 1, 0),
            "events": [entry, returned],
        }

        self.assertTrue(bios_trace_is_verified(trace))
        returned["first_resume_pc"] += 4
        self.assertFalse(bios_trace_is_verified(trace))

        returned["first_resume_pc"] = entry["first_resume_pc"]
        returned["sequence"] = 1
        entry["sequence"] = 2
        trace["events"] = [returned, entry]
        self.assertFalse(bios_trace_is_verified(trace))

    def test_rejects_iop_oracle_pairing_counter_or_result_omission(self) -> None:
        entry = make_bios_import_event(1)
        entry.update({"outcome": "oracle", "result_valid": False})
        del entry["result"]
        entry.update(
            {"first_stack_pointer": 0x001FF000, "first_resume_pc": 0x00010200}
        )
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [entry],
        }

        self.assertFalse(bios_trace_is_verified(trace))
        trace["iop_import_pairing"] = make_iop_import_pairing(1, 0, 1)
        self.assertTrue(bios_trace_is_verified(trace))

    def test_accepts_resultless_direct_syscall(self) -> None:
        event = make_bios_syscall_event(1)
        event.update({"number": 100, "name": "FlushCache", "result_expected": False})
        event["result_valid"] = False
        del event["result"]
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [event],
        }

        self.assertTrue(bios_trace_is_verified(trace))

    def test_accepts_exactly_paired_bios_syscall_return(self) -> None:
        entry = make_bios_syscall_event(1)
        entry.update({"number": 68, "name": "WaitSema", "outcome": "bios"})
        entry["result_valid"] = False
        del entry["result"]
        returned = {
            "sequence": 2,
            "kind": "ee_syscall_return",
            "number": 68,
            "name": "WaitSema",
            "result_expected": True,
            "result_valid": True,
            "result": 0,
            "first_stack_pointer": 0x01FFF000,
            "first_resume_pc": 0x00102004,
            "calls": 1,
        }
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(1, 1, 0),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [entry, returned],
        }

        self.assertTrue(bios_trace_is_verified(trace))

    def test_accepts_exactly_paired_u64_bios_syscall_return(self) -> None:
        entry = make_bios_syscall_event(1)
        entry.update({"number": 112, "name": "GsGetIMR", "outcome": "bios"})
        entry["result_valid"] = False
        del entry["result"]
        returned = {
            "sequence": 2,
            "kind": "ee_syscall_return",
            "number": 112,
            "name": "GsGetIMR",
            "result_expected": True,
            "result_valid": True,
            "result_u64": (1 << 63) + 1,
            "first_stack_pointer": 0x01FFF000,
            "first_resume_pc": 0x00102004,
            "calls": 1,
        }
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(1, 1, 0),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [entry, returned],
        }

        self.assertTrue(bios_trace_is_verified(trace))
        returned["result"] = 1
        self.assertFalse(bios_trace_is_verified(trace))

    def test_accepts_nonreturning_bios_control_transfer(self) -> None:
        event = make_bios_syscall_event(1)
        event.update(
            {
                "number": 5,
                "name": "ResumeIntrDispatch",
                "outcome": "bios",
                "result_valid": False,
                "result_expected": False,
                "return_expected": False,
            }
        )
        del event["result"]
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [event],
        }

        self.assertTrue(bios_trace_is_verified(trace))

    def test_accepts_resultless_and_unobserved_bios_returns(self) -> None:
        void_entry = make_bios_syscall_event(1)
        void_entry.update(
            {
                "number": 100,
                "name": "FlushCache",
                "outcome": "bios",
                "result_valid": False,
                "result_expected": False,
            }
        )
        del void_entry["result"]
        void_return = {
            "sequence": 2,
            "kind": "ee_syscall_return",
            "number": 100,
            "name": "FlushCache",
            "result_expected": False,
            "result_valid": False,
            "first_stack_pointer": 0x01FFF000,
            "first_resume_pc": 0x00102004,
            "calls": 1,
        }
        unknown_entry = make_bios_syscall_event(3)
        unknown_entry.update(
            {
                "number": 3,
                "name": "RFU003",
                "outcome": "bios",
                "result_valid": False,
            }
        )
        del unknown_entry["result"]
        unknown_return = {
            "sequence": 4,
            "kind": "ee_syscall_return",
            "number": 3,
            "name": "RFU003",
            "result_expected": True,
            "result_valid": False,
            "first_stack_pointer": 0x01FFE000,
            "first_resume_pc": 0x00103004,
            "calls": 1,
        }
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(2, 2, 0),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [void_entry, void_return, unknown_entry, unknown_return],
        }

        self.assertTrue(bios_trace_is_verified(trace))

        void_return["result"] = 2
        self.assertFalse(bios_trace_is_verified(trace))

    def test_rejects_syscall_return_pairing_errors(self) -> None:
        event = make_bios_syscall_event(1)
        event.update({"number": 68, "name": "WaitSema", "outcome": "bios"})
        event["result_valid"] = False
        del event["result"]
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": {
                **make_ee_syscall_pairing(1, 0, 1),
                "sequence_errors": 1,
            },
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [event],
        }

        self.assertFalse(bios_trace_is_verified(trace))

    def test_rejects_unordered_or_overflowed_bios_trace(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [
                make_bios_import_event(2),
                make_bios_syscall_event(1),
            ],
        }
        overflowed = {**trace, "overflow": 1}

        self.assertFalse(bios_trace_is_verified(trace))
        self.assertFalse(bios_trace_is_verified(overflowed))

    def test_accepts_complete_grounded_mission_boundary(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [{"sequence": 1, "kind": "rpc"}],
            "mission_boundary": {
                "entry_pc": MISSION_TRACE_ENTRY_PC,
                "return_pc": MISSION_TRACE_RETURN_PC,
                "complete": True,
                "sequence_errors": 0,
                "entry": {"pc": MISSION_TRACE_ENTRY_PC},
                "return": {"pc": MISSION_TRACE_RETURN_PC},
            },
        }

        self.assertTrue(mission_boundary_is_verified(trace))

    def test_rejects_incomplete_or_wrong_mission_boundary(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [{"sequence": 1, "kind": "rpc"}],
            "mission_boundary": {
                "entry_pc": MISSION_TRACE_ENTRY_PC,
                "return_pc": MISSION_TRACE_RETURN_PC,
                "complete": False,
                "sequence_errors": 0,
                "entry": {"pc": MISSION_TRACE_ENTRY_PC},
                "return": {"pc": MISSION_TRACE_RETURN_PC},
            },
        }

        self.assertFalse(mission_boundary_is_verified(trace))
        trace["mission_boundary"]["return_pc"] = 0
        self.assertFalse(mission_boundary_is_verified(trace))

    def test_bios_trace_artifact_names_the_clean_boot_phase(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bios-trace.json"
            write_bios_trace(trace, output, self.status, None)
            artifact = json.loads(output.read_text())

        self.assertEqual(artifact["phase"], "clean_boot_to_running")
        self.assertEqual(artifact["trace"], trace)

    def test_bios_trace_artifact_names_the_savestate_phase(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bios-trace.json"
            statefile = Path(directory) / "title-real.p2s"
            write_bios_trace(trace, output, self.status, statefile)
            artifact = json.loads(output.read_text())

        self.assertEqual(artifact["phase"], "statefile_to_running")
        self.assertEqual(artifact["statefile"], "title-real.p2s")

    def test_bios_trace_artifact_records_explicit_phase_operation(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bios-trace.json"
            write_bios_trace(
                trace,
                output,
                self.status,
                Path(directory) / "pause-menu.p2s",
                "statefile_to_menu",
                "menu_down",
            )
            artifact = json.loads(output.read_text())

        self.assertEqual(artifact["phase"], "statefile_to_menu")
        self.assertEqual(artifact["operation"], "menu_down")

    def test_bios_trace_capture_uses_atomic_capture_route(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [
                make_bios_import_event(1),
                make_bios_syscall_event(2),
            ],
        }
        with patch(
            "avpe.native_bios_probe.request_bytes",
            return_value=(200, json.dumps(trace).encode()),
        ) as request:
            self.assertEqual(capture_bios_trace(31234), trace)

        request.assert_called_once_with(
            31234, "POST", "/bios/trace/capture-at-guest-boundary", {}, timeout=7.0
        )

    def test_bios_trace_capture_can_use_immediate_diagnostic_route(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [make_bios_import_event(1)],
        }
        with patch(
            "avpe.native_bios_probe.request_bytes",
            return_value=(200, json.dumps(trace).encode()),
        ) as request:
            self.assertEqual(capture_bios_trace(31234, at_guest_boundary=False), trace)

        request.assert_called_once_with(31234, "POST", "/bios/trace/capture", {}, timeout=7.0)

    def test_bios_trace_start_clears_and_enables_phase_sink(self) -> None:
        with patch(
            "avpe.native_bios_probe.request_bytes",
            return_value=(200, b'{"started":true}'),
        ) as request:
            start_bios_trace(31234)

        request.assert_called_once_with(31234, "POST", "/bios/trace/start", {})

    def test_save_load_bios_phase_uses_game_owned_menu_completion(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [make_bios_import_event(1)],
        }
        statefile = Path("scratch/states/pause-menu.p2s")
        isolated_state = Path("scratch/control-test/bios-phase-state.p2s")
        with patch(
            "avpe.native_bios_probe.request_json",
            side_effect=[
                (200, {"saved": True}, "saved"),
                (200, {"loaded": True}, "loaded"),
            ],
        ) as request, patch(
            "avpe.native_bios_probe.start_bios_trace"
        ) as start, patch(
            "avpe.native_bios_probe.menu_action",
            return_value=(202, {"deferred_call_id": 17}, "queued"),
        ) as menu, patch(
            "avpe.native_bios_probe.await_deferred_call"
        ) as await_call, patch(
            "avpe.native_bios_probe.capture_bios_trace", return_value=trace
        ) as capture:
            result = run_bios_phase(
                31234, 99.0, "save-load", statefile, isolated_state
            )

        self.assertEqual(
            result,
            (trace, "save_load_to_menu_action", "state_save_load_then_menu_down"),
        )
        self.assertEqual(
            request.call_args_list,
            [
                call(31234, "POST", "/state/save", {"path": str(isolated_state)}),
                call(31234, "POST", "/state/load", {"path": str(statefile)}),
            ],
        )
        start.assert_called_once_with(31234)
        menu.assert_called_once_with(31234, "down")
        await_call.assert_called_once_with(
            31234, 99.0, 17, "BIOS phase save-load menu down"
        )
        capture.assert_called_once_with(31234, at_guest_boundary=False)

    def test_game_save_boundary_requires_a_returned_zero_result(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [make_bios_import_event(1)],
            "game_save_boundary": {
                "entry_pc": GAME_SAVE_TRACE_ENTRY_PC,
                "return_pc": GAME_SAVE_TRACE_RETURN_PC,
                "pacify_process_pc": 0x00202F40,
                "pacify_process_calls": 3,
                "complete": True,
                "succeeded": True,
                "result": 0,
                "sequence_errors": 0,
                "entry": {
                    "pc": GAME_SAVE_TRACE_ENTRY_PC,
                    "ee_cycle": 100,
                    "iop_cycle": 40,
                    "frame": 3,
                    "host_time_ns": 1_000,
                },
                "return": {
                    "pc": GAME_SAVE_TRACE_RETURN_PC,
                    "ee_cycle": 101,
                    "iop_cycle": 40,
                    "frame": 3,
                    "host_time_ns": 1_001,
                },
            },
        }

        self.assertTrue(game_save_boundary_is_verified(trace))
        trace["game_save_boundary"]["result"] = 1
        self.assertFalse(game_save_boundary_is_verified(trace))

    def test_game_save_bios_phase_uses_the_native_menu_activation(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [make_bios_import_event(1)],
        }
        with patch("avpe.native_bios_probe.start_bios_game_save_phase") as start, patch(
            "avpe.native_bios_probe.menu_state",
            return_value=(200, {"focus_object": "0x00123456"}, "OK"),
        ) as state, patch(
            "avpe.native_bios_probe.menu_action",
            return_value=(202, {"deferred_call_id": 17}, "queued"),
        ) as activate, patch("avpe.native_bios_probe.await_deferred_call") as await_call, patch(
            "avpe.native_bios_probe.capture_bios_game_save_boundary",
            return_value=trace,
        ) as capture:
            result = run_bios_phase(
                31234,
                99.0,
                "game-save",
                Path("scratch/states/save-menu.p2s"),
                Path("scratch/control-test/bios-phase-state.p2s"),
            )

        self.assertEqual(
            result,
            (trace, "statefile_to_game_save", "slot_select_to_cprofile_save_game"),
        )
        start.assert_called_once_with(31234)
        state.assert_called_once_with(31234)
        activate.assert_called_once_with(31234, "activate")
        await_call.assert_called_once_with(
            31234, 99.0, 17, "BIOS phase game-save activate"
        )
        capture.assert_called_once_with(31234)

    def test_game_save_capture_retains_a_structured_timeout(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": False,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [],
            "game_save_boundary": {
                "complete": False,
                "entry": None,
                "return": None,
                "sequence_errors": 0,
            },
        }
        with patch(
            "avpe.native_bios_probe.request_bytes",
            return_value=(504, json.dumps(trace).encode()),
        ) as request, self.assertRaises(BiosGameSaveCaptureError) as raised:
            capture_bios_game_save_boundary(31234)

        self.assertEqual(raised.exception.trace, trace)
        self.assertEqual(request.call_args.args[:3], (31234, "POST", "/bios/trace/capture-game-save"))
        self.assertEqual(request.call_args.kwargs["timeout"], 22.0)

    def test_shell_shutdown_boundary_requires_exact_quit_mainloop_pair(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [make_bios_import_event(1)],
            "shell_shutdown_boundary": {
                "complete": True,
                "quit_bit_observed": True,
                "sequence_errors": 0,
                "quit_entry": {
                    "pc": SHELL_SHUTDOWN_QUIT_ENTRY_PC,
                    "ee_cycle": 100,
                    "iop_cycle": 40,
                    "frame": 3,
                    "host_time_ns": 1_000,
                },
                "main_loop_return": {
                    "pc": SHELL_SHUTDOWN_MAIN_LOOP_RETURN_PC,
                    "ee_cycle": 101,
                    "iop_cycle": 40,
                    "frame": 3,
                    "host_time_ns": 1_001,
                },
            },
        }

        self.assertTrue(shell_shutdown_boundary_is_verified(trace))
        trace["shell_shutdown_boundary"]["quit_bit_observed"] = False
        self.assertFalse(shell_shutdown_boundary_is_verified(trace))

    def test_shutdown_bios_phase_refuses_a_non_quit_menu_item(self) -> None:
        deadline = time.monotonic() + 1.0
        candidate = {"focused_item_action": "0xCA788CFB"}
        with patch("avpe.native_bios_probe.probe_gameplay_pause_menu") as pause, patch(
            "avpe.native_bios_probe._pause_selection_rectangles", return_value=[]
        ), patch(
            "avpe.native_bios_probe._complete_menu_action"
        ) as action, patch(
            "avpe.native_bios_probe._await_settled_menu_state",
            return_value=(200, candidate),
        ) as settled, patch("avpe.native_bios_probe.start_bios_shell_shutdown_phase") as start, self.assertRaisesRegex(
            RuntimeError, "QuitGame"
        ):
            run_bios_phase(
                31234, deadline, "shutdown", Path("scratch/states/mission1.p2s"),
                Path("scratch/control-test/bios-phase-state.p2s"),
            )

        pause.assert_called_once_with(31234, deadline)
        self.assertEqual(action.call_count, 1)
        self.assertEqual(settled.call_count, 2)
        start.assert_not_called()

    def test_shutdown_pointer_phase_arms_only_the_live_quit_confirmation(self) -> None:
        deadline = time.monotonic() + 1.0
        quit_row = [{"handle": 1, "xmin": 402, "ymin": 372, "xmax": 598, "ymax": 409}]
        confirmation_row = [{"handle": 2, "xmin": 402, "ymin": 212, "xmax": 598, "ymax": 249}]
        load_menu = {"state": {"before": {"focus_object": "0x015D0001"}, "focused_item_action": "0xCA788CFB"}}
        confirmation = {"state": {"before": {"focus_object": "0x015D0002"}, "focused_item_action": "0x0B36B742"}}
        trace = {"shell_shutdown_boundary": {"complete": True}}
        with patch("avpe.native_bios_probe.probe_gameplay_pause_menu", return_value={"menu": "pause"}), patch(
            "avpe.native_bios_probe._pause_selection_rectangles", side_effect=(quit_row, confirmation_row)
        ), patch(
            "avpe.native_pause_quit_probe.dispatch_dispatched_menu_pointer_at",
            side_effect=(load_menu, confirmation),
        ) as move, patch(
            "avpe.native_pause_quit_probe.menu_item_text", side_effect=("Quit", "Yes")
        ), patch(
            "avpe.native_pause_quit_probe.menu_item_action_target", side_effect=(0x142DB54, 0)
        ), patch(
            "avpe.native_bios_probe._await_settled_menu_state", return_value=(200, {"menu": "confirm"})
        ), patch(
            "avpe.native_bios_probe._menu_parent", return_value=0x015EFA70
        ), patch(
            "avpe.native_bios_probe._menu_parent_action_handler",
            return_value={"item_activated_handler": "0x002073b0"},
        ), patch(
            "avpe.native_bios_probe.start_bios_shell_shutdown_phase"
        ) as start, patch(
            "avpe.native_bios_probe.activate_focused_dispatched_menu_pointer",
            return_value={"activation": "complete"},
        ) as activate, patch(
            "avpe.native_bios_probe.capture_bios_shell_shutdown_boundary", return_value=trace
        ):
            result = run_bios_phase(
                31234, deadline, "shutdown-pointer", Path("scratch/states/mission1.p2s"),
                Path("scratch/control-test/bios-phase-state.p2s"),
            )

        self.assertEqual(result[1:], ("mission_to_pause_quit_confirmation", "pad_start_then_quit_then_confirmation"))
        self.assertEqual(move.call_args_list[0].args[2:], (500.0, 390.5))
        self.assertEqual(move.call_args_list[1].args[2:], (500.0, 230.5))
        start.assert_called_once_with(31234)
        self.assertEqual(activate.call_count, 2)
        self.assertEqual(trace["quit_confirmation"]["focused_item_text"], "Yes")
        self.assertEqual(trace["quit_menu_parent_action_handler"]["item_activated_handler"], "0x002073b0")

    def test_title_bios_phase_waits_for_title_menu_then_activates(self) -> None:
        deadline = time.monotonic() + 1.0
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [make_bios_import_event(1)],
        }
        with patch(
            "avpe.native_bios_probe._reach_title_menu"
        ) as reach, patch(
            "avpe.native_bios_probe.start_bios_trace"
        ) as start, patch(
            "avpe.native_bios_probe.menu_action",
            return_value=(202, {"deferred_call_id": 19}, "queued"),
        ) as menu, patch(
            "avpe.native_bios_probe.await_deferred_call"
        ) as await_call, patch(
            "avpe.native_bios_probe.menu_state",
            return_value=(409, {"menu": "0x00123456", "callback_count": 2}, "ambiguous"),
        ) as state, patch(
            "avpe.native_bios_probe.capture_bios_trace", return_value=trace
        ) as capture:
            result = run_bios_phase(
                31234, deadline, "title", Path("scratch/states/title-real.p2s"),
                Path("scratch/control-test/bios-phase-state.p2s"),
            )

        self.assertEqual(
            result,
            (trace, "zono_splash_to_title_menu_action", "start_then_title_activate"),
        )
        reach.assert_called_once_with(31234, deadline)
        start.assert_called_once_with(31234)
        menu.assert_called_once_with(31234, "activate")
        await_call.assert_called_once_with(31234, deadline, 19, "BIOS phase title activate")
        self.assertEqual(state.call_count, 2)
        capture.assert_called_once_with(31234, at_guest_boundary=False)
        self.assertEqual(trace["title_menu_after_action"]["status"], 409)
        self.assertEqual(trace["title_menu_after_action"]["state"]["menu"], "0x00123456")

    def test_title_profile_bios_phase_requires_profile_menu_before_second_activation(self) -> None:
        deadline = time.monotonic() + 1.0
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [make_bios_import_event(1)],
        }
        with patch(
            "avpe.native_bios_probe._reach_title_menu"
        ) as reach, patch(
            "avpe.native_bios_probe.start_bios_trace"
        ) as start, patch(
            "avpe.native_bios_probe.menu_action",
            side_effect=[
                (202, {"deferred_call_id": 19}, "queued"),
                (202, {"deferred_call_id": 20}, "queued"),
            ],
        ) as menu, patch(
            "avpe.native_bios_probe.await_deferred_call"
        ) as await_call, patch(
            "avpe.native_bios_probe.menu_state",
            side_effect=[
                (200, {"menu_vtable": "0x00342A50"}, "title"),
                (200, {"menu_vtable": PROFILE_MENU_VTABLE}, "profile"),
                (500, None, "transitional focus"),
                (409, {"menu": "0x00123456", "callback_count": 2}, "ambiguous"),
            ],
        ) as state, patch(
            "avpe.native_bios_probe.capture_bios_trace", return_value=trace
        ) as capture:
            result = run_bios_phase(
                31234, deadline, "title-profile", Path("scratch/states/title-real.p2s"),
                Path("scratch/control-test/bios-phase-state.p2s"),
            )

        self.assertEqual(
            result,
            (trace, "zono_splash_to_profile_menu_action", "start_then_title_and_profile_activate"),
        )
        reach.assert_called_once_with(31234, deadline)
        start.assert_called_once_with(31234)
        self.assertEqual(menu.call_args_list[0].args, (31234, "activate"))
        self.assertEqual(menu.call_args_list[1].args, (31234, "activate"))
        self.assertEqual(await_call.call_args_list[0].args, (31234, deadline, 19, "BIOS phase title activate"))
        self.assertEqual(await_call.call_args_list[1].args, (31234, deadline, 20, "BIOS phase profile activate"))
        self.assertEqual(state.call_count, 4)
        capture.assert_called_once_with(31234, at_guest_boundary=False)
        self.assertEqual(trace["profile_menu_after_action"]["status"], 409)

    def test_title_down_bios_phase_waits_for_the_settled_focused_action(self) -> None:
        deadline = time.monotonic() + 1.0
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [make_bios_import_event(1)],
        }
        state = {
            "menu": "0x0139AA20",
            "menu_vtable": PROFILE_MENU_VTABLE,
            "focus_object": "0x0153AA10",
            "focused_item_action": "0x95DF2577",
        }
        with patch("avpe.native_bios_probe._reach_title_menu") as reach, patch(
            "avpe.native_bios_probe.start_bios_trace"
        ) as start, patch(
            "avpe.native_bios_probe.menu_action",
            return_value=(202, {"deferred_call_id": 19}, "queued"),
        ) as menu, patch(
            "avpe.native_bios_probe.await_deferred_call"
        ) as await_call, patch(
            "avpe.native_bios_probe.menu_state",
            return_value=(200, state, "settled"),
        ) as menu_state_mock, patch(
            "avpe.native_bios_probe.capture_bios_trace", return_value=trace
        ) as capture:
            result = run_bios_phase(
                31234, deadline, "title-down", Path("scratch/states/title-real.p2s"),
                Path("scratch/control-test/bios-phase-state.p2s"),
            )

        self.assertEqual(
            result,
            (trace, "zono_splash_to_title_menu_direction", "start_then_title_down"),
        )
        reach.assert_called_once_with(31234, deadline)
        start.assert_called_once_with(31234)
        menu.assert_called_once_with(31234, "down")
        await_call.assert_called_once_with(31234, deadline, 19, "BIOS phase title down")
        menu_state_mock.assert_called_once_with(31234)
        capture.assert_called_once_with(31234, at_guest_boundary=False)
        self.assertEqual(trace["title_menu_after_down"], {"status": 200, "state": state})

    def test_title_down_activation_uses_the_settled_focused_action(self) -> None:
        deadline = time.monotonic() + 1.0
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [make_bios_import_event(1)],
        }
        down_state = {"menu": "0x01346590", "focused_item_action": "0x807F1E5F"}
        destination_state = {"menu": "0x01346910", "focused_item_action": "0xC1D97EAC"}
        with patch("avpe.native_bios_probe._reach_title_menu") as reach, patch(
            "avpe.native_bios_probe.start_bios_trace"
        ) as start, patch(
            "avpe.native_bios_probe.menu_action",
            side_effect=[
                (202, {"deferred_call_id": 19}, "queued down"),
                (202, {"deferred_call_id": 20}, "queued activate"),
            ],
        ) as menu, patch(
            "avpe.native_bios_probe.await_deferred_call"
        ) as await_call, patch(
            "avpe.native_bios_probe.menu_state",
            side_effect=[(200, down_state, "down"), (200, destination_state, "destination")],
        ) as menu_state_mock, patch(
            "avpe.native_bios_probe.capture_bios_trace", return_value=trace
        ) as capture:
            result = run_bios_phase(
                31234, deadline, "title-down-activate", Path("scratch/states/title-real.p2s"),
                Path("scratch/control-test/bios-phase-state.p2s"),
            )

        self.assertEqual(
            result,
            (trace, "zono_splash_to_title_menu_transition", "start_then_title_down_activate"),
        )
        reach.assert_called_once_with(31234, deadline)
        start.assert_called_once_with(31234)
        self.assertEqual(menu.call_args_list, [call(31234, "down"), call(31234, "activate")])
        self.assertEqual(
            await_call.call_args_list,
            [
                call(31234, deadline, 19, "BIOS phase title down"),
                call(31234, deadline, 20, "BIOS phase title down activation"),
            ],
        )
        self.assertEqual(menu_state_mock.call_count, 2)
        capture.assert_called_once_with(31234, at_guest_boundary=False)
        self.assertEqual(trace["title_menu_after_down"], {"status": 200, "state": down_state})
        self.assertEqual(
            trace["title_menu_after_down_activation"], {"status": 200, "state": destination_state}
        )

    def test_title_actions_phase_records_each_settled_game_action(self) -> None:
        deadline = time.monotonic() + 1.0
        trace = {
            "schema": BIOS_TRACE_SCHEMA, "enabled": True, "capacity": 4096, "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(), "events": [make_bios_import_event(1)],
        }
        initial_state = {"menu": "0x01346590", "focused_item_action": "0x95DF2577"}
        first_state = {"menu": "0x01346590", "focused_item_action": "0x807F1E5F"}
        second_state = {"menu": "0x01346590", "focused_item_action": "0x95DF2577"}
        with patch("avpe.native_bios_probe._reach_title_menu") as reach, patch(
            "avpe.native_bios_probe.start_bios_trace"
        ) as start, patch(
            "avpe.native_bios_probe.menu_action",
            side_effect=[(202, {"deferred_call_id": 19}, "down"), (202, {"deferred_call_id": 20}, "down")],
        ), patch("avpe.native_bios_probe.await_deferred_call") as await_call, patch(
            "avpe.native_bios_probe.menu_state",
            side_effect=[
                (200, initial_state, "initial"),
                (200, first_state, "first"),
                (200, first_state, "before-second"),
                (200, second_state, "second"),
            ],
        ), patch("avpe.native_bios_probe.capture_bios_trace", return_value=trace):
            result = run_bios_phase(
                31234, deadline, "title-actions", Path("scratch/states/title-real.p2s"),
                Path("scratch/control-test/bios-phase-state.p2s"), ("down", "down"),
            )

        self.assertEqual(result, (trace, "zono_splash_to_title_menu_actions", "down,down"))
        reach.assert_called_once_with(31234, deadline)
        start.assert_called_once_with(31234)
        self.assertEqual(await_call.call_count, 2)
        self.assertEqual(
            trace["title_menu_actions"],
            [
                {"action": "down", "status": 200, "state": first_state},
                {"action": "down", "status": 200, "state": second_state},
            ],
        )

    def test_title_profile_bios_phase_refuses_another_menu_before_second_activation(self) -> None:
        deadline = time.monotonic() + 1.0
        with patch(
            "avpe.native_bios_probe._reach_title_menu"
        ), patch(
            "avpe.native_bios_probe.start_bios_trace"
        ), patch(
            "avpe.native_bios_probe.menu_action",
            return_value=(202, {"deferred_call_id": 19}, "queued"),
        ) as menu, patch(
            "avpe.native_bios_probe.await_deferred_call"
        ), patch(
            "avpe.native_bios_probe.menu_state",
            side_effect=[
                (200, {"menu_vtable": "0x00342A50"}, "title"),
                (200, {"menu_vtable": "0x00000000"}, "another menu"),
            ],
        ), patch(
            "avpe.native_bios_probe.capture_bios_trace"
        ) as capture, self.assertRaisesRegex(RuntimeError, "grounded GProfileMenu"):
            run_bios_phase(
                31234, deadline, "title-profile", Path("scratch/states/title-real.p2s"),
                Path("scratch/control-test/bios-phase-state.p2s"),
            )

        menu.assert_called_once_with(31234, "activate")
        capture.assert_not_called()

    def test_bios_mission_phase_uses_grounded_boundary_routes(self) -> None:
        with patch(
            "avpe.native_bios_probe.request_bytes",
            side_effect=[
                (200, b'{"started":true}'),
                (200, json.dumps({
                    "schema": BIOS_TRACE_SCHEMA,
                    "enabled": True,
                    "capacity": 4096,
                    "overflow": 0,
                    "ee_syscall_pairing": make_ee_syscall_pairing(),
                    "iop_import_pairing": make_iop_import_pairing(),
                    "events": [{"sequence": 1, "kind": "rpc"}],
                    "mission_boundary": {
                        "entry_pc": MISSION_TRACE_ENTRY_PC,
                        "return_pc": MISSION_TRACE_RETURN_PC,
                        "complete": True,
                        "sequence_errors": 0,
                        "entry": {"pc": MISSION_TRACE_ENTRY_PC},
                        "return": {"pc": MISSION_TRACE_RETURN_PC},
                    },
                }).encode()),
            ],
        ) as request:
            start_bios_mission_phase(31234)
            self.assertIn("mission_boundary", capture_bios_mission_boundary(31234))

        self.assertEqual(request.call_args_list[0].args[:3],
                         (31234, "POST", "/bios/trace/start-mission"))
        self.assertEqual(request.call_args_list[1].args[:3],
                         (31234, "POST", "/bios/trace/capture-mission"))
        self.assertEqual(request.call_args_list[1].kwargs["timeout"], 122.0)

    def test_bios_mission_timeout_writes_diagnostic_and_still_fails(self) -> None:
        diagnostic = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": False,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [{"sequence": 1, "kind": "rpc"}],
            "mission_boundary": {
                "entry_pc": MISSION_TRACE_ENTRY_PC,
                "return_pc": MISSION_TRACE_RETURN_PC,
                "complete": False,
                "sequence_errors": 0,
                "entry": {"pc": MISSION_TRACE_ENTRY_PC},
                "return": None,
            },
        }
        transition = {"world": "populated"}
        args = SimpleNamespace(
            probe_bios_trace=False,
            probe_bios_phase="mission",
            statefile=None,
        )
        scratch = Path("scratch")
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            log_dir = Path(directory) / "logs"
            output = Path(directory) / "mission-timeout.json"
            with patch("avpe.native_bios_probe.await_native_stream_reads"), patch(
                "avpe.native_bios_probe.start_bios_mission_phase"
            ), patch(
                "avpe.native_bios_probe.probe_marine_m1_transition",
                return_value=transition,
            ), patch(
                "avpe.native_bios_probe.request_bytes",
                return_value=(504, json.dumps(diagnostic).encode()),
            ), patch(
                "avpe.native_bios_probe.request_json",
                return_value=(200, {"ee_pc": "0x002CDAF8"}, ""),
            ):
                trace, phase, operation, error = run_requested_bios_probe(
                    args, 31234, 100.0, log_dir
                )

            self.assertIsNotNone(error)
            self.assertEqual(trace, {**diagnostic, "mission_transition_proof": transition})
            self.assertEqual(phase, "clean_boot_to_mission")
            self.assertEqual(operation, "shell_set_next_level")
            with patch("avpe.native_bios_probe.sys.stderr"):
                self.assertFalse(
                    report_bios_trace(
                        trace,
                        output,
                        self.status,
                        log_dir,
                        None,
                        error,
                        phase,
                        operation,
                    )
                )
            artifact = json.loads(output.read_text())

        self.assertEqual(artifact["trace"], trace)
        self.assertEqual(artifact["phase"], "clean_boot_to_mission")
        self.assertEqual(artifact["operation"], "shell_set_next_level")

    def test_bios_mission_unstructured_timeout_has_no_diagnostic_trace(self) -> None:
        with patch(
            "avpe.native_bios_probe.request_bytes",
            return_value=(504, b"deadline expired"),
        ), patch(
            "avpe.native_bios_probe.request_json",
            return_value=(503, None, "unavailable"),
        ), self.assertRaises(BiosMissionCaptureError) as raised:
            capture_bios_mission_boundary(31234)

        self.assertIsNone(raised.exception.trace)

    def test_bios_trace_failure_detail_is_bounded(self) -> None:
        trace = {
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": True,
            "capacity": 4096,
            "overflow": 12786,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [{"sequence": 1, "kind": "ee_syscall"}],
        }

        detail = bios_trace_failure_detail(trace)

        self.assertIn("events=1", detail)
        self.assertIn("overflow=12786", detail)
        self.assertIn("syscall_sequence_errors=0", detail)
        self.assertNotIn("first_arguments", detail)

    def test_bios_trace_failure_detail_reports_mission_boundary(self) -> None:
        detail = bios_trace_failure_detail({
            "schema": BIOS_TRACE_SCHEMA,
            "enabled": False,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": make_ee_syscall_pairing(),
            "iop_import_pairing": make_iop_import_pairing(),
            "events": [],
            "mission_boundary": {
                "complete": False,
                "entry": {"pc": MISSION_TRACE_ENTRY_PC},
                "return": None,
                "load_error": {
                    "argument": 0,
                    "return_pc": 1521844,
                },
                "load_progress": {
                    "chunks_started": 4,
                    "chunks_completed": 3,
                },
                "sequence_errors": 0,
            },
        })

        self.assertIn("mission_complete=False", detail)
        self.assertIn("mission_entry=True", detail)
        self.assertIn("mission_return=False", detail)
        self.assertIn("mission_load_error={'argument': 0, 'return_pc': 1521844}", detail)
        self.assertIn(
            "mission_load_progress={'chunks_started': 4, 'chunks_completed': 3}",
            detail,
        )

    def test_json_probe_reporting_rejects_missing_requested_proof(self) -> None:
        self.assertTrue(
            report_json_probe(False, None, "unused", None, Path("/logs"))
        )
        self.assertFalse(
            report_json_probe(True, None, "native-camera", "not observed", Path("/logs"))
        )

    def test_build_environment_sets_mission_load_timing_target(self) -> None:
        env = build_environment(
            {},
            1234,
            "nonce",
            asset_load_timing_mode="native",
            asset_load_timing_target="mission",
        )

        self.assertEqual(env["AVPE_LOAD_TIMING"], "native")
        self.assertEqual(env["AVPE_LOAD_TIMING_TARGET"], "mission")

    def test_native_asset_root_requires_admission_token(self) -> None:
        with self.assertRaisesRegex(ValueError, "manifest admission token"):
            build_environment(
                {}, 31234, self.nonce, native_asset_root=Path("/validated/files")
            )

    def test_accepts_active_bounded_native_asset_cache_snapshot(self) -> None:
        snapshot = {
            "page_bytes": 64 * 1024,
            "maximum_pages": 512,
            "maximum_resident_bytes": 32 * 1024 * 1024,
            "hits": 4,
            "misses": 3,
            "fills": 3,
            "evictions": 1,
            "resident_pages": 2,
            "resident_bytes": 2 * 64 * 1024,
            "transient_handles": 0,
            "peak_transient_handles": 1,
        }

        self.assertTrue(
            cache_snapshot_is_verified(snapshot, require_activity=True)
        )

    def test_rejects_unbounded_or_internally_inconsistent_cache_snapshot(self) -> None:
        snapshot = {
            "page_bytes": 64 * 1024,
            "maximum_pages": 512,
            "maximum_resident_bytes": 32 * 1024 * 1024,
            "hits": 4,
            "misses": 513,
            "fills": 513,
            "evictions": 0,
            "resident_pages": 513,
            "resident_bytes": 513 * 64 * 1024,
            "transient_handles": 0,
            "peak_transient_handles": 1,
        }

        self.assertFalse(
            cache_snapshot_is_verified(snapshot, require_activity=True)
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
            "cdvd_completion": {
                "recorded": 3,
                "consumed": 3,
                "consume_misses": 2,
                "rejected_records": 0,
                "active_tokens": 0,
            },
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

    def test_rejects_stream_read_with_stale_or_rejected_completion(self) -> None:
        trace = {
            "enabled": True,
            "target_recognized": True,
            "total_open_calls": 4,
            "dropped_unique_paths": 0,
            "cdvd_completion": {
                "recorded": 3,
                "consumed": 2,
                "consume_misses": 0,
                "rejected_records": 1,
                "active_tokens": 1,
            },
            "paths": [
                {"path": "cdrom0:/SLUS_201.47;1", "count": 1,
                 "native_open_count": 0, "original_fallback_count": 1},
                {"path": "cdrom0:/TBD/TBF.TBF;1", "count": 1,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 2, "bytes_read": 4096},
                {"path": "cdrom0:/STREAMS/MENU01.ZIV;1", "count": 1,
                 "native_open_count": 1, "original_fallback_count": 0,
                 "read_calls": 3, "bytes_read": 49_152, "seek_calls": 1},
            ],
        }

        self.assertFalse(native_stream_reads_are_verified(trace))

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
            self.assertIn("EnableEE = true", text)


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
