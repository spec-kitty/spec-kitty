---
work_package_id: WP04
title: Agent Protocol Service
dependencies:
- WP03
requirement_refs:
- FR-001
- FR-003
- FR-010
- FR-012
- FR-013
- FR-018
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-in-harness-feedback-survey-01M3PK9W
base_commit: a525f0f7652f6fc451cd2851e472ec9994e45d2d
created_at: '2026-09-30T14:10:58.400007+00:00'
subtasks:
- T019
- T020
- T021
- T022
- T023
phase: Phase 2 - Core delivery
assignee: ''
agent: cursor
history:
- at: '2026-09-30T07:59:37Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/feedback/agent_protocol.py
create_intent:
- src/specify_cli/feedback/agent_protocol.py
- src/specify_cli/feedback/wording.py
- tests/specify_cli/feedback/test_agent_protocol.py
- tests/specify_cli/feedback/test_agent_contracts.py
- tests/specify_cli/feedback/fixtures/agent-check.schema.json
- tests/specify_cli/feedback/fixtures/agent-submit.schema.json
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/feedback/agent_protocol.py
- src/specify_cli/feedback/wording.py
- tests/specify_cli/feedback/test_agent_protocol.py
- tests/specify_cli/feedback/test_agent_contracts.py
- tests/specify_cli/feedback/fixtures/agent-check.schema.json
- tests/specify_cli/feedback/fixtures/agent-submit.schema.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Agent Protocol Service

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `cursor`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.
- **Report progress**: Update the Activity Log as you address each item.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Implement the agent ↔ CLI handshake as pure-ish service functions returning JSON-ready dicts. WP05 wires them to hidden CLI flags; this WP has no CLI code.

- `agent_check(trigger, agent)` claims the offer through WP01's `claim_offer()` and returns a dict valid against `contracts/agent-check.schema.json`. On `prompt`, it includes the fixed survey wording and `comment_max_length`.
- `agent_submit(...)` requires explicit consent (`consent == "yes"`), validates the answers, builds the payload, and hands it off. It returns a dict valid against `contracts/agent-submit.schema.json`. It **never** reports delivery success or failure (fire-and-forget).
- `agent_choice("skip" | "never", trigger)` records the user's choice: `skip` changes nothing further (the offer was already marked shown by `agent_check`); `never` turns automatic prompts off.
- Survey wording lives in one module (`wording.py`) shared by agents (here) and the terminal form (WP05), so the questions can never diverge.

## Context & Constraints

- `spec.md`: FR-001, FR-003, FR-010, FR-012, FR-013, FR-018; C-007 (consent wording "Send feedback?").
- `plan.md`: Key Design Decisions 1 and 7; IC-04. `research.md`: R-01, R-08.
- `contracts/agent-check.schema.json`, `contracts/agent-submit.schema.json`: authoritative shapes. Copy both verbatim into `tests/specify_cli/feedback/fixtures/`.
- Dependencies: WP01 (`claim_offer`, `set_automatic_prompts`, `load_preferences`, models), WP02 (`resolve_feedback_endpoint`), WP03 (`parse_rating`, `normalize_comment`, `parse_email`, `collect_context`, `build_and_hand_off`).
- **Important gating rule**: `agent_check` must pass `interactive=True` to `claim_offer`. Agents drive the CLI non-interactively by design (often with `SPEC_KITTY_NON_INTERACTIVE=1`), and the agent itself is the human's interactive intermediary. The **CI** gate still applies (`specify_cli.compat.planner.is_ci_env()`). Headless or unattended agent runs are handled by the agent block's instruction (WP07): "if no human is in the loop, do not run the check".

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `feat/in-harness-feedback-survey`
- **Merge target branch**: `feat/in-harness-feedback-survey`

> Populated automatically by `finalize-tasks`; enter your lane with `spec-kitty agent action implement WP04 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T019 – Red-first contract tests

- **Purpose**: Lock the agent-facing JSON contracts before implementing (C-011).
- **Steps**:
  1. Copy the two schemas into `tests/specify_cli/feedback/fixtures/`.
  2. `test_agent_contracts.py`: validate with `jsonschema.Draft202012Validator` the outputs of:
     - `agent_check` → `prompt` (eligible) and each `none` reason you can produce with fixtures (`no_endpoint`, `throttled`, `prompts_off`, `ci`, `lock_busy`, `preferences_unreadable`).
     - `agent_submit` → `handed_off`, `not_sent`, `invalid_input` (rating out of range; malformed email), `no_endpoint`, and `handed_off` + `errors: ["comment_truncated"]`.
     - `agent_choice` → `skipped`, `prompts_off`.
  3. **Negative control**: a dict with an unknown `status` fails validation.
- **Files**: `tests/specify_cli/feedback/test_agent_contracts.py`, the two fixtures.

### Subtask T020 – `agent_check()`

- **Signature**:

```python
def agent_check(
    trigger: SurveyTrigger,
    agent: str | None,
    *,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]: ...
