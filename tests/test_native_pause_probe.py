import time
import unittest
from unittest.mock import patch

from avpe import native_pause_probe


class NativePauseProbeTests(unittest.TestCase):
    def test_rejects_an_already_active_menu(self) -> None:
        with patch(
            "avpe.native_pause_probe.menu_state",
            return_value=(200, {"menu": "0x01500000", "callback_count": 1}, ""),
        ):
            with self.assertRaisesRegex(RuntimeError, "no active menu"):
                native_pause_probe.probe_gameplay_pause_menu(31234, time.monotonic() + 1.0)

    def test_presses_start_and_requires_a_new_live_menu(self) -> None:
        menu = {"menu": "0x01500000", "callback_count": 4}
        with patch(
            "avpe.native_pause_probe.menu_state",
            side_effect=[(409, None, "unavailable"), (200, menu, "")],
        ), patch(
            "avpe.native_pause_probe.request_json",
            return_value=(200, {"pressed": True}, ""),
        ) as press:
            proof = native_pause_probe.probe_gameplay_pause_menu(31234, time.monotonic() + 1.0)

        press.assert_called_once_with(
            31234,
            "POST",
            "/input/press",
            {"mask": native_pause_probe.PAD_START_MASK, "ms": 250},
        )
        self.assertEqual(proof["input_route"], "physical-pad-start")
        self.assertEqual(proof["menu"], menu)

    def test_refuses_a_non_menu_response_after_start(self) -> None:
        with patch(
            "avpe.native_pause_probe.menu_state",
            side_effect=[(409, None, "unavailable"), (500, None, "bad owner")],
        ), patch(
            "avpe.native_pause_probe.request_json",
            return_value=(200, {"pressed": True}, ""),
        ):
            with self.assertRaisesRegex(RuntimeError, "last_status=500"):
                native_pause_probe.probe_gameplay_pause_menu(31234, time.monotonic() + 1.0)
