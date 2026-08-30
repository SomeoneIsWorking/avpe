import copy
import time
import unittest
from unittest.mock import patch

from avpe import native_mission_probe


class NativeMissionProbePolicyTests(unittest.TestCase):
    @classmethod
    def _proof(cls, *, native_assets: bool = True) -> dict[str, object]:
        shell = "0x01400000"
        path_hex = (
            native_mission_probe.M1_BACKGROUND_PATH.encode() + b"\0"
        ).hex()
        proof: dict[str, object] = {
            "input_route": "shell-set-next-level",
            "pad_injection": False,
            "input_savestate": False,
            "world_before": "0x00000000",
            "trigger": {
                "function": f"0x{native_mission_probe.SET_NEXT_LEVEL:08X}",
                "shell": shell,
                "path": native_mission_probe.M1_BACKGROUND_PATH,
                "path_bytes_hex": path_hex,
                "staged_path_bytes_hex": path_hex,
                "flags_after": 1,
                "call": {
                    "v0": shell,
                    "staging_address": "0x01FF0000",
                    "stack_restored": True,
                },
            },
            "endpoint": {"world": "0x01500000"},
            "mission_goals": {
                "singleton_address": "0x00367C04",
                "menu": "0x01510000",
                "state_before": {
                    "source": "mission-goals-load",
                    "menu": "0x01510000",
                    "action_target": "0x01510200",
                    "callback_count": 0,
                    "focus_handle": "0x00000000",
                    "focus_object": "0x00000000",
                },
                "focus_vtable": "0x00342370",
                "action": "activate",
                "dispatch": {
                    "source": "mission-goals-load",
                    "menu": "0x01510000",
                    "handler": "0x00125330",
                    "action_target": "0x01510200",
                    "before": {
                        "focus_handle": "0x00001234",
                        "focus_object": "0x01510200",
                    },
                    "execution": "synchronous",
                    "stopped_pc": "0x002052C8",
                    "stack_restored": True,
                    "elapsed_cycles": 1100,
                    "deferred": False,
                },
                "singleton_after": "0x00000000",
            },
        }
        if native_assets:
            proof["native_assets"] = {
                "before": {
                    "opens": cls._opens(reads=10, seeks=2, byte_count=655_360),
                    "cache": cls._cache(fills=3),
                },
                "after": {
                    "opens": cls._opens(reads=15, seeks=3, byte_count=983_040),
                    "cache": cls._cache(fills=5),
                },
            }
        return proof

    @staticmethod
    def _opens(reads: int, seeks: int, byte_count: int) -> dict[str, object]:
        return {
            "enabled": True,
            "target_recognized": True,
            "paths": [
                {
                    "path": "cdrom0:/TBD/TBF.TBF;1",
                    "count": 1,
                    "native_open_count": 1,
                    "original_fallback_count": 0,
                    "read_calls": reads,
                    "bytes_read": byte_count,
                    "seek_calls": seeks,
                    "close_count": 0,
                }
            ],
        }

    @staticmethod
    def _cache(fills: int) -> dict[str, object]:
        return {
            "page_bytes": 64 * 1024,
            "maximum_pages": 512,
            "maximum_resident_bytes": 32 * 1024 * 1024,
            "hits": 2,
            "misses": fills,
            "fills": fills,
            "evictions": 0,
            "resident_pages": fills,
            "resident_bytes": fills * 64 * 1024,
            "transient_handles": 0,
            "peak_transient_handles": 1,
        }

    def test_accepts_grounded_trigger_with_native_deltas(self) -> None:
        self.assertEqual(
            native_mission_probe.validate_marine_m1_evidence(
                self._proof(), require_native_assets=True
            ),
            [],
        )

    def test_accepts_backend_neutral_transition_without_native_policy(self) -> None:
        self.assertEqual(
            native_mission_probe.validate_marine_m1_evidence(
                self._proof(native_assets=False)
            ),
            [],
        )

    def test_rejects_wrong_path_or_unrestored_staging(self) -> None:
        proof = self._proof(native_assets=False)
        trigger = proof["trigger"]
        assert isinstance(trigger, dict)
        trigger["path"] = "M02/background.tbd"
        call = trigger["call"]
        assert isinstance(call, dict)
        call["stack_restored"] = False

        errors = native_mission_probe.validate_marine_m1_evidence(proof)

        self.assertTrue(any("path is not exact" in error for error in errors))
        self.assertTrue(any("restore its guest staging" in error for error in errors))

    def test_rejects_missing_shell_flag_and_existing_world(self) -> None:
        proof = self._proof(native_assets=False)
        trigger = proof["trigger"]
        assert isinstance(trigger, dict)
        trigger["flags_after"] = 0
        proof["world_before"] = "0x01500000"

        errors = native_mission_probe.validate_marine_m1_evidence(proof)

        self.assertTrue(any("pending-level flag" in error for error in errors))
        self.assertTrue(any("already populated" in error for error in errors))

    def test_rejects_unmatched_or_uncleared_mission_goals_menu(self) -> None:
        proof = self._proof(native_assets=False)
        mission_goals = proof["mission_goals"]
        assert isinstance(mission_goals, dict)
        state = mission_goals["state_before"]
        assert isinstance(state, dict)
        state["menu"] = "0x01520000"
        state["source"] = "callback-registry"
        mission_goals["singleton_after"] = "0x01510000"

        errors = native_mission_probe.validate_marine_m1_evidence(proof)

        self.assertTrue(any("did not match" in error for error in errors))
        self.assertTrue(any("synchronous load source" in error for error in errors))
        self.assertTrue(any("did not clear" in error for error in errors))

    def test_rejects_deferred_mission_goals_activation(self) -> None:
        proof = self._proof(native_assets=False)
        mission_goals = proof["mission_goals"]
        assert isinstance(mission_goals, dict)
        dispatch = mission_goals["dispatch"]
        assert isinstance(dispatch, dict)
        dispatch["execution"] = "deferred"
        dispatch["deferred"] = True
        dispatch["stack_restored"] = False

        errors = native_mission_probe.validate_marine_m1_evidence(proof)

        self.assertTrue(any("synchronous execution" in error for error in errors))
        self.assertTrue(any("did not complete safely" in error for error in errors))

    def test_dismisses_only_the_grounded_mission_goals_menu(self) -> None:
        state = {
            "source": "mission-goals-load",
            "menu": "0x01510000",
            "action_target": "0x01510200",
            "callback_count": 0,
            "focus_handle": "0x00000000",
            "focus_object": "0x00000000",
        }
        dispatch = {
            "source": "mission-goals-load",
            "menu": "0x01510000",
            "handler": "0x00125330",
            "action_target": "0x01510200",
            "before": {
                "focus_handle": "0x00001234",
                "focus_object": "0x01510200",
            },
            "execution": "synchronous",
            "stopped_pc": "0x002052C8",
            "stack_restored": True,
            "elapsed_cycles": 1100,
            "deferred": False,
        }
        deadline = time.monotonic() + 1.0
        with patch(
            "avpe.native_mission_probe._await_nonzero_u32", return_value=0x01510000
        ), patch(
            "avpe.native_mission_probe.menu_state", return_value=(200, state, "")
        ), patch(
            "avpe.native_mission_probe.menu_action",
            return_value=(200, dispatch, ""),
        ) as activate, patch(
            "avpe.native_mission_probe._read_u32",
            return_value=native_mission_probe.EXIT_MISSION_GOALS_BUTTON_VTABLE,
        ), patch("avpe.native_mission_probe._await_zero_u32"):
            evidence = native_mission_probe.dismiss_mission_goals(31234, deadline)

        activate.assert_called_once_with(31234, "activate")
        self.assertEqual(evidence["menu"], "0x01510000")
        self.assertEqual(evidence["singleton_after"], "0x00000000")

    def test_rejects_native_reopen_fallback_and_nonincreasing_reads(self) -> None:
        proof = self._proof()
        native_assets = proof["native_assets"]
        assert isinstance(native_assets, dict)
        after = native_assets["after"]
        assert isinstance(after, dict)
        opens = after["opens"]
        assert isinstance(opens, dict)
        tbf = opens["paths"][0]
        tbf["native_open_count"] = 2
        tbf["original_fallback_count"] = 1
        tbf["read_calls"] = 10

        errors = native_mission_probe.validate_marine_m1_evidence(
            proof, require_native_assets=True
        )

        self.assertTrue(any("native_open_count changed" in error for error in errors))
        self.assertTrue(any("original_fallback_count changed" in error for error in errors))
        self.assertTrue(any("read_calls did not increase" in error for error in errors))

    def test_rejects_unbounded_or_transient_cache(self) -> None:
        proof = copy.deepcopy(self._proof())
        native_assets = proof["native_assets"]
        assert isinstance(native_assets, dict)
        after = native_assets["after"]
        assert isinstance(after, dict)
        cache = after["cache"]
        assert isinstance(cache, dict)
        cache["transient_handles"] = 1

        errors = native_mission_probe.validate_marine_m1_evidence(
            proof, require_native_assets=True
        )

        self.assertIn(
            "post-transition cache snapshot is not bounded and quiescent", errors
        )


if __name__ == "__main__":
    unittest.main()
