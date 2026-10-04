"""Approved-content presence axis (#5571, mission consolidate-rc5-integrity-regressions).

``_lane_already_integrated`` skips a lane by ancestry alone, so once an operator
commits a revert of a lane's files the lane still looks integrated. The presence
axis is the backstop in ``MergeOutcomeVerifier.verify``: every approved code lane's
FINAL authored state per path must be on the target unless a later approved lane
built atop it superseded the path. These tests cover

* the pure supersession helper (ordering, deletion, rename, later window of the
  same lane, independent lanes, third content);
* the verifier step on a tiny real repository (every verdict, the fail-closed
  edges, the fold into an existing divergence);
* the allocator-faithful supersession family: a later approved WP that deletes,
  renames away or reverts passes -- through the real ``consolidate`` CLI under
  both strategies -- and each twin where the later WP is canceled or unapproved
  refuses naming the earlier WP (only approved WPs supersede).
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from specify_cli.consolidation.git_probes import _lane_already_integrated
from specify_cli.consolidation.reconciliation import (
    APPROVED_CONTENT_MISSING,
    ApprovedLaneContent,
    ApprovedWpCommitSet,
    Divergence,
    MergeOutcomeVerifier,
    MissingApprovedContent,
    VerifyResult,
    VerifyStatus,
    _describe_approved_content_missing,
    _fold_divergence,
    _order_lane_content,
    build_approved_wp_set,
    unmet_approved_content,
)
from specify_cli.consolidation.wp_attribution import CanceledPathState
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.lanes.persistence import read_lanes_json
from tests.terminus.approved_content_support import (
    ADDED_BODY,
    ADDED_PATH,
    RENAMED_PATH,
    SHARED_PATH,
    SHARED_V0,
    SHARED_V1,
    DependentEditMission,
    Edit,
    Wp02Final,
    build_dependent_edit_mission,
)
from tests.terminus.canceled_dependency_support import WP02_PATH, _commit_in
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import blob_present_at, run_terminus
from tests.terminus.mixed_lane_support import collapse

# --------------------------------------------------------------------------- #
# Pure helper: supersession
# --------------------------------------------------------------------------- #

V1, V2, V3 = "blob-v1", "blob-v2", "blob-v3"


def _content(lane_id: str, wp_ids: tuple[str, ...], state: dict[str, str | None], *, ancestors: tuple[str, ...] = ()) -> ApprovedLaneContent:
    return ApprovedLaneContent(lane_id=lane_id, wp_ids=wp_ids, ancestors=frozenset(ancestors), final_state=state)


def _unmet(contents: list[ApprovedLaneContent], target: dict[str, str | None], base: dict[str, str | None] | None = None) -> list[MissingApprovedContent]:
    base = base or {}
    missing: list[MissingApprovedContent] = unmet_approved_content(contents, target_state=lambda path: target.get(path), base_state=lambda path: base.get(path))
    return missing


@pytest.mark.fast
def test_content_on_the_target_is_not_missing() -> None:
    assert _unmet([_content("lane-a", ("WP01",), {"a.py": V1})], {"a.py": V1}) == []


@pytest.mark.fast
def test_absent_path_names_the_wp_lane_and_blob() -> None:
    missing = _unmet([_content("lane-a", ("WP01",), {"a.py": V1})], {})

    assert missing == [MissingApprovedContent(wp_ids=("WP01",), lane_ids=("lane-a",), path="a.py", expected=V1, found="absent")]


@pytest.mark.fast
def test_path_still_at_its_pre_consolidation_state_is_reported_as_unchanged() -> None:
    missing = _unmet([_content("lane-a", ("WP01",), {"a.py": V2})], {"a.py": V1}, base={"a.py": V1})

    assert [(m.path, m.found, m.expected) for m in missing] == [("a.py", "unchanged", V2)]


@pytest.mark.fast
def test_third_content_is_judged_by_the_blob_axes_not_here() -> None:
    """A merge resolution or later legitimate edit: neither absent nor untouched, so not a presence gap."""
    assert _unmet([_content("lane-a", ("WP01",), {"a.py": V2})], {"a.py": V3}, base={"a.py": V1}) == []


@pytest.mark.fast
def test_deletion_that_did_not_land_is_missing_and_one_that_landed_is_not() -> None:
    contents = [_content("lane-a", ("WP01",), {"gone.py": None})]

    assert _unmet(contents, {"gone.py": V1}, base={"gone.py": V1})[0].expected is None
    assert _unmet(contents, {}, base={"gone.py": V1}) == []


@pytest.mark.fast
def test_later_lane_that_deleted_the_path_supersedes_the_earlier_author() -> None:
    contents = [_content("lane-a", ("WP01",), {"a.py": V1}), _content("lane-b", ("WP02",), {"a.py": None}, ancestors=("lane-a",))]

    assert _unmet(contents, {}) == []


@pytest.mark.fast
def test_later_lane_that_renamed_the_path_away_supersedes_via_its_deletion_source() -> None:
    contents = [_content("lane-a", ("WP01",), {"a.py": V1}), _content("lane-b", ("WP02",), {"a.py": None, "b.py": V1}, ancestors=("lane-a",))]

    assert _unmet(contents, {"b.py": V1}) == []
    assert [m.path for m in _unmet(contents, {})] == ["b.py"], "the rename target is still required"


@pytest.mark.fast
def test_later_lane_that_reverted_the_path_supersedes_the_earlier_change() -> None:
    contents = [_content("lane-a", ("WP01",), {"a.py": V2}), _content("lane-b", ("WP02",), {"a.py": V1}, ancestors=("lane-a",))]

    assert _unmet(contents, {"a.py": V1}, base={"a.py": V1}) == []


@pytest.mark.fast
def test_the_dependent_lane_that_carries_the_path_unchanged_names_both_authors() -> None:
    """lane-b was built atop lane-a and carries its file: the verdict names the WP that authored it too."""
    contents = [_content("lane-a", ("WP01",), {"a.py": V1}), _content("lane-b", ("WP02",), {"a.py": V1}, ancestors=("lane-a",))]

    [missing] = _unmet(contents, {})

    assert missing.wp_ids == ("WP01", "WP02")
    assert missing.lane_ids == ("lane-a", "lane-b")


@pytest.mark.fast
def test_a_lane_never_supersedes_a_lane_it_does_not_depend_on() -> None:
    """Independent lanes: a later lane id is no ordering, so lane-a's content is still required."""
    contents = [_content("lane-a", ("WP01",), {"a.py": V1}), _content("lane-b", ("WP02",), {"b.py": V2})]

    assert [m.path for m in _unmet(contents, {"b.py": V2})] == ["a.py"]


