---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: shared-collection-and-shard-recapture-01M42V58
mission_id: 01M42V58B793R59V51H1YAA6TB
generated_at: '2026-10-04T07:29:01.140836+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/shared-collection-and-shard-recapture-01M42V58/spec.md
    sha256: 10f55e2f46217fe50745dc6096d77152daf4b4d53c1a16106361c78b5847ed76
  plan.md:
    path: kitty-specs/shared-collection-and-shard-recapture-01M42V58/plan.md
    sha256: 290b38b2629ea954f071ee88ea3ca93416578ae932dd64e0ab13d8d15738b840
  tasks.md:
    path: kitty-specs/shared-collection-and-shard-recapture-01M42V58/tasks.md
    sha256: e4ca88f8a3607a7164b292094a5286402144600459155033906337821f3972a6
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 69c63e91ae27a02b0c07b48939f72198b0d2654ed5bee42e3d6bc1d5d4e71a6e
verdict: ready
issue_counts:
  high: 0
  low: 4
  critical: 0
  medium: 2
  info: 0
findings:
- id: C1
  severity: medium
  category: coverage
  summary: NFR-001, NFR-002, NFR-003, SC-001 and SC-002 can only be measured on per-PR CI runs; WP03 delivers the workflow shape and WP07 a pending-marked template, so these stay unproven until after the pull request is open.
- id: C2
  severity: medium
  category: coverage
  summary: SC-006's post-merge evidence (first scheduled recapture on the primary branch) depends on the token fix tracked outside the mission; until then the run can capture but not propose.
- id: I1
  severity: low
  category: inconsistency
  summary: plan.md concern map orders documentation (IC-07) after the full recapture (IC-06); tasks.md deliberately runs WP06 before WP05 so the capture is the last change to test counts.
- id: I2
  severity: low
  category: inconsistency
  summary: data-model.md's reuse report line omits the dirty_paths field that WP01 T005 adds for dirty-checkout bypasses.
- id: I3
  severity: low
  category: inconsistency
  summary: spec.md FR-011 names only a test that 'collected for itself'; research D-14 and the contract also fail the check on a non-override bypass.
- id: U1
  severity: low
  category: underspecification
  summary: The per-capture subprocess timeout and the scheduled job's budget and timeout values are left to WP04 to choose and justify; no number is fixed in spec or plan.
---

## Specification Analysis Report

Mission `shared-collection-and-shard-recapture-01M42V58`. Artifacts analysed after four review passes (two grounding scouts, two post-spec reviewers, a brownfield seam map and a post-tasks review); their blocking findings were folded before this report, so what remains is residual.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | MEDIUM | spec.md NFR-001..003, SC-001, SC-002; tasks.md WP03, WP07 | Per-PR performance requirements are measurable only on CI runs of the open pull request. | Keep WP07's template `pending`; the orchestrator fills it from three runs and corrects the thresholds if measurement disagrees. |
| C2 | Coverage | MEDIUM | spec.md SC-006, "Operator action outside this mission" | Post-merge evidence depends on the recapture token being fixed. | Record the dependency in the pull request body; SC-006's test half is delivered in WP04. |
| I1 | Inconsistency | LOW | plan.md IC-06/IC-07; tasks.md WP05/WP06 | Plan orders docs after recapture; tasks reverse it on purpose. | Accept; tasks.md states the reason. |
| I2 | Inconsistency | LOW | data-model.md "Reuse report line"; tasks/WP01 T005 | `dirty_paths` field missing from the data model. | Add the field to data-model.md when WP01 lands. |
| I3 | Inconsistency | LOW | spec.md FR-011; research.md D-14; contracts/collection-store.md | FR-011 wording is narrower than the contract. | Accept; the contract is the binding detail and WP02 T007 pins it. |
| U1 | Underspecification | LOW | tasks/WP04 T019, T020 | Timeout and budget numbers are not fixed in planning. | WP04 states the numbers and reasoning in the workflow comment; reviewer checks them against the 18-minute charter capture. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001..FR-007, FR-012 | Yes | T002–T004, T006 | WP01 |
| FR-010 | Yes | T005, T009 | WP01 report line, WP02 summary |
| FR-011 | Yes | T007, T009 | WP02 |
| FR-008, FR-009 | Yes | T011–T013 | WP03 |
| FR-013..FR-016 | Yes | T023–T027 | WP05 |
| FR-017..FR-021 | Yes | T016–T022 | WP04 |
| FR-022 | Partly | T033–T035 | CI half completed after the pull request opens (C1) |
| FR-023 | Yes | T030–T032 | WP06 |
| NFR-001..NFR-003 | Shape only | T011–T013 | Measured after the pull request opens (C1) |
| NFR-004 | Yes | T002 (case 12) | WP01 |
| NFR-005 | Yes | T010, T014 | WP02 compare, WP03 nightly job |
| NFR-006 | Yes | T027 | WP05 |
| NFR-007 | Yes | T019, T020 | WP04 |
| NFR-008 | Yes | every WP | lint, format and complexity commands in each Test Strategy |
| C-001..C-010 | Yes | constraints carried in each WP's context | |
| SC-003, SC-007 | Yes | T002, T006 | WP01 |
| SC-004, SC-005 | Yes | T023, T026, T027 | WP05 |
| SC-006 | Yes (test half) | T017 | Post-merge half depends on the token (C2) |

**Charter Alignment Issues:** none. ATDD-first is the first subtask of every code work package; the allowlist is deleted rather than zeroed (ADR `2026-09-30-1`); no new allowlist; no heavy-suite runs; no version numbers.

**Unmapped Tasks:** T001, T016 (campsite refactors) and T028–T029 (workflow rename) serve no single requirement; they are tidy-first and naming-honesty steps under Standing Orders 2 and 6.

**Metrics:**

- Total requirements: 23 functional, 8 non-functional, 10 constraints, 7 success criteria
- Total tasks: 35 subtasks in 7 work packages
- Coverage: 100% of functional requirements have at least one task; 5 performance criteria are provable only after the pull request opens
- Ambiguity count: 1 (U1)
- Duplication count: 0
- Critical issues: 0

## Next Actions

- No critical or high findings; implementation may start.
- I2: update `data-model.md` when WP01 is approved.
- C1 and C2: carried as explicit post-PR and post-merge evidence steps.
