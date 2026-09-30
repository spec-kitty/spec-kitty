"""Tests for context validation and location-aware command guards.

Verifies Phase 3 implementation:
- Context detection (main repo vs worktree)
- Location-based command guards (@require_main_repo, @require_worktree)
- Clear error messages for location mismatches
- Environment variable support
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.core.context_validation import (
    CurrentContext,
    ExecutionContext,
    detect_execution_context,
    format_location_error,
    get_context_env_vars,
    get_current_context,
    require_main_repo,
    require_worktree,
    set_context_env_vars,
)

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: repo_root detection returns /tmp in mutmut's forked sandbox CWD,
#         which breaks the "not a worktree" negative assertion. Structural
#         sandbox incompatibility; not a regression of production behaviour.
pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a deterministic git command for real-worktree ownership tests."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _real_primary_and_linked_checkout(tmp_path: Path, *, under_dot_worktrees: bool) -> tuple[Path, Path]:
    """Create a primary checkout and a registered linked checkout."""
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-b", "main")
    _git(primary, "config", "user.email", "spec-kitty-tests@example.invalid")
    _git(primary, "config", "user.name", "Spec Kitty Tests")
    (primary / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    _git(primary, "add", "tracked.txt")
    _git(primary, "commit", "-m", "baseline")

    linked = primary / ".worktrees" / "owned-lane" if under_dot_worktrees else tmp_path / "generic-linked"
    linked.parent.mkdir(parents=True, exist_ok=True)
    _git(primary, "worktree", "add", "-b", "owned-lane", str(linked), "HEAD")
    return primary.resolve(), linked.resolve()


def _write_owned_mission(linked: Path, *, slug: str = "owned-mission", target_branch: str = "owned-lane") -> None:
    """Commit a valid single_branch mission into the linked checkout (the validator reads it)."""
    mission_dir = linked / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M3WP19000000000000000001",
                "mission_slug": slug,
                "slug": slug,
                "mission_type": "software-dev",
                "topology": "single_branch",
                "target_branch": target_branch,
            }
        ),
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    _git(linked, "add", "-A")
    _git(linked, "commit", "-m", "owned mission")


def _capture_next_query_root(monkeypatch: pytest.MonkeyPatch, primary: Path) -> list[Path]:
    """Patch mutation-free next internals and capture the root the runtime would be handed.

    For an owned run that is ``owned.owned_root`` (the fact), otherwise the ambient root.
    """
    from specify_cli.cli.commands import next_cmd

    captured: list[Path] = []
    monkeypatch.setattr(next_cmd, "locate_project_root", lambda: primary)
    monkeypatch.setattr(next_cmd, "_maybe_emit_runtime_notice", lambda *_: None)
    monkeypatch.setattr(next_cmd, "_run_charter_preflight_for_next", lambda *_a, **_k: None)
    monkeypatch.setattr(
        next_cmd,
        "_resolve_mission_slug",
        lambda mission, _root, *, owned=None: owned.mission_slug if owned is not None else mission,
    )
    monkeypatch.setattr(next_cmd, "_validate_result_and_answer", lambda *_a, **_k: None)
    monkeypatch.setattr(next_cmd, "_maybe_handle_answer", lambda *_a, **_k: None)
    monkeypatch.setattr(
        next_cmd,
        "_run_query_mode",
        lambda _agent, _mission, repo_root, *_a, owned=None: captured.append(owned.owned_root if owned is not None else repo_root),
    )
    return captured


def test_next_cli_accepts_explicit_owned_checkout_option(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The stable CLI surface must parse the explicit ownership affordance."""
    from specify_cli import app as main_app

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        main_app,
        [
            "next",
            "--mission",
            "owned-mission",
            "--owned-checkout",
            str(tmp_path),
            "--json",
        ],
    )

    assert result.exit_code != 2, result.output
    assert "No such option" not in result.output


