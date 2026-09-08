import unittest

from avpe.native_osd_config2_probe import (
    EXPECTED_PREFIX_HEX,
    EXPECTED_OUTPUT_HEX,
    OUTPUT_ADDRESS,
    OUTPUT_SIZE,
    SENTINEL_HEX,
    osd_config2_probe_is_verified,
)


class OsdConfig2ProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {"diagnostic_osd_config2": {
            "address": f"0x{OUTPUT_ADDRESS:08x}",
            "size": OUTPUT_SIZE,
            "offset": 0,
            "seed_hex": SENTINEL_HEX,
            "output_hex": EXPECTED_OUTPUT_HEX,
            "written_prefix_hex": EXPECTED_PREFIX_HEX,
        }}

    def test_accepts_grounded_output(self) -> None:
        self.assertTrue(osd_config2_probe_is_verified(self._trace()))

    def test_rejects_changed_output(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_osd_config2"]
        assert isinstance(diagnostic, dict)
        diagnostic["output_hex"] = SENTINEL_HEX
        self.assertFalse(osd_config2_probe_is_verified(trace))

    def test_rejects_changed_call_shape(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_osd_config2"]
        assert isinstance(diagnostic, dict)
        diagnostic["offset"] = 1
        self.assertFalse(osd_config2_probe_is_verified(trace))
