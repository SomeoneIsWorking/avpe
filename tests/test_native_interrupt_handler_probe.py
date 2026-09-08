import unittest

from avpe.native_interrupt_handler_probe import interrupt_handler_probe_is_captured


class InterruptHandlerProbeValidationTests(unittest.TestCase):
    def test_accepts_complete_result_capture(self) -> None:
        self.assertTrue(interrupt_handler_probe_is_captured({
            "diagnostic_interrupt_handler": {"invalid_id": {
                "enable_intc": 0xFFFFFFFF, "i_enable_intc": 0xFFFFFFFF,
                "disable_intc": 0xFFFFFFFF, "i_disable_intc": 0xFFFFFFFF,
            }}
        }))

    def test_rejects_missing_wrapper(self) -> None:
        self.assertFalse(interrupt_handler_probe_is_captured({
            "diagnostic_interrupt_handler": {"invalid_id": {"enable_intc": -1}}
        }))

    def test_rejects_unexpected_result(self) -> None:
        self.assertFalse(interrupt_handler_probe_is_captured({
            "diagnostic_interrupt_handler": {"invalid_id": {
                "enable_intc": 0, "i_enable_intc": 0xFFFFFFFF,
                "disable_intc": 0xFFFFFFFF, "i_disable_intc": 0xFFFFFFFF,
            }}
        }))
