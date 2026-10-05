---
title: Branch-Target Routing
description: Explanation of which git branch a mission's code, coordination surface, and base-level artifacts land on.
doc_status: active
updated: '2026-10-05'
audience: docs/context/audience/internal/system-architect.md
type: explanation
related:
- docs/architecture/artifact-placement-seam.md
- docs/architecture/execution-lanes.md
- docs/architecture/git-worktrees.md
---
# Branch-Target Routing

When spec-kitty runs a mission with execution lanes, different categories of change land on
different **branches**. This page explains the branch-level destinations — lane branch,
coordination branch, target/base branch — and the **simple case**: what happens when there are
no lanes or coordination branches at all.

**This page is about branches, not artifact kinds.** Which `MissionArtifactKind` (spec, status
event, work-package task, …) resolves to which physical *tree* is a separate, more granular
question, answered by [The Artifact Placement Seam](artifact-placement-seam.md). That page also
holds the normative citations (ADR `2026-06-24-1`, ADR `2026-07-23-1`) for the placement rule
itself — this page does not restate them.

## Why branch-target routing exists

Before execution lanes, every change from every work package landed on the same branch. That
worked fine for sequential missions, but breaks down when two work packages run in parallel:
their changes would collide, producing merge conflicts on files neither WP was supposed to
touch.

The model solves this by giving each category of change a **dedicated landing branch**:

- Work-package code stays in an isolated **lane branch** so two lanes never touch each other's
  files.
- Mission-wide bookkeeping (status events and the other coordination-owned artifacts) lands on
  a shared **coordination branch** so every lane can read it without checking out a different
  branch.
- Everything else — planning artifacts, documentation, the final merge target — resolves to the
  mission's **target branch** (its base, e.g. `feat/my-mission` or `main`), so it is accessible
  from any context without a coordination round-trip.

The destination is decided automatically; you do not choose a landing branch manually.

## The three branch-level destinations

**Lane branch** — the branch checked out inside a lane's worktree. Only the work packages
assigned to that lane write code here. Lane branches are isolated from each other.

**Coordination branch** — the shared visibility surface for a mission's coordination-owned
bookkeeping (status events, acceptance/issue/analysis records, and the other kinds
[The Artifact Placement Seam](artifact-placement-seam.md#the-layer-table) classifies to that
partition). All lanes read from it, keeping mission-wide bookkeeping out of the lane branches.

**target branch** (the mission's base, e.g. `feat/my-mission` or `main`) — where planning
artifacts, shared documentation, and the eventual merge target resolve. Every lane can reach it
without a coordination round-trip.

*Which artifact kind is classified into which of these — and by what authority — is the
question [The Artifact Placement Seam](artifact-placement-seam.md) answers; this page names
only the three branch-level destinations themselves.*

## Upgrade and project-global state

`spec-kitty upgrade` writes project-global state (`.kittify/metadata.yaml`, `.gitattributes`)
on the branch checked out in the repository root checkout, and in linked worktrees on
ordinary branches. It skips every
[integrating worktree](../context/execution.md#integrating-worktree): a worktree on a
`kitty/mission-…` mission, lane or coordination branch, or on a branch that cannot be read.
So an upgrade run from the repository root checkout adds no upgrade commit to a lane, mission
or coordination branch; a lane keeps its pre-upgrade copy until it is consolidated. Where a pre-fix upgrade already left
divergent copies, the integration sites resolve the generated `.kittify/metadata.yaml` to a
fixed side. See [ADR 2026-10-04-4](../adr/4.x/2026-10-04-4-upgrade-writes-project-global-state-once.md)
and the [recovery runbook](../operations/upgrade-with-live-lanes-recovery.md).

## The simple case: flat topology (no lanes, no coordination)

When a mission has only one work package and no coordination branch is configured, every
category above resolves to the **target branch**. There are no lane worktrees and no
coordination surface — spec-kitty runs exactly as it did before lanes were introduced.

This is the **all-base collapse**: code, coordination bookkeeping, planning artifacts, and
documentation all resolve to the same branch. The result is byte-identical to the
single-branch workflow from earlier versions of spec-kitty. No worktree directories are created
or read; no coordination branch is touched.

The flat topology is not a special mode you activate — it is simply what happens when a mission
has no coordination branch or lane worktrees declared. If you are running a straightforward,
single-threaded mission, you are already in the simple case.

## Relationship to execution lanes

This page describes *which branch* changes land on. The execution lanes model describes *how*
work packages are grouped and run in parallel. These two concerns are complementary:

- Execution lanes allocate work packages to lane branches.
- Branch-target routing ensures the coordination surface and target branch remain accessible to
  all lanes simultaneously.

See [Execution Lanes](execution-lanes.md) for how lanes are computed, how worktrees are
created, and how lane branches merge back to the mission branch.

See [Git Worktrees Explained](git-worktrees.md) for the underlying git mechanism that makes
isolated lane workspaces possible.

See [The Artifact Placement Seam](artifact-placement-seam.md) for how an individual artifact
*kind* is classified to a physical tree — the layer model, the two composition roots, and the
compliance taxonomy for call sites that bypass the seam.
