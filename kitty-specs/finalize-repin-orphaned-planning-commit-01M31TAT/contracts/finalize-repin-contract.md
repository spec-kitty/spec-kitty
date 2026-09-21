# Contract: finalize re-pin CLI + JSON + error surfaces (#4827)

## CLI flag surface (`spec-kitty agent mission finalize-tasks`)

Adds one boolean option; the existing surface is otherwise unchanged.

| Flag | Type | Default | Meaning |
|------|------|---------|---------|
| `--allow-orphaned` | bool | `False` | Only meaningful with `--refresh-planning-commit`. Permits the re-pin to re-point a recorded SHA that is **orphaned** (present in the object store but unreachable from the target-branch tip — the mid-mission-rebase shape). Without it, `--refresh-planning-commit` stays advance-only (refuses a non-ancestor). Refused regardless for a **foreign** (absent) object. |

- The golden-contract frozenset `_EXPECTED_FLAGS["finalize-tasks"]` in `test_mission_cli_golden_contract.py` gains `--allow-orphaned` in the same PR (exact set-equality assertion).
- The `--refresh-planning-commit` help text is updated to mention the `--allow-orphaned` escape hatch for the rebase case.

## JSON success payload (`--json`)

`planning_commit` object `action` enum extends to include `repinned`:

```json
{"result": "success",
 "planning_commit": {"action": "repinned", "sha": "<new tip>", "previous_sha": "<orphaned sha>", "branch_tip": "<new tip>"}}
```

Existing values `captured` / `preserved` / `refreshed` are unchanged. `orchestrator_api/envelope.py` `CONTRACT_VERSION` 1.5.0 → 1.6.0 (additive; no consumer contract test pins the action vocabulary).

## Error / diagnostic contracts

| Situation | Surface | Contract |
|-----------|---------|----------|
| Plain finalize, proven orphan, capturable tip | finalize (human + `--json` error) | fail closed BEFORE any `lanes.json` write; message names the recorded SHA, the tip, and the `--refresh-planning-commit --allow-orphaned` recovery. |
| `--refresh-planning-commit` (no `--allow-orphaned`), non-ancestor | finalize | refused (Exit 1); message **contains** "not an ancestor" (preserves #4141 test). |
| `--refresh-planning-commit --allow-orphaned`, foreign (absent) object | finalize | refused (Exit 1); message says the object is absent / investigate; no re-pin. |
| Non-git / uncapturable tip, plain finalize | finalize | DEGRADE to historical preserve (no abort). |
| Orphaned pin at lane allocation / reconcile | `_merge_recorded_planning_commit` | raises an orphan-specific error whose `next_step` names the finalize re-pin recovery — NOT the generic `PlanningCommitMergeConflictError`. |
| Healthy (reachable) pin, real content conflict | `_merge_recorded_planning_commit` | unchanged generic `PlanningCommitMergeConflictError`. |
| Orphaned pin at claim gate | `check_claim_ancestry` | names orphan + recovery, not a bare `missing_refs` entry. |
| Orphaned pin at owned-review base | `_mt_resolve_owned_review_base` | detects orphan, fails closed / names recovery; never diffs against the dead base. |

## Backward-compatibility invariants (NFR-001)

- `--allow-orphaned` defaults `False`; every existing invocation behaves identically.
- The bare-flag non-ancestor refusal keeps the "not an ancestor" substring.
- Non-git / synthetic-absent-SHA preserve (#3311) is unchanged (degrade path).
