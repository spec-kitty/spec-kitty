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
of the earlier one.

Pair counts: 9 refusals
make 36 unordered pairs. 2 co-occur and are driven end to end through ``build_approved_wp_set``
with real-git fixtures. The other 34 cannot co-occur, and each row of ``NON_CO_OCCURRING``
carries a ``reason``:

* ``witnessed`` (4): adjacent pairs of independent checks, each with an executable witness
  (both conditions live, the earlier marker present, the later one absent; a control run with
  only the later condition shows its marker, so the later condition is not vacuous).
* ``data_dependency`` (3): adjacent pairs whose later check consumes the earlier check's output,
  so they cannot be reordered without rewriting the code.
* ``unreachable_without_production_change`` (0): none today.
* ``transitive`` (27): non-adjacent pairs. If every adjacent pair keeps its order, transitivity
  keeps the whole order, so these need no witness of their own (a few carry an extra one).

The seven adjacent non-co-occurring pairs plus the adjacent co-occurring ``mixed_lane``/``bound``
pair make every adjacent swap fail a test.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Literal

import pytest

from specify_cli.consolidation.approved_bound import BoundRefusalCode
from specify_cli.consolidation.reconciliation import (
    _ALSO_HAS,
    _BOTH_NEEDED,
    ApprovedWpCommitSet,
    _BoundVerdict,
    _ClaimEventLog,
    _compound_refusal,
    _lane_branch_for,
    build_approved_wp_set,
)
from specify_cli.consolidation.wp_evidence import IMPLEMENTATION_MISSING
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.lanes.models import LanesManifest
from specify_cli.lanes.persistence import read_lanes_json
from tests.terminus.canceled_dependency_support import LANE_A, LANE_B, build_canceled_dependency_mission, strip_lane_head_stamps
from tests.terminus.conftest import CoordMission, build_coord_mission_mixed_lane_canceled, git_rev
from tests.terminus.conftest import _git as git
from tests.terminus.post_approval_support import add_post_approval_commit, build_post_approval_coord_mission, lane_worktree

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
_ADJACENT = frozenset(zip(_IDS, _IDS[1:], strict=False))


# --------------------------------------------------------------------------- #
# Shared fixture helpers
# --------------------------------------------------------------------------- #


def _status_dir(mission: CoordMission) -> Path:
    return Path(resolve_status_surface(mission.repo, mission.slug)).parent


def _manifest(mission: CoordMission) -> LanesManifest:
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    return manifest


def _claim(
    mission: CoordMission,
    *,
    canceled: str | None,
    base: str,
    refs: tuple[str, ...] = (),
    window_base: str | None = None,
) -> ApprovedWpCommitSet:
    """Build the claim; *base* is the mission-branch ref, *window_base* (default *base*) the claim's own base."""
    return build_approved_wp_set(
        mission.repo,
        _status_dir(mission),
        _manifest(mission),
        coord_base_ref=base,
        excluded_canceled_wp_ids=frozenset({canceled}) if canceled else frozenset(),
        excluded_window_base=window_base or base,
        external_dependency_refs=refs,
    )


def _refusal(claim: ApprovedWpCommitSet) -> str:
    assert claim.refusal is not None, "the fixture must produce a refusing claim"
    return str(claim.refusal)


def _delete_lane_branch(mission: CoordMission, lane_id: str) -> None:
    """Remove *lane_id*'s worktree and branch; the branch name comes from the manifest, never rebuilt by hand."""
    branch = _lane_branch_for(_manifest(mission), lane_id)
    worktree = lane_worktree(mission, lane_id)
    if worktree.exists():
        git(mission.repo, "worktree", "remove", "--force", str(worktree))
    git(mission.repo, "branch", "-D", branch)


def _empty_lane(mission: CoordMission, lane_id: str) -> None:
    """Reset *lane_id*'s branch to the mission branch tip: an approved lane with no implementation."""
    branch = _lane_branch_for(_manifest(mission), lane_id)
    git(mission.repo, "update-ref", f"refs/heads/{branch}", git_rev(mission.repo, mission.coord_branch))


