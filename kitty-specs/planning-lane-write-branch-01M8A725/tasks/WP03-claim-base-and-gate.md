---
work_package_id: WP03
title: Claim base and the move-into-review gate
dependencies:
- WP02
requirement_refs:
- FR-011
- FR-013
- NFR-004
planning_base_branch: fix/7860-planning-evidence-window
merge_target_branch: fix/7860-planning-evidence-window
branch_strategy: Planning artifacts for this mission were generated on fix/7860-planning-evidence-window. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7860-planning-evidence-window unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 3 - Claim and gate
history:
- at: '2026-11-25T21:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/lanes/test_planning_claim_base_7860.py
- tests/orchestrator_api/test_planning_start_7860.py
- tests/coordination/test_shared_coord_worktree_7860.py
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/implement_support.py
- src/specify_cli/lanes/for_review_gate.py
- src/specify_cli/orchestrator_api/wp_lifecycle.py
- tests/lanes/test_planning_claim_base_7860.py
- tests/orchestrator_api/test_planning_start_7860.py
- tests/coordination/test_shared_coord_worktree_7860.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Claim base and the move-into-review gate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

Then: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item and record it with `add-history`.

---

## Objectives & Success Criteria

When a default Mission's planning WP is claimed before landing, the claim base is recorded from the checkout the WP actually works in (the Mission-branch checkout). The `for_review` gate then counts only that WP's commits since the claim. Both hold on the CLI path and on the orchestrator API path.

Done when:
- `lanes/implement_support.py` records the claim base from `resolved_workspace.worktree_path` rather than `repo_root` (around :370). Unchanged shapes still record the repository root, because their workspace is the repository root.
- `orchestrator_api/wp_lifecycle.py` (around :320–345) for a repo-root/planning lane returns:
  - `workspace_path` = the resolved planning checkout;
  - `lane_branch` from `planning_lane_target(...).branch`, replacing `_repo_root_lane_branch` for the planning case;
  - the claim base recorded from that checkout.
  - The `single_branch` write-checkout refusals still run for `single_branch`.
- `lanes/for_review_gate.py` (around :225–255) diffs in the resolved checkout (it already resolves `worktree_path`). Its refusal message names that checkout and branch instead of "the repository root checkout" for the new resolution kind.
- A ratchet test proves that a CLI status commit in the shared coordination worktree carries only status paths and leaves a planning agent's uncommitted (and staged) edits intact (FR-013). If it is red, fix it in the status commit path and report the file you changed (an out-of-map edit, with rationale).

Requirements: FR-011, FR-013 (and FR-001 on the orchestrator path).

## Context & Constraints

