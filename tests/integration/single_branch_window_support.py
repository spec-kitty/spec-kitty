"""Shared ``single_branch`` Mission builder and lifecycle steps (#7283, promoted from the S8 test module).

A pure move out of ``tests/integration/test_single_branch_approval_windows.py`` (consolidation-window-provenance
WP02): that module keeps its pytest fixtures and tests and imports these helpers; the characterization corpus
(``tests/consolidation/characterization_support.py``) reuses them to build its ``single_branch`` shape.

The Mission is built through the real CLI (``init``, ``agent mission create --topology single_branch`` on protected
``main``, ``finalize-tasks``); lifecycle moves run in-process through the Typer apps; :func:`consolidate` runs the
real CLI as a subprocess.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.status import app as status_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from tests._support.ansi import strip_ansi

TARGET = "main"
_CLI = [sys.executable, "-m", "specify_cli"]
_REVIEW = json.dumps({"reviewer": "bob", "verdict": "approved", "reference": "PR#1"})
_NO_HOOKS = ("-c", "core.hooksPath=/dev/null")

_runner = CliRunner()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *_NO_HOOKS, *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def cli_env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HOME=str(home / "home"),
        XDG_CONFIG_HOME=str(home / "xc"),
        XDG_CACHE_HOME=str(home / "xcache"),
        XDG_DATA_HOME=str(home / "xd"),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
        SPEC_KITTY_WORKTREE_REMOVAL_DELAY="0",
        SPEC_KITTY_ORIGIN_CHECK="off",
    )
    # A protected-branch override would make create skip the Mission-branch mint.
    env.pop("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", None)
    for key in ("home", "xc", "xcache", "xd"):
        (home / key).mkdir(parents=True, exist_ok=True)
    return env


def _sk(repo: Path, env: dict[str, str], *args: str) -> str:
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=400)
    if proc.returncode != 0:
        raise AssertionError(f"spec-kitty {' '.join(args)} failed rc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc.stdout


def _wp_file(wp: str, module: str, subtask: str) -> str:
    return (
        f"---\nwork_package_id: {wp}\ntitle: {wp} {module}\ndependencies: []\nrequirement_refs: [FR-001]\n"
        f"authoritative_surface: src/{module}/\nowned_files:\n  - src/{module}/**\nsubtasks:\n  - {subtask}\n---\n"
        f"# {wp} {module}\n\n- [ ] {subtask} do {module}\n"
    )


def build_template(base: Path, *, commit_to_target: bool) -> tuple[Path, str]:
    """A ``single_branch`` Mission on protected ``main`` with two code work packages (WP01 owns src/m1, WP02 src/m2)."""
    env = cli_env(base)
    repo = base / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", TARGET)
    git(repo, "config", "user.name", "QA")
    git(repo, "config", "user.email", "qa@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    _sk(repo, env, "init", "--ai", "claude", "--non-interactive")
    (repo / "src").mkdir()
    (repo / "src" / "shared.py").write_text("A = 1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    extra = ("--commit-to-target",) if commit_to_target else ()
    created = _sk(
        repo,
        env,
        *("agent", "mission", "create", "fx", "--mission-type", "software-dev", "--topology", "single_branch", *extra),
        *("--branch-strategy", "already-confirmed", "--target-branch", TARGET, "--friendly-name", "fx"),
        *("--purpose-tldr", "fx", "--purpose-context", "QA fixture.", "--json"),
    )
    slug = str(json.loads(created)["mission_slug"])
    fd = repo / "kitty-specs" / slug
    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    (fd / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01: m1\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T1 do m1\n\n"
        "## Work Package WP02: m2\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T2 do m2\n",
        encoding="utf-8",
    )
    (fd / "tasks" / "WP01-m1.md").write_text(_wp_file("WP01", "m1", "T1"), encoding="utf-8")
    (fd / "tasks" / "WP02-m2.md").write_text(_wp_file("WP02", "m2", "T2"), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "planning")
    _sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--json")
    (base / "analysis.md").write_text("# Analysis\n\nNo blocking findings.\n", encoding="utf-8")
    _sk(repo, env, "agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(base / "analysis.md"))
    settle(repo)
    return repo, slug


class Mission:
    """One copied Mission checkout: the repository, its slug and the CLI environment."""

    def __init__(self, repo: Path, slug: str, home: Path) -> None:
        self.repo = repo
        self.slug = slug
        self.env = cli_env(home)

    @property
    def mission_branch(self) -> str:
        meta = json.loads((self.repo / "kitty-specs" / self.slug / "meta.json").read_text(encoding="utf-8"))
        return str(meta["mission_branch"])


def settle(repo: Path) -> None:
    """Commit whatever the CLI left in ``kitty-specs`` (status rows, ticked subtasks): Mission bookkeeping."""
    if git(repo, "status", "--porcelain", "--", "kitty-specs"):
        git(repo, "add", "-A", "kitty-specs")
        git(repo, "commit", "-qm", "chore: status bookkeeping")


def _invoke(app: typer.Typer, args: list[str]) -> tuple[int, str]:
    result = _runner.invoke(app, args)
    return result.exit_code, strip_ansi(result.output + (result.stderr if result.stderr_bytes is not None else ""))


def move(m: Mission, wp: str, to: str, agent: str, *extra: str) -> None:
    code, out = _invoke(tasks_app, ["move-task", wp, "--to", to, "--agent", agent, "--note", f"{to} by {agent}", "--mission", m.slug, *extra])
    assert code == 0, out
    settle(m.repo)


def emit(m: Mission, wp: str, to: str, actor: str, *extra: str) -> None:
    code, out = _invoke(status_app, ["emit", wp, "--to", to, "--actor", actor, "--mission", m.slug, *extra])
    assert code == 0, out
    settle(m.repo)


def commit_file(m: Mission, rel: str, content: str, message: str) -> str:
    path = m.repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(m.repo, "add", rel)
    git(m.repo, "commit", "-qm", message)
    return git(m.repo, "rev-parse", "HEAD")


_MODULE = {"WP01": ("m1", "T1"), "WP02": ("m2", "T2")}


def claim(m: Mission, wp: str) -> None:
    move(m, wp, "in_progress", "alice")


def implement(m: Mission, wp: str, *, revision: int = 1) -> str:
    """alice commits real work in *wp*'s owned files and ticks its subtask."""
    module, subtask = _MODULE[wp]
    sha = commit_file(m, f"src/{module}/real.py", f"VALUE = {wp!r}\nREVISION = {revision}\n", f"feat({wp}): implement {module} r{revision}")
    code, out = _invoke(tasks_app, ["mark-status", subtask, "--status", "done", "--mission", m.slug])
    assert code == 0, out
    settle(m.repo)
    return sha


def submit(m: Mission, wp: str) -> None:
    """Hand *wp* to review: a forced ``for_review`` (the commit gate is not under test), then bob's unforced review claim."""
    emit(m, wp, "for_review", "alice", "--force", "--reason", "handed to review")
    emit(m, wp, "in_review", "bob")


def approve(m: Mission, wp: str) -> None:
    emit(m, wp, "approved", "bob", "--review-result-json", _REVIEW)


def send_back(m: Mission, wp: str) -> None:
    move(m, wp, "in_progress", "alice", "--force")


def build_and_approve(m: Mission, wp: str) -> None:
    claim(m, wp)
    implement(m, wp)
    submit(m, wp)
    approve(m, wp)


# --------------------------------------------------------------------------- consolidate


def consolidate(m: Mission, *extra: str) -> tuple[int, str]:
    proc = subprocess.run(
        [*_CLI, "consolidate", "--mission", m.slug, "--yes", *extra],
        cwd=m.repo,
        env=m.env,
        capture_output=True,
        text=True,
        timeout=400,
    )
    return proc.returncode, " ".join((proc.stdout + "\n" + proc.stderr).split())


def tip(m: Mission, ref: str) -> str:
    return git(m.repo, "rev-parse", ref)
