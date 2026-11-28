---
doc_status: draft
updated: '2026-11-28'
---

# Candidate architecture CA (delete-first)

Architect CA, profile `architect-alphonso`. The profile's "decide" verb yields to the envelope: this file proposes, the architect decides. `A/` is this assessment folder. Facts relayed from the mechanism reports are cited as `A/mechanisms/Mx §n`; facts I checked at head carry [read] or [executed]. Line estimates for the target are [inferred] orders of magnitude.

## Conclusion

Three choices remove most of the present system. They only work as a set.

1. **Status leaves every working tree.** One append-only record on one git ref per repository, written by compare-and-swap, owned by the events system. No checkout holds a copy.
2. **One branch per unit of review.** A Mission is a branch. A work package is a branch cut from it, merged back into it when approved. There are no execution lanes, no topology, no coordination branch, no partition.
3. **Approval and acceptance each name a commit.** Landing is a tree-equality test and one ref update.

With these, lanes, coordination, placement, consolidation and most of status have nothing left to do: about 96,000 of core's 524,936 source lines [executed: `find src -name '*.py' | xargs cat | wc -l`, and the same per package: `consolidation` 36,414, `lanes` 16,574, `coordination` 15,036, `status` 21,397, `mission_runtime` 6,868]. Three further cuts are independent: rules are compiled to static files when they change (`charter`, 77,725 lines, leaves core); the step loop is a pure function with no cursor; upgrade is a reconcile plus a baseline cut (`upgrade` 33,155, `migration` 12,003). I estimate core at 25,000 to 40,000 lines at the end state.

What is lost, in one sentence: conflict avoidance by construction, fine-grained local proofs about canceled content, per-artefact rule activation, bespoke per-tool features, and direct upgrade of Missions in flight.

## 1. The architecture in one page

Six concepts. A user needs the first four.

| Concept | What it is | Carried by |
|---|---|---|
| **Mission** | An agreed intent on its way to a verified result | One branch (`kitty/<slug>-<mid8>`) holding one folder `kitty-specs/<slug>/` |
| **Work package** | A bounded unit of work and of review | One branch cut from the Mission branch; a checkout of it is the workspace |
| **Record** | Who did what, when, on which commit | One append-only log per repository on a ref no checkout holds |
| **Mission type** | The steps of a kind of work, with their checks | Data in a pack |
| **Charter bundle** | The rules in force, as files an agent reads | Compiled from an ordered pack list; committed |
| **Landing** | Accepted tree equals landed tree | One compare-and-swap of the target ref |

```
packs (open-packs, org, project)        content: rules, profiles, mission types, skills, tool adapters
  └─ charter system                     validates packs; compiles activation → charter bundle (static files)
        └─ .kittify/charter/bundle/     the only thing core reads about rules and mission types
core CLI (spec-kitty)
  ├─ Mission model                      identity, target, type; one value object per invocation
  ├─ step loop                          next = f(mission type, files on the Mission branch, record)
  ├─ workspace                          create/verify a work-package branch and checkout (git worktree)
  ├─ review and landing                 approve(sha), integrate, accept(sha), land (tree equality)
  ├─ tool projection                    bundle + adapter table → files in each agent tool's format
  └─ reconcile                          init / upgrade / doctor: desired state versus actual
events system (spec-kitty-events)       record format, append by CAS, fold, the one state machine and its guards
git                                     branches, worktrees, merge, ancestry, refs, transport
host agent tool / external orchestrator starts, supervises and stops executors; clients of `--json`
```

## 2. Capabilities kept, changed and dropped

"Carrier" is the mechanism that carries the capability in this design.

