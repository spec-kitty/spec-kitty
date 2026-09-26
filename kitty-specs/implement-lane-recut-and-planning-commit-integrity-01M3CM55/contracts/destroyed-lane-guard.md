# Contract: destroyed-lane fail-closed guard (#4889)

**Surface**: `src/specify_cli/lanes/worktree_allocator.py::allocate_lane_worktree` — a pre-flight evaluated after the REUSE (`worktree_path.exists()`) and CRASH_RECOVERY (`_branch_exists()`) gates and **before** the FRESH routes.

## Preconditions consulted
- `CTX` = persisted `WorkspaceContext` for the WP's lane exists (`workspace/context.py::find_context_for_wp` / `load_context`).
- `STATE` = canonical WP lane state via the reducer over the **resolved coordination status surface** (never the lane worktree tree).
- refs: neither the local lane branch nor its worktree exists.
- `REACH` = the lane's **cut-from base** (`WorkspaceContext.base_commit`, the parent SHA fixed at allocation — used as a **proxy** for the lane's work tip, which is not persisted) is an ancestor of the target branch.

> **Known limitation (non-blocking, tracked as follow-up).** `WorkspaceContext` persists only `base_commit` — the SHA the lane was *cut from* (its parent), never the lane's own committed-work tip (no work-tip SHA is persisted anywhere the guard can read once the branch is `-D`'d). So `REACH` is evaluated against the parent, not the work tip. This is **sound in the dominant direction**: `¬REACH(base)` ⟹ the work tip is also unreachable ⟹ REFUSE is always correct, which covers the entire default **coord topology** (the coordination branch's lifecycle commits never land on target, so `base` is genuinely not an ancestor of target) — i.e. the filed #4889 P0 is fully closed. The residual is a narrow **false-pass** window when `REACH(base)=True` but the work commits did *not* land on target (e.g. a non-squash merge of the parent line only) with a stale non-terminal status — there the guard suppresses and a re-cut could still strand work. Closing it requires persisting the lane's work tip at commit time so `REACH` can key on the actual tip; deferred to avoid a `WorkspaceContext` schema + write-on-commit change inside this P0. See the mission PR body / follow-up issue.

## Behaviour
- **Trigger** (`CTX` ∧ `STATE ∈ {in_progress, blocked, for_review, in_review}` ∧ ¬branch ∧ ¬worktree ∧ ¬`REACH`): raise a typed, fail-closed error →
  - non-zero exit;
  - message names the missing lane branch (`branch_name`) and a concrete recovery ref/command (reflog / `git fsck --lost-found`);
  - **must not** print `✓ Lane worktree ready`;
  - **must not** overwrite `.kittify/workspaces/<slug>-lane-<id>.json` or any lane metadata.
- **No trigger**: fall through to existing routing unchanged (REUSE / CRASH_RECOVERY / FRESH / terminal / reachable-tip resume).

## Caller-independence (FR-008)
Because the guard is inside `allocate_lane_worktree`, it fires for **both** callers:
- `lanes/implement_support.py::create_lane_workspace` (CLI `spec-kitty implement`);
- `orchestrator_api/commands.py::_resolve_start_workspace` (`agent action implement` / `start-implementation` / `transition --to claimed`).

## Regression assertions (must be RED pre-fix)
1. Destroyed lane + `in_progress` via **CLI** → non-zero, diagnostic, CTX unchanged, no `Lane worktree ready`.
2. Same via **orchestrator/agent** caller → identical refusal.
3. Non-`in_progress` non-terminal (`blocked`/`for_review`/`in_review`) destroyed lane → refusal.
4. Genuinely fresh lane (no CTX, `planned`) → normal fresh creation (no false positive).
5. Intact worktree → REUSE no-op; intact branch, gone worktree → CRASH_RECOVERY re-attach (control arms preserved).
6. Re-open after merge (tip ancestor of target) → resume/recreate, no false refusal.
