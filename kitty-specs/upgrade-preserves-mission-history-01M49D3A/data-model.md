# Data Model: Upgrade must not rewrite healthy Mission history

## Entities

### Status event row (one line of `status.events.jsonl`)

There are three classes:

| Class | Recognised by | Repair behaviour |
|---|---|---|
| Lane row | has `to_lane` + `wp_id`, no non-lane `event_type`/`kind` | alias/strip → `StatusEvent.from_dict` → `to_dict` → store row-to-line; unchanged bytes when already writer-shaped |
| Preserved non-lane row | `event_type` in `AUTHORITATIVE_NON_LANE_EVENT_TYPES`, or `_is_preserved_non_lane_row` | byte-preserved |
| Annotation row | `kind == "annotation"` | byte-preserved |

**Invariants**
- The physical order of the rows is never changed.
- A writer-shaped lane row is a fixed point: `line(canon(row)) == original line`.
- A populated optional field (`reason_source`, `review_result`, `mission_id`) survives; an absent one stays absent.

### Mission directory

`is_mission_dir(path)` is true when `path/spec.md` or `path/meta.json` is git-tracked. Any other directory under `kitty-specs/` is a **residue directory**. A residue directory produces a non-blocking `RESIDUE_DIRECTORY` finding, and the repair never writes into it.

### Derived files (`status.json`, `lanes.json`)

The repair writes a derived file only when both are true:
- the Mission's event log changed in this repair;
- the file is tracked, or was already present.

Drift without a log change is reported as a finding and not rewritten.

### Repair outcome

The repair outcome carries `updated`, `unchanged`, `errors` and `errored_missions` (each with its first reason). "Blockers cleared" is reported only when `errors == 0`, and the exit code is non-zero when `errors > 0`.

## State: upgrade gate

```
drain off → gate not evaluated
drain on  → evaluate readiness → blocked? → report count/codes + `spec-kitty doctor mission-state --fix`; exit 0; no writes
                               → clear   → no output
```
