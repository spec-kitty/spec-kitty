---
work_package_id: WP07
title: Lane work tip and destroyed-lane guard (#5115 red→green)
dependencies:
- WP05
requirement_refs:
- FR-018
- FR-019
- FR-020
- FR-021
- FR-022
- FR-024
- NFR-001
planning_base_branch: issue-5100-single-branch-topology
merge_target_branch: issue-5100-single-branch-topology
branch_strategy: Planning artifacts for this mission were generated on issue-5100-single-branch-topology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5100-single-branch-topology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-branch-topology-honesty-01M3M22V
base_commit: b1d397061491858776902e2ea97355cb3d50457d
created_at: '2026-09-29T02:23:01.082952+00:00'
subtasks:
- T028
- T029
- T030
- T031
- T032
- T033
phase: Phase 6 - Lane work tip
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- src/specify_cli/lanes/lane_tip.py
- src/specify_cli/policy/lane_tip_recorder.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_install_lane_tip_recorder.py
- tests/lanes/test_issue_5115_destroyed_lane_non_coord.py
- tests/lanes/test_lane_tip.py
- tests/policy/test_lane_tip_recorder.py
- tests/specify_cli/upgrade/migrations/test_install_lane_tip_recorder.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/lanes/lane_tip.py
- src/specify_cli/policy/lane_tip_recorder.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_install_lane_tip_recorder.py
- tests/lanes/test_issue_5115_destroyed_lane_non_coord.py
- tests/lanes/test_lane_tip.py
- tests/policy/test_lane_tip_recorder.py
- tests/specify_cli/upgrade/migrations/test_install_lane_tip_recorder.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Lane work tip and destroyed-lane guard (#5115 red→green)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, `implementer`, `claude`) and follow its guidance.

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log for `review_ref` and address every item.

---

## Objectives & Success Criteria

This WP closes #5115 for LANES and flat missions (FR-018 to FR-022, FR-024, NFR-001, US6, SC-002). Today the guard at `worktree_allocator.py:268-353` checks whether the lane's creation **base** is reachable. In non-coord topologies the base is always an ancestor of the target, so the guard never fires, and a destroyed lane that held unmerged committed work is silently re-cut empty.

After this WP:

1. **Tip ref.** Every lane commit records `refs/spec-kitty/lane-tip/<lane-branch>`. A plain-`sh` `post-commit` + `post-rewrite` recorder writes it at commit time. spec-kitty's own lane advances write it too.
2. **Guard.** On `implement` of a destroyed lane whose WP is in a trigger state (`in_progress`, `blocked`, `for_review`, `in_review`), the guard refuses with `DestroyedLaneError`. It names the tip SHA and a restore command, unless the tip is **absorbed**: equal to the base, an ancestor of the target, or a merge-tree no-op.
3. **Unknown tip.** A destroyed lane with a context but no tip ref refuses with `LaneWorkTipUnknownError`.
4. **Context deleted.** If the workspace record was deleted but a tip ref exists, the guard still refuses. It must not fail open.
5. **Orchestrator.** Lanes allocated through the orchestrator persist their context through the allocator (FR-022).

**Done when**:
- The red-first `tests/lanes/test_issue_5115_destroyed_lane_non_coord.py` was committed RED first and is now GREEN.
- `tests/lanes/test_issue_4889_destroyed_lane_guard.py` still passes. Any flip must be justified per plan fold M7.
- The recorder runs in under 50 ms and never changes a commit's exit status.
- Foreign hooks are never overwritten.

## Context & Constraints

- **Read first:**
  - `contracts/lane-work-tip.md` (the binding hook body and API)
  - `data-model.md` "Guard decision table"
  - `research.md` R-6, R-7
  - `plan.md` IC-04 and folds M1, M4, M5, M7, plus the minor "lane_tip must not import consolidation"
- **Tip storage is a git ref, not a `WorkspaceContext` field.** This deliberately departs from the brief's wording; the justification is in `plan.md` Complexity Tracking and `research.md` R-6. Do not add a tip field to `WorkspaceContext`.
- **Hook discipline:**
  - Install the recorder with a **separate** installer (`policy/lane_tip_recorder.py`) into `git rev-parse --git-path hooks`.
  - Install only when the slot is empty or already carries the spec-kitty lane-tip signature line. Otherwise warn once and skip (C-010, charter "User Customization Preservation").
  - Never go through `policy/hook_installer.py`'s backup-and-overwrite path.
  - Mark the hook executable (`chmod 0o755`). On Windows, Git for Windows runs `sh` hooks.
- **Absorption** needs `git merge-tree --write-tree` (git ≥ 2.38). On an older git, `is_absorbed` raises `AbsorptionUnsupported`, and the guard refuses (fail closed). Reuse the version-probe approach at `consolidation/reconciliation.py:~815`, but **do not import `consolidation.*`** from `lanes/`.
- **Out-of-map edits** (rationale per edit in the Activity Log):
  - `lanes/implement_support.py` (record at reuse/claim)
  - `lanes/auto_rebase.py`
  - `cli/commands/agent/tasks_move_task.py` (record at for_review / safe_commit)
  - `orchestrator_api/commands.py:~1376` (allocate through the allocator)
  - the terminal-transition clear site
  - `cli/commands/context.py:~258` (`context cleanup` must not delete tip refs)

## Branch Strategy

- **Planning base / merge target**: `issue-5100-single-branch-topology`.
- Run `spec-kitty implement WP07 --mission single-branch-topology-honesty-01M3M22V`.

## Subtasks & Detailed Guidance

### Subtask T028 – Red-first #5115 acceptance test (commit FIRST, alone)

- **File**: `tests/lanes/test_issue_5115_destroyed_lane_non_coord.py`
- **Markers**: `pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]`

**Fixture.** Clone `tests/lanes/test_lane_allocation_integrity_e2e.py::_build_coord_mission` into a local `_build_lanes_mission`: no coordination branch, no coord bootstrap, `meta.json` `"topology": "lanes"`, status seeded on the target branch.
- Reuse `_run_cli_implement`, `_destroy_lane`, `_commit_real_work` and `_wp_context` by importing them from that module. If they are private and the import is awkward, copy the minimal pieces and say so in the Activity Log.
- Use `_ids()` from `tests/lanes/test_issue_4889_destroyed_lane_guard.py` for per-test identity.
- Set `monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_file))` so a global `core.hooksPath` cannot interfere.

**Tests:**

1. `test_destroyed_lane_refuses_and_names_tip`
   - **Setup:**
     1. Run `implement WP01` through the CLI; WP01 is now `in_progress`.
     2. Make a **plain `git commit`** in the lane worktree, of a file inside WP01's `owned_files`, so the pre-commit guard passes. Record `work_sha`.
     3. Destroy the worktree and the branch with `git worktree remove --force` and `git branch -D`.
   - **Act:** run `implement WP01` again.
   - **Assert:**
     - the exit code is non-zero;
     - `work_sha` (or its 7+ character prefix) appears in the output;
     - `"Lane worktree ready"` does not appear;
     - the lane worktree path does not exist and the lane branch does not exist;
     - afterwards, `git rev-parse refs/spec-kitty/lane-tip/<branch>` equals `work_sha`.
2. `test_squash_merged_lane_reopens` (control)
   - **Setup:** commit on the lane, then `git merge --squash <lane>` into the (unprotected) target and commit. Then destroy the lane.
   - **Assert:** `implement WP01` exits 0.
3. `test_tip_equals_base_reopens` (control): no commits, destroy the lane → exit 0.
4. `test_context_deleted_still_refuses`: the same as test 1, but also delete `.kittify/workspaces/<name>.json` before re-implementing → still refuses.
5. `test_unknown_tip_fails_closed`: a context is present but the tip ref is deleted and the lane is destroyed → `LANE_WORK_TIP_UNKNOWN`, and nothing is created (US6.6).
6. `test_live_branch_backfills_tip`: a pre-existing lane has a live branch but no tip ref → the next spec-kitty touch records the tip from the branch (FR-021).
7. `test_ancestor_merged_lane_reopens`: the lane work was merged into the target (not squashed) and the lane destroyed → exit 0 (US6.3).

**Red for the right reason.** On the planning base, test 1 must fail at the `exit_code != 0` assertion: today the CLI exits 0 with "Lane worktree ready". Controls 2 and 3 are green on main, which is fine.

**Commit this test alone** with the message `test(lanes): red-first #5115 destroyed lane non-coord`.

### Subtask T029 – `lanes/lane_tip.py`

Implement the API from `contracts/lane-work-tip.md`: `tip_ref`, `record_tip`, `read_tip`, `clear_tip` and `is_absorbed`, plus the `AbsorptionUnsupported` exception.

`is_absorbed(repo_root, tip, target, base)` answers these in order:
1. `tip == base` → True.
2. `git merge-base --is-ancestor tip target` → True.
3. `git merge-tree --write-tree target tip`:
   - exit 0 and the output tree equals `git rev-parse target^{tree}` → True;
   - exit 1 (conflict) → False;
   - unknown option or a git version below 2.38 → raise `AbsorptionUnsupported`.

**Tests** go in `tests/lanes/test_lane_tip.py`, using real tmp git repos:
- a two-commit squash with later unrelated edits to the target → absorbed;
- destroyed unique work → not absorbed;
- a conflict → not absorbed;
- the ancestor and equals-base cases;
- the unsupported path, simulated by monkeypatching the version probe.

### Subtask T030 – Recorder installer and install migration

**Installer.** `policy/lane_tip_recorder.py` provides `install_lane_tip_recorder(repo_root) -> list[Path]`, which installs both `post-commit` and `post-rewrite`:
- Write the exact body from the contract. The signature line is `# Generated by spec-kitty (lane-tip recorder).`
- Resolve the hooks dir with `git rev-parse --git-path hooks`.
- Skip with a single warning if a foreign hook exists.
- It is idempotent.

**Where it is called.** From lane allocation (`allocate_lane_worktree`, once per repo, cheap), next to the existing `install_commit_guard` call at `implement_support.py:~178`.

**Migration.** `m_4_0_0rc5_install_lane_tip_recorder` uses `TARGET_VERSION="4.0.0rc5"`, `runs_on_worktrees=False`, and calls the installer. Test it in `tests/specify_cli/upgrade/migrations/test_install_lane_tip_recorder.py`, looking it up through the registry.

**Tests** in `tests/policy/test_lane_tip_recorder.py`:
- installs into an empty slot;
- skips a foreign hook and leaves its bytes unchanged;
- re-install is idempotent;
- honours `core.hooksPath`;
- the hook records on a lane commit from a **linked worktree**;
- the hook does **not** record for `kitty/mission-foo-lane-recut-01ABC` (slug containing `-lane-`, M4) or for a non-lane branch;
- the hook records after `git commit --amend` via post-rewrite;
- the hook records for a `git commit --no-verify` lane commit, after `git rebase` of the lane (post-rewrite), and after `git cherry-pick` onto the lane (FR-018);
- the hook exits 0 even when `update-ref` fails;
- timing: 20 commits with the hook add under 50 ms p95 each versus no hook. If CI noise is too high, mark the timing test `timing`/`slow` and keep a single-sample sanity bound of < 150 ms added per commit. The NFR-001 evidence is the `timing`-marked p95 ≤ 50 ms assertion; the sanity bound must never be cited as NFR evidence (analysis finding I2).

### Subtask T031 – Guard order and tip-based decision

Extend WP01's `_destroyed_lane_verdict` with tip inputs. The order, per plan fold M7:
1. **Coord base-unreachable check:** unchanged; still fires first.
2. **No context and no tip ref** → proceed, because this is a fresh lane.
3. **Context present, status unreadable** → refuse, as today.
4. **Trigger state** (the existing set) and a tip ref present:
   - absorbed → proceed;
   - not absorbed → refuse `DestroyedLaneError(tip_sha=...)`;
   - `AbsorptionUnsupported` → refuse.
5. **Trigger state, context present, no tip ref** → refuse `LaneWorkTipUnknownError`, unless the live branch still exists (backfill, T032).
6. **Context missing but a tip ref present**, with a trigger state → evaluate as in step 4. This closes the context-cleanup fail-open.

The **base-reachable early return is removed for the tip path**.

**Errors:**
- `DestroyedLaneError` gains an optional `tip_sha`. When it is set, the message names it plus the restore command `git branch <b> refs/spec-kitty/lane-tip/<b>` and the abandon command `git update-ref -d refs/spec-kitty/lane-tip/<b>`.
- The existing messages without a tip stay byte-identical.
- New `LaneWorkTipUnknownError` with `error_code = "LANE_WORK_TIP_UNKNOWN"`.

**#4889 tests.** Run `tests/lanes/test_issue_4889_destroyed_lane_guard.py`. If a test that relied on "base reachable → re-open" now refuses because its fixture has an unabsorbed tip, re-pin it only if the new refusal is correct (DIRECTIVE_041: judge the test), and justify each change in the Activity Log.

### Subtask T032 – Record at spec-kitty advances; clear; backfill

**Record** (`record_tip`) after:
- allocation, on the FRESH, REUSE and CRASH_RECOVERY routes;
- `_merge_recorded_planning_commit`;
- `_merge_dependency_lane_tips`;
- `auto_rebase` (the lane is merged forward);
- the for_review transitions (`agent/status.py:276`, `orchestrator_api/commands.py:1755`);
- `tasks_move_task.py:~933` `safe_commit` in a lane.

**Clear** (`clear_tip`), extending WP02's single `claim_base.on_wp_terminal` hook (post-tasks fold M-3; no second terminal hook):
- when a WP reaches `done` or `canceled` and no other non-terminal WP remains in that lane;
- at consolidation lane teardown. That is sibling-owned, so make it a one-line call and note it.

**Backfill on touch.** When the guard or allocator sees a context without a tip ref and the branch is still live, record the tip from the branch. This is local-state recording, not topology inference.

**Context cleanup.** `spec-kitty context cleanup` must leave tip refs alone; only the context JSON is removed.

### Subtask T033 – Orchestrator context through the allocator (FR-022)

`orchestrator_api/commands.py:1376` allocates a lane without writing a `WorkspaceContext`. Move `save_context` into `allocate_lane_worktree`, so it is written on every route, and delete the now-duplicate writes in `implement_support.py`. Existing callers then get a context automatically.

**Test:** extend `tests/orchestrator_api/test_issue_4889_caller_independence.py`, or add a focused test, asserting that an orchestrator-allocated lane has a context and that a tip ref is recorded after a commit.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/lanes/test_issue_5115_destroyed_lane_non_coord.py tests/lanes/test_lane_tip.py tests/policy/test_lane_tip_recorder.py tests/specify_cli/upgrade/migrations/test_install_lane_tip_recorder.py -q
.venv/bin/python -m pytest tests/lanes/test_issue_4889_destroyed_lane_guard.py tests/lanes/test_lane_allocation_integrity_e2e.py tests/lanes/test_destroyed_lane_guard_helpers.py tests/orchestrator_api/test_issue_4889_caller_independence.py tests/lanes/test_worktree_allocator.py tests/lanes/test_worktree_allocator_atomicity.py tests/lanes/test_worktree_allocator_rematerialize.py tests/specify_cli/lanes/test_worktree_allocator_recovery.py tests/specify_cli/lanes/test_worktree_allocator_coord.py -q
.venv/bin/python -m pytest tests/policy/test_hook_installer_rendering.py tests/policy/test_hook_installer_execution.py -q
make test-fast
.venv/bin/mypy --strict src/specify_cli/lanes/ src/specify_cli/policy/ ; .venv/bin/ruff check . ; .venv/bin/ruff format --check .
```

## Risks & Mitigations

- **Hook portability (Windows).** Keep the body POSIX, with no bashisms; the test asserts the body text.
- **Interaction with the existing pre-commit repin migration** (ADR 2026-08-27-1). The recorder is a separate file, so the pre-commit hook is not touched.
- **Performance of the absorption check.** It runs only on the destroyed-lane path, which is rare.
- **Coord regressions.** Coord's first-step check is unchanged. Run the coord allocator tests.

## Review Guidance

- Red→green for T028, with a real plain `git commit` in the lane. Mocked commits are not acceptable.
- Verify the hook skips foreign hooks and does not match `-lane-` slugs.
- Verify the guard order against `data-model.md`.
- Verify that `context cleanup` no longer causes fail-open.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
