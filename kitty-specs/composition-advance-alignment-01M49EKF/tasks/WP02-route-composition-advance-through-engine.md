---
work_package_id: WP02
title: Route the composition advance through the engine
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- FR-007
- FR-008
- FR-009
- FR-010
- FR-012
- SC-001
- SC-002
- SC-004
planning_base_branch: issue-2562-composition-advance-alignment
merge_target_branch: issue-2562-composition-advance-alignment
branch_strategy: Planning artifacts for this mission were generated on issue-2562-composition-advance-alignment. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2562-composition-advance-alignment unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Behaviour change
history:
- at: '2026-10-06T21:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/runtime_bridge_engine.py
create_intent:
- tests/runtime/test_composition_advance_alignment.py
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- src/runtime/next/runtime_bridge_engine.py
- src/runtime/next/runtime_bridge.py
- tests/runtime/test_composition_advance_alignment.py
- tests/runtime/test_bridge_engine.py
- tests/runtime/test_bridge_decision_log_flush.py
- tests/runtime/test_bridge_decide_next.py
- tests/specify_cli/next/test_runtime_bridge_composition.py
- tests/next/test_mission_run_back_reference.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#2562'
---

# Work Package Prompt: WP02 – Route the composition advance through the engine

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission composition-advance-alignment-01M49EKF`) or the Activity Log below. Address all feedback before the work is complete.

## Branch Strategy

- Planning/base branch: `issue-2562-composition-advance-alignment` (stacked on #5834).
- Final merge target: `issue-2562-composition-advance-alignment`.
- Topology `single_branch`: the WP runs in the repository root checkout.

## Shared rules

- This WP is the specified behaviour change (spec FR-001..FR-003). Everything else stays behaviour-preserving.
- The following are pinned and must not move:
  - Engine-private access stays in `runtime_bridge_engine` (C-002).
  - No forwarders and no `runtime_bridge_*` → `runtime_bridge` import (C-003).
  - Complexity ≤ 15; no new `noqa`.
- **Re-seaming rule (squad BLOCKER):** existing adapter tests that stub `_planner.plan_next` with an `object()` template are re-seamed onto a real minimal frozen template. You may remove a stub; you may not remove or weaken an assertion. List each re-seamed test in the WP activity log for the PR body.

## Objective

Close the significance/RACI gap by routing the composition advance through the engine's `plan_advance` / `commit_advance`, and delete the adapter's parallel planner and event code.

## Subtasks

### T006: Commit the red acceptance gate

`tests/runtime/test_composition_advance_alignment.py` already exists in the working tree. It is red on the base with 4 failed:
- no `raci:plan`;
- no significance record;
- MEDIUM options are approve/reject;
- LOW stops at the gate.

Commit it alone, first, as `test(#2562): red acceptance ...`. Add one assertion to the LOW test (squad NOTE 7): the issued step is the step the bridge resolved, i.e. `plan`.

### T007: Bridge plans with the engine

`runtime_bridge.py::_dn_plan_composition_advance` calls `_engine_adapter.plan_advance(ctx.run_ref, ctx.agent, "success")` instead of `plan_composition_advance`. `_resolve_planned_wp_workspace(plan.decision, ...)` stays and resolves the post-LOW-re-plan decision. Nothing else in the bridge changes.

### T008: Adapter commits through the engine

In `runtime_bridge_engine.py`, `advance_run_state_after_composition(..., plan: AdvancePlan, ...)` runs these steps in order:
1. The unchanged FR-008 refusal (`ValueError` before any write).
2. `_seed_emitter(sync_emitter, _read_snapshot(run_dir))`.
3. `_engine.commit_advance(run_ref, plan, agent, sync_emitter, before_run_completed=<guard>)`.
   - The guard resolves the retrospective policy lazily, raises `policy_error` under a blocking policy, and runs the blocking capture.
   - Policy resolution only happens on the terminal branch, so `test_advance_run_state_terminal_skipped_when_no_step_completed` stays meaningful.
4. When `plan.decision.kind == "terminal" and plan.completed_step_id is not None` and the policy is enabled but not blocking, run the non-blocking capture after the commit.
5. `_mapping._map_runtime_decision(...)` as today.

Delete these from the adapter:
- `CompositionAdvancePlan`, `plan_composition_advance`;
- `_emit_step_completed`, `_mark_step_completed`, `_emit_step_issued`, `_emit_decision_required`, `_apply_decision_effects`, `_emit_terminal`;
- the `apply_result` wrapper and `_live_template_path`, if no `src/` caller remains;
- the payload / `DecisionRequest` / `now_utc` / event-constant imports.

Keep the six engine/planner wrappers that the six-wrapper test pins. Update the module docstring: the adapter no longer duplicates `next_step`; it commits the engine's plan and owns the composition-specific edges.

`StaleAdvancePlan` is not caught in the adapter. The bridge's existing `except Exception` turns it into the EDGE-003 blocked Decision. Do not add a legacy fall-back.

### T009: Re-seam tests and add gates

- **Re-seam:** `tests/runtime/test_bridge_engine.py` (`_stub_engine_and_planner` users, roughly `:341-640`) and `tests/runtime/test_bridge_decision_log_flush.py` (`:250-400`) move onto a real frozen template. Copy the minimal-template helper style from the existing composition tests. Every existing assertion stays: event counts, dedupe, FR-008 refusal persists nothing, strict/default retrospective ordering, policy error.
- **Old names:** repoint tests that import `plan_composition_advance` to `plan_advance`:
  - `tests/specify_cli/next/test_runtime_bridge_composition.py` (~1207-1380);
  - `tests/next/test_mission_run_back_reference.py` (~264, ~354);
  - the name lists in `tests/runtime/test_bridge_decide_next.py:143` and `tests/runtime/test_bridge_decision_log_flush.py:262`.
  - In the bridge, `_dn_plan_composition_advance` keeps its name.
- **New tests in `test_bridge_engine.py`:**
  - (a) Stale plan (FR-010): mutate `state.json` between `plan_advance` and `advance_run_state_after_composition` → `StaleAdvancePlan`, `state.json` / `run.events.jsonl` unchanged. Through `decide_next_via_runtime`, the same race yields a `blocked` Decision and `runtime_next_step` is not called.
  - (b) Seeding happens before the first emit (FR-009).
  - (c) AST shape gate (FR-004/FR-005/SC-002): the adapter module defines no `plan_composition_advance` / `CompositionAdvancePlan`, calls no `apply_result`, and constructs none of `NextStepAutoCompletedPayload`, `NextStepIssuedPayload`, `DecisionInputRequestedPayload`, `MissionRunCompletedPayload`, `DecisionRequest`. Include a self-mutation row: a planted construction in a source string is reported.

### T010: Changelog and docs

Add a `docs/changelog/CHANGELOG.md` `[Unreleased]` entry. Use a bold impact-first lead with `(#2562)`, then before → after:
- composition-backed runs now record `raci:<step>`, `significance:audit:<step>` and `SignificanceEvaluated`;
- MEDIUM gates offer the soft-gate options and LOW gates auto-proceed;
- a malformed significance block now blocks the composition advance (EDGE-003);
- `decisions.events.jsonl` content changes for MEDIUM/LOW gates;
- a stale plan is refused.


## Post-tasks squad folds (2026-10-06, binding for this WP)

1. **Silently dead patch targets.** `plan_advance` calls the `plan_next` name bound in `engine.py` at import. A test that patches `runtime.next._internal_runtime.planner.plan_next` stops taking effect on the composition path.
   - Repatch onto `runtime.next._internal_runtime.engine.plan_next` in:
     - `tests/specify_cli/next/test_runtime_bridge_composition.py:1140-1196` (synthetic `dm-test-001`), `:1227`, `:1291` and `:1355`;
     - `tests/next/test_mission_run_back_reference.py:291` and `:378`. These currently pass vacuously.
   - Each repatched test must assert that its fake ran.
2. **Pin the retrospective order on the composition path (FR-008).**
   - Add order assertions: the strict capture runs before `emit_mission_run_completed`; the default capture runs after it.
   - Add a test that a raising strict capture leaves `state.json` unwritten and `MissionRunCompleted` absent.
   - Keep the policy root as `owned.owned_root if owned else repo_root`, and add an owned-checkout case for the guard's policy root.
3. **The FR-010 red case is already committed** in the gate file (`test_composition_advance_refuses_a_stale_plan`). T009's stale-plan test may reuse it rather than duplicate it.
4. **Tests that depend on `_live_template_path`.** Deleting it removes the tests at `tests/runtime/test_bridge_engine.py:256-273`. Move those assertions onto `engine.existing_template_path`; do not drop them.
5. **Stub arity.** Stubs for `plan_composition_advance` take 2 arguments (`test_bridge_decide_next.py:136-145`, `test_bridge_decision_log_flush.py:259-263`). `plan_advance` is called with 3 arguments, so change the lambdas' arity, not just their name.
6. **Re-seam range.** `test_bridge_decision_log_flush.py:353-420` patches the adapter's `_read_snapshot`, `_write_snapshot` and `plan_next`. The engine commit bypasses them, so re-seam that range too.
7. **AST gate (T009c).** The gate must also assert:
   - the adapter calls `plan_next` only inside its pinned `plan_next` wrapper;
   - the bridge's `_dn_plan_composition_advance` calls `_engine_adapter.plan_advance`.
8. **Edge-case tests.** Add tests for:
   - a malformed significance block, which gives a blocked Decision (EDGE-003);
   - a LOW re-plan that reaches terminal, which runs the retrospective path.
9. **Wider test surface.** Also run `tests/next/test_engine_plan_advance.py` and every `tests/integration/*` file that references `runtime_bridge` (NFR-003).
10. **Unused imports.** Removing `_apply_decision_effects` leaves `DecisionKind`, `RuntimeActorIdentity` and `dataclass` unused; remove them.
11. **T006 LOW assertion.** The extra assertion is on the returned Decision: `decision.step_id == "plan"`.
12. **Record in the PR.** The non-blocking capture now runs after `state.json` is written; today it runs before.

## Definition of Done

- The acceptance gate is red at its own commit and green at the end.
- The WP02 independent-test set, `tests/runtime`, `tests/next` and `tests/specify_cli/next` are green, apart from failures recorded as pre-existing against the base.
- These gates are green: `tests/runtime/test_bridge_no_compat_delegates.py`, `tests/architectural/test_runtime_emitter_seam.py`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_no_dead_symbols.py`.
- ruff, format and mypy are clean.

## Reviewer guidance

- Verify red→green: check out the T006 commit and run the gate.
- Verify each re-seamed test kept its assertions (diff the asserts).
- Verify no path calls `runtime_next_step` on a composition failure.

## Activity Log

- 2026-10-06T21:10:00Z – system – Prompt created.
