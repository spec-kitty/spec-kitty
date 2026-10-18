---
work_package_id: WP01
title: Manifest reconcile + verification + hardening (P0 core)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
planning_base_branch: fix/plan-guard-artifact-vocabulary
merge_target_branch: fix/plan-guard-artifact-vocabulary
branch_strategy: Planning artifacts for this mission were generated on fix/plan-guard-artifact-vocabulary. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/plan-guard-artifact-vocabulary unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - P0 core
history:
- timestamp: '2026-10-18T09:20:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/built-in/missions/plan/
create_intent:
- tests/architectural/test_mission_type_vocabulary_coherence.py
execution_mode: code_change
mission_id: 01M57FKP4Z0HV4E5AQVPQEKX31
model: sonnet
owned_files:
- packs/built-in/missions/plan/expected-artifacts.yaml
- tests/runtime/next/test_cli_guard_family.py
- tests/next/test_guard_failure_paths_3883.py
- tests/specify_cli/runtime/test_configured_artifact_name.py
- tests/dossier/test_manifest.py
- tests/architectural/test_mission_type_vocabulary_coherence.py
role: implementer
tags: []
tracker_refs: []
wp_code: WP01
---

# Work Package Prompt: WP01 — Manifest reconcile + verification + hardening

## ⚡ Do This First: Load Agent Profile

Load your agent profile via `/spk-charter-profile-load` with profile id **`python-pedro`**, adopt its
scope/boundaries, then read `kitty-specs/plan-guard-artifact-vocabulary-01M57FKP/{spec.md,plan.md,research.md,data-model.md,contracts/behavioral-contracts.md}`.

## Objective

