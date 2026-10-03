---
work_package_id: WP01
title: Hardened shared validator
dependencies: []
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-009
- FR-011
- FR-012
- FR-013
- FR-015
- FR-016
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-feedback-slash-command-validation-01M3VZBD
base_commit: 2d4ea25d3fea789f94a26510c5185d2827a5d5a1
created_at: '2026-10-01T19:38:16.283541+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Validation
history:
- at: '2026-10-01T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/feedback/
create_intent:
- tests/specify_cli/feedback/test_validation_table.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/feedback/payload.py
- src/specify_cli/feedback/agent_protocol.py
- tests/specify_cli/feedback/test_payload.py
- tests/specify_cli/feedback/test_agent_protocol.py
- tests/specify_cli/feedback/test_validation_table.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Hardened shared validator

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

- Rating accepts only the integers 1 to 5. Text, other numbers, decimals, booleans, whitespace-padded values and empty values are rejected.
- Comment is sanitized (control characters, format characters, terminal escape sequences removed; NFC; whitespace normalized), markup preserved, capped at 2000 characters without splitting a character, truncation flagged.
- Email is optional; if present it is exactly one well-formed address, at most 254 characters, never altered.
- `agent_submit` returns all failing field codes together (`rating_out_of_range`, `email_malformed`) and sends nothing when any field is invalid.
- Spec refs: FR-006 to FR-009, FR-011 to FR-013, FR-015, FR-016, NFR-001, NFR-002.

## Context & Constraints

- Read `.kittify/charter/charter.md`, `kitty-specs/feedback-slash-command-validation-01M3VZBD/{spec,plan,research,data-model}.md`.
- The validator lives in `src/specify_cli/feedback/payload.py` (`parse_rating`, `normalize_comment`, `parse_email`). Do not create a second validator.
- Keep shipped error codes; do not change `ALLOWED_KEYS` or add network calls (C-001, C-002).
- Complexity at most 15 per function; mypy strict; ruff check and format clean. No `# noqa` or `# type: ignore`.
- Red-first: write failing tests before implementation.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `spec-kitty agent mission finalize-tasks`. Do not edit by hand.

## Subtasks & Detailed Guidance

### Subtask T001 – Red input table tests

- **Purpose**: One shared table that later work packages reuse for parity.
- **Steps**: Create `tests/specify_cli/feedback/test_validation_table.py` with parametrized tables exported as module-level constants (`RATING_CASES`, `COMMENT_CASES`, `EMAIL_CASES`).
  - Rating invalid: `0`, `6`, `-1`, `4.5`, `"five"`, `"5 stars"`, `" 5 "`, `""`, `True`, `None`. Valid: `1` to `5` as int and as digit string.
  - Comment hostile (at least 20 cases): ANSI CSI and OSC sequences, NUL, BEL, DEL, C1 controls, zero-width space and joiner, bidi overrides, byte-order mark, mixed. Preserved: `use <b>bold</b> and a < b`, accented text, emoji, code snippet.
  - Email invalid (at least 10): `a@b`, `a b@example.test`, `a@@example.test`, `a@example.test, b@example.test`, `a@example.test;b@example.test`, control character inside, over 254 characters, leading or trailing dot in domain. Valid: `person@example.test`, empty.
  - Confirm every test fails first.
- **Files**: `tests/specify_cli/feedback/test_validation_table.py`.
- **Parallel?**: No; do first.
- **Notes**: Use only `example.test` addresses.

### Subtask T002 – Strict rating

- **Purpose**: Pin behavior that is mostly already correct.
- **Steps**: Run the rating table; adjust `parse_rating` only if a case fails (for example padded strings).
- **Files**: `src/specify_cli/feedback/payload.py`.
- **Parallel?**: Yes with T003 and T004 (same file, coordinate edits).

### Subtask T003 – Comment sanitizer

- **Purpose**: Clean without rejecting.
- **Steps**: In `normalize_comment`: NFC normalize; strip ANSI/OSC escape sequences with a compiled regex; drop characters in Unicode categories Cc and Cf (convert newline and tab to a single space or preserve newlines per the table you wrote; document the choice in a docstring); strip; return `(None, False)` if empty; truncate to `COMMENT_MAX_LENGTH` by characters (not bytes), never splitting a combined character if avoidable, and return `truncated=True`.
- **Files**: `src/specify_cli/feedback/payload.py`.
- **Notes**: Extract helpers to stay under complexity 15. Markup must pass through untouched.

### Subtask T004 – Strict email

- **Purpose**: One well-formed address.
- **Steps**: Replace the loose `_EMAIL_SHAPE` check. Reject whitespace, control characters, more than one `@`, comma or semicolon lists, empty local part or domain, domain without a dot or with leading, trailing or doubled dots. Keep the 254 limit. Return `(None, False)` when invalid; never alter the value apart from outer-whitespace trimming.
- **Files**: `src/specify_cli/feedback/payload.py`.

### Subtask T005 – `agent_submit` aggregation and no send

- **Purpose**: Structured errors and a guaranteed no-send on invalid input.
- **Steps**: Add tests that both invalid fields return both codes in one response and that `build_and_hand_off` is never called (use a mock or the loopback server). Adjust `agent_submit` only if needed.
- **Files**: `src/specify_cli/feedback/agent_protocol.py`, `tests/specify_cli/feedback/test_agent_protocol.py`.

### Subtask T006 – Fix affected existing tests

- **Purpose**: Keep the suite honest after stricter rules.
- **Steps**: Run `tests/specify_cli/feedback/test_payload.py` and `test_agent_protocol.py`; update expectations that encoded the old loose behavior, justifying each in the Activity Log. Never loosen the new rules to make an old test pass.
- **Files**: the two existing test files.

## Test Strategy

- `uv run --frozen pytest tests/specify_cli/feedback/test_validation_table.py tests/specify_cli/feedback/test_payload.py tests/specify_cli/feedback/test_agent_protocol.py -q`
- Then the subsystem: `uv run --frozen pytest tests/specify_cli/feedback -q`
- `uv run --frozen ruff check src/specify_cli/feedback tests/specify_cli/feedback`, `uv run --frozen ruff format --check` on the same paths, and `uv run --frozen mypy --strict src/specify_cli/feedback/payload.py src/specify_cli/feedback/agent_protocol.py`.
- Coverage of changed lines at least 90%.

## Risks & Mitigations

- Over-stripping legitimate text → keep preservation cases in the table.
- Truncation splitting a combined character → test with a combining sequence at the boundary.

## Review Guidance

- Confirm the table has at least 10 rating, 20 comment and 10 email cases.
- Confirm no new network call, no new allowlist key, no literal vendor names.
- Confirm compiler (mypy strict) and ruff passed, not just pytest.

## Activity Log

> Entries are chronological, oldest first; append new entries at the end.
> Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`

- 2026-10-01T20:00:00Z – system – Prompt created.
