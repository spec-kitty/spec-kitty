"""Claim/verdict units for the canceled-dependency hardening (#5569 follow-up, #5613).

The allocator-faithful fixture (:mod:`tests.terminus.canceled_dependency_support`)
builds the real shape -- WP01's commit fast-forwarded onto the approved WP02
lane's first-parent spine -- and these tests drive ``build_approved_wp_set`` +
``MergeOutcomeVerifier`` directly. They pin what #5613 adds on top of the
fully-canceled-lane subtraction: the stable ``CANCELED_REACHABLE_VIA_DEPENDENCY``
code next to the strategy axis's own clause, a superseded canceled dependency that
consolidates, and a legacy unstamped WP that REFUSEs until it is attested.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from specify_cli.consolidation import wp_attribution as wpa
from specify_cli.consolidation.git_probes import GitProbeError, first_parent_commits_in_range
from specify_cli.consolidation.reconciliation import (
    CANCELED_REACHABLE_VIA_DEPENDENCY,
    ApprovedWpCommitSet,
    CanceledDependencyContent,
    MergeOutcomeVerifier,
    VerifyStatus,
    _CanceledLaneQuery,
    _carried_dependency_content,
    _describe_canceled_reachable,
    build_approved_wp_set,
)
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status import read_events
from tests.terminus.canceled_dependency_support import (
    LANE_A,
    LANE_B,
    WP01_PATH,
    CanceledDependencyMission,
    build_canceled_dependency_mission,
    strip_lane_head_stamps,
)
from tests.terminus.conftest import CoordMission, PlantedChange, build_coord_mission_mixed_lane_canceled
from tests.terminus.conftest import _git as git

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_RECONCILIATION = "specify_cli.consolidation.reconciliation"


def _status_dir(mission: CoordMission) -> Path:
    """The coordination status leg (where the executor's ``run.feature_dir`` points)."""
    return Path(resolve_status_surface(mission.repo, mission.slug)).parent


def _claim(built: CanceledDependencyMission, *, excluded: frozenset[str] = frozenset({"WP01"})) -> ApprovedWpCommitSet:
    mission = built.mission
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    return build_approved_wp_set(
        mission.repo,
        _status_dir(mission),
        manifest,
        coord_base_ref=mission.target_branch,
        excluded_canceled_wp_ids=excluded,
        excluded_window_base=mission.target_branch,
    )


def _integrated_target(built: CanceledDependencyMission, *, squash: bool) -> str:
    """A real squash (or ``--no-ff`` merge) of the carrying lane onto a scratch branch cut from the target."""
    repo = built.mission.repo
    scratch = "scratch-squash" if squash else "scratch-merge"
    git(repo, "branch", scratch, built.mission.target_branch)
    git(repo, "checkout", "-q", scratch)
    if squash:
        git(repo, "merge", "--squash", built.lane_b_branch)
        git(repo, "commit", "-qm", "squash lane-b")
    else:
        git(repo, "merge", "--no-ff", "-qm", "merge lane-b", built.lane_b_branch)
    sha = built.mission.rev("HEAD")
    git(repo, "checkout", "-q", built.mission.target_branch)
    return sha


def _entry(path: str = "src/a.py", *, deleted: bool = False) -> CanceledDependencyContent:
    return CanceledDependencyContent(wp_ids=("WP01",), canceled_lane_id=LANE_A, carrier_lane_id=LANE_B, path=path, state=None if deleted else "blob")


# --------------------------------------------------------------------------- #
# The core case: the code rides along upstream's own verdict
# --------------------------------------------------------------------------- #


def test_claim_names_the_carried_content_and_keeps_the_commit_out_of_authorship(tmp_path: Path) -> None:
    built = build_canceled_dependency_mission(tmp_path)
    claim = _claim(built)

    carried = [(e.wp_ids, e.canceled_lane_id, e.carrier_lane_id, e.path) for e in claim.canceled_dependency_content]
    assert carried == [(("WP01",), LANE_A, LANE_B, WP01_PATH)]
    assert built.wp01_sha not in claim.authored_shas, "the carried canceled commit must not count as approved authorship"
    assert built.wp01_sha in claim.excluded_shas, "merge reachability must see the same commit"
    assert WP01_PATH not in {path for path, _blob in claim.authored_blobs}, "the squash blob axis must not attribute the canceled blob"
    assert claim.authored_shas, "WP02's own commits stay authored"


@pytest.mark.parametrize("squash", [True, False], ids=["squash", "merge"])
def test_verdict_fails_with_the_code_alongside_the_strategy_clause(tmp_path: Path, squash: bool) -> None:
    built = build_canceled_dependency_mission(tmp_path)
    claim = replace(_claim(built), verify_reachability=not squash)

    result = MergeOutcomeVerifier(built.mission.repo).verify(_integrated_target(built, squash=squash), claim)

    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert [(e.wp_ids, e.carrier_lane_id, e.path) for e in result.divergence.canceled_reachable_via_dependency] == [(("WP01",), LANE_B, WP01_PATH)]
    # The strategy axis's own divergence is still there: the code is added, nothing is replaced.
    if squash:
        assert [path for path, _blob in result.divergence.unattributable_blobs] == [WP01_PATH]
    else:
        assert built.wp01_sha in {sha for sha, _pid in result.divergence.reachable_excluded}
    text = result.divergence.describe()
    assert CANCELED_REACHABLE_VIA_DEPENDENCY in text and "WP01" in text and LANE_A in text and LANE_B in text and WP01_PATH in text


# --------------------------------------------------------------------------- #
# The superseded dependency upstream used to refuse
# --------------------------------------------------------------------------- #


def test_superseded_canceled_commit_stays_in_the_carrier_authorship_without_its_blob(tmp_path: Path) -> None:
    built = build_canceled_dependency_mission(tmp_path, wp02_overwrites_wp01=True)
    claim = _claim(built)
    repo = built.mission.repo

    assert built.wp01_sha in claim.authored_shas and built.wp01_sha not in claim.excluded_shas
    canceled_blob = git(repo, "rev-parse", f"{built.wp01_sha}:{WP01_PATH}").stdout.strip()
    final_blob = git(repo, "rev-parse", f"{built.lane_b_branch}:{WP01_PATH}").stdout.strip()
    assert (WP01_PATH, final_blob) in claim.authored_blobs
    assert (WP01_PATH, canceled_blob) not in claim.authored_blobs, "only the approved WP's final blob is authored"


def test_commit_superseded_on_one_carrier_but_live_on_another_stays_subtracted(tmp_path: Path) -> None:
    built = build_canceled_dependency_mission(tmp_path, wp02_overwrites_wp01=True)
    mission = built.mission
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    query = _CanceledLaneQuery(mission.repo, _status_dir(mission), manifest, {}, frozenset({"WP01"}), mission.target_branch, None, None, None)
    own = frozenset({built.wp01_sha})
    spine_b = first_parent_commits_in_range(mission.repo, mission.target_branch, built.lane_b_branch)
    carriers = {LANE_B: spine_b, "lane-c": [built.wp01_sha]}

    superseded, content = _carried_dependency_content(query, {LANE_A: own}, carriers, own)

    assert superseded == frozenset(), "live on lane-c, so it must leave every lane's authorship"
    assert [(e.carrier_lane_id, e.path) for e in content] == [("lane-c", WP01_PATH)]
    assert _carried_dependency_content(query, {LANE_A: own}, {LANE_B: spine_b}, own) == (own, frozenset())


def test_mixed_lane_claim_is_untouched(tmp_path: Path) -> None:
    """#5046 shape: no fully-canceled lane, so nothing is carried and the mixed-lane axis is unchanged."""
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[PlantedChange("src/pkg/wp02_new.py", "def wp02_new() -> str:\n    return 'x'\n")],
        mid8="01M5569M",
    )
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    claim = build_approved_wp_set(
        mission.repo,
        _status_dir(mission),
        manifest,
        coord_base_ref=mission.coord_branch,
        excluded_canceled_wp_ids=frozenset({"WP02"}),
        excluded_window_base=mission.coord_branch,
    )
    assert claim.canceled_dependency_content == frozenset()
    assert claim.canceled_content, "the mixed-lane axis still finds WP02's content"


