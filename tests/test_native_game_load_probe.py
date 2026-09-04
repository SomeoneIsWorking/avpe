import json
import unittest
from unittest.mock import patch

from avpe.native_game_load_probe import (
    GAME_LOAD_MENU_VTABLE,
    GAME_LOAD_PACIFY_PROCESS_PC,
    GAME_LOAD_TRACE_ENTRY_PC,
    GAME_LOAD_TRACE_RETURN_PC,
    LOAD_CONFIRMATION_MENU_VTABLE,
    BiosGameLoadCaptureError,
    _focus_confirmation_yes,
    _prepare_game_load_confirmation,
    _require_menu,
    capture_bios_game_load_boundary,
    game_load_boundary_is_verified,
    run_game_load_phase,
)


def _valid_trace() -> dict[str, object]:
    return {
        "schema": "avpe-bios-trace-v6",
        "enabled": True,
        "capacity": 4096,
        "overflow": 0,
        "events": [
            {
                "sequence": 1,
                "kind": "import",
                "library": "ioman",
                "ordinal": 6,
                "function": "read",
                "first_arguments": [1, 2, 3, 4],
                "outcome": "hle",
                "result_valid": True,
                "result_summary": {
                    "encoding": "s32",
                    "first": 0,
                    "last": 0,
                    "min": 0,
                    "max": 0,
                    "changes": 0,
                },
                "hle_available": True,
                "debug_available": False,
                "calls": 1,
            }
        ],
        "ee_syscall_pairing": {
            "entries": 0,
            "returns": 0,
            "pending": 0,
            "sequence_errors": 0,
            "overflow": 0,
        },
        "iop_import_pairing": {
            "entries": 0,
            "returns": 0,
            "pending": 0,
            "overflow": 0,
        },
        "game_load_boundary": {
            "entry_pc": GAME_LOAD_TRACE_ENTRY_PC,
            "return_pc": GAME_LOAD_TRACE_RETURN_PC,
            "pacify_process_pc": GAME_LOAD_PACIFY_PROCESS_PC,
            "pacify_process_calls": 3,
            "complete": True,
            "succeeded": True,
            "result": 0,
            "sequence_errors": 0,
            "entry": {
                "pc": GAME_LOAD_TRACE_ENTRY_PC,
                "ee_cycle": 100,
                "iop_cycle": 40,
                "frame": 3,
                "host_time_ns": 1_000,
            },
            "return": {
                "pc": GAME_LOAD_TRACE_RETURN_PC,
                "ee_cycle": 101,
                "iop_cycle": 40,
                "frame": 3,
                "host_time_ns": 1_001,
            },
        },
    }


