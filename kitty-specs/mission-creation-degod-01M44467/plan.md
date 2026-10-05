# Implementation Plan: Mission creation degod

**Branch**: `issue-5634-mission-creation-degod` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/mission-creation-degod-01M44467/spec.md`

## Summary

Split `src/specify_cli/core/mission_creation.py` (2,363 LOC, 46 top-level definitions over 14 responsibilities) into one pure decision module plus ten effect-adapter leaf modules. The create module stays as a façade that keeps the public entry point and the orchestrator (`create_mission_core`, `_create_mission_core_impl`) and re-exports every moved name. It follows the PR #5679 pattern. The work is test-led:

1. A zero-patch golden matrix is captured on the unchanged code, with tests for the ten uncovered branches. It must be green before anything moves.
2. Pure decision cores are introduced in place: the existing functions delegate to them.
3. The leaf modules are moved verbatim, with a patch-interception routing check and the architectural gates re-pointed.
4. Behaviour-neutral seam cleanups.
5. The façade patch sites (279 by the WP04 census) move onto the seams.

The work does not change behaviour. Three items stay out because each changes behaviour (follow-up: #5676, #5704, #5707).

## Engineering Alignment (planning answers)

The operator's dispatch brief answers the planning questions. It asks for a semi-automatic run, so these answers were not asked again interactively.

| # | Question | Answer (source) |
|---|---|---|
| 1 | Where does the topology *default* decision get extracted? | It is not extracted. It already lives in `cli/commands/agent/mission_create.py::_resolve_default_topology_phase` and delegates to the pure `coord_topology_reachable`. It is pinned by tests and not moved (spec FR-010, C-007; grounding G3/T-findings). |
| 2 | Façade keeps the orchestrator, or does it move too? | The façade keeps it. That way the façade-resolved calls (`ULID`, `_emit_create_events`, `_commit_create_scaffold`, …) keep intercepting with no routing (architect §3). |
| 3 | How strict is "byte-identical"? | Every observable listed in FR-001, *and* the point at which each error is raised (C-001). The golden test and its normaliser are frozen after WP01 (NFR-001). |
| 4 | Is a gate allowed? | Only liveness, routing and purity checks, each with an empty allowlist. Size and count ratchets are not allowed (C-002, operator ruling). |
| 5 | Are the occupancy and orphan-scaffold fixes folded in (follow-up: #5676, #5704)? | No (decision `01M446WTGDPEAGV4MSRD1CJK75`). The facts shape of `decide_protected_mint` is designed so each becomes a one-precondition change. |

## Technical Context

**Language/Version**: Python 3.11+ (mypy runs with `follow_imports=skip` for `specify_cli.*`, so each leaf must type-check on its own)
**Primary Dependencies**: existing only: typer, rich, ruamel.yaml, `ulid`, pytest, pytest-xdist. No new dependency.
**Storage**: files and git (mission scaffold, `meta.json`, `status.events.jsonl`, refs)
**Testing**: pytest. The golden matrix runs against real temporary git repos (`clone_template`, `provision_test_charter`), with zero patches. Pure-core unit tests use plain inputs. Gate files are named individually; full heavy suites are never run (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: Linux/macOS/Windows CLI (unchanged)
**Project Type**: single project (`src/specify_cli`)
**Performance Goals**: the golden files take at most 45 s wall under `-n 4 --dist loadfile` (NFR-002). Create latency is unchanged; the refactor adds no extra git calls.
**Constraints**: byte-identical behaviour and error timing (C-001); verbatim moves (C-003); the routing rule (C-004); a stable public surface and logger name (C-006); file set (C-007); order of work (C-008).
**Scale/Scope**: one source module becomes 1 façade, 1 pure module and 10 adapters. About 33 test files are touched by the patch migration, plus about 6 architectural gate files.

**Supply-chain**: no dependency is added, removed or upgraded, so `DIRECTIVE_051` has no control to evaluate (recorded as not applicable).

## Charter Check

| Charter rule | How this plan complies |
|---|---|
| Single canonical authority | Cores delegate to `ProtectionPolicy.is_protected_target`, `topology_mints_coordination_branch`, `mission_branch_name` and `classify_topology`. The two topology-based copies of the coordination-routed predicate become one; the third site keys on other inputs (FR-003, FR-009, WP05 fold 4). |
| Architectural alignment / layer rules | New modules stay inside `specify_cli.core`. The `landscape` layer rules constrain only top-level packages, and `test_integration_boundary` already scans all of `core/` (grounding gates §C). |
| DDD + tiered rigour | Pure cores carry the highest rigour: direct unit tests and planted breaks. Adapters are thin and covered through the golden matrix and fault injection. |
| ATDD-first / red-first (C-011) | WP01 and WP02 are test-only and land first. For a structural refactor, "red" means a planted break per captured dimension (recorded in the review record), because the behaviour itself must stay green. |
| Standing Order 2 (campsite, tidy-first) | The whole mission is the tidy-first enabler for the follow-up: #5676 and #5704. Boy-scout fixes are limited to touched tests (faked branches, dead patches, sleeps). |
| Standing Order 4 (test remediation) | Judge the test, not the blame. Retire only with a named guard plus a planted break. Never retry to green. |
| Standing Order 5 (gate discipline) | Every new check starts empty and carries a self-mutation control. No allowlist, no baseline bump. |
| Standing Order 3 (tracer files) | `traces/` is seeded; implementers append to it. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Each WP's validation names test files and gate files explicitly. The refactoring procedure's "full suite" step is replaced by this blast-radius rule. |
| Terminology canon | Mission, never Feature, in new prose and identifiers. "Routing" always names the patch-interception sense. |

Post-design re-check: there are no violations, so no Complexity Tracking entry is needed.

## Project Structure

### Documentation (this mission)

```
kitty-specs/mission-creation-degod-01M44467/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── research/code-grounding.md, research/test-remediation.md   # grounding squad
├── traces/ (tooling-friction, approach, design-decisions)
├── checklists/requirements.md
└── tasks.md + tasks/WP*.md   # /spec-kitty.tasks
```

`contracts/` is intentionally absent. The mission defines no external interface, so `meta.json` carries `"contracts": "none"` with a rationale.

### Source Code (repository root)

```
src/specify_cli/core/
├── mission_creation.py                    # façade: create_mission_core, _create_mission_core_impl, re-exports (x as x), logger
├── mission_creation_errors.py             # MissionCreationError, MissionAlreadyExistsError, MissionBranchExistsError, MissionCreationResult
├── mission_creation_decisions.py          # PURE: facts dataclasses + decide_* / plan_* functions (data-model.md)
├── mission_creation_identity.py           # KEBAB_CASE_PATTERN, _validate_create_inputs, _Purpose/_resolve_purpose, mid8/dir-name derivation helper
├── mission_creation_roots.py              # _CreateRoots, _resolve_create_roots
├── mission_creation_duplicates.py         # _list_mission_scaffolds, _prior_mission_is_abandoned, _find_live_duplicate_mission, _refuse_live_duplicate
├── mission_creation_protected_mint.py     # _refuse_target_without_commit, _target_is_protected, _protected_mint_applies, _mint_protected_single_branch_mission_branch, _refuse_protected_recreate, _mint_protected_branch_for_topology
├── mission_creation_scaffold.py           # TASKS_README_TEMPLATE, render_tasks_readme_content, _Governance/_resolve_create_governance, _Scaffold/_scaffold_mission_dir
├── mission_creation_meta.py               # _MetaBuild, _build_create_meta
├── mission_creation_events.py             # _emit_create_events, _commit_coord_create_events, _CoordCreateSeed, _seed_coord_surface_for_create
├── mission_creation_commit.py             # _commit_feature_file, _CommitOutcome, _commit_create_scaffold, _consume_pending_origin_if_present, _build_create_result
└── mission_creation_rollback.py           # _list_coordination_branches, _rev_parse_or_none, _path_is_tracked_by_git, _failure_is_disposable_create_refusal, _plan_orphan_scaffold_removal, _remove_orphan_mission_scaffolds, _CoordCreateRollbackContext, _rollback_coordination_surface, _restore_git_state_after_failed_create

