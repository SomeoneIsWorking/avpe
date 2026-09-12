import subprocess
import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

from avpe.ci import CiError, assert_asset_free_package, verify_host


class HostedCiTests(unittest.TestCase):
    def test_reuses_product_preparation_and_normal_verifier(self) -> None:
        root = Path("/repo")
        package = root / "build" / "avpe-package"
        binary = package / "bin" / "avpe"
        environment = {"CXX": "clang++"}
        run = Mock()
        with patch("avpe.ci.prepare_product_package", return_value=package) as prepare:
            with patch("avpe.ci.assert_asset_free_package") as assert_package:
                self.assertEqual(verify_host(root, environment, "Linux", run), binary)
        prepare.assert_called_once_with(root, environment)
        assert_package.assert_called_once_with(package, "Linux")
        run.assert_called_once_with(
            [ANY, "tools/verify.py"],
            cwd=root,
            env={**environment, "AVPE_TEST_PRODUCT": str(binary)},
            check=True,
        )

    def test_macos_verifier_returns_the_staged_bundle_executable(self) -> None:
        root = Path("/repo")
        package = root / "build" / "avpe-package"
        environment = {"CXX": "clang++"}
        run = Mock()
        with patch("avpe.ci.prepare_product_package", return_value=package):
            with patch("avpe.ci.assert_asset_free_package") as assert_package:
                with patch("avpe.ci.platform.machine", return_value="arm64"):
                    binary = verify_host(root, environment, "Darwin", run)
        self.assertEqual(binary, package / "avpe.app/Contents/MacOS/avpe")
        assert_package.assert_called_once_with(package, "Darwin")
        self.assertEqual(
            run.call_args_list[0].args[0],
            ["lipo", str(binary), "-verify_arch", "arm64"],
        )
        self.assertEqual(run.call_args_list[1].args[0][0], "codesign")
        self.assertEqual(run.call_args_list[2].args[0][:2], ["codesign", "--verify"])
        self.assertEqual(run.call_args_list[3].args[0][1], "tools/verify.py")

    def test_macos_signature_failure_stops_before_normal_verifier(self) -> None:
        root = Path("/repo")
        package = root / "build" / "avpe-package"
        run = Mock(side_effect=[None, None, subprocess.CalledProcessError(1, "codesign")])
        with patch("avpe.ci.prepare_product_package", return_value=package):
            with patch("avpe.ci.assert_asset_free_package"):
                with self.assertRaises(subprocess.CalledProcessError):
                    verify_host(root, {}, "Darwin", run)
        self.assertEqual(run.call_count, 3)

    def test_asset_free_package_rejects_unowned_files(self) -> None:
        with self.subTest("generic frontend"):
            with self.assertRaisesRegex(CiError, "unowned file"):
                with self._package_tree("bin/pcsx2-qt"):
                    assert_asset_free_package(self._package_root)

        with self.subTest("game asset"):
            with self.assertRaisesRegex(CiError, "user-supplied asset"):
                with self._package_tree("bin/resources/disc.iso"):
                    assert_asset_free_package(self._package_root)

    def test_asset_free_package_accepts_product_and_resources(self) -> None:
        with self._package_tree("bin/resources/GameIndex.yaml"):
            assert_asset_free_package(self._package_root)

    def test_asset_free_package_requires_the_core_resources(self) -> None:
        with self._package_tree("bin/resources/other.txt"):
            with self.assertRaisesRegex(CiError, "missing core resources"):
                assert_asset_free_package(self._package_root)

    def test_asset_free_package_requires_desktop_platform_plugins(self) -> None:
        with self._package_tree("bin/resources/GameIndex.yaml"):
            (self._package_root / "plugins/platforms/libqwayland.so").unlink()
            with self.assertRaisesRegex(CiError, "libqwayland.so"):
                assert_asset_free_package(self._package_root)

    def test_macos_bundle_is_the_product_package_boundary(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "avpe.app/Contents/MacOS/avpe"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"product")
            resource = root / "avpe.app/Contents/Resources/GameIndex.yaml"
            resource.parent.mkdir(parents=True)
            resource.write_bytes(b"resource")
            assert_asset_free_package(root, "Darwin")
            (root / "bin").mkdir()
            (root / "bin" / "pcsx2-qt").write_bytes(b"unowned")
            with self.assertRaisesRegex(CiError, "unowned file"):
                assert_asset_free_package(root, "Darwin")

    def _package_tree(self, extra: str):
        import tempfile

        temporary = tempfile.TemporaryDirectory()
        self._package_root = Path(temporary.name)
        (self._package_root / "bin").mkdir()
        (self._package_root / "bin" / "avpe").write_bytes(b"product")
        (self._package_root / "bin" / "qt.conf").write_text("[Paths]\n")
        platforms = self._package_root / "plugins" / "platforms"
        platforms.mkdir(parents=True)
        for name in ("libqoffscreen.so", "libqxcb.so", "libqwayland.so"):
            (platforms / name).write_bytes(b"plugin")
        extra_path = self._package_root / extra
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        extra_path.write_bytes(b"fixture")
        return temporary

    def test_refuses_an_unclaimed_host(self) -> None:
        with self.assertRaisesRegex(CiError, "unsupported on Windows"):
            verify_host(Path("/repo"), system="Windows")


if __name__ == "__main__":
    unittest.main()
