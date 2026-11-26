"""WP07: the approved-lane stale remedy incorporates the sibling lane, every auto-rebase move is recorded, and
``--incorporate`` refuses a merge an unreviewed merge attribute would compute.

Operator ruling DM-01M88RZDBP57ZTYJHC5NP0ZH4R (2026-11-25): main's #7754/#7755 code names the sibling
lanes, the halt reason and the reopen step; WP07 changes three things only, each pinned here:

1. the refresh step of a stale code lane whose overlap comes from a consolidated sibling lane runs
   ``spec-kitty agent action implement <WP> --mission <m> --incorporate <sibling>`` (WP08's command,
   which merges the sibling at its approval stamp) instead of a raw ``git merge`` of the sibling branch,
   then hands the work back for an independent review; T036 runs every printed command;
2. ``phase_advance`` records the run's own auto-rebase move (``lane_rebase_moves``) whatever the lane's
   consolidation then does, so the rollback (WP03) can undo it (FR-009, R-03);
3. ``--incorporate`` runs WP01's merge-attribute guard, with the Mission branch tip as the committed
   attributes source, before its merge and inside its canceled-window merge probe, and refuses with
   ``INCORPORATE_MERGE_ATTRIBUTES_REFUSED`` (fail closed).
"""

from __future__ import annotations

import inspect
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from kernel.git.listing import merge_tree
from specify_cli.consolidation.state import ConsolidationState, load_state
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.incorporate import IncorporateRefused, SiblingStamp
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from tests.consolidation.stale_sibling_lane_support import (
    IMPLEMENTER,
    LANE_A_TEXT,
    LANE_B_TEXT,
    POPUP,
    RESOLVED_TEXT,
    REVIEWER,
    SEED,
    approve,
    commit_in,
)
from tests.terminus.conftest import (
    _STATUS_EVENTS_FILENAME,
    CoordMission,
    _commit_planning_artifacts,
    _cut_coord_branch,
    _finish_coord_mission,
    _init_fixture_repo,
    _now_iso,
    _write_meta,
    git_rev,
    pin_planning_commit,
    run_terminus,
)
from tests.terminus.conftest import _git as git
from tests.terminus.mixed_lane_support import transition

pytestmark = [pytest.mark.git_repo]

_ATTRIBUTES_REFUSED = "INCORPORATE_MERGE_ATTRIBUTES_REFUSED"
_UNION = "*.py merge=union\n"
_WIDE = {"COLUMNS": "1000"}


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    git(repo, "add", path)
    git(repo, "commit", "-qm", message)
    return git_rev(repo, "HEAD")


def _plain_repo(root: Path) -> Path:
    repo = root / "plain"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.email", "t@example.invalid"), ("user.name", "t"), ("commit.gpgsign", "false")):
        git(repo, "config", key, value)
    _commit(repo, "src/p.py", "a = 1\n", "base")
    return repo


def _refused(call: Any) -> IncorporateRefused:
    with pytest.raises(IncorporateRefused) as caught:
        call()
    return caught.value


def _merge_in_progress(checkout: Path) -> bool:
    return subprocess.run(["git", "-C", str(checkout), "rev-parse", "-q", "--verify", "MERGE_HEAD"], capture_output=True, check=False).returncode == 0


# --- 2. FR-009: the run's own auto-rebase move is recorded on every outcome ------------------------------------

_SLUG = "demo-01ABCDEF"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"


def _manifest() -> LanesManifest:
    lane = ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=("**",), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01ABCDEF0000000000000000AA",
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=[lane],
        computed_at="2026-11-25T00:00:00+00:00",
        computed_from="unit",
    )


