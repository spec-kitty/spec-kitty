"""Verdict matrix, policy and opt-out of :mod:`specify_cli.git.origin_freshness` (FR-006/007/009/010/017).

Every classification test drives REAL git: a bare remote, clone A (the repository
under check) and clone B (the second clone that pushes ahead of A). The policy
tests build :class:`FreshnessVerdict` values directly because the policy is a
pure function of them.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from kernel.git.remote import tracking_ref
from kernel.git import remote as kernel_remote
from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.git.origin_freshness import (
    ORIGIN_CHECK_ENV,
    ORIGIN_LANE_DIVERGED,
    ORIGIN_LANE_STALE,
    ORIGIN_STATUS_STALE,
    ORIGIN_UNREACHABLE,
    FreshnessState,
    FreshnessVerdict,
    OriginCheckMode,
    OriginCheckSetting,
    OriginFreshnessRefused,
    ReviewLaneKind,
    approved_lane_branches,
    check_branches,
    check_mission_branches,
    enforce_merge_gate,
    plan_review_lane,
    resolve_origin_check_mode,
)
from specify_cli.lanes.persistence import read_lanes_json
from tests.terminus.conftest import _cancel_event, build_coord_mission
from tests.terminus.lanes_fixture import build_lanes_mission
from tests._support.two_clone import (
    attach_and_push,
    clone_from,
    isolated_git_env,
    make_bare_remote,
    unreachable_remote,
)

pytestmark = [pytest.mark.git_repo]

_STATUS_LOG = "status.events.jsonl"
_FLAG_WARN_SETTING = OriginCheckSetting(OriginCheckMode.WARN, "flag")
_ENFORCE_SETTING = OriginCheckSetting(OriginCheckMode.ENFORCE, "default")
_OPT_OUT_LINE = "Opt out (not recommended): --origin-check warn, or SPEC_KITTY_ORIGIN_CHECK=warn."


def _status_evidence(repo: Path, slug: str) -> FreshnessVerdict:
    """The status evidence verdict alone: the evidence half of ``check_mission_branches`` with no lanes."""
    evidence = check_mission_branches(repo, slug, lane_branches=()).evidence
    assert evidence is not None
    return evidence


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, name: str, content: str = "x", message: str | None = None) -> str:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message or f"add {name}")
    return _git(repo, "rev-parse", "HEAD")


@dataclass
class World:
    """A bare remote plus two clones of its ``main`` branch."""

    bare: Path
    a: Path
    b: Path


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    isolated_git_env(monkeypatch, tmp_path)
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True, capture_output=True)
    _git(seed, "config", "user.name", "Test User")
    _git(seed, "config", "user.email", "test@example.com")
    _commit(seed, "README.md", "seed")
    bare = make_bare_remote(tmp_path)
    attach_and_push(seed, bare, ["main"])
    return World(bare=bare, a=clone_from(bare, tmp_path / "a"), b=clone_from(bare, tmp_path / "b"))


def _push_branch(clone: Path, branch: str, name: str) -> None:
    _git(clone, "checkout", "-q", "-B", branch)
    _commit(clone, name)
    _git(clone, "push", "-q", "origin", f"{branch}:{branch}")
    _git(clone, "checkout", "-q", "main")


def _only(verdicts: list[FreshnessVerdict]) -> FreshnessVerdict:
    assert len(verdicts) == 1
    return verdicts[0]


# --------------------------------------------------------------------------- check_branches


def test_no_remote_when_repository_has_no_remotes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    repo = tmp_path / "solo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "user.email", "t@t.com")
    _commit(repo, "f")

    verdict = _only(check_branches(repo, ["main"]))

    assert verdict.state is FreshnessState.NO_REMOTE
    assert verdict.remote is None


def test_remote_missing_when_the_remote_answers_without_the_branch(world: World) -> None:
    _git(world.a, "branch", "kitty/only-here")

    verdict = _only(check_branches(world.a, ["kitty/only-here"]))

    assert verdict.state is FreshnessState.REMOTE_MISSING
    assert verdict.remote == "origin"


def test_up_to_date(world: World) -> None:
    verdict = _only(check_branches(world.a, ["main"]))

    assert (verdict.state, verdict.behind, verdict.ahead) == (FreshnessState.UP_TO_DATE, 0, 0)


def test_ahead_when_local_has_unpushed_commits(world: World) -> None:
    _commit(world.a, "local.txt")

    verdict = _only(check_branches(world.a, ["main"]))

    assert (verdict.state, verdict.behind, verdict.ahead) == (FreshnessState.AHEAD, 0, 1)


def test_behind_when_the_second_clone_pushed(world: World) -> None:
    _commit(world.b, "remote.txt")
    _git(world.b, "push", "-q", "origin", "main")
    # A tag named like the branch outranks refs/heads for a bare name; the verdict must still judge the branch.
    _git(world.a, "fetch", "-q", "origin")
    _git(world.a, "tag", "main", tracking_ref("origin", "main"))

    verdict = _only(check_branches(world.a, ["main"]))

    assert (verdict.state, verdict.behind, verdict.ahead) == (FreshnessState.BEHIND, 1, 0)
    assert _git(world.a, "rev-parse", tracking_ref("origin", "main")) == _git(world.b, "rev-parse", "HEAD")


def test_diverged_when_both_sides_have_commits(world: World) -> None:
    _commit(world.b, "remote.txt")
    _git(world.b, "push", "-q", "origin", "main")
    _commit(world.a, "local.txt")

    verdict = _only(check_branches(world.a, ["main"]))

    assert (verdict.state, verdict.behind, verdict.ahead) == (FreshnessState.DIVERGED, 1, 1)


def test_local_missing_when_only_the_remote_has_the_branch(world: World) -> None:
    _push_branch(world.b, "kitty/lane-x", "lane.txt")

    verdict = _only(check_branches(world.a, ["kitty/lane-x"]))

    assert verdict.state is FreshnessState.LOCAL_MISSING
    assert verdict.remote == "origin"


def test_unreachable_is_never_remote_missing_for_a_pushed_never_fetched_branch(world: World) -> None:
    """FR-006 key guard: a dead remote must not be read as 'the branch is absent'."""
    _push_branch(world.b, "kitty/lane-y", "lane.txt")
    _git(world.a, "branch", "kitty/lane-y", "main")
    unreachable_remote(world.a)

    verdict = _only(check_branches(world.a, ["kitty/lane-y"]))

    assert verdict.state is FreshnessState.UNREACHABLE
    assert verdict.detail


def test_a_non_origin_remote_is_named_in_the_verdict(world: World) -> None:
    _git(world.a, "remote", "rename", "origin", "upstream")
    _commit(world.b, "remote.txt")
    _git(world.b, "push", "-q", "origin", "main")

    verdict = _only(check_branches(world.a, ["main"]))

    assert verdict.remote == "upstream"
    assert verdict.state is FreshnessState.BEHIND


def test_check_branches_keeps_input_order_and_contacts_the_remote_once(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _push_branch(world.b, "kitty/lane-z", "lane.txt")
    _git(world.a, "branch", "kitty/lane-z", "main")
    from specify_cli.git import origin_freshness

    calls = {"heads": 0, "fetch": 0}
    real_heads, real_fetch = kernel_remote.remote_heads, kernel_remote.fetch_branches

    def counting_heads(*args: Any, **kwargs: Any) -> dict[str, str]:
        calls["heads"] += 1
        return real_heads(*args, **kwargs)

    def counting_fetch(*args: Any, **kwargs: Any) -> None:
        calls["fetch"] += 1
        real_fetch(*args, **kwargs)

    monkeypatch.setattr(origin_freshness, "remote_heads", counting_heads)
    monkeypatch.setattr(origin_freshness, "fetch_branches", counting_fetch)

    verdicts = check_branches(world.a, ["kitty/lane-z", "main"])

    assert [v.branch for v in verdicts] == ["kitty/lane-z", "main"]
    assert calls == {"heads": 1, "fetch": 1}


def test_check_branches_empty_input_is_empty(world: World) -> None:
    assert check_branches(world.a, []) == []


# --------------------------------------------------------------------------- evidence (lanes topology)


@dataclass
class MissionWorld:
    """A LANES mission under check (``repo``), its bare remote and a second clone."""

    repo: Path
    feature_dir: Path
    slug: str
    target_branch: str
    lane_branches: dict[str, str]
    second: Path


@pytest.fixture
def mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MissionWorld:
    """A LANES mission whose status lives on ``develop``, pushed to a bare remote with a second clone."""
    isolated_git_env(monkeypatch, tmp_path)
    built = build_lanes_mission(tmp_path / "m", wps=("WP01", "WP02"))
    bare = make_bare_remote(tmp_path)
    attach_and_push(built.repo, bare, [built.target_branch, *built.lane_branches.values()])
    _git(bare, "symbolic-ref", "HEAD", f"refs/heads/{built.target_branch}")
    return MissionWorld(
        repo=built.repo,
        feature_dir=built.feature_dir,
        slug=built.slug,
        target_branch=built.target_branch,
        lane_branches=built.lane_branches,
        second=clone_from(bare, tmp_path / "second"),
    )


def _append_status_event(clone: Path, slug: str) -> None:
    log = clone / "kitty-specs" / slug / _STATUS_LOG
    log.write_text(log.read_text(encoding="utf-8") + json.dumps({"event_id": "01EXTRA", "wp_id": "WP01"}) + "\n", encoding="utf-8")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "status: extra event")


def test_status_evidence_behind_when_the_second_clone_appended_an_event(mission: MissionWorld) -> None:
    second = mission.second
    _append_status_event(second, mission.slug)
    _git(second, "push", "-q", "origin", mission.target_branch)

    verdict = _status_evidence(mission.repo, mission.slug)

    assert verdict.state is FreshnessState.BEHIND
    assert verdict.branch == mission.target_branch
    assert verdict.behind == 1
    assert verdict.scope and _STATUS_LOG in verdict.scope


def test_status_evidence_ignores_unrelated_remote_commits(mission: MissionWorld) -> None:
    second = mission.second
    _commit(second, "src/x.py", "x = 1")
    _git(second, "push", "-q", "origin", mission.target_branch)

    verdict = _status_evidence(mission.repo, mission.slug)

    assert verdict.state is FreshnessState.UP_TO_DATE
    assert verdict.behind == 0


def test_status_evidence_local_only_commits_never_refuse(mission: MissionWorld) -> None:
    _commit(mission.repo, "src/local.py", "y = 1")

    verdict = _status_evidence(mission.repo, mission.slug)

    assert verdict.state is FreshnessState.UP_TO_DATE
    assert verdict.ahead == 1


def test_status_evidence_diverged_when_remote_status_moved_and_local_committed(mission: MissionWorld) -> None:
    _append_status_event(mission.second, mission.slug)
    _git(mission.second, "push", "-q", "origin", mission.target_branch)
    _commit(mission.repo, "src/local.py", "y = 1")

    verdict = _status_evidence(mission.repo, mission.slug)

    assert (verdict.state, verdict.behind, verdict.ahead) == (FreshnessState.DIVERGED, 1, 1)


def _write_status_log(clone: Path, slug: str, event_ids: list[str]) -> None:
    log = clone / "kitty-specs" / slug / _STATUS_LOG
    log.write_text("".join(json.dumps({"event_id": event_id, "wp_id": "WP01"}) + "\n" for event_id in event_ids), encoding="utf-8")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", f"status: {len(event_ids)} events")


def test_status_evidence_squash_with_identical_log_content_is_up_to_date(mission: MissionWorld) -> None:
    """The remote squashed the per-event commits into one: commits differ, the log content is identical."""
    _write_status_log(mission.repo, mission.slug, ["01A"])
    _write_status_log(mission.repo, mission.slug, ["01A", "01B"])
    _write_status_log(mission.second, mission.slug, ["01A", "01B"])
    _git(mission.second, "push", "-q", "origin", mission.target_branch)

    verdict = _status_evidence(mission.repo, mission.slug)

    assert verdict.state is FreshnessState.UP_TO_DATE
    assert verdict.behind == 0


def test_status_evidence_squash_with_different_log_content_still_diverges(mission: MissionWorld) -> None:
    _write_status_log(mission.repo, mission.slug, ["01A"])
    _write_status_log(mission.second, mission.slug, ["01A", "01B"])
    _git(mission.second, "push", "-q", "origin", mission.target_branch)

    verdict = _status_evidence(mission.repo, mission.slug)

    assert (verdict.state, verdict.behind) == (FreshnessState.DIVERGED, 1)


def test_status_evidence_unreachable(mission: MissionWorld) -> None:
    unreachable_remote(mission.repo)

    assert _status_evidence(mission.repo, mission.slug).state is FreshnessState.UNREACHABLE


def test_check_mission_branches_contacts_each_remote_once_for_evidence_and_lanes(mission: MissionWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.git import origin_freshness

    calls = {"heads": 0, "fetch": 0}
    real_heads, real_fetch = kernel_remote.remote_heads, kernel_remote.fetch_branches

    def counting_heads(*args: Any, **kwargs: Any) -> dict[str, str]:
        calls["heads"] += 1
        return real_heads(*args, **kwargs)

    def counting_fetch(*args: Any, **kwargs: Any) -> None:
        calls["fetch"] += 1
        real_fetch(*args, **kwargs)

    monkeypatch.setattr(origin_freshness, "remote_heads", counting_heads)
    monkeypatch.setattr(origin_freshness, "fetch_branches", counting_fetch)

    result = check_mission_branches(mission.repo, mission.slug, lane_branches=list(mission.lane_branches.values()))

    assert calls == {"heads": 1, "fetch": 1}
    assert result.evidence is not None
    assert result.evidence.state is FreshnessState.UP_TO_DATE
    assert [v.state for v in result.lanes] == [FreshnessState.UP_TO_DATE, FreshnessState.UP_TO_DATE]
    assert [v.branch for v in result.lanes] == list(mission.lane_branches.values())


def test_check_mission_branches_scopes_evidence_but_not_lanes(mission: MissionWorld) -> None:
    lane = mission.lane_branches["WP01"]
    _git(mission.second, "checkout", "-q", lane)
    _commit(mission.second, "src/more.py", "z = 1")
    _git(mission.second, "push", "-q", "origin", lane)
    _git(mission.second, "checkout", "-q", mission.target_branch)
    _commit(mission.second, "src/unrelated.py", "q = 1")
    _git(mission.second, "push", "-q", "origin", mission.target_branch)

    result = check_mission_branches(mission.repo, mission.slug, lane_branches=[lane])

    assert result.evidence is not None
    assert result.evidence.state is FreshnessState.UP_TO_DATE
    assert result.lanes[0].state is FreshnessState.BEHIND


def test_check_mission_branches_leaves_an_unnameable_evidence_branch_to_the_caller(mission: MissionWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    """A placement refusal (e.g. a deleted coordination branch) yields no evidence verdict; lanes are still checked."""
    from mission_runtime import ActionContextError
    from specify_cli.git import origin_freshness

    def refusing_seam(*args: Any, **kwargs: Any) -> Any:
        raise ActionContextError("COORDINATION_BRANCH_DELETED", "declared in meta.json but deleted from git")

    monkeypatch.setattr(origin_freshness, "placement_seam", refusing_seam)
    lane = mission.lane_branches["WP01"]

    result = check_mission_branches(mission.repo, mission.slug, lane_branches=[lane])

    assert result.evidence is None
    assert [v.state for v in result.lanes] == [FreshnessState.UP_TO_DATE]


def test_check_mission_branches_unreachable_marks_everything_unreachable(mission: MissionWorld) -> None:
    unreachable_remote(mission.repo)

    result = check_mission_branches(mission.repo, mission.slug, lane_branches=list(mission.lane_branches.values()))

    assert result.evidence.state is FreshnessState.UNREACHABLE
    assert {v.state for v in result.lanes} == {FreshnessState.UNREACHABLE}


def test_coordination_local_missing_is_returned_and_write_target_stays_benign(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A fetched ``refs/remotes/<r>/<coord>`` leaves ``write_target`` (the #4979 probe) benign; the verdict is passed through."""
    isolated_git_env(monkeypatch, tmp_path)
    coord = build_coord_mission(tmp_path / "c", wps=("WP01",))
    bare = make_bare_remote(tmp_path)
    attach_and_push(coord.repo, bare, [coord.target_branch, coord.coord_branch])
    for line in _git(coord.repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree ") and Path(line.split(" ", 1)[1]) != coord.repo:
            _git(coord.repo, "worktree", "remove", "--force", line.split(" ", 1)[1])
    _git(coord.repo, "branch", "-D", coord.coord_branch)
    before = placement_seam(coord.repo, coord.slug).write_target(MissionArtifactKind.STATUS_STATE).ref

    verdict = _status_evidence(coord.repo, coord.slug)

    assert verdict.branch == before == coord.coord_branch
    assert verdict.state is FreshnessState.LOCAL_MISSING
    assert placement_seam(coord.repo, coord.slug).write_target(MissionArtifactKind.STATUS_STATE).ref == before


# --------------------------------------------------------------------------- approved_lane_branches


def test_approved_lane_branches_selects_code_lanes_and_honours_resume(mission: MissionWorld) -> None:
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None

    selected = approved_lane_branches(mission.repo, mission.slug, manifest)
    assert selected == list(mission.lane_branches.values())

    resumed = approved_lane_branches(mission.repo, mission.slug, manifest, completed_wps=frozenset({"WP01"}))
    assert resumed == [mission.lane_branches["WP02"]]


def test_approved_lane_branches_skips_planning_and_fully_canceled_lanes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    isolated_git_env(monkeypatch, tmp_path)
    built = build_lanes_mission(tmp_path / "m", wps=("WP01", "WP02"), with_planning_lane_wp=True)
    log = built.feature_dir / _STATUS_LOG
    canceled = _cancel_event(built, "WP02", from_lane="approved")
    log.write_text(log.read_text(encoding="utf-8") + json.dumps(canceled, sort_keys=True) + "\n", encoding="utf-8")
    manifest = read_lanes_json(built.feature_dir)
    assert manifest is not None

    assert approved_lane_branches(built.repo, built.slug, manifest) == [built.lane_branches["WP01"]]


def test_approved_lane_branches_over_selects_when_status_is_unreadable(mission: MissionWorld) -> None:
    (mission.feature_dir / _STATUS_LOG).write_text("not json\n", encoding="utf-8")
    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None

    assert approved_lane_branches(mission.repo, mission.slug, manifest) == list(mission.lane_branches.values())


def test_approved_lane_branches_over_selects_when_the_coordination_worktree_is_unmaterialized(mission: MissionWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    """A removed coordination worktree is a status read refusal the selection absorbs, never a crash (#5780)."""
    from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized

    manifest = read_lanes_json(mission.feature_dir)
    assert manifest is not None
    unmaterialized = CoordinationWorktreeUnmaterialized.for_mission(
        repo_root=mission.repo,
        mission_slug=mission.slug,
        mid8="01M5001A",
        coordination_branch="kitty/mission-x",
        primary_candidate=mission.feature_dir,
    )

    def refuse(*args: object, **kwargs: object) -> None:
        raise unmaterialized

    monkeypatch.setattr("specify_cli.git.origin_freshness.read_events", refuse)
    assert approved_lane_branches(mission.repo, mission.slug, manifest) == list(mission.lane_branches.values())


# --------------------------------------------------------------------------- mode


def test_mode_flag_beats_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ORIGIN_CHECK_ENV, "warn")

    setting = resolve_origin_check_mode("enforce")

    assert (setting.mode, setting.source, setting.warning) == (OriginCheckMode.ENFORCE, "flag", None)


def test_mode_environment_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ORIGIN_CHECK_ENV, "warn")

    setting = resolve_origin_check_mode(None)

    assert (setting.mode, setting.source) == (OriginCheckMode.WARN, "environment")


