"""Isolated memory-card working copies for save-boundary observation."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import time

from avpe.control_http import request_bytes


PS2_CARD_MAGIC = b"Sony PS2 Memory Card Format "
WORKING_CARD_NAME = "save-boundary-probe.ps2"
MEMORY_CARD_STATE_SCHEMA = "avpe-memory-card-state-v1"


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


def memory_card_state(port: int) -> tuple[int, dict[str, object] | None, str]:
    status, body = request_bytes(port, "GET", "/memory-card/state")
    detail = body.decode(errors="replace").strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return status, None, detail
    if not isinstance(parsed, dict) or not _valid_memory_card_state(parsed):
        return status, None, detail
    return status, parsed, detail


def await_memory_card_ready(port: int, deadline: float) -> dict[str, object]:
    """Wait for PCSX2's savestate-load card ejection to complete."""
    observations = 0
    saw_ejected = False
    saw_busy = False
    last_state: dict[str, object] | None = None
    while time.monotonic() < deadline:
        status, state, detail = memory_card_state(port)
        if status != 200 or state is None:
            raise RuntimeError(
                f"memory-card readiness returned HTTP {status}: {detail}"
            )
        observations += 1
        last_state = state
        ticks = int(state["auto_eject_ticks"])
        saw_ejected = saw_ejected or ticks > 0
        saw_busy = saw_busy or state["busy"] is True
        if state["ready"] is True:
            return {
                "observations": observations,
                "saw_auto_eject": saw_ejected,
                "saw_busy": saw_busy,
                "state": state,
            }
        time.sleep(0.01)
    raise RuntimeError(
        "memory card did not become ready after ejection or active writes: "
        f"observations={observations}, last_state={last_state}"
    )


def _valid_memory_card_state(state: dict[str, object]) -> bool:
    ticks = state.get("auto_eject_ticks")
    return state.get("schema") == MEMORY_CARD_STATE_SCHEMA \
        and state.get("slot") == 0 \
        and isinstance(state.get("present"), bool) \
        and isinstance(state.get("busy"), bool) \
        and isinstance(ticks, int) and not isinstance(ticks, bool) and ticks >= 0 \
        and isinstance(state.get("ready"), bool) \
        and state["ready"] is (state["present"] and not state["busy"] and ticks == 0)
