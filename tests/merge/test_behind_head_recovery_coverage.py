"""In-process coverage for the #4997 behind-own-HEAD lag proof and its recovery seam.

The diff-cover gate on PR #5031's merge head scored these lines at 26% because
:func:`specify_cli.merge.preflight.is_pure_behind_head_lag`,
:func:`specify_cli.merge.executor._recover_behind_head_primary_on_resume`, and
:func:`specify_cli.merge.executor._pre_mutation_safety_preflight_with_recovery`
are exercised only by real-CLI **subprocess** tests in ``tests/terminus/`` (they
run ``python -m specify_cli`` in a fresh interpreter, so ``coverage.py`` never
sees the parent process execute these lines). These tests call the functions
**directly**, in-process, so the merge shard's coverage records every branch.

``is_pure_behind_head_lag`` is exercised against **real** temporary git
repositories (mirroring the house discipline in ``test_behind_head_remedy.py``
— the ancestry/diff probes must run for real). The two executor-layer
recovery helpers are exercised with mocked collaborators, since driving a full
mission through ``--resume`` end-to-end is impractical for a focused unit test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import typer

from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.merge import executor as ex
from specify_cli.merge import preflight as pf
from specify_cli.merge.preflight import ResumeRemedyKind, is_pure_behind_head_lag
from specify_cli.merge.state import MergeState

# Two profiles in one file: the preflight-layer tests build real git repos
# (subprocess-backed, mirroring test_behind_head_remedy.py) while the
# executor-layer tests mock collaborators and run purely in-process. The
# subprocess work means this module cannot carry ``fast`` (Rule 2 of the
# sibling file) and must carry ``non_sandbox`` alongside it.
pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(repo: Path, *args: str) -> str:
    """Run ``git`` in *repo*, returning stripped stdout (raises on failure)."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "C0 base")
    return repo


