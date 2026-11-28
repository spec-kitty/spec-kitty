---
doc_status: draft
updated: '2026-11-28'
---

# Quality attributes, candidate invariants and scenarios

Synthesis S-C, profile `architect-alphonso`. Sources: all workstreams, read evidence-first (`S-C-phase1.md`), then compared (`S-C-differences.md`). Hypothesis verdicts are those of `hypothesis-assessment.md` and are not changed here.

## How to read this file

- Each statement carries a view: **recorded-intent**, **observed**, **approved-plan** or **proposed**. The design brief is **proposed**.
- Evidence kinds: `exec` executed, `static` static-derived, `hist` history-derived, `doc` document-claim. Revisions are `head` unless stated.
- "(inference)" marks a statement of mine that no finding carries.
- Nothing here recommends a change to a repository.

## 1. Quality attributes

The brief ranks five groups, P0 to P2, "for this investigation only" (proposed). The table sets each beside what the records ask for and what was observed.

| Attribute | Source | What the observations show (observed) |
|---|---|---|
| Modularity, orthogonality | Proposed (brief, P0). Recorded-intent: the enforced pair (package set plus layer rules) prevails over prose maps (F-A1-001, doc); 26 must-not-depend relationships recorded (F-A1-031, doc) | Direction between the six packages holds: 0 unrecorded violations of 8,332 module edges (F-B1-010, exec + static). 48 ledger entries stand for 228 upward imports (F-B1-011); B1 reads them as recording that two layers are not below `specify_cli` in the import graph (F-B1-026, interpretation, medium). 92.8% of source lines sit in units with no recorded internal model (F-B1-013, static). 62 of 74 components are in a cycle counting all imports; load-time cycles stay inside one component (F-B1-004, F-B1-007) |
| Independent evolvability, replaceability | Proposed (P0). Recorded-intent: 16 distribution claims and 13 source claims over 40 named components (F-A1-029, doc) | Published artefacts install alone (F-D1-008, exec, released). Named doors exist and most traffic goes round them under recorded baselines: 80 of 101 consumer files import behind `charter.activation.api` (F-D1-015, F-G2-003). Both Python ranges admit one published version (F-D1-003) |
| Interoperability, contract integrity | Proposed (P0). Recorded-intent: consumers adapt to the owning repository's contracts (F-A1-003, doc) | Released services answer their own request sets, 53 of 53 (F-D2-003, F-D2-004, exec, released). Ten formats are defined on both sides of a boundary with no shared schema (F-D2-010). Breaking-change checks pass with no baseline to compare (F-E3-015, exec) |
| Architectural integrity, exception governance | Proposed (P0). Recorded-intent: a baseline entry names an issue, an owner and a drain date (F-E1-022, F-E1-024, doc) | 2 of 24 non-zero ratchet leaves name all three (F-E1-022). 0 of 60 sampled entries carry rationale, retirement, owner and approval together (F-E1-025). Older ledgers are mostly flat or shrinking, 24 of 27 (F-E1-018, hist) |
| Recoverability | Proposed (P1). Recorded-intent: the event log is the sole authority, snapshots are derived (F-H06a-003, doc) | Lane state rebuilt from the log for 12 of 12 sampled Missions, 80 work packages (F-D1-026, exec). Recovery is tested per holder; no holder records what an executor process was doing (F-F-017) |
| Observability, traceability of execution | Proposed (P1) | The model that ran a work package is recorded nowhere in core (F-F-014). A status event stores no Op identifier (F-F-013). Outbound event seams have no production registrant (F-F-016, F-D1-016) |
| Testability, reproducible verification | Proposed (P1) | Core's tests cannot be pointed at an installed wheel (F-D1-014, exec). A source checkout does not import until a pack tree is fetched from another repository: 811 of 1,490 modules fail (F-B1-022, exec). Static invariant walks run in seconds (F-G1-001, F-G2-001) |
| Composability, adoptability | Proposed (P1) | The CLI runs with every service absent (F-D1-020, F-D2-017, exec). A pack at the producer's `head` stops `charter pack list` for the whole consumer project (F-D1-022, exec, released) |
| Deployability, portability | Proposed (P2). Recorded-intent: 8 deployment claims (F-A1-029) | Core starts no service at `head`; the launcher completes a handshake in a rehearsal (F-D2-012, F-D2-017). No consumer needs a Java service in-process (F-D2-018) |
| Authority integrity | Proposed (P2; "security is a fundamental runner constraint") | Execution policy is declared by the caller and not observable by the host; 7 of 11 invokers of the external provider pass a flag the host bans on declaration (F-F-010, static). Every `main` ruleset lists a bypass actor; 0 approving reviews required (F-E1-004, exec) |
| Knowledge integrity (not in the brief) | Observed regularity: investigators attached the tags "consistency" and "discoverability" 42 times to finding records (count over `findings/`, synthesis-run) | 2 of 20 questions answered from one authoritative source, correct, with no contradicting source (F-H06b-013). In-place amendment on 63% of 4.x core decision records (F-A1-018). 26 core records Proposed, some in force (F-A1-019) |
| Conceptual integrity of vocabulary (not in the brief) | Recorded-intent: named multi-sense entries in core's glossary (F-A2-005, F-A2-015) | 17 of 38 inventory terms have no glossary entry; 18 multi-sense terms are not disambiguated (F-A2-001, F-A2-005). One file has three names in three repositories (F-A2-006) |

