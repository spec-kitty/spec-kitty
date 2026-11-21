"""Repro #5936 — the first coordination writer in a teammate's clone refuses.

A teammate clones (or pulls) a repository whose coordination Mission was pushed
by its author. The coordination branch then exists in the teammate's clone only
as the remote-tracking ref ``refs/remotes/origin/kitty/mission-<slug>``: there is
no local head. Since rc6 (#5440) every coordination status write goes through
``materialize_coord_surface_for_write``, which refused any branch that was not a
local head with ``COORDINATION_WORKTREE_UNMATERIALIZED``, and the remedy it
printed (``git fetch`` + ``doctor coordination --fix``) changed nothing: the
doctor's ``--fix`` reached the same refusal. rc5 let ``git worktree add`` create
the local tracking branch from the remote-tracking ref and the write succeeded.

Built through the real CLI (``spec-kitty init``, ``agent mission create``,
``finalize-tasks``, ``implement``, ``move-task``), a real bare origin and a real
``git clone`` / ``git pull``, then each arm the issue names runs in the
teammate's clone: ``agent status emit``, ``agent tasks move-task``,
``agent tasks mark-status``, ``agent action review`` and the printed remedy ``doctor coordination --fix``.

The guard stays fail-closed for a branch this clone has no ref for at all: that
arm still refuses (``test_branch_with_no_local_ref_still_refuses``).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression, pytest.mark.slow, pytest.mark.non_sandbox]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TIMEOUT = 300


@dataclass(frozen=True)
class _Team:
    """The author's clone, a bare origin and a pristine teammate clone to copy per arm."""

    author: Path
    origin: Path
    teammate_template: Path
    slug: str
    env: dict[str, str]

    @property
    def coord_branch(self) -> str:
        return f"kitty/mission-{self.slug}"


def _env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "FORCE_COLOR", "CLICOLOR_FORCE")}
    for key, rel in (
        ("HOME", "home"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_STATE_HOME", "state"),
        ("SPEC_KITTY_HOME", "kitty"),
    ):
        path = home / rel
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    (home / "home" / ".gitconfig").write_text(
        "[user]\n\tname = QA\n\temail = qa@example.com\n[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n",
        encoding="utf-8",
    )
    env.update(
        PYTHONPATH=str(_REPO_ROOT / "src"),
        SPEC_KITTY_TEMPLATE_ROOT=str(_REPO_ROOT),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
        SPEC_KITTY_WORKTREE_REMOVAL_DELAY="0",
        SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS="1",
        NO_COLOR="1",
        COLUMNS="200",
        GIT_CONFIG_NOSYSTEM="1",
    )
    # Git merge drivers installed by `init` call `spec-kitty` by name.
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env


def _run(env: dict[str, str], cwd: Path, *args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(a) for a in args], cwd=str(cwd), env=env, text=True, capture_output=True, timeout=_TIMEOUT, check=False)


def _sk(env: dict[str, str], cwd: Path, *args: str | Path) -> subprocess.CompletedProcess[str]:
    return _run(env, cwd, sys.executable, "-m", "specify_cli.__init__", *args)


def _must(proc: subprocess.CompletedProcess[str], what: str) -> subprocess.CompletedProcess[str]:
    assert proc.returncode == 0, f"fixture step failed: {what}\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}"
    return proc


