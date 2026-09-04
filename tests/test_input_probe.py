import time
import unittest
from unittest.mock import patch

from avpe import input_probe


class InputProbeTests(unittest.TestCase):
    def test_press_requires_active_and_released_shipping_states(self) -> None:
        states = [
            (200, {"inject_inputs": "0000", "inject_wire": "0000", "transfers": 10}, ""),
            (200, {"inject_inputs": "0200", "inject_wire": "0800", "transfers": 11}, ""),
            (200, {"inject_inputs": "0000", "inject_wire": "0000", "transfers": 12}, ""),
        ]
        with patch(
            "avpe.input_probe.button_injection_state", side_effect=states
        ), patch(
            "avpe.input_probe.request_json",
            return_value=(200, {"pressed": True}, ""),
        ) as request:
            proof = input_probe.press_buttons(
                31234, time.monotonic() + 1.0, 1 << 9
            )

        request.assert_called_once_with(
            31234, "POST", "/input/press", {"mask": 1 << 9, "ms": 250}
        )
        self.assertEqual(proof["active"]["inject_inputs"], "0200")
        self.assertEqual(proof["active"]["inject_wire"], "0800")
        self.assertEqual(proof["released"]["inject_inputs"], "0000")
        self.assertEqual(proof["released"]["inject_wire"], "0000")

    def test_press_refuses_an_existing_injection(self) -> None:
        with patch(
            "avpe.input_probe.button_injection_state",
            return_value=(200, {"inject_inputs": "0040", "inject_wire": "0040"}, ""),
        ):
            with self.assertRaisesRegex(RuntimeError, "already active"):
                input_probe.press_buttons(31234, time.monotonic() + 1.0, 1 << 9)

    def test_press_refuses_an_unbounded_duration(self) -> None:
        with self.assertRaisesRegex(ValueError, "duration"):
            input_probe.press_buttons(
                31234, time.monotonic() + 1.0, 1 << 9, duration_ms=60_001
            )

    def test_press_reports_a_missing_active_observation(self) -> None:
        with patch(
            "avpe.input_probe.button_injection_state",
            return_value=(200, {"inject_inputs": "0000", "inject_wire": "0000"}, ""),
        ), patch(
            "avpe.input_probe.request_json",
            return_value=(200, {"pressed": True}, ""),
        ), patch("avpe.input_probe.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "both active and released"):
                input_probe.press_buttons(31234, time.monotonic() - 1.0, 1 << 9)

    def test_press_rejects_a_different_active_mask(self) -> None:
        with patch(
            "avpe.input_probe.button_injection_state",
            side_effect=[
                (200, {"inject_inputs": "0000", "inject_wire": "0000"}, ""),
                (200, {"inject_inputs": "0800", "inject_wire": "0200"}, ""),
            ],
        ), patch(
            "avpe.input_probe.request_json",
            return_value=(200, {"pressed": True}, ""),
        ):
            with self.assertRaisesRegex(RuntimeError, "different active mask"):
                input_probe.press_buttons(31234, time.monotonic() + 1.0, 1 << 9)

    def test_state_rejects_a_non_hex_injection_mask(self) -> None:
        with patch(
            "avpe.input_probe.request_bytes",
            return_value=(200, b'{"inject_inputs":"nope","inject_wire":"0000"}'),
        ):
            status, state, detail = input_probe.button_injection_state(31234)

        self.assertEqual(status, 200)
        self.assertIsNone(state)
        self.assertEqual(detail, '{"inject_inputs":"nope","inject_wire":"0000"}')
