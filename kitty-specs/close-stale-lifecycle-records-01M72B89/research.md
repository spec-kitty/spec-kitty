# Research: Close stale WP lifecycle records

Code grounding for #7346 was done read-only at `origin/main` 9518fb71 (2026-11-10). File and line references are to that tree.

## Current state

- `doctor ops --close-stale` (`src/specify_cli/cli/commands/doctor.py:1040-1090`, `_run_ops_sweep` :990-1037) closes only Op records (`kitty-ops/<id>.jsonl`) through `doctor.ops.close_stale_ops` (`src/specify_cli/doctor/ops.py:193-283`). Each close goes through `ProfileInvocationExecutor.complete_invocation(outcome="abandoned", closed_by="doctor_sweep")` and auto-commits only the closure spine.
- Lifecycle records (`src/specify_cli/invocation/lifecycle.py`) are one file per record, append-only (ADR 2026-11-01-2). Pairing groups by `(mission_id, canonical_action_id)`; a group is an orphan when it has more `started` than completions (`completed`, `failed`). `find_orphans` (:246) lists orphaned groups; `doctor invocation-pairing` reports them.
- The only completion writer is `pair_previous_lifecycle_record` (`src/runtime/next/next_invocation_lifecycle.py:138`), which runs only when `spec-kitty next` reports a result, and that also advances the Mission. This is the #7346 gap.
- `ProfileInvocationPhase` is `started|completed|failed` (`invocation/record.py:242`); `from_dict` rejects any other phase (:307), and readers skip a record they cannot parse.
- In this repository: 1,652 lifecycle files and 123 orphans (44 with a work package id), among them #7340's WP04.

## Decisions

- **Phase.** Decision: a new `abandoned` phase (operator ruling, Decision Moment 01M72B8Z4FQ7J02B2HJ0ZNTC25). Rationale: a sweep closure is not a failure of the action. Alternative considered: `failed` with an `abandoned:` reason, which needs no contract change, but the operator chose a distinct phase.
- **Commit.** Decision: auto-commit like the Op sweep (Decision Moment 01M72B942EZG713N48E0ERWE9K). The #6410 rules apply per record kind: skip when the path is ignored or the primary branch tracks no lifecycle records. A protected-branch refusal is reported, never bypassed. Alternative considered: write and list without committing (rejected by the operator).
- **Commit helper.** Decision: extract the trailer, `safe_commit` and refusal mapping from `ProfileInvocationExecutor._commit_op_record` into one helper. Rationale: a second copy would drift (single canonical authority). Alternative considered: a new lifecycle-only commit function (rejected as duplicate authority).
- **Unpaired tail.** Decision: one `unpaired_started(group)` helper. The slice exists twice today (`doctor_orphan_report`, `find_latest_unpaired_started`); a third copy was rejected.
- **Scope and exit code.** Every checkout (parity with #6661), and fresh orphans make the sweep exit 1 as fresh Ops do (Decision Moment 01M72B9FER5AYKRVXF0QX06XK1).
- **JSON.** Additive `lifecycle_records` key; the existing keys stay Op-only (`test_doctor_ops_cli.py` pins the key set; `closure_spine` is the precedent for an additive key).

## Gates and tests that pin the touched code

- `tests/architectural/test_event_log_writes_gate.py` (one locked lifecycle writer), `tests/architectural/test_archive_root_byte_identical.py` (`kitty-ops/` add-only), `tests/architectural/test_no_dead_symbols.py`, `tests/architectural/test_json_contract_enumeration.py`, `tests/architectural/test_timing_coverage_invariant.py`, `tests/architectural/test_docs_cli_reference_parity.py`.
- `tests/specify_cli/invocation/test_doctor_ops.py`, `test_doctor_ops_worktrees.py`, `cli/test_doctor_ops_cli.py`, `test_lifecycle_pairing.py`, `test_lifecycle_per_record.py`, `tests/specify_cli/next/test_next_invocation_lifecycle_seam.py`, `tests/integration/test_next_lifecycle_records.py`, `tests/cli/test_doctor_default_run.py`.
- Out of matrix (run locally): `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py`, `test_lifecycle_read_seam_migration.py`.

## Related, not folded

- #3969 (explicit abandon/resume semantics, the conceptual home under #3897), #5052 (doctor-ops sweep performance budget, already red), #5938 (uncommitted `next` writes dirty consolidate), #4504 and #4419 (Op spine).
