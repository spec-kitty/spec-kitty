# Mission Specification: Test suite quality — fix vacuous guards, unstub gates, retire scaffolding

**Mission Branch**: `test-suite-quality-p0-01M3NYXQ`
**Created**: 2026-09-29
**Status**: Complete
**Input**: P0 #5353 "Test suite quality - immediate action required" (children #5344, #5345, #5346–#5349, #5351; epics #5107/#5104)

## Purpose

A green CI no longer proves that consolidation, acceptance, drain and guard flows work. Two 2026-09-29 reviews (docs: `test-review/2026-09-29-last-48h-test-review.md`, `test-review/2026-09-29-dev-assist-test-audit.md`, both posted on #5353) found 14 HIGH vacuous tests, a stub-the-new-gate pattern, and ~260 retire-able development-assist tests. This mission restores predictive value for the maintainers and CI.

## User Scenarios & Testing

### User Story 1 — Guards fail when the product is broken (Priority: P1)
A maintainer breaks a guarded behaviour (plants a violation); the corresponding guard test goes red. Previously it stayed green.

**Independent Test**: for each of the 14 HIGH findings, the fixed test is run against a planted break (recorded as red-proof) and against the real product (green).

**Acceptance Scenarios**:
1. **Given** the drain gate is deleted, **When** `test_drain_capability` runs, **Then** it fails.
2. **Given** `specify_cli.consolidation` is imported by an acceptance module, **When** the forbidden-import guard runs, **Then** it fails.

### User Story 2 — Safety gates run in their integration harnesses (Priority: P2)
The consolidate/teardown/acceptance harnesses exercise the real gates (#4900 bake, `locked_reread_splice_and_write`, `_verify_and_announce_mission_number`) via real-git fixtures instead of stubbing them.

**Acceptance Scenarios**:
1. **Given** a stubbed-gate harness is migrated, **When** the gate is removed from production, **Then** a real-git test fails.

### User Story 3 — Redundant scaffolding is retired with named coverage (Priority: P3)
The top ranked development-assist retirements (audit items 1–10 that are safe within this mission) are deleted or folded, each naming the standing guard that asserts the same contract.

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| FR-001 | Each of the 14 HIGH findings (48h review §5/§6 R1+R2) is fixed so its oracle fails on the broken product, or deleted with a named covering guard. | Required |
| FR-002 | Each fixed guard has red-then-green evidence (planted break) recorded in the mission tracer/approach file and cited in the PR. | Required |
| FR-003 | Harnesses stubbing a production safety gate (#5345) are moved to real-git fixtures, or deleted with proof that coverage survives; a real-git gate test exists and is cited. | Required |
| FR-004 | Ranked audit items retired in this mission each name the covering guard in the commit message and PR (DIRECTIVE_041). | Required |
| FR-005 | The mission records a keep/retire/split verdict for each test file it adds or touches materially. | Required |
| FR-006 | Any baselined file that is fixed drops its ruff PT entry in the same commit — except `ruff.toml`'s PT block and `tests/architectural/test_ruff_pytest_style_baseline.py`, which stay untouched until PR #5355 lands. | Required |

## Non-Functional Requirements / Constraints

| ID | Constraint |
|----|-----------|
| NFR-001 | No heavy suites in-mission (NO_FULL_HEAVY_SUITES_IN_MISSION); run only the specific files each change implicates. |
| NFR-002 | No coverage deleted without naming the covering guard (DIRECTIVE_041, development-assist-test-cleanup procedure). |
| NFR-003 | New test code passes ruff, ruff format and mypy; complexity ≤ 15. |
| NFR-004 | No production code change except where a test fix exposes a real product defect (then filed/fixed red-first). |
| NFR-005 | No version bump; CHANGELOG entry under `[Unreleased]`. |

## Out of Scope

- Ruff PT rules / smell census (#5351, in PR #5355); exact-count pin conversion (#5346), fabricated-id lint (#5347), Sonar-helper tests (#5348), red-first provenance (#5349) — remain open under their epics.
- MED/LOW catalogue items; known-P0 red-on-main tests (#5106).
- Audit items whose covering guard cannot be verified in this mission (left in the ledger, not deleted).

## Success Criteria

| ID | Criterion |
|----|-----------|
| SC-001 | All 14 HIGH findings have red-then-green proof recorded. |
| SC-002 | Every deleted test cites a covering guard that was run green. |
| SC-003 | Targeted gate files and the touched test files pass; no new red on the merge-base comparison. |

## Assumptions

- The issue's "14 HIGH" counts the H rows in §6 R1+R2 (R1: 7 findings incl. sub-locations; R2: 3 findings). Where sub-locations count separately, all are covered.
