---
work_package_id: WP05
title: Mission state builders and mission-lifecycle scenarios
dependencies:
- WP02
- WP04
requirement_refs:
- FR-012
- FR-013
- C-002
- SC-004
planning_base_branch: ccr-002603b2-bip646
merge_target_branch: ccr-002603b2-bip646
branch_strategy: Planning artifacts for this mission were generated on ccr-002603b2-bip646. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into ccr-002603b2-bip646 unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
history: []
agent_profile: java-jenny
authoritative_surface: acceptance-jvm/src/test/java/kitty/acceptance/
create_intent:
- acceptance-jvm/src/test/java/kitty/acceptance/environment/MissionFixture.java
execution_mode: code_change
model: ''
owned_files:
- acceptance-jvm/src/test/java/kitty/acceptance/environment/MissionFixture.java
- acceptance-jvm/src/test/java/kitty/acceptance/steps/ArrangeSteps.java
- acceptance-jvm/src/test/java/kitty/acceptance/steps/AssertSteps.java
- tests/scenarios/mission/**
role: implementer
tags: []
tracker_refs: []
---

# WP05: Mission state builders and mission-lifecycle scenarios

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Implementation command: `spec-kitty agent action implement WP05 --agent claude --mission acceptance-scenario-contract-01M4T9GC`

---

## Objective

Builders that reach a project with a Mission (and a work package in a lane) only by running the CLI, the steps that expose them, and a first `tests/scenarios/mission/` area.

## Context

Plan IC-05. Black-box only (C-002): every state change goes through `SpecKittyDriver`. Depends on WP04 (scenarios must pass the check) and WP02 (Java build layout). The step table in `tests/scenarios/README.md` is owned by WP01; add the new steps there as a recorded out-of-map edit.

### Subtask T017: `MissionFixture`

- **Steps**: discover the minimal CLI sequence against the current CLI (`spec-kitty init --ai claude`, `git add/commit`, `spec-kitty agent mission create <slug> --json`, and for a work package the planning chain then `spec-kitty agent tasks move-task`). If reaching a work-package lane needs more than a handful of commands, scope the lane builder down and record why. Builders fail fast with the command output when a step fails.

### Subtask T018: Steps

- **Steps**: Arrange `Given a project with a mission {string}` and, if feasible, `Given the work package {string} of mission {string} is in lane {string}`; Assert steps on `spec-kitty agent tasks status --json` (for example `Then the mission {string} is listed`), using the existing JSON handling in `CliResult`.

### Subtask T019: Scenarios

- **Steps**: `tests/scenarios/mission/mission-status.feature` with at least two scenarios, each with a positive control; run the per-PR check and the scratch-copy Gradle gating pass.

## Definition of Done

- T017 to T019 done; the check is green; the scenarios pass locally in the scratch copy.

## Risks

- CLI planning commands may need a git remote or agent configuration; keep everything inside the scenario's temp repository.

## Reviewer Guidance

- No direct writes to `.kittify/` or `kitty-specs/` from Java.
