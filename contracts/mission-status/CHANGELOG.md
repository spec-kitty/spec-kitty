# Changelog

All notable changes to the `mission-status` contract are recorded here, newest first. The
module version is the `info.version` of `openapi.yaml`.

## 1.0.0-SNAPSHOT

Initial entry. This version is not yet released: an unreleased contract version carries the `-SNAPSHOT` suffix and
becomes `1.0.0` in the release commit.

### Added

- `GET /project`: the project name and the number of Missions listed.
- `GET /missions`: one page of Mission overviews, ordered by `createdAt` descending with
  ties broken by `missionId` ascending, paged with the shared opaque page cursor.
- The vocabularies `StatusLane` (nine values), `LifecycleStatus`, `Topology`,
  `ActorHandle`, `MissionId` and `StreamCursor`.
- `GET /missions/{missionId}`: one Mission in detail, the overview fields plus the five Mission
  phases (`specify`, `plan`, `tasks`, `implement`, `review`, each with a `status` and a `basis`)
  and a summary of each work package.
- `GET /missions/{missionId}/work-packages/{wpId}`: one work package in full, with its authored
  plan, resolved state, review evidence, readiness, status history and, only when
  `includePrompt` is true, the prompt body as `promptMarkdown`.
- The path parameters `missionId` (a ULID, the only identifier accepted) and `wpId`, and the
  query parameter `includePrompt`.
- `GET /events`: the change stream, served as `text/event-stream`, with exactly three event
  names, each with one data schema: `status-transition` (`StatusTransitionEvent`),
  `mission-lifecycle` (`MissionLifecycleEvent`, seven lifecycle types) and `log-truncated`
  (`LogTruncatedEvent`, reasons `size_shrink` and `content_mismatch`, reset cursor). Raw log
  rows are never forwarded. The framing, resume, heartbeat and per-Mission ordering are
  documented as a convention in the operation description.
- `StreamCursorString` (`offset:invariant`, the value of the `streamCursor` query parameter, the
  `Last-Event-ID` header and the SSE `id`), `StreamRefusal` (a `Problem` whose `code` is
  `negative`, `out_of_range`, `misaligned`, `content_mismatch` or `cursor_without_mission`) and
  the query parameters `missionId` and `streamCursor` of `GET /events`.

### Changed

- Pre-release shape change: `MissionOverview` is now composed from the new open piece
  `MissionHead`, which holds every overview field, and is closed with
  `unevaluatedProperties: false`. The set of properties and their definitions are unchanged.
  The reason: `MissionDetail` adds fields to the same head, and a schema closed with
  `additionalProperties: false` cannot be extended by composition. Citation inputs that named
  `MissionOverview.createdAt` and `MissionOverview.missionId` now name `MissionHead`.

- Pre-release shape change: the event stream sends no `id:` line on an unscoped stream (no
  `missionId`) and none on a `log-truncated` event of any stream. An unscoped stream has no usable
  cursor, and the `log-truncated` cursor is the reset position, so a browser's automatic
  `Last-Event-ID` no longer holds a position that is refused or that replays the whole log. The
  cursor stays inside the `log-truncated` data. `StreamCursorString` and the `Last-Event-ID`
  description say so.
- Pre-release shape change: `GET /events` gains a `404` response (the shared `Problem`) for a
  `missionId` that names no Mission, as `getMission` and `getWorkPackage` have. `StreamRefusal`
  now states the status of each `code` as a checkable rule: `negative`, `misaligned` and
  `cursor_without_mission` carry `400`; `out_of_range` and `content_mismatch` carry `409`.
- Pre-release shape change: `GET /missions` gains a `400` response (the shared `Problem`, code
  `invalid_page_cursor`) for a malformed, forged or stale `pageCursor`.
- Pre-release shape change: `StreamCursorString` accepts no leading zeros in the offset (pattern
  `^(0|[1-9][0-9]*):[0-9a-f]{64}$`), so one cursor has one text. `StreamCursor.offset` and
  `LogTruncatedEvent.detectedAtOffset` are `format: int64`, so a generated client does not use a
  32-bit integer for a byte offset.
- Pre-release shape change: `WpId` is `^WP[0-9]{2,}$`, the rule the planning-file reader enforces,
  instead of any identifier-like text.
- Pre-release shape change: `Staleness.reason` is an enum of the two reasons the code sets,
  `planning_artifact_repo_root_shared_workspace` and `live_claim_process`, or null.
- Pre-release shape change: `ReviewOverride` gains the required boolean `complete`, the code's own
  rule (`at`, `actor`, work package id and `reason` all non-empty), and `at` and `reason` become
  nullable. A partial override record, which the code keeps and which still blocks the merge
  gate, is now shown with `complete: false` and its blank members null, so a consumer can see
  that an override exists and that the gate is blocked. Only the release marker (all four fields
  empty) is projected as a null `override`.
- Pre-release shape change: a status-transition row whose `wp_id` does not match `WpId`
  (`^WP[0-9]{2,}$`) is not forwarded as a `status-transition` event; it is dropped, counted and
  reported. `WpId` and `StatusTransitionEvent` state this.
- Redaction is named in every human text field description: a host path is replaced by `[path]`
  and an e-mail address by `[email]`. `promptMarkdown` is stated to be the one text field that is
  not redacted; `includePrompt` is its only guard.
- `mid8` is a non-nullable string, the first eight characters of `missionId`; every example
  carries the `mid8` its `missionId` implies. `friendlyName` documents the slug fallback as a rule
  of this contract. `nextAction` is null for a Mission whose work packages are all canceled, a
  deliberate divergence from the replaced dashboard. `executionMode` documents the stripping of
  one pair of literal quotes. The per-work-package keys `lastTransitionAt`, `forceCount` and
  `lastEventId` cite the work package state of the status snapshot.

- `GET /missions` answers an invalid page cursor with `PageCursorRefusal`: a `Problem` whose
  `code` is `invalid_page_cursor` and whose `status` is 400.
- `StatusTransitionEvent` names the `StatusEvent` fields it leaves out, so projecting one later
  is a visible contract change.

### Removed

- Nothing yet.

### Provisional

- `StreamCursor`, the structured `{offset, invariant}` cursor, is provisional like its text
  form: it exposes the tail reader's byte offset, so its shape is an open decision on #5528.
- `MissionOverview.nextAction` is provisional: its shape is an open decision on #5528.
- `WorkPackage.staleness` is provisional: how staleness is measured, and whether v1 carries
  it, is an open decision on #5528. It is null when it was not computed.
- `StreamCursorString`, the `Last-Event-ID` precedence rule and the HTTP status of each
  `StreamRefusal` code (400 or 409) are provisional: the tail reader has no text form of its
  cursor and no HTTP mapping, so they are open decisions on #5528. The event stream framing and
  heartbeat interval are conventions of this contract and are likewise open.
- `StreamRefusal.code` value `cursor_without_mission` is provisional: it is owned by this
  contract (the tail reader's `ResumeRefused` has no such reason and no HTTP mapping), so it is
  an open decision on #5528.
- The event stream framing (`event:`, `id:`, `data:` lines, which events carry an `id:` line) and the 30 second heartbeat are
  marked `x-provisional` on `GET /events`, and the `Last-Event-ID` precedence rule on the
  `streamCursor` parameter, as open decisions on #5528.
- `StreamCursorString` is a deliberately stricter rule than the code: `validate_resume_cursor`
  accepts an offset without an invariant, the contract requires both. This is provisional and an
  open decision on #5528.
