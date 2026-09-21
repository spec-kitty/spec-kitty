---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: ci-prose-only-downroute-01M31T5S
mission_id: 01M31T5SRZDJ147ZEZG49HQNPV
generated_at: '2026-09-21T11:42:55.664281+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/ci-prose-only-downroute-01M31T5S/spec.md
    sha256: 8069c2dd79443c38d5927e6d53f685b272338e4aebcbd5542946ceb6a4e70bcd
  plan.md:
    path: kitty-specs/ci-prose-only-downroute-01M31T5S/plan.md
    sha256: 8f3ebd2909d2d93c1db4b5ef939f890a397ef81b25be411191fb8a03ff4af020
  tasks.md:
    path: kitty-specs/ci-prose-only-downroute-01M31T5S/tasks.md
    sha256: 27bdc41a7faac5b88d3a54a80bd074835610693e9f160d99f1b390f16bdf0a6d
  charter:
    path: .kittify/charter/charter.yaml
    sha256: a2b2f62cf1c0fa8987b67f6759d18bcc18b2fb47a8d3ad2783f8fac68b192c77
verdict: ready
issue_counts:
  low: 2
  high: 0
  critical: 0
  medium: 1
  info: 0
findings:
- id: I1
  severity: medium
  category: inconsistency
  summary: data-model.md PRProseVerdict invariant still echoes the retracted research R2 claim (prose_only==True implies no unmapped src); safety was relocated to the wiring.
- id: I2
  severity: low
  category: inconsistency
  summary: FR-005 and one SC reference a 'doctest lane' to enable, but no doctest lane exists; doctests are handled by fail-closed classification (R4), not a lane.
- id: C1
  severity: low
  category: coverage
  summary: NFR-001..004 are covered in WP Definitions of Done but not carried in any WP requirement_refs (only FR-### are machine-tracked); acceptable for cross-cutting NFRs, noted for traceability.
---

## Specification Analysis Report

Cross-artifact consistency check across `spec.md`, `plan.md`, `tasks.md`,
`research.md`, `data-model.md`, and `contracts/prose-only-classifier.md` for mission
`ci-prose-only-downroute-01M31T5S`, after the post-tasks adversarial squad revisions
(3 WPs, FR-001..009). The two squad blockers (coverage-gate starvation F1, phantom
routing group F2) and the false research R2 argument were resolved during the squad
fold, so this pass finds no CRITICAL/HIGH issues — only three minor consistency /
traceability items.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | data-model.md (PRProseVerdict invariants) vs research.md R2 | The entity invariant still states `prose_only == True ⟹ no unmapped src present`, the exact claim research R2 was corrected to retract. Safety is now structural in the wiring (every guard ANDed subtractive), not a classifier implication. | Reword the data-model invariant to match the corrected R2: safety comes from the wiring keeping `prose_only` subtractive, not from an implication about unmapped src. |
| I2 | Inconsistency | LOW | spec.md FR-005 / SC references | Wording implies enabling a "doctest lane"; there is no doctest lane — doctests run inside the module matrix and are protected by treating a changed `>>>`-bearing docstring as code (R4). | Reword FR-005 to "documentation/help-drift lane"; keep the doctest protection described as fail-closed classification. |
| C1 | Coverage | LOW | WP01/02/03 frontmatter `requirement_refs` | NFR-001..004 (isolation, fail-closed provability, type/lint cleanliness, no product code) appear in WP Definitions of Done but are not in any `requirement_refs`. | Acceptable — NFRs are cross-cutting and the CLI maps only FR-###. No action required; noted for traceability. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 prose-only classifier | yes | WP01 (T001–T003) | |
| FR-002 semantically-live content guard | yes | WP01 (T001,T003) | directive/encoding/doctest guards |
| FR-003 aggregate all-or-nothing | yes | WP02 (T007) | verdict in wiring (R9) |
| FR-004 down-route target set | yes | WP02 (T008) | now includes code shards |
| FR-005 positive docs enablement | yes | WP02 (T008) | |
| FR-006 fail-closed default | yes | WP01 (T002,T003) | |
| FR-007 gate_selection path purity | yes | WP02 (T007,T010) | separate-job mechanism |
| FR-008 wiring across three surfaces | yes | WP02 (T006–T008), WP03 (T012) | |
| FR-009 coverage-gate honesty | yes | WP03 (T011–T013) | |

**Charter Alignment Issues:** none. The design explicitly upholds DIRECTIVE_001
(architectural integrity — new module keeps `gate_selection.py` pure), DIRECTIVE_024
(locality — CI surfaces only), #2476/C-001 (single routing authority — separate-job
`prose_only` avoids the phantom group), and epic #4437 honesty (FR-009 prevents a new
false-fail). No `feature*` terminology introduced (C-003).

**Unmapped Tasks:** none. All of T001–T013 (incl. T008b) belong to exactly one WP.

**Metrics:**

- Total Requirements: 9 FR + 4 NFR + 4 C = 17
- Total Tasks: 13 subtasks across 3 WPs
- Coverage %: 100% of FRs have ≥1 task
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

## Next Actions

- No CRITICAL/HIGH issues → the mission is **ready** to implement.
- I1 (MEDIUM) and I2 (LOW) are planning-doc wording reconciliations that should be
  applied before implementers read the artifacts, but they do not block the gate.
- Proceed to `/spec-kitty.implement` (WP01 first; WP02 and WP03 in parallel after).
