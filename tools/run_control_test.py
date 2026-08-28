#!/usr/bin/env python3
"""Run AVPE control tests without a native window or audio device."""

import argparse
import hashlib
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from avpe.cli import load_env
from avpe.control_test import (
    EXPECTED_SERIAL,
    build_argv,
    build_environment,
    find_bios,
    report_json_probe,
    status_is_verified,
)
from avpe.control_http import read_status, request_bytes, request_json, request_shutdown
from avpe.cursor import CursorObservation, detect_cursor
from avpe.memory_card_probe import prepare_memory_card_probe
from avpe.native_asset_probe import (
    await_asset_byte_trace,
    await_load_timing,
    await_native_stream_reads,
    capture_iso_oracle,
    probe_native_asset_cache,
    probe_native_assets,
    probe_native_cdvd_state_recovery,
    probe_native_asset_guest_reset,
    probe_native_ioman_state_recovery,
    probe_native_movie_reads,
    probe_native_stream_reads,
    write_asset_byte_trace,
)
from avpe.native_bios_probe import (
    add_arguments as add_bios_arguments,
    capture_bios_trace_if_requested,
    report_bios_trace,
    validate_arguments as validate_bios_arguments,
)
from avpe.menu_probe import (
    await_deferred_call,
    menu_action,
    menu_state,
    run_deferred_menu_action,
)
from avpe.native_mission_probe import (
    await_mission_load_timing,
    probe_marine_m1_transition,
)
from avpe.native_camera_probe import probe_native_camera
from avpe.native_assets import (
    NativeAssetError,
    manifest_sha256,
    provision_native_assets,
)
from avpe.pcsx2_config import ensure_test_config

ROOT = Path(__file__).resolve().parent.parent
PCSX2 = ROOT / "scratch" / "build" / "bin" / "pcsx2-qt"
DATA_DIR = ROOT / "scratch" / "control-test" / "pcsx2-home"
LOG_DIR = ROOT / "scratch" / "control-test" / "logs"
NATIVE_ASSET_DIR = ROOT / "scratch" / "native-assets"