def test_mode_default_is_enforce(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ORIGIN_CHECK_ENV, raising=False)

    setting = resolve_origin_check_mode(None)

    assert (setting.mode, setting.source, setting.warning) == (OriginCheckMode.ENFORCE, "default", None)


def test_mode_unknown_environment_value_enforces_with_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ORIGIN_CHECK_ENV, "bogus")

    setting = resolve_origin_check_mode(None)

    assert setting.mode is OriginCheckMode.ENFORCE
    assert setting.warning is not None and "bogus" in setting.warning and ORIGIN_CHECK_ENV in setting.warning


def test_mode_unknown_flag_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="bogus"):
        resolve_origin_check_mode("bogus")


# --------------------------------------------------------------------------- enforce_merge_gate


def _verdict(state: FreshnessState, branch: str = "kitty/lane-a", *, behind: int = 0, ahead: int = 0, detail: str | None = None) -> FreshnessVerdict:
    return FreshnessVerdict(branch=branch, remote="origin", state=state, behind=behind, ahead=ahead, detail=detail)


def _gate(
    *,
    evidence: FreshnessVerdict | None = None,
    lanes: tuple[FreshnessVerdict, ...] = (),
    setting: OriginCheckSetting = _ENFORCE_SETTING,
    merge_record_exists: bool = False,
    evidence_checkout: Path | None = Path("/work/repo"),
) -> list[str]:
    warnings: list[str] = enforce_merge_gate(
        evidence=evidence,
        lanes=lanes,
        setting=setting,
        merge_record_exists=merge_record_exists,
        evidence_checkout=evidence_checkout,
    )
    return warnings