# --------------------------------------------------------------------------- #
# Legacy unstamped WP: an attestable REFUSE, not a FAIL
# --------------------------------------------------------------------------- #


def test_attestation_lifts_the_unstamped_refusal_only_while_no_stamp_is_overridable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The lift follows the one authority (``canceled_attestation.OVERRIDABLE_REASONS``), never a second hard-wired rule."""
    built = build_canceled_dependency_mission(tmp_path, mid8="01M5569N")
    strip_lane_head_stamps(built.mission, "WP01")
    monkeypatch.setattr(f"{_RECONCILIATION}.attestation_stamps", lambda _events: {"WP01": None})
    monkeypatch.setattr(f"{_RECONCILIATION}.OVERRIDABLE_REASONS", frozenset())

    refused = _claim(built)

    assert refused.refusal is not None and "WP01" in refused.refusal and "--attest-canceled-superseded WP01" in refused.refusal


def _add_unstamped_sibling(mission: CoordMission, wp_id: str, *, like: str) -> None:
    """Append *wp_id* to the event log as a copy of *like*'s lifecycle without any ``lane_head`` stamp."""
    log = _status_dir(mission) / "status.events.jsonl"
    copies: list[str] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("wp_id") != like:
            continue
        event.update(wp_id=wp_id, event_id=f"{event['event_id'][:-3]}ZZZ", policy_metadata=None)
        copies.append(json.dumps(event, sort_keys=True))
    with log.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(copies) + "\n")


