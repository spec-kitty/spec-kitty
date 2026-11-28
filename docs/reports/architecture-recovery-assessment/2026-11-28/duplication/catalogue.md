---
doc_status: draft
updated: '2026-11-28'
---

# Catalogue of semantic duplication and competing mechanisms (X1)

Assessor X1, profile `paula-patterns`, in squad-delegate mode (the envelope forbids the scout swarm and any hand-off issue; the envelope wins). All references are to `core` = `/home/user/spec-kitty` at head unless a repository is named. Tags: [read], [executed] (a grep whose pattern is given in the note at the end), [inferred]. Counts are pointers for where to look (R15), not proof of excess.

## Conclusion

The same shape repeats in every mechanism looked at. A generic, declared mechanism exists. Beside it runs the older hardcoded one it was meant to replace. The older one still decides for the four built-in mission types and for the common path. The generic one decides only for the cases the older one does not know. So two generations run at once, and the built-in path never exercises the extension mechanism.

Three consequences follow.

1. A fact has several owners, and code exists to detect and repair disagreement between them. Roughly a third of the refusal-style codes sampled guard another mechanism of the tool, not a user need.
2. Core domain rules are restated at each call site instead of asked of one owner. There are about 22 functions that resolve a Mission's target branch and about 34 literal restatements of "approved or done".
3. Transitional arrangements have no end. The word "legacy" appears in 460 of 1,335 non-migration source files.

The need behind most of these capabilities is real. The duplication is in the implementation. Where I recommend deletion, the capability stays unless said otherwise.

## Class 1. Hardcoded special cases beside a configuration mechanism

The first grep is confirmed in substance and corrected in number. Strict comparisons of a mission-type variable against a literal: 13 [executed]. Looser literal comparisons that include step ids named like types: 25 [executed]. Files naming `software-dev` or `documentation` as a literal: 85 in `src`, of which 18 are upgrade migrations [executed].

| Id | Case | Evidence | Nature |
|---|---|---|---|
| 1.1 | **Step guards per built-in type in Python.** `_GUARD_TABLES` maps the four built-in names to four hand-written functions that test step ids such as `scoping`, `gathering`, `discover`, `publish`. A custom type takes a different path: its `expected-artifacts.yaml` blocking set. The built-in packs ship the same manifest (`packs/built-in/missions/research/expected-artifacts.yaml`) and the same step ids (`mission-runtime.yaml`). | `src/runtime/next/runtime_bridge_cores.py:595-641, 798-846, 859-864, 892-905` [read] | Two generations. Generation 1: per-family guard function, marked by the family name as dictionary key. Generation 2: manifest-driven, marked by `blocking_artifact_names`. Bypass of the extension mechanism for exactly the types that define it. |
| 1.2 | **Work-package iteration decided by name.** `mission == "software-dev" or snapshot.wp_driven`. The capability fact `wp_driven` already exists and is derived from the declared steps. | `src/runtime/next/runtime_bridge_composition.py:509`; `runtime_bridge_io.py:971` [read] | Remnant. The literal is redundant if software-dev declares `implement`. |
| 1.3 | **Requirement kinds.** `grammar.py` adds `DR`, `AR`, `QR` when the type is `research`, in five branches. A declared schema (`RequirementKindDeclaration`, `requirement-kinds.yaml`) and a tier-walking loader exist. No built-in pack ships the file, and I found no caller of `load_requirement_kinds` outside its own module. | `src/specify_cli/requirement_mapping/grammar.py:78-83, 196, 287, 362, 379`; `src/charter/offering/missions/requirement_kinds.py`; `src/charter/activation/manifest_loader.py:363` [read, executed] | Bypass, plus indirection with nothing behind it (class 6). The extension mechanism was built and the special case kept. |
| 1.4 | **Capability table in Python.** `BUILTIN_TYPE_CAPABILITIES` holds `code_producing` and `requires_substantive_spec` for the four names. The module's own text says no shipped descriptor declares the key. The descriptors in `packs/built-in/missions/mission_types/*.yaml` are four lines each. | `src/charter/offering/missions/capabilities.py:36-44` [read] | Deliberate default, but in the wrong store. The rule "declared value wins, else table, else false" is three tiers for one boolean. |
| 1.5 | **Type-specific state written at creation.** `if mission == "documentation"` seeds `documentation_state` in `meta.json`; `doc_state.py` re-checks the literal twice; substantive-spec tests branch on `research`. | `src/specify_cli/core/mission_creation_meta.py:262`; `doc_analysis/doc_state.py:275, 407`; `missions/_substantive.py:954`; `cli/commands/agent/mission_setup_plan.py:429`; `mission_finalize_validation.py:81` [read] | Bypass. A pack type cannot have its own creation state or spec test. |
| 1.6 | **Default-type constants.** Sixteen module constants equal `"software-dev"`, eleven outside migrations, under seven names (`DEFAULT_MISSION_KEY`, `_DEFAULT_MISSION_TYPE` five times, `MISSION_TYPE_SOFTWARE_DEV`, `_DEFAULT_RESOLUTION_MISSION`, `_MISSION_TYPE  # V1 always software-dev`). | `core/config.py:43`; `core/constants.py:62`; `decisions/emit.py:66`; `runtime/next/prompt_builder.py:55`; `charter/activation/resolver.py:147` [executed] | A default is legitimate. Eleven owners of it is not. |

