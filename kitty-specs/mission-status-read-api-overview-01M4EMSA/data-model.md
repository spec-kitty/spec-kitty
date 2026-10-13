# Data model: Mission Status Read API, overview

Plan-level types of the framework-free `domain` and `application` packages. Names are binding for the two ports; fields follow the contract (`contracts/mission-status/schemas/*.yaml`) and are not redefined here.

## Domain values

| Type | Fields / rule |
|---|---|
| `MissionId` | ULID text (26 chars); `Mid8` = first 8 chars |
| `Lane` | enum of the contract `StatusLane` values; unknown lane in a lane row = malformed input |
| `StatusEvent` | `eventId`, `at` (text, compared as text), `wpId`, `fromLane`, `toLane`, `force`, plus the cancellation-provenance members `materialize_snapshot` projects; NO logical-clock field (the reduction never reads one) |
| `LifecycleEvent` | top-level `type` one of the seven lifecycle types; other well-formed objects are dropped |
| `Topology` | `single_branch`, `lanes`, `coord`, `lanes_with_coord`, or classified when absent (rule 3 of FR-006) |
| `MissionMeta` | `missionId`, `slug`, `friendlyName`, `displayNumber`, `missionType`, `targetBranch`, `topology?`, `createdAt`, `acceptedAt`, `mergedAt`, `discardedAt`, baseline record |
| `SupportedSchemaRange` | the single constant (min, max); Java test asserts equality with `manifest.json` |
| `LedgerLine` | one physical line, already decoded by the outbound codec (`adapter.out.filesystem.codec.LedgerLineDecoder`, a sub-package of the one outbound adapter): `lineNumber` (1-based), `rawLineSha256` (hex SHA-256 of the raw line bytes, the cursor invariant), `byteLength`, `kind` = `Status(StatusEvent)` / `Lifecycle(LifecycleEvent)` / `Annotation(wpId)` (an annotation row; the WP counts in `wpTotal` even with no transition, operator ruling 2026-10-11) / `Ignored` (a non-lane row the oracle skips: `event_name` starting `retrospective.`, a retrospective `type`, or an `event_type` key that is not one of the seven forwarded lifecycle types; any other object without usable lane fields, `{}` included, is `Malformed`; DD-84) / `Blank` / `Malformed(reason)` with reason `not_json`, `not_object`, `not_utf8`; the domain and application never see JSON text |
| `Projector` / `LeakClasses` / `ProjectionError` | `domain.projection`, the port of the oracle's `Projector`: a strict field is served clean, nulled when nullable, refused when not representable; a human field has host paths replaced by `[path]` and emails by `[email]`; `LeakClasses` is built by the caller from the patterns of `leak-patterns.json` (the domain does no I/O); `ProjectionError` carries the field name, never the value, and maps to the diagnostic code `projection_refused` and the same 500 Problem shape as rows L3a and L3b (plan.md section 13, Projection) |
| `LedgerStamp` | opaque to the application, compared only with `equals`: the adapter-defined identity (size, mtime, file key) plus `terminatedLength` and the SHA-256 of the last terminated line |

## Reduction

