---
doc_status: draft
updated: '2026-11-28'
---

# Candidate simplified architecture

Consolidator K2, profile `architect-alphonso`; its verb "decide" yields to the envelope: this file recommends. `A/` is this folder; `CA`, `CB` are the candidates; `CH` is `A/challenge/candidate-challenge.md`; `Mx §n` is `A/mechanisms/Mx.md`; `X1` is `A/duplication/catalogue.md`. Code references are to core at head unless a repository is named. Tags: [read], [executed] (by me), [relayed] (checked by an input), [inferred]. Experiments ran in `/tmp/claude-0/-home-user/8e7878bc-ed16-58f9-9a0e-caec07f98b23/scratchpad/ar-K2/` on git 2.43.0 (list in section 13). Dispositions are in `06-capability-dispositions.md`.

## 1. Conclusion

One candidate is recommended. It is built on four structural choices that CA (delete-first) and CB (consolidate in place) reached **independently** from opposite stances:

1. The Mission record is on a git ref that no checkout holds.
2. One branch per work package.
3. Approved work is integrated into the Mission branch on approval.
4. Landing is a tree-equality check and one compare-and-swap of the target.

The challenge raised seven major findings. Their status after this consolidation:

| # | Finding | Status here | What is still the architect's |
|---|---|---|---|
| F1 | Mission-branch join | **Answered and checked by experiment**: join by merge, never rebase; every commit an event names stays an ancestor; unreviewed commits are listed at acceptance | Whether an agent's approval may move the Mission branch (D3) |
| F2 | Nobody pushes the record | **Answered in design, open as a ruling**: the tool pushes the record; unshared events are always shown; no clone-local configuration | Whether the tool may push at all (D2). Without that ruling choice 1 is not settled |
| F3 | Where the guards are written | **Named choice with a corrected cost**: guards move from core's Python into the events Python package, once | Library or Java service on the write path (D4) |
| F4 | The `cli` package | **Answered**: disposition table in section 8; CA's end-state size is withdrawn | none |
| F5 | Narrowing; test-origin probe | **Answered**: a pinned-ids form per pack, opt-in kinds, probe kept | Whether exclusion alone is enough (D7) |
| F6 | Transitional compiler without end | **Answered**: no new compiler is written; the Python charter ends before 4.0.0 general availability | Whether 4.0.0 waits for the charter system (D6) |
| F7 | Import of Missions in flight | **Repriced; open**: default is no import; the bounded import is costed honestly | Which of two options (D8) |

Choices 1 and 3 are therefore put forward as **conditional**: 1 on D2, 3 on D3. Choices 2 and 4 stand.

Effect on core, corrected (section 8): from 524,936 Python lines [executed] to roughly 140,000 to 160,000 [inferred]. About 85,000 of that is the Python charter leaving for the charter system: a move, not a deletion. CA's "25,000 to 40,000" follows from no named deletion and is withdrawn.

Confidence: medium-high that topology, coordination, execution lanes and consolidation should be replaced together; medium on integration on approval; medium-low on the writer fork (D4).

## 2. The architecture in one page (intended target)

| Concept | Meaning | Carried by |
|---|---|---|
| Mission | Agreed intent on its way to a verified result | A Mission branch `kitty/<slug>-<mid8>` holding `kitty-specs/<slug>/` |
| Work package | A bounded unit of work and of review | A branch cut from the Mission tip; any checkout of it is the workspace |
| Mission record | Who did what, when, on which commit | One append-only file per Mission on `refs/heads/spec-kitty/record` |
| Mission type | The steps of a kind of work and their checks | Pack data; resolved copy committed per Mission as `type.lock.yaml` |
| Charter bundle | The rules in force, as files an agent reads | Compiled at change time, committed under `.kittify/charter/bundle/` |
| Acceptance | The Human in Charge accepts one commit, the Mission tip | One record event |
| Landing | Accepted tree equals landed tree, or nothing moves | One compare-and-swap of the target ref |

```
Interfaces      CLI | generated agent commands | programmatic API 2.0     (render; hold no rule)
Operations      decide | act (start, submit, verdict, answer, accept, land) | read | sync
Core (Python)   Mission model | step runtime | workspaces | review and landing
                bundle reader | tool-surface reconciler | upgrade (reconcile)
Events system   record: envelope, state machine, every lifecycle guard, fold, append by CAS, replay
Charter system  packs, activation, precedence, required floor, compile to files
Packs           content: rules, profiles, mission types, skills, tool rows
Git             Mission branch, work-package branches, record ref, target, transport
```

Five design rules decide the forks below:

