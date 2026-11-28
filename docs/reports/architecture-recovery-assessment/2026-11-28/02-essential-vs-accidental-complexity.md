---
doc_status: draft
updated: '2026-11-28'
---

# 2. Essential versus accidental complexity

Consolidator K1, profile `synthesizer-sam`. This file judges the **current implementation** against the needs and names no target. Sources: `mechanisms/M1` to `M8`, `duplication/` (X1), `needs/` (N1), `challenge/steelman.md` (ST), `challenge/candidate-challenge.md` (CH). "K1" marks what I measured or re-read at head. Code references are to core unless a repository is named.

## Conclusion: how problematic is the present architecture

**Seriously, in a narrow and recoverable way.** Five statements carry the answer.

1. **The needs are sound and small.** 32 capabilities, 12 rated core. No assessor found a core capability that should not exist. The problem is in the implementation (R14).
2. **The implementation is about one and a half to two times what the needs require, and the excess is concentrated.** Summing the deletions the eight assessors name, about 110,000 of core's 524,936 lines serve no need that a simpler mechanism would not meet (the sum is candidate CB's, which CH section 7 found consistent with its sources), and a further 78,000 (the Python charter) are one of two complete implementations of the same thing. That is a floor of about a third of core. For the five packages around workspaces, status and landing (96,289 lines, CH CA01 [executed]) the assessors put the essential share at a fifth to a half.
3. **Every mechanism assessed runs several generations of its own solution at once**, between three and six (section 3). In no case was the older generation removed when the newer arrived. The architect's example (configurable mission types beside hardcoded conditionals) is one instance of a pattern that every assessor found in their own mechanism.
4. **The incoherence produces defects today**, not only cost: a research Mission is blocked by a guard whose events nothing writes (M2 5.4); what governance text an agent receives depends on per-checkout state (M5 5.1, [executed]); the public machine interface lands work with no claim, gate or rollback (`orchestrator_api/consolidation.py:586` [read K1]); both known API clients have drifted (M6 5.6); 18 strict `xfail` tests pin known holes in landing (M7 section 5).
5. **It compounds.** Each fix adds a rule and names a new residual: five landing ADRs carry 41 amendment headings (M7 section 4); the migration-ledger ADR gathered 8 amendments in six weeks (M8 5.3, CH R12 [executed]).

Two limits. **Not all of the complexity is accidental**: of 36 proposed removals the steelman found 7 where a recorded failure would return (section 5). And the largest delete-first claim was found false: an end state of 25,000 to 40,000 lines does not follow from the deletions named (CH CA02). The honest range of excess is a third to a half of core, not nine tenths.

One root cause sits under four of the eight mechanisms: **status and planning artefacts are tracked files on branches that also carry code** (M1 section 7; M3 section 10; M4 section 10; M7 section 10). Four assessors reached it independently; it makes their mechanisms one design problem.

## 1. Summary table

"Essential share" is my rough reading of each assessor's alternatives ([inferred]; overlapping packages; a pointer to proportion, not a measurement). Excess sources use the brief's categories: compensation for another mechanism (Comp), remnant (Rem), special case (Spec), duplication (Dup), compatibility (Compat), speculative generality (Gen).

