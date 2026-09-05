import subprocess
import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

from avpe.ci import CiError, verify_host


class HostedCiTests(unittest.TestCase):
    def test_reuses_product_preparation_and_normal_verifier(self) -> None:
        root = Path("/repo")
        binary = root / "build" / "bin" / "avpe"
        environment = {"CXX": "clang++"}
        run = Mock()
        with patch("avpe.ci.prepare_product", return_value=binary) as prepare:
            self.assertEqual(verify_host(root, environment, "Linux", run), binary)
        prepare.assert_called_once_with(root, environment)
        run.assert_called_once_with(
            [ANY, "tools/verify.py"], cwd=root, env=environment, check=True
        )

    def test_refuses_an_unclaimed_host(self) -> None:
        with self.assertRaisesRegex(CiError, "unsupported on Windows"):
            verify_host(Path("/repo"), system="Windows")


if __name__ == "__main__":
    unittest.main()
