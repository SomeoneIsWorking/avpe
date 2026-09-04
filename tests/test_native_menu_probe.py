import time
import unittest
from unittest.mock import ANY, patch

from avpe.menu_probe import (
    await_different_menu_input_dispatch,
    await_dispatched_menu_action,
    run_menu_action,
)
from avpe.native_menu_probe import _complete_directional_action


class NativeMenuProbeTests(unittest.TestCase):
    def test_menu_transition_waits_for_a_different_normal_input_owner(self) -> None:
        old_callback = {
            "owner": "0x012e85a0",
            "member_function": ["0x00000000", "0xffffffff", "0x00125230"],
            "dispatches": 4,
        }
        new_callback = {
            "owner": "0x015efeb0",
            "owner_vtable": "0x00341520",
            "member_function": ["0x00000000", "0xffffffff", "0x00125230"],
            "dispatches": 1,
        }
        completed = {"callbacks": [old_callback]}
        with patch(
            "avpe.menu_probe.input_dispatch_state",
            side_effect=[
                (200, {"callbacks": [old_callback]}, "old"),
                (200, {"callbacks": [old_callback, new_callback]}, "new"),
            ],
        ):
            owner, dispatch = await_different_menu_input_dispatch(
                31234,
                time.monotonic() + 1.0,
                "0x012e85a0",
                completed,
                "0x00341520",
            )

        self.assertEqual(owner, "0x015efeb0")
        self.assertEqual(dispatch["callbacks"][-1], new_callback)

    def test_directional_action_uses_completed_guest_input(self) -> None:
        queued = {
            "deferred": True,
            "deferred_call_id": 7,
            "before": {"focus_object": "0x015DFB60"},
        }
        completion = {"state": "completed", "stack_restored": True}
        state = {
            "focus_handle": "0x03400001",
            "focus_object": "0x015E0640",
            "focus_vtable": "0x00331610",
        }
        with patch(
            "avpe.native_menu_probe.run_menu_action",
            return_value=(queued, completion),
        ) as run_action, patch(
            "avpe.native_menu_probe.menu_state",
            return_value=(200, state, ""),
        ):
            result = _complete_directional_action(31234, time.monotonic() + 1.0, "down")

        run_action.assert_called_once_with(31234, ANY, "down")
        self.assertEqual(result["after"]["focus_object"], "0x015E0640")
        self.assertEqual(result["deferred_completion"], completion)

    def test_menu_action_waits_for_dispatched_callback(self) -> None:
        queued = {"deferred": True, "dispatch_action_id": 41}
        dispatch = {"completed_menu_action_id": 41}
        with patch(
            "avpe.menu_probe.menu_action", return_value=(202, queued, "queued")
        ), patch(
            "avpe.menu_probe.await_dispatched_menu_action", return_value=dispatch
        ) as await_dispatch:
            response, completion = run_menu_action(31234, time.monotonic() + 1.0, "down")

        self.assertEqual(response, queued)
        self.assertEqual(completion, dispatch)
        await_dispatch.assert_called_once_with(31234, ANY, 41)

    def test_dispatched_menu_action_reports_injected_callback(self) -> None:
        with patch(
            "avpe.menu_probe.input_dispatch_state",
            return_value=(200, {"completed_menu_action_id": 41}, ""),
        ):
            result = await_dispatched_menu_action(31234, time.monotonic() + 1.0, 41)

        self.assertEqual(result["completed_menu_action_id"], 41)

    def test_dispatched_menu_action_refuses_rejected_callback(self) -> None:
        with patch(
            "avpe.menu_probe.input_dispatch_state",
            return_value=(200, {"rejected_menu_action_id": 41}, ""),
        ), self.assertRaisesRegex(RuntimeError, "was rejected"):
            await_dispatched_menu_action(31234, time.monotonic() + 1.0, 41)
