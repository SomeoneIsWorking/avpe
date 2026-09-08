import unittest

from avpe.native_thread_probe import thread_probe_is_verified


class ThreadProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {
            "diagnostic_thread": {
                "invalid_id": {
                    "delete_thread": -1,
                    "start_thread": -1,
                    "refer_thread_status": -1,
                    "i_refer_thread_status": -1,
                    "wakeup_thread": -1,
                    "i_wakeup_thread": -1,
                    "cancel_wakeup_thread": -1,
                    "i_cancel_wakeup_thread": -1,
                }
            }
        }

    def test_accepts_grounded_invalid_id_results(self) -> None:
        self.assertTrue(thread_probe_is_verified(self._trace()))

    def test_rejects_any_non_error_result(self) -> None:
        trace = self._trace()
        invalid = trace["diagnostic_thread"]["invalid_id"]
        assert isinstance(invalid, dict)
        invalid["wakeup_thread"] = 1
        self.assertFalse(thread_probe_is_verified(trace))

    def test_rejects_missing_service_result(self) -> None:
        trace = self._trace()
        invalid = trace["diagnostic_thread"]["invalid_id"]
        assert isinstance(invalid, dict)
        del invalid["start_thread"]
        self.assertFalse(thread_probe_is_verified(trace))

    def test_rejects_unexpected_extra_service(self) -> None:
        trace = self._trace()
        invalid = trace["diagnostic_thread"]["invalid_id"]
        assert isinstance(invalid, dict)
        invalid["sleep_thread"] = -1
        self.assertFalse(thread_probe_is_verified(trace))
