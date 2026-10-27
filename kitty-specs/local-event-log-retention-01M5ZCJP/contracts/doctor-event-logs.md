# Contract: `spec-kitty doctor event-logs`

```
spec-kitty doctor event-logs [--apply] [--json]
```

- No flag: preview. Lists candidates and kept items with reasons. Changes nothing.
- `--apply`: deletes every candidate (re-checking its lock), removes a deleted run's `.kittify/runtime/feature-runs.json` entries under the index lock, reports `deleted` and `failed`.
- `--json`: machine-readable report.

## JSON shape

```json
{
  "applied": false,
  "limits": {"keep_runs": 20, "max_age_days": 30, "source": ".kittify/config.yaml | default"},
  "candidates": [{"surface": "runtime_run_event_log", "kind": "run", "path": ".kittify/runtime/runs/<id>", "mission": "<slug>", "age_days": 41.2, "reason": "past retention; Mission completed"}],
  "kept": [{"surface": "...", "kind": "...", "path": "...", "mission": null, "age_days": 3.0, "reason": "Mission not found"}],
  "deleted": [],
  "failed": [],
  "removed_index_entries": []
}
```

In preview, `deleted`, `failed` and `removed_index_entries` are empty.

## Exit codes

| Code | When |
|---|---|
| 0 | Preview, or an apply where every candidate was deleted (or there were none) |
| 1 | An apply where at least one deletion failed |
| 2 | Not inside a project, or `ledger.retention` invalid (nothing scanned, nothing deleted) |

## Config

```yaml
ledger:
  retention:
    keep_runs: 20      # protect the newest N of each kind
    max_age_days: 30   # and everything younger than this
```

Deletion requires BOTH limits exceeded.
