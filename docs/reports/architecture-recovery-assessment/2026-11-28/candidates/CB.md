---
doc_status: draft
updated: '2026-11-28'
---

# Candidate CB: consolidate in place

Architect CB, profile architect-alphonso. The profile's verb "decide" yields to the envelope: this file recommends, the human architect decides.

Evidence note. Sizes and spreads are taken from the mechanism reports (cited as M1 to M8, X1 for the duplication catalogue) and tagged [inferred] where I did not re-run them. Facts I rely on for a design choice were checked at head and tagged [read].

## Conclusion

The coherent architecture is reachable from here, and most of the way is deletion. Two moves already under way carry it, if each is finished on a narrower target than the one being built:

1. **The ledger leaves the working tree.** One Mission ledger per Mission, on a git ref that no checkout holds, written by commit with compare-and-swap by the events system. This is the recorded direction (`spec-kitty-events:docs/adr/0007-write-service-commits-coordination-status-by-ref.md` D-1 [read]) with one change: the ref carries only the ledger, never code.
2. **The charter leaves core.** The charter system compiles packs and activation into plain files at change time. Core reads files.

With status out of the tree, topology, the coordination branch, the PRIMARY/COORD partition and the placement seam have nothing left to decide. With one branch per work package and approval naming a commit, landing is a tree comparison. I replace three subsystems (coordination, execution lanes, consolidation) because repair is worse, and consolidate the rest.

Rough effect on core [inferred from M1 to M8]: about 110,000 lines deleted and about 78,000 more leaving with the Python charter, of 525,000.

## 1. The architecture in one page

**What a user holds in their head**

| Concept | Meaning |
|---|---|
| Mission | Agreed intent, carried from specification to a landed result. Has a type, a target branch and a Mission branch. |
| Mission type | Pack data: ordered steps, each with a prompt, a role, artefacts and completion checks. |
| Work package | A bounded unit of work with dependencies. It is implemented on its own work branch. |
| Review verdict | Approve or reject **of one commit**, by someone other than the author. Approval integrates that commit into the Mission branch. |
| Acceptance | The Human in Charge accepts the Mission branch tip, one commit. |
| Landing | The accepted tree reaches the target branch, or nothing moves. |
| Charter | The rules in force, compiled per mission type and action. |
| Ledger | The append-only record of who did what, when, on which commit. |

**What a contributor holds in addition:** three operations (`decide`, `act`, `record`) behind every entry point; one Mission value object; the ledger is the only mutable Mission state.

```
Interfaces        CLI | generated agent commands | orchestrator API      (views, no rules)
Operations        decide (next) | act (claim, verdict, accept, land) | read
Core (Python)     Mission model | step runtime | workspaces | review and landing
                  governance reader | tool-surface reconciler | upgrade
Events system     ledger: envelope, state machine, guards, fold, store on a ref, streams
Charter system    packs, activation, layering, compile to files, pack validation
Open packs        content: rules, profiles, mission types, tool profiles
Git               Mission branch, work branches, ledger ref, target
```

## 2. Capabilities kept, changed and dropped

"Carrier" is the mechanism that carries the capability in the target.