def _corrupt_status_log(mission: CoordMission) -> None:
    log = _status_dir(mission) / "status.events.jsonl"
    log.write_text(log.read_text(encoding="utf-8") + "not json{\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# T015: pairwise fixtures (a precedes b, a does not short-circuit b)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PairResult:
    """The refusal text of a co-occurring pair, and the commits the fixture created (the only SHAs the text may print)."""

    text: str
    commits: tuple[str, ...]


def _pair_canceled_dependency__bound(tmp_path: Path) -> PairResult:
    """A carried canceled dependency lane with an unstamped WP, and a late commit on the approved carrier lane."""
    built = build_canceled_dependency_mission(tmp_path, mid8="01M6Y8P1")
    strip_lane_head_stamps(built.mission, "WP01")
    late = add_post_approval_commit(built.mission, LANE_B)
    return PairResult(_refusal(_claim(built.mission, canceled="WP01", base=built.mission.target_branch)), (late,))


def _plant_straggler(mission: CoordMission, path: str) -> str:
    """Commit real content on WP02's lane after every WP window closed, and after WP01's approval; return its SHA."""
    git(mission.repo, "checkout", "-q", mission.lane_branches["WP02"])
    target = mission.repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{path}\n", encoding="utf-8")
    git(mission.repo, "add", path)
    git(mission.repo, "commit", "-qm", f"straggler {path}")
    straggler = git_rev(mission.repo, "HEAD")
    git(mission.repo, "checkout", "-q", mission.target_branch)
    return straggler


def _pair_mixed_lane__bound(tmp_path: Path) -> PairResult:
    """A commit outside every WP's work window on a mixed lane, made after the approved WP's approval."""
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=(), stamp_attribution=True, mid8="01M6Y8P2")
    straggler = _plant_straggler(mission, "src/pkg/late.py")
    return PairResult(_refusal(_claim(mission, canceled="WP02", base=mission.coord_branch)), (straggler,))


@dataclass(frozen=True)
class PairSpec:
    a: str
    b: str
    build: Callable[[Path], PairResult]
    #: The mixed-lane / canceled-dependency refusal, then the compound join, then the bound refusal.
    joiner: str


CO_OCCURRING_PAIRS: tuple[PairSpec, ...] = (
    PairSpec("canceled_dependency", "bound", _pair_canceled_dependency__bound, f"\n\n{_ALSO_HAS}\n"),
    PairSpec("mixed_lane", "bound", _pair_mixed_lane__bound, f"\n\n{_ALSO_HAS}\n"),
)
_CO_KEYS = frozenset((pair.a, pair.b) for pair in CO_OCCURRING_PAIRS)


# --------------------------------------------------------------------------- #
# T017: executable witnesses for pairs of independent checks that cannot co-occur
# --------------------------------------------------------------------------- #

_NO_SUCH_REF = "no-such-dependency-ref"


@dataclass(frozen=True)
class Witness:
    """An executable witness that *earlier* hides *later* although both conditions hold on one Mission.

    ``build(tmp_path, earlier=..., later=...)`` builds a fresh Mission with the named conditions
    live and returns its refusal text. ``(True, True)`` is the witness; ``(False, True)`` is the
    control that proves the later condition is live and sufficient on its own, so the witness
    cannot pass merely because the later condition was destroyed (review cycle 1, issue 3).
    """

    earlier: str
    later: str
    build: Callable[..., str]

    @property
    def key(self) -> tuple[str, str]:
        return (self.earlier, self.later)


def _canceled_dependency_mission(tmp_path: Path, mid8: str) -> CoordMission:
    return build_canceled_dependency_mission(tmp_path, mid8=mid8).mission


def _w_dependency_refs__surface(tmp_path: Path, *, earlier: bool, later: bool) -> str:
    """A declared ref over an unreadable status log (earlier) is the whole text; without the ref the log is a surface refusal (later)."""
    mission = _canceled_dependency_mission(tmp_path, "01M6Y8W1")
    if later:
        _corrupt_status_log(mission)
    return _refusal(_claim(mission, canceled="WP01", base=mission.target_branch, refs=(_NO_SUCH_REF,) if earlier else ()))


