# Changelog

All notable changes to the `mission-status` contract are recorded here, newest first. The
module version is the `info.version` of `openapi.yaml`.

## 1.0.0-SNAPSHOT

Initial entry. This version is not yet released: an unreleased contract version carries the `-SNAPSHOT`
suffix and becomes `1.0.0` in the release commit. The release is the tag `contract-mission-status-v1.0.0`,
pushed by a maintainer. Until then the breaking-change job has no baseline and reports
`NO_BASELINE_INITIAL_VERSION`.

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
- `GET /missions/{missionId}/artifacts` (`listArtifacts`): the eligible files of one Mission directory
  as a flat list sorted by path in byte order, at most 1000 entries, with `truncated` set when more
  existed. Each entry (`ArtifactEntry`) names the `path`, the `kind`, the `sizeBytes`, the
  `modifiedAt` and whether the content is `readable`.
- `GET /missions/{missionId}/artifacts/content` (`getArtifactContent`): the decoded and redacted text
  of one artifact (`ArtifactContent`), selected by the required query parameter `path`
  (`ArtifactPath`). Content that is invalid UTF-8, and content that holds a NUL byte, is a 415, not a
  replacement text.
- The two root status records of a Mission directory, `status.events.jsonl` and `status.json`, are
  not artifacts: they are not listed and are answered 404.
- The schemas `ArtifactPath`, `ArtifactKind` (twelve values, in snake_case: `review_cycle`,
  `work_package_prompt`, `spec`, `plan`, `tasks`, `data_model`, `quickstart`, `analysis_report`,
  `research`, `contract`, `checklist` and `other`), `ArtifactEntry`, `ArtifactListing`,
  `ArtifactContent`, `ArtifactRefusalCode` (seven values) and `ArtifactRefusal`, the parameter
  `ArtifactPath`, and the seven responses `ArtifactPathRefused` (400), `ArtifactNotFound` (404),
  `ArtifactTooLarge` (413), `ArtifactNotText` (415), `ArtifactSecretRefused` (422),
  `ArtifactUnreadable` (500) and `ArtifactListingUnreadable` (500).
- `GET /missions/{missionId}/work-packages/{wpId}/detail` (`getWorkPackageDetail`): the detail of one
  work package (`WorkPackageDetail`): its subtasks and dependencies with titles and status lanes, its
  review cycles, its workspace, the files it owns with their change state, and pointers to its prompt
  file and the Mission's specification. Every array is present and may be empty. A review-cycle file
  the product cannot parse is still a cycle: only its `reviewedAt` and `reviewer` are null, and its
  `verdict`, `feedbackReference` and `artifactPath` follow their own rules. A work package id held
  by two files is served by the first regular, non-symlink file in byte order of the file name, and the
  prompt file is the first qualifying `tasks/WP[0-9]{2,}-*.md` file in byte order.
- The schemas `WorkPackageDetail`, `Subtask`, `DependencyRef`, `ReviewCycle`, `Workspace`, `OwnedFile`,
  `ChangeState` (`changed`, `unchanged`, `unknown`), `ArtifactReferences`, `ArtifactReference`,
  `WorkPackageDetailRefusalCode` (two values) and `WorkPackageDetailRefusal`, and the responses
  `WorkPackageDetailNotFound` (404) and `WorkPackageDetailUnreadable` (500).
- Coverage of the removed dashboard's routes (#5533): the artifact reads cover `/api/artifact/*`,
  `/api/research/*`, `/api/contracts/*`, `/api/checklists/*` and the artifact part of `/api/dossier/*`.
  The dossier overview and the snapshot export are not covered. The route-by-route mapping is the work of
  #5533 and is not recorded here.
- `GET /drift` (`getDriftReport`): where derived state disagrees with its source, for the project or, with
  the optional query parameter `missionId` (`DriftMissionId`), for one Mission. A scan reads and never
  repairs; `scannedAt` is the time of the scan, the 200 carries `Cache-Control: no-store`, and a
  `missionId` that names no Mission is a 404 (`DriftMissionNotFound`) while a scan that cannot read a
  Mission is a 500 (`DriftScanUnreadable`), never a partial report. The stock coordination resolver may
  query remotes, so the outcome depends on the network; `findings: []` means the scan ran and found none.
- The schemas `DriftReport`, `DriftFinding`, `LaneComparison`, `DriftKind` (three values:
  `snapshot_disagrees_with_event_log`, `snapshot_or_event_log_missing` and `lane_branch_missing`),
  `DriftSeverity` (`error`, `warning`), `DriftAuthority` (`event_log`, `git`), `DriftSide` (`status_json`,
  `lanes_json`), `DriftRemedy` (`materialize_status`), `DriftRefusalCode` (`mission_not_found`,
  `drift_scan_unreadable`) and `DriftRefusal`, the two responses `DriftMissionNotFound` (404) and
  `DriftScanUnreadable` (500), and the tag `Drift`. The summary of a finding is one of six fixed sentences.
- The report holds at most 1000 findings, sorted by `missionId`, `kind` and `artifactPath` in byte order,
  with `truncated` set when more existed. `missionId` and `artifactPath` of `DriftFinding` are non-null:
  every shipped kind belongs to one Mission and names one file.
- The `info` value of the audit `Severity` is not carried: `DriftSeverity` is `error` and `warning` only.
- A fourth kind, `derived_view_stale`, was considered and is not shipped. A kind ships only with an honest
  rule and a real example. The rule could be written, but no example exists: `.kittify/derived/` is ignored
  by git, untracked and written only on an operator machine, so a fresh clone has none, and the product has
  retired its own check of derived views.
- One read behaviour readers will meet: a manifest that predates `mission_slug` is not evaluated for
  `lane_branch_missing` and no finding is reported for it; the two status files of that Mission are still
  compared.
