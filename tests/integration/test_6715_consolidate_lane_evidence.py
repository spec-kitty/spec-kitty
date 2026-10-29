"""#6715: ``consolidate`` refuses an approved lanes/coord work package with no implementation or no independent review.

Background (#6715, P0). #5939 closed the hollow-approval hole for ``single_branch`` only. On a
``lanes`` or ``coord`` Mission a work package that was claimed but never implemented (or was
approved by its own implementer) still consolidated as ``done`` at exit 0 and printed the
"Reconciliation verified" banner, with its owned deliverable absent from the target: the
approved-bound check (#5668) finds nothing to bound on a lane that holds no content commit, and
nothing else asked whether the owned files changed.

The consolidate claim builder now runs one topology-neutral evidence axis
(``consolidation/wp_evidence.py``) for every lane, code and planning alike:

* :func:`test_hollow_and_self_approved_work_packages_are_refused` -- WP02 approved with no
  change to its owned file (``IMPLEMENTATION_MISSING``), WP03 approved by its own implementer
  (``REVIEW_NOT_INDEPENDENT``) and WP04, a planning-artifact work package, approved with no
  change to its research file (``IMPLEMENTATION_MISSING``): consolidate exits non-zero before any
  branch moves, never prints the banner, lands nothing ``done``.
* :func:`test_real_work_with_independent_review_consolidates_clean` -- the positive control on
  the same fixture shape: real owned-file commits (code lanes and the planning lane) and an
  independent reviewer consolidate clean with every work package ``done``.

The approvals that the fixture forces (``--force`` from ``in_review``) keep the approval stamp
(a review claim precedes them), so the approved-bound check passes and the evidence axis is the
one that refuses. Drives the REAL CLI end to end in an isolated HOME.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

# Each case drives ~50 real CLI calls over four work packages; the default 240 s budget is too
# tight on a loaded runner, so the cases carry their own (pytest.ini: mark, never raise the default).
pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1200)]

_CLI = [sys.executable, "-m", "specify_cli"]
_BANNER = "Reconciliation verified"
_RESEARCH_FILE = "research/notes.md"


@dataclass(frozen=True)
class _Mission:
    repo: Path
    env: dict[str, str]
    slug: str
    feature_dir: Path


def _env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HOME=str(home / "home"),
        XDG_CONFIG_HOME=str(home / "xc"),
        XDG_CACHE_HOME=str(home / "xcache"),
        XDG_DATA_HOME=str(home / "xd"),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
        SPEC_KITTY_WORKTREE_REMOVAL_DELAY="0",
        SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS="1",
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


def _commit_specs(repo: Path) -> None:
    if _git(repo, "status", "--porcelain", "--", "kitty-specs"):
        _git(repo, "add", "-A", "kitty-specs")
        _git(repo, "commit", "-qm", "status residue")


def _wp_file(wp: str, subtask: str, owned: str, *, planning: bool = False, create: bool = False) -> str:
    surface = owned.split("*")[0]
    extra = "execution_mode: planning_artifact\n" if planning else ""
    intent = f"create_intent:\n  - {owned}\n" if create else ""
    return (
        f"---\nwork_package_id: {wp}\ntitle: {wp}\ndependencies: []\nrequirement_refs: [FR-001]\n{extra}"
        f"authoritative_surface: {surface}\nowned_files:\n  - {owned}\n{intent}subtasks:\n  - {subtask}\n---\n# {wp}\n\n- [ ] {subtask} do\n"
    )


def setup_mission(tmp_path: Path, topology: str) -> _Mission:
    """A Mission with three code WPs (WP01 ``src/m1/**``, WP02 ``tools/check.sh``, WP03 ``src/m3/**``) and one planning WP04."""
    env = _env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _sk((repo, env), "init", "--ai", "claude", "--non-interactive", check=True)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "shared.py").write_text("A = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    created = _sk(
        (repo, env),
        *("agent", "mission", "create", "fx", "--mission-type", "software-dev", "--topology", topology),
        *("--branch-strategy", "already-confirmed", "--target-branch", "main", "--friendly-name", "fx"),
        *("--purpose-tldr", "fx", "--purpose-context", "QA fixture.", "--json"),
        check=True,
    )
    slug = json.loads(created.stdout)["mission_slug"]
    fd = repo / "kitty-specs" / slug
    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    sections = "".join(
        f"## Work Package {wp}: {wp}\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] {t} do\n\n"
        for wp, t in (("WP01", "T1"), ("WP02", "T2"), ("WP03", "T3"), ("WP04", "T4"))
    )
    (fd / "tasks.md").write_text(f"# Tasks\n\n{sections}", encoding="utf-8")
    (fd / "tasks" / "WP01-m1.md").write_text(_wp_file("WP01", "T1", "src/m1/**"), encoding="utf-8")
    (fd / "tasks" / "WP02-tools.md").write_text(_wp_file("WP02", "T2", "tools/check.sh", create=True), encoding="utf-8")
    (fd / "tasks" / "WP03-m3.md").write_text(_wp_file("WP03", "T3", "src/m3/**"), encoding="utf-8")
    (fd / "tasks" / "WP04-research.md").write_text(_wp_file("WP04", "T4", f"kitty-specs/{slug}/research/**", planning=True), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    mission = _Mission(repo, env, slug, fd)
    _sk(mission, "agent", "mission", "finalize-tasks", "--mission", slug, "--json", check=True)
    (tmp_path / "analysis.md").write_text("# Analysis\n\nNo blocking findings.\n", encoding="utf-8")
    _sk(mission, "agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(tmp_path / "analysis.md"))
    _commit_specs(repo)
    return mission


def _workspace_for(mission: _Mission, wp: str) -> Path:
    """The checkout a WP's implementation is committed in: its lane worktree, or the repository root for the planning lane."""
    manifest = json.loads((mission.feature_dir / "lanes.json").read_text(encoding="utf-8"))
    lane_id = next(lane["lane_id"] for lane in manifest["lanes"] if wp in lane["wp_ids"])
    worktree = mission.repo / ".worktrees" / f"{mission.slug}-{lane_id}"
    return worktree if worktree.is_dir() else mission.repo


def _commit_owned(mission: _Mission, wp: str, relpath: str) -> None:
    checkout = _workspace_for(mission, wp)
    target = checkout / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"# {wp}\n", encoding="utf-8")
    _git(checkout, "add", "--", relpath)
    _git(checkout, "commit", "-qm", f"feat({wp}): implement")


def drive(mission: _Mission, wp: str, subtask: str, *, implementer: str, reviewer: str, owned_path: str | None) -> None:
    """Claim, optionally commit, review and approve *wp*.

    Every move after the claim is forced so a move-time gate can never mask what consolidate
    sees; the approval comes out of ``in_review`` after a review claim, so it keeps the approval
    stamp (#5668) and the approved-bound check passes.
    """
    slug = mission.slug
    _sk(mission, "agent", "action", "implement", wp, "--agent", implementer, "--mission", slug, check=True)
    if owned_path is not None:
        _commit_owned(mission, wp, owned_path)
    _sk(mission, "agent", "tasks", "mark-status", subtask, "--status", "done", "--mission", slug)
    _sk(mission, "agent", "tasks", "move-task", wp, "--to", "for_review", "--agent", implementer, "--note", "done", "--force", "--mission", slug, check=True)
    _sk(mission, "agent", "action", "review", wp, "--agent", reviewer, "--mission", slug, check=True)
    _sk(mission, "agent", "tasks", "move-task", wp, "--to", "approved", "--agent", reviewer, "--note", "lgtm", "--force", "--mission", slug, check=True)
    _commit_specs(mission.repo)


def lanes_of(mission: _Mission) -> dict[str, str]:
    status = _sk(mission, "agent", "tasks", "status", "--mission", mission.slug, "--json")
    try:
        return {w["id"]: w["lane"] for w in json.loads(status.stdout)["work_packages"]}
    except (ValueError, KeyError, TypeError):
        return {"<unparsed>": status.stdout[-400:]}


def accept(mission: _Mission) -> None:
    """Record the acceptance verdict and run ``accept --lenient`` (its exit code is not this file's concern)."""
    _sk(mission, "agent", "acceptance-verdict", "--mission", mission.slug, "--criterion", "FR-001", "--result", "pass", "--actor", "operator", "--evidence", "qa")
    _commit_specs(mission.repo)
    _sk(mission, "accept", "--mission", mission.slug, "--json", "--lenient")
    _commit_specs(mission.repo)


def on_target(mission: _Mission, relpath: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"main:{relpath}"], cwd=mission.repo, capture_output=True).returncode == 0


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_hollow_and_self_approved_work_packages_are_refused(tmp_path: Path, topology: str) -> None:
    mission = setup_mission(tmp_path, topology)
    research = f"kitty-specs/{mission.slug}/{_RESEARCH_FILE}"
    drive(mission, "WP01", "T1", implementer="alice", reviewer="bob", owned_path="src/m1/real.py")
    drive(mission, "WP02", "T2", implementer="claude", reviewer="bob", owned_path=None)
    drive(mission, "WP03", "T3", implementer="claude", reviewer="claude", owned_path="src/m3/real.py")
    drive(mission, "WP04", "T4", implementer="alice", reviewer="bob", owned_path=None)
    before = lanes_of(mission)
    assert all(before.get(wp) == "approved" for wp in ("WP01", "WP02", "WP03", "WP04")), f"fixture: every WP must reach approved; lanes={before}"
    accept(mission)
    main_before = _git(mission.repo, "rev-parse", "main")

    consolidated = _sk(mission, "consolidate", "--mission", mission.slug)
    output = consolidated.stdout + consolidated.stderr

    assert consolidated.returncode != 0, f"a hollow or self-approved WP must not consolidate. output:\n{output[-3000:]}"
    assert _BANNER not in output, f"the integrity banner must never print on a refusal. output:\n{output[-3000:]}"
    assert "IMPLEMENTATION_MISSING: WP02" in output, output[-3000:]
    assert "REVIEW_NOT_INDEPENDENT: WP03" in output, output[-3000:]
    assert "IMPLEMENTATION_MISSING: WP04" in output, output[-3000:]
    assert "IMPLEMENTATION_MISSING: WP01" not in output and "REVIEW_NOT_INDEPENDENT: WP01" not in output, output[-3000:]
    assert "SINGLE_BRANCH_" not in output, "lanes/coord refusals use the neutral codes"
    after = lanes_of(mission)
    assert not any(after.get(wp) == "done" for wp in ("WP01", "WP02", "WP03", "WP04")), f"nothing may land done; lanes={after}"
    assert _git(mission.repo, "rev-parse", "main") == main_before, "the refusal happens before any branch moves"
    assert not on_target(mission, "tools/check.sh")
    assert not on_target(mission, research)


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_real_work_with_independent_review_consolidates_clean(tmp_path: Path, topology: str) -> None:
    mission = setup_mission(tmp_path, topology)
    research = f"kitty-specs/{mission.slug}/{_RESEARCH_FILE}"
    drive(mission, "WP01", "T1", implementer="alice", reviewer="bob", owned_path="src/m1/real.py")
    drive(mission, "WP02", "T2", implementer="claude", reviewer="bob", owned_path="tools/check.sh")
    drive(mission, "WP03", "T3", implementer="claude", reviewer="bob", owned_path="src/m3/real.py")
    drive(mission, "WP04", "T4", implementer="alice", reviewer="bob", owned_path=research)
    accept(mission)

    consolidated = _sk(mission, "consolidate", "--mission", mission.slug)
    output = consolidated.stdout + consolidated.stderr

    assert consolidated.returncode == 0, f"real work with an independent review must consolidate clean. output:\n{output[-3000:]}"
    after = lanes_of(mission)
    assert all(after.get(wp) == "done" for wp in ("WP01", "WP02", "WP03", "WP04")), f"every WP must land done; lanes={after}"
    assert on_target(mission, "tools/check.sh")
    assert on_target(mission, research)
