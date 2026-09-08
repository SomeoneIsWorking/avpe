import unittest

from avpe.native_semaphore_probe import DESCRIPTOR, semaphore_probe_is_verified


class SemaphoreProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {
            "diagnostic_semaphore": {
                "descriptor_hex": DESCRIPTOR.hex(),
                "invalid_id": {
                    "poll_invalid": -1,
                    "signal_invalid": -1,
                    "i_signal_invalid": -1,
                    "wait_invalid": 0xFFFFFFFF,
                    "i_poll_invalid": -1,
                    "refer_invalid": -1,
                    "i_refer_invalid": -1,
                    "delete_invalid": -1,
                },
                "operations": {
                    "create": 10,
                    "poll_empty": -1,
                    "signal": 10,
                    "signal_full": 10,
                    "poll_available": 10,
                    "poll_after_one": 10,
                    "delete": 10,
                },
            }
        }

    def test_accepts_grounded_nonblocking_lifecycle(self) -> None:
        self.assertTrue(semaphore_probe_is_verified(self._trace()))

    def test_rejects_saturating_or_wrong_error_result(self) -> None:
        trace = self._trace()
        operations = trace["diagnostic_semaphore"]["operations"]
        assert isinstance(operations, dict)
        operations["poll_after_one"] = -1
        self.assertFalse(semaphore_probe_is_verified(trace))

        trace = self._trace()
        invalid = trace["diagnostic_semaphore"]["invalid_id"]
        assert isinstance(invalid, dict)
        invalid["wait_invalid"] = 10
        self.assertFalse(semaphore_probe_is_verified(trace))

    def test_rejects_descriptor_drift(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_semaphore"]
        assert isinstance(diagnostic, dict)
        diagnostic["descriptor_hex"] = "00"
        self.assertFalse(semaphore_probe_is_verified(trace))
