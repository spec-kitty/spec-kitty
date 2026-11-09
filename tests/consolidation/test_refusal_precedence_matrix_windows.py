"""Refusal-precedence rows of the lane window refusal (Mission consolidation-window-provenance-01M6Y84D, WP19, FR-017, C-006).

WP19 adds a second text to the ``bound`` refusal of :mod:`tests.consolidation.test_refusal_precedence_matrix`
(WP03's matrix, unchanged): the tier-2 window refusal, one line per commit that lies in no approved
work package's window, naming the work package approved before it. It is rendered AFTER the tier-1
text of every lane (``reconciliation_bound._render_lane_verdicts``), inside the same ``bound`` slot,
so it keeps the bound's place in the claim builder's order. This module pins, with WP03's fixtures,
conventions and normalizer:

* the two compositions through ``_compound_refusal`` (``canceled_dependency`` and ``mixed_lane``,
  each followed by the window refusal), full normalized text;
* the window refusal following a tier-1 ``bound`` refusal of another lane in one text, full text;
* three witnesses (each with a control): a tier-1 refusal on the same lane hides the window refusal,
  ``unresolvable_branches`` hides it, and it hides ``evidence``.

Row count: WP03's matrix holds 2 co-occurring pairs and 7 witnesses; this module adds 3 co-occurring
rows and 3 witnesses (6 rows).

The window condition every row uses is real history built through the production status shell:
a commit X on a lane after its work package's approval, then a rewind (``approved -> in_progress
-> planned``) and a new cycle that opens after X (FR-021), re-approved. X lies in no window, and
the lane's own approval stamp, which reaches X, exempts nothing (WW-2a). The rewind abandons the whole
earlier cycle, so the window text also names that cycle's own commits (and, on a carrier lane, the
canceled dependency content it merged in that cycle): the cycle rule as specified, not fixture noise.
The texts list commits newest first, which is deterministic here (each lane's chain is linear, and a
merged-in commit is reachable only through its merge).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.consolidation.reconciliation import _ALSO_HAS, _BOTH_NEEDED
from tests.consolidation import characterization_support as cs
from tests.consolidation.test_refusal_precedence_matrix import (
    _BY_ID,
    _claim,
    _delete_lane_branch,
    _empty_lane,
    _refusal,
    normalize,
)
from tests.terminus.canceled_dependency_support import ACTOR, LANE_A, LANE_B, _approve, _commit_in, build_canceled_dependency_mission, strip_lane_head_stamps
from tests.terminus.conftest import CoordMission
from tests.terminus.conftest import _git as git
from tests.terminus.mixed_lane_support import transition
from tests.terminus.post_approval_support import add_post_approval_commit, build_post_approval_coord_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: The tier-2 window refusal's own line (``write_branch_bound._window_finding``), shared by both of its forms.
WINDOW_MARKER = "review window; see it with"
#: The tier-1 ``bound`` line (``approved_bound.render_refusals``).
TIER_ONE_MARKER = "holds content committed after its approval stamp"
_ABANDONED_PATH = "src/pkg/between.py"


def _commit_on(mission: CoordMission, branch: str, path: str, message: str) -> str:
    """Commit real content on *branch*, in its worktree when it has one, else through a checkout in the repository root."""
    worktree = cs._worktree_of(mission.repo, branch)
    if worktree is not None:
        return _commit_in(worktree, path, f"{path}\n", message)
    git(mission.repo, "checkout", "-q", branch)
    sha = _commit_in(mission.repo, path, f"{path}\n", message)
    git(mission.repo, "checkout", "-q", mission.target_branch)
    return sha


def plant_window_stray(mission: CoordMission, wp_id: str, *, rework_path: str) -> str:
    """X after *wp_id*'s approval, then a rewind and a new cycle opening after X, re-approved; return X.

    ``approved -> in_progress`` is a review rejection (it keeps the cycle); ``in_progress -> planned``
    is the rewind (FR-021) that starts a new cycle, whose ``claimed`` opener records the lane head
    after X. Every move goes through the production status shell, so ``wp_window`` is captured, not written.
    """
    branch = mission.lane_branches[wp_id]
    stray = _commit_on(mission, branch, _ABANDONED_PATH, f"feat({mission.slug}): unreviewed change after {wp_id}'s approval")
    transition(mission, wp_id, "in_progress", actor=ACTOR, review_ref=f"review-{wp_id}-reopened")
    transition(mission, wp_id, "planned", actor=ACTOR, reason="rewound: restart the work package")
    transition(mission, wp_id, "claimed", actor=ACTOR)
    transition(mission, wp_id, "in_progress", actor=ACTOR)
    _commit_on(mission, branch, rework_path, f"feat({mission.slug}): {wp_id} restarted work")
    _approve(mission, wp_id, reference=f"review-{wp_id}-restarted")
    return stray


def _every_commit(repo: Path) -> tuple[str, ...]:
    """Every commit the fixture made: a rewind abandons a whole cycle, so the window text names the cycle's own commits too."""
    return tuple(cs._git(repo, "rev-list", "--all").split())


