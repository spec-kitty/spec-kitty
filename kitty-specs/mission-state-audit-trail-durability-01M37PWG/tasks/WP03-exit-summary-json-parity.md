---
work_package_id: WP03
title: Write-only operator exit summary + --json parity
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- NFR-004
planning_base_branch: fix/mission-state-audit-trail-durability
merge_target_branch: fix/mission-state-audit-trail-durability
branch_strategy: Planning artifacts for this mission were generated on fix/mission-state-audit-trail-durability. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/mission-state-audit-trail-durability unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
phase: Phase 2 - Visibility
history:
- timestamp: '2026-09-23T18:10:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
mission_id: 01M37PWGWRFNZY8X2Y7P7KJJGK
owned_files:
- src/specify_cli/cli/commands/doctor.py
- src/specify_cli/cli/commands/_mission_state_doctor.py
- tests/cli/commands/test_doctor_mission_state.py
role: implementer
tags: []
tracker_refs: []
wp_code: WP03
---

## ⚡ Do This First: Load Agent Profile

Load `/ad-hoc-profile-load implementer-ivan` and apply its initialization/boundaries/directives first. State which you applied.

# Work Package Prompt: WP03 — Write-only operator exit summary + `--json` parity

## Objective

On `doctor mission-state --fix` completion, tell the operator where the audit trail went and that it is tracked-but-uncommitted, and instruct them to commit it — realizing the "visibility" half of the decision. Add `--json` field parity. `--fix` performs **no git operation** (write-only; the operator commits).

## Context & Constraints

- Read `../contracts/audit-trail-contract.md` — it is the authoritative output contract.
- The audit paths + `quarantined_rows` come from the `RepairReport` fields WP01 added; this WP renders them. Do NOT change where artifacts are written (WP01) or the churn classification (WP02).
- Rendering lives in `cli/commands/doctor.py` and/or `cli/commands/_mission_state_doctor.py` (the `--fix` command surface + its `--json` serializer).

## Subtasks

### T009 — Human exit summary (always manifest; conditional quarantine)
After the existing `Mission-state repair complete (…)` line, print:
- Always: `Audit trail written to <audit_manifest_path> (tracked, uncommitted).` + `Commit it to preserve the record of this repair.`
- When `quarantined_rows > 0`: `<N> row(s) quarantined verbatim to <audit_quarantine_path>.` + `Commit the audit trail before running 'git clean'.`
Paths are repo-relative. No path printed may be git-ignored (WP04's e2e asserts this).

### T010 — `--json` field parity
Add to the `--fix --json` object: `audit_manifest_path` (always), `audit_quarantine_path` (non-null iff `quarantined_rows > 0`, else `null` — document the choice), `quarantined_rows`. Additive only; do not change existing fields. Ensure the count equals the human summary's (parity).

### T011 — Tests: update old-path literals + parity
In `tests/cli/commands/test_doctor_mission_state.py`: the test-set `report.manifest_path = ".kittify/migrations/mission-state/…"` literals (`:283,:376,:446`) move to the audit root. Add a parity test: a quarantining run's human summary names manifest+quarantine+count+commit-instruction and its `--json` carries the same paths/count; a zero-quarantine run names the manifest and omits/nulls the quarantine path.

## Definition of Done
- Human summary + `--json` match the contract, with parity; write-only (no git mutation) preserved.
- `ruff`/`mypy` clean; `test_doctor_mission_state.py` green.

## Reviewer guidance
Confirm no git add/commit is introduced. Confirm the quarantine line/field appears iff `quarantined_rows > 0`. Confirm parity between human and JSON.
