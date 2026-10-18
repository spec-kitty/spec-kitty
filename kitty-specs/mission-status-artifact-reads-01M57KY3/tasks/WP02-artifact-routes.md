---
work_package_id: WP02
title: The two artifact routes over HTTP
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-005
- FR-008
- NFR-003
planning_base_branch: issue-957-dashboard-read-rehome
merge_target_branch: issue-957-dashboard-read-rehome
branch_strategy: Planning artifacts for this mission were generated on issue-957-dashboard-read-rehome. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-dashboard-read-rehome unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - Routes
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/ArtifactsController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/ArtifactQueryService.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/rest/ArtifactRoutesTest.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/MissionArtifactQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/exceptions/ArtifactRefused.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/ArtifactQueryServiceTest.java
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/ArtifactQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/MissionArtifactQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/exceptions/ArtifactRefused.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/ArtifactsController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/dto/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/ProblemMapper.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/ProblemBody.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/ProblemAdvice.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/ServiceWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/rest/ArtifactRoutesTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/rest/OutOfScopeRoutesTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/ArtifactQueryServiceTest.java
- services/mission-status-api/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – The two artifact routes over HTTP

## Do This First: Load Agent Profile

Load the profile `java-jenny` (role implementer).

## Objectives & Success Criteria

- `GET /api/v1/missions/{missionId}/artifacts` serves `ArtifactListing`, and `GET .../artifacts/content?path=` serves
  `ArtifactContent`. Every response code the contract lists is produced and validated against the contract schema.
- A missing, repeated or malformed `path` (including a malformed percent-encoding) is 400 `invalid_artifact_path`.
- `OutOfScopeRoutesTest` drops the two artifact paths and keeps the other five at 404.
- The README "Routes and scope" and "Read allowlist" sections describe the new routes.

## Context & Constraints

- spec.md FR-002, FR-003, FR-005, FR-008, NFR-003; plan.md planning answer 5 (a hand-written controller, hand DTOs in
  `adapter.in.http.dto`).
- No refusal body echoes a path, a directory, content or an OS message.

## Test Strategy

- Write `ArtifactRoutesTest` first and see it RED (the routes answer 404). Then implement until it is GREEN.
- Validate bodies with the existing `ContractValidator` used by `ResponseContractValidationTest`.