Equivalents for the other vocabularies:

| Id | Vocabulary | Evidence | Nature |
|---|---|---|---|
| 1.7 | **Topology.** One stored enum, `MissionTopology`, and three more enums that also say "topology": `LaneTopology` (members `COORD`, `LEGACY`), `WorktreeTopology`, `TopologySurface`. 63 references to a `MissionTopology` member in 20 files; 61 comparisons spread over `core`, `cli/commands/agent`, `lanes`, `coordination`, `mission_runtime`. The placement seam's own docstring forbids conditioning on topology at call sites. | `src/mission_runtime/context.py:44`; `lanes/worktree_allocator.py:77`; `coordination/surface_resolver.py:126`; `mission_runtime/artifacts.py:23` [read, executed] | The seam is generation 2; per-site topology branches are generation 1 and still the majority. |
| 1.8 | **Agents and tools.** At least ten tables keyed by agent: `AI_CHOICES`, `AGENT_TOOL_REQUIREMENTS`, `IDE_AGENTS`, `AGENT_COMMAND_CONFIG`, `AGENT_PROJECT_CONFIG_DIRS`, `AGENT_SKILL_CONFIG` (all `core/config.py:17-213`), `AGENT_DIRS` and `AGENT_DIR_TO_KEY` (`agent_utils/directories.py:26, 45`), `AGENT_DIRECTORIES` (`gitignore_manager.py:363`), `SUPPORTED_AGENTS` (`skills/_agent_roster.py:34`), `AGENT_ARG_PLACEHOLDERS` (`shims/generator.py:57`), plus `tool_surface/profiles/capability_matrix.py`. Twelve literal agent comparisons outside migrations (`vibe` four times, `codex`, `claude`, `copilot`). The canonical `AGENT_DIRS` is re-exported from a migration module (`m_0_9_1_complete_lane_migration.py:567`). | [executed, read] | Two generations: per-agent tables, and the `tool_surface` profile model. Adding an agent is a six-step checklist in `CLAUDE.md`. |

Single owner: the mission-type descriptor in the pack, read through `charter.offering.api`. Deletable: the four guard functions and their step-id branches, the capability table, the research branches in `grammar.py`, the type-specific creation branches. Rough size 800 to 1,200 lines in core, plus the matching tests. The built-in packs would have to declare what the code now assumes. That is a pack-content change in `spec-kitty-open-packs`, not a data migration for users.

## Class 2. The same domain rule in several places

