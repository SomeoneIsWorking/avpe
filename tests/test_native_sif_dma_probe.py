import unittest

from avpe.native_sif_dma_probe import EXPECTED_RESULT, sif_dma_probe_is_verified


class SifDmaProbeValidationTests(unittest.TestCase):
    def _trace(self) -> dict[str, object]:
        return {"diagnostic_sif_dma": {
            "token": "0xffffffff",
            "result": EXPECTED_RESULT,
        }}

    def test_accepts_grounded_invalid_result(self) -> None:
        self.assertTrue(sif_dma_probe_is_verified(self._trace()))

    def test_rejects_changed_result(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_sif_dma"]
        assert isinstance(diagnostic, dict)
        diagnostic["result"] = 0
        self.assertFalse(sif_dma_probe_is_verified(trace))

    def test_rejects_changed_token(self) -> None:
        trace = self._trace()
        diagnostic = trace["diagnostic_sif_dma"]
        assert isinstance(diagnostic, dict)
        diagnostic["token"] = "0x00000000"
        self.assertFalse(sif_dma_probe_is_verified(trace))
