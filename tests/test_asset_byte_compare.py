import copy
import json
import unittest

from avpe.asset_byte_compare import (
    COMPARISON_SCHEMA,
    REQUIRED_FILES,
    TRACE_SCHEMA,
    asset_byte_trace_is_ready,
    compare_asset_byte_traces,
)


def make_trace(mode: str) -> dict[str, object]:
    files = []
    for file_index, path in enumerate(REQUIRED_FILES):
        chunks = []
        for chunk_index in range(4):
            chunks.append({
                "offset": chunk_index * 2048,
                "size": 2048,
                "sha256": f"{file_index * 4 + chunk_index + 1:064x}",
                "sources": ["iso-oracle" if mode == "oracle" else "native-ioman"],
                "hits": chunk_index + 1,
                "conflict": False,
            })
        files.append({
            "path": path,
            "iso_lsn": 1000 + file_index * 100,
            "iso_size": 16_384,
            "chunks": chunks,
        })
    return {
        "schema": TRACE_SCHEMA,
        "enabled": True,
        "target_recognized": True,
        "mode": mode,
        "dropped_files": 0,
        "dropped_bytes": 0,
        "registration_failures": 0,
        "files": files,
    }


class AssetByteComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.oracle = make_trace("oracle")
        self.native = make_trace("native")

    def test_accepts_matching_keyed_chunks_independent_of_order_and_hits(self) -> None:
        native_files = self.native["files"]
        self.assertIsInstance(native_files, list)
        native_files.reverse()
        for file in native_files:
            file["chunks"].reverse()
            for chunk in file["chunks"]:
                chunk["hits"] = 99

        report = compare_asset_byte_traces(self.oracle, self.native)

        self.assertEqual(report["schema"], COMPARISON_SCHEMA)
        self.assertTrue(report["verified"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(
            [file["path"] for file in report["files"]],
            sorted(REQUIRED_FILES),
        )
        self.assertTrue(all(file["matched_chunks"] == 4 for file in report["files"]))
        json.dumps(report)

    def test_live_trace_readiness_uses_the_same_strict_policy(self) -> None:
        self.assertTrue(asset_byte_trace_is_ready(self.oracle, "oracle"))
        self.assertTrue(asset_byte_trace_is_ready(self.native, "native"))
        self.native["files"][0]["chunks"] = self.native["files"][0]["chunks"][:3]
        self.assertFalse(asset_byte_trace_is_ready(self.native, "native"))

    def test_rejects_source_from_the_other_execution_path(self) -> None:
        self.native["files"][0]["chunks"][0]["sources"] = ["iso-oracle"]
        report = compare_asset_byte_traces(self.oracle, self.native)
        self.assertFalse(report["verified"])
        self.assertIn("do not belong", report["errors"][0]["detail"])

    def test_other_answer_reports_precise_changed_digest_location(self) -> None:
        changed = self.native["files"][1]["chunks"][2]
        changed["sha256"] = "f" * 64

        report = compare_asset_byte_traces(self.oracle, self.native)

        self.assertFalse(report["verified"])
        mismatch = next(
            error for error in report["errors"]
            if error["code"] == "chunk_digest_mismatch"
        )
        self.assertEqual(mismatch["path"], "MOVIES/EALOGO.PSS")
        self.assertEqual(mismatch["offset"], 4096)
        self.assertEqual(mismatch["size"], 2048)
        self.assertEqual(mismatch["native_sha256"], "f" * 64)
        self.assertNotEqual(mismatch["oracle_sha256"], mismatch["native_sha256"])

    def test_rejects_wrong_identity_modes(self) -> None:
        self.oracle["mode"] = "native"
        self.native["mode"] = "oracle"

        report = compare_asset_byte_traces(self.oracle, self.native)

        self.assertFalse(report["verified"])
        self.assertEqual(
            [error["code"] for error in report["errors"]],
            ["invalid_oracle_trace", "invalid_native_trace"],
        )

    def test_rejects_loss_and_conflict(self) -> None:
        cases = (
            ("dropped_files", 1),
            ("dropped_bytes", 2048),
            ("registration_failures", 1),
        )
        for field, value in cases:
            with self.subTest(field=field):
                trace = copy.deepcopy(self.oracle)
                trace[field] = value
                report = compare_asset_byte_traces(trace, self.native)
                self.assertFalse(report["verified"])
                self.assertIn(field, report["errors"][0]["detail"])

        trace = copy.deepcopy(self.native)
        trace["files"][0]["chunks"][0]["conflict"] = True
        report = compare_asset_byte_traces(self.oracle, trace)
        self.assertFalse(report["verified"])
        self.assertIn("conflict must be false", report["errors"][0]["detail"])

    def test_rejects_missing_required_file(self) -> None:
        self.native["files"] = self.native["files"][1:]

        report = compare_asset_byte_traces(self.oracle, self.native)

        self.assertFalse(report["verified"])
        error = next(
            error for error in report["errors"]
            if error["code"] == "missing_required_file"
        )
        self.assertEqual(error["path"], "TBD/TBF.TBF")
        self.assertEqual(error["missing_from"], ["native"])

    def test_rejects_file_size_and_lsn_mismatch(self) -> None:
        self.native["files"][0]["iso_lsn"] += 1
        self.native["files"][1]["iso_size"] += 1

        report = compare_asset_byte_traces(self.oracle, self.native)

        self.assertFalse(report["verified"])
        codes = {error["code"] for error in report["errors"]}
        self.assertIn("file_lsn_mismatch", codes)
        self.assertIn("file_size_mismatch", codes)

    def test_rejects_fewer_than_four_common_chunks_per_required_file(self) -> None:
        self.native["files"][0]["chunks"] = self.native["files"][0]["chunks"][:3]

        report = compare_asset_byte_traces(self.oracle, self.native)

        self.assertFalse(report["verified"])
        error = next(
            error for error in report["errors"]
            if error["code"] == "insufficient_common_chunks"
        )
        self.assertEqual(error["path"], "TBD/TBF.TBF")
        self.assertEqual(error["required"], 4)
        self.assertEqual(error["observed"], 3)

    def test_rejects_malformed_chunk_and_duplicate_range(self) -> None:
        malformed = copy.deepcopy(self.oracle)
        malformed["files"][0]["chunks"][0]["sha256"] = "NOT-A-DIGEST"
        report = compare_asset_byte_traces(malformed, self.native)
        self.assertFalse(report["verified"])
        self.assertIn("lowercase SHA-256", report["errors"][0]["detail"])

        duplicate = copy.deepcopy(self.native)
        duplicate["files"][0]["chunks"].append(
            copy.deepcopy(duplicate["files"][0]["chunks"][0])
        )
        report = compare_asset_byte_traces(self.oracle, duplicate)
        self.assertFalse(report["verified"])
        self.assertIn("duplicate range", report["errors"][0]["detail"])

    def test_rejects_no_common_chunks(self) -> None:
        for file in self.native["files"]:
            for chunk in file["chunks"]:
                chunk["offset"] += 8192

        report = compare_asset_byte_traces(self.oracle, self.native)

        self.assertFalse(report["verified"])
        self.assertIn("no_common_chunks", [error["code"] for error in report["errors"]])

    def test_rejects_noncanonical_path(self) -> None:
        self.native["files"][0]["path"] = r"cdrom0:\TBD\TBF.TBF;1"

        report = compare_asset_byte_traces(self.oracle, self.native)

        self.assertFalse(report["verified"])
        self.assertIn("not canonical", report["errors"][0]["detail"])


if __name__ == "__main__":
    unittest.main()