| Id | Rule | Spread | Representative references | Nature |
|---|---|---|---|---|
| 2.1 | **What a Mission's target branch is.** | About 22 resolver functions outside migrations [executed]. | `core/paths.py:690, 918, 959`; `core/git_ops.py:354, 414`; `workspace/context.py:1374`; `coordination/commit_router.py:1333`; `consolidation/resolve.py:450`; `orchestrator_api/consolidation.py:210`; `missions/_resolve_planning_branch.py:68`; `cli/commands/agent/mission_branch_context.py:66, 289, 385` | Five branch notions (target, planning, mission, coordination, primary) each with local derivation. `"main"` or `"master"` literal in 31 files. |
| 2.2 | **What counts as a protected branch, and what to say.** | One policy class, then about 40 functions named `*protected*` [executed]. The same two refusals are rendered four times. | `git/protection_policy.py:145, 261`; `consolidation/preflight.py:1264, 1317`; `consolidation/entry_preflight.py:496, 556`; `consolidation/forecast.py:276, 583`; `orchestrator_api/consolidation.py:478, 495`; duplicate `_protected_branch_status_commit_error` in `cli/commands/implement_claim.py:104` and `cli/commands/agent/tasks_shared.py:384` | The policy has an owner. Its enforcement and wording do not. |
| 2.3 | **"Approved or done" as the accepted set.** | 34 literal restatements [executed]; at least seven named constants. | `consolidation/wp_evidence.py:112, 176`; `consolidation/reconciliation_kernel.py:28`; `review/artifacts.py:27`; `audit/classifiers/wp_files.py:16`; `release/changelog.py:16`; `cli/commands/agent/tasks_move_task.py:1161`; `tasks_transition_core.py:102` | The lane model has no query "is accepted". Each caller rebuilds it. |
| 2.4 | **How a Mission handle resolves.** | 97 functions match resolve/find/locate + mission/feature; five separate `_resolve_mission_slug`, three `_find_mission_slug`, two public `resolve_mission_handle` [executed]. | `context/mission_resolver.py:1027`; `cli/selector_resolution.py:179`; `cli/commands/agent_retrospect.py:73`; `status/read_surface.py:385`; `orchestrator_api/_common.py:167`; `retrospective/generator.py:140` | One canonical resolver exists; command modules keep private ones. |
| 2.5 | **Ready for review.** | Two functions of the same name. | `cli/commands/agent/tasks_parsing_validation.py:1049`; `tasks_shared.py:621` | Parallel old and new module (see 6.4). |
| 2.6 | **Small helpers.** | 343 function names are defined at module level in two or more non-migration modules, of 11,916 [executed]: `_git` ten times, `_generate_ulid` nine, `_run_git` seven, `_is_ancestor` six, `_current_branch` six, `_resolve_repo_root` five. | — | Symptom of module-local reasoning. Nine ULID generators is a rule (identity minting) with nine owners. |

Single owners: a Mission value object that answers target, write and status branch once per invocation; `ProtectionPolicy` returning a typed refusal with its own text; a lane predicate on the lane model; `context/mission_resolver`. Deletable: most of the 22 branch resolvers and the three extra refusal renderers; the size is in the low thousands of lines. Confidence high for 2.2 to 2.5, medium for 2.1 because the five branch notions partly come from lanes and coordination, which other assessors judge.

## Class 3. Competing mechanisms for one problem