@pytest.mark.parametrize("state", [FreshnessState.UP_TO_DATE, FreshnessState.AHEAD, FreshnessState.REMOTE_MISSING, FreshnessState.NO_REMOTE])
def test_gate_passes_for_non_stale_states(state: FreshnessState) -> None:
    assert _gate(evidence=_verdict(state, "develop"), lanes=(_verdict(state),)) == []


def test_gate_with_nothing_to_check_passes() -> None:
    assert _gate() == []


@pytest.mark.parametrize("state", [FreshnessState.BEHIND, FreshnessState.DIVERGED, FreshnessState.LOCAL_MISSING])
def test_gate_refuses_stale_status_evidence(state: FreshnessState) -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(evidence=_verdict(state, "develop", behind=2, ahead=1 if state is FreshnessState.DIVERGED else 0))

    assert caught.value.error_code == ORIGIN_STATUS_STALE
    assert caught.value.error_codes == [ORIGIN_STATUS_STALE]
    assert caught.value.verdicts[0].branch == "develop"


@pytest.mark.parametrize("state", [FreshnessState.BEHIND, FreshnessState.DIVERGED, FreshnessState.LOCAL_MISSING])
def test_gate_refuses_stale_lanes(state: FreshnessState) -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(lanes=(_verdict(state, behind=3),))

    assert caught.value.error_code == ORIGIN_LANE_STALE


