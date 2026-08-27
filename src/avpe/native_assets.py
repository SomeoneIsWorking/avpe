"""Provision a validated PC-native asset store from the user's AVP:E CHD."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile

from avpe.iso9660 import FileEntry, Iso9660Error, IsoImage
from avpe.raw_sector import RawSectorError, strip_image

STORE_SCHEMA = "avpe-native-assets-v1"
SUPPORTED_ANCHORS = {
    "SYSTEM.CNF": (57, "a331d8ad574f49fdd824b155e4abd182924c209dc0c335cbfc662c9639d7098f"),
    "SLUS_201.47": (4_829_548, "54d8e87c674cc1f8411c75ee784e4ee46fe2b4797bbcd81f16f077c74fab9a27"),
    "TBD/TBF.TBF": (76_132_970, "cd7d76fc2d2fd018b72b3da9197387bcc904f85459dd72e1cd514f1f204f9038"),
}


class NativeAssetError(RuntimeError):
    """Provisioning or validation failed without publishing a partial store."""


def provision_native_assets(chd: Path, store_parent: Path) -> Path:
    chd = chd.resolve()
    if not chd.is_file():
        raise NativeAssetError(f"game CHD is not a file: {chd}")
    chdman = shutil.which("chdman")
    if chdman is None:
        raise NativeAssetError("required tool chdman is not on PATH")

    store_parent.mkdir(parents=True, exist_ok=True)
    final = store_parent / STORE_SCHEMA
    if final.exists():
        validate_native_store(final, full=True)
        return final / "files"

    staging = Path(tempfile.mkdtemp(prefix=".provision-", dir=store_parent))
    try:
        cue = staging / "disc.cue"
        raw = staging / "disc.bin"
        iso = staging / "disc.iso"
        result = subprocess.run(
            [chdman, "extractcd", "-i", str(chd), "-o", str(cue), "-ob", str(raw)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            detail = result.stdout.strip().splitlines()
            raise NativeAssetError(
                f"chdman extractcd failed ({result.returncode}): "
                f"{detail[-1] if detail else 'no diagnostic'}"
            )

        conversion = strip_image(raw, iso)
        if conversion.mode1_sectors or conversion.mode2_form2_sectors \
                or conversion.mode2_form1_sectors != conversion.sectors:
            raise NativeAssetError(
                "supported AVP:E image must contain only MODE2 Form1 sectors; "
                f"observed {asdict(conversion)}"
            )

        image = IsoImage(iso)
        entries = image.files()
        validate_supported_image(image, entries)
        files_root = staging / "files"
        manifest_files: list[dict[str, object]] = []
        for entry in entries:
            target = files_root.joinpath(*entry.path.parts)
            image.copy_file(entry, target)
            manifest_files.append({
                "path": str(entry.path),
                "size": entry.size,
                "sha256": _sha256(target),
            })
        manifest = {
            "schema": STORE_SCHEMA,
            "identity": {
                path: {"size": size, "sha256": digest}
                for path, (size, digest) in SUPPORTED_ANCHORS.items()
            },
            "source_chd_sha256": _sha256(chd),
            "conversion": asdict(conversion),
            "files": manifest_files,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        validate_native_store(staging, full=True)
        for intermediate in (cue, raw, iso):
            intermediate.unlink(missing_ok=True)
        staging.rename(final)
        return final / "files"
    except (Iso9660Error, RawSectorError) as error:
        raise NativeAssetError(str(error)) from error
    finally:
        if staging.exists():
            _remove_scoped(staging, store_parent, ".provision-")


def validate_native_store(store: Path, *, full: bool) -> None:
    manifest_path = store / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise NativeAssetError(f"native asset manifest is unreadable: {manifest_path}") from error
    if not isinstance(manifest, dict) or manifest.get("schema") != STORE_SCHEMA:
        raise NativeAssetError(f"native asset manifest has the wrong schema: {manifest_path}")
    expected_identity = {
        path: {"size": size, "sha256": digest}
        for path, (size, digest) in SUPPORTED_ANCHORS.items()
    }
    if manifest.get("identity") != expected_identity:
        raise NativeAssetError("native asset manifest does not identify the supported disc revision")
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise NativeAssetError("native asset manifest has no files")

    indexed: dict[str, tuple[int, str]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str) \
                or not isinstance(record.get("size"), int) \
                or not isinstance(record.get("sha256"), str):
            raise NativeAssetError("native asset manifest contains an invalid file record")
        relative = PurePosixPath(record["path"])
        if relative.is_absolute() or ".." in relative.parts \
                or "\\" in record["path"]:
            raise NativeAssetError(f"native asset manifest contains unsafe path {relative}")
        folded = relative.as_posix().casefold()
        if folded in indexed:
            raise NativeAssetError(f"native asset manifest contains duplicate path {relative}")
        indexed[folded] = (record["size"], record["sha256"])

    checks = indexed.items() if full else (
        (path.casefold(), identity) for path, identity in SUPPORTED_ANCHORS.items()
    )
    for folded, (expected_size, expected_hash) in checks:
        candidates = [record["path"] for record in records
                      if record["path"].casefold() == folded]
        if len(candidates) != 1:
            raise NativeAssetError(f"native asset store is missing manifest entry {folded}")
        path = store / "files" / candidates[0]
        if not path.is_file() or path.stat().st_size != expected_size:
            raise NativeAssetError(f"native asset has wrong size or is missing: {path}")
        if _sha256(path) != expected_hash:
            raise NativeAssetError(f"native asset hash mismatch: {path}")


def validate_supported_image(image: IsoImage, entries: list[FileEntry]) -> None:
    indexed = {str(entry.path).casefold(): entry for entry in entries}
    for path, (expected_size, expected_hash) in SUPPORTED_ANCHORS.items():
        entry = indexed.get(path.casefold())
        if entry is None or entry.size != expected_size:
            raise NativeAssetError(f"disc is not the supported revision: {path} size mismatch")
        if hashlib.sha256(image.read_file(entry)).hexdigest() != expected_hash:
            raise NativeAssetError(f"disc is not the supported revision: {path} hash mismatch")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_scoped(path: Path, parent: Path, required_prefix: str) -> None:
    if path.parent != parent or not path.name.startswith(required_prefix):
        raise NativeAssetError(f"refusing cleanup outside scoped staging: {path}")
    shutil.rmtree(path)
