import struct
import unittest

from avpe.save_descriptor_probe import (
    EditableDescriptor,
    descriptor_wire_size,
    inspect_class_type_database,
    parse_serialized_descriptor_body,
    resolve_save_ex_dispatch,
)


class GuestMemory:
    def __init__(self) -> None:
        self.cells: dict[int, bytes] = {}

    def add(self, address: int, data: bytes) -> None:
        self.cells[address] = data

    def read(self, address: int, length: int) -> bytes:
        for base, data in self.cells.items():
            if base <= address and address + length <= base + len(data):
                start = address - base
                return data[start:start + length]
        raise ValueError(f"unmapped guest address 0x{address:08x}")


class SaveDescriptorProbeTests(unittest.TestCase):
    def test_resolves_inherited_and_overridden_save_ex(self) -> None:
        self.assertEqual(
            resolve_save_ex_dispatch("GMarineInfantry", ("GMarine", "GUnit")),
            resolve_save_ex_dispatch("GUnit", ()),
        )
        self.assertEqual(
            resolve_save_ex_dispatch("GDropShip", ("GVehicle", "GUnit")).implementation,
            "GDropShip",
        )
        self.assertEqual(
            resolve_save_ex_dispatch("GAlienPlayerManager", ("GPlayerManager",)).implementation,
            "GPlayerManager",
        )
        self.assertEqual(
            resolve_save_ex_dispatch("GAdultAlienAI", ("GUnitAI", "GObjectAI")).implementation,
            "GObjectAI",
        )

    def test_splits_scalar_pointer_and_pointer_array_wire_fields(self) -> None:
        descriptors = (
            EditableDescriptor(0x11, 2, 1, 0, 0),
            EditableDescriptor(0x22, 4, 7, 0, 4),
            EditableDescriptor(0x33, 8, 9, 0, 8),
        )
        data = bytearray(4 + 12 + 16)
        data[:4] = b"AB\0\0"
        struct.pack_into("<I H B B I", data, 4, 0x22, 4, 0, 0, 0x1234)
        struct.pack_into("<I H B B II", data, 16, 0x33, 8, 0, 0, 7, 8)
        parsed = parse_serialized_descriptor_body(bytes(data) + b"EXTRA", descriptors)

        self.assertEqual(parsed.consumed_bytes, 32)
        self.assertEqual(parsed.fields[0].raw, b"AB\0\0")
        self.assertEqual(parsed.fields[1].pointer_identities, (0x1234,))
        self.assertEqual(parsed.fields[2].pointer_identities, (7, 8))

    def test_descriptor_wire_size_rejects_unknown_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported editable descriptor kind"):
            descriptor_wire_size(EditableDescriptor(1, 4, 10, 0, 0))

    def test_descriptor_body_rejects_truncated_pointer_description(self) -> None:
        descriptor = EditableDescriptor(0x22, 4, 7, 0, 4)
        with self.assertRaisesRegex(ValueError, "is truncated"):
            parse_serialized_descriptor_body(b"\0" * 11, (descriptor,))

    def test_descriptor_body_rejects_mismatched_pointer_description(self) -> None:
        descriptor = EditableDescriptor(0x22, 4, 7, 0, 4)
        data = struct.pack("<I H B B I", 0x99, 4, 0, 0, 0)
        with self.assertRaisesRegex(ValueError, "mismatched wire description"):
            parse_serialized_descriptor_body(data, (descriptor,))

    def test_selects_observed_classes_and_parses_descriptors(self) -> None:
        memory = GuestMemory()
        database = 0x1000
        array = 0x2000
        entry_a = 0x3000
        entry_b = 0x3040
        name_a = 0x4000
        name_b = 0x4010
        desc_a = 0x5000
        desc_b = 0x5040
        memory.add(database, struct.pack("<3I", array, 2, 2))
        memory.add(array, struct.pack("<2I", entry_a, entry_b))
        memory.add(
            entry_a,
            struct.pack("<8I", 0xAABBCCDD, name_a, 0, 0, 0, 0x1234, 0, desc_a),
        )
        memory.add(
            entry_b,
            struct.pack("<8I", 0x11223344, name_b, 0, 0x3010, 0, 0x5678, 0, desc_b),
        )
        memory.add(name_a, b"FirstClass\0".ljust(128, b"\0"))
        memory.add(name_b, b"SecondClass\0".ljust(128, b"\0"))
        memory.add(0x3010, struct.pack("<8I", 0xABCDEF01, 0x4020, 0, 0, 0, 0, 0, 0))
        memory.add(0x4020, b"ParentClass\0".ljust(128, b"\0"))
        memory.add(
            desc_a,
            struct.pack("<I H B B I", 7, 4, 3, 1, 0x28)
            + b"\0" * 12,
        )
        memory.add(
            desc_b,
            struct.pack("<I H B B I", 8, 24, 8, 1, 0x40)
            + struct.pack("<I H B B I", 9, 4, 7, 0x11, 0x50)
            + struct.pack("<III", 0, 0x01030004, 0),
        )

        inventory = inspect_class_type_database(memory.read, {0x11223344}, database)

        self.assertEqual(inventory["entry_count"], 2)
        self.assertEqual(inventory["missing_class_ids"], [])
        self.assertEqual(len(inventory["entries"]), 1)
        entry = inventory["entries"][0]
        self.assertEqual(entry["name"], "SecondClass")
        self.assertEqual(entry["parent_address"], 0x3010)
        self.assertEqual(entry["parent_chain"][0]["name"], "ParentClass")
        self.assertEqual(entry["descriptors"][1]["kind"], 7)
        self.assertEqual(entry["descriptors"][1]["flags"], 0x11)
        self.assertEqual(entry["save_ex"]["implementation"], "GObject")

    def test_reports_requested_class_ids_missing_from_live_database(self) -> None:
        memory = GuestMemory()
        memory.add(0x1000, struct.pack("<3I", 0x2000, 1, 1))
        memory.add(0x2000, struct.pack("<I", 0x3000))
        memory.add(0x3000, struct.pack("<8I", 1, 0x4000, 0, 0, 0, 0, 0, 0x5000))
        memory.add(0x4000, b"Class\0".ljust(128, b"\0"))
        memory.add(0x5000, struct.pack("<III", 0, 0x01030004, 0))

        inventory = inspect_class_type_database(memory.read, {1, 2}, 0x1000)

        self.assertEqual(inventory["missing_class_ids"], [2])

    def test_rejects_unbounded_database(self) -> None:
        memory = GuestMemory()
        memory.add(0x1000, struct.pack("<3I", 0x2000, 4097, 4097))

        with self.assertRaisesRegex(ValueError, "invalid bounded array"):
            inspect_class_type_database(memory.read, database_address=0x1000)

    def test_rejects_cyclic_parent_chain(self) -> None:
        memory = GuestMemory()
        memory.add(0x1000, struct.pack("<3I", 0x2000, 1, 1))
        memory.add(0x2000, struct.pack("<I", 0x3000))
        memory.add(
            0x3000,
            struct.pack("<8I", 1, 0x4000, 0, 0x3000, 0, 0, 0, 0x5000),
        )
        memory.add(0x4000, b"Class\0".ljust(128, b"\0"))
        memory.add(0x5000, struct.pack("<III", 0, 0x01030004, 0))

        with self.assertRaisesRegex(ValueError, "parent chain cycles"):
            inspect_class_type_database(memory.read, {1}, 0x1000)
