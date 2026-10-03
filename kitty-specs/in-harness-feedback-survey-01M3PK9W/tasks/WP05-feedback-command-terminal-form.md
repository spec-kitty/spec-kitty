---
work_package_id: WP05
title: spec-kitty feedback Command & Terminal Form
dependencies:
- WP04
requirement_refs:
- C-007
- FR-001
- FR-002
- FR-003
- FR-008
- FR-009
- FR-012
- FR-017
- FR-019
- FR-020
- NFR-007
- NFR-008
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-in-harness-feedback-survey-01M3PK9W
base_commit: 1f235c51017ea0f93f1027ace42075ddaefa691a
created_at: '2026-09-30T14:39:50.390406+00:00'
subtasks:
- T024
- T025
- T026
- T027
- T028
- T029
phase: Phase 2 - Core delivery
assignee: ''
agent: cursor
history:
- at: '2026-09-30T07:59:37Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/feedback.py
create_intent:
- src/specify_cli/cli/commands/feedback.py
- src/specify_cli/feedback/terminal_form.py
- tests/specify_cli/cli/commands/test_feedback.py
- tests/specify_cli/feedback/test_terminal_form.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/feedback.py
- src/specify_cli/feedback/terminal_form.py
- src/specify_cli/cli/commands/__init__.py
- src/specify_cli/_completion_manifest.json
- docs/api/cli-commands.md
- tests/specify_cli/cli/commands/test_feedback.py
- tests/specify_cli/feedback/test_terminal_form.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – `spec-kitty feedback` Command & Terminal Form

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

Ship the lean, single command agreed at planning (no subcommand group):

| Invocation | Behaviour |
|---|---|
| `spec-kitty feedback` | On-demand survey in the terminal (FR-008). Ignores the weekly limit and "don't ask again". Dormant → prints the no-endpoint message and asks nothing (FR-017). Not interactive → prints a one-line hint (use it from a terminal, or ask your agent) and exits 0. |
| `spec-kitty feedback --status` | Effective destination + source, the list of fields a submission contains, last-shown date (or "never"), automatic prompts on/off, and a note when preferences are unreadable (FR-019, C-007). |
| `spec-kitty feedback --prompts on\|off` | Toggles automatic prompts (FR-013). |
| hidden `--agent-check --trigger <t> [--agent <key>] --json` | WP04 `agent_check` → JSON |
| hidden `--agent-submit --trigger <t> [--agent <key>] --rating N [--comment T] [--email E] --consent yes --json` | WP04 `agent_submit` → JSON |
| hidden `--agent-choice skip\|never --trigger <t> --json` | WP04 `agent_choice` → JSON |

Also create the reusable **terminal form** used by the bare command and, in WP06, by inline trigger offers. For inline offers the **rating question itself is timed**: it shows the hint "(Enter to skip, 'never' to stop asking)" and auto-skips after 30 s without input. There is no separate "share feedback?" gate question, so every flow stays within NFR-008's four interactions (rating, comment, email, consent). This resolves analysis finding I1.

Done when: CliRunner integration tests pass; the completion manifest and CLI reference are regenerated and their gates pass; mypy/ruff/format are clean; exit status is always 0 for the survey paths (a survey never fails a command).

## Context & Constraints

