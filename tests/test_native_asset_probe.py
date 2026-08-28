import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import ANY, call, patch

from avpe import native_asset_probe


class NativeAssetProbeTests(unittest.TestCase):
    @staticmethod
    def _snapshot() -> dict[str, object]:
        return {
            "descriptors": [
                {"fd": 17, "path": "cdrom0:/MOVIES/INTRO.PSS;1", "cursor": 4096}
            ],
            "cdvd_mappings": [
                {
                    "path": "cdrom0:/STREAMS/MENU01.ZIV;1",
                    "base_lsn": 0x70000000,
                    "size": 49152,
                    "sha256": "a" * 64,
                }
            ],
            "next_lsn": 0x70000018,
            "cdvd_completion_active_tokens": 0,
        }

    @staticmethod
    def _stream_trace(
        reads: int, opens: int = 1, recorded: int = 0
    ) -> dict[str, object]:
        return {
            "cdvd_completion": {
                "recorded": recorded,
                "consumed": recorded,
                "rejected_records": 0,
                "active_tokens": 0,
            },
            "paths": [
                {
                    "path": "cdrom0:/STREAMS/MENU01.ZIV;1",
                    "native_open_count": opens,
                    "original_fallback_count": 0,
                    "read_calls": reads,
                    "bytes_read": reads * 2048,
                }
            ],
        }

    def test_asset_trace_polling_uses_shipping_verifier(self) -> None:
        trace = {"enabled": True, "paths": []}
        verifier_calls: list[dict[str, object] | None] = []

        def verifier(candidate: dict[str, object] | None) -> bool:
            verifier_calls.append(candidate)
            return candidate == trace

        with patch.object(
            native_asset_probe,
            "request_bytes",
            return_value=(200, json.dumps(trace).encode()),
        ) as request:
            result = native_asset_probe.await_asset_trace(
                28447, time.monotonic() + 1.0, verifier, "asset trace"
            )

        self.assertEqual(result, trace)
        self.assertEqual(verifier_calls, [trace])
        request.assert_called_once_with(28447, "GET", "/assets/opens")

    def test_guest_reset_requires_new_epoch_and_empty_transient_state(self) -> None:
        response = {
            "reset": True,
            "before": {
                "guest_reset_epoch": 4,
                "descriptors": [{"fd": 17}],
                "cdvd_mappings": [{"path": "MENU01.ZIV"}],
                "cdvd_completion_active_tokens": 0,
            },
            "after": {
                "guest_reset_epoch": 5,
                "descriptors": [],
                "cdvd_mappings": [],
                "cdvd_completion_active_tokens": 0,
            },
            "cache": {
                "resident_pages": 4,
                "resident_bytes": 262144,
                "transient_handles": 0,
            },
        }
        with patch.object(
            native_asset_probe,
            "request_json",
            return_value=(200, response, ""),
        ) as request:
            result = native_asset_probe._request_guest_reset(28447)

        self.assertEqual(result, response)
        request.assert_called_once_with(28447, "POST", "/guest/reset", {})

    def test_guest_reset_rejects_retained_descriptors(self) -> None:
        response = {
            "reset": True,
            "before": {"guest_reset_epoch": 4},
            "after": {
                "guest_reset_epoch": 5,
                "descriptors": [{"fd": 17}],
                "cdvd_mappings": [],
                "cdvd_completion_active_tokens": 0,
            },
            "cache": {"resident_pages": 0, "resident_bytes": 0, "transient_handles": 0},
        }
        with patch.object(
            native_asset_probe, "request_json", return_value=(200, response, "")
        ):
            with self.assertRaisesRegex(RuntimeError, "retained active native state"):
                native_asset_probe._request_guest_reset(28447)

    def test_native_asset_probe_preserves_policy_and_proof_artifact(self) -> None:
        trace = {"enabled": True, "paths": [{"path": "TBD/TBF.TBF"}]}

        def resolve(
            _port: int,
            _method: str,
            _path: str,
            payload: dict[str, str],
        ) -> tuple[int, dict[str, object], str]:
            guest_path = payload["path"]
            access = payload["access"]
            if access == "write" or "../" in guest_path:
                disposition = "refused-access"
            elif "__AVPE_MISSING__" in guest_path:
                disposition = "refused-missing"
            elif "SLUS_201.47" in guest_path:
                disposition = "unhandled"
            else:
                disposition = "native-file"
            return 200, {"disposition": disposition}, ""

        with tempfile.TemporaryDirectory() as directory, patch.object(
            native_asset_probe, "await_asset_trace", return_value=trace
        ), patch.object(native_asset_probe, "request_json", side_effect=resolve):
            output_dir = Path(directory)
            proof = native_asset_probe.probe_native_assets(
                28447, time.monotonic() + 1.0, True, output_dir
            )
            written = json.loads(
                (output_dir / "native-assets-proof.json").read_text()
            )

        self.assertEqual(written, proof)
        self.assertEqual(proof["trace"], trace)
        self.assertEqual(
            proof["policy"],
            {
                "native": "native-file",
                "write": "refused-access",
                "traversal": "refused-access",
                "missing": "refused-missing",
                "bootstrap": "unhandled",
            },
        )

    def test_cache_probe_composes_existing_cache_policy(self) -> None:
        asset_proof = {"trace": "asset"}
        cache = {"resident_pages": 2}
        expected = {
            "boot_asset_boundary": asset_proof,
            "cache": cache,
            "bounded": True,
        }

        with tempfile.TemporaryDirectory() as directory, patch.object(
            native_asset_probe, "probe_native_assets", return_value=asset_proof
        ) as asset_probe, patch.object(
            native_asset_probe, "await_asset_cache", return_value=cache
        ), patch.object(
            native_asset_probe, "build_cache_proof", return_value=expected
        ):
            output_dir = Path(directory)
            proof = native_asset_probe.probe_native_asset_cache(
                28447, time.monotonic() + 1.0, output_dir
            )
            written = json.loads(
                (output_dir / "native-asset-cache-proof.json").read_text()
            )

        self.assertEqual(written, expected)
        self.assertEqual(proof, expected)
        asset_probe.assert_called_once_with(28447, ANY, True, output_dir)

    def test_byte_trace_and_load_timing_poll_their_exact_routes(self) -> None:
        byte_trace = {"mode": "native"}
        timing = {"mode": "native"}
        responses = [
            (200, json.dumps(byte_trace).encode()),
            (200, json.dumps(timing).encode()),
        ]

        with patch.object(
            native_asset_probe, "request_bytes", side_effect=responses
        ) as request, patch.object(
            native_asset_probe, "asset_byte_trace_is_ready", return_value=True
        ), patch.object(
            native_asset_probe, "load_timing_sample_is_ready", return_value=True
        ):
            observed_trace = native_asset_probe.await_asset_byte_trace(
                28447, time.monotonic() + 1.0, "native"
            )
            observed_timing = native_asset_probe.await_load_timing(
                28447, time.monotonic() + 1.0, "native"
            )

        self.assertEqual(observed_trace, byte_trace)
        self.assertEqual(observed_timing, timing)
        self.assertEqual(
            request.call_args_list,
            [
                call(28447, "GET", "/assets/byte-trace"),
                call(28447, "GET", "/assets/load-timing"),
            ],
        )

    def test_atomic_state_snapshot_rejects_transient_completion(self) -> None:
        snapshot = self._snapshot()
        snapshot["cdvd_completion_active_tokens"] = 1

        with self.assertRaisesRegex(RuntimeError, "transient native completion"):
            native_asset_probe._state_snapshot(
                {"saved": True, "native_asset_state": snapshot},
                "saved",
                "state save",
            )

    def test_post_load_status_requires_surfaceless_running_target(self) -> None:
        invalid = {
            "vm": "Paused",
            "host_mode": "control-test",
            "surface": "surfaceless",
            "audio": "null-muted",
        }
        with patch.object(
            native_asset_probe,
            "request_bytes",
            return_value=(200, json.dumps(invalid).encode()),
        ):
            with self.assertRaisesRegex(RuntimeError, "status is invalid"):
                native_asset_probe._runtime_status(28447)

    def test_path_progress_requires_no_reopen_and_new_completion(self) -> None:
        baseline = self._stream_trace(1, recorded=1)
        reopened = self._stream_trace(2, opens=2, recorded=2)
        progressed = self._stream_trace(2, recorded=2)

        def await_trace(_port, _deadline, verifier, _description):
            self.assertFalse(verifier(reopened))
            self.assertTrue(verifier(progressed))
            return progressed

        with patch.object(
            native_asset_probe, "await_asset_trace", side_effect=await_trace
        ):
            observed = native_asset_probe._await_path_progress(
                28447,
                time.monotonic() + 1.0,
                native_asset_probe.NATIVE_CDVD_RECOVERY_PATH,
                baseline,
                True,
            )

        self.assertEqual(observed, progressed)

    def test_ioman_recovery_rejects_loaded_descriptor_drift(self) -> None:
        saved = self._snapshot()
        loaded = json.loads(json.dumps(saved))
        loaded["descriptors"][0]["cursor"] = 2048
        traces = [
            {"paths": []},
            {
                "paths": [
                    {
                        "path": "cdrom0:/MOVIES/INTRO.PSS;1",
                        "native_open_count": 1,
                        "original_fallback_count": 0,
                        "read_calls": 2,
                        "bytes_read": 8192,
                    }
                ]
            },
            {
                "paths": [
                    {
                        "path": "cdrom0:/MOVIES/INTRO.PSS;1",
                        "native_open_count": 1,
                        "original_fallback_count": 0,
                        "read_calls": 3,
                        "bytes_read": 12288,
                    }
                ]
            },
        ]

        with tempfile.TemporaryDirectory() as directory, patch.object(
            native_asset_probe, "await_asset_trace", side_effect=traces
        ), patch.object(
            native_asset_probe, "_request_state", side_effect=[saved, loaded]
        ):
            with self.assertRaisesRegex(RuntimeError, "differs from the saved state"):
                native_asset_probe.probe_native_ioman_state_recovery(
                    28447, time.monotonic() + 1.0, Path(directory)
                )


if __name__ == "__main__":
    unittest.main()
