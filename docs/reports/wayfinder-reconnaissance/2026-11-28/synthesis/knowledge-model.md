---
doc_status: draft
updated: '2026-11-28'
---

# Minimum viable architectural knowledge model

Synthesis S-C, profile `architect-alphonso`.

## Standing of this file

- Everything proposed here is a **prospective design recommendation in the proposed view**. Nothing is approved. Nothing here authorises work.
- The design brief's Wayfinder is itself a proposal (ruling R4). Where the repositories differ from it, that is not a deficiency of the repositories.
- Observations are cited by finding id. Evidence kinds: `exec`, `static`, `hist`, `doc`. Revisions are `head` unless stated. "(inference)" marks my own reasoning.
- No part of this was tested. Wayfinder does not exist; all statements about how it would behave are desk assessment.
- The aim is evidence for the design, not a defence of the preliminary design (ruling R12). Section 6 lists where the evidence argues against it.

## 1. The needs the evidence shows

A knowledge model earns an element only where an observed need exists. These are the needs I read from the observations.

| | Need | Observations |
|---|---|---|
| N1 | Know which decision is in force | 521 decision records in six repositories (F-A1-026). Status field unreliable: 26 core records Proposed, 4 in force by merge, one Proposed and executed (F-A1-019). Meaning changed by in-place amendment under an unchanged title on 63% of 4.x core records (F-A1-018). 6 identifiers shared by 13 files (F-A1-028). 6 of 10 supersession chains cross repositories; one core record is superseded by records in another repository (F-A1-027). All `doc` |
| N2 | Know who decides across repositories | No ecosystem-wide precedence; 8 pairwise statements (F-A1-003). Decision authority recorded two ways (F-A1-005). An operator ruling recorded in one repository only (F-A1-012) |
| N3 | Know what the components are, by one name | Three decompositions of core (F-A1-030). 50 of 72 documented relationships name things outside the observed component table (F-B3-007). 9 units with no recorded internal structure (F-A1-031) |
| N4 | Know what a word means and who owns it | 17 of 38 terms unentered; 18 multi-sense terms not disambiguated (F-A2-001, F-A2-005). Core and the charter service model "mission type" differently (F-A2-009). Each glossary's precedence rule points at another repository (F-A2-020, investigator's interpretation, medium) |
| N5 | Know which revision a statement or a check is about | 33 pin and lock surfaces (F-D1-001). Pins lag heads by 53 to 4,369 commits; four consumers pin four open-packs commits (F-D1-002). The pack graph core composes and the one at open-packs `head` differ in shape (F-B2-023, F-D1-023). One pin is not on the pinned repository's main line (F-B2-026) |
| N6 | Know where each exception is, who owns it and when it ends | 75 ledgers, 3,357 file-ledger entries (F-E1-016). Reference on the entry for 12.5% (F-E1-020). Owner on 2 of 30 and 6 of 30 sampled entries (F-E1-025). 13 of 19 ledger files without a baseline leaf (F-E1-023). Rules differ by repository (F-E1-024) |
| N7 | Know which rule is checked by what, and where no check exists | 6 of 12 sampled rules end at a step instruction with no gate (F-E1-014). 0 of 13 acceptance checks look beyond the Mission's repository (F-E1-032). Core against the charter service: no check at all (F-E1-008). Contract compatibility checks pass with no baseline (F-E3-015) |
| N8 | Know which formats cross a boundary and where their definition lives | 10 formats defined on both sides with no shared schema (F-D2-010). 9 project files read by the Java services, described in prose (F-D2-008). Released contract bundles cite 38 core source files as origin (F-D2-009) |
| N9 | Tell intent, plan and fact apart | 4 active core records state a superseded direction with no marker (F-A1-010). The H04 verdict turns on whether an approved plan counts as a present claim (`hypothesis-assessment.md`). 8 of 20 documentation answers were partly correct against code (F-H06b-013) |

Evidence against the size of these needs, which I looked for:

- No documentation answer was incorrect against code; 12 of 20 were fully correct (F-H06b-013).
- 23 of 72 documented relationships already name the test that enforces them (F-A1-031).
- Core already ranks its own sources for module boundaries: the enforced pair prevails (F-A1-001).
- Three records carry a dated supersession note beside the old text (F-A1-010).

