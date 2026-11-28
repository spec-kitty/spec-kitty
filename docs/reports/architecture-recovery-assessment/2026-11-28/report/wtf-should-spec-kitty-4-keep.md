---
doc_status: draft
updated: '2026-11-28'
---

# Executive summary

**Bottom line.** This was a read-only assessment and design exercise on the Spec Kitty ecosystem. It asks what the 4.0 release should keep. What the product promises is sound and small: 32 documented capabilities, 12 of them rated core, and no assessor found a core capability that should not exist. The implementation is larger than those needs require, by an estimated third to a half of the main repository, and the excess is concentrated. Every mechanism examined runs three to six generations of its own solution at once, because the older one stayed when the newer arrived. Two design candidates written from opposite stances reached the same four structural choices independently. A challenge then found seven major gaps; two of them leave a choice conditional on the architect. Nothing here authorises work: the roadmap is a proposal, and 27 decisions are open.

| Measure | Value | Source |
|---|---|---|
| Documented capabilities; rated core | 32; 12 | `needs/capabilities.csv` |
| Python lines in the main repository ("core") | 524,936 | `01` section 5 |
| Excess over what the needs require | a third to a half of core (an estimate) | `02` conclusion |
| Generations of one solution live at once, per mechanism | 3 to 6 | `02` section 3 |
| Capabilities retained / simplified / left for investigation | 28 / 3 / 1; none rated core or important is removed | `06` section 1 |
| Mechanisms removed / replaced / consolidated / simplified / retained / to investigate | 19 / 12 / 9 / 9 / 5 / 5, of 59 | `06` section 1 |
| Proposed removals where a recorded failure would return | 7 of 36 | `challenge/steelman.md` |
| Load-bearing claims of the two candidates, checked in code | 13 true, 5 partly true, 2 false, of 20 | `challenge/candidate-challenge.md` |
| Roadmap steps; steps that need no ruling | 15; 4, plus 10 probes | `07` |
| Open decisions; decisions that gate most of the deletion | 27; 3 | `09` |

A Mission is Spec Kitty's unit of planned work, from agreed intent to an accepted result. A work package is one bounded piece of a Mission. "Core" is the main repository, `spec-kitty`. A mechanism is a part of the implementation that carries a capability.

**What we found.**

1. **The needs are fine; the implementation is the problem.** No documented need names lanes, topologies or a coordination branch. The assessors put the essential share of the five packages around workspaces, status and landing at a fifth to a half (`02`).
2. **One cause sits under four of the eight mechanisms.** The record of a Mission's progress and its planning documents are kept as ordinary files on the same git branches that carry code. Four assessors named this independently as the source of their own mechanism's excess (`02` section 4).
3. **The incoherence produces defects today.** A research Mission cannot pass one of its steps. The programmatic interface lands a Mission without the checks the command applies. The rules text an agent receives depends on the state of the checkout (`02` conclusion).
4. **Two opposite candidates agreed on four choices.** Keep the Mission record outside every working copy; give each work package its own branch; integrate approved work at once; make landing one equality check and one move. Two of the four stay conditional on a ruling (`04` section 1).
5. **Not all of it is accidental, and the largest deletion claim was false.** For 7 of 36 proposed removals a recorded failure would return. One candidate's end state of 25,000 to 40,000 lines did not follow from its own deletions and is withdrawn; the corrected estimate is about 147,000 (`challenge/steelman.md`; `04` section 8).

**Still open.** Nobody knows who holds Missions in flight, or who reads the on-disk status files, outside these repositories; see Open risks.

**What we need from the architect.**

- **Rule on three questions that gate most of the deletion** (D1, D2, D3): may the live Mission record leave the working tree; may the tool push it; is approved work integrated on approval. Together they decide whether about 96,000 lines in five packages are replaced as a set or only tidied.
- **Rule on whether the programmatic interface gets the same checks now** (D23). Today it lands a Mission "with no claim and no gate behind it (and no rollback)", in the code's own words.
- **Authorise the ten probes and the reading pass** (D17). About 79,000 lines of core had no assessor, and one pilot Mission decides whether the simplest landing design holds.
- **Decide whether the break belongs to 4.0.0, and what happens to Missions in flight** (D22, D8). The default is one break before general availability, with no import of unfinished Missions.

# Part A. How problematic the current architecture is

This part describes the **current implementation**. It proposes nothing.

## A.1 The answer

The consolidated judgement is: seriously, in a narrow and recoverable way (`02`). Five statements carry it.

1. **The needs are sound and small.** The problem is in the implementation, not in what the product promises.
2. **The implementation is about one and a half to two times what the needs require.** Summing the deletions the eight assessors name gives about 110,000 lines that serve no need a simpler mechanism would not meet. A further 78,000, the Python charter, are one of two complete implementations of the same thing. That is a floor of about a third of core.
3. **Every mechanism runs several generations of its own solution.** In no case was the older generation removed when the newer arrived.
4. **The incoherence produces defects, not only cost** (section A.4).
5. **It compounds.** Each fix adds a rule and names a new exception. Five decision records about landing carry 41 amendment headings; the record about the migration ledger gathered 8 amendments in six weeks.

Two limits apply to this answer. The honest range of excess is a third to a half of core, not nine tenths. And the shares are estimates read from each assessor's alternatives, not measurements.

## A.2 Where the code is

Counted lines are pointers for where to look. By the architect's ruling they are not evidence of excess.

| Package in core | Lines | Carries |
|---|---|---|
| Command layer (`src/specify_cli/cli`) | 107,407 | every capability's commands, and many rules |
| Charter (`src/charter`) | 77,725 | governance rules, roles, mission-type definitions |
| Landing (`consolidation`) | 36,414 | "only reviewed work lands" |
| Upgrade (`upgrade`) | 33,155 | 144 registered migrations |
| Status (`status`) | 21,397 | the record of work-package state |
| Step runtime (`src/runtime`) | 17,627 | "what next" |
| Agent-tool files (`tool_surface`, `skills`) | 17,229 | commands inside each agent tool |
| Lanes (`lanes`) | 16,574 | isolation of parallel work |
| Coordination (`coordination`) | 15,036 | where status is written |
| About 70 other packages | 182,372 | review, acceptance, migration, helpers and others |
| **Total** | **524,936** | |

The command layer is the largest package and no assessor was assigned to it. A light look by the consolidator found that about one line in six is command wiring. About half the package sits in modules that define no command at all. It is where rules without an owning module ended up, so its size is the sum of the other mechanisms' unowned rules (`01` section 4).

Outside core the same capabilities are carried again: an events package and two Java services in `spec-kitty-events`, and a Java charter service of about 137,000 main lines in `spec-kitty-charter`. The read service has no caller in core and the charter service has no client in core. Both are intended target, not in use (`01` section 5).

## A.3 Root causes

| # | Cause | Mechanisms it inflates |
|---|---|---|
| RC1 | Status and planning records are tracked files on branches that carry code | workspaces, lifecycle, events, landing |
| RC2 | Built-in mission types predate the extension points and were never moved onto them | mission types, charter, execution, the command layer |
| RC3 | Moves begun and not finished, with both sides live: events to a service, charter to a service, agent files to a reconciler | events, charter, execution, upgrade |
| RC4 | An approval is an event about a shared, moving branch, not a named commit of one unit | landing |
| RC5 | No single Mission value answers target, branches, identity and status location; each command derives them | the command layer |
| RC6 | No upgrade floor: old shapes stay valid inputs, so run-time code keeps fallbacks | upgrade, and through it three others |
| RC7 | No human identity: the actor is a string the caller asserts | execution, landing |

