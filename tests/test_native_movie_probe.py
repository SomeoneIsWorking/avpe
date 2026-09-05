import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from avpe.native_movie_probe import probe_native_movie_cancellation


class NativeMovieProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.start = self.patches.enter_context(patch(
            "avpe.native_movie_probe.start_title_transition_observation",
        ))
        self.action = self.patches.enter_context(patch(
            "avpe.native_movie_probe.run_menu_action",
            side_effect=[
                ({"source": "movie-cancellation", "movie_action_id": 1}, {"safe": True}),
                ({"source": "movie-cancellation", "movie_action_id": 2}, {"safe": True}),
            ],
        ))
        self.menu = self.patches.enter_context(patch(
            "avpe.native_movie_probe.menu_state",
            return_value=(200, {"menu_vtable": "0x00342A50", "callback_count": 8}, "title"),
        ))
        self.observer = self.patches.enter_context(patch(
            "avpe.native_movie_probe.title_transition_snapshot",
            return_value={"press_start": {"ordinal": 0}, "profile_create": {"ordinal": 0}},
        ))
        self.http = self.patches.enter_context(patch(
            "avpe.native_movie_probe.request_json",
            side_effect=[
                (200, {"inject_inputs": "0000", "inject_wire": "0000"}, "neutral"),
                (200, {}, "loaded"),
                (200, {"state": "idle", "id": 0}, "reset"),
            ],
        ))

    def run_probe(self) -> dict[str, object]:
        return probe_native_movie_cancellation(31234, time.monotonic() + 1, Path("fixture.p2s"))

    def test_observes_two_explicit_lifetimes_with_reset_between(self) -> None:
        result = self.run_probe()
        self.assertEqual(result["first"]["request"]["movie_action_id"], 1)
        self.assertEqual(result["restored_player"]["request"]["movie_action_id"], 2)
        self.assertEqual(self.action.call_count, 2)
        self.assertEqual(self.http.call_args_list[1].args[2], "/state/load")

    def test_failed_call_stops_without_retry_or_state_reload(self) -> None:
        self.action.side_effect = RuntimeError("deferred call did not return")
        with self.assertRaisesRegex(RuntimeError, "did not return"):
            self.run_probe()
        self.assertEqual(self.action.call_count, 1)
        self.http.assert_not_called()

    def test_non_movie_admission_is_not_a_logo_success(self) -> None:
        self.action.side_effect = [({"source": "callback-registry"}, {})]
        with self.assertRaisesRegex(RuntimeError, "did not reach movie admission"):
            self.run_probe()
        self.menu.assert_not_called()

    def test_title_activation_leak_refuses_before_reload(self) -> None:
        self.observer.return_value["press_start"]["ordinal"] = 1
        with self.assertRaisesRegex(RuntimeError, "leaked"):
            self.run_probe()
        self.http.assert_not_called()

    def test_reset_must_discard_prior_ticket(self) -> None:
        self.http.side_effect = [
            (200, {"inject_inputs": "0000", "inject_wire": "0000"}, "neutral"),
            (200, {}, "loaded"),
            (200, {"state": "dispatched", "id": 1}, "inherited"),
        ]
        with self.assertRaisesRegex(RuntimeError, "inherited"):
            self.run_probe()
        self.assertEqual(self.action.call_count, 1)
