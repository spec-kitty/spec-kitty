---
work_package_id: WP01
title: "Red-first fix: agent action implement refreshes a reused lane's workspace context"
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
planning_base_branch: issue-6650-agent-action-lane-context-refresh
merge_target_branch: issue-6650-agent-action-lane-context-refresh
branch_strategy: Planning artifacts for this mission were generated on issue-6650-agent-action-lane-context-refresh. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6650-agent-action-lane-context-refresh unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Defect fix
history:
- at: '2026-10-30T13:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/agent/test_agent_action_lane_context_refresh.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/workflow.py
- src/specify_cli/lanes/implement_support.py
- tests/agent/test_agent_action_lane_context_refresh.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first fix: agent action implement refreshes a reused lane's workspace context

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

`spec-kitty agent action implement` claiming a second or later WP into an
already-materialized lane worktree advances the lane's persisted workspace
context (`current_wp`, `wp_id`, `dependencies`) to the newly claimed WP,
through the shared `refresh_reused_lane_context` helper — the same helper the
native `spec-kitty implement` reuse arm and orchestrator-api
`start-implementation` already call. A red-first regression test proves it.

Success criteria:

- The new test is RED on the planning base branch (witnessed and recorded) and
  GREEN after the fix (SC-002).
- After claiming WP02 into a lane that hosted approved WP01, the persisted
  context reports `current_wp=WP02` and `resolve_active_wp_for_branch` on the
  lane branch emits no `ACTIVE_WP_CONTEXT_STALE` warning (SC-001).
- The two already-fixed claim paths and their tests are unchanged (SC-003).
- `test_stale_exists_workspace_reenters_self_heal_not_create` still passes
  (C-001): the exists-path never routes through `top_level_implement`.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6650. Prior art: #3946, PR #4584 (commit
  `48467e8fb9`). Spec: `kitty-specs/agent-action-lane-context-refresh-01M66FF3/spec.md`;
  plan and grounding: `plan.md`, `research.md` in the same directory.
- The exists-path seam: `src/specify_cli/cli/commands/agent/workflow.py`, the
  `_reenter_self_heal` closure (~line 1726), invoked by
  `_ensure_workspace_materialized` only when the resolved workspace already
  exists (`src/specify_cli/cli/commands/agent/workflow_executor.py:512`).
- The shared helper: `refresh_reused_lane_context`
  (`src/specify_cli/lanes/implement_support.py:330`) — idempotent, a no-op
  when the lane has no persisted context or `lane_id is None`.
- The argument shape the orchestrator path uses
  (`src/specify_cli/orchestrator_api/wp_lifecycle.py:577-586`):
  `refresh_reused_lane_context(repo_root, mission_dir_name_or_slug, lane_id, wp_id, parse_wp_dependencies(wp_path))`.
  In `workflow.py`, `mission_slug` is the same resolved handle threaded to
  `top_level_implement` (which saves the context under that name),
  `workspace.lane_id` and `wp.path` are already in scope at the seam.
- Constraints: no fourth variant of the refresh logic (NFR-001); no new git
  subprocess on the path (NFR-002); terminology canon (C-003).
- Do NOT run full heavy suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`); targeted
  files only.

## Branch Strategy

- **Strategy**: lanes (computed by finalize-tasks)
- **Planning base branch**: `issue-6650-agent-action-lane-context-refresh`
- **Merge target branch**: `issue-6650-agent-action-lane-context-refresh`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red regression test

- **Purpose**: Pin the defect through the pre-existing entry point before any
  fix exists (ATDD-first; the gap PR #4584 left must not reopen silently).
- **Steps**:
  1. Create `tests/agent/test_agent_action_lane_context_refresh.py` modelled
     on `tests/agent/test_orchestrator_lane_context_refresh.py` (same fixture
     shape: real git repo, coordination topology, `lanes.json` placing WP01
     and WP02 in one lane, WP01 seeded through `approved` with a materialized
     lane worktree + persisted context naming WP01).
  2. Drive the real `agent action implement` CLI command for WP02 (typer
     `CliRunner` against the agent workflow app, `--agent pi`) instead of the
     orchestrator API. Patch only what the orchestrator test patches (repo
     root resolution), never the seam under test.
  3. Assert: exit code 0; `load_context(repo, "<mission>-lane-c")` reports
     `current_wp == "WP02"` and `wp_id == "WP02"`;
     `resolve_active_wp_for_branch(repo, LANE_BRANCH)` resolves `wp_id ==
     "WP02"` with no `ACTIVE_WP_CONTEXT_STALE` warning.
  4. Run it on the un-fixed tree and WITNESS THE RED (record the failure
     output). Commit the test as its own commit before any fix.
- **Files**: `tests/agent/test_agent_action_lane_context_refresh.py` (new).
- **Parallel?**: No.
- **Notes**: `pytestmark = [pytest.mark.unit, pytest.mark.git_repo]`. If the
  command refuses for a reason unrelated to the defect (e.g. write-checkout
  guard), fix the fixture, never the guard.

### Subtask T002 – The fix

- **Purpose**: Put the third claim path onto the one shared refresh helper.
- **Steps**:
  1. In `src/specify_cli/cli/commands/agent/workflow.py`, inside the
     `_reenter_self_heal` closure, after the `reenter_lane_self_heal(...)`
     call, add the `refresh_reused_lane_context(...)` call with the arguments
     named in Context & Constraints. Import it lazily beside the existing
     lazy `reenter_lane_self_heal` import, matching local style.
  2. Add a short comment citing `#6650` / the F-78 lineage, mirroring the
     comment style of the two existing call sites.
  3. Run the T001 test — it must be green. Run the two existing refresh test
     files — they must stay green.
