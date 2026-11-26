"""The agent-folder notice never lists Spec Kitty's own session-presence files (#7878).

``4.0.0rc9_report_newly_visible_agent_files`` settled only when it found a file
to list. Its ``detect()`` runs before upgrade's finalizer writes the
session-presence files (``.claude/CLAUDE.md``, ``.claude/settings.json``), so
with auto-commit off the first upgrade recorded ``skipped`` and the second one
found those files untracked, listed them, and appended a ``success`` row to
``.kittify/migrations/clone-local.jsonl``: a second upgrade changed bytes
(NFR-004). It is superseded by ``4.0.0rc9_report_exposed_agent_files``, which
leaves the files the session-presence writers own out of the list.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.gitignore_manager import GitignoreManager
from specify_cli.session_presence.content import SessionPresenceContent
from specify_cli.session_presence.writers.claude_code import ClaudeCodeWriter
from specify_cli.session_presence.writers.null_writer import NullWriter
from specify_cli.session_presence.writers.registry import WRITER_REGISTRY, presence_file_paths
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations import m_4_0_0rc9_report_exposed_agent_files as successor
from specify_cli.upgrade.migrations.base import BaseMigration
from specify_cli.upgrade.migrations.m_4_0_0rc9_report_exposed_agent_files import ReportExposedAgentFilesMigration
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.supersession import SUPERSEDED_MIGRATIONS

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

SHIPPED_ID = "4.0.0rc9_report_newly_visible_agent_files"
SUCCESSOR_ID = "4.0.0rc9_report_exposed_agent_files"
_PRESENCE_FILES = (".claude/CLAUDE.md", ".claude/settings.json")


@pytest.fixture(autouse=True)
def _no_codex_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_HOME", raising=False)


def _registered(migration_id: str) -> BaseMigration:
    auto_discover_migrations()
    found = [m for m in MigrationRegistry.get_all() if m.migration_id == migration_id]
    assert found, f"{migration_id} is not registered"
    migration = found[0]
    assert isinstance(migration, BaseMigration)
    return migration


def _write(project: Path, *paths: str) -> None:
    for rel in paths:
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")


def _narrowed(project: Path, *untracked: str) -> Path:
    """A project with the committed agent-files block for claude and cursor, plus *untracked* files."""
    (project / ".kittify").mkdir(parents=True, exist_ok=True)
    save_agent_config(project, AgentConfig(available=["claude", "cursor"]))
    assert GitignoreManager(project).protect_all_agents().success
    _write(project, *untracked)
    return project


def _project(tmp_path: Path, *untracked: str) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return _narrowed(tmp_path, *untracked)


def test_registered_notice_steps_ignore_session_presence_files(tmp_path: Path) -> None:
    """Red at #7878: the registered shipped step reports the files the finalizer wrote."""
    project = _project(tmp_path, *_PRESENCE_FILES)
    assert not _registered(SHIPPED_ID).detect(project)
    assert not _registered(SUCCESSOR_ID).detect(project)


def test_the_shipped_step_is_superseded_by_the_successor() -> None:
    assert SUPERSEDED_MIGRATIONS[SHIPPED_ID] == SUCCESSOR_ID
    migration = _registered(SUCCESSOR_ID)
    assert isinstance(migration, ReportExposedAgentFilesMigration)
    assert migration.clone_local_effect is True


def test_presence_file_paths_name_the_claude_code_files() -> None:
    assert set(_PRESENCE_FILES) <= set(presence_file_paths())


def test_an_operator_file_is_listed_and_presence_files_are_not(tmp_path: Path) -> None:
    project = _project(tmp_path, *_PRESENCE_FILES, ".claude/notes.md", ".cursor/mine.txt")
    migration = ReportExposedAgentFilesMigration()
    assert successor.exposed_agent_files(project) == [".claude/notes.md", ".cursor/mine.txt"]
    assert migration.detect(project)
    assert migration.can_apply(project) == (True, "")

    result = migration.apply(project)
    assert result.success and result.manual_review_required
    assert result.changes_made == ["Listed the untracked files git shows in agent folders"]
    (warning,) = result.warnings
    assert ".claude/notes.md" in warning and ".cursor/mine.txt" in warning
    assert not any(path in warning for path in _PRESENCE_FILES)


def test_dry_run_only_says_it_would_list(tmp_path: Path) -> None:
    project = _project(tmp_path, ".claude/notes.md")
    result = ReportExposedAgentFilesMigration().apply(project, dry_run=True)
    assert result.changes_made == ["Would list the untracked files git shows in agent folders"]


def test_nothing_to_list_is_a_no_op(tmp_path: Path) -> None:
    project = _project(tmp_path, *_PRESENCE_FILES)
    result = ReportExposedAgentFilesMigration().apply(project)
    assert result.success and result.warnings == []
    assert result.changes_made == ["No untracked files in agent folders"]


def test_a_nested_project_leaves_its_own_presence_files_out(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    project = _narrowed(tmp_path / "svc", *_PRESENCE_FILES, ".claude/notes.md")
    assert successor.exposed_agent_files(project) == ["svc/.claude/notes.md"]


def test_outside_a_repository_nothing_is_detected(tmp_path: Path) -> None:
    project = _narrowed(tmp_path / "plain", ".claude/notes.md")
    migration = ReportExposedAgentFilesMigration()
    assert not migration.detect(project)
    assert migration.can_apply(project) == (False, "Not a git repository")
    assert migration.apply(project).changes_made == ["Skipped: not a git repository"]
    assert successor._presence_paths_from_root(project) == frozenset(presence_file_paths())


def test_presence_file_paths_is_the_union_of_every_writers_owned_paths() -> None:
    """The writers own their file lists; the registry view only unions them (#7878 review, LOW 1)."""
    assert ClaudeCodeWriter().owned_paths() == _PRESENCE_FILES
    assert NullWriter("q").owned_paths() == ()
    assert WRITER_REGISTRY["cursor"].owned_paths() == (".cursor/rules/spec-kitty.mdc",)
    union = {path for writer in WRITER_REGISTRY.values() for path in writer.owned_paths()}
    assert presence_file_paths() == tuple(sorted(union))


@pytest.mark.parametrize("harness", sorted(WRITER_REGISTRY))
def test_every_file_a_writer_writes_is_in_presence_file_paths(harness: str, tmp_path: Path) -> None:
    """Each writer, run for real, writes only files ``presence_file_paths()`` names (#7878 review, LOW 1)."""
    for folder in (".claude", ".cursor", ".windsurf", ".github", ".kiro"):
        (tmp_path / folder).mkdir()
    before = {p for p in tmp_path.rglob("*") if p.is_file()}
    WRITER_REGISTRY[harness].write(tmp_path, SessionPresenceContent("4.0.0", "demo", "healthy", None))
    written = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file() and p not in before}
    assert written <= set(presence_file_paths()), f"{harness} wrote files presence_file_paths() leaves out: {sorted(written - set(presence_file_paths()))}"
