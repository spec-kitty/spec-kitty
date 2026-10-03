# Implementation Plan: Charter Service Architecture for 4.x

**Branch**: `docs/charter-service-architecture`
**Date**: 2026-10-03
**Spec**: [spec.md](spec.md)

## Summary

Promote the reviewed charter redesign into the canonical 4.x architecture
surfaces. Author one Proposed ADR as the decision owner, add matching living C4
views, and add concise pointers from the roadmap, architecture vision, and
charter-domain planning surface. Do not copy the investigation corpus or
implement the Java service.

## Technical Context

**Documentation Framework**: existing Markdown architecture corpus
**Languages**: Markdown and Mermaid
**Generators**: none
**Output**: repository-hosted Markdown
**Canonical layout**: `docs/architecture/README.md`
**Validation**: relative links, Mermaid syntax review, terminology guard,
architecture-boundary review

## Branch Contract

Current branch at plan start, planning/base branch, and final mission target are
all `docs/charter-service-architecture`. The checkout matches that target. A
later pull request from this topic branch targets `main`; this Mission does not
publish or merge it.

## Architecture Authority Split

| Surface | Owns | Must not contain |
|---|---|---|
| New 4.x ADR | Decision, stages, invariants, non-goals, deferred decisions | Roadmap sequencing detail or unverified pins |
| Living C4 | System, container, and component relationships | A second rationale narrative |
| 4.x roadmap | Placement under #645 and #2519; off-GA posture | Repeated architecture |
| Architecture vision | One forward-intent pointer | Implementation plan |
| Charter-domain plan | One dependency/promotion link | Duplicate decision |

## Phase 0: Research Consolidation

Use the gitignored preparatory corpus in the original isolated checkout as
evidence, especially:

- `architectural_design.md`
- `12-c4-roadmap-fit.md`
- `13-review-renata.md`
- `14-review-alphonso.md`
- `15-review-daphne.md`
- `16-review-priti.md`
- `17-review-synthesis.md`

Only the final operator direction and dispositioned findings become normative.
Earlier projection-server conclusions remain historical.

See [research.md](research.md).

## Phase 1: Documentation Design

### ADR

Create one 4.x ADR with:

1. context and 4.x placement;
2. decision: Python write seam now, Java production reads, later Java writes;
3. hexagonal dependency direction and read/write module separation;
4. shared contract: schemas, semantic rules, identifiers, and fixtures;
5. staged read cut-over with a temporary, loud Python fallback;
6. write migration gates: codec identity, mapping identity, confined mutation;
7. sibling relationship to Mission Status Read;
8. explicit non-goals and deferred choices;
9. consequences, risks, and acceptance evidence.

### Living C4

Add or update the living C4 pages under:

- `docs/architecture/diagrams/01_context/`
- `docs/architecture/diagrams/02_containers/`
- `docs/architecture/diagrams/03_components/`

Every diagram links to the ADR. Planned containers are marked planned and do
not enter the implementation mapping as shipped code.

### Plan and vision pointers

- Add one dependency-spine annotation and one focused strangler-prep paragraph
  to `docs/plans/4-0-0-milestone-roadmap.md`.
- Add one forward-intent pointer to `docs/architecture/vision/README.md`.
- Find the canonical charter-domain plan; add one link only if such a current
  plan exists. Do not create a second architecture explanation.

## Round-trip Gate Design

The ADR distinguishes three tests:

1. **Codec identity**: lossless YAML load and emit is byte-identical.
2. **Mapping identity**: source document maps to domain and back without a
   business mutation and remains byte-identical.
3. **Confined mutation**: a deliberate domain-field change produces exactly
   the expected local diff.

Gate 2 alone is fakeable if the implementation ignores the domain object.
Gate 3 is required before a production write operation moves to Java. These
write gates do not block the read-service cut-over.

## Charter Check

- Single canonical authority: the ADR owns the decision; other surfaces link.
- Architectural alignment: adapters depend inward; domain remains pure.
- Canonical sources: do not copy work notes into `docs/`.
- Terminology: Mission, branch integration, read path, and write path are used
  precisely.
- Pack tiers: the design must preserve configured built-in, org, and project
  inputs without making `packs/internal` a consumer default.
- Git discipline: topic branch only, no push or publication in this Mission.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Two read authorities during migration | Staged shadow comparison, explicit primary, loud fallback, retirement gate |
| Byte parity passes without domain use | Confined-mutation witness |
| Read cut-over waits for write codec | Separate read and write milestones |
| Status-service ADR absorbs charter design | New charter ADR; sibling citation only |
| Plans duplicate architecture | Pointer-only roadmap and vision edits |
| Unverified stack choices become commitments | Keep libraries and versions deferred |
| Planned service appears shipped | Mark planned in C4; no implementation-map edit |

## Validation

1. Verify relative links in every changed page.
2. Inspect Mermaid blocks for parseable syntax and consistent C4 names.
3. Run `pytest tests/architectural/test_no_legacy_terminology.py`.
4. Run any existing targeted documentation-link or architecture-index tests
   discovered from the changed paths.
5. Dispatch an independent architecture/documentation review and disposition
   every finding.

## Work Breakdown Preview

1. WP01 — Author the Proposed ADR.
2. WP02 — Add matching living C4 views.
3. WP03 — Add roadmap, vision, and domain-plan pointers.
4. WP04 — Validate links, terminology, diagrams, and canonical ownership.
5. WP05 — Independent review and findings fold.
