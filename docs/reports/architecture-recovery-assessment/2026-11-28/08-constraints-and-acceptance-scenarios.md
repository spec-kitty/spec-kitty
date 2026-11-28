---
doc_status: draft
updated: '2026-11-28'
---

# 8. Architectural constraints and acceptance scenarios

Consolidator K4, profile `architect-alphonso`; its verb "decide" yields to the envelope. `02`, `03`, `04`, `06` are the deliverables of this folder. "P3" is pattern 3 of `03`; "03:D3.1" is a case of `03` (not a decision id of `09`); "RC1" is a root cause of `02` section 4; Tags: [read] and [executed] are mine at head; [relayed] is checked by an input. Everything here is **intended target** unless a row says otherwise.

## 1. Conclusion

1. **Twenty-seven constraints keep the recommended design from eroding.** Each is stated so that a check could decide it and names the pattern it stops from returning. Thirteen can be decided by a static check, five by a behavioural scenario, nine only through a small register that a human maintains and a check keeps consistent.
2. **The present gates pass with all ten patterns of `03` present.** Core has about 400 entries under `tests/architectural` [executed: `ls | wc -l`, 405] and a register of 62 state surfaces (`src/specify_cli/state/contract.py` [executed]). They record what exists and check direction. The constraints here check **necessity, ownership and ends**.
3. **A structural check cannot find semantic duplication.** It finds a restated literal, a second writer, a missing register row. Whether a new mechanism repeats the intent of an old one is a human judgement, so AC-06, AC-15, AC-18 and AC-20 rest on a register plus review. That is the main requirement on an architectural knowledge capability (section 5).
4. **Twenty-three acceptance scenarios cover the five principles of ruling R8**; four more test erosion at change time. Twelve depend on an open decision.
5. **Where the code violates a constraint today, the check starts as a shrink-only count.** Each count is transitional and ends at zero by a named roadmap step. A ratchet without an end is how seven arrangements became permanent (`02` section 3).

## 2. Constraints

Kinds of check: **static** (reads source), **behavioural** (runs a scenario of section 4), **register** (a data file checked against itself and source). "Today" is the present state or the decision waited for.

### A. Extension mechanisms are used by the built-ins

| Id | Constraint | A check looks at | Prevents | Today |
|---|---|---|---|---|
| AC-01 | Core compares no identifier that originates in a pack (mission-type key, step id, artefact kind, profile id) with a literal | static: comparisons, dictionary keys and match arms on a type, step or kind value, outside the upgrade component; shrink-only list by file and symbol | P3 (03:D3.1 to D3.5, D3.9); RC2; the architect's example | fails: `_GUARD_TABLES` keyed by four type names (`src/runtime/next/runtime_bridge_cores.py:859-864` [read]); 152 quoted `software-dev` literals in 61 non-migration files [executed: `grep -rn` for the quoted literal; CH counted 156 in 64] |
| AC-02 | Built-in mission types and tools load through the same loader and format as a project's; no reserved key, no second table | behavioural: scenario S-13; static: one loader symbol, no table of built-in keys | P3 (03:D3.8, D3.10); P6 (03:D6.1) | fails: `mission == "software-dev" or snapshot.wp_driven` (`src/runtime/next/runtime_bridge_composition.py:509` [read]) |
| AC-03 | Every step that declares a command gets one, whatever its type | static: generated command set equals the declared steps of the activated types | P3 (03:D3.6) | fails: fixed tuple (`src/specify_cli/skills/command_installer.py:101-114` [read]) |
| AC-04 | A tool id appears only in tool data rows | static: literal scan for registered tool ids outside the rows and the upgrade component | P3 (03:D3.10) | 44 non-migration files [relayed CH]; waits for D10 |
| AC-05 | Core knows the transitions the record contract names (`start`, `submit`, `verdict`, `accept`, `land`) and no step id; a step declares which transition completes it | static: core's verb list equals the contract's; no step id of any pack occurs in core | the architect's example again (CH T4) | `review` and `accept` are both step ids and core operations |

### B. One owner per domain rule

