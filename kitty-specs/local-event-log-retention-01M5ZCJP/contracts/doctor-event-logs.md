# Contract: `spec-kitty doctor event-logs`

```
spec-kitty doctor event-logs [--apply] [--json]
```

- No flag: preview. Lists candidates and kept items with reasons. Changes nothing.
- `--apply`: deletes every candidate (re-checking its lock), removes a deleted run's `.kittify/runtime/feature-runs.json` entries under the run lock and the index lock, then removes the run directory after releasing both, and reports `deleted` and `failed`.
- Scope: run directories and per-Mission glossary logs (`ledger_retention`), derived Mission views (`rebuildable`). The Op index (`kitty-ops/ops-index.jsonl`) and the run index file are never deleted.
- A run is a candidate only when its Mission is merged or the run itself recorded `MissionRunCompleted`; a glossary log when its Mission is completed (merged, or every WP terminal).
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

In preview, `deleted`, `failed` and `removed_index_entries` are empty. `mission` is the Mission directory name or `null`; each `failed` entry adds `error` (the error text).

On exit 2 with `--json`, the payload is the doctor error envelope `{"ok": false, "error": {"code": ..., "message": ...}}` with code `config_error`, `not_in_project` or `retention_policy_drift`.

## Exit codes

| Code | When |
|---|---|
| 0 | Preview, or an apply where every candidate was deleted (or there were none) |
| 1 | An apply where at least one deletion failed |
| 2 | Not inside a project, the configuration unreadable or `ledger.retention` invalid, or the internal registry/engine drift error (nothing scanned, nothing deleted) |

## Config

```yaml
# round-trip: skip: illustrative .kittify/config.yaml excerpt, not a Pydantic contract example
ledger:
  retention:
    keep_runs: 20      # protect the newest N of each kind
    max_age_days: 30   # and everything younger than this
```

Deletion requires BOTH limits exceeded.