def _write_planning(feature_dir: Path) -> None:
    requirements = "".join(f"- **FR-00{i}**: requirement {i}.\n" for i in (1, 2, 3))
    (feature_dir / "spec.md").write_text(f"# Spec\n\n## Requirements\n\n{requirements}", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\nSimple files under src/.\n", encoding="utf-8")
    (feature_dir / "tasks").mkdir(exist_ok=True)
    tasks = "# Tasks\n\n"
    for i, letter in enumerate("abc", start=1):
        wp = f"WP0{i}"
        tasks += f"## Work Package {wp}: part {i}\n\n**Dependencies**: None\n\nRequirement refs: FR-00{i}\n\n- [ ] T0{i}1 do part {i}\n\n"
        (feature_dir / "tasks" / f"{wp}-part{i}.md").write_text(
            f"---\nwork_package_id: {wp}\ntitle: part {i}\ndependencies: []\nrequirement_refs: [FR-00{i}]\n"
            f"authoritative_surface: src/{letter}/\nowned_files:\n  - src/{letter}/**\nsubtasks:\n  - T0{i}1\n---\n"
            f"# {wp}\n\n- [ ] T0{i}1 do part {i}\n",
            encoding="utf-8",
        )
    (feature_dir / "tasks.md").write_text(tasks, encoding="utf-8")


@pytest.fixture(scope="module")
def team(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Team]:
    """Author creates a coord Mission, moves WP01 to for_review and pushes; the teammate clones and pulls."""
    root = tmp_path_factory.mktemp("team5936")
    env = _env(root / "env")
    origin = root / "origin.git"
    _must(_run(env, root, "git", "init", "-q", "--bare", "-b", "main", origin), "git init --bare")
    author = root / "author"
    author.mkdir()
    _must(_run(env, author, "git", "init", "-q", "-b", "main"), "git init")
    _must(_sk(env, author, "init", "--ai", "claude", "--non-interactive"), "spec-kitty init")
    (author / "README.md").write_text("fixture\n", encoding="utf-8")
    _run(env, author, "git", "add", "-A")
    _must(_run(env, author, "git", "commit", "-q", "-m", "init"), "init commit")
    created = _must(
        _sk(
            env,
            author,
            "agent",
            "mission",
            "create",
            "team",
            "--mission-type",
            "software-dev",
            "--topology",
            "coord",
            "--branch-strategy",
            "already-confirmed",
            "--target-branch",
            "main",
            "--friendly-name",
            "Team QA",
            "--purpose-tldr",
            "Two clone QA",
            "--purpose-context",
            "Functional QA fixture.",
            "--json",
        ),
        "mission create",
    )
    slug = json.loads(created.stdout)["mission_slug"]
    _write_planning(author / "kitty-specs" / slug)
    _run(env, author, "git", "add", "-A")
    _must(_run(env, author, "git", "commit", "-q", "-m", "planning"), "planning commit")
    _must(_sk(env, author, "agent", "mission", "finalize-tasks", "--mission", slug, "--json"), "finalize-tasks")
    _must(_sk(env, author, "implement", "WP01", "--mission", slug), "implement WP01")
    lane = author / ".worktrees" / f"{slug}-lane-a"
    (lane / "src" / "a").mkdir(parents=True, exist_ok=True)
    (lane / "src" / "a" / "mod.py").write_text("# WP01\n", encoding="utf-8")
    _run(env, lane, "git", "add", "-A")
    _must(_run(env, lane, "git", "commit", "-q", "-m", "WP01: work"), "WP01 commit")
    _sk(env, author, "agent", "tasks", "mark-status", "T011", "--status", "done", "--mission", slug)
    _must(_sk(env, author, "agent", "tasks", "move-task", "WP01", "--to", "for_review", "--agent", "author", "--mission", slug), "move-task for_review")
    _must(_run(env, author, "git", "remote", "add", "origin", origin), "remote add")
    _must(_run(env, author, "git", "push", "-q", "-u", "origin", "--all"), "push --all")

    teammate = root / "teammate-template"
    _must(_run(env, root, "git", "clone", "-q", origin, teammate), "clone")
    _must(_run(env, teammate, "git", "pull", "-q", "--no-rebase"), "pull")
    yield _Team(author=author, origin=origin, teammate_template=teammate, slug=slug, env=env)


def _teammate(team: _Team, tmp_path: Path) -> Path:
    clone = tmp_path / "teammate"
    shutil.copytree(team.teammate_template, clone, symlinks=True)
    return clone


def _has_local_head(env: dict[str, str], repo: Path, branch: str) -> bool:
    return _run(env, repo, "git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0


def _assert_remote_only(team: _Team, clone: Path) -> None:
    assert not _has_local_head(team.env, clone, team.coord_branch), "fixture precondition: no local coordination head"
    tracking = _run(team.env, clone, "git", "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{team.coord_branch}")
    assert tracking.returncode == 0, "fixture precondition: the clone carries the remote-tracking ref"


def _assert_materialized(team: _Team, clone: Path) -> None:
    worktrees = _run(team.env, clone, "git", "worktree", "list", "--porcelain").stdout
    assert f"branch refs/heads/{team.coord_branch}" in worktrees, worktrees
    upstream = _run(team.env, clone, "git", "rev-parse", "--abbrev-ref", f"{team.coord_branch}@{{upstream}}")
    assert upstream.stdout.strip() == f"origin/{team.coord_branch}", upstream.stdout + upstream.stderr
    local = _run(team.env, clone, "git", "rev-parse", f"refs/heads/{team.coord_branch}").stdout.strip()
    remote = _run(team.env, clone, "git", "rev-parse", f"refs/remotes/origin/{team.coord_branch}").stdout.strip()
    # The status write may add its own commit on top; the local branch must descend from the remote one, never fork from main.
    ancestry = _run(team.env, clone, "git", "merge-base", "--is-ancestor", remote, local)
    assert ancestry.returncode == 0, f"local {local} does not descend from origin's coordination tip {remote}"


_ARMS = {
    "emit": ("agent", "status", "emit", "WP01", "--to", "in_review", "--actor", "teammate"),
    "markstatus": ("agent", "tasks", "mark-status", "T021", "--status", "done"),
    # An artifact writer (issue matrix) goes through the write seam's own gate, not the status seam.
    "issueverdict": ("agent", "issue-verdict", "--issue", "#5936", "--verdict", "in-mission", "--actor", "teammate", "--wp", "WP01"),
    # The WP is assigned to its implementer; the teammate takes the review seat.
    "movetask": ("agent", "tasks", "move-task", "WP01", "--to", "in_review", "--agent", "author", "--reviewer", "teammate"),
    "review": ("agent", "action", "review", "WP01", "--agent", "teammate"),
    # Without a WP id, review auto-detects the first for_review WP by reading status first.
    "reviewauto": ("agent", "action", "review", "--agent", "teammate"),
}


@pytest.mark.parametrize("arm", sorted(_ARMS))
def test_first_coord_writer_in_teammate_clone_materializes(team: _Team, tmp_path: Path, arm: str) -> None:
    """Each coordination writer in a fresh teammate clone materializes the coordination surface and succeeds."""
    clone = _teammate(team, tmp_path)
    _assert_remote_only(team, clone)
    if arm in ("review", "reviewauto"):
        # Review also syncs the WP's lane after its claim, and the lane branch is
        # remote-only in this clone too. Creating a remote-only LANE head is a
        # separate gap (outside #5936's coordination scope), so the reviewer
        # tracks the lane by hand here, as a reviewer would to read its commits.
        lane = f"{team.coord_branch}-lane-a"
        _must(_run(team.env, clone, "git", "branch", "--track", lane, f"origin/{lane}"), "track lane branch")

    proc = _sk(team.env, clone, *_ARMS[arm], "--mission", team.slug)

    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"{arm} refused in the teammate clone:\n{output[-3000:]}"
    assert "COORDINATION_WORKTREE_UNMATERIALIZED" not in output
    _assert_materialized(team, clone)


def test_doctor_coordination_fix_materializes_in_teammate_clone(team: _Team, tmp_path: Path) -> None:
    """The remedy the refusal printed, ``doctor coordination --fix``, creates the local branch and the worktree."""
    clone = _teammate(team, tmp_path)
    _assert_remote_only(team, clone)

    proc = _sk(team.env, clone, "doctor", "coordination", "--mission", team.slug, "--fix")

    output = proc.stdout + proc.stderr
    # The exit code is not asserted: the same run also reports that the
    # coordination branch has diverged from ``main`` (normal while WPs are in
    # flight; a separate doctor check from the worktree materialization).
    assert f"Materialized: coordination worktree for mission {team.slug!r}." in output, output[-3000:]
    assert "exists only as a remote-tracking ref" not in output, output[-3000:]
    _assert_materialized(team, clone)
    # The write that refused before now succeeds without any manual git step.
    emit = _sk(team.env, clone, *_ARMS["emit"], "--mission", team.slug)
    assert emit.returncode == 0, (emit.stdout + emit.stderr)[-3000:]


def test_doctor_coordination_report_leads_with_fix_for_tracking_ref(team: _Team, tmp_path: Path) -> None:
    """The read-only report names ``--fix`` (which now works) rather than manual fetch/branch steps."""
    clone = _teammate(team, tmp_path)

    proc = _sk(team.env, clone, "doctor", "coordination", "--mission", team.slug)

    output = proc.stdout + proc.stderr
    assert f"spec-kitty doctor coordination --mission {team.slug} --fix" in output, output[-3000:]
    assert not _has_local_head(team.env, clone, team.coord_branch), "the report must not write a branch"


def test_branch_with_no_local_ref_still_refuses(team: _Team, tmp_path: Path) -> None:
    """Fail-closed: with neither a local head nor a remote-tracking ref, the writer still refuses (no fork from main)."""
    clone = _teammate(team, tmp_path)
    # The branch still lives on origin, but this clone never fetched it (a single-branch / shallow / CI
    # clone): no local ref proves its content, so the guard refuses rather than fork from main.
    _must(_run(team.env, clone, "git", "update-ref", "-d", f"refs/remotes/origin/{team.coord_branch}"), "drop tracking ref")

    proc = _sk(team.env, clone, *_ARMS["emit"], "--mission", team.slug)

    output = proc.stdout + proc.stderr
    assert proc.returncode != 0, output[-3000:]
    # The refusal comes from the coordination guard, not from some unrelated failure.
    assert "is unmaterialized" in output, output[-3000:]
    assert not _has_local_head(team.env, clone, team.coord_branch)
