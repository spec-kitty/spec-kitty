---
doc_status: draft
updated: '2026-11-28'
---

# Deviation catalogue

Synthesis S-A. Every observed departure of implementation from recorded intent that the workstreams reported, with the record, the observation, and whether a recorded exception covers it.

## Rules of this catalogue

- A **deviation** needs two things: a record that states an intent (view: recorded-intent, evidence: document-claim) and an observation of code, build or history that departs from it (view: observed).
- A recorded exception (ledger, allowlist, baseline, documented carve-out) makes a deviation **covered**. Covered deviations are listed; they are the recorded state, not hidden defects.
- A departure from an **approved plan** that has not been executed yet is not a deviation. It is listed in part C.
- A conflict between a recorded decision and a **proposal** is not a deviation (ruling R4). It is listed in part D.
- Two records that contradict each other are a state of the documents, not of the implementation. They are listed in part B only where code was checked against them.
- The catalogue does not rule which side is right and proposes nothing.
- Where the record is an agent-guidance file, it is tagged "secondary source".
- Coverage: only what the workstreams looked at. The absence of an entry is not evidence of conformance.

## Part A. Implementation departs from a record

### A1. Covered by a recorded exception

| # | Record (recorded-intent) | Observation (observed, head) | Exception | Findings |
|---|---|---|---|---|
| A1.1 | Layer chain: `runtime` and `mission_runtime` must not import `specify_cli` | 228 import statements (98 and 30 module edges) import it | Two shrink-only ledgers, 22 and 10 subpackage entries, flat since 2026-09-07 | F-B1-011, F-B3-004, F-B3-005, F-G2-005, F-E1-018 |
| A1.2 | `charter.activation.api` is the only door from `specify_cli` (core ADR 2026-10-03-1, amendment 2026-10-19) | 80 of 101 consumer files outside `src/charter` import modules behind it | Shrink-only baseline of 231 (file, module) pairs; observed pairs equal it exactly; names an owner and a drain date | F-D1-015, F-G2-003, F-E1-022 |
| A1.3 | `specify_cli` reaches the charter offering through the `charter.*` facades | 11 files (9 `specify_cli`, 2 `runtime`) import `charter.offering.*` directly, all function-level | Ratchet allowlist; the boundary gate passes | F-D1-015, F-H06b-001, F-H06b-006 |
| A1.4 | One status read door (core ADR 2026-11-06-2) | 33 legacy read sites bypass the door | Shrink-only allowlist with drain date 2026-12-31 | F-H06b-003, F-E1-019 |
| A1.5 | The status event log is written through its owner | 11 modules outside `specify_cli.status` are recorded writers | Two shrink-only allowlists; they share no module | F-G2-009, F-G2-014 |
| A1.6 | `consolidation` does not import the CLI layer | 16 files import `specify_cli.cli.console` | Console-importer ledger, 16 entries | F-B1-011 |
| A1.7 | Events services "never need core to build or run" (events charter) | Events pins core commit 512567ee for CI oracles and three generator scripts; that commit is 4,369 commits behind core `head` | The events charter records the pin as test-only | F-D1-012, F-D2-010, F-A1-032 |
| A1.8 | Charter Java: only the adapter ring of a slice names another slice | 9 named-class exemption lines for 6 classes; 136 executed tests, 0 failures | Exemptions are written in the rules | F-B2-005 |

### A2. Covered only by a note, or disputed between workstreams

| # | Record | Observation | Status | Findings |
|---|---|---|---|---|
| A2.1 | Layer rule forbids `charter` to import `glossary` | `charter.offering.missions.glossary_hook` line 115 loads `glossary.attachment` through `import_module` (confirmed by grep at synthesis) | The rule's docstring says this import is outside the assertion. B1 treats that as recorded. G2 counts the edge as in no recorded ledger. **Both kept.** | F-B1-012, F-G2-001 |
| A2.2 | Charter Java ring rule as published | 6 imports in one file pair: `artifacts.infra.packs` names `routing.domain` types | The published module table allows the module dependency; the two published statements differ. Admissibility is undecided without type-flow analysis. Both G agents found the same 6 | F-G1-004, F-G2-004 |
| A2.3 | Charter Java documented module table | 5 main-scope module edges are absent from the table; 3 are recorded elsewhere in the same document | Partly recorded | F-G2-002 |
| A2.4 | Charter Java: "kernel depends on nothing outside the JDK" | 59 of 382 kernel and domain files import `org.jspecify.annotations` | No exception found; annotations only | F-G1-006 |

### A3. No recorded exception found

