"""FR-008 / FR-009 / SC-004 (Mission ``approved-lane-resolution-route``): the three-lane route, the next run after a rollback, the lanes topology.

Every scenario starts from WP12's frozen builder
:func:`~tests.terminus.approved_lane_route_support.build_conflicting_lanes_mission`, imported, never edited.

* T055 -- SC-004 / FR-009: a run that auto-rebases ``lane-b`` cleanly, lands the lanes and then FAILs at the
  gate once rolls ``lane-b`` back from its own verified auto-rebase move (tip, lane work-tip ref, no durable
  record left); the next ``consolidate`` lands without tripping over that move. The control: a foreign commit
  made on ``lane-b`` after the rollback is judged (``LANE_MOVED_AFTER_APPROVAL``), never reset.
* T056 -- the three-lane route: exact sibling sets in every stale refusal (``lane-d`` never named), one review
  cycle per conflicting lane, the Mission lands with every lane's content.
* T057 -- the own-lane rule (R-04): ``lane-c``'s approval stamp reaching ``lane-b``'s unreviewed merge does not
  excuse it.
* T058 -- the two-lane route on the LANES topology (no coordination branch) under squash and ``--strategy
  merge``, plus N1 there.

No ``xfail`` and no ``skip``: a route gap is reported, never marked.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from specify_cli.consolidation.approved_bound import approval_stamp
from specify_cli.consolidation.reconciliation_verifier import MergeOutcomeVerifier, VerifyResult
from specify_cli.status.models import actor_full_identity
from tests.terminus.approved_lane_route_support import (
    IMPLEMENTER,
    LANE_A,
    LANE_A_LINE,
    LANE_B,
    LANE_B_LINE,
    LANE_C,
    LANE_C_LINE,
    LANE_D,
    OTHER_PATH,
    RECONCILIATION_VERIFIED,
    RESOLUTION_MERGE_UNREVIEWED,
    RESOLVED_TEXT,
    REVIEWER,
    SHARED_PATH,
    RouteMission,
    Strategy,
    add_dependent_and_control_lanes,
    approval_event,
    assert_no_branch_moved,
    branch_reflog_lengths,
    build_conflicting_lanes_mission,
    cli,
    consolidate,
    consolidate_in_process,
    events,
    git,
    hand_merge,
    independent_approval,
    lane_of,
    merge_own_paths,
    one_shot_gate_fail,
    output,
    printed_commands,
    reopen_command,
    resolve_conflict,
    run_printed,
    run_route,
    show,
    snapshot_written,
)
from tests.terminus.conftest import blob_present_at, git_rev, sha_reachable
from tests.terminus.rollback_harness import state_path

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_HARNESS_VARIABLES = ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE")
_STRATEGIES = pytest.mark.parametrize("strategy", ["squash", "merge"])
_ATTESTATION_FLAGS = ("--attest-approved-reviewed", "--attest-canceled-superseded", "--attest-no-implementation")
_LANE_MOVED_AFTER_APPROVAL = "LANE_MOVED_AFTER_APPROVAL"
_AUTO_REBASE_PREFIX = "refs/spec-kitty/auto-rebase/"
_LANE_TIP_PREFIX = "refs/spec-kitty/lane-tip/"
#: ``lane-b``'s clean change in T055: line 6, two unchanged lines away from ``lane-a``'s line 3.
_LANE_B_CLEAN_LINE = "EPSILON = 5  # lane-b"
_LATE_PATH = "src/pkg/late.py"
#: The rollback report that follows the stale refusal (it lists every branch, so it is not the refusal's sibling set).
_ROLLBACK_REPORT = " Rollback"


@pytest.fixture(autouse=True)
def _unset_harness_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)


# --------------------------------------------------------------------------- local helpers


def _with(text: str, old: str, new: str) -> str:
    assert old in text, f"fixture: {old!r} not in {text!r}"
    return text.replace(old, new)


def _clean_lane_b_text(route: RouteMission) -> str:
    """The target's seed with only line 6 changed: ``lane-b``'s net change no longer touches lines 3 or 4."""
    seed = show(route.repo, route.mission.target_branch, SHARED_PATH)
    return _with(seed, "EPSILON = 0", _LANE_B_CLEAN_LINE)


def _run_ok(route: RouteMission, *argv: str) -> str:
    result = cli(route, *argv)
    assert result.returncode == 0, f"{' '.join(argv)}\n{output(result)}"
    return output(result)


def _rework_lane_b_clean(route: RouteMission) -> None:
    """Send ``WP02`` back, move its change to line 6 in the lane checkout, and have it re-reviewed, through the CLI.

    The built lanes conflict (lines 3 and 4); the clean variant T055 needs an auto-rebase that succeeds, so
    ``lane-b``'s net change is moved two lines away from ``lane-a``'s. Every step is a CLI command plus the
    implementer's commit; the re-approval is unforced, by the independent reviewer.
    """
    feedback = route.mission.home / "WP02-clean.md"
    feedback.write_text("Move the change to EPSILON.\n", encoding="utf-8")
    _run_ok(route, "agent", "tasks", "move-task", "WP02", "--to", "planned", "--review-feedback-file", str(feedback), "--mission", route.slug)
    _run_ok(route, "agent", "action", "implement", "WP02", "--mission", route.slug, "--agent", IMPLEMENTER)
    checkout = route.checkouts[LANE_B]
    (checkout / SHARED_PATH).write_text(_clean_lane_b_text(route), encoding="utf-8")
    git(checkout, "add", SHARED_PATH)
    git(checkout, "commit", "-qm", "feat: WP02 moves its change to EPSILON")
    _run_ok(route, "agent", "tasks", "move-task", "WP02", "--to", "for_review", "--agent", IMPLEMENTER, "--mission", route.slug)
    review_output, approve = independent_approval(route, "WP02")
    assert approve.returncode == 0, f"{review_output}\n{output(approve)}"


def build_clean_lanes_mission(tmp_path: Path, mid8: str) -> RouteMission:
    """T055's clean variant: two approved lanes that both edit :data:`SHARED_PATH` and merge cleanly."""
    route = build_conflicting_lanes_mission(tmp_path, "coord", mid8=mid8)
    _rework_lane_b_clean(route)
    lane_a, lane_b = route.lane_branches[LANE_A], route.lane_branches[LANE_B]
    merged = subprocess.run(["git", "merge-tree", "--write-tree", lane_a, lane_b], cwd=str(route.repo), capture_output=True, text=True, check=False)
    assert merged.returncode == 0, f"fixture: lane-a and lane-b must merge cleanly: {merged.stdout}{merged.stderr}"
    assert all(path.exists() for path in (route.checkouts[LANE_A], route.checkouts[LANE_B])), "fixture: both lane checkouts exist"
    assert approval_stamp(events(route), "WP02") == git_rev(route.repo, lane_b), "fixture: WP02 re-approved at lane-b's tip"
    assert lane_of(route, "WP02") == "approved"
    return route


