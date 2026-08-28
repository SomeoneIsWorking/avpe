"""Provision the PCSX2 dependency prefix through its tracked workflow."""

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shutil
import subprocess

@dataclass(frozen=True)
class DependencyWorkflow:
    script: Path


class DependencyPrefixError(RuntimeError):
    """The dependency workflow could not be selected or completed."""


def dependency_prefix_complete(deps_dir: Path) -> bool:
    return (
        (deps_dir / "include" / "QtCore" / "qglobal.h").is_file()
        and (deps_dir / "lib" / "cmake" / "Qt6" / "Qt6Config.cmake").is_file()
    )


def dependency_prefix_error(deps_dir: Path) -> str:
    header = deps_dir / "include" / "QtCore" / "qglobal.h"
    config = deps_dir / "lib" / "cmake" / "Qt6" / "Qt6Config.cmake"
    return (
        f"self-built Qt/deps prefix incomplete: header={header.is_file()} "
        f"cmake_config={config.is_file()} — provision {deps_dir} with the "
        "PCSX2 Qt dependency workflow before building AVPE"
    )


def select_workflow(root: Path, system: str | None = None) -> DependencyWorkflow:
    host = system or platform.system()
    scripts = {
        "Linux": root / "thirdparty" / "pcsx2" / ".github" / "workflows" / "scripts" / "linux" / "build-dependencies-qt.sh",
        "Darwin": root / "thirdparty" / "pcsx2" / ".github" / "workflows" / "scripts" / "macos" / "build-dependencies.sh",
    }
    script = scripts.get(host)
    if script is None:
        raise DependencyPrefixError(
            f"automatic dependency-prefix provisioning is unsupported on {host}; "
            "use the documented PCSX2 dependency workflow for that platform"
        )
    if not script.is_file():
        raise DependencyPrefixError(f"tracked dependency workflow is missing: {script}")
    return DependencyWorkflow(script)


def _required_tools(environment: dict[str, str]) -> tuple[str, ...]:
    names = ("bash", "curl", "shasum", "tar", "make", "patch", "gzip", "cmake", "ninja")
    missing = [name for name in names if shutil.which(name) is None]
    compiler = environment.get("CXX") or "c++"
    if shutil.which(compiler) is None:
        missing.append("c++")
    return tuple(missing)


def _install_hint(missing: tuple[str, ...], system: str) -> str:
    if system == "Darwin":
        commands = []
        brew_packages = [name for name in missing if name in {"cmake", "ninja"}]
        if brew_packages:
            commands.append("brew install " + " ".join(brew_packages))
        if any(name in missing for name in ("bash", "make", "patch", "c++")):
            commands.append("xcode-select --install")
        return " && ".join(commands)
    if system == "Linux":
        package_manager = "dnf" if _fedora_family() else "apt"
        package_names = {
            "bash": "bash",
            "curl": "curl",
            "shasum": "perl-Digest-SHA" if package_manager == "dnf" else "perl",
            "tar": "tar",
            "make": "make",
            "patch": "patch",
            "gzip": "gzip",
            "cmake": "cmake",
            "ninja": "ninja-build",
            "c++": "gcc-c++" if package_manager == "dnf" else "g++",
        }
        return f"sudo {package_manager} install " + " ".join(package_names[name] for name in missing)
    return "install the missing tools using the supported platform instructions"


def _fedora_family() -> bool:
    try:
        values = {}
        for line in Path("/etc/os-release").read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value.strip('"').lower()
    except OSError:
        return False
    return values.get("ID") in {"fedora", "rhel", "rocky", "almalinux", "centos"}


def provision_dependency_prefix(
    root: Path,
    output_dir: Path,
    environment: dict[str, str] | None = None,
) -> Path:
    """Run the vendor workflow in scratch and verify its Qt prefix output."""
    root = root.resolve()
    output_dir = output_dir.resolve()
    env = dict(os.environ if environment is None else environment)
    workflow = select_workflow(root)
    missing = _required_tools(env)
    if missing:
        names = ", ".join(missing)
        raise DependencyPrefixError(
            f"missing dependency-build tool(s): {names} — run: "
            f"{_install_hint(missing, platform.system())}"
        )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    env["BUILD_FFMPEG"] = "0"
    command = [str(workflow.script), str(output_dir)]
    try:
        subprocess.run(command, cwd=output_dir.parent, env=env, check=True)
    except OSError as error:
        raise DependencyPrefixError(f"could not execute {' '.join(command)}: {error}") from error
    except subprocess.CalledProcessError as error:
        raise DependencyPrefixError(
            f"dependency workflow failed with exit status {error.returncode}: {' '.join(command)}"
        ) from error
    if not dependency_prefix_complete(output_dir):
        raise DependencyPrefixError(
            f"dependency workflow completed without a usable Qt prefix at {output_dir}"
        )
    return output_dir
