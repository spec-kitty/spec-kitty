"""ATDD: the python-only migration preserves unprovable user scripts.

WP05 (mission ownership-boundary-preservation, #3347). Scripts carry no version
marker and the package no longer ships a canonical to byte-match, so
``CanonicalContentProver.prove()`` returns ``None`` for every ``.sh``/``.ps1``
and for the obsolete ``scripts/tasks/`` directory ⇒ **preserve-all** (charter
L472: unprovable ⇒ preserve + warn). "owned-delete" is N/A here — there is no
ownership signal for scripts.

These tests pin BOTH directions of the WP contract (contracts/
ownership-guard-contract.md C4 US4 script clause; data-model census rows 2-3 +
B2; research Decision 6):

* the four routed sites (``:175`` bash sweep, ``:187`` powershell sweep, ``:250``
  ``scripts/tasks/`` rmtree, ``:229`` worktree bash sweep) leave user bytes on
  disk and name them in a warning; and
* the migration's non-script step (command-template rewrite) still runs, so the
  "removed N" → "preserved M" expectation rewrite cannot silently neuter the
  migration into a no-op.

RED on base ``32cfc272ee`` (the base migration deletes the scripts by glob);
GREEN on this WP's final commit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_0_10_0_python_only import PythonOnlyMigration

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_BASH_BYTES = b"#!/bin/bash\necho 'user-authored bash WP05 marker 7f3a'\n"
_PS_BYTES = b"# user-authored powershell WP05 marker 7f3a\nWrite-Host 'hi'\n"
_TASKS_BYTES = b"#!/bin/bash\necho 'user task helper WP05 marker 7f3a'\n"
_WORKTREE_BYTES = b"#!/bin/bash\necho 'user worktree script WP05 marker 7f3a'\n"


@pytest.fixture
def migration() -> PythonOnlyMigration:
    return PythonOnlyMigration()


def _seed_command_template(project_path: Path) -> Path:
    """Seed a slash-command template that references a retired bash script.

    Used by the positive non-neuter assertion: the migration must still rewrite
    this template even though the script sweeps now preserve instead of delete.
    """
    templates_dir = project_path / ".kittify" / "templates" / "command-templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    template = templates_dir / "specify.md"
    template.write_text(
        "Run .kittify/scripts/bash/create-new-feature.sh to create a feature.\n",
        encoding="utf-8",
    )
    return template


@pytest.fixture
def project_with_user_scripts(tmp_path: Path) -> Path:
    """A project whose scripts are entirely user-authored (no ownership signal)."""
    bash_dir = tmp_path / ".kittify" / "scripts" / "bash"
    bash_dir.mkdir(parents=True)
    (bash_dir / "custom.sh").write_bytes(_BASH_BYTES)

    ps_dir = tmp_path / ".kittify" / "scripts" / "powershell"
    ps_dir.mkdir(parents=True)
    (ps_dir / "custom.ps1").write_bytes(_PS_BYTES)

    tasks_dir = tmp_path / ".kittify" / "scripts" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "helper.sh").write_bytes(_TASKS_BYTES)

    worktree_bash = tmp_path / ".worktrees" / "001-lane-a" / ".kittify" / "scripts" / "bash"
    worktree_bash.mkdir(parents=True)
    (worktree_bash / "wt.sh").write_bytes(_WORKTREE_BYTES)

    _seed_command_template(tmp_path)
    return tmp_path


def test_user_bash_and_powershell_scripts_survive_and_are_named(migration: PythonOnlyMigration, project_with_user_scripts: Path) -> None:
    """`:175` + `:187` — user `.sh`/`.ps1` survive byte-for-byte and are named."""
    project = project_with_user_scripts

    result = migration.apply(project, dry_run=False)

    assert result.success is True
    bash_script = project / ".kittify" / "scripts" / "bash" / "custom.sh"
    ps_script = project / ".kittify" / "scripts" / "powershell" / "custom.ps1"
    assert bash_script.read_bytes() == _BASH_BYTES
    assert ps_script.read_bytes() == _PS_BYTES

    assert any("custom.sh" in warning for warning in result.warnings)
    assert any("custom.ps1" in warning for warning in result.warnings)


def test_result_reports_preserved_not_removed(migration: PythonOnlyMigration, project_with_user_scripts: Path) -> None:
    """The expectations read "preserved M unprovable script(s)", not "removed N"."""
    result = migration.apply(project_with_user_scripts, dry_run=False)

    joined = "\n".join(result.changes_made + result.warnings)
    assert "unprovable script" in joined.lower()
    # The base migration reported "Total scripts removed: N" and "Removed:
    # <script>"; preserve-all must never claim to have removed a user script.
    assert "Total scripts removed" not in joined
    assert not any(change.startswith("Removed: .kittify/scripts/bash/") for change in result.changes_made)
    assert not any(change.startswith("Removed: .kittify/scripts/powershell/") for change in result.changes_made)


def test_obsolete_tasks_directory_member_survives(migration: PythonOnlyMigration, project_with_user_scripts: Path) -> None:
    """B2 `:250` — the `scripts/tasks/` rmtree becomes preserve-all."""
    project = project_with_user_scripts

    result = migration.apply(project, dry_run=False)

    assert result.success is True
    tasks_member = project / ".kittify" / "scripts" / "tasks" / "helper.sh"
    assert tasks_member.read_bytes() == _TASKS_BYTES


def test_worktree_user_script_survives_and_is_named(migration: PythonOnlyMigration, project_with_user_scripts: Path) -> None:
    """`:229` — the worktree bash sweep is REQUIRED-route preserve-all, not teardown."""
    project = project_with_user_scripts

    result = migration.apply(project, dry_run=False)

    assert result.success is True
    wt_script = project / ".worktrees" / "001-lane-a" / ".kittify" / "scripts" / "bash" / "wt.sh"
    assert wt_script.read_bytes() == _WORKTREE_BYTES
    assert any("wt.sh" in warning for warning in result.warnings)


def test_non_script_step_still_runs(migration: PythonOnlyMigration, project_with_user_scripts: Path) -> None:
    """Positive non-neuter: the command-template rewrite still fires.

    Guards the "removed N" → "preserved M" expectation rewrite against silently
    turning the migration into a no-op.
    """
    project = project_with_user_scripts
    template = project / ".kittify" / "templates" / "command-templates" / "specify.md"

    result = migration.apply(project, dry_run=False)

    assert result.success is True
    content = template.read_text(encoding="utf-8")
    assert "spec-kitty agent mission create-feature" in content
    assert ".kittify/scripts/bash/create-new-feature.sh" not in content
    assert any("specify.md" in change for change in result.changes_made)