def test_auto_rebase_move_recorded_when_the_lane_consolidation_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The auto-rebase merged the Mission branch into the lane, then the lane's consolidation failed: the move is recorded.

    Before WP07 ``_phase_merge_lanes`` recorded the move only when the lane consolidated, so a run that then
    failed and rolled back left the merge on the lane with no record the rollback could undo (R-03, WP03).
    """
    from specify_cli.consolidation import phase_advance
    from specify_cli.lanes import consolidation as lane_consolidation
    from specify_cli.lanes.consolidation import LaneConsolidationResult

    repo = _plain_repo(tmp_path)
    lane_branch = lane_branch_name(_SLUG, "lane-a", target_branch="main")
    git(repo, "branch", _MISSION_BRANCH)
    worktree = tmp_path / "lane-a"
    git(repo, "worktree", "add", "-q", "-b", lane_branch, str(worktree))
    before = _commit(worktree, "src/lane.py", "lane = 1\n", "lane work")
    git(repo, "checkout", "-q", _MISSION_BRANCH)
    _commit(repo, "src/other.py", "other = 1\n", "another lane landed")
    git(repo, "checkout", "-q", "main")

    merged: list[str] = []

    def _auto_rebase_then_fail(repo_root: Path, mission_slug: str, lane_id: str, *_args: object, **_kwargs: object) -> LaneConsolidationResult:
        git(worktree, "merge", "-q", "--no-ff", "--no-edit", _MISSION_BRANCH)  # the merge lanes.auto_rebase makes
        merged.append(git_rev(worktree, "HEAD"))
        return LaneConsolidationResult(success=False, lane_id=lane_id, merged_into=_MISSION_BRANCH, errors=["Lane lane-a is stale"])

    monkeypatch.setattr(lane_consolidation, "consolidate_lane_into_mission", _auto_rebase_then_fail)
    state = ConsolidationState.from_dict(
        {"mission_id": "01ABCDEF0000000000000000AA", "mission_slug": _SLUG, "target_branch": "main", "wp_order": [], "pre_mutation_refs": {lane_branch: before}}
    )
    run = SimpleNamespace(
        main_repo=repo,
        state=state,
        lanes_manifest=_manifest(),
        mission_slug=_SLUG,
        excluded_canceled_wp_ids=frozenset(),
        is_resume=False,
        any_lane_had_unintegrated_code=False,
    )

    # The undecorated phase: the post-tip recorder needs a full run state this stand-in does not carry.
    unwrapped = inspect.unwrap(phase_advance._phase_merge_lanes)
    with pytest.raises(typer.Exit):
        unwrapped(run)

    assert merged, "precondition: the stand-in made the auto-rebase merge"
    assert run.state.lane_rebase_moves == {lane_branch: [before, merged[0]]}
    saved = load_state(repo, state.mission_id)
    assert saved is not None and saved.lane_rebase_moves == {lane_branch: [before, merged[0]]}


# --- 3. The --incorporate merge-attribute guard (binding DoD item, FR-010) -------------------------------------


def _conflicting_sibling(repo: Path, *, lane_attributes: str | None) -> SiblingStamp:
    """``sib`` and ``own`` both edit ``src/p.py``; ``own`` (checked out) commits *lane_attributes* first."""
    git(repo, "checkout", "-q", "-b", "sib", "main")
    stamp = _commit(repo, "src/p.py", "a = 'sibling'\n", "sibling work")
    git(repo, "checkout", "-q", "-b", "own", "main")
    if lane_attributes is not None:
        _commit(repo, ".gitattributes", lane_attributes, "lane attributes")
    _commit(repo, "src/p.py", "a = 'own'\n", "own work")
    return SiblingStamp(lane_id="lane-s", branch="sib", stamp=stamp, wp_ids=("WP09",), attributes_source=git_rev(repo, "main"))


def test_a_lane_committed_union_attribute_refuses_the_incorporate_merge(tmp_path: Path) -> None:
    """Red at the WP08 base: git merged the conflict with ``union``, bytes neither side wrote, and exited 0."""
    from specify_cli.lanes.incorporate import incorporate_sibling

    repo = _plain_repo(tmp_path)
    sibling = _conflicting_sibling(repo, lane_attributes=_UNION)
    assert merge_tree(repo, "own", sibling.stamp).conflicted == (), "precondition: union makes the conflict merge clean"
    head = git_rev(repo, "HEAD")

    refusal = _refused(lambda: incorporate_sibling(repo, sibling))

    assert refusal.code == _ATTRIBUTES_REFUSED, refusal
    assert "merge=union" in refusal.message or "'union'" in refusal.message, refusal.message
    assert "src/p.py" in refusal.message and "nothing was merged" in refusal.message, refusal.message
    assert git_rev(repo, "HEAD") == head and not _merge_in_progress(repo)
    assert (repo / "src" / "p.py").read_text(encoding="utf-8") == "a = 'own'\n"


def test_a_clone_local_union_attribute_refuses_the_incorporate_merge(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import incorporate_sibling

    repo = _plain_repo(tmp_path)
    sibling = _conflicting_sibling(repo, lane_attributes=None)
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "attributes").write_text(_UNION, encoding="utf-8")
    head = git_rev(repo, "HEAD")

    refusal = _refused(lambda: incorporate_sibling(repo, sibling))

    assert refusal.code == _ATTRIBUTES_REFUSED, refusal
    assert git_rev(repo, "HEAD") == head and not _merge_in_progress(repo)


def test_a_union_committed_on_the_mission_branch_is_honoured(tmp_path: Path) -> None:
    """Control (operator ruling (a)): a ``union`` committed at the attributes source is reviewed, so the merge runs."""
    from specify_cli.lanes.incorporate import incorporate_sibling

    repo = _plain_repo(tmp_path)
    _commit(repo, ".gitattributes", _UNION, "reviewed attributes")
    sibling = _conflicting_sibling(repo, lane_attributes=None)

    outcome = incorporate_sibling(repo, sibling)

    assert outcome.merged and not outcome.conflicted, outcome
    assert git_rev(repo, "HEAD^2") == sibling.stamp


def test_without_an_attributes_source_a_committed_union_is_refused(tmp_path: Path) -> None:
    """An unread Mission branch tip honours no committed ``union`` (fail closed), even one on ``main``."""
    from dataclasses import replace

    from specify_cli.lanes.incorporate import incorporate_sibling

    repo = _plain_repo(tmp_path)
    _commit(repo, ".gitattributes", _UNION, "reviewed attributes")
    sibling = replace(_conflicting_sibling(repo, lane_attributes=None), attributes_source=None)

    assert _refused(lambda: incorporate_sibling(repo, sibling)).code == _ATTRIBUTES_REFUSED


def test_a_plain_conflict_still_stops_for_resolution(tmp_path: Path) -> None:
    """Control: with git's built-in merge the guard passes and the conflict is left for the operator, as before."""
    from specify_cli.lanes.incorporate import incorporate_sibling

    repo = _plain_repo(tmp_path)
    sibling = _conflicting_sibling(repo, lane_attributes=None)

    outcome = incorporate_sibling(repo, sibling)

    assert outcome.conflicted_paths == ("src/p.py",) and _merge_in_progress(repo)


