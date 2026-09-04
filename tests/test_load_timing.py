import copy
import json
import unittest

from avpe.load_timing import (
    COMPARISON_SCHEMA,
    MISSION_COMPARISON_SCHEMA,
    MISSION_TIMING_SCHEMA,
    TIMING_SCHEMA,
    compare_load_timing_samples,
    compare_mission_load_timing_samples,
    load_timing_sample_is_ready,
    mission_load_timing_sample_is_ready,
    validate_load_timing_sample,
    validate_mission_load_timing_sample,
)


def make_sample(
    mode: str,
    *,
    ee_cycles: int,
    iop_cycles: int,
    frames: int,
    host_elapsed_ns: int,
    ordinal: int = 7,
) -> dict[str, object]:
    start = {
        "kind": "tbf-open",
        "path": "TBD/TBF.TBF",
        "ordinal": ordinal,
        "ee_cycle": 1_000_000,
        "iop_cycle": 400_000,
        "frame": 20,
        "host_time_ns": 50_000_000_000,
    }
    end = {
        "kind": "menu01-post-search-seek",
        "path": "STREAMS/MENU01.ZIV",
        "ordinal": ordinal + 8,
        "ee_cycle": start["ee_cycle"] + ee_cycles,
        "iop_cycle": start["iop_cycle"] + iop_cycles,
        "frame": start["frame"] + frames,
        "host_time_ns": start["host_time_ns"] + host_elapsed_ns,
    }
    return {
        "schema": TIMING_SCHEMA,
        "enabled": True,
        "target_recognized": True,
        "byte_trace_disabled": True,
        "mode": mode,
        "complete": True,
        "sequence_errors": 0,
        "backends": {
            "tbf": "native" if mode == "native" else "optical",
            "menu01_seek": "native" if mode == "native" else "optical",
        },
        "start": start,
        "end": end,
        "deltas": {
            "ee_cycles": ee_cycles,
            "iop_cycles": iop_cycles,
            "frames": frames,
            "host_elapsed_ns": host_elapsed_ns,
        },
    }


def make_runs(mode: str, multiplier: int) -> list[dict[str, object]]:
    return [
        make_sample(
            mode,
            ee_cycles=multiplier * ee,
            iop_cycles=multiplier * iop,
            frames=multiplier * 10 + frame_jitter,
            host_elapsed_ns=multiplier * host_ns,
        )
        for ee, iop, frame_jitter, host_ns in (
            (100_000, 50_000, 0, 1_000_000_000),
            (100_200, 50_100, 0, 1_050_000_000),
            (99_900, 49_950, 1, 950_000_000),
        )
    ]


def make_mission_sample(
    mode: str,
    *,
    ee_cycles: int,
    iop_cycles: int,
    frames: int,
    host_elapsed_ns: int,
    ordinal: int = 20,
) -> dict[str, object]:
    start = {
        "kind": "shell-load-level-entry",
        "path": "M01/background.tbd",
        "pc": 0x0016F910,
        "ordinal": ordinal,
        "ee_cycle": 4_000_000,
        "iop_cycle": 1_600_000,
        "frame": 200,
        "host_time_ns": 70_000_000_000,
    }
    end = {
        "kind": "shell-load-level-return",
        "path": "M01/background.tbd",
        "pc": 0x0016FA4C,
        "ordinal": ordinal + 1,
        "ee_cycle": start["ee_cycle"] + ee_cycles,
        "iop_cycle": start["iop_cycle"] + iop_cycles,
        "frame": start["frame"] + frames,
        "host_time_ns": start["host_time_ns"] + host_elapsed_ns,
    }
    return {
        "schema": MISSION_TIMING_SCHEMA,
        "target": "mission",
        "enabled": True,
        "target_recognized": True,
        "byte_trace_disabled": True,
        "mode": mode,
        "complete": True,
        "sequence_errors": 0,
        "optical_activity": {
            "action_waits": {
                "count": 3 if mode == "oracle" else 0,
                "cycles": 900_000 if mode == "oracle" else 0,
            },
            "read_waits": {
                "count": 20 if mode == "oracle" else 0,
                "cycles": 6_000_000 if mode == "oracle" else 0,
            },
            "sector_ready_waits": {
                "count": 40 if mode == "oracle" else 0,
                "cycles": 12_000_000 if mode == "oracle" else 0,
            },
            "sector_deliveries": 20 if mode == "oracle" else 0,
        },
        "start": start,
        "end": end,
        "deltas": {
            "ee_cycles": ee_cycles,
            "iop_cycles": iop_cycles,
            "frames": frames,
            "host_elapsed_ns": host_elapsed_ns,
        },
    }


