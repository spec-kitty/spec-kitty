---
title: Clean Up Local Event Logs
description: 'Preview, then remove, the local run journals, event logs and caches under .kittify/ that are past retention, with spec-kitty doctor event-logs.'
doc_status: active
updated: '2026-10-27'
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

For a script, add `--json`. The payload holds `applied`, `limits`, `candidates`, `kept`, `deleted`, `failed` and `removed_index_entries`; every item carries `surface`, `kind`, `path`, `mission`, `age_days` and `reason`.

```bash
spec-kitty doctor event-logs --json
```

## Read the reasons

| Reason | Meaning |
|---|---|
| `past retention; Mission completed` | A candidate: outside the newest `keep_runs`, older than `max_age_days`, and its Mission is completed. |
| `rebuildable cache` | A candidate: a derived Mission view or the Op index, which Spec Kitty rebuilds when it needs them. |
| `within keep_runs` | Kept: one of the newest `keep_runs` items of its kind. |
| `younger than max_age_days` | Kept: modified within the last `max_age_days` days. |
| `Mission is open` | Kept: its Mission is not completed yet. |
| `Mission not found` | Kept: this checkout has no Mission with that identity, for example because it lives on another branch. |
| `lock held` | Kept: another process is using it right now. |

An item is removed only when it is past BOTH limits and its Mission is completed.

## Tune the limits

The limits live under `ledger.retention` in `.kittify/config.yaml`. Without that block the defaults apply (`keep_runs: 20`, `max_age_days: 30`):

```yaml
ledger:
  retention:
    keep_runs: 50      # protect the newest 50 items of each kind
    max_age_days: 90   # and everything modified in the last 90 days
```

Both values must be whole numbers of 0 or more. An invalid value or an unknown key makes the command stop with exit code 2 and a message naming the key; nothing is scanned or deleted.

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
| `2` | Not inside a project, or `ledger.retention` is invalid. Nothing was scanned or deleted. |

## What is never removed

- Committed Mission records: `status.events.jsonl`, `decisions.events.jsonl` and the Op records under `kitty-ops/`.
- Lock files.
- The glossary logs that belong to no Mission (`_cli`, `_renderer`).
- The logs and runs of an open Mission, or of a Mission this checkout cannot find.
- Anything whose lock another process holds.

## See also

- [ADR 2026-10-13-2: The event ledger is the publication seam, default on, with local retention](../../../adr/4.x/2026-10-13-2-the-event-ledger-is-the-publication-seam-default-on-with-local-retention.md)
- [CLI Command Reference: `spec-kitty doctor event-logs`](../../../api/cli-commands.md#spec-kitty-doctor-event-logs)
