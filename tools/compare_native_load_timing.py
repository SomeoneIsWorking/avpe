#!/usr/bin/env python3
"""Run and compare isolated optical/native AVP:E load-timing samples."""

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from avpe.load_timing import (
    compare_load_timing_samples,
    compare_mission_load_timing_samples,
    validate_load_timing_sample,
    validate_mission_load_timing_sample,
)
from avpe.native_mission_probe import validate_marine_m1_evidence
from avpe.pcsx2_config import timing_config_identity


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tools" / "run_control_test.py"
DEFAULT_CARD = ROOT / "scratch" / "control-test" / "source-card.ps2"
DEFAULT_OUTPUT_DIR = ROOT / "scratch" / "control-test" / "load-timing"
DEFAULT_MISSION_OUTPUT_DIR = (
    ROOT / "scratch" / "control-test" / "mission-load-timing"
)
PCSX2 = ROOT / "scratch" / "build" / "bin" / "pcsx2-qt"
PCSX2_INI = ROOT / "scratch" / "control-test" / "pcsx2-home" / "PCSX2" / "inis" / "PCSX2.ini"
NATIVE_MANIFEST = ROOT / "scratch" / "native-assets" / "avpe-native-assets-v1" / "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_identity(path: Path) -> dict[str, object]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=path, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    return {"revision": revision, "dirty": dirty}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return value


def validate_run_envelope(
    sample: dict[str, object],
    target: str,
) -> list[str]:
    errors: list[str] = []
    status = sample.get("control_status")
    if not isinstance(status, dict) or any((
        status.get("serial") != "SLUS-20147",
        status.get("host_mode") != "control-test",
        status.get("surface") != "surfaceless",
        status.get("audio") != "null-muted",
    )):
        errors.append("control status is not the expected surfaceless/null-muted AVP:E runtime")
    card = sample.get("memory_card_proof")
    if not isinstance(card, dict) or any((
        card.get("changed_bytes") != 0,
        card.get("source_sha256") != card.get("working_sha256"),
    )):
        errors.append("isolated memory-card bytes were not preserved")
    if sample.get("byte_trace_disabled") is not True:
        errors.append("asset byte tracing was enabled during timing")
    if target == "mission":
        mode = sample.get("mode")
        transition = sample.get("mission_transition_proof")
        if not isinstance(transition, dict) or mode not in ("oracle", "native"):
            errors.append("mission transition proof is missing or has no valid mode")
        else:
            errors.extend(
                validate_marine_m1_evidence(
                    transition,
                    require_native_assets=mode == "native",
                )
            )
        startup_backend = sample.get("startup_backend_timing")
        try:
            validate_load_timing_sample(startup_backend, str(mode))
        except (TypeError, ValueError) as error:
            errors.append(f"startup backend identity is invalid: {error}")
    return errors


def ordinal_negative_control(
    oracle: list[dict[str, object]], native: list[dict[str, object]],
    *,
    target: str = "startup",
) -> dict[str, object]:
    changed = copy.deepcopy(native)
    end = changed[0]["end"]
    assert isinstance(end, dict) and isinstance(end.get("ordinal"), int)
    end["ordinal"] += 1
    compare = (
        compare_mission_load_timing_samples
        if target == "mission"
        else compare_load_timing_samples
    )
    result = compare(oracle, changed)
    rejected = any(error.get("code") == "boundary_ordinal_drift" for error in result["errors"])
    return {"verified_rejection": not result["verified"] and rejected, "result": result}


