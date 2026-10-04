"""Fold for PR #3246: ``spec-kitty upgrade`` heals a missing
``mission_type_activations`` key for pre-rc39 (rc36-rc38) projects.

PR #3246 removed the implicit "all four built-ins" backfill and made mission
creation fail closed (``CharterPackConfigError``) whenever a project's
``.kittify/config.yaml`` lacks ``mission_type_activations``. Fresh
``spec-kitty init`` got a provisioner
(:func:`specify_cli.provisioning.default_charter.provision_default_mission_type_activations`),
but ``spec-kitty upgrade`` had no equivalent seeder for existing projects: the
only pre-existing seeder is the version-pinned
``3.2.0rc35_activate_builtin_mission_types`` migration, and
``MigrationRegistry.get_applicable``'s ``from_v < target <= to_v`` window
never selects a migration targeting a version at or below ``from_version`` —
so a project first initialised on rc36-rc38 (already past rc35) is stranded
on every subsequent ``upgrade``, even though the create-gate's own error
message tells the operator to run ``spec-kitty upgrade``.

This suite:

* pins the pre-fix defect directly at the create-gate (``existing_mission_types``
  / ``create_mission_core``) so the stranding is provable independent of any
  particular CLI wiring;
* proves ``spec-kitty upgrade`` now heals a stranded project (the exact
  ``from_version == target_version`` / no-applicable-migrations shape that
  the rc35 migration's version window can never reach);
* proves the heal is idempotent and never clobbers an authored empty list
  (mirroring ``tests/specify_cli/cli/commands/test_init_provisioning.py``'s
  fresh-init parity checks); and
* unit-pins the new ``_provision_missing_mission_type_activations`` CLI
  helper's dry-run and fail-closed behaviour in isolation.

WP01 (#3282) extends this suite: the fix above only ever wrote
``mission_type_activations`` into ``.kittify/config.yaml``, but a
pointer-based/migrated project (``config.yaml`` carries a ``charter:``
pointer to ``charter.yaml``) reads activations from the pointed-at
``charter.yaml`` (``PackContext.from_config`` / INV-2). The write side was
pointer-blind, so the key it wrote into ``config.yaml`` was never read by
anything — the effective registry stayed empty and mission creation kept
failing closed even after a "successful" upgrade. These additional tests:

* prove ``spec-kitty upgrade`` heals a pointer-based project by writing into
  the resolved ``charter.yaml`` write authority, not ``config.yaml`` (C-WP01);
* prove an authored-empty ``mission_type_activations: []`` in ``charter.yaml``
  is preserved (additive/idempotent parity with the ``config.yaml`` case)
  AND that the dry-run preview predicate agrees (never falsely reports
  pending for a deliberate empty list); and
* pin the dangling/unreadable ``charter:`` pointer contract: the preview
  predicate must not crash (``resolve_activation_write_target`` raises
  ``CharterPackConfigError`` in that case) — it reports a stable, honest
  "pending" signal instead of silently swallowing the broken pointer.
"""

from __future__ import annotations

import contextlib
import subprocess
from kernel.clock import now_utc
from pathlib import Path
from typing import Any

import pytest
import typer
from click.testing import Result
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.mission_type_profiles import existing_mission_types
from charter.activation.pack_context import CharterPackConfigError, PackContext
from specify_cli.cli.commands.upgrade import (
    _mission_type_activation_provisioning_pending,
    _provision_missing_mission_type_activations,
    upgrade,
)
from specify_cli.core.mission_creation import create_mission_core
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SAFE_YAML = YAML(typ="safe")


@pytest.mark.parametrize("pointer", [False, True])
def test_same_version_provisioning_owner_matches_prepared_bytes(tmp_path: Path, pointer: bool) -> None:
    """Real upgrade helper consumes compiler preparation in both P7 layouts."""
    from charter.activation.compiler import prepare_mission_type_activations
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    if pointer:
        target = _write_pointer_charter_project(tmp_path)
    else:
        _write_stranded_project(tmp_path)
        target = tmp_path / ".kittify/config.yaml"
    authored = target.read_bytes() + b'# keep comment\nunowned:\n  list:\n    - "quoted"\n'
    target.write_bytes(authored)
    before = snapshot({"project": tmp_path})
    prepared = prepare_mission_type_activations(tmp_path)
    assert prepared.mission_type_activations
    assert_unchanged(before, snapshot({"project": tmp_path}))

    _provision_missing_mission_type_activations(tmp_path, dry_run=False)

    assert target.read_bytes() == prepared.write.desired_bytes
    assert target.read_bytes().startswith(authored)
    assert {(e.path, e.action) for e in net_delta(before, snapshot({"project": tmp_path}))} == {
        (".kittify/charter/charter.yaml" if pointer else ".kittify/config.yaml", "update")
    }
    after = snapshot({"project": tmp_path})
    _provision_missing_mission_type_activations(tmp_path, dry_run=False)
    assert_unchanged(after, snapshot({"project": tmp_path}))


