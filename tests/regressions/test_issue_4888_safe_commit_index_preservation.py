"""Regression test for issue #4888: ``safe_commit`` must never wipe the
operator's index.

Pre-fix, ``safe_commit`` preserved the operator's unrelated staged changes by
running ``git stash push --staged`` before committing the requested paths,
then ``git stash pop --index`` to restore them afterward. That pop is
deterministically REFUSED by git whenever any stashed path also carries an
unstaged modification -- an everyday ``git add -p`` partial-stage state.
When that happened, ALL of the stashed content (not just the conflicting
file) stayed stranded in an un-poppable stash, and ``upgrade`` swallowed the
resulting ``SafeCommitRecoveryFailed`` into a misleading "please commit
manually" exit-0 warning that never named the stash or the landed SHA.

The fix (T024) rewrites ``safe_commit`` to stage and commit EXACTLY the
requested paths via ``git commit --only -- <paths>``, which structurally
disregards whatever else is staged -- there is no stash/pop dance, so the
operator's index (including a partially-staged unrelated file) is never
read, moved, or mutated in the first place.

This file exercises that invariant directly against ``safe_commit`` (the
hot, shared helper) and against every caller this WP's tracer audit found
to route real user-facing commits through it: ``agent mission create``,
``agent mission finalize-tasks``, ``spec-kitty implement``'s WP-claim commit,
and ``spec-kitty upgrade``'s auto-commit step -- plus the ``upgrade``
forced-failure path that must surface (never swallow) a
``SafeCommitRecoveryFailed``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed, safe_commit
from mission_runtime import CommitTarget

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]

_BRANCH = "kitty/mission-test-01ABCDEF"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("# seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", "-M", _BRANCH)
    return repo


def _seed_partially_staged_unrelated_file(repo: Path) -> None:
    """Create the exact partial-stage shape that broke ``git stash pop --index``.

    ``partial.txt`` gets a STAGED hunk (the ``git add`` below) followed by a
    further UNSTAGED edit on top -- ``git status --porcelain`` reports it as
    ``MM``. ``fully_staged.txt`` is a second, fully-staged unrelated file, so
    the fix is verified against both shapes at once.
    """
    partial = repo / "partial.txt"
    partial.write_text("base\n", encoding="utf-8")
    _git(repo, "add", "partial.txt")
    _git(repo, "commit", "-q", "-m", "add partial")

    partial.write_text("staged change\n", encoding="utf-8")
    _git(repo, "add", "partial.txt")
    partial.write_text("staged change\nunstaged tail\n", encoding="utf-8")

    fully_staged = repo / "fully_staged.txt"
    fully_staged.write_text("fully staged content\n", encoding="utf-8")
    _git(repo, "add", "fully_staged.txt")

    status = _git(repo, "status", "--porcelain").stdout
    assert "MM partial.txt" in status, f"fixture setup did not reproduce the MM shape: {status!r}"
    assert "A  fully_staged.txt" in status


def _cached_and_stash_snapshot(repo: Path) -> tuple[str, str]:
    return (
        _git(repo, "diff", "--cached").stdout,
        _git(repo, "stash", "list").stdout,
    )


# ---------------------------------------------------------------------------
# Control + Case 1 (T023): direct safe_commit invariant
# ---------------------------------------------------------------------------


def test_control_fully_staged_unrelated_file_survives_safe_commit(tmp_path: Path) -> None:
    """Control: an unrelated file that is FULLY staged is untouched by safe_commit."""
    repo = _init_repo(tmp_path)
    unrelated = repo / "unrelated.txt"
    unrelated.write_text("keep me staged\n", encoding="utf-8")
    _git(repo, "add", "unrelated.txt")

    before_cached, before_stash = _cached_and_stash_snapshot(repo)

    wp_file = repo / "WP01.md"
    wp_file.write_text("---\nlane: doing\n---\n", encoding="utf-8")
    result = safe_commit(
        repo_root=repo,
        worktree_root=repo,
        destination_ref=_BRANCH,
        message="Update WP01 status",
        paths=(wp_file,),
    )
    assert result.sha

    after_cached, after_stash = _cached_and_stash_snapshot(repo)
    assert after_cached == before_cached, "unrelated fully-staged content must be byte-identical"
    assert after_stash == before_stash == "", "no stash must ever be created"

    status = _git(repo, "status", "--porcelain").stdout
    assert "A  unrelated.txt" in status
    assert "WP01.md" not in status


def test_partially_staged_unrelated_file_survives_safe_commit(tmp_path: Path) -> None:
    """Case 1 (RED on base, #4888): a PARTIALLY staged unrelated file, plus a
    fully-staged one, is byte-identical (index AND stash list) before and
    after ``safe_commit`` commits an unrelated new path.

    Pre-fix, ``git stash push --staged`` would sweep ``partial.txt``'s staged
    hunk into a stash, then ``git stash pop --index`` would be refused
    because ``partial.txt`` still carries an unstaged hunk on disk -- leaving
    BOTH ``partial.txt``'s staged hunk AND ``fully_staged.txt`` stranded in
    an un-poppable stash.
    """
    repo = _init_repo(tmp_path)
    _seed_partially_staged_unrelated_file(repo)

    before_cached, before_stash = _cached_and_stash_snapshot(repo)

    wp_file = repo / "WP07.md"
    wp_file.write_text("---\nlane: doing\n---\n", encoding="utf-8")
    result = safe_commit(
        repo_root=repo,
        worktree_root=repo,
        destination_ref=_BRANCH,
        message="Update WP07 status",
        paths=(wp_file,),
    )
    assert result.sha

    after_cached, after_stash = _cached_and_stash_snapshot(repo)
    assert after_cached == before_cached, "partially-staged unrelated content must be byte-identical"
    assert after_stash == before_stash == "", "no stash must ever be created (this is the #4888 repro)"

    status = _git(repo, "status", "--porcelain").stdout
    assert "MM partial.txt" in status
    assert "A  fully_staged.txt" in status
    assert "WP07.md" not in status

    tracked = _git(repo, "log", "-1", "--format=%s").stdout.strip()
    assert tracked == "Update WP07 status"


def test_partially_staged_survives_multiple_paths_and_deletion(tmp_path: Path) -> None:
    """Belt-and-braces: multiple requested paths, including a deletion,
    still leave a partially-staged unrelated file untouched."""
    repo = _init_repo(tmp_path)

    # Seed + commit `doomed.md` on its OWN, BEFORE any unrelated content gets
    # staged -- so the later unrelated staging is not accidentally swept into
    # this commit too.
    doomed = repo / "doomed.md"
    doomed.write_text("to be deleted\n", encoding="utf-8")
    _git(repo, "add", "doomed.md")
    _git(repo, "commit", "-q", "-m", "seed doomed")

    _seed_partially_staged_unrelated_file(repo)
    doomed.unlink()

    keep = repo / "WP08.md"
    keep.write_text("---\nlane: doing\n---\n", encoding="utf-8")

    before_cached, before_stash = _cached_and_stash_snapshot(repo)

    result = safe_commit(
        repo_root=repo,
        worktree_root=repo,
        destination_ref=_BRANCH,
        message="Update WP08 status and remove doomed.md",
        paths=(keep, doomed),
    )
    assert result.sha

    after_cached, after_stash = _cached_and_stash_snapshot(repo)
    assert after_cached == before_cached
    assert after_stash == before_stash == ""

    tracked = _git(repo, "ls-files", "doomed.md").stdout.strip()
    assert tracked == "", "doomed.md must be committed as a deletion"


# ---------------------------------------------------------------------------
# upgrade auto-commit path
# ---------------------------------------------------------------------------


def test_upgrade_autocommit_preserves_partially_staged_unrelated_file(tmp_path: Path) -> None:
    """``upgrade``'s auto-commit step (``commit_touched_checkout``) inherits
    the same index-preservation guarantee -- it is a thin wrapper over
    ``safe_commit`` with no staging logic of its own."""
    from specify_cli.upgrade import autocommit

    repo = _init_repo(tmp_path)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    _git(repo, "add", ".kittify/config.json")
    _git(repo, "commit", "-q", "-m", "seed .kittify")

    _seed_partially_staged_unrelated_file(repo)

    before_cached, before_stash = _cached_and_stash_snapshot(repo)

    baseline = autocommit.capture_upgrade_baseline(repo)
    churned = repo / ".kittify" / "upgraded.txt"
    churned.write_text("upgrade churn\n", encoding="utf-8")

    committed, paths, warning = autocommit.commit_touched_checkout(
        repo,
        baseline,
        "3.0.0",
        "3.0.1",
    )

    after_cached, after_stash = _cached_and_stash_snapshot(repo)
    assert after_cached == before_cached
    assert after_stash == before_stash == ""

    assert committed is True, f"expected the upgrade churn to commit cleanly, warning={warning!r}"
    assert any("upgraded.txt" in p for p in paths)

    status = _git(repo, "status", "--porcelain").stdout
    assert "MM partial.txt" in status
    assert "A  fully_staged.txt" in status


def test_upgrade_forced_failure_surfaces_stash_ref_and_landed_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T025 (defense-in-depth): if ``safe_commit`` ever raises
    ``SafeCommitRecoveryFailed`` again (residual path — the root fix removes
    the only production trigger, so this forces it via injection, exactly as
    the WP's reviewer guidance calls out), ``commit_touched_checkout`` must
    propagate it VERBATIM rather than flattening it into the generic
    ``UPGRADE_COMMIT_SKIP_WARNING`` -- an exit-0 "please commit manually"
    that hides the stash ref and misstates whether the commit landed.
    """
    from specify_cli.upgrade import autocommit

    repo = _init_repo(tmp_path)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    _git(repo, "add", ".kittify/config.json")
    _git(repo, "commit", "-q", "-m", "seed .kittify")

    baseline = autocommit.capture_upgrade_baseline(repo)
    churned = repo / ".kittify" / "upgraded.txt"
    churned.write_text("upgrade churn\n", encoding="utf-8")

    landed_sha = "deadbeefcafef00dfeedfacedeadbeefcafef00d"
    injected = SafeCommitRecoveryFailed(
        "safe_commit: failed to restore caller staging (forced by test)",
        destination_ref=_BRANCH,
        worktree_root=repo,
        orphan_stash_ref="stash@{0}",
        commit_sha=landed_sha,
    )

    def _raise_recovery_failed(**_kwargs: object) -> None:
        raise injected

    monkeypatch.setattr(autocommit, "safe_commit", _raise_recovery_failed)

    with pytest.raises(SafeCommitRecoveryFailed) as excinfo:
        autocommit.commit_touched_checkout(repo, baseline, "3.0.0", "3.0.1")

    assert excinfo.value is injected
    assert excinfo.value.orphan_stash_ref == "stash@{0}"
    assert excinfo.value.commit_sha == landed_sha

    # cli/commands/upgrade.py renders the stash ref + landed SHA and must not
    # exit 0 with a message that hides either.
    from specify_cli.cli.commands.upgrade import _render_safe_commit_recovery_failed

    rendered = _render_safe_commit_recovery_failed(injected)
    assert landed_sha in rendered
    assert "stash@{0}" in rendered
    assert "DID land" in rendered


def test_upgrade_finalizer_step_flips_exit_code_non_zero_on_recovery_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The finalizer's ``commit_churn`` step must turn a forced
    ``SafeCommitRecoveryFailed`` into a non-zero-exit-code, rendered error --
    never a silent exit-0 skip warning."""
    from specify_cli.cli.commands import upgrade as upgrade_cmd
    from specify_cli.upgrade import autocommit
    from specify_cli.upgrade.outcome import UpgradeOutcome
    from specify_cli.upgrade.runner import UpgradeResult

    repo = _init_repo(tmp_path)

    injected = SafeCommitRecoveryFailed(
        "safe_commit: failed to restore caller staging (forced by test)",
        destination_ref=_BRANCH,
        worktree_root=repo,
        orphan_stash_ref="stash@{0}",
        commit_sha="cafed00d" * 5,
    )

    def _raise(*_args: object, **_kwargs: object) -> tuple[bool, list[str], str | None]:
        raise injected

    monkeypatch.setattr(autocommit, "commit_touched_checkout", _raise)

    outcome = UpgradeOutcome(result=UpgradeResult(success=True, from_version="3.0.0", to_version="3.0.1"))
    ctx = upgrade_cmd._FinalizerRenderContext()

    committed = upgrade_cmd._finalizer_step_commit_churn(
        outcome,
        ctx,
        project_path=repo,
        baseline_changed_paths=None,
    )

    assert committed is False
    assert outcome.result.success is False
    assert outcome.result.errors, "the recovery-failed message must land in result.errors"
    assert "cafed00d" * 5 in outcome.result.errors[0]
    assert "stash@{0}" in outcome.result.errors[0]

    outcome.derive_exit_code()
    assert outcome.exit_code != 0, "a forced SafeCommitRecoveryFailed must never leave the upgrade exit code at 0"


# ---------------------------------------------------------------------------
# agent mission create / finalize-tasks / implement claim
# ---------------------------------------------------------------------------


def test_mission_create_preserves_partially_staged_unrelated_file(tmp_path: Path) -> None:
    """``spec-kitty agent mission create`` drives ``create_mission_core``
    (``core/mission_creation.py``), which commits its scaffold via
    ``safe_commit`` (``_commit_feature_file``). This exercises the REAL
    production entry point -- not a hand-mimicked ``safe_commit`` call -- so
    the partial-stage invariant is verified end-to-end for this caller."""
    from mission_runtime import MissionTopology
    from specify_cli.core.mission_creation import create_mission_core
    from tests._factories import provision_test_charter

    repo = tmp_path
    (repo / ".kittify").mkdir(exist_ok=True)
    provision_test_charter(repo)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    (repo / "kitty-specs" / ".gitkeep").touch()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    _git(repo, "branch", "-M", "main")
    _git(repo, "checkout", "-b", "feat/repro")

    _seed_partially_staged_unrelated_file(repo)

    before_cached, before_stash = _cached_and_stash_snapshot(repo)

    result = create_mission_core(
        repo,
        "issue-4888",
        topology=MissionTopology.SINGLE_BRANCH,
        allow_worktree_context=True,
        friendly_name="Issue 4888",
        purpose_tldr="Deliver issue 4888 cleanly for the team.",
        purpose_context="This mission delivers issue 4888 so product and engineering can move forward with a clear outcome and shared understanding.",
    )
    assert result.feature_dir.exists()

    after_cached, after_stash = _cached_and_stash_snapshot(repo)
    assert after_cached == before_cached
    assert after_stash == before_stash == ""

    status = _git(repo, "status", "--porcelain").stdout
    assert "MM partial.txt" in status
    assert "A  fully_staged.txt" in status


def test_finalize_tasks_preserves_partially_staged_unrelated_file(tmp_path: Path) -> None:
    """``spec-kitty agent mission finalize-tasks`` writes ``lanes.json`` +
    task manifests and commits them through ``safe_commit`` on the same
    ``CommitTarget`` contract; the partial-stage invariant must hold there
    too."""
    repo = _init_repo(tmp_path)
    _seed_partially_staged_unrelated_file(repo)

    before_cached, before_stash = _cached_and_stash_snapshot(repo)

    lanes = repo / "kitty-specs" / "demo-mission" / "lanes.json"
    lanes.parent.mkdir(parents=True)
    lanes.write_text("{}\n", encoding="utf-8")
    wp01 = repo / "kitty-specs" / "demo-mission" / "tasks" / "WP01.md"
    wp01.parent.mkdir(parents=True)
    wp01.write_text("---\nwork_package_id: WP01\n---\n", encoding="utf-8")

    result = safe_commit(
        repo_root=repo,
        worktree_root=repo,
        target=CommitTarget(ref=_BRANCH),
        message="chore: finalize tasks for demo-mission",
        paths=(lanes, wp01),
        capability=GuardCapability.STANDARD,
    )
    assert result.sha

    after_cached, after_stash = _cached_and_stash_snapshot(repo)
    assert after_cached == before_cached
    assert after_stash == before_stash == ""


def test_implement_claim_preserves_partially_staged_unrelated_file(tmp_path: Path) -> None:
    """``spec-kitty implement``'s WP-claim status commit
    (``coordination.status_transition`` -> ``safe_commit``) must not
    disturb a partially-staged unrelated file either -- exercised directly
    against ``safe_commit`` on the WP-lane worktree's own branch, which is
    exactly what the status-commit call site does."""
    repo = _init_repo(tmp_path)
    _seed_partially_staged_unrelated_file(repo)

    before_cached, before_stash = _cached_and_stash_snapshot(repo)

    events = repo / "kitty-specs" / "demo-mission" / "status.events.jsonl"
    events.parent.mkdir(parents=True)
    events.write_text('{"to_lane":"claimed","wp_id":"WP01"}\n', encoding="utf-8")

    result = safe_commit(
        repo_root=repo,
        worktree_root=repo,
        target=CommitTarget(ref=_BRANCH),
        message="chore(demo-mission): WP01 claimed",
        paths=(events,),
        capability=GuardCapability.STANDARD,
    )
    assert result.sha

    after_cached, after_stash = _cached_and_stash_snapshot(repo)
    assert after_cached == before_cached
    assert after_stash == before_stash == ""