- Plan IC-03. Squad finding: the claim base recorded at the repository root makes the gate diff the whole Mission history when the work happens in the coordination worktree (`research.md` R-03 #2).
- The claim base is a **clone-local** ref (`lanes/claim_base.py`), idempotent by absence. A WP claimed before the upgrade keeps its old base. That is acceptable (guidance only); do not rewrite existing refs.
- The window *evidence* start is not the claim base. WP04 uses the claim-event commit (durable). Do not couple them.
- `safe_commit` stages explicit paths with `git commit --only` (`git/commit_helpers.py:35`), so FR-013 may already hold. T014 is then a ratchet.

## Branch Strategy

- **Planning base branch**: `fix/7860-planning-evidence-window` · **Merge target branch**: `fix/7860-planning-evidence-window`
- Use the workspace `spec-kitty agent action implement WP03 --agent claude --mission planning-lane-write-branch-01M8A725` prints.

## Subtasks & Detailed Guidance

### Subtask T010 – Red tests for the claim base and the gate

- **File**: `tests/lanes/test_planning_claim_base_7860.py` (new), real git.
- **Cases**:
  1. A default, not-landed planning WP claimed through the CLI path (`ensure_repo_root_lane_workspace` or the function at implement_support.py:~350) → `read_claim_base(...)` equals the coordination worktree's HEAD, not the root checkout's HEAD (make the two differ: put a commit on the target after the Mission was created).
  2. Gate, hollow: right after the claim, with no commit, the `for_review` gate refuses, even though the Mission branch holds spec, plan and tasks commits beyond the target.
  3. Gate, positive control: one owned commit in the coordination worktree → the gate passes.
  4. Explicit topology: claim base = repo root HEAD (unchanged).
- Look at `tests/lanes/` for existing gate fixtures (`grep -rl "read_claim_base\|evaluate_for_review" tests/lanes`).

### Subtask T011 – Claim base from the resolved checkout (CLI)

- `implement_support.py:~370`: `record_claim_base(repo_root, resolved_workspace.worktree_path, mission_slug, wp_id)`. The first argument stays the repository root that owns the common git dir.
- Check `_ensure_repo_root_checkout_available`: its occupancy and dirty checks apply to `single_branch`. Decide whether the new kind needs a dirty check on the coordination worktree. Recommended: **no** new refusal (status commits use `--only`), but document the decision in `add-history`.

### Subtask T012 – Orchestrator API start

- **File**: `orchestrator_api/wp_lifecycle.py`.
  - Use the workspace from `resolve_workspace_for_wp` (or `planning_lane_target`) for `workspace_path` and `lane_branch`.
  - Keep `_ensure_repo_root_checkout_or_fail` for `single_branch`.
  - Update `_repo_root_lane_branch`'s docstring (:150–164), which states "a repo-root (planning-artifact) WP runs on the target branch". Either delegate it to `planning_write_ref`, or retire it if nothing else uses it (`grep -rn _repo_root_lane_branch src tests`).
- **Test**: `tests/orchestrator_api/test_planning_start_7860.py`. Follow the existing `tests/orchestrator_api` start-implementation tests. Assert the envelope's `workspace_path` and `lane_branch` for the default shape and for an explicit-topology control.

### Subtask T013 – Gate message

- `for_review_gate.py:~246`: for the new kind say "no implementation commit since claim in the Mission branch checkout `<path>` (branch `<branch>`) beyond `<sha>`". Keep the text for the other kinds. Update the docstring (:225–232) that calls `lane_branch` the target.

### Subtask T014 – Ratchet: status commit in the shared coordination worktree

- **File**: `tests/coordination/test_shared_coord_worktree_7860.py` (new).
- **Setup**: a coordination worktree with an untracked new file under `kitty-specs/<slug>/research/`, a modified tracked file, and a staged change to a third file (all owned-file content). Then drive one status transition for another WP through the production path that commits status in that worktree (`emit_status_transition` through `BookkeepingTransaction`, or `spec-kitty agent tasks move-task` on a real repo).
- **Assert**:
  - the new commit's changed paths are status paths only (`git show --name-only HEAD`);
  - the three edits are still present and uncommitted, and the staged one is still staged;
  - the transition succeeded.
- If it is red, the fix belongs where the status commit is made. Report it and keep the change minimal.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/lanes tests/orchestrator_api tests/coordination tests/status -q -p no:cacheprovider
make test-fast
```

Plus ruff, format and mypy on the changed files.

## Risks & Mitigations

- The orchestrator envelope shape is a public contract (`orchestrator_api/envelope.py::CONTRACT_VERSION`). Changing a *value* is not a shape change; do not add or remove keys without a version bump decision (ask the dispatcher).
- In-flight claims keep their old claim base: the gate may refuse them. That is consistent with "guidance only"; WP04's evidence refusal names the remedy.

## Standing rules

Signed commits; no model names; zero ruff/format/mypy findings, no suppressions, complexity ≤ 15; no `test-full`; attribute every red.

## Review Guidance

- Claim base equals the resolved checkout's HEAD for the new kind, and the repo root's HEAD otherwise.
- The gate refuses hollow WPs even with Mission history ahead of the target.
- The orchestrator API and the CLI agree.
- The FR-013 ratchet uses the production status-commit path, not a mock.

## Progress & Status

- `spec-kitty agent tasks add-history WP03 --note "..."` · `mark-status T010 … --status done` · `move-task WP03 --to for_review`
