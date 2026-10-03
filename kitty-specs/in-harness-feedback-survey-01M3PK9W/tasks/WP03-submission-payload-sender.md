---
work_package_id: WP03
title: Submission Payload & Fire-and-Forget Sender
dependencies:
- WP01
- WP02
requirement_refs:
- C-003
- FR-002
- FR-003
- FR-004
- FR-014
- FR-020
- FR-021
- NFR-001
- NFR-002
- NFR-004
- NFR-007
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-in-harness-feedback-survey-01M3PK9W
base_commit: 405e3e0f4fe52a434a78b6004279c4db1c37fd9b
created_at: '2026-09-30T12:58:00.581428+00:00'
subtasks:
- T013
- T014
- T015
- T016
- T017
- T018
phase: Phase 2 - Core delivery
assignee: ''
agent: cursor
history:
- at: '2026-09-30T07:59:37Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/feedback/payload.py
create_intent:
- src/specify_cli/feedback/payload.py
- src/specify_cli/feedback/sender.py
- tests/specify_cli/feedback/test_payload.py
- tests/specify_cli/feedback/test_sender.py
- tests/specify_cli/feedback/test_submission_contract.py
- tests/specify_cli/feedback/fixtures/feedback-submission.schema.json
- tests/specify_cli/feedback/loopback_server.py
- tests/specify_cli/feedback/acceptance/test_submission_delivery.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/feedback/payload.py
- src/specify_cli/feedback/sender.py
- tests/specify_cli/feedback/test_payload.py
- tests/specify_cli/feedback/test_sender.py
- tests/specify_cli/feedback/test_submission_contract.py
- tests/specify_cli/feedback/fixtures/feedback-submission.schema.json
- tests/specify_cli/feedback/loopback_server.py
- tests/specify_cli/feedback/acceptance/test_submission_delivery.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Submission Payload & Fire-and-Forget Sender

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

- `payload.py` validates raw user input (rating, comment, email) and builds a **Feedback Submission** whose keys are exactly the allowlist in `contracts/feedback-submission.schema.json` (FR-004, FR-021, NFR-004). Email is present only when provided.
- `sender.py` delivers a confirmed submission **fire-and-forget** (FR-014, NFR-001, NFR-002):
  - The parent hands the payload to a **detached child process** through stdin, never argv and never disk, and returns immediately without waiting.
  - The child makes **one** HTTPS POST with a 5-second total timeout, sends **no** authentication or cookie headers (C-003, DIRECTIVE_050), ignores the response, and always exits 0 silently.
- Nothing in this WP ever prints, logs, or persists the user's answers.
- Proven against a real loopback HTTP server: a confirmed submission arrives exactly once; with the server hanging, refusing, or returning 500, the parent returns in < 1 s with no output.

## Context & Constraints

- `spec.md`: FR-002, FR-003, FR-004, FR-014, FR-020, FR-021, NFR-001, NFR-002, NFR-004, C-003; Edge Cases (endpoint failures, long comment, malformed email).
- `plan.md`: Key Design Decision 4; IC-03. `research.md`: R-03, R-06, R-08.
- `data-model.md`: SurveyAnswers, ContextFields, FeedbackSubmission, Invariants 1–2.
- `contracts/feedback-submission.schema.json`: the wire contract. Copy it verbatim into `tests/specify_cli/feedback/fixtures/` for the contract test, and add a comment in the test pointing at the mission contract as the source.
- WP01 gives you `SurveyAnswers`, `Rating`, `SurveyTrigger`, `normalize_harness`. WP02 gives you `ResolvedEndpoint`.
- `httpx` is already a runtime dependency; `jsonschema` is available in the test extras.

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `feat/in-harness-feedback-survey`
- **Merge target branch**: `feat/in-harness-feedback-survey`

