"""FR-006 (#5604): the gate's recovery hint names re-review for content a dropped, unreviewed merge brought in.

The reconciliation gate (and the ``--dry-run`` forecast) prints ``VerifyResult.attribution_hint``
after an un-attributable FAIL. When EVERY un-attributable item is the own content of a merge the
claim recorded in ``unreviewed_merges`` (a merge on an approved lane that no approval stamp of its
lane reaches), the way out is a review that reaches the merge, not ``--dependency-ref``. When only
SOME items are a dropped merge's content (operator ruling, review cycle 1), the re-review route is
printed for those and the ``--dependency-ref`` hint is scoped to the remaining items. Foreign content
alone, a canceled or removed-work clause, and a covering merge that names no work package keep
today's hint byte for byte.

These are renderer-level tests on hand-built claims: once the claim-time refusal of the hand
merge shape exists, this path is reachable end to end only for tool merges with own content,
merges made during a run, and frozen claims read back on ``--resume``. The last section drives
the two probe call sites against a real repository (the committed ``merge=union`` source).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import reconciliation_verifier as rv
from specify_cli.consolidation.approved_bound import move_back_command
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.reconciliation_claim_types import (
    ApprovedWpCommitSet,
    CanceledDependencyContent,
    LaneContribution,
    UnreviewedMerge,
)
from specify_cli.consolidation.reconciliation_verifier import Divergence, MergeOutcomeVerifier, VerifyResult, _with_attribution_hint
from specify_cli.consolidation.wp_attribution import CanceledPathState

SLUG = "demo-mission-01ABCDEF"

#: Today's ``--dependency-ref`` hint, byte for byte (US4 AS3: foreign content keeps it).
DEPENDENCY_REF_HINT = (
    "If a work-package branch brought an external dependency branch's newer head in, declare it and re-run: "
    "spec-kitty consolidate --dependency-ref <ref>. Only a ref the mission branch or one of its lane branches reaches, "
    "on which no commit of any mission lane or mission branch sits, is accepted — mission-authored work is never exempt."
)

MERGE_SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
OTHER_MERGE_SHA = "0f1e2d3c4b5a69788796a5b4c3d2e1f001234567"
BLOB_X = "1111111111111111111111111111111111111111"
BLOB_FOREIGN = "2222222222222222222222222222222222222222"
BLOB_Y = "3333333333333333333333333333333333333333"
PATCH_ID = "9999999999999999999999999999999999999999"

#: The evil merge of the #5604 shape: lane-a (WP01) merged with own content at ``src/x.py`` and deleted ``src/gone.py``.
MERGE = UnreviewedMerge(
    sha=MERGE_SHA,
    lane_id="lane-a",
    wp_ids=("WP01",),
    own_paths=("src/x.py", "src/gone.py"),
    own_blobs=(("src/x.py", BLOB_X),),
)
#: A second dropped merge on another lane, carrying ``src/y.py``.
OTHER_MERGE = UnreviewedMerge(
    sha=OTHER_MERGE_SHA,
    lane_id="lane-b",
    wp_ids=("WP02", "WP03"),
    own_paths=("src/y.py",),
    own_blobs=(("src/y.py", BLOB_Y),),
)

CANCELED_STATE = CanceledPathState(wp_id="WP09", lane_id="lane-c", path="src/c.py", canceled_state=BLOB_FOREIGN, pre_state=None, pre_state_by_survivor=False)
CANCELED_CARRIED = CanceledDependencyContent(wp_ids=("WP09",), canceled_lane_id="lane-c", carrier_lane_id="lane-a", path="src/c.py", state=BLOB_FOREIGN)


def _claim(*merges: UnreviewedMerge, slug: str | None = SLUG, refs: tuple[str, ...] = ()) -> ApprovedWpCommitSet:
    return ApprovedWpCommitSet(mission_slug=slug, unreviewed_merges=merges, external_dependency_refs=refs)


def _hint(divergence: Divergence, claim: ApprovedWpCommitSet) -> str | None:
    return _with_attribution_hint(VerifyResult.failed(divergence), claim).attribution_hint


def _assert_re_review(hint: str | None, merge: UnreviewedMerge) -> None:
    assert hint is not None
    assert merge.sha[:7] in hint
    assert f"lane {merge.lane_id}" in hint
    for wp_id in merge.wp_ids:
        assert wp_id in hint
        assert move_back_command(wp_id, SLUG) in hint
    assert "independent" in hint
    assert "--dependency-ref" not in hint


# --- T029: the four shapes ------------------------------------------------------------------------------


@pytest.mark.unit
def test_hand_merge_blob_names_re_review_not_dependency_ref() -> None:
    """Squash shape (#5604): the un-attributable blob is the dropped merge's own blob."""
    hint = _hint(Divergence(unattributable_blobs=(("src/x.py", BLOB_X),)), _claim(MERGE))
    _assert_re_review(hint, MERGE)


@pytest.mark.unit
def test_hand_merge_commit_names_re_review_under_merge_strategy() -> None:
    """Merge strategy: the closed world reports the merge commit itself, so the match is by SHA, not by blob."""
    hint = _hint(Divergence(unattributable_content=((MERGE_SHA, PATCH_ID),)), _claim(MERGE))
    _assert_re_review(hint, MERGE)


#: Each N4 clause beside an un-attributable blob that the dropped merge DOES cover.
MATCHED_BLOB = (("src/x.py", BLOB_X),)
N4_DIVERGENCES = [
    pytest.param(Divergence(unattributable_blobs=MATCHED_BLOB, canceled_content=(CANCELED_STATE,)), id="canceled_content"),
    pytest.param(Divergence(unattributable_blobs=MATCHED_BLOB, canceled_reachable_via_dependency=(CANCELED_CARRIED,)), id="canceled_reachable_via_dependency"),
    pytest.param(Divergence(unattributable_blobs=MATCHED_BLOB, reachable_excluded=((OTHER_MERGE_SHA, PATCH_ID),)), id="reachable_excluded"),
]


@pytest.mark.unit
@pytest.mark.parametrize("divergence", N4_DIVERGENCES)
def test_canceled_clause_suppresses_re_review_hint(divergence: Divergence) -> None:
    """N4: a divergence that also names canceled or removed work is not a re-review case.

    The mixed case keeps today's behaviour: the claim declared no dependency ref and an
    un-attributable axis is non-empty, so the ``--dependency-ref`` hint is shown, exactly as before
    this change (the canceled clause explains itself through ``describe()``).
    """
    assert _hint(divergence, _claim(MERGE)) == DEPENDENCY_REF_HINT


@pytest.mark.unit
@pytest.mark.parametrize("merges", [pytest.param((), id="no_dropped_merge"), pytest.param((MERGE,), id="dropped_merge_not_matching")])
def test_foreign_content_keeps_dependency_ref_hint(merges: tuple[UnreviewedMerge, ...]) -> None:
    hint = _hint(Divergence(unattributable_blobs=(("src/x.py", BLOB_FOREIGN),)), _claim(*merges))
    assert hint == DEPENDENCY_REF_HINT


def _remainder(count: int) -> str:
    return f"For the remaining content ({count} item(s) no dropped merge explains): {DEPENDENCY_REF_HINT}"


def _assert_partial(hint: str | None, merge: UnreviewedMerge, remaining: int) -> None:
    """Re-review for the covered part first, then the ``--dependency-ref`` hint scoped to the remainder, once."""
    assert hint is not None
    re_review, _, rest = hint.partition(" For the remaining content")
    _assert_re_review(re_review, merge)
    assert hint == f"{re_review} {_remainder(remaining)}"
    assert hint.count("--dependency-ref") == 1


@pytest.mark.unit
def test_partial_match_names_re_review_and_scopes_dependency_ref_to_the_rest() -> None:
    """One blob from the merge and one foreign blob on another path: re-review for the merge, the ref hint for the one foreign item."""
    divergence = Divergence(unattributable_blobs=(("src/x.py", BLOB_X), ("src/z.py", BLOB_FOREIGN)))
    _assert_partial(_hint(divergence, _claim(MERGE)), MERGE, remaining=1)


@pytest.mark.unit
def test_partial_match_on_one_shared_path_scopes_dependency_ref_to_the_foreign_blob() -> None:
    """Two blobs on the merge's own path: only the merge's blob is covered (blob match, not a coarse path rule)."""
    divergence = Divergence(unattributable_blobs=(("src/x.py", BLOB_X), ("src/x.py", BLOB_FOREIGN), ("src/z.py", BLOB_FOREIGN)))
    _assert_partial(_hint(divergence, _claim(MERGE)), MERGE, remaining=2)


@pytest.mark.unit
def test_partial_match_whose_covered_part_is_a_deletion() -> None:
    """The merge's own deletion is covered; a foreign commit and an unrelated deletion are the remainder."""
    divergence = Divergence(unattributable_deletions=("src/gone.py", "src/other.py"), unattributable_content=(("feedface" * 5, PATCH_ID),))
    _assert_partial(_hint(divergence, _claim(MERGE)), MERGE, remaining=2)


@pytest.mark.unit
def test_partial_match_with_a_merge_naming_no_work_package_keeps_dependency_ref_hint() -> None:
    """The empty ``wp_ids`` fallback holds for a partial match too: today's hint, unscoped."""
    orphan = UnreviewedMerge(sha=MERGE_SHA, lane_id="lane-a", wp_ids=(), own_paths=("src/x.py",), own_blobs=(("src/x.py", BLOB_X),))
    divergence = Divergence(unattributable_blobs=(("src/x.py", BLOB_X), ("src/z.py", BLOB_FOREIGN)))
    assert _hint(divergence, _claim(orphan)) == DEPENDENCY_REF_HINT


@pytest.mark.unit
def test_declared_dependency_ref_keeps_no_hint() -> None:
    result = VerifyResult.failed(Divergence(unattributable_blobs=(("src/x.py", BLOB_X),)))
    assert _with_attribution_hint(result, _claim(MERGE, refs=("dep",))) is result


@pytest.mark.unit
def test_deletion_from_merge_resolution() -> None:
    """``src/gone.py`` is an own path of the merge with no own blob: the merge deleted it."""
    hint = _hint(Divergence(unattributable_deletions=("src/gone.py",)), _claim(MERGE))
    _assert_re_review(hint, MERGE)


@pytest.mark.unit
def test_deletion_of_a_path_the_merge_wrote_keeps_dependency_ref_hint() -> None:
    """``src/x.py`` is an own path the merge WROTE (it has an own blob), so its deletion is not the merge's."""
    assert _hint(Divergence(unattributable_deletions=("src/x.py",)), _claim(MERGE)) == DEPENDENCY_REF_HINT


@pytest.mark.unit
@pytest.mark.parametrize(
    "divergence",
    [
        pytest.param(Divergence(unattributable_blobs=(("src/x.py", BLOB_X),)), id="blob"),
        pytest.param(Divergence(unattributable_content=((MERGE_SHA, PATCH_ID),)), id="commit"),
        pytest.param(Divergence(unattributable_deletions=("src/gone.py",)), id="deletion"),
        pytest.param(Divergence(unattributable_blobs=(("src/x.py", BLOB_X),), canceled_content=(CANCELED_STATE,)), id="mixed"),
    ],
)
def test_describe_is_unchanged(divergence: Divergence) -> None:
    """The hint lives only in ``attribution_hint``; the divergence and its wording are untouched."""
    before = divergence.describe()
    hinted = _with_attribution_hint(VerifyResult.failed(divergence), _claim(MERGE))
    assert hinted.divergence is divergence
    assert hinted.divergence.describe() == before
    assert hinted.recovery_guidance().startswith(f"Reconciliation FAILED: {before.rstrip('.')}. {hinted.attribution_hint} ")


@pytest.mark.unit
def test_describe_wording_of_the_blob_shape_is_pinned() -> None:
    assert Divergence(unattributable_blobs=(("src/x.py", BLOB_X),)).describe() == (
        f"file 'src/x.py' (blob {BLOB_X[:10]}) IS reachable on the target but belongs to NO approved WP — un-attributable (removed/canceled work would ship)"
    )


@pytest.mark.unit
def test_frozen_claim_without_the_field_keeps_dependency_ref_hint() -> None:
    """A claim frozen before the field existed reads back with ``unreviewed_merges=()``: today's hint, no crash."""
    assert _hint(Divergence(unattributable_content=((MERGE_SHA, PATCH_ID),)), _claim()) == DEPENDENCY_REF_HINT


@pytest.mark.unit
def test_blob_match_compares_the_full_blob_id() -> None:
    near = BLOB_X[:-1] + "2"
    assert _hint(Divergence(unattributable_blobs=(("src/x.py", near),)), _claim(MERGE)) == DEPENDENCY_REF_HINT


@pytest.mark.unit
def test_commit_match_compares_the_full_sha() -> None:
    near = MERGE_SHA[:-1] + "9"
    assert _hint(Divergence(unattributable_content=((near, PATCH_ID),)), _claim(MERGE)) == DEPENDENCY_REF_HINT


@pytest.mark.unit
def test_a_dropped_merge_naming_no_work_package_keeps_dependency_ref_hint() -> None:
    """Fail closed: a malformed entry that names no work package cannot route a re-review."""
    orphan = UnreviewedMerge(sha=MERGE_SHA, lane_id="lane-a", wp_ids=(), own_paths=("src/x.py",), own_blobs=(("src/x.py", BLOB_X),))
    assert _hint(Divergence(unattributable_blobs=(("src/x.py", BLOB_X),)), _claim(orphan)) == DEPENDENCY_REF_HINT


# --- T031: direct helper tests ----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("divergence", "expected"),
    [
        pytest.param(Divergence(unattributable_content=((MERGE_SHA, PATCH_ID),)), True, id="commit"),
        pytest.param(Divergence(unattributable_blobs=(("src/x.py", BLOB_X),)), True, id="blob"),
        pytest.param(Divergence(unattributable_deletions=("src/gone.py",)), True, id="deletion"),
        pytest.param(Divergence(), False, id="empty"),
        pytest.param(Divergence(canceled_content=(CANCELED_STATE,)), False, id="canceled_only"),
    ],
)
def test_has_unattributable(divergence: Divergence, expected: bool) -> None:
    assert rv._has_unattributable(divergence) is expected


