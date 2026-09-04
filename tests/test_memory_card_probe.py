import time
import unittest
from unittest.mock import patch

from avpe import memory_card_probe


class MemoryCardReadinessTests(unittest.TestCase):
    def test_waits_for_auto_ejection_to_complete(self) -> None:
        with patch(
            "avpe.memory_card_probe.memory_card_state",
            side_effect=[
                (200, self._state(42, False, False), ""),
                (200, self._state(1, False, False), ""),
                (200, self._state(0, False, True), ""),
            ],
        ), patch("avpe.memory_card_probe.time.sleep"):
            proof = memory_card_probe.await_memory_card_ready(
                31234, time.monotonic() + 1.0
            )

        self.assertEqual(proof["observations"], 3)
        self.assertIs(proof["saw_auto_eject"], True)
        self.assertIs(proof["saw_busy"], False)
        self.assertIs(proof["state"]["ready"], True)

    def test_waits_for_active_card_writes_to_settle(self) -> None:
        with patch(
            "avpe.memory_card_probe.memory_card_state",
            side_effect=[
                (200, self._state(0, True, False), ""),
                (200, self._state(0, False, True), ""),
            ],
        ), patch("avpe.memory_card_probe.time.sleep"):
            proof = memory_card_probe.await_memory_card_ready(
                31234, time.monotonic() + 1.0
            )

        self.assertIs(proof["saw_auto_eject"], False)
        self.assertIs(proof["saw_busy"], True)

    def test_reports_a_card_that_never_becomes_ready(self) -> None:
        with patch(
            "avpe.memory_card_probe.memory_card_state",
            return_value=(200, self._state(12, False, False), ""),
        ):
            with self.assertRaisesRegex(RuntimeError, "did not become ready"):
                memory_card_probe.await_memory_card_ready(
                    31234, time.monotonic() - 1.0
                )

    def test_state_parser_rejects_inconsistent_readiness(self) -> None:
        with patch(
            "avpe.memory_card_probe.request_bytes",
            return_value=(200, b'{"schema":"avpe-memory-card-state-v1",'
                              b'"slot":0,"present":true,'
                              b'"auto_eject_ticks":2,"busy":false,"ready":true}'),
        ):
            status, state, detail = memory_card_probe.memory_card_state(31234)

        self.assertEqual(status, 200)
        self.assertIsNone(state)
        self.assertIn('"auto_eject_ticks":2', detail)

    @staticmethod
    def _state(ticks: int, busy: bool, ready: bool) -> dict[str, object]:
        return {
            "schema": memory_card_probe.MEMORY_CARD_STATE_SCHEMA,
            "slot": 0,
            "present": True,
            "auto_eject_ticks": ticks,
            "busy": busy,
            "ready": ready,
        }