```

- **Steps**:
  1. Resolve preferences (for `endpoint_override`) and the endpoint via WP02.
  2. `decision = claim_offer(trigger, endpoint_available=resolved.url is not None, interactive=True, ci=is_ci_env(), now=now)`.
  3. Build `{"schema_version": 1, "action": decision.action, "reason": decision.reason.value, "trigger": trigger.value}`; when `prompt`, add `"survey": wording.agent_survey_payload()`.
  4. `agent` is accepted for symmetry and future use; it does not affect the decision.
- **Files**: `src/specify_cli/feedback/agent_protocol.py`

### Subtask T021 – `agent_submit()`

- **Signature**:

```python
def agent_submit(
    trigger: SurveyTrigger,
    agent: str | None,
    *,
    rating: str | int | None,
    comment: str | None,
    email: str | None,
    consent: str | None,
    mission_type: str | None = None,
) -> dict[str, object]: ...
```

- **Steps** (in this order):
  1. `consent != "yes"` (case-sensitive exact match) → `{"status": "not_sent", "message": wording.NOT_SENT_MESSAGE}`. Nothing else runs.
  2. Validate: bad rating → `errors: ["rating_out_of_range"]`; malformed email → `errors: ["email_malformed"]`. Either → `status: invalid_input`, nothing sent.
  3. Resolve the endpoint; `None` → `status: no_endpoint`.
  4. Build answers and context (`harness = normalize_harness(agent)`), then `build_and_hand_off(..., consent=True)` → `status: handed_off`, `message: wording.THANK_YOU`, plus `errors: ["comment_truncated"]` if truncation happened.
  5. Never include any answer text in the returned dict.
- **Notes**: `agent_submit` does **not** re-check the throttle. The offer was claimed by `agent_check`; `on_demand` submissions are also valid here.

### Subtask T022 – `agent_choice()`

- **Steps**: `agent_choice(choice: Literal["skip","never"], trigger)`:
  - `skip` → `{"status": "skipped"}` (no state change; the offer was already marked shown).
  - `never` → `set_automatic_prompts(False)` → `{"status": "prompts_off", "message": wording.PROMPTS_OFF_MESSAGE}` (the message tells the user how to re-enable: `spec-kitty feedback --prompts on`).
  - Any other value is a caller bug; raise `ValueError` (the CLI layer in WP05 restricts choices with a Click `Choice`).
- **Parallel?**: Yes, once T020 exists.

### Subtask T023 – Shared wording + harness normalization

- **Steps**: `src/specify_cli/feedback/wording.py` holds module constants:
  - `RATING_QUESTION = "How would you rate your experience? (1-5)"`
  - `COMMENT_QUESTION = "What would you change? (optional)"`
  - `EMAIL_QUESTION = "Email, only if you want to sign your feedback (optional)"`
  - `CONSENT_QUESTION = "Send feedback?"`
  - `RATING_TERMINAL_HINT = "Enter to skip, 'never' to stop asking"` (appended in parentheses by WP05's terminal form to the rating question on automatic offers; the agent contract wording stays unchanged)
  - `THANK_YOU = "Thanks for your feedback."`
  - `NOT_SENT_MESSAGE`, `PROMPTS_OFF_MESSAGE`, `COMMENT_TRUNCATED_NOTICE`, `EMAIL_MALFORMED_NOTICE`, `NO_ENDPOINT_MESSAGE`
  - `agent_survey_payload() -> dict` returning exactly the `survey` object from the agent-check contract (with `comment_max_length` taken from `payload.COMMENT_MAX_LENGTH`, not a second literal).
  - Harness normalization lives in WP01's `normalize_harness`; reuse it and add nothing new here.
- **Files**: `src/specify_cli/feedback/wording.py`
- **Notes**: The contract uses `const` for the question strings; the contract test (T019) therefore also guards the wording.

## Test Strategy

`test_agent_protocol.py` (unit, beyond the contract shapes):

- `agent_check` in CI → `none/ci`, and preferences are untouched.
- `agent_check` twice within 7 days → second is `throttled` (proves the offer was claimed).
- `agent_submit` with consent `"YES"` or `"true"` → `not_sent` (exact-match rule); **positive control** `"yes"` → `handed_off` (monkeypatch `hand_off` to record calls; assert exactly one call).
- `agent_submit` result never contains the comment or email text.
- `agent_choice("never")` then `agent_check` → `prompts_off`.

```bash
uv run --frozen pytest tests/specify_cli/feedback -q
uv run --frozen mypy --strict src/specify_cli/feedback
uv run --frozen ruff check src/specify_cli/feedback tests/specify_cli/feedback
uv run --frozen ruff format --check src/specify_cli/feedback tests/specify_cli/feedback
make test-fast
```

## Risks & Mitigations

- **Agents answering for the user** → wording and WP07 block forbid it; `consent` must be literally `"yes"`.
- **Contract drift between mission contracts and fixtures** → fixtures are verbatim copies; note the source path in a comment.

## Review Guidance

- Verify `agent_check` passes `interactive=True` and still honours CI.
- Verify the consent check precedes every other step in `agent_submit`.
- Verify no answer text is echoed back in any response.

## Activity Log

> **CRITICAL**: Append entries in chronological order: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-09-30T07:59:37Z – system – Prompt created.
