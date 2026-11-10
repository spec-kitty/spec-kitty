"""``policy_metadata.wp_window`` capture on window-opening transitions (WP07, FR-002 / FR-003).

One test per writer-table row of the Mission data model (section 2) and the contract
``contracts/status-event-wp-window.md`` (writer rules W-1..W-6):

* real-git tests drive both composition shells (``emit_status_transition``, the flat door,
  and ``move-task``, which goes through the transactional door) against a ``lanes`` Mission;
* pure pipeline tests inject fake readers for the failure rows (C-002: the pipeline stays
  git-free, the reading is injected).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from typer.testing import CliRunner

import specify_cli.status.emit as emit_module
import specify_cli.status.lane_head as lane_head_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.lanes.compute import PLANNING_LANE_ID, lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.status import LANE_HEAD_KEY, WP_WINDOW_KEY
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.lane_head import CaptureCause, LaneHeadReading, read_lane_head
from specify_cli.status.models import Lane, TransitionRequest
from specify_cli.status.store import read_events
from specify_cli.status.transition_pipeline import _stamped_policy_metadata, _wp_window_value, prepare_transition
from tests._support.ansi import strip_ansi
from tests.integration.coord_topology_fixture import FlatTopologyContext, _git, build_flat_topology_mission
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SHA = "3f1c0d9e8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e"
_CONTRACT = Path(__file__).resolve().parents[2] / "kitty-specs" / "consolidation-window-provenance-01M6Y84D" / "contracts" / "status-event-wp-window.md"

#: The contract's JSON Schema (kept verbatim here so the test also runs where the mission dir is absent).
_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema_version"],
    "properties": {
        "schema_version": {"const": 1},
        "open_sha": {"type": "string", "pattern": "^([0-9a-f]{40}|[0-9a-f]{64})$"},
        "gap": {
            "type": "object",
            "required": ["reason"],
            "properties": {
                "reason": {"enum": ["capture_failed", "lane_branch_missing"]},
                "cause": {"enum": ["git_error", "probe_error"]},
                "detail": {"type": "string", "maxLength": 500},
            },
            "oneOf": [
                {"properties": {"reason": {"const": "capture_failed"}}, "required": ["cause"]},
                {"properties": {"reason": {"const": "lane_branch_missing"}}, "not": {"required": ["cause"]}},
            ],
            "additionalProperties": False,
        },
    },
    "oneOf": [
        {"required": ["open_sha"], "not": {"required": ["gap"]}},
        {"required": ["gap"], "not": {"required": ["open_sha"]}},
    ],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def flat_mission(tmp_path: Path) -> FlatTopologyContext:
    """A coordination-less ``lanes`` Mission with WP01 on ``lane-a`` and no status log yet."""
    ctx = build_flat_topology_mission(tmp_path, topology="lanes")
    _git(ctx.repo, "rm", "-q", "--", str(ctx.status_events_path.relative_to(ctx.repo)))
    _git(ctx.repo, "commit", "-qm", "test: start WP01 with no status log")
    return ctx


def _lane_branch(ctx: FlatTopologyContext, lane_id: str = "lane-a") -> str:
    manifest = read_lanes_json(ctx.primary_feature_dir)
    assert manifest is not None
    return lane_created_branch(manifest, lane_id)


def _create_lane_branch(ctx: FlatTopologyContext, lane_id: str = "lane-a") -> str:
    """Create *lane_id*'s branch off ``main`` with one commit; return its head sha."""
    branch = _lane_branch(ctx, lane_id)
    _git(ctx.repo, "branch", branch)
    worktree = ctx.repo.parent / f"{lane_id}-worktree"
    _git(ctx.repo, "worktree", "add", "-q", str(worktree), branch)
    (worktree / "impl.txt").write_text("lane work\n", encoding="utf-8")
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", "feat: lane work")
    sha = _git(worktree, "rev-parse", "HEAD")
    _git(ctx.repo, "worktree", "remove", "-f", str(worktree))
    return sha