| Id | Disposition | Carrier in the target | Reason |
|---|---|---|---|
| C01 | kept | `init`, one `doctor` | core |
| C02 | kept, reduced | tool-surface reconciler; tool profiles as data; commands generated per active mission type | five mechanisms today (M6 §5.7) |
| C03 | kept | specify step; decisions as ledger events | core |
| C04 | kept | `wps.yaml` as the one work-package manifest | three dependency sources today |
| C05 | kept | `decide`: a function of frozen type, artefacts, ledger | six claimants today |
| C06 | kept | Mission ledger on a ref | one authority |
| C07 | kept, changed | work branch per work package, optional worktree | isolation without topology |
| C08 | kept, simpler | a dependent starts from the Mission branch, which holds approved predecessors | no dependency merge |
| C09 | kept | verdict event naming a commit; independence guard in the state machine | one owner |
| C10 | kept, strengthened | acceptance event naming the Mission tip | a nudge today (M7 §2) |
| C11 | kept, changed | landing by tree equality; one ref moves | replaces claim, gate, rollback |
| C12 | kept | Mission branch always; typed protection refusals | already the default (M1 G4) |
| C13 | kept, simpler | every operation re-runnable; no run state files | by construction |
| C14 | kept | mission types as pack data only | no type names in code |
| C15 | kept, made true | built-ins use the same format; a project may override one | extension point on the main path |
| C16 | kept | compiled charter files | six claimants today |
| C17 | kept, reduced | activation = ordered pack list + exclusions | M5 B |
| C18 | kept | org pack with a required floor, enforced at compile | |
| C19 | kept | profiles as pack content, appended at delivery | |
| C20 | kept, reduced | glossary as pack content and an authoring lint | optional need |
| C21 | kept, reduced | `dispatch` = context + one ledger record | router dropped |
| C22 | kept, changed | orchestrator API 2.0, a pure view | half a second implementation today |
| C23 | kept | external orchestrator; stops at decisions and acceptance | |
| C24 | kept | `read` operation; events system streams | one door |
| C25 | kept, reduced | consumers read the ledger | no consumer at head |
| C26 | kept | retrospective events; a human applies proposals through charter verbs | |
| C27 | kept, reduced | floor 3.2.x; one converter; reconcilers | M8 A |
| C28 | kept as is | tracker package | optional; not changed here |
| C29 | kept, reduced | `doctor` over stores that still exist | |
| C30 | kept | `mission_id`; Mission value object | |
| C31 | reduced | close and archive as ledger events; reopen is a new Mission citing the old | no journey found |
| C32 | kept | ledger ref and branches travel by push and fetch | |

Nothing documented is dropped outright. The reductions that a user can notice are in section 12.

## 3. Components and ownership

| Component | Owns (one responsibility) | Knows nothing about | Public interface | State; other readers and writers |
|---|---|---|---|---|
| **Mission model** (core) | Identity, type, target branch, Mission branch, work-package manifest; handle resolution | git plumbing detail, rules, tools | `Mission.load(handle)` value object | `kitty-specs/<m>/meta.json`, `wps.yaml`, `type.lock.yaml` on the Mission branch; read by all, written only by create and tasks-finalize |
| **Events system** (`spec-kitty-events`) | The ledger: envelope, state vocabulary, legal moves, guards over ledger facts, fold, ordering, storage, streams | git branches of code, worktrees, prompts, mission types | commands `append`; queries `state`, `history`, `stream` | the ledger refs; nobody else writes them |
| **Step runtime** (core) | "What is legal next, for whom" | how state is stored, which tool asks | `decide(mission, actor)` | none |
| **Workspaces** (core) | Work branch naming, creating and finding a checkout, safe removal | status, review rules, landing | `open(wp)`, `locate(wp)`, `close(wp)` | git worktree registry only |
| **Review and landing** (core) | Git evidence for a verdict; integration on approval; the landing check | the state machine, charter | `integrate(wp, sha)`, `land(mission)` | none; reads the ledger, moves the Mission branch and the target |
| **Protection policy** (core) | Which branches refuse direct writes, with the refusal text | Missions | `check(ref, intent)` | project config |
| **Charter system** (`spec-kitty-charter`) | Packs, activation, precedence, required floor, compile | Missions in flight, git, ledger | `compile`, `activate`, `validate` commands | `.kittify/charter/activation.yaml` (source), `.kittify/charter/compiled/` (derived) |
| **Governance reader** (core) | Hand the compiled context for (type, action, profile) to a prompt, with a staleness check | packs, DRG, kinds | `context(type, action, profile)` | none |
| **Tool surface** (core) | Reconcile generated files in each configured tool to the desired state | Missions, lifecycle | `reconcile(project)` | one ownership manifest |
| **Interfaces** (core) | Render operations for a person, an agent or a program | every rule | CLI, generated commands, orchestrator API | none |
| **Upgrade** (core) | Shape version gate; one converter per major; run reconcilers | subsystem internals | `upgrade` | `schema_version` |

