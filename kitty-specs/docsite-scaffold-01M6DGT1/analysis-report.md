---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: docsite-scaffold-01M6DGT1
mission_id: 01M6DGT1J6CRK7YSBA2ERGJ96C
generated_at: '2026-11-02T07:02:42.177423+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/docsite-scaffold-01M6DGT1/spec.md
    sha256: 0bf28ec024503a85e8955e9401880455582bb65a23f183ff8adf5a9adf66577b
  plan.md:
    path: kitty-specs/docsite-scaffold-01M6DGT1/plan.md
    sha256: 54b7f4f8b5bfd5aa0ca45fbed6f3658fdea8f8dc13099f1c7cc70ac540e6953b
  tasks.md:
    path: kitty-specs/docsite-scaffold-01M6DGT1/tasks.md
    sha256: 6ddc777855afca70e0e315f6b62b8684efaac0f9720d9215ac04bee57cc7073f
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  medium: 1
  low: 2
  critical: 0
  high: 0
  info: 0
findings:
- id: A1
  severity: medium
  category: inconsistency
  summary: The docs_site group lists .github/workflows/ci-router.yml, so every router edit also builds the site; the spec names 'its own workflow' but no cost bound.
- id: A2
  severity: low
  category: coverage
  summary: 'FR-009 is no-op passable until #6937 wires a dockitty-* gate; non-vacuity rests on the self-mutation fixture.'
- id: A3
  severity: low
  category: coverage
  summary: T012 (changelog fragment) maps to no spec requirement; it is a repository process rule (CLAUDE.md).
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | MEDIUM | spec.md FR-007; tasks/WP03 | The `docs_site` group includes `ci-router.yml`, so any router PR runs a ~640-page build. ADR D-11 asks for "its own workflow", which here is the shared router. | Keep (ADR D-11 wording) and record the cost in design-decisions; the build is bounded by `timeout-minutes: 20` (NFR-003). |
| A2 | Coverage | LOW | spec.md FR-009 | No `dockitty-*` gate is wired yet, so the invariant passes on an empty set. | Keep the self-mutation fixture in `tests/ci/test_docs_site_job.py` as the non-vacuity proof. |
| A3 | Coverage | LOW | tasks.md T012 | Changelog fragment has no requirement row. | No change; process rule from CLAUDE.md. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 site project | yes | T001, T003, T005 | |
| FR-002 config values | yes | T001, T003 | |
| FR-003 single exclusion authority | yes | T001, T002 | drift negative control |
| FR-004 section registry | yes | T001, T004 | |
| FR-005 make docs-site | yes | T008 | |
| FR-006 make docs-site-bump | yes | T006, T007, T008 | |
| FR-007 router job | yes | T009, T010, T011 | |
| FR-008 not required | yes | T009, T011 | |
| FR-009 --astro-config | yes | T006, T009 | A2 |
| NFR-001 no credential | yes | T009, T011 | |
| NFR-002 pinned inputs | yes | T003, T009, T011 | |
| NFR-003 bounded runtime | yes | T009, T011 | |
| NFR-004 code quality | yes | T002, T007 | |

**Charter Alignment Issues:** none. ATDD-first is encoded as the first subtask of every WP; the single exclusion authority is preserved with a parity test; no full heavy suites.

**Unmapped Tasks:** T012 (A3).

**Metrics:**

- Total Requirements: 13 (9 FR, 4 NFR) plus 6 constraints and 4 success criteria
- Total Tasks: 12
- Coverage %: 100
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

### Next Actions

No CRITICAL or HIGH findings: proceed to `/spec-kitty.implement WP01`. A1 is recorded as a design decision.
