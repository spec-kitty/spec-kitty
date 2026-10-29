---
title: Clean Up Local Event Logs
description: 'Preview, then remove, the local run journals, event logs and caches under .kittify/ that are past retention, with spec-kitty doctor event-logs.'
doc_status: active
updated: '2026-10-28'
type: how-to
audience: docs/context/audience/external/project-owner.md
---
# Clean Up Local Event Logs

Every `spec-kitty next` run writes a run journal under `.kittify/runtime/runs/`, and the glossary keeps one event log per Mission under `.kittify/events/glossary/`. These files are local: git ignores them, and nothing removes them on its own, so `.kittify/` keeps growing. Use `spec-kitty doctor event-logs` to see what is past retention and remove it.

## Preview what would be removed

Run the command without options. It lists every item it looked at and changes nothing:

```bash
spec-kitty doctor event-logs
```

The report has two lists:

- **Candidates**: the items `--apply` would delete, each with its path, age and reason.
- **Kept**: everything else, grouped by the reason it stays.

Each item names its **surface**: the kind of state file it is, by its name in the Spec Kitty state registry (for example `runtime_run_event_log` for a run directory or `glossary_fallback_events` for a glossary log).

For a script, add `--json`:

```bash
spec-kitty doctor event-logs --json
```

The payload holds:

- `applied`: `true` after `--apply`, `false` for a preview.
- `limits`: `keep_runs`, `max_age_days` and `source`, which is `.kittify/config.yaml` when the limits come from that file and `default` otherwise.
- `candidates`, `kept`, `deleted`: lists of items. Every item carries `surface`, `kind` (`run`, `mission_log` or `cache`), `path` (relative to the project), `mission` (the Mission directory name under `kitty-specs/`, or `null` when there is none), `age_days` and `reason`.
- `failed`: the items whose deletion failed, each with the item fields plus `error`, the error text.
- `removed_index_entries`: the run-index entries removed with their runs.

When the command stops with exit code 2, `--json` prints an error envelope instead: `{"ok": false, "error": {"code": ..., "message": ...}}`. The codes are `config_error` (the configuration cannot be read or is invalid), `not_in_project` (not run inside a Spec Kitty project) and `retention_policy_drift` (an internal error, see below).

## Read the reasons

| Reason | Meaning |
|---|---|
| `past retention; Mission completed` | A candidate: outside the newest `keep_runs`, older than `max_age_days`, and its work is over (see below). |
| `rebuildable cache` | A candidate: a derived Mission view under `.kittify/derived/`. It is rebuildable: Spec Kitty rebuilds it the next time it is read. |
| `within keep_runs` | Kept: one of the newest `keep_runs` items of its kind. |
| `younger than max_age_days` | Kept: modified within the last `max_age_days` days. |
| `Mission is open` | Kept: its work is not over yet (see below). |
| `Mission not found` | Kept: this checkout has no Mission with that identity, for example because it lives on another branch. |
| `lock held` | Kept: another process is using it right now. |

An item is removed only when it is past BOTH limits and its work is over:

- **A run** is over when its Mission is merged, or when the run itself finished (its journal records that the run completed). A run of a Mission whose work packages are all done but which was never merged stays until the Mission is merged or the run finishes.
- **A glossary log** is over when its Mission is completed: merged, or every work package done or canceled.

A run's Mission is the one `spec-kitty next` recorded for it in the run index. Rebuildable caches are candidates whatever their age, unless locked.

## Tune the limits

The limits live under `ledger.retention` in `.kittify/config.yaml`. Without that block the defaults apply (`keep_runs: 20`, `max_age_days: 30`):

```yaml
ledger:
  retention:
    keep_runs: 50      # protect the newest 50 items of each kind
    max_age_days: 90   # and everything modified in the last 90 days
```

Both values must be whole numbers of 0 or more. An invalid value, an unknown key, a `.kittify/config.yaml` that is not valid YAML, or a `ledger` or `ledger.retention` that is not a mapping makes the command stop with exit code 2 and a message naming the problem; nothing is scanned or deleted.

## Remove the candidates

When the preview looks right, delete exactly the listed candidates:

```bash
spec-kitty doctor event-logs --apply
```

Each candidate's lock is checked again just before it is deleted, so an item that became busy is kept and reported as `lock held`. When a run directory is deleted, its entry in `.kittify/runtime/feature-runs.json` goes with it, and the report lists it under the removed run-index entries.

The exit code tells you how it went:

| Exit code | When |
|---|---|
| `0` | A preview, or an apply where every deletion succeeded (or there was nothing to delete). |
| `1` | An apply where at least one deletion failed. The `failed` list names each item and its error. |
| `2` | Not inside a project (`not_in_project`); the configuration cannot be read or `ledger.retention` is invalid (`config_error`); or an internal error where the state registry and the cleanup engine disagree (`retention_policy_drift`). Nothing was scanned or deleted. Please report a `retention_policy_drift` error. |

## What is never removed

- Committed Mission records: `status.events.jsonl` and `decisions.events.jsonl`.
- The Op records under `kitty-ops/` and the Op index, `kitty-ops/ops-index.jsonl`. `spec-kitty invocations list` reads the index as it is, so removing it would hide Op history.
- The run index file, `.kittify/runtime/feature-runs.json`. Only the entries of deleted runs leave it.
- Lock files.
- The glossary logs that belong to no Mission (`_cli`, `_renderer`).
- The logs and runs whose work is not over, or whose Mission this checkout cannot find.
- Anything whose lock another process holds.

## See also

- [ADR 2026-10-13-2: The event ledger is the publication seam, default on, with local retention](../../../adr/4.x/2026-10-13-2-the-event-ledger-is-the-publication-seam-default-on-with-local-retention.md)
- [CLI Command Reference: `spec-kitty doctor event-logs`](../../../api/cli-commands.md#spec-kitty-doctor-event-logs)