@pytest.mark.fast
def test_independent_lanes_that_ended_on_different_states_need_one_of_them_or_something_else() -> None:
    contents = [_content("lane-a", ("WP01",), {"a.py": V1}), _content("lane-b", ("WP02",), {"a.py": V2})]

    assert _unmet(contents, {"a.py": V1}) == []
    assert _unmet(contents, {"a.py": V3}, base={"a.py": "v0"}) == [], "a merge resolution is the blob axes' call"
    assert {m.expected for m in _unmet(contents, {})} == {V1, V2}, "nothing at all on the target is missing either way"


@pytest.mark.fast
def test_later_work_window_of_the_same_lane_is_already_its_final_state() -> None:
    """A lane that added a file and a later WP of the same lane changed it ends on the later blob: the earlier blob is not required."""
    contents = [_content("lane-a", ("WP01", "WP02"), {"a.py": V2})]

    assert _unmet(contents, {"a.py": V2}) == []
    assert [m.expected for m in _unmet(contents, {"a.py": V1}, base={})] == []  # third content: deferred
    assert [m.expected for m in _unmet(contents, {})] == [V2]


@pytest.mark.fast
def test_skip_names_the_paths_judged_elsewhere() -> None:
    contents = [_content("lane-a", ("WP01",), {"a.py": V1, "kitty-specs/m/status.json": V1})]

    missing = unmet_approved_content(contents, target_state=lambda _p: None, base_state=lambda _p: None, skip=lambda p: p.startswith("kitty-specs/"))

    assert [m.path for m in missing] == ["a.py"]


# --------------------------------------------------------------------------- #
# Pure helper: only a lane's own net change, on a path the target left alone
# --------------------------------------------------------------------------- #

V0 = "blob-v0"
Refs = dict[str, dict[str, str | None]]