- **R-a.** No mutable Mission state in any working tree.
- **R-b.** One owner per domain rule; every door reaches it through the same operation.
- **R-c.** No native process on the per-command path. Native tools are acceptable at change time (compiling rules).
- **R-d.** An event that names a commit is shared only together with that commit.
- **R-e.** Core compares no identifier that originates in a pack with a literal.

## 3. Essential capabilities and the mechanisms that carry them

The needs (`A/needs/capabilities.csv`) reduce to eight essential capabilities. The rest of the present system is mechanism, and most of it compensates for another mechanism (M1 §7, M7 §1 [relayed]).

| Essential capability | Needs | Target carrier | Replaces |
|---|---|---|---|
| Know where work stands; refuse illegal moves | C05, C06, C24, C32 | record, one state machine | 17 stores, 3 state machines (M3 §4) |
| Isolated parallel work, ordered by dependency | C07, C08, C30 | branch per work package | lanes, 4 topologies, coordination branch, placement seam |
| Independent review, human acceptance | C09, C10 | events naming a commit | review-cycle files, stamps, windows |
| Only accepted work lands, recoverably | C11 to C13 | tree equality, one ref update | claim, gate axes, rollback authority |
| Kinds of work as data | C14, C15 | one type format, closed checks | 5 definition generations, per-type Python |
| Rules stated once, applied at every step | C16 to C19 | compiled bundle | Python charter, resolvers, context state |
| Reachable from agent tools and programs | C02, C21 to C23 | generated commands, API 2.0 | 7 doors, 10 tool tables |
| Set up, repaired, upgraded | C01, C27, C29 | reconcile | 144 migrations, 25 doctor subcommands |

## 4. Components and ownership (intended target)

| Component | Owns | Knows nothing about | State and its writer |
|---|---|---|---|
| Mission model (core) | identity, type, target, Mission branch, the one work-package manifest `wps.yaml`, handle resolution | rules, tools | `kitty-specs/<slug>/` on the Mission branch: `meta.json`, `wps.yaml`, `type.lock.yaml`, artefacts; authors and `mission create`, `finalize` |
| Events system (`spec_kitty_events`, in process) | envelope, states, legal moves, **all guards**, fold, append, replay | worktrees, mission-type content | the record ref; sole writer |
| Step runtime (core) | "what is legal next, for whom" | storage, type names | none |
| Workspaces (core) | create, find, verify and safely remove a work-package checkout; the test-origin check | review, rules | git's worktree registry |
| Review and landing (core) | git facts for a verdict, integration, the acceptance listing, the landing check, `sync` | rule content | Mission branch and target |
| Charter system | pack model, activation semantics, compile, mission-type schema | Missions in flight | `activation.yaml` (source); the bundle (derived, committed) |
| Bundle reader (core) | hand the compiled context to a prompt; staleness check | packs, kinds, graph | none |
| Tool surface (core) | reconcile generated files per configured tool | tool names (data) | one ownership manifest |
| Interfaces (core, `cli`) | render the operations | every rule | none |
| Upgrade (core) | shape gate, one converter, reconcilers | subsystem internals | `schema_version` |

Rules duplicated today get one owner: lane vocabulary, legal moves, readiness, reviewer independence and the "accepted" predicate (34 restatements, X1 2.3) go to the events system; branch and handle resolution (about 22 and 97 functions, X1 2.1, 2.4) to the Mission model; step order and checks (7 surfaces, M2 §5.1) to the type definition; "what is in force" (5 sources, M5 §5.2) to the charter system; tool paths (about 10 tables, X1 1.8) to data rows [all relayed].

## 5. Answers to the seven major findings

### F1. The Mission-branch join

**Finding accepted.** Today approvals in two clones commute; after choice 3 they do not.

**Design answer.**

1. The Mission branch is an ordinary shared branch. Its join rule is git's: a refused push is followed by fetch and `git merge` of the remote tip. The tool never rebases the Mission branch. `sync` performs this.
2. Events name the **approved work-package commit**, not the integration merge. Landing checks that each approved commit is an ancestor of the accepted commit.
3. `accept` names the Mission tip. A join moves the tip, so an earlier acceptance no longer matches and is given again. That is intended.
4. **Acceptance listing.** At `accept` the tool partitions `target..tip` by graph position only: (i) commits inside an approved range (first parent to second parent of an integration merge whose second parent is a currently approved commit); (ii) merges whose tree equals the recomputed mechanical merge of their parents; (iii) the rest. Class (iii) is shown to the human and its commit ids are stored in the acceptance event. It holds planning commits, hand-resolved joins, target merges, reverts, and the integration merge of an approval that a later replay refused.
5. Integration needs no hidden checkout (CH T1). If a clean checkout holds the Mission branch, `git merge --no-ff` runs there. If none holds it, the merge is built with `git merge-tree --write-tree`, `commit-tree` and a compare-and-swap `update-ref`. A checked-out branch is never moved by `update-ref`, so the checkout-behind-its-own-HEAD state the resync code exists for (`src/specify_cli/git/ref_advance.py:3-9` [relayed]) cannot arise. Needs git 2.38, as the present squash detection does.

