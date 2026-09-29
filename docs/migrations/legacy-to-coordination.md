---
title: 'Migration: Legacy Topology to the Coordination Model'
description: 'Operator runbook for the legacy-topology bookkeeping warning: what a pre-coordination mission is, how to detect one, and the supported paths forward.'
doc_status: active
updated: '2026-09-26'
related:
- docs/architecture/branch-target-routing.md
- docs/architecture/execution-lanes.md
- docs/adr/3.x/2026-06-22-1-mission-topology-ssot.md
- docs/migrations/mission-id-canonical-identity.md
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Migration: Legacy Topology to the Coordination Model

**Source of the warning**: `src/specify_cli/coordination/transaction.py`
(the bookkeeping transaction).
**ADR**: [2026-06-22-1 — MissionTopology SSOT](../adr/3.x/2026-06-22-1-mission-topology-ssot.md)
**Audience**: Operators who saw the stderr warning below while running a
mission that predates the coordination-branch topology, or who need to
decide how to move such a mission forward.

## The warning you saw

```text
warning: mission '<slug>' uses the legacy topology (no coordination branch).
New atomicity invariants apply, but consider migrating: see
docs/migrations/legacy-to-coordination.md
```

It is emitted **at most once per mission**, on the first bookkeeping write
(status event or planning-artifact commit) for a mission whose `meta.json`
does not carry a `coordination_branch`. A marker file
`.kittify/legacy-warning-shown-<mission_id>` records that the warning was
shown, so subsequent commands stay quiet.

The warning is **informational, not an error**. Your mission keeps working.
Every atomicity invariant of the bookkeeping transaction — the pre-flight
policy gate, the lock, the surgical truncate rollback, and outbound deferral
— applies to legacy missions exactly as it does to coordination missions.
Only the write destination differs (see below).

## What a legacy mission is

Under the current [branch-target routing model](../architecture/branch-target-routing.md),
a mission's planning artifacts, status events, and lane definitions land on a
dedicated **coordination branch**, hosted in a per-mission coordination
worktree (`.worktrees/<slug>-<mid8>-coord/`). The branch name is recorded in
the mission's `meta.json` under `coordination_branch` at `mission create`
time, when the chosen topology calls for one.

A **legacy mission** is one whose `meta.json` exists but carries no
`coordination_branch` — typically because the mission was created before the
coordination-branch topology landed. For those missions the bookkeeping
write target is the operator's **current lane worktree and its checked-out
branch**, resolved from your working directory. This is the pre-coordination
behavior, preserved on purpose.

Two neighbouring states are *not* legacy, and — since #2351 — do **not** draw
the legacy-topology warning:

- **A coordination-less topology chosen at creation.** A mission created on a
  current version with the `single_branch` or `lanes` topology also has no
  `coordination_branch` — those shapes never mint one. Write-path routing
  still treats them identically to a legacy mission (the key is absent either
  way; `lanes` writes through the operator's lane worktree, while `single_branch`
  writes in its write checkout and has no lane worktree), but the warning
  classifier is topology-aware: it reads the mission's **stored** topology
  and no longer warns when that topology is a coordination-less shape chosen
  on purpose.
- **A flattened mission.** A mission that *had* a coordination branch and had
  it deliberately removed is **flattened**, recorded as a separate
  `flattened` provenance flag in `meta.json` — never as a topology value.
  Flattened missions do not draw the legacy-topology warning either.
  See the [MissionTopology SSOT ADR](../adr/3.x/2026-06-22-1-mission-topology-ssot.md).

## Detect the state

