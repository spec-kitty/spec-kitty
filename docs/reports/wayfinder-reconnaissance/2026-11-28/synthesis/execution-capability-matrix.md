---
doc_status: draft
updated: '2026-11-28'
---

# Execution capability matrix

Synthesis S-B, measure M07. This page says where each of the fifteen execution responsibilities sits and in what state. It assigns no hypothesis verdict. The source is workstream F (profile `analyst-annie`), whose classification is in `evidence/F/m07a-execution-responsibilities.csv`. The split rows and the state vocabulary of this page are in [execution-capability-matrix.csv](execution-capability-matrix.csv), 22 rows.

The matter here is allocation of responsibility. The absence of a component with a particular name is not a deficiency (ruling R5).

## 1. Vocabulary

| State on this page | F's state | Meaning |
|---|---|---|
| implemented | verified by execution | Named tests pass at head, or a command was run. It does not mean every path is covered (F, deviation 3) |
| delegated | delegated by recorded intent | A record places it outside core |
| specified but unimplemented | specified only | A contract or document exists; no implementation found |
| intentionally out of scope | out of scope by recorded intent | A record excludes it. No row has this state |
| absent | missing | No record and no implementation in any repository read |

Loci: core runtime; external tool (the agent CLI or IDE); human operations; external coordination (`spec-kitty-orchestrator`); other ecosystem component.

F assigned one locus per responsibility, the holder of the operative act, and noted the rest as secondary (F, deviation 2). Several responsibilities are in fact split. This page shows the parts.

## 2. The fifteen responsibilities

| # | Responsibility | Where it sits | State | Findings |
|---|---|---|---|---|
| X01 | Resource identity | Core runtime: actor, profile and claim PID on status events and Op records | implemented; caller-asserted | F-F-001, F-F-004, F-F-013 |
| | session and attempt identifiers | Other component: `spec-kitty-events` contracts | specified but unimplemented; no producer in core | F-F-013, F-F-015 |
| X02 | Context preparation | Core runtime: `spec-kitty dispatch`, profile invocation | implemented | F-F-003 |
| X03 | Workspace provisioning | Core runtime: lane worktree per lane | implemented, for work packages only | F-F-001 |
| X04 | Dispatch, starting the executor | External coordination, or the agent tool starting itself | delegated by record; the external implementation ran 9 of 10 end-to-end tests against core head | F-F-005, F-F-003, F-F-018 |
| X05 | Profile selection | Core runtime | implemented | F-F-014 |
| | model selection | External tool | absent in the ecosystem: advisory recommendation; the model that ran is recorded nowhere | F-F-014 |
| X06 | Lifecycle supervision: detection | Core runtime | implemented, detection only | F-F-011 |
| | timeout enforcement | External coordination | implemented; verified by the workstream's probe, no project test | F-F-011 |
| X07 | Cancellation: stopping a running unit on request | None | absent | F-F-012 |
| | recording a cancellation | Core runtime | implemented, record only | F-F-012 |
| X08 | Handover between executors | Core runtime and external coordination | implemented at state level; no transfer of an in-flight context | F-F-025 |
| X09 | Evidence collection | Core runtime | implemented; evidence is self-reported | F-F-001, F-F-004 |
| X10 | Event publication: local append | Core runtime | implemented | F-F-016 |
| | transport to outside consumers | Other component, a transport owner | delegated by record; no implementation found | F-F-016, F-F-019 |
| X11 | Reconciliation after interruption | Core runtime; external coordination for adoption on resume | implemented and tested per holder | F-F-017 |
| X12 | Permissions: repository authority | Core runtime | implemented | F-F-001, F-F-010 |
| | executor sandbox, network, approval mode | External tool | absent in the ecosystem: self-declared metadata that no code reads | F-F-010 |
| X13 | Human attachment to a running unit | None; the agent tool's own interface | absent | F-F-024 |
| X14 | Dependency eligibility | Core runtime | implemented | F-F-001 |
| X15 | Acceptance of an executed unit | Core runtime | implemented | F-F-001 |

