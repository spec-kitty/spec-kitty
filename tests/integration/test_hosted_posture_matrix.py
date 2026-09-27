"""NFR-001 / NFR-004 end-to-end: the hosted posture matrix walk.

Mission ``hosted-opt-in-drain-ledger-01M3FFEV`` (#4971). Contract:
``kitty-specs/hosted-opt-in-drain-ledger-01M3FFEV/contracts/hosted-posture.md``.

* **NFR-001** -- *"With no drain configuration and no endpoint configured, a
  full lane walk (9 lanes) plus one decision round-trip makes 0 outbound hosted
  requests (asserted by instrumenting every hosted network edge)."*
* **NFR-004** -- *"Across all 4 combinations of {ledger on/off} × {drain
  on/off}, lane-ledger bytes, tracked status-snapshot bytes, status-ref commit
  count and the reduced snapshot are identical (exercised on a flat mission and
  on a coordination-topology mission)."*

How the walk is made falsifiable
--------------------------------
* The instrumentation sits at the socket-adjacent openers, not at a higher
  layer: ``zeitgeist_client.budget.NoRedirects.build`` (every relay open --
  ``open_bounded`` builds through it) and ``httpx.Client.send`` (every
  capability-gateway request). Each records the attempt and raises, so a
  send can never succeed -- there is no server.
* Every cell seeds a valid relay credential for the checkout's hosted origin
  and registers the production moment handlers, so a **drain-on** cell really
  reaches the relay opener. :func:`test_cell_hosted_egress` asserts *> 0*
  attempts there; the drain-off *0* is therefore not the trivial zero of a
  walk that never had anywhere to send.
* Posture comes from the real files (``.kittify/config.yaml`` ``hosted.drain``
  / ``ledger.projection`` and ``<runtime-root>/config.toml`` ``[hosted]
  drain``), read by the real reader: the module carries
  ``real_drain_posture`` so the root autouse drain-on pin does not apply, and
  the env narrowers (``SPEC_KITTY_NO_MOMENT_HANDLERS`` & co.) are cleared so a
  developer shell cannot silently force every cell off.
* Clock and ids are made deterministic (a frozen ``kernel.clock`` and counter
  event/decision ids) so NFR-004 compares raw bytes rather than filtering
  fields out.

Each (topology, ledger, drain) walk runs once per module and is cached; the
per-cell test and the per-topology identity test both read the cache.
"""

from __future__ import annotations

import itertools
import json
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
import typer

from kernel import clock as clock_module
from specify_cli.core import env as core_env
from specify_cli.core import hosted_posture
from specify_cli.status import adapters
from specify_cli.status.models import Lane, ReviewResult, StatusEvent, TransitionRequest
from specify_cli.status.reducer import materialize_snapshot, reduce
from specify_cli.status.store import read_events
from specify_cli.zeitgeist_client import budget, credentials
from specify_cli.zeitgeist_client.resolution import store_key

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.real_drain_posture]

_ORIGIN = "https://github.com/acme/widget.git"
_HOST = "github.com"
_REPO_SLUG = "acme/widget"
_FROZEN_INSTANT = clock_module.datetime(2026, 9, 27, 12, 0, 0, tzinfo=clock_module.UTC)

_HUMAN_SLUG = "posture-matrix"
_MISSION_ID = "01KZPMATRX0000000000000001"
_MID8 = _MISSION_ID[:8]
_MISSION_DIR = f"{_HUMAN_SLUG}-{_MID8}"
_COORD_BRANCH = f"kitty/mission-{_MISSION_DIR}"
_DECISION_ID = "01KZPMATRXDEC1S10N00000001"
_ACTOR = "matrix-walker"

_TOPOLOGIES = ("flat", "coord")
_POSTURES = tuple(itertools.product((True, False), (True, False)))  # (ledger_on, drain_on)
_DONE_EVIDENCE: dict[str, Any] = {
    "review": {"reviewer": "reviewer-1", "verdict": "approved", "reference": "PR#1"},
    "repos": [{"repo": "acme/widget", "branch": "main", "commit": "abc1234"}],
    "verification": [{"command": "pytest", "result": "pass", "summary": "matrix walk"}],
}


class _InstrumentedEgress(RuntimeError):
    """Raised by the instrumented openers: no hosted request may complete."""