Where each rule that is duplicated today would live:

| Rule | Places today | One owner |
|---|---|---|
| Lane vocabulary, legal edges | 5 (M4 §5.2) | events system; core imports nothing but names in rendered output |
| Fold and ordering | 4 in 2 languages | events system, once; append order is the order |
| Reviewer differs from author | 5 (M3 §6) | events system guard on the verdict event |
| "Accepted set" predicate | 34 restatements (X1 2.3) | a query of the events system |
| Dependency readiness | 5 | events system guard on the start event; manifest from the Mission model |
| Target, Mission and write branch | about 22 resolvers (X1 2.1) | Mission model |
| Mission handle resolution | 97 functions (X1 2.4) | Mission model |
| Step order, exit conditions, role, capabilities of a type | 7 surfaces (M2 §5.1) | the mission-type definition in the pack |
| Layered resolution of pack content and templates | 4 chains | charter system |
| What is in force | 5 sources (M5 §5.2) | activation file, resolved by the charter system |
| Protected-branch refusal and wording | 4 renderers (X1 2.2) | protection policy |
| Tool list and paths | about 10 tables (X1 1.8) | tool profiles (data) |
| Landing | 2 executors (X1 3.1) | `land`, rendered twice |

## 4. The mechanisms in scope

### 4.1 Workspaces and parallel work

**Design.** Every Mission has one Mission branch, cut from the target. Every work package is implemented on a work branch cut from the Mission branch tip at start. A checkout for it is a linked worktree made by the tool, or the checkout the caller is already in if it is clean (the present owned-checkout case, `src/mission_runtime/owned_checkout.py` [read], made the general rule). A solo user works in the repository root checkout; the tool switches it to the work branch and back.

No lane computation. `owned_files` in `wps.yaml` (`src/specify_cli/core/wps_manifest.py:53` [read]) stays as planning data: tasks-finalize warns when two work packages without a dependency between them overlap. Conflicts that still occur surface at integration, as in plain git.

**Deletes** [inferred, M1 §8]: topology and settlement; `coordination/` (about 15,000 lines); the placement seam (`mission_runtime/`, about 6,000); read-path resolution (about 3,000); about 14,000 of 16,500 lines in `lanes/` (lane computation, `lanes.json`, dependency merges, auto-rebase, incorporate, sparse exclusion); about 120 refusal codes.

**Kept from today:** worktree allocation and the rule that a branch with commits not contained in the Mission branch is never deleted by the tool. That rule replaces the lane-tip hooks: `git branch -d` semantics plus a refusal.

**No longer does:** choose a topology; hold status in a checkout; keep approved work unintegrated until acceptance.

### 4.2 Mission-type definition and the step runtime

**Design.** One format: a type descriptor plus one folder per step (M2 A). A step declares order, dependencies, role, governance references, produced artefacts, and completion checks from a closed vocabulary: file present, glob non-empty, table has at least N rows, all work packages at or beyond a state, human decision recorded. One step kind iterates over work packages; it is declared, not inferred from the id `implement`. Built-in types ship only this.

At `mission create` the resolved definition is written to `kitty-specs/<m>/type.lock.yaml` and committed. `decide` reads the lock, the artefacts on the Mission branch and the ledger. It returns step, decision required, blocked or done. Steps with no artefact record a `StepCompleted` event. There is no run cursor.

**Deletes** [inferred, M2 §8, M6 §8]: `mission.yaml` and the `Mission` class; `mission-runtime.yaml`; workflows; `_GUARD_TABLES` (`src/runtime/next/runtime_bridge_cores.py:859` [read]) and the other per-type tables; the internalised engine and its reconcile phases; `mission-events.jsonl`; the copied tree under `src/specify_cli/missions/`. About 12,000 to 15,000 of the 27,000 lines M2 counts.

**No longer does:** RACI and significance scoring. "A human decides this step" is the "human decision recorded" check.

