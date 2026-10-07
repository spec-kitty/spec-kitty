# Data Model: Mission Status contract, health, drift and ops reads

Mission `mission-status-health-drift-ops-01M464D3` (#5776). The entities of the three reads, the derivation rules in their order of decision, the closed vocabularies, the status and refusal pairings, and the floors with the independent counts they are compared against. The product contract is the OpenAPI module itself once built; this note fixes the shapes the work packages build from. Every rule is the spec's (FR-001 to FR-029, AD-1 to AD-10 and the operator rulings); nothing here adds a rule. Plain text fences only.

## Entities

| Entity | Members (all required; nullable where stated) | Closed |
|---|---|---|
| `Project` (extended) | `name`, `missionCount`, `specKittyVersion` (string or null), `schemaVersion` (integer or null), `health` (`ProjectHealth`; provisional), `currentBranch` (string or null), `lastActivityAt` (date-time or null) | yes |
| `DriftReport` | `scannedAt` (date-time), `findings` (array of `DriftFinding`, at most 1000), `truncated` (boolean; provisional) | yes |
| `DriftFinding` | `kind` (`DriftKind`; provisional), `severity` (`DriftSeverity`), `missionId` (`MissionId`, non-null), `artifactPath` (the artifact-path rule, non-null), `summary` (fixed text), `authority` (`DriftAuthority`), `derivedSide` (`DriftSide`), `laneComparison` (array of `LaneComparison`; provisional), `remedy` (`DriftRemedy` or null; provisional), `sourceCode` (string matching `^[A-Z][A-Z0-9_]*$` or null) | yes |
| `LaneComparison` | `wpId` (`WpId`), `persistedStatusLane` (`StatusLane` or null), `derivedStatusLane` (`StatusLane` or null) | yes |
| `DriftRefusal` | a `Problem` with `code` (`DriftRefusalCode`; provisional) and one `if`/`then` per code pinning `status` (`mission_not_found` 404, `drift_scan_unreadable` 500) | as `Problem` plus `code` |
| `OpsInvocationPage` | `items` (array of `OpsInvocation`), `pageInfo` (shared `PageInfo`), `totalCount` (integer at least 0; provisional), `skippedCount` (integer at least 0; provisional) | yes |
| `OpsInvocation` | `invocationId` (ULID), `profileId`, `action` (both `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`), `actor` (`ActorHandle`, nullable), `modeOfWork` (`OpsModeOfWork`), `startedAt` (date-time), `missionId` (nullable), `wpId` (nullable), `status` (`OpsInvocationStatus`), `outcome` (`OpsOutcome`, nullable), `closedBy` (`OpsClosedBy`, nullable), `completedAt` (nullable), `evidence` (`OpsEvidence`, nullable; provisional) | yes |
| `OpsEvidence` | `kind` (`OpsEvidenceKind`), `value` (string, at most 512 characters), `redacted` (boolean) | yes |
| `OpsRefusal` | a `Problem` with `code` (`OpsRefusalCode`; provisional), status pinned (500) | as `Problem` plus `code` |

The record fields left out on purpose are named in the `OpsInvocation` description: `request_text`, `model_id`, `governance_context_hash`, `governance_context_available`, `router_confidence` (FR-021). The `Project` description names the five properties, no longer says "a name and a count only", and states the cost (it grows with the Mission count and with the network, FR-007).

## The memo and the fallback (FR-015)

```text
memo key      (resolved repository root, Mission directory name)
memo value    raw resolver outcome: a directory, or the exception it raised
              plus the number of subprocesses the resolver call started
consumers     strict drift sibling   CoordinationBranchDeleted -> own directory, reason coordination_branch_deleted
                                     every other exception     -> unreadable (500 drift_scan_unreadable)
                                     directory outside the root -> unreadable
              Project builder        the three exceptions and the outside-root case -> own directory (v1's four fallbacks)
              oracles                the memo's raw outcome (never the reader)
```

Own directory: `kitty-specs/<name>/`. Read directory: the directory the resolver returns (the own directory except for an unmerged coordination-topology Mission, whose read directory is the coordination surface). `meta.json`, `lanes.json` and the merge marker are read in the own directory; `status.json` and `status.events.jsonl` in the read directory.

## Project: the order of decision per property

```text
specKittyVersion  .kittify/metadata.yaml via ProjectMetadata.load (never the CLI wrapper)
  absent, empty, not YAML                              -> null
  guard (plan D-P4): the parsed YAML is checked first; ProjectMetadata.load is called only when the top level is a mapping
  and spec_kitty is a mapping; a residual AttributeError or TypeError from load (environment a list or scalar, a
  non-mapping migrations entry) is read as null
  top level not a mapping, or spec_kitty not a mapping -> null (the read does not raise, never a 500)
  no spec_kitty.version (the product's sentinel)       -> null
  version not a string                                 -> null
  string not matching ^[0-9A-Za-z][0-9A-Za-z.+!_-]{0,63}$ -> null
  otherwise                                            -> the string (strict field: never redacted)
schemaVersion     get_project_schema_version(repo root): its integer, or null when it returns None
                  the CLI's coercion is the contract's ("3" gives 3, 3.9 gives 3, true gives 1)
health            healthy exactly when schemaVersion is not null and
                  MIN_SUPPORTED_SCHEMA <= schemaVersion <= MAX_SUPPORTED_SCHEMA (the serving build's range); else schema_drift
                  never depends on a drift finding (OR-8)
currentBranch     HEAD file (the gitdir when .git is a file); no subprocess
  ref: refs/heads/<name>      -> <name> (an unborn branch is its name)
  detached, no .git, unreadable or unparseable HEAD -> null
  name failing ^[A-Za-z0-9][A-Za-z0-9._/-]*$, longer than 255 characters,
  or matching the strict host-path patterns         -> null
lastActivityAt    the latest MissionHead.lastActivityAt over exactly the Missions GET /missions lists,
                  compared as instants, emitted as that Mission's own string;
                  null when no Mission is listed or every listed Mission has null activity
```

## Drift: the order of decision per Mission (FR-015, AD-10)

```text
0  the Mission directory under kitty-specs/        (a directory with an unreadable identity matches no ULID; it does not fail another Mission's report)
1  read directory: memo outcome
     directory                                    -> read it
     CoordinationBranchDeleted                    -> own directory; fallback Mission, reason coordination_branch_deleted
     any other resolver exception, outside root   -> 500 drift_scan_unreadable (no partial report)
2  meta.json in the own directory (load_meta_fail_closed)
     absent                                       -> names no coordination branch
     exists but corrupt, not an object, not UTF-8 -> 500 (MissionMetaReadError)
3  completion (the two arms, applied by the reader):
     own meta.json holds a merged_at instant, OR derive_mission_lifecycle(read directory) is recently_completed or archived
4  kind 1 / kind 2 over the read directory (see below)
5  kind 3, only for a Mission that step 3 reports not completed, and only now is lanes.json opened
```

**Status files (kinds 1 and 2).**

| `status.json` | `status.events.jsonl` | Outcome |
|---|---|---|
| absent | absent | no finding (nothing to compare; 2 of 569 here) |
| absent | present | kind 2, `artifactPath` `status.json`, `warning`, `remedy` `materialize_status` |
| present | absent | kind 2, `artifactPath` `status.events.jsonl`, `warning`, `remedy` null |
| not valid UTF-8, not JSON, or JSON but not an object | present (the population of kind 1 holds both files) | kind 1, `CORRUPT_JSON`, `error`, `laneComparison` `[]`; with the log absent the Mission is a kind-2 finding instead |
| unreadable (`OSError`) | any | 500 |
| valid | present, reducer raises (including an event log that is not UTF-8) | 500 |
| valid | present, equal under the classifier's normalisation | no finding |
| valid | present, differs | kind 1; `SNAPSHOT_DRIFT_PROVENANCE` when the difference is provenance-only (`actor`, `last_event_id`, `last_transition_at` per work package), else `SNAPSHOT_DRIFT_TERMINAL` when every work package of the reducer output is `done`, else `SNAPSHOT_DRIFT` (`error`) |

Kind 1 compares `status.json` with `materialize_snapshot(<read directory>)`, which replays at the generation recorded in the existing `status.json`; never `materialize`. `laneComparison`: one row per work package of the union whose `lane` differs, by `wpId` byte order; a work package on one side only has the other side null; a lane outside the nine display lanes (`genesis`, `uninitialized`) reads null; `[]` when the files differ only outside `lane`.

**`remedy`** is `materialize_status` for `SNAPSHOT_DRIFT` and `CORRUPT_JSON` and for a kind-2 finding whose log exists; null for the two warning variants, for a kind-1 error on a Mission merged to `main` (the own `meta.json` has `merged_at`), for kind 2 with a missing log and for kind 3. `materialize_status` is `spec-kitty agent status materialize --mission <slug>`; the client builds the text and takes the slug from `MissionHead.slug` of the finding's `missionId`.

**Kind 3 (`lane_branch_missing`; provisional).**

```text
population     every Mission step 3 reports not completed, in any lifecycle state, that has a lanes.json
lanes.json     raw JSON first:
                 object with mission_slug                       -> current shape: read_lanes_json / LanesManifest.from_dict
                 object with feature_slug and no mission_slug   -> legacy shape: not evaluated for kind 3; kinds 1 and 2 still apply; counted on the named list
                 anything else (not UTF-8, not JSON, not an object, neither key, current-shaped but refused by read_lanes_json) -> 500
code lane      every lane other than lane-planning
expected lane  one of its work packages is, in the reducer output, claimed, in_progress, for_review, in_review or approved
expected names code_lane_branch_name(mission_slug, lane_id) per expected lane, and, when any lane is expected,
               the coordination_branch that meta.json names, else the manifest's mission_branch (never both)
source         at most one `git for-each-ref refs/heads`, run once when the first Mission with an expected lane needs it
               non-zero exit, missing git, not a repository: 500 (never "every branch is absent"); zero listings when no Mission has an expected lane
finding        one per Mission when any expected name is not a local head: artifactPath lanes.json, warning, authority git,
               derivedSide lanes_json, laneComparison [], sourceCode null, remedy null; no branch name appears
```

**The fixed summaries** (the pair set is closed; a pair outside it is a reference-reader failure with a planted case):

| `kind` | `sourceCode` | `summary` |
|---|---|---|
| `snapshot_disagrees_with_event_log` | `SNAPSHOT_DRIFT` | The status snapshot disagrees with the event log. |
| `snapshot_disagrees_with_event_log` | `SNAPSHOT_DRIFT_PROVENANCE` | The status snapshot differs from the event log only in provenance fields. |
| `snapshot_disagrees_with_event_log` | `SNAPSHOT_DRIFT_TERMINAL` | The status snapshot differs from the event log and every work package is done. |
| `snapshot_disagrees_with_event_log` | `CORRUPT_JSON` | The status snapshot is not a valid JSON object. |
| `snapshot_or_event_log_missing` | null | One of the status snapshot and the event log is missing. |
| `lane_branch_missing` | null | An expected lane or Mission branch has no local branch. |

**Fixed fields by kind:** kind 1 and kind 2: `authority` `event_log`, `derivedSide` `status_json`; kind 3: `authority` `git`, `derivedSide` `lanes_json`. `severity`: `SNAPSHOT_DRIFT` and `CORRUPT_JSON` `error`, the two variants and kinds 2 and 3 `warning`.

**Order and cap.** Findings sort by `(missionId, kind, artifactPath)` in UTF-8 byte order; the key is unique (one finding per Mission, kind and artifact path), so the order is total. More than 1000: exactly the first 1000 and `truncated` true; exactly 1000: false. `scannedAt` is the service clock (`now_utc`) at the scan; the 200 documents `Cache-Control: no-store`.

**The 500 line (AD-10), as a table.** The report is refused 500 `drift_scan_unreadable`, never partial, when, for any scanned Mission: a resolver outcome other than a directory or `CoordinationBranchDeleted`; a read directory outside the repository; an `OSError` on `status.json`; an event log that cannot be reduced; `meta.json` corrupt, not an object, not UTF-8 or unreadable; `lanes.json` of a non-completed Mission neither current nor legacy shaped; or the branch listing failing while a Mission has an expected lane. Defined outcomes, not failures: a legacy-shaped manifest (counted); a `status.json` that is not UTF-8, not JSON or not an object (a finding); a fallback Mission.

## Ops: the order of decision per record (FR-016 to FR-019)

```text
candidate set   the distinct invocation ids of kitty-ops/ops-index.jsonl when it exists and can be opened (a corrupt line is skipped),
                else the Op files of the directory (names matching the 26-character Crockford ULID plus .jsonl);
                the index only supplies candidates: the profile filter, totalCount and the cursor binding use the profile_id of the Op's own started event
directory       absent                          -> 200, items [], totalCount 0, skippedCount 0, hasNextPage false
                exists but not listable / not a directory -> 500 ops_unreadable
spine           kitty-ops/op-closures.jsonl: OSError or invalid UTF-8 -> 500; a corrupt line is skipped
per candidate   no file (index entry without a file, or a file gone after listing)  -> skipped and counted
                OSError opening the file (other than FileNotFoundError)            -> 500
                first line empty, not JSON, not a v2 started event, stem differs from invocation_id,
                legacy started, started_at not an RFC 3339 instant with an offset, a required field failing its shape,
                invalid UTF-8 anywhere in the file                                  -> skipped and counted
completion      first own-file completed line that is valid -> closed from it
                else the first spine record in file order for the id  -> closed from it
                the own file wins when both exist; a legacy own completion with a spine record is served closed from the spine;
                a legacy own completion with no spine record skips the Op; a spine record for an id with no served Op is ignored
status          closed when a completion was found, else open
```

`totalCount` is the number of served Ops matching `profile` (the description says it can lag the newest records); `skippedCount` counts skipped records over the same candidate set, independent of `profile`. Order: `startedAt` descending as instants, ties by `invocationId` descending. The cursor is opaque, bound to `profile` and to the keyset position; a cursor issued for another `profile`, malformed or forged is 400 `invalid_page_cursor`.

Invariants checked by the reference validator: `open` implies `outcome`, `closedBy`, `completedAt` and `evidence` null; `closed` implies the first three non-null. A `mission_id` or `wp_id` failing its pattern makes the record unreadable (skipped), not null; only `actor` degrades to null.

## Evidence: the pipeline (FR-020)

```text
0  credential check on the stored evidence_ref, before everything, for every shape (SECRET_PATTERNS kinds): a match withholds the evidence:
   the Op is served, evidence null, nothing else changes, no marker, no failure
1  classify the stored string
     file:// URL (any case)                            -> kind text, value [path]
     other URL scheme (^[A-Za-z][A-Za-z0-9+.-]+://)    -> kind url; userinfo, query and fragment removed
     starts with /, ~/, two backslashes, or drive letter + colon -> kind text, the whole value [path] (also with whitespace)
     single line, no whitespace, passes the artifact-path rule   -> candidate kind repo_path
     otherwise                                         -> kind text
2  redact what step 1 did not replace: each embedded scheme:// run loses userinfo, query and fragment;
   each human host-path run becomes [path]; each address becomes [email] (redact_emails, never EMAIL_PATTERN);
   a repo_path candidate changed here becomes text; a url not parseable after 1(b) becomes text
3  a result over 512 code points is cut to 512, its kind becomes text, redacted is true
redacted       true exactly when value differs from the stored string
```

The `evidence` description says null means "no evidence, or withheld because it holds a credential", names the credential kinds checked (GitHub classic and fine-grained tokens, AWS access key id, private-key header) and says other secret shapes are not detected. `request_text` and `model_id` never leave the service.

## Status and refusal pairing

| Operation | Status | Code | Body |
|---|---|---|---|
| `getDriftReport` | 200 | | `DriftReport` (`Cache-Control: no-store`) |
| | 404 | `mission_not_found` | `DriftRefusal` |
| | 500 | `drift_scan_unreadable` | `DriftRefusal` |
| | 400 (a non-ULID `missionId`) | | the shared `Problem` under `default` |
| `listOpsInvocations` | 200 | | `OpsInvocationPage` |
| | 400 | `invalid_page_cursor` | the existing `PageCursorRefusal` response |
| | 400 (a `profile` failing its pattern) | | the shared `Problem` under `default` |
| | 500 | `ops_unreadable` | `OpsRefusal` |

## Closed vocabularies (pinned in `contracts/tools/enum_pins.json` under `mission-status`; all snake_case)

| Enum | Values | Producer (no dead value, AD-6) |
|---|---|---|
| `ProjectHealth` | `healthy`, `schema_drift` | project fixtures |
| `DriftKind` | `snapshot_disagrees_with_event_log`, `snapshot_or_event_log_missing`, `lane_branch_missing` | one fixture each; `derived_view_stale` is not a value |
| `DriftSeverity` | `error`, `warning` | `info` of the audit vocabulary is not carried |
| `DriftAuthority` | `event_log`, `git` | `meta` has no producer |
| `DriftSide` | `status_json`, `lanes_json` | `derived_views` has no producer |
| `DriftRemedy` | `materialize_status` | |
| `DriftRefusalCode` | `mission_not_found`, `drift_scan_unreadable` | |
| `OpsRefusalCode` | `ops_unreadable` | |
| `OpsModeOfWork` | `task_execution`, `advisory`, `mission_step`, `query` | one Op per mode |
| `OpsInvocationStatus` | `open`, `closed` | |
| `OpsOutcome` | `done`, `failed`, `abandoned` | |
| `OpsClosedBy` | `agent`, `doctor_sweep` | |
| `OpsEvidenceKind` | `repo_path`, `url`, `text` | |

Thirteen new enums, 29 values; the pin check line moves from `counts: enums=7 values=43` to `counts: enums=20 values=72` once all are pinned (planned; the figure is re-computed by the work package that adds the last pin). Titles are the schema file stems.

## Floors and the independent counts (plan D-P13; fixed at plan time, never re-pinned)

| Quantity | Plan-time measure | Floor | Independent count it is compared with |
|---|---|---|---|
| Missions examined | 569 | 540 | a scan for `meta.json` |
| Missions declaring no coordination branch, compared in the completion equality (AC-DRIFT 19, reality module) | 518 (569 less 51 declaring one) | 490 | a `meta.json` scan for Missions with no `coordination_branch` |
| Ops served | 473 | 440 | a direct scan of every Op file and of the spine |
| Spine-closed Ops | 6 | 5 | the spine's records whose Op is open in its own file |
| Own-file evidence: none / absolute / free text / relative | 351 / 32 / 56 / 28 | 330 / 28 / 50 / 25 | a regex classification of the stored strings |
| Evidence of kind `url`, a redacted address, a withheld credential | 0 | fixture-only | planted fixtures |
| Kind-1 findings | 44 (43 terminal, 1 provenance, 0 plain) | 39 | file presence plus `classify_status_json` filtered to the four codes |
| Kind-2 findings | 31 | 27 | the file-presence scan |
| Kind 3 | not measured under the final rule | **none** | equality with the oracle only |
| Fallback Missions | 37 (clone and network dependent) | **none** | the independent derivation, with the stale-entry check both ways |

**Named lists** (examined plus skipped equals discovered; a 500 outside a list or a stale entry fails): Ops whose own completion line lacks `closed_by` and with no spine record (7); the legacy-shaped `lanes.json` of a non-completed Mission, counted for kind 3 only (1, `064-complete-mission-identity-cutover`); the fallback Missions (37). `skippedCount` of the whole Ops walk equals the oracle's skipped list. A named anomaly fixture (`tests/contract/fixtures/mission_status_health_drift_ops_expected.json`) lists the 7 Op ids and the one legacy Mission by name as a subset check; the fallback Missions are never pinned.
