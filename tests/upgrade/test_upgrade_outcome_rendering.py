"""What a completed ``spec-kitty upgrade`` prints, pinned through the real command.

Every test drives the real ``upgrade`` command in-process with ``CliRunner`` on a
real git-backed project; only the inputs the run depends on (the applicable
migrations, the repair inventory) are stubbed. The outcome object is never built
by hand here: the closing line, the JSON ``status`` and the exit code are all
read from what the command emitted.

The first group are golden characterisation tests: the full captured text of a
successful run, pinned before the single-outcome change and unchanged after it
(FR-006, FR-007, NFR-003).
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import upgrade as upgrade_module
from specify_cli.cli.console import console
from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed
from specify_cli.tool_surface.operations import Disposition, OwnerApplyResult, OwnerAssessment
from specify_cli.upgrade import assessment, autocommit
from specify_cli.upgrade.migrations.base import MigrationResult
from specify_cli.upgrade.outcome import SurfaceRepairReport, UpgradeOutcome
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_PROJECT_VERSION = "1.0.0a1"
_MIGRATED_VERSION = "3.2.0a4"
_MIGRATION_ID = "3.2.0a4_fake_migration"
_SKIPPED_ID = "3.1.0_old_migration"
_OWNER = "agent_profiles"
_DRIFTED_PATH = ".claude/agents/reviewer.md"
_PREVIEW_NOTICE = "Supporting repair preview incomplete: stub owner assessment."
_WORKTREE_FAILURE = "Worktree lane-x: stamp failed"
_MIGRATION_ERROR = "migration boom"
_ACTIVATION_ERROR = "forced activation failure"
_GOLDEN_WIDTH = 80
_GOLDEN_HEIGHT = 24

_METADATA_YAML = (
    "spec_kitty:\n"
    "  version: '{version}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade_module.upgrade)
_runner = CliRunner()


def _init_project(root: Path, *, version: str = _PROJECT_VERSION) -> None:
    """A minimal, real git-backed Spec Kitty project at *version*."""
    root.mkdir(parents=True, exist_ok=True)
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(_METADATA_YAML.format(version=version), encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


def _invoke(project: Path, args: list[str]) -> Any:
    with contextlib.chdir(project):
        return _runner.invoke(_test_app, args, catch_exceptions=False)


def _stub_applied_migration(
    monkeypatch: pytest.MonkeyPatch,
    *,
    success: bool = True,
    errors: tuple[str, ...] = (),
    worktree_failures: tuple[str, ...] = (),
) -> None:
    """One applicable migration that the (stubbed) runner applies, or fails to apply."""
    migration = MagicMock(migration_id=_MIGRATION_ID, description="fake migration", target_version=_MIGRATED_VERSION)
    monkeypatch.setattr("specify_cli.upgrade.registry.MigrationRegistry.get_applicable", lambda *_a, **_kw: [migration])

    def _upgrade(_self: object, target_version: str, **kwargs: Any) -> UpgradeResult:
        return UpgradeResult(
            success=success,
            from_version=_PROJECT_VERSION,
            to_version=target_version,
            dry_run=bool(kwargs.get("dry_run")),
            migrations_applied=[_MIGRATION_ID] if success else [],
            migrations_skipped=[_SKIPPED_ID],
            migration_results={_MIGRATION_ID: MigrationResult(success=True)},
            errors=list(errors),
            worktree_failures=list(worktree_failures),
        )

    monkeypatch.setattr("specify_cli.upgrade.runner.MigrationRunner.upgrade", _upgrade)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real project, with the banner silenced and a fixed render width."""
    monkeypatch.setattr(upgrade_module, "show_banner", lambda: None)
    console.size = (_GOLDEN_WIDTH, _GOLDEN_HEIGHT)  # the autouse render pin restores it after the test
    root = tmp_path / "project"
    _init_project(root)
    return root


_GOLDEN_NO_OP_WITH_WARNING = (
    "Current version: 1.0.0a1\nTarget version:  1.0.0a1\n\nProject is already up to date!\nWarning: one warning\n→ Auto-committed upgrade changes (2 files)\n"
)