def _w_unresolvable_branches__unreadable_canceled_dependency(tmp_path: Path, *, earlier: bool, later: bool) -> str:
    """Approved lane-b's branch gone (earlier) and the canceled dependency lane-a's branch gone (later): two different lanes."""
    mission = _canceled_dependency_mission(tmp_path, "01M6Y8W2")
    if earlier:
        _delete_lane_branch(mission, LANE_B)
    if later:
        _delete_lane_branch(mission, LANE_A)
    return _refusal(_claim(mission, canceled="WP01", base=mission.target_branch))


def _w_bound__evidence(tmp_path: Path, *, earlier: bool, later: bool) -> str:
    """A late commit on approved lane-a (earlier) and approved lane-b emptied of its implementation (later)."""
    mission = build_post_approval_coord_mission(tmp_path, mid8="01M6Y8W3")
    if earlier:
        add_post_approval_commit(mission, LANE_A)
    if later:
        _empty_lane(mission, LANE_B)
    return _refusal(_claim(mission, canceled=None, base=mission.coord_branch))


def _w_evidence__presence(tmp_path: Path, *, earlier: bool, later: bool) -> str:
    """Approved lane-b emptied (earlier) and a mission-branch range that cannot be read while the claim base resolves (later)."""
    mission = build_post_approval_coord_mission(tmp_path, mid8="01M6Y8W4")
    if earlier:
        _empty_lane(mission, LANE_B)
    return _refusal(_claim(mission, canceled=None, base="no-such-branch" if later else mission.coord_branch, window_base=mission.coord_branch))


def _w_dependency_refs__canceled_dependency(tmp_path: Path, *, earlier: bool, later: bool) -> str:
    mission = _canceled_dependency_mission(tmp_path, "01M6Y8W5")
    if later:
        strip_lane_head_stamps(mission, "WP01")
    return _refusal(_claim(mission, canceled="WP01", base=mission.target_branch, refs=(_NO_SUCH_REF,) if earlier else ()))


def _w_dependency_refs__bound(tmp_path: Path, *, earlier: bool, later: bool) -> str:
    mission = _canceled_dependency_mission(tmp_path, "01M6Y8W6")
    if later:
        add_post_approval_commit(mission, LANE_B)
    return _refusal(_claim(mission, canceled="WP01", base=mission.target_branch, refs=(_NO_SUCH_REF,) if earlier else ()))


def _w_unresolvable_branches__bound(tmp_path: Path, *, earlier: bool, later: bool) -> str:
    """Approved lane-b's branch gone (earlier) while approved lane-a, a different lane, holds a late commit (later)."""
    mission = build_post_approval_coord_mission(tmp_path, mid8="01M6Y8W7")
    if earlier:
        _delete_lane_branch(mission, LANE_B)
    if later:
        add_post_approval_commit(mission, LANE_A)
    return _refusal(_claim(mission, canceled=None, base=mission.coord_branch))


WITNESSES: tuple[Witness, ...] = (
    # Adjacent pairs of independent checks: each swap of two neighbours fails one of these.
    Witness("dependency_refs", "surface", _w_dependency_refs__surface),
    Witness("unresolvable_branches", "unreadable_canceled_dependency", _w_unresolvable_branches__unreadable_canceled_dependency),
    Witness("bound", "evidence", _w_bound__evidence),
    Witness("evidence", "presence", _w_evidence__presence),
    # Non-adjacent extras: implied by the adjacent chain, kept as direct evidence.
    Witness("dependency_refs", "canceled_dependency", _w_dependency_refs__canceled_dependency),
    Witness("dependency_refs", "bound", _w_dependency_refs__bound),
    Witness("unresolvable_branches", "bound", _w_unresolvable_branches__bound),
)