**How I checked** [executed]. Bare remote, clones A and B. A integrates WP01, B integrates WP02, both `--no-ff`. A pushes; B's push is rejected. B fetches and merges. Both approved commits and both integration merges are ancestors of the join; the join's tree equals `git merge-tree --write-tree` of its parents, so it is classed mechanical. Second round, WP03 and WP04 edit the same file: the join conflicts, the hand resolution is classed (iii) and listed with the planning commit; both approved commits remain ancestors. The join "invalidates" recorded commits (CH F1) only if it is a rebase.

**What it costs.** One small check stays where a gate stood: the listing (a few hundred lines [inferred]). It refuses nothing, and has no path filter, attribution or attestation. A hand-resolved join is reviewed by no work-package reviewer; the human sees it by name. The guarantee becomes "a human accepted the tip, with the unreviewed commits named": weaker than today's per-line proofs (CH C11).

**Still the architect's (D3).** An agent's approval now moves the Mission branch at once; nothing reaches the target without `accept`. **Alternative:** integrate at acceptance. Approvals commute again and F1 disappears, but a dependent work package must be cut from a merge of its predecessors' approved commits (the dependency merge returns), and all conflicts surface together at the human's desk. I recommend integration on approval; a pilot measuring re-review after integration conflicts decides.

### F2. Who pushes the record

**Finding accepted.** A plain `git push` reported "Everything up-to-date" and left the record behind [executed]. A push refspec in `.git/config` or a hook would be clone-local configuration, the S20 failure again; I reject both.

**Design answer.**

1. A `sync` operation: fetch the record and the Mission's branches; replay local-only record rows on the fetched tip through the state machine; push the record together with every commit that the unshared events name (rule R-d). It never pushes the target.
2. Project setting `sync: auto | manual` in `.kittify/config.yaml`, which is committed. `auto` runs `sync` after each state-changing operation when a remote exists; a failed or offline push is not a refusal.
3. Unshared events are never silent. `git rev-list --count origin/spec-kitty/record..spec-kitty/record` is a local read [executed]; `decide`, `read` and every `act` print "N events not shared".
4. `accept` and `land` refuse while the record or the Mission branch differs from the remote. This is the existing origin-freshness gate extended to the record ref (kept, M7 §7 [relayed]).

