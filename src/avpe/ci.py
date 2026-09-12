"""Hosted, asset-free verification of AVPE's buildable product boundary."""

import os
from pathlib import Path
import platform
import plistlib
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


def assert_asset_free_package(package_root: Path, system: str | None = None) -> None:
    """Require the staged package to contain only redistributable AVPE files."""
    host = system or platform.system()
    binary = (
        package_root / "avpe.app" / "Contents" / "MacOS" / "avpe"
        if host == "Darwin"
        else package_root / "bin" / "avpe"
    )
    if not binary.is_file():
        raise CiError(f"asset-free package is missing {binary}")
    resources = (
        package_root / "avpe.app" / "Contents" / "Resources"
        if host == "Darwin"
        else package_root / "bin" / "resources"
    )
    for path in package_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(package_root)
        if relative == binary.relative_to(package_root):
            continue
        if host == "Darwin" and relative.parts[:1] == ("avpe.app",):
            pass
        elif relative.parts[:2] == ("bin", "resources"):
            pass
        elif host == "Linux" and relative.parts[:1] == ("lib",):
            pass
        elif host == "Linux" and relative.parts[:1] == ("plugins",):
            pass
        elif host == "Linux" and relative == Path("bin/qt.conf"):
            pass
        else:
            raise CiError(f"package contains an unowned file: {relative}")
        if path.suffix.lower() in _FORBIDDEN_ASSET_SUFFIXES:
            raise CiError(f"package contains a user-supplied asset: {relative}")
    if not (resources / "GameIndex.yaml").is_file():
        raise CiError(f"asset-free package is missing core resources at {resources}")
    if host == "Linux":
        for relative in (
            "bin/qt.conf",
            "plugins/platforms/libqoffscreen.so",
            "plugins/platforms/libqxcb.so",
            "plugins/platforms/libqwayland.so",
        ):
            if not (package_root / relative).is_file():
                raise CiError(f"asset-free package is missing {relative}")


def _verify_macos_bundle(
    root: Path,
    package_root: Path,
    run: Callable[..., subprocess.CompletedProcess[object]],
) -> None:
    """Sign nested code first, then require the app's JIT entitlements."""
    architecture = platform.machine()
    if architecture not in {"arm64", "x86_64"}:
        raise CiError(f"unsupported macOS package architecture: {architecture}")
    bundle = package_root / "avpe.app"
    contents = bundle / "Contents"
    executable = contents / "MacOS" / "avpe"
    entitlements_path = root / "thirdparty/pcsx2/pcsx2/Resources/PCSX2.entitlements"
    with entitlements_path.open("rb") as stream:
        required_entitlements = plistlib.load(stream)
    nested_code: list[Path] = []
    for directory in (contents / "Frameworks", contents / "PlugIns"):
        if not directory.is_dir():
            continue
        bundles = sorted(
            path for path in directory.rglob("*")
            if path.is_dir() and path.suffix in {".framework", ".bundle", ".plugin"}
        )
        if bundles:
            raise CiError(f"macOS signing needs an owner for nested bundle {bundles[0]}")
        nested_code.extend(
            path for path in directory.rglob("*")
            if path.is_file() and not path.is_symlink()
            and path.suffix in {".dylib", ".so"}
        )
    for path in (executable, *sorted(nested_code)):
        run(["lipo", str(path), "-verify_arch", architecture], check=True)
    for path in sorted(nested_code):
        run(["codesign", "--force", "--sign", "-", "--timestamp=none", str(path)], check=True)
    run(
        ["codesign", "--force", "--sign", "-", "--timestamp=none",
         "--entitlements", str(entitlements_path), str(bundle)],
        check=True,
    )
    run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
    embedded = run(
        ["codesign", "--display", "--entitlements", "-", "--xml", str(bundle)],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    try:
        actual_entitlements = plistlib.loads(embedded)
    except (TypeError, ValueError) as error:
        raise CiError(f"macOS app has unreadable embedded entitlements: {bundle}") from error
    if actual_entitlements != required_entitlements:
        raise CiError(f"macOS app does not embed its required JIT entitlements: {bundle}")


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
    assert_asset_free_package(package_root, host)
    if host == "Darwin":
        _verify_macos_bundle(root, package_root, run)
    binary = (
        package_root / "avpe.app" / "Contents" / "MacOS" / "avpe"
        if host == "Darwin"
        else package_root / "bin" / "avpe"
    )
    run(
        [sys.executable, "tools/verify.py"],
        cwd=root,
        env={**env, "AVPE_TEST_PRODUCT": str(binary)},
        check=True,
    )
    return binary
