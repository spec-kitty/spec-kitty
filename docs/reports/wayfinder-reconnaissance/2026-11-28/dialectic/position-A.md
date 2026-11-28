---
doc_status: draft
updated: '2026-11-28'
---

# Position A

Role A, profile `architect-alphonso`, charter context for the action `review` loaded. I authored no finding, synthesis, review or evaluation file. Another agent under the same profile wrote `synthesis/knowledge-model.md`. The profile's verbs are "design" and "decide"; the envelope allows neither, and the envelope wins. I did not read `position-B.md`. Nothing was re-run; I read 19 finding records directly and otherwise rely on the synthesis as traced by the review.

Statements are in the **observed** view at `head` unless marked. Kinds: `exec`, `static`, `hist`, `doc`. "(conjecture)" marks an argument with no evidence behind it. The human architect decides.

## 1. The claim, stated narrowly

I do not argue that the layering of core has decayed. I argue:

1. The ecosystem departs from its own records in places that no existing gate looks at. Those places are: between repositories, between a record and the behaviour it describes, between records, and inside `specify_cli`.
2. The two hypotheses that survive review (H03 qualified, H06) and the experiment PX-01 describe conditions that cost something in practice.
3. A register of architectural knowledge with verification bindings, which is the core of the design brief, is warranted. The brief's full initial scope is not.

## 2. What I concede

| Point | Why |
|---|---|
| H01, the brief's founding story | Inconclusive, and near contradicted. In the window M01a rose 14.2% and 15.1%, M01b (load time) and M01d fell (F-B1-001, F-B1-004, F-C-008). Corrective commits touch fewer components than capability-growth commits in every period, in both runs (F-C-006, F-C2-008). The evidence does not show that point fixes in the window eroded orthogonality |
| H02 as registered | Inconclusive: 4 of 30 against 5 of 30 on the acceptance clause (F-C-021). Acceptance was read from a field present on 430 of 858 Missions |
| H07 | Contradicted by the letter: 12 of 14 against 15 of 15 (F-F-001, F-F-002). I use only its excluded rows, in section 4 |
| H05 as "sediment accumulated" | 24 of 27 ledgers that existed on 2026-09-07 are flat or shrinking (F-E1-018). The verdict turns on one ruling about ledger headers |
| H04 | Undetermined. The count of capabilities is 0, 1 or 2 by mapping choices made after the data (review item H-07) |
| The enforced tier | It works. 0 unrecorded violations in 8,332 module edges (F-B1-010). Reverse-dependency mutations detected 5 of 6; ownership bypass of the status log and migration ledger 3 of 3 (F-E3-003, F-E3-004) |
| Covered deviations | The 8 entries of part A1 of `deviation-catalogue.md` are recorded exceptions, not drift |
| The documentation is mostly right | 0 of 20 documentation answers were incorrect against code; 12 were fully correct (F-H06b-013) |
| H08, a premise of the brief | Contradicted on the review's reading: contract-only checks fail in core today. I use only the cause (section 5) |
| The brief's full scope | Section 6 |

## 3. Departures that no gate caught

"Drift" here means: a record states an intent, the implementation or another record departs from it, and no recorded exception covers it. Part A3 of `deviation-catalogue.md` lists 14 such entries; part B lists 8 contradictions between records where code was checked. The catalogue covers only what the workstreams looked at: 77 of the 89 rules in E1's two frames were not traced.

### 3.1 A mission type that cannot finish, with green tests

PX-01, pre-registered, executed, replayed by reviewer R3. A `research` Mission advanced with documented commands stalls at the third of six steps (F-E1-028). The guard counts `source_documented` rows; in `src/` the string occurs only in the reader and the guard; the tests that pass the guard write the rows by hand (F-E1-029). The prompt, both templates and the glossary page name a file path the guard does not read (F-E1-030). No producer was found in core or in seven other repositories (`validity-evaluation.md`, section 3).

The recorded intent is a six-step mission type. The implementation has no way through step three. The tests are green because they supply by hand what the product never writes. No gate reported it.

### 3.2 Contract checks that pass without comparing

- In both repositories that hold an OpenAPI contract the breaking-change check passed with no baseline: "No released baseline" in charter, `NO_BASELINE_INITIAL_VERSION` in events (F-E3-013, exec, reproduced; F-E3-015, exec, exploratory).
- 0 of 6 incompatible-contract mutations were caught by a compatibility or version check. 5 were caught by other means (F-E3-015).
- The orchestrator API removed the verb `merge-mission` with the contract version unchanged at 1.6.0; the version ledger has no entry for it (F-F-007, hist). 2 of 3 consumers read still name the removed verb, and both gate on a minimum version, which a removal without a version change does not trip (F-F-008, reproduced).