@dataclass(frozen=True)
class WindowRow:
    """One co-occurring row: the refusal ids in text order, the fixture, and the commits the text may print."""

    first: str
    builds: Callable[[Path], tuple[str, tuple[str, ...]]]
    joiner: str | None


def _row_canceled_dependency__window(tmp_path: Path) -> tuple[str, tuple[str, ...]]:
    """A carried canceled dependency lane with an unstamped WP; on the approved carrier lane-b, a commit between two cycles of WP02."""
    built = build_canceled_dependency_mission(tmp_path, mid8="01M6Y9P1")
    mission = built.mission
    stray = plant_window_stray(mission, "WP02", rework_path="src/alpha/restarted.py")
    strip_lane_head_stamps(mission, "WP01")
    return _refusal(_claim(mission, canceled="WP01", base=mission.target_branch)), (stray,)


def _row_mixed_lane__window(tmp_path: Path) -> tuple[str, tuple[str, ...]]:
    """On a mixed lane, a commit after WP01's approval that lies outside every work window AND in no review window."""
    mission = cs.build_mixed_lane_through_the_shell(tmp_path, mid8="01M6Y9P2")
    stray = plant_window_stray(mission, "WP01", rework_path="src/pkg/restarted.py")
    return _refusal(_claim(mission, canceled="WP02", base=mission.coord_branch)), (stray,)


def _row_bound__window(tmp_path: Path) -> tuple[str, tuple[str, ...]]:
    """A late commit on lane-a (tier 1) and, on lane-b, a commit between two cycles of WP02 (tier 2): one text, tier 1 first."""
    mission = build_post_approval_coord_mission(tmp_path, mid8="01M6Y9P3")
    late = add_post_approval_commit(mission, LANE_A)
    stray = plant_window_stray(mission, "WP02", rework_path="src/beta/restarted.py")
    return _refusal(_claim(mission, canceled=None, base=mission.coord_branch)), (late, stray)


_COMPOUND = f"\n\n{_ALSO_HAS}\n"
ROWS: tuple[WindowRow, ...] = (
    WindowRow("canceled_dependency", _row_canceled_dependency__window, _COMPOUND),
    WindowRow("mixed_lane", _row_mixed_lane__window, _COMPOUND),
    WindowRow("bound", _row_bound__window, None),
)