#: Adjacent pairs whose later check consumes the earlier check's output: they cannot be reordered
#: without rewriting the code, so a witness is impossible by construction.
_DATA_DEPENDENCY: dict[tuple[str, str], str] = {
    ("surface", "unresolvable_branches"): "unresolvable_branches reads snapshot.work_packages, the value surface materializes (materialize_snapshot)",
    ("unreadable_canceled_dependency", "canceled_dependency"): (
        "canceled_dependency reads the canceled lane's commit range (_fully_canceled_lane_commits), "
        "which yields an empty set for an unreadable lane; unreadable_canceled_dependency vets that range first"
    ),
    ("canceled_dependency", "mixed_lane"): "mixed_lane takes canceled_lane_commits=dependency.unapproved_commits, the value canceled_dependency produces",
}
#: Adjacent pairs an executable witness cannot reach without a production change, each with a one-line why.
_UNREACHABLE: dict[tuple[str, str], str] = {}

Reason = Literal["witnessed", "data_dependency", "unreachable_without_production_change", "transitive"]


@dataclass(frozen=True)
class NonCoOccurring:
    """Why two refusals never appear in one text, as data."""

    reason: Reason
    why: str
    witnesses: tuple[Witness, ...] = ()


def _non_co_occurring(a: str, b: str) -> NonCoOccurring:
    key = (a, b)
    if key in _DATA_DEPENDENCY:
        return NonCoOccurring("data_dependency", _DATA_DEPENDENCY[key])
    if key in _UNREACHABLE:
        return NonCoOccurring("unreachable_without_production_change", _UNREACHABLE[key])
    witnesses = tuple(witness for witness in WITNESSES if witness.key == key)
    return NonCoOccurring("witnessed" if key in _ADJACENT else "transitive", _BY_ID[a].site, witnesses)


NON_CO_OCCURRING: dict[tuple[str, str], NonCoOccurring] = {(a, b): _non_co_occurring(a, b) for a, b in combinations(_IDS, 2) if (a, b) not in _CO_KEYS}


def test_matrix_is_complete() -> None:
    """Every unordered pair of refusals is classified exactly once, in code order."""
    expected = set(combinations(_IDS, 2))
    co = {(pair.a, pair.b) for pair in CO_OCCURRING_PAIRS}
    non_co = set(NON_CO_OCCURRING)
    assert len(CO_OCCURRING_PAIRS) == len(co), "a co-occurring pair is listed twice"
    assert co.isdisjoint(non_co), "a pair is classified as both co-occurring and not"
    assert co | non_co == expected, "every unordered pair must be classified"
    assert len(expected) == len(co) + len(non_co) == len(_IDS) * (len(_IDS) - 1) // 2


def test_every_adjacent_swap_fails_a_test() -> None:
    """Each adjacent pair is driven end to end, witnessed, or carries a stated reason; transitivity covers the rest."""
    witness_keys = [witness.key for witness in WITNESSES]
    assert len(witness_keys) == len(set(witness_keys)), "a witness is listed twice"
    assert set(witness_keys) <= set(NON_CO_OCCURRING), "a witness must belong to a pair that cannot co-occur"
    for a, b in combinations(_IDS, 2):
        if (a, b) in _CO_KEYS:
            continue
        row = NON_CO_OCCURRING[(a, b)]
        if (a, b) not in _ADJACENT:
            assert row.reason == "transitive", f"{a}/{b} is not adjacent, so only transitivity covers it"
            continue
        assert row.reason != "transitive", f"{a}/{b} is adjacent: it needs a witness or a stated reason"
        if row.reason == "witnessed":
            assert row.witnesses, f"adjacent independent pair {a}/{b} has no executable witness"
        else:
            assert row.reason in ("data_dependency", "unreachable_without_production_change")
            assert a in row.why
            assert b in row.why, f"{a}/{b}: the reason must name both checks"
            assert not row.witnesses
    adjacent_co = _ADJACENT & _CO_KEYS
    assert adjacent_co == {("mixed_lane", "bound")}, "an adjacent co-occurring pair is pinned by its own fixture"


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
#: The abbreviation lengths the refusal texts print: ``approved_bound._SHORT_SHA`` and ``wp_attribution._short_shas``.
_SHORT_LENGTHS = (10, 7)