def _make_behind_own_head_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """Return ``(repo, lane_branch, base_sha)`` for a checkout behind its own HEAD.

    Identical construction to ``test_behind_head_remedy.py``'s helper of the
    same purpose: the lane is merged onto ``main`` by advancing the ref, but
    the ``reset --hard`` that would refresh the working checkout never runs.
    ``base_sha`` is C0 — the persisted ``pre_mutation_target_sha`` the pure-lag
    proof is checked against.
    """
    repo = _init_repo(tmp_path)
    base_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-b", "lane-x")
    (repo / "beta.txt").write_text("beta\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "C1 lane work")
    lane_sha = _git(repo, "rev-parse", "lane-x")
    _git(repo, "checkout", "main")
    _git(repo, "update-ref", "refs/heads/main", lane_sha)
    return repo, "lane-x", base_sha


# --- is_pure_behind_head_lag -------------------------------------------------


def test_pure_lag_false_on_missing_base_sha(tmp_path: Path) -> None:
    repo, _lane, _base = _make_behind_own_head_repo(tmp_path)

    assert is_pure_behind_head_lag(repo, base_sha=None) is False
    assert is_pure_behind_head_lag(repo, base_sha="") is False


def test_pure_lag_false_when_head_equals_base(tmp_path: Path) -> None:
    # Lane never merged: HEAD is still C0, so head == base_sha.
    repo = _init_repo(tmp_path)
    base_sha = _git(repo, "rev-parse", "HEAD")

    assert is_pure_behind_head_lag(repo, base_sha=base_sha) is False


def test_pure_lag_false_when_base_not_ancestor_of_head(tmp_path: Path) -> None:
    repo, lane_branch, base_sha = _make_behind_own_head_repo(tmp_path)
    # A SHA descended from base but not an ancestor of the CURRENT head
    # (main was force-set back to base_sha here) proves non-ancestry.
    lane_sha = _git(repo, "rev-parse", lane_branch)
    _git(repo, "update-ref", "refs/heads/main", base_sha)

    assert is_pure_behind_head_lag(repo, base_sha=lane_sha) is False


def test_pure_lag_false_on_dirty_worktree_vs_base(tmp_path: Path) -> None:
    repo, _lane, base_sha = _make_behind_own_head_repo(tmp_path)
    # Genuine uncommitted edit to a tracked file, unrelated to the lag.
    (repo / "alpha.txt").write_text("alpha edited\n", encoding="utf-8")

    assert is_pure_behind_head_lag(repo, base_sha=base_sha) is False


def test_pure_lag_false_on_dirty_index_vs_base(tmp_path: Path) -> None:
    repo, _lane, base_sha = _make_behind_own_head_repo(tmp_path)
    # Stage a change against alpha.txt (index now differs from base)...
    (repo / "alpha.txt").write_text("alpha staged\n", encoding="utf-8")
    _git(repo, "add", "alpha.txt")
    # ...then restore the WORKING FILE content to match base directly (not via
    # git), so the worktree-vs-base diff is clean while the INDEX-vs-base diff
    # is still dirty — isolating the index-only branch.
    (repo / "alpha.txt").write_text("alpha\n", encoding="utf-8")

    assert is_pure_behind_head_lag(repo, base_sha=base_sha) is False


def test_pure_lag_false_on_untracked_obstruction(tmp_path: Path) -> None:
    repo, _lane, base_sha = _make_behind_own_head_repo(tmp_path)
    # beta.txt is absent from the checkout (worktree/index sit at base_sha's
    # tree) but present in HEAD's tree — an untracked file at that same path
    # would be silently clobbered by `git reset --hard HEAD`.
    (repo / "beta.txt").write_text("untracked obstruction\n", encoding="utf-8")

    assert is_pure_behind_head_lag(repo, base_sha=base_sha) is False


def test_pure_lag_true_on_provably_pure_lag(tmp_path: Path) -> None:
    repo, _lane, base_sha = _make_behind_own_head_repo(tmp_path)

    assert is_pure_behind_head_lag(repo, base_sha=base_sha) is True


# --- _recover_behind_head_primary_on_resume ----------------------------------


def _refusal(error_code: str = "MERGE_UNSAFE_PRIMARY_DIRTY") -> DestructiveOpRefused:
    return DestructiveOpRefused(error_code=error_code, remediation="do something")


def test_recover_false_on_wrong_error_code(tmp_path: Path) -> None:
    exc = _refusal(error_code="MERGE_UNSAFE_PRIMARY_OFF_TARGET")

    result = ex._recover_behind_head_primary_on_resume(exc, tmp_path, "01ID", mission_branch="kitty/mission-m")

    assert result is False


def test_recover_false_on_fresh_merge_no_state(tmp_path: Path) -> None:
    exc = _refusal()

    with patch.object(ex, "load_state", return_value=None) as mock_load_state:
        result = ex._recover_behind_head_primary_on_resume(exc, tmp_path, "01ID", mission_branch="kitty/mission-m")

    assert result is False
    mock_load_state.assert_called_once_with(tmp_path, "01ID")


def _fake_state(**overrides: object) -> MergeState:
    defaults: dict[str, object] = {
        "mission_id": "01ID",
        "mission_slug": "m",
        "target_branch": "main",
        "wp_order": ["WP01"],
        "pre_mutation_target_sha": "deadbeef",
    }
    defaults.update(overrides)
    return MergeState(**defaults)


def test_recover_false_when_remedy_is_not_behind_own_head(tmp_path: Path) -> None:
    exc = _refusal()
    state = _fake_state()

    with (
        patch.object(ex, "load_state", return_value=state),
        patch.object(
            pf,
            "classify_resume_dirty_remedy",
            return_value=pf.ResumeDirtyRemedy(kind=ResumeRemedyKind.LOCAL_CHANGES, remediation=["commit"]),
        ) as mock_classify,
        patch.object(pf, "is_pure_behind_head_lag") as mock_pure_lag,
    ):
        result = ex._recover_behind_head_primary_on_resume(exc, tmp_path, "01ID", mission_branch="kitty/mission-m")

    assert result is False
    mock_classify.assert_called_once()
    mock_pure_lag.assert_not_called()


def test_recover_false_when_lag_not_provably_pure(tmp_path: Path) -> None:
    exc = _refusal()
    state = _fake_state()

    with (
        patch.object(ex, "load_state", return_value=state),
        patch.object(
            pf,
            "classify_resume_dirty_remedy",
            return_value=pf.ResumeDirtyRemedy(kind=ResumeRemedyKind.BEHIND_OWN_HEAD, remediation=["reset"]),
        ),
        patch.object(pf, "is_pure_behind_head_lag", return_value=False) as mock_pure_lag,
        patch.object(ex, "run_command") as mock_run_command,
    ):
        result = ex._recover_behind_head_primary_on_resume(exc, tmp_path, "01ID", mission_branch="kitty/mission-m")

    assert result is False
    mock_pure_lag.assert_called_once_with(tmp_path, base_sha="deadbeef")
    mock_run_command.assert_not_called()


def test_recover_false_and_prints_error_when_reset_fails(tmp_path: Path) -> None:
    exc = _refusal()
    state = _fake_state()

    with (
        patch.object(ex, "load_state", return_value=state),
        patch.object(
            pf,
            "classify_resume_dirty_remedy",
            return_value=pf.ResumeDirtyRemedy(kind=ResumeRemedyKind.BEHIND_OWN_HEAD, remediation=["reset"]),
        ),
        patch.object(pf, "is_pure_behind_head_lag", return_value=True),
        patch.object(ex, "run_command", return_value=(1, "", "fatal: something")) as mock_run_command,
        patch.object(ex, "console") as mock_console,
    ):
        result = ex._recover_behind_head_primary_on_resume(exc, tmp_path, "01ID", mission_branch="kitty/mission-m")

    assert result is False
    mock_run_command.assert_called_once_with(
        ["git", "reset", "--hard", "HEAD"],
        capture=True,
        check_return=False,
        cwd=tmp_path,
    )
    assert any("Error" in call.args[0] for call in mock_console.print.call_args_list)


def test_recover_true_on_success(tmp_path: Path) -> None:
    exc = _refusal()
    state = _fake_state()

    with (
        patch.object(ex, "load_state", return_value=state),
        patch.object(
            pf,
            "classify_resume_dirty_remedy",
            return_value=pf.ResumeDirtyRemedy(kind=ResumeRemedyKind.BEHIND_OWN_HEAD, remediation=["reset"]),
        ),
        patch.object(pf, "is_pure_behind_head_lag", return_value=True),
        patch.object(ex, "run_command", return_value=(0, "", "")),
        patch.object(ex, "console") as mock_console,
    ):
        result = ex._recover_behind_head_primary_on_resume(exc, tmp_path, "01ID", mission_branch="kitty/mission-m")

    assert result is True
    assert any("Recovered a behind-own-HEAD primary" in call.args[0] for call in mock_console.print.call_args_list)


# --- _pre_mutation_safety_preflight_with_recovery ----------------------------


def _manifest_and_retention() -> tuple[SimpleNamespace, SimpleNamespace]:
    manifest = SimpleNamespace(target_branch="main", mission_branch="kitty/mission-m")
    retention = SimpleNamespace(remove_worktree=True, teardown_coordination=True)
    return manifest, retention


def test_preflight_with_recovery_passes_through_on_success(tmp_path: Path) -> None:
    manifest, retention = _manifest_and_retention()

    with patch.object(ex, "_pre_mutation_safety_preflight") as mock_preflight:
        ex._pre_mutation_safety_preflight_with_recovery(tmp_path, "m", manifest, "01ID", "01MISSION", tmp_path / "meta", retention)

    mock_preflight.assert_called_once()


def test_preflight_with_recovery_recovers_and_retries_successfully(tmp_path: Path) -> None:
    manifest, retention = _manifest_and_retention()
    exc = _refusal()

    with (
        patch.object(ex, "_pre_mutation_safety_preflight", side_effect=[exc, None]) as mock_preflight,
        patch.object(ex, "_recover_behind_head_primary_on_resume", return_value=True) as mock_recover,
        patch.object(ex, "_report_pre_mutation_refusal") as mock_report,
    ):
        ex._pre_mutation_safety_preflight_with_recovery(tmp_path, "m", manifest, "01ID", "01MISSION", tmp_path / "meta", retention)

    assert mock_preflight.call_count == 2
    mock_recover.assert_called_once_with(exc, tmp_path, "01ID", mission_branch="kitty/mission-m")
    mock_report.assert_not_called()


def test_preflight_with_recovery_reports_and_exits_when_not_recovered(tmp_path: Path) -> None:
    manifest, retention = _manifest_and_retention()
    exc = _refusal()

    with (
        patch.object(ex, "_pre_mutation_safety_preflight", side_effect=exc) as mock_preflight,
        patch.object(ex, "_recover_behind_head_primary_on_resume", return_value=False) as mock_recover,
        patch.object(ex, "_report_pre_mutation_refusal") as mock_report,
        pytest.raises(typer.Exit) as exc_info,
    ):
        ex._pre_mutation_safety_preflight_with_recovery(tmp_path, "m", manifest, "01ID", "01MISSION", tmp_path / "meta", retention)

    assert mock_preflight.call_count == 1
    mock_recover.assert_called_once()
    mock_report.assert_called_once_with(exc, tmp_path, mission_branch="kitty/mission-m")
    assert exc_info.value.exit_code == 1


def test_preflight_with_recovery_reports_and_exits_when_still_refused_after_recovery(
    tmp_path: Path,
) -> None:
    manifest, retention = _manifest_and_retention()
    exc = _refusal()
    exc_after = _refusal()

    with (
        patch.object(ex, "_pre_mutation_safety_preflight", side_effect=[exc, exc_after]) as mock_preflight,
        patch.object(ex, "_recover_behind_head_primary_on_resume", return_value=True) as mock_recover,
        patch.object(ex, "_report_pre_mutation_refusal") as mock_report,
        pytest.raises(typer.Exit) as exc_info,
    ):
        ex._pre_mutation_safety_preflight_with_recovery(tmp_path, "m", manifest, "01ID", "01MISSION", tmp_path / "meta", retention)

    assert mock_preflight.call_count == 2
    mock_recover.assert_called_once()
    mock_report.assert_called_once_with(exc_after, tmp_path, mission_branch="kitty/mission-m")
    assert exc_info.value.exit_code == 1
