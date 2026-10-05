---
work_package_id: WP02
title: Comment limit shown before typing
dependencies: []
requirement_refs:
- FR-010
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-feedback-slash-command-validation-01M3VZBD
base_commit: 1b54a3275cd50b05c3a8fbcb6e82f5f5f1d582d0
created_at: '2026-10-01T19:39:28.548614+00:00'
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 1 - Validation
history:
- at: '2026-10-01T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/feedback/
create_intent:
- tests/specify_cli/feedback/test_wording.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/feedback/wording.py
- src/specify_cli/feedback/terminal_form.py
- tests/specify_cli/feedback/test_terminal_form.py
- tests/specify_cli/feedback/test_agent_contracts.py
- tests/specify_cli/feedback/test_wording.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Comment limit shown before typing

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: set at claim time

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` in the event log (`spec-kitty agent tasks status`) or the Activity Log. Address every feedback item and log what you changed.

---

## Objectives & Success Criteria

- Every comment prompt states the 2000-character limit before the user types.
- The limit text is built from `COMMENT_MAX_LENGTH`; the literal `2000` appears in no prompt string.
- The agent check payload carries the same text, so the slash command (WP03) never hardcodes it.
- Spec refs: FR-010, NFR-006.

## Context & Constraints

- Read `kitty-specs/feedback-slash-command-validation-01M3VZBD/{spec,plan,research}.md` (R2) and `.kittify/charter/charter.md`.
- The limit is per comment; it is unrelated to the weekly offer throttle.
- `wording.py` already imports `COMMENT_MAX_LENGTH` and exposes `agent_survey_payload()` with `comment_max_length`.
- Inline hooks (`hooks.py`) do not render a comment question themselves; they hand off to the terminal form or agent block. Confirm this and leave `hooks.py` alone unless a prompt string lives there.
- mypy strict, ruff clean, complexity at most 15, no suppressions.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `spec-kitty agent mission finalize-tasks`. Do not edit by hand.

## Subtasks & Detailed Guidance

### Subtask T007 – Red tests

- **Purpose**: Specify the behavior first.
- **Steps**: In `tests/specify_cli/feedback/test_wording.py` assert the comment question includes the limit derived from `COMMENT_MAX_LENGTH` (monkeypatch the constant to a different value and see the text follow it). In `test_terminal_form.py` assert the prompt text passed to the input function contains the limit and is issued before the comment is read. Confirm they fail.
- **Files**: the two test files.

### Subtask T008 – Wording from the constant

- **Purpose**: One source for the text.
- **Steps**: Change `COMMENT_QUESTION` (or replace it with a function if monkeypatch-following is needed) so it reads like: `What would you change? (optional, up to {limit} characters)`. Keep `COMMENT_TRUNCATED_NOTICE` consistent and also built from the constant.
- **Files**: `src/specify_cli/feedback/wording.py`.
- **Notes**: Update `agent_survey_payload()` so `comment_question` carries the new text.

### Subtask T009 – Terminal form

- **Purpose**: The terminal flow shows the limit first.
- **Steps**: Ensure `terminal_form.py` prints or uses the new question text before reading input; adjust existing tests that pinned the old wording.
- **Files**: `src/specify_cli/feedback/terminal_form.py`, `tests/specify_cli/feedback/test_terminal_form.py`.

### Subtask T010 – Agent contract

- **Purpose**: The agent check payload stays schema-valid with the new text.
- **Steps**: Run `test_agent_contracts.py`; update only fixtures and expectations that pin the old wording. The schema file under `tests/specify_cli/feedback/fixtures/` must remain valid.
- **Files**: `tests/specify_cli/feedback/test_agent_contracts.py`.
- **Parallel?**: Yes with T009.

## Test Strategy

- `uv run --frozen pytest tests/specify_cli/feedback/test_wording.py tests/specify_cli/feedback/test_terminal_form.py tests/specify_cli/feedback/test_agent_contracts.py -q`
- Then `uv run --frozen pytest tests/specify_cli/feedback -q`.
- `uv run --frozen ruff check` and `ruff format --check` on changed files; `uv run --frozen mypy --strict` on changed source files.

## Risks & Mitigations

- Old wording pinned in several tests → update deliberately, never loosen.
- Wording pinned in docs → leave to WP04.

## Review Guidance

- Confirm no literal `2000` in prompt text and that changing the constant changes the text.
- Confirm the limit appears before input in the terminal form.
- Confirm mypy strict and ruff passed.

## Activity Log

> Entries are chronological, oldest first; append new entries at the end.
> Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`

- 2026-10-01T20:00:00Z – system – Prompt created.
