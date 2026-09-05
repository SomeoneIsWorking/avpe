"""Hosted, asset-free verification of AVPE's buildable product boundary."""

import os
from pathlib import Path
import platform
import subprocess
import sys
from collections.abc import Callable

from avpe.build import prepare_product


class CiError(RuntimeError):
    """The current host is not an AVPE CI target."""


SUPPORTED_HOSTS = frozenset({"Linux", "Darwin"})


def verify_host(
    root: Path,
    environment: dict[str, str] | None = None,
    system: str | None = None,
    run: Callable[..., subprocess.CompletedProcess[object]] = subprocess.run,
) -> Path:
    """Build AVPE and run its normal asset-free verifier on one supported host."""
    host = system or platform.system()
    if host not in SUPPORTED_HOSTS:
        raise CiError(f"AVPE hosted CI is unsupported on {host}")

    env = dict(os.environ if environment is None else environment)
    binary = prepare_product(root, env)
    run([sys.executable, "tools/verify.py"], cwd=root, env=env, check=True)
    return binary