@pytest.mark.unit
@pytest.mark.parametrize("divergence", N4_DIVERGENCES)
def test_dropped_merges_covering_is_none_for_each_n4_clause(divergence: Divergence) -> None:
    assert rv._dropped_merges_covering(divergence, _claim(MERGE)) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("divergence", "uncovered"),
    [
        pytest.param(Divergence(unattributable_blobs=(("src/x.py", BLOB_X), ("src/z.py", BLOB_FOREIGN))), 1, id="partial_blob"),
        pytest.param(Divergence(unattributable_content=((MERGE_SHA, PATCH_ID), ("feedface" * 5, PATCH_ID))), 1, id="partial_commit"),
        pytest.param(Divergence(unattributable_deletions=("src/gone.py", "src/other.py")), 1, id="partial_deletion"),
        pytest.param(Divergence(unattributable_blobs=(("src/x.py", BLOB_X),), unattributable_deletions=("src/other.py",)), 1, id="axes_mixed_one_unmatched"),
        pytest.param(Divergence(unattributable_blobs=(("src/x.py", BLOB_X),), unattributable_content=((MERGE_SHA, PATCH_ID),)), 0, id="all_covered"),
    ],
)
def test_dropped_merges_covering_a_partial_match_returns_the_covering_merge(divergence: Divergence, uncovered: int) -> None:
    """A partial match still returns the merge that covers an item; the remainder is counted separately."""
    merges = rv._dropped_merges_covering(divergence, _claim(MERGE, OTHER_MERGE))
    assert merges == (MERGE,)
    assert rv._uncovered_count(divergence, merges) == uncovered


