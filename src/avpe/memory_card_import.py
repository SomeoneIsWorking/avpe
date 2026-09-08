"""Bounded importer for the title's raw PS2 memory-card filesystem."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
import struct
from typing import Iterable
import zlib

from avpe.native_save_store import (
    MAX_RECORD_BYTES,
    PROFILE_PAYLOAD_BYTES,
    PROFILE_REVISION,
    NativeSaveStoreError,
    replace_container,
)
from avpe.save_format import parse_game_save_record


CARD_MAGIC = b"Sony PS2 Memory Card Format "
PAGE_BYTES = 0x200
ECC_BYTES = 0x10
RAW_PAGE_BYTES = PAGE_BYTES + ECC_BYTES
PAGES_PER_CLUSTER = 2
CLUSTER_BYTES = PAGE_BYTES * PAGES_PER_CLUSTER
INDIRECT_FAT_ENTRIES = CLUSTER_BYTES // 4
LAST_DATA_CLUSTER = 0x7FFFFFFF
NEXT_DATA_CLUSTER_MASK = 0x7FFFFFFF
DATA_CLUSTER_IN_USE = 0x80000000
MODE_FILE = 0x10
MODE_DIRECTORY = 0x20
MODE_USED = 0x8000
MAX_DIRECTORY_ENTRIES = 4096
PROFILE_RECORD_BYTES = 0x118 + PROFILE_PAYLOAD_BYTES
PROFILE_DIRECTORY_PREFIX = "BASLUS-20147"
SLOT_NAME = re.compile(r"(\d+)\.SAV\Z")


class MemoryCardImportError(ValueError):
    """The card is not a supported, internally consistent AVP:E card."""


@dataclass(frozen=True)
class ImportedMemoryCard:
    profile: bytes
    slots: dict[int, bytes]
    directory: str


@dataclass(frozen=True)
class _Entry:
    mode: int
    length: int
    cluster: int
    name: str


class _Card:
    def __init__(self, raw: bytes):
        if len(raw) < PAGE_BYTES or raw[: len(CARD_MAGIC)] != CARD_MAGIC:
            raise MemoryCardImportError("memory-card image has no PS2 format header")
        self.raw = raw
        self.clusters, self.alloc_offset, self.alloc_end, self.root = struct.unpack_from(
            "<4I", raw, 0x30
        )
        page_len, pages_per_cluster, pages_per_block = struct.unpack_from(
            "<3H", raw, 0x28
        )
        if (page_len, pages_per_cluster, pages_per_block) != (PAGE_BYTES, 2, 16):
            raise MemoryCardImportError("memory-card geometry is unsupported")
        expected = self.clusters * PAGES_PER_CLUSTER * RAW_PAGE_BYTES
        if self.clusters == 0 or len(raw) != expected:
            raise MemoryCardImportError("memory-card image size does not match its header")
        if not 0 < self.alloc_offset < self.alloc_end < self.clusters:
            raise MemoryCardImportError("memory-card data allocation bounds are invalid")
        if self.root >= self.alloc_end:
            raise MemoryCardImportError("memory-card root directory is outside data")
        self.fat = self._read_fat()

    def payload_cluster(self, physical_cluster: int) -> bytes:
        if not 0 <= physical_cluster < self.clusters:
            raise MemoryCardImportError("memory-card physical cluster is out of range")
        start = physical_cluster * PAGES_PER_CLUSTER * RAW_PAGE_BYTES
        return b"".join(
            self.raw[start + page * RAW_PAGE_BYTES : start + page * RAW_PAGE_BYTES + PAGE_BYTES]
            for page in range(PAGES_PER_CLUSTER)
        )

    def _read_fat(self) -> tuple[int, ...]:
        fat_cluster_count = (self.clusters + INDIRECT_FAT_ENTRIES - 1) // INDIRECT_FAT_ENTRIES
        ifc_locations = struct.unpack_from("<32I", self.raw, 0x50)
        ifc_count = (fat_cluster_count + INDIRECT_FAT_ENTRIES - 1) // INDIRECT_FAT_ENTRIES
        if ifc_count > len(ifc_locations):
            raise MemoryCardImportError("memory-card FAT exceeds its indirect table")
        indirect = b"".join(
            self.payload_cluster(ifc_locations[index]) for index in range(ifc_count)
        )
        fat_locations = struct.unpack_from(f"<{ifc_count * INDIRECT_FAT_ENTRIES}I", indirect)
        selected = fat_locations[:fat_cluster_count]
        if any(location >= self.clusters for location in selected):
            raise MemoryCardImportError("memory-card FAT points outside the image")
        values = b"".join(self.payload_cluster(location) for location in selected)
        return struct.unpack_from(f"<{self.clusters}I", values)

    def chain(self, start: int) -> tuple[int, ...]:
        if start == 0xFFFFFFFF:
            return ()
        if start >= self.alloc_end:
            raise MemoryCardImportError("memory-card data chain starts outside allocation")
        result: list[int] = []
        seen: set[int] = set()
        current = start
        while True:
            if current in seen:
                raise MemoryCardImportError("memory-card data chain contains a cycle")
            if current >= self.alloc_end:
                raise MemoryCardImportError("memory-card data chain leaves allocation")
            seen.add(current)
            result.append(current)
            value = self.fat[current]
            if not value & DATA_CLUSTER_IN_USE:
                raise MemoryCardImportError("memory-card data chain references a free cluster")
            next_cluster = value & NEXT_DATA_CLUSTER_MASK
            if next_cluster == LAST_DATA_CLUSTER:
                return tuple(result)
            current = next_cluster

    def read_data(self, start: int, length: int) -> bytes:
        if length < 0:
            raise MemoryCardImportError("memory-card file length is negative")
        if length == 0:
            if start != 0xFFFFFFFF:
                self.chain(start)
            return b""
        chain = self.chain(start)
        if len(chain) * CLUSTER_BYTES < length:
            raise MemoryCardImportError("memory-card file chain is shorter than its length")
        return b"".join(
            self.payload_cluster(self.alloc_offset + cluster) for cluster in chain
        )[:length]

    def directory(self, start: int, count: int) -> tuple[_Entry, ...]:
        if not 0 <= count <= MAX_DIRECTORY_ENTRIES:
            raise MemoryCardImportError("memory-card directory entry count is unreasonable")
        raw = self.read_data(start, count * PAGE_BYTES)
        entries = []
        for offset in range(0, len(raw), PAGE_BYTES):
            mode, length = struct.unpack_from("<II", raw, offset)
            cluster = struct.unpack_from("<I", raw, offset + 0x10)[0]
            name_bytes = raw[offset + 0x40 : offset + 0x60]
            if b"\0" not in name_bytes:
                raise MemoryCardImportError("memory-card directory name is not terminated")
            try:
                name = name_bytes.split(b"\0", 1)[0].decode("ascii")
            except UnicodeDecodeError as error:
                raise MemoryCardImportError("memory-card directory name is not ASCII") from error
            entries.append(_Entry(mode, length, cluster, name))
        return tuple(entries)


def import_memory_card(card_path: Path, destination: Path) -> ImportedMemoryCard:
    """Validate and atomically import AVP:E profile and non-empty game slots."""
    try:
        raw = card_path.read_bytes()
    except OSError as error:
        raise MemoryCardImportError(f"could not read memory-card image: {card_path}") from error
    card = _Card(raw)
    root_entries = card.directory(card.root, _directory_count(card, card.root))
    profiles = [
        entry
        for entry in root_entries
        if (
            entry.name.startswith(PROFILE_DIRECTORY_PREFIX)
            and entry.mode & MODE_DIRECTORY
            and entry.mode & MODE_USED
        )
    ]
    if len(profiles) != 1:
        raise MemoryCardImportError("memory-card must contain exactly one AVP:E profile directory")
    profile_dir = profiles[0]
    if not re.fullmatch(r"BASLUS-20147[0-9A-F]{8}", profile_dir.name):
        raise MemoryCardImportError("memory-card profile directory has an invalid title identity")
    entries = card.directory(profile_dir.cluster, profile_dir.length)
    profile_entry = _single_entry(entries, profile_dir.name)
    if (
        profile_entry.length != PROFILE_RECORD_BYTES
        or profile_entry.mode & MODE_FILE == 0
        or profile_entry.mode & MODE_USED == 0
    ):
        raise MemoryCardImportError("memory-card profile record has an invalid size or mode")
    profile = _validate_profile_record(
        card.read_data(profile_entry.cluster, profile_entry.length), profile_dir.name
    )

    slots: dict[int, bytes] = {}
    for entry in entries:
        match = SLOT_NAME.fullmatch(entry.name)
        if match is None:
            continue
        slot = int(match.group(1), 10)
        if slot >= 16 or entry.mode & MODE_FILE == 0 or entry.mode & MODE_USED == 0:
            raise MemoryCardImportError(f"memory-card slot name is outside 0..15: {entry.name}")
        if slot in slots:
            raise MemoryCardImportError(f"memory-card contains duplicate slot {slot}")
        data = card.read_data(entry.cluster, entry.length)
        if not data.strip(b"\0\xff"):
            continue
        if entry.length > MAX_RECORD_BYTES:
            raise MemoryCardImportError(f"memory-card slot {slot} exceeds the native bound")
        try:
            parse_game_save_record(data)
        except ValueError as error:
            raise MemoryCardImportError(
                f"memory-card slot {slot} failed title validation: {error}"
            ) from error
        slots[slot] = data
    try:
        replace_container(destination, profile, slots)
    except NativeSaveStoreError as error:
        raise MemoryCardImportError(f"native save import failed: {error}") from error
    return ImportedMemoryCard(profile, slots, profile_dir.name)


def _directory_count(card: _Card, cluster: int) -> int:
    first = card.read_data(cluster, PAGE_BYTES)
    if len(first) != PAGE_BYTES:
        raise MemoryCardImportError("memory-card directory header is truncated")
    return struct.unpack_from("<I", first, 4)[0]


def _single_entry(entries: Iterable[_Entry], name: str) -> _Entry:
    matches = [entry for entry in entries if entry.name == name]
    if len(matches) != 1:
        raise MemoryCardImportError(f"memory-card must contain exactly one {name} record")
    return matches[0]


def _validate_profile_record(record: bytes, directory: str) -> bytes:
    if len(record) != PROFILE_RECORD_BYTES:
        raise MemoryCardImportError("memory-card profile record length is invalid")
    name = _fixed_string(record[:0x80], "profile name")
    path = _fixed_string(record[0x80:0x100], "profile directory")
    expected_crc = zlib.crc32(name.encode("ascii")) ^ 0xFFFFFFFF
    if path != directory or expected_crc & 0xFFFFFFFF != struct.unpack_from("<I", record, 0x100)[0]:
        raise MemoryCardImportError("memory-card profile identity does not match its directory")
    revision = struct.unpack_from("<I", record, 0x108)[0]
    payload_size = struct.unpack_from("<I", record, 0x110)[0]
    if revision != PROFILE_REVISION or payload_size != PROFILE_PAYLOAD_BYTES:
        raise MemoryCardImportError("memory-card profile revision or payload size is incompatible")
    return record[0x118:]


def _fixed_string(raw: bytes, label: str) -> str:
    if b"\0" not in raw:
        raise MemoryCardImportError(f"memory-card {label} is not NUL-terminated")
    try:
        value = raw.split(b"\0", 1)[0].decode("ascii")
    except UnicodeDecodeError as error:
        raise MemoryCardImportError(f"memory-card {label} is not ASCII") from error
    if not value:
        raise MemoryCardImportError(f"memory-card {label} is empty")
    return value
