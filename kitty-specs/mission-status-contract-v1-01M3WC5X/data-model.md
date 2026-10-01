# Data Model: Mission Status contract v1

Phase 1 output of the plan. The authoritative field catalogue is the spec's "Contract Field Catalogue"; this file does not repeat it. It records the entities, the derivation and projection rules the implementation must follow, the invariants the checks enforce, and the one state machine involved. Rules marked `x-derived` in the contract are written in the schema descriptions; the single authority for each is that description, and the helper in `tests/contract/` is its executable copy.

## Entities

| Entity | Identity | Source of truth | Notes |
|---|---|---|---|
| Project | project slug | `.kittify/config.yaml` `project.slug`; `ProjectIdentity` in `specify_cli/identity/project.py` | Two fields only: `name`, `missionCount`. No path, no tokens. |
| Mission overview | `missionId` (26-character Crockford ULID) | `meta.json` through `resolve_mission_identity` (`specify_cli/mission_metadata.py`) and the status snapshot through `materialize_snapshot` (`specify_cli/status/reducer.py`) | `displayNumber` is display-only and repeats; `mid8` is null when there is no Mission id. |
| Mission detail | `missionId` | Overview plus phases and work package summaries | Exactly five phases. |
| Work package | `(missionId, wpId)` | Authored plan from `read_authored_wp_frontmatter` (`specify_cli/status/wp_metadata.py`); resolved state from the snapshot (`reconstruct_wp_view` in `specify_cli/status/wp_view.py`) | Resolved state never comes from stale frontmatter keys. |
| Event | `eventId` within one Mission's log | `status.events.jsonl` rows, projected by allow-list | Three kinds only. |
| Stream cursor | one physical event log | `TailCursor` in `specify_cli/status/tail_reader.py` | Field `invariant` is `content_invariant` in the source; bound to one file. |
| Page cursor | opaque token | `contracts/_shared/` | No schema relationship to the stream cursor. |
| Problem | n/a | `contracts/_shared/` (`application/problem+json`) | The only non-2xx body. |

## Vocabularies (closed, ungrouped)

- **StatusLane** (nine display values): planned, claimed, in_progress, for_review, in_review, approved, done, blocked, canceled. Source: the `Lane` enum in `specify_cli/status/models.py` (it also carries `genesis` and `uninitialized`, which are not display values: an event-less work package reads as a null `statusLane`, and `statusLaneCounts` has exactly the nine keys, all required).
- **LifecycleStatus** (five): active, planned, done, draft, discarded.
- **Topology** (five): lanes, single_branch, coord, lanes_with_coord, unknown. A Mission with no stored topology (49 of 539 at measurement), or a stored value outside the four known shapes, is `unknown`; it does not inherit the runtime's "unstamped means lanes" default. Unrelated to `MissionStatus.topology` (`legacy` or `coordination`) in `specify_cli/status/aggregate.py`.
- **Mission phase** (five, contract field `phases`): specify, plan, tasks, implement, review. Not the glossary `phase`. **Phase label** (`phaseLabel`) is the free-text frontmatter `phase`. **Lifecycle status** is Mission-level. Three different things.

## Derivation rules (contract-owned, `x-derived`)

**Lifecycle status** from `statusLaneCounts`, `wpTotal`, `discardedAt`, `acceptedAt` (D-5), evaluated in order:

| Order | Condition | Value |
|---|---|---|
| 1 | `discardedAt` set | discarded |
| 2 | `wpTotal` is 0 (including an unreadable event log) | draft |
| 3 | any work package claimed, in_progress, for_review, in_review or approved | active |
| 4 | none of the above and any work package planned or blocked | planned |
| 5 | otherwise (every work package done or canceled) | active until `acceptedAt` is set, then done |

Pinned quirks: a Mission whose only remaining work packages are blocked reads as planned; all-canceled with `acceptedAt` set reads as done. `wpTotal` is `len(snapshot.work_packages)`, so it may differ from the number of `tasks/WP*.md` files (52 Missions at measurement); that difference is a counted, ceilinged list, never a silent one.

**Mission phases** (FR-005):

| Phase | complete | in_progress | pending | basis |
|---|---|---|---|---|
| specify, plan, tasks | the matching file (`spec.md`, `plan.md`, `tasks.md`) exists; else the matching `...Completed` lifecycle event exists | the matching `...Started` event exists | otherwise | `artifact` or `lifecycle_event` |
| implement | `wpTotal` above 0 and every work package is for_review, in_review, approved, done or canceled | any work package has left planned or blocked | no work package has left planned or blocked (including zero work packages) | `derived_from_status_lanes` |
| review | `wpTotal` above 0 and every work package is done or canceled | any work package is for_review, in_review, approved or done | none of those | `derived_from_status_lanes` |

