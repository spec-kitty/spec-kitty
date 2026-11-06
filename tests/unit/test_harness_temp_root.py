"""The run's ``tempfile`` root must sit below the harness's own git ceiling (#7076).

#7022 lists the run's basetemp and the worker's isolated home in
``GIT_CEILING_DIRECTORIES``, and #7056 moved the parent-enumerating root walks in
``src/`` onto that ceiling. The ceiling only governs directories *below* a listed entry,
and ``tempfile``'s default root is the **platform** temp root — above every entry — so
nothing ``tempfile`` creates is bounded by the harness at all. On a shared host whose
platform temp root has gained a stray ``.git`` (this host's did, left by parallel
missions), a test's ``mkdtemp`` directory therefore sits inside a foreign repository:
lock paths resolve into its ``.git``, mission-state repair re-anchors on it and finds
no missions, and "not a repository" probes are never reached.

The harness fix is to point the run's temp root *inside* the basetemp, which is a
ceiling entry and is wiped and reaped with the run. These two tests are the red-first
proof: the first reads the property directly, the second proves the walk verdict
against a hostile host built in the test's own tree, without touching ``/tmp``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from specify_cli.core.paths import locate_project_root
from tests._support.git_ceiling import (
    GIT_CEILING_ENV,
    harness_git_ceilings,
    install_git_ceilings,
)
from tests._support.temp_root import TEMP_ROOT_VARS, install_temp_root

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class _Option:
    """The one ``config.option`` attribute the harness ceiling and the temp root read."""

    def __init__(self, basetemp: str) -> None:
        self.basetemp = basetemp


class _Config:
    """A minimal ``pytest.Config`` stand-in for one harness install."""

    def __init__(self, basetemp: Path) -> None:
        self.option: Any = _Option(str(basetemp))
        self.workerinput: dict[str, str] | None = None


def test_tempfile_root_is_below_the_run_basetemp(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Whatever the suite makes with ``tempfile`` is below the ceiling #7022 installs."""
    basetemp = tmp_path_factory.getbasetemp().resolve()
    root = Path(tempfile.gettempdir()).resolve()

    assert root.is_relative_to(basetemp), (
        f"tempfile root {root} is not below the run basetemp {basetemp}: every directory "
        "made with tempfile escapes the harness GIT_CEILING_DIRECTORIES ceiling (#7076)"
    )

    made = Path(tempfile.mkdtemp())
    try:
        assert made.resolve().is_relative_to(basetemp)
    finally:
        shutil.rmtree(made, ignore_errors=True)


def test_a_tempfile_dir_under_a_hostile_temp_root_resolves_no_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A repository enclosing the temp root cannot capture a ``tempfile`` directory.

    The hostile host is built in this test's own tree — an ambient checkout with a
    ``.git`` directory and a ``.kittify`` marker, and a "run" directory inside it —
    so the assertion holds on a clean host and on a shared one alike.
    """
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)

    ambient = tmp_path / "ambient"
    (ambient / ".git").mkdir(parents=True)
    (ambient / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (ambient / ".kittify").mkdir()
    basetemp = ambient / "run"
    home_base = tmp_path / "home"
    home_base.mkdir()

    # Install the ceiling exactly as pytest_configure does. Setting the variable to ""
    # first (and setting it again for the control) hands the mutation to monkeypatch, so
    # teardown restores the real harness value instead of leaking this test's.
    monkeypatch.setenv(GIT_CEILING_ENV, "")
    install_git_ceilings(harness_git_ceilings(_Config(basetemp), home_base), os.environ)

    # install_temp_root writes the temp-root variables and resets tempfile's cached root in
    # this process; hand both to monkeypatch first so teardown gives the next test on this
    # worker the run's real temp root back instead of this test's (soon deleted) one.
    for variable in TEMP_ROOT_VARS:
        monkeypatch.setenv(variable, os.environ.get(variable, ""))
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    installed = install_temp_root(_Config(basetemp), os.environ)
    assert installed is not None
    assert installed.is_relative_to(basetemp)

    temp_dir = Path(tempfile.mkdtemp())
    try:
        project = temp_dir / "a-test-tree"
        project.mkdir()
        assert locate_project_root(project) is None, "the walk climbed out of the harness temp root into the enclosing repository"

        # Non-vacuity: with no ceiling at all, the same fixture resolves that repository.
        monkeypatch.setenv(GIT_CEILING_ENV, "")
        assert locate_project_root(project) == ambient
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
