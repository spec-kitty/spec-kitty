---
doc_status: draft
updated: '2026-11-28'
---

# 5. Obstruction map

Consolidator K3, profile `planner-priti`. The profile decomposes into work packages; the envelope forbids work items, so this is a proposal only. The map lists each **present arrangement** that impedes the recommended architecture of `04-candidate-architecture.md`. Every row names the roadmap step of `07-remediation-roadmap.md` that removes it (`T1` to `T15`; `P1` to `P10` are probes). Decision ids `D1` to `D16` are those of `06-capability-dispositions.md` section 2. The full rows, with representative example and label, are in `05-obstruction-map.csv` (58 rows).

Evidence tags: [read] and [executed] are mine, at head; [relayed] is an input's reference that I did not re-open. `Mx §n` is `mechanisms/Mx.md`; `X1` is `duplication/catalogue.md`; `ST` is `challenge/steelman.md`; `CH` is `challenge/candidate-challenge.md`. Code references are to core unless a repository is named.

## Conclusion

1. **One obstruction blocks most of the others.** The status log is a tracked file on branches that carry code (O01). At least nine further rows exist because of it (O02 to O04, O06, O15, O17, O49, O54, O58), and none of them can be deleted before the record is written elsewhere (step T8). Four assessors named it independently (M1 §10.1, M3 §10.1, M4 §10.1, M7 §10 [relayed]).
2. **Eleven of 58 obstructions can be removed fully with no ruling, and six more in part**, in steps T1 to T4 and by the probes. They are copies, restated predicates, built-in types that bypass their own extension mechanism, and a seam that carries no traffic.
3. **Twelve obstructions are compatibility mechanisms**, not code problems. A ruling removes them, not an implementation: the upgrade floor (D9), Missions in flight (D8), the tool list (D10), the API (D11), recorded decisions (D15).
4. **Three obstructions are not removed by this roadmap**, only bounded: no human identity (O52), git's one checkout per branch (O55), and prompts that restate mechanism (O28).
5. **The pins are obstructions too.** Architectural gates, parity fixtures and tests that patch private names (O14, O26, O41, O42) make a deletion look like a regression. Each step must retire the gates of what it deletes.

| Kind | Rows | Typical removal |
|---|---|---|
| shared state or implicit dependency | 13 | move the state; state the dependency in a contract |
| compatibility mechanism | 12 | a ruling, then a floor or a converter |
| duplicated rule | 8 | one owner; delete the copies |
| competing authority | 7 | name the authority; delete or demote the other |
| unnecessary abstraction | 6 | delete with its cause |
| hardcoded special case | 5 | declare as data |
| distributed responsibility | 4 | one operation behind every door |
| bypassed extension mechanism | 3 | put the built-in on the declared path |

Kind codes in the tables: **SS** shared state or implicit dependency, **CM** compatibility mechanism, **DR** duplicated rule, **CA** competing authority, **UA** unnecessary abstraction, **HS** hardcoded special case, **DI** distributed responsibility, **BE** bypassed extension mechanism.

## 1. What blocks the record on a ref (04 choice 1)

| Id | Kind | Present arrangement and example | Source | What removes it | Step |
|---|---|---|---|---|---|
| O01 | SS | Status log is a tracked file on code branches; every checkout holds a copy | M1 §10.1; M3 §10.1; M4 §10.1 [relayed] | record written by compare-and-swap to a ref | T8, T11 |
| O02 | UA | PRIMARY/COORD partition and placement seam; `mission_runtime/resolution.py` is imported by most commands | M1 5.1, §10.6 [relayed] | commands ask a Mission value; seam deleted with the old shape | T2, T11 |
| O03 | CA | Coordination branch and worktree: a second copy of status; Proposed ADRs keep it as lifecycle home | M1 5.2, §10.4; ST S23 [relayed] | deleted with the old shape; ADR set superseded (D15) | T11 |
| O04 | SS | Sparse status exclusion, lane write guard, planning-commit pin | M1 5.3, 5.4 [relayed]; `cli/commands/agent/mission_finalize_planning_pin.py`, 1,623 lines [executed] | gone when status is off the tree | T11 |
| O15 | SS | Wall-clock ordering, lift, merge driver and its clone-local git configuration. Contested (ST S1, S20) | M4 5.4 [relayed] | replay at `sync` is the one join rule | T8, T11, T14 |
| O17 | CA | Seventeen lifecycle stores; the frontmatter lane mirror is still written | `status/emit.py:640, 823, 879, 1207` [read]; M3 §4 [relayed] | mirror stops with the one log per Mission | T6, T11 |
| O48 | SS | External readers of the on-disk log and of `status.json`: `fleet-kitty`, `spec-kitty-planning`, hosted dossier, read-service resolver | 04 §12; ST S28 [relayed] | one update per consumer, announced a release candidate ahead | T6, T8 |
| O49 | DR | Java services and events contracts restate topology and the read-directory rule (`Topology.yaml`, `WriteSurface.yaml`) | M1 §10.3 [relayed] | an events contract release drops them | T11 |
| O47 | UA | Produce seam: no registrant in core, registrants preserved in `event-router`. Contested (ST S17) | `status/adapters.py:150` [read]; CH CA05 [relayed] | removed after the ref is readable and their owner agrees | T11 |

