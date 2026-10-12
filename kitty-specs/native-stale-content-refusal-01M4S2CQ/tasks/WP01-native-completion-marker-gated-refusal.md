---
work_package_id: WP01
title: Native completion enforces the API-authored marker-gated refusal
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
planning_base_branch: issue-5879-native-stale-content-refusal
merge_target_branch: issue-5879-native-stale-content-refusal
branch_strategy: Planning artifacts for this mission were generated on issue-5879-native-stale-content-refusal. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5879-native-stale-content-refusal unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Native enforcement
history:
- at: '2026-10-12T22:10:00Z'
  actor: system
  action: Prompt generated via the canonical tasks step
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/next_cmd.py
- src/specify_cli/orchestrator_api/runtime_next.py
- src/specify_cli/cli/commands/agent/tasks_finalize.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- tests/specify_cli/orchestrator_api/test_planning_client_journey.py
- tests/specify_cli/orchestrator_api/test_runtime_next.py
- tests/specify_cli/design/test_design_authoring.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Native completion enforces the API-authored marker-gated refusal

## Objectives & Success Criteria

- Native `spec-kitty next --result success` refuses stale/unfinished content for an API-authored
  Mission with the same typed `DESIGN_*` reason the orchestrator-api `next` path returns (SC-001).
- Native `agent … finalize-tasks` refuses stale `tasks`-stage content for an API-authored Mission
  and acquires the cooperative `authoring_lock` (SC-002).
- Non-API-authored Missions and the orchestrator-api path show no observable behaviour change
  (SC-003); one canonical enforcement authority (the api `_completion_gate` is removed).
- Red-first native cases are RED on `origin/main`, GREEN on the fix; `test_layer_rules.py` green (SC-004).

## Context & Constraints

