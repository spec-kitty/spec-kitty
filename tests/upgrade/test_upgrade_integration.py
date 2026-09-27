"""Integration tests for the `spec-kitty upgrade` finalizer wiring (WP04, T023).

Mission: upgrade-command-hardening-01M0N5N4.

These tests drive the REAL command entry point (via a ``typer.Typer`` test
app + ``CliRunner``, mirroring
``tests/specify_cli/upgrade/test_upgrade_provisions_mission_type_activations.py``)
rather than mocking the finalizer wiring away, so a regression in the T017
integration (the single ``finalize_upgrade`` call, the normalized
no-migrations branch, the exit-once invariant) is caught here even though the
seam itself is already unit-pinned by ``tests/upgrade/test_finalizer.py``.

Covers:
  * C4/D-3 — the no-migrations (up-to-date) branch prints a completion
    outcome AND exits 0, derived from the single ``UpgradeOutcome`` (distinct
    from the NFR-001 no-op idempotency assertion in
    ``test_upgrade_idempotency.py``).
  * FR-008/#3392 — ``upgrade --project --yes`` full success exits 0 with a
    printed outcome.
  * T022/D-5 — a FAILED run's exit code equals ``UpgradeOutcome.exit_code``,
    not a stray ``typer.Exit`` surviving somewhere in the tail (the
    pre-refactor code raised directly at upgrade.py:912/924/968/1101 and
    inside ``_run_upgrade_surface_repair``).
"""

from __future__ import annotations

import json
import contextlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

import specify_cli.cli.commands.upgrade as upgrade_cmd
from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.upgrade import autocommit
from specify_cli.upgrade.migrations.base import MigrationResult
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.mark.parametrize("current", ["unknown", "3.2.7rc1"])
@pytest.mark.parametrize("target", ["", "not-a-version", "3.2.7\\x1b[31m"])
def test_target_validator_refuses_malformed_before_selection(current: str, target: str) -> None:
    from specify_cli.upgrade.runner import validate_upgrade_target

    error = validate_upgrade_target(current, target)
    assert error is not None
    assert error.startswith("Invalid upgrade target version: ")
    assert all(character.isprintable() for character in error)


@pytest.mark.parametrize("target", ["3.2.7rc1", "3.2.7rc2", "3.2.7", "3.2.8", "99.0"])
def test_target_validator_keeps_equal_and_higher_eligibility(target: str) -> None:
    from specify_cli.upgrade.runner import validate_upgrade_target

    assert validate_upgrade_target("3.2.7rc1", target) is None


def test_target_validator_diagnoses_malformed_known_current() -> None:
    from specify_cli.upgrade.runner import validate_upgrade_target

    assert validate_upgrade_target("broken", "3.2.7rc1") == "Invalid project metadata version: broken"


_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)
_runner = CliRunner()

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