| Id | Constraint | A check looks at | Prevents | Today |
|---|---|---|---|---|
| AC-06 | Each domain rule has one owning component and one symbol; callers ask the owner | register: rule, owner, symbol. static: lane-state literals, the bookkeeping-path test and target-branch derivation occur only in the owner | P7 (03:D7.1 to D7.6); P2 (03:D2.3 to D2.5) | "approved or done" restated 34 times; about 22 target-branch resolvers [relayed X1] |
| AC-07 | An interface module parses, calls one operation and renders. It defines no guard, no refusal code and resolves no path | static: modules under `cli` and the API import the operations facade and rendering only; none imports git, record or store modules or defines a refusal literal | rules without an owner (`02`, command layer; RC5); P4 (03:D4.2) | `cli` is 107,407 lines; one gates module 1,703 [relayed `04` section 8] |
| AC-08 | Every door (CLI, generated command, programmatic API) reaches the same operation and so the same guards | behavioural: S-16 runs each refusal through every door. static: each API verb maps to one operation; no second executor | P4 (03:D4.1, D4.3, D4.6) | fails: the API lands "with no claim and no gate behind it (and no rollback)" (`src/specify_cli/orchestrator_api/consolidation.py:586` [read]) |
| AC-09 | A rule that exists in two languages or repositories has one named definition; the other side is generated from it or held by a conformance corpus that is a required check | register across repositories; the required-check list of each repository names the corpus | P2 (03:D2.1 to D2.7); RC3 | charter conformance corpus dropped as a gate [relayed M5]; waits for D4, D6 |

### C. One authority per store

| Id | Constraint | A check looks at | Prevents | Today |
|---|---|---|---|---|
| AC-10 | One authority per fact and one writing component per store; everything else is declared a view | register: no fact twice, one writer per store. static: writes to a store path come from its writer only | P5 (03:D5.1 to D5.9) | 62 registered surfaces [executed]; 17 lifecycle stores [relayed M3]; target is eight (`04` section 9) |
| AC-11 | No mutable Mission state in any working tree | behavioural: after every operation of section 4, `git status --porcelain` is empty in every checkout. static: the record writer takes no working-tree path | P1 (03:D1.1 to D1.5); RC1 | waits for D1 |
| AC-12 | A view is never read as authority and is reproducible | static: no operation reads a view to decide. behavioural: delete and rebuild gives equal bytes; the manifest hashes inputs and outputs | P5 (03:D5.2); a hand-edited bundle (CH C18) | frontmatter lane still written (`src/specify_cli/status/emit.py:640` [read]) |
| AC-13 | An event that names a commit is shared only together with that commit; unshared events are counted on every operation | behavioural: S-17 | hidden local-only authority (CH F2); steelman S1 | waits for D2 |
| AC-14 | Correctness needs no clone-local configuration: no hook, merge driver or git setting | behavioural: S-22 in a fresh clone. static: no write to `.git/config`, `.git/hooks`, `.git/info` | P1 (03:D1.5); steelman S20 | recorder hooks and a merge driver are installed today [relayed M1, M4] |

### D. No unearned generality

| Id | Constraint | A check looks at | Prevents | Today |
|---|---|---|---|---|
| AC-15 | No mode without two real users. A mode is a stored or flag-selected value that changes which code path carries a responsibility. Each names two documented journeys needing different values (journeys, not usage counts: R15) | register: enum members against rows. static: a mode whose values give the same result on the default path is flagged | speculative generality (`02`, M1); P1 (03:D1.1) | four topologies; "a user is never asked to want a topology" (`needs/needs-and-journeys.md` section 4 [read]) |
| AC-16 | Every port, registry or seam has a production implementation and a production caller in the same release | static: protocol and registry symbols with no implementer or no caller outside tests | P9 (03:D9.1 to D9.6) | produce seam: no registrant in `src` [executed: no call of a `register_*_handler`] |

### E. Compensation is named

