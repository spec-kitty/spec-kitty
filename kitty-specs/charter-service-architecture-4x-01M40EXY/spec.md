# Mission Specification: Charter Service Architecture for 4.x

**Mission Branch**: `docs/charter-service-architecture`
**Created**: 2026-10-03
**Status**: Ready
**Mission**: documentation
**Input**: Consolidate the reviewed charter read/write redesign into canonical
4.x architecture, ADR, C4, and roadmap documentation.

## Documentation Scope

**Iteration Mode**: mission_specific
**Target Audience**: Spec Kitty maintainers, architecture reviewers, and 4.x
planning owners
**Selected Divio Types**: explanation
**Languages Detected**: Markdown and Mermaid
**Generators to Use**: none

The canonical addition consists of:

- one new 4.x ADR owning the staged charter read/write redesign;
- living C4 context, container, and component views that link to the ADR;
- one concise strangler-prep addition to the active 4.x roadmap;
- one forward-intent pointer in the architecture vision;
- one charter-domain plan pointer where a canonical domain plan exists.

The gitignored research corpus remains evidence and is not copied into `docs/`.
Later operator rulings supersede the earlier projection-server design: Python
keeps the production write path and CLI seam initially; Java becomes the
production read implementation; Java writes follow after lossless YAML
round-trip and confined-mutation evidence.

## User Scenarios & Testing

### User Story 1 - Understand the authoritative decision (Priority: P1)

As a maintainer, I can identify one canonical decision describing the staged
Python-to-Java charter transition without reconciling contradictory work notes.

**Why this priority**: Implementation cannot start safely while compiler
authority, read cut-over, and write cut-over are ambiguous.

**Independent Test**: A reviewer can answer who owns reads and writes at each
stage, which contract is shared across languages, and what remains deferred,
using only the ADR and its direct links.

**Acceptance Scenarios**:

1. **Given** the ADR, **When** a reviewer traces the transition stages,
   **Then** Python write, Java read, shadow/conformance, and later Java write
   responsibilities are explicit and non-contradictory.
2. **Given** an unresolved library or storage choice, **When** a reader checks
   the ADR, **Then** it appears as deferred rather than settled.

### User Story 2 - Place the design in 4.x (Priority: P2)

As a 4.x planning owner, I can see where the redesign belongs in the active
roadmap and which milestone it must not block.

**Why this priority**: The read service belongs to strangler preparation under
#645, while the later write swap belongs to #2519; neither belongs on milestone
11.

**Independent Test**: The roadmap addition names the stable API dependency,
the separate read and write tracker homes, and the off-GA posture without
duplicating the ADR.

**Acceptance Scenarios**:

1. **Given** the active roadmap, **When** a planning owner locates the redesign,
   **Then** the Java read service is under 4.x Work/#645 and the write migration
   is deferred to CLI 4.x stable/#2519.

### User Story 3 - Navigate the intended architecture (Priority: P3)

As an architect or implementer, I can use the living C4 views to understand the
system boundary, containers, components, and dependency direction.

**Why this priority**: The design depends on hexagonal boundaries and distinct
read/write infrastructure modules.

**Independent Test**: Every C4 view identifies the Python seam, Java service,
pure domain, inbound adapters, outbound adapters, shared contract, and Mission
Status Read sibling without introducing a second architecture narrative.

**Acceptance Scenarios**:

1. **Given** the living C4 pages, **When** a reviewer follows component
   dependencies, **Then** infrastructure dependencies point inward and the
   domain imports no YAML, HTTP, MCP, or SQL library.

### Edge Cases

- Work notes still contain superseded projection-server conclusions.
- The Mission Status Read ADR is a sibling precedent, not the owner of charter
  semantics.
- Byte-identical YAML output can pass while domain mapping is bypassed.
- Python fallback and Java-primary behavior can become a permanent split-brain.
- A planned Java service does not belong in implementation mapping as shipped
  code.

## Requirements

### Functional Requirements

