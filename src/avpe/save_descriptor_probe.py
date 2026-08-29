"""Parse AVP:E's live ClassTypeEntry and editable descriptor tables."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
import struct
from typing import Any


CLASS_TYPE_DATABASE_ADDRESS = 0x003B10B0
CLASS_TYPE_ARRAY_POINTER_OFFSET = 0x00
CLASS_TYPE_ARRAY_COUNT_OFFSET = 0x04
CLASS_TYPE_ARRAY_CAPACITY_OFFSET = 0x08
CLASS_TYPE_ENTRY_SIZE = 0x20
CLASS_TYPE_ID_OFFSET = 0x00
CLASS_TYPE_NAME_POINTER_OFFSET = 0x04
CLASS_TYPE_PARENT_POINTER_OFFSET = 0x0C
CLASS_TYPE_FLAGS_OFFSET = 0x14
CLASS_TYPE_DESCRIPTOR_POINTER_OFFSET = 0x1C
EDITABLE_DESCRIPTOR_SIZE = 0x0C
EDITABLE_DESCRIPTOR_ID_OFFSET = 0x00
EDITABLE_DESCRIPTOR_SIZE_OFFSET = 0x04
EDITABLE_DESCRIPTOR_KIND_OFFSET = 0x06
EDITABLE_DESCRIPTOR_FLAGS_OFFSET = 0x07
EDITABLE_DESCRIPTOR_OBJECT_OFFSET = 0x08
MAX_CLASS_TYPE_ENTRIES = 4096
MAX_DESCRIPTOR_ENTRIES = 1024
MAX_CLASS_NAME_BYTES = 128
MAX_PARENT_CHAIN_DEPTH = 64

GuestMemoryReader = Callable[[int, int], bytes]


@dataclass(frozen=True)
class EditableDescriptor:
    field_id: int
    size: int
    kind: int
    flags: int
    object_offset: int


@dataclass(frozen=True)
class ClassTypeIdentity:
    address: int
    class_id: int
    name: str


@dataclass(frozen=True)
class ClassTypeEntry:
    address: int
    class_id: int
    name: str
    parent_address: int
    flags: int
    descriptor_address: int
    descriptors: tuple[EditableDescriptor, ...]
    parent_chain: tuple[ClassTypeIdentity, ...]


@dataclass(frozen=True)
class SaveExDispatch:
    """The most-derived grounded SaveEx implementation for one class."""

    implementation: str
    address: int


SAVE_EX_IMPLEMENTATION_ADDRESSES = {
    "GObject": 0x001070A0,
    "GFOWSaver": 0x00110450,
    "GHiveNode": 0x0019FFC0,
    "GAlienCarrier": 0x001A8850,
    "GUnit": 0x001C0C80,
    "GChestBurster": 0x001DD8E0,
    "GDropShip": 0x001DF840,
    "GHugger": 0x001F1DC0,
    "GPlayerManager": 0x001F5E40,
    "GObjectAI": 0x00223090,
    "GDropPod": 0x0023EF40,
    "GAlarm": 0x00248A30,
}


@dataclass(frozen=True)
class SerializedDescriptorField:
    """One wire slice emitted for a class descriptor."""

    field_id: int
    kind: int
    offset: int
    wire_size: int
    raw: bytes
    pointer_identities: tuple[int, ...]


@dataclass(frozen=True)
class SerializedDescriptorBody:
    """Descriptor fields and the byte boundary before any SaveEx payload."""

    fields: tuple[SerializedDescriptorField, ...]
    consumed_bytes: int


def inspect_class_type_database(
    read: GuestMemoryReader,
    observed_class_ids: Iterable[int] | None = None,
    database_address: int = CLASS_TYPE_DATABASE_ADDRESS,
) -> dict[str, Any]:
    """Return bounded descriptor metadata for selected live class IDs."""

    database = read(database_address, 12)
    array_address = _u32(database, CLASS_TYPE_ARRAY_POINTER_OFFSET)
    entry_count = _u32(database, CLASS_TYPE_ARRAY_COUNT_OFFSET)
    capacity = _u32(database, CLASS_TYPE_ARRAY_CAPACITY_OFFSET)
    if array_address == 0 or entry_count == 0 or entry_count > MAX_CLASS_TYPE_ENTRIES:
        raise ValueError("class type database has an invalid bounded array")
    if capacity < entry_count or capacity > MAX_CLASS_TYPE_ENTRIES:
        raise ValueError("class type database has an invalid capacity")

    requested = None if observed_class_ids is None else set(observed_class_ids)
    if requested is not None and any(
        isinstance(class_id, bool) or not isinstance(class_id, int) or class_id < 0
        for class_id in requested
    ):
        raise ValueError("observed class IDs must be non-negative integers")

    pointers = read(array_address, entry_count * 4)
    entries: list[ClassTypeEntry] = []
    found: set[int] = set()
    for index in range(entry_count):
        entry_address = _u32(pointers, index * 4)
        if entry_address == 0:
            continue
        entry = _parse_entry(read, entry_address)
        if requested is None or entry.class_id in requested:
            entries.append(entry)
            found.add(entry.class_id)

    missing = sorted(requested - found) if requested is not None else []
    serialized_entries = []
    for entry in sorted(entries, key=lambda e: e.class_id):
        serialized = asdict(entry)
        serialized["save_ex"] = asdict(
            resolve_save_ex_dispatch(
                entry.name, tuple(parent.name for parent in entry.parent_chain)
            )
        )
        serialized_entries.append(serialized)
    return {
        "schema": "avpe-save-descriptor-inventory-v1",
        "database_address": database_address,
        "array_address": array_address,
        "entry_count": entry_count,
        "capacity": capacity,
        "requested_class_ids": sorted(requested) if requested is not None else None,
        "missing_class_ids": missing,
        "entries": serialized_entries,
    }


def resolve_save_ex_dispatch(
    class_name: str, parent_names: Iterable[str]
) -> SaveExDispatch:
    """Resolve virtual SaveEx using a live class's grounded parent chain."""

    for name in (class_name, *parent_names):
        address = SAVE_EX_IMPLEMENTATION_ADDRESSES.get(name)
        if address is not None:
            return SaveExDispatch(name, address)
    return SaveExDispatch("GObject", SAVE_EX_IMPLEMENTATION_ADDRESSES["GObject"])


