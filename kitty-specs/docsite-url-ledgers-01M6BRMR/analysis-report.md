---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: docsite-url-ledgers-01M6BRMR
mission_id: 01M6BRMR1VJ9DJZP4R04K1QMJT
generated_at: '2026-11-01T14:47:28.438024+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/docsite-url-ledgers-01M6BRMR/spec.md
    sha256: 51ff83386c64cf1ea2cb156be6a07a29c112085c21ffcde2d1b7ffa802509447
  plan.md:
    path: kitty-specs/docsite-url-ledgers-01M6BRMR/plan.md
    sha256: d032c536088915db3a03e62233c8f68bb6da65a18f53fbde976601428f6a9e8e
  tasks.md:
    path: kitty-specs/docsite-url-ledgers-01M6BRMR/tasks.md
    sha256: 0e1a2fed9fe9953db6adbd258d1221302bd5f145e7102eaa21b3edb471b3f853
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  low: 3
  medium: 1
  high: 0
  critical: 0
  info: 0
findings:
- id: I1
  severity: low
  category: inconsistency
  summary: Decision Moment answer records the route as 'a/b.html' while research D1 and the contracts settle on a leading slash '/a/b.html'.
- id: U1
  severity: medium
  category: underspecification
  summary: NFR-001 depends on a local DocFX build; the container needs .NET from the Ubuntu archive and PlantUML fences stubbed, so the evidence method must be recorded.
- id: C1
  severity: low
  category: coverage
  summary: WP03 appends to site/moves.yaml and regenerates redirect_map.yaml, which WP01 owns; recorded as an out-of-map edit, no overlap in owned_files.
- id: I2
  severity: low
  category: inconsistency
  summary: ADR D-5 says dir/README.html redirects to dir/; the DocFX map uses dir/index.html, the same page under DocFX. The doc-kitty generator maps it later.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | LOW | decisions/, research.md D1 | Decision Moment answer says `a/b.html`; research and contracts say `/a/b.html`. | The leading slash is the refinement for doc-kitty's format; note it in the design-decisions tracer (already done). |
| U1 | Underspecification | MEDIUM | spec NFR-001, WP01 T004/T006, WP03 test strategy | Local DocFX evidence depends on environment workarounds. | Record the exact build commands and the PlantUML stub in the PR "Tests run". |
| C1 | Coverage | LOW | WP03 T013 | Out-of-map, append-only edit of WP01-owned files. | Keep it append-only and mention it in the commit. |
| I2 | Inconsistency | LOW | spec US4 scenario 3, ADR D-5 rule 1 | `README.html` → `index.html` (DocFX) vs `dir/` (doc-kitty). | No change: the ledger stores DocFX routes; #6933 maps `index.html` to `dir/`. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 baseline ledger | Yes | T003 | |
| FR-002 containment test | Yes | T001 | |
| FR-003 moves ledger | Yes | T003 | |
| FR-004 map from ledger | Yes | T004 | |
| FR-005 ledger validity | Yes | T001, T002 | |
| FR-006 #3914 reconcile | Yes | T001, T003 | |
| FR-007 no Mission-scoped map | Yes | T004, T007–T010 | |
| FR-008 ADR stubs | Yes | T011, T012 | |
| FR-009 architecture fold | Yes | T011, T012 | |
| FR-010 repoint references | Yes | T014 | |
| FR-011 one-index test | Yes | T011 | |
| FR-012 drift report | Yes | T004, T006 | |
| NFR-001..004 | Yes | T001, T004, test strategies | |
| C-001..007 | Yes | WP constraints sections | |

**Charter Alignment Issues:** none. ATDD-first is a first subtask in each WP; single authority (`moves_ledger.py`); immutable history guarded by occurrence-map exceptions; test policy honours `NO_FULL_HEAVY_SUITES_IN_MISSION`.

**Unmapped Tasks:** none (T015 maps to C-007 / delivery hygiene).

**Metrics:**

- Total Requirements: 12 FR, 4 NFR, 7 C, 5 SC
- Total Tasks: 15
- Coverage: 100%
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

### Next Actions

No CRITICAL or HIGH findings. Proceed to implementation; address U1 by recording the DocFX evidence method in the PR.
