"""``spec-kitty consolidate`` stays under a git process ceiling (#7689).

The nightly acceptance scenario "Consolidating lands the approved work and leaves my untracked
files alone" (``tests/scenarios/consolidate/consolidate.feature``) timed out on a Windows runner:
there a ``git`` process start costs far more than on Linux, and one ``consolidate`` run started
671 of them, many repeating the same read. The run now reads repeated queries through a run-scoped
git read cache (:mod:`kernel.git.read_cache`) and starts 470 for the same scenario. The #7747
landing proofs pushed it to 582 (#7848); batching their tree reads and reusing object-id reads
brought it back to 486.

This test builds that scenario with the real CLI (this checkout's ``src``), runs ``consolidate``
in a shim that counts every ``git`` process the CLI starts, and requires the count to stay under
:data:`SPAWN_CEILING`. Losing the cache (671) or adding a new repeated read goes red here, on any
OS, instead of as a Windows-only nightly timeout. Raise the ceiling only for a deliberate new read,
with the measured count in the commit message.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_SRC = str(Path(__file__).resolve().parents[2] / "src")
_CLI_TIMEOUT_SECONDS = 300
_TOPIC = "work"

#: Measured: 671 git processes before #7689, 470 after; 582 after the #7747 landing proofs, 486
#: once those proofs batch their reads and object-id reads are reused (#7848). About 3% headroom.
SPAWN_CEILING = 500

#: Runs the CLI with every git process start counted; the count lands in ``SPAWN_COUNT_FILE``.
_COUNTING_SHIM = """
import atexit, os, subprocess, sys
from pathlib import Path

_count = 0
_real_init = subprocess.Popen.__init__

def _counting_init(self, args, *rest, **kwargs):
    global _count
    argv = args if isinstance(args, (list, tuple)) else [args]
    if argv and Path(str(argv[0])).name.lower().startswith("git"):
        _count += 1
    return _real_init(self, args, *rest, **kwargs)

subprocess.Popen.__init__ = _counting_init
atexit.register(lambda: Path(os.environ["SPAWN_COUNT_FILE"]).write_text(str(_count)))
sys.argv = ["spec-kitty", *sys.argv[1:]]
from specify_cli import main
main()
"""

_SPEC = (
    "# demo\n\n## Functional Requirements\n\n"
    "| ID | Requirement | Acceptance Criteria | Status |\n| --- | --- | --- | --- |\n"
    "| FR-001 | Each work package adds a greeting module. | The module exists and is committed. | proposed |\n"
)
_TASKS = "# Work Packages\n\n## Work Package WP01: wp01\n\n### Included Subtasks\n- [ ] T01 Create the wp01 module\n"
_WP01 = """---
work_package_id: "WP01"
title: "wp01"
dependencies: []
requirement_refs: [FR-001]
subtasks:
  - "T01"
owned_files:
  - "src/wp01/**"
authoritative_surface: "src/wp01/"
---

# Work Package Prompt: WP01 -- wp01

- [ ] T01 Create the wp01 module
"""


def _env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"))}
    env.update(
        PYTHONPATH=os.pathsep.join(p for p in (_SRC, os.environ.get("PYTHONPATH")) if p),
        NO_COLOR="1",
        COLUMNS="100",
        HOME=str(home),
        USERPROFILE=str(home),
        SPEC_KITTY_HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_STATE_HOME=str(home / ".local" / "state"),
        XDG_CACHE_HOME=str(home / ".cache"),
        XDG_DATA_HOME=str(home / ".local" / "share"),
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@e",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@e",
        GIT_CONFIG_NOSYSTEM="1",
    )
    return env


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def _cli(root: Path, env: dict[str, str], shim: Path, *args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(shim), *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=_CLI_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, f"spec-kitty {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout + result.stderr


def _commit_all(root: Path, env: dict[str, str], message: str) -> None:
    _git(root, env, "add", "-A")
    _git(root, env, "commit", "-qm", message)


def test_consolidate_of_one_approved_work_package_stays_under_the_git_spawn_ceiling(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    env = _env(home)
    shim = tmp_path / "counting_cli.py"
    shim.write_text(_COUNTING_SHIM, encoding="utf-8")
    env["SPAWN_COUNT_FILE"] = str(tmp_path / "spawns.txt")

    def cli(*args: str) -> str:
        return _cli(root, env, shim, *args)

    _git(root, env, "init", "-q", "-b", "main")
    _git(root, env, "commit", "-q", "--allow-empty", "-m", "init")
    cli("init", "--non-interactive", "--ai", "claude")
    if _git(root, env, "status", "--porcelain"):
        _commit_all(root, env, "set up spec-kitty")
    _git(root, env, "checkout", "-q", "-b", _TOPIC)

    created = cli("agent", "mission", "create", "demo", "--json", "--topology", "lanes_with_coord")
    match = re.search(r'"mission_slug"\s*:\s*"([^"]+)"', created)
    assert match, created
    slug = match.group(1)
    folder = root / "kitty-specs" / slug
    (folder / "spec.md").write_text(_SPEC, encoding="utf-8")
    _commit_all(root, env, "spec")
    cli("agent", "mission", "setup-plan", "--mission", slug, "--json")
    (folder / "plan.md").write_text("# Implementation Plan\n\n## Technical Context\n\n", encoding="utf-8")
    (folder / "tasks.md").write_text(_TASKS, encoding="utf-8")
    (folder / "tasks").mkdir(exist_ok=True)
    (folder / "tasks" / "WP01-wp01.md").write_text(_WP01, encoding="utf-8")
    _commit_all(root, env, "plan and tasks")
    cli("agent", "mission", "finalize-tasks", "--mission", slug, "--json")
    analysis = tmp_path / "analysis.md"
    analysis.write_text("# Analysis Report\n\nNo issues found. Every requirement maps to a work package.\n", encoding="utf-8")
    cli("agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(analysis), "--agent", "claude")

    implemented = cli("agent", "action", "implement", "WP01", "--mission", slug, "--agent", "claude")
    lane = re.search(r"\(Lane [^:]+: ([^)]+)\)", implemented)
    assert lane, implemented
    worktree = root / lane.group(1).strip()
    (worktree / "src" / "wp01").mkdir(parents=True)
    (worktree / "src" / "wp01" / "__init__.py").write_text('GREETING = "hello from WP01"\n', encoding="utf-8")
    _git(worktree, env, "add", "--", "src/wp01")
    _git(worktree, env, "commit", "-qm", "implement WP01")
    cli("agent", "tasks", "mark-status", "T01", "--status", "done", "--mission", slug)
    cli("agent", "tasks", "move-task", "WP01", "--to", "for_review", "--mission", slug, "--agent", "claude")
    cli("agent", "action", "review", "WP01", "--mission", slug, "--agent", "reviewer")
    cli("agent", "tasks", "move-task", "WP01", "--to", "approved", "--mission", slug, "--agent", "reviewer", "--note", "reviewed")
    cli("agent", "acceptance-verdict", "--mission", slug, "--criterion", "FR-001", "--result", "pass", "--actor", "operator", "--evidence", "test")
    cli("accept", "--mission", slug, "--json", "--lenient")
    (root / "tmp.txt").write_text("stray\n", encoding="utf-8")

    cli("consolidate", "--mission", "demo", "--yes")

    spawned = int((tmp_path / "spawns.txt").read_text(encoding="utf-8"))
    assert _git(root, env, "show", f"{_TOPIC}:src/wp01/__init__.py") == 'GREETING = "hello from WP01"'
    assert spawned <= SPAWN_CEILING, json.dumps({"git_processes": spawned, "ceiling": SPAWN_CEILING})
