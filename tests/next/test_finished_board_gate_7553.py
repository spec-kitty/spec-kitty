"""Advancing ``next`` never rewinds a finalized software-dev board (#7553, #5929, #7565).

Mission ``next-lifecycle-integrity-01M77BWP`` WP02 (FR-001..FR-007, FR-016). An advancing
``next`` against a finalized board used to fall through to the mission DAG and issue
``discovery`` (then ``specify``, ``plan`` ... on each ``--result success``), recording false
step rows after the work was finished, accepted, or still in progress. The never-rewind gate
answers those calls from the board instead:

* a finished board (every WP approved/done/canceled) with no fresh acceptance is
  ``blocked`` ``MISSION_AWAITING_ACCEPTANCE`` naming ``spec-kitty accept``;
* a finished board accepted after its newest WP transition is ``terminal``;
* a board step that cannot be dispatched (a WP ``claimed``/``in_progress``) is ``blocked``
  ``BOARD_STEP_NOT_DISPATCHABLE`` naming the WP and its resume command.

A gate answer starts or advances no run, pairs no stale lifecycle record and writes no
issuance record; the CLI records exactly one ``MissionNextInvoked`` row (C-005), which the
tree-snapshot probe requires as its positive control.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from typer.testing import CliRunner
from ulid import ULID

from runtime.next.decision import Decision, DecisionKind
from specify_cli import app as cli_app
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_events
from tests.next.test_finalized_task_routing import _scaffold
from tests.runtime._next_mission_scaffold import analysis_is_current, provision_mission_type_activations

if TYPE_CHECKING:
    from runtime.next.board_status import BoardStatus

pytestmark = [pytest.mark.git_repo, pytest.mark.regression]

runner = CliRunner()

_AWAITING = "MISSION_AWAITING_ACCEPTANCE"
_NOT_DISPATCHABLE = "BOARD_STEP_NOT_DISPATCHABLE"
_GATE_CODES = frozenset({_AWAITING, _NOT_DISPATCHABLE})
_ROW_KINDS = frozenset({DecisionKind.blocked, DecisionKind.terminal})
_SEED_AT = "2026-01-01T00:00:00+00:00"
_FRESH_ACCEPTANCE = "2026-02-01T00:00:00+00:00"
_STALE_ACCEPTANCE = "2025-12-01T00:00:00+00:00"
_AGENT = "claude"
_RUN_INDEX = Path(".kittify") / "runtime" / "feature-runs.json"
_RUNS_DIR = Path(".kittify") / "runtime" / "runs"


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixture stages no charter; the preflight is not what these cells exercise."""
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    passed = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr("specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort", lambda *_a, **_k: passed)
    monkeypatch.setattr("specify_cli.charter_runtime.preflight.hook.run_preflight_warn_only", lambda *_a, **_k: passed)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", message], cwd=repo, check=True, capture_output=True)


def _transition(slug: str, wp_id: str, from_lane: Lane, to_lane: Lane, at: str, actor: str = "fixture") -> StatusEvent:
    return StatusEvent(
        event_id=f"extra-{wp_id}-{to_lane}-{at}",
        mission_slug=slug,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor=actor,
        force=True,
        execution_mode="worktree",
        reason="fixture reopen" if to_lane is Lane.IN_PROGRESS else None,
    )


