# Data Model: Upgrade reports one outcome

## UpgradeOutcomeKind (string enum)

`applied` · `no_op` · `drift_unresolved` · `failed`

## UpgradeFailureReason (string enum)

| Value | Holds when |
|-------|-----------|
| `migration_failed` | `result.success` is false |
| `activation_error` | `activation_errors` is non-empty |
| `worktree_failure` | `worktree_failures` is non-empty |
| `commit_recovery_failed` | the churn commit failed to restore the operator's staging |
| `surface_repair_failed` | a repair was not applied |
| `preview_incomplete` | a dry-run preview could not be completed |
| `surface_drift` | `drifted_paths` is non-empty |

Order above is the order of `reasons`.

## SurfaceRepairReport (frozen)

| Field | Type | Meaning |
|-------|------|---------|
| `drifted_paths` | `tuple[Path, ...]` | managed files preserved pending consent |
| `failed` | `bool` | a repair was not applied |
| `preview_incomplete` | `bool` | dry-run preview could not be completed |
| `failure_messages` | `tuple[str, ...]` | one reason per non-applied repair, synthesised when the repair gave no error diagnostic |

Returned by the finalizer's `run_surface_repair` callable.

## UpgradeOutcome (existing, extended)

| Field / member | Change |
|----------------|--------|
| `result`, `manual_review_paths`, `worktree_failures`, `activation_errors`, `repair`, `committed`, `exit_code` | unchanged |
| `surface_drift_failed` | removed |
| `had_migrations: bool` | new |
| `drifted_paths: list[Path]` | new |
| `surface_repair_failed: bool`, `preview_incomplete: bool` | new |
| `warnings() -> list[str]` | new; `result.warnings` plus the mission-state repair message when `repair.failed` |
| `reasons -> tuple[UpgradeFailureReason, ...]` | new, derived |
| `kind -> UpgradeOutcomeKind` | new, derived |
| `effective_success -> bool` | now `not reasons` (same truth table as before) |
| `errors() -> list[str]` | new; ordered: `result.errors`, `activation_errors`, `worktree_failures` (de-duplicated), repair-failure message when no diagnostic names it, drift message when `drifted_paths` |
| `status -> str` | new; `success` / `up_to_date` / `failed` |
| `closing_line() -> str` | new |
| `derive_exit_code()` | unchanged; still the only site |

## Invariants

1. `exit_code == 0` iff `kind in {applied, no_op}`.
2. `status == "failed"` iff `exit_code != 0`.
3. `errors()` is non-empty whenever `exit_code != 0`.
4. The drift message appears in `errors()` iff `len(drifted_paths) >= 1`, and its count equals `len(drifted_paths)`.
5. A `repair` (mission-state) outcome never contributes a reason.
