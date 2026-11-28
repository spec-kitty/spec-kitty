---
doc_status: draft
updated: '2026-11-28'
---

# S-B phase 1: evidence-first reading

Synthesiser S-B (`synthesizer-sam`). Written before opening `findings/`, `workstream-reports/` or `synthesis/sealed/`.

## 1. What this reading rests on

- Read: rulings, pre-registration, approval record, coordinator procedure notes, operations log, the briefs of A1, D1, D2 and F, and the common synthesis brief.
- Read in full from `synthesis/input/observations-index.csv`: the claims of A1 (36), A2 (19), B1 (25), B2 (33), B3 (12), D1 (30), D2 (20), F (26), CX (13).
- Read truncated (first 200 to 420 characters): C, C2, E1, E2, E3, G1, G2, H06a, H06b. Fourteen of those were then read in full (F-E1-004, -008, -028, -029, -032, -033, F-E3-006, F-G1-009, -011, F-G2-001, F-H06a-008, -017, -019, -021).
- Raw artefacts opened: `evidence/A1/component-catalogue.csv`, `supersession-chains.csv`, `documented-relationships.csv`, `approved-plans-vs-proposals.csv`, the header and status counts of `decision-timeline.csv`; `evidence/B1/layer-edges-head.csv`, `m03a-enforced-model-head.json`; `evidence/B2/xrepo-pin-matrix.csv`; `evidence/B3/m03b-summary.json`; `evidence/D1/revision-table.csv`, `independence-matrix.csv`, `m04e-status-seam-stub.txt`; `evidence/D2/independence-matrix.csv`, `m04c-contract-bypass-inventory.csv`, `m04f-core-service-cli-absent.txt`, `m04f-core-status-write-without-service.txt`; `evidence/F/m07a-execution-responsibilities.csv`, `m07b-coordination-classification.csv`, `coordination-responsibilities.txt`, `core-tests-summary.txt`, `timeout-probe.txt`, `prospective-operations-matrix.csv`, `unit-identifiers.csv`, `ops-log-corroboration.csv`, `orch-e2e-summary.txt`.
- Synthesis-run: `ls pins/ packs/` in `/home/user/spec-kitty` (working tree at `5a66c0fc92`, the research branch). `pins/` holds `README.md` and `read-service.source.yaml` only. This agrees with F-D1-001 and F-D2-017.
- Not opened in phase 1: most raw artefacts of C, C2, E1, E2, E3, G1, G2, H06a, H06b. Statements below that cite those workstreams rest on the claim sentence and are marked "claim only".

The two independence matrices under `evidence/D1` and `evidence/D2` carry the investigators' cell values. They are part of the measure, not interpretation records, but they are judgements. Section 4 gives my own cell reading from the counts and marks where it departs.

## 2. Components and capabilities

Recorded-intent, document-claim. A1 names 40 components or capabilities (F-A1-029, `evidence/A1/component-catalogue.csv`). Three decompositions of core coexist in the records (F-A1-030): eight landscape containers plus four layer packages; four bounded modules plus an Op tier; the six-package enforced chain. Only some records say which wins.

Observed, static-derived, head. Core Python is 1,490 modules and 524,936 physical lines in 74 components (F-B1-001, F-B1-006). `specify_cli` holds 77.6% of the lines (F-B1-013). The charter repository is 18 Gradle projects with 124,725 Java main lines, 61.5% of them in the one module `packs` (F-B2-001). The events repository holds six Gradle projects (17,131 Java main lines) and one Python distribution (18,399 lines) (F-B2-008). doc-kitty is three workspace packages (F-B2-018). open-packs holds 19 packs at head (F-B2-022).

Naming does not line up between the records and the code. Of 74 observed components, 51 have no counterpart in the documented relationship table below their parent package; of 72 documented relationship rows, 14 resolve to a pair of observed components (F-B3-007).

My inference: the component catalogue has to carry two keys per row, the recorded name and the observed unit, and several rows will have only one of them.