@dataclass
class _EgressLog:
    attempts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CellResult:
    """Everything a cell's assertions need, captured before any on-demand materialize."""

    topology: str
    ledger_on: bool
    drain_on: bool
    hosted_attempts: tuple[str, ...]
    event_log: bytes
    tracked_status: bytes | None
    status_ref_commits: int
    reduced_snapshot: dict[str, Any]
    derived_after_walk: dict[str, bytes]
    expected_projection: dict[str, Any]
    derived_after_materialize: dict[str, bytes]


# ---------------------------------------------------------------------------
# Fixture construction
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "matrix@spec-kitty.test")
    _git(repo, "config", "user.name", "Posture Matrix")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "remote", "add", "origin", _ORIGIN)


def _write_posture(repo: Path, home: Path, *, ledger_on: bool, drain_on: bool | None) -> None:
    """The two posture-controlling files (contracts/hosted-posture.md).

    ``drain_on=None`` writes no drain key anywhere (the real-default case).
    Drain off is expressed at the *repository* scope with the personal scope
    on, so the reader's repo-scope limb is what refuses.
    """
    kittify = repo / ".kittify"
    kittify.mkdir(exist_ok=True)
    lines = [f"ledger:\n  projection: {'true' if ledger_on else 'false'}\n"]
    if drain_on is not None:
        lines.append(f"hosted:\n  drain: {'true' if drain_on else 'false'}\n")
        home.mkdir(parents=True, exist_ok=True)
        (home / "config.toml").write_text("[hosted]\ndrain = true\n", encoding="utf-8")
    (kittify / "config.yaml").write_text("".join(lines), encoding="utf-8")


def _write_meta(feature_dir: Path, *, coord: bool) -> None:
    meta: dict[str, Any] = {
        "mission_id": _MISSION_ID,
        "mission_slug": _HUMAN_SLUG,
        "slug": _HUMAN_SLUG,
        "mission_type": "software-dev",
        "target_branch": "main",
        "vcs": "git",
    }
    if coord:
        meta["coordination_branch"] = _COORD_BRANCH
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def _write_wp(feature_dir: Path, wp_id: str) -> None:
    tasks = feature_dir / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    (tasks / f"{wp_id}.md").write_text(f"---\nwork_package_id: {wp_id}\nsubtasks: []\n---\n\n# {wp_id}\n", encoding="utf-8")


def _seed_event(wp_id: str) -> StatusEvent:
    return StatusEvent(
        event_id=f"01KZPMATRXSEED0000000{wp_id}0",
        mission_slug=_HUMAN_SLUG,
        mission_id=_MISSION_ID,
        wp_id=wp_id,
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-09-27T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )


def _build_flat(repo: Path) -> Path:
    from specify_cli.status.store import append_event

    feature_dir = repo / "kitty-specs" / _MISSION_DIR
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, coord=False)
    for wp in ("WP01", "WP02"):
        _write_wp(feature_dir, wp)
        append_event(feature_dir, _seed_event(wp))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed flat mission")
    return feature_dir


def _build_coord(repo: Path) -> Path:
    """Coord-topology mission, seeded genesis->planned ON the coordination
    branch (the shape of ``tests/status/test_execution_projection.py``'s
    ``coord_repo``, which mirrors ``tests/specify_cli/coordination/
    test_status_transition.py``)."""
    from specify_cli.coordination.status_service import EventLogWriteContract, append_event_log
    from specify_cli.coordination.workspace import CoordinationWorkspace

    feature_dir = repo / "kitty-specs" / _MISSION_DIR
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, coord=True)
    for wp in ("WP01", "WP02"):
        _write_wp(feature_dir, wp)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed coord mission")
    _git(repo, "branch", _COORD_BRANCH)

    seed_wt = repo / ".worktrees" / "seed-genesis"
    _git(repo, "worktree", "add", "-q", str(seed_wt), _COORD_BRANCH)
    for wp in ("WP01", "WP02"):
        append_event_log(
            EventLogWriteContract.coordination_transaction_append(seed_wt / "kitty-specs" / _MISSION_DIR),
            _seed_event(wp),
        )
    _git(seed_wt, "add", "kitty-specs")
    _git(seed_wt, "commit", "-q", "-m", "seed genesis->planned")
    _git(repo, "worktree", "remove", "-f", str(seed_wt))

    # #5113: decision open/resolve on an UNmaterialized coord worktree fails
    # today (tracked separately, out of scope for this mission -- spec.md "Out
    # of scope"). Pre-materialize it through the canonical CoordinationWorkspace
    # resolver so the decision round-trip below runs; remove this once #5113
    # lands.
    CoordinationWorkspace.resolve(repo, _MISSION_DIR, _MID8)
    return feature_dir


