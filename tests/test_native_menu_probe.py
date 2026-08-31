import time
import unittest
from unittest.mock import ANY, patch

from avpe.native_menu_probe import _complete_directional_action


class NativeMenuProbeTests(unittest.TestCase):
    def test_directional_action_uses_completed_deferred_focus(self) -> None:
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
            "avpe.native_menu_probe.menu_action",
            return_value=(202, queued, "queued"),
        ), patch(
            "avpe.native_menu_probe.await_deferred_call",
            return_value=completion,
        ) as await_call, patch(
            "avpe.native_menu_probe.menu_state",
            return_value=(200, state, ""),
        ):
            result = _complete_directional_action(31234, time.monotonic() + 1.0, "down")

        await_call.assert_called_once_with(31234, ANY, 7, "menu down")
        self.assertEqual(result["after"]["focus_object"], "0x015E0640")
        self.assertEqual(result["deferred_completion"], completion)

    def test_directional_action_preserves_synchronous_result(self) -> None:
        response = {"before": {}, "after": {"focus_object": "0x015E0640"}}
        with patch(
            "avpe.native_menu_probe.menu_action",
            return_value=(200, response, ""),
        ):
            self.assertIs(
                _complete_directional_action(31234, time.monotonic() + 1.0, "down"), response
            )