1. **Check `meta.json` directly.** From the repository root:

   ```bash
   jq '.coordination_branch' kitty-specs/<mission-dir>/meta.json
   ```

   `null` (or a missing key) means the bookkeeping transaction treats the
   mission as legacy. A missing `meta.json` altogether is treated as
   new-topology, not legacy — as is a corrupt (unparseable) one, which
   additionally surfaces as an error via `backfill-topology` (exit 1, see
   [troubleshooting](#spec-kitty-migrate-backfill-topology-exits-1)).

2. **Audit the stored topology.** The read-only audit walks `kitty-specs/`
   and reports each mission's stored shape and `flattened` flag:

   ```bash
   spec-kitty doctor topology --json
   spec-kitty doctor topology --mission <slug>
   ```

   A `topology` of `null` means the mission predates the stored-topology
   model and has not been backfilled yet (see Path A below). The four valid
   stored values are `single_branch`, `lanes`, `coord`, and
   `lanes_with_coord`; `coord` and `lanes_with_coord` are the shapes that
   carry a coordination branch.

3. **Check the worktree layout.** Coordination missions have a
   `.worktrees/<slug>-<mid8>-coord/` worktree alongside any lane worktrees.
   Legacy missions have only lane worktrees, laid out as
   `.worktrees/<slug>-lane-<id>/` (or `.worktrees/<slug>-<mid8>-lane-<id>/`
   when the recorded slug itself embeds a mid8 — lane naming keys on the
   slug and lane id, never on the Mission identity; see [Execution Lanes
   §Naming](../architecture/execution-lanes.md#naming)), or the pre-083
   forms described in the [mission identity runbook](mission-id-canonical-identity.md).

## Path A — Stay on the legacy topology and backfill the stored shape

Running a legacy mission to completion is fully supported. The one piece of
maintenance worth doing is persisting the mission's shape, so that readers
consult a **stored** topology instead of re-inferring it from disk (the
drift class the SSOT ADR closes):

```bash
spec-kitty migrate backfill-topology --dry-run --json   # preview
spec-kitty migrate backfill-topology                    # write
spec-kitty doctor topology --json                       # confirm
```

`backfill-topology` computes each mission's topology from its current
on-disk signals and writes it into `meta.json` as the authoritative
`topology` value. It is idempotent — a mission that already has a valid
`topology` is skipped and never overwritten. `--mission <slug>` scopes it to
one mission. Exit code `1` means one or more missions had a corrupt or
unreadable `meta.json`; repair the JSON and re-run.

Note the backfill stores the *shape*; it never mints a coordination branch.
A legacy mission stays on the legacy write path after backfill — routing is
unaffected. The warning behavior, however, changes deliberately (#2351):
backfilling a genuinely legacy mission's stored topology **suppresses** the
legacy-topology warning on the next invocation, since the classifier now
sees an affirmative stored shape instead of "absent."

## Path B — Adopt the coordination model

Coordination branches are minted **only at `mission create`**, when the
chosen topology calls for one. There is no in-place converter that retrofits
a coordination branch onto an existing mission — an in-flight legacy mission
should simply run to merge under the legacy invariants.

Missions created on current versions with a coordination topology carry
`coordination_branch` in `meta.json` from creation, and their bookkeeping
routes through the coordination worktree automatically. In other words: the
migration to the coordination model happens per new mission, not by
converting old ones.

**Do not hand-edit `coordination_branch` into `meta.json`.** The transaction
would treat the value as authoritative and re-create the coordination surface
fresh on the next write — a surface that never hosted the mission's existing
planning and status history. The mission's status log would then be split
across two surfaces.

## Troubleshooting

### `BOOKKEEPING_LEGACY_RESOLUTION_FAILED`

The mission is legacy but the CLI could not resolve a legitimate write
target from your working directory. The stable error code covers three
causes, each with the same remedy — run the command from inside the
mission's lane worktree with the lane branch checked out:

- *"no git worktree found above `<cwd>`"* — you are outside any checkout.
- *"HEAD is detached or symbolic-ref failed"* — the worktree you are in has
  a detached HEAD; check out the lane branch.
- *"HEAD resolves to an empty branch name"* — same remedy.

### The write is refused from the primary checkout

Running legacy bookkeeping from the main checkout while it sits on a
protected ref (for example `main`) is blocked by the pre-flight policy gate
in the transaction — the same machinery that guards the coordination
topology. Move to the mission's lane worktree.

### The warning keeps repeating

The once-only behavior depends on writing the marker file
`.kittify/legacy-warning-shown-<mission_id>`. If that write fails (for
example, a read-only `.kittify/`), the failure is non-fatal and the warning
simply re-appears on the next invocation. Fix the permissions to restore the
once-only behavior. Conversely, delete the marker file to see the warning
again on purpose.

### `spec-kitty migrate backfill-topology` exits 1

One or more missions had a corrupt or unreadable `meta.json`. The command
reports which; repair the JSON by hand and re-run — the backfill is safe to
re-run and skips missions that are already done.

## Related Documentation

- [Branch-Target Routing](../architecture/branch-target-routing.md) — the
  routing table, the coordination branch's role, and the flat-topology
  collapse when no coordination branch is configured.
- [Execution Lanes](../architecture/execution-lanes.md) — lane worktree and
  branch naming, and how lanes merge back.
- [MissionTopology SSOT ADR](../adr/3.x/2026-06-22-1-mission-topology-ssot.md)
  — why the shape is stored in `meta.json` and resolved once, and why
  `flattened` is a provenance flag rather than a topology.
- [Mission ID canonical identity](mission-id-canonical-identity.md) — the
  sibling migration for pre-083 missions without a `mission_id`; the same
  audit-then-backfill pattern this page follows.