RC1 and RC4 answer the architect's question about lanes, worktrees, landing and topology management. They are not independently complex. Worktrees are independently necessary. The rest is interaction between abstractions (`02` section 4).

## A.4 Defects that exist today

- A research Mission is blocked at its gathering step. The check waits for events that only a retired engine wrote (`02`; `03` section 4).
- The governance text an agent receives depends on per-checkout state.
- The programmatic interface lands a Mission through a second executor with no claim, no gate and no rollback (`orchestrator_api/consolidation.py:586`).
- Both known clients of that interface have drifted. One calls a verb that core does not register.
- Eighteen tests marked as known failures pin holes in the landing checks.

<div style="page-break-before: always"></div>

# Part B. Which mechanisms add unnecessary complexity

Still the **current implementation**. The necessity of a capability and the necessity of its present implementation are kept apart: each row names the need first.

## B.1 The eight mechanisms

"Essential share" is the consolidator's rough reading of each assessor's alternatives. Packages overlap between rows, so the rows do not add up.

| Mechanism | The need | What exists | Essential share | Generations live |
|---|---|---|---|---|
| Workspaces: lanes, worktrees, topology, coordination | isolated working copies for parallel work | 44,500 lines; 4 topologies; about 120 refusal codes | a third to a half | 5, a sixth proposed |
| Mission types and step runtime | a kind of work as data; one loop that gates steps | 27,000 lines; 7 step lists | half to two thirds | 6 |
| Mission and work-package lifecycle | know where things stand; refuse illegal moves | about 64,000 lines around an 883-line state machine; 17 stores | about half | 3 |
| Event handling | a durable, ordered record | Python in core, a shared package, two Java services | about a third | 3 |
| Charter integration | the right rules to an agent at each step | 78,000 Python lines; about 137,000 Java | a fifth to a third | 3 for activation |
| Execution coordination | decide, hand out, record, ask | about 75,000 lines; 7 ways to drive work; 17 tools | two thirds to three quarters | 3 inside the loop |
| Landing and approval evidence | what lands is what was approved, by another | about 64,500 lines; 15 phases; about 60 refusal codes | a third of the whole | 3 |
| Upgrade and compatibility | bring an older project to the current shape | about 67,000 lines; 144 migrations | a third to a half | 5 |

A topology is the stored choice of how a Mission uses branches. A lane is a branch and working copy that several work packages may share. A refusal code is the name of a reason the tool gives for declining an operation.

## B.2 One shape repeats

A generic, declared mechanism exists. Beside it runs the older one it was meant to replace. The older one still decides on the common path; the generic one decides only for cases the older one does not know. So the main path never exercises the extension mechanism, and every rule has two homes (`03` conclusion). The architect's own example, mission types configurable through packs beside conditionals in the CLI, is one instance. Every assessor found the same in their own mechanism.

Four examples make it concrete.

- **Built-in types bypass their own extension point.** The exit checks of the four built-in mission types sit in a Python table keyed by the type names (`runtime/next/runtime_bridge_cores.py:859-864`). The declared file that would carry them ships in the same packs.
- **The guarantee depends on the door.** The command that lands a Mission runs a claim, a gate and a rollback. The programmatic verb for the same act runs none of them and re-adds selected checks as nine separate functions (`orchestrator_api/consolidation.py:586`).
- **A gate that gates nothing.** The start-up check for an outdated project compares against a minimum and a maximum that are both 3 (`migration/schema_version.py:22-23`). So 26 files outside the upgrade packages carry their own "not migrated" refusal.
- **Software vocabulary inside a generic mechanism.** Two work packages are put on one lane when their text shares a substring such as "api" or "template" (`lanes/compute.py:302`).

## B.3 The ten patterns

The duplication catalogue holds 74 cases in ten patterns, ranked by cost. The ranking is a judgement, not a measurement.

| Rank | Pattern | Cases | Removed by |
|---|---|---|---|
| 1 | Compensation for the interaction of the tool's own git surfaces | 9 | status off the code branches; one branch model |
| 2 | One rule implemented in parallel, across languages or repositories | 7 | finishing or cancelling each move |
| 3 | Built-in types and tools bypass the extension mechanism | 10 | built-ins declared as data |
| 4 | Entry points that enforce different rule sets | 7 | one operation behind every door |
| 5 | Several stores for one fact | 9 | one authority per fact |
| 6 | Unfinished extraction kept in parallel | 6 | completing each split |
| 7 | A domain rule restated at call sites | 7 | one Mission value; shared predicates |
| 8 | Transitional arrangements with no end | 6 | an upgrade floor |
| 9 | Indirection with nothing behind it | 7 | deletion |
| 10 | Vocabulary and parameter redundancy | 6 | one vocabulary |

The most dangerous pattern is the fourth, not the largest. It is small in lines, and it makes a guarantee depend on which entry point was used.

Landing shows the first pattern most clearly. Its assessor put four fifths of the package down to interaction: "It mostly proves properties its own neighbours destroy" (`02`, quoting the landing assessment).

| Complexity in landing | Caused by |
|---|---|
| Content comparison by file identity and patch identity | squash as the default, which destroys the commit identities that would prove equality |
| Attribution of commits and lines to work packages | several work packages sharing one lane |
| A bound on what an approval covers | approval is an event about a moving branch |
| Late checks on a second branch and its repair | status kept on a second branch |
| Snapshots, intents and resume recovery | fifteen phases moving up to three branches |
| Operator attestations | rules strict enough to refuse legitimate history |

## B.4 Several generations at once

"Legacy" marks a generation with no intended future. "Transitional" marks one that exists to move between two shapes.

| Subject | Generations live, oldest first | Oldest is |
|---|---|---|
| Workspace placement | status in the lane worktree; coordination worktree; partition by kind; single branch; size default; commit by ref (proposed) | legacy |
| Mission-type definition | `mission.yaml` with a class; an older state-machine residue; runtime graph; step contracts; pack descriptors; workflows (dormant) | legacy, still read |
| Status storage | a field in the work-package file; a log per Mission with a Python fold; a Java write service (built, not bound) | legacy, still written |
| Activation of rules | selection lists and legacy keys; activation ledger; charter service | transitional, no end |
| Plan for moving the charter | five plans | each still visible |
| Landing gate | reachability; content attribution; presence, cancellation and line checks | current |
| Agent-tool files | per-version migrations; an installer with a manifest; a declarative plan | legacy |
| "What has run" in an upgrade | version window; two-part ledger; adoption; reconcilers; operator backfills | legacy |
| User documentation | three descriptions of the product | legacy |

Seven arrangements were introduced as temporary and have no end in force. Among them: the status field mirrored into work-package files, a start-up gate awaiting "a later release", the 18 pinned known failures in landing, and the Python charter in core awaiting "the single switch" with no date (`02` section 3).

# Part C. Which capabilities are genuinely needed

## C.1 The promise

Needs were taken from the documentation and the prompts, not from how Spec Kitty's own repositories use the tool. Twelve journeys and 32 needs cover everything the README, tutorials, how-to guides and prompts promise. Sixteen are rated important, three optional and one speculative, beside the twelve rated core.

No documented need names lanes, a coordination branch, a topology, a partition or an approval stamp. The documentation promises outcomes. Worktrees are the one mechanism the README promises by name (`needs/needs-and-journeys.md`).

Each core capability is carried by more than one mechanism today.

