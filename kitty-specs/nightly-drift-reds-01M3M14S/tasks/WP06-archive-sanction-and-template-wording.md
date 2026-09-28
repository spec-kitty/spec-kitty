---
work_package_id: WP06
title: Archive sanction and template wording
dependencies: []
requirement_refs:
- FR-006
- FR-008
planning_base_branch: issue-5258-nightly-drift-reds
merge_target_branch: issue-5258-nightly-drift-reds
branch_strategy: Planning artifacts for this mission were generated on issue-5258-nightly-drift-reds. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5258-nightly-drift-reds unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-drift-reds-01M3M14S
base_commit: d1aacecd12c3a0306e29646f11d1d72c4f6cf978
created_at: '2026-09-28T14:01:56.841964+00:00'
subtasks:
- T018
- T019
phase: Phase 1 - Drift remediation
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/architectural/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_archive_root_byte_identical.py
- src/specify_cli/missions/documentation/templates/task-prompt-template.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP06 – Archive sanction and template wording

## ⚡ Do This First: Load Agent Profile

Load the `implementer-ivan` profile (`/ad-hoc-profile-load`) and behave according to its guidance before parsing the rest of this prompt.

## Context & Constraints

- Spec verdict table: `kitty-specs/nightly-drift-reds-01M3M14S/spec.md` (R1–R23). The charter binds you: `.kittify/charter/charter.md` (DIRECTIVE_041: stale → re-pin, stub → delete, valid → fix the product; never skip, xfail, quarantine or retry-to-green).
- Sibling-owned paths (never edit): `src/specify_cli/consolidation/**`, `tests/integration/**`, `.github/workflows/ci-nightly.yml`, `scripts/ci/nightly_escalation.py`, `tests/charter/test_consistency_check.py`.
- NO_FULL_HEAVY_SUITES_IN_MISSION: run only the files listed under Validation.
- Every re-pin comment names the causing commit sha. New code passes `ruff check`, `ruff format --check`, and complexity ≤15.

## Branch Strategy

- **Strategy**: single_branch (lane-less) on `issue-5258-nightly-drift-reds`
- **Planning base branch**: issue-5258-nightly-drift-reds
- **Merge target branch**: issue-5258-nightly-drift-reds (PR → `main`)

## Objectives & Success Criteria

- **R9 prerequisite:** add dated `_OPERATOR_SANCTIONED_CORRECTIONS` entries for the 4 files the dogfood cutover rewrites. Follow the #4972/#4957 entry format exactly.
  - Files: `kitty-specs/doctrine-org-init-from-template-01KXNA6P/{meta.json,status.events.jsonl}` and `kitty-specs/org-init-template-security-remediation-01KY4S90/{meta.json,status.events.jsonl}`.
  - Rationale: operator sanction by stijn-dejongh, 2026-09-28, mission nightly-drift-reds-01M3M14S / #5258. Both missions were born pre-birth-cutover-seam on a long-lived branch.
  - The entry must say it is removed once the corrected bytes are in main's baseline.
- **FR-008:** in the src documentation template, change `For large features` to `For large missions`, matching the canon at packs/built-in/.../task-prompt-template.md:163. Full fork retirement is #5280.

## Validation

- `tests/architectural/test_archive_root_byte_identical.py`, which goes green only together with WP07.
- `tests/cross_cutting/misc/test_template_compliance.py`.
- `grep -rn "large features" src packs` returns 0 hits.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
