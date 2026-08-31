import struct
import unittest

from avpe.iop_imports import scan_iop_module


def _synthetic_irx(import_words: list[int]) -> bytes:
    code_offset = 0x80
    code = struct.pack(f"<{len(import_words)}I", *import_words)
    section_names = b"\0.text\0.iopmod\0.shstrtab\0"
    section_offset = code_offset + len(code)
    section_offset += (-section_offset) % 4
    shstr_offset = section_offset + 4 * 40
    iopmod_offset = shstr_offset + len(section_names)
    iopmod = (
        struct.pack("<6I", 0, 0x40, 0, 0, 0, 0)
        + struct.pack("<H", 0x0102)
        + b"testmod\0"
    )
    section_headers = [
        struct.pack("<10I", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        struct.pack("<10I", 1, 1, 6, 0, code_offset, len(code), 0, 0, 4, 0),
        struct.pack("<10I", 7, 1, 3, 0, iopmod_offset, len(iopmod), 0, 0, 4, 0),
        struct.pack("<10I", 15, 3, 0, 0, shstr_offset, len(section_names), 0, 0, 1, 0),
    ]
    header = struct.pack(
        "<16sHHIIIIIHHHHHH",
        b"\x7fELF\x01\x01\x01" + b"\0" * 9,
        8,
        8,
        1,
        0x40,
        52,
        section_offset,
        0,
        52,
        32,
        1,
        40,
        len(section_headers),
        3,
    )
    program = struct.pack("<IIIIIIII", 1, code_offset, 0, 0, len(code), len(code), 5, 4)
    padding = b"\0" * (code_offset - len(header) - len(program))
    between = b"\0" * (section_offset - code_offset - len(code))
    return (
        header
        + program
        + padding
        + code
        + between
        + b"\0" * (shstr_offset - section_offset - 160)
        + b"".join(section_headers)
        + section_names
        + iopmod
    )


class IopImportTests(unittest.TestCase):
    def test_reads_library_ordinals_and_module_header(self) -> None:
        words = [
            0x41E00000,
            0,
            0x0101,
            0x6574796D,
            0x00000000,
            0x03E00008,
            0x24000004,
            0x03E00008,
            0x24000005,
            0,
            0,
        ]
        module = scan_iop_module(_synthetic_irx(words))
        self.assertEqual(
            (module.name, module.version, module.entry_address),
            ("testmod", 0x0102, 0x40),
        )
        self.assertEqual(module.libraries[0].name, "myte")
        self.assertEqual([item.ordinal for item in module.libraries[0].imports], [4, 5])

    def test_rejects_truncated_import_table(self) -> None:
        words = [0x41E00000, 0, 0x0101, 0x6D797465, 0]
        with self.assertRaisesRegex(ValueError, "import table.*truncated"):
            scan_iop_module(_synthetic_irx(words))