_GOLDEN_APPLIED = (
    "Current version: 1.0.0a1\n"
    "Target version:  3.2.0a4\n"
    "\n"
    "                   Migration Plan                    \n"
    "┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┓\n"
    "┃ Migration              ┃ Description    ┃ Target  ┃\n"
    "┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━┩\n"
    "│ 3.2.0a4_fake_migration │ fake migration │ 3.2.0a4 │\n"
    "└────────────────────────┴────────────────┴─────────┘\n"
    "\n"
    "\n"
    "Migrations applied:\n"
    "  ✓ 3.2.0a4_fake_migration\n"
    "Migrations skipped (already applied or not needed):\n"
    "  ○ 3.1.0_old_migration\n"
    "\n"
    "Upgrade complete! 1.0.0a1 -> 3.2.0a4\n"
    "→ Auto-committed upgrade changes (1 files)\n"
)

_GOLDEN_APPLIED_DRY_RUN = (
    "Current version: 1.0.0a1\n"
    "Target version:  3.2.0a4\n"
    "\n"
    "                   Migration Plan                    \n"
    "┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┓\n"
    "┃ Migration              ┃ Description    ┃ Target  ┃\n"
    "┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━┩\n"
    "│ 3.2.0a4_fake_migration │ fake migration │ 3.2.0a4 │\n"
    "└────────────────────────┴────────────────┴─────────┘\n"
    "\n"
    "Would provision missing mission_type_activations (seeded on a real upgrade).\n"
    "Would repair 1 supporting surface paths (including 0 manifests). Use --plan-json\n"
    "for full repair details.\n"
    "\n"
    "╭──────────────────────────────────────────────────────────────────────────────╮\n"
    "│ DRY RUN - No changes were made                                               │\n"
    "╰──────────────────────────────────────────────────────────────────────────────╯\n"
    "Migrations applied:\n"
    "  ✓ 3.2.0a4_fake_migration\n"
    "Migrations skipped (already applied or not needed):\n"
    "  ○ 3.1.0_old_migration\n"
    "\n"
    "Dry run complete — no changes applied. (1.0.0a1 -> 3.2.0a4 previewed)\n"
)


