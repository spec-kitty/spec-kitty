---
doc_status: draft
updated: '2026-11-28'
---

# 3. Catalogue of semantic duplication and competing mechanisms

Consolidator K1, profile `synthesizer-sam`. This catalogue merges the cross-cutting hunt (`duplication/`, X1) with section 6 of each mechanism assessment (M1 to M8), removes repeats, groups by pattern and ranks by cost. It describes the **current implementation**. Each case keeps its source reference; "K1" marks what I re-read or measured at head. Corrections from the challenge's reference checks (CH) are applied and marked. Code references are to core unless a repository is named. Counts are pointers (R15). The same 74 cases, one row each with label and steelman verdict, are in `03-duplication-and-competing-mechanisms.csv`.

## Conclusion

1. **One shape repeats in every mechanism.** A generic, declared mechanism exists. Beside it runs the older one it was meant to replace. The older one still decides on the common path; the generic one decides only for cases the older one does not know (X1, conclusion). So the main path never exercises the extension mechanism, and every rule has two homes.
2. **Ten patterns cover the 74 cases.** Ranked by cost, the first two account for most of the lines: compensation for the interaction of the tool's own git surfaces, and one rule implemented in parallel in two languages.
3. **The most dangerous pattern is not the largest.** Entry points that enforce different rule sets (pattern 4) are small in lines, but they make the guarantee depend on the door used. The public machine interface lands a Mission "with no claim and no gate behind it (and no rollback)" (`orchestrator_api/consolidation.py:586` [read K1]).
4. **Not every duplicate is accidental.** The steelman found a live reason behind seven mechanisms proposed for removal (ST section 2). Those cases are marked "contested" and are not to be read as free deletions.

## 1. The patterns, ranked by cost

Cost weighs three things: lines implicated, exposure to defects, and whether more than one repository must move together.

| Rank | Pattern | Cases | Scale (pointer) | Removed by |
|---|---|---|---|---|
| 1 | Compensation for the interaction of the tool's own git surfaces | 9 | five packages, 96,289 lines (CH CA01); about 70 refusal codes in three families (X1 class 5) | status off the code branches; one branch model |
| 2 | One rule implemented in parallel, across languages or repositories | 7 | charter 77,725 Python and about 137,000 Java; state machine 3 to 5 times; fold 4 times | finishing or cancelling each move |
| 3 | Built-in types and tools bypass the extension mechanism | 10 | 1,000 to 6,000 lines; 156 `software-dev` literals in 64 non-migration files (CH CB12) | built-ins declared as data |
| 4 | Entry points that enforce different rule sets | 7 | 2 landing executors; guards at 3 levels; 6 context paths | one operation behind every door |
| 5 | Several stores for one fact | 9 | 17 lifecycle stores; 62 registered state surfaces | one authority per fact |
| 6 | Unfinished extraction kept in parallel | 6 | 14 lazy re-export modules; 20-file `tasks*.py` | completing each split |
| 7 | A domain rule restated at call sites | 7 | about 22 target-branch resolvers; 34 "approved or done" | a Mission value and lane predicates |
| 8 | Transitional arrangements with no end; legacy readers in run-time code | 6 | "legacy" in 460 of 1,335 non-migration files (X1) | an upgrade floor |
| 9 | Indirection with nothing behind it | 7 | small each | deletion |
| 10 | Vocabulary and parameter redundancy | 6 | 9 JSON keys for branch facts; 62 `SPEC_KITTY_*` variables | one vocabulary |

## 2. Pattern 1: compensation for git-surface interaction

A mechanism exists to detect, refuse or repair a bad state that another mechanism of the tool can produce. Most codes in these families name two mechanisms at once (`LANES_PROTECTED_TARGET_REFUSED`, `COORD_MOVED_AFTER_LANDING`, `STATUS_WRITE_TARGETS_LANE_CHECKOUT`).