| Core capability | Mechanisms that carry it today |
|---|---|
| Bring a repository under Spec Kitty | 3 |
| The workflow inside the user's agent tool | 5 |
| Intent to an agreed specification by interview | 4 |
| A plan and bounded work packages with dependencies | 4 |
| "What next", and resume in a new session | 6 |
| State of each unit recorded in the repository | 5 |
| Several agents on one Mission without overwriting | 6 |
| Review by someone other than the author | 6 |
| A human accepts the Mission | 4 |
| Only reviewed work lands; preview, resume, undo | 7 |
| Rules stated once, applied at every step | 6 |
| Progress visible to a person and a tool | 5 |

The four with the most mechanisms are the four the README sells: next action, isolation, landing, rules once.

## C.2 What is not accidental

A separate assessor argued the case for what exists. Of 36 proposed removals, the reason holds and the proposal loses it for 7; the reason holds and is kept by other means for 15; the reason no longer holds for 9; no reason was found for 5. The seven must not be carried into any simplification as "accidental".

| Id | Mechanism | The failure that returns |
|---|---|---|
| S1 | Ordering rules and the merge driver for the status log | two clones write one Mission; a stale approval is read after a rejection |
| S2 | Landing locally, without a forge | the solo journey ends at a local landing |
| S3 | Protection of lanes that mix work packages | a canceled sibling's commits land, unless one branch holds one unit of review |
| S4 | The check of where a lane's tests load code from | tests in a lane pass against another checkout's code |
| S5 | Native command files for twelve tools | a user's tool reads neither open format |
| S6 | Narrowing the rule set by allow list; skills absent by default | a version bump of a pack brings rules into force with no human act |
| S7 | The frozen step definition | an upgrade in the middle of a Mission changes its step list |

## C.3 Gaps in both directions

Three documented journeys have nothing placed to serve them at head: read-only progress for an outsider, tracker issues turned into work, and publishing a landed Mission. In the other direction, closing, reopening and archiving a Mission, and the choice of a topology, exist with no journey behind them. "A user is never asked to want a topology" (`needs/needs-and-journeys.md` section 4).

## C.4 Two needs the inputs disagree on

| Question | One reading | The other | What settles it |
|---|---|---|---|
| Do several clones write one Mission's state through git? | three assessors treat it as hypothetical | the steelman shows a recorded scenario with three issue numbers | a ruling on whether Mission state is shared through git or one store |
| Is landing without a forge a need? | the landing assessor found it undocumented | the solo-developer guide ends at a local landing | a ruling; the guide exists |

Low use of a mission type, a topology or a capability inside Spec Kitty's own repositories was not taken as evidence that it is unnecessary.

<div style="page-break-before: always"></div>

# Part D. What a simpler coherent architecture could look like

Everything in this part is the **intended target**: a proposal. Nothing in it is built, and choices marked conditional are not settled.

## D.1 The target on one page

| Concept | Carried by |
|---|---|
| Mission | a Mission branch that holds the Mission's planning folder |
| Work package, a unit of work and of review | a branch cut from the Mission branch; any checkout of it is the workspace |
| Mission record: who did what, when, on which commit | one append-only file per Mission on a git ref that no checkout holds |
| Mission type | pack data; a resolved copy committed with each Mission |
| Rules in force | a bundle compiled when rules change, and committed |
| Acceptance | one record event that names the accepted commit |
| Landing | one checked move of the target branch |

A git ref is a named pointer to a commit; a branch is one kind. Five design rules decide the forks: no mutable Mission state in any working tree; one owner per domain rule, reached by every entry point through the same operation; no native process on the per-command path; an event that names a commit is shared only together with that commit; core compares no identifier that comes from a pack with a literal.

The core and important needs reduce to eight essential capabilities, each with one carrier in the target.

| Essential capability | Target carrier | Replaces |
|---|---|---|
| Know where work stands; refuse illegal moves | the record, one state machine | 17 stores, 3 state machines |
| Isolated parallel work, ordered by dependency | a branch per work package | lanes, 4 topologies, coordination branch, placement layer |
| Independent review, human acceptance | events that name a commit | review-cycle files, stamps, windows |
| Only accepted work lands, recoverably | tree equality, one move | claim, gate checks, rollback authority |
| Kinds of work as data | one type format, a closed set of checks | 5 definition generations, per-type Python |
| Rules stated once, applied at every step | compiled bundle | Python charter, resolvers, context state |
| Reachable from agent tools and programs | generated commands, a smaller programmatic interface | 7 entry points, 10 tool tables |
| Set up, repaired, upgraded | reconcile | 144 migrations, 25 doctor subcommands |

## D.2 What the two candidates agreed on, and what stays conditional

One candidate was written to delete first, the other to consolidate in place. They reached the same four structural choices without seeing each other.

| # | Choice | Standing after the challenge |
|---|---|---|
| 1 | The Mission record is on a git ref that no checkout holds | **conditional** on D1 and D2 |
| 2 | One branch per work package | stands; a pilot measures the cost |
| 3 | Approved work is integrated into the Mission branch on approval | **conditional** on D3 |
| 4 | Landing is a tree-equality check and one checked move of the target | stands |

They also agreed independently on six states for a work package in place of nine, on activation as a pack list with exclusions, and on agent tools as data rows. The challenger called this agreement the strongest result of the exercise.

## D.3 What the challenge found

The challenge graded seven findings major. None overturns the four shared choices. Their status after consolidation:

| # | Finding | Status | Still the architect's |
|---|---|---|---|
| F1 | Integration on approval moves the join problem to the Mission branch | answered and checked by experiment: join by merge; approved commits stay ancestors; unreviewed commits are listed at acceptance | whether an agent's approval may move the Mission branch (D3) |
| F2 | Nobody pushes the record, so events stay on one machine in silence | design answer: a `sync` operation; unshared events always shown | whether the tool may push (D2) |
| F3 | The guards exist in the Java service only; the Python package has edge rules | named choice, cost corrected: guards move from core into the events Python package | library or Java service as writer (D4) |
| F4 | The command layer had no disposition; one end state did not follow | answered; the 25,000 to 40,000 figure withdrawn | none |
| F5 | Narrowing by allow list and the test-origin check were lost | answered: a pinned list per pack, opt-in kinds, the check kept | whether exclusion alone is enough (D7) |
| F6 | A transitional compiler had no end | answered: no new compiler; the Python charter ends before 4.0.0 | whether 4.0.0 waits for the charter system (D6) |
| F7 | Importing Missions in flight was underpriced | repriced, open: the default is no import | which option (D8) |

The F1 experiment used a bare remote and two clones. Each integrated a different work package and one push was refused. After a fetch and a merge, both approved commits were ancestors of the joined tip. For F2 the mechanics of appending, a refused push and a replay were run by hand. The re-check of replayed rows through the state machine is not built.

## D.4 The main forks, with their alternatives

| Fork | Recommended | Alternative | Decided by |
|---|---|---|---|
| Where the record lives | a ref no checkout holds (independent agreement) | a tracked file on the Mission branch | D1, D2 |
| Record granularity | one ref per repository, one file per Mission | one ref per Mission | a push-contention probe (D16) |
| Unit of isolation | a branch per work package (independent) | thin lanes | a pilot: the re-review rate |
| When work integrates | on approval (independent) | at acceptance | D3 |
| Landing strategy | a merge commit that names the accepted commit; squash optional | squash by default | D13 |
| Work-package states | six, "blocked" as a flag, an override as an event (independent) | nine | D5 |
| Record writer | a Python library in process | the Java service | D4 |

