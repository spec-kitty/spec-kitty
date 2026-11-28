---
doc_status: draft
updated: '2026-11-28'
---

# Capability dispositions

Consolidator K2, profile `architect-alphonso`; the architect decides. This file gives one disposition per capability and per mechanism for the candidate in `04-candidate-architecture.md`. The full row for each item (evidence, expected benefit, migration obstacles, risks, both kinds of uncertainty, the three views, what is deleted) is in `06-capability-dispositions.csv`; the tables here carry the columns a reader decides with. Evidence tags as in `04`: [read], [executed], [relayed], [inferred].

## 1. Conclusion

No capability rated core or important is removed. Of 32 capabilities, 28 are retained, 3 simplified and 1 left for investigation. The cut is in the mechanisms: of 59, 19 are removed, 12 replaced, 9 consolidated, 9 simplified, 5 retained and 5 need investigation or a ruling first.

Three limits. The dispositions of the workspace, lifecycle, event and landing mechanisms hold **as a set**: none can be applied alone, because each compensates for another (M1 §7, M7 §1 [relayed]). Sixteen decisions belong to the architect (section 2); D1 to D3 gate the largest deletions. About 79,000 lines of core have no assessor and so no disposition (X.3).

A disposition describes the **present mechanism**: `remove` and `replace` mean it is legacy once its roadmap step is done; what replaces it is the intended target in `04`. Transitional arrangements and their ends are in `04` section 11.

## 2. Decisions the dispositions depend on