_STRANDED_FROM_VERSION = "3.2.0rc37"  # past rc35, never re-selected by get_applicable


def _load_config(config_file: Path) -> dict[str, Any]:
    return _SAFE_YAML.load(config_file) or {}


def _write_stranded_project(project: Path, *, config_body: str = "vcs:\n  type: git\n") -> None:
    """Build a project pinned at ``_STRANDED_FROM_VERSION`` lacking the key.

    Mirrors a project first initialised on rc36-rc38: ``config.yaml`` has no
    ``mission_type_activations`` key, and ``metadata.yaml`` records a version
    already past the rc35 migration's ``target_version``.
    """
    kittify = project / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(config_body, encoding="utf-8")

    metadata = ProjectMetadata(
        version=_STRANDED_FROM_VERSION,
        initialized_at=now_utc(),
        python_version="3.11",
        platform="test",
        platform_version="test",
    )
    metadata.save(kittify)
    # Schema version must sit inside [MIN_SUPPORTED, MAX_SUPPORTED] or the
    # too-new/too-old CLI guards fire before the migration/provisioning path
    # this suite is exercising is ever reached.
    from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA

    MigrationRunner._stamp_schema_version(kittify, MAX_SUPPORTED_SCHEMA)


_POINTER_CONFIG_BODY = "vcs:\n  type: git\ncharter: .kittify/charter/charter.yaml\n"

# A migrated charter.yaml lacking the WP04 provisioning key -- the exact
# broken shape a pointer-based project can be stranded in (mirrors
# tests/charter/test_mission_type_activation_emit.py's fixture).
_CHARTER_YAML_WITHOUT_KEY = """\
schema_version: "2.0.0"
governance:
  testing: {}
directives: []
catalog: {}
metadata:
  bundle_schema_version: 2
"""


def _write_pointer_charter_project(project: Path, *, charter_body: str = _CHARTER_YAML_WITHOUT_KEY) -> Path:
    """Build a stranded, pointer-based project: ``config.yaml`` -> ``charter.yaml``.

    Reuses :func:`_write_stranded_project`'s stranding shape (metadata pinned
    at ``_STRANDED_FROM_VERSION``, schema stamped in the supported range) but
    with ``config.yaml`` carrying a ``charter:`` pointer instead of embedding
    activation keys inline -- the migrated-project shape
    ``resolve_activation_write_target``/``PackContext.from_config`` read and
    write against. Returns the pointed-at ``charter.yaml`` path.
    """
    _write_stranded_project(project, config_body=_POINTER_CONFIG_BODY)
    charter_dir = project / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "charter.yaml"
    charter_path.write_text(charter_body, encoding="utf-8")
    return charter_path


def _init_git_repo(repo: Path) -> None:
    (repo / "kitty-specs").mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)


_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)
_runner = CliRunner()


