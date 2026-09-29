"""Tests for ``status.lane_head`` (WP03, FR-001 / C-001 / C-002 / NFR-002).

Three groups:

1. :func:`probe_lane_head` unit behaviour, git-backed, against a real
   ``lanes.json`` written through the canonical lanes persistence API
   (T015).
2. An AST pin (T013) proving every ``prepare_transition(...)`` call site in
   ``src/specify_cli/`` passes ``lane_head_probe=probe_lane_head`` -- the bare
   name, never ``None`` and never a lambda -- with a numeric floor and a
   self-mutation (non-vacuity) check.
3. End-to-end proof through both composition shells (the flat/primary door
   ``emit_status_transition`` and the transactional door
   ``emit_status_transition_transactional``) that a persisted, lane-mapped
   transition's event carries the stamp, alongside any caller-supplied claim
   ``policy_metadata``.
"""

from __future__ import annotations

import ast
import json
import logging
import subprocess
from pathlib import Path

import pytest

import specify_cli.status.emit as emit_module
import specify_cli.status.transition_pipeline as transition_pipeline_module
from specify_cli.coordination.status_transition import emit_status_transition_transactional
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.emit import build_claim_policy_metadata, emit_status_transition
from specify_cli.status.lane_head import LANE_HEAD_KEY, probe_lane_head
from specify_cli.status.models import Lane, StatusEvent, TransitionRequest
from specify_cli.status.store import read_events, read_events_from_text
from tests.integration.coord_topology_fixture import (
    FlatTopologyContext,
    _git,
    _make_git_repo,
    _write_lanes_json,
    _write_meta,
    _write_wp_task,
)
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Group 1: probe_lane_head unit behaviour
# ---------------------------------------------------------------------------


@pytest.fixture
def flat_mission(tmp_path: Path) -> FlatTopologyContext:
    """A flat/single-branch mission with ``lane-a``/``WP01`` in ``lanes.json``.

    Mirrors ``tests.integration.coord_topology_fixture.flat_topology_mission``
    exactly (that fixture is registered for ``tests/specify_cli/`` only, via
    its ``conftest.py``, so it is not reachable by name here) -- reuses its
    canonical builder helpers rather than re-deriving the mission shape.
    """
    mission_id = "01LANEHEADFC00000000000001"
    mid8 = "01LANEHE"
    human_slug = "lane-head-fixture"
    slug = f"{human_slug}-{mid8}"

    repo = _make_git_repo(tmp_path / "flat")
    primary_feature_dir = repo / "kitty-specs" / slug
    primary_feature_dir.mkdir(parents=True)
    _write_meta(
        primary_feature_dir,
        slug=slug,
        mission_id=mission_id,
        topology="single_branch",
        coordination_branch=None,
    )
    tasks_dir = primary_feature_dir / "tasks"
    tasks_dir.mkdir()
    _write_wp_task(tasks_dir, "WP01")
    _write_lanes_json(primary_feature_dir, slug=slug, mission_id=mission_id)

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat: lane-head fixture mission")

    return FlatTopologyContext(
        repo=repo,
        slug=slug,
        mid8=mid8,
        mission_id=mission_id,
        primary_feature_dir=primary_feature_dir,
        status_events_path=primary_feature_dir / "status.events.jsonl",
    )


def _create_lane_branch(repo: Path, slug: str, *, lane_id: str = "lane-a") -> str:
    """Create ``lane_id``'s branch off ``main`` with one commit; return its sha."""
    branch = lane_branch_name(slug, lane_id, target_branch="main")
    _git(repo, "branch", branch)
    worktree = repo.parent / f"{lane_id}-worktree"
    _git(repo, "worktree", "add", "-q", str(worktree), branch)
    (worktree / "impl.txt").write_text("lane work\n", encoding="utf-8")
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", "feat: lane work")
    sha = _git(worktree, "rev-parse", "HEAD")
    _git(repo, "worktree", "remove", "-f", str(worktree))
    return sha


def test_probe_lane_head_returns_lane_branch_sha(flat_mission: FlatTopologyContext) -> None:
    sha = _create_lane_branch(flat_mission.repo, flat_mission.slug)
    result = probe_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01")
    assert result == sha


