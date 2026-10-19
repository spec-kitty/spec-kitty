---
work_package_id: WP01
title: Artifact rules and the file-system port
dependencies: []
requirement_refs:
- FR-004
- FR-006
- FR-009
- NFR-001
- NFR-002
- NFR-004
planning_base_branch: issue-957-dashboard-read-rehome
merge_target_branch: issue-957-dashboard-read-rehome
branch_strategy: Planning artifacts for this mission were generated on issue-957-dashboard-read-rehome. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-dashboard-read-rehome unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Rules and port
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/artifact/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/artifact/ArtifactPathRule.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/MissionArtifactSource.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/FilesystemMissionArtifactSource.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/FilesystemMissionArtifactSourceTest.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/ArtifactFile.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/ArtifactBytes.java
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/artifact/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/MissionArtifactSource.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/ArtifactFile.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/ArtifactBytes.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/FilesystemMissionArtifactSource.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/SafeFiles.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/Allowlist.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/artifact/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/FilesystemMissionArtifactSourceTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/AllowlistTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/NoUncappedReadTest.java
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Artifact rules and the file-system port

## Do This First: Load Agent Profile

Load the profile `java-jenny` (role implementer) before reading on.

## Objectives & Success Criteria

- The domain holds the contract rules of the artifact reads, as pure functions with unit tests:
  - the path rule (`malformed_artifact_path` of `contracts/tools/leak_scan.py`, lengths in code points);
  - the ordered kind classifier;
  - the media-type table;
  - the seven refusal codes with their fixed status, title and detail;
  - the text decision (NUL byte, strict UTF-8, credential, redaction through `LeakClasses`);
  - the casefold match of the root status records.
- A new outbound port `MissionArtifactSource` and its filesystem adapter:
  - the Mission index by `mission_id`;
  - eligibility (an lstat per component);
  - the iterative walk;
  - a bounded NOFOLLOW read through `SafeFiles`.
- The allowlist names the new reads (`MISSION_DIR` gains LIST; two new classes). The README's fenced allowlist and
  `AllowlistReadmeParityTest` agree, entry for entry.

## Context & Constraints

- spec.md (FR-004, FR-006, FR-009, NFR-001, NFR-002, NFR-006, D6, D7), plan.md "Design notes".
- The reference is `tests/contract/_mission_status_artifacts.py`: follow its order and semantics exactly.
- ArchUnit rules 1–14: domain is file-free; the adapter only depends on `port.out`, `domain` and itself; only `SafeFiles`
  (plus the ledger and the seam) call `openRead` (`NoUncappedReadTest`).
- Clean room: nothing from PRs #6264/#6265.

## Test Strategy

- `./gradlew test` with GraalVM CE 25.0.2 and `LC_ALL=C.UTF-8`; the contract bundle in `CONTRACT_BUNDLE`.
- Unit tests per rule. Adapter tests over `@TempDir` trees: a link file, a link directory, a link Mission directory, a
  FIFO (POSIX only), vanishing entries, an unreadable directory (POSIX only), a 262,145-byte file, a supplementary-character
  name.

## Review Guidance

- Compare each rule line by line with the reference. Reject any Java-idiomatic shortcut that changes an answer
  (`String.length`, `toLowerCase`, `\\S` with Java semantics).
