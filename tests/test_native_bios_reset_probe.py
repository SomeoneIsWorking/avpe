import json
import unittest
from unittest.mock import patch

from avpe.native_bios_reset_probe import BiosResetCaptureError, run_guest_reset_phase


class BiosResetProbeTests(unittest.TestCase):
    def _trace(self, *, release: bool = True) -> dict[str, object]:
        events: list[dict[str, object]] = [
            {"kind": "module", "operation": "register", "module": "ioman"},
        ]
        if release:
            events.append({"kind": "module", "operation": "release", "module": "ioman"})
        return {
            "schema": "avpe-bios-trace-v7",
            "enabled": True,
            "overflow": 0,
            "events": events,
        }

    @patch("avpe.native_bios_reset_probe.request_json")
    @patch("avpe.native_bios_reset_probe.request_bytes")
    def test_records_missing_release_as_negative(self, request_bytes, request_json) -> None:
        request_bytes.side_effect = [
            (200, b'{"started":true}'),
            (200, json.dumps(self._trace(release=False)).encode()),
        ]
        request_json.return_value = (200, {"reset": True}, "")
        trace, _phase, _operation = run_guest_reset_phase(1234)
        self.assertEqual(trace["guest_reset"]["release_count"], 0)
        self.assertFalse(trace["guest_reset"]["release_observed"])

    @patch("avpe.native_bios_reset_probe.request_json")
    @patch("avpe.native_bios_reset_probe.request_bytes")
    def test_reports_released_modules(self, request_bytes, request_json) -> None:
        request_bytes.side_effect = [
            (200, b'{"started":true}'),
            (200, json.dumps(self._trace()).encode()),
        ]
        request_json.return_value = (200, {"reset": True}, "")
        trace, phase, operation = run_guest_reset_phase(1234)
        self.assertEqual((phase, operation), ("statefile_to_guest_reset", "guest_reset_module_release"))
        self.assertEqual(trace["guest_reset"]["released_modules"], ["ioman"])
