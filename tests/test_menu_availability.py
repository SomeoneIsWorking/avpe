"""Menu publication must complete before a dependent action is admitted."""

import time
import unittest
from pathlib import Path
from unittest.mock import patch

from avpe.menu_probe import await_settled_menu_state
from avpe.native_bios_probe import PROFILE_MENU_VTABLE, run_bios_phase


class MenuAvailabilityTests(unittest.TestCase):
    def test_existing_observation_preserves_unavailable_state(self) -> None:
        state = {"menu": "0x00000000"}
        with patch("avpe.menu_probe.menu_state", return_value=(409, state, "absent")):
            self.assertEqual(
                await_settled_menu_state(1, time.monotonic() + 1, "observe"), (409, state)
            )

    def test_required_menu_waits_through_ambiguous_and_unavailable_states(self) -> None:
        profile = {"menu_vtable": PROFILE_MENU_VTABLE}
        with patch("avpe.menu_probe.menu_state", side_effect=[
            (409, {"conflicting_menu": "0x0147D230"}, "ambiguous"),
            (500, None, "transitional focus"),
            (200, profile, "profile"),
        ]), patch("avpe.menu_probe.time.sleep"):
            self.assertEqual(await_settled_menu_state(
                1, time.monotonic() + 1, "publish", require_available=True
            ), (200, profile))

    def test_required_menu_keeps_deadline_failure(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "did not settle"):
            await_settled_menu_state(1, 0, "publish", require_available=True)

    def test_profile_action_waits_for_publication_after_title_overlap(self) -> None:
        profile = {"menu_vtable": PROFILE_MENU_VTABLE}
        with patch("avpe.native_bios_probe._activate_title_menu", return_value={
            "status": 409, "state": {"conflicting_menu": "0x0147D230"}
        }), patch("avpe.menu_probe.menu_state", side_effect=[
            (409, {}, "overlap"), (200, profile, "published")
        ]), patch("avpe.menu_probe.time.sleep"), patch(
            "avpe.native_bios_probe.title_transition_snapshot", return_value={"complete": True}
        ), patch("avpe.native_bios_probe._complete_menu_action") as activate, patch(
            "avpe.native_bios_probe._await_menu_transition", return_value=(200, {})
        ), patch("avpe.native_bios_probe.capture_bios_trace", return_value={}):
            result, _, _ = run_bios_phase(
                1, time.monotonic() + 1, "title-profile", Path("title.p2s"), Path("out.p2s")
            )
        self.assertEqual(result["title_menu_after_action"], {"status": 200, "state": profile})
        activate.assert_called_once()