A check named for compatibility that compares nothing gives a green result a reader takes for assurance. The orchestrator case shows the same in history: a breaking change passed through a versioned contract unseen.

### 3.3 Between repositories

- 15 cross-repository check relations exist; 2 are required on every pull request. For core against the charter service there is none (F-E1-008, static). Counterevidence in that finding: the charter-service pin is pending by recorded intent.
- The checks validate against pins, 53 to 4,369 commits behind head (F-E1-009, hist, exploratory). Whether those commits matter was not tested, except once: core's validator accepts 5 of 5 packs at core's pin and 0 of 19 at open-packs head, with the released 4.0.0rc8 wheel and with head (F-D1-021, exec, decisive, reproduced). The records disagree too: an open-packs ADR ends compatibility with the CLI; the core charter keeps the built-in pack byte-identical in every install (F-A1-015, doc).
- The events required check `cross-repo-harness-tests` installs `spec-kitty-cli==3.2.0rc22` and a harness commit of 2026-05-21; on a fork pull request it is skipped, which reports as success (F-E1-010, static).
- The events packaged conformance suite, which the events agent guide calls a gate on every pull request, is invoked by no workflow, Makefile target or pytest setting (F-E1-012, reproduced). (The guide is secondary.)
- 10 formats have a definition on each side of a service boundary and no single generated source (F-D2-010). 7 of 8 pack-artifact schema pairs differ in top-level property names between core and the charter repository (F-B2-031, medium confidence).

### 3.4 Between a rule and a gate

Of 12 rules sampled by seed, 6 end at a step instruction with no gate (F-E1-014). The charter context for an action lists 50 directives by id; none of the 6 sampled architecture rule texts occurs in it (F-E1-015). Small sample.

### 3.5 Between records

