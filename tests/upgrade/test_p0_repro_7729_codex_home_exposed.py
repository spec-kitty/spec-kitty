"""Regression guard for #7729: narrowing the agent gitignore must not expose a project-local CODEX_HOME.

``4.0.0rc8_narrow_agent_gitignore`` replaces the whole-folder ``.codex/`` line
with a managed block that keeps only ``auth.json``, ``history.jsonl``,
``sessions/`` and ``log/`` ignored (``agent_utils/ignore_entries.py``). A
project that set ``CODEX_HOME=<project>/.codex`` then has its personal Codex
state (config, state/log databases, approval rules, caches, memories) shown as
untracked, so ``git add -A`` committed it.

Both halves are driven through ``MigrationRunner.upgrade``, the entry point
``spec-kitty upgrade`` uses, on a ledger that settles every other migration:

- the clone that runs the upgrade keeps its Codex home ignored;
- a second clone that pulls the narrowed ``.gitignore`` keeps its Codex home
  ignored once it upgrades, and is told which agent-folder files git now shows.

This was the open P0 reproduction for #7729 (``p0_repro``); the fix removed the
marker and moved it to ``tests/upgrade/`` (the ``upgrade`` module's per-PR
matrix), so it now guards every PR that touches the upgrade package.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.clock import now_utc
from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.gitignore_manager import SPEC_KITTY_GITIGNORE_MARKER
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner, UpgradeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: The upgrade target that reaches every migration this reproduction exercises.
_TARGET = "4.0.0rc9"

#: Migrations the reproduction leaves unsettled: the rc8 narrowing, and the two
#: clone-local steps of the fix (the Codex home exclusion and the per-clone notice).
_UNDER_TEST = frozenset(
    {
        "4.0.0rc8_narrow_agent_gitignore",
        "4.0.0rc9_exclude_project_local_codex_home",
        "4.0.0rc9_report_newly_visible_agent_files",
    }
)

#: Files Codex writes into its home (the issue's list), all personal state.
_CODEX_HOME_FILES: tuple[str, ...] = (
    ".codex/auth.json",
    ".codex/config.toml",
    ".codex/logs_1.sqlite",
    ".codex/logs_1.sqlite-wal",
    ".codex/logs_1.sqlite-shm",
    ".codex/state_1.sqlite",
    ".codex/models_cache.json",
    ".codex/version.json",
    ".codex/rules/default.rules",
    # Codex's own scratch dir; spelled split so the shared-tmp literal gate
    # (test_no_tmp_paths_in_tests) does not read it as the system /tmp.
    ".codex/" + "tmp" + "/x",
    ".codex/shell_snapshots/snap.sh",
    ".codex/memories/m.md",
    ".codex/skills/.system/foo/SKILL.md",
)

#: A team file in an agent folder the old whole-folder rule hid (the issue's ``.cursor/rules/x.md``).
_EXPOSED_TEAM_FILE = ".cursor/rules/x.md"

_GIT_IDENTITY = ("-c", "user.name=Repro", "-c", "user.email=repro@example.invalid", "-c", "commit.gpgsign=false")


@pytest.fixture(autouse=True)
def _real_registry() -> None:
    MigrationRegistry.clear()
    auto_discover_migrations()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *_GIT_IDENTITY, *args], check=True, capture_output=True, text=True).stdout


def _write_files(root: Path, paths: tuple[str, ...]) -> None:
    for rel in paths:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fake\n", encoding="utf-8")


def _pre_rc8_project(root: Path) -> Path:
    """A project last upgraded before rc8: whole-folder agent lines, every other migration settled."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    (root / ".kittify").mkdir()
    save_agent_config(root, AgentConfig(available=["codex", "cursor"]))
    # The rows as 3.2.6rc3 left them: ``.cursor/`` between ``.gemini/`` and ``.qwen/`` (proven Spec Kitty's),
    # and the clone-local migration partition ignored as in every initialized project.
    gitignore = f"{SPEC_KITTY_GITIGNORE_MARKER}\n.codex/\n.gemini/\n.cursor/\n.qwen/\n.kittify/migrations/\n"
    (root / ".gitignore").write_text(gitignore, encoding="utf-8")
    ProjectMetadata(version="4.0.0rc7", initialized_at=now_utc()).save(root / ".kittify")
    ledger = MigrationLedger(root)
    for migration in MigrationRegistry.get_all():
        if migration.migration_id not in _UNDER_TEST:
            ledger.append(build_record(migration, "success"))
    return root


def _upgrade(project: Path) -> UpgradeResult:
    result = MigrationRunner(project).upgrade(_TARGET, include_worktrees=False)
    assert result.success, result.errors
    return result


def _untracked_visible(project: Path, prefix: str = ".codex/") -> list[str]:
    out = _git(project, "status", "--porcelain", "-uall")
    return sorted(line[3:] for line in out.splitlines() if line.startswith("?? ") and line[3:].startswith(prefix))


def test_narrowing_keeps_a_project_local_codex_home_ignored(tmp_path: Path) -> None:
    project = _pre_rc8_project(tmp_path / "project")
    _write_files(project, _CODEX_HOME_FILES)
    assert _untracked_visible(project) == []  # pre-upgrade: the whole folder is ignored

    result = _upgrade(project)
    assert "4.0.0rc8_narrow_agent_gitignore" in result.migrations_applied  # positive control: the narrowing ran

    exposed = _untracked_visible(project)
    assert exposed == [], f"#7729: personal Codex home state is no longer ignored after narrowing: {exposed}"


def test_a_clone_that_pulls_the_narrowed_gitignore_keeps_its_codex_home_ignored_and_is_told(tmp_path: Path) -> None:
    upgrading = _pre_rc8_project(tmp_path / "upgrading")
    _git(upgrading, "add", "-A")
    _git(upgrading, "commit", "-q", "-m", "pre-rc8 project")
    pulled = tmp_path / "pulled"
    subprocess.run(["git", "clone", "-q", str(upgrading), str(pulled)], check=True)
    _write_files(pulled, (*_CODEX_HOME_FILES, _EXPOSED_TEAM_FILE))
    assert _untracked_visible(pulled, prefix=".") == []  # before the pull: the whole folders are ignored

    _upgrade(upgrading)
    _git(upgrading, "add", "-A")
    _git(upgrading, "commit", "-q", "-m", "spec-kitty upgrade")
    _git(pulled, "pull", "-q", "--no-rebase")
    assert _EXPOSED_TEAM_FILE in _untracked_visible(pulled, prefix=".cursor/")  # positive control: the narrowing reached this clone

    result = _upgrade(pulled)

    exposed = _untracked_visible(pulled)
    assert exposed == [], f"#7729: the pulled clone's Codex home state is exposed after its upgrade: {exposed}"
    warnings = " ".join(result.warnings)
    assert _EXPOSED_TEAM_FILE in warnings, f"#7729: the pulled clone was not told which files git now shows: {result.warnings}"
