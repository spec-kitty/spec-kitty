# Code grounding: single_branch claim gaps (#5663, #5680)

Read-only grounding pass, run before specify. Base: branch
`issue-5680-single-branch-claim-gaps`, stacked on PR #5659
(`origin/ccr-ba04d8aa-fx98ee` @ `28b0dc1f`). #5659 had not merged into
`origin/main` (@ `ef5ce4f0`) when this note was written.

Reader: the implementer and reviewer of this mission.

## 1. #5663 against #5659: already fixed

**Claim:** #5659 fixes #5663 on every single_branch `agent action implement`
path, including the `_reenter_self_heal` path that #5663 traced.

Evidence:

- `src/specify_cli/cli/commands/agent/workflow.py` (around L1637-1643) calls
  `_guard_repo_root_claim(main_repo_root, mission_slug, wp_id, workspace)`
  **before** `_ensure_workspace_materialized(...)`. The re-enter path therefore
  never skips the claim seam.
- `workflow_executor.guard_repo_root_claim` delegates to
  `lanes/implement_support.py::guard_repo_root_claim`. That function runs the
  write-checkout refusals and then `record_claim_base(repo_root, repo_root, slug, wp)`,
  which is idempotent by absence. The scope is `is_repo_root_lane(workspace)` and
  stored topology `single_branch`.
- `reenter_lane_self_heal`'s planning-lane arm still does not call
  `record_claim_base`. That no longer matters, because the guard records the
  base before the self-heal runs.

Reproduction on a scratch single_branch mission, built with the
`test_single_branch_write_checkout_e2e.py` helpers:
1. `agent action implement WP01`. The claim base was recorded
   (`read_claim_base` returned a SHA).
2. Commit, then `mark-status T001 --status done`.
3. `move-task WP01 --to for_review` without `--force`, which exits 0.

Existing pin: `tests/integration/test_single_branch_write_checkout_e2e.py::test_action_implement_records_claim_base_and_reaches_review`
runs exactly that sequence through the CLI and asserts the claim base. #5659's
PR body records it as red on the pre-#5659 code ("#5459: the loop tests give 3
failed, 1 passed").