def _tracked(
    lane_id: str, wp_ids: tuple[str, ...], state: dict[str, str | None], *, ancestors: tuple[str, ...] = (), forks: dict[str, str] | None = None
) -> ApprovedLaneContent:
    """A lane as the claim builder records it: with its tip, its own base and where it left each dependency lane."""
    return ApprovedLaneContent(
        lane_id=lane_id,
        wp_ids=wp_ids,
        ancestors=frozenset(ancestors),
        final_state=state,
        tip=f"{lane_id}-tip",
        fork_point=f"{lane_id}-base",
        dependency_forks=forks or {},
    )


def _unmet_at(contents: list[ApprovedLaneContent], *, target: dict[str, str | None], base: dict[str, str | None], refs: Refs) -> list[MissingApprovedContent]:
    missing: list[MissingApprovedContent] = unmet_approved_content(
        contents, target_state=target.get, base_state=base.get, state_at=lambda ref, path: refs[ref].get(path)
    )
    return missing


@pytest.mark.fast
def test_net_change_the_target_lost_is_still_missing_when_the_lane_base_is_known() -> None:
    """The #5571 verdict survives the narrowing: the lane changed the path, the target did not, and the change is gone."""
    added = [_tracked("lane-a", ("WP01",), {"a.py": V1})]
    edited = [_tracked("lane-a", ("WP01",), {"a.py": V2})]

    [absent] = _unmet_at(added, target={}, base={}, refs={"lane-a-tip": {"a.py": V1}, "lane-a-base": {}})
    [unchanged] = _unmet_at(edited, target={"a.py": V0}, base={"a.py": V0}, refs={"lane-a-tip": {"a.py": V2}, "lane-a-base": {"a.py": V0}})

    assert (absent.found, absent.wp_ids) == ("absent", ("WP01",))
    assert (unchanged.found, unchanged.expected) == ("unchanged", V2)

    # A dependent lane's change is dropped while its dependency's landed: the target holds what lane-b started from.
    lane_a = _tracked("lane-a", ("WP01",), {"a.py": V1})
    lane_b = _tracked("lane-b", ("WP02",), {"a.py": V2}, ancestors=("lane-a",), forks={"lane-a": "lane-a-tip"})
    refs: Refs = {"lane-a-tip": {"a.py": V1}, "lane-a-base": {"a.py": V0}, "lane-b-tip": {"a.py": V2}, "lane-b-base": {"a.py": V0}}

    [dropped] = _unmet_at([lane_a, lane_b], target={"a.py": V1}, base={"a.py": V0}, refs=refs)

    assert (dropped.found, dropped.wp_ids, dropped.expected) == ("unchanged", ("WP02",), V2)


@pytest.mark.fast
def test_path_the_lane_left_net_unchanged_is_not_judged() -> None:
    """The lane ends where it started on this path: whatever the target holds, no approved change was dropped."""
    contents = [_tracked("lane-a", ("WP01",), {"a.py": V0})]
    refs: Refs = {"lane-a-tip": {"a.py": V0}, "lane-a-base": {"a.py": V0}}

    assert _unmet_at(contents, target={}, base={"a.py": V0}, refs=refs) == []


@pytest.mark.fast
@pytest.mark.parametrize("moved_to", [V3, None], ids=["edited", "deleted-or-renamed"])
def test_path_the_target_moved_since_the_lane_was_cut_is_not_judged(moved_to: str | None) -> None:
    """The target changed (or removed) the path itself: what lands is a merge resolution, which the blob axes judge."""
    contents = [_tracked("lane-a", ("WP01",), {"a.py": V1})]
    refs: Refs = {"lane-a-tip": {"a.py": V1}, "lane-a-base": {"a.py": V0}}
    moved = {"a.py": moved_to}

    assert _unmet_at(contents, target=moved, base=moved, refs=refs) == []


@pytest.mark.fast
def test_path_the_lane_tip_no_longer_holds_is_not_judged() -> None:
    """A merge on the lane's own spine took another version: the lane itself does not end on what its commits say."""
    contents = [_tracked("lane-a", ("WP01",), {"a.py": V1})]
    refs: Refs = {"lane-a-tip": {"a.py": V0}, "lane-a-base": {"a.py": V0}}

    assert _unmet_at(contents, target={"a.py": V0}, base={"a.py": V0}, refs=refs) == []