### 4.3 Mission and work-package lifecycle

**Design.** One record per Mission: the ledger. Work-package states: `planned`, `in_progress`, `for_review`, `in_review`, `approved`, `canceled`; `blocked` is a flag with a reason. A claim is the actor on the start event. "Landed" is a Mission fact, not a work-package state. An override is its own event type with actor and reason; an overridden approval is a different fact from a reviewed one, so no later mechanism re-reads history to tell them apart.

Mission-level facts in the same ledger: created, step completed, decision asked and answered, accepted (naming a commit), landed (naming the target commit), closed.

Guards that need only ledger facts live in the events system. Guards that need git facts are satisfied by evidence the caller supplies as event fields (the reviewed commit, the integrated commit); core's review component computes them. Every door reaches the same guards because there is one `act` operation.

**Deletes** [inferred, M3 §8]: the frontmatter mirror; committed `status.json`; sentinel states; runtime fields in work-package files; two write shells; the five-source read door; the merge driver; repair modules. About 13,000 of 21,400 lines in `status/` and most of the 6,500 lines of `move-task` modules.

### 4.4 Events

**Design.** The events system owns one ledger per Mission at `refs/heads/kitty/ledger/<slug>-<mid8>`, and one repository ledger for Ops. A ledger commit holds one file. Writes follow ADR-0007 D-1: read the tip, append rows to the blob, build the tree, commit, `update-ref` with the expected old value. No checkout ever holds the ref, so `COORDINATION_REF_CHECKED_OUT` and the move of the repository root checkout at settlement (`core:docs/adr/4.x/2026-11-06-4-coordination-branch-written-by-commit.md:152,183` [read]) have no cause.

One envelope with a version. Order is append order. Two clones that both appended meet at push: the loser fetches and re-appends its local rows after the remote ones, each re-checked by the state machine; a row that is no longer legal is refused and reported. This is the one join rule that remains.

One deployable serves command and query, with one fold. Core holds a client behind the existing port (`src/runtime/next/event_bridge.py` [read]).

**Deletes** [inferred, M4 §8]: core's appenders and reducer wrapper; wall-clock ordering, the approved-departure lift and seed arbitration (not ported); the second Java fold; the produce seam (`src/specify_cli/status/adapters.py:150-318` [read]; no registrant, X1 6.1); `canonical-events.jsonl`; the hosted vocabulary in the package; the parity oracles against a pinned core commit.

**No longer does:** byte parity with today's rows; union of logs written on several branches.

### 4.5 Charter and packs

**Design** (M5 B and C combined). Activation is one file: an ordered pack list, exclusions, and the floor an organisation pack imposes. One id per artefact. One precedence order for artefacts and templates. The charter system compiles on every change of a pin or of the activation into `.kittify/charter/compiled/<type>/<action>.md`, one file per fetchable body, and one resolved definition per active mission type. Core's governance reader checks an input hash and hands the file to the prompt. A profile is appended at delivery. The same inputs give the same text in every checkout; `context-state.json` is gone.

`charter` CLI verbs forward to the charter system's command. No resident charter process is needed locally.

**Deletes:** `src/charter/` and the CLI-side helpers leave core (about 87,000 lines [inferred, M5 §4]); the six-tier template chain and its copy; `selected_*`, three-state allow lists, per-kind defaults, the identity index, the catalog copy in `charter.yaml`.

**No longer does:** per-artefact opt-in without a pack; relationship queries at run time.

### 4.6 Execution coordination and agent integration

**Design.** Three operations. `decide` (4.2). `act`: start, submit, verdict, answer, accept, land, each one guarded event plus its git effect. `read`. The CLI, the generated commands and the orchestrator API render them. The API shrinks to those verbs at contract 2.0. Starting and supervising executors stays outside core.

Commands in agent tools are generated from the active mission types, one per step, by the tool-surface reconciler (`src/specify_cli/tool_surface/` [read], already declarative). A tool is a data row: directory, file format, argument placeholder, orientation file.

