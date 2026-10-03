---
title: 'How to repair a Mission whose status snapshot misses work packages'
description: 'Use spec-kitty migrate backfill-wp-status to seed the lane events a Mission’s WP files lack, so status counts match the files; covers dry-run, evidence manifest and JSON.'
doc_status: active
type: how-to
audience: docs/context/audience/external/project-owner.md
updated: '2026-10-03'
related:
- docs/adr/3.x/2026-06-07-3-wp-lane-fsm-genesis-and-finalize-clobber.md
- docs/architecture/status-model.md
- docs/api/cli-commands.md
- docs/migrations/index.md
---
# How to repair a Mission whose status snapshot misses work packages

**Audience**: project owners and maintainers whose Mission shows fewer work
packages (WPs) in `spec-kitty agent tasks status` or in `status.json` than it has
`tasks/WP*.md` files.

`spec-kitty migrate backfill-wp-status` appends the missing `planned` lane
events so the snapshot counts every WP file. Mission data is repaired in place;
no WP file is created, edited or deleted.

## Why a Mission can be short of WPs

The status snapshot is reduced from `status.events.jsonl`, and a WP with no lane
event never appears in it (see the *genesis* lane in
[ADR 2026-06-07-3](../adr/3.x/2026-06-07-3-wp-lane-fsm-genesis-and-finalize-clobber.md)).
A Mission whose log never seeded some `tasks/WP*.md` file therefore under-counts
on every surface that lists WPs from the files. In this repository 51 Missions
had a snapshot WP count that disagreed with their WP files (#5579): 44 were
repaired with this command and 7 are permanent carve-outs whose WP files were
never committed.

## Before you start

- Run inside the project whose Missions you want to repair.
- Run `--dry-run` first. It writes nothing.
- If some Missions are finished, prepare the evidence manifest **before the first
  live run** (see below).

## Steps

1. Preview the repair for the whole corpus:

   ```bash
   spec-kitty migrate backfill-wp-status --dry-run
   ```

   Each affected Mission is listed with the events it would seed. Add `--mission
   <handle>` (`mission_id`, `mid8` or slug) to look at one Mission.

2. If a Mission is finished, name it in an evidence manifest (next section) and
   re-run the preview with `--evidence-manifest evidence.yaml --dry-run`.

3. Run the repair:

   ```bash
   spec-kitty migrate backfill-wp-status --evidence-manifest evidence.yaml
   ```

4. Run it once more. A second run appends nothing; every Mission reports as
   skipped (nothing to seed).

## Mark finished Missions with an evidence manifest

A Mission counts as finished only on terminal evidence. Nothing else qualifies:

- its `meta.json` carries `merged_at` or `accepted_at`, or
- it has an entry in the evidence manifest.

For a finished Mission, each freshly seeded WP is seeded `planned` and then
moved to `done` with a forced event whose reason cites that evidence, so the
Mission reads 100% done. Without evidence the seeded WPs stay `planned`.

The manifest is YAML. Each key is the **exact Mission directory name** under
`kitty-specs/`, and each entry has a non-empty `reason`:

```yaml
missions:
  my-mission-01ABCDEF:
    reason: "PR #1234 merged 2026-09-01; dossier landed on main"
```

The manifest is validated before anything is written. These make the command
exit 1 with nothing changed:

- the file is unreadable or not valid YAML;
- a top-level key other than `missions`, or an entry key other than `reason`;
- a missing, blank or non-text `reason`;
- a Mission name that is not a `kitty-specs/` directory (a typo would otherwise
  do nothing). This is checked even when `--mission` scopes the run elsewhere.

> **The manifest must be complete on the first live run.** Evidence applies
> only to WPs seeded in that same run. Once a run has seeded a WP `planned`, it is
> no longer a gap, so evidence supplied later is a no-op: those WPs are not
> moved to `done`. The summary warns for every manifest entry that had nothing
> to seed. Use `--dry-run` with the full manifest first.

## What the command changes

| Case | Result |
|------|--------|
| WP file with no lane event | One `planned` event, actor `migration:backfill_wp_status` |
| Same WP in a finished Mission | `planned` seed, then a forced `done` event citing the evidence |
| WP that already has any lane event | Left untouched |
| WP in the snapshot but with no WP file | Reported as snapshot-only; never repaired and no file is invented |
| WP file with unusable frontmatter | Reported as malformed and skipped |
| Mission whose status log lives on a live coordination surface | Refused as `COORD_SURFACE_LIVE`; nothing is planned or written, not even on `--dry-run` |

### Missions with a live coordination surface

A Mission with a coordination topology keeps its status log on the coordination
surface while the coordination branch exists and the Mission is not completed.
The log in the PRIMARY-partition `kitty-specs/` directory is not its authority,
so seeding it would split the Mission's status in two. The command therefore
refuses such a Mission: it reports `COORD_SURFACE_LIVE`, counts it as skipped
(exit stays `0`) and writes nothing. Consolidate the Mission first
(`spec-kitty consolidate --mission <handle>`), or run the command from the
coordination checkout. A Mission whose coordination branch has been deleted is
not refused; it is repaired in the PRIMARY-partition directory and no branch is
created.

Events are appended to the Mission's resolved status event log through the
existing migration writer. `status.json` is regenerated only where it already
existed. If that regeneration fails after the events were written, the Mission
is reported with a warning (`refresh_error`, counted in `refresh_warnings`), not
as an error, and the exit code stays `0`: run `spec-kitty materialize` to
regenerate the file. The command is idempotent.

## Read the result

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | Every visited Mission was repaired, needed nothing, or was refused as `COORD_SURFACE_LIVE` |
| `1` | A per-Mission error, an invalid evidence manifest, or an unknown or ambiguous `--mission` handle |

A per-Mission error does not stop the walk over the other Missions; the run
still exits 1.

With `--json`, the command prints one object:

| Key | Content |
|-----|---------|
| `dry_run` | `true` when nothing was written |
| `result` | `success` or `errors_present` |
| `mission` | The `--mission` handle, or `null` for the whole corpus |
| `summary` | Counters: `scanned`, `missions_seeded`, `missions_would_seed`, `events_seeded`, `events_would_seed`, `finished_missions`, `snapshot_only_missions`, `malformed_missions`, `coord_surface_live_missions`, `refresh_warnings`, `skipped`, `errors` |
| `manifest.path` | The manifest path, or `null` |
| `manifest.entries` | Number of manifest entries |
| `manifest.unused` | Entries that had no effect, each `{mission, reason}` where `reason` is `not in scope` (`--mission` named another Mission), `nothing to seed`, or `coordination surface live` (the Mission was refused) |
| `missions` | One row per Mission: `slug`, `seeded`, `would_seed`, `files_only`, `snapshot_only`, `malformed`, `terminal_reason`, `status_json_refreshed`, `refresh_error`, `skip_reason` (`COORD_SURFACE_LIVE` for a refused Mission), `error` |

A failure before any write (bad manifest, unknown handle) prints
`{"success": false, "error_code": ..., "error": ...}` instead.

## Related

- [`spec-kitty migrate backfill-wp-status` in the CLI reference](../api/cli-commands.md#spec-kitty-migrate-backfill-wp-status)
- [Status model](../architecture/status-model.md)