@pytest.mark.fast
def test_dependent_lane_that_only_carries_a_path_does_not_supersede_the_dependency_that_moved_on() -> None:
    """lane-a changed the path, lane-b forked carrying it, lane-a then reverted it: lane-a's later state is the mission's."""
    lane_a = _tracked("lane-a", ("WP01",), {"a.py": V0})
    lane_b = _tracked("lane-b", ("WP02",), {"a.py": V1}, ancestors=("lane-a",), forks={"lane-a": "a-when-b-forked"})
    refs: Refs = {
        "lane-a-tip": {"a.py": V0},
        "lane-a-base": {"a.py": V0},
        "lane-b-tip": {"a.py": V1},
        "lane-b-base": {"a.py": V0},
        "a-when-b-forked": {"a.py": V1},
    }

    assert _unmet_at([lane_a, lane_b], target={"a.py": V0}, base={"a.py": V0}, refs=refs) == []


@pytest.mark.fast
def test_dependent_lane_that_only_carries_a_path_leaves_the_verdict_to_its_author() -> None:
    lane_a = _tracked("lane-a", ("WP01",), {"a.py": V1})
    lane_b = _tracked("lane-b", ("WP02",), {"a.py": V1, "b.py": V2}, ancestors=("lane-a",), forks={"lane-a": "lane-a-tip"})
    refs: Refs = {"lane-a-tip": {"a.py": V1}, "lane-a-base": {}, "lane-b-tip": {"a.py": V1, "b.py": V2}, "lane-b-base": {}}

    [missing] = _unmet_at([lane_a, lane_b], target={"b.py": V2}, base={}, refs=refs)

    assert (missing.path, missing.wp_ids, missing.lane_ids) == ("a.py", ("WP01",), ("lane-a",))


@pytest.mark.fast
def test_dependent_lane_that_changed_the_path_itself_still_supersedes_its_dependency() -> None:
    lane_a = _tracked("lane-a", ("WP01",), {"a.py": V1})
    lane_b = _tracked("lane-b", ("WP02",), {"a.py": None}, ancestors=("lane-a",), forks={"lane-a": "lane-a-tip"})
    refs: Refs = {"lane-a-tip": {"a.py": V1}, "lane-a-base": {}, "lane-b-tip": {}, "lane-b-base": {}}

    assert _unmet_at([lane_a, lane_b], target={}, base={}, refs=refs) == []


@pytest.mark.fast
def test_lane_order_is_dependency_first_then_lane_id() -> None:
    contents = [
        _content("lane-c", ("WP03",), {}, ancestors=("lane-b",)),
        _content("lane-b", ("WP02",), {}, ancestors=("lane-a",)),
        _content("lane-d", ("WP04",), {}),
        _content("lane-a", ("WP01",), {}),
    ]

    assert [c.lane_id for c in _order_lane_content(contents)] == ["lane-a", "lane-d", "lane-b", "lane-c"]


@pytest.mark.fast
def test_lane_order_stays_deterministic_on_a_dependency_cycle() -> None:
    cycle = [_content("lane-b", ("WP02",), {}, ancestors=("lane-a",)), _content("lane-a", ("WP01",), {}, ancestors=("lane-b",))]

    assert [c.lane_id for c in _order_lane_content(cycle)] == ["lane-a", "lane-b"]


@pytest.mark.fast
def test_description_names_code_wp_lane_path_and_the_recovery() -> None:
    absent = MissingApprovedContent(wp_ids=("WP01",), lane_ids=("lane-a",), path="a.py", expected=V1, found="absent")
    unchanged = replace(absent, found="unchanged")
    deletion = replace(absent, expected=None, found="unchanged")

    text = _describe_approved_content_missing(absent)
    assert text.startswith(f"{APPROVED_CONTENT_MISSING}: approved WP01 (lane lane-a) file 'a.py' is absent from the target")
    assert "git reset --hard HEAD" in text and "then re-run spec-kitty consolidate" in text
    assert "the target branch did not change this path, so revert nothing there" in text, "the recovery must not read as advice to revert a target commit"
    assert text.count(";") == 1, "one ';' between the situation and the recovery"
    assert "pre-consolidation content" in _describe_approved_content_missing(unchanged)
    assert "deletion of 'a.py' is not applied" in _describe_approved_content_missing(deletion)
    assert APPROVED_CONTENT_MISSING in Divergence(approved_content_missing=(absent,)).describe()