| Fork | Recommended | Alternative | Decided by |
|---|---|---|---|
| Charter delivery | a compiled, committed bundle | not committed: every clone needs the charter system | D19 |
| Activation | pack list, exclusions, a pinned list per pack, opt-in kinds | exclusions alone (independent; loses S6) | D7 |
| Agent tools | data rows, one ownership manifest (independent on rows) | two open formats only | D10, after a desk check |
| Programmatic contract | about 8 verbs, rendered from the same operations | machine output of every command as the contract | D11 |
| Who accepts | interactive unless a standing delegation is recorded | an asserted actor | D12 |
| Protection policy | no separate component; writing straight to the target given up | keep the component | D14 |

One alternative at the first fork removes finding F2 altogether: the record as a tracked file on the Mission branch. An ordinary push then carries it. Its price is that the Mission branch moves on every event, so acceptance needs a definition of bookkeeping paths. Both candidates rejected it and the consolidator agrees. The challenger noted that the candidates had not shown the price of their own choice at the same point; D2 is that price.

## D.5 Dispositions

No capability rated core or important is removed. The cut is in the mechanisms. The dispositions of the workspace, lifecycle, event and landing mechanisms hold as a set: none can be applied alone, because each compensates for another.

A disposition describes the present mechanism. "Remove" and "replace" mean it is legacy once its roadmap step is done. The table holds the rows that carry most of the change; all 59 mechanisms and the 32 capabilities are in the appendix.

| Mechanism | Disposition | Reason | Confidence | Waits on |
|---|---|---|---|---|
| Topology grid | remove | exists because status is a tracked file on code branches | medium-high | D1, D8 |
| Coordination branch and worktree | remove | a second copy for status writes | high | D1 |
| Partition and placement layer | remove | no artefact needs a surface decision once status is off the tree | medium-high | D1 |
| Execution lanes | replace | one branch per work package | medium | D3 |
| Status log as a tracked file | replace | the record on a ref unlocks the other deletions | medium | D1, D2, D16 |
| Ordering rules and merge driver | remove | order is append order; replay at `sync` is the one join rule | medium | D2 |
| Three state machines | consolidate | one, in the events system | medium | D4 |
| Per-type Python tables | replace | a closed set of declared checks | medium | none |
| Step engine with its own cursor | replace | "what next" computed from the type, the artefacts and the record | medium | none |
| Python charter in core | replace | core reads a compiled bundle; about 85,000 lines leave core, a move | medium | D6 |
| Claim, gate checks, attribution, approval bound | replace | approval names a commit; landing is tree equality | medium | D3, D8 |
| Rollback authority and resume recovery | remove | landing is one checked move | medium-high | none |
| Migration registry and ledger | remove | a floor, one converter, reconcilers | medium | D9 |
| Programmatic interface, 27 verbs | replace | a rendering of the same operations | medium | D11 |
| The command layer | simplify | modules parse, call one operation, render | medium-low | none |

Where the assessor, the steelman and the challenge disagree, the row is shown with all three views.

| Item | Assessor | Steelman | Challenge | Disposition chosen |
|---|---|---|---|---|
| Workflow inside the agent tool | two open formats only | holds; the proposal loses it | row schema unproven | retain through data rows; the desk check comes first |
| Parallel work without overwriting | keep lanes | S3, S11 | note | a branch per work package; lanes are the fallback |
| Only reviewed work lands | tree equality | S2, S9, S18 | major, argued | retain with a weaker, stated guarantee |
| Choosing which rules apply | exclusions only | S6 holds | major (F5) | keep narrowing by a pinned list |
| Learning loop from finished Missions | one candidate reduced it | none | the reduction's premise was false | retain |
| Test-origin check | delete | S4 holds | lost in silence by both candidates | retain |
| Lane work tips | simplify or give up | kept by other means | a safe branch delete refuses after squash | an ancestry rule; merge landing by default |
| Frozen step definition | a digest | S7 holds | one candidate does not freeze | a committed lock |

| Item | Assessor | Steelman | Challenge | Disposition chosen |
|---|---|---|---|---|
| State machine | consolidate | none | F3 | consolidate in the events Python package; D4 open |
| Ordering rules | delete, do not port | S1 holds | S1 answered for the record | remove; replay is the join rule |
| Java write service | recommended by its assessor | none | major for one candidate | off the per-command path for 4.0; D4 open |
| Activation model | exclusions only | S6 holds | F5 | simplify, keeping the pinned list |
| Agent-tool tables | two open formats | S5 holds | not already declarative | rows; schema to be proven |
| Landing checks | replace | S3 holds | major, argued | replace; per-line proof given up knowingly |
| Landing strategies | fast-forward or squash | the reason for squash is gone | a safe branch delete refuses after squash | merge by default |
| Import of Missions in flight | a flatten command | none | F7 | no import by default; D8 open |

## D.6 What the target is worse at

The consolidated design says so itself. It is worse at avoiding conflicts by construction, at cancelling after approval, at proof against a dishonest agent, at per-tool features, at one-command upgrade from old versions, and at showing a live record in the target tree.

The landing guarantee changes. Today the gate tries to prove, line by line, that what lands was approved. In the target it is "a human accepted the named tip, with the unreviewed commits listed". The challenge graded this loss major and argued. The present proof is itself incomplete, with 18 pinned known failures. Whether the weaker guarantee is acceptable is decision D18.

| Principle | Effect in the target |
|---|---|
| Human in Charge; governed coordination | stronger at acceptance: interactive, delegation recorded, unreviewed commits named; the same checks behind every entry point |
| Responsible delegation | changed: an agent's approval moves the Mission branch; nothing reaches the target without acceptance |
| Explicit responsibility ownership | per-line authorship proof given up; every verdict, acceptance, override and landing names an actor and a commit |
| Independent evolvability | three contracts: the record, the bundle, the programmatic interface; a change to a check needs an events release |

Size, corrected. Core would go from 524,936 lines to roughly 147,000. This is an estimate, inferred from counted packages and the shares kept.

| Part of core | Lines today | After (estimate) |
|---|---|---|
| Landing, lanes, coordination, placement, workspace, status | 99,161 | about 8,000 |
| Charter packages | 86,558 | about 2,000; it leaves core, a move |
| Step runtime and mission definitions | 25,339 | about 4,000 |
| Upgrade, migration, compatibility | 50,319 | about 3,000 |
| Agent tools, programmatic interface, dispatch | 30,850 | about 6,000 |
| Review, acceptance, git helpers, glossary | 46,568 | about 17,000; the weakest estimate |
| Command layer | 107,407 | about 28,000 |
| About 40 packages with no disposition in any input | about 79,000 | about 79,000 |

The charter line is a move to the charter system, not a deletion. The real deletion there depends on reducing the model on the Java side before the switch.

# Part E. What prevents moving towards it

## E.1 The obstruction map

The map lists 58 present arrangements that impede the target. Each names the roadmap step that removes it.

| Kind of obstruction | Rows | Typical removal |
|---|---|---|
| Shared state or implicit dependency | 13 | move the state; state the dependency in a contract |
| Compatibility mechanism | 12 | a ruling, then a floor or a converter |
| Duplicated rule | 8 | one owner; delete the copies |
| Competing authority | 7 | name the authority; demote the other |
| Unnecessary abstraction | 6 | delete with its cause |
| Hardcoded special case | 5 | declare as data |
| Distributed responsibility | 4 | one operation behind every entry point |
| Bypassed extension mechanism | 3 | put the built-in on the declared path |

Five readings matter.

1. **One obstruction blocks most of the others.** The status log is a tracked file on code branches. At least nine further rows exist because of it, and none can be deleted before the record is written elsewhere.
2. **Eleven obstructions can be removed fully with no ruling**, and six more in part.
3. **Twelve are compatibility mechanisms.** A ruling removes them, not an implementation.
4. **Three are not removed by this roadmap, only bounded**: no human identity, git's rule of one checkout per branch, and prompts that restate mechanism.
5. **The pins are obstructions too.** Architectural gates, parity fixtures and tests that patch private names make a deletion look like a regression. Each step must retire the gates of what it deletes.

