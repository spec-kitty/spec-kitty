"""Seam unit tests for the upgrade finalizer (C4, D-4/D-5/D-11, FR-007/011/014).

Exercises `finalize_upgrade`'s ordering, the one-commit property with
mission-state repair excluded from the churn commit (#2491/SC-008), the
single exit-code-derivation invariant (D-5), and the FR-014 failure-isolation
boundary around the repair step.
"""

from __future__ import annotations

import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

from specify_cli.upgrade.finalize import finalize_upgrade
from specify_cli.upgrade.outcome import (
    RepairOutcome,
    SurfaceRepairReport,
    UpgradeFailureReason,
    UpgradeOutcome,
    UpgradeOutcomeKind,
)
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.unit, pytest.mark.fast]


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

    def _offer_repair() -> RepairOutcome:
        calls.append("offer_repair")
        return RepairOutcome(pending=True)

    outcome = UpgradeOutcome(result=_synthesized_result())
    finalize_upgrade(
        outcome,
        provision_activations=_provision,
        run_surface_repair=_surface_repair,
        offer_repair=_offer_repair,
        commit_churn=_commit_churn,
        should_commit=True,
    )

    assert calls == ["provision", "surface_repair", "commit_churn", "offer_repair"]


def test_finalizer_skips_commit_when_should_commit_is_false(tmp_path: Path) -> None:
    def _commit_churn() -> bool:
        raise AssertionError("commit_churn must not run when should_commit is False")

    outcome = UpgradeOutcome(result=_synthesized_result())
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=SurfaceRepairReport,
        offer_repair=lambda: RepairOutcome(pending=True),
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
        offer_repair=lambda: RepairOutcome(pending=True),
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
        offer_repair=lambda: RepairOutcome(pending=True),
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
        offer_repair=lambda: RepairOutcome(pending=True),
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
        offer_repair=lambda: RepairOutcome(failed=True, message="repair blew up"),
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
    exception escaping the injected ``offer_repair`` callable must not crash
    the finalizer nor affect the exit code."""

    def _boom() -> RepairOutcome:
        raise RuntimeError("unexpected repair blowup")

    outcome = UpgradeOutcome(result=_synthesized_result(success=True))
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=SurfaceRepairReport,
        offer_repair=_boom,
        commit_churn=lambda: True,
        should_commit=True,
    )
    assert result.repair.failed is True
    assert result.exit_code == 0
    # The gate never saw this failure, so the outcome lists it as a warning (and nothing else changes).
    assert result.warnings() == ["Mission-state repair boundary raised: unexpected repair blowup"]
    assert result.kind is UpgradeOutcomeKind.NO_OP


def test_activation_errors_stop_the_surface_repair_step_and_fail_the_outcome() -> None:
    outcome = UpgradeOutcome(result=_synthesized_result(success=True))
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: ["mission-type X activation failed"],
        run_surface_repair=lambda: pytest.fail("surface repair must not run after an activation error"),
        offer_repair=lambda: RepairOutcome(pending=True),
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
        offer_repair=lambda: RepairOutcome(pending=True),
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
        offer_repair=lambda: RepairOutcome(pending=True),
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
        offer_repair=lambda: RepairOutcome(pending=True),
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

    def repair() -> RepairOutcome:
        calls.append("mission")
        return RepairOutcome()

    result = finalize_upgrade(
        UpgradeOutcome(result=_synthesized_result()),
        provision_activations=provision,
        run_surface_repair=surfaces,
        commit_churn=commit,
        offer_repair=repair,
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

    def _offer_repair() -> RepairOutcome:
        # Mission-state repair's own, separately-scoped commit (D-4) — must
        # never be folded into the churn commit above.
        (tmp_path / "repair_repo_output.txt").write_text("repaired-state\n", encoding="utf-8")
        subprocess.run(["git", "add", "repair_repo_output.txt"], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "chore: mission-state repair"],
            cwd=tmp_path,
            check=True,
        )
        return RepairOutcome(reported=True, message="repaired")

    outcome = UpgradeOutcome(result=_synthesized_result())
    result = finalize_upgrade(
        outcome,
        provision_activations=lambda: [],
        run_surface_repair=_surface_repair,
        offer_repair=_offer_repair,
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