def _auto_rebase_refs(route: RouteMission, lane: str) -> list[str]:
    listed = git(route.repo, "for-each-ref", "--format=%(refname)", f"{_AUTO_REBASE_PREFIX}{route.lane_branches[lane]}/")
    return listed.split()


def _persisted_moves(route: RouteMission) -> dict[str, list[str]]:
    path = state_path(route.mission)
    if path is None:
        return {}
    moves = json.loads(path.read_text(encoding="utf-8")).get("lane_rebase_moves") or {}
    return {str(branch): list(move) for branch, move in moves.items()}


def _observe_moves_at_gate(route: RouteMission, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, list[str]]]:
    """Wrap the (already one-shot-failing) gate so the persisted ``lane_rebase_moves`` are read before the rollback drops them."""
    seen: list[dict[str, list[str]]] = []
    inner: Callable[..., VerifyResult] = MergeOutcomeVerifier.verify

    def observing(self: MergeOutcomeVerifier, target_ref: str, claim: object) -> VerifyResult:
        seen.append(_persisted_moves(route))
        return inner(self, target_ref, claim)

    monkeypatch.setattr(MergeOutcomeVerifier, "verify", observing)
    return seen


def _parents(route: RouteMission, sha: str) -> list[str]:
    return git(route.repo, "rev-list", "--parents", "-n", "1", sha).split()[1:]


