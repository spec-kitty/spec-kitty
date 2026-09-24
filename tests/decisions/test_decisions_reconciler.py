"""T008/T009/T012 — the canonical event->IndexEntry fold and the
``doctor decisions`` reconciler (mission local-write-safety-01M2ZPZD WP03,
FR-004/FR-005, ``contracts/decisions-doctor.md``).

T009 is the RED-FIRST invariant proof: before the fix, ``service.py`` built
each ``IndexEntry`` by hand and ``index_fold.py`` did not exist at all, so
there was no inverse mapping to prove I9 (index reconstructible from the
log) against. ``test_opened_and_resolved_round_trip_every_field`` asserts
the FULL reconstructed object equals the original -- driven off
``IndexEntry.model_fields`` (the canonical field set), not a hand-picked
subset, so a future field addition/rename that breaks the fold is caught
here rather than silently passing.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.decisions import index_fold
from specify_cli.decisions import store as _store
from specify_cli.decisions.index_fold import FoldError, fold_events
from specify_cli.decisions.models import DecisionStatus, IndexEntry, OriginFlow
from specify_cli.decisions.service import open_decision, resolve_decision

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID = "01KTEST_RECONCILER_MISSION_0"
MISSION_SLUG = "reconciler-mission"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mission_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / MISSION_SLUG


def _setup_meta(repo_root: Path) -> None:
    mission_dir = _mission_dir(repo_root)
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _events_for_decision(repo_root: Path, decision_id: str) -> list[dict]:  # type: ignore[type-arg]
    events_path = _mission_dir(repo_root) / "status.events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [e for e in events if e.get("payload", {}).get("decision_point_id") == decision_id]


# ---------------------------------------------------------------------------
# T009 — red-first I9 round-trip proof
# ---------------------------------------------------------------------------


def test_opened_and_resolved_round_trip_every_field(tmp_path: Path) -> None:
    """A fully resolved decision's IndexEntry is byte-for-byte recoverable
    from its DecisionPointOpened + DecisionPointResolved events.

    Drives the comparison off ``IndexEntry.model_fields`` (the canonical
    field set) so a future field this fold forgets to map is caught, not
    silently dropped by a hand-picked assertion subset.
    """
    _setup_meta(tmp_path)
    resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="step-1",
        input_key="team_size",
        question="How large is the team?",
        options=("1-5", "6-20", "20+"),
        actor="alice",
    )
    resolve_decision(
        tmp_path,
        MISSION_SLUG,
        resp.decision_id,
        final_answer="6-20",
        other_answer=False,
        rationale="measured headcount",
        resolved_by="bob",
        actor="bob",
    )

    original = next(e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == resp.decision_id)
    assert original.status == DecisionStatus.RESOLVED  # sanity: exercising the terminal path

    events = _events_for_decision(tmp_path, resp.decision_id)
    reconstructed = fold_events(events)

    # Known, documented wire-schema gap (index_fold.py module docstring):
    # summary_json never reaches the wire in V1. Not exercised by THIS
    # fixture (no summary_json was ever set), so it round-trips trivially --
    # both sides are None -- and every OTHER field is compared for real.
    mismatches = [field for field in IndexEntry.model_fields if getattr(original, field) != getattr(reconstructed, field)]
    assert mismatches == [], f"fields that failed to round-trip: {mismatches}"
    assert reconstructed == original


def test_opened_only_round_trips_every_field(tmp_path: Path) -> None:
    """An OPEN (never resolved) decision also round-trips fully."""
    _setup_meta(tmp_path)
    resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.SPECIFY,
        step_id="step-open-only",
        input_key="scope",
        question="What is in scope?",
        options=(),
        actor="carol",
    )

    original = next(e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == resp.decision_id)
    events = _events_for_decision(tmp_path, resp.decision_id)
    reconstructed = fold_events(events)

    mismatches = [field for field in IndexEntry.model_fields if getattr(original, field) != getattr(reconstructed, field)]
    assert mismatches == [], f"fields that failed to round-trip: {mismatches}"
    assert reconstructed == original


# ---------------------------------------------------------------------------
# T008 — fold_events error handling / single canonical fold
# ---------------------------------------------------------------------------


def test_fold_events_requires_an_opened_event() -> None:
    with pytest.raises(FoldError, match="no DecisionPointOpened"):
        fold_events([])


def test_fold_events_rejects_duplicate_opened_events(tmp_path: Path) -> None:
    _setup_meta(tmp_path)
    resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="dup-step",
        input_key="dup",
        question="Q?",
        actor="alice",
    )
    events = _events_for_decision(tmp_path, resp.decision_id)
    with pytest.raises(FoldError, match="more than one DecisionPointOpened"):
        fold_events(events + events)


def test_fold_events_rejects_unknown_event_type(tmp_path: Path) -> None:
    _setup_meta(tmp_path)
    resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="unknown-step",
        input_key="unk",
        question="Q?",
        actor="alice",
    )
    events = _events_for_decision(tmp_path, resp.decision_id)
    bogus = dict(events[0])
    bogus["event_type"] = "SomeOtherEvent"
    with pytest.raises(FoldError, match="unknown event type"):
        fold_events([*events, bogus])


def test_service_forward_path_shares_build_opened_entry(tmp_path: Path) -> None:
    """T008: the forward path constructs its OPEN entry via the SAME
    ``index_fold.build_opened_entry`` assembler the fold uses -- not a
    second, independently-hand-rolled ``IndexEntry(...)`` call."""
    _setup_meta(tmp_path)
    with patch(
        "specify_cli.decisions.index_fold.build_opened_entry",
        wraps=index_fold.build_opened_entry,
    ) as spy:
        open_decision(
            tmp_path,
            MISSION_SLUG,
            origin_flow=OriginFlow.CHARTER,
            step_id="shared-ctor-step",
            input_key="shared",
            question="Q?",
            actor="alice",
        )
    spy.assert_called_once()


# ---------------------------------------------------------------------------
# T012 — ``doctor decisions`` reconciler
# ---------------------------------------------------------------------------


def _seed_diverged_corpus(tmp_path: Path) -> list[str]:
    """Open 8 decisions (8 log entries), then hand-corrupt index.json down
    to 5 entries -- the seeded log=8/index=5 corpus the DoD names."""
    _setup_meta(tmp_path)
    decision_ids = []
    for i in range(8):
        resp = open_decision(
            tmp_path,
            MISSION_SLUG,
            origin_flow=OriginFlow.CHARTER,
            step_id=f"seed-step-{i}",
            input_key=f"seed-key-{i}",
            question=f"Q{i}?",
            actor="alice",
        )
        decision_ids.append(resp.decision_id)

    mission_dir = _mission_dir(tmp_path)
    index = _store.load_index(mission_dir)
    assert len(index.entries) == 8
    truncated = index.model_copy(update={"entries": index.entries[:5]})
    _store.save_index(mission_dir, truncated)
    return decision_ids


def test_diagnose_reports_missing_from_index(tmp_path: Path) -> None:
    # #4966 AC-D2: events (COORD) and ledger (PRIMARY) resolve separately;
    # they coincide under this flat (coord-less) fixture topology.
    from specify_cli.cli.commands._decisions_doctor import _diagnose, _ledger_dir, _mission_dir

    decision_ids = _seed_diverged_corpus(tmp_path)
    events_dir = _mission_dir(tmp_path, MISSION_SLUG)
    ledger_dir = _ledger_dir(tmp_path, MISSION_SLUG)
    report, _grouped = _diagnose(events_dir, ledger_dir, MISSION_SLUG)

    assert not report.clean
    assert len(report.log_decision_ids) == 8
    assert len(report.index_decision_ids) == 5
    assert set(report.missing_from_index) == set(decision_ids) - set(report.index_decision_ids)
    assert report.orphaned_in_index == []


def test_repair_heals_log_8_index_5_corpus(tmp_path: Path) -> None:
    import typer

    from specify_cli.cli.commands._decisions_doctor import run_decisions_reconciliation

    decision_ids = _seed_diverged_corpus(tmp_path)
    mission_dir = _mission_dir(tmp_path)
    assert len(_store.load_index(mission_dir).entries) == 5

    with pytest.raises(typer.Exit):
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=True)

    healed = _store.load_index(mission_dir)
    assert {e.decision_id for e in healed.entries} == set(decision_ids)
    assert len(healed.entries) == 8


def test_repair_is_no_op_on_agreeing_corpus(tmp_path: Path) -> None:
    import typer

    from specify_cli.cli.commands._decisions_doctor import run_decisions_reconciliation

    _setup_meta(tmp_path)
    open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="agree-step",
        input_key="agree",
        question="Q?",
        actor="alice",
    )
    mission_dir = _mission_dir(tmp_path)
    index_path = _store.index_path(mission_dir)
    before = index_path.read_bytes()
    before_mtime = index_path.stat().st_mtime_ns

    with pytest.raises(typer.Exit):
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=True)

    after = index_path.read_bytes()
    after_mtime = index_path.stat().st_mtime_ns
    assert after == before
    assert after_mtime == before_mtime, "no-op repair must not rewrite index.json when already agreeing"


def test_diagnose_without_repair_leaves_index_unchanged(tmp_path: Path) -> None:
    import typer

    from specify_cli.cli.commands._decisions_doctor import run_decisions_reconciliation

    _seed_diverged_corpus(tmp_path)
    mission_dir = _mission_dir(tmp_path)
    assert len(_store.load_index(mission_dir).entries) == 5

    with pytest.raises(typer.Exit):
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=True, repair=False)

    assert len(_store.load_index(mission_dir).entries) == 5


# ---------------------------------------------------------------------------
# review-feedback-2 (cycle 2) — Fold A: lossy slot_key attribution must not
# be silently rewritten by --repair
# ---------------------------------------------------------------------------


def test_repair_refuses_to_mis_attribute_slot_key_origin_decision(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fold A: the wire event only ever carries a single collapsed
    ``step_id`` field (``decisions/emit.py:213``, upstream
    ``spec_kitty_events.decisionpoint`` schema gap) -- folding a
    slot_key-origin decision from the log alone would silently reconstruct
    it as ``step_id=<slot_key value>, slot_key=None``. ``--repair`` must
    detect this from the PRE-repair on-disk entry, keep its attribution
    unchanged instead of fabricating it, and warn loudly -- while still
    healing membership for every OTHER diverged decision in the same run."""
    import typer

    from specify_cli.cli.commands._decisions_doctor import run_decisions_reconciliation

    _setup_meta(tmp_path)
    slot_resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        slot_key="slot-origin-key",
        input_key="slot-origin-input",
        question="Slot-origin Q?",
        actor="alice",
    )
    all_ids = [slot_resp.decision_id]
    for i in range(7):
        resp = open_decision(
            tmp_path,
            MISSION_SLUG,
            origin_flow=OriginFlow.CHARTER,
            step_id=f"other-step-{i}",
            input_key=f"other-key-{i}",
            question=f"Q{i}?",
            actor="alice",
        )
        all_ids.append(resp.decision_id)

    mission_dir = _mission_dir(tmp_path)
    original_slot_entry = next(e for e in _store.load_index(mission_dir).entries if e.decision_id == slot_resp.decision_id)
    assert original_slot_entry.slot_key == "slot-origin-key"
    assert original_slot_entry.step_id is None

    # Diverge the corpus WITHOUT touching the slot_key entry: drop two of
    # the step_id-origin entries so --repair still fires, and the
    # slot_key-origin entry's PRE-repair on-disk copy is still there for
    # `--repair` to detect.
    index = _store.load_index(mission_dir)
    dropped = {all_ids[1], all_ids[2]}
    truncated_entries = tuple(e for e in index.entries if e.decision_id not in dropped)
    _store.save_index(mission_dir, index.model_copy(update={"entries": truncated_entries}))
    assert len(_store.load_index(mission_dir).entries) == 6

    with pytest.raises(typer.Exit):
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=True)

    healed = _store.load_index(mission_dir)
    # Membership healed: all 8 decisions present again.
    assert {e.decision_id for e in healed.entries} == set(all_ids)

    # But the slot_key-origin entry's attribution was NOT silently rewritten.
    healed_slot_entry = next(e for e in healed.entries if e.decision_id == slot_resp.decision_id)
    assert healed_slot_entry == original_slot_entry, "repair silently mis-attributed a slot_key-origin decision"
    assert healed_slot_entry.slot_key == "slot-origin-key"
    assert healed_slot_entry.step_id is None

    # And the previously-dropped step_id-origin entries WERE rebuilt from
    # the log as usual (Fold A only refuses the unrecoverable case).
    for dropped_id in dropped:
        assert any(e.decision_id == dropped_id for e in healed.entries)

    captured = capsys.readouterr()
    assert slot_resp.decision_id in captured.out
    assert "refused to rewrite" in captured.out.lower()


