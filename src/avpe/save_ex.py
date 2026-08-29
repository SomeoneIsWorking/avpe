"""Bounded readers for AVP:E's class-specific SaveEx payloads."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import struct

from avpe.save_message_types import (
    MESSAGE_DYNAMIC_SIZE,
    MessageTypeEntry,
    MESSAGE_TYPE_ENTRY_COUNT,
)

PLAYER_MANAGER_FIXED_BYTES = 0x474 + 0x10


@dataclass(frozen=True)
class GUnitSaveEx:
    value: int
    consumed_bytes: int


@dataclass(frozen=True)
class GDropShipSaveEx:
    current_state: int
    unit_value: int
    consumed_bytes: int


@dataclass(frozen=True)
class GFowSaveEx:
    bit_count: int
    words: tuple[int, ...]
    consumed_bytes: int


@dataclass(frozen=True)
class GObjectAIMessage:
    type_id: int
    raw: bytes


@dataclass(frozen=True)
class GObjectAISaveEx:
    messages: tuple[GObjectAIMessage, ...]
    consumed_bytes: int


@dataclass(frozen=True)
class GPlayerManagerSaveEx:
    fixed_bytes: bytes
    groups: tuple[tuple[bytes, ...], ...]
    consumed_bytes: int


MessageSize = Callable[[int], int]


def parse_gunit_payload(data: bytes) -> GUnitSaveEx:
    """Read the four bytes emitted by ``GUnit::SaveEx``."""

    _require_bytes(data, 4, "GUnit SaveEx value")
    return GUnitSaveEx(struct.unpack_from("<I", data)[0], 4)


def parse_gdrop_ship_payload(data: bytes) -> GDropShipSaveEx:
    """Read ``GDropShip::SaveEx`` and its inherited ``GUnit`` payload."""

    _require_bytes(data, 8, "GDropShip SaveEx payload")
    current_state, unit_value = struct.unpack_from("<II", data)
    return GDropShipSaveEx(current_state, unit_value, 8)


def parse_gfow_saver_payload(
    data: bytes, expected_word_count: int | None = None
) -> GFowSaveEx:
    """Read GFOWSaver's bit-count and sign-bit words."""

    _require_bytes(data, 4, "GFOWSaver SaveEx count")
    bit_count = struct.unpack_from("<I", data)[0]
    word_count = (bit_count + 31) // 32
    if expected_word_count is not None and word_count != expected_word_count:
        raise ValueError("GFOWSaver SaveEx count does not match the expected count")
    consumed = 4 + word_count * 4
    _require_bytes(data, consumed, "GFOWSaver SaveEx bitmap")
    words = struct.unpack_from("<" + "I" * word_count, data, 4)
    return GFowSaveEx(bit_count, words, consumed)


def parse_gobject_ai_payload(data: bytes, message_size: MessageSize) -> GObjectAISaveEx:
    """Read GObjectAI's count, message types, and type-sized message bytes."""

    return _parse_gobject_ai_payload(data, lambda type_id, _: message_size(type_id))


def parse_gobject_ai_payload_from_database(
    data: bytes, entries: tuple[MessageTypeEntry | None, ...]
) -> GObjectAISaveEx:
    """Read GObjectAI messages using the title's fixed/dynamic size table."""

    if len(entries) != MESSAGE_TYPE_ENTRY_COUNT:
        raise ValueError("message type database has the wrong slot count")

    def size_for_message(type_id: int, offset: int) -> int:
        entry = entries[type_id & 0xFF]
        if entry is None:
            raise ValueError(f"message type 0x{type_id:08x} is not registered")
        if entry.size != MESSAGE_DYNAMIC_SIZE:
            return entry.size
        _require_range(data, offset, 0x0E, "dynamic message size")
        return struct.unpack_from("<H", data, offset + 0x0C)[0]

    return _parse_gobject_ai_payload(data, size_for_message)


def _parse_gobject_ai_payload(
    data: bytes, message_size: Callable[[int, int], int]
) -> GObjectAISaveEx:
    """Shared bounded loop for callback- and table-backed message sizes."""

    _require_bytes(data, 4, "GObjectAI SaveEx count")
    count = struct.unpack_from("<I", data)[0]
    offset = 4
    if count > (len(data) - offset) // 4:
        raise ValueError("GObjectAI SaveEx message type list is truncated")
    messages: list[GObjectAIMessage] = []
    for _ in range(count):
        _require_range(data, offset, 4, "GObjectAI SaveEx message type")
        type_id = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        size = message_size(type_id, offset)
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError(f"message type 0x{type_id:08x} has an invalid size")
        _require_range(data, offset, size, "GObjectAI SaveEx message")
        messages.append(GObjectAIMessage(type_id, bytes(data[offset:offset + size])))
        offset += size
    return GObjectAISaveEx(tuple(messages), offset)


def parse_gplayer_manager_payload(
    data: bytes, active: bool
) -> GPlayerManagerSaveEx:
    """Read the conditional player-manager header and four counted groups."""

    if not active:
        return GPlayerManagerSaveEx(b"", (), 0)
    _require_bytes(data, PLAYER_MANAGER_FIXED_BYTES, "GPlayerManager fixed payload")
    offset = PLAYER_MANAGER_FIXED_BYTES
    groups: list[tuple[bytes, ...]] = []
    for _ in range(4):
        _require_range(data, offset, 4, "GPlayerManager group count")
        count = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if count > (len(data) - offset) // 12:
            raise ValueError("GPlayerManager group records are truncated")
        group_size = count * 12
        _require_range(data, offset, group_size, "GPlayerManager group records")
        groups.append(
            tuple(
                bytes(data[offset + index:offset + index + 12])
                for index in range(0, group_size, 12)
            )
        )
        offset += group_size
    return GPlayerManagerSaveEx(bytes(data[:PLAYER_MANAGER_FIXED_BYTES]), tuple(groups), offset)


def _require_bytes(data: bytes, size: int, label: str) -> None:
    _require_range(data, 0, size, label)


def _require_range(data: bytes, offset: int, size: int, label: str) -> None:
    if offset < 0 or size < 0 or offset > len(data) - size:
        raise ValueError(f"{label} is truncated")