def test_attesting_an_unstamped_wp_never_lifts_a_stamped_sibling_of_the_same_canceled_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A fully-canceled lane with a stamped WP01 and an unstamped, attested WP03: WP01's commit stays out of the claim."""
    built = build_canceled_dependency_mission(tmp_path, mid8="01M5569R")
    mission = built.mission
    _add_unstamped_sibling(mission, "WP03", like="WP01")
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    two_wp_lane = replace(manifest, lanes=[replace(lane, wp_ids=("WP01", "WP03")) if lane.lane_id == LANE_A else lane for lane in manifest.lanes])
    events = read_events(_status_dir(mission))
    assert wpa.lacks_lane_head_stamps(events, "WP03") and not wpa.lacks_lane_head_stamps(events, "WP01"), "fixture precondition: one stamped, one unstamped"
    monkeypatch.setattr(f"{_RECONCILIATION}.attestation_stamps", lambda _events: {"WP03": None})

    claim = build_approved_wp_set(
        mission.repo,
        _status_dir(mission),
        two_wp_lane,
        coord_base_ref=mission.target_branch,
        excluded_canceled_wp_ids=frozenset({"WP01", "WP03"}),
        excluded_window_base=mission.target_branch,
    )

    assert claim.refusal is None, claim.refusal
    assert built.wp01_sha not in claim.authored_shas, "attesting WP03 must not turn stamped WP01's commit into approved authorship"
    assert built.wp01_sha in claim.excluded_shas
    assert [(e.wp_ids, e.path) for e in claim.canceled_dependency_content] == [(("WP01", "WP03"), WP01_PATH)]


def test_lacks_lane_head_stamps_is_event_only(tmp_path: Path) -> None:
    built = build_canceled_dependency_mission(tmp_path, mid8="01M5569X")
    mission = built.mission

    assert wpa.lacks_lane_head_stamps(read_events(_status_dir(mission)), "WP01") is False
    assert wpa.lacks_lane_head_stamps([], "WP01") is False, "a WP that never entered implementation has nothing to attribute"

    strip_lane_head_stamps(mission, "WP01")
    events = read_events(_status_dir(mission))
    assert wpa.lacks_lane_head_stamps(events, "WP01") is True
    assert wpa.lacks_lane_head_stamps(events, "WP02") is False


# --------------------------------------------------------------------------- #
# Fail-closed edges
# --------------------------------------------------------------------------- #


