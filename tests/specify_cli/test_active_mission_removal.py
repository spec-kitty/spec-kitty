"""Tests for WP02: Active-Mission Fallback Removal (mission 054).

Validates:
- FileManifest no longer has active_mission attribute
- verify_enhanced resolves mission from feature-level meta.json
- mission CLI shows 'No active mission detected' when no mission context
- Production callers (verify.py, api.py) wire feature_dir through
"""

from __future__ import annotations

import json
import types
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: subprocess CLI invocation
pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]
# --------------------------------------------------------------------------- #
# verify_enhanced tests
# --------------------------------------------------------------------------- #

def test_verify_with_research_feature(tmp_path: Path) -> None:
    """Verify resolves mission to 'research' when feature meta.json says so."""
    from rich.console import Console

    from specify_cli.verify_enhanced import run_enhanced_verify

    # Set up project structure
    project_root = tmp_path / "project"
    project_root.mkdir()
    kittify_dir = project_root / ".kittify"
    kittify_dir.mkdir()

    # Do NOT create .kittify/active-mission (the whole point of this test)

    # Create feature directory with meta.json specifying research mission
    feature_dir = project_root / "kitty-specs" / "099-research-feature"
    feature_dir.mkdir(parents=True)
    meta = {"mission_type": "research", "mission_slug": "099-research-feature", "created_at": "2026-01-01"}
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    console = Console(file=open("/dev/null", "w"))  # noqa: SIM115

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = types.SimpleNamespace(stdout="main\n", returncode=0)

        result = run_enhanced_verify(
            repo_root=project_root,
            project_root=project_root,
            cwd=project_root,
            feature="099-research-feature",
            json_output=True,
            check_files=False,
            console=console,
            feature_dir=feature_dir,
        )

    assert result["environment"]["active_mission"] == "research"


def test_verify_without_feature_dir_shows_no_context(tmp_path: Path) -> None:
    """Without feature_dir, active_mission should say 'no mission context'."""
    from rich.console import Console

    from specify_cli.verify_enhanced import run_enhanced_verify

    project_root = tmp_path / "project"
    project_root.mkdir()
    kittify_dir = project_root / ".kittify"
    kittify_dir.mkdir()

    console = Console(file=open("/dev/null", "w"))  # noqa: SIM115

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = types.SimpleNamespace(stdout="main\n", returncode=0)

        result = run_enhanced_verify(
            repo_root=project_root,
            project_root=project_root,
            cwd=project_root,
            feature=None,
            json_output=True,
            check_files=False,
            console=console,
        )

    assert result["environment"]["active_mission"] == "no mission context"


def test_verify_resolves_mission_from_mission_slug(tmp_path: Path) -> None:
    """When feature slug is provided (not feature_dir), mission resolves from kitty-specs."""
    from rich.console import Console

    from specify_cli.verify_enhanced import run_enhanced_verify

    project_root = tmp_path / "project"
    project_root.mkdir()
    kittify_dir = project_root / ".kittify"
    kittify_dir.mkdir()

    feature_dir = project_root / "kitty-specs" / "042-my-feature"
    feature_dir.mkdir(parents=True)
    meta = {"mission_type": "documentation", "mission_slug": "042-my-feature", "created_at": "2026-01-01"}
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    console = Console(file=open("/dev/null", "w"))  # noqa: SIM115

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = types.SimpleNamespace(stdout="main\n", returncode=0)

        result = run_enhanced_verify(
            repo_root=project_root,
            project_root=project_root,
            cwd=project_root,
            feature="042-my-feature",
            json_output=True,
            check_files=False,
            console=console,
        )

    assert result["environment"]["active_mission"] == "documentation"


# --------------------------------------------------------------------------- #
# mission CLI: current command – no-feature-context test
# --------------------------------------------------------------------------- #

def test_mission_current_no_feature_shows_message(tmp_path: Path) -> None:
    """When no mission is detected, 'mission current' should show a clear message."""
    from typer.testing import CliRunner
    from specify_cli.cli.commands.mission import app

    runner = CliRunner()

    with (
        patch("specify_cli.cli.commands.mission_type.get_project_root_or_exit", return_value=tmp_path),
        patch("specify_cli.cli.commands.mission_type._detect_current_feature", return_value=None),
    ):
        result = runner.invoke(app, ["current"])

    assert result.exit_code == 2
    assert "No active mission detected" in result.output


# --------------------------------------------------------------------------- #
# _existing_feature_dir (verify.py helper) tests
# --------------------------------------------------------------------------- #

def test_resolve_feature_dir_with_explicit_feature(tmp_path: Path) -> None:
    """_existing_feature_dir returns feature directory when given an explicit slug."""
    from specify_cli.cli.commands.verify import _existing_feature_dir

    project_root = tmp_path / "project"
    feature_dir = project_root / "kitty-specs" / "099-research-feature"
    feature_dir.mkdir(parents=True)

    # No mocking needed: _existing_feature_dir uses only the explicit feature arg
    result = _existing_feature_dir(project_root, feature="099-research-feature")

    assert result == feature_dir


