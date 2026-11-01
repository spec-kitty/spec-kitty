---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: docsite-frontmatter-migration-01M6BRJK
mission_id: 01M6BRJK82753H4QXJBGCYVQ12
generated_at: '2026-11-01T14:47:37.505425+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/docsite-frontmatter-migration-01M6BRJK/spec.md
    sha256: ad1fdb3c23983cc663f1295a449d90e151eaae3975a3b64994d694a12bda5299
  plan.md:
    path: kitty-specs/docsite-frontmatter-migration-01M6BRJK/plan.md
    sha256: 198ade32b3725a3ed36f6295ed58818a059c92181e43a596439bbb5000765153
  tasks.md:
    path: kitty-specs/docsite-frontmatter-migration-01M6BRJK/tasks.md
    sha256: 98a9fe70052a8bbda3f61dda8007184a3625f079d77590a3fecab2833bf5e4a1
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  low: 2
  high: 0
  critical: 0
  medium: 2
  info: 0
findings:
- id: I1
  severity: medium
  category: inconsistency
  summary: FR-001 says the body hash compares the base and the working tree; research R-5 and WP01 T001 compare a file before and after the migration in memory, with --verify-against covering the base comparison.
- id: C1
  severity: medium
  category: coverage
  summary: NFR-002 (docs query unchanged for 3 sample queries) has no explicit task; WP03 T015 runs the docs tests but no before/after query comparison.
- id: U1
  severity: low
  category: underspecification
  summary: WP01 T001 leaves the test marker choice open ('architectural? No ... check neighbours').
- id: G1
  severity: low
  category: process
  summary: CLI auto-commits (scaffold, plan, tasks, status) lack the operator-required Co-Authored-By trailer; to be fixed in history compaction before the PR.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | spec.md FR-001; research.md R-5; tasks/WP01 T001 | Body-hash comparison point differs between spec and design | Implement per R-5 (in-memory before/after over the real corpus, plus `--verify-against origin/main` recorded in the PR); state the reading in the PR. R-5 records why a permanent git comparison is wrong (it would fail later legitimate ADR amendments). |
| C1 | Coverage | MEDIUM | spec.md NFR-002; tasks/WP03 T015 | No explicit before/after `docs query` comparison | During WP03 T015, run 3 `spec-kitty docs query` samples on the base and branch and diff them. |
| U1 | Underspecification | LOW | tasks/WP01 T001 | Marker choice left open | Match neighbouring `tests/docs/` fast tests. |
| G1 | Process | LOW | git history | CLI commits lack the co-author trailer | Fix during compaction. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 body hash | yes | T001 | see I1 |
| FR-002 audience shape | yes | T004, T014 | |
| FR-003 audience readers | yes | T008-T010 | |
| FR-004 excluded folders | yes | T016-T018 | verified in grounding too |
| FR-005 related slugs | yes | T006, T014 | |
| FR-006 external refs | yes | T006, T014 | |
| FR-007 related reader | yes | T012, T013 | |
| FR-008 ADR fields | yes | T005, T014 | |
| FR-009 shape invariant | yes | T011 | |
| FR-010 re-runnable | yes | T007 | |
| FR-011 build | yes | T016-T018 | |
| NFR-001 frontmatter-only | yes | T001, T015 | |
| NFR-002 docs query | partial | T015 | see C1 |
| NFR-003 fast checks | yes | T001, T011 | |
| NFR-004 quality | yes | all code WPs | |

**Charter Alignment Issues:** none. ATDD-first is planned per WP; single canonical authority via the contract module; no heavy suites.

**Unmapped Tasks:** none.

**Metrics:** 15 requirements (11 FR, 4 NFR) + 5 constraints; 18 tasks; coverage 100% (NFR-002 partial); ambiguity 1; duplication 0; critical 0.

**Next Actions:** proceed to implementation; fold I1/C1 into WP execution as noted.
