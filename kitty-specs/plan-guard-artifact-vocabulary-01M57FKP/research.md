# Research: Fix plan-mission guard/manifest artifact-vocabulary mismatch (#6388)

## R1 — Root cause (reproduced on main @ 4.0.0rc8)
- **Decision**: Manifest `plan/expected-artifacts.yaml` is the stale outlier; the guard is correct.
- **Evidence (grounding squad, direct call on a real plan mission dir with committed spec.md)**:
  `_presence_filenames_for("plan")` = `{goals.md, research.md, plan.md}` (no spec.md) →
  `_evaluate_plan_guards(step_id=specify)` → `['Required artifact missing: spec.md']`;
  `required_artifacts_for('specify','plan')` = `[]` while `('goals','plan')` = `['goals.md']` →
  `guard_failure_paths={}`. The 4 plan step contracts write spec.md/research.md/plan.md; nothing
  writes goals.md (phantom).
- **Alternatives**: Option B (retag guard to goals.md) — rejected: guard dispatches on action id
  `specify` and the step contract writes spec.md, so B recreates the block in reverse and pushes the
  dead vocabulary into the authoritative layer.

## R2 — Both axes required
- **Decision**: Re-path (`goals.md`→`spec.md`) AND re-key (`goals`/`draft`→`specify`/`plan`).
- **Rationale**: path rename fixes the block (presence union); step-key rename fixes
  `guard_failure_paths` (step-keyed `required_artifacts_for`). A path-only change leaves symptom (b).

## R3 — mission.yaml is descriptive-only (confirmed this session)
- **Decision**: Reconcile both `mission.yaml` copies for coherence; non-load-bearing.
- **Evidence**: grep — only `step_projection.py` reads `required_*`, and only from
  `expected-artifacts.yaml`. No consumer of `mission.yaml` `artifacts.required`/`workflow.phases` on the
  gather/guard path.

## R4 — Parity test non-vacuity
- **Decision**: Route the cross-family parity test through the REAL `gather_artifact_presence`.
- **Rationale**: every existing plan guard test injected `present_artifacts` synthetically, bypassing
  the manifest-sourced presence set — the exact reason the bug passed all of them.

## R5 — AST/corpus risk
- **Decision**: No decision-site risk. The `_materialize_decision` exact-count test is now a floor (≥1).
  Watch: `test_configured_artifact_name.py` ten-tags source-pair map + the `('plan','output.goals.main',
  'goals.md')` row; `test_manifest.py` plan step ids + goals.md row; `test_bridge_parity.py::
  test_coverage_floor_is_met` (confirm the re-key does not re-trip the WP04 over-block).

## R6 — Supply-chain / dependencies
- **Decision**: N/A — no dependency added/changed. DIRECTIVE_051 controls not triggered.

## Out of scope
- Defect #2 (`profile_hint` composition default — charter#42), fires upstream; verification here is at
  the gather/guard structural level. `MISSION_GOALS` orphan removal is a separate campsite follow-up.
