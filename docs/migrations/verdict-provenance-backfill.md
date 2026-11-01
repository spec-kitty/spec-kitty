---
title: 'Migration: Verdict-Provenance Backfill'
description: "Upgrade-time backfill (FR-012/SC-008) reducing each mission's terminal review-cycle .md verdict into the event log, completing event authority after the verdict-reader collapse."
doc_status: active
updated: '2026-08-06'
related:
- architecture/status-model
- migrations/mission-id-canonical-identity
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Migration: Verdict-Provenance Backfill

**Status**: Shipped with mission `verdict-seam-write-unification-01KZ9Q35`.
**Migration id**: `verdict_provenance_backfill`
(`src/specify_cli/upgrade/migrations/m_zz_verdict_provenance_backfill.py`).
**Audience**: Operators upgrading existing Spec Kitty projects across the
verdict single-authority cutover.

## Why This Matters

The `verdict-seam-write-unification-01KZ9Q35` mission made the append-only
event log (`status.events.jsonl`) the **sole** authority for a work package's
review verdict. Every verdict reader was collapsed onto the event-sourced
`review_result` slot, and the `review-cycle-N.md` frontmatter readers were
**deleted** — the irreversible half of single-authority.

That deletion is only safe if the event log already carries every verdict a
mission ever recorded. A mission created before the cutover can carry a
**terminal `.md` verdict with no `review_result` event slot** — a *stranded*
verdict. Once the frontmatter readers are gone, a consumer reading the event
authority mid-upgrade would simply not see that historical rejection.

This migration closes that gap (FR-012 / SC-008): it recovers each stranded
`.md` verdict into the event log so the authority is complete before anyone
reads it.

## What It Does

On `spec-kitty upgrade`, for **every** mission under `kitty-specs/`:

1. Find each WP with a terminal `review-cycle-N.md` verdict but no event
   `review_result` slot (the `stranded_verdict_findings` predicate).
2. Reduce that historical verdict into a **hand-constructed** `review_result`
   `StatusEvent` appended to `status.events.jsonl`
   (`backfill_verdict_provenance`). The event's timestamp is the artifact's
   own historical `reviewed_at` — never `now()` — so it sorts correctly in the
   reducer's `(at, event_id)` fold and never resurrects over a later approval.

The backfill spine is unchanged; this migration only adds the corpus walk.

## When It Runs

Automatically, as an auto-discovered upgrade migration
(`@MigrationRegistry.register` + `pkgutil.iter_modules`), during
`spec-kitty upgrade`. It targets the current package version and runs after the
charter-fold migrations at the same version (the `m_zz_` filename encodes that
ordering). No operator action beyond running `upgrade` is required.

## Idempotency

The backfill is keyed on a **deterministic ULID** over
`(mission_id, wp_id, verdict, cycle)` and skips any WP that already carries a
`review_result` event slot. Re-running `upgrade` over an already-migrated
corpus therefore seeds nothing:

- `detect()` returns `False` once every mission is converged.
- A live `apply()` appends zero events; a `--dry-run` reports a would-seed
  count of `0`.

Running it more than once is safe.

## Verifying

`spec-kitty accept` carries a **non-blocking** diagnostic that reports any
remaining stranded verdict for the mission under acceptance (naming the WPs and
pointing at `spec-kitty upgrade`). A clean upgrade leaves it silent. The
diagnostic is advisory only — it never blocks acceptance and never raises.

## Rationale / References

- Requirement: FR-012 (backfill) / SC-008 (safe reader collapse).
- Backfill library: `src/specify_cli/migration/verdict_provenance_backfill.py`.
- Follow-up: [#3236](https://github.com/Priivacy-ai/spec-kitty/issues/3236)
  now tracks only the function-level census-exclusion narrowing for
  `_legacy_frontmatter_verdict`, not the wiring — which this migration closes.
