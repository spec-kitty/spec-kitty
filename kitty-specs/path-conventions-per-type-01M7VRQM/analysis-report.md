---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: path-conventions-per-type-01M7VRQM
mission_id: 01M7VRQM1E45PQDM459J7PTNYD
generated_at: '2026-11-20T06:40:02.708887+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: .worktrees/path-conventions-per-type-01M7VRQM-coord/kitty-specs/path-conventions-per-type-01M7VRQM/spec.md
    sha256: 8379b0efea3c113a015a8e10e1557bc64e0991c3473d5a1f9e1cf4fedbd2904c
  plan.md:
    path: .worktrees/path-conventions-per-type-01M7VRQM-coord/kitty-specs/path-conventions-per-type-01M7VRQM/plan.md
    sha256: 8fc4b42a411c050213e8445ddbc0e29e821ad54ed8ab85851a09175b91f9ea7b
  tasks.md:
    path: .worktrees/path-conventions-per-type-01M7VRQM-coord/kitty-specs/path-conventions-per-type-01M7VRQM/tasks.md
    sha256: 0bb424cfcad01f912551ca0d9c93e60632a107c40e91d302835aca5237229f1f
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: blocked
issue_counts:
  medium: 1
  low: 2
  high: 1
  critical: 0
  info: 0
findings:
- id: F1
  severity: high
  category: inconsistency
  summary: spec.md US4 scenario 6 says orchestrator-api offers no waiver, while research.md R-4 says the meta.json waiver applies wherever accept is evaluated (including orchestrator-api); FR-013 only names the per-run waiver.
- id: C1
  severity: medium
  category: coverage
  summary: NFR-003 (ruff/format/mypy/C901 on touched code) is mapped to WP01 only, but applies to every code WP; each WP prompt carries the lint commands, so the gap is mapping-only.
- id: U1
  severity: low
  category: underspecification
  summary: The brief names contracts/precedence-contract.md as a doc to update; the original is no longer in the tree. WP05 amends the ADR and this Mission ships its own contract, which research R-6 records.
- id: I1
  severity: low
  category: inconsistency
  summary: WP05 maps C-002 (no pack schema change) although no WP changes packs; the constraint is honoured by omission.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| F1 | Inconsistency | HIGH | spec.md US4 scenario 6, FR-013; research.md R-4; tasks/WP02, WP04 | Is the meta.json waiver honoured on the orchestrator-api accept/consolidate path? The spec says no waiver there; research says the meta.json declaration applies everywhere. | Get an operator ruling. Then align spec FR-013, research R-4, contracts/accept-waiver-contract.md and the WP02/WP04 prompts to one answer. |
| C1 | Coverage | MEDIUM | tasks.md requirement mapping | NFR-003 is mapped to WP01 only. | Map NFR-003 to every code WP (WP02, WP03, WP04); each prompt already runs the checks. |
| U1 | Underspecification | LOW | brief scope item 5; research.md R-6 | The original precedence contract is gone; the ADR is its durable record. | No change; WP05 amends the ADR. |
| I1 | Inconsistency | LOW | tasks/WP05 requirement_refs | C-002 is mapped to the docs WP. | Optional: leave it as is; the constraint holds by omission. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 per-type section shape | Yes | T001–T003 | |
| FR-002 precedence per type | Yes | T010–T011 | |
| FR-003 unknown type id fails closed | Yes | T001, T004 | |
| FR-004 section validation | Yes | T001, T003 | |
| FR-005 flat unchanged | Yes | T001, T005 | positive control: unedited tests |
| FR-006 per-type remedy first | Yes | T013 | |
| FR-007 mkdir only for deliverables | Yes | T013 | |
| FR-008 copy route demoted | Yes | T013 | |
| FR-009 per-run waiver | Yes | T008, T015–T017 | |
| FR-010 meta.json waiver | Yes | T006–T007, T012 | see F1 |
| FR-011 reason required | Yes | T015–T016 | |
| FR-012 waiver before --lenient | Yes | T013 | |
| FR-013 orchestrator strict | Yes | T015, T018 | see F1 |
| NFR-001 one read / lazy roster | Yes | T001, T010 | |
| NFR-002 no config edits | Yes | T005 | |
| NFR-003 lint/type/complexity | Partial | T005 (+ per-WP verify steps) | see C1 |
| C-001 single caller | Yes | T014, T019 | |
| C-002 no pack change | Yes (by omission) | — | |
| C-003 remap-only | Yes | T010 | |
| C-004 #3783 policy / pins | Yes | T014 | |
| C-005 subkey only | Yes | T001 (existing test kept) | |
| C-006 waivers path-only | Yes | T012, T015 | |

**Charter Alignment Issues:** none. ATDD (red-first subtasks lead every code WP), the single canonical authority (one reader, a generalized waiver reader, the layered roster seam reused) and the test policy (targeted modules + named gate) are respected.

**Unmapped Tasks:** none.

**Metrics:**

- Total Requirements: 22 (13 FR, 3 NFR, 6 C) + 4 SC
- Total Tasks: 22
- Coverage: 100% of FR/NFR/C have at least one task (NFR-003 partial mapping)
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

## Next Actions

- F1 (HIGH) blocks implementation until it is resolved: ask the operator, then align spec/research/contract/prompts and re-run `/spec-kitty.analyze`.
- C1 can be fixed in the same pass with `spec-kitty agent tasks map-requirements`.