@pytest.mark.unit
@pytest.mark.parametrize(
    "divergence",
    [
        pytest.param(Divergence(unattributable_content=(("", PATCH_ID),)), id="patch_id_only_commit"),
        pytest.param(Divergence(unattributable_deletions=("src/other.py", "src/x.py")), id="unmatched_deletions"),
        pytest.param(Divergence(unattributable_blobs=(("src/z.py", BLOB_FOREIGN),)), id="foreign_blob"),
    ],
)
def test_dropped_merges_covering_is_none_when_nothing_is_covered(divergence: Divergence) -> None:
    assert rv._dropped_merges_covering(divergence, _claim(MERGE, OTHER_MERGE)) is None


@pytest.mark.unit
def test_uncovered_count_spans_all_three_axes() -> None:
    divergence = Divergence(
        unattributable_content=((MERGE_SHA, PATCH_ID), ("feedface" * 5, PATCH_ID)),
        unattributable_blobs=(("src/y.py", BLOB_Y), ("src/y.py", BLOB_FOREIGN)),
        unattributable_deletions=("src/gone.py", "src/y.py"),
    )
    assert rv._uncovered_count(divergence, (MERGE, OTHER_MERGE)) == 3


@pytest.mark.unit
def test_dropped_merges_covering_is_none_without_dropped_merges() -> None:
    assert rv._dropped_merges_covering(Divergence(unattributable_blobs=(("src/x.py", BLOB_X),)), _claim()) is None


