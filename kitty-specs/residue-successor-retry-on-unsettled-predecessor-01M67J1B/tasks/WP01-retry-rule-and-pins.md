---
work_package_id: WP01
title: The retry rule and the red-first pins
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6688-residue-successor-retry
merge_target_branch: issue-6688-residue-successor-retry
branch_strategy: Planning artifacts for this mission were generated on issue-6688-residue-successor-retry. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6688-residue-successor-retry unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - The reported defect
history:
- at: '2026-10-30T23:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- tests/specify_cli/upgrade/test_successor_retry_6688.py
execution_mode: code_change
owned_files:
- src/specify_cli/upgrade/registry.py
- src/specify_cli/upgrade/migrations/base.py
- src/specify_cli/upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py
- src/specify_cli/upgrade/migrations/m_3_1_1_residue_safe_normalize_status_json.py
- tests/specify_cli/upgrade/test_residue_safe_successors_6669.py
- tests/specify_cli/upgrade/test_successor_retry_6688.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- spec-kitty/spec-kitty#6688
---

# Work Package Prompt: WP01 – The retry rule and the red-first pins

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave
according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: claude

---

## Objectives & Success Criteria

On a pre-ledger project whose `metadata.yaml` records a superseded residue predecessor as
`failed` or `skipped`, first adoption settles the successor with a baseline `success` record and
the repair is never retried (residual `C-006` of ADR `2026-10-17-1`, pinned by #6680 as a strict
`xfail`). This WP makes the settlement follow the predecessor: a migration that declares a
`predecessor_id` is settled only when that predecessor's recorded outcome proves the repair ran.
`detect()` stays the idempotency guard, so a repaired project is re-evaluated and never
re-applied.

Success means:

- `test_c006_an_unsettled_predecessor_record_still_lets_the_successor_run[failed|skipped]` passes
  with the `xfail` marker removed, and is red when the rule is reverted;
- a pre-ledger project at 3.2.0 with a `failed` or `skipped` predecessor gets the successor applied
  through `MigrationRunner.upgrade`, for all four successor/predecessor pairs, and the dirty
  Mission is repaired;
- a second `upgrade` on the same project applies nothing and changes no bytes under
  `kitty-specs/`;
- a migration without a declared predecessor, and a successor whose predecessor recorded `success`,
  behave exactly as before.

## Context

Read first:

- `kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/spec.md` — the requirement
  and the rejected routes (route 1 edits the frozen backfill; route 3 changes manifest semantics).
- `kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/research.md` — the traced
  record flow and decisions D1-D4.
- `kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/plan.md` — the rule in
  pseudocode and the risk table.

Code you will touch:

- `src/specify_cli/upgrade/registry.py` — `MigrationRegistry.get_applicable` (ledger-diff
  selection), `_settled_in_view`, `migration_settled`, `settled_in_selection_view`,
  `pending_adoption_ids`. It deliberately imports `migrations.base` lazily; keep it that way.
