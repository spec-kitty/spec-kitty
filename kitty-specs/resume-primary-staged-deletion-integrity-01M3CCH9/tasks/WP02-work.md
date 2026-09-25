---
work_package_id: WP02
title: Merge-strategy no-op adjudication (Defect B)
dependencies:
- WP01
requirement_refs:
- FR-003
- NFR-003
- C-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Defect B (no-op adjudication)
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/terminus/test_merge_noop_adjudication.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/lanes/merge.py
- src/specify_cli/merge/executor.py
- tests/terminus/test_merge_noop_adjudication.py
tags: []
tracker_refs: []
---
# WP02 — Merge-strategy no-op adjudication

A merge-strategy "Already up to date" that would leave the target tree missing approved
content must refuse (non-zero), not stamp WPs `done` / exit 0.

- [ ] T006 New red-first `test_merge_noop_adjudication.py`: merge strategy, mission branch ancestor of target but target tree diverges → `merge --resume --strategy merge` REFUSES (`rc != 0`). Confirm RED first.
- [ ] T007 `_merge_branch_into` MERGE branch: detect the no-op (pre/post target tip unchanged) → `return False` under `allow_noop_squash`, else raise (mirror squash). `already_applied=True` propagates.
- [ ] T008 Rename `_reject_zero_diff_noop_squash` → `_reject_zero_diff_noop_integration` (strategy-neutral) + update call site/tests.
- [ ] T009 Prove T006 green; record C-002 residual in PR body.