- Grounding: `../grounding-note.md` (two pre-spec squads + verification). Plan: `../plan.md`. Spec: `../spec.md`.
- ADR `docs/adr/4.x/2026-10-07-2-governed-planning-application-seam.md` (residuals #1 and #2).
- **C-001 (layer boundary)**: enforcement lives in `specify_cli.cli.commands` (top layer). It may NOT
  go into `src/runtime/` — `tests/architectural/test_layer_rules.py` forbids `runtime → specify_cli.design`.
  This reconciles the operator's "runtime-bridge composition-advance" hint with the enforced architecture.
- **C-002 (no api behaviour change)**: the orchestrator-api refusals/codes/envelope are unchanged;
  removing its local `_completion_gate` is a single-authority refactor (the api verb calls `next_step`
  in-process, so it inherits the gate).
- **C-003 (scope boundary)**: do not widen. The residual api-`plan`-`require_unfinalized`-under-lock and
  native `move-task` lock adoption are tracked follow-ups noted in the PR, not folded here.
- Marker gate: fire only for `result == "success"` and only when `api_authoring_enabled(root, slug)`;
  validate the native persisted `issued_step_id` (∈ {specify,plan,tasks}), never a caller-supplied stage.
- `authoring_lock` is reentrant → nesting (api verb → `next_step`) is safe.

## Branch Strategy

- **Strategy**: single_branch; planning artifacts generated on `issue-5879-native-stale-content-refusal`; completed changes merge into `issue-5879-native-stale-content-refusal`.
- **Planning base branch**: `issue-5879-native-stale-content-refusal`
- **Merge target branch**: `issue-5879-native-stale-content-refusal`

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first native `next` refusal case
- **Purpose**: Pin the user-observable native-`next` refusal before the fix exists.
- **Steps**: In `tests/specify_cli/orchestrator_api/test_planning_client_journey.py`, build an
  API-authored Mission exactly as `test_public_next_completes_real_design_actions` does (marker +
  receipts present), leave an issued stage's content stale/unfinished, then drive the **native** CLI
  app (`specify_cli.cli` / `next_cmd.next_step`) `next --agent … --result success` and assert it
  refuses with the typed `DESIGN_*` reason. Mark `@pytest.mark.regression` pinned to #5879; it must be
  RED on `origin/main` via the pre-existing entry point.
- **Files**: `tests/specify_cli/orchestrator_api/test_planning_client_journey.py`.

### Subtask T002 – Red-first native `agent … finalize-tasks` refusal case
- **Purpose**: Pin the native finalize refusal before the fix.
- **Steps**: With an API-authored Mission with stale `tasks`-stage parents, invoke native
  `agent … finalize-tasks` and assert the typed `DESIGN_*` refusal (RED on base). Co-locate with the
  native-next case or a finalize-focused sibling as ownership allows.
- **Files**: `tests/specify_cli/orchestrator_api/test_planning_client_journey.py`.

### Subtask T003 – Marker-gated gate in `next_cmd.next_step`
- **Purpose**: Enforce the shared gate for native + api `next`.
- **Steps**: In the `--result success` advancing path (before `decide_next` applies completion), when
  `api_authoring_enabled(root, slug)`, resolve `issued_step_id_for_mission` and run `validate_stage`
  for issued ∈ {specify,plan,tasks} under `authoring_lock`. Surface `DesignError` as the structured
  JSON error envelope / non-zero exit; keep native notices on stderr. Resolve the marker/receipts root
  the way `next_step` already resolves the mission (git common dir for receipts).
- **Files**: `src/specify_cli/cli/commands/next_cmd.py`.

### Subtask T004 – Remove the redundant api `_completion_gate`
- **Purpose**: Single canonical authority.
- **Steps**: Delete `_completion_gate`/`_run_governed` from `runtime_next.py` and call native
  `next_step` directly; keep `_decode` single-JSON contract and `RUNTIME_NEXT_FAILED`/`RUNTIME_BLOCKED`/
  `data.reason` mapping intact. Update any dead-symbol allowlist if needed.
- **Files**: `src/specify_cli/orchestrator_api/runtime_next.py`.

### Subtask T005 – Wrap native finalize in `finalization_scope`
- **Purpose**: Enforce `validate_stage("tasks")` + acquire `authoring_lock` on the native finalize surface.
- **Steps**: Wrap the native finalize body/bodies (`tasks_finalize._do_finalize_tasks`, and
  `mission_finalize.finalize_tasks` if it is a separate path) in `design.validation.finalization_scope`
  when `api_authoring_enabled`, mirroring the orchestrator-api `tasks` verb (`design_phase.py`), including
  the success-gated receipt re-stamp. Non-API-authored missions stay byte-identical.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_finalize.py`, `.../agent/mission_finalize.py`.

### Subtask T006 – Update/extend tests
- **Purpose**: Keep the surface pinned.
- **Steps**: Reflect the gate relocation in `tests/specify_cli/orchestrator_api/test_runtime_next.py`;
  add read-only + marker-gate unit assertions in `tests/specify_cli/design/test_design_authoring.py`.

### Subtask T007 – Targeted tests + gates + lint/type
- **Purpose**: Verify green and clean.
- **Steps**: `make test-fast`; the planning-client-journey, orchestrator-api runtime-next, native-next,
  and finalize test files; the specific architectural gate files the diff implicates
  (`test_layer_rules.py`, dead-symbol gates); `ruff check`, `ruff format --check --force-exclude`,
  `mypy --strict` on the changed files. Record commands + counts.

## Test Strategy

- ATDD red-first: T001/T002 committed as the first commit (RED on base); implementation (T003–T005) makes them GREEN.
- Typecheck: `.venv/bin/mypy --strict` on every changed source file (compiler diagnostics gate, in addition to pytest).

## Risks & Mitigations

- Root resolution for marker/receipts (owned checkout vs git common dir) → mirror existing `next_step` resolution; pin with a test.
- Dead-symbol gate after removing `_completion_gate` → update references/allowlist.
- Merge conflicts with open PRs #5907 / #5945 on the finalize/runtime-bridge guard surface → small diff, rebase late.

## Review Guidance
- Verify RED→GREEN for T001/T002 (RED on `origin/main`, GREEN on final).
- Confirm no api behaviour change (orchestrator-api journey assertions unchanged) and `test_layer_rules.py` green.
- Confirm `mypy --strict` + ruff/format clean with no new suppressions.
