# Behavioural Contracts: plan guard/manifest vocabulary

No network/API interfaces; behavioural seams on existing in-process surfaces, each pinned by a test.

## C-PLAN-1 — present spec.md reads present (FR-001)
Given a plan mission dir with committed spec.md, `gather_artifact_presence(..., step_id="specify",
mission_family="plan")` yields `present_artifacts ⊇ {spec.md}` and `_evaluate_plan_guards` /
`evaluate_guards_strict` return `[]`. (Red pre-fix: `['Required artifact missing: spec.md']`.)

## C-PLAN-2 — manifest resolves the action vocabulary (FR-002)
`_presence_filenames_for('plan') ⊇ {spec.md}` and excludes the phantom `goals.md`;
`required_artifacts_for('specify','plan') == {spec.md}`, `('plan','plan') == {plan.md}`.

## C-PLAN-3 — genuine block names its path (FR-003)
For a plan mission at `specify` with spec.md ABSENT, `guard_failure_artifact_paths(...)` returns a
non-empty map keyed by `spec.md`.

## C-PLAN-4 — cross-family parity (FR-004)
For each family in {software-dev, research, documentation, plan}, with the step's required artifact
present on disk and presence gathered through the REAL `gather_artifact_presence`, the family's guard
returns `[]` (no spurious block).

## C-PLAN-5 — vocabulary-coherence guard (FR-005)
A corpus guard fails when a built-in mission type's manifest `required_by_step` keys diverge from its
runtime step-contract action ids, or it is missing step contracts. Red against the pre-fix plan
divergence, green after.

## C-PLAN-6 — no non-plan regression (NFR-001)
`software-dev`/`research`/`documentation` presence filename sets and guard outcomes are byte-identical
before/after (the per-(family,artifact_key) byte-compat characterization, minus the intentional plan
rows).