## E.2 Breaking changes, as trade-offs

Existing user data and capabilities are not disposable. Each row names who is affected and what the migration costs. Consumers were relayed from the challenge and the steelman; they were not asked.

| Change | Who and what is affected | Migration and cost |
|---|---|---|
| The record moves to a ref; six states: the present status files are no longer written, two state names vanish, a new branch appears on the forge | every project; `fleet-kitty`; `spec-kitty-planning`; a hosted reader; the orchestrator; 12 pack prompts | landed Missions stay as text; one name map; one update per consumer |
| Lanes, topologies and the coordination branch go | Missions in flight; the orchestrator; two events contracts below 1.0 | decision D8 |
| Integration on approval; tree-equality landing: a late cancel is a revert; attestations and 22 flags go | operators; step prompts; two recovery guides | no data migration; documentation rewritten |
| Checks behind every entry point: transitions that pass today may refuse | `spec-kitty-orchestrator`, which today bypasses the command checks | one client update |
| The programmatic interface goes from 27 verbs to about 8 | `spec-kitty-orchestrator`; `spec-kitty-mcp` | aliases until 4.1.0 |

| Change | Who and what is affected | Migration and cost |
|---|---|---|
| Activation model: older selection files and legacy keys are ignored | every project with a charter; organisation packs | one converter; it keeps a project's narrowing |
| One mission-type format: custom definitions in older formats stop loading | projects with custom types; organisation packs; the pack composer | a converter in the charter system |
| Tools as rows; no user-wide installs: tool-specific features may go | users of 17 tools; a user's other projects on an older CLI lose shared commands | the reconciler removes what it owns; the other-project effect is announced, not solved |
| Upgrade floor at 3.2.x; the `migrate` commands go | users below 3.2; four pack prompts | two commands through a pinned older release |

## E.3 Missions in flight

This is the one change with no cheap answer. A Mission that is under way when the old shape is removed cannot continue on the new CLI.

| Option | What it is | Cost | Protection |
|---|---|---|---|
| No import (the default) | the Mission lands on the last release that has the present landing command; unfinished work continues as a new Mission | no code; per open Mission one extra landing, a pinned old CLI, a split identity | today's gate |
| Bounded import | import only Missions whose lanes each hold one work package, or only approved ones | readers of the old shape stay until 4.1.0: thousands of lines, an estimate | only a fresh acceptance |
| Full import | flatten everything | the landing problem, rebuilt | none |

The 859 landed Missions in core stay as files in history under every option. How many users hold Missions in flight across an upgrade is unknown and decides the matter.

# Part F. How to get there in steps

The roadmap is a proposal. No work item exists, nothing is scheduled and no effort is estimated. This part holds the **transitional arrangements**, each with its end, and the **legacy** to retire.

## F.1 What can start now, with no ruling

Each step below is undone by a revert and writes no user data.

| Step | What it does | What it deletes |
|---|---|---|
| T1 | retire copies and unread stores | the copied built-in mission definitions, byte-identical to the pack tree; an empty registry with its doctor and gates; one of two resolver modules; one type-name literal; a store with no reader |
| T2 | one Mission value; one predicate per rule | about 22 target-branch resolvers; 34 restatements of "approved or done"; run-time imports of migration code |
| T3 | the charter boundary carries the traffic | nothing yet; it creates the place where the later switch happens |
| T4 | built-in types on the declared path | the per-type Python tables, the fixed command list, and the research defect with them |

Ten probes also need no ruling. Each runs in a disposable clone or on paper. Two carry the most weight.

| Probe | What it does | Informs |
|---|---|---|
| P4 | one pilot Mission by hand on work-package branches; count second reviews after conflicts | D3 |
| P6 | replay the tree-equality check over landed Missions; compare with the recorded verdicts | D18 |
| P1 | several Missions push to one record ref from several clones | D16 |
| P2 | compare the Java checks with core's, rule by rule | D4 |
| P3 | check the tool row format against the 17 supported tools at the desk | D10 |
| P5 | read the command layer and the roughly 40 unassessed packages | every size |
| P7 to P9 | declared checks for two built-in types; fold existing logs by append order; prototype the replay | T4, T6, T8 |
| P10 | ask who holds Missions in flight and who reads the on-disk log | D1, D8 |

If the pilot shows frequent second reviews, thin lanes come back and about 20,000 lines of landing stay.

## F.2 The main line

| Step | What it does | Waits for | What it deletes |
|---|---|---|---|
| T5 | one operation behind every entry point | T2; D23 | the second landing executor; the second claim path |
| T6 | six states, one envelope, one log per Mission; still a file | D5 | the mirrored status field; a second decisions log; two placeholder states |
| T7 | checks and fold behind one append call in the events package | D4 | core's copies of the state machine and fold |
| T8 | the record on a ref, with `sync` | D1, D2, D16 | nothing yet; old Missions keep the file |
| T9 | work-package branches, acceptance, landing, the new interface | D3, D11 to D13 | nothing yet |
| T10 | "what next" without stored position; one type format | T4, T8; D27 | the run cursor and internal engine; four older definition generations |
| T11 | remove the old Mission shape as a set | T9, T10; D8, D14, D15 | topologies, coordination, placement, lanes, the landing subsystem, the ordering rules, and the gates that pin them |

Three points about the order.

- **T8 is the unlock.** Until the record is on a ref, no step can delete lanes, coordination, placement or the landing subsystem.
- **T11 is the only step that cannot be undone after release.** Before it, both Mission shapes run on the release-candidate line only. No general release ships both.
- **T5 comes early** because it removes the most dangerous pattern, and later steps move the checks from that one place.

Two side tracks share no code with the main line. T12 switches core to the compiled charter bundle and deletes the Python charter. T13 turns agent tools into data rows. T14, the baseline cut, comes last so that its converter is written once; it removes the migration registry and the legacy readers in 26 files. T15, in 4.1.0, removes the aliases. Eleven of the fifteen steps touch persistent data or a public contract.

## F.3 Transitional arrangements and their ends

A temporary mechanism does not become permanent by default. Each has a stated end.

| Arrangement | Introduced | End |
|---|---|---|
| Declared and Python checks evaluated together | T4 | one release candidate without a disagreement |
| Warnings in place of the new refusals on the interface | T5 | one release candidate |
| Name map for old state names | T6 | T11 |
| Local-file adapter behind the event port | T7 | T11 |
| Old and new Mission shape side by side | T8 | T11; no general release ships both |
| Present command names and verbs as aliases | T9 | 4.1.0 |
| Python charter behind its boundary | T3 | before 4.0.0; 4.1.0 if D6 says so |
| Last release with the present landing command | T11 | no code in core; the architect dates the end of support (D25) |
| Bounded import, only if D8 chooses it | T11 | 4.1.0 |
| Pinned 3.2.x stepping stone | T14 | no code in core |

"A mechanism still present after its end condition is a finding, not a default" (`07`).

## F.4 Legacy to retire

Retired without any arrangement: the copied missions tree, the status field mirrored into work-package files, an older events file, the committed status snapshot, the empty compatibility registry, the second resolver, workflows, the rebase landing strategy, two of the four topologies, legacy activation keys, and the programmatic interface's second landing executor (`04` section 11).

# Part G. Decisions, and what this means for Wayfinder

## G.1 The decisions, in order of what they unblock

