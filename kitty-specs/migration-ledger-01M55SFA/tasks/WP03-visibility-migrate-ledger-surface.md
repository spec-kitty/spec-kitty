---
work_package_id: WP03
title: 'Visibility: the spec-kitty migrate ledger read surface (IC-05)'
dependencies:
- WP01
- WP02
requirement_refs:
- FR-011
- SC-005
planning_base_branch: issue-5230-migration-ledger-impl
merge_target_branch: issue-5230-migration-ledger-impl
branch_strategy: Planning artifacts for this mission were generated on issue-5230-migration-ledger-impl. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5230-migration-ledger-impl unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-migration-ledger-01M55SFA
base_commit: 103b68497fcab2d9e84668a8aa9db27d6d93a4a0
created_at: '2026-10-18T00:16:04.307535+00:00'
subtasks:
- T018
- T019
- T020
- T021
history:
- timestamp: '2026-10-17T21:06:30Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks-packages
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/upgrade/test_migrate_ledger_cmd.py
execution_mode: code_change
lane: planned
owned_files:
- src/specify_cli/cli/commands/migrate_cmd.py
- tests/specify_cli/upgrade/test_migrate_ledger_cmd.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – Visibility: the `spec-kitty migrate ledger` read surface

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`role: implementer`). Implementation command (depends on WP01, WP02):
`spec-kitty implement WP03 --base WP02`

---

## Objective

Add the ONE canonical, read-only operator surface **`spec-kitty migrate ledger`** on the existing
`migrate` Typer group. It prints the applied set in declared (manifest) order, the tracked /
clone-local partition, whether a clone-local step is *in place here* vs merely *recorded elsewhere*
(via the migration's own `detect()`), and a per-row drift flag; `--json` emits the structured shape.

Grounded in `plan.md` **IC-05 (E1)** and OQ-1; spec FR-011, SC-005.

## Context & Constraints — design invariants (carry these exactly)

- **A single canonical surface (OQ-1 ruling).** `spec-kitty migrate ledger` only. Do **NOT** add a
  `doctor migrations` surface, and do **NOT** add a `spec-kitty upgrade --list-applied` alias. The
  feature file's three `When` lines are rebound to `migrate ledger` in WP05, not here.
- **Consume, do not recompute.** The surface reads via `detector.applicable_migrations` (the single
  pending-source) + the **report-model assembler in WP01's `ledger.py`** (declared/applied/pending,
  partition, in-place-here, drift). It must NOT reimplement selection or drift.
- **Read-only.** No commit, no file write, no mutation of any kind.
- **House pattern.** Mirror the existing `migrate` subcommands' shape (`--json` structured payload +
  rich human summary), e.g. the `backfill-topology` subcommand.

## Pointcut Map (file:line → change)

| # | file | change | what |
|---|------|--------|------|
| E1 | `src/specify_cli/cli/commands/migrate_cmd.py` ≈ end of subcommands | **ADD** | `@app.command(name="ledger")` read-only surface; `--json`; reads via `detector.applicable_migrations` + the `ledger` report assembler; prints applied-in-declared-order, partition, in-place-here, drift. |

> E2 (report-model assembler) is owned by WP01 in `ledger.py`; consume it, do not duplicate it.

## Owned files (disjoint)

- `src/specify_cli/cli/commands/migrate_cmd.py`
- `tests/specify_cli/upgrade/test_migrate_ledger_cmd.py`

## Red-first tests to write FIRST

**`tests/specify_cli/upgrade/test_migrate_ledger_cmd.py`** (NEW):
- prints the applied set in **declared (manifest) order**;
- distinguishes **recorded-elsewhere vs in-place-here** on a seeded clone;
- **flags drift** for a drifted record;
- `--json` emits the structured shape;
- is **read-only** — asserts no commit and no file write.

— FR-011, SC-005. Write red first (surface absent), then green.

## Subtasks & Detailed Guidance

### T018 – `migrate ledger` subcommand skeleton + `--json` (FR-011)
Register `@app.command(name="ledger")` on the `migrate` group; add `--json`. No doctor surface, no
upgrade alias.

### T019 – Wire to the single authority (FR-011)
Consume `detector.applicable_migrations` + WP01's report assembler; render partition, in-place-here
(via `detect()`), drift. Do not recompute selection/drift.

### T020 – Rich human summary (house pattern)
Match the sibling `migrate` subcommands' human output; keep the `--json` payload the one structured
shape both paths share.

### T021 – Land the test green (SC-005)
Make `test_migrate_ledger_cmd.py` green, including the read-only (no commit / no write) assertion.

## Test strategy & blast radius (targeted — NOT whole dirs)

Run and record counts: `tests/specify_cli/upgrade/test_migrate_ledger_cmd.py`, plus `tests/cli/`
and `tests/specify_cli/upgrade/`. CI owns full suites.

## Quality gates

`ruff check` + `ruff format --check` clean; `mypy` zero new; complexity ≤15; literals hoisted; no
suppressions. SC-008 ratchet untouched.

## Acceptance criteria satisfied

SC-005 (visibility surface prints applied-in-declared-order, recorded-elsewhere-vs-in-place-here,
drift — all read-only); FR-011. Enables the three read-surface feature scenarios bound in WP05.

## Risks & Mitigations

- **Single-authority drift:** if the surface recomputes selection it diverges from `--dry-run` —
  mitigate by consuming `detector.applicable_migrations` only.

## Review Guidance

Confirm: exactly one new surface (`migrate ledger`), no doctor/alias; no mutation; `--json` and
human output share one assembler.

## Activity Log

- 2026-10-17T21:06:30Z – system – lane=planned – Prompt created.
