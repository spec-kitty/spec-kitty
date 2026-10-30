---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: issue-6693-red-main-refs-to-directive-01M66YZX
mission_id: 01M66YZXX85Q4GEC0R3D77D440
generated_at: '2026-10-30T17:58:12.038193+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/issue-6693-red-main-refs-to-directive-01M66YZX/spec.md
    sha256: 0d89967f03e9af846c53ffad7d2bb2d395314571af98d438641d5adc3e4e0c87
  plan.md:
    path: kitty-specs/issue-6693-red-main-refs-to-directive-01M66YZX/plan.md
    sha256: 0e9ef7fc702ab5b30cab40910b45814b010bdb1ae4b23368bd5d2d5c8d28be40
  tasks.md:
    path: kitty-specs/issue-6693-red-main-refs-to-directive-01M66YZX/tasks.md
    sha256: 35bb1c6efef347ca2e2e45d25550bfe1212582ce12cd8c87b62c9e0934ec058d
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  high: 0
  low: 2
  critical: 0
  medium: 1
  info: 0
findings:
- id: A1
  severity: medium
  category: ambiguity
  summary: FR-005's no-op-passable note conflates the guard's positive control with the fixed state, so the two-sided proof it asks for is not stated as a single checkable property.
- id: A2
  severity: low
  category: inconsistency
  summary: The WP01 prompt's phrase '346 -> 345 node count is what the broken state produced' reads as one transition rather than as two states (shipped 345, broken regeneration 346).
- id: A3
  severity: low
  category: style
  summary: spec.md's Rename-target paragraph names both the built-in and internal targets while occurrence_map.yaml classifies only the built-in term; the map explains why, but the spec does not point at that explanation.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | spec.md FR-005 (No-op passable column); plan.md IC-03 | FR-005 says the guard "fails on the pre-fix ledger (positive control: the fixed ledger passes on the same fixture)" — that names two states of the same test, not the positive control acceptance-criteria-non-vacuity actually requires (a known-good id resolving on the same fixture, so a blind probe cannot pass). | Restate FR-005's non-vacuity note as: negative assertion = every ledger id resolves; positive control = a known-good id resolves through the same resolver on the same fixture; red proof = revert the ledger and watch it fail. WP03's T010 already states this correctly, so only the spec wording needs aligning. |
| A2 | Inconsistency | LOW | tasks/WP01-vendor-pin-and-curated-edge.md, T004 | "346 → 345 node count is what the broken state produced" compresses two distinct states: the shipped graph holds 345 nodes, and the pre-fix regeneration produces 346. | Reword as "shipped 345 nodes; pre-fix regeneration emits 346 because of the orphan node". |
| A3 | Style | LOW | spec.md Rename-target paragraph | The paragraph names the internal-pack sibling rename (`spec-kitty-red-main-policy` → `SPEC_KITTY_RED_MAIN_POLICY`) while `occurrence_map.yaml` classifies only the built-in term; the map's header explains that the internal rename has no tracked core occurrence, but the spec does not cross-reference that reasoning. | Add a half-sentence pointing at `occurrence_map.yaml` for the internal-pack half. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 | yes | T001 | Pin bump both packs |
| FR-002 | yes | T003 | Curated edge |
| FR-003 | yes | T005-T009 | Five tests + fixture |
| FR-004 | yes | T011, T012 | Ledger + charter pointers |
| FR-005 | yes | T010 | New guard test |
| FR-006 | yes | T014 | Changelog entry |
| NFR-001 | yes | T001, T004 | Only the pins change under `packs/` |
| NFR-002 | yes | T005-T009, T013 | Stale-reference sweep |
| NFR-003 | yes | T004 | Zero-delta regeneration |
| C-001 | yes | T001 | Upstream-first |
| C-002 | yes | T005-T009, T012 | Historical wording preserved |
| C-003 | yes | T001 | One commit for both pins |
| SC-001 | yes | T002, T004 | Red evidence + fix |
| SC-002 | yes | T013 | Doctor/consistency clean |
| SC-003 | yes | T001, T004 | Only two tracked `packs/` files change |
| SC-004 | yes | T005-T009, T012 | Grep sweep |

**Charter Alignment Issues:** none. The mission edits no doctrine, respects the
pack-tier boundary and the template-source rule (open-packs authors, core pins),
carries `change_mode: bulk_edit` with a complete eight-category occurrence map, and
plans no full heavy suite.

**Unmapped Tasks:** none — every `T0xx` belongs to exactly one WP, and every WP declares
its `requirement_refs`.

**Metrics:**

- Total Requirements: 16 (6 FR, 3 NFR, 3 C, 4 SC)
- Total Tasks: 14
- Coverage % (requirements with >=1 task): 100%
- Ambiguity Count: 1
- Duplication Count: 0
- Critical Issues Count: 0

**Notes on the three findings.** None blocks implementation: A1 is a wording defect in
the spec's non-vacuity column while the task prompt already states the correct proof, and
A2/A3 are clarity defects in support prose. They are recorded here rather than edited
away so the readiness gate sees the artifact as it stands; each is corrected in the WP
that owns the file (WP01 for A2, WP03 for A1 alongside the guard test it describes).
