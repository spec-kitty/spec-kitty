---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: residue-safe-migration-sweep-01M5SS0F
mission_id: 01M5SS0FBR3MKEB8X0CRYZC3AC
generated_at: '2026-10-25T16:28:32.270615+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/residue-safe-migration-sweep-01M5SS0F/spec.md
    sha256: 38058a01b58cb8310c9c0ba25ec6e809a8d0eecc202b56c06793ecfb51396020
  plan.md:
    path: kitty-specs/residue-safe-migration-sweep-01M5SS0F/plan.md
    sha256: c7532dfc1e0bafd457ddde97afc6cfbe92ea99d41e37d365db9b5e6ce98f10ae
  tasks.md:
    path: kitty-specs/residue-safe-migration-sweep-01M5SS0F/tasks.md
    sha256: 230a2a32498224547781e2a2f0af62a8109119ee2c461445b6ad1f2cabbf6dbc
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  high: 0
  medium: 2
  low: 3
  info: 0
findings:
- id: F1
  severity: medium
  category: inconsistency
  summary: 'plan.md concern map predates the post-tasks re-cut: IC-04 owns the walker gate and depends on IC-02, IC-01 owns the RESIDUE_DIRECTORY remedy, IC-05 puts baseline_slug_fields in feature_meta.py; tasks move these to WP03, WP06 and mission_metadata.py.'
- id: F2
  severity: medium
  category: ambiguity
  summary: FR-008 says the notice states the git-aware reason; WP01's draft RESIDUE_NOTICE text names only missing files, not that the folder is not a tracked Mission.
- id: F3
  severity: low
  category: coverage
  summary: NFR-004 (ruff format, diff coverage >= 90%) is mapped only to WP07; WP02/WP03/WP05 test strategies list mypy but not ruff format or a coverage check.
- id: F4
  severity: low
  category: coverage
  summary: SC-003 and SC-004 are referenced only by WP07; their real evidence is WP03 T015 and WP06 T026, traced by T030.
- id: F5
  severity: low
  category: inconsistency
  summary: Subtask T022 retired in the re-cut leaves a numbering gap; tasks.md records it explicitly.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| F1 | Inconsistency | MEDIUM | plan.md IC-01, IC-04, IC-05; tasks.md WP03/WP05/WP06 | The concern map predates the post-tasks re-cut. Tasks now: the gate reclassification is in WP03, WP05 lands before WP03, the `RESIDUE_DIRECTORY` remedy is in WP06, and `baseline_slug_fields` lives in `specify_cli/mission_metadata.py` (to avoid an 85-module audit import). | The concern map is explicitly "not work packages", so this does not block. Reviewers should treat tasks.md and the WP prompts as authoritative, and the PR body should name the drift. |
| F2 | Ambiguity | MEDIUM | spec.md FR-008, US1 scenario 6; WP01 T003 | The FR asks the notice to state the git-aware reason. The drafted text says only "no mission_id and no spec.md or meta.json". | During WP01, add "not a tracked Mission" (git-aware mode) to the reason; the WP01 review checks it. |
| F3 | Coverage | LOW | spec.md NFR-004; WP02/WP03/WP05 Test Strategy | `ruff format --check --force-exclude` and diff coverage are not listed in every code WP. | Implementers run ruff and ruff format on changed files in each WP; WP07 T030 records the diff-cover result. |
| F4 | Coverage | LOW | tasks.md coverage table | SC-003 and SC-004 are attributed only to WP07. | T030 already traces them to WP03 T015 and WP06 T026. No change needed. |
| F5 | Inconsistency | LOW | tasks.md Subtask Index | T022 is retired, leaving a numbering gap. | Recorded in tasks.md. No change needed. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 git-aware rule | Yes | T001, T002, T004 | WP01 |
| FR-002 tracked-only mode | Yes | T001, T004 | Every fallback setting tested |
| FR-003 one rule for every seam | Yes | T002, T019, T020, T021 | WP01, WP05 |
| FR-004 supersede four migrations | Yes | T009–T012 | WP03 |
| FR-005 repairs kept | Yes | T015 (parity, fallback repair) | WP03 |
| FR-006 predecessor slot | Yes | T012, T015 (order) | WP03 |
| FR-007 no re-sweep | Yes | T006, T007, T015 | WP02, WP03 |
| FR-008 once per folder | Yes | T003, T016–T018, T027 | WP01, WP04, WP07 |
| FR-009 P0 to guard | Yes | T027 | WP07 |
| FR-010 fabricated finding | Yes | T024–T026 | WP06 |
| FR-011 never blocks or deletes | Yes | T025, T026 | `--fail-on` contract test |
| FR-012 one baseline owner | Yes | T023 | WP06 |
| FR-013 walker inventory | Yes | T014 | WP03 |
| NFR-001 byte-identical shipped migrations | Yes | T015, T030 | Command in WP03 and WP07 |
| NFR-002 zero false findings | Yes | T026 (corpus) | WP06 |
| NFR-003 git cost | Yes | T004 (spy) | WP01 |
| NFR-004 quality gates | Partial | T030 | See F3 |
| C-001 to C-006 | Yes | T025, T012, T030, T015 (C-006) | |
| SC-001 to SC-004 | Yes | T027, T015, T026 | See F4 |

**Charter Alignment Issues:** none.
- Red-first is satisfied: #6672 carries the `p0_repro` reproduction, and WP07 turns it into a per-PR guard.
- Single canonical authority is kept: one rule, `is_kitty_specs_residue` on top of `is_mission_dir`.
- Supersession is used instead of editing a migration (DIRECTIVE_044).
- No suppressions are planned.

**Unmapped Tasks:** none.

**Issue-matrix heads-up (non-gating):** #6669 and #6668 are cited without a qualifier, so each needs an issue-matrix row before approval. #6589, #6627, #6662, #6672 and #6673 are cited as context.

**Metrics:**

| Metric | Value |
|---|---|
| Total requirements | 27 (13 FR, 4 NFR, 6 C, 4 SC) |
| Total tasks | 29 subtasks across 7 WPs |
| Coverage | 100% of requirements have at least one task (NFR-004 partially) |
| Ambiguity count | 1 |
| Duplication count | 0 |
| Critical issues | 0 |

**Next Actions:** No critical or high findings, so implementation may proceed. Handle F2 inside WP01, and name F1 in the PR body.
