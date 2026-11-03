"""Unit tests for the harness temp root (#7076): edges only, no subprocess, no real run."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from tests._support.git_ceiling import GIT_CEILING_ENV
from tests._support.temp_root import (
    TEMP_ROOT_NAME,
    TEMP_ROOT_VARS,
    ensure_temp_root,
    harness_env,
    install_temp_root,
    temp_root_dir,
    temp_root_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class _Option:
    def __init__(self, basetemp: str | None) -> None:
        self.basetemp = basetemp


class _Config:
    """A bare ``pytest.Config`` stand-in: no plugin manager, as a unit test wants."""

    def __init__(self, basetemp: str | None) -> None:
        self.option = _Option(basetemp)


def test_no_basetemp_is_a_no_op(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A run that never resolved a basetemp must not invent an environment."""
    platform_root = str(tmp_path / "platform-temp")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "elsewhere"))
    environ = dict.fromkeys(TEMP_ROOT_VARS, platform_root)

    assert temp_root_for(None) is None
    assert temp_root_for("") is None
    assert temp_root_dir(_Config(None)) is None
    assert install_temp_root(_Config(None), environ) is None

    assert environ == dict.fromkeys(TEMP_ROOT_VARS, platform_root)
    assert tempfile.tempdir == str(tmp_path / "elsewhere")


def test_install_points_every_temp_variable_at_the_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``tempfile`` reads ``TMPDIR`` first; Windows tools read ``TEMP``/``TMP``. All three."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "elsewhere"))
    environ: dict[str, str] = {}

    root = install_temp_root(_Config(str(tmp_path)), environ)

    assert root == tmp_path / TEMP_ROOT_NAME
    assert root is not None and root.is_dir()
    assert environ == {variable: str(root) for variable in TEMP_ROOT_VARS}
    # The stdlib caches the root in a module global; without the reset the new variables
    # are ignored for the rest of the process.
    assert tempfile.tempdir is None


def test_install_overwrites_a_previously_installed_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A second install (another worker, another basetemp) wins, and the directory exists."""
    monkeypatch.setattr(tempfile, "tempdir", None)
    environ: dict[str, str] = {"TMPDIR": str(tmp_path / "platform-temp")}

    first = install_temp_root(_Config(str(tmp_path / "one")), environ)
    second = install_temp_root(_Config(str(tmp_path / "two")), environ)

    assert first != second
    assert environ["TMPDIR"] == str(second)
    assert second is not None and second.is_dir()


def test_ensure_temp_root_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "a" / "b"

    assert ensure_temp_root(root) == root
    assert root.is_dir()
    assert ensure_temp_root(root) == root


def test_harness_env_carries_the_ceiling_and_the_temp_variables(tmp_path: Path) -> None:
    temp_root = str(tmp_path / "run" / "tmp")
    ceiling = os.pathsep.join([str(tmp_path / "run"), str(tmp_path / "home")])
    environ: dict[str, Any] = {
        GIT_CEILING_ENV: ceiling,
        "TMPDIR": temp_root,
        "TEMP": temp_root,
        "TMP": temp_root,
        # Everything below is NOT harness-owned and must not travel to a child.
        "GIT_DIR": str(tmp_path / "elsewhere" / ".git"),
        "GIT_ASKPASS": "/usr/bin/true",
        "HOME": str(tmp_path / "home-dir"),
        "PATH": "/usr/bin",
    }

    carried = harness_env(environ)

    assert carried == {
        GIT_CEILING_ENV: ceiling,
        "TMPDIR": temp_root,
        "TEMP": temp_root,
        "TMP": temp_root,
    }


def test_harness_env_invents_nothing_when_the_harness_owns_nothing() -> None:
    assert harness_env({}) == {}
    assert GIT_CEILING_ENV not in harness_env({"PATH": "/usr/bin"})