> Populated automatically by `finalize-tasks`; enter your lane with `spec-kitty agent action implement WP03 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T013 – Red-first acceptance tests

- **Purpose**: Pin delivery behaviour first (C-011); separate first commit.
- **Steps**:
  1. Create `tests/specify_cli/feedback/loopback_server.py`: a small test helper that starts an `http.server` on `127.0.0.1:<ephemeral>` in a thread, supports modes `ok` (record body and headers, return 204), `hang` (sleep longer than the test), `error` (500), and `closed` (a port with nothing listening). Expose `received: list[tuple[dict, dict]]` and a `wait_for(n, timeout)` helper.
  2. `tests/specify_cli/feedback/acceptance/test_submission_delivery.py`:
     - Confirmed submission to `ok` arrives exactly once within 5 s; body keys ⊆ allowlist; **positive control** on the same captured body: rating, trigger, and harness are present with the expected values.
     - No `Authorization`, `Cookie`, or `Proxy-Authorization` header in the captured request (positive control: `Content-Type: application/json` **is** present).
     - Email blank → no `email` key; email given → exactly that value.
     - For `hang`, `error`, and `closed`: `hand_off()` returns in < 1.0 s (measure with `time.monotonic()`), produces no stdout/stderr (`capfd`), and raises nothing.
     - Without consent, `build_and_hand_off(..., consent=False)` sends nothing (server `received` stays empty after a short wait). **Positive control**: the same fixture with `consent=True` receives one.
- **Files**: the two files above.

### Subtask T014 – `payload.py`

- **Purpose**: The only place raw input becomes a wire payload.
- **Steps**:
  1. Constants: `SUBMISSION_FORMAT_VERSION = 1`, `COMMENT_MAX_LENGTH = 2000`, `EMAIL_MAX_LENGTH = 254`, and `ALLOWED_KEYS` (frozenset matching the schema's properties).
  2. Validation helpers returning results rather than raising at the boundary:
     - `parse_rating(raw: str | int) -> Rating | None` (accepts "1"–"5" and ints; rejects bools, floats, and anything else).
     - `normalize_comment(raw: str | None) -> tuple[str | None, bool]` (strip; blank → None; returns `(text, truncated)`; truncation at 2,000 **characters**).
     - `parse_email(raw: str | None) -> tuple[str | None, bool]` (blank → `(None, True)`; valid shape `^[^@\s]+@[^@\s]+\.[^@\s]+$` and ≤ 254 → `(value, True)`; otherwise `(None, False)` meaning "malformed, re-ask").
  3. Context collection: `collect_context(trigger, harness, mission_type) -> ContextFields` using the installed CLI version (same source `upgrade.py` uses), `resolve_distribution_profile().package_name`, and the OS family from `sys.platform` → `linux|darwin|windows|other`.
  4. `build_submission(answers: SurveyAnswers, context: ContextFields) -> dict[str, object]`: emits exactly the allowlisted keys; omits `email` when `None`; `comment` may be `None`; asserts `set(result) <= ALLOWED_KEYS` before returning.
- **Files**: `src/specify_cli/feedback/payload.py`
- **Notes**: Never include repo, path, mission slug or id, branch, user, host, or git identity data. No free-text context fields.

### Subtask T015 – `sender.py` child entry point

- **Purpose**: The only code that talks to the network.
- **Steps**:
  1. `def _child_main() -> int`: read at most 16 KiB from `sys.stdin.buffer`; parse the JSON envelope `{"url": str, "body": dict}`; re-validate that the URL scheme is https or loopback http (defence in depth); POST with `httpx.Client(timeout=httpx.Timeout(5.0), follow_redirects=False, headers={"Content-Type": "application/json", "User-Agent": "spec-kitty-feedback/<version>"})`. Do not pass auth. Do not read or forward any credential environment variables.
  2. Wrap everything in `try/except BaseException` and `return 0`. The child never writes to stdout or stderr.
  3. `if __name__ == "__main__": raise SystemExit(_child_main())` so `python -m specify_cli.feedback.sender` works.
  4. Keep the module importable without side effects.
- **Files**: `src/specify_cli/feedback/sender.py`
- **Notes**: `follow_redirects=False` prevents an https endpoint redirecting the payload to plain http.

### Subtask T016 – `hand_off()` detached spawn

- **Purpose**: Return control within 1 s regardless of endpoint state (NFR-001).
- **Steps**:
  1. `def hand_off(body: Mapping[str, object], endpoint_url: str) -> bool`: serialise `{"url": ..., "body": ...}`; spawn `[sys.executable, "-m", "specify_cli.feedback.sender"]` with `stdin=PIPE`, `stdout=DEVNULL`, `stderr=DEVNULL`, `close_fds=True`, plus `_detach_kwargs()`.
  2. `_detach_kwargs() -> dict[str, object]`: POSIX → `{"start_new_session": True}`; Windows → `{"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}`. Isolate this in its own function for testing.
  3. Write the bytes to `proc.stdin`, close it, and **do not wait**. Return `True` if the spawn succeeded; on any exception return `False` (the caller still shows the same thank-you).
  4. `build_and_hand_off(answers, context, endpoint: ResolvedEndpoint, *, consent: bool) -> Literal["handed_off", "not_sent", "no_endpoint"]`: consent False → `not_sent`; `endpoint.url is None` → `no_endpoint`; otherwise build and hand off → `handed_off` (even if the spawn failed, because delivery is best-effort and invisible).
  5. Make the child's environment explicit: pass `env=` as a copy of `os.environ` with `SPEC_KITTY_NON_INTERACTIVE=1` added, so the child can never prompt.
- **Files**: `src/specify_cli/feedback/sender.py`
- **Notes**: On POSIX the child reparents when the parent exits; that is intended. Do not add a `wait()` "for tidiness".

### Subtask T017 – Tests

- **Steps** (`test_payload.py`, `test_sender.py`):
  - Rating parsing table (0, 1, 5, 6, "3", "3.0", True, None).
  - Comment: None, blank, 2,000 chars (not truncated), 2,001 chars (truncated, flag True), multi-byte characters counted as characters.
  - Email: blank, valid, missing `@`, spaces, 255 chars.
  - `build_submission` key set equals the allowlist minus `email` when omitted; **positive control** with email present.
  - Argv hygiene: monkeypatch `subprocess.Popen` to capture args; assert no answer text (rating value or comment string) appears in argv.
  - `_detach_kwargs` returns the right keys under monkeypatched `sys.platform` / `os.name` (cover the Windows branch on any host).
  - The child's `_child_main` with a stub stdin: invalid JSON → 0; non-https non-loopback URL → 0 with **no** request (use `httpx.MockTransport` or monkeypatch `httpx.Client`); valid → one request without auth headers.
  - `hand_off` returns `False` (not raises) when `Popen` raises `OSError`.
- **Files**: `tests/specify_cli/feedback/test_payload.py`, `tests/specify_cli/feedback/test_sender.py`

### Subtask T018 – Contract test

- **Steps**: Copy `kitty-specs/in-harness-feedback-survey-01M3PK9W/contracts/feedback-submission.schema.json` to `tests/specify_cli/feedback/fixtures/`. In `test_submission_contract.py`, build submissions for each trigger, with and without comment and email, and validate each with `jsonschema.Draft202012Validator`. **Negative control**: a dict with an extra key (for example `"repo": "x"`) fails validation, so the test cannot pass vacuously.
- **Files**: `tests/specify_cli/feedback/test_submission_contract.py`, `tests/specify_cli/feedback/fixtures/feedback-submission.schema.json`
- **Parallel?**: Yes, once T014 exists.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/feedback -q
uv run --frozen mypy --strict src/specify_cli/feedback
uv run --frozen ruff check src/specify_cli/feedback tests/specify_cli/feedback
uv run --frozen ruff format --check src/specify_cli/feedback tests/specify_cli/feedback
make test-fast
```

Loopback tests use only `127.0.0.1` and ephemeral ports. Record commands and counts in the Activity Log.

## Risks & Mitigations

- **Latency tests are flaky on slow CI** → the < 1 s bound is against spawn plus return only (no waiting); if a timing marker exists in `pytest.ini` for wall-clock tests, apply it rather than loosening the bound.
- **Orphan child processes in tests** → the `hang` server mode must be shut down in fixture teardown so children exit on their 5 s timeout.
- **Proxy environment variables** → httpx honours `HTTPS_PROXY`; acceptable. Never forward proxy credentials explicitly.

## Review Guidance

- Check the allowlist test has its positive control and the contract test has its negative control.
- Check no answer text appears in argv, logs, or files.
- Check `follow_redirects=False`, no auth headers, and a 5 s timeout.
- Check the parent never waits on the child.

## Activity Log

> **CRITICAL**: Append entries in chronological order: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-09-30T07:59:37Z – system – Prompt created.