@pytest.mark.unit
def test_dropped_merges_covering_returns_the_covering_merges_sorted() -> None:
    """Two merges on two lanes cover one item each; an unrelated third merge is left out; order is lane, then SHA."""
    unrelated = UnreviewedMerge(sha="c" * 40, lane_id="lane-0", wp_ids=("WP07",), own_paths=("src/u.py",), own_blobs=(("src/u.py", "4" * 40),))
    divergence = Divergence(unattributable_blobs=(("src/y.py", BLOB_Y),), unattributable_content=((MERGE_SHA, PATCH_ID),))
    assert rv._dropped_merges_covering(divergence, _claim(OTHER_MERGE, unrelated, MERGE)) == (MERGE, OTHER_MERGE)


@pytest.mark.unit
def test_dropped_merges_covering_orders_merges_of_one_lane_by_sha() -> None:
    later = UnreviewedMerge(sha="f" * 40, lane_id="lane-a", wp_ids=("WP01",), own_paths=("src/w.py",), own_blobs=(("src/w.py", "5" * 40),))
    divergence = Divergence(unattributable_blobs=(("src/w.py", "5" * 40), ("src/x.py", BLOB_X)))
    assert rv._dropped_merges_covering(divergence, _claim(later, MERGE)) == (MERGE, later)


