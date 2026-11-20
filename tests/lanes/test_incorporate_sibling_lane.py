"""``agent action implement <WP> --incorporate <lane>``: the incorporate step of the re-review route.

A coordination Mission has two independent code lanes, ``lane-a`` (WP01) and
``lane-b`` (WP02), both approved through the production status shell. WP01 is
reworked and approved again, so its newest approval stamp names a commit that
adds ``src/pkg/shared.py``; one bookkeeping-only commit then lands on ``lane-a``
after that approval, so the live tip of ``lane-a`` is past its stamp. WP02 is
reworked and approved again too (its rework adds the same path with other
content for the conflict case, another file for the clean case), then sent back
with the real ``move-task --to in_progress`` CLI.

``implement --incorporate lane-a`` must merge ``lane-a`` at its approval stamp
(never its live tip), stop on a conflict with the merge left in progress, refuse
before any side effect for every precondition, and leave ``implement`` without
the flag unchanged (a golden recorded at the WP08 base).

The two lanes are cut from the same coordination tip, which does not carry
``src/pkg/shared.py``: the conflict case is an add/add conflict, the clean case
touches distinct paths. Both are asserted with ``git merge-tree`` as a
precondition.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from kernel.git.listing import merge_tree
from specify_cli.consolidation.approved_bound import approval_stamp, move_back_command
from specify_cli.lanes.incorporate import SiblingStamp
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.status import read_status_events, resolve_status_read
from tests.terminus.canceled_dependency_support import ACTOR, LANE_A, LANE_B, _approve, _commit_in
from tests.terminus.conftest import CoordMission, git_rev, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.mixed_lane_support import collapse, transition
from tests.terminus.post_approval_support import (
    add_post_approval_commit,
    build_post_approval_coord_mission,
    lane_worktree,
    strip_approval_stamps,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_IMPLEMENTER = "claude"
_SHARED = "src/pkg/shared.py"
_WP02_OWN = "src/pkg/wp02_rework.py"
_CLOSURE_PATH = "kitty-ops/lifecycle/01M72B89ABCDEFGHJKMNPQRSTV.json"
_CLOSURE = '{"metadata": {"closed_by": "doctor_sweep"}, "phase": "abandoned"}\n'
_STATUS_EVENTS = "status.events.jsonl"
_ANALYSIS = (
    "---\nschema: analysis-findings/v1\nfindings: []\ncounts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n"
    "# Specification Analysis Report\n\nNo blocking findings.\n"
)


@dataclass(frozen=True)
class Route:
    """The built Mission plus the facts the assertions read."""

    mission: CoordMission
    lane_a_branch: str
    lane_b_branch: str
    lane_a_stamp: str


#: A printed ``git merge`` that would perform a merge (A-10); ``git merge --abort`` only backs one out.
_MERGE_REMEDY = re.compile(r"git merge(?! --abort)")


def _rev(repo: Path, ref: str) -> str:
    return git_rev(repo, ref)


def _parents(repo: Path, ref: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(repo), "rev-list", "--parents", "-n1", ref], capture_output=True, text=True, check=True).stdout
    return out.split()[1:]


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant], check=False).returncode == 0


def _events(mission: CoordMission) -> list:
    return read_status_events(resolve_status_read(mission.repo, mission.slug))


def _prepare_cli_gates(mission: CoordMission) -> None:
    """Planning documents and a recorded analysis report, which every ``implement`` claim requires."""
    exclude = mission.repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
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


def _rework_and_reapprove(mission: CoordMission, wp_id: str, lane: str, path: str, content: str) -> str:
    transition(mission, wp_id, "in_progress", actor=ACTOR, review_ref=f"review-{wp_id}-rejected")
    tip = _commit_in(lane_worktree(mission, lane), path, content, f"feat({mission.slug}): {wp_id} rework")
    _approve(mission, wp_id, reference=f"review-{wp_id}-rework")
    return tip


def _send_back(mission: CoordMission, wp_id: str) -> None:
    feedback = mission.home / f"{wp_id}-feedback.md"
    feedback.write_text("Incorporate the sibling lane and resolve the overlap.\n", encoding="utf-8")
    moved = run_terminus(
        mission,
        ["agent", "tasks", "move-task", wp_id, "--to", "in_progress", "--mission", mission.slug, "--review-feedback-file", str(feedback)],
    )
    assert moved.returncode == 0, moved.stdout + moved.stderr


def build_route(tmp_path: Path, *, conflict: bool, send_back: bool = True) -> Route:
    mission = build_post_approval_coord_mission(tmp_path)
    _prepare_cli_gates(mission)
    stamp_commit = _rework_and_reapprove(mission, "WP01", LANE_A, _SHARED, "SHARED = 'lane-a'\n")
    if conflict:
        _rework_and_reapprove(mission, "WP02", LANE_B, _SHARED, "SHARED = 'lane-b'\n")
    else:
        _rework_and_reapprove(mission, "WP02", LANE_B, _WP02_OWN, "OWN = 'lane-b'\n")
    add_post_approval_commit(mission, LANE_A, path=_CLOSURE_PATH, content=_CLOSURE)
    if send_back:
        _send_back(mission, "WP02")
    lane_a_branch = mission.lane_branch("WP01")
    lane_b_branch = mission.lane_branch("WP02")
    stamp = approval_stamp(_events(mission), "WP01")
    assert stamp == stamp_commit, "fixture: WP01's newest approval stamp is its rework commit"
    assert _rev(mission.repo, lane_a_branch) != stamp, "fixture: lane-a's live tip is past its approval stamp"
    conflicted = merge_tree(mission.repo, lane_b_branch, stamp).conflicted
    if conflict:
        assert conflicted, "fixture: lane-b and lane-a's stamp must really conflict"
    else:
        assert conflicted == (), f"fixture: the clean case must merge cleanly, got {conflicted}"
    return Route(mission=mission, lane_a_branch=lane_a_branch, lane_b_branch=lane_b_branch, lane_a_stamp=stamp)


def _implement(mission: CoordMission, *extra: str) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["agent", "action", "implement", "WP02", "--agent", _IMPLEMENTER, "--mission", mission.slug, *extra])


def _status_logs(mission: CoordMission) -> dict[str, bytes]:
    logs: dict[str, bytes] = {}
    for directory, subdirectories, files in os.walk(mission.repo):
        subdirectories[:] = [name for name in subdirectories if name != ".git"]
        if _STATUS_EVENTS in files:
            path = Path(directory) / _STATUS_EVENTS
            logs[str(path.relative_to(mission.repo))] = path.read_bytes()
    return logs


def _checkout_state(checkout: Path) -> tuple[str, str]:
    head = git_rev(checkout, "HEAD")
    status = subprocess.run(["git", "-C", str(checkout), "status", "--porcelain=v1", "--untracked-files=all"], capture_output=True, text=True, check=True).stdout
    return head, status


# --- T014 test 1: a clean incorporation merges the sibling's approval stamp -----------------------


def test_clean_incorporate_merges_the_sibling_stamp(tmp_path: Path) -> None:
    route = build_route(tmp_path, conflict=False)
    mission = route.mission
    before = _rev(mission.repo, route.lane_b_branch)

    result = _implement(mission, "--incorporate", LANE_A)
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode == 0, flat
    tip = _rev(mission.repo, route.lane_b_branch)
    first, second = _parents(mission.repo, tip)
    # The normal implement refresh may advance lane-b first (the lane sync point); the
    # incorporation merge sits on top of that refreshed tip.
    assert _is_ancestor(mission.repo, before, first), "the merge's first parent is lane-b's (refreshed) tip"
    assert not _is_ancestor(mission.repo, route.lane_a_stamp, first), "lane-a reached lane-b only through the incorporation merge"
    assert second == route.lane_a_stamp, "the merge's second parent is lane-a's approval stamp, never its live tip"
    assert not _is_ancestor(mission.repo, _rev(mission.repo, route.lane_a_branch), tip), "lane-a's live tip (past its stamp) is not merged"
    message = git_rev_message(mission.repo, tip)
    assert LANE_A in message and route.lane_a_stamp[:12] in message, message
    assert f"Incorporated {LANE_A} at approval stamp {route.lane_a_stamp[:12]}" in flat, flat
    assert not _MERGE_REMEDY.search(flat) and "cd .worktrees" not in flat
    snapshot_lane = _wp_lane(mission, "WP02")
    assert snapshot_lane == "in_progress", "incorporating is not approving: WP02 stays in_progress (C-004)"


def git_rev_message(repo: Path, ref: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%B", ref], capture_output=True, text=True, check=True).stdout


def _wp_lane(mission: CoordMission, wp_id: str) -> str:
    from specify_cli.status import reduce

    state = reduce(_events(mission)).work_packages.get(wp_id) or {}
    return str(state.get("lane"))


# --- T014 test 2: a conflict stops with the merge in progress --------------------------------------


def test_conflict_leaves_merge_in_progress(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import INCORPORATE_CONFLICT_EXIT

    route = build_route(tmp_path, conflict=True)
    mission = route.mission
    before = _rev(mission.repo, route.lane_b_branch)
    checkout = lane_worktree(mission, LANE_B)

    result = _implement(mission, "--incorporate", LANE_A)
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert INCORPORATE_CONFLICT_EXIT not in (0, 1, 2)
    assert result.returncode == INCORPORATE_CONFLICT_EXIT, flat
    assert git_rev(checkout, "MERGE_HEAD") == route.lane_a_stamp, "the merge in progress is lane-a's approval stamp"
    tip = _rev(mission.repo, route.lane_b_branch)
    assert git_rev(checkout, "ORIG_HEAD") == tip, "a conflict commits nothing: lane-b stays at the tip the merge started from"
    assert _is_ancestor(mission.repo, before, tip)
    assert not _is_ancestor(mission.repo, route.lane_a_stamp, tip)
    assert "INCORPORATE STOPPED ON A CONFLICT" in flat, flat
    assert f"conflicted: {_SHARED}" in flat, flat
    assert f"spec-kitty agent tasks move-task WP02 --to for_review --mission {mission.slug}" in flat, flat
    assert f"spec-kitty consolidate --mission {mission.slug}" in flat, flat
    assert not _MERGE_REMEDY.search(flat) and "cd .worktrees" not in flat
    assert f"To back out instead, run in {checkout}: git merge --abort" in flat, flat
    assert _wp_lane(mission, "WP02") == "in_progress"


# --- T014 test 3: every refusal happens before any side effect -------------------------------------


def _strip_stamps(route: Route) -> None:
    strip_approval_stamps(route.mission, "WP01")


def _rewrite_lane_a(route: Route) -> None:
    tree = lane_worktree(route.mission, LANE_A)
    git(tree, "reset", "-q", "--hard", f"{route.lane_a_stamp}~1")
    _commit_in(tree, "src/pkg/rewritten.py", "REWRITTEN = True\n", "feat: rewritten lane-a")


_REFUSALS = {
    "INCORPORATE_LANE_UNKNOWN": ("lane-z", True, None),
    "INCORPORATE_OWN_LANE": (LANE_B, True, None),
    "INCORPORATE_NO_APPROVAL_STAMP": (LANE_A, True, _strip_stamps),
    "INCORPORATE_STAMP_NOT_ON_LANE": (LANE_A, True, _rewrite_lane_a),
    "INCORPORATE_WP_NOT_SENT_BACK": (LANE_A, False, None),
}


@pytest.mark.parametrize("code", sorted(_REFUSALS))
def test_refusal_has_no_side_effect(tmp_path: Path, code: str) -> None:
    lane, send_back, mutate = _REFUSALS[code]
    route = build_route(tmp_path, conflict=False, send_back=send_back)
    mission = route.mission
    if mutate is not None:
        mutate(route)
    checkout = lane_worktree(mission, LANE_B)
    tip_before = _rev(mission.repo, route.lane_b_branch)
    checkout_before = _checkout_state(checkout)
    logs_before = _status_logs(mission)

    result = _implement(mission, "--incorporate", lane)
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode == 1, flat
    assert f"Error: {code}:" in flat, flat
    assert _rev(mission.repo, route.lane_b_branch) == tip_before, "a refusal leaves lane-b's tip"
    assert _checkout_state(checkout) == checkout_before, "a refusal leaves lane-b's checkout"
    assert _status_logs(mission) == logs_before, "a refusal writes no status event"
    if code == "INCORPORATE_WP_NOT_SENT_BACK":
        assert move_back_command("WP02", mission.slug) in flat, flat


def test_planning_lane_is_refused(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import IncorporateCode, IncorporateRefused, _resolve_sibling_stamp

    manifest = LanesManifest(
        version=1,
        mission_slug="m-01M7WW0Z",
        mission_id="01M7WW0Z" + "0" * 18,
        mission_branch="kitty/mission-m-01M7WW0Z",
        target_branch="main",
        lanes=[
            ExecutionLane(lane_id=lane_id, wp_ids=(wp,), write_scope=("src",), predicted_surfaces=("code",), depends_on_lanes=(), parallel_group=0)
            for lane_id, wp in (("lane-planning", "WP01"), (LANE_B, "WP02"))
        ],
        computed_at="2026-11-20T00:00:00+00:00",
        computed_from="unit",
    )
    with pytest.raises(IncorporateRefused) as caught:
        _resolve_sibling_stamp(tmp_path, "m-01M7WW0Z", manifest, own_lane_id=LANE_B, sibling_lane_id="lane-planning", events=[])
    assert caught.value.code is IncorporateCode.PLANNING_LANE


@pytest.mark.parametrize("lane", ["planned", "approved", "done", "for_review", "in_review"])
def test_only_a_claimed_or_in_progress_wp_may_incorporate(lane: str) -> None:
    from specify_cli.lanes.incorporate import IncorporateCode, IncorporateRefused, _check_wp_may_incorporate
    from specify_cli.status import Lane

    with pytest.raises(IncorporateRefused) as caught:
        _check_wp_may_incorporate(Lane(lane), "WP02", "m-01M7WW0Z")
    assert caught.value.code is IncorporateCode.WP_NOT_SENT_BACK
    if lane == "planned":
        assert "nothing to resolve yet" in caught.value.message
    else:
        assert move_back_command("WP02", "m-01M7WW0Z") in caught.value.message
    if lane == "done":
        assert "--force --note" in caught.value.message
    for allowed in ("claimed", "in_progress"):
        _check_wp_may_incorporate(Lane(allowed), "WP02", "m-01M7WW0Z")


# --- T014 test 4 (ratchet): without the flag, implement is unchanged ------------------------------

_SHA = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b")
_ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?")
_PID = re.compile(r"PID: \d+")


def _normalise(text: str, root: Path, home: Path) -> str:
    """Replace the volatile tokens (paths, SHAs, ULIDs, timestamps, the claim PID) with fixed placeholders."""
    text = text.replace(str(home), "<HOME>").replace(str(root), "<TMP>")
    text = _TIMESTAMP.sub("<TS>", text)
    text = _ULID.sub("<ULID>", text)
    text = _SHA.sub("<SHA>", text)
    return _PID.sub("PID: <PID>", text)


def _unflagged_output(root: Path) -> tuple[int, str, str]:
    route = build_route(root, conflict=False)
    result = _implement(route.mission)
    home = route.mission.home
    return result.returncode, _normalise(collapse(result.stdout), root, home), _normalise(collapse(result.stderr), root, home)


#: Recorded at the WP08 base (before ``--incorporate`` existed) with :func:`_unflagged_output`.
_GOLDEN_RC = 0
_GOLDEN_STDOUT = (
    "Branch: main (target for this mission) ✓ Claimed WP02 (agent: claude, PID: <PID>, target: main) 📍 "
    "Workspace: cd <TMP>/repo/.worktrees/terminus-01M56680-lane-b Lane workspace: lane-b (shared by WP02) "
    "⚠️ Has review feedback - read reference: <HOME>/WP02-feedback.md ▶▶▶ NEXT STEP: Read the full prompt "
    "file now: cat "
    "<HOME>/.spec-kitty/spec-kitty-prompts/<SHA>/spec-kitty-implement-terminus-01M56680-WP02.md After "
    'implementation, run: 1. git status && spec-kitty safe-commit <your-files> -m "feat(WP02): '
    '<description>" --to-branch kitty/mission-terminus-01M56680-lane-b 2. spec-kitty agent tasks '
    "mark-status <subtask-ids> --wp WP02 --status done --mission terminus-01M56680 3. spec-kitty agent "
    'tasks move-task WP02 --to for_review --mission terminus-01M56680 --note "Ready for review" '
    "(Pre-flight check will verify no uncommitted changes) [implement] Commits recorded: - "
    "kitty/mission-terminus-01M56680 <SHA> chore: Start WP02 implementation [claude] [ok]"
)
_GOLDEN_STDERR = (
    "Warning: WP02 was claimed as 'claude' with no profile or model recorded, so spec-kitty accept and "
    "spec-kitty consolidate will refuse an approval by another 'claude' identity with "
    "REVIEW_NOT_INDEPENDENT (SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT on a single_branch Mission). Record "
    "your identity: claim with --agent claude:<model>:<profile> (or --profile <profile>), or submit with "
    "spec-kitty agent tasks move-task WP02 --to for_review --agent claude::<profile>."
)


def test_without_flag_implement_is_unchanged(tmp_path: Path) -> None:
    first = _unflagged_output(tmp_path / "first")
    second = _unflagged_output(tmp_path / "second")
    assert first == second, "the normalised output must be deterministic for the golden to hold"
    assert first == (_GOLDEN_RC, _GOLDEN_STDOUT, _GOLDEN_STDERR)


# --- In-process coverage (review cycle 1, item 4): real git, no subprocess CLI ----------------------


def _plain_repo(root: Path) -> Path:
    repo = root / "plain"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "commit.gpgsign", "false")
    _commit_in(repo, "shared.txt", "base\n", "base")
    return repo


def _sibling(repo: Path, *, path: str = "sib.txt", content: str = "sib\n") -> SiblingStamp:
    git(repo, "checkout", "-q", "-b", "sib", "main")
    stamp = _commit_in(repo, path, content, "sibling work")
    git(repo, "checkout", "-q", "-b", "own", "main")
    return SiblingStamp(lane_id="lane-s", branch="sib", stamp=stamp, wp_ids=("WP09",))


def _refused(call: Callable[[], object], code: str) -> str:
    from specify_cli.lanes.incorporate import IncorporateRefused

    with pytest.raises(IncorporateRefused) as caught:
        call()
    assert caught.value.code == code, caught.value
    return caught.value.message


def test_incorporate_sibling_merges_then_reports_already_present(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import incorporate_sibling, render_outcome

    repo = _plain_repo(tmp_path)
    sibling = _sibling(repo)
    before = git_rev(repo, "HEAD")

    merged = incorporate_sibling(repo, sibling)

    assert merged.merged and not merged.already_present and not merged.conflicted
    assert _parents(repo, "HEAD") == [before, sibling.stamp]
    assert merged.merge_sha == git_rev(repo, "HEAD")
    assert render_outcome(merged, "WP02", "m") == [f"Incorporated lane-s at approval stamp {sibling.stamp[:12]} into {repo} (merge {merged.merge_sha[:12]})."]
    again = incorporate_sibling(repo, sibling)
    assert again.already_present and not again.merged
    assert render_outcome(again, "WP02", "m") == [f"lane-s's approval stamp {sibling.stamp[:12]} is already in this lane; nothing to incorporate."]


def test_incorporate_sibling_conflict_then_busy(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import IncorporateCode, incorporate_sibling, render_outcome

    repo = _plain_repo(tmp_path)
    sibling = _sibling(repo, path="shared.txt", content="sibling\n")
    _commit_in(repo, "shared.txt", "own\n", "own work")

    outcome = incorporate_sibling(repo, sibling)

    assert outcome.conflicted_paths == ("shared.txt",)
    assert git_rev(repo, "MERGE_HEAD") == sibling.stamp
    lines = render_outcome(outcome, "WP02", "m")
    assert lines[0].startswith("INCORPORATE STOPPED ON A CONFLICT: lane-s")
    assert f"To back out instead, run in {repo}: git merge --abort" in lines
    message = _refused(lambda: incorporate_sibling(repo, sibling), IncorporateCode.CHECKOUT_BUSY)
    assert "MERGE_HEAD" in message


def test_incorporate_sibling_refuses_dirty_tracked_files(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import IncorporateCode, incorporate_sibling

    repo = _plain_repo(tmp_path)
    sibling = _sibling(repo)
    (repo / "shared.txt").write_text("edited\n", encoding="utf-8")
    head = git_rev(repo, "HEAD")

    message = _refused(lambda: incorporate_sibling(repo, sibling), IncorporateCode.CHECKOUT_BUSY)

    assert "shared.txt" in message
    assert git_rev(repo, "HEAD") == head


def test_incorporate_sibling_failure_without_conflict_is_a_probe_failure(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import IncorporateCode, incorporate_sibling

    repo = _plain_repo(tmp_path)
    sibling = _sibling(repo, path="new.txt", content="sibling\n")
    (repo / "new.txt").write_text("untracked in the way\n", encoding="utf-8")

    message = _refused(lambda: incorporate_sibling(repo, sibling), IncorporateCode.PROBE_FAILED)

    assert "failed without a conflict" in message


def test_incorporate_sibling_probe_errors_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel.git import GitCommandError
    from specify_cli.consolidation import git_probes
    from specify_cli.lanes import incorporate
    from specify_cli.lanes.incorporate import IncorporateCode, incorporate_sibling

    repo = _plain_repo(tmp_path)
    sibling = _sibling(repo, path="shared.txt", content="sibling\n")

    def _status_fails(*_args: object, **_kwargs: object) -> tuple[()]:
        raise GitCommandError(argv=("status",), cwd=repo, returncode=128, stderr="boom")

    with monkeypatch.context() as patch:
        patch.setattr(incorporate, "status_entries", _status_fails)
        assert "cannot read the status" in _refused(lambda: incorporate_sibling(repo, sibling), IncorporateCode.PROBE_FAILED)

    real_resolve = git_probes.resolve_commit

    def _head_unreadable(root: Path, ref: str) -> str:
        if ref == "HEAD":
            raise git_probes.GitProbeError("HEAD unreadable")
        return real_resolve(root, ref)

    with monkeypatch.context() as patch:
        patch.setattr(git_probes, "resolve_commit", _head_unreadable)
        assert "HEAD cannot be read" in _refused(lambda: incorporate_sibling(repo, sibling), IncorporateCode.PROBE_FAILED)

    git(repo, "reset", "-q", "--hard", "HEAD~1")
    _commit_in(repo, "shared.txt", "own\n", "own work")

    def _diff_fails(*_args: object, **_kwargs: object) -> tuple[()]:
        raise GitCommandError(argv=("diff",), cwd=repo, returncode=128, stderr="boom")

    with monkeypatch.context() as patch:
        patch.setattr(incorporate, "changed_paths", _diff_fails)
        assert "conflicts cannot be read" in _refused(lambda: incorporate_sibling(repo, sibling), IncorporateCode.PROBE_FAILED)


def test_newest_stamp_and_stamp_on_branch(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import IncorporateCode, _newest_stamp, _require_stamp_on_branch

    repo = _plain_repo(tmp_path)
    first = _commit_in(repo, "a.txt", "a\n", "a")
    second = _commit_in(repo, "b.txt", "b\n", "b")
    assert _newest_stamp(repo, {"WP01": first, "WP02": second}, "lane-s") == second
    assert _newest_stamp(repo, {"WP01": second, "WP02": first}, "lane-s") == second
    git(repo, "checkout", "-q", "-b", "fork", first)
    forked = _commit_in(repo, "c.txt", "c\n", "c")
    message = _refused(lambda: _newest_stamp(repo, {"WP01": second, "WP02": forked}, "lane-s"), IncorporateCode.STAMP_NOT_ON_LANE)
    assert "diverged" in message
    _require_stamp_on_branch(repo, first, "fork", "lane-s")
    _refused(lambda: _require_stamp_on_branch(repo, second, "fork", "lane-s"), IncorporateCode.STAMP_NOT_ON_LANE)
    assert "cannot read" in _refused(lambda: _require_stamp_on_branch(repo, first, "no-such-branch", "lane-s"), IncorporateCode.PROBE_FAILED)


def test_check_wp_refuses_other_lanes() -> None:
    from specify_cli.lanes.incorporate import IncorporateCode, _check_wp_may_incorporate
    from specify_cli.status import Lane

    message = _refused(lambda: _check_wp_may_incorporate(Lane.CANCELED, "WP02", "m"), IncorporateCode.WP_NOT_SENT_BACK)
    assert "only a claimed or in-progress" in message


def test_exit_if_incorporate_conflict() -> None:
    import typer

    from specify_cli.cli.commands.agent.workflow import _exit_if_incorporate_conflict
    from specify_cli.lanes.incorporate import INCORPORATE_CONFLICT_EXIT, IncorporateOutcome, SiblingStamp

    sibling = SiblingStamp(lane_id="lane-s", branch="sib", stamp="0" * 40, wp_ids=())
    _exit_if_incorporate_conflict(None)
    _exit_if_incorporate_conflict(IncorporateOutcome(sibling, merged=True, already_present=False, merge_sha="1" * 40, conflicted_paths=(), checkout=Path(".")))
    with pytest.raises(typer.Exit) as caught:
        _exit_if_incorporate_conflict(IncorporateOutcome(sibling, merged=False, already_present=False, merge_sha=None, conflicted_paths=("x",), checkout=Path(".")))
    assert caught.value.exit_code == INCORPORATE_CONFLICT_EXIT


def test_incorporate_with_force_is_refused_in_process() -> None:
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent import workflow

    result = CliRunner().invoke(workflow.app, ["implement", "WP02", "--agent", "a", "--force", "--note", "why", "--incorporate", LANE_A])

    assert result.exit_code == 1, result.output
    assert "--incorporate cannot be combined with --force" in result.output


def test_prepare_incorporation_in_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """One real route, every status/manifest probe branch of :func:`prepare_incorporation`, then the CLI helper."""
    from types import SimpleNamespace

    import specify_cli.status as status_module
    from specify_cli.cli.commands.agent.workflow import _run_incorporation
    from specify_cli.lanes import persistence
    from specify_cli.lanes.incorporate import IncorporateCode, SiblingStamp, _resolve_sibling_stamp, prepare_incorporation
    from specify_cli.workspace.context import ResolvedWorkspace, resolve_workspace_for_wp

    route = build_route(tmp_path, conflict=False)
    mission = route.mission
    repo, slug = mission.repo, mission.slug

    sibling = prepare_incorporation(repo, slug, "WP02", LANE_A)
    assert (sibling.stamp, sibling.lane_id, sibling.branch) == (route.lane_a_stamp, LANE_A, route.lane_a_branch)

    assert "no readable lane" in _refused(lambda: prepare_incorporation(repo, slug, "WP99", LANE_A), IncorporateCode.PROBE_FAILED)
    assert "not assigned to any lane" in _refused(lambda: prepare_incorporation(repo, slug, "WP99", LANE_A, check_wp=False), IncorporateCode.PROBE_FAILED)
    manifest = persistence.read_lanes_json(mission.feature_dir)
    assert manifest is not None
    assert "no approved work package" in _refused(
        lambda: _resolve_sibling_stamp(repo, slug, manifest, own_lane_id=LANE_B, sibling_lane_id=LANE_A, events=[]), IncorporateCode.NO_APPROVAL_STAMP
    )

    def _corrupt(_path: Path) -> None:
        raise persistence.CorruptLanesError("bad json")

    def _unreadable(*_args: object, **_kwargs: object) -> None:
        raise OSError("gone")

    planning = LanesManifest(
        **{
            **manifest.__dict__,
            "lanes": [ExecutionLane(lane_id="lane-planning", wp_ids=("WP02",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)],
        }
    )
    probes = [
        ("read_lanes_json", _corrupt, persistence, "lanes.json cannot be read", IncorporateCode.PROBE_FAILED),
        ("read_lanes_json", lambda _path: None, persistence, "has no lanes.json", IncorporateCode.PROBE_FAILED),
        ("read_lanes_json", lambda _path: planning, persistence, "repository root checkout", IncorporateCode.PLANNING_LANE),
        ("resolve_status_read", _unreadable, status_module, "cannot be read", IncorporateCode.PROBE_FAILED),
    ]
    for name, replacement, module, expected, code in probes:
        with monkeypatch.context() as patch:
            patch.setattr(module, name, replacement)
            assert expected in _refused(lambda: prepare_incorporation(repo, slug, "WP02", LANE_A), code)

    assert "own lane" in _refused(
        lambda: _resolve_sibling_stamp(repo, slug, manifest, own_lane_id=LANE_A, sibling_lane_id=LANE_A, events=_events(mission)), IncorporateCode.OWN_LANE
    )

    workspace = resolve_workspace_for_wp(repo, slug, "WP02")
    root_workspace = SimpleNamespace(runs_in_checkout_root=True)
    _refused(lambda: _run_incorporation(repo, slug, "WP02", cast("ResolvedWorkspace", root_workspace), sibling), IncorporateCode.PLANNING_LANE)
    assert _run_incorporation(repo, slug, "WP02", workspace, None) is None
    stale = SiblingStamp(lane_id=LANE_A, branch=route.lane_a_branch, stamp=git_rev(repo, f"{route.lane_a_stamp}~1"), wp_ids=("WP01",))
    outcome = _run_incorporation(repo, slug, "WP02", workspace, stale)
    printed = capsys.readouterr().out
    assert outcome is not None and outcome.merged
    assert f"moved from {stale.stamp[:12]} to {route.lane_a_stamp[:12]}" in printed
    assert _parents(repo, route.lane_b_branch)[1] == route.lane_a_stamp

    strip_approval_stamps(mission, "WP01")
    assert "approved with no approval stamp" in _refused(lambda: prepare_incorporation(repo, slug, "WP02", LANE_A), IncorporateCode.NO_APPROVAL_STAMP)


def test_implement_in_process_refusal_and_conflict_on_fix_prompt_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``implement`` run in process: an ``IncorporateRefused`` exits 1; a conflict exits 3 on the fix-prompt path too."""
    from click.testing import Result
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent import workflow, workflow_executor
    from specify_cli.lanes.incorporate import INCORPORATE_CONFLICT_EXIT

    route = build_route(tmp_path, conflict=True)
    mission = route.mission
    monkeypatch.chdir(mission.repo)
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.delenv("SPEC_KITTY_ORIGIN_CHECK", raising=False)

    def _invoke(lane: str) -> Result:
        return CliRunner().invoke(workflow.app, ["implement", "WP02", "--agent", _IMPLEMENTER, "--mission", mission.slug, "--incorporate", lane])

    refused = _invoke("lane-z")
    assert refused.exit_code == 1, refused.output
    assert "Error: INCORPORATE_LANE_UNKNOWN:" in refused.output

    unflagged = CliRunner().invoke(workflow.app, ["implement", "WP02", "--agent", _IMPLEMENTER, "--mission", mission.slug])
    assert unflagged.exit_code == 0, unflagged.output
    assert "INCORPORAT" not in unflagged.output

    fix_prompt = mission.home / "fix-prompt.md"
    monkeypatch.setattr(workflow_executor, "implement_try_render_fix_mode_prompt", lambda **_kwargs: fix_prompt)
    conflicted = _invoke(LANE_A)
    assert conflicted.exit_code == INCORPORATE_CONFLICT_EXIT, conflicted.output
    assert "INCORPORATE STOPPED ON A CONFLICT" in conflicted.output
    assert git_rev(lane_worktree(mission, LANE_B), "MERGE_HEAD") == route.lane_a_stamp


