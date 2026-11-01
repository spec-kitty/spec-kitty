---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: events-service-cutover-01M6B0AE
mission_id: 01M6B0AEGV2NN3DZP7S6734GS2
generated_at: '2026-11-01T07:46:08.193542+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/events-service-cutover-01M6B0AE/spec.md
    sha256: 80c07ec3ef707937649c2686949e6011fcbe12ce7f744df5347f37ec2e76188a
  plan.md:
    path: kitty-specs/events-service-cutover-01M6B0AE/plan.md
    sha256: 04b3eae0e425a9eb3b32cc5b75a71be5d041a02b69698c4027ba3b39ea83f30d
  tasks.md:
    path: kitty-specs/events-service-cutover-01M6B0AE/tasks.md
    sha256: 40c8548b8661579203288599acbe4a46ffbfb1615ad7f0b0b882897817096b38
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  low: 3
  medium: 1
  critical: 0
  high: 0
  info: 0
findings:
- id: C1
  severity: medium
  category: coverage
  summary: NFR-004 (ruff/format/mypy, complexity <= 15) and C-005..C-007 are cross-cutting and mapped to no single WP; each WP's validation section must carry them.
- id: F1
  severity: low
  category: inconsistency
  summary: WP01 leaves the wiring ratchet in tests/ci/test_sync_services.py red until WP04; documented as WP04's acceptance test, but WP01 review must not read it as a regression.
- id: U1
  severity: low
  category: underspecification
  summary: WP03 leaves open whether test_mission_status_project.py:701 (raw Project.yaml) is re-pointed or deleted; the rule (source-layout assertion -> delete, record residual) is stated.
- id: U2
  severity: low
  category: underspecification
  summary: WP02 must decide how the test reader finds the CI-fetched cache under the per-worker HOME/XDG isolation; the decision point is named, the answer is not.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | MEDIUM | spec.md NFR-004, C-005..C-007; tasks.md | Cross-cutting quality/scope rows have no owning WP | Every WP validation block runs ruff, format `--force-exclude`, mypy on changed files; review checks C-005/C-006 per WP |
| F1 | Inconsistency | LOW | WP01 T001, WP04 objective | Intentional red between WP01 and WP04 | Keep; reviewer of WP01 confirms it is the only red |
| U1 | Underspecification | LOW | WP03 T012 | `Project.yaml` raw read | Decide at implementation by the stated rule |
| U2 | Underspecification | LOW | WP02 T007 | Cache location under test isolation | Decide at implementation; record in design-decisions tracer |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 read-service pin | Yes | T002 | via `service vendor` only |
| FR-002 extras-only fetch | Yes | T001, T003 | |
| FR-003 verified extraction | Yes | T001, T004 | |
| FR-004 dev-setup | Yes | T001, T005 | |
| FR-005 CI wiring | Yes | T016, T017, T021, T023 | ratchet test is the acceptance test |
| FR-006 goldens repoint | Yes | T008-T010 | |
| FR-007 oracle/contract repoint | Yes | T011-T013 | |
| FR-008 fail closed | Yes | T007 | |
| FR-009 nightly compare | Yes | T020, T021 | |
| FR-010 acceptance-jvm tools | Yes | T014, T022, T023 | |
| FR-011 remove copies | Yes | T024, T025 | |
| FR-012 remove coupling | Yes | T016, T018, T027 | |
| FR-013 remove gate/tests | Yes | T026 | |
| FR-014 release check | Yes | T028, T029 | |
| FR-015 checklist | Yes | T028, T030 | |
| FR-016 governance pointers | Yes | T031, T032 | |
| FR-017 changelog | Yes | T033 | |
| NFR-001 pure wheel | Yes | T029 + packaging guards (WP06/WP07 validation) | |
| NFR-002 dev fetch size | Yes | T005, T006 | |
| NFR-003 corpus parity | Yes | T015, T021 | live run at T015 |
| NFR-004 code quality | Partial | all WPs | see C1 |
| NFR-005 coverage | Yes | tests in every WP | |

**Charter Alignment Issues:** none. ATDD-first is explicit per WP (red test commits); gates are re-pointed, the freeze gate is removed by its own exit clause (ADR D-9), no allowlist grows; test policy uses named gate files only; draft PR, operator merges.

**Unmapped Tasks:** none.

**Metrics:**

- Total Requirements: 17 FR, 5 NFR, 7 C, 5 SC
- Total Tasks: 33 (8 WPs, 3-6 subtasks each)
- Coverage: 100 % of FRs; NFR-004 cross-cutting
- Ambiguity Count: 2 (U1, U2)
- Duplication Count: 0
- Critical Issues Count: 0

## Next Actions

No CRITICAL/HIGH findings: proceed to implementation. Carry C1 into each WP's validation and review; resolve U1/U2 at implementation time and record them in `traces/design-decisions.md`.
