---
title: Events in core
description: 'Contributor rules for writing and reading event logs in core today, what not to do, and how to adopt a new spec-kitty-events release without a red nightly.'
doc_status: active
updated: '2026-10-22'
audience: docs/context/audience/internal/maintainer.md
type: reference
related:
- docs/architecture/event-ledger-writers-and-readers.md
- docs/architecture/status-model.md
- docs/development/how-to/contract-pinning.md
- docs/adr/4.x/2026-10-14-1-event-native-core-one-canonical-event-writer.md
---

# Events in core

> **When you need this page.** Your change appends to an event log, reads one, or bumps
> `spec-kitty-events`. The map of every writer and reader, and the gaps against the
> ADRs, is in [Event ledger writers and readers](../../architecture/event-ledger-writers-and-readers.md).
> This page is the short version: what to call, what not to do.

The target is one canonical event writer (ADR
[2026-10-14-1](../../adr/4.x/2026-10-14-1-event-native-core-one-canonical-event-writer.md)).
It does not exist yet. Until it does, follow the rules below so you do not add a writer
that the migration has to remove later.

## Writing events

| You want to record | Call | Not |
|---|---|---|
| A work package lane transition | `emit_status_transition_transactional` (`coordination/status_transition.py`); it falls back to the flat shell `emit_status_transition` (`status/emit.py`) for a Mission without coordination topology | building a `StatusEvent` and appending it yourself |
| An inner-state annotation | `emit_inner_state_changed` (`status/emit.py`) | a raw row in `status.events.jsonl` |
| A glossary fact | `glossary.events.append_event` (`src/glossary/events.py`), which writes through `spec_kitty_events.persistence.append_event` | a hand-built dict |
| A new kind of fact | Ask first. The fact needs a model in `spec-kitty-events` before core writes it (ADR 2026-10-14-1 D-4). Write it through `spec_kitty_events.persistence.append_event` | a new `*.jsonl` file with a core-owned row shape |

Rules:

- **Never `open(path, "a")` an event log.** A plain append has no lock and no torn-tail
  check. `tests/architectural/test_status_events_writes_gate.py` rejects any write to
  `status.events.jsonl` outside `status/store.py` and its ledgered sites. Other logs
  have no gate yet, which is a gap to close, not a license.
- **Never import from `specify_cli.status._unsafe`.** Its `ALLOWED_CALLERS` list is
  shrink-only; adding a module fails `test_status_unsafe_allowlist.py`.
- **Never add a new `canonical-producer-exempt` marker or a new local envelope.**
  Sixteen markers remain in `src/`; the migration removes them.
- **Serialize status rows with `store.serialize_event_line`**, the one authority for the
  on-disk row shape. Do not `json.dumps` a status row yourself.
- **Keep `prepare_transition` pure.** It does no writes, locks, git or fan-out
  (`status/transition_pipeline.py`); git-derived values such as the `lane_head` stamp
  come in through an injected probe.
- **A side effect that reacts to an event is a consumer, not a new line in a shell.**
  Today the shells still run commits inline; do not add more. The produce seam
  `status/adapters.py` is where a transport registers a handler. Open-core registers none,
  so every `fire_*` is a no-op, and nothing hosted belongs in this repository.
- **Call the state files by their names.** The migration ledger
  (`.kittify/migration-ledger.jsonl`, `upgrade/ledger.py`) and the activation ledger
  (`.kittify/charter/activation.yaml`) are state ledgers, not event logs. Never write
  bare "the ledger".

## Reading events

- **Lane state:** `status.lane_reader.get_wp_lane` / `get_all_wp_lanes`, or
  `status.reducer.materialize_snapshot` for a whole snapshot. Never parse
  `status.events.jsonl` with your own `json.loads` loop and never take "the last
  `to_lane` in the file": file order is not lane order.
- **Ordering is wall clock.** Every reducer-based CLI lane read (`reduce`, `materialize_snapshot`, `materialize`) reaches `spec_kitty_events.diary.reduce_parsed`,
  which orders by the writer's `at`, then `event_id`, with a lift that sorts a departure
  from `approved` after its approval (#4941). CLI rows carry no Lamport clock. Do not
  write code or docs that assume Lamport ordering on the status path.
- **Streaming:** `status.tail_reader` (and `spec-kitty events tail`) read raw bytes with a
  cursor; use them for a change feed, not for lane state.
- **Mission Status Read API:** a consumer reads it across its contract
  (`contracts/mission-status/openapi.yaml`), never this log or CLI internals.

## Adopting a new `spec-kitty-events` release

The library ships reducer behaviour changes in **patch** releases, and three recent bumps
(10.4.0 in September, 10.4.2 and 10.4.6 in October) went red on `main` in tests the bump PR
never ran (the history is in the
[architecture page](../../architecture/event-ledger-writers-and-readers.md#why-event-changes-are-risky)).
Do these in one PR:

1. **Read before you bump.** Read the library's `CHANGELOG.md`, `COMPATIBILITY.md` and its
   `docs/changelog/*diary*` entries. Flag any change to a reducer, a validator, the
   envelope or a symbol core imports.
2. **Bump with the repo tooling.** `uv lock --upgrade-package spec-kitty-events`; update the
   `pyproject.toml` range if the floor moves (pinned by `tests/architectural/test_pyproject_shape.py`)
   and `.kittify/release/shared-package-compatibility.json`. Follow
   [Contract pinning](../how-to/contract-pinning.md).
3. **Commit the envelope snapshot in the same PR.**
   `uv run python scripts/snapshot_events_envelope.py --force`, then run
   `tests/contract/test_events_envelope_matches_resolved_version.py`.
4. **Run the event consumers, including the ones a lock-only change does not select per PR**, and record
   the counts in the PR:
   `tests/status tests/consolidation tests/migration tests/contract/spec_kitty_events_consumer tests/next tests/decisions tests/specify_cli/decisions tests/specify_cli/migration tests/upgrade/test_mission_corpus_recovery.py`.
   This is the targeted blast radius of the bump, not a whole-repo run.
5. **A/B any reducer change.** Run the reducer-pinning tests on the same tree with the
   old and new versions, and write the delta in the PR body. A changed verdict is a
   decision for the reviewer, never an `xfail` added after the PR lands.
6. **Check the Java read API.** If the release touches `diary.reduce_parsed`, the service's
   `StatusReducer.PORTED_EVENTS_VERSION` needs a port review, and a behaviour change needs
   a conformance golden that exercises it.
7. **Never import a private symbol** (`spec_kitty_events._*` or `module._name`). If you
   need one, ask upstream for a public API first.

## See also

- [Event ledger writers and readers](../../architecture/event-ledger-writers-and-readers.md): the full map and gap table.
- [Status model](../../architecture/status-model.md): lanes, guards and CLI commands.
- [Contract pinning](../how-to/contract-pinning.md) and [Consumer census](../how-to/consumer-census.md).
- `spec-kitty-events` `docs/api/ledger-write-contract.md`: the `persistence.append_event` contract.
