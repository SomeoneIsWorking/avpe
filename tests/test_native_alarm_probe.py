import unittest

from avpe.native_alarm_probe import EXPECTED_RESULTS, alarm_probe_is_verified


class AlarmProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {"diagnostic_alarm": {"invalid_id": dict(EXPECTED_RESULTS)}}

    def test_accepts_grounded_result_shapes(self) -> None:
        self.assertTrue(alarm_probe_is_verified(self._trace()))

    def test_rejects_changed_result(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_alarm"]
        assert isinstance(diagnostic, dict)
        invalid = diagnostic["invalid_id"]
        assert isinstance(invalid, dict)
        invalid["release_alarm"] = -1
        self.assertFalse(alarm_probe_is_verified(trace))

    def test_rejects_missing_wrapper(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_alarm"]
        assert isinstance(diagnostic, dict)
        invalid = diagnostic["invalid_id"]
        assert isinstance(invalid, dict)
        del invalid["i_release_alarm"]
        self.assertFalse(alarm_probe_is_verified(trace))
