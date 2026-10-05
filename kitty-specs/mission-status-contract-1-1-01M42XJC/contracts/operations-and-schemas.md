# Contract: the planned file set of `contracts/mission-status/` for 1.1

This is the planning contract between the work packages of Mission `mission-status-contract-1-1-01M42XJC`: the exact set of files the 1.1 slice (a working name, not a version) adds or edits under `contracts/mission-status/`, the schema sketches, the status and code pairing, the examples and the provisional elements. The product contract is the OpenAPI module itself once built. This note fixes names and shapes so every work package works from one agreed set; an implementer may refine a description but must keep every property, name and rule listed here, or report the change in the hand-off report; the orchestrator records it in `tracer-design-decisions.md` (a work package never writes under `kitty-specs/`: plan, "Record-keeping and write scope"). No block below is a YAML example: sketches use plain text fences so the round-trip gate of the corpus (`tests/contract/test_example_round_trip.py`) has nothing to collect.

## Operations (three, all `GET`, all tagged `Missions`)

The new operations reuse the existing `Missions` tag. A new tag would change the root `tags` list and make the bundle comparison of FR-017 observable 3 (b) unequal (research R-7).

| operationId | Path key (root map) | Path file | Parameters | Responses |
|---|---|---|---|---|
| `getWorkPackageDetail` | `/missions/{missionId}/work-packages/{wpId}/detail` | `paths/missions_missionId_work-packages_wpId_detail.yaml` | `MissionId`, `WpId` (both existing) | 200 `WorkPackageDetail`; 404 `WorkPackageDetailNotFound`; 500 `WorkPackageDetailUnreadable`; `default` shared `Problem` |
| `listArtifacts` | `/missions/{missionId}/artifacts` | `paths/missions_missionId_artifacts.yaml` | `MissionId` | 200 `ArtifactListing`; 404 `ArtifactNotFound`; 500 `ArtifactListingUnreadable`; `default` shared `Problem` |
| `getArtifactContent` | `/missions/{missionId}/artifacts/content` | `paths/missions_missionId_artifacts_content.yaml` | `MissionId`, `ArtifactPath` (new, query `path`, required) | 200 `ArtifactContent`; 400 `ArtifactPathRefused`; 404 `ArtifactNotFound`; 413 `ArtifactTooLarge`; 415 `ArtifactNotText`; 422 `ArtifactSecretRefused`; 500 `ArtifactUnreadable`; `default` shared `Problem` |

The three file names were computed with `contract_resolver.path_file_name`. The detail path is a **new** path item (a sub-resource), so no existing path file changes. No operation declares a security scheme (as in v1). The `getArtifactContent` description states the order of decision (400, 404, 413, 500, 415, 422), the 262,144-byte cap, that `path` is decoded once at the HTTP layer, that a symlink is never followed and that the two root status records are not artifacts. The 422 response description and the `readable` property description list the credential kinds by name: a GitHub token (`ghp`, `gho`, `ghu`, `ghs`, `ghr` prefixes and the fine-grained `github_pat` prefix), an AWS access key id (`AKIA` and `ASIA` prefixes) and the header line of a PEM private key (a test compares these words with `SECRET_PATTERNS`, FR-019).

## New files (all under `contracts/mission-status/`)

Parameters: `parameters/ArtifactPath.yaml` (query parameter `path`, required, schema `ArtifactPath`).

Schemas, one file each, `title` equal to the file stem, closed unless stated (`additionalProperties: false`), every property carrying exactly one `x-source` or `x-derived`:

