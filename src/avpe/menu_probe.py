"""Shared typed-menu diagnostic calls for surfaceless AVP:E probes."""

import json
import time
from pathlib import Path

from avpe.control_http import request_bytes, request_json


MENU_INPUT_ANALOG = ("0x00000000", "0xffffffff", "0x00125230")


def menu_action(
    port: int,
    action: str,
) -> tuple[int, dict[str, object] | None, str]:
    return request_json(port, "POST", "/input/menu-action", {"action": action})


def run_ready_menu_action(
    port: int,
    deadline: float,
    action: str,
    menu_vtable: object,
    focused_item_action: object,
) -> tuple[dict[str, object], dict[str, object]]:
    """Apply one exact menu action through the title's physical-pad path."""
    body = {
        "action": action,
        "when_menu_vtable": _canonical_word(menu_vtable, "menu vtable"),
        "when_focused_item_action": _canonical_word(
            focused_item_action, "focused item action"
        ),
    }
    status, response, detail = request_json(port, "POST", "/input/menu-action", body)
    action_id = _integer(response.get("readiness_action_id")) if response is not None else -1
    if status != 202 or response is None or response.get("awaiting_readiness") is not True \
            or action_id <= 0:
        raise RuntimeError(
            "native ready menu action was not admitted through physical input: "
            f"HTTP {status}: {detail}"
        )
    return response, await_ready_menu_action(port, deadline, action_id)


def await_ready_menu_action(
    port: int, deadline: float, action_id: int
) -> dict[str, object]:
    """Wait for one admitted menu readiness action to dispatch or reject."""
    last_state: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, body = request_bytes(port, "GET", "/input/menu-readiness")
        detail = body.decode(errors="replace").strip()
        try:
            state = json.loads(body)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"menu readiness returned invalid JSON: HTTP {status}: {detail}"
            ) from error
        if status != 200 or not isinstance(state, dict):
            raise RuntimeError(f"menu readiness returned HTTP {status}: {detail}")
        if _integer(state.get("id")) != action_id:
            raise RuntimeError(
                f"menu readiness did not identify action {action_id}: {state}"
            )
        last_state = state
        if state.get("state") == "dispatched" \
                and _integer(state.get("dispatched_id")) == action_id:
            return state
        if state.get("state") == "rejected" \
                and _integer(state.get("rejected_id")) == action_id:
            raise RuntimeError(f"menu readiness action {action_id} was rejected: {state}")
        if state.get("state") != "pending":
            raise RuntimeError(f"menu readiness action {action_id} entered an invalid state: {state}")
        time.sleep(0.05)
    raise RuntimeError(
        f"menu readiness action {action_id} did not dispatch before its deadline: {last_state}"
    )


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


def menu_input_dispatch_count(snapshot: dict[str, object], menu: object) -> int:
    menu_address = _u32(menu)
    if menu_address is None:
        raise RuntimeError(f"menu dispatch owner is invalid: {menu!r}")
    for callback in snapshot.get("callbacks", []):
        if not isinstance(callback, dict):
            continue
        member = callback.get("member_function")
        if _u32(callback.get("owner")) != menu_address \
                or not isinstance(member, list) \
                or tuple(member) != MENU_INPUT_ANALOG:
            continue
        dispatches = callback.get("dispatches")
        if isinstance(dispatches, int) and not isinstance(dispatches, bool):
            return dispatches
    return 0


