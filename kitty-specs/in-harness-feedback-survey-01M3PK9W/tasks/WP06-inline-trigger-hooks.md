---
work_package_id: WP06
title: Inline Trigger Hooks for Humans
dependencies:
- WP05
requirement_refs:
- FR-005
- FR-006
- FR-007
- FR-015
- FR-018
planning_base_branch: feat/in-harness-feedback-survey
merge_target_branch: feat/in-harness-feedback-survey
branch_strategy: Planning artifacts for this mission were generated on feat/in-harness-feedback-survey. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/in-harness-feedback-survey unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-in-harness-feedback-survey-01M3PK9W
base_commit: c3b1efc2219bc652adfb2308f653ef5d7375b128
created_at: '2026-09-30T16:46:57.327232+00:00'
subtasks:
- T030
- T031
- T032
- T033
- T034
- T035
phase: Phase 3 - Triggers
assignee: ''
agent: cursor
history:
- at: '2026-09-30T07:59:37Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/feedback/hooks.py
create_intent:
- src/specify_cli/feedback/hooks.py
- tests/specify_cli/feedback/test_hooks.py
- tests/specify_cli/feedback/acceptance/test_trigger_hooks.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/feedback/hooks.py
- src/specify_cli/cli/commands/consolidate.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/profile_invocation.py
- tests/specify_cli/feedback/test_hooks.py
- tests/specify_cli/feedback/acceptance/test_trigger_hooks.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Inline Trigger Hooks for Humans

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

A human running a trigger command in a real terminal is offered the Feedback Survey **after** the command's own work has completed and been reported:

| Trigger | Command | When |
|---|---|---|
| `mission_end` | `spec-kitty consolidate` | after `_run_real_merge(...)` returns successfully (not `--dry-run`, not `--abort`) |
| `planning_complete` | `spec-kitty agent mission finalize-tasks` | after the success report (not `--validate-only`, not `--json`) |
| `op_close` | `spec-kitty profile-invocation complete` | after the close is rendered, only for outcome `done` or `failed`, not `--json` |

Hard guarantees (FR-015, FR-018):

- The hook never changes the command's exit status, output contract, or recorded outcome. `--json` output is **byte-identical** to before.
- Offers happen only when `is_interactive()` is true, the command was not run with `--json`, and `is_ci_env()` is false. The first question is the **timed rating** ("How would you rate your experience? (1-5) (Enter to skip, 'never' to stop asking)", 30 s auto-skip), so a pseudo-terminal agent run can never stall and the flow stays at four interactions (NFR-008).
- Any exception inside the hook, including `KeyboardInterrupt` during the survey, is contained and treated as a skip.
- Each host function gains exactly **one** straight-line call; no new branches in `consolidate()` or `finalize_tasks()` (C901 ceiling; `finalize_tasks` already carries a justified suppression).

## Context & Constraints

- `spec.md`: FR-005, FR-006, FR-007, FR-015, FR-018; Edge Cases (triggering workflow fails, several triggers close together, abandoned form).
- `plan.md`: Key Design Decision 2; IC-05 risks. `research.md`: R-02, R-09.
- Host seams (read around each before editing):
  - `src/specify_cli/cli/commands/consolidate.py::consolidate` — the real path ends with `_run_real_merge(...)`. The `--json` flag is refused for non-dry-run consolidation, so `json_output` is False on this path. `--resume` also ends there, which is fine.
  - `src/specify_cli/cli/commands/agent/mission_finalize.py::finalize_tasks` (line ~3217, `# noqa: C901`) and `_emit_success_report(...)` (~2788).
  - `src/specify_cli/cli/commands/profile_invocation.py::complete_invocation` — after `_render_complete_response(...)`. The `--json` payload is contract-frozen.
- WP05 provides `terminal_form.run_form` (with `first_question_timeout_s`); WP04 provides the offer/submit services; WP01 provides `claim_offer`.
- `mission_type` for the payload: read it from the mission's `meta.json` through the existing canonical reader used by these commands (do not parse JSON by hand). For `op_close`, pass `None`.

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `feat/in-harness-feedback-survey`
- **Merge target branch**: `feat/in-harness-feedback-survey`