tests/
├── _support/mission_creation_source.py    # family module list (derived from disk) + source/AST helpers, with self-test
├── _support/patch_census.py               # reporting tool: static + runtime patch counts (NOT a gate), with self-test
├── core/golden/mission_create_<family>.json # per-family snapshots, captured on base sha (recorded in file)
├── core/test_mission_creation_golden_*.py   # zero-patch golden (core level; split by family for loadfile)
├── specify_cli/cli/commands/agent/test_mission_create_golden_cli.py
├── core/test_mission_creation_decisions.py        # pure-core unit tests
└── core/test_mission_creation_family.py           # re-export identity, no module-scope façade import, logger pin, routing set-equality + planted controls, local-import pin, exactly-once proof (purity check: test_mission_creation_purity.py)
```

**Structure Decision**: single project. The `mission_creation_` prefix keeps the module family greppable and lets the gates derive the family from disk. The final assignment of each definition is fixed in WP06 by the exactly-once proof. The layout above is the target, and the implementer may adjust it only to break a real import cycle (recorded as a deviation).

## Phase 0: Research

See [research.md](research.md). Every open question from the spec has a decision there, and the grounding squad's findings are dispositioned in `research/code-grounding.md` and `research/test-remediation.md`.

## Phase 1: Design

- [data-model.md](data-model.md): the facts and decision value types of the pure cores, and their invariants.
- [quickstart.md](quickstart.md): how to run the golden matrix, the patch census and the gate files.
- Contracts: none (see above).

## Implementation Concern Map

### IC-01 — Golden behaviour matrix and census baseline

- **Purpose**: freeze today's observable create behaviour (core and CLI) and today's patch use, so every later step is measured against it.
- **Relevant requirements**: FR-001, FR-002, FR-011, NFR-001, NFR-002, NFR-004 (baseline), SC-001, C-008.
- **Affected surfaces**: `tests/core/golden/`, `tests/core/test_mission_creation_golden_*.py`, `tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py`, `tests/_support/patch_census.py`. Test-only.
- **Sequencing/depends-on**: none.
- **Risks**:
  - Fixture cost: reuse `clone_template`.
  - A normaliser that is too broad: whitelist only mission_id, mid8, ISO timestamps and absolute paths.
  - Flakiness: the baseline-red #5706 fan-out leak. Golden cells must not depend on fan-out registry state.
  - Capture on the base sha, then prove reproducibility.

### IC-02 — Coverage of uncovered decision branches

- **Purpose**: cover the ten decision branches that no test exercises today, on the unchanged code.
- **Relevant requirements**: FR-008, SC-004, C-008.
- **Affected surfaces**: new focused test files under `tests/core/`. Test-only. Fault injection on unchanged code uses the current module names; IC-05 moves those tests onto seams.
- **Sequencing/depends-on**: none (in parallel with IC-01).
- **Risks**: some branches are reachable only by fault injection. Each such test must still fail on a planted break of its branch.

### IC-03 — Pure decision cores (strangler in place)

- **Purpose**: introduce `mission_creation_decisions.py` with the facts and decision types, and make the existing functions in `mission_creation.py` delegate to it, without moving anything else yet.
- **Relevant requirements**: FR-003, FR-009 (predicate single source), US1.
- **Affected surfaces**: `src/specify_cli/core/mission_creation.py`, `src/specify_cli/core/mission_creation_decisions.py`, `tests/core/test_mission_creation_decisions.py`, the purity check.
- **Sequencing/depends-on**: IC-01, IC-02.
- **Risks**:
  - Re-encoding an authority: delegate instead.
  - Changing error timing: gathering facts must happen at the same point where each probe ran today.
  - Unwired cores: a planted break per core must turn a golden cell red.

### IC-04 — Verbatim module split, routing and gate re-pins

- **Purpose**: move each responsibility into its leaf module verbatim. The façade re-exports moved names, and leaves route patched names through the façade module object.
- **Relevant requirements**: FR-004, FR-005, FR-006, C-003, C-004, C-006, C-007, SC-002, SC-005.
- **Affected surfaces**:
  - the 10 new leaf modules and the façade;
  - `tests/core/test_mission_creation_family.py`, `tests/_support/mission_creation_source.py`;
  - re-pinned gates:
    - `tests/architectural/test_single_mission_surface_resolver.py`
    - `tests/architectural/test_no_write_side_rederivation.py`
    - `tests/architectural/test_mission_resolver_walker_gate.py`
    - `tests/specify_cli/cli/commands/test_commit_recipes.py`
    - `tests/core/test_adapters.py`
    - the mission-type reader census
  - a module map in the façade docstring and in `docs/` (where the precedent added one); `CHANGELOG.md` (Internal).
- **Sequencing/depends-on**: IC-03.
- **Risks**:
  - Patch interception silently lost: enforced by the routing set-equality check.
  - Import cycles: lazy imports only.
  - The dead-symbol gate: move constants with their readers.
  - The collection-time descriptor in the single-mission surface resolver.
  - The pinned count of the `_PRE_*` list: do not add there.
  - Rebase churn on a file that changed 6 times in 4 days: rebase immediately before this step.

### IC-05 — Behaviour-neutral seam cleanups

- **Purpose**: make the seams match the responsibilities.
- **Relevant requirements**: FR-009, C-001.
- **Affected surfaces**: the leaf modules from IC-04.
- **Sequencing/depends-on**: IC-04.
- **Risks**:
  - Error timing: protection is resolved lazily and memoised, never earlier than today.
  - The `commit_to_target` dual source is kept.
  - The golden matrix, including the malformed-protection-config cell, proves neutrality.
- **Changes**:
  - Resolve protection at most once per create (memoised at the first-use point).
  - Invoke the protected mint from the orchestrator instead of from inside `_build_create_meta` (same order).
  - Replace the rollback list holder with a typed journal.
  - Split `_build_create_result` fan-out from the pure file sets.

### IC-06 — Move the tests onto the seams

- **Purpose**: replace façade patch stacks with pure-core tests, real-repo behaviour tests or adapter-targeted fault injection, retiring dead patches with proof.
- **Relevant requirements**: FR-007, NFR-004, SC-003, C-005, US3.
- **Affected surfaces**: the 33 patch-carrying test files (inventory in `research/test-remediation.md` §2), `tests/_support/patch_census.py` (final report).
- **Sequencing/depends-on**: IC-04, IC-05.
- **Risks**:
  - Fixture laundering: the census counts runtime applications too.
  - Assertion weakening: C-005 log.
  - Keep one end-to-end smoke per behaviour family.
  - Retirements need a planted break or a coverage-context proof.
  - Large file count: split by target name or file cluster.

## Rebase protocol (golden freeze vs a moving main)

`main` moves fast, so the orchestrator rebases at every phase boundary. If a rebase brings an upstream change to `core/mission_creation.py` (or to a module it imports) **before WP06 has split the file**, the orchestrator re-captures the golden files on the rebased, still unsplit code. The re-capture is its own commit, `test(golden): re-capture on rebased base <sha>`, whose message carries the upstream diff, and it updates `base_commit`. After WP06, an upstream change to the create module is ported into the split by hand, as PR #5679 did, and the golden files are re-captured only if the upstream change is itself a behaviour change; that is recorded in the PR. No other route edits the freeze set (NFR-001).

## Validation strategy (per WP; blast radius, not full suites)

- Always run `make test-fast`.
- Always run the golden files plus `tests/core/test_mission_creation_*.py`, `tests/specify_cli/core/test_*mission_creation*.py`, `tests/specify_cli/cli/commands/agent/test_mission_create*.py`, `tests/agent/test_agent_feature.py` and the 42-file covering set (`research/test-remediation.md` §1).
- IC-04 and later also run the gate files listed above, plus:
  - `tests/architectural/test_no_dead_symbols.py`
  - `tests/architectural/test_layer_rules.py`
  - `tests/architectural/test_integration_boundary.py` (if present)
  - `tests/architectural/test_no_legacy_terminology.py`
  - `tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py`
- Static checks: `ruff check`, `ruff format --check --force-exclude <changed files>`, `mypy <changed modules>`.
- Baseline reds to classify, not chase: baseline-red #5705, #5706.