def test_repair_still_heals_agreeing_slot_key_entry_untouched(tmp_path: Path) -> None:
    """A slot_key-origin decision that never diverges is not touched by
    `--repair` at all (the run is a clean no-op, matching the
    already-agreeing-corpus contract)."""
    import typer

    from specify_cli.cli.commands._decisions_doctor import run_decisions_reconciliation

    _setup_meta(tmp_path)
    slot_resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        slot_key="agree-slot-key",
        input_key="agree-slot-input",
        question="Q?",
        actor="alice",
    )
    mission_dir = _mission_dir(tmp_path)
    before = next(e for e in _store.load_index(mission_dir).entries if e.decision_id == slot_resp.decision_id)

    with pytest.raises(typer.Exit):
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=True)

    after = next(e for e in _store.load_index(mission_dir).entries if e.decision_id == slot_resp.decision_id)
    assert after == before


# ---------------------------------------------------------------------------
# review-feedback-2 (cycle 2) — Fold B: --repair must read the event log
# INSIDE the sidecar lock, not from _diagnose's pre-lock snapshot
# ---------------------------------------------------------------------------


def test_repair_reads_log_fresh_inside_lock_not_stale_diagnose_snapshot(
    tmp_path: Path,
) -> None:
    """Fold B: `_repair` must not rebuild from `_diagnose`'s pre-lock
    snapshot. Simulate a writer landing in the exact window between the
    pre-lock diagnose read and the lock acquisition -- via a side effect on
    `_diagnose` itself, which is the only way to deterministically land a
    write in that window without a real, flaky thread race -- and assert
    the concurrently-opened decision survives `--repair` rather than being
    silently dropped by a rebuild sourced from the stale pre-lock grouped
    events."""
    import typer

    from specify_cli.cli.commands import _decisions_doctor as _doctor_mod
    from specify_cli.cli.commands._decisions_doctor import run_decisions_reconciliation

    decision_ids = _seed_diverged_corpus(tmp_path)
    mission_dir = _mission_dir(tmp_path)

    real_diagnose = _doctor_mod._diagnose
    concurrent_ids: list[str] = []

    def _diagnose_then_concurrent_write(events_dir_arg: Path, ledger_dir_arg: Path, mission_slug_arg: str):  # type: ignore[no-untyped-def]
        report, grouped = real_diagnose(events_dir_arg, ledger_dir_arg, mission_slug_arg)
        # A writer landing AFTER this pre-lock read but BEFORE `_repair`
        # acquires the sidecar lock -- the exact window Fold B closes.
        resp = open_decision(
            tmp_path,
            MISSION_SLUG,
            origin_flow=OriginFlow.CHARTER,
            step_id="concurrent-after-diagnose",
            input_key="concurrent-after-diagnose",
            question="Q?",
            actor="racer",
        )
        concurrent_ids.append(resp.decision_id)
        return report, grouped

    with (
        patch.object(_doctor_mod, "_diagnose", side_effect=_diagnose_then_concurrent_write),
        pytest.raises(typer.Exit),
    ):
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=True)

    assert concurrent_ids, "test setup: the simulated concurrent write did not run"
    healed = _store.load_index(mission_dir)
    healed_ids = {e.decision_id for e in healed.entries}
    assert set(decision_ids) <= healed_ids
    assert set(concurrent_ids) <= healed_ids, (
        "repair rebuilt from the stale pre-lock diagnose snapshot and dropped a decision opened in the window between the diagnose read and the lock acquisition"
    )