def _rolled_back_first_run(tmp_path: Path, mid8: str, monkeypatch: pytest.MonkeyPatch) -> tuple[RouteMission, str, str]:
    """T055 steps 1-3: the clean variant, a first run that lands then FAILs once and rolls back; ``(route, before, after)``."""
    route = build_clean_lanes_mission(tmp_path, mid8)
    lane_b = route.lane_branches[LANE_B]
    before = git_rev(route.repo, lane_b)
    calls = one_shot_gate_fail(monkeypatch)
    seen = _observe_moves_at_gate(route, monkeypatch)

    code, text = consolidate_in_process(route, "squash", monkeypatch)

    assert calls == [1] and code != 0, text
    assert RECONCILIATION_VERIFIED not in text, text
    assert seen and lane_b in seen[0], f"precondition: the run recorded its own auto-rebase of lane-b: {seen}\n{text}"
    recorded_before, after = seen[0][lane_b]
    assert recorded_before == before and after != before, seen
    parents = _parents(route, after)
    assert len(parents) == 2 and parents[0] == before, f"precondition: the move is a two-parent merge from before: {parents}"
    monkeypatch.undo()
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)
    return route, before, after


def _assert_lane_b_restored(route: RouteMission, before: str, after: str) -> None:
    """Lane-b is back at *before*, its work-tip ref too, and no auto-rebase record names the run's own merge *after*.

    The re-entry (``implement``) and the hand-back already brought lane-b up to the Mission branch with merges
    of their own, each with its durable record; those merges stay on lane-b, so their records stay too. Only
    the record of the run's own move must be gone.
    """
    lane_b = route.lane_branches[LANE_B]
    assert git_rev(route.repo, lane_b) == before, "the rollback restored lane-b from its own auto-rebase move"
    assert git(route.repo, "rev-parse", f"{_LANE_TIP_PREFIX}{lane_b}") == before, "the lane work-tip ref is reset"
    records = _auto_rebase_refs(route, LANE_B)
    assert f"{_AUTO_REBASE_PREFIX}{lane_b}/{after}" not in records, f"the durable record of the run's own merge is gone: {records}"
    for ref in records:
        assert sha_reachable(route.repo, ref.rsplit("/", 1)[1], before), f"every record left names a merge still on lane-b: {ref}"
    assert not sha_reachable(route.repo, after, lane_b), "the run's own merge is no longer on lane-b"


# --------------------------------------------------------------------------- T055


@pytest.mark.parametrize("entry", ["fresh", "resume"])
def test_next_run_after_rollback_is_not_refused_by_own_auto_rebase_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str) -> None:
    route, before, after = _rolled_back_first_run(tmp_path, f"01M7XS4{entry[0].upper()}", monkeypatch)
    _assert_lane_b_restored(route, before, after)
    assert not snapshot_written(route), "the full restore re-baselined the record: no pre-mutation snapshot is left"
    # As landed (WP03 / #6770): the re-baselined record itself stays (``--abort`` clears it), so ``--resume`` has one to read.
    assert state_path(route.mission) is not None, "the re-baselined record is kept"

    if entry == "fresh":
        code, text = consolidate(route, "squash")
    else:
        result = cli(route, "consolidate", "--mission", route.slug, "--yes", "--resume")
        code, text = result.returncode, " ".join(output(result).split())

    assert code == 0, text
    assert RECONCILIATION_VERIFIED in text, f"an exit 0 without the gate's banner is a failure: {text}"
    assert RESOLUTION_MERGE_UNREVIEWED not in text and "LANE_TIP" not in text, text
    assert after[:12] not in text, f"nothing names the first run's merge {after}: {text}"
    landed = show(route.repo, route.mission.target_branch, SHARED_PATH)
    assert LANE_A_LINE in landed and _LANE_B_CLEAN_LINE in landed, landed


def test_foreign_commit_after_rollback_is_judged_not_reset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    route, before, after = _rolled_back_first_run(tmp_path, "01M7XS4X", monkeypatch)
    _assert_lane_b_restored(route, before, after)
    checkout = route.checkouts[LANE_B]
    (checkout / _LATE_PATH).write_text("LATE = True\n", encoding="utf-8")
    git(checkout, "add", _LATE_PATH)
    git(checkout, "commit", "-qm", "operator: a late change on lane-b")
    foreign = git_rev(checkout, "HEAD")
    assert _parents(route, foreign) == [before], "fixture: the foreign commit sits on the restored lane-b"

    code, text = consolidate(route, "squash")

    assert code == 1, text
    assert _LANE_MOVED_AFTER_APPROVAL in text and re.search(rf"\b{foreign[:7]}", text), text
    assert RECONCILIATION_VERIFIED not in text
    assert git_rev(route.repo, route.lane_branches[LANE_B]) == foreign, "the foreign commit is never reset"


# --------------------------------------------------------------------------- T056 / T057 helpers


