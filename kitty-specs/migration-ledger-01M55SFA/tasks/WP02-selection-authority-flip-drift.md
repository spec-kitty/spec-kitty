---
work_package_id: WP02
title: Selection authority flip + drift instrumentation (IC-03, IC-04)
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-008
- FR-010
- NFR-004
- C-003
- C-004
- SC-001
- SC-002
- SC-006
planning_base_branch: issue-5230-migration-ledger-impl
merge_target_branch: issue-5230-migration-ledger-impl
branch_strategy: Planning artifacts for this mission were generated on issue-5230-migration-ledger-impl. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5230-migration-ledger-impl unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-migration-ledger-01M55SFA
base_commit: 103b68497fcab2d9e84668a8aa9db27d6d93a4a0
created_at: '2026-10-17T22:20:09.900579+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
- T016
- T017
history:
- timestamp: '2026-10-17T21:06:30Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks-packages
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/upgrade/test_ledger_drift.py
execution_mode: code_change
lane: planned
owned_files:
- src/specify_cli/upgrade/registry.py
- src/specify_cli/upgrade/runner.py
- src/specify_cli/upgrade/migrations/base.py
- src/specify_cli/upgrade/detector.py
- tests/upgrade/test_clone_local_selection.py
- tests/upgrade/test_clone_local_migration_idempotent.py
- tests/upgrade/test_ledger_drift.py
- tests/specify_cli/upgrade/test_registry_runs_first.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – Selection authority flip + drift instrumentation

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`role: implementer`). Implementation command (depends on WP01):
`spec-kitty implement WP02 --base WP01`

---

## Objective

Flip the execution authority from the **version window** to **ledger-diff**, delete the #6233
compensation machinery, demote `detect()` to an idempotency guard only, wire `get_all()` to the
manifest index, and add the drift ClassVars + apply-time hash storage. This is the sharpest edge of
the mission: behaviour for the 124 migrations must stay byte-identical EXCEPT the two intended fixes
(version-window strand, pulled-clone clone-local).

Grounded in `plan.md` **IC-03 (C1–C7)** + **IC-04 (D1, D3)**, and spec FR-004/005/008/010, NFR-004,
C-003/004, SC-001/002/006.

## Context & Constraints — design invariants (carry these exactly)

- **`get_applicable()` → ledger-diff.** `pending = [m for m in manifest_order if m not in
  ledger.applicable_records_for(m)]`, partition-aware, THEN filtered by `detect()`/`can_apply()`.
  The version window (`from_v < target <= to_v`) is retired as the applied authority.
- **DELETE `_clone_local_selected_below_window`** and its call site. A pulled clone's empty
  per-clone ledger is what re-selects the clone-local migration now — not per-site reselection.
- **Collapse `reselect_when_recorded`** to a ledger lookup (or inline at the skip gate); the
  sub-window clone-local branch is gone.
- **`detect()` is the idempotency guard ONLY (C-003)** — a pre-`apply()` belt-and-suspenders
  check, NEVER the selection authority.