@pytest.mark.unit
def test_re_review_hint_for_one_merge() -> None:
    assert rv._re_review_hint((MERGE,), SLUG) == (
        f"Merge {MERGE_SHA[:7]} on lane lane-a (WP01) was made after that lane's last review approval and carries content of its own, "
        "so it authors nothing until a review approves it. "
        f"Route: send the work package back for rework ({move_back_command('WP01', SLUG)}), have the merge's resolution reviewed "
        "and approved again by an independent reviewer (the new approval must reach the merge), "
        f"then re-run spec-kitty consolidate --mission {SLUG}."
    )


@pytest.mark.unit
def test_re_review_hint_for_two_merges_on_one_lane() -> None:
    second = UnreviewedMerge(sha="f" * 40, lane_id="lane-a", wp_ids=("WP01",), own_paths=("src/w.py",), own_blobs=(("src/w.py", "5" * 40),))
    hint = rv._re_review_hint((MERGE, second), SLUG)
    assert f"Merge {MERGE_SHA[:7]} on lane lane-a (WP01)" in hint
    assert "Merge fffffff on lane lane-a (WP01)" in hint
    assert hint.count("Route:") == 1
    assert hint.count(move_back_command("WP01", SLUG)) == 1


@pytest.mark.unit
def test_re_review_hint_names_every_work_package_with_its_own_command() -> None:
    hint = rv._re_review_hint((OTHER_MERGE,), SLUG)
    assert "Merge 0f1e2d3 on lane lane-b (WP02, WP03)" in hint
    assert "Route: send each work package back for rework" in hint
    assert f"({move_back_command('WP02', SLUG)}; {move_back_command('WP03', SLUG)})" in hint


@pytest.mark.unit
def test_re_review_hint_without_a_mission_slug_prints_no_command() -> None:
    hint = rv._re_review_hint((MERGE,), None)
    assert "spec-kitty" not in hint
    assert "move-task" not in hint
    assert "Route: send the work package back for rework, have the merge's resolution reviewed" in hint
    assert hint.endswith("then re-run the consolidation.")


@pytest.mark.unit
def test_with_attribution_hint_uses_the_dependency_ref_constant() -> None:
    assert rv._DEPENDENCY_REF_HINT == DEPENDENCY_REF_HINT


# --- T030 step 7: the committed-attribute source at the two probe call sites -------------------------------


