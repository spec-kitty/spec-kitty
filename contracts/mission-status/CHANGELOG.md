# Changelog

All notable changes to the `mission-status` contract are recorded here, newest first. The
module version is the `info.version` of `openapi.yaml`.

## 1.0.0

Initial entry. This version is not yet released.

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

### Removed

- Nothing yet.

### Provisional

- `MissionOverview.nextAction` is provisional: its shape is an open decision on #5528.
- `WorkPackage.staleness` is provisional: how staleness is measured, and whether v1 carries
  it, is an open decision on #5528. It is null when it was not computed.
- `StreamCursorString`, the `Last-Event-ID` precedence rule and the HTTP status of each
  `StreamRefusal` code (400 or 409) are provisional: the tail reader has no text form of its
  cursor and no HTTP mapping, so they are open decisions on #5528. The event stream framing and
  heartbeat interval are conventions of this contract and are likewise open.
