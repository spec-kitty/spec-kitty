---
title: How to Accept and Consolidate a Mission
description: "How to accept and consolidate a mission with Spec Kitty 3.2: Use this guide to validate mission readiness and consolidate into the mission's target branch."
doc_status: active
updated: '2026-07-04'
audience: docs/context/audience/external/project-owner.md
type: how-to
related:
- docs/guides/how-to/installation/install-and-upgrade.md
- docs/guides/how-to/missions/keep-main-clean.md
- docs/guides/how-to/missions/merge-mission.md
- docs/guides/how-to/missions/review-work-package.md
- docs/guides/how-to/collaboration/run-an-autonomous-mission.md
- docs/guides/how-to/recovery/troubleshoot-merge.md
- docs/guides/how-to/governance/use-retrospective-learning.md
---
# How to Accept and Consolidate a Mission

Use this guide to validate mission readiness and consolidate into the mission's target branch.

## Prerequisites

- All WPs are `approved` or `done`, with review feedback resolved
- You are in a checkout where the mission can be resolved (repository root checkout or execution workspace)

## Accept the Mission

Run acceptance after the implement-review loop approves every WP and before
consolidation. This is a readiness nudge for humans and LLMs; consolidation still performs its
own gates and remains the mission-close operation.

In your agent:

```text
/spec-kitty.accept
```

Or in your terminal:

```bash
spec-kitty accept
```

### What Accept Checks

- All WPs are `approved` or `done`
- Required metadata and activity logs are present
- No unresolved `[NEEDS CLARIFICATION]` markers remain

To run a read-only checklist (in your terminal):

```bash
spec-kitty accept --mode checklist
```

### Negative Invariants That Assert the Consolidated Post-State

The accept gate **re-runs each acceptance negative-invariant `verification_command`
live** against the working tree at accept time — it does not trust a stored
`result` or a hand-set `overall_verdict`. Two consequences follow:

