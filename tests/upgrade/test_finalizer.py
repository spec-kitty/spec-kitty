"""Seam unit tests for the upgrade finalizer (C4, D-4/D-5/D-11, FR-007/011/014).

Exercises `finalize_upgrade`'s ordering, the one-commit property with
mission-state repair excluded from the churn commit (#2491/SC-008), the
single exit-code-derivation invariant (D-5), and the FR-014 failure-isolation
boundary around the repair step.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import pytest

from specify_cli.cli.commands import upgrade as upgrade_cmd
from specify_cli.lanes import consolidation
from specify_cli.upgrade.finalize import finalize_upgrade
from specify_cli.upgrade.outcome import (
    MergeDriverConfigState,
    MissionStateReportOutcome,
    SurfaceRepairReport,
    UpgradeFailureReason,
    UpgradeOutcome,
    UpgradeOutcomeKind,
)
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.git_repo]


def _synthesized_result(*, success: bool = True) -> UpgradeResult:
    """A normalized no-migrations UpgradeResult (D-3)."""
    return UpgradeResult(success=success, from_version="3.2.3", to_version="3.2.3")


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def _commit_count(path: Path) -> int:
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return len(log.stdout.strip().splitlines())


def _files_in_commit(path: Path, ref: str = "HEAD") -> set[str]:
    show = subprocess.run(
        ["git", "show", "--stat", "--name-only", "--format=", ref],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in show.stdout.splitlines() if line.strip()}


def _porcelain_status(path: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


def test_finalizer_runs_steps_in_contract_order(tmp_path: Path) -> None:
    calls: list[str] = []

    def _provision() -> list[str]:
        calls.append("provision")
        return []

    def _surface_repair() -> SurfaceRepairReport:
        calls.append("surface_repair")
        return SurfaceRepairReport()

    def _commit_churn() -> bool:
        calls.append("commit_churn")
        return True

    def _offer_repair() -> MissionStateReportOutcome:
        calls.append("report_mission_state")
        return MissionStateReportOutcome(pending=True)

    outcome = UpgradeOutcome(result=_synthesized_result())
    finalize_upgrade(
        outcome,
        provision_activations=_provision,
        run_surface_repair=_surface_repair,
        report_mission_state=_offer_repair,
        commit_churn=_commit_churn,
        should_commit=True,
    )

    assert calls == ["provision", "surface_repair", "commit_churn", "report_mission_state"]


def test_finalizer_skips_commit_when_should_commit_is_false(tmp_path: Path) -> None:
    def _commit_churn() -> bool:
        raise AssertionError("commit_churn must not run when should_commit is False")

    outcome = UpgradeOutcome(result=_synthesized_result())
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=SurfaceRepairReport,
        report_mission_state=lambda: MissionStateReportOutcome(pending=True),
        commit_churn=_commit_churn,
        should_commit=False,
    )

    assert result.committed is False


# ---------------------------------------------------------------------------
# Exit-code derivation (D-5) and FR-014 (repair failure never sinks a
# completed upgrade)
# ---------------------------------------------------------------------------


def test_successful_upgrade_derives_exit_code_zero() -> None:
    outcome = UpgradeOutcome(result=_synthesized_result(success=True))
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=SurfaceRepairReport,
        report_mission_state=lambda: MissionStateReportOutcome(pending=True),
        commit_churn=lambda: True,
        should_commit=True,
    )
    assert result.exit_code == 0
    assert result.effective_success is True


def test_failed_migration_result_derives_exit_code_one_no_typer_exit() -> None:
    """A FAILED run's exit code comes from ``UpgradeOutcome.exit_code`` — the
    finalizer must never raise ``typer.Exit`` itself (D-5)."""
    outcome = UpgradeOutcome(result=_synthesized_result(success=False))
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=SurfaceRepairReport,
        report_mission_state=lambda: MissionStateReportOutcome(pending=True),
        commit_churn=lambda: False,
        should_commit=False,
    )
    assert result.exit_code == 1
    assert result.effective_success is False


def test_worktree_failures_flip_exit_code_nonzero() -> None:
    """FR-012: fatal worktree failures flip effective success/exit code even
    though the migration result itself reported success."""
    outcome = UpgradeOutcome(result=_synthesized_result(success=True))
    outcome.worktree_failures = ["lane-a: schema mismatch"]
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=SurfaceRepairReport,
        report_mission_state=lambda: MissionStateReportOutcome(pending=True),
        commit_churn=lambda: False,
        should_commit=False,
    )
    assert result.exit_code == 1
    assert result.effective_success is False


def test_optional_repair_failure_does_not_flip_a_successful_exit_code() -> None:
    """FR-014: an optional-repair failure never sinks a completed upgrade."""
    outcome = UpgradeOutcome(result=_synthesized_result(success=True))
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=SurfaceRepairReport,
        report_mission_state=lambda: MissionStateReportOutcome(failed=True, message="repair blew up"),
        commit_churn=lambda: True,
        should_commit=True,
    )
    assert result.repair.failed is True
    assert result.exit_code == 0
    assert result.effective_success is True
    # The gate printed its own failure; the outcome must not list it a second time.
    assert result.warnings() == []


def test_offer_repair_exception_is_isolated_and_does_not_flip_exit_code() -> None:
    """The repair step runs inside a failure-isolating boundary (FR-014): an
    exception escaping the injected ``report_mission_state`` callable must not crash
    the finalizer nor affect the exit code."""

    def _boom() -> MissionStateReportOutcome:
        raise RuntimeError("unexpected repair blowup")

    outcome = UpgradeOutcome(result=_synthesized_result(success=True))
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=SurfaceRepairReport,
        report_mission_state=_boom,
        commit_churn=lambda: True,
        should_commit=True,
    )
    assert result.repair.failed is True
    assert result.exit_code == 0
    # The gate never saw this failure, so the outcome lists it as a warning (and nothing else changes).
    assert result.warnings() == ["Mission-state report boundary raised: unexpected repair blowup"]
    assert result.kind is UpgradeOutcomeKind.NO_OP


def test_activation_errors_stop_the_surface_repair_step_and_fail_the_outcome() -> None:
    outcome = UpgradeOutcome(result=_synthesized_result(success=True))
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: ["mission-type X activation failed"],
        run_surface_repair=lambda: pytest.fail("surface repair must not run after an activation error"),
        report_mission_state=lambda: MissionStateReportOutcome(pending=True),
        commit_churn=lambda: False,
        should_commit=False,
    )
    assert result.activation_errors == ["mission-type X activation failed"]
    assert result.reasons == (UpgradeFailureReason.ACTIVATION_ERROR,)
    assert result.kind is UpgradeOutcomeKind.FAILED
    assert result.effective_success is False
    assert result.exit_code == 1


def test_unresolved_drift_is_recorded_and_derives_exit_code_one() -> None:
    drifted = (Path("/proj/.claude/agents/a.md"), Path("/proj/.claude/agents/b.md"))
    result = finalize_upgrade(
        UpgradeOutcome(result=_synthesized_result(success=True)),
        provision_activations=lambda: [],
        run_surface_repair=lambda: SurfaceRepairReport(drifted_paths=drifted),
        report_mission_state=lambda: MissionStateReportOutcome(pending=True),
        commit_churn=lambda: False,
        should_commit=False,
    )
    assert result.drifted_paths == list(drifted)
    assert result.reasons == (UpgradeFailureReason.SURFACE_DRIFT,)
    assert result.kind is UpgradeOutcomeKind.DRIFT_UNRESOLVED
    assert [error.split(": ")[0] for error in result.errors()[:2]] == ["Not updated, your local edit was kept"] * 2
    assert result.closing_line() == "Upgrade finished, but 2 managed file(s) with local edits were not updated."
    assert result.exit_code == 1


def test_unapplied_repair_is_recorded_as_a_failure_not_as_drift() -> None:
    report = SurfaceRepairReport(failed=True, failure_messages=("Tool-surface repair for x was not applied (failed); re-run 'spec-kitty upgrade'.",))
    result = finalize_upgrade(
        UpgradeOutcome(result=_synthesized_result(success=True)),
        provision_activations=lambda: [],
        run_surface_repair=lambda: report,
        report_mission_state=lambda: MissionStateReportOutcome(pending=True),
        commit_churn=lambda: False,
        should_commit=False,
    )
    assert result.drifted_paths == []
    assert result.reasons == (UpgradeFailureReason.SURFACE_REPAIR_FAILED,)
    assert result.kind is UpgradeOutcomeKind.FAILED
    assert result.errors() == list(report.failure_messages)
    assert result.exit_code == 1


def test_provisioning_refusal_prevents_dependent_writes_and_commit(tmp_path: Path) -> None:
    """A failed prerequisite cannot fall through to the surface writer."""
    output = tmp_path / "surface.txt"
    commits: list[str] = []

    def repair_surface() -> SurfaceRepairReport:
        output.write_text("dependent output\n")
        return SurfaceRepairReport()

    def commit() -> bool:
        commits.append("commit")
        return True

    outcome = finalize_upgrade(
        UpgradeOutcome(result=_synthesized_result()),
        provision_activations=lambda: ["Provisioning inputs changed"],
        run_surface_repair=repair_surface,
        report_mission_state=lambda: MissionStateReportOutcome(pending=True),
        commit_churn=commit,
        should_commit=True,
    )
    assert not output.exists()
    assert commits == []
    assert outcome.activation_errors == ["Provisioning inputs changed"]
    assert outcome.exit_code == 1


def test_finalizer_keeps_preflight_around_writes_not_commit_or_mission_repair() -> None:
    calls: list[str] = []

    @contextmanager
    def preflight():
        calls.append("preflight")
        try:
            yield ()
        finally:
            calls.append("release")

    def provision() -> list[str]:
        calls.append("provision")
        return []

    def surfaces() -> SurfaceRepairReport:
        calls.append("surfaces")
        return SurfaceRepairReport()

    def commit() -> bool:
        calls.append("commit")
        return True

    def repair() -> MissionStateReportOutcome:
        calls.append("mission")
        return MissionStateReportOutcome()

    result = finalize_upgrade(
        UpgradeOutcome(result=_synthesized_result()),
        provision_activations=provision,
        run_surface_repair=surfaces,
        commit_churn=commit,
        report_mission_state=repair,
        should_commit=True,
        repair_preflight=preflight(),
    )
    assert result.exit_code == 0
    assert calls == ["preflight", "provision", "surfaces", "release", "commit", "mission"]


# ---------------------------------------------------------------------------
# One-commit property + repair exclusion (D-4, #2491/SC-008) — filesystem
# ---------------------------------------------------------------------------


def test_single_churn_commit_excludes_mission_state_repair_paths(tmp_path: Path) -> None:
    """Surface-repair writes land INSIDE the single churn commit; mission-
    state repair writes never do (D-4). The scenario also has the repair
    step make (and commit) its own separate change, proving the overall tree
    ends up clean without that change ever entering the churn commit."""
    _init_git_repo(tmp_path)
    commits_before = _commit_count(tmp_path)

    def _surface_repair() -> SurfaceRepairReport:
        (tmp_path / "surface_repaired.txt").write_text("repaired\n", encoding="utf-8")
        subprocess.run(["git", "add", "surface_repaired.txt"], cwd=tmp_path, check=True)
        return SurfaceRepairReport()

    def _commit_churn() -> bool:
        subprocess.run(
            ["git", "commit", "-q", "-m", "chore: apply spec-kitty upgrade changes"],
            cwd=tmp_path,
            check=True,
        )
        return True

    def _offer_repair() -> MissionStateReportOutcome:
        # Mission-state repair's own, separately-scoped commit (D-4) — must
        # never be folded into the churn commit above.
        (tmp_path / "repair_repo_output.txt").write_text("repaired-state\n", encoding="utf-8")
        subprocess.run(["git", "add", "repair_repo_output.txt"], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "chore: mission-state repair"],
            cwd=tmp_path,
            check=True,
        )
        return MissionStateReportOutcome(reported=True, message="repaired")

    outcome = UpgradeOutcome(result=_synthesized_result())
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=_surface_repair,
        report_mission_state=_offer_repair,
        commit_churn=_commit_churn,
        should_commit=True,
    )

    # Exactly one churn commit was created (plus the repair's own commit).
    assert _commit_count(tmp_path) == commits_before + 2

    churn_commit_files = _files_in_commit(tmp_path, "HEAD~1")
    assert "surface_repaired.txt" in churn_commit_files
    assert "repair_repo_output.txt" not in churn_commit_files

    repair_commit_files = _files_in_commit(tmp_path, "HEAD")
    assert repair_commit_files == {"repair_repo_output.txt"}

    assert _porcelain_status(tmp_path) == ""
    assert result.committed is True
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# #5759 -- ``finalize_upgrade`` installs the per-clone merge-driver git config.
#
# Unit coverage of the injected ``install_merge_driver_config`` step, the
# ``_finalizer_step_merge_driver_config`` callable behind it, and the informational
# ``UpgradeOutcome.merge_driver_config`` field (ADR 2026-10-04-3: additive, never a
# failure reason). The end-to-end clone arm lives in
# ``tests/terminus/test_clone_init_installs_merge_drivers.py``.
# ---------------------------------------------------------------------------

_INSTALLED_NOTICE = "Installed clone-local merge-driver settings"


def _outcome() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=True, from_version="4.0.0", to_version="4.0.0"))


def _git_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def _merge_keys(repo: Path) -> list[str]:
    result = subprocess.run(["git", "-C", str(repo), "config", "--local", "--get-regexp", r"^merge\."], capture_output=True, text=True)
    return result.stdout.splitlines()


def _finalize(outcome: UpgradeOutcome, step: Callable[[], MergeDriverConfigState] | None, *, preflight_errors: Sequence[str] = ()) -> UpgradeOutcome:
    @contextmanager
    def _preflight() -> Iterator[list[str]]:
        yield list(preflight_errors)

    return finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=SurfaceRepairReport,
        offer_repair=lambda: RepairOutcome(pending=True),
        commit_churn=lambda: False,
        should_commit=False,
        repair_preflight=_preflight(),
        install_merge_driver_config=step,
    )


def test_step_skips_a_project_that_is_not_a_git_repository(tmp_path: Path) -> None:
    outcome = _outcome()

    state = upgrade_cmd._finalizer_step_merge_driver_config(outcome, project_path=tmp_path, dry_run=False)

    assert state == "skipped"
    assert not outcome.result.warnings


def test_step_installs_missing_config_then_reports_present(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    outcome = _outcome()

    first = upgrade_cmd._finalizer_step_merge_driver_config(outcome, project_path=repo, dry_run=False)
    keys_after_first = _merge_keys(repo)
    second = upgrade_cmd._finalizer_step_merge_driver_config(outcome, project_path=repo, dry_run=False)

    assert first == "installed"
    assert keys_after_first, "the driver config must be defined"
    assert second == "present"
    assert _merge_keys(repo) == keys_after_first
    assert outcome.result.warnings == []


def test_step_keeps_a_customized_driver_and_replaces_a_superseded_one(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    upgrade_cmd._finalizer_step_merge_driver_config(_outcome(), project_path=repo, dry_run=False)
    custom = "/opt/venv/bin/spec-kitty merge-driver-meta %O %A %B"
    subprocess.run(["git", "-C", str(repo), "config", "--local", "merge.spec-kitty-meta.driver", custom], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "--local", "merge.spec-kitty-issue-matrix.name", "Spec Kitty issue matrix filled-side merge"], check=True)
    outcome = _outcome()

    state = upgrade_cmd._finalizer_step_merge_driver_config(outcome, project_path=repo, dry_run=False)

    assert state == "customized"
    assert (
        subprocess.run(["git", "-C", str(repo), "config", "--local", "--get", "merge.spec-kitty-meta.driver"], capture_output=True, text=True).stdout.strip()
        == custom
    )
    row_aware = subprocess.run(["git", "-C", str(repo), "config", "--local", "--get", "merge.spec-kitty-issue-matrix.name"], capture_output=True, text=True)
    assert row_aware.stdout.strip() == "Spec Kitty issue matrix row-aware merge"  # a value an older release shipped is ours to update
    (warning,) = outcome.result.warnings
    assert "merge.spec-kitty-meta.driver" in warning and custom in warning and "spec-kitty merge-driver-meta %O %A %B" in warning


def test_step_reports_installed_when_one_key_is_missing(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    upgrade_cmd._finalizer_step_merge_driver_config(_outcome(), project_path=repo, dry_run=False)
    subprocess.run(["git", "-C", str(repo), "config", "--local", "--unset", "merge.spec-kitty-meta.driver"], check=True)

    assert upgrade_cmd._finalizer_step_merge_driver_config(_outcome(), project_path=repo, dry_run=False) == "installed"


def test_step_is_skipped_on_a_dry_run_and_writes_nothing(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)

    assert upgrade_cmd._finalizer_step_merge_driver_config(_outcome(), project_path=repo, dry_run=True) == "skipped"
    assert _merge_keys(repo) == []


def test_step_failure_is_a_warning_and_never_a_failure_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object) -> None:
        raise OSError("read-only .git")

    monkeypatch.setattr(consolidation, "_set_local_git_config", _boom)
    outcome = _outcome()

    result = _finalize(outcome, lambda: upgrade_cmd._finalizer_step_merge_driver_config(outcome, project_path=_git_repo(tmp_path), dry_run=False))

    assert result.merge_driver_config == "failed"
    assert any("read-only .git" in warning for warning in result.warnings())
    assert result.reasons == ()
    assert result.kind is UpgradeOutcomeKind.NO_OP
    assert result.exit_code == 0


def test_finalizer_records_the_step_result_and_runs_despite_repair_preparation_errors() -> None:
    result = _finalize(_outcome(), lambda: "installed", preflight_errors=["prep failed"])

    assert result.merge_driver_config == "installed"
    assert result.repair_preparation_errors == ["prep failed"]


def test_finalizer_leaves_the_field_skipped_when_no_step_is_injected() -> None:
    result = _finalize(_outcome(), None)

    assert result.merge_driver_config == "skipped"
    assert result.notices() == []


@pytest.mark.parametrize(("state", "expected"), [("installed", [_INSTALLED_NOTICE]), ("present", []), ("customized", []), ("skipped", []), ("failed", [])])
def test_only_a_fresh_install_is_announced(state: MergeDriverConfigState, expected: list[str]) -> None:
    outcome = _outcome()
    outcome.merge_driver_config = state

    assert outcome.notices() == expected
