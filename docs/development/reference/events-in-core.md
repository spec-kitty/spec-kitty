---
title: Events in core
description: 'Contributor rules for writing and reading event logs in core today, what not to do, and how to adopt a new spec-kitty-events release without a red nightly.'
doc_status: active
updated: '2026-10-28'
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
[2026-10-14-1](../../adr/4.x/2026-10-14-1-event-native-core-one-canonical-event-writer.md)):
a resident Java write service per repository behind the Python EventBridge port (ADR
[2026-10-22-1](../../adr/4.x/2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md)).
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
  `status.events.jsonl` outside `status/store.py` and its ledgered sites, and
  `tests/architectural/test_event_log_writes_gate.py` does the same for every other log
  (see [Appending to an event log (interim)](#appending-to-an-event-log-interim)).
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
- **The migration ledger's append is locked, and one selection rule is structural.**
  `MigrationLedger.append` / `append_many` hold
  `.kittify/migrations/<ledger file name>.lock` (a `kernel.locks.machine_file_lock`
  sidecar in the IGNORED per-clone surface, bounded at 30 s) across their
  read-modify-write, so two `upgrade`/`migrate` runs on one checkout cannot lose a
  record; a lock that never frees raises `MigrationLedgerLockTimeoutError` and
  appends nothing. Selection is ledger-diff **plus** the `runs_first` structural
  reselection: a recorded migration whose `structural_detect` fires is re-selected
  (a pulled `metadata.yaml` or a merge can revive the old state), while `detect()`
  stays the pre-`apply()` idempotency guard. See
  [ADR 2026-10-17-1](../../adr/4.x/2026-10-17-1-explicit-migration-ledger.md), Amendments
  2026-10-20 and 2026-10-30.

## Appending to an event log (interim)

Until the Java write service owns a log (#6193), an append to any event log other than
`status.events.jsonl` and `canonical-events.jsonl` goes through one door,
`kernel.event_log_append` (#6606). Those two keep the Mission status lock and the
`status.store` primitives.

- **Call `append_event_log_lines(path, lines)`.** Pass complete serialized rows without a
  trailing newline; the door adds the framing. You keep serializing your own row bytes:
  the door checks framing, never content, because the write service is the validation
  authority (operator ruling of 2026-10-25 on #6117).
- **The lock contract.** The lock is anchored on the log, or on the family directory for
  one-file-per-record logs (`kitty-ops/<op>.jsonl`). It lives at
  `<git-common-dir>/spec-kitty-locks/event-logs/<sha256[:32]>.lock`, so every worktree of a
  repository shares it; outside a git repository it is `<anchor>.event-log.lock`. The wait
  is bounded (`EVENT_LOG_LOCK_TIMEOUT_S`, 10 s). Under the lock, a log whose last byte is
  not LF is refused, then the whole unit is written in one `O_APPEND` write and fsynced.
  A new log is created with mode `0o666` less the umask; the `kitty-ops/` Op records
  (per-Op trails, `ops-index.jsonl`, `op-closures.jsonl`) are created owner-only (`0600`).
  The Java writer takes the same lock files (ADR 2026-10-22-1 D-4). One exception to the
  refusal: the glossary contract writer repairs a torn tail under the lock, moving the
  fragment to a `.torn` sidecar and retrying; repair is a per-log policy above the lock.
- **Refusals are `OSError`s with a `code`:** `EVENT_LOG_TORN_TAIL`,
  `EVENT_LOG_LOCK_TIMEOUT`, `EVENT_LOG_LOCK_UNAVAILABLE` (git cannot be invoked, so the
  append refuses rather than lock where other writers do not), `EVENT_LOG_SYMLINK` and
  `EVENT_LOG_SHORT_WRITE`. A caller that already treats an I/O error as non-fatal keeps
  doing so; decide deliberately if yours should surface it. Each message ends with
  `Error code: <CODE>.`, so an operator can quote it.
- **A torn tail, per log.** A crash in the middle of an append can leave a last line with
  no trailing newline. Only the glossary logs repair it: the contract writer moves the
  fragment to a `.torn` sidecar (quarantine) and retries. Every other log refuses with
  `EVENT_LOG_TORN_TAIL` until the bytes are cut by hand: the run journal
  (`run.events.jsonl`, so `spec-kitty next` stops for that run), `decisions.events.jsonl`,
  `mission-events.jsonl`, the `kitty-ops/` trails, index, closure spine, lifecycle and
  propagation-error logs, the policy audit log, the mission archive log and the charter
  encoding provenance log. Writers that already treat an I/O error as non-fatal (the Op
  index, the propagation-error log, the encoding provenance log) log a warning and drop
  the row instead. The repair: keep a copy of the file, then truncate it to its last
  newline. A short write, or `ENOSPC` after a partial write, does not leave a torn tail:
  the door cuts the log back to its size before the write, under the lock, then raises.
- **When git cannot run, appends refuse.** The lock path needs the git common dir. When
  git cannot be invoked, including when it rejects the checkout for "dubious ownership"
  (`safe.directory`), every append refuses with `EVENT_LOG_LOCK_UNAVAILABLE`. Whether
  to fall back instead is an operator decision still open on PR #6681; until it is made,
  make git runnable in the checkout and retry.
- **One lock per name, not per file.** The lock digest is taken over the anchor's
  resolved, `normcase`-d path. Two hard-linked names of one file, or two spellings that
  differ only in case on a case-insensitive macOS file system (`normcase` does not fold
  case there), get two locks and do not exclude each other. Write a log through one name.
- **A check that must see the current file** (an identity check, "already closed") goes in
  the `precondition` callback so it runs under the lock; `event_log_lock(path)` holds the
  lock for a read-modify-write such as the glossary contract write.
- **The gate.** `tests/architectural/test_event_log_writes_gate.py` ledgers every caller of
  the door and of `spec_kitty_events.persistence.append_event` (under any alias) by module
  and function, fails a raw write whose path it resolves to a named log or any other
  `.jsonl`, and pins raw writes whose path reads like a log. A new caller is added to its
  ledger in the change that adds it. It cannot see a path that arrives only as a parameter
  whose callers disagree, a path built from a glob, or an imported constant with a neutral
  name, so do not lean on it: use the door.
- **Retirement.** Each log's interim append, and its ledger entry, is deleted when the
  write service takes that log over whole (#6193); the module goes with the last one.
  Do not build new behaviour on it.

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
   `tests/status tests/consolidation tests/migration tests/contract/spec_kitty_events_consumer tests/contract/test_mission_status_conformance.py tests/next tests/decisions tests/specify_cli/decisions tests/specify_cli/migration tests/ci/test_reducer_lock_census.py tests/upgrade/test_mission_corpus_recovery.py`.
   This is the targeted blast radius of the bump, not a whole-repo run.
5. **A/B any reducer change.** Run the reducer-pinning tests on the same tree with the
   old and new versions, and write the delta in the PR body. A changed verdict is a
   decision for the reviewer, never an `xfail` added after the PR lands.
6. **Check the Java read API on every bump.** The conformance manifest records the installed
   version, and `ManifestCouplingTest` holds the service's `StatusReducer.PORTED_EVENTS_VERSION`
   equal to it, so every version move needs both: regenerate the corpus
   (`.venv/bin/python -m tests.contract._mission_status_conformance --write`) and advance
   `PORTED_EVENTS_VERSION` with a port-review paragraph in its Javadoc, even when nothing changed.
   If the release touches `diary.reduce_parsed`, the review is a real port, and a behaviour change
   needs a conformance golden that exercises it.
7. **Never import a private symbol** (`spec_kitty_events._*` or `module._name`). If you
   need one, ask upstream for a public API first.

## See also

- [Event ledger writers and readers](../../architecture/event-ledger-writers-and-readers.md): the full map and gap table.
- [Status model](../../architecture/status-model.md): lanes, guards and CLI commands.
- [Contract pinning](../how-to/contract-pinning.md) and [Consumer census](../how-to/consumer-census.md).
- `spec-kitty-events` `docs/api/ledger-write-contract.md`: the `persistence.append_event` contract.