`StatusReducer(EventOrdering)`: the production ordering is `AtThenEventId` (code-point compare), injected at construction so the perturbation test (AC-8a) can supply a wrong one. Steps: dedup by `event_id` (first copy in FILE order wins, as `diary.reduce_parsed` does) -> sort -> (the cancellation-provenance and implementer projections instead run over sort-then-dedup, first copy in SORTED order wins, as `reducer.py` `_project_*` do; DD-81) -> rollback-aware fold -> annotation pass -> lane counts. `StatusSnapshot` carries per-WP lane, `lastTransitionAt`, counts. `OverviewDeriver` derives `lifecycleStatus` (discard rule first, then wpTotal rule), `progress` (equivalent of `compute_weighted_progress`), `blockedCount`, `lastActivityAt` (maximum by parsed instant, first on ties, served as the WP's own string), `topology`.

## Cursors

- `StreamCursor(offset, invariant)`: text `offset:invariant`; invariant = SHA-256 hex of the single most recently consumed physical line (empty digest at offset 0). Position is in physical bytes, so a CRLF ledger differs from its LF twin.
- `PageCursor`: `v1.` + URL-safe base64 (no padding) of `<createdAt>` LF `<missionId>`; stateless, at most 512 characters.

## Ports

Exactly the two seams of the operator's Architecture decision; no other named port.

Inbound (the HTTP adapter depends on this one only):

- `MissionStatusQuery`: `ProjectHeader project()`; `MissionPage missions(PageRequest)`; `ChangeBatch changesSince(StreamScope, Optional<StreamCursor>)`, which mirror the Python read port (#5532) one to one; and `Subscription subscribe(StreamScope, Optional<StreamCursor>)`, the continuous form of the same "changes since a cursor" capability (an operation of the one inbound port, with no Python counterpart because Python has no push stream). Typed exceptions: `MissionStatusUnavailable(code, diagnostic)` (also thrown by `subscribe` for the connect-time S2 rows, including `mission_dir_unreadable`, and used for a `ProjectionError` as `projection_refused`), `InvalidPageCursor`, `StreamRefused(code, kind)` (`kind` = `unknown_mission` for S1, or a cursor-refusal kind of the contract's 400/409 rows; always thrown before any subscription exists). `Subscription`: `StreamSignal next(Duration)` (blocking), `void close()`. `StreamSignal` is sealed: `Forwarded(ChangeBatch)`, `Truncated` (a `log-truncated` frame, no `id:`, then re-baseline), `Dropped(mid8)` (unscoped: Mission dropped, connection kept), `Closed(closure)` (scoped faults S3-S5, and `slow_consumer`), `Idle` (nothing within the wait; the adapter turns it into a heartbeat). `ChangeFeed` is package-private in `application` and not visible to adapters.

Outbound:

- `MissionEventSource`: `ProjectInputs projectInputs()` (config slug, metadata, branch name); `List<MissionRef> listMissions()` (sorted by the source, name order); `MissionMeta readMeta(MissionRef)`; `LedgerStamp stampLedger(MissionRef)` (cheap: stat plus a bounded read of the last physical line); `LedgerRead readLedger(MissionRef, LedgerStamp)` (called only on a cache miss; decoded `LedgerLine` records of the resolved read directory's ledger plus the read-directory class, and the unterminated-tail classification `none` / `whitespace` / `non_whitespace`); `LedgerWindow readLedgerFrom(MissionRef, long offset)` (decoded lines from the offset, the SHA-256 of the line ending at the offset, the current size and whether the offset is line-aligned). Path resolution, symlink and containment checks, listing and OS faults stay in `adapter.out.filesystem`; line decoding stays in `adapter.out.filesystem.codec`, shared with the in-memory test source, which is constructed from raw ledger lines (plan.md section 13, E-13).

Application-internal collaborators (constructor arguments of the public `MissionStatusService`, supplied by `config`; NOT ports and not named in the hexagon):

- `Consumer<Diagnostic>`: called once per occurrence (see Diagnostics); production `config.LoggingDiagnostics`, tests a recording consumer.
- `ScheduledExecutorService` and `Clock`: the feed's 500 ms poll tick and 1 s re-list run on the injected executor (`config.FeedExecutorConfig`); the application creates no thread. Tests inject a deterministic executor.
- `StreamSettings`: poll and re-list intervals and the per-subscriber queue capacity (`mission-status.stream.queue-capacity`, default 1024).

## Results and invariants

- `MissionPage`: items (contract order: `createdAt` desc, `missionId` asc), `nextPageCursor?`, `missionCount` computed from the same enumeration as the items. It carries no diagnostics.
- Invariant I-1: `eventCount`, `statusLaneCounts`, `lastEventId`, `streamCursor` of an item describe ONE prefix of complete (newline-terminated) lines; any unterminated non-whitespace tail refuses the read (L4/L4b).
- Invariant I-2: `ProjectionCache` key = the `LedgerStamp` (identity over size, mtime and file key, plus the cursor facts `terminatedLength` and last-line digest); an equal stamp never re-reduces and never triggers a `readLedger`; a changed stamp invalidates. The application does not interpret the stamp's identity fields.
- Invariant I-3: no domain/application class references `java.io` file classes, `java.nio.file`, Spring, HTTP or a JSON library. `java.security` (SHA-256) is permitted in `domain`. JSON appears only in `adapter.*` and `config`, and ledger-line decoding only in `adapter.out.filesystem.codec`.

## Stream state (per subscriber)

States: `OPEN(scope, cursorOrNone)` -> emits `status-transition` / `mission-lifecycle` for forwarded terminated lines; `TRUNCATED` -> emits `log-truncated` (no `id:`) and re-baselines; `CLOSED` (scoped: faults S3/S4/S5 close; unscoped: the faulty Mission is dropped, connection kept, rows S2-S6 of the spec's stream table). The unterminated tail is a non-event. Heartbeat comment every 30 s (the interval is configuration so a test can shorten it). The emitter has no timeout of its own (`SseEmitter(0L)`, async request timeout -1); completion, error and timeout callbacks close the subscription. The feed owns the shared state, including the S6 "no further diagnostic until a listing has succeeded" flag; a subscriber holds only its scope, cursor and bounded queue. A full queue closes that subscriber with `Closed(slow_consumer)` (no diagnostic, nothing dropped or reordered before the close; plan.md section 13, E-12).

**Connect-time rows (decided in `MissionStatusService.subscribe`, before a subscription exists).** The table S1 to S6 is in spec.md after FR-004. Mission-scoped S1: `StreamRefused(unknown_mission)`, 404, `path_refused` diagnostic only for an L9 Mission. Mission-scoped S2: `MissionStatusUnavailable` with the row's code, 500. Unscoped S1/S2: the Mission is left out of the watched set, one diagnostic with the row's code, `subscribe` still returns; an unlistable `kitty-specs/` is `MissionStatusUnavailable(mission_dir_unreadable)`, 500. The service emits each of these once; the feed never repeats a connect-time diagnostic.

## Diagnostics

`Diagnostic(code, mid8|"none", line?)`; codes in plan.md section 13. Never carries a path, line text or OS message. One occurrence is emitted once, through the injected `Consumer<Diagnostic>`, by the component that detects it: `MissionStatusService` for a request-scoped read and for the connect-time rows of a stream, the shared `ChangeFeed` for a fault after connect. A fault in one Mission observed by N subscribers is one line, not N.