@pytest.mark.fast
def test_fold_composes_like_the_other_divergence_folds() -> None:
    field_name = "approved_content_missing"
    entry = MissingApprovedContent(wp_ids=("WP01",), lane_ids=("lane-a",), path="a.py", expected=V1, found="absent")
    refused = VerifyResult.refused("x")

    assert _fold_divergence(refused, field_name, [entry]) is refused
    assert _fold_divergence(VerifyResult.passed(), field_name, []).is_pass
    failed = _fold_divergence(VerifyResult.passed(), field_name, [entry])
    assert failed.divergence is not None and failed.divergence.approved_content_missing == (entry,)
    existing = VerifyResult.failed(Divergence(unattributable_deletions=("z.py",)))
    combined = _fold_divergence(existing, field_name, [entry])
    assert combined.divergence is not None
    assert combined.divergence.unattributable_deletions == ("z.py",)
    assert combined.divergence.approved_content_missing == (entry,)


# --------------------------------------------------------------------------- #
# The verifier step on a tiny real repository
# --------------------------------------------------------------------------- #

pytestmark_git = [pytest.mark.integration, pytest.mark.git_repo]


def _commit(repo: Path, files: dict[str, str | None], message: str) -> str:
    for rel, text in files.items():
        if text is None:
            git(repo, "rm", "-q", rel)
            continue
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
        git(repo, "add", rel)
    git(repo, "commit", "-qm", message, "--allow-empty")
    return git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "tiny"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    _commit(repo, {"README.md": "x\n", "keep.py": "keep = 0\n"}, "base")
    return repo


def _blob(repo: Path, ref: str, path: str) -> str:
    return git(repo, "rev-parse", f"{ref}:{path}").stdout.strip()


def _claim(base: str | None, contents: tuple[ApprovedLaneContent, ...], **extra: object) -> ApprovedWpCommitSet:
    return ApprovedWpCommitSet(
        approved={"WP01": ("a" * 40,)},
        manifest_wp_ids=frozenset({"WP01"}),
        excluded_window_base=base,
        enforce_closed_world=True,
        verify_reachability=False,
        approved_lane_content=contents,
        mission_slug="m",
        planning_prefix="kitty-specs/m",
        authored_blobs=frozenset({("feature.py", "x")}),
        **extra,
    )


@pytest.mark.integration
@pytest.mark.git_repo
def test_step_reports_absent_and_unchanged_content_and_is_silent_when_present(tiny_repo: Path) -> None:
    base = git(tiny_repo, "rev-parse", "HEAD").stdout.strip()
    landed = _commit(tiny_repo, {"feature.py": "v1\n"}, "land")
    feature_blob = _blob(tiny_repo, "HEAD", "feature.py")
    verifier = MergeOutcomeVerifier(tiny_repo)
    present = (_content_for("lane-a", {"feature.py": feature_blob}),)
    absent = (_content_for("lane-a", {"other.py": feature_blob}),)
    unchanged = (_content_for("lane-a", {"keep.py": feature_blob}),)

    assert verifier._approved_content_divergence(landed, _claim(base, present)) == ([], None)
    [missing], refuse = verifier._approved_content_divergence(landed, _claim(base, absent))
    assert refuse is None and (missing.path, missing.found) == ("other.py", "absent")
    [stale], _ = verifier._approved_content_divergence(landed, _claim(base, unchanged))
    assert (stale.path, stale.found) == ("keep.py", "unchanged")


def _content_for(lane_id: str, state: dict[str, str | None]) -> ApprovedLaneContent:
    return ApprovedLaneContent(lane_id=lane_id, wp_ids=("WP01",), ancestors=frozenset(), final_state=state)


@pytest.mark.integration
@pytest.mark.git_repo
def test_step_is_a_noop_for_hand_built_claims_and_empty_content(tiny_repo: Path) -> None:
    base = git(tiny_repo, "rev-parse", "HEAD").stdout.strip()
    verifier = MergeOutcomeVerifier(tiny_repo)
    content = (_content_for("lane-a", {"missing.py": "blob"}),)

    assert verifier._approved_content_divergence(base, _claim(base, ())) == ([], None)
    assert verifier._approved_content_divergence(base, replace(_claim(base, content), enforce_closed_world=False)) == ([], None)


