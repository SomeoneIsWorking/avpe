import struct
import unittest

from avpe.save_format import (
    GAME_TIME_OFFSET,
    GAME_LEVEL_SIZE,
    OBJECT_NESTED_OR_END_MARKER,
    OBJECT_STREAM_OFFSET,
    OBJECT_TOP_LEVEL_OR_END_MARKER,
    OUTER_RECORD_SIZE,
    OUTER_FIELDS_OFFSET,
    REPEATED_GAME_TIME_OFFSET,
    decode_bwj,
    parse_game_save_record,
)


def encode_literal_words(words: list[int]) -> bytes:
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
    encoded.extend(struct.pack("<H", 0x8000))
    encoded.extend(struct.pack("<H", 0))
    return bytes(encoded)


class SaveFormatTests(unittest.TestCase):
    def test_decodes_literals_and_overlapping_back_reference(self) -> None:
        stream = bytearray(struct.pack("<HHHH", 0x07FF, 0x4000, 0x0042, 0x0022))
        stream.extend(struct.pack("<" + "H" * 14, *range(14)))
        stream.extend(struct.pack("<HH", 0x8000, 0))

        decoded = decode_bwj(bytes(stream), 128)

        self.assertEqual(decoded.mode, 0x07FF)
        self.assertEqual(decoded.shift, 5)
        self.assertEqual(decoded.length_mask, 0x1F)
        self.assertEqual(struct.unpack_from("<H", decoded.data, 0)[0], 0x0042)
        self.assertEqual(struct.unpack_from("<H", decoded.data, 2)[0], 0x0042)
        self.assertEqual(struct.unpack_from("<H", decoded.data, 4)[0], 0x0042)

    def test_parses_fixed_prefix_and_opaque_object_markers(self) -> None:
        decoded = bytearray(OBJECT_STREAM_OFFSET + 80)
        level = b"M01/background.tbd\0"
        decoded[:GAME_LEVEL_SIZE] = level.ljust(GAME_LEVEL_SIZE, b"\0")
        decoded[len(level)] = 1
        struct.pack_into("<f", decoded, GAME_TIME_OFFSET, 12.5)
        struct.pack_into("<f", decoded, REPEATED_GAME_TIME_OFFSET, 12.5)
        object_offset = OBJECT_STREAM_OFFSET
        for words in (
            (OBJECT_TOP_LEVEL_OR_END_MARKER, 0x1234, 0x20, 0x00000001),
            (OBJECT_NESTED_OR_END_MARKER, 0x5678, 0x10, 0x00000002),
            (OBJECT_NESTED_OR_END_MARKER, 0, 0, 0),
            (OBJECT_NESTED_OR_END_MARKER, 0, 0, 0),
            (OBJECT_TOP_LEVEL_OR_END_MARKER, 0, 0, 0),
        ):
            struct.pack_into("<4I", decoded, object_offset, *words)
            object_offset += 16
        record = bytearray(OUTER_RECORD_SIZE)
        struct.pack_into(
            "<6I", record, OUTER_FIELDS_OFFSET, 1, 0, 2, 0xFFFFFFFF, 0x20, 0
        )
        record.extend(
            encode_literal_words(
                list(struct.unpack("<" + "H" * (len(decoded) // 2), decoded))
            )
        )

        parsed = parse_game_save_record(bytes(record))

        self.assertEqual(parsed["bwj"]["mode"], 0x07FF)
        self.assertEqual(parsed["stream"]["level"], "M01/background.tbd")
        self.assertEqual(
            parsed["stream"]["level_suffix_hex"],
            (b"\x01" + b"\0" * (GAME_LEVEL_SIZE - len(level) - 1)).hex(),
        )
        self.assertTrue(parsed["stream"]["game_time_bytes_match"])
        self.assertEqual(parsed["stream"]["object_marker_counts"], {
            "top_level_or_end": 2,
            "nested_or_end": 3,
        })
        self.assertEqual(
            parsed["stream"]["object_stream_summary"],
            {
                "header_size": 16,
                "top_level_starts": 1,
                "top_level_terminators": 1,
                "nested_starts": 1,
                "nested_terminators": 2,
                "class_id_counts": {0x1234: 1, 0x5678: 1},
                "max_depth": 2,
                "active_objects": 0,
                "structure_balanced": True,
            },
        )

    def test_rejects_truncated_object_header(self) -> None:
        decoded = bytearray(OBJECT_STREAM_OFFSET + 4)
        decoded[:GAME_LEVEL_SIZE] = b"M01/background.tbd\0".ljust(GAME_LEVEL_SIZE, b"\0")
        struct.pack_into("<f", decoded, GAME_TIME_OFFSET, 1.0)
        struct.pack_into("<f", decoded, REPEATED_GAME_TIME_OFFSET, 1.0)
        struct.pack_into("<I", decoded, OBJECT_STREAM_OFFSET, OBJECT_TOP_LEVEL_OR_END_MARKER)
        record = bytearray(OUTER_RECORD_SIZE)
        record.extend(
            encode_literal_words(
                list(struct.unpack("<" + "H" * (len(decoded) // 2), decoded))
            )
        )

        with self.assertRaisesRegex(ValueError, "object header is truncated"):
            parse_game_save_record(bytes(record))

    def test_rejects_unbalanced_object_end(self) -> None:
        decoded = bytearray(OBJECT_STREAM_OFFSET + 16)
        decoded[:GAME_LEVEL_SIZE] = b"M01/background.tbd\0".ljust(GAME_LEVEL_SIZE, b"\0")
        struct.pack_into("<f", decoded, GAME_TIME_OFFSET, 1.0)
        struct.pack_into("<f", decoded, REPEATED_GAME_TIME_OFFSET, 1.0)
        struct.pack_into(
            "<4I", decoded, OBJECT_STREAM_OFFSET, OBJECT_NESTED_OR_END_MARKER, 0, 0, 0
        )
        record = bytearray(OUTER_RECORD_SIZE)
        record.extend(
            encode_literal_words(
                list(struct.unpack("<" + "H" * (len(decoded) // 2), decoded))
            )
        )

        with self.assertRaisesRegex(ValueError, "closes an empty object stack"):
            parse_game_save_record(bytes(record))

    def test_rejects_invalid_back_reference_and_output_bound(self) -> None:
        invalid = struct.pack("<HHH", 0x07FF, 0x8000, 0x0022)
        with self.assertRaisesRegex(ValueError, "distance"):
            decode_bwj(invalid, 128)
        with self.assertRaisesRegex(ValueError, "exceeds the configured bound"):
            decode_bwj(encode_literal_words([1] * 16), 2)

    def test_rejects_mismatched_game_time_prefix(self) -> None:
        decoded = bytearray(OBJECT_STREAM_OFFSET + 16)
        decoded[:GAME_LEVEL_SIZE] = b"M01/background.tbd\0".ljust(GAME_LEVEL_SIZE, b"\0")
        struct.pack_into("<f", decoded, GAME_TIME_OFFSET, 1.0)
        struct.pack_into("<f", decoded, REPEATED_GAME_TIME_OFFSET, 2.0)
        struct.pack_into(
            "<4I", decoded, OBJECT_STREAM_OFFSET, OBJECT_TOP_LEVEL_OR_END_MARKER, 0, 0, 0
        )
        record = bytearray(OUTER_RECORD_SIZE)
        record.extend(
            encode_literal_words(
                list(struct.unpack("<" + "H" * (len(decoded) // 2), decoded))
            )
        )

        parsed = parse_game_save_record(bytes(record))

        self.assertFalse(parsed["stream"]["game_time_bytes_match"])