`dispatch` loads the compiled context for a role and appends one record to the Ops ledger.

**Deletes** [inferred, M6 §8, M8 §4]: the parallel claim path in `orchestrator_api/`; lifecycle shims; `shims/`; user-global installers; about 56 agent-copy migrations; three of four ownership manifests; the dispatch keyword router.

**No longer does:** install outside the project; keep a fixed software-dev command list.

### 4.7 Landing approved work with evidence

**Design** (M7 B). Four rules.

1. A verdict names the commit it judged. Approval is recorded only together with integration: the work branch at that commit is merged into the Mission branch with a real merge (`--no-ff`). If the merge has conflicts, the approval is refused and the work package returns to `in_progress` to take the Mission branch in and be reviewed again. A crash between merge and record is healed by running the command again: the commit is already an ancestor.
2. Canceling an approved work package requires a reverting work package. Canceled work that was never approved was never integrated.
3. Acceptance names the Mission branch tip. If the target moved, the Mission branch takes the target in first; that merge is a reviewed unit like any other.
4. Landing advances the target by one compare-and-swap. Merge strategy: the target tip's second parent is the accepted commit. Squash strategy: the new commit's tree equals the accepted commit's tree. Otherwise nothing moves. Origin freshness is checked first (kept as is, about 800 lines, M7 §7).

`land --dry-run` runs the same checks without the ref update. Publication stays a push and a pull request by the user; `land --as-pr` stops after the checks and prints the branch to publish.

**Deletes** [inferred, M7 §8]: the gate axes, attribution, windows, the approval-stamp bound, attestations, `--dependency-ref`, snapshot and intent records, resume recovery, the merge-attribute guard, forecast, coordination teardown, the orchestrator mirror, the `rebase` strategy. About 30,000 of 36,400 lines in `consolidation/`.

**No longer does:** land a branch that mixes approved and canceled work; lift a refusal by attestation.

### 4.8 Upgrade and compatibility

**Design** (M8 A, ending at B). `schema_version` is the one "older or newer" authority; `MIN_SUPPORTED_SCHEMA` (`src/specify_cli/migration/schema_version.py:22` [read], unchanged since 3.0) is raised to 4 once. `upgrade` does three things: refuse below the floor (3.2.x) naming the stepping-stone command; run one converter to shape 4; run the reconcilers (tool surface, ignore lines, git config). After 4.0, a data change is one idempotent converter per major version. No ledger of applied steps.

**Deletes** [inferred, M8 §8]: nearly all 144 registered migrations; supersession, adoption, the clone-local partition; the 14 `migrate` subcommands; the worktree pass; runtime legacy readers in 26 files; the empty shim registry. About 20,000 to 25,000 lines.

## 5. How the extension points work

| Who | Can change without editing core | Through |
|---|---|---|
| Mission-type author | steps, order, prompts, templates, roles, checks, requirement kinds, capabilities; may override a built-in | a pack or `.kittify/charter-packs/` |
| Pack author | rules, profiles, skills, glossary terms, presets, required floor | a pack, validated by the charter system |
| Agent-tool integrator | where and in what format commands and orientation text are written | a tool profile (data) in a pack |
| External orchestrator | when and with which executor each operation runs | orchestrator API 2.0 |

**The rule that keeps core free of special cases.** Core source contains no mission-type id, no step id and no tool id. A gate fails the build on any such literal outside tests. Built-in types and tools use exactly the files an outside author would write. If a built-in needs something the format cannot express, the format grows a named check or field; core never branches on a name. The check vocabulary is closed and versioned in the compiled-definition contract; an unknown check fails at compile, not at run time.

## 6. State and authority

