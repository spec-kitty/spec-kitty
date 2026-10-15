"""FR-032 integration: fail-loud uninitialized repo for spec/plan/tasks.

Authority: ``kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/spec.md``
section FR-032 and ``research.md`` D14.

The ``specify`` / ``plan`` / ``tasks`` commands must never silently fall
back to a parent or sibling initialized repository when the cwd is not
itself a Spec Kitty project. Symmetric with FR-005's no-silent-fallback
selector stance.

This test exercises :func:`specify_cli.workspace.assert_initialized` --
the helper the three commands call before any side effects -- to assert
the contract end-to-end without spinning up the full Typer app, which is
expensive and orthogonal to the gate.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from specify_cli.workspace.assert_initialized import (
    SpecKittyNotInitialized,
    assert_initialized,
)


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

def _git_init(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-q"],
        cwd=path,
        check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t"},
    )


def test_uninitialized_dir_raises_with_resolved_root(tmp_path: Path) -> None:
    """No ``.kittify`` and no ``kitty-specs/``: gate must fail loud."""
    _git_init(tmp_path)

    with pytest.raises(SpecKittyNotInitialized) as excinfo:
        assert_initialized(tmp_path)

    assert excinfo.value.root == tmp_path.resolve()
    rendered = str(excinfo.value)
    # Actionable message names the resolved root and the missing markers.
    assert "SPEC_KITTY_REPO_NOT_INITIALIZED" in rendered
    assert str(tmp_path.resolve()) in rendered
    assert "kitty-specs" in rendered
    assert "config.yaml" in rendered


def test_initialized_dir_returns_root(tmp_path: Path) -> None:
    """Both markers present: gate is a no-op and returns the root."""
    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("agents:\n  available: []\n")
    (tmp_path / "kitty-specs").mkdir()

    resolved = assert_initialized(tmp_path)

    assert resolved == tmp_path.resolve()


def test_partial_init_missing_specs_dir_fails_when_specs_required(tmp_path: Path) -> None:
    """Only ``.kittify/config.yaml``: plan/tasks-style guards still fail."""
    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("agents:\n  available: []\n")

    with pytest.raises(SpecKittyNotInitialized) as excinfo:
        assert_initialized(tmp_path)

    assert any("kitty-specs" in str(p) for p in excinfo.value.missing)


def test_partial_init_missing_specs_dir_allowed_for_first_specify(tmp_path: Path) -> None:
    """Only ``.kittify/config.yaml`` is enough for specify to create kitty-specs."""
    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("agents:\n  available: []\n")

    assert assert_initialized(tmp_path, require_specs=False) == tmp_path.resolve()


def test_partial_init_missing_config(tmp_path: Path) -> None:
    """Only ``kitty-specs/``: still uninitialized."""
    _git_init(tmp_path)
    (tmp_path / "kitty-specs").mkdir()

    with pytest.raises(SpecKittyNotInitialized) as excinfo:
        assert_initialized(tmp_path)

    assert any("config.yaml" in str(p) for p in excinfo.value.missing)


def test_no_git_repo_at_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``cwd``-driven path: a non-git temp tree fails fast.

    This is the primary defense for FR-032: an operator running
    ``spec-kitty specify`` from ``/tmp`` (a directory that is not a
    spec-kitty project and has no enclosing one) gets a structured
    error instead of a silent write to a parent project.
    """
    # Walk all the way to a non-git dir. tmp_path itself is sufficient.
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SpecKittyNotInitialized) as excinfo:
        assert_initialized()

    rendered = str(excinfo.value)
    assert "config.yaml" in rendered
    assert "kitty-specs" in rendered


def test_no_silent_fallback_to_parent_repo(tmp_path: Path) -> None:
    """An initialized parent must NOT rescue an uninitialized child cwd.

    The contract is "no silent fallback": a sibling-initialized repo
    above us in the filesystem cannot be claimed as our project root.
    We pin this by asserting that ``assert_initialized(child)`` raises
    even though ``parent`` carries a valid Spec Kitty layout.
    """
    parent = tmp_path / "parent_repo"
    parent.mkdir()
    _git_init(parent)
    (parent / ".kittify").mkdir()
    (parent / ".kittify" / "config.yaml").write_text("agents:\n  available: []\n")
    (parent / "kitty-specs").mkdir()

    # Initialized parent is fine.
    assert assert_initialized(parent) == parent.resolve()

    # Child sub-directory is not itself initialized; gate must fail.
    child = parent / "subdir_no_kitty"
    child.mkdir()
    with pytest.raises(SpecKittyNotInitialized):
        assert_initialized(child)
