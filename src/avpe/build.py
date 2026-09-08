"""Prepare the standalone AVPE product from the tracked source tree."""

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from avpe.dependencies import inspect_submodule, provision_submodules
from avpe.dependency_prefix import (
    DependencyPrefixError,
    dependency_prefix_complete,
    provision_dependency_prefix,
)


@dataclass(frozen=True)
class BuildPaths:
    root: Path

    @property
    def source_dir(self) -> Path:
        return self.root / "thirdparty" / "pcsx2"

    @property
    def build_dir(self) -> Path:
        return self.root / "build"

    @property
    def dependency_prefix(self) -> Path:
        return self.build_dir / "deps"

    @property
    def product_binary(self) -> Path:
        return self.build_dir / "bin" / "avpe"

    @property
    def control_test_binary(self) -> Path:
        return self.build_dir / "bin" / "pcsx2-qt"

    @property
    def package_install_dir(self) -> Path:
        return self.build_dir / "avpe-install"

    @property
    def package_dir(self) -> Path:
        return self.build_dir / "avpe-package"


class BuildError(RuntimeError):
    """A preparation prerequisite or build command failed."""


def _linux_package_manager() -> str:
    try:
        values = {}
        for line in Path("/etc/os-release").read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value.strip('"')
    except OSError:
        return "apt"
    distro_id = values.get("ID", "").lower()
    if distro_id in {"fedora", "rhel", "rocky", "almalinux", "centos"}:
        return "dnf"
    return "apt"


def install_hint(missing: tuple[str, ...], system: str, package_manager: str = "") -> str:
    """Return the exact user-run installation instruction for build tools."""
    if system == "Darwin":
        commands = []
        brew_packages = [name for name in missing if name in {"cmake", "ninja"}]
        if brew_packages:
            commands.append("brew install " + " ".join(brew_packages))
        if "c++" in missing:
            commands.append("xcode-select --install")
        return " && ".join(commands)
    if system == "Linux":
        manager = package_manager or _linux_package_manager()
        package_names = {
            "cmake": "cmake",
            "ninja": "ninja-build",
            "c++": "gcc-c++" if manager == "dnf" else "g++",
        }
        packages = " ".join(package_names[name] for name in missing)
        return f"sudo {manager} install {packages}"
    if system == "Windows":
        return (
            "Visual Studio Installer: select the 'Desktop development with C++' "
            "workload and its CMake tools; then run: "
            "winget install --id Ninja-build.Ninja --exact"
        )
    return "install the missing build tools for the documented platform"


def _missing_build_tools(environment: dict[str, str]) -> tuple[str, ...]:
    missing = [name for name in ("cmake", "ninja") if shutil.which(name) is None]
    compiler = environment.get("CXX") or "c++"
    if shutil.which(compiler) is None:
        missing.append("c++")
    return tuple(missing)


def _require_build_tools(environment: dict[str, str]) -> None:
    missing = _missing_build_tools(environment)
    if missing:
        names = ", ".join(missing)
        system = platform.system()
        package_manager = _linux_package_manager() if system == "Linux" else ""
        hint = install_hint(missing, system, package_manager)
        raise BuildError(f"missing build tool(s): {names} — run: {hint}")


def _run(command: list[str], root: Path, environment: dict[str, str]) -> None:
    try:
        subprocess.run(command, cwd=root, env=environment, check=True)
    except OSError as error:
        raise BuildError(f"could not execute {' '.join(command)}: {error}") from error
    except subprocess.CalledProcessError as error:
        raise BuildError(f"command failed with exit status {error.returncode}: {' '.join(command)}") from error


def _ensure_submodule(root: Path) -> None:
    state = inspect_submodule(root)
    if state.is_ready:
        return
    if not provision_submodules(root):
        raise BuildError("PCSX2 submodule provisioning failed — run ./run.sh provision for details")
    state = inspect_submodule(root)
    if not state.is_ready:
        raise BuildError("PCSX2 checkout does not match the tracked gitlink after provisioning")


