# Code grounding: `core/mission_creation.py` decomposition (#5634)

**Point-cut**: pre-spec / brownfield, adversarial-squad procedure. **Date**: 2026-10-04. **Base**: `origin/main` 9adc6880.
**Squad** (each profile-loaded via `spec-kitty agent profile show`, read-only): architect (`architect-alphonso`), code archaeologist (`researcher-robbie`), gates (`reviewer-renata`), test-suite remediation (`reviewer-renata`, see `test-remediation.md`).

## Measurements (re-measured on current main)

| Metric | Issue said | Measured |
|---|---|---|
| LOC | 2,363 | 2,363 |
| Commits in 90 days | 42 (28 fix) | 42 (28 `fix`, ~8 feat, 5 refactor, 1 style) |
| String monkeypatch targets into the module | 57 | **277 patch sites, 13 distinct names, 33 files** (AST count that resolves `f"{_CORE_MODULE}.X"`; a literal grep misses 215 f-string sites) |
| Max cyclomatic complexity | — | 11 (`_build_create_meta`); ruff and mypy clean |
| Line coverage by the 42 covering test files | — | 95% |

The module is **broad, not tangled**: 46 top-level definitions over 14 responsibilities, with already-extracted phase helpers and an orchestrator (`_create_mission_core_impl`, 298 LOC, mostly docstring). The debt is that every responsibility lives in one namespace that tests patch as a whole.

## Synthesis: what the spec must honour

1. **Layout** (architect §3): `mission_creation.py` stays the façade and keeps `create_mission_core` and the orchestrator, so that the ~250 façade patches keep intercepting where the orchestrator calls. Leaf modules: `_errors`, `_decisions` (pure), `_identity`, `_roots`, `_duplicates`, `_protected_mint`, `_scaffold`, `_meta`, `_events`, `_commit`, `_rollback`. Use the PR #5679 routing rule: a leaf calls any name tests patch on the façade, and any function another family module owns, through a lazy in-function `_mc.` import. No leaf imports the façade at module scope.
2. **Pure decision cores** (architect §1.1): protected-target check over a frozen `ProtectionPolicy` value; `protected_mint_applies`; `decide_protected_mint(facts) -> NoMint | Refuse | Mint`; the coordination-routed predicate (today copied three times, at :1312, :1874, :2020); topology corroboration; meta defaults and flag patch (retention, `pr_bound`, `commit_to_target`, never default-written); duplicate match and abandonment; orphan-scaffold plan; coordination rollback action; scaffold-commit outcome classification; created/uncommitted file sets. Identity (ULID) and clock become inputs.
3. **The topology default is not in this module.** It lives in `cli/commands/agent/mission_create.py::_resolve_default_topology_phase` (:372-445) and already delegates to the pure `coord_topology_reachable`. The no-origin/HEAD caveat is decided there, with `bias=True`. The mission pins it with a decision-level test but does not move CLI code; that file is out of the file set (locality).
4. **Behaviour-preservation invariants** (archaeologist): the #5440 coordination seed (MissionCreated plus SpecifyStarted in the coordination worktree, status log kept off the target); the failed-create restore order (checkout restore first; then orphan branch delete and the coordination rollback, which clears the coordination Mission dir before worktree teardown and before the branch delete or CAS reset; disposable-scaffold removal planned before the index restore). **Erratum (orchestrator check):** the archaeology lens reported "salvage status logs before coordination teardown" helpers; no salvage helper exists in `src/`, so that claim was dropped; the #5100 mint order and refusals (refuse a target without a commit, a dirty-outside-scaffold checkout, or an existing branch; MISSION_ALREADY_EXISTS raised before the mint refusal; the scaffold commit lands on the minted branch); `commit_to_target` is single_branch-only; #4033 duplicate detection stays abandonment-aware; `retain_*` and `commit_to_target` are never default-written (#3131); mid8 is derived once (#3474); the meta commit comes after origin binding; function-local imports stay local (to avoid cycles and to keep the tracker adapter registration order).
5. **Gates to re-point honestly** (gates §A/B, proven by a trial move in a scratch clone that went 10 failed + 20 errors without re-pointing):
   - `tests/architectural/test_single_mission_surface_resolver.py:304`: the `_scaffold_mission_dir` descriptor. It is a collection error that cascades into roughly 20 collect-only gates.
   - `tests/architectural/test_no_write_side_rederivation.py:1381`: the `_emit_create_events` census pair. Also add the new siblings to `_WRITE_DIR_CONSUMER_MODULES`; the scan silently loses scope otherwise. Leave `_PRE_*` alone, because its count is pinned.
   - `tests/architectural/test_mission_resolver_walker_gate.py:21`: the `_list_mission_scaffolds` exemption follows the function.
   - `tests/specify_cli/cli/commands/test_commit_recipes.py:82`: the path key.
   - `tests/core/test_adapters.py:297`: reads only the façade file, so widen it to the family.
   - `test_no_dead_symbols`: move constants and classes together with their readers; no unused `logger`.
   - No new allowlist entries and no baseline bumps.
6. **Patch liveness is the main hidden risk.** 82% of the patch sites patch names the module *imports*. When a reader moves to a leaf, those patches stop intercepting and the test runs real effects while staying green. Mitigation: the PR #5679 routing gate (`_ROUTED_NAMES`, a no-bare-use rule, a stale check and a planted control), plus the family-source helper and re-export identity checks. Extending `test_tasks_patch_targets_live.py`'s scanner to the `mission_creation*` family is a liveness check with an empty allowlist, not a size gate, so it is compatible with the operator ruling.

## Findings disposition

| # | Finding (lens) | Disposition | Where |
|---|---|---|---|
| G1 | Mint runs after the scaffold write; a refusal leaves an orphan without `meta.json`, so the retry is refused MISSION_ALREADY_EXISTS (architect; reproduced by the orchestrator via the CLI) | **deferred_with_rationale**: a behaviour change, out of scope for tidy-first. The golden matrix pins the current behaviour; the `decide_protected_mint` seam makes the hoist small. | #5704 |
| G2 | #5676 create switches an occupied checkout (archaeologist, architect) | **deferred_with_rationale**: a behaviour change. The seam gets an `occupants` fact slot design note only; the fix should land on the #5704 hoist. | #5676 |
| G3 | Primary branch resolved twice with different `bias` (architect) | **deferred_with_rationale**: kept byte-identical; the pure cores take named inputs | #5707 |
| G4 | Protection decision computed twice per create (:555, :1559) | **accepted**: compute the facts once (behaviour-neutral; config cannot change mid-call) | plan, WP04 |
| G5 | Two `commit_to_target` sources (parameter vs `read_commit_to_target(meta)`) | **accepted with proof**: the golden matrix covers meta-exists × commit_to_target before any single-source change; if not provably equivalent, keep both | plan, WP04 |
| G6 | Coordination-routed predicate copied three times | **accepted**: extract once as a first-order concept | plan, WP02 |
| G7 | Rollback holder is a `list` out-parameter | **accepted**: a typed `CreateRollbackJournal` (behaviour-neutral) | plan, WP04 |
| G8 | `test_commit_recipes` red on base (gates; confirmed by the orchestrator) | **deferred_with_rationale**: pre-existing, not ours; recorded as baseline-red | #5705 |
| G9 | Gates that silently lose scope (`_WRITE_DIR_CONSUMER_MODULES`, `test_adapters.py`) | **accepted**: widen in the same WP that creates each module | spec C-004, plan |
| G10 | INV-COORD-HOME residual (an owned coordination create is never seeded on the coordination surface) | **deferred_with_rationale**: a named, pre-existing residual; a behaviour change | already tracked in code comments; untouched |
| G11 | Recent churn (6 commits Oct 1-3) and sibling #5635 (implement.py) | **accepted**: rebase at every phase boundary; no shared helper with `implement.py` was found (overlap is conceptual only: ProtectionPolicy, checkout occupancy) | plan |

---

The full lens reports follow verbatim.


## Appendix A — Architect lens

### Grounding: architect lens on #5634 (de-god `core/mission_creation.py`)

Delegate: architect-alphonso, read-only. Branch `issue-5634-mission-creation-degod`. File measured at 2,363 LOC.

#### 0. Profile and doctrine applied

- **Profile:** `spec-kitty agent profile show architect-alphonso`: design, evaluate, decide; no implementation code. Directives 001, 003, 031, 032, 041, 043, 044, 051. Tactics `dependency-hygiene` and `development-bdd`.
- **Charter context:** `spec-kitty charter context --action specify --json`, bootstrap load. Applied:
  - single canonical authority: one protection decision, one primary-branch resolution, one topology authority;
  - architectural alignment: Modularity SSOT and the `landscape` fixture;
  - DDD splits with tiered rigour;
  - ATDD-first, which makes the golden matrix WP01;
  - `change-apply-smallest-viable-diff`, DIRECTIVE_024 (locality) and DIRECTIVE_025 (Boy Scout, scoped);
  - brownfield-onboarding: investigate before restructuring;
  - ADR `4.x/2026-09-30-1`: allowlists are priced debt, so the split must not grow any allowlist.
- **Refactoring tactics** (`packs/built-in/tactics/refactoring/`):
  - `extract-class-by-responsibility-split`: map clusters, extract one cluster at a time, keep the source delegating;
  - `move-method`: copy, delegate from the old location, migrate callers, then delete;
  - `strangler-fig`: the façade coexists with leaf modules, and patch routing is the coexistence shim;
  - `extract-first-order-concept`: `ProtectedMintDecision`, `CreatePlan`, `RollbackJournal`.
- **Docs read:**
  - CLAUDE.md "Execution Workspace Strategy (2.x)" and "Modularity SSOT";
  - ADRs `3.x/2026-06-22-1` (topology SSOT: "store it, do not guess it"; pure resolver), `3.x/2026-08-12-1` and `3.x/2026-09-03-1` (owned checkout), `4.x/2026-09-30-1` (priced allowlists);
  - PR #5679 body (precedent);
  - issue texts for #5634 and #5676, fetched over the REST API.

#### 1. Responsibility map

Legend: **P** = pure (no git, fs, subprocess, env or clock). **E** = effectful. **E(d)** = effectful, with buried decision logic that can be extracted.

