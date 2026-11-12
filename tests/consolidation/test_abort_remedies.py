"""#7600: an ``--abort`` refusal names a remedy that completes the abort.

Operator ruling ``01M78G5ZPT2R106TZ26HB4EG5W``: :class:`RefAdvanceDirtyWorktreeError` says
only what blocks (a dirty checkout), and each caller appends its own next step. The rollback
report renders that next step for the command that ran it: ``--abort`` (re-run ``--abort``,
or release a branch another actor moved) or the fresh-run / ``--resume`` rollback door (resume).

Real git in a tmp repo and the REAL rollback authority; only the rich console is captured.
Rich wraps long commands, so every assertion matches whitespace-normalised output.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands import consolidate
from specify_cli.consolidation.rollback import (
    BranchOutcomeKind,
    RollbackReport,
    begin_attempt,
    record_post_mutation_tips,
    rollback_to_snapshot,
)
from specify_cli.consolidation.state import ConsolidationState, save_state
from specify_cli.git.ref_advance import RefAdvanceDirtyWorktreeError

pytestmark = [pytest.mark.git_repo, pytest.mark.fast]

_MISSION_ID = "01MREMEDY" + "0" * 17
_MISSION_SLUG = "abort-remedies"
_MISSION_BRANCH = "kitty/mission-abort-remedies"
_ABORT_RERUN = "re-run `spec-kitty consolidate --abort`"
_RESUME = "spec-kitty consolidate --resume"


def _flat(text: str) -> str:
    return " ".join(text.split())


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def _commit(repo: Path, branch: str, name: str) -> str:
    """One real commit on *branch* with the same tree (plumbing only, no checkout touched)."""
    tip = _git(repo, "rev-parse", branch)
    tree = _git(repo, "rev-parse", f"{tip}^{{tree}}")
    new = _git(repo, "commit-tree", tree, "-p", tip, "-m", name)
    _git(repo, "update-ref", f"refs/heads/{branch}", new, tip)
    return new


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-qb", "main", str(root)], check=True)
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    (root / "README.md").write_text("init\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "init")
    _git(root, "branch", _MISSION_BRANCH)
    _git(root, "checkout", "-q", "-b", "parking")
    return root


def _advanced_state(repo: Path) -> ConsolidationState:
    """A record whose run advanced ``main`` and the mission branch and recorded its post tips."""
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug=_MISSION_SLUG, target_branch="main", wp_order=["WP01"])
    state.pre_mutation_refs = {"main": _git(repo, "rev-parse", "main"), _MISSION_BRANCH: _git(repo, "rev-parse", _MISSION_BRANCH)}
    save_state(state, repo)
    begin_attempt(repo, state)
    _commit(repo, "main", "squash")
    _commit(repo, _MISSION_BRANCH, "bake")
    record_post_mutation_tips(repo, state)
    return state


def _dirty_main_checkout(repo: Path) -> Path:
    """Check ``main`` out in a linked worktree and leave a tracked edit there (the restore must resync it)."""
    checkout = repo.parent / "main-checkout"
    _git(repo, "worktree", "add", "-q", str(checkout), "main")
    (checkout / "README.md").write_text("operator edit\n")
    return checkout


def _render(report: RollbackReport, mode: str) -> str:
    from specify_cli.consolidation.rollback import RollbackFollowUp

    return _flat(report.render(follow_up=RollbackFollowUp(mode)))


def _cli_abort(repo: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, str]:
    """Run ``spec-kitty consolidate --abort`` (the command body); return ``(exit_code, flattened output)``."""
    monkeypatch.setattr(consolidate, "find_repo_root", lambda: repo)
    monkeypatch.setattr(consolidate, "show_banner", lambda: None)
    code = 0
    with consolidate.console.capture() as capture:
        try:
            consolidate.run_consolidate(consolidate.ConsolidateOptions(abort=True))
        except typer.Exit as exc:
            code = int(exc.exit_code or 0)
    return code, _flat(capture.get())


# --------------------------------------------------------------------------- the neutral exception


def test_dirty_worktree_error_names_the_blocker_and_no_command() -> None:
    exc = RefAdvanceDirtyWorktreeError(
        worktree_path=Path("/tmp/wt"),
        branch="main",
        old_sha="a" * 40,
        new_sha="b" * 40,
        dirty_entries=[" M README.md"],
    )

    text = str(exc)

    assert "Commit, stash, or revert these changes in /tmp/wt." in text
    assert "consolidate" not in text
    assert exc.error_code == "REF_ADVANCE_DIRTY_WORKTREE"


# --------------------------------------------------------------------------- render, per follow-up


def test_a_dirty_checkout_outcome_tells_abort_to_re_run_abort(repo: Path) -> None:
    state = _advanced_state(repo)
    checkout = _dirty_main_checkout(repo)

    report = rollback_to_snapshot(repo, state, target_branch="main")

    assert any(o.branch == "main" and o.kind is BranchOutcomeKind.NOT_RESTORED for o in report.outcomes)
    text = _render(report, "abort")
    assert str(checkout) in text
    assert _ABORT_RERUN in text
    assert "--resume" not in text


def test_a_dirty_checkout_outcome_keeps_the_resume_hint_on_the_rollback_door(repo: Path) -> None:
    state = _advanced_state(repo)
    _dirty_main_checkout(repo)

    report = rollback_to_snapshot(repo, state, target_branch="main")

    text = _render(report, "resume")
    assert _RESUME in text
    assert _ABORT_RERUN not in text


def test_a_branch_moved_by_another_actor_names_the_release_flag_for_abort(repo: Path) -> None:
    state = _advanced_state(repo)
    _commit(repo, _MISSION_BRANCH, "another actor")

    report = rollback_to_snapshot(repo, state, target_branch="main")

    text = _render(report, "abort")
    assert f'spec-kitty consolidate --abort --release-branch {_MISSION_BRANCH} --release-reason "<why>"' in text
    assert "--resume" not in text


def test_a_move_without_a_recorded_post_tip_names_the_release_flag_for_abort(repo: Path) -> None:
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug=_MISSION_SLUG, target_branch="main", wp_order=["WP01"])
    state.pre_mutation_refs = {"main": _git(repo, "rev-parse", "main")}
    save_state(state, repo)
    begin_attempt(repo, state)
    _commit(repo, "main", "unrecorded")

    report = rollback_to_snapshot(repo, state, target_branch="main")

    assert _flat(report.render()).count("NOT restored") == 1
    assert '--abort --release-branch main --release-reason "<why>"' in _render(report, "abort")


def test_a_kept_verified_landing_offers_resume_labelled_as_finishing_the_teardown(repo: Path) -> None:
    state = _advanced_state(repo)
    state.reconciliation_passed_target_sha = _git(repo, "rev-parse", "main")

    report = rollback_to_snapshot(repo, state, target_branch="main")

    assert report.refused_verified_landing
    text = _render(report, "abort")
    assert "Kept the landing verified by an earlier reconciliation" in text
    assert f"To finish the teardown of this landing instead, run `{_RESUME}`" in text


def test_a_coordination_checkout_left_as_found_tells_abort_to_re_run_abort() -> None:
    report = RollbackReport(coord_checkout_note="Refusing to resync branch 'kitty/coord': dirty")

    text = _render(report, "abort")

    assert "commit or stash the listed change in the coordination worktree" in text
    assert _ABORT_RERUN in text
    assert "--resume" not in text
    assert _RESUME in _render(report, "resume"), "the rollback door keeps its resume remedy"


def test_render_defaults_to_the_rollback_door_follow_up(repo: Path) -> None:
    state = _advanced_state(repo)
    _dirty_main_checkout(repo)

    report = rollback_to_snapshot(repo, state, target_branch="main")

    assert _flat(report.render()) == _render(report, "resume")


def test_a_missing_branch_names_the_recreate_command_and_the_follow_up(repo: Path) -> None:
    """#7600 fold: a NOT_RESTORED missing branch had no next step under "complete the next steps above"."""
    state = _advanced_state(repo)
    snapshot = state.pre_mutation_refs[_MISSION_BRANCH]
    _git(repo, "branch", "-D", _MISSION_BRANCH)

    report = rollback_to_snapshot(repo, state, target_branch="main")

    assert any(o.branch == _MISSION_BRANCH and o.kind is BranchOutcomeKind.NOT_RESTORED for o in report.outcomes)
    abort_text = _render(report, "abort")
    assert f"{_MISSION_BRANCH}: recreate it (`git branch {_MISSION_BRANCH} {snapshot}`), then {_ABORT_RERUN}." in abort_text
    assert "--resume" not in abort_text
    assert f"{_MISSION_BRANCH}: recreate it (`git branch {_MISSION_BRANCH} {snapshot}`), then resume the consolidation (`{_RESUME}`)." in _render(report, "resume")


