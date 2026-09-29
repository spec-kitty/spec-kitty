# Data model — consolidation-claim-rollback-integrity-01M3PD1T

## ConsolidationState (additive, `.kittify/runtime/merge/<mission_id>/state.json`)
| Field | Type | Default | Written | Read |
|---|---|---|---|---|
| `pre_mutation_refs` | `dict[str, str]` branch → sha | `{}` (absent key loads as `{}`) | once, fresh run, before the first mutation | rollback authority; never recaptured by `--resume` |
| `post_mutation_refs` | `dict[str, str]` branch → sha | `{}` | immediately before the reconciliation gate | rollback authority (CAS expected value); cleared after a full restore |

Existing fields reused: `pre_mutation_target_sha`, `pre_mutation_coord_sha/ref`, `pre_interrupt_lane_tips` (seeds), `mission_number_baked`, `completed_wps`, `reconciliation_passed_target_sha` (cleared after a full restore; the latter also drives the FR-011 guard).

**Invariants**: `pre_mutation_refs` is immutable for the life of the record; its keys ⊇ keys of `post_mutation_refs`; a branch is restored only when current == `post_mutation_refs[b]` (or, absent, snapshot is-ancestor-of current).

## RollbackReport (value object, `consolidation/rollback.py`)
- `outcome_by_branch: dict[str, BranchOutcome]` where `BranchOutcome = RESTORED(from, to) | ALREADY_AT_SNAPSHOT(sha) | NOT_RESTORED(observed, expected, reason)`
- `refused_verified_landing: bool` (FR-011)
- `fully_restored: bool` (all RESTORED / ALREADY_AT_SNAPSHOT and not refused)
- `render() -> str` — the only source of operator-facing rollback text.

## State transitions (consolidation record)
fresh → snapshot persisted → mutating → post-mutation tips persisted → gate
- gate PASS → reconciliation_passed_target_sha set → teardown (unchanged)
- gate FAIL/REFUSE or projection refusal → rollback → fully_restored ? (bookkeeping cleared, record kept for `--resume`/`--abort`) : (record kept, branches named)
- `--abort` → rollback → fully_restored ? clear record + teardown : keep record, exit 1
