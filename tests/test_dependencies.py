import subprocess
import unittest
from pathlib import Path
from unittest.mock import call, patch

from avpe.dependencies import (
    SubmoduleState,
    parse_gitlink_revision,
    provision_submodules,
)


class GitlinkParsingTests(unittest.TestCase):
    def test_extracts_revision_from_gitlink_record(self) -> None:
        revision = "37a1c62a937162902a8b46ec9b222f35227fd898"
        record = f"160000 {revision} 0\tthirdparty/pcsx2\n"

        self.assertEqual(parse_gitlink_revision(record), revision)

    def test_rejects_regular_file_record(self) -> None:
        record = "100644 1111111111111111111111111111111111111111 0\tdeps.toml\n"

        self.assertIsNone(parse_gitlink_revision(record))

    def test_ready_requires_matching_nonempty_revisions(self) -> None:
        self.assertTrue(SubmoduleState("abc", "abc").is_ready)
        self.assertFalse(SubmoduleState("abc", "def").is_ready)
        self.assertFalse(SubmoduleState(None, None).is_ready)


class ProvisioningTests(unittest.TestCase):
    @patch("avpe.dependencies.subprocess.run")
    def test_syncs_then_initializes_recursively(self, run) -> None:
        run.return_value = subprocess.CompletedProcess([], 0)
        root = Path("/project")

        self.assertTrue(provision_submodules(root))

        self.assertEqual(
            run.call_args_list,
            [
                call(
                    ["git", "-C", "/project", "submodule", "sync", "--recursive"],
                    check=False,
                ),
                call(
                    [
                        "git",
                        "-C",
                        "/project",
                        "submodule",
                        "update",
                        "--init",
                        "--recursive",
                    ],
                    check=False,
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