def test_a_refused_compare_and_swap_names_an_inspect_step_and_the_follow_up(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#7600 fold: a restore whose compare-and-swap was refused (a race) had no next step."""
    from specify_cli.consolidation import rollback
    from specify_cli.git.ref_advance import RefRestoreError

    state = _advanced_state(repo)

    def _race(*_args: object, **_kwargs: object) -> None:
        raise RefRestoreError("cannot lock ref: is at another sha but expected the recorded one")

    monkeypatch.setattr(rollback, "restore_branch_ref", _race)

    report = rollback_to_snapshot(repo, state, target_branch="main")

    assert any(o.branch == "main" and o.kind is BranchOutcomeKind.NOT_RESTORED for o in report.outcomes)
    abort_text = _render(report, "abort")
    assert f"main: inspect it (`git log -3 main`), then {_ABORT_RERUN}." in abort_text
    assert "--resume" not in abort_text
    assert f"main: inspect it (`git log -3 main`), then resume the consolidation (`{_RESUME}`)." in _render(report, "resume")


# --------------------------------------------------------------------------- the --abort command


def test_abort_over_a_dirty_checkout_names_it_and_says_re_run_abort(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _advanced_state(repo)
    checkout = _dirty_main_checkout(repo)

    code, output = _cli_abort(repo, monkeypatch)

    assert code == 1, output
    assert str(checkout) in output
    assert _ABORT_RERUN in output
    assert "--resume" not in output
    assert "resolve the branches named above" not in output


def test_abort_over_a_foreign_commit_names_the_release_command(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _advanced_state(repo)
    _commit(repo, "main", "teammate")

    code, output = _cli_abort(repo, monkeypatch)

    assert code == 1, output
    assert 'spec-kitty consolidate --abort --release-branch main --release-reason "<why>"' in output
    assert "--resume" not in output


def test_abort_over_a_verified_landing_offers_the_labelled_resume(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _advanced_state(repo)
    state.reconciliation_passed_target_sha = _git(repo, "rev-parse", "main")
    save_state(state, repo)

    code, output = _cli_abort(repo, monkeypatch)

    assert code == 1, output
    assert f"To finish the teardown of this landing instead, run `{_RESUME}`" in output
    assert "resolve the branches named above" not in output


# --------------------------------------------------------------------------- the consolidate fresh/resume path


def test_a_lane_merge_refused_by_a_dirty_checkout_keeps_the_resume_hint() -> None:
    from specify_cli.lanes.consolidation import lane_merge_error_text

    exc = RefAdvanceDirtyWorktreeError(
        worktree_path=Path("/tmp/wt"),
        branch="kitty/mission-x",
        old_sha="a" * 40,
        new_sha="b" * 40,
        dirty_entries=[" M README.md"],
    )

    text = _flat(lane_merge_error_text(exc))

    assert text.startswith(_flat(str(exc)))
    assert f"Then resume the consolidation (`{_RESUME}`)" in text
    assert lane_merge_error_text(RuntimeError("boom")) == "boom"
