# Specification Quality Checklist: Acceptance Harness — the "real home stayed clean" guard on a shared host

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-02
**Mission**: `acceptance-real-home-shared-host-01M6EJXK` ([spec.md](../spec.md))

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — the spec names the harness file, the two subtrees and the switch because the defect *is* a harness guard; no design beyond FR-001/FR-004's stated behaviour. Java class names appear only in the reproduction evidence.
- [x] Focused on user value and business needs — the user is the maintainer running the suite; the value is a green run that means green.
- [x] Written for non-technical stakeholders — the narrative and Success Criteria are readable without the harness; the tables carry the precision.
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Requirement types are separated (Functional / Non-Functional / Constraints)
- [x] IDs are unique across FR-###, NFR-###, C-### and SC-### entries, and match the requirement-ID grammar
- [x] All requirement rows include a non-empty Status value
- [x] Non-functional requirements include measurable thresholds (one `Files.walk` per scenario; at most 3 synthetic files; byte-identical string when strict)
- [x] Every FR row and success criterion carries a delivery label and no-op mark
- [x] Success criteria are measurable (counts of red scenarios; per-scope fingerprint behaviour)
- [x] Success criteria are technology-agnostic — they state which writes change the fingerprint, not how it is computed
- [x] All acceptance scenarios are defined (SC-001–SC-004 plus the reproduction evidence)
- [x] Edge cases are identified — CI runner with the switch set (FR-003, SC-003), single-writer machine (FR-002, SC-004), `credentials` write (SC-002, C-002), 4-way parallel scenarios (NFR-003)
- [x] Scope is clearly bounded (C-001: harness, one docs page, one fragment)
- [x] Dependencies and assumptions identified (nightly-only JVM lane; no per-PR JVM test lane — recorded in research.md, decision 4)

## Mission Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows (shared host green, strict default, CI force, non-vacuity, diagnosable red)
- [x] Mission meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- The spec's reproduction section carries a concrete before/after fingerprint from `main`; it is the
  red-first evidence for SC-001 and is quoted from the run, not reconstructed.
- `spec-kitty charter context --action plan` is loaded before planning; planning artifacts land on the
  mission branch, not `main`.
