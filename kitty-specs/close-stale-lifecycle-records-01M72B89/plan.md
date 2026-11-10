# Implementation Plan: Close stale WP lifecycle records

**Branch**: `kitty/mission-close-stale-lifecycle-records-01M72B89` (lands on `feat/7346-close-stale-lifecycle-records`) | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/close-stale-lifecycle-records-01M72B89/spec.md`

## Summary

`spec-kitty doctor ops --close-stale` gains a second sweep: after closing stale Ops it closes every stale orphaned work-package lifecycle record (`kitty-ops/lifecycle/<ulid>.json`) by writing a new `abandoned` record paired with the orphaned `started` record, then commits the new files in the checkout that holds them. The record contract gains the `abandoned` phase; pairing counts it as a completion. The commit reuses the Op sweep's commit-or-skip rules and protected-branch refusal through one shared helper.

## Engineering Alignment

The scope decisions are the operator's (Decision Moments in `spec.md`). The engineering decisions below follow the existing seams and need no operator input:

- The `abandoned` phase is a value of the existing record contract (`ProfileInvocationPhase`), written through the one locked lifecycle append (`append_lifecycle_record`). No new writer.
- `abandoned` counts as a completion everywhere pairing counts completions (one predicate, not three copies).
- The unpaired tail of a group (the last `deficit` started records) is computed once (`unpaired_started`), replacing the two existing copies in `doctor_orphan_report` and `find_latest_unpaired_started`.
- The commit-or-skip rules (#6410) are generalized from the Op-record path shape to a record-kind pattern, so lifecycle closures skip when `kitty-ops/lifecycle/` is ignored or the primary branch tracks no lifecycle records.
- The commit itself (co-author trailer, `safe_commit`, protected-branch refusal mapped to `OpCommitOutcome`) is extracted from `ProfileInvocationExecutor._commit_op_record` into one helper both callers use.
- The sweep groups closures per checkout and commits each checkout's new files once.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (CLI); git via `kernel.git` and `specify_cli.git.safe_commit`
**Storage**: files: `kitty-ops/lifecycle/<ulid>.json` (one sorted-key JSON line per record, ADR 2026-11-01-2)
**Testing**: pytest; unit tests under `tests/specify_cli/invocation/`, CLI tests under `tests/specify_cli/invocation/cli/`, and the out-of-matrix golden `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` run locally
**Target Platform**: Linux, macOS, Windows 10+ (CLI)
**Project Type**: single (CLI package `src/specify_cli`)
**Performance Goals**: NFR-003: under 2 s added for 2,000 lifecycle records with no orphans
**Constraints**: append-only lifecycle store (NFR-001); existing sweep JSON keys unchanged (C-003); complexity ≤ 15 per function
**Scale/Scope**: about 1,650 lifecycle records in this repository today, 123 orphans

## Charter Check

- **Single canonical authority**: one lifecycle writer, one completion predicate, one unpaired-tail helper, one commit helper shared with the Op sweep. Pass.
- **Architectural alignment**: changes stay in `specify_cli.invocation` and `specify_cli.doctor` plus the `doctor` CLI shell; no layer rule changes. Pass.
- **ATDD-first**: each work package starts with failing acceptance tests through the pre-existing entry point (`doctor ops --close-stale`, the lifecycle reader). Pass (planned).
- **Terminology**: Mission, work package, Op; no new "feature" vocabulary. Pass.
- **Architectural gates**: `test_event_log_writes_gate.py` (no new raw writer), `test_archive_root_byte_identical.py` (add-only), `test_no_dead_symbols.py`. Re-pinned honestly, never loosened. Pass (planned).
- **No full heavy suites in Mission work**: targeted files and the named gates only. Pass.

## Project Structure

### Documentation (this mission)

```
kitty-specs/close-stale-lifecycle-records-01M72B89/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/doctor-ops-lifecycle-sweep.md
└── tasks.md (produced by /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/invocation/record.py            # ProfileInvocationPhase gains "abandoned"
src/specify_cli/invocation/lifecycle.py         # completion predicate, unpaired_started, abandoned writer
src/specify_cli/invocation/op_commit_policy.py  # skip rules keyed on a record-kind path pattern
src/specify_cli/invocation/executor.py          # _commit_op_record delegates to the shared commit helper
src/specify_cli/doctor/ops.py                   # close_stale_lifecycle_records, SweepReport.lifecycle_records
src/specify_cli/cli/commands/doctor.py          # ops sweep output (table + JSON) and exit code
docs/adr/4.x/2026-11-01-2-op-lifecycle-records-are-one-file-per-record.md  # amendment
docs/context/ops-vs-missions.md, docs/architecture/trail-model.md, docs/api/cli-commands.md (regenerated)
```

**Structure Decision**: single project; the change extends the existing invocation and doctor modules.

## Complexity Tracking

No Charter Check violations.

## Implementation Concern Map

### IC-01 — The abandoned phase in the lifecycle record contract

- **Purpose**: let a lifecycle record say "closed by the doctor sweep" and have pairing count it as a completion.
- **Relevant requirements**: FR-001, FR-002, FR-005, NFR-001, C-002, C-004
- **Affected surfaces**: `invocation/record.py`, `invocation/lifecycle.py`, ADR 2026-11-01-2 (amendment)
- **Sequencing/depends-on**: none
- **Risks**: an older CLI skips `abandoned` records (accepted). `pair_previous_lifecycle_record` must not pair a `next --result` with a record the sweep already closed: it reads the unpaired tail, which now excludes swept records.

### IC-02 — The lifecycle sweep, its commit and its report

- **Purpose**: close stale orphans in every checkout, commit the closures, and report them in human and JSON output.
- **Relevant requirements**: FR-003, FR-004, FR-006, FR-007, FR-008, FR-009, NFR-002, NFR-003, C-001, C-003, C-005
- **Affected surfaces**: `doctor/ops.py`, `cli/commands/doctor.py`, `invocation/op_commit_policy.py`, `invocation/executor.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: `close_stale_ops` is at complexity 11 and `doctor.py` is a hot god-module: add new functions, do not grow existing ones. The sweep JSON is a frozen contract except for additive keys (`closure_spine` precedent). The doctor-ops perf test is already red (#5052); keep the lifecycle scan out of its path or record its cost.

### IC-03 — Documentation

- **Purpose**: make the docs match: lifecycle records now have a close route.
- **Relevant requirements**: FR-010
- **Affected surfaces**: `docs/context/ops-vs-missions.md:113`, `docs/architecture/trail-model.md`, `docs/api/cli-commands.md` (regenerated), changelog fragment
- **Sequencing/depends-on**: IC-02
- **Risks**: `docs/api/cli-commands.md` is generated; regenerate with `scripts/docs/build_cli_reference.py`, never hand-edit.