- `src/specify_cli/upgrade/migrations/base.py` — `BaseMigration.reselect_when_recorded` (the
  documented reselection seam that both selection and the runner's skip gate consult),
  `SupersededMigration`, `legacy_upgrade_scope`. `base.py` must not import the registry at module
  level; import it inside the method you add to.
- `src/specify_cli/upgrade/migrations/_residue_successor.py` — the lane mixin, which already
  declares `predecessor_id` and uses `settled_in_selection_view` in `detect()`. No behaviour change
  is expected there; if you touch it, keep its `detect`/`apply` wrappers intact.
- `src/specify_cli/upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py` and
  `m_3_1_1_residue_safe_normalize_status_json.py` — the two re-implemented successors; each reads a
  module-level `PREDECESSOR_ID` in `detect()` and needs one `predecessor_id` classvar.
- `tests/specify_cli/upgrade/test_residue_safe_successors_6669.py` — the #6680 suite, including the
  strict `xfail` and its helpers (`_plain_project`, `_dirty_mission`, `_pre_ledger`, `_ledger_era`,
  `_selected`, `_snapshot`, `_record`, `_get`, `PAIRS`, `quiet_runtime_assets`).

Do **not** edit a shipped migration module (`m_0_9_0_frontmatter_only_lanes.py`,
`m_0_9_1_complete_lane_migration.py`, `m_2_0_6_consistency_sweep.py`,
`m_3_1_1_normalize_status_json.py`) or `m_4_0_0rc8_backfill_migration_ledger.py`; DIRECTIVE_044
makes their bytes their `content_hash`. Do not change `target_version`, `order_manifest.txt`, the
ledger record schema, or the adoption ceiling.

## Subtasks

### T001 — Record the red

```bash
uv run pytest tests/specify_cli/upgrade/test_residue_safe_successors_6669.py -k c006 -q --runxfail
```

Both parameters fail on `assert NEW_311 in _selected(project, "3.2.0", "3.2.0")`. Keep the output;
it is the red-first evidence for the PR body.

### T002 — `BaseMigration.predecessor_id` and the reselection qualification

Add a documented `ClassVar[str] = ""` next to `runs_first`/`clone_local_effect`, naming the
superseded migration this one replaces and stating that a recorded success does not settle the
successor while the predecessor's outcome leaves the repair unproven (#6688).

Extend `reselect_when_recorded`:

```python
def reselect_when_recorded(self, project_path: Path) -> bool:
    if self.runs_first and self.structural_detect(project_path):
        return True
    if not self.predecessor_id:
        return False
    from ..registry import predecessor_outcome_settled

    return not predecessor_outcome_settled(project_path, self)
```

The empty-id guard must run before any ledger read (NFR-001). Update the method docstring: the
`runs_first`/`structural_detect` qualification stays, and the declared-predecessor qualification is
added; clone-local reselection is still not a per-migration hook.

### T003 — the selection-view predicate

In `registry.py`:

- add `_predecessor_outcome_settled_in_view(ledger, migration, adopting)` returning True when
  `migration.predecessor_id` is empty, when `MigrationRegistry.get_by_id(...)` cannot resolve it
  (D4: keep the record's word), or when the predecessor is settled in view
  (`migration_settled(ledger, predecessor) or predecessor_id in adopting`);
- make `_settled_in_view` = (recorded success or pending adoption settles it) **and**
  `_predecessor_outcome_settled_in_view(...)`;
- add the public `predecessor_outcome_settled(project_path, migration)` that mirrors
  `settled_in_selection_view` (same `legacy_upgrade_scope`, same `pending_adoption_ids` projection),
  so a dry run and a live run agree on a pre-ledger project;
- update the docstrings of `get_applicable`, `_settled_in_view`, `settled_in_selection_view` and
  `migration_settled` where they state the success-only rule, so the retry rule is named once.

The successor's own record must no longer settle it on its own: that is the bug. Do not change
`migration_settled` itself — it stays the success-only "recorded applied" predicate; the new
conjunct belongs to the selection view.

### T004 — declare the predecessor on the two re-implemented successors

Add `predecessor_id = PREDECESSOR_ID` beside `migration_id` in
`m_2_0_6_residue_safe_consistency_sweep.py` and `m_3_1_1_residue_safe_normalize_status_json.py`.
Confirm the 0.9.0/0.9.1 successors already inherit the declaration from
`ResidueSafeLaneSuccessorMixin`; if the mixin's declaration became redundant, leave it alone rather
than editing more than necessary.

### T005 — remove the strict xfail

Delete the `pytest.mark.xfail(strict=True, ...)` from
`test_c006_an_unsettled_predecessor_record_still_lets_the_successor_run` and keep its docstring,
updating it to say the case is now a passing pin. Both parameters must pass.

### T006 — runner-level retry coverage

In the new file `tests/specify_cli/upgrade/test_successor_retry_6688.py` (module docstring: the
`C-006` retry, #6688), parametrize over `PAIRS` (import them or restate them with ids) and over
`("failed", "skipped")`:

- build a plain project, `_dirty_mission`, `_pre_ledger(project, "3.2.0", {old: recorded})`;
- assert the successor is in `_selected(project, "3.2.0", "3.2.0")` and unsettled in the selection
  view;
- run `MigrationRunner(project).upgrade("4.0.0rc8", include_worktrees=False)` (use the
  `quiet_runtime_assets` fixture for the 2.0.6 pair);
- assert `result.success`, the successor in `result.migrations_applied`, a non-empty
  `changes_made`, and that the Mission was repaired (for 0.9.x the `tasks/doing` folder is gone, for
  3.1.1 `materialized_at` is empty, for 2.0.6 the Mission's `meta.json` exists).

Keep the fixtures as close to the existing #6680 suite as you can; prefer importing its helpers
instead of copying them if the import is clean (the module has no side effects at import).

### T007 — never replay a completed repair

On the same fixture, after a successful run: snapshot `kitty-specs/`, run `upgrade` again, and
assert `result.success`, the successor **not** in `result.migrations_applied`,
`result.migration_results[new].changes_made == []`, and the snapshot unchanged. This is the
"never re-run something that genuinely completed" half of the rule; it must fail if `detect()` is
bypassed (do not weaken it by asserting only on the outcome).

### T008 — non-vacuity controls

- A migration with no `predecessor_id` (an ordinary registered migration) is unaffected: its
  `reselect_when_recorded(project)` is False on a project where it is recorded, and the selection
  view still reports it settled.
- A successor whose predecessor recorded `success` keeps the #6680 behaviour: settled in view,
  `detect()` False, not applied by a live run, tree unchanged (the existing
  `test_a_settled_predecessor_makes_the_successor_inert` and dry-run/live tests already cover part
  of this — add only what is missing, and keep those tests unmodified).

## Test Strategy

```bash
uv run pytest tests/specify_cli/upgrade/test_residue_safe_successors_6669.py \
  tests/specify_cli/upgrade/test_successor_retry_6688.py -q
uv run pytest tests/specify_cli/upgrade/test_residue_successor_plumbing_6669.py \
  tests/specify_cli/upgrade/test_registry_runs_first.py \
  tests/specify_cli/upgrade/test_migrate_ledger_cmd.py -q
uv run pytest tests/architectural/test_migration_order_manifest.py \
  tests/architectural/test_migration_chain_integrity.py -q
```

`uv run ruff check <changed files>` and `uv run mypy <changed source files>` must be clean. Do not
run a full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION); CI owns the rest.

## Definition of Done

- [ ] T001 red captured; T005's test passes without `xfail`.
- [ ] The retry rule lives once (registry) and is reused by `reselect_when_recorded`; no second copy.
- [ ] All four pairs retry on `failed` and `skipped`, and none replays a completed repair.
- [ ] `git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'` shows
      only the two successor modules (one classvar each).
- [ ] No change to `order_manifest.txt`, `target_version`, ledger schema or the frozen backfill.
- [ ] Ruff/mypy clean on the changed files; the scoped suites green.

## Risks

- **Half-fix stays green**: fixing only `reselect_when_recorded` leaves
  `settled_in_selection_view(project, successor)` True and T005's second assertion red; fixing only
  the registry leaves the runner skipping at apply time. Verify both halves separately.
- **Over-wide rule**: any migration with an accidental `predecessor_id` re-selects forever. T008
  and the empty-id guard contain it.
- **Perf**: no ledger read for migrations without a predecessor (NFR-001).

## Reviewer Guidance

- Is "settled" answered by one predicate, and does the runner's gate reach it?
- Does any path still let the successor's own baseline record settle it?
- Does `detect()` remain the only thing that can trigger `apply()`?
- Are the successor modules' only diffs the classvar (and, if needed, its docstring)?