| Id | Disposition | Carrier, and reason |
|---|---|---|
| C01 setup | kept | `init` = reconcile; `doctor` = reconcile in check mode |
| C02 inside the agent tool | kept, reduced | Agent Skills plus an `AGENTS.md` block; other tools through adapter rows in a pack. Native hooks, plugin bundles and native profile projection go |
| C03 interview to spec | kept | Step prompt; questions and answers are record events |
| C04 plan and work packages | kept | Step prompts; `work-packages/WPnn.md` frontmatter is the one source of dependencies |
| C05 what next, resume | kept | Stateless step loop; nothing clone-local to lose |
| C06 state recorded | kept | Record on a ref |
| C07 parallel without overwriting | kept | A branch and a worktree per work package |
| C08 dependent work | kept | A work package is claimable when its dependencies are approved and merged into the Mission branch; it is cut from there |
| C09 independent review | kept | Approval event names a commit and a reviewer; one guard in the state machine |
| C10 human accepts | kept | `accept` event names the Mission tip |
| C11 only reviewed work lands; preview, resume, undo | kept, simpler | Tree equality; dry run is the same check; resume is re-run; undo is the previous tip in the landing event |
| C12 target stays clean | kept | Nothing but `land` moves the target |
| C13 recoverable | kept | Every operation is one ref update or one ordinary git command |
| C14 other kinds of work | kept | Mission types as data, built-ins included |
| C15 new kind without changing the CLI | kept, made true | Same path as built-ins |
| C16 rules once | kept | Charter bundle |
| C17 choose what applies | kept, reduced | Ordered pack list plus exclusions. Per-artefact opt-in and cascade go |
| C18 organisation floor | kept | A pack marks artefacts required; the compiler refuses an exclusion |
| C19 roles | kept | Profiles are bundle files |
| C20 consistent terms | reduced | Glossary is pack content delivered in context. The semantic-integrity pipeline goes |
| C21 short governed task | kept, reduced | An Op is two record events around a bundle read. The keyword router goes |
| C22 external program, versioned contract | kept, changed | `--json` on the same commands; one envelope version |
| C23 unattended to a decision point | kept | Loop returns `wait` at a human step; supervision stays outside core |
| C24 visibility | kept | `status` and `status --json` fold the record |
| C25 event consumers | kept at no cost | The record ref is the publication seam; no in-process seam |
| C26 learning loop | reduced | A `retrospect` step writes proposals; a human edits the project pack |
| C27 upgrade | reduced | Reconcile, plus one bounded import for Missions in flight |
| C28 tracker | dropped from core | The host tool's own connectors fetch issues; a Mission stores links |
| C29 diagnose and repair | kept, reduced | One `doctor` |
| C30 several Missions | kept | Each is a branch; a second Mission in the same clone uses a worktree |
| C31 close, reopen, follow-up, archive | dropped | No journey found (`A/needs/needs-and-journeys.md` §4). A follow-up is a new Mission with a link |
| C32 shared state through git | kept | Fetch and push of the record ref; divergence resolved by replay |

## 3. Components and ownership

| Component | Owns | Knows nothing about | Interface | State, and who may write |
|---|---|---|---|---|
| Mission model (core) | Identity, slug, target branch, type and its digest | Status, rules | `Mission.load(handle)`; every command receives it | `kitty-specs/<slug>/mission.yaml` on the Mission branch; humans and `mission create` |
| Step loop (core) | "What is legal next, for whom" | How status is stored; type names | `next`, `report` | none |
| Workspace (core) | Work-package branch and checkout exist and match | Review, rules | `claim` | git only |
| Review and landing (core) | Approve, integrate, accept, land; the evidence that needs git | Rule content | `review`, `accept`, `land` | git refs; record through the events API |
| Tool projection (core) | Files in agent-tool formats | Tool names (data) | `reconcile` | generated files, marked in a header |
| Events system | Record format, append, fold, exchange, the state machine and every lifecycle guard | Worktrees, mission-type content | `append(event, expected_tip)`, `fold(mission)`, `tail` | the record ref; sole writer |
| Charter system | Pack model, validation, activation semantics, compilation, mission-type schema | Missions in flight | `charter compile`, `charter check` | reads `activation.yaml` and packs; writes the bundle |
| Packs | Content | Code | files | pack repositories |
| Orchestrator, MCP adapter | Executor lifecycle | Core internals | client of `--json` | their own |