def test_an_unreadable_merge_base_refuses_before_any_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes import incorporate

    repo = _plain_repo(tmp_path)
    sibling = _conflicting_sibling(repo, lane_attributes=None)
    head = git_rev(repo, "HEAD")
    monkeypatch.setattr(incorporate, "git_merge_base", lambda *_args: None)

    refusal = _refused(lambda: incorporate.incorporate_sibling(repo, sibling))

    assert refusal.code == _ATTRIBUTES_REFUSED and "merge base" in refusal.message, refusal
    assert git_rev(repo, "HEAD") == head and not _merge_in_progress(repo)


def test_the_incorporate_merge_runs_with_the_pinned_merge_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The merge itself runs with WP01's pinned config (``merge_probe_env``), so a value set after the guard cannot apply."""
    from specify_cli.consolidation.merge_attribute_guard import MERGE_PROBE_CONFIG_PINS
    from specify_cli.lanes import incorporate

    repo = _plain_repo(tmp_path)
    sibling = _conflicting_sibling(repo, lane_attributes=None)
    seen: dict[str, str] = {}
    real = incorporate.run_committing_op

    def _spy(checkout: Path, op: str, args: list[str], *, env: dict[str, str], **kwargs: Any) -> Any:
        seen.update(env)
        return real(checkout, op, args, env=env, **kwargs)

    monkeypatch.setattr(incorporate, "run_committing_op", _spy)
    incorporate.incorporate_sibling(repo, sibling)

    for key, value in MERGE_PROBE_CONFIG_PINS:
        assert f"'{key}'='{value}'" in seen.get("GIT_CONFIG_PARAMETERS", ""), seen.get("GIT_CONFIG_PARAMETERS")


# --- 3b. The canceled-window merge probe runs under the same guard, with the Mission branch tip as source ---------

_MIXED_SLUG = "m-01M7WW0Z"
_MIXED_MISSION_BRANCH = f"kitty/mission-{_MIXED_SLUG}"


