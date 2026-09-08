import struct
import tempfile
import unittest
from pathlib import Path
import zlib

from avpe.memory_card_import import MemoryCardImportError, import_memory_card
from avpe.native_save_store import read_profile, list_slots


PAGE = 0x200
RAW_PAGE = 0x210
CLUSTER = PAGE * 2
CLUSTERS = 64
ALLOC_OFFSET = 9


def _entry(mode: int, length: int, cluster: int, name: str) -> bytes:
    raw = bytearray(PAGE)
    struct.pack_into("<II", raw, 0, mode, length)
    struct.pack_into("<I", raw, 0x10, cluster)
    raw[0x40:0x40 + len(name)] = name.encode("ascii")
    return bytes(raw)


def _card() -> bytes:
    raw = bytearray(CLUSTERS * 2 * RAW_PAGE)
    raw[:28] = b"Sony PS2 Memory Card Format "
    struct.pack_into("<HHHH", raw, 0x28, PAGE, 2, 16, 0)
    struct.pack_into("<IIIIII", raw, 0x30, CLUSTERS, ALLOC_OFFSET, 48, 0, 31, 30)
    struct.pack_into("<I", raw, 0x50, 2)

    def put_cluster(physical: int, payload: bytes) -> None:
        for page in range(2):
            start = (physical * 2 + page) * RAW_PAGE
            raw[start:start + PAGE] = payload[page * PAGE:(page + 1) * PAGE]

    indirect = bytearray(CLUSTER)
    struct.pack_into("<I", indirect, 0, 3)
    put_cluster(2, indirect)
    fat = [0] * CLUSTERS
    fat[0] = 0x80000001
    fat[1] = 0x80000004
    fat[2] = 0x80000004
    fat[3] = 0xFFFFFFFF
    fat[4] = 0xFFFFFFFF
    put_cluster(3, struct.pack("<64I", *fat) + bytes(CLUSTER - 64 * 4))

    profile_name = "Test Profile"
    directory = "BASLUS-20147%08X" % (
        zlib.crc32(profile_name.encode()) ^ 0xFFFFFFFF
    )
    profile = bytearray(0x138)
    profile[: len(profile_name)] = profile_name.encode()
    profile[0x80:0x80 + len(directory)] = directory.encode()
    struct.pack_into(
        "<6I",
        profile,
        0x100,
        zlib.crc32(profile_name.encode()) ^ 0xFFFFFFFF,
        0,
        0x1CD9DEE3,
        0,
        0x20,
        0,
    )
    profile[0x118:] = bytes.fromhex(
        "11101000000000000000000001000000000000000000803f0000803f0000803f"
    )

    root = _entry(0x8427, 3, 0, ".") + _entry(0x8427, 0, 0, "..")
    put_cluster(ALLOC_OFFSET, root + bytes(CLUSTER - len(root)))
    put_cluster(ALLOC_OFFSET + 1, _entry(0x8427, 3, 2, directory) + bytes(CLUSTER - PAGE))
    child = _entry(0x8427, 3, 2, ".") + _entry(0x8427, 0, 0, "..")
    put_cluster(ALLOC_OFFSET + 2, child + bytes(CLUSTER - len(child)))
    put_cluster(
        ALLOC_OFFSET + 4,
        _entry(0x8497, len(profile), 3, directory) + bytes(CLUSTER - PAGE),
    )
    put_cluster(ALLOC_OFFSET + 3, profile + bytes(CLUSTER - len(profile)))
    return bytes(raw)


class MemoryCardImportTests(unittest.TestCase):
    def test_imports_profile_from_grounded_card_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            card = Path(directory) / "card.ps2"
            destination = Path(directory) / "native.avpesave"
            card.write_bytes(_card())
            result = import_memory_card(card, destination)

            self.assertEqual(result.directory, "BASLUS-201470015E060")
            self.assertEqual(len(result.profile), 0x20)
            self.assertEqual(result.slots, {})
            self.assertEqual(read_profile(destination), result.profile)
            self.assertEqual(list_slots(destination), ())

    def test_rejects_card_with_corrupt_fat_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            card = bytearray(_card())
            struct.pack_into("<I", card, (3 * 2) * RAW_PAGE + 8, 0x80000002)
            path = Path(directory) / "card.ps2"
            path.write_bytes(card)
            with self.assertRaisesRegex(MemoryCardImportError, "cycle"):
                import_memory_card(path, Path(directory) / "native.avpesave")
