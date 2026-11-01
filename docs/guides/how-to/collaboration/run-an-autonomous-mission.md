---
title: Run an Autonomous Mission
description: Run specify, plan, tasks, implementation review, mission review, and retrospective steps without manual merge workarounds.
doc_status: active
updated: '2026-11-01'
type: how-to
audience:
- profile: external/tech-lead-evaluator
  guidance_text: Written for the External Tech Lead Evaluator reader.
related:
- guides/how-to/missions/accept-and-merge
- guides/how-to/missions/merge-mission
- guides/how-to/collaboration/run-external-orchestrator
- guides/how-to/recovery/troubleshoot-merge
---
# Run an Autonomous Mission

Use this guide when an agent or external orchestrator runs a Spec Kitty mission
end to end from a local checkout.

## Prerequisites

- `spec-kitty` is installed and authenticated for any services your run uses
- The repository checkout is clean before starting
- The intended target branch is known, usually `main`
- Agent CLIs or orchestrator providers are installed

## 1. Create the Mission

Start from the intake prompt:

```text
/spec-kitty.specify @start-here.md
```

Confirm the generated mission slug and target branch before continuing.

## 2. Plan the Mission

```text
/spec-kitty.plan @start-here.md
```

Review the plan for scope, branch intent, and known risks. Keep unrelated CLI or
documentation improvements out of the mission unless they are part of the spec.

## 3. Generate and Finalize Tasks

```text
/spec-kitty.tasks @start-here.md
```

If you are operating from a terminal, finalize tasks explicitly:

```bash
spec-kitty agent mission finalize-tasks --mission <mission-slug>
```

Check `lanes.json` and WP prompt frontmatter before implementation starts.

## 4. Run Implementation and Review

Use the normal implement-review loop:

```text
/spec-kitty-implement-review
```

Or drive each WP through the CLI:

```bash
spec-kitty agent action implement WP01 --mission <mission-slug> --agent <agent>
cd <workspace path printed by the command>
# implement, test, commit
spec-kitty agent tasks move-task WP01 --to for_review --mission <mission-slug> --note "Ready for review"
spec-kitty agent action review WP01 --mission <mission-slug> --agent <reviewer>
```

Continue until every WP is approved.

## 5. Accept the Mission

```text
/spec-kitty.accept
```

Or:

```bash
spec-kitty accept --mission <mission-slug>
```

Acceptance verifies mission readiness. It does not replace merge pre-flight
validation.

## 6. Preview the Merge

Before mutating the target branch, run:

```bash
spec-kitty merge --mission <mission-slug> --dry-run
```

Fix dirty worktrees, missing worktrees, and unresolved WP states before trying a
real merge.

## 7. Handle `TARGET_BRANCH_NOT_SYNCHRONIZED`

Autonomous local runs can accumulate many local commits on `main`, including
planning artifacts, status events, review notes, and orchestration commits.
When that happens, `spec-kitty merge` may stop before mutating merge state:

```text
Error: Target branch is not synchronized with its tracking branch.
  diagnostic_code: TARGET_BRANCH_NOT_SYNCHRONIZED
  branch_or_work_package: main
  violated_invariant: local_target_branch_must_match_tracking_branch
```

Do not reset, rebase, force-push, or push local `main` just to clear this
pre-flight. Those operations can discard or publish unrelated local history.

First inspect the divergence:

```bash
git fetch origin main
git log --oneline --left-right --cherry-pick main...origin/main
git diff --name-only origin/main...main
```

If every local commit is intentionally ready for `main`, a maintainer can decide
to publish it. Otherwise, use a focused PR.

### Direct Mission-Branch PR

Use this path when `kitty/mission-<mission-slug>` already contains the approved
mission result:

```bash
git push -u origin kitty/mission-<mission-slug>
gh pr create --base main --head kitty/mission-<mission-slug> --fill
```

This was the successful path for the autonomous run behind PR #1251: the PR
surface was the mission result, not the local orchestration history on `main`.

### Dedicated Focused PR Branch

Use this path when you want the PR branch name to be separate from the mission
branch:

```bash
git switch -c kitty/pr/<mission-slug>-to-main kitty/mission-<mission-slug>
git push -u origin kitty/pr/<mission-slug>-to-main
gh pr create --base main --head kitty/pr/<mission-slug>-to-main --fill
```

Prefer squash-merge for autonomous runs with large orchestration commit piles:

```bash
gh pr merge --auto   # queues it; the merge queue rebase-merges once the required checks pass
```

## 8. Run Mission Review

After the PR lands, update your local checkout and run:

```bash
git fetch origin main
git switch main
git pull --ff-only origin main
spec-kitty agent mission review --mission <mission-slug>
```

Mission review verifies requirement coverage and drift after landing.

## 9. Run the Retrospective Loop

Verify the retrospective record and inspect synthesis proposals:

```bash
spec-kitty retrospect create --mission <mission-slug>
spec-kitty retrospect summary
spec-kitty agent retrospect synthesize --mission <mission-slug>
```

Apply an individual proposal only after review:

```bash
spec-kitty agent retrospect synthesize --mission <mission-slug> --apply <proposal-id>
```

## See Also

- [Accept and Merge](../missions/accept-and-merge.md)
- [Merge a Mission](../missions/merge-mission.md)
- [Troubleshoot Merge Issues](../recovery/troubleshoot-merge.md)
- [Run the External Orchestrator](run-external-orchestrator.md)
