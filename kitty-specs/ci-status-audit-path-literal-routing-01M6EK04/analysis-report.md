---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: ci-status-audit-path-literal-routing-01M6EK04
mission_id: 01M6EK04QX173M8CHW8EYKVZNT
generated_at: '2026-11-02T17:55:03.055900+00:00'
analyzer_agent: claude
input_artifacts:
  spec.md:
    path: kitty-specs/ci-status-audit-path-literal-routing-01M6EK04/spec.md
    sha256: 6fb7565e288396bfff08210a9089dd102d90bf6337e65a34037a05846641fad9
  plan.md:
    path: kitty-specs/ci-status-audit-path-literal-routing-01M6EK04/plan.md
    sha256: 95e4195f6738751895fa52474f967beb48a051bad0fbf06c781d16fde417fc94
  tasks.md:
    path: kitty-specs/ci-status-audit-path-literal-routing-01M6EK04/tasks.md
    sha256: f8e87d64478630266608748fca640fd8c711fd5c759d794af726c5c77cf6f93b
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: unknown
issue_counts:
  low:
  critical:
  high:
  info:
  medium:
findings: []
---

# Specification Analysis Report — ci-status-audit-path-literal-routing-01M6EK04

Analyzed after `spec-kitty agent mission finalize-tasks` (planning commit `61635f15a`): `spec.md`
(6 FR / 3 NFR / 4 C / 3 SC), `plan.md` (3 implementation concerns, 5 design decisions),
`tasks.md` + one WP prompt (T001–T006), `issue-matrix.md` (1 row, issue #6879).

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | RESOLVED | spec.md SC-001/edge case, plan.md charter check, tasks/WP01 T001 | The negative control named `src/specify_cli/dashboard/**`, which does not exist in this tree (no `src/specify_cli/dashboard` package). A control over a non-existent subtree would pass vacuously. | FIXED pre-implement: the control is now `src/specify_cli/review/**` (an existing src-backed group), so the router probe demonstrably *can* match a group and simply does not match this one. |
| A1 | Ambiguity | LOW | tasks/WP01 T001 (3) | The negative control asserts "does NOT match the group"; without the positive assertion on the same fixture it would be a blind probe. | Already covered by T001 items (1)-(2) on the same `select_gates` fixture — same-router positive control is explicit in the WP; no action. |
| C1 | Coverage | INFO | tasks.md, finalize `requirement_refs_parsed` | FR-001..006, NFR-001..003 and SC-001..003 are all referenced by WP01; `success_criteria_coverage` reports 0 unreferenced criteria. | None. |

## Coverage summary (from finalize `requirement_refs_parsed` — authoritative)

| Requirement | WP | Requirement | WP |
|-------------|----|-------------|----|
| FR-001 | WP01 (T002, T003) | NFR-001 | WP01 (T003, T005) |
| FR-002 | WP01 (T003) | NFR-002 | WP01 (T003) |
| FR-003 | WP01 (T001, T002) | NFR-003 | WP01 (T005) |
| FR-004 | WP01 (T002, T003, T004) | SC-001 | WP01 (T001) |
| FR-005 | WP01 (T001, T003) | SC-002 | WP01 (T001, T005) |
| FR-006 | WP01 (T001) | SC-003 | WP01 (T005) |

9/9 FR+NFR mapped (C-005 was added after the first recording: the group stays non-src so it is not a code shard and does not narrow the FR-004 sensor over src/specify_cli/paths/**), 3/3 success criteria referenced, 0 unmapped subtasks: T001–T006 each appear in
WP01's `subtasks` frontmatter and in the tasks.md subtask index. Constraints C-001 (no registry
row), C-002 (guard file untouched) and C-003 (two authorities only) are restated in the WP prompt's
Definition of Done, so they are enforced at review, not only declared.

## Grounding verification performed while analysing

- `src/specify_cli/status/**`, `src/specify_cli/paths/**`, `src/kernel/paths.py` and
  `tests/audit/test_no_legacy_path_literals.py` all exist; the group's globs are therefore all live
  (`test_workflow_coherence.test_every_restored_filter_glob_is_live` rejects a dead glob).
- `scripts/ci/router_gate.ADVISORY_JOB_NAMES`, `tests/ci/_gh_if.eval_gh_if`,
  `scripts/ci/gate_selection.select_gates` and
  `tests/architectural/test_no_duplicate_suite_execution.AUTHORIZED_SUITE_INVOCATIONS_PER_JOB`
  are the surfaces the WP cites; all exist at the names used.
- The guard module's marker state was re-verified locally: `pytest tests/audit/test_no_legacy_path_literals.py -m "fast or unit" --collect-only -q`
  reports `0 collected, 8 deselected`, which is why FR-005 requires the lane's command to carry no
  marker expression and why SC-002 asserts a collected count.