def stop_process_group(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def mouse_button(
    port: int,
    button: str,
    edge: str,
) -> tuple[int, dict[str, object] | None, str]:
    return request_json(
        port, "POST", "/input/mouse-button", {"button": button, "edge": edge})


def menu_pointer_state(port: int) -> tuple[int, dict[str, object] | None, str]:
    status, body = request_bytes(port, "GET", "/input/menu-pointer")
    detail = body.decode(errors="replace").strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return status, None, detail
    return status, parsed if isinstance(parsed, dict) else None, detail


def stable_cursor_snapshot(
    port: int,
    expected_x: float,
    expected_y: float,
    deadline: float,
    artifact_name: str,
) -> tuple[CursorObservation, bytes]:
    previous: CursorObservation | None = None
    for _ in range(12):
        if time.monotonic() >= deadline:
            break
        status, bmp = request_bytes(port, "GET", "/snap")
        if status != 200:
            continue
        observation = detect_cursor(bmp, expected_x, expected_y)
        if observation is None:
            previous = None
            continue
        if previous is not None and abs(observation.x - previous.x) <= 2.0 \
                and abs(observation.y - previous.y) <= 2.0:
            artifact = LOG_DIR.parent / artifact_name
            artifact.write_bytes(bmp)
            return observation, bmp
        previous = observation
    raise RuntimeError(
        f"cursor did not stabilize near ({expected_x:.1f}, {expected_y:.1f})")


def probe_native_pointer(port: int, deadline: float) -> dict[str, object]:
    targets = (("p1", 128.0, 96.0), ("p2", 512.0, 96.0))
    results: dict[str, object] = {}
    observations: dict[str, CursorObservation] = {}
    for name, screen_x, screen_y in targets:
        normalized = {"x": screen_x / 639.0, "y": screen_y / 447.0}
        status, body = request_bytes(port, "POST", "/input/move-absolute", normalized)
        if status != 200:
            raise RuntimeError(
                f"native move {name} returned HTTP {status}: {body.decode(errors='replace').strip()}")
        response = json.loads(body)
        if not isinstance(response, dict):
            raise RuntimeError(f"native move {name} returned non-object JSON")
        if not response.get("stack_restored") or response.get("staging_address") == "0x00000000":
            raise RuntimeError(f"native move {name} did not attest restored guest staging: {response}")
        for field, expected in (("screen_x", screen_x), ("screen_y", screen_y),
                                ("observed_x", screen_x), ("observed_y", screen_y)):
            if abs(float(response.get(field, float("inf"))) - expected) > 0.05:
                raise RuntimeError(f"native move {name} returned unexpected {field}: {response}")
        observation, bmp = stable_cursor_snapshot(
            port, screen_x, screen_y, deadline, f"pointer-{name}.bmp")
        observations[name] = observation
        results[name] = {
            "request": normalized,
            "response": response,
            "cursor": observation.__dict__,
            "snapshot_sha256": hashlib.sha256(bmp).hexdigest(),
        }

    first = observations["p1"]
    second = observations["p2"]
    if second.x - first.x <= 300.0 or abs(second.y - first.y) > 8.0:
        raise RuntimeError(f"cursor positions are not distinct horizontal targets: {first}, {second}")

    status, body = request_bytes(
        port, "POST", "/input/move-absolute", {"x": 1.25, "y": 0.2})
    if status != 400:
        raise RuntimeError(
            f"out-of-range native move returned HTTP {status}, expected 400: "
            f"{body.decode(errors='replace').strip()}")
    negative, negative_bmp = stable_cursor_snapshot(
        port, 512.0, 96.0, deadline, "pointer-negative.bmp")
    if abs(negative.x - second.x) > 2.0 or abs(negative.y - second.y) > 2.0:
        raise RuntimeError(f"rejected move changed the rendered cursor: {second}, {negative}")
    results["negative"] = {
        "http_status": status,
        "cursor": negative.__dict__,
        "snapshot_sha256": hashlib.sha256(negative_bmp).hexdigest(),
    }
    proof_path = LOG_DIR.parent / "pointer-proof.json"
    proof_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    return results


def probe_native_mouse(port: int, deadline: float, statefile: Path) -> dict[str, object]:
    def reload_state() -> dict[str, object]:
        reload_status, loaded_state, reload_detail = request_json(
            port, "POST", "/state/load", {"path": str(statefile)})
        if reload_status != 200 or loaded_state is None \
                or loaded_state.get("loaded") is not True:
            raise RuntimeError(
                f"state reload returned HTTP {reload_status}: {reload_detail}")
        return loaded_state

    selection_x, selection_y = 240.0, 340.0
    status, move, detail = request_json(
        port, "POST", "/input/move-absolute",
        {"x": selection_x / 639.0, "y": selection_y / 447.0})
    if status != 200 or move is None:
        raise RuntimeError(f"selection move returned HTTP {status}: {detail}")

    status, primary_press, detail = mouse_button(port, "primary", "press")
    if status != 200 or primary_press is None:
        raise RuntimeError(f"primary press returned HTTP {status}: {detail}")
    if primary_press.get("handler") != "0x001B52C0":
        raise RuntimeError(f"primary press used the wrong game handler: {primary_press}")
    stable_cursor_snapshot(
        port, selection_x, selection_y, deadline, "mouse-primary-held.bmp")

    status, primary_release, detail = mouse_button(port, "primary", "release")
    if status != 200 or primary_release is None:
        raise RuntimeError(f"primary release returned HTTP {status}: {detail}")
    after_selection = primary_release.get("after")
    before_selection = primary_press.get("before")
    if primary_release.get("handler") != "0x001B52D0" \
            or not isinstance(after_selection, dict) \
            or int(after_selection.get("count", 0)) != 1 \
            or after_selection.get("selected_object") == "0x00000000":
        raise RuntimeError(f"primary release did not select one game object: {primary_release}")
    if isinstance(before_selection, dict) \
            and before_selection.get("selected_object") == after_selection.get("selected_object"):
        raise RuntimeError(f"primary click retained the previous selected object: {primary_release}")
    selected_object = after_selection["selected_object"]

    status, _, detail = mouse_button(port, "primary", "release")
    if status != 409:
        raise RuntimeError(
            f"duplicate primary release returned HTTP {status}, expected 409: {detail}")

    status, command_move, detail = request_json(
        port, "POST", "/input/move-absolute", {"x": 100.0 / 639.0, "y": 100.0 / 447.0})
    if status != 200 or command_move is None:
        raise RuntimeError(f"command move returned HTTP {status}: {detail}")

    status, secondary_press, detail = mouse_button(port, "secondary", "press")
    if status != 200 or secondary_press is None \
            or secondary_press.get("handler") != "0x001B5300":
        raise RuntimeError(f"secondary press failed or used the wrong game handler: {detail}")
    status, _, detail = mouse_button(port, "secondary", "press")
    if status != 409:
        raise RuntimeError(
            f"duplicate secondary press returned HTTP {status}, expected 409: {detail}")

    status, secondary_release, detail = mouse_button(port, "secondary", "release")
    if status != 200 or secondary_release is None:
        raise RuntimeError(f"secondary release returned HTTP {status}: {detail}")
    command_after = secondary_release.get("after")
    if secondary_release.get("handler") != "0x001B5310" \
            or not isinstance(command_after, dict) \
            or command_after.get("selected_object") != selected_object \
            or command_after.get("command_id") != "0x00060039":
        raise RuntimeError(
            f"secondary release did not record AVP:E move command 0x60039: {secondary_release}")

    status, _, detail = mouse_button(port, "wheel", "press")
    if status != 400:
        raise RuntimeError(f"unknown mouse button returned HTTP {status}, expected 400: {detail}")

    status, pointer_invalidation, detail = request_json(
        port, "POST", "/mem/write", {"addr": "0x00367720", "hex": "00000000"})
    if status != 200 or pointer_invalidation is None \
            or pointer_invalidation.get("written") != 4:
        raise RuntimeError(f"pointer invalidation returned HTTP {status}: {detail}")
    status, _, detail = mouse_button(port, "primary", "press")
    if status != 409:
        raise RuntimeError(
            f"invalid game pointer returned HTTP {status}, expected 409: {detail}")
    pointer_restore = reload_state()

    status, reset_press, detail = mouse_button(port, "primary", "press")
    if status != 200 or reset_press is None:
        raise RuntimeError(f"pre-state-load primary press returned HTTP {status}: {detail}")
    loaded = reload_state()
    status, _, detail = mouse_button(port, "primary", "release")
    if status != 409:
        raise RuntimeError(
            f"state load did not reset held button state; release returned HTTP {status}: {detail}")

    proof = {
        "selection_move": move,
        "primary_press": primary_press,
        "primary_release": primary_release,
        "command_move": command_move,
        "secondary_press": secondary_press,
        "secondary_release": secondary_release,
        "pointer_invalidation": pointer_invalidation,
        "pointer_restore": pointer_restore,
        "state_reset_press": reset_press,
        "state_reload": loaded,
        "negative_statuses": {
            "duplicate_primary_release": 409,
            "duplicate_secondary_press": 409,
            "unknown_button": 400,
            "invalid_pointer": 409,
            "release_after_state_load": 409,
        },
    }
    proof_path = LOG_DIR.parent / "mouse-proof.json"
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    return proof


def menu_snapshot(port: int, name: str) -> str:
    status = 503
    bmp = b""
    for _ in range(20):
        status, bmp = request_bytes(port, "GET", "/snap")
        if status == 200:
            break
        time.sleep(0.05)
    if status != 200:
        raise RuntimeError(f"menu snapshot {name} returned HTTP {status}")
    (LOG_DIR.parent / name).write_bytes(bmp)
    return hashlib.sha256(bmp).hexdigest()


def move_menu_pointer(
    port: int,
    deadline: float,
    normalized_x: float,
    normalized_y: float,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    status, response, detail = request_json(
        port, "POST", "/input/menu-pointer-move",
        {"x": normalized_x, "y": normalized_y})
    if status != 202 or response is None \
            or response.get("deferred") is not True \
            or int(response.get("deferred_call_id", 0)) <= 0:
        raise RuntimeError(
            "native menu pointer move was not queued through deferred execution: "
            f"HTTP {status}: {detail}")
    if response.get("stack_restored") is not True \
            or response.get("staging_address") == "0x00000000":
        raise RuntimeError(
            f"native menu pointer move did not restore guest staging: {response}")
    for field, expected in (
        ("screen_x", normalized_x * 639.0),
        ("screen_y", normalized_y * 447.0),
        ("observed_x", normalized_x * 639.0),
        ("observed_y", normalized_y * 447.0),
    ):
        if abs(float(response.get(field, float("inf"))) - expected) > 0.05:
            raise RuntimeError(
                f"native menu pointer move returned unexpected {field}: {response}")

    completion = await_deferred_call(
        port, deadline, int(response["deferred_call_id"]), "menu pointer hover")
    state_status, state, state_detail = menu_pointer_state(port)
    if state_status != 200 or state is None:
        raise RuntimeError(
            f"native menu pointer state returned HTTP {state_status}: {state_detail}")
    state_focus = state.get("before")
    if response.get("pointer") != state.get("pointer") \
            or not isinstance(state_focus, dict) \
            or state_focus.get("focus_object") == "0x00000000":
        raise RuntimeError(
            f"native menu pointer hover did not focus an item: move={response}, state={state}")
    return response, completion, state


def probe_native_menu_pointer(port: int, deadline: float) -> dict[str, object]:
    source_status, source_menu, source_detail = menu_state(port)
    if source_status != 200 or source_menu is None:
        raise RuntimeError(
            f"native menu pointer source menu returned HTTP {source_status}: {source_detail}")

    first_move, first_completion, first_state = move_menu_pointer(
        port, deadline, 0.7, 0.3)
    second_move, second_completion, second_state = move_menu_pointer(
        port, deadline, 0.7, 0.4)
    first_focus = first_state.get("before", {}).get("focus_object")
    second_focus = second_state.get("before", {}).get("focus_object")
    if first_focus == second_focus:
        raise RuntimeError(
            f"distinct menu pointer targets focused the same item: {first_state}, {second_state}")

    deferred_status, deferred_before_body = request_bytes(port, "GET", "/ee/deferred")
    if deferred_status != 200:
        raise RuntimeError(
            f"deferred status before rejected move returned HTTP {deferred_status}")
    deferred_before = json.loads(deferred_before_body)
    invalid_status, _, invalid_detail = request_json(
        port, "POST", "/input/menu-pointer-move", {"x": 1.25, "y": 0.4})
    if invalid_status != 400:
        raise RuntimeError(
            f"out-of-range menu pointer move returned HTTP {invalid_status}, expected 400: "
            f"{invalid_detail}")
    deferred_after_status, deferred_after_body = request_bytes(port, "GET", "/ee/deferred")
    if deferred_after_status != 200:
        raise RuntimeError(
            f"deferred status after rejected move returned HTTP {deferred_after_status}")
    deferred_after = json.loads(deferred_after_body)
    if deferred_after != deferred_before:
        raise RuntimeError(
            "rejected menu pointer move changed deferred execution state: "
            f"before={deferred_before}, after={deferred_after}")

    activation_status, activation, activation_detail = request_json(
        port, "POST", "/input/menu-pointer-activate", {})
    if activation_status != 202 or activation is None \
            or activation.get("deferred") is not True \
            or int(activation.get("deferred_call_id", 0)) <= 0:
        raise RuntimeError(
            "native menu pointer activation was not queued through deferred execution: "
            f"HTTP {activation_status}: {activation_detail}")
    activation_completion = await_deferred_call(
        port, deadline, int(activation["deferred_call_id"]), "menu pointer activation")

    destination: dict[str, object] | None = None
    while time.monotonic() < deadline:
        destination_status, candidate, _ = menu_state(port)
        if destination_status == 200 and candidate is not None \
                and candidate.get("menu") != source_menu.get("menu"):
            destination = candidate
            break
        time.sleep(0.05)
    if destination is None:
        raise RuntimeError(
            "menu pointer activation completed but no distinct destination menu became active; "
            f"source={source_menu}")

    proof = {
        "source_menu": source_menu,
        "first": {
            "move": first_move,
            "completion": first_completion,
            "state": first_state,
        },
        "second": {
            "move": second_move,
            "completion": second_completion,
            "state": second_state,
        },
        "negative": {
            "http_status": invalid_status,
            "deferred_state": deferred_after,
        },
        "activation": activation,
        "activation_completion": activation_completion,
        "destination": destination,
    }
    (LOG_DIR.parent / "menu-pointer-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n")
    return proof


def activate_menu(
    port: int,
    deadline: float,
    source_menu: str,
    before_snapshot: str,
    artifact_name: str,
    require_destination: bool = True,
    require_render_change: bool = True,
) -> dict[str, object]:
    activation, completion = run_deferred_menu_action(
        port, deadline, "activate")

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
            f"menu activation completed but no distinct destination menu became active; "
            f"source={source_menu}")
    activated_snapshot = menu_snapshot(port, artifact_name)
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


def probe_native_menu(port: int, deadline: float) -> dict[str, object]:
    before_snapshot = menu_snapshot(port, "menu-before.bmp")
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
    activation_proof = activate_menu(
        port, deadline, source_menu, before_snapshot, "menu-activated.bmp")
    cancel, cancel_completion = run_deferred_menu_action(
        port, deadline, "cancel")
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
    (LOG_DIR.parent / "menu-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n")
    return proof


def probe_native_menu_activation(port: int, deadline: float) -> dict[str, object]:
    before_snapshot = menu_snapshot(port, "menu-activation-before.bmp")
    status, source, detail = menu_action(port, "down")
    if status != 200 or source is None or source.get("menu") == "0x00000000" \
            or int(source.get("callback_count", 0)) == 0:
        raise RuntimeError(f"could not inspect source menu through native action: {detail}")
    proof = {
        "source": source,
        **activate_menu(
            port, deadline, str(source["menu"]), before_snapshot,
            "menu-activation-after.bmp", require_render_change=False),
    }
    (LOG_DIR.parent / "menu-activation-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n")
    return proof


def reserve_port(requested: int) -> tuple[int, socket.socket]:
    reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    reservation.bind(("127.0.0.1", requested))
    return reservation.getsockname()[1], reservation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--statefile", type=Path)
    parser.add_argument(
        "--memory-card-source",
        type=Path,
        help="copy a formatted PS2 card into the isolated profile and report byte changes",
    )
    parser.add_argument(
        "--use-native-assets",
        action="store_true",
        help="provision and admit the native asset store for an otherwise manual control run",
    )
    parser.add_argument("--probe-native-pointer", action="store_true",
                        help="prove two native cursor positions; requires --statefile")
    parser.add_argument("--probe-native-mouse", action="store_true",
                        help="prove native selection and command actions; requires --statefile")
    parser.add_argument("--probe-native-menu", action="store_true",
                        help="prove native directional focus and activation; requires a menu --statefile")
    parser.add_argument("--probe-native-menu-activate", action="store_true",
                        help="prove activation on a single-item menu; requires --statefile")
    parser.add_argument("--probe-native-menu-pointer", action="store_true",
                        help="prove native menu hover and pointer activation; requires --statefile")
    parser.add_argument("--probe-native-camera", action="store_true",
                        help="prove native camera, selector, and minimap input; requires --statefile")
    parser.add_argument("--probe-native-assets", action="store_true",
                        help="prove AVP:E asset opens reach the title-specific IOP boundary")
    parser.add_argument("--probe-native-asset-reads", action="store_true",
                        help="prove TBF reads use the validated host store while bootstrap remains optical")
    parser.add_argument("--probe-native-asset-cache", action="store_true",
                        help="prove native reads populate the bounded host asset cache")
    parser.add_argument("--probe-native-movie-reads", action="store_true",
                        help="prove a complete native EALOGO.PSS lifecycle; requires a clean boot and --memory-card-source")
    parser.add_argument("--probe-native-stream-reads", action="store_true",
                        help="prove native STREAMS sector reads; requires a clean boot and --memory-card-source")
    parser.add_argument(
        "--probe-native-marine-m1-transition",
        action="store_true",
        help="prove the clean-boot SetNextLevel-to-M1 native loader path; requires --memory-card-source",
    )
    parser.add_argument("--probe-native-ioman-state-recovery", action="store_true",
                        help="prove a live native descriptor survives save/load; requires a clean boot and --memory-card-source")
    parser.add_argument("--probe-native-cdvd-state-recovery", action="store_true",
                        help="prove a native CDVD mapping survives save/load; requires a clean boot and --memory-card-source")
    parser.add_argument("--probe-native-asset-reset", choices=("ioman", "cdvd"),
                        help="prove native guest state cleanup across a real in-process reset; requires a clean boot and --memory-card-source")
    parser.add_argument("--probe-asset-byte-trace", choices=("oracle", "native"),
                        help="capture bounded optical or native SHA-256 chunks from a clean boot")
    parser.add_argument("--asset-byte-trace-output", type=Path,
                        help="write --probe-asset-byte-trace JSON to this scratch path")
    parser.add_argument("--probe-load-timing", choices=("oracle", "native"),
                        help="capture the grounded startup load interval from a clean boot")
    parser.add_argument(
        "--load-timing-target",
        choices=("startup", "mission"),
        default="startup",
        help="select the startup or exact Marine M1 ShellLoadLevel timing boundary",
    )
    parser.add_argument("--load-timing-output", type=Path,
                        help="write --probe-load-timing JSON to this scratch path")
    add_bios_arguments(parser)
    parser.add_argument("--http-port", type=int, default=0,
                        help="control port; zero allocates an available loopback port")
    args = parser.parse_args()

    if args.seconds <= 0:
        parser.error("--seconds must be greater than zero")
    if not 0 <= args.http_port <= 65535:
        parser.error("--http-port must be between 0 and 65535")
    if args.statefile is not None and not args.statefile.is_file():
        parser.error(f"--statefile is not a file: {args.statefile}")
    if args.memory_card_source is not None and not args.memory_card_source.is_file():
        parser.error(f"--memory-card-source is not a file: {args.memory_card_source}")
    native_input_probe_requested = any((
        args.probe_native_pointer,
        args.probe_native_mouse,
        args.probe_native_menu,
        args.probe_native_menu_activate,
        args.probe_native_menu_pointer,
        args.probe_native_camera,
    ))
    if native_input_probe_requested and args.statefile is None:
        parser.error("native input probes require --statefile")
    native_asset_probe_count = sum((
        args.probe_native_assets,
        args.probe_native_asset_reads,
        args.probe_native_asset_cache,
        args.probe_native_movie_reads,
        args.probe_native_stream_reads,
        args.probe_native_marine_m1_transition,
        args.probe_native_ioman_state_recovery,
        args.probe_native_cdvd_state_recovery,
        bool(args.probe_native_asset_reset),
    ))
    if native_asset_probe_count > 1:
        parser.error("choose only one native asset probe")
    if args.probe_native_movie_reads and args.statefile is not None:
        parser.error("--probe-native-movie-reads requires a clean boot without --statefile")
    if args.probe_native_movie_reads and args.memory_card_source is None:
        parser.error("--probe-native-movie-reads requires --memory-card-source until native saves replace the card path")
    if args.probe_native_stream_reads and args.statefile is not None:
        parser.error("--probe-native-stream-reads requires a clean boot without --statefile")
    if args.probe_native_stream_reads and args.memory_card_source is None:
        parser.error("--probe-native-stream-reads requires --memory-card-source until native saves replace the card path")
    if args.probe_native_marine_m1_transition and args.statefile is not None:
        parser.error(
            "--probe-native-marine-m1-transition requires a clean boot without --statefile"
        )
    if args.probe_native_marine_m1_transition and args.memory_card_source is None:
        parser.error(
            "--probe-native-marine-m1-transition requires --memory-card-source until native saves replace the card path"
        )
    if args.probe_native_marine_m1_transition and args.probe_asset_byte_trace:
        parser.error("--probe-native-marine-m1-transition must run without asset byte tracing")
    native_recovery_requested = (
        args.probe_native_ioman_state_recovery
        or args.probe_native_cdvd_state_recovery
    )
    if native_recovery_requested and args.statefile is not None:
        parser.error("native asset recovery probes require a clean boot without --statefile")
    if native_recovery_requested and args.memory_card_source is None:
        parser.error("native asset recovery probes require --memory-card-source until native saves replace the card path")
    if args.probe_native_asset_reset and args.statefile is not None:
        parser.error("--probe-native-asset-reset requires a clean boot without --statefile")
    if args.probe_native_asset_reset and args.memory_card_source is None:
        parser.error("--probe-native-asset-reset requires --memory-card-source until native saves replace the card path")
    if args.probe_asset_byte_trace and args.statefile is not None:
        parser.error("--probe-asset-byte-trace requires a clean boot without --statefile")
    if args.probe_asset_byte_trace and args.memory_card_source is None:
        parser.error("--probe-asset-byte-trace requires --memory-card-source until native saves replace the card path")
    if args.asset_byte_trace_output is not None and not args.probe_asset_byte_trace:
        parser.error("--asset-byte-trace-output requires --probe-asset-byte-trace")
    if args.probe_load_timing and args.statefile is not None:
        parser.error("--probe-load-timing requires a clean boot without --statefile")
    if args.probe_load_timing and args.memory_card_source is None:
        parser.error("--probe-load-timing requires --memory-card-source until native saves replace the card path")
    if args.load_timing_output is not None and not args.probe_load_timing:
        parser.error("--load-timing-output requires --probe-load-timing")
    if args.load_timing_target != "startup" and not args.probe_load_timing:
        parser.error("--load-timing-target requires --probe-load-timing")
    if args.probe_load_timing and (native_asset_probe_count or args.probe_asset_byte_trace):
        parser.error("--probe-load-timing must run without other asset probes or byte tracing")
    validate_bios_arguments(args, parser)
    probe_requested = (
        native_input_probe_requested
        or args.probe_native_assets
        or args.probe_native_asset_reads
        or args.probe_native_asset_cache
        or args.probe_native_movie_reads
        or args.probe_native_stream_reads
        or args.probe_native_marine_m1_transition
        or native_recovery_requested
        or args.probe_native_asset_reset
        or args.probe_asset_byte_trace
        or args.probe_load_timing
        or args.probe_bios_trace
    )

    if not PCSX2.is_file():
        print(f"FATAL built PCSX2 missing: {PCSX2}", file=sys.stderr)
        return 2

    project_env = load_env()
    chd = Path(project_env.get("AVPE_CHD", ""))
    bios = find_bios(project_env.get("AVPE_BIOS_DIR", ""))
    if not chd.is_file():
        print(f"FATAL AVPE_CHD missing or invalid: {chd}", file=sys.stderr)
        return 2
    if bios is None:
        print("FATAL no usable BIOS in AVPE_BIOS_DIR", file=sys.stderr)
        return 2

    native_asset_root: Path | None = None
    native_asset_manifest_sha256: str | None = None
    if (args.use_native_assets or args.probe_native_asset_reads
            or args.probe_native_asset_cache
            or args.probe_native_movie_reads
            or args.probe_native_stream_reads
            or args.probe_native_marine_m1_transition
            or native_recovery_requested
            or args.probe_native_asset_reset
            or args.probe_asset_byte_trace
            or args.probe_load_timing == "native"):
        try:
            native_asset_root = provision_native_assets(chd, NATIVE_ASSET_DIR)
            native_asset_manifest_sha256 = manifest_sha256(native_asset_root)
        except (NativeAssetError, OSError) as error:
            print(f"FATAL native asset store: {error}", file=sys.stderr)
            return 2

    try:
        card_probe = (
            prepare_memory_card_probe(args.memory_card_source, DATA_DIR)
            if args.memory_card_source is not None
            else None
        )
    except RuntimeError as error:
        print(f"FATAL {error}", file=sys.stderr)
        return 2
    ensure_test_config(
        DATA_DIR,
        bios,
        card_probe.working.name if card_probe is not None else None,
    )
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        port, port_reservation = reserve_port(args.http_port)
    except OSError as error:
        print(f"FATAL control port {args.http_port} is unavailable: {error}", file=sys.stderr)
        return 2
    nonce = secrets.token_hex(16)
    argv = build_argv(PCSX2, DATA_DIR, LOG_DIR / "emulog.txt", chd, args.statefile)
    env = build_environment(
        os.environ,
        port,
        nonce,
        native_asset_root=native_asset_root,
        native_asset_manifest_sha256=native_asset_manifest_sha256,
        asset_byte_trace_mode=args.probe_asset_byte_trace,
        asset_load_timing_mode=args.probe_load_timing,
        asset_load_timing_target=(
            args.load_timing_target
            if args.probe_load_timing and args.load_timing_target != "startup"
            else None
        ),
    )
    stdout = (LOG_DIR / "stdout.log").open("wb")
    try:
        port_reservation.close()
        proc = subprocess.Popen(argv, env=env, stdout=stdout, stderr=subprocess.STDOUT,
                                start_new_session=True)
    except OSError as error:
        stdout.close()
        print(f"FATAL could not start control test: {error}", file=sys.stderr)
        return 2
    print(f"control-test pid={proc.pid} port={port} display=surfaceless audio=null", flush=True)

    def handle_signal(_signum: int, _frame: object) -> None:
        stop_process_group(proc)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    deadline = time.monotonic() + args.seconds
    boot_status: dict[str, str] | None = None
    pointer_proof: dict[str, object] | None = None
    mouse_proof: dict[str, object] | None = None
    menu_proof: dict[str, object] | None = None
    menu_activation_proof: dict[str, object] | None = None
    menu_pointer_proof: dict[str, object] | None = None
    camera_proof: dict[str, object] | None = None
    native_assets_proof: dict[str, object] | None = None
    native_asset_cache_proof: dict[str, object] | None = None
    native_movie_reads_proof: dict[str, object] | None = None
    native_stream_reads_proof: dict[str, object] | None = None
    native_marine_m1_proof: dict[str, object] | None = None
    native_asset_recovery_proof: dict[str, object] | None = None
    native_asset_reset_proof: dict[str, object] | None = None
    asset_byte_trace: dict[str, object] | None = None
    load_timing: dict[str, object] | None = None
    bios_trace: dict[str, object] | None = None
    probe_error: str | None = None
    graceful_shutdown = False
    try:
        while proc.poll() is None and time.monotonic() < deadline:
            status = read_status(port)
            if status_is_verified(status, nonce):
                boot_status = status
                if args.probe_native_assets or args.probe_native_asset_reads:
                    try:
                        native_assets_proof = probe_native_assets(
                            port,
                            deadline,
                            args.probe_native_asset_reads,
                            LOG_DIR.parent,
                        )
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_asset_cache:
                    try:
                        native_asset_cache_proof = probe_native_asset_cache(
                            port, deadline, LOG_DIR.parent
                        )
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_movie_reads:
                    try:
                        native_movie_reads_proof = probe_native_movie_reads(
                            port, deadline, LOG_DIR.parent
                        )
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_stream_reads:
                    try:
                        native_stream_reads_proof = probe_native_stream_reads(
                            port, deadline, LOG_DIR.parent
                        )
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_marine_m1_transition:
                    try:
                        await_native_stream_reads(
                            port,
                            deadline,
                            "native MENU01 readiness before the M1 transition",
                        )
                        native_marine_m1_proof = probe_marine_m1_transition(
                            port,
                            deadline,
                            LOG_DIR.parent,
                            require_native_assets=True,
                        )
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_ioman_state_recovery:
                    try:
                        native_asset_recovery_proof = (
                            probe_native_ioman_state_recovery(
                                port, deadline, LOG_DIR.parent
                            )
                        )
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_cdvd_state_recovery:
                    try:
                        native_asset_recovery_proof = (
                            probe_native_cdvd_state_recovery(
                                port, deadline, LOG_DIR.parent
                            )
                        )
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_asset_reset:
                    try:
                        native_asset_reset_proof = probe_native_asset_guest_reset(
                            port, deadline, LOG_DIR.parent, args.probe_native_asset_reset
                        )
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_asset_byte_trace and probe_error is None:
                    try:
                        await_native_stream_reads(
                            port,
                            deadline,
                            "native MENU01 stream reads before byte capture",
                        )
                        if args.probe_asset_byte_trace == "oracle":
                            capture_iso_oracle(port)
                        asset_byte_trace = await_asset_byte_trace(
                            port, deadline, args.probe_asset_byte_trace)
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_load_timing and probe_error is None:
                    try:
                        if args.load_timing_target == "mission":
                            startup_backend_timing = await_load_timing(
                                port, deadline, args.probe_load_timing
                            )
                            transition = probe_marine_m1_transition(
                                port,
                                deadline,
                                LOG_DIR.parent,
                                require_native_assets=(
                                    args.probe_load_timing == "native"
                                ),
                            )
                            load_timing = await_mission_load_timing(
                                port, deadline, args.probe_load_timing
                            )
                            load_timing["mission_transition_proof"] = transition
                            load_timing["startup_backend_timing"] = (
                                startup_backend_timing
                            )
                        else:
                            load_timing = await_load_timing(
                                port, deadline, args.probe_load_timing
                            )
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if probe_error is None:
                    bios_trace, bios_error = capture_bios_trace_if_requested(
                        args.probe_bios_trace, port, probe_error
                    )
                    if bios_error is not None:
                        probe_error = bios_error
                if args.probe_native_pointer and probe_error is None:
                    try:
                        pointer_proof = probe_native_pointer(port, deadline)
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_mouse and probe_error is None:
                    try:
                        mouse_proof = probe_native_mouse(port, deadline, args.statefile)
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_menu and probe_error is None:
                    try:
                        menu_proof = probe_native_menu(port, deadline)
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_menu_activate and probe_error is None:
                    try:
                        menu_activation_proof = probe_native_menu_activation(port, deadline)
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_menu_pointer and probe_error is None:
                    try:
                        menu_pointer_proof = probe_native_menu_pointer(port, deadline)
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if args.probe_native_camera and probe_error is None:
                    try:
                        camera_proof = probe_native_camera(
                            lambda method, path, payload: request_json(
                                port, method, path, payload
                            )
                        )
                    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                        probe_error = str(error)
                if probe_requested:
                    break
            time.sleep(0.1)
        if proc.poll() is None and request_shutdown(port):
            try:
                proc.wait(timeout=10)
                graceful_shutdown = True
            except subprocess.TimeoutExpired:
                pass
    finally:
        stop_process_group(proc)
        stdout.close()

    card_proof: dict[str, object] | None = None
    if card_probe is not None:
        try:
            card_proof = card_probe.observe()
        except RuntimeError as error:
            print(f"FATAL {error}; see {LOG_DIR}", file=sys.stderr)
            return 1
        (LOG_DIR.parent / "memory-card-proof.json").write_text(
            json.dumps(card_proof, indent=2, sort_keys=True) + "\n"
        )
        print(
            f"control-test memory-card proof={json.dumps(card_proof, sort_keys=True)}",
            flush=True,
        )

    if proc.returncode != 0:
        print(f"FATAL control test exited rc={proc.returncode}; see {LOG_DIR}", file=sys.stderr)
        return 1
    if not graceful_shutdown:
        print(f"FATAL control test did not complete graceful shutdown; see {LOG_DIR}", file=sys.stderr)
        return 1
    if boot_status is None:
        print(f"FATAL {EXPECTED_SERIAL} never reached Running state; see {LOG_DIR}", file=sys.stderr)
        return 1
    print(f"control-test verified status={json.dumps(boot_status, sort_keys=True)}", flush=True)
    if args.probe_native_assets or args.probe_native_asset_reads:
        if native_assets_proof is None:
            detail = probe_error or "probe did not run"
            print(
                f"FATAL native asset probe failed: {detail}; see {LOG_DIR}",
                file=sys.stderr)
            return 1
        print(
            "control-test native-assets proof="
            f"{json.dumps(native_assets_proof, sort_keys=True)}",
            flush=True)
    if args.probe_native_asset_cache:
        if native_asset_cache_proof is None:
            detail = probe_error or "probe did not run"
            print(
                f"FATAL native asset cache probe failed: {detail}; see {LOG_DIR}",
                file=sys.stderr,
            )
            return 1
        print(
            "control-test native-asset-cache proof="
            f"{json.dumps(native_asset_cache_proof, sort_keys=True)}",
            flush=True,
        )
    if args.probe_native_movie_reads:
        if native_movie_reads_proof is None:
            detail = probe_error or "probe did not run"
            print(
                f"FATAL native movie read probe failed: {detail}; see {LOG_DIR}",
                file=sys.stderr)
            return 1
        print(
            "control-test native-movie-reads proof="
            f"{json.dumps(native_movie_reads_proof, sort_keys=True)}",
            flush=True)
    if args.probe_native_stream_reads:
        if native_stream_reads_proof is None:
            detail = probe_error or "probe did not run"
            print(
                f"FATAL native stream read probe failed: {detail}; see {LOG_DIR}",
                file=sys.stderr)
            return 1
        print(
            "control-test native-stream-reads proof="
            f"{json.dumps(native_stream_reads_proof, sort_keys=True)}",
            flush=True)
    if args.probe_native_marine_m1_transition:
        if native_marine_m1_proof is None:
            detail = probe_error or "probe did not run"
            print(
                f"FATAL native Marine M1 transition probe failed: {detail}; see {LOG_DIR}",
                file=sys.stderr,
            )
            return 1
        print(
            "control-test native-marine-m1-transition proof="
            f"{json.dumps(native_marine_m1_proof, sort_keys=True)}",
            flush=True,
        )
    if native_recovery_requested:
        if native_asset_recovery_proof is None:
            detail = probe_error or "probe did not run"
            print(
                f"FATAL native asset state recovery probe failed: {detail}; see {LOG_DIR}",
                file=sys.stderr,
            )
            return 1
        print(
            "control-test native-asset-state-recovery proof="
            f"{json.dumps(native_asset_recovery_proof, sort_keys=True)}",
            flush=True,
        )
    if args.probe_native_asset_reset:
        if native_asset_reset_proof is None:
            detail = probe_error or "probe did not run"
            print(
                f"FATAL native {args.probe_native_asset_reset} guest reset probe failed: "
                f"{detail}; see {LOG_DIR}",
                file=sys.stderr,
            )
            return 1
        print(
            f"control-test native-{args.probe_native_asset_reset}-guest-reset proof="
            f"{json.dumps(native_asset_reset_proof, sort_keys=True)}",
            flush=True,
        )
    if args.probe_asset_byte_trace:
        if asset_byte_trace is None:
            detail = probe_error or "probe did not run"
            print(
                f"FATAL {args.probe_asset_byte_trace} asset byte trace failed: "
                f"{detail}; see {LOG_DIR}",
                file=sys.stderr)
            return 1
        output = write_asset_byte_trace(
            asset_byte_trace, args.probe_asset_byte_trace,
            args.asset_byte_trace_output, LOG_DIR.parent
        )
        print(
            f"control-test asset-byte-trace mode={args.probe_asset_byte_trace} "
            f"output={output}",
            flush=True)
    if args.probe_load_timing:
        if load_timing is None:
            detail = probe_error or "probe did not run"
            print(f"FATAL {args.probe_load_timing} load timing failed: {detail}; see {LOG_DIR}",
                  file=sys.stderr)
            return 1
        load_timing["control_status"] = boot_status
        load_timing["memory_card_proof"] = card_proof
        output = args.load_timing_output or (
            LOG_DIR.parent / f"load-timing-{args.probe_load_timing}.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(load_timing, indent=2, sort_keys=True) + "\n")
        print(f"control-test load-timing mode={args.probe_load_timing} output={output}", flush=True)
    if args.probe_bios_trace:
        if not report_bios_trace(bios_trace, args.bios_trace_output, boot_status, LOG_DIR):
            return 1
    if not report_json_probe(args.probe_native_pointer, pointer_proof, "native-pointer", probe_error, LOG_DIR):
        return 1
    if not report_json_probe(args.probe_native_mouse, mouse_proof, "native-mouse", probe_error, LOG_DIR):
        return 1
    if not report_json_probe(args.probe_native_menu, menu_proof, "native-menu", probe_error, LOG_DIR):
        return 1
    if not report_json_probe(args.probe_native_menu_activate, menu_activation_proof, "native-menu-activation", probe_error, LOG_DIR):
        return 1
    if not report_json_probe(args.probe_native_menu_pointer, menu_pointer_proof, "native-menu-pointer", probe_error, LOG_DIR):
        return 1
    if args.probe_native_camera:
        if camera_proof is None:
            detail = probe_error or "probe did not run"
            print(f"FATAL native camera probe failed: {detail}; see {LOG_DIR}", file=sys.stderr)
            return 1
        camera_proof["control_status"] = boot_status
        camera_output = LOG_DIR.parent / "native-camera-proof.json"
        camera_output.write_text(json.dumps(camera_proof, indent=2, sort_keys=True) + "\n")
        print(
            "control-test native-camera proof="
            f"{json.dumps(camera_proof, sort_keys=True)}",
            flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