## 3. Decisions

Recorded-intent, document-claim. 521 decision records were indexed (F-A1-026). Status classes are heuristic. October 2026 holds 119 of the 465 records outside the v0.11 set. Dates for 98 records come from git first-add.

Ten supersession chains were reconstructed for ownership, location or contract (F-A1-027, `supersession-chains.csv`, 68 steps). Six cross repositories. Reading the chain file:

- Charter location: extraction to its own repository was Accepted on 2026-10-12 and marked Superseded on 2026-10-19 by two records in the charter repository. The replacement is a frozen seam with a Java service behind it.
- Read service location: in-core modulith, then separate Java service, then "extract when frozen", then `spec-kitty-events` on 2026-10-29.
- Event writer: publication seam (2026-10-13), one EventBridge writer (2026-10-14), resident Java write service (2026-10-22), built in `spec-kitty-events` (2026-10-29).
- Hosted surfaces: client inversion (2026-09-06), unsupported (2026-10-06), removed (2026-10-14).
- Pack logic: core, then the charter repository by a ruling of 2026-11-16 that is recorded only in open-packs.

Decisions change mostly by in-place amendment, although core records say ADRs are immutable (F-A1-018): 33 of 52 core 4.x ADRs and 61 of 83 charter-repository ADRs carry amendment markers. The status field is not a reliable guide: 26 of 239 core ADRs are Proposed, and some of these are in force by their own text (F-A1-019). Six core ADR identifiers are used by more than one file (F-A1-028).

Records at head disagree on several ownership questions (F-A1-005 to F-A1-025). The ones that bear on my deliverables: owner of activation logic (F-A1-012), authority over activation after cutover (F-A1-013), event ordering target (F-A1-014), pack compatibility with the CLI (F-A1-015), read-service location in two active core plans (F-A1-009), mission-status contract owner as doc-kitty names it (F-A1-025), and the distribution rule for the events and tracker packages (F-A1-007).

Thirteen approved future changes were found (F-A1-033). All are approved-plan and must not be read as observed.

## 4. Dependencies

### 4.1 Intended

Enforced tier (recorded-intent, with the gate named): `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`, plus two shrink-only ledgers for `runtime -> specify_cli` and `mission_runtime -> specify_cli`. Documented tier: 72 relationships, 23 recorded as enforced by a named test and 49 documented only (F-A1-031). Nine units have no recorded internal structure.

### 4.2 Observed in core, head

- Top level: 14 package-to-package edges (`layer-edges-head.csv`). `kernel` imports no other package and `charter` imports only `kernel` in the static graph (F-B1-009).
- Enforced tier: 0 unrecorded violations by static check and by the gate's own collector functions run in a clone (F-B1-010; the pytestarch rules themselves did not run, memory limit). 48 ledger entries stand for 228 upward import statements (F-B1-011). One string-literal dynamic import, `charter.offering` to `glossary.attachment`, sits outside the rule's graph and the rule's docstring says so (F-B1-012). G2 counts the same import as an unrecorded row and as a `charter`/`glossary` cycle (F-G2-001, claim only). Both readings are kept.
- Below the six packages: 656 component edges; 62 of 74 components sit in a cycle counting all imports, 50 counting load-time imports (F-B1-007). At module level, load-time cycles are 10 of 1,490 modules, none crossing a component (F-B1-004).
- Documented tier: at top level 11 of 14 edges match a documented relationship; at 74 components 162 of 656 (24.7%) do; 465 edges (70.9%) connect pairs no record speaks to (F-B3-001, -002, -006). The granularity moves the share by 54 points, far more than any rule choice (F-B3-009).
- 92.8% of source lines are in units for which the enforced model states no internal structure (F-B1-013).
- Private access: 734 of 10,427 cross-component imported names reach something marked private (F-B1-014). G1 reports 593 entries under different rules at six-package level (F-G1-003, claim only). Different scopes; not comparable.
- Shared files: `status.events.jsonl` paths are built in 14 components, with a write call nearby in 4 (F-B1-016). D1 counts 140 literals in 65 files outside the owning package (F-D1-011). G1 counts 128 non-owner files, 34 with a write primitive (F-G1-009, claim only).

