---
work_package_id: WP04
title: 'Track B fix: restore merged_at writer + reopen-aware guard (#4090)'
dependencies:
- WP03
requirement_refs:
- C-001
- C-003
- FR-004
- FR-005
- FR-006
- NFR-002
planning_base_branch: issue-3942-merge-surface-authority
merge_target_branch: issue-3942-merge-surface-authority
branch_strategy: Planning artifacts for this mission were generated on issue-3942-merge-surface-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3942-merge-surface-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-post-merge-partition-integrity-01M2FQ80
base_commit: ccb1635af4bca4e10d03197e269ae992a1946e1c
created_at: '2026-09-14T11:21:52.807514+00:00'
subtasks:
- T009
- T010
- T011
history:
- created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/baseline.py
create_intent:
- tests/specify_cli/status/test_merged_at_writer_and_reopen_4090.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/merge/baseline.py
- src/specify_cli/status/lifecycle.py
- tests/specify_cli/status/test_merged_at_writer_and_reopen_4090.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Track B fix: restore merged_at writer + reopen-aware guard (#4090)

## ⚡ Do This First: Load Agent Profile

- **Profile**: `python-pedro` (implementer feasibility / TDD)
- **Role**: `implementer`

---

## Objectives & Success Criteria

Write the post-merge authority marker `merged_at` at merge completion AND make `is_mission_merged` reopen-aware, so retrospect ≡ doctor for a merged mission — and a **reopened** mission is correctly NOT treated as merged.

- SC: WP03's red-first test passes (remove its xfail-strict — documented out-of-map one-liner).
- SC: a merged mission's `meta.json` gains `merged_at` (datetime) and `is_mission_merged(feature_dir)` returns True.
- SC: a reopened mission (later `MissionReopened`) returns `is_mission_merged` False.
- SC: `runtime_bridge.py` :1600 terminal short-circuit fires for a merged (marker-present) mission; `tests/specify_cli/status/test_lifecycle.py` stays green.

## Context & Constraints (locked design — D-B1 RE-LOCKED, coupled change)

- **Writer home**: restore the `merged_at` (+`merged_commit`) write as a sibling of `record_baseline_merge_commit` in the meta-write authority `merge/baseline.py`, on the same executor finalize path (`_phase_capture_and_baseline`, call site `executor.py:951`) so it lands in the same bookkeeping commit and flows through the driver's `_TARGET_AUTHORITATIVE_META_FIELDS` (already declared at `merge_driver.py:84-95`). **Do NOT put the write in `done_bookkeeping.py`** (it writes nothing to meta.json — boundary leak). **Prefer NOT to edit `merge/executor.py`** (owned by WP02): extend the baseline.py function the executor already invokes so no executor edit is needed. If a genuinely new call site is unavoidable, add only a one-line documented out-of-map call and flag it.
- **Do NOT re-point** the guard to `baseline_merge_commit` (modern-only; not cleared on reopen; a SHA) or `mission_number` (permanent; never cleared) — both make a reopened mission read as merged forever, and neither is the datetime the reopen machinery compares.
- **Reopen-awareness (mandatory)**: nothing today clears `merged_at` on reopen and `is_mission_merged` (`lifecycle.py:302`) is presence-only. Restoring the writer would make a reopened mission wrongly read as merged across THREE consumers (`surface_resolver.py:745`, `runtime_bridge.py:1600`, `is_mission_completed`). Fix by making `is_mission_merged` reopen-aware via the adjacent `_last_reopen_at` machinery (merged iff `merged_at` present AND no later `MissionReopened`) — event-sourced, no meta-clearer. Keep `_last_merge_marker_at` returning a datetime for `_is_reopened`.
- **D-B3**: keep `resolve_status_surface` as the single reader; you only make the signal it consumes written + reopen-correct.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

## Subtasks & Detailed Guidance

### Subtask T009 – Restore the merged_at writer
- **Steps**: In `merge/baseline.py`, write `merged_at` (UTC datetime, ISO) and `merged_commit` onto the primary `meta.json` in the same function/flow that records `baseline_merge_commit`. Confirm it lands on the target and folds into the existing bookkeeping commit + post-commit durability path.

### Subtask T010 – Reopen-aware is_mission_merged
- **Steps**: In `status/lifecycle.py`, make `is_mission_merged` return True only if `merged_at` present AND there is no later `MissionReopened` (use `_last_reopen_at` vs `_last_merge_marker_at`). Do not add a meta-mutating clearer. Verify the docstring claims (IC-02) now match behavior.

### Subtask T011 – Focused tests
- **Steps**: New `tests/specify_cli/status/test_merged_at_writer_and_reopen_4090.py`:
  1. writer unit test (call the baseline write on a temp feature_dir → `merged_at` present, `is_mission_merged` True);
  2. reopened-mission-not-merged (emit `MissionReopened` after → `is_mission_merged` False);
  3. runtime-bridge terminal short-circuit for a merged mission (`runtime_bridge.py:1600`).
  Then remove WP03's xfail so `test_retrospect_doctor_surface_4090.py` passes (retrospect ≡ doctor). Keep `test_lifecycle.py` green.

## Test Strategy

```bash
PWHEADLESS=1 SPEC_KITTY_SYNC_DISABLE=1 PYTHONPATH=$(pwd)/src .venv/bin/python -m pytest \
  tests/specify_cli/status/test_merged_at_writer_and_reopen_4090.py \
  tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py \
  tests/specify_cli/status/test_lifecycle.py \
  tests/runtime/test_bridge_decide_next.py \
  -q -p no:cacheprovider
.venv/bin/ruff check src/specify_cli/merge/baseline.py src/specify_cli/status/lifecycle.py
.venv/bin/ruff format --check src/specify_cli/merge/baseline.py src/specify_cli/status/lifecycle.py
```

## Risks & Mitigations
- **Reopen regression (the big one)**: skipping T010 re-arms three consumers with a non-reopen-aware marker → a reopened mission reads as merged. T010 is NOT optional.
- **Executor ownership**: keep the write inside baseline.py; avoid editing WP02's `executor.py`.
- **Legacy missions**: unlike `baseline_merge_commit` (modern-only), `merged_at` should be written for all merges — verify legacy path also marks.

## Review Guidance
- Confirm the writer is in `merge/baseline.py`, not `done_bookkeeping.py`, and executor.py is untouched (or a single documented one-liner).
- Confirm `is_mission_merged` is reopen-aware and the reopened-not-merged test is non-vacuous.
- Confirm both real readers (retrospect + doctor) now agree.

## Activity Log
- {{TIMESTAMP}} – system – Prompt created.