class _CanceledWindowLane:
    """``lane-a`` (WP01 approved, WP02 canceled); in WP02's window a merge's own resolution adds ``src/canceled.py``."""

    def __init__(self, root: Path, *, mission_union: bool) -> None:
        self.repo = _plain_repo(root)
        _commit(self.repo, ".gitattributes", _UNION, "lane attributes: union on python files")
        git(self.repo, "branch", _MIXED_MISSION_BRANCH, "main" if mission_union else "main~1")
        self.branch = lane_branch_name(_MIXED_SLUG, "lane-a", target_branch="main")
        git(self.repo, "checkout", "-q", "-b", self.branch)
        self.events: list[Any] = []
        self.claim("WP02")
        git(self.repo, "checkout", "-q", "-b", "side")
        _commit(self.repo, "src/side.py", "SIDE = 1\n", "side work")
        git(self.repo, "checkout", "-q", self.branch)
        git(self.repo, "merge", "-q", "--no-ff", "--no-commit", "side")
        (self.repo / "src" / "canceled.py").write_text("CANCELED = True\n", encoding="utf-8")
        git(self.repo, "add", "src/canceled.py")
        git(self.repo, "commit", "-qm", "merge side")
        self.merge = git_rev(self.repo, "HEAD")
        self.move("WP02", "in_progress", "canceled")
        self.claim("WP01")
        _commit(self.repo, "src/wp01.py", "WP01 = 1\n", "WP01 work")
        for source, target in (("in_progress", "for_review"), ("for_review", "in_review"), ("in_review", "approved")):
            self.move("WP01", source, target)

    def move(self, wp_id: str, from_lane: str, to_lane: str) -> None:
        from specify_cli.status import StatusEvent

        index = len(self.events) + 1
        approved = to_lane == "approved"
        self.events.append(
            StatusEvent.from_dict(
                {
                    "event_id": f"01M7WW0Z{index:018d}",
                    "mission_slug": _MIXED_SLUG,
                    "wp_id": wp_id,
                    "from_lane": from_lane,
                    "to_lane": to_lane,
                    "at": f"2026-11-25T00:00:{index:02d}+00:00",
                    "actor": "reviewer" if to_lane in ("in_review", "approved") else "implementer",
                    "force": to_lane == "canceled",
                    "execution_mode": "worktree",
                    "reason": "descoped" if to_lane == "canceled" else None,
                    "review_ref": "review-1" if approved else None,
                    "review_result": {"reviewer": "reviewer", "verdict": "approved", "reference": "review-1"} if approved else None,
                    "policy_metadata": {"lane_head": git_rev(self.repo, "HEAD")},
                }
            )
        )

    def claim(self, wp_id: str) -> None:
        self.move(wp_id, "planned", "claimed")
        self.move(wp_id, "claimed", "in_progress")

    def resolve(self) -> SiblingStamp:
        from specify_cli.lanes.incorporate import _resolve_sibling_stamp

        lanes = [
            ExecutionLane(lane_id=lane_id, wp_ids=wps, write_scope=("src",), predicted_surfaces=("code",), depends_on_lanes=(), parallel_group=0)
            for lane_id, wps in (("lane-a", ("WP01", "WP02")), ("lane-own", ("WP77",)))
        ]
        manifest = LanesManifest(
            version=1,
            mission_slug=_MIXED_SLUG,
            mission_id="01M7WW0Z" + "0" * 18,
            mission_branch=_MIXED_MISSION_BRANCH,
            target_branch="main",
            lanes=lanes,
            computed_at="2026-11-25T00:00:00+00:00",
            computed_from="unit",
        )
        return _resolve_sibling_stamp(self.repo, _MIXED_SLUG, manifest, own_lane_id="lane-own", sibling_lane_id="lane-a", events=self.events, wp_id="WP77")


def test_a_canceled_window_merge_under_an_unreviewed_union_refuses_with_the_attributes_code(tmp_path: Path) -> None:
    """The lane committed ``*.py merge=union``; the Mission branch did not, so the window merge cannot be judged."""
    lane = _CanceledWindowLane(tmp_path, mission_union=False)

    refusal = _refused(lane.resolve)

    assert refusal.code == _ATTRIBUTES_REFUSED, refusal
    assert lane.merge[:12] in refusal.message and "nothing was merged" in refusal.message, refusal.message


def test_a_canceled_window_merge_judged_against_the_mission_branch_attributes(tmp_path: Path) -> None:
    """With ``union`` committed on the Mission branch tip the guard passes and the merge's own content is named."""
    lane = _CanceledWindowLane(tmp_path, mission_union=True)

    refusal = _refused(lane.resolve)

    assert refusal.code == "INCORPORATE_CANCELED_CONTENT_UNDER_STAMP", refusal
    assert f"reaches merge {lane.merge[:12]}, whose own resolution changed src/canceled.py" in refusal.message, refusal.message