### 4.3 Observed across repositories

- 33 pin or lock surfaces (F-D1-001, `revision-table.csv`). The pin graph over the five repositories has 11 edges and two two-node cycles: core with events, charter with open-packs (F-B2-027).
- Reverse pins: events pins core commit `512567ee`, 4,369 commits behind core head, for CI oracles (F-D1-012). The charter repository pins a core commit in a corpus script (F-B2-025).
- Core holds no pin of the charter repository and no write-service pin (F-D1-001, F-D2-017; synthesis-run agrees).
- The Java services read core's project files directly: 10 input items with no machine-readable schema (F-D2-008). Ten formats or rule sets are defined on both sides of a service boundary (F-D2-010).
- Released events contract bundles cite core source paths as the origin of their properties, 317 and 182 lines (F-D2-009).

### 4.4 Head, core-pin, released

- Events Python: head 11.5.0 unpublished; core's range admits exactly one published version, 11.3.0, equal to the lock (F-D1-003). Tracker likewise, 0.5.2.
- Built-in pack: core's pin is 665 commits behind open-packs main and is not an ancestor of it (F-B2-026). At the pin the pack tree is one 505-file pack; at head it is a 5-file distribution pack over six member packs (F-D1-023). Core's validator accepts 5 of 5 packs at the pin and 0 of 19 at head (F-D1-021, executed).
- Read service: rc.1 pinned, rc.2 exists and meets the pinned fixtures (F-D2-011).
- Released wheel 4.0.0rc8 carries the same external pins as head. Stable 3.2.7 depends on events 6.x and tracker 0.4.x (F-D1-006).
- Development versus distribution: a source checkout does not import until the built-in pack is fetched (811 of 1,490 modules fail, F-B1-022); the wheel is self-contained (F-D1-007). Core's seam tests cannot be pointed at an installed wheel (F-D1-014).

## 5. Independence, my cell reading

Rule I applied. Established: the count shows no bypass or a passing executed test. Partly: the interface or owner exists and carries part of the traffic, or the test passed in one direction only. Not established: no such interface, or the capability has no separate form on that dimension. Not claimed: a record declines the dimension. Not assessable: blocked or not measured.

| Capability | Logical | Contract | Source | Distribution | Deployment |
|---|---|---|---|---|---|
| Charter activation | partly | partly | not established | not claimed | not claimed at head |
| Charter offering (Python in core) | partly | partly | not assessable | not claimed | not claimed at head |
| Charter service (Java) | not established as sole owner at head | partly | partly | established | established as a unit |
| Events contracts, Python package | partly | partly | partly | established | not applicable |
| Events contracts, Java bundles | partly | partly | partly | established | not applicable |
| Status ledger and reducer | partly | partly | partly | not separate; intent silent | in-process; intent silent |
| Events read service | partly | partly | partly | established (build not assessable) | established as a unit |
| Events write service | not established at head | partly | not assessable | partly | partly |
| Mission state machine | partly | partly | partly | partly | not claimed |
| Work-package state machine | partly | partly | not established | not separate; intent silent | in-process; intent silent |
| Packs | partly | partly | partly | partly | not applicable |
| Glossary | partly | not assessable | not assessable | not separate; intent silent | in-process; intent silent |
| Tracker client | established | partly | partly | established | not applicable |
| doc-kitty | established | partly | established (static only) | partly | not applicable |

Where I depart from the investigators' matrices before reading their reasons:

