"""FR-009 (#3336, WP10): the ``upgrade --dry-run`` preview must be honest.

``spec-kitty upgrade --dry-run`` (and ``--dry-run --json``) has to report the
*same* pending work a real run would apply. Two historical divergences made the
preview under-report:

1. **Pending migrations.** The ``--json`` preview routed through the
   compat-planner's ``_pending_migrations_for`` (gated on
   ``BLOCK_PROJECT_MIGRATION`` — ``()`` for any project that is
   schema-compatible but version-stale), while the real run selects via
   ``MigrationRegistry.get_applicable``. A stale-but-schema-OK project could
   therefore preview ``[]`` while the real run applied migrations.

2. **Provisioning.** ``_provision_missing_mission_type_activations`` never runs
   under ``--dry-run`` (it returns early), so the preview never signalled the
   pending ``mission_type_activations`` seed the real run performs.

These tests pin parity for both divergences: the ``--json`` preview's
``pending_migrations`` is driven through the exact selector the real run uses
(``MigrationRegistry.get_applicable``), and the provisioning seed is surfaced on
the human ``--dry-run`` preview (the frozen ``compat-planner.json`` machine
contract, ``additionalProperties: false``, owns no provisioning field).
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli import __version__
from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# A version far enough behind the CLI that ``get_applicable`` selects a
# non-empty window of real migrations, yet with a *current* schema_version so
# the planner's block decision stays ALLOW (schema-compatible) — the exact
# shape that exposed divergence #1.
_STALE_VERSION = "0.0.1"

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)
_runner = CliRunner()


def _write_project(
    project: Path,
    *,
    version: str,
    config_body: str,
    schema_version: int = MAX_SUPPORTED_SCHEMA,
) -> None:
    """Materialize a minimal Spec Kitty project on disk.

    Writes ``.kittify/metadata.yaml`` (version + schema_version) and
    ``.kittify/config.yaml`` (``config_body``). No git required: the
    ``--dry-run``/``--json`` preview short-circuits before any commit path.
    """
    kittify = project / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "metadata.yaml").write_text(
        f"spec_kitty:\n  version: \"{version}\"\n  schema_version: {schema_version}\n  initialized_at: '2026-01-01T00:00:00+00:00'\n",
        encoding="utf-8",
    )
    (kittify / "config.yaml").write_text(config_body, encoding="utf-8")


def _invoke_upgrade(project: Path, args: list[str], monkeypatch: pytest.MonkeyPatch) -> object:
    """Invoke ``upgrade`` with *args* inside *project* (CI=1 → no network)."""
    monkeypatch.setenv("CI", "1")
    with contextlib.chdir(project):
        return _runner.invoke(_test_app, args, catch_exceptions=False)


def _run_dry_run_json(project: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Invoke ``upgrade --dry-run --json --no-nag`` in *project* and parse JSON."""
    result = _invoke_upgrade(project, ["--dry-run", "--json", "--no-nag"], monkeypatch)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _run_dry_run_human(project: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Invoke the human ``upgrade --dry-run --no-nag`` preview; return its output.

    The provisioning divergence is surfaced on the human preview (the frozen
    ``compat-planner.json`` machine contract owns no provisioning field). The
    generated-surface repair is stubbed out so the assertion stays scoped to
    the provisioning notice.
    """
    monkeypatch.setattr(
        "specify_cli.cli.commands.upgrade._run_upgrade_surface_repair",
        lambda *a, **k: None,
    )
    result = _invoke_upgrade(project, ["--dry-run", "--no-nag", "--no-worktrees"], monkeypatch)
    assert result.exit_code == 0, result.output
    return result.output


def _real_applied_ids(project: Path, target_version: str, from_version: str) -> list[str]:
    """The migration ids a real ``upgrade`` run would apply (upgrade.py:751)."""
    auto_discover_migrations()
    version_for_migration = "0.0.0" if from_version == "unknown" else from_version
    applicable = MigrationRegistry.get_applicable(version_for_migration, target_version, project_path=project)
    return sorted(m.migration_id for m in applicable)


# ---------------------------------------------------------------------------
# Divergence #1 — pending-migration parity
# ---------------------------------------------------------------------------


def test_dry_run_json_pending_set_equals_real_applied_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Preview ``pending_migrations`` == the real run's ``get_applicable`` set.

    The project is schema-compatible (block decision ALLOW) but version-stale,
    so the pre-fix planner path reported ``[]`` while a real run applied the
    windowed migrations. This is the FR-009 SC-004 parity guarantee.
    """
    project = tmp_path / "stale"
    _write_project(
        project,
        version=_STALE_VERSION,
        config_body="vcs:\n  type: git\nmission_type_activations:\n  - software-development\n",
    )

    real_ids = _real_applied_ids(project, __version__, _STALE_VERSION)
    # Sanity: the scenario must actually have pending work, else the parity
    # assertion below would pass vacuously.
    assert real_ids, "fixture must have >=1 pending migration for a meaningful parity check"

    payload = _run_dry_run_json(project, monkeypatch)
    preview_ids = sorted(step["migration_id"] for step in payload["pending_migrations"])

    assert preview_ids == real_ids


# ---------------------------------------------------------------------------
# Divergence #2 — provisioning parity
# ---------------------------------------------------------------------------


_PROVISION_NOTICE = "Would provision missing mission_type_activations"


def test_dry_run_reflects_pending_provisioning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A project missing ``mission_type_activations`` previews the pending seed.

    The real run seeds the key (``_provision_missing_mission_type_activations``);
    the pre-fix dry-run skipped it silently. The preview must surface it so the
    reported pending work matches what a real run performs.
    """
    project = tmp_path / "unprovisioned"
    _write_project(
        project,
        version=__version__,  # current version → isolate provisioning from migrations
        config_body="vcs:\n  type: git\n",  # no mission_type_activations key
    )

    output = _run_dry_run_human(project, monkeypatch)

    assert _PROVISION_NOTICE in output


def test_dry_run_no_provisioning_when_key_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An already-provisioned project previews no pending provisioning."""
    project = tmp_path / "provisioned"
    _write_project(
        project,
        version=__version__,
        config_body="vcs:\n  type: git\nmission_type_activations:\n  - software-development\n",
    )

    output = _run_dry_run_human(project, monkeypatch)

    assert _PROVISION_NOTICE not in output


def test_dry_run_no_provisioning_for_authored_empty_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An authored empty list is a deliberate state — never a pending seed."""
    project = tmp_path / "empty-authored"
    _write_project(
        project,
        version=__version__,
        config_body="vcs:\n  type: git\nmission_type_activations: []\n",
    )

    output = _run_dry_run_human(project, monkeypatch)

    assert _PROVISION_NOTICE not in output