def test_the_mission_branch_tip_is_the_attributes_source(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import _read_attributes_source

    lane = _CanceledWindowLane(tmp_path, mission_union=True)

    assert _read_attributes_source(lane.repo, _MIXED_MISSION_BRANCH) == git_rev(lane.repo, _MIXED_MISSION_BRANCH)
    assert _read_attributes_source(lane.repo, "kitty/mission-missing") is None


# --- 1 + T036: the printed approved-lane route runs, command by command --------------------------------------------

_ANALYSIS = (
    "---\nschema: analysis-findings/v1\nfindings: []\ncounts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n"
    "# Specification Analysis Report\n\nNo blocking findings.\n"
)
#: Refusal wording ``implement`` / ``move-task`` print for an approved work package; none may appear on the route.
_APPROVED_REFUSALS = ("cannot claim", "is already in lane: approved", "refuses an approved", "--force")


def _route_wp_file(wp: str) -> str:
    return f"---\nwork_package_id: {wp}\ntitle: {wp} work\ndependencies: []\nsubtasks: []\nowned_files:\n  - src/**\n---\n# {wp}\n"


def _build_route_mission(tmp_path: Path, *, mid8: str = "01M7WW07") -> tuple[CoordMission, Path]:
    """The #7755 two-lane shape (``tests.consolidation.stale_sibling_lane_support``) under a real Mission slug.

    That builder lower-cases the mid8 in the slug (``alpha-01m77550``); the CLI's coordination lookup for
    a status commit then misses the ``-coord`` worktree and refuses on the protected target, so the
    printed CLI commands cannot run there. Real slugs carry the upper-case mid8, as here. Returns the
    Mission and lane-b's checkout.
    """
    slug = f"alpha-{mid8}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch="main", extra_base_files={POPUP: SEED})
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)

    def _lane(lane_id: str, wp: str) -> ExecutionLane:
        return ExecutionLane(lane_id=lane_id, wp_ids=(wp,), write_scope=("src/**",), predicted_surfaces=("ui",), depends_on_lanes=(), parallel_group=0)

    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=[_lane("lane-a", "WP01"), _lane("lane-b", "WP02")],
        computed_at=_now_iso(),
        computed_from="approved-lane-route-fixture",
    )
    write_lanes_json(mission.feature_dir, manifest)
    pin_planning_commit(mission.repo, mission.feature_dir)
    for wp in ("WP01", "WP02"):
        (mission.feature_dir / "tasks" / f"{wp}-work.md").write_text(_route_wp_file(wp), encoding="utf-8")
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text("", encoding="utf-8")
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap approved-lane route mission")
    _cut_coord_branch(mission)
    _finish_coord_mission(mission)
    manifest = read_lanes_json(mission.feature_dir) or manifest
    checkouts: dict[str, Path] = {}
    for wp, text in (("WP01", LANE_A_TEXT), ("WP02", LANE_B_TEXT)):
        transition(mission, wp, "planned", actor=IMPLEMENTER)
        transition(mission, wp, "claimed", actor=IMPLEMENTER)
        checkout, branch = allocate_lane_worktree(mission.repo, slug, wp, manifest)
        transition(mission, wp, "in_progress", actor=IMPLEMENTER)
        commit_in(checkout, POPUP, text, f"feat({slug}): {wp} edits Popup.vue")
        approve(mission, wp, reference=f"review-{wp}")
        checkouts[wp] = checkout
        mission.lane_branches[wp] = branch
    return mission, checkouts["WP02"]


def _prepare_cli_gates(mission: CoordMission) -> None:
    """Planning documents and a recorded analysis report, which every ``implement`` claim requires."""
    exclude = mission.repo / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as fh:
        fh.write(".kittify/derived/\n.kittify/workspaces/\n")
    for name, text in (("spec.md", "# Spec\n\nFR-001.\n"), ("plan.md", "# Plan\n"), ("tasks.md", "# Tasks\n")):
        (mission.feature_dir / name).write_text(text, encoding="utf-8")
    git(mission.repo, "add", "kitty-specs")
    git(mission.repo, "commit", "-qm", "chore: planning documents")
    findings = mission.home / "analysis-input.md"
    findings.write_text(_ANALYSIS, encoding="utf-8")
    recorded = run_terminus(mission, ["agent", "mission", "record-analysis", "--mission", mission.slug, "--input-file", str(findings)])
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    git(mission.repo, "add", "kitty-specs")
    git(mission.repo, "commit", "-qm", "chore: record analysis", "--allow-empty")


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout or "") + (result.stderr or "")


