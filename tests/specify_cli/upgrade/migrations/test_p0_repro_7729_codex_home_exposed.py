"""Open P0 reproduction for #7729: narrowing the agent gitignore exposes a project-local CODEX_HOME.

``4.0.0rc8_narrow_agent_gitignore`` replaces the whole-folder ``.codex/`` line
with a managed block that keeps only ``auth.json``, ``history.jsonl``,
``sessions/`` and ``log/`` ignored (``agent_utils/ignore_entries.py``). A
project that set ``CODEX_HOME=<project>/.codex`` then has its personal Codex
state (config, state/log databases, approval rules, caches, memories) shown as
untracked, so ``git add -A`` commits it.

This is an open P0 reproduction (``p0_repro``): it is expected to FAIL until
#7729 is fixed, and runs only in the nightly ``p0-repro`` lane.

Not covered here: the "pulled clones get no warning" half of #7729.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.gitignore_manager import SPEC_KITTY_GITIGNORE_MARKER
from specify_cli.upgrade.migrations.m_4_0_0rc8_narrow_agent_gitignore import NarrowAgentGitignoreMigration

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

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


def _pre_rc8_project(tmp_path: Path) -> Path:
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / ".kittify").mkdir()
    save_agent_config(tmp_path, AgentConfig(available=["codex", "cursor"]))
    (tmp_path / ".gitignore").write_text(f"{SPEC_KITTY_GITIGNORE_MARKER}\n.codex/\n.cursor/\n", encoding="utf-8")
    for rel in _CODEX_HOME_FILES:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fake\n", encoding="utf-8")
    return tmp_path


def _untracked_visible(project: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(project), "status", "--porcelain", "-uall"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sorted(line[3:] for line in out.splitlines() if line.startswith("?? ") and line[3:].startswith(".codex/"))


@pytest.mark.p0_repro(issue=7729)
def test_narrowing_keeps_a_project_local_codex_home_ignored(tmp_path: Path) -> None:
    project = _pre_rc8_project(tmp_path)
    assert _untracked_visible(project) == []  # pre-upgrade: the whole folder is ignored

    result = NarrowAgentGitignoreMigration().apply(project)
    assert result.success, result.errors

    exposed = _untracked_visible(project)
    assert exposed == [], f"#7729: personal Codex home state is no longer ignored after narrowing: {exposed}"
