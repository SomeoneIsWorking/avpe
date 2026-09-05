"""Unit tests for title-to-profile lifecycle control evidence."""

import json
import unittest
from unittest.mock import patch

from avpe.native_title_probe import (
    TITLE_TRANSITION_SCHEMA,
    start_title_transition_observation,
    title_transition_snapshot,
)


class NativeTitleTransitionProbeTests(unittest.TestCase):
    def test_start_arms_the_passive_observer(self) -> None:
        snapshot = {"schema": TITLE_TRANSITION_SCHEMA, "armed": True, "complete": False}
        with patch(
            "avpe.native_title_probe.request_bytes",
            return_value=(200, json.dumps(snapshot).encode()),
        ) as request:
            result = start_title_transition_observation(31234)

        self.assertEqual(result, snapshot)
        request.assert_called_once_with(31234, "POST", "/title-transition/start", {})

    def test_start_rejects_an_unarmed_response(self) -> None:
        snapshot = {"schema": TITLE_TRANSITION_SCHEMA, "armed": False, "complete": False}
        with patch(
            "avpe.native_title_probe.request_bytes",
            return_value=(200, json.dumps(snapshot).encode()),
        ), self.assertRaisesRegex(RuntimeError, "did not arm"):
            start_title_transition_observation(31234)

    def test_snapshot_rejects_an_unknown_schema(self) -> None:
        snapshot = {"schema": "wrong", "armed": True, "complete": False}
        with patch(
            "avpe.native_title_probe.request_bytes",
            return_value=(200, json.dumps(snapshot).encode()),
        ), self.assertRaisesRegex(RuntimeError, "unknown schema"):
            title_transition_snapshot(31234)


if __name__ == "__main__":
    unittest.main()
