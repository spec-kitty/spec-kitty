---
title: Consumers of the optional Lamport clock
description: Every core site that reads or writes Event.lamport_clock or the spec-kitty-events ordering keys, with a verdict and the test that pins it, following spec-kitty-events 11.0.
doc_status: active
type: reference
audience: docs/context/audience/internal/maintainer.md
updated: '2026-10-31'
related:
- docs/development/reference/events-in-core.md
- docs/changelog/CHANGELOG.md
---

# Consumers of the optional Lamport clock

`spec-kitty-events` 11.0.0 made `Event.lamport_clock` optional and changed the status
ordering key. This page records what core does with both, so the next contract move does
not have to re-run the audit from scratch. Tracking issue: #6414 (parent epic #6411).

## The contract this page is written against

Pinned floor: `spec-kitty-events>=11.3.0,<12` (`pyproject.toml`). Read from the installed
package, not from the issue that requested the audit:

| Surface | Behaviour |
| --- | --- |
| `spec_kitty_events/models.py` — `Event.lamport_clock` | `Optional[int]`. The field description says it plainly: "An envelope without it is unclocked and orders **before** clocked ones." `0` is a *real* clocked position, not "no clock". |
| `spec_kitty_events/ordering.py` — `canonical_order_key` | `(1 if clocked else 0, clock or 0, utc_timestamp_iso, event_id)` — the one mixed-stream key. `node_order_key` is the storage-adapter sibling keyed on `(clocked, clock, node_id, event_id)`. |
| `spec_kitty_events/status.py` — `status_event_sort_key` | Delegates to `canonical_order_key`. It is a **4-tuple**, not the 3-tuple older integrations unpack. |
| `spec_kitty_events/merge.py`, `work_replay.py` | `merge` raises on an unclocked event; `work_replay` refuses one (`work replay requires lamport_clock`). |
| `spec_kitty_events/status.py` — `reduce_status_events` | The only consumer that sorts with the 4-tuple key *and* groups by `(wp_id, lamport_clock)`, treating an unclocked event as its own singleton group. |
| `spec_kitty_events/strict.py` | The strict 14-key envelope requires every key present, nullable ones as an explicit `null`. |

**Direction note.** The issue that prompted this audit states that unclocked envelopes
sort *after* clocked ones. The released contract sorts them *before*: the leading
component is `1` only when the event is clocked. Where the two disagree, this page and the
code follow the installed package.

## What core does not do

- **No caller of the ordering surface.** `status_event_sort_key`, `canonical_order_key`,
  `node_order_key` and `total_order_key` have no call site in `src/`; the only mention of
  `canonical_order_key` in core is the migration docstring that explains *why* the
  migration emits an unclocked row (below). The Java read API names
  `status_event_sort_key` in a comment recording that it is not ported.
- **No `merge` / `work_replay` use.** Core never imports `spec_kitty_events.merge` or
  `spec_kitty_events.work_replay`, so the two functions that *reject* unclocked input are
  unreachable from the CLI.
- **The CLI's lane readers are wall-clock.** `materialize_snapshot` and the lane-state
  reads fold events through the diary reducer (`spec_kitty_events.diary.reduce_parsed`),
  ordered by `(at, event_id)`. Room to make the status log Lamport-primary belongs to
  #6609 (parked post-GA) and is deliberately out of scope here.

## Consumers, and why each one is safe

Proofs live in `tests/status/test_optional_lamport_clock_consumers.py` unless a path is
named.

