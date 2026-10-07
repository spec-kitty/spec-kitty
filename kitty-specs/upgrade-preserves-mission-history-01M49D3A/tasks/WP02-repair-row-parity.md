---
work_package_id: WP02
title: Repair keeps writer-shaped history byte-identical
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-008
- NFR-003
- SC-002
- C-002
planning_base_branch: issue-5811-upgrade-preserves-mission-history
merge_target_branch: issue-5811-upgrade-preserves-mission-history
branch_strategy: Planning artifacts for this mission were generated on issue-5811-upgrade-preserves-mission-history. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5811-upgrade-preserves-mission-history unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-preserves-mission-history-01M49D3A
base_commit: b2ec92a2f095361c6727673847d994e502c713c9
created_at: '2026-10-07T04:57:00.179663+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Fixes
history:
- at: '2026-10-07T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/migration/
create_intent:
- tests/migration/test_repair_row_parity_5811.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/migration/mission_state.py
- src/specify_cli/status/store.py
- tests/integration/migration/fixtures/**
- tests/integration/migration/test_mission_state_repair_fidelity_e2e.py
- tests/migration/test_mission_state_repair.py
- tests/migration/test_repair_row_parity_5811.py
- tests/status/test_authoritative_non_lane_registry_4897.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02: Repair keeps writer-shaped history byte-identical

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter, and follow its guidance before reading the rest of this prompt. If the skill is not available, run `.venv/bin/spec-kitty agent profile show python-pedro` and apply the resolved profile.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ Review Feedback

If this WP came back from review, read the `review_ref` in the event log first (`.venv/bin/spec-kitty agent tasks status --mission 01M49D3A`). Every feedback item is part of your work.

## Objective

Make the mission-state repair (`repair_repo`, used by `spec-kitty doctor mission-state --fix`) a byte-identical no-op on history written by the current status writer:
- lane rows round-trip through `StatusEvent` and the store's own serializer;
- no row is re-ordered;
- `status.json` and `lanes.json` are written only when the Mission's log changed and the file is tracked;
- the outcome names every errored Mission.

Spec references: FR-003, FR-004, FR-005, FR-007 (data side), FR-008, NFR-002, NFR-003.

## Branch Strategy

- Planning base and final merge target: `issue-5811-upgrade-preserves-mission-history`.
- Worktrees are per lane from `lanes.json`. Prepare with `.venv/bin/spec-kitty agent action implement WP02 --agent claude`; it bases on WP01's lane.

## Seam Map (brownfield scout, at base `1fb084d7f2`; re-check line numbers)

`src/specify_cli/migration/mission_state.py`:

| Function | Lines | Notes |
|---|---|---|
| `_rebuild_lanes_if_wedged` | 1550–1674 | |
| `_repair_mission` | 1675–1859 | **complexity 15, at the ceiling** |
| `_canonicalize_status_rows` | 1916–2014 | complexity 6 |
| `_row_sort_key` | 2015–2044 | |
| `_rule_strip_legacy_keys` | ~2284 | |
| `_build_canonical_row` | 2395–2422 | the second-authority allowlist; already calls `StatusEvent.from_dict` at ~2448, only to validate |
| `_canonicalize_status_row` | 2476–2516 | |

Inside these functions:
- **Serialization** (~1988): `json.dumps(result.row, sort_keys=True)`. "Changed" is `new_text != row.text.strip() or actions` (1989).
- **Sort** (~2001): `sorted(canonical_rows, key=_row_sort_key)`.
- **Change detection** in `_repair_mission`: meta 1716, status file 1777, events 1780, quarantine 1794, `status.json` 1799–1803 (`materialize_to_json`, compare, `atomic_write`), lanes 1810–1825.

`src/specify_cli/status/store.py`:
- Lines 301 and 385 use `json.dumps(sanitize_event_for_log(...), sort_keys=True)`, with default separators and `ensure_ascii=True`.

The allowlist drifts from `StatusEvent.to_dict()` (`status/models.py` ~366–390) in three ways:
1. It emits null `reason_source`, `review_result` and `mission_id`.
2. It flattens a structured `actor` with `str(...)`.
3. It overwrites `mission_id` unconditionally.

## Subtasks

### T005: Campsite extraction, behaviour-preserving (do first, separate commit)

Charter Standing Order #2 (tidy first): before the functional change, extract helpers from `_repair_mission` so that it drops well below 15. Candidates are the meta step, the status-log step, the quarantine step, the derived-file step and the lanes step. Behaviour must not change. Run the existing repair suites green before and after:
- `tests/migration/test_mission_state_repair.py`
- `tests/integration/migration/`
- `tests/unit/migration/test_mission_state_lanes_rebuild.py`
- `tests/migration/test_dup_key_repair.py` (locate it with `grep -rl test_dup_key tests/`)

Commit message: `refactor(migration): extract _repair_mission phases (tidy-first, #5811)`.

### T006: One public row-to-line function in `status/store.py`

1. Add `serialize_event_line(event_dict: dict[str, Any]) -> str` to `status/store.py`. It returns `json.dumps(sanitize_event_for_log(event_dict), sort_keys=True)`, the exact expression the store uses today. Use the name if it is free; otherwise pick a clear one.
2. Make both store call sites (301 and 385) use it, so the store and the repair cannot diverge.
3. Add a focused unit test only if the existing store tests do not already pin the line format. Check `tests/status/` first, and do not duplicate.

### T007: Lane rows round-trip; delete the allowlist; byte-preserve non-lane rows

1. In `_canonicalize_status_rows` / `_canonicalize_status_row`, classify each row (see `data-model.md`):
   - **Preserved non-lane rows**: `event_type` in `status.AUTHORITATIVE_NON_LANE_EVENT_TYPES`, `_is_preserved_non_lane_row`, or the `_rule_reject_non_status_event` path. Emit the **original line text unchanged**.
   - **Annotation rows** (`kind == "annotation"`): original text unchanged.
   - **Lane rows**: apply the existing alias and legacy-strip rules (`_rule_strip_legacy_keys`, lane alias), then `StatusEvent.from_dict(row).to_dict()`, then `serialize_event_line(...)`.
2. Delete `_build_canonical_row`'s hand-written allowlist. It and its sibling rules do these things that `to_dict` does not. Decide each one explicitly, as a named rule before the round trip or as a deliberate drop, and list the decisions in the hand-off note:
   - `wp_id` None → `""`;
   - `str()` coercion of `event_id`, `mission_slug`, `from_lane`, `to_lane`, `at`, `execution_mode`;
   - `bool(force)`;
   - `str(actor)`: **drop it**. Structured actors are preserved through `from_dict`/`decode_actor`.
   - unconditional `mission_id`: see step 2a;
   - **`removed_field:<k>` manifest actions for unknown keys.** These must survive, computed by comparing the input row's keys with the `to_dict` output's keys.

   Add one legacy test with a non-str `at` and a non-bool `force`.
2a. `_rule_stamp_identity` (~:2297) sets `mission_id = ctx.mission_id` unconditionally. For rows that are already writer-shaped, it must neither add a `mission_id` key the row lacks nor overwrite one it has. Any backfill of a legacy row's identity becomes its own named rule with its own manifest action, applied only to rows that are not writer-shaped (for example rows carrying `feature_slug`). Without this, the T010 subsets without `mission_id` go red.
3. **Change detection**: a row is unchanged when the new line equals the original line text. For writer-shaped input this must hold exactly.
4. Check explicitly that `StatusEvent.from_dict` accepts a row that still carries legacy keys such as `feature_slug` after the strip rule runs. If it does not, the strip rule must run first; it does.
5. Keep `test_canonical_row_allowlist_covers_every_status_event_field` meaningful. If it tests the deleted allowlist, re-pin it to assert that the round trip preserves every `StatusEvent` field, rather than deleting it (judge the test, don't green-wash).

### T008: Remove the re-sort

1. Remove `sorted(canonical_rows, key=_row_sort_key)`. Write rows in their original physical order, with dedup and quarantine removals applied in place. Delete `_row_sort_key` if nothing else uses it (grep).
2. Prove that lane state is unchanged: in the new parity test file, take a log whose physical order differs from `(at, event_id)`, run `status.reducer.materialize` (or `reduce`) before and after the repair, and assert equal snapshots and identical bytes.
3. `tests/status/test_authoritative_non_lane_registry_4897.py` carries a sort rationale (the `timestamp` sort key). Re-pin it to the order-preservation contract; do not delete its non-lane coverage.

### T009: Derived files only when the log changed and the file is tracked

1. In the derived-file step extracted in T005, write `status.json` only when this repair changed the Mission's event log. When the log did not change but `status.json` differs from a fresh materialization, record a drift finding or report entry instead of writing (reuse the repair's existing report/manifest structure).
2. Never **create** `status.json` or `lanes.json` when the Mission did not already have it: absent on disk, or untracked in git. Use `kernel.git.listing.is_tracked(cwd, path)` (`src/kernel/git/listing.py:457`; it raises `GitCommandError` on other git failures, so let that propagate or translate it, never swallow). A coord-topology Mission whose primary checkout has neither file must stay clean.
3. `_rebuild_lanes_if_wedged` must only rewrite an existing tracked `lanes.json`.
4. Focused tests in the parity test file:
   - snapshot drift without a log change leaves the file untouched and reports the drift;
   - no `lanes.json` or `status.json` is created when absent;
   - a changed log still rewrites `status.json` (positive control).

### T010: Field-list-driven parity test; re-pin fixtures

**File**: `tests/migration/test_repair_row_parity_5811.py` (new)
1. Generate `StatusEvent` instances from `dataclasses.fields(StatusEvent)`: one base valid instance plus every subset of the optional fields populated (at least `reason_source`, `review_result` built as a full `ReviewResult`, `mission_id`, `evidence`, `review_ref`, a structured `actor`, and `policy_metadata` with nested and non-ASCII values, to pin `ensure_ascii` and key order). Serialize each through the writer path (`serialize_event_line(event.to_dict())`), feed the lines through the repair's canonicalization, and assert byte equality per line.
2. Add one test per byte-preserved class: a non-lane row and an annotation row stay verbatim.
3. Add one legacy-row test: a row carrying `feature_slug` or an alias lane (`doing`) is still normalized (positive control for FR-008).
4. Re-pin `tests/integration/migration/fixtures/12_canonical_row.json` and any other fixture that pins `"reason_source": null` or the sorted order to the writer shape. Re-pin in `test_mission_state_repair_fidelity_e2e.py` and `tests/migration/test_mission_state_repair.py` where they assert the old shape or sorting. For each changed assertion, add a one-line commit-message note on why it was stale.

### T011: The repair outcome names errored Missions

1. In the outcome object `repair_repo` returns (find it; it carries `updated` / `unchanged` / `errors`), add a field listing each errored Mission with its first error reason, for example `errored_missions: list[tuple[str, str]]`, typed. Errors are collected at about line 1951.
2. Characterize the `errors=52` class. With the fix in place, run `.venv/bin/spec-kitty doctor mission-state --json` (audit only, no `--fix`) on this repository's own corpus, read-only, and group the error reasons. Record the result in your hand-off note only; do not edit the tracer files. If the errors are preserved non-lane shapes the classifier missed, fix the classifier so they are byte-preserved, not errors. **Never run `--fix` on the real repository.**
3. `_mission_state_doctor.py:298-307` already prints each errored Mission's `validation_errors`. If your field adds nothing beyond that, do not add it; keep `validation_errors` as the single source. Either way, the doctor's non-zero exit and no-"cleared" guarantee are WP04's job. Report the field you settled on in the hand-off note.

## Constraints

- Complexity at most 15 for every touched function. Ruff, `ruff format --force-exclude` and mypy clean, with no suppressions.
- Mission terminology only.
- Do not touch `upgrade.py` or the gate (WP04), or `_select_mission_dirs` (WP03).
- Test economy: only the tests named above, plus re-pins of tests that pinned the defect.

## Tests to Run

```bash
.venv/bin/python -m pytest tests/migration/ tests/integration/migration/ tests/unit/migration/ tests/status/ -q
SPEC_KITTY_RUN_P0_REPRO=1 .venv/bin/python -m pytest tests/integration/migration/test_residue_dir_not_mission_5812.py -q   # may stay red until WP03
make test-fast
.venv/bin/ruff check src/specify_cli/migration/mission_state.py src/specify_cli/status/store.py tests/migration/test_repair_row_parity_5811.py
```

The #5811 repro is fixed by WP04 (the upgrade stops repairing). Additionally run it with `doctor mission-state --fix` semantics in mind; your parity work is what makes the doctor path safe.

## Definition of Done

- The writer-shaped parity test is green for every optional-field subset.
- No re-sort; the order-preservation and lane-state-equality tests are green.
- The derived-file guard tests are green.
- The repair suites are green, with stale pins re-pinned and justified.
- `errored_missions` is in the outcome, and the `errors=52` class is characterized.
- The campsite commit is separate and behaviour-preserving.

## Reviewer Guidance

- Verify that the allowlist is gone. A second hand-written key list is a regression of the single-authority principle.
- Verify that non-lane and annotation rows are emitted from the original text, not re-serialized.
- Verify that `is_tracked` errors are not swallowed.
