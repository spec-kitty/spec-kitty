---
description: "Work package task list for mission decisions-lock-timeout-refusal-01M66YMG"
---

# Work Packages: Decisions Lock Timeout Refusal

**Inputs**: Design documents from `kitty-specs/decisions-lock-timeout-refusal-01M66YMG/`
**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md), [research.md](research.md), [quickstart.md](quickstart.md)

**Tests**: Required. Every functional requirement is a defect fix; each acquisition site gets
a red-first test through its existing entry point (charter ATDD-First, `DIRECTIVE_034`), plus
a same-fixture positive control so the refusal assertion is not vacuously satisfiable.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into three work packages, one per
command named in #6763. Prompt files live in `tasks/`; this file is the high-level view.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first test for `doctor decisions --repair` lock timeout | WP01 | |
| T002 | Red-first test for the coordination-only ledger copy site | WP01 | |
| T003 | Widen `_decisions_lock(mission_slug=...)` to `str \| None` | WP01 | |
| T004 | Route both doctor acquisitions through `_decisions_lock` | WP01 | |
| T005 | Render the doctor's lock-timeout refusal (human + `--json`) | WP01 | |
| T006 | Red-first test for owned `next` lock timeout | WP02 | |
| T007 | Route the owned-`next` acquisition through `_decisions_lock` | WP02 | |
| T008 | Render the `next` lock-timeout refusal (human + `--json`) | WP02 | |
| T009 | Positive control: a free lock still commits the advancement | WP02 | |
| T010 | Red-first integration test for `repair-runtime-lock` lock timeout | WP03 | |
| T011 | Route the runtime-lock repair acquisition through `_decisions_lock` | WP03 | |
| T012 | Map a `DecisionError` to its own code in the repair renderer | WP03 | |
| T013 | Positive control: a free lock still repairs, and the existing verb suite passes | WP03 | |

---

## Work Package WP01: Doctor `--repair` refuses a busy decisions lock (Priority: P1) 🎯 MVP