def _seed_relay_credential() -> None:
    """A valid cached relay credential for the checkout's hosted origin, so a
    drain-ON cell resolves offline (no gateway) and reaches the relay opener."""
    credentials.store(
        repo=store_key(host=_HOST, repo_slug=_REPO_SLUG),
        relay_url="https://relay.matrix.invalid",
        token="matrix-token",
        token_kind="presence",
        capability_credential="matrix-capability",
        expires_at="2099-01-01T00:00:00+00:00",
        host=_HOST,
        repo_slug=_REPO_SLUG,
        team="matrix-team",
        session_ref="matrix-session",
    )


# ---------------------------------------------------------------------------
# Instrumentation and determinism
# ---------------------------------------------------------------------------


@contextmanager
def _instrumented_egress(mp: pytest.MonkeyPatch) -> Iterator[_EgressLog]:
    log = _EgressLog()

    def _relay_build() -> Any:
        log.attempts.append("relay:NoRedirects.build")
        raise _InstrumentedEgress("relay opener reached")

    def _http_send(self: httpx.Client, request: httpx.Request, *args: Any, **kwargs: Any) -> httpx.Response:
        log.attempts.append(f"httpx:{request.method} {request.url}")
        raise _InstrumentedEgress("capability gateway client reached")

    mp.setattr(budget.NoRedirects, "build", staticmethod(_relay_build))
    mp.setattr(httpx.Client, "send", _http_send)
    yield log


def _deterministic_ids(mp: pytest.MonkeyPatch) -> None:
    from specify_cli.decisions import emit as decisions_emit
    from specify_cli.status import emit as status_emit

    counter = itertools.count(1)

    def _next_ulid() -> str:
        return f"01KZPMATRX{next(counter):016d}"

    mp.setattr(status_emit, "_generate_ulid", _next_ulid)
    mp.setattr(decisions_emit, "_generate_ulid", _next_ulid)
    mp.setattr(clock_module, "DEFAULT_CLOCK", clock_module.FrozenClock(instant=_FROZEN_INSTANT))


def _hermetic_env(mp: pytest.MonkeyPatch) -> None:
    """Clear the env narrowers and run fan-out inline. The personal home is
    NOT pinned here: every test requests the one canonical owner
    (``canonical_home``), and the walk writes the personal posture file and
    the relay credential under whatever home that owner established."""
    for name in core_env.MOMENT_HANDLER_DISABLE_ENV_VARS:
        mp.delenv(name, raising=False)
    # Run fan-out handlers inline: the bounded worker thread would let an
    # attempt land after the walk's egress count was read.
    mp.setenv("SPEC_KITTY_SAAS_FANOUT_TIMEOUT", "0")


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------


def _emitter(topology: str, repo: Path, feature_dir: Path) -> Callable[..., Any]:
    if topology == "coord":
        from specify_cli.coordination.status_transition import emit_status_transition_transactional as emit_txn

        def _emit_coord(wp_id: str, to_lane: str, **extra: Any) -> Any:
            return emit_txn(
                TransitionRequest(feature_dir=feature_dir, mission_slug=_HUMAN_SLUG, wp_id=wp_id, to_lane=to_lane, actor=_ACTOR, repo_root=repo, **extra)
            )

        return _emit_coord

    from specify_cli.status.emit import emit_status_transition

    def _emit_flat(wp_id: str, to_lane: str, **extra: Any) -> Any:
        return emit_status_transition(
            TransitionRequest(feature_dir=feature_dir, mission_slug=_HUMAN_SLUG, wp_id=wp_id, to_lane=to_lane, actor=_ACTOR, repo_root=repo, **extra)
        )

    return _emit_flat


