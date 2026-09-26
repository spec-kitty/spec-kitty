---
work_package_id: WP04
title: Governance ratchets, test migration, durability e2e
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- C-003
- C-005
- FR-010
planning_base_branch: fix/mission-state-audit-trail-durability
merge_target_branch: fix/mission-state-audit-trail-durability
branch_strategy: Planning artifacts for this mission were generated on fix/mission-state-audit-trail-durability. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/mission-state-audit-trail-durability unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
phase: Phase 3 - Governance & Proof
history:
- timestamp: '2026-09-23T18:10:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: reviewer-renata
authoritative_surface: tests/
create_intent:
- tests/integration/migration/test_audit_trail_durability_4928.py
execution_mode: code_change
mission_id: 01M37PWGWRFNZY8X2Y7P7KJJGK
owned_files:
- tests/architectural/test_archive_root_byte_identical.py
- tests/architectural/test_transition_guard_shrink_only.py
- tests/architectural/test_upgrade_recovery_preservation.py
- tests/migration/test_teamspace_migration_rehearsal.py
- tests/integration/migration/test_mission_state_repair_fidelity_e2e.py
- tests/integration/migration/test_audit_trail_durability_4928.py
role: implementer
tags: []
tracker_refs: []
wp_code: WP04
---

## ⚡ Do This First: Load Agent Profile

Load `/ad-hoc-profile-load reviewer-renata` and apply its initialization/boundaries/directives first. State which you applied. (This WP is test-heavy and adversarial — the reviewer lens fits.)

# Work Package Prompt: WP04 — Governance ratchets, test migration, durability e2e

## Objective

Repoint the architectural archive/exclusion ratchets that pin the OLD quarantine root, migrate the remaining tests that assert the old path, confirm the legacy `.kittify/migrations/` ignore stays for back-compat, and add the end-to-end durability guard that proves the mission's success criteria.

## Context & Constraints

- Depends on WP01 (relocation), WP02 (churn classification), WP03 (summary) — the e2e exercises all three.
- Three architectural ratchets pin `.kittify/migrations/mission-state/quarantine/` as an immutable/shrink-only/upgrade-preserved archive (DM-`01M0P6C8C7Q6SPBT412V39RPN0`). Decision recorded in spec FR-010: the relocated, operator-committed trail is **reviewable, NOT DM-immutable** — so repoint the ratchets to the new root only where they must still exclude/scan correctly; do not re-impose immutable-archive status on the tracked trail unless a ratchet genuinely requires it. Record the rationale inline.

## Subtasks

### T012 — Repoint the architectural ratchets
- `tests/architectural/test_archive_root_byte_identical.py:86` (`_ARCHIVE_ROOTS`) and `test_transition_guard_shrink_only.py:120` (`_EXCLUSION_ROOTS`): update the old quarantine path. Decide consciously whether the new root belongs in these roots — default: the new tracked trail is ordinary reviewable content, so it should NOT silently inherit immutable/shrink-only status; ensure the guards don't start flagging committed verbatim quarantine JSONL as violations.
- `test_upgrade_recovery_preservation.py:257`: update the parametrized old quarantine path.

### T013 — Migrate remaining old-path tests + back-compat check
- `tests/migration/test_teamspace_migration_rehearsal.py` (`:143` `_git_diff` hard-codes `.kittify/migrations/mission-state`; `:231-232` quarantine glob): repoint to the audit root.
- `tests/integration/migration/test_mission_state_repair_fidelity_e2e.py`: the "gitignored manifest" premise is reversed — update.
- Add/confirm an assertion that the legacy `.kittify/migrations/` gitignore entry (and the `m_3_2_4` runtime-dirs backfill) is UNCHANGED (C-005 back-compat).

### T014 — NEW durability e2e `test_audit_trail_durability_4928.py`
Create `tests/integration/migration/test_audit_trail_durability_4928.py` (real git repo, isolated HOME/XDG, mirror the #4897/rehearsal fixture: `git init` → config user.email/name → `git add .` → commit baseline). Exercise BOTH writers (mission-state repair + a duplicate-key repair). Assert, non-fakeably:
1. `git check-ignore` reports the written manifest + quarantine as NOT ignored.
2. `git add .kittify/mission-state-audit && git status --porcelain` shows them STAGED (proves `git add` is not a silent no-op — the durability linchpin).
3. After commit + `git clean -xfd`, the artifacts SURVIVE.
4. A `--fix` that writes uncommitted audit artifacts does not gate `spec-kitty accept` (or the record-analysis dirty preflight) — the #2384-via-churn property.
Do NOT copy the old-path literal from the rehearsal helper.

## Definition of Done
- All old-path ratchets/tests repointed; legacy ignore confirmed kept.
- New e2e passes and covers both writers + all four assertions.
- `ruff`/`mypy` clean; the touched architectural tests pass; canonicality suite still green.

## Reviewer guidance
The e2e is the mission's proof — verify assertion #2 (staged, not silently ignored) and #4 (accept not gated) are present and non-fakeable. Verify no ratchet silently re-imposes immutable status on the tracked trail.
