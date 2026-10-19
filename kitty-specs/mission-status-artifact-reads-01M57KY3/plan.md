# Implementation Plan: Mission Status Read API: artifact reads and dashboard route inventory

**Branch**: `issue-957-dashboard-read-rehome` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/mission-status-artifact-reads-01M57KY3/spec.md`

## Summary

The Java read service (`services/mission-status-api/`) gains the two artifact operations of the `mission-status` contract,
`listArtifacts` and `getArtifactContent`, built in the service's hexagonal layout. The rules (path rule, classifier, media
type, order of decision, text decision, credential check, redaction, ordering and cap) live in the domain. A new outbound
port reads the file system without following links. A hand-written controller maps the outcomes to the contract's bodies.
The answers equal those of the Python reference reader (`tests/contract/_mission_status_artifacts.py`). A shared,
data-described case file is materialized by both sides: the Python side writes goldens and the Java side compares against
them. The route inventory (#5533) is already committed as `route-inventory.md`.

### Planning answers (the discovery questions, answered from the operator task and the issues)

1. *Which read path serves the artifacts?* The Java read service (ADR D-4 amended, D-10). The CLI's native Python path is
   unchanged.
2. *Contract change?* None (C-001). The version stays `1.0.0-SNAPSHOT`.
3. *Which implementation is the reference?* The Python reference reader. Where it is stricter or looser than a Java idiom,
   the reference wins. Any deliberate divergence is recorded in the service README's divergence list.
4. *Mission directory?* The primary `kitty-specs/<name>/`, selected by `mission_id` from each `meta.json`, with the first
   directory in name order winning. Never the coordination copy.
5. *Generated or hand-written HTTP layer?* Hand-written (like `EventsController`). Three reasons. The generated models type
   `sizeBytes` as a 32-bit `Integer`, but the listing reports the size of any file, including ones over 2 GiB. A repeated
   `path` parameter must be refused, while Spring's `String` binding joins repeats with a comma. A missing `path` must answer
   `invalid_artifact_path`, not the framework's code-less 400. The `openApiGenerate` FILTER and its model list are not changed.

## Technical Context

**Language/Version**: Java 25 (GraalVM CE 25.0.2, as CI pins), Spring Boot 4; Python 3.11+ for the reference and the golden generator
**Primary Dependencies**: no new dependency (Spring MVC, Jackson 3, the existing `LeakClasses`)
**Storage**: files: a Mission directory read-only
**Testing**: JUnit 5 + AssertJ (Gradle `test`); pytest for the Python golden generator check; the existing `ContractValidator` for response bodies
**Target Platform**: the four native targets of `mission-status-api.yml` (Linux x64/arm64, macOS arm64, Windows x64)
**Project Type**: a service module inside the CLI repository (not in the wheel)
**Performance Goals**: NFR-005, a listing of this repository's largest Mission in under 500 ms on a warm JVM
**Constraints**: NFR-001 to NFR-004. Every open goes through `AllowlistAccess` with no link followed, and only `SafeFiles` opens for reading.
**Scale/Scope**: the 594 Missions of this repository; listings of up to 1000 entries

## Charter Check

- **Single canonical authority**: the contract is the authority for the shape; the Python reference is the authority for the rules
  (ADR D-11). The Java side adds no rule of its own and does not edit either. **Pass.**
- **Architectural alignment**: ArchUnit rules 1–14 stay green. Domain rules sit in `domain`, the file system sits behind a
  port (rule 4, rule 7), and the HTTP layer reaches only `port.in` (rule 3). `NoUncappedReadTest`: the new reads go through
  a capped `SafeFiles` method, and no new class calls `openRead`. **Pass.**
- **ATDD-first**: the route tests and the conformance comparison are written first. The out-of-scope test is RED for the two
  routes before the implementation. **Pass.**
- **Terminology**: Mission, never feature. `tests/architectural/test_no_legacy_terminology.py` is run. **Pass.**
- **Open-core only / Team Kitty boundary**: no hosted surface. **Pass.**
- **Test policy**: targeted tests, `make test-fast`, the Gradle `test` of the service; no `make test-full`. **Pass.**

## Project Structure

### Documentation (this mission)

```
kitty-specs/mission-status-artifact-reads-01M57KY3/
├── spec.md
├── route-inventory.md       # #5533 deliverable
├── plan.md
├── research.md
├── tracer-tooling-friction.md
├── tracer-approach.md
├── tracer-design-decisions.md
├── tasks.md
└── tasks/
```

### Source Code (repository root)

```
services/mission-status-api/src/main/java/org/speckitty/missionstatus/
├── domain/readmodel/artifact/          # NEW: pure rules
│   ├── ArtifactPathRule.java           # malformed_artifact_path + code-point length
│   ├── ArtifactKind.java               # the ordered classifier (enum with wire names)
│   ├── ArtifactMediaType.java          # extension table
│   ├── ArtifactRefusal.java            # code enum + fixed status/title/detail
│   ├── ArtifactText.java               # bytes -> 415/422/200 decision, strict UTF-8, redaction
│   └── ArtifactListing / ArtifactEntry / ArtifactContent records
├── application/query/
│   ├── ArtifactQueryService.java       # NEW: order of decision, walk filtering, sort, cap, readable flag
│   ├── port/in/MissionArtifactQuery.java          # NEW inbound port
│   ├── port/in/exceptions/ArtifactRefused.java    # NEW
│   ├── port/out/MissionArtifactSource.java        # NEW outbound port
│   └── port/out/dto/{ArtifactFile, ArtifactBytes}.java
├── adapter/out/filesystem/
│   ├── FilesystemMissionArtifactSource.java       # NEW: mission index, eligibility (lstat per component), walk, bounded read
│   ├── SafeFiles.java                  # + readBounded(path, cap): a capped open of a regular file, no link followed
│   └── Allowlist.java                  # + MISSION_DIR LIST/READ…, + MISSION_ARTIFACT_DIR, MISSION_ARTIFACT classes
├── adapter/in/http/
│   ├── ArtifactsController.java        # NEW: GET /missions/{missionId}/artifacts, /artifacts/content
│   ├── dto/{ArtifactListingBody, ArtifactEntryBody, ArtifactContentBody}.java   # NEW hand DTOs (rule 9 package)
│   ├── ProblemMapper.java / ProblemBody.java      # + artifact refusal (with type about:blank)
│   └── ProblemAdvice.java              # + ArtifactRefused; malformed query on the content route -> invalid_artifact_path
└── config/ServiceWiring.java           # + the artifact source and service beans