| Def (top-level) | Lines | LOC | Responsibility | P/E | Notes |
|---|---|---|---|---|---|
| `MissionCreationError` | 83-92 | 10 | errors | P | public |
| `MissionAlreadyExistsError` | 95-106 | 12 | errors | P | public, `MISSION_ALREADY_EXISTS` |
| `MissionCreationResult` | 110-134 | 25 | result building | P | public dataclass |
| `KEBAB_CASE_PATTERN`, `TASKS_README_TEMPLATE` | 141-210 | — | input validation / scaffold | P | `KEBAB_CASE_PATTERN` is imported by tests |
| `render_tasks_readme_content` | 213-215 | 3 | scaffold content | P | |
| `_commit_feature_file` | 223-286 | 64 | commit | E | `get_current_branch`, `placement_seam`, `safe_commit`. Tests patch it 47× on the façade |
| `_list_coordination_branches` | 294-318 | 25 | rollback snapshot | E | subprocess |
| `_rev_parse_or_none` | 321-329 | 9 | git probe | E | subprocess |
| `_list_mission_scaffolds` | 332-343 | 12 | rollback snapshot / duplicate scan | E | fs. **Path-pinned exemption** in `test_mission_resolver_walker_gate.py:21-22` |
| `_prior_mission_is_abandoned` | 354-386 | 33 | duplicate detection | E(d) | decision: all WPs canceled, or `event_count==0 and not spec_tracked` |
| `_find_live_duplicate_mission` | 389-440 | 52 | duplicate detection | E(d) | decision: name grammar, type match, fail-closed on unreadable meta |
| `MissionBranchExistsError` | 443-454 | 12 | errors | P | `MISSION_BRANCH_EXISTS` |
| `_refuse_target_without_commit` | 457-480 | 24 | protected mint precondition | E(d) | rev-parse probe plus refusal |
| `_target_is_protected` | 483-501 | 19 | protection decision | E(d) | `ProtectionPolicy.resolve`, `resolve_primary_branch(bias=False)`, then the pure `is_protected_target` |
| `_protected_mint_applies` | 504-521 | 18 | protected mint decision | E(d) | pure except the `_target_is_protected` call |
| `_mint_protected_single_branch_mission_branch` | 524-608 | 85 | protected mint and checkout | E(d) | 1 protection, 2 target has a commit, 3 dirty outside scaffold, 4 branch exists, 5 `git checkout -b`, 6 `meta["mission_branch"]=`. Mixes four decisions with two effects |
| `_path_is_tracked_by_git` | 611-622 | 12 | git probe | E | fail-closed True |
| `_failure_is_disposable_create_refusal` | 625-647 | 23 | rollback classification | **P** | exception-chain walk. Redundant local re-import of types already imported at module scope (:48-53) |
| `_plan_orphan_scaffold_removal` | 650-673 | 24 | rollback planning | E(d) | decision: (post − pre) ∩ slug-grammar − tracked |
| `_remove_orphan_mission_scaffolds` | 676-686 | 11 | rollback | E | rmtree |
| `_CoordCreateRollbackContext` | 690-719 | 30 | rollback | P | dataclass |
| `_rollback_coordination_surface` | 722-777 | 56 | rollback (coordination) | E(d) | decision: delete when created, CAS-reset when reused and moved, else no-op |
| `_restore_git_state_after_failed_create` | 780-858 | 79 | rollback (git) | E(d) | ordering decision: checkout, CAS ref, read-tree, coordination, branch sweep |
| `create_mission_core` | 866-984 | 119 | public API, failure-atomic wrapper | E | inline snapshot of HEAD, index tree, branches and scaffolds. C901 = 9 |
| `_validate_create_inputs` | 987-1017 | 31 | input validation | **P** | |
| `_CreateRoots` | 1021-1034 | 14 | roots | P | |
| `_resolve_create_roots` | 1037-1111 | 75 | root resolution and context guards | E(d) | cwd, worktree, git, unborn and detached guards. C901 = 9 |
| `_refuse_live_duplicate` | 1114-1152 | 39 | duplicate refusal | E(d) | message building is pure |
| `_Purpose` / `_resolve_purpose` | 1156-1177 | 22 | input normalization | **P** | `validate_purpose_summary` is pure |
| `_Governance` / `_resolve_create_governance` | 1181-1235 | 55 | charter/template resolution | E | reads charter config |
| `_Scaffold` | 1239-1249 | 11 | scaffold | P | |
| `_scaffold_mission_dir` | 1252-1371 | 120 | scaffold, placement, recreate refusal | E(d) | buried decisions: `is_coordination_routed = owned is None and mints_coord(topology)`, the scaffold path set, and the protected-recreate refusal |
| `_MetaBuild` | 1375-1397 | 23 | meta | P | |
| `_build_create_meta` | 1400-1532 | 133 | meta build, **coordination branch mint**, **protected mint**, meta write, documentation state | E(d) | **C901 = 11, the highest in the file.** Its name hides a git checkout. See §1.1 |
| `_refuse_protected_recreate` | 1535-1568 | 34 | protected recreate refusal | E(d) | `meta.json` exists AND `_protected_mint_applies` |
| `_mint_protected_branch_for_topology` | 1571-1603 | 33 | protected mint gate | E(d) | reads `commit_to_target` from **meta**, not from the parameter |
| `_emit_create_events` | 1606-1729 | 124 | event emission | E | **path+qualname-pinned** census (`test_no_write_side_rederivation.py:1381`) |
| `_CommitOutcome` | 1733-1740 | 8 | commit | P | |
| `_commit_create_scaffold` | 1743-1838 | 96 | scaffold commit, origin binding, second commit | E(d) | decision: bootstrap-skip vs typed already-exists vs hard failure |
| `_build_create_result` | 1841-1915 | 75 | result building **plus hosted fan-out** | E(d) | `created_files`/`uncommitted_files` is a pure computation, but `fanout_lifecycle_event_hosted` (egress) is buried in a "builder" |
| `_commit_coord_create_events` | 1918-1960 | 43 | coordination commit | E | `commit_for_mission` |
| `_CoordCreateSeed` / `_seed_coord_surface_for_create` | 1964-2038 | 75 | coordination seeding | E(d) | decision: mints coordination? real branch? owned? Also the rollback-holder out-parameter |
| `_create_mission_core_impl` | 2041-2338 | 298 | orchestration | E | ~140 LOC docstring. Mints `ULID()` at :2228 |
| `_consume_pending_origin_if_present` | 2341-2363 | 23 | origin binding adapter | E | `core.adapters` port |

The previous T051 work already split the impl into in-file section helpers (`tests/core/test_mission_creation_decomposition.py`). This mission is phase 2: split into modules and extract pure cores.

### 1.1 Decision logic buried in effectful functions, and the inputs a pure core needs