## 2. What blocks one state machine and one owner per rule (04 section 4)

| Id | Kind | Present arrangement and example | Source | What removes it | Step |
|---|---|---|---|---|---|
| O10 | DI | Guards live in a command module; `agent status emit` and the API `transition` verb reach the pipeline without them | `cli/commands/agent/tasks_move_task_gates.py`, 1,703 lines [executed]; M3 5.7 [relayed] | one transition operation in core, then behind `append` | T5, T7 |
| O09 | CA | Second landing executor: "merges lanes with no claim and no gate behind it (and no rollback)" | `orchestrator_api/consolidation.py:586` [read] | the verb calls the one executor | T5 |
| O11 | DR | Second claim implementation for programs | `orchestrator_api/wp_lifecycle.py`, 1,074 lines [executed]; M6 5.5 [relayed] | both call one `start` operation | T5, T9 |
| O12 | DR | Lane vocabulary and legal edges in three to five places, two languages, held by parity oracles | M4 5.2; CH CA06 [relayed] | states reduced once; core's copy deleted | T6, T7 |
| O13 | DR | The fold exists four times | M4 5.2 [relayed] | one fold by append order | T7, T8 |
| O14 | CM | Byte-exact parity with a pinned core commit is the migration method; deletion reads as regression | M4 §10.3 [relayed] | contract restated as `append` with facts | T7 |
| O16 | CA | Java write service built and released, not bound; "no Python fallback writer" is recorded | M4 5.1 [relayed]; `CLAUDE.md` [read] | a ruling on the writer (D4) | T7 |
| O06 | SS | Lifecycle rows carry landing's git evidence (`lane_head`, `wp_window`) | `status/transition_pipeline.py:201` [read]; M3 §10.2 [relayed] | the verdict names a commit | T6, T9, T11 |
| O45 | DI | Target branch, handle and status location derived per command: about 22 resolvers | X1 2.1, 2.4 [relayed] | one Mission value object | T2 |
| O46 | DR | "Approved or done" restated 34 times; bookkeeping-path and single-branch predicates four times each | X1 2.3; M7 §6 [relayed] | one predicate each | T2 |
| O52 | SS | No human identity: the actor is an asserted string | `status/models.py:411` [read]; M6 §11 [relayed] | **not removed**; bounded by interactive `accept` (D12) | T9 |

## 3. What blocks a branch per work package and tree-equality landing (04 choices 2 to 4)

| Id | Kind | Present arrangement and example | Source | What removes it | Step |
|---|---|---|---|---|---|
| O05 | HS | Several work packages share a lane; `_SURFACE_KEYWORDS` groups them on substrings | `lanes/compute.py:302` [read]; M7 §10 [relayed] | `start` cuts a branch from the Mission tip | T9, T11 |
| O07 | SS | Squash is the default; it destroys the identities that would prove equality | M7 §5, §10 [relayed] | merge commit by default (D13) | T9 |
| O08 | UA | Fifteen landing phases over three branches, with a rollback authority | `consolidation/rollback.py`, 1,380 lines [executed]; M7 §5 [relayed] | `land` is one compare-and-swap | T9, T11 |
| O55 | SS | Git allows one checkout per branch | M1 §10.7 [relayed] | **not removed**; integration by `merge-tree` when no clean checkout holds the branch | T9 |
| O54 | UA | Protection policy and `--commit-to-target`; about 40 `*protected*` functions | X1 2.2 [relayed] | only `land` writes the target (D14) | T2, T11 |
| O44 | CM | API contract: 27 verbs, enumerated refusal codes; both clients drifted | M7 §10; M6 5.6 [relayed] | API 2.0, aliases to 4.1.0 (D11) | T9, T15 |
| O51 | CM | Missions in flight in the old shape; mixed lanes cannot be imported without the old gate | 04 §5 F7 [relayed] | land on the last release with `consolidate` (D8) | T11, T15 |
| O50 | CM | 859 landed Missions kept readable by the live reader | `status/cutover_eligibility.py:1-8` [read]; M3 §10.6 [relayed] | they stay as files in history | T11, T14 |
| O43 | CM | Recorded decisions encode the present shape: five landing ADRs with 41 amendment headings | M7 §10 [relayed] | superseded as sets (D15) | T7, T11, T14 |

