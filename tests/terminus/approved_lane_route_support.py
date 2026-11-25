"""The approved-lane re-review route, driven through the real CLI (FR-008, Mission ``approved-lane-resolution-route``).

One fixture builder for every scenario of the route, with its preconditions asserted inside the
builder so no test can pass on a mis-built fixture:

* :func:`build_conflicting_lanes_mission` -- two approved, independent code lanes (``WP01`` on
  ``lane-a``, ``WP02`` on ``lane-b``) that edit ADJACENT lines of one shared file,
  :data:`SHARED_PATH`, seeded on the target before the lanes are cut: ``lane-a`` changes line 3,
  ``lane-b`` changes line 4, so stock git conflicts on them. Both topologies (``"coord"``: a
  coordination branch; ``"lanes"``: the Mission branch, no coordination branch). Lanes are cut by
  the real ``allocate_lane_worktree`` and every lifecycle transition runs through the production
  status shell, by distinct identities (:data:`IMPLEMENTER` implements, :data:`REVIEWER` approves).
* :func:`add_dependent_and_control_lanes` -- the three-lane variants' shape (WP14): ``lane-c``
  (``WP03``) depends on ``lane-b`` and rewrites line 4 of :data:`SHARED_PATH` again (``GAMMA``, the
  line ``lane-b`` changed), so its approved content overlaps ``lane-b``'s and it conflicts with the
  Mission branch once ``lane-a``'s line 3 lands there through ``lane-b``'s resolution (line 3 and
  line 4 are adjacent); ``lane-d`` (``WP04``) edits only :data:`OTHER_PATH`, overlaps nothing and is
  never named as a sibling (the exact-set control).
* :func:`run_route` -- consolidate refuses ``lane-b`` as stale and prints the route; the operator
  runs the printed commands (reopen, re-enter, ``--incorporate``), resolves and commits the merge
  by hand, hands the work package back, and an independent reviewer claims the review through
  ``agent action review`` and approves it, unforced, through ``move-task``. Its stages are public
  too (:func:`refuse_as_stale`, :func:`follow_route_to_review`, :func:`independent_approval`) for
  the negative controls that stop part way.
* SC-003 helpers: :func:`branch_reflog_lengths` and :func:`assert_no_branch_moved` prove "no branch
  moved" by reflog lengths plus "no pre-mutation snapshot written", never by end-state SHAs (a
  land-then-rollback also ends with identical SHAs). :func:`consolidate_in_process` and
  :func:`one_shot_gate_fail` (the pattern of ``test_rollback_record_rebaseline.py``, copied, not
  imported) make the discriminating control: a run that lands lanes and then fails at the gate.

Identities are ``tool::profile`` strings (no model recorded on either side), distinct in their
profile segment, so the review is independent under ``status.actor_identities_independent``.

This module is FROZEN once the work package that created it (WP12) is approved: WP14 imports it
and must not edit it; anything more lives in WP14's own test module.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pytest
from typer.testing import CliRunner

from kernel.git.listing import merge_tree
from specify_cli.consolidation.approved_bound import approval_stamp
from specify_cli.consolidation.reconciliation_verifier import Divergence, MergeOutcomeVerifier, VerifyResult
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.branch_naming import mission_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status import StatusEvent, read_status_events, resolve_status_read
from specify_cli.status.models import ReviewResult
from tests.terminus.conftest import CoordMission, git_rev, pin_planning_commit, run_terminus
from tests.terminus.mixed_lane_support import collapse, transition
from tests.terminus.rollback_harness import reflog_shas, state_path

Topology = Literal["coord", "lanes"]
Strategy = Literal["squash", "merge"]

#: The implementer and the independent reviewer (#6715): distinct ``tool::profile`` identities.
IMPLEMENTER = "claude::implementer-ivan"
REVIEWER = "claude::reviewer-renata"

LANE_A = "lane-a"
LANE_B = "lane-b"
LANE_C = "lane-c"
LANE_D = "lane-d"
SHARED_PATH = "src/pkg/shared.py"
OTHER_PATH = "src/pkg/other.py"

_SEED_LINES = (
    '"""Shared module of the approved-lane route fixture."""',
    "ALPHA = 0",
    "BETA = 0",
    "GAMMA = 0",
    "DELTA = 0",
    "EPSILON = 0",
)
#: ``lane-a``'s change (line 3) and ``lane-b``'s change (line 4): adjacent, so git conflicts.
LANE_A_LINE = "BETA = 1  # lane-a"
LANE_B_LINE = "GAMMA = 2  # lane-b"
#: ``lane-c`` rewrites ``lane-b``'s line 4 again (WP14's dependent lane).
LANE_C_LINE = "GAMMA = 3  # lane-c"
#: The resolution's line from neither side (the residual control and N1's ``novel_line`` case).
NOVEL_LINE = 'NOVEL = "added by the resolution, from neither side"'
OTHER_TEXT = "def other() -> int:\n    return 4\n"

RECONCILIATION_VERIFIED = "Reconciliation verified"
RESOLUTION_MERGE_UNREVIEWED = "RESOLUTION_MERGE_UNREVIEWED"
_WIDE = {"COLUMNS": "1000"}
_SPEC_KITTY = "spec-kitty"
_AGENT_PLACEHOLDER = "<agent>"
_FILE_PLACEHOLDER = "<file>"
#: Wording ``implement`` / ``move-task`` print when they refuse an approved work package (SC-001).
APPROVED_REFUSALS = ("cannot claim", "is already in lane: approved", "refuses an approved", "--force")
_ANALYSIS = (
    "---\nschema: analysis-findings/v1\nfindings: []\ncounts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n"
    "# Specification Analysis Report\n\nNo blocking findings.\n"
)


def _text(lines: Sequence[str]) -> str:
    return "\n".join(lines) + "\n"


def _with_line(index: int, line: str, base: Sequence[str] = _SEED_LINES) -> list[str]:
    changed = list(base)
    changed[index] = line
    return changed


SEED_TEXT = _text(_SEED_LINES)
LANE_A_TEXT = _text(_with_line(2, LANE_A_LINE))
LANE_B_TEXT = _text(_with_line(3, LANE_B_LINE))
#: The operator's resolution that keeps both sides' lines.
RESOLVED_TEXT = _text(_with_line(3, LANE_B_LINE, _with_line(2, LANE_A_LINE)))
#: The resolution with a line from neither side, after ``lane-b``'s line.
NOVEL_TEXT = RESOLVED_TEXT.replace(f"{LANE_B_LINE}\n", f"{LANE_B_LINE}\n{NOVEL_LINE}\n")


# --------------------------------------------------------------------------- plain git


def git(cwd: Path, *args: str) -> str:
    """Run git in *cwd* (raises on failure) and return its stripped stdout."""
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True).stdout.strip()


def _commit_file(checkout: Path, rel_path: str, text: str, message: str) -> str:
    target = checkout / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    git(checkout, "add", rel_path)
    git(checkout, "commit", "-qm", message)
    return git_rev(checkout, "HEAD")


def show(repo: Path, ref: str, rel_path: str) -> str:
    """The bytes of *rel_path* at *ref* (raises when absent)."""
    return subprocess.run(["git", "show", f"{ref}:{rel_path}"], cwd=str(repo), check=True, capture_output=True, text=True).stdout


# --------------------------------------------------------------------------- HOME

_HOME_TEMPLATE: list[Path] = []


def _cli_home_template() -> Path:
    """A HOME the CLI has already bootstrapped, built once per test process (a copy costs well under a second)."""
    if not _HOME_TEMPLATE:
        template = Path(tempfile.mkdtemp(prefix="route-home-"))
        atexit.register(shutil.rmtree, template, ignore_errors=True)
        env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
        env.update({"HOME": str(template), "SPEC_KITTY_NO_UPGRADE_CHECK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src")})
        subprocess.run([sys.executable, "-m", "specify_cli", "consolidate", "--help"], cwd=str(template), env=env, capture_output=True, check=True, timeout=180)
        _HOME_TEMPLATE.append(template)
    return _HOME_TEMPLATE[0]


# --------------------------------------------------------------------------- the Mission


@dataclass
class RouteMission:
    """The built route Mission plus every fact a scenario needs."""

    mission: CoordMission
    topology: Topology
    implementer: str
    reviewer: str
    checkouts: dict[str, Path]
    lane_branches: dict[str, str]
    wp_of_lane: dict[str, str]
    shared_path: str = SHARED_PATH
    side_texts: dict[str, str] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return self.mission.slug

    @property
    def repo(self) -> Path:
        return self.mission.repo


@dataclass(frozen=True)
class RouteOutcome:
    """What :func:`run_route` observed: the stale refusal, the printed route, the resolution merge and the re-approval."""

    refusal_output: str
    reopen_command: list[str]
    printed: list[list[str]]
    resolution_merge: str
    review_output: str
    review_prompt: str
    approval: StatusEvent


def _wp_file(wp: str, dependencies: Sequence[str] = ()) -> str:
    deps = "[" + ", ".join(dependencies) + "]"
    return f"---\nwork_package_id: {wp}\ntitle: {wp} work\ndependencies: {deps}\nsubtasks: []\nowned_files:\n  - src/**\n---\n# {wp}\n"


def _lane(lane_id: str, wp: str, depends_on: tuple[str, ...] = ()) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=(wp,),
        write_scope=("src/**",),
        predicted_surfaces=("code",),
        depends_on_lanes=depends_on,
        parallel_group=1 if depends_on else 0,
    )


def _meta(mission: CoordMission, topology: Topology) -> dict[str, object]:
    meta: dict[str, object] = {
        "mission_slug": mission.slug,
        "mission_id": mission.mission_id,
        "mid8": mission.mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": mission.target_branch,
        "purpose_tldr": "approved-lane re-review route",
        "purpose_context": "a reviewed resolution of an approved lane lands; an unreviewed one never does",
    }
    if topology == "coord":
        meta["coordination_branch"] = mission.coord_branch
    else:
        meta["topology"] = "lanes"
    return meta


def _new_mission(tmp_path: Path, topology: Topology, mid8: str) -> CoordMission:
    mid8 = mid8.upper()
    mission_id = (mid8 + "0" * 26)[:26]
    slug = f"route-{mid8}"
    target = "main" if topology == "coord" else "develop"
    branch = CoordinationWorkspace.branch_name(slug, mid8) if topology == "coord" else mission_branch_name(slug, mission_id=mission_id)
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    shutil.copytree(_cli_home_template(), home, dirs_exist_ok=True)
    return CoordMission(
        repo=repo,
        home=home,
        feature_dir=repo / "kitty-specs" / slug,
        slug=slug,
        mission_id=mission_id,
        mid8=mid8,
        coord_branch=branch,
        target_branch=target,
    )


def _init_repo(mission: CoordMission) -> None:
    """``git init``, the test identity, and one init commit holding the seeded shared file."""
    repo = mission.repo
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-qb", mission.target_branch, str(repo)], check=True, capture_output=True)
    for key, value in (("user.email", "route@test.invalid"), ("user.name", "Route Test"), ("commit.gpgsign", "false")):
        git(repo, "config", key, value)
    for rel_path, text in (("README.md", "init\n"), (".gitignore", ".worktrees/\n"), (SHARED_PATH, SEED_TEXT)):
        (repo / rel_path).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel_path).write_text(text, encoding="utf-8")
    git(repo, "add", "README.md", ".gitignore", SHARED_PATH)
    git(repo, "commit", "-qm", "init")
    with (repo / ".git" / "info" / "exclude").open("a", encoding="utf-8") as fh:
        fh.write(".kittify/derived/\n.kittify/workspaces/\n")


def _bootstrap(tmp_path: Path, topology: Topology, mid8: str) -> tuple[CoordMission, LanesManifest]:
    """Planning artifacts (two WPs, a ``lane-a``/``lane-b`` manifest, an empty event log) committed; the Mission branch cut."""
    mission = _new_mission(tmp_path, topology, mid8)
    _init_repo(mission)
    feature_dir = mission.feature_dir
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps(_meta(mission, topology), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = LanesManifest(
        version=1,
        mission_slug=mission.slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=[_lane(LANE_A, "WP01"), _lane(LANE_B, "WP02")],
        computed_at="2026-11-25T00:00:00+00:00",
        computed_from="approved-lane-route-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    pin_planning_commit(mission.repo, feature_dir)
    for wp in ("WP01", "WP02"):
        (feature_dir / "tasks" / f"{wp}-work.md").write_text(_wp_file(wp), encoding="utf-8")
    for name, text in (("spec.md", "# Spec\n\nFR-001.\n"), ("plan.md", "# Plan\n"), ("tasks.md", "# Tasks\n")):
        (feature_dir / name).write_text(text, encoding="utf-8")
    (feature_dir / "status.events.jsonl").write_text("", encoding="utf-8")
    git(mission.repo, "add", f"kitty-specs/{mission.slug}")
    git(mission.repo, "commit", "-qm", f"chore({mission.slug}): bootstrap approved-lane route mission")
    git(mission.repo, "branch", mission.coord_branch)
    if topology == "coord":
        CoordinationWorkspace.resolve(mission.repo, mission.slug, mission.mid8)
    return mission, read_lanes_json(feature_dir) or manifest


def approve_through_shell(mission: CoordMission, wp: str, *, reference: str) -> None:
    """Hand *wp* to review (implementer) and approve it (independent reviewer) through the production status shell."""
    transition(mission, wp, "for_review", actor=IMPLEMENTER, subtasks_complete=True)
    transition(mission, wp, "in_review", actor=REVIEWER)
    transition(
        mission, wp, "approved", actor=REVIEWER, review_ref=reference, review_result=ReviewResult(reviewer=REVIEWER, verdict="approved", reference=reference)
    )


def _implement_and_approve(mission: CoordMission, manifest: LanesManifest, wp: str, rel_path: str, text: str) -> tuple[Path, str]:
    for lane in ("planned", "claimed"):
        transition(mission, wp, lane, actor=IMPLEMENTER)
    checkout, branch = allocate_lane_worktree(mission.repo, mission.slug, wp, manifest)
    transition(mission, wp, "in_progress", actor=IMPLEMENTER)
    _commit_file(checkout, rel_path, text, f"feat({mission.slug}): {wp} edits {rel_path}")
    approve_through_shell(mission, wp, reference=f"review-{wp}")
    mission.lane_branches[wp] = branch
    return checkout, branch


def _record_analysis(mission: CoordMission) -> None:
    """The recorded analysis report every ``implement`` claim requires, committed on the target."""
    findings = mission.home / "analysis-input.md"
    findings.write_text(_ANALYSIS, encoding="utf-8")
    recorded = run_terminus(mission, ["agent", "mission", "record-analysis", "--mission", mission.slug, "--input-file", str(findings)])
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    git(mission.repo, "add", "kitty-specs")
    git(mission.repo, "commit", "-qm", "chore: record analysis", "--allow-empty")


def events(route: RouteMission) -> list[StatusEvent]:
    """The Mission's lane transitions, read through the one status read door (either topology)."""
    found: list[StatusEvent] = read_status_events(resolve_status_read(route.repo, route.slug))
    return found