@pytest.mark.real_worktree_detection
def test_next_explicit_owned_checkout_bypasses_literal_guard_and_routes_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validated opt-in routes next state to an owned `.worktrees` checkout."""
    from specify_cli.cli.commands import next_cmd

    primary, linked = _real_primary_and_linked_checkout(tmp_path, under_dot_worktrees=True)
    _write_owned_mission(linked)
    captured = _capture_next_query_root(monkeypatch, primary)
    monkeypatch.chdir(linked)

    next_cmd.next_step(
        mission="owned-mission",
        json_output=True,
        owned_checkout=linked,
    )

    assert captured == [linked]
    assert captured[0] != primary


@pytest.mark.real_worktree_detection
def test_next_generic_linked_checkout_without_opt_in_keeps_primary_routing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pre-existing generic-linked ambient-to-primary behavior is unchanged."""
    from specify_cli.cli.commands import next_cmd

    primary, linked = _real_primary_and_linked_checkout(tmp_path, under_dot_worktrees=False)
    captured = _capture_next_query_root(monkeypatch, primary)
    monkeypatch.chdir(linked)

    next_cmd.next_step(mission="legacy-mission", json_output=True)

    assert captured == [primary]


@pytest.mark.real_worktree_detection
def test_next_literal_worktree_without_opt_in_remains_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No flag leaves the historical `.worktrees` guard fully intact."""
    from specify_cli.cli.commands import next_cmd

    primary, linked = _real_primary_and_linked_checkout(tmp_path, under_dot_worktrees=True)
    captured = _capture_next_query_root(monkeypatch, primary)
    monkeypatch.chdir(linked)

    with pytest.raises(typer.Exit) as exc_info:
        next_cmd.next_step(mission="legacy-mission", json_output=True)

    assert exc_info.value.exit_code == 1
    assert captured == []


@pytest.mark.real_worktree_detection
def test_next_explicit_checkout_subdirectory_is_refused_before_routing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit scope must name a checkout root, never its subdirectory."""
    from specify_cli.cli.commands import next_cmd

    primary, linked = _real_primary_and_linked_checkout(tmp_path, under_dot_worktrees=True)
    nested = linked / "src"
    nested.mkdir()
    captured = _capture_next_query_root(monkeypatch, primary)
    monkeypatch.chdir(linked)

    with pytest.raises(typer.Exit) as exc_info:
        next_cmd.next_step(
            mission="owned-mission",
            json_output=True,
            owned_checkout=nested,
        )

    assert exc_info.value.exit_code == 1
    assert captured == []


@pytest.mark.real_worktree_detection
def test_owned_checkout_keeps_status_lock_in_shared_git_common_dir(
    tmp_path: Path,
) -> None:
    """Per-checkout state routing must not relocate the shared status lock."""
    from specify_cli.status.locking import feature_status_lock_path

    primary, linked = _real_primary_and_linked_checkout(tmp_path, under_dot_worktrees=True)

    assert feature_status_lock_path(linked, "owned-mission") == feature_status_lock_path(primary, "owned-mission")