SNAPSHOTS: dict[str, str] = {
    "canceled_dependency": "\n".join(
        (
            (
                "canceled WP01 (lane lane-a) is carried by approved lane(s) lane-b but cannot be attributed — WP01 in lane-a entered "
                "implementation but its lifecycle events carry no commit attribution (missions created before this change, or a "
                "transition made outside the governed workflow). This attribution evidence cannot appear later (the event log is "
                "append-only), so re-running alone cannot clear it. Recovery: verify by hand that WP01's canceled content is absent "
                "or superseded on the lane, then re-run spec-kitty consolidate with --attest-canceled-superseded WP01 --attest-reason "
                '"<what you checked>".'
            ),
            "",
            "This Mission also has:",
            (
                "LANE_MOVED_AFTER_APPROVAL: commit <sha> ('src/pkg/between.py') on branch 'kitty/mission-terminus-01M6Y9P1-lane-b' "
                "(lane-b) was committed before WP02's review window opened, and no work package's newest approval comes before it, so "
                "it is in no work package's review window; see it with `git show <sha>`."
            ),
            (
                "commit <sha> ('src/pkg/wp02.py') on branch 'kitty/mission-terminus-01M6Y9P1-lane-b' (lane-b) was committed before "
                "WP02's review window opened, and no work package's newest approval comes before it, so it is in no work package's "
                "review window; see it with `git show <sha>`."
            ),
            (
                "commit <sha> ('src/pkg/wp01.py') on branch 'kitty/mission-terminus-01M6Y9P1-lane-b' (lane-b) was committed before "
                "WP02's review window opened, and no work package's newest approval comes before it, so it is in no work package's "
                "review window; see it with `git show <sha>`."
            ),
            (
                "Recovery: A commit made before a work package's review window opened is covered by no approval: approving again "
                "moves a window's end, never its start. Take the commit off the branch (for example rebuild the branch without it), "
                "then send the branch's work packages back for review and approve them again."
            ),
            "Then re-run spec-kitty consolidate.",
            "",
            (
                "Both parts need their own fix, in either order: the recovery in the first part does not approve the new content, and "
                "approving the work package again does not clear the first part. Re-run spec-kitty consolidate after both."
            ),
        )
    ),
    "mixed_lane": "\n".join(
        (
            (
                "mixed lane lane-a: canceled WP02 cannot be attributed — lane-a carries commit(s) <sha> (touching "
                "'src/pkg/between.py') that lie outside every WP's recorded work window — no governed WP owns them, so canceled "
                "WP02's content cannot be told apart from approved work. No governed WP window will ever cover those commits, so "
                "re-running alone cannot clear this. Recovery: verify by hand that they carry no canceled work and that WP02's "
                "canceled content is absent or superseded, then re-run spec-kitty consolidate with --attest-canceled-superseded WP02 "
                '--attest-reason "<what you checked>".'
            ),
            "",
            "This Mission also has:",
            (
                "LANE_MOVED_AFTER_APPROVAL: commit <sha> ('src/pkg/between.py') on branch 'kitty/mission-terminus-01M6Y9P2-lane-a' "
                "(lane-a) was committed before WP01's review window opened, and no work package's newest approval comes before it, so "
                "it is in no work package's review window; see it with `git show <sha>`."
            ),
            (
                "commit <sha> ('src/pkg/wp01.py') on branch 'kitty/mission-terminus-01M6Y9P2-lane-a' (lane-a) was committed before "
                "WP01's review window opened, and no work package's newest approval comes before it, so it is in no work package's "
                "review window; see it with `git show <sha>`."
            ),
            (
                "commit <sha> ('src/pkg/canceled.py') on branch 'kitty/mission-terminus-01M6Y9P2-lane-a' (lane-a) was committed "
                "before WP01's review window opened, and no work package's newest approval comes before it, so it is in no work "
                "package's review window; see it with `git show <sha>`."
            ),
            (
                "Recovery: A commit made before a work package's review window opened is covered by no approval: approving again "
                "moves a window's end, never its start. Take the commit off the branch (for example rebuild the branch without it), "
                "then send the branch's work packages back for review and approve them again."
            ),
            "Then re-run spec-kitty consolidate.",
            "",
            (
                "Both parts need their own fix, in either order: the recovery in the first part does not approve the new content, and "
                "approving the work package again does not clear the first part. Re-run spec-kitty consolidate after both."
            ),
        )
    ),
    "bound": "\n".join(
        (
            (
                "LANE_MOVED_AFTER_APPROVAL: branch 'kitty/mission-terminus-01M6Y9P3-lane-a' (lane-a carries WP01) holds content "
                "committed after its approval stamp (the lane commit recorded when review approved it): <sha> (e.g. "
                "'src/alpha/late.py'); see one with `git show <sha>`."
            ),
            "Recovery: send WP01 back for review so the new content is reviewed:",
            "  spec-kitty agent tasks move-task WP01 --to in_progress --mission terminus-01M6Y9P3",
            "Then approve it again and re-run spec-kitty consolidate.",
            (
                "LANE_MOVED_AFTER_APPROVAL: commit <sha> ('src/pkg/between.py') on branch 'kitty/mission-terminus-01M6Y9P3-lane-b' "
                "(lane-b) was committed before WP02's review window opened, and no work package's newest approval comes before it, so "
                "it is in no work package's review window; see it with `git show <sha>`."
            ),
            (
                "commit <sha> ('src/pkg/wp02.py') on branch 'kitty/mission-terminus-01M6Y9P3-lane-b' (lane-b) was committed before "
                "WP02's review window opened, and no work package's newest approval comes before it, so it is in no work package's "
                "review window; see it with `git show <sha>`."
            ),
            (
                "Recovery: A commit made before a work package's review window opened is covered by no approval: approving again "
                "moves a window's end, never its start. Take the commit off the branch (for example rebuild the branch without it), "
                "then send the branch's work packages back for review and approve them again."
            ),
            "Then re-run spec-kitty consolidate.",
        )
    ),
}


