# Specification Quality Checklist: Account for every late-window change before the coordination branch goes

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-05
**Mission**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details leak into the user-facing stories (the "Problem" and "Scope decisions"
      sections name modules and issues on purpose: this is a brownfield defect spec whose acceptance
      is a teardown verdict, and a reviewer must be able to check the claim against the code)
- [x] Focused on user value and business needs (no committed change is dropped with the coordination branch)
- [x] Written for the maintainers who own `consolidation/`
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous (each FR names the verdict its test asserts)
- [x] Success criteria are measurable (red-first test, suite pass, mypy/ruff/changelog/docs gates)
- [x] All acceptance scenarios are defined for all three user stories
- [x] Edge cases are identified (mixed window, log deletion, unparseable input, empty window)
- [x] Scope is clearly bounded (Non-Goals names #7199, #7209, #7121 and the primary-projection exclusion)
- [x] Dependencies and assumptions identified (the #7124 assertion and its call ordering; the union stage
      reads the coordination worktree's working tree)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows (status event, primary document, no-weakening)
- [x] Mission meets measurable outcomes defined in Success Criteria
- [x] Delivery labels and no-op marks are populated on every FR row and every success criterion
      (`[build]`/`[ratchet]`, `no-op passable: no` throughout — a skip here is the defect, so no
      criterion can pass vacuously)

## Notes

- Two judgement calls are recorded as spec decisions rather than left implicit: `status.json` stays
  excluded **because it is derived** (Decision 3), and a primary document is "landed" when the
  target's committed copy contains it (Decision 4). A reviewer may disagree with either; both are
  restated in the PR body so the disagreement is visible rather than buried in the diff.
- No item required a spec update on re-validation.
