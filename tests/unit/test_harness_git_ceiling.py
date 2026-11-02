"""The test run's own temp roots are a git ceiling (#7022, #5356).

Many fixtures build a project in ``tmp_path`` without ``git init`` and rely on
it being outside every repository. When the platform temp root itself sits
inside a git work tree (an agent sandbox that puts ``TMPDIR`` under a
checkout, a ``/tmp`` someone ran ``git init`` in), git discovery walks up from
``tmp_path`` into that foreign repository: lock paths land in its ``.git``,
mission-state repair finds no missions, the non-repository git probe is never
reached. ``make test-fast`` went red on such hosts while CI stayed green.

The harness therefore installs ``GIT_CEILING_DIRECTORIES`` for the roots it
owns, so discovery from inside them never climbs above them. Pure-logic limbs
are ``fast``; the nested pytest run that proves the wiring end to end, with the
temp root planted inside a real outer repository, carries ``integration``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.core.paths import WorkspaceRootNotFound, locate_project_root, resolve_canonical_root
from tests._support.git_ceiling import GIT_CEILING_ENV, harness_git_ceilings, install_git_ceilings
from tests.utils import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PROBE_ENV = "SPEC_KITTY_GIT_CEILING_PROBE"


def _config(basetemp: str | None) -> SimpleNamespace:
    return SimpleNamespace(option=SimpleNamespace(basetemp=basetemp))


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------


def test_ceilings_are_the_basetemp_and_the_home_base(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ceilings = harness_git_ceilings(_config(str(tmp_path / "run-1")), home)
    assert ceilings == [(tmp_path / "run-1").resolve(), home.resolve()]


def test_no_basetemp_yields_only_the_home_base(tmp_path: Path) -> None:
    assert harness_git_ceilings(_config(None), tmp_path) == [tmp_path.resolve()]


def test_install_sets_the_variable_when_absent(tmp_path: Path) -> None:
    environ: dict[str, str] = {}
    install_git_ceilings([tmp_path], environ)
    assert environ[GIT_CEILING_ENV] == str(tmp_path)


def test_install_keeps_an_existing_value_verbatim_and_appends(tmp_path: Path) -> None:
    # A leading empty entry is meaningful to git (later entries skip realpath), so
    # the existing value is never re-parsed or normalised -- only appended to.
    environ = {GIT_CEILING_ENV: f"{os.pathsep}/elsewhere"}
    install_git_ceilings([tmp_path], environ)
    assert environ[GIT_CEILING_ENV] == f"{os.pathsep}/elsewhere{os.pathsep}{tmp_path}"


def test_install_is_idempotent(tmp_path: Path) -> None:
    environ: dict[str, str] = {}
    install_git_ceilings([tmp_path, tmp_path], environ)
    install_git_ceilings([tmp_path], environ)
    assert environ[GIT_CEILING_ENV] == str(tmp_path)


def test_this_session_has_its_basetemp_as_a_ceiling(tmp_path_factory: pytest.TempPathFactory) -> None:
    """The conftest wiring, observed in-process: the live basetemp itself is listed.

    Exact membership, not "some ancestor is listed": a developer who already
    exports a broad ceiling must not mask a removed conftest call. Under xdist
    the worker's basetemp is ``<run basetemp>/popen-gwN``, so its parent counts.
    """
    basetemp = tmp_path_factory.getbasetemp().resolve()
    listed = {Path(part).resolve() for part in os.environ.get(GIT_CEILING_ENV, "").split(os.pathsep) if part}
    assert basetemp in listed or basetemp.parent in listed, listed


# ---------------------------------------------------------------------------
# End-to-end wiring: a real nested pytest run whose temp root is inside a repo
# ---------------------------------------------------------------------------


def test_inner_tmp_path_is_outside_every_repository(tmp_path: Path) -> None:
    """Runs only as the inner probe spawned by the integration test below."""
    if not os.environ.get(_PROBE_ENV):
        pytest.skip("inner probe of test_tmp_path_under_an_enclosing_repo_is_not_inside_it")
    # Non-vacuity: the temp root really is inside a git work tree, so without the
    # ceiling git would find it.
    temproot = Path(os.environ["PYTEST_DEBUG_TEMPROOT"])
    outer = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=temproot,
        capture_output=True,
        text=True,
        check=False,
        env={k: v for k, v in os.environ.items() if k != GIT_CEILING_ENV},
    )
    assert outer.returncode == 0, outer.stderr
    probe = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode != 0, f"tmp_path resolved into an enclosing repository: {probe.stdout}"
    # The Python root walks the status lock and project detection use agree.
    assert locate_project_root(tmp_path) is None
    with pytest.raises(WorkspaceRootNotFound):
        resolve_canonical_root(tmp_path)


@pytest.mark.integration
def test_tmp_path_under_an_enclosing_repo_is_not_inside_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The #7022 host shape: the platform temp root lives inside a git work tree."""
    if os.environ.get(_PROBE_ENV):
        pytest.skip("the inner probe must not recurse")
    outer = tmp_path / "outer-repo"
    outer.mkdir()
    subprocess.run(["git", "init", "-q", str(outer)], check=True)
    scratch = outer / "tmp"
    scratch.mkdir()
    monkeypatch.setenv("PYTEST_DEBUG_TEMPROOT", str(scratch))
    monkeypatch.setenv(_PROBE_ENV, "1")
    # The inner run must start from a clean slate: the outer session's own
    # ceiling would otherwise hide the defect this test exists to catch.
    monkeypatch.delenv(GIT_CEILING_ENV, raising=False)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(Path(__file__).resolve()),
            "-k",
            "inner",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:randomly",
            "-n0",
            "--tb=short",
            "-q",
        ],
        cwd=REPO_ROOT,
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "1 passed" in output, output