def _board(
    tmp_path: Path,
    wps: dict[str, Lane],
    *,
    accepted_at: str | None = None,
    extra: Iterable[tuple[str, Lane, Lane, str] | tuple[str, Lane, Lane, str, str]] = (),
) -> tuple[Path, str, Path]:
    """A finalized software-dev board with a minted ULID ``mission_id`` (the lifecycle key).

    ``accepted_at`` is written the way ``record_acceptance`` writes it; ``extra`` appends
    ``(wp_id, from, to, at[, actor])`` transitions after the ``_SEED_AT`` seed.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, slug = _scaffold(repo, wps)
    provision_mission_type_activations(repo, "software-dev")
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_id"] = str(ULID())
    if accepted_at is not None:
        meta.update({"accepted_at": accepted_at, "accepted_by": "operator", "acceptance_mode": "local"})
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    events = [_transition(slug, *row) for row in extra]
    if events:
        seed_status_events(feature_dir, events)
    _commit(repo, "finalize board fixture")
    return repo, slug, feature_dir


def _tree_digest(repo: Path) -> dict[str, bytes]:
    """Every file of the checkout (``.git/`` excluded) as relative path -> its bytes (the fixture is small)."""
    digest: dict[str, bytes] = {}
    for path in sorted(repo.rglob("*")):
        rel = path.relative_to(repo)
        if (rel.parts and rel.parts[0] == ".git") or not path.is_file():
            continue
        digest[rel.as_posix()] = path.read_bytes()
    return digest


def _events_path(slug: str) -> str:
    return f"kitty-specs/{slug}/mission-events.jsonl"


def _rows(repo: Path, slug: str) -> list[dict[str, object]]:
    path = repo / _events_path(slug)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _row_payload(row: dict[str, object]) -> dict[str, object]:
    payload = row.get("payload")
    return payload if isinstance(payload, dict) else row


def _run_artifacts(repo: Path) -> tuple[bool, list[str]]:
    runs = repo / _RUNS_DIR
    files = sorted(p.relative_to(repo).as_posix() for p in runs.rglob("*") if p.is_file()) if runs.is_dir() else []
    return (repo / _RUN_INDEX).is_file(), files


def _invoke_next(repo: Path, slug: str, result: str, monkeypatch: pytest.MonkeyPatch) -> tuple[int, dict[str, object]]:
    monkeypatch.chdir(repo)
    outcome = runner.invoke(cli_app, ["next", "--agent", _AGENT, "--mission", slug, "--result", result, "--json"])
    assert outcome.stdout.strip(), outcome.output
    return outcome.exit_code, json.loads(outcome.stdout)


def _gated_cli_call(repo: Path, slug: str, result: str, monkeypatch: pytest.MonkeyPatch) -> tuple[int, dict[str, object]]:
    """One CLI call that must be a gate answer: the tree changes only by one blocked/terminal row."""
    before = _tree_digest(repo)
    rows_before = _rows(repo, slug)
    runs_before = _run_artifacts(repo)
    code, payload = _invoke_next(repo, slug, result, monkeypatch)
    after = _tree_digest(repo)
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    assert changed == {_events_path(slug)}, (payload, sorted(changed))
    rows_after = _rows(repo, slug)
    assert rows_after[: len(rows_before)] == rows_before
    new_rows = rows_after[len(rows_before) :]
    assert len(new_rows) == 1, new_rows
    assert _row_payload(new_rows[0]).get("decision_kind") in _ROW_KINDS, new_rows[0]
    assert _run_artifacts(repo) == runs_before
    return code, payload


def _bridge(repo: Path, slug: str, result: str = "success") -> Decision:
    from runtime.next.runtime_bridge import decide_next_via_runtime

    return decide_next_via_runtime(_AGENT, slug, result, repo, analysis_currency=analysis_is_current)


def _gated_bridge_call(repo: Path, slug: str, result: str = "success") -> Decision:
    """A bridge-level gate answer leaves the whole checkout untouched (no run started)."""
    before = _tree_digest(repo)
    decision = _bridge(repo, slug, result)
    assert _tree_digest(repo) == before, decision.to_dict()
    return decision


def _assert_awaiting_acceptance(payload: dict[str, object], slug: str) -> None:
    assert payload["kind"] == DecisionKind.blocked, payload
    assert payload["mission_state"] == "accept", payload
    assert payload["error_code"] == _AWAITING, payload
    assert payload["next_command"] == f"spec-kitty accept --mission {slug}", payload
    assert f"spec-kitty accept --mission {slug}" in str(payload["reason"]), payload


# ---------------------------------------------------------------------------
# Cells 1, 2, 5: finished board through the real CLI
# ---------------------------------------------------------------------------


def test_cell1_approved_board_not_accepted_is_blocked_awaiting_acceptance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.APPROVED})

    code, payload = _gated_cli_call(repo, slug, "success", monkeypatch)

    assert code == 1
    _assert_awaiting_acceptance(payload, slug)


def test_cell2_approved_board_accepted_later_is_terminal_on_every_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-001: ten consecutive advances stay terminal and record no step."""
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.DONE}, accepted_at=_FRESH_ACCEPTANCE)

    for _ in range(10):
        code, payload = _gated_cli_call(repo, slug, "success", monkeypatch)
        assert code == 0, payload
        assert payload["kind"] == DecisionKind.terminal, payload
        assert payload["mission_state"] == "done", payload


