import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LINE_CAP = 1_200
PYTHON_ROOTS = (ROOT / "src" / "avpe", ROOT / "tools")
AVPE_CPP_ROOTS = (
    ROOT / "thirdparty" / "pcsx2" / "pcsx2" / "AVPE",
    ROOT / "thirdparty" / "pcsx2" / "pcsx2-avpe",
)
CPP_SUFFIXES = frozenset({".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"})


def owned_sources() -> list[Path]:
    python_sources = (
        path
        for source_root in PYTHON_ROOTS
        for path in source_root.rglob("*.py")
    )
    cpp_sources = (
        path
        for source_root in AVPE_CPP_ROOTS
        for path in source_root.rglob("*")
        if path.suffix.lower() in CPP_SUFFIXES
    )
    return sorted(
        path for path in (*python_sources, *cpp_sources)
        if path.is_file() and not path.is_symlink()
    )


class ProjectStructureTests(unittest.TestCase):
    def test_build_outputs_do_not_live_under_scratch(self) -> None:
        forbidden = (
            '"scratch" / "build"',
            '"scratch" / "deps"',
            "'scratch' / 'build'",
            "'scratch' / 'deps'",
            "scratch/build",
            "scratch/deps",
        )
        violations: list[Path] = []
        for source_root in PYTHON_ROOTS:
            for source in source_root.rglob("*.py"):
                text = source.read_text(encoding="utf-8")
                if any(value in text for value in forbidden):
                    violations.append(source.relative_to(ROOT))

        self.assertFalse(
            violations,
            "build output path is still owned by scratch/: "
            + ", ".join(str(path) for path in sorted(violations)),
        )

    def test_first_party_source_files_do_not_exceed_line_cap(self) -> None:
        violations: list[tuple[Path, int]] = []
        for source in owned_sources():
            line_count = len(source.read_text(encoding="utf-8").splitlines())
            if line_count > SOURCE_LINE_CAP:
                violations.append((source.relative_to(ROOT), line_count))

        details = "\n".join(
            f"  {path}: {line_count} lines (cap: {SOURCE_LINE_CAP})"
            for path, line_count in violations
        )
        self.assertFalse(
            violations,
            "first-party source file line cap exceeded:\n" + details,
        )

    def test_product_target_is_independent_of_pcsx2_gui(self) -> None:
        cmake = (
            ROOT / "thirdparty" / "pcsx2" / "pcsx2-avpe" / "CMakeLists.txt"
        ).read_text(encoding="utf-8")
        self.assertIn("add_executable(avpe", cmake)
        self.assertIn("PCSX2", cmake)
        forbidden = (
            "pcsx2-qt",
            "MainWindow",
            "DisplayWidget",
            "GameList",
            "Debugger",
            "Settings/",
            "KDAB::kddockwidgets",
        )
        for dependency in forbidden:
            self.assertNotIn(dependency, cmake)

    def test_pcsx2_qt_has_no_product_frontend_mode(self) -> None:
        qt_host = (
            ROOT / "thirdparty" / "pcsx2" / "pcsx2-qt" / "QtHost.cpp"
        ).read_text(encoding="utf-8")
        self.assertNotIn("-avpe-host", qt_host)
        self.assertNotIn("HostWindow", qt_host)

    def test_native_environment_reads_have_one_owner(self) -> None:
        native_config = (
            ROOT
            / "thirdparty"
            / "pcsx2"
            / "pcsx2"
            / "AVPE"
            / "NativeConfig.cpp"
        )
        violations: list[Path] = []
        for source_root in AVPE_CPP_ROOTS:
            for source in source_root.rglob("*"):
                if (
                    source.suffix.lower() in CPP_SUFFIXES
                    and source.is_file()
                    and source != native_config
                    and "getenv" in source.read_text(encoding="utf-8")
                ):
                    violations.append(source.relative_to(ROOT))

        self.assertFalse(
            violations,
            "native environment access must be owned by AVPE/NativeConfig.cpp: "
            + ", ".join(str(path) for path in sorted(violations)),
        )


if __name__ == "__main__":
    unittest.main()