| Mechanism | The need, in one line | What exists | Essential share | Main sources of excess | Generations live | Contested |
|---|---|---|---|---|---|---|
| M1 Workspaces: lanes, worktrees, topology, coordination, placement | isolated working copies for parallel work on a Mission branch | 44,500 lines; 4 topologies, 5 surfaces over 23 artefact kinds; about 120 refusal codes | a third to a half | Comp (status in the tree), Rem (G0, G1), Gen (the grid), Spec (keyword heuristic) | 5, a sixth proposed | S3, S4, S8, S11 |
| M2 Mission-type configuration and step runtime | a kind of work as data; one loop that gates steps | 27,000 lines; 9 file kinds per type; 7 step lists | half to two thirds | Spec (Python tables for built-ins), Dup, Rem (G0, G1), Gen (workflows, RACI) | 6 | S7, S13, S14 |
| M3 Mission and work-package lifecycle | know where things stand; refuse illegal moves | about 64,000 lines around an 883-line state machine; 17 stores; 10 lifecycles | about half; a third of `status/` | Comp (log placement), Dup (state machine three times), Rem (frontmatter lane), Compat | 3 | S1, S15, S16 |
| M4 Event handling | a durable, ordered record that people and tools can read | Python in core, a shared package (18.6k), two Java services (19.5k main) | about a third across the three places | Dup (fold four times), Comp (ordering rules), Gen (seam, wide package, read service) | 3 | S1, S17, S28 |
| M5 Charter integration | the right rules to an agent at each step | 78,000 Python in core; about 137,000 Java; about 19 concepts | a fifth to a third across both | Dup (two full implementations), Rem (`selected_*`, legacy keys), Spec (per-kind flags), Gen (run-time graph) | 3 for activation; 5 plans for the move | S6, S10, S21 |
| M6 Execution coordination | decide, hand out, record, ask; teach the tool | about 75,000 lines; 7 ways to drive work; 17 tools | two thirds to three quarters | Comp (two cursors), Dup (second claim path, tool tables), Spec (fixed command set), Rem (lifecycle shims) | 3 inside `next` | S5, S7, S36 |
| M7 Consolidation and approval evidence | what lands is what was approved, by another; a failed landing leaves nothing | about 64,500 lines; 15 phases; 6 gate axes; about 60 refusal codes | a fifth of `consolidation/`; a third of the whole | Comp (mixed lanes, squash, coordination branch, plumbing), Dup (second executor) | 3 gate generations | S2, S3, S9, S18, S19 |
| M8 Upgrade migrations and compatibility | bring an older project to the current shape | about 67,000 lines with doctors and commands; 144 registered migrations; 14 backfill commands | a third to a half | Compat (back to 0.2.0), Dup (three channels), Rem, Gen (unused knobs, empty registry) | 5 | S20 |
| Command layer `cli` | render operations to a person, an agent, a program | 107,407 lines; 198 command entry functions | about a sixth is wiring; the rest follows the rows above | rules with no owning module | n/a | CH F4 |

Sizes are each assessor's section 4; `cli` is [executed K1]. Packages overlap between rows (`src/runtime` counts under M2, M3 and M6), so rows do not add up.

## 2. Per mechanism

### M1 Workspaces

**Essential:** one branch per Mission that is not the target; zero or more isolated working copies cut from it; a rule that keeps concurrent writers off the same files; dependency order; one status record every working copy can write; safe removal; git's one-checkout-per-branch rule. "Nothing here requires a mode" (M1 section 3).

**Beyond it:**

- The PRIMARY/COORD partition and its five-layer placement seam run for every read and write, yet on the default path both partitions resolve to the same branch (M1 5.1, E23, E24). *Compensation that the newest default made degenerate.*
- The coordination worktree is a second copy that can be wrong; a 1,278-line module seeds, restores and refuses around it (M1 5.2, E25). The project's own Proposed ADRs retire it (ST S23).
- Sparse exclusion of status from lane checkouts, a write guard and a clone-local migration exist only because status is a tracked file in the tree lanes are cut from (M1 5.4).
- Lane computation holds software vocabulary: `_SURFACE_KEYWORDS` merges two work packages into one lane on substrings such as "api" or "template" (`lanes/compute.py:302`, CH R13 [read]). *Special case in the CLI.* ST S11: the reason (do not let two agents edit the same files) is real and survives as "no disjoint `owned_files`, same lane".

**Assessor's verdict:** worktrees are independently necessary; lanes only as a thin assignment; topology management is three switches multiplied by where status lives.

### M2 Mission types and the step runtime

**Essential:** a type as data; per step a prompt, artefacts, a completion check from a small closed set, a role, governance references; one step kind that iterates over work packages; layering; a loop; stability for a Mission in flight. "None of this requires a type's name in code" (M2 section 3).

**Beyond it:**

- Six concerns are each solved twice: a Python table for the four built-in types and a declared file for custom types. Guards, plan substantiveness, requirement kinds, capabilities, step profile, step sequence (M2 5.2; `runtime_bridge_cores.py:859-864` [read K1]). The built-in path never exercises the extension mechanism.
- The step list of software-dev is stated on seven surfaces that disagree (M2 5.1).
- Two legacy generations still gate: `mission.yaml` phases that match no running step, kept byte-identical in two trees ([executed K1]: `diff -q` silent for all four types), and guards that count events only a retired engine wrote (M2 5.4).

