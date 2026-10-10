"""Workspace husk resolution guards (#1833 — fall-through is failure).

A "husk" is a directory under ``.worktrees/`` that is not a git worktree (no
``.git`` entry). Before mission coordination-merge-stabilization WP04, git
commands invoked with a husk as their working directory silently walked up to
the PRIMARY repository and produced misattributed verdicts ("No implementation
commits on lane branch!", primary-repo dirty complaints).

Acceptance criteria covered here (contracts/class-d-workspace-resolution.md):

- AC-D1: move-task validation fails with a structured resolution error naming
  the husk path and the failed check; zero git subprocess calls run against
  the primary repository from the husk resolution.
- AC-D2: ``ResolvedWorkspace.exists`` is False for a husk; review claim
  acquires the ReviewLock only after the workspace exists; ``git worktree
  add`` failure is a hard error and leaves no lock behind.
- AC-D3: the doctor husk check reports husks; ``--fix`` removes only
  unregistered husks and never removes a registered worktree.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

import specify_cli.cli.commands.agent.tasks as tasks_module
import specify_cli.cli.commands.agent.workflow as workflow_module
from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review
from specify_cli.review.lock import LOCK_DIR, LOCK_FILE
from specify_cli.workspace.context import ResolvedWorkspace
from tests.lane_test_utils import lane_branch_name, lane_worktree_path, write_single_lane_manifest

pytestmark = pytest.mark.git_repo

runner = CliRunner()

MISSION_SLUG = "017-test-feature"
WP_ID = "WP01"
# Pinned operator recovery command (NFR-003). A separate test asserts the
# production constant matches this literal.
WORKSPACE_HUSK_RECOVERY_COMMAND = "spec-kitty doctor workspaces --fix"


def test_recovery_command_constant_is_pinned() -> None:
    from specify_cli.workspace import context as workspace_context

    assert workspace_context.WORKSPACE_HUSK_RECOVERY_COMMAND == WORKSPACE_HUSK_RECOVERY_COMMAND


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def husk_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Git repo with a mission and a planted husk lane directory.

    Returns (repo_root, husk_path). The husk is ``.worktrees/<slug>-lane-a/``
    with no ``.git`` entry.
    """
    repo = tmp_path / "test-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("# Config\n")

    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=(WP_ID,))

    task_file = tasks_dir / f"{WP_ID}-test-task.md"
    task_file.write_text(
        '---\nwork_package_id: "WP01"\ntitle: "Test Task"\nagent: "test-agent"\n---\n\n# Work Package: WP01\n'
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Initial commit")

    husk = lane_worktree_path(repo, MISSION_SLUG)
    # An empty leftover directory: a husk holding no file is removable, one holding
    # work is preserved by the destructive guard (#5965; see test_guarded_site_routing_misc).
    husk.mkdir(parents=True)
    return repo, husk


def _resolved_workspace(path: Path, branch: str | None = None) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        execution_mode="code_change",
        mode_source="frontmatter",
        resolution_kind="lane_workspace",
        workspace_name=path.name,
        worktree_path=path,
        branch_name=branch or lane_branch_name(MISSION_SLUG),
        lane_id="lane-a",
        lane_wp_ids=[WP_ID],
        context=None,
    )


