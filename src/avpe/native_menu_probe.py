"""Native menu activation probes for surfaceless AVP:E control runs."""

import json
import time
from pathlib import Path

from avpe.menu_probe import (
    capture_menu_snapshot,
    menu_action,
    menu_state,
    run_deferred_menu_action,
)


def probe_native_menu(port: int, deadline: float, output_dir: Path) -> dict[str, object]:
    before_snapshot = capture_menu_snapshot(port, "menu-before.bmp", output_dir)
    down_results: list[dict[str, object]] = []
    initial_focus: str | None = None
    down_focus: str | None = None
    for _ in range(3):
        status, response, detail = menu_action(port, "down")
        if status != 200 or response is None:
            raise RuntimeError(f"native menu down returned HTTP {status}: {detail}")
        before = response.get("before")
        after = response.get("after")
        if not isinstance(before, dict) or not isinstance(after, dict) \
                or response.get("menu") == "0x00000000" \
                or int(response.get("callback_count", 0)) == 0:
            raise RuntimeError(f"native menu down returned invalid ownership state: {response}")
        if initial_focus is None:
            initial_focus = str(before.get("focus_object"))
        down_results.append(response)
        candidate = str(after.get("focus_object"))
        if candidate != initial_focus and candidate != "0x00000000":
            down_focus = candidate
            break
    if down_focus is None:
        raise RuntimeError(f"native menu down did not change game focus: {down_results}")
    source_menu = str(down_results[-1].get("menu"))
    activation_proof = _activate_menu(
        port, deadline, source_menu, before_snapshot, "menu-activated.bmp", output_dir)
    cancel, cancel_completion = run_deferred_menu_action(port, deadline, "cancel")
    canceled_menu = str(cancel.get("menu"))
    cancel_destination: dict[str, object] | None = None
    cancel_candidate: dict[str, object] | None = None
    cancel_status = 0
    cancel_detail = ""
    while time.monotonic() < deadline:
        cancel_status, candidate, cancel_detail = menu_state(port)
        if candidate is not None:
            cancel_candidate = candidate
        if cancel_status == 409:
            cancel_destination = {"menu_unavailable": True, "http_status": 409}
            break
        if cancel_status == 200 and candidate is not None \
                and candidate.get("menu") != canceled_menu:
            cancel_destination = candidate
            break
        time.sleep(0.05)
    if cancel_destination is None:
        raise RuntimeError(
            f"native menu cancel left canceled menu {canceled_menu} active: "
            f"cancel={cancel}, completion={cancel_completion}, "
            f"last_status={cancel_status}, last_detail={cancel_detail}, "
            f"last_menu={cancel_candidate}")

    proof = {
        "initial_focus": initial_focus,
        "down_focus": down_focus,
        "down_calls": down_results,
        **activation_proof,
        "cancel": cancel,
        "cancel_completion": cancel_completion,
        "cancel_destination": cancel_destination,
    }
    (output_dir / "menu-proof.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    return proof


def probe_native_menu_activation(port: int, deadline: float, output_dir: Path) -> dict[str, object]:
    before_snapshot = capture_menu_snapshot(port, "menu-activation-before.bmp", output_dir)
    status, source, detail = menu_action(port, "down")
    if status != 200 or source is None or source.get("menu") == "0x00000000" \
            or int(source.get("callback_count", 0)) == 0:
        raise RuntimeError(f"could not inspect source menu through native action: {detail}")
    proof = {
        "source": source,
        **_activate_menu(
            port, deadline, str(source["menu"]), before_snapshot,
            "menu-activation-after.bmp", output_dir, require_render_change=False),
    }
    (output_dir / "menu-activation-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n")
    return proof


def _activate_menu(
    port: int,
    deadline: float,
    source_menu: str,
    before_snapshot: str,
    artifact_name: str,
    output_dir: Path,
    require_destination: bool = True,
    require_render_change: bool = True,
) -> dict[str, object]:
    activation, completion = run_deferred_menu_action(port, deadline, "activate")
    destination: dict[str, object] | None = None
    if require_destination:
        while time.monotonic() < deadline:
            destination_status, candidate, _ = menu_state(port)
            if destination_status == 200 and candidate is not None \
                    and candidate.get("menu") != source_menu:
                destination = candidate
                break
            time.sleep(0.05)
    else:
        _, destination, _ = menu_state(port)
    if require_destination and destination is None:
        raise RuntimeError(
            "menu activation completed but no distinct destination menu became active; "
            f"source={source_menu}")
    activated_snapshot = capture_menu_snapshot(port, artifact_name, output_dir)
    if require_render_change and activated_snapshot == before_snapshot:
        raise RuntimeError("native menu activation left the rendered state unchanged")
    return {
        "activation": activation,
        "deferred_completion": completion,
        "destination": destination,
        "snapshots": {
            "before_sha256": before_snapshot,
            "activated_sha256": activated_snapshot,
        },
    }