All are the architect's. The order is a judgement of how many dispositions and steps wait on each. Every decision has a default, and no default removes a capability rated core or important.

| Rank | Id | Question | Default if no ruling |
|---|---|---|---|
| 1 | D1 | May the live Mission record leave the target tree, onto a ref? | yes |
| 2 | D2 | May the tool push the record and the commits its events name? | yes, automatic |
| 3 | D3 | Is approved work integrated on approval, or at acceptance? | on approval |
| 4 | D23 | Do the checks apply to every entry point at once, before the new interface? | yes; warnings for one release candidate |
| 5 | D17 | Are the reversible probes and the reading pass authorised? | yes, in disposable clones and at the desk |
| 6 | D15 | Are the landing, topology, coordination and migration-ledger records superseded as sets? | supersede |
| 7 | D22 | Does the breaking set land before 4.0.0 general availability? | yes |
| 8 | D8 | Missions in flight: land on the old CLI, or a bounded import? | no import |
| 9 | D25 | Until when is the last release with the present landing command supported? | until 4.1.0 |

| Rank | Id | Question | Default if no ruling |
|---|---|---|---|
| 10 | D9 | Upgrade floor and removal of the `migrate` commands | floor 3.2.x |
| 11 | D24 | Is a baseline cut of shipped migrations a permitted retirement? | yes |
| 12 | D4 | Record writer for 4.0: Python library in process, or the Java service? | library |
| 13 | D27 | Do custom mission types in the old formats stop loading? | yes, with a converter |
| 14 | D5 | Six states before the record contract reaches 1.0? | yes |
| 15 | D18 | Is "a human accepted the named tip, unreviewed commits listed" an acceptable landing guarantee? | yes |
| 16 | D6 | Does 4.0.0 wait for the charter system's compile? | wait |
| 17 | D11 | A programmatic interface of about 8 verbs, breaking both known clients once? | yes |
| 18 | D12 | Acceptance: interactive unless a standing delegation, or an asserted actor? | interactive |

| Rank | Id | Question | Default if no ruling |
|---|---|---|---|
| 19 | D7 | Is exclusion the only narrowing? | no: also a pinned list per pack and opt-in kinds |
| 20 | D19 | Must a clone work without the charter system installed? | yes: the bundle is committed |
| 21 | D13 | Default landing strategy | merge commit |
| 22 | D10 | Is the list of 17 tools a commitment; which tool features stay? | rows; features by desk check |
| 23 | D16 | One record ref per repository, or per Mission? | per repository |
| 24 | D20 | Are the constraints adopted, including those that need a register? | yes, with each roadmap step |
| 25 | D14 | Optional capabilities, and writing straight to the target | two kept, two reduced, the flag given up |
| 26 | D21 | Is event consumption by other systems a 4.0 need? | no; remove the seam once the ref is readable |
| 27 | D26 | What are the responsibility and significance scores for? | keep untouched until stated |

Five defaults challenge something recorded: D4 (a recorded rule against a Python writer), D13 (squash as the default), D15 (amendment as practice), D9 (upgrade from every version) and D24 (shipped migrations are never edited). The architect's ruling R1 permits the challenge; it does not decide it.

Some decisions depend on others. D2 and D16 have a subject only if D1 is yes. D3 presumes D1. D8 and D9 follow D22. D18 follows D3: under thin lanes an attribution rule returns.

## G.2 What this implies for Wayfinder

Wayfinder is a proposed capability for architectural knowledge and assurance. It stays prospective. By ruling, its requirements derive from the problems and decisions found here, and its purpose is to keep a design coherent while it changes, not to protect what exists.

The starting fact is that the present gates pass with all ten patterns present. Core has about 400 architectural test entries and a register of 62 state surfaces. They record what exists and check direction. They do not check necessity, ownership or ends (`08` section 1).

| Id | Derived requirement | The problem found here |
|---|---|---|
| W-1 | A capability map: each mechanism names the capability it serves | 59 mechanisms for 32 capabilities; about 79,000 lines with no assessor |
| W-2 | A generation and transition register: one target per subject; older ones transitional with an end, or legacy | three to six generations live; seven arrangements without end |
| W-3 | A rule-ownership register, across repositories for the few rules that cross | one rule in two languages; checks at three levels |
| W-4 | A store register that carries "one authority, one writer", not only the inventory | 62 surfaces were registered and still grew |
| W-5 | A reason on every guard and exception: the failure answered, the owner, the end | reasons were found only by a steelman pass |
| W-6 | Decisions in force per subject, superseded as sets | 41 amendment headings on five records |
| W-7 | Scenarios bound to principles, run through every entry point | the guarantee depends on the door |
| W-8 | A recurring necessity review by a human before each release | no check can decide whether a new mechanism repeats an old one |

A structural check finds a restated literal, a second writer or a missing register row. Whether a new mechanism repeats the intent of an old one is a human judgement. That is the main requirement on such a capability.

Against the earlier reconnaissance proposal, this exercise confirms a decision index and an exception register with identity and owner. It narrows the component register to "capability, mechanism, owner". It contradicts two earlier readings for this class of problem. The missing knowledge is why a mechanism exists, what it compensates and when it ends, and no record holds that. And the enforced structural model is not sufficient as the intent of record. Registers belong inside the owning repository first; a cross-repository index is needed for W-3 and W-6 only. Wayfinder is subject to its own constraints: a register that needs a doctor is itself a compensating mechanism.

Deliverable `08` states 27 constraints, 23 acceptance scenarios and 4 erosion scenarios that would keep the target from eroding. Whether to adopt them is decision D20.

# Part H. How far to trust this

## H.1 What was checked, and with what result

- **A seeded sample of source references.** The challenger drew 20 of the 437 evidence rows of the eight mechanism assessments and the duplication catalogue with a fixed random seed. 19 were true, 1 partly true, none false. The partly true one was a count that could not be reproduced as written; the pattern behind it holds.
- **The candidates' load-bearing claims.** Ten per candidate were checked in the code: 13 true, 5 partly true, 2 false. The two false claims were the end state of 25,000 to 40,000 lines, and the claim that a safe branch delete refuses only unmerged work.
- **Re-reads by the consolidators.** One re-read six references its ranking rests on most; another re-read 17. Where a count differed from an input, both are shown in the deliverable.
- **Experiments.** Four were run in scratch repositories: the two-clone join, the mechanics of the record ref, a merge landing followed by a safe branch delete, and a squash landing proven absorbed.

## H.2 What was read and never run

No test suite and no build was run. No check, gate or converter proposed here was built. The replay of record rows through the state machine was not built. No agent tool was tested against a data row. The Java repositories and the charter repository were not opened by the consolidators; statements about them are relayed from the assessors, and the challenger read the Java checks by file names and two class headers. The steelman read the context sections of nine decision records and module documentation, not the issues, and ran no reproduction.

## H.3 What is an estimate

- The essential share of each mechanism, and "a third to a half of core".
- Every target size, including the total of about 147,000 lines.
- The cost of a bounded import ("thousands of lines").
- The ranking of patterns and the ranking of decisions, which are judgements.

No effort was estimated for any step.

## H.4 What was not assessed

- About 79,000 lines in about 40 packages of core have no disposition in any input.
- The command layer got a light look by signature and file name, not a reading of each module.
- Tracker integration was not assessed and is left untouched.
- Consumers outside these repositories were named from references in code and documents. None was asked.

## H.5 How to read the numbers

The evidence is representative, not exhaustive. That was the architect's ruling: evidence in proportion to risk, cost and reversibility. Counts from the code are pointers for where to look. They are not evidence of unnecessary complexity. Low use inside Spec Kitty's own repositories, which is heavily skewed to one mission type, is not evidence that something is unnecessary.