def _run_upgrade(args: list[str], cwd: Path) -> Result:
    with contextlib.chdir(cwd):
        return _runner.invoke(_test_app, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Pre-fix defect, pinned directly at the create-gate (independent of any
# particular upgrade-CLI wiring) — proves the stranding is real.
# ---------------------------------------------------------------------------


def test_stranded_project_fails_closed_at_the_create_gate(tmp_path: Path) -> None:
    """A config-absent-key project blocks mission creation with CharterPackConfigError."""
    project = tmp_path / "stranded"
    project.mkdir()
    _write_stranded_project(project)
    _init_git_repo(project)

    assert existing_mission_types(project) == []

    with pytest.raises(CharterPackConfigError, match="CHARTER_PACK_CONFIG_INVALID") as exc:
        create_mission_core(project, "stranded-mission", allow_worktree_context=True)
    assert "spec-kitty upgrade" in exc.value.body


# ---------------------------------------------------------------------------
# `spec-kitty upgrade` now heals the stranded project.
#
# from_version == target_version reproduces the exact "no applicable
# migration" shape MigrationRegistry.get_applicable produces once a project
# is already past rc35 — the CLI's "already up to date" branch, which
# bypasses MigrationRunner.upgrade() entirely and is the funnel the rc36-rc38
# stranding actually falls through.
# ---------------------------------------------------------------------------


def test_upgrade_heals_stranded_project_and_unblocks_mission_creation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "stranded"
    project.mkdir()
    _write_stranded_project(project)
    _init_git_repo(project)

    assert existing_mission_types(project) == []

    result = _run_upgrade(
        ["--target", _STRANDED_FROM_VERSION, "--force", "--no-worktrees"],
        cwd=project,
    )
    assert result.exit_code == 0, result.output

    config_data = _load_config(project / ".kittify" / "config.yaml")
    activations = config_data.get("mission_type_activations")
    assert activations, f"mission_type_activations still absent/empty after upgrade: {config_data}"

    assert existing_mission_types(project) != []

    created = create_mission_core(project, "healed-mission", allow_worktree_context=True)
    assert created.mission_slug.startswith("healed-mission-")


def test_upgrade_provisioning_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A second real upgrade run leaves the healed activation list untouched."""
    project = tmp_path / "stranded"
    project.mkdir()
    _write_stranded_project(project)
    _init_git_repo(project)

    first = _run_upgrade(
        ["--target", _STRANDED_FROM_VERSION, "--force", "--no-worktrees"],
        cwd=project,
    )
    assert first.exit_code == 0, first.output
    config_file = project / ".kittify" / "config.yaml"
    after_first = config_file.read_text(encoding="utf-8")

    second = _run_upgrade(
        ["--target", _STRANDED_FROM_VERSION, "--force", "--no-worktrees"],
        cwd=project,
    )
    assert second.exit_code == 0, second.output
    after_second = config_file.read_text(encoding="utf-8")

    assert after_second == after_first


def test_upgrade_preserves_authored_empty_activation_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An authored empty list is a deliberate zero-types state, not a gap to heal."""
    project = tmp_path / "stranded"
    project.mkdir()
    _write_stranded_project(project, config_body="vcs:\n  type: git\nmission_type_activations: []\n")
    _init_git_repo(project)

    result = _run_upgrade(
        ["--target", _STRANDED_FROM_VERSION, "--force", "--no-worktrees"],
        cwd=project,
    )
    assert result.exit_code == 0, result.output

    config_data = _load_config(project / ".kittify" / "config.yaml")
    assert config_data["mission_type_activations"] == []
    # Still blocked -- an authored empty list is unchanged (C-008), so the
    # create-gate must still fail closed exactly as before the upgrade.
    assert existing_mission_types(project) == []
    with pytest.raises(CharterPackConfigError):
        create_mission_core(project, "still-empty-mission", allow_worktree_context=True)


# ---------------------------------------------------------------------------
# WP01 (#3282) -- pointer-based (migrated) charter projects: the write
# authority is charter.yaml, not config.yaml (C-WP01).
# ---------------------------------------------------------------------------


def test_upgrade_heals_pointer_charter_activation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pointer-based project's activations land in charter.yaml, not config.yaml."""
    project = tmp_path / "pointer-project"
    project.mkdir()
    charter_path = _write_pointer_charter_project(project)
    _init_git_repo(project)

    assert existing_mission_types(project) == []

    result = _run_upgrade(
        ["--target", _STRANDED_FROM_VERSION, "--force", "--no-worktrees"],
        cwd=project,
    )
    assert result.exit_code == 0, result.output

    # The pointer-resolved charter.yaml is the write authority -- config.yaml
    # (the legacy shape) must NOT gain the key.
    config_data = _load_config(project / ".kittify" / "config.yaml")
    assert "mission_type_activations" not in config_data

    charter_data = _load_config(charter_path)
    activations = charter_data.get("mission_type_activations")
    assert activations, f"mission_type_activations still absent/empty in charter.yaml: {charter_data}"

    ctx = PackContext.from_config(project)
    assert ctx.activated_mission_types

    assert existing_mission_types(project) != []


def test_upgrade_preserves_authored_empty_pointer_activation_and_previews_not_pending(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An authored-empty pointer list is a no-op, AND never previewed as pending.

    Pins the T003 predicate-basis hazard the post-tasks squad flagged: keying
    the pending predicate on ``PackContext.from_config(...).activated_mission_types``
    non-emptiness would falsely report ``pending=True`` here (an authored
    ``[]`` yields an EMPTY ``frozenset``), even though a real upgrade
    correctly no-ops. The predicate must key on KEY-PRESENCE in the resolved
    write target instead (C-WP01).
    """
    project = tmp_path / "pointer-empty-project"
    project.mkdir()
    charter_body = _CHARTER_YAML_WITHOUT_KEY + "mission_type_activations: []\n"
    charter_path = _write_pointer_charter_project(project, charter_body=charter_body)
    _init_git_repo(project)

    assert _mission_type_activation_provisioning_pending(project) is False

    dry_run_result = _run_upgrade(
        ["--target", _STRANDED_FROM_VERSION, "--force", "--no-worktrees", "--dry-run"],
        cwd=project,
    )
    assert dry_run_result.exit_code == 0, dry_run_result.output
    assert "Would provision missing mission_type_activations" not in dry_run_result.output

    real_result = _run_upgrade(
        ["--target", _STRANDED_FROM_VERSION, "--force", "--no-worktrees"],
        cwd=project,
    )
    assert real_result.exit_code == 0, real_result.output

    charter_data = _load_config(charter_path)
    assert charter_data["mission_type_activations"] == []
    config_data = _load_config(project / ".kittify" / "config.yaml")
    assert "mission_type_activations" not in config_data
    # Preserved-empty is still a deliberate zero-types state -- create-gate
    # stays fail-closed exactly as the config.yaml-authored-empty parity test.
    assert existing_mission_types(project) == []


def test_pending_predicate_is_non_crashing_for_dangling_pointer(tmp_path: Path) -> None:
    """A dangling ``charter:`` pointer must not crash the dry-run preview (C-WP01).

    ``resolve_activation_write_target`` fail-loud raises ``CharterPackConfigError``
    for this exact shape (INV-5) -- the *real* write path is meant to propagate
    that. But the *preview* predicate must absorb it into a defined,
    non-crashing signal instead: not an unhandled raise, and not a silent
    ``False`` that would hide the broken pointer from the operator.
    """
    project = tmp_path / "dangling-pointer"
    project.mkdir()
    _write_stranded_project(project, config_body=_POINTER_CONFIG_BODY)
    # Intentionally do NOT create .kittify/charter/charter.yaml -- the
    # pointer dangles.

    assert _mission_type_activation_provisioning_pending(project) is True


# ---------------------------------------------------------------------------
# Unit-pin the new CLI helper in isolation (dry-run / fail-closed).
# ---------------------------------------------------------------------------


def test_provision_helper_is_noop_during_dry_run(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_stranded_project(project)

    errors = _provision_missing_mission_type_activations(project, dry_run=True)

    assert errors == []
    config_data = _load_config(project / ".kittify" / "config.yaml")
    assert "mission_type_activations" not in config_data


def test_provision_helper_surfaces_missing_default_pack_as_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A broken shipped default pack surfaces as a helper error, not a crash.

    WP01 (#3282) re-routed the helper through
    ``charter.activation.compiler.provision_mission_type_activations``, whose seed-read
    is ``charter.activation.default_pack.load_default_mission_type_activations`` (module-
    level import into ``charter.activation.compiler``'s namespace) -- the same fail-closed
    ``CharterPackConfigError`` seam :func:`_provision_missing_mission_type_activations`
    now catches (using ``.body``, since ``CharterPackConfigError.__str__`` is
    just its error code, not the message).
    """

    def _raise_missing(*args: object, **kwargs: object) -> list[str]:
        raise CharterPackConfigError("shipped default.yaml declares no mission_type_activations list")

    monkeypatch.setattr("charter.activation.compiler.load_default_mission_type_activations", _raise_missing)

    project = tmp_path / "project"
    project.mkdir()
    _write_stranded_project(project)

    errors = _provision_missing_mission_type_activations(project, dry_run=False)

    assert len(errors) == 1
    assert "default" in errors[0].lower()