## 4. What blocks kinds of work as data and a stateless loop (04 rule R-e)

| Id | Kind | Present arrangement and example | Source | What removes it | Step |
|---|---|---|---|---|---|
| O19 | BE | `_GUARD_TABLES` keyed by the four type names | `runtime/next/runtime_bridge_cores.py:859-864` [read] | declared checks carry every guard | T4 |
| O20 | HS | `mission == "software-dev" or snapshot.wp_driven`; 156 such literals in 64 files | `runtime_bridge_composition.py:509` [read]; CH CB12 [relayed] | literal deleted; shrink-only count | T1, T4 |
| O21 | BE | Five `research` branches beside a loader with no caller | `requirement_mapping/grammar.py:83, 196`; `charter/activation/manifest_loader.py:363` [read] | loader bound, branches deleted | T4 |
| O22 | HS | `if mission == "documentation"` at creation; capability and profile tables | `core/mission_creation_meta.py:262` [read]; M2 5.2 [relayed] | descriptor fields carry them | T4 |
| O23 | HS | Installed commands are a fixed tuple of software-dev steps | `skills/command_installer.py:101-114` [read] | commands generated per step | T4 |
| O25 | SS | Research guards count events only a retired engine wrote: a live defect | M2 5.4; ST S26 [relayed] | guards restated on artefacts | T4 |
| O26 | CM | Parity fixtures marked "do not weaken" pin the Python chains | M2 §10.1 [relayed] | side-by-side evaluation for one release candidate | P7, T4 |
| O24 | CM | Five definition generations read at once; a byte-identical copy of each built-in `mission.yaml` | `diff -q` silent for four types [executed]; M2 4.3 [relayed] | copy deleted; one format with a converter | T1, T10 |
| O18 | CA | Run cursor beside the committed board; engine internalised with its own store | M6 5.1, §10.1 [relayed] | `decide` over lock, artefacts and record | T10 |
| O27 | DR | Charter and runtime each parse the other's files because of the layer rule | M2 §10.2 [relayed] | core reads `type.lock.yaml` only | T10, T12 |
| O56 | UA | Dispatch keyword router; Op lifecycle files | M6.5; ST S34 [relayed] | Ops are events in `ops.jsonl` | T10 |
| O28 | DI | Prompts and skills restate paths, guards and states: 5,236 and 5,800 lines, no gate | M2 §10.5; M6 §10.6 [relayed] | **not removed**; each step updates what it invalidates, in `spec-kitty-open-packs` | T4, T6, T9, T10 |

## 5. What blocks the compiled bundle and tools as data

| Id | Kind | Present arrangement and example | Source | What removes it | Step |
|---|---|---|---|---|---|
| O30 | BE | `charter.offering.api` is not a routing point: 149 files outside `src/charter` import `charter.*`, most often `charter.drg` (80 import lines) | [executed]; M5 §10.1 [relayed] | imports routed through the seam, gated | T3 |
| O29 | DR | Two full charter implementations, no traffic between them | M5 §6; CH CB11 [relayed] | one switch after equivalence in CI (D6) | T12 |
| O31 | CA | Five sources answer "is this rule in force"; the two repositories disagree on an absent key | M5 5.2, §6 [relayed] | model reduced on the charter side first (D7) | T12 |
| O32 | SS | Governance text depends on per-checkout first-load state: a live defect | M5 5.1 [relayed] | compiled per-step files | T12 |
| O33 | DR | Two `resolver.py` modules (402 and 846 lines), second tier named `LEGACY` | [executed]; X1 3.4 [relayed] | one module now; chain goes at the switch | T1, T12 |
| O34 | HS | Per-tool tables in ten to twelve places; `AGENT_DIRS` owned by a migration; four manifests | `upgrade/migrations/m_0_9_1_complete_lane_migration.py:21` [read]; X1 1.8 [relayed] | rows after a desk check | P3, T13 |
| O35 | CM | The tool list is a product promise in README and `init` | M6 §10.5 [relayed] | a ruling (D10) | T13 |