| Id | Constraint | A check looks at | Prevents | Today |
|---|---|---|---|---|
| AC-17 | Every compensating guard names what it compensates. A refusal code states what it protects against: user input, git or the environment, another actor, or **a named mechanism of the tool itself**. The last class needs a transitional entry (AC-20) | register: every refusal literal in source has a row; the count of the last class only shrinks | P1; RC1, RC4 | 374 refusal-style literals; about 70 in three families that name two mechanisms [relayed X1] |
| AC-18 | A guard records the failure it answers (an issue or a scenario id). It is removed only if that scenario stays green by other means | register field; the named scenario exists and runs | the reverse erosion: 7 of 36 proposed removals bring a recorded failure back (`02` section 5) | reasons live in ADR amendments and comments |
| AC-19 | Repair vocabulary (heal, repair, backfill, restamp, reconcile) exists only in the upgrade component and the one doctor; the doctor checks only stores of the register | static: name scan, shrink-only | P1 (219 such functions, 18 doctor modules [relayed `03`]) | 25 doctor subcommands, 14 `migrate` subcommands [relayed M8] |

### F. One generation at a time

| Id | Constraint | A check looks at | Prevents | Today |
|---|---|---|---|---|
| AC-20 | A change that introduces a replacement removes what it replaces in the same release, or adds a transitional entry: what, owner, end condition (a version or an event), the symbols to delete | register; release check fails when the end version is reached and a named symbol still exists | P8; P6; RC3; "generations running at once" (`02` section 3) | seven arrangements with no end (`02` section 3) |
| AC-21 | One shape authority. The schema gate is effective, and no module outside the upgrade component reads an older shape | static: the minimum supported schema equals the floor; no import from upgrade or migration packages elsewhere; no "unmigrated" refusal elsewhere | P8 (03:D8.1 to D8.3); RC6 | `MIN_SUPPORTED_SCHEMA = MAX_SUPPORTED_SCHEMA = 3` (`src/specify_cli/migration/schema_version.py:22-23` [read]); waits for D9 |
| AC-22 | A known hole is an exception with identity, owner and end; the set only shrinks | register: each strict `xfail` and allow-list entry has the three fields | P8 (18 pinned residuals in landing [relayed M7]) | owner on 2 of 30 sampled ledger entries [relayed W F-E1-025] |
| AC-23 | A decision that changes meaning is a new record that supersedes; one record is in force per subject | register: one in-force record per mechanism; no amendment heading in records after the cut | compounding by amendment (`02` conclusion 5: 41 amendment headings on five ADRs [relayed]) | waits for D15 |

### G. The principles are carried by mechanism

| Id | Constraint | A check looks at | Prevents | Today |
|---|---|---|---|---|
| AC-24 | Only `land` writes the target, and only to a commit an acceptance event names | static: one call site updates the target ref. behavioural: S-01, S-02 | Human in Charge carried by instruction (`02`, M6) | `--commit-to-target` and three landing paths exist |
| AC-25 | One exception path: an override is one event with actor, reason, guard and commit. No flag changes a guard's verdict | static: no `force` or attestation parameter outside the override operation | P1 (03:D1.6); a forced state that does not mean what it says (`02`, M3) | five attestation families, a force flag [relayed M7, M3] |
| AC-26 | A change of the rules in force is a committed diff made by a human act | static in CI: rebuilding the bundle gives the committed bytes. behavioural: S-04 | steelman S6; delivery depending on checkout state (`02`, M5) | waits for D6, D7 |

### H. One vocabulary

| Id | Constraint | A check looks at | Prevents | Today |
|---|---|---|---|---|
| AC-27 | On every contract surface one fact has one key and one word has one sense | static: contract schemas against a key list; "lane" names one thing | P10 (03:D10.1 to D10.5) | nine JSON keys for branch facts [relayed X1] |

## 3. Where the inputs disagree about a constraint

| Constraint | Disagreement | What settles it |
|---|---|---|
| AC-01 | Both candidates propose a gate. CH: at this scale "a programme of work, not a test to switch on" | a shrink-only count that ends when built-ins are data |
| AC-15 | Delete-first reads "two users" from use; R15 forbids that | the register cites journeys; one journey with a recorded failure behind it (steelman S7, S22) is kept as a rule, not a mode |
| AC-17 against AC-18 | AC-17 pushes to delete compensators; AC-18 keeps the reason. For steelman S1 and S3 the assessor and the steelman differ on whether the guard is compensation | D2 and D3 of `09` |
| AC-24 | The candidate gives up per-line proof of what landed; CH grades the loss major, argued | D18 of `09` |

## 4. Acceptance scenarios

"Needs" names the decision of `09` whose default a scenario assumes.

### Human in Charge