One owner per rule that is duplicated today (`A/duplication/catalogue.md` classes 1 to 4):

| Rule | Owner |
|---|---|
| Lane vocabulary, legal moves, dependency readiness, reviewer differs from author, "accepted" predicate | Events system. Core and the orchestrator ask; none restates |
| Target branch, Mission branch, handle resolution | Mission model. The about 22 branch resolvers and 97 handle resolvers (catalogue 2.1, 2.4) collapse into one object |
| Step order, exit checks, profile per step, requirement kinds, capability flags | Mission-type definition in the pack |
| What is in force | `activation.yaml`, interpreted only by the charter system |
| Supported tools and their paths | Adapter table in a pack |
| Protected-branch behaviour | Not needed: nothing but `land` writes to the target, and the record ref is never protected |

## 4. The mechanisms in scope

### 4.1 Workspaces and parallel work

**Design.** `mission create` makes the Mission branch and switches the current checkout to it, or adds a worktree with `--worktree` for a second Mission. Planning steps commit to that branch as ordinary commits. `claim WP03` creates branch `kitty/<slug>-<mid8>.WP03` from the Mission tip and adds a worktree; `--here` switches the checkout the caller is in instead, which is also how a host-provided worktree is used. Core stores nothing about this: the check is "this checkout's HEAD is the work-package branch". Overlapping `owned_files` between two work packages in progress give a warning at claim; a conflict surfaces at integration, as in plain git. Cleanup uses `git branch -d` and `git worktree remove`, which refuse unmerged or dirty work.

**Deletes.** Execution lanes and lane computation with its keyword heuristic (`A/mechanisms/M1 §5` item 7); the four topologies, their source and settlement; the coordination branch and worktree; the PRIMARY/COORD partition and placement seam; the planning-commit pin; sparse exclusion; write-checkout modes; owned checkout as a mode; workspace context files; lane-tip hooks and refs; auto-rebase and incorporate. Packages `lanes`, `coordination`, `workspace`, `mission_runtime`: about 41,000 lines [executed], and about 120 refusal codes (`A/mechanisms/M1 §4`).

**No longer does.** It does not group work packages to avoid a conflict.

### 4.2 Mission types and the step runtime

**Design.** A mission type is one descriptor and one folder per step: prompt, templates, role profile, governance references, produced artefacts, and exit checks from a closed vocabulary (file present; glob count at least N; table has at least N rows; all work packages at or beyond a state; decision recorded; step reported). A step has one of three kinds: `once`, `per-work-package`, `human-decision`. Built-in types ship only in this form. `next` evaluates the steps in order against the Mission branch and the folded record, and returns `step`, `wait`, `blocked` or `done`. A step that leaves no artefact is completed by a `report` event. The type's digest is stored in `mission.yaml`; a changed definition is reported and a human re-pins.

**Deletes.** `mission.yaml` phases and the `Mission` class, `mission-runtime.yaml`, step contracts as a kind, workflows, the run cursor and run index, composition versus DAG dispatch, `_GUARD_TABLES`, `_STATE_ALIASES`, capability and profile tables, `RESERVED_BUILTIN_KEYS`, the copied tree `src/specify_cli/missions/<type>/`, the requirement-kind branches (`A/mechanisms/M2 §4-5`). `src/runtime` is 17,627 lines [executed]; the target loop is about 2,000.

**No longer does.** No RACI or significance scoring, no frozen template per run, no audit steps.

### 4.3 Mission and work-package lifecycle

**Design.** Six states: `planned`, `in_progress` (with assignee), `for_review`, `in_review` (with reviewer), `approved` (with commit), `canceled`; `blocked` is a flag with a reason. `done` is not a state; it is the landing fact. An override is its own event with actor and reason, so an overridden approval is a different fact from a reviewed one. Review feedback is the payload of the rejection event. Mission-level facts (created, question asked and answered, step reported, accepted, landed) are events on the same record. Every guard runs inside `append`, so the rules do not depend on the door used.