@pytest.mark.parametrize("row", ROWS, ids=lambda row: f"{row.first}__bound_window")
def test_window_refusal_follows_the_earlier_refusal(row: WindowRow, tmp_path: Path) -> None:
    text, commits = row.builds(tmp_path)
    first = _BY_ID[row.first]

    assert first.marker in text, text
    assert WINDOW_MARKER in text, text
    marker = TIER_ONE_MARKER if row.first == "bound" else first.marker
    assert text.index(marker) < text.index(WINDOW_MARKER), f"{row.first} must precede the window refusal:\n{text}"
    if row.joiner is not None:
        head, joiner, tail = text.partition(row.joiner)
        assert joiner and first.marker in head and WINDOW_MARKER not in head, text
        assert WINDOW_MARKER in tail and tail.endswith(_BOTH_NEEDED), text
    else:
        assert _ALSO_HAS not in text, text
    normalized = normalize(text, repo=tmp_path / "repo", commits=(*commits, *_every_commit(tmp_path / "repo")))
    assert normalized == SNAPSHOTS[row.first], normalized


# --------------------------------------------------------------------------- witnesses


def _w_tier_one__window_same_lane(tmp_path: Path, *, earlier: bool, later: bool) -> str:
    """On lane-b: a commit between two cycles of WP02 (later); a commit after its newest approval (earlier). Tier 1 is returned alone."""
    mission = build_post_approval_coord_mission(tmp_path, mid8="01M6Y9W1")
    if later:
        plant_window_stray(mission, "WP02", rework_path="src/beta/restarted.py")
    if earlier:
        add_post_approval_commit(mission, LANE_B)
    return _refusal(_claim(mission, canceled=None, base=mission.coord_branch))


def _w_unresolvable_branches__window(tmp_path: Path, *, earlier: bool, later: bool) -> str:
    """Approved lane-b's branch gone (earlier) while lane-a holds a commit between two cycles of WP01 (later)."""
    mission = build_post_approval_coord_mission(tmp_path, mid8="01M6Y9W2")
    if later:
        plant_window_stray(mission, "WP01", rework_path="src/alpha/restarted.py")
    if earlier:
        _delete_lane_branch(mission, LANE_B)
    return _refusal(_claim(mission, canceled=None, base=mission.coord_branch))


def _w_window__evidence(tmp_path: Path, *, earlier: bool, later: bool) -> str:
    """Lane-a holds a commit between two cycles of WP01 (earlier); approved lane-b is emptied of its implementation (later)."""
    mission = build_post_approval_coord_mission(tmp_path, mid8="01M6Y9W3")
    if earlier:
        plant_window_stray(mission, "WP01", rework_path="src/alpha/restarted.py")
    if later:
        _empty_lane(mission, LANE_B)
    return _refusal(_claim(mission, canceled=None, base=mission.coord_branch))


@dataclass(frozen=True)
class WindowWitness:
    """*earlier*'s marker hides *later*'s; ``build(earlier=False, later=True)`` is the control that shows *later* alone."""

    earlier_marker: str
    later_marker: str
    build: Callable[..., str]
    id: str


WITNESSES: tuple[WindowWitness, ...] = (
    WindowWitness(TIER_ONE_MARKER, WINDOW_MARKER, _w_tier_one__window_same_lane, "bound_tier_one__bound_window_same_lane"),
    WindowWitness(_BY_ID["unresolvable_branches"].marker, WINDOW_MARKER, _w_unresolvable_branches__window, "unresolvable_branches__bound_window"),
    WindowWitness(WINDOW_MARKER, _BY_ID["evidence"].marker, _w_window__evidence, "bound_window__evidence"),
)


@pytest.mark.parametrize("witness", WITNESSES, ids=lambda witness: witness.id)
def test_an_earlier_refusal_hides_a_later_window_row(witness: WindowWitness, tmp_path: Path) -> None:
    (tmp_path / "control").mkdir()
    (tmp_path / "witness").mkdir()
    control = witness.build(tmp_path / "control", earlier=False, later=True)
    assert witness.later_marker in control, f"the later condition must refuse on its own, or the witness is vacuous:\n{control}"
    assert witness.earlier_marker not in control, control

    text = witness.build(tmp_path / "witness", earlier=True, later=True)
    assert witness.earlier_marker in text, text
    assert witness.later_marker not in text, f"the earlier refusal must hide the later one:\n{text}"
    assert _ALSO_HAS not in text
