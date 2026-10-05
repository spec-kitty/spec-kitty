# Contract: `LANE_MEMBERSHIP_FROZEN` refusal (finalize-tasks)

**Surface**: `spec-kitty agent mission finalize-tasks --mission <handle> [--json] [--validate-only]`

**When**:
- the mission already has a lane manifest, **and**
- the re-finalize cannot keep every started work package on its recorded lane, or the status log is unreadable.

**Exit code**: `1`.

**Side effects**: none.
- No status event and no lane manifest are written.
- Work package files, `tasks.md` and `meta.json` are restored byte-identical by finalize's existing write-scope
  restore.
- No commit.

## JSON envelope (`--json`)

```json
{
  "error": "Cannot re-finalize: started work packages would change lane. WP01 (lane-a) and WP02 (lane-b) would be merged into one lane. …",
  "error_code": "LANE_MEMBERSHIP_FROZEN",
  "reason": "started_lanes_collapsed",
  "conflicts": [
    {
      "reason": "started_lanes_collapsed",
      "wp_ids": ["WP01", "WP02"],
      "recorded_lanes": ["lane-a", "lane-b"],
      "remedy": "Remove the overlap that forces WP01 and WP02 into one lane (for example, move the shared path into a new work package that depends on both), then re-run finalize-tasks."
    }
  ],
  "next_step": "Remove the overlap that forces WP01 and WP02 into one lane …",
  "spec_kitty_version": "…"
}
```

The key set is fixed: `error`, `error_code`, `reason`, `conflicts`, `next_step`, plus the standard
`spec_kitty_version`. When a `--target-branch` override revert or a status leftover note applies, finalize's
existing extra keys (`target_branch_override_revert_error`, `status_commits_not_undone`) may also appear.

## Reasons and remedies

| `reason` | Trigger | Remedy (non-destructive) |
|---|---|---|
| `started_lanes_collapsed` | One computed group holds started WPs recorded in two or more lanes | Remove the overlap that forces the named work packages into one lane (move the shared path into a new work package that depends on them, or drop it from one of them), then re-run finalize-tasks. |
| `started_wp_removed` | A started WP is missing from the plan, and was not excluded by cancellation | Restore the task file of the named work package. To retire it, cancel it with `spec-kitty agent tasks move-task <WP> --to canceled --mission <handle>` without clearing its owned files, then re-run finalize-tasks. |
| `started_wp_kind_changed` | A started WP's `execution_mode` now puts it on the other side of `lane-planning` | Restore the named work package's `execution_mode`, put the new kind of work in a new work package, then re-run finalize-tasks. |
| `status_unreadable` | A lane manifest exists, but the status log cannot be read (malformed, undecodable or unreadable) or its surface cannot be resolved. A malformed line in a log that finalize's earlier frontmatter read already parses is refused there first, with that step's existing message. | Repair the status log (`spec-kitty agent status validate --mission <handle>` reports the problem; `spec-kitty agent status doctor` checks status hygiene), then re-run finalize-tasks. |

Remedies never suggest any of the following: deleting `lanes.json`, a force flag, `git reset`, `git restore`,
`git checkout -- .`, or removing worktrees or branches.

## Console (no `--json`)

```
Error: Cannot re-finalize: started work packages would change lane. …
  started_lanes_collapsed: WP01 (lane-a), WP02 (lane-b)
  Remedy: Remove the overlap that forces WP01 and WP02 into one lane …
```

## Unchanged surfaces

- A successful re-finalize keeps the existing success payload.
- The `collapse_report` may contain a new `rule` value, `frozen_lane_membership` (additive).
