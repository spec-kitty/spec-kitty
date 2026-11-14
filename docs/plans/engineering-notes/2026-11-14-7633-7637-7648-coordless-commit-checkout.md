---
title: Coordination-less status commit checkout, review claim follow-up, idempotent no-op
description: Grounding note for #7633 (slice 2 of checkout-verdict-agreement-01M7B1GG), #7637 and #7648, delivered as one pull request.
doc_status: draft
kind: Reference
audience:
- profile: internal/system-architect
  guidance_text: Check the reproductions, the chosen fix seams, the invariants and the dispositioned siblings.
updated: '2026-11-14T00:00:00Z'
---
# Coordination-less status commit checkout, review claim follow-up, idempotent no-op

Read-only grounding at `origin/main` `d7cedd7e` (2026-11-14), committed before the spec. One
runner for three tickets that sit in the same code (`coordination/transaction.py` and the
logic that picks which checkout a coordination-less commit runs in), so the fixes do not
conflict. #7633 is slice 2 of Mission `checkout-verdict-agreement-01M7B1GG` (slice 1, #7594,
landed as PR #7638); its research (`kitty-specs/checkout-verdict-agreement-01M7B1GG/research.md`)
is on `main` and is reused here. Prior grounding for the neighbouring fixes:
`2026-11-13-7589-7632-lanes-claim-and-protected-create.md`.

## Reproductions (red on `d7cedd7e`)

| ticket | entry point | red evidence |
|---|---|---|
| #7633 | `BookkeepingTransaction.acquire` (coordination-less arm), real `agent mission create` core, real git | `tests/coordination/test_coordless_status_commit_checkout.py`: the 11-row matrix of #7633. 7 rows agree; the 4 diverging rows reproduce the issue's table exactly (today: lane-holder row `root`, both (a) rows `other`, (b) `other`) |
| #7637 | `agent action review WP02 --agent ...` on the `lanes_with_coord` review fixture, protected `main` | drop the `lanes_with_coord` protection lift in `_review_args` (`tests/integration/review/test_review_range_acceptance_action.py`): 8 `lanes_with_coord` cells fail (exit 1, `PROTECTED_BRANCH_REFUSED` on the follow-up commit to `main`) |
| #7648 | `BookkeepingTransaction.commit_idempotent` | `tests/specify_cli/coordination/test_transaction.py`: staging an already-committed status log with `status_entries` raising `GitCommandError` raises `BookkeepingCommitFailed` (`SafeCommitStagedTreeUnchanged` wrapped, rollback run); the strict `commit()` control raises as documented |

## Root causes and chosen seams

**#7633.** `coordination/transaction.py::_write_branch_holder` picks the checkout with the raw
`status.read_surface.non_lane_checkout_holding_branch` probe (l.225, used at l.878 and inside
`_primary_partition_holder`, l.235). #7615 made `PlacementSeam.write_dir(kind).surface_root` the
one checkout authority. Fix: the coordination-less arm takes `write_dir(STATUS_STATE).surface_root`
when the caller's ref is `write_target(STATUS_STATE).ref`, else the repository root checkout (the
fallback #7633 proposes). `_primary_partition_holder` takes the PRIMARY `write_dir(...).surface_root`
under the same rule; for a default Mission before landing that is the topic holder (same answer
as `primary_partition_checkout` today), so #7372 is unchanged.

The seam's checkout cannot always commit: git lets only one checkout hold a branch, so when
*another* checkout holds the write ref (shape (a)), or the holder has no Mission directory
(shape (b)), or a lane worktree holds it, the seam's checkout (the repository root checkout) is
not on the ref. Today (a)/(b) commit in the other checkout (which the read door never reads for
(a), and reads only as a ref for (b)), and the lane row fails late with `SafeCommitHeadMismatch`.
**Operator ruling Q8 (2026-11-13), option a:** (b) refuses with a named code, never a root
fallback. One up-front check gives that rule to every such shape: when the chosen checkout's HEAD
is not the destination ref, `acquire` raises `BookkeepingPolicyRefused` with
`STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH` before any write. Applying it to (a) and the lane row
was raised to the orchestrator (recommended option 1, proceeding unless overruled).