def _write_manifest(ctx: FlatTopologyContext, lanes: list[ExecutionLane]) -> None:
    manifest = LanesManifest(
        version=1,
        mission_slug=ctx.slug,
        mission_id=ctx.mission_id,
        mission_branch=f"kitty/mission-{ctx.slug}",
        target_branch="main",
        lanes=lanes,
        computed_at="2026-11-09T00:00:00+00:00",
        computed_from="test",
    )
    write_lanes_json(ctx.primary_feature_dir, manifest)


def _lane(lane_id: str, *wp_ids: str) -> ExecutionLane:
    return ExecutionLane(lane_id=lane_id, wp_ids=wp_ids, write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)


def _emit(ctx: FlatTopologyContext, to_lane: str, **extra: Any) -> Any:
    request = TransitionRequest(
        feature_dir=ctx.primary_feature_dir,
        mission_slug=ctx.slug,
        wp_id="WP01",
        to_lane=to_lane,
        actor="tester",
        repo_root=ctx.repo,
        **extra,
    )
    return emit_status_transition(request)


def _persisted_metadata(ctx: FlatTopologyContext, event_id: str) -> dict[str, Any] | None:
    (persisted,) = [e for e in read_events(ctx.primary_feature_dir) if e.event_id == event_id]
    metadata: dict[str, Any] | None = persisted.policy_metadata
    return metadata


def _reader(reading: LaneHeadReading, calls: list[dict[str, Any]] | None = None) -> Any:
    def _read(*, repo_root: Path, mission_slug: str, wp_id: str, owned: object = None) -> LaneHeadReading:
        if calls is not None:
            calls.append({"repo_root": repo_root, "wp_id": wp_id})
        return reading

    return _read


def _prepare(
    tmp_path: Path, *, to_lane: str, from_lane: str, reader: Any, actor: str = "agent-1", policy_metadata: dict[str, Any] | None = None, **extra: Any
) -> Any:
    feature_dir = tmp_path / "kitty-specs" / "m-01M6Y84D"
    feature_dir.mkdir(parents=True, exist_ok=True)
    request = TransitionRequest(
        feature_dir=feature_dir,
        mission_slug="m-01M6Y84D",
        wp_id="WP01",
        to_lane=to_lane,
        actor=actor,
        repo_root=tmp_path,
        policy_metadata=policy_metadata,
        **extra,
    )
    return prepare_transition(
        request=request,
        feature_dir=feature_dir,
        mission_slug="m-01M6Y84D",
        mission_id=None,
        from_lane=from_lane,
        lane_head_reader=reader,
        at="2026-11-09T10:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# LaneHeadReading value object
# ---------------------------------------------------------------------------


def test_reading_constructors_enforce_exactly_one_state() -> None:
    assert LaneHeadReading.of_sha(_SHA) == LaneHeadReading(sha=_SHA, applicable=True, cause=None, detail="")
    assert LaneHeadReading.not_applicable().applicable is False
    failed = LaneHeadReading.failed(CaptureCause.GIT_ERROR, "x" * 900)
    assert failed.cause is CaptureCause.GIT_ERROR and failed.sha is None and len(failed.detail) == 500
    for bad in (
        {"sha": _SHA, "applicable": False, "cause": None},
        {"sha": _SHA, "applicable": True, "cause": CaptureCause.GIT_ERROR},
        {"sha": None, "applicable": True, "cause": None},
        {"sha": None, "applicable": False, "cause": CaptureCause.PROBE_ERROR},
        {"sha": "", "applicable": True, "cause": None},
    ):
        with pytest.raises(ValueError, match="LaneHeadReading"):
            LaneHeadReading(**bad)


# ---------------------------------------------------------------------------
# Writer table rows
# ---------------------------------------------------------------------------


def test_claim_with_lane_branch_records_open_sha_equal_to_lane_head(flat_mission: FlatTopologyContext) -> None:
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)
    sha = _create_lane_branch(flat_mission)

    event = _emit(flat_mission, "claimed")

    expected = {"schema_version": 1, "open_sha": sha}
    assert event.policy_metadata[LANE_HEAD_KEY] == sha
    assert event.policy_metadata[WP_WINDOW_KEY] == expected
    persisted = _persisted_metadata(flat_mission, event.event_id)
    assert persisted is not None
    assert persisted[WP_WINDOW_KEY] == expected
    assert persisted[WP_WINDOW_KEY]["open_sha"] == persisted[LANE_HEAD_KEY]  # WP-1


