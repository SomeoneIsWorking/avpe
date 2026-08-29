import struct
import unittest

from avpe.ee_syscalls import scan_ee_syscalls


def _synthetic_elf(words: list[int]) -> bytes:
    program_offset = 52
    code_offset = 0x80
    program = struct.pack(
        "<IIIIIIII", 1, code_offset, 0x1000, 0x1000, len(words) * 4, len(words) * 4, 5, 4
    )
    header = struct.pack(
        "<16sHHIIIIIHHHHHH",
        b"\x7fELF\x01\x01\x01" + b"\0" * 9,
        2,
        8,
        1,
        0x1000,
        program_offset,
        0,
        0,
        52,
        32,
        1,
        0,
        0,
        0,
    )
    return header + program + b"\0" * (code_offset - len(header) - len(program)) + struct.pack(
        f"<{len(words)}I", *words
    )


class EeSyscallTests(unittest.TestCase):
    def test_finds_wrapper_call_and_direct_syscall(self) -> None:
        words = [
            0x2403002A,
            0x0000000C,
            0x03E00008,
            0,
            0x0C000400,
            0,
            0,
            0,
            0x2403FF80,
            0x0000000C,
        ]

        inventory = scan_ee_syscalls(_synthetic_elf(words))

        self.assertEqual(
            [(item.address, item.call_number) for item in inventory.wrappers],
            [(0x1000, 0x2A)],
        )
        self.assertEqual(
            [
                (item.address, item.call_number, item.wrapper_address)
                for item in inventory.wrapper_calls
            ],
            [(0x1010, 0x2A, 0x1000)],
        )
        self.assertEqual(
            [(item.address, item.call_number) for item in inventory.direct_syscalls],
            [(0x1024, 0x80)],
        )

    def test_rejects_non_elf_and_unaligned_executable_segment(self) -> None:
        with self.assertRaisesRegex(ValueError, "not an ELF"):
            scan_ee_syscalls(b"not an elf")

        words = [0x24030001, 0x0000000C, 0x03E00008, 0]
        malformed = bytearray(_synthetic_elf(words))
        struct.pack_into("<I", malformed, 52 + 16, len(words) * 4 - 1)
        with self.assertRaisesRegex(ValueError, "instruction aligned"):
            scan_ee_syscalls(bytes(malformed))