Reading (inference). The attributes the brief puts first have the most recorded rules and gates. The two rows it does not name have the least: nothing checks that a statement about the architecture is current.

Not covered: performance and benchmarks (no workstream measured them); security beyond the two observations above.

## 2. Candidate invariants

### 2.1 The six from the brief (H08)

G1 wrote each check from public contracts, schemas, metadata and published documents. G2 wrote each with the implementation in view. Both ran on core Python and charter Java at `head`. Events Java was not a subject.

| | Statement, technology-neutral | Core: contract-only (G1) | Core: implementation-aware (G2) | Charter: G1 / G2 | Mutation run (E3) |
|---|---|---|---|---|---|
| I1 | No dependency cycle between components that is not already recorded | Written. 0 new at package level against a substituted baseline, the previous wheel (F-G1-001) | Written. 303 of 304 cycle-closing rows in recorded ledgers; 1 dynamic edge in none (F-G2-001) | 0 new / acyclic main scope (F-G1-002, F-G2-002) | not a mutation class |
| I2 | A component is used only through its declared public surface | Written from published statements. 593 entries break a rule (F-G1-003) | Written from the gates' own surfaces and baselines. 0 new; 231 of 231 pairs match the baseline (F-G2-003) | Same 6 imports (F-G1-004, F-G2-004) | 3 of 6 detected (F-E3-002) |
| I3 | A lower layer, or a library, does not depend on the composing distribution | Written. 312 import names from two layers; cannot tell recorded from unrecorded (F-G1-005) | Written. 229 sites, all in ledgers (F-G2-005) | 0 / 0 (F-G1-006, F-G2-006) | 5 of 6 detected (F-E3-003) |
| I4 | Domain logic holds no command-line concern | Written for five packages: 9 references. Not judged inside `specify_cli` (F-G1-007) | 8 sites in 4 files; needed the location of the CLI package (F-G2-007) | 0 / 0 (F-G1-008, F-G2-008) | not a mutation class |
| I5 | Owned state is written only by its owner | Check runs; gives no pass or fail (F-G1-009) | Needs the allowlists and hand reading; 0 confirmed outside writers for three state kinds, 11 recorded for the status log (F-G2-009) | Partial / 0 after reading 18 sites (F-G1-010, F-G2-010) | 3 of 5 assessable (F-E3-004) |
| I6 | A component builds, installs and passes its own checks without another component's sources | Build fails without the pinned pack tree; install and smoke pass (F-G1-011) | Same (F-G2-011) | Not completed, environment / builds, 16,177 tests pass (F-G1-012, F-G2-012) | not a mutation class |

All `exec`. Verdict for H08 per `hypothesis-assessment.md`: inconclusive.

**Can a contract-only check be written?** For I1 to I4 and I6: yes, in both languages. For I5: not as pass or fail. A static reader can find who names a state file; it cannot bind a write call to its target (F-G1-009).

**Does it give the same answer?** In charter Java, for four of five assessable invariants. In core Python, only for I4 and I6.