**#7637.** `review_claim_transition` (`cli/commands/agent/workflow_executor.py`) passes the
PRIMARY-partition WP file with the status artifacts, although the claim writes no byte to it
(the #2816 cutover). `_commit_via_coordination_transaction` partitions it into a second,
`commit_to_primary_target` transaction on `main`, which the policy refuses before any content
check. Fix: commit exactly the paths the claim wrote, the status pair
(`claim_status_pair_paths`), as the implement claim already does (#5673).

**#7648.** `commit_idempotent` trusts the fail-open `_worktree_has_pending_changes`; on
`GitCommandError` the strict `commit()` runs and wraps `SafeCommitStagedTreeUnchanged` (raised
only on the index authority) into a rollback plus `BookkeepingCommitFailed`. Fix (PR #7639
pattern): on the `commit_idempotent` path only, catch that typed signal and return the no-op
receipt pinned at HEAD. The strict `commit()` keeps raising.

**`_resolve_legacy_porcelain_root` residual** (named in the #7639 note). The legacy leaf
(`_commit_via_legacy_safe_commit`) commits with `worktree_root=repo_root`, but its advisory
porcelain pre-check runs in `.worktrees/<slug>-coord` whenever that directory exists (and can
even materialize it through `CoordinationWorkspace.resolve`). The pre-check must ask the checkout
the commit runs in. Fix: run it in `repo_root`, and short-cut only when every path is inside that
checkout (`checkout_root_in_spelling`), which keeps the #2684 phantom guard without an existence
probe. The other directory-exists picks are filed, not changed (below).

## Invariants that must survive

- **One placement authority** (#7615 / #7546, DIRECTIVE_044, C-001): no raw holder probe left in
  `transaction.py`; the arm consumes `write_target` / `write_dir`, it does not re-derive.
- **Writes land where the status read door reads** (ADR `2026-11-06-2`), or refuse.
- **FR-061 / #7372:** a default Mission's PRIMARY commit runs in its topic holder before landing;
  explicit / legacy / landed Missions keep the repository root checkout.
- **#2647 caller contract:** the coordination-less arm never reads `Path.cwd()`.
- **#2861 / WP04 T015:** an unchanged follow-up commit is a no-op receipt; the strict `commit()`
  still surfaces an empty changeset (`test_commit_idempotent_still_raises_*`).
- **#2684:** the legacy pre-check never reports a path in another checkout as committed.
- **Owned checkouts:** the seam is constructed with `owned=`; owned Missions keep
  `owned.owned_root`.

## Architectural gates

- `test_no_write_side_rederivation.py`: `write_target(kind).ref` is the sanctioned form; its
  `checkout_branch_or_fallback` allowlist entry names closed #2453 and is repointed to an open
  issue (#1878, the coordination placement strangler epic, parent of #7633).
- `test_layer_rules.py`: `specify_cli -> mission_runtime` is the allowed direction.
- `test_no_dead_symbols.py` / `test_no_dead_modules.py`: `_write_branch_holder` and
  `_resolve_legacy_porcelain_root` are deleted with their last callers.
- `test_status_read_single_door.py`, `test_coord_read_residuals_closeout.py`,
  `test_no_legacy_terminology.py`: re-run.

## Similar-surfaces squad (dispositions)

| surface | disposition |
|---|---|
| `transaction.py::_write_branch_holder` / `_primary_partition_holder` | **in scope** (#7633) |
| `git/commit_helpers.py::_head_mismatch_holder` (remedy text only) | no action; docstring at l.213 updated (#7633 asks for it) |
| `status/read_surface.py` topic-holder lookups (read door itself) | no action (the read authority) |
| `coordination/planning_commit.py::primary_partition_checkout` (l.249) | no action (planning commit, seam-backed caller) |
| `workflow.py::_resolve_legacy_porcelain_root` | **in scope** (residual named in the brief) |
| `tasks_move_task.py:2321`, `mission_finalize_planning_pin.py:433` (coord worktree picked by existence, diagnostics) | file-and-link (follow-up issue) |
| settled `lanes_with_coord` Mission with its coordination worktree removed: `write_dir(TASKS_INDEX)` builds on the root checkout (#7633 comment) | file-and-link (seam change in `mission_runtime`, not this arm) |
| `commit_idempotent` fail-open (#7648) | **in scope** |
| `write_seam.py` `_EMPTY_CHANGESET_PREFIX`, `implement_claim.py` warning, `invocation/executor.py` (from the #7639 note) | already filed there; no action |
| other claim follow-ups (implement claim, resume refresh) | already commit only the status pair (#5673); no action |

## Tracked-issues squad (dispositions)

- **Closes:** #7633, #7637, #7648.
- **Refs:** #7594 / #7638 (slice 1), #7615 / #7546 (seam authority), #7589 / #7639 (legacy-leaf
  twin), #5673 (status-pair precedent), #7372, #2684, #2861, #1878 (parent), #7545 (parent),
  #5764 (husk writes on an unmaterialized coord worktree, related, unchanged).
- **Duplicates:** none; no open PR touches these files.
