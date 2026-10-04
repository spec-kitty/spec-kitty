"""WP05 T024/T025 — worktree schema-stamp guard + fatal worktree-failure surfacing.

Contracts ``contracts/seam-contracts.md`` C5 (FR-009, #3376) and FR-012
(``data-model.md``'s ``UpgradeOutcome.worktree_failures``).

C5: ``MigrationRunner._upgrade_worktrees`` unconditionally stamped
``schema_version`` on every touched worktree (``:461-462`` pre-fix), even one
whose migration recorded ``failed``. This is a GUARD -- a NEW per-worktree
``worktree_failed`` flag, sticky for the remainder of that worktree's
migrations -- not a restore: the worktree loop captures no per-worktree
pre-run schema (unlike the main path's ``pre_run_schema_version`` capture), so
the fix is "leave whatever is present on disk," never "re-stamp the target."

FR-012: a fatal worktree migration failure must be visible in a structured
channel (``UpgradeResult.worktree_failures``), not just folded anonymously
into the pre-existing ``errors``/``warnings`` strings, so WP04's
``UpgradeOutcome`` can flip effective success + exit code non-zero.

Both tests follow the injection pattern from
``tests/upgrade/test_failed_upgrade_recoverable.py``
(``_register_stub_failing_migration``) and
``tests/upgrade/test_upgrade_worktree_commit.py`` (real git worktrees): a
fresh ``BaseMigration`` subclass is registered whose ``target_version`` sits
inside the version window (``from_v < target <= to_v``) and whose
``detect()`` returns True, so it is actually SELECTED and APPLIED inside the
worktree -- without that the failing migration never runs and the guard is
never exercised (the exact vacuous-test trap the #3334 test docstring and
this WP's task file both flag).
"""

from __future__ import annotations

import json
import contextlib
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_cli_app = typer.Typer(add_completion=False)
_cli_app.command()(upgrade)
_cli_runner = CliRunner()


def _invoke_upgrade(args: list[str], cwd: Path):
    """Invoke the real `upgrade` command from *cwd* (mirrors
    ``tests/upgrade/test_upgrade_integration.py``'s harness)."""
    with contextlib.chdir(cwd):
        return _cli_runner.invoke(_cli_app, args, catch_exceptions=False)


def _last_json_line(output: str) -> dict[str, Any]:
    """Decode the final stdout line as JSON (banner/log lines may precede it)."""
    lines = [line for line in output.strip().splitlines() if line.strip()]
    return json.loads(lines[-1])


_FROM_VERSION = "3.2.0"
_TARGET_VERSION = "3.2.1"

_METADATA_YAML = (
    "spec_kitty:\n"
    "  version: '{version}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "  schema_version: {schema_version}\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)

