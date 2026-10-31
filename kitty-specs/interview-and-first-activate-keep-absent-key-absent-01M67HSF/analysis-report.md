---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: interview-and-first-activate-keep-absent-key-absent-01M67HSF
mission_id: 01M67HSFXQJXPP4R8ARV1R4GT3
generated_at: '2026-10-30T23:27:11.738256+00:00'
analyzer_agent: pi-flash
input_artifacts:
  spec.md:
    path: kitty-specs/interview-and-first-activate-keep-absent-key-absent-01M67HSF/spec.md
    sha256: 3d35e918a75b0b7fa566b82d9c47413102bbba2ace195dfa78ed2c375719e1df
  plan.md:
    path: kitty-specs/interview-and-first-activate-keep-absent-key-absent-01M67HSF/plan.md
    sha256: 9d7cad26c9f2ad62d12c123b963411ed9326d2b6ce8d5b895d762ba5c785cb96
  tasks.md:
    path: kitty-specs/interview-and-first-activate-keep-absent-key-absent-01M67HSF/tasks.md
    sha256: 55fbc72e062878f65612fa49d6adeeeba91071da36f2a4592aac3543becfb536
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: unknown
issue_counts:
  low:
  medium:
  info:
  critical:
  high:
findings: []
---

---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: interview-and-first-activate-keep-absent-key-absent-01M67HSF
generated_at: '2026-10-30T23:30:00Z'
analyzer_agent: pi-flash
verdict: ready
issue_counts:
  critical: 0
  high: 0
  medium: 1
  low: 2
findings:
- id: I1
  severity: medium
  category: coverage
  summary: FR-009 (the FR-015 acceptance matrix rows) was mapped only to WP03, though the rows are written in WP01 and WP02.
  resolution: fixed before finalize-tasks — FR-009 moved to WP01/WP02 requirement_refs and dropped from WP03.
- id: U1
  severity: low
  category: underspecification
  summary: The spec does not fix the exact operator-facing message for the left-absent key; the tests pin a substring, not the full sentence.
  resolution: accepted — the message is not a contract surface, the pin asserts the key name and the `--narrow-activation` hint.
- id: C1
  severity: low
  category: coverage
  summary: The cascade path (`activate <kind> <id> --cascade ...`) reuses `ActiveCharterManager.activate`, so the guard applies per cascaded target, but no test drives a cascade explicitly.
  resolution: accepted — the guard is inside the one planner every cascade target goes through; the PR lists it as not separately tested.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Coverage | MEDIUM | tasks.md, tasks/WP01, tasks/WP02, tasks/WP03 | FR-009 was referenced only by WP03, while T004 and T008 write the acceptance rows in WP01 and WP02. | Fixed: FR-009 now belongs to WP01 and WP02. |
| U1 | Underspecification | LOW | spec.md FR-002, WP01 T003 | The spec asks the output to name the absent key and the narrowing flag; it does not quote the sentence. | Accept. The test pins the key name and the flag, which is what an operator reads for. |
| C1 | Coverage | LOW | spec.md Edge Cases (cascade) | No test activates through `--cascade` on an absent key. | Accept and record in the PR: the cascade calls the same planner per target. |

### Cross-artifact checks

- **Every FR has an owning WP**: FR-001..FR-010 all appear in at least one WP's `requirement_refs`; every SC is referenced.
- **Constraints are honoured by the design**: C-001 (no narrowing) is asserted by the #4253 tests and the new end-to-end tests; C-002 (no ledger schema change) — no new key is introduced; C-003 (`--only` / `--narrow-activation` unchanged) — `test_activate_only_6408.py` and the narrow interview tests run unchanged; C-004 (no migration change) — no file under `src/specify_cli/upgrade/` is touched; C-005 (`skill` / `mission-type` untouched) — pinned by `test_skill_freeze_warning_6458.py` and the mission-type seeding test; C-006 (never narrow an existing list) — present-list tests keep their assertions; C-007 (single write seam) — no `save` call is added.
- **Red-first is named per WP**: T001 and T005 both name the failing end-to-end test and the reason it is red on main.
- **Terminology**: the artifacts say "activation ledger" and "Migration Ledger", never bare "ledger".
