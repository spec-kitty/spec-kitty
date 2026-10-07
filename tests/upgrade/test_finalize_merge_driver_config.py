"""#5759 -- ``finalize_upgrade`` installs the per-clone merge-driver git config.

Unit coverage of the injected ``install_merge_driver_config`` step, the
``_finalizer_step_merge_driver_config`` callable behind it, and the informational
``UpgradeOutcome.merge_driver_config`` field (ADR 2026-10-04-3: additive, never a
failure reason). The end-to-end clone arm lives in
``tests/terminus/test_clone_init_installs_merge_drivers.py``.
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
from specify_cli.upgrade.outcome import MergeDriverConfigState, RepairOutcome, SurfaceRepairReport, UpgradeOutcome, UpgradeOutcomeKind
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.git_repo]

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
    def _boom(_repo: Path) -> None:
        raise OSError("read-only .git")

    monkeypatch.setattr(consolidation, "_ensure_merge_driver_git_config", _boom)
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


@pytest.mark.parametrize(("state", "expected"), [("installed", [_INSTALLED_NOTICE]), ("present", []), ("skipped", []), ("failed", [])])
def test_only_a_fresh_install_is_announced(state: MergeDriverConfigState, expected: list[str]) -> None:
    outcome = _outcome()
    outcome.merge_driver_config = state

    assert outcome.notices() == expected