def test_gate_refuses_unreachable_for_evidence_and_lanes() -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(evidence=_verdict(FreshnessState.UNREACHABLE, "develop", detail="timed out"), lanes=(_verdict(FreshnessState.UNREACHABLE, detail="timed out"),))

    assert caught.value.error_code == ORIGIN_UNREACHABLE
    assert caught.value.error_codes == [ORIGIN_UNREACHABLE]
    assert "timed out" in str(caught.value)


def test_gate_lists_every_distinct_code_evidence_first() -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(
            evidence=_verdict(FreshnessState.BEHIND, "develop", behind=1),
            lanes=(_verdict(FreshnessState.BEHIND, "kitty/lane-a", behind=2), _verdict(FreshnessState.BEHIND, "kitty/lane-b", behind=1)),
        )

    assert caught.value.error_codes == [ORIGIN_STATUS_STALE, ORIGIN_LANE_STALE]
    assert caught.value.error_code == ORIGIN_STATUS_STALE
    assert len(caught.value.verdicts) == 3


def test_status_refusal_text_names_branch_counts_remote_remedy_and_opt_out() -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(evidence=_verdict(FreshnessState.BEHIND, "develop", behind=2, ahead=1), evidence_checkout=Path("/work/repo"))

    lines = str(caught.value).splitlines()
    assert lines[0] == f"{ORIGIN_STATUS_STALE}: develop is behind (2 behind / 1 ahead of origin/develop)"
    assert "git -C /work/repo pull origin develop" in str(caught.value)
    assert lines[-1] == _OPT_OUT_LINE