def _printed_route(output: str) -> tuple[str, list[str]]:
    """The reopen command (inside the reopen sentence) and every later line that is a ``spec-kitty`` command."""
    flat = " ".join(output.split())  # the console wraps the long reopen sentence
    reopen = re.search(r"(spec-kitty agent tasks move-task WP02 --to planned --review-feedback-file <file> --mission \S+?)\.(?:\s|$)", flat)
    assert reopen is not None, output
    commands = [line.strip() for line in output.splitlines() if line.strip().startswith("spec-kitty ")]
    return reopen.group(1), commands


def _run_printed(mission: CoordMission, command: str) -> subprocess.CompletedProcess[str]:
    """Run a printed command as an operator would: only the ``<agent>`` placeholder is filled in."""
    argv = command.replace("<agent>", IMPLEMENTER).split()
    assert argv[0] == "spec-kitty", command
    return run_terminus(mission, argv[1:], env=_WIDE)


def _assert_no_approved_refusal(result: subprocess.CompletedProcess[str], command: str) -> None:
    text = _output(result)
    for wording in _APPROVED_REFUSALS:
        assert wording not in text, f"{command}: {text}"


def _assert_review_cycle_on_coordination_branch(mission: CoordMission, wp_id: str) -> None:
    """The reopen's review-cycle evidence is committed on the coordination branch (its COORD-partition home)."""
    listed = subprocess.run(
        ["git", "-C", str(mission.repo), "ls-tree", "-r", "--name-only", mission.coord_branch, f"kitty-specs/{mission.slug}/tasks/"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert any(f"/{wp_id}-" in path and path.endswith("/review-cycle-1.md") for path in listed), listed


@pytest.mark.integration
@pytest.mark.slow
def test_main_reopen_line_runs_on_a_protected_coordination_target(tmp_path: Path) -> None:
    """#7861 on WP08's ``build_route`` fixture: main's reopen line, then re-entry with ``--agent``, run as printed.

    Red at the WP07 base: ``move-task --to planned --review-feedback-file`` exited 1 with "Automatic verdict
    evidence could not be committed because the governed destination branch is protected".
    """
    from tests.lanes.test_incorporate_sibling_lane import build_route

    mission = build_route(tmp_path, conflict=True, send_back=False).mission
    target_before = git_rev(mission.repo, mission.target_branch)
    feedback = mission.home / "WP02-feedback.md"
    feedback.write_text("Incorporate lane-a and resolve the shared.py overlap.\n", encoding="utf-8")

    reopened = _run_printed(mission, f"spec-kitty agent tasks move-task WP02 --to planned --review-feedback-file {feedback} --mission {mission.slug}")

    assert reopened.returncode == 0, _output(reopened)
    assert git_rev(mission.repo, mission.target_branch) == target_before, "the reopen never commits to the protected target"
    _assert_review_cycle_on_coordination_branch(mission, "WP02")
    reentered = _run_printed(mission, f"spec-kitty agent action implement WP02 --mission {mission.slug} --agent <agent>")
    assert reentered.returncode == 0, _output(reentered)
    _assert_no_approved_refusal(reentered, "implement")
    incorporated = _run_printed(mission, f"spec-kitty agent action implement WP02 --mission {mission.slug} --incorporate lane-a --agent <agent>")
    assert incorporated.returncode == 3, _output(incorporated)  # the add/add conflict, left for resolution


@pytest.mark.integration
@pytest.mark.slow
def test_reopen_without_a_coordination_surface_never_commits_to_the_protected_target(tmp_path: Path) -> None:
    """Fail closed (#7861 ruling item 6): with the coordination worktree and branch gone the reopen refuses by name."""
    from tests.lanes.test_incorporate_sibling_lane import build_route

    mission = build_route(tmp_path, conflict=True, send_back=False).mission
    coord_checkout = next(path for path in (mission.repo / ".worktrees").iterdir() if path.name.endswith("-coord"))
    git(mission.repo, "worktree", "remove", "--force", str(coord_checkout))
    git(mission.repo, "branch", "-D", mission.coord_branch)
    target_before = git_rev(mission.repo, mission.target_branch)
    feedback = mission.home / "WP02-feedback.md"
    feedback.write_text("Incorporate lane-a.\n", encoding="utf-8")

    reopened = _run_printed(mission, f"spec-kitty agent tasks move-task WP02 --to planned --review-feedback-file {feedback} --mission {mission.slug}")

    assert reopened.returncode == 1, _output(reopened)
    # The existing named protected-primary refusal (``_protected_branch_status_commit_error``), before any write.
    assert "Refusing to run `spec-kitty agent tasks move-task` with auto-commit on protected branch 'main'" in " ".join(_output(reopened).split())
    assert git_rev(mission.repo, mission.target_branch) == target_before, "never a fallback commit on the protected target"


@pytest.mark.integration
@pytest.mark.slow
def test_every_printed_route_command_runs_and_the_mission_lands(tmp_path: Path) -> None:
    """T036 (FR-001, no-op passable: no): run each printed command in order; the human resolves and reviews between them."""
    mission, checkout = _build_route_mission(tmp_path)
    _prepare_cli_gates(mission)

    first = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"], env=_WIDE)
    output = _output(first)
    assert first.returncode == 1, output
    assert "lane-b is stale" in output and POPUP in output, output
    assert not re.search(r"git merge(?! --abort)", output) and "cd .worktrees" not in output, output
    reopen, commands = _printed_route(output)
    incorporate = f"spec-kitty agent action implement WP02 --mission {mission.slug} --incorporate lane-a --agent <agent>"
    assert commands == [
        f"spec-kitty agent action implement WP02 --mission {mission.slug} --agent <agent>",
        incorporate,
        f"spec-kitty agent tasks move-task WP02 --to for_review --mission {mission.slug}",
        f"spec-kitty consolidate --mission {mission.slug}",
    ], output

    # Main's #7754 reopen line, run exactly as printed (operator ruling DM-01M89KDT5DZQ4DX6ZFX54HY3J3, #7861):
    # its review-cycle evidence goes to the coordination branch, never to the protected target.
    assert reopen == f"spec-kitty agent tasks move-task WP02 --to planned --review-feedback-file <file> --mission {mission.slug}"
    target_before = git_rev(mission.repo, mission.target_branch)
    feedback = mission.home / "WP02-feedback.md"
    feedback.write_text("Incorporate lane-a at its approval stamp and resolve the Popup.vue overlap.\n", encoding="utf-8")
    sent_back = _run_printed(mission, reopen.replace("<file>", str(feedback)))
    assert sent_back.returncode == 0, _output(sent_back)
    assert git_rev(mission.repo, mission.target_branch) == target_before, "the reopen never commits to the protected target"
    _assert_review_cycle_on_coordination_branch(mission, "WP02")

    reentered = _run_printed(mission, commands[0])
    assert reentered.returncode == 0, _output(reentered)
    _assert_no_approved_refusal(reentered, commands[0])

    incorporated = _run_printed(mission, commands[1])
    # WP08: a conflicted incorporation leaves the merge in progress and exits 3 for hand resolution.
    assert incorporated.returncode == 3, _output(incorporated)
    _assert_no_approved_refusal(incorporated, commands[1])
    assert _merge_in_progress(checkout), _output(incorporated)
    assert str(checkout) in _output(incorporated)

    # The human act between the printed commands: resolve and commit in the checkout the command named.
    (checkout / POPUP).write_text(RESOLVED_TEXT, encoding="utf-8")
    git(checkout, "add", POPUP)
    git(checkout, "commit", "-q", "--no-edit")

    handed_back = _run_printed(mission, commands[2])
    assert handed_back.returncode == 0, _output(handed_back)
    _assert_no_approved_refusal(handed_back, commands[2])

    # The independent review (another identity), then the printed consolidate.
    from specify_cli.status.models import ReviewResult

    transition(mission, "WP02", "in_review", actor=REVIEWER)
    reference = "review-WP02-after-incorporating-lane-a"
    transition(
        mission,
        "WP02",
        "approved",
        actor=REVIEWER,
        review_ref=reference,
        review_result=ReviewResult(reviewer=REVIEWER, verdict="approved", reference=reference),
    )
    landed = _run_printed(mission, commands[3] + " --yes")
    assert landed.returncode == 0, _output(landed)
    shown = subprocess.run(["git", "-C", str(mission.repo), "show", f"{mission.target_branch}:{POPUP}"], capture_output=True, text=True, check=True)
    assert shown.stdout == RESOLVED_TEXT