def _approval_counts(route: RouteMission) -> dict[str, int]:
    counts = dict.fromkeys(route.wp_of_lane.values(), 0)
    for event in events(route):
        if str(event.to_lane) == "approved" and event.wp_id in counts:
            counts[event.wp_id] += 1
    return counts


def _stale_remedy(text: str, lane: str) -> str:
    """The stale refusal's own text for *lane* (from its ``Lane <lane> is stale`` line on), whitespace-collapsed."""
    flat = " ".join(text.split())
    start = flat.find(f"Lane {lane} is stale")
    assert start != -1, f"no stale refusal for {lane}: {flat}"
    end = flat.find(_ROLLBACK_REPORT, start)
    return flat[start : end if end != -1 else len(flat)]


def _assert_exact_siblings(text: str, lane: str, siblings: Sequence[str], never: Sequence[str]) -> None:
    """FR-002: the refusal for *lane* names exactly *siblings*, in that order; no lane of *never* is named at all."""
    remedy = _stale_remedy(text, lane)
    assert re.findall(r"--incorporate (\S+)", remedy) == list(siblings), remedy
    cause = re.search(r"The overlapping change comes from (.*?), consolidated into", remedy)
    assert cause is not None, remedy
    assert re.findall(r"lane (\S+) \(branch ", cause.group(1)) == list(siblings), cause.group(1)
    for other in never:
        assert other not in remedy, f"{other} is never named as a sibling of {lane}: {remedy}"


def _for_review(commands: Sequence[Sequence[str]], wp_id: str) -> list[str]:
    found = [list(argv) for argv in commands if argv[:4] == ["agent", "tasks", "move-task", wp_id] and "for_review" in argv]
    assert found, f"the route prints no move-task {wp_id} --to for_review: {commands}"
    return found[0]


def _dependent_resolution(route: RouteMission) -> str:
    """``lane-c``'s resolution: ``lane-a``'s line 3 and ``lane-c``'s own line 4 (it supersedes ``lane-b``'s)."""
    return RESOLVED_TEXT.replace(LANE_B_LINE, LANE_C_LINE)


def _incorporate(route: RouteMission, argv: Sequence[str], text: str) -> str | None:
    """Run one printed ``--incorporate`` command; on its conflict stop, resolve with *text* and commit. Return the merge, if any."""
    checkout = route.checkouts[LANE_C]
    head = git_rev(checkout, "HEAD")
    result = run_printed(route, argv)
    assert result.returncode in (0, 3), output(result)  # 3: WP08's conflict exit, the merge is left in progress
    sibling = argv[list(argv).index("--incorporate") + 1]
    stamp = approval_stamp(events(route), route.wp_of_lane[sibling])
    if result.returncode == 3:
        assert git_rev(checkout, "MERGE_HEAD") == stamp, f"the incorporation merges {sibling} at its approval stamp"
        return resolve_conflict(checkout, text)
    tip = git_rev(checkout, "HEAD")
    assert tip != head and stamp is not None and sha_reachable(route.repo, stamp, tip), output(result)
    return tip


def _route_dependent_lane(route: RouteMission, strategy: Strategy) -> tuple[str, list[str]]:
    """The route for ``lane-c``, as printed, with ``lane-c``'s own resolution; return the refusal and the incorporation merges.

    WP12's :func:`run_route` assumes one sibling and resolves with ``lane-b``'s text, so the stages run here with the
    public pieces: the printed reopen, re-entry and every ``--incorporate``, the operator's resolution, the printed
    hand-back and the independent review.
    """
    result = cli(route, "consolidate", "--mission", route.slug, "--yes", "--strategy", strategy)
    refusal = output(result)
    assert result.returncode == 1, refusal
    _assert_exact_siblings(refusal, LANE_C, [LANE_A, LANE_B], never=(LANE_D,))
    flat = " ".join(refusal.split())
    assert "git merge " not in flat.replace("git merge --abort", "") and "cd .worktrees" not in flat, flat
    commands = printed_commands(refusal)
    for argv in commands:
        assert not any(flag in argv for flag in (*_ATTESTATION_FLAGS, "--force")), f"C-002: {argv}"
    feedback = route.mission.home / "WP03-feedback.md"
    feedback.write_text("Incorporate the sibling lanes at their approval stamps and keep lane-c's line.\n", encoding="utf-8")
    assert run_printed(route, reopen_command(refusal, "WP03"), feedback=feedback).returncode == 0
    reentered = run_printed(route, commands[0])
    assert reentered.returncode == 0 and "--incorporate" not in commands[0], output(reentered)
    merges = [_incorporate(route, argv, _dependent_resolution(route)) for argv in commands if "--incorporate" in argv]
    assert run_printed(route, [*_for_review(commands, "WP03"), "--agent", IMPLEMENTER]).returncode == 0
    review_output, approve = independent_approval(route, "WP03")
    assert approve.returncode == 0, f"{review_output}\n{output(approve)}"
    return refusal, [merge for merge in merges if merge is not None]


