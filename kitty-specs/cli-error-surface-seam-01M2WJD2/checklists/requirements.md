# Specification Quality Checklist: Canonical guarded-read + CLI error-presentation seam

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-19
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — *structural terms (kernel, seam) are the product intent of an infra mission; kept to observable behavior where possible*
- [x] Focused on user value and business needs (operator/automation: clean errors, not crashes)
- [x] Written for non-technical stakeholders (BLUF summary + scenarios)
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Requirement types are separated (Functional / Non-Functional / Constraints)
- [x] IDs are unique across FR-###, NFR-###, and C-### entries
- [x] All requirement rows include a non-empty Status value
- [x] Non-functional requirements include measurable thresholds
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded (umbrella #2899 open remainder; subsumed fixes excluded)
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification (beyond the unavoidable seam/primitive intent)

## Notes

- Non-ASCII policy resolved via decision 01M2WJE53KMFBGEJX8JMFT71EE (reject explicitly).
- Scope confirmed with operator: full class-closer including #4720.
- **Post-spec adversarial squad (3 lenses: architecture, completeness, boundary/whack-a-field) run and folded** — see `traces/design-decisions.md` D1–D5. Reshaped: FR-001 now format-agnostic (kernel can't import runtime's pydantic model); FR-002 committed to a global Typer hook (not a decorator); FR-011 gate invariant named + non-vacuity via self-mutation; FR-013 subclass-compat (paula's ~85-catch-site census); #4637 three failure modes; #4739 text-stream root cause; #4720 typer.BadParameter→domain error; exit-1 domain / exit-2 usage boundary; NFR-003 restated structural; NFR-005 negative no-write assertion; NFR-006 back-compat added; FR-006 -f sweep across 4 sites.
- Mechanism no longer deferred: global hook + format-agnostic primitive are now pinned in the spec, gate-checkable.
