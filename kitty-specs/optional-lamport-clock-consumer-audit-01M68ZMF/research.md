# Discovery Findings — Optional Lamport clock consumer audit

Mission: `optional-lamport-clock-consumer-audit-01M68ZMF` (issue #6414, parent epic #6411).
Branch: `issue-6414-optional-lamport-clock-consumer-audit`. Grounded on `origin/main` @ `dfe9efb0e8`.

## D1 — The contract, as installed (not as the issue body states it)

Decision: treat `spec_kitty_events` 11.3.0 (the pinned floor, `pyproject.toml:80`) as the
authority for ordering semantics, and record that the issue body's direction claim is
inverted.

Evidence (`<venv>/site-packages/spec_kitty_events/`):

- `models.py:120` — `lamport_clock: Optional[int] = Field(None, ge=0, ...)`, description:
  "An envelope without it is unclocked and orders before clocked ones."
- `ordering.py:41` — `canonical_order_key(event) -> (1 if clocked else 0, clock or 0,
  utc_timestamp_iso, event_id)`; `node_order_key` is the storage-adapter sibling keyed on
  `(clocked, clock, node_id, event_id)`.
- `status.py:748` — `status_event_sort_key` delegates to `canonical_order_key`; it is a
  4-tuple now, not the 3-tuple the issue body describes.
- `merge.py:45` — raises `Cannot merge unclocked event ...`; `work_replay.py:84` raises
  `work replay requires lamport_clock (LW-10)`.
- `status.py:839` / `:887` — `reduce_status_events` is the only consumer that sorts with
  the 4-tuple key *and* groups by `(wp_id, lamport_clock)`, with "unclocked = singleton".
- `strict.py` — the strict profile requires all 14 envelope keys present, nullable ones as
  explicit `null`.

Consequence: the issue body says unclocked sorts *after* clocked; the released contract
sorts unclocked *before* clocked (leading `0`). The audit document states the real
direction and cites `ordering.py`; the issue thread keeps the historical wording.

## D2 — Core imports none of the ordering surface

Decision: the audit record is the deliverable; no core module re-implements the key.

Evidence (`git grep` over `src/` at `dfe9efb0e8`):

- `status_event_sort_key`: 0 hits in `src/` (1 hit in a Java comment,
  `services/mission-status-api/.../StatusReducer.java:50`, and 1 in
  `.kittify/release/shared-package-compatibility.json`).
- `canonical_order_key`, `node_order_key`, `total_order_key`: 0 hits in `src/`.
- `spec_kitty_events.merge` / `spec_kitty_events.work_replay`: 0 imports in `src/`.

## D3 — Every core site that names `lamport_clock` or `lamport`, and its verdict

| # | Site | Kind | Verdict |
| --- | --- | --- | --- |
| 1 | `src/specify_cli/migration/mission_state.py:1018,1025` | producer (dry-run) | Unaffected: sorts source rows by `(at, event_id)` and re-synthesizes a strictly increasing `lamport_clock=index`, so every emitted envelope is clocked and ordered by wall clock. Any source clock is discarded. |
| 2 | `src/specify_cli/migration/mission_state.py:1241,1260,1283,1298,1338` | local shadow model `_TeamspaceEnvelope` | Unaffected: `lamport_clock: int` is required by construction because the only builder always supplies the synthesized index; deliberately not the wire `Event` model (documented at `:1222-1233`). |
| 3 | `src/specify_cli/status/lifecycle_events.py:304-324` | producer (live appender) | Unaffected and *already unclocked*: the 9-key legacy envelope never writes `lamport_clock`, so under 11.x these rows read as unclocked. |
| 4 | `src/specify_cli/status/migrate_lifecycle_envelope.py:199` | producer (migration) | **Defect**: stamps `lamport_clock: 0`, i.e. a *clocked* row at position zero, for a row that never recorded a clock. Fix = `None` (unclocked). |
| 5 | `src/specify_cli/state/contract.py:857-866,1118` | on-disk path inventory | Unaffected: declares retired `~/.spec-kitty/clock.json` / `events/lamport_clock.json` surfaces (hosted-sync residue, #114); not the envelope field. |
| 6 | `src/specify_cli/retrospective/lifecycle_events.py:148,203,265,362-386` | separate local clock | Unaffected: the retrospective log's own `lamport` field (default `0`), not `Event.lamport_clock`; `_next_lamport` already guards with `isinstance(lp, int)`. |
| 7 | `src/specify_cli/retrospective/summary.py:650-668,737-742` | separate local clock reader | Handles `None`: every read is `obj.get("lamport", 0)` followed by an `isinstance(..., int)` guard, so an explicit `null` behaves as absent. |
| 8 | `src/specify_cli/decisions/models.py:140,152`, `decisions/service.py`, `orchestrator_api/decision_verbs.py` | response field `event_lamport` | Unaffected: typed `int | None`, only serialized, never compared or unpacked. |
| 9 | `tests/_factories/coord_mission.py:1085-1092` | test probe | Already tolerates absence/non-int: returns `None`. |

## D4 — The read paths that actually see status rows are clock-agnostic

Decision: the CLI keeps its wall-clock `(at, event_id)` fold; the audit proves the
optional clock cannot change lane state rather than switching the fold (that is #6609).

Evidence:

- `status/reducer.py:205` — `reduce_parsed` (dependency diary reducer, wall-clock
  `_order_transitions`, no `lamport_clock`); `status/reducer.py:401` —
  `materialize_snapshot` uses `spec_kitty_events.status.reduce`, the diary reducer
  re-exported, *not* `reduce_status_events`.
- `status/store.py` / `status/models.py:523` — `StatusEvent` has no `lamport_clock`
  field; the reader never promotes a row's clock into core state.
- `status/event_log_merge.py:178` — merge orders by `(at or timestamp, event_id)` and
  keeps whole dicts, so no key is dropped or reinterpreted.
- Probe: appending a `lamport_clock` to alternating rows of the shipped
  `status_diary_every_lane.jsonl` replay fixture produces an identical
  `spec_kitty_events.status.reduce` state (verified locally before specifying).

## D5 — Fix boundary

Decision: exactly one production edit — the migration sentinel. Everything else is
documentation plus tests. Rationale: `canonical_order_key` places a clocked row after
every unclocked one, so a migrated legacy row currently sorts after strictly newer,
never-migrated rows of the same mission log, and would join one "concurrent" bucket with
every other migrated row for any consumer that groups by `(wp_id, lamport_clock)`. The
fix keeps migrated rows in their existing relative order (`None` still orders by
`timestamp`, then `event_id`) while removing the false claim of clockedness.

## Open questions (resolved in plan)

- Whether rewriting already-migrated `lamport_clock: 0` rows to `None` is in scope.
  Resolution: **no** — the migration must stay a byte-identical no-op on an
  already-migrated file (existing MIG2 assertion), and no core consumer reads lifecycle
  rows with the ordering key. Recorded as a documented residual in the audit doc.
- Where the audit lives. Resolution: `docs/development/reference/` beside the other
  consumer/contract references, indexed by the docs freshness gate.

## Pre-existing reds on main (not this mission's)

#6801 (`tests/migration/test_birth_cutover.py`, EVIDENCE_WINDOW_UNCOMPUTABLE),
#6816 (router gate false red on duplicate-named sibling job), #5927
(`tests/contract/test_mission_status_reality.py`), and #6798 (closed: legacy mission
discovery tests, fixed on main). Cited in the PR's `## Deferred`.
