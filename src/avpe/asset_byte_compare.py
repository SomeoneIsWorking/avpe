"""Strict comparison policy for native and optical AVP:E byte traces."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


TRACE_SCHEMA = "avpe-asset-byte-trace-v1"
COMPARISON_SCHEMA = "avpe-asset-byte-comparison-v1"
REQUIRED_FILES = (
    "TBD/TBF.TBF",
    "MOVIES/EALOGO.PSS",
    "STREAMS/MENU01.ZIV",
)
MINIMUM_COMMON_CHUNKS = 4

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class _Chunk:
    offset: int
    size: int
    sha256: str


@dataclass(frozen=True)
class _File:
    path: str
    iso_lsn: int
    iso_size: int
    chunks: dict[tuple[int, int], _Chunk]


class _InvalidTrace(ValueError):
    pass


def compare_asset_byte_traces(
    oracle_trace: object,
    native_trace: object,
    *,
    minimum_common_chunks: int = MINIMUM_COMMON_CHUNKS,
) -> dict[str, Any]:
    """Compare canonical file-relative chunks from independent trace runs.

    Invalid, lossy, or internally conflicted traces produce a rejected report
    instead of a partial comparison. Chunk order and hit count are deliberately
    ignored; the stable identity is ``(path, offset, size)``.
    """

    if not _is_positive_int(minimum_common_chunks):
        raise ValueError("minimum_common_chunks must be a positive integer")

    report: dict[str, Any] = {
        "schema": COMPARISON_SCHEMA,
        "verified": False,
        "minimum_common_chunks": minimum_common_chunks,
        "required_files": list(REQUIRED_FILES),
        "errors": [],
        "files": [],
    }
    errors: list[dict[str, Any]] = report["errors"]

    try:
        oracle_files = _validate_trace(oracle_trace, "oracle")
    except _InvalidTrace as error:
        errors.append({
            "code": "invalid_oracle_trace",
            "detail": str(error),
        })
        oracle_files = None

    try:
        native_files = _validate_trace(native_trace, "native")
    except _InvalidTrace as error:
        errors.append({
            "code": "invalid_native_trace",
            "detail": str(error),
        })
        native_files = None

    if oracle_files is None or native_files is None:
        return report

    for path in REQUIRED_FILES:
        missing_from = [
            mode
            for mode, files in (("oracle", oracle_files), ("native", native_files))
            if path not in files
        ]
        if missing_from:
            errors.append({
                "code": "missing_required_file",
                "path": path,
                "missing_from": missing_from,
            })

    common_paths = sorted(oracle_files.keys() & native_files.keys())
    total_common_chunks = 0
    for path in common_paths:
        oracle_file = oracle_files[path]
        native_file = native_files[path]
        if oracle_file.iso_lsn != native_file.iso_lsn:
            errors.append({
                "code": "file_lsn_mismatch",
                "path": path,
                "oracle_iso_lsn": oracle_file.iso_lsn,
                "native_iso_lsn": native_file.iso_lsn,
            })
        if oracle_file.iso_size != native_file.iso_size:
            errors.append({
                "code": "file_size_mismatch",
                "path": path,
                "oracle_iso_size": oracle_file.iso_size,
                "native_iso_size": native_file.iso_size,
            })

        common_keys = sorted(oracle_file.chunks.keys() & native_file.chunks.keys())
        total_common_chunks += len(common_keys)
        mismatches = []
        for offset, size in common_keys:
            oracle_digest = oracle_file.chunks[(offset, size)].sha256
            native_digest = native_file.chunks[(offset, size)].sha256
            if oracle_digest == native_digest:
                continue
            mismatch = {
                "path": path,
                "offset": offset,
                "size": size,
                "oracle_sha256": oracle_digest,
                "native_sha256": native_digest,
            }
            mismatches.append(mismatch)
            errors.append({"code": "chunk_digest_mismatch", **mismatch})

        file_report = {
            "path": path,
            "iso_lsn": oracle_file.iso_lsn,
            "iso_size": oracle_file.iso_size,
            "oracle_chunks": len(oracle_file.chunks),
            "native_chunks": len(native_file.chunks),
            "common_chunks": len(common_keys),
            "matched_chunks": len(common_keys) - len(mismatches),
            "mismatches": mismatches,
        }
        report["files"].append(file_report)

        if path in REQUIRED_FILES and len(common_keys) < minimum_common_chunks:
            errors.append({
                "code": "insufficient_common_chunks",
                "path": path,
                "required": minimum_common_chunks,
                "observed": len(common_keys),
            })

    if total_common_chunks == 0:
        errors.append({"code": "no_common_chunks"})

    report["verified"] = not errors
    return report


def asset_byte_trace_is_ready(
    trace: object,
    mode: str,
    *,
    minimum_chunks: int = MINIMUM_COMMON_CHUNKS,
) -> bool:
    """Return whether one live trace has enough lossless canonical evidence."""

    if mode not in ("oracle", "native") or not _is_positive_int(minimum_chunks):
        return False
    try:
        files = _validate_trace(trace, mode)
    except _InvalidTrace:
        return False
    return all(
        path in files and len(files[path].chunks) >= minimum_chunks
        for path in REQUIRED_FILES
    )


def _validate_trace(trace: object, expected_mode: str) -> dict[str, _File]:
    if not isinstance(trace, dict):
        raise _InvalidTrace("trace must be an object")
    if trace.get("schema") != TRACE_SCHEMA:
        raise _InvalidTrace(f"schema must be {TRACE_SCHEMA!r}")
    if trace.get("enabled") is not True:
        raise _InvalidTrace("trace was not enabled")
    if trace.get("target_recognized") is not True:
        raise _InvalidTrace("target was not recognized")
    if trace.get("mode") != expected_mode:
        raise _InvalidTrace(f"mode must be {expected_mode!r}")

    for field in (
        "dropped_files",
        "dropped_bytes",
        "registration_failures",
    ):
        value = trace.get(field)
        if not _is_nonnegative_int(value):
            raise _InvalidTrace(f"{field} must be a non-negative integer")
        if value != 0:
            raise _InvalidTrace(f"{field} must be zero, observed {value}")

    records = trace.get("files")
    if not isinstance(records, list):
        raise _InvalidTrace("files must be an array")

    files: dict[str, _File] = {}
    for file_index, record in enumerate(records):
        file = _validate_file(record, file_index, expected_mode)
        if file.path in files:
            raise _InvalidTrace(f"files contains duplicate path {file.path!r}")
        files[file.path] = file
    return files


def _validate_file(record: object, file_index: int, expected_mode: str) -> _File:
    location = f"files[{file_index}]"
    if not isinstance(record, dict):
        raise _InvalidTrace(f"{location} must be an object")

    path = record.get("path")
    if not isinstance(path, str) or not path:
        raise _InvalidTrace(f"{location}.path must be a non-empty string")
    if _canonical_path(path) != path:
        raise _InvalidTrace(f"{location}.path is not canonical: {path!r}")

    iso_lsn = record.get("iso_lsn")
    iso_size = record.get("iso_size")
    if not _is_nonnegative_int(iso_lsn):
        raise _InvalidTrace(f"{location}.iso_lsn must be a non-negative integer")
    if not _is_positive_int(iso_size):
        raise _InvalidTrace(f"{location}.iso_size must be a positive integer")

    records = record.get("chunks")
    if not isinstance(records, list):
        raise _InvalidTrace(f"{location}.chunks must be an array")

    chunks: dict[tuple[int, int], _Chunk] = {}
    for chunk_index, chunk_record in enumerate(records):
        chunk = _validate_chunk(
            chunk_record, location, chunk_index, iso_size, expected_mode
        )
        key = (chunk.offset, chunk.size)
        if key in chunks:
            raise _InvalidTrace(
                f"{location}.chunks contains duplicate range "
                f"offset={chunk.offset} size={chunk.size}"
            )
        chunks[key] = chunk

    return _File(path=path, iso_lsn=iso_lsn, iso_size=iso_size, chunks=chunks)


def _validate_chunk(
    record: object,
    file_location: str,
    chunk_index: int,
    iso_size: int,
    expected_mode: str,
) -> _Chunk:
    location = f"{file_location}.chunks[{chunk_index}]"
    if not isinstance(record, dict):
        raise _InvalidTrace(f"{location} must be an object")

    offset = record.get("offset")
    size = record.get("size")
    digest = record.get("sha256")
    sources = record.get("sources")
    hits = record.get("hits")
    conflict = record.get("conflict")

    if not _is_nonnegative_int(offset):
        raise _InvalidTrace(f"{location}.offset must be a non-negative integer")
    if not _is_positive_int(size):
        raise _InvalidTrace(f"{location}.size must be a positive integer")
    if offset + size > iso_size:
        raise _InvalidTrace(f"{location} extends past the file size")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise _InvalidTrace(f"{location}.sha256 must be a lowercase SHA-256 digest")
    if (
        not isinstance(sources, list)
        or not sources
        or any(not isinstance(source, str) or not source for source in sources)
        or len(set(sources)) != len(sources)
    ):
        raise _InvalidTrace(f"{location}.sources must contain unique non-empty strings")
    expected_sources = (
        {"iso-oracle"}
        if expected_mode == "oracle"
        else {"native-ioman", "native-cdvd"}
    )
    if any(source not in expected_sources for source in sources):
        raise _InvalidTrace(
            f"{location}.sources do not belong to {expected_mode!r}: {sources!r}"
        )
    if not _is_positive_int(hits):
        raise _InvalidTrace(f"{location}.hits must be a positive integer")
    if conflict is not False:
        raise _InvalidTrace(f"{location}.conflict must be false")

    return _Chunk(offset=offset, size=size, sha256=digest)


def _canonical_path(path: str) -> str:
    if path.startswith("/") or "\\" in path or ";" in path:
        return ""
    components = path.split("/")
    if any(not component or component in (".", "..") for component in components):
        return ""
    return "/".join(components).upper()


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_positive_int(value: object) -> bool:
    return _is_nonnegative_int(value) and value > 0