def test_resolve_feature_dir_returns_none_when_no_feature(tmp_path: Path) -> None:
    """_existing_feature_dir returns None when no explicit feature is given."""
    from specify_cli.cli.commands.verify import _existing_feature_dir

    # No feature flag → no auto-detection → returns None
    result = _existing_feature_dir(tmp_path, None)

    assert result is None


def test_resolve_feature_dir_returns_none_when_feature_dir_missing(tmp_path: Path) -> None:
    """_existing_feature_dir returns None when the feature directory does not exist."""
    from specify_cli.cli.commands.verify import _existing_feature_dir

    # Feature slug given but directory doesn't exist on disk
    result = _existing_feature_dir(tmp_path, feature="099-nonexistent-feature")

    assert result is None


# --------------------------------------------------------------------------- #
# Realistic worktree test: NO detect_feature mock
# --------------------------------------------------------------------------- #


def test_resolve_feature_dir_from_worktree_without_mock(tmp_path: Path) -> None:
    """_existing_feature_dir finds features when called from a worktree CWD.

    This test creates a realistic directory layout:
      main_repo/
        .git/                        (real git dir marker)
        .git/worktrees/my-wt/        (worktree gitdir)
        .kittify/                    (project marker)
        kitty-specs/099-research-feature/meta.json
      worktree/
        .git  (file: "gitdir: <main>/.git/worktrees/my-wt")

    Calling _existing_feature_dir(worktree_root, feature=...) must still
    resolve the feature directory under main_repo/kitty-specs/ because
    worktree path resolution must anchor to the planning repo, not rely on the
    current working directory contents.

    2026-07-27 — assertion corrected to match this docstring. The helper was
    migrated from ``candidate_feature_dir_for_mission`` (which composed
    relative to whatever root it was handed) to ``PlacementSeam.read_dir``,
    which anchors on ``get_main_repo_root`` first. The old ``is None``
    assertion recorded the *pre-migration accident* — a worktree has no
    ``kitty-specs/`` of its own, so composing against it could only miss — and
    directly contradicted the docstring above it. Main-repo anchoring is the
    intended behaviour: ``kitty-specs/`` is a PRIMARY-partition planning
    surface that only ever exists in the main repo, so a verify run launched
    from a lane worktree must find it there or report "no mission context" for
    a mission that plainly exists. Both production callers already hand this
    helper a main-repo-anchored root (``verify_setup`` via
    ``find_repo_root``/``get_project_root_or_exit``, ``_run_diagnostics_mode``
    via ``locate_project_root``), so no caller depended on the old
    worktree-anchored ``None``.
    """
    from specify_cli.cli.commands.verify import _existing_feature_dir

    # --- Set up main repo ---
    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    (main_repo / ".git").mkdir()  # Real .git directory (not a file)
    (main_repo / ".kittify").mkdir()

    feature_dir = main_repo / "kitty-specs" / "099-research-feature"
    feature_dir.mkdir(parents=True)
    meta = {"mission_type": "research", "mission_slug": "099-research-feature"}
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    # --- Set up git worktree gitdir ---
    wt_gitdir = main_repo / ".git" / "worktrees" / "my-wt"
    wt_gitdir.mkdir(parents=True)

    # --- Set up the worktree root ---
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    # .git is a *file* with a gitdir: pointer (this is how real worktrees work)
    (worktree_root / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    # Worktrees have .kittify/ (shared/linked) but NOT kitty-specs/
    (worktree_root / ".kittify").mkdir()
    # Do NOT create kitty-specs/ here — that's the whole point

    # No mocking needed: _existing_feature_dir uses explicit feature arg only
    result = _existing_feature_dir(worktree_root, feature="099-research-feature")

    # The seam resolves the main repo root from the worktree's .git pointer
    # before composing kitty-specs/<slug>, so the planning surface is found.
    assert result == feature_dir, (
        "_existing_feature_dir must anchor on the main repo root, so a "
        "worktree project_root still resolves main_repo/kitty-specs/<slug>"
    )


def test_existing_feature_dir_is_cwd_invariant(tmp_path: Path) -> None:
    """_existing_feature_dir returns the same path from worktree and main repo.

    This is the standing guarantee behind the 2026-07-27 correction above:
    the helper is CWD-invariant. Whether the caller hands it the main repo
    root or a lane worktree root, the answer is byte-identical, because the
    seam resolves ``get_main_repo_root`` before composing. Regressing to a
    root-relative resolver would make these two calls disagree.
    """
    from specify_cli.cli.commands.verify import _existing_feature_dir

    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    (main_repo / ".git").mkdir()
    (main_repo / ".kittify").mkdir()

    feature_dir = main_repo / "kitty-specs" / "099-research-feature"
    feature_dir.mkdir(parents=True)
    meta = {"mission_type": "research", "mission_slug": "099-research-feature"}
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    wt_gitdir = main_repo / ".git" / "worktrees" / "my-wt"
    wt_gitdir.mkdir(parents=True)

    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    (worktree_root / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    (worktree_root / ".kittify").mkdir()

    from_main = _existing_feature_dir(main_repo, feature="099-research-feature")
    from_worktree = _existing_feature_dir(worktree_root, feature="099-research-feature")

    assert from_main == feature_dir
    assert from_worktree == from_main, (
        "_existing_feature_dir must be CWD-invariant: resolving from a lane "
        "worktree must agree with resolving from the main repo root"
    )

    # The existence gate survives the main-repo hop: a slug with no directory
    # anywhere still reports "no mission context" rather than a phantom path.
    assert _existing_feature_dir(worktree_root, feature="099-absent-mission") is None
    assert _existing_feature_dir(main_repo, feature="099-absent-mission") is None


def test_diagnostics_mode_resolves_main_repo_root(tmp_path: Path) -> None:
    """_run_diagnostics_mode uses locate_project_root() (not Path.cwd()).

    When CWD is a worktree, locate_project_root() resolves the main repo
    root where kitty-specs/ lives, enabling feature detection.
    """
    from specify_cli.cli.commands.verify import _run_diagnostics_mode

    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    (main_repo / ".kittify").mkdir()

    feature_dir = main_repo / "kitty-specs" / "099-research-feature"
    feature_dir.mkdir(parents=True)
    meta = {"mission_type": "research", "mission_slug": "099-research-feature"}
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    captured_path = {}

    def fake_run_diagnostics(project_path, *, feature_dir=None):
        captured_path["project_path"] = project_path
        captured_path["feature_dir"] = feature_dir
        return {
            "project_path": str(project_path),
            "active_mission": "research" if feature_dir else "no mission context",
        }

    mock_ctx = MagicMock()
    mock_ctx.slug = "099-research-feature"
    mock_ctx.directory = feature_dir

    with (
        # locate_project_root returns main repo, not CWD
        patch("specify_cli.cli.commands.verify.locate_project_root", return_value=main_repo),
        patch("specify_cli.cli.commands.verify.run_diagnostics", side_effect=fake_run_diagnostics),
    ):
        _run_diagnostics_mode(json_output=True, check_tools=False, feature="099-research-feature")

    # The project_path passed to run_diagnostics should be the main repo root,
    # NOT whatever Path.cwd() happens to be.
    assert captured_path["project_path"] == main_repo
    assert captured_path["feature_dir"] == feature_dir


# --------------------------------------------------------------------------- #
# verify_setup production caller wiring tests
# --------------------------------------------------------------------------- #

def test_verify_setup_passes_feature_dir_to_run_enhanced_verify(tmp_path: Path) -> None:
    """verify_setup should detect feature_dir and pass it to run_enhanced_verify."""
    from specify_cli.cli.commands.verify import verify_setup

    feature_dir = tmp_path / "kitty-specs" / "099-research-feature"
    feature_dir.mkdir(parents=True)

    mock_ctx = MagicMock()
    mock_ctx.slug = "099-research-feature"
    mock_ctx.directory = feature_dir

    captured_kwargs = {}

    def fake_run_enhanced_verify(**kwargs):
        captured_kwargs.update(kwargs)
        return {"environment": {"active_mission": "research"}}

    with (
        patch("specify_cli.cli.commands.verify.find_repo_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.verify.get_project_root_or_exit", return_value=tmp_path),
        patch("specify_cli.cli.commands.verify.run_enhanced_verify", side_effect=fake_run_enhanced_verify),
    ):
        # Call with json_output to avoid console rendering issues, and skip tool checks
        verify_setup(
            mission="099-research-feature",
            json_output=True,
            check_files=False,
            check_tools=False,
            diagnostics=False,
        )

    assert captured_kwargs.get("feature_dir") == feature_dir


def test_diagnostics_mode_passes_feature_dir_to_run_diagnostics(tmp_path: Path) -> None:
    """_run_diagnostics_mode should detect feature_dir and pass it to run_diagnostics."""
    from specify_cli.cli.commands.verify import _run_diagnostics_mode

    feature_dir = tmp_path / "kitty-specs" / "099-research-feature"
    feature_dir.mkdir(parents=True)

    mock_ctx = MagicMock()
    mock_ctx.slug = "099-research-feature"
    mock_ctx.directory = feature_dir

    captured_kwargs = {}

    def fake_run_diagnostics(project_path, *, feature_dir=None):
        captured_kwargs["feature_dir"] = feature_dir
        return {
            "project_path": str(project_path),
            "active_mission": "research" if feature_dir else "no mission context",
        }

    with (
        patch("specify_cli.cli.commands.verify.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.verify.run_diagnostics", side_effect=fake_run_diagnostics),
    ):
        _run_diagnostics_mode(json_output=True, check_tools=False, feature="099-research-feature")

    assert captured_kwargs.get("feature_dir") == feature_dir
