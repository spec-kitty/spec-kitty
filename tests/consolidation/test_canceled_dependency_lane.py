"""Unit pins for the fully-canceled dependency-lane fix (#5569, IC-01).

A fully-canceled lane's own commits can ride an approved dependent lane's
first-parent spine (the allocator merges dependency lanes without ``--no-ff``).
These tests drive real git through the shared lane-base helper
(``wp_attribution.lane_own_commits`` / ``_lane_exempt_commits``) and its three
consumers in ``reconciliation``: the canceled-commit set, the authored claim and
the closed-world anchors. The CLI-level reproduction is
``tests/terminus/test_canceled_dependency_content_refused.py``.
"""

from __future__ import annotations

import inspect
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.consolidation.reconciliation import (
    _closed_world_anchors,
    _collect_authored,
    _fully_canceled_lane_commits,
    _unreadable_canceled_dependency_lanes,
    _unreadable_canceled_dependency_refusal_text,
)
from specify_cli.consolidation.wp_attribution import (
    Attributed,
    Unattributable,
    UnattributableReason,
    _lane_exempt_commits,
    _outside_after_anchors,
    lane_own_commits,
    resolve_canceled_wp,
)
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.status import LANE_HEAD_KEY, Lane, StatusEvent

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_TARGET = "main"
_SLUG = "canceled-dep"
_ALPHA = "src/alpha/mod.py"
_BETA = "src/beta/mod.py"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, path: str, text: str) -> str:
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", f"edit {path}")
    return _git(repo, "rev-parse", "HEAD")


def _lane(lane_id: str, wp_id: str, deps: tuple[str, ...] = ()) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=(wp_id,),
        write_scope=("src",),
        predicted_surfaces=("code",),
        depends_on_lanes=deps,
        parallel_group=0,
    )


def _manifest(*lanes: ExecutionLane) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01CANCELEDDEP00000000000000",
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch=_TARGET,
        lanes=list(lanes),
        computed_at="2026-10-03T00:00:00+00:00",
        computed_from="test-canceled-dependency-lane",
    )


def _branch(lane_id: str) -> str:
    branch: str = lane_branch_name(_SLUG, lane_id, target_branch=_TARGET)
    return branch


@dataclass(frozen=True)
class Dep:
    """``base`` -> lane-a (WP01, canceled work) fast-forwarded into lane-b (WP02, approved work)."""

    repo: Path
    manifest: LanesManifest
    base: str
    canceled_sha: str
    approved_sha: str


@pytest.fixture
def dep(tmp_path: Path) -> Dep:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    base = _commit(repo, "README.md", "init\n")
    manifest = _manifest(_lane("lane-a", "WP01"), _lane("lane-b", "WP02", ("lane-a",)))
    _git(repo, "checkout", "-q", "-b", _branch("lane-a"), base)
    canceled_sha = _commit(repo, _ALPHA, "ALPHA = 'canceled work'\n")
    _git(repo, "checkout", "-q", "-b", _branch("lane-b"), base)
    _git(repo, "merge", "-q", "--no-edit", _branch("lane-a"))  # fast-forward, as the allocator does
    approved_sha = _commit(repo, _BETA, "BETA = 'approved work'\n")
    return Dep(repo=repo, manifest=manifest, base=base, canceled_sha=canceled_sha, approved_sha=approved_sha)


# --------------------------------------------------------------------------- #
# T002 -- the shared lane-base helper
# --------------------------------------------------------------------------- #


def test_lane_exempt_commits_unions_anchor_ranges(dep: Dep) -> None:
    exempt = _lane_exempt_commits(dep.repo, dep.base, [_branch("lane-a")])
    assert exempt == {dep.canceled_sha}


def test_lane_exempt_commits_skips_an_unreadable_anchor(dep: Dep) -> None:
    exempt = _lane_exempt_commits(dep.repo, dep.base, ["no-such-ref", _branch("lane-a")])
    assert exempt == {dep.canceled_sha}  # the bad anchor exempts nothing; the good one still does


def test_lane_exempt_commits_without_anchors_is_empty(dep: Dep) -> None:
    assert _lane_exempt_commits(dep.repo, dep.base, []) == frozenset()


def test_lane_own_commits_drops_history_reachable_from_an_anchor(dep: Dep) -> None:
    lane_b = [dep.approved_sha, dep.canceled_sha]
    assert lane_own_commits(dep.repo, dep.base, lane_b, [_branch("lane-a")]) == {dep.approved_sha}


