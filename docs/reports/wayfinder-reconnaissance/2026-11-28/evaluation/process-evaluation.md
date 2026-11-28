---
doc_status: draft
updated: '2026-11-28'
---

# Process evaluation (part P)

Evaluator P, profile `retrospective-facilitator`, charter context for the `review` action loaded. Its `retrospective.yaml` output conflicts with the envelope; the envelope wins. I authored none of the work. I did not read the other evaluator's files.

Read: files 00 to 05, the operations log, every brief in `dispatch/`, the deviation sections of all 18 workstream reports, the phase-1 and differences files, the review outputs. Run: read-only git, `grep`, a YAML field scan. Supporting files: `process-deviations.csv` (PD-01 to PD-20) and `envelope-check.txt`.

## 1. Controls of section 11

| Control | Grade | Evidence |
|---|---|---|
| 11.1 Briefs carry measures, scope, revisions and sections 1 to 4, not the hypotheses or the failure-mode list | held in part | No brief names H01 to H08. Three briefs steer (section 3 below): PX-01, H06a, F. `COMMON.txt` carries the periods T1 to T3, whose T2 equals the H01 window (PD-08) |
| 11.1 No workstream receives another's output | held in part | Permitted inputs are named (B3, CX, E3, H06b). B3 saw B1's 14-row aggregate and 29 edge rows before its rules (declared). Scratch folders are shared and readable; isolation is by instruction only (operations log, line 7) |
| 11.1 Each agent loads its profile and states what it applied | held | All 18 reports name the profile and applied directives; analyst fields in 414 of 414 records |
| 11.2 One YAML record per finding, in the schema | held | 414 records; 393 observations, 21 interpretations |
| 11.2 Disconfirmation search on every record | held | 0 of 414 empty; R1 judges 9 of 55 sampled searches not a search for the opposite |
| 11.2 Hash mismatch voids a finding | held | 391 hashes checked by R1 to R3; all match |
| 11.2 No code files under `docs/` | held | Extensions in the report folder: csv, json, md, txt, yaml only |
| 11.2 Interpretations cite finding ids, never repository text | not checked | Outside what I could verify in this pass |
| 11.3 C′ on a different model and profile, sealed until C finished | held in part | C on `fable` / `researcher-robbie`, C2 on `opus` / `analyst-annie` (analyst fields). No record shows the sealing; both ran in a shared scratch tree |
| 11.3 10% replication rule applied | held | CX applies it measure by measure; CX's own definition of relative difference is declared |
| 11.3 Review reproduces every decisive finding plus a seeded 20% (at least five per workstream) | held in part | 162 sampled (`sample-method.txt`, seed 20261128); R1 55, R2 48, R3 59 = 162. The decisive set (67) was fixed by the synthesiser S-A and omits F-B1-006 and F-A1-031, from which M03b is computed (V, section 3) |
| 11.4 Interpretation and confidence removed mechanically before synthesis | held | `synthesis/input/` holds 393 observation records with neither field; 21 interpretations in `sealed/held-back-records.csv`; `unparseable-records.csv` empty |
| 11.4 Released only after the synthesis drafted its own reading | held in part | Phase-1 files exist for S-A, S-B and S-C. Each was committed together with its final documents (commits `ce92f19631`, `23ea4709af`, `5cd95bc354`), so the order rests on the synthesisers' statements (PD-14). S-C's phase 1 read S-A and S-B outputs that already carried investigator readings (declared, PD-13) |
| 11.4 Reviewer derives its own claim first | held | Cards omit the claim; own-claim logs in `logs-R2/`, `logs-R3/`; R1 declares two early glimpses |
| 11.4 Coordinator does not paraphrase findings into prompts | held | No brief in `dispatch/` quotes or summarises a finding. Environment facts about other agents' builds appear (E3, D2); they are not findings |
| 11.4 Coordinator does not filter duplicates or inconclusive results | held | All 393 observations reached the packet; the review sample is drawn from all 414 records |
| 11.4 Coordinator does not repair a command while keeping its result | held | No case found. Two mid-run instructions changed procedure only (E3 layer rules alone; B2 second retry); neither is in `dispatch/` (PD-09) |
| 11.4 Coordinator does not tell the reviewer which findings matter | held in part | `RV-REPRO.txt`: "Do all decisive ones first"; `sample.csv` carries `selected_as = decisive`. Required by 11.3, but still a signal of importance (PD-12) |
| 11.5 Predictions recorded before any substantive finding is disclosed | held in part | `predictions-outside-observer.md` does not exist; 05 says nothing was disclosed. All outputs are pushed to `origin`, so observer blindness rests on the observer not reading that branch |
| 12 Deviations filed, thresholds never changed after measurement | held in part | 114 of 414 records carry a non-null `prereg.deviation`. No threshold was moved (V finds no adapted criterion). Two operationalisations were chosen with data in view by the synthesis: "claimed" for approved-plan cells (H04) and entry-level against ledger-level references (H05). V overturned H05 on the second |
| Header: pre-registration SHA recorded in every finding | not held | `ab118801fd` appears in 0 of 414 records; investigators were not given it (PD-10) |

