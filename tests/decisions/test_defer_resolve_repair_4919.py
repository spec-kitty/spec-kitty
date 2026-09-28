"""#4919: decisions survive defer-then-resolve and repair.

The documented Decision Moment flow ``open -> defer -> resolve`` emits TWO
real ``DecisionPointResolved`` events for one decision -- ``defer`` with
``terminal_outcome=deferred``, then ``resolve`` with
``terminal_outcome=resolved``. Before this fix, the canonical fold
(``index_fold.fold_events``) rejected "more than one DecisionPointResolved",
so rebuilding the index (``doctor decisions --repair`` after the index is
missing or diverged) silently DROPPED the decision and exited 0.

Contracts pinned here:

* ``open -> defer -> resolve`` then deleting ``decisions/index.json`` --
  ``doctor decisions --repair`` rebuilds the decision as ``resolved`` with
  its final answer. Driven through the real CLI.
* A log already on disk with the (deferred, resolved) pair, in EITHER
  order, rebuilds as resolved -- the fold must not depend on append order
  (the event-log git merge driver re-sorts by ``(at, event_id)``, #4941
  class).
* The read-only ``doctor decisions`` reports a genuinely unfoldable
  decision (e.g. two ``DecisionPointOpened`` events, or a malformed
  payload) as a problem (``clean: false``, id in ``malformed_folds``), and
  also flags an index entry whose status differs from the folded status.
* ``doctor decisions --repair`` never removes a decision it cannot fold; it
  exits 1 and names the decision(s) with a remedy. Under ``--json`` it
  emits exactly one JSON document, then exits 1.
* ``--repair`` never wipes a non-wire index field (``summary_json``,
  ``slot_key`` attribution) of an entry it reconciles.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli import app as root_app
from specify_cli.cli.commands._decisions_doctor import (
    _ledger_dir,
    run_decisions_reconciliation,
)
from specify_cli.decisions import store as _store
from specify_cli.decisions.models import DecisionStatus, IndexEntry, OriginFlow
from specify_cli.decisions.service import defer_decision, open_decision, resolve_decision

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID = "01KTEST_4919_MISSION_00000"
MISSION_SLUG = "defer-resolve-repair-4919"

runner = CliRunner()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mission_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / MISSION_SLUG


def _setup_project(repo_root: Path) -> None:
    """Mint a project root (``.kittify`` marker) with a mission's ``meta.json``.

    Mirrors ``tests/decisions/test_decisions_reconciler.py::_setup_meta`` and
    ``tests/specify_cli/cli/commands/test_decision.py::_setup_mission`` --
    the ``.kittify`` marker is what ``locate_project_root()`` anchors on, so
    the real CLI resolves ``tmp_path`` as the project root exactly
    like a real checkout instead of walking up past it.
    """
    (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
    mission_dir = _mission_dir(repo_root)
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _events_path(repo_root: Path) -> Path:
    return _mission_dir(repo_root) / "status.events.jsonl"


def _read_events(repo_root: Path) -> list[dict[str, Any]]:
    path = _events_path(repo_root)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _events_for_decision(repo_root: Path, decision_id: str) -> list[dict[str, Any]]:
    return [e for e in _read_events(repo_root) if e.get("payload", {}).get("decision_point_id") == decision_id]


def _swap_resolved_event_order(repo_root: Path, decision_id: str) -> None:
    """Swap the on-disk line order of *decision_id*'s two
    ``DecisionPointResolved`` events -- the exact reshuffle the event-log git
    merge driver (``status/event_log_merge.py:62-68``, sorts by
    ``(at, event_id)``) can produce across a merge (the #4941 ordering-bug
    class). Proves the fold does not depend on append order."""
    path = _events_path(repo_root)
    lines = _read_events(repo_root)
    resolved_idx = [
        i for i, e in enumerate(lines) if e.get("event_type") == "DecisionPointResolved" and e.get("payload", {}).get("decision_point_id") == decision_id
    ]
    assert len(resolved_idx) == 2, "test setup: expected exactly two DecisionPointResolved events to swap"
    i, j = resolved_idx
    lines[i], lines[j] = lines[j], lines[i]
    path.write_text("\n".join(json.dumps(e) for e in lines) + "\n", encoding="utf-8")


def _duplicate_opened_event(repo_root: Path, decision_id: str) -> None:
    """Append a second ``DecisionPointOpened`` envelope for *decision_id* --
    an ``open -> open`` corruption the canonical fold cannot resolve
    (mirrors ``test_repair_reports_malformed_fold_instead_of_crashing`` in
    ``tests/decisions/test_decisions_reconciler.py``)."""
    lines = _read_events(repo_root)
    opened = [e for e in lines if e.get("event_type") == "DecisionPointOpened" and e.get("payload", {}).get("decision_point_id") == decision_id]
    assert len(opened) == 1, "test setup: expected exactly one DecisionPointOpened event to duplicate"
    lines.append(dict(opened[0]))
    path = _events_path(repo_root)
    path.write_text("\n".join(json.dumps(e) for e in lines) + "\n", encoding="utf-8")


def _open_defer_resolve(repo_root: Path, *, step_id: str, final_answer: str = "final answer") -> str:
    """Drive a decision through the real ``open -> defer -> resolve`` flow
    via the service functions (mirrors the reconciler tests' origin choice:
    step_id-origin, to avoid the #4817 slot_key ``lossy_attribution``
    refusal)."""
    resp = open_decision(
        repo_root,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id=step_id,
        input_key=f"{step_id}-input",
        question=f"{step_id}?",
        actor="alice",
    )
    defer_decision(
        repo_root,
        MISSION_SLUG,
        resp.decision_id,
        rationale="later",
        actor="alice",
    )
    resolve_decision(
        repo_root,
        MISSION_SLUG,
        resp.decision_id,
        final_answer=final_answer,
        actor="alice",
    )
    return str(resp.decision_id)


def _invoke_agent(args: list[str], cwd: Path) -> Result:
    """Invoke ``spec-kitty agent <args>`` through the ROOT Typer app (not
    the ``agent`` sub-app directly), so top-level registration and the root
    callback are exercised too."""
    with contextlib.chdir(cwd):
        return runner.invoke(root_app, ["agent", *args], catch_exceptions=False)


def _invoke_doctor(args: list[str], cwd: Path) -> Result:
    """Invoke ``spec-kitty doctor <args>`` through the ROOT Typer app (not
    the ``doctor`` sub-app directly)."""
    with contextlib.chdir(cwd):
        return runner.invoke(root_app, ["doctor", *args], catch_exceptions=False)


# ---------------------------------------------------------------------------
# Real CLI: open -> defer -> resolve -> delete index -> --repair
# ---------------------------------------------------------------------------


def test_cli_defer_then_resolve_survives_index_rebuild(tmp_path: Path) -> None:
    """Pre-fix: `malformed_folds:[D]`, `count:0`, exit 0 -- the decision
    vanished from the rebuilt index. This drives the full flow through the
    real CLI, not the service functions directly."""
    _setup_project(tmp_path)

    open_result = _invoke_agent(
        [
            "decision",
            "open",
            "--mission",
            MISSION_SLUG,
            "--flow",
            "specify",
            "--step-id",
            "cli-step",
            "--input-key",
            "cli-input",
            "--question",
            "How many kittens?",
        ],
        tmp_path,
    )
    assert open_result.exit_code == 0, open_result.output
    open_lines = [line for line in open_result.output.splitlines() if line.strip()]
    assert len(open_lines) == 1, f"expected exactly 1 JSON line, got: {open_result.output!r}"
    decision_id = json.loads(open_lines[0])["decision_id"]

    defer_result = _invoke_agent(
        ["decision", "defer", decision_id, "--mission", MISSION_SLUG, "--rationale", "need more research"],
        tmp_path,
    )
    assert defer_result.exit_code == 0, defer_result.output

    resolve_result = _invoke_agent(
        ["decision", "resolve", decision_id, "--mission", MISSION_SLUG, "--final-answer", "42 kittens"],
        tmp_path,
    )
    assert resolve_result.exit_code == 0, resolve_result.output

    ledger_dir = _ledger_dir(tmp_path, MISSION_SLUG)
    index_path = _store.index_path(ledger_dir)
    assert index_path.exists()
    index_path.unlink()

    repair_result = _invoke_doctor(
        ["decisions", "--mission", MISSION_SLUG, "--repair", "--json"],
        tmp_path,
    )
    payload = json.loads(repair_result.output)
    assert payload["malformed_folds"] == [], repair_result.output
    assert decision_id in payload["index_decision_ids"], repair_result.output
    assert repair_result.exit_code == 0, repair_result.output

    healed = _store.load_index(ledger_dir)
    healed_entry = next(e for e in healed.entries if e.decision_id == decision_id)
    assert healed_entry.status.value == "resolved"
    assert healed_entry.final_answer == "42 kittens"


# ---------------------------------------------------------------------------
# An existing on-disk log with the (deferred, resolved) pair, in EITHER
# order, rebuilds as resolved.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("swap_order", [False, True], ids=["deferred-then-resolved", "resolved-then-deferred"])
def test_existing_log_rebuilds_as_resolved_in_either_order(tmp_path: Path, swap_order: bool) -> None:
    _setup_project(tmp_path)
    decision_id = _open_defer_resolve(tmp_path, step_id="order-step", final_answer="the answer")
    if swap_order:
        _swap_resolved_event_order(tmp_path, decision_id)

    ledger_dir = _ledger_dir(tmp_path, MISSION_SLUG)
    _store.index_path(ledger_dir).unlink()

    with pytest.raises(typer.Exit) as exc_info:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=True)
    assert exc_info.value.exit_code == 0

    healed = _store.load_index(ledger_dir)
    healed_entry = next(e for e in healed.entries if e.decision_id == decision_id)
    assert healed_entry.status.value == "resolved"
    assert healed_entry.final_answer == "the answer"


# ---------------------------------------------------------------------------
# A genuinely unfoldable decision (two DecisionPointOpened)
# ---------------------------------------------------------------------------


def test_diagnose_reports_unfoldable_decision_without_repair(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Read-only `doctor decisions` (no --repair): reports the malformed
    decision (`clean: false`, id in `malformed_folds`) and exits 0."""
    _setup_project(tmp_path)
    resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="diagnose-step",
        input_key="diagnose-input",
        question="Q?",
        actor="alice",
    )
    _duplicate_opened_event(tmp_path, resp.decision_id)

    with pytest.raises(typer.Exit) as exc_info:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=False)
    assert exc_info.value.exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["clean"] is False
    assert resp.decision_id in payload["malformed_folds"]

    ledger_dir = _ledger_dir(tmp_path, MISSION_SLUG)
    unchanged = _store.load_index(ledger_dir)
    assert any(e.decision_id == resp.decision_id for e in unchanged.entries), "diagnose (read-only) must never mutate the index"