def test_lane_own_commits_without_anchors_keeps_every_commit(dep: Dep) -> None:
    lane_b = [dep.approved_sha, dep.canceled_sha]
    assert lane_own_commits(dep.repo, dep.base, lane_b, []) == set(lane_b)


# --------------------------------------------------------------------------- #
# T003 -- the fully-canceled lanes' commits and the authored claim
# --------------------------------------------------------------------------- #


def test_fully_canceled_lane_commits_are_the_canceled_lanes_own(dep: Dep) -> None:
    got = _fully_canceled_lane_commits(dep.repo, dep.manifest, frozenset({"WP01"}), dep.base, None)
    assert got == {dep.canceled_sha}


def test_no_fully_canceled_lane_means_no_canceled_commits(dep: Dep) -> None:
    assert _fully_canceled_lane_commits(dep.repo, dep.manifest, frozenset(), dep.base, None) == frozenset()


def test_mixed_lane_is_not_fully_canceled(dep: Dep) -> None:
    mixed = _manifest(_lane("lane-a", "WP01"), ExecutionLane("lane-b", ("WP02", "WP03"), ("src",), ("code",), ("lane-a",), 0))
    assert _fully_canceled_lane_commits(dep.repo, mixed, frozenset({"WP02"}), dep.base, None) == frozenset()


def test_fully_canceled_lane_whose_branch_is_gone_yields_nothing(dep: Dep) -> None:
    gone = _manifest(_lane("lane-a", "WP01"), _lane("lane-gone", "WP09"), _lane("lane-b", "WP02", ("lane-a",)))
    assert _fully_canceled_lane_commits(dep.repo, gone, frozenset({"WP09"}), dep.base, None) == frozenset()


def test_canceled_lane_does_not_claim_history_inherited_from_an_approved_dependency(dep: Dep) -> None:
    """lane-c (canceled WP03) depends on lane-b: lane-b's commits are its inherited base, not its own."""
    manifest = _manifest(*dep.manifest.lanes, _lane("lane-c", "WP03", ("lane-b",)))
    _git(dep.repo, "checkout", "-q", "-b", _branch("lane-c"), _branch("lane-b"))
    own = _commit(dep.repo, "src/gamma/mod.py", "GAMMA = 'canceled'\n")
    got = _fully_canceled_lane_commits(dep.repo, manifest, frozenset({"WP03"}), dep.base, None)
    # lane-a and lane-b are not canceled, so lane-b is a (live) anchor: only lane-c's own commit remains.
    assert got == {own}


def test_target_base_keeps_target_history_out_of_the_canceled_set(dep: Dep) -> None:
    got = _fully_canceled_lane_commits(dep.repo, dep.manifest, frozenset({"WP01"}), dep.base, _branch("lane-a"))
    assert got == frozenset()  # the target already carries lane-a's commit: nothing new to exclude


def test_authored_claim_drops_the_canceled_commit_from_the_dependent_lane(dep: Dep) -> None:
    lanes_approved = {"WP02": {"lane": "approved"}}
    before = _collect_authored(dep.repo, dep.manifest, lanes_approved, dep.base, canceled_lane_commits=frozenset())
    assert dep.canceled_sha in before[0]  # the pre-fix claim: canceled work counted as approved authorship

    shas, _patch_ids, blobs, _deletions, _multi, _content = _collect_authored(
        dep.repo, dep.manifest, lanes_approved, dep.base, None, canceled_lane_commits=frozenset({dep.canceled_sha})
    )

    assert dep.canceled_sha not in shas
    assert dep.approved_sha in shas
    assert {path for path, _blob in blobs} == {_BETA}


# --------------------------------------------------------------------------- #
# T004 -- closed-world anchors
# --------------------------------------------------------------------------- #


def test_fully_canceled_dependency_lane_tip_is_not_an_anchor(dep: Dep) -> None:
    anchors = _closed_world_anchors(dep.manifest, dep.manifest.lanes[1], "target-tip", excluded_canceled_wp_ids=frozenset({"WP01"}))
    assert anchors == ["target-tip"]


def test_approved_dependency_lane_tip_stays_an_anchor(dep: Dep) -> None:
    anchors = _closed_world_anchors(dep.manifest, dep.manifest.lanes[1], "target-tip", excluded_canceled_wp_ids=frozenset())
    assert anchors == [_branch("lane-a"), "target-tip"]


