---
work_package_id: WP02
title: Build the three lifecycle payloads through their canonical models
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-004
planning_base_branch: issue-6438-build-lifecycle-payloads-from-models
merge_target_branch: issue-6438-build-lifecycle-payloads-from-models
branch_strategy: Planning artifacts for this mission were generated on issue-6438-build-lifecycle-payloads-from-models. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6438-build-lifecycle-payloads-from-models unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-6438-build-lifecycle-payloads-from-models-01M68ZPD
base_commit: 284cf67ff8fdbf668d7d1acc84463f4787d7619c
created_at: '2026-10-31T13:06:58.142839+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Green
history:
- at: '2026-10-31T12:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/lifecycle_events.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Build the three lifecycle payloads through their canonical models

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status` before starting. Address every feedback item with
`spec-kitty agent tasks add-history WP02 --note "..."`.

## Objectives & Success Criteria

`emit_reviewer_self_approval`, `emit_mission_reopened` and `emit_follow_up_recorded` each construct
their canonical `spec_kitty_events` payload model and persist its JSON dump, so a payload the published
contract rejects raises `pydantic.ValidationError` before anything is appended.

WP01's module goes green; the pre-existing status suites pass with no edited assertion.

## Context & Constraints

- Issue #6438; spec FR-001/FR-002/FR-003, NFR-001/002/003, C-001/C-002/C-004.
- The idiom to match already exists in the same file — `emit_wp_created_local`:

  ```python
  from spec_kitty_events.project_lifecycle import WPCreatedPayload
  payload_model = WPCreatedPayload(...)
  payload: dict[str, Any] = payload_model.model_dump(mode="json", exclude_none=False)
  ```

- Function-local imports only (`from spec_kitty_events.lifecycle import ...` inside the emitter), matching
  every sibling emitter: the module must keep importing cleanly when an older `spec-kitty-events` is installed.
- Do **not** change: `_build_envelope`, `append_lifecycle_event`, `persist_lifecycle_event_local`,
  the event-type constants, `POST_MISSION_LIFECYCLE_EVENT_TYPES`, `LIFECYCLE_EVENT_TYPES`, `__all__`,
  the dedup keys, or the emitters' signatures.
- Do **not** wrap, catch or re-raise `ValidationError`. It must reach the caller. `ValidationError` is a
  `ValueError` subclass, so nothing else needs adapting.
- The emitters' own guards stay **before** model construction, so their messages still fire first:
  the `#1926` completion guard in both mission emitters, and the `follow_up_type`/reference guard in
  `emit_follow_up_recorded`.

## Branch Strategy

- **Strategy**: feature-branch on `issue-6438-build-lifecycle-payloads-from-models`
- **Planning base branch**: `issue-6438-build-lifecycle-payloads-from-models`
- **Merge target branch**: `issue-6438-build-lifecycle-payloads-from-models`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Subtasks & Detailed Guidance

### Subtask T006 – `emit_mission_reopened`

- **Purpose**: Make `MissionReopenedPayload` the construction authority for a re-open.
- **Steps**:
  - Keep `_require_mission_completed(...)` first.
  - Replace the dict literal with:

    ```python
    from spec_kitty_events.lifecycle import MissionReopenedPayload

    payload: dict[str, Any] = MissionReopenedPayload(
        mission_id=mission_id,
        mission_slug=mission_slug,
        reason=reason,
        reopened_by=reopened_by,
        reopened_at=reopened_at or now_utc_iso(),
        cleared_merge=dict(cleared_merge) if cleared_merge is not None else None,
    ).model_dump(mode="json", exclude_none=False)
    ```

  - Update the docstring paragraph that describes the payload so it says the payload is built through
    `MissionReopenedPayload` (keep the existing "fail-closed (#1926)" and "append-each" notes intact).
- **Files**: `src/specify_cli/status/lifecycle_events.py`
- **Parallel?**: yes.
- **Notes**: `reason` is typed `str` in the signature; the model is what rejects `""`/`None`.

### Subtask T007 – `emit_follow_up_recorded`

- **Purpose**: Make `FollowUpRecordedPayload` the construction authority for a follow-up.
- **Steps**:
  - Keep the `follow_up_type` discriminator block and `_require_mission_completed(...)` first.
  - Build the payload through the model with `recorded_at=recorded_at or now_utc_iso()` and dump it.
  - Update the docstring's payload description.
- **Files**: same file.
- **Parallel?**: yes.
- **Notes**: the model's `commit_sha`/`pr_number` are optional; pass them straight through so a `None`
  still serialises as `null`.

### Subtask T008 – `emit_reviewer_self_approval`

- **Purpose**: Make `ReviewerSelfApprovalPayload` the construction authority for the fallback approval.
- **Steps**:
  - Build the payload through the model with `timestamp=at or now_utc_iso()` and dump it.
  - Extend the one-line docstring so a reader knows the payload is model-built.
- **Files**: same file.
- **Parallel?**: yes.
- **Notes**: this one imports from `spec_kitty_events.project_lifecycle`, not `.lifecycle`.

### Subtask T009 – Blast radius

- **Steps**:
  - `uv run pytest tests/specify_cli/status/ -q` (the owning subsystem).
  - `uv run pytest tests/specify_cli/status/test_model_built_payloads_6438.py -q`.
  - `uv run pytest tests/architectural/test_events_tracker_public_imports.py -q` (public-import gate touch).
  - `uv run ruff check src/specify_cli/status/lifecycle_events.py`
  - `uv run mypy src/specify_cli/status/lifecycle_events.py`
  - Record every command and its pass/fail counts.
- **Files**: none.
- **Parallel?**: no.

## Test Strategy

WP01's module is the primary gate. A green run there plus an unedited
`tests/specify_cli/status/` is the acceptance evidence. Do not run a full-suite pass
(`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Risks & Mitigations

- **Key-order / `null` drift**: `exclude_none=False` and model field order match the old dicts exactly;
  do not "tidy" a field or add `exclude_none=True`.
- **Guard ordering**: constructing the model before the `#1926` guard would turn a named
  `MissionNotCompletedError` into a validation error — keep the guard first.
- **Private imports**: only `spec_kitty_events.lifecycle` and `spec_kitty_events.project_lifecycle`
  public modules; `tests/architectural/test_events_tracker_public_imports.py` fails on any `_`-prefixed name.

## Review Guidance

- Diff should be three function bodies plus docstring text. Anything touching the envelope, the append
  path, the constants or a dedup key is out of scope and must be refused.
- Confirm no `try/except` around construction and no `# type: ignore`/`noqa` added.
- Confirm the emitters' guard order is unchanged.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
