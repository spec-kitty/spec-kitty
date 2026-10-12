---
work_package_id: WP02
title: Prune repair-only tests, keep end-state coverage
dependencies:
- WP01
requirement_refs:
- FR-004
- C-003
- SC-001
- SC-002
planning_base_branch: issue-6095-dead-compat-repair
merge_target_branch: issue-6095-dead-compat-repair
branch_strategy: Planning artifacts for this mission were generated on issue-6095-dead-compat-repair. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6095-dead-compat-repair unless the human explicitly redirects the landing branch.
base_branch: issue-6095-dead-compat-repair
base_commit: cb780be8770a4775f16b2e490b251705a8afb0b5
created_at: '2026-10-12T17:45:05Z'
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Prune repair-only tests
history: []
agent_profile: python-pedro
authoritative_surface: tests/migration/test_birth_cutover.py
create_intent: []
execution_mode: code_change
owned_files:
- tests/migration/test_birth_cutover.py
- tests/unit/migration/test_backfill_runtime_state.py
role: implementer
tags: []
tracker_refs: []
---

# WP02 — Prune repair-only tests, keep end-state coverage

Remove only the repair-exercising assertions/tests. Keep every end-state / lane / slot /
idempotency / cutover-correctness assertion. Leave immutable historical snapshots untouched
(C-003). No test references a removed symbol.

**Validation**: `grep -rn` removed symbols in tests/ → none; `tests/migration/` +
`tests/unit/migration/` pass.