> Populated automatically by `finalize-tasks`; enter your lane with `spec-kitty agent action implement WP06 --agent <name>`.

## Subtasks & Detailed Guidance

### Subtask T030 – Red-first acceptance tests

- **Purpose**: Pin trigger behaviour through the **production entry points** (non-vacuity tactic: no helper-only tests).
- **Steps** (`tests/specify_cli/feedback/acceptance/test_trigger_hooks.py`):
  1. For `profile-invocation complete`: build a minimal repo with an open Op (reuse fixtures from `tests/specify_cli/invocation/` where possible). With `SPEC_KITTY_FORCE_INTERACTIVE=1`, a loopback endpoint, and input `"4\n\n\ny\n"` (rating, blank comment, blank email, consent), invoke the real CLI (`CliRunner`) with `--outcome done` → exit 0, the Op is closed, and the loopback server receives one submission with `trigger == "op_close"`. **Negative cases on the same fixture**: `--outcome abandoned` → no offer; `--json` → stdout byte-identical to a baseline captured with the hook monkeypatched to a no-op; `SPEC_KITTY_NON_INTERACTIVE=1` → no offer and `last_shown_at` untouched.
  2. For `consolidate` and `finalize-tasks`: full end-to-end fixtures are heavy. Prove the wiring by monkeypatching `specify_cli.feedback.hooks.offer_after_trigger` with a recorder and running the real command on the smallest existing fixture used by their current tests (look in `tests/specify_cli/consolidation/` and `tests/specify_cli/cli/commands/agent/` for mission fixtures). Assert: called once with the right trigger after success; **not** called on `--dry-run`, `--validate-only`, or a failing run (positive control: the success run). Exit codes are unchanged versus the same run with the recorder.
- **Files**: `tests/specify_cli/feedback/acceptance/test_trigger_hooks.py`

### Subtask T031 – `feedback/hooks.py`

- **API**:

```python
def offer_after_trigger(
    trigger: SurveyTrigger,
    *,
    json_output: bool,
    mission_type: str | None = None,
    console: Console | None = None,
) -> None: ...
```

- **Steps**:
  1. Wrap the whole body in `try: ... except BaseException: return`, logging at debug level only. Re-raising `SystemExit` is not needed because the survey never calls `exit`. Document why `BaseException` is caught: the host command has already finished, and Ctrl-C during an optional survey must not turn a successful command into a failure.
  2. Early returns: `json_output` → return; `not is_interactive()` → return; `is_ci_env()` → return; the trigger is not automatic → return.
  3. Resolve the endpoint; `claim_offer(trigger, endpoint_available=..., interactive=True, ci=False)`; not `prompt` → return.
  4. `run_form(allow_never=True, first_question_timeout_s=30.0)`. Outcomes `skipped` (including timeout), `declined`, and `aborted` → return quietly (the offer already counts as shown); `never` → `set_automatic_prompts(False)` and print the re-enable hint.
  5. On `submitted` → `build_and_hand_off(..., consent=True)` with `harness="cli"`, then print `THANK_YOU`. On `never` → as above. Otherwise return quietly.
  6. Print a blank line and a subtle separator before the question so it is visually distinct from the command's own output; use `rich` styling consistent with the CLI.
- **Files**: `src/specify_cli/feedback/hooks.py`

### Subtask T032 – Mission-end hook in `consolidate`

- **Steps**: Immediately after the `_run_real_merge(...)` call at the end of `consolidate()`, add one call: `offer_after_trigger(SurveyTrigger.mission_end, json_output=json_output, mission_type=<resolved mission type>)`. Resolve the mission type inside a tiny helper in `hooks.py` (for example `mission_type_for(repo_root, mission_slug)`) so `consolidate()` gains no branches. Use a local import if that is the file's convention for optional subsystems (check the top of `consolidate.py`).
- **Files**: `src/specify_cli/cli/commands/consolidate.py`
- **Parallel?**: Yes, with T033/T034.
- **Notes**: `_run_real_merge` raises `typer.Exit` on failure, so the hook is naturally skipped on failure. Verify this by reading it, and cover it in T030.

