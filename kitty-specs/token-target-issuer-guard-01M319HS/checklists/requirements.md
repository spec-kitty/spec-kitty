# Specification Quality Checklist: Auth token-target issuer guard

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — kept to endpoints/flows named in the issue; the helper is described by behaviour, not code
- [x] Focused on user value and business needs (self-hosted operator, exfiltration victim, maintainer)
- [x] Written for non-technical stakeholders (security/availability framing)
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Requirement types are separated (Functional / Non-Functional / Constraints)
- [x] IDs are unique across FR-###, NFR-###, and C-### entries
- [x] All requirement rows include a non-empty Status value
- [x] Non-functional requirements include measurable thresholds (0 bytes to non-issuer host; 0 divergent normalizers; self-mutation guard)
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified (legacy null issuer, split-brain, in-lock refresh, best-effort rehydrate, normalization)
- [x] Scope is clearly bounded (closes #4755; #4053/#4265 folded as same-seam campsite; others separate)
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows (self-hosted mis-target; hostile-checkout exfil; recurrence prevention)
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Grounding squad (3 lenses, opus) confirmed the mission is real, not superseded, and correctly scoped
  before spec authoring. Verdicts folded into edge cases and constraints:
  - Path 4 (ws provisioning) is dormant → FR-004 marked defence-in-depth (Medium).
  - Refresh runs in-lock → C-002 / edge case requires guarding at the TokenManager boundary.
  - The `saas_client` bare-`except` swallow path is the re-opened-leak trap → FR-008.
- Operator steer: prefer a structural close (unification + fence) over a pointfix; fold #4053/#4265.
- Post-spec adversarial lens (analyst-annie, opus) attacked the spec and returned 12 findings (M1–M12),
  all folded before `/plan`:
  - M1 display-vs-raise duality → FR-007 split into shared decision + per-consumer reaction; US3 AC2.
  - M2 token-free diagnostics → NFR-006.
  - M3 per-flow split-brain + logout local-teardown → Edge Cases + US2 AC5.
  - M4 held-token fast path (guard the send, not only the refresh) → FR-008; US2 AC3/AC4.
  - M5 dormant ws untestable via entry point → NFR-004/SC-002/SC-004 carve-out to direct invocation.
  - M6 allowlist-exclusion vacuity → NFR-003 second assertion; US3 AC4.
  - M7 session=None contract → FR-012 + edge case.
  - M8 non-deterministic remedy → US2 AC2 pins a stable structured remedy identifier.
  - M9 "0 copies" negative → SC-003/US3 AC1 reframed as positive membership.
  - M10 static gates → NFR-007 (ruff/mypy/complexity ≤15).
  - M11 legacy null-issuer AC → US1 AC4.
  - M12 chained refresh → edge case.
