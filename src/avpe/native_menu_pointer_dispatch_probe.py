"""Proof policy for dispatch-bound native menu pointer motion."""

import json
from pathlib import Path

from avpe.control_http import request_json
from avpe.menu_probe import (
    await_dispatched_pointer_follow_up,
    menu_pointer_state,
    menu_state,
)


def _move_through_dispatch(
    port: int,
    deadline: float,
    normalized_x: float,
    normalized_y: float,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    status, response, detail = request_json(
        port, "POST", "/input/menu-pointer-dispatch", {"x": normalized_x, "y": normalized_y}
    )
    if (
        status != 202
        or response is None
        or response.get("deferred") is not True
        or int(response.get("deferred_call_id", 0)) <= 0
    ):
        raise RuntimeError(
            "native menu pointer dispatch was not queued through game input: "
            f"HTTP {status}: {detail}"
        )
    for field, expected in (
        ("screen_x", normalized_x * 639.0),
        ("screen_y", normalized_y * 447.0),
    ):
        if abs(float(response.get(field, float("inf"))) - expected) > 0.05:
            raise RuntimeError(
                f"native menu pointer dispatch returned unexpected {field}: {response}"
            )

    dispatch, completion = await_dispatched_pointer_follow_up(
        port, deadline, int(response["deferred_call_id"])
    )
    state_status, state, state_detail = menu_pointer_state(port)
    if state_status != 200 or state is None:
        raise RuntimeError(
            f"native menu pointer state returned HTTP {state_status}: {state_detail}"
        )
    if response.get("pointer") != state.get("pointer"):
        raise RuntimeError(
            "dispatched menu pointer state lost its pointer identity: "
            f"move={response}, dispatch={dispatch}, state={state}"
        )
    for field, expected in (
        ("menu_x", normalized_x * 639.0),
        ("menu_y", normalized_y * 447.0),
    ):
        if abs(float(state.get(field, float("inf"))) - expected) > 0.05:
            raise RuntimeError(
                f"dispatched menu pointer state returned unexpected {field}: {state}"
            )
    return response, dispatch, completion, state


def probe_native_menu_pointer_dispatch(
    port: int, deadline: float, output_dir: Path
) -> dict[str, object]:
    source_status, source_menu, source_detail = menu_state(port)
    if source_status != 200 or source_menu is None:
        raise RuntimeError(
            "native dispatched menu pointer source menu returned "
            f"HTTP {source_status}: {source_detail}"
        )
    move, dispatch, completion, state = _move_through_dispatch(port, deadline, 0.675, 0.4)
    proof = {
        "source_menu": source_menu,
        "move": move,
        "dispatch": dispatch,
        "completion": completion,
        "state": state,
    }
    (output_dir / "menu-pointer-dispatch-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    )
    return proof