def lane_of(route: RouteMission, wp_id: str) -> str:
    """*wp_id*'s current lane from the status events (the newest transition naming it)."""
    found = [event for event in events(route) if event.wp_id == wp_id]
    assert found, f"no status event names {wp_id}"
    return str(found[-1].to_lane)


def _assert_stamps_at_tips(route: RouteMission) -> None:
    log = events(route)
    for lane_id, wp in route.wp_of_lane.items():
        stamp = approval_stamp(log, wp)
        tip = git_rev(route.repo, route.lane_branches[lane_id])
        assert stamp == tip, f"fixture: {wp}'s newest approval stamp {stamp} must equal {lane_id}'s tip {tip}"
        assert lane_of(route, wp) == "approved", f"fixture: {wp} must be approved"


def build_conflicting_lanes_mission(tmp_path: Path, topology: Topology, *, mid8: str) -> RouteMission:
    """Two approved, independent lanes whose edits of :data:`SHARED_PATH` conflict (adjacent lines 3 and 4)."""
    mission, manifest = _bootstrap(tmp_path, topology, mid8)
    checkouts: dict[str, Path] = {}
    branches: dict[str, str] = {}
    for lane_id, wp, text in ((LANE_A, "WP01", LANE_A_TEXT), (LANE_B, "WP02", LANE_B_TEXT)):
        checkouts[lane_id], branches[lane_id] = _implement_and_approve(mission, manifest, wp, SHARED_PATH, text)
    _record_analysis(mission)
    route = RouteMission(
        mission=mission,
        topology=topology,
        implementer=IMPLEMENTER,
        reviewer=REVIEWER,
        checkouts=checkouts,
        lane_branches=branches,
        wp_of_lane={LANE_A: "WP01", LANE_B: "WP02"},
        side_texts={LANE_A: LANE_A_TEXT, LANE_B: LANE_B_TEXT},
    )
    conflict = merge_tree(route.repo, branches[LANE_B], branches[LANE_A])
    assert tuple(str(path) for path in conflict.conflicted) == (SHARED_PATH,), f"fixture: git must conflict on {SHARED_PATH}: {conflict}"
    _assert_stamps_at_tips(route)
    return route


