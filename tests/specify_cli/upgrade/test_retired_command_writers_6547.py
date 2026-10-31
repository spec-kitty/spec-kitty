"""The ledger cutover keeps the retired project-local command files retired (#6547).

Since 3.1.2 the ``spec-kitty.*`` slash-command files are installed once, in the
user's home agent directories. A project no longer carries its own copies:
``3.1.2_globalize_commands`` and ``3.2.0a4_safe_globalize_commands`` remove the
copies a pre-3.1.2 project had. Under ledger-diff selection (ADR
``docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`` §3) the pre-globalize
*writers* are re-selected on any ledger that does not settle them, and after
3.1.2 "missing" is the correct state — so their ``detect()`` reports work to do
and the upgrade writes the files back while the retiring migrations, already
recorded, are skipped.

Reproduction on ``main@35318ef51c`` (the red proof for this module): a project
whose ledger was cut over before the version-floor baseline (#6431) settles
everything it ever ran — both retiring migrations included — and never recorded
the two pre-globalize writers, because the version window never needed them. On
that shape the upgrade gains ``2.1.4_enforce_command_file_state`` in
``migrations_applied`` and 14 ``spec-kitty.*`` files beside the user's own. These tests assert the opposite and
were observed failing before ``2.1.4``/``3.0.2`` were declared superseded.

Every case drives the production entry point, ``MigrationRunner.upgrade``, which
is what ``spec-kitty upgrade`` calls; none calls a writer's ``apply()`` directly,
because the defect was in selection plus registration, not in ``apply()``.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

TARGET = "4.0.0rc8"
ENFORCE = "2.1.4_enforce_command_file_state"
RESTORE = "3.0.2_restore_prompt_commands"
RETIRE = ("3.1.2_globalize_commands", "3.2.0a4_safe_globalize_commands")
SUCCESSOR = "3.2.0a4_safe_globalize_commands"
WRITERS = (ENFORCE, RESTORE)

#: The user's own file, which no upgrade may touch.
USER_COMMAND = "my-command.md"
USER_COMMAND_BODY = "---\ndescription: my own command\n---\nDo the thing.\n"
#: A user file that *is* named like ours but carries no version marker: unproven, so held.
USER_NAMED_COMMAND = "spec-kitty.custom.md"
#: A generated project-local command file: it carries a version marker, so the retire path owns it.
GENERATED_LOCAL_COMMAND = "spec-kitty.accept.md"
GENERATED_MARKER = "<!-- spec-kitty-command-version: 3.0.0 -->"


@pytest.fixture(autouse=True)
def _real_registry() -> None:
    MigrationRegistry.clear()
    auto_discover_migrations()


def _project(tmp_path: Path) -> Path:
    """A git project at ``4.0.0rc7`` with a configured ``claude`` agent and one user command."""
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / ".kittify").mkdir()
    save_agent_config(tmp_path, AgentConfig(available=["claude"]))
    (tmp_path / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    # schema_version 3 is the post-canonical-context stamp: a project that went through 3.0.0
    # and 3.1.2, which is the state the issue reports.
    ProjectMetadata(version="4.0.0rc7", initialized_at=now_utc(), schema_version=3).save(tmp_path / ".kittify")
    commands = tmp_path / ".claude" / "commands"
    commands.mkdir(parents=True)
    (commands / USER_COMMAND).write_text(USER_COMMAND_BODY, encoding="utf-8")
    return tmp_path


def _project_metadata_with_retire_records(project: Path) -> None:
    """Write the pre-ledger shape the issue describes: only the retiring migrations recorded."""
    metadata = project / ".kittify" / "metadata.yaml"
    applied = "".join(f"  - id: {migration_id}\n    applied_at: '{now_utc().isoformat()}'\n    result: success\n" for migration_id in RETIRE)
    metadata.write_text(metadata.read_text(encoding="utf-8") + f"migrations:\n  applied:\n{applied}", encoding="utf-8")


def _post_cutover(tmp_path: Path) -> Path:
    """A ledger cut over *before* the #6431 floor, as a real project's looks.

    Everything it ever ran is settled -- including the two retirees and the adoption
    backfill -- and the two pre-globalize writers are the ones the version window
    never needed, so they were never recorded. That is exactly the shape the issue
    reports: the writers are re-selected, the retirees are skipped.
    """
    project = _project(tmp_path)
    ledger = MigrationLedger(project)
    for migration in MigrationRegistry.get_all():
        if migration.migration_id in WRITERS:
            continue
        ledger.append(build_record(migration, "success"))
    return project


def _pre_ledger(tmp_path: Path) -> Path:
    """No ledger yet; the adoption baseline (#6431) is what settles the writers."""
    project = _project(tmp_path)
    _project_metadata_with_retire_records(project)
    return project


def _ledger_era(tmp_path: Path) -> Path:
    """Every registered migration is settled, so nothing is selected at all."""
    project = _project(tmp_path)
    ledger = MigrationLedger(project)
    for migration in MigrationRegistry.get_all():
        ledger.append(build_record(migration, "success"))
    return project


def _command_files(project: Path) -> set[str]:
    return {path.name for path in (project / ".claude" / "commands").iterdir()}


def _writer_records(project: Path) -> dict[str, list[object]]:
    records: dict[str, list[object]] = {writer: [] for writer in WRITERS}
    for record in MigrationLedger(project).read_all():
        if record.id in records:
            records[record.id].append(record)
    return records


def test_post_cutover_upgrade_writes_no_project_command_files(tmp_path: Path) -> None:
    """Repeated upgrades on the post-cutover ledger keep exactly the user's own file."""
    project = _post_cutover(tmp_path)

    for _ in range(2):
        result = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
        assert result.success, result.errors
        assert ENFORCE not in result.migrations_applied
        assert RESTORE not in result.migrations_applied
        assert _command_files(project) == {USER_COMMAND}

    assert (project / ".claude" / "commands" / USER_COMMAND).read_text(encoding="utf-8") == USER_COMMAND_BODY


def test_the_writers_are_recorded_as_superseded_no_ops(tmp_path: Path) -> None:
    """Neither writer is ever recorded ``success``; each record names the successor."""
    project = _post_cutover(tmp_path)
    result = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
    assert result.success, result.errors

    records = _writer_records(project)
    for writer in WRITERS:
        assert records[writer], f"{writer} has no ledger record"
        assert all(record.result != "success" for record in records[writer]), records[writer]
        assert all(record.superseded_by == f"Superseded by {SUCCESSOR}" for record in records[writer]), records[writer]


@pytest.mark.parametrize(
    "make_project",
    [_pre_ledger, _post_cutover, _ledger_era],
    ids=["pre-ledger-floor-settles", "post-cutover-without-floor", "ledger-era-all-settled"],
)
def test_every_ledger_shape_reaches_the_same_end_state(tmp_path: Path, make_project: Callable[[Path], Path]) -> None:
    """Whatever the ledger shape, the upgrade neither adds nor removes the user's file."""
    project = make_project(tmp_path)
    before = _command_files(project)

    result = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
    assert result.success, result.errors
    assert ENFORCE not in result.migrations_applied
    assert RESTORE not in result.migrations_applied
    assert _command_files(project) == before == {USER_COMMAND}


@pytest.fixture
def retire_path_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the retire path's classifiable branch reachable without reading the machine's ``~``.

    The writer declarations must not silence the retiring migrations: when a project
    still carries a *generated* local file and a global equivalent exists, it is
    removed. Both probes are stubbed so the test does not depend on ``$HOME`` state.
    """
    # Patch the classes the registry actually registered: ``auto_discover_migrations``
    # reloads a module after ``MigrationRegistry.clear()``, so a module-level import
    # of the base class can be a stale class object.
    for retire in RETIRE:
        registered = type(MigrationRegistry.get_by_id(retire))
        monkeypatch.setattr(registered, "_global_runtime_present", staticmethod(lambda: True))
        monkeypatch.setattr(registered, "_global_command_file_present", staticmethod(lambda *_: True))


def test_legacy_local_command_files_are_still_retired(tmp_path: Path, retire_path_is_available: None) -> None:
    """A pre-3.1.2 project's generated local files are still removed; user files are kept."""
    project = _post_cutover(tmp_path)
    commands = project / ".claude" / "commands"
    (commands / GENERATED_LOCAL_COMMAND).write_text(f"{GENERATED_MARKER}\n# generated\n", encoding="utf-8")
    (commands / USER_NAMED_COMMAND).write_text("---\ndescription: mine\n---\nMine.\n", encoding="utf-8")
    # The retirees are not recorded, so ledger-diff selects them again.
    _drop_retire_records(project)

    result = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
    assert result.success, result.errors
    assert set(RETIRE) & set(result.migrations_applied), result.migrations_applied

    assert _command_files(project) == {USER_COMMAND, USER_NAMED_COMMAND}
    assert (commands / USER_NAMED_COMMAND).read_text(encoding="utf-8") == "---\ndescription: mine\n---\nMine.\n"


def _drop_retire_records(project: Path) -> None:
    """Drop both retirees' records so ledger-diff re-selects and re-evaluates them."""
    tracked = MigrationLedger(project).tracked_path
    lines = [line for line in tracked.read_text(encoding="utf-8").splitlines() if line.strip()]
    kept = [line for line in lines if json.loads(line)["id"] not in RETIRE]
    tracked.write_text("\n".join(kept) + "\n", encoding="utf-8")


def test_dry_run_previews_no_project_command_write(tmp_path: Path) -> None:
    """``upgrade --dry-run`` must not list a writer, and must write nothing."""
    project = _post_cutover(tmp_path)
    result = MigrationRunner(project).upgrade(TARGET, dry_run=True, include_worktrees=False)

    assert result.success, result.errors
    assert ENFORCE not in result.migrations_applied
    assert RESTORE not in result.migrations_applied
    assert _command_files(project) == {USER_COMMAND}