def test_repair_refuses_malformed_decision_with_existing_entry(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--repair` on a decision whose events fold to malformed: the index
    entry and log stay unchanged for that decision, the command names it and
    exits 1 -- exactly one JSON document carrying the id and the remedy."""
    _setup_project(tmp_path)
    bad_resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="malformed-step",
        input_key="malformed-step-input",
        question="Q?",
        actor="alice",
    )
    _duplicate_opened_event(tmp_path, bad_resp.decision_id)
    ledger_dir = _ledger_dir(tmp_path, MISSION_SLUG)
    original_bad_entry = next(e for e in _store.load_index(ledger_dir).entries if e.decision_id == bad_resp.decision_id)

    # Diverge the index so --repair actually fires (drop an unrelated,
    # cleanly-folding decision).
    other_resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="clean-step",
        input_key="clean-input",
        question="Q?",
        actor="alice",
    )
    index = _store.load_index(ledger_dir)
    truncated = index.model_copy(update={"entries": tuple(e for e in index.entries if e.decision_id != other_resp.decision_id)})
    _store.save_index(ledger_dir, truncated)

    with pytest.raises(typer.Exit) as exc_info:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=True)
    assert exc_info.value.exit_code == 1, "malformed decision must make --repair exit non-zero"

    captured = capsys.readouterr()
    # Exactly one JSON document on stdout (never a second JSON document).
    stdout_lines = [line for line in captured.out.splitlines() if line.strip()]
    payload = json.loads("\n".join(stdout_lines))
    assert payload["malformed_folds"] == [bad_resp.decision_id]
    assert bad_resp.decision_id in payload["index_decision_ids"], "index entry unchanged for the malformed decision"
    # The SAME single JSON document must carry the remedy -- "left in place" plus the inspect
    # pointer -- not just the bare id.
    assert payload["remedy"] is not None, payload
    assert "left in place" in payload["remedy"]
    assert "spec-kitty agent decision list" in payload["remedy"]
    assert "status.events.jsonl" in payload["remedy"]

    healed = _store.load_index(ledger_dir)
    healed_bad_entry = next(e for e in healed.entries if e.decision_id == bad_resp.decision_id)
    assert healed_bad_entry == original_bad_entry, "repair must never rewrite a malformed decision's index entry"
    # The OTHER (cleanly-folding) decision was healed as usual.
    assert any(e.decision_id == other_resp.decision_id for e in healed.entries)

    events_for_bad = _events_for_decision(tmp_path, bad_resp.decision_id)
    assert len(events_for_bad) == 2, "the malformed decision's log must be untouched by a refused repair"


def test_repair_refuses_malformed_decision_with_no_prior_entry(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The no-prior-entry variant: the malformed decision was never in the
    index (never fabricated), and --repair still names it and exits 1
    (both the id AND the remedy text)."""
    _setup_project(tmp_path)
    bad_resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="orphan-step",
        input_key="orphan-input",
        question="Q?",
        actor="alice",
    )
    _duplicate_opened_event(tmp_path, bad_resp.decision_id)

    ledger_dir = _ledger_dir(tmp_path, MISSION_SLUG)
    index = _store.load_index(ledger_dir)
    # Drop the malformed decision's own (pre-corruption) index entry so
    # there is genuinely no prior on-disk copy to fall back to.
    no_prior = index.model_copy(update={"entries": tuple(e for e in index.entries if e.decision_id != bad_resp.decision_id)})
    _store.save_index(ledger_dir, no_prior)

    with pytest.raises(typer.Exit) as exc_info:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=True)
    assert exc_info.value.exit_code == 1

    captured = capsys.readouterr()
    assert bad_resp.decision_id in captured.out
    assert "left in place" in captured.out
    assert "spec-kitty agent decision list" in captured.out
    assert "status.events.jsonl" in captured.out

    healed = _store.load_index(ledger_dir)
    assert not any(e.decision_id == bad_resp.decision_id for e in healed.entries), "a decision with no prior entry must never be fabricated"


# ---------------------------------------------------------------------------
# The "anything else is malformed" half of the rule --
# data-model: "Any other multi-outcome set is malformed". A mutation that
# accepted any pair of DecisionPointResolved outcomes and picked one of them
# must fail these.
# ---------------------------------------------------------------------------


def _resolved_envelope_for(repo_root: Path, decision_id: str) -> dict[str, Any]:
    """Return the real, CLI/service-emitted ``DecisionPointResolved``
    envelope for *decision_id* (there must be exactly one on disk already,
    from a prior ``defer_decision``/``resolve_decision`` call) -- used as
    the SHAPE template for hand-written corrupted envelopes below, so the
    corruption is "a real envelope with the outcome(s) changed", not an
    invented shape."""
    matches = [e for e in _events_for_decision(repo_root, decision_id) if e.get("event_type") == "DecisionPointResolved"]
    assert len(matches) == 1, "test setup: expected exactly one real DecisionPointResolved envelope to copy"
    return matches[0]


def _write_corrupted_resolved_outcomes(repo_root: Path, decision_id: str, outcomes: list[str]) -> None:
    """Replace *decision_id*'s single real ``DecisionPointResolved`` envelope
    with ``len(outcomes)`` copies of it, one per outcome in *outcomes* --
    copying a real emitted envelope's shape but forcing a combination the
    write path would never itself produce, to prove the fold's
    malformed-rejection half."""
    template = _resolved_envelope_for(repo_root, decision_id)
    other_lines = [
        e for e in _read_events(repo_root) if not (e.get("event_type") == "DecisionPointResolved" and e.get("payload", {}).get("decision_point_id") == decision_id)
    ]
    corrupted: list[dict[str, Any]] = []
    for index, outcome in enumerate(outcomes):
        envelope = json.loads(json.dumps(template))
        envelope["event_id"] = f"{template['event_id']}-corrupt{index}"
        envelope["payload"]["terminal_outcome"] = outcome
        corrupted.append(envelope)
    all_events = other_lines + corrupted
    _events_path(repo_root).write_text("\n".join(json.dumps(e) for e in all_events) + "\n", encoding="utf-8")


_UNFOLDABLE_OUTCOMES = pytest.mark.parametrize(
    "outcomes",
    [
        ["resolved", "resolved"],
        ["resolved", "canceled"],
        ["deferred", "deferred"],
        ["deferred", "resolved", "resolved"],
    ],
    ids=["two-resolved", "resolved-and-canceled", "two-deferred", "three-events"],
)


@_UNFOLDABLE_OUTCOMES
def test_unfoldable_resolved_combinations_reported_and_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    outcomes: list[str],
) -> None:
    """Every multi-outcome ``DecisionPointResolved`` combination OTHER than
    an allowed deferred+resolved pair is malformed (data-model: "Any other
    multi-outcome set is malformed"): read-only diagnose reports it
    (`clean: false`, id in `malformed_folds`), and `--repair` refuses it
    (exits 1, index entry and log byte-identical for this decision)."""
    _setup_project(tmp_path)
    resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id=f"malformed-{'-'.join(outcomes)}",
        input_key="malformed-input",
        question="Q?",
        actor="alice",
    )
    defer_decision(tmp_path, MISSION_SLUG, resp.decision_id, rationale="later", actor="alice")
    _write_corrupted_resolved_outcomes(tmp_path, resp.decision_id, outcomes)

    ledger_dir = _ledger_dir(tmp_path, MISSION_SLUG)
    index_before = _store.index_path(ledger_dir).read_bytes()
    events_before = _events_for_decision(tmp_path, resp.decision_id)

    # Read-only diagnose reports it, and never mutates the index.
    with pytest.raises(typer.Exit) as diag_exc:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=False)
    assert diag_exc.value.exit_code == 0
    diag_payload = json.loads(capsys.readouterr().out)
    assert diag_payload["clean"] is False, diag_payload
    assert resp.decision_id in diag_payload["malformed_folds"], diag_payload
    assert _store.index_path(ledger_dir).read_bytes() == index_before

    # --repair refuses: exits 1, names the id, and leaves the index entry
    # and the log for this decision byte-identical.
    with pytest.raises(typer.Exit) as repair_exc:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=True)
    assert repair_exc.value.exit_code == 1, "a genuinely unfoldable combination must make --repair exit non-zero"
    repair_payload = json.loads(capsys.readouterr().out)
    assert repair_payload["malformed_folds"] == [resp.decision_id], repair_payload
    assert resp.decision_id in repair_payload["index_decision_ids"], "index entry unchanged for the malformed decision"

    assert _store.index_path(ledger_dir).read_bytes() == index_before, "repair must never rewrite the malformed decision's index entry"
    assert _events_for_decision(tmp_path, resp.decision_id) == events_before, "repair must never touch the malformed decision's log"


@_UNFOLDABLE_OUTCOMES
def test_select_terminal_event_folderror_names_the_outcomes(outcomes: list[str]) -> None:
    """Fold-level unit assertion (single authority, `index_fold.py`):
    `_select_terminal_event` raises `FoldError` for every unfoldable
    combination, and the message names the outcomes involved -- so a
    mutation that swallowed the malformed case silently would be caught at
    this level too, not just through the CLI."""
    from specify_cli.decisions.index_fold import FoldError, _select_terminal_event

    events: list[Mapping[str, Any]] = [{"payload": {"terminal_outcome": outcome}} for outcome in outcomes]
    with pytest.raises(FoldError) as exc_info:
        _select_terminal_event(events)
    message = str(exc_info.value)
    for outcome in outcomes:
        assert outcome in message, message


# ---------------------------------------------------------------------------
# Stale status: index says deferred, log folds to resolved
# ---------------------------------------------------------------------------


def test_stale_index_status_reported_by_diagnose_and_healed_by_repair(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The id-set agrees (the decision is in both the log and the index),
    but the index's recorded status is stale -- diagnose must catch this,
    not just a missing/orphaned id-set comparison."""
    _setup_project(tmp_path)
    decision_id = _open_defer_resolve(tmp_path, step_id="stale-status-step", final_answer="answer")

    ledger_dir = _ledger_dir(tmp_path, MISSION_SLUG)
    index = _store.load_index(ledger_dir)
    stale_entry = next(e for e in index.entries if e.decision_id == decision_id)
    assert stale_entry.status.value == "resolved"
    # Hand-corrupt the index entry back to `deferred` -- the log already
    # folds to `resolved` (open -> defer -> resolve), so this is a genuine
    # stale-status divergence the id-set comparison alone cannot see.
    from specify_cli.decisions.models import DecisionStatus

    staled = stale_entry.model_copy(update={"status": DecisionStatus.DEFERRED})
    new_index = index.model_copy(update={"entries": tuple(staled if e.decision_id == decision_id else e for e in index.entries)})
    _store.save_index(ledger_dir, new_index)
    before_diagnose = _store.index_path(ledger_dir).read_bytes()

    with pytest.raises(typer.Exit) as exc_info:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=False)
    assert exc_info.value.exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["clean"] is False, payload
    assert payload["malformed_folds"] == [], payload
    assert payload["status_mismatch"] == [{"decision_id": decision_id, "index_status": "deferred", "folded_status": "resolved"}], payload
    # Read-only diagnose must never mutate the index.
    assert _store.index_path(ledger_dir).read_bytes() == before_diagnose

    with pytest.raises(typer.Exit) as repair_exc_info:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=True)
    assert repair_exc_info.value.exit_code == 0, "a stale-status-only repair must reconcile cleanly and exit 0"

    healed = _store.load_index(ledger_dir)
    healed_entry = next(e for e in healed.entries if e.decision_id == decision_id)
    assert healed_entry.status.value == "resolved", "--repair must heal a stale index status"
    assert healed_entry.final_answer == "answer"


# ---------------------------------------------------------------------------
# Positive control: a healthy open -> resolve decision stays clean
# ---------------------------------------------------------------------------


def test_healthy_open_resolve_decision_stays_clean(tmp_path: Path) -> None:
    """Same fixture builder as the destructive tests above: a decision that
    never diverges is reported clean and untouched by diagnose or repair."""
    _setup_project(tmp_path)
    resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="healthy-step",
        input_key="healthy-input",
        question="Q?",
        actor="alice",
    )
    resolve_decision(
        tmp_path,
        MISSION_SLUG,
        resp.decision_id,
        final_answer="answer",
        actor="alice",
    )
    ledger_dir = _ledger_dir(tmp_path, MISSION_SLUG)
    index_path = _store.index_path(ledger_dir)
    before = index_path.read_bytes()

    with pytest.raises(typer.Exit) as exc_info:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=True)
    assert exc_info.value.exit_code == 0

    after = index_path.read_bytes()
    assert after == before, "a healthy corpus must be a no-op, even under --repair"


# ---------------------------------------------------------------------------
# ``--repair`` must never wipe a non-wire field of an entry it rebuilds. ``summary_json`` (widen-review provenance, C-005) is never placed
# on the wire, so the fold always yields ``summary_json=None``; a repair
# triggered by ONE stale status rebuilt EVERY entry from the log and silently
# erased every other decision's provenance, exit 0.
# ---------------------------------------------------------------------------


def _set_index_status(repo_root: Path, decision_id: str, status: DecisionStatus) -> None:
    """Hand-edit one index entry's status -- a stale index the log disagrees with."""
    ledger_dir = _ledger_dir(repo_root, MISSION_SLUG)
    index = _store.load_index(ledger_dir)
    entries = tuple(e.model_copy(update={"status": status}) if e.decision_id == decision_id else e for e in index.entries)
    _store.save_index(ledger_dir, index.model_copy(update={"entries": entries}))


def _entry(repo_root: Path, decision_id: str) -> IndexEntry:
    ledger_dir = _ledger_dir(repo_root, MISSION_SLUG)
    return next(e for e in _store.load_index(ledger_dir).entries if e.decision_id == decision_id)


def test_repair_of_one_stale_status_keeps_other_decisions_summary_json(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    provenance_resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="provenance-step",
        input_key="provenance-input",
        question="Provenance?",
        actor="alice",
    )
    resolve_decision(
        tmp_path,
        MISSION_SLUG,
        provenance_resp.decision_id,
        final_answer="widened",
        summary_json={"k": "provenance"},
        actor="alice",
    )
    stale_id = _open_defer_resolve(tmp_path, step_id="stale-step", final_answer="done")
    _set_index_status(tmp_path, stale_id, DecisionStatus.DEFERRED)
    provenance_before = _entry(tmp_path, provenance_resp.decision_id)
    assert provenance_before.summary_json == {"k": "provenance"}

    repair_result = _invoke_doctor(["decisions", "--mission", MISSION_SLUG, "--repair", "--json"], tmp_path)

    assert repair_result.exit_code == 0, repair_result.output
    payload = json.loads(repair_result.output)
    assert payload["repaired"] is True, payload
    assert payload["clean"] is True, payload
    assert _entry(tmp_path, stale_id).status is DecisionStatus.RESOLVED
    assert _entry(tmp_path, provenance_resp.decision_id) == provenance_before, "repair wiped a non-wire field"


def test_repaired_stale_entry_keeps_its_own_summary_json(tmp_path: Path) -> None:
    """The entry whose status IS rewritten takes wire fields from the fold
    but carries its own non-wire ``summary_json`` forward."""
    _setup_project(tmp_path)
    resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="self-step",
        input_key="self-input",
        question="Self?",
        actor="alice",
    )
    resolve_decision(tmp_path, MISSION_SLUG, resp.decision_id, final_answer="yes", summary_json={"k": "mine"}, actor="alice")
    _set_index_status(tmp_path, resp.decision_id, DecisionStatus.OPEN)

    with pytest.raises(typer.Exit) as exc_info:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=True)

    assert exc_info.value.exit_code == 0
    healed = _entry(tmp_path, resp.decision_id)
    assert healed.status is DecisionStatus.RESOLVED
    assert healed.summary_json == {"k": "mine"}


# ---------------------------------------------------------------------------
# A malformed PAYLOAD (not just a malformed event set) must
# be reported as a malformed fold, never crash the read-only doctor.
# ---------------------------------------------------------------------------


def _corrupt_payload(repo_root: Path, decision_id: str, event_type: str, mutate: Any) -> None:
    lines = _read_events(repo_root)
    for event in lines:
        if event.get("event_type") == event_type and event.get("payload", {}).get("decision_point_id") == decision_id:
            mutate(event["payload"])
    _events_path(repo_root).write_text("\n".join(json.dumps(e) for e in lines) + "\n", encoding="utf-8")


def _drop_origin_flow(payload: dict[str, Any]) -> None:
    del payload["origin_flow"]


def _bogus_outcome(payload: dict[str, Any]) -> None:
    payload["terminal_outcome"] = "bogus"


_PAYLOAD_CORRUPTIONS = [
    pytest.param("DecisionPointOpened", _drop_origin_flow, id="opened-missing-origin_flow"),
    pytest.param("DecisionPointResolved", _bogus_outcome, id="resolved-bogus-terminal_outcome"),
]


def _open_and_resolve(repo_root: Path, step_id: str) -> str:
    resp = open_decision(
        repo_root,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id=step_id,
        input_key=f"{step_id}-input",
        question=f"{step_id}?",
        actor="alice",
    )
    resolve_decision(repo_root, MISSION_SLUG, resp.decision_id, final_answer="a", actor="alice")
    return str(resp.decision_id)


@pytest.mark.parametrize(("event_type", "mutate"), _PAYLOAD_CORRUPTIONS)
def test_malformed_payload_is_reported_not_crashed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    event_type: str,
    mutate: Any,
) -> None:
    _setup_project(tmp_path)
    bad_id = _open_and_resolve(tmp_path, "bad-payload-step")
    good_id = _open_and_resolve(tmp_path, "good-payload-step")
    _corrupt_payload(tmp_path, bad_id, event_type, mutate)
    bad_entry_before = _entry(tmp_path, bad_id)

    with pytest.raises(typer.Exit) as diag_exc:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=False)
    assert diag_exc.value.exit_code == 0
    diag_payload = json.loads(capsys.readouterr().out)
    assert diag_payload["clean"] is False, diag_payload
    assert diag_payload["malformed_folds"] == [bad_id], diag_payload

    with pytest.raises(typer.Exit) as repair_exc:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=True)
    assert repair_exc.value.exit_code == 1
    out = capsys.readouterr().out
    assert bad_id in out
    assert "left in place" in out
    assert _entry(tmp_path, bad_id) == bad_entry_before, "the malformed decision's entry must be kept"
    assert _entry(tmp_path, good_id).status is DecisionStatus.RESOLVED


@pytest.mark.parametrize(("event_type", "mutate"), _PAYLOAD_CORRUPTIONS)
def test_fold_events_wraps_payload_errors_as_folderror(tmp_path: Path, event_type: str, mutate: Any) -> None:
    from specify_cli.decisions.index_fold import FoldError, fold_events

    _setup_project(tmp_path)
    decision_id = _open_and_resolve(tmp_path, "fold-unit-step")
    _corrupt_payload(tmp_path, decision_id, event_type, mutate)

    with pytest.raises(FoldError, match="malformed") as exc_info:
        fold_events(_events_for_decision(tmp_path, decision_id))
    assert isinstance(exc_info.value.__cause__, (KeyError, ValueError))


# ---------------------------------------------------------------------------
# A slot_key-origin decision's STATUS is on the wire, so a
# stale status must be reported and repaired even though its attribution
# (step_id/slot_key split) cannot be rebuilt from the log.
# ---------------------------------------------------------------------------


def test_slot_key_origin_stale_status_is_reported_and_repaired(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _setup_project(tmp_path)
    resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        slot_key="origin-slot",
        input_key="slot-input",
        question="Slot?",
        actor="alice",
    )
    defer_decision(tmp_path, MISSION_SLUG, resp.decision_id, rationale="later", actor="alice")
    resolve_decision(tmp_path, MISSION_SLUG, resp.decision_id, final_answer="slot answer", actor="alice")
    _set_index_status(tmp_path, resp.decision_id, DecisionStatus.DEFERRED)

    with pytest.raises(typer.Exit) as diag_exc:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=False)
    assert diag_exc.value.exit_code == 0
    diag_payload = json.loads(capsys.readouterr().out)
    assert diag_payload["status_mismatch"] == [{"decision_id": resp.decision_id, "index_status": "deferred", "folded_status": "resolved"}]

    with pytest.raises(typer.Exit) as repair_exc:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=True)
    assert repair_exc.value.exit_code == 0
    repair_payload = json.loads(capsys.readouterr().out)
    assert repair_payload["clean"] is True, repair_payload
    assert repair_payload["lossy_attribution"] == [resp.decision_id]

    healed = _entry(tmp_path, resp.decision_id)
    assert healed.status is DecisionStatus.RESOLVED
    assert healed.final_answer == "slot answer"
    assert healed.slot_key == "origin-slot", "attribution must be kept, not rebuilt from the collapsed wire field"
    assert healed.step_id is None


# ---------------------------------------------------------------------------
# The human-text ``stale status`` line.
# ---------------------------------------------------------------------------


def test_diagnose_human_output_names_stale_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _setup_project(tmp_path)
    decision_id = _open_defer_resolve(tmp_path, step_id="human-stale-step")
    _set_index_status(tmp_path, decision_id, DecisionStatus.DEFERRED)

    with pytest.raises(typer.Exit) as exc_info:
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=False)

    assert exc_info.value.exit_code == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "stale status" in out
    assert f"{decision_id} (index=deferred, log=resolved)" in out


# ---------------------------------------------------------------------------
# ``_reconcile_entry`` branch-level unit tests.
# ---------------------------------------------------------------------------


def _index_entry(**overrides: Any) -> IndexEntry:
    from kernel.clock import parse_iso

    fields: dict[str, Any] = {
        "decision_id": "01KRECONCILE0000000000000A",
        "origin_flow": OriginFlow.CHARTER,
        "step_id": "step-a",
        "input_key": "in",
        "question": "Q?",
        "status": DecisionStatus.RESOLVED,
        "final_answer": "yes",
        "created_at": parse_iso("2026-09-01T00:00:00+00:00"),
        "resolved_at": parse_iso("2026-09-02T00:00:00+00:00"),
        "resolved_by": "alice",
        "opened_by": "alice",
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
    }
    fields.update(overrides)
    return IndexEntry(**fields)


def test_reconcile_entry_without_existing_takes_the_fold() -> None:
    from specify_cli.cli.commands._decisions_doctor import _reconcile_entry

    folded = _index_entry()
    assert _reconcile_entry(None, folded) is folded


def test_reconcile_entry_keeps_wire_agreeing_entry_verbatim() -> None:
    """Emission-normalised fields (``resolved_by``/``rationale``) and
    non-wire fields never count as disagreement."""
    from specify_cli.cli.commands._decisions_doctor import _reconcile_entry

    existing = _index_entry(resolved_by=None, rationale=None, summary_json={"k": "v"}, slot_key="also")
    folded = _index_entry(resolved_by="alice", rationale="no rationale")
    assert _reconcile_entry(existing, folded) is existing


def test_reconcile_entry_carries_slot_key_beside_agreeing_step_id() -> None:
    from specify_cli.cli.commands._decisions_doctor import _reconcile_entry

    existing = _index_entry(status=DecisionStatus.DEFERRED, final_answer=None, slot_key="side-slot", summary_json={"k": "v"})
    folded = _index_entry()
    merged = _reconcile_entry(existing, folded)
    assert merged.status is DecisionStatus.RESOLVED
    assert merged.slot_key == "side-slot"
    assert merged.summary_json == {"k": "v"}


def test_reconcile_entry_takes_fold_step_id_when_it_disagrees() -> None:
    from specify_cli.cli.commands._decisions_doctor import _reconcile_entry

    existing = _index_entry(step_id="hand-edited", slot_key="stale-slot")
    folded = _index_entry(step_id="step-a")
    merged = _reconcile_entry(existing, folded)
    assert merged.step_id == "step-a"
    assert merged.slot_key is None


def test_reconcile_entry_keeps_slot_key_origin_attribution() -> None:
    from specify_cli.cli.commands._decisions_doctor import _reconcile_entry

    existing = _index_entry(step_id=None, slot_key="origin-slot", status=DecisionStatus.DEFERRED, final_answer=None)
    folded = _index_entry(step_id="origin-slot")
    merged = _reconcile_entry(existing, folded)
    assert (merged.step_id, merged.slot_key) == (None, "origin-slot")
    assert merged.status is DecisionStatus.RESOLVED
