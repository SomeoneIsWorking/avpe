import struct
import unittest

from avpe.save_message_types import (
    MESSAGE_DYNAMIC_SIZE,
    MESSAGE_TYPE_DATABASE_SIZE,
    fixed_message_size,
    parse_message_type_database,
)


class SaveMessageTypeTests(unittest.TestCase):
    def test_parses_fixed_slots_and_resolves_registered_size(self) -> None:
        data = bytearray(MESSAGE_TYPE_DATABASE_SIZE)
        struct.pack_into("<III", data, 0x2A * 12, 0x12345678, 0x14, 0x1234)

        entries = parse_message_type_database(bytes(data))

        self.assertEqual(entries[0], None)
        self.assertEqual(entries[0x2A].create_address, 0x12345678)
        self.assertEqual(entries[0x2A].size, 0x14)
        self.assertEqual(fixed_message_size(entries, 0x3002A), 0x14)

    def test_rejects_unregistered_dynamic_and_short_databases(self) -> None:
        data = bytearray(MESSAGE_TYPE_DATABASE_SIZE)
        struct.pack_into("<III", data, 0x2A * 12, 0x1234, MESSAGE_DYNAMIC_SIZE, 0)
        entries = parse_message_type_database(bytes(data))

        with self.assertRaisesRegex(ValueError, "not registered"):
            fixed_message_size(entries, 0x2B)
        with self.assertRaisesRegex(ValueError, "dynamic size"):
            fixed_message_size(entries, 0x2A)
        with self.assertRaisesRegex(ValueError, "truncated"):
            parse_message_type_database(b"\0" * (MESSAGE_TYPE_DATABASE_SIZE - 1))
