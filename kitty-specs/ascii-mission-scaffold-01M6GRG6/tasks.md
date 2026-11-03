# Tasks: ASCII-by-construction mission scaffolding

**Mission**: `ascii-mission-scaffold-01M6GRG6` · **Branch**: `issue-6877-ascii-mission-scaffold`
**Input**: [plan.md](./plan.md) (IC-01..IC-03), [spec.md](./spec.md) (7 FRs, 2 NFRs, 4 Cs, 7 SCs), [research.md](./research.md) (D-1..D-6).

> Reference rows below are **not** checkboxes. Subtask completion is event-sourced —
> record with `spec-kitty agent tasks mark-status T0xx --wp WPxx --status done`. The
> reduced event-log snapshot is the sole authority (#2816).

> **Standing clause for every WP:** any non-ASCII character added to a *core-owned
> scaffold string* is a defect against this mission's own invariant, even when the gate
> would not flag it (`detect_problematic_characters` ignores box drawing and `·`; the
> mission's pin is `max(byte) <= 0x7F`, which is stricter). Author new scaffold text in
> ASCII.

## Lane / sequencing overview

- **Lane A** — WP01 (`TASKS_README_TEMPLATE` ASCII + the pin). Independent. Owns the
  product text and the gate that keeps it honest.
- **Lane B** — WP02 (converge the legacy emitter onto the renderer). Independent of WP01 in
  code (different files, no import of WP01's new symbols) and may be implemented in
  parallel; it *depends* on WP01 at review time for the shared invariant, so it is
  sequenced after WP01 for a clean single-WP diff to review (`plan.md` IC-02/IC-03).
- No WP owns `kitty-specs/` paths, so no `planning_artifact` WP is needed. The changelog
  fragment is wrap-up work, not a WP subtask (#6879).

## Requirement → Work-Package coverage

| FR | WP | FR | WP |
|----|----|----|----|
| FR-001 | WP01 | FR-005 | wrap-up (PR body + upstream issue) |
| FR-002 | WP01 | FR-006 | WP02 |
| FR-003 | WP01 | FR-007 | WP01 (T004) |
| FR-004 | WP01 | NFR-001 / NFR-002 | WP01 (asserted in the pin) |

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: new pin module asserts the rendered `tasks/README.md` is ASCII and the gate detector is empty — run it against the current constant and record it failing on U+2013 | WP01 | |
| T002 | Red-first: add the self-mutation case (subprocess render with a glyph-injected constant) and prove it can distinguish pass from fail | WP01 | [P] |
| T003 | Replace the en dash and the box-drawing tree in `TASKS_README_TEMPLATE` with ASCII, preserving every instruction/label token verbatim | WP01 | |
| T004 | Align the scaffold's `history:` example to the pack template's `at:`/`actor:` field names (FR-007) | WP01 | |
| T005 | Assert FR-004 at the renderer boundary: the renderer formats, it does not sanitise — a non-ASCII branch name passes through unchanged | WP01 | |
| T006 | Red-first: a test asserts `setup_feature_directory()` writes exactly `render_tasks_readme_content(feature_dir.name)` — run it against the inlined copy and record it failing | WP02 | |
| T007 | Delete the ~55-line inline literal in `setup_feature_directory` and render through `render_tasks_readme_content` (lazy import; `plan.md` IC-02) | WP02 | |
| T008 | Add the second-literal census: no other module in `src/` inlines the scaffold text (`# Work Package Prompt:` appears in exactly one core module) | WP02 | |
| T009 | Re-run the touched suites and record counts; confirm `test_worktree.py`'s existing `"lane:" not in content` assertion still holds on the converged text | WP02 | |

---

## Work Packages

### WP01 — ASCII scaffold text and the pin · FR-001, FR-002, FR-003, FR-004, FR-007
**Prompt**: [tasks/WP01-ascii-scaffold-text-and-pin.md](./tasks/WP01-ascii-scaffold-text-and-pin.md)
**Goal**: Remove the U+2013 (and the non-ASCII tree art) from the one core-owned scaffold constant by editing the source text, and pin the rendered result so the class cannot come back.
**Priority**: P0 (this is the reported defect). **Independent test**: `render_tasks_readme_content("main")` is pure ASCII, `detect_problematic_characters()` reports nothing on it, and the pin fails when a glyph is injected.
**Subtasks**: T001–T005. **Depends on**: none. **Risk**: the tempting wrong fix is a write-boundary sanitizer (NFR-001) — the pin's round-trip case exists to catch it. **~300 lines.**

### WP02 — One authority for `tasks/README.md` · FR-006
**Prompt**: [tasks/WP02-one-scaffold-authority.md](./tasks/WP02-one-scaffold-authority.md)
**Goal**: Point the legacy `setup_feature_directory` emitter at `render_tasks_readme_content` and delete its inlined copy, so one literal holds the text and one pin covers both entry points.
**Priority**: P1. **Independent test**: the file `setup_feature_directory` writes is byte-identical to `render_tasks_readme_content(feature_dir.name)`, and no second copy of the text exists in `src/`.
**Subtasks**: T006–T009. **Depends on**: WP01 (shared invariant; sequenced for review, not for compilation). **Risk**: the inline copy's content drifts from the canonical text — the convergence is a deliberate content change to a test-only path, and C-004 forbids touching anything else in `worktree.py`. **~180 lines.**

---

## MVP scope

**WP01 alone** closes the reported defect: a freshly created mission's `tasks/README.md` stops failing its own encoding gate, and the pin keeps it that way. **WP02** removes the second authority that made the pin partially vacuous; it is small, independent in code, and can be dropped without weakening WP01.