@pytest.mark.parametrize("result", ["failed", "blocked"])
def test_cell5_failed_or_blocked_result_on_finished_board_is_blocked_never_a_step(result: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.APPROVED})

    code, payload = _gated_cli_call(repo, slug, result, monkeypatch)

    assert code == 1
    _assert_awaiting_acceptance(payload, slug)


# ---------------------------------------------------------------------------
# Cells 3, 4, 6: finished-board shapes and acceptance freshness (bridge level)
# ---------------------------------------------------------------------------


def test_cell3_done_board_not_accepted_is_blocked(tmp_path: Path) -> None:
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.DONE, "WP02": Lane.DONE})

    decision = _gated_bridge_call(repo, slug)

    _assert_awaiting_acceptance(decision.to_dict(), slug)


@pytest.mark.parametrize(
    "wps",
    [
        pytest.param({"WP01": Lane.CANCELED, "WP02": Lane.CANCELED}, id="all-canceled"),
        pytest.param({"WP01": Lane.APPROVED, "WP02": Lane.CANCELED}, id="approved-and-canceled"),
    ],
)
def test_cell4_canceled_endings_count_as_finished(wps: dict[str, Lane], tmp_path: Path) -> None:
    repo, slug, _ = _board(tmp_path, wps)

    decision = _gated_bridge_call(repo, slug)

    _assert_awaiting_acceptance(decision.to_dict(), slug)


@pytest.mark.parametrize(
    ("extra", "expect_terminal"),
    [
        pytest.param(
            [
                ("WP01", Lane.APPROVED, Lane.IN_PROGRESS, "2026-03-01T00:00:00+00:00"),
                ("WP01", Lane.IN_PROGRESS, Lane.APPROVED, "2026-03-02T00:00:00+00:00"),
            ],
            False,
            id="reopen-and-reapproval-needs-acceptance-again",
        ),
        pytest.param(
            [("WP01", Lane.APPROVED, Lane.DONE, "2026-03-01T00:00:00+00:00", "merge")],
            True,
            id="consolidation-done-bookkeeping-is-not-a-fresh-transition",
        ),
        pytest.param(
            [("WP01", Lane.APPROVED, Lane.DONE, "2026-03-01T00:00:00+00:00", "operator")],
            False,
            id="non-merge-done-after-acceptance-is-fresh-work",
        ),
    ],
)
def test_cell6_acceptance_freshness_against_later_board_transitions(
    extra: list[tuple[str, Lane, Lane, str] | tuple[str, Lane, Lane, str, str]], expect_terminal: bool, tmp_path: Path
) -> None:
    """FR-002 freshness: ``accepted_at`` is sticky, so a re-approval needs acceptance again.

    Consolidation's system ``approved -> done`` (actor ``merge``) lands after ``accepted_at``
    but before the landing is recorded; it must not make an accepted Mission look stale.
    """
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.APPROVED}, accepted_at=_FRESH_ACCEPTANCE, extra=extra)

    decision = _gated_bridge_call(repo, slug)

    if expect_terminal:
        assert decision.kind == DecisionKind.terminal, decision.to_dict()
    else:
        assert decision.kind == DecisionKind.blocked, decision.to_dict()
        _assert_awaiting_acceptance(decision.to_dict(), slug)