@pytest.mark.integration
@pytest.mark.git_repo
def test_step_refuses_without_a_window_base_and_on_a_probe_error(tiny_repo: Path) -> None:
    base = git(tiny_repo, "rev-parse", "HEAD").stdout.strip()
    verifier = MergeOutcomeVerifier(tiny_repo)
    content = (_content_for("lane-a", {"missing.py": "blob"}),)

    missing, refuse = verifier._approved_content_divergence(base, _claim(None, content))
    assert missing == [] and refuse is not None and "window base" in refuse
    missing, refuse = verifier._approved_content_divergence("refs/heads/no-such-branch", _claim(base, content))
    assert missing == [] and refuse is not None and "approved content presence" in refuse


@pytest.mark.integration
@pytest.mark.git_repo
def test_step_leaves_canceled_wp_paths_and_bookkeeping_to_their_own_axes(tiny_repo: Path) -> None:
    base = git(tiny_repo, "rev-parse", "HEAD").stdout.strip()
    verifier = MergeOutcomeVerifier(tiny_repo)
    content = (_content_for("lane-a", {"canceled.py": "blob", "kitty-specs/m/status.json": "blob", "real.py": "blob"}),)
    canceled = frozenset({CanceledPathState(wp_id="WP09", lane_id="lane-a", path="canceled.py", canceled_state="x", pre_state=None, pre_state_by_survivor=False)})

    missing, _ = verifier._approved_content_divergence(base, _claim(base, content, canceled_content=canceled))

    assert [m.path for m in missing] == ["real.py"]


@pytest.mark.integration
@pytest.mark.git_repo
def test_verify_fails_with_the_missing_content_and_rolls_up_with_other_axes(tiny_repo: Path) -> None:
    base = git(tiny_repo, "rev-parse", "HEAD").stdout.strip()
    landed = _commit(tiny_repo, {"feature.py": "v1\n"}, "land")
    claim = _claim(base, (_content_for("lane-a", {"other.py": _blob(tiny_repo, "HEAD", "feature.py")}),), authored_deletions=frozenset({"x"}))

    result = MergeOutcomeVerifier(tiny_repo).verify(landed, claim)

    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert [m.path for m in result.divergence.approved_content_missing] == ["other.py"]
    assert APPROVED_CONTENT_MISSING in result.recovery_guidance()


# --------------------------------------------------------------------------- #
# Real claim builder: lane content, supersession family, twins
# --------------------------------------------------------------------------- #


def _status_dir(built: DependentEditMission) -> Path:
    mission = built.mission
    return Path(resolve_status_surface(mission.repo, mission.slug)).parent


def _claim_for(built: DependentEditMission) -> ApprovedWpCommitSet:
    mission = built.mission
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    return build_approved_wp_set(
        mission.repo,
        _status_dir(built),
        manifest,
        coord_base_ref=mission.target_branch,
        excluded_canceled_wp_ids=frozenset(mission.canceled_wps),
        excluded_window_base=mission.target_branch,
    )


def _landed(built: DependentEditMission, strategy: str, branch: str) -> str:
    """The tip of a scratch branch where lane-b landed on the target with *strategy*."""
    repo = built.mission.repo
    git(repo, "branch", branch, built.mission.target_branch)
    git(repo, "checkout", "-q", branch)
    if strategy == "squash":
        git(repo, "merge", "--squash", built.lane_b_branch)
        git(repo, "commit", "-qm", "squash lane-b", "--allow-empty")
    else:
        git(repo, "merge", "--no-ff", "-qm", "merge lane-b", built.lane_b_branch)
    sha = built.mission.rev("HEAD")
    git(repo, "checkout", "-q", built.mission.target_branch)
    return sha


def _verify(built: DependentEditMission, strategy: str, branch: str) -> VerifyResult:
    claim = _claim_for(built)
    if strategy == "squash":
        claim = replace(claim, verify_reachability=False)
    return MergeOutcomeVerifier(built.mission.repo).verify(_landed(built, strategy, branch), claim)


_STRATEGIES = ("squash", "merge")
_EDITS: tuple[Edit, ...] = ("delete", "rename", "revert")
_AUTHORED = {"delete": ADDED_PATH, "rename": ADDED_PATH, "revert": SHARED_PATH}