def test_only_the_canceled_dependency_is_dropped_from_a_chain(dep: Dep) -> None:
    chain = _manifest(_lane("lane-a", "WP01"), _lane("lane-b", "WP02", ("lane-a",)), _lane("lane-c", "WP03", ("lane-b",)))
    anchors = _closed_world_anchors(chain, chain.lanes[2], None, excluded_canceled_wp_ids=frozenset({"WP01"}))
    assert anchors == [_branch("lane-b")]


def test_never_exempt_commits_stay_outside_even_when_an_anchor_reaches_them(dep: Dep) -> None:
    outside = ((dep.canceled_sha, _ALPHA), (dep.approved_sha, _BETA))
    anchors = [_branch("lane-b")]  # e.g. the first-claim stamp taken after the fast-forward

    exempted = _outside_after_anchors(dep.repo, dep.base, outside, anchors, never_exempt=frozenset())
    kept = _outside_after_anchors(dep.repo, dep.base, outside, anchors, never_exempt=frozenset({dep.canceled_sha}))

    assert exempted == ()
    assert kept == ((dep.canceled_sha, _ALPHA),)


def test_never_exempt_is_a_no_op_without_outside_commits(dep: Dep) -> None:
    assert _outside_after_anchors(dep.repo, dep.base, (), [], never_exempt=frozenset({dep.canceled_sha})) == ()


# --------------------------------------------------------------------------- #
# Fail closed when a fully-canceled DEPENDENCY lane's tip is unreadable
# --------------------------------------------------------------------------- #


def test_fully_canceled_dependency_lane_whose_branch_is_gone_refuses(dep: Dep) -> None:
    """lane-b inherited lane-a's canceled commit; with lane-a's branch gone nothing can subtract it."""
    _git(dep.repo, "branch", "-D", _branch("lane-a"))

    unreadable = _unreadable_canceled_dependency_lanes(dep.repo, dep.manifest, frozenset({"WP01"}), dep.base)

    assert unreadable == [("lane-a", _branch("lane-a"))]
    text = _unreadable_canceled_dependency_refusal_text(unreadable)
    assert "lane-a" in text
    assert _branch("lane-a") in text


def test_fully_canceled_dependency_lane_with_an_unreadable_range_refuses(dep: Dep) -> None:
    unreadable = _unreadable_canceled_dependency_lanes(dep.repo, dep.manifest, frozenset({"WP01"}), "no-such-base")

    assert [lane_id for lane_id, _branch_name in unreadable] == ["lane-a"]


def test_readable_fully_canceled_dependency_lane_does_not_refuse(dep: Dep) -> None:
    assert _unreadable_canceled_dependency_lanes(dep.repo, dep.manifest, frozenset({"WP01"}), dep.base) == []


def test_fully_canceled_lane_nobody_depends_on_stays_tolerated(dep: Dep) -> None:
    gone = _manifest(_lane("lane-a", "WP01"), _lane("lane-gone", "WP09"), _lane("lane-b", "WP02", ("lane-a",)))

    assert _unreadable_canceled_dependency_lanes(dep.repo, gone, frozenset({"WP09"}), dep.base) == []


def test_missing_branch_of_a_dependency_lane_that_is_not_canceled_is_not_this_check(dep: Dep) -> None:
    """An approved lane's missing branch is the PD-5 check's business, not this one's."""
    _git(dep.repo, "branch", "-D", _branch("lane-a"))

    assert _unreadable_canceled_dependency_lanes(dep.repo, dep.manifest, frozenset(), dep.base) == []


def test_canceled_lane_depending_on_a_canceled_lane_does_not_count_as_a_live_dependent(dep: Dep) -> None:
    both = _manifest(_lane("lane-a", "WP01"), _lane("lane-c", "WP03", ("lane-a",)))
    _git(dep.repo, "branch", "-D", _branch("lane-a"))

    assert _unreadable_canceled_dependency_lanes(dep.repo, both, frozenset({"WP01", "WP03"}), dep.base) == []


def test_multi_lane_contribution_is_recorded_at_an_authored_commit_not_a_canceled_tip(dep: Dep) -> None:
    """The recorded lane commit feeds the three-way merge guard, so it must be one the lane authored."""
    _git(dep.repo, "checkout", "-q", "-b", _branch("lane-c"), dep.base)
    _commit(dep.repo, _ALPHA, "ALPHA = 'another lane'\n")
    manifest = _manifest(_lane("lane-b", "WP02"), _lane("lane-c", "WP03"))
    approved = {"WP02": {"lane": "approved"}, "WP03": {"lane": "approved"}}
    # lane-b's tip is dep.approved_sha; mark it canceled so lane-b authors only dep.canceled_sha (ALPHA).
    *_, multi_lane_paths, _content = _collect_authored(dep.repo, manifest, approved, dep.base, None, canceled_lane_commits=frozenset({dep.approved_sha}))

    first, second = multi_lane_paths[_ALPHA]
    by_lane = {contribution.lane_id: contribution for contribution in (first, second)}
    assert by_lane["lane-b"].lane_commit == dep.canceled_sha