**How I checked** [executed]. Appends by `hash-object`, `write-tree`, `commit-tree` and `update-ref <new> <old>` with no checkout; the working tree stayed clean. With A and B both appending, B's push is rejected; B's local-only rows (one in the same Mission file, one in another's) were recovered by diff against the merge base, re-appended on the fetched tip and pushed. A stale `update-ref` is refused. Rows were replayed mechanically; the state-machine re-check on replay is not built.

**What it costs.** A network round trip per state-changing command in `auto`; credential prompts in agent sandboxes; a new behaviour, since today the tool pushes only under `consolidate --push` (`src/specify_cli/consolidation/phase_finalize.py:50` [read]). A forge rule matching every branch may refuse the push [inferred].

**Still open (D2).** May the tool push. If not, `manual` is the only mode, sharing depends on the user running `sync`, and points 3 and 4 are the whole protection. **Alternative that removes F2:** the record as a tracked file on the Mission branch, written by commit. Default push carries it; but the Mission tip then moves on every event, so acceptance needs a definition of bookkeeping paths, and a checked-out Mission branch lags its own HEAD. Both candidates rejected it; I agree, and D2 is the price.

### F3. Where the lifecycle guards are written

**Finding accepted; CA's premise corrected.** The events Python package validates edges, force and `review_ref` only (`spec-kitty-events:src/spec_kitty_events/status.py:692`, CH [relayed]). Reviewer independence and dependency readiness are in core (`src/specify_cli/status/models.py:411`, `src/specify_cli/core/dependency_graph.py:35` [read]). The Java write service carries dependency, claim and pipeline guards in an authority package of 2,105 main lines [executed: `wc -l` over `spec-kitty-events:service/command-cli/…/domain/authority`], with no independence guard found (CH F3). It is a served process with an idle timer (`…/config/IdleTicker.java` [read]).

**Choice: the library in process (CA's fork), with the cost CA omitted.** The guards are moved from core's Python into `spec_kitty_events`, behind `append(event, facts, expected_tip)`. That is a move, within one language, of rules that exist; its size is of the order of the Java authority package [inferred]. Core supplies the facts a guard needs (manifest dependencies, the reviewed commit); the contract names them. Reason: R-c; the need is an append to a small file in git.

**Alternative (CB): the Java service as writer.** It already has three of the four guards and gives one fold shared with the read service. It costs a native process on every write, a launcher and release matrix on four platforms, and no pure-Python install; its pin is not yet vendored (`pins/README.md:28`, M4 [relayed]). The ref format and the append contract are the same, so the choice is reversible.

**What decides (D4).** A 4.0 requirement for a writer other than the Python CLI. My choice contradicts the recorded "no Python fallback writer" (`CLAUDE.md`, Shared Package Boundary [read]); under R1 I challenge it and the architect rules. A rule-by-rule comparison of the Java guards with core's is a cheap experiment to run first.

### F4. The `cli` package

Answered in section 8.

### F5. Narrowing by allow list; the test-origin probe

- **S6 (a), kept by other means.** `activation.yaml` holds an ordered pack list with pins and exclusions, and per pack an optional `only:` list of ids. A pack with `only:` does not grow on a pin bump; a pack taken whole does, by the owner's choice. The committed bundle makes any change of the effective set a reviewable diff.
- **S6 (b), kept as is.** A kind that projects files into tool directories (today: skills) is opt-in per id; the absent default stays "organisation-required only" (`src/charter/offering/artifact_kinds.py:263-271`, steelman S6 [relayed]).
- **S4, kept as is, smaller.** The probe that tells whether tests in a work-package checkout load code from that checkout (`src/specify_cli/lanes/lane_invocation.py`, 476 lines, CH [relayed]) moves to the workspaces component and runs at review. One worktree per work package raises the exposure.

### F6. The charter transition

**Finding accepted; CA's trimmed compiler is dropped.** The present Python charter stays behind `charter.offering.api`, unchanged, until one switch (CB's form). The switch release makes core read the bundle and deletes the Python charter. Equivalence is shown beforehand in CI on the conformance corpus, not by a shadow period in user installs.

**End condition:** the switch happens before 4.0.0 general availability. The project's own record already makes the activation switch a 4.0 deliverable (`CLAUDE.md`, Modularity SSOT [read]). **Cost:** 4.0.0 is gated on a charter-system release that has `compile` and the reduced model. **If the architect prefers not to wait (D6):** 4.0.0 ships with the Python charter and the end is 4.1.0; nothing is added to the Python side meanwhile. Either way the end is a version.

CH T7 stands: core loses about 85,000 lines (`charter` 77,725, `charter_runtime` 4,654, `charter_packs` 2,859 [executed]) while the charter system holds about 137,000 Java main lines (M5 E7 [relayed]). The real deletion is the run-time half and about twelve of nineteen concepts (M5 §8 B), and only if the model is reduced on the Java side **before** the switch.

### F7. Missions in flight

**Finding accepted.** A flatten import must merge lanes that mix approved and canceled work and read four topologies, once, without the gate built for those cases. "A few hundred lines" is withdrawn.

| Option | What it is | Cost | Protection |
|---|---|---|---|
| (a) **No import** (recommended default) | A Mission in flight lands on the last release that has `consolidate`, with its full gate. Unfinished work continues as a new 4.0 Mission based on the landed result | No code. Per open Mission: one extra landing, a pinned old CLI, a split Mission identity | Today's gate |
| (b) Bounded import | Import only Missions where every lane holds one work package, or only approved ones; refuse the rest to (a) | Readers for `lanes.json`, the log and the topologies stay until 4.1.0: thousands of lines, not hundreds [inferred] | A fresh `accept` with the listing of F1 |
| (c) Full import | Flatten everything | The consolidation problem, rebuilt | None credible; rejected |

**Open (D8).** Decision-material and unknown: how many users hold Missions in flight across an upgrade. Landed Missions (859 on disk in core, M3 §9 [relayed]) stay as files in history under every option.

## 6. Forks: choice, alternative, what decides

"Independent" marks agreement reached from opposite stances (CH §8).

| Fork | Recommended | Alternative | Decided by |
|---|---|---|---|
| Record location | ref no checkout holds. **Independent** | tracked file on the Mission branch | D1, D2 |
| Record granularity | one ref per repository, one file per Mission (CA): one thing to fetch and push; replay is per file [executed] | one ref per Mission (CB): less contention, more forge branches | push-contention experiment (D16) |
| Unit of isolation | branch per work package. **Independent** | thin lanes (M1 §8 A) | pilot: re-review rate |
| When work integrates | on approval. **Independent** | at acceptance | D3 |
| Landing check | tree equality. **Independent** | the pull request as the only landing (M7 §8 A); loses S2 | settled unless a forge is always present |
| Landing strategy | merge commit with the accepted commit as second parent; squash optional with an `Accepted-Commit` trailer | squash default | D13; squash's reason was bookkeeping commits (S25), gone with R-a |
| States | six, `blocked` as a flag, override as an event. **Independent** | nine | D5, before the record contract is 1.0 |
| Record writer | Python library in process | Java service | D4 |
| Charter delivery | compiled, **committed** bundle (CA); built-ins precompiled in the wheel; charter verbs forward to the charter system (CB) | not committed: every clone needs the charter system | whether a clone must work without it; I assume yes |
| Charter transition | one switch before 4.0.0 (CB) | Python charter until 4.1.0 | D6 |
| Activation | pack list, exclusions, `only:`, opt-in kinds | exclusions alone (**independent**; loses S6) | D7 |
| Step definition in flight | committed `type.lock.yaml` (CB): steps, checks, prompt digests; a changed definition is reported and a human relocks | digest only (CA): the live definition runs meanwhile | settled by S7 |
| Tools | data rows, one ownership manifest (CB). **Independent** on rows | two open formats only | D10, after a desk check against the 17 tools |
| Programmatic contract | API 2.0, about 8 verbs, rendered by `cli` from the same operations (CB) | `--json` everywhere as contract (CA): wider than today's 27 verbs | D11 |
| Acceptance identity | interactive unless a standing delegation is recorded (CB). A terminal check is a recorded act, not proof of a human | asserted actor | D12 |
| Manifest | `wps.yaml` alone says which work packages exist; task files are prose | task-file frontmatter (CA): the #1589 shape (S15) | settled by S15 |
| Protection policy | no component; only `land` writes the target; `--commit-to-target` given up | keep it (CB) | D14 |
| Optional capabilities | C26 kept; C28 untouched; C20, C31 reduced (CB) | CA's drops | D14 |

## 7. The mechanisms in scope (intended target)

| Mechanism | Target design | Deleted with it |
|---|---|---|
| Workspaces | `start WP03` cuts `kitty/<slug>-<mid8>.WP03` from the Mission tip and adds a worktree; `--here` switches the caller's checkout (the owned checkout made general, S22). Overlapping `owned_files` warn at `finalize` and at start. Cleanup deletes a work-package branch only if it is an ancestor of the Mission branch, and a Mission branch only if it is an ancestor of the target or named by an `Accepted-Commit` trailer with an equal tree [executed] | topology and settlement, coordination branch and worktree, PRIMARY/COORD partition and placement seam, lane computation, dependency merges, auto-rebase, `--incorporate`, sparse exclusion, planning pin, lane-tip hooks; about 120 refusal codes (M1 §4) |
| Mission types, step runtime | One format: a descriptor and a folder per step. Step kinds `once`, `per-work-package`, `human-decision`. Checks from a closed, versioned vocabulary; an unknown check fails at compile. `decide` is a function of the lock, the artefacts and the record. Replacing a built-in type needs an explicit `replaces:` (S13) | `mission.yaml` phases, `mission-runtime.yaml`, workflows, run cursor and index, `_GUARD_TABLES` (`src/runtime/next/runtime_bridge_cores.py:859-864`), per-type tables, the copied tree `src/specify_cli/missions/` |
| Lifecycle | States `planned`, `in_progress`, `for_review`, `in_review`, `approved`, `canceled`; landed is a Mission fact. `finalize` commits the manifest and appends one planned event per work package; a manifest entry with no event reads "not finalized", never `planned` (S15). Start is exclusive by compare-and-swap (S16) | sentinel lanes, `claimed`, `done`, the force flag, two write shells, the five-source read door, the frontmatter mirror, committed `status.json` |
| Events | Append is a commit built from objects plus a compare-and-swap, as the events repository accepted (`spec-kitty-events:docs/adr/0007-…-by-ref.md`). Order is append order. The one join rule is replay at `sync`; a row no longer legal is refused and reported (S1) | wall-clock ordering, the lift, seed arbitration, the merge driver; the produce seam, **after** the ref is readable (S17); `canonical-events.jsonl`; hosted vocabulary |
| Charter, packs | F5 and F6. Per type and step one context file within the budget plus one file per fetchable body (S10). The manifest hashes inputs **and** outputs, so a hand edit is detected (CH C18). The organisation floor holds at compile and in a CI check (S21) | context state, six-tier template chain, both resolvers, `selected_*`, three-state lists, cascade, identity index, the daemon on the local path |
| Execution coordination | The operations of section 2. One command per step that declares one; today a fixed tuple (`src/specify_cli/skills/command_installer.py:101-114` [read]). Starting and supervising executors stays outside core | `orchestrator_api` as a second implementation, lifecycle shims, user-global installers, the keyword router, three of four ownership manifests |
| Landing | F1 and section 6. `land` checks: tip equals accepted commit; every approved commit is its ancestor; the target tip is its ancestor; the remote is not ahead. `--dry-run` runs the same checks. Undo is a compare-and-swap back to the tip stored in the landing event (S18). The one exception path is the override event (S9) | claim, gate axes, attribution, windows, approval-stamp bound, attestations, `--dependency-ref`, snapshot and intent records, resume recovery, forecast, teardown, `rebase`; 18 pinned residuals (M7 §5) |
| Upgrade | `schema_version` is the one authority; floor 3.2.x with a pinned stepping stone; one converter; reconcilers for tool files and ignore lines, which also remove old merge-driver lines from `.gitattributes`. No clone-local git configuration remains | 144 migrations, both ledger partitions, 14 `migrate` subcommands, runtime legacy readers in 26 files (M8 §5.2), the empty shim registry |

References in this table are [relayed] unless tagged.

**Core verbs and pack step ids (CH T4).** `start`, `submit`, `verdict`, `accept`, `land` are transitions of the record's state machine, named by the events contract. `implement`, `review`, `accept` as step ids are pack data; a `per-work-package` step declares which transition completes it. The gate for R-e checks comparisons against step, type, kind and tool variables, not text, and starts as a shrink-only count: `software-dev` occurs 156 times in 64 non-migration files (CH §4 [relayed]).

**Merge configuration (S19).** A local merge driver can change an integration merge. What lands is still the accepted tree, and a merge that differs from the recomputed mechanical merge is listed at acceptance: visible, not refused.

## 8. The `cli` package and the corrected size (F4)

`src/specify_cli/cli` is 107,407 lines, 105,766 of them under `commands/` [executed]. Grouped by file name [executed: a pattern script over `commands/`; the grouping is mine and approximate]:

| Family | Lines today | Disposition | Rough target |
| --- | --- | --- | --- |
| `move-task`, status, transitions (24 files) | 17,741 | replace by `act` and `read` renderers | 3,000 |
| charter verbs (37 files) | 17,349 | forward to the charter system | 1,000 |
| doctor family (30 files) | 13,332 | one `doctor` over the stores of section 9 | 3,000 |
| implement, workflow, owned checkout (13) | 10,686 | `start` | 1,500 |
| finalize, planning pin, lanes (14) | 10,296 | validate the manifest, append planned events | 1,500 |
| retrospect, tracker, decisions, dispatch, intake (17) | 8,592 | retain; not assessed in depth | 6,000 |
| upgrade, migrate (10) | 7,383 | reconcile | 1,000 |
| consolidate, accept, review (11) | 6,652 | `verdict`, `accept`, `land` | 2,000 |
| mission create and setup (10) | 5,591 | `mission create` | 2,000 |
| next, init (5) | 4,371 | simplify | 3,000 |
| other, and non-command helpers | 5,414 | retain | 4,000 |
| **Total** | **107,407** |  | **about 28,000** |

The families are large because they hold rules of the subsystems above, for example `agent/tasks_move_task_gates.py` (1,703 lines) and `agent/mission_finalize_planning_pin.py` (1,623) [executed]. The constraint that keeps the target small: a module under `cli` parses arguments, calls one operation and renders; it holds no guard and resolves no path.

Derived end state of core [inferred from executed package counts and the kept shares named in sections 7 and 8]:

| Part | Lines today | After |
|---|---|---|
| consolidation, lanes, coordination, mission_runtime, workspace, status | 99,161 | about 8,000 |
| charter, charter_runtime, charter_packs, charter_pack_synthesizer | 86,558 | about 2,000 (leaves core; a move) |
| runtime, missions, mission_loader, mission_step_contracts, mission_v1 | 25,339 | about 4,000 |
| upgrade, migration, compat | 50,319 | about 3,000 |
| tool_surface, skills, session_presence, shims, orchestrator_api, invocation | 30,850 | about 6,000 |
| review, acceptance, git, core, glossary | 46,568 | about 17,000 (weakest estimate) |
| cli | 107,407 | about 28,000 |
| about 40 packages and top-level modules with **no disposition in any input** | about 79,000 | about 79,000 |
| **Total** | **524,936** | **about 147,000** |

The last row is the limit of this assessment: `retrospective` (8,483), `kernel` (9,179), `specify_cli/runtime` (5,726), top-level modules (9,327), `decisions`, `dossier`, `state`, `tracker`, `audit` and others were not assessed. CA's figure would need a further 100,000 lines of deletions nobody has named.

## 9. State and authority (intended target)

| Store | Where | Authority for | Writer |
|---|---|---|---|
| Mission record | `refs/heads/spec-kitty/record`, `<mission_id>.jsonl`; `ops.jsonl` | work-package state, position, verdicts, decisions, acceptance, landing, Ops | events system |
| Mission definition | `kitty-specs/<slug>/` on the Mission branch | identity, plan, manifest, locked type | core verbs and authors |
| Code | Mission, work-package and target branches | content | git |
| Activation | `.kittify/charter/activation.yaml` | what is in force | charter system verbs |
| Bundle | `.kittify/charter/bundle/` (derived, committed, hashed) | nothing; a view | charter system |
| Project config | `.kittify/config.yaml` | tools, sync mode, landing strategy | core verbs |
| Generated tool files and one manifest | tool directories | nothing; a view | reconciler |
| Shape version | `.kittify/metadata.yaml` | supported shape | upgrade |

Eight stores against 62 registered surfaces today (M3 §4 [relayed]). Clone-local: git's worktree registry, and events not yet shared, counted on every command. No file export is written: CB's `history.md` would be a second store and move the tip after acceptance (CH C24). Observers without the CLI read JSONL on the forge: a stated loss (J10).

## 10. Steelman items

| Item | Outcome | By what, or at what cost |
|---|---|---|
| S1 two clones, one Mission | kept by other means | replay at `sync`; F1 for the code branch |
| S2 landing without a forge | kept as is | `land` moves the target locally |
| S3 mixed lanes | kept by other means | one branch per work package |
| S4 test-origin probe | kept as is, smaller | F5 |
| S5 native files for twelve tools | kept by other means, **unproven** | rows; a tool that fails the desk check keeps a renderer or is dropped by ruling (D10) |
| S6 narrowing; skills default | kept by other means; kept as is | F5 |
| S7 frozen step definition | kept by other means | `type.lock.yaml` |
| S8 unabsorbed branches | kept by other means | ancestry rule at cleanup; a merge landing makes `git branch -d` agree |
| S9 attestations | kept by other means | the override event |
| S13 reserved built-in keys | kept by other means | explicit `replaces:` |
| S14 Python step guards | kept in transition | side by side for one release candidate |
| S15 sentinel states | kept by other means | one manifest; "not finalized" is a Mission condition |
| S17 produce seam | **given up** | consumers read the ref; registrants preserved in `event-router` (11 files, CH) become readers |
| S19 merge-attribute guard | **given up** | visible at acceptance, not refused |
| S11 keyword heuristic | **given up** | a warning replaces avoidance; conflicts cost a second review |
| Per-line proof that canceled content is absent | **given up** | a canceled, integrated work package needs a revert, which the listing shows |

## 11. Target, current, transitional, legacy

**Intended target:** sections 2 to 9.

**Current implementation:** described in `01` to `03` and M1 to M8.

**Transitional arrangements, each with its end:**

| Arrangement | Why | End condition |
|---|---|---|
| Local-file adapter behind the event port | until the record ref is written | the release that writes the ref for new Missions |
| Old and new Mission shape side by side, chosen by the Mission's format field | development on the release-candidate line | no general release ships both; ends at 4.0.0 |
| Declarative and Python step guards evaluated together | equivalence before deletion (S14) | one release candidate |
| Python charter behind `charter.offering.api` | until the bundle switch | before 4.0.0; or 4.1.0 by ruling D6 |
| Present command names and API 1.x verbs as aliases | users and two clients update once | removed in 4.1.0 |
| Stepping stone through a pinned 3.2.x CLI | projects below the floor | no code in core; the pin stays installable |
| Bounded import, only if D8 chooses option (b) | Missions in flight | removed in 4.1.0 |

**Legacy that can be retired without an arrangement:** the copied missions tree, the frontmatter lane mirror, `mission-events.jsonl`, committed `status.json`, `canonical-events.jsonl`, the empty shim registry with its doctor and gates, the second resolver, workflows, the `rebase` strategy, the `lanes` and `coord` topologies, legacy activation keys, the second consolidation executor in the orchestrator API (S23 to S35 [relayed]).

**Order constraints for the roadmap.** (1) Legacy retirement and the Mission value object need no ruling. (2) Built-in types as data, then the state reduction and the guards behind `append`, while the record is still a file. (3) The record on the ref with `sync`, after D1 and D2. (4) Work-package branches, integration and `land` together, deleting lanes, coordination and consolidation in one step, after D3; API 2.0 with it. (5) The charter switch. (6) Tools as data. (7) The baseline cut. Step 3 is the unlock: while status is a tracked file none of the later steps can delete what it replaces (M1 §10 [relayed]).

## 12. Breaking changes as trade-offs (R16)

| Change | Consequence | Consumers and data | Migration and cost |
|---|---|---|---|
| Record on a ref, one envelope, six states | `status.events.jsonl`, `status.json` no longer written; `claimed`, `done` vanish | every project; `fleet-kitty`; `spec-kitty-planning` (18 files name the log); hosted dossier; read-service resolver; orchestrator scheduler; 12 pack prompts | landed Missions stay as text; one name map; one update per consumer |
| Lanes, topologies, coordination branch removed | `lanes.json`, `--topology`, lane ids go | Missions in flight; orchestrator `workspace_path`; events contracts `Topology.yaml`, `WriteSurface.yaml` (below 1.0) | D8 |
| Integration on approval; tree-equality landing | approved work is on the Mission branch early; a late cancel is a revert; attestations, `--dependency-ref` and 22 flags go | operators; step prompts; two recovery guides | no data migration; docs rewritten |
| Guards behind every door | transitions that pass today may refuse, the pre-review gate included | `spec-kitty-orchestrator`, which calls `transition` without command guards | one client update, with API 2.0 |
| API 2.0 | 27 verbs become about 8 | `spec-kitty-orchestrator` (already calls an unregistered verb, `…/host/client.py:399`); `spec-kitty-mcp` | aliases until 4.1.0 |
| Activation model | `charter.yaml` selections and legacy keys ignored | every project with a charter; org packs | one converter; it writes `only:` where a project had narrowed |
| One mission-type format | custom `mission.yaml` and workflows stop loading | projects with `.kittify/missions/<key>/`; org packs; pack composer | a converter in the charter system |
| Tools as rows; no user-global installs | tool-specific features may go | users of 17 tools; a user's other projects on an older CLI lose global commands | reconcile removes what it owns; the other-project effect is not solved, only announced |
| Floor 3.2.x; `migrate` removed | two commands for older projects | users below 3.2; 4 open-packs prompts | pinned stepping stone |
| Record pushed by the tool | a branch `spec-kitty/record` on the forge | every team; forge branch rules | D2 |

Consumers are relayed from CH and `A/challenge/steelman.md` §6.

## 13. What this design is worse at, and the principles

Worse at: conflict avoidance by construction; cancelling after approval; proof against a dishonest agent (identities stay asserted); bespoke per-tool features; one-command upgrade from old versions; visibility of the live record in the target tree.

| Principle (R8) | Effect |
|---|---|
| Human in Charge | Stronger at `accept` (interactive, delegation recorded, unreviewed commits named). A pin bump cannot widen a narrowed rule set |
| Responsible delegation | Changed: an agent's approval moves the Mission branch. Bounded by `accept`; D3 |
| Explicit responsibility ownership | Per-line authorship proof given up; every verdict, acceptance, override and landing names an actor and a commit |
| Independent evolvability | Three contracts: record, bundle, API 2.0. A guard change needs an events release and a lock refresh in core; that is the price of one owner |
| Governed coordination | Same guards behind every door |

**Experiments run** [executed]: two-clone integration and merge join; conflicting join; listing of commits outside approved ranges; record append by plumbing, plain and explicit push, refused push and replay; merge landing with `git branch -d`; squash landing with trailer and tree equality; stale compare-and-swap. **Not checked:** the state-machine re-check on replay; push contention; the row schema against any tool; the Java guards rule by rule.

**What would change the recommendation.** A documented journey that needs the live record in the target tree (a partition survives). A pilot in which most Missions need a second review after integration (thin lanes; about 20,000 lines of consolidation stay). A 4.0 requirement for a non-Python writer (the Java service). A ruling against any push by the tool (choice 1 stands only with `manual` sync).
