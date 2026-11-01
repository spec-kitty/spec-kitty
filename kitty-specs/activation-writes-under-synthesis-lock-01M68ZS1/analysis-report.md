---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: activation-writes-under-synthesis-lock-01M68ZS1
mission_id: 01M68ZS1EJTGNEZG3K1R35A1BE
generated_at: '2026-10-31T12:49:54.719196+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/activation-writes-under-synthesis-lock-01M68ZS1/spec.md
    sha256: a33e48a05836f7862c9ac15d0d84ec03cf03827e913f1d2df378f191c9c62cc8
  plan.md:
    path: kitty-specs/activation-writes-under-synthesis-lock-01M68ZS1/plan.md
    sha256: f9241c13f198b20a43d16f4ed2aa436c80fa7fca51489fb13be33b6fff6d68fa
  tasks.md:
    path: kitty-specs/activation-writes-under-synthesis-lock-01M68ZS1/tasks.md
    sha256: c5fc060a8edb06d3926b1f95e690760592a9e3e8a503ed5a06f9c98158915ef3
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  high: 0
  critical: 0
  medium: 2
  low: 2
  info: 0
findings:
- id: A1
  severity: low
  category: consistency
  summary: WP03 originally owned a docs page that does not exist (docs/guides/charter-activation.md); the real page documenting the lock behaviour is docs/api/charter-commands.md.
- id: A2
  severity: medium
  category: coverage
  summary: The CHARTER_SYNTHESIS_LOCK_UNAVAILABLE arm (git not invocable, so the lock cannot be placed) has no direct test; the lock-held arm does.
- id: A3
  severity: low
  category: coverage
  summary: SC-004 had no owning work package until WP01/WP03 declared it.
- id: A4
  severity: medium
  category: scope
  summary: C-004 declares the compiled-catalog write (recompile_or_notify) out of scope but names no follow-up issue, so the remaining staleness window is only documented in the plan.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Consistency | LOW | tasks/WP03-cli-window-and-changelog.md | WP03 owned `docs/guides/charter-activation.md`, which does not exist; `finalize-tasks --validate-only` rejected it and the WP now owns `docs/api/charter-commands.md`, the page that actually states the current unlocked behaviour. | Resolved during finalize; implementer must still confirm the page. |
| A2 | Coverage | MEDIUM | spec.md FR-005; tasks/WP01 T003 | Only `CHARTER_SYNTHESIS_LOCK_HELD` is drilled end to end. `CHARTER_SYNTHESIS_LOCK_UNAVAILABLE` is reachable only when git cannot be invoked; the seam conversion covers it, but no test exercises that arm. | Accept as a documented coverage gap, or add one unit assertion monkeypatching `kernel.git_topology.git_common_dir` to raise `GitTopologyUnavailableError` and asserting the mapped code. Prefer adding it — it is a few lines. |
| A3 | Coverage | LOW | spec.md SC-004; tasks/WP01, WP03 | SC-004 (the pre-existing suites stay green, no new lock surface) was unreferenced. | Fixed: WP01 and WP03 now declare SC-004. |
| A4 | Scope | MEDIUM | spec.md C-004; plan.md Phase 0 table | The compiled-catalog write window stays unlocked and is declared out of scope, but no tracking issue exists. | Name it in the PR `## Deferred` section with the reason if it is still real after the fix; file an issue only if a concrete staleness case is found. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 | yes | T004, T009 | manager seam + CLI window |
| FR-002 | yes | T005, T010 | preset plan+apply |
| FR-003 | yes | T006 | `promote_activations` self-guards |
| FR-004 | yes | T007 | migration window incl. `_stamp_manifest` |
| FR-005 | yes | T003, T008, T009, T010 | coded refusal, text + `--json`, documented |
| FR-006 | yes | T001, T002, T003 | red-first two-writer + refusal tests |
| NFR-001 | yes | T004, T005, T006, T007 | no new lock surface (diff-level check in WP02 DoD) |
| NFR-002 | yes | T003 | sub-second timeout override |
| NFR-003 | yes | T001, T002, T003 | suite parity, no skips |
| C-001 | yes | T004, T005, T006, T007 | existing lock only |
| C-002 | yes | T004 | read-only paths untouched |
| C-003 | yes | T004, T007 | re-entrancy (`--resynthesize`) |
| C-004 | yes | T012 | out-of-scope stated in docs + PR Deferred |
| SC-001 | yes | T001 | red-then-green two-writer |
| SC-002 | yes | T002 | entry retained |
| SC-003 | yes | T003 | refusal + byte-identical files |
| SC-004 | yes | T009, T010, T011, T012 | suites + no new lock surface |

**Charter Alignment Issues:** none — the plan's charter check covers single canonical authority (the one lock), ATDD-first (T001–T003 before T004–T007), locality (four seams + two commands), and the `__all__` rule (no new public symbol).

**Unmapped Tasks:** none.

**Metrics:**

- Total Requirements: 13 (6 FR, 3 NFR, 4 C)
- Total Tasks: 12
- Coverage % (requirements with >=1 task): 100
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0