def parse_serialized_descriptor_body(
    data: bytes, descriptors: Iterable[EditableDescriptor]
) -> SerializedDescriptorBody:
    """Split the descriptor-defined prefix of one saved object body.

    ``GObject::Save`` emits scalar bytes directly and emits an eight-byte
    field description plus saved-object identities for pointer kinds.  The
    returned ``consumed_bytes`` deliberately leaves any following class
    ``SaveEx`` payload untouched; callers must identify that payload from its
    grounded virtual implementation instead of treating it as a field.
    """

    fields: list[SerializedDescriptorField] = []
    offset = 0
    for descriptor in descriptors:
        wire_size = descriptor_wire_size(descriptor)
        end = offset + wire_size
        if end > len(data):
            raise ValueError(
                f"descriptor field 0x{descriptor.field_id:08x} is truncated"
            )
        raw = bytes(data[offset:end])
        identities: tuple[int, ...] = ()
        if descriptor.kind in (6, 7, 9):
            field_id, size, _, _ = struct.unpack_from("<I H B B", raw)
            if field_id != descriptor.field_id or size != descriptor.size:
                raise ValueError(
                    f"descriptor field 0x{descriptor.field_id:08x} has a mismatched wire description"
                )
            identity_count = 1 if descriptor.kind in (6, 7) else descriptor.size // 4
            identities = tuple(
                struct.unpack_from("<I", raw, 8 + index * 4)[0]
                for index in range(identity_count)
            )
        fields.append(
            SerializedDescriptorField(
                field_id=descriptor.field_id,
                kind=descriptor.kind,
                offset=offset,
                wire_size=wire_size,
                raw=raw,
                pointer_identities=identities,
            )
        )
        offset = end
    return SerializedDescriptorBody(tuple(fields), offset)


