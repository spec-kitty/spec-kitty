---
title: 'Migration: Mission ID as Canonical Identity'
description: "Migration to mission_id (ULID) as a mission's canonical identity, shipped with mission 083: the new identity model, the backfill, and the ADR behind it."
doc_status: active
updated: '2026-07-08'
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
| Branch naming | `kitty/mission-<slug>-lane-<id>` | `kitty/mission-<slug>-<mid8>-lane-<id>` |
| Worktree naming | `.worktrees/<slug>-lane-<id>` | `.worktrees/<slug>-<mid8>-lane-<id>` |
| Ambiguous selector | Silent first-match fallback | Structured `MISSION_AMBIGUOUS_SELECTOR` error |
| When `mission_number` is assigned | At mission creation | At merge time, under the merge-state lock |
| Dashboard scanner key | `mission_slug` | `mission_id` (distinct rows for duplicate prefixes) |

- `mid8` is the first 8 characters of the ULID. It is the short disambiguator
  used in filesystem and git identifiers.
- Pre-083 missions without a `mission_id` are called **legacy missions**. The
  doctor and backfill commands below mint a `mission_id` for them.

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

## Step 5 — Understanding the new branch and worktree naming

Once a mission has a `mission_id`, the next `spec-kitty implement` cycle will
produce new branches and worktrees that embed `mid8`.

**Legacy form (still resolvable for pre-083 state):**

```text
Branch:    kitty/mission-auth-system-lane-a
Worktree:  .worktrees/auth-system-lane-a/
```

**New form (083+):**

```text
Branch:    kitty/mission-auth-system-01J6XW9K-lane-a
Worktree:  .worktrees/auth-system-01J6XW9K-lane-a/
```

Where `01J6XW9K` is the first 8 characters of
`mission_id = 01J6XW9KQT7M0YB3N4R5CQZ2EX`.

**What this means in practice:**

- You may see both legacy and new branches side-by-side during the transition.
  That is expected.
- The dashboard scanner keys rows by `mission_id`, so two missions that share
  a numeric prefix now appear as distinct rows instead of overwriting each
  other.
- Existing worktrees for a mission do **not** rename automatically. They
  continue to work until the next `implement` cycle, at which point the new
  lane worktree is created in the new form. You can delete the old one with
  `git worktree remove` once you have moved any in-flight work.

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
   `mission_number`. The new branches and worktrees created under 083 will
   remain on disk but will not be used by the old CLI; you can either
   `git worktree remove` them or leave them as archived state.
3. **Report the failure.** File an issue at
   [Priivacy-ai/spec-kitty#557](https://github.com/Priivacy-ai/spec-kitty/issues/557)
   or the tracking issue for the release with the output of
   `spec-kitty doctor identity --json` attached.

**Do not** hand-edit `meta.json` to remove `mission_id`. The file is watched
by the event log and the dashboard scanner, and a missing `mission_id` will
cause them to classify the mission as legacy and prompt for another
backfill — at which point the mission will receive a **different** ULID, and
any event log entries keyed off the original ULID will become orphaned.

## Related Documentation

- [Mission Identity Model in `CLAUDE.md`](https://github.com/spec-kitty/spec-kitty/blob/main/CLAUDE.md#mission-identity-model-083) — developer-facing contract summary.
- [Event Envelope Reference](../api/event-envelope.md) — how `mission_id` flows into the machine contract.
- [Orchestrator API Reference](../api/orchestrator-api.md) — `--mission` selector semantics.
- [Execution Lanes](../architecture/execution-lanes.md) — lane branch and worktree naming.
- [Feature Detection architecture note](https://github.com/spec-kitty/spec-kitty/blob/main/docs/architecture/feature-detection.md) — historical context for the pre-083 selector.
- [Feature Flag Deprecation](feature-flag-deprecation.md) — the earlier `--feature` → `--mission` migration.
