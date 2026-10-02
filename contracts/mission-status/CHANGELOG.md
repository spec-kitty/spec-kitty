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
