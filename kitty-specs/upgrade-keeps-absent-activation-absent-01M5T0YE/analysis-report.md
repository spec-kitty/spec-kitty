---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: upgrade-keeps-absent-activation-absent-01M5T0YE
mission_id: 01M5T0YEQ79NXQCP88NW5EZJV7
generated_at: '2026-10-25T17:53:12.066961+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/upgrade-keeps-absent-activation-absent-01M5T0YE/spec.md
    sha256: 4afc84729cfdbdda9cf5e73197d9ae46e513f549ae6f7c133d91ac2cde94770f
  plan.md:
    path: kitty-specs/upgrade-keeps-absent-activation-absent-01M5T0YE/plan.md
    sha256: 8f6f6e91febbbc62599f82dabc8f701260044436522f316a16025afce3f4eb2d
  tasks.md:
    path: kitty-specs/upgrade-keeps-absent-activation-absent-01M5T0YE/tasks.md
    sha256: 7c3957359fa71ddcedf06129ab0d64f1150d92727a094a1fec283a2d046a8d3f
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  medium: 1
  critical: 0
  high: 0
  low: 2
  info: 0
findings:
- id: I1
  severity: medium
  category: inconsistency
  summary: plan.md Source Code tree and Design omit the post-tasks folds (charter.activation.api re-exports, dead-module and seam-boundary gate entries) that WP01 now owns.
- id: U1
  severity: low
  category: underspecification
  summary: FR-008's seeded-list hint keys on set equality with today's in-force set; a list seeded before the catalogue grew is a strict subset and gets no hint.
- id: C1
  severity: low
  category: coverage
  summary: The mission-step-contract edge case (selections never resolve, pre-existing) has no test; it is recorded as deferred.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | plan.md "Source Code", "Design"; tasks/WP01 "Post-tasks squad folds" | The plan predates the post-tasks folds. WP01 carries them: imports through `charter.activation.api`, the new re-exports, and the dead-module and seam-boundary gate entries. | Treat the WP01 fold section as authoritative. The PR body lists the touched files. |
| U1 | Underspecification | LOW | spec.md FR-008; WP01 T005 | The hint compares a present list with today's full in-force set. A list seeded before the catalogue grew does not match. | Accept it: the hint is advisory, and the CHANGELOG names the remedy for every already-seeded project. Note it in the PR. |
| C1 | Coverage | LOW | spec.md Edge Cases (mission-step contracts) | The pre-existing resolver gap is not tested by this mission. | Keep it deferred, and list it under Deferred in the PR. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 absent-key-stays-absent | yes | T001, T002, T004 | end-to-end and unit |
| FR-002 synthesis-matches-absent-key | yes | T001 | CLI `synthesize --dry-run --json` |
| FR-003 promote-into-present-list | yes | T002, T004 | |
| FR-004 authoritative-surface | yes | T001, T002, T004 | |
| FR-005 superseded-not-edited | yes | T003, T004, T006 | |
| FR-006 deactivations-and-unresolved | yes | T002, T004, T006 | the deny gate is in WP01 |
| FR-007 one-run-settles | yes | T001, T002 | narrowing scenario |
| FR-008 seeded-list-hint | yes | T005 | |
| FR-009 bundle-restamp | yes | T002, T004 | |
| FR-010 dry-run-preview | yes | T005 | |
| NFR-001 idempotence | yes | T001, T004 | |
| NFR-002 upgrade-cost | yes | T004 | spy test |
| NFR-003 code-quality | yes | all | ruff, mypy, complexity |
| C-001..C-006 | yes | T002, T003, T006, T008 | |

**Charter Alignment Issues:** none. The change works through the canonical seams (single authority), the shipped migration stays untouched (DIRECTIVE_044), and the work is red-first (ATDD).

**Unmapped Tasks:** none.

**Metrics:**

- Total Requirements: 22 (10 FR, 3 NFR, 6 C, 3 SC)
- Total Tasks: 8
- Coverage: 100%
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

## Next Actions

Proceed to implement. I1 is resolved by the WP01 fold section. U1 and C1 go into the PR body.