So the knowledge exists and is mostly right. What the observations show is that it is spread over many records, not current everywhere, and not ranked across repositories.

## 2. Answers to the brief's synthesis questions

### "Which existing artefacts already represent the required concepts?"

| Concept in the brief | Existing artefact (observed) | State |
|---|---|---|
| Quality attribute | No workstream inventoried quality-attribute records. **Not covered** | Unknown |
| Architectural decision | ADR folders in five repositories and planning; an index in core keyed by file (F-A1-026, F-A1-028) | Present; status and identity unreliable (N1) |
| Invariant | Core: the enforced pair and 310 architectural gate files (F-E1-001). Charter: 92 ArchUnit rules, a module allowlist (F-B2-005). Events: 35 rules (F-B2-011). doc-kitty: three point guards (F-B2-020) | Present per repository, each in its own form |
| Acceptance scenario | Charter contract: 74 scenario entries (F-D2-006). Events: conformance fixtures, a 53-request replay set (F-D2-005). Core: the Mission acceptance matrix with negative invariants (F-E1-032). A Proposed core ADR on shared acceptance scenarios (F-A1-034) | Present per contract; none at ecosystem level |
| Verification binding | Core's gate-selection registry and required checks (F-E1-002, F-E1-004, F-E3-017) | Gate to CI job: present. Rule to gate: not recorded (N7) |
| Revision-bound evidence | Pin files with digests (F-D1-001); release checksum files, which matched 8 of 8 (F-D2-003); an attestation check (F-D2-012) | Present for artefacts. Not found for check results; **not covered** |
| Component and responsibility | Three views in core (F-A1-030); a module registry for CI | Present, three ways |
| Exception | 75 ledgers; `_baselines.yaml`; a suppressions register in charter with 0 entries (F-E1-016, F-E1-017) | Present; fields incomplete (N6) |
| Registry of contracts | Pin files, per consumer. No cross-repository list found | Partial |
| As planned | A roadmap, domain plans, approved plans inside ADRs; "no single approved-plan document" (F-H06a-020; F-A1-033) | Spread |
| Terms | Core `docs/context` with 287 scoped entries (F-A2-018); charter and events glossaries | Present, three owners |

The A1 component catalogue (40 rows), the decision timeline (521 rows), the pin table (33 rows) and the contract-surface table of this synthesis were **built by this investigation**. They did not exist as artefacts before it.

### "Which relationships require stable IDs?"

From what broke or could not be joined (inference over the cited findings):

| Relationship | Why an identifier is needed | Observation |
|---|---|---|
| Decision to decision (supersedes, amends) | References use the id alone, and ids collide | F-A1-028, F-A1-027 |
| Decision to the rule or gate that enforces it | 6 of 12 sampled rules could not be followed to a gate | F-E1-014 |
| Exception entry to rule, owner and retirement | Entries keyed by count cannot be told apart; a cap with headroom admits a new entry | F-E1-018, F-E1-025 |
| Component to its names in each view | 50 of 72 relationship rows did not resolve to an observed component | F-B3-007 |
| Format or contract to each reader and its pin | Readers drift without a visible record; doc-kitty's lock makes its drift visible, core's schema copies have none | F-B2-021, F-B2-031 |
| Evidence to revision | Already done with commit and digest in pins and in this investigation's records | F-D1-001 |
| Unit of execution to status event | A status event stores no Op identifier; the join is one-way | F-F-013 |

The last row belongs to the execution context, not to a knowledge repository. It is listed because the question is general.

Identifiers that already work: `mission_id` (F-H06a-010, no contradicting source), commit and digest pins, and the (file, module) pairs of the activation baseline (F-G2-003).

### "Which invariants are declarative?"

Answered in `quality-attributes-invariants-scenarios.md`, section 2.3. In short:

