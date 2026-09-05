"""Surfaceless Zono-logo cancellation and restored-player regression scenario."""

import time
from pathlib import Path

from avpe.control_http import request_json
from avpe.menu_probe import menu_state, run_menu_action
from avpe.native_title_probe import (
    start_title_transition_observation,
    title_transition_snapshot,
)


def _cancel_logo(port: int, deadline: float) -> dict[str, object]:
    queued, completed = run_menu_action(port, deadline, "activate")
    if queued.get("source") != "movie-cancellation":
        raise RuntimeError(f"logo scenario did not reach movie admission: {queued}")
    last = None
    while time.monotonic() < deadline:
        status, menu, detail = menu_state(port)
        last = (status, detail)
        if status == 200:
            if menu is None or menu.get("menu_vtable") != "0x00342A50" \
                    or menu.get("callback_count") != 8:
                raise RuntimeError(f"logo cancellation reached an unexpected menu: {menu}")
            return {"request": queued, "completion": completed, "title": menu}
        if status not in (409, 500):
            raise RuntimeError(f"logo destination discovery failed: HTTP {status}: {detail}")
        time.sleep(0.05)
    raise RuntimeError(f"logo cancellation did not reach the title: last={last}")


def probe_native_movie_cancellation(
    port: int, deadline: float, statefile: Path,
) -> dict[str, object]:
    """Two explicit player lifetimes, never retries of a failed cancellation."""
    start_title_transition_observation(port)
    first = _cancel_logo(port, deadline)
    observation = title_transition_snapshot(port)
    if observation["press_start"]["ordinal"] != 0 \
            or observation["profile_create"]["ordinal"] != 0:
        raise RuntimeError(f"logo input leaked into title activation: {observation}")
    status, pad, detail = request_json(port, "GET", "/debug", {})
    if status != 200 or pad is None or pad.get("inject_inputs") != "0000" \
            or pad.get("inject_wire") != "0000":
        raise RuntimeError(f"logo scenario observed controller injection: {detail}")

    status, _, detail = request_json(
        port, "POST", "/state/load", {"path": str(statefile.resolve())},
    )
    if status != 200:
        raise RuntimeError(f"logo state reload failed: HTTP {status}: {detail}")
    status, reset, detail = request_json(port, "GET", "/input/movie-cancellation", {})
    if status != 200 or reset is None or reset.get("state") != "idle" or reset.get("id") != 0:
        raise RuntimeError(f"restored player inherited cancellation state: {detail}")
    second = _cancel_logo(port, deadline)
    if second["request"]["movie_action_id"] <= first["request"]["movie_action_id"]:
        raise RuntimeError(f"restored player reused a cancellation ticket: {second}")
    return {"first": first, "title_observation": observation, "pad": pad,
            "reset": reset, "restored_player": second}
