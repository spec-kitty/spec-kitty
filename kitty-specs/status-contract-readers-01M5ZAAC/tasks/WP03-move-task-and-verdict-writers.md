---
work_package_id: WP03
title: move-task and verdict writers
dependencies:
- WP02
requirement_refs:
- FR-006
- FR-007
- FR-010
- SC-001
- SC-002
- C-004
planning_base_branch: issue-6400-structured-status-actor
merge_target_branch: issue-6400-structured-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6400-structured-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6400-structured-status-actor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-status-contract-readers-01M5ZAAC
base_commit: c37c3a0f6a7c7bd4430c62d662ede2f13f7ba3ad
created_at: '2026-10-27T19:49:25.463816+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 2 - Write paths
history:
- at: '2026-10-27T18:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_move_task_executor.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task_executor.py
- src/specify_cli/cli/commands/agent/tasks_move_task_hops.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py
- src/specify_cli/cli/commands/agent/tasks_materialization.py
- tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – move-task and verdict writers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`. Address every feedback item and record each change with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## ⚠️ Phase split (operator decision 2026-10-27) — overrides the sections below

`spec-kitty-events` 11.0.0's `diary.decode_actor` (every status read) accepts only `{tool, role, profile, model}`. In this mission, writers emit that **4-key** structured actor; `profile` comes only from the dispatch invocation, `--profile`, or the compact `--agent` profile segment, else `null`. **No WP-frontmatter fill and no `profile_source` on the wire** (deferred to a follow-up, spec C-006). Wherever the text below mentions `planned_profile_for_wp`, `planned_profile=`, `profile_source` or `wp_frontmatter` on a *written* actor, drop it; expected actors in tests are 4-key dicts. Every other instruction stands.

## Objectives & Success Criteria

Part of issue #6400; the path where it was observed.

- Every `agent tasks move-task` hop writes the 5-key structured actor, whatever the target lane and whether or not `--profile`/`--invocation-id` was given (FR-007).
- Role per hop follows `status.actor.role_for_hop` (FR-006): `for_review` → implementer; `in_review`/`approved`/`done` → reviewer; any hop out of `in_review` (rejection to `planned`/`in_progress`) → reviewer.
- The paired note annotation (`_mt_emit_runtime_state` → `emit_runtime_annotation`) carries the structured actor of the final hop (FR-007).
- The review-override verdict annotation (`tasks_materialization._persist_review_artifact_override`) carries a reviewer actor (FR-010).
- `profile` follows the order invocation → flag → agent string → WP frontmatter (`planned_profile_for_wp`, read once per command) → null.
- Gate behaviour unchanged: claim matching (`_actor_key`), `review_roles`, `_mt_resolve_active_reviewer_identity`, independence (`actor_full_identity`) give the same verdicts as before (C-004).

## Context & Constraints

- WP02 delivers `status.actor` (`build_status_actor`, `role_for_hop`, `planned_profile_for_wp`) and binding `profile_source`. Use only those; do not build actor dicts by hand.
- Current code (origin/main `581b5c46`):
  - `tasks_move_task_executor.py:201-300` `_mt_emit_transitions`: structured actor only when `_binding_role_for_lane(target)` is not None (claimed / in_review / approved / done) and `st.resolved_binding` is set; otherwise the bare `_mt_hop_actor` string (`tasks_move_task_hops.py:139-162`, which falls back to `"user"`).
  - `tasks_move_task_executor.py:532-543`: paired annotation `actor=st.final_hop_actor or st.actor` (bare string).
  - `tasks_verdict_persistence.py:722-735` → `tasks_materialization.py:70-106`: review-override annotation `actor=st.agent or "operator"`. Keep the `ReviewOverride.actor` field inside the delta a string (it is delta content read by the merge gate); only the event's `actor` becomes structured.
  - `tasks_move_task.py:543-566`: `_resolve_dispatch_binding(...)` — `st.resolved_binding` is always a `ResolvedBinding` (possibly with `agent_profile=None`).
- `_mt_hop_actor` keeps resolving the **tool identity** (agent flag, implementer handoff, recorded reviewer, `"user"`); feed its result as `fallback_tool` and `st.agent` as `agent` to `build_status_actor`. Do not change how the tool is chosen.
- `_binding_role_for_lane` still decides whether the resolved-binding annotation delta is written (`annotation_delta`); that logic (#4673, #6630) must not change. Only the transition's `actor` value changes.
- `st.final_hop_actor` is consumed elsewhere as a string (e.g. `implementing_actor=st.final_hop_actor or ""` at `:614`, review cycle receipts). Keep `final_hop_actor` a string; store the structured actor in a new state field (e.g. `st.final_hop_structured_actor`) for the annotation.
- #6715 (`issue-6715-lane-evidence-independence`) will edit `tasks_move_task.py` move gates. Keep edits there minimal (ideally none beyond reading the planned profile once); if it merges first, rebase.
- Charter: ATDD red-first through the real `agent tasks move-task` entry point; complexity ≤ 15 (`_mt_emit_transitions` is near the ceiling — extract the actor construction into a helper in `tasks_move_task_hops.py`, e.g. `_mt_hop_structured_actor(st, from_lane, target, hop_actor)`).

## Branch Strategy

- **Planning base branch**: `issue-6400-structured-status-actor`
- **Merge target branch**: `issue-6400-structured-status-actor`

```bash
spec-kitty agent action implement WP03 --agent claude --mission status-contract-readers-01M5ZAAC
```

## Subtasks & Detailed Guidance

### Subtask T011 – Red-first CLI tests

- **File**: `tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py` (new).
- **Harness**: reuse the real-mission fixture pattern of `tests/specify_cli/cli/commands/agent/test_issue_2684_subtask_completion_event_sourced.py` (`create_mission_core(..., topology=MissionTopology.LANES)`, charter seeding helpers, `CliRunner` on `specify_cli.app`), or a lighter existing fixture if one already drives `move-task` end to end (search `tests/specify_cli/cli/commands/agent/` for `"move-task"` and `invoke(`; prefer the lightest one that runs the real command). Write `agent_profile: python-pedro` into the WP01 frontmatter of the fixture.
- **Cases** (read `status.events.jsonl` after each command; assert on the newly appended events only):
  1. `--to for_review --agent claude` (from `in_progress`): transition actor == `{"tool":"claude","role":"implementer","profile":"python-pedro","profile_source":"wp_frontmatter","model":None}`; the paired `--note` annotation has the same actor.
  2. `--to approved --agent claude-reviewer --profile reviewer-renata`: every emitted hop (`for_review→in_review→approved` auto-walk, if it walks) has role `reviewer` on the in_review/approved hops, `profile_source == "flag"`.
  3. Rejection `in_review → planned` (or `in_progress`) with a review artifact/`--review-feedback-file` as the existing rejection tests do: role `reviewer`.
  4. `--agent claude::python-pedro` (compact string): `profile_source == "agent_string"`, `tool == "claude"`.
  5. WP with no `agent_profile`: `profile is None and profile_source is None`.
  6. No bare-string actor appears in any event these commands append (SC-001).
- RED on base: cases 1, 3, 4, 5, 6 fail (bare string); commit alone first: `test(tasks): pin structured actor on move-task hops (#6400)`.

### Subtask T012 – Every hop structured

- In `_mt_emit_transitions`, replace the `transition_actor: str | dict = hop_actor` + conditional block with one call that always builds the structured actor:
  - `from_lane` for the hop = previous event's `to_lane` or the current lane (already computed as `st.authoritative_lane_at_emit`).
  - `role = role_for_hop(from_lane, target)`.
  - `build_status_actor(role=role, agent=st.agent, fallback_tool=hop_actor, binding=st.resolved_binding, planned_profile=st.planned_profile)`.
- Compute `st.planned_profile = planned_profile_for_wp(st.feature_dir, st.task_id)` once (where `st.wp`/`st.feature_dir` are resolved; add the field to `_MoveTaskState`).
- Keep the `annotation_delta` branch (binding role + `_mt_hop_records_binding`) exactly as is.
- Check `_mt_hop_review_result(st, event, current_event_lane, target, hop_actor)` and `_mt_hop_policy_metadata` keep receiving the string `hop_actor`.

### Subtask T013 – Paired note

- `_mt_emit_runtime_state` (`tasks_move_task_executor.py:~500-543`): pass the structured actor of the final hop (stored by T012) as `actor=`; fall back to building one with `role_for_hop(current, target)` when no hop was emitted (an annotation-only move).
- Confirm `emit_runtime_annotation` / `emit_inner_state_changed` accept `ActorField` (dict) — they are typed `ActorField` since WP12 of an earlier mission; if a signature is still `actor: str`, widen it (that file is outside `owned_files`: a one-line type widening is a justified out-of-map edit; note it in history).

### Subtask T014 – Verdict annotation [P]

- `tasks_verdict_persistence._mt_fire_override_persist` → `_persist_review_artifact_override(..., actor=...)`: pass a reviewer structured actor (`build_status_actor(role="reviewer", agent=st.agent, fallback_tool="operator", binding=st.resolved_binding, planned_profile=...)`).
- In `tasks_materialization._persist_review_artifact_override`, accept `actor: ActorField`; build `ReviewOverride(actor=actor_identity_str(actor), ...)` so the delta content stays a string, and pass the structured `actor` to `emit_inner_state_changed`.
- Other callers of `_persist_review_artifact_override` (grep) keep passing strings; that still works.

### Subtask T015 – Regression sweep

- Run the move-task and review suites below; any failure that asserted the old bare string on a hop this WP changes is updated to the new shape (record each file in a history note); any other failure is a regression to fix in the product.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -k "move_task or move-task or verdict or review or claim"
uv run --frozen pytest tests/unit/status/test_review_roles.py tests/status/test_actor_identity_reconciliation_4665.py tests/status/test_review_claim_role_aware.py -q
uv run --frozen ruff check <touched>; uv run --frozen ruff format --check --force-exclude <touched>; uv run --frozen mypy <touched src files>
```

## Risks & Mitigations

- Review-claim conflict detection compares actors through `_actor_key` (tool) — unaffected; verify with `test_review_claim_role_aware.py`.
- An approval receipt or consolidate gate reading `event.actor` as a string: grep `\.actor\b` in `src/specify_cli/consolidation` and `src/specify_cli/review`; all should go through `actor_identity_str`/`_actor_key`/`actor_full_identity`. Report any that does not.

## Review Guidance

- Red-first commit precedes the fix and was red on the base.
- No hop writes a bare string; tool selection unchanged; `annotation_delta` logic unchanged.
- `_mt_emit_transitions` complexity ≤ 15 (`uv run --frozen ruff check --select C901`).

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP03 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T011 --status done`.