UNION_BYTES = "ONE\nTWO\nb\nc\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _commit_file(repo: Path, rel: str, body: str, message: str) -> str:
    (repo / rel).write_text(body, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


class _UnionRepo:
    """``one`` and ``two`` edit line 1 of ``p.py``; ``merge`` resolves them to their union; ``tip`` commits ``p.py merge=union`` on ``main``."""

    def __init__(self, root: Path) -> None:
        subprocess.run(["git", "init", "-qb", "main", str(root)], check=True)
        self.repo = root
        for key, value in (("user.email", "t@t.co"), ("user.name", "T"), ("commit.gpgsign", "false")):
            _git(root, "config", key, value)
        _commit_file(root, "p.py", "a\nb\nc\n", "base")
        _git(root, "branch", "one")
        _git(root, "branch", "two")
        _git(root, "checkout", "-q", "one")
        self.one = _commit_file(root, "p.py", "ONE\nb\nc\n", "one")
        _git(root, "checkout", "-q", "two")
        self.two = _commit_file(root, "p.py", "TWO\nb\nc\n", "two")
        _git(root, "checkout", "-q", "one")
        subprocess.run(["git", "-C", str(root), "merge", "--no-commit", "two"], capture_output=True, check=False)
        self.merge = _commit_file(root, "p.py", UNION_BYTES, "hand merge")
        self.union_blob = _git(root, "rev-parse", f"{self.merge}:p.py")
        _git(root, "checkout", "-q", "main")
        self.tip = _commit_file(root, ".gitattributes", "p.py merge=union\n", "attrs")


@pytest.fixture
def union_repo(tmp_path: Path) -> _UnionRepo:
    return _UnionRepo(tmp_path / "repo")


@pytest.mark.git_repo
def test_merge_axis_honours_a_committed_union_only_with_the_window_base(union_repo: _UnionRepo) -> None:
    """The merge axis passes ``excluded_window_base`` as the attribute source: with it the union merge is clean."""
    verifier = MergeOutcomeVerifier(union_repo.repo)
    with_base = ApprovedWpCommitSet(mission_slug=SLUG, excluded_window_base=union_repo.tip)
    assert verifier._unattributable_patch_id(union_repo.merge, with_base) is None
    without_base = ApprovedWpCommitSet(mission_slug=SLUG)
    with pytest.raises(GitProbeError, match="union"):
        verifier._unattributable_patch_id(union_repo.merge, without_base)


@pytest.mark.git_repo
def test_fold_honours_a_committed_union_only_with_the_window_base(union_repo: _UnionRepo) -> None:
    """``is_legitimate_merge_resolution`` passes ``excluded_window_base`` to the fold as the attribute source."""
    contributions = {
        "p.py": (
            LaneContribution(lane_id="lane-a", lane_commit=union_repo.one, authored_blob=_git(union_repo.repo, "rev-parse", f"{union_repo.one}:p.py")),
            LaneContribution(lane_id="lane-b", lane_commit=union_repo.two, authored_blob=_git(union_repo.repo, "rev-parse", f"{union_repo.two}:p.py")),
        )
    }
    with_base = ApprovedWpCommitSet(mission_slug=SLUG, excluded_window_base=union_repo.tip, path_contributions=contributions)
    assert rv.is_legitimate_merge_resolution(union_repo.repo, with_base, "p.py", union_repo.union_blob) is True
    without_base = ApprovedWpCommitSet(mission_slug=SLUG, path_contributions=contributions)
    with pytest.raises(GitProbeError, match="union"):
        rv.is_legitimate_merge_resolution(union_repo.repo, without_base, "p.py", union_repo.union_blob)


@pytest.mark.git_repo
def test_advisory_entry_probes_with_the_claims_attributes_source(union_repo: _UnionRepo) -> None:
    """Squad-3 A7: on a memo miss the advisory FR-006 entry probes the merge with the claim's attributes source.

    With the source the committed union stands (the merge adds nothing of its own); without it the
    probe refuses and the advisory entry is skipped.
    """
    from specify_cli.consolidation.reconciliation_authorship import _unreviewed_merge

    entry = _unreviewed_merge(union_repo.repo, union_repo.merge, "lane-a", ("WP01",), None, attributes_source=union_repo.tip)
    assert entry is not None and entry.own_paths == ()
    assert _unreviewed_merge(union_repo.repo, union_repo.merge, "lane-a", ("WP01",), None) is None