| Id | Given | When | Then | Needs |
|---|---|---|---|---|
| S-01 | every work package approved; no acceptance event | any actor calls `land` through any door | refused; the target does not move | |
| S-02 | acceptance names commit A; the Mission tip is now B | `land` | refused until a human accepts B; the acceptance listing names every commit outside an approved range | D3 |
| S-03 | no standing delegation is recorded | a non-interactive caller calls `accept` | refused. With a delegation recorded by a named human it succeeds and the event cites the delegation | D12 |
| S-04 | a project took a pack with `only:` | the pack pin is bumped to a release with new rules | the rebuilt bundle is unchanged for that pack. For a pack taken whole the new rules appear as a diff and are not in force until committed | D7 |
| S-05 | a guard refuses a move | a human overrides with a reason | one override event names actor, reason, guard and commit; no other route makes the move legal | |

### Responsible delegation

| Id | Given | When | Then | Needs |
|---|---|---|---|---|
| S-06 | the human attends only the final decision | agents drive the Mission to a human-decision step | `decide` answers "wait" at every door; the record shows per step the role, profile and bundle digest that acted | |
| S-07 | an agent approves a work package | the approval is recorded | the Mission branch holds the approved commit; the target is untouched; a later cancel is a revert shown in the acceptance listing | D3 |
| S-08 | no Mission exists | a short task is dispatched with a profile | Op events name profile, bundle digest and outcome; no keyword decides the profile | |

### Explicit responsibility ownership

| Id | Given | When | Then | Needs |
|---|---|---|---|---|
| S-09 | actor X submitted a work package | X records an approving verdict through any door | refused by the one independence guard; an identity unknown on one side never proves independence | D4 |
| S-10 | a landed Mission | its record is read | per work package it answers who implemented, who reviewed, which commit was approved, who accepted, who landed, without reading branch history | D1 |
| S-11 | an organisation pack requires a rule | a project excludes it | compile refuses and names the pack; a CI check refuses the same commit | |

### Independent evolvability

| Id | Given | When | Then | Needs |
|---|---|---|---|---|
| S-12 | a pack with a new mission type that uses only the closed check vocabulary | it is activated on an unchanged CLI | creation, a command per declared step, `decide`, gates and landing work; core contains no reference to its key | |
| S-13 | a built-in type copied into a project pack under another key | a Mission of that key runs | the step sequence and every gate verdict equal the built-in's | |
| S-14 | a client built against API 2.x | the CLI is upgraded within the major version | the contract's conformance fixtures pass unchanged | D11 |
| S-15 | a Mission in flight with a committed type lock | the pack pin or the CLI changes | that Mission's steps do not change until a human relocks | |

### Governed Mission coordination

| Id | Given | When | Then | Needs |
|---|---|---|---|---|
| S-16 | one Mission state | the same illegal move is tried through the CLI, a generated command and the API | the same refusal code three times; no state change | D11 |
| S-17 | two clones each approve a different work package | both run `sync` | the record replays in append order; a row no longer legal is refused and reported; both approved commits are ancestors of the joined tip; an earlier acceptance no longer matches | D2, D3 |
| S-18 | two agents | both start the same work package | one start event is appended; the other caller is refused | |
| S-19 | WP02 depends on WP01, not yet approved | WP02 is started through any door | refused. After approval WP02's branch is cut from a tip that contains WP01's approved commit | D3 |
| S-20 | an operation is interrupted at any point | it is run again | it completes or refuses; no branch is half-moved; no repair command is needed | |
| S-21 | two checkouts at the same commit | each asks for the context of a step | identical text, from the committed bundle | D6 |
| S-22 | a fresh clone; no reconcile has run | pull, then `read` | the state is correct | D1 |
| S-23 | a repository with no remote | a Mission runs from specification to a local landing | it completes; `sync` does nothing | |

### Erosion at change time

| Id | Given | When | Then |
|---|---|---|---|
| E-01 | a change writes an existing fact to a second file | checks run | AC-10 fails and names the fact and its authority |
| E-02 | a change adds a refusal code that protects against another mechanism of the tool, with no transitional entry | checks run | AC-17 fails |
| E-03 | a transitional entry whose end version is the release being cut | the release check runs | it fails while a named symbol exists |
| E-04 | a change introduces a second mechanism for an existing capability and declares nothing | checks run | **no check fails.** Only review against the capability map catches it |

