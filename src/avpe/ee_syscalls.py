"""Scan an ELF32 MIPS executable for direct EE BIOS syscall use."""

from __future__ import annotations

from dataclasses import dataclass
import struct


ELF_HEADER_SIZE = 52
PROGRAM_HEADER_SIZE = 32
PT_LOAD = 1
PF_X = 1
EM_MIPS = 8
SYSCALL_INSTRUCTION = 0x0000000C
JR_RA_INSTRUCTION = 0x03E00008
NOP_INSTRUCTION = 0


@dataclass(frozen=True)
class ExecutableSegment:
    file_offset: int
    virtual_address: int
    file_size: int
    flags: int


@dataclass(frozen=True)
class SyscallWrapper:
    address: int
    call_number: int


@dataclass(frozen=True)
class SyscallSite:
    address: int
    call_number: int | None
    wrapper_address: int | None


@dataclass(frozen=True)
class EeSyscallInventory:
    executable_segments: tuple[ExecutableSegment, ...]
    wrappers: tuple[SyscallWrapper, ...]
    wrapper_calls: tuple[SyscallSite, ...]
    direct_syscalls: tuple[SyscallSite, ...]


def scan_ee_syscalls(data: bytes) -> EeSyscallInventory:
    """Find embedded syscall wrappers, direct wrapper calls, and direct syscalls."""

    segments = tuple(parse_executable_segments(data))
    words_by_segment = [(_words(data, segment), segment) for segment in segments]
    wrappers_by_address: dict[int, SyscallWrapper] = {}
    wrapper_syscall_addresses: set[int] = set()

    for words, segment in words_by_segment:
        for index in range(len(words) - 3):
            call_number = _wrapper_call_number(words[index])
            if call_number is None \
                    or words[index + 1] != SYSCALL_INSTRUCTION \
                    or words[index + 2] != JR_RA_INSTRUCTION \
                    or words[index + 3] != NOP_INSTRUCTION:
                continue
            address = segment.virtual_address + index * 4
            wrappers_by_address[address] = SyscallWrapper(address, call_number)
            wrapper_syscall_addresses.add(address + 4)

    wrapper_calls: list[SyscallSite] = []
    direct_syscalls: list[SyscallSite] = []
    for words, segment in words_by_segment:
        for index, instruction in enumerate(words):
            address = segment.virtual_address + index * 4
            if instruction == SYSCALL_INSTRUCTION:
                if address in wrapper_syscall_addresses:
                    continue
                direct_syscalls.append(
                    SyscallSite(address, _direct_call_number(words, index), None)
                )
                continue
            if instruction >> 26 != 3:
                continue
            target = _jump_target(address, instruction)
            wrapper = wrappers_by_address.get(target)
            if wrapper is not None:
                wrapper_calls.append(SyscallSite(address, wrapper.call_number, target))

    return EeSyscallInventory(
        segments,
        tuple(sorted(wrappers_by_address.values(), key=lambda item: item.address)),
        tuple(sorted(wrapper_calls, key=lambda item: item.address)),
        tuple(sorted(direct_syscalls, key=lambda item: item.address)),
    )


def parse_executable_segments(data: bytes) -> list[ExecutableSegment]:
    if len(data) < ELF_HEADER_SIZE or data[:4] != b"\x7fELF":
        raise ValueError("input is not an ELF file")
    if data[4] != 1 or data[5] != 1:
        raise ValueError("ELF must be 32-bit little-endian")
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    machine = header[2]
    version = header[3]
    program_offset = header[5]
    program_size = header[9]
    program_count = header[10]
    if machine != EM_MIPS or version != 1:
        raise ValueError("ELF must be a current MIPS executable")
    if program_size < PROGRAM_HEADER_SIZE:
        raise ValueError("ELF program-header entry is too small")
    if program_offset > len(data) or program_count > (len(data) - program_offset) // program_size:
        raise ValueError("ELF program-header table is truncated")

    segments = []
    for index in range(program_count):
        offset = program_offset + index * program_size
        kind, file_offset, virtual_address, _, file_size, _, flags, _ = struct.unpack_from(
            "<IIIIIIII", data, offset
        )
        if kind != PT_LOAD or not flags & PF_X or file_size == 0:
            continue
        if file_offset > len(data) or file_size > len(data) - file_offset:
            raise ValueError("ELF executable segment is truncated")
        if file_size % 4:
            raise ValueError("ELF executable segment is not instruction aligned")
        segments.append(ExecutableSegment(file_offset, virtual_address, file_size, flags))
    return segments


def _words(data: bytes, segment: ExecutableSegment) -> tuple[int, ...]:
    count = segment.file_size // 4
    return struct.unpack_from(f"<{count}I", data, segment.file_offset)


def _wrapper_call_number(instruction: int) -> int | None:
    if instruction & 0xFFFF0000 == 0x24030000:
        immediate = instruction & 0xFFFF
        if immediate & 0x8000:
            immediate -= 0x10000
        return _normalize_call_number(-immediate if immediate < 0 else immediate)
    if instruction & 0xFFFF0000 == 0x34030000:
        return _normalize_call_number(instruction & 0xFFFF)
    return None


def _direct_call_number(words: tuple[int, ...], index: int) -> int | None:
    if index == 0:
        return None
    instruction = words[index - 1]
    return _wrapper_call_number(instruction)


def _normalize_call_number(value: int) -> int | None:
    return value if 0 <= value <= 0xFF else None


def _jump_target(address: int, instruction: int) -> int:
    return ((address + 4) & 0xF0000000) | ((instruction & 0x03FFFFFF) << 2)
