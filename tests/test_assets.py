import json
import struct
import tempfile
import unittest
from pathlib import Path

from avpe.iso9660 import Iso9660Error, IsoImage, SECTOR_SIZE
from avpe.native_assets import (
    STORE_SCHEMA,
    SUPPORTED_ANCHORS,
    NativeAssetError,
    validate_native_store,
    validate_supported_image,
)
from avpe.raw_sector import (
    ISO_SECTOR_SIZE,
    RAW_SECTOR_SIZE,
    SYNC,
    RawSectorError,
    strip_image,
)


def directory_record(extent: int, size: int, flags: int, name: bytes) -> bytes:
    length = 33 + len(name) + (1 if len(name) % 2 == 0 else 0)
    record = bytearray(length)
    record[0] = length
    struct.pack_into("<I", record, 2, extent)
    struct.pack_into(">I", record, 6, extent)
    struct.pack_into("<I", record, 10, size)
    struct.pack_into(">I", record, 14, size)
    record[25] = flags
    struct.pack_into("<H", record, 28, 1)
    struct.pack_into(">H", record, 30, 1)
    record[32] = len(name)
    record[33:33 + len(name)] = name
    return bytes(record)


def make_iso(path: Path) -> None:
    image = bytearray(26 * SECTOR_SIZE)
    pvd = memoryview(image)[16 * SECTOR_SIZE:17 * SECTOR_SIZE]
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    struct.pack_into("<I", pvd, 80, 26)
    struct.pack_into(">I", pvd, 84, 26)
    struct.pack_into("<H", pvd, 128, SECTOR_SIZE)
    struct.pack_into(">H", pvd, 130, SECTOR_SIZE)
    root = directory_record(20, SECTOR_SIZE, 2, b"\x00")
    pvd[156:156 + len(root)] = root

    root_records = b"".join((
        directory_record(20, SECTOR_SIZE, 2, b"\x00"),
        directory_record(20, SECTOR_SIZE, 2, b"\x01"),
        directory_record(21, SECTOR_SIZE, 2, b"DATA"),
        directory_record(22, 5, 0, b"HELLO.TXT;1"),
    ))
    image[20 * SECTOR_SIZE:20 * SECTOR_SIZE + len(root_records)] = root_records
    data_records = b"".join((
        directory_record(21, SECTOR_SIZE, 2, b"\x00"),
        directory_record(20, SECTOR_SIZE, 2, b"\x01"),
        directory_record(23, 4, 0, b"ITEM.BIN;1"),
    ))
    image[21 * SECTOR_SIZE:21 * SECTOR_SIZE + len(data_records)] = data_records
    image[22 * SECTOR_SIZE:22 * SECTOR_SIZE + 5] = b"hello"
    image[23 * SECTOR_SIZE:23 * SECTOR_SIZE + 4] = b"item"
    path.write_bytes(image)


def raw_sector(fill: int, *, form2: bool = False) -> bytes:
    sector = bytearray(RAW_SECTOR_SIZE)
    sector[:12] = SYNC
    sector[15] = 2
    sector[18] = 0x20 if form2 else 0
    sector[24:24 + ISO_SECTOR_SIZE] = bytes([fill]) * ISO_SECTOR_SIZE
    return bytes(sector)


class Iso9660Tests(unittest.TestCase):
    def test_lists_and_extracts_nested_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            iso_path = root / "fixture.iso"
            make_iso(iso_path)

            image = IsoImage(iso_path)
            files = image.files()
            self.assertEqual(
                [str(entry.path) for entry in files],
                ["DATA/ITEM.BIN", "HELLO.TXT"],
            )
            item = files[0]
            self.assertEqual(image.read_file(item), b"item")
            target = root / "out" / "DATA" / "ITEM.BIN"
            image.copy_file(item, target)
            self.assertEqual(target.read_bytes(), b"item")

    def test_rejects_disagreeing_endian_extent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            iso_path = Path(directory) / "fixture.iso"
            make_iso(iso_path)
            data = bytearray(iso_path.read_bytes())
            struct.pack_into(">I", data, 16 * SECTOR_SIZE + 156 + 6, 99)
            iso_path.write_bytes(data)

            with self.assertRaisesRegex(Iso9660Error, "endian copies disagree"):
                IsoImage(iso_path)

    def test_supported_revision_check_rejects_another_iso(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            iso_path = Path(directory) / "fixture.iso"
            make_iso(iso_path)
            image = IsoImage(iso_path)

            with self.assertRaisesRegex(NativeAssetError, "SYSTEM.CNF size mismatch"):
                validate_supported_image(image, image.files())


class RawSectorTests(unittest.TestCase):
    def test_streams_form1_and_marks_form2_without_shifting_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "disc.bin"
            iso = root / "disc.iso"
            raw.write_bytes(raw_sector(0x5A) + raw_sector(0xA5, form2=True))

            report = strip_image(raw, iso)

            self.assertEqual(report.sectors, 2)
            self.assertEqual(report.mode2_form1_sectors, 1)
            self.assertEqual(report.mode2_form2_sectors, 1)
            self.assertEqual(
                iso.read_bytes(),
                bytes([0x5A]) * ISO_SECTOR_SIZE + bytes(ISO_SECTOR_SIZE),
            )

    def test_rejects_bad_sync_without_publishing_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "disc.bin"
            iso = root / "disc.iso"
            raw.write_bytes(bytes(RAW_SECTOR_SIZE))

            with self.assertRaisesRegex(RawSectorError, "invalid sync"):
                strip_image(raw, iso)

            self.assertFalse(iso.exists())
            self.assertFalse((root / ".disc.iso.partial").exists())


class NativeStoreValidationTests(unittest.TestCase):
    def test_rejects_wrong_revision_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            (store / "manifest.json").write_text(
                '{"schema":"avpe-native-assets-v1","identity":{},"files":[]}'
            )

            with self.assertRaisesRegex(NativeAssetError, "supported disc revision"):
                validate_native_store(store, full=False)

    def test_rejects_manifest_whose_validated_files_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            records = [
                {"path": path, "size": size, "sha256": digest}
                for path, (size, digest) in SUPPORTED_ANCHORS.items()
            ]
            identity = {
                path: {"size": size, "sha256": digest}
                for path, (size, digest) in SUPPORTED_ANCHORS.items()
            }
            (store / "manifest.json").write_text(json.dumps({
                "schema": STORE_SCHEMA,
                "identity": identity,
                "files": records,
            }))

            with self.assertRaisesRegex(NativeAssetError, "wrong size or is missing"):
                validate_native_store(store, full=False)


if __name__ == "__main__":
    unittest.main()
