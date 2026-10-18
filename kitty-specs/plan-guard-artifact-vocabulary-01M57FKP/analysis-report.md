---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: plan-guard-artifact-vocabulary-01M57FKP
mission_id: 01M57FKP4Z0HV4E5AQVPQEKX31
generated_at: '2026-10-18T12:35:25.933919+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/plan-guard-artifact-vocabulary-01M57FKP/spec.md
    sha256: b8df4efd5aa37009a84a6c57af138237113592fcac3cf80fabb1e45f3ff04be4
  plan.md:
    path: kitty-specs/plan-guard-artifact-vocabulary-01M57FKP/plan.md
    sha256: 91401f6f570a71a02cba78b6018b0385943c9a195a33b4e09b39ca7a933a3101
  tasks.md:
    path: kitty-specs/plan-guard-artifact-vocabulary-01M57FKP/tasks.md
    sha256: 192070e7c5b8a549d733b4c7842a65e62bb60e799f6b0b15e012d06288994e2c
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 2efd56dd3a968d08fa0b764f7e554d4d64963b46707d77c06c3d4cc7957636a0
verdict: ready
issue_counts:
  medium: 1
  high: 0
  critical: 0
  low: 1
  info: 1
findings:
- id: M1
  severity: medium
  category: test-coverage
  summary: The cross-family parity test (FR-004) is only non-vacuous if it routes through the real gather_artifact_presence; a synthetic present_artifacts= fixture would pass vacuously (that is why the bug hid).
- id: L1
  severity: low
  category: ci-visibility
  summary: WP01's source edit is in packs/ but its tests live in tests/runtime|next|architectural; the per-PR shard router may not auto-run them, so they must be run as orchestrator breadth.
---

## Specification Analysis Report

Mission `plan-guard-artifact-vocabulary-01M57FKP` (#6388). Artifacts: spec.md, plan.md, tasks.md,
research.md, data-model.md, contracts/, quickstart.md. Grounded + reproduced by a profile-loaded opus
squad (architect + paula-patterns). Charter: compact; no MUST conflicts for this scope.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| M1 | Test non-vacuity | MEDIUM | WP01 T001 / FR-004 / contracts C-PLAN-4 | The parity test must dispatch each family through the REAL `gather_artifact_presence` against an on-disk artifact-present fixture. Every existing plan guard test injected `present_artifacts=` synthetically, which is exactly why the defect passed them all. | Reviewer must confirm the parity test uses the real gatherer, not a hand-built snapshot; red-first (plan arm red pre-fix) is the proof. Non-blocking (captured in the WP prompt). |
| L1 | CI visibility | LOW | WP01 owned_files | The P0 edit is `packs/built-in/missions/plan/expected-artifacts.yaml` (a packs change); the verifying tests are under `tests/runtime`/`tests/next`/`tests/architectural`. The shard router keys on source dir, so the PR's own CI may skip them. | Orchestrator runs those dirs as integrated breadth before PR-ready; noted in tasks.md guardrails. |
| I1 | Coverage (info) | INFO | spec.md, tasks.md | #6388 is the owning gating issue (needs an issue-matrix verdict before WP approval). #3386/#3883/#4390/open-packs#41/#42/charter#42/core#6372 are context/done/separate. | Record the #6388 matrix row during review. |

### Adversarial lens (folded from grounding)

- **Reconciliation direction** is settled with evidence: the step contracts produce spec.md/research.md/
  plan.md; the guard checks those; only the manifest (and the descriptive mission.yaml copies) disagree.
  Option A (manifest-side, both axes) is correct; Option B (retag the guard) is rejected (recreates the
  block in reverse). `_evaluate_plan_guards` is explicitly NOT modified (C-001).
- **Both axes are required** (re-path + re-key): a path-only rename leaves `guard_failure_paths={}`.
  Captured in data-model.md and WP01 T002.
- **Coverage-floor re-trip risk**: `test_bridge_parity.py::test_coverage_floor_is_met` previously red on a
  step-scoped presence design that over-blocked plan; WP01 T005 verifies the re-key does not re-trip it.
- **mission.yaml is descriptive-only** (confirmed by grep: only `step_projection.py` reads `required_*`,
  from `expected-artifacts.yaml`), so WP02 is coherence-only with no runtime impact.

### Coverage Summary

| Requirement | WP | Subtasks |
|-------------|----|----------|
| FR-001 present spec.md reads present | WP01 | T001,T002,T005 |
| FR-002 manifest uses action vocabulary | WP01 | T002,T003,T005 |
| FR-003 genuine block names its path | WP01 | T004 |
| FR-004 cross-family parity (real gather) | WP01 | T001,T005 |
| FR-005 vocabulary-coherence CI guard | WP01 | T001,T005 |
| FR-006 descriptive mission.yaml + doc reconcile | WP02 | T007,T008,T009 |
| NFR-001 no non-plan regression | WP01 | T005,T006 |
| NFR-002 manifest schema-valid | WP01 | T002 |

### Charter Alignment

None violated. Single canonical vocabulary (C-002), guard untouched (C-001), keep MISSION_GOALS (C-003),
defect #2 out of scope (C-004), test-run guardrails (C-005) all represented as WP constraints.

### Metrics
- Requirements: 6 FR + 2 NFR + 5 C + 4 SC. Tasks: 10 subtasks / 2 WPs / 2 lanes. FR+NFR coverage: 100%.
- Ambiguity: 0 unresolved markers. Duplication: 0. Critical: 0.

## Next Actions

No CRITICAL/HIGH → ready to implement. M1 (parity-test non-vacuity) must be actively confirmed in WP01
review; L1 (shard masking) handled by orchestrator breadth. Record the #6388 issue-matrix row before WP
approval.