class NativeGameLoadProbeTests(unittest.TestCase):
    def test_boundary_requires_the_exact_successful_ordered_pair(self) -> None:
        trace = _valid_trace()
        self.assertTrue(game_load_boundary_is_verified(trace))

        trace["game_load_boundary"]["pacify_process_calls"] = 0  # type: ignore[index]
        self.assertFalse(game_load_boundary_is_verified(trace))

    def test_preparation_uses_live_load_slot_and_yes_controls(self) -> None:
        pause = {"menu": {"menu": "0x012e85a0"}}
        load_item = {"focused_item_text": "Load"}
        load_menu = {
            "menu": "0x015f04b0",
            "menu_vtable": GAME_LOAD_MENU_VTABLE,
            "focus_object": "0x015f5530",
            "focused_item_action_valid": True,
        }
        confirmation_menu = {
            "menu": "0x015f5070",
            "menu_vtable": LOAD_CONFIRMATION_MENU_VTABLE,
            "focus_object": "0x015fd7a0",
            "focused_item_action_valid": True,
        }
        with patch(
            "avpe.native_game_load_probe.probe_gameplay_pause_menu",
            return_value=pause,
        ), patch(
            "avpe.native_game_load_probe.pause_selection_rectangles",
            return_value=[{"handle": 1}],
        ), patch(
            "avpe.native_game_load_probe.focus_pause_selection",
            return_value=(load_item, [load_item]),
        ) as focus, patch(
            "avpe.native_game_load_probe.activate_focused_dispatched_menu_pointer",
            return_value={"completion": "load"},
        ), patch(
            "avpe.native_game_load_probe.await_settled_menu_state",
            return_value=(200, load_menu),
        ), patch(
            "avpe.native_game_load_probe.menu_item_text",
            return_value="Extinction 1",
        ), patch(
            "avpe.native_game_load_probe.complete_menu_action",
            return_value={"completion": "slot"},
        ), patch(
            "avpe.native_game_load_probe.await_menu_transition",
            return_value=(200, confirmation_menu),
        ), patch(
            "avpe.native_game_load_probe._focus_confirmation_yes",
            return_value={"after_text": "Yes"},
        ):
            result = _prepare_game_load_confirmation(31234, 99.0)

        self.assertEqual(result["slot_text"], "Extinction 1")
        self.assertEqual(result["confirmation_focus"], {"after_text": "Yes"})
        self.assertEqual(focus.call_args_list[0].args[-2:], ("0xCA788CFB", "Load"))

    def test_confirmation_focus_uses_the_game_owned_left_action(self) -> None:
        confirmation = {
            "menu_vtable": LOAD_CONFIRMATION_MENU_VTABLE,
            "focus_object": "0x015fd7a0",
            "focused_item_action_valid": True,
        }
        focused = {**confirmation, "focus_object": "0x015f6260"}
        with patch(
            "avpe.native_game_load_probe.menu_item_text",
            side_effect=("No", "Yes"),
        ), patch(
            "avpe.native_game_load_probe.complete_menu_action",
            return_value={"completed_menu_action_id": 4},
        ) as complete, patch(
            "avpe.native_game_load_probe.await_settled_menu_state",
            return_value=(200, focused),
        ):
            result = _focus_confirmation_yes(31234, 99.0, confirmation)

        complete.assert_called_once_with(
            31234, 99.0, "left", "BIOS phase game-load confirmation Yes focus"
        )
        self.assertEqual(result["after_text"], "Yes")

    def test_phase_exits_the_load_modal_before_capture(self) -> None:
        trace = _valid_trace()
        with patch(
            "avpe.native_game_load_probe._prepare_game_load_confirmation",
            return_value={"confirmation": "ready"},
        ), patch(
            "avpe.native_game_load_probe.start_bios_game_load_phase"
        ) as start, patch(
            "avpe.native_game_load_probe._await_mission_goals_modal",
            return_value={"source": "mission-goals-load"},
        ), patch(
            "avpe.native_game_load_probe.complete_menu_action",
            side_effect=(
                {"completed_menu_action_id": 5},
                {"execution": "synchronous"},
            ),
        ) as complete, patch(
            "avpe.native_game_load_probe.capture_bios_game_load_boundary",
            return_value=trace,
        ) as capture:
            result = run_game_load_phase(31234, 99.0)

        self.assertEqual(
            result[1:],
            (
                "gameplay_to_game_load",
                "pause_load_slot_confirm_to_cprofile_load_game",
            ),
        )
        start.assert_called_once_with(31234)
        self.assertEqual(
            complete.call_args_list[0].args,
            (31234, 99.0, "activate", "BIOS phase game-load confirmation activation"),
        )
        self.assertEqual(
            complete.call_args_list[1].args,
            (31234, 99.0, "activate", "BIOS phase game-load mission-goals exit"),
        )
        capture.assert_called_once_with(31234)
        self.assertEqual(
            trace["game_load_confirmation_activation"],
            {"completed_menu_action_id": 5},
        )

    def test_capture_retains_a_structured_timeout(self) -> None:
        trace = _valid_trace()
        trace["game_load_boundary"]["complete"] = False  # type: ignore[index]
        trace["game_load_boundary"]["return"] = None  # type: ignore[index]
        with patch(
            "avpe.native_game_load_probe.request_bytes",
            return_value=(504, json.dumps(trace).encode()),
        ), self.assertRaises(BiosGameLoadCaptureError) as raised:
            capture_bios_game_load_boundary(31234)

        self.assertEqual(raised.exception.trace, trace)

    def test_menu_discriminator_rejects_a_wrong_owner(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "GLoadGameMenu"):
            _require_menu(
                200,
                {
                    "menu_vtable": "0xdeadbeef",
                    "focus_object": "0x015f5530",
                    "focused_item_action_valid": True,
                },
                GAME_LOAD_MENU_VTABLE,
                "GLoadGameMenu",
            )


if __name__ == "__main__":
    unittest.main()
