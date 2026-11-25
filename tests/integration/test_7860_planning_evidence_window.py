"""#7860: a planning-artifact work package's evidence window ends at the branch its work is written to.

Background (#7860, P1). A Mission created without ``--topology`` mints one topic branch and settles
its topology at the first ``finalize-tasks`` by size; with more than one code lane it settles
``lanes_with_coord``, the topic branch becoming the coordination branch (ADR ``2026-11-06-3``).
Until the Mission lands, its PRIMARY partition, and with it every planning-artifact work package's
work, is written to that topic branch (FR-061, :func:`mission_runtime.resolution.default_mission_primary_ref`).
The #6715 evidence axis nevertheless ended a planning lane's window at the TARGET branch, which
holds none of that work before the landing, so ``move-task --to for_review`` refused every planning
work package with ``IMPLEMENTATION_MISSING`` (reproduced in spec-kitty-open-packs, Mission
``pack-doctor-alignment``).

After the settlement the repository root checkout is back on the target and ``implement`` names
it as the planning lane's workspace, so work committed where ``implement`` says lands on the
target. Both places must count; the rule that reconciles them is pending an operator ruling.

* :func:`test_planning_work_on_the_topic_branch_moves_into_review` -- the reproduction: the owned
  file is committed on the topic branch and the unforced move into review passes.
* :func:`test_planning_work_where_implement_puts_it_moves_into_review` -- the control: work
  committed in the root checkout on the target keeps passing.
* :func:`test_a_hollow_planning_work_package_is_still_refused` -- the negative control: with no
  owned change the move is still refused.

Drives the REAL CLI end to end in an isolated HOME.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(900)]

_CLI = [sys.executable, "-m", "specify_cli"]
_PLANNING_OWNED = "kitty-specs/{slug}/research/notes.md"


@dataclass(frozen=True)
class _Mission:
    repo: Path
    env: dict[str, str]
    slug: str
    topic_branch: str
    topic_checkout: Path

    @property
    def feature_dir(self) -> Path:
        """The Mission directory on the topic branch (its checkout after the settlement)."""
        return self.topic_checkout / "kitty-specs" / self.slug


def _env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HOME=str(home / "home"),
        XDG_CONFIG_HOME=str(home / "xc"),
        XDG_CACHE_HOME=str(home / "xcache"),
        XDG_DATA_HOME=str(home / "xd"),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
        SPEC_KITTY_WORKTREE_REMOVAL_DELAY="0",
        SPEC_KITTY_ENABLE_SAAS_SYNC="0",
    )
    for key in ("home", "xc", "xcache", "xd"):
        (home / key).mkdir(parents=True, exist_ok=True)
    return env


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _sk(mission: _Mission | tuple[Path, dict[str, str]], *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    repo, env = (mission.repo, mission.env) if isinstance(mission, _Mission) else mission
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=400)
    if check and proc.returncode != 0:
        raise AssertionError(f"fixture setup step failed: spec-kitty {' '.join(args)}\nrc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc


def _wp_file(wp: str, subtask: str, owned: str, *, planning: bool = False) -> str:
    surface = owned.split("*")[0]
    extra = "execution_mode: planning_artifact\n" if planning else ""
    return (
        f"---\nwork_package_id: {wp}\ntitle: {wp}\ndependencies: []\nrequirement_refs: [FR-001]\n{extra}"
        f"authoritative_surface: {surface}\nowned_files:\n  - {owned}\ncreate_intent:\n  - {owned}\nsubtasks:\n  - {subtask}\n---\n# {wp}\n\n- [ ] {subtask} do\n"
    )


_WPS = (
    ("WP01", "T1", "src/m1/**", False),
    ("WP02", "T2", _PLANNING_OWNED, True),
    ("WP03", "T3", "src/m3/**", False),
    ("WP04", "T4", "src/m4/**", False),
)


def setup_default_mission(tmp_path: Path) -> _Mission:
    """A Mission created WITHOUT ``--topology``: three code WPs (three lanes) and one planning WP02.

    ``finalize-tasks`` settles it ``lanes_with_coord`` by size, its topic branch becoming the
    coordination branch; the repository root checkout stays on that topic branch.
    """
    env = _env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _sk((repo, env), "init", "--ai", "claude", "--non-interactive", check=True)
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    created = _sk(
        (repo, env),
        *("agent", "mission", "create", "fx", "--mission-type", "software-dev"),
        *("--branch-strategy", "already-confirmed", "--target-branch", "main", "--friendly-name", "fx"),
        *("--purpose-tldr", "fx", "--purpose-context", "QA fixture.", "--json"),
        check=True,
    )
    slug = json.loads(created.stdout)["mission_slug"]
    fd = repo / "kitty-specs" / slug
    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    sections = "".join(f"## Work Package {wp}: {wp}\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] {t} do\n\n" for wp, t, _o, _p in _WPS)
    (fd / "tasks.md").write_text(f"# Tasks\n\n{sections}", encoding="utf-8")
    for wp, subtask, owned, planning in _WPS:
        owned_path = owned.format(slug=slug)
        (fd / "tasks" / f"{wp}-work.md").write_text(_wp_file(wp, subtask, owned_path, planning=planning), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    topic_branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    _sk((repo, env), "agent", "mission", "finalize-tasks", "--mission", slug, "--json", check=True)
    mission = _Mission(repo, env, slug, topic_branch, _checkout_of(repo, topic_branch))
    (tmp_path / "analysis.md").write_text("# Analysis\n\nNo blocking findings.\n", encoding="utf-8")
    _sk(mission, "agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(tmp_path / "analysis.md"), check=True)
    _commit_bookkeeping(mission.topic_checkout)
    return mission


def _checkout_of(repo: Path, branch: str) -> Path:
    """The worktree that has *branch* checked out (the settlement moves the topic branch into the coordination worktree)."""
    current: Path | None = None
    for line in _git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current = Path(line.removeprefix("worktree "))
        elif line == f"branch refs/heads/{branch}" and current is not None:
            return current
    raise AssertionError(f"fixture: no checkout of {branch}")


def _commit_bookkeeping(repo: Path) -> None:
    if _git(repo, "status", "--porcelain", "--", "kitty-specs"):
        _git(repo, "add", "-A", "kitty-specs")
        _git(repo, "commit", "-qm", "status residue")


def _meta(mission: _Mission) -> dict[str, object]:
    loaded: dict[str, object] = json.loads((mission.feature_dir / "meta.json").read_text(encoding="utf-8"))
    return loaded


def _claim_planning_wp(mission: _Mission) -> str:
    """Claim WP02 and return its owned path (the Mission directory sits on the topic branch)."""
    meta = _meta(mission)
    assert meta.get("topology") == "lanes_with_coord", f"fixture: the size rule must settle lanes_with_coord; meta={meta}"
    assert meta.get("topology_source") == "default", f"fixture: a Mission created without --topology; meta={meta}"
    assert meta.get("coordination_branch") == mission.topic_branch, f"fixture: the topic branch is the coordination branch; meta={meta}"
    _sk(mission, "agent", "action", "implement", "WP02", "--agent", "alice", "--mission", mission.slug, check=True)
    return _PLANNING_OWNED.format(slug=mission.slug)


def _commit_owned(checkout: Path, relpath: str) -> None:
    owned = checkout / relpath
    owned.parent.mkdir(parents=True, exist_ok=True)
    owned.write_text("# WP02 research\n", encoding="utf-8")
    _git(checkout, "add", "--", relpath)
    _git(checkout, "commit", "-qm", "feat(WP02): research notes")


def _move_into_review(mission: _Mission) -> subprocess.CompletedProcess[str]:
    _sk(mission, "agent", "tasks", "mark-status", "T2", "--status", "done", "--mission", mission.slug)
    _commit_bookkeeping(mission.topic_checkout)
    return _sk(mission, "agent", "tasks", "move-task", "WP02", "--to", "for_review", "--agent", "alice", "--note", "done", "--mission", mission.slug)


def _on_branch(mission: _Mission, branch: str, relpath: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{branch}:{relpath}"], cwd=mission.repo, capture_output=True).returncode == 0


def test_planning_work_on_the_topic_branch_moves_into_review(tmp_path: Path) -> None:
    """The #7860 shape: the work is committed on the topic (coordination) branch. Red on main @ e6b18eeb."""
    mission = setup_default_mission(tmp_path)
    relpath = _claim_planning_wp(mission)
    _commit_owned(mission.topic_checkout, relpath)
    assert not _on_branch(mission, "main", relpath), "fixture: the target branch must not carry the planning work before the landing"

    moved = _move_into_review(mission)
    output = moved.stdout + moved.stderr

    assert "IMPLEMENTATION_MISSING" not in output, f"planning work on the topic branch is the work package's evidence. output:\n{output[-3000:]}"
    assert moved.returncode == 0, f"the unforced move into review must pass. output:\n{output[-3000:]}"


def test_planning_work_where_implement_puts_it_moves_into_review(tmp_path: Path) -> None:
    """Control: implement names the repository root checkout, on the target branch; work committed there passes today."""
    mission = setup_default_mission(tmp_path)
    relpath = _claim_planning_wp(mission)
    assert _git(mission.repo, "rev-parse", "--abbrev-ref", "HEAD") == "main", "fixture: the settlement returns the root checkout to the target"
    _commit_owned(mission.repo, relpath)

    moved = _move_into_review(mission)
    output = moved.stdout + moved.stderr

    assert moved.returncode == 0, f"work committed where implement puts it must pass. output:\n{output[-3000:]}"


def test_a_hollow_planning_work_package_is_still_refused(tmp_path: Path) -> None:
    mission = setup_default_mission(tmp_path)
    _claim_planning_wp(mission)

    moved = _move_into_review(mission)
    output = moved.stdout + moved.stderr

    assert moved.returncode != 0, f"a planning work package with no owned change must still be refused. output:\n{output[-3000:]}"
    assert "IMPLEMENTATION_MISSING" in output, output[-3000:]