def test_probe_lane_head_none_when_lanes_json_absent(tmp_path: Path) -> None:
    slug = "no-lanes-fixture"
    repo = _make_git_repo(tmp_path / "flat")
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, slug=slug, mission_id="01NOLANES0000000000000001", topology="single_branch", coordination_branch=None)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feat: no lanes.json")

    assert probe_lane_head(repo_root=repo, mission_slug=slug, wp_id="WP01") is None


def test_probe_lane_head_none_when_lanes_json_corrupt(flat_mission: FlatTopologyContext) -> None:
    (flat_mission.primary_feature_dir / "lanes.json").write_text("{ not json", encoding="utf-8")

    assert probe_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01") is None


def test_probe_lane_head_none_when_wp_not_in_manifest(flat_mission: FlatTopologyContext) -> None:
    assert probe_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP99") is None


def test_probe_lane_head_none_for_planning_lane(flat_mission: FlatTopologyContext) -> None:
    manifest = LanesManifest(
        version=1,
        mission_slug=flat_mission.slug,
        mission_id=flat_mission.mission_id,
        mission_branch=f"kitty/mission-{flat_mission.slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=PLANNING_LANE_ID,
                wp_ids=("WP01",),
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at="2026-06-26T00:00:00+00:00",
        computed_from="test",
    )
    write_lanes_json(flat_mission.primary_feature_dir, manifest)

    assert probe_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01") is None


def test_probe_lane_head_none_when_branch_missing(flat_mission: FlatTopologyContext) -> None:
    # lanes.json already assigns WP01 to lane-a (the fixture default); the
    # branch itself was never created.
    assert probe_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01") is None


def _two_lane_manifest(ctx: FlatTopologyContext) -> None:
    """WP01 on lane-a, WP02 on lane-b (no branches created)."""
    lanes = [
        ExecutionLane(lane_id=lane_id, wp_ids=(wp,), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
        for lane_id, wp in (("lane-a", "WP01"), ("lane-b", "WP02"))
    ]
    manifest = LanesManifest(
        version=1,
        mission_slug=ctx.slug,
        mission_id=ctx.mission_id,
        mission_branch=f"kitty/mission-{ctx.slug}",
        target_branch="main",
        lanes=lanes,
        computed_at="2026-09-29T00:00:00+00:00",
        computed_from="test",
    )
    write_lanes_json(ctx.primary_feature_dir, manifest)


def _no_stamp_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING and r.name == "specify_cli.status.lane_head"]


def test_missing_branch_after_implementation_started_warns_with_wp_and_lane(flat_mission: FlatTopologyContext, caplog: pytest.LogCaptureFixture) -> None:
    """#5046 landing (D): a lost stamp once lanes exist is a WARNING naming the WP and lane."""
    _two_lane_manifest(flat_mission)
    _create_lane_branch(flat_mission.repo, flat_mission.slug, lane_id="lane-b")
    with caplog.at_level(logging.DEBUG, logger="specify_cli.status.lane_head"):
        assert probe_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01") is None
    (message,) = _no_stamp_warnings(caplog)
    assert "WP01" in message and "lane-a" in message and "does not exist" in message


def test_missing_branch_before_any_lane_branch_exists_stays_silent(flat_mission: FlatTopologyContext, caplog: pytest.LogCaptureFixture) -> None:
    """Pre-implementation (finalize-tasks seeding every WP) is the normal state, not a lost stamp."""
    _two_lane_manifest(flat_mission)
    with caplog.at_level(logging.DEBUG, logger="specify_cli.status.lane_head"):
        assert probe_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01") is None
    assert _no_stamp_warnings(caplog) == []