def _configure_command(
    paths: BuildPaths,
    *,
    package_mode: bool = False,
    install_prefix: Path | None = None,
) -> list[str]:
    command = [
        "cmake",
        "-S",
        str(paths.source_dir),
        "-B",
        str(paths.build_dir),
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_PREFIX_PATH={paths.dependency_prefix}",
        "-DENABLE_QT_UI=ON",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        f"-DPython3_EXECUTABLE={sys.executable}",
    ]
    if package_mode:
        command.append("-DPACKAGE_MODE=ON")
    if install_prefix is not None:
        command.append(f"-DCMAKE_INSTALL_PREFIX={install_prefix}")
    return command


def _build_target(
    paths: BuildPaths,
    root: Path,
    environment: dict[str, str],
    target: str,
    *,
    force_configure: bool = False,
    package_mode: bool = False,
    install_prefix: Path | None = None,
) -> None:
    if force_configure or not (paths.build_dir / "build.ninja").is_file():
        _run(
            _configure_command(
                paths, package_mode=package_mode, install_prefix=install_prefix
            ),
            root,
            environment,
        )
    _run(
        ["cmake", "--build", str(paths.build_dir), "--target", target, "--parallel"],
        root,
        environment,
    )


def _prepare_target(
    paths: BuildPaths,
    root: Path,
    environment: dict[str, str] | None,
    target: str,
    binary: Path,
    *,
    force_configure: bool = False,
    package_mode: bool = False,
    install_prefix: Path | None = None,
) -> Path:
    """Provision dependencies, rebuild one source target, and verify its output."""
    environment_snapshot = dict(os.environ if environment is None else environment)
    _require_build_tools(environment_snapshot)
    _ensure_submodule(root)
    if not dependency_prefix_complete(paths.dependency_prefix):
        try:
            provision_dependency_prefix(root, paths.dependency_prefix, environment_snapshot)
        except DependencyPrefixError as error:
            raise BuildError(str(error)) from error
    _build_target(
        paths,
        root,
        environment_snapshot,
        target,
        force_configure=force_configure,
        package_mode=package_mode,
        install_prefix=install_prefix,
    )
    if not binary.is_file():
        raise BuildError(f"build completed without producing {binary}")
    return binary


def prepare_product(root: Path, environment: dict[str, str] | None = None) -> Path:
    """Provision source dependencies and build the standalone AVPE product."""
    paths = BuildPaths(root)
    return _prepare_target(paths, root, environment, "avpe", paths.product_binary)


def _reset_generated_directory(path: Path) -> None:
    """Reset one exact generated output directory before staging a package."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def prepare_product_package(
    root: Path, environment: dict[str, str] | None = None
) -> Path:
    """Build and stage the standalone AVPE installable package boundary."""
    paths = BuildPaths(root)
    _reset_generated_directory(paths.package_install_dir)
    _prepare_target(
        paths,
        root,
        environment,
        "avpe",
        paths.product_binary,
        force_configure=True,
        package_mode=True,
        install_prefix=paths.package_install_dir,
    )
    environment_snapshot = dict(os.environ if environment is None else environment)
    _run(["cmake", "--install", str(paths.build_dir)], root, environment_snapshot)

    installed_binary = paths.package_install_dir / "bin" / "avpe"
    installed_resources = paths.package_install_dir / "share" / "avpe"
    if not installed_binary.is_file():
        raise BuildError(f"install completed without producing {installed_binary}")
    _reset_generated_directory(paths.package_dir)
    staged_binary = paths.package_dir / "bin" / "avpe"
    staged_binary.parent.mkdir(parents=True)
    shutil.copy2(installed_binary, staged_binary)
    if installed_resources.is_dir():
        shutil.copytree(
            installed_resources,
            paths.package_dir / "share" / "avpe",
        )
    return paths.package_dir


def prepare_control_test(root: Path, environment: dict[str, str] | None = None) -> Path:
    """Provision source dependencies and rebuild the surfaceless oracle frontend."""
    paths = BuildPaths(root)
    return _prepare_target(paths, root, environment, "pcsx2-qt", paths.control_test_binary)