# --- Review cycle 1, item 5: canceled content under the sibling's approval stamp -----------------


def _own_lane_manifest(mission: CoordMission) -> LanesManifest:
    from specify_cli.lanes.persistence import read_lanes_json

    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    own = ExecutionLane(lane_id="lane-own", wp_ids=("WP77",), write_scope=("src",), predicted_surfaces=("code",), depends_on_lanes=(), parallel_group=0)
    return LanesManifest(**{**manifest.__dict__, "lanes": [*manifest.lanes, own]})


def test_canceled_content_under_the_stamp_is_refused(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import IncorporateCode, _resolve_sibling_stamp
    from tests.terminus.conftest import PlantedChange, build_coord_mission_mixed_lane_canceled

    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path, canceled_changes=(PlantedChange("src/pkg/canceled.py", "CANCELED = True\n"),), survivor_reapproved=True, mid8="01M7WW8A"
    )
    events = _events(mission)
    stamp = approval_stamp(events, "WP01")
    assert stamp is not None

    message = _refused(
        lambda: _resolve_sibling_stamp(mission.repo, mission.slug, _own_lane_manifest(mission), own_lane_id="lane-own", sibling_lane_id=LANE_A, events=events),
        IncorporateCode.CANCELED_CONTENT_UNDER_STAMP,
    )
    assert "canceled WP02" in message and stamp[:12] in message


