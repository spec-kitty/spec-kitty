# Data Model — Doctor mission-state legacy repair & report fidelity

## Entity: `change_mode` (mission metadata field)

| Attribute | Value |
|-----------|-------|
| Location | `meta.json` per mission |
| Type | `str \| None` (optional) |
| Canonical values | `"bulk_edit"` only |
| Ordinary mission | field **absent** (`None`) — no guardrail applies |
| Legacy/foreign value | any other string (e.g. `"regular"`) or non-string — never written by this codebase |
| Invariant (INV-1) | A stored `change_mode` is either `"bulk_edit"` or absent. Repair enforces this by normalization. |
| Invariant (INV-2) | Removing a non-`bulk_edit` value changes no runtime behavior at any read boundary (behavior-preserving). |
| Write path | `set_change_mode` rejects anything not in `VALID_CHANGE_MODES` (unchanged). |
| Repair path | `_canonicalize_mission_meta` normalizes non-`bulk_edit` → absent, records `normalized_change_mode`. |

**State transition (repair):**
```
change_mode = "regular"  ──normalize──▶  (field removed)   [action: normalized_change_mode]
change_mode = "bulk_edit" ──unchanged──▶ change_mode = "bulk_edit"
(absent)                  ──unchanged──▶ (absent)
change_mode = <malformed> ──normalize──▶ (field removed)   [action: normalized_change_mode]
```

## Entity: Repair report (`--fix`) — existing, extend rendering

| Field | Meaning | Change |
|-------|---------|--------|
| `missions[]` | per-mission `MissionRepairResult` (`mission_slug`, `mission_id`, `status`, `file_changes`, `row_transformations`, `quarantined_rows`, `validation_errors`) | already populated for errors/changes; **now rendered** per-mission in terminal |
| **`meta_actions[]`** (NEW) | per-mission meta canonicalizer actions (`normalized_change_mode`, `removed_meta_key:*`, `mission_id_deterministically_backfilled`, …) | **NEW FIELD** on `MissionRepairResult` (FR-013). Today `_canonicalize_meta` returns these but they are consumed only as a boolean write-gate at `mission_state.py:~1499` and **discarded** — this mission wires them into the result + `to_dict()`. Recorded **conditionally** (only when the field was present/changed) so idempotency holds. |
| summary counts | updated / unchanged / errors | kept |
| manifest path | sidecar location | kept (sidecar, not sole evidence) |

**New rendering contract:** for every mission with `status` errored OR with non-empty `meta_actions`, the terminal prints `mission_slug` + reason/actions; `--json` carries the full list including `meta_actions` — verified by test.

**Correction (post-plan squad):** an earlier draft claimed a per-mission `actions` field was "already populated." It is not — `MissionRepairResult` and `FileChange` carry no meta-action field today; adding `meta_actions` is an explicit, owned schema change (safe against the `to_dict()` shape tests, which compare `["summary"]` / whole-dict A==B determinism, not a fixed key set).

## Reader alignment (FR-012 — durable fix)

`change_mode` has an implicit value-semantics reader outside `validate_meta`: `bulk_edit/gate.py:91-95` returns the **raw** value in `GateResult.change_mode`, and `implement.py:1340` does `if gate_result.change_mode is not None: return` — treating a legacy value like `"bulk_edit"` (skip inference) but absent differently (run inference). This mission aligns that reader to `== "bulk_edit"` (matching `workflow_executor.py:1609`) and pins `GateResult.change_mode ∈ {"bulk_edit", None}`, so a legacy value and absence are indistinguishable at every reader (INV-2 / NFR-001).

## Entity: Dry-run report (`--teamspace-dry-run`) — existing, reach parity

| Field | Meaning | Change |
|-------|---------|--------|
| `errors[]` | per-error dict: `mission_slug`, `artifact_path`, `line`, `error` code, `message` | already built; **now rendered** per-mission in terminal + emitted in `--json` |
| summary | `N validation errors` | kept as a header, no longer the only output |

**Parity requirement:** dry-run emits per-mission structured records equivalent in shape to the repair report's error records (so an agent can consume either identically).

## Reconciliation surface

`audit/shape_registry.py` (writer-schema authority) and `mission_metadata.validate_meta` must agree on a legacy `change_mode`: audit must not present it as valid-and-final while fix treats it as an unrecoverable error. The canonical classification is **repairable**.
