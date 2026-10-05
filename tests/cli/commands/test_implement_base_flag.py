"""Tests for FR-021: implement --base <ref> flag.

Verifies:
- Valid ref creates lane workspace branching from the given ref.
- Invalid ref fails with the documented error message (no fallback).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from specify_cli.cli.commands.implement import _validate_base_ref
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_git_repo(path: Path) -> None:
    """Create a minimal git repo with an initial commit on 'main'."""
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "branch", "-M", "main"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


# A real 26-char ULID (Crockford base32), the shape mission_id has in production.
MISSION_ID = "01KQHRB8GCFJAX7HM4ZY52AQGR"


def _setup_feature(repo: Path, mission_slug: str = "068-test") -> Path:
    """Set up a minimal feature with one WP.

    Seeds a ``genesis -> planned`` bootstrap event for WP06 so that the
    implement command's genesis gate (T012, Contract 3) treats the WP as
    having been through ``finalize-tasks``.  Without this seed the gate
    raises before ``create_lane_workspace`` is reached.
    """
    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True, exist_ok=True)

    manifest = LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=MISSION_ID,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP06",),
                write_scope=("src/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-04-07T10:00:00+00:00",
        computed_from="test",
    )
    write_lanes_json(feature_dir, manifest)

    meta = {
        "mission_id": MISSION_ID,
        "mission_slug": mission_slug,
        "vcs": "git",
        "target_branch": "main",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / "WP06-task.md").write_text("---\nwork_package_id: WP06\ndependencies: []\n---\n# WP06\n")

    # Seed the bootstrap event that finalize-tasks would write.
    # The implement genesis gate (T012) reads the event log directly and
    # rejects WPs with no lane-state events (genesis state).  A single
    # genesis -> planned event is the minimal required seed.
    seed_event = {
        "actor": "finalize-tasks",
        "at": "2026-04-07T10:00:00.000000+00:00",
        "event_id": "01JT00000000000000000WP06",
        "evidence": None,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "genesis",
        "mission_id": MISSION_ID,
        "mission_slug": mission_slug,
        "policy_metadata": None,
        "reason": "canonical bootstrap",
        "review_ref": None,
        "to_lane": "planned",
        "wp_id": "WP06",
    }
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(seed_event, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    (repo / ".kittify" / "workspaces").mkdir(parents=True, exist_ok=True)

    return feature_dir


# ---------------------------------------------------------------------------
# Unit tests for _validate_base_ref
# ---------------------------------------------------------------------------


class TestValidateBaseRef:
    """Tests for the _validate_base_ref helper (called by implement --base)."""

    def test_valid_ref_returns_sha(self, tmp_path: Path) -> None:
        """A valid ref (e.g., 'main') should resolve successfully."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        sha = _validate_base_ref(repo, "main")
        assert len(sha) == 40, f"Expected full SHA, got: {sha!r}"
        assert all(c in "0123456789abcdef" for c in sha)

    def test_invalid_ref_raises_exit(self, tmp_path: Path) -> None:
        """An unknown ref should raise typer.Exit(1) with a clear message."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        with pytest.raises(typer.Exit) as exc_info:
            _validate_base_ref(repo, "bogus-ref-that-does-not-exist")

        assert exc_info.value.exit_code == 1

    def test_invalid_ref_error_message_contains_remediation(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """The error message for an invalid ref must mention the ref and remediation."""
        from rich.console import Console
        import specify_cli.cli.commands.implement as impl_mod

        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        # Capture output from the Rich console used by implement.py
        captured_messages: list[str] = []
        original_print = impl_mod.console.print

        def capturing_print(*args, **kwargs):
            captured_messages.append(str(args[0]) if args else "")
            original_print(*args, **kwargs)

        with patch.object(impl_mod.console, "print", side_effect=capturing_print):
            with pytest.raises(typer.Exit):
                _validate_base_ref(repo, "bogus-ref")

        all_output = " ".join(captured_messages)
        assert "bogus-ref" in all_output, f"Expected ref name in error: {all_output!r}"
        assert "does not resolve" in all_output, f"Expected 'does not resolve' in: {all_output!r}"


class TestImplementBaseFlagIntegration:
    """Integration tests for the implement --base flag."""

    def test_implement_base_flag_invalid_ref_fails_clearly(self, tmp_path: Path) -> None:
        """--base bogus-ref exits 1 with the documented message and allocates nothing.

        Exit code 1 alone is not the contract: ``implement`` exits 1 for many
        unrelated reasons. The contract is "no fallback" -- the unresolved ref is
        named in the error and no lane branch or worktree is created from it.
        """
        import specify_cli.cli.commands.implement as impl_mod
        from specify_cli.cli.commands.implement import implement

        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)
        feature_dir = _setup_feature(repo, "068-test")

        with (
            patch("specify_cli.cli.commands.implement.find_repo_root", return_value=repo),
            patch("specify_cli.cli.commands.implement.detect_feature_context", return_value=("068", "068-test")),
            patch("specify_cli.workspace.context.find_wp_file", return_value=feature_dir / "tasks" / "WP06-task.md"),
            patch("specify_cli.core.dependency_graph.parse_wp_dependencies", return_value=[]),
            patch("specify_cli.workspace.context.resolve_mission_target_branch", return_value="main"),
            patch("specify_cli.cli.commands.implement_planning_commit._ensure_planning_artifacts_committed_git"),
            patch("specify_cli.core.agent_config.get_auto_commit_default", return_value=False),
            impl_mod.console.capture() as captured,
            pytest.raises((typer.Exit, SystemExit)) as exc_info,
        ):
            implement(
                wp_id="WP06",
                mission="068-test",
                auto_commit=False,
                json_output=False,
                recover=False,
                base="totally-bogus-ref-xyz",
            )

        exit_code = getattr(exc_info.value, "exit_code", None) or getattr(exc_info.value, "code", None)
        assert exit_code == 1, f"Expected exit code 1 for invalid ref, got {exit_code}"
        message = " ".join(captured.get().split())
        assert "Base ref 'totally-bogus-ref-xyz' does not resolve" in message, message

        branches = subprocess.run(
            ["git", "branch", "--list", "kitty/mission-068-test-lane-a"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert branches == "", f"no lane branch may be created from an unresolved --base, found: {branches!r}"
        assert not (repo / ".worktrees" / "068-test-lane-a").exists()