- `spec.md`: FR-001, FR-002, FR-003, FR-008, FR-009, FR-012, FR-017, FR-019, FR-020, NFR-008, C-007; Edge Cases (invalid rating, long comment, malformed email, abandoned form).
- `plan.md`: Key Design Decisions 2 and 7; IC-04. `quickstart.md` steps 2–5 and 7 are your manual smoke test.
- Prompt gating authority: `specify_cli.core.env.is_interactive()`. Any prompt must consult it first (#2876 defect class). Do not call `sys.stdin.isatty()` directly.
- Command registration pattern: `src/specify_cli/cli/commands/__init__.py` uses per-command `_register_<name>(app)` functions (see `_register_accept`, `_register_dashboard`). Follow it exactly, including any lazy-import convention used there.
- Terminology canon: `--mission` only; never "feature" or "telemetry" in help text.
- Hidden flags: mirror how `spec-kitty upgrade` defines `--agent-check` / `--agent-choice` (`hidden=True` options in `src/specify_cli/cli/commands/upgrade.py`).

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `feat/in-harness-feedback-survey`
- **Merge target branch**: `feat/in-harness-feedback-survey`

> Populated automatically by `finalize-tasks`; enter your lane with `spec-kitty agent action implement WP05 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T024 – Red-first CLI integration tests

- **Purpose**: Pin the command surface first (C-011); separate first commit.
- **Steps** (`tests/specify_cli/cli/commands/test_feedback.py`, using Typer's `CliRunner` against the real `specify_cli` app, plus the WP01 conftest fixture for an isolated config dir and WP03's `loopback_server` helper):
  1. With `SPEC_KITTY_FEEDBACK_URL` pointing at the loopback server and `SPEC_KITTY_FORCE_INTERACTIVE=1`, invoke `feedback` with input `"4\nFaster planning\n\ny\n"` → exit 0, output contains the thank-you, and the server receives one body with `trigger == "on_demand"`, `harness == "cli"`, and no `email` key.
  2. Same, but answer `n` to "Send feedback?" → nothing received (**positive control**: case 1).
  3. `--status` shows the destination, the field list, `never`, and `on`. After `--prompts off`, `--status` shows `off`.
  4. Unset the URL (stock profile) → bare `feedback` prints the no-endpoint message and asks nothing.
  5. Non-interactive (`SPEC_KITTY_NON_INTERACTIVE=1`) bare `feedback` → hint line, exit 0, nothing received.
  6. Hidden flags: `--agent-check --trigger mission_end --agent cursor --json` returns JSON parseable as the agent-check contract; `--agent-submit ... --consent yes --json` returns `handed_off`; `--agent-choice never --trigger op_close --json` returns `prompts_off`.
  7. `spec-kitty --help` does **not** list the hidden flags (help snapshot of `feedback --help` excludes `agent-`).
- **Files**: `tests/specify_cli/cli/commands/test_feedback.py`

### Subtask T025 – `feedback/terminal_form.py`

- **Purpose**: One reusable human form; questions come from WP04's `wording.py`.
- **API**:

```python
@dataclass(frozen=True)
class FormResult:
    outcome: Literal["submitted", "declined", "skipped", "never", "aborted"]
    answers: SurveyAnswers | None
    comment_truncated: bool = False

def run_form(
    *,
    allow_never: bool,
    first_question_timeout_s: float | None = None,
    ask: Callable[[str], str] | None = None,
) -> FormResult: ...
```

- **Flow for `run_form`** (at most four interactions: rating, comment, email, consent — NFR-008):
  1. Rating: when `allow_never` (automatic offers), the prompt is `RATING_QUESTION` plus the hint `(RATING_TERMINAL_HINT)`. When `first_question_timeout_s` is set, read this first answer with the timed reader below; a timeout → `skipped`. Re-ask on invalid input (use WP03 `parse_rating`; re-asks are not timed); empty input or `s` → `skipped`; `never` (only when `allow_never`) → `never`.
  2. Comment (optional): if truncated, show `COMMENT_TRUNCATED_NOTICE` **before** consent.
  3. Email (optional): malformed → show `EMAIL_MALFORMED_NOTICE` and re-ask once; blank allowed.
  4. Consent: `CONSENT_QUESTION` [y/N] → `submitted` or `declined`.
  5. `KeyboardInterrupt` / `EOFError` anywhere → `aborted` (never propagates).
  6. `ask` is injectable for tests; default uses `typer.prompt` / `rich` prompt consistent with other interactive commands in the repo.
- **Timed reader** (private `_read_line_with_timeout(prompt, timeout_s) -> str | None`, used only for the first question of inline trigger offers in WP06): POSIX uses `select.select([sys.stdin], [], [], timeout_s)`; Windows polls `msvcrt.kbhit()` in a short-sleep loop until the deadline, then reads a line. Returns `None` on timeout. Isolate the platform branch in one private function so both branches can be unit-tested by monkeypatching. The on-demand command never passes a timeout.
- **Files**: `src/specify_cli/feedback/terminal_form.py`
- **Parallel?**: Yes, with T026.

### Subtask T026 – `cli/commands/feedback.py`

- **Steps**:
  1. A single Typer command function `feedback(...)` with options: `--status`, `--prompts [on|off]` (Click `Choice`), `--json`, and hidden: `--agent-check`, `--agent-submit`, `--agent-choice [skip|never]`, `--trigger [planning_complete|mission_end|op_close|on_demand]`, `--agent`, `--rating`, `--comment`, `--email`, `--consent`.
  2. Dispatch: extract a small `_dispatch_hidden(...)` (like `upgrade.py::_dispatch_agent_flags`) so the main function's complexity stays ≤ 15. Mutually exclusive modes → exit 2 with a clear message.
  3. Bare mode: resolve the endpoint (WP02). If there is none, print `NO_ENDPOINT_MESSAGE` and exit 0. If not `is_interactive()`, print the hint and exit 0. Otherwise `run_form(allow_never=False)`; on `submitted`, call WP03 `build_and_hand_off(..., consent=True)` with `trigger=on_demand` and `harness="cli"`, then print `THANK_YOU`.
  4. `--status`: use WP02 `describe_endpoint`, WP01 `load_preferences`, and WP03 `ALLOWED_KEYS` (render as a sorted, comma-separated list). With `--json`, emit an equivalent object.
  5. Help text: one sentence per option, canonical terms only; the command docstring states that submissions are anonymous unless an email is typed, and are sent only after "Send feedback?".
- **Files**: `src/specify_cli/cli/commands/feedback.py`

### Subtask T027 – Register the command

- **Steps**: Add `_register_feedback(app)` in `src/specify_cli/cli/commands/__init__.py`, following the file's existing pattern and ordering convention (alphabetical if that is the convention). Keep the diff to the registration only.
- **Files**: `src/specify_cli/cli/commands/__init__.py`

### Subtask T028 – Regenerate the completion manifest and CLI reference

- **Steps**:
  1. `uv run --frozen python -m specify_cli.completion --regenerate` → commit `src/specify_cli/_completion_manifest.json`.
  2. Regenerate `docs/api/cli-commands.md` with `scripts/docs/build_cli_reference.py` (read its `--help`/module docstring for the exact invocation; do not hand-edit generated sections).
  3. Run the gates: `tests/architectural/test_completion_manifest_freshness.py`, `tests/architectural/test_docs_cli_reference_parity.py`, and `tests/specify_cli/cli/commands/test_completion_fast_path.py`.
- **Files**: `src/specify_cli/_completion_manifest.json`, `docs/api/cli-commands.md`

### Subtask T029 – Terminal-form unit tests

- **Steps** (`tests/specify_cli/feedback/test_terminal_form.py`): drive `run_form` with an injected `ask` sequence for each outcome (submitted, declined, skipped, never when allowed / treated as invalid when not allowed, aborted via `KeyboardInterrupt` and `EOFError`), re-ask on bad rating, the truncation notice shown before consent, and email re-ask. For the timed first question: with `first_question_timeout_s` set, monkeypatch the POSIX `select` path to simulate a timeout (→ `skipped`) and input (→ continues), and the Windows `msvcrt` path (inject a fake module) to simulate the same. Assert the whole happy path asks exactly four questions (NFR-008 guard).
- **Files**: `tests/specify_cli/feedback/test_terminal_form.py`

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/feedback tests/specify_cli/cli/commands/test_feedback.py -q
uv run --frozen pytest tests/architectural/test_completion_manifest_freshness.py tests/architectural/test_docs_cli_reference_parity.py tests/specify_cli/cli/commands/test_completion_fast_path.py -q
uv run --frozen mypy --strict src/specify_cli/feedback src/specify_cli/cli/commands/feedback.py
uv run --frozen ruff check src/specify_cli/feedback src/specify_cli/cli/commands tests/specify_cli/feedback tests/specify_cli/cli/commands/test_feedback.py
uv run --frozen ruff format --check src/specify_cli/feedback src/specify_cli/cli/commands tests/specify_cli/feedback tests/specify_cli/cli/commands/test_feedback.py
make test-fast
```

Manual smoke: follow `quickstart.md` steps 2–5 and 7 with a loopback endpoint. Record commands and counts in the Activity Log.

## Risks & Mitigations

- **Parity gates red** → T028 is mandatory; do not hand-edit generated reference sections.
- **Stale install** → CliRunner tests use the in-process app; if you smoke-test the `spec-kitty` binary, reinstall the editable package first (CLAUDE.md baseline-red category 3).
- **A prompt hangs in tests** → every prompt path is behind `is_interactive()` or an injected `ask`.

## Review Guidance

- Confirm the bare command never prompts when `is_interactive()` is false.
- Confirm the consent wording is exactly "Send feedback?" and no URL is shown in the form (C-007); the URL appears only in `--status`.
- Confirm hidden flags are hidden in help and delegate to WP04 without re-implementing logic.
- Confirm the manifest and reference were regenerated by tool, not by hand.

## Activity Log

> **CRITICAL**: Append entries in chronological order: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-09-30T07:59:37Z – system – Prompt created.
