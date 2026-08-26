"""Tracked dependency inspection and provisioning."""

from dataclasses import dataclass
from pathlib import Path
import subprocess


PCSX2_SUBMODULE = Path("thirdparty/pcsx2")


@dataclass(frozen=True)
class SubmoduleState:
    expected_revision: str | None
    checkout_revision: str | None

    @property
    def is_ready(self) -> bool:
        return (
            self.expected_revision is not None
            and self.checkout_revision == self.expected_revision
        )


def parse_gitlink_revision(index_record: str) -> str | None:
    """Return the object ID from one `git ls-files --stage` gitlink record."""
    fields = index_record.strip().split()
    if len(fields) < 3 or fields[0] != "160000":
        return None
    return fields[1]


def inspect_submodule(root: Path, path: Path = PCSX2_SUBMODULE) -> SubmoduleState:
    index = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "--", path.as_posix()],
        capture_output=True,
        text=True,
        check=False,
    )
    expected = parse_gitlink_revision(index.stdout) if index.returncode == 0 else None

    checkout = root / path
    if not checkout.is_dir():
        return SubmoduleState(expected, None)
    head = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    actual = head.stdout.strip() if head.returncode == 0 else None
    return SubmoduleState(expected, actual)


def provision_submodules(root: Path) -> bool:
    """Synchronize configured URLs and initialize every nested submodule."""
    commands = (
        ["git", "-C", str(root), "submodule", "sync", "--recursive"],
        [
            "git",
            "-C",
            str(root),
            "submodule",
            "update",
            "--init",
            "--recursive",
        ],
    )
    return all(subprocess.run(command, check=False).returncode == 0 for command in commands)
