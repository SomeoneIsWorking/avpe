"""Small strict ISO9660 reader for provisioning user-owned AVP:E assets."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import struct

SECTOR_SIZE = 2048
PVD_SECTOR = 16


class Iso9660Error(RuntimeError):
    """The image violates the subset required by the AVP:E disc."""


@dataclass(frozen=True)
class FileEntry:
    path: PurePosixPath
    extent: int
    size: int


@dataclass(frozen=True)
class _DirectoryEntry:
    name: str
    extent: int
    size: int
    is_directory: bool


class IsoImage:
    def __init__(self, path: Path):
        self.path = path
        self._size = path.stat().st_size
        pvd = self._read_extent(PVD_SECTOR, SECTOR_SIZE)
        if pvd[0] != 1 or pvd[1:6] != b"CD001" or pvd[6] != 1:
            raise Iso9660Error("sector 16 is not an ISO9660 primary volume descriptor")
        logical_size = _both_endian_u16(pvd, 128, "logical block size")
        if logical_size != SECTOR_SIZE:
            raise Iso9660Error(f"logical block size {logical_size} is not {SECTOR_SIZE}")
        self._root = self._parse_record(pvd, 156)
        if not self._root.is_directory:
            raise Iso9660Error("primary volume root record is not a directory")

    def files(self) -> list[FileEntry]:
        files: list[FileEntry] = []
        paths: set[str] = set()
        visited_directories: set[tuple[int, int]] = set()
        self._walk(PurePosixPath(), self._root, files, paths, visited_directories)
        return sorted(files, key=lambda entry: str(entry.path))

    def read_file(self, entry: FileEntry) -> bytes:
        return self._read_extent(entry.extent, entry.size)

    def copy_file(self, entry: FileEntry, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        remaining = entry.size
        offset = entry.extent * SECTOR_SIZE
        with self.path.open("rb") as source, target.open("xb") as output:
            source.seek(offset)
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise Iso9660Error(f"{entry.path}: truncated extent")
                output.write(chunk)
                remaining -= len(chunk)

    def _walk(
        self,
        parent: PurePosixPath,
        directory: _DirectoryEntry,
        files: list[FileEntry],
        paths: set[str],
        visited_directories: set[tuple[int, int]],
    ) -> None:
        identity = (directory.extent, directory.size)
        if identity in visited_directories:
            raise Iso9660Error(f"directory cycle at {parent or '/'}")
        visited_directories.add(identity)
        data = self._read_extent(directory.extent, directory.size)
        offset = 0
        while offset < len(data):
            sector_offset = offset % SECTOR_SIZE
            record_length = data[offset]
            if record_length == 0:
                offset += SECTOR_SIZE - sector_offset
                continue
            if sector_offset + record_length > SECTOR_SIZE:
                raise Iso9660Error(f"directory record crosses a sector at byte {offset}")
            entry = self._parse_record(data, offset)
            offset += record_length
            if entry.name in (".", ".."):
                continue
            path = parent / entry.name
            folded = str(path).casefold()
            if folded in paths:
                raise Iso9660Error(f"duplicate case-insensitive path {path}")
            paths.add(folded)
            if entry.is_directory:
                self._walk(path, entry, files, paths, visited_directories)
            else:
                files.append(FileEntry(path, entry.extent, entry.size))

    def _parse_record(self, data: bytes, offset: int) -> _DirectoryEntry:
        if offset >= len(data):
            raise Iso9660Error("directory record offset is out of range")
        record_length = data[offset]
        if record_length < 34 or offset + record_length > len(data):
            raise Iso9660Error(f"invalid directory record length {record_length}")
        extent = _both_endian_u32(data, offset + 2, "extent")
        size = _both_endian_u32(data, offset + 10, "extent size")
        filename_length = data[offset + 32]
        if 33 + filename_length > record_length:
            raise Iso9660Error("directory filename exceeds its record")
        raw_name = data[offset + 33:offset + 33 + filename_length]
        if raw_name == b"\x00":
            name = "."
        elif raw_name == b"\x01":
            name = ".."
        else:
            try:
                name = raw_name.split(b";", 1)[0].decode("ascii")
            except UnicodeDecodeError as error:
                raise Iso9660Error("directory filename is not ASCII") from error
            if not name or name in (".", "..") or any(char in name for char in "/\\\x00"):
                raise Iso9660Error(f"unsafe ISO filename {name!r}")
        self._validate_extent(extent, size)
        return _DirectoryEntry(name, extent, size, bool(data[offset + 25] & 2))

    def _read_extent(self, extent: int, size: int) -> bytes:
        self._validate_extent(extent, size)
        with self.path.open("rb") as image:
            image.seek(extent * SECTOR_SIZE)
            data = image.read(size)
        if len(data) != size:
            raise Iso9660Error(f"extent {extent}+{size} is truncated")
        return data

    def _validate_extent(self, extent: int, size: int) -> None:
        end = extent * SECTOR_SIZE + size
        if extent < 0 or size < 0 or end > self._size:
            raise Iso9660Error(f"extent {extent}+{size} exceeds image size {self._size}")


def _both_endian_u16(data: bytes, offset: int, label: str) -> int:
    little = struct.unpack_from("<H", data, offset)[0]
    big = struct.unpack_from(">H", data, offset + 2)[0]
    if little != big:
        raise Iso9660Error(f"{label} endian copies disagree: {little} != {big}")
    return little


def _both_endian_u32(data: bytes, offset: int, label: str) -> int:
    little = struct.unpack_from("<I", data, offset)[0]
    big = struct.unpack_from(">I", data, offset + 4)[0]
    if little != big:
        raise Iso9660Error(f"{label} endian copies disagree: {little} != {big}")
    return little