- Declarative today: no unrecorded cycle, layer direction, exception records, decision identity.
- Declarative only after a public surface, a domain boundary or an owner-and-writers list is published: private access for four of core's six packages, CLI concerns inside `specify_cli`, state ownership (F-G1-007, F-G1-009, F-G2-003).
- Behavioural: independent build, guard producers, projection rebuild.
- Not checkable from records: declared execution policy (F-F-010).

### "Which checks belong locally versus ecosystem-wide?"

What the evidence shows about where checks work (observed):

- Checks inside one repository detect well: reverse dependency 5 of 6, with messages naming the import (F-E3-003). They run in seconds to minutes and are already required (F-E1-004).
- The build-based check took 45 minutes for charter and was lost three times to the environment (F-G2-012, F-G1-012).
- Relations between repositories are checked against pins that lag; one relation has no check (F-E1-008, F-E1-009).
- 0 of 6 incompatible-contract mutations were caught by a compatibility or version check (F-E3-015).

A split that follows from this (proposed, inference):

| Belongs in the owning repository | Belongs across repositories |
|---|---|
| Cycles, layer direction, private access, state ownership, CLI concerns | Who pins what, and how far behind |
| Its own build, install and packaged checks | A format has one definition and each reader pins it |
| Its own exception ledger and ratchet | A consumer's released version reads the producer's released output |
| Compatibility of its contract against its last release | Decision identity, status and supersession across records |
| | That each cross-repository relation has some check |

The evidence does not say that an ecosystem check must run the local ones again. It suggests an ecosystem check reads their declared inputs (model, ledgers, pins) and their results.

### "How is evidence bound to versions?"

Observed today:

- Artefacts: commit plus tree or asset digest in pin files; release checksum files; attestations (F-D1-001, F-D2-003, F-D2-012).
- Three different tree-digest algorithms pin the same pack trees; the same file name has two schemas in two repositories (F-D1-004).
- Released contract bundles carry `SNAPSHOT` as version; the released service and the released contract differ in that one line (F-D2-005, F-D2-019).
- This investigation: finding record with repository, revision, revision kind, command, exit code, environment and SHA-256 of the output (`01-pre-registration.md`, section 11.2). The three kinds `head`, `core-pin` and `released` were needed in practice: validation of packs gives 5 of 5 at the pin and 0 of 19 at `head` with the same tool (F-D1-021).

Options (proposed):

1. Bind evidence to a single commit of the subject. Simple; says nothing about what the subject composes.
2. Bind to the subject's commit plus the pin set it composed. Matches how the ecosystem already integrates; needs the pin table (N5).
3. Bind to released artefacts only. Matches what users run; blind to `head`.

The observations favour 2 for structure and 3 for independence claims, since the two gave different answers (F-D1-021, F-D1-006). That is a reading, not a ruling.

### "How are architectural changes governed?"

Observed and recorded today:

- A decision changes by in-place amendment more often than by a new record, against the recorded rule (F-A1-018).
- Acceptance is by the operator merging; planning's rule says decisions go through a `type:decision` issue and never a named person; core cites only part of that document (F-A1-005).
- Rulesets require a pull request and status checks, 0 approvals, with a bypass actor (F-E1-004). The core charter says nothing on GitHub enforces the workflow (F-E1-006).
- A rule reaches a step as one id in a list of 50 (F-E1-015).
- Exceptions: who approves an entry is recorded nowhere except through review of the pull request (F-E1-024).

The brief proposes: human review protects rules, baselines and exceptions; exceptions carry scope, rationale, owner, approval and retirement. The evidence is consistent with a need (N6) and shows the gap is in owner and approval fields, not in rationale: rationale 30 of 30, owner 2 of 30, approval 1 of 30 (F-E1-025). One ledger's parser refuses an owner key by design (F-E1-025, disconfirmation note). Which process binds is an open decision (`open-human-decisions.md`).

### "What is the smallest useful Wayfinder design?"

Section 3 gives the elements; section 5 gives four shapes with trade-offs. My reading of "smallest" (proposed): four registers of **references**, no copies, no prose architecture description at first.

## 3. The elements

Each element: the need it answers, what would be authoritative, how it is kept true, and what happens without it. "Without it" describes what was observed, not a prediction.

