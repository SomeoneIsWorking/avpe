import unittest

from avpe.native_sif_query_probe import (
    EXPECTED_REGISTERS,
    sif_query_probe_is_verified,
)


class SifQueryProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {"diagnostic_sif_query": {"registers": dict(EXPECTED_REGISTERS)}}

    def test_accepts_grounded_registers(self) -> None:
        self.assertTrue(sif_query_probe_is_verified(self._trace()))

    def test_rejects_changed_register(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_sif_query"]
        assert isinstance(diagnostic, dict)
        registers = diagnostic["registers"]
        assert isinstance(registers, dict)
        registers["selector_4"] = 0
        self.assertFalse(sif_query_probe_is_verified(trace))

    def test_rejects_missing_register(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_sif_query"]
        assert isinstance(diagnostic, dict)
        registers = diagnostic["registers"]
        assert isinstance(registers, dict)
        del registers["selector_2"]
        self.assertFalse(sif_query_probe_is_verified(trace))
