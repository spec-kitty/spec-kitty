# Contract: the planned file set of `contracts/mission-status/` for the health, drift and ops reads

This is the planning contract between the work packages of Mission `mission-status-health-drift-ops-01M464D3`: the exact set of files the slice adds or edits under `contracts/mission-status/`, the schema sketches, the status and code pairing, the examples and the provisional elements. The product contract is the OpenAPI module itself once built. This note fixes names and shapes so every work package works from one agreed set; an implementer may refine a description but must keep every property, name and rule listed here, or report the change in the hand-off report; the orchestrator records it in `tracer-design-decisions.md` (a work package never writes under `kitty-specs/`: plan, "Record-keeping and write scope"). No block below is a YAML example: sketches use plain text fences so the round-trip gate of the corpus (`tests/contract/test_example_round_trip.py`) has nothing to collect. **No new contract version**: `info.version` stays `1.0.0-SNAPSHOT` (spec PR-1).

## Operations (two new, one changed), tags and parameters

| operationId | Path key (root map) | Path file | Tag | Parameters | Responses |
|---|---|---|---|---|---|
| `getProject` (changed) | `/project` | `paths/project.yaml` (description only) | `Project` (existing) | none | 200 `Project` (five new required properties); `default` shared `Problem` |
| `getDriftReport` | `/drift` | `paths/drift.yaml` | `Drift` (new) | optional query `missionId` (`parameters/DriftMissionId.yaml`, over the `MissionId` schema; the existing `parameters/MissionId.yaml` is a path parameter and is not reused) | 200 `DriftReport` with the header `Cache-Control: no-store` documented; 404 `DriftMissionNotFound` (`DriftRefusal`, code `mission_not_found`); 500 `DriftScanUnreadable` (`DriftRefusal`, code `drift_scan_unreadable`); `default` shared `Problem` (a non-ULID `missionId` is 400 under `default`) |
| `listOpsInvocations` | `/ops/invocations` | `paths/ops_invocations.yaml` | `Ops` (new) | shared `PageSize` and `PageCursor`; optional query `profile` (`parameters/OpsProfile.yaml`, pattern of `profileId`) | 200 `OpsInvocationPage`; 400 the existing `PageCursorRefused`; 500 `OpsUnreadable` (`OpsRefusal`, code `ops_unreadable`); `default` shared `Problem`; carries `x-provisional` (AD-7) |

The two path-file names were computed with `contract_resolver.path_file_name` (`/drift` gives `drift.yaml`, `/ops/invocations` gives `ops_invocations.yaml`). No operation declares a security scheme (as in v1). The root `tags` list of `openapi.yaml` gains `Drift` and `Ops` with one-line descriptions; the previous slice added none, so the additive comparison removes them too (plan PD-4). The `listOpsInvocations` description states the skipped-record rule (legacy or unreadable records are skipped and counted in `skippedCount`), that `totalCount` can lag the newest records, and that the operation never starts an agent or writes. The `getDriftReport` description states: a scan reads, never repairs; Rescan is a second call; `scannedAt` is the time of this scan; a Mission whose declared coordination branch no longer exists is scanned from its own directory, which can lag the coordination surface; the stock coordination resolver may query remotes, so the outcome depends on the network; an unreachable remote leaves the Mission's own directory as the read directory (a 200 with no fallback entry), a reachable remote that lacks the declared branch gives the `coordination_branch_deleted` fallback, and any other resolver error is a 500 `drift_scan_unreadable` (FRESH3-001, as ruled by the operator ruling at WP07, 2026-10-06); `findings: []` means the scan ran and found none.

## New files (all under `contracts/mission-status/`; 49 in all)

Parameters: `parameters/DriftMissionId.yaml` (query `missionId`, optional), `parameters/OpsProfile.yaml` (query `profile`, optional, pattern `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`).

Schemas, one file each, `title` equal to the file stem, closed unless stated (`additionalProperties: false`), every property carrying exactly one `x-source` or `x-derived` (the field catalogue of the spec is the authority; citation inputs name symbols, never line numbers):

