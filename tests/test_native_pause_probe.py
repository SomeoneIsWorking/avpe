import struct
import time
import unittest
from unittest.mock import patch

from avpe import native_pause_probe


class NativePauseProbeTests(unittest.TestCase):
    def test_waits_for_guest_pause_timer_before_admission(self) -> None:
        handler = 0x014E2940
        game_times = iter((5.0, 50.125))

        def guest_buffer(_port: int, address: int, _size: int) -> str:
            if address == native_pause_probe.PAUSE_HANDLER_SINGLETON:
                return struct.pack("<I", handler).hex()
            if address == handler:
                return struct.pack("<I", native_pause_probe.PAUSE_HANDLER_VTABLE).hex()
            if address == native_pause_probe.GAME_TIME:
                return struct.pack("<f", next(game_times)).hex()
            if address == handler + native_pause_probe.PAUSE_ENABLED_AT_OFFSET:
                return struct.pack("<f", 50.0).hex()
            raise AssertionError(f"unexpected guest address: 0x{address:08x}")

        with patch("avpe.native_pause_probe.read_guest_buffer", side_effect=guest_buffer):
            with patch("avpe.native_pause_probe.time.sleep") as sleep:
                initial, admitted = native_pause_probe._await_pause_readiness(
                    31234, time.monotonic() + 1.0
                )
        self.assertEqual(initial, {"game_time": 5.0, "enabled_at": 50.0, "ready": False})
        self.assertEqual(
            admitted, {"game_time": 50.125, "enabled_at": 50.0, "ready": True}
        )
        sleep.assert_called_once_with(0.05)

    def test_refuses_to_press_when_guest_pause_timer_is_not_ready(self) -> None:
        with patch(
            "avpe.native_pause_probe.menu_state", return_value=(409, None, "unavailable")
        ), patch(
            "avpe.native_pause_probe.input_dispatch_state",
            return_value=(200, {"callbacks": []}, ""),
        ), patch(
            "avpe.native_pause_probe._pause_readiness",
            return_value={"game_time": 5.0, "enabled_at": 50.0, "ready": False},
        ), patch(
            "avpe.native_pause_probe.time.monotonic", side_effect=(0.0, 1.0)
        ), patch("avpe.native_pause_probe.time.sleep") as sleep, patch(
            "avpe.native_pause_probe.press_buttons"
        ) as press:
            with self.assertRaisesRegex(RuntimeError, "did not admit Pause"):
                native_pause_probe.probe_gameplay_pause_menu(31234, 0.5)
        press.assert_not_called()
        sleep.assert_called_once_with(0.05)

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
            "avpe.native_pause_probe.press_buttons",
            return_value={"request": {"pressed": True}},
        ) as press, patch(
            "avpe.native_pause_probe._await_pause_readiness",
            return_value=({"ready": False}, {"ready": True}),
        ):
            proof = native_pause_probe.probe_gameplay_pause_menu(31234, time.monotonic() + 1.0)

        press.assert_called_once_with(
            31234, unittest.mock.ANY, native_pause_probe.PAD_START_MASK
        )
        self.assertEqual(proof["input_route"], "physical-pad-start")
        self.assertEqual(proof["pause_readiness"]["admitted"], {"ready": True})
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
            "avpe.native_pause_probe.press_buttons",
            return_value={"request": {"pressed": True}},
        ), patch(
            "avpe.native_pause_probe._await_pause_readiness",
            return_value=({"ready": True}, {"ready": True}),
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
            "avpe.native_pause_probe.press_buttons",
            return_value={"request": {"pressed": True}},
        ), patch(
            "avpe.native_pause_probe._await_pause_readiness",
            return_value=({"ready": True}, {"ready": True}),
        ):
            proof = native_pause_probe.probe_gameplay_pause_menu(31234, time.monotonic() + 1.0)

        self.assertEqual(proof["post_pause_menu_dispatch"]["dispatches"], 4)
