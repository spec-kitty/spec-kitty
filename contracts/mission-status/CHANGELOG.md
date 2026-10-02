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

### Changed

- Nothing yet.

### Removed

- Nothing yet.

### Provisional

- `MissionOverview.nextAction` is provisional: its shape is an open decision on #5528.