# ---------------------------------------------------------------------------
# Cell 7: mid-implementation replay (#5929 comment 2, #7565; FR-016)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("busy_lane", [Lane.IN_PROGRESS, Lane.CLAIMED])
def test_cell7_mid_implementation_board_is_blocked_with_a_resume_command(busy_lane: Lane, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": busy_lane})

    code, payload = _gated_cli_call(repo, slug, "success", monkeypatch)

    assert code == 1
    assert payload["kind"] == DecisionKind.blocked, payload
    assert payload["error_code"] == _NOT_DISPATCHABLE, payload
    assert payload["mission_state"] == "implement", payload
    reason = str(payload["reason"])
    assert "WP02" in reason and str(busy_lane) in reason, payload
    assert payload["next_command"] == f"spec-kitty agent action implement WP02 --agent {_AGENT} --mission {slug}", payload


# ---------------------------------------------------------------------------
# Cell 8: a stale run walked onto the DAG before the fix (seeded engine-direct)
# ---------------------------------------------------------------------------


def _seed_run_at(repo: Path, slug: str, step_id: str) -> Path:
    from runtime.next.runtime_bridge import get_or_start_run
    from tests.runtime._next_mission_scaffold import advance_to_step

    advance_to_step(repo, slug, "software-dev", step_id)
    return Path(get_or_start_run(slug, repo, "software-dev").run_dir)


def _run_position(run_dir: Path) -> tuple[str | None, tuple[str, ...]]:
    from runtime.next._internal_runtime.engine import _read_snapshot

    snapshot = _read_snapshot(run_dir)
    return snapshot.issued_step_id, tuple(snapshot.completed_steps)


@pytest.mark.parametrize("stale_step", ["discovery", "plan", "tasks"])
def test_cell8_stale_planning_run_is_answered_by_the_gate_and_left_unchanged(stale_step: str, tmp_path: Path) -> None:
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.DONE})
    run_dir = _seed_run_at(repo, slug, stale_step)
    position = _run_position(run_dir)
    assert position[0] == stale_step

    decision = _gated_bridge_call(repo, slug)

    _assert_awaiting_acceptance(decision.to_dict(), slug)
    assert _run_position(run_dir) == position


def test_cell8_stale_walked_run_through_the_cli_is_answered_by_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-004: the same stale engine-direct run, through the real CLI: one row, run untouched."""
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.DONE})
    run_dir = _seed_run_at(repo, slug, "discovery")
    position = _run_position(run_dir)

    code, payload = _gated_cli_call(repo, slug, "success", monkeypatch)

    assert code == 1
    _assert_awaiting_acceptance(payload, slug)
    assert _run_position(run_dir) == position


def test_cell8_stale_planning_run_on_a_mid_implementation_board_is_blocked(tmp_path: Path) -> None:
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.IN_PROGRESS})
    run_dir = _seed_run_at(repo, slug, "specify")
    position = _run_position(run_dir)

    decision = _gated_bridge_call(repo, slug, "failed")

    assert decision.kind == DecisionKind.blocked, decision.to_dict()
    assert decision.error_code == _NOT_DISPATCHABLE, decision.to_dict()
    assert _run_position(run_dir) == position


# ---------------------------------------------------------------------------
# FR-007 parity: read-only and advancing `next` agree on a finished board
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("accepted_at", "advance_kind", "query_command"),
    [
        pytest.param(None, DecisionKind.blocked, "spec-kitty accept --mission {slug}", id="unaccepted"),
        pytest.param(_STALE_ACCEPTANCE, DecisionKind.blocked, "spec-kitty accept --mission {slug}", id="stale-acceptance"),
        pytest.param(_FRESH_ACCEPTANCE, DecisionKind.terminal, "spec-kitty consolidate --mission {slug}", id="fresh-acceptance"),
    ],
)
def test_query_and_advance_agree_on_a_finished_board(accepted_at: str | None, advance_kind: str, query_command: str, tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import query_current_state

    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.DONE}, accepted_at=accepted_at)

    query = query_current_state(_AGENT, slug, repo, analysis_currency=analysis_is_current)
    advance = _gated_bridge_call(repo, slug)

    assert query.kind == DecisionKind.query, query.to_dict()
    assert query.next_command == query_command.format(slug=slug), query.to_dict()
    assert advance.kind == advance_kind, advance.to_dict()
    if advance_kind == DecisionKind.blocked:
        _assert_awaiting_acceptance(advance.to_dict(), slug)
    else:
        assert advance.next_command is None, advance.to_dict()


# ---------------------------------------------------------------------------
# Cell 9: a stale `started` lifecycle record is never paired by a gate answer (T023)
# ---------------------------------------------------------------------------


def _lifecycle_phases(repo: Path) -> list[tuple[str, str]]:
    from specify_cli.invocation.lifecycle import read_lifecycle_records

    return [(record.phase, record.canonical_action_id) for record in read_lifecycle_records(repo)]


def test_cell9_gate_answer_leaves_the_stale_started_record_unpaired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, feature_dir = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.APPROVED})
    tasks_md = feature_dir / "tasks.md"
    tasks_text = tasks_md.read_text(encoding="utf-8")
    tasks_md.unlink()
    _commit(repo, "unfinalize the board")

    seed_code, seeded = _invoke_next(repo, slug, "success", monkeypatch)
    assert seed_code == 0, seeded
    assert seeded["kind"] == DecisionKind.step and seeded["mission_state"] == "discovery", seeded
    phases = _lifecycle_phases(repo)
    assert [phase for phase, _ in phases] == ["started"], phases  # positive control: the seeding call wrote `started`

    tasks_md.write_text(tasks_text, encoding="utf-8")
    _commit(repo, "restore the finalized board")
    code, payload = _gated_cli_call(repo, slug, "success", monkeypatch)

    assert code == 1
    _assert_awaiting_acceptance(payload, slug)
    assert _lifecycle_phases(repo) == phases


def _advance_board(repo: Path, slug: str, feature_dir: Path, wp_id: str, from_lane: Lane, to_lane: Lane, at: str) -> None:
    seed_status_events(feature_dir, [_transition(slug, wp_id, from_lane, to_lane, at)])
    _commit(repo, f"{wp_id} -> {to_lane}")


def test_cell9_board_dispatched_review_is_paired_when_the_gate_answers_awaiting_acceptance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A WP step the board handed out is a real issuance: the gate answer still pairs its completion."""
    repo, slug, feature_dir = _board(tmp_path, {"WP01": Lane.FOR_REVIEW})
    code, dispatched = _invoke_next(repo, slug, "success", monkeypatch)
    assert code == 0 and dispatched["kind"] == DecisionKind.step and dispatched["action"] == "review", dispatched
    assert _lifecycle_phases(repo) == [("started", "review::review")]

    _advance_board(repo, slug, feature_dir, "WP01", Lane.FOR_REVIEW, Lane.APPROVED, "2026-01-02T00:00:00+00:00")
    code, payload = _invoke_next(repo, slug, "success", monkeypatch)

    assert code == 1
    _assert_awaiting_acceptance(payload, slug)
    assert _lifecycle_phases(repo) == [("started", "review::review"), ("completed", "review::review")]