- Core and charter records say an ADR is immutable and superseded explicitly. Amendment markers sit on 77 of 239 core records, 33 of 52 in the 4.x era, and on 61 of 83 charter records (F-A1-018, doc; a lower bound by the finding's own check).
- The core charter says nothing on GitHub enforces the pull-request workflow; three rulesets do (F-E1-006, F-A1-006).

These are departures of records from records. A reader who follows the record is misled about what is in force.

Each item is bounded, and several are known to the project in its own words. I claim only that the existing gates did not report them and that nothing in the gate inventory is built to.

## 4. Why the supported hypotheses matter in practice

### H06, supported, robust

2 of 20 questions were answered from one authoritative source, correct, with no contradicting source; a contradicting source was found for 10 of 20, so at most 10 can pass whatever the judgement on authority (F-H06b-013; `verdict-challenge.md`, section 6). Both declared instrumentation gaps push the count up.

The practical weight comes from who reads these documents: agents carry out Missions here, and their context is built from documentation, charters and guidance files. With guidance files added, 12 answers changed and the count meeting all three conditions stayed at 2 (F-H06b-013). 8 of 20 answers were partly correct. An agent that acts on a partly correct answer about who may import what, or which component is authoritative for activation, produces a change that is locally reasonable and architecturally off. That this has happened at any rate is conjecture.

I accept the review's points that the questions were written after reading core's guidance file and that the third condition fails on any stale page. The second is the hypothesis itself: a corpus of 2,051 files in which a stale page is always findable is fragmented.

### H03, supported, qualified

M03b is 24.7% at the registered unit (F-B3-002). Synthesis, review and evaluation agree that this shows silence, not breach: 464 of 656 edges lie inside one top-level package where no record speaks. I accept that.

The silence matters because of where it sits. `specify_cli` holds 77.6% of source lines, and 90.7% of those have no stated internal model (F-B1-013, reproduced). The gates that work check the six-package layer rule. In the period from the convergence merge result to head, M01a rose 21.7% (F-B1-001); the granularity-free density rose 14.2% (reviewer-computed, exploratory, review item C-01). The enforced tier showed 0 violations throughout. So the one structural measure that moved after the convergence moved where the assurance has no model to compare against. I draw no trend across the merge and no cause: M01f cannot rank classes.

Whether the inside of `specify_cli` is meant to have a model is the architect's ruling (decision F3). If the answer is no, H03 says nothing. If the answer is yes, 407,154 lines have been growing denser without an intent to check them against.

### The rows H07's measure could not see

H07 is contradicted on its registered denominator. That denominator leaves out the three responsibilities no record places anywhere: supervision, cancellation on request, human attachment (F-F-012, F-F-024; `validity-evaluation.md`, section 3). I do not claim H07 is supported. I claim that an unowned responsibility is a gap in recorded intent, a matter for a knowledge repository before it is one for a runner.

### M02, beside the verdict

15 of 30 sampled cross-component fixes corrected a defect that had reached `main`; all 15 were found by a person or a review squad (F-C-019, medium confidence). An automated check before `main` is the named detector for 1 of 30 (C) and 2 of 30 (C2). 0 of 13 acceptance checks read another repository, a pin, a lockfile, a contract or a gate result (F-E1-032, reproduced).

Limits I accept: the detection route did not replicate (22 against 16); a gate that blocks a change before any commit leaves no trace in this frame; "a person" includes agent review squads. What stands is a direction both runs share and a statement of scope: Mission acceptance is not built to see the ecosystem.

## 5. Why a knowledge and assurance repository is warranted

| Observed | Element of the brief it answers |
|---|---|
| H08, overturned to contradicted by the review: in core Python the contract-only check and the implementation-aware check agree for 2 of 6 invariants. The cause both the review and the evaluation name is that core's exception ledgers and baselines sit in test files (F-G2-015, F-G1-003, F-G1-005). In charter Java, where the model is published, 4 of 5 assessable agree | "Registry of references", invariants with declared exceptions. An ecosystem check cannot exist until models and ledgers are readable outside the repository that owns them |
| Owner on 2 of 30 and 6 of 30 sampled ledger entries; approval record on 1 and 7; all four fields on 0 of 60 (F-E1-025). 0 required approvals and an always-bypass actor in all five repositories (F-E1-004, reproduced) | "Exceptions require scope, rationale, owner, approval and retirement condition"; "protect rules, baselines and exceptions with human review" |
| 6 of 12 sampled rules with no gate (F-E1-014); compatibility checks with no baseline (F-E3-015); a gate named in a guide and run nowhere (F-E1-012) | "Verification binding": a record of which rule is checked by what, and where nothing checks it |
| 33 pin and lock surfaces; four consumers pin four open-packs commits (F-D1-001, F-D1-002); 5 of 5 against 0 of 19 by revision kind (F-D1-021) | "Revision-bound evidence" |
| 521 decision records in six repositories; 6 of 10 supersession chains cross repositories (F-A1-026, F-A1-027); status unreliable (F-A1-019) | A decision index with identity and in-force status |
| H04 undetermined because an approved plan and a present claim could not be told apart; two synthesisers mapped 34 and 43 claimed cells from the same catalogue | The views: as designed, as built, as planned |

The gaps are between repositories. No single repository's gate can hold a cross-repository view, and the records give no ecosystem-wide precedence, only 8 pairwise statements (F-A1-003, doc). Shape D of the knowledge model, publish locally and index nothing, leaves the decision index and the pin view unanswered by its own account.

## 6. Where the brief goes further than the evidence

Conceded against my own role.

- **A prose architecture description in a separate repository** (vision, context, components, interactions, deployment). The evidence argues against restating what a repository owns. A "frozen" document differs from its twin in 97 of 295 lines (F-A1-021); the planning repository already holds a 56-record target architecture that binds nothing and names no core revision (F-A1-036). The review narrows the drift claim correctly (item W-01): copies with a pin or lock lag, copies without one drift. That still leaves a prose "as designed" needing a pin and a precedence ruling it does not have.
- **"Never regenerate normative intent from implementation."** For module boundaries core's recorded rule is that the enforced pair prevails over every prose map (F-A1-001). The recorded decision is working (ruling R4: a conflict with a proposal, not a violation).
- **Nothing about Wayfinder was tested.** AS-10 is desk only. The cost of keeping registers true is unknown. That a register would have caught PX-01 or the verb removal is conjecture: a register records that a guard has no producer only if someone asks it to.
- **A register can become the next stale document.** I have no evidence that it would be kept true.
- **Smaller responses exist** for several single items, and none needs a repository. My claim is about the class, shown by 14 uncovered entries from a partial trace, not by a rate.

So the position is: shape B of the knowledge model (a thin register of references with checks, no copies), resting on shape D (each repository publishes its model, ledgers and pins). This keeps the brief's traceability chain, exception fields, registry and "no persistent service" constraint, and drops the prose views until a precedence ruling exists.

## 7. What would change my position

| If this were shown | I would withdraw |
|---|---|
| The full battery of 310 gate files, or per-change CI, detects PX-01's missing producer or a contract removal without a version change | Section 3.1 or 3.2 as "not caught" |
| A second question set, written by someone who has not read core's guidance file, scores 11 or more | H06 as a basis |
| The architect rules that `specify_cli` is intended to have no internal model | The H03 argument in section 4 |
| G1 re-run with the ledgers supplied as data still disagrees with G2 | The link from H08 to "publish the models", and with it shape B |

## 8. Limits

One author, one pass, nothing re-run. Events Java is static only, a coverage limit. The outside observer's predictions have not been returned.
