---
doc_status: draft
updated: '2026-11-28'
---

# Decision timeline

Synthesis S-B. Everything on this page is in the recorded-intent, approved-plan or proposed view and rests on document-claim evidence. It says what records state. It does not say what the code does.

Two tables support it:

- [decision-timeline.csv](decision-timeline.csv): 96 rows in date order. 68 are the steps of the ten supersession chains that workstream A1 reconstructed. 25 are single records that findings cite. 3 are block or ruling entries. Each row carries status at head, what was decided, what it supersedes and the finding ids.
- `evidence/A1/decision-timeline.csv`: the full index of 521 records, with status class, supersession fields and amendment markers. It is the reference for any record not in the selection.

## The population

| Repository | Records | Accepted | Partly superseded | Superseded | Proposed | Unstated |
|---|---|---|---|---|---|---|
| spec-kitty (core) | 239 | 183 | 0 | 30 | 26 | 0 |
| spec-kitty-charter | 83 | 59 | 22 | 0 | 2 | 0 |
| doc-kitty | 85 | 82 | 2 | 0 | 1 | 0 |
| spec-kitty-open-packs | 16 | 11 | 1 | 1 | 3 | 0 |
| spec-kitty-events | 8 | 8 | 0 | 0 | 0 | 0 |
| planning, decisions | 34 | 9 | 0 | 0 | 3 | 21 (plus 1 other) |
| planning, Kitty Shared Architecture v0.11 | 56 | 3 | 0 | 1 | 52 | 0 |

Source: F-A1-026, recounted from the index file. Status classes are heuristic (A1 deviation 5). The v0.11 set binds nothing until ratified, and no ratification was found (F-A1-036); it belongs to the proposed view.

Records per month, excluding v0.11: 21, 23, 5, 36, 14, 22, 27, 86, 91, 119, 77 from January to November 2026. October 2026 is the densest month (F-A1-026). Dates of 98 records come from git first-add, not from the record.

## The main lines, in date order

### Events and tracker packages: how core consumes them (chain CH1, 9 steps)

| Date | Record | Decided | Status at head |
|---|---|---|---|
| 2026-01-27 | core 2026-01-27-11 | Events library in its own repository, commit-pinned | accepted |
| 2026-01-31 | core 2026-01-31-1 | Vendor the events library into the CLI | accepted, reversed elsewhere without a status change (F-A1-017) |
| 2026-02-11 | core 2026-02-11-6 | Exact PyPI pin; git refs banned | accepted |
| 2026-04-25 | core 2026-04-25-1 | Events and tracker are external packages, public imports only; runtime package retired | accepted |
| 2026-08-27 | planning decision | For the programme: exact git SHA, never PyPI | ratified, programme scope |
| 2026-11-25 | core charter | Released PyPI packages, SemVer ranges, lockfile | current |
| 2026-10-29 | events charter | Keeps the programme exception live | current |

Two rules are live at head and no record ends the programme exception (F-A1-007).

### Charter: location and activation (chains CH2 and CH3, 18 steps)

| Date | Record | Decided | Status at head |
|---|---|---|---|
| 2026-08-02 | core 2026-08-02-1 | Charter is extractable in principle | accepted |
| 2026-10-12 | core 2026-10-12-2 | Charter becomes an external contract package in its own repository | superseded on 2026-10-19 |
| 2026-10-13 | charter ADR-0001 | A Java service with an OpenAPI contract | accepted |
| 2026-10-16 | core 2026-10-16-1 | Offering extracts first; activation rework after GA | accepted, amended twice in place |
| 2026-10-18, -19 | charter ADR-0008, ADR-0010 | Rewrite and replace; the Python charter stays in core; one switch-over; core governs only seam routing | accepted; supersede a core ADR from another repository |
| 2026-10-19 | core 2026-10-19-1; charter ADR-0013 | One activation ledger file with deny lists | accepted |
| 2026-10-20 | core 2026-10-16-1, amendment | Activation switch is a 4.0 deliverable; after cutover the service is authoritative and the ledger is its mapped copy | in force by amendment |
| 2026-10-24 | charter ADR-0020 | On divergence the service wins | partly superseded |
| 2026-10-26 | charter ADR-0033 | The local activation file is the source of truth; local wins | accepted; its decision 6 is superseded in part and decision 5 amended by later charter ADRs (index status line; those ADRs were not read here) |
| 2026-11-16 | open-packs charter | Operator ruling: the charter repository owns pack logic including activation | recorded only in open-packs |
| 2026-11-25 | core charter | Restates the 2026-10-20 position | current |

The last three rows are incompatible as written (F-A1-012, F-A1-013). A1's interpretation is that recorded intent for activation is not single-valued (F-A1-038). I keep that reading: the chain file shows three live statements and no record that orders them. Four active core records still state the superseded extraction direction without a marker (F-A1-010).

### Read service and event writer (chains CH4 and CH5, 13 steps)

| Date | Record | Decided | Status at head |
|---|---|---|---|
| 2026-10-01 | core 2026-10-01-2 | A read API replaces the bundled dashboard; modulith first | accepted, amended four times in place |
| 2026-10-03 | same, amendment | A separate Java read service | in force by amendment |
| 2026-10-12 | same, amendment | In core now, extracted when the contract freezes | overtaken |
| 2026-10-13 | core 2026-10-13-2 | The committed ledger is the publication seam | accepted |
| 2026-10-14 | core 2026-10-14-1 | One EventBridge writer behind a port | accepted |
| 2026-10-22 | core 2026-10-22-1 | A resident Java write service per repository; no Python writer | accepted; one amendment still Proposed |
| 2026-10-27 | core 2026-10-27-1 | Loopback HTTP with a bearer token | accepted |
| 2026-10-29 | core 2026-10-29-1; events ADR-0002 | Java services and contracts live in `spec-kitty-events`; core pins `service-v*` | accepted |
| 2026-11-06 | events ADR-0007, ADR-0008; core 2026-11-06-4, -6 | Coordination status written by commit and read from git objects | accepted in events, Proposed in core (F-A1-020) |