| Id | Problem | Competing mechanisms | Evidence | Nature |
|---|---|---|---|---|
| 3.1 | **Consolidating a Mission.** | `spec-kitty consolidate` (62 modules, about 35,500 lines in `consolidation/`) and `orchestrator-api consolidate-mission` with its own `_execute_lane_merge`. The second re-implements the preflights and says of itself that it has "no rollback door" and "merges lanes with no claim and no gate behind it". | `orchestrator_api/consolidation.py:507, 538, 586, 679` [read] | Two generations of one operation with different safety. The weaker one is the public machine contract. |
| 3.2 | **Driving a Mission forward.** | `spec-kitty next`; top-level `implement`; `agent action implement/review`; `agent tasks move-task`; `agent status emit`; `orchestrator-api` lifecycle verbs; and the slash-command prompts that call some of these. | `cli/commands/next_cmd.py`, `implement.py`, `agent/workflow.py`, `agent/tasks_move_task.py`, `agent/status.py`, `orchestrator_api/wp_lifecycle.py`, `runtime_next.py` [read: listing; inferred: equivalence] | The runtime loop is generation 3. Direct lane moves are generation 1 and remain the way work packages actually advance. |
| 3.3 | **Recording a lane transition.** | Two shells over one pipeline: `emit_status_transition` and `emit_status_transition_transactional`. | `status/emit.py:882`; `coordination/status_transition.py:1626`; `status/transition_pipeline.py:313` [read] | Already half consolidated. The second shell exists because of the coordination surface. |
| 3.4 | **Resolving a template or mission asset.** | Two `resolver.py` modules with the same private helpers (`_is_global_runtime_configured`, `_warn_legacy_asset`, `_emit_migrate_nudge`, `_resolve_asset`, `resolve_template`, `resolve_command`, `resolve_mission`). A six-tier chain whose second tier is named `LEGACY`. | `src/charter/offering/resolver.py:73-332`; `src/specify_cli/runtime/resolver.py:1-17, 156-769` [read] | Copy made during the extraction to the charter layer; the original stayed. |
| 3.5 | **Describing a mission type.** | Per type: `mission.yaml`, `mission-runtime.yaml`, `mission_types/<type>.yaml`, `governance-profile.yaml`, `expected-artifacts.yaml`, `actions/`, plus step contracts and `mission-steps/` prompts; plus the Python tables of class 1. | `packs/built-in/missions/` [read] | `mission.yaml` (states) and `mission-runtime.yaml` (step DAG) are two generations of the workflow definition. The artifact manifest says its step names follow `mission.yaml` state ids. |
| 3.7 | **Registry of installed commands and skills.** | `command-skills-manifest.json`, `skills-manifest.json`, `tool-surface-profile-manifest.json`, a bare `manifest.json`. | 13, 11, 1 and 11 references in non-migration source [executed] | Three ownership ledgers for projected files. |
| 3.8 | **Gates over the same evidence.** | `move-task` hop gates, the `for_review` gate, `accept`, the consolidation claim, the reconciliation gate, the orchestrator-api preflights. `CLAUDE.md` states several run the same predicate from different entry points. | `cli/commands/agent/tasks_move_task_gates.py`; `lanes/for_review_gate.py`; `consolidation/wp_evidence.py`; `consolidation/approved_bound.py` [read: listing] | Layered because an earlier gate can be bypassed by a later entry point. |

## Class 4. Competing sources of authority

| Id | Fact | Stores | Reconciling code | Nature |
|---|---|---|---|---|
| 4.1 | Mission topology and branches | `meta.json` (`topology`, `target_branch`, `mission_branch`) and `lanes.json` (`mission_branch`, `target_branch`, lanes) | `TopologyManifestMismatch`, code `SINGLE_BRANCH_CODE_LANES_UNMIGRATED`, a re-stamp migration, `migrate backfill-topology`, `doctor topology` (`mission_runtime/context.py:198-215`; `lanes/models.py:158-159`) [read] | Two stores of one fact, with a refusal, a migration and a doctor for their disagreement. |
| 4.2 | Work-package lane | Event log (authority), `status.json` (derived, named in 86 files), work-package frontmatter (`lane` still read in two places), git lane tips and `refs/spec-kitty/lane-tip/*` | `status/doctor.py`, `status/validate.py`, `_mission_state_doctor.py`, `migrate` WP-status command [read: listing, executed] | A derived file treated as a store. |
| 4.3 | Built-in mission definitions | `src/specify_cli/missions/<type>/mission.yaml` and `packs/built-in/missions/<type>/mission.yaml`, byte-identical for all four types (`diff -q` silent) [executed]. The lint module calls the first "the separate, still-live legacy tree" (`charter/activation/neutrality/lint.py:387`). | none found; they can drift silently | Remnant copy. |
| 4.4 | Charter activation | `activation.yaml` (ledger), legacy keys in `charter.yaml` and `config.yaml`, and, by the stated 4.0 direction, the charter service | legacy read scope, eight doctor codes, a migration, `DenyListWriteRefused` (per `CLAUDE.md`; `charter/activation/activation_ledger.py`) [inferred from the record] | Three generations at once: legacy keys, ledger, service. The ledger is transitional by its own ADR. |
| 4.6 | Lane vocabulary and transition rules | core `status/transitions.py` with `status_lanes`; `spec-kitty-events` `diary.py` and JSON schemas; `spec-kitty-orchestrator` `scheduler.py`, `loop.py`, `host/models.py` | `ALLOWED_TRANSITIONS` is "a non-authoritative derived" table (`status/transitions.py:9`) [read, executed] | Cross-repository. Three repositories each know the nine lanes. |
| 4.7 | Charter domain | Python `src/charter` (about 77,700 lines) and the Java `spec-kitty-charter` service (about 2,000 Java files), both knowing `software-dev` and `research` by name (`service/missions-edge/.../MissionTypeNarrowing.java`) [executed] | the conformance corpus | Transitional by ruling R7; the end is the service. Until then every charter rule has two implementations. |