## 2. Rulings R1 to R12

| Ruling | Grade | Evidence |
|---|---|---|
| R1 Additive-only storage | held | Research branch against base: 1,800 paths, all status `A`; 0 paths outside the report folder and the Mission folder (`envelope-check.txt`) |
| R2 Hybrid vehicle; research-Mission defect verified in a disposable environment | held | Mission scaffold by the CLI (`d0b07dcaf6`); PX-01 run in a clone (E1), replayed by R3. The Mission folder holds no plan, unlike D-1 says (PD-19) |
| R3 Five independence dimensions | held in part | Briefs and matrices keep all five apart. The two synthesisers fill the M04 matrix differently (34 against 43 claimed cells; S-B changed five investigator cells, S-A none) and neither document names the other (PD-11; wording-review L-001; synthesis-challenge X2 to X4) |
| R4 Four views apart | held in part | Every record carries a view. Mislabels found: F-A2-012 (R1), F-E1-029 and F-E1-033 (R3), plus synthesis statements graded by V and L; none changes a verdict |
| R5 Prospective terms, no deficiency from absence | held in part | Briefs state the rule (COMMON, A2, F). L-019 (major): "missing" for cancellation and attachment in the H07 table, where no record places either |
| R6 Maintenance window from the architect, separate from agent figures | held in part | Window recorded in 04 before dispatch. The architect confirmed dates the coordinator had proposed from grounding, after the coordinator had seen raw M01b counts (declared in 04 and 00 section 4). Agent authorship kept out of supervision measures (C, C2 M01g) |
| R7 Execution allocation; operations log single case; desk labels | held | F tags operations-log items as single case; AS-10 labelled desk only (V). The F comparator came from the brief (PD-02) |
| R8 Revision model | held in part | Every record names a revision and kind. D1's pin table did not precede other citations; workstreams ran in parallel on the pins copied into `COMMON.txt` |
| R9 Neutral dispatch, evidence-first synthesis, independent review, separate mutation author and gate runner, reproduction sampling | held in part | Structure in place; weakened by PD-01 to PD-05, PD-12 to PD-14 |
| R10 Blind C2 under another model; prediction packet | held in part | C2 held (model and profile differ). CX, which compares them, runs on the same model and profile as C2 (PD-15). Predictions not yet returned |
| R11 Java in scope; blocked builds as coverage limits | held | Events Gradle blocked by HTTP 429 in every attempt (B2, D2, R2); marked not assessable throughout; charter built with capped heaps |
| R12 Non-remedial | held | No issue, pull request or tracked change outside the report and Mission folders; D2's pin rehearsal and E3's patches stayed in disposable clones (E3 scratch: 1.4 MB, no clone left) |

## 3. Neutrality of the dispatch

No brief names a hypothesis, a threshold or the design brief's failure modes. Most measure definitions are neutral. Five passages carry a direction or a prior expectation.

1. **PX-01** (`E1.txt`, item 8): "Record the first step that cannot be passed, the guard that refuses, what the guard waits for, and whether any documented CLI command or documented procedure produces it." The outcome list includes "completes", but the instruction presumes a stall and names the mechanism grounding had already suspected (00, D-1). The outcome is mechanical and R3 replayed it, so the effect on the result is none; neutrality is weakened.
2. **H06a** (`H06a.txt`): "other sources that say something different (cite; this matters)". H06b then read that column before its own contradiction search. This leans toward finding contradictions, which leans H06 toward support. The verdict rests on 2 of 20 meeting all three conditions, far from the threshold of 10, so the effect is "weakens".
3. **F** (`F.txt`): "(for example: work-package eligibility, dependency gating, ... resume)" lists exactly fifteen items, and F adopted them as the comparator. The pre-registration asks the workstream to list the comparator before classifying; in practice the coordinator wrote it after grounding. These are well-tested areas of core, which raises the comparator and leans H07 toward support. H07 came out contradicted, so it holds a fortiori; V notes the margin rests on one row (X06).
4. **E3** (`E3.txt`): "expect a few dozen files, not all 400". The frozen set became 66 of 310 files. R3 shows four of the seven "not detected" core mutations fail a battery gate outside the set, and per-change CI selects the battery. The brief's estimate narrowed the measure and produced a headline that understates detection (F-E3-006 "wider than evidence").
5. **B1**: "Exception leakage", "CLI leakage" are loaded labels on neutral counts. Effect none.

The report path tells every agent the purpose (`wayfinder-reconnaissance`). The protective sentences of `COMMON.txt` (absence is not a deficiency, a blocked build is a coverage limit) lean against over-reading.

## 4. Evidence-first synthesis