| Id | Compensator | Compensates for | Evidence |
|---|---|---|---|
| D1.1 | PRIMARY/COORD partition and five-layer placement seam, over 23 artefact kinds | status and planning on different branches; degenerate on the default path, where both are one branch | M1 5.1 (E16, E23, E24) |
| D1.2 | Coordination worktree: seed, restore, coherence, teardown; five refusal codes of its own | a second copy of the status branch that can be wrong | M1 5.2 (E22, E25); ST S23 agrees the reason is gone |
| D1.3 | Sparse exclusion of status in lane checkouts, write guard, clone-local migration | status is a tracked file in the tree lanes are cut from | M1 5.4 (E28) |
| D1.4 | Planning-commit pin, orphan classes, patch-id follow | the partition separated two histories | M1 5.3 (E26, E27); `cli/commands/agent/mission_finalize_planning_pin.py`, 1,623 lines [executed K1] |
| D1.5 | Two status write shells, five read sources, merge driver, status-surface divergence guard | the log is a file on a topology-dependent branch | M3 section 7; X1 3.3; `status/emit.py:882`, `coordination/status_transition.py:1626` |
| D1.6 | Six gate axes, work-package attribution, windows, line attribution, attestations | several work packages on one lane; squash; approval as an event on a moving branch | M7 section 5. **Contested:** essential while a lane holds more than one unit of review (ST S3) |
| D1.7 | Snapshot, intents, unsettled refs, resume recovery, teardown gate, late projection | fifteen phases moving up to three branches; a second status branch | M7 section 5; `consolidation/rollback.py` 1,380 lines |
| D1.8 | Wall-clock ordering, approved-departure lift, seed arbitration | rows appended on several branches and joined by git | M4 5.4. **Contested:** the two-clone scenario is recorded and survives any git-shared record (ST S1) |
| D1.9 | Run-cursor reconcile phases in `next`: never-rewind gate, finalized-board override | a clone-local cursor beside the committed board | M6 5.1 (E21, E22) |

Refusal families, by what they protect against (X1 class 5; 374 refusal-style literals in non-migration source):

| Family | About | Protects against | Essential? |
|---|---|---|---|
| `COORD_*`, `COORDINATION_*`, `PROJECTION_TEARDOWN_ABORTED` | 22 | a second branch and worktree for status | no |
| `LANE_*`, `DESTROYED_LANE`, `WORKTREE_*`, `INCORPORATE_*` | 25 | lane branches deleted, stale or conflicting | partly: losing committed work is a real risk (ST S8) |
| `WRITE_CHECKOUT_*`, `SINGLE_BRANCH_*`, `OWNED_*`, `TOPOLOGY_SETTLEMENT_REFUSED` | 25 | four topologies meeting protected branches and shared checkouts | mostly no |
| `LANE_MOVED_AFTER_APPROVAL`, `APPROVAL_STAMP_*`, `CANCELED_*` | not counted | unreviewed content between approval and landing | the need is essential; the form follows from approving a moving branch |
| `ORIGIN_*` | 6 | stale local evidence | yes |
| `IMPLEMENTATION_MISSING`, `REVIEW_NOT_INDEPENDENT`, `OWNERSHIP_UNRESOLVED` | 3 named | hollow work, self-review | yes (R8) |
| `ACTIVATION_*`, `LEGACY_*`, `DENY_*` | 12 | two activation stores | no |

Also in this pattern: 219 functions named drift, reconcile, heal, repair, backfill or restamp outside migrations; 18 doctor modules, 9,877 lines ([executed K1]).

## 3. Pattern 2: one rule, implemented in parallel

| Id | Rule | Implementations | Held together by | Evidence |
|---|---|---|---|---|
| D2.1 | Charter domain: offering, activation, context | Python in core (77,725 lines; 85,238 with the two CLI-side packages, CH CB11) and the Java service (about 137,000 main). No client, pin or launch path in core | nothing now; the conformance corpus was dropped as a gate | M5 section 6 (E7, E27, E29) |
| D2.2 | Meaning of an absent activation key | core: per-kind default; charter repository: none | nothing: they disagree | M5 section 6 (E31) |
| D2.3 | Lane vocabulary and legal edges | `status/wp_state.py:221`; `spec-kitty-events:src/spec_kitty_events/status.py:692` and `diary.py:152`; Java `LaneMachine`; orchestrator `scheduler.py` | parity oracles against a pinned core commit | M4 5.2; M3 5.2; CH CA06 [read] |
| D2.4 | Status fold | package `diary.reduce_parsed`; package `reduce_status_events` (not on the CLI path); Java `StatusReducer`; Java `TransitionFold` | conformance fixtures; the Java read side lags one ordering fix | M4 5.2; M3 5.2 |
| D2.5 | Lifecycle guards | core pipeline and `move-task`; package `validate_transition` (edges, force, `review_ref` only); Java `DependencyGate`, `ClaimGate`, `PipelineGuards` | nothing | CH CA07 [read] |
| D2.6 | Where status is read from; what topology is | Python read-path resolver and placement seam; Java `ReadDirResolver`, `Topology` | a contract enum pinned to core's symbol | M1 section 6 (E32, E37) |
| D2.7 | Pack validation | `pack_validator.py`, `consistency_check.py`, `neutrality/lint.py`; Java `pack-validation`, `pack-doctor` | nothing | M5 section 6 |

