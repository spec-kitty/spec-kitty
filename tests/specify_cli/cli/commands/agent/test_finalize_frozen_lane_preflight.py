"""Unit tests for the finalize-tasks frozen-lane preflight (#5573, WP03 T010-T013).

The finalize shell gathers the evidence WP02's pure constraint needs -- the
history-started set from the status log (fail-closed) and the recorded lane
work tips -- dry-runs ``compute_lanes`` with it before the first status write,
and renders a ``LANE_MEMBERSHIP_FROZEN`` refusal. Seams are patched on the
module that owns the lazily imported name (``specify_cli.status``,
``specify_cli.lanes.*``, ``specify_cli.coordination.surface_resolver``), never
on ``mission_finalize``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.cli.commands.agent import mission_finalize_commit as finalize_commit
from specify_cli.cli.commands.agent import mission_finalize_lanes as finalize_lanes
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from specify_cli.lanes.compute import LaneMembershipFrozenError
from specify_cli.lanes.frozen_membership import FrozenLaneMembership, conflict_for, remedy_for
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind
from specify_cli.status import StoreError, WPMetadata

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "frozen-preflight"
_EVENTS = "status.events.jsonl"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _lane(lane_id: str, *wp_ids: str) -> ExecutionLane:
    return ExecutionLane(lane_id=lane_id, wp_ids=tuple(wp_ids), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)


def _write_previous(planning_dir: Path, *lanes: ExecutionLane) -> LanesManifest:
    manifest = LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=f"kitty/mission-{_SLUG}",
        target_branch="qa-main",
        lanes=list(lanes),
        computed_at="2026-10-04T00:00:00+00:00",
        computed_from="dependency_graph+ownership",
    )
    write_lanes_json(planning_dir, manifest)
    return manifest


def _frontmatters(*wp_ids: str) -> dict[str, WPMetadata]:
    return {wp_id: WPMetadata(work_package_id=wp_id, title=wp_id) for wp_id in wp_ids}


def _event(wp_id: str, to_lane: str) -> SimpleNamespace:
    return SimpleNamespace(wp_id=wp_id, to_lane=to_lane)


def _code(owned: str) -> OwnershipManifest:
    return OwnershipManifest(execution_mode=WorkProductKind("code_change"), owned_files=(owned,), authoritative_surface=owned)


class _Recorder:
    """A callable that records its calls and returns (or raises) a fixed outcome."""

    def __init__(self, result: object = None, *, raises: BaseException | None = None) -> None:
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self._result = result
        self._raises = raises

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        if self._raises is not None:
            raise self._raises
        return self._result


@pytest.fixture
def status_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Resolve every status read to ``tmp_path / "status"`` (the coordination-aware resolver is patched)."""
    read_dir = tmp_path / "status"
    read_dir.mkdir()
    monkeypatch.setattr(
        "specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor",
        lambda _repo_root, _slug: SimpleNamespace(read_dir=read_dir),
    )
    return read_dir


@pytest.fixture
def planning_dir(tmp_path: Path) -> Path:
    path = tmp_path / "kitty-specs" / _SLUG
    path.mkdir(parents=True)
    return path


def _with_events(monkeypatch: pytest.MonkeyPatch, status_dir: Path, events: Iterable[SimpleNamespace]) -> None:
    (status_dir / _EVENTS).write_text("{}\n", encoding="utf-8")
    listed = list(events)
    monkeypatch.setattr("specify_cli.status.read_events", lambda _read_dir: listed)


def _gather(planning_dir: Path, tmp_path: Path, *, present: Iterable[str] = ("WP01", "WP02"), eligible: Iterable[str] | None = None) -> FrozenLaneMembership:
    present_ids = tuple(present)
    return finalize_lanes._gather_frozen_lane_membership(
        planning_dir,
        tmp_path,
        _SLUG,
        wp_frontmatters=_frontmatters(*present_ids),
        eligible_wp_ids=frozenset(present_ids if eligible is None else eligible),
    )