**Goal**: `spec-kitty doctor decisions --repair` reports a lock timeout as its C2 refusal
(human and `--json`), exits 1, writes nothing — for both of its acquisitions — and the
decisions lock has exactly one timeout translation in the codebase.
**Independent Test**: With the lock held, `doctor decisions --mission <m> --repair --json`
prints one `{"ok": false, "error": {...}}` document carrying `DECISION_LOCK_TIMEOUT`, exits
1, and the decisions directory is byte-identical afterwards; with the lock free, the same
command repairs and exits 0.
**Prompt**: `tasks/WP01-doctor-repair-refusal.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001, SC-001, SC-002, SC-003

### Included Subtasks

T001 Red-first test for `doctor decisions --repair` lock timeout
T002 Red-first test for the coordination-only ledger copy site
T003 Widen `_decisions_lock(mission_slug=...)` to `str | None`
T004 Route both doctor acquisitions through `_decisions_lock`
T005 Render the doctor's lock-timeout refusal (human + `--json`)

### Implementation Notes

- Write T001/T002 first and capture the pre-fix failure (`LockAcquireTimeout` escaping), then
  T003-T005 make them pass.
- T003 is a pure annotation widening on a private helper: the doctor always passes a real
  slug, but `_repair` is typed `str | None` and must not invent one.
- T004 deletes `_decisions_doctor.py`'s local `_LOCK_ACQUIRE_TIMEOUT_S` and imports the
  service's, so the doctor and the write path cannot drift to different waits. Keep the
  module's own `_decisions_lock_path` (two lockstep tests pin it).
- T005 catches `DecisionError` around the repair calls in `run_decisions_reconciliation` and
  emits exactly one document: `json_error("DECISION_LOCK_TIMEOUT", str(exc))` through
  `console.emit_json` under `--json`, a Rich `Error:` line otherwise, then `typer.Exit(1)`.

### Parallel Opportunities

- None worth taking: T001/T002 both edit one test module, and T003-T005 edit one source pair.

### Dependencies

- None (starting package).

### Risks & Mitigations

- The doctor must not print a partial report and then an error document → the catch wraps the
  repair calls *before* `_emit_human`/`_emit_json` runs.
- `_repair` may legitimately be called with `mission_slug=None` → the widened annotation is
  the fix; do not default the slug to `""` at call sites.

---

## Work Package WP02: Owned `next` refuses a busy decisions lock (Priority: P2)

**Goal**: An owned `spec-kitty next --owned-checkout` whose commit step cannot take the
decisions lock reports a lock-timeout refusal in `next`'s own error contract (human and
`--json`) and exits 1, instead of raising a traceback into the agent loop.
**Independent Test**: With the lock held, the advancing dispatch for an owned checkout exits
1 and emits `error_code: DECISION_LOCK_TIMEOUT` with a `next_step` retry instruction; with
the lock free, the same fixture still commits and returns its decision.
**Prompt**: `tasks/WP02-owned-next-refusal.md`
**Requirement Refs**: FR-001, FR-004, NFR-001, NFR-002, NFR-003, C-001, C-002, SC-001, SC-002

### Included Subtasks

T006 Red-first test for owned `next` lock timeout
T007 Route the owned-`next` acquisition through `_decisions_lock`
T008 Render the `next` lock-timeout refusal (human + `--json`)
T009 Positive control: a free lock still commits the advancement

### Implementation Notes

- T006 uses the owned-`next` unit seam (`tests/specify_cli/cli/commands/test_next_owned_*`
  style): mint the `OwnedCheckout` fact, create the lock file so the guard is taken, hold it,
  shorten the wait, and call `_dispatch_advancing_mode` with the pre-commit steps faked.
- T007 replaces the `nullcontext`-vs-`machine_file_lock` ternary with the seam; the
  "lock does not exist yet" case (no guard needed) must be preserved.
- T008 adds one dual renderer following `_emit_meta_read_error`'s shape, and catches only
  around the commit call so a decision is never printed after the refusal.

### Parallel Opportunities

- T006 and T009 can be written together in the same test module; T007/T008 are one source edit.

### Dependencies

- Depends on WP01 (the widened seam annotation and the single translation).

### Risks & Mitigations

- Refusing after the advancement and lifecycle record are durable → the message must say the
  retry is safe rather than implying nothing happened.
- Do not swallow other `RuntimeError`s from `safe_commit`: catch `DecisionError` only.

---

## Work Package WP03: `agent decision repair-runtime-lock` refuses a busy lock (Priority: P2)

**Goal**: The runtime-lock repair reports a lock timeout in its `{status, code, message}`
payload with code `DECISION_LOCK_TIMEOUT`, exits 1, and leaves the owned checkout untouched.
**Independent Test**: With the lock held, the verb exits 1, prints one JSON document carrying
`DECISION_LOCK_TIMEOUT`, and every asserted artifact (HEAD, index, worktree, lock inode) is
unchanged; with the lock free, the existing repair tests still pass.
**Prompt**: `tasks/WP03-runtime-lock-repair-refusal.md`
**Requirement Refs**: FR-001, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, SC-001, SC-002, SC-003

### Included Subtasks

T010 Red-first integration test for `repair-runtime-lock` lock timeout
T011 Route the runtime-lock repair acquisition through `_decisions_lock`
T012 Map a `DecisionError` to its own code in the repair renderer
T013 Positive control: a free lock still repairs, and the existing verb suite passes

### Implementation Notes

- T010 belongs in `tests/integration/test_owned_decision_runtime_lock.py`, which already owns
  the `owned_checkouts` fixture, `seed()` and `snapshot()` helpers for this verb.
- T011: the acquire happens only after the preflight and the `dry_run`/no-change
  short-circuits, so the refusal still leaves nothing written.
- T012: `_runtime_lock_error_code` maps `DecisionError` to `exc.code.value`; every other
  exception keeps its current mapping (ADR `2026-10-27-2` decision 7 keeps this verb's
  `{status, code, message}` shape for non-refusal failures).

### Parallel Opportunities

- None: all three subtasks touch the same call path.

### Dependencies

- Depends on WP01 (the single translation and the widened seam annotation).

### Risks & Mitigations

- The verb commits, so a partial run would be worse than a refusal → assert the full snapshot
  (HEAD, index, untracked files, lock inode) after the refusal.
- Do not change the owned-refusal (C2) path: only the generic failure renderer gains a code.
