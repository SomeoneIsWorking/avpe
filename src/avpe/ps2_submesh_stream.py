"""Decode an AVP:E PS2SubMesh vertex stream as PS2ProcessVerts hands it to VU1.

A stream starts with four halfwords (vertex count, a repeat of it, the byte offset of
its DMA packet from stream+4, and zero), followed by the float scale vector that the
quantised positions multiply against. The packet is a DMAtag/VIF qword ending in one
UNPACK V4-16, then two V4-16 elements per vertex: (x, y, z, u) and (nx, ny, nz, v).
"""

import struct
from dataclasses import dataclass

STREAM_HEADER_SIZE = 0x14
# VIF UNPACK with vn=3, vl=1 (V4-16); bits 5 and 4 of the command are the mask and
# reserved bits, so compare after clearing the mask bit.
_VIF_UNPACK_V4_16 = 0x6D
_VIF_UNPACK_MASK_BIT = 0x10
_ELEMENTS_PER_VERTEX = 2
_PACKET_HEADER_SIZE = 0x10
# ITOF15, the VU's 1.15 fixed-point conversion.
_ITOF15 = 1.0 / 32768.0


@dataclass(frozen=True)
class SubmeshVertex:
    position: tuple[float, float, float]
    u: int
    v: int


@dataclass(frozen=True)
class SubmeshStream:
    vertex_count: int
    scale: tuple[float, float, float]
    packet_offset: int
    vertices: tuple[SubmeshVertex, ...]

    def y_extent(self) -> tuple[float, float]:
        ys = [vertex.position[1] for vertex in self.vertices]
        return min(ys), max(ys)


def packet_size(header: bytes) -> int:
    """Bytes from the stream start through the end of the vertex payload."""
    count, _, packet_offset, _ = struct.unpack_from("<4H", header, 0)
    return 4 + packet_offset + _PACKET_HEADER_SIZE + count * _ELEMENTS_PER_VERTEX * 8


def decode_submesh_stream(raw: bytes) -> SubmeshStream:
    count, repeat, packet_offset, _ = struct.unpack_from("<4H", raw, 0)
    if count != repeat:
        raise ValueError(f"stream vertex counts disagree: {count} != {repeat}")
    scale = struct.unpack_from("<3f", raw, 8)
    packet = 4 + packet_offset
    unpack = struct.unpack_from("<I", raw, packet + 12)[0]
    command = (unpack >> 24) & ~_VIF_UNPACK_MASK_BIT & 0xFF
    elements = (unpack >> 16) & 0xFF
    if command != _VIF_UNPACK_V4_16 & ~_VIF_UNPACK_MASK_BIT:
        raise ValueError(f"stream packet does not end in UNPACK V4-16: 0x{unpack:08X}")
    if elements != count * _ELEMENTS_PER_VERTEX:
        raise ValueError(f"UNPACK carries {elements} elements for {count} vertices")
    vertices = []
    base = packet + _PACKET_HEADER_SIZE
    for index in range(count):
        x, y, z, u = struct.unpack_from("<4h", raw, base + index * 16)
        _, _, _, v = struct.unpack_from("<4h", raw, base + index * 16 + 8)
        position = tuple(q * _ITOF15 * s for q, s in zip((x, y, z), scale))
        vertices.append(SubmeshVertex(position=position, u=u, v=v))
    return SubmeshStream(
        vertex_count=count,
        scale=scale,
        packet_offset=packet_offset,
        vertices=tuple(vertices),
    )
