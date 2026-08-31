"""Read static IOP import tables from PlayStation 2 IRX ELF modules."""

from __future__ import annotations

from dataclasses import dataclass
import string
import struct

from avpe.ee_syscalls import ExecutableSegment, parse_executable_segments


ELF_HEADER_SIZE = 52
SECTION_HEADER_SIZE = 40
SYMBOL_SIZE = 16
SHT_SYMTAB = 2
IMPORT_MAGIC = 0x41E00000
IMPORT_HEADER_SIZE = 20
IMPORT_ENTRY_SIZE = 8
JR_RA_INSTRUCTION = 0x03E00008
ORDINAL_INSTRUCTION_MASK = 0xFFFF0000
ORDINAL_INSTRUCTION = 0x24000000
MAX_IMPORT_TABLES = 128
MAX_IMPORT_ENTRIES = 4096


@dataclass(frozen=True)
class IopImport:
    ordinal: int
    address: int
    symbol: str | None


@dataclass(frozen=True)
class IopLibrary:
    name: str
    version: int
    address: int
    imports: tuple[IopImport, ...]


@dataclass(frozen=True)
class IopModule:
    name: str
    version: int
    entry_address: int
    libraries: tuple[IopLibrary, ...]


def scan_iop_module(data: bytes) -> IopModule:
    """Extract the module header and all static import tables from one IRX."""

    segments = tuple(parse_executable_segments(data))
    module_name, module_version, entry_address = _parse_module_header(data)
    symbols = _parse_import_symbols(data)
    libraries = _parse_import_tables(data, segments, symbols)
    return IopModule(module_name, module_version, entry_address, tuple(libraries))


def _parse_module_header(data: bytes) -> tuple[str, int, int]:
    sections = _parse_sections(data)
    module = next((section for section in sections if section.name == ".iopmod"), None)
    if module is None:
        raise ValueError("IRX does not contain an .iopmod section")
    raw = _slice(data, module.file_offset, module.size, ".iopmod")
    if len(raw) < 0x1A:
        raise ValueError("IRX .iopmod section is truncated")
    entry_address = struct.unpack_from("<I", raw, 4)[0]
    version = struct.unpack_from("<H", raw, 0x18)[0]
    name = _nul_string(raw[0x1A:], ".iopmod module name")
    return name, version, entry_address


def _parse_import_tables(
    data: bytes,
    segments: tuple[ExecutableSegment, ...],
    symbols: dict[int, str],
) -> list[IopLibrary]:
    tables: list[IopLibrary] = []
    seen_addresses: set[int] = set()
    for segment in segments:
        words = _segment_words(data, segment)
        for index, word in enumerate(words):
            if word != IMPORT_MAGIC:
                continue
            address = segment.virtual_address + index * 4
            if address in seen_addresses:
                continue
            seen_addresses.add(address)
            tables.append(_parse_import_table(words, segment, index, symbols))
            if len(tables) > MAX_IMPORT_TABLES:
                raise ValueError("IRX contains too many import tables")
    if not tables:
        raise ValueError("IRX contains no import tables")
    return sorted(tables, key=lambda table: table.address)