## 6. What blocks the baseline cut, and what blocks every step

| Id | Kind | Present arrangement and example | Source | What removes it | Step |
|---|---|---|---|---|---|
| O36 | CM | No-op schema gate, so 26 files carry their own "unmigrated" refusal | `migration/schema_version.py:22-23` [read] | shape 4 with a floor (D9) | T14 |
| O37 | SS | Run-time code imports topology readers from `migration/` | M8 §10.2 [relayed: 24 call sites]; the name occurs in 26 files outside the package [executed] | readers move behind the Mission value | T2 |
| O38 | CM | `mission_id` and `topology` optional in `meta.json` | M8 §10.3 [relayed] | mandatory in shape 4 | T2, T14 |
| O39 | CM | 144 migrations back to 0.2.0, protected by DIRECTIVE_044 and a hash audit | M8 §4, §10.1 [relayed] | a ruling that a baseline cut is a retirement (D9, D15) | T14 |
| O40 | CA | Three upgrade channels, four records of what ran | M8 5.1, 5.4 [relayed] | one shape version | T14 |
| O58 | UA | A doctor per mechanism that can enter a bad state: 18 modules | 03 §2 [relayed] | each goes with its store | T11, T14 |
| O41 | SS | Architectural gates and AST pins freeze module shapes | `tests/consolidation/test_single_rollback_authority.py` [read: exists]; M3 §10.5 [relayed] | each step retires its gates and adds the replacing rule's gate | every step |
| O42 | SS | Tests patch private names across modules | M6 §10.4 [relayed] | tests restated against the operation before the move | T2, T5 |
| O53 | DI | `cli` holds rules of other subsystems; 79,000 lines elsewhere have no assessor | 04 §8 [relayed] | each step removes its command family; a reading pass | P5, T15 |
| O57 | CM | Vocabulary residue: `feature_dir` in 284 files; two senses of "lane" | X1 class 7 [relayed] | renamed where a step rewrites the module | T2, T6, T9 |

## 7. How the obstructions depend on each other

```
O01 status in the tree
 ├─ O02 partition, O03 coordination copy, O04 exclusions and pin
 ├─ O15 ordering and merge driver, O17 stores, O49 Java restatement
 ├─ O06 stamps in lifecycle rows ── O05 shared lanes ── O07 squash ── O08 phased landing
 └─ O54 protection policy, O58 doctors

O10 guards in a command ── O09, O11 (second executor, second claim)
O12, O13 two languages ── O14 parity ── O16 writer undecided
O19 to O23 built-ins in Python ── O26 parity fixtures ── O25 research defect
O30 seam without traffic ── O29 two charters ── O31, O32
O36 no-op gate ── O38 optional fields ── O37 run-time imports of migration code ── O39, O40
```

Three consequences for the order. O01 is removed late, because it needs D1 and D2 and a new store; so the roadmap first removes what does not depend on it. O10 is small and independent, and it carries the highest exposure (03, conclusion 3), so it comes early. O30 costs nothing in behaviour and is the precondition of the largest single move.

## 8. Disagreements kept visible

| Row | Position A | Position B | What settles it |
|---|---|---|---|
| O15 | M4: compensation, delete | ST S1: the two-clone failure returns in any git-shared record; 04 keeps a join rule (replay) | D2; the replay re-check through the state machine is not built (04 §5 F2) |
| O05 | M1 alternative A keeps thin lanes | CA, CB and 04: a branch per work package | probe P4, the pilot (D3) |
| O47 | M4, X1: remove | ST S17: a read surface must exist first | the owner of the preserved registrants |
| O26 | X1, M2: guards are declarable | fixtures say "do not weaken" | probe P7 |
| O34 | M6: two open formats | ST S5: unchecked assumption; 04: rows, unproven | probe P3 |

## Limits

I re-read at head 17 references, those tagged [read] or [executed] above. The Java repositories and the charter repository were not opened. Counts are pointers (R15). One number differs between an input and my count and both are shown: 24 call sites against 26 files for O37. For O30 the assessor counted 148 files; my grep over `src/specify_cli`, `src/runtime`, `src/mission_runtime` and `src/glossary` finds 149 [executed]. The frontmatter lane (O17) is named in at least 12 non-migration files [executed], so its mirror is not stopped in T1 but with the one log in T6.
