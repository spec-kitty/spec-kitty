---
work_package_id: WP03
title: S8264/S8233 least-privilege permissions + ci-aggregate install pins
dependencies: []
requirement_refs:
- FR-003
- FR-004
- NFR-001
- NFR-003
planning_base_branch: fix/ghactions-sonar-hardening
merge_target_branch: fix/ghactions-sonar-hardening
branch_strategy: Planning artifacts for this mission were generated on fix/ghactions-sonar-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ghactions-sonar-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ghactions-sonar-hardening-01M2FYX1
base_commit: 01845da093c7c8954b4c0b7ed7aaa3ba6045d000
created_at: '2026-09-14T12:56:17.286832+00:00'
subtasks:
- T005
- T006
history:
- created by /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/ci-aggregate.yml
- .github/workflows/ci-fleet-verdict.yml
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load your profile: `spec-kitty agent profile show implementer-ivan`.

## Objective
Relocate the S8264/S8233 workflow-level permissions to their needing jobs in `ci-aggregate.yml`
and `ci-fleet-verdict.yml` (FR-003, C-003), and pin ci-aggregate's bare 3rd-party installs
(pyyaml, diff-cover, defusedxml) with exact versions + `--only-binary :all:` (FR-004). NOT the
`uv sync --frozen` self-install (C-004). Behavior-identical (NFR-001).

## Guidance per subtask
### T005 — Least-privilege permissions (C-003)
- Enumerate EVERY job in each file and what token scope it uses BEFORE moving anything.
- Move the workflow-level `permissions:` block down to each job that needs it; a job that needs no elevated scope gets `permissions: {}` or the minimal read it uses. Never drop a scope a job relies on.
### T006 — ci-aggregate install pins + validate
- `pip install --only-binary :all: pyyaml==6.0.2` at the flagged line (S8541/S8544 combined — the currently-bare `pip install pyyaml`).
- `uv pip install --only-binary :all: diff-cover==10.3.0 defusedxml==0.7.1` at the flagged line.
- Leave `uv sync --frozen` untouched (C-004); if Sonar flags it here, it goes to the WP05 dossier.
- Validate: actionlint / YAML parse clean on both files.

## Branch Strategy
Base + merge target `fix/ghactions-sonar-hardening`; enter the lane workspace from lanes.json.

## Definition of Done
- ci-aggregate + ci-fleet-verdict permissions at job scope, no job de-privileged (FR-003/C-003); ci-aggregate 3rd-party installs pinned (FR-004); uv-sync untouched (C-004); YAML valid; behavior-identical.

## Risks / reviewer guidance
- **Reviewer**: permission relocation is fail-dangerous — confirm every job that used a scope still has it. Confirm no `--only-binary`/`--no-build` landed on any `uv sync`.