def add_dependent_and_control_lanes(route: RouteMission) -> RouteMission:
    """Add ``lane-c`` (``WP03``, depends on ``lane-b``, rewrites line 4) and the independent ``lane-d`` (``WP04``, :data:`OTHER_PATH`)."""
    mission = route.mission
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    manifest.lanes = [*manifest.lanes, _lane(LANE_C, "WP03", (LANE_B,)), _lane(LANE_D, "WP04")]
    write_lanes_json(mission.feature_dir, manifest)  # keeps the recorded planning commit: the lanes' evidence windows stay put
    for wp, deps in (("WP03", ("WP02",)), ("WP04", ())):
        (mission.feature_dir / "tasks" / f"{wp}-work.md").write_text(_wp_file(wp, deps), encoding="utf-8")
    git(mission.repo, "checkout", "-q", mission.target_branch)
    git(mission.repo, "add", f"kitty-specs/{mission.slug}")
    git(mission.repo, "commit", "-qm", f"chore({mission.slug}): add the dependent and control lanes")
    manifest = read_lanes_json(mission.feature_dir) or manifest
    lane_c_text = show(route.repo, route.lane_branches[LANE_B], SHARED_PATH).replace(LANE_B_LINE, LANE_C_LINE)
    for lane_id, wp, rel_path, text in ((LANE_C, "WP03", SHARED_PATH, lane_c_text), (LANE_D, "WP04", OTHER_PATH, OTHER_TEXT)):
        route.checkouts[lane_id], route.lane_branches[lane_id] = _implement_and_approve(mission, manifest, wp, rel_path, text)
        route.wp_of_lane[lane_id] = wp
        route.side_texts[lane_id] = text
    recorded = read_lanes_json(mission.feature_dir)
    assert recorded is not None and next(lane for lane in recorded.lanes if lane.lane_id == LANE_C).depends_on_lanes == (LANE_B,)
    assert git(route.repo, "merge-base", "--is-ancestor", route.lane_branches[LANE_B], route.lane_branches[LANE_C]) == ""
    for lane_id in (LANE_A, LANE_B, LANE_C):
        changed = git(route.repo, "diff", "--name-only", f"{route.lane_branches[LANE_D]}...{route.lane_branches[lane_id]}").split()
        assert OTHER_PATH not in changed, f"fixture: {lane_id} must not touch {OTHER_PATH}"
    lane_d_paths = git(route.repo, "diff", "--name-only", f"{route.lane_branches[LANE_A]}...{route.lane_branches[LANE_D]}", "--", "src").split()
    assert lane_d_paths == [OTHER_PATH], f"fixture: lane-d changes only {OTHER_PATH}: {lane_d_paths}"
    _assert_stamps_at_tips(route)
    return route