Evidence kind: executed, through 14 batches of named core test files (1,182 passed, 0 failed, `evidence/F/core-tests-summary.txt`), CLI runs in a disposable clone, the orchestrator's own tests, and one probe; static-derived for the "absent" rows. Revision: core head, `spec-kitty-orchestrator` 8be32b1.

## 3. Counts

By F's single-locus rule (F-F-001):

| | Count |
|---|---|
| Locus core runtime | 11 |
| Locus external coordination | 2 (dispatch, supervision) |
| No locus | 2 (cancellation, attachment) |
| State verified | 12 |
| State delegated by record | 1 (dispatch) |
| State missing | 2 |

The comparator, fifteen mission-coordination responsibilities: 14 in core, 1 in `spec-kitty-events` (ordering of status events), 15 of 15 verified (F-F-002).

### The share depends on the denominator

The pre-registration computes the verified share "over responsibilities that recorded intent places inside the ecosystem". F's artefact has a column for exactly that.

| Reading | Execution share | Coordination share |
|---|---|---|
| F's: all except the one delegated by record | 12 of 14 (85.7%) | 15 of 15 |
| Strict: only rows where the artefact says a record places it inside | 11 of 11 | 15 of 15 |
| Split rows of this page, parts a record places inside | 12 of 13: the unproduced session and attempt identifiers are the one "specified but unimplemented" part | not split |

For supervision, cancellation and attachment the artefact says no record places them in core or anywhere (`m07a-execution-responsibilities.csv`, column `record_places_inside_ecosystem`). Whether they belong in the denominator is a question of what "recorded intent places inside the ecosystem" means when the records are silent. I do not settle it. The three readings are given so that the choice is visible.

Two procedure notes weigh on the comparator: the coordinator records that the comparator list was not committed before classification (F wrote it to a file with an earlier timestamp and could not commit); and the fifteen coordination items are the fifteen examples that F's brief listed, so the comparator set was in effect chosen by the coordinator.

## 4. What the allocation looks like

F's interpretation (F-F-027): core holds the responsibilities that record, prepare and gate a unit of agent work; starting, supervising and stopping an executor are held by an external provider or by no one. I reach the same reading from the artefact and add three qualifications.

1. **"Implemented" is narrower than the row name in five rows.** Profile is selected, model is not (X05). Publication is a local append (X10). Permissions are repository authority, not executor confinement (X12). Handover is a state change (X08). Supervision in core is detection (X06).
2. **The delegated part has one working provider and one consumer contract.** `spec-kitty-orchestrator` drives core through the orchestrator API only and passed 9 of 10 fake-agent end-to-end tests against core head; the failure is its own exact-version assertion (F-F-018). Real-agent tests were not run (no credentials).
3. **The provider's interface is narrower than the host CLI.** The orchestrator API's consolidate verb takes 5 options against 33 on the CLI and has no resume, abort, dry-run or attestation; its own failure text tells callers to run host CLI commands (F-F-009). Its delivery profile lists 13 capabilities as unavailable, among them leases, watch and remote serving (F-F-006).

### Units and their identifiers

Fourteen unit identifiers were mapped (F-F-013, `unit-identifiers.csv`). Eight are minted in core: Mission, work package, lane, status event, Op invocation, `next` run, API correlation id, claim PID. Three exist only as events contracts with no producer. Two are local to the orchestrator. The Op and the work package are joined one way: a claim can check an Op, and the status event stores no invocation id. The correlation id is not persisted. An Op record carries no process, host, session, model or attempt (F-F-004).

### Interruption

Each record holder has a documented, tested recovery: work package (`implement --recover`), consolidation (`--resume`, `--abort`), Op (`doctor ops`), orchestrator run (resume adoption) (F-F-017). No holder records what a stopped executor was doing. Scenario AS-08 is therefore verifiable for identification and state recovery, and not for the executor's own progress.