| # | Record | Observation | Findings |
|---|---|---|---|
| A3.1 | Research mission: the gathering prompt, the spec and plan templates and the mission-types glossary page name `research/source-register.csv` | The guard looks for `source-register.csv` in the Mission directory; a register written where the prompt says does not satisfy it (executed) | F-E1-030 |
| A3.2 | Research mission: the step prompt tells the agent to follow the harness's event-emission mechanism; prompts and README cite guard expressions as being in `mission.yaml` | No writer of `source_documented` exists in `src/`; tests write the rows by hand; `mission.yaml` holds no such expression. A research Mission stalls at step 3 of 6 (PX-01, executed) | F-E1-028, F-E1-029, F-E1-031 |
| A3.3 | Charter burn-down policy: a baseline entry names a tracker issue, an owner and a drain date | Of 24 non-zero leaves: 16 name an issue, 5 an owner, 3 a date, 2 all three | F-E1-022, F-H06b-011 |
| A3.4 | Same policy: every mutable architectural allowlist is governed by a baseline leaf | 6 of 19 non-empty ledger files have a leaf; 13 do not (each states shrink-only or generated semantics in its own header) | F-E1-023 |
| A3.5 | Orchestrator API: a version ledger with 31 minor entries; boilerplate says no field is removed or renamed | Verb `merge-mission` was removed and `consolidate-mission` added with the contract version unchanged at 1.6.0; the ledger has no entry for the removal. Two consumers still name the removed verb | F-F-007, F-F-008 |
| A3.6 | `host-boundary-rules.md`: external systems do not call host CLI commands (anti-pattern 2) | The API's stale-lane failure text prints a route made of host CLI commands; the API has no attestation, resume, abort or dry-run | F-F-009 |
| A3.7 | Orchestrator API policy: four flags are banned when declared | `spec-kitty-orchestrator` declares no dangerous flags while 7 of its 11 invokers pass a banned or equivalent flag to the agent tool. The host cannot observe the invocation | F-F-010 |
| A3.8 | `multi-agent-orchestration.md` and `host-boundary-rules.md` (core, head) | Four statements disagree with code: one worktree per work package (code: per lane); `merge-mission` listed; `in_progress` maps to internal `doing`; the orchestrator creates the worktree | F-F-020 |
| A3.9 | Events `ordering-and-reduction.md` (active) and the envelope README: a timestamp is never used to order a stream | The reducer on core's status path orders by the writer's timestamp, then event id, and reads no Lamport clock. Core's ADR amendment of 2026-10-22 records the wall-clock order; the events documents and the unamended ADR body do not | F-H06b-002, F-A1-014 |
| A3.10 | Core charter: `event-ledger-writers-and-readers.md` stays frozen in core | The core copy is marked active with no frozen banner and differs from the events copy in 97 of 295 lines | F-A1-021, F-D2-010 |
| A3.11 | Core ADRs are immutable and superseded explicitly; charter ADR-0010 says the same | In-place amendment markers on 77 of 239 core records (63% of the 4.x era) and 61 of 83 charter records | F-A1-018 |
| A3.12 | Event log is the sole authority; `status.json` is derived | One Mission (purposive, outside the seeded sample) reports "Materialization drift" between `status.json` and the reducer output. In the seeded sample lanes were equal for 12 of 12 | F-D1-020, F-D1-026 |
| A3.13 | Charter repository: exceptions to hand-written gates live in one register and "those gates are never relaxed in source" | The register has 0 entries; 59 `@SuppressWarnings` annotations exist. Which of them relax a covered gate was not determined | F-E1-017 |
| A3.14 | Events agent guide (secondary source): the packaged conformance suite is a gate on every pull request | No workflow, Makefile target or pytest setting invokes it | F-E1-012 |

### A4. The record lags the implementation

Here the implementation is ahead of, or stricter than, the record.

| # | Record | Observation | Findings |
|---|---|---|---|
| A4.1 | Core charter: nothing on GitHub enforces the pull-request workflow | Three active rulesets since 2026-11-01 require a pull request, linear history and three status checks | F-E1-006, F-A1-006 |
| A4.2 | Core `pins/README.md`: the write service waits for a release that carries it | Such a release exists (`service-v0.1.0-rc.2`) and core's own tool can pin it in a rehearsal | F-D2-020, F-D2-012 |
| A4.3 | Core charter: "rc5 was published, rc6 is open"; ADRs live in `architecture/decisions/` | Eight release candidates shipped, rc9 open; ADRs are under `docs/adr/<era>/` (record against record, cited by A1) | F-A1-023 |
| A4.4 | Core architecture views: the read service lives in core; the charter is "extracting" | The service lives in `spec-kitty-events`; core's copies were removed; the extraction decision is superseded (record against record) | F-A1-009, F-A1-010 |

## Part B. Records that contradict each other, where code was checked

