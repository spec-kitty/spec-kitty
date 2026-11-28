"""#7860 (FR-012, SC-006): ``consolidate`` lands a default Mission's planning work that sits only on its Mission branch.

Before a default Mission lands, its planning lane writes to its Mission branch, which a settled
``lanes_with_coord`` Mission checks out in the coordination worktree (operator ruling A'). The
planning work package's owned change therefore reaches the target only through ``consolidate``,
which lands the Mission branch; the reconciliation gate must accept it.

Both shapes run through the REAL CLI in an isolated HOME: every work package is implemented where
``implement`` says (code lanes in their lane worktrees, the planning work package in the
coordination worktree), moved into review unforced, reviewed by an independent reviewer and
approved; then ``accept`` and ``consolidate``.

* Shape A (:func:`test_planning_work_inside_the_mission_directory_lands`) is a CONTROL, not
  FR-012 evidence: the owned file lives in ``kitty-specs/<slug>/research/``, which the
  reconciliation gate counts as bookkeeping, so it passes with or without a planning-lane fix.
* Shape B (:func:`test_pre_7816_planning_work_outside_the_mission_directory_lands`) is the pre-#7816
  shape: the planning work package owns ``curation/apply_curation.py``, outside ``kitty-specs/``.
  A fresh ``finalize-tasks`` cannot produce it (``ownership/kind_normalisation.py`` records such a
  work package as ``code_change`` with its own lane, #7809/#7816), so the fixture builds it the way
  a Mission finalized before #7816 recorded it: after ``finalize-tasks`` it moves the work package
  into ``lane-planning`` in ``lanes.json``, lists it in ``planning_artifact_wps``, sets its task
  file back to ``execution_mode: planning_artifact`` and commits that on the Mission branch, before
  any work package is claimed. The rebuilt shape is asserted before the CLI is driven.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

# Each case drives ~50 real CLI calls over four work packages plus a consolidation; the default
# budget is too tight on a loaded runner, so the cases carry their own (pytest.ini: mark, never raise the default).
pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1500)]

_CLI = [sys.executable, "-m", "specify_cli"]
_BANNER = "Reconciliation verified"
_PLANNING_LANE = "lane-planning"
_RESEARCH = "kitty-specs/{slug}/research/notes.md"
_CURATION = "curation/apply_curation.py"
_CODE_WPS = (("WP01", "T1", "src/m1/**", "src/m1/real.py"), ("WP03", "T3", "src/m3/**", "src/m3/real.py"), ("WP04", "T4", "src/m4/**", "src/m4/real.py"))
#: The files the CLI writes in the Mission directory; an owned file is never staged by the fixture's bookkeeping.
_TOOL_WRITTEN = (
    "status.events.jsonl",
    "status.json",
    "meta.json",
    "lanes.json",
    "analysis-report.md",
    "acceptance-matrix.json",
    "issue-matrix.json",
    "decisions",
    "tasks.md",
    "tasks",
)
_WORKSPACE_LINE = re.compile(r"Workspace:\s+(?:cd\s+)?(\S+)")


@dataclass(frozen=True)
class _Mission:
    repo: Path
    env: dict[str, str]
    slug: str
    mission_branch: str
    coord: Path

    @property
    def feature_dir(self) -> Path:
        return self.coord / "kitty-specs" / self.slug


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
        # Wide enough that rich never wraps a SHA, a branch or a phrase the assertions read.
        COLUMNS="500",
    )
    for key in ("home", "xc", "xcache", "xd"):
        (home / key).mkdir(parents=True, exist_ok=True)
    return env


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _sk(mission: _Mission | tuple[Path, dict[str, str]], *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    repo, env = (mission.repo, mission.env) if isinstance(mission, _Mission) else mission
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=600)
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


def _checkout_of(repo: Path, branch: str) -> Path:
    current: Path | None = None
    for line in _git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current = Path(line.removeprefix("worktree "))
        elif line == f"branch refs/heads/{branch}" and current is not None:
            return current
    raise AssertionError(f"fixture: no checkout of {branch}")


def _commit_bookkeeping(mission: _Mission) -> None:
    """Commit only the CLI-written files of the Mission directory, in the coordination worktree."""
    base = mission.feature_dir
    paths = [f"kitty-specs/{mission.slug}/{name}" for name in _TOOL_WRITTEN if (base / name).exists()]
    if paths:
        _git(mission.coord, "add", "--", *paths)
    if _git(mission.coord, "diff", "--cached", "--name-only"):
        _git(mission.coord, "commit", "-qm", "status residue")


def setup_mission(tmp_path: Path, planning_owned: str) -> _Mission:
    """A default Mission (no ``--topology``): code WP01/WP03/WP04 and planning WP02 owning *planning_owned*."""
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
    owned = planning_owned.format(slug=slug)
    fd = repo / "kitty-specs" / slug
    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    wps = (*((wp, t, o) for wp, t, o, _p in _CODE_WPS), ("WP02", "T2", owned))
    sections = "".join(f"## Work Package {wp}: {wp}\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] {t} do\n\n" for wp, t, _o in sorted(wps))
    (fd / "tasks.md").write_text(f"# Tasks\n\n{sections}", encoding="utf-8")
    for wp, subtask, path in wps:
        (fd / "tasks" / f"{wp}-work.md").write_text(_wp_file(wp, subtask, path, planning=wp == "WP02"), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    mission_branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    _sk((repo, env), "agent", "mission", "finalize-tasks", "--mission", slug, "--json", check=True)
    mission = _Mission(repo, env, slug, mission_branch, _checkout_of(repo, mission_branch))
    meta = json.loads((mission.feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert (meta.get("topology"), meta.get("topology_source")) == ("lanes_with_coord", "default"), f"fixture: a default lanes_with_coord Mission; meta={meta}"
    # Review 10: the planning lane's taint walk starts only at a recorded Mission base; the CLI records it at create (#7560).
    assert meta.get("mission_base_sha") == _git(repo, "rev-parse", "main"), f"fixture: the CLI records the Mission base; meta={meta}"
    assert mission.coord != repo, "fixture: the Mission branch is checked out in the coordination worktree"
    (tmp_path / "analysis.md").write_text("# Analysis\n\nNo blocking findings.\n", encoding="utf-8")
    _sk(mission, "agent", "mission", "record-analysis", "--mission", slug, "--input-file", str(tmp_path / "analysis.md"), check=True)
    _commit_bookkeeping(mission)
    return mission


def _rebuild_pre_7816_planning_lane(mission: _Mission) -> None:
    """Record WP02 in ``lane-planning`` as a Mission finalized before #7816 did (see the module docstring)."""
    lanes_path = mission.feature_dir / "lanes.json"
    manifest = json.loads(lanes_path.read_text(encoding="utf-8"))
    lanes = [lane for lane in manifest["lanes"] if lane["wp_ids"] != ["WP02"]]
    planning = next((lane for lane in lanes if lane["lane_id"] == _PLANNING_LANE), None)
    if planning is None:
        planning = {"lane_id": _PLANNING_LANE, "wp_ids": [], "write_scope": [], "predicted_surfaces": [], "depends_on_lanes": [], "parallel_group": 0}
        lanes.append(planning)
    planning["wp_ids"] = sorted({*planning["wp_ids"], "WP02"})
    planning["write_scope"] = sorted({*planning["write_scope"], _CURATION})
    manifest["lanes"] = lanes
    manifest["planning_artifact_wps"] = sorted({*manifest.get("planning_artifact_wps", []), "WP02"})
    lanes_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    task = next((mission.feature_dir / "tasks").glob("WP02-*.md"))
    text = task.read_text(encoding="utf-8")
    text = re.sub(r"^execution_mode: .*$", "execution_mode: planning_artifact", text, count=1, flags=re.MULTILINE)
    if "execution_mode:" not in text:
        text = text.replace("work_package_id: WP02\n", "work_package_id: WP02\nexecution_mode: planning_artifact\n", 1)
    task.write_text(text, encoding="utf-8")
    _git(mission.coord, "add", "--", f"kitty-specs/{mission.slug}/lanes.json", str(task.relative_to(mission.coord)))
    _git(mission.coord, "commit", "-qm", "fixture: WP02 recorded in lane-planning, as before #7816")
    rebuilt = json.loads(lanes_path.read_text(encoding="utf-8"))
    by_lane = {lane["lane_id"]: lane["wp_ids"] for lane in rebuilt["lanes"]}
    assert "WP02" in by_lane[_PLANNING_LANE], f"fixture: WP02 sits in lane-planning; lanes={by_lane}"
    assert sum("WP02" in wps for wps in by_lane.values()) == 1, f"fixture: WP02 in exactly one lane; lanes={by_lane}"
    assert "execution_mode: planning_artifact" in task.read_text(encoding="utf-8")