def test_status_refusal_with_merge_record_starts_remedy_with_abort() -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(evidence=_verdict(FreshnessState.BEHIND, "develop", behind=1), merge_record_exists=True)

    text = str(caught.value)
    abort_at = text.index("spec-kitty consolidate --abort")
    assert abort_at < text.index("git -C /work/repo pull origin develop") < text.index("spec-kitty consolidate\n")


def test_status_refusal_without_a_holding_checkout_fast_forwards_the_branch_ref() -> None:
    """No checkout holds the branch: `git pull` in the root checkout would merge it into the current branch."""
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(evidence=_verdict(FreshnessState.BEHIND, "kitty/mission-x", behind=1), evidence_checkout=None)

    text = str(caught.value)
    assert "git fetch origin kitty/mission-x:kitty/mission-x" in text
    assert "git pull" not in text


def test_status_refusal_with_a_merge_record_and_no_checkout_still_aborts_first() -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(evidence=_verdict(FreshnessState.BEHIND, "develop", behind=1), merge_record_exists=True, evidence_checkout=None)

    lines = str(caught.value).splitlines()
    assert lines[1] == "  A consolidation record exists. Recover with:"
    assert lines[2] == "    spec-kitty consolidate --abort"
    assert lines[3] == "    git fetch origin develop:develop"