| Subject | Records | Code at head | Findings |
|---|---|---|---|
| Who may import `charter.offering.api` | Frozen relationship row: `specify_cli` consumes it. The module's docstring: `specify_cli` must not import it. Superseded ADR 2026-10-12-2: same | 0 files outside `charter` import it | F-B3-011, F-D1-015 |
| Events package pinning | ADR 2026-02-11-6 (Accepted, no supersession marker): exact pins. Charter: SemVer range plus lockfile | The wheel declares the range; the lock holds 11.3.0; the range admits one published version | F-H06b-008, F-D1-003 |
| Where a mission type is defined | `docs/context/mission-types.md`: under `src/specify_cli/missions/`. `mission-system.md`: the pack is canonical | Four `mission.yaml` files exist in both places, byte-identical | F-H06b-009 |
| Built-in pack in core | Charter ADR-0005: core carries a committed tree. Core ADR 2026-08-16-2: fetched from a pin | Fetched; only pin files are tracked | F-H06b-004 |
| Status fan-out | ADR 2026-06-26-2 line 128: core registers an observer. Same ADR lines 104 to 112: none registered | 0 registrations in `src/` | F-H06b-010, F-D1-016 |
| Authority for charter activation | Core charter: service authoritative after cut-over. Charter ADR-0033: local file is the source of truth. open-packs charter: the charter repository owns activation logic | Core holds the file and the engine; the service stores its own; no shared store | F-A1-012, F-A1-013, F-D2-016, F-A1-038 |
| Pack compatibility with the CLI | open-packs ADR 2026-11-04-1 ends it. Core charter: built-in stays byte-identical in every install; pin says `requires_core >=4.0.0rc7,<5` | Core's validator accepts 5 of 5 packs at core's pin and 0 of 19 at open-packs head | F-A1-015, F-D1-021 |
| Owner of the mission-status contract | doc-kitty ADR-0082: "core's public contract". Events ADR-0002: events | Contract and service are in `spec-kitty-events` | F-A1-025, F-D2-005 |

A1 reports 18 recorded contradictions under its measure M6 (among F-A1-005 to F-A1-025). Those with no code check are not repeated here.

## Part C. Approved plans not yet executed (not deviations)

View: approved-plan. The records themselves call these pending.

| Plan | State observed at head | Findings |
|---|---|---|
| Offering reads cut over to the charter service through `charter.offering.api` | Core answers offering reads in-process; no HTTP client; charter-service launch policy disabled; no charter pin | F-A1-033, F-D2-017, F-E1-008 |
| The Java write service as sole event writer | Core's Python writer performs every write; the launcher completes a handshake in a rehearsal; no transport | F-A1-033, F-D2-012, F-D2-017 |
| Activation switch to the charter surface as a 4.0 deliverable | No consumer calls the activation operations | F-A1-033, F-D2-007 |
| Lamport-primary ordering | Not on the status path; recorded differently in core and events | F-A1-014 |

## Part D. Recorded decisions against proposals (not deviations)

| Recorded decision | Proposal | Note | Findings |
|---|---|---|---|
| Nothing Python moves to `spec-kitty-charter`; the extraction ADR is superseded | The design brief's "complete Charter extraction" | A decision on the source and distribution dimensions. Open for the architect (rulings, section 3) | F-A1-010, F-A1-027 |
| The status reducer and the ledger files stay in core; contracts and Java services are in `spec-kitty-events` | An "Events and API" capability as one unit | Each dimension measured as found (H04) | F-A1-027, F-D2-021 |
| Running agents is placed outside core, with an external orchestrator | Execution infrastructure inside the ecosystem (containerised runner, attach, cancel) | Dispatch is delegated by recorded intent; cancellation and attachment are placed nowhere | F-F-005, F-F-012, F-F-024 |
| Events ADR-0007 and ADR-0008 (Accepted): coordination status committed by ref compare-and-swap | Core ADRs 2026-11-06-4 and 2026-11-06-6 (Proposed) on the same design | Same design, different status in two repositories | F-A1-020 |
| No record forbids command-line libraries below the CLI layer | Candidate invariant I4 | 4 modules in `charter`, `glossary`, `runtime` import one; no gate | F-B1-020, F-G2-007 |
| No record declares a public surface for `kernel`, `glossary`, `runtime`, `specify_cli` | Candidate invariant I2 | 131 underscore imports across top-level packages; convention only | F-G2-003, F-E2-002 |
| The Kitty Shared Architecture v0.11 binds nothing until ratified | Its 56 records | No ratification found | F-A1-036, F-A1-004 |

Prospective terms (Kira, HUD, Operations Deck, Wayfinder) have no counterpart in the repositories. That is not a deviation and not a deficiency (ruling R5; F-A2-019).

## Counts

| Part | Entries |
|---|---|
| A1 covered by a recorded exception | 8 |
| A2 covered by a note or disputed | 4 |
| A3 no recorded exception found | 14 |
| A4 record lags implementation | 4 |
| B record against record, code checked | 8 |
| C approved plans pending | 4 |
| D decision against proposal | 7 |

These are counts of catalogue entries, not a measure. Entries differ greatly in size: A1.2 stands for 231 import pairs, A2.1 for one line.

## Not covered

- Rules of the charters and directives that no workstream traced (77 of the 89 in E1's two frames).
- The supplementary repositories, except where F read them.
- Whether each covered exception is still needed.