def reduction_negative_control(
    oracle: list[dict[str, object]], native: list[dict[str, object]],
    *,
    target: str = "startup",
) -> dict[str, object]:
    changed = copy.deepcopy(native)
    for oracle_sample, native_sample in zip(oracle, changed, strict=True):
        oracle_delta = oracle_sample["deltas"]
        native_delta = native_sample["deltas"]
        native_end = native_sample["end"]
        native_start = native_sample["start"]
        assert all(isinstance(value, dict) for value in (
            oracle_delta, native_delta, native_end, native_start))
        value = oracle_delta["ee_cycles"]
        native_delta["ee_cycles"] = value
        native_end["ee_cycle"] = native_start["ee_cycle"] + value
    compare = (
        compare_mission_load_timing_samples
        if target == "mission"
        else compare_load_timing_samples
    )
    result = compare(oracle, changed)
    rejected = any(
        error.get("code") == "no_measured_reduction" and error.get("metric") == "ee_cycles"
        for error in result["errors"]
    )
    return {"verified_rejection": not result["verified"] and rejected, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--seconds", type=float, default=210.0)
    parser.add_argument(
        "--target", choices=("startup", "mission"), default="startup"
    )
    parser.add_argument("--memory-card-source", type=Path, default=DEFAULT_CARD)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.samples < 3:
        parser.error("--samples must be at least 3")
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    if not args.memory_card_source.is_file():
        parser.error(f"memory card source is not a file: {args.memory_card_source}")

    repository_identity = {
        "project": git_identity(ROOT),
        "pcsx2_fork": git_identity(ROOT / "thirdparty" / "pcsx2"),
    }
    dirty = [name for name, identity in repository_identity.items() if identity["dirty"]]
    if dirty:
        print(f"FATAL timing evidence requires clean repositories: {', '.join(dirty)}", file=sys.stderr)
        return 2
    if not PCSX2.is_file():
        print(f"FATAL built control-test binary is missing: {PCSX2}", file=sys.stderr)
        return 2

    output_dir = (
        args.output_dir
        or (DEFAULT_MISSION_OUTPUT_DIR if args.target == "mission" else DEFAULT_OUTPUT_DIR)
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    binary_sha256 = sha256_file(PCSX2)
    samples: dict[str, list[dict[str, object]]] = {"oracle": [], "native": []}
    run_records: list[dict[str, object]] = []
    for pair in range(1, args.samples + 1):
        for mode in ("oracle", "native"):
            output = output_dir / f"pair-{pair:02d}-{mode}.json"
            command = [
                sys.executable, str(RUNNER), "--seconds", str(args.seconds),
                "--memory-card-source", str(args.memory_card_source),
                "--probe-load-timing", mode, "--load-timing-output", str(output),
            ]
            if args.target == "mission":
                command += ["--load-timing-target", "mission"]
            print(f"load-timing pair={pair} mode={mode}", flush=True)
            subprocess.run(command, cwd=ROOT, check=True)
            sample = load_json(output)
            if args.target == "mission":
                validate_mission_load_timing_sample(sample, mode)
            else:
                validate_load_timing_sample(sample, mode)
            samples[mode].append(sample)
            run_records.append({
                "pair": pair,
                "mode": mode,
                "output": str(output.relative_to(ROOT)),
                "binary_sha256": sha256_file(PCSX2),
                "config_identity": timing_config_identity(PCSX2_INI),
                "envelope_errors": validate_run_envelope(sample, args.target),
            })

    manifest = load_json(NATIVE_MANIFEST)
    compare = (
        compare_mission_load_timing_samples
        if args.target == "mission"
        else compare_load_timing_samples
    )
    comparison = compare(samples["oracle"], samples["native"])
    ordinal_control = ordinal_negative_control(
        samples["oracle"], samples["native"], target=args.target
    )
    reduction_control = reduction_negative_control(
        samples["oracle"], samples["native"], target=args.target
    )
    environment_errors = [
        error
        for record in run_records
        for error in record["envelope_errors"]
    ]
    if any(record["binary_sha256"] != binary_sha256 for record in run_records):
        environment_errors.append("control-test binary changed between samples")
    config_identities = [record["config_identity"] for record in run_records]
    if any(identity != config_identities[0] for identity in config_identities[1:]):
        environment_errors.append("control-test configuration changed between samples")
    if git_identity(ROOT) != repository_identity["project"] or \
            git_identity(ROOT / "thirdparty" / "pcsx2") != repository_identity["pcsx2_fork"]:
        environment_errors.append("repository identity changed between samples")

    report = {
        "schema": (
            "avpe-mission-load-timing-run-v1"
            if args.target == "mission"
            else "avpe-load-timing-run-v1"
        ),
        "target": args.target,
        "verified": bool(
            comparison["verified"]
            and ordinal_control["verified_rejection"]
            and reduction_control["verified_rejection"]
            and not environment_errors
        ),
        "execution_order": [f"{record['pair']}:{record['mode']}" for record in run_records],
        "identity": {
            "repositories": repository_identity,
            "binary_sha256": binary_sha256,
            "disc_sha256": manifest.get("source_chd_sha256"),
            "memory_card_source_sha256": sha256_file(args.memory_card_source),
            "config": config_identities[0],
        },
        "environment_errors": environment_errors,
        "runs": run_records,
        "comparison": comparison,
        "negative_controls": {
            "ordinal_drift": ordinal_control,
            "no_reduction": reduction_control,
        },
    }
    output = output_dir / (
        "mission-load-timing-comparison.json"
        if args.target == "mission"
        else "asset-load-timing-comparison.json"
    )
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if not report["verified"]:
        print(f"FATAL load-timing comparison rejected; see {output}", file=sys.stderr)
        return 1
    reductions = comparison["reductions"]
    print(
        "load-timing comparison verified; reductions="
        + ", ".join(f"{name}:{value['percent']:.2f}%" for name, value in reductions.items())
        + f"; output={output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