def _init_project(root: Path, *, version: str = "1.0.0a1") -> None:
    """A minimal, real git-backed Spec Kitty project (up to date at *version*)."""
    root.mkdir(parents=True, exist_ok=True)
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(_METADATA_YAML.format(version=version), encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


def _run_upgrade(args: list[str], cwd: Path):
    """Invoke the real `upgrade` command from *cwd* (mirrors the sibling harness)."""
    with contextlib.chdir(cwd):
        return _runner.invoke(_test_app, args, catch_exceptions=False)


def _last_json_line(output: str) -> dict[str, object]:
    """Decode the final line of stdout as JSON (banner/log lines may precede it)."""
    lines = [line for line in output.strip().splitlines() if line.strip()]
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# (a) No-migrations branch: completion outcome AND exit 0 from one outcome
# ---------------------------------------------------------------------------


def test_no_migrations_outcome_prints_completion_and_exits_zero(tmp_path: Path) -> None:
    """C4/D-3: the normalized no-migrations branch prints a completion
    outcome AND derives exit 0 from the single ``UpgradeOutcome`` — distinct
    from the NFR-001 no-op idempotency assertion (test_upgrade_idempotency.py)."""
    project = tmp_path / "proj"
    _init_project(project)

    result = _run_upgrade(
        ["--target", "1.0.0a1", "--yes", "--no-worktrees", "--json"],
        cwd=project,
    )

    assert result.exit_code == 0, result.output
    payload = _last_json_line(result.output)
    assert payload["status"] == "up_to_date"
    assert payload["success"] is True
    assert payload["errors"] == []


def test_no_migrations_outcome_prints_completion_human_mode(tmp_path: Path) -> None:
    """Same branch, human-readable renderer: a completion line is printed and
    the command exits 0 (no stray raise anywhere in the tail)."""
    project = tmp_path / "proj"
    _init_project(project)

    result = _run_upgrade(["--target", "1.0.0a1", "--yes", "--no-worktrees"], cwd=project)

    assert result.exit_code == 0, result.output
    assert "already up to date" in result.output.lower()


# ---------------------------------------------------------------------------
# (b) #3392 — `upgrade --project --yes` full success exits 0
# ---------------------------------------------------------------------------


def test_project_yes_full_success_exits_zero_with_printed_outcome(tmp_path: Path) -> None:
    """#3392: `upgrade --project --yes` full success prints an outcome and
    exits 0 — the exact regression this mission fixes (the pre-refactor code
    had three independent, divergent success/exit-code formulas)."""
    project = tmp_path / "proj"
    _init_project(project)

    result = _run_upgrade(
        ["--project", "--yes", "--no-worktrees", "--target", "1.0.0a1"],
        cwd=project,
    )

    assert result.exit_code == 0, result.output
    assert "already up to date" in result.output.lower()


# ---------------------------------------------------------------------------
# T022/D-5 — exit-once: a FAILED run's exit code == UpgradeOutcome.exit_code
# ---------------------------------------------------------------------------


def _fail_retained_activation_apply(_self: object) -> bool:
    raise ValueError("forced activation failure")


def test_failed_run_exit_code_equals_outcome_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A FAILED run's exit code comes from ``UpgradeOutcome.exit_code`` — not
    a stray ``typer.Exit`` surviving in the tail (post-tasks squad concern;
    the pre-refactor code raised independently at several sites). Forces the
    failure through the activation-provisioning channel (D-11), the exact
    signal the pre-refactor code used to mutate ``result``/`errors` for."""
    project = tmp_path / "proj"
    _init_project(project)

    monkeypatch.setattr(
        "charter.activation.compiler._PreparedMissionTypeActivations.apply",
        _fail_retained_activation_apply,
    )

    result = _run_upgrade(
        ["--target", "1.0.0a1", "--yes", "--no-worktrees", "--json"],
        cwd=project,
    )

    assert result.exit_code == 1
    payload = _last_json_line(result.output)
    assert payload["success"] is False
    assert "forced activation failure" in payload["errors"]


def test_failed_run_exit_code_equals_outcome_exit_code_human_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same failure channel, human-readable renderer: still exits 1, and the
    failure is rendered (not silently swallowed)."""
    project = tmp_path / "proj"
    _init_project(project)

    monkeypatch.setattr(
        "charter.activation.compiler._PreparedMissionTypeActivations.apply",
        _fail_retained_activation_apply,
    )

    result = _run_upgrade(["--target", "1.0.0a1", "--yes", "--no-worktrees"], cwd=project)

    assert result.exit_code == 1
    # The no-migrations human renderer (_display_no_migrations_results) never
    # printed an "Upgrade failed." banner even pre-refactor — it surfaces the
    # error line directly. What matters here is: the error is rendered AND
    # the exit code is 1, with no stray typer.Exit short-circuiting the tail
    # before the renderer runs.
    assert "forced activation failure" in result.output


# ---------------------------------------------------------------------------
# FIX 1 (MEDIUM-1, FR-003/#3654) — human-mode "left uncommitted" report
# ---------------------------------------------------------------------------
#
# Pre-merge adversarial-squad finding: FR-003/User Story 2 scenario 1 requires
# that "the command reports that changes were left uncommitted" when
# `auto_commit: false` is configured and the run produces real churn. Before
# this fold, the human renderer only ever printed something when a commit
# WAS made (`→ Auto-committed …`) — the config-opt-out-with-real-churn case
# printed nothing at all, leaving the acceptance scenario undischarged even
# though the JSON contract already carried `auto_committed: false` honestly.
#
# These tests drive the real `upgrade()` entry point directly (mirroring
# ``tests/upgrade/test_upgrade_char_net.py``'s call-level harness) rather than
# through a real git repo: `autocommit.git_status_paths` is spied so the
# "would there have been churn to commit" detection (`prepare_upgrade_commit_
# files`) sees a deterministic, test-controlled diff without needing an actual
# git-backed fixture project.


def _setup_minimal_kittify_project(project_path: Path) -> None:
    """The same minimal `.kittify` scaffold `test_upgrade_char_net.py` uses,
    duplicated locally so this file's fixtures don't reach across WP
    boundaries."""
    project_path.mkdir(parents=True, exist_ok=True)
    kittify_dir = project_path / ".kittify"
    kittify_dir.mkdir()
    (kittify_dir / "metadata.yaml").write_text(
        "spec_kitty:\n"
        "  version: '1.0.0a1'\n"
        "  initialized_at: '2026-01-01T00:00:00'\n"
        "environment:\n"
        "  python_version: '3.12'\n"
        "  platform: linux\n"
        "  platform_version: ''\n"
        "migrations:\n"
        "  applied: []\n"
    )


def _stub_fake_migration_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force one applicable, successfully-applied migration (real migration
    mechanics are out of scope here — only the finalizer's post-migration
    reporting tail is under test)."""
    fake_migration = MagicMock(
        migration_id="3.2.0a4_fake_churn_migration",
        description="fake migration for FIX-1 coverage",
        target_version="3.2.0a4",
    )
    monkeypatch.setattr(
        "specify_cli.upgrade.registry.MigrationRegistry.get_applicable",
        lambda *_a, **_kw: [fake_migration],
    )
    monkeypatch.setattr(
        "specify_cli.upgrade.runner.MigrationRunner.upgrade",
        lambda self, *args, **kwargs: UpgradeResult(
            success=True,
            from_version="1.0.0a1",
            to_version="3.2.0a4",
            migrations_applied=["3.2.0a4_fake_churn_migration"],
            migration_results={"3.2.0a4_fake_churn_migration": MigrationResult(success=True)},
        ),
    )


def _stub_churn_git_status(monkeypatch: pytest.MonkeyPatch, churn_paths: set[str]) -> None:
    """First `git_status_paths` call is the pre-migration baseline (clean);
    every later call reports *churn_paths* — the real post-migration diff the
    left-uncommitted detector (`prepare_upgrade_commit_files`) reads."""
    calls = {"count": 0}

    def _fake_status(_repo_path: Path) -> set[str]:
        calls["count"] += 1
        if calls["count"] == 1:
            return set()
        return set(churn_paths)

    monkeypatch.setattr(autocommit, "git_status_paths", _fake_status)


def test_auto_commit_disabled_reports_left_uncommitted_human_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """FR-003/US2 scenario 1: `auto_commit: false` + real churn must print an
    explicit "left uncommitted" line in human-mode output — not stay silent."""
    project_path = tmp_path / "proj"
    _setup_minimal_kittify_project(project_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo: False)
    _stub_churn_git_status(monkeypatch, {".kittify/metadata.yaml"})
    _stub_fake_migration_run(monkeypatch)

    upgrade_cmd.upgrade(
        dry_run=False,
        plan_json=False,
        yes=False,
        no_nag=False,
        force=True,
        target="3.2.0a4",
        json_output=False,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
        agent_check=False,
        agent_choice=None,
        agent_latest=None,
    )

    output = capsys.readouterr().out
    assert "left uncommitted" in output.lower(), output
    assert "auto_commit is disabled" in output


def test_auto_commit_disabled_json_mode_still_reports_auto_committed_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same scenario, `--json`: the machine contract must keep reporting
    `auto_committed: false` honestly (unchanged by this fold — JSON consumers
    already had the honest signal; only human mode was silent)."""
    project_path = tmp_path / "proj"
    _setup_minimal_kittify_project(project_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo: False)
    _stub_churn_git_status(monkeypatch, {".kittify/metadata.yaml"})
    _stub_fake_migration_run(monkeypatch)

    upgrade_cmd.upgrade(
        dry_run=False,
        plan_json=False,
        yes=False,
        no_nag=False,
        force=True,
        target="3.2.0a4",
        json_output=True,
        verbose=False,
        no_worktrees=True,
        cli=False,
        project=False,
        agent_check=False,
        agent_choice=None,
        agent_latest=None,
    )

    data = json.loads(capsys.readouterr().out.strip())
    assert data["auto_committed"] is False
    assert data["success"] is True


# ---------------------------------------------------------------------------
# FIX 2 (MEDIUM-2, SC-002) — the worktree opt-out decision genuinely reaches
# the fan-out, not just `should_auto_commit_for_worktree` in isolation
# ---------------------------------------------------------------------------


def test_auto_commit_disabled_worktree_decision_reaches_runner_fanout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """SC-002 end-to-end: with `auto_commit: false`, (1)
    ``should_auto_commit_for_worktree`` itself returns False, AND (2) that
    decision genuinely reaches ``MigrationRunner.upgrade``'s ``auto_commit``
    kwarg — the seam the worktree fan-out (`runner._upgrade_worktrees`)
    consults for every sibling worktree (main-checkout coverage alone would
    not prove the worktree-scope decision was actually wired through)."""
    project_path = tmp_path / "proj"
    _setup_minimal_kittify_project(project_path)
    monkeypatch.setattr(Path, "cwd", lambda: project_path)
    monkeypatch.setattr(autocommit, "get_auto_commit_default", lambda _repo: False)
    _stub_churn_git_status(monkeypatch, {".kittify/metadata.yaml"})

    assert autocommit.should_auto_commit_for_worktree(project_path, dry_run=False) is False

    fake_migration = MagicMock(
        migration_id="3.2.0a4_fake_churn_migration",
        description="fake migration for FIX-2 coverage",
        target_version="3.2.0a4",
    )
    monkeypatch.setattr(
        "specify_cli.upgrade.registry.MigrationRegistry.get_applicable",
        lambda *_a, **_kw: [fake_migration],
    )

    captured_auto_commit: list[bool] = []

    def _spy_runner_upgrade(self: object, *args: object, **kwargs: object) -> UpgradeResult:
        captured_auto_commit.append(bool(kwargs.get("auto_commit")))
        return UpgradeResult(
            success=True,
            from_version="1.0.0a1",
            to_version="3.2.0a4",
            migrations_applied=["3.2.0a4_fake_churn_migration"],
            migration_results={"3.2.0a4_fake_churn_migration": MigrationResult(success=True)},
        )

    monkeypatch.setattr(
        "specify_cli.upgrade.runner.MigrationRunner.upgrade",
        _spy_runner_upgrade,
    )

    upgrade_cmd.upgrade(
        dry_run=False,
        plan_json=False,
        yes=False,
        no_nag=False,
        force=True,
        target="3.2.0a4",
        json_output=True,
        verbose=False,
        no_worktrees=False,  # the fan-out decision is only wired when worktrees are in play
        cli=False,
        project=False,
        agent_check=False,
        agent_choice=None,
        agent_latest=None,
    )

    assert captured_auto_commit == [False], (
        "the config opt-out must reach MigrationRunner.upgrade's auto_commit kwarg (the seam runner._upgrade_worktrees fans out to every worktree from)"
    )


# ---------------------------------------------------------------------------
# Static guard — no stray typer.Exit left in the tail (reviewer guidance)
# ---------------------------------------------------------------------------


def test_no_stray_noqa_c901_marker() -> None:
    """DoD: ``ruff``'s complexity suppression must be gone from ``upgrade()``
    (T021) — the entry decomposition must have brought it under the ceiling
    without a suppression comment."""
    import inspect

    from specify_cli.cli.commands import upgrade as upgrade_module

    source = inspect.getsource(upgrade_module)
    assert "noqa: C901" not in source


@pytest.mark.parametrize("machine", [False, True], ids=["human", "legacy-json"])
@pytest.mark.parametrize("fault", ["incomplete", "exception"])
@pytest.mark.parametrize("schema_version", [3, 1], ids=["compatible", "stale"])
def test_dry_run_repair_assessment_failure_is_visible_and_write_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    machine: bool,
    fault: str,
    schema_version: int,
) -> None:
    from dataclasses import replace
    from specify_cli.tool_surface.operations import Diagnostic
    from specify_cli.upgrade import assessment as repair_assessment
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    _init_project(project)
    metadata = project / ".kittify/metadata.yaml"
    metadata.write_text(metadata.read_text().replace("spec_kitty:\n", f"spec_kitty:\n  schema_version: {schema_version}\n"))
    # Match the public preview witness: read-only git queries must not refresh
    # the index through optional locks while we compare exact node identities.
    monkeypatch.setenv("GIT_OPTIONAL_LOCKS", "0")
    original = repair_assessment.prepare_upgrade_repairs

    def failed_assessment(*args, **kwargs):
        if fault == "exception":
            raise OSError("fixture repair inventory unavailable")
        prepared = original(*args, **kwargs)
        return replace(
            prepared,
            diagnostics=(
                Diagnostic(
                    "fixture_incomplete",
                    "upgrade",
                    "error",
                    "fixture repair inventory incomplete",
                ),
            ),
        )

    monkeypatch.setattr(repair_assessment, "prepare_upgrade_repairs", failed_assessment)
    before = snapshot({"project": project})
    args = ["--dry-run", "--target", "1.0.0a1", "--no-worktrees", "--yes"]
    result = _run_upgrade(args + (["--json"] if machine else []), cwd=project)
    assert result.exit_code == 1, result.output
    assert "Supporting repair preview incomplete" in result.output
    assert "fixture repair inventory" in result.output
    if machine:
        payload = json.loads(result.output)
        assert len(payload["rendered_human"]) <= 1024
        assert payload["exit_code"] == 1
        assert payload["decision"] == ("ALLOW" if schema_version == 3 else "BLOCK_PROJECT_MIGRATION")
        assert payload["project"]["state"] == ("compatible" if schema_version == 3 else "stale")
    assert_unchanged(before, snapshot({"project": project}))


def test_dry_run_oversized_repair_notice_respects_json_text_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    project = tmp_path / "project"
    _init_project(project)
    monkeypatch.setenv("GIT_OPTIONAL_LOCKS", "0")
    notice = "Supporting repair preview incomplete: " + "x" * 2048
    monkeypatch.setattr(upgrade_cmd, "_supporting_repair_preview", lambda _: (notice, True))
    before = snapshot({"project": project})
    result = _run_upgrade(["--dry-run", "--target", "1.0.0a1", "--no-worktrees", "--yes", "--json"], cwd=project)
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert len(payload["rendered_human"]) <= 1024
    assert "Supporting repair preview incomplete" in payload["rendered_human"]
    assert payload["exit_code"] == result.exit_code
    assert_unchanged(before, snapshot({"project": project}))
