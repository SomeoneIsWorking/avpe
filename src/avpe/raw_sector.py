"""Validated streaming conversion of raw CD sectors to 2048-byte ISO blocks."""

from dataclasses import dataclass
from pathlib import Path

SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
RAW_SECTOR_SIZE = 2352
ISO_SECTOR_SIZE = 2048


class RawSectorError(RuntimeError):
    """The source is not a supported raw-sector image."""


@dataclass(frozen=True)
class ConversionReport:
    sectors: int
    mode1_sectors: int
    mode2_form1_sectors: int
    mode2_form2_sectors: int


def strip_image(raw_path: Path, iso_path: Path) -> ConversionReport:
    """Convert without loading the disc into RAM; publish only a complete image."""
    if raw_path.resolve() == iso_path.resolve():
        raise RawSectorError("raw input and ISO output resolve to the same path")
    size = raw_path.stat().st_size
    if size == 0 or size % RAW_SECTOR_SIZE != 0:
        raise RawSectorError(
            f"raw size {size} is not a positive multiple of {RAW_SECTOR_SIZE}"
        )

    partial = iso_path.with_name(f".{iso_path.name}.partial")
    partial.unlink(missing_ok=True)
    counts = {"mode1": 0, "mode2_form1": 0, "mode2_form2": 0}
    try:
        with raw_path.open("rb") as source, partial.open("xb") as output:
            for index in range(size // RAW_SECTOR_SIZE):
                sector = source.read(RAW_SECTOR_SIZE)
                if len(sector) != RAW_SECTOR_SIZE:
                    raise RawSectorError(f"sector {index}: truncated raw sector")
                if sector[:12] != SYNC:
                    raise RawSectorError(
                        f"sector {index}: invalid sync prefix {sector[:12].hex()}"
                    )
                mode = sector[15]
                if mode == 1:
                    counts["mode1"] += 1
                    output.write(sector[16:16 + ISO_SECTOR_SIZE])
                elif mode == 2 and sector[18] & 0x20 == 0:
                    counts["mode2_form1"] += 1
                    output.write(sector[24:24 + ISO_SECTOR_SIZE])
                elif mode == 2:
                    counts["mode2_form2"] += 1
                    output.write(bytes(ISO_SECTOR_SIZE))
                else:
                    raise RawSectorError(f"sector {index}: unsupported mode byte {mode}")
        partial.replace(iso_path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    return ConversionReport(
        sectors=size // RAW_SECTOR_SIZE,
        mode1_sectors=counts["mode1"],
        mode2_form1_sectors=counts["mode2_form1"],
        mode2_form2_sectors=counts["mode2_form2"],
    )