- **Hand-editing a verdict does not stick.** Setting `overall_verdict` (or a
  negative invariant's `result`) by hand in `acceptance-matrix.json` is
  overwritten the moment accept runs; the invariant's `verification_command` is
  the single source of truth, and it must actually pass in the checkout accept
  runs from.
- **Consolidated-post-state invariants must be verified after consolidation.** If an invariant
  asserts a state that only exists **once the mission is consolidated** — for example,
  "`shell: bash` is present in `ci-quality.yml`" when that line is added by the
  consolidation — it cannot pass while the mission still lives on its lane branch. For
  such missions, run `spec-kitty consolidate` (into **local** `main`) **before**
  `spec-kitty accept`, so the working tree accept inspects already carries the
  consolidated post-state:

  ```bash
  spec-kitty consolidate    # land into LOCAL main first
  spec-kitty accept         # now the post-state invariants can verify live
  ```

  This inverts the usual accept-then-consolidate order and is only needed for missions
  whose negative invariants assert the post-consolidation result. Missions whose
  invariants describe the lane's own diff verify fine in the normal order.

  If you prefer not to re-order, scope the invariant to a path that exists on the
  lane branch (see `NegativeInvariant.scope`) or express it as a `custom_command`
  that is meaningful pre-consolidation.

### Deferred Invariants and the Post-Consolidation Gate

A scoped `grep_absence` invariant whose subject does not exist yet — because it
is added only by consolidating the mission's lane branches — cannot be honestly
judged at `accept` time. Rather than report a false "still present" or a false
"pass", accept records that invariant's result as `deferred_to_consolidation`
and the mission's `overall_verdict` as `pass_pending_consolidation`: acceptance
is **not blocked**, but the mission cannot reach `done` while the deferral is
outstanding.

**What this means for you as the operator:**

- **The mission loop does not verify a deferred invariant.** `spec-kitty accept`
  is the acceptance matrix's only pre-consolidation reader, and it is the gate
  that *creates* the deferral — it cannot also be the thing that resolves it.
  When `spec-kitty accept` assigns `deferred_to_consolidation` it discloses this
  immediately, in the same run, as a `negative_invariants_deferred` entry under
  "Skipped checks" — look for it in the console output or the JSON summary.
- **What verifies it instead** is the **post-consolidation verification op** —
  dispatched after `spec-kitty consolidate` (lane consolidation) completes, against
  the consolidated mission tree. It re-judges every `deferred_to_consolidation`
  invariant on that tree and records a terminal result
  (`confirmed_absent` / `still_present` / `verification_error`) stamped with the
  `CONSOLIDATED` surface. A violation fails **that verification op**, not the
  already-completed consolidation — see
  [post-consolidation / `CONSOLIDATED`](../../../context/orchestration.md#topology-surface)
  in the terminology glossary for how this surface relates to `spec-kitty
  consolidate`'s three overloaded "merge" senses.
- **What your repository needs**: a CI check on the pull request that fails when
  any `kitty-specs/*/acceptance-matrix.json` still carries an unresolved
  `deferred_to_consolidation` invariant. This project's own gate is
  `scripts/ci/check_dangling_deferrals.py`, wired into `ci-quality.yml`'s
  `deferral-consistency-check` job. **A repository without an equivalent check
  never verifies the deferral** — the disclosure above exists precisely so that
  gap is visible rather than silently assumed away (ADR
  [2026-07-23-2](../../../adr/3.x/2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md)).

## Consolidate into the target branch

In your agent:

```text
/spec-kitty.merge --push
```

Or in your terminal:

```bash
spec-kitty consolidate --push
```

By default, `spec-kitty consolidate` lands in the mission's recorded target branch. Use `spec-kitty consolidate --target <branch>` only when you intentionally need to override that destination.

For detailed consolidation options including dry-run, strategies, and cleanup flags, see [Merge a Mission](merge-mission.md).

### When Local `main` Is Not Publishable

Autonomous local runs can leave `main` ahead of or diverged from `origin/main`
with planning, status, review, and orchestration commits. If consolidation refuses with
`TARGET_BRANCH_NOT_SYNCHRONIZED`, do not reset, rebase, force-push, or push
local `main` only to satisfy the pre-flight.

Open a focused PR from the mission result instead:

```bash
git push -u origin kitty/mission-<mission-slug>
gh pr create --base main --head kitty/mission-<mission-slug> --fill
```

Or create a dedicated PR branch from the mission branch:

```bash
git switch -c kitty/pr/<mission-slug>-to-main kitty/mission-<mission-slug>
git push -u origin kitty/pr/<mission-slug>-to-main
gh pr create --base main --head kitty/pr/<mission-slug>-to-main --fill
```

Prefer squash-merge when the autonomous run accumulated many orchestration
commits. For the full end-to-end path, see
[Run an Autonomous Mission](../collaboration/run-an-autonomous-mission.md).

## After Consolidation

Complete the following three steps before declaring the mission done.

**1. Mission review** — run the post-consolidation mission review to confirm spec→code fidelity and FR
coverage:

```bash
# In your agent:
/spec-kitty-mission-review

# Or directly:
spec-kitty agent mission review --mission <handle>
```

**2. Author or verify the retrospective** — under default policy the record was already written
during consolidation. Verify with:

```bash
cat .kittify/missions/$(jq -r .mission_id kitty-specs/<slug>/meta.json)/retrospective.yaml
```

If the file is absent (for example, an older mission predating 3.2.0), author it now:

```bash
spec-kitty retrospect create --mission <handle>
```

Reserve the noun "capture" for the event-log fact `RetrospectiveCaptured`, not for the
operator verb.

**3. Surface findings** — aggregate across recent missions or inspect proposals for this one:

```bash
# Cross-mission view (read-only aggregation)
spec-kitty retrospect summary

# Preview proposals in this mission's retrospective.yaml (dry-run by default)
spec-kitty agent retrospect synthesize --mission <handle>

# Apply a proposal (requires explicit --apply)
spec-kitty agent retrospect synthesize --mission <handle> --apply <proposal-id>
```

For full details on each command, see
[How to Use Retrospective Learning](../governance/use-retrospective-learning.md).

## Consolidation Strategies

- **Default (merge commit)**: `spec-kitty consolidate`
- **Squash**: `spec-kitty consolidate --strategy squash`

Note: Rebase is not supported for multi-workspace missions. Use `merge` or `squash` instead.

## Cleanup

By default, consolidation removes resolved execution worktrees and deletes the mission branch. Use these flags to keep them (in your terminal):

```bash
spec-kitty consolidate --keep-worktree --keep-branch
```

## Abandon a Mission (Manual Cleanup)

If you decide to drop a mission without consolidating, remove its execution worktrees and branches manually.
These steps are safe and reversible until you delete the branch and commit the cleanup.

1. List worktrees to find all workspaces for the mission:
```bash
git worktree list
```

2. Remove each execution worktree for the mission:
```bash
git worktree remove .worktrees/<mission-slug>-lane-a
git worktree remove .worktrees/<mission-slug>-lane-b
```

If a worktree has uncommitted changes you want to discard, use `--force`:
```bash
git worktree remove --force .worktrees/<mission-slug>-lane-a
```

3. Delete the mission branches:
```bash
git branch -D <mission-slug>-lane-a
git branch -D <mission-slug>-lane-b
```

4. Remove the planning artifacts from the repository root checkout (spec/plan/tasks), then commit:
```bash
rm -rf kitty-specs/<mission-slug>
git add kitty-specs/
git commit -m "Remove abandoned mission <mission-slug>"
```

## Troubleshooting

- **Accept reports blockers**: Resolve the listed issues, then rerun `/spec-kitty.accept`.
- **Consolidation fails**: Ensure your current checkout is clean and the mission resolves correctly.
- **Consolidation reports `TARGET_BRANCH_NOT_SYNCHRONIZED`**: Use the focused-PR path when local `main` contains autonomous-run history that should not be published directly.
- **Consolidation is heading to the wrong branch**: Inspect the mission's recorded target branch before retrying, and use `spec-kitty consolidate --target <branch>` only if you intend to override it.

For detailed troubleshooting including pre-flight failures, conflict resolution, and consolidation recovery, see [Troubleshoot Merge Issues](../recovery/troubleshoot-merge.md).

---

## Command Reference

- [Slash Commands](../../../api/slash-commands.md) - All `/spec-kitty.*` commands
- [CLI Commands](../../../api/cli-commands.md) - Full CLI reference

## See Also

- [Merge a Mission](merge-mission.md) - Detailed merge workflow
- [Run an Autonomous Mission](../collaboration/run-an-autonomous-mission.md) - End-to-end autonomous run and focused-PR fallback
- [Keep Main Clean](keep-main-clean.md) - Choose a target branch without changing planning location
- [Troubleshoot Merge Issues](../recovery/troubleshoot-merge.md) - Recovery and conflict resolution
- [Review a work package](review-work-package.md) - Required before accept
- [Upgrade to 0.11.0](../installation/install-and-upgrade.md) - Breaking changes in v0.11.0

## Background

- [Execution Lanes](../../../architecture/execution-lanes.md) - Worktree cleanup
- [Git Worktrees](../../../architecture/git-worktrees.md) - How worktrees work

## Getting Started

- [Your First Mission](../../tutorials/your-first-mission.md) - Complete workflow walkthrough