The event-log family is wider than one log. Non-migration source names more than twenty `.jsonl` files, among them `status.events.jsonl`, `mission-events.jsonl`, `decisions.events.jsonl`, `canonical-events.jsonl`, `run.events.jsonl`, `lifecycle.jsonl`, `ops-index.jsonl`, `op-closures.jsonl` [executed]. Each is a small store with its own reader. The move to the events system (R7) is the natural single owner.

## Class 5. Compensating mechanisms

The sampled set: 1,166 distinct upper-case code-like literals in non-migration source, of which 374 carry a refusal-style word (`REFUSED`, `MISSING`, `STALE`, `DIVERGED`, `UNREADABLE`, `MOVED`, `DIRTY` and so on) [executed]. The first grep's 165 was a narrower pattern; the order of magnitude holds. Grouping by leading word and reading the definitions in `CLAUDE.md` and the modules:

| Family (examples) | Protects against | Disappears with |
|---|---|---|
| `COORD_*`, `COORDINATION_*`, `PROJECTION_TEARDOWN_ABORTED`, `COORD_MOVED_AFTER_LANDING`, `COORD_STATUS_SURFACE_DIVERGED` (about 22) | A second branch and worktree that hold status, moving or diverging from the Mission branch | The coordination branch as a separate git surface |
| `LANE_*`, `DESTROYED_LANE`, `LANE_WORK_TIP_UNKNOWN`, `WORKTREE_*`, `INCORPORATE_*`, `DEPENDENCY_LANE_MERGE_CONFLICT` (about 25) | Lane branches deleted, stale or conflicting; worktrees in the wrong state | Lane worktrees, or one branch per Mission |
| `WRITE_CHECKOUT_*`, `SINGLE_BRANCH_*`, `OWNED_*`, `TOPOLOGY_SETTLEMENT_REFUSED`, `LANES_PROTECTED_TARGET_REFUSED` (about 25) | The interaction of four topologies with protected branches and shared checkouts | A single topology |
| `LANE_MOVED_AFTER_APPROVAL`, `APPROVAL_STAMP_*`, `RESOLUTION_MERGE_UNREVIEWED`, `APPROVED_CONTENT_MISSING`, `CANCELED_*`, `UNEXPLAINED_BRANCH_MOVE` | Unreviewed content reaching the target between approval and landing | Partly essential (the need is real: what lands is what was reviewed). The present form follows from approving a moving branch instead of a commit. |
| `ORIGIN_*` (6) | Stale local evidence | Essential in any design with a remote |
| `ACTIVATION_*`, `LEGACY_*`, `DENY_*` (about 12) | Two activation stores | The legacy keys (4.4) |
| `IMPLEMENTATION_MISSING`, `REVIEW_NOT_INDEPENDENT`, `OWNERSHIP_UNRESOLVED` | Hollow work or self-review | Essential (responsible delegation, R8) |

Other compensators, by count [executed]: 219 functions named drift, reconcile, heal, repair, backfill or restamp outside migrations; 16 doctor modules under `cli/commands/`; 14 `migrate` subcommands of which six are backfills; 155 migration modules and about 33,000 lines under `upgrade/`.

Reading: about three families of five exist because git-level mechanisms of the tool (coordination surface, lanes, topologies) can enter a bad state. This matches the question in R18. The refusal families are evidence that the complexity is in the interaction, since most codes name two mechanisms at once (`LANES_PROTECTED_TARGET_REFUSED`, `COORD_MOVED_AFTER_LANDING`, `STATUS_WRITE_TARGETS_LANE_CHECKOUT`).

