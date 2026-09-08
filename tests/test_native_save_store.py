import json
import struct
import tempfile
import unittest
from pathlib import Path

from avpe.native_save_store import (
    NativeSaveStoreError,
    list_slots,
    read_slot,
    write_slot,
)
from avpe.save_format import (
    GAME_LEVEL_SIZE,
    GAME_TIME_OFFSET,
    OBJECT_NESTED_OR_END_MARKER,
    OBJECT_STREAM_OFFSET,
    OBJECT_TOP_LEVEL_OR_END_MARKER,
    OUTER_FIELDS_OFFSET,
    OUTER_RECORD_SIZE,
    REPEATED_GAME_TIME_OFFSET,
)


def _encode_literal_words(words: list[int]) -> bytes:
    encoded = bytearray(struct.pack("<H", 0x07FF))
    for start in range(0, len(words), 16):
        chunk = words[start:start + 16]
        if len(chunk) == 16:
            encoded.extend(struct.pack("<H", 0))
        else:
            encoded.extend(struct.pack("<H", 0x8000 >> len(chunk)))
        encoded.extend(struct.pack("<" + "H" * len(chunk), *chunk))
        if len(chunk) != 16:
            encoded.extend(struct.pack("<H", 0))
            return bytes(encoded)
    encoded.extend(struct.pack("<HH", 0x8000, 0))
    return bytes(encoded)


def _record(level: bytes, game_time: float) -> bytes:
    decoded = bytearray(OBJECT_STREAM_OFFSET + 80)
    decoded[:GAME_LEVEL_SIZE] = level.ljust(GAME_LEVEL_SIZE, b"\0")
    struct.pack_into("<f", decoded, GAME_TIME_OFFSET, game_time)
    struct.pack_into("<f", decoded, REPEATED_GAME_TIME_OFFSET, game_time)
    offset = OBJECT_STREAM_OFFSET
    for words in (
        (OBJECT_TOP_LEVEL_OR_END_MARKER, 0x1234, 0x20, 1),
        (OBJECT_NESTED_OR_END_MARKER, 0x5678, 0x10, 2),
        (OBJECT_NESTED_OR_END_MARKER, 0, 0, 0),
        (OBJECT_NESTED_OR_END_MARKER, 0, 0, 0),
        (OBJECT_TOP_LEVEL_OR_END_MARKER, 0, 0, 0),
    ):
        struct.pack_into("<4I", decoded, offset, *words)
        offset += 16
    record = bytearray(OUTER_RECORD_SIZE)
    struct.pack_into("<6I", record, OUTER_FIELDS_OFFSET, 1, 0, 2, 0xFFFFFFFF, 0x20, 0)
    record.extend(_encode_literal_words(list(struct.unpack("<" + "H" * (len(decoded) // 2), decoded))))
    return bytes(record)


class NativeSaveStoreTests(unittest.TestCase):
    def test_round_trips_distinct_slots_and_preserves_existing_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.avpesave"
            first = _record(b"M01/background.tbd\0", 12.5)
            second = _record(b"M02/background.tbd\0", 24.0)

            write_slot(path, 0, first)
            write_slot(path, 1, second)

            self.assertEqual(list_slots(path), (0, 1))
            self.assertEqual(read_slot(path, 0), first)
            self.assertEqual(read_slot(path, 1), second)

    def test_rejects_truncated_container_without_replacing_valid_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.avpesave"
            record = _record(b"M01/background.tbd\0", 12.5)
            write_slot(path, 0, record)
            original = path.read_bytes()
            path.write_bytes(original[: len(original) // 2])

            with self.assertRaisesRegex(NativeSaveStoreError, "valid JSON"):
                read_slot(path, 0)

    def test_rejects_corrupt_record_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.avpesave"
            write_slot(path, 0, _record(b"M01/background.tbd\0", 12.5))
            container = json.loads(path.read_text())
            container["slots"]["0"]["sha256"] = "0" * 64
            path.write_text(json.dumps(container))

            with self.assertRaisesRegex(NativeSaveStoreError, "integrity check"):
                read_slot(path, 0)

    def test_rejects_incompatible_title_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.avpesave"
            write_slot(path, 0, _record(b"M01/background.tbd\0", 12.5))
            text = path.read_text().replace("SLUS-20147", "OTHER-00000", 1)
            path.write_text(text)

            with self.assertRaisesRegex(NativeSaveStoreError, "another title revision"):
                read_slot(path, 0)
