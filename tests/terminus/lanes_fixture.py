"""LANES-topology (no coordination branch) real-CLI fixture builder.

Port of the live-verified reference
``kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/research/lanes_fixture_reference.py.txt``.
It reuses the coord builder's primitives from :mod:`tests.terminus.conftest`
(which #5359 also edits, so every private helper is bound in ONE adapter block
below -- a rename there breaks exactly one place) and returns the same
:class:`~tests.terminus.conftest.CoordMission` shape, with ``coord_branch``
holding the MISSION branch, so ``plant_canceled_commit`` / ``run_terminus``
work unchanged.

Two live-verified traps:

* **Protected target (#5385).** A LANES ``consolidate`` whose target is a
  protected branch such as ``main`` is refused up front with the policy's
  ``PROTECTED_BRANCH_REFUSED`` before any branch moves (its ``done`` bookkeeping
  would land on ``main``). The builder therefore defaults to ``develop`` but does
  NOT forbid ``main`` (the #5385 repros and WP05's protected-``main`` claim case
  need it).
* **No ``agent:`` frontmatter (asserted).** A WP carrying ``agent:`` makes
  ``_run_birth_cutover`` seed claim events onto the target log after ``done``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from specify_cli.lanes.branch_naming import mission_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from tests.terminus import conftest as _harness
from tests.terminus.conftest import CoordMission, PlantedChange, git_rev

# --- single adapter over the conftest private helpers (#5359 rename => one edit) ---
_run = _harness._run
_git = _harness._git
_approve_events = _harness._approve_events
_now_iso = _harness._now_iso
_STATUS_EVENTS_FILENAME = _harness._STATUS_EVENTS_FILENAME
_event = _harness._event
_cancel_event = _harness._cancel_event
_plant_change = _harness._plant_change
_APPROVE_CHAIN = _harness._APPROVE_CHAIN
# -----------------------------------------------------------------------------------

_PLANNING_LANE_ID = "lane-planning"
_GIT_IDENTITY = (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false"))


def _wp_file_text(wp: str) -> str:
    text = f"---\nwork_package_id: {wp}\ntitle: {wp} work\n---\n# {wp}\n"
    assert "agent:" not in text, "WP frontmatter must not carry `agent:` (birth-cutover seeds claim events after done)"
    return text


def _code_lanes(wps: Sequence[str]) -> list[ExecutionLane]:
    return [
        ExecutionLane(
            lane_id=f"lane-{chr(ord('a') + i)}",
            wp_ids=(wp,),
            write_scope=(f"src/pkg/{wp.lower()}.py",),
            predicted_surfaces=("code",),
            depends_on_lanes=(),
            parallel_group=0,
        )
        for i, wp in enumerate(wps)
    ]


def _planning_lane(slug: str, wp: str, *, depends_on_code: bool) -> ExecutionLane:
    return ExecutionLane(
        lane_id=_PLANNING_LANE_ID,
        wp_ids=(wp,),
        write_scope=(f"kitty-specs/{slug}/**",),
        predicted_surfaces=("planning",),
        depends_on_lanes=("lane-a",) if depends_on_code else (),
        parallel_group=1 if depends_on_code else 0,
    )


def _init_repo(repo: Path, target_branch: str) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", target_branch, str(repo)])
    for key, value in _GIT_IDENTITY:
        _git(repo, "config", key, value)
    (repo / "README.md").write_text("init\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")


def _write_meta(m: CoordMission, target_branch: str) -> None:
    meta = {
        "mission_slug": m.slug,
        "mission_id": m.mission_id,
        "mid8": m.mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "topology": "lanes",
        "purpose_tldr": "lanes fixture",
        "purpose_context": "lanes fixture",
    }
    (m.feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")


def _cut_lane_branches(m: CoordMission, wps: Sequence[str], target_branch: str) -> None:
    for i, wp in enumerate(wps):
        lane_branch = f"kitty/mission-{m.slug}-lane-{chr(ord('a') + i)}"
        _git(m.repo, "branch", lane_branch, m.coord_branch)
        _git(m.repo, "checkout", "-q", lane_branch)
        code = m.repo / "src" / "pkg" / f"{wp.lower()}.py"
        code.parent.mkdir(parents=True, exist_ok=True)
        code.write_text(f"def {wp.lower()}() -> int:\n    return {i}\n")
        _git(m.repo, "add", str(code))
        _git(m.repo, "commit", "-qm", f"feat({m.slug}): {wp} approved code")
        _git(m.repo, "checkout", "-q", target_branch)
        m.lane_branches[wp] = lane_branch


def build_lanes_mission(
    tmp_path: Path,
    *,
    wps: Sequence[str] = ("WP01",),
    target_branch: str = "develop",
    mid8: str = "01M5318L",
    with_planning_lane_wp: bool = False,
    planning_depends_on_code: bool = True,
    approve_planning_wp: bool = True,
) -> CoordMission:
    """Materialize a real LANES-topology mission (no coordination branch).

    ``meta.json`` carries ``"topology": "lanes"`` and no ``coordination_branch``;
    ``lanes.json``'s ``mission_branch`` is ``mission_branch_name(slug, mission_id=...)``
    and that branch is cut at the bootstrap commit, with each code lane cut from it.

    Planning-lane variant (WP05): ``with_planning_lane_wp=True`` adds a
    ``lane-planning`` lane owning the next WP id (``WP{n+1}``), which resolves to
    the target branch (no lane branch is created). ``planning_depends_on_code``
    makes it depend on ``lane-a``; ``approve_planning_wp=False`` leaves the
    planning WP ``planned`` (claimable) instead of approved.
    """
    mid8 = mid8.upper()
    mission_id = (mid8 + "0" * 26)[:26]
    slug = f"terminus-{mid8}"
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    mission_branch = mission_branch_name(slug, mission_id=mission_id)
    m = CoordMission(
        repo=repo,
        home=home,
        feature_dir=repo / "kitty-specs" / slug,
        slug=slug,
        mission_id=mission_id,
        mid8=mid8,
        coord_branch=mission_branch,
        target_branch=target_branch,
    )
    _init_repo(repo, target_branch)
    (m.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(m, target_branch)

    lanes = _code_lanes(wps)
    planning_wp = f"WP{len(wps) + 1:02d}"
    if with_planning_lane_wp:
        lanes.append(_planning_lane(slug, planning_wp, depends_on_code=planning_depends_on_code))
    write_lanes_json(
        m.feature_dir,
        LanesManifest(
            version=1,
            mission_slug=slug,
            mission_id=mission_id,
            mission_branch=mission_branch,
            target_branch=target_branch,
            lanes=lanes,
            computed_at=_now_iso(),
            computed_from="lanes-scratch-fixture",
        ),
    )

    all_wps = [*wps, *([planning_wp] if with_planning_lane_wp else [])]
    events: list[dict[str, object]] = []
    for wp in all_wps:
        (m.feature_dir / "tasks" / f"{wp}-work.md").write_text(_wp_file_text(wp))
        if wp != planning_wp or approve_planning_wp:
            events.extend(_approve_events(m, wp))
    (m.feature_dir / _STATUS_EVENTS_FILENAME).write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", f"chore({slug}): bootstrap lanes mission")
    _git(repo, "branch", mission_branch)
    _cut_lane_branches(m, wps, target_branch)
    return m


_DEP_CANCELED_PATH = "src/alpha/mod.py"
_DEP_DEPENDENT_PATH = "src/beta/mod.py"


def _dependency_lanes() -> list[ExecutionLane]:
    """``lane-a`` (WP01, no deps) and ``lane-b`` (WP02, depends on ``lane-a``)."""
    return [
        ExecutionLane(
            lane_id=lane_id,
            wp_ids=(wp,),
            write_scope=(scope,),
            predicted_surfaces=("code",),
            depends_on_lanes=deps,
            parallel_group=group,
        )
        for lane_id, wp, scope, deps, group in (
            ("lane-a", "WP01", "src/alpha/**", (), 0),
            ("lane-b", "WP02", "src/beta/**", ("lane-a",), 1),
        )
    ]


def _stamped(m: CoordMission, wp: str, frm: str, to: str, worktree: Path) -> dict[str, object]:
    return _event(m, wp, frm, to, policy_metadata={"lane_head": git_rev(worktree, "HEAD")})


def _approved_session(m: CoordMission, wp: str, worktree: Path, path: str) -> list[dict[str, object]]:
    """Claim, commit *path* in *worktree*, then walk *wp* to ``approved``; every event is lane-head stamped."""
    events = [_stamped(m, wp, frm, to, worktree) for frm, to in _APPROVE_CHAIN[:2]]
    _plant_change(worktree, PlantedChange(path, f"{wp} = 'work'\n"), message=f"feat({m.slug}): {wp} work")
    events.extend(_stamped(m, wp, frm, to, worktree) for frm, to in _APPROVE_CHAIN[2:])
    return events


def build_lanes_mission_canceled_dependency(tmp_path: Path, *, cancel_dependency: bool, mid8: str = "01M5569A") -> CoordMission:
    """LANES mission where approved ``WP02`` (``lane-b``) depends on ``WP01`` (``lane-a``) (#5569).

    Both lane worktrees come from the REAL allocator
    (:func:`~specify_cli.lanes.worktree_allocator.allocate_lane_worktree`), so
    ``lane-b`` is cut from the mission branch and the allocator's own
    dependency merge (no ``--no-ff``) fast-forwards ``lane-a``'s WP01 commit onto
    ``lane-b``'s first-parent spine -- never a hand-built merge. ``WP01``
    commits ``src/alpha/mod.py`` and is approved; with ``cancel_dependency`` it
    is then canceled with operator provenance (``lane-a`` holds only a canceled
    WP), otherwise it stays approved (positive control).
    """
    mid8 = mid8.upper()
    mission_id = (mid8 + "0" * 26)[:26]
    slug = f"terminus-{mid8}"
    mission_branch = mission_branch_name(slug, mission_id=mission_id)
    m = CoordMission(
        repo=tmp_path / "repo",
        home=tmp_path / "home",
        feature_dir=tmp_path / "repo" / "kitty-specs" / slug,
        slug=slug,
        mission_id=mission_id,
        mid8=mid8,
        coord_branch=mission_branch,
        target_branch="develop",
    )
    m.home.mkdir(parents=True, exist_ok=True)
    _init_repo(m.repo, m.target_branch)
    (m.repo / ".gitignore").write_text(".worktrees/\n")
    (m.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(m, m.target_branch)
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission_id,
        mission_branch=mission_branch,
        target_branch=m.target_branch,
        lanes=_dependency_lanes(),
        computed_at=_now_iso(),
        computed_from="terminus-red-first-fixture-canceled-dependency",
    )
    write_lanes_json(m.feature_dir, manifest)
    for wp in ("WP01", "WP02"):
        (m.feature_dir / "tasks" / f"{wp}-work.md").write_text(_wp_file_text(wp))
    _git(m.repo, "add", ".")
    _git(m.repo, "commit", "-qm", f"chore({slug}): bootstrap canceled-dependency mission")
    _git(m.repo, "branch", mission_branch)

    lane_a, branch_a = allocate_lane_worktree(m.repo, slug, "WP01", manifest)
    events = _approved_session(m, "WP01", lane_a, _DEP_CANCELED_PATH)
    lane_b, branch_b = allocate_lane_worktree(m.repo, slug, "WP02", manifest)
    events.extend(_approved_session(m, "WP02", lane_b, _DEP_DEPENDENT_PATH))
    if cancel_dependency:
        events.append(_cancel_event(m, "WP01", from_lane="approved", policy_metadata={"lane_head": git_rev(lane_a, "HEAD")}))
        m.canceled_wps.add("WP01")
    m.lane_branches.update({"WP01": branch_a, "WP02": branch_b})

    events_path = m.feature_dir / _STATUS_EVENTS_FILENAME
    events_path.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in events))
    _git(m.repo, "add", ".")
    _git(m.repo, "commit", "-qm", f"chore({slug}): canceled-dependency events")
    _git(m.repo, "branch", "-f", mission_branch, m.target_branch)
    return m