Two active core plan records still place the read service in core (F-A1-009).

### Event ordering (chain CH6, 5 steps)

Core decided Lamport-primary ordering on 2026-02-09 and amended it in place on 2026-10-22 to wall-clock order for 4.0.0. The events repository records Lamport as the decided target since 2026-10-15 and says it does not mirror core's amendment (F-A1-014).

### Hosted surfaces (chain CH7, 8 steps)

Client inversion on 2026-09-06, "no longer supported" on 2026-10-06, removal from open-core on 2026-10-14. The planning repository still names Team Kitty as what is being built (F-A1-008). The 2026-09-06 ADR keeps status Accepted with no amendment (F-A1-017).

### Packs (chain CH8, 8 steps)

open-packs became the source of the built-in pack on 2026-08-16; committed trees were replaced by pin and fetch on 2026-10-19. On 2026-11-04 open-packs ended compatibility with the as-is CLI. On 2026-11-11 the built-in pack became a distribution pack over member packs. On 2026-11-18 open-packs recorded that packs pin a charter release and the charter repository owns pack logic. Core's charter still says built-in content stays byte-identical in every install and its pin declares `requires_core >=4.0.0rc7,<5` (F-A1-015).

### Execution placement

Two core ADRs of 2026-06-02 place agent invokers in the external `spec-kitty-orchestrator` package, and an architecture page says external providers run agents and core has no `orchestrate` command (F-F-005). Core's charter says the SkyKitty fleet is switched off. This is the only recorded allocation of an execution responsibility found; see [execution-capability-matrix.md](execution-capability-matrix.md).

## What superseded what, across repositories

Six of the ten chains cross repositories (F-A1-027). The cases where a record in one repository changes a decision recorded in another:

| Decision | Changed by | Marked in the original? |
|---|---|---|
| Core 2026-10-12-2, charter extraction | charter ADR-0008 and ADR-0010 | yes, status Superseded |
| Charter ADR-0020 decision 5, "service wins" | charter ADR-0033 | yes, in the charter repository; core's charter still states the earlier position |
| Core's pack ownership | open-packs charter and ADR 2026-11-19-3 | no core record |
| Core's built-in pack compatibility | open-packs ADR 2026-11-04-1 | no core record |
| Core 2026-02-09-3, ordering | events ADR-0001 keeps a different target | each names the other; neither yields |

No record in any repository states a general precedence order among the repositories (F-A1-003).

## How reliable the status field is

- Core records say ADRs are immutable and superseded explicitly. In practice 77 of 239 core ADRs carry amendment markers, 33 of 52 in the 4.x era, and 61 of 83 in the charter repository (F-A1-018). The counts are lower bounds.
- 26 of 239 core ADRs are Proposed. Four say the operator accepts them by merging. One Proposed ADR has six amendments that record its execution (F-A1-019).
- At least two Accepted core ADRs state decisions that later records reverse, with no status change (F-A1-017).
- Six core ADR identifiers are each used by two or three files (F-A1-028). A citation by identifier alone can be ambiguous.

A1's interpretation is that status and title alone do not tell a reader which decision is in force (F-A1-037). My reading of the same four observations agrees. It follows that the "status at head" column in the CSV is the recorded field, not a judgement of what is in force.

## Approved plans, kept apart

Thirteen approved future changes were found (F-A1-033, `evidence/A1/approved-plans-vs-proposals.csv`). The ones that change an owner or a location:

| Plan | Approved | Observed state at head |
|---|---|---|
| All offering reads route to the charter service through `charter.offering.api` in one switch | 2026-10-19 | Core has no client and no charter pin (F-D2-017) |
| Activation switches to the charter surface as a 4.0 deliverable | 2026-10-20 | Core's own file and engine (F-D2-017) |
| The Java write service becomes the one event writer | 2026-10-22 | Core's Python writer performs every write; a rehearsal with the released rc.2 worked (F-D2-012, F-D2-017) |
| Core pins the write service and the charter service | 2026-10-29 | No such pin (F-D1-001) |
| Packs pin a charter release; the charter repository owns pack logic | 2026-11-16, -18 | open-packs pins charter rc.3 (F-B2-024) |
| doc-kitty reads Missions through a mission-status contract reader | 2026-11-23 | Not observed |

A plan that is not yet carried out is not a deviation.

## Decisions that could not be read

| What | Why | Effect |
|---|---|---|
| The full analysis behind the 2026-09-27 alignment review | Stated to be in a private repository (F-A1-035) | Only its engine-side page was read |
| Records of `spec-kitty-go` | Repository not attached (coordinator notes) | A core ADR that refers to it could not be followed |
| The operator ruling of 2026-11-16 as an original record | Found only as a restatement in open-packs (F-A1-027) | Its exact wording is unknown |
| Tracker repository records, GitHub issues, most of planning `docs/` | Outside A1's coverage | Decisions recorded only there are missing |
| 432 of 521 indexed records | Indexed, not deep-read: A1 read 89 in depth, 40 by seeded sample and 49 because they change ownership, location or contract | Their status and supersession fields are heuristic |
| Chains for core's internal mechanics (consolidation, lanes) | Not reconstructed (F-A1-027) | Not in the timeline |
| 21 of 34 planning decisions | No machine-readable status line (F-A1-004) | Listed as "unstated" |