- Charter activation, logical. D1 has "established" from one literal outside the owner. I read "partly": inside core the file has one owner, but three records name three owners or authorities (F-A1-012, F-A1-013), and the Java service keeps its own activation store (F-D2-004).
- Work-package state machine, logical. D1 has "not established". I read "partly": core's `wp_state.py` is the named origin, and the events mirrors say so and are tested against a core commit (F-D1-024, F-D2-015). The definitions are three, the named owner is one.
- doc-kitty, source. D1 has "not assessable (not measured)". B2 measured it statically: no code of another repository is imported and 15 of 15 cross-package imports use the exports map (F-B2-019, F-B2-021). I read "established, static-derived only".
- Distribution and deployment cells where recorded intent declines the dimension (Python charter as a package, runtime as a package) are "not claimed", not "not established".

Three points that cut across the table:

1. Core's declared ranges admit one published version each, so version tolerance (M04d) was exercised at one point only (F-D1-003, F-D1-013). This bounds every "source" cell for events and tracker.
2. Two seams accept a second implementation with no consumer edit, by execution: the status produce seam (F-D1-016) and the packs root (F-D1-018). No stub was tried behind `charter.offering.api` (F-D1-015).
3. At head no Java service is on any core command path (F-D2-017). The write service is an approved plan with a working rehearsal (F-D2-012), not an observed part of core's behaviour.

## 6. Execution responsibilities

Observed, F. Eleven of fifteen execution responsibilities have their locus in core, two in `spec-kitty-orchestrator` (dispatch, timeout supervision), two nowhere (on-demand cancellation, human attachment) (F-F-001, `m07a-execution-responsibilities.csv`). F counts 12 of 14 verified. All fifteen coordination responsibilities are verified (F-F-002).

My reading of the artefact differs in three ways.

- Denominator. The pre-registration counts responsibilities "that recorded intent places inside the ecosystem". The artefact's own column says a record places 11 inside; for supervision, cancellation and attachment it says no record does. Read strictly, the execution share is 11 of 11. Read as F did, it is 12 of 14. Both must be shown to whoever assigns the verdict.
- What "verified" covers. For several rows the verified part is narrower than the row's name: profile selection is operative, model selection is advisory and the model that ran is recorded nowhere (F-F-014); publication is a local append with no registered transport (F-F-016); permissions are repository authority, while the executor sandbox is self-declared metadata that nothing reads (F-F-010); handover is state-level only (F-F-025); supervision in core is detection only (F-F-011), and the timeout path in the orchestrator was verified by the workstream's own probe, not by a project test (`timeout-probe.txt`).
- Comparator. The coordinator notes that F's comparator list was not committed before classification; the file carries a timestamp before classification. I treat the list as pre-written but uncommitted.

Other observed facts I will carry: `spec-kitty dispatch` starts no executor (F-F-003); the Op record has no process, session, model or attempt field (F-F-004); three unit identifiers exist only as events contracts with no producer (F-F-013, F-F-015); the orchestrator API removed a verb without a version change and two consumers still name it (F-F-007, F-F-008); the API lacks resume, abort and attestation that the host CLI has (F-F-009). A documentation answer says profile and model are recorded on each status event (F-H06a-017, document-claim); the code observation says the model slot holds an absent sentinel (F-F-014). The observed finding stands for the observed view.

A research Mission stalls at its third step because no documented command produces the event its guard waits for (F-E1-028, F-E1-029, executed). This bears on the mission state machine as a capability and on context for the single case.

Single case. The operations log's 14 entries were checked by F: 9 corroborated, 4 partly, 2 not (F-F-022). The investigation used core for governance context and Mission scaffold only (F-F-023).

## 7. Limits of this reading

- Events Java: static only. Charter activation as served: one probe.
- `spec-kitty-go` not attached. The private analysis behind the 2026-09-27 review was not read by anyone (F-A1-035).
- B3 saw 29 edge rows of B1 before fixing its mapping rules (declared breach). The M03b shares depend on that mapping.
- E3 ran 66 of 310 gate files. H06a had agent-guidance files in context.
- I did not open the raw artefacts of C, C2, E, G or H06 beyond what section 1 lists.