### M3 Lifecycle

**Essential:** identity; a Mission position; a work-item state of about six values plus blocked; a legality rule with an audited override; dependency readiness; a review record; an append-only history; one read and safe concurrent writes (M3 section 3).

**Beyond it:** about ten lifecycles and 17 stores (M3 section 4). The frontmatter `lane` mirror is still written on every transition although the documentation says it is not (`status/emit.py:640, 823, 879, 1207` [read K1]). Guards sit at three levels, so the rule set depends on the command used (M3 5.7). A lane reached by force does not mean what it says, so landing re-reads history to decide whether an approval counts (M3 5.8). Five read sources, two write shells, a merge driver and surface guards exist because the log is a file on a topology-dependent branch.

**Contested:** the sentinel lanes answer a recorded defect and are needed while task files can exist without a record (ST S15); `claimed` opens the approval-evidence window (ST S16).

### M4 Event handling

**Essential:** a fact with identity, type, subject, actor, time and versioned payload; atomic appends; one ordering rule; one fold; one read door. A join rule is essential **only while** the record is written in several places and joined by git (M4 section 3, item 7).

**Beyond it:** the lane vocabulary five times and the fold four times in two languages, held together by parity oracles against a pinned core commit (M4 5.2). The Java write service is built, released and tested while every transition still goes through Python; the only production call of the launcher is `service stop` (M4 5.1). A read service nobody calls (M4 5.8).

**Contested, and decision-material:** M4 calls the wall-clock ordering, the approved-departure lift and the merge driver compensation. ST S1 shows the scenario they answer is recorded (two clones, one Mission; rejected work landed on `main`) and that it survives any design in which clones share the record through git. Whether these rules are essential depends on one ruling: is Mission state shared through git (C32) or through a single store. Both readings agree a simpler ordering rule is possible.

### M5 Charter integration

**Essential:** content with one identity; composition from shipped, organisation and project sources; a choice per project with exceptions and an organisation floor; scoping to mission type and action; a size budget with fetch on demand; reproducibility; projection into each tool (M5 section 3).

**Beyond it:** two complete implementations with no traffic between them, which already disagree on what an absent activation key means (M5 section 6). Five sources answer "is this rule in force" (M5 5.2). Three identities per artefact; two layering mechanisms (M5 5.3, 5.4). First-load state makes delivery depend on the checkout (M5 5.1).

**Contested:** the budget reason behind progressive disclosure is real (184 artefacts against a 32,000-token budget, ST S10); the defect is the stored timestamp, not the staging. Allow-list narrowing and the skills default answer recorded rules (ST S6).

### M6 Execution coordination

**Essential:** answer "what is legal next, for whom"; hand an executor a unit of work; make a claim exclusive; accept and check a result; stop and ask a person; expose this to a person, an agent and a program; teach the tool (M6 section 3).

**Beyond it:** two cursors for one Mission, reconciled at run time by guards that "protect one mechanism from another" (M6 5.1). Three routes inside `next`, a second claim implementation for programs, and per-tool tables in at least ten places (M6 5.2, 5.5; X1 1.8).

**Contested:** the frozen step definition has a reason the cursor does not (ST S7). Native files for twelve tools serve a core capability; narrowing to two formats rests on an unchecked assumption (ST S5).

**Human in Charge** is carried by mechanism at three points only: protected-branch refusals, the independence comparison, operator attestations. Elsewhere it is an instruction to the agent. The actor is a caller-asserted string (M6 section 11; `status/models.py:411-427` per M7).

### M7 Consolidation

**Essential:** an approval names a commit; what lands equals what was approved; canceled work does not land; the approver is not the author; landing is atomic or recoverable; evidence is fresh; cleanup does not destroy unmerged work. Git supplies three of these directly (M7 section 3).

**Beyond it**, each traced to another mechanism's design (M7 section 5):

| Complexity | Caused by |
|---|---|
| blob attribution, patch-id window | squash as the default, which destroys the commit identities that would prove equality |
| work-package attribution, windows, line attribution by `git blame` | several work packages sharing one lane |
| approval-stamp bound with anchors and a bookkeeping filter | approval is a status event about a moving branch, and bookkeeping commits share the code branch |
| teardown gate, late projection, strand repair | status on a second branch |
| snapshot, intents, unsettled refs, resume recovery | fifteen phases moving up to three branches |
| attestation flags | rules strict enough to refuse legitimate history |