| Schema | Properties and rules | Provisional (AD-14) |
|---|---|---|
| `WorkPackageDetail` | required: `missionId` (`MissionId`), `wpId` (`WpId`), `subtasks` (array of `Subtask`), `dependencies` (array of `DependencyRef`), `reviewCycles` (array of `ReviewCycle`), `workspace` (`Workspace`), `ownedFiles` (array of `OwnedFile`), `artifactReferences` (`ArtifactReferences`); every array present, possibly empty; embeds no `WorkPackage` | `reviewCycles`, `workspace` |
| `Subtask` | `id` (`RelativeReference`), `title` (string, minLength 1, or null; human text), `statusLane` (`StatusLane` or null) | none |
| `DependencyRef` | `wpId` (`WpId`), `title` (string, minLength 1; never empty; the id as fallback), `statusLane` (`StatusLane` or null) | none |
| `ReviewCycle` | `cycleNumber` (integer, minimum 1), `reviewedAt` (RFC 3339 date-time with offset, or null), `reviewer` (`ActorHandle`, already nullable), `verdict` (`ReviewVerdict` or null), `feedbackReference` (string matching the pointer pattern, or null), `artifactPath` (`ArtifactPath` or null) | the schema |
| `Workspace` | `laneId` (string, strict, or null), `laneBranch` (string matching the branch pattern, or null), `planningBranch` (string or null), `worktreePresent` (boolean) | the schema |
| `OwnedFile` | `pattern` (`RelativeReference`), `isGlob` (boolean), `changeState` (`ChangeState`) | none |
| `ChangeState` | enum `changed`, `unchanged`, `unknown`; description states the host dependence and the derivation | none (stable) |
| `ArtifactReferences` | `prompt` and `spec`, each `ArtifactReference` or null, both required | none |
| `ArtifactReference` | `path` (`ArtifactPath`), `kind` (`ArtifactKind`) | via `kind` |
| `ArtifactPath` | string, `minLength: 1`, `maxLength: 512`, the pattern below | none |
| `ArtifactKind` | enum of twelve values: `review_cycle`, `work_package_prompt`, `spec`, `plan`, `tasks`, `data_model`, `quickstart`, `analysis_report`, `research`, `contract`, `checklist`, `other`; the classifier order is the description | the schema |
| `ArtifactEntry` | `path` (`ArtifactPath`), `kind` (`ArtifactKind`), `sizeBytes` (integer, minimum 0), `modifiedAt` (RFC 3339 UTC with `Z`, whole seconds), `readable` (boolean; the description lists the credential kinds) | via `kind` |
| `ArtifactListing` | `missionId`, `entries` (array of `ArtifactEntry`, `maxItems: 1000`), `truncated` (boolean) | `truncated` |
| `ArtifactContent` | all required: `path` (`ArtifactPath`), `kind`, `mediaType` (string), `encoding` (`const: utf-8`), `sizeBytes`, `redacted` (boolean), `content` (string, may be empty) | `redacted`, via `kind` |
| `ArtifactRefusalCode` | enum of seven values (`invalid_artifact_path`, `not_found`, `artifact_too_large`, `artifact_not_text`, `artifact_secret`, `artifact_unreadable`, `artifact_listing_unreadable`) | the schema |
| `ArtifactRefusal` | the shared `Problem` plus required `code` (`$ref` `ArtifactRefusalCode`) and one `if`/`then` per code pinning `status` (400, 404, 413, 415, 422, 500, 500), built like `StreamRefusal`; no field carries file content, a host path or the Mission directory | `code` |
| `WorkPackageDetailRefusalCode` | enum `not_found`, `source_unreadable` | the schema |
| `WorkPackageDetailRefusal` | the shared `Problem` plus required `code` (`$ref` `WorkPackageDetailRefusalCode`) and the status rule (404 for `not_found`, 500 for `source_unreadable`) | `code` |

`ArtifactPath` pattern (ECMA-262 compatible, written with the hex escape, not a unicode escape: a unicode escape typed into some editing tools is decoded into a raw NUL character):

```text
^(?!~/)(?![A-Za-z]:)(?!\.\.?(?:/|$))[^/\\\x00]+(?:/(?!\.\.?(?:/|$))[^/\\\x00]+)*$
```

Responses (`responses/`, each `application/problem+json`): `ArtifactPathRefused` (400), `ArtifactNotFound` (404, used by `listArtifacts` and `getArtifactContent`), `ArtifactTooLarge` (413), `ArtifactNotText` (415), `ArtifactSecretRefused` (422), `ArtifactUnreadable` (500, content), `ArtifactListingUnreadable` (500, listing) all with schema `ArtifactRefusal`; `WorkPackageDetailNotFound` (404) and `WorkPackageDetailUnreadable` (500) with schema `WorkPackageDetailRefusal`. The status of each is the key it is mounted under; the schema pins the code-to-status pairing.

## Environment-dependent and derived descriptions (FR-016, FR-019)

`Workspace.worktreePresent`, `OwnedFile.changeState` and `ArtifactEntry.modifiedAt` say in their descriptions that they depend on the serving host. `ReviewCycle`'s description says a cycle held only on a coordination surface is not shown and that `[]` means none was found on the primary planning surface. `OwnedFile.changeState` is `x-derived` with the full rule of the data model and inputs `git_merge_base`, `changed_paths` and `is_glob_pattern`; `Subtask.title` and `DependencyRef.title` are `x-derived` with the extraction rule; `ArtifactReferences` and the entries are `x-derived` with the eligibility rule. Citation inputs name symbols (never line numbers); the symbols were all resolved (research R-12).

## Examples (21 files under `examples/`, named `<Schema>.<case>.yaml`) and the in-test required cases