Sibling probe (not part of #5663): a `lanes` mission's `planning_artifact` WP,
claimed through `agent action implement`, then committed and moved to
`for_review` without `--force`, also passes. The guard skips non-single_branch
missions, but the claim base is still recorded on that path, so the for_review
gate is satisfied there.

**Verdict:** #5663 is a duplicate of #5459, closed by #5659. No new fix and no
new pinning test; the named e2e test already covers the sequence. The PR uses
`Closes #5663` with this evidence.

## 2. The occupancy scan (#5680)

- **Where:** `src/specify_cli/lanes/checkout_occupancy.py::in_progress_wps_in_write_checkout`.
  It is called only from `lanes/implement_support.py::_ensure_repo_root_checkout_available`,
  which raises `WriteCheckoutOccupiedError` (`WRITE_CHECKOUT_OCCUPIED`).
- **Callers of that refusal:**
  - `guard_repo_root_claim`, which both claim verbs use: `spec-kitty implement`
    through `create_lane_workspace`, and `agent action implement` through
    `workflow_executor.guard_repo_root_claim`.
  - `implement`'s early check in `cli/commands/implement.py`.
- **What it enumerates:**
  1. Every mission from `FsMissionResolver(repo_root).all_missions()`, that is,
     every `kitty-specs/*` directory **as checked out on the current branch**.
  2. Filters, cheapest first:
     1. stored topology `single_branch` (`migration.backfill_topology.read_topology`);
     2. `lanes.json` assigns at least one WP to a repo-root lane;
     3. not `status.is_mission_completed(feature_dir)`;
     4. reduced status snapshot (`read_events` + `reduce` through
        `placement_seam(...).read_dir(STATUS_STATE)`) shows that WP `in_progress`.
- **How "finished" is knowable today** (the only authority is `status/lifecycle.py`):
  - `is_mission_completed` is true when `meta.json.merged_at` is set (written by
    `consolidate`), or when `derive_mission_lifecycle` reports
    `recently_completed`/`archived`, meaning every WP is terminal (`done`/`canceled`).
  - `is_mission_merged` is the narrower check: `merged_at` only, aware of re-opens.
  - `mission_number` is display-only. CLAUDE.md "Mission Identity Model" says it
    is never used for lookup, so it is **not** a liveness signal.
  - Acceptance commits and `acceptance-matrix.json` are not a status authority.
  - Lifecycle `stale`/`abandoned` are wall-clock heuristics (14/30 days). A
    claim refusal must not hinge on a wall clock.

## 3. #5680 reproduced

**Real record.** In a local clone of this branch, checked out on a fresh topic
branch `probe-5680-topic` with one new single_branch mission created there,
`in_progress_wps_in_write_checkout(root, root)` returns
`[('reconcile-flake-family-01M34HR7', 'WP04')]` in about 2 s over 552 missions.

The occupying mission:
- `meta.json`:
  - `topology: single_branch`
  - `target_branch: fix/reconcile-flake-family-4882`
  - no `mission_branch`
  - no `merged_at`
  - `mission_number: null`
- `lanes.json`: WP01-03 in code lanes, WP04 in `lane-planning` (a repo-root lane).
- Status: WP01-03 `approved`, WP04 `in_progress` (claimed 2026-09-22T17:33Z).
  No WP is `done`, so `is_mission_completed` is False.
- It reached `main` through a squash merge of its topic branch (`1fc1c29b` in
  this shallow history), never through `spec-kitty consolidate`, so no merge
  marker was ever written.

**Synthetic fixture.**
1. Mission A (single_branch, target `issue-5100-work`) claims WP01 through
   `agent action implement`, and its status is committed.
2. The operator branches `next-topic` from that tip and creates mission B
   (single_branch, target `next-topic`).
3. `spec-kitty implement WP01 --mission B` exits 1, and so does
   `spec-kitty agent action implement WP01 --mission B`. Both print
   `old-mission-… WP01 is already in_progress in the shared write checkout … Move WP01 out of in_progress (approve, reject, or block it) before claiming …`
   (`WRITE_CHECKOUT_OCCUPIED`).

The refusal gives no runnable command, and does not say which branch the
occupant lives on.

### Root-cause reading

For a single_branch mission, the authoritative status surface is the
mission's **write branch**: `mission_runtime.single_branch_write_ref(stored_topology, meta.mission_branch, meta.target_branch)`,
which is the protected-target mint or the target branch. CLAUDE.md "Status
Model / Execution Workspace Strategy" says the status source of truth is the
resolved status surface, not the open worktree.

The scan reads each mission's status **from whatever branch the repository root
checkout currently has**. When that branch is not the occupant's write branch,
the snapshot it reads is a copy carried over by branch integration (a squash or
merge) or by branching off. That copy is not the occupant's live status. The
scan already sees only missions whose directory exists on the current branch,
so in practice it was branch-scoped in one direction already. The defect is
that it trusts a foreign-branch copy as live.

## 4. Gates and test seams

No architectural gate names `checkout_occupancy.py` or `implement_support.py`
directly. These generic gates apply to a change there:

- `tests/architectural/test_layer_rules.py`: `lanes/` stays in `specify_cli`.
  `mission_runtime.single_branch_write_ref` is already imported by
  `specify_cli` (allowed direction `mission_runtime <- specify_cli`).
- `tests/architectural/test_no_dead_symbols.py`: no new public symbol without a
  `src/` caller. New helpers stay private to the module.
- `tests/architectural/test_module_length_agreement.py`: keep module growth small.
- `tests/architectural/test_issue_named_test_census.py`: do not add new
  issue-named test files. Put tests in the owning suites.
- `tests/architectural/test_no_legacy_terminology.py`: prose.
- `scripts.docs.check_changelog_style`: the changelog entry.

Test seams:

- `tests/lanes/test_checkout_occupancy.py` (fast, unit): the scan itself. Every
  existing case targets `main` while sitting on `main`, so all stay valid.
- `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`
  (CLI level, `spec-kitty implement`): the `occupied` refusals assert
  `"Move WP01 out of in_progress"`, so that phrase must stay in the message.
  Its repo sits on `trunk`, with `target_branch: trunk`.
- `tests/integration/test_single_branch_write_checkout_e2e.py`
  (`agent action implement` loop, `agent_loop_mission` fixture).

## 5. Churn (90 days)

The clone is shallow (50 commits), so `git log --since=90.days` only reaches
back to the graft:

- `checkout_occupancy.py`: 1 commit visible.
- `implement_support.py` and `claim_base.py`: 3 commits combined.

Both files were born in #5100 (single-branch-topology-honesty, late September)
and changed again in #5659. They are young, hot code, owned by the
single_branch line of work.