def _hide_ambient_repo_markers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Hide .kittify/.git markers above tmp_path for negative detection tests."""
    original_exists = Path.exists

    def exists(path: Path) -> bool:
        if path.name in {".kittify", ".git"} and not path.parent.is_relative_to(tmp_path):
            return False
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", exists)


class TestContextDetection:
    """Tests for context detection logic."""

    def test_detect_main_repo_with_kittify(self, tmp_path: Path):
        """Test detection when in main repo with .kittify directory."""
        # Create .kittify to mark main repo
        kittify = tmp_path / ".kittify"
        kittify.mkdir()

        ctx = detect_execution_context(cwd=tmp_path)

        assert ctx.location == ExecutionContext.MAIN_REPO
        assert ctx.cwd == tmp_path
        assert ctx.repo_root == tmp_path
        assert ctx.worktree_name is None
        assert ctx.worktree_path is None

    def test_detect_main_repo_with_git(self, tmp_path: Path):
        """Test detection when in main repo with .git directory."""
        # Create .git to mark main repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        ctx = detect_execution_context(cwd=tmp_path)

        assert ctx.location == ExecutionContext.MAIN_REPO
        assert ctx.repo_root == tmp_path

    def test_detect_worktree_root(self, tmp_path: Path):
        """Test detection when in worktree root directory."""
        # Create worktree structure
        (tmp_path / ".kittify").mkdir()
        worktree_path = tmp_path / ".worktrees" / "010-feature-lane-b"
        worktree_path.mkdir(parents=True)

        ctx = detect_execution_context(cwd=worktree_path)

        assert ctx.location == ExecutionContext.WORKTREE
        assert ctx.cwd == worktree_path
        assert ctx.repo_root == tmp_path
        assert ctx.worktree_name == "010-feature-lane-b"
        assert ctx.worktree_path == worktree_path

    def test_detect_worktree_subdirectory(self, tmp_path: Path):
        """Test detection when in subdirectory of worktree."""
        # Create worktree with subdirectory
        (tmp_path / ".kittify").mkdir()
        worktree_path = tmp_path / ".worktrees" / "010-feature-lane-b"
        subdir = worktree_path / "src" / "components"
        subdir.mkdir(parents=True)

        ctx = detect_execution_context(cwd=subdir)

        assert ctx.location == ExecutionContext.WORKTREE
        assert ctx.cwd == subdir
        assert ctx.repo_root == tmp_path
        assert ctx.worktree_name == "010-feature-lane-b"
        assert ctx.worktree_path == worktree_path

    def test_detect_nested_worktree_path(self, tmp_path: Path):
        """Test detection prevents nested worktree confusion."""
        # Create nested structure (should not happen, but test detection)
        (tmp_path / ".kittify").mkdir()
        outer_worktree = tmp_path / ".worktrees" / "010-feature-lane-a"
        # This would be a nested worktree (invalid)
        nested_path = outer_worktree / ".worktrees" / "010-feature-lane-b"
        nested_path.mkdir(parents=True)

        ctx = detect_execution_context(cwd=nested_path)

        # Should detect as worktree (first .worktrees in path)
        assert ctx.location == ExecutionContext.WORKTREE
        # Should use first .worktrees found
        assert ctx.worktree_name == "010-feature-lane-a"

    def test_get_current_context(self, tmp_path: Path, monkeypatch):
        """Test get_current_context uses current working directory."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()

        monkeypatch.chdir(tmp_path)

        ctx = get_current_context()

        assert ctx.location == ExecutionContext.MAIN_REPO
        assert ctx.cwd == tmp_path

    def test_detect_false_positive_worktree(self, tmp_path: Path, monkeypatch):
        """Directory named .worktrees outside project root should not false-positive."""
        _hide_ambient_repo_markers(monkeypatch, tmp_path)
        fake_worktree = tmp_path / ".worktrees" / "not-a-worktree"
        fake_worktree.mkdir(parents=True)

        ctx = detect_execution_context(cwd=fake_worktree)

        assert ctx.location == ExecutionContext.MAIN_REPO
        assert ctx.repo_root is None


@pytest.mark.real_worktree_detection
class TestRequireMainRepo:
    """Tests for @require_main_repo decorator."""

    def test_allows_execution_from_main_repo(self, tmp_path: Path, monkeypatch):
        """Test decorator allows execution from main repo."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        monkeypatch.chdir(tmp_path)

        @require_main_repo
        def test_command():
            return "success"

        result = test_command()
        assert result == "success"

    def test_blocks_execution_from_worktree(self, tmp_path: Path, monkeypatch):
        """Test decorator blocks execution from worktree."""
        (tmp_path / ".kittify").mkdir()
        worktree_path = tmp_path / ".worktrees" / "010-feature-lane-b"
        worktree_path.mkdir(parents=True)
        monkeypatch.chdir(worktree_path)

        @require_main_repo
        def test_command():
            return "success"

        with pytest.raises(typer.Exit) as exc_info:
            test_command()

        assert exc_info.value.exit_code == 1


@pytest.mark.real_worktree_detection
class TestRequireWorktree:
    """Tests for @require_worktree decorator."""

    def test_allows_execution_from_worktree(self, tmp_path: Path, monkeypatch):
        """Test decorator allows execution from worktree."""
        (tmp_path / ".kittify").mkdir()
        worktree_path = tmp_path / ".worktrees" / "010-feature-lane-b"
        worktree_path.mkdir(parents=True)
        monkeypatch.chdir(worktree_path)

        @require_worktree
        def test_command():
            return "success"

        result = test_command()
        assert result == "success"

    def test_blocks_execution_from_main_repo(self, tmp_path: Path, monkeypatch):
        """Test decorator blocks execution from main repo."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        monkeypatch.chdir(tmp_path)

        @require_worktree
        def test_command():
            return "success"

        with pytest.raises(typer.Exit) as exc_info:
            test_command()

        assert exc_info.value.exit_code == 1