def test_cell9_board_dispatched_implement_is_paired_failed_when_the_board_cannot_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, feature_dir = _board(tmp_path, {"WP01": Lane.PLANNED})
    # The analysis gate is not what this cell exercises: the fixture records no analysis report.
    monkeypatch.setattr("runtime.next.runtime_bridge_io.mission_declares_analyze_step", lambda *_a, **_k: False)
    code, dispatched = _invoke_next(repo, slug, "success", monkeypatch)
    assert code == 0 and dispatched["kind"] == DecisionKind.step and dispatched["action"] == "implement", dispatched
    assert _lifecycle_phases(repo) == [("started", "implement::implement")]

    _advance_board(repo, slug, feature_dir, "WP01", Lane.PLANNED, Lane.IN_PROGRESS, "2026-01-02T00:00:00+00:00")
    code, payload = _invoke_next(repo, slug, "failed", monkeypatch)

    assert code == 1
    assert payload["error_code"] == _NOT_DISPATCHABLE, payload
    assert _lifecycle_phases(repo) == [("started", "implement::implement"), ("failed", "implement::implement")]


# ---------------------------------------------------------------------------
# Cell 10: residual pins (documented, not fixed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("walked_step", ["analyze", "implement"])
def test_cell10_residual_stale_run_at_an_authoritative_step_keeps_the_engine_path(walked_step: str, tmp_path: Path) -> None:
    # residual: indistinguishable from a legitimate run (research.md)
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.APPROVED})
    _seed_run_at(repo, slug, walked_step)

    decision = _bridge(repo, slug)

    assert decision.error_code not in _GATE_CODES, decision.to_dict()


# ---------------------------------------------------------------------------
# FR-006 positive controls: the gate leaves every other path alone
# ---------------------------------------------------------------------------


