---
work_package_id: WP03
title: Prove the architectural gates stay green honestly
dependencies:
- WP01
- WP02
requirement_refs:
- FR-005
- C-002
- SC-003
planning_base_branch: issue-6095-dead-compat-repair
merge_target_branch: issue-6095-dead-compat-repair
branch_strategy: Planning artifacts for this mission were generated on issue-6095-dead-compat-repair. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6095-dead-compat-repair unless the human explicitly redirects the landing branch.
base_branch: issue-6095-dead-compat-repair
base_commit: cb780be8770a4775f16b2e490b251705a8afb0b5
created_at: '2026-10-12T17:45:05Z'
subtasks:
- T009
- T010
phase: Phase 3 - Gates green honestly
history: []
agent_profile: python-pedro
authoritative_surface: tests/architectural/_baselines.yaml
create_intent: []
execution_mode: code_change
owned_files:
- tests/architectural/_baselines.yaml
role: implementer
tags: []
tracker_refs: []
---

# WP03 — Prove the gates stay green honestly

Run `tests/architectural/test_no_dead_symbols.py` and `test_no_dead_modules.py` by name.
Re-point `_baselines.yaml` or any other implicated gate honestly (shrink only; no loosening;
no new allowlist entry; no new size/ratchet gate — C-002). Run `make test-fast`. Record all
commands + counts.