**Deletes.** Seventeen stores down to one (`A/mechanisms/M3 §4`): `status.json`, the frontmatter mirror, `mission-events.jsonl`, `lanes.json`, `wps.yaml` versus `tasks.md` dependency sources, review-cycle files, acceptance fields in `meta.json`, the derived lifecycle file. The sentinel lanes, `claimed`, `done`, the force flag, the two write shells, the five read sources.

### 4.4 Events

**Design.** One branch-shaped ref, `refs/heads/spec-kitty/record`, never checked out. It holds one JSONL file per Mission and one for Ops. An append is a commit built from git objects and a compare-and-swap ref update, the technique the events repository has already accepted for coordination status (`spec-kitty-events:docs/adr/0007-write-service-commits-coordination-status-by-ref.md:2` [read]). Append order is causal order. Between clones the ref travels by ordinary fetch and push; when a push is refused, local-only events are replayed on the fetched tip through the state machine and any that became illegal are reported to the caller ("WP03 was claimed by another actor"). One envelope with a schema version; one fold; one implementation, in the events system, called in process.

**Deletes.** Wall-clock ordering, the approved-departure lift, seed arbitration and the merge driver, which exist because rows are appended on several branches and joined by git (`A/mechanisms/M4 §5.4`). The produce seam with no subscriber. Core's `status` package. The second and third copies of the state machine. On the Java side, the write service and the read-directory resolver are not on the CLI path; the read service becomes a reader of one ref when a consumer exists.

**No longer does.** No resident process; no status file in a working tree.

### 4.5 Charter and packs

**Design.** `.kittify/charter/activation.yaml` is an ordered list of packs with pins, a list of exclusions, and nothing else. The charter repository has already ruled that the local file is the source of truth (`spec-kitty-charter:docs/adr/0033-local-active-charter-is-source-of-truth.md:24` [read]). `charter compile` runs when that file or a pin changes and writes `.kittify/charter/bundle/`: per mission type and step, one context file within the size budget plus one file per fetchable body; the mission-type definitions; the profiles; the skills; the adapter table; a hash of the inputs. The bundle is committed, so a rule change is a reviewable diff and a clone needs no compiler. `next` compares the hash and refuses a stale bundle. The built-in bundle ships precompiled in the wheel.

**Deletes.** From core: the `charter` package, the charter CLI helpers, the six-tier template chain, both resolvers, `context-state.json` and the first-load mode that makes delivery depend on checkout state (`A/mechanisms/M5 §5.1`). From the model: `selected_*` lists, three-state allow lists, per-kind absent defaults, cascade, the identity index, the run-time graph, the per-worktree daemon. About 78,000 Python lines in core [executed], and the reason to port the same concept set to Java.

### 4.6 Execution coordination and agent integration

**Design.** Five operations: decide (`next`), claim, report, ask/answer, read (`status`). Review, accept and land are the three governed transitions on top. Each is one command with `--json` and one envelope version; there is no separate orchestrator API package. Commands for agent tools are generated from the steps of the active mission types, one per step that declares it, so a research or custom step gets a command exactly as `specify` does. Today the set is a fixed tuple matching software-dev (`core:src/specify_cli/skills/command_installer.py:98-102` [read]). A tool adapter is a row of data: directory, file format, argument placeholder. Generated files carry a header marker; reconcile removes marked files that are no longer wanted. No manifest stores.

**Deletes.** `orchestrator_api` (5,855 lines [executed]) as a second implementation; `tool_surface` and `skills` (17,229 lines) down to a renderer of about 1,500; the ten per-tool tables (catalogue 1.8); session presence writers; user-global installs; top-level lifecycle shims; `agent action` versus `implement` versus `move-task` as separate doors; the dispatch router; `kitty-ops/lifecycle`.

### 4.7 Landing approved work with evidence

**Design.**

