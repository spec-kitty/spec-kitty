---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: upgrade-dry-run-would-apply-heading-01M6BV1G
mission_id: 01M6BV1GGRS0JMA284R6GDY60G
generated_at: '2026-11-01T15:27:56.204724+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/upgrade-dry-run-would-apply-heading-01M6BV1G/spec.md
    sha256: 5688d6edbae57b7bec0f3cabaca7bf4ee2967071125f0ff4212b3e356cf018ec
  plan.md:
    path: kitty-specs/upgrade-dry-run-would-apply-heading-01M6BV1G/plan.md
    sha256: 4d0515e554813095b8d936e2b2976981c316547c44418e74ea479b5bcf0f2af0
  tasks.md:
    path: kitty-specs/upgrade-dry-run-would-apply-heading-01M6BV1G/tasks.md
    sha256: ce60f4e8a33d39afe8ae0d2ba1d86d99fd78281f920fa3f8120e37218d955863
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  low: 2
  medium: 1
  high: 0
  info: 0
findings:
- id: C1
  severity: medium
  category: coverage
  summary: SC-004 (a dry run still writes nothing) has no dedicated assertion in WP01's subtasks; it is covered only transitively by the existing module rows run in T006.
- id: I1
  severity: low
  category: inconsistency
  summary: WP01 T005 permits an out-of-map edit to src/specify_cli/upgrade/runner.py:620 (a stale comment) that is not in owned_files.
- id: U1
  severity: low
  category: underspecification
  summary: Tasks do not say whether the changelog fragment is renamed to the PR number at hand-off, while the fragment README asks for it.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | MEDIUM | tasks.md WP01, spec.md SC-004 | The "dry run writes nothing" invariant is pinned by the existing module's tree-digest rows, but no WP01 subtask names it as a thing to keep green. | Treat T006's full-module run as the SC-004 witness and say so in the WP history note; no new test is warranted (DIRECTIVE_041). |
| I1 | Inconsistency | LOW | tasks/WP01, T005 | T005 allows rewording a comment in `src/specify_cli/upgrade/runner.py`, which is outside the WP's `owned_files`. | The WP already requires a one-line rationale for any out-of-map edit; skip it unless the stale comment would genuinely mislead, keeping the diff scoped to the renderer. |
| U1 | Underspecification | LOW | tasks/WP02 T008 | The fragment filename convention asks for the PR number once known; tasks name `6234.fixed.md` only. | Rename to `<pr>.fixed.md` at hand-off if the PR number differs from the issue number, as `docs/changelog/unreleased/README.md` instructs. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 dry-run heading names the preview | Yes | T001, T002, T003 | Golden + renderer |
| FR-002 non-success marker | Yes | T001, T002, T003 | Golden |
| FR-003 real-run report byte-identical | Yes | T003, T006 | `_GOLDEN_APPLIED` unedited |
| FR-004 goldens become a deliberate oracle | Yes | T001, T003, T004 | Docstrings cite #6234 |
| FR-005 one decision site | Yes | T002 | Single `if/else` |
| NFR-001 dry run writes nothing | Yes | T006 | Existing module rows |
| NFR-002 rendering stays pure | Yes | T002, T006 | No raise, no I/O |
| NFR-003 complexity ceiling | Yes | T002, T006 | One `if/else` added |
| C-001 presentation only | Yes | T002 | No runner/registry edit required |
| C-002 no JSON/contract change | Yes | T002, T006 | Renderer only |
| C-003 same-fixture control | Yes | T003 | Golden pair |
| C-004 no gate weakening | Yes | T003, T004 | Retarget, never delete |
| C-005 ADR closing line | Yes | T006 | Golden asserts the tail |
| SC-001 dry-run text corrected | Yes | T001, T003 | |
| SC-002 real-run golden unedited | Yes | T003 | |
| SC-003 no skipped/deleted assertions | Yes | T003, T004 | |
| SC-004 dry run writes nothing | Partial | T006 | See C1 |

**Charter Alignment Issues:** none. The one recorded deviation (no REASONS canvas) is scoped by the SPDD paradigm itself, which excludes tiny fixes.

**Unmapped Tasks:** none.

**Metrics:**

- Total Requirements: 17 (5 FR, 3 NFR, 5 C, 4 SC)
- Total Tasks: 9
- Coverage %: 100 (SC-004 transitively, see C1)
- Ambiguity Count: 1 (U1)
- Duplication Count: 0
- Critical Issues Count: 0

## Next Actions

1. Proceed to implementation: `spec-kitty next --agent python-pedro --mission upgrade-dry-run-would-apply-heading --result success`.
2. During WP01, record the SC-004 witness (full module green, tree digest unchanged) in the WP history note.
3. At hand-off, rename the changelog fragment to the PR number if it differs from 6234.
