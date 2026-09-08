import unittest

from avpe.native_gs_h_param_probe import (
    BUFFER_ADDRESSES,
    EXPECTED_PREFIX_HEX,
    SENTINEL_HEX,
    gs_h_param_probe_is_verified,
)


class GsHParamProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        expected_hex = EXPECTED_PREFIX_HEX + SENTINEL_HEX[len(EXPECTED_PREFIX_HEX):]
        return {"diagnostic_gs_h_param": {
            "seed_hex": SENTINEL_HEX,
            "written_prefix_hex": EXPECTED_PREFIX_HEX,
            "buffers": [
                {
                    "address": f"0x{address:08x}",
                    "output_hex": expected_hex,
                    "written_prefix_hex": EXPECTED_PREFIX_HEX,
                }
                for address in BUFFER_ADDRESSES
            ],
        }}

    def test_accepts_grounded_buffers(self) -> None:
        self.assertTrue(gs_h_param_probe_is_verified(self._trace()))

    def test_rejects_changed_buffer(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_gs_h_param"]
        assert isinstance(diagnostic, dict)
        buffers = diagnostic["buffers"]
        assert isinstance(buffers, list)
        assert isinstance(buffers[1], dict)
        buffers[1]["output_hex"] = SENTINEL_HEX
        self.assertFalse(gs_h_param_probe_is_verified(trace))

    def test_rejects_missing_buffer(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_gs_h_param"]
        assert isinstance(diagnostic, dict)
        buffers = diagnostic["buffers"]
        assert isinstance(buffers, list)
        del buffers[-1]
        self.assertFalse(gs_h_param_probe_is_verified(trace))
