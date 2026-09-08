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
        assert_package.assert_called_once_with(package)
        run.assert_called_once_with(
            [ANY, "tools/verify.py"], cwd=root, env=environment, check=True
        )

    def test_asset_free_package_rejects_unowned_files(self) -> None:
        with self.subTest("generic frontend"):
            with self.assertRaisesRegex(CiError, "unowned file"):
                with self._package_tree("bin/pcsx2-qt"):
                    assert_asset_free_package(self._package_root)

        with self.subTest("game asset"):
            with self.assertRaisesRegex(CiError, "user-supplied asset"):
                with self._package_tree("share/avpe/resources/disc.iso"):
                    assert_asset_free_package(self._package_root)

    def test_asset_free_package_accepts_product_and_resources(self) -> None:
        with self._package_tree("share/avpe/resources/GameIndex.yaml"):
            assert_asset_free_package(self._package_root)

    def _package_tree(self, extra: str):
        import tempfile

        temporary = tempfile.TemporaryDirectory()
        self._package_root = Path(temporary.name)
        (self._package_root / "bin").mkdir()
        (self._package_root / "bin" / "avpe").write_bytes(b"product")
        extra_path = self._package_root / extra
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        extra_path.write_bytes(b"fixture")
        return temporary

    def test_refuses_an_unclaimed_host(self) -> None:
        with self.assertRaisesRegex(CiError, "unsupported on Windows"):
            verify_host(Path("/repo"), system="Windows")


if __name__ == "__main__":
    unittest.main()
