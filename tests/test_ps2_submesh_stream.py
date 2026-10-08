import struct
import unittest

from avpe.ps2_submesh_stream import decode_submesh_stream, packet_size

# The live Back prompt stream at 0x0135EAB4, captured during the pause menu.
_BACK_PROMPT_WORDS = [
    0x00040004, 0x00000018, 0x43400000, 0x42200000,
    0x40A00000, 0x00000000, 0x00000000, 0x60000004,
    0x00000000, 0x00000000, 0x6D088025, 0x33327FFF,
    0x10027FFF, 0x00000000, 0xFFFF7FFF, 0x7FFF7FFF,
    0x10027FFF, 0x00000000, 0x07F27FFF, 0x33326FFF,
    0x080F7FFF, 0x00000000, 0xFFFF7FFF, 0x7FFF6FFF,
    0x080F7FFF, 0x00000000, 0x07F27FFF,
]


def back_prompt_stream() -> bytes:
    return struct.pack(f"<{len(_BACK_PROMPT_WORDS)}I", *_BACK_PROMPT_WORDS)


class SubmeshStreamTest(unittest.TestCase):
    def test_back_prompt_positions_match_the_stored_bounding_box(self) -> None:
        stream = decode_submesh_stream(back_prompt_stream())
        self.assertEqual(stream.vertex_count, 4)
        self.assertEqual(stream.scale, (192.0, 40.0, 5.0))
        low, high = stream.y_extent()
        self.assertAlmostEqual(low, 16.0, places=2)
        self.assertAlmostEqual(high, 40.0, places=2)
        xs = sorted({round(vertex.position[0]) for vertex in stream.vertices})
        self.assertEqual(xs, [168, 192])

    def test_back_prompt_texture_coordinates(self) -> None:
        stream = decode_submesh_stream(back_prompt_stream())
        self.assertEqual([vertex.u for vertex in stream.vertices], [0x1002, 0x1002, 0x080F, 0x080F])
        self.assertEqual([vertex.v for vertex in stream.vertices], [-1, 0x07F2, -1, 0x07F2])

    def test_packet_size_covers_the_whole_payload(self) -> None:
        self.assertEqual(packet_size(back_prompt_stream()), len(back_prompt_stream()))

    def test_rejects_a_packet_that_is_not_v4_16(self) -> None:
        words = list(_BACK_PROMPT_WORDS)
        words[10] = 0x6C088025
        with self.assertRaises(ValueError):
            decode_submesh_stream(struct.pack(f"<{len(words)}I", *words))


if __name__ == "__main__":
    unittest.main()