- **`get_all()` sort key → `manifest_index`** (consume WP01's `manifest.py`); `Version(target_version)`
  demoted to the monotonicity cross-check the gate consumes.
- **Add `identity` + `content_hash_sources` ClassVars to `base.py`** (OQ-3): `identity: ClassVar[str]`
  defaults to `migration_id`; `content_hash_sources: ClassVar[tuple[str, ...]]` defaults empty ⇒ own
  module file. Store `identity`+`content_hash` in the record at apply time (co-located with the
  record path).
- **`SupersededMigration` / neutralised no-ops** (`detect()==False`) stay in the manifest, record a
  `skipped` result, and never re-fire (FR-008).
- **EXTEND, do not weaken, the existing selection/idempotency tests** (NFR-004).

## Pointcut Map (file:line → change)

| # | file:line | change | what |
|---|-----------|--------|------|
| B3 | `registry.py:79-80` (`get_all`) | **MODIFY** | sort key → `manifest_index`; `Version(target_version)` → monotonicity cross-check. |
| C1 | `registry.py:82-135` (`get_applicable`) | **MODIFY** | replace version-window body (`:119`, `:130-132` clone-local branch) with ledger-diff, partition-aware; then `detect()`/`can_apply` filter. |
| C2 | `registry.py:175` (`_clone_local_selected_below_window`) + call site `:130-132` | **DELETE** | remove the #6233 compensation. |
| C3 | `base.py:135` (`reselect_when_recorded`) | **MODIFY/collapse** | ledger lookup or inline; sub-window branch gone. |
| C4 | `registry.py:198` (`_runs_first_selected_outside_window`) + `:212` (`_order_runs_first`) | **MODIFY** | reconcile `runs_first` with manifest order (still leads); `structural_detect` via ledger not window. |
| C5 | `runner.py:357` (`_apply_migration` skip gate) | **MODIFY** | skip = "id present in the applicable ledger partition?"; `detect()` at `:377-378` stays idempotency guard only. |
| C6 | `runner.py` record path (`_apply_migration` success leg, `_record_migration_result`, `_finalize_main_metadata` ≈`:290`) | **MODIFY** | write applied record into the ledger (partition-routed) instead of `metadata.record_migration`; Superseded/no-ops record `skipped`. |
| C7 | `detector.py:49` (`applicable_migrations`) | **VERIFY/MINOR** | stays the single pending-source over the new `get_applicable`. |
| D1 | `base.py:74` (`BaseMigration`) | **MODIFY** | ADD `identity` + `content_hash_sources` ClassVars. |
| D3 | `runner.py` apply success leg | **MODIFY** | compute + store `identity`+`content_hash` in the record (co-located with C6, via WP01's `compute_content_hash`). |

## Owned files (disjoint)

- `src/specify_cli/upgrade/registry.py`
- `src/specify_cli/upgrade/runner.py`
- `src/specify_cli/upgrade/migrations/base.py`
- `src/specify_cli/upgrade/detector.py`
- `tests/upgrade/test_clone_local_selection.py`
- `tests/upgrade/test_clone_local_migration_idempotent.py`
- `tests/upgrade/test_ledger_drift.py`
- `tests/specify_cli/upgrade/test_registry_runs_first.py`

## Red-first tests to write FIRST

1. **EXTEND `tests/upgrade/test_clone_local_selection.py`**: red-first — a sub-window stranded
   migration IS selected by ledger-diff; a pulled-clone clone-local case selects via the EMPTY
   per-clone ledger (NOT `_clone_local_selected_below_window`, which is deleted). — FR-004, FR-005,
   SC-001, SC-002, SC-006.
2. **EXTEND `tests/upgrade/test_clone_local_migration_idempotent.py`**: `SupersededMigration`
   records `skipped` and never re-fires; a present clone-local effect no-ops via `detect()`. — FR-008.
3. **EXTEND `tests/specify_cli/upgrade/test_registry_runs_first.py`**: `runs_first` still leads under
   manifest order. — NFR-004.
4. **`tests/upgrade/test_ledger_drift.py`** (NEW): a drifted-source fixture flags drift; a
   multi-file migration hashes deterministically; drift NEVER triggers `apply()` (C-004). — FR-010.

Also add/keep a **parity** assertion that the selected set over a corpus fixture is unchanged
before/after, minus the two intended fixes (NFR-004).

## Subtasks & Detailed Guidance

### T010 – `get_all` → manifest index (B3)
Swap the sort key to `manifest_index`; keep `Version(target_version)` only for the monotonicity
cross-check. Do not change the resulting order for existing migrations (parity).

### T011 – `get_applicable` → ledger-diff; DELETE `_clone_local_selected_below_window` (C1, C2)
Implement partition-aware ledger-diff; remove the window body and the clone-local sub-window branch
+ its helper and call site.

### T012 – Collapse `reselect_when_recorded`; reconcile `runs_first` (C3, C4)
Collapse to a ledger lookup; keep `runs_first` leading under manifest order; route `structural_detect`
through the ledger.

### T013 – Skip gate → ledger; `detect()` demoted (C5)
Skip decision reads the applicable ledger partition; keep `detect()` strictly as the pre-`apply()`
idempotency guard (C-003).

### T014 – Record path → ledger (C6, FR-008)
Write applied records (partition-routed) in place of `metadata.record_migration`; Superseded /
neutralised no-ops record `skipped` and never re-fire.

### T015 – Drift ClassVars + apply-time hash (D1, D3, FR-010)
Add `identity` + `content_hash_sources` ClassVars to `BaseMigration`; store `identity`+`content_hash`
at apply via WP01's `compute_content_hash`. Drift is read-only — never auto-reapply (C-004).

### T016 – Verify `detector.applicable_migrations` single pending-source (C7)
Confirm it delegates to the new `get_applicable` so `--dry-run`, the WP03 surface, and the compat
planner share one authority (FR-011 dependency).

### T017 – Land the extended/new tests green (NFR-004)
Make all four test files green; confirm the corpus parity assertion holds.

## Test strategy & blast radius (targeted — NOT whole dirs)

Run and record counts: the four test files above, plus `tests/upgrade/` and
`tests/specify_cli/upgrade/`. CI owns full suites. Do NOT run the bare `tests/architectural/`.

## Quality gates

`ruff check` + `ruff format --check` clean; `mypy` zero new; complexity ≤15 (extract helpers in
`registry.py`); literals hoisted; no suppressions. SC-008 ratchet untouched.

## Acceptance criteria satisfied

SC-001 (no-op / stranded applies), SC-002 (fresh-clone local effect), SC-006
(`_clone_local_selected_below_window` deleted, `reselect_when_recorded` collapsed, no regression);
FR-004/005/008/010, NFR-004.

## Risks & Mitigations

- **R2 (#6233 regression, SC-006):** extend the clone-local tests red-first so the partition
  mechanism is proven to carry exactly what the deleted code carried; keep `detect()` as idempotency
  guard.
- **R1 parity (NFR-004):** corpus parity assertion before/after.

## Review Guidance

Confirm `_clone_local_selected_below_window` is gone (and its call site), `detect()` is never the
selection authority, and the extended tests are stricter (not weakened). Verify drift never calls
`apply()`.

## Activity Log

- 2026-10-17T21:06:30Z – system – lane=planned – Prompt created.
