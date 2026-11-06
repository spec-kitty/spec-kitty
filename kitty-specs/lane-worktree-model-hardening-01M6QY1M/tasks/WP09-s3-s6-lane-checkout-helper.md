---
work_package_id: WP09
title: S3/S6 - one lane-checkout helper; status exclusion on every lane checkout
dependencies:
- WP01
- WP03
- WP08
requirement_refs:
- FR-021
- FR-022
- FR-040
- SC-004
- C-013
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T047
- T048
- T049
- T050
- T051
- T052
- T053
phase: Phase 3 - S2/S3/S6 lanes carry no live status
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- src/specify_cli/lanes/lane_checkout.py
- tests/architectural/test_lane_checkout_single_seam.py
- tests/lanes/test_lane_checkout_helper.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/lane_checkout.py
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/lanes/lifecycle_sync.py
- src/specify_cli/cli/commands/agent/workflow.py
- src/specify_cli/coordination/workspace.py
- tests/architectural/test_lane_checkout_single_seam.py
- tests/lanes/test_lane_checkout_helper.py
- tests/integration/test_lane_lifecycle_sync.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 - S3/S6: one lane-checkout helper; status exclusion on every lane checkout

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP09 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP09 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

- FR-021: every lane checkout is created by one helper `lanes/lane_checkout.py::open_lane_checkout(...)` - routes: allocation FRESH, FRESH_LEGACY, CRASH_RECOVERY; `lifecycle_sync` recreate (`:139`); the review checkout (`agent/workflow.py::_create_review_worktree`); and the printed recreate command (`workspace/landed_worktrees.py:636-638`).
- The helper runs `git worktree add` on an ATTACHED branch (so the `post-commit` lane-tip hook fires), installs the lane-tip hook, the `.spec-kitty/` local exclude and the status sparse exclusion.
- FR-040: on every topology with code lanes (`lanes` included, not only coordination topologies) a lane checkout has no `status.events.jsonl` / `status.json` on disk, while the lane branch tree still carries the fork-time blob (C-008).
- FR-022 / C-013: a non-vacuous architectural gate `tests/architectural/test_lane_checkout_single_seam.py` fails on any lane `git worktree add` outside the helper (empty allowlist, scan floor, planted violations).
- SC-004: 0 Mission status files in any route's checkout; 100% of creation sites through the helper.

## Context & Constraints