| Schema | Properties and rules | Provisional (FR-023) |
|---|---|---|
| `ProjectHealth` | enum `healthy`, `schema_drift`; the description says the range is the serving build's and rolls up the three non-compatible schema statuses | via `health` |
| `DriftReport` | `scannedAt`, `findings` (array of `DriftFinding`, `maxItems: 1000`), `truncated`; the description states the cap, the order, the fallback rule and the network behaviour | `truncated` |
| `DriftFinding` | the ten members of the data model, all required; `missionId` and `artifactPath` non-null; the description qualifies the kind-1 summaries (the disagreement is with the reducer replay at the snapshot's own generation, not with the true event log) | `kind`, `remedy`, `laneComparison` |
| `LaneComparison` | `wpId` (`WpId`), `persistedStatusLane` and `derivedStatusLane` (`StatusLane` or null); the description says "status lane", never "code lane" | via `laneComparison` |
| `DriftKind` | enum of three values; the description states the two checks behind `lane_branch_missing`, that a manifest predating `mission_slug` is not evaluated for it, "no local branch", and the decision on `derived_view_stale` (considered, not shipped, why) | the schema |
| `DriftSeverity` | enum `error`, `warning` | none |
| `DriftAuthority` | enum `event_log`, `git` | none |
| `DriftSide` | enum `status_json`, `lanes_json` | none |
| `DriftRemedy` | enum `materialize_status`; the description maps it once to `spec-kitty agent status materialize --mission <slug>` (not `spec-kitty materialize`, which writes only derived views), says the client builds the text and takes the slug from `MissionHead.slug` | the schema |
| `DriftRefusalCode` | enum `mission_not_found`, `drift_scan_unreadable` | the schema |
| `DriftRefusal` | the shared `Problem` plus required `code` (`$ref` `DriftRefusalCode`) and one `if`/`then` per code pinning `status` (404, 500), built like `ArtifactRefusal` | `code` |
| `OpsInvocationPage` | `items`, `pageInfo` (shared), `totalCount`, `skippedCount` | `totalCount`, `skippedCount` |
| `OpsInvocation` | the twelve members of the data model, all required; the description names the five omitted record fields and uses the glossary definition of an Op | `evidence` |
| `OpsModeOfWork` | enum `task_execution`, `advisory`, `mission_step`, `query` | none |
| `OpsInvocationStatus` | enum `open`, `closed`; the description says `closed` counts the closure spine | none |
| `OpsOutcome` | enum `done`, `failed`, `abandoned` | none |
| `OpsClosedBy` | enum `agent`, `doctor_sweep` | none |
| `OpsEvidence` | `kind` (`OpsEvidenceKind`), `value` (`maxLength: 512`), `redacted` (boolean) | via `evidence` |
| `OpsEvidenceKind` | enum `repo_path`, `url`, `text` | none |
| `OpsRefusalCode` | enum `ops_unreadable` | the schema |
| `OpsRefusal` | the shared `Problem` plus required `code` (`$ref` `OpsRefusalCode`) and the status rule (500) | `code` |

Responses (`responses/`, each `application/problem+json`): `DriftMissionNotFound` (404) and `DriftScanUnreadable` (500) with schema `DriftRefusal`; `OpsUnreadable` (500) with schema `OpsRefusal`. The status of each is the key it is mounted under; the schema pins the code-to-status pairing. The 404 no longer reads "shared Problem shape".

**Patterns written with the hex escape.** Any pattern that needs a NUL or a backslash is written `\x00` and `\\`; a unicode escape typed into some editing tools is decoded into the raw character. Tests build a NUL with `chr(0)` and a backslash with `chr(92)`.

## Descriptions that carry rules (checked by committed tests)

- **`Project`**: names the five properties; no longer says "a name and a count only"; says the cost grows with the Mission count and that each Mission's read directory is resolved through git queries that can include network probes (so "safe to call once per recent project" means side-effect-free, not network-free); says `GET /project` runs no drift scan and never depends on a finding.
- **`schemaVersion`**: the value is the CLI's coercion (a float or boolean in the file is served as an integer). **`health`**: the serving build's range; provisional. **`currentBranch`**: null means "no branch name this contract can carry" and does not separate detached, absent, unreadable or unrepresentable; a served name is user-authored text served as stored. **`lastActivityAt`**: null when no Mission is listed and when every listed Mission has null activity.
- **`evidence`**: null means "no evidence, or withheld because it holds a credential"; names the credential kinds checked (GitHub classic and fine-grained tokens, AWS access key id, private-key header; a test compares these words with `SECRET_PATTERNS`) and says other secret shapes are not detected.
- **`OpsInvocation`**: the omitted fields by name (`request_text`, `model_id`, `governance_context_hash`, `governance_context_available`, `router_confidence`); a committed test fails when one name is missing, and the closed schema rejects a payload carrying any of them.
- **`DriftFinding.summary`**: the six fixed sentences of the data model, written in the schema description and compared literally by the reference reader.

## Examples (21 new files under `examples/`, named `<Schema>.<case>.yaml`) and the in-test required cases

| Example | Covers |
|---|---|
| `Project.example` (edited), `Project.all-null`, `Project.schema-drift` | healthy; every nullable property null with `schema_drift`; schema drift with a branch and an activity instant |
| `DriftReport.clean` | `findings: []`, `truncated: false` |
| `DriftReport.populated` | the three kinds, a lane comparison with a one-sided work package, a warning variant, a null `remedy` |
| `DriftReport.corrupt-json` | `CORRUPT_JSON` with `laneComparison: []` and `remedy: materialize_status` |
| `DriftReport.truncated` | `truncated: true` (a short list with a comment; a real truncated report holds exactly 1000 findings) |
| `DriftRefusal.mission-not-found`, `DriftRefusal.scan-unreadable` | each code with its pinned status |
| `OpsInvocationPage.first`, `.last`, `.empty` | `hasNextPage` true with a cursor; the last page; `items: []` with `totalCount: 0` and `skippedCount: 0` |
| `OpsInvocation.open`, `.closed-by-agent`, `.closed-by-doctor-sweep` | the three closure states, `completedAt` of the closure for the sweep |
| `OpsInvocation.evidence-repo-path`, `.evidence-url`, `.evidence-url-redacted`, `.evidence-text`, `.evidence-text-redacted`, `.evidence-null` | each evidence kind with and without redaction, and `evidence: null` |
| `OpsRefusal.ops-unreadable` | the one code with its pinned status |

Small leaf schemas (`LaneComparison`, `OpsEvidence`, the enums) carry short inline `examples` so that every new schema has examples. The spec's required cases are enforced by extending `tests/contract/test_mission_status_examples.py` (an in-test manifest: every refusal code has an example, both `redacted` values occur, each evidence kind occurs, each `DriftKind` and each `sourceCode` of the pair table occurs, each closure state occurs, an example with a null `missionId` or `artifactPath` is refused), not by an entry in `contracts/tools/fixtures/example_check/required_examples.json` (a path outside the file set). Every example is leak-free: no host path, e-mail address, credential or unredacted evidence value; a path in an example satisfies the artifact-path rule. `MIN_EXAMPLES` and `EXPECTED_PATH_KEYS` (ten path keys) move with the files.

## The provisional elements and their CHANGELOG tokens (FR-023)

Exactly these elements carry `x-provisional`; each token is a whole word in the `### Provisional` heading of the `1.0.0-SNAPSHOT` section (the output of `provisional_check.py` run on the finished tree is the final list, never a guess):

```text
health                         property of Project
DriftKind                      schema (with the two checks, the legacy-manifest rule, "no local branch", the derived_view_stale decision)
kind                           property of DriftFinding   (qualified: DriftFinding.kind)
remedy, DriftRemedy            property of DriftFinding; schema
laneComparison                 property of DriftFinding
truncated                      property of DriftReport    (qualified: DriftReport.truncated)
DriftRefusalCode               schema;  code of DriftRefusal  (qualified: DriftRefusal.code)
OpsRefusalCode                 schema;  code of OpsRefusal    (qualified: OpsRefusal.code)
evidence                       property of OpsInvocation
totalCount, skippedCount       properties of OpsInvocationPage
/ops/invocations               the operation (carries the legacy-record rule, AD-7)
```

`kind`, `code` and `truncated` are already named in that section by the previous slice (`ArtifactKind`, `ArtifactRefusalCode`, `ArtifactListing`), so `provisional_check` is satisfied by the bare word; a committed test asserts the four qualified names literally, each with a plant that removes it.

## Edits to existing files (the whole list; everything else under `contracts/mission-status/` and `contracts/_shared/` stays byte-identical)

- `schemas/Project.yaml`: `description` rewritten, `required` extended, five properties added (`x-source` or `x-derived` each; `health` `x-provisional`); `examples/Project.example.yaml` updated and two examples added; `paths/project.yaml`: description only.
- `openapi.yaml`: `info.version` stays; two path keys and two tags added. The four `_index.yaml` files: new entries only.
- `CHANGELOG.md`, merged into the existing `## 1.0.0-SNAPSHOT` section (no new heading): `### Added` (the two operations; the new schemas, parameters and responses; the two read behaviours that readers will meet: legacy and unreadable Op records are skipped and counted, a manifest predating `mission_slug` is not evaluated for kind 3), `### Changed` (the `Project` change as a pre-release shape change, with the four non-provisional additions and why the tooling reports them), `### Removed` ("Nothing."), `### Provisional` (above), `### Deferred to the next major version` (**three** gaps: per-Mission staleness on `MissionOverview`, an actor on `WorkPackageSummary`, the lane weights behind `weightedPercentage`; the line "The project branch" and the word "Four" are gone), plus the statements of FR-023: the cap of 1000, the not-shipped decision of `derived_view_stale` with its reason, that `info` of the audit `Severity` is not carried, that `missionId` and `artifactPath` of `DriftFinding` are non-null, and the design note for the read service (resolve coordination locally; out of scope, no `src/` change).
- `contracts/tools/enum_pins.json`: thirteen pins (see the data model); `tests/contract/test_enum_pin_check.py` moves its pinned `counts:` line.

## Order of work for the shared files

`openapi.yaml`, the four `_index.yaml` files, `enum_pins.json` and `CHANGELOG.md` are written by the contract work packages in sequence (the `Project` vertical, then Drift, then Ops, then the final CHANGELOG statements), never in parallel (plan, Lanes). The JVM replay (J-1) runs once the last of them is approved.
