---
work_package_id: WP05
title: status emit, orchestrator-api and docs
dependencies:
- WP02
requirement_refs:
- FR-011
- C-001
- C-003
- C-005
- SC-003
- FR-016
planning_base_branch: issue-6400-structured-status-actor
merge_target_branch: issue-6400-structured-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6400-structured-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6400-structured-status-actor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-status-contract-readers-01M5ZAAC
base_commit: 59e2b07747c366dafde46f744e7e7465b63b04bd
created_at: '2026-10-27T19:50:53.288657+00:00'
subtasks:
- T020
- T021
- T022
- T023
phase: Phase 2 - Write paths
history:
- at: '2026-10-27T18:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/orchestrator_api/wp_lifecycle.py
create_intent:
- tests/status/test_status_emit_structured_actor_6400.py
- tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/status.py
- src/specify_cli/orchestrator_api/wp_lifecycle.py
- src/specify_cli/status/work_package_lifecycle.py
- tests/status/test_status_emit_structured_actor_6400.py
- tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py
- docs/architecture/status-model.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – status emit, orchestrator-api and docs

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`. Address every feedback item and record each change with `spec-kitty agent tasks add-history WP05 --note "..."`.

---

## ⚠️ Phase split (operator decision 2026-10-27) — overrides the sections below

`spec-kitty-events` 11.0.0's `diary.decode_actor` (every status read) accepts only `{tool, role, profile, model}`. In this mission, writers emit that **4-key** structured actor; `profile` comes only from the dispatch invocation, `--profile`, or the compact `--agent` profile segment, else `null`. **No WP-frontmatter fill and no `profile_source` on the wire** (deferred to a follow-up, spec C-006). Wherever the text below mentions `planned_profile_for_wp`, `planned_profile=`, `profile_source` or `wp_frontmatter` on a *written* actor, drop it; expected actors in tests are 4-key dicts. Every other instruction stands.

## Objectives & Success Criteria

Part of issue #6400 (FR-011) plus the mission's docs.

- `agent status emit WPxx --to <lane> --actor <name>` writes the 5-key actor: `tool` = bare tool of `--actor` (compact form parsed), `role = role_for_hop(current, to)`, profile from the compact segment else WP frontmatter.
- `orchestrator-api` lifecycle commands (`start-implementation`, `start-review`, the transition and note commands in `orchestrator_api/wp_lifecycle.py`) write the same shape. Their JSON envelopes do not change (the orchestrator contract version stays as is).
- `docs/architecture/status-model.md` documents the actor shape, the profile order, role rule and the frontmatter-identity rule; the event-format example shows the structured actor.
- `docs/changelog/CHANGELOG.md` `[Unreleased]` gets one entry (Changed) for #6400 and #6448, in the section's existing style (a style guard checks it).

## Context & Constraints

- WP02 delivers `status.actor`. Use `build_status_actor`, `role_for_hop`, `planned_profile_for_wp` only.
- `agent status emit` (`src/specify_cli/cli/commands/agent/status.py:307-...`): `--actor` is required and free text in docs examples (`claude`, `reviewer`, `admin`). Treat it as the agent value (`agent=actor`, `fallback_tool=actor`). A value that `parse_agent_boundary_string` rejects (empty tool) is already invalid today.
- Orchestrator API: `wp_lifecycle.py:481-960` takes `--actor` and calls `status/work_package_lifecycle.py` helpers (`:253-487`), which call the emit shells. Build the structured actor at the orchestrator command boundary (where the WP id and lanes are known) or inside `work_package_lifecycle` where `from`/`to` lanes are known; pick the single place that covers every orchestrator transition and keep `_actors_compatible` / `_actor_key` comparisons fed with the same values they get today (they project dicts to the tool).
- `wp_lifecycle.py:953` builds a history line `f"- [{timestamp}] {actor}: {note}"` — keep it a string.
- System writers stay strings (C-003): do not touch migrations, `consolidation/`, `status/bootstrap.py`, `lanes/recovery.py`, attestations.
- Docs: Divio Explanation/Reference page; keep its frontmatter `updated:` date current (2026-10-27); plain language; no `feature` wording.

## Branch Strategy

- **Planning base branch**: `issue-6400-structured-status-actor`
- **Merge target branch**: `issue-6400-structured-status-actor`

```bash
spec-kitty agent action implement WP05 --agent claude --mission status-contract-readers-01M5ZAAC
```

## Subtasks & Detailed Guidance

### Subtask T020 – Red-first tests

- `tests/status/test_status_emit_structured_actor_6400.py`: drive `agent status emit` with `CliRunner` on a fixture mission (see `tests/status/test_agent_status_emit_cli.py` for the existing harness); WP frontmatter `agent_profile: python-pedro`. Cases: `--to claimed --actor claude` → implementer, wp_frontmatter; `--to in_review --actor claude-reviewer:opus:reviewer-renata` → reviewer, `agent_string`, model `opus`; a WP without profile → nulls.
- `tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py`: drive `orchestrator-api start-implementation` (see `tests/agent/test_orchestrator_commands_integration.py` for the harness) and one review/transition command; assert the appended events' actor shape and that the JSON envelope is byte-identical to the base for the same inputs (compare keys/values except timestamps/ids).
- RED on base. Commit alone first: `test(status): pin structured actor on status emit and orchestrator-api (#6400)`.

### Subtask T021 – `agent status emit`

- In `status.py::emit`, before calling the emit shell, compute `from_lane` (the command already reads the current lane for validation; reuse it) and build the actor. Pass it as `actor=`.
- Keep any output that prints the actor using `actor_identity_str`.

### Subtask T022 – orchestrator-api

- Implement per the constraint above; one construction site. Pass `planned_profile` read once per command.

### Subtask T023 – Docs and changelog [P]

- `docs/architecture/status-model.md`: add a short "Actor" section (shape table, profile order, role rule, legacy shapes readers accept, frontmatter identity rule) and update the event-format example and any `--actor` examples if they describe the stored value.
- `docs/changelog/CHANGELOG.md` `[Unreleased]`: one Changed bullet, e.g. "Status events written by move-task, mark-status, add-history, action implement/review, status emit and the orchestrator API now record the actor as `{tool, role, profile, model}` instead of a bare string, with `role` taken from the action, and `mark-status` takes `--agent` (#6400). The CLI's lane list is derived from `spec_kitty_events` (#6448)." Match the section's sub-headings and run the changelog style test (`grep -rl "changelog" tests/architectural tests/docs 2>/dev/null` to find it).
- #6271 item 2 (folded in): in `docs/changelog/CHANGELOG.md` (~line 235, the #4941 entry) cite the diary-reducer fix as spec-kitty-events PR #102 (fixing issue #101) instead of the bare `spec-kitty-events#101`. Do not rewrite other `#101` mentions blindly (triage: #101 is the issue, #102 the PR).
- File the follow-up issue for system writers at mission closeout (orchestrator does this; not this WP).

## Test Strategy

```bash
uv run --frozen pytest tests/status/test_status_emit_structured_actor_6400.py tests/orchestrator_api/test_wp_lifecycle_structured_actor_6400.py -q
uv run --frozen pytest tests/status/test_agent_status_emit_cli.py tests/status/test_agent_status_emit_aggregate_wiring.py tests/agent/test_orchestrator_commands_integration.py tests/agent/test_json_envelope_contract_integration.py tests/orchestrator_api -q
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q   # prose touched
uv run --frozen ruff check <touched>; uv run --frozen ruff format --check --force-exclude <touched>; uv run --frozen mypy <touched src files>
```

## Risks & Mitigations

- Orchestrator contract tests pin envelopes; only stored events change. If an envelope echoes the actor, keep it a string (`actor_identity_str`).

## Review Guidance

- Red-first commit precedes the fix; envelopes unchanged; system writers untouched; docs match shipped behaviour.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP05 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T020 --status done`.
