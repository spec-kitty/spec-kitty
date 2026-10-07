"""Pure-function coverage of the no-commit vocabulary of ``spec-kitty upgrade`` (#5443).

Every case where the upgrade does not commit prints exactly one explicit reason
(FR-023); held files are named (FR-021); an ignored-at-baseline path is never a
commit candidate (FR-020). No git, no subprocess: collaborators are monkeypatched.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands import upgrade as upgrade_cmd
from specify_cli.upgrade import autocommit
from specify_cli.upgrade import runner as upgrade_runner
from specify_cli.upgrade.outcome import UpgradeOutcome
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_METADATA = ".kittify/metadata.yaml"


# ---------------------------------------------------------------------------
# _under_ignored
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "ignored", "expected"),
    [
        (".kittify/workspaces/token.json", frozenset({".kittify/workspaces/"}), True),
        (".kittify/workspaces2/token.json", frozenset({".kittify/workspaces/"}), False),
        ("secrets.env", frozenset({"secrets.env"}), True),
        ("secrets.env.bak", frozenset({"secrets.env"}), False),
        (".kittify/workspaces", frozenset({".kittify/workspaces/"}), True),
        ("src/app.py", frozenset(), False),
    ],
)
def test_under_ignored(path: str, ignored: frozenset[str], expected: bool) -> None:
    assert autocommit._under_ignored(path, ignored) is expected


# ---------------------------------------------------------------------------
# commit_touched_checkout warnings
# ---------------------------------------------------------------------------


def _baseline(*paths: str) -> autocommit._GitStatusPaths:
    baseline = autocommit._GitStatusPaths()
    baseline.update(paths)
    return baseline


@pytest.fixture
def committing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(autocommit, "prepare_upgrade_commit_files", lambda _checkout, baseline_paths: [Path("src/new.py")])
    monkeypatch.setattr(autocommit, "safe_commit", lambda **_kw: None)
    monkeypatch.setattr(subprocess, "check_output", lambda *_a, **_kw: "work\n")


def test_successful_commit_reports_metadata_dirty_at_baseline(tmp_path: Path, committing: None) -> None:
    result = autocommit.commit_touched_checkout(tmp_path, _baseline(_METADATA), "2.1.0", "4.0.0")
    assert result == (True, ["src/new.py"], autocommit.METADATA_DIRTY_AT_BASELINE_WARNING)


def test_successful_commit_without_dirty_metadata_has_no_warning(tmp_path: Path, committing: None) -> None:
    result = autocommit.commit_touched_checkout(tmp_path, _baseline(), "2.1.0", "4.0.0")
    assert result == (True, ["src/new.py"], None)


def test_unavailable_baseline_returns_no_reason_here(tmp_path: Path) -> None:
    """The baseline-unavailable reason is produced by the CLI, never returned by the commit step."""
    assert autocommit.commit_touched_checkout(tmp_path, None, "2.1.0", "4.0.0") == (False, [], None)


# ---------------------------------------------------------------------------
# _no_commit_reason
# ---------------------------------------------------------------------------


def _outcome(*, success: bool = True, committed: bool = False, activation: bool = False, prepare: bool = False, held: tuple[str, ...] = ()) -> UpgradeOutcome:
    return UpgradeOutcome(
        result=UpgradeResult(success=success, from_version="2.1.0", to_version="4.0.0"),
        committed=committed,
        activation_errors=["boom"] if activation else [],
        repair_preparation_errors=["boom"] if prepare else [],
        manual_review_paths=[Path(path) for path in held],
    )


_DEFAULTS = {"dry_run": False, "should_commit_main": True, "baseline_available": True, "metadata_dirty_at_baseline": False, "churn_present": False}


@pytest.mark.parametrize(
    ("outcome_kwargs", "overrides", "expected"),
    [
        ({}, {"dry_run": True, "churn_present": True}, None),
        ({"committed": True}, {"churn_present": True}, None),
        ({"success": False}, {"churn_present": True}, autocommit.FAILED_RUN_LEFT_UNCOMMITTED_WARNING),
        ({"success": False}, {}, None),
        ({"success": False}, {"baseline_available": False, "churn_present": True}, autocommit.FAILED_RUN_LEFT_UNCOMMITTED_WARNING),
        ({}, {"should_commit_main": False, "churn_present": True}, None),
        ({}, {"baseline_available": False}, autocommit.BASELINE_UNAVAILABLE_WARNING),
        ({"activation": True}, {}, autocommit.REPAIR_ERRORS_LEFT_UNCOMMITTED_WARNING),
        ({"prepare": True}, {}, autocommit.REPAIR_ERRORS_LEFT_UNCOMMITTED_WARNING),
        ({}, {"metadata_dirty_at_baseline": True}, autocommit.METADATA_DIRTY_AT_BASELINE_WARNING),
        ({}, {"metadata_dirty_at_baseline": True, "churn_present": True}, None),
        ({}, {}, None),
    ],
)
def test_no_commit_reason_table(outcome_kwargs: dict[str, bool], overrides: dict[str, bool], expected: str | None) -> None:
    reason = upgrade_cmd._no_commit_reason(_outcome(**outcome_kwargs), **{**_DEFAULTS, **overrides})
    assert reason == expected


# ---------------------------------------------------------------------------
# _held_files_warning
# ---------------------------------------------------------------------------


def test_held_warning_when_committed_says_not_committed() -> None:
    warning = upgrade_cmd._held_files_warning(_outcome(committed=True, held=("b.md", "a.md")), dry_run=False)
    assert warning == "Held for manual review (not committed): a.md, b.md"


def test_held_warning_when_nothing_committed_keeps_the_skipped_wording() -> None:
    warning = upgrade_cmd._held_files_warning(_outcome(held=("b.md", "a.md")), dry_run=False)
    assert warning is not None
    assert warning.startswith("Skipped auto-commit")
    assert "2 file(s)" in warning
    assert "a.md, b.md" in warning


@pytest.mark.parametrize(
    ("outcome", "dry_run"),
    [(_outcome(), False), (_outcome(held=("a.md",)), True), (_outcome(success=False, held=("a.md",)), False)],
)
def test_held_warning_is_absent_without_held_files_or_for_dry_and_failed_runs(outcome: UpgradeOutcome, dry_run: bool) -> None:
    assert upgrade_cmd._held_files_warning(outcome, dry_run=dry_run) is None


# ---------------------------------------------------------------------------
# _report_commit_outcome (one reason, never doubled)
# ---------------------------------------------------------------------------


def test_report_adds_held_warning_and_one_reason(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(autocommit, "prepare_upgrade_commit_files", lambda _p, _b: [Path("x")])
    outcome = _outcome(success=False, held=("a.md",))
    upgrade_cmd._report_commit_outcome(outcome, dry_run=False, should_commit_main=False, project_path=tmp_path, baseline=set(), commit_warned=False)
    assert outcome.result.warnings == [autocommit.FAILED_RUN_LEFT_UNCOMMITTED_WARNING]


def test_report_adds_no_reason_when_the_commit_already_warned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(autocommit, "prepare_upgrade_commit_files", lambda _p, _b: [Path("x")])
    outcome = _outcome(held=("a.md",))
    upgrade_cmd._report_commit_outcome(outcome, dry_run=False, should_commit_main=True, project_path=tmp_path, baseline=set(), commit_warned=True)
    assert [w for w in outcome.result.warnings if w.startswith("Skipped auto-commit")]
    assert len(outcome.result.warnings) == 1


def test_report_names_an_unavailable_baseline(tmp_path: Path) -> None:
    outcome = _outcome()
    upgrade_cmd._report_commit_outcome(outcome, dry_run=False, should_commit_main=True, project_path=tmp_path, baseline=None, commit_warned=False)
    assert outcome.result.warnings == [autocommit.BASELINE_UNAVAILABLE_WARNING]


# ---------------------------------------------------------------------------
# upgraded worktrees (MigrationRunner._upgrade_worktrees helper)
# ---------------------------------------------------------------------------


def _worktree(tmp_path: Path) -> Path:
    path = tmp_path / "wt-a"
    path.mkdir()
    return path


def test_worktree_failed_run_with_changes_says_so_and_does_not_commit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(autocommit, "prepare_upgrade_commit_files", lambda _c, _b: [Path("x")])
    monkeypatch.setattr(autocommit, "commit_touched_checkout", lambda *_a, **_k: pytest.fail("a failed worktree must not commit"))
    warnings = upgrade_runner._commit_worktree_churn(_worktree(tmp_path), baseline=set(), from_version="2", to_version="4", failed=True, held_paths=["h.md"])
    assert warnings == [f"Worktree wt-a: {autocommit.FAILED_RUN_LEFT_UNCOMMITTED_WARNING}"]


def test_worktree_failed_run_without_changes_is_silent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(autocommit, "prepare_upgrade_commit_files", lambda _c, _b: [])
    assert upgrade_runner._commit_worktree_churn(_worktree(tmp_path), baseline=set(), from_version="2", to_version="4", failed=True, held_paths=[]) == []


def test_worktree_without_baseline_reports_it(tmp_path: Path) -> None:
    warnings = upgrade_runner._commit_worktree_churn(_worktree(tmp_path), baseline=None, from_version="2", to_version="4", failed=False, held_paths=[])
    assert warnings == [f"Worktree wt-a: {autocommit.BASELINE_UNAVAILABLE_WARNING}"]


def test_worktree_commit_names_held_files_as_not_committed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(autocommit, "commit_touched_checkout", lambda *_a, **_k: (True, ["x"], None))
    warnings = upgrade_runner._commit_worktree_churn(
        _worktree(tmp_path), baseline=set(), from_version="2", to_version="4", failed=False, held_paths=["a.md", "b.md"]
    )
    assert warnings == ["Worktree wt-a: Held for manual review (not committed): a.md, b.md"]


def test_worktree_without_commit_names_held_files_as_skipped_and_keeps_the_commit_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(autocommit, "commit_touched_checkout", lambda *_a, **_k: (False, ["x"], autocommit.UPGRADE_COMMIT_SKIP_WARNING))
    warnings = upgrade_runner._commit_worktree_churn(_worktree(tmp_path), baseline=set(), from_version="2", to_version="4", failed=False, held_paths=["a.md"])
    assert warnings[0] == f"Worktree wt-a: {autocommit.UPGRADE_COMMIT_SKIP_WARNING}"
    assert warnings[1].startswith("Worktree wt-a: Skipped auto-commit of 1 file(s)")
