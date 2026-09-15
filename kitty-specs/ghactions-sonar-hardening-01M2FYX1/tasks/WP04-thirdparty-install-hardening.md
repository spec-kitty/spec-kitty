---
work_package_id: WP04
title: 3rd-party install hardening (ci-modules, events-alignment, packs)
dependencies: []
requirement_refs:
- FR-004
- NFR-001
- NFR-003
planning_base_branch: fix/ghactions-sonar-hardening
merge_target_branch: fix/ghactions-sonar-hardening
branch_strategy: Planning artifacts for this mission were generated on fix/ghactions-sonar-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ghactions-sonar-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ghactions-sonar-hardening-01M2FYX1
base_commit: 55f420676150e58d51c2f1941ef9f1841da88581
created_at: '2026-09-14T12:57:19.493628+00:00'
subtasks:
- T007
- T008
history:
- created by /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/ci-modules.yml
- .github/workflows/check-spec-kitty-events-alignment.yml
- .github/workflows/packs.yml
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load your profile: `spec-kitty agent profile show implementer-ivan`.

## Objective
Harden the bare in-scope 3rd-party installs (FR-004): pin pyyaml in `ci-modules.yml`, pin
packaging in `check-spec-kitty-events-alignment.yml`, and pin the claude-code npm tool (S8543) in
`packs.yml`. Do NOT touch `uv sync --frozen` (C-004) or the npm-lifecycle `npm install`
(S6505 — that one legitimately needs its scripts; record in WP05, no edit here). Behavior-identical.

## Guidance per subtask
### T007 — Pin installs
- ci-modules.yml: the bare `pip install pyyaml` → `pip install --only-binary :all: pyyaml==6.0.2`.
- check-spec-kitty-events-alignment.yml: pin the bare `packaging` install to an exact version + `--only-binary :all:`.
- packs.yml: S8543 `npm install -g @anthropic-ai/claude-code` → pin to an exact version `@anthropic-ai/claude-code@<version>`. NOTE this freezes the tool — pin to the version currently in use; do not add `--ignore-scripts` (it needs its lifecycle scripts, S6505 → adjudicate in WP05, no edit).
### T008 — Validate
- actionlint / YAML parse clean on all three files. Confirm no `uv sync --frozen` touched (C-004).

## Branch Strategy
Base + merge target `fix/ghactions-sonar-hardening`; enter the lane workspace from lanes.json.

## Definition of Done
- pyyaml, packaging, claude-code pinned (FR-004); uv-sync + npm-lifecycle untouched (C-004, C-001); YAML valid; behavior-identical.

## Risks / reviewer guidance
- **Reviewer**: confirm pinned versions match what was running (no bump); confirm the npm-lifecycle `npm install` was NOT given `--ignore-scripts`.