class TestLocationErrorMessages:
    """Tests for error message formatting."""

    def test_format_error_main_required_from_worktree(self, tmp_path: Path):
        """Test error message for command needing main repo, run from worktree."""
        ctx = CurrentContext(
            location=ExecutionContext.WORKTREE,
            cwd=tmp_path / ".worktrees" / "010-feature-lane-b",
            repo_root=tmp_path,
            worktree_name="010-feature-lane-b",
            worktree_path=tmp_path / ".worktrees" / "010-feature-lane-b",
        )

        error_msg = format_location_error(
            required=ExecutionContext.MAIN_REPO,
            actual=ExecutionContext.WORKTREE,
            command_name="implement",
            current_ctx=ctx,
        )

        assert "implement" in error_msg
        assert "main repository" in error_msg
        assert "010-feature-lane-b" in error_msg
        assert f"cd {tmp_path}" in error_msg


class TestEnvVarBypass:
    """Tests for env var bypass prevention."""

    def test_filesystem_overrides_env(self, mock_worktree, monkeypatch):
        """Filesystem detection should override SPEC_KITTY_CONTEXT env var."""
        monkeypatch.setenv("SPEC_KITTY_CONTEXT", "main")

        context = detect_execution_context(cwd=mock_worktree["worktree_path"])
        assert context.location == ExecutionContext.WORKTREE

    def test_format_error_worktree_required_from_main(self, tmp_path: Path):
        """Test error message for command needing worktree, run from main repo."""
        ctx = CurrentContext(
            location=ExecutionContext.MAIN_REPO,
            cwd=tmp_path,
            repo_root=tmp_path,
            worktree_name=None,
            worktree_path=None,
        )

        error_msg = format_location_error(
            required=ExecutionContext.WORKTREE,
            actual=ExecutionContext.MAIN_REPO,
            command_name="workspace_status",
            current_ctx=ctx,
        )

        assert "workspace_status" in error_msg
        assert "worktree" in error_msg
        assert ".worktrees" in error_msg