def make_mission_runs(mode: str, multiplier: int) -> list[dict[str, object]]:
    return [
        make_mission_sample(
            mode,
            ee_cycles=multiplier * ee,
            iop_cycles=multiplier * iop,
            frames=multiplier * 18 + frame_jitter,
            host_elapsed_ns=multiplier * host_ns,
        )
        for ee, iop, frame_jitter, host_ns in (
            (800_000, 300_000, 0, 3_000_000_000),
            (800_800, 300_300, 0, 3_100_000_000),
            (799_600, 299_850, 1, 2_900_000_000),
        )
    ]


class LoadTimingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.oracle = make_runs("oracle", 2)
        self.native = make_runs("native", 1)

    def test_accepts_stable_symmetric_samples_and_reports_reduction(self) -> None:
        report = compare_load_timing_samples(self.oracle, self.native)

        self.assertEqual(report["schema"], COMPARISON_SCHEMA)
        self.assertNotIn("target", report)
        self.assertTrue(report["verified"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(
            report["raw_samples"]["oracle"]["ee_cycles"],
            [200_000, 200_400, 199_800],
        )
        self.assertEqual(report["medians"]["oracle"]["ee_cycles"], 200_000)
        self.assertEqual(report["spreads"]["native"]["frames"], 1)
        self.assertEqual(report["reductions"]["ee_cycles"]["absolute"], 100_000)
        self.assertEqual(report["reductions"]["ee_cycles"]["percent"], 50.0)
        json.dumps(report)

    def test_public_validator_returns_canonical_deltas(self) -> None:
        self.assertEqual(
            validate_load_timing_sample(self.native[0], "native"),
            {
                "ee_cycles": 100_000,
                "iop_cycles": 50_000,
                "frames": 10,
                "host_elapsed_ns": 1_000_000_000,
            },
        )
        self.assertTrue(load_timing_sample_is_ready(self.native[0], "native"))
        self.assertFalse(load_timing_sample_is_ready(self.native[0], "oracle"))

    def test_rejects_wrong_schema_mode_and_incomplete_capture(self) -> None:
        cases = (
            ("schema", "wrong"),
            ("mode", "oracle"),
            ("complete", False),
            ("enabled", False),
            ("target_recognized", False),
            ("byte_trace_disabled", False),
            ("sequence_errors", 1),
        )
        for field, value in cases:
            with self.subTest(field=field):
                runs = copy.deepcopy(self.native)
                runs[0][field] = value
                report = compare_load_timing_samples(self.oracle, runs)
                self.assertFalse(report["verified"])
                self.assertEqual(report["errors"][0]["code"], "invalid_sample")
                self.assertEqual(report["errors"][0]["mode"], "native")
                self.assertEqual(report["errors"][0]["index"], 0)

    def test_rejects_wrong_boundary_identity_and_order(self) -> None:
        mutations = (
            ("start", "kind", "movie-open"),
            ("start", "path", "MOVIES/EALOGO.PSS"),
            ("end", "kind", "menu01-search"),
            ("end", "path", "MOVIES/INTRO.PSS"),
            ("end", "ordinal", 7),
        )
        for section, field, value in mutations:
            with self.subTest(section=section, field=field):
                runs = copy.deepcopy(self.native)
                runs[0][section][field] = value
                report = compare_load_timing_samples(self.oracle, runs)
                self.assertFalse(report["verified"])
                self.assertEqual(report["errors"][0]["code"], "invalid_sample")

    def test_rejects_backend_that_does_not_match_mode(self) -> None:
        self.native[0]["backends"]["tbf"] = "optical"

        report = compare_load_timing_samples(self.oracle, self.native)

        self.assertFalse(report["verified"])
        self.assertIn("backends.tbf", report["errors"][0]["detail"])

    def test_rejects_nonpositive_and_mismatched_recomputed_deltas(self) -> None:
        for metric in ("ee_cycles", "iop_cycles", "frames"):
            with self.subTest(metric=metric, reason="nonpositive"):
                runs = copy.deepcopy(self.native)
                runs[0]["deltas"][metric] = 0
                report = compare_load_timing_samples(self.oracle, runs)
                self.assertFalse(report["verified"])
                self.assertIn("positive integer", report["errors"][0]["detail"])

            with self.subTest(metric=metric, reason="recomputed"):
                runs = copy.deepcopy(self.native)
                runs[0]["deltas"][metric] += 1
                report = compare_load_timing_samples(self.oracle, runs)
                self.assertFalse(report["verified"])
                self.assertIn("recomputed", report["errors"][0]["detail"])

    def test_rejects_too_few_or_mismatched_sample_counts(self) -> None:
        report = compare_load_timing_samples(self.oracle[:2], self.native)

        self.assertFalse(report["verified"])
        codes = [error["code"] for error in report["errors"]]
        self.assertIn("insufficient_samples", codes)
        self.assertIn("sample_count_mismatch", codes)

    def test_rejects_boundary_ordinal_drift(self) -> None:
        self.native[2]["start"]["ordinal"] += 1
        self.native[2]["end"]["ordinal"] += 1

        report = compare_load_timing_samples(self.oracle, self.native)

        self.assertFalse(report["verified"])
        error = next(
            error for error in report["errors"]
            if error["code"] == "boundary_ordinal_drift"
        )
        self.assertEqual(error["mode"], "native")

    def test_rejects_spread_instead_of_averaging_away_drift(self) -> None:
        drifted = self.native[2]
        drifted["end"]["ee_cycle"] += 2_000
        drifted["deltas"]["ee_cycles"] += 2_000

        report = compare_load_timing_samples(self.oracle, self.native)

        self.assertFalse(report["verified"])
        error = next(
            error for error in report["errors"]
            if error["code"] == "excessive_guest_boundary_spread"
        )
        self.assertEqual(error["mode"], "native")
        self.assertEqual(error["metric"], "ee_cycles")
        self.assertGreater(error["spread"], error["allowed"])

    def test_rejects_a_native_path_without_measured_improvement(self) -> None:
        native = make_runs("native", 2)

        report = compare_load_timing_samples(self.oracle, native)

        self.assertFalse(report["verified"])
        self.assertEqual(
            [error["metric"] for error in report["errors"]],
            ["ee_cycles", "iop_cycles", "frames", "host_elapsed_ns"],
        )
        self.assertTrue(all(
            error["code"] == "no_measured_reduction"
            for error in report["errors"]
        ))

    def test_rejects_non_lists_without_throwing(self) -> None:
        report = compare_load_timing_samples(tuple(self.oracle), self.native)
        self.assertFalse(report["verified"])
        self.assertEqual(report["errors"][0]["code"], "invalid_run_collection")


class MissionLoadTimingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.oracle = make_mission_runs("oracle", 2)
        self.native = make_mission_runs("native", 1)

    def test_accepts_mission_samples_with_shared_comparison_policy(self) -> None:
        report = compare_mission_load_timing_samples(self.oracle, self.native)

        self.assertEqual(report["schema"], MISSION_COMPARISON_SCHEMA)
        self.assertEqual(report["target"], "mission")
        self.assertTrue(report["verified"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["medians"]["oracle"]["ee_cycles"], 1_600_000)
        self.assertEqual(report["reductions"]["ee_cycles"]["percent"], 50.0)
        json.dumps(report)

    def test_public_mission_validator_returns_canonical_deltas(self) -> None:
        self.assertEqual(
            validate_mission_load_timing_sample(self.native[0], "native"),
            {
                "ee_cycles": 800_000,
                "iop_cycles": 300_000,
                "frames": 18,
                "host_elapsed_ns": 3_000_000_000,
            },
        )
        self.assertTrue(
            mission_load_timing_sample_is_ready(self.native[0], "native")
        )
        self.assertFalse(
            mission_load_timing_sample_is_ready(self.native[0], "oracle")
        )

    def test_accepts_zero_native_frames_for_host_fast_synchronous_load(self) -> None:
        sample = make_mission_sample(
            "native",
            ee_cycles=800_000,
            iop_cycles=300_000,
            frames=0,
            host_elapsed_ns=3_000_000_000,
        )

        self.assertTrue(mission_load_timing_sample_is_ready(sample, "native"))

    def test_other_answers_reject_wrong_schema_target_path_and_pc(self) -> None:
        mutations = (
            (None, "schema", TIMING_SCHEMA, MISSION_TIMING_SCHEMA),
            (None, "target", "startup", "mission"),
            ("start", "path", "M02/background.tbd", "M01/background.tbd"),
            ("end", "path", "M01/terrain.tbd", "M01/background.tbd"),
            ("start", "pc", 0x0016F914, "0x0016f910"),
            ("end", "pc", 0x0016FA50, "0x0016fa4c"),
        )
        for section, field, value, expected in mutations:
            with self.subTest(section=section, field=field):
                runs = copy.deepcopy(self.native)
                owner = runs[0] if section is None else runs[0][section]
                owner[field] = value

                report = compare_mission_load_timing_samples(self.oracle, runs)

                self.assertFalse(report["verified"])
                error = report["errors"][0]
                self.assertEqual(error["code"], "invalid_sample")
                self.assertEqual(error["mode"], "native")
                self.assertEqual(error["index"], 0)
                self.assertIn(str(expected), error["detail"])

    def test_rejects_startup_backends_inside_mission_sample(self) -> None:
        self.native[0]["backends"] = {
            "tbf": "native",
            "menu01_seek": "native",
        }

        report = compare_mission_load_timing_samples(self.oracle, self.native)

        self.assertFalse(report["verified"])
        self.assertIn(
            "must not contain startup backends",
            report["errors"][0]["detail"],
        )

    def test_rejects_missing_common_host_counter_without_throwing(self) -> None:
        del self.native[0]["start"]["host_time_ns"]

        report = compare_mission_load_timing_samples(self.oracle, self.native)

        self.assertFalse(report["verified"])
        self.assertIn("start.host_time_ns", report["errors"][0]["detail"])

    def test_rejects_optical_work_in_native_mission_interval(self) -> None:
        self.native[0]["optical_activity"]["read_waits"] = {
            "count": 1,
            "cycles": 100,
        }

        report = compare_mission_load_timing_samples(self.oracle, self.native)

        self.assertFalse(report["verified"])
        self.assertIn(
            "zero optical waits and sector deliveries",
            report["errors"][0]["detail"],
        )

    def test_rejects_oracle_that_does_not_fire_optical_instrument(self) -> None:
        self.oracle[0]["optical_activity"] = copy.deepcopy(
            self.native[0]["optical_activity"]
        )

        report = compare_mission_load_timing_samples(self.oracle, self.native)

        self.assertFalse(report["verified"])
        self.assertIn("positive optical wait", report["errors"][0]["detail"])

    def test_rejects_inconsistent_optical_wait_pair(self) -> None:
        self.oracle[0]["optical_activity"]["read_waits"]["cycles"] = 0

        report = compare_mission_load_timing_samples(self.oracle, self.native)

        self.assertFalse(report["verified"])
        self.assertIn("count/cycles", report["errors"][0]["detail"])

    def test_startup_validator_still_rejects_mission_schema(self) -> None:
        self.assertFalse(load_timing_sample_is_ready(self.native[0], "native"))


if __name__ == "__main__":
    unittest.main()