- `GET /ops/invocations` (`listOpsInvocations`): one page of the Op invocation records of the project,
  newest first (`startedAt` descending, ties by `invocationId` descending), with the optional query
  parameter `profile` (`OpsProfile`) and the shared `PageSize` and `PageCursor`. It never starts an agent
  and never writes. An Op is closed when its own file holds a completion or the closure spine holds a record
  for its id. `totalCount` is the number of served Ops that match the filter and can lag the newest
  records; `skippedCount` is the number of legacy or unreadable records, over the same candidate set and
  independent of the filter. A directory that exists but cannot be read is a 500 (`OpsUnreadable`), never an
  empty page. The operation carries `x-provisional`.
- The schemas `OpsInvocationPage`, `OpsInvocation`, `OpsEvidence`, `OpsModeOfWork` (`task_execution`,
  `advisory`, `mission_step`, `query`), `OpsInvocationStatus` (`open`, `closed`), `OpsOutcome` (`done`,
  `failed`, `abandoned`), `OpsClosedBy` (`agent`, `doctor_sweep`), `OpsEvidenceKind` (`repo_path`, `url`,
  `text`), `OpsRefusalCode` (`ops_unreadable`) and `OpsRefusal`, the response `OpsUnreadable` (500), the
  parameter `OpsProfile` and the tag `Ops`. The record fields `request_text`, `model_id`,
  `governance_context_hash`, `governance_context_available` and `router_confidence` are left out on
  purpose, and the closed schema rejects a payload that carries one.
- One read behaviour readers will meet: legacy and unreadable Op records are skipped and counted in
  `skippedCount`, never served and never a failure. Evidence that holds a credential is withheld (the
  Op is served with `evidence` null), and other evidence has host paths, e-mail addresses and address
  userinfo removed and is cut to 512 characters.

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

- Pre-release shape change: `Project` gains five required properties: `specKittyVersion`,
  `schemaVersion`, `health` (the new schema `ProjectHealth`: `healthy`, `schema_drift`),
  `currentBranch` and `lastActivityAt`. Each is required and nullable except `health`, so an
  absent key is never a valid answer. The `Project` description now states that the read is
  side-effect-free but not free: its cost grows with the Mission count and its git queries can
  include network probes. The breaking-change tooling reports the four non-provisional additions
  (`specKittyVersion`, `schemaVersion`, `currentBranch`, `lastActivityAt`) as breaking, because
  they add required properties to an existing, closed response; this is the one change of an
  existing response, made before the contract is released, and `health` is provisional.

### Removed

- Nothing. This is the initial version.

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
- `ArtifactKind` (the schema, and the `kind` property of `ArtifactEntry` and `ArtifactContent` that
  carries it): the twelve classes and the order of the classifier are a proposal.
- `ArtifactRefusalCode` (the schema) and the `code` of `ArtifactRefusal`: the seven codes and the
  status each takes are a proposal.
- `truncated` of `ArtifactListing`: the cap of 1000 entries may be replaced by paging.
- `redacted` of `ArtifactContent`: the flag and the markers `[path]` and `[email]` are a proposal.
- `reviewCycles` of `WorkPackageDetail` and the schema `ReviewCycle`: the shape of a review cycle and
  the reading of the primary planning surface only are a proposal.
- `workspace` of `WorkPackageDetail` and the schema `Workspace`: the four members are a proposal.
- `WorkPackageDetailRefusalCode` (the schema) and `WorkPackageDetailRefusal` (the schema, with its
  `code`): the two codes and the status each takes are a proposal.
- `kind` of `ArtifactReference`: it carries the provisional `ArtifactKind`.
- `health` of `Project`: the two-value badge and the serving build's range rule are a proposal.
- `DriftKind` (the schema) and the `kind` of `DriftFinding` that carries it (`DriftFinding.kind`): the
  three kinds, the two checks behind `lane_branch_missing` and the decision not to ship `derived_view_stale`
  are a proposal.
- `remedy` of `DriftFinding` and the schema `DriftRemedy`: whether a finding names its repair, and the one
  value `materialize_status`, are a proposal.
- `laneComparison` of `DriftFinding`: the lane rows of a snapshot that disagrees with the event log are a
  proposal.
- `truncated` of `DriftReport` (`DriftReport.truncated`): the cap of 1000 findings may be replaced by paging.
- `DriftRefusalCode` (the schema) and the `code` of `DriftRefusal` (`DriftRefusal.code`): the two codes and
  the status each takes are a proposal.
- `OpsRefusalCode` (the schema) and the `code` of `OpsRefusal` (`OpsRefusal.code`): the one code and the
  status it takes are a proposal.
- `evidence` of `OpsInvocation`: the three classes of evidence, the removal of host paths and addresses, the
  withholding of a credential and the cut at 512 characters are a proposal. The credential kinds checked
  are the GitHub classic and fine-grained tokens, the AWS access key id and the private-key header; other
  secret shapes are not detected.
- `totalCount` and `skippedCount` of `OpsInvocationPage`: that the list carries a total which can lag the
  newest records, and that legacy and unreadable records are skipped and counted, are a proposal.
- `/ops/invocations` (`GET /ops/invocations`): the operation carries `x-provisional` because the legacy-record
  rule has no property of its own; the marker is dropped once that rule and `skippedCount` are settled.

### Deferred to the next major version

Three gaps are decided out of this release. Each would add a property to an existing, closed response, which the
breaking-change check treats as breaking once the contract is released, so each waits for the next major version.

- The per-Mission staleness on `MissionOverview`: a new property of an existing, closed response.
- An actor on `WorkPackageSummary`: a new property of an existing, closed response.
- The lane weights behind `weightedPercentage`: new properties of an existing, closed response.