def test_control_stale_planning_run_with_a_claimable_wp_dispatches_from_the_board_for_any_result(tmp_path: Path) -> None:
    """T022: the widened front phase dispatches the board's WP and leaves the stale run where it was."""
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.PLANNED})
    run_dir = _seed_run_at(repo, slug, "discovery")
    position = _run_position(run_dir)

    decision = _bridge(repo, slug, "failed")

    assert decision.kind == DecisionKind.step, decision.to_dict()
    assert (decision.action, decision.wp_id) == ("implement", "WP02")
    assert _run_position(run_dir) == position


def test_control_walked_run_at_review_issues_accept_then_terminal(tmp_path: Path) -> None:
    """An authoritative next-driven run keeps the engine path (R-3): accept, then terminal."""
    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED})
    run_dir = _seed_run_at(repo, slug, "review")

    to_accept = _bridge(repo, slug)
    assert to_accept.error_code not in _GATE_CODES, to_accept.to_dict()
    assert to_accept.kind == DecisionKind.step and to_accept.mission_state == "accept", to_accept.to_dict()
    assert _run_position(run_dir)[0] == "accept"

    finished = _bridge(repo, slug)
    assert finished.kind == DecisionKind.terminal, finished.to_dict()
    assert finished.error_code not in _GATE_CODES


def test_control_mission_without_work_packages_still_starts_the_dag(tmp_path: Path) -> None:
    repo, slug, _ = _board(tmp_path, {})

    decision = _bridge(repo, slug)

    assert decision.kind == DecisionKind.step, decision.to_dict()
    assert decision.mission_state == "discovery"
    assert decision.error_code not in _GATE_CODES


def test_control_documentation_mission_with_a_finished_board_is_not_gated(tmp_path: Path) -> None:
    """Gate scope is software-dev only (decision plan.next.gate_scope_family)."""
    repo, slug, feature_dir = _board(tmp_path, {"WP01": Lane.APPROVED, "WP02": Lane.DONE})
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_type"] = "documentation"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    provision_mission_type_activations(repo, "documentation")
    _commit(repo, "documentation mission")

    decision = _bridge(repo, slug)

    assert decision.error_code not in _GATE_CODES, decision.to_dict()
    assert decision.next_command is None
    assert decision.suppress_step_pairing is False
    assert (repo / _RUN_INDEX).is_file()  # the DAG path started its run, as before


def test_control_reopened_accepted_mission_follows_the_board(tmp_path: Path) -> None:
    repo, slug, _ = _board(
        tmp_path,
        {"WP01": Lane.APPROVED},
        accepted_at=_FRESH_ACCEPTANCE,
        extra=[("WP01", Lane.APPROVED, Lane.FOR_REVIEW, "2026-03-01T00:00:00+00:00")],
    )

    decision = _bridge(repo, slug)

    assert decision.kind == DecisionKind.step, decision.to_dict()
    assert (decision.action, decision.wp_id) == ("review", "WP01")


# ---------------------------------------------------------------------------
# Door reads: the bootstrap read plus the landed-routing read of the blocked/terminal row
# ---------------------------------------------------------------------------


def test_gated_answer_reads_the_status_door_twice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One bootstrap door read, plus the ``MissionNextInvoked`` row's landed-routing read (accepted)."""
    import specify_cli.status as status_package
    from runtime.next.next_invocation_lifecycle import emit_mission_next_invoked

    repo, slug, _ = _board(tmp_path, {"WP01": Lane.APPROVED})
    real: Callable[..., Any] = status_package.resolve_status_read
    calls: list[object] = []

    def _spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(status_package, "resolve_status_read", _spy)

    decision = _bridge(repo, slug)
    assert len(calls) == 1, "the gate reuses the bootstrap's one door read"
    emit_mission_next_invoked(_AGENT, "success", slug, repo, decision)

    assert decision.error_code == _AWAITING
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# T023: pairing after decide_next, skipped for a gate answer, kept on the raise path
# ---------------------------------------------------------------------------


def _pair_spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from specify_cli.cli.commands import next_cmd

    paired: list[str] = []
    monkeypatch.setattr(next_cmd, "_pair_previous_lifecycle_record", lambda _agent, _slug, result, *_a, **_k: paired.append(result))
    return paired