def test_diverged_status_with_a_holding_checkout_merges_explicitly() -> None:
    """A plain `git pull` aborts on git >= 2.33 without pull.rebase, so a diverged branch is pulled with --no-rebase."""
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(evidence=_verdict(FreshnessState.DIVERGED, "develop", behind=1, ahead=2), evidence_checkout=Path("/work/repo"))

    text = str(caught.value)
    assert "git -C /work/repo pull --no-rebase origin develop" in text
    assert "git fetch origin develop:develop" not in text


def test_diverged_status_without_a_holder_says_to_check_the_branch_out_first() -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(evidence=_verdict(FreshnessState.DIVERGED, "kitty/mission-x", behind=1, ahead=1), evidence_checkout=None)

    text = str(caught.value)
    assert "git worktree add <path> kitty/mission-x" in text
    assert "git switch kitty/mission-x" in text
    assert text.index("git worktree add") < text.index("git pull --no-rebase origin kitty/mission-x")
    assert "git fetch origin kitty/mission-x:kitty/mission-x" not in text


def test_diverged_status_with_a_merge_record_still_aborts_first() -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(evidence=_verdict(FreshnessState.DIVERGED, "develop", behind=1, ahead=1), merge_record_exists=True, evidence_checkout=Path("/work/repo"))

    lines = str(caught.value).splitlines()
    assert lines[2] == "    spec-kitty consolidate --abort"
    assert lines[3] == "    git -C /work/repo pull --no-rebase origin develop"
    assert lines[4] == "    spec-kitty consolidate"