@pytest.mark.integration
@pytest.mark.git_repo
def test_claim_records_each_approved_code_lane_in_dependency_order(tmp_path: Path) -> None:
    built = build_dependent_edit_mission(tmp_path, edit="rename")
    claim = _claim_for(built)

    assert [c.lane_id for c in claim.approved_lane_content] == ["lane-a", "lane-b"]
    lane_a, lane_b = claim.approved_lane_content
    assert (lane_a.wp_ids, lane_a.ancestors) == (("WP01",), frozenset())
    assert (lane_b.wp_ids, lane_b.ancestors) == (("WP02",), frozenset({"lane-a"}))
    assert set(lane_a.final_state) == {ADDED_PATH} and lane_a.final_state[ADDED_PATH] is not None
    assert lane_b.final_state[ADDED_PATH] is None, "the rename source is the later lane's final state: deleted"
    assert lane_b.final_state[RENAMED_PATH] == lane_a.final_state[ADDED_PATH]


@pytest.mark.integration
@pytest.mark.git_repo
def test_claim_records_each_lanes_tip_own_base_and_dependency_fork(tmp_path: Path) -> None:
    """What the net-change rule reads: the lane tip, the commit the lane was cut from and where it left its dependency."""
    built = build_dependent_edit_mission(tmp_path, edit="rename")
    mission = built.mission
    lane_a, lane_b = _claim_for(built).approved_lane_content
    cut_from = git(mission.repo, "merge-base", built.lane_a_branch, mission.target_branch).stdout.strip()

    assert (lane_a.tip, lane_b.tip) == (mission.rev(built.lane_a_branch), mission.rev(built.lane_b_branch))
    assert lane_a.fork_point is not None and lane_b.fork_point is not None
    assert (mission.rev(lane_a.fork_point), mission.rev(lane_b.fork_point)) == (cut_from, cut_from)
    assert lane_a.dependency_forks == {}
    assert lane_b.dependency_forks == {"lane-a": mission.rev(built.lane_a_branch)}


@pytest.mark.integration
@pytest.mark.git_repo
def test_claim_leaves_a_canceled_or_unapproved_lane_out_of_the_content(tmp_path: Path) -> None:
    for final in ("canceled", "in_progress"):
        built = build_dependent_edit_mission(tmp_path / final, edit="delete", wp02_final=final)
        assert [c.lane_id for c in _claim_for(built).approved_lane_content] == ["lane-a"], final


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("strategy", _STRATEGIES)
@pytest.mark.parametrize("edit", _EDITS)
def test_a_later_approved_wp_that_edits_the_path_supersedes_it(tmp_path: Path, edit: Edit, strategy: str) -> None:
    built = build_dependent_edit_mission(tmp_path, edit=edit, wp02_final="approved")

    result = _verify(built, strategy, "landed")

    assert result.status is VerifyStatus.PASS, result.recovery_guidance()


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("final", ["canceled", "in_progress"])
@pytest.mark.parametrize("strategy", _STRATEGIES)
@pytest.mark.parametrize("edit", _EDITS)
def test_twin_a_later_wp_that_is_not_approved_supersedes_nothing(tmp_path: Path, edit: Edit, strategy: str, final: Wp02Final) -> None:
    """Same fixture, same landed target; only WP02's approval differs, and WP01's content is now missing."""
    built = build_dependent_edit_mission(tmp_path, edit=edit, wp02_final=final)

    result = _verify(built, strategy, "landed")

    assert result.status is VerifyStatus.FAIL, result
    assert result.divergence is not None
    entries = [m for m in result.divergence.approved_content_missing if m.path == _AUTHORED[edit]]
    assert [(m.wp_ids, m.lane_ids) for m in entries] == [(("WP01",), ("lane-a",))], result.recovery_guidance()
    assert APPROVED_CONTENT_MISSING in result.recovery_guidance()


@pytest.mark.integration
@pytest.mark.git_repo
def test_the_ancestry_skip_still_fires_for_a_lane_whose_content_is_gone(tmp_path: Path) -> None:
    """The fix is the presence axis: a lane merged into the mission branch and then reverted there still reads as integrated."""
    built = build_dependent_edit_mission(tmp_path, edit="none")
    repo = built.mission.repo
    git(repo, "branch", "mission-tip", built.mission.coord_branch)
    git(repo, "checkout", "-q", "mission-tip")
    git(repo, "merge", "--no-ff", "-qm", "merge lane-a", built.lane_a_branch)
    git(repo, "rm", "-q", ADDED_PATH)
    git(repo, "commit", "-qm", "operator: commit the staged deletions")
    git(repo, "checkout", "-q", built.mission.target_branch)

    assert _lane_already_integrated(repo, built.lane_a_branch, "mission-tip")
    assert not blob_present_at(repo, "mission-tip", ADDED_PATH)


