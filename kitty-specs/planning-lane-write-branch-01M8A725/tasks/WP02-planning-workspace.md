---
work_package_id: WP02
title: Planning workspace in the Mission-branch checkout
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-006
- FR-014
- C-003
- SC-003
planning_base_branch: fix/7860-planning-evidence-window
merge_target_branch: fix/7860-planning-evidence-window
branch_strategy: Planning artifacts for this mission were generated on fix/7860-planning-evidence-window. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7860-planning-evidence-window unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 2 - Workspace
history:
- at: '2026-11-25T21:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/workspace/
create_intent:
- tests/specify_cli/workspace/test_planning_workspace_7860.py
execution_mode: code_change
owned_files:
- src/specify_cli/workspace/context.py
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/cli/commands/agent/workflow.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
- src/specify_cli/cli/commands/agent/tasks_status_view.py
- src/specify_cli/core/worktree_topology.py
- src/runtime/next/prompt_builder.py
- src/specify_cli/ownership/workspace_strategy.py
- src/specify_cli/ownership/kind_normalisation.py
- tests/specify_cli/workspace/test_planning_workspace_7860.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Planning workspace in the Mission-branch checkout

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission planning-lane-write-branch-01M8A725`). Address every item and record it with `add-history`.

---

## Objectives & Success Criteria

`implement` resolves a planning work package's workspace as follows:
- For a default Mission that has not landed, it resolves to the checkout holding the Mission branch (the coordination worktree once settled), names that branch, and says the work is committed there.
- For every other shape it stays exactly as today.

Done when:
- `resolve_workspace_for_wp` returns, for a default not-landed Mission's planning WP:
  - `worktree_path` = `planning_lane_target(...).checkout`;
  - `branch_name` = the Mission branch;
  - a **distinct** `resolution_kind` (recommended: `"mission_branch_checkout"`);
  - `lane_id="lane-planning"`.
- It returns today's `"repo_root"` result for explicit topologies, landed Missions and the `single_branch` repo-root lane. Owned checkouts are untouched.
- A missing holder refuses with WP01's named error, and is never silently the repository root (NFR-002).
- Every reader of `resolution_kind == "repo_root"` was audited, and the new kind is handled where it means "no lane worktree / planning surface".
- The `implement` output names "the Mission branch (the coordination branch)" and the coordination worktree path (FR-002). The ancestry message no longer says "repository root checkout on the target branch" for this shape.
- Docstrings and the "main repository" wording are fixed (Branch-Intent Terminology, charter).

Requirements: FR-001, FR-002, FR-006, FR-014 (docstrings), NFR-002.

## Context & Constraints

- Plan IC-02. Contract C1 (`contracts/planning-write-branch.md`). Data model: PlanningWorkspace.
- Today's three planning arms, all `resolution_kind="repo_root"`:
  - `_resolve_planning_artifact_arm` (context.py:874, `branch_name=None`, via `ownership/workspace_strategy.create_planning_workspace`);
  - `_resolve_repo_root_lane_arm` (around :989, `resolve_single_branch_write_ref`);
  - `_resolve_planning_lane_arm` (around :1039, `lane_branch_name(...PLANNING_LANE_ID)` → target).

  Route the planning shapes through **one** helper that reads `planning_lane_target` (WP01). Keep `_planning_surface_root(owned)` precedence for owned checkouts.
- **C-003 (#5604)**: in `cli/commands/agent/workflow.py`, edit only:
  - the planning ancestry message (around :2036–2040, "Planning work package: code dependency lanes are not merged into the repository root checkout on the target branch …");
  - the workspace print for planning WPs.

  Do **not** touch the `implement()` hunks around :1842–1925 (the `--incorporate` option and its preflight), which #5604 changes.
- Other readers found by the post-spec squad: 14 places read `resolution_kind == "repo_root"`. `grep -rn '"repo_root"' src` lists more candidates, so classify each:
  - `runtime/next/prompt_builder.py:~397`
  - `cli/commands/implement.py:~339`
  - `agent/tasks_parsing_validation.py:~948`
  - `agent/workflow.py:~2207`
  - `agent/tasks_status_view.py:~138,147`
  - `agent/workflow_executor.py:~2684`
  - `core/worktree_topology.py:~68,193,198,256,258,308`
  - `agent/tasks_move_task.py:~1525`, owned by **WP04**: leave a note there for WP04, or make the change in WP04.

  A reader outside `owned_files` that genuinely needs the new kind may be edited with a one-line rationale in `add-history` (ownership leeway); list each such edit.
- `ResolvedWorkspace`: check whether `resolution_kind` is a `Literal[...]` type. If it is, extend it and let mypy find every exhaustive match.

## Branch Strategy

- **Planning base branch**: `fix/7860-planning-evidence-window` · **Merge target branch**: `fix/7860-planning-evidence-window`
- Use the workspace `spec-kitty agent action implement WP02 --agent claude --mission planning-lane-write-branch-01M8A725` prints.

## Subtasks & Detailed Guidance

### Subtask T005 – Red tests for the planning workspace resolution

- **File**: `tests/specify_cli/workspace/test_planning_workspace_7860.py` (new). Reuse fixture helpers from `tests/specify_cli/workspace/` or `tests/runtime/test_workspace_context_unit.py` where they build `lanes.json` and `meta.json`.
- **Cases**:
  1. default, not landed, settled `lanes_with_coord`, coordination worktree on `kitty/mission-<slug>` → kind `"mission_branch_checkout"`, path = that worktree, `branch_name` = Mission branch, lane `lane-planning`;
  2. explicit `--topology lanes_with_coord` (no `topology_source: default`) → `"repo_root"`, repo root, the target (today's values; assert them byte for byte against the pre-change behaviour);
  3. default, landed → `"repo_root"`, the target;
  4. default `single_branch` repo-root lane → unchanged (`"repo_root"`, write branch per `resolve_single_branch_write_ref`);
  5. default, not landed, coordination worktree removed → raises WP01's named error (or the `ActionContextError` you translate it to); never the repo root;
  6. an owned checkout → unchanged (the owned arm wins).
- Optionally run a real-CLI check of `agent action implement` output in WP05's suite instead; keep this file at unit level with real git.

### Subtask T006 – One planning workspace path in `workspace/context.py`

- **Steps**:
  1. Add one helper, `_planning_workspace(repo_root, mission_slug, wp_id, normalized_wp, execution_mode, lane_wp_ids, target_branch, owned)`. It returns `ResolvedWorkspace`:
     - for an owned checkout, keep today's owned-surface behaviour;
     - otherwise call `planning_lane_target`. If `on_mission_branch`, return the new kind with its checkout and branch; else return today's `"repo_root"` result, preserving each arm's current `branch_name` semantics, so explicit shapes are byte-identical. Note today's planning_artifact arm returns `branch_name=None`; keep that for unchanged shapes unless a test proves otherwise.
  2. Make the three arms delegate to it for the planning-lane cases. Keep the `single_branch` code-WP behaviour of `_resolve_repo_root_lane_arm` unchanged: that lane can hold code WPs.
  3. Translate WP01's missing-checkout error into the error type `resolve_workspace_for_wp` callers already handle. Find what `implement` prints for a refused resolution (for example `ActionContextError` with a code) and reuse it; name the code `PLANNING_CHECKOUT_MISSING` if a new one is unavoidable, and document it.
  4. Complexity ≤ 15: extract small helpers rather than growing `_resolve_workspace_for_wp_impl`.

### Subtask T007 – Audit and update the `resolution_kind == "repo_root"` readers

- For each reader listed above, decide one of:
  - (a) the reader means "not a lane worktree / planning surface", so the new kind must behave like `"repo_root"`. Prefer one predicate on `ResolvedWorkspace` (for example `is_shared_checkout` / `has_no_lane_worktree`) over string comparisons repeated at every site; it shrinks the readers and keeps one authority.
  - (b) the reader means "literally the repository root checkout", so the new kind must not match.
- Record the classification table in `add-history` (file:line → a/b → change).
- `core/worktree_topology.py` (6 hits) is the densest. Read it fully before changing.
- Keep behaviour identical for unchanged shapes. The existing tests under `tests/specify_cli/cli/commands/agent`, `tests/runtime`, `tests/specify_cli/workspace` and `tests/core` must stay green.

### Subtask T008 – `implement` messages

- **`cli/commands/implement.py`** (around :320–337, `_print_workspace_ready_banner` and the contract line): for the new kind print, for example:
  - "Planning-artifact work for this WP is committed on the Mission branch `<branch>` (the coordination branch)"
  - `cd <coordination worktree>`
  - "Commit your planning-artifact changes there; `spec-kitty consolidate` lands them on `<target>`."

  Keep today's text for `"repo_root"`, but fix "Make planning-artifact changes directly in the repository root" wording only where it is wrong for the shape.
- **`cli/commands/agent/workflow.py`**:
  - The workspace print for `agent action implement` ("📍 Workspace: cd …", "Lane workspace: lane-planning"): print the coordination worktree and the Mission branch for the new kind.
  - The ancestry message (around :2036–2040): for the new kind say code dependency lanes are not merged into the Mission branch and reach the target through `spec-kitty consolidate`. Keep the text unchanged for other shapes.
  - Stay out of the #5604 hunks.
- The `next` runtime prompt (`runtime/next/prompt_builder.py`) must print the same workspace for the new kind.

### Subtask T009 – Docstrings and "main repository" campsite fixes

- `workspace/context.py:14`, `:796`, `:893` ("main repository root/checkout") → "repository root checkout", and describe the Mission-branch case.
- `ownership/workspace_strategy.py:9` and the module docstring: planning WPs work in the planning surface (the repository root checkout, or the Mission branch's checkout before a default Mission lands).
- `ownership/kind_normalisation.py:4` ("`lane-planning`, whose branch is the target branch") → "whose branch is the target branch, or the Mission branch before a default Mission lands (#7860)".
- Charter: never "main repository" (Branch-Intent Terminology Governance).

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/workspace tests/runtime tests/specify_cli/cli/commands/agent tests/core -q -p no:cacheprovider
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_workspace_resolution_doc.py tests/architectural/test_owned_checkout_single_authority.py -q
make test-fast
```

Plus ruff, format and mypy on every changed file. If `tests/architectural/test_workspace_resolution_doc.py` pins documented kinds, update the doc it reads and say so.

## Risks & Mitigations

- Fan-out of 25 callers: run the full owning test directories listed above.
- #5604 overlap in `workflow.py`: diff your hunks against the C-003 region before committing.
- A silent fallback to the repo root is a bug (NFR-002). Test 5 guards it.

## Standing rules

Signed commits; no model names; zero ruff/format/mypy findings, no suppressions, complexity ≤ 15; no `test-full`; attribute every red.

## Review Guidance

- One planning helper; the three arms delegate to it.
- The explicit-topology results are byte-identical (test 2).
- Is the audit table recorded? Is every reader classified?
- Messages name the Mission branch and the coordination worktree; the #5604 hunks are untouched.

## Progress & Status

- `spec-kitty agent tasks add-history WP02 --note "..."` · `mark-status T005 … --status done` · `move-task WP02 --to for_review`