def _decision_round_trip(repo: Path) -> None:
    """One decision open/resolve -- unaffected by drain/ledger by contract (D3)."""
    from specify_cli.decisions.models import OriginFlow
    from specify_cli.decisions.service import open_decision, resolve_decision

    open_decision(
        repo,
        _MISSION_DIR,
        origin_flow=OriginFlow.PLAN,
        input_key="matrix-choice",
        question="Which way?",
        options=("left", "right"),
        step_id="matrix-step",
        actor=_ACTOR,
        decision_id=_DECISION_ID,
    )
    resolve_decision(repo, _MISSION_DIR, _DECISION_ID, final_answer="left", actor=_ACTOR)


def _lane_walk(emit: Callable[..., Any]) -> None:
    """The full 9-lane state machine: WP01 to done; WP02 through blocked to canceled."""
    emit("WP01", "claimed")
    emit("WP01", "in_progress", workspace_context="worktree:matrix")
    emit("WP01", "for_review", subtasks_complete=True, implementation_evidence_present=True)
    emit("WP01", "in_review")
    emit("WP01", "approved", review_result=ReviewResult(reviewer="reviewer-1", verdict="approved", reference="PR#1"), evidence=_DONE_EVIDENCE)
    emit("WP01", "done", evidence=_DONE_EVIDENCE)
    emit("WP02", "claimed")
    emit("WP02", "blocked", reason="waiting on upstream")
    emit("WP02", "canceled", reason="descoped")


def _status_dir(topology: str, repo: Path) -> Path:
    from mission_runtime import MissionArtifactKind, placement_seam

    status_dir: Path = placement_seam(repo, _MISSION_DIR).read_dir(MissionArtifactKind.STATUS_STATE)
    if topology == "coord":
        assert ".worktrees" in status_dir.parts, f"coord status must resolve to the coordination worktree, got {status_dir}"
    return status_dir


def _derived_files(repo: Path) -> dict[str, bytes]:
    derived = repo / ".kittify" / "derived"
    if not derived.exists():
        return {}
    return {str(p.relative_to(derived)): p.read_bytes() for p in sorted(derived.rglob("*")) if p.is_file()}


def _tracked_status(topology: str, repo: Path, status_dir: Path) -> bytes | None:
    if topology == "coord":
        try:
            return _git(repo, "show", f"{_COORD_BRANCH}:kitty-specs/{_MISSION_DIR}/status.json").encode("utf-8")
        except subprocess.CalledProcessError:
            return None
    path = status_dir / "status.json"
    return path.read_bytes() if path.exists() else None


def _status_ref(topology: str) -> str:
    return _COORD_BRANCH if topology == "coord" else "main"


def _run_materialize_cli(repo: Path) -> None:
    from specify_cli.cli.commands.materialize import materialize as materialize_cli

    with pytest.raises(typer.Exit) as exc_info:
        materialize_cli(mission=_MISSION_DIR, json_output=False)
    assert exc_info.value.exit_code == 0


def _personal_home() -> Path:
    """The runtime root the canonical owner established (the real reader's own resolution)."""
    from specify_cli.paths import get_runtime_root

    base: Path = get_runtime_root().base
    return base


def walk_cell(root: Path, topology: str, *, ledger_on: bool, drain_on: bool | None) -> CellResult:
    """Build one mission, walk it under the given posture, capture every artifact."""
    repo = root / "repo"
    _init_repo(repo)
    with pytest.MonkeyPatch.context() as mp:
        _hermetic_env(mp)
        _write_posture(repo, _personal_home(), ledger_on=ledger_on, drain_on=drain_on)
        mp.chdir(repo)
        _deterministic_ids(mp)
        feature_dir = _build_coord(repo) if topology == "coord" else _build_flat(repo)
        _seed_relay_credential()
        adapters.ensure_zeitgeist_moment_handlers()

        posture = hosted_posture.drain_posture(repo)
        assert posture.enabled is bool(drain_on), f"posture files did not produce drain={drain_on}: {posture}"
        assert hosted_posture.ledger_posture(repo).enabled is ledger_on

        with _instrumented_egress(mp) as egress:
            _decision_round_trip(repo)
            _lane_walk(_emitter(topology, repo, feature_dir))
            attempts = tuple(egress.attempts)

        status_dir = _status_dir(topology, repo)
        snapshot = reduce(read_events(status_dir))
        result_before_materialize = {
            "event_log": (status_dir / "status.events.jsonl").read_bytes(),
            "tracked_status": _tracked_status(topology, repo, status_dir),
            "status_ref_commits": int(_git(repo, "rev-list", "--count", _status_ref(topology))),
            "reduced_snapshot": snapshot.to_dict(),
            "derived_after_walk": _derived_files(repo),
            "expected_projection": materialize_snapshot(status_dir).to_dict(),
        }
        _run_materialize_cli(repo)
        return CellResult(
            topology=topology,
            ledger_on=ledger_on,
            drain_on=bool(drain_on),
            hosted_attempts=attempts,
            derived_after_materialize=_derived_files(repo),
            **result_before_materialize,
        )


