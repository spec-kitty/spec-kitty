# Contract deltas: Lane and worktree model hardening

Only the CLI and JSON contract **deltas** are listed. All are additive unless marked otherwise.

| File | Surface | Kind | Version impact |
|---|---|---|---|
| [finalize-tasks-json.md](./finalize-tasks-json.md) | `spec-kitty agent mission finalize-tasks --json` (and `--validate-only`) | additive `topology_decision` object | none for the agent CLI; mirrored on `orchestrator-api tasks` under contract 1.24.0 (DM `01M6R0BJQ6Q1MV6492EH6HB66H`) |
| [mission-create-json.md](./mission-create-json.md) | `spec-kitty agent mission create --json`, `specify --json`, `orchestrator-api specify` | additive `topology_source`, `topology_provisional`; the `topology` value is `single_branch` while provisional | none for the agent CLI; on `orchestrator-api specify` under contract 1.24.0 (DM `01M6R0BJQ6Q1MV6492EH6HB66H`) |
| [consolidate-cleanup-report.md](./consolidate-cleanup-report.md) | `spec-kitty consolidate` text and `--json`; `orchestrator-api consolidate-mission`; `accept --mode pr --json` | per-lane cleanup outcomes; exit 0 after a verified landing with kept lanes | **orchestrator-api 1.23.0 → 1.24.0 (minor, the Mission's one bump; it also carries the topology fields, DM `01M6R0BJQ6Q1MV6492EH6HB66H`)** |
| [for-review-gate-refusal.md](./for-review-gate-refusal.md) | `agent status emit`, `move-task`, `orchestrator-api transition` | refusal text; envelope shape unchanged | none |
| [error-codes.yaml](./error-codes.yaml) | all | new and reused codes, with where they surface | see entries |

## Internal-only (no external contract change)

- **S1 read door** (`StatusReadSurface`, `resolve_status_read`) is an internal Python API. CLI status output is unchanged in shape. Values become consistent across working directories (SC-001). A bad ref now exits non-zero where it used to print an empty history; that is a behaviour fix, not a schema change.
- **S3 lane-checkout helper and S6 exclusion** change no command flags or JSON. The migration report prints in `spec-kitty upgrade` and `migrate ledger` output with the existing clone-local partition semantics.
- **S8** adds no orchestrator-api code. Refusals arrive as `PREFLIGHT_FAILED` with the reused codes in `preflight_error_codes` (FR-076). The status event shape gains `policy_metadata.lane_head` on `single_branch` events (an existing optional key).
- **`meta.json`** gains `topology_source`, `topology_settled`, `topology_decision` and `create_return_branch` (additive; see data-model.md §1).
- **S9** contract changes to `mission-write` are recorded in the Proposed spec-kitty-events ADR 0007 draft only. Nothing changes in this repository.
