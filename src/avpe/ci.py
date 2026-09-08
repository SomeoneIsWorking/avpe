"""Hosted, asset-free verification of AVPE's buildable product boundary."""

import os
from pathlib import Path
import platform
import subprocess
import sys
from collections.abc import Callable

from avpe.build import prepare_product_package


class CiError(RuntimeError):
    """The current host is not an AVPE CI target."""


SUPPORTED_HOSTS = frozenset({"Linux", "Darwin"})
_FORBIDDEN_ASSET_SUFFIXES = frozenset(
    {".bin", ".chd", ".elf", ".irx", ".iso", ".p2s", ".ps2", ".rom", ".sav"}
)


def assert_asset_free_package(package_root: Path) -> None:
    """Require the staged package to contain only redistributable AVPE files."""
    binary = package_root / "bin" / "avpe"
    if not binary.is_file():
        raise CiError(f"asset-free package is missing {binary}")
    for path in package_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(package_root)
        if relative == Path("bin/avpe"):
            continue
        if relative.parts[:3] == ("share", "avpe", "resources"):
            pass
        else:
            raise CiError(f"package contains an unowned file: {relative}")
        if path.suffix.lower() in _FORBIDDEN_ASSET_SUFFIXES:
            raise CiError(f"package contains a user-supplied asset: {relative}")


def verify_host(
    root: Path,
    environment: dict[str, str] | None = None,
    system: str | None = None,
    run: Callable[..., subprocess.CompletedProcess[object]] = subprocess.run,
) -> Path:
    """Build, inspect, and verify AVPE's asset-free package on one host."""
    host = system or platform.system()
    if host not in SUPPORTED_HOSTS:
        raise CiError(f"AVPE hosted CI is unsupported on {host}")

    env = dict(os.environ if environment is None else environment)
    package_root = prepare_product_package(root, env)
    assert_asset_free_package(package_root)
    run([sys.executable, "tools/verify.py"], cwd=root, env=env, check=True)
    return package_root / "bin" / "avpe"
