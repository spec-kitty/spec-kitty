---
work_package_id: WP04
title: mark-status, add-history and action writers
dependencies:
- WP02
requirement_refs:
- FR-008
- FR-009
- SC-001
- SC-002
planning_base_branch: issue-6400-structured-status-actor
merge_target_branch: issue-6400-structured-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6400-structured-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6400-structured-status-actor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-status-contract-readers-01M5ZAAC
base_commit: 23125a47260a620d104b9644c90d919fdaeda8a2
created_at: '2026-10-27T19:50:10.999345+00:00'
subtasks:
- T016
- T017
- T018
- T019
phase: Phase 2 - Write paths
history:
- at: '2026-10-27T18:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_mark_status.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_structured_actor_annotations_6400.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_mark_status.py
- src/specify_cli/cli/commands/agent/tasks.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- tests/specify_cli/cli/commands/agent/test_structured_actor_annotations_6400.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – mark-status, add-history and action writers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`. Address every feedback item and record each change with `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## ⚠️ Phase split (operator decision 2026-10-27) — overrides the sections below

`spec-kitty-events` 11.0.0's `diary.decode_actor` (every status read) accepts only `{tool, role, profile, model}`. In this mission, writers emit that **4-key** structured actor; `profile` comes only from the dispatch invocation, `--profile`, or the compact `--agent` profile segment, else `null`. **No WP-frontmatter fill and no `profile_source` on the wire** (deferred to a follow-up, spec C-006). Wherever the text below mentions `planned_profile_for_wp`, `planned_profile=`, `profile_source` or `wp_frontmatter` on a *written* actor, drop it; expected actors in tests are 4-key dicts. Every other instruction stands.

## Objectives & Success Criteria

Part of issue #6400.

- `agent tasks mark-status` writes the structured actor and accepts a new optional `--agent` (compact form accepted). Without it: `tool="user"`, `role="implementer"`, profile from the WP frontmatter (FR-008). The display identity (snapshot actor) stays `user`.
- `agent tasks add-history` writes the structured actor; role `reviewer` when the WP's current lane is `in_review`, else `implementer`.
- The annotations written by `agent action implement` and `agent action review` (resume refresh, claim annotations, review re-claim) carry the same structured actor as their transitions (FR-009).
- JSON/text output of these commands does not change.

## Context & Constraints

- WP02 delivers `status.actor.build_status_actor`, `role_for_hop`, `planned_profile_for_wp`; use them only.
- Current code (origin/main `581b5c46`):
  - `tasks_mark_status.py:494-513`: `emit_runtime_annotation(..., actor="user", ...)` per WP; command defined in `tasks.py:979` (`mark_status`), state in `_MarkStatusState`.
  - `tasks.py:~1136` (`add_history`, `--agent`) → `tasks.py:1214-1221` `emit_inner_state_changed(..., actor=agent_name, ...)`.
  - `workflow_executor.py`: transitions at `:895-945` (implement claim, `build_self_asserting_actor`) and `:1889-1945` (review claim) are already structured; the annotations at `:1060-1070` (`_implement_emit_*`, `actor=actor`), `:1205-1215` / `:1232-1240` (`actor=agent or wp_agent_assignment.tool or "unknown"`), and `:1965-1972` (review re-claim, `actor=agent`) are bare strings. `:680` (`require_no_sparse_checkout(actor=agent)`) is a preflight log, not a status event — leave it.
- The new `--agent` on mark-status follows the existing `--agent` help text style ("Agent name"); no `--feature` alias anywhere (Terminology Canon).
- Per-WP frontmatter read: once per WP per command (mark-status may touch several WPs; cache in a dict).
- Charter: ATDD red-first through the real commands; complexity ≤ 15; no new `noqa`.

## Branch Strategy

- **Planning base branch**: `issue-6400-structured-status-actor`
- **Merge target branch**: `issue-6400-structured-status-actor`

```bash
spec-kitty agent action implement WP04 --agent claude --mission status-contract-readers-01M5ZAAC
```

## Subtasks & Detailed Guidance

### Subtask T016 – Red-first CLI tests

