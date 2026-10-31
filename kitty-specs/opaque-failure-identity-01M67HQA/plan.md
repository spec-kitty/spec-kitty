# Implementation Plan: Opaque declared-command failure identity

**Branch**: `issue-6751-opaque-failure-identity` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/opaque-failure-identity-01M67HQA/spec.md`

The planning questions are answered by `research.md`: the collision is reproduced on `main@512567eee7`, the cause is exactly the issue's three cited symbols, and the one hard constraint on the shape of the fix is the transition-gate parity oracle, which asserts exact metadata equality against fixtures captured from the base commit.

## Summary

An opaque declared-command failure (`review/scope_source.py::_whole_run_failure`) is a synthetic placeholder whose only identity is the constant `<declared-command>`; `review/baseline.py::diff_baseline` matches failures by name, so every opaque failure matches every other one and `review/pre_review_gate.py::_classify_current_failures` returns `no_new_failures` for a candidate that failed for an unrelated reason than the baseline. The plan:

1. Give `BaselineFailure` an explicit **opaque** marker plus the run's **observed exit status**, and make the synthetic identity carry both. An opaque failure is the same failure only when the exit status AND a digest of the run's full output tail are equal; otherwise it is a **new** failure. The one-line `error` stays display text: unrelated failures routinely share a generic last line (`make: *** [Makefile:1: all] Error 1`), so it is not an identity.
2. Keep named identities (`FAIL <name>: <message>`, JUnit test names) on name matching so the existing pre-existing-failure behaviour is preserved.
3. Carry the candidate run's exit status into `GateVerdict` and state it in the `no_new_failures` reason, so a baseline-relative verdict can no longer read as "the candidate exited 0".

No gate is skipped, no default changes, and the opt-in block predicate is untouched.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pytest; the review engine, typer/click for the transition hook
**Storage**: `baseline-tests.json` mission artifacts (per-WP baseline records)
**Testing**: Red first through the pre-existing entry point (`parse_results` → `_classify_current_failures`, and `evaluate_with_scope` for the verdict surface); targeted modules under `tests/review/`
**Target Platform**: Linux CI (module matrix: review shard)
**Project Type**: single
**Performance Goals**: N/A (pure comparison over in-memory failure tuples)
**Constraints**: parity oracle in `tests/review/fixtures/parity/` asserts exact metadata equality — the exit status must ride on the existing `reason` field, not a new metadata key; no new suppressions; no timeout default change
**Scale/Scope**: 3 product modules, roughly 120 product lines, plus tests, a changelog entry and a changelog-adjacent doc note

## Charter Check

- **ATDD-first / red-first (DIRECTIVE_034).** The repro test (the issue's counterexample) is written and shown red on the planning base before the fix, then green.
- **Single canonical authority.** `OPAQUE_FAILURE_TEST_ID` moves to `baseline.py` next to `BaselineFailure`, the data model that owns the identity, and `scope_source.py` consumes it; there is no second sentinel.
- **No fake green (Standing Order #9).** The fix never turns an unparseable result into a pass: a non-matching opaque candidate failure is `NEW_FAILURES`, and a matching one still records the nonzero exit in the verdict reason.
- **Locality of change (DIRECTIVE_024).** Product edits stay in `src/specify_cli/review/{baseline,scope_source,pre_review_gate}.py` and the transition-gate renderer.
- **No full heavy suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`).** Validation is the `tests/review/` modules that own the touched code plus the one hook module the verdict surface touches.
- **Pre-existing failure reporting.** Any red encountered outside this diff is cited in the PR's Deferred section against its issue (#6798, #6801, #6816 family).

## Project Structure

### Documentation (this mission)

```
kitty-specs/opaque-failure-identity-01M67HQA/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── issue-matrix.md
├── traces/
└── tasks/
```

### Source Code (repository root)

```
src/specify_cli/review/baseline.py          # BaselineFailure identity fields, diff_baseline comparison
src/specify_cli/review/scope_source.py      # _whole_run_failure carries exit status + opaque marker
src/specify_cli/review/pre_review_gate.py   # GateVerdict.candidate_exit_code + honest no_new_failures reason
src/specify_cli/cli/commands/agent/tasks_move_task_gates.py   # render the reason on the existing no_new_failures line
tests/review/test_opaque_failure_identity.py                  # new: red-first repro + ratchets
tests/review/test_pre_review_gate_engine.py                   # verdict-surface assertions
tests/review/test_scope_source.py                             # parse_results identity assertions
tests/review/test_baseline.py                                 # diff_baseline back-compat
```

**Structure Decision**: single project; the change is confined to the existing review engine and its one renderer.

## Implementation Concern Map

### IC-01 — Bounded opaque identity and comparator

- **Purpose**: Make two opaque whole-run failures the same failure only when their exit status and summary are identical, without changing named-failure matching.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-003, C-002
- **Affected surfaces**: `src/specify_cli/review/scope_source.py` (`_whole_run_failure`, sentinel constant), `src/specify_cli/review/baseline.py` (`BaselineFailure.opaque`, `BaselineFailure.exit_code`, `to_dict`/`from_dict`, `diff_baseline`)
- **Sequencing/depends-on**: none
- **Risks**: legacy `baseline-tests.json` artifacts must load (missing keys default, never `KeyError`); the sentinel constant must have one home; `diff_baseline`'s named-failure behaviour must be byte-identical for existing callers.

### IC-02 — Verdict reports the candidate exit status

- **Purpose**: Carry the candidate command's observed exit status into the verdict and say in the `no_new_failures` reason that the verdict is baseline-relative, without adding a metadata key the parity oracle would reject.
- **Relevant requirements**: FR-004, SC-004, C-001
- **Affected surfaces**: `src/specify_cli/review/pre_review_gate.py` (`GateVerdict`, `_classify_current_failures`, `_evaluate_via_scope_source`), `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py` (render the reason on the existing dim line)
- **Sequencing/depends-on**: IC-01
- **Risks**: the parity fixtures pin `reason: null` and the exact console string for `no_new_failures`; both must stay unchanged for a verdict that carries no exit status. The `NEW_FAILURES` console line and block message stay unchanged.

## Complexity Tracking

No charter violations. No new project, package or persistence layer; the change reuses the existing data model and the existing verdict surface.