## Class 6. Indirection with nothing behind it

| Id | Case | Evidence | Nature |
|---|---|---|---|
| 6.1 | **Event produce seam with no subscriber.** Three `register_*_fanout_handler` functions; no registrant in source besides the re-export; six `fire_*` call sites, each a no-op. | `status/adapters.py:150-318`; grep for registrants returns only `status/__init__.py:234-236` [executed] | Remnant of the removed transport, kept as a seam for a future owner. Transitional with no stated end. |
| 6.2 | **Requirement-kind loader with no caller** (see 1.3). | `charter/activation/manifest_loader.py:363` | Built, never bound. |
| 6.3 | **Re-export facades.** 243 non-migration files mention re-export or facade; 14 modules define `__getattr__` for lazy or compatibility re-export, among them `consolidation/preflight.py`, `status/__init__.py`, `missions/__init__.py`, `runtime/__init__.py`. `reconciliation.py` is a facade over `reconciliation_*.py` and tests patch through a helper. | [executed]; `CLAUDE.md` | A split by file size, not by responsibility; the old import path is kept alive. |
| 6.4 | **Parallel old and new command modules.** `cli/commands/agent/tasks*.py` is 20 files and about 17,000 lines. `tasks_move_task.py` coexists with `tasks_move_task_executor.py`, `_hops.py`, `_gates.py`, `tasks_transition_core.py`; `_APPROVAL_LANES` and the ready-for-review check are defined in both generations. | `tasks_move_task.py:1161`; `tasks_transition_core.py:102` [read] | A decomposition that was not finished: the god module was split and also kept. |

## Class 7. Remnants

Lines and files in non-migration source, case-insensitive [executed]:

| Vocabulary | Lines / files | Still read or written? |
|---|---|---|
| `feature_dir` | 4,353 / 284 | Yes: the standard parameter name for the Mission directory. |
| `feature` (word) | 773 / 188 | Yes: `--feature` flag, `feature_slug` read fallback in events (`status/models.py:674, 1061`; `status/store.py:291`), `get_feature_target_branch`, `mission_feature_resolution.py`. |
| `legacy` | 3,246 / 460 | Yes: resolution tier `LEGACY`, `LaneTopology.LEGACY`, `coordination/legacy_resolution.py`, `legacy_step_id`. |
| `sync` | 682 / 166 | Mixed; the transport is gone, `manifest_version` is still described as "a sync-namespace identity key" in pack files. |
| merge state | 107 / 16 | Yes: `.kittify/runtime/merge/`, `resolve_merge_target_branch`, `policy/merge_gates.py`. |

The terminology canon forbids `feature` for the Mission. The code's most common parameter name is `feature_dir`. Structural remnants are in 4.3 (the copied mission tree), 3.4 (the copied resolver), 6.1 (the transport seam) and 1.8 (`AGENT_DIRS` owned by a migration module).

## Class 8. Parameter and output redundancy

| Id | Case | Evidence |
|---|---|---|
| 8.1 | Branch facts are emitted under nine JSON keys: `target_branch` (25 emit sites), `destination_ref` (13), `mission_branch` (6), `coordination_branch` (4), `current_branch`, `base_branch`, `merge_target_branch`, `planning_base_branch`, `branch_strategy_summary` [executed]. | grep over dict literals in non-migration source |
| 8.2 | Mission selection: `--mission`, `--feature`, positional handle; events accept `mission_slug` or `feature_slug`. | `status/models.py:674` [read] |
| 8.4 | Flags that select behaviours by generation: `legacy_step_id` beside `step_id` in guard dispatch (`runtime_bridge_cores.py:720-752`); 62 distinct `SPEC_KITTY_*` environment variable names in source [executed]. |

## Generations running at once