"It mostly proves properties its own neighbours destroy" (M7 section 1); the assessor puts four fifths of `consolidation/` down to interaction.

**Contested:** local landing without a forge is a documented journey (ST S2). Mixed-lane protection is essential for as long as a lane holds more than one work package (ST S3); M1's and M7's preferred shapes disagree on exactly this. Attestations are one of the three Human-in-Charge mechanisms (ST S9).

### M8 Upgrade and compatibility

**Essential:** tell older from newer from unreadable; one-way data transformations, once and in order; per-clone effects; regeneration of agent copies; a record only for steps that are not idempotent; preview (M8 section 3).

**Beyond it:** content back to 0.2.0 with no documented need below 3.0 (M8 section 2). Three channels, each with its own record (M8 5.1). The start-up gate is a no-op: `MIN_SUPPORTED_SCHEMA = MAX_SUPPORTED_SCHEMA = 3` (`migration/schema_version.py:22-23` [read K1]), so 26 files outside the upgrade packages carry their own "unmigrated" refusal (M8 5.2).

**Beyond its size:** the legacy readers pin the other mechanisms. An unstamped topology, a Mission without `mission_id` and legacy activation keys each keep a fallback alive in runtime code (M8 section 6).

**Contested:** a fresh clone needs the merge-driver configuration before its first pull, which is earlier than any reconcile on `upgrade` or `init` (ST S20).

### The command layer

No input assessed it (CH F4). My light look (deliverable 1, section 4) [executed K1]: 194 files, 107,407 lines; 198 command entry functions hold 18,096 lines (17%); 113 files with no command entry hold 51,477 lines (48%). Five groups hold 55,000 lines tied to other mechanisms: `agent/tasks*.py`, `agent/mission*.py`, the doctors, upgrade and migrate, `agent/workflow*.py`.

**Essential:** parse, call one operation, render, map a refusal to an exit code.

**Beyond it:** the guards only `move-task` runs; the planning-commit pin driven from `finalize-tasks`; one of two claim paths; a doctor per mechanism that can enter a bad state; 154 distinct refusal-style codes. Its excess has no cause of its own: these are rules without an owner (X1 pattern 4), and it cannot be sized apart from M1, M3, M6 and M8. A module-by-module classification of the 113 files, a desk exercise, would settle its true proportion.

## 3. Generations running at once (R14)

| Subject | Generations live, oldest first, with the mark of each | Label of the oldest | Source |
|---|---|---|---|
| Workspace placement | G0 status in the lane worktree (`FRESH_LEGACY`); G1 coordination worktree at create; G2 partition by kind; G3 `single_branch`; G4 size default; G5 commit by ref (Proposed) | legacy | M1 section 4 |
| Mission-type definition | G0 `mission.yaml` + `Mission` class; G1 v1 state-machine residue (`mission-events.jsonl` guards); G2 runtime DAG; G3 step contracts; G4 charter descriptors and step folders; G5 workflows (dormant) | legacy, still read | M2 4.3 |
| Status storage | frontmatter `lane`; per-Mission JSONL with a Python reducer; Java write service (built, not bound) | legacy, still written | M3 5.1 |
| Event code | Python appenders in core; shared Python package; Java services | current | M4 section 4 |
| Activation | `selected_*` and legacy keys; activation ledger; charter service | transitional, no end | M5 5.2; X1 4.4 |
| Plan for moving the charter | five plans, from a doctrine wheel to "design as oracle, one switch" | each still visible | M5 section 6 |
| The `next` loop | internalised DAG engine; composition dispatch; board-driven iteration | current | M6 5.2 |
| Landing gate | SHA reachability; blob attribution; presence, canceled and line axes; all in one `verify()` | current | M7 section 5 |
| Agent copies | imperative per-version migrations (about 56); manifest-owned installer; declarative tool-surface plan | legacy | M8 section 6 |
| "What has run" | version window (`migrations.applied`, still written in memory); two-partition ledger; adoption; reconcilers; operator backfills | legacy | M8 section 13 |
| User documentation | project-level mission and one worktree per feature; per-Mission type with `merge`; topologies with `consolidate` | legacy | N1 section 6 |