Implement is evaluated before review. The seven lifecycle event type constants are in `specify_cli/status/lifecycle_events.py`.

**readyToStart**: true only when `statusLane` is `planned` and the readiness result (`dependency_readiness_for_wp` in `specify_cli/core/dependency_graph.py`) is satisfied; false for every other lane, including null. **blockedCount**: `statusLaneCounts.blocked`. **lastActivityAt**: the maximum work package `lastTransitionAt`. **missionCount** (project): the number of overview records.

## Projection rules

**Actor** (D-10): `{tool, role, profile}`, each a nullable `ActorHandle` (letters, digits, `.`, `_`, `:`, `-`; no `@`, no `/`, no whitespace; at most 128 characters).

| Stored form | Projection |
|---|---|
| Structured actor with `tool`, `role`, `profile` keys (and possibly `model`) | Field by field through the handle filter; each becomes null when null or failing the pattern; `model` is dropped |
| Plain string matching the pattern (for example `user`, `finalize-tasks`, `migration`) | `tool` = the string, `role` and `profile` null; colon-encoded values are not split |
| Any other string (e-mail, contains `@`, `/` or whitespace, longer than 128) | all three null |

**Event stream** (D-8, D-9, FR-007), allow-list from `status.events.jsonl`:

| Source row | Kind | `missionId` | `at` | `eventId` |
|---|---|---|---|---|
| status transition (has `to_lane`) | `status-transition` | `meta.json` `mission_id` | row `at` | row `event_id` |
| lifecycle row whose `event_type` is MissionCreated, SpecifyStarted, SpecifyCompleted, PlanStarted, PlanCompleted, TasksStarted or TasksCompleted | `mission-lifecycle` | `meta.json` `mission_id` | row `timestamp` | row `event_id` |
| anything else (annotations, WPCreated, ReviewerSelfApproval, decision-point rows, retrospective rows, unknown kinds) | dropped, counted per event type, never forwarded | | | |

`missionId` never comes from `aggregate_id`. A third kind, `log-truncated`, is emitted by the (future) reader when the tail reader signals truncation (`size_shrink` or `content_mismatch`), with a reset cursor at offset 0 and the empty digest.

**Stream cursor string form** (D-18): `<offset>:<invariant>` (decimal byte offset, colon, 64 hex characters); the same string is the SSE `id:` and the `Last-Event-ID` value; the JSON object `{offset, invariant}` is the form inside `data`. A cursor requires `missionId`; an unscoped stream is live-only; order is per Mission only; a heartbeat comment line every 30 seconds.

**String field classes** (D-14): authored markdown (`promptMarkdown`, on request only) passes through and is excluded from corpus-payload scans but scanned in `examples/`; strict fields (ids, handles, branch names, `missionType`, dependencies, owned files, requirement refs, subtask ids, tracker refs) become null where nullable and otherwise are a projection error; human text fields (titles, friendly names, phase labels, every `reason`, review `reference`, `nextAction`) pass through when clean and have only the matching substring replaced by `[path]` or `[email]` when not. Every redaction is printed with its Mission and field.

## Invariants (what the checks enforce)

1. Every response object schema is closed (`additionalProperties: false`, or `unevaluatedProperties: false` where composed); documented open maps are the only exceptions.
2. Every property of every resource schema, at any depth and including properties reached only through `$ref`, carries `x-source` or a structured `x-derived`; the two counts sum to the computed property count, which is above zero.
3. `x-source` resolves by defined name (def, class, or module- or class-level assignment or annotated target) in the cited file, or by key path in YAML or JSON; a name in a comment or string does not resolve.
4. `x-provisional` elements carry a description naming the open decision on #5528; provisional fields are nullable.
5. No property is named like a host path, and no value in a payload, example or contract file is an absolute host path or an e-mail address (per field class).
6. The bundle is never tracked; two builds are byte-identical; the resolver's tree equals the bundle's after the named normalisations.
7. `missionId` is unique across the corpus; `displayNumber` is never an identifier.
8. The reality check changes no tracked file under `kitty-specs/`.

## State machine involved

The only lifecycle in play is the work package lane machine of the status domain (planned, claimed, in_progress, for_review, in_review, approved, done; blocked from every non-terminal lane; canceled from every lane; `done` and `canceled` terminal). The contract exposes lane values and transitions read-only. It adds no state and no transition, and a transition appears in `history` only as `kind: transition`.
