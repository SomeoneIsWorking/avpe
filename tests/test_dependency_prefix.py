import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from avpe.dependency_prefix import (
    DependencyPrefixError,
    DependencyWorkflow,
    _install_hint,
    provision_dependency_prefix,
    select_workflow,
)


ROOT = Path(__file__).resolve().parent.parent


class WorkflowSelectionTests(unittest.TestCase):
    def test_selects_tracked_linux_workflow(self) -> None:
        workflow = select_workflow(ROOT, "Linux")

        self.assertEqual(workflow.script.name, "build-dependencies-qt.sh")
        self.assertTrue(workflow.script.is_file())

    def test_rejects_unsupported_platform(self) -> None:
        with self.assertRaisesRegex(DependencyPrefixError, "unsupported on Windows"):
            select_workflow(ROOT, "Windows")


class DependencyPrefixProvisioningTests(unittest.TestCase):
    @patch("avpe.dependency_prefix.dependency_prefix_complete", return_value=True)
    @patch("avpe.dependency_prefix.subprocess.run")
    @patch("avpe.dependency_prefix._required_tools", return_value=())
    @patch("avpe.dependency_prefix.select_workflow")
    @patch("avpe.dependency_prefix.Path.mkdir")
    def test_runs_vendor_workflow_under_build_root_and_verifies_output(
        self,
        _mkdir: Mock,
        select: Mock,
        _required_tools: Mock,
        run: Mock,
        _complete: Mock,
    ) -> None:
        root = Path("/repo")
        output = root / "build" / "deps"
        script = root / "thirdparty" / "pcsx2" / "workflow.sh"
        select.return_value = DependencyWorkflow(script)
        run.return_value = subprocess.CompletedProcess([], 0)

        result = provision_dependency_prefix(root, output, {"CXX": "clang++"})

        self.assertEqual(result, output)
        run.assert_called_once_with(
            [str(script), str(output)],
            cwd=root / "build",
            env={"CXX": "clang++", "BUILD_FFMPEG": "0"},
            check=True,
        )

    @patch("avpe.dependency_prefix._required_tools", return_value=("curl", "shasum"))
    @patch("avpe.dependency_prefix.select_workflow")
    @patch("avpe.dependency_prefix.platform.system", return_value="Linux")
    @patch("avpe.dependency_prefix._fedora_family", return_value=True)
    def test_missing_tools_refuse_with_dnf_command(
        self, _fedora: Mock, _system: Mock, _select: Mock, _required: Mock
    ) -> None:
        with self.assertRaisesRegex(
            DependencyPrefixError,
            "sudo dnf install curl perl-Digest-SHA",
        ):
            provision_dependency_prefix(Path("/repo"), Path("/repo/build/deps"), {})


class InstallHintTests(unittest.TestCase):
    def test_apt_hint_maps_dependency_tools(self) -> None:
        with patch("avpe.dependency_prefix._fedora_family", return_value=False):
            self.assertEqual(
                _install_hint(("curl", "shasum", "ninja", "c++"), "Linux"),
                "sudo apt install curl perl ninja-build g++",
            )

    def test_macos_hint_uses_the_command_line_tools_for_compiler(self) -> None:
        self.assertEqual(
            _install_hint(("cmake", "c++"), "Darwin"),
            "brew install cmake && xcode-select --install",
        )


if __name__ == "__main__":
    unittest.main()
