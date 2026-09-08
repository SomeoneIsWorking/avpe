import unittest

from avpe.native_cop0_probe import EXPECTED_REGISTERS, GET_COP0, cop0_probe_is_verified


class Cop0ProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {"diagnostic_cop0": {
            "function": f"0x{GET_COP0:08x}",
            "registers": {str(register): value for register, value in EXPECTED_REGISTERS.items()},
        }}

    def test_accepts_grounded_registers(self) -> None:
        self.assertTrue(cop0_probe_is_verified(self._trace()))

    def test_rejects_changed_register(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_cop0"]
        assert isinstance(diagnostic, dict)
        registers = diagnostic["registers"]
        assert isinstance(registers, dict)
        registers["12"] = 0
        self.assertFalse(cop0_probe_is_verified(trace))

    def test_rejects_missing_register(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_cop0"]
        assert isinstance(diagnostic, dict)
        registers = diagnostic["registers"]
        assert isinstance(registers, dict)
        del registers["31"]
        self.assertFalse(cop0_probe_is_verified(trace))