Fix the P0 (#6388): reconcile `packs/built-in/missions/plan/expected-artifacts.yaml` to the runtime
action vocabulary so a committed `spec.md` reads present at the plan `specify` guard and
`guard_failure_paths` is restored — **without touching `_evaluate_plan_guards`** (the guard is already
correct). Add the cross-family parity test (through the REAL `gather_artifact_presence`), the
vocabulary-coherence corpus guard, and the `guard_failure_paths` regression; update the change-together
mirrors. Work in the lane worktree; stay within `owned_files`.

## Context & Constraints

- **Root cause**: the plan guard checks `spec.md`/`research.md`/`plan.md` (what the step contracts
  produce), but the manifest declares `goals.md`/`research.md`/`plan.md` under step-keys
  `goals`/`research`/`draft`. So `_presence_filenames_for("plan")` never includes `spec.md` (block), and
  `required_artifacts_for('specify','plan')==[]` (empty `guard_failure_paths`). `goals.md` is a phantom.
- **Both axes required** (see `data-model.md`): re-path `goals.md`→`spec.md` AND re-key `goals`→`specify`,
  `draft`→`plan`. A path-only rename leaves `guard_failure_paths` empty.
- **Do NOT modify** `src/runtime/next/runtime_bridge_cores.py` (`_evaluate_plan_guards`), C-001.
- **Schema** is `extra="forbid"`: change only step-keys, `path_pattern`s, and comments; preserve
  `schema_version`/`manifest_version`/field shapes (NFR-002).
- **No non-plan regression** (NFR-001): software-dev/research/documentation presence sets unchanged.
- **Shard-masking**: the source edit is in `packs/`; run the `tests/runtime`/`tests/next`/`tests/architectural`
  dirs locally regardless of CI shard routing.
- Do NOT run `make test-full`; do NOT regenerate `.github/ci-shard-timings.json`. Keep `MISSION_GOALS`.

## Subtasks & Detailed Guidance

### T001 — Red-first: parity test + coherence guard + plan assertions (RED pre-fix)

**Purpose**: Pin the fix with tests that fail against the current (pre-fix) manifest.

- **Cross-family parity** (IC-04) in `tests/runtime/next/test_cli_guard_family.py`: for each family in
  `{software-dev, research, documentation, plan}`, build an on-disk mission dir with the step's required
  artifact present, gather presence through the **real** `gather_artifact_presence` (NOT synthetic
  `present_artifacts=`), and assert the family's guard returns `[]`. The `plan`/`specify` case is RED now.
- **Vocabulary-coherence corpus guard** (IC-05) — new file
  `tests/architectural/test_mission_type_vocabulary_coherence.py`: for each built-in mission type, assert
  its manifest `required_by_step` keys are a subset of its runtime step-contract action ids (and that it
  has step contracts). Read both from their canonical loaders (`charter.activation.manifest_loader` and
  the step-contract corpus), not hardcoded lists. RED now for `plan` (manifest keys goals/draft ∉ action
  ids specify/plan).
- **Plan presence/guard assertions**: a plan mission dir with committed `spec.md` →
  `gather_artifact_presence(..., step_id="specify", mission_family="plan")` ⊇ {spec.md};
  `_evaluate_plan_guards` returns `[]`; `_presence_filenames_for('plan')` ⊇ {spec.md};
  `required_artifacts_for('specify','plan')=={spec.md}`. RED now.

Run and confirm RED before T002.

### T002 — Reconcile the manifest (IC-01)

- Edit `packs/built-in/missions/plan/expected-artifacts.yaml`:
  - `required_by_step`: rename key `goals`→`specify` with `path_pattern: spec.md` (keep `artifact_key`
    coherent — e.g. `output.spec.main`); rename key `draft`→`plan` (path_pattern `plan.md` unchanged);
    keep `research` (research.md); `structure`/`review`/`done` carry no required artifact (drop the empty
    `structure`/`done` keys or keep them empty — harmless, no runtime action id).
  - Rewrite the now-false header comment (it claims no plan guard branch exists / mirrors mission.yaml
    state ids — both false post-#3386; `_GUARD_TABLES["plan"]` is live).
  - Keep the file schema-valid (`extra="forbid"`).
- Make T001's plan assertions + parity + coherence guard GREEN.

### T003 — Update change-together mirrors

- `tests/specify_cli/runtime/test_configured_artifact_name.py`: update the `('plan','output.goals.main',
  'goals.md')` row to the new `(plan, <spec artifact_key>, spec.md)`; update the exactly-ten-tags
  source-pair map if the `(family,artifact_key)` pairing changed (count likely stays 10 — spec.md is
  already a tag); keep `test_every_built_in_type_has_a_resolvable_manifest` green.
- `tests/dossier/test_manifest.py`: update the plan `get_step_ids()` assertion and the `goals.md` row to
  the new keys/artifact.
- These are **intentional contract updates**, not regressions — note that in the diff/handoff.

### T004 — guard_failure_paths regression (IC-03)

- In `tests/next/test_guard_failure_paths_3883.py`, add a plan `specify` case: with `spec.md` ABSENT,
  assert `guard_failure_artifact_paths(...)` (family `plan`) returns a non-empty map keyed by `spec.md`.
  (Family-aware post-#4390; see the existing cases.)

### T005 — Verify green + no re-trip

- Run the narrow set (foreground): the new/updated tests + `tests/runtime/test_bridge_parity.py::test_coverage_floor_is_met`
  (the WP04 note warns a step-scoped presence design over-blocked plan — confirm the re-key does not
  re-trip it).

### T006 — Validate blast radius (narrow, foreground)

- `mark-status` T001–T005 as done. Run the WP01 blast-radius set (see Test Strategy). Record commands +
  pass/fail counts for the PR.

## Branch Strategy

Planning/base = final merge target = `fix/plan-guard-artifact-vocabulary` (PR to `main`, operator
merges). Execution worktrees are allocated per computed lane from `lanes.json` — do not pick a base
branch manually.

## Test Strategy (red-first)

```bash
PYTHONPATH="$PWD/src:$PWD" /home/stijn/Documents/_code/SDD/fork/spec-kitty/.venv/bin/python -m pytest \
  tests/runtime/next/test_cli_guard_family.py \
  tests/architectural/test_mission_type_vocabulary_coherence.py \
  tests/next/test_guard_failure_paths_3883.py \
  tests/specify_cli/runtime/test_configured_artifact_name.py \
  tests/dossier/test_manifest.py \
  tests/runtime/test_bridge_parity.py -q
```
Confirm the parity/coherence/plan assertions are RED before T002 and GREEN after. Do NOT run `make test-full`.
`ruff check` / `ruff format --check --force-exclude` / `mypy` clean on changed Python files.

## Definition of Done

- Plan `specify` guard reads a committed `spec.md` present (`_evaluate_plan_guards`→`[]`); `_presence_filenames_for('plan')`⊇{spec.md} and excludes `goals.md`; `required_artifacts_for('specify','plan')=={spec.md}`.
- `guard_failure_paths` non-empty for a genuine plan miss; parity + coherence guards green (red pre-fix).
- `_evaluate_plan_guards` unchanged; manifest schema-valid; non-plan families byte-identical.
- `ruff`/`mypy` clean on changed files.

## Risks & Reviewer Guidance

- **Reviewer**: confirm the parity test routes through the REAL `gather_artifact_presence` (not synthetic) — this is the non-vacuity crux.
- Confirm `_evaluate_plan_guards` / `runtime_bridge_cores.py` is NOT in the diff.
- Confirm the change-together mirror edits are intentional contract updates, and `test_coverage_floor_is_met` is not re-tripped.
- Confirm `MISSION_GOALS` is still defined (no orphan removal in this WP).