def _implement(mission: _Mission, wp: str, implementer: str) -> Path:
    out = _sk(mission, "agent", "action", "implement", wp, "--agent", implementer, "--mission", mission.slug, check=True)
    found = _WORKSPACE_LINE.search(out.stdout + out.stderr)
    assert found is not None, f"implement must name the workspace. output:\n{(out.stdout + out.stderr)[-3000:]}"
    _commit_bookkeeping(mission)
    return Path(found.group(1))


def drive(mission: _Mission, wp: str, subtask: str, owned_path: str, *, implementer: str = "alice", reviewer: str = "bob") -> Path:
    """Implement *wp* where ``implement`` says, move it into review unforced, review and approve it; return the workspace."""
    slug = mission.slug
    workspace = _implement(mission, wp, implementer)
    target = workspace / owned_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"# {wp}\nVALUE = 1\n", encoding="utf-8")
    _git(workspace, "add", "--", owned_path)
    _git(workspace, "commit", "-qm", f"feat({wp}): implement")
    _sk(mission, "agent", "tasks", "mark-status", subtask, "--status", "done", "--mission", slug)
    _commit_bookkeeping(mission)
    _sk(mission, "agent", "tasks", "move-task", wp, "--to", "for_review", "--agent", implementer, "--note", "done", "--mission", slug, check=True)
    _sk(mission, "agent", "action", "review", wp, "--agent", reviewer, "--mission", slug, check=True)
    _sk(mission, "agent", "tasks", "move-task", wp, "--to", "approved", "--agent", reviewer, "--note", "lgtm", "--force", "--mission", slug, check=True)
    _commit_bookkeeping(mission)
    return workspace