1. `review approve WP03` records the reviewed commit. Core then merges the work-package branch into the Mission branch with `git merge --no-ff`, in the Mission's own checkout. A conflict aborts the merge and returns the work package to its author; the resolution is a new commit and needs a new approval.
2. A canceled work package that was never approved was never merged. One canceled after integration is removed by a revert commit on the Mission branch.
3. `accept` is a human act that names the Mission tip. It is the integrated review that covers what separate approvals cannot: the combination.
4. `land` checks: the Mission tip equals the accepted commit; every approved work-package commit is an ancestor of it; the target tip is an ancestor of it; the remote is not ahead (the origin-freshness check stays; it is small). It then advances the target by fast-forward merge, or by one squash commit whose tree equals the accepted tree. If the target moved, the user merges it into the Mission branch and accepts again.
5. If the target already contains the accepted tree, because a pull request landed it, `land` records that and cleans up. The Mission branch is an ordinary branch and can be the pull-request branch.

**Deletes.** Claim, gate, six axes, attribution, windows, line attribution, attestations, snapshot and intent rollback, resume recovery, forecast, merge-attribute guard, coordination teardown, the orchestrator mirror, the `rebase` strategy. About 34,000 of 36,414 lines, 60 refusal codes and 18 pinned residuals (`A/mechanisms/M7 §4-5`).

### 4.8 Upgrade and compatibility

**Design.** One integer, the project format, in `.kittify/config.yaml`. `upgrade` is reconcile: bundle, generated tool files, required ignore lines, format stamp. It refuses a project older than the floor and names the stepping-stone command. Clone-local git configuration is no longer needed: there are no merge drivers, hooks or sparse patterns left to install. A future data change is one idempotent converter per format number.

**Deletes.** 155 migration modules, both ledger partitions, the order manifest, supersession, adoption, the worktree pass, the `migrate` command family, 16 doctor modules, the empty shim registry, and every runtime "unmigrated" reader (`A/mechanisms/M8 §5`). About 45,000 lines [executed].

## 5. Extension points

| Who | Changes without editing core | Through |
|---|---|---|
| Mission-type author | Steps, order, prompts, templates, checks, roles, which steps get a command | A pack folder |
| Pack author | Rules, profiles, skills, glossary, required items | A pack |
| Agent-tool integrator | Where and in which format commands and skills are written | An adapter row in a pack; or nothing, if the tool reads Agent Skills |
| External orchestrator | Scheduling, executor choice, supervision, model selection | `--json` commands and the record ref |

**The rule.** Core never compares an identifier that originates in a pack (type, step, kind, tool, profile) with a literal. Two things hold it in place. Built-in content has no other path into core than the bundle, so the extension mechanism is exercised on the main path every day. One architectural test greps `src` for the identifiers present in the built-in bundle. When a built-in type needs something the vocabulary lacks, the vocabulary grows by a named check kind, for every type.

## 6. State and authority

| Store | Authority | Derived views |
|---|---|---|
| Git branches: Mission, work package, target | git | ancestry, "integrated", "landed" |
| `kitty-specs/<slug>/` on the Mission branch: `mission.yaml`, spec, plan, `work-packages/*.md`, step artefacts | their authors; no runtime field | work-package list, dependencies |
| Record ref | events system, sole writer | board, Mission position, readiness, lifecycle (stale, abandoned), Op trail |
| `.kittify/config.yaml` | project owner | none |
| `.kittify/charter/activation.yaml`, project pack | project owner | the bundle (committed, hashed) |
| Generated tool files | none; derived from the bundle | n/a |

Nothing is clone-local except git's own worktree registry. The state registry lists 62 surfaces today (`A/mechanisms/M3 §4`).

End state. The **events system** owns the record schema, the append and exchange protocol, the fold, and the work-package and Mission state machine with its guards. The **charter system** owns pack and mission-type schemas, activation semantics, validation and compilation. Core owns the bundle reader and the git operations.

## 7. Quality attributes

