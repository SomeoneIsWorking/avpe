"""Shared typed-menu diagnostic calls for surfaceless AVP:E probes."""

import json
import time
from pathlib import Path

from avpe.control_http import request_bytes, request_json


def menu_action(
    port: int,
    action: str,
) -> tuple[int, dict[str, object] | None, str]:
    return request_json(port, "POST", "/input/menu-action", {"action": action})


def menu_state(port: int) -> tuple[int, dict[str, object] | None, str]:
    status, body = request_bytes(port, "GET", "/input/menu")
    detail = body.decode(errors="replace").strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return status, None, detail
    return status, parsed if isinstance(parsed, dict) else None, detail


def menu_pointer_state(port: int) -> tuple[int, dict[str, object] | None, str]:
    status, body = request_bytes(port, "GET", "/input/menu-pointer")
    detail = body.decode(errors="replace").strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return status, None, detail
    return status, parsed if isinstance(parsed, dict) else None, detail


def capture_menu_snapshot(port: int, name: str, output_dir: Path) -> str:
    import hashlib

    status = 503
    bitmap = b""
    for _ in range(20):
        status, bitmap = request_bytes(port, "GET", "/snap")
        if status == 200:
            break
        time.sleep(0.05)
    if status != 200:
        raise RuntimeError(f"menu snapshot {name} returned HTTP {status}")
    (output_dir / name).write_bytes(bitmap)
    return hashlib.sha256(bitmap).hexdigest()


def input_dispatch_state(port: int) -> tuple[int, dict[str, object] | None, str]:
    status, body = request_bytes(port, "GET", "/input/dispatch")
    detail = body.decode(errors="replace").strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return status, None, detail
    return status, parsed if isinstance(parsed, dict) else None, detail


def await_deferred_call(
    port: int,
    deadline: float,
    call_id: int,
    description: str,
) -> dict[str, object]:
    completion: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, body = request_bytes(port, "GET", "/ee/deferred")
        if status != 200:
            raise RuntimeError(f"deferred status returned HTTP {status}")
        candidate = json.loads(body)
        if not isinstance(candidate, dict) or int(candidate.get("id", 0)) != call_id:
            raise RuntimeError(
                f"deferred status did not identify call {call_id}: {candidate}"
            )
        if candidate.get("state") in ("completed", "failed"):
            completion = candidate
            break
        time.sleep(0.05)
    if not deferred_completion_is_safe(completion):
        raise RuntimeError(
            f"deferred {description} did not complete safely: {completion}"
        )
    assert completion is not None
    return completion


def await_dispatched_pointer_motion(
    port: int,
    deadline: float,
    pointer_id: int,
) -> dict[str, object]:
    last_dispatch: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, dispatch, detail = input_dispatch_state(port)
        if status != 200 or dispatch is None:
            raise RuntimeError(
                f"input dispatch state returned HTTP {status}: {detail}"
            )
        last_dispatch = dispatch
        if int(dispatch.get("rejected_pointer_id", 0)) == pointer_id:
            raise RuntimeError(
                f"dispatched pointer motion {pointer_id} was rejected: {dispatch}"
            )
        if int(dispatch.get("injected_pointer_id", 0)) == pointer_id:
            return dispatch
        time.sleep(0.05)
    raise RuntimeError(
        "dispatched pointer motion did not inject: "
        f"pointer_id={pointer_id}, last_dispatch={last_dispatch}"
    )


def await_dispatched_menu_action(
    port: int,
    deadline: float,
    action_id: int,
) -> dict[str, object]:
    last_dispatch: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, dispatch, detail = input_dispatch_state(port)
        if status != 200 or dispatch is None:
            raise RuntimeError(
                f"input dispatch state returned HTTP {status}: {detail}"
            )
        last_dispatch = dispatch
        if int(dispatch.get("rejected_menu_action_id", 0)) == action_id:
            raise RuntimeError(
                f"dispatched menu action {action_id} was rejected: {dispatch}"
            )
        if int(dispatch.get("completed_menu_action_id", 0)) == action_id:
            return dispatch
        time.sleep(0.05)
    raise RuntimeError(
        "dispatched menu action did not inject: "
        f"action_id={action_id}, last_dispatch={last_dispatch}"
    )


def run_menu_action(
    port: int,
    deadline: float,
    action: str,
) -> tuple[dict[str, object], dict[str, object]]:
    status, response, detail = menu_action(port, action)
    if status != 202 or response is None or response.get("deferred") is not True:
        raise RuntimeError(
            f"native menu {action} was not queued through guest input dispatch: "
            f"HTTP {status}: {detail}"
        )
    action_id = _integer(response.get("dispatch_action_id"))
    if action_id > 0:
        completion = await_dispatched_menu_action(port, deadline, action_id)
        return response, completion
    call_id = _integer(response.get("deferred_call_id"))
    if call_id <= 0:
        raise RuntimeError(
            f"native menu {action} returned no dispatch or deferred completion id: {detail}"
        )
    completion = await_deferred_call(port, deadline, call_id, f"menu {action}")
    return response, completion


def deferred_completion_is_safe(value: object) -> bool:
    return bool(
        isinstance(value, dict)
        and value.get("state") == "completed"
        and value.get("succeeded") is True
        and value.get("stack_restored") is True
        and value.get("staging_address") != "0x00000000"
    )


def _integer(value: object) -> int:
    if isinstance(value, bool):
        return -1
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return -1