def lanes_of(mission: _Mission) -> dict[str, str]:
    status = _sk(mission, "agent", "tasks", "status", "--mission", mission.slug, "--json")
    try:
        return {w["id"]: w["lane"] for w in json.loads(status.stdout)["work_packages"]}
    except (ValueError, KeyError, TypeError):
        return {"<unparsed>": status.stdout[-400:]}


def accept_and_consolidate(mission: _Mission) -> subprocess.CompletedProcess[str]:
    _sk(mission, "agent", "acceptance-verdict", "--mission", mission.slug, "--criterion", "FR-001", "--result", "pass", "--actor", "operator", "--evidence", "qa")
    _commit_bookkeeping(mission)
    accepted = _sk(mission, "accept", "--mission", mission.slug, "--json", "--lenient")
    assert "IMPLEMENTATION_MISSING" not in accepted.stdout + accepted.stderr, (accepted.stdout + accepted.stderr)[-3000:]
    _commit_bookkeeping(mission)
    return _sk(mission, "consolidate", "--mission", mission.slug)


def on_target(mission: _Mission, relpath: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"main:{relpath}"], cwd=mission.repo, capture_output=True).returncode == 0


def _drive_all_and_consolidate(mission: _Mission, planning_owned: str) -> subprocess.CompletedProcess[str]:
    for wp, subtask, _glob, path in _CODE_WPS:
        drive(mission, wp, subtask, path)
    planning_workspace = drive(mission, "WP02", "T2", planning_owned)
    assert planning_workspace.resolve() == mission.coord.resolve(), "the planning work package is implemented in the coordination worktree"
    assert not on_target(mission, planning_owned), "fixture: the planning work sits on the Mission branch only before the landing"
    before = lanes_of(mission)
    assert all(before.get(wp) == "approved" for wp in ("WP01", "WP02", "WP03", "WP04")), f"fixture: every WP must reach approved; lanes={before}"
    return accept_and_consolidate(mission)


def _assert_landed(mission: _Mission, consolidated: subprocess.CompletedProcess[str], planning_owned: str) -> None:
    output = consolidated.stdout + consolidated.stderr
    assert consolidated.returncode == 0, f"planning work on the Mission branch must consolidate clean. output:\n{output[-4000:]}"
    assert _BANNER in output, f"the reconciliation gate must pass. output:\n{output[-4000:]}"
    after = lanes_of(mission)
    assert all(after.get(wp) == "done" for wp in ("WP01", "WP02", "WP03", "WP04")), f"every WP must land done; lanes={after}"
    assert on_target(mission, planning_owned), "the planning work must be on the target after the landing"
    for _wp, _t, _glob, path in _CODE_WPS:
        assert on_target(mission, path), f"{path} must be on the target"


def test_planning_work_inside_the_mission_directory_lands(tmp_path: Path) -> None:
    """Shape A (control): the owned file is inside ``kitty-specs/<slug>/``."""
    mission = setup_mission(tmp_path, _RESEARCH)
    research = _RESEARCH.format(slug=mission.slug)

    consolidated = _drive_all_and_consolidate(mission, research)

    _assert_landed(mission, consolidated, research)


def test_pre_7816_planning_work_outside_the_mission_directory_lands(tmp_path: Path) -> None:
    """Shape B (FR-012 evidence): the planning work package owns ``curation/apply_curation.py`` in ``lane-planning``."""
    mission = setup_mission(tmp_path, _CURATION)
    _rebuild_pre_7816_planning_lane(mission)

    consolidated = _drive_all_and_consolidate(mission, _CURATION)

    _assert_landed(mission, consolidated, _CURATION)
