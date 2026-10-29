# Research: Decision log integrity

Phase 0 grounding, re-verified on `origin/main` 581b5c46 (2026-10-27).

## R-1 Code grounding (#4848 open half)

- `src/specify_cli/decisions/service.py:557` `_locate_or_create_open_entry` takes
  `decisions/index.json.lock`, does the dedup lookup and the index append, and releases.
- `service.py:736-737` (fresh path): `_store.write_artifact` and `_emit.emit_decision_opened`
  run after the release.
- `service.py:711` (idempotent path): `_repair_missing_opened_event` (`:445`) checks
  `_opened_event_exists` (`:419`) and emits (`:462`) without the decisions lock.
- `src/specify_cli/decisions/emit.py` `_append_raw_event` takes the Mission status lock around
  the append only, so the check-then-append is not serialized.
- `src/specify_cli/decisions/index_fold.py:331` raises `FoldError("more than one
  DecisionPointOpened event ...")`; `cli/commands/_decisions_doctor.py:336` records the decision
  as a malformed fold, and `--repair` exits 1 leaving it in place.

Red-first evidence (scratch test pausing the real `emit_decision_opened`, pattern of
`tests/specify_cli/decisions/test_service_terminal_concurrency.py`):

```
FAILED test_one_opened_row[fresh]        assert 2 == 1
FAILED test_one_opened_row[interrupted]  assert 2 == 1
```

This matches Ivan-Melck's 2026-10-16 reproduction on #4848 (ARM A and ARM B, 2 rows each).

- Decision: hold the decisions lock across the whole open (fresh and retry paths).
- Rationale: identical to #6294's fix for the terminal verbs; closes both arms.
- Alternatives considered: dedupe at append time inside the status lock (a second check
  authority inside emit; rejected: the index/log divergence window of the original #4848 body
  stays open).

## R-2 Lock order and the #6193 lock story

- Every holder of `index.json.lock` (`service.py` open/terminal, `_decisions_doctor.py` repair and
  ledger copy, `next_cmd._commit_owned_next_mutations`, `decision.py` runtime-lock repair) takes
  it first or alone; the status lock is only ever taken inside it (emit). No reverse order found.
- `src/kernel/event_log_append.py` (#6606) explicitly excludes `status.events.jsonl`, which keeps
  the Mission status lock and the `status.store` primitives. PR #6716 (#6193 spike) is test code
  and a report only; it does not change `machine_file_lock` or the status lock. Our change is
  lock-scope only on an existing lock, so it aligns with both and survives the Java handover
  (ADR 2026-10-22-1: Python keeps only the EventBridge port; nothing here is redone).

## R-3 Existing duplicated ledgers (operator ruling 1: reader tolerance)

- Both racing writers build the opening from the same saved index entry, so the two payloads
  are equal except `recorded_at` (the envelope `event_id` and `at` differ too).
- `_fold_opened` does not read `recorded_at`, so any identical row folds to the same entry;
  "earliest" is chosen by `(recorded_at, event_id)` for determinism.
- spec-kitty-events 11.0.0 `reduce_decision_point_events` also treats a second open as a
  non-fatal `invalid_transition` anomaly, so reader tolerance matches the package's semantics.
- Decision: tolerate equal-but-for-`recorded_at` duplicates; keep refusing any other difference.
- Alternatives considered: `doctor --repair` rewrite of the log (rejected by the operator: a new
  out-of-store write site, conflicts with the canonical-writer direction).

## R-4 #6412 reader half (operator ruling 2: reopen table only)

- `reduce_decision_point_records` validates each DecisionPoint record as a full `Event`
  envelope (`aggregate_id`, `timestamp`, `build_id`, `node_id`, `project_uuid`,
  `correlation_id` required). The CLI's rows are 4-key `{event_id, at, event_type, payload}`;
  probing one raises `LedgerValidationError`. The reduced state also drops `created_at` and
  `opened_by`. Adoption therefore needs the envelope half (spec-kitty-events #92, #6194).
- `DECISION_POINT_TERMINAL_REOPEN` (package) = `{(DEFERRED, RESOLVED)}` over `TerminalOutcome`,
  the same rule as the local table over `DecisionStatus`.
- Decision: derive `is_allowed_terminal_reopen` from the package table via `_OUTCOME_TO_STATUS`;
  delete `ALLOWED_TERMINAL_REOPEN`. Callers (`service._is_allowed_terminal_reopen`,
  `consolidation/drivers.py`) are unchanged.

## R-5 Writes gates (#6608)

- `tests/architectural/test_event_log_writes_gate.py` ledgers `kernel.event_log_append` callers;
  `test_status_events_writes_gate.py` pins `specify_cli.decisions.emit` as family 8 and its one
  `feature_status_lock` composition. This mission adds no write site and no lock composition,
  so neither ledger changes. Adding the duplicate-open case to an AST write-site gate is not
  natural (it is a runtime interleaving, not a write shape); it lands as a behavioural
  regression test beside the #5681 ones instead.

## R-6 Related surfaces / in-flight work

- No open PR touches `src/specify_cli/decisions/` (searched 2026-10-27). PR #6717 (#6706,
  glossary ledger lock) is unrelated.
- #6411 (events 11.0 umbrella), #6447/#6449 (parked for #92): untouched.
- Avoided: #6715, #6675, #6193/PR #6716, events #92, sibling missions M1–M3, M5, M6.