def test_unreadable_event_log_refuses_and_cannot_be_overridden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.status import StoreError

    built = build_canceled_dependency_mission(tmp_path, mid8="01M5569Z")

    def unreadable(_feature_dir: Path) -> list[object]:
        raise StoreError("corrupt line 3")

    monkeypatch.setattr("specify_cli.status.read_events", unreadable)
    claim = _claim(built)

    assert claim.refusal is not None
    assert "WP01" in claim.refusal and "corrupt line 3" in claim.refusal and "cannot be overridden" in claim.refusal


def test_unreadable_carrier_spine_keeps_the_stricter_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A probe error supersedes nothing: the canceled commit stays subtracted (unnamed), so the strategy axis still fails."""
    built = build_canceled_dependency_mission(tmp_path, wp02_overwrites_wp01=True, mid8="01M5569P")

    def boom(*_args: object, **_kwargs: object) -> object:
        raise GitProbeError("spine unreadable")

    monkeypatch.setattr(f"{_RECONCILIATION}.canceled_spine_content", boom)
    claim = _claim(built)

    assert claim.refusal is None
    assert built.wp01_sha not in claim.authored_shas
    assert claim.canceled_dependency_content == frozenset()


def test_verifier_step_noop_without_entries_refuses_without_window_base_and_on_probe_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    built = build_canceled_dependency_mission(tmp_path, mid8="01M5569V")
    verifier = MergeOutcomeVerifier(built.mission.repo)
    claim = _claim(built)
    target = built.mission.target_branch

    assert verifier._canceled_dependency_divergence(target, replace(claim, canceled_dependency_content=frozenset())) == ([], None)

    _, no_base = verifier._canceled_dependency_divergence(target, replace(claim, excluded_window_base=None))
    assert no_base is not None

    def boom(*_args: object, **_kwargs: object) -> str | None:
        raise GitProbeError("probe failed")

    monkeypatch.setattr(f"{_RECONCILIATION}.path_state_at", boom)
    _, probe = verifier._canceled_dependency_divergence(target, claim)
    assert probe is not None and "probe failed" in probe


def test_window_base_already_holding_the_state_is_not_a_hit(tmp_path: Path) -> None:
    built = build_canceled_dependency_mission(tmp_path, mid8="01M5569W")
    base = built.mission.rev(built.lane_b_branch)
    claim = replace(_claim(built), excluded_window_base=base)

    assert MergeOutcomeVerifier(built.mission.repo)._canceled_dependency_divergence(base, claim) == ([], None)


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


def test_canceled_spine_content_skips_merges_and_bookkeeping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    built = build_canceled_dependency_mission(tmp_path, mid8="01M5569Y")
    repo = built.mission.repo
    spine = first_parent_commits_in_range(repo, built.mission.target_branch, built.lane_b_branch)
    canceled = frozenset({built.wp01_sha})
    blob = git(repo, "rev-parse", f"{built.wp01_sha}:{WP01_PATH}").stdout.strip()

    assert wpa.canceled_spine_content(repo, spine, canceled, lambda _p: False) == (frozenset(), {WP01_PATH: (built.wp01_sha, blob)})
    # A commit touching only bookkeeping paths is neither superseded nor content.
    assert wpa.canceled_spine_content(repo, spine, canceled, lambda _p: True) == (frozenset(), {})
    # Nothing on the spine is canceled: no commit is read at all.
    assert wpa.canceled_spine_content(repo, spine, frozenset({"0" * 40}), lambda _p: False) == (frozenset(), {})

    monkeypatch.setattr(wpa, "is_merge_commit", lambda _repo, _sha: True)
    assert wpa.canceled_spine_content(repo, spine, canceled, lambda _p: False) == (frozenset(), {})


def test_describe_names_the_code_wps_lanes_and_path_and_offers_no_attestation() -> None:
    changed = _describe_canceled_reachable(_entry())
    deleted = _describe_canceled_reachable(_entry(deleted=True))
    for text in (changed, deleted):
        assert CANCELED_REACHABLE_VIA_DEPENDENCY in text and "WP01" in text and LANE_A in text and LANE_B in text and "src/a.py" in text
        assert "--attest-canceled-superseded" not in text