def _parse_import_table(
    words: tuple[int, ...],
    segment: ExecutableSegment,
    start: int,
    symbols: dict[int, str],
) -> IopLibrary:
    if start + IMPORT_HEADER_SIZE // 4 > len(words):
        raise ValueError("IRX import table header is truncated")
    version = words[start + 2]
    name_bytes = struct.pack("<2I", words[start + 3], words[start + 4])
    name = _fixed_ascii(name_bytes, "IRX import library name")
    entry_start = start + IMPORT_HEADER_SIZE // 4
    imports: list[IopImport] = []
    for ordinal in range(MAX_IMPORT_ENTRIES):
        entry = entry_start + ordinal * (IMPORT_ENTRY_SIZE // 4)
        if entry + 2 > len(words):
            raise ValueError(f"IRX import table {name!r} is truncated")
        first, second = words[entry : entry + 2]
        if first == 0 and second == 0:
            break
        if (
            first != JR_RA_INSTRUCTION
            or second & ORDINAL_INSTRUCTION_MASK != ORDINAL_INSTRUCTION
        ):
            raise ValueError(f"IRX import table {name!r} contains an invalid stub")
        address = segment.virtual_address + entry * 4
        imports.append(IopImport(second & 0xFFFF, address, symbols.get(address)))
    else:
        raise ValueError(f"IRX import table {name!r} exceeds entry bound")
    if not imports:
        raise ValueError(f"IRX import table {name!r} has no entries")
    return IopLibrary(
        name, version, segment.virtual_address + start * 4, tuple(imports)
    )


def _parse_import_symbols(data: bytes) -> dict[int, str]:
    sections = _parse_sections(data)
    text_index = next(
        (index for index, section in enumerate(sections) if section.name == ".text"),
        None,
    )
    if text_index is None:
        return {}
    symbols: dict[int, str] = {}
    for section in sections:
        if section.kind != SHT_SYMTAB or section.entry_size < SYMBOL_SIZE:
            continue
        if section.link >= len(sections):
            raise ValueError("IRX symbol table has an invalid string-table link")
        strings = _slice(
            data,
            sections[section.link].file_offset,
            sections[section.link].size,
            ".strtab",
        )
        raw = _slice(data, section.file_offset, section.size, ".symtab")
        for offset in range(0, len(raw), section.entry_size):
            if offset + SYMBOL_SIZE > len(raw):
                raise ValueError("IRX symbol table is truncated")
            name_offset, value, size, info, _, section_index = struct.unpack_from(
                "<IIIBBH", raw, offset
            )
            if section_index != text_index or size != 0 or info >> 4 == 0:
                continue
            name = _string_at(strings, name_offset, ".strtab symbol")
            if name and not name.startswith("_"):
                symbols.setdefault(value, name)
    return symbols


@dataclass(frozen=True)
class _Section:
    name: str
    kind: int
    file_offset: int
    size: int
    link: int
    entry_size: int


def _parse_sections(data: bytes) -> list[_Section]:
    if len(data) < ELF_HEADER_SIZE or data[:4] != b"\x7fELF":
        raise ValueError("input is not an ELF file")
    if data[4] != 1 or data[5] != 1:
        raise ValueError("ELF must be 32-bit little-endian")
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    section_offset, entry_size, count, strings_index = (
        header[6],
        header[11],
        header[12],
        header[13],
    )
    if entry_size < SECTION_HEADER_SIZE:
        raise ValueError("ELF section-header entry is too small")
    if section_offset > len(data) or count > (len(data) - section_offset) // entry_size:
        raise ValueError("ELF section-header table is truncated")
    if strings_index >= count:
        raise ValueError("ELF section-name string-table index is invalid")
    raw_sections = [
        struct.unpack_from("<IIIIIIIIII", data, section_offset + index * entry_size)
        for index in range(count)
    ]
    names_raw = raw_sections[strings_index]
    names = _slice(data, names_raw[4], names_raw[5], "section-name string table")
    return [
        _Section(
            _string_at(names, raw[0], "section name"),
            raw[1],
            raw[4],
            raw[5],
            raw[6],
            raw[9],
        )
        for raw in raw_sections
    ]


def _segment_words(data: bytes, segment: ExecutableSegment) -> tuple[int, ...]:
    raw = _slice(data, segment.file_offset, segment.file_size, "executable segment")
    if len(raw) % 4:
        raise ValueError("IRX executable segment is not word aligned")
    return struct.unpack(f"<{len(raw) // 4}I", raw)


def _slice(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset > len(data) or size > len(data) - offset:
        raise ValueError(f"IRX {label} is truncated")
    return data[offset : offset + size]


def _string_at(data: bytes, offset: int, label: str) -> str:
    if offset >= len(data):
        raise ValueError(f"IRX {label} offset is out of bounds")
    end = data.find(b"\0", offset)
    if end < 0:
        raise ValueError(f"IRX {label} is not NUL-terminated")
    return _decode_ascii(data[offset:end], label, require_nonempty=False)


def _nul_string(data: bytes, label: str) -> str:
    end = data.find(b"\0")
    if end < 0:
        raise ValueError(f"IRX {label} is not NUL-terminated")
    return _decode_ascii(data[:end], label, require_nonempty=True)


def _fixed_ascii(data: bytes, label: str) -> str:
    return _decode_ascii(data.split(b"\0", 1)[0], label, require_nonempty=True)


def _decode_ascii(data: bytes, label: str, require_nonempty: bool) -> str:
    value = data.decode("ascii", errors="strict")
    if (require_nonempty and not value) or any(
        character not in string.printable or character in "\r\n\t"
        for character in value
    ):
        raise ValueError(f"IRX {label} is not printable ASCII")
    return value