# --------------------------------------------------------------------------- #
# Through the real CLI: supersession passes, content lands
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("strategy", _STRATEGIES)
@pytest.mark.parametrize("edit", _EDITS)
def test_consolidate_cli_passes_when_a_later_approved_wp_edits_earlier_content(tmp_path: Path, edit: Edit, strategy: str) -> None:
    built = build_dependent_edit_mission(tmp_path, edit=edit, mid8="01M55713")
    mission = built.mission

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--strategy", strategy, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode == 0, f"a later approved WP's {edit} must not be refused ({strategy}):\n{flat}"
    assert APPROVED_CONTENT_MISSING not in flat
    repo, target = mission.repo, mission.target_branch
    if edit == "delete":
        assert not blob_present_at(repo, target, ADDED_PATH)
    elif edit == "rename":
        assert blob_present_at(repo, target, RENAMED_PATH) and not blob_present_at(repo, target, ADDED_PATH)
    else:
        assert git(repo, "show", f"{target}:{SHARED_PATH}").stdout == SHARED_V0


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("strategy", _STRATEGIES)
def test_consolidate_cli_lands_both_wps_when_the_later_wp_adds_its_own_file(tmp_path: Path, strategy: str) -> None:
    """Control for the control: nothing is edited, every approved file lands."""
    built = build_dependent_edit_mission(tmp_path, edit="none", mid8="01M55714")
    mission = built.mission

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--strategy", strategy, "--yes"])

    assert result.returncode == 0, collapse(result.stdout + "\n" + result.stderr)
    assert git(mission.repo, "show", f"{mission.target_branch}:{ADDED_PATH}").stdout == ADDED_BODY


MAIN_SIDE = SHARED_V0 + "\n\ndef main_side() -> int:\n    return 7\n"


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("strategy", _STRATEGIES)
def test_consolidate_cli_passes_when_the_lanes_net_no_op_meets_a_concurrent_target_change(tmp_path: Path, strategy: str) -> None:
    """WP01 changes a file, dependent approved WP02 reverts it; the target changes the same file meanwhile.

    The mission leaves the file as it found it, so the target's own change is all
    that lands: nothing approved was dropped.
    """
    built = build_dependent_edit_mission(tmp_path, edit="revert", mid8="01M55715")
    mission = built.mission
    _commit_in(mission.repo, SHARED_PATH, MAIN_SIDE, "feat: unrelated target-side change to the same file")

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--strategy", strategy, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert result.returncode == 0, f"a net no-op next to a target-side change must consolidate ({strategy}):\n{flat}"
    assert APPROVED_CONTENT_MISSING not in flat
    assert git(mission.repo, "show", f"{mission.target_branch}:{SHARED_PATH}").stdout == MAIN_SIDE


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.parametrize("strategy", _STRATEGIES)
def test_consolidate_cli_does_not_report_missing_content_when_the_target_renamed_the_path(tmp_path: Path, strategy: str) -> None:
    """WP01 modifies a file the target renames meanwhile: the approved content lands at the new path.

    Under ``merge`` that consolidates. Under ``squash`` the blob-attribution axis
    refuses the renamed blob (unchanged from before the presence axis existed), so
    only the absence of this axis's verdict is pinned there.
    """
    built = build_dependent_edit_mission(tmp_path, edit="modify", mid8="01M55716")
    mission = built.mission
    moved = "src/pkg/shared_moved.py"
    git(mission.repo, "mv", SHARED_PATH, moved)
    git(mission.repo, "commit", "-qm", "refactor: the target renames the shared file")

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--strategy", strategy, "--yes"])
    flat = collapse(result.stdout + "\n" + result.stderr)

    assert APPROVED_CONTENT_MISSING not in flat, f"a target-side rename is not dropped approved work ({strategy}):\n{flat}"
    if strategy == "merge":
        assert result.returncode == 0, flat
        assert git(mission.repo, "show", f"{mission.target_branch}:{moved}").stdout == SHARED_V1
        assert blob_present_at(mission.repo, mission.target_branch, WP02_PATH)