# --------------------------------------------------------------------------- CLI


def cli(route: RouteMission, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``spec-kitty <args>`` for real in the Mission's repository (a wide console, so no line wraps)."""
    return run_terminus(route.mission, list(args), env=_WIDE)


def output(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout or "") + (result.stderr or "")


def consolidate(route: RouteMission, strategy: Strategy) -> tuple[int, str]:
    """A fresh ``consolidate`` run under *strategy*; its exit code and collapsed output."""
    result = cli(route, "consolidate", "--mission", route.slug, "--yes", "--strategy", strategy)
    return result.returncode, collapse(output(result))


def printed_commands(text: str) -> list[list[str]]:
    """Every printed line that is a ``spec-kitty`` command, ``shlex``-split, the leading ``spec-kitty`` dropped."""
    lines = [line.strip() for line in text.splitlines()]
    return [shlex.split(line)[1:] for line in lines if line.startswith(f"{_SPEC_KITTY} ")]


def reopen_command(text: str, wp_id: str) -> list[str]:
    """main's #7754 reopen command, printed inside the reopen sentence (it ends with a full stop)."""
    flat = collapse(text)
    lead = f"{_SPEC_KITTY} agent tasks move-task {wp_id} --to planned --review-feedback-file {_FILE_PLACEHOLDER} --mission "
    start = flat.find(lead)
    assert start != -1, f"no reopen command for {wp_id} in:\n{text}"
    mission_handle = flat[start + len(lead) :].split()[0].rstrip(".")
    return shlex.split(lead + mission_handle)[1:]


def _fill(argv: Sequence[str], agent: str, feedback: Path | None = None) -> list[str]:
    filled = [agent if arg == _AGENT_PLACEHOLDER else arg for arg in argv]
    return [str(feedback) if arg == _FILE_PLACEHOLDER and feedback is not None else arg for arg in filled]


def assert_no_approved_refusal(result: subprocess.CompletedProcess[str], argv: Sequence[str]) -> None:
    """SC-001: no printed command is refused for an approved work package."""
    text = output(result)
    for wording in APPROVED_REFUSALS:
        assert wording not in text, f"{' '.join(argv)} was refused for an approved work package: {text}"


def run_printed(route: RouteMission, argv: Sequence[str], *, feedback: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run one printed command as an operator would: only the placeholders are filled in (the agent is the implementer)."""
    filled = _fill(argv, route.implementer, feedback)
    result = cli(route, *filled)
    assert_no_approved_refusal(result, filled)
    return result


def resolve_conflict(checkout: Path, text: str, *, novel_line: bool = False, rel_path: str = SHARED_PATH) -> str:
    """The human act: write the resolved file, ``git add`` it and commit the merge in progress; return the merge SHA."""
    resolved = text.replace(f"{LANE_B_LINE}\n", f"{LANE_B_LINE}\n{NOVEL_LINE}\n") if novel_line else text
    (checkout / rel_path).write_text(resolved, encoding="utf-8")
    git(checkout, "add", rel_path)
    git(checkout, "commit", "-q", "--no-edit")
    return git_rev(checkout, "HEAD")


def approval_event(route: RouteMission, wp_id: str) -> StatusEvent:
    """*wp_id*'s newest transition into ``approved``."""
    found = [event for event in events(route) if event.wp_id == wp_id and str(event.to_lane) == "approved"]
    assert found, f"{wp_id} has no approval"
    return found[-1]


# --------------------------------------------------------------------------- the route


def stale_remedy_parts(route: RouteMission, *, lane: str, wp_id: str, sibling: str) -> list[str]:
    """The stale refusal's text, in order, as WP07 prints it (the landed text supersedes ``contracts/stale-remedy.md``).

    The in-run auto-rebase halt reason leads, then main's #7755 cause sentence naming the sibling lane and
    its branch, main's #7754 reopen line, then one command per line: re-enter, ``--incorporate`` with its
    resolve-and-commit line, hand back, the independent review, ``consolidate``.
    """
    mission_branch = route.mission.coord_branch
    slug = route.slug
    implement = f"{_SPEC_KITTY} agent action implement {wp_id} --mission {slug}"
    return [
        f"Lane {lane} is stale: overlapping files ['{route.shared_path}'].",
        f"The in-run auto-rebase of lane {lane} onto {mission_branch} stopped:",
        f"The overlapping change comes from lane {sibling} (branch {route.lane_branches[sibling]}), consolidated into {mission_branch} ahead of it.",
        f"{_SPEC_KITTY} agent tasks move-task {wp_id} --to planned --review-feedback-file {_FILE_PLACEHOLDER} --mission {slug}.",
        f"{implement} --agent {_AGENT_PLACEHOLDER}",
        f"{implement} --incorporate {sibling} --agent {_AGENT_PLACEHOLDER}",
        "If it stops on a conflict, resolve it in the lane checkout that command names and commit the merge there.",
        f"{_SPEC_KITTY} agent tasks move-task {wp_id} --to for_review --mission {slug}",
        f"An independent reviewer reviews {wp_id} and approves it again; the new approval must reach the incorporation merge.",
        f"{_SPEC_KITTY} consolidate --mission {slug}",
    ]


def assert_in_order(text: str, parts: Sequence[str]) -> None:
    """Every one of *parts* appears in the collapsed *text*, each after the previous one."""
    flat = collapse(text)
    position = 0
    for part in parts:
        found = flat.find(part, position)
        assert found != -1, f"missing, or out of order after offset {position}: {part!r}\n{flat}"
        position = found + len(part)


def refuse_as_stale(route: RouteMission, *, lane: str, sibling: str, strategy: Strategy) -> str:
    """Step 1: ``consolidate`` refuses *lane* as stale, names *sibling*, the conflict and the shared path; return its raw output.

    The refusal comes from the stale check during lane consolidation, so the rollback leaves every
    branch as it was, ``lane-b`` too (WP03 restores only the run's own verified auto-rebase move).
    """
    before = ref_shas(route)
    result = cli(route, "consolidate", "--mission", route.slug, "--yes", "--strategy", strategy)
    raw = output(result)
    text = collapse(raw)
    assert result.returncode == 1, text
    assert_in_order(raw, stale_remedy_parts(route, lane=lane, wp_id=route.wp_of_lane[lane], sibling=sibling))
    assert "git merge " not in text.replace("git merge --abort", "") and "cd .worktrees" not in text, text
    assert ref_shas(route) == before, "the stale refusal's rollback restores every branch, lane branches included"
    return raw


def follow_route_to_review(route: RouteMission, refusal: str, *, wp_id: str, sibling: str, novel_line: bool = False) -> tuple[list[str], list[list[str]], str]:
    """Steps 2-4: run the printed route up to ``move-task --to for_review``; return the reopen, the printed commands and the merge SHA.

    The reopen runs first (main's #7754 line, with a feedback file), then the re-entry and
    ``--incorporate`` exactly as printed with the implementer as ``<agent>``; the incorporation stops
    on the conflict with the sibling's approval stamp as ``MERGE_HEAD``; the operator resolves and
    commits; the work package goes back for review under the implementer's identity.
    """
    reopen = reopen_command(refusal, wp_id)
    commands = printed_commands(refusal)
    feedback = route.mission.home / f"{wp_id}-feedback.md"
    feedback.write_text(f"Incorporate {sibling} at its approval stamp and resolve the {route.shared_path} overlap.\n", encoding="utf-8")
    sent_back = run_printed(route, reopen, feedback=feedback)
    assert sent_back.returncode == 0, output(sent_back)
    reenter, incorporate = commands[0], commands[1]
    assert "--incorporate" not in reenter and incorporate[incorporate.index("--incorporate") + 1] == sibling, commands
    reentered = run_printed(route, reenter)
    assert reentered.returncode == 0, output(reentered)
    incorporated = run_printed(route, incorporate)
    assert incorporated.returncode == 3, output(incorporated)  # WP08: INCORPORATE_CONFLICT_EXIT, the merge is left in progress
    lane = next(lane_id for lane_id, wp in route.wp_of_lane.items() if wp == wp_id)
    checkout = route.checkouts[lane]
    sibling_stamp = approval_stamp(events(route), route.wp_of_lane[sibling])
    assert git_rev(checkout, "MERGE_HEAD") == sibling_stamp, "the incorporation merges the sibling at its approval stamp"
    merge = resolve_conflict(checkout, RESOLVED_TEXT, novel_line=novel_line)
    handed_back = run_printed(route, [*_for_review_command(commands, wp_id), "--agent", route.implementer])
    assert handed_back.returncode == 0, output(handed_back)
    return reopen, commands, merge


def _for_review_command(commands: Sequence[Sequence[str]], wp_id: str) -> list[str]:
    found = [list(argv) for argv in commands if argv[:4] == ["agent", "tasks", "move-task", wp_id] and "for_review" in argv]
    assert found, f"the route prints no move-task {wp_id} --to for_review: {commands}"
    return found[0]


def independent_approval(route: RouteMission, wp_id: str, *, reviewer: str | None = None) -> tuple[str, subprocess.CompletedProcess[str]]:
    """Step 5: the reviewer claims the review through ``agent action review`` and approves through ``move-task``, unforced.

    Returns the review output and the approval run (asserted by the caller: a self-approval may be refused).
    No ``--note``: on a coordination Mission whose target is protected ``main`` the note's activity-log
    write to the WP file refuses (it is PRIMARY-partition metadata); the approval itself needs none.
    """
    identity = reviewer or route.reviewer
    review = cli(route, "agent", "action", "review", wp_id, "--agent", identity, "--mission", route.slug)
    if review.returncode != 0:
        return output(review), review
    approve = cli(route, "agent", "tasks", "move-task", wp_id, "--to", "approved", "--agent", identity, "--mission", route.slug)
    return output(review), approve


def review_prompt(review_output: str) -> str:
    """The review prompt file ``agent action review`` wrote (its path follows ``cat``); it holds the full review-context block."""
    found = re.search(r"^\s*cat (\S+\.md)\s*$", review_output, re.MULTILINE)
    assert found is not None, f"no review prompt path in:\n{review_output}"
    return Path(found.group(1)).read_text(encoding="utf-8")


def run_route(route: RouteMission, *, lane: str, wp_id: str, sibling: str, strategy: Strategy, novel_line: bool = False) -> RouteOutcome:
    """Steps 1-5 of the re-review route for one conflicting *lane*; the caller runs the final ``consolidate``."""
    refusal = refuse_as_stale(route, lane=lane, sibling=sibling, strategy=strategy)
    reopen, commands, merge = follow_route_to_review(route, refusal, wp_id=wp_id, sibling=sibling, novel_line=novel_line)
    review_output, approve = independent_approval(route, wp_id)
    assert approve.returncode == 0, f"{review_output}\n{output(approve)}"
    return RouteOutcome(
        refusal_output=refusal,
        reopen_command=reopen,
        printed=commands,
        resolution_merge=merge,
        review_output=review_output,
        review_prompt=review_prompt(review_output),
        approval=approval_event(route, wp_id),
    )


def hand_merge(route: RouteMission, *, lane: str, sibling: str, novel_line: bool = False) -> str:
    """The old remedy's shape: merge *sibling*'s approval stamp into *lane*'s checkout by hand, resolve, commit; no send-back."""
    checkout = route.checkouts[lane]
    stamp = approval_stamp(events(route), route.wp_of_lane[sibling])
    assert stamp is not None
    merged = subprocess.run(["git", "merge", "--no-ff", "--no-commit", stamp], cwd=str(checkout), capture_output=True, text=True, check=False)
    assert merged.returncode == 1, f"fixture: the hand merge must conflict: {merged.stdout}{merged.stderr}"
    return resolve_conflict(checkout, RESOLVED_TEXT, novel_line=novel_line)


def merge_own_paths(route: RouteMission, merge: str) -> list[str]:
    """Anti-vacuity: the paths *merge* changed beyond its parents' automatic merge (``git show --remerge-diff``)."""
    return git(route.repo, "show", "--remerge-diff", "--format=", "--name-only", merge).split()


# --------------------------------------------------------------------------- SC-003


def ref_shas(route: RouteMission) -> dict[str, str]:
    """End-state SHAs of the target, the Mission/coordination branch and every lane branch (not a no-move proof alone)."""
    return {branch: git_rev(route.repo, branch) for branch in _moved_branches(route)}


def _moved_branches(route: RouteMission) -> list[str]:
    mission = route.mission
    return [mission.target_branch, mission.coord_branch, *sorted(route.lane_branches.values())]


def branch_reflog_lengths(route: RouteMission) -> dict[str, int]:
    """Reflog length of the target, the Mission/coordination branch and every lane branch."""
    return {branch: len(reflog_shas(route.mission, branch)) for branch in _moved_branches(route)}


def _snapshot_written(route: RouteMission) -> bool:
    path = state_path(route.mission)
    if path is None:
        return False
    return bool(json.loads(path.read_text(encoding="utf-8")).get("pre_mutation_refs"))


def assert_no_branch_moved(route: RouteMission, before: Mapping[str, int]) -> None:
    """SC-003: every branch's reflog has the length it had (no move, not even a rolled-back one) and no snapshot was written."""
    after = branch_reflog_lengths(route)
    assert after == dict(before), f"a branch moved: reflog lengths {dict(before)} -> {after}"
    assert not _snapshot_written(route), "no pre-mutation snapshot may be written by a refusal before any mutation"


def snapshot_written(route: RouteMission) -> bool:
    """Whether a pre-mutation snapshot record exists (the re-entry precondition: a fresh run, never ``--resume``)."""
    return _snapshot_written(route)


def consolidate_in_process(route: RouteMission, strategy: Strategy, monkeypatch: pytest.MonkeyPatch) -> tuple[int, str]:
    """``spec-kitty consolidate`` in this process (so a monkeypatch reaches it); exit code and collapsed output."""
    from specify_cli import app

    monkeypatch.setenv("HOME", str(route.mission.home))
    monkeypatch.setenv("COLUMNS", "1000")
    monkeypatch.chdir(route.repo)
    result = CliRunner().invoke(app, ["consolidate", "--mission", route.slug, "--yes", "--strategy", strategy], catch_exceptions=False)
    return result.exit_code, collapse(result.output)


def one_shot_gate_fail(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Make the REAL gate FAIL exactly once, then delegate to the real verifier (a run that lands lanes, then rolls back)."""
    failed = VerifyResult.failed(Divergence(missing_approved=(("WP01", "a" * 40),)))
    real_verify: Callable[..., VerifyResult] = MergeOutcomeVerifier.verify
    calls: list[int] = []

    def verify_once(self: MergeOutcomeVerifier, target_ref: str, claim: object) -> VerifyResult:
        calls.append(len(calls) + 1)
        if len(calls) == 1:
            return failed
        return real_verify(self, target_ref, claim)

    monkeypatch.setattr(MergeOutcomeVerifier, "verify", verify_once)
    return calls
