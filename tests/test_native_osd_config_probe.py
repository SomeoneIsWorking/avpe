import unittest

from avpe.native_osd_config_probe import (
    EXPECTED_PREFIX_HEX,
    OUTPUT_ADDRESS,
    SENTINEL_HEX,
    osd_config_probe_is_verified,
)


class OsdConfigProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {"diagnostic_osd_config": {
            "address": f"0x{OUTPUT_ADDRESS:08x}",
            "seed_hex": SENTINEL_HEX,
            "output_hex": EXPECTED_PREFIX_HEX + SENTINEL_HEX[len(EXPECTED_PREFIX_HEX):],
            "written_prefix_hex": EXPECTED_PREFIX_HEX,
        }}

    def test_accepts_grounded_output(self) -> None:
        self.assertTrue(osd_config_probe_is_verified(self._trace()))

    def test_rejects_changed_output(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_osd_config"]
        assert isinstance(diagnostic, dict)
        diagnostic["output_hex"] = SENTINEL_HEX
        self.assertFalse(osd_config_probe_is_verified(trace))

    def test_rejects_changed_address(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_osd_config"]
        assert isinstance(diagnostic, dict)
        diagnostic["address"] = "0x00000000"
        self.assertFalse(osd_config_probe_is_verified(trace))