_CELL_CACHE: dict[tuple[str, bool, bool], CellResult] = {}


@pytest.fixture()
def cell(canonical_home: None, tmp_path_factory: pytest.TempPathFactory) -> Callable[[str, bool, bool], CellResult]:
    def _get(topology: str, ledger_on: bool, drain_on: bool) -> CellResult:
        key = (topology, ledger_on, drain_on)
        if key not in _CELL_CACHE:
            root = tmp_path_factory.mktemp(f"{topology}-ledger{int(ledger_on)}-drain{int(drain_on)}")
            _CELL_CACHE[key] = walk_cell(root, topology, ledger_on=ledger_on, drain_on=drain_on)
        return _CELL_CACHE[key]

    return _get


def _status_json_of(derived: dict[str, bytes]) -> dict[str, Any]:
    matches = [name for name in derived if name.endswith("/status.json")]
    assert len(matches) == 1, f"expected exactly one derived <mission>/status.json, got {sorted(derived)}"
    parsed: dict[str, Any] = json.loads(derived[matches[0]])
    return parsed


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


_CELL_PARAMS = [
    pytest.param(topology, ledger_on, drain_on, id=f"{topology}-ledger_{'on' if ledger_on else 'off'}-drain_{'on' if drain_on else 'off'}")
    for topology in _TOPOLOGIES
    for ledger_on, drain_on in _POSTURES
]


@pytest.mark.parametrize(("topology", "ledger_on", "drain_on"), _CELL_PARAMS)
def test_cell_hosted_egress(cell: Callable[[str, bool, bool], CellResult], topology: str, ledger_on: bool, drain_on: bool) -> None:
    """NFR-001: drain off => zero hosted attempts; drain on => the instrumented
    opener is genuinely on the walk's path (so the zero is not vacuous)."""
    result = cell(topology, ledger_on, drain_on)
    if drain_on:
        assert result.hosted_attempts, "drain-on walk never reached an instrumented opener -- the drain-off zero would be vacuous"
    else:
        assert result.hosted_attempts == (), f"drain off, yet hosted edges were attempted: {result.hosted_attempts}"


@pytest.mark.parametrize(("topology", "ledger_on", "drain_on"), _CELL_PARAMS)
def test_cell_ledger_projection(cell: Callable[[str, bool, bool], CellResult], topology: str, ledger_on: bool, drain_on: bool) -> None:
    """FR-008/FR-009: ledger on refreshes .kittify/derived/ to the reduced
    snapshot automatically; ledger off never does, yet ``spec-kitty
    materialize`` still produces it on demand."""
    result = cell(topology, ledger_on, drain_on)
    expected_lanes = {wp: data["lane"] for wp, data in result.expected_projection["work_packages"].items()}
    assert expected_lanes == {"WP01": "done", "WP02": "canceled"}
    if ledger_on:
        derived = result.derived_after_walk
        assert any(name.endswith("/board-summary.json") for name in derived), sorted(derived)
        assert _status_json_of(derived) == result.expected_projection
    else:
        assert result.derived_after_walk == {}, f"ledger off, yet the emits wrote {sorted(result.derived_after_walk)}"
        on_demand = _status_json_of(result.derived_after_materialize)
        assert {wp: data["lane"] for wp, data in on_demand["work_packages"].items()} == expected_lanes


