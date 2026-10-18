---
work_package_id: WP03
title: Conformance with the Python reference
dependencies:
- WP02
requirement_refs:
- FR-007
- SC-002
- SC-003
planning_base_branch: issue-957-dashboard-read-rehome
merge_target_branch: issue-957-dashboard-read-rehome
branch_strategy: Planning artifacts for this mission were generated on issue-957-dashboard-read-rehome. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-dashboard-read-rehome unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
phase: Phase 3 - Conformance
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/_mission_status_artifact_goldens.py
create_intent:
- tests/contract/_mission_status_artifact_goldens.py
- tests/contract/test_mission_status_artifact_goldens.py
- services/mission-status-api/src/test/resources/artifact-conformance/cases.json
- services/mission-status-api/src/test/resources/artifact-conformance/golden.json
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/test/resources/artifact-conformance/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/artifacts/**
- tests/contract/_mission_status_artifact_goldens.py
- tests/contract/test_mission_status_artifact_goldens.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Conformance with the Python reference

## Do This First: Load Agent Profile

Load the profile `python-pedro` (role implementer).

## Objectives & Success Criteria

- `cases.json` describes each case tree as data: files (text, base64, or repeated bytes), directories, links. Credentials are
  assembled from parts, so no literal token is committed.
- `python -m tests.contract._mission_status_artifact_goldens --write | --check` runs the reference over each materialized case
  and writes or checks `golden.json` (status and body per request; `modifiedAt` replaced by a format marker).
- `ArtifactConformanceTest` materializes the same cases, serves them through the HTTP harness, and asserts equality with
  `golden.json`. A planted difference fails. A link case is skipped, with the reason stated, where links cannot be created.

## Test Strategy

- `pytest tests/contract/test_mission_status_artifact_goldens.py` and `./gradlew test --tests '*ArtifactConformance*'`.
- ruff, `ruff format --check --force-exclude` and mypy over the new Python files.
