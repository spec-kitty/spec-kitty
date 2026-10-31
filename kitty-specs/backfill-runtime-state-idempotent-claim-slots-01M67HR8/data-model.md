# Data Model — Backfill runtime state on a slug-identified legacy Mission

The Mission introduces no new persisted entity and no schema change. It changes which value
one existing field of one existing record carries at migration time. This document records
the two identities involved, their invariants, and the state transitions of the migration so
a reviewer can check the fix against the model rather than against the diff.

## Entities

### `MissionMeta` (`meta.json`) — existing

| Field | Type | Meaning here |
| --- | --- | --- |
| `mission_slug` | `str` | The Mission's directory name; also the `mission_slug` on every event row. |
| `mission_id` | `str \| None` | The canonical identity. Post-WP05 Missions carry a ULID. **Legacy Missions carry either nothing or their own slug** — the shape in #6689. |

### Declared mission id (derived value, new *name* for an existing fact)

`_declared_mission_id(read_dir) -> str | None`: the `mission_id` `meta.json` declares, or
`None` when it declares none. Validation/invariants:

- Read only from the **PRIMARY** leg (`read_dir`), never the COORD write leg (#2966 part-1).
- A malformed or absent `meta.json` degrades to `None` (`load_meta(..., on_malformed="none")`);
  it never raises from this seam.
- A slug-valued id is **not** reinterpreted as absent (C-002). If `meta.json` says the id is
  the slug, the id *is* the slug.

### Seed namespace root — existing, unchanged

`_mission_id(read_dir) -> str`: `declared or read_dir.name`. Used **only** as the input to
`_seed_id(mission_id, wp_id, field)`. Its value must not change for any corpus, because it
is the deterministic-id input.

### Seed carrier row (`StatusEvent`) — existing

| Field | Post-fix value | Invariant |
| --- | --- | --- |
| `event_id` | `deterministic_ulid(f"{namespace}|{wp_id}|claim")` | Unchanged from pre-fix for every corpus shape (idempotency). |
| `mission_slug` | the Mission directory name | Unchanged. |
| `mission_id` | the **declared** mission id, or `None` when undeclared | Must equal the value `read_event_stream` re-derives for this row. |
| `policy_metadata` | the un-migrated claim slots | Unchanged (already-migrated suppression still applies). |
| `at` | anchor, or the strict per-WP floor | Unchanged. |
| `actor` | `migration:backfill_runtime_state` | Unchanged — the provenance predicate. |

### `InnerStateChanged` seed annotation — existing

Carries no `mission_id` field at all, so it has no round-trip asymmetry and is untouched.

## Invariants

- **INV-1 (round-trip parity).** For every seed row the migration mints,
  `read_event_stream(feature_dir)` must return an event whose `to_dict()` equals the row the
  builder computed, modulo the tolerances the verifier already allows (an older `at`, the
  pre-#2985 full-payload carrier, a superseded subtask seed). This is the invariant #6689
  broke, and the one FR-001/FR-002 restore.
- **INV-2 (namespace stability).** Changing the declared id must never change a seed
  `event_id`. Ids are the idempotency key; a changed id means a duplicate row on the next run.
- **INV-3 (no fabricated identity).** The envelope never carries an id the Mission does not
  declare. Undeclared stays undeclared.
- **INV-4 (no reader change).** `status/store.py`'s resolution stays byte-identical
  (NFR-004): the fix makes the writer agree with the reader, never the reverse.
- **INV-5 (fail-closed preserved).** No tolerance is added; every fail-closed class still
  aborts (FR-006, FR-007, NFR-003).

## State transitions of the migration (per Mission)

```
un-seeded
  └─ backfill_runtime_state()  ──► seeds-written
        (idempotency: ids already on disk are skipped)
                                   │
                                   ├─ verify_backfill() ok ──► cutover flips status_phase (snapshot authority)
                                   ├─ verify_backfill() not ok ──► status_phase untouched, exit 1  (#6689 was stuck HERE, forever)
                                   └─ frontmatter already stripped ──► MigrationOrderingError (fail-closed)
```

The only transition this Mission changes is the middle one: for a slug-identified Mission the
`not ok` branch becomes `ok`, and the arrow into `seeded-written` becomes a no-op on the
second run. The two fail-closed edges are unchanged.

## Data migration / compatibility

No data migration. Existing rows are immutable and remain valid (research Decision 5): a
pre-fix row that lacks the field reads back as the declared identity, which is exactly the
new expectation. Nothing needs rewriting, and nothing can be rewritten on an append-only log.