def _decision(*, kind: str = DecisionKind.blocked, **fields: Any) -> Decision:
    return Decision(kind=kind, agent=_AGENT, mission_slug="m", mission="software-dev", mission_state="accept", timestamp=_SEED_AT, **fields)


@pytest.mark.parametrize(
    ("suppress", "board_action", "expected"),
    [(True, False, []), (True, True, ["success"]), (False, False, ["success"]), (False, True, ["success"])],
)
def test_pairing_is_skipped_only_for_a_suppressing_decision_over_a_stale_issuance(
    suppress: bool, board_action: bool, expected: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from specify_cli.cli.commands import next_cmd

    paired = _pair_spy(monkeypatch)
    monkeypatch.setattr(next_cmd, "decide_next", lambda *_a, **_k: _decision(suppress_step_pairing=suppress))
    monkeypatch.setattr(next_cmd, "_latest_issuance_is_board_action", lambda *_a, **_k: board_action)

    next_cmd._decide_and_pair(_AGENT, "m", "success", Path("."), True, owned=None)

    assert paired == expected


def test_pairing_still_runs_when_decide_next_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands import next_cmd

    paired = _pair_spy(monkeypatch)
    sentinel = RuntimeError("decide_next failed")

    def _raise(*_a: object, **_k: object) -> Decision:
        raise sentinel

    monkeypatch.setattr(next_cmd, "decide_next", _raise)

    with pytest.raises(RuntimeError) as excinfo:
        next_cmd._decide_and_pair(_AGENT, "m", "failed", Path("."), True, owned=None)

    assert excinfo.value is sentinel
    assert paired == ["failed"]


def test_pairing_still_runs_when_meta_cannot_be_read(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import typer

    from specify_cli.cli.commands import next_cmd
    from specify_cli.core.paths import MissionMetaReadError

    paired = _pair_spy(monkeypatch)

    def _raise(*_a: object, **_k: object) -> Decision:
        raise MissionMetaReadError(Path("kitty-specs/m/meta.json"), ValueError("bad json"))

    monkeypatch.setattr(next_cmd, "decide_next", _raise)

    with pytest.raises(typer.Exit):
        next_cmd._decide_and_pair(_AGENT, "m", "success", Path("."), True, owned=None)

    assert paired == ["success"]
    assert json.loads(capsys.readouterr().out)["error_code"] == "MISSION_META_READ_ERROR"


# ---------------------------------------------------------------------------
# T013: the human renderers print the next command
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("renderer", "fields", "next_line"),
    [
        pytest.param(
            "_print_standard_human",
            {"reason": "awaits acceptance", "next_command": "spec-kitty accept --mission m"},
            "  Next: spec-kitty accept --mission m",
            id="blocked",
        ),
        pytest.param(
            "_print_query_details",
            {"kind": DecisionKind.query, "reason": "preview", "next_command": "spec-kitty next --agent <agent> --mission m --result success"},
            "  Next: spec-kitty next --agent <agent> --mission m --result success",
            id="query",
        ),
        pytest.param("_print_standard_human", {"reason": "blocked"}, None, id="no-next-command-prints-no-next-line"),
    ],
)
def test_human_output_prints_the_next_command(renderer: str, fields: dict[str, Any], next_line: str | None, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.cli.commands import next_cmd

    getattr(next_cmd, renderer)(_decision(**fields))

    out = capsys.readouterr().out
    if next_line is None:
        assert "Next:" not in out
    else:
        assert next_line in out


# ---------------------------------------------------------------------------
# Run-authority scope (operator ruling plan.next.authoritative_run_scope) and fallbacks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("step_id", "gate", "board_dispatch"),
    [
        ("discovery", True, True),
        ("specify", True, True),
        ("plan", True, True),
        ("tasks", True, False),
        ("analyze", False, False),
        ("implement", False, False),
        ("review", False, False),
        ("accept", False, False),
        (None, False, False),
    ],
)
def test_issued_step_scope_split_by_use(step_id: str | None, gate: bool, board_dispatch: bool) -> None:
    from runtime.next import runtime_bridge as bridge

    assert bridge._issued_step_is_rewindable(step_id, bridge._GATE_SCOPE) is gate
    assert bridge._issued_step_is_rewindable(step_id, bridge._BOARD_DISPATCH_SCOPE) is board_dispatch


def test_unreadable_run_snapshot_is_authoritative(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    from runtime.next import runtime_bridge as bridge

    with caplog.at_level("DEBUG", logger="runtime.next.runtime_bridge"):
        assert bridge._run_dir_is_rewindable(tmp_path / "missing-run", bridge._GATE_SCOPE) is False

    assert "unreadable, treating the run as authoritative" in caplog.text


def test_run_lookup_error_lets_the_bootstrap_report_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A ``RunStateMissing`` (or any run-read error) is not answered by the gate."""
    from runtime.next import runtime_bridge as bridge

    def _missing(*_a: object, **_k: object) -> None:
        raise RuntimeError("run state missing")

    monkeypatch.setattr("runtime.next.runtime_bridge_io._existing_run_ref", _missing)

    assert bridge._gate_run_lookup("m", tmp_path, "software-dev", None) == (False, None)


def test_not_dispatchable_answer_without_a_named_wp_points_at_the_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from runtime.next import runtime_bridge as bridge
    from runtime.next import runtime_bridge_decision_mapping as mapping

    monkeypatch.setattr(mapping, "_board_step_busy_wp", lambda *_a: None)
    inputs = bridge._GateInputs(agent=_AGENT, mission_slug="m", mission_type="software-dev", now=_SEED_AT, progress=None, origin={}, run_id=None)
    resolved = mapping._FinalizedBoardStep(board_step="review", task_board_dir=tmp_path, board=cast("BoardStatus", None))  # unread by the patched helper

    decision = bridge._not_dispatchable_answer(inputs, resolved, mapping._WP_BOARD_DECLINE)

    assert decision.error_code == _NOT_DISPATCHABLE
    assert decision.next_command == "spec-kitty agent tasks status --mission m"
    assert decision.suppress_step_pairing is True


def test_busy_wp_lookup_names_nothing_for_a_step_without_busy_lanes(tmp_path: Path) -> None:
    from runtime.next import runtime_bridge_decision_mapping as mapping

    assert mapping._board_step_busy_wp("accept", tmp_path, cast("BoardStatus", None)) is None  # no lane is read for this step


def _unresolvable_error(name: str) -> Exception:
    from mission_runtime import ActionContextError
    from specify_cli.lanes.persistence import CorruptLanesError

    errors: dict[str, Exception] = {
        "corrupt-lanes": CorruptLanesError("lanes.json is corrupt"),
        "unassigned-wp": ValueError("WP01 is not assigned to any lane"),
        "unreadable-file": FileNotFoundError("tasks/WP01.md"),
        "no-context": ActionContextError("MISSION_CONTEXT_UNRESOLVED", "mission context unresolved"),
    }
    return errors[name]


@pytest.mark.parametrize("error", ["corrupt-lanes", "unassigned-wp", "unreadable-file", "no-context"])
def test_unresolvable_board_dispatch_falls_through(error: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A dispatch the gate cannot resolve is left to the path that reports it today."""
    from runtime.next import runtime_bridge as bridge
    from runtime.next import runtime_bridge_decision_mapping as mapping

    def _unresolvable(*_a: object, **_k: object) -> None:
        raise _unresolvable_error(error)

    monkeypatch.setattr(mapping, "_board_step_action", _unresolvable)
    resolved = mapping._FinalizedBoardStep(board_step="implement", task_board_dir=tmp_path, board=cast("BoardStatus", None))

    assert bridge._gate_board_action(resolved, "m", tmp_path, None) is None


@pytest.mark.parametrize("error", [RuntimeError("defect"), KeyError("defect")], ids=["runtime-error", "key-error"])
def test_unexpected_board_dispatch_error_propagates(error: Exception, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The gate's catch is narrow: a defect is never silently turned into a fall-through."""
    from runtime.next import runtime_bridge as bridge
    from runtime.next import runtime_bridge_decision_mapping as mapping

    def _defect(*_a: object, **_k: object) -> None:
        raise error

    monkeypatch.setattr(mapping, "_board_step_action", _defect)
    resolved = mapping._FinalizedBoardStep(board_step="implement", task_board_dir=tmp_path, board=cast("BoardStatus", None))

    with pytest.raises(type(error)):
        bridge._gate_board_action(resolved, "m", tmp_path, None)
