"""WP04 / FR-001: recovery COMPOSES — ``doctor --fix`` -> re-run upgrade (SC-001).

This is a **verification** WP: it owns no product module. It proves that three
already-shipped behaviours compose into self-recovery for a wedged project, with
**zero manual git steps** (SC-001) and without requiring version control at all:

* **FR-002 / WP01** (``runner.py`` + ``metadata.py``): a failed migration
  PRESERVES ``schema_version`` instead of erasing it. Before WP01 a mid-migration
  abort dropped ``schema_version``, so a re-run re-detected the project as legacy
  and re-hit the same failing migration on the still-invalid corpus — permanently
  wedged (#3334, P0).
* **FR-008 / WP03** (``status/dup_key_repair.py`` + ``doctor mission-state
  --fix``): heals a legacy dual-key ``review_feedback`` artifact (invalid YAML the
  frontmatter boundary fails CLOSED on, #3372) — the thing an upgrade migration
  trips over.
* **FR-012 / WP01**: a re-run after the corpus is healed applies the migration
  cleanly and stamps the target schema (resumable, no-op on already-done work).

The composition is a **SEQUENCE**, not a new orchestrator (paula-patterns
post-tasks finding: no recovery surface exists and none is needed). The honest
hinge proven here is that the SAME upgrade migration FAILS while the artifact
carries the duplicate key and SUCCEEDS once ``--fix`` has healed it — so the heal
is genuinely what unblocks the upgrade, not incidental.

Scope discipline: ``doctor --fix`` also runs an unrelated mission-state
canonicalization pass (``repair_repo``) that is a *separate* FR path needing full
mission scaffolding (``meta.json`` / status logs). It is isolated here (WP03
CLI-test precedent) so this proof stays pinned to the FR-002 + FR-008 + FR-012
composition and cannot flake on mission-state-repair concerns it does not own.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from kernel.clock import now_utc

from specify_cli.frontmatter import FrontmatterError, FrontmatterManager
from specify_cli.migration.schema_version import (
    REQUIRED_SCHEMA_VERSION,
    get_project_schema_version,
)
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.runner import MigrationRunner

# Green end-to-end acceptance of the wedged -> recovered sequence (#3334 +
# #3372). No ``@pytest.mark.regression``: this is a green composition proof, not
# a red-first open-P0 reproduction, so it stays in its path suite rather than the
# ADR 2026-07-17-1 red-first home (``tests/regression/``). The SC-001 case carries
# ``git_repo`` (real ``git init``) -> integration-tests-upgrade; the no-VCS case
# carries ``fast`` -> fast-tests-upgrade.
pytestmark = pytest.mark.unit

_GET_APPLICABLE = "specify_cli.upgrade.runner.MigrationRegistry.get_applicable"

# Legacy dual-key ``review_feedback`` artifact: an empty ``''`` write followed by
# the real recorded pointer. This is invalid YAML that the canonical frontmatter
# boundary fails CLOSED on (ruamel ``DuplicateKeyError``), so an upgrade migration
# reading it dies — the exact wedge WP03's keep-last-non-empty heal repairs.
_WEDGED_ARTIFACT = (
    "---\n"
    "work_package_id: WP01\n"
    "title: Wedged mission artifact\n"
    "review_feedback: ''\n"
    "subtasks:\n"
    "- T001\n"
    "review_feedback: review-cycle-1.md\n"
    "---\n"
    "Body content.\n"
)
_RECORDED_POINTER = "review-cycle-1.md"


class _ArtifactBoundaryMigration(BaseMigration):
    """A migration that reads a mission artifact via the fail-closed boundary.

    Reproduces a real upgrade tripping over invalid YAML: it FAILS while the
    artifact carries the duplicate ``review_feedback`` key and SUCCEEDS once the
    ``--fix`` heal has removed the empty duplicate. Trigger is the artifact's
    validity, so the heal is the load-bearing precondition for success.
    """

    migration_id = "99.0.0_artifact_boundary"
    description = "Reads a mission artifact through the fail-closed frontmatter boundary"
    target_version = "99.0.0"

    def __init__(self, artifact_path: Path) -> None:
        self._artifact_path = artifact_path

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
        try:
            FrontmatterManager().read(self._artifact_path)
        except FrontmatterError as exc:
            return MigrationResult(
                success=False,
                errors=[f"upgrade tripped on invalid artifact YAML: {exc}"],
            )
        return MigrationResult(success=True, changes_made=["migrated mission artifact"])


def _write_metadata(kittify_dir: Path, version: str, schema_version: int) -> None:
    """Write ``metadata.yaml`` directly (not via the code under test)."""
    kittify_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "spec_kitty": {
            "version": version,
            "initialized_at": now_utc().isoformat(),
            "schema_version": schema_version,
        },
        "environment": {},
        "migrations": {"applied": []},
    }
    (kittify_dir / "metadata.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def _write_wedged_artifact(project_path: Path) -> Path:
    """Materialize the invalid dual-key artifact under ``kitty-specs/``."""
    path = project_path / "kitty-specs" / "mission-wedged" / "tasks" / "WP01.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_WEDGED_ARTIFACT, encoding="utf-8")
    return path


def _build_wedged_project(project_path: Path, schema_version: int) -> Path:
    """Create a project with a below-target schema and the invalid artifact."""
    _write_metadata(project_path / ".kittify", version="3.0.0", schema_version=schema_version)
    return _write_wedged_artifact(project_path)


def _run_upgrade(
    monkeypatch: pytest.MonkeyPatch, project_path: Path, migration: BaseMigration
) -> object:
    runner = MigrationRunner(project_path)
    monkeypatch.setattr(
        _GET_APPLICABLE,
        lambda _from, _to, project_path=None: [migration],  # noqa: ARG005
    )
    return runner.upgrade("99.0.0", include_worktrees=False)


def _doctor_fix(
    project_path: Path, monkeypatch: pytest.MonkeyPatch, *, allow_dirty: bool
) -> None:
    """Drive the real ``doctor mission-state --fix`` CLI dispatch.

    The FR-008 dup-key heal runs for real; the unrelated mission-state
    canonicalization arm (``repair_repo``) is stubbed to a no-op report so this
    proof stays scoped to the recovery composition (WP03 CLI-test precedent).
    """
    import specify_cli.migration.mission_state as mission_state
    from specify_cli.cli.commands import _mission_state_doctor as cmd
    from specify_cli.migration.mission_state import RepairReport

    monkeypatch.setattr(
        mission_state,
        "repair_repo",
        lambda *_a, **_k: RepairReport(
            run_id="noop-composition",
            repo_head=None,
            target_missions=[],
            manifest_path="noop",
            missions=[],
        ),
    )
    cmd.run_mission_state(
        audit=False,
        fix=True,
        json_output=False,
        mission=None,
        fail_on=None,
        fixture_dir=None,
        include_fixtures=False,
        manifest_path=None,
        allow_dirty=allow_dirty,
        repo_root=project_path,
    )


def _artifact_is_invalid(path: Path) -> bool:
    """True when the artifact still trips the fail-closed frontmatter boundary."""
    try:
        FrontmatterManager().read(path)
    except FrontmatterError:
        return True
    return False


def _git(project_path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(project_path), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


# ---------------------------------------------------------------------------
# T013 — SC-001: a wedged git-backed project recovers with ZERO manual git steps.
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_sc001_wedged_project_recovers_with_zero_manual_git_steps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """doctor --fix -> re-run upgrade heals a wedged project without any git step.

    The wedge (invalid artifact + below-target schema) is COMMITTED, mirroring a
    real repo. Recovery then runs with ``allow_dirty=False`` — the operator does
    not pass ``--allow-dirty`` or stash/commit/reset anything. The concrete
    zero-git-steps proof: ``HEAD`` is byte-identical before and after recovery
    (the sequence creates NO commits) yet the project ends consistent.
    """
    assert REQUIRED_SCHEMA_VERSION is not None
    below_required = REQUIRED_SCHEMA_VERSION - 1

    project_path = tmp_path / "repo"
    project_path.mkdir()
    artifact = _build_wedged_project(project_path, schema_version=below_required)

    # Commit the wedged state so the working tree is clean before recovery.
    _git(project_path, "init")
    _git(project_path, "config", "user.email", "test@example.com")
    _git(project_path, "config", "user.name", "Test")
    _git(project_path, "add", "-A")
    _git(project_path, "commit", "-m", "wedged state")
    setup_head = _git(project_path, "rev-parse", "HEAD")

    # 1. A first upgrade trips over the invalid artifact and FAILS.
    first = _run_upgrade(monkeypatch, project_path, _ArtifactBoundaryMigration(artifact))
    assert first.success is False
    # WP01: the failure PRESERVES schema_version (recoverable, not erased/advanced).
    assert get_project_schema_version(project_path) == below_required
    # Still wedged: the artifact remains invalid until healed.
    assert _artifact_is_invalid(artifact) is True

    # 2. Recovery step one: doctor --fix heals the artifact (no --allow-dirty).
    _doctor_fix(project_path, monkeypatch, allow_dirty=False)
    fm, _body = FrontmatterManager().read(artifact)
    assert fm["review_feedback"] == _RECORDED_POINTER  # NFR-002: recorded value kept
    assert fm["work_package_id"] == "WP01"

    # 3. Recovery step two: re-run upgrade now SUCCEEDS and stamps the target.
    second = _run_upgrade(monkeypatch, project_path, _ArtifactBoundaryMigration(artifact))
    assert second.success is True
    assert get_project_schema_version(project_path) == REQUIRED_SCHEMA_VERSION

    # SC-001: recovery created ZERO commits — no manual git steps were required.
    assert _git(project_path, "rev-parse", "HEAD") == setup_head


# ---------------------------------------------------------------------------
# T014 — no-VCS: a wedged project NOT under version control recovers on-disk.
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_no_vcs_wedged_project_recovers_on_disk(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Recovery needs no git checkpoint: a non-git project heals purely on disk.

    ``doctor --fix``'s git-safety preflight is skipped when there is no repo, and
    ``atomic_write`` mutates files directly — so the same doctor --fix -> re-run
    upgrade sequence recovers a project that was never under version control.
    """
    assert REQUIRED_SCHEMA_VERSION is not None
    below_required = REQUIRED_SCHEMA_VERSION - 1

    project_path = tmp_path / "repo"
    project_path.mkdir()
    artifact = _build_wedged_project(project_path, schema_version=below_required)
    # Precondition: genuinely no version control anywhere in the project.
    assert not (project_path / ".git").exists()

    first = _run_upgrade(monkeypatch, project_path, _ArtifactBoundaryMigration(artifact))
    assert first.success is False
    assert get_project_schema_version(project_path) == below_required
    assert _artifact_is_invalid(artifact) is True

    # doctor --fix with allow_dirty=False: git-safety is auto-skipped (no repo),
    # proving no git checkpoint is required to recover.
    _doctor_fix(project_path, monkeypatch, allow_dirty=False)
    fm, _body = FrontmatterManager().read(artifact)
    assert fm["review_feedback"] == _RECORDED_POINTER

    second = _run_upgrade(monkeypatch, project_path, _ArtifactBoundaryMigration(artifact))
    assert second.success is True
    assert get_project_schema_version(project_path) == REQUIRED_SCHEMA_VERSION
    # Recovery never introduced version control.
    assert not (project_path / ".git").exists()
