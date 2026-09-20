---
work_package_id: WP04
title: Integration verification + CHANGELOG
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- NFR-001
- NFR-003
planning_base_branch: fix/doctor-mission-state-repair-fidelity
merge_target_branch: fix/doctor-mission-state-repair-fidelity
branch_strategy: Planning artifacts for this mission were generated on fix/doctor-mission-state-repair-fidelity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/doctor-mission-state-repair-fidelity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-doctor-mission-state-repair-fidelity-01M2YGV8
base_commit: d2e0d58f7b861c773b88c9b02e1214b72fe451f5
created_at: '2026-09-20T06:29:31.253867+00:00'
subtasks:
- T018
- T019
- T020
phase: Phase 3 - Integration
history:
- at: '2026-09-20T05:01:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/integration/migration/
create_intent:
- tests/integration/migration/test_mission_state_repair_fidelity_e2e.py
execution_mode: code_change
model: ''
owned_files:
- CHANGELOG.md
- tests/integration/migration/test_mission_state_repair_fidelity_e2e.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Integration verification + CHANGELOG

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Capstone: prove the whole seam end-to-end and record the change.

Done when:
- An e2e test over a seeded fixture (a repo with a legacy-`change_mode` mission + a genuinely audit-blocking mission) proves: `--fix` repairs the legacy one (SC-001), terminal/`--json` name every affected mission with no gitignored read (SC-002/003), `--audit`/`--fix` agree (SC-004), rerun is idempotent (SC-005), and the dry-run STILL refuses the audit-blocking mission (exit 1). This is the cross-lane integration gate (catches defects per-WP reviews miss).
- Blast-radius suite green; `tests/architectural/` run in full only if a new-symbol/gate red appears; any red classified per the baseline-red gotcha.
- `CHANGELOG.md` `[Unreleased]` gains a Fixed entry citing #4778/#4780/#4779 — **no version bump** (a version bump trips the release-readiness triple-source gate).

## Context & Constraints

- Depends on WP01+WP02+WP03 all merged into this lane's base. Verify the shared helpers each WP introduced are actually wired (integration gate has historically caught dead-shared-helper + ruff-exclude-ratchet defects).
- Blast radius (record commands + pass/fail counts in the PR *Tests run* section):
  `tests/specify_cli tests/unit/migration tests/integration/migration tests/cli/commands tests/audit tests/status` + `make test-fast`.
- CHANGELOG: append under the existing `[Unreleased]` heading; do NOT add a new `## [X.Y.Z]` version heading and do NOT touch `pyproject.toml`/`uv.lock`/`.kittify/metadata.yaml` (release gate).

## Subtasks

### T018 — e2e integration test
Create `tests/integration/migration/test_mission_state_repair_fidelity_e2e.py` (pytestmark). Seed a temp repo with (a) a mission `change_mode: regular`, (b) a mission with a genuinely audit-blocking shape. Assert SC-001..006 end-to-end incl. the dry-run still refuses (b) with exit 1.

### T019 — Blast-radius run + classification
Run the blast-radius suite + `make test-fast`. If any `tests/architectural/` gate fires (dead-symbol, golden-count, inline-meta floor, ruff-format), address at root; classify any unrelated red per the baseline-red gotcha (do not green-wash pre-existing P0 reds). Record commands + counts.

### T020 — CHANGELOG entry
Add a `[Unreleased]` → Fixed entry: "doctor mission-state now repairs legacy `change_mode` instead of aborting, and reports per-mission detail in terminal/`--json` (dry-run parity); aligned the bulk-edit-gate reader (#4778, #4780, #4779)." No version bump.

## Branch Strategy
- Planning base / merge target: `fix/doctor-mission-state-repair-fidelity` (final PR → `main`). Capstone lane; worktree per `lanes.json`.

## Definition of Done
- T018–T020 green; blast-radius recorded; CHANGELOG updated with no version bump; ruff/mypy clean.

## Reviewer guidance
- Confirm the e2e asserts BOTH the repair AND the preserved dry-run refusal (the additive-only guarantee). Confirm no version-bump files touched. Confirm shared helpers from WP01–03 are genuinely wired (no reimplementation).