### Subtask T033 – Planning-complete hook in `finalize_tasks`

- **Steps**: At the point where `finalize_tasks` has emitted its success report (after `_emit_success_report(...)` in the non-validate-only path), add one straight-line call: `offer_after_trigger(SurveyTrigger.planning_complete, json_output=json_output, mission_type=...)`. If the only way to avoid a new branch for `validate_only` is to place the call inside the success-only path, do that. If `finalize_tasks` has no single success point, add the call at the end of `_emit_success_report` guarded by that function's existing non-JSON branch, and document why.
- **Files**: `src/specify_cli/cli/commands/agent/mission_finalize.py`
- **Notes**: Tidy-first rule (charter Standing Order 2): if placing the call cleanly needs an extraction, commit that extraction first as a behaviour-preserving step with its own tests.

### Subtask T034 – Op-close hook in `profile-invocation complete`

- **Steps**: After `_render_complete_response(...)`, add `offer_after_trigger(SurveyTrigger.op_close, json_output=json_output) if checked_outcome in ("done", "failed") else None`. To keep the command body branch-free, you may instead pass `outcome` into a thin wrapper `offer_after_op_close(outcome, json_output=...)` in `hooks.py` that performs the check. Prefer the wrapper.
- **Files**: `src/specify_cli/cli/commands/profile_invocation.py`, `src/specify_cli/feedback/hooks.py`
- **Notes**: The `--json` payload shape is contract-frozen; the byte-identity test in T030 guards it.

### Subtask T035 – Hook unit tests + complexity check

- **Steps** (`tests/specify_cli/feedback/test_hooks.py`): table-drive `offer_after_trigger` over json/non-interactive/CI/non-automatic/claim-none/form-outcomes (skipped incl. timeout, declined, aborted, never, submitted)/exception-inside; assert `run_form` is called with `allow_never=True, first_question_timeout_s=30.0` (monkeypatch `run_form` to raise `KeyboardInterrupt` → returns None, nothing propagates). Assert the recorded `build_and_hand_off` calls. Run ruff's C901 check on the three host files and confirm no new violations: `uv run --frozen ruff check --select C901 src/specify_cli/cli/commands/consolidate.py src/specify_cli/cli/commands/agent/mission_finalize.py src/specify_cli/cli/commands/profile_invocation.py`.
- **Files**: `tests/specify_cli/feedback/test_hooks.py`

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/feedback -q
uv run --frozen pytest tests/specify_cli/invocation tests/specify_cli/consolidation -q -m "fast or unit"
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -m "fast or unit"
uv run --frozen mypy --strict src/specify_cli/feedback src/specify_cli/cli/commands/profile_invocation.py
uv run --frozen ruff check src/specify_cli/feedback src/specify_cli/cli/commands/consolidate.py src/specify_cli/cli/commands/agent/mission_finalize.py src/specify_cli/cli/commands/profile_invocation.py tests/specify_cli/feedback
uv run --frozen ruff format --check src/specify_cli/feedback src/specify_cli/cli/commands tests/specify_cli/feedback
make test-fast
```

These are the owning subsystems' directories at the fast tier. Do not run the whole `tests/architectural/` directory or `make test-full`. Classify any unrelated red with the baseline-red gotcha (CLAUDE.md) before touching it.

## Risks & Mitigations

- **Accidental JSON contamination** → the survey prints only on the non-JSON path; the byte-identity test catches regressions.
- **Hangs in agent pseudo-terminals** → the timed first (rating) question; unit-tested in WP05, exercised here.
- **Complexity creep in god-functions** → one call each; C901 check in T035.

## Review Guidance

- Verify each host function gained exactly one straight-line call and no branches.
- Verify the byte-identical `--json` test for `profile-invocation complete` exists and compares against a real baseline.
- Verify tests call the production CLI entry points (not only `offer_after_trigger`).
- Verify `abandoned` Ops, dry runs, validate-only runs, and failures never offer.

## Activity Log

> **CRITICAL**: Append entries in chronological order: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-09-30T07:59:37Z – system – Prompt created.
