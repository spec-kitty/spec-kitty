---
description: "Work packages for the Mission Status Read API artifact reads and the removed-dashboard route inventory"
---

# Work Packages: Mission Status Read API: artifact reads and dashboard route inventory

**Inputs**: `kitty-specs/mission-status-artifact-reads-01M57KY3/` (spec.md, plan.md, research.md, route-inventory.md)
**Prerequisites**: plan.md, spec.md

**Tests**: required. The operations are contract surfaces, so every WP lands its tests in the same commit (ATDD: the route and
conformance tests are written first and seen RED).

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Artifact rules and the file-system port (Priority: P1)

**Goal**: The pure contract rules in the domain, plus a link-safe, bounded file-system adapter behind a new outbound port.
**Independent Test**: unit tests of the path rule, classifier, media type, text decision and redaction; adapter tests over real
trees with links, a FIFO, vanishing files and faults; the ArchUnit, allowlist-parity and no-uncapped-read tests stay green.
**Prompt**: `/tasks/WP01-artifact-rules-and-file-port.md`
**Requirement Refs**: FR-004, FR-006, FR-009, NFR-001, NFR-002, NFR-004

### Included Subtasks

T001 [P] Domain rules: `ArtifactPathRule`, `ArtifactKind`, `ArtifactMediaType`, `ArtifactRefusalCode`, `ArtifactText` (+ unit tests)
T002 Outbound port `MissionArtifactSource` and its DTOs in `application/query/port/out/`
T003 `FilesystemMissionArtifactSource`: Mission index, eligibility, walk, bounded read (+ adapter tests)
T004 `SafeFiles.readBounded` and the `Allowlist` classes `MISSION_ARTIFACT_DIR` / `MISSION_ARTIFACT` (+ the README block and the parity test)

### Dependencies

- None.

### Risks & Mitigations

- The Python and Java string models differ (code points against UTF-16 units). Lengths are counted in code points, and a
  supplementary character case is tested.

---

## Work Package WP02: The two routes over HTTP (Priority: P1) 🎯 MVP

**Goal**: `GET /api/v1/missions/{missionId}/artifacts` and `.../artifacts/content?path=` served, with every contract response.
**Independent Test**: `ArtifactRoutesTest` over the HTTP harness. Each response code is validated against the contract
schema. `OutOfScopeRoutesTest` keeps the five other operations at 404.
**Prompt**: `/tasks/WP02-artifact-routes.md`
**Requirement Refs**: FR-002, FR-003, FR-005, FR-008, NFR-003

### Included Subtasks

T005 Inbound port `MissionArtifactQuery`, `ArtifactRefused`, and `ArtifactQueryService` (order of decision, listing walk, sort, cap, readable)
T006 `ArtifactsController`, hand DTOs, the `ProblemMapper`/`ProblemAdvice` mapping (missing, repeated or malformed `path` means 400)
T007 Wiring in `ServiceWiring`; `OutOfScopeRoutesTest` updated; README "Routes and scope" updated
T008 `ArtifactRoutesTest`: every response code, written first

### Dependencies

- Depends on WP01.

---

## Work Package WP03: Conformance with the Python reference (Priority: P1)

**Goal**: One shared case file that both implementations materialize. The Python reference writes the goldens and Java compares
against them.
**Independent Test**: `pytest tests/contract/test_mission_status_artifact_goldens.py` (the goldens are current) and
`ArtifactConformanceTest` (Java equals golden), with a planted difference that fails.
**Prompt**: `/tasks/WP03-artifact-conformance.md`
**Requirement Refs**: FR-007, SC-002, SC-003

### Included Subtasks

T009 `cases.json`: the case trees as data, with credentials assembled from parts
T010 `tests/contract/_mission_status_artifact_goldens.py` (`--write`/`--check`) and its pytest
T011 `ArtifactConformanceTest` (link cases skipped where links cannot be made, with the skip stated)

### Dependencies

- Depends on WP02.

---

## Work Package WP04: Route inventory and changelog (Priority: P2)

**Goal**: #5533's inventory is complete and checked, and the changelog records the new routes and the dropped dashboard routes.
**Independent Test**: every route of `router.py` at `3d5c85d09^` has one inventory row; the changelog entry names the dropped
routes.
**Prompt**: `/tasks/WP04-route-inventory-and-changelog.md`
**Requirement Refs**: FR-001, FR-010, SC-001

### Included Subtasks

T012 Verify the inventory against `router.py` at `3d5c85d09^` (count and handler names)
T013 Add the `[Unreleased]` changelog entry: the new routes, and the dropped dashboard routes appended to the removal list

### Dependencies

- Depends on WP02.
