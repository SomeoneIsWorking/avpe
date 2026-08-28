import unittest

from avpe.native_camera_probe import probe_native_camera


def camera_response(action: str, before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    return {
        "action": action,
        "before": before,
        "after": after,
        "stack_restored": True,
        "elapsed_cycles": 100,
    }


class NativeCameraProbeTests(unittest.TestCase):
    def test_probe_requires_each_guest_owned_transition(self) -> None:
        base = {
            "pointer": "0x1000",
            "pointer_input_type": 0,
            "camera": "0x2000",
            "move": [0.0, 0.0],
            "cursor": [1.0, 2.0, 3.0],
            "minimap_mode": False,
        }
        responses = [
            camera_response("move", base, {**base, "pointer_input_type": 1, "move": [25.0, 0.0]}),
            camera_response("zoom", base, {**base, "minimap_mode": True, "cursor": [4.0, 2.0, 3.0]}),
            camera_response("rotate", {**base, "minimap_mode": True}, {**base, "cursor": [5.0, 2.0, 3.0]}),
        ]

        def request(_method: str, _path: str, _payload: dict[str, object]) -> tuple[int, dict[str, object], str]:
            return 200, responses.pop(0), ""

        proof = probe_native_camera(request)

        self.assertEqual(proof["selector_mode"], 1)
        self.assertTrue(proof["minimap_mode_after_zoom"])
        self.assertTrue(proof["minimap_cursor_changed_after_rotate"])

    def test_probe_rejects_camera_call_without_guest_move_effect(self) -> None:
        state = {
            "pointer": "0x1000",
            "pointer_input_type": 1,
            "camera": "0x2000",
            "move": [0.0, 0.0],
            "cursor": [1.0, 2.0, 3.0],
            "minimap_mode": False,
        }
        responses = [
            camera_response("move", state, state),
        ]

        def request(_method: str, _path: str, payload: dict[str, object]) -> tuple[int, dict[str, object], str]:
            response = dict(responses[0])
            response["action"] = payload["action"]
            return 200, response, ""

        with self.assertRaisesRegex(RuntimeError, "camera move did not change"):
            probe_native_camera(request)


if __name__ == "__main__":
    unittest.main()
