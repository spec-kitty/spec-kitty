# Specification Quality Checklist: Verdict-matrix RMW preservation (#4858 + #4868)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-21
**Mission**: [spec.md](../spec.md)

<!-- Terminology note: the canonical specify checklist template ships "**Feature**:" and
     "## Feature Readiness"; per the Terminology Canon this instance uses "Mission".
     Upstream gap to file against the shipped template in packs/built-in. -->

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — behaviour-level; fix mechanisms (lock/atomic/read-source) expressed as constraints
- [x] Focused on user value and business needs — honest verdicts, no silent verdict loss
- [x] Written for non-technical stakeholders — Intent Summary + user stories are plain-language
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
- [x] Edge cases are identified (both roots)
- [x] Scope is clearly bounded — two roots in one class; #2482 excluded (C-005); non-verdict acceptance writers out of scope (C-010); no issue-matrix concurrency work
- [x] Dependencies and assumptions identified

## Mission Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows (both roots + single-writer preservation)
- [x] Mission meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Folded per operator decision (2026-09-21): #4868 joins #4858 as the "verdict-matrix RMW
  preservation" class. Operator's own #4868 triage routed it to this family.
- #4858 half hardened by the post-spec adversarial squad (lock-acquisition spy FR-007, call-order
  FR-008, exact seam + one-shot reentrancy, disk-reload assertions, mid-point provenance, coord
  two-worktree-root drive, criterion-mode seam). See `tracer-squad-findings.md`.
- #4868 half grounded (`research/grounding-4868.md`): confirmed `_migrate_if_needed` wrong-source
  read; fix = coord-aware `read_dir` into `migrate_issue_matrix_to_json`, write staging unchanged
  (C-011); integration red-first test mandatory (real write-seam). A focused post-spec squad pass
  on the #4868 half + combined coherence runs before plan.
