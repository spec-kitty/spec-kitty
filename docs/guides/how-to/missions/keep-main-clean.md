---
title: How to Keep Main Clean
description: 'How to keep main clean with Spec Kitty 3.2: Use this guide when you want planning to happen from the repository root checkout but you do not want the.'
doc_status: active
updated: '2026-06-03T00:00:00Z'
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/missions/create-plan.md
- docs/guides/how-to/missions/create-specification.md
- docs/guides/how-to/missions/generate-tasks.md
- docs/guides/how-to/missions/merge-mission.md
kind: How-To
---
# How to Keep Main Clean

Use this guide when you want planning to happen from the repository root checkout but you do not want the mission to target `main`.

## Know the Three Moving Parts

- `repository root checkout`: where `/spec-kitty.specify`, `/spec-kitty.plan`, and `/spec-kitty.tasks` run
- `target branch`: the branch the mission records planning artifacts and merge intent against
- worktrees: the per-work-package execution checkouts used during implementation

Planning location and target branch are separate choices. Running from the repository root checkout does not force `main`.

## Start on an Existing Branch and Keep It as the Target

If you are already on the branch that should receive the feature, verify the branch contract first:

```bash
spec-kitty agent mission branch-context --json
```

If the JSON shows the current branch, `planning_base_branch`, and `merge_target_branch` all pointing at the branch you want, run `/spec-kitty.specify` normally from the repository root checkout.

This is the simplest way to keep `main` clean: start from `main`, your release branch, or your mission integration branch before planning begins.

## Pick an Explicit target branch

If you want to plan from the repository root checkout but land somewhere other than the current branch, name it explicitly:

```bash
spec-kitty agent mission branch-context --json --target-branch develop
spec-kitty agent mission create "new-dashboard" --target-branch develop --json
```

The packaged `/spec-kitty.specify` prompt now tells the agent to restate:

- the current branch
- `planning_base_branch`
- `merge_target_branch`
- whether the current checkout matches the intended target

If those values do not match the branch you want, the agent should stop and confirm before it creates artifacts.

## Use `main` Only When You Mean `main`

If the feature should actually land on `main`, either:

- start from `main` and let the default current-branch behavior apply, or
- pass `--target-branch main` explicitly

Do not treat `main` as a synonym for "the repository root checkout."

## Plan in the repository root checkout, Implement in Worktrees

The normal flow is:

1. Run `/spec-kitty.specify`, `/spec-kitty.plan`, and `/spec-kitty.tasks` from the repository root checkout.
2. Let those commands create and commit planning artifacts on the mission's target branch.
3. Start implementation with `spec-kitty next --agent <agent> --mission <handle>`.
4. Let Spec Kitty allocate or reuse per-lane worktrees for the work packages.

If you need to inspect the recorded branch contract later, use:

```bash
spec-kitty agent mission branch-context --json --target-branch <branch>
```

## Override the Merge Target Only Intentionally

By default, `spec-kitty merge` lands in the mission's recorded target branch.

Use this only when you intentionally need a different destination:

```bash
spec-kitty merge --target main
```

If you are reaching for `--target`, confirm first that the mission was not simply created against the wrong target branch.

## Troubleshooting

### I’m in the repository root checkout but I do not want `main`

Stay in the repository root checkout. Change the branch intent, not the location:

- check out the branch you actually want before `/spec-kitty.specify`, or
- pass `--target-branch <branch>` when resolving branch context or creating the mission

### Why am I being told to switch branches?

Because the current checkout branch and the intended target branch do not match.

The planning prompts now use `branch-context --json` and should restate that mismatch. If the restated `planning_base_branch` is wrong, stop and pick the right target before creating more artifacts.

### How do I plan on one branch and implement in worktrees?

Keep planning in the repository root checkout on the mission's target branch. After `/spec-kitty.tasks`, use `spec-kitty next` or `spec-kitty agent action implement ...` and let the CLI create worktrees for the execution lanes.

The worktrees are for implementation only. They do not replace the repository root checkout as the planning location.

## See Also

- [Create a Specification](create-specification.md)
- [Create a Plan](create-plan.md)
- [Generate Tasks](generate-tasks.md)
- [Merge a Feature](merge-mission.md)