def test_golden_no_op_with_one_warning(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A no-op run prints its closing line first, then each warning, then the commit line."""
    monkeypatch.setattr(upgrade_module, "_run_no_migrations_worktree_stamp", lambda *_a, **_kw: (["one warning"], []))

    result = _invoke(project, ["--target", _PROJECT_VERSION, "--yes", "--no-worktrees"])

    assert result.exit_code == 0, result.output
    assert result.output == _GOLDEN_NO_OP_WITH_WARNING


def test_golden_applied_run(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An applied run prints its sections, then the closing line, then the commit line."""
    _stub_applied_migration(monkeypatch)

    result = _invoke(project, ["--target", _MIGRATED_VERSION, "--yes", "--no-worktrees"])

    assert result.exit_code == 0, result.output
    assert result.output == _GOLDEN_APPLIED


def test_golden_applied_dry_run(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A completed dry run says nothing was applied and never prints the commit line."""
    _stub_applied_migration(monkeypatch)

    result = _invoke(project, ["--target", _MIGRATED_VERSION, "--yes", "--no-worktrees", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert result.output == _GOLDEN_APPLIED_DRY_RUN


# ---------------------------------------------------------------------------
# The outcome matrix: closing line, JSON status, outcome kind and exit code agree
# ---------------------------------------------------------------------------

_NO_MIGRATIONS = "no-migrations"
_MIGRATIONS = "migrations"
_NO_WRITES = "no_writes"

_CLOSING_NO_OP = "Project is already up to date!"
_CLOSING_APPLIED = f"Upgrade complete! {_PROJECT_VERSION} -> {_MIGRATED_VERSION}"
_CLOSING_APPLIED_DRY_RUN = f"Dry run complete — no changes applied. ({_PROJECT_VERSION} -> {_MIGRATED_VERSION} previewed)"
_CLOSING_DRIFT = "Upgrade finished with unresolved tool-surface drift."
_CLOSING_FAILED = "Upgrade failed."
_SUCCESS_PHRASES = ("already up to date", "upgrade complete", "dry run complete")


def _stub_drift(monkeypatch: pytest.MonkeyPatch, _path: str) -> None:
    """The prepared inventory reports one managed file that needs the operator's consent."""
    original = assessment.prepare_upgrade_repairs

    def _prepare(*args: Any, **kwargs: Any) -> Any:
        prepared = original(*args, **kwargs)
        drifted = OwnerAssessment(
            owner_key=_OWNER,
            root=prepared.root,
            dispositions=(Disposition(_OWNER, prepared.root.root_id, _DRIFTED_PATH, "consent_required", "edited by hand"),),
        )
        return replace(prepared, remaining=(*prepared.remaining, drifted))

    monkeypatch.setattr(assessment, "prepare_upgrade_repairs", _prepare)


def _stub_no_writes(monkeypatch: pytest.MonkeyPatch, _path: str) -> None:
    """The repair apply step reports nothing: a drift disposition has no effect to write."""
    monkeypatch.setattr(assessment, "apply_upgrade_repairs", lambda _prepared: ())


def _stub_unapplied(monkeypatch: pytest.MonkeyPatch, _path: str) -> None:
    """A repair is attempted and not applied, with no error diagnostic and no drifted file."""

    def _apply(_prepared: Any) -> tuple[OwnerApplyResult, ...]:
        return (OwnerApplyResult(owner_key=_OWNER, failed=("effect-1",), outcome="failed"),)

    monkeypatch.setattr(assessment, "apply_upgrade_repairs", _apply)


def _stub_activation_error(monkeypatch: pytest.MonkeyPatch, _path: str) -> None:
    def _fail(_self: object) -> bool:
        raise ValueError(_ACTIVATION_ERROR)

    monkeypatch.setattr("charter.activation.compiler._PreparedMissionTypeActivations.apply", _fail)


def _stub_worktree_failure(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    if path == _MIGRATIONS:
        _stub_applied_migration(monkeypatch, worktree_failures=(_WORKTREE_FAILURE,), errors=(_WORKTREE_FAILURE,))
    else:
        monkeypatch.setattr(upgrade_module, "_run_no_migrations_worktree_stamp", lambda *_a, **_kw: ([], [_WORKTREE_FAILURE]))


def _stub_commit_recovery_failure(monkeypatch: pytest.MonkeyPatch, _path: str) -> None:
    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise SafeCommitRecoveryFailed("restore failed", orphan_stash_ref="stash@{0}", commit_sha="c0ffee" * 6 + "c0ff")

    monkeypatch.setattr(autocommit, "commit_touched_checkout", _raise)


def _stub_migration_failure(monkeypatch: pytest.MonkeyPatch, _path: str) -> None:
    _stub_applied_migration(monkeypatch, success=False, errors=(_MIGRATION_ERROR,))


def _stub_incomplete_preview(monkeypatch: pytest.MonkeyPatch, _path: str) -> None:
    monkeypatch.setattr(upgrade_module, "_supporting_repair_preview", lambda _project: (_PREVIEW_NOTICE, True))


_STUBS: dict[str, Callable[[pytest.MonkeyPatch, str], None]] = {
    "drift": _stub_drift,
    _NO_WRITES: _stub_no_writes,
    "unapplied": _stub_unapplied,
    "activation_error": _stub_activation_error,
    "worktree_failure": _stub_worktree_failure,
    "commit_recovery_failure": _stub_commit_recovery_failure,
    "migration_failure": _stub_migration_failure,
    "incomplete_preview": _stub_incomplete_preview,
}


@dataclass(frozen=True)
class _Row:
    """One state of the outcome matrix and what every surface must report for it."""

    name: str
    stubs: tuple[str, ...]
    kind: str
    reasons: tuple[str, ...]
    paths: tuple[str, ...] = (_NO_MIGRATIONS, _MIGRATIONS)
    yes: bool = True
    errors_contain: tuple[str, ...] = ()
    config_yaml: str = ""

    @property
    def exit_code(self) -> int:
        return 0 if self.kind in {"applied", "no_op"} else 1


_DANGLING_CHARTER_CONFIG = "charter: does/not/exist.yaml\n"

_ROWS = (
    _Row("clean-no-op", (), "no_op", (), paths=(_NO_MIGRATIONS,)),
    _Row("clean-applied", (), "applied", (), paths=(_MIGRATIONS,)),
    _Row("drift", ("drift", _NO_WRITES), "drift_unresolved", ("surface_drift",), errors_contain=("Unresolved tool-surface drift in 1 file(s)",)),
    _Row("drift-without-yes", ("drift", _NO_WRITES), "drift_unresolved", ("surface_drift",), paths=(_NO_MIGRATIONS,), yes=False),
    _Row("repair-not-applied", ("unapplied",), "failed", ("surface_repair_failed",), errors_contain=("was not applied",)),
    _Row(
        "repair-not-applied-with-drift",
        ("drift", "unapplied"),
        "failed",
        ("surface_repair_failed", "surface_drift"),
        errors_contain=("was not applied", "Unresolved tool-surface drift in 1 file(s)"),
    ),
    _Row("activation-error", ("activation_error",), "failed", ("activation_error",), errors_contain=(_ACTIVATION_ERROR,)),
    _Row(
        "dangling-charter-pointer",
        (),
        "failed",
        ("activation_error",),
        config_yaml=_DANGLING_CHARTER_CONFIG,
        errors_contain=("'charter:' pointer names", "which does not exist"),
    ),
    _Row("worktree-failure", ("worktree_failure",), "failed", ("worktree_failure",), errors_contain=(_WORKTREE_FAILURE,)),
    _Row("commit-recovery-failure", ("commit_recovery_failure",), "failed", ("commit_recovery_failed",), errors_contain=("stash@{0}",)),
    _Row("migration-failure", ("migration_failure",), "failed", ("migration_failed",), paths=(_MIGRATIONS,), errors_contain=(_MIGRATION_ERROR,)),
)

_CASES = [(row, path) for row in _ROWS for path in row.paths]
_CASE_IDS = [f"{row.name}-{path}" for row, path in _CASES]


def _expected_closing(row: _Row, path: str) -> str:
    return {
        "no_op": _CLOSING_NO_OP,
        "applied": _CLOSING_APPLIED,
        "drift_unresolved": _CLOSING_DRIFT,
        "failed": _CLOSING_FAILED,
    }[row.kind]


def _prepare_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: _Row, path: str, *labels: str) -> tuple[list[Path], list[str]]:
    """One fresh real project per label, stubbed (once) into *row*'s state, and the CLI args."""
    roots = [tmp_path / label for label in labels]
    for root in roots:
        _init_project(root)
        if row.config_yaml:
            (root / ".kittify" / "config.yaml").write_text(row.config_yaml, encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "configure"], cwd=root, check=True)
    if path == _MIGRATIONS and not any(stub in {"worktree_failure", "migration_failure"} for stub in row.stubs):
        _stub_applied_migration(monkeypatch)
    for stub in row.stubs:
        _STUBS[stub](monkeypatch, path)
    target = _MIGRATED_VERSION if path == _MIGRATIONS else _PROJECT_VERSION
    args = ["--target", target, "--no-worktrees", "--no-nag"]
    return roots, [*args, "--yes"] if row.yes else args


@pytest.fixture
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silence the banner and keep tests off the network-bound CI heuristics."""
    monkeypatch.setattr(upgrade_module, "show_banner", lambda: None)
    monkeypatch.setenv("CI", "1")


@pytest.mark.parametrize(("row", "path"), _CASES, ids=_CASE_IDS)
def test_matrix_text_and_json_agree_on_one_outcome(row: _Row, path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quiet: None) -> None:
    (text_root, json_root), args = _prepare_state(tmp_path, monkeypatch, row, path, "as-text", "as-json")

    text = _invoke(text_root, args)
    machine = _invoke(json_root, [*args, "--json"])
    payload = json.loads(machine.output.strip().splitlines()[-1])

    # Rule 1: text and JSON exit with the same code for the same project state.
    assert text.exit_code == machine.exit_code == row.exit_code, (text.output, machine.output)
    # JSON: status, success, outcome and reasons describe the same outcome.
    assert payload["success"] is (row.exit_code == 0)
    assert payload["status"] == {"no_op": "up_to_date", "applied": "success"}.get(row.kind, "failed")
    assert payload["outcome"] == row.kind
    assert payload["failure_reasons"] == list(row.reasons)
    assert not any("in 0 file(s)" in error for error in payload["errors"])
    for expected in row.errors_contain:
        assert any(expected in error for error in payload["errors"]), payload["errors"]
    # Text: the closing line is the outcome's, and it is the last thing printed on a failure.
    closing = _expected_closing(row, path)
    assert closing in text.output
    if row.exit_code != 0:
        # Rule 2: every string in the JSON errors is printed, no success line is, and the verdict comes last.
        assert payload["errors"], "a non-zero exit always has at least one reason (rule 7)"
        for error in payload["errors"]:
            # The two runs are the same project state at two locations: compare the error as printed at the text run's.
            assert error.replace(str(json_root.resolve()), str(text_root.resolve())) in text.output
        lowered = text.output.lower()
        assert not any(phrase in lowered for phrase in _SUCCESS_PHRASES)
        assert text.output.rstrip().splitlines()[-1] == closing
    else:
        assert payload["errors"] == []


_AUTO_COMMITTED_PATTERN = re.compile(r"^→ Auto-committed upgrade changes \((\d+) files\)$", re.MULTILINE)


@pytest.mark.parametrize("path", [_NO_MIGRATIONS, _MIGRATIONS])
def test_text_reports_the_auto_commit_of_a_drift_unresolved_run_as_json_does(path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quiet: None) -> None:
    """The churn commit runs before the verdict: a non-success run that committed says so in text too."""
    row = _Row("drift", ("drift", _NO_WRITES), "drift_unresolved", ("surface_drift",))
    (text_root, json_root), args = _prepare_state(tmp_path, monkeypatch, row, path, "as-text", "as-json")

    text = _invoke(text_root, args)
    machine = _invoke(json_root, [*args, "--json"])
    payload = json.loads(machine.output.strip().splitlines()[-1])

    assert text.exit_code == machine.exit_code == 1, (text.output, machine.output)
    assert payload["auto_committed"] is True
    assert payload["auto_commit_paths"]
    committed_lines = _AUTO_COMMITTED_PATTERN.findall(text.output)
    assert committed_lines == [str(len(payload["auto_commit_paths"]))], text.output
    assert text.output.rstrip().splitlines()[-1] == _CLOSING_DRIFT


# ---------------------------------------------------------------------------
# Dry runs are text-only (``--json --dry-run`` is the planner contract, out of scope)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "closing"),
    [(_NO_MIGRATIONS, _CLOSING_NO_OP), (_MIGRATIONS, _CLOSING_APPLIED_DRY_RUN)],
    ids=[_NO_MIGRATIONS, _MIGRATIONS],
)
def test_completed_dry_run_prints_its_closing_line_and_exits_zero(path: str, closing: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quiet: None) -> None:
    row = _Row("dry-run", (), "applied" if path == _MIGRATIONS else "no_op", ())
    (root,), args = _prepare_state(tmp_path, monkeypatch, row, path, "dry")

    result = _invoke(root, [*args, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert closing in result.output
    assert "upgrade complete" not in result.output.lower()
    assert "Upgrade failed." not in result.output


@pytest.mark.parametrize("path", [_NO_MIGRATIONS, _MIGRATIONS])
@pytest.mark.parametrize(
    ("row", "notice"),
    [
        (_Row("incomplete-preview", ("incomplete_preview",), "failed", ("preview_incomplete",)), _PREVIEW_NOTICE),
        (
            _Row("dangling-charter-pointer", (), "failed", ("preview_incomplete",), config_yaml=_DANGLING_CHARTER_CONFIG),
            "Supporting repair preview incomplete: .kittify/config.yaml 'charter:' pointer names",
        ),
    ],
    ids=["stubbed-preview", "dangling-charter-pointer"],
)
def test_incomplete_dry_run_preview_is_a_failure_and_its_notice_prints_once(
    row: _Row, notice: str, path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quiet: None
) -> None:
    (root,), args = _prepare_state(tmp_path, monkeypatch, row, path, "preview")

    result = _invoke(root, [*args, "--dry-run"])

    assert result.exit_code == 1, result.output
    assert result.output.count(notice) == 1, result.output
    assert not any(phrase in result.output.lower() for phrase in _SUCCESS_PHRASES)
    assert result.output.rstrip().splitlines()[-1] == _CLOSING_FAILED


# ---------------------------------------------------------------------------
# The tail renderer, directly: layouts that are awkward to reach through the command
# ---------------------------------------------------------------------------


def _render_tail(outcome: UpgradeOutcome, **overrides: Any) -> str:
    kwargs: dict[str, Any] = {"manual_review_paths": [], "auto_commit_paths": [], "left_uncommitted": False, **overrides}
    with console.capture() as capture:
        upgrade_module._render_outcome_tail(outcome, **kwargs)
    return capture.get()


def test_no_op_tail_still_shows_an_error_diagnostic_carried_by_a_successful_result() -> None:
    result = UpgradeResult(success=True, from_version=_PROJECT_VERSION, to_version=_PROJECT_VERSION, errors=["an error diagnostic"])

    output = _render_tail(UpgradeOutcome(result=result))

    assert output == f"{_CLOSING_NO_OP}\nError: an error diagnostic\n"


def test_non_success_tail_prints_sections_then_the_closing_line_last() -> None:
    outcome = UpgradeOutcome(
        result=UpgradeResult(success=True, from_version=_PROJECT_VERSION, to_version=_MIGRATED_VERSION, warnings=["a warning"]),
        had_migrations=True,
        activation_errors=[_ACTIVATION_ERROR],
    )

    output = _render_tail(outcome, manual_review_paths=["notes/review.md"])

    assert output == f"Warnings:\n  ! a warning\nErrors:\n  ✗ {_ACTIVATION_ERROR}\nManual review required:\n  ! notes/review.md\n\n{_CLOSING_FAILED}\n"


def test_square_brackets_in_a_message_are_printed_literally() -> None:
    outcome = UpgradeOutcome(
        result=UpgradeResult(success=False, from_version=_PROJECT_VERSION, to_version=_MIGRATED_VERSION, errors=["see [/bold] and [link=x]"]),
        had_migrations=True,
    )

    assert "✗ see [/bold] and [link=x]" in _render_tail(outcome)


def test_applied_tail_reports_the_commit_or_the_left_uncommitted_line() -> None:
    result = UpgradeResult(success=True, from_version=_PROJECT_VERSION, to_version=_MIGRATED_VERSION)

    committed = UpgradeOutcome(result=result, had_migrations=True, committed=True)
    assert _render_tail(committed, auto_commit_paths=["a", "b"]).endswith(f"{_CLOSING_APPLIED}\n→ Auto-committed upgrade changes (2 files)\n")

    left = UpgradeOutcome(result=result, had_migrations=True)
    assert "left uncommitted" in _render_tail(left, left_uncommitted=True)


# ---------------------------------------------------------------------------
# The surface-repair step: every way it can return
# ---------------------------------------------------------------------------


@pytest.fixture
def prepared_project(tmp_path: Path, quiet: None) -> tuple[Path, upgrade_module._FinalizerRenderContext]:
    """A real project with its repairs prepared exactly as the command prepares them."""
    root = tmp_path / "step"
    _init_project(root)
    ctx = upgrade_module._FinalizerRenderContext()
    assert upgrade_module._prepare_finalizer_repairs(root, ctx) == ()
    assert ctx.prepared_repairs is not None
    return root, ctx


def _outcome(*, success: bool = True) -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=success, from_version=_PROJECT_VERSION, to_version=_PROJECT_VERSION))


def _run_step(outcome: UpgradeOutcome, ctx: Any, project: Path, *, dry_run: bool = False, json_output: bool = False) -> SurfaceRepairReport:
    return upgrade_module._finalizer_step_surface_repair(outcome, ctx, project_path=project, dry_run=dry_run, json_output=json_output)


def test_step_after_a_failed_migration_reports_nothing(prepared_project: tuple[Path, Any]) -> None:
    project, ctx = prepared_project

    assert _run_step(_outcome(success=False), ctx, project) == SurfaceRepairReport()
    assert ctx.surface_repair_summary is None


def test_step_without_prepared_repairs_reports_nothing(tmp_path: Path) -> None:
    ctx = upgrade_module._FinalizerRenderContext()

    assert _run_step(_outcome(), ctx, tmp_path) == SurfaceRepairReport()


def test_step_dry_run_with_a_complete_preview_prints_the_notice_and_reports_nothing(prepared_project: tuple[Path, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    project, ctx = prepared_project
    monkeypatch.setattr(upgrade_module, "_supporting_repair_preview", lambda _project: ("Would repair 3 supporting surface paths.", False))

    with console.capture() as capture:
        report = _run_step(_outcome(), ctx, project, dry_run=True)
    assert report == SurfaceRepairReport()
    assert "Would repair 3 supporting surface paths." in capture.get()

    with console.capture() as quiet_capture:
        assert _run_step(_outcome(), ctx, project, dry_run=True, json_output=True) == SurfaceRepairReport()
    assert quiet_capture.get() == ""


def test_step_dry_run_with_an_incomplete_preview_carries_the_notice_in_the_report(prepared_project: tuple[Path, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    project, ctx = prepared_project
    monkeypatch.setattr(upgrade_module, "_supporting_repair_preview", lambda _project: (_PREVIEW_NOTICE, True))

    with console.capture() as capture:
        report = _run_step(_outcome(), ctx, project, dry_run=True)

    assert report == SurfaceRepairReport(preview_incomplete=True, failure_messages=(_PREVIEW_NOTICE,))
    assert capture.get() == "", "the notice is printed once, by the renderer"


def test_step_with_a_drifted_owner_reports_the_drifted_path(prepared_project: tuple[Path, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    project, ctx = prepared_project
    _stub_drift(monkeypatch, _NO_MIGRATIONS)
    _stub_no_writes(monkeypatch, _NO_MIGRATIONS)
    prepared = ctx.prepared_repairs
    assert prepared is not None
    ctx.prepared_repairs = assessment.prepare_upgrade_repairs(project, consent=prepared.consent)

    report = _run_step(_outcome(), ctx, project)

    assert report.drifted_paths == (project.resolve() / _DRIFTED_PATH,)
    assert report.failed is False
    assert ctx.surface_repair_summary is not None
    assert ctx.surface_repair_summary.drifted_reported == [project.resolve() / _DRIFTED_PATH]


def test_step_names_a_repair_that_was_not_applied_and_gave_no_error_diagnostic(prepared_project: tuple[Path, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    project, ctx = prepared_project
    _stub_unapplied(monkeypatch, _NO_MIGRATIONS)
    outcome = _outcome()

    report = _run_step(outcome, ctx, project)

    assert report.failed is True
    assert report.drifted_paths == ()
    assert report.failure_messages == (f"Tool-surface repair for {_OWNER} was not applied (failed); re-run 'spec-kitty upgrade'.",)
    assert outcome.result.errors == []


def test_step_keeps_an_error_diagnostic_in_the_result_errors_instead_of_synthesising_a_message(
    prepared_project: tuple[Path, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from specify_cli.tool_surface.operations import Diagnostic

    project, ctx = prepared_project
    diagnostic = Diagnostic("write_failed", _OWNER, "error", "disk full")
    monkeypatch.setattr(
        assessment, "apply_upgrade_repairs", lambda _prepared: (OwnerApplyResult(owner_key=_OWNER, failed=("e",), diagnostics=(diagnostic,), outcome="failed"),)
    )
    outcome = _outcome()

    report = _run_step(outcome, ctx, project)

    assert report.failed is True
    assert report.failure_messages == ()
    assert outcome.result.errors == ["disk full"]


# ---------------------------------------------------------------------------
# The mission-state repair gate stays closed after a failed commit recovery
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", [_NO_MIGRATIONS, _MIGRATIONS])
@pytest.mark.parametrize(("recovery_fails", "gate_calls"), [(True, 0), (False, 1)], ids=["recovery-failed", "clean-run"])
def test_mission_state_repair_gate_is_not_offered_after_a_failed_commit_recovery(
    path: str, recovery_fails: bool, gate_calls: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quiet: None
) -> None:
    from specify_cli.upgrade.outcome import RepairOutcome

    row = _Row("gate", ("commit_recovery_failure",) if recovery_fails else (), "failed" if recovery_fails else "applied", (), yes=True)
    (root,), args = _prepare_state(tmp_path, monkeypatch, row, path, "gate")
    gate = MagicMock(return_value=RepairOutcome())
    monkeypatch.setattr(upgrade_module, "offer_teamspace_mission_state_migration", gate)

    result = _invoke(root, args)

    assert gate.call_count == gate_calls, result.output
    assert (result.exit_code != 0) is recovery_fails


# ---------------------------------------------------------------------------
# Help text (FR-014)
# ---------------------------------------------------------------------------


def test_help_says_only_a_completed_dry_run_preview_exits_zero() -> None:
    doc = upgrade_module.upgrade.__doc__ or ""

    assert "a completed ``--dry-run`` preview" in doc
    assert "any ``--dry-run``" not in doc
    assert "``--dry-run``\n         preview that could not be completed" in doc