| Store | Where | Authority for | Writer | Derived views |
|---|---|---|---|---|
| Mission ledger | ref `kitty/ledger/<slug>-<mid8>` | work-package state, Mission position, verdicts, decisions, acceptance, landing | events system | status board, lifecycle age, `history.md` export |
| Ops ledger | ref `kitty/ledger/ops` | dispatch records | events system | invocation lists |
| Mission definition | `kitty-specs/<m>/` on the Mission branch: `meta.json` (id, slug, type, target), `wps.yaml`, `type.lock.yaml`, spec, plan, task files | identity and plan | core (create, tasks) and the author | none |
| Code | Mission branch, work branches, target | content | git | none |
| Activation | `.kittify/charter/activation.yaml` | what is in force | charter system | `.kittify/charter/compiled/` |
| Pack pins | `packs/*.source.yaml`, config pack list | which content versions | charter system verbs | fetched trees (cache) |
| Project config | `.kittify/config.yaml` | tools, protected branches, landing strategy | core verbs | generated tool files and their one manifest |
| Shape version | `.kittify/metadata.yaml` | supported shape | upgrade | none |

That is eight stores against 62 registered surfaces today (M3 §4). No local-only store holds authority; nothing under `.kittify/runtime/` is needed.

**End state.** The events system owns every ledger, the envelope, the state machine and the read side. The charter system owns pack semantics, activation semantics and compilation. Core owns the Mission model, the step runtime, workspaces, landing and the interfaces.

## 7. Quality attributes

| Attribute | How it is met |
|---|---|
| Recoverable after interruption | Every operation is one compare-and-swap, or a git effect followed by one event that a re-run completes. No run state to resume or abort. |
| Safe with several agents | Separate work branches; exclusive start through the ledger's compare-and-swap; no shared mutable file in any checkout. |
| Auditable | One ledger; every verdict, acceptance and landing names a commit and an actor; overrides are their own events. |
| Shared through git | Ledger refs and branches are ordinary branches. |
| Usable offline | Everything is local; the join rule runs at the next push. |
| Replaceable parts | Three contracts: ledger commands and queries, compiled charter files, orchestrator API. Core imports neither Java service's model. |
| Explainable refusals | A refusal names one mechanism. |

**Traded away:** proof against a dishonest agent (identities stay asserted, M7 §2); a pure-Python install if the ledger writer is the Java service.

## 8. What this design is worse at

| Worse | For whom |
|---|---|
| Parallel work packages that touch the same file now meet at integration: the later one must take the Mission branch in and be reviewed again. Today lanes try to avoid this by construction. | teams running many agents on overlapping areas |
| The Mission branch contains approved work before the Mission is accepted. A late change of mind costs a revert. | a Human in Charge who cancels after approval |
| The ledger is not a file in the target tree. A reader in a forge's file browser sees the plan and an optional exported history, not the live record. | observers without the CLI (C24, J10) |
| Per-artefact activation becomes pack list plus exclusions; long exclusion lists for projects that hand-picked. | governance owners with fine-grained selections |
| Tools without a profile get nothing; native pickers and plugin bundles are not generated. | users of the less common tools |
| Upgrade from below 3.2 takes two commands; in-flight Missions on execution lanes are flattened and need one integrated approval. | long-dormant projects; Missions open at upgrade |
| Operator escape hatches (attestations) are gone; the only override is the recorded override event. | operators with irregular history |

**Complexity my stance keeps that a blank-page design would not have.** Two native Java systems beside a Python CLI, with launchers, pins and release lines, for a tool whose state is small files in git. Packs with thirteen artefact kinds and a relationship graph at authoring time. Tool-managed worktrees where a host could own them. A versioned orchestrator API with two drifted clients. Seventeen tools as data rows. I keep these because they are the direction under way or a documented promise, not because the needs require them.

## 9. Alternatives rejected at the main forks

