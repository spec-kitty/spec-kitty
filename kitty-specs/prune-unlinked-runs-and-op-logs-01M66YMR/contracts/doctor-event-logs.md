# Contract: `spec-kitty doctor event-logs` (amended for #6739)

```
spec-kitty doctor event-logs [--apply] [--json]
```

Unchanged: the flags, the exit codes, the limits (`ledger.retention.keep_runs`,
`max_age_days`), the both-limits-required rule, the preview/apply parity, the lock
guarantee, and the never-removed list (committed Mission ledgers, Op records and the
Op index, the run index, tracked files, lock files, `_cli` / `_renderer` logs).

## What changes

Two families that were reported `Mission not found` and kept forever now resolve
their owner and take a normal verdict:

| Item | Link | Verdict |
| --- | --- | --- |
| run with no run-index entry whose snapshot records its Mission by slug (`inputs.mission_slug`) | the Mission that slug names | as an indexed run: candidate once past both limits and the Mission is merged or the run finished; `Mission is open` otherwise |
| run that records no Mission identity anywhere | none (unlinked) | candidate once past both limits, reason `past retention; no Mission recorded` |
| `.kittify/events/glossary/profile-invocation-<id>.events.jsonl` whose Op is closed | the closed Op | candidate once past both limits, reason `past retention; Op completed` |
| the same log whose Op is open | the open Op | kept, reason `Op is open` |
| the same log whose Op has no record here | none (unlinked) | candidate once past both limits, reason `past retention; no Op recorded` |

Unchanged and re-affirmed: a run whose recorded Mission identity this checkout
cannot resolve, or that resolves ambiguously, is kept as `Mission not found`.

## JSON shape

The envelope, keys and item fields are unchanged; only the `kind` and `reason`
value sets grow:

```json
{
  "applied": false,
  "limits": {"keep_runs": 20, "max_age_days": 30, "source": ".kittify/config.yaml | default"},
  "candidates": [
    {"surface": "glossary_fallback_events", "kind": "op_log", "path": ".kittify/events/glossary/profile-invocation-<id>.events.jsonl", "mission": null, "age_days": 41.2, "reason": "past retention; Op completed"}
  ],
  "kept": [
    {"surface": "runtime_run_event_log", "kind": "run", "path": ".kittify/runtime/runs/<id>", "mission": null, "age_days": 41.2, "reason": "past retention; no Mission recorded"}
  ],
  "deleted": [],
  "failed": [],
  "removed_index_entries": []
}
```

- `kind` gains `op_log` alongside `run`, `mission_log`, `cache`.
- `reason` gains `past retention; no Mission recorded`, `past retention; Op completed`,
  `past retention; no Op recorded` and `Op is open`.
- `mission` stays `null` for Op logs and for unlinked items.
- Deleting an Op log adds nothing to `removed_index_entries` (it has no index entry);
  deleting an unlinked run adds the same entries an indexed run would, which for an
  unlinked run is normally none.

A consumer that switches on `kind` or `reason` must tolerate unknown values; the
existing consumers (the human renderer, the docs, the tests) read them as strings.

## Exit codes

Unchanged: `0` preview or clean apply, `1` at least one deletion failed, `2` not in a
project / unreadable configuration / registry-engine drift (nothing scanned, nothing
deleted).

## Performance

Unchanged contract: a preview writes nothing, and a scan reads each Op record at
most once. A project with 1,000 Op records and 1,000 glossary logs previews in under
2 s on a warm filesystem.