def test_git_error_on_mapped_lane_warns(flat_mission: FlatTopologyContext, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.lane_head as lane_head_module

    def _boom(_repo_root: Path, _branch: str) -> str | None:
        raise OSError("git exploded")

    monkeypatch.setattr(lane_head_module, "_branch_head", _boom)
    with caplog.at_level(logging.DEBUG, logger="specify_cli.status.lane_head"):
        assert probe_lane_head(repo_root=flat_mission.repo, mission_slug=flat_mission.slug, wp_id="WP01") is None
    (message,) = _no_stamp_warnings(caplog)
    assert "WP01" in message and "lane-a" in message and "git exploded" in message


def test_no_lanes_json_and_planning_lane_stay_silent(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="specify_cli.status.lane_head"):
        assert probe_lane_head(repo_root=tmp_path / "does-not-exist", mission_slug="whatever", wp_id="WP01") is None
    assert _no_stamp_warnings(caplog) == []


def test_probe_lane_head_never_raises_on_unusable_repo_root(tmp_path: Path) -> None:
    """Best-effort (C-1): an unresolvable repo root degrades to None, never a raise."""
    assert probe_lane_head(repo_root=tmp_path / "does-not-exist", mission_slug="whatever", wp_id="WP01") is None


# ---------------------------------------------------------------------------
# Group 2: AST pin -- every prepare_transition(...) call site in
# src/specify_cli/, whole-tree (T013). Matches both the bare-name call form
# (``prepare_transition(...)``) and the attribute call form
# (``x.prepare_transition(...)``, e.g. an aliased-module import) -- a call
# site that escapes both shapes would silently evade the stamp.
# ---------------------------------------------------------------------------

_SPECIFY_CLI_SRC_ROOT = Path(emit_module.__file__).resolve().parent.parent
_TRANSITION_PIPELINE_PATH = Path(transition_pipeline_module.__file__).resolve()


def _prepare_transition_call_nodes(source: str) -> list[ast.Call]:
    """Every ``prepare_transition(...)`` call in *source*: bare name OR attribute access."""
    tree = ast.parse(source)
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == "prepare_transition") or (isinstance(func, ast.Attribute) and func.attr == "prepare_transition"):
            calls.append(node)
    return calls


def _lane_head_probe_violations(source: str) -> list[str]:
    """One message per call that does not pass ``lane_head_probe=probe_lane_head`` (bare name)."""
    violations: list[str] = []
    for call in _prepare_transition_call_nodes(source):
        kwarg = next((kw.value for kw in call.keywords if kw.arg == "lane_head_probe"), None)
        if kwarg is None:
            violations.append(f"line {call.lineno}: missing lane_head_probe=")
        elif not (isinstance(kwarg, ast.Name) and kwarg.id == "probe_lane_head"):
            violations.append(f"line {call.lineno}: lane_head_probe is not the bare name probe_lane_head ({ast.dump(kwarg)})")
    return violations


def _iter_specify_cli_source_files() -> list[Path]:
    """Every ``*.py`` under ``src/specify_cli/``, excluding ``transition_pipeline.py`` itself.

    That module is the ``def prepare_transition(...)`` definition site, not a
    caller -- excluded so the pin scans call sites only (T013's own text:
    "skip transition_pipeline.py's own def").
    """
    return sorted(p for p in _SPECIFY_CLI_SRC_ROOT.rglob("*.py") if p.resolve() != _TRANSITION_PIPELINE_PATH)


def test_every_prepare_transition_call_site_passes_probe_lane_head() -> None:
    all_calls: list[tuple[Path, ast.Call]] = []
    all_violations: list[str] = []
    for path in _iter_specify_cli_source_files():
        source = path.read_text(encoding="utf-8")
        if "prepare_transition" not in source:
            # Cheap pre-filter: a real call site must contain this substring
            # somewhere in its source text, so a file lacking it entirely
            # cannot hide a call -- this only skips ast.parse on ~1000 files
            # that provably have nothing to find.
            continue
        calls = _prepare_transition_call_nodes(source)
        all_calls.extend((path, call) for call in calls)
        all_violations.extend(f"{path}: {message}" for message in _lane_head_probe_violations(source))

    assert len(all_calls) == 4, (
        f"expected exactly 4 prepare_transition call sites across src/specify_cli/ (whole-tree floor pin), "
        f"found {len(all_calls)}: {[str(path) for path, _ in all_calls]}"
    )
    assert all_violations == [], all_violations


