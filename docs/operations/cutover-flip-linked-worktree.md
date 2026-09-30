---
title: 'Recovery: Cutover Flip Fails From a Linked Worktree'
description: 'Recovery when the runtime-state cutover flip fails closed with PlacementMismatchError inside a linked git worktree, even though migration events seeded.'
doc_status: active
updated: '2026-08-15'
related:
- docs/operations/recovery-index.md
- docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md
---

# Recovery: Cutover Flip Fails From a Linked Worktree

`spec-kitty cutover-guard --base-ref <ref>` reports `status_phase not flipped
despite event-log runtime evidence`, or `cutover_mission()` raises
`PlacementMismatchError`, even though the migration events were seeded
successfully.

## Why this happens

`cutover_mission()` (seed → verify → flip) is run from a linked git
worktree — for example a `.worktrees/pr-*-landing` landing worktree.
`_flip_phase` (`src/specify_cli/migration/runtime_state_cutover.py`)
resolves the PRIMARY home via `resolve_canonical_root`, which maps a linked
worktree back to the **primary checkout**. It then compares that absolute
primary-checkout path against the (relative, worktree-scoped) write target.
They never match, so the flip fails closed before writing `status_phase` — a
correct, intentional refusal, not a bug. The seed events still get written
(they append to a relative path), so only the flip step is blocked.

## No shipped `--fix` for this case

`spec-kitty doctor cutover` is informational only — it always exits 0 and
reports a per-mission cut-over verdict, but it has no `--fix`. Its
whole-corpus `--dry-run` spine also reads from a different root than a
single worktree expects (it can report `would_flip` for missions already
flipped on `main`), so trust the CI `cutover-guard` per-mission verdict over
a whole-corpus dry-run when you're inside a worktree.

## Fix: run from the primary checkout (preferred)

The simplest fix is to not run the flip from the worktree at all — `cd` into
the primary checkout and re-run:

```bash
spec-kitty migrate backfill-runtime-state --mission <slug>
```

## Fix: apply the flip's exact net write directly (when you can't leave the worktree)

1. Seed the migration events (idempotent if already seeded):

   ```python
   from specify_cli.migration.backfill_runtime_state import run_backfill_and_verify
   run_backfill_and_verify(mission_dir, dry_run=False)
   ```

2. Apply the flip's exact net write yourself:

   ```python
   from specify_cli.core.paths import load_meta_fail_closed
   from specify_cli.mission_metadata import write_meta

   write_meta(
       mission_dir,
       {**load_meta_fail_closed(mission_dir), "status_phase": "1"},
       validate=False,
   )
   ```

   `validate=False` is deliberate and narrow here — you're setting only the
   single `status_phase` field the flip would set; do not reuse this bypass
   for broader `meta.json` edits.

3. Confirm:

   ```python
   from specify_cli.status.cutover_eligibility import is_cut_over
   assert is_cut_over(mission_dir).cut_over is True
   ```

   ```bash
   spec-kitty cutover-guard --base-ref upstream/main
   ```

   The guard should report 0 un-cut-over missions.

## Related

- [Coord-branch bookkeeping root-cause](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md)
- [Recovery & Troubleshooting (agent-facing)](../guides/how-to/recovery/index.md) — implementation-crash and merge recovery