def normalize(text: str, *, repo: Path | None = None, commits: tuple[str, ...] = ()) -> str:
    """Replace the commits the fixture created, in full and as 10- and 7-character prefixes, with ``<sha>``; the checkout path with ``<repo>``.

    The known SHAs are replaced exactly, never guessed from a hex pattern: a short SHA made only
    of digits is as valid as any other, and a pattern that needs a letter misses it (about 7% of
    runs of the first version of this module). The 40-hex pattern stays as a backstop for a
    full SHA the fixture did not name.
    """
    out = text
    for sha in commits:
        for candidate in (sha, *(sha[:length] for length in _SHORT_LENGTHS)):
            out = re.sub(rf"(?<![0-9a-f]){re.escape(candidate)}(?![0-9a-f])", "<sha>", out)
    out = _SHA.sub("<sha>", out)
    if repo is not None:
        out = out.replace(str(repo), "<repo>")
    return out


@pytest.mark.parametrize("sha", ["1234567890123456789012345678901234567890", "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"], ids=["all-digits", "mixed"])
def test_normalize_replaces_the_known_commits_whatever_their_digits(sha: str) -> None:
    """An all-digit SHA (the flake of review cycle 1) is replaced in its 40-, 10- and 7-character forms."""
    text = f"holds content: {sha[:7]} (e.g. 'a.py'); see `git show {sha[:7]}`; commit(s) {sha[:10]} (touching 'a.py'); full {sha}."
    assert normalize(text, commits=(sha,)) == "holds content: <sha> (e.g. 'a.py'); see `git show <sha>`; commit(s) <sha> (touching 'a.py'); full <sha>."
    assert normalize("an unrelated 7654321 and abcdef0 stay", commits=(sha,)) == "an unrelated 7654321 and abcdef0 stay"


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
    result = pair.build(tmp_path)
    text = result.text
    first, second = _BY_ID[pair.a], _BY_ID[pair.b]

    assert_precedes(text, first, second)

    head, joiner, tail = text.partition(pair.joiner)
    assert joiner, f"the compound join {pair.joiner!r} is missing:\n{text}"
    assert first.marker in head and second.marker not in head, "the first refusal stands unchanged before the join"
    assert second.marker in tail, "the bound refusal follows the join"
    assert tail.endswith(_BOTH_NEEDED), "the compound text ends with the both-need-fixing tail"
    assert text.count(_ALSO_HAS) == 1
    normalized = normalize(text, repo=tmp_path / "repo", commits=result.commits)
    assert normalized == SNAPSHOTS[(pair.a, pair.b)], normalized


def test_swapped_order_control(tmp_path: Path) -> None:
    """The order assertion is not vacuous: asked for the reverse order of a real refusal, it fails."""
    pair = CO_OCCURRING_PAIRS[0]
    text = pair.build(tmp_path).text
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
# Running the witnesses
# --------------------------------------------------------------------------- #


def _witness_id(witness: Witness) -> str:
    return f"{witness.earlier}__{witness.later}"


@pytest.mark.parametrize("witness", WITNESSES, ids=_witness_id)
def test_an_earlier_refusal_hides_a_later_one_whose_condition_holds(witness: Witness, tmp_path: Path) -> None:
    """Both conditions live: the earlier refusal is the whole text. The control proves the later condition is live."""
    assert witness.key in NON_CO_OCCURRING
    earlier, later = _BY_ID[witness.earlier], _BY_ID[witness.later]

    (tmp_path / "control").mkdir()
    (tmp_path / "witness").mkdir()
    control = witness.build(tmp_path / "control", earlier=False, later=True)
    assert later.marker in control, f"the later condition ({later.id}) must refuse on its own, or the witness is vacuous:\n{control}"
    assert earlier.marker not in control

    text = witness.build(tmp_path / "witness", earlier=True, later=True)
    assert earlier.marker in text, f"{earlier.id} must be named:\n{text}"
    assert later.marker not in text, f"{earlier.id} must short-circuit {later.id}:\n{text}"
    assert _ALSO_HAS not in text