| Id | Decision for the architect | Dispositions that wait for it | Default assumed here |
|---|---|---|---|
| D1 | May the live record leave the target tree, onto a ref | M1.1 to M1.3, M1.6, M3.3, M3.4, M4.1 | yes |
| D2 | May the tool push the record and the commits its events name; default `sync` mode | M4.1, M4.2, C32 | yes, `auto` |
| D3 | Integration on approval (an agent's approval moves the Mission branch), or at acceptance | M1.4, M1.5, M7.1 | on approval |
| D4 | Record writer for 4.0: Python library in process, or the Java service | M3.2, M4.4, M7.7 | library |
| D5 | Reduce to six states before the record contract reaches 1.0 | M3.1 | yes |
| D6 | Does 4.0.0 wait for the charter system's compile, or ship with the Python charter until 4.1.0 | M5.1, M5.5 | wait |
| D7 | Is exclusion the only narrowing, or also `only:` per pack and opt-in kinds | M5.2, M5.6 | also `only:` and opt-in |
| D8 | Missions in flight: land on the old CLI, or a bounded import until 4.1.0 | M8.6, M1.1, M7.1 | no import |
| D9 | Upgrade floor (proposed 3.2.x) and removal of `migrate` | M8.1 to M8.3 | 3.2.x |
| D10 | Is the list of 17 tools a commitment; which tool-specific features stay | M6.3, M6.4, C02 | rows; features by desk check |
| D11 | API 2.0 of about 8 verbs, breaking both known clients once | M6.2 | yes |
| D12 | Acceptance: interactive unless a standing delegation is recorded, or an asserted actor | C10 | interactive |
| D13 | Default landing strategy: merge commit, or squash | M7.6, M1.8 | merge |
| D14 | Optional capabilities C20, C26, C28, C31, and `--commit-to-target` | M1.11, M5.7 | C26, C28 kept; C20, C31 reduced; flag given up |
| D15 | Supersede as sets, not amend: the consolidation, topology, coordination and migration-ledger ADRs | all of M1, M7, M8 | supersede |
| D16 | Record granularity: one ref per repository, or one per Mission | M4.1 | per repository, after the contention experiment |

## 3. Capabilities

| Id | Capability | Disposition | How it is carried in the target; what changes | Confidence | Decision |
|---|---|---|---|---|---|
| C01 | Bring a repository under Spec Kitty and verify the setup | retain | Core need; carrier becomes reconcile (init) and one doctor (M8.5) | high |  |
| C02 | Workflow inside the agent tool the user already has | retain | Core need; carrier M6.3 (data rows). Tool-specific features decided per feature | medium | D10 |
| C03 | Interview to an agreed specification | retain | Core need; questions and answers become record events | high |  |
| C04 | Plan and bounded work packages with dependencies | retain | Core need; one manifest (M3.5) | high |  |
| C05 | Ask what to do next; resume | retain | Core need; carrier M2.3 (stateless decide over a lock) | medium-high |  |
| C06 | State recorded with who, when, why | retain | Core need; carrier M4.1 (record on a ref) | medium | D1, D2 |
| C07 | Several agents work at once without overwriting | retain | Core need; carrier M1.4 (branch per work package) | medium | D3 |
| C08 | Dependent work starts from its predecessor's result | retain | A dependent is cut from the Mission tip, which holds approved predecessors | medium | D3 |
| C09 | Review by someone other than the author | retain | Core need; verdict event names a commit; independence guard in the events system | medium-high | D4 |
| C10 | A human accepts the Mission as a whole | retain | Strengthened: acceptance names the tip, is interactive unless delegated, lists unreviewed commits | medium | D12 |
| C11 | Only reviewed work lands; preview, resume, undo | retain | Carrier M7.1 (tree equality). Guarantee becomes: a human accepted the tip with unreviewed commits named | medium | D3, D13 |
| C12 | Target stays clean; target chosen deliberately | retain | Only land writes the target. --commit-to-target is given up | medium | D14 |
| C13 | Interrupted work is recoverable | retain | Every operation is one compare-and-swap or one ordinary git command; re-run is resume | medium-high |  |
| C14 | Other kinds of work have their own steps and gates | retain | Carrier M2.1 (one format, built-ins as data) | medium-high |  |
| C15 | New kind of work without changing the CLI | retain | Made true: built-ins use the extension path | medium-high |  |
| C16 | Rules stated once, applied at every step | retain | Carrier M5.1 (compiled, committed bundle) | medium | D6 |
| C17 | Choose which rules apply | retain | Reduced: pack list, exclusions, only: per pack, opt-in kinds. Cascade goes | medium | D7 |
| C18 | Organisation floor a project cannot remove | retain | Enforced at compile and by a CI check | medium |  |
| C19 | An agent takes a defined role | retain | Profiles are bundle files | medium-high |  |
| C20 | Consistent terms | simplify | Optional need; glossary as pack content and an authoring lint | low | D14 |
| C21 | Short governed task with a trace, no Mission | retain | dispatch = bundle context plus events in ops.jsonl; router removed | medium |  |
| C22 | Outside program drives a Mission through a versioned contract | retain | Carrier M6.2 (API 2.0, about 8 verbs, a rendering of the same operations) | medium | D11 |
| C23 | Unattended to a human decision point | retain | decide returns wait at a human-decision step; supervision stays outside core | medium-high |  |
| C24 | Progress visible without reading source | retain | read folds the record; no file export | medium | D1 |
| C25 | Other systems consume lifecycle events | retain | Speculative; the record ref is the publication surface; in-process seam removed | low |  |
| C26 | Learning loop under human approval | retain | Rated important with journeys J2, J5; CA's reduction rested on a false premise | low | D14 |
| C27 | Upgrade without losing work in flight | simplify | Reconcile plus floor; Missions in flight by D8 | medium | D8, D9 |
| C28 | Start from and report to an issue tracker | investigate further | Optional; not assessed; left untouched | low | D14 |
| C29 | Diagnose and repair a broken setup | retain | One doctor over eight stores | medium |  |
| C30 | Several Missions in flight | retain | mission_id and one Mission value object | high |  |
| C31 | Close, reopen, follow up, archive | simplify | No journey found; close and archive as events; reopen is a new Mission citing the old | low | D14 |
| C32 | Share Mission state through ordinary git | retain | Record ref and branches travel by sync; no hidden local-only authority because unshared events are counted and gated | medium | D2, D3 |

## 4. Mechanisms

### Workspaces for parallel work

| Id | Mechanism | Disposition | Rationale | Expected benefit | Confidence | Decision |
|---|---|---|---|---|---|---|
| M1.1 | Topology grid: four kinds, source, settlement | **remove** | Exists because status is a tracked file on code branches; nothing left to decide once it is not | with M1.2, M1.3: about 22,000 lines and 60 to 80 refusal codes [inferred] | medium-high | D1, D8 |
| M1.2 | Coordination branch, worktree, seed and restore | **remove** | A second copy for status writes; no cause once the record is on a ref | src/specify_cli/coordination 15,036 lines [executed] | high | D1 |
| M1.3 | PRIMARY/COORD partition and placement seam | **remove** | No artefact kind needs a surface decision when status is off the tree | src/mission_runtime 6,868 lines [executed] | medium-high | D1 |
| M1.4 | Execution lanes and lane computation | **replace** | One branch per work package; owned_files overlap warns at finalize and start | about 14,000 of 16,574 lines in lanes/ [inferred] | medium | D3 |
| M1.5 | Lane dependency merge, auto-rebase, --incorporate | **remove** | A dependent is cut from the Mission tip | included in M1.4 | medium | D3 |
| M1.6 | Sparse status exclusion, lane write guard, planning-commit pin | **remove** | Compensate for status being a tracked file in the lane's tree | included in M1.4; cli finalize family 10,296 lines [executed] | medium-high | D1 |
| M1.7 | Worktree allocation and cleanup | **simplify** | Kept small: git worktree add, or --here; cleanup by ancestry rule | most of worktree_allocator, recovery, workspace/context | medium |  |
| M1.8 | Lane work tips and recorder hooks | **replace** | One rule: never delete a branch whose commits the Mission branch (or the landing) lacks | hooks, refs, two refusal codes | medium | D13 |
| M1.9 | Lane test-origin probe | **retain** | Tests in a checkout can load code from another; more exposure with a worktree per work package | none; moves to workspaces | medium-high |  |
| M1.10 | Owned checkout as a mode | **consolidate** | Becomes the general --here case | one mode fewer | medium |  |
| M1.11 | Protection policy and --commit-to-target | **remove** | Only land writes the target; the record ref is never a protected code branch | policy/ about 2,000 lines [executed] | medium-low | D14 |

### Mission types and the step runtime

| Id | Mechanism | Disposition | Rationale | Expected benefit | Confidence | Decision |
|---|---|---|---|---|---|---|
| M2.1 | Mission-type definition: five generations of format | **consolidate** | One format; built-ins authored in it | 4,000 to 6,000 lines and five concepts [inferred M2] | medium-high |  |
| M2.2 | Per-type Python tables (guards, profiles, grammar, capabilities) | **replace** | Closed, versioned check vocabulary in the type definition | removes the architect's own example | medium |  |
| M2.3 | Step engine with run cursor and run index | **replace** | decide is a function of the lock, artefacts and record | most of src/runtime 17,627 lines [executed] | medium |  |
| M2.4 | Frozen template per run | **replace** | type.lock.yaml committed per Mission; a human relocks | definition visible in the Mission folder | medium |  |
| M2.5 | RESERVED_BUILTIN_KEYS | **replace** | Replacing a built-in type is an explicit replaces: in the activation | built-ins and custom types share one path | medium |  |
| M2.6 | RACI and significance scoring | **investigate further** | No reason found; the human-decision step kind covers the one known use | small | low |  |
| M2.7 | Fixed command tuple matching software-dev | **replace** | One generated command per step that declares one | research and custom steps get commands | high |  |

### Mission and work-package lifecycle

| Id | Mechanism | Disposition | Rationale | Expected benefit | Confidence | Decision |
|---|---|---|---|---|---|---|
| M3.1 | Nine lanes, two sentinels, force flag | **simplify** | Six states, blocked as a flag, override as its own event | no re-reading of history to tell forced from reviewed | medium-high | D5 |
| M3.2 | Three implementations of the state machine | **consolidate** | One, in the events system, inside append | one owner for five duplicated rules | medium | D4 |
| M3.3 | Seventeen status stores | **consolidate** | One record per Mission | 62 registered surfaces to 8 | medium-high | D1 |
| M3.4 | Two write shells and the five-source read door | **remove** | Exist because the log's location depends on topology | most of status/ 21,397 lines [executed] | medium-high | D1 |
| M3.5 | Work-package manifest sources | **consolidate** | wps.yaml alone; finalize appends planned events; no sentinel state | one source of existence and dependencies | medium |  |

### Event handling

| Id | Mechanism | Disposition | Rationale | Expected benefit | Confidence | Decision |
|---|---|---|---|---|---|---|
| M4.1 | Status log as a tracked file | **replace** | Record on refs/heads/spec-kitty/record, written by compare-and-swap, never checked out | unlocks M1, M3, M7 deletions | medium | D1, D2, D16 |
| M4.2 | Wall-clock ordering, lift, arbitration, merge driver | **remove** | Order is append order; the one join rule is replay at sync | the ordering residuals (#4941 class) lose their cause | medium | D2 |
| M4.3 | Produce seam status/adapters.py | **remove** | No registrant in core; removed after the ref is readable | an indirection with nothing behind it | medium |  |
| M4.4 | Java write service on the CLI path | **investigate further** | Recommended off the per-command path for 4.0; it has three of four guards and is the alternative writer | no launcher, pin or native matrix on the write path | medium-low | D4 |
| M4.5 | Java read service | **retain** | Unchanged: pinned for CI conformance, not launched by the CLI; becomes a reader of the ref when a consumer exists | none | low |  |
| M4.6 | Hosted vocabulary and canonical-events.jsonl | **remove** | No reader in core | small | medium-high |  |

### Charter and packs

| Id | Mechanism | Disposition | Rationale | Expected benefit | Confidence | Decision |
|---|---|---|---|---|---|---|
| M5.1 | Python charter in core | **replace** | Core reads a compiled, committed bundle; one switch before 4.0.0 | about 85,000 lines leave core (a move); run-time half deleted | medium | D6 |
| M5.2 | Activation model: selected lists, three-state, per-kind defaults, cascade, identity index | **simplify** | Pack list, exclusions, only: per pack, opt-in kinds | about twelve of nineteen concepts [inferred M5] | medium | D7 |
| M5.3 | Six-tier template chain and two resolvers | **consolidate** | One precedence order, in the charter system | one layering mechanism | medium |  |
| M5.4 | Context state (first-load mode) | **remove** | Delivery must not depend on checkout state; compiled per-step files within the budget | same text in every checkout | medium-high |  |
| M5.5 | Per-worktree charter daemon and run-time graph | **remove** | Rules change at pin or activation changes, not per step | no resident process locally | medium | D6 |
| M5.6 | Pack skills default (required-only when absent) | **retain** | A registered pack must not add commands to every tool | none | medium | D7 |
| M5.7 | Glossary pipeline | **simplify** | Pack content plus an authoring lint (C20) | src/glossary 6,383 lines [executed] | low | D14 |

### Execution coordination and agent tools

| Id | Mechanism | Disposition | Rationale | Expected benefit | Confidence | Decision |
|---|---|---|---|---|---|---|
| M6.1 | Seven doors to drive work forward | **consolidate** | Operations decide, act, read, sync; every door renders them | one model of progress | medium-high |  |
| M6.2 | orchestrator_api package (27 verbs, parallel claim, second executor) | **replace** | API 2.0 as a rendering of the same operations | 5,855 lines [executed]; guards identical for every driver | medium | D11 |
| M6.3 | Per-tool tables, renderers and providers | **simplify** | Tools as data rows; one ownership manifest | most of tool_surface and skills, 17,229 lines [executed] | medium-low | D10 |
| M6.4 | User-global installs, session presence, hooks, plugin bundles | **investigate further** | Go unless the desk check shows a tool needs one; decided per feature | about 30 agent-copy migrations lose their reason | low | D10 |
| M6.5 | Dispatch keyword router; Op lifecycle files | **remove** | dispatch asks for a profile or takes one; an Op is events in ops.jsonl | part of invocation/ 5,367 lines [executed] | medium |  |

### Landing (consolidation) and approval evidence

| Id | Mechanism | Disposition | Rationale | Expected benefit | Confidence | Decision |
|---|---|---|---|---|---|---|
| M7.1 | Claim, gate axes, attribution, windows, approval-stamp bound | **replace** | Approval names a commit; landing is tree equality; acceptance lists unreviewed commits | about 30,000 of 36,414 lines; 60 refusal codes; 18 pinned residuals | medium | D3, D8 |
| M7.2 | Operator attestations and --dependency-ref | **replace** | One override event with actor and reason | five attestation families to one event | medium |  |
| M7.3 | Rollback authority, run record, resume recovery | **remove** | Landing is one compare-and-swap; undo is a swap back to the stored tip | no multi-phase mutation | medium-high |  |
| M7.4 | Origin-freshness gate | **retain** | Small and needed; extended to the record ref | none | high | D2 |
| M7.5 | Merge-attribute guard | **remove** | Given up: a non-mechanical merge is listed at acceptance instead of refused | small | low |  |
| M7.6 | Landing strategies squash, merge, rebase | **simplify** | Merge commit default; squash optional with an Accepted-Commit trailer; rebase removed | git branch -d agrees with the landing | medium | D13 |
| M7.7 | Owned-file evidence and review independence axis | **consolidate** | Independence is one guard in the events system; implementation evidence is a non-empty approved range | four evaluation sites to one | medium | D4 |
| M7.8 | Pre-review gate (scoped test run) | **retain** | A separate concern from landing proof | none | medium |  |
| M7.9 | Retention policy and cleanup | **simplify** | Cleanup by the ancestry rule; retention as one flag | small | medium |  |

### Upgrade and compatibility

| Id | Mechanism | Disposition | Rationale | Expected benefit | Confidence | Decision |
|---|---|---|---|---|---|---|
| M8.1 | Migration registry, ledger partitions, order manifest, supersession | **remove** | Baseline cut: floor, one converter, reconcilers | upgrade 33,155 and migration 12,003 lines [executed], mostly | medium | D9 |
| M8.2 | migrate command family (14 subcommands) | **remove** | Backfills are part of the one converter | cli upgrade family 7,383 lines [executed], mostly | medium | D9 |
| M8.3 | Runtime legacy readers and unmigrated fallbacks | **remove** | schema_version becomes the one authority | old states stop pinning topology, naming and activation | medium-high | D9 |
| M8.4 | Empty shim registry, its doctor and gates | **remove** | No reason found | small; available now | high |  |
| M8.5 | Doctor family (25 subcommands) | **simplify** | One doctor over the stores that still exist | about 10,000 lines [inferred] | medium |  |
| M8.6 | Import of Missions in flight | **investigate further** | Default: none, land on the old CLI. A bounded import costs thousands of lines until 4.1.0 | none; a cost | medium-low | D8 |

### Cross-cutting

| Id | Mechanism | Disposition | Rationale | Expected benefit | Confidence | Decision |
|---|---|---|---|---|---|---|
| X.1 | The cli package (107,407 lines) | **simplify** | Modules parse, call one operation, render; no guard, no path resolution | about 79,000 lines [inferred] | medium-low |  |
| X.2 | Mission identity and handle resolution | **consolidate** | mission_id stays; about 97 resolvers become one Mission value object | one object per invocation | medium-high |  |
| X.3 | About 79,000 lines in about 40 packages with no assessor | **investigate further** | No input gives a disposition (retrospective, kernel, specify_cli/runtime, decisions, dossier, state, tracker, audit and others) | unknown | low |  |

## 5. Where assessor, steelman and challenge differ

Rows where at least two of the three views disagree with each other or with the disposition here. "Here" is the disposition chosen and the reason.

| Id | Assessor | Steelman | Challenge | Here |
|---|---|---|---|---|
| C02 | M6: two open formats only | S5: holds, proposal loses it | minor: row schema unproven | retain through data rows; the desk check comes before any tool loses native files |
| C07 | M1 A (lanes kept); M1 C as comparison | S3, S11 | note | branch per work package; lanes are the fallback if the pilot shows frequent re-review |
| C11 | M7 B | S2, S9, S18 | major, argued | retain with a weaker, stated guarantee and a listing at acceptance |
| C17 | M5 B: exclusions only | S6 holds | major (F5) | retain narrowing by `only:` and opt-in kinds |
| C26 | CA reduced; CB kept | none | CA premise false | retain; the reduction had no basis |
| M1.4 | simplify (M1 A keeps lanes; C held as comparison) | S3, S11 | independent agreement of CA and CB on a branch per work package | replace; both candidates chose it independently |
| M1.9 | M1 B deletes | S4 holds | F5: lost in silence by both | retain; deleting it was an oversight in both candidates |
| M1.8 | simplify or give up | S8 kept by other means | minor: git branch -d refuses after squash | replace by the ancestry rule; merge landing by default |
| M2.4 | M2 B digest | S7 holds | CB answers it; CA does not freeze | replace by a committed lock (CB) |
| M3.2 | consolidate | none | F3 | consolidate in the events Python package; D4 open |
| M4.2 | delete, do not port | S1 holds; S20 | S1 answered for the record | remove; replay at `sync` is the join rule; the code branch joins by merge (04, F1) |
| M4.4 | M4 A (service) recommended; M4 B (library) cheapest | none | F3: major for CA | off the per-command path for 4.0; D4 open |
| M5.2 | simplify (exclusions only) | S6 holds; S30 no longer holds | F5 | simplify, keeping `only:` |
| M6.3 | two open formats (M6 B) | S5 holds | partly: not already declarative | simplify to rows; schema to be proven |
| M7.1 | replace | S3 holds | C11 major, argued | replace; per-line proof given up knowingly |
| M7.6 | B: fast-forward or squash | S25 no longer holds | S8: branch -d refuses after squash | simplify; merge default |
| M8.6 | M7: flatten command | none | F7 | no import by default; D8 open |
| X.1 | none (no assessor covered it) | none | F4 | simplify; table in 04 section 8 |

## 6. Uncertainty

**Decision-material** (a ruling or a fact about users changes the disposition):

| Uncertainty | Changes | Decision |
|---|---|---|
| Does any documented journey need the live record in the target tree | M1.1 to M1.3, M4.1: a partition survives | D1 |
| May the tool push | M4.1, C32: without it sharing rests on a manual `sync` and a visible count | D2 |
| How often integration conflicts force a second review | M1.4, M7.1: thin lanes return, about 20,000 lines of consolidation stay | D3 |
| Is a writer other than the Python CLI a 4.0 requirement | M3.2, M4.4 | D4 |
| How many users hold Missions in flight across an upgrade | M8.6 | D8 |
| Who outside these clones reads the on-disk log | M4.1 migration cost | D1 |
| Is the supported-tool list a commitment | M6.3, M6.4 | D10 |

**Settle by experiment** (safe, reversible, no ruling needed):

| Experiment | Settles | State |
|---|---|---|
| Two clones integrate and join the Mission branch | F1: recorded commits survive a merge join | done [executed], `04` section 5 |
| Append, push, refused push and replay of the record ref | F2: mechanics of the ref | done mechanically [executed]; replay through the state machine not built |
| Push contention on one record ref with several Missions | D16 | open |
| Rule-by-rule comparison of the Java guards with core's | size of the move in D4; the missing independence guard | open |
| Desk check of the row schema against the 17 tools | M6.3, C02 | open |
| Declarative checks beside the Python guards for one release candidate | M2.2 | open; a transitional arrangement with that end |
| Pilot Mission on work-package branches, counting re-reviews | D3 | open |
| A disposition of `cli` by reading, and a pass over the unassessed packages | X.1, X.3; the size of the roadmap | open |

## 7. Confidence and what would change it

High where the reason for a mechanism has gone and nobody defends it (M1.2, M8.4, M2.7). Medium where the disposition depends on D1 to D3. Low where no assessor looked (X.3, C26, C28) or a count stands in for a reading (X.1). A documented need for the record in the target tree, or a pilot showing frequent re-review, would move M1.1 to M1.6 and M7.1 from remove or replace to simplify.