# --------------------------------------------------------------------------- T056


def test_three_lane_route_names_exact_siblings_and_lands(tmp_path: Path) -> None:
    started = time.monotonic()
    route = add_dependent_and_control_lanes(build_conflicting_lanes_mission(tmp_path, "coord", mid8="01M7X3RT"))
    approvals = _approval_counts(route)

    outcome = run_route(route, lane=LANE_B, wp_id="WP02", sibling=LANE_A, strategy="squash")
    _assert_exact_siblings(outcome.refusal_output, LANE_B, [LANE_A], never=(LANE_C, LANE_D))
    for argv in [outcome.reopen_command, *outcome.printed]:
        assert not any(flag in argv for flag in (*_ATTESTATION_FLAGS, "--force")), f"C-002: {argv}"

    _refusal, lane_c_merges = _route_dependent_lane(route, "squash")
    lane_c_stamp = approval_event(route, "WP03").policy_metadata["lane_head"]
    assert lane_c_merges and all(sha_reachable(route.repo, merge, lane_c_stamp) for merge in lane_c_merges), "the re-approval reaches every incorporation"

    assert not snapshot_written(route)
    code, text = consolidate(route, "squash")
    assert code == 0, text
    assert RECONCILIATION_VERIFIED in text, f"an exit 0 without the gate's banner is a failure: {text}"
    target = route.mission.target_branch
    assert show(route.repo, target, SHARED_PATH) == _dependent_resolution(route), "lane-a's and lane-c's lines land (lane-c supersedes lane-b's line)"
    assert blob_present_at(route.repo, target, OTHER_PATH) and show(route.repo, target, OTHER_PATH) == route.side_texts[LANE_D]
    after = _approval_counts(route)
    added = {wp: after[wp] - approvals[wp] for wp in after}
    assert added == {"WP01": 0, "WP02": 1, "WP03": 1, "WP04": 0}, f"SC-001: one review cycle per conflicting lane, none for lane-d: {added}"
    print(f"three-lane route[squash] wall time {time.monotonic() - started:.1f}s")


# --------------------------------------------------------------------------- T057


def _reapprove_lane_c_over(route: RouteMission, lane_b_merge: str) -> str:
    """Send ``WP03`` back, merge ``lane-b`` (with its hand merge) into ``lane-c``, and re-approve it unforced; return lane-c's merge."""
    feedback = route.mission.home / "WP03-rework.md"
    feedback.write_text("Take lane-b's latest work.\n", encoding="utf-8")
    _run_ok(route, "agent", "tasks", "move-task", "WP03", "--to", "planned", "--review-feedback-file", str(feedback), "--mission", route.slug)
    implement = ("agent", "action", "implement", "WP03", "--mission", route.slug, "--agent", IMPLEMENTER)
    # As landed: the re-entry first merges the dependency lane-b into lane-c itself; on a conflict it refuses and
    # tells the operator to merge lane-b by hand, commit, and run implement again. That is what the operator does.
    healed = cli(route, *implement)
    assert healed.returncode != 0 and "cannot auto-merge dependency lane 'lane-b'" in output(healed), output(healed)
    checkout = route.checkouts[LANE_C]
    merged = subprocess.run(["git", "merge", "--no-ff", "--no-commit", route.lane_branches[LANE_B]], cwd=str(checkout), capture_output=True, text=True, check=False)
    assert merged.returncode == 1, f"fixture: lane-b's hand merge conflicts with lane-c's line: {merged.stdout}{merged.stderr}"
    merge = resolve_conflict(checkout, _dependent_resolution(route))
    _run_ok(route, *implement)
    assert sha_reachable(route.repo, lane_b_merge, merge), "fixture: lane-c's merge takes lane-b's hand merge"
    _run_ok(route, "agent", "tasks", "move-task", "WP03", "--to", "for_review", "--agent", IMPLEMENTER, "--mission", route.slug)
    review_output, approve = independent_approval(route, "WP03")
    assert approve.returncode == 0, f"{review_output}\n{output(approve)}"
    return merge