| Element | Answers | Authoritative source | Kept true by | Without it (observed) |
|---|---|---|---|---|
| **K1. Decision index.** One row per decision record in any repository: unique id, repository, in-force status, supersedes and amended-by links, view (intent, plan, proposal) | N1, N2, N9 | The records stay where they are. The index holds references and the status | Generated from record headers; a check fails on a duplicate id, a dangling link, or a status that an amendment contradicts | A reader cannot tell what is in force from status and title (F-A1-037, investigator's interpretation, medium; F-A1-019). 10 of 20 answers had a contradicting source (F-H06b-013) |
| **K2. Component register.** One id per component and capability, with its names in each repository's view and its owner | N3 | Per component, the owning repository's enforced model where one exists; otherwise a declared row | A check that every documented relationship and every ledger names a registered component | Relationship tables do not resolve (F-B3-007); three decompositions (F-A1-030) |
| **K3. Contract and pin register.** One row per surface that crosses a boundary: owner, form, version line, each reader, each reader's pin, reverse pins | N5, N8 | The owning repository's contract and each consumer's pin file | Generated from pin and lock files; reports distance from pin to `head` and to the last release | Four pins of one tree, three digest schemes (F-D1-002, F-D1-004); a relation with no check (F-E1-008); definitions drifting unseen (F-B2-031) |
| **K4. Invariant and exception register.** Per invariant: statement, scope, where the declared model is published, where its exception ledger is, which check runs it and where | N6, N7 | The owning repository's gate and ledger | A check that each invariant names a published model and a ledger, and that each ledger entry has identity, owner and retirement condition | Contract-only and implementation-aware checks disagree in core (F-G1-003, F-G2-003); owner on 2 of 30 (F-E1-025) |
| K5. Term map. One row per shared term: owning repository, senses, the other repositories' names for it | N4 | The owning glossary | A check for terms defined in two glossaries without a cross-reference | One file, three names (F-A2-006); "tier" with two contradictory rules (F-A2-008) |
| K6. Scenario set with bindings. Five to ten scenarios, each bound to an existing check and a revision kind | Brief's traceability chain | The owning repository's scenario or fixture | Each scenario names the check that classifies it | Scenarios exist per contract, not across (section 2) |
| K7. Evidence records. Revision-bound results of the checks | N5, N9 | The CI run or command output, by digest | Written by the check; never hand-edited | Check results are not kept as architecture evidence today (**not covered** by any workstream) |

K1 to K4 are in bold because several independent observations support each. K5 rests on one workstream (A2), whose outside-term mapping is declared low confidence (coordinator's notes). K6 and K7 come from the brief's chain; the evidence does not argue against them and gives little for them.

A property, not an element: every row in every register carries its **view** (intent, plan, observed, proposal) and its **revision kind**. The investigation needed four views, one more than the brief's three, to keep proposals apart from approved plans (ruling R4; F-A1-033, F-A1-034).

## 4. Where the evidence argues against the preliminary design, and where it is silent

### Argues against, or qualifies

| Element of the brief | Evidence | Reading (inference) |
|---|---|---|
| "Never regenerate normative intent from implementation" | Core's recorded rule is the reverse for module boundaries: the enforced pair prevails over every prose map (F-A1-001, F-A1-030, doc). | A conflict between a recorded decision and a proposal. Not a violation (ruling R4). For structure, the enforced model is the intent of record today. A prose "as designed" beside it would be one more map that loses on conflict |
| A separate documentation-first repository describing vision, context, components, interactions and deployment | Copies drift: a "frozen" document differs in 97 of 295 lines from its twin (F-A1-021, F-D2-010); a vendored contract differs in 3 of 7 files (F-B2-029); shared OpenAPI blocks differ in 2 of 7 (F-B2-030); four sites pin four toolkit versions (F-B2-028). The planning repository already holds a 56-record target architecture that binds nothing and names no core revision (F-A1-036, F-A1-004) | The observations argue against any element that **restates** what a repository owns. They do not argue against a register of references |
| "Technology-agnostic invariants" | Statements were technology-neutral for all six. Checks agreed across agents for 4 of 5 assessable in charter and 2 of 6 in core (section 2.1 of the invariants file). H08 is inconclusive | Neutral statements are viable. A neutral **check** needs the model and its exceptions published in a neutral form. In core they are in test files (F-G2-015) |
| "Ratchet existing violations by stable identity, not aggregate counts" | Both forms exist. Identity: 231 pairs matched exactly (F-G2-003). Count: a cap of 231 over 225 entries (F-E1-018) | Supports the proposal. Partly done already |
| Exceptions with "scope, rationale, owner, approval and retirement condition" | Core's recorded rule asks for three fields (issue, owner, drain date); charter's for four; events' for approval and follow-up (F-E1-024). 0 of 60 sampled entries have all four of rationale, retirement, owner, approval (F-E1-025) | Five fields exceed every recorded rule. The gap is owner and approval |
| "Verification adapters" in Wayfinder | Static walks: seconds. Build-based check: 45 minutes, lost to the environment three times (F-G2-012). Existing gates already detect inside a repository (F-E3-003) | Favours adapters that read declared inputs and results over adapters that rebuild |
| "It supplies verification evidence, not ... acceptance authority" | 0 of 13 acceptance checks look beyond the Mission's repository (F-E1-032) | If Wayfinder has no authority and acceptance stays local, the evidence does not show where an ecosystem violation would stop a change. Open decision |
| Three views | Four were needed (section 3) | Add "proposed", or define "as planned" to exclude unapproved proposals |

### Consistent with the brief

- "No persistent service, database or new DSL compiler without demonstrated need." Every check in this investigation was a script over files. No observation shows a need for more.
- "Reuse existing scenario formats and tools." Scenario and fixture formats exist in charter and events (F-D2-005, F-D2-006).
- "Registry of references to authoritative contracts." N5 and N8.
- "Begin with ... a small invariant set." Six were enough to show where checks agree and where they do not.

### Silent

- Benchmarks and performance; fault injection; negative permission tests. No workstream measured them.
- The full chain from quality attribute to evidence. Only the rule-to-gate link was sampled (F-E1-014).
- Whether five to ten scenarios is the right number.
- The runner assignment contract (desk only; F-F-021).
- Whether Wayfinder's own availability matters (AS-10, desk only).
- Events Java (static only).

## 5. Four shapes, with trade-offs

All proposed. The evidence does not choose between them.

| Shape | What it is | For | Against |
|---|---|---|---|
| A. No new repository | K1 to K4 generated into an existing place (doc-kitty already builds every repository's site and reads pinned contracts, F-B2-021, F-B2-028) | No sixth thing to pin. Uses a toolkit four repositories already consume | doc-kitty has no enforced model of its own (F-B2-020). Ties architecture knowledge to a documentation tool. Its consumers are on four versions |
| B. Thin register repository | K1 to K4 as data files holding references, plus the checks that keep them true. No prose architecture, no copies | Smallest thing that answers N1 to N8. Nothing in it can drift from an owner, because it owns no content | Still a new repository with its own pins. Useless unless the owning repositories publish their models and ledgers in a readable form |
| C. The brief's initial scope | B plus vision, principles, context, component, interaction and deployment descriptions, scenarios and adapters | One place to read the intended system. Answers H06 directly | The drift observations of section 4 apply in full. A second normative source beside the enforced pair needs a precedence ruling first |
| D. Publish locally, index nothing | Each repository publishes its model, ledgers and pins in an agreed form; no central register | Fixes what made contract-only checks fail (F-G2-015). No central artefact | Leaves N1, N2 and N5 unanswered: nobody holds the cross-repository view |

B and D are not exclusive: B needs what D provides. A and B differ only in where the registers live.

What each shape waits on is in `open-human-decisions.md`.

## 6. Limits

- The needs are read from one day's `head` revisions and from samples (12 rules, 60 ledger entries, 20 questions).
- K5 rests on one workstream. K6 and K7 rest on the brief more than on evidence.
- I did not test any element. The four generated tables of this investigation show that K1 to K3 can be built once by hand and script; they do not show the cost of keeping them true.
- Quality-attribute records were not inventoried by any workstream.