@pytest.mark.parametrize("topology", _TOPOLOGIES)
def test_fsm_artifacts_identical_across_postures(cell: Callable[[str, bool, bool], CellResult], topology: str) -> None:
    """NFR-004 / FR-010: flipping ledger/drain never perturbs lane-FSM state."""
    results = [cell(topology, ledger_on, drain_on) for ledger_on, drain_on in _POSTURES]
    baseline = results[0]
    assert baseline.event_log, "empty lane ledger -- the walk wrote nothing"
    assert baseline.reduced_snapshot["work_packages"]["WP01"]["lane"] == "done"
    if topology == "coord":
        assert baseline.tracked_status is not None, "coord walk committed no status.json on the coordination branch"
    for other in results[1:]:
        label = f"{topology} ledger={other.ledger_on} drain={other.drain_on} vs ledger={baseline.ledger_on} drain={baseline.drain_on}"
        assert other.event_log == baseline.event_log, f"lane-ledger bytes differ: {label}"
        assert other.tracked_status == baseline.tracked_status, f"tracked status.json bytes differ: {label}"
        assert other.status_ref_commits == baseline.status_ref_commits, f"status-ref commit count differs: {label}"
        assert other.reduced_snapshot == baseline.reduced_snapshot, f"reduced snapshot differs: {label}"


def test_no_drain_configuration_is_zero_egress(canonical_home: None, tmp_path: Path) -> None:
    """contracts/hosted-posture.md: no drain configuration => off. The real
    file reader, with nothing written under the canonical home or the repo,
    resolves drain off -- and the full walk plus decision makes 0 attempts."""
    assert not (_personal_home() / "config.toml").exists()
    result = walk_cell(tmp_path / "default", "flat", ledger_on=True, drain_on=None)
    assert not (_personal_home() / "config.toml").exists(), "the walk itself must not write a personal drain key"
    assert result.hosted_attempts == ()
    assert result.reduced_snapshot["work_packages"]["WP01"]["lane"] == "done"


class _CountingOfferClient:
    """Wraps a REAL ZeitgeistClient so the drain refusal is the production one."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self.calls = 0

    def offer(self, op: str, args: dict[str, Any], *, request_id: str | None = None) -> Any:
        self.calls += 1
        return self._real.offer(op, args, request_id=request_id)


def test_authored_messages_refuse_and_never_retry_under_file_level_drain_off(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D3/C-005 end to end: file-level drain off => ``send`` refuses with
    ``drain_off``; the real client's DRAIN_DISABLED is definitive (one offer,
    zero sleeps) and never reaches the relay opener."""
    from specify_cli.live_work import authored
    from specify_cli.live_work.bindings import RepositoryBinding, ResolvedBindings
    from specify_cli.zeitgeist_client.transport import ClientConfig, OfferOutcome, ZeitgeistClient

    repo = tmp_path / "repo"
    _init_repo(repo)
    _hermetic_env(monkeypatch)
    _write_posture(repo, _personal_home(), ledger_on=True, drain_on=False)
    monkeypatch.chdir(repo)
    assert hosted_posture.drain_posture(repo).enabled is False

    monkeypatch.setattr(
        "specify_cli.live_work.bindings.resolve_bindings",
        lambda cwd: ResolvedBindings(repository=RepositoryBinding(slug=_REPO_SLUG), mission=None, repo_root=Path(cwd)),
    )
    monkeypatch.setattr(authored, "_require_moments_enabled", lambda: None)

    def _no_sleep(seconds: float) -> None:
        raise AssertionError(f"slept {seconds}s on a definitive drain refusal")

    monkeypatch.setattr(authored.time, "sleep", _no_sleep)

    with _instrumented_egress(monkeypatch) as egress:
        with pytest.raises(authored.AuthoredMessageError) as excinfo:
            authored.send("message", "hello team", cwd=repo)
        assert excinfo.value.code == "drain_off"

        real = ZeitgeistClient(
            ClientConfig(
                relay_url="https://relay.matrix.invalid",
                token="t",
                harness="claude",
                session_id="s",
                agent_id=None,
                repo="",
                branch="",
            )
        )
        assert real.offer("event.publish", {"kind": "k"}).outcome is OfferOutcome.DRAIN_DISABLED
        client = _CountingOfferClient(real)
        # cast: a structural stand-in that delegates to the real client -- only
        # ``offer`` is used, and it is the production one.
        outcome, reason = authored._offer_with_bounded_retry(cast(ZeitgeistClient, client), {"kind": "work.message.team_sent.v1"}, "msg-1")

    assert client.calls == 1
    assert outcome is authored.SendOutcome.FAILED
    assert reason is not None and "drain_disabled" in reason
    assert egress.attempts == []
