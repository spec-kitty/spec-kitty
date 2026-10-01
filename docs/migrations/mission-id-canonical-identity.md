---
title: 'Migration: Mission ID as Canonical Identity'
description: "Migration to mission_id (ULID) as a mission's canonical identity, shipped with mission 083: the new identity model, the backfill, and the ADR behind it."
doc_status: active
updated: '2026-09-26'
related:
- docs/migrations/feature-flag-deprecation.md
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Migration: Mission ID as Canonical Identity

**Status**: Shipped with mission `083-mission-id-canonical-identity-migration`.
**ADR**: [2026-04-09-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-04-09-1-mission-identity-uses-ulid-not-sequential-prefix.md)
**Issue**: [Priivacy-ai/spec-kitty#557](https://github.com/Priivacy-ai/spec-kitty/issues/557)
**Audience**: Operators upgrading existing Spec Kitty projects to the 3.x line
that ships the `mission_id` identity model.

## Why This Matters

Before mission 083, Spec Kitty used the three-digit numeric prefix
(`mission_number`) that shows up in directory names like
`kitty-specs/001-auth-system/` as the canonical identity for every mission.
This caused four distinct failure modes in real projects:

1. **Collision on import.** Two repositories each had a `001-auth-system`
   directory. Merging them or running a cross-repo dashboard scanner produced
   silently-merged state, because both missions looked identical to the
   selector.
2. **Silent fallback on ambiguous handles.** A user ran
   `spec-kitty agent tasks status --mission 020` in a project that had both
   `020-feature-a` and `020-feature-b` (from a botched rebase). The CLI picked
   one arbitrarily — and usually the wrong one.
3. **Branch and worktree name collisions.** Two missions with the same
   human-chosen slug would fight over the same `.worktrees/<slug>-lane-a`
   directory and the same `kitty/mission-<slug>-lane-a` branch.
4. **Early numbering pressure.** `mission_number` had to be assigned the
   moment a mission was created, which meant the number had to be globally
   unique at creation time, which forced a cross-checkout lock that did not
   actually exist.

Mission 083 fixes all four by making `mission_id` (a ULID) the canonical
machine identity, minted at creation and immutable. `mission_number` becomes
**display-only metadata**, `null` until merge time, and assigned as
`max(existing_numbers)+1` inside the merge-state lock — the only place where a
global invariant can actually be enforced.

> **Breaking (3.2.5+): this backfill is now mandatory for coordination.**
> As of 3.2.5, a pre-3.2.x mission with no resolvable `mission_id`/`mid8`
> **hard-fails** on coordination operations (status transitions, `move-task`,
> review/merge coordination writes) instead of silently degrading — the
> coordination-workspace seam refuses to compose a malformed
> `kitty/mission-<slug>-` ref (#2091). If you see
> `COORDINATION_WORKSPACE_MID8_REQUIRED`, run the backfill below
> (`spec-kitty migrate backfill-identity`) to modernize the mission; audit
> first with `spec-kitty doctor identity`. The dual-era legacy-bridge fallback
> is intentionally removed (#2462).

## What Changed

| Field | Before (2.x) | After (083+) |
|-------|--------------|--------------|
| Canonical machine identity | `mission_number` (3-digit string) | `mission_id` (26-char ULID) |
| Selector routing | `mission_number` / `mission_slug` prefix match | `mission_id`, `mid8`, or `mission_slug`, disambiguated by `mission_id` |
| Mission branch naming | `kitty/mission-<slug>` | `kitty/mission-<slug>-<mid8>` |
| Lane branch naming† | `kitty/mission-<slug>-lane-<id>` | `kitty/mission-<slug>-lane-<id>` (unchanged — see footnote) |
| Lane worktree naming† | `.worktrees/<slug>-lane-<id>` | `.worktrees/<slug>-lane-<id>` (unchanged — see footnote) |
| Ambiguous selector | Silent first-match fallback | Structured `MISSION_AMBIGUOUS_SELECTOR` error |
| When `mission_number` is assigned | At mission creation | At merge time, under the merge-state lock |

- `mid8` is the first 8 characters of the ULID. It is the short disambiguator
  used in the Mission branch and coordination identifiers.
- Pre-083 missions without a `mission_id` are called **legacy missions**. The
  doctor and backfill commands below mint a `mission_id` for them.
- † **Lane branch and worktree naming never derived from `mission_id`.**
  Mission 083 originally documented lane names as embedding `mid8` the same
  way the Mission branch does. That was never what lane *creation* produced
  — lanes were always named from the slug and lane id alone — and the gap
  between what six other read sites assumed and what creation actually did
  caused a merge defect (#5108). ADR
  [`2026-09-26-2`](../adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md)
  makes the created (slug-only) name the only name any caller can compose.
  `mid8` appears in a lane name only when the recorded Mission **slug**
  happens to embed it (see
  [Execution Lanes §Naming](../architecture/execution-lanes.md#naming)).

## Step 1 — Upgrade `spec-kitty-cli`

Install the pre-release that contains the 083 work:

```bash
pipx install --force --pip-args="--pre" spec-kitty-cli
spec-kitty --version
```

Expected: a version at or above the 083 release tag.

> **Note:** `spec-kitty-cli` is installed via `pipx`, not `pip`. See the
> project's `CLAUDE.md` for the rationale.

## Step 2 — Run the identity audit

From the root of each project you want to migrate:

```bash
spec-kitty doctor identity --json
```

The command walks `kitty-specs/` and classifies every mission:

- `ok` — mission already has a `mission_id`; nothing to do.
- `legacy` — mission has no `mission_id`; backfill required.
- `conflict` — two or more legacy missions share a `mission_slug` or
  `mission_number`; they need human disambiguation before backfill.

**Expected output** for a project with one legacy mission:

```json
{
  "status": "legacy_present",
  "total": 12,
  "ok": 11,
  "legacy": 1,
  "conflicts": 0,
  "missions": [
    {
      "dir": "kitty-specs/001-auth-system",
      "mission_slug": "auth-system",
      "mission_number": 1,
      "mission_id": null,
      "state": "legacy"
    }
  ]
}
```

If `conflicts > 0`, resolve them first: rename one of the colliding
directories, or delete a stale checkout. The backfill refuses to run while
conflicts are present, by design — we do not want the CLI to guess.

## Step 3 — Run the backfill

Once the audit is clean of conflicts:

```bash
spec-kitty migrate backfill-identity
```

This command:

1. Loads every legacy mission.
2. Mints a fresh `mission_id` (ULID) per mission.
3. Writes `mission_id` into `meta.json`. **No other field is touched** —
   `mission_number`, `mission_slug`, `created_at`, `target_branch`,
   `friendly_name`, `mission_type` are all preserved byte-for-byte.
4. Commits the change on the current branch with a deterministic message.

**Expected output:**

```text
Scanning kitty-specs/ ...
  001-auth-system     legacy -> minted 01J6XW9KQT7M0YB3N4R5CQZ2EX
  003-dashboard       legacy -> minted 01J6XW9VMJ5Z3QRXPFW5K2H1MA
Backfilled 2 missions. meta.json updated. Git commit: abc1234
```

**Backfill is additive-only.** Existing data is never overwritten. The
backfill is safe to re-run: missions that already have a `mission_id` are
skipped.

## Step 4 — Re-run the audit

Confirm the project is clean:

```bash
spec-kitty doctor identity --json
```

**Expected output:**

```json
{
  "status": "ok",
  "total": 12,
  "ok": 12,
  "legacy": 0,
  "conflicts": 0
}
```

If any mission is still `legacy`, rerun backfill against that mission
directly. If a `conflict` appears after backfill, open an issue — backfill
should never produce one.

## What Backfill Does Not Change

Backfill mints `mission_id` and writes it into `meta.json`; it does **not**
touch `lanes.json` or rename anything already created on disk:

- **Lane branches and worktrees keep their created names.** Backfilling a
  legacy mission's identity does not rename its lane branches or lane
  worktrees, because lane naming never took the identity as an input in the
  first place (see the footnote in **What Changed** above and ADR
  [`2026-09-26-2`](../adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md)).
  A lane created before backfill and a lane created after backfill compose
  the identical name, for the identical slug and lane id.
- **`lanes.json`'s recorded `mission_branch` is preserved across
  re-finalize (FR-011).** Only the *first* `finalize-tasks` for a mission
  defines its recorded Mission branch. Backfilling the identity and then
  re-running `finalize-tasks` leaves that recorded value byte-identical —
  it is never recomposed from the (now-different) identity. This is what
  keeps a backfilled mission's later `implement`/`merge` steps targeting the
  Mission branch that was actually created, instead of a phantom name that
  was never created.

## Step 5 — Understanding the new branch and worktree naming

This step applies only to a Mission's **first** `finalize-tasks` — the one
that defines `lanes.json`'s recorded Mission branch for the first time. Once
a mission has a `mission_id`, that first finalize (via the following
`spec-kitty implement` cycle) produces a **Mission branch** that embeds
`mid8`. A **re-finalize** on an already-finalized Mission is a different
case: it preserves the already-recorded Mission branch byte-identically (see
**What Backfill Does Not Change** above) rather than recomputing it. Lane
branches and lane worktrees are keyed on the slug and lane id only in either
case, never on `mission_id` directly.

**Case A — a legacy Mission backfilled after it was already finalized.**
Its lanes were created from the pre-backfill slug, so its lane names do not
change:

```text
Mission branch: kitty/mission-auth-system
Lane branch:    kitty/mission-auth-system-lane-a
Lane worktree:  .worktrees/auth-system-lane-a/
```

Backfilling this Mission's identity does not by itself change any of the
above — see **What Backfill Does Not Change**.

**Case B — a Mission created fresh on 083+.** Its recorded slug already
embeds the mid8 (minted at `mission create`, before the first `finalize`
ever runs), so the Mission branch **and** the lane names both contain it —
not because lane naming looked up the identity, but because it is already
part of the slug it composes from:

```text
Mission branch: kitty/mission-auth-system-01J6XW9K
Lane branch:    kitty/mission-auth-system-01J6XW9K-lane-a
Lane worktree:  .worktrees/auth-system-01J6XW9K-lane-a/
```

Where `01J6XW9K` is the first 8 characters of
`mission_id = 01J6XW9KQT7M0YB3N4R5CQZ2EX`. Compare Case A: there, the slug
never embedded a mid8, so the lane names never picked one up either — lane
naming only ever reflects whatever the recorded slug already contains, never
the identity directly (see ADR
[`2026-09-26-2`](../adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md)).

**What this means in practice:**

- You may see both legacy and new Mission branches side-by-side during the
  transition. That is expected.
- Existing worktrees for a mission do **not** rename automatically. Lane
  worktrees never need to — they were never keyed on the identity.

## Step 6 — What to do if a selector is ambiguous

The `--mission` flag on every command now accepts three forms:

1. **`mission_id`** — full 26-char ULID. Always unique. Always works.
2. **`mid8`** — first 8 chars of the ULID. Unique in practice; the resolver
   falls through to a structured error if two missions somehow share `mid8`.
3. **`mission_slug`** — human-readable slug. Preferred for interactive use;
   the resolver disambiguates by `mission_id` when two missions share a slug.

If the resolver cannot disambiguate, you get a `MISSION_AMBIGUOUS_SELECTOR`
error **without fallback**:

```text
Error: Handle 'auth-system' matches 2 missions:
  - mission_id=01J6XW9KQT7M0YB3N4R5CQZ2EX slug=auth-system number=1
  - mission_id=01J7YZ0DPN5A2B3C4D5E6F7G8H slug=auth-system number=14
Pass the full mission_id or mid8 to disambiguate, e.g. --mission 01J6XW9K.
```

Copy the `mid8` from the error and re-run the command. This is deliberate —
mission 083 removed silent fallback (work package WP07) because it was the
root cause of the collision class of bugs.

## Rollback Plan

`mission_id` is a **forward-only, additive** change. If something breaks
after the migration:

1. **The stored data is safe.** Backfill only adds `mission_id` to
   `meta.json`; it never removes or modifies existing fields. A project
   whose `meta.json` files have both `mission_id` and `mission_number` is in
   the normal state for 083+.
2. **Pin the CLI back.** `pipx install spec-kitty-cli==<pre-083-version>`
   returns you to the 2.x line. The old CLI will ignore the new
   `mission_id` field in `meta.json` and continue to route by
   `mission_number`. The new Mission branches created under 083 will
   remain on disk but will not be used by the old CLI; you can either
   `git worktree remove` them or leave them as archived state.
3. **Report the failure.** File an issue at
   [Priivacy-ai/spec-kitty#557](https://github.com/Priivacy-ai/spec-kitty/issues/557)
   or the tracking issue for the release with the output of
   `spec-kitty doctor identity --json` attached.

**Do not** hand-edit `meta.json` to remove `mission_id`. The file is watched
by the event log, and a missing `mission_id` will
cause it to classify the mission as legacy and prompt for another
backfill — at which point the mission will receive a **different** ULID, and
any event log entries keyed off the original ULID will become orphaned.

## Related Documentation

- [Mission Identity Model in `CLAUDE.md`](https://github.com/spec-kitty/spec-kitty/blob/main/CLAUDE.md#mission-identity-model-083) — developer-facing contract summary.
- [Event Envelope Reference](../api/event-envelope.md) — how `mission_id` flows into the machine contract.
- [Orchestrator API Reference](../api/orchestrator-api.md) — `--mission` selector semantics.
- [Execution Lanes](../architecture/execution-lanes.md) — lane branch and worktree naming.
- [Feature Detection architecture note](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/architecture/feature-detection.md) — historical context for the pre-083 selector.
- [Feature Flag Deprecation](feature-flag-deprecation.md) — the earlier `--feature` → `--mission` migration.