| Attribute | How it is met |
|---|---|
| Recoverable after interruption | No multi-phase mutation. An interrupted merge is git's own state; re-running a command is the resume |
| Safe with several agents | Compare-and-swap on the record makes a claim exclusive; each work package has its own branch and checkout |
| Auditable | Record events name commits; the landing commit carries accepted-by and reviewed-by trailers; a rule change is a diff of the bundle |
| Usable offline | Everything is local git and files; no service; the bundle is committed |
| Replaceable parts | Three contracts: bundle schema, record schema, `--json` envelope. The events implementation may become a service behind `append` and `fold` |
| Human in Charge | Mechanism at four points: question events, human-decision steps, `accept`, `land`. Honest limit: the actor is asserted locally; an authenticated reviewer needs a host (`A/mechanisms/M7 §2`) |
| Same rules for every driver | One state machine behind one `append`; one set of commands |

## 8. What this design is worse at

| Worse at | For whom |
|---|---|
| Conflicts appear at integration, after approval, and cost a second review | Teams with overlapping work packages |
| A work package rejected after integration needs a revert, which may conflict | The same |
| A work package per worktree means more dependency installs than a shared lane | Large repositories |
| `--here` switches the user's own checkout between branches | Solo users who want no worktrees |
| No proof that canceled lines are absent, no attestations, no declared dependency ref | Operators who relied on those refusals |
| A moved target forces merge and re-acceptance | Busy integration branches |
| Per-artefact activation becomes pack plus exclusions; no cascade; no run-time graph | Fine-grained governance users; any hosted graph consumer |
| Hooks, plugin bundles, native agent pickers, tool-specific orientation | Users of the tools that have them |
| Tracker binding, glossary pipeline, retrospective subsystem, close/reopen/archive, workflows | Their users, if any; none has a documented journey except the glossary |
| No direct upgrade below the floor; Missions in flight need an import | Every existing project, once |
| The Java write service, read-directory logic and charter daemon are off the CLI path | The teams that built them |
| Readers of `status.events.jsonl` on disk | fleet-kitty, the hosted dossier (`A/mechanisms/M3 §9`, `M4 §9`) |

## 9. Alternatives rejected

| Fork | Rejected | I would choose it if |
|---|---|---|
| Where status lives | A tracked file on the Mission branch; or a service-owned store outside git | A ruling that status must be a working-tree file (then the partition returns in some form); or that a hosted store is the product (then the ref is the local cache of it) |
| Unit of isolation | Lanes kept as thin groups on one Mission branch (`A/mechanisms/M1 §8` A) | Measured conflict or setup cost shows integration-time conflicts are frequent |
| Landing | The pull request is the only landing (`M7 §8` A) | The architect rules that a forge is always present. My design already lets a pull request land the Mission branch |
| Rules at run time | A charter service queried per step | A committed product need for live organisation policy or graph queries |
| Step position | An engine with a persisted cursor | A mission type needs progress that can leave neither artefact nor event. I found none |
| Tools | Agent Skills and `AGENTS.md` only, no adapters | The supported-tool list is not a commitment |
| Events implementation | A resident Java writer for 4.0 | Alternate deployments are a 4.0 requirement, not a later option |

## 10. Dependencies on the architect's decisions

1. Integration on approval into the Mission branch, with `accept` as the integrated review. This is a product decision about review, not only a simplification.
2. The record on a ref outside every working tree, and in-process events for 4.0.
3. Compiled, committed rules; the charter system delivers a compiler, not a daemon, for the local product.
4. The supported-tool list becomes data; four tool-specific feature families go.
5. The upgrade floor, and that Missions in flight are imported or finished first.
6. Dropping C28 and C31 and reducing C20 and C26.
7. Whether an asserted human actor is enough locally for `accept`, with the host carrying strong identity.
8. Superseding as a set the five consolidation ADRs and the proposed coordination ADRs, not amending them (R1).

## 11. Transition

During development the old and the new path coexist on the release-candidate line only, selected by the Mission's format field. No general release ships both.

