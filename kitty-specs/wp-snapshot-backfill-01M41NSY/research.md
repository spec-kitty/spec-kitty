# Research: wp-snapshot-backfill

## R-01 Reducer model (decision: do not change)

- Decision: keep the reducer; repair the log.
- Rationale: ADR `docs/adr/3.x/2026-06-07-3-wp-lane-fsm-genesis-and-finalize-clobber.md` (lines 48-66) defines a `genesis` WP as having no lane events and never materialising; `status/models.py` `UNINITIALIZED` is the read-time marker. `WPCreated` is a lifecycle event (`status/lifecycle_events.py`), not a lane transition. The Lamport reducer lives in the external `spec_kitty_events` package.
- Alternatives rejected: materialising event-less WPs (contradicts ADR, needs an upstream package change, would make files a second authority).

## R-02 Root cause

- `bootstrap_canonical_state` (`status/bootstrap.py`) is called only by `finalize-tasks` and writes through the transactional, topology-routed writer. Coord-topology Missions therefore wrote `planned` seeds (and later lifecycle events) to a coordination branch that was never projected into the dossier commit landed on `main`. No coordination branch for these Missions survives locally or on the remote.
- Prevention of recurrence for new Missions is out of scope (consolidation/dossier projection); the corpus parity gate (FR-009) detects regrowth on this repository.

## R-03 Writer seam (decision: extend `migration/backfill_runtime_state.py`)

- `backfill_runtime_state` imports `append_event_stream_atomic_verified` from `status._unsafe` (line ~111), takes `resolve_status_lock_root` + `feature_status_lock` (~1417), filters seeds by event ids already on disk (~1439), returns on dry-run (~1460), appends atomically (~1465). Deterministic ids via `_seed_id` (~308, `deterministic_ulid`). Actor `migration:backfill_runtime_state` (~120).
- A new module importing `_unsafe` would add entries to `_unsafe.ALLOWED_CALLERS` (baseline in `test_status_unsafe_allowlist.py`) and the writes-gate ledger (`test_status_events_writes_gate.py`). Decision: the pure planner is a new module; the write is a new function in `backfill_runtime_state.py` reusing the same lock/append.
- Surface: `canonicalize_feature_dir` for the write target; `runtime_state_cutover._resolve_primary_home_or_degrade` documents the degrade-on-deleted-coordination-branch behaviour.

## R-04 Forced done

- `status/wp_state.py` (~178-196): an edge absent from the matrix passes with `force=True`, non-empty actor and reason. The unforced `done` guard needs `DoneEvidence.review` (~579-594). Seeds use `force=True`, `reason` citing the evidence, `evidence=None`; FR-011 pins this with a `validate_transition` test and checks `.evidence` readers (acceptance, `status/zeitgeist_bridge.py` ~284-289) tolerate `None`.

## R-05 Archive freeze

- `kitty-specs/` is in `_ARCHIVE_ROOTS` (`tests/architectural/test_archive_root_byte_identical.py` ~96-101). Additions (new `status.events.jsonl`) are allowed; modifications of baseline files need `_OPERATOR_SANCTIONED_CORRECTIONS` entries with a dated operator-decision comment (precedent: #5258 runtime-state backfill entries ~170-200).

## R-06 Terminal evidence in the corpus

- Of the disagreeing Missions, `accepted_at` is present on 12 and `merged_at` on 7. Others landed on `main` as mission-dossier commits; their evidence (merged PR / dossier commit) is recorded per Mission in `evidence-manifest.yaml` by WP03, or the Mission stays `planned` when unknown.

## R-07 Existing overlap

- `tests/specify_cli/migration/test_dogfood_corpus_backfilled.py` already walks the corpus for runtime-state cutover; the new parity gate sits beside it.
- **Merge-order dependency on PR #5581 (corrected).** This mission imports nothing from #5581 (C-004), but the two are not independent at merge time. #5581's `test_the_ceiling_is_not_stale` pins its ceiling at 52 and requires measured >= ceiling. After this drain the measured residue is about 8, so whichever PR lands second goes red until its ceiling is lowered (or retired). Whoever lands second owns that edit. Recommendation: retire #5581's count ratchet in favour of this mission's set-based parity gate (`test_corpus_wp_snapshot_parity.py`), which is stricter (per-WP set equality, permanent carve-outs listed with reasons, live-coordination Missions skipped and named) and cannot be satisfied by a count that merely stays under a ceiling.

## Adversarial dispositions (post-spec squad)

| Finding | Disposition |
|---|---|
| P0 archive freeze contradicts drain | Folded: C-005 rewritten to sanctioned corrections |
| P0 materialize refuses on deleted coord branch (#5286) | Folded: edge case; in-process reducer on primary dir; fixture test |
| P1 forced-done evidence | Folded: FR-011 |
| P1 evidence fields unverified | Folded: verified counts (R-06) |
| P1 count-based SC fakeable | Folded: set-based FR-009 / SC-001 |
| P2 gate overlap | Folded: gate beside dogfood test |
| P2 idempotence mechanism | Folded: FR-010 deterministic ids |
| P2 interleaving with runtime backfill | Folded: FR-012 |