def test_canceled_wp_without_commits_does_not_refuse(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import _resolve_sibling_stamp
    from tests.terminus.conftest import build_coord_mission_mixed_lane_canceled

    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), mid8="01M7WW8B")
    events = _events(mission)

    sibling = _resolve_sibling_stamp(mission.repo, mission.slug, _own_lane_manifest(mission), own_lane_id="lane-own", sibling_lane_id=LANE_A, events=events)

    assert sibling.stamp == approval_stamp(events, "WP01")


def test_unbounded_canceled_window_refuses() -> None:
    from specify_cli.lanes.incorporate import _window_commits_under

    with pytest.raises(ValueError, match="no recorded lane head"):
        _window_commits_under(Path("."), ("a" * 40, None), "b" * 40)


def _event(wp_id: str, from_lane: str, to_lane: str, index: int, lane_head: str | None) -> object:
    from specify_cli.status import StatusEvent

    return StatusEvent.from_dict(
        {
            "event_id": f"01M7WW0Z{index:018d}",
            "mission_slug": "m",
            "wp_id": wp_id,
            "from_lane": from_lane,
            "to_lane": to_lane,
            "at": f"2026-11-20T00:00:{index:02d}+00:00",
            "actor": "t",
            "force": to_lane == "canceled",
            "execution_mode": "worktree",
            "reason": "test" if to_lane == "canceled" else None,
            "policy_metadata": {"lane_head": lane_head} if lane_head else None,
        }
    )


def test_canceled_window_without_lane_heads_refuses(tmp_path: Path) -> None:
    from specify_cli.lanes.incorporate import IncorporateCode, _active_windows, _refuse_canceled_content_under_stamp

    repo = _plain_repo(tmp_path)
    stamp = git_rev(repo, "HEAD")
    events = [_event("WP05", "planned", "claimed", 1, None), _event("WP05", "claimed", "in_progress", 2, None), _event("WP05", "in_progress", "canceled", 3, None)]
    lane = ExecutionLane(lane_id="lane-s", wp_ids=("WP05",), write_scope=("src",), predicted_surfaces=("code",), depends_on_lanes=(), parallel_group=0)

    assert _active_windows(events, "WP05") == [(None, None)]
    message = _refused(lambda: _refuse_canceled_content_under_stamp(repo, events, lane, stamp), IncorporateCode.CANCELED_CONTENT_UNDER_STAMP)
    assert "cannot be bounded" in message
    assert _active_windows(events[:1], "WP05") == [(None, None)]
    assert _active_windows([_event("WP05", "planned", "claimed", 1, stamp)], "WP05") == [(stamp, None)]