def test_repair_reads_index_fresh_inside_lock(tmp_path: Path) -> None:
    """Fold B companion: `_repair` (the low-level function) reads the
    current index itself rather than accepting a pre-lock caller-supplied
    index -- covered directly at the unit level (no CLI wrapper indirection)
    by asserting its signature takes no pre-lock arguments."""
    from specify_cli.cli.commands._decisions_doctor import _repair

    decision_ids = _seed_diverged_corpus(tmp_path)
    mission_dir = _mission_dir(tmp_path)

    # #4966 AC-D2: events (COORD) and ledger (PRIMARY) coincide under this
    # flat (coord-less) fixture topology.
    lossy_ids, malformed_ids = _repair(mission_dir, mission_dir)

    assert lossy_ids == []
    assert malformed_ids == []
    healed = _store.load_index(mission_dir)
    assert {e.decision_id for e in healed.entries} == set(decision_ids)


# ---------------------------------------------------------------------------
# Fold C (#470 dead-symbol gate + robustness) — a malformed event-log group
# must not crash the whole reconciler run
# ---------------------------------------------------------------------------


def test_repair_reports_malformed_fold_instead_of_crashing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A decision_id whose grouped events violate ``fold_events``'s
    invariants (here: a duplicated ``DecisionPointOpened`` envelope for one
    decision_id, mirroring ``test_fold_events_rejects_duplicate_opened_events``
    -- the ``_read_decision_events`` grouper only filters by event *type*,
    not by cardinality, so a duplicate-OPENED corruption reaches
    ``fold_events`` intact and raises there) must not raise an uncaught
    ``FoldError`` out of ``--repair`` and crash the whole run.
    ``_rebuild_index_from_log`` catches it, keeps the decision's pre-repair
    on-disk entry unchanged, reports the decision_id via
    ``malformed_folds``, and still heals every OTHER diverged decision in
    the same run."""
    import typer

    from specify_cli.cli.commands._decisions_doctor import run_decisions_reconciliation

    _setup_meta(tmp_path)
    bad_resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="malformed-step",
        input_key="malformed-key",
        question="Q?",
        actor="alice",
    )
    other_ids = [bad_resp.decision_id]
    for i in range(3):
        resp = open_decision(
            tmp_path,
            MISSION_SLUG,
            origin_flow=OriginFlow.CHARTER,
            step_id=f"clean-step-{i}",
            input_key=f"clean-key-{i}",
            question=f"Q{i}?",
            actor="alice",
        )
        other_ids.append(resp.decision_id)

    mission_dir = _mission_dir(tmp_path)
    events_path = mission_dir / "status.events.jsonl"
    lines = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    duplicated_opened = [
        event for event in lines if event.get("payload", {}).get("decision_point_id") == bad_resp.decision_id and event.get("event_type") == "DecisionPointOpened"
    ]
    assert len(duplicated_opened) == 1, "test setup: expected exactly one DecisionPointOpened event to duplicate"
    lines.append(dict(duplicated_opened[0]))
    events_path.write_text("\n".join(json.dumps(e) for e in lines) + "\n", encoding="utf-8")

    original_bad_entry = next(e for e in _store.load_index(mission_dir).entries if e.decision_id == bad_resp.decision_id)

    # Diverge the index (drop one clean decision) so `--repair` fires.
    index = _store.load_index(mission_dir)
    dropped_id = other_ids[1]
    truncated_entries = tuple(e for e in index.entries if e.decision_id != dropped_id)
    _store.save_index(mission_dir, index.model_copy(update={"entries": truncated_entries}))

    with pytest.raises(typer.Exit):
        run_decisions_reconciliation(tmp_path, MISSION_SLUG, json_output=False, repair=True)

    healed = _store.load_index(mission_dir)
    healed_ids = {e.decision_id for e in healed.entries}
    # The dropped clean decision was healed as usual.
    assert dropped_id in healed_ids
    # The malformed decision's PRE-repair entry survived, unchanged.
    healed_bad_entry = next(e for e in healed.entries if e.decision_id == bad_resp.decision_id)
    assert healed_bad_entry == original_bad_entry

    captured = capsys.readouterr()
    assert bad_resp.decision_id in captured.out
    assert "could not fold" in captured.out.lower()


def test_rebuild_index_from_log_omits_malformed_decision_with_no_prior_entry(tmp_path: Path) -> None:
    """When a malformed decision_id has NO pre-repair on-disk entry to fall
    back to, ``_rebuild_index_from_log`` omits it from the rebuilt index
    (rather than fabricating one) and still reports it as malformed."""
    from specify_cli.cli.commands._decisions_doctor import _rebuild_index_from_log
    from specify_cli.decisions.models import DecisionIndex

    _setup_meta(tmp_path)
    resp = open_decision(
        tmp_path,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="no-prior-step",
        input_key="no-prior-key",
        question="Q?",
        actor="alice",
    )
    events = _events_for_decision(tmp_path, resp.decision_id)
    bogus = dict(events[0])
    bogus["event_type"] = "SomeOtherEvent"
    grouped = {resp.decision_id: [bogus]}

    empty_current = DecisionIndex(mission_id=MISSION_ID, entries=())
    rebuilt, lossy_ids, malformed_ids = _rebuild_index_from_log(empty_current, grouped)

    assert lossy_ids == []
    assert malformed_ids == [resp.decision_id]
    assert rebuilt.entries == ()


# ---------------------------------------------------------------------------
# #4966 AC-D2 (WP03 scope expansion) — service.py and _decisions_doctor.py
# must resolve the decision ledger (and its sidecar lock) to the SAME
# PRIMARY-partition dir, or a concurrent open/resolve could race a --repair
# against a different index.json than the one it locks against.
# ---------------------------------------------------------------------------


def test_service_and_doctor_resolve_ledger_dir_in_lockstep(tmp_path: Path) -> None:
    """``decisions/service.py::_ledger_dir`` and
    ``cli/commands/_decisions_doctor.py::_ledger_dir`` must resolve to the
    IDENTICAL directory (and therefore the identical sidecar
    ``index.json.lock`` path) for the same ``(repo_root, mission_slug)`` --
    otherwise a concurrent ``open``/``resolve`` (service.py) and a
    ``doctor decisions --repair`` (the doctor) would serialize against two
    DIFFERENT locks and could race each other's writes to two different
    ``index.json`` files."""
    from specify_cli.cli.commands import _decisions_doctor as _doctor_mod
    from specify_cli.decisions import service as _service_mod

    _setup_meta(tmp_path)

    service_ledger_dir = _service_mod._ledger_dir(tmp_path, MISSION_SLUG)
    doctor_ledger_dir = _doctor_mod._ledger_dir(tmp_path, MISSION_SLUG)
    assert service_ledger_dir == doctor_ledger_dir, "service.py and _decisions_doctor.py disagree on the ledger dir -- lockstep invariant broken"

    service_lock_path = _service_mod._decisions_lock_path(service_ledger_dir)
    doctor_lock_path = _doctor_mod._decisions_lock_path(doctor_ledger_dir)
    assert service_lock_path == doctor_lock_path, "service.py and _decisions_doctor.py disagree on the sidecar index.json.lock path"

    # And the ledger dir is genuinely PRIMARY-partition-resolved -- NOT the
    # COORD-partition dir events (`status.events.jsonl`) live in when the two
    # diverge under a coord topology. Under this flat fixture they coincide
    # (AC-D3), so this also pins that coincidence for the flat case.
    events_dir = _service_mod._mission_dir(tmp_path, MISSION_SLUG)
    assert service_ledger_dir == events_dir, "flat-topology sanity: PRIMARY and COORD dirs must coincide here (AC-D3)"


def test_service_and_doctor_resolve_ledger_dir_in_lockstep_under_coord_topology(
    tmp_path: Path,
) -> None:
    """COORD-topology variant of the lockstep pin above (pre-PR squad
    hardening fold): the flat fixture above resolves PRIMARY_METADATA and
    STATUS_STATE to the SAME directory (AC-D3), so it cannot distinguish a
    correct ``_ledger_dir`` (PRIMARY_METADATA) from a REGRESSED one that
    reverts to routing through STATUS_STATE (the COORD partition) -- both
    copies would still "agree" with each other while silently agreeing on the
    WRONG dir.

    Mocks ``placement_seam`` to hand back genuinely DIFFERENT directories for
    the two kinds (the coord-topology shape, ``PRIMARY_METADATA`` != COORD
    ``STATUS_STATE``) and asserts BOTH ``decisions/service.py::_ledger_dir``
    and ``cli/commands/_decisions_doctor.py::_ledger_dir`` land on the
    PRIMARY dir, identically to each other (and their sidecar
    ``index.json.lock`` paths), AND that this differs from the COORD events
    dir (``_mission_dir`` / ``status.events.jsonl``'s home) -- a drift back to
    ``STATUS_STATE`` in either module fails this test.
    """
    from unittest.mock import patch

    from mission_runtime import MissionArtifactKind

    from specify_cli.cli.commands import _decisions_doctor as _doctor_mod
    from specify_cli.decisions import service as _service_mod

    primary_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    coord_dir = tmp_path / ".worktrees" / f"{MISSION_SLUG}-01KTEST0-coord" / "kitty-specs" / MISSION_SLUG
    primary_dir.mkdir(parents=True)
    coord_dir.mkdir(parents=True)
    assert primary_dir != coord_dir, "fixture invariant: the two surfaces must be genuinely distinct dirs"

    def _fake_read_dir(kind: MissionArtifactKind) -> Path:
        if kind is MissionArtifactKind.PRIMARY_METADATA:
            return primary_dir
        if kind is MissionArtifactKind.STATUS_STATE:
            return coord_dir
        raise AssertionError(f"unexpected MissionArtifactKind requested in this test: {kind}")

    class _FakeSeam:
        def read_dir(self, kind: MissionArtifactKind) -> Path:
            return _fake_read_dir(kind)

    with (
        patch.object(_service_mod, "placement_seam", return_value=_FakeSeam()) as service_seam_ctor,
        patch.object(_doctor_mod, "placement_seam", return_value=_FakeSeam()) as doctor_seam_ctor,
    ):
        service_ledger_dir = _service_mod._ledger_dir(tmp_path, MISSION_SLUG)
        doctor_ledger_dir = _doctor_mod._ledger_dir(tmp_path, MISSION_SLUG)
        events_dir = _service_mod._mission_dir(tmp_path, MISSION_SLUG)

    service_seam_ctor.assert_called_with(tmp_path, MISSION_SLUG)
    doctor_seam_ctor.assert_called_with(tmp_path, MISSION_SLUG)

    assert service_ledger_dir == primary_dir, "service.py::_ledger_dir must resolve PRIMARY_METADATA under coord topology, not drift to STATUS_STATE"
    assert doctor_ledger_dir == primary_dir, "_decisions_doctor.py::_ledger_dir must resolve PRIMARY_METADATA under coord topology, not drift to STATUS_STATE"
    assert service_ledger_dir == doctor_ledger_dir, "service.py and _decisions_doctor.py disagree on the ledger dir under coord topology"

    service_lock_path = _service_mod._decisions_lock_path(service_ledger_dir)
    doctor_lock_path = _doctor_mod._decisions_lock_path(doctor_ledger_dir)
    assert service_lock_path == doctor_lock_path, "service.py and _decisions_doctor.py disagree on the sidecar lock path under coord topology"

    assert events_dir == coord_dir, "fixture sanity: the events dir must resolve the mocked COORD surface"
    assert service_ledger_dir != events_dir, "PRIMARY ledger dir must differ from the COORD events dir -- a drift to STATUS_STATE would collapse this undetected"
