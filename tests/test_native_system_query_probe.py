import unittest

from avpe.native_system_query_probe import EXPECTED_RESULTS, system_query_probe_is_verified


class SystemQueryProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {"diagnostic_system_query": {
            "results": dict(EXPECTED_RESULTS),
            "void_queries": ["ps_mode"],
        }}

    def test_accepts_grounded_results(self) -> None:
        self.assertTrue(system_query_probe_is_verified(self._trace()))

    def test_rejects_changed_result(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_system_query"]
        assert isinstance(diagnostic, dict)
        results = diagnostic["results"]
        assert isinstance(results, dict)
        results["get_memory_size"] = 0
        self.assertFalse(system_query_probe_is_verified(trace))

    def test_rejects_missing_query(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_system_query"]
        assert isinstance(diagnostic, dict)
        results = diagnostic["results"]
        assert isinstance(results, dict)
        del results["machine_type"]
        self.assertFalse(system_query_probe_is_verified(trace))

    def test_rejects_missing_void_query(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_system_query"]
        assert isinstance(diagnostic, dict)
        diagnostic["void_queries"] = []
        self.assertFalse(system_query_probe_is_verified(trace))