### Transitional arrangements that became permanent (R17)

| Arrangement | Its own stated end | Source |
|---|---|---|
| Frontmatter lane mirror | "transitional"; none | M3 5.1 |
| `mission-events.jsonl` | "Phase 1B provisional"; awaits a "Phase 2" | M4 5.9; CH R16 |
| No-op schema gate | "a later release will bump MIN" | M8 section 13 |
| Legacy activation reader | epic child #6535 | M8 section 13 |
| Unstamped-topology derive at run time | none; a gate claims inference is retired | M8 section 13 |
| The 18 strict `xfail` residuals in landing | none | M7 section 5 |
| Python charter in core | "the single switch"; no date | M5 labels |

## 4. Root causes

| # | Cause | Mechanisms it inflates | Independent agreement |
|---|---|---|---|
| RC1 | Status and planning artefacts are tracked files on branches that carry code | M1, M3, M4, M7; the lane-worktree upgrade pass in M8 | M1, M3, M4, M7 each name it |
| RC2 | Built-in mission types predate the extension points and were never moved onto them | M2, M5 (5.6), M6 (5.3, 5.4), the command layer | M2, M6, X1 |
| RC3 | Moves begun and not finished, leaving both sides live: events to a service, charter to a service, runtime internalised whole, agent copies to a reconciler | M4, M5, M6, M8 | X1 pattern 3 |
| RC4 | An approval is an event about a shared, moving branch, not a named commit of one unit | M7; the evidence stamps carried in M3's rows | M7; M3 obstruction 2 |
| RC5 | No single Mission value answers target, branches, identity and status location; each command derives them | the command layer; X1 class 2 | X1 pattern 4 |
| RC6 | No upgrade floor; old shapes stay valid inputs, so runtime code keeps fallbacks | M8, and through it M1, M3, M5 | M8 |
| RC7 | No human identity; the actor is an asserted string | M6, M7 | M6, M7, ST section 6 |

RC1 and RC4 together answer the R18 question. Lanes, worktrees, consolidation and topology management are **not** independently complex. Worktrees are independently necessary. The rest is interaction.

## 5. What is not accidental

The steelman's verdicts on 36 proposed removals (ST section 1): the reason holds and the proposal loses it, 7; the reason holds and is kept by other means, 15; the reason no longer holds, 9; no reason found, 5. The seven, which must not be carried into any simplification as "accidental":

| Id | Mechanism | The failure that returns |
|---|---|---|
| S1 | ordering rules and merge driver | two clones write one Mission; a stale approval is read after a rejection |
| S2 | local landing without a forge | the solo journey ends at a local landing |
| S3 | mixed-lane protection | a canceled sibling's commits land, unless one branch holds one unit of review |
| S4 | lane test-origin probe | tests in a lane pass against the root checkout's code |
| S5 | native command files for twelve tools | a user's tool reads neither open format |
| S6 | allow-list narrowing; skills absent by default | a pin bump brings rules into force with no human act |
| S7 | frozen step definition | an upgrade mid-Mission changes the step list |

Fifteen more survive only on a condition, for example: lane work tips need an absorption check while landing squashes (S8); a clone-local reconcile must run before the first pull (S20).

## 6. Uncertainty

Decision-material (changes the proportions above):

- Is Mission state shared through git? If yes, part of M4's ordering and join complexity is essential (S1).
- May one branch hold more than one unit of review? If yes, M7's attribution core is essential (S3).
- Is a resident service on the write path wanted for 4.0? It decides which of M4's three places is the excess.
- Which upgrade floor? It decides how much of M8 and of the runtime fallbacks is essential.

Settled safely by experiment (each assessor's section 11): whether the placement seam can answer anything but "the topic branch" on the default path (M1); whether tree equality reproduces the landing gate's verdicts on landed Missions (M7); whether a closed check vocabulary covers the Python guards (M2); whether a fold by append order differs from the present one (M4).

What would change my reading: evidence that the built-in Python paths encode rules the declared mechanisms cannot express (X1 found none), or that most of the command layer's non-wiring half is rendering.
