"""Acceptance policy for native AVP:E camera and minimap input."""

from collections.abc import Callable
from typing import Any


def _state(response: dict[str, Any], name: str) -> dict[str, Any]:
    value = response.get(name)
    if not isinstance(value, dict):
        raise RuntimeError(f"camera response has no {name} state: {response}")
    return value


def _vector(state: dict[str, Any], name: str, length: int) -> list[float]:
    value = state.get(name)
    if not isinstance(value, list) or len(value) != length \
            or not all(isinstance(item, (int, float)) for item in value):
        raise RuntimeError(f"camera state has invalid {name}: {state}")
    return [float(item) for item in value]


def _require_success(response: dict[str, Any], action: str) -> None:
    if response.get("action") != action or response.get("stack_restored") is not True:
        raise RuntimeError(f"native camera {action} call was not restored: {response}")
    if int(response.get("elapsed_cycles", 0)) <= 0:
        raise RuntimeError(f"native camera {action} call has no cycle evidence: {response}")
    before = _state(response, "before")
    after = _state(response, "after")
    if before.get("camera") != after.get("camera") \
            or before.get("pointer") != after.get("pointer"):
        raise RuntimeError(f"native camera {action} changed singleton identity: {response}")


def probe_native_camera(
    request: Callable[
        [str, str, dict[str, object]], tuple[int, dict[str, object] | None, str]
    ],
) -> dict[str, object]:
    """Prove camera movement, selector mode, minimap zoom, and minimap pan."""

    calls: list[dict[str, object]] = []
    for action, payload in (
        ("move", {"action": "move", "x": 1.0, "y": 0.0}),
        ("zoom", {"action": "zoom", "x": 1.0}),
        ("rotate", {"action": "rotate", "x": 0.2, "y": 0.0}),
    ):
        status, response, detail = request("POST", "/input/camera", payload)
        if status != 200 or response is None:
            raise RuntimeError(f"native camera {action} returned HTTP {status}: {detail}")
        _require_success(response, action)
        calls.append(response)

    move_before = _state(calls[0], "before")
    move_after = _state(calls[0], "after")
    if move_after.get("pointer_input_type") != 1:
        raise RuntimeError(f"camera move did not retain absolute selector mode: {calls[0]}")
    move_before_vector = _vector(move_before, "move", 2)
    move_after_vector = _vector(move_after, "move", 2)
    if move_before_vector == move_after_vector:
        raise RuntimeError(f"camera move did not change game-owned move state: {calls[0]}")

    zoom_after = _state(calls[1], "after")
    zoom_cursor = _vector(zoom_after, "cursor", 3)
    if zoom_after.get("minimap_mode") is not True or not all(abs(value) < 1_000_000 for value in zoom_cursor):
        raise RuntimeError(f"camera zoom did not enter a valid minimap mode: {calls[1]}")

    rotate_before = _state(calls[2], "before")
    rotate_after = _state(calls[2], "after")
    before_cursor = _vector(rotate_before, "cursor", 3)
    after_cursor = _vector(rotate_after, "cursor", 3)
    if before_cursor == after_cursor:
        raise RuntimeError(f"camera rotate did not move the minimap cursor: {calls[2]}")

    return {
        "actions": calls,
        "selector_mode": move_after.get("pointer_input_type"),
        "minimap_mode_after_zoom": zoom_after.get("minimap_mode"),
        "minimap_cursor_changed_after_rotate": before_cursor != after_cursor,
    }