class TestMoveTaskHuskResolution:
    """AC-D1: husk resolution in move-task validation is a structured failure."""

    def test_husk_fails_with_structured_error_and_no_git_against_primary(
        self, husk_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, husk = husk_repo
        recorded: list[tuple[list[str], str | None]] = []
        real_run = subprocess.run

        def recording_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
            cwd = kwargs.get("cwd")
            recorded.append(([str(part) for part in cmd], str(cwd) if cwd is not None else None))
            return real_run(cmd, *args, **kwargs)

        monkeypatch.setattr(tasks_module.subprocess, "run", recording_run)

        ok, guidance = _validate_ready_for_review(repo, MISSION_SLUG, WP_ID, force=False)
        text = "\n".join(guidance)

        assert ok is False
        # Structured error names the husk path and the failed check.
        assert str(husk) in text
        assert ".git" in text
        # Recovery command is named (NFR-003 / T023).
        assert WORKSPACE_HUSK_RECOVERY_COMMAND in text
        # NOT a misattributed verdict.
        assert "No implementation commits on lane branch!" not in text
        assert "Uncommitted implementation changes in worktree!" not in text
        assert "Staged but uncommitted changes in worktree!" not in text

        # Zero git subprocess calls executed against the primary repo *from the
        # husk resolution*: nothing ran with the husk as cwd or via -C <husk>.
        husk_str = str(husk)
        for cmd, cwd in recorded:
            assert cwd != husk_str, f"git invoked with husk cwd: {cmd}"
            assert husk_str not in cmd, f"git invoked with husk path argument: {cmd}"

    def test_toplevel_mismatch_is_structured_error(self, husk_repo: tuple[Path, Path]) -> None:
        """Last-line defense (T021): a directory whose git toplevel is not itself is rejected.

        A nested plain directory inside the primary repo has a ``.git``-less
        parent chain; simulate the other lineage by planting a ``.git`` file
        that does not resolve to the directory itself.
        """
        repo, husk = husk_repo
        # Make the husk pass the .git-entry existence check while git still
        # resolves the toplevel to the primary repository: an empty ``.git``
        # directory is not a valid gitdir, so git keeps walking up.
        (husk / ".git").mkdir()

        ok, guidance = _validate_ready_for_review(repo, MISSION_SLUG, WP_ID, force=False)
        text = "\n".join(guidance)

        assert ok is False
        assert str(husk) in text
        assert "toplevel" in text.lower()
        assert WORKSPACE_HUSK_RECOVERY_COMMAND in text
        assert "No implementation commits on lane branch!" not in text


def test_verify_workspace_toplevel_git_failure_is_structured_error(tmp_path: Path) -> None:
    from specify_cli.workspace.context import verify_workspace_toplevel

    missing = tmp_path / "does-not-exist"
    error = verify_workspace_toplevel(missing)
    assert error is not None
    assert str(missing) in str(error)
    assert WORKSPACE_HUSK_RECOVERY_COMMAND in str(error)


class TestResolvedWorkspaceExists:
    """AC-D2: ``exists`` requires a .git entry (file or directory)."""

    def test_exists_false_for_husk(self, husk_repo: tuple[Path, Path]) -> None:
        _repo, husk = husk_repo
        assert _resolved_workspace(husk).exists is False

    def test_exists_true_for_real_worktree(self, husk_repo: tuple[Path, Path]) -> None:
        repo, _husk = husk_repo
        worktree = repo / ".worktrees" / f"{MISSION_SLUG}-lane-b"
        _git(repo, "worktree", "add", "-b", lane_branch_name(MISSION_SLUG, "lane-b"), str(worktree), "main")
        # git worktrees have a .git FILE, not a directory.
        assert (worktree / ".git").is_file()
        assert _resolved_workspace(worktree).exists is True

    def test_exists_false_for_missing_path(self, tmp_path: Path) -> None:
        assert _resolved_workspace(tmp_path / "nope").exists is False

    def test_is_husk_only_for_gitless_existing_dir(self, husk_repo: tuple[Path, Path]) -> None:
        repo, husk = husk_repo
        assert _resolved_workspace(husk).is_husk is True
        assert _resolved_workspace(repo / "absent").is_husk is False
        assert _resolved_workspace(repo).is_husk is False


class TestReviewClaimWorkspacePreparation:
    """AC-D2: lock acquired only after the workspace exists; creation failure is failure."""

    def test_husk_claim_is_hard_error_and_leaves_no_lock(
        self, husk_repo: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, husk = husk_repo
        workspace = _resolved_workspace(husk)

        with pytest.raises(typer.Exit) as excinfo:
            workflow_module._prepare_review_workspace(workspace, repo, WP_ID, "claude")

        assert excinfo.value.exit_code == 1
        out = capsys.readouterr().out
        assert str(husk) in out
        assert ".git" in out
        assert WORKSPACE_HUSK_RECOVERY_COMMAND in out
        # No ReviewLock left behind in the husk.
        assert not (husk / LOCK_DIR / LOCK_FILE).exists()

    def test_worktree_add_failure_is_hard_error_with_stderr_and_no_lock(
        self, husk_repo: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _husk = husk_repo
        missing = repo / ".worktrees" / f"{MISSION_SLUG}-lane-z"
        # Invalid branch name forces `git worktree add` to fail.
        workspace = _resolved_workspace(missing, branch="invalid..branch..name")

        with pytest.raises(typer.Exit) as excinfo:
            workflow_module._prepare_review_workspace(workspace, repo, WP_ID, "claude")

        assert excinfo.value.exit_code == 1
        out = capsys.readouterr().out
        assert "Error" in out
        assert str(missing) in out
        # git's stderr is surfaced.
        assert "invalid..branch..name" in out
        assert not (missing / LOCK_DIR / LOCK_FILE).exists()

    def test_successful_creation_then_lock(self, husk_repo: tuple[Path, Path]) -> None:
        repo, _husk = husk_repo
        path = repo / ".worktrees" / f"{MISSION_SLUG}-lane-d"
        workspace = _resolved_workspace(path, branch=lane_branch_name(MISSION_SLUG, "lane-d"))

        result = workflow_module._prepare_review_workspace(workspace, repo, WP_ID, "claude")

        assert (path / ".git").exists()
        assert result.worktree_path == path
        # Lock acquired after creation succeeded.
        assert (path / LOCK_DIR / LOCK_FILE).exists()

    def test_creation_attaches_to_existing_branch(self, husk_repo: tuple[Path, Path]) -> None:
        repo, _husk = husk_repo
        branch = lane_branch_name(MISSION_SLUG, "lane-f")
        _git(repo, "branch", branch)
        path = repo / ".worktrees" / f"{MISSION_SLUG}-lane-f"
        workspace = _resolved_workspace(path, branch=branch)

        result = workflow_module._prepare_review_workspace(workspace, repo, WP_ID, "claude")

        assert (path / ".git").exists()
        assert result.worktree_path == path

    def test_missing_branch_name_is_hard_error(
        self, husk_repo: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _husk = husk_repo
        path = repo / ".worktrees" / f"{MISSION_SLUG}-lane-g"
        workspace = ResolvedWorkspace(
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            execution_mode="code_change",
            mode_source="frontmatter",
            resolution_kind="lane_workspace",
            workspace_name=path.name,
            worktree_path=path,
            branch_name=None,
            lane_id="lane-g",
            lane_wp_ids=[WP_ID],
            context=None,
        )

        with pytest.raises(typer.Exit) as excinfo:
            workflow_module._prepare_review_workspace(workspace, repo, WP_ID, "claude")

        assert excinfo.value.exit_code == 1
        assert "no branch name" in capsys.readouterr().out

    def test_creation_reporting_success_without_worktree_is_hard_error(
        self,
        husk_repo: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A `git worktree add` that exits 0 without materializing .git is rejected."""
        repo, _husk = husk_repo
        path = repo / ".worktrees" / f"{MISSION_SLUG}-lane-h"
        workspace = _resolved_workspace(path, branch=lane_branch_name(MISSION_SLUG, "lane-h"))

        def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(workflow_module.subprocess, "run", fake_run)

        with pytest.raises(typer.Exit) as excinfo:
            workflow_module._prepare_review_workspace(workspace, repo, WP_ID, "claude")

        assert excinfo.value.exit_code == 1
        assert "is not a git worktree" in capsys.readouterr().out

    def test_env_var_isolation_skips_lock(
        self, husk_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, _husk = husk_repo
        path = repo / ".worktrees" / f"{MISSION_SLUG}-lane-i"
        workspace = _resolved_workspace(path, branch=lane_branch_name(MISSION_SLUG, "lane-i"))

        import specify_cli.review.lock as lock_module

        applied: list[str] = []
        monkeypatch.setattr(lock_module, "_get_isolation_config", lambda _root: {"strategy": "env_var"})
        monkeypatch.setattr(
            lock_module,
            "_apply_env_var_isolation",
            lambda _cfg, _agent, wp: applied.append(wp),
        )

        result = workflow_module._prepare_review_workspace(workspace, repo, WP_ID, "claude")

        assert applied == [WP_ID]
        assert not (result.worktree_path / LOCK_DIR / LOCK_FILE).exists()

    def test_active_lock_conflict_is_hard_error(
        self, husk_repo: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _husk = husk_repo
        path = repo / ".worktrees" / f"{MISSION_SLUG}-lane-j"
        workspace = _resolved_workspace(path, branch=lane_branch_name(MISSION_SLUG, "lane-j"))

        workflow_module._prepare_review_workspace(workspace, repo, WP_ID, "claude")
        # Second claim while the first lock (this live PID) is held.
        with pytest.raises(typer.Exit) as excinfo:
            workflow_module._prepare_review_workspace(workspace, repo, WP_ID, "other-agent")

        assert excinfo.value.exit_code == 1
        assert "active review" in capsys.readouterr().out


class TestImplementHuskGuard:
    """AC-D2: implement also refuses husks instead of recreating over them."""

    def test_implement_husk_is_hard_error(
        self, husk_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock, patch

        from specify_cli.status.models import Lane, StatusEvent
        from specify_cli.status.store import append_event

        repo, husk = husk_repo
        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        wp_path = feature_dir / "tasks" / f"{WP_ID}-test-task.md"
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{WP_ID}-planned",
                mission_slug=MISSION_SLUG,
                wp_id=WP_ID,
                from_lane=Lane.PLANNED,
                to_lane=Lane.PLANNED,
                at="2026-01-01T00:00:00+00:00",
                actor="test-fixture",
                force=True,
                execution_mode="worktree",
            ),
        )

        with (
            patch.object(workflow_module, "_find_mission_slug", return_value=MISSION_SLUG),
            patch.object(workflow_module, "locate_project_root", return_value=repo),
            patch.object(workflow_module, "get_main_repo_root", return_value=repo),
            patch.object(workflow_module, "_ensure_target_branch_checked_out", return_value=(repo, "main")),
            patch.object(workflow_module, "_require_current_analysis_report", return_value=None),
            patch.object(workflow_module, "locate_work_package", return_value=SimpleNamespace(path=wp_path)),
            patch.object(workflow_module, "resolve_workspace_for_wp", return_value=_resolved_workspace(husk)),
            patch.object(workflow_module, "top_level_implement", MagicMock()) as mock_implement,
        ):
            result = runner.invoke(
                workflow_module.app,
                ["implement", WP_ID, "--mission", MISSION_SLUG, "--agent", "claude"],
            )

        assert result.exit_code == 1
        assert str(husk) in result.stdout
        assert WORKSPACE_HUSK_RECOVERY_COMMAND in result.stdout
        mock_implement.assert_not_called()


class TestDoctorHuskCheck:
    """AC-D3: doctor reports husks; --fix removes only unregistered husks."""

    def test_scan_reports_husk_with_registration_flag(self, husk_repo: tuple[Path, Path]) -> None:
        from specify_cli.status.doctor_husks import scan_workspace_husks

        repo, husk = husk_repo
        report = scan_workspace_husks(repo)

        assert report.healthy is False
        names = {entry.path: entry.registered for entry in report.husks}
        rel = str(husk.relative_to(repo))
        assert rel in names
        assert names[rel] is False

    def test_scan_healthy_when_no_husks(self, tmp_path: Path) -> None:
        from specify_cli.status.doctor_husks import scan_workspace_husks

        repo = tmp_path / "clean-repo"
        repo.mkdir()
        _git(repo, "init", "-b", "main")
        report = scan_workspace_husks(repo)
        assert report.healthy is True
        assert report.husks == []

    def test_fix_removes_unregistered_husk_and_preserves_registered_worktree(
        self, husk_repo: tuple[Path, Path]
    ) -> None:
        from specify_cli.status.doctor_husks import fix_workspace_husks

        repo, husk = husk_repo
        real_worktree = repo / ".worktrees" / f"{MISSION_SLUG}-lane-b"
        _git(repo, "worktree", "add", "-b", lane_branch_name(MISSION_SLUG, "lane-b"), str(real_worktree), "main")

        report, fix_result = fix_workspace_husks(repo)

        assert str(husk.relative_to(repo)) in fix_result.removed
        assert not husk.exists()
        # The registered real worktree survives untouched.
        assert real_worktree.exists()
        assert (real_worktree / ".git").exists()

    def test_fix_never_removes_registered_broken_worktree(self, husk_repo: tuple[Path, Path]) -> None:
        from specify_cli.status.doctor_husks import fix_workspace_husks

        repo, _husk = husk_repo
        broken = repo / ".worktrees" / f"{MISSION_SLUG}-lane-e"
        _git(repo, "worktree", "add", "-b", lane_branch_name(MISSION_SLUG, "lane-e"), str(broken), "main")
        # Break it: remove the .git file so it scans as a husk, but it is
        # still registered in `git worktree list`.
        (broken / ".git").unlink()

        report, fix_result = fix_workspace_husks(repo)

        assert broken.exists(), "registered worktree must never be removed (R5)"
        rel = str(broken.relative_to(repo))
        assert rel in fix_result.skipped_registered
        assert rel not in fix_result.removed

    def test_fix_refuses_when_registered_worktree_scan_fails(
        self, husk_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import specify_cli.cli.commands.doctor as doctor_module
        import specify_cli.status.doctor_husks as doctor_husks

        repo, husk = husk_repo
        rel = str(husk.relative_to(repo))

        def fail_worktree_list(cmd: Any, *args: Any, **kwargs: Any) -> SimpleNamespace:
            assert cmd == ["git", "worktree", "list", "--porcelain"]
            return SimpleNamespace(
                returncode=128,
                stdout="",
                stderr="fatal: unable to read worktree registrations\n",
            )

        monkeypatch.setattr(doctor_husks.subprocess, "run", fail_worktree_list)
        monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: repo)

        report = doctor_husks.scan_workspace_husks(repo)
        assert report.registration_error is not None
        assert "git worktree list --porcelain failed" in report.registration_error
        assert {entry.path: entry.registered for entry in report.husks}[rel] is None

        result = runner.invoke(doctor_module.app, ["workspaces", "--fix"])

        assert result.exit_code == 1
        assert "git worktree list --porcelain failed" in result.stdout
        assert "Workspace husks were not modified" in result.stdout
        assert husk.exists()

    def test_fix_rechecks_git_entry_before_removal(
        self, husk_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import specify_cli.status.doctor_husks as doctor_husks

        repo, husk = husk_repo
        rel = str(husk.relative_to(repo))
        real_scan = doctor_husks.scan_workspace_husks

        def scan_then_git_entry_appears(repo_root: Path) -> doctor_husks.HuskReport:
            report = real_scan(repo_root)
            (husk / ".git").write_text("gitdir: ../now-valid\n")
            return report

        def fail_if_removed(path: Path, **_kwargs: Any) -> None:
            raise AssertionError(f"removal must not run after .git appeared: {path}")

        monkeypatch.setattr(
            doctor_husks,
            "scan_workspace_husks",
            scan_then_git_entry_appears,
        )
        monkeypatch.setattr(doctor_husks, "guarded_tree_delete", fail_if_removed)

        report, fix_result = doctor_husks.fix_workspace_husks(repo)

        assert rel in {entry.path for entry in report.husks}
        assert rel in fix_result.skipped_appeared_valid
        assert rel not in fix_result.removed
        assert husk.exists()

    def test_doctor_workspaces_cli_json_and_fix(
        self, husk_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import specify_cli.cli.commands.doctor as doctor_module

        repo, husk = husk_repo
        monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: repo)

        result = runner.invoke(doctor_module.app, ["workspaces", "--json"])
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["healthy"] is False
        assert any(str(husk.relative_to(repo)) == entry["path"] for entry in payload["husks"])

        # Human report names the husk and the recovery command.
        result = runner.invoke(doctor_module.app, ["workspaces"])
        assert result.exit_code == 1
        assert str(husk.relative_to(repo)) in result.stdout
        assert "--fix" in result.stdout

        result = runner.invoke(doctor_module.app, ["workspaces", "--fix"])
        assert result.exit_code == 0
        assert not husk.exists()

        result = runner.invoke(doctor_module.app, ["workspaces"])
        assert result.exit_code == 0

        # --fix on a clean tree is a no-op success.
        result = runner.invoke(doctor_module.app, ["workspaces", "--fix"])
        assert result.exit_code == 0
        assert "No workspace husks" in result.stdout

    def test_doctor_workspaces_cli_fix_json_preserves_registered(
        self, husk_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import specify_cli.cli.commands.doctor as doctor_module

        repo, husk = husk_repo
        broken = repo / ".worktrees" / f"{MISSION_SLUG}-lane-k"
        _git(repo, "worktree", "add", "-b", lane_branch_name(MISSION_SLUG, "lane-k"), str(broken), "main")
        (broken / ".git").unlink()
        monkeypatch.setattr(doctor_module, "locate_project_root", lambda *a, **k: repo)

        result = runner.invoke(doctor_module.app, ["workspaces", "--fix", "--json"])
        assert result.exit_code == 1  # registered husk remains
        payload = json.loads(result.stdout)
        assert str(husk.relative_to(repo)) in payload["removed"]
        assert str(broken.relative_to(repo)) in payload["skipped_registered"]
        assert broken.exists()
        assert not husk.exists()

        # Human fix mode reports the preserved registered worktree.
        result = runner.invoke(doctor_module.app, ["workspaces", "--fix"])
        assert result.exit_code == 1
        assert "Preserved registered worktree" in result.stdout