Each role was one agent with one lens and one pass. The needs analysis says nine capabilities are core in its text and marks twelve in its table; this report uses the table, as deliverable `01` does. Several agent profiles ask their holder to decide or approve. In every case that verb yielded to the mandate: the agents assessed, and the architect decides.

# Open risks

No issue was filed for any row. Whether any is already tracked was not checked.

| Risk | Why it matters | Issue | Owner |
|---|---|---|---|
| A user who starts a research Mission cannot pass its gathering step | a built-in kind of work does not complete today | none filed | architect decides |
| A program can land a Mission without the checks a person's command applies | the guarantee depends on the entry point used | none filed | architect (D23) |
| A user with a Mission in flight at the upgrade has no supported way to finish it after the old release's support ends | the upgrade capability promises that work in flight is not lost | not applicable | architect (D8, D25) |
| Progress events stay on one machine in silence if nobody pushes the record | another clone lands or accepts on stale state | not applicable | architect (D2) |
| The simpler landing lets through content the present checks would refuse | "only reviewed work lands" becomes "a human accepted the tip"; the replay over landed Missions was not run | not applicable | architect (D18) |
| The 4.0.0 date depends on a release of another repository | the charter switch waits for the charter system | not applicable | architect (D6) |
| The roadmap's sizes are wrong | about 79,000 lines of core had no assessor, so no disposition | not applicable | architect (D17) |
| A tool's users lose their native commands | the row format is unproven against 17 tools | not applicable | architect (D10) |
| A deletion is refused or reads as a regression | existing gates and fixtures pin the present shape | not applicable | each roadmap step |
| A choice is carried forward as settled | two of the four shared choices are conditional on D1 to D3 | not applicable | architect |

# Appendix: method, sources and caveats

## Method

A read-only assessment and design exercise, commissioned by the architect on 2026-11-28, after the Wayfinder reconnaissance of the same day and reusing its findings. Code references are to core at head on that day unless a repository is named. No production implementation or remediation is authorised, and no history of who caused the present state was written.

Stages, each writing to its own folder: a needs analysis from the documentation; eight mechanism assessments; a cross-cutting hunt for duplication; two design candidates from opposite stances (delete first; consolidate in place); a steelman of what exists and a challenge of both candidates; consolidation into nine deliverables; this report. The experimental apparatus of the reconnaissance (pre-registration, blind replication, planted violations, seeded reproduction of findings) was not repeated, by ruling.

Three departures from the debrief procedure, with the architect's authority:

1. **Source of facts.** This debrief reports no GitHub activity, so the collector was not run. Every number and statement traces to a file in the assessment folder instead. Issue and pull-request references are omitted.
2. **Vehicle.** The work ran as a Mission of the `plan` type with profile-loaded subagents, not as a dispatch Op.
3. **Placement.** The architect ruled that the documents are stored in the assessment folder on a research branch. The Markdown source of this report is in `report/`. The PDF is written outside the repository and handed over.

The PDF was rendered with the branded generator and each page was inspected. A designer review pass was not run.

## Where each deliverable lives

All paths are under `docs/reports/architecture-recovery-assessment/2026-11-28/`.

| # | Deliverable | File |
|---|---|---|
| 0 | Mandate and rulings R1 to R20 | `00-mandate-and-rulings.md` |
| 1 | Current capability and responsibility map | `01-capability-and-responsibility-map.md`, `.csv` |
| 2 | Essential versus accidental complexity | `02-essential-vs-accidental-complexity.md` |
| 3 | Duplication and competing mechanisms | `03-duplication-and-competing-mechanisms.md`, `.csv` |
| 4 | Candidate simplified architecture | `04-candidate-architecture.md` |
| 5 | Obstruction map | `05-obstruction-map.md`, `.csv` |
| 6 | Capability dispositions | `06-capability-dispositions.md`, `.csv` |
| 7 | Incremental remediation roadmap | `07-remediation-roadmap.md` |
| 8 | Constraints and acceptance scenarios | `08-constraints-and-acceptance-scenarios.md` |
| 9 | Outstanding decisions | `09-open-decisions.md` |

Working material: `needs/` (journeys and capabilities), `mechanisms/` (M1 to M8 with evidence tables), `duplication/`, `candidates/` (CA and CB), `challenge/` (challenge, steelman, forks, reference checks), `dispatch/` (the briefs).

## All mechanism dispositions

From `06-capability-dispositions.md` section 4; the full rows, with evidence, risks and what is deleted, are in the `.csv`. Each table is one group of mechanisms, named in its second column heading. Confidence: H high, MH medium-high, M medium, ML medium-low, L low.

| Id | Workspaces for parallel work | Disposition | Reason | Conf. | Waits on |
|---|---|---|---|---|---|
| M1.1 | Topology grid | remove | nothing left to decide once status is off the code branches | MH | D1, D8 |
| M1.2 | Coordination branch and worktree | remove | a second copy for status writes | H | D1 |
| M1.3 | Partition and placement layer | remove | no artefact needs a surface decision | MH | D1 |
| M1.4 | Execution lanes and lane computation | replace | one branch per work package | M | D3 |
| M1.5 | Lane dependency integration, auto-rebase | remove | a dependent is cut from the Mission tip | M | D3 |
| M1.6 | Status exclusion, write guard, planning pin | remove | compensate for status in the lane's tree | MH | D1 |
| M1.7 | Worktree allocation and cleanup | simplify | kept small; cleanup by an ancestry rule | M | |
| M1.8 | Lane work tips and recorder hooks | replace | one rule: never delete a branch with unabsorbed commits | M | D13 |
| M1.9 | Test-origin check | retain | tests in one checkout can load code from another | MH | |
| M1.10 | Owned checkout as a mode | consolidate | becomes the general case | M | |
| M1.11 | Protection policy; writing straight to the target | remove | only landing writes the target | ML | D14 |

| Id | Mission types and the step runtime | Disposition | Reason | Conf. | Waits on |
|---|---|---|---|---|---|
| M2.1 | Five generations of type definition | consolidate | one format; built-ins authored in it | MH | |
| M2.2 | Per-type Python tables | replace | a closed, versioned set of checks | M | |
| M2.3 | Step engine with run cursor | replace | "what next" computed from lock, artefacts, record | M | |
| M2.4 | Frozen template per run | replace | a lock committed per Mission | M | |
| M2.5 | Reserved built-in keys | replace | replacing a built-in is an explicit act | M | |
| M2.6 | Responsibility and significance scoring | investigate | no reason found | L | D26 |
| M2.7 | Fixed command list | replace | one generated command per declared step | H | |

| Id | Mission and work-package lifecycle | Disposition | Reason | Conf. | Waits on |
|---|---|---|---|---|---|
| M3.1 | Nine states, two placeholders, force flag | simplify | six states, a flag, an override event | MH | D5 |
| M3.2 | Three state machines | consolidate | one, in the events system | M | D4 |
| M3.3 | Seventeen status stores | consolidate | one record per Mission | MH | D1 |
| M3.4 | Two write paths, five-source read | remove | exist because the log's place depends on topology | MH | D1 |
| M3.5 | Work-package manifest sources | consolidate | one manifest | M | |

| Id | Event handling | Disposition | Reason | Conf. | Waits on |
|---|---|---|---|---|---|
| M4.1 | Status log as a tracked file | replace | the record on a ref | M | D1, D2, D16 |
| M4.2 | Ordering rules and merge driver | remove | append order; replay at `sync` | M | D2 |
| M4.3 | Produce seam | remove | no registrant in core; after the ref is readable | M | D21 |
| M4.4 | Java write service on the CLI path | investigate | the alternative writer; has three of four checks | ML | D4 |
| M4.5 | Java read service | retain | unchanged; not launched by the CLI | L | |
| M4.6 | Hosted vocabulary and an unread events file | remove | no reader in core | MH | |