| Fork | Chosen | Rejected | What would make me choose it |
|---|---|---|---|
| Where the ledger lives | a dedicated ref no checkout holds | (a) a tracked file on the Mission or coordination branch (the recorded G5); (b) a store outside git | (a) if the architect requires the live record in the target tree at all times: then the partition survives in a small form and section 4.1 shrinks to "retire the coordination worktree". (b) if sharing through ordinary git (C32) is dropped |
| Unit of approval | one work branch, integrated on approval | (a) thin lanes with per-work-package approval; (b) the pull request as the landing (M7 A) | (a) if "nothing integrates before acceptance" is a requirement: then attribution stays and about 20,000 lines of consolidation survive. (b) if every user has a forge with required review: then `land` becomes "open the pull request" |
| Who writes the ledger | the events system as one service deployable | the events Python package in process (M4 B) | if a resident native process on the CLI path is not required for 4.0. The port and the ref format are the same, so this is reversible; it deletes `command-cli` and core's `services/` instead of core's reducer wrapper |
| Charter delivery | compile to files at change time | a resident charter service answering each step | a committed hosted or multi-project product that needs live resolution; local delivery would still read files |
| Step position | derived, with events for artefact-less steps | a persisted cursor in the ledger | a documented mission type whose steps can repeat or branch on data that is neither artefact nor event |
| Tool integration | profiles as data, 17 rows | two open formats only (M6 B) | a ruling that the tool list is not a commitment |
| Worktree ownership | the tool creates, or adopts the caller's checkout | host-provided only (M1 B) | evidence that every supported host creates worktrees reliably |

## 10. Dependencies on decisions only the architect can make

1. **The live ledger may leave the target tree** (a ref, plus an export). Everything in 4.1, 4.3 and 4.7 rests on this.
2. **Integration on approval** is acceptable, with a revert as the cost of canceling approved work.
3. **Service or library** as the ledger writer for 4.0.
4. **The local activation file is authoritative** and the charter is compiled, not served, for local use. Three records disagree today (M5 §6).
5. **The 4.0 floor is 3.2.x**, and Missions in flight are flattened at upgrade.
6. **State reduction** (`claimed`, `done`, sentinels) before the ledger contract reaches 1.0.
7. **Orchestrator API 2.0**, breaking both known clients once.
8. **Squash or merge** as the default landing strategy.
9. **Supersede as sets**, not amend: the five consolidation ADRs, the topology and coordination ADRs, the migration-ledger ADR.
10. **Human in Charge at acceptance:** whether `accept` must be interactive unless a standing delegation is recorded in the charter. I recommend yes; it is the one place where the principle would be mechanism instead of instruction (M6 §11).

Principles (R8): all five are kept. I challenge one application: "explicit responsibility ownership" carried as per-line authorship proof at landing. I keep the principle as "every verdict, acceptance and landing names an actor and a commit".

## 11. Transition

Order matters; the product works after each step. Steps 1 to 3 need no ruling beyond this assessment.

| # | Step | Kind |
|---|---|---|
| 1 | Retire what has no reader or is a copy: the copied missions tree, the produce seam, the frontmatter mirror, `mission-events.jsonl`, committed `status.json`, the empty shim registry, the second resolver | legacy, retire now |
| 2 | Mission value object and one handle resolver; accepted-set query; typed protection refusals | consolidation |
| 3 | Built-in types as data: declarative checks carry every present guard, then the Python tables go; commands generated from types | consolidation |
| 4 | One envelope; all Mission facts in one log; events system binds as the only writer and fold | finish the move |
| 5 | The ledger moves to its own ref for new Missions; work branches replace execution lanes; topology is no longer written | replacement |
| 6 | `land` by tree equality becomes the only landing; API 2.0 | replacement |
| 7 | Charter model reduced on the service side; compile to files; core's Python charter removed at one switch | finish the move |
| 8 | Baseline cut: shape 4, converter, reconcilers; migrations and legacy readers removed | retirement |

Transitional arrangements, each with its end:

| Arrangement | Why | End |
|---|---|---|
| Local-file adapter behind the event port | until the events system writes | step 4 complete |
| Declarative and Python guards both evaluated and compared | to prove equivalence before deletion | one release candidate; then the tables go |
| Flatten converter for Missions in flight (merge lanes into the Mission branch, import the old log into a ledger, ask one integrated approval) | user data is not disposable (R16) | removed in 4.1 |
| Read-only import of old `status.events.jsonl` rows | used only by the converter | removed with it |
| Python charter behind `charter.offering.api` | until the compile switch | step 7; one switch, no shadow period |
| The 14 present command names as generated aliases | muscle memory | 4.1 |
| API 1.x verb names accepted and mapped | the two clients update once | 4.1 |
| Stepping stone through a pinned 3.2.x CLI | projects below the floor | lives outside core; no code kept |

