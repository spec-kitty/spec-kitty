# Specification Quality Checklist: move-task / approval-gate ergonomics

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-20
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — CLI flag/verdict names are the
      product surface itself, not implementation choices
- [x] Focused on user value and business needs (honest audit artifact, unsurprising workflow)
- [x] Written for stakeholders (operators/agents driving missions)
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Requirement types are separated (Functional / Non-Functional / Constraints)
- [x] IDs are unique across FR-###, NFR-###, and C-### entries
- [x] All requirement rows include a non-empty Status value
- [x] Non-functional requirements include measurable thresholds (<200ms, <2s, 100%, 0)
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded (explicit out-of-scope: #4330 landed work, #2816, #3454 children)
- [x] Dependencies and assumptions identified (grounding verdict recorded in Context section)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Verdict-value naming (`not-applicable`) confirmed by the operator via Decision Moment
  `DM-01M302SBM26BGHEX36GC8YFJME`.
- Scope (both levers + ADR; all three ergonomics items) confirmed by the operator; recorded as
  resolved Decision Moments.
- Grounding squad reproduced every sub-defect against `main` HEAD `a9d3f4b747` before authoring;
  already-landed items (#4330) and by-design behavior (#2816) explicitly excluded.
