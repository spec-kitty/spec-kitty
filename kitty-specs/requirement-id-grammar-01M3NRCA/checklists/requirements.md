# Specification Quality Checklist: Requirement-ID grammar and finalize-tasks diagnostics

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-29
**Mission**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Requirement types are separated (Functional / Non-Functional / Constraints)
- [x] IDs are unique across FR-###, NFR-###, and C-### entries
- [x] All requirement rows include a non-empty Status value
- [x] Non-functional requirements include measurable thresholds
- [x] Every FR row and success criterion carries a delivery label and no-op mark
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Mission Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Mission meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Audience: this mission's users are CLI operators and agents. Command names (`setup-plan`, `map-requirements`, `finalize-tasks`, the orchestrator-api `plan` verb), JSON reason vocabulary and ID shapes are the user-facing surface, not implementation detail. Module and file names are deliberately left to plan.md.
- The only `yes` no-op mark (SC-005, a ratchet) carries a named positive control.
- Post-spec adversarial squad (reviewer-renata: non-vacuity; paula-patterns: boundaries) folded in iteration 2. Three findings needed operator rulings, now recorded as Decision Moments: the rejected-ref verdict table (FR-019), carrying the refusal reason in data for the orchestrator-api (FR-015), and never rewriting existing refs (FR-004/FR-005). Other folds: a lowercase-only suffix when scanning specs (FR-002), a precise declared-position definition (FR-013), US1 made non-vacuous by a real finalize write, the SC discard warning retired (FR-007), a finalize/runtime parity story (US6, FR-016, SC-007), C-001 tightened to include canonicalisation and tokenisation plus an architectural test, a required argument with no default for the runtime (C-002), scan and benchmark methods pinned (NFR-001, NFR-003), and the contract-fixture exceptions corrected (NFR-002).
- Parser self-check (current `main` parser): 19 FR / 5 NFR / 9 C declared; bare-prose check `[]`; undeclared-citation check `[]`. Examples of the new shapes appear only inside table cells or outside requirement-named sections, so this spec stays clean under both the old and the new grammar.
