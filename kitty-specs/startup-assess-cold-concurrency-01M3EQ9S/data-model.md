# Data Model: Concurrency-safe cold startup asset assessment

## TornReadError (value-carrying exception; subclass of `ValueError`)

| Field | Type | Source | Invariant |
|---|---|---|---|
| `path` | `Path` | The observed path whose state changed within one pass | The same path was observed twice with different `(state, identity)` |
| `role` | `ObservationRole` (`"source_read"` \| `"destination_probe"`) | The effective role: `source_read` if either observation was a source read | Source-role stickiness is honoured |
| `lock_paths` | `tuple[Path, ...]` | `(AssetPreparation.lock_path,)` | Equal to the `PreparedAssets.lock_paths` that `finish()` would produce |
| `anchor` | `Path` | `AssetPreparation.root.path` | Equal to `PreparedAssets.anchor` |

`str(exc)` equals `f"Asset changed during preparation: {path}"`, the same as today.

## Serialization point (`_serialize_owner(lock_paths, anchor)`)

- `cold = any(not p.exists() for p in lock_paths)`. If cold, acquire `machine_file_lock(_cold_install_sentinel(anchor), blocking=True)`.
- For each `p in lock_paths` that exists: `machine_file_lock(p, blocking=True)`.
- Then set `_HELD_LOCKS |= set(lock_paths)` and reset it on exit.
- Invariant: one implementation, used by both `recheck_assets` and `build_serialized` (C-008).

## Escalation state machine (`build_serialized`)

```
UNLOCKED_ATTEMPT --ok--> DONE
UNLOCKED_ATTEMPT --TornReadError(source_read)--> TERMINAL(source_drift)
UNLOCKED_ATTEMPT --TornReadError(dest), _HELD_LOCKS non-empty--> TERMINAL(torn_read)
UNLOCKED_ATTEMPT --TornReadError(dest), nothing held--> SERIALIZED_ATTEMPT   [INFO log once]
UNLOCKED_ATTEMPT --other exception--> PROPAGATE (unchanged)
SERIALIZED_ATTEMPT --ok--> DONE
SERIALIZED_ATTEMPT --TornReadError--> TERMINAL(torn_read)
SERIALIZED_ATTEMPT --other exception--> PROPAGATE
```

## Diagnostic codes (on an incomplete `OwnerAssessment`)

| Code | When | New? |
|---|---|---|
| `asset_torn_read` | Terminal destination-role torn read (under lock or re-entrant) | new |
| `asset_source_drift` | Source-role torn read | new |
| `global_assets_unavailable` | Any other `OSError`/`ValueError` during assessment | existing, unchanged |

## StartupAssetError (subclass of `GuardedReadError` and `RuntimeError`)

- Raised by `ensure_runtime`, `_apply_command_assessment` and `ensure_global_agent_skills` when an assessment is incomplete or an apply result is neither `applied` nor `skipped`.
- `reason`: the joined diagnostic messages plus a next step. For example: "another spec-kitty process may still be installing; re-run the command. If it persists, remove the partially-written home (`<path>`) and re-run."
- `path`: `str` of the offending path when a single diagnostic names one, otherwise `None`. It must be a `str`, never a `Path`, because the JSON envelope `json.dumps` it.
- `code` (attribute): the first diagnostic's code. It is a Python attribute only. The CLI JSON envelope emits `error`/`kind`/`path` and stays unchanged (C-010).
- Rendered by `_run_app_with_error_hook`: exit 1, one stderr line, or a JSON object under `--json`.