def test_pin_checker_flags_a_call_missing_the_kwarg() -> None:
    """Self-mutation (architectural-gate-non-vacuity): the checker must fire on a real gap."""
    assert _lane_head_probe_violations("prepare_transition(request=r, feature_dir=f)\n") != []


def test_pin_checker_flags_lane_head_probe_none() -> None:
    """Self-mutation: a call that explicitly nulls the probe must also be flagged."""
    assert _lane_head_probe_violations("prepare_transition(request=r, lane_head_probe=None)\n") != []


def test_pin_checker_flags_attribute_call_form_missing_the_kwarg() -> None:
    """Self-mutation: the ``x.prepare_transition(...)`` attribute-call shape must also be caught.

    This is the exact escape Issue 1 named: a scanner matching only
    ``ast.Name`` would silently ignore a call routed through an imported
    module alias (e.g. ``_pipeline.prepare_transition(...)``).
    """
    assert _lane_head_probe_violations("_pipeline.prepare_transition(request=r, feature_dir=f)\n") != []


def test_pin_checker_flags_attribute_call_form_with_lane_head_probe_none() -> None:
    """Self-mutation: the attribute-call shape with an explicit ``None`` probe must also be caught."""
    assert _lane_head_probe_violations("_pipeline.prepare_transition(request=r, lane_head_probe=None)\n") != []


def test_pin_checker_accepts_the_attribute_call_form_when_correct() -> None:
    """Non-vacuity in the other direction: a correct attribute-call site is NOT flagged."""
    assert _lane_head_probe_violations("_pipeline.prepare_transition(request=r, lane_head_probe=probe_lane_head)\n") == []


# ---------------------------------------------------------------------------
# Group 3: end-to-end through both composition shells
# ---------------------------------------------------------------------------


def test_flat_shell_stamps_lane_head_and_preserves_claim_metadata(flat_mission: FlatTopologyContext) -> None:
    seed_wp_to_planned(flat_mission.primary_feature_dir, "WP01", slug=flat_mission.slug)
    sha = _create_lane_branch(flat_mission.repo, flat_mission.slug)
    claim_metadata = build_claim_policy_metadata(shell_pid=4242, shell_pid_created_at="2026-01-01T00:00:00+00:00", agent="claude")

    request = TransitionRequest(
        feature_dir=flat_mission.primary_feature_dir,
        mission_slug=flat_mission.slug,
        wp_id="WP01",
        to_lane="claimed",
        actor="tester",
        repo_root=flat_mission.repo,
        policy_metadata=claim_metadata,
    )
    event = emit_status_transition(request)

    assert event.policy_metadata is not None
    assert event.policy_metadata[LANE_HEAD_KEY] == sha
    # Caller-supplied claim keys ride alongside the stamp untouched.
    assert event.policy_metadata["agent"] == "claude"
    assert event.policy_metadata["shell_pid"] == 4242

    persisted = [e for e in read_events(flat_mission.primary_feature_dir) if e.event_id == event.event_id]
    assert len(persisted) == 1
    assert persisted[0].policy_metadata is not None
    assert persisted[0].policy_metadata[LANE_HEAD_KEY] == sha


_COORD_MISSION_SLUG = "lane-head-coord"
_COORD_MID8 = "01LHCOORD"
_COORD_MISSION_ID = "01LHCOORD0000000000000001"
_COORD_MISSION_DIRNAME = f"{_COORD_MISSION_SLUG}-{_COORD_MID8}"
_COORD_BRANCH = f"kitty/mission-{_COORD_MISSION_DIRNAME}"