services/mission-status-api/src/test/
├── java/.../adapter/in/http/rest/ArtifactRoutesTest.java         # NEW: every response code over HTTP, body validated
├── java/.../conformance/artifacts/ArtifactConformanceTest.java   # NEW: Java vs Python goldens
├── java/.../domain/readmodel/artifact/*Test.java                  # NEW: unit tests of the rules
├── java/.../adapter/out/filesystem/FilesystemMissionArtifactSourceTest.java   # NEW: links, faults, vanishing files
└── resources/artifact-conformance/{cases.json, golden.json}      # NEW: shared case data + Python goldens

tests/contract/
├── _mission_status_artifact_goldens.py   # NEW: materialize cases.json, run the reference, --write/--check
└── test_mission_status_artifact_goldens.py   # NEW: --check as a test (goldens are current)
```

**Structure Decision**: the service's existing hexagonal layout. The new parts mirror the overview's: a domain read model,
an application service behind an inbound port, an outbound port with a filesystem adapter, and a controller.

## Design notes

- **Mission index.** For each `kitty-specs/<name>` with a regular `meta.json` (link followed, as `Listing` does), the
  adapter parses `meta.json` with the existing Python-compatible JSON codec and takes `mission_id` if it is a string. The
  first name in code-point order wins. A malformed or unreadable `meta.json` is skipped, as the reference does. The id must
  match `^[0-9A-HJKMNP-TV-Z]{26}$` before lookup. The directory must be a real directory (not a link) inside the real
  project root (`SafeFiles.requireContainedDir`): vanished or refused is 404, and unreadable is 500 (listing:
  `artifact_listing_unreadable`; content: `artifact_unreadable`).
- **Eligibility.** The path rule, then the case-insensitive root status records, then an lstat of every component (absent
  or not-a-directory means not eligible; a link means not eligible; the last component must be a regular file). Any other
  OS failure is a fault, which maps to 500, never 404.
- **Walk.** An explicit stack, names in code-point order, lstat per name; directories are pushed only while their relative
  path is shorter than 512 code points; regular files are collected. Then eligibility, a sort by UTF-8 bytes (equal to
  code-point order), the first 1000, a stat per entry (vanished means omitted), and `readable` from the same content
  decision (a file over the cap is decided from its size and never opened).
- **Content read.** A NOFOLLOW open, the size from the open handle, over the cap means 413 (not read), then at most cap+1
  bytes. Over the cap means 413; a NUL byte means 415; strict UTF-8 failure means 415; a credential pattern means 422;
  otherwise the human host paths (widened by `\S*`) become `[path]` and the addresses `[email]`.
- **modifiedAt.** The mtime floored to whole seconds, `yyyy-MM-dd'T'HH:mm:ss'Z'` in UTC.
- **Problem body.** `type: about:blank` plus the fixed title, status, code and detail of the reference, served as
  `application/problem+json`. `ProblemBody` gains an optional `type` member (omitted when null, so every existing body is
  unchanged).
- **Allowlist.** `MISSION_DIR` gains LIST. New classes: `MISSION_ARTIFACT_DIR` (`kitty-specs/<mission>/<dir…>`: STAT, LIST)
  and `MISSION_ARTIFACT` (`kitty-specs/<mission>/<path…>`: STAT, READ). The classifier tries them last, so `meta.json`,
  `lanes.json` and the ledger keep their own classes. `status.json` and the ledger are never read for content through the
  artifact path (eligibility refuses them first). The README's fenced allowlist and the parity test gain the two lines.
- **Out of scope stays 404.** `OutOfScopeRoutesTest` keeps `getMission`, `getWorkPackage`, `getWorkPackageDetail`, `/drift`
  and `/ops/invocations`.

## Complexity Tracking

No charter violation.

## Implementation Concern Map

### IC-01 — Artifact rules in the domain

- **Purpose**: the pure rules of the contract (path, kind, media type, refusals, text decision, redaction), unit-tested.
- **Relevant requirements**: FR-004, FR-005, FR-006
- **Affected surfaces**: `domain/readmodel/artifact/`, `domain/redaction/LeakClasses` (reused, unchanged)
- **Sequencing/depends-on**: none
- **Risks**: Python versus Java regex and string semantics (code points, `\S`). Mitigated by reusing `LeakClasses` and by
  conformance cases with supplementary characters.

### IC-02 — File-system port and adapter

- **Purpose**: read a Mission directory without following links, bounded, through the allowlist seam.
- **Relevant requirements**: FR-004, FR-009, NFR-001, NFR-002, NFR-004
- **Affected surfaces**: `application/query/port/out/`, `adapter/out/filesystem/`, `Allowlist`, the README allowlist block
- **Sequencing/depends-on**: none
- **Risks**: `NoUncappedReadTest` and the allowlist parity tests; the TOCTOU residual (same as the README threat note).

### IC-03 — Query service, controller and wiring

- **Purpose**: the order of decision and the HTTP mapping of the two operations.
- **Relevant requirements**: FR-002, FR-003, FR-005, FR-008
- **Affected surfaces**: `application/query/`, `adapter/in/http/`, `config/ServiceWiring`, `OutOfScopeRoutesTest`, the README routes section
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: a malformed query string or a missing or repeated parameter must map to `invalid_artifact_path`.

### IC-04 — Conformance with the Python reference

- **Purpose**: one shared case file, Python goldens, and a Java comparison.
- **Relevant requirements**: FR-007, SC-003
- **Affected surfaces**: `tests/contract/_mission_status_artifact_goldens.py`, `src/test/resources/artifact-conformance/`
- **Sequencing/depends-on**: IC-03
- **Risks**: symbolic links on Windows (link cases are skipped where links cannot be created and say so); planted credentials
  must never be committed as literal tokens (they are built from parts at materialization time).

### IC-05 — Route inventory and docs

- **Purpose**: #5533's mapping (committed) and the changelog and README updates.
- **Relevant requirements**: FR-001, FR-010
- **Affected surfaces**: `route-inventory.md`, `CHANGELOG.md`, `services/mission-status-api/README.md`
- **Sequencing/depends-on**: IC-03
- **Risks**: none