def descriptor_wire_size(descriptor: EditableDescriptor) -> int:
    """Return the exact byte count emitted by ``GObject::Save``."""

    if descriptor.kind in (1, 2, 3, 4, 5, 8):
        return max(descriptor.size, 4)
    if descriptor.kind in (6, 7):
        return 12
    if descriptor.kind == 9:
        return 8 + 4 * (descriptor.size // 4)
    raise ValueError(f"unsupported editable descriptor kind {descriptor.kind}")


def _parse_entry(read: GuestMemoryReader, address: int) -> ClassTypeEntry:
    raw = read(address, CLASS_TYPE_ENTRY_SIZE)
    class_id = _u32(raw, CLASS_TYPE_ID_OFFSET)
    name_address = _u32(raw, CLASS_TYPE_NAME_POINTER_OFFSET)
    descriptor_address = _u32(raw, CLASS_TYPE_DESCRIPTOR_POINTER_OFFSET)
    if name_address == 0 or descriptor_address == 0:
        raise ValueError(f"class type 0x{class_id:08x} has a null metadata pointer")
    name = _read_string(read, name_address)
    descriptors = _parse_descriptors(read, descriptor_address)
    parent_chain = _parse_parent_chain(read, _u32(raw, CLASS_TYPE_PARENT_POINTER_OFFSET))
    return ClassTypeEntry(
        address=address,
        class_id=class_id,
        name=name,
        parent_address=_u32(raw, CLASS_TYPE_PARENT_POINTER_OFFSET),
        flags=_u32(raw, CLASS_TYPE_FLAGS_OFFSET),
        descriptor_address=descriptor_address,
        descriptors=descriptors,
        parent_chain=parent_chain,
    )


def _parse_parent_chain(
    read: GuestMemoryReader, address: int
) -> tuple[ClassTypeIdentity, ...]:
    chain: list[ClassTypeIdentity] = []
    seen: set[int] = set()
    while address:
        if address in seen:
            raise ValueError(f"class type parent chain cycles at 0x{address:08x}")
        if len(chain) >= MAX_PARENT_CHAIN_DEPTH:
            raise ValueError("class type parent chain exceeds its bound")
        seen.add(address)
        raw = read(address, CLASS_TYPE_ENTRY_SIZE)
        class_id = _u32(raw, CLASS_TYPE_ID_OFFSET)
        name_address = _u32(raw, CLASS_TYPE_NAME_POINTER_OFFSET)
        if name_address == 0:
            raise ValueError(f"class type 0x{class_id:08x} has a null parent name")
        chain.append(
            ClassTypeIdentity(
                address=address,
                class_id=class_id,
                name=_read_string(read, name_address),
            )
        )
        address = _u32(raw, CLASS_TYPE_PARENT_POINTER_OFFSET)
    return tuple(chain)


def _parse_descriptors(
    read: GuestMemoryReader, address: int
) -> tuple[EditableDescriptor, ...]:
    descriptors: list[EditableDescriptor] = []
    for index in range(MAX_DESCRIPTOR_ENTRIES):
        raw = read(address + index * EDITABLE_DESCRIPTOR_SIZE, EDITABLE_DESCRIPTOR_SIZE)
        if _u32(raw, EDITABLE_DESCRIPTOR_ID_OFFSET) == 0:
            return tuple(descriptors)
        descriptors.append(
            EditableDescriptor(
                field_id=_u32(raw, EDITABLE_DESCRIPTOR_ID_OFFSET),
                size=_u16(raw, EDITABLE_DESCRIPTOR_SIZE_OFFSET),
                kind=raw[EDITABLE_DESCRIPTOR_KIND_OFFSET],
                flags=raw[EDITABLE_DESCRIPTOR_FLAGS_OFFSET],
                object_offset=_u32(raw, EDITABLE_DESCRIPTOR_OBJECT_OFFSET),
            )
        )
    raise ValueError(f"editable descriptor table at 0x{address:08x} is unterminated")


def _read_string(read: GuestMemoryReader, address: int) -> str:
    raw = read(address, MAX_CLASS_NAME_BYTES)
    terminator = raw.find(b"\0")
    if terminator < 0:
        raise ValueError(f"class name at 0x{address:08x} is unterminated")
    try:
        return raw[:terminator].decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError(f"class name at 0x{address:08x} is not ASCII") from error


def _u16(raw: bytes, offset: int) -> int:
    if offset + 2 > len(raw):
        raise ValueError("guest memory response is truncated")
    return struct.unpack_from("<H", raw, offset)[0]


def _u32(raw: bytes, offset: int) -> int:
    if offset + 4 > len(raw):
        raise ValueError("guest memory response is truncated")
    return struct.unpack_from("<I", raw, offset)[0]
