import struct
import unittest

from avpe.save_ex import (
    PLAYER_MANAGER_FIXED_BYTES,
    parse_gdrop_ship_payload,
    parse_gfow_saver_payload,
    parse_gobject_ai_payload,
    parse_gobject_ai_payload_from_database,
    parse_gplayer_manager_payload,
    parse_gunit_payload,
)
from avpe.save_message_types import MessageTypeEntry


class SaveExTests(unittest.TestCase):
    def test_reads_gunit_and_dropship_fixed_payloads(self) -> None:
        unit = parse_gunit_payload(struct.pack("<I", 0x12345678))
        dropship = parse_gdrop_ship_payload(struct.pack("<II", 7, 9))

        self.assertEqual((unit.value, unit.consumed_bytes), (0x12345678, 4))
        self.assertEqual(
            (dropship.current_state, dropship.unit_value, dropship.consumed_bytes),
            (7, 9, 8),
        )

    def test_reads_gfow_bitmap_with_expected_count(self) -> None:
        data = struct.pack("<III", 33, 0x80000001, 0x00000001) + b"tail"

        parsed = parse_gfow_saver_payload(data, expected_word_count=2)

        self.assertEqual(parsed.bit_count, 33)
        self.assertEqual(parsed.words, (0x80000001, 1))
        self.assertEqual(parsed.consumed_bytes, 12)

    def test_reads_type_sized_object_ai_messages(self) -> None:
        data = struct.pack("<I I", 2, 0x10) + b"abcd" + struct.pack("<I", 0x20) + b"xy"

        parsed = parse_gobject_ai_payload(data, {0x10: 4, 0x20: 2}.get)

        self.assertEqual([message.type_id for message in parsed.messages], [0x10, 0x20])
        self.assertEqual([message.raw for message in parsed.messages], [b"abcd", b"xy"])
        self.assertEqual(parsed.consumed_bytes, len(data))

    def test_reads_dynamic_object_ai_message_from_database_size_field(self) -> None:
        entries: list[MessageTypeEntry | None] = [None] * 256
        entries[0x67] = MessageTypeEntry(0x67, 0x1234, 0xFFFFFFFF, 0)
        message = bytearray(16)
        struct.pack_into("<H", message, 0x0C, len(message))
        data = struct.pack("<II", 1, 0x67) + message

        parsed = parse_gobject_ai_payload_from_database(data, tuple(entries))

        self.assertEqual(parsed.messages[0].type_id, 0x67)
        self.assertEqual(parsed.messages[0].raw, bytes(message))
        self.assertEqual(parsed.consumed_bytes, len(data))

    def test_reads_active_player_manager_groups_and_skips_inactive(self) -> None:
        data = bytearray(PLAYER_MANAGER_FIXED_BYTES)
        for count in (1, 0, 2, 1):
            data.extend(struct.pack("<I", count))
            data.extend(bytes(range(count * 12)))

        active = parse_gplayer_manager_payload(bytes(data), active=True)
        inactive = parse_gplayer_manager_payload(b"unrelated", active=False)

        self.assertEqual([len(group) for group in active.groups], [1, 0, 2, 1])
        self.assertEqual(active.consumed_bytes, len(data))
        self.assertEqual(inactive.consumed_bytes, 0)

    def test_rejects_truncated_and_inconsistent_variable_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "bitmap is truncated"):
            parse_gfow_saver_payload(struct.pack("<I", 33))
        with self.assertRaisesRegex(ValueError, "expected count"):
            parse_gfow_saver_payload(struct.pack("<III", 33, 0, 0), expected_word_count=3)
        with self.assertRaisesRegex(ValueError, "message is truncated"):
            parse_gobject_ai_payload(struct.pack("<II", 1, 0x10), lambda _: 4)
        with self.assertRaisesRegex(ValueError, "fixed payload is truncated"):
            parse_gplayer_manager_payload(b"short", active=True)