- **File**: `tests/specify_cli/cli/commands/agent/test_structured_actor_annotations_6400.py` (new).
- **Harness**: as WP03 (real mission fixture; see `test_issue_2684_subtask_completion_event_sourced.py`, which already drives `mark-status` and `action implement`), WP01 frontmatter `agent_profile: python-pedro`.
- **Cases**:
  1. `mark-status T001 --status done` (no `--agent`): annotation actor == `{"tool":"user","role":"implementer","profile":"python-pedro","profile_source":"wp_frontmatter","model":None}`; `agent tasks status --json` still reports the subtask done and any snapshot actor slot shows `user`.
  2. `mark-status T001 --status done --agent claude`: `tool == "claude"`.
  3. `add-history WP01 --note x --agent claude`: implementer actor; same with the WP moved to `in_review`: reviewer.
  4. `agent action implement WP01 --agent claude` then re-run (resume refresh): every appended event (transition and annotation) is a 5-key dict, role implementer.
  5. `agent action review WP01 --agent claude-reviewer` and its re-claim path: reviewer actors.
- RED on base for 1-5 (bare strings / unknown `--agent`). Commit alone first: `test(tasks): pin structured actor on mark-status, add-history and action notes (#6400)`.

### Subtask T017 – mark-status

- Add `agent: Annotated[str | None, typer.Option("--agent", help="Agent name (compact tool:model:profile accepted)")] = None` to `mark_status` in `tasks.py`; thread it into `_MarkStatusState`.
- In `_ms_emit_history` build per WP: `build_status_actor(role="implementer", agent=st.agent, fallback_tool="user", binding=None, planned_profile=planned_profile_for_wp(st.status_dir_or_primary, wp_id))`. Resolve the WP file from the PRIMARY planning surface (WP prompts live there, not on the coord status surface): use the same feature dir mark-status already reads `tasks.md` from (`st.tasks_md.parent`), not `st.status_dir`.
- Update the command's help/docs only where `--agent` is listed (`docs/` reference pages that enumerate mark-status options, if any; out-of-map docs edit is acceptable with a note).

### Subtask T018 – add-history [P]

- In `tasks.py` `add_history`: determine the current lane via the existing lane reader used nearby (`status.lane_reader.get_wp_lane` or the snapshot already loaded); `role = "reviewer" if lane == in_review else "implementer"`; `actor = build_status_actor(role=role, agent=agent_name, fallback_tool=agent_name or "user", binding=None, planned_profile=...)`.
- Keep the `history_entry` text unchanged.

### Subtask T019 – action implement/review annotations

- For each annotation site listed above, pass the structured actor the matching transition already uses (`transition_actor` / the implement or review claim actor), or build one with the same inputs (`role` = implementer for implement paths, reviewer for review paths; `binding=resolved_binding`; `planned_profile` read once per command).
- Where the helper signature is `actor: str` (e.g. `_implement_emit_resume_refresh`), widen to `ActorField`; keep any place that needs a string (`build_operational_context_for_claim(actor=...)`, `active_role=... or actor`) on `actor_identity_str(actor)`.
- Verify the transitions at `:903` / `:1925` now also carry `profile_source` (WP02 delegation) and the frontmatter fill (pass `planned_profile=` to `build_self_asserting_actor`).

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_structured_actor_annotations_6400.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -k "mark_status or history or implement or review or claim"
uv run --frozen pytest tests/specify_cli/cli/commands/test_implement_characterization.py tests/specify_cli/cli/commands/agent/test_claim_event_source.py tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py tests/specify_cli/cli/commands/agent/test_tasks_json_bytes.py -q
uv run --frozen ruff check <touched>; uv run --frozen ruff format --check --force-exclude <touched>; uv run --frozen mypy <touched src files>
```

## Risks & Mitigations

- `test_tasks_cli_contract.py` / JSON contract enumeration (`tests/architectural/test_json_contract_enumeration.py`) may pin the mark-status option set; update the pinned option list if it does (run that specific gate file).
- `tasks.py` is large; keep the new option and the add-history change local.

## Review Guidance

- Red-first commit precedes the fix.
- No annotation in these commands writes a bare string; command output unchanged; `--agent` is optional.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP04 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T016 --status done`.