E-04 is the limit that section 5 answers.

## 5. What this implies for an architectural knowledge and assurance capability (Wayfinder)

Following R19, these requirements come only from the problems and decisions of this exercise. The purpose is to keep the design coherent while it changes, not to protect what exists.

### Requirements derived here

| Id | Requirement | The problem found here | Serves |
|---|---|---|---|
| W-1 | A capability map: each mechanism names the capability it serves; each package has a stated responsibility | 59 mechanisms for 32 capabilities; 5 with "no reason found"; about 79,000 lines with no assessor (`06` X.1, X.3) | E-04; AC-15 |
| W-2 | A generation and transition register: per subject the one target generation, and each older one as transitional with an end or as legacy | three to six generations live in every mechanism; seven arrangements without end (`02` section 3) | AC-20, AC-21 |
| W-3 | A rule-ownership register, across repositories for the few rules that cross | one rule in two languages; guards at three levels; five rules duplicated (P2, P4, P7) | AC-06, AC-09 |
| W-4 | A store register that carries the rule "one authority, one writer", not only the inventory | 62 surfaces were registered and still grew (P5) | AC-10, AC-12 |
| W-5 | A reason on every guard and exception: the failure answered, the owner, the end | compensation chains (P1); 18 pinned residuals without end; reasons found only by a steelman pass | AC-17, AC-18, AC-22 |
| W-6 | Decisions in force per subject, superseded as sets; each constraint and roadmap step names the decision it rests on | 41 amendment headings on five records; D1 to D22 gate dispositions (`09`) | AC-23 |
| W-7 | Scenarios bound to principles, run through every door | the guarantee depends on the door (P4) | AC-08, AC-24 |
| W-8 | A recurring necessity review: a human reads W-1 and W-2 against the needs before each release | no check can decide E-04 | AC-15, AC-20 |

### Against the earlier proposal (`W/synthesis/knowledge-model.md`)

| Element there | This exercise | Why |
|---|---|---|
| K1 decision index | **confirms**, and adds supersession by set | W-6 |
| K2 component register | **narrows**: the unit is capability to mechanism to owner, not names per view | W-1; the map of `01` was the artefact every later deliverable needed |
| K3 contract and pin register | **narrows** to rules and formats implemented twice (charter, record); pin distance was not a problem found here | W-3 |
| K4 invariant and exception register | **confirms** identity and owner; **contradicts** a ratchet as an end state: every ratchet needs an end (AC-20, AC-22) | W-5 |
| K5 term map, K7 evidence records | no evidence here; P10 is the cheapest pattern of `03` | AC-27 is a contract lint |
| K6 scenario set | **confirms**, with other content: principles and doors, not cross-repository flows | W-7 |
| "The knowledge exists and is mostly right; it is spread" | **contradicts** for this class of problem: the missing knowledge is why a mechanism exists, what it compensates and when it ends; no record holds it | W-1, W-2, W-5 |
| "The enforced model is the intent of record" for structure | **contradicts** as sufficient: the enforced pair passes with all ten patterns present | section 1, item 2 |
| Shapes A to D | **narrows** to registers inside the owning repository first; a cross-repository index is needed for W-3 and W-6 only | most root causes are inside core (`02` section 4) |
| No service, database or new language | **confirms** | every check above reads files or runs a scenario |

Two cautions. Wayfinder is subject to its own constraints: its registers are stores under AC-10, and a register that needs a doctor is a compensator under AC-17. A few files in core and one cross-repository index carry W-1 to W-7. And its first content should be the target's constraints and the decisions of `09`, not a model of the present: lanes, topologies and the placement seam are proposed for removal.

## 6. Limits and what would change this

- References marked [read] or [executed] are re-checked; the rest are relayed. `05` and `07` were not read. No check was built.
- The defaults of `09` are assumed. If D1 is refused, AC-11 becomes "status is written by one component to one branch" and AC-13, AC-14 lose their subject. If D3 goes to thin lanes, AC-24 needs an attribution rule and S-07, S-17, S-19 change.
- Decision-material: whether the architect wants constraints that need a human-maintained register (D20). Settled by experiment: the false-positive rate of AC-01 and AC-07 on one package.
