import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import Mock, call, patch

from avpe.build import BuildError, BuildPaths, install_hint, prepare_product
from avpe.dependency_prefix import DependencyPrefixError


class BuildHintTests(unittest.TestCase):
    def test_fedora_hint_names_the_user_run_packages(self) -> None:
        self.assertEqual(
            install_hint(("cmake", "ninja", "c++"), "Linux", "dnf"),
            "sudo dnf install cmake ninja-build gcc-c++",
        )

    def test_debian_hint_names_the_user_run_packages(self) -> None:
        self.assertEqual(
            install_hint(("cmake", "ninja", "c++"), "Linux", "apt"),
            "sudo apt install cmake ninja-build g++",
        )

    def test_macos_hint_uses_homebrew(self) -> None:
        self.assertEqual(
            install_hint(("cmake", "ninja"), "Darwin"),
            "brew install cmake ninja",
        )


class ProductPreparationTests(unittest.TestCase):
    def test_build_paths_use_the_top_level_build_root(self) -> None:
        paths = BuildPaths(Path("/repo"))

        self.assertEqual(paths.build_dir, Path("/repo/build"))
        self.assertEqual(paths.dependency_prefix, Path("/repo/build/deps"))
        self.assertEqual(paths.product_binary, Path("/repo/build/bin/avpe"))

    @patch("avpe.launch.launch", return_value=0)
    @patch("avpe.cli.prepare_product")
    @patch("avpe.cli.load_env", return_value={"AVPE_CHD": "/game/test.chd"})
    def test_default_cli_path_prepares_before_launch(
        self, load_env: Mock, prepare: Mock, launch: Mock
    ) -> None:
        from avpe.cli import main

        self.assertEqual(main([]), 0)
        prepare.assert_called_once()
        launch.assert_called_once_with("/game/test.chd")

    @patch("avpe.build._run")
    @patch("avpe.build._ensure_submodule")
    @patch("avpe.build.dependency_prefix_complete", return_value=True)
    @patch("avpe.build.shutil.which", return_value="/usr/bin/tool")
    @patch("avpe.build.BuildPaths")
    def test_configures_and_builds_missing_product(
        self,
        paths_type: Mock,
        _which: Mock,
        _prefix_complete: Mock,
        ensure_submodule: Mock,
        run: Mock,
    ) -> None:
        paths = paths_type.return_value
        paths.source_dir = Path("/repo/thirdparty/pcsx2")
        paths.build_dir = Path("/repo/build")
        paths.dependency_prefix = Path("/repo/build/deps")
        paths.product_binary = Mock()
        paths.product_binary.is_file.return_value = True

        result = prepare_product(Path("/repo"), {"CXX": "clang++"})

        self.assertIs(result, paths.product_binary)
        ensure_submodule.assert_called_once_with(Path("/repo"))
        self.assertEqual(
            run.call_args_list,
            [
                call(
                    [
                        "cmake",
                        "-S",
                        "/repo/thirdparty/pcsx2",
                        "-B",
                        "/repo/build",
                        "-G",
                        "Ninja",
                        "-DCMAKE_BUILD_TYPE=Release",
                        "-DCMAKE_PREFIX_PATH=/repo/build/deps",
                        "-DENABLE_QT_UI=ON",
                        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                        f"-DPython3_EXECUTABLE={sys.executable}",
                    ],
                    Path("/repo"),
                    {"CXX": "clang++"},
                ),
                call(
                    [
                        "cmake",
                        "--build",
                        "/repo/build",
                        "--target",
                        "avpe",
                        "--parallel",
                    ],
                    Path("/repo"),
                    {"CXX": "clang++"},
                ),
            ],
        )

    @patch("avpe.build._run")
    @patch("avpe.build._require_build_tools")
    @patch("avpe.build._ensure_submodule")
    @patch("avpe.build.dependency_prefix_complete", return_value=True)
    @patch("avpe.build.BuildPaths")
    def test_existing_product_rebuilds_current_target(
        self,
        paths_type: Mock,
        _prefix_complete: Mock,
        ensure: Mock,
        _require_tools: Mock,
        run: Mock,
    ) -> None:
        paths = paths_type.return_value
        paths.product_binary.is_file.return_value = True
        paths.dependency_prefix = Path("/repo/build/deps")

        with tempfile.TemporaryDirectory() as directory:
            paths.build_dir = Path(directory)
            (paths.build_dir / "build.ninja").write_text("# test build tree\n")
            result = prepare_product(Path("/repo"), {})

        self.assertIs(result, paths.product_binary)
        ensure.assert_called_once_with(Path("/repo"))
        run.assert_called_once_with(
            [
                "cmake",
                "--build",
                str(paths.build_dir),
                "--target",
                "avpe",
                "--parallel",
            ],
            Path("/repo"),
            {},
        )

    @patch("avpe.build._run")
    @patch("avpe.build._require_build_tools")
    @patch("avpe.build._ensure_submodule")
    @patch("avpe.build.dependency_prefix_complete", return_value=True)
    @patch("avpe.build.BuildPaths")
    def test_existing_product_with_missing_build_tree_configures_before_build(
        self,
        paths_type: Mock,
        _prefix_complete: Mock,
        ensure: Mock,
        _require_tools: Mock,
        run: Mock,
    ) -> None:
        paths = paths_type.return_value
        paths.product_binary.is_file.return_value = True
        paths.source_dir = Path("/repo/thirdparty/pcsx2")
        paths.dependency_prefix = Path("/repo/build/deps")

        with tempfile.TemporaryDirectory() as directory:
            paths.build_dir = Path(directory)
            prepare_product(Path("/repo"), {})

        ensure.assert_called_once_with(Path("/repo"))
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1][0][0][:5], [
            "cmake", "--build", str(paths.build_dir), "--target", "avpe"
        ])

    @patch("avpe.build._ensure_submodule")
    @patch("avpe.build.dependency_prefix_complete", return_value=False)
    @patch(
        "avpe.build.provision_dependency_prefix",
        side_effect=DependencyPrefixError("self-built Qt/deps prefix incomplete"),
    )
    @patch("avpe.build.shutil.which", return_value="/usr/bin/tool")
    @patch("avpe.build.BuildPaths")
    def test_incomplete_dependency_prefix_refuses_before_cmake(
        self,
        paths_type: Mock,
        _which: Mock,
        provision_prefix: Mock,
        _prefix_complete: Mock,
        ensure_submodule: Mock,
    ) -> None:
        paths = paths_type.return_value
        paths.product_binary.is_file.return_value = False
        paths.dependency_prefix = Path("/repo/build/deps")

        with self.assertRaisesRegex(BuildError, "self-built Qt/deps prefix incomplete"):
            prepare_product(Path("/repo"), {})

        ensure_submodule.assert_called_once_with(Path("/repo"))
        provision_prefix.assert_called_once()

    @patch("avpe.build.platform.system", return_value="Linux")
    @patch("avpe.build._linux_package_manager", return_value="dnf")
    @patch("avpe.build.shutil.which", return_value=None)
    def test_missing_tools_explain_dnf_install(self, _which: Mock, _manager: Mock, _system: Mock) -> None:
        with self.assertRaisesRegex(BuildError, r"sudo dnf install cmake ninja-build gcc-c\+\+"):
            prepare_product(Path("/repo"), {})


if __name__ == "__main__":
    unittest.main()