Legacy retired with no arrangement: G0 status routes, the `lanes` and `coord` topologies, the `LEGACY` template tier, legacy activation keys, `feature_*` aliases, the `rebase` strategy, workflows.

The old consolidation executor is not kept for old Missions. Two shapes without an end is how the present generations came to coexist (M1 §9).

## 12. Breaking changes as trade-offs

| Change | Consequence | Consumers and data | Migration options and cost |
|---|---|---|---|
| Ledger on a ref, one envelope | `status.events.jsonl` and `status.json` are no longer written; tools that read the files break | every project; `fleet-kitty` scripts that read the log; the read service's directory resolver | (a) import open Missions, leave landed ones as text: low cost, no reopening of pre-4.0 Missions; (b) convert all: clean, but rewrites history-derived data for no reader; (c) upcast on read for ever: keeps two shapes. I recommend (a) |
| Work branches replace execution lanes; topology keys removed | `lanes.json`, `--topology`, coordination branches disappear | Missions in flight; events contracts `Topology.yaml`, `WriteSurface.yaml`; orchestrator `workspace_path` | flatten converter (a few hundred lines, ends 4.1), or "land before upgrading" at zero code cost. Contracts are below 1.0 and have no consumer outside the ecosystem |
| Integration on approval | approved work is on the Mission branch early; canceling it needs a revert | users of cancel-after-approve; prompts for review | none needed for data; a documentation and prompt change |
| Landing by tree equality; attestations and `--dependency-ref` removed | irregular histories refuse with no lift | operators; orchestrator refusal-code lists | the override event is the one exception path; state it in the guide |
| State reduction | `claimed` and `done` vanish as names | orchestrator scheduler and loop; 12 pack prompts naming `move-task` | one mapping table on import; clients updated once |
| Orchestrator API 2.0 | 27 verbs become about 8 | `spec-kitty-orchestrator`, `spec-kitty-mcp`, both already behind (`spec-kitty-orchestrator:src/spec_kitty_orchestrator/host/client.py:399` calls `merge-mission` [read]; core registers `consolidate-mission`, `src/specify_cli/orchestrator_api/commands.py:619` [read]) | one update each; 1.x names mapped until 4.1 |
| Activation as pack list plus exclusions; ids equal stems | `charter.yaml` selections and legacy keys stop being read | every project with a charter; org packs; open-packs content | one converter that writes the new file and leaves the old; the effective set is computable today (M5 §9). Pack content change is mechanical |
| Mission-type format unified | custom `.kittify/missions/<key>/mission.yaml` and workflow files stop loading | projects with custom types; org packs | a converter command, or read the old shape as input for one release line |
| Floor at 3.2.x; `migrate` commands removed | no one-command upgrade from older versions | users below 3.2; open-packs prompts naming `migrate` (4 files, M8 §9) | pinned 3.2.x stepping stone: near-zero build cost, one extra command for the user |
| Commands generated per type; user-global installs removed | stale global files; new names for non-software steps | every user's tool directories | the reconciler removes what it owns; aliases until 4.1 |

## Confidence and what would change my mind

Medium-high that topology, coordination, execution lanes and consolidation should be replaced together. Medium on the unit of approval and on the Java service as ledger writer; the design does not depend on the latter.

Settleable by safe experiment: declarative checks against present guards (M2 §11); tree equality against the present gate on landed Missions (M7 §11); append order against the fold (M4 §11); `decide` without the cursor (M6 §11).

I would change the recommendation on a documented journey that needs planning artefacts on the target while status sits elsewhere before landing, or on evidence that re-review after an integration conflict costs teams more than the lane machinery it replaces.