| Example | Covers |
|---|---|
| `WorkPackageDetail.populated` | titles and lanes on subtasks and dependencies; two review cycles (one `approved`, one `changes_requested`); a lane worktree present; owned files `changed` and `unchanged` and one glob; both artifact references |
| `WorkPackageDetail.no-cycles` | `reviewCycles: []`, a dependency with a null lane, a subtask with a null title |
| `WorkPackageDetail.unknown-change-state` | owned files `unknown` (no worktree) including a brace pattern; `worktreePresent: false` |
| `WorkPackageDetail.null-workspace` | `laneId`, `laneBranch`, `planningBranch` all null; empty `subtasks`, `dependencies`, `ownedFiles`; both references null |
| `WorkPackageDetail.planning-lane` | `laneId: lane-planning`, `laneBranch: null`, a `planningBranch` |
| `WorkPackageDetail.unparseable-cycle` | a cycle with null `reviewedAt`, null `reviewer`, null `verdict`, null `feedbackReference` and a null `artifactPath` |
| `ArtifactListing.populated` | entries across several kinds with one `readable: false` entry |
| `ArtifactListing.truncated` | `truncated: true` (a short list; a comment states a real truncated listing holds exactly 1000 entries) |
| `ArtifactContent.markdown` | `redacted: false` |
| `ArtifactContent.redacted` | `redacted: true`, `[path]` and `[email]` in `content` |
| `ArtifactContent.json` | `application/json` |
| `ArtifactContent.empty` | a zero-byte file: `content: ""`, `sizeBytes: 0` |
| `ArtifactRefusal.<code>` (7: `invalid-artifact-path`, `not-found`, `artifact-too-large`, `artifact-not-text`, `artifact-secret`, `artifact-unreadable`, `artifact-listing-unreadable`) | each code with its pinned status |
| `WorkPackageDetailRefusal.<code>` (2: `not-found`, `source-unreadable`) | each code with its pinned status |

Small leaf schemas (`Subtask`, `DependencyRef`, `ReviewCycle`, `Workspace`, `OwnedFile`, `ArtifactReference`, `ArtifactEntry`, the enums) carry short inline `examples` so that every new schema has examples (FR-019). The spec's required cases are enforced by extending `tests/contract/test_mission_status_examples.py` (an in-test manifest: every refusal code has an example; both `redacted` values occur; both `readable` values occur; `truncated: true` occurs; each `ChangeState` value occurs; a cycle with a null `feedbackReference` and one with a null `reviewedAt` occur), not by an entry in `contracts/tools/fixtures/example_check/required_examples.json` (OD-2). Every example is leak-free; a path in an example satisfies the `ArtifactPath` pattern; no example holds an absolute path, a host path, an e-mail address, a credential or an unredacted content.

## Edits to existing files (the whole list; everything else under `contracts/mission-status/` and `contracts/_shared/` stays byte-identical)

`openapi.yaml`: `info.version` stays `1.0.0-SNAPSHOT` (no new version, operator ruling 2026-10-05) and three path keys are added to the root map (no new tag, no change to `servers` or `info` otherwise). `_index.yaml` of `schemas/`, `parameters/`, `responses/` and `examples/`: new entries only. `CHANGELOG.md`: the additions merge into the existing `## 1.0.0-SNAPSHOT` section (no new heading), with `### Added` (the three operations; the new schemas, parameter and responses; the two behaviours of the reads: invalid UTF-8 is a 415 and the root status records are no artifacts; a one-line reference to #5533 for the route mapping, naming the five route families covered and stating that the dossier overview and the snapshot export are not covered), `### Changed` ("Nothing."), `### Removed` ("Nothing."), `### Provisional` (below) and `### Deferred to the next major version` (the four v1 gaps, each with one line of reason: per-Mission staleness on `MissionOverview`, an actor on `WorkPackageSummary`, the project branch, the lane weights behind `weightedPercentage`; each would add a property to an existing response, which the breaking-change check treats as breaking).

The Provisional section of the `1.0.0-SNAPSHOT` section names, as whole words: `reviewCycles`, `workspace`, `ReviewCycle`, `Workspace`, `ArtifactKind`, `truncated`, `redacted`, `code`, `ArtifactRefusalCode`, `WorkPackageDetailRefusalCode`, `ArtifactRefusal`, `WorkPackageDetailRefusal`, and `kind` (the properties that reference a provisional schema are counted by `provisional_check` under their own name; the final list is the output of `provisional_check.py` run on the finished tree, never a guess).

## Order of work for the shared files

`openapi.yaml`, the four `_index.yaml` files and `CHANGELOG.md` are written by the contract work packages in sequence (artifact reads first, then the detail, then the CHANGELOG once the provisional list is final), never in parallel (plan, Implementation Concern Map).
