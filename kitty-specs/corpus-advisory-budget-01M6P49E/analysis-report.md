---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: corpus-advisory-budget-01M6P49E
mission_id: 01M6P49EBJZ15Q06S9XYQE61HX
generated_at: '2026-11-05T15:16:48.963260+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/corpus-advisory-budget-01M6P49E/spec.md
    sha256: 2094e6576eafc58d47fb5eda145331d2b3a57de53ef5d711d7885943981d17cc
  plan.md:
    path: kitty-specs/corpus-advisory-budget-01M6P49E/plan.md
    sha256: df3f70164558e9475be6c8dbf715144a2c09a39e9263c01a6a39ee51904789fa
  tasks.md:
    path: kitty-specs/corpus-advisory-budget-01M6P49E/tasks.md
    sha256: 112e814b7acbae9e3a54b6eb155e7de428216d90c89fde800c778669c728206c
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  high: 0
  critical: 0
  medium: 0
  low: 2
  info: 0
findings:
- id: C1
  severity: low
  category: coverage
  summary: FR-006 (selection semantics byte-identical) has no dedicated new assertion; it is proved by T006's diff review plus pre-existing live guards.
- id: T1
  severity: low
  category: consistency
  summary: The 75% rule in WP01 T002 checks the recorded MAX suite against the cap, which is stricter than the issue's p95 metric; the wording should say so explicitly so no reader thinks p95 was measured per-run in CI.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | LOW | spec.md FR-006; tasks.md WP01 T006 | FR-006 requires the selection semantics to stay byte-identical and is labelled `[ratchet]`, which the tactic allows to be satisfied by existing guards. There is no *new* assertion; the proof is T006's recorded `git diff` plus the five pre-existing guard modules named in T005. | Keep as is: adding a second assertion over `continue-on-error`/trigger would create a second source of truth for facts `tests/ci/test_corpus_blocking_home.py` and `tests/architectural/test_ci_corpus_trigger_completeness.py` already own. Cite both in the PR body so the ratchet is visible. |
| T1 | Consistency | LOW | tasks/WP01 T002 item 3; spec.md NFR-001 | The machine-checked rule is `recorded_max_suite / cap <= 0.75`, while the issue states `p95 / cap <= 0.75`. The recorded value is a max, so the guard is stricter than the acceptance metric — but the prompt must not let a reader believe CI measures p95. | Phrase the guard's docstring and the PR body as "the recorded worst case (a p95 upper bound) is within 75% of the cap; the measured p95 is 20.3/31 = 65%". |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 cap derived + guard | yes | T001, T003 | red-first receipt recorded in T001 |
| FR-002 recorded headroom line | yes | T003 | guard reports absence (existing mutation case) |
| FR-003 cap raised to derived value | yes | T003 | 31 = ceil((19:55 + 0:30) x 1.5) |
| FR-004 step budget below cap | yes | T004, T002 | guard rejects step >= cap |
| FR-005 legible expiry notice | yes | T004, T002 | wording asserted, not just presence |
| FR-006 selection unchanged | yes | T005, T006 | existing guards + recorded diff (finding C1) |
| FR-007 rationale recorded | yes | T003, T007 | workflow comment + reference page |
| NFR-001 75% ratio | yes | T002, T008 | machine-checked against the record (finding T1) |
| NFR-002 headroom formula | yes | T001 | extends the guard that owns the formula |
| NFR-003 guard cost | yes | T002, T005 | text-only parsing, `fast` marker |
| NFR-004 honest green | yes | T004, T006 | notice + unchanged job-level `continue-on-error` |
| C-001 no shard/matrix | yes | T005, T006 | both pinned guards run unchanged |
| C-002 no gate weakened | yes | T006 | diff review of the wiring keys |
| C-003 reuse #5378 convention | yes | T001, T003 | no new formula |
| C-004 advisory posture | yes | T004 | job-level `continue-on-error` untouched |
| SC-001 ratio <= 0.75 | yes | T002 | 0.64 recorded |
| SC-002 guard red then green | yes | T001, T002 | mutation controls |
| SC-003 semantics byte-identical | yes | T005, T006 | see C1 |
| SC-004 expiry annotation | yes | T004, T008 | notice wording + doc |

**Charter Alignment Issues:** none. The mission keeps one authority for the cap formula, touches one
workflow plus two guard modules, and writes the cap guard before the workflow value (ATDD-first).

**Unmapped Tasks:** none — T001-T009 all belong to WP01 or WP02.

**Metrics:**

- Total Requirements: 19 (7 FR, 4 NFR, 4 C, 4 SC)
- Total Tasks: 9
- Coverage %: 100
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

**Next Actions**

1. Implement WP01 red-first (T001, T002 before T003/T004) and record the failure text.
2. Implement WP02 after WP01 lands the numbers; rename the fragment to the PR number.
3. Apply the T1 wording in the guard's docstring and the PR body.