All seven are **transitional by ruling R7**: the event log moves to the events system and the charter to the charter system. None has a dated end, and in D2.1 and D2.3 the two sides are still both being changed.

## 4. Pattern 3: built-ins bypass the extension mechanism

The extension point exists in each case; the four built-in types, or the built-in tools, do not use it.

| Id | Concern | Built-in path | Declared path | Evidence |
|---|---|---|---|---|
| D3.1 | Step guards | `_GUARD_TABLES` keyed by the four type names, with step-id chains | blocking set from `expected-artifacts.yaml`, which the built-in packs also ship | `runtime_bridge_cores.py:859-864` [read K1]; X1 1.1 |
| D3.2 | Work-package iteration | `mission == "software-dev" or snapshot.wp_driven` | the `wp_driven` fact, derived from declared steps | `runtime_bridge_composition.py:509`; X1 1.2 |
| D3.3 | Requirement kinds | five `research` branches in `grammar.py` | `requirement-kinds.yaml` loader with no production caller | `requirement_mapping/grammar.py:83,196,287,362,379`; X1 1.3 |
| D3.4 | Capabilities, plan substantiveness, step profile | `BUILTIN_TYPE_CAPABILITIES`, `_PLAN_FIELD_DECLARATIONS`, `_ACTION_PROFILE_DEFAULTS` | descriptor field; `plan-field-declaration.yaml` (none shipped); `agent_profile` on the step | M2 5.2 |
| D3.5 | Type-specific state and spec tests | `if mission == "documentation"` at creation; research-only substantiveness message | none: a pack type cannot have its own | `core/mission_creation_meta.py:262`; `cli/commands/agent/mission_setup_plan.py:429`; X1 1.5 |
| D3.6 | Installed commands | a fixed tuple matching the software-dev step directories | none: a research or custom step has no command | `skills/command_installer.py:98-114` [read K1] |
| D3.7 | Lane grouping | `_SURFACE_KEYWORDS` substrings ("api", "view", "template") | `owned_files` in the manifest | `lanes/compute.py:302` (CH R13). **Contested:** the conflict-avoidance reason holds (ST S11) |
| D3.8 | Reserved built-in keys | a project may not override a built-in type | layer precedence, as for every other artefact | `_internal_runtime/discovery.py:42-49`; ST S13 |
| D3.9 | Mission type inside the charter layer | `software-dev` in 87 lines of 30 files of `src/charter`; a four-token fast path in the context builder | graph membership | M5 5.6 (CH R19 [executed]) |
| D3.10 | Agent tools | 10 to 12 tables keyed by agent; `AGENT_DIRS` owned by a migration module | `tool_surface/` profiles | X1 1.8. CH CB07: the declared path is itself only partly declarative (three tool-named renderers) |

Step-id literals: the catalogue's count of 31 was not reproducible; a strict pattern finds 15 in `src`, a wider one 24 in `runtime_bridge_cores.py` alone (CH R04). The pattern holds; the number does not.

A live defect belongs here: the research guards need events that only a retired engine wrote, so a research Mission cannot pass `gathering` (M2 5.4; ST S26 finds no defence).

## 5. Pattern 4: entry points with different rule sets

| Id | Operation | Entry points | Difference | Evidence |
|---|---|---|---|---|
| D4.1 | Landing a Mission | `consolidate`; `orchestrator-api consolidate-mission` | the second has no claim, no gate, no rollback, and re-adds selected checks as nine `_refuse_*` functions | `orchestrator_api/consolidation.py:507,538,586` [read K1]; M7 section 6; ST S31 finds no reason |
| D4.2 | Moving a work package | `move-task`; `agent status emit`; `orchestrator-api transition`; `agent action`; `implement`; `next`; `accept`; `consolidate` | ownership, evidence, independence and pre-review gates live in the `move-task` command; `status emit` and the API reach the pipeline without them | M3 5.7; `cli/commands/agent/tasks_move_task_gates.py` (1,703 lines) |
| D4.3 | Claiming a work package | `agent action implement`; `orchestrator_api/wp_lifecycle.py` | own dependency pre-flight, lane resolution and workspace allocation | M6 5.5 (E31) |
| D4.4 | Driving a Mission forward | seven ways, resting on two models of progress | the board and the run cursor | M6 section 4; X1 3.2 |
| D4.5 | Governance text into a prompt | `charter context`; `next` prompt builder; `agent action`; `dispatch`; skill projection; command templates | each passes different arguments (profile without mission type, or the reverse) | M5 E13 |
| D4.6 | Gates over the same evidence | `move-task` hop gates; `for_review` gate; `accept`; the claim; the reconciliation gate; API preflights | layered because a later entry can bypass an earlier gate | X1 3.8 |
| D4.7 | Checking a file a step produced | `next` passes `scoping` on presence of `spec.md`; `setup-plan` refuses the same file | two checks, two verdicts | M2 5.5 |