A separate observed fact about a Mission as the unit: a `research` Mission stalls at its third step through the documented surface, because no documented command produces the event its guard counts (F-E1-028, F-E1-029, executed; pre-registered experiment PX-01).

### External loci

| Locus | Took on | Interface to core | Recorded status |
|---|---|---|---|
| spec-kitty-orchestrator | dispatch, timeout, retries, fallback agents, resume adoption | orchestrator API, 8 verbs | last commit 2026-10-23 |
| spec-kitty-mcp | adapts 10 API verbs to tools; runs no agents | orchestrator API | last commit 2026-08-22 |
| spec-kitty-container | an environment for a human-run session | packages the CLI (default 3.2.2) | documents removed commands |
| fleet-kitty | issue-driven factory: own dispatch, heartbeats, workers | 3 CLI command strings; no orchestrator API | calls itself active; no core document names it |
| event-router | named as subscriber side | none | bootstrap, no code |

Source: F-F-019. fleet-kitty was read at README and search level only.

### Prospective operations (desk classification)

F classified submit, inspect, attach, cancel and collect for five targets: 25 cells, 9 verified, 2 present but unverified, 1 specified only, 13 missing (F-F-021). Attach is missing for all five targets. Every remote-worker cell is missing in core. This is a desk classification except where an executed test is named in `prospective-operations-matrix.csv`. It maps existing surfaces onto operations proposed from outside; a "missing" cell is not a defect against recorded intent, because no record asks for these operations.

## 5. Single case: what this investigation needed

Kept apart. One case, the coordinator's own account (`operations-log.txt`), not to be generalised without corroboration (ruling R7).

F checked each of 15 items: 9 corroborated, 4 partly, 2 not (F-F-022, `ops-log-corroboration.csv`).

| Need of the investigation | Provided by | Corroboration |
|---|---|---|
| Governance context and profiles | native CLI | corroborated |
| A Mission as the container | created natively; its steps not advanced with `next` | corroborated |
| Splitting into parallel units, starting each, choosing its model, passing its brief | the external agent tool | corroborated for the root checkout: 0 Ops opened after the Mission's creation |
| Identity of a unit of work | a workstream id invented by the coordinator; no work package, lane or Op | corroborated: the Mission has 0 work packages and no `lanes.json` |
| Isolation between units | written instruction only | corroborated at the file-system layer: restricted files are readable by every executor |
| Liveness, completion, cancellation, collection | the external agent tool | corroborated by absence in core; the tool itself was not inspected |
| Disposable environments | made by hand by each executor | corroborated for F's own run |
| Evidence format and storage | defined by coordinator and architect | partly: not a Mission artifact kind; the research Mission type has its own evidence artifacts, which were not used |
| Review independence, replication | arranged by the coordinator | not corroborated |
| Approvals | given in chat | partly: files exist |

Read against section 2, the single case agrees with the allocation: what core supplied was context and the Mission scaffold; starting, model choice, liveness, cancellation and collection came from outside (F-F-023). It adds one thing the matrix does not show: a parallel unit of work that is not a work package had no native identity at all.

Two cautions. The case was shaped by deviation D-1: the workstreams were deliberately not run through the mission runtime, so it cannot show what the runtime would have supplied. And the procedure notes record that isolation by instruction did fail twice in this run (B3 and H06a read material they should not have), which is consistent with entry 7 of the log and is still one case.

## 6. Limits

- Agent CLIs' internals and fleet-kitty's runtime were not examined.
- The `next` run's own interruption path was not covered.
- `spec-kitty-go`, which a core ADR is said to cite for a second orchestrator, is not attached.
- "Implemented" rests on named test files and CLI runs at head in a disposable clone. An installed wheel was not used for these checks.
- Desk assessments (the prospective operations matrix, AS-10) are not empirical verification.