| Synthesiser | Phase 1 against final | Differences file |
|---|---|---|
| S-A (hypotheses) | Phase-1 verdicts H01 to H08 and PX-01 equal the final ones. Scenario classifications equal. H04's basis changed from "none I can fix without interpretation" to one capability counted; the label "inconclusive (partial)" was already in phase 1 | Names 8 points of difference and 5 document changes. States "No verdict changed between phase 1 and phase 2", which is true of the verdict words |
| S-B (components, independence, execution) | Phase 1 is the longest (2,491 words); five investigator cell values replaced by the synthesiser's own; one restored after phase 2 (charter service deployment) | Ten changes adopted from investigators, each with its source; marks four statements as own inference |
| S-C (invariants, knowledge model, decisions) | Phase 1 read the design brief and the S-A and S-B consolidated documents, which name investigator readings (declared). Four statements changed after phase 2, two credited to investigators | Clear; one inference kept against both G workstreams |

It held for S-A and S-B: phase-1 readings are explicit and every later change is attributed. It held in part for S-C. The phase order is not provable from the record (PD-14), and two incompatible M04 matrices reached the review unreconciled, where four major items caught them.

## 5. Coordinator within section 11.4

No brief paraphrases a finding, the procedure notes read no result, and the packet was not filtered. Outside a strict reading: unrecorded mid-run instructions (PD-09); a breach list that omits E2's and G1's exposure to guidance text and the F comparator's origin (PD-01, PD-02), and says "four" breaching workstreams where it lists five (PD-20); the decisive flag passed to reproducers (PD-12).

## 6. Deviations and their likely effect

All 20, declared or not, are in `process-deviations.csv` with evidence. By effect:

- **Invalidates:** none found.
- **Weakens a result:** PD-01 (agent-guidance text in every executor's context; reached H06a run 1, the contract-only G1 arm and the blind author E2, who used ArchUnit-method knowledge in two subtle Java mutations; leans H06 toward support, mutation detection toward non-detection, and H08 conservatively, since G1 had more than contracts and still differed); PD-02 (H07 comparator); PD-03 (E3 gate set); PD-05 and PD-06 (H06); PD-11 (two M04 matrices, H04); PD-12 (decisive flag, review); PD-13 and PD-14 (evidence-first for S-C, phase order).
- **Weakens auditability only:** PD-09 (G1 and G2 constraints, C2 cast, reviewer sets, mid-run and resume instructions absent from `dispatch/`; the condition that defines the H08 test is not in the record), PD-10 (pre-registration SHA).
- **None, or none to weakens:** PD-04, PD-07, PD-08, PD-15 (cast; CX shares model and profile with C2), PD-16 (declared breaches; V finds no verdict changed), PD-18 to PD-20.
- **Not assessable:** PD-17 (seven interrupted workstreams; resume texts not recorded).

Undeclared by the coordinator: PD-01 for E2 and G1, PD-02 to PD-05, PD-08 to PD-12, PD-14, PD-18 to PD-20. PD-01 is the largest; it is a property of the environment, not a lapse, but it is not listed among the limits.

## 7. Envelope

- **Production repositories.** All 18 checkouts have no tracked change, no stash and one worktree. Every HEAD equals the revision named in the pre-registration or `COMMON.txt`; core is at the research branch tip. The only untracked file in core was my own `envelope-check.txt`.
- **Research branch.** Against base `5c4fc5a79d`, 1,800 added paths and no modified or deleted path. 0 paths outside `docs/reports/wayfinder-reconnaissance/` and the Mission folder `kitty-specs/wayfinder-ecosystem-reconnaissance-01M8GNWM/` (five files, CLI scaffold plus status log). No rule, CI configuration or existing document was modified.
- **Ignored state.** Core's `.pytest_cache/` holds a test virtualenv created 08:38 to 08:39 UTC, before the pre-registration commit (08:40): grounding ran tests in the production checkout (PD-18). `context-state.json` comes from the mandated `charter context`; the pack trees from `make sync-packs`. None is tracked; effect none.
- **Remote.** The branch is pushed (D-2 permits it); GitHub was not queried.

## 8. What to do differently next time (process only)

1. Run blind arms (documentation-only answerer, contract-only checker, blind mutation author) in sessions without project agent-guidance files, or record the injected text as an input and grade blindness by it.
2. Commit every per-agent prompt in `dispatch/`: information constraints, model, profile, mid-run and resume messages.
3. Give no example list or size where the workstream must fix a list or frame itself (M07b, the gate set).
4. Phrase experiments without the expected outcome ("how far does the Mission advance, and why does it stop if it does").
5. Commit each phase-1 file, and the C′ output, on its own before the next phase is unsealed.
6. Name one owner for any table two parallel synthesisers both present.
7. Choose the decisive set apart from the synthesiser, and do not show reproducers which findings are decisive.
8. Pre-register the unit of every ambiguous count (approved-plan claims, entry against ledger references, recorded exceptions).
9. Run grounding in disposable clones too.
10. Put the pre-registration SHA in the common brief.
11. Keep 05 and README current.
12. Collect the observer's predictions before findings reach a branch the observer could read.