def test_in_progress_with_lane_branch_records_open_sha(flat_mission: FlatTopologyContext) -> None:
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)
    sha = _create_lane_branch(flat_mission)
    _emit(flat_mission, "claimed")

    event = _emit(flat_mission, "in_progress")

    assert event.to_lane == Lane.IN_PROGRESS
    assert event.policy_metadata[WP_WINDOW_KEY] == {"schema_version": 1, "open_sha": sha}
    assert event.policy_metadata[LANE_HEAD_KEY] == sha


def test_missing_lane_branch_records_lane_branch_missing_gap_and_move_succeeds(flat_mission: FlatTopologyContext) -> None:
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)
    branch = _lane_branch(flat_mission)

    event = _emit(flat_mission, "claimed")

    assert event.to_lane == Lane.CLAIMED
    assert LANE_HEAD_KEY not in event.policy_metadata
    assert event.policy_metadata[WP_WINDOW_KEY] == {
        "schema_version": 1,
        "gap": {"reason": "lane_branch_missing", "detail": f"refs/heads/{branch} not found"},
    }
    persisted = _persisted_metadata(flat_mission, event.event_id)
    assert persisted is not None and persisted[WP_WINDOW_KEY]["gap"]["reason"] == "lane_branch_missing"


def test_git_error_records_capture_failed_with_git_error_cause(flat_mission: FlatTopologyContext, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)

    def _boom(_repo_root: Path, _branch: str) -> str | None:
        raise OSError("fatal: bad object")

    monkeypatch.setattr(lane_head_module, "_branch_head", _boom)

    event = _emit(flat_mission, "claimed")

    assert event.to_lane == Lane.CLAIMED
    assert LANE_HEAD_KEY not in event.policy_metadata
    assert event.policy_metadata[WP_WINDOW_KEY] == {
        "schema_version": 1,
        "gap": {"reason": "capture_failed", "cause": "git_error", "detail": "fatal: bad object"},
    }


def _rev_parse_exits(monkeypatch: pytest.MonkeyPatch, code: int, stderr: str) -> None:
    """Make every ``git rev-parse --verify`` of a branch exit *code* (the rest of git stays real)."""
    import specify_cli.core.git_ops as git_ops

    real = git_ops.run_command

    def _fake(cmd: Any, **kwargs: Any) -> tuple[int, str, str]:
        if list(cmd[:3]) == ["git", "rev-parse", "--verify"]:
            return code, "", stderr
        return real(cmd, **kwargs)

    monkeypatch.setattr(git_ops, "run_command", _fake)