**What separates the two (inference, from F-G1-001, F-G1-003, F-G1-005, F-G2-015).** Not the language. In charter the intended model is published as ring rules and a module table, and it has few exceptions. In core the facts that make "new" and "private" decidable are the ledgers and baselines, which sit in test files that the contract-only agent did not read. Two details support this:

- G1 coded the charter-offering door as "`specify_cli` imports `charter.offering.api`". The module's own docstring says the opposite: `specify_cli` must not import it, and the `charter.*` facades are the door (synthesis-run read of `src/charter/offering/api.py`; F-D1-015). Three records state that door three ways (F-B3-011).
- G1 took "public information" to include the agent-guidance file loaded with its session (`workstream-reports/G1.md`). So its checks rest partly on a secondary source.

**What the mutation run adds.** The undetected mutations name what the existing gates cannot see: a dynamic import (F-E3-008); underscore names of a package with no declared surface (F-E3-007); a library with no rule on what it may import (F-E3-010); a contract with no released baseline (F-E3-013); a compile-time constant invisible to bytecode analysis (F-E3-009); a second caller of a single-writer function (F-E3-012). E3 ran 66 of 310 gate files; detection is a lower bound (F-E3-017).

### 2.2 Further candidates the observations suggest

Candidates only (proposed).

| | Statement | Source | Contract-only check possible? | Observed today |
|---|---|---|---|---|
| I7 | Every exception to a rule is a recorded entry with a stable identity, an owner and a retirement condition | Recorded-intent (F-E1-022, F-E1-024); brief | Yes, if the ledger format is published | Identity-keyed: the activation baseline, 231 pairs (F-G2-003). Count-keyed: ratchet caps; one cap is 231 while its file holds 225 (F-E1-018). Owner on 2 of 30 sampled entries (F-E1-025) |
| I8 | Every event or artefact a guard waits for has a producer reachable through a documented command | Observed regularity (PX-01; investigator's candidate in F-E1-029) | Yes: guard inputs against command outputs | A research Mission stalls at step 3 of 6 (F-E1-028, exec) |
| I9 | Removing or renaming part of a published interface changes its version and is entered in its change record | Recorded-intent (version ledger, F-F-007); investigator's candidate | Yes: diff of two published interface descriptions | A verb was removed inside one version; two consumers still name it (F-F-007, F-F-008). 0 of 6 contract mutations caught by a version or compatibility check (F-E3-015) |
| I10 | A format read on both sides of a boundary has one published definition, and each reader pins it | Observed regularity (inference) | Yes: registry of formats against pins | 10 formats without a shared schema (F-D2-010). 8 pack schemas defined twice; 7 differ (F-B2-031). doc-kitty's vendored copy carries a lock (F-B2-021) |
| I11 | Derived state can be rebuilt from the authoritative record | Recorded-intent (F-H06a-003); brief AS-09 | Yes, by execution: delete and rebuild | 12 of 12 for lane state; byte-identical to the committed file in 0 of 12 (F-D1-026) |
| I12 | A decision record has a unique identifier and a status that says whether it is in force | Observed regularity (inference) | Yes: index over record headers | 6 identifiers shared by 13 files (F-A1-028); 26 Proposed, 4 in force by merge (F-A1-019) |
| I13 | A declared execution policy matches what the executor was started with | Investigator's candidate (F-F-010) | No. The host cannot observe the invocation (F-F-010) | Declared and actual differ in the one provider read |

I13 shows the limit: some properties cannot be checked from records.

### 2.3 Declarative or not

A candidate is "declarative" here when it can be stated as data (components, allowed relations, owners, exceptions) and checked by a generic walker.

- Declarative today: I1, I3 (layer chain and ledgers), I2 where a surface is declared, I7, I12.
- Declarative only after something is published that is not published now: I2 for `kernel`, `glossary`, `runtime`, `specify_cli` (no declared surface, F-G2-003); I4 inside `specify_cli` (no record says which parts are domain, F-G1-007); I5 (owner and sanctioned writers per state, F-G1-009); I10 (a format registry).
- Behavioural, checked by running: I6, I8, I11.
- Not checkable from records: I13.

## 3. Scenarios

### 3.1 The twelve from the brief

Classified, not passed or failed. Classifications are those of `hypothesis-assessment.md`; the attribute and evidence columns are added here.

| Scenario | Attribute | Classification | Evidence kind |
|---|---|---|---|
| AS-01 Charter internals change without consumer change | Evolvability | not demonstrated | static; no stub tried (F-D1-015) |
| AS-02 External runner records and retrieves evidence without the CLI | Interoperability | partly: read demonstrated, write not sent | exec, released (F-D2-003, F-D2-012) |
| AS-03 New state-machine configuration needs no unrelated change | Modularity | partly | hist; none under the present layout (F-D1-025) |
| AS-04 New tool adapter preserves mission semantics | Modularity | partly: 35 files in 12 components for the latest | hist (F-D1-025) |
| AS-05 Standalone installation provides declared capabilities | Composability | demonstrated for released artefacts | exec, released (F-D1-008, F-D2-003, F-D2-004) |
| AS-06 Unauthorised dependency is rejected | Integrity | partly: 5 of 6 and 3 of 6 | exec (F-E3-002, F-E3-003) |
| AS-07 Temporary exception stays attributable and bounded | Exception governance | partly: bounded more than attributable | hist + static (F-E1-018, F-E1-025) |
| AS-08 Interrupted assignment stays identifiable and recoverable | Recoverability | partly | exec for core-held parts; otherwise desk (F-F-017) |
| AS-09 Lost projection (derived status snapshot) is reconstructable | Recoverability | demonstrated for lane state | exec (F-D1-026) |
| AS-10 Wayfinder unavailability does not disrupt operations | Composability | not assessable | **desk only** |
| AS-11 Compatible release does not force lockstep upgrades | Evolvability | partly | exec, released (F-D2-011, F-D1-003, F-D1-021) |
| AS-12 Mission acceptance does not conceal ecosystem violations | Integrity | not demonstrated | static + hist (F-E1-032, F-C-019) |

### 3.2 Further scenarios the observations suggest

Proposed, mine. None is a requirement.

| | Stimulus | Response to look for | Observed today |
|---|---|---|---|
| QS-A | A Mission of any shipped mission type is advanced with documented commands only | It reaches its last step | `research` stalls at step 3 of 6 (F-E1-028, exec) |
| QS-B | A verb is removed from the external host interface | A consumer gated on a minimum version learns of it before calling | Not signalled (F-F-007, F-F-008) |
| QS-C | A reader asks which decision is in force on a subject | One record answers, and no active record contradicts it | 2 of 20 (F-H06b-013) |
| QS-D | The producer of packs moves its `head` | The released consumer either reads the new packs or refuses them with a version message | 0 of 19 packs at `head` validate; errors are schema errors (F-D1-021, exec, released) |
| QS-E | A running unit of agent work must be stopped on request | Some holder stops it and records the stop | No holder found; record-only cancellation (F-F-012) |

QS-E touches the prospective execution context. Under ruling R5 the absence is not a deficiency; no record places the responsibility anywhere (F-F-024).

## 4. What is desk assessment

**H08.** The pre-registered measure M08 was executed: twelve checks by each of two agents, on core Python and charter Java at `head`. It tests whether six invariants can be expressed and checked. It does not test Wayfinder. The brief's challenge "Test Wayfinder itself, not just core" could not be met: there is no subject. Everything said about how Wayfinder would hold or run invariants, in this file and in `knowledge-model.md`, is desk assessment in the proposed view.

**AS-10.** Desk only. No measurement was taken and none was possible. What can be said at the desk (inference):

- At `head` no operational path reads a Wayfinder artefact, because none exists. That proves nothing about a future design.
- The nearest observed analogues: the CLI works with every service absent (F-D1-020, F-D2-017, exec), and each repository's gates run in its own CI (F-E1-004).
- If ecosystem checks were made required status checks, an outage would block merges. Whether that counts as "operational disruption" is a definition the architect would have to give.

These three points are reasoning, not verification.

## 5. Limits

- Events Java was not a subject of M08; its build never ran (coverage limit, never a defect).
- G1's charter build was lost to memory; I6 for charter rests on G2 alone.
- The candidates in 2.2 and the scenarios in 3.2 were not tested. Their "observed today" column reuses observations made for other measures.
