# Quickstart: what an operator sees after this Mission

Three walkthroughs, end to end. Output is abbreviated. Flags and codes are those in [contracts/](./contracts/README.md).

## 1. A small Mission becomes `single_branch` (any target)

```bash
spec-kitty agent mission create add-retry-flag --json
# "topology": "single_branch", "topology_source": "default", "topology_provisional": true,
# "mission_branch": "kitty/mission-add-retry-flag-01ABCDEF"
git branch --list 'kitty/*'    # exactly one new branch: the Mission topic branch
git worktree list               # no new worktree
```

`/spec-kitty.specify`, `/spec-kitty.plan` and `/spec-kitty.tasks` write to the topic branch in the write checkout. The write checkout is the repository root checkout, now on the topic branch.

```bash
spec-kitty agent mission finalize-tasks --mission add-retry-flag --validate-only --json
# "topology_decision": {"preview": true, "rule": "wp_count_le_2", "wp_count": 2, "settled_topology": "single_branch", ...}
spec-kitty agent mission finalize-tasks --mission add-retry-flag --json
# "topology_decision": {"settled_this_run": true, "settled_topology": "single_branch", ...}
```

Implement and review run in the write checkout. Every transition is stamped with the Mission branch head. If someone commits content after WP01's approval and outside WP02's window, consolidation refuses before any branch moves:

```bash
spec-kitty consolidate --mission add-retry-flag
# LANE_MOVED_AFTER_APPROVAL  lane-planning  kitty/mission-add-retry-flag-01ABCDEF
#   commit 3f2a1c0 was committed after WP01's approval and is in no later WP's review window.
#   Send WP01 back for review and approve it again, or revert the commit.   (exit 1, target unchanged)
```

For an in-flight `single_branch` Mission approved before the upgrade:

```bash
spec-kitty consolidate --mission old-mission
# APPROVAL_STAMP_MISSING ... WP01
spec-kitty consolidate --mission old-mission --attest-approved-reviewed WP01 --attest-reason "reviewed in PR #123"
```

## 2. A bigger Mission becomes `lanes_with_coord` (any target)

```bash
git switch main          # main is a protected target
spec-kitty agent mission create payments-refactor --json      # provisional, topic branch only
# ... specify / plan / tasks: 5 WPs that compute to 3 code lanes ...
spec-kitty agent mission finalize-tasks --mission payments-refactor --json
# "topology_decision": {"rule": "lanes_with_coord", "wp_count": 5, "code_lane_count": 3, "target_protected": true,
#                       "provisional_topology": "single_branch", "settled_topology": "lanes_with_coord"}
```

What changed at settlement:
- The repository root checkout is back on `main`, the branch it was on at create. It left the topic branch first, because git does not let one branch be checked out in two worktrees.
- The topic branch `kitty/mission-payments-refactor-<mid8>` is now the **coordination branch**. It keeps the same name, and every pre-finalize status event is readable.
- The coordination worktree is materialized on the topic branch.
- Nothing landed on `main`. Lanes will be cut from the topic branch, lane consolidation lands into it, and it lands on `main` at consolidate.
- `lanes.json` is written. No lane branch or lane checkout exists yet.

If the write checkout was dirty or another WP was in progress there, finalize refuses (`WRITE_CHECKOUT_DIRTY` / `WRITE_CHECKOUT_OCCUPIED`), and if the branch recorded at create is gone or checked out elsewhere it refuses `TOPOLOGY_SETTLEMENT_REFUSED`. Either way the Mission stays provisional with nothing changed.

```bash
spec-kitty agent action implement WP01 --mission payments-refactor
# Lane checkout: .worktrees/payments-refactor-<mid8>-lane-a   (no status.events.jsonl or status.json on disk)
```

From any working directory (the lane checkout, the coordination worktree, the repository root checkout), with or without the coordination worktree present, status reads the same:

```bash
spec-kitty agent tasks status --mission payments-refactor
```

Hand-off works after the lane checkout is gone, because the gate reads the lane branch:

```bash
git worktree remove .worktrees/payments-refactor-<mid8>-lane-a    # for illustration only
spec-kitty agent status emit WP01 --to for_review --mission payments-refactor   # passes if the lane branch has commits
```

On an **unprotected** target the same Mission settles the same way: `lanes_with_coord`, with the topic branch as the coordination branch and nothing landed on the target at settlement (`"target_protected": false` in the decision; the outcome does not depend on it). Plain `lanes` or `coord` are available only with an explicit `--topology` at create.

## 3. Consolidation ends with cleanup

```bash
spec-kitty consolidate --mission payments-refactor
# ... claim, gate PASS, landing verified ...
# Coordination teardown: done
# Lane cleanup
#   Removed   lane-a  (recreate: git branch kitty/mission-payments-refactor-lane-a refs/spec-kitty/discarded/...)
#   Kept      lane-b  MERGE_UNSAFE_WORKTREE_DIRTY  .worktrees/...-lane-b has uncommitted changes.
#             Remedy: commit or discard them, then run: spec-kitty doctor workspaces --prune
#   Removed   lane-c
# exit 0; the consolidation record is cleared
```

- With `--retain-worktrees` set at create, lanes show `Retained ... retained by policy` instead.
- `orchestrator-api consolidate-mission` returns the same per-lane list in `data.lane_cleanup` (contract 1.25.0).
- After #7275 merges, landing through a pull request also cleans up without waiting for the merge:

```bash
spec-kitty accept --mode pr --mission payments-refactor
# lanes absorbed by the pushed PR head: removed; unpushed lanes: Kept NOT_LANDED_ON_NAMED_REMOTE
spec-kitty doctor workspaces --prune      # backstop for anything kept
```

## Upgrading an existing clone

`spec-kitty upgrade` runs the clone-local lane-checkout migration once per clone. It reports, per lane worktree, one of: `excluded`, `flagged_redundant`, `refused_lane_only_events` (listing the event ids; that worktree is left untouched) or `skipped_mid_operation`. A second run changes nothing. `spec-kitty doctor` lists any lane branch with lane-authored status changes (`LANE_STATUS_AUTHORED`).
