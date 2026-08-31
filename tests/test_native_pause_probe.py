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
        dispatch = {
            "callbacks": [{
                "owner": "0x01500000",
                "member_function": ["0x00000000", "0xffffffff", "0x00125230"],
                "dispatches": 1,
            }]
        }
        with patch(
            "avpe.native_pause_probe.menu_state",
            side_effect=[(409, None, "unavailable"), (200, menu, "")],
        ), patch(
            "avpe.native_pause_probe.input_dispatch_state",
            side_effect=[(200, {"callbacks": []}, ""), (200, dispatch, "")],
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
        self.assertEqual(proof["post_pause_menu_dispatch"], dispatch["callbacks"][0])

    def test_refuses_a_non_menu_response_after_start(self) -> None:
        with patch(
            "avpe.native_pause_probe.menu_state",
            side_effect=[(409, None, "unavailable"), (500, None, "bad owner")],
        ), patch(
            "avpe.native_pause_probe.input_dispatch_state",
            return_value=(200, {"callbacks": []}, ""),
        ), patch(
            "avpe.native_pause_probe.request_json",
            return_value=(200, {"pressed": True}, ""),
        ):
            with self.assertRaisesRegex(RuntimeError, "last_status=500"):
                native_pause_probe.probe_gameplay_pause_menu(31234, time.monotonic() + 1.0)

    def test_requires_a_new_menu_callback_after_start(self) -> None:
        menu = {"menu": "0x01500000", "callback_count": 4}
        callback = {
            "owner": "0x01500000",
            "member_function": ["0x00000000", "0xffffffff", "0x00125230"],
            "dispatches": 3,
        }
        with patch(
            "avpe.native_pause_probe.menu_state",
            side_effect=[(409, None, "unavailable"), (200, menu, ""), (200, menu, "")],
        ), patch(
            "avpe.native_pause_probe.input_dispatch_state",
            side_effect=[
                (200, {"callbacks": [callback]}, ""),
                (200, {"callbacks": [callback]}, ""),
                (200, {"callbacks": [{**callback, "dispatches": 4}]}, ""),
            ],
        ), patch(
            "avpe.native_pause_probe.request_json",
            return_value=(200, {"pressed": True}, ""),
        ):
            proof = native_pause_probe.probe_gameplay_pause_menu(31234, time.monotonic() + 1.0)

        self.assertEqual(proof["post_pause_menu_dispatch"]["dispatches"], 4)
