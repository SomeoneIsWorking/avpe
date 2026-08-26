import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LINE_CAP = 1_200
PYTHON_ROOTS = (ROOT / "src" / "avpe", ROOT / "tools")
AVPE_CPP_ROOTS = (
    ROOT / "thirdparty" / "pcsx2" / "pcsx2" / "AVPE",
    ROOT / "thirdparty" / "pcsx2" / "pcsx2-qt" / "AVPE",
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


if __name__ == "__main__":
    unittest.main()