| Site | Kind | Verdict | Proof |
| --- | --- | --- | --- |
| `src/specify_cli/migration/mission_state.py` | Producer (`teamspace_dry_run`, `_build_teamspace_envelope`, `_TeamspaceEnvelope`) | Unaffected. Source rows are read into `StatusEvent` (which carries no clock), sorted by `(at, event_id)`, and re-emitted with a synthesized `lamport_clock` equal to their 1-based position, so every emitted envelope is clocked and the source clock is discarded rather than mixed. | `test_dry_run_emitted_envelopes_are_clocked_by_position` |
| `src/specify_cli/status/lifecycle_events.py` | Producer (`_build_envelope`) | Already unclocked. The live lifecycle appender writes no `lamport_clock` key at all, which under 11.x reads as unclocked — the contract's "no causal order recorded". | `test_live_lifecycle_envelope_carries_no_clock` |
| `src/specify_cli/status/migrate_lifecycle_envelope.py` | Producer (upgrade migration) | **Was the defect.** It stamped `lamport_clock: 0`, a clocked position the legacy row never recorded, so the row sorted after every never-migrated row of the same log. It now writes `None`. See [the changelog](../../changelog/CHANGELOG.md). | `tests/status/test_optional_lamport_clock_migration.py` |
| `src/specify_cli/status/reducer.py` | Reader (`materialize_snapshot`, `reduce`) | Unaffected. `materialize_snapshot` reduces through the diary reducer, which orders by `(at, event_id)` and never reads a clock; `StatusEvent` has no `lamport_clock` field, so a foreign clock on a row is ignored rather than promoted. | `test_mixed_stream_materializes_identically` |
| `src/specify_cli/status/event_log_merge.py` | Reader/rewriter (`merge_event_payloads`) | Unaffected. It orders by `(at or timestamp, event_id)` and keeps whole row dicts, so it neither reinterprets nor drops a clock. | `test_merge_event_payloads_ignores_clock` |
| `src/specify_cli/status/store.py` | Reader (`read_events`, `read_events_raw`) | Unaffected. Rows become `StatusEvent`, which has no clock field; raw rows are handed to the dependency unchanged. | `test_mixed_stream_materializes_identically` |
| `src/specify_cli/state/contract.py` | On-disk path inventory | Unaffected. The `lamport_clock` / `legacy_lamport_clock` surfaces it declares are the retired hosted-sync files `~/.spec-kitty/clock.json` and `~/.spec-kitty/events/lamport_clock.json` (#114), not the envelope field. | `test_state_contract_lamport_rows_are_retired_paths` |
| `src/specify_cli/retrospective/lifecycle_events.py` | Producer (separate local clock) | Unaffected. The retrospective log's own `lamport` field (default `0`) is not `Event.lamport_clock`; `_next_lamport` already guards with `isinstance(lp, int)`. | `test_retrospective_clock_reads_tolerate_null` |
| `src/specify_cli/retrospective/summary.py` | Reader (separate local clock) | Handles `None`. Every read is `obj.get("lamport", 0)` followed by an `isinstance(..., int)` guard, so an explicit `null` behaves as absent. | `test_retrospective_clock_reads_tolerate_null` |
| `src/specify_cli/decisions/models.py`, `decisions/service.py`, `orchestrator_api/decision_verbs.py` | Response field `event_lamport` | Unaffected. Typed `int | None`, only serialized, never compared or unpacked. | `test_decision_event_lamport_is_an_optional_passthrough` |
| `tests/_factories/coord_mission.py` | Test probe (`_row_lamport`) | Already tolerant. Returns `None` for an absent or non-integer clock. | `test_test_probe_tolerates_missing_clock` |

## Residual

- A project that ran an older release of the migration already carries
  `lamport_clock: 0` rows. The migration deliberately does **not** rewrite them: re-running
  it must stay a byte-identical no-op on an already-migrated file, and no core reader uses
  the key for ordering. A future Lamport-primary reader (#6609) has to decide what an
  already-stamped `0` means; #6414 does not.
- The TeamSpace dry-run envelope keeps a required `int` for `lamport_clock` because it
  must emit the 5.0.0 replay envelope, and its builder always synthesizes the value. It is
  a local shadow model by design (it carries `aggregate_type` / `repo_slug`, which the wire
  `Event` does not), so it is not evidence that core "reads the clock as an int".

## Keeping this page honest

`tests/status/test_optional_lamport_clock_consumers.py` scans `src/` for
`lamport_clock`, `status_event_sort_key`, `canonical_order_key`, `node_order_key`,
`total_order_key` and `work_replay`. Every file it finds must appear in the table above; a
new consumer therefore fails the suite until it is audited and added here. A moved line
does not fail it.
