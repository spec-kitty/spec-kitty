"""Refusal-precedence matrix of ``build_approved_wp_set`` (FR-017, C-006, IC-03).

``build_approved_wp_set`` refuses a claim through a fixed sequence of checks, and that
sequence **is** the refusal-precedence contract: the operator reads one refusal text per
run, so which refusal shows first (and which ones the text names together) is behaviour.
This module pins that contract *before* the claim builder is split across modules, so
moving code cannot reorder refusals unnoticed.

Today's order, read from the function (the code wins over plan IC-03's summary):

1. ``dependency_refs``: a declared ``--dependency-ref`` that cannot be honoured, or an
   unreadable status log while reading the recorded lane heads.
2. ``surface``: the coordination surface cannot be materialized.
3. ``unresolvable_branches``: an approved lane's branch is missing from git.
4. ``unreadable_canceled_dependency``: a fully-canceled dependency lane cannot be read.
5. ``canceled_dependency``: a carried canceled dependency lane cannot be attributed.
   Composes with ``bound`` (:func:`_compound_refusal`).
6. ``mixed_lane``: a mixed lane's canceled content cannot be attributed. Composes with
   ``bound``.
7. ``bound``: the approval-stamp bound refuses a lane (#5668).
8. ``evidence``: the owned-file evidence / review-independence axis refuses (#6715).
9. ``presence``: the mission-branch range the presence axis needs cannot be read.

``authored`` and ``excluded`` (the last two collectors) build the claim; they never refuse,
which differs from the IC-03 summary that lists them as refusals.

Only the two refusals that call :func:`_compound_refusal` can appear together with another
refusal, and only ever with ``bound``; every other pair is cut short by an early ``return``
of the earlier one. The co-occurring pairs are driven end to end through
``build_approved_wp_set`` with real-git fixtures; the rest are listed as data with the
short-circuit site that prevents them, a few of them with an executable witness.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import pytest

from specify_cli.consolidation.approved_bound import BoundRefusalCode
from specify_cli.consolidation.reconciliation import (
    _ALSO_HAS,
    _BOTH_NEEDED,
    ApprovedWpCommitSet,
    _BoundVerdict,
    _ClaimEventLog,
    _compound_refusal,
    build_approved_wp_set,
)
from specify_cli.consolidation.wp_evidence import IMPLEMENTATION_MISSING
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.lanes.persistence import read_lanes_json
from tests.terminus.canceled_dependency_support import LANE_B, build_canceled_dependency_mission, strip_lane_head_stamps
from tests.terminus.conftest import CoordMission, build_coord_mission_mixed_lane_canceled
from tests.terminus.conftest import _git as git
from tests.terminus.post_approval_support import add_post_approval_commit, lane_worktree

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# --------------------------------------------------------------------------- #
# T014: the inventory, in today's order
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RefusalSpec:
    """One claim-time refusal of ``build_approved_wp_set``.

    ``short_circuits`` is True when the refusal is the whole text (nothing after it is
    named); it is False for the two refusals that append the approval bound through
    ``_compound_refusal``. ``site`` names the function whose ``return`` ends the build.
    """

    id: str
    marker: str
    short_circuits: bool
    site: str


_BUILD = "build_approved_wp_set"
REFUSALS: tuple[RefusalSpec, ...] = (
    RefusalSpec("dependency_refs", "Error code: DEPENDENCY_REF_", True, f"{_BUILD}: early return after resolve_external_dependency_refs"),
    RefusalSpec("surface", "coordination surface could not be materialized", True, f"{_BUILD}: early return after materialize_snapshot"),
    RefusalSpec("unresolvable_branches", "does not exist in git", True, f"{_BUILD}: early return after _unresolvable_approved_lane_branches"),
    RefusalSpec(
        "unreadable_canceled_dependency",
        "is a dependency of a live lane but",
        True,
        f"{_BUILD}: early return after _unreadable_canceled_dependency_lanes",
    ),
    RefusalSpec("canceled_dependency", "is carried by approved lane(s)", False, f"{_BUILD}: return after _resolve_canceled_dependency_lanes via _compound_refusal"),
    RefusalSpec("mixed_lane", "mixed lane lane-", False, f"{_BUILD}: return after _resolve_mixed_lane_canceled_content via _compound_refusal"),
    RefusalSpec("bound", BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL, True, f"{_BUILD}: early return after _approved_bound_verdict"),
    RefusalSpec("evidence", IMPLEMENTATION_MISSING, True, f"{_BUILD}: early return after evaluate_evidence"),
    RefusalSpec("presence", "cannot be checked for presence on the target", True, f"{_BUILD}: early return after _presence_range_unreadable_refusal"),
)
_BY_ID = {spec.id: spec for spec in REFUSALS}
_IDS = tuple(spec.id for spec in REFUSALS)


# --------------------------------------------------------------------------- #
# T015: pairwise fixtures (a precedes b, a does not short-circuit b)
# --------------------------------------------------------------------------- #


def _status_dir(mission: CoordMission) -> Path:
    return Path(resolve_status_surface(mission.repo, mission.slug)).parent


def _claim(mission: CoordMission, *, canceled: str, base: str, refs: tuple[str, ...] = ()) -> ApprovedWpCommitSet:
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    return build_approved_wp_set(
        mission.repo,
        _status_dir(mission),
        manifest,
        coord_base_ref=base,
        excluded_canceled_wp_ids=frozenset({canceled}),
        excluded_window_base=base,
        external_dependency_refs=refs,
    )


def _refusal(claim: ApprovedWpCommitSet) -> str:
    assert claim.refusal is not None, "the fixture must produce a refusing claim"
    return str(claim.refusal)


def _pair_canceled_dependency__bound(tmp_path: Path) -> str:
    """A carried canceled dependency lane with an unstamped WP, and a late commit on the approved carrier lane."""
    built = build_canceled_dependency_mission(tmp_path, mid8="01M6Y8P1")
    strip_lane_head_stamps(built.mission, "WP01")
    add_post_approval_commit(built.mission, LANE_B)
    return _refusal(_claim(built.mission, canceled="WP01", base=built.mission.target_branch))


def _plant_straggler(mission: CoordMission, path: str) -> None:
    """Commit real content on WP02's lane after every WP window closed, and after WP01's approval."""
    git(mission.repo, "checkout", "-q", mission.lane_branches["WP02"])
    target = mission.repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{path}\n", encoding="utf-8")
    git(mission.repo, "add", path)
    git(mission.repo, "commit", "-qm", f"straggler {path}")
    git(mission.repo, "checkout", "-q", mission.target_branch)


def _pair_mixed_lane__bound(tmp_path: Path) -> str:
    """A commit outside every WP's work window on a mixed lane, made after the approved WP's approval."""
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), stamp_attribution=True, mid8="01M6Y8P2")
    _plant_straggler(mission, "src/pkg/late.py")
    return _refusal(_claim(mission, canceled="WP02", base=mission.coord_branch))


@dataclass(frozen=True)
class PairSpec:
    a: str
    b: str
    build: Callable[[Path], str]
    #: The mixed-lane / canceled-dependency refusal, then the compound join, then the bound refusal.
    joiner: str


CO_OCCURRING_PAIRS: tuple[PairSpec, ...] = (
    PairSpec("canceled_dependency", "bound", _pair_canceled_dependency__bound, f"\n\n{_ALSO_HAS}\n"),
    PairSpec("mixed_lane", "bound", _pair_mixed_lane__bound, f"\n\n{_ALSO_HAS}\n"),
)


# --------------------------------------------------------------------------- #
# T017: the pairs that cannot co-occur, each with its short-circuit site
# --------------------------------------------------------------------------- #

_CO_KEYS = frozenset((pair.a, pair.b) for pair in CO_OCCURRING_PAIRS)
NON_CO_OCCURRING: dict[tuple[str, str], str] = {(a, b): _BY_ID[a].site for a, b in combinations(_IDS, 2) if (a, b) not in _CO_KEYS}


def test_matrix_is_complete() -> None:
    """Every unordered pair of refusals is classified exactly once, in code order."""
    expected = set(combinations(_IDS, 2))
    co = {(pair.a, pair.b) for pair in CO_OCCURRING_PAIRS}
    non_co = set(NON_CO_OCCURRING)
    assert len(CO_OCCURRING_PAIRS) == len(co), "a co-occurring pair is listed twice"
    assert co.isdisjoint(non_co), "a pair is classified as both co-occurring and not"
    assert co | non_co == expected, "every unordered pair must be classified"
    assert len(expected) == len(co) + len(non_co) == len(_IDS) * (len(_IDS) - 1) // 2


def test_only_compounding_refusals_can_precede_another_refusal() -> None:
    """A co-occurring pair needs a non-short-circuiting first element, and only the bound can follow it."""
    for pair in CO_OCCURRING_PAIRS:
        assert not _BY_ID[pair.a].short_circuits, f"{pair.a} short-circuits, so {pair.b} cannot follow it"
        assert pair.b == "bound", "_compound_refusal appends the approval bound and nothing else"
    assert {spec.id for spec in REFUSALS if not spec.short_circuits} == {pair.a for pair in CO_OCCURRING_PAIRS}


# --------------------------------------------------------------------------- #
# T016: the matrix
# --------------------------------------------------------------------------- #

_SHA = re.compile(r"\b[0-9a-f]{40}\b")
_SHORT_SHA = re.compile(r"(?<![0-9A-Za-z])(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])[0-9a-f]{7,10}(?![0-9A-Za-z])")


def normalize(text: str, *, repo: Path | None = None) -> str:
    """Replace 40-hex SHAs (and 7-10 hex short SHAs) with ``<sha>``; the checkout path with ``<repo>``."""
    out = _SHA.sub("<sha>", text)
    out = _SHORT_SHA.sub("<sha>", out)
    if repo is not None:
        out = out.replace(str(repo), "<repo>")
    return out


#: The normalized full refusal text per co-occurring pair. Only SHAs and the checkout path are
#: normalized, so a wording change anywhere in either refusal, the join or the tail fails here.
_BOTH_NEEDED_LITERAL = (
    "Both parts need their own fix, in either order: the recovery in the first part does not approve the new content, "
    "and approving the work package again does not clear the first part. Re-run spec-kitty consolidate after both."
)
SNAPSHOTS: dict[tuple[str, str], str] = {
    ("canceled_dependency", "bound"): "\n".join(
        (
            "canceled WP01 (lane lane-a) is carried by approved lane(s) lane-b but cannot be attributed — WP01 in lane-a entered implementation "
            "but its lifecycle events carry no commit attribution (missions created before this change, or a transition made outside the "
            "governed workflow). This attribution evidence cannot appear later (the event log is append-only), so re-running alone cannot "
            "clear it. Recovery: verify by hand that WP01's canceled content is absent or superseded on the lane, then re-run "
            'spec-kitty consolidate with --attest-canceled-superseded WP01 --attest-reason "<what you checked>".',
            "",
            "This Mission also has:",
            "LANE_MOVED_AFTER_APPROVAL: branch 'kitty/mission-terminus-01M6Y8P1-lane-b' (lane-b carries WP02) holds content committed after its "
            "approval stamp (the lane commit recorded when review approved it): <sha> (e.g. 'src/alpha/late.py'); see one with `git show <sha>`.",
            "Recovery: send WP02 back for review so the new content is reviewed:",
            "  spec-kitty agent tasks move-task WP02 --to in_progress --mission terminus-01M6Y8P1",
            "Then approve it again and re-run spec-kitty consolidate.",
            "",
            _BOTH_NEEDED_LITERAL,
        )
    ),
    ("mixed_lane", "bound"): "\n".join(
        (
            "mixed lane lane-a: canceled WP02 cannot be attributed — lane-a carries commit(s) <sha> (touching 'src/pkg/late.py') that lie outside "
            "every WP's recorded work window — no governed WP owns them, so canceled WP02's content cannot be told apart from approved work. "
            "No governed WP window will ever cover those commits, so re-running alone cannot clear this. Recovery: verify by hand that they "
            "carry no canceled work and that WP02's canceled content is absent or superseded, then re-run spec-kitty consolidate with "
            '--attest-canceled-superseded WP02 --attest-reason "<what you checked>".',
            "",
            "This Mission also has:",
            "LANE_MOVED_AFTER_APPROVAL: branch 'kitty/mission-terminus-01M6Y8P2-lane-a' (lane-a carries WP01) holds content committed after its "
            "approval stamp (the lane commit recorded when review approved it): <sha> (e.g. 'src/pkg/late.py'); see one with `git show <sha>`.",
            "Recovery: send WP01 back for review so the new content is reviewed:",
            "  spec-kitty agent tasks move-task WP01 --to in_progress --mission terminus-01M6Y8P2",
            "Then approve it again and re-run spec-kitty consolidate.",
            "",
            _BOTH_NEEDED_LITERAL,
        )
    ),
}


def assert_precedes(text: str, first: RefusalSpec, second: RefusalSpec) -> None:
    """Both markers are present (named in the message), then *first* comes before *second*."""
    assert first.marker in text, f"the refusal text does not name {first.id} ({first.marker!r}):\n{text}"
    assert second.marker in text, f"the refusal text does not name {second.id} ({second.marker!r}):\n{text}"
    assert text.index(first.marker) < text.index(second.marker), f"{first.id} must precede {second.id}:\n{text}"


def _pair_id(pair: PairSpec) -> str:
    return f"{pair.a}__{pair.b}"


@pytest.mark.parametrize("pair", CO_OCCURRING_PAIRS, ids=_pair_id)
def test_co_occurring_pair_names_both_in_order_and_joins_them(pair: PairSpec, tmp_path: Path) -> None:
    text = pair.build(tmp_path)
    first, second = _BY_ID[pair.a], _BY_ID[pair.b]

    assert_precedes(text, first, second)

    head, joiner, tail = text.partition(pair.joiner)
    assert joiner, f"the compound join {pair.joiner!r} is missing:\n{text}"
    assert first.marker in head and second.marker not in head, "the first refusal stands unchanged before the join"
    assert second.marker in tail, "the bound refusal follows the join"
    assert tail.endswith(_BOTH_NEEDED), "the compound text ends with the both-need-fixing tail"
    assert text.count(_ALSO_HAS) == 1
    snapshot = SNAPSHOTS.get((pair.a, pair.b))
    assert normalize(text, repo=tmp_path / "repo") == snapshot, normalize(text, repo=tmp_path / "repo")


def test_swapped_order_control(tmp_path: Path) -> None:
    """The order assertion is not vacuous: asked for the reverse order of a real refusal, it fails."""
    pair = CO_OCCURRING_PAIRS[0]
    text = pair.build(tmp_path)
    first, second = _BY_ID[pair.a], _BY_ID[pair.b]

    assert_precedes(text, first, second)
    with pytest.raises(AssertionError, match="must precede"):
        assert_precedes(text, second, first)


# --------------------------------------------------------------------------- #
# The composition seam itself
# --------------------------------------------------------------------------- #


def test_compound_refusal_joins_first_and_bound_with_the_pinned_text(tmp_path: Path) -> None:
    """``_compound_refusal`` is ``first``, a blank line, the also-has line, the bound refusal, a blank line, the both-needed tail."""
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), stamp_attribution=True, mid8="01M6Y8P3")
    log = _ClaimEventLog(_status_dir(mission))
    bound = _BoundVerdict(refusal="bound refusal")

    assert _compound_refusal("first", lambda: bound, log) == f"first\n\n{_ALSO_HAS}\nbound refusal\n\n{_BOTH_NEEDED}"
    assert _compound_refusal("first", lambda: _BoundVerdict(), log) == "first"


# --------------------------------------------------------------------------- #
# Executable witnesses for some of the pairs that cannot co-occur
# --------------------------------------------------------------------------- #


def _live_conditions_mission(tmp_path: Path, mid8: str) -> CoordMission:
    """The canceled-dependency + bound conditions of :func:`_pair_canceled_dependency__bound`, left live."""
    built = build_canceled_dependency_mission(tmp_path, mid8=mid8)
    strip_lane_head_stamps(built.mission, "WP01")
    add_post_approval_commit(built.mission, LANE_B)
    return built.mission


def _witness_dependency_refs(mission: CoordMission) -> str:
    return _refusal(_claim(mission, canceled="WP01", base=mission.target_branch, refs=("no-such-dependency-ref",)))


def _witness_unresolvable_branches(mission: CoordMission) -> str:
    git(mission.repo, "worktree", "remove", "--force", str(lane_worktree(mission, LANE_B)))
    git(mission.repo, "branch", "-D", mission.lane_branches["WP02"])
    return _refusal(_claim(mission, canceled="WP01", base=mission.target_branch))


_WITNESSES = {"dependency_refs": _witness_dependency_refs, "unresolvable_branches": _witness_unresolvable_branches}


@pytest.mark.parametrize("earlier", sorted(_WITNESSES))
def test_an_early_refusal_hides_the_compounding_refusals_that_follow_it(earlier: str, tmp_path: Path) -> None:
    """With the canceled-dependency and bound conditions both live, the earlier refusal is the whole text.

    This is the executable half of the ``NON_CO_OCCURRING`` rows for these two refusals: the
    later checks hold on the same Mission, and neither marker nor the compound join appears.
    """
    mission = _live_conditions_mission(tmp_path, "01M6Y8P4" if earlier == "dependency_refs" else "01M6Y8P5")
    mission.lane_branches.setdefault("WP02", f"kitty/mission-{mission.slug}-lane-b")

    text = _WITNESSES[earlier](mission)

    assert _BY_ID[earlier].marker in text, text
    for later in ("canceled_dependency", "bound"):
        assert (earlier, later) in NON_CO_OCCURRING
        assert _BY_ID[later].marker not in text, f"{earlier} must short-circuit {later}:\n{text}"
    assert _ALSO_HAS not in text
