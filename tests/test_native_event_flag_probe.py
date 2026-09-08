import unittest

from avpe.native_event_flag_probe import EXPECTED_RESULTS, event_flag_probe_is_verified


class EventFlagProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {"diagnostic_event_flag": {"invalid_id": dict(EXPECTED_RESULTS)}}

    def test_accepts_grounded_invalid_id_results(self) -> None:
        self.assertTrue(event_flag_probe_is_verified(self._trace()))

    def test_rejects_success_result(self) -> None:
        trace = self._trace()
        invalid = trace["diagnostic_event_flag"]["invalid_id"]
        assert isinstance(invalid, dict)
        invalid["poll_event_flag"] = 0
        self.assertFalse(event_flag_probe_is_verified(trace))

    def test_rejects_missing_service(self) -> None:
        trace = self._trace()
        invalid = trace["diagnostic_event_flag"]["invalid_id"]
        assert isinstance(invalid, dict)
        del invalid["i_refer_event_flag"]
        self.assertFalse(event_flag_probe_is_verified(trace))