| ID | Requirement | Priority | Status |
|---|---|---|---|
| FR-001 | Add one Proposed 4.x ADR that owns the staged charter read/write redesign and supersedes the projection-server interpretation. | High | Open |
| FR-002 | The ADR MUST state the current stage, transition stages, shared language-neutral contract, conformance gates, and non-goals. | High | Open |
| FR-003 | Add living C4 context, container, and component views under `docs/architecture/diagrams/`, each linking to the ADR. | High | Open |
| FR-004 | Update the active 4.x roadmap with one concise strangler-prep clause placing read work under #645/4.x Work and later write work under #2519/CLI 4.x stable. | High | Open |
| FR-005 | Add only pointers—not duplicate architecture narrative—to the architecture vision and relevant charter-domain plan. | Medium | Open |
| FR-006 | Record YAML round-trip parity as a write-path gate and require a confined-mutation witness so the gate cannot pass while ignoring the domain model. | High | Open |
| FR-007 | Keep unverified stack details, measurements, token estimates, and superseded findings out of canonical decision text. | High | Open |
| FR-008 | Cross-link the ADR, C4 pages, roadmap entry, and plan/vision pointers without broken relative links. | Medium | Open |

### Non-Functional Requirements

- **NFR-001 (Required)**: A reviewer MUST identify the canonical decision and
  linked views within five minutes.
- **NFR-002 (Required)**: Every changed page MUST have one owning purpose:
  decision, model, or plan.
- **NFR-003 (Required)**: New Mermaid diagrams MUST parse without errors.
- **NFR-004 (Required)**: Documentation validation and targeted terminology
  checks MUST complete with zero failures caused by this Mission.

### Constraints

- **C-001 (Required)**: Follow `docs/architecture/README.md`.
- **C-002 (Required)**: Keep the work off the 4.0.0 GA milestone.
- **C-003 (Required)**: Do not edit generated agent copies.
- **C-004 (Required)**: Keep the Mission Status Read service as a sibling, not
  a shared process or domain.
- **C-005 (Required)**: Keep read conformance and write round-trip parity as
  separate milestones.

### Key Entities

- **Charter API Seam**: Existing Python-facing boundary through which callers
  transition to Java reads without per-command changes.
- **Cross-language Contract**: Versioned schemas, semantic rules, identifiers,
  and conformance fixtures shared by Python and Java.
- **Java Charter Read Service**: Per-worktree read implementation responsible
  for parsing, validation, domain resolution, and agent-facing reads.
- **Lossless YAML Document**: Infrastructure representation preserving comments
  and style separately from semantic domain objects.
- **Canonical Architecture Set**: ADR plus linked living C4 views; plans and
  vision point to it rather than restating it.

## Success Criteria

- **SC-001**: All four review lenses can classify the promoted decision as
  READY without a blocker about competing Python/Java read authorities.
- **SC-002**: Every canonical page reaches the owning ADR through one direct
  link.
- **SC-003**: The roadmap addition is no more than one focused clause and one
  dependency-spine annotation.
- **SC-004**: All new and changed internal links resolve.
- **SC-005**: The terminology guard passes with zero new violations.
- **SC-006**: Review finds zero unqualified claims that Java performance,
  inference savings, or adoption improvements have already been measured.

## Assumptions

- **ASM-001**: The operator-approved direction supersedes conflicting earlier
  work notes.
- **ASM-002**: The ADR starts Proposed; implementation and final stack
  selection remain later work.
- **ASM-003**: This isolated topic branch will be proposed to `main` by PR.
- **ASM-004**: Issue numbers and milestone placement are planning anchors, not
  an implementation schedule.

## Out of Scope

- Implementing the Java service or changing Python charter behavior.
- Selecting or pinning final Java libraries and build plugins.
- Creating service source directories or CI workflows.
- Editing the Mission Status Read ADR.
- Copying the gitignored research corpus into canonical docs.
- Filing or changing tracker issues.
- Claiming measured performance or adoption improvements.