def test_lane_refusal_text_gives_fetch_and_branch_force_remedy() -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(lanes=(_verdict(FreshnessState.BEHIND, "kitty/lane-a", behind=1),))

    text = str(caught.value)
    assert text.splitlines()[0].startswith(f"{ORIGIN_LANE_STALE}: kitty/lane-a is behind (1 behind / 0 ahead of origin/kitty/lane-a)")
    assert "git fetch origin kitty/lane-a" in text
    assert "git branch -f kitty/lane-a origin/kitty/lane-a" in text


def test_unreachable_refusal_text_points_at_network_and_credentials() -> None:
    with pytest.raises(OriginFreshnessRefused) as caught:
        _gate(evidence=_verdict(FreshnessState.UNREACHABLE, "develop", detail="remote origin unreachable: timed out"))

    text = str(caught.value)
    assert text.startswith(f"{ORIGIN_UNREACHABLE}: develop is unreachable")
    assert "network" in text and "credentials" in text


def test_warn_mode_returns_warnings_naming_verdict_and_source_instead_of_raising() -> None:
    warnings = _gate(
        evidence=_verdict(FreshnessState.BEHIND, "develop", behind=1),
        lanes=(_verdict(FreshnessState.UNREACHABLE, detail="timed out"),),
        setting=_FLAG_WARN_SETTING,
    )

    assert len(warnings) == 2
    assert all("flag" in warning for warning in warnings)
    assert ORIGIN_STATUS_STALE in warnings[0] and "develop" in warnings[0]
    assert ORIGIN_UNREACHABLE in warnings[1]


def test_warn_mode_names_the_environment_source() -> None:
    warnings = _gate(evidence=_verdict(FreshnessState.BEHIND, "develop", behind=1), setting=OriginCheckSetting(OriginCheckMode.WARN, "environment"))

    assert "environment" in warnings[0]


def test_enforce_mode_surfaces_the_setting_warning() -> None:
    setting = OriginCheckSetting(OriginCheckMode.ENFORCE, "default", warning="unknown value 'bogus'")

    assert _gate(setting=setting) == ["unknown value 'bogus'"]


