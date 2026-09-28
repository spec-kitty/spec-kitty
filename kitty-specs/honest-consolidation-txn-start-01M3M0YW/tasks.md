# Work Packages: Honest consolidation transaction start + nightly integration green

Spec: [spec.md](spec.md) · Plan: [plan.md](plan.md)

## Subtask Format: `[Txxx] [P?] Description`

## Work Package WP01: #5111 transaction-start ordering (Priority: P1) 🎯 MVP

**Goal**: A fresh `state.json` never exists on disk without its reconciliation marker, and `clear_state` clears both (FR-001–FR-003).

### Included Subtasks
- [ ] T001 Red-first CLI repro `tests/consolidation/test_issue_5111_fresh_gate_failure_rerun.py`: a gate fails, then a plain re-run; `--abort`; `clear_state` unit pins
- [ ] T002 Move marker filename ownership into `consolidation/state.py`; `clear_state` unlinks the marker (both the keyed and the legacy branch)
- [ ] T003 The fresh branch of `_load_or_create_merge_state` writes the marker before `save_state`
- [ ] T004 Run the existing `detect_legacy_in_flight_state`/FR-012 tests and the `tests/consolidation` state/resolve/terminus files

### Dependencies
None.

### Risks & Mitigations
- The re-run is now a zero-progress resume. Check that persisted target/strategy precedence is acceptable (post-spec squad).

## Work Package WP02: #5110 dry-run fail-closed (Priority: P2)

**Goal**: `consolidate --dry-run [--json]` exits 1 on `CoordinationWorktreeUnmaterialized`/`CoordinationBranchDeleted`, with the exception's remediation and valid JSON (FR-004).

### Included Subtasks
- [ ] T005 Red-first CLI repro `tests/consolidation/test_issue_5110_dry_run_unmaterialized_coord.py`
- [ ] T006 [P] Guard the review-preflight region of `run_dry_run_forecast` via an extracted helper; `_emit_dry_run_error` gains an optional `error_code`
- [ ] T007 Run `tests/consolidation/test_forecast_seam.py` and the dry-run tests

### Dependencies
None (parallel with WP01).

## Work Package WP03: #5044 integration fixture re-pins + sc007 verdict (Priority: P2)

**Goal**: Every #5044 `tests/integration` red is re-pinned (stale fixture) or dispositioned. `test_resume_completes_within_30s_budget` goes green without loosening its budget (FR-005–FR-007).

### Included Subtasks
- [ ] T008 Drift A: the coord fail-closed ADR (seam, Guard4, retention ×4)
- [ ] T009 Drift B: the MagicMock-manifest reconciliation phases (post-merge index refresh ×3, untracked, sparse, planning-lane wp_order)
- [ ] T010 Drift C1: `test_merge_resume` post-fix resume state (3 + the budget test)
- [ ] T011 Drift C3: seed WP01 approved (lane-worktree safety, primary-checkout safety)
- [ ] T012 Drift D: the arbiter fixture writes `lanes.json`, plus a negative cell
- [ ] T013 Drift E: causal rework events in the retrospect smoke test
- [ ] T014 sc007: a both-sides write-up and an operator verdict request; no edit without a verdict

### Dependencies
WP01 (the C1 fixtures depend on marker semantics).

### Risks & Mitigations
- A vacuous re-pin. Each re-pin keeps the test's load-bearing assertion, and any stub is justified in its commit message.
