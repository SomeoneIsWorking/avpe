"""Strict validation and comparison policy for AVP:E guest load timing."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any


TIMING_SCHEMA = "avpe-load-timing-v1"
MISSION_TIMING_SCHEMA = "avpe-mission-load-timing-v1"
COMPARISON_SCHEMA = "avpe-load-timing-comparison-v1"
MISSION_COMPARISON_SCHEMA = "avpe-mission-load-timing-comparison-v1"
MINIMUM_SAMPLES = 3
MAX_FRAME_SPREAD = 1
MAX_CYCLE_SPREAD_PERCENT = 1.0
MAX_HOST_SPREAD_PERCENT = 25.0

_METRICS = ("ee_cycles", "iop_cycles", "frames", "host_elapsed_ns")
_BOUNDARY_COUNTERS = {
    "ee_cycles": "ee_cycle",
    "iop_cycles": "iop_cycle",
    "frames": "frame",
    "host_elapsed_ns": "host_time_ns",
}


@dataclass(frozen=True)
class _BoundaryIdentity:
    kind: str
    path: str
    pc: int | None = None


@dataclass(frozen=True)
class _TimingPolicy:
    schema: str
    target: str | None
    boundaries: dict[str, _BoundaryIdentity]
    validates_startup_backends: bool
    allows_zero_frame_delta: bool = False


_STARTUP_POLICY = _TimingPolicy(
    schema=TIMING_SCHEMA,
    target=None,
    boundaries={
        "start": _BoundaryIdentity("tbf-open", "TBD/TBF.TBF"),
        "end": _BoundaryIdentity(
            "menu01-post-search-seek", "STREAMS/MENU01.ZIV"
        ),
    },
    validates_startup_backends=True,
)
_MISSION_POLICY = _TimingPolicy(
    schema=MISSION_TIMING_SCHEMA,
    target="mission",
    boundaries={
        "start": _BoundaryIdentity(
            "shell-load-level-entry", "M01/background.tbd", 0x0016F910
        ),
        "end": _BoundaryIdentity(
            "shell-load-level-return", "M01/background.tbd", 0x0016F78C
        ),
    },
    validates_startup_backends=False,
    allows_zero_frame_delta=True,
)


class _InvalidSample(ValueError):
    pass


def validate_load_timing_sample(sample: object, expected_mode: str) -> dict[str, int]:
    """Validate one endpoint sample and return its canonical guest deltas.

    The returned mapping contains integers owned by this module, so callers do
    not need to retain or trust the mutable endpoint object after validation.
    """

    if expected_mode not in ("oracle", "native"):
        raise ValueError("expected_mode must be 'oracle' or 'native'")
    return _validate_sample(sample, expected_mode, _STARTUP_POLICY).copy()


def load_timing_sample_is_ready(sample: object, expected_mode: str) -> bool:
    """Return whether a runtime snapshot is a complete valid timing sample."""

    try:
        validate_load_timing_sample(sample, expected_mode)
    except (ValueError, TypeError):
        return False
    return True


def validate_mission_load_timing_sample(
    sample: object,
    expected_mode: str,
) -> dict[str, int]:
    """Validate one mission-transition sample and return canonical deltas."""

    if expected_mode not in ("oracle", "native"):
        raise ValueError("expected_mode must be 'oracle' or 'native'")
    return _validate_sample(sample, expected_mode, _MISSION_POLICY).copy()


def mission_load_timing_sample_is_ready(
    sample: object,
    expected_mode: str,
) -> bool:
    """Return whether a mission snapshot is a complete valid timing sample."""

    try:
        validate_mission_load_timing_sample(sample, expected_mode)
    except (ValueError, TypeError):
        return False
    return True


def compare_load_timing_samples(
    oracle_runs: object,
    native_runs: object,
) -> dict[str, Any]:
    """Compare symmetric oracle/native guest timing samples.

    Medians are reported only as summary statistics. A comparison is rejected
    before it can be verified when either execution mode exceeds the explicit
    within-mode spread bounds, preventing a median from concealing unstable
    guest boundaries.
    """

    return _compare_timing_samples(oracle_runs, native_runs, _STARTUP_POLICY)


def compare_mission_load_timing_samples(
    oracle_runs: object,
    native_runs: object,
) -> dict[str, Any]:
    """Compare symmetric oracle/native mission-transition timing samples."""

    return _compare_timing_samples(oracle_runs, native_runs, _MISSION_POLICY)


def _compare_timing_samples(
    oracle_runs: object,
    native_runs: object,
    policy: _TimingPolicy,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": (
            MISSION_COMPARISON_SCHEMA
            if policy.target == "mission"
            else COMPARISON_SCHEMA
        ),
        **({"target": "mission"} if policy.target == "mission" else {}),
        "verified": False,
        "policy": {
            "minimum_samples_per_mode": MINIMUM_SAMPLES,
            "equal_sample_counts_required": True,
            "maximum_frame_spread": MAX_FRAME_SPREAD,
            "maximum_cycle_spread_percent": MAX_CYCLE_SPREAD_PERCENT,
            "maximum_host_spread_percent": MAX_HOST_SPREAD_PERCENT,
            "stable_boundary_ordinals_required": True,
        },
        "raw_samples": {"oracle": {}, "native": {}},
        "medians": {"oracle": {}, "native": {}},
        "spreads": {"oracle": {}, "native": {}},
        "reductions": {},
        "errors": [],
    }
    errors: list[dict[str, Any]] = report["errors"]

    if not isinstance(oracle_runs, list):
        errors.append({"code": "invalid_run_collection", "mode": "oracle"})
    if not isinstance(native_runs, list):
        errors.append({"code": "invalid_run_collection", "mode": "native"})
    if errors:
        return report

    assert isinstance(oracle_runs, list)
    assert isinstance(native_runs, list)
    if len(oracle_runs) < MINIMUM_SAMPLES:
        errors.append({
            "code": "insufficient_samples",
            "mode": "oracle",
            "required": MINIMUM_SAMPLES,
            "observed": len(oracle_runs),
        })
    if len(native_runs) < MINIMUM_SAMPLES:
        errors.append({
            "code": "insufficient_samples",
            "mode": "native",
            "required": MINIMUM_SAMPLES,
            "observed": len(native_runs),
        })
    if len(oracle_runs) != len(native_runs):
        errors.append({
            "code": "sample_count_mismatch",
            "oracle": len(oracle_runs),
            "native": len(native_runs),
        })

    validated: dict[str, list[dict[str, int]]] = {"oracle": [], "native": []}
    ordinals: dict[str, list[tuple[int, int]]] = {"oracle": [], "native": []}
    for mode, runs in (("oracle", oracle_runs), ("native", native_runs)):
        for index, sample in enumerate(runs):
            try:
                deltas = _validate_sample(sample, mode, policy)
            except _InvalidSample as error:
                errors.append({
                    "code": "invalid_sample",
                    "mode": mode,
                    "index": index,
                    "detail": str(error),
                })
                continue
            validated[mode].append(deltas)
            assert isinstance(sample, dict)
            start = sample["start"]
            end = sample["end"]
            assert isinstance(start, dict) and isinstance(end, dict)
            ordinals[mode].append((start["ordinal"], end["ordinal"]))

    if errors:
        return report

    for mode in ("oracle", "native"):
        if len(set(ordinals[mode])) != 1:
            errors.append({
                "code": "boundary_ordinal_drift",
                "mode": mode,
                "observed": [list(pair) for pair in ordinals[mode]],
            })

        for metric in _METRICS:
            samples = [run[metric] for run in validated[mode]]
            sample_median = median(samples)
            spread = max(samples) - min(samples)
            report["raw_samples"][mode][metric] = samples
            report["medians"][mode][metric] = sample_median
            report["spreads"][mode][metric] = spread

            if metric == "frames":
                allowed = MAX_FRAME_SPREAD
            elif metric == "host_elapsed_ns":
                allowed = sample_median * MAX_HOST_SPREAD_PERCENT / 100.0
            else:
                allowed = sample_median * MAX_CYCLE_SPREAD_PERCENT / 100.0
            if spread > allowed:
                errors.append({
                    "code": "excessive_guest_boundary_spread",
                    "mode": mode,
                    "metric": metric,
                    "spread": spread,
                    "allowed": allowed,
                })

    for metric in _METRICS:
        oracle_median = report["medians"]["oracle"][metric]
        native_median = report["medians"]["native"][metric]
        absolute = oracle_median - native_median
        percent = absolute / oracle_median * 100.0
        report["reductions"][metric] = {
            "absolute": absolute,
            "percent": percent,
        }
        if absolute <= 0:
            errors.append({
                "code": "no_measured_reduction",
                "metric": metric,
                "oracle_median": oracle_median,
                "native_median": native_median,
            })

    report["verified"] = not errors
    return report


def _validate_sample(
    sample: object,
    expected_mode: str,
    policy: _TimingPolicy,
) -> dict[str, int]:
    if not isinstance(sample, dict):
        raise _InvalidSample("sample must be an object")
    if sample.get("schema") != policy.schema:
        raise _InvalidSample(f"schema must be {policy.schema!r}")
    if policy.target is not None and sample.get("target") != policy.target:
        raise _InvalidSample(f"target must be {policy.target!r}")
    if sample.get("enabled") is not True:
        raise _InvalidSample("timing capture was not enabled")
    if sample.get("target_recognized") is not True:
        raise _InvalidSample("target was not recognized")
    if sample.get("byte_trace_disabled") is not True:
        raise _InvalidSample("asset byte tracing must be disabled")
    if sample.get("mode") != expected_mode:
        raise _InvalidSample(f"mode must be {expected_mode!r}")
    _validate_backend_contract(sample, expected_mode, policy)
    if sample.get("complete") is not True:
        raise _InvalidSample("capture must be complete")
    sequence_errors = sample.get("sequence_errors")
    if not _is_nonnegative_int(sequence_errors):
        raise _InvalidSample("sequence_errors must be a non-negative integer")
    if sequence_errors != 0:
        raise _InvalidSample(
            f"sequence_errors must be zero, observed {sequence_errors}"
        )

    boundaries = {
        name: _validate_boundary(sample.get(name), name, policy.boundaries[name])
        for name in ("start", "end")
    }
    start = boundaries["start"]
    end = boundaries["end"]
    if end["ordinal"] <= start["ordinal"]:
        raise _InvalidSample("end.ordinal must be greater than start.ordinal")

    deltas = sample.get("deltas")
    if not isinstance(deltas, dict):
        raise _InvalidSample("deltas must be an object")
    canonical: dict[str, int] = {}
    for metric in _METRICS:
        value = deltas.get(metric)
        valid_delta = (
            _is_nonnegative_int(value)
            if metric == "frames" and policy.allows_zero_frame_delta
            else _is_positive_int(value)
        )
        if not valid_delta:
            requirement = "a non-negative integer" if (
                metric == "frames" and policy.allows_zero_frame_delta
            ) else "a positive integer"
            raise _InvalidSample(f"deltas.{metric} must be {requirement}")
        counter = _BOUNDARY_COUNTERS[metric]
        recomputed = end[counter] - start[counter]
        if value != recomputed:
            raise _InvalidSample(
                f"deltas.{metric} is {value}, recomputed boundary delta is {recomputed}"
            )
        canonical[metric] = value
    return canonical


def _validate_backend_contract(
    sample: dict[str, Any],
    expected_mode: str,
    policy: _TimingPolicy,
) -> None:
    if not policy.validates_startup_backends:
        if "backends" in sample:
            raise _InvalidSample("mission samples must not contain startup backends")
        return

    expected_backend = "native" if expected_mode == "native" else "optical"
    backends = sample.get("backends")
    if not isinstance(backends, dict):
        raise _InvalidSample("backends must be an object")
    for boundary in ("tbf", "menu01_seek"):
        if backends.get(boundary) != expected_backend:
            raise _InvalidSample(
                f"backends.{boundary} must be {expected_backend!r}"
            )


def _validate_boundary(
    boundary: object,
    name: str,
    identity: _BoundaryIdentity,
) -> dict[str, Any]:
    if not isinstance(boundary, dict):
        raise _InvalidSample(f"{name} must be an object")
    if boundary.get("kind") != identity.kind:
        raise _InvalidSample(f"{name}.kind must be {identity.kind!r}")
    if boundary.get("path") != identity.path:
        raise _InvalidSample(f"{name}.path must be {identity.path!r}")
    if identity.pc is not None and boundary.get("pc") != identity.pc:
        raise _InvalidSample(f"{name}.pc must be {identity.pc:#010x}")
    for field in ("ordinal", "ee_cycle", "iop_cycle", "frame", "host_time_ns"):
        if not _is_nonnegative_int(boundary.get(field)):
            raise _InvalidSample(f"{name}.{field} must be a non-negative integer")
    return boundary


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_positive_int(value: object) -> bool:
    return _is_nonnegative_int(value) and value > 0
