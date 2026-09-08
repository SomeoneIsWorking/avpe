"""Atomic, versioned host storage for validated AVP:E save records."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from avpe.save_format import parse_game_save_record


SCHEMA = "avpe-native-save-v1"
TITLE_SERIAL = "SLUS-20147"
TITLE_CRC = 0x64DA78A3
MAX_SLOTS = 16
MAX_RECORD_BYTES = 0x7E400
PROFILE_PAYLOAD_BYTES = 0x20
PROFILE_REVISION = 0x1CD9DEE3
PROFILE_SLOT_COUNT = 4


class NativeSaveStoreError(ValueError):
    """A native save container is missing, incompatible, or invalid."""


def write_profile(path: Path, payload: bytes) -> None:
    """Atomically replace the title profile payload while preserving slots."""
    _validate_profile(payload)
    container = _read_container(path) if path.exists() else _empty_container()
    container["profile"] = _encode_profile(payload)
    _atomic_write(path, container)


def read_profile(path: Path) -> bytes:
    """Read and validate the title profile payload from a native container."""
    container = _read_container(path)
    encoded = container.get("profile")
    if encoded is None:
        raise NativeSaveStoreError("native save profile is empty")
    return _decode_profile(encoded)


def write_slot(path: Path, slot: int, record: bytes) -> None:
    """Atomically replace one slot while preserving other validated slots."""
    _validate_slot(slot)
    _validate_record(record)
    container = _read_container(path) if path.exists() else _empty_container()
    slots = container["slots"]
    assert isinstance(slots, dict)
    slots[str(slot)] = _encode_record(record)
    _atomic_write(path, container)


def read_slot(path: Path, slot: int) -> bytes:
    """Read and revalidate one native slot through the shipping save parser."""
    _validate_slot(slot)
    container = _read_container(path)
    slots = container["slots"]
    assert isinstance(slots, dict)
    encoded = slots.get(str(slot))
    if encoded is None:
        raise NativeSaveStoreError(f"native save slot {slot} is empty")
    return _decode_record(encoded, slot)


def list_slots(path: Path) -> tuple[int, ...]:
    """Return the sorted occupied slots after validating the whole container."""
    container = _read_container(path)
    slots = container["slots"]
    assert isinstance(slots, dict)
    occupied: list[int] = []
    for key, encoded in slots.items():
        try:
            slot = int(key, 10)
        except (TypeError, ValueError) as error:
            raise NativeSaveStoreError("native save contains a non-numeric slot") from error
        _validate_slot(slot)
        _decode_record(encoded, slot)
        occupied.append(slot)
    return tuple(sorted(occupied))


def _empty_container() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "title": {"serial": TITLE_SERIAL, "crc": TITLE_CRC},
        "profile": None,
        "slots": {},
    }


def _read_container(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise NativeSaveStoreError(f"could not read native save container: {path}") from error
    try:
        container = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NativeSaveStoreError("native save container is not valid JSON") from error
    if not isinstance(container, dict):
        raise NativeSaveStoreError("native save container is not an object")
    if container.get("schema") != SCHEMA:
        raise NativeSaveStoreError("native save container has an unsupported schema")
    title = container.get("title")
    if not isinstance(title, dict) or title.get("serial") != TITLE_SERIAL or title.get("crc") != TITLE_CRC:
        raise NativeSaveStoreError("native save container targets another title revision")
    slots = container.get("slots")
    if not isinstance(slots, dict) or len(slots) > MAX_SLOTS:
        raise NativeSaveStoreError("native save container has an invalid slot table")
    for key, encoded in slots.items():
        try:
            slot = int(key, 10)
        except (TypeError, ValueError) as error:
            raise NativeSaveStoreError("native save contains a non-numeric slot") from error
        _validate_slot(slot)
        _decode_record(encoded, slot)
    profile = container.get("profile")
    if profile is not None:
        _decode_profile(profile)
    return container


def _encode_record(record: bytes) -> dict[str, object]:
    return {
        "record_hex": record.hex(),
        "sha256": hashlib.sha256(record).hexdigest(),
    }


def _encode_profile(payload: bytes) -> dict[str, object]:
    return {
        "payload_hex": payload.hex(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "revision": PROFILE_REVISION,
        "slot_count": PROFILE_SLOT_COUNT,
    }


def _decode_profile(encoded: Any) -> bytes:
    if not isinstance(encoded, dict) or encoded.get("revision") != PROFILE_REVISION or \
            encoded.get("slot_count") != PROFILE_SLOT_COUNT:
        raise NativeSaveStoreError("native save profile contract is incompatible")
    payload_hex = encoded.get("payload_hex")
    digest = encoded.get("sha256")
    if not isinstance(payload_hex, str) or not isinstance(digest, str):
        raise NativeSaveStoreError("native save profile is missing its payload")
    try:
        payload = bytes.fromhex(payload_hex)
    except ValueError as error:
        raise NativeSaveStoreError("native save profile is not hexadecimal") from error
    if hashlib.sha256(payload).hexdigest() != digest:
        raise NativeSaveStoreError("native save profile failed its integrity check")
    _validate_profile(payload)
    return payload


def _decode_record(encoded: Any, slot: int) -> bytes:
    if not isinstance(encoded, dict):
        raise NativeSaveStoreError(f"native save slot {slot} is malformed")
    record_hex = encoded.get("record_hex")
    digest = encoded.get("sha256")
    if not isinstance(record_hex, str) or not isinstance(digest, str):
        raise NativeSaveStoreError(f"native save slot {slot} is missing its record")
    try:
        record = bytes.fromhex(record_hex)
    except ValueError as error:
        raise NativeSaveStoreError(f"native save slot {slot} is not hexadecimal") from error
    if hashlib.sha256(record).hexdigest() != digest:
        raise NativeSaveStoreError(f"native save slot {slot} failed its integrity check")
    _validate_record(record)
    return record


def _validate_record(record: bytes) -> None:
    if not isinstance(record, bytes) or not record or len(record) > MAX_RECORD_BYTES:
        raise NativeSaveStoreError("native save record is outside its size bound")
    try:
        parse_game_save_record(record)
    except ValueError as error:
        raise NativeSaveStoreError(f"native save record failed title validation: {error}") from error


def _validate_profile(payload: bytes) -> None:
    if not isinstance(payload, bytes) or len(payload) != PROFILE_PAYLOAD_BYTES:
        raise NativeSaveStoreError(
            f"native save profile payload must be exactly {PROFILE_PAYLOAD_BYTES} bytes"
        )


def _validate_slot(slot: int) -> None:
    if not isinstance(slot, int) or not 0 <= slot < MAX_SLOTS:
        raise NativeSaveStoreError(f"native save slot is outside 0..{MAX_SLOTS - 1}")


def _atomic_write(path: Path, container: dict[str, object]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise NativeSaveStoreError(f"could not create native save directory: {path.parent}") from error
    payload = json.dumps(container, sort_keys=True, separators=(",", ":")).encode("utf-8")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except OSError as error:
        raise NativeSaveStoreError(f"could not atomically write native save container: {path}") from error
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