def menu_input_dispatch_counts(snapshot: dict[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for callback in snapshot.get("callbacks", []):
        if not isinstance(callback, dict):
            continue
        owner = callback.get("owner")
        member = callback.get("member_function")
        dispatches = callback.get("dispatches")
        if _u32(owner) is None or not isinstance(owner, str) \
                or not isinstance(member, list) \
                or tuple(member) != MENU_INPUT_ANALOG \
                or not isinstance(dispatches, int) \
                or isinstance(dispatches, bool):
            continue
        counts[owner.lower()] = dispatches
    return counts


def await_following_menu_input_dispatch(
    port: int,
    deadline: float,
    menu: object,
    completed_action: dict[str, object],
) -> dict[str, object]:
    baseline = menu_input_dispatch_count(completed_action, menu)
    last_dispatch: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, dispatch, detail = input_dispatch_state(port)
        if status != 200 or dispatch is None:
            raise RuntimeError(
                f"input dispatch state returned HTTP {status}: {detail}"
            )
        last_dispatch = dispatch
        if menu_input_dispatch_count(dispatch, menu) > baseline:
            return dispatch
        time.sleep(0.05)
    raise RuntimeError(
        "menu did not complete a following normal input dispatch: "
        f"menu={menu!r}, baseline={baseline}, last_dispatch={last_dispatch}"
    )


def await_different_menu_input_dispatch(
    port: int,
    deadline: float,
    previous_menu: object,
    completed_action: dict[str, object],
    expected_vtable: str | None = None,
) -> tuple[str, dict[str, object]]:
    previous_address = _u32(previous_menu)
    if previous_address is None:
        raise RuntimeError(f"previous menu dispatch owner is invalid: {previous_menu!r}")
    baseline = menu_input_dispatch_counts(completed_action)
    last_dispatch: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, dispatch, detail = input_dispatch_state(port)
        if status != 200 or dispatch is None:
            raise RuntimeError(
                f"input dispatch state returned HTTP {status}: {detail}"
            )
        last_dispatch = dispatch
        for callback in dispatch.get("callbacks", []):
            if not isinstance(callback, dict):
                continue
            owner = callback.get("owner")
            counts = menu_input_dispatch_counts({"callbacks": [callback]})
            if not isinstance(owner, str) or owner.lower() not in counts:
                continue
            normalized_owner = owner.lower()
            if int(normalized_owner, 0) == previous_address \
                    or counts[normalized_owner] <= baseline.get(normalized_owner, 0) \
                    or expected_vtable is not None \
                    and callback.get("owner_vtable") != expected_vtable:
                continue
            return normalized_owner, dispatch
        time.sleep(0.05)
    raise RuntimeError(
        "menu transition produced no different normal input owner: "
        f"previous_menu={previous_menu!r}, expected_vtable={expected_vtable!r}, "
        f"baseline={baseline}, "
        f"last_dispatch={last_dispatch}"
    )


def complete_menu_action(
    port: int,
    deadline: float,
    action: str,
    context: str,
) -> dict[str, object]:
    """Complete either an ordinary dispatched action or a synchronous modal action."""
    status, response, detail = menu_action(port, action)
    if status == 202 and response is not None:
        action_id = _integer(response.get("dispatch_action_id"))
        if action_id > 0:
            return await_dispatched_menu_action(port, deadline, action_id)
        call_id = _integer(response.get("deferred_call_id"))
        if call_id <= 0:
            raise RuntimeError(
                f"{context} returned no dispatch or deferred completion id: {detail}"
            )
        return await_deferred_call(port, deadline, call_id, context)
    if status != 200 or response is None:
        raise RuntimeError(f"{context} failed: HTTP {status}: {detail}")
    return response


def await_settled_menu_state(
    port: int,
    deadline: float,
    context: str,
    *,
    require_available: bool = False,
) -> tuple[int, dict[str, object]]:
    """Observe menu state; optionally wait through unavailable/ambiguous owners."""
    last_status = 0
    last_detail = ""
    while time.monotonic() < deadline:
        status, state, detail = menu_state(port)
        if state is not None and (status == 200 or (status == 409 and not require_available)):
            return status, state
        if status not in (409, 500):
            raise RuntimeError(f"{context} failed: HTTP {status}: {detail}")
        last_status, last_detail = status, detail
        time.sleep(0.05)
    raise RuntimeError(f"{context} did not settle: HTTP {last_status}: {last_detail}")


def await_menu_transition(
    port: int,
    deadline: float,
    before: dict[str, object],
    context: str,
) -> tuple[int, dict[str, object]]:
    before_identity = _menu_identity(before)
    last_status = 0
    last_detail = ""
    last_state: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, state, detail = menu_state(port)
        if status == 409 and state is not None:
            return status, state
        if status == 200 and state is not None:
            last_state = state
            if _menu_identity(state) != before_identity:
                return status, state
        elif status not in (409, 500):
            raise RuntimeError(f"{context} failed: HTTP {status}: {detail}")
        last_status, last_detail = status, detail
        time.sleep(0.05)
    raise RuntimeError(
        f"{context} did not change game-owned menu state: "
        f"HTTP {last_status}: {last_detail}; last_state={last_state}"
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


def _u32(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = int(value, 0)
    except ValueError:
        return None
    return parsed if 0 <= parsed <= 0xFFFFFFFF else None


def _canonical_word(value: object, description: str) -> str:
    parsed = _u32(value)
    if parsed is None:
        raise ValueError(f"{description} is not an unsigned hexadecimal word: {value!r}")
    return f"0x{parsed:08x}"


def _menu_identity(state: dict[str, object]) -> tuple[object, ...]:
    return tuple(
        state.get(field)
        for field in ("menu", "menu_vtable", "focus_object", "focused_item_action")
    )
