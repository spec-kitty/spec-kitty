---
doc_status: draft
updated: '2026-11-28'
---

# Open decisions for the human architect

Synthesis S-C, profile `architect-alphonso`.

## How to read this file

- Each entry is a decision left to the human architect. The synthesis informs it and does not make it.
- "Evidence" cites findings. Views: **recorded-intent**, **observed**, **approved-plan**, **proposed**. Kinds: `exec`, `static`, `hist`, `doc`. Revisions are `head` unless stated.
- Options carry no preference. Where the evidence bears on one, the evidence is named.
- No entry asks for implementation.

## A. Rulings that would settle a verdict

The verdicts in `hypothesis-assessment.md` stand as written. Each of these rulings would move one.

| # | Decision | Options | What the evidence says | Unknown | Blocks |
|---|---|---|---|---|---|
| A1 | The H01 window. It is 2026-07-01 to 2026-09-05, provisional | Confirm; give other dates; give two windows (one per line) | The window is not distinguished from its neighbours: edge density rose 23.6% before, 14% to 15% inside, 21.7% after (F-B1-001). Per-commit spread fell in every period (F-C-008, F-C2-010); C reads that as inseparable from a change in how work is cut into commits (F-C-032, interpretation, medium). The coordinator proposed the same dates before the architect gave them (`04-approval-and-dispatch.md`) | Whether "the reported maintenance period" in the brief is this window | A final H01 verdict |
| A2 | H04: does a cell whose claim is an approved plan, not yet executed, count as "claimed" | Present claims only (verdict inconclusive, partial); plans count (verdict supported) | Under ruling R4 the views are kept apart. One capability has a present claim not established; a second (events write service) has an approved-plan claim whose binding the records call pending (F-A1-033, F-D2-017, F-D2-020). D2 reads logical independence as established in 0 of 5 service rows (F-D2-021, investigator's interpretation, medium) | Nothing measured is missing | The H04 verdict |
| A3 | H03: is the one dynamic import from `charter` to `glossary` a recorded exception | Recorded (a docstring names it); unrecorded (no ledger holds it) | B1 and G2 read it differently (F-B1-012, F-G2-001). The existing gate passes with it present (F-G2-001) | Nothing | Only whether a second support limb is met; the verdict is supported either way |
| A4 | H08: do "the same imports, a different pass or fail" count as a different result (I3) | Same result (inconclusive); different (contradicted) | Both agents found the same imports in the same two packages. The contract-only agent could not see the exception ledgers (F-G1-005, F-G2-005) | Nothing | The H08 verdict |
| A5 | H05: does a reference in a ledger's header count for its entries | Entry only (supported); header counts (not supported on that measure) | 12.5% on the entry; with headers, a retirement condition for 22 and 16 of 30 sampled (F-E1-020, F-E1-025) | The share over all entries with headers counted was not computed | The H05 verdict |
| A6 | H07: are responsibilities that no record places anywhere "inside the ecosystem" | Count them as missing (85.7%, contradicted); exclude them (100%, contradicted); a ruling that they are intended (would need a record) | Supervision, cancellation and attachment have no placing record (F-F-012, F-F-024, `execution-capability-matrix.md` section 3). The comparator list was in effect chosen by the coordinator | Whether "verified" by named passing tests is the intended bar | Not the verdict under any listed reading; the meaning of the result |

## B. Conflicts between recorded decisions and proposals

Under ruling R4 none of these is a violation.

### B1. Charter: source and distribution of the Python implementation

- **Recorded-intent.** Nothing Python moves to `spec-kitty-charter`; the extraction ADR is superseded; offering reads cut over to the charter service behind `charter.offering.api` (F-A1-027, F-A1-033, doc).
- **Proposed.** The brief: "Complete Charter extraction".
- **Options.** (a) The brief's phrase means the recorded direction: a frozen seam with a replacement implementation behind it. (b) It means source and distribution separation of the Python code as well, which reverses the 2026-10-19 supersession. (c) Leave both dimensions "explicitly not pursued" for Python and assess only contract and logical independence.
- **Evidence.** The served offering is established on distribution and deployment (F-D2-004, exec, released). Core answers offering reads in-process; it has no client, no pin and a disabled launch policy (F-D2-017, F-E1-008). 80 of 101 consumer files import behind the activation door under a recorded baseline (F-D1-015). Two validators disagree: 118 divergences recorded, 111 open (F-D2-016).
- **Unknown.** Whether a stub can stand behind `charter.offering.api`: not tried (F-D1-015).
- **Blocks.** AS-01; the meaning of "independent" for charter in any Wayfinder invariant.

### B2. Charter activation: who is authoritative, and who owns the logic

- **Recorded-intent, three ways** (F-A1-011, F-A1-012, F-A1-013; F-A1-038, investigator's interpretation, medium). Core: after cutover the service is authoritative and the local ledger is a mapped copy. Charter ADR-0033: the local file is the source of truth. Open-packs: an operator ruling of 2026-11-16 gives the logic to the charter repository; no core or charter record of it was found.
- **Options.** Confirm one; or state that they describe different stages.
- **Evidence.** At `head` the local ledger is the only authority in use; no consumer calls an activation operation of the service (F-D2-007, F-H06b-005).
- **Blocks.** Any state-ownership invariant (I5) for activation; question 6 of H06.

### B3. Events: ledger, reducer and state machine

- **Recorded-intent.** Contracts and Java services live in `spec-kitty-events`; the reducer and ledger files stay in core (F-A1-027). **Approved-plan.** The Java write service becomes the one event writer; pin pending (F-A1-033).
- **Proposed.** The brief: "Events bus/ledger extraction".
- **Evidence.** Core's Python writes every status event (F-D2-017, exec). The write service starts and completes a handshake in a rehearsal; a release that carries it exists, while core's pin note says it waits for one (F-D2-012, F-D2-020). The work-package state machine is code in core and is mirrored in the events package against a core commit 4,369 commits old (F-D1-012, F-D1-024). The events repository pins core for its test oracles (F-D2-015).
- **Options.** (a) Proceed as planned; decide when to pin. (b) Decide which side owns the transition rules; two code definitions exist. (c) Decide whether the reverse pin of core is permanent or transitional.
- **Unknown.** Every executed Java check in events (build blocked; coverage limit).
- **Blocks.** AS-02 (write side); the H04 rows for the two services.

### B4. Events ordering

- Core: wall-clock order is the rule of record; Lamport-primary needs its own ADR. Events ADR-0001: Lamport is decided and the reducer switch is post-GA (F-A1-014). The events glossary says a timestamp never orders; the reducer on core's path orders by timestamp (F-A2-010, F-H06b-002, static).
- **Options.** Confirm core's record and mark the events documents; or record the Lamport decision in core.
- **Blocks.** Question 2 of H06; any ordering invariant.

### B5. Normative source for structure

- **Recorded-intent.** The enforced pair prevails over every prose module map (F-A1-001).
- **Proposed.** The brief: "Never regenerate normative intent from implementation."
- **Options.** (a) Enforced model stays the intent of record; Wayfinder references it. (b) A prose "as designed" becomes normative and the enforced model must follow it. (c) Split by level: enforced model for package direction, declared intent for what has no model yet.
- **Evidence.** 92.8% of core's lines have no recorded internal model (F-B1-013). Contract-only checks could not decide "new" or "private" in core without the ledgers (F-G2-015).
- **Blocks.** Shape C of `knowledge-model.md`; K2 and K4.

### B6. Execution

- **Recorded-intent.** Running agents is outside core, with an external orchestrator (F-F-005).
- **Proposed.** The brief: runner operations submit, inspect, attach, cancel, collect; an assignment contract; containerised runners.
- **Evidence.** Core holds what records, prepares and gates; acting on a running process is outside core or nowhere (F-F-027, interpretation, medium). Dispatch is delegated by record. On-demand cancellation and human attachment have no holder and no placing record (F-F-012, F-F-024). 13 of 25 prospective operation cells are missing (F-F-021, desk with executed support). The model that ran a work package is not recorded, by design (F-F-014). Declared policy is not observable (F-F-010). fleet-kitty is active by its own README and unnamed in core (F-F-019).
- **Options.** Place supervision, cancellation and attachment: in core, in the external orchestrator, in a new component, or out of scope by record.
- **Unknown.** Containers and remote workers: desk assessment only.
- **Blocks.** AS-08 beyond core-held parts; QS-E; any reading of H07 that depends on placement.

### B7. Exception record

- Core's rule asks for issue, owner, drain date; charter's for rule, file, reason, sunset; the brief for scope, rationale, owner, approval, retirement (F-E1-024).
- **Evidence.** Rationale 30 of 30, owner 2 of 30, approval 1 of 30 (F-E1-025).
- **Options.** One field set for all repositories; or per repository as now.
- **Blocks.** I7; K4.

## C. Contradictions between records

`evidence/A1/recorded-contradictions.csv` has 25 rows. Those that block something:

| # | Subject | The two statements | Evidence | Blocks |
|---|---|---|---|---|
| C1 | Which decision process binds core | Planning: only a `type:decision` issue, never a named person. Core: ADRs name the deciding person; the charter is accepted by the operator merging | F-A1-005 | How any Wayfinder change would be governed |
| C2 | Is the merge path enforced | Core charter: nothing on GitHub enforces. Live rulesets: pull request, three checks, linear history | F-A1-006, F-E1-006 (exec) | Nothing technical; the charter text is the stale side by observation |
| C3 | How events and tracker packages are consumed | Planning and the events charter exception: exact git commit. Core charter: PyPI ranges | F-A1-007; observed: PyPI, lock 11.3.0 (F-D1-003, F-H06b-008) | The events distribution question of the rulings file |
| C4 | Team Kitty as a goal | Planning: part of what is built. Core: unsupported, hosted surfaces removed | F-A1-008 | Scope of any ecosystem model |
| C5 | Packs against the as-is CLI | Open-packs: compatibility ended, a core release never gates pack work. Core: `requires_core >=4.0.0rc7,<5`, built-in byte-identical in every install | F-A1-015; observed: 0 of 19 packs at `head` validate with the released CLI (F-D1-021, exec); core's built-in pin is not on open-packs' main line (F-B2-026) | AS-11; when core's pin can move |
| C6 | ADR practice | Records say immutable, superseded explicitly. Practice: in-place amendment on 77 of 239 core and 61 of 83 charter records | F-A1-018 | K1: what "in force" is read from |
| C7 | Term ownership | Each glossary's precedence points at another repository | F-A2-020 (interpretation, medium), F-A2-009 | K5 |
| C8 | Core charter currency | Four statements contradicted by other core records | F-A1-023 | Nothing technical |

For C2 the observations show which side is current. For the others they do not.

## D. Scope and coverage

| # | Decision | Options | What it would add | Evidence |
|---|---|---|---|---|
| D1 | `spec-kitty-go`, cited by core records, is not attached | Attach and extend; leave as a coverage limit | Unknown. The orchestrator API profile declares `full_go_conformance: false` (F-F-006); that this refers to the repository is my inference | Coordinator's notes; `grounding/intent-landscape.txt` |
| D2 | Events Java: no build ran (HTTP 429) | Re-run where the plugin portal answers; accept static only | The H04 cells marked not assessable; mutation M-OB-5; M-IC-3 on the Gradle side | F-D2-002, F-E3-014 |
| D3 | The stub test behind `charter.offering.api` was not attempted | Commission it; leave | AS-01 | F-D1-015 |
| D4 | E3 ran 66 of 310 gate files | Re-run the undetected mutations against the full battery | Whether 3 core mutations stay undetected; one was caught outside the set (F-E3-011) | F-E3-017 |
| D5 | The research Mission that carries this investigation will not reach `done` (deviation D-1) | Leave it open; close it by hand; wait | Nothing for the findings | PX-01 (F-E1-028) |
| D6 | Whether these reports reach `main` (deviation D-2) | Keep on the research branch; open a pull request | n/a | Rulings file |

## E. Should any finding become a tracker issue

The investigation filed none (deviation D-3). Below are observations that are **executed or statically confirmed, at `head`, with no recorded exception found**. The list serves the decision; it does not recommend filing.

| Observation | Kind | Findings | Note |
|---|---|---|---|
| A `research` Mission cannot pass step 3 of 6 with documented commands; no writer of the awaited event; guard and prompt name different paths | exec | F-E1-028, F-E1-029, F-E1-030 | Not checked: a producer outside core |
| `orchestrator-api`: a verb removed with the contract version unchanged; two consumers and one core document still name it | exec + hist | F-F-007, F-F-008, F-F-020 | Consumers are in other repositories |
| Charter contract: an optional request property made required passes every contract check; no released baseline | exec | F-E3-013, F-E3-015 | In `spec-kitty-charter` |
| Events: a contract example checker that no workflow invokes; the packaged conformance suite not invoked by the command the guide names | exec + static | F-E3-014, F-E1-012 | In `spec-kitty-events` |
| Events: the required cross-repository harness runs against a pin of 2026-05-21 and `spec-kitty-cli==3.2.0rc22`; skipped on fork pull requests, which reads as success | static + hist | F-E1-010 | The events guide records the fork case and a maintainer step for it (secondary source) |
| Core: the built-in pack is not digest-verified at run time; a tampered tree reports healthy | exec | F-D1-019 | Exploratory |
| Core: one Mission reports materialisation drift between `status.json` and the reducer | exec | F-D1-020 | One purposive case |
| Core: `spec-kitty --version` and four other read commands write into the user's home directory | exec | F-B1-025 | Exploratory |
| Core: mypy reports 3 errors in `status/reducer.py`; no workflow runs mypy | exec | F-E3-001, F-E1-013 | |

Options: (a) file none and treat this folder as the record; (b) file those with executed evidence; (c) the architect selects. The charter asks for an issue per pre-existing failure (rulings file, D-3); the mandate here was non-remedial. Whether an item is already known was not checked against the trackers. D2 classifies three further items (a `SNAPSHOT` version string in released contracts, five goldens missing from a fixtures archive, an activation corpus nobody references) as open questions, not defects (F-D2-022, interpretation, medium); they are left out of the table.

## F. The shape of Wayfinder

All proposed. See `knowledge-model.md`, sections 3 to 5.

| # | Decision | Options | What the evidence says | Unknown | Waits on |
|---|---|---|---|---|---|
| F1 | Where the knowledge lives | A: generated into an existing place. B: a thin register repository of references. C: the brief's full scope. D: publish locally, no index | Copies drift in every case observed (F-A1-021, F-B2-029, F-B2-030). A prior target architecture in planning binds nothing and names no core revision (F-A1-036) | Cost of keeping any register true | B5, C1 |
| F2 | Whether core publishes its model and exceptions outside test files | Yes; no | The contract-only checks disagreed with the implementation-aware ones where the ledgers were unreadable (F-G1-003, F-G1-005, F-G2-015) | Whether the ledgers are stable enough to publish | Nothing; it gates B and D |
| F3 | Whether `specify_cli` gets a recorded internal model | State one; record that none is intended | 77.6% of source lines; 400 component edges with no record speaking to them (F-B1-013, F-B3-006). "No intended model" is not a defect (pre-registration, section 3) | What model would fit | I2 and I4 inside `specify_cli` |
| F4 | Who can stop a change that passes Mission acceptance and breaks an ecosystem invariant | Wayfinder evidence feeds each repository's required checks; a separate ecosystem gate; no gate, evidence only | 0 of 13 acceptance checks look beyond the repository (F-E1-032). 15 of 30 sampled cross-component fixes corrected defects already on `main`, found by a person (F-C-019; the detection route is not replicated between C and C2, F-CX-008) | Whether those defects were cross-repository | AS-12; the meaning of "not acceptance authority" |
| F5 | Views | Three, as the brief; four, as this investigation used | Approved plans and proposals had to be kept apart to read H04 (A2 above) | Nothing | K1 |
| F6 | First invariant set | The brief's six; add I7 to I12 of the invariants file; a subset | I5 cannot be judged from records today; I13 cannot be checked at all (F-G1-009, F-F-010) | Whether candidates I7 to I12 hold as invariants: not tested | F2 |
| F7 | Revision binding of evidence | Subject commit; commit plus composed pin set; released artefacts | The same check gives 5 of 5 at the pin and 0 of 19 at `head` (F-D1-021) | Nothing | K3, K7 |

The order inside each group is not a priority.
