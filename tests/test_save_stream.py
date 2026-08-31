import struct
import unittest

from avpe.save_stream import (
    SaveClassMetadata,
    parse_serialized_object_stream,
    serialize_object_stream,
)
from avpe.save_format import (
    OBJECT_NESTED_OR_END_MARKER,
    OBJECT_TOP_LEVEL_OR_END_MARKER,
)


def _header(marker: int, class_id: int, serial: int, state: int) -> bytes:
    return struct.pack("<4I", marker, class_id, serial, state)


def _terminator(marker: int) -> bytes:
    return _header(marker, 0, 0, 0)


class SaveStreamTests(unittest.TestCase):
    def test_parses_delayed_save_ex_after_nested_structure(self) -> None:
        root_id = 0x100
        child_id = 0x200
        data = b"".join(
            (
                _header(OBJECT_TOP_LEVEL_OR_END_MARKER, root_id, 7, 3),
                _header(OBJECT_NESTED_OR_END_MARKER, child_id, 8, 4),
                _terminator(OBJECT_NESTED_OR_END_MARKER),
                _terminator(OBJECT_NESTED_OR_END_MARKER),
                struct.pack("<I", 0xAABBCCDD),
                struct.pack("<I", 0x11223344),
                _terminator(OBJECT_TOP_LEVEL_OR_END_MARKER),
            )
        )
        metadata = {
            root_id: SaveClassMetadata(root_id, "GUnit", (), "GUnit"),
            child_id: SaveClassMetadata(child_id, "GUnit", (), "GUnit"),
        }

        parsed = parse_serialized_object_stream(data, metadata)

        self.assertEqual(parsed.top_level_objects, (0,))
        self.assertEqual(parsed.terminator_offset, len(data) - 16)
        self.assertEqual(
            [record.parent_index for record in parsed.objects], [None, 0]
        )
        self.assertEqual(
            [record.children for record in parsed.objects], [(1,), ()]
        )
        self.assertEqual(
            [record.structure_end_offset for record in parsed.objects], [64, 48]
        )
        self.assertEqual(
            [(record.save_ex_offset, record.save_ex_end_offset) for record in parsed.objects],
            [(64, 68), (68, 72)],
        )
        self.assertEqual(
            [record.save_ex.value for record in parsed.objects],
            [0xAABBCCDD, 0x11223344],
        )

        report = serialize_object_stream(parsed)
        self.assertEqual(report["object_count"], 2)
        self.assertEqual(report["objects"][1]["parent_index"], 0)

    def test_rejects_unknown_class_before_consuming_payload(self) -> None:
        data = _header(OBJECT_TOP_LEVEL_OR_END_MARKER, 0xBAD, 1, 0)

        with self.assertRaisesRegex(ValueError, "unknown class"):
            parse_serialized_object_stream(data, {})

    def test_rejects_nonzero_trailing_bytes(self) -> None:
        data = _terminator(OBJECT_TOP_LEVEL_OR_END_MARKER) + b"\x01"

        with self.assertRaisesRegex(ValueError, "nonzero or excessive"):
            parse_serialized_object_stream(data, {})


if __name__ == "__main__":
    unittest.main()