def test_rev_parse_failure_other_than_absent_ref_records_git_error(flat_mission: FlatTopologyContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-003: only ``rev-parse --verify --quiet`` exit 1 means "branch missing"; any other failure is a git error."""
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)
    _create_lane_branch(flat_mission)
    _rev_parse_exits(monkeypatch, 128, "fatal: unable to read packed-refs")

    reading = read_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01")

    assert reading.cause is CaptureCause.GIT_ERROR, reading
    assert "fatal: unable to read packed-refs" in reading.detail


def test_rev_parse_exit_one_still_reads_as_lane_branch_missing(flat_mission: FlatTopologyContext, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)
    _rev_parse_exits(monkeypatch, 1, "")

    reading = read_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01")

    assert reading.cause is CaptureCause.LANE_BRANCH_MISSING, reading


def test_probe_exception_records_capture_failed_with_probe_error_cause(flat_mission: FlatTopologyContext, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)

    def _explode(**_kwargs: Any) -> LaneHeadReading:
        raise RuntimeError("placement seam exploded")

    monkeypatch.setattr(lane_head_module, "_read_lane_head", _explode)
    reading = read_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01")
    assert reading == LaneHeadReading.failed(CaptureCause.PROBE_ERROR, "RuntimeError: placement seam exploded")

    event = _emit(flat_mission, "claimed")

    assert LANE_HEAD_KEY not in event.policy_metadata
    assert event.policy_metadata[WP_WINDOW_KEY] == {
        "schema_version": 1,
        "gap": {"reason": "capture_failed", "cause": "probe_error", "detail": "RuntimeError: placement seam exploded"},
    }


def test_probe_and_git_error_details_carry_no_absolute_paths(flat_mission: FlatTopologyContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """N4: the detail lands in the committed event log, so the repository root and the home directory are redacted."""
    repo, home = flat_mission.repo, Path.home()

    def _explode(**_kwargs: Any) -> LaneHeadReading:
        raise FileNotFoundError(f"{repo}/kitty-specs/x/lanes.json and {home}/.config/y and {repo}b/sibling")

    monkeypatch.setattr(lane_head_module, "_read_lane_head", _explode)
    reading = read_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01")

    assert reading.cause is CaptureCause.PROBE_ERROR
    # A sibling whose name merely starts with the root ("<root>b") is not under the root.
    assert reading.detail == f"FileNotFoundError: <repo>/kitty-specs/x/lanes.json and ~/.config/y and {repo}b/sibling"

    # A relative root (``Path('.')``) would turn every ``.`` into ``<repo>``: it is not redacted.
    relative = read_lane_head(repo_root=Path("."), mission_slug=flat_mission.slug, wp_id="WP01")
    assert relative.detail is not None and "<repo>" not in relative.detail


def test_unknown_home_directory_does_not_fail_the_transition(flat_mission: FlatTopologyContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """``Path.home()`` raises when HOME is unset and the uid has no passwd entry: the transition still records a gap."""
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)

    def _explode(**_kwargs: Any) -> LaneHeadReading:
        raise RuntimeError("placement seam exploded")

    def _no_home() -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(lane_head_module, "_read_lane_head", _explode)
    monkeypatch.setattr(Path, "home", staticmethod(_no_home))

    event = _emit(flat_mission, "claimed")

    assert event.policy_metadata[WP_WINDOW_KEY]["gap"] == {
        "reason": "capture_failed",
        "cause": "probe_error",
        "detail": "RuntimeError: placement seam exploded",
    }


def test_corrupt_lanes_json_reads_as_probe_error(flat_mission: FlatTopologyContext) -> None:
    (flat_mission.primary_feature_dir / "lanes.json").write_text("{not json", encoding="utf-8")

    reading = read_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01")

    assert reading == LaneHeadReading.failed(CaptureCause.PROBE_ERROR, "corrupt lanes.json")


def test_minted_single_branch_write_branch_readings(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """S8: the minted write branch is the reading; a missing one is a ``lane_branch_missing`` failure."""
    ctx = build_flat_topology_mission(tmp_path, topology="single_branch", mission_branch="kitty/mission-flat-write")

    with caplog.at_level(logging.WARNING, logger="specify_cli.status.lane_head"):
        missing = read_lane_head(repo_root=ctx.repo, mission_slug=ctx.slug, wp_id="WP01")
    assert missing == LaneHeadReading.failed(CaptureCause.LANE_BRANCH_MISSING, "Mission branch kitty/mission-flat-write does not exist")
    assert any("kitty/mission-flat-write" in r.getMessage() for r in caplog.records)

    _git(ctx.repo, "branch", "kitty/mission-flat-write")
    head = _git(ctx.repo, "rev-parse", "kitty/mission-flat-write")
    assert read_lane_head(repo_root=ctx.repo, mission_slug=ctx.slug, wp_id="WP01") == LaneHeadReading.of_sha(head)


def test_minted_write_branch_rev_parse_failure_reads_as_git_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = build_flat_topology_mission(tmp_path, topology="single_branch", mission_branch="kitty/mission-flat-write")
    _rev_parse_exits(monkeypatch, 128, "fatal: bad ref")

    reading = read_lane_head(repo_root=ctx.repo, mission_slug=ctx.slug, wp_id="WP01")

    assert reading.cause is CaptureCause.GIT_ERROR and "fatal: bad ref" in reading.detail, reading


def test_planning_lane_writes_no_wp_window(flat_mission: FlatTopologyContext) -> None:
    _write_manifest(flat_mission, [_lane(PLANNING_LANE_ID, "WP01")])
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)

    assert read_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01") == LaneHeadReading.not_applicable()
    event = _emit(flat_mission, "claimed")

    assert event.policy_metadata is None or WP_WINDOW_KEY not in event.policy_metadata


def test_unassigned_wp_and_no_lanes_json_write_no_wp_window(flat_mission: FlatTopologyContext, tmp_path: Path) -> None:
    unassigned = read_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP99")
    (flat_mission.primary_feature_dir / "lanes.json").unlink()
    no_manifest = read_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01")

    assert unassigned == LaneHeadReading.not_applicable()
    assert no_manifest == LaneHeadReading.not_applicable()
    prepared = _prepare(tmp_path, to_lane="claimed", from_lane=Lane.PLANNED, reader=_reader(no_manifest), policy_metadata={"agent": "claude"})
    assert prepared.event.policy_metadata == {"agent": "claude"}


def test_migration_actor_never_writes_wp_window(tmp_path: Path) -> None:
    for to_lane, from_lane in (("claimed", Lane.PLANNED), ("in_progress", Lane.CLAIMED)):
        prepared = _prepare(
            tmp_path,
            to_lane=to_lane,
            from_lane=from_lane,
            reader=_reader(LaneHeadReading.of_sha(_SHA)),
            actor="migration:backfill",
            workspace_context="worktree:/x",
        )
        assert prepared.event.policy_metadata == {LANE_HEAD_KEY: _SHA}


@pytest.mark.parametrize(
    ("to_lane", "from_lane", "extra"),
    [
        pytest.param("blocked", Lane.PLANNED, {}, id="blocked"),
        pytest.param("blocked", Lane.IN_PROGRESS, {}, id="blocked-from-in-progress"),
        pytest.param("for_review", Lane.IN_PROGRESS, {"force": True, "reason": "ready"}, id="for-review"),
        pytest.param("canceled", Lane.PLANNED, {"force": True, "reason": "dropped"}, id="canceled"),
        pytest.param("planned", Lane.CLAIMED, {"force": True, "reason": "released"}, id="planned"),
    ],
)
def test_blocked_and_other_lanes_never_write_wp_window(tmp_path: Path, to_lane: str, from_lane: str, extra: dict[str, Any]) -> None:
    for reading in (LaneHeadReading.of_sha(_SHA), LaneHeadReading.failed(CaptureCause.GIT_ERROR, "boom")):
        prepared = _prepare(tmp_path, to_lane=to_lane, from_lane=from_lane, reader=_reader(reading), **extra)
        assert prepared.event is not None
        metadata = prepared.event.policy_metadata or {}
        assert WP_WINDOW_KEY not in metadata
        assert metadata.get(LANE_HEAD_KEY) == reading.sha


def test_non_qualifying_event_is_byte_identical_to_today(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """W-5 / WP-3: a move that does not qualify builds today's event, byte for byte."""
    monkeypatch.setattr(emit_module, "_generate_ulid", lambda: "01FIXEDULIDFORCOMPARISON1")
    claim = {"agent": "claude", "shell_pid": 7}

    no_reader = _prepare(tmp_path, to_lane="claimed", from_lane=Lane.PLANNED, reader=None, policy_metadata=dict(claim))
    not_applicable = _prepare(tmp_path, to_lane="claimed", from_lane=Lane.PLANNED, reader=_reader(LaneHeadReading.not_applicable()), policy_metadata=dict(claim))
    assert json.dumps(no_reader.event.to_dict(), sort_keys=True) == json.dumps(not_applicable.event.to_dict(), sort_keys=True)

    # A non-opening move with a sha keeps today's shape: request metadata plus ``lane_head`` only.
    blocked = _prepare(tmp_path, to_lane="blocked", from_lane=Lane.PLANNED, reader=_reader(LaneHeadReading.of_sha(_SHA)), policy_metadata=dict(claim))
    assert blocked.event.policy_metadata == {**claim, LANE_HEAD_KEY: _SHA}

    # Nothing added: the request's own object (or None) is returned, as today.
    request = TransitionRequest(feature_dir=tmp_path, mission_slug="m", wp_id="WP01", to_lane="blocked", actor="a", repo_root=tmp_path, policy_metadata=claim)
    same = _stamped_policy_metadata(
        request=request, mission_slug="m", lane_head_reader=_reader(LaneHeadReading.failed(CaptureCause.GIT_ERROR, "x")), repo_root=None, resolved_lane=Lane.BLOCKED
    )
    assert same is claim


def test_move_task_claimed_before_implement_then_in_progress(flat_mission: FlatTopologyContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """US1-5: ``move-task --to claimed`` before the lane exists records the gap; the later ``in_progress`` records ``open_sha``."""
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)
    _git(flat_mission.repo, "add", "-A")
    _git(flat_mission.repo, "commit", "-qm", "test: seed WP01 planned")
    monkeypatch.chdir(flat_mission.repo)
    # A coordination-less ``lanes`` Mission targeting ``main`` records status on ``main``,
    # which is protected by default; the operator override lets the fixture record it.
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    runner = CliRunner()

    def _move(to: str) -> None:
        result = runner.invoke(tasks_app, ["move-task", "WP01", "--to", to, "--agent", "alice", "--mission", flat_mission.slug, "--force", "--note", to])
        assert result.exit_code == 0, strip_ansi(result.output)

    _move("claimed")
    sha = _create_lane_branch(flat_mission)
    _move("in_progress")

    events = [e for e in read_events(flat_mission.primary_feature_dir) if e.wp_id == "WP01" and e.to_lane in (Lane.CLAIMED, Lane.IN_PROGRESS)]
    claimed, in_progress = events
    assert claimed.policy_metadata is not None and claimed.policy_metadata[WP_WINDOW_KEY]["gap"]["reason"] == "lane_branch_missing"
    assert in_progress.policy_metadata is not None and in_progress.policy_metadata[WP_WINDOW_KEY] == {"schema_version": 1, "open_sha": sha}


def test_capture_adds_no_git_read(flat_mission: FlatTopologyContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-006 / W-2: the window takes the one lane-head reading; a move reads the lane head once."""
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)
    sha = _create_lane_branch(flat_mission)
    real = lane_head_module._branch_head
    branch_reads: list[str] = []

    def _counting(repo_root: Path, branch: str) -> str | None:
        branch_reads.append(branch)
        return real(repo_root, branch)

    monkeypatch.setattr(lane_head_module, "_branch_head", _counting)
    event = _emit(flat_mission, "claimed")

    assert branch_reads == [_lane_branch(flat_mission)]  # the same single read the lane_head stamp always took
    assert event.policy_metadata[WP_WINDOW_KEY]["open_sha"] == sha

    calls: list[dict[str, Any]] = []
    _prepare(flat_mission.repo, to_lane="claimed", from_lane=Lane.PLANNED, reader=_reader(LaneHeadReading.of_sha(_SHA), calls))
    assert len(calls) == 1


def test_wp_window_value_matches_contract_schema() -> None:
    request = TransitionRequest(mission_slug="m", wp_id="WP01", to_lane="claimed", actor="a")
    readings = [
        LaneHeadReading.of_sha(_SHA),
        LaneHeadReading.failed(CaptureCause.LANE_BRANCH_MISSING, "refs/heads/x not found"),
        LaneHeadReading.failed(CaptureCause.GIT_ERROR, "e" * 900),
        LaneHeadReading.failed(CaptureCause.PROBE_ERROR, ""),
    ]
    values = [_wp_window_value(request, reading, Lane.CLAIMED) for reading in readings]
    for value in values:
        assert value is not None
        jsonschema.validate(value, _SCHEMA)
    assert _wp_window_value(request, LaneHeadReading.not_applicable(), Lane.CLAIMED) is None
    if _CONTRACT.exists():  # the mission dir rides the planning branch; the schema above must match it verbatim
        assert '"reason": { "enum": ["capture_failed", "lane_branch_missing"] }' in _CONTRACT.read_text(encoding="utf-8")