## 6. Pattern 5: several stores for one fact

| Id | Fact | Stores | Reconciling code | Evidence |
|---|---|---|---|---|
| D5.1 | Topology and branches of a Mission | `meta.json` and `lanes.json` | `TopologyManifestMismatch`, a re-stamp migration, `migrate backfill-topology`, `doctor topology` | X1 4.1; M1 E41 |
| D5.2 | Work-package lane | event log; committed `status.json`; frontmatter `lane`; lane-tip refs | `status/doctor.py`, `validate.py`, a merge driver | X1 4.2; M3 5.9. The mirror is still written: `status/emit.py:640,823,879,1207` [read K1] |
| D5.3 | Mission position | clone-local run cursor; the board; `mission-events.jsonl` | override phases in `next` | M3 5.4 |
| D5.4 | Work-package dependencies | `wps.yaml`; `tasks.md` prose; frontmatter | none found | M3 section 6 |
| D5.5 | Whether a rule is in force | `activated_*`; `selected_*`; the `directives:` section; org `required_*`; `deactivated_*`; legacy keys | resolver union; eight doctor codes | M5 5.2; X1 4.4 |
| D5.6 | Where a lane lives | `lanes.json`; a workspace context JSON; the git worktree registry; the lane-tip ref | recovery and cleanup commands | M1 section 6 (E42) |
| D5.7 | What migrations ran | two ledger partitions; an in-memory `metadata` record; the schema integer | adoption logic | M8 5.4; X1 4.5 |
| D5.8 | Which projected files the tool owns | `command-skills-manifest.json`; `skills-manifest.json`; `tool-surface-profile-manifest.json`; a bare `manifest.json` | none found | X1 3.7 |
| D5.9 | Decisions | DecisionPoint rows in `status.events.jsonl`; `decisions.events.jsonl` | none found | M4 section 6 |

Non-migration source names more than twenty `.jsonl` files, each with its own reader (X1 class 4).

## 7. Patterns 6 to 10

**Pattern 6: unfinished extraction kept in parallel.**

| Id | Case | Evidence |
|---|---|---|
| D6.1 | Built-in mission definitions in `src/specify_cli/missions/<type>/mission.yaml` and `packs/built-in/missions/<type>/mission.yaml`, byte-identical for all four types | [executed K1: `diff -q`]; X1 4.3 |
| D6.2 | Two `resolver.py` modules with the same private helpers; a six-tier chain whose second tier is named `LEGACY` | `src/charter/offering/resolver.py:73-332`; `src/specify_cli/runtime/resolver.py:156-769`; X1 3.4 |
| D6.3 | The reducer "moved verbatim" to the events package; core kept its own 1,217-line `status/models.py` and wraps the package fold | M4 5.3 |
| D6.4 | `tasks_move_task.py` beside its executor, hops and gates split; `_APPROVAL_LANES` defined in both | X1 6.4; 20 files, 16,999 lines [executed K1] |
| D6.5 | Re-export facades: 14 modules with lazy `__getattr__`; `reconciliation.py` "holding no logic" | X1 6.3; M7 section 5 |
| D6.6 | The step engine internalised whole from a retired package, with its own state store and an 11-module bridge | M6 section 10 |

**Pattern 7: a rule restated at call sites.**

| Id | Rule | Spread | Evidence |
|---|---|---|---|
| D7.1 | A Mission's target branch | about 22 resolver functions; five branch notions | X1 2.1 |
| D7.2 | Protected-branch enforcement and wording | one policy; about 40 `*protected*` functions; the refusal rendered four times | X1 2.2 |
| D7.3 | "Approved or done" | 34 literal restatements; seven named constants | X1 2.3 |
| D7.4 | Mission handle resolution | one canonical resolver; five private `_resolve_mission_slug` | X1 2.4 |
| D7.5 | "Is this path bookkeeping" | 4 | M7 section 6 |
| D7.6 | "Is this single-branch" | 4 predicates | M1 E39 |
| D7.7 | Small helpers | 343 function names defined in two or more modules: `_git` ten times, `_generate_ulid` nine | X1 2.6 |

**Pattern 8: transitional without end; legacy readers in run-time code.**

