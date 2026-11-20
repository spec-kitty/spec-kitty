# Contract: approved-lane stale remedy

The approved-lane remedy applies when every one of these holds:

- the caller passes `approved_wp_ids`;
- the lane is a code lane (not a planning lane);
- at least one of the lane's WPs is in `approved_wp_ids`.

In every other case the remedy text is unchanged (US1 AS3).

Ordered content (the command shape per DM-01M7WX8AX56E23AXBZRWGNX4EM; option (b) shown):

1. `Lane <id> is stale: <sibling lane id(s)> landed approved changes to <paths> that conflict with this lane.` This line names exactly `sibling_lanes`.
2. `The in-run auto-rebase stopped: <halt_reason> (<conflicted paths>).`
   - `no_lane_checkout`: "no lane checkout exists; the command below recreates it".
   - `merge_in_progress`: "a merge was left in progress in <checkout>; finish or abort it first".
3. `A conflict resolution on an approved lane is new content: it must be reviewed and approved again.`
4. Commands, one per line:
   - `spec-kitty agent tasks move-task <WP> --to in_progress --mission <slug> ...`. This comes from `move_back_command`. When the WP is `done`, it adds `--force --note <why>`.
   - `spec-kitty agent action implement <WP> --mission <slug> --incorporate <sibling lane id>`, once per sibling.
   - `(resolve the conflict in the checkout that command names, commit)`
   - `spec-kitty agent tasks move-task <WP> --to for_review --mission <slug>`
   - `(an independent reviewer reviews and approves <WP>; the new approval must reach the resolution merge)`
   - `spec-kitty consolidate --mission <slug>`

Invariants:

- No `git merge`, `cd .worktrees` or bare `agent action implement <WP>` without `--incorporate` appears for an approved code lane. A-10 is kept.
- Every printed command runs as printed in the fixture, and none is refused for being approved.
