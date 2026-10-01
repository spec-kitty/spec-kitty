---
name: spk-run-blocked-recovery
description: "Recover from Spec Kitty blocked runtime states, missing artifacts, failed guards, stale worktrees, and decision-required loops."
---

# spk-run-blocked-recovery

Use this skill when `next`, review, accept, merge, or sync output
shows a blocker.

## Flow

1. Capture the exact command and blocker output.
2. Classify the blocker: missing artifact, invalid state, guard failure,
   worktree/git issue, sync issue, auth issue, or user decision required.
3. Use the nearest specialist skill: setup doctor, git workflow, team sync,
   review, accept, or merge.
4. Make one repair, rerun the same command, and compare output.
5. Escalate to the user only when the command requires a product decision or
   external credential.

## Rule

Do not bypass a guard. Resolve the reason the guard exists.
