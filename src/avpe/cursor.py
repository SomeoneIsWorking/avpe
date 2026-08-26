"""Detect AVP:E's rendered cursor in a coherent control-channel BMP snapshot."""

from dataclasses import dataclass
from math import hypot
from struct import unpack_from


@dataclass(frozen=True)
class CursorObservation:
    x: float
    y: float
    pixel_count: int


@dataclass(frozen=True)
class _Component:
    pixels: tuple[tuple[int, int], ...]
    left: int
    top: int
    right: int
    bottom: int

    @property
    def area(self) -> int:
        return len(self.pixels)

    @property
    def width(self) -> int:
        return self.right - self.left + 1

    @property
    def height(self) -> int:
        return self.bottom - self.top + 1

    @property
    def centroid(self) -> tuple[float, float]:
        return (
            sum(point[0] for point in self.pixels) / self.area,
            sum(point[1] for point in self.pixels) / self.area,
        )


def _cursor_color(red: int, green: int, blue: int) -> bool:
    return red > 140 and green > 107 and blue < 184 and red > green > blue


def _decode_mask(bmp: bytes) -> tuple[int, int, set[tuple[int, int]]]:
    if len(bmp) < 54 or bmp[:2] != b"BM":
        raise ValueError("snapshot is not a BMP")
    pixel_offset = unpack_from("<I", bmp, 10)[0]
    dib_size = unpack_from("<I", bmp, 14)[0]
    width = unpack_from("<i", bmp, 18)[0]
    stored_height = unpack_from("<i", bmp, 22)[0]
    planes, bits_per_pixel = unpack_from("<HH", bmp, 26)
    compression = unpack_from("<I", bmp, 30)[0]
    if dib_size < 40 or width <= 0 or stored_height == 0:
        raise ValueError("snapshot has invalid BMP dimensions")
    if planes != 1 or bits_per_pixel != 24 or compression != 0:
        raise ValueError("snapshot must be an uncompressed 24-bit BMP")

    height = abs(stored_height)
    row_stride = (width * 3 + 3) & ~3
    if pixel_offset + row_stride * height > len(bmp):
        raise ValueError("snapshot BMP pixel data is truncated")

    mask: set[tuple[int, int]] = set()
    for stored_row in range(height):
        y = height - stored_row - 1 if stored_height > 0 else stored_row
        row_offset = pixel_offset + stored_row * row_stride
        for x in range(width):
            blue, green, red = bmp[row_offset + x * 3:row_offset + x * 3 + 3]
            if _cursor_color(red, green, blue):
                mask.add((x, y))
    return width, height, mask


def _components(mask: set[tuple[int, int]]) -> list[_Component]:
    remaining = set(mask)
    found: list[_Component] = []
    while remaining:
        seed = remaining.pop()
        stack = [seed]
        pixels = [seed]
        while stack:
            x, y = stack.pop()
            for offset_y in (-1, 0, 1):
                for offset_x in (-1, 0, 1):
                    if offset_x == 0 and offset_y == 0:
                        continue
                    neighbor = (x + offset_x, y + offset_y)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        stack.append(neighbor)
                        pixels.append(neighbor)
        xs = [point[0] for point in pixels]
        ys = [point[1] for point in pixels]
        found.append(_Component(tuple(pixels), min(xs), min(ys), max(xs), max(ys)))
    return found


def detect_cursor(
    bmp: bytes,
    expected_x: float,
    expected_y: float,
    search_radius: float = 40.0,
) -> CursorObservation | None:
    """Return the cursor formed by its two gold arc components near a target."""
    width, height, mask = _decode_mask(bmp)
    if not 0 <= expected_x < width or not 0 <= expected_y < height:
        raise ValueError("expected cursor position is outside the snapshot")

    candidates = [
        component
        for component in _components(mask)
        if 25 <= component.area <= 80
        and 6 <= component.width <= 18
        and 10 <= component.height <= 22
    ]
    matches: list[tuple[float, CursorObservation]] = []
    for index, first in enumerate(candidates):
        first_x, first_y = first.centroid
        for second in candidates[index + 1:]:
            second_x, second_y = second.centroid
            separation = hypot(first_x - second_x, first_y - second_y)
            if not 8.0 <= separation <= 20.0:
                continue
            union_width = max(first.right, second.right) - min(first.left, second.left) + 1
            union_height = max(first.bottom, second.bottom) - min(first.top, second.top) + 1
            if not 15 <= union_width <= 28 or not 15 <= union_height <= 28:
                continue
            pixel_count = first.area + second.area
            center_x = (first_x * first.area + second_x * second.area) / pixel_count
            center_y = (first_y * first.area + second_y * second.area) / pixel_count
            distance = hypot(center_x - expected_x, center_y - expected_y)
            if distance <= search_radius:
                matches.append((distance, CursorObservation(center_x, center_y, pixel_count)))
    if not matches:
        return None
    return min(matches, key=lambda match: match[0])[1]