| Id | Case | Evidence |
|---|---|---|
| D8.1 | No-op schema gate (`MIN = MAX = 3`), so 26 files carry their own "unmigrated" refusal | `migration/schema_version.py:22-23` [read K1]; M8 5.2 |
| D8.2 | Run-time code imports topology readers from the migration package at 24 call sites | M8 section 6 |
| D8.3 | Legacy activation reader; branch-name failover; pre-SSOT status routing | M8 section 13 |
| D8.4 | Three upgrade channels, each with its own record | M8 5.1 |
| D8.5 | Migration content back to 0.2.0: 144 registered steps (155 modules with helpers, CH CA11), 59 below 3.0 | M8 section 4 |
| D8.6 | `mission-events.jsonl`, a "Phase 1B provisional interface" | `mission_v1/events.py:1` (CH R16) |

**Pattern 9: indirection with nothing behind it.**

| Id | Case | Evidence |
|---|---|---|
| D9.1 | Event produce seam: no registrant in core's `src`. **Corrected:** registrants are preserved in `event-router` (11 files), so "no subscriber" is true of core only | `status/adapters.py:150-318`; CH CA05 |
| D9.2 | Requirement-kind loader with no production caller | `charter/activation/manifest_loader.py:363`; X1 1.3 |
| D9.3 | Write-service protocol module with no transport; launcher called only by `service stop` | M4 5.1 (CH R10) |
| D9.4 | Read service with no caller | M4 5.8 |
| D9.5 | Workflows: one shipped file; nothing writes `workflow_id` | M2 4.3 |
| D9.6 | Empty shim registry with a doctor and three gates | M8 5.7; ST S35 |
| D9.7 | Migration knobs with zero or one user; RACI and significance scoring used by no built-in type | M8 5.8; M6 E14. ST S36: decide the intent before deleting the second |

**Pattern 10: vocabulary and parameter redundancy.**

| Id | Case | Evidence |
|---|---|---|
| D10.1 | "Lane" names a status state and an isolation unit | M3 section 6; N1 section 6 |
| D10.2 | `feature_dir` in 4,353 lines of 284 files, against a canon that forbids the word | X1 class 7 |
| D10.3 | Branch facts emitted under nine JSON keys | X1 8.1 |
| D10.4 | Mission selection by `--mission`, `--feature` or position; events accept two slug keys | X1 8.2 |
| D10.5 | Four enums that say "topology" | X1 1.7 |
| D10.6 | "merge" names under the `consolidate` command; `spec-kitty ops` is the reflog while an Op is a dispatch record | M7 section 5; M6 5.9 |

## 8. Where the inputs disagree

| Case | Position A | Position B | What would settle it |
|---|---|---|---|
| D1.8 ordering rules | M4: compensation; delete with a single writer | ST S1: a recorded two-clone failure returns in any git-shared design | a ruling on how clones share Mission state |
| D1.6 attribution core | M7: not needed if one branch is one unit of review | M1's preferred shape keeps lanes with several work packages; ST S3: the pair loses the rule | a ruling on the unit of isolation and review |
| D4.1 second executor | X1, M7, ST: no reason found | none | whether an external consumer depends on the difference (X1 uncertainty) |
| D3.1 built-in guards | X1, M2: declarable | parity fixtures marked "do not weaken" (M2 section 10) | M2's experiment: express the research and documentation guards as manifest entries |
| D9.1 produce seam | M4, X1: remove | ST S17: a read surface must exist first | the owner of the preserved registrants |
| D3.10 tools | M6: two open formats | ST S5: a core capability on an unchecked assumption | a per-tool desk check |

## 9. The cheapest to remove

From X1, kept where the challenge and the steelman raise no objection. Each is internal to core and touches no user data.

| # | Removal | Why cheap |
|---|---|---|
| 1 | The copied tree `src/specify_cli/missions/<type>/` (D6.1) | byte-identical to the pack tree; readers are repointed |
| 2 | The `software-dev` literal beside `wp_driven` (D3.2) and the eleven default-type constants | mechanical; the fact exists |
| 3 | Duplicate predicates and helpers (D7.3, D7.5 to D7.7) | one predicate on the lane model |
| 4 | One of the two `resolver.py` modules (D6.2) | same functions |
| 5 | The uncalled kind loader, or bind it and delete the `research` branches (D3.3) | no caller |
| 6 | The empty shim registry with its doctor and gates (D9.6) | guards nothing |

The produce seam is **not** on this list: it has preserved registrants outside core (D9.1).

## Limits

I re-read at head the references my ranking rests on most: D3.1, D3.6, D4.1, D5.2, D6.1, D8.1. The rest are the assessors' references, of which the challenge sampled 20 and found 19 true and 1 partly true (CH section 9). I did not re-read the Java repositories. The ranking is a judgement of cost, not a measurement.
