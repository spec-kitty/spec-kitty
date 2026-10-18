# Specification Quality Checklist: Fix plan-mission guard/manifest artifact-vocabulary mismatch

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-18
**Mission**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details leak into requirements (surfaces named only as grounding context)
- [x] Focused on user/operator value (plan mission can advance; diagnosable blocks)
- [x] Written for non-technical stakeholders (user stories in plain language; mechanism isolated to Context)
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain (design settled by grounding squad)
- [x] Requirements are testable and unambiguous
- [x] Requirement types separated (Functional / Non-Functional / Constraints)
- [x] IDs unique across FR/NFR/C/SC and match the grammar
- [x] All requirement rows have a non-empty Status
- [x] NFRs include measurable thresholds (byte-identical non-plan sets; schema-valid)
- [x] Every FR row and success criterion carries a delivery label + no-op mark
- [x] Success criteria measurable and technology-agnostic
- [x] Acceptance scenarios defined
- [x] Edge cases identified (other-family regression, schema, MISSION_GOALS, defect #2, orphan keys)
- [x] Scope clearly bounded (Out of Scope)
- [x] Dependencies and assumptions identified

## Mission Readiness

- [x] All FRs have clear acceptance criteria
- [x] User scenarios cover primary flows (advance, diagnosability, hardening)
- [x] Mission meets measurable outcomes in Success Criteria
- [x] No implementation details leak into requirement statements

## Notes

- FR-004 non-vacuity is load-bearing: the parity test MUST go through the real `gather_artifact_presence`,
  not synthetic `present_artifacts=`, because synthetic injection is exactly why the bug passed every
  existing plan test. The red-first proof (red pre-fix, green post-fix) is the non-vacuity control.
- Reconciliation direction (Option A, manifest-side) and canonical-vocabulary choice are settled by the
  grounding squad (architect + paula-patterns), not deferred.
