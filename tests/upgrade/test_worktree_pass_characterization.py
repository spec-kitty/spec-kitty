"""Characterization net for the upgrade worktree pass (#7405, slice S2 of epic #3347).

Pinned BEFORE ``MigrationRunner._upgrade_worktrees`` was split into a plan step and
an apply step (``specify_cli.upgrade.worktree_pass``), and kept green across that
move. Each test drives the pass in process, through the runner's own entry point,
with a scripted migration that takes exactly one branch of the per-migration loop,
and pins everything the pass reports and writes for it:

* the returned report (``warnings``, ``errors``, ``worktree_failures``, and the
  outcome per worktree), compared whole, so a reordered or reworded line fails;
* the worktree's ledger records (which result, if any, is persisted);
* the worktree's metadata version and ``schema_version`` stamp;
* whether an upgrade commit landed on the worktree's branch.

The fixture is a real git repository with non-Mission worktrees on ``wip/``
branches (Mission worktrees are skipped by the pass, #5457), selected with
``WorktreeSelection.all()``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from kernel.git import GitCommandError
from specify_cli.gitignore_manager import GitignorePathError
from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION
from specify_cli.upgrade import autocommit
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult, MigrationStateUnreadableError
from specify_cli.upgrade.runner import MigrationRunner
from specify_cli.upgrade.worktree_selection import WorktreeSelection
from tests.upgrade.test_worktree_stamp_guard import _STALE_SCHEMA_VERSION, _TARGET_VERSION, _add_worktree, _init_repo, _wt_schema_version

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

WT = "wip-a"
PREFIX = f"Worktree {WT}: "
#: The one no-commit line a worktree whose run failed (or errored) and left changes gets.
LEFT_UNCOMMITTED = PREFIX + autocommit.FAILED_RUN_LEFT_UNCOMMITTED_WARNING


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def _head(cwd: Path) -> str:
    return _git(cwd, "rev-parse", "HEAD").strip()


def _git_error(cwd: Path) -> GitCommandError:
    return GitCommandError(argv=("status",), cwd=cwd, returncode=128, stderr="fatal: boom\n")


@dataclass
class Script:
    """What one scripted migration does at each step; a callable raises or returns."""

    detect: bool | Exception = True
    can_apply: tuple[bool, str] = (True, "")
    apply: MigrationResult | Exception = field(default_factory=lambda: MigrationResult(success=True, changes_made=["changed"]))
    runs_on_worktrees: bool = True
    calls: list[str] = field(default_factory=list)


def _migration(migration_id: str, script: Script) -> BaseMigration:
    class _Scripted(BaseMigration):
        description = f"characterization stub {migration_id}"
        target_version = _TARGET_VERSION
        runs_on_worktrees = script.runs_on_worktrees

        def detect(self, project_path: Path) -> bool:
            script.calls.append("detect")
            if isinstance(script.detect, Exception):
                raise script.detect
            return script.detect

        def can_apply(self, project_path: Path) -> tuple[bool, str]:
            script.calls.append("can_apply")
            return script.can_apply

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
            script.calls.append(f"apply(dry_run={dry_run})")
            if isinstance(script.apply, Exception):
                raise script.apply
            return script.apply

    _Scripted.migration_id = migration_id
    _Scripted.__name__ = f"Scripted_{migration_id}"
    return _Scripted()


@pytest.fixture()
def project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    _init_repo(root)
    return root, _add_worktree(root, WT, "wip/a")


def _run(
    root: Path,
    migrations: list[BaseMigration],
    *,
    dry_run: bool = False,
    auto_commit: bool = True,
    selection: WorktreeSelection | None = None,
) -> dict[str, Any]:
    return MigrationRunner(root)._upgrade_worktrees(
        _TARGET_VERSION,
        migrations,
        dry_run,
        auto_commit=auto_commit,
        worktree_selection=WorktreeSelection.all() if selection is None else selection,
    )


def _report(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "warnings": result["warnings"],
        "errors": result["errors"],
        "worktree_failures": result["worktree_failures"],
        "outcomes": [(run.disposition.path.name, run.outcome.value) for run in result["worktree_results"]],
    }


def _ledger(worktree: Path) -> list[tuple[str, str]]:
    return [(record.id, record.result) for record in MigrationLedger(worktree).read_all()]


def _version(worktree: Path) -> str:
    import yaml

    data = yaml.safe_load((worktree / ".kittify" / "metadata.yaml").read_text(encoding="utf-8-sig"))
    return str(data["spec_kitty"]["version"])


STAMPED = REQUIRED_SCHEMA_VERSION
UNSTAMPED = _STALE_SCHEMA_VERSION


def _assert_worktree(worktree: Path, head_before: str, *, ledger: list[tuple[str, str]], version: str, schema: int | None, committed: bool) -> None:
    assert _ledger(worktree) == ledger
    assert _version(worktree) == version
    assert _wt_schema_version(worktree / ".kittify") == schema
    assert (_head(worktree) != head_before) is committed


# ---------------------------------------------------------------------------
# One branch of the per-migration loop per test
# ---------------------------------------------------------------------------


def test_successful_migration_records_success_and_commits(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)
    script = Script(apply=MigrationResult(success=True, changes_made=["did a", "did b"], warnings=["heads up"]))

    result = _run(root, [_migration("char_success", script)])

    assert _report(result) == {
        "warnings": [PREFIX + "heads up"],
        "errors": [],
        "worktree_failures": [],
        "outcomes": [(WT, "upgraded_committed")],
    }
    assert script.calls == ["detect", "can_apply", "apply(dry_run=False)"]
    _assert_worktree(wt, head, ledger=[("char_success", "success")], version=_TARGET_VERSION, schema=STAMPED, committed=True)
    assert _git(wt, "status", "--porcelain") == ""


def test_successful_migration_without_auto_commit_is_not_committed(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)

    result = _run(root, [_migration("char_success", Script())], auto_commit=False)

    assert _report(result)["outcomes"] == [(WT, "upgraded_not_committed")]
    assert result["warnings"] == []
    _assert_worktree(wt, head, ledger=[("char_success", "success")], version=_TARGET_VERSION, schema=STAMPED, committed=False)


def test_not_needed_migration_records_skipped(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)
    script = Script(detect=False)

    result = _run(root, [_migration("char_not_needed", script)])

    assert _report(result) == {"warnings": [], "errors": [], "worktree_failures": [], "outcomes": [(WT, "upgraded_committed")]}
    assert script.calls == ["detect"]
    _assert_worktree(wt, head, ledger=[("char_not_needed", "skipped")], version=_TARGET_VERSION, schema=STAMPED, committed=True)


def test_already_settled_migration_is_not_probed(project: tuple[Path, Path]) -> None:
    root, wt = project
    script = Script()
    migration = _migration("char_settled", script)
    MigrationLedger(wt).append(build_record(migration, "success"))
    head = _head(wt)

    result = _run(root, [migration])

    assert script.calls == []
    assert _report(result) == {"warnings": [], "errors": [], "worktree_failures": [], "outcomes": [(WT, "upgraded_committed")]}
    # The ledger written above was uncommitted before the run, so it stays out of the
    # commit-set; the run's own metadata bump is committed.
    assert _ledger(wt) == [("char_settled", "success")]
    assert _version(wt) == _TARGET_VERSION
    assert _head(wt) != head
    assert "migration-ledger.jsonl" in _git(wt, "status", "--porcelain")


@pytest.mark.parametrize(
    ("raised", "reason"),
    [
        (GitignorePathError("ignore file is a symlink"), "ignore file is a symlink"),
        (MigrationStateUnreadableError("state unreadable"), "state unreadable"),
    ],
    ids=["gitignore-path", "state-unreadable"],
)
def test_detect_error_is_a_recorded_fatal_failure(project: tuple[Path, Path], raised: Exception, reason: str) -> None:
    root, wt = project
    head = _head(wt)
    script = Script(detect=raised)

    result = _run(root, [_migration("char_detect_error", script)])

    message = PREFIX + f"Cannot safely detect char_detect_error: {reason}"
    assert _report(result) == {"warnings": [LEFT_UNCOMMITTED], "errors": [message], "worktree_failures": [message], "outcomes": [(WT, "failed")]}
    assert script.calls == ["detect"]
    # An errored (not failed) worktree keeps the schema stamp rule unchanged, but commits nothing.
    _assert_worktree(wt, head, ledger=[("char_detect_error", "failed")], version=_TARGET_VERSION, schema=STAMPED, committed=False)


def test_detect_git_error_names_git(project: tuple[Path, Path]) -> None:
    root, wt = project
    error = _git_error(wt)

    result = _run(root, [_migration("char_detect_git", Script(detect=error))])

    message = PREFIX + f"Cannot safely detect char_detect_git: git failed ({error})"
    assert result["errors"] == [message]
    assert result["worktree_failures"] == [message]
    assert _ledger(wt) == [("char_detect_git", "failed")]


def test_can_apply_refusal_is_a_warning_and_records_nothing(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)
    script = Script(can_apply=(False, "not this tree"))

    result = _run(root, [_migration("char_refused", script)])

    assert _report(result) == {
        "warnings": [PREFIX + "Cannot apply char_refused: not this tree"],
        "errors": [],
        "worktree_failures": [],
        "outcomes": [(WT, "upgraded_committed")],
    }
    assert script.calls == ["detect", "can_apply"]
    _assert_worktree(wt, head, ledger=[], version=_TARGET_VERSION, schema=STAMPED, committed=True)


def test_apply_git_error_is_a_recorded_failed_apply(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)
    error = _git_error(wt)

    result = _run(root, [_migration("char_apply_git", Script(apply=error))])

    message = PREFIX + f"Cannot apply char_apply_git: git failed ({error})"
    assert _report(result) == {"warnings": [LEFT_UNCOMMITTED], "errors": [message], "worktree_failures": [message], "outcomes": [(WT, "failed")]}
    # A failed worktree keeps its old schema stamp (FR-009 / #3376).
    _assert_worktree(wt, head, ledger=[("char_apply_git", "failed")], version=_TARGET_VERSION, schema=UNSTAMPED, committed=False)


@pytest.mark.parametrize(
    "raised",
    [GitignorePathError("symlinked ignore"), MigrationStateUnreadableError("unreadable state")],
    ids=["gitignore-path", "state-unreadable"],
)
def test_apply_unsafe_error_is_unrecorded_and_fatal(project: tuple[Path, Path], raised: Exception) -> None:
    root, wt = project
    head = _head(wt)

    result = _run(root, [_migration("char_apply_unsafe", Script(apply=raised))])

    message = PREFIX + f"Cannot apply char_apply_unsafe: {raised}"
    assert _report(result) == {"warnings": [LEFT_UNCOMMITTED], "errors": [message], "worktree_failures": [message], "outcomes": [(WT, "failed")]}
    _assert_worktree(wt, head, ledger=[], version=_TARGET_VERSION, schema=STAMPED, committed=False)


def test_failed_apply_with_errors_reports_each_error(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)
    script = Script(apply=MigrationResult(success=False, errors=["first", "second"], warnings=["dropped"]))

    result = _run(root, [_migration("char_failed", script)])

    assert _report(result) == {
        "warnings": [LEFT_UNCOMMITTED],
        "errors": [PREFIX + "first", PREFIX + "second"],
        "worktree_failures": [PREFIX + "first", PREFIX + "second"],
        "outcomes": [(WT, "failed")],
    }
    _assert_worktree(wt, head, ledger=[("char_failed", "failed")], version=_TARGET_VERSION, schema=UNSTAMPED, committed=False)


def test_failed_apply_without_errors_still_reports_one_line(project: tuple[Path, Path]) -> None:
    root, wt = project

    result = _run(root, [_migration("char_silent", Script(apply=MigrationResult(success=False)))])

    message = PREFIX + "Migration char_silent failed"
    assert result["errors"] == [message]
    assert result["worktree_failures"] == [message]


def test_held_paths_are_named_and_do_not_block_the_commit(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)
    held = MigrationResult(success=True, changes_made=["kept"], manual_review_required=True, preserved_paths=["b.md", "a.md"])

    result = _run(root, [_migration("char_held", Script(apply=held))])

    assert result["errors"] == []
    assert result["warnings"] == [PREFIX + autocommit.HELD_FOR_REVIEW_NOT_COMMITTED_WARNING.format(paths="a.md, b.md")]
    assert _report(result)["outcomes"] == [(WT, "upgraded_committed")]
    _assert_worktree(wt, head, ledger=[("char_held", "success")], version=_TARGET_VERSION, schema=STAMPED, committed=True)


def test_failure_is_sticky_for_the_schema_stamp_and_later_migrations_still_run(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)
    first = Script(apply=MigrationResult(success=False, errors=["broke"]))
    second = Script(apply=MigrationResult(success=True, changes_made=["ok"], warnings=["later"]))

    result = _run(root, [_migration("char_first", first), _migration("char_second", second)])

    assert _report(result) == {
        "warnings": [PREFIX + "later", LEFT_UNCOMMITTED],
        "errors": [PREFIX + "broke"],
        "worktree_failures": [PREFIX + "broke"],
        "outcomes": [(WT, "failed")],
    }
    assert second.calls == ["detect", "can_apply", "apply(dry_run=False)"]
    _assert_worktree(wt, head, ledger=[("char_first", "failed"), ("char_second", "success")], version=_TARGET_VERSION, schema=UNSTAMPED, committed=False)


# ---------------------------------------------------------------------------
# Pass-level behaviour
# ---------------------------------------------------------------------------


def test_dry_run_writes_nothing_but_still_reports(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)
    metadata_before = (wt / ".kittify" / "metadata.yaml").read_bytes()
    script = Script(apply=MigrationResult(success=True, changes_made=["would"], warnings=["preview"]))

    result = _run(root, [_migration("char_dry", script)], dry_run=True)

    assert _report(result) == {"warnings": [PREFIX + "preview"], "errors": [], "worktree_failures": [], "outcomes": [(WT, "nothing_to_upgrade")]}
    assert script.calls == ["detect", "can_apply", "apply(dry_run=True)"]
    assert (wt / ".kittify" / "metadata.yaml").read_bytes() == metadata_before
    assert _ledger(wt) == []
    assert _head(wt) == head


def test_dry_run_failure_is_reported_but_not_recorded(project: tuple[Path, Path]) -> None:
    root, wt = project

    result = _run(root, [_migration("char_dry_fail", Script(apply=MigrationResult(success=False, errors=["no"])))], dry_run=True)

    assert result["worktree_failures"] == [PREFIX + "no"]
    assert _report(result)["outcomes"] == [(WT, "nothing_to_upgrade")]
    assert _ledger(wt) == []


def test_no_selection_probes_nothing(project: tuple[Path, Path]) -> None:
    root, wt = project
    script = Script()

    result = _run(root, [_migration("char_unselected", script)], selection=WorktreeSelection.none())

    assert script.calls == []
    assert _report(result) == {"warnings": [], "errors": [], "worktree_failures": [], "outcomes": [(WT, "skipped_not_selected")]}


def test_only_main_only_migrations_pending_probes_nothing(project: tuple[Path, Path]) -> None:
    root, wt = project
    script = Script(runs_on_worktrees=False)
    head = _head(wt)

    result = _run(root, [_migration("char_main_only", script)])

    assert script.calls == []
    assert _report(result)["outcomes"] == [(WT, "nothing_to_upgrade")]
    assert _version(wt) != _TARGET_VERSION
    assert _head(wt) == head


def test_worktree_without_upgradeable_state_is_left_alone(project: tuple[Path, Path]) -> None:
    root, wt = project
    _git(wt, "rm", "-q", "-r", ".kittify")
    _git(wt, "commit", "-q", "-m", "drop kittify")
    head = _head(wt)
    script = Script()

    result = _run(root, [_migration("char_bare", script)])

    assert script.calls == []
    assert _report(result) == {"warnings": [], "errors": [], "worktree_failures": [], "outcomes": [(WT, "nothing_to_upgrade")]}
    assert not (wt / ".kittify").exists()
    assert _head(wt) == head


def test_kitty_specs_alone_is_upgradeable_only_when_worktree_migrations_are_pending(project: tuple[Path, Path]) -> None:
    root, wt = project
    _git(wt, "rm", "-q", "-r", ".kittify")
    (wt / "kitty-specs").mkdir()
    (wt / "kitty-specs" / "README.md").write_text("specs\n", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "specs only")
    script = Script(detect=False)

    result = _run(root, [_migration("char_specs", script)], auto_commit=False)

    assert script.calls == ["detect"]
    assert _ledger(wt) == [("char_specs", "skipped")]
    assert _report(result)["outcomes"] == [(WT, "upgraded_not_committed")]


def test_no_migrations_bumps_version_only(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)

    result = _run(root, [])

    assert _report(result) == {"warnings": [], "errors": [], "worktree_failures": [], "outcomes": [(WT, "upgraded_committed")]}
    _assert_worktree(wt, head, ledger=[], version=_TARGET_VERSION, schema=STAMPED, committed=True)


def test_worktrees_run_in_name_order_and_each_reports_its_own_outcome(project: tuple[Path, Path]) -> None:
    root, wt_a = project
    wt_c = _add_worktree(root, "wip-c", "wip/c")
    wt_b = _add_worktree(root, "wip-b", "wip/b")
    seen: list[str] = []

    class _OrderProbe(BaseMigration):
        migration_id = "char_order"
        description = "order probe"
        target_version = _TARGET_VERSION

        def detect(self, project_path: Path) -> bool:
            seen.append(project_path.name)
            return project_path.name != "wip-b"

        def can_apply(self, project_path: Path) -> tuple[bool, str]:
            return True, ""

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
            if project_path.name == "wip-c":
                return MigrationResult(success=False, errors=["c broke"])
            return MigrationResult(success=True, changes_made=["ok"])

    result = _run(root, [_OrderProbe()])

    assert seen == ["wip-a", "wip-b", "wip-c"]
    assert _report(result) == {
        "warnings": ["Worktree wip-c: " + autocommit.FAILED_RUN_LEFT_UNCOMMITTED_WARNING],
        "errors": ["Worktree wip-c: c broke"],
        "worktree_failures": ["Worktree wip-c: c broke"],
        "outcomes": [("wip-a", "upgraded_committed"), ("wip-b", "upgraded_committed"), ("wip-c", "failed")],
    }
    assert _ledger(wt_a) == [("char_order", "success")]
    assert _ledger(wt_b) == [("char_order", "skipped")]
    assert _ledger(wt_c) == [("char_order", "failed")]


def test_upgrade_worktrees_only_runs_the_pass_with_no_migrations(project: tuple[Path, Path]) -> None:
    root, wt = project
    head = _head(wt)

    result = MigrationRunner(root).upgrade_worktrees_only(_TARGET_VERSION, auto_commit=True, worktree_selection=WorktreeSelection.all())

    assert sorted(result) == ["errors", "warnings", "worktree_failures", "worktree_results"]
    assert _report(result)["outcomes"] == [(WT, "upgraded_committed")]
    _assert_worktree(wt, head, ledger=[], version=_TARGET_VERSION, schema=STAMPED, committed=True)