| Transitional arrangement | Stated end |
|---|---|
| `import-legacy <mission>`: merges a Mission's lanes into its Mission branch, rebuilds a record from the old log through one name map, and requires a fresh `accept` | Removed in 4.1 |
| The fourteen present command names as generated aliases of step commands | Removed in 4.1 |
| `orchestrator-api` verbs as thin aliases of `--json` commands | Removed in 4.1 |
| A trimmed Python compiler in core that writes the bundle from today's resolver | The first charter-system release with `charter compile`; the architect sets the date. The bundle schema is frozen first |
| `spec_kitty_events` in Python as the in-process implementation | None needed; it is the target unless decision 2 changes |

A workable order: record on a ref with the six-state machine; then branch per work package with tree-equality landing, deleting lanes, coordination and consolidation together; then the stateless loop with the single type format; then the bundle; then tool projection as data; last the baseline cut. The first step is the unlock: while status is a tracked file, none of the others can delete what they replace (`A/mechanisms/M1 §10`).

Legacy that can simply be retired now: the fan-out seam and propagator; `canonical-events.jsonl`; the copied mission tree; one of the two resolvers; the frontmatter lane mirror; `mission-events.jsonl`; the hosted vocabulary in the events package; the empty shim registry; migrations below the floor.

## 12. Breaking changes

| Change | Consequences | Consumers and data | Migration options and cost |
|---|---|---|---|
| Mission on-disk shape: `meta.json`, `lanes.json`, `status.events.jsonl`, `status.json` replaced by `mission.yaml` and the record | Old Missions are not readable by the new commands | Every project; 859 Missions in core (`M3 §9`); Java read service; fleet-kitty; hosted dossier | (a) land or abort on the old CLI first: no build cost; (b) `import-legacy`: a few hundred lines, ends 4.1; (c) dual readers: rejected, it is how generations accumulated. Landed Missions stay as files in history, unconverted |
| Topologies, coordination branch, lanes removed | Flags and refusal codes vanish | Missions in flight; orchestrator `workspace_path` and lane ids; `Topology.yaml` and `WriteSurface.yaml` contracts (`M1 §9`) | Covered by the import; both contracts are below 1.0 |
| Nine status lanes to six states | `claimed` and `done` disappear as names | Orchestrator scheduler and loop; prompts; `lane.schema.json` | One name map in the import; one update per client |
| `orchestrator-api` (27 verbs, 1.31.0) replaced by `--json` | Contract 2.0 | spec-kitty-orchestrator, which already calls a verb core does not register; spec-kitty-mcp, with fixtures at 1.3.0 (`M6 §5.6`) | Aliases until 4.1; one update each |
| `consolidate` replaced by `land` | 22 flags, three strategies and five attestation families go | Scripts, skills, step prompts, two recovery guides | Rewrite docs; `consolidate` alias until 4.1 |
| Activation model | `charter.yaml` selections and legacy keys ignored | Every project that ran `charter generate` or `activate` | One converter writes pack list plus exclusions; the effective set is computable today (`M5 §9`); long exclusion lists are the cost |
| Mission-type format | Old custom definitions and workflows not loaded | Projects with `.kittify/missions/<key>/`; org packs; pack composer and charter service schemas (`M2 §9`) | A converter in the charter system; one pack release and pin bump |
| Tool surface | Tool-specific features go; file locations may move | Users of 17 tools | Reconcile rewrites generated files; adapters ship as pack data so listed support need not shrink |
| Upgrade floor and no ledger | Two-step upgrade for old projects; `migrate` commands gone | Users below 3.2; open-packs prompts naming `migrate` (4 files, `M8 §9`) | Stepping stone through the last 3.2 release |
| Events package surface narrowed | Unused exports removed | Any hosted consumer outside these clones | The hosted owner takes its vocabulary with it |

## Uncertainty and what would change my mind

Decision-relevant: whether integration-time conflicts are common enough to justify lanes; whether any documented user relies on run-time rule resolution; who outside these clones reads the on-disk log.

Safe to settle by experiment: the four smallest experiments named in `M4 §11`, `M5 §11`, `M6 §11` and `M7 §11` each test one premise of this design.

I would retreat from "one branch per work package" to thin lanes if a pilot shows a second review on most Missions. I would not retreat from moving status out of the working tree: every other deletion depends on it.