| Subject | Generation 1 (mark) | Generation 2 (mark) | Generation 3 (mark) | Label for the oldest |
|---|---|---|---|---|
| Mission-type behaviour | Python branches on type name | Capability table and `_GUARD_TABLES` | Pack descriptor, manifests, `wp_driven` | Legacy, retirable |
| Workflow definition | `mission.yaml` states | `mission-runtime.yaml` step DAG with `legacy_step_id` | — | Transitional without end |
| Mission assets | `src/specify_cli/missions/` and `.kittify/templates` (`LEGACY` tier) | `packs/built-in/` through the pack chain | Charter service | Legacy, retirable |
| Status authority | Frontmatter `lane` | Event log plus `status.json` | Events service | Legacy read still present |
| Placement | Call-site topology branches | Placement seam and commit router | — | Current implementation |
| Activation | Keys in `charter.yaml`/`config.yaml` | Activation ledger | Charter service | Ledger is transitional |
| Consolidation | `orchestrator-api` lane~ merge | Claim, gate and rollback authority | — | Public contract; see trade-off |

## The five patterns that cost the most

1. **Compensation for git-surface interaction** (class 5, cases 4.1, 4.2). The coordination surface, lanes and four topologies generate most refusal families, most doctors and much of `consolidation/`. Other assessors own the verdict; the cross-cutting evidence favours removing them together (R18).
2. **Built-in types bypass the pack mechanism** (1.1 to 1.6, 3.5, 4.3). This makes the extension mechanism unproven on the main path and gives every type rule two homes.
3. **Unfinished extractions kept in parallel** (3.4, 4.3, 4.7, 6.3, 6.4). Each extraction added a copy and left the original.
4. **No Mission value object** (2.1, 2.4, 8.1). Branch and identity facts are re-derived per command, so each new rule must be added in many places.
5. **Two consolidation paths with different guarantees** (3.1). The weaker one is the published machine interface.

## The five cheapest to remove

| # | Removal | Why cheap | Consequence |
|---|---|---|---|
| 1 | The copied tree `src/specify_cli/missions/<type>/` (4.3) | Byte-identical to the pack tree | Readers of the old path must be repointed; no user data. |
| 2 | The literal in 1.2 and the eleven default-type constants (1.6) | Mechanical; the capability fact exists | None for users. |
| 3 | The unbound fan-out seam (6.1) and the uncalled kind loader, or bind the loader and delete the `research` branches (1.3) | No caller | A future transport owner re-adds a seam where it is needed. |
| 4 | Duplicate predicates and helpers (2.3, 2.5, 2.6) | One predicate on the lane model; shared git helper | None for users. |
| 5 | One of the two `resolver.py` modules (3.4) | Same functions; one is already declared the source | Import paths change inside core only. |

## Breaking changes implied, as trade-offs (R16)

| Change | Consumers | Data affected | Migration options |
|---|---|---|---|
| Built-in guards from manifests only (1.1) | Every Mission of a built-in type in flight | None on disk; guard outcomes could differ where the Python guard was stricter than the manifest | Make the manifests carry the stricter rule first; run both and compare before deleting |
| Retire `orchestrator-api consolidate-mission` as a separate executor (3.1) | `spec-kitty-orchestrator` (`host/client.py`), any external automation | The envelope contract | Keep the verb, delegate to the one executor; envelope version bump |
| Drop `feature_slug` read fallback and `--feature` (8.2) | Old event logs under `kitty-specs/`, scripts | Historic logs | One rewrite migration, or drop per R6 with a stated cut-off |
| One branch vocabulary in JSON output (8.1) | Command prompts in packs, the orchestrator | Output contract | Emit both for one release, or cut at 4.0 |

## Uncertainty

Would change a decision: whether the built-in Python guards are stricter than the shipped manifests (1.1); whether any external consumer depends on the orchestrator-api consolidation differing from the CLI (3.1). Settled safely by experiment: every "no caller" claim (6.1, 1.3), by deletion in a disposable clone and a targeted test run.

What would change my mind: evidence that the hardcoded built-in path encodes rules the declared mechanism cannot express. I found none.

## Note on the greps

Counts exclude `__pycache__`; "non-migration" excludes `upgrade/migrations/`. Patterns are in `catalogue.csv` references or reproducible from the case text. Rows 1.9, 1.10, 3.6, 4.5, 6.5 and 8.3 are in the CSV only. Source size: 1,335 non-migration Python files; about 525,000 lines in `src`.