class TestEnvironmentVariables:
    """Tests for context environment variable support."""

    _CONTEXT_ENV_VARS = (
        "SPEC_KITTY_CONTEXT",
        "SPEC_KITTY_CWD",
        "SPEC_KITTY_REPO_ROOT",
        "SPEC_KITTY_WORKTREE_NAME",
        "SPEC_KITTY_WORKTREE_PATH",
    )

    @pytest.fixture(autouse=True)
    def _isolate_context_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T031 (WP06 fix-before-wiring, FR-015): ``set_context_env_vars``
        mutates ``os.environ`` directly with no built-in restore, so a test
        below that calls it leaves ``SPEC_KITTY_CONTEXT``/``CWD``/
        ``REPO_ROOT``/``WORKTREE_NAME``/``WORKTREE_PATH`` set for whatever
        test runs next in this worker -- order-dependent on shard split.
        ``monkeypatch.delenv(raising=False)`` records each key's pre-test
        state (present or absent) and restores exactly that at teardown,
        regardless of what the test under it set or removed.
        """
        for var in self._CONTEXT_ENV_VARS:
            monkeypatch.delenv(var, raising=False)

    def test_set_context_env_vars_main_repo(self, tmp_path: Path):
        """Test setting environment variables for main repo context."""
        ctx = CurrentContext(
            location=ExecutionContext.MAIN_REPO,
            cwd=tmp_path,
            repo_root=tmp_path,
            worktree_name=None,
            worktree_path=None,
        )

        set_context_env_vars(ctx)

        import os

        assert os.environ["SPEC_KITTY_CONTEXT"] == "main"
        assert os.environ["SPEC_KITTY_CWD"] == str(tmp_path)
        assert os.environ["SPEC_KITTY_REPO_ROOT"] == str(tmp_path)
        assert "SPEC_KITTY_WORKTREE_NAME" not in os.environ
        assert "SPEC_KITTY_WORKTREE_PATH" not in os.environ

    def test_set_context_env_vars_worktree(self, tmp_path: Path):
        """Test setting environment variables for worktree context."""
        worktree_path = tmp_path / ".worktrees" / "010-feature-lane-b"

        ctx = CurrentContext(
            location=ExecutionContext.WORKTREE,
            cwd=worktree_path,
            repo_root=tmp_path,
            worktree_name="010-feature-lane-b",
            worktree_path=worktree_path,
        )

        set_context_env_vars(ctx)

        import os

        assert os.environ["SPEC_KITTY_CONTEXT"] == "worktree"
        assert os.environ["SPEC_KITTY_WORKTREE_NAME"] == "010-feature-lane-b"
        assert os.environ["SPEC_KITTY_WORKTREE_PATH"] == str(worktree_path)

    def test_get_context_env_vars(self, tmp_path: Path):
        """Test getting context environment variables."""
        ctx = CurrentContext(
            location=ExecutionContext.WORKTREE,
            cwd=tmp_path / ".worktrees" / "010-feature-lane-b",
            repo_root=tmp_path,
            worktree_name="010-feature-lane-b",
            worktree_path=tmp_path / ".worktrees" / "010-feature-lane-b",
        )

        set_context_env_vars(ctx)
        env_vars = get_context_env_vars()

        assert env_vars["SPEC_KITTY_CONTEXT"] == "worktree"
        assert env_vars["SPEC_KITTY_WORKTREE_NAME"] == "010-feature-lane-b"

    def test_env_vars_cleared_when_switching_context(self, tmp_path: Path):
        """Test environment variables are cleared when switching from worktree to main."""
        # Set worktree context
        worktree_ctx = CurrentContext(
            location=ExecutionContext.WORKTREE,
            cwd=tmp_path / ".worktrees" / "010-feature-lane-b",
            repo_root=tmp_path,
            worktree_name="010-feature-lane-b",
            worktree_path=tmp_path / ".worktrees" / "010-feature-lane-b",
        )
        set_context_env_vars(worktree_ctx)

        # Switch to main repo context
        main_ctx = CurrentContext(
            location=ExecutionContext.MAIN_REPO,
            cwd=tmp_path,
            repo_root=tmp_path,
            worktree_name=None,
            worktree_path=None,
        )
        set_context_env_vars(main_ctx)

        import os

        # Worktree-specific vars should be removed
        assert "SPEC_KITTY_WORKTREE_NAME" not in os.environ
        assert "SPEC_KITTY_WORKTREE_PATH" not in os.environ

    def test_no_context_env_vars_leak_out_of_this_class(self) -> None:
        """T031 red-first (FR-015 fix-before-wiring): order-independence proof.

        Every test above calls ``set_context_env_vars`` (production code,
        ``core/context_validation.py``), which mutates ``os.environ`` directly
        with no test-side restore. Placed last in the class (pytest runs a
        class's methods in declaration order), this asserts a clean
        ``SPEC_KITTY_CONTEXT``/``CWD``/``REPO_ROOT`` slate is observed by
        whatever runs next -- on base this is RED (the prior tests' mutations
        survive past their own scope, an order-dependent leak invisible to
        ``make test-fast`` but exposed under any shard split that runs this
        class before something depending on ambient env cleanliness).
        """
        import os

        assert "SPEC_KITTY_CONTEXT" not in os.environ
        assert "SPEC_KITTY_CWD" not in os.environ
        assert "SPEC_KITTY_REPO_ROOT" not in os.environ
        assert "SPEC_KITTY_WORKTREE_NAME" not in os.environ
        assert "SPEC_KITTY_WORKTREE_PATH" not in os.environ


@pytest.mark.real_worktree_detection
class TestWorktreeNestingPrevention:
    """Critical tests for worktree nesting prevention."""

    def test_implement_blocked_from_worktree(self, tmp_path: Path, monkeypatch):
        """CRITICAL: Test that implement command is blocked from worktree.

        This prevents nested worktrees which corrupt git state.
        """
        (tmp_path / ".kittify").mkdir()
        # Setup worktree
        worktree_path = tmp_path / ".worktrees" / "010-feature-lane-b"
        worktree_path.mkdir(parents=True)
        monkeypatch.chdir(worktree_path)

        # Import implement command (which has @require_main_repo decorator)
        from specify_cli.cli.commands.implement import implement

        # Should be blocked with clear error
        with pytest.raises(typer.Exit) as exc_info:
            implement(wp_id="WP03")

        assert exc_info.value.exit_code == 1

    def test_merge_blocked_from_worktree(self, tmp_path: Path, monkeypatch):
        """Test that merge command is blocked from worktree."""
        (tmp_path / ".kittify").mkdir()
        worktree_path = tmp_path / ".worktrees" / "010-feature-lane-b"
        worktree_path.mkdir(parents=True)
        monkeypatch.chdir(worktree_path)

        from specify_cli.cli.commands.consolidate import consolidate as merge

        with pytest.raises(typer.Exit) as exc_info:
            merge()

        assert exc_info.value.exit_code == 1

    def test_nested_worktree_detection(self, tmp_path: Path):
        """Test detection of nested worktree paths (edge case)."""
        # Create what would be a nested worktree (invalid scenario)
        (tmp_path / ".kittify").mkdir()
        outer_worktree = tmp_path / ".worktrees" / "010-feature-lane-a"
        nested_worktrees = outer_worktree / ".worktrees"
        nested_workspace = nested_worktrees / "010-feature-lane-b"
        nested_workspace.mkdir(parents=True)

        ctx = detect_execution_context(cwd=nested_workspace)

        # Should detect as worktree (first .worktrees in path)
        assert ctx.location == ExecutionContext.WORKTREE
        # This prevents trying to create another worktree
        assert ctx.worktree_name == "010-feature-lane-a"


class TestEdgeCases:
    """Tests for edge cases in context detection."""

    def test_detect_without_repo_markers(self, tmp_path: Path, monkeypatch):
        """Test detection when no .kittify or .git found."""
        _hide_ambient_repo_markers(monkeypatch, tmp_path)
        # Empty directory
        empty_dir = tmp_path / "no-repo"
        empty_dir.mkdir()

        ctx = detect_execution_context(cwd=empty_dir)

        # Should still detect as main repo (default)
        assert ctx.location == ExecutionContext.MAIN_REPO
        # But repo_root will be None
        assert ctx.repo_root is None

    def test_detect_from_deep_subdirectory(self, tmp_path: Path):
        """Test detection from deep subdirectory in main repo."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()

        deep_dir = tmp_path / "src" / "specify_cli" / "cli" / "commands"
        deep_dir.mkdir(parents=True)

        ctx = detect_execution_context(cwd=deep_dir)

        assert ctx.location == ExecutionContext.MAIN_REPO
        assert ctx.repo_root == tmp_path

    def test_worktree_name_with_hyphens(self, tmp_path: Path):
        """Test worktree detection with complex names."""
        (tmp_path / ".kittify").mkdir()
        worktree_path = tmp_path / ".worktrees" / "010-sequential-lane-h"
        worktree_path.mkdir(parents=True)

        ctx = detect_execution_context(cwd=worktree_path)

        assert ctx.location == ExecutionContext.WORKTREE
        assert ctx.worktree_name == "010-sequential-lane-h"
