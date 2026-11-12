---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: settled-placement-surface-01M78GR4
mission_id: 01M78GR4VQ0DD9ASHV9KCP0CRP
generated_at: '2026-11-12T18:57:19.994280+00:00'
analyzer_agent: claude
input_artifacts:
  spec.md:
    path: kitty-specs/settled-placement-surface-01M78GR4/spec.md
    sha256: e443483f0522f33c7fb783b65bba69420ab4c21391efdaa8ff126ddeecd5b26a
  plan.md:
    path: kitty-specs/settled-placement-surface-01M78GR4/plan.md
    sha256: a041d3921040ae25fa129426284ab520f98cad21c8bd2c3a53b7700fa3e90a9e
  tasks.md:
    path: kitty-specs/settled-placement-surface-01M78GR4/tasks.md
    sha256: 6a20d2fd732f3a9feb1b9c999115c4501cd06b10ce02827c031c8c32709c8c4f
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  medium: 2
  low: 2
  high: 0
  info: 0
findings:
- id: C1
  severity: medium
  category: consistency
  summary: WP03 T011/T012 prescribe write_target(WORK_PACKAGE_TASK).ref, but the post-tasks review showed new refusals beyond the Q2(a) ruling's premise; escalated (escalation 2), WP03 to be revised before it starts.
- id: N1
  severity: medium
  category: coverage
  summary: NFR-001 (≤2 s spec-commit, no extra git subprocess for the checkout lookup) has no subtask that measures it.
- id: L1
  severity: low
  category: coverage
  summary: FR-012 / SC-003 (followable remedies) is split across WP02 (executed remedies) and WP03 (pending); WP03 must add an executed-remedy assertion.
- id: L2
  severity: low
  category: scope
  summary: core/paths.py::resolve_merge_target_branch reads the same root-only meta.json; out of scope by C-006, recorded as a follow-up.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Consistency | MEDIUM | tasks/WP03-protected-preflights.md T011/T012; decisions (protected-check input) | The prescribed preflight input creates new refusals (flat-Mission resume; `lanes` test at test_implement_phases.py:489) and, fed only to the skip gate, breaks auto-committed move-task from a protected root | Operator ruling requested (escalation 2); revise WP03 before it starts; re-run analyze |
| N1 | Coverage | MEDIUM | spec.md NFR-001; tasks WP01/WP02 | No subtask measures the latency budget | Time the settled spec-commit in WP02's CLI test (assert < 2 s) or record the measurement in the PR |
| L1 | Coverage | LOW | spec.md FR-012, SC-003 | Remedy execution covered for WP02 only so far | WP03 revision adds an executed-remedy assertion |
| L2 | Scope | LOW | core/paths.py resolve_merge_target_branch | Same-class root-only meta read outside the Mission | Follow-up issue at PR time |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 one checkout authority | Yes | T001–T004 | WP01 |
| FR-002 spec-commit after settlement | Yes | T005–T007 | WP02 |
| FR-003 refuse stray root copy | Yes | T005, T007 | WP02 |
| FR-004 safe-commit after settlement | Yes | T005, T009 | WP02 (CLI test added) |
| FR-005 baseline committed | Yes | T014, T015 | WP04 |
| FR-006 implement from protected root | Yes | T010, T011 | WP03 (pending ruling) |
| FR-007 move-task --note | Yes | T010, T012 | WP03 (pending ruling) |
| FR-008 protected writes still refused | Yes | T010 | WP03 positive control |
| FR-009 target banner | Yes | T014, T016 | WP04 |
| FR-010 path-convention frame | Yes | T017–T019 | WP05 |
| FR-011 status lock | Yes | T005, T008 | WP02 |
| FR-012 followable remedies | Yes | T009, T013 | WP02, WP03 |
| NFR-001 latency | Partial | — | N1 |
| NFR-002 / NFR-003 quality, coverage | Yes | every WP DoD | |

**Charter Alignment Issues:** none. Red-first (C-011), single authority, no new gate, targeted tests only.

**Unmapped Tasks:** none.

**Metrics:** 12 FR + 3 NFR + 7 C + 4 SC; 19 tasks; FR coverage 100 %; ambiguity 0; duplication 0; critical 0.

**Next Actions:** proceed with WP01 → WP02; hold WP03 for the ruling; re-run `/spec-kitty.analyze` after WP03 is revised.