- Read: spec User Story 5 and 7, FR-020 to FR-022, FR-040, C-007, C-008; `research.md` R-4, R-5; `data-model.md` §4 (`LaneCheckoutRequest`); WP01 ADR (restated ruling 3) and WP03's ADR `2026-04-03-1` amendment if written.
- Today three routes skip the exclusion even for coordination topologies, and `lanes` never registers it (brief B §7).
- No lease state is built (C-007): the helper is the future lease acquire, nothing more.
- Shared file: `src/specify_cli/workspace/landed_worktrees.py` is owned by WP16 (blocked on #7275). Your hunk is the printed recreate command at `:636-638` only; make it and record it as out-of-map.
- Lane-tip recorder rules (CLAUDE.md "Lane work tips"): hooks are skipped with a warning when `core.hooksPath` is global/system, `/dev/null`, missing or inside the work tree. Keep that behaviour.
- Sparse configuration is per-worktree (clone-local). Do not touch `lanes/auto_rebase.py` (C-008: the union merger and deletion refusals stay).
- C-011 red-first.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T047 - Tidy

- `coordination/workspace.py::lane_sparse_checkout_patterns` takes the resolved Mission dir name (keep the slug+mid8 wrapper for existing callers).
- Rename `worktree_allocator._register_sparse_checkout_if_coord` (it will no longer be coord-only), e.g. `_register_lane_status_exclusion`. Behaviour-preserving commit first.

### Subtask T048 - Red-first tests

In `tests/lanes/test_lane_checkout_helper.py` (real git fixtures):

- `test_lanes_topology_allocation_has_no_status_files_on_disk` (+ assert `git cat-file -e <lane>:kitty-specs/<dir>/status.events.jsonl` still succeeds: fork-time blob in history);
- `test_review_checkout_has_no_status_files`;
- `test_crash_recovery_checkout_has_no_status_files`;
- `test_lane_tip_hook_fires_in_helper_checkout` (commit in the checkout; `refs/spec-kitty/lane-tip/<branch>` updated).

In `tests/integration/test_lane_lifecycle_sync.py`: deliberately flip the assertion at `:124` to `test_lifecycle_sync_recreate_has_no_status_files` (explain the flip in the commit message).

Commit red.

### Subtask T049 - The helper

- `open_lane_checkout(request: LaneCheckoutRequest) -> Path` with fields `repo_root`, `mission_slug`, `mission_dir_name`, `lane_id`, `branch`, `create_branch_from: str | None`, `route` (enum: `allocation_fresh | allocation_legacy | recovery | lifecycle_sync | review | recreate`).
- Steps: `git worktree add` attached (`-b` when `create_branch_from` is set); install lane-tip hook through the existing installer; add `.spec-kitty/` to the worktree's local exclude; register sparse exclusion of the Mission's `status.events.jsonl` and `status.json` (patterns from `lane_sparse_checkout_patterns`); reapply sparse checkout so the files leave the disk.
- Keep functions <= 15 complexity; one step per helper.

### Subtask T050 - Allocation routes

- `worktree_allocator.py` FRESH, FRESH_LEGACY, CRASH_RECOVERY call the helper; remove their raw `worktree add`. Preserve all existing refusal codes (`DESTROYED_LANE`, `LANE_WORK_TIP_UNKNOWN`, etc.).

### Subtask T051 - Other routes [P]

- `lifecycle_sync.py:~139` recreate -> helper.
- `agent/workflow.py::_create_review_worktree` (~2298) -> helper (route `review`).
- `workspace/landed_worktrees.py:636-638`: the printed recreate command should name a `spec-kitty` re-entry path if one exists (`spec-kitty agent action implement <WP>`), else keep the git command but make sure the CLI-created route goes through the helper. Out-of-map hunk.

### Subtask T052 - Single-seam gate

- `tests/architectural/test_lane_checkout_single_seam.py`: AST/string scan of `src/` for `worktree add` invocations (subprocess arg lists and helper calls) that create lane checkouts; only `lanes/lane_checkout.py` may contain one. Distinguish coordination worktree creation (allowed in its own module: define the allowed module set as constants and justify each).
- Scan floor (files scanned >= measured), planted violations in `tmp_path` (raw list form, f-string form, helper alias). <= 5 s (NFR-006).

### Subtask T053 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/lanes/test_lane_checkout_helper.py tests/integration/test_lane_lifecycle_sync.py tests/architectural/test_lane_checkout_single_seam.py -q
uv run --frozen pytest tests/lanes tests/specify_cli/lanes tests/coordination tests/integration/sparse_checkout tests/specify_cli/workspace -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -n auto --dist loadfile -k "review or workflow"   # out-of-matrix dir
uv run --frozen pytest tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_layer_rules.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict <touched src files>
```

Never `make test-full` or a bare `tests/architectural/` sweep.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP09] ...**`, naming the trace file); the orchestrator appends them.

## Risks & Mitigations

- Sparse checkout on Windows: use git's own sparse commands, no shell globs (NFR-008).
- Detached checkouts silently skip the hook: the helper refuses detached creation.
- Existing worktrees are not migrated here (WP10 owns the migration).

## Review Guidance

- Every route through the helper; `lanes` topology excluded too; fork-time blob still in history; gate non-vacuous; lifecycle-sync flip explained.

## Definition of Done

- T047-T053 done; tests green; out-of-map hunk recorded; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T047 T048 T049 T050 T051 T052 T053 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP09 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