def _git_run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def coord_repo(tmp_path: Path) -> Path:
    """A coord-topology mission with ``lane-a``/``WP01`` in ``lanes.json``."""
    r = tmp_path / "coord-repo"
    r.mkdir()
    _git_run(r, "init", "-q", "-b", "main")
    _git_run(r, "config", "user.email", "t@example.invalid")
    _git_run(r, "config", "user.name", "Test")
    _git_run(r, "config", "commit.gpgsign", "false")

    feature_dir = r / "kitty-specs" / _COORD_MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _COORD_MISSION_SLUG,
                "mission_id": _COORD_MISSION_ID,
                "mid8": _COORD_MID8,
                "coordination_branch": _COORD_BRANCH,
                "target_branch": "main",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=_COORD_MISSION_DIRNAME,
        mission_id=_COORD_MISSION_ID,
        mission_branch=_COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at="2026-06-26T00:00:00+00:00",
        computed_from="test",
    )
    write_lanes_json(feature_dir, manifest)
    _git_run(r, "add", "kitty-specs")
    _git_run(r, "commit", "-q", "-m", "seed mission")
    _git_run(r, "branch", _COORD_BRANCH)
    return r


def _seed_planned_on_coord_repo(repo: Path) -> None:
    from specify_cli.coordination.status_service import EventLogWriteContract, append_event_log

    seed = StatusEvent(
        event_id="01SEEDLANEHEADCOORD00000001",
        mission_slug=_COORD_MISSION_SLUG,
        mission_id=_COORD_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-06-19T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    worktree = repo / ".worktrees" / "seed-coord"
    _git_run(repo, "worktree", "add", "-q", str(worktree), _COORD_BRANCH)
    append_event_log(
        EventLogWriteContract.coordination_transaction_append(worktree / "kitty-specs" / _COORD_MISSION_DIRNAME),
        seed,
    )
    _git_run(worktree, "add", "-A")
    _git_run(worktree, "commit", "-q", "-m", "seed genesis->planned")
    _git_run(repo, "worktree", "remove", "-f", str(worktree))


def _read_coord_branch_events(repo: Path, mission_dirname: str) -> list[StatusEvent]:
    """Read the persisted event log back off the coordination branch (T015).

    ``git show`` the JSONL blob straight off ``_COORD_BRANCH`` -- no worktree
    materialization needed -- and parse it through the canonical store reader
    so this reads the SAME authoritative log the coord worktree would.
    """
    content = subprocess.run(
        ["git", "show", f"{_COORD_BRANCH}:kitty-specs/{mission_dirname}/status.events.jsonl"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return read_events_from_text(repo / "kitty-specs" / mission_dirname, content)


def test_transactional_shell_stamps_lane_head(coord_repo: Path) -> None:
    _seed_planned_on_coord_repo(coord_repo)
    sha = _create_lane_branch(coord_repo, _COORD_MISSION_DIRNAME)
    claim_metadata = build_claim_policy_metadata(shell_pid=9911, shell_pid_created_at="2026-06-19T00:05:00+00:00", agent="claude")

    # The mission handle the placement seam resolves against is the full
    # directory-embedding slug (what an operator-supplied ``--mission``
    # selector or a coord-topology mission dirname is) -- mirrors
    # ``test_for_review_gate_parity.py``'s ``MISSION_DIRNAME`` convention,
    # not the bare ``meta.json.mission_slug`` field.
    request = TransitionRequest(
        feature_dir=coord_repo / "kitty-specs" / _COORD_MISSION_DIRNAME,
        mission_slug=_COORD_MISSION_DIRNAME,
        wp_id="WP01",
        to_lane="claimed",
        actor="tester",
        repo_root=coord_repo,
        policy_metadata=claim_metadata,
    )
    event = emit_status_transition_transactional(request)

    assert event.policy_metadata is not None
    assert event.policy_metadata[LANE_HEAD_KEY] == sha
    assert event.policy_metadata["agent"] == "claude"
    assert event.policy_metadata["shell_pid"] == 9911

    # T015: the *persisted* event, read back off the coordination branch
    # (not just the returned in-memory value), carries the stamp alongside
    # the caller-supplied claim keys.
    persisted = [e for e in _read_coord_branch_events(coord_repo, _COORD_MISSION_DIRNAME) if e.event_id == event.event_id]
    assert len(persisted) == 1
    assert persisted[0].policy_metadata is not None
    assert persisted[0].policy_metadata[LANE_HEAD_KEY] == sha
    assert persisted[0].policy_metadata["agent"] == "claude"
    assert persisted[0].policy_metadata["shell_pid"] == 9911
