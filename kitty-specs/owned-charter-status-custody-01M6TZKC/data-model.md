# Data Model: Owned Mission coordination status charter custody

## Owned Mission custody

- **OwnedCheckout**: existing validated identity supplying `repository_root`, `owned_root`, `mission_slug`, and `mission_dir`; unchanged.
- **Primary Mission directory**: `owned.mission_dir`, admitted by the existing resolved-equality fast path and retained as the charter-scope anchor.
- **Canonical status directory**: `mission_context_for(...).artifact(MissionArtifactKind.STATUS_STATE).read_dir`, admitted only on the unequal arm after resolved exact equality.
- **Foreign directory**: every other input, refused with the existing `MISSION_CONTEXT_CONFLICT` error.

## Invariants

1. No additional placement lookup occurs when `feature_dir` is absent or equals `owned.mission_dir` after resolution.
2. A canonical status match changes admission only; it never changes the charter root or primary Mission directory.
3. No new persisted field, state transition, external contract, or migration exists.
