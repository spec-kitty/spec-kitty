# for_review gate refusal (S2: FR-010 to FR-014)

The gate reads `refs/heads/<lane>` from the repository root checkout. A lane checkout is never required.

| Case | Verdict | Message (shape) |
|---|---|---|
| Lane branch has ≥ 1 commit beyond base; checkout absent or present | pass | none |
| No commit beyond base | refuse (`reason_code=LANE_NO_COMMIT_BEYOND_BASE`) | `WP01 cannot move to for_review: lane branch kitty/mission-<slug>-lane-a has no commit beyond <base>. Commit the WP's work on that lane branch, or pass --force if there is genuinely nothing to commit.` The message does not mention a worktree. |
| `refs/heads/<lane>` absent | refuse (`reason_code=LANE_BRANCH_MISSING`) | `WP01 cannot move to for_review: lane branch kitty/mission-<slug>-lane-a does not exist. Restore it (see the lane-tip record) or re-run spec-kitty agent action implement WP01.` |

## Envelope impact

- **`orchestrator-api transition`**: unchanged. `TRANSITION_REJECTED` with `data.{wp_id, lane_id, ...}`; the message carries the reason. No new key and no version bump.
- **`agent status emit --json`**: unchanged keys (`error`, `wp_id`, `lane_id`).
- **`move-task`**: checkout-present checks (dirty, currency, health, contamination) are unchanged and run only when a checkout exists (C-006). With the checkout absent, it applies the same shared verdict.

The base ref is passed after `--end-of-options`, so a ref beginning with `-` is never read as an option.