| Decision | Today | Pure core inputs | Output |
|---|---|---|---|
| **Topology choice (create default)** | Not in this module. It lives in CLI `_resolve_default_topology_phase` (`cli/commands/agent/mission_create.py:372-445`) | `explicit: MissionTopology?`, `owned: bool`, `repo_resolvable: bool`, `current_branch`, `primary_branch` (bias=True!), `pr_bound`, `primary_protected` | `MissionTopology` |
| Topology corroboration | `_build_create_meta:1487-1497` | `topology`, `coordination_branch: str?` | ok, or a refusal message (pure via `classify_topology`) |
| Coordination-routed scaffold | `_scaffold_mission_dir:1312`, `_build_create_result:1874`, `_seed_coord_surface_for_create:2020-2036` (**three copies** of the predicate) | `topology`, `owned: bool`, `coord_skipped: bool` | `is_coordination_routed`, `scaffold_paths` |
| `commit_to_target` validity | `_create_mission_core_impl:2179-2183` | `commit_to_target`, `topology` | refusal or ok |
| **`_target_is_protected`** | `:483-501` (resolves the policy and the primary each call) | `policy: ProtectionPolicy` (already a frozen, I/O-free value, `protection_policy.py:114-121`), `target_branch`, `primary_branch` (bias=False) | bool |
| **`_protected_mint_applies`** | `:504-521` | `topology`, `commit_to_target`, `target_protected` | bool |
| Protected recreate refusal | `_refuse_protected_recreate:1535` | `meta_exists`, `mint_applies`, `dir_name` | refusal or ok |
| Protected mint preconditions | `_mint_protected_single_branch_mission_branch:555-597` | `mint_applies`, `target_has_commit`, `dirty_outside_scaffold: tuple[str]`, `branch_name`, `branch_exists`, plus **(#5676) `occupants: tuple[(mission, wp)]`** | `NoMint`, `Refuse(code, msg)` or `Mint(branch_name)` |
| Retention and override meta flags | `_build_create_meta:1452-1461` | `pr_bound`, `retain_*`, `commit_to_target` | dict patch, with fields absent unless True |
| Meta identity defaults | `_build_create_meta:1437-1451` | `existing_meta`, `mission_id`, `mid8`, slug, names, purpose, type, `planning_branch`, `created_at` (**clock injected**) | dict |
| Documentation state | `:1513-1524` | `mission`, `meta` | doc_state or None |
| Duplicate match | `_find_live_duplicate_mission` | `base_slug`, `mission_type`, `candidates: [(dir_name, meta or UNREADABLE, abandoned: bool)]` | `(dir, mid8)` or None |
| Abandoned | `_prior_mission_is_abandoned` | `wp_lanes`, `event_count`, `spec_tracked`, `read_failed` | bool |
| Disposable failure | `_failure_is_disposable_create_refusal` | exc | bool (already pure) |
| Orphan scaffold plan | `_plan_orphan_scaffold_removal` | `post_names`, `pre_names`, `slug`, `tracked: set` | names |
| Coordination rollback action | `_rollback_coordination_surface:756-777` | `created`, `pre_seed_tip`, `current_tip` | `Delete`, `CasReset(expected, to)` or `Noop` |
| Scaffold commit outcome | `_commit_create_scaffold` except-ladder | exception type | skip, already-exists or raise |
| Created and uncommitted file sets | `_build_create_result:1874-1890` | `scaffold`, `skipped`, `coord_routed`, `log_path` | lists |

#### 2. Callers and the public surface

**Production importers (src):** exactly one, `cli/commands/agent/mission_create.py`. It lazy-imports `create_mission_core` (:647), `MissionCreationError` (:494, :600) and `MissionCreationResult` (:49). No other src module calls `create_mission_core`. orchestrator-api `specify` goes through the CLI. Other src hits are docstrings and comments.

**Names imported by tests** (AST count, `from specify_cli.core.mission_creation import …`):
- `create_mission_core` 58, `MissionCreationResult` 14, `MissionCreationError` 11, `MissionAlreadyExistsError` 3, `KEBAB_CASE_PATTERN` 1;
- private: `_build_create_meta` 5, `_validate_create_inputs` 4, `_mint_protected_single_branch_mission_branch` 3, `_path_is_tracked_by_git`, `_CoordCreateRollbackContext`, `_rollback_coordination_surface`, `_protected_mint_applies`, `_Purpose`, `_plan_orphan_scaffold_removal`, `_restore_git_state_after_failed_create` (1 each).

**Patch targets on the façade** (string, `f"{_CORE_MODULE}.x"` and `setattr` forms combined):

| Name | Hits |
|---|---|
| `is_worktree_context` | ~70 |
| `locate_project_root` | ~45 |
| `get_current_branch` | ~42 |
| `is_git_repo` | ~44 |
| `_commit_feature_file` | ~41 |
| `ULID` | ~11 |
| `preflight_commit` | 5 |
| `safe_commit` | 4 |
| `_commit_create_scaffold` | 2 |
| `create_mission_core` | 6 |
| `now_utc_iso` | 1 |
| `_emit_create_events` | 1 |
| `_commit_coord_create_events` | 1 |
| `_consume_pending_origin_if_present` | 1 |
| `subprocess.run` | 1 (patches the global module; location-independent) |

**No `globals()` or re-export tricks exist today.** `tests/_factories/{__init__,coord_mission}.py` import from and patch the façade, so every factory-driven test depends on it.

**Must stay importable from `specify_cli.core.mission_creation`:** every name listed above, re-exported as `x as x` (strict mypy re-export rule, as in PR #5679).

### Path-pinned structural gates (these follow the code, not the import surface)

- [HIGH] `tests/core/test_adapters.py:297-337` scans **only** `mission_creation.py` for INTEGRATION imports. After the split, leaf modules escape this scan and the gate **weakens silently**. Recommendation: widen it to the `mission_creation*.py` family. `test_integration_boundary.py:69` already covers all of `specify_cli/core`, so the risk is the redundant pin going vacuous, not a real hole.
- [HIGH] `tests/architectural/test_no_write_side_rederivation.py:95` lists the path in `_PRE_WRITE_DIR_ADOPTED_MODULES`, and `:1381` has the census pair `("…/mission_creation.py","_emit_create_events")`. Moving `_emit_create_events` requires re-pinning both. Add the new module to the adopted set, or the boundary contract under-scans it. The `:1123-1198` parity controls use the path as a fixture and can keep it.
- [MED] `tests/architectural/test_mission_resolver_walker_gate.py:21-22` exempts only `_list_mission_scaffolds` *in this file*. If it moves, the exemption must move with it. The gate reds rather than weakening, which is good.
- [MED] `tests/architectural/test_single_mission_surface_resolver.py:305-307` pins the qualname `_scaffold_mission_dir` together with the token `feature_dir = write_root / KITTY_SPECS_DIR / mission_slug_formatted`. Re-pin it to the new module. The `:704-728` bite battery targets `mission_creation.py`; keep the façade non-empty, or retarget the battery to the scaffold module.
- [LOW] `tests/specify_cli/cli/commands/test_commit_recipes.py:83` pins `("core/mission_creation.py","has no commits yet")`. This moves with `_resolve_create_roots`.
- [LOW] `tests/architectural/mission_type_reader_allowlist.yaml:87` is a census row with stale line numbers. Its `"software-dev"` literal appears 8× in the file (S1192 threshold). Hoist it to one `_DEFAULT_MISSION_TYPE` constant in the meta-core module so the census row stays one path and does not grow (ADR 2026-09-30-1).
- [LOW] `tests/release/coverage_breadth_baseline.json:2591` is a point-in-time snapshot keyed by path (`test_coverage_breadth.py`). Verify it does not assert per-file parity for moved lines. The baseline appears to be an evidence record.

#### 3. Proposed target layout (PR #5679 precedent)

All modules go under `src/specify_cli/core/`. The `mission_creation_` prefix keeps the family greppable and lets gates glob `mission_creation*.py`.

| Module | Kind | Owns |
|---|---|---|
| `mission_creation.py` (**façade**) | E (orchestrator) | `create_mission_core`, `_create_mission_core_impl` (slimmed to phase calls), re-exports `x as x`, logger name unchanged. **Keep the orchestrator here.** Its calls to `_emit_create_events`, `_commit_create_scaffold`, `_commit_coord_create_events`, `ULID` and `now_utc_iso` then resolve façade globals, so those patches keep working with no routing |
| `mission_creation_errors.py` | P | `MissionCreationError`, `MissionAlreadyExistsError`, `MissionBranchExistsError`, `MissionCreationResult` (leaf; prevents cycles) |
| `mission_creation_decisions.py` | **P** | Every pure core in §1.1. Frozen dataclasses: `CreateInputs` (validated slug, friendly name, purpose), `ProtectedMintFacts` → `ProtectedMintDecision` (`NoMint`, `Refuse(error_cls, msg)`, `Mint(branch)`), `ScaffoldPlan` (`is_coordination_routed`, `scaffold_paths` as relative `GitPath`s), `MetaPatch`, `DuplicateCandidate` → match, `abandoned()`, `orphan_plan()`, `coord_rollback_action()`, `classify_create_failure()`, `created_file_sets()`. **Imports only** `mission_runtime` enums, `kernel.git.GitPath`, `lanes.branch_naming` (pure) and `core.paths.read_commit_to_target` (pure). An AST gate (no `subprocess`/`Path.cwd`/`os`/clock imports) keeps it honest |
| `mission_creation_identity.py` | P (given an injected ULID) | `mint_identity(ulid_factory) -> (mission_id, mid8, mission_slug_formatted)`. `ULID` stays called from the façade so the `ULID` patch keeps intercepting; or pass `_mc.ULID` |
| `mission_creation_roots.py` | E | `_CreateRoots`, `_resolve_create_roots` (routes `_mc.is_worktree_context`, `locate_project_root`, `is_git_repo`, `has_unborn_head`, `get_current_branch`) |
| `mission_creation_duplicates.py` | E adapter | `_list_mission_scaffolds` (exemption moves), `_prior_mission_is_abandoned`, `_find_live_duplicate_mission`, `_refuse_live_duplicate`: thin I/O feeding pure cores |
| `mission_creation_protected_mint.py` | E adapter | `_target_is_protected`, `_refuse_target_without_commit`, `_mint_protected_single_branch_mission_branch`, `_mint_protected_branch_for_topology`, `_refuse_protected_recreate`, plus a `gather_protected_mint_facts(write_root, …) -> ProtectedMintFacts` query and an `apply_mint(write_root, branch, target)` effect |
| `mission_creation_scaffold.py` | E | `TASKS_README_TEMPLATE`, `render_tasks_readme_content`, `_Scaffold`, `_scaffold_mission_dir` (routes `_mc.preflight_commit`), `_resolve_create_governance` |
| `mission_creation_meta.py` | E | `_MetaBuild`, `_build_create_meta`, split into **pure `MetaPatch`**, a **coordination-branch-mint adapter**, the protected mint **called from the orchestrator, not from the meta builder** (move-method; order preserved: after the coordination mint, before `write_meta`) and `write_meta` plus documentation state |
| `mission_creation_events.py` | E | `_emit_create_events`, `_commit_coord_create_events`, `_CoordCreateSeed`, `_seed_coord_surface_for_create` |
| `mission_creation_commit.py` | E | `_commit_feature_file` (routes `_mc.get_current_branch`, `_mc.safe_commit`), `_CommitOutcome`, `_commit_create_scaffold` (routes `_mc._commit_feature_file`, `_mc._consume_pending_origin_if_present`), `_consume_pending_origin_if_present`, `_build_create_result` (with the pure file-set computation split out and `fanout` kept as the effect) |
| `mission_creation_rollback.py` | E | snapshot capture (extracted from `create_mission_core:898-929` into `CreateRollbackSnapshot.capture(root)`), `_CoordCreateRollbackContext`, `_list_coordination_branches`, `_rev_parse_or_none`, `_path_is_tracked_by_git`, `_plan_orphan_scaffold_removal`, `_remove_orphan_mission_scaffolds`, `_rollback_coordination_surface`, `_restore_git_state_after_failed_create`. Replace the `list` holder out-parameter with a typed `CreateRollbackJournal` (`record_coord(ctx)`). This is behaviour-neutral |

**Routing rule** (copy PR #5679 verbatim): a leaf module calls (1) any function another `mission_creation*` module owns and (2) any name tests patch on the façade through a lazy in-function `from specify_cli.core import mission_creation as _mc`. No leaf imports the façade at module scope. Add a routing gate like #5679's landing fold: every façade-patched name must be referenced as `_mc.<name>` in leaves, never as a bare name.

**Layer rules:** the `landscape` fixture (`tests/architectural/conftest.py:89-118`) layers only top-level packages. Nothing in `test_layer_rules.py` constrains intra-`specify_cli.core` modules. `core` appears only as an allowed `mission_runtime → specify_cli.core` ledger row (:119), which new core modules do not affect, because mission_runtime does not import them. `test_integration_boundary.py:69` scans all of `specify_cli/core`, so new modules are covered automatically. **No layer constraint blocks the split.** The one design constraint: `mission_creation_decisions.py` must not import `specify_cli.lanes.checkout_occupancy` or `ProtectionPolicy.resolve`. Only the adapters do I/O; the decision takes the frozen `ProtectionPolicy` value or a precomputed bool.

#### 4. Where the topology decision lives (end-to-end create chain)

1. **CLI** `create_mission` (`mission_create.py:829-1013`):
   1. `_mission.locate_project_root()`;
   2. `_mint_owned_create_root` (validates `--owned-checkout` once);
   3. `_resolve_start_branch_phase` (may `git switch`);
   4. `get_current_branch(command_checkout)`;
   5. `_enforce_branch_strategy_gate_phase`;
   6. **`_resolve_default_topology_phase`** (:372-445). Order: explicit wins; then owned gives `SINGLE_BRANCH`; then no root or branch gives `COORD`. Otherwise `primary = resolve_primary_branch(repo_root)` with **bias=True**. If `pr_bound`, `coord_topology_reachable(pr_bound, policy.is_protected(primary), current==primary)` (pure, `coordination/surface_authority.py:162`). Else `current==primary` gives `COORD`, and anything else gives `LANES`.
2. **Core** `_create_mission_core_impl`:
   1. validates `commit_to_target` only for `single_branch` (:2179);
   2. sets `planning_branch = target_branch or current_branch` (:2214);
   3. sets `create_time_target = resolve_create_time_write_target(planning_branch)`.
3. **Core** `_scaffold_mission_dir` → `_refuse_protected_recreate` → `_protected_mint_applies` → `_target_is_protected` uses `resolve_primary_branch(write_root, bias=False)` (:500) plus `ProtectionPolicy.resolve(write_root).is_protected_target`.
4. **Core** `_build_create_meta`:
   1. `topology_mints_coordination_branch` (`missions/_create.py:75`, pure) → `ensure_coordination_branch`;
   2. `classify_topology` corroboration (COORD and SINGLE_BRANCH only);
   3. `meta["topology"]` stored verbatim (ADR 2026-06-22-1);
   4. `_mint_protected_branch_for_topology` → `_mint_protected_single_branch_mission_branch` → `_target_is_protected` **again**.
5. **Core** impl: when a branch was minted, it re-derives `create_time_target` from `minted_mission_branch` (:2265-2276).

**No-origin/HEAD caveat.** `resolve_primary_branch` method 1 (`origin/HEAD`) fails. With **bias=True** (CLI default topology) the current branch *is* primary, so a create on any branch resolves to `COORD`, as CLAUDE.md documents. With **bias=False** (core protection), the current branch counts as primary only if it is in `COMMON_PRIMARY_BRANCHES`; otherwise the ladder probes local and origin refs, and if nothing matches it **falls back to the biased cascade**.

Findings:
- [MED] `mission_create.py:435` vs `mission_creation.py:500` — **two primary-branch resolutions with different `bias` in one create.** On a no-origin repo standing on a non-common branch `feat/x` with `main` present, the CLI treats `feat/x` as primary (→ COORD default) while the core treats `main` as primary. That is benign today, because the protected mint is single_branch-only and single_branch is explicit-only. But it is two authorities for one concept. Recommendation: do **not** change it in the tidy refactor. Make `primary_branch` an *explicit, named* input of each pure core (`primary_for_topology_default` vs `primary_for_protection`), so the divergence becomes visible and testable, and file a follow-up.
- [MED] `mission_creation.py:555` + `:1559` — **the protection decision is computed twice** per protected single_branch create, each time doing `ProtectionPolicy.resolve` and `resolve_primary_branch` I/O. Recommendation: gather `ProtectedMintFacts` once, before scaffold, and thread the decision. This is behaviour-neutral, because config cannot change mid-call under the single-writer assumption.
- [LOW] `:1591` vs `:519` — **two `commit_to_target` sources.** The recreate guard uses the parameter; the mint uses `read_commit_to_target(meta)`. `meta` merges a *pre-existing* `meta.json` (`load_meta_or_empty`, :1430), so a stale `commit_to_target: true` or a malformed `"true"` in a reused dir would steer the mint, or raise `CommitToTargetMetaError` (`paths.py:781-806`). They are observably equivalent today only because the recreate guard refuses the meta-exists-and-mint-applies case first. The pure core should take one input, the parameter. Prove equivalence in the golden matrix (meta exists × commit_to_target), or keep the meta read as the adapter's input. **Do not silently pick one.**
- [MED] The coordination-routed predicate is triplicated (:1312, :1874, :2020-2036). Extract it once as a first-order concept, `ScaffoldPlan.is_coordination_routed`.

### #5676 plug-in point (designed seam)

Today `_mint_protected_single_branch_mission_branch` checks, in order: protected → target has a commit → dirty → branch exists → `checkout -b`. It never consults `lanes.checkout_occupancy.in_progress_wps_in_write_checkout` (`checkout_occupancy.py:139`), which `implement` uses (`implement_support.py:169`) to raise `WriteCheckoutOccupiedError` (`WRITE_CHECKOUT_OCCUPIED`, :43-46).

Design:

```
# mission_creation_decisions.py (pure)
@dataclass(frozen=True) class ProtectedMintFacts:
    mint_applies: bool; target_has_commit: bool; dirty_outside_scaffold: tuple[str, ...]
    occupants: tuple[tuple[str, str], ...]   # #5676: empty until the fix lands
    branch_name: str; branch_exists: bool
def decide_protected_mint(f: ProtectedMintFacts) -> NoMint | Refuse | Mint:
    if not f.mint_applies: return NoMint()
    if not f.target_has_commit: return Refuse(MissionCreationError, ...)
    if f.dirty_outside_scaffold: return Refuse(MissionCreationError, ...)
    # #5676 precondition goes HERE (one line + one Refuse with WRITE_CHECKOUT_OCCUPIED)
    if f.branch_exists: return Refuse(MissionBranchExistsError, ...)
    return Mint(f.branch_name)
# mission_creation_protected_mint.py (adapter)
def gather_protected_mint_facts(...) -> ProtectedMintFacts   # the ONLY place git is queried
    # #5676: occupants=tuple(in_progress_wps_in_write_checkout(repo_root, write_root))
```

After the split, #5676 becomes one precondition in `decide_protected_mint` plus one adapter query. Occupancy must be gathered with `repo_root=resolved_root, write_checkout=write_root`. Note that the query returns `[]` when the two differ (owned checkout), which matches `implement`.

Choose where the occupancy refusal sits relative to dirty. Recommended: occupancy **before** dirty, so the operator sees the actionable `move-task` remedy, mirroring `implement`'s order (occupied before dirty, :169-195).

- **[HIGH] latent bug the seam must address. Verified empirically in a scratch repo.**
  - **Location:** the mint runs *inside* `_build_create_meta` (`mission_creation.py:1500`), **after** `_scaffold_mission_dir` has written the mission dir, and before `write_meta`.
  - **Refusal leaves an orphan:** a mint refusal (dirty, target without a commit, branch exists, and #5676 occupancy if added naively) raises `MissionCreationError`. `_failure_is_disposable_create_refusal` returns False for it, so the scaffold is **retained**: `spec.md`, `tasks/`, `status.events.jsonl`, but **no `meta.json`**.
  - **Retry is blocked:** on retry, `_find_live_duplicate_mission` fails closed on the missing meta (`:425-426`) and raises **`MISSION_ALREADY_EXISTS`**.
  - **Probe:** first create refused "uncommitted changes outside this mission's own scaffold". Leftover dir `dirty-probe-01M444E3` contained `[checklists, research, spec.md, status.events.jsonl, tasks/…]`. After the operator cleaned their tree, the retry was refused with `MissionAlreadyExistsError MISSION_ALREADY_EXISTS … dirty-probe-01M444E3`.
  - **Recommendation:** in the decomposition, gather facts and decide **before any scaffold write** (next to `_refuse_protected_recreate`, which already runs pre-write), and keep only `apply_mint` (the `checkout -b`) at its current position. This hoist is a **behaviour change** (no orphan left behind), so it must be its own WP or issue with an explicit operator ruling, not hidden in the tidy-first split. File it as a sibling of #5676. The #5676 fix should land on the hoisted seam, or it inherits the orphan-blocks-retry defect.

#### 5. Complexity and type health

- `ruff C901` at threshold 8: `_build_create_meta` **11**, `create_mission_core` 9, `_resolve_create_roots` 9. **Nothing exceeds 12**, so the file is under the 15 ceiling. The god-ness is breadth and size (`_create_mission_core_impl` is 298 LOC, mostly docstring), not cyclomatic complexity.
- `.venv/bin/mypy src/specify_cli/core/mission_creation.py`: **Success: no issues**. `ruff check`: clean.
- Note: mypy uses `follow_imports=skip` for `specify_cli.*` (comment at :2358-2361). Each new leaf must type-check standalone. #5679 needed "typed locals" for exactly this. Plan for it.

#### 6. Suggested WP slicing (lanes topology)

| WP | Scope | Depends on | Reviewable because |
|---|---|---|---|
| **WP01 Golden behaviour matrix** (tests only) | Freeze ULID and clock (precedent `tests/_factories/test_make_mission_parity.py:64-79`). Snapshot `meta.json` bytes, the file tree, refs, HEAD and branch, commit messages and trees, status events (normalized), `MissionCreationResult` fields, exception type and `error_code`, and leftovers on failure. Axes: topology {coord, lanes, lanes_with_coord, single_branch} × target protected {y, n} × commit_to_target × owned {none, owned} × type {software-dev, documentation} × {pr_bound, retain_*}. Failures: live duplicate, abandoned prior, dirty mint, branch exists, target without a commit, bootstrap skip, coordination seed failure (rollback), `SafeCommitStagedTreeUnchanged`. **Pin the current orphan-on-mint-refusal behaviour as-is**, with a comment linking the follow-up | — | Green on base. Defines "behaviour preserved" |
| **WP02 Pure decision cores** | Add `mission_creation_decisions.py`, using extract-first-order-concept and strangler-fig: the existing functions delegate to the cores in place. Unit tests per core, with no monkeypatch. Purity AST gate | WP01 | Additive; old functions become thin |
| **WP03 Module split** (move-method, verbatim) | Leaf modules plus façade re-exports `x as x` plus `_mc.` routing plus a routing gate. **Zero test assertion edits.** Exactly-once AST proof as in #5679. Re-pin path gates: `test_adapters` widened to the family, `test_no_write_side_rederivation` census and adopted set, the walker-gate exemption, the `test_single_mission_surface_resolver` descriptor, `test_commit_recipes` | WP02 | Mechanical; WP01 proves equivalence |
| **WP04 Seam cleanups** (behaviour-neutral) | Move the protected mint out of `_build_create_meta` into the orchestrator (order preserved). Compute `ProtectedMintFacts` once (removes the double `_target_is_protected`). Single `commit_to_target` source (proved by WP01). `CreateRollbackJournal` replaces the list holder. Split `_build_create_result` fan-out from the pure file sets. One `_DEFAULT_MISSION_TYPE` constant | WP03 | Each fold is small; golden stays green |
| **WP05 Retarget tests to seams** | Move the ~250 string patches on the façade onto decision cores or owning modules where they test a decision. Drop routing for names no longer patched on the façade (shrink the routing gate's list) | WP03 (parallel with WP04) | Delivers the issue's "tests pin cores without monkeypatching internals" |

Out of scope: the hoist of the mint decision before the scaffold write (behaviour change, see §4), the #5676 occupancy precondition, and the `bias` unification. Each is its own issue or mission, which the seam makes a one-liner.

#### Concessions (where the architect lens does not apply)

- I did not judge per-test flakiness or runtime cost of the golden matrix. That is the reviewer and QA lens.
- I did not assess Sonar coverage deltas per module, beyond noting the need for per-core unit tests.
- Retention "resolution" is not decided here. Create only *mints* the flags (fields absent unless True). Resolution lives in `core/paths.resolve_merge_retention` and consolidate. Nothing to extract beyond the `MetaPatch`.
- I did not read issue #5550's interaction in depth. It affects what `in_progress_wps_in_write_checkout` counts, not the seam shape.

#### Verdict

**GO, with conditions.** The file is a breadth god-module (14 responsibilities). Its complexity is low (max C901 11, mypy and ruff clean), and its public surface is small: one src caller plus tests. The PR #5679 façade and lazy-routing precedent fits directly. No layer rule blocks new `specify_cli/core` modules.

Conditions:
1. WP01 golden matrix first.
2. Re-pin, not delete, the five path-pinned gates, and widen `test_adapters` to the family.
3. Keep the orchestrator in the façade to minimize routing.
4. Treat the protected-mint pre-scaffold hoist, #5676, and the bias unification as **separate behaviour changes**. The empirically confirmed orphan-scaffold-blocks-retry defect means #5676 must not be fixed "in place" in the current mint position.

## Appendix B — Code archaeologist lens

### Grounding: archaeologist lens, #5634 mission_creation.py degod
Profile: researcher-robbie (read-only; directive 003 applied: cite evidence, no decisions). Charter context (specify) loaded: applied single-canonical-authority, locality of change (DIR_024), smallest-viable-diff, ATDD-first.
File: src/specify_cli/core/mission_creation.py = 2363 lines, 42 commits/90d, 53 `#NNNN` refs in code. Branch issue-5634-mission-creation-degod is checked out (no commits yet).

#### 1. Commit classification (42 in 90d)
- fix: ~27 (create/landing/convergence/commit-boundary); feat: ~8 (5c9424fc8 placement seam, cd9f0fc85 template resolve, b1d7a2c23, bf6487494 retention #3131, 9e73b3cf0 protected mint #5100, 639aa2feb OwnedCheckout, 5b5699e50 coord home, e72f8b8a0 split); refactor: ~5 (aa7e97dfe/370d1b72e clock, ef964bf98 #2561, 27210e6ed); style 1; tests/docs 0 (touch-only).
- Issue numbers: #5100 (7 commits: 9e73b3cf0 04099ee52 7f41347c6 0b4444bbe 67baad909 108e7ed89 + tail), #5440 (cbfedfa19, d78aa2345), #4033 (d074349fd), #3861 (26cf22bac), #3474 (d183d990e), #3131 (bf6487494), #2693 (b6fb5df3e), #3660 (ccb8ea82a), #3339/FR-011 (f28b1923e), #3346 (7923fda40), #3681 (161db6e04), #222, #677, #5392/#5400 (41979c2c9), #4084 (f2be03af4), #2658, #2561, #2496, #3664, #1716.
- Note: file already partially decomposed (frozen dataclasses _CreateRoots/_Scaffold/_MetaBuild/_CommitOutcome/_CoordCreateSeed, ~20 helpers). `_create_mission_core_impl` is lines 2041-2340 (~300 lines) and is the true god function.

#### 2. Hotspots (diff-hunk attribution via `git show -U0`)
| Function | fix touches |
|---|---|
| `_create_mission_core_impl` (2041) | ~30 of 42 commits (#5100 x7, #4033, #3474, #3131, #2693, #3660, #222, #3681, #5440, coord-home) |
| `create_mission_core` (866, wrapper) | ~14 (owned-checkout #3346, templates #2658, placement, rollback, retention, FR-011/#4035) |
| `_mint_protected_single_branch_mission_branch` (524) | 5 (#5100 x4, #5392/#5400) |
| `_restore_git_state_after_failed_create` (780) | 5 (WP12 FR-011, #3660, #5440, coord-home) |
| `_commit_feature_file` (223) | 6 (#2693, #3681, placement, #3346) |
| `_scaffold_mission_dir`/`_build_create_result`/`_emit_create_events` | 3-4 each, #5440 + 5b5699e50 |
| `_rollback_coordination_surface`, `_salvage_status_logs`, `_status_log_residue` | newest (Oct 2-3), churning |

Recurring defect classes: (a) rollback/atomicity after failed create (FR-011/#3339, #4035, #3660); (b) protected-target minting (#5100); (c) coord surface seeding/status-log placement (#5440, 5b5699e50, d78aa2345, 94b864d45); (d) duplicate detection (#4033/#3861); (e) origin binding/pending-origin ordering (460fd00ad, 2a39dd2e1, #222); (f) commit-boundary/transactional scaffold (#2693, #3681); (g) git path-as-data (#5392/#5400).

#### 3. Invariants to preserve (cite owner commit)
- [HIGH] Coord create seeds MissionCreated+SpecifyStarted into the coordination worktree, status log kept OFF target branch (#5440 cbfedfa19; gate via canonical partition predicate `_status_homes_on_coordination`, d78aa2345). Line ~1349 comment: "do not resurrect #5440".
- [HIGH] Coordination artifacts one durable home (5b5699e50, 94b864d45); named residual INV-COORD-HOME (owned coord mission still root-checkout scaffolded, lines ~1307, 1351, 2001, 2208). `_salvage_status_logs` before rollback teardown.
- [HIGH] Failed create: restore original checkout, CAS-restore via `restore_branch_ref`, delete orphan minted branch, remove orphan scaffolds only if untracked/disposable (`_failure_is_disposable_create_refusal`, `_plan_orphan_scaffold_removal`), and non-git side effects too (#4035, line ~978). Order: plan removal before mutation.
- [HIGH] #5100: protected mint only when topology single_branch AND target protected via ProtectionPolicy.is_protected_target (one authority, C-002); refuse target w/o commit (0b4444bbe); dirty refusal ignores only this mission's scaffold (bidirectional overlap, comment L561); MISSION_ALREADY_EXISTS reported BEFORE mint refusal (7f41347c6); re-create refusal scoped to protected mint only, idempotent resume otherwise (67baad909); scaffold commit lands on minted branch (108e7ed89, L2266); `commit_to_target` single_branch-only, persisted in meta, ambiguous selector fails closed (04099ee52).
- [HIGH] #4033: live-duplicate guard, abandonment-aware, `allow_duplicate` hatch; byte-identical committed scaffold = same duplicate signature (L1789, #3861); structured error classification not substring (26cf22bac, MissionAlreadyExistsError).
- [MED] #3131: retain_* never default-written; absent unless True; byte-identical output when off (L2126).
- [MED] #3474 mid8 derived from mission_id into meta once, shared by create+result (L1441, L2231).
- [MED] #2693/#3681: scaffold committed transactionally, `file_paths` tuple generated set; spec.md disclosed; meta commit after origin-binding on pending-origin flow (460fd00ad); commit failure names failing step; hard git failure raises (FR-001 #3673).
- [MED] #846: tasks readme NOT committed at create. #3660: mission created before discovery. #3346: explicit owned-checkout state isolated; `owned_checkout` result field name stable (L133). #2602: implicit create default is lanes (b97a535e4, in _create.py).
- [MED] Lazy function-local imports (L374,490,738,1200-1213,1310,1463,1487,1509,1892,1941,2018,2356) exist for cycle avoidance and adapter registration order: `consume_pending_origin` register-before-use (core/adapters.py:43,139). Hoisting them risks import cycles/ordering.
- [LOW] Kernel clock door `now_utc_iso()` only; no datetime direct.

#### 4. Open / still-open-shaped
- #5676 (protected single_branch create switches an occupied checkout): code-confirmed at `_mint_protected_single_branch_mission_branch` L600 `git checkout -b` in write_root; only dirty check, NO occupancy check (cf. lanes/checkout_occupancy). Fix lands in this function; it is behaviour change, so out of tidy-first scope: extract the function unchanged, add seam for later fix.
- #5550/#5696, #5680, #5459: occupancy/implement side; in implement.py/implement_support.py (WRITE_CHECKOUT_* codes, lanes/implement_support.py:40-52). No imports from mission_creation; shared concepts only: ProtectionPolicy (`resolve_for_mission` vs `is_protected_target` used here), `lanes.checkout_occupancy`, mission_runtime owned-checkout/`mission_branch_name`. Collision risk is conceptual (protection rule/occupancy), not textual.
- #5663, #1619, #5635: no references in code/tests (grep of src/tests for 5676/5663 hits only unrelated tracker tests). Cannot verify from here.
- INV-COORD-HOME residual (named residual comments, L1307/1351/2001/2208) = open-shaped.
- xfail grep for mission creation: none found. Tests calling create_mission_core: ~20 files (key: tests/specify_cli/cli/commands/agent/test_mission_create.py, test_mission_create_phases.py, test_mission_create_json_remediation.py, tests/specify_cli/test_mission_create_retention.py, tests/architectural/test_single_mission_surface_resolver.py, test_no_production_worktree_guard_bypass.py, tests/charter/*).

#### 5. In-flight / recent (14d) on main
Touching file: 94b864d45 (Oct 3), 5b5699e50 (Oct 2), d78aa2345, cbfedfa19, 41979c2c9 (Oct 1), 639aa2feb, #5100 series (Sep 29-30). Churn is very hot; rebase early and keep refactor PR short-lived. Coord-home work (5b5699e50 touched 11 sites in `_create_mission_core_impl`, plus decisions/fork.py, review/cycle.py, teardown.py, surface_resolver.py) may have follow-ups. Parallel #5635 area: implement.py/implement_support.py got 7 commits Oct 4 (#5680, #5459, move-task docs #5629); no overlap with mission_creation.py text. Open PRs not queryable (no GitHub access used).

#### 6. Callers / command layer
- Sole production caller: src/specify_cli/cli/commands/agent/mission_create.py:647-650 (`_invoke_create` funnel; error classifier L476-506; imports at L49,494,600). Churn: 22 commits/90d on this CLI file; 2 on missions/_create.py (topology_mints_coordination_branch, lazily imported). Others reference only in docstrings (charter/activation/*, tracker/origin_consumer.py, core/adapters.py).
- Public surface to preserve: create_mission_core signature, MissionCreationResult (incl. owned_checkout), MissionCreationError, MissionAlreadyExistsError, MissionBranchExistsError, render_tasks_readme_content.

#### Findings
[HIGH] mission_creation.py:2041 - `_create_mission_core_impl` ~300 lines, hit by ~30/42 commits - primary extraction target; split into pure decision cores (topology/protected-mint applicability, duplicate verdict, meta build, seed-gate predicate, rollback plan) and effect adapters (git, fs, commit, emit).
[HIGH] mission_creation.py:524-610 - protected mint mixes decision (is_protected, dirty filter, exists) with git effects; #5676 fix lands here - extract decision core with characterization tests first, do not change behaviour.
[HIGH] mission_creation.py:690-866 - rollback trio (_CoordCreateRollbackContext/_rollback_coordination_surface/_restore_git_state_after_failed_create) newest and most churny; extract plan as pure function, pin ordering and #4035 non-git effects with red-first tests.
[MED] lazy imports throughout - keep local or move behind adapters; cycle/registration-order hazard.
[MED] mission_creation.py:1307/1351/2001/2208 - INV-COORD-HOME residual; do not "fix" in a tidy-first PR.
[LOW] no xfails for mission create; test blast radius = test_mission_create*.py, test_mission_create_retention.py, architectural single_mission_surface_resolver + no_production_worktree_guard_bypass, tests/charter pack tests.

Verdict: Proceed, tidy-first feasible (file already half-decomposed). Risks: hot churn (rebase conflicts with coord-home follow-ups), lazy-import ordering, and tempting #5676 behaviour change which must stay out. Lens concession: I cannot see open PRs/issue state; #5663/#1619/#5635 unverifiable from code.

## Appendix C — Gates lens

### Grounding: gates lens for #5634 (mission_creation.py decomposition)

Delegate: reviewer-renata (loaded via `spec-kitty agent profile show reviewer-renata`; `spec-kitty charter context --action review --json` loaded in bootstrap mode).
Applied: DIRECTIVE_024 (locality of change: keep the blast radius to the gates that name the file), DIRECTIVE_030/032 (test and gate discipline: re-point, never loosen), DIRECTIVE_041/051; tactics `code-review-incremental`, `reverse-speccing` (gates read as the spec of today's invariants), `delete-the-assertion-not-the-test` (no gate is deleted or loosened to go green); charter standing orders on architectural gate discipline and canonical sources.

Repo HEAD: `2b7ad857f` (scaffold for mission-creation-degod-01M44467). `src/specify_cli/core/mission_creation.py` is 2,363 lines.

Method: static census (`grep -rln mission_creation tests/ scripts/ .github/ pyproject.toml docs/`, AST scans of every patch site), plus an **empirical move simulation**. In a scratch `git clone --shared` (the repo itself was not touched), I moved 21 functions verbatim into three new siblings: `mission_creation_git.py` (9 git/fs effect helpers), `mission_creation_scaffold.py` (7 scaffold/emit/commit adapters) and `mission_creation_cores.py` (5 pure helpers). `mission_creation.py` re-exports all of them. I ran the whole `tests/architectural/` suite before and after the move (see "Empirical results" at the end).

---

#### A. Gates that name the file and trip on a move (re-point needed)

[HIGH] tests/architectural/test_no_write_side_rederivation.py:1381 - `_COORD_WRITER_CENSUS` pins `("src/specify_cli/core/mission_creation.py", "_emit_create_events")`. If `_emit_create_events` moves, `test_coord_writer_census_floor_is_live` (line 1701) goes red with "Stale COORD writer census pair ... Re-point the census". - Re-point the pair to the new file. Do not delete the pair, and do not add an allow-list entry. Use the precedent at line 1373: `mission_finalize.py::_emit_local_canonical_events` was re-pointed to `mission_finalize_bootstrap.py` in #5627.

[HIGH] tests/architectural/test_no_write_side_rederivation.py:88-110 / :126-168 - the first grammar (root_walk / mid8 recompute / HEAD selectors) scans only `_ADOPTED_MODULES`, a hand-written list that contains `mission_creation.py` and not the new siblings. Code moved out of the file leaves the scan **silently**: the gate stays green while losing scope. - Add each new sibling that holds moved write-side code to `_WRITE_DIR_CONSUMER_MODULES`, not to `_PRE_WRITE_DIR_ADOPTED_MODULES`. `test_root_walk_scope_keeps_the_retired_checkout_allowlist_frozen` (line 2011) asserts `len(_RETIRED_CHECKOUT_GRAMMAR_ALLOWLIST) == 17`, and that set derives from `_PRE_*`, so adding a module there reds. Precedent: commit f89218441 (#5695) added `tasks_move_task_hops.py` and `tasks_move_task_executor.py` to `_WRITE_DIR_CONSUMER_MODULES`. This also fits that list's meaning: `_seed_coord_surface_for_create` (mission_creation.py:2037) consumes `placement_seam(...).write_dir(STATUS_STATE)`. Nothing checks that this list is complete, so this step is easy to miss.

[HIGH] tests/architectural/test_single_mission_surface_resolver.py:297-322 - a `ContentDescriptor(rel_path="specify_cli/core/mission_creation.py", qualname="_scaffold_mission_dir", token_substring="feature_dir = write_root / KITTY_SPECS_DIR / mission_slug_formatted")` in `_ALLOWLISTED_RAW_JOINS`. A move reds twice: the join is flagged in the new file as an unexpected raw bypass, and the old descriptor is reported stale (`test_allowlist_entries_are_not_stale`). - Change `rel_path` on the existing descriptor and append "re-pinned (#5634): moved verbatim to <file>" to its rationale. Do not add a second entry. The bite-battery test at :704 injects into an isolated copy of `mission_creation.py`. Its precondition ("no unexpected raw-join row in mission_creation.py today") still holds for the façade, so leave it targeting the façade.

[HIGH] tests/architectural/test_mission_resolver_walker_gate.py:21-22 - `_SCAFFOLD_SNAPSHOT_MODULE = "src/specify_cli/core/mission_creation.py"` plus `_SCAFFOLD_SNAPSHOT_FUNCTION = "_list_mission_scaffolds"` is a single-function exemption for a raw `kitty-specs/*` walk. If `_list_mission_scaffolds` moves, `test_no_unsanctioned_raw_kitty_specs_enumeration_in_src` reds on the new file. - Re-point `_SCAFFOLD_SNAPSHOT_MODULE` to the new home. The exemption stays scoped to one top-level function, and `test_scaffold_snapshot_exception_does_not_hide_another_walker` keeps proving that. Do not add the new file to `_LEGACY_WALKER_ALLOWLIST`, which would widen the exemption to the whole file.

[MEDIUM] tests/specify_cli/cli/commands/test_commit_recipes.py:82-90 - `_ALLOWED_GIT_COMMIT_HITS` is keyed by `("core/mission_creation.py", "has no commits yet")`. The string sits in `_resolve_create_roots` (mission_creation.py:1096). If that function moves, two tests red: `test_no_unallowed_git_commit_recipe_strings_in_src` (unallowed hit in the new file) and `test_allowlist_has_no_stale_entries`. - Re-point the path key and keep the rationale. The entry count does not change.

[LOW] tests/architectural/mission_type_reader_allowlist.yaml:87-98 - this entry exists for census completeness only. `mission_creation.py` is NOT in `IN_SCOPE_READER_MODULES` (test_mission_type_reader_invariants.py:134), so nothing reds. Its rationale already cites stale line numbers (623/704/822/835). - If the `"software-dev"` create-time defaults move into `_build_create_meta`'s new home, re-point the `path` (or add a `path` for the sibling, carrying the same issue and rationale) so the census stays complete. Drop the line numbers in favour of function names.

#### B. Gates that do NOT name the file but lose coverage or need an extension

[HIGH] Patch-liveness hazard (the biggest risk of the move). An AST scan of `tests/` (scratchpad `scan_patches2.py`, which resolves module-level string constants such as `_CORE_MODULE = "specify_cli.core.mission_creation"`, f-strings, `monkeypatch.setattr(mod, "x")` and `patch.object`) finds:
- **277 patch sites**, in **33 test files**, forming **93 distinct (file, name) pairs**, over **13 distinct names**: `is_worktree_context` 72, `locate_project_root` 45, `is_git_repo` 44, `get_current_branch` 42, `_commit_feature_file` 41, `ULID` 11, `create_mission_core` 7, `preflight_commit` 5, `safe_commit` 4, `now_utc_iso` 2, `_commit_create_scaffold` 2, `_consume_pending_origin_if_present` 1, `subprocess.run` 1.
- The issue's "57 string targets" undercounts. Plain string literals alone come to 51 sites; most sites go through the `_CORE_MODULE` f-string form.
- Readers of each name inside mission_creation:
  - `is_worktree_context`: `_resolve_create_roots`.
  - `locate_project_root`, `is_git_repo`: `create_mission_core` and `_resolve_create_roots`.
  - `get_current_branch`: `_commit_feature_file`, `_restore_git_state_after_failed_create`, `create_mission_core`, `_resolve_create_roots`.
  - `ULID`: `_create_mission_core_impl`.
  - `now_utc_iso`: `_build_create_meta`.
  - `preflight_commit`: `_scaffold_mission_dir`.
  - `safe_commit`: `_commit_feature_file`.
  - `_commit_feature_file` and `_consume_pending_origin_if_present`: `_commit_create_scaffold`.
  - `_commit_create_scaffold`: `_create_mission_core_impl`.
- **Any of those readers moved verbatim into a sibling silently kills every patch of that name on `mission_creation`.**
- Demonstrated in the simulation: `tests/core/test_mission_creation_decomposition.py::test_worktree_context_without_allow_flag_is_refused` went red once `_resolve_create_roots` moved. That one failed loudly. Patches whose test still passes against the real function fail silently, which is the case the gate exists for.
- `subprocess.run` is patched as `mission_creation.subprocess.run`, which patches the shared `subprocess` module. That one is out of scope by design, as in the move-task gate.

[HIGH] tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py (#5629 / #5684 / PR #5695 lineage) - the existing patch-liveness gate is hard-scoped to `_PKG = "specify_cli.cli.commands.agent"` with `_SEAMS = tasks_*.py` plus the `tasks` bridge. It does **not** cover `specify_cli.core.mission_creation*`.
- How it works:
  - `_Scanner` walks every test file and resolves `patch` / `patch.object` / `patch.multiple` / `monkeypatch.setattr` targets to `(module, name)`, including constants, f-strings, `import_module` aliases and `__name__` forms.
  - `_live_names` treats a name as live for module M only when one of these holds:
    - M reads the name as a module-global `Name` load outside the name's own def, with no shadowing local;
    - any `src/` function imports it at call time (`from <pkg>.M import name` inside a function);
    - it is reached through the bridge alias.
  - Re-export `ImportFrom` lines never count, so a façade that only re-exports a name reads as dead for it.
  - Unresolvable targets are counted against `UNRESOLVABLE_BASELINE = 1`. An `ALLOWLIST` with TODO(#2561) entries exists.
  - It has a positive control (a known f-string site must be found) and a negative control (a moved-symbol patch must be reported dead).
- Recommendation: extend coverage to the `mission_creation*` family by generalising the scanner (package plus module-family parameters, or a shared `tests/_support` helper). Do not fork a copy. Give the new family zero allowlist entries and an unresolvable count of 0.
- This is a liveness check, not a size or ratchet gate, so the operator's "no new size/ratchet gates" ruling does not forbid it. If the operator reads any new baseline number as a ratchet, the minimum acceptable alternative is the #5679 `_ROUTED_NAMES` pin below, which has no numeric baseline.

[HIGH] PR #5679 / #5627 (mission_finalize split): the template to copy. These are the precise mechanics.
1. **Family source helper** `tests/_support/finalize_source.py`:
   - `FINALIZE_MODULE_PATHS` lists the façade plus 7 phase modules.
   - `finalize_family_source()` concatenates the sources and strips the `_mf.` routing qualifier (`re.compile(r"\b_mf\.")`), so structural pins that once read one file now read the whole family, and a routed `_mf.x(...)` looks like the plain `x(...)`.
   - The helper has a self-test, `tests/_support/test_finalize_source.py`, with two checks: `set(FINALIZE_MODULE_PATHS) == set(AGENT_DIR.glob("mission_finalize*.py"))` (a new sibling joins automatically), and `"_mf." not in finalize_family_source()`.
2. **Seam pins** in `tests/specify_cli/cli/commands/agent/test_mission_finalize_phase_modules.py`. `PHASE_MODULES` is the helper's list minus the façade.
   - (a) `test_mission_finalize_reexports_every_phase_definition`: every top-level def, class or assignment of a phase module is reachable on the façade by **identity** (`getattr(facade, n) is getattr(leaf, n)`).
   - (b) `test_phase_module_never_imports_mission_finalize_at_module_scope`: a leaf reaches the façade only through a lazy, function-local `from ...agent import mission_finalize as _mf`. This rules out an import cycle.
   - (c) `test_logger_name_is_pinned_to_mission_finalize`: leaves log through the façade's logger name, so caplog/logger-name assertions keep holding.
   - (d) Behavioural intercept tests: patch `mission_finalize.<name>`, call a function inside a leaf, and assert the patch fired.
   - (e) `_ROUTED_NAMES` frozenset holds every name a test patches on the façade plus the pre-split patch surface. A comment requires: "Add a name in the same change that first patches it."
     - Rule 1: a routed name is never referenced bare (as a `Name` load) inside a leaf function body. It must be `_mf.<name>`.
     - Rule 2: a function another family module owns is never referenced bare, so cross-leaf calls also go through `_mf`.
     - A stale check fails if a `_ROUTED_NAMES` entry no longer exists on the façade.
     - A planted control (`test_routing_gate_flags_an_unrouted_reference`) de-routes `_mf._compute_and_write_lanes(` in memory and expects exactly 2 violations.
   - Template for #5634:
     - Add `tests/_support/mission_creation_source.py` with `MISSION_CREATION_MODULE_PATHS` (glob `core/mission_creation*.py`) and a family-source helper with the same self-test.
     - Add a seam-pin module with the five properties above. Seed `_ROUTED_NAMES` from the 13 names in this report, minus `subprocess` and `create_mission_core`; `create_mission_core` is patched by CLI tests and is called through the façade module attribute.
     - Pure cores must not read any routed name. If a core needs `now_utc_iso` or `ULID`, that is a sign it is an effect: inject the value as a parameter instead of routing it.
   - **The alternative** to routing is to re-point all 93 test patch pairs to the new homes in the same PR. That is behaviour-preserving for production but churns 33 test files and breaks the "façade is the patch surface" contract. Choose one strategy per name, and write that choice down.

[MEDIUM] tests/core/test_adapters.py:296-337 (`test_mission_creation_has_no_integration_imports`) - this scan reads only `core/mission_creation.py`, so moved code would leave its scope. The loss is mitigated: `tests/architectural/test_integration_boundary.py` scans all of `src/specify_cli/core/` (`CORE_PACKAGES`, `ALLOWLIST = frozenset()`), so the siblings stay covered for the same INTEGRATION prefixes. - Switch the test to read the family through the new source helper. It stays green either way, but would otherwise quietly narrow.

[MEDIUM] Logger identity - every moved function that logs uses `logger = logging.getLogger(__name__)`. A new module gets a new logger name (`specify_cli.core.mission_creation_git`, ...). - Pin `logging.getLogger("specify_cli.core.mission_creation")` in each sibling, and add a test as #5679 did with `test_logger_name_is_pinned_to_mission_finalize`. Any caplog filters on the façade logger name otherwise go silently empty.

[LOW] tests/release/test_pinning_inventory_fresh.py + scripts/ci/derive_pinning_inventory.py - **N/A to this move.**
- What it is: a deterministic derivation of every rule in `tests/` and `scripts/` that references the retiring sonarcloud job's SUBJECTS (`sonarcloud`, `ci-quality.yml`, `make test-fast`). It writes the committed `tests/release/pinning_rule_inventory.json` (54 files, 0 mentions of mission_creation) with text-scan line numbers, and a freshness gate diffs that file.
- It does not enumerate monkeypatch targets.
- It trips only if the mission edits one of its 54 listed files above a pinned line. The listed arch files include `test_coverage_breadth.py`, `test_fast_tier_marker_completeness.py` and `test_pyproject_shape.py`. If that happens, regenerate with `python scripts/ci/derive_pinning_inventory.py` and commit the artefact.

[LOW] tests/architectural/test_module_length_agreement.py - new or removed tests in core_misc/agent test dirs change collected counts against `.github/ci-shard-timings.json`. This **warns** by default and fails only under strict mode in the scheduled `ci-shard-recapture.yml`. - No action needed per PR. Optionally recapture with `scripts/ci/capture_shard_timings.py`.

#### C. Gates checked and not applicable (concede)

- test_layer_rules.py + conftest `landscape`: siblings stay in `specify_cli.core` with the same imports, so the direction is unchanged. mission_runtime's outbound ledgers do not import mission_creation.
- test_mission_runtime_surface.py:207: a whole-tree scan banning internal `mission_runtime.*` submodule imports. Verbatim imports from the package root stay legal. Copy the import lines as they are, with `resolve_create_time_write_target` from the package root.
- test_compat_shims.py: `_ADAPTER_FILES` is limited to `src/specify_cli/compat/_adapters/`, so a re-export façade is not a "shim" there. test_unregistered_shim_scanner.py fires only on `__deprecated__ = True`. **Do not mark the façade deprecated.** That would require a shim-registry entry and a removal plan.
- test_no_dead_symbols.py / test_no_dead_modules.py: a façade `from ...siblings import X` counts as a src caller of each sibling definition and module. mission_creation has no `__all__`. Its public names (`MissionCreationError`, `MissionCreationResult`, `create_mission_core`, `MissionAlreadyExistsError`, `MissionBranchExistsError`, `KEBAB_CASE_PATTERN`, `TASKS_README_TEMPLATE`, `render_tasks_readme_content`) stay importable. No allowlist growth expected (cap 294 / 92 in `_baselines.yaml`). Confirm with the run.
- test_destructive_op_routing.py: mission_creation holds no `reset --hard` / `worktree remove --force` / `merge --abort` / `stash push` argv. It has `branch -D`, `checkout`, `read-tree` and `worktree prune`, and the docstring at :69 keeps `branch -D` out of scope. That docstring is prose only and can stay.
- test_mutation_ownership_routing.py: its census module set is `init.py` + `migrations/*`. The `shutil.rmtree` calls in mission_creation (:686, :745) are not in scope today, and a move does not change that.
- test_egress_consent_boundary.py:472: prose in an E2 note. mission_creation holds no transmit primitive.
- test_no_worktree_name_guess.py:152: a historical comment only.
- test_untrusted_path_containment.py, test_coverage_breadth.py, tests/git/test_guard_capability_regression.py, test_guard_capability_call_sites.py: none are keyed on this file.
- `_baselines.yaml`: no counter covers this file. Nothing grows if the honest re-pointing above is used. Counters such as `coord_writer_allowlist: 0` and `destructive_op_allowlist: 61` stay unchanged.
- CI gate selection (`scripts/ci/gate_selection.py`, `.github/workflows/ci-router.yml`, `.github/ci-module-registry.yml`): `src/specify_cli/core/**` routes to `core_misc` (test_dirs tests/core, tests/specify_cli/core, ...) and `specify_cli_runtime`. New `core/mission_creation_*.py` files match the glob automatically, so **no registration is needed**. Patch-heavy tests also live in `tests/agent` (module `agent`), `tests/specify_cli/cli/commands/**` (`cli`/`execution_context`) and `tests/integration`. Those do not run on a core-only diff unless the PR also edits them, so run them locally (list below). `tests/architectural` runs in the router's architectural-heavy lane on any src change.
- pyproject.toml:1176, :1992-1994: these name `tests/core/test_mission_creation_identity.py` and `tests/specify_cli/core/test_mission_creation_*.py` in a test-file list. They are test paths, not src paths, so nothing changes unless those tests are renamed.
- Docs: the line-number citations in `docs/convergence/landing.md:23`, `docs/development/docs-retrieval-index.yaml:10657` (generated) and `docs/plans/engineering-notes/naming-identity-ssot-strangler/00-OVERVIEW.md:235` are historical snapshots and already stale (`:721-738` etc.). ADRs cite only the module path, which the façade keeps valid. In src, the docstrings `tracker/origin_consumer.py:5` and `core/adapters.py:4` cite `core/mission_creation.py::_consume_pending_origin_if_present`. Update that citation only if the function moves; no gate resolves `::qualname` citations.

#### D. Exact pytest command for the implicated gates

```
.venv/bin/python -m pytest -p no:cacheprovider \
  tests/architectural/test_no_write_side_rederivation.py \
  tests/architectural/test_single_mission_surface_resolver.py \
  tests/architectural/test_mission_resolver_walker_gate.py \
  tests/architectural/test_mission_type_reader_invariants.py \
  tests/specify_cli/test_mission_type_write_boundaries.py \
  tests/architectural/test_integration_boundary.py \
  tests/architectural/test_mission_runtime_surface.py \
  tests/architectural/test_layer_rules.py \
  tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_no_dead_modules.py \
  tests/architectural/test_destructive_op_routing.py \
  tests/architectural/test_egress_consent_boundary.py \
  tests/architectural/test_unregistered_shim_scanner.py \
  tests/architectural/test_ratchet_baselines.py \
  tests/architectural/test_ruff_format_enforcement.py \
  tests/specify_cli/cli/commands/test_commit_recipes.py \
  tests/core/test_adapters.py \
  tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py \
  tests/release/test_pinning_inventory_fresh.py
```

The 32 patch-carrying test files below, plus the factory `tests/_factories/coord_mission.py`. Together they hold all 33 files with patch sites, and these tests are the liveness blast radius:

```
.venv/bin/python -m pytest -p no:cacheprovider -n auto --dist loadfile \
  tests/_factories/test_make_mission_parity.py \
  tests/agent/test_agent_feature.py \
  tests/agent/test_create_feature_branch_unit.py \
  tests/contract/test_mission_id_creation_contract.py \
  tests/core/test_mission_create_checkout_restore.py \
  tests/core/test_mission_create_coord_seed_rollback.py \
  tests/core/test_mission_create_coord_status_placement.py \
  tests/core/test_mission_create_coord_status_seed.py \
  tests/core/test_mission_create_protected_single_branch.py \
  tests/core/test_mission_create_scaffold_rollback.py \
  tests/core/test_mission_creation_decomposition.py \
  tests/core/test_mission_creation_fanout_commit_boundary.py \
  tests/core/test_mission_creation_identity.py \
  tests/core/test_mission_creation_topology.py \
  tests/core/test_mission_creation_unborn_head.py \
  tests/core/test_slug_validator_unit.py \
  tests/integration/test_issue_4863_merge_abort_no_state.py \
  tests/integration/test_placement_partition_golden_path.py \
  tests/integration/test_specify_plan_commit_boundary.py \
  tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py \
  tests/specify_cli/cli/commands/agent/test_issue_2684_subtask_completion_event_sourced.py \
  tests/specify_cli/cli/commands/agent/test_mission_create.py \
  tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py \
  tests/specify_cli/cli/commands/agent/test_mission_create_phases.py \
  tests/specify_cli/cli/commands/review/test_issue_matrix_partition.py \
  tests/specify_cli/cli/commands/test_coordination_doctor.py \
  tests/specify_cli/cli/commands/test_selector_resolution.py \
  tests/specify_cli/core/test_feature_creation.py \
  tests/specify_cli/core/test_mission_creation_fire_once.py \
  tests/specify_cli/core/test_mission_creation_placement.py \
  tests/specify_cli/core/test_mission_creation_specify_started.py \
  tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py
```
(Regenerate the exact list with `python3 <scratchpad>/scan_patches2.py . -v`.)

#### E. Empirical results (simulated verbatim move, scratch clone only)

Setup: 21 functions were moved verbatim into `mission_creation_git.py`, `mission_creation_scaffold.py` and `mission_creation_cores.py`, and `mission_creation.py` re-exports them. The move script is `gates_move_sim.py`; the clone is `gates_sim2/`.

**Whole `tests/architectural/` run after the move:** 10 failed, 20 errors, 3871 passed (28m56s). The full output is in `gates_sim2_arch.txt`.

Attribution:

| Red | Cause | Predicted above? | Honest fix |
|---|---|---|---|
| `test_single_mission_surface_resolver.py` **collection ERROR** (`DescriptorResolutionError ... resolved to 0 finding(s)`) | `_ALLOWLISTED_RAW_JOINS` descriptors are resolved at **module import time** | yes (A) | Re-point `rel_path` |
| ~25 cascaded reds: 17 setup errors in the collect-only probes, `test_universe_store` (battery 1/2), `test_interpreter_shard_coverage` x2, `test_battery_partition_proof_collect` x2 | Every gate that shells out to `pytest --collect-only` over `tests/architectural` inherits the collection error above | **new** | Disappears once the descriptor is re-pointed. Do not triage these one by one. |
| `test_no_write_side_rederivation.py::test_coord_writer_census_floor_is_live` | stale census pair `_emit_create_events` | yes (A) | Re-point the pair |
| `test_mission_resolver_walker_gate.py::test_no_unsanctioned_raw_kitty_specs_enumeration_in_src` (`mission_creation_git.py: iterdir`) | snapshot exemption is pinned to the old path | yes (A) | Re-point `_SCAFFOLD_SNAPSHOT_MODULE` |
| `test_no_dead_symbols.py` x2 | **new, see below** | **new** | see below |
| `test_ruff_format_enforcement.py` | the scratch move left the new files unformatted (artefact of the simulation) | n/a | Run `ruff format --force-exclude` on the new files |
| (silently green) first-grammar scope of `test_no_write_side_rederivation` | the new siblings are not in `_ADOPTED_MODULES` | yes (A), **confirmed silent** | Add them to `_WRITE_DIR_CONSUMER_MODULES` |

Targeted, non-architectural run after the move:
- `test_commit_recipes.py::test_no_unallowed_...` and `::test_allowlist_has_no_stale_entries` went red, as predicted in (A).
- **Baseline red at HEAD:** `test_no_unallowed_git_commit_recipe_strings_in_src` is **already red** on the unmodified clone, flagging `cli/commands/_commit_message.py` ("...as git commit does"). This is pre-existing and not the mission's to fix. The `::test_allowlist_has_no_stale_entries` red is caused by the move.

[HIGH] tests/architectural/test_no_dead_symbols.py:1544 / :2397 (newly found by simulation) - the gate counts an **intra-module reference** as "alive" for a non-`__all__` public name. Two traps follow from that:
1. A public constant or class left in the façade whose only readers moved goes dead. In the simulation this hit `mission_creation::KEBAB_CASE_PATTERN`, `::TASKS_README_TEMPLATE`, `::MissionBranchExistsError` and `::logger`.
2. A sibling that defines `logger` but never logs makes `mission_creation_cores::logger` / `mission_creation_git::logger` dead.

Recommendation:
- **Move each public constant or class together with its sole reader.** The façade re-export import then counts as the src caller.
- Define `logger` only in siblings that log.
- Never grow `dead_symbol_allowlist.yaml` (cap 294) or `widened_grandfathered_470` (cap 92) to absorb this.

Caveat: the simulation copied façade globals into the siblings with `setattr` instead of real imports. That is why the façade constants read as unreferenced here. A real split importing them from a shared module would see different liveness, but trap 2 and the "orphaned constant" trap are real either way.

Behavioural spot-check: `tests/core/test_mission_creation_decomposition.py::test_worktree_context_without_allow_flag_is_refused` went red after the move. Its `monkeypatch.setattr(f"{_CORE_MODULE}.is_worktree_context", ...)` stopped intercepting once `_resolve_create_roots` moved. This one failed loudly. Patches whose test passes either way fail silently, which is why the liveness gate (B) is needed.

#### Verdict

**The move can be gated green honestly, with no new allowlist entries and no baseline bumps**, provided the mission:
1. **Re-points** the four path-pinned exemptions (single-surface descriptor, walker snapshot module, coord-writer census pair, commit-recipe key).
2. Adds the new siblings to `_WRITE_DIR_CONSUMER_MODULES`, following the f89218441 precedent. Not `_PRE_*`, whose count is frozen at 17.
3. Keeps the façade as the patch surface, using the #5679 template: a family-source helper, identity re-export pins, lazy `_mc` routing with `_ROUTED_NAMES`, and a pinned logger name. Alternatively, re-points every patch pair. For mechanical enforcement, extend the existing #5695 patch-liveness scanner to the `mission_creation*` family.
4. Moves constants and classes with their readers so the dead-symbol gate holds.
5. Widens `tests/core/test_adapters.py` to the family.

The highest hidden risk is item 3: 277 patch sites, 93 (file, name) pairs, 13 names. Today no gate covers `mission_creation` patch liveness, and a verbatim move turns an unknown number of those patches into silently inert ones.

Out of scope for this lens: CI routing needs nothing, because `src/specify_cli/core/**` globs absorb the new files. The pinning inventory is untouched unless one of its 54 listed files is edited. Shard-timing drift only warns.
