"""Isolated memory-card working copies for save-boundary observation."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil


PS2_CARD_MAGIC = b"Sony PS2 Memory Card Format "
WORKING_CARD_NAME = "save-boundary-probe.ps2"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class MemoryCardProbe:
    source: Path
    working: Path
    source_sha256: str

    def observe(self) -> dict[str, object]:
        if sha256_file(self.source) != self.source_sha256:
            raise RuntimeError(f"memory-card probe source changed during run: {self.source}")

        changed_bytes = 0
        first_changed_offset: int | None = None
        last_changed_offset: int | None = None
        offset = 0
        with self.source.open("rb") as source, self.working.open("rb") as working:
            while True:
                source_chunk = source.read(1024 * 1024)
                working_chunk = working.read(1024 * 1024)
                if not source_chunk and not working_chunk:
                    break
                if len(source_chunk) != len(working_chunk):
                    raise RuntimeError("memory-card working-copy size changed during run")
                for index, (before, after) in enumerate(zip(source_chunk, working_chunk)):
                    if before == after:
                        continue
                    absolute = offset + index
                    changed_bytes += 1
                    if first_changed_offset is None:
                        first_changed_offset = absolute
                    last_changed_offset = absolute
                offset += len(source_chunk)

        return {
            "source": str(self.source),
            "working_copy": str(self.working),
            "size": offset,
            "source_sha256": self.source_sha256,
            "working_sha256": sha256_file(self.working),
            "changed_bytes": changed_bytes,
            "first_changed_offset": first_changed_offset,
            "last_changed_offset": last_changed_offset,
        }


def prepare_memory_card_probe(source: Path, data_dir: Path) -> MemoryCardProbe:
    source = source.resolve()
    if not source.is_file():
        raise RuntimeError(f"memory-card probe source is not a file: {source}")
    with source.open("rb") as stream:
        if stream.read(len(PS2_CARD_MAGIC)) != PS2_CARD_MAGIC:
            raise RuntimeError(f"memory-card probe source is not a formatted PS2 card: {source}")

    destination_dir = data_dir / "PCSX2" / "memcards"
    destination_dir.mkdir(parents=True, exist_ok=True)
    working = destination_dir / WORKING_CARD_NAME
    if source == working.resolve():
        raise RuntimeError("memory-card probe source cannot be its own working copy")
    pending = working.with_suffix(working.suffix + ".pending")
    shutil.copyfile(source, pending)
    pending.replace(working)
    return MemoryCardProbe(source, working, sha256_file(source))
