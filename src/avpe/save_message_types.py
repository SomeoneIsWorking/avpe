"""Parse AVP:E's registered CMessage type-size database."""

from __future__ import annotations

from dataclasses import dataclass
import struct


MESSAGE_TYPE_DATABASE_ADDRESS = 0x003B10C0
MESSAGE_TYPE_ENTRY_SIZE = 0x0C
MESSAGE_TYPE_ENTRY_COUNT = 0x100
MESSAGE_DYNAMIC_SIZE = 0xFFFFFFFF
MESSAGE_TYPE_DATABASE_SIZE = MESSAGE_TYPE_ENTRY_SIZE * MESSAGE_TYPE_ENTRY_COUNT


@dataclass(frozen=True)
class MessageTypeEntry:
    slot: int
    create_address: int
    size: int
    name_address: int


def parse_message_type_database(data: bytes) -> tuple[MessageTypeEntry | None, ...]:
    """Return the fixed 256-slot database, preserving empty slots."""

    if len(data) < MESSAGE_TYPE_DATABASE_SIZE:
        raise ValueError("message type database is truncated")
    entries: list[MessageTypeEntry | None] = []
    for slot in range(MESSAGE_TYPE_ENTRY_COUNT):
        create_address, size, name_address = struct.unpack_from(
            "<III", data, slot * MESSAGE_TYPE_ENTRY_SIZE
        )
        entries.append(
            None
            if create_address == 0
            else MessageTypeEntry(slot, create_address, size, name_address)
        )
    return tuple(entries)


def fixed_message_size(
    entries: tuple[MessageTypeEntry | None, ...], type_id: int
) -> int:
    """Resolve a registered fixed-size message as ``CMessage::GetSize`` does."""

    if len(entries) != MESSAGE_TYPE_ENTRY_COUNT:
        raise ValueError("message type database has the wrong slot count")
    if isinstance(type_id, bool) or not isinstance(type_id, int) or not 0 <= type_id <= 0xFFFFFFFF:
        raise ValueError("message type ID is outside u32")
    entry = entries[type_id & 0xFF]
    if entry is None:
        raise ValueError(f"message type 0x{type_id:08x} is not registered")
    if entry.size == MESSAGE_DYNAMIC_SIZE:
        raise ValueError(f"message type 0x{type_id:08x} has dynamic size")
    return entry.size
