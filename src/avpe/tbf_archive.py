"""Bounded structural search of decoded AVP:E TBF payloads, not reachability proof."""

from collections import Counter
from dataclasses import dataclass
import struct
from typing import TypedDict

from avpe.save_format import decode_bwj


@dataclass(frozen=True)
class Limits:
    archive_bytes: int = 128 * 1024 * 1024
    chunk_bytes: int = 128 * 1024 * 1024
    decoded_bytes: int = 512 * 1024 * 1024
    chunks: int = 10_000
    depth: int = 8
    locations: int = 20


COMPRESSED = {b"DATX", b"TEMX", b"PLAX"}
LEAVES = COMPRESSED | {
    b"INDX", b"TYPE", b"PUBL", b"OFFS", b"DATA", b"TEMP", b"PLAT",
    b"EXTA", b"EXTN", b"HNDL",
}


class Location(TypedDict):
    chunk_offset: int
    tag: str
    payload_offset: int
    containers: list[int]


class PatternResult(TypedDict):
    pattern_hex: str
    matches: int
    locations: list[Location]


class SearchResult(TypedDict):
    schema: str
    archive_bytes: int
    chunks: int
    chunk_counts: dict[str, int]
    compressed_chunks: int
    decoded_payload_bytes: int
    patterns: list[PatternResult]
    scope: str


def search_archive(data: bytes, patterns: tuple[bytes, ...], limits: Limits = Limits()) -> SearchResult:
    """Validate all chunks and search every decoded leaf; never skip malformed input.

    CTbdFile::ReadChunk (0x00173CB0) reads a u32 expanded size before BWJ
    data. LoadCore (0x00173FC0) pairs DATA/DATX, TEMP/TEMX and PLAT/PLAX.
    Matches are byte occurrences, not interpreted object fields or live actions.
    """
    if any(value <= 0 for value in vars(limits).values()):
        raise ValueError("archive limits must be positive")
    if not patterns or any(not pattern for pattern in patterns):
        raise ValueError("at least one nonempty search pattern is required")
    if len(set(patterns)) != len(patterns):
        raise ValueError("search patterns must be unique")
    if len(data) > limits.archive_bytes:
        raise ValueError("archive exceeds input byte budget")
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"TBFF":
        raise ValueError("expected a RIFF/TBFF archive")
    if struct.unpack_from("<I", data, 4)[0] != len(data) - 8:
        raise ValueError("RIFF size does not cover the exact input")
    counts: Counter[str] = Counter()
    results: list[PatternResult] = [
        {"pattern_hex": pattern.hex(), "matches": 0, "locations": []} for pattern in patterns]
    decoded_bytes = 0
    chunk_count = 0

    def walk(begin: int, end: int, parents: tuple[int, ...]) -> None:
        nonlocal decoded_bytes, chunk_count
        if len(parents) >= limits.depth:
            raise ValueError("archive nesting exceeds depth budget")
        position = begin
        while position < end:
            if end - position < 8:
                raise ValueError(f"truncated chunk header at 0x{position:X}")
            tag, size = struct.unpack_from("<4sI", data, position)
            stop = position + 8 + size
            padded_stop = stop + (size & 1)
            if padded_stop > end:
                raise ValueError(f"chunk at 0x{position:X} exceeds its parent")
            chunk_count += 1
            if chunk_count > limits.chunks:
                raise ValueError("archive exceeds chunk count budget")
            counts[tag.decode("ascii", errors="backslashreplace")] += 1
            if tag in (b"RIFF", b"LIST"):
                if size < 4 or data[position + 8:position + 12] not in (
                    b"TBFF", b"TBD2", b"PS2 ",
                ):
                    raise ValueError(f"unsupported container at 0x{position:X}")
                walk(position + 12, stop, parents + (position,))
            else:
                if tag not in LEAVES:
                    raise ValueError(f"unsupported chunk {tag!r} at 0x{position:X}")
                payload = data[position + 8:stop]
                if tag in COMPRESSED:
                    if len(payload) < 8:
                        raise ValueError(f"truncated compressed chunk at 0x{position:X}")
                    expanded = struct.unpack_from("<I", payload)[0]
                else:
                    expanded = len(payload)
                if expanded > limits.chunk_bytes or decoded_bytes + expanded > limits.decoded_bytes:
                    raise ValueError(f"decoded byte budget exceeded at 0x{position:X}")
                if tag in COMPRESSED:
                    decoded = decode_bwj(payload[4:], expanded)
                    if len(decoded.data) != expanded or decoded.consumed_bytes != len(payload) - 4:
                        raise ValueError(f"compressed framing mismatch at 0x{position:X}")
                    payload = decoded.data
                decoded_bytes += len(payload)
                for pattern, result in zip(patterns, results, strict=True):
                    offset = 0
                    while (offset := payload.find(pattern, offset)) >= 0:
                        result["matches"] += 1
                        if len(result["locations"]) < limits.locations:
                            result["locations"].append({
                                "chunk_offset": position, "tag": tag.decode("ascii"),
                                "payload_offset": offset, "containers": list(parents),
                            })
                        offset += 1
            position = padded_stop

    walk(0, len(data), ())
    if chunk_count < 2 or decoded_bytes == 0:
        raise ValueError("archive contains no payload corpus to search")
    return {
        "schema": "avpe-tbf-search-v1", "archive_bytes": len(data),
        "chunks": chunk_count, "chunk_counts": dict(sorted(counts.items())),
        "compressed_chunks": sum(counts[tag.decode()] for tag in COMPRESSED),
        "decoded_payload_bytes": decoded_bytes, "patterns": results,
        "scope": "decoded payload byte occurrences; not object semantics or runtime reachability",
    }