def test_three_lane_dependent_stamp_does_not_excuse_unreviewed_merge(tmp_path: Path) -> None:
    route = add_dependent_and_control_lanes(build_conflicting_lanes_mission(tmp_path, "coord", mid8="01M7X3DS"))
    merge = hand_merge(route, lane=LANE_B, sibling=LANE_A)
    assert lane_of(route, "WP02") == "approved", "fixture: WP02 was never sent back"
    _reapprove_lane_c_over(route, merge)

    lane_c_approval = approval_event(route, "WP03")
    assert lane_c_approval.force is False and actor_full_identity(lane_c_approval.actor) == REVIEWER
    lane_c_stamp = approval_stamp(events(route), "WP03")
    assert lane_c_stamp is not None and sha_reachable(route.repo, merge, lane_c_stamp), "precondition: lane-c's stamp reaches lane-b's merge"
    lane_b_stamps = [e.policy_metadata.get("lane_head") for e in events(route) if e.wp_id == "WP02" and str(e.to_lane) == "approved"]
    assert lane_b_stamps and not any(stamp and sha_reachable(route.repo, merge, str(stamp)) for stamp in lane_b_stamps), "precondition: no lane-b stamp reaches it"
    assert SHARED_PATH in merge_own_paths(route, merge), "precondition: the merge carries content of its own"
    before = branch_reflog_lengths(route)

    code, text = consolidate(route, "squash")

    assert code == 1, text
    assert RESOLUTION_MERGE_UNREVIEWED in text and re.search(rf"\b{merge[:7]}", text), text
    assert f"lane {LANE_B} (WP02)" in text, text
    assert RECONCILIATION_VERIFIED not in text
    assert_no_branch_moved(route, before)


# --------------------------------------------------------------------------- T058


@_STRATEGIES
def test_route_lands_after_independent_re_review_lanes_topology(tmp_path: Path, strategy: Strategy) -> None:
    started = time.monotonic()
    route = build_conflicting_lanes_mission(tmp_path, "lanes", mid8=f"01M7XL{strategy[0].upper()}T")
    assert route.topology == "lanes"
    assert "coordination_branch" not in json.loads((route.mission.feature_dir / "meta.json").read_text(encoding="utf-8")), "fixture: no coordination branch"

    outcome = run_route(route, lane=LANE_B, wp_id="WP02", sibling=LANE_A, strategy=strategy)

    for argv in [outcome.reopen_command, *outcome.printed]:
        assert not any(flag in argv for flag in (*_ATTESTATION_FLAGS, "--force")), f"C-002: {argv}"
    approval = outcome.approval
    assert approval.force is False and actor_full_identity(approval.actor) == REVIEWER
    assert approval.review_result is not None and approval.review_result.verdict == "approved"
    assert sha_reachable(route.repo, outcome.resolution_merge, approval.policy_metadata["lane_head"]), "the new approval reaches the resolution merge"
    assert not snapshot_written(route)
    code, text = consolidate(route, strategy)
    assert code == 0, text
    assert RECONCILIATION_VERIFIED in text, f"an exit 0 without the gate's banner is a failure: {text}"
    assert show(route.repo, route.mission.target_branch, SHARED_PATH) == RESOLVED_TEXT
    print(f"route lanes[{strategy}] wall time {time.monotonic() - started:.1f}s")


def test_n1_unreviewed_hand_resolution_is_refused_lanes_topology(tmp_path: Path) -> None:
    route = build_conflicting_lanes_mission(tmp_path, "lanes", mid8="01M7XLN1")
    merge = hand_merge(route, lane=LANE_B, sibling=LANE_A)
    assert SHARED_PATH in merge_own_paths(route, merge), "precondition: the merge carries content of its own"
    assert lane_of(route, "WP02") == "approved", "fixture: WP02 was never sent back"
    before = branch_reflog_lengths(route)

    code, text = consolidate(route, "squash")

    assert code == 1, text
    assert RESOLUTION_MERGE_UNREVIEWED in text and re.search(rf"\b{merge[:7]}", text), text
    assert f"move-task WP02 --to in_progress --mission {route.slug}" in text, text
    assert RECONCILIATION_VERIFIED not in text
    assert_no_branch_moved(route, before)
