# Contract: the settlement view and the successor retry rule (#6688)

This is the reviewer-facing contract of the two questions the upgrade subsystem asks about a
declared migration. It is not a wire or API contract; it names what may answer "settled" and what
that answer permits, so that ledger-diff selection, the runner's skip gate and a successor's
`detect()` cannot drift apart.

## Terms

- **Settled**: the selection view's answer that a run must not apply this migration again. It is
  *not* the same claim as "this migration's record says applied"; it is the conjunction below.
- **Recorded applied**: the migration's authoritative ledger partition holds a `success` record for
  its `migration_id` (`LEDGER.SETTLED_RESULT`; `registry.migration_settled`).
- **Adoption projection**: the ids an unsettled ledger-adoption migration will record as `success`
  when it applies (`registry.pending_adoption_ids` → `BaseMigration.adoption_settled_ids`).
- **Predecessor**: the shipped migration a successor replaces, declared as
  `BaseMigration.predecessor_id`.

## The contract

```
settled(m) =
    (recorded_applied(m) or adoption_projection_contains(m.id))
    AND predecessor_outcome_settles(m)

predecessor_outcome_settles(m) =
    m.predecessor_id == ""                       -> true
    registry cannot resolve m.predecessor_id     -> true
    otherwise -> recorded_applied(predecessor) or adoption_projection_contains(predecessor.id)
```

Consumers, all reaching the same predicate:

| Consumer | Entry point |
|---|---|
| Ledger-diff selection | `MigrationRegistry.get_applicable` → `registry._settled_in_view` |
| Public projection (a successor's `detect()` gate, diagnostics) | `registry.settled_in_selection_view` |
| Runner skip gate, main checkout and `.worktrees/*` | `BaseMigration.reselect_when_recorded` → `registry.predecessor_outcome_settled` |

## Invariants

1. **Success-only settlement.** A `skipped` or `failed` record never settles a migration; it stays
   re-evaluable and `detect()` decides.
2. **A successor's own record cannot prove its repair ran.** First adoption settles an id from the
   recorded version rather than from a run, so the successor's `success` is necessary but not
   sufficient: the predecessor's outcome must also prove the repair happened.
3. **`detect()` is the only trigger of `apply()`.** The rule changes who is re-evaluated, never what
   is re-applied. A re-evaluation that finds nothing to do writes nothing.
4. **A held `success` is never downgraded to `skipped`.** The read view keeps the last record per id,
   so downgrading would claim a completed repair never ran (`runner._record_ledger_result`).
   A held `failed` may become `skipped`: a retry that finds nothing to do resolves the failure.
5. **One rule, one home.** The predicate lives in `registry._settled_in_view` (with
   `_predecessor_outcome_settled_in_view`); no caller restates it.
6. **No schema, manifest or frozen-module change.** The rule reads existing records; it adds no
   ledger field, changes no `target_version` or manifest slot, and edits no shipped migration module
   (DIRECTIVE_044).

## Out of scope

- The read surfaces (`migrate ledger`, `upgrade --dry-run --verbose`) report what the ledger says,
  not what the selection view concludes; a successor can read `applied` while still being
  re-evaluated. That split is recorded as a residual in ADR `2026-10-17-1`.
- A predecessor that recorded a real "not applicable" `skipped` leaves its successor re-evaluated
  once per run. Accepted, documented, and the price of not trusting an adoption stamp.