# --------------------------------------------------------------------------- plan_review_lane


def test_review_lane_keep_for_an_up_to_date_lane(world: World) -> None:
    _git(world.a, "branch", "lane-current", "main")
    _git(world.a, "push", "-q", "origin", "lane-current:lane-current")

    assert plan_review_lane(world.a, "lane-current").kind is ReviewLaneKind.KEEP


def test_review_lane_keep_when_remote_has_no_such_branch(world: World) -> None:
    _git(world.a, "branch", "lane-local-only", "main")

    assert plan_review_lane(world.a, "lane-local-only").kind is ReviewLaneKind.KEEP


def test_review_lane_fast_forward_carries_the_remote_sha(world: World) -> None:
    _git(world.a, "branch", "lane-ff", "main")
    _git(world.a, "push", "-q", "origin", "lane-ff:lane-ff")
    _push_branch(world.b, "lane-ff", "lane.txt")
    _git(world.b, "checkout", "-q", "lane-ff")
    remote_sha = _git(world.b, "rev-parse", "HEAD")
    _git(world.b, "checkout", "-q", "main")

    action = plan_review_lane(world.a, "lane-ff")

    assert action.kind is ReviewLaneKind.FAST_FORWARD
    assert action.remote_sha == remote_sha
    assert action.remote_ref == tracking_ref("origin", "lane-ff")


def test_review_lane_create_from_the_tracking_ref_when_only_remote_has_it(world: World) -> None:
    _push_branch(world.b, "lane-new", "lane.txt")

    action = plan_review_lane(world.a, "lane-new")

    assert action.kind is ReviewLaneKind.CREATE_FROM
    assert action.remote_ref == tracking_ref("origin", "lane-new")


def test_review_lane_refuses_a_diverged_lane(world: World) -> None:
    _git(world.a, "branch", "lane-d", "main")
    _git(world.a, "push", "-q", "origin", "lane-d:lane-d")
    _push_branch(world.b, "lane-d", "remote.txt")
    _git(world.a, "checkout", "-q", "lane-d")
    _commit(world.a, "local.txt")
    _git(world.a, "checkout", "-q", "main")

    action = plan_review_lane(world.a, "lane-d")

    assert action.kind is ReviewLaneKind.REFUSE
    assert action.code == ORIGIN_LANE_DIVERGED
    assert "lane-d" in (action.message or "")


def test_review_lane_diverged_refusal_names_both_recoveries(world: World) -> None:
    _git(world.a, "branch", "lane-r", "main")
    _git(world.a, "push", "-q", "origin", "lane-r:lane-r")
    _push_branch(world.b, "lane-r", "remote.txt")
    _git(world.a, "checkout", "-q", "lane-r")
    _commit(world.a, "local.txt")
    _git(world.a, "checkout", "-q", "main")

    message = plan_review_lane(world.a, "lane-r").message or ""

    assert "merge origin/lane-r" in message
    assert "git push origin lane-r" in message
    assert "SPEC_KITTY_ORIGIN_CHECK=warn" in message


def test_review_lane_keeps_a_diverged_lane_in_warn_mode(world: World) -> None:
    _git(world.a, "branch", "lane-w", "main")
    _git(world.a, "push", "-q", "origin", "lane-w:lane-w")
    _push_branch(world.b, "lane-w", "remote.txt")
    _git(world.a, "checkout", "-q", "lane-w")
    _commit(world.a, "local.txt")
    _git(world.a, "checkout", "-q", "main")

    action = plan_review_lane(world.a, "lane-w", OriginCheckSetting(OriginCheckMode.WARN, "environment"))

    assert action.kind is ReviewLaneKind.WARN
    assert action.code == ORIGIN_LANE_DIVERGED
    assert "origin check is warn, source: environment" in (action.message or "")


def test_review_lane_warns_when_the_remote_is_unreachable(world: World) -> None:
    _git(world.a, "branch", "lane-u", "main")
    unreachable_remote(world.a)

    action = plan_review_lane(world.a, "lane-u")

    assert action.kind is ReviewLaneKind.WARN
    assert action.code == ORIGIN_UNREACHABLE
    assert action.verdict is not None and action.verdict.state is FreshnessState.UNREACHABLE
