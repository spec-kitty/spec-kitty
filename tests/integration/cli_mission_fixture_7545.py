"""A real-CLI Mission fixture for the #7545 red tests (the CLI commits its own writes).

Drives the installed source CLI as a subprocess, the way an agent does: ``init``,
``agent mission create``, planning files, ``finalize-tasks``, ``record-analysis``.
Each test then runs the command under test through the same entry point and
reads ``git status`` itself. Shared by the WP02..WP04 tests of Mission
``cli-owns-its-commits-01M75NTA`` so each red test stays small.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_CLI = [sys.executable, "-m", "specify_cli"]

ANALYSIS_BODY = (
    "---\n"
    "schema: analysis-findings/v1\n"
    "findings: []\n"
    "counts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n"
    "verdict_hint: ready\n"
    "---\n"
    "# Analysis\n\n"
    "No blocking findings.\n"
)


@dataclass(frozen=True)
class CliMission:
    """A created, finalized Mission in a throwaway repository."""

    repo: Path
    env: dict[str, str]
    slug: str
    topology: str

    @property
    def feature_dir(self) -> Path:
        return self.repo / "kitty-specs" / self.slug

    def run(self, *args: str, check: bool = False, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return run_sk(cwd or self.repo, self.env, *args, check=check)

    def coordination_worktree(self) -> Path:
        matches = sorted((self.repo / ".worktrees").glob("*-coord"))
        assert len(matches) == 1, f"expected one coordination worktree, found {matches}"
        return matches[0]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def dirty(checkout: Path) -> list[str]:
    """Every uncommitted path in ``checkout`` (all untracked files listed)."""
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=checkout, check=True, capture_output=True, text=True).stdout
    return [line[3:] for line in out.splitlines()]


def run_sk(repo: Path, env: dict[str, str], *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=400)
    if check and proc.returncode != 0:
        raise AssertionError(f"fixture step failed: spec-kitty {' '.join(args)}\nrc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc


def flat(proc: subprocess.CompletedProcess[str]) -> str:
    """stdout+stderr with whitespace runs collapsed (the console wraps long lines)."""
    return " ".join((proc.stdout + proc.stderr).split())


def json_of(proc: subprocess.CompletedProcess[str]) -> dict[str, object]:
    text = proc.stdout
    data = json.JSONDecoder().raw_decode(text[text.index("{") :])[0]
    assert isinstance(data, dict)
    return data


def isolated_env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HOME=str(home / "home"),
        XDG_CONFIG_HOME=str(home / "xc"),
        XDG_CACHE_HOME=str(home / "xcache"),
        XDG_DATA_HOME=str(home / "xd"),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
        SPEC_KITTY_WORKTREE_REMOVAL_DELAY="0",
        SPEC_KITTY_ENABLE_SAAS_SYNC="0",
        NO_COLOR="1",
    )
    env.pop("FORCE_COLOR", None)
    for key in ("home", "xc", "xcache", "xd"):
        (home / key).mkdir(parents=True, exist_ok=True)
    return env


def init_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A git repository on an unprotected ``dev`` branch with ``spec-kitty init`` committed."""
    env = isolated_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "trunk")
    git(repo, "config", "user.name", "QA")
    git(repo, "config", "user.email", "qa@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "commit", "-q", "--allow-empty", "-m", "root")
    run_sk(repo, env, "init", "--ai", "claude", "--non-interactive", check=True)
    if dirty(repo):
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "init")
    git(repo, "checkout", "-qb", "dev")
    return repo, env


def _wp_file(wp: str, subtask: str, owned: str) -> str:
    return (
        f"---\nwork_package_id: {wp}\ntitle: {wp}\ndependencies: []\nrequirement_refs: [FR-001]\n"
        f"authoritative_surface: {owned.rstrip('*')}\nowned_files:\n  - {owned}\nsubtasks:\n  - {subtask}\n"
        f"---\n# {wp}\n\n- [ ] {subtask} do\n"
    )


def create_mission(repo: Path, env: dict[str, str], name: str, *, topology: str, record_analysis: bool = True) -> CliMission:
    """Create, plan (one WP owning ``src/<name>/**``), finalize and analyse a Mission."""
    created = run_sk(
        repo,
        env,
        *("agent", "mission", "create", name, "--mission-type", "software-dev", "--topology", topology),
        *("--target-branch", "dev", "--friendly-name", name, "--purpose-tldr", name, "--purpose-context", "Fixture.", "--json"),
        check=True,
    )
    slug = str(json_of(created)["mission_slug"])
    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (feature_dir / "tasks").mkdir(exist_ok=True)
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01: WP01\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T001 do\n\n", encoding="utf-8"
    )
    (feature_dir / "tasks" / "WP01-a.md").write_text(_wp_file("WP01", "T001", f"src/{name}/**"), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", f"planning {name}")
    run_sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--json", check=True)
    mission = CliMission(repo, env, slug, topology)
    if record_analysis:
        body = repo.parent / f"analysis-{name}.md"
        body.write_text(ANALYSIS_BODY, encoding="utf-8")
        mission.run("agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(body), "--json", check=True)
    if dirty(repo):
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", f"fixture residue {name}")
    return mission
