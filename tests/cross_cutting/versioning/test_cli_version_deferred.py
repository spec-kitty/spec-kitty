"""``specify_cli.__version__`` is resolved on first use, not at import (#6584).

Resolving the version means resolving the CLI's distribution name, and that
goes through ``importlib.metadata.packages_distributions()``, which reads the
metadata of every installed distribution. ``specify_cli/__init__.py`` used to
do it at import, so ``spec-kitty --help`` paid for a version it never prints.
The subprocess tests pin the deferral through the real entry point; the
``--version`` case is the control that shows the probe sees the scan when it
happens.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Counts ``packages_distributions()`` calls, then runs the CLI's ``main()``.
#: The patch is installed before ``specify_cli`` is imported, so the
#: ``from importlib.metadata import packages_distributions`` binding in
#: ``specify_cli.distribution.package_name`` picks up the counting wrapper.
_PROBE = r"""
import contextlib, io, json, sys
import importlib.metadata as metadata

calls = []
real = metadata.packages_distributions

def counting():
    calls.append(1)
    return real()

metadata.packages_distributions = counting
sys.argv = ["spec-kitty", *json.loads(sys.argv[1])]
from specify_cli import main

out = io.StringIO()
with contextlib.redirect_stdout(out):
    try:
        main()
    except SystemExit:
        pass
print(json.dumps({"scans": len(calls), "stdout": out.getvalue()}))
"""


class _ProbeReport(TypedDict):
    scans: int
    stdout: str


def _run_cli(*args: str) -> _ProbeReport:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    # Test mode short-circuits the version to an env value, which would make
    # the --version control pass without any metadata scan.
    env.pop("SPEC_KITTY_TEST_MODE", None)
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, json.dumps(list(args))],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    report: _ProbeReport = json.loads(result.stdout.strip().splitlines()[-1])
    return report


def test_help_does_not_scan_distribution_metadata() -> None:
    report = _run_cli("--help")
    assert "Usage" in report["stdout"], "--help printed no usage text: the probe is vacuous"
    assert report["scans"] == 0, "spec-kitty --help resolved the CLI version (a packages_distributions() scan)"


def test_version_still_resolves_the_version() -> None:
    report = _run_cli("--version")
    assert report["scans"] >= 1, "--version did not reach packages_distributions(): the --help probe proves nothing"
    assert " version " in report["stdout"]