@pytest.mark.parametrize(
    ("function", "parameter"),
    [
        (_outside_after_anchors, "never_exempt"),
        (_collect_authored, "canceled_lane_commits"),
        (_closed_world_anchors, "excluded_canceled_wp_ids"),
        (resolve_canceled_wp, "never_exempt_commits"),
    ],
)
def test_safety_parameters_are_required_keyword_only(function: Callable[..., object], parameter: str) -> None:
    """A caller that forgets the canceled-lane set must fail loudly, not quietly exempt/claim everything."""
    declared = inspect.signature(function).parameters[parameter]
    assert declared.kind is inspect.Parameter.KEYWORD_ONLY
    assert declared.default is inspect.Parameter.empty


def test_canceled_lane_content_recovery_offers_only_the_revert_that_survives_resume() -> None:
    """A rebuilt lane trips the resume lane-tip CAS, so the advice must not suggest rebuilding it."""
    from specify_cli.consolidation.reconciliation import _mixed_lane_recovery

    advice = _mixed_lane_recovery(UnattributableReason.CANCELED_LANE_CONTENT, "WP02")

    assert "reverting them on it" in advice
    assert "rebuild the lane without them" not in advice
    assert "do not rebuild the lane" in advice


# --------------------------------------------------------------------------- #
# #5569 end to end through the attribution resolver (seam for the CLI repro)
# --------------------------------------------------------------------------- #


def _stamped(event_id: str, wp_id: str, from_lane: Lane, to_lane: Lane, stamp: str) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_SLUG,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=f"2026-10-03T00:00:{event_id[-2:]}+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        policy_metadata={LANE_HEAD_KEY: stamp},
    )


def _resolve_in_lane_b(dep: Dep, *, never_exempt: frozenset[str]) -> Attributed | Unattributable:
    """Resolve canceled WP03 on mixed lane-b (approved WP02) whose spine inherited lane-a's commit.

    WP02's first governed claim was stamped AFTER the allocator's fast-forward, so the
    first-claim anchor reaches ``dep.canceled_sha`` -- exactly the path an exemption
    would take if nothing named that commit as a fully-canceled lane's own.
    """
    events = [
        _stamped("e01", "WP02", Lane.PLANNED, Lane.CLAIMED, dep.canceled_sha),
        _stamped("e02", "WP02", Lane.IN_PROGRESS, Lane.FOR_REVIEW, dep.approved_sha),
        _stamped("e05", "WP02", Lane.IN_REVIEW, Lane.APPROVED, dep.approved_sha),
        _stamped("e03", "WP03", Lane.PLANNED, Lane.CLAIMED, dep.approved_sha),
        _stamped("e04", "WP03", Lane.IN_PROGRESS, Lane.CANCELED, dep.approved_sha),
    ]
    return resolve_canceled_wp(
        dep.repo,
        events=events,
        lane_id="lane-b",
        lane_wp_ids=["WP02", "WP03"],
        canceled_wp_id="WP03",
        lane_branch=_branch("lane-b"),
        coord_base_ref=dep.base,
        is_bookkeeping=lambda _path: False,
        closed_world_anchors=[_branch("lane-a")],
        never_exempt_commits=never_exempt,
    )


def test_fully_canceled_dependency_commit_is_refused_as_canceled_lane_content_even_when_anchors_reach_it(dep: Dep) -> None:
    outcome = _resolve_in_lane_b(dep, never_exempt=frozenset({dep.canceled_sha}))

    assert isinstance(outcome, Unattributable)
    assert outcome.reason is UnattributableReason.CANCELED_LANE_CONTENT
    assert dep.canceled_sha[:7] in outcome.detail


def test_approved_dependency_commit_stays_exempt_and_passes_the_closed_world(dep: Dep) -> None:
    """Positive control on the same fixture: nothing is fully canceled, so the inherited commit is plain history."""
    outcome = _resolve_in_lane_b(dep, never_exempt=frozenset())

    assert isinstance(outcome, Attributed)
