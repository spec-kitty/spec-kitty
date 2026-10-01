"""Local-runnable counterpart of the clean-install CI verification job.

Mirrors the GitHub Actions job in
``.github/workflows/ci-quality.yml`` (``clean-install-verification``) so
developers can reproduce the assertion on their own machines, end-to-end.

Per FR-010 / FR-017 of mission ``shared-package-boundary-cutover-01KQ22DS``,
the CLI must run ``spec-kitty next`` against a fixture mission in a clean
venv without ``spec-kitty-runtime`` installed.

Marked ``@pytest.mark.distribution`` (slow: builds a wheel + creates a
clean venv + installs the wheel) and ``@pytest.mark.integration``. Does
not run in the fast gate; runs in the distribution / nightly gate and on
demand locally::

    pytest tests/integration/test_clean_install_next.py -m distribution -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

pytestmark = [pytest.mark.distribution, pytest.mark.integration, pytest.mark.git_repo]


_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "clean_install_fixture_mission"


def _build_wheel(repo_root: Path, out: Path) -> Path:
    """Build the spec-kitty-cli wheel into ``out`` and return its path."""
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(out)],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    wheels = list(out.glob("spec_kitty_cli-*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, found {wheels}"
    return wheels[0]


def _venv_bin(venv_dir: Path, name: str) -> Path:
    """Return the venv's bin/<name> path (Windows: Scripts/<name>.exe)."""
    if os.name == "nt":  # pragma: no cover — CI runs on Linux
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def test_clean_install_next_runs_without_runtime(tmp_path: Path) -> None:
    """End-to-end: install spec-kitty-cli into a clean venv, run ``next``.

    Assertions:

    1. After ``pip install spec_kitty_cli-*.whl``, ``spec-kitty-runtime``
       is NOT installed.
    2. ``spec-kitty next --json`` runs successfully against the fixture
       mission and reports ``result == "success"`` (or another non-error
       result that proves the runtime entry point is wired up).
    3. After importing ``specify_cli``, ``spec_kitty_runtime`` is NOT in
       ``sys.modules``.
    """
    # ---- Build the wheel from the repo source tree.
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = _build_wheel(_REPO_ROOT, dist)

    # ---- Create a clean venv and install the wheel.
    venv_dir = tmp_path / "clean-venv"
    venv.create(venv_dir, with_pip=True, clear=True)
    py = _venv_bin(venv_dir, "python")
    pip = _venv_bin(venv_dir, "pip")
    sk = _venv_bin(venv_dir, "spec-kitty")

    subprocess.run(
        [str(pip), "install", "--upgrade", "pip"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [str(pip), "install", str(wheel)],
        check=True,
        capture_output=True,
    )

    # ---- Assertion 1: spec-kitty-runtime is NOT installed.
    show = subprocess.run(
        [str(pip), "show", "spec-kitty-runtime"],
        capture_output=True,
    )
    assert show.returncode != 0, (
        "spec-kitty-runtime got installed transitively. Per FR-006 / FR-010 "
        "of mission shared-package-boundary-cutover-01KQ22DS, the CLI must "
        "not depend on the retired runtime PyPI package, directly or "
        "transitively."
    )

    # ---- Assertion 3 (run before next so we don't import side-effects from
    #      a previously-claimed mission state):
    check = subprocess.run(
        [
            str(py),
            "-c",
            (
                "import sys, specify_cli; "
                "leaked = [k for k in sys.modules if 'spec_kitty_runtime' in k]; "
                "assert not leaked, f'spec_kitty_runtime imported: {leaked}'"
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, (
        f"importing specify_cli pulled in spec_kitty_runtime: {check.stderr}"
    )

    # ---- Assertion 2: spec-kitty next runs against the fixture mission.
    fixture_copy = tmp_path / "mission"
    shutil.copytree(_FIXTURE, fixture_copy)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=fixture_copy,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=fixture_copy,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-c", "user.email=t@t",
            "-c", "user.name=t",
            "commit", "-q", "-m", "fixture",
        ],
        cwd=fixture_copy,
        check=True,
        capture_output=True,
    )

    result = subprocess.run(
        [
            str(sk),
            "next",
            "--agent", "claude",
            "--mission", "clean-install-fixture-01KQ22XX",
            "--json",
        ],
        cwd=fixture_copy,
        capture_output=True,
        text=True,
    )
    # Even if the fixture mission's state machine refuses to advance
    # (e.g. no charter, no doctrine), the command MUST exit cleanly with
    # a structured JSON response. The cutover regression we're catching is
    # an ImportError or a hard crash from a missing spec-kitty-runtime
    # dependency.
    assert result.returncode == 0, (
        f"`spec-kitty next` failed in the clean venv. This usually means "
        f"a runtime dependency is missing.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    # Sanity check the payload parses as JSON.
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
