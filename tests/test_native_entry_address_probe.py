import unittest

from avpe.native_entry_address_probe import (
    EXPECTED_RESULT,
    entry_address_probe_is_verified,
)


class EntryAddressProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {"diagnostic_entry_address": {
            "token": "0xffffffff",
            "result": EXPECTED_RESULT,
        }}

    def test_accepts_grounded_invalid_result(self) -> None:
        self.assertTrue(entry_address_probe_is_verified(self._trace()))

    def test_rejects_changed_result(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_entry_address"]
        assert isinstance(diagnostic, dict)
        diagnostic["result"] = 1
        self.assertFalse(entry_address_probe_is_verified(trace))

    def test_rejects_changed_token(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_entry_address"]
        assert isinstance(diagnostic, dict)
        diagnostic["token"] = "0x00000000"
        self.assertFalse(entry_address_probe_is_verified(trace))