- **Files**: `src/specify_cli/cli/commands/agent/workflow.py`.
- **Parallel?**: No.
- **Notes**: Do NOT touch `_create_workspace`, `top_level_implement`, or the
  helper itself. The refresh runs only on the exists-path (the closure's
  invocation condition), which is exactly the uncovered path.

### Subtask T003 – Docstring truth on the shared helper

- **Purpose**: The helper's docstring says "Both WP writers that reuse a
  lane — the native ``implement`` flow and the orchestrator API's
  ``start-implementation`` — route through this helper"; after this WP there
  are three, and the docstring must not drift.
- **Steps**: Update the docstring in
  `src/specify_cli/lanes/implement_support.py` (~lines 344-346) and the
  adjacent reuse-arm comment (~line 505) to name every claim path. No
  behaviour change.
- **Files**: `src/specify_cli/lanes/implement_support.py`.
- **Parallel?**: No.

### Subtask T004 – Targeted blast-radius run

- **Purpose**: Evidence for review and the PR's Tests-run section.
- **Steps** (record commands and pass/fail counts):
  - `uv run --frozen pytest tests/agent/test_agent_action_lane_context_refresh.py tests/agent/test_orchestrator_lane_context_refresh.py -q`
  - `uv run --frozen pytest tests/specify_cli/lanes/test_lane_context_refresh.py tests/lanes/test_planning_claim_self_heal.py -q`
  - `uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_implement_single_resolution.py -q`
  - `uv run --frozen ruff check src/specify_cli/cli/commands/agent/workflow.py src/specify_cli/lanes/implement_support.py tests/agent/test_agent_action_lane_context_refresh.py`
  - `uv run --frozen ruff format --check --force-exclude <the same files>`
  - `uv run --frozen mypy src/specify_cli/cli/commands/agent/workflow.py src/specify_cli/lanes/implement_support.py` (match the repo's mypy invocation if file-scoped is not supported)
- **Parallel?**: No.
- **Notes**: Any red not caused by this diff gets classified per the
  baseline-red gotcha (AGENTS.md), never green-washed.

## Test Strategy

The regression test (T001) is mandatory and is the ATDD contract. Fixtures:
real git repo via `tmp_path`, coordination topology mission with
`lanes.json`, seeded status events through the coordination worktree,
materialized lane worktree + persisted context from WP01 — copy the shape
(not the file) of `tests/agent/test_orchestrator_lane_context_refresh.py`.

Compiler/typecheck: the WP owns typed sources; run mypy on the touched
modules per T004.

## Risks & Mitigations

- **Fixture falsity** (the test passing for the wrong reason): assert both
  the persisted context AND the resolver warning absence, exactly like the
  orchestrator test; witness red first.
- **Mission-handle mismatch**: pass the same `mission_slug` already threaded
  through the command; the context filename must resolve identically to the
  one `top_level_implement` saved.
- **Single-branch/repo-root shapes**: the helper no-ops there; no new
  failure mode, and no test changes needed for those shapes.

## Review Guidance

- Verify red→green: the test commit precedes the fix commit; the RED run is
  recorded in the WP history.
- Verify the diff adds exactly one call site of
  `refresh_reused_lane_context` (NFR-001) and no routing through
  `top_level_implement` (C-001).
- Verify the two existing claim paths' tests are untouched and green (SC-003).

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