# Genuinely stale so a real re-stamp to REQUIRED is a non-fakeable assertion
# (not a coincidence if the guard already happened to leave REQUIRED behind).
_STALE_SCHEMA_VERSION = (REQUIRED_SCHEMA_VERSION or 0) - 1
assert _STALE_SCHEMA_VERSION != REQUIRED_SCHEMA_VERSION


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (root / ".kittify").mkdir()
    (root / ".kittify" / "metadata.yaml").write_text(
        _METADATA_YAML.format(version=_FROM_VERSION, schema_version=_STALE_SCHEMA_VERSION),
        encoding="utf-8",
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


def _add_worktree(root: Path, name: str, branch: str) -> Path:
    # The new worktree checks out the same commit as root, so its
    # .kittify/metadata.yaml already carries the STALE fixture content
    # written in _init_repo -- no separate write/commit needed here.
    wt = root / ".worktrees" / name
    _git(root, "worktree", "add", "-q", "-b", branch, str(wt))
    return wt


#: Branch prefix of a NON-integrating worktree (#5457). A ``kitty/mission-...``
#: worktree integrates back into the target branch and upgrade skips it, so the
#: #3376 / FR-012 guards are exercised on worktrees upgrade still writes.
NON_INTEGRATING_PREFIX = "wip/"


def _wt_schema_version(kittify_dir: Path) -> int | None:
    data = yaml.safe_load((kittify_dir / "metadata.yaml").read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        return None
    spec_kitty = data.get("spec_kitty")
    if not isinstance(spec_kitty, dict):
        return None
    value = spec_kitty.get("schema_version")
    return value if isinstance(value, int) else None


def _register_stub_migration(migration_id: str, *, succeeds: bool) -> type[BaseMigration]:
    """Register a migration selected for this worktree's version window.

    ``target_version`` matches ``_TARGET_VERSION`` (the value ``upgrade()`` is
    invoked with below) so ``MigrationRegistry.get_applicable`` actually
    selects it (``from_v < target <= to_v``), and ``detect()`` unconditionally
    returns True so it is applied, not skipped as "not needed."
    """
    MigrationRegistry.clear()

    class _StubMigration(BaseMigration):
        description = "WP05 T024/T025 stub migration"
        target_version = _TARGET_VERSION
        runs_on_worktrees = True

        def detect(self, project_path: Path) -> bool:  # noqa: ARG002
            return True

        def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
            return True, ""

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
            if succeeds:
                return MigrationResult(success=True, changes_made=["stub applied"])
            return MigrationResult(success=False, errors=["stub failure for T024/T025 repro"])

    _StubMigration.migration_id = migration_id
    MigrationRegistry.register(_StubMigration)
    return _StubMigration


def test_failed_worktree_migration_does_not_advance_schema_version(tmp_path: Path) -> None:
    """T024 (C5, #3376): a worktree whose migration fails must NOT have its
    ``schema_version`` stamped to ``REQUIRED_SCHEMA_VERSION`` -- it is left
    exactly as it was on disk (a guard, not a restore)."""
    root = tmp_path / "repo"
    _init_repo(root)
    wt = _add_worktree(root, "lane-a", f"{NON_INTEGRATING_PREFIX}lane-a")

    try:
        _register_stub_migration("test_t024_stub_failing", succeeds=False)

        result = MigrationRunner(root).upgrade(_TARGET_VERSION, dry_run=False, include_worktrees=True)

        # Sanity: the stub really ran (and failed) inside the worktree, not
        # skipped -- else this whole test would be vacuous (the #3334 trap).
        assert any("lane-a" in e for e in result.errors), result.errors

        post_schema = _wt_schema_version(wt / ".kittify")
        assert post_schema == _STALE_SCHEMA_VERSION, (
            f"a failed worktree migration must not advance schema_version (got {post_schema!r}, expected the untouched stale value {_STALE_SCHEMA_VERSION!r})"
        )
        assert post_schema != REQUIRED_SCHEMA_VERSION
    finally:
        MigrationRegistry.clear()


def test_successful_worktree_migration_still_advances_schema_version(tmp_path: Path) -> None:
    """Guard-rail: the new flag must not regress the existing success path --
    a worktree whose migration succeeds still gets stamped to REQUIRED."""
    root = tmp_path / "repo"
    _init_repo(root)
    wt = _add_worktree(root, "lane-b", f"{NON_INTEGRATING_PREFIX}lane-b")

    try:
        _register_stub_migration("test_t024_stub_succeeding", succeeds=True)

        result = MigrationRunner(root).upgrade(_TARGET_VERSION, dry_run=False, include_worktrees=True)
        assert result.worktree_failures == []

        assert _wt_schema_version(wt / ".kittify") == REQUIRED_SCHEMA_VERSION
    finally:
        MigrationRegistry.clear()


def test_integrating_worktree_is_skipped_not_stamped(tmp_path: Path) -> None:
    """#5457: a lane worktree (``kitty/mission-...``) is skipped outright: no
    migration runs there, no schema stamp, no failure; the non-integrating
    sibling in the same run is still stamped."""
    root = tmp_path / "repo"
    _init_repo(root)
    lane = _add_worktree(root, "lane-z", "kitty/mission-lane-z")
    sibling = _add_worktree(root, "lane-y", f"{NON_INTEGRATING_PREFIX}lane-y")
    lane_metadata = (lane / ".kittify" / "metadata.yaml").read_bytes()

    try:
        _register_stub_migration("test_5457_stub_succeeding", succeeds=True)

        result = MigrationRunner(root).upgrade(_TARGET_VERSION, dry_run=False, include_worktrees=True)

        assert result.worktree_failures == []
        assert not any("lane-z" in message for message in [*result.errors, *result.warnings])
        assert (lane / ".kittify" / "metadata.yaml").read_bytes() == lane_metadata
        assert _wt_schema_version(lane / ".kittify") == _STALE_SCHEMA_VERSION
        assert _wt_schema_version(sibling / ".kittify") == REQUIRED_SCHEMA_VERSION
    finally:
        MigrationRegistry.clear()


def test_failed_worktree_migration_is_surfaced_in_worktree_failures(tmp_path: Path) -> None:
    """T025 (FR-012): a fatal worktree failure must appear in the structured
    ``UpgradeResult.worktree_failures`` channel -- not just be folded silently
    into ``errors``/``warnings`` where a caller has to string-match to notice.
    """
    root = tmp_path / "repo"
    _init_repo(root)
    _add_worktree(root, "lane-c", f"{NON_INTEGRATING_PREFIX}lane-c")

    try:
        _register_stub_migration("test_t025_stub_failing", succeeds=False)

        result = MigrationRunner(root).upgrade(_TARGET_VERSION, dry_run=False, include_worktrees=True)

        assert result.worktree_failures, "fatal worktree failure must be surfaced structurally (FR-012)"
        assert any("lane-c" in f for f in result.worktree_failures)
        # Still present in the pre-existing channel too (backward compat).
        assert any("lane-c" in e for e in result.errors)
    finally:
        MigrationRegistry.clear()


def test_non_fatal_cannot_apply_note_does_not_populate_worktree_failures(tmp_path: Path) -> None:
    """A worktree migration that merely can't be applied yet (a warning-only
    note) must not be classified as a fatal worktree failure."""
    MigrationRegistry.clear()

    class _CannotApplyMigration(BaseMigration):
        migration_id = "test_t025_cannot_apply"
        description = "WP05 T025 non-fatal can_apply refusal"
        target_version = _TARGET_VERSION
        runs_on_worktrees = True

        def detect(self, project_path: Path) -> bool:  # noqa: ARG002
            return True

        def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
            return False, "not safe yet"

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
            raise AssertionError("apply() must not be called when can_apply() is False")

    root = tmp_path / "repo"
    _init_repo(root)
    _add_worktree(root, "lane-d", f"{NON_INTEGRATING_PREFIX}lane-d")

    try:
        MigrationRegistry.register(_CannotApplyMigration)

        result = MigrationRunner(root).upgrade(_TARGET_VERSION, dry_run=False, include_worktrees=True)

        assert result.worktree_failures == []
        assert any("Cannot apply" in w for w in result.warnings)
    finally:
        MigrationRegistry.clear()


# ---------------------------------------------------------------------------
# FR-012 errors-channel consistency: ``UpgradeOutcome.errors()`` must fold
# ``UpgradeOutcome.worktree_failures`` (upgrade/outcome.py), so a ``--json`` consumer
# keying on ``errors`` to explain a non-zero exit code is never handed an
# empty array.
# ---------------------------------------------------------------------------


def _init_no_migrations_project(root: Path, *, version: str = "1.0.0a1") -> None:
    """A minimal, real git-backed project already at *version* (no migrations
    pending) -- mirrors ``tests/upgrade/test_upgrade_integration.py``'s
    ``_init_project`` fixture, kept local here so this file's worktree-stamp
    concern stays self-contained."""
    root.mkdir(parents=True, exist_ok=True)
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(
        (
            "spec_kitty:\n"
            f"  version: '{version}'\n"
            "  initialized_at: '2026-01-01T00:00:00'\n"
            "environment:\n"
            "  python_version: '3.12'\n"
            "  platform: linux\n"
            "  platform_version: ''\n"
            "migrations:\n"
            "  applied: []\n"
        ),
        encoding="utf-8",
    )
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


def test_no_migrations_worktree_stamp_failure_surfaces_in_json_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-012 errors-channel gap: the no-migrations branch's worktree-stamp
    pass (``_build_no_migrations_outcome`` -> ``_run_no_migrations_worktree_stamp``
    -> ``MigrationRunner.upgrade_worktrees_only``) records a fatal failure
    ONLY into ``UpgradeOutcome.worktree_failures`` and ``warnings`` -- never
    into ``result.errors``. ``UpgradeOutcome.effective_success`` already
    flips ``success: false`` / ``status: "failed"`` off a non-empty
    ``worktree_failures`` (FR-012); ``UpgradeOutcome.errors()`` -- the single
    place both renderers source ``errors`` from -- must fold that channel
    too, or a ``--json`` consumer keying on ``errors`` to explain the
    non-zero exit gets an EMPTY array.

    ``upgrade_worktrees_only`` always calls the private impl with an empty
    ``migrations`` list (pinned by
    ``test_upgrade_auto_commit_unit.py::test_upgrade_worktrees_only_delegates_to_private_impl``),
    so today's real runner can never itself populate
    ``worktree_failures`` through this exact call path -- the method is
    stubbed here to simulate the failure and drive the real CLI entry point
    end to end, pinning the ``errors()`` contract regardless of how
    the failure got into that channel.
    """
    project = tmp_path / "proj"
    _init_no_migrations_project(project)
    # A worktree must exist for the no-migrations branch's worktree-stamp
    # guard to actually attempt the (stubbed) pass; its content is otherwise
    # irrelevant since ``upgrade_worktrees_only`` is replaced below.
    (project / ".worktrees" / "lane-x").mkdir(parents=True)

    failure_reason = "Worktree lane-x: simulated worktree-stamp failure"

    def _fake_upgrade_worktrees_only(
        self: MigrationRunner,
        target_version: str,  # noqa: ARG001
        dry_run: bool = False,  # noqa: ARG001
        auto_commit: bool = False,  # noqa: ARG001
    ) -> dict[str, Any]:
        return {
            "warnings": [],
            "errors": [failure_reason],
            "worktree_failures": [failure_reason],
        }

    monkeypatch.setattr(MigrationRunner, "upgrade_worktrees_only", _fake_upgrade_worktrees_only)

    result = _invoke_upgrade(["--target", "1.0.0a1", "--yes", "--json"], cwd=project)

    assert result.exit_code == 1, result.output
    payload = _last_json_line(result.output)
    assert payload["status"] == "failed"
    assert payload["success"] is False
    assert payload["errors"], "errors channel must not be empty when success is false (FR-012 consistency)"
    assert any(failure_reason in e for e in payload["errors"]), payload["errors"]


def test_migrations_pending_worktree_failure_not_duplicated_in_json_errors(
    tmp_path: Path,
) -> None:
    """Guard-rail: the migrations-pending path already mirrors a fatal
    worktree failure into both ``UpgradeResult.errors`` and
    ``UpgradeResult.worktree_failures`` from the SAME ``failure_messages``
    list (``MigrationRunner._upgrade_worktrees``). Folding
    ``worktree_failures`` into ``UpgradeOutcome.errors()`` must be deduplicated
    against messages already present in ``result.errors``, or this
    pre-existing (already-correct) path would start reporting the same
    worktree failure twice.
    """
    root = tmp_path / "repo"
    _init_repo(root)
    _add_worktree(root, "lane-e", f"{NON_INTEGRATING_PREFIX}lane-e")

    try:
        _register_stub_migration("test_no_dup_stub_failing", succeeds=False)

        result = _invoke_upgrade(
            ["--target", _TARGET_VERSION, "--yes", "--json"],
            cwd=root,
        )

        assert result.exit_code == 1, result.output
        payload = _last_json_line(result.output)
        assert payload["status"] == "failed"
        assert payload["success"] is False
        matches = [e for e in payload["errors"] if "lane-e" in e]
        assert matches, payload["errors"]
        assert len(matches) == 1, f"worktree failure must appear exactly once in errors, got {matches!r}"
    finally:
        MigrationRegistry.clear()
