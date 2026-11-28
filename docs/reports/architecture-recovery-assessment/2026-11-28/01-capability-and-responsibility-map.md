---
doc_status: draft
updated: '2026-11-28'
---

# 1. Current capability and responsibility map

Consolidator K1, profile `synthesizer-sam` (its rule to write under a `synthesizer/` folder yields to the envelope: the files named in the brief are written here). This file describes the **current implementation**. It proposes nothing; the target is deliverable 4.

Sources: `needs/` (N1), `mechanisms/M1` to `M8`, `duplication/` (X1), `challenge/` (steelman ST, challenge CH). A reference such as "M1 E8" is a row of that assessor's evidence table. Statements tagged "K1" were re-checked or measured by me at head. Code references are to core (`/home/user/spec-kitty`) unless a repository is named. Counts are pointers for where to look, not evidence of excess (R15).

## Conclusion

1. **The product promise is 32 capabilities, of which 12 are rated core** (N1's table; its text says nine). Every core capability is carried by more than one mechanism today, between three and seven (N1 section 3).
2. **Few responsibilities have one owner.** Each of the 24 domain rules traced below is held in 2 to about 40 places; seven are held in more than one repository or language. I found three rules with one owner that every caller asks.
3. **About 400,000 of core's 524,936 Python lines sit in the packages that carry the eight assessed mechanisms and the command layer** (section 5) [executed K1: `find <dir> -name '*.py' -not -path '*__pycache__*' | xargs cat | wc -l` per package].
4. **The command layer is the largest single holder of domain rules.** `src/specify_cli/cli` is 107,407 lines. About a sixth of it is command wiring. About half sits in modules that define no command at all (section 4). No input gave it a disposition; it is described here so that it is not left unassessed.
5. **Three documented journeys have nothing placed to serve them** (read-only progress for an outsider, tracker issues into work, publishing a landed Mission), and five capabilities exist with no documented journey (N1 section 4).

## 1. How to read the map

- **Capability** ids C01 to C32 and essentiality are N1's (`needs/capabilities.csv`).
- **Places** counts the mechanisms that claim the capability today: names, a pointer.
- **Lines** are rough package sizes. They overlap (`status/` serves C06, C09, C11, C24) and are not additive.
- **Label** follows R17: current, transitional (its end, if one is stated), legacy, intended target not yet in use.
- The full rows, with code locations and concepts, are in `01-capability-and-responsibility-map.csv`.

## 2. Capabilities and what carries them today

| Id | Capability (short) | Ess. | Carried today by | Main code | Places | Rough lines |
|---|---|---|---|---|---|---|
| C01 | Bring a repository under Spec Kitty | core | `init`, `verify-setup`, `doctor` | `cli/commands/init.py` (1,917) | 3 | 2k |
| C02 | Workflow inside the user's agent tool | core | command files for 12 tools, shared skills for 5, plugin, session hooks, `agent config` | `tool_surface/` 10,743; `skills/` 6,486; `session_presence/` 2,030 | 5 | 19k |
| C03 | Intent to agreed specification by interview | core | specify prompt, Decision Moments, intake, `mission create` | `decisions/` 3,654; `cli/commands/agent/mission*.py` | 4 | 5k + prompts |
| C04 | Plan and bounded work packages with dependencies | core | plan and tasks prompts, `finalize-tasks`, `wps.yaml`, dependency graph | `cli/commands/agent/mission_finalize*.py`; `core/dependency_graph.py` | 4 | 9k |
| C05 | "What next", and resume in a new session | core | `next` runtime, step graph, slash commands, implement-review skill, `orchestrator-api list-ready`, top-level lifecycle commands | `src/runtime/` 17,627; `cli/commands/next_cmd.py` 1,627 | 6 | 19k |
| C06 | State of each unit recorded in the repository | core | status event log, state machine in three places, package reducer, write service, derived views | `status/` 21,397; `spec-kitty-events` Python 18.6k; Java 19.5k main (M4) | 5 | 21k core |
| C07 | Several agents on one Mission without overwriting | core | lanes, worktrees, four topologies, coordination branch, write-checkout guards, `owned_files` | `lanes/` 16,574; `workspace/` 2,872; `coordination/` 15,036; `mission_runtime/` 6,868 | 6 | 41k |
| C08 | Dependent work starts when and from its predecessor | important | dependency gating, lane dependency merge, `implement --incorporate`, auto-rebase | `core/dependency_graph.py`; `lanes/auto_rebase.py`, `incorporate.py` | 4 | in C07 |
| C09 | Review by someone other than the author | core | review prompt, `agent action review`, `move-task`, review-cycle artefacts, independence check, verdict skill | `review/` 9,326; `cli/commands/agent/tasks*.py` 16,999 | 6 | 26k |
| C10 | A human accepts the Mission | core | `accept`, mission review, analyze step, issue matrix | `acceptance/` 6,108; `cli/commands/accept.py` 1,927 | 4 | 8k |
| C11 | Only reviewed work lands; preview, resume, undo | core | `consolidate`, `orchestrator-api consolidate-mission`, approval-stamp bound, reconciliation gate, rollback authority, retention, origin gate | `consolidation/` 36,414; in all about 64,500 (M7 section 4) | 7 | 64k |
| C12 | Integration branch clean; target chosen deliberately | important | topic branch default, protection policy, `--commit-to-target`, retarget | `git/protection_policy.py`; about 40 `*protected*` functions (X1 2.2) | 5 | in C07, C11 |
| C13 | Interrupted work recoverable with a named remedy | important | `--resume`/`--abort`, lane work-tip recorder, `context cleanup`, doctors | `consolidation/rollback.py` 1,380; `lanes/lane_tip.py` | 4 | in C07, C11 |
| C14 | Other kinds of work have their own steps and gates | important | mission types as pack data, a second `mission.yaml` tree, type-specific commands, Python tables per type | `charter/offering/missions/` 3,499; `runtime_bridge_cores.py`; `missions/` 5,195 | 4 | 27k with C05 (M2) |
| C15 | A new kind of work without changing the CLI | important | project mission loader, pack mission type, `workflow`, `mission run` | `mission_loader/` 1,399 | 4 | 2k |
| C16 | Rules stated once, applied at every step | core | Python charter, charter service (no traffic), activation ledger, context resolver, rendered prompts, DRG | `src/charter/` 77,725; `cli/commands/charter/` 12,135; `spec-kitty-charter` Java about 137,000 main (M5 E7) | 6 | 90k core |
| C17 | Choose which rules and roles apply | important | activation engine, cascade, ledger, presets | `charter/activation/` 45,426 (M5 E5) | 4 | in C16 |
| C18 | Organisation rules, some not removable | important | org packs, open-packs, pack logic in four readers, composer | `charter_packs/` 2,859; `spec-kitty-open-packs` | 4 | in C16 |
| C19 | An agent takes a defined role | important | agent profiles, profile invocation, lineage edge, model/task selection | `charter/offering/`; `invocation/` | 4 | in C16, C21 |
| C20 | Consistent terms | optional | glossary | `src/glossary/` 6,383 | 1 | 6k |
| C21 | Short governed task without a Mission | important | `dispatch`, Op records, invocations, session hooks | `invocation/` 5,367; four command modules 1.7k (M6) | 4 | 7k |
| C22 | Outside program drives a Mission by contract | important | orchestrator API (27 verbs, contract 1.31.0), `next --json`, agent subcommands, MCP adapter | `orchestrator_api/` 5,855 | 4 | 6k |
| C23 | Unattended run up to a human decision | important | `next` loop, implement-review skill, external orchestrator, decision loop | as C05; `spec-kitty-orchestrator` 4.1k | 4 | in C05 |
| C24 | Progress visible to a person and a tool | core | `agent tasks status`, `orchestrator-api mission-state`, `events tail`, read service (not launched), dashboard (removed) | `status/read_surface.py` 835; `agent/tasks_status_cmd.py` 1,112 | 5 | in C06 |
| C25 | Other systems consume lifecycle events | speculative | produce seam, events contracts, write service, event-router | `status/adapters.py` 340; `services/` 2,111 | 4 | 3k |
| C26 | Finished Missions feed proposals into the rules | important | `retrospect`, synthesis | `retrospective/` 8,483; 2,431 in commands | 2 | 11k |
| C27 | Upgrade without losing work in flight | important | `upgrade`, migration ledger, 14 `migrate` subcommands, compatibility code | `upgrade/` 33,155; `migration/` 12,003; `compat/` 5,161 | 4 | 50k |
| C28 | Start from and report to an issue tracker | optional | tracker (local providers), intake origin, issue matrix | `tracker/` 2,652 | 3 | 3k |
| C29 | Diagnose and repair a broken setup | important | `doctor` (19 to 25 subcommands by source), `verify-setup` | 18 doctor modules, 9,877 | 4 | 10k |
| C30 | Several Missions without identity confusion | important | `mission_id`, `mid8`, slug, branches, selectors | `context/mission_resolver.py`; 97 resolver-like functions (X1 2.4) | 4 | 2k + spread |
| C31 | Close, reopen, follow up, archive | optional | `mission close/reopen/follow-up`, `archive` | commands only | 2 | small |
| C32 | Clones share Mission state through git | important | committed status log, origin gate, ledger partitions, event-log merge driver | `status/event_log_merge.py`; `git/origin_freshness.py` | 3 | in C06 |

Package figures are [executed K1]; M-figures are as cited.

Two readings matter. The four capabilities with the most mechanisms are the four the README sells: next action (6), isolation (6), landing (7), rules once (6). And some narrow needs have large carriers: C11 states three properties and is carried by about 64,500 lines (M7 section 4); C16 has two complete implementations with no traffic between them (M5 section 6).

### Capabilities without a journey, and journeys without a carrier

| Kind | Item | State at head | Source |
|---|---|---|---|
| Capability, no journey | `mission close/reopen/follow-up`, `archive` (C31) | reference text only | N1 section 4; CH confirms no guide |
| Capability, no journey | topology choice (`--topology`) | one guide mentions it; no guide says how or why to choose | N1 section 4; M1 E7 |
| Journey, no carrier | client sees progress without source access (J10) | dashboard removed; read service not launched by the CLI | N1 section 4 |
| Journey, no carrier | tracker issues into work packages | local trackers only | N1 section 4 |
| Journey, no carrier | publish after landing | no such command; `consolidate` lands locally | N1 section 4 |
| Journey, weak carrier | a custom mission "appears as an option during specify" (J9) | installed commands are the software-dev step list | `skills/command_installer.py:98-114` [read K1] |

## 3. Who owns each responsibility today

"Places" counts where the rule is actually held.

| # | Rule or fact | Declared owner today | Places | Across repositories | Source |
|---|---|---|---|---|---|
| 1 | Work-package lane vocabulary and legal moves | `status/wp_state.py` (883 lines) | 5 to 7 | core, `spec-kitty-events` (Python, twice; Java), orchestrator | M3 section 6; M4 5.2; CH CA06 |
| 2 | Fold of events into current state | `spec_kitty_events.diary.reduce_parsed` | 4 implementations, 2 languages | core wraps the package; Java read and write each fold | M4 5.2 |
| 3 | Where a Mission's status is read from | `status/read_surface.resolve_status_read` | 5 | Java `ReadDirResolver` restates it | M1 section 6 (E9, E37) |
| 4 | What topology a Mission has | `meta.json` `topology` | 5 readings; an unstamped Mission is `lanes` at runtime, `single_branch` when backfilled, `unknown` in the events contract | Java `Topology` | M1 section 6; M8 section 6 |
| 5 | A Mission's target branch | none | about 22 resolver functions | no | X1 2.1 |
| 6 | The Mission branch name and value | none | 2 modules give the name; `meta.json` and `lanes.json` both store the value | no | M1 E40, E41 |
| 7 | What a protected branch is; what to say | `git/protection_policy.py` | policy 1; about 40 `*protected*` functions; the refusal rendered 4 times | no | X1 2.2 |
| 8 | "Approved or done" as the accepted set | `status_lanes.py:53` | 34 literal restatements | no | X1 2.3; M3 section 6 |
| 9 | How a Mission handle resolves | `context/mission_resolver.py` | the canonical one plus private resolvers in command modules | no | X1 2.4 |
| 10 | Work-package dependencies | none | 3 (`wps.yaml`, `tasks.md` prose, frontmatter) | no | M3 section 6 |
| 11 | Dependency readiness; which work package is claimable | `core/dependency_graph.py:35` | 4 to 5 | Java `ClaimRules` | M3 section 6; M6 section 6 |
| 12 | Claiming a work package | none | 2 (`agent action implement`; `orchestrator_api/wp_lifecycle.py`) | no | M6 5.5 |
| 13 | Reviewer is not the author; owned-file evidence | `status.actor_identities_independent` | 4 to 5 entry points run it | no | M7 section 6; M3 section 6 |
| 14 | Landing a Mission | `consolidation/` executor | 2 executors with different guarantees | no | X1 3.1; `orchestrator_api/consolidation.py:586` [read K1] |
| 15 | "Is this path bookkeeping" | none | 4 | no | M7 section 6 |
| 16 | Step order of a mission type | none | 7 surfaces, which disagree | pack and core | M2 5.1 |
| 17 | What a step must produce; its exit check | none | 5 (manifest, `mission.yaml`, Python guards, prompt text, contract) | pack and core | M2 section 6 |
| 18 | The set of built-in types | none | 7 tables; two of them list two or three types | no | M2 section 6 |
| 19 | Whether a rule is in force | activation ledger | 5 sources united for directives; 2 full implementations with different meanings of an absent key | core Python, `spec-kitty-charter` Java | M5 5.2, section 6 |
| 20 | What governance text reaches an agent | `charter` context builder | 6 delivery paths, with different arguments | no | M5 E13 |
| 21 | The list of agent tools and their paths | `.kittify/config.yaml` for the choice; none for the table | 10 to 12 tables | orchestrator adapters; skill prose | X1 1.8; M6 5.7 |
| 22 | Mission position (which step) | run cursor (clone-local) for non-work-package steps; the board after `tasks` | 2 to 3 | no | M3 5.4; M6 5.1 |
| 23 | "This project needs migration" | none | 3 (schema integer, ledger diff, 26 subsystem refusals) | no | M8 5.2 |
| 24 | Which files of projected commands and skills the tool owns | none | 3 to 4 manifests | no | X1 3.7 |

Three rules outside the table have one owner that callers do ask: the lane legality check inside the transition pipeline, the origin-freshness gate (M7 section 6), and the migration order manifest.

### Who owns each store

M3 lists 17 stores of lifecycle state; the registry `state/contract.py` lists 62 surfaces (CH CB10). Those with a contested owner:

| Store | Holds | Authority today | Contest |
|---|---|---|---|
| `status.events.jsonl` | lane moves and five other row shapes | authoritative for lanes | location depends on topology; two aggregate keys in one file (M3 5.3) |
| `status.json` | reduced snapshot | derived, yet committed | treated as a store; needs a merge driver (M3 5.9) |
| `meta.json` and `lanes.json` | topology, branches | both | a refusal, a migration and a doctor exist for their disagreement (X1 4.1) |
| `.kittify/runtime/runs/<id>/state.json` | step cursor | authoritative for non-work-package steps | gitignored, so absent in a second clone (M3 5.4) |
| work-package frontmatter | definition plus runtime fields | mixed | lane mirror still written (`status/emit.py:640, 823, 879, 1207` [read K1]) |
| `activation.yaml`, legacy keys, `charter.yaml` selections | rules in force | ledger, with legacy reads | three generations (X1 4.4; M5 5.2) |

## 4. The command layer (`src/specify_cli/cli`)

This is my own light look, made because the challenge found that no input gave the package a disposition (CH F4). All figures [executed K1]; the script splits each module into functions that carry Typer options or a command decorator ("entry functions") and everything else.

| Measure | Value |
|---|---|
| Files, lines | 194 files, 107,407 lines: 20% of core |
| Command entry functions | 198 functions, 18,096 lines (17%) |
| Other module-level functions and classes | 2,668 definitions, 67,966 lines (63%) |
| Modules with no command entry at all | 113 of 194 files, 51,477 lines (48%) |
| Refusal-style code literals defined or used | 154 distinct |
| Modules that run git themselves | 33 |
| Topology vocabulary (`single_branch`, `lanes_with_coord`, `MissionTopology.`) | 188 lines in 27 files |
| Built-in mission-type name as a literal | 37 lines in 14 files |
| Source files outside `cli/` that import from `cli.commands` | 14 (four in `orchestrator_api/`; others in `status/`, `review/`, `policy/`, `tasks/`, `upgrade/`, `migration/`) |

What it holds, by group:

| Group | Files, lines | What is in it | Wiring or rules |
|---|---|---|---|
| `commands/agent/tasks*.py` | 20, 16,999 | `move-task` with its gates (`tasks_move_task_gates.py`, 1,703), hop logic, verdict persistence, requirement mapping, status rendering | mostly rules: the command-level guards of M3 5.7 live here, and a second generation of the same module beside the first (X1 6.4) |
| `commands/agent/mission*.py` | 19, 14,900 | Mission creation, `setup-plan`, `finalize-tasks` (planning-commit pin 1,623; lanes; commit; bootstrap; validation) | mostly rules: M1's planning pin and topology settlement are driven from here |
| `commands/agent/workflow*.py` | 3, 6,196 | `agent action implement` and `review`: claim, workspace, context | rules plus compensation for lanes and worktrees (M6 section 7) |
| `commands/charter/` | 32, 12,135 | 19 subcommands; activation, synthesis | about a quarter wiring |
| doctors (`doctor.py`, `_*_doctor.py`) | 18, 9,877 | diagnosis of coordination, command surface, decisions, identity, review cycles, sparse checkout | diagnosis logic; each doctor mirrors a mechanism that can enter a bad state (X1 class 5) |
| `upgrade.py`, `migrate_cmd.py`, `migrate/` | 8, 6,725 | upgrade driver and 14 operator backfills | rules of M8's channels B and C |
| `implement*.py` | 6, 3,237 | top-level `implement`: claim, phases, planning commit | duplicate of the `agent action` path (M6 section 7) |
| `consolidate.py`, `accept.py` | 2, 3,656 | 22 and 16 flags; `accept` runs gates of its own | M7 section 5 |
| `next_cmd.py`, `lifecycle.py`, `dispatch.py`, `decision.py` | 4, 3,697 | the loop's command, the lifecycle shims, dispatch, Decision Moments | mixed |
| about 50 other modules | about 21,000 | `init`, `mission_type`, `retrospect`, `glossary`, `tracker` and others | mixed |

Reading: the package is not a thin interface. Roughly one line in six is command wiring. It is where rules that have no owning module ended up: the work-package guards that only `move-task` runs, the finalize and planning-pin logic, one of two claim paths, and a doctor per failure-prone mechanism. Other layers treat it as a domain layer: 14 modules outside it import from it. The package therefore has no complexity of its own to assess; its size is the sum of the eight mechanisms' unowned rules. Limits: I classified by function signature and file name, not by reading each module; the split between "rules" and "rendering" inside the 63% is not measured.

## 5. Where core's lines are

[executed K1], Python only, `__pycache__` excluded.

| Layer or package | Files | Lines | Carries |
|---|---|---|---|
| `src/specify_cli/cli` | 194 | 107,407 | every capability's commands and many rules (section 4) |
| `src/charter` | 252 | 77,725 | C16 to C19, C14 definitions |
| `specify_cli/consolidation` | 63 | 36,414 | C11 |
| `specify_cli/upgrade` | 178 | 33,155 | C27 (144 registered migrations; 155 modules with helpers, CH CA11) |
| `specify_cli/status` | 52 | 21,397 | C06, C09, C24 |
| `src/runtime` | 36 | 17,627 | C05, C14, C23 |
| `specify_cli/lanes` | 29 | 16,574 | C07, C08 |
| `specify_cli/coordination` | 24 | 15,036 | C06 placement, C07 |
| `specify_cli/tool_surface` + `skills` | 64 | 17,229 | C02 |
| everything else (about 70 packages; sizes of those named in section 2 are given there) | 598 | 182,372 | review, acceptance, migration, core helpers, placement, API, retrospective and others |
| **Total** | 1,490 | 524,936 | |

Outside core, the same capabilities are also carried by: `spec-kitty-events` (Python package 18.6k lines; Java services 19.5k main, 44k test; M4 section 4), `spec-kitty-charter` (Java about 137,000 main, 204,000 test; M5 E7), `spec-kitty-open-packs` (19 packs; built-in about 290 artefacts; M5 E9), `spec-kitty-orchestrator` (4.1k), `spec-kitty-mcp`. The read service has no caller and the charter service no client in core (M4 5.8; M5 E29): both are **intended target, not in use**.

## 6. Disagreements and limits

| Point | Positions | What would settle it |
|---|---|---|
| Is "several clones write one Mission's status" a need (C32)? | N1 rates C32 important but "implied". M1, M3, M4 treat multi-clone writes as hypothetical. ST S1 shows it is a recorded scenario with three issue numbers | a ruling on whether Mission state is shared through git or through a service |
| Is a local landing without a forge a need (C11)? | M7 says not documented. ST S2 cites the solo-developer guide, which ends at local consolidation | a ruling; the guide exists (`docs/guides/how-to/scenarios/solo-developer-workflow.md:131-136`, per ST) |

Limits. Line figures per capability are overlapping package totals. I did not re-read the Java repositories; their figures are the assessors'.