def _assert_status_unreadable(excinfo: pytest.ExceptionInfo[LaneMembershipFrozenError]) -> None:
    error = excinfo.value
    assert error.error_code == "LANE_MEMBERSHIP_FROZEN"
    assert error.reason == "status_unreadable"
    assert [conflict.reason for conflict in error.conflicts] == ["status_unreadable"]
    assert error.__cause__ is not None, "the refusal must chain the underlying read failure"
    remedy = error.conflicts[0].remedy
    assert remedy.startswith(remedy_for("status_unreadable", ())), remedy
    assert str(error.__cause__) in remedy, "the underlying cause keeps its diagnostic"


# ---------------------------------------------------------------------------
# T010: _gather_frozen_lane_membership
# ---------------------------------------------------------------------------


def test_first_finalize_reads_no_status(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = _Recorder(raises=AssertionError("a first finalize must not resolve the status surface"))
    monkeypatch.setattr("specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor", resolver)
    tips = _Recorder(frozenset())
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", tips)

    frozen = _gather(planning_dir, tmp_path)

    assert frozen.is_empty
    assert resolver.calls == []
    assert tips.calls == []


def test_absent_log_means_nothing_history_started(planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    monkeypatch.setattr("specify_cli.status.read_events", _Recorder(raises=AssertionError("an absent log must not be read")))
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", lambda _root: frozenset())

    frozen = _gather(planning_dir, tmp_path)

    assert not (status_dir / _EVENTS).exists()
    assert dict(frozen.bindings) == {}
    assert frozen.is_empty


def test_history_started_wps_are_bound_to_their_recorded_lanes(planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    _with_events(monkeypatch, status_dir, [_event("WP01", "planned"), _event("WP02", "planned"), _event("WP02", "claimed")])
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", lambda _root: frozenset())

    # WP02 is started but no longer a lane input (present minus eligible): the shell forwards both sets to the builder.
    frozen = _gather(planning_dir, tmp_path, present=("WP01", "WP02", "WP03"), eligible=("WP01", "WP03"))

    assert dict(frozen.bindings) == {"WP02": "lane-b"}
    assert frozen.retired_wp_ids == frozenset({"WP02"})


def test_malformed_log_refuses_status_unreadable(planning_dir: Path, tmp_path: Path, status_dir: Path) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    (status_dir / _EVENTS).write_text("{not json\n", encoding="utf-8")

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _gather(planning_dir, tmp_path)

    _assert_status_unreadable(excinfo)
    assert isinstance(excinfo.value.__cause__, StoreError)


@pytest.mark.parametrize("failure", [UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"), OSError("disk gone")])
def test_unreadable_log_refuses_status_unreadable(
    planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    (status_dir / _EVENTS).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr("specify_cli.status.read_events", _Recorder(raises=failure))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _gather(planning_dir, tmp_path)

    _assert_status_unreadable(excinfo)
    assert excinfo.value.__cause__ is failure


@pytest.mark.parametrize("failure", [FileNotFoundError("no status surface"), ValueError("ambiguous status surface")])
def test_unresolvable_status_surface_refuses_status_unreadable(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    monkeypatch.setattr("specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor", _Recorder(raises=failure))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _gather(planning_dir, tmp_path)

    _assert_status_unreadable(excinfo)
    assert excinfo.value.__cause__ is failure


def _missing_status_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    missing = tmp_path / ".worktrees" / "frozen-preflight-coord" / "kitty-specs" / _SLUG
    monkeypatch.setattr(
        "specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor",
        lambda _repo_root, _slug: SimpleNamespace(read_dir=missing),
    )
    return missing


def test_unmaterialized_coordination_worktree_refuses_with_the_canonical_guidance(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4959: a status dir that does not exist is not an absent log; with no readable branch, the seam's remedy is kept."""
    _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    missing = _missing_status_dir(tmp_path, monkeypatch)
    unmaterialized = CoordinationWorktreeUnmaterialized(
        repo_root=tmp_path,
        mission_slug=_SLUG,
        mid8="01M444FM",
        coordination_branch=f"kitty/mission-{_SLUG}",
        coord_candidate=missing,
        primary_candidate=planning_dir,
    )
    seam = SimpleNamespace(read_dir=_Recorder(raises=unmaterialized))
    monkeypatch.setattr("mission_runtime.placement_seam", lambda *_args, **_kwargs: seam)
    monkeypatch.setattr("specify_cli.status.read_events", _Recorder(raises=AssertionError("an absent surface must not be read as empty")))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _gather(planning_dir, tmp_path)

    error = excinfo.value
    assert error.reason == "status_unreadable"
    assert error.__cause__ is unmaterialized
    remedy = error.conflicts[0].remedy
    assert remedy.startswith("Materialize the coordination worktree"), remedy
    assert unmaterialized.next_step in remedy


# ---------------------------------------------------------------------------
# #5573 fold: an unmaterialized coordination worktree is read from its branch
# ---------------------------------------------------------------------------

_MID8 = "01M444FM"
_COORD_BRANCH = f"kitty/mission-{_SLUG}-{_MID8}"


def _run_git(repo: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _coord_repo(tmp_path: Path, log: bytes | None) -> tuple[Path, Path]:
    """A repository whose local coordination branch carries *log* (``None``: no status log); returns (repo, coord dir)."""
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from specify_cli.missions._read_path_resolver import coord_feature_dir

    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q", "-b", "qa-main")
    _run_git(repo, "config", "user.name", "Test")
    _run_git(repo, "config", "user.email", "test@example.invalid")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-qm", "base")
    coord_dir = coord_feature_dir(repo, _SLUG, _MID8)
    relative_dir = coord_dir.relative_to(CoordinationWorkspace.worktree_path(repo, _SLUG, _MID8))
    _run_git(repo, "checkout", "-q", "-b", _COORD_BRANCH)
    (repo / relative_dir).mkdir(parents=True)
    (repo / relative_dir / "meta.json").write_text("{}\n", encoding="utf-8")
    if log is not None:
        (repo / relative_dir / _EVENTS).write_bytes(log)
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-qm", "coordination")
    _run_git(repo, "checkout", "-q", "qa-main")
    return repo, coord_dir


def _unmaterialized(repo: Path, coord_dir: Path, planning_dir: Path) -> CoordinationWorktreeUnmaterialized:
    return CoordinationWorktreeUnmaterialized(
        repo_root=repo,
        mission_slug=_SLUG,
        mid8=_MID8,
        coordination_branch=_COORD_BRANCH,
        coord_candidate=coord_dir,
        primary_candidate=planning_dir,
    )


def _route_to_unmaterialized(monkeypatch: pytest.MonkeyPatch, coord_dir: Path, unmaterialized: CoordinationWorktreeUnmaterialized) -> None:
    monkeypatch.setattr(
        "specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor",
        lambda _repo_root, _slug: SimpleNamespace(read_dir=coord_dir),
    )
    monkeypatch.setattr("mission_runtime.placement_seam", lambda *_args, **_kwargs: SimpleNamespace(read_dir=_Recorder(raises=unmaterialized)))


@pytest.mark.git_repo
def test_branch_without_a_committed_log_refuses_status_unreadable(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, coord_dir = _coord_repo(tmp_path, None)
    _route_to_unmaterialized(monkeypatch, coord_dir, _unmaterialized(repo, coord_dir, planning_dir))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        finalize_lanes._read_started_wp_ids(repo, _SLUG, owned=None)

    _assert_status_unreadable(excinfo)
    assert _COORD_BRANCH in excinfo.value.conflicts[0].remedy


@pytest.mark.git_repo
@pytest.mark.parametrize("log", [b"{corrupt\n", b"\xff\xfe\n"], ids=["malformed-json", "bad-encoding"])
def test_malformed_branch_log_refuses_status_unreadable(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, log: bytes) -> None:
    repo, coord_dir = _coord_repo(tmp_path, log)
    _route_to_unmaterialized(monkeypatch, coord_dir, _unmaterialized(repo, coord_dir, planning_dir))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        finalize_lanes._read_started_wp_ids(repo, _SLUG, owned=None)

    _assert_status_unreadable(excinfo)


@pytest.mark.parametrize("failure", [ValueError("ambiguous meta.json"), FileNotFoundError("meta.json is gone")])
def test_missing_status_dir_whose_seam_read_fails_refuses_with_the_cause(
    planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    _missing_status_dir(tmp_path, monkeypatch)
    monkeypatch.setattr("mission_runtime.placement_seam", lambda *_args, **_kwargs: SimpleNamespace(read_dir=_Recorder(raises=failure)))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _gather(planning_dir, tmp_path)

    _assert_status_unreadable(excinfo)
    assert excinfo.value.__cause__ is failure


def test_missing_status_dir_without_a_canonical_refusal_still_refuses(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    missing = _missing_status_dir(tmp_path, monkeypatch)
    monkeypatch.setattr("mission_runtime.placement_seam", lambda *_args, **_kwargs: SimpleNamespace(read_dir=lambda _kind: missing))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _gather(planning_dir, tmp_path)

    _assert_status_unreadable(excinfo)
    assert str(missing) in excinfo.value.conflicts[0].remedy


def test_recorded_tips_keep_a_lane_id_reserved_after_the_manifest_stops_listing_it(
    planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specify_cli.lanes.compute import lane_created_branch

    previous = _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"), _lane("lane-planning", "WP03"))
    _with_events(monkeypatch, status_dir, [_event("WP01", "in_progress"), _event("WP02", "claimed")])
    # lane-c left the manifest after its WP was retired, but its branch still carries a recorded tip; the listing is
    # repository-wide, so another mission's lane branch is in it too and must not reserve anything here.
    tips = _Recorder(frozenset({lane_created_branch(previous, "lane-c"), "kitty/mission-another-mission-lane-d"}))
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", tips)

    frozen = _gather(planning_dir, tmp_path, present=("WP01", "WP02", "WP03"))

    assert [args for args, _kwargs in tips.calls] == [(tmp_path,)], "the one git listing runs whenever a prior manifest exists"
    assert dict(frozen.bindings) == {"WP01": "lane-a", "WP02": "lane-b"}
    assert frozen.reserved_lane_ids == frozenset({"lane-a", "lane-b", "lane-c"})


def test_tip_fallback_freezes_a_tipped_lane_without_history(planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes.compute import lane_created_branch

    previous = _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    _with_events(monkeypatch, status_dir, [_event("WP01", "in_progress")])
    tips = _Recorder(frozenset({lane_created_branch(previous, "lane-b")}))
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", tips)

    frozen = _gather(planning_dir, tmp_path)

    assert [args for args, _kwargs in tips.calls] == [(tmp_path,)]
    assert dict(frozen.bindings) == {"WP01": "lane-a", "WP02": "lane-b"}


def test_unreadable_tip_listing_refuses_status_unreadable(planning_dir: Path, tmp_path: Path, status_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes.lane_tip import LaneTipListingError

    _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    _with_events(monkeypatch, status_dir, [_event("WP01", "in_progress")])
    failure = LaneTipListingError("git could not list the recorded lane work tips: not a git repository")
    monkeypatch.setattr("specify_cli.lanes.lane_tip.recorded_tip_branches", _Recorder(raises=failure))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _gather(planning_dir, tmp_path)

    error = excinfo.value
    assert error.reason == "status_unreadable"
    assert error.__cause__ is failure
    remedy = error.conflicts[0].remedy
    assert "lane work tips" in remedy and str(failure) in remedy
    assert "Repair the status log" not in remedy, "a git listing failure is not a status-log problem"


# ---------------------------------------------------------------------------
# T011: _preflight_frozen_lane_membership
# ---------------------------------------------------------------------------


def _preflight(
    planning_dir: Path,
    tmp_path: Path,
    meta: dict[str, object] | None,
    *,
    lane_wp_manifests: dict[str, OwnershipManifest] | None = None,
    lane_wp_dependencies: dict[str, list[str]] | None = None,
) -> FrozenLaneMembership:
    return finalize_lanes._preflight_frozen_lane_membership(
        planning_dir,
        tmp_path,
        _SLUG,
        meta,
        "qa-main",
        lane_wp_manifests={"WP01": _code("a.py"), "WP02": _code("b.py")} if lane_wp_manifests is None else lane_wp_manifests,
        lane_wp_dependencies={"WP01": [], "WP02": []} if lane_wp_dependencies is None else lane_wp_dependencies,
        lane_wp_bodies={},
        wp_frontmatters=_frontmatters("WP01", "WP02"),
        eligible_wp_ids=frozenset({"WP01", "WP02"}),
    )


def test_single_branch_skips_the_evidence(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gather = _Recorder(raises=AssertionError("SINGLE_BRANCH has nothing to freeze"))
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", gather)

    frozen = _preflight(planning_dir, tmp_path, {"topology": "single_branch"})

    assert frozen.is_empty
    assert gather.calls == []


def test_empty_evidence_skips_the_dry_run(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(FrozenLaneMembership.empty()))
    compute = _Recorder(raises=AssertionError("nothing frozen: no dry run"))
    monkeypatch.setattr("specify_cli.lanes.compute.compute_lanes", compute)

    assert _preflight(planning_dir, tmp_path, {"topology": "lanes"}).is_empty
    assert compute.calls == []


def test_empty_lane_inputs_still_refuse_a_removed_started_wp(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every WP left the lane inputs, but the started WP01 is neither present nor retired: refuse before any write."""
    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(FrozenLaneMembership(bindings={"WP01": "lane-a"})))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _preflight(planning_dir, tmp_path, {"topology": "lanes"}, lane_wp_manifests={}, lane_wp_dependencies={})

    assert excinfo.value.reason == "started_wp_removed"


def test_empty_lane_inputs_with_only_retired_wps_pass(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    frozen = FrozenLaneMembership(bindings={"WP01": "lane-a"}, retired_wp_ids=frozenset({"WP01"}))
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(frozen))

    assert _preflight(planning_dir, tmp_path, {"topology": "lanes"}, lane_wp_manifests={}, lane_wp_dependencies={}) == frozen


def test_dry_run_threads_previous_lanes_and_frozen_and_writes_nothing(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    previous = _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    before = (planning_dir / "lanes.json").read_bytes()
    frozen = FrozenLaneMembership(bindings={"WP02": "lane-b"})
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(frozen))
    compute = _Recorder()
    monkeypatch.setattr("specify_cli.lanes.compute.compute_lanes", compute)

    result = _preflight(planning_dir, tmp_path, {"topology": "lanes", "mission_id": "01M444FMXXXXXXXXXXXXXXXXXX", "mission_branch": "kitty/m"})

    assert result == frozen
    assert len(compute.calls) == 1
    kwargs = compute.calls[0][1]
    assert kwargs["frozen"] == frozen
    assert kwargs["previous_lanes"] == previous
    assert kwargs["mission_id"] == "01M444FMXXXXXXXXXXXXXXXXXX"
    assert kwargs["mission_branch"] == "kitty/m"
    assert (planning_dir / "lanes.json").read_bytes() == before


def test_dry_run_frozen_refusal_propagates(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_previous(planning_dir, _lane("lane-a", "WP01"), _lane("lane-b", "WP02"))
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(FrozenLaneMembership(bindings={"WP01": "lane-a", "WP02": "lane-b"})))

    with pytest.raises(LaneMembershipFrozenError) as excinfo:
        _preflight(
            planning_dir,
            tmp_path,
            {"topology": "lanes"},
            lane_wp_manifests={
                "WP01": OwnershipManifest(execution_mode=WorkProductKind("code_change"), owned_files=("a.py", "b.py"), authoritative_surface="a.py"),
                "WP02": _code("b.py"),
            },
            lane_wp_dependencies={"WP01": ["WP02"], "WP02": []},
        )

    assert excinfo.value.reason == "started_lanes_collapsed"


def test_dry_run_freeze_induced_cycle_propagates(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keeping WP01 and WP03 together on lane-a closes lane-a -> lane-b -> lane-a; refuse before any status write."""
    from specify_cli.lanes.compute import LaneDependencyCycleError

    _write_previous(planning_dir, _lane("lane-a", "WP01", "WP03"))
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(FrozenLaneMembership(bindings={"WP01": "lane-a", "WP03": "lane-a"})))

    with pytest.raises(LaneDependencyCycleError) as excinfo:
        _preflight(
            planning_dir,
            tmp_path,
            {"topology": "lanes"},
            lane_wp_manifests={"WP01": _code("a.py"), "WP02": _code("b.py"), "WP03": _code("c.py")},
            lane_wp_dependencies={"WP01": [], "WP02": ["WP01"], "WP03": ["WP02"]},
        )

    assert excinfo.value.error_code == "LANE_DEPENDENCY_CYCLE"
    assert excinfo.value.cycle_path == ("lane-a", "lane-b", "lane-a")


def test_dry_run_defers_other_lane_failures_to_the_lane_write(planning_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes.compute import LaneComputationError

    _write_previous(planning_dir, _lane("lane-a", "WP01"))
    frozen = FrozenLaneMembership(bindings={"WP01": "lane-a"})
    monkeypatch.setattr(finalize_lanes, "_gather_frozen_lane_membership", _Recorder(frozen))
    monkeypatch.setattr("specify_cli.lanes.compute.compute_lanes", _Recorder(raises=LaneComputationError("cycle")))

    assert _preflight(planning_dir, tmp_path, {"topology": "lanes"}) == frozen


# ---------------------------------------------------------------------------
# T013: rendering
# ---------------------------------------------------------------------------


def _collapsed_error() -> LaneMembershipFrozenError:
    return LaneMembershipFrozenError((conflict_for("started_lanes_collapsed", {"WP01": "lane-a", "WP02": "lane-b"}),))


def test_json_envelope_carries_the_contract_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_finalize

    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(mission_finalize, "_emit_json", emitted.append)
    error = _collapsed_error()

    finalize_commit._emit_finalize_error_with_revert_note(error, None, json_output=True)

    assert len(emitted) == 1
    payload = emitted[0]
    assert payload["error"] == str(error)
    assert payload["error_code"] == "LANE_MEMBERSHIP_FROZEN"
    assert payload["reason"] == "started_lanes_collapsed"
    assert payload["conflicts"] == [
        {
            "reason": "started_lanes_collapsed",
            "wp_ids": ["WP01", "WP02"],
            "recorded_lanes": ["lane-a", "lane-b"],
            "remedy": remedy_for("started_lanes_collapsed", ["WP01", "WP02"]),
        }
    ]
    assert payload["next_step"] == error.next_step


def test_console_status_unreadable_has_no_wp_list(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_finalize

    printed: list[str] = []
    monkeypatch.setattr(mission_finalize, "console", SimpleNamespace(print=lambda text: printed.append(str(text))))

    error = finalize_lanes._status_unreadable_error(OSError("disk gone"))
    finalize_commit._emit_finalize_error_with_revert_note(error, None, json_output=False)

    assert "  status_unreadable" in printed
    assert f"  Remedy: {error.conflicts[0].remedy}" in printed
    assert "disk gone" in error.conflicts[0].remedy


def test_other_errors_keep_their_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.agent import mission_finalize

    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(mission_finalize, "_emit_json", emitted.append)

    finalize_commit._emit_finalize_error_with_revert_note(RuntimeError("boom"), None, json_output=True)

    assert emitted == [{"error": "boom"}]
