---
work_package_id: WP01
title: 'Harden the compact agent-string parser: stripped segments, blank-is-absent, refusal beyond four segments'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
- NFR-002
planning_base_branch: issue-6755-agent-string-parser-hardening
merge_target_branch: issue-6755-agent-string-parser-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-6755-agent-string-parser-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6755-agent-string-parser-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-agent-string-parser-hardening-01M6699F
base_commit: bf22e3bd64d6d543c0809aa28b285ad1c9a0934b
created_at: '2026-10-30T11:37:13.083799+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Defect fix
history:
- at: '2026-10-30T11:34:45Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/models.py
- tests/status/test_actor_boundary_normalize.py
- tests/specify_cli/cli/commands/agent/test_structured_actor_annotations_6400.py
- tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Harden the compact agent-string parser

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `maintainer-3`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Deliver issue #6755: the compact `--agent` parser stops fabricating whitespace identity and stops silently truncating past the fourth segment.

Done when:

1. `parse_agent_boundary_string("claude: :")` returns `("claude", None, None, None)`.
2. `parse_agent_boundary_string("claude\n")` returns `("claude", None, None, None)`.
3. `parse_agent_boundary_string("a:b:c:d:e")` raises `ValueError` naming the segment count (message includes the count, e.g. "5").
4. `spec-kitty agent tasks mark-status` / `add-history` / `move-task` with `--agent "a:b:c:d:e"` refuse before any write with exit 1 and `Invalid --agent value: <reason>` in the output.
5. A whitespace-only tool (`" "`) raises the existing empty-tool `ValueError`.
6. Existing #6400 lenient-path tests and #2861 bare-tool tests stay green, unchanged.
7. mypy --strict clean on the touched module; targeted test files green.

## Context & Constraints

- Spec: `kitty-specs/agent-string-parser-hardening-01M6699F/spec.md`; plan: `plan.md`; call-site survey: `research.md`; contract facts: `contracts/agent-boundary-parser.md`; validation commands: `quickstart.md`.
- The fix lives in `parse_agent_boundary_string` (`src/specify_cli/status/models.py`) ONLY. No call-site changes: the three explicit `--agent` paths already convert a parser `ValueError` into the clean refusal (`_ms_status_actor` in `cli/commands/agent/tasks_mark_status.py`, `_refuse_unparseable_agent` in `cli/commands/agent/tasks_shared.py` used by `move-task` and `add-history`).
- Do NOT touch: `wp_metadata._resolve_agent_from_colon_string` (persisted-frontmatter authority), `actor_from_option` (lenient builder — pre-checks the segment count), `actor_full_identity` / `_actor_key` (catch `ValueError`, fall back whole).
- #2861 bare-tool rule: absent segments stay `None`; never a tool-derived synthetic default.
- Refusal envelope stays exactly `Invalid --agent value: <reason>`; the new `ValueError` message is the `<reason>`.
- Red-first (ATDD): T001/T002 tests are written and committed RED before T003's production edit. The tests go through the pre-existing entry points (the parser function; the CLI commands through CliRunner) — no new test-only seams.
- No full heavy suite; run only the targeted files.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red parser tests for the three issue rows

- **Purpose**: Pin each row of #6755's table through the pre-existing parser entry point before the fix exists.
- **Steps**: Add to `tests/status/test_actor_boundary_normalize.py` (it already pins this parser; follow its docstring style):
  - `"claude: :"` → `("claude", None, None, None)` (whitespace segment is absent).
  - `"claude\n"` → `("claude", None, None, None)` (segments stripped).
  - `" codex :: planner-priti: "` → `("codex", None, "planner-priti", None)` (strip + blank-is-absent combined).
  - `"a:b:c:d:e"` → `pytest.raises(ValueError)` matching the count (5) in the message.
  - `" "` → `pytest.raises(ValueError, match="Empty agent tool")`.
- **Files**: `tests/status/test_actor_boundary_normalize.py`.
- **Parallel?**: No.
- **Notes**: Run `uv run pytest tests/status/test_actor_boundary_normalize.py -q` and confirm the NEW tests fail (the pre-existing ones pass). Commit the red state with a message naming the red evidence.

### Subtask T002 – Red CLI refusal tests for the three explicit paths