| Id | Charter and packs | Disposition | Reason | Conf. | Waits on |
|---|---|---|---|---|---|
| M5.1 | Python charter in core | replace | core reads a compiled, committed bundle | M | D6 |
| M5.2 | Activation model | simplify | pack list, exclusions, pinned list, opt-in kinds | M | D7 |
| M5.3 | Six-tier template chain, two resolvers | consolidate | one precedence order | M | |
| M5.4 | Context state | remove | delivery must not depend on the checkout | MH | |
| M5.5 | Per-worktree daemon, run-time graph | remove | rules change at pin or activation changes | M | D6 |
| M5.6 | Pack skills default | retain | a pack must not add commands to every tool | M | D7 |
| M5.7 | Glossary pipeline | simplify | pack content and an authoring lint | L | D14 |

| Id | Execution coordination and agent tools | Disposition | Reason | Conf. | Waits on |
|---|---|---|---|---|---|
| M6.1 | Seven entry points to drive work | consolidate | four operations; every entry point renders them | MH | |
| M6.2 | Programmatic interface package | replace | a rendering of the same operations | M | D11 |
| M6.3 | Per-tool tables and renderers | simplify | tools as data rows | ML | D10 |
| M6.4 | User-wide installs, session hooks, plugin bundles | investigate | decided per feature after the desk check | L | D10 |
| M6.5 | Dispatch keyword router; Op files | remove | an Op is events in the record | M | |

| Id | Landing and approval evidence | Disposition | Reason | Conf. | Waits on |
|---|---|---|---|---|---|
| M7.1 | Claim, gate checks, attribution, approval bound | replace | approval names a commit; tree equality | M | D3, D8 |
| M7.2 | Operator attestations | replace | one override event | M | |
| M7.3 | Rollback authority, resume recovery | remove | one checked move; undo is a move back | MH | |
| M7.4 | Origin-freshness gate | retain | small and needed; extended to the record | H | D2 |
| M7.5 | Merge-attribute guard | remove | given up: listed at acceptance, not refused | L | |
| M7.6 | Landing strategies | simplify | merge default; squash optional; rebase removed | M | D13 |
| M7.7 | Owned-file evidence, review independence | consolidate | one check in the events system | M | D4 |
| M7.8 | Pre-review test gate | retain | a separate concern | M | |
| M7.9 | Retention and cleanup | simplify | ancestry rule; one flag | M | |

| Id | Upgrade, compatibility and cross-cutting | Disposition | Reason | Conf. | Waits on |
|---|---|---|---|---|---|
| M8.1 | Migration registry, ledger, order manifest | remove | floor, one converter, reconcilers | M | D9 |
| M8.2 | `migrate` command family | remove | part of the one converter | M | D9 |
| M8.3 | Run-time legacy readers | remove | one shape authority | MH | D9 |
| M8.4 | Empty compatibility registry | remove | no reason found; available now | H | |
| M8.5 | Doctor family | simplify | one doctor over the stores that remain | M | |
| M8.6 | Import of Missions in flight | investigate | default: none | ML | D8 |
| X.1 | The command layer | simplify | parse, call one operation, render | ML | |
| X.2 | Mission identity and handle resolution | consolidate | one Mission value | MH | |
| X.3 | About 79,000 unassessed lines | investigate | no input gives a disposition | L | D17 |

The "Waits on" entries for M2.6, M4.3 and X.3 name decisions that `09` added after `06` was written.

## Capability dispositions

Of 32 capabilities, 28 are retained. The four others, and the retained ones whose guarantee or carrier changes most:

| Id | Capability | Disposition | What changes | Conf. | Waits on |
|---|---|---|---|---|---|
| C20 | Consistent terms | simplify | glossary as pack content and a lint | L | D14 |
| C27 | Upgrade without losing work in flight | simplify | reconcile plus a floor | M | D8, D9 |
| C31 | Close, reopen, follow up, archive | simplify | no journey found; reopen is a new Mission | L | D14 |
| C28 | Start from and report to an issue tracker | investigate | not assessed; left untouched | L | D14 |
| C10 | A human accepts the Mission | retain | strengthened: interactive, names the tip, lists unreviewed commits | M | D12 |
| C11 | Only reviewed work lands | retain | the guarantee becomes "a human accepted the tip, unreviewed commits named" | M | D3, D13 |
| C12 | Target chosen deliberately | retain | only landing writes the target | M | D14 |
| C17 | Choose which rules apply | retain | reduced; the cascade goes | M | D7 |
| C32 | Share Mission state through git | retain | record and branches travel by `sync`; unshared events counted | M | D2, D3 |

## Definitions

- **Disposition.** One of retain, simplify, consolidate, replace, remove, investigate further. It describes the present mechanism, never the capability behind it.
- **The four labels.** Intended target: the proposed design of `04`. Current implementation: what exists at head. Transitional: an arrangement that exists to move between the two, with a stated end. Legacy: an arrangement with no intended future.
- **Generation.** One of several successive solutions to the same problem that are all still live in the code.
- **Independent agreement.** The same choice reached by the two candidates from opposite stances, before either saw the other.
- **Steelman verdicts.** "Holds; the proposal loses it" means a recorded failure would return. "Kept by other means" means the reason survives through a simpler mechanism, often on a condition.
- **Evidence tags in the deliverables.** Read, executed, relayed (checked by an input, not re-opened), inferred. This report keeps the distinction in Part H.
- **Corrected figures.** Where a later stage corrected a number, this report quotes the later one: the end size of core (about 147,000, not 25,000 to 40,000); migrations (144 registered, not 155 modules); the count of comparisons of a step id against a literal, which is quoted nowhere because it did not reproduce.

## Traceability

The full table is `report/traceability.csv`: one row per statement, with its kind and source files. The summary's figures were re-checked against their sources after rendering.

| Statement | Kind | Source |
|---|---|---|
| The six questions and rulings R1 to R20 | method | `00-mandate-and-rulings.md` |
| Capability and line counts | current | `01`; `needs/capabilities.csv` |
| Severity, shares, generations, root causes | current | `02` |
| Patterns and examples | current | `03` |
| Target, forks, findings F1 to F7, corrected size | target | `04`; `challenge/candidate-challenge.md`; `challenge/forks.csv` |
| Obstructions | current | `05` |
| Dispositions and three-view disagreements | disposition | `06`, `.csv` |
| Steps, probes, transitional ends | transitional | `07` |
| Legacy list | legacy | `04` section 11 |
| Constraints, scenarios, Wayfinder requirements | target | `08` |
| Decisions D1 to D27, defaults, order | decision | `09` |
| Reference checks and limits | method | `challenge/candidate-challenge.md` sections 4, 9, 10; `challenge/reference-checks.csv` |

## Caveats

- One agent and one pass per role. Estimates, rankings and confidence grades are single judgements.
- Counts quoted from different inputs sometimes differ by a few units because the search pattern differed. The deliverables show both figures where that happened; this report quotes one and names its source.
- Line counts are of Python files and overlap between capabilities. They are not additive except in the two tables that say so.
- The defaults in Part G are assumptions made so that the roadmap could be written. A default is not a recommendation that the ruling be skipped.
- The outside observer has received the findings of the earlier reconnaissance. The prediction control of that study is abandoned, by ruling; nothing here depends on it.
