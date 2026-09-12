"""Exercise the standalone product's failure exit through its real binary."""

import os
import subprocess
import unittest
from pathlib import Path

from avpe.build import BuildPaths


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = Path(os.environ.get("AVPE_TEST_PRODUCT", BuildPaths(ROOT).product_binary))
PROBE = ROOT / "scratch" / "product-boot-test"


class ProductBootTests(unittest.TestCase):
    def test_missing_game_reports_boot_failure_to_caller(self) -> None:
        self.assertTrue(PRODUCT.is_file(), f"product binary is missing: {PRODUCT}")
        missing_game = PROBE / "missing.chd"
        self.assertFalse(missing_game.exists(), f"test input unexpectedly exists: {missing_game}")
        PROBE.mkdir(parents=True, exist_ok=True)
        environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        result = subprocess.run(
            [str(PRODUCT), "-datapath", str(PROBE / "data"), "--", str(missing_game)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("game boot failed", result.stdout + result.stderr)
        self.assertIn("does not exist", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