- **Purpose**: Prove the refusal surfaces on the real commands before the fix.
- **Steps**: Extend the existing #6400 test files (they already build the CLI runner fixtures — reuse them):
  - `mark-status` with `--agent "a:b:c:d:e"` → exit 1, `Invalid --agent value` in output, nothing written.
  - `add-history` with `--agent "a:b:c:d:e"` → exit 1, `Invalid --agent value`.
  - `move-task` with `--agent "a:b:c:d:e"` → exit 1, `Invalid --agent value` (follow the existing move-task 6400 test's fixture).
- **Files**: `tests/specify_cli/cli/commands/agent/test_structured_actor_annotations_6400.py` (mark-status, add-history), `tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py` (move-task).
- **Parallel?**: No.
- **Notes**: Confirm the three new tests fail on the planning base (today the value is accepted and truncated). Commit the red state.

### Subtask T003 – Parser hardening in models.py

- **Purpose**: The production fix.
- **Steps**: In `parse_agent_boundary_string`:
  1. Split as today; if more than four segments, raise `ValueError(f"Too many segments in --agent value: {raw!r} (expected at most 4, got {len(segments)})")` (wording may be tightened, but the count must appear and the message must read cleanly inside `Invalid --agent value: <reason>`).
  2. Pad to four as today; strip each segment.
  3. Tool blank after strip → the existing `ValueError(f"Empty agent tool in --agent value: {raw!r}")`.
  4. Return stripped segments with `(seg or None)` semantics as today.
  5. Update the docstring: stripping, blank-after-strip is absent, >4 segments refused; keep the thin/non-synthesizing contract wording.
- **Files**: `src/specify_cli/status/models.py`.
- **Parallel?**: No.
- **Notes**: Keep the function THIN — no new helper module, no second parser. Type annotations must satisfy mypy --strict.

### Subtask T004 – Targeted test surface + mypy evidence

- **Purpose**: Verify red→green and record evidence.
- **Steps**:
  - `uv run pytest tests/status/test_actor_boundary_normalize.py tests/specify_cli/cli/commands/agent/test_structured_actor_annotations_6400.py tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py -q`
  - `uv run mypy src/specify_cli/status/models.py` (or the repository's configured mypy invocation for strict checks on the module).
  - `uv run python -c "..."` spot-check from quickstart.md.
  - Record commands, exit codes and counts with `spec-kitty agent tasks add-history WP01 --note "..."`.
- **Files**: none new.
- **Parallel?**: No.
- **Notes**: If a pre-existing red appears in these files, do not fix unrelated failures here — report per the Pre-existing Failure Reporting Rule.

### Subtask T005 – Changelog entry

- **Purpose**: User-facing change record.
- **Steps**: Add under `[Unreleased]` in `docs/changelog/CHANGELOG.md`: a bold impact-first lead with `(#6755)`, then Before/After, under 1,200 characters. Mention: segments are now stripped, blank segments treated as absent, and `--agent` values with more than four segments are refused by `move-task`/`mark-status`/`add-history` before any write; free-text `--actor` values still store whole.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: No.
- **Notes**: Root `CHANGELOG.md` is a symlink; edit the docs/ file.

## Test Strategy

- Mandatory: the T001/T002 tests above (red-first through pre-existing entry points).
- Commands: see quickstart.md; record counts in the WP history notes.
- Compiler check: `mypy` strict on the touched module (this WP owns typed sources).

## Risks & Mitigations

- Silent truncation relied on somewhere unseen → re-run the call-site survey (`grep -rn "parse_agent_boundary_string" src/ tests/ --include=*.py`); all callers refuse, pre-check or catch.
- Identity drift for recorded whitespace strings → `actor_full_identity` strips projected parts already; add an assertion if a gap shows.
- Message wording churn breaking pinned tests → the new tests match on stable substrings ("Invalid --agent value", the count), not full messages.

## Review Guidance

- Verify red→green: T001/T002 tests fail on the planning base commit and pass on the final commit.
- Verify the lenient contract: #6400 tests unchanged and green; `actor_from_option` untouched.
- Verify single authority: only `parse_agent_boundary_string` changed in src/.
- Confirm mypy --strict and the targeted pytest surface results recorded in the event log.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
