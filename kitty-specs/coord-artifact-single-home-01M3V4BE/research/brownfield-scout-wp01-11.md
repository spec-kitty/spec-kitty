# Brownfield scout: WP01-WP11 (coord-artifact-single-home-01M3V4BE)

- Point-cut: pre-implementation, procedure `adversarial-squad-deployment`, lens `paula-patterns` (squad-delegate mode: no swarm, direct lens).
- Loaded: `spec-kitty agent profile show paula-patterns` (architecture-scout; avoid production implementation); `spec-kitty charter context --action implement --json` (compact; DIRECTIVE_024 locality, DIRECTIVE_025 campsite, NO_FULL_HEAVY_SUITES_IN_MISSION); `squad-post-tasks.md` (prior paula P-M1..P-m7 folds, so not repeated here).
- HEAD `79c453e286` (product code == upstream/main `bc826fcbcb`; the prompts cite `ecb5dd914a`, and every line number re-checked below matches HEAD).
- Method: WP01 scouted directly; WP02-04, WP05-07 and WP08-11 scouted by three forks of this scout, then merged here. Every claim carries file:line at HEAD.

## WP01

**C901 baseline: CONFIRMED at HEAD.** All twelve rows of the T001 table reproduce exactly (`ruff check --select C901 --config 'lint.mccabe.max-complexity=9'`): `_stage_artifacts_in_coord_worktree` 13 (commit_router.py:991), `resolve_status_surface_with_anchor` 12 (surface_resolver.py:1192), `_coord_branch_exists` 10 (surface_resolver.py:688, out of scope).

**Baseline green (recorded by scout):** the owning surfaces (commit_router x3, `tests/specify_cli/coordination/`, the 3 surface_resolver files, aggregate) give **513 passed, 10 skipped, 64 s** with `-n 4 --dist loadfile`. `test_surface_resolver_anchor_helpers.py` does not exist yet (create_intent, correct).

### Seam map
- `_stage_artifacts_in_coord_worktree(files, coord_worktree, repo_root, *, primary_paths_created_this_invocation=None) -> list[Path]` at commit_router.py:991.
  - src callers: commit_router.py:947 and :1230.
  - Alias `_stage_finalize_artifacts_in_coord_worktree = _stage_artifacts_in_coord_worktree` at commit_router.py:1255.
  - The alias is re-exported by `cli/commands/agent/mission.py:298`, and that shim is pinned by `tests/specify_cli/cli/commands/agent/test_mission_shim_reexports.py:91`. Keep the alias assignment **after** the def; do not convert it into a wrapper.
- Test callers the prompt does not list:
  - `tests/specify_cli/cli/commands/agent/test_finalize_coord_staging.py` (5 direct calls via the alias; these pin the tasks.md/lanes.json → coord staging the L1047-1059 comment cites);
  - `tests/specify_cli/cli/commands/agent/test_finalize_clobber_e2e.py:361-374`;
  - `tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py:649-714`, which calls the alias through the module attribute (`commit_router_module._stage_finalize_artifacts_in_coord_worktree`).
  - **Add all three to the T005 validation run.** They are the pins most likely to catch an ordering or COPY-semantics slip.
- Patch-by-name sites (survive an extraction because they look up the module global): `test_commit_router.py:744` (`patch.object(commit_router, "_stage_artifacts_in_coord_worktree")`) and `test_commit_router_fail_loud.py:316`.
- `resolve_status_surface_with_anchor(repo_root, mission_slug, topology=None, *, for_write=False) -> ResolvedStatusSurface` at surface_resolver.py:1192. Callers sit in 6 src modules: `mission_finalize.py`, `implement.py`, `consolidation/executor.py`, `coordination/status_transition.py`, `surface_resolver.py` itself (`resolve_status_surface` at L1189) and `missions/_read_path_resolver.py`. Purity matters on all of them, not only `resolve_placement_only`.

### CORRECTION (T005 action enum is incomplete)
- The suggested `_StagePlan` = `IN_PLACE / SKIP_STATUS_LOG / SKIP_ANALYSIS_REPORT / COPY(dst)` misses a fifth outcome.
- The **under-`.worktrees/`-but-not-this-worktree** path (and an `analysis-report.md` under `.worktrees/`) is **dropped**: commit_router.py:1026-1029 `continue`s without appending.
- This is pinned by `test_commit_router.py::test_coord_staging_drops_a_status_log_from_another_worktree` (both params: the sibling Mission's coordination worktree, and a worktree nested inside this one).
- Model it as an explicit `DROP_FOREIGN_WORKTREE` (or similar). Do not fold it into a SKIP that WP05 might later "translate".

### Hazards
- **COPY semantics trap.** commit_router.py:1062-1067 appends `dst` to `coord_files` **even when `src` does not exist** (no copy, still listed), and records only the copied pairs in `staged_sources`. The "act" step must keep both behaviours. A classifier that returns `COPY` only when `src.exists()` is a silent behaviour change.
- **Exceptions.** `src.relative_to(repo_root)` (L1018) raises `ValueError` for a path outside `repo_root`. The classifier must not swallow that, because today it propagates.
- **Symlinks.** `_is_directly_in_worktree` compares `.resolve()`d paths, so the classifier is not purely lexical. That is pinned by `test_coord_staging_keeps_its_own_status_log_through_a_symlinked_repo_root` (test_commit_router.py:876; it uses `symlink_to`, a Windows-CI caveat that already exists). Keep the resolve inside the classifier, and do not "simplify" it to lexical `relative_to`.
- **Lazy import.** `from specify_cli.coordination.surface_resolver import is_under_worktrees_segment` is function-local (L1012). Keep it lazy inside the new helper. Hoisting it to module top changes the import graph, and `test_commit_router_layering.py::test_has_surface_resolver_import` AST-scans that file.
- **ruff `ARG` is enabled** (pyproject `[tool.ruff.lint] select` includes `"ARG"`). So T006 cannot pre-add the parameters WP04 will need. WP04's D4 discriminator (`git ls-tree <coord_branch> kitty-specs/<dir>`) needs `repo_root` and `coord_branch`, and neither is in the suggested `_empty_coord_surface(feature_dir, composed_coord_dir, mission_slug, effective_topology)`.
  - Accept that WP04 widens this private signature. That costs nothing, because the helper is private.
  - Alternative: pass `repo_root` / `coord_branch` now only if the helper already uses them, and it does not.
  - **Tell WP04** (its T021 assumes the helper is ready to take the discriminator).
- **Warning payload.** `logger.warning(_COORD_EMPTY_FALLBACK_WARNING, {"slug": ..., "coord_root": composed_coord_dir.parent.parent})` (L1443-1446) uses the mapping-style `%` args. Move the call verbatim: `test_surface_resolver_coord_empty_warning.py` matches on the constant (L32, L188).
- **Dead-symbol gate:** this WP adds no exposure.
  - `test_no_dead_symbols.py` scans `__all__` plus **public (non-underscore)** module-level names only (docstring L19-63).
  - `_StagePlan`, `_classify_stage_path`, `_cleanup_staging_residue` and `_empty_coord_surface` are exempt.
  - If someone names the enum `StagePlan` (public), it still passes through the "used within own module" rescue. Keep it private anyway.
- **Architectural scanners keyed by `(qualname, token_line)` read both files:** `test_single_mission_surface_resolver.py` (raw-join allowlist L197-389), `test_no_worktree_name_guess.py` (L126-198) and `_load_meta_census.py:181` (`commit_router._resolve_mid8`).
  - None of their sanctioned sites is in `resolve_status_surface_with_anchor` or `_stage_artifacts_in_coord_worktree`. Their sanctions sit in `_coord_mid8`, `_compose_primary_feature_dir`, `_scaffold_mission_dir` and `_resolve_mid8`.
  - So moving code out of these two functions moves no sanctioned site. **But** `load_meta_fail_closed` is called twice inside `resolve_status_surface_with_anchor` (L1283, L1346). If T006 extracts the `meta is None` block (L1341-1358, a legitimate complexity source the prompt does not name), check `_load_meta_census.py` for an un-keyed census count.
- **C901 headroom.** Extracting only the EMPTY branch (`if` + inner `if`) takes 12 to about 10. The completed-shortcut extraction (T006 step 3) is then needed for margin, or extract the `meta is None` fallback instead (L1341-1358: 3 branches).

### Pinning tests
These are valid guards and must stay green unchanged:
- `test_commit_router.py::test_coord_staging_*` (L760-893);
- `test_finalize_coord_staging.py` (the tasks.md/lanes.json staging contract);
- `test_surface_resolver_coord_empty_warning.py` (solo `coord` quiet, `lanes_with_coord` loud);
- `test_surface_resolver_solo_coord_primary.py`.

There is no stale pin in this WP (it is behaviour-preserving).

### Parallel-authority risk
- surface_resolver.py:1445 already derives the coordination worktree root as `composed_coord_dir.parent.parent`, and L385 does the same with `coord_candidate.parent.parent`.
- WP01 must move that expression verbatim, not "fix" it.
- **Flag for WP03/WP04/WP07/WP09/WP17:**
  - `test_no_worktree_name_guess.py:474-476` explicitly does **NOT** cover the `feature_dir.parent.parent` repo-root-derivation class (deferred to #2007).
  - The post-tasks fold P-M3 names that file as the gate stopping `.path.parent.parent` guessing for `WriteLocation.checkout_root` consumers. **It will not catch that pattern.** See the cross-cutting risks section.

### Quick-run
```bash
uv run --frozen pytest -n 4 --dist loadfile -q tests/coordination/test_commit_router.py tests/coordination/test_commit_router_fail_loud.py tests/coordination/test_commit_router_layering.py tests/specify_cli/coordination/test_commit_router_partition.py tests/specify_cli/coordination/test_commit_router_partition_authority.py tests/specify_cli/cli/commands/agent/test_finalize_coord_staging.py tests/specify_cli/cli/commands/agent/test_finalize_clobber_e2e.py tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py tests/specify_cli/cli/commands/agent/test_mission_shim_reexports.py
uv run --frozen pytest -n 4 --dist loadfile -q tests/coordination/test_surface_resolver_coord_empty_warning.py tests/coordination/test_surface_resolver_collapse.py tests/coordination/test_surface_resolver_solo_coord_primary.py tests/coordination/test_surface_resolver_anchor_helpers.py tests/specify_cli/coordination/test_coord_topology_states.py tests/specify_cli/coordination/test_legacy_warning_classifier.py tests/status/test_aggregate_surface_resolution.py
uv run --frozen pytest -q tests/architectural/test_single_mission_surface_resolver.py tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_layer_rules.py
```
- Timing note: `test_commit_router.py::test_router_does_not_commit_a_status_row_while_a_transition_holds_the_status_lock` takes about 14 s (lock wait). It is not a hang.

## WP02

### Seam map
Anchors confirmed at HEAD:
- `create_mission_core` `core/mission_creation.py:760`;
- `_resolve_default_topology_phase` `mission_create.py:372`;
- `CoordinationWorkspace.worktree_path` `workspace.py:270` and `.resolve` `:297`;
- `CoordState` `missions/_read_path_resolver.py:250`;
- `probe_coord_state` `:278`.

### CORRECTION (DELETED variant)
- `probe_coord_state(repo_root, slug, mid8, *, coordination_branch=None)` returns `DELETED` **only when `coordination_branch=` is passed**. Without it, an absent root is always `UNMATERIALIZED`.
- `_coord_branch_exists` (surface_resolver.py:688) checks the local head, then `refs/remotes/`, then makes a network `remote_branch_lookup` (`:672`), which treats HIT and ERROR as "present".
- `branch_deleted=True` must therefore remove the local head, the remote-tracking ref and the bare-remote branch, or the fixture must have no remote at all. An unreachable remote URL reads ERROR, so the probe says UNMATERIALIZED: a flake vector. Keep fixtures remote-less unless `remote_only=True`.

### CORRECTION (T010 `lamports` hint)
- `status/models.py` has no `event_lamport` field. Status rows carry `lamport_clock` (lifecycle envelope, `status/lifecycle_events.py:464`) or nothing (`MissionCreated`).
- Decision events carry `event_lamport` (`decisions/models.py:137`), which may be `None`. `decisions/emit.py:97` uses the row count as the Lamport proxy.
- `lamports` must tolerate a missing field per row.

### Two decision streams
- DecisionPoint* rows go through `decisions/emit.py:88` (`placement_seam(...).read_dir(STATUS_STATE)`) into **`status.events.jsonl`**.
- `DecisionGitLog` writes **`decisions.events.jsonl`** (`events/decision_log.py:119`).
- Fork fixtures (a) and (b) must say which stream diverges. The WP03 prefix rule runs per stream.

### Hazards
- MATERIALIZED vs EMPTY is decided by `Path.exists()` on the worktree root (`feature_dir.parent.parent`). A plain `mkdir` gives EMPTY without a real `git worktree`, and the existing tests rely on that (`test_surface_resolver_coord_empty_warning.py:120`). The `materialized=True` builder must use a real `git worktree add` (R-M4 requires the production probe).
- `def coord_mission` fixture names already exist in `tests/terminus/conftest.py:1351` (its own `CoordMission` class), `tests/architectural/test_write_surface_placement_guard.py:138`, `tests/missions/test_gate_read_two_surface_behavioral.py:173` and 4 `tests/integration/*` files.
  - They are directory-scoped, so they do not clash.
  - Do not import both `CoordMission` classes into one module.
- `tests/coordination/` and `tests/mission_runtime/` have no `__init__.py` (rootless). Test basenames must stay unique repo-wide; no clash was found for the planned names.
- `hypothesis` is not a dependency. Any property test in WP03/WP04 must use a seeded RNG.

### Quick-run
`uv run --frozen pytest -q tests/coordination/test_coord_mission_factory.py tests/_factories/test_make_mission_parity.py`

## WP03

### CORRECTION (BLOCKING): the `mission_runtime` submodule import is forbidden
- The prompt says "specify_cli may import `mission_runtime.resolution`".
- MR-1 `test_mission_runtime_surface.py::test_no_external_submodule_imports` (:244) and MR-2 `test_ast_scan_no_external_internal_imports` (:342) forbid any `src/` module outside `mission_runtime` from importing a submodule. The AST scan catches lazy imports too.
- `coord_seed.py` must import `WriteLocation` / `Establishment` / `SeedReport` from the package root. That requires editing `src/mission_runtime/__init__.py` (re-export plus `__all__`) and `_PUBLIC_SURFACE` in `test_mission_runtime_surface.py:50`, which `test_public_surface_is_exactly_all` asserts with strict list equality (order matters).
- **Neither file is in any WP's owned_files** (grep over `tasks/*.md`: 0 hits). Add both to WP03 (and WP04 for `write_dir`, if it exports anything).
- `test_package_root_cold_imports` (:223) keeps `import mission_runtime` cold, so `CoordState` must be a `TYPE_CHECKING`-only import in `write_location.py`.

### CORRECTION (error code)
- `ActionContextError(code, message)` stores `self.code` (`resolution.py:126-135`); there is no `error_code` attribute.
- Consumers branch on `.code`: `coordination/write_seam.py:312`, `next_cmd.py:873`.
- `CoordSeedForkRefused` must call `super().__init__("COORD_SEED_FORK_REFUSED", msg)`.

### CORRECTION (partition predicate)
- `_PLACEMENT_ARTIFACT_KINDS` is private (`artifacts.py:194`).
- Use the root-exported `kind_is_coordination_residue(kind, topology)` (`artifacts.py:131`) or `not is_primary_artifact_kind(kind)`, and filter `kind_for_mission_file(...) is None` explicitly.
- `DECISION_LEDGER` is COORD at HEAD (`artifacts.py:217`), so the seed copies `decisions/DM-*.md` / `index.json` until WP12 lands. That is a cross-lane timing dependency.

### Parallel authority (not in the prompt; top risk)
- `mission_runtime.assert_coord_write_materialized` (`write_target_degrade.py:157`, docstring: "the single decision locus for S-C (FR-006/#4970)").
- It is used by `coordination/write_seam.py:312` (`write_artifact`) and by `resolve_write_target_or_degrade(terminus_write=True)` (via `surface_resolver.resolve_for_write:847` ← `issue_verdict.py:348`).
- It **refuses** UNMATERIALIZED-with-local-head when the branch already carries a committed artifact of the kind (`COORD_WRITE_SURFACE_UNMATERIALIZED`). WP03's `establish` **materializes** that same state.
- After WP06, every post-fix branch carries content, so `write_dir` and `write_artifact` disagree on the same state. `establish_coord_write_location` must subsume that gate or call it, and its refusal tests must be re-pinned deliberately.

### Seam map and caller deltas
- `materialize_coord_surface_for_write` (surface_resolver.py:903) callers: `decisions/service.py:501`, `:696`; `_coordination_doctor.py:1424`.
- Owned arm: `_resolve_owned_coordination_workspace` is **private** in `runtime/next/runtime_bridge.py:417`. Import it lazily or relocate it. The owned coordination dir composes from `owned.repository_root` (`resolution.py:1290`), not `owned_root`.

### Locks
- Lock root: `BookkeepingTransaction.acquire` locks on `owned.owned_root if owned else repo_root` (`transaction.py:290-291`). The seed must use the same root, or reentrancy breaks on an owned checkout.
- `feature_status_lock` defaults to `timeout=-1` (`locking.py:278`), so `STATUS_LOCK_HELD` can never fire. Use `BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS`, like `coord_status_lock` (`status_transition.py:409-424`).
- Reentrancy is per thread, keyed on `coord_feature_dir.name`. It matches the router's `_coord_status_locks` (`commit_router.py:586`).

### Seed commit and results
- The seed commit policy should be `ProtectionPolicy.resolve_for_mission(repo_root, slug)` (`git/protection_policy.py:249`, honours `commit_to_target`), or `resolve_for_owned` (`:203`) plus `owned=`. The prompt has `resolve(repo_root)`.
- `CommitRouterResult.status` takes `committed | unchanged | no_op_wrong_surface | error` (`commit_router.py:175`), and `reason` disambiguates `unchanged`. Map every non-`committed` status, not only refusal.

### Side effect of adding `error_code` to `FeatureStatusLockTimeoutError`
- Generic `getattr(err, "error_code")` renderers change output on a real lock timeout: owned `mark-status` goes from `MARK_STATUS_FAILED` to `STATUS_LOCK_HELD` (`tasks_mark_status.py:573`); `next_cmd.py:873`.
- Existing pins use non-lock errors and stay green. Declare the change in the PR body.

### Restore over-reach (I-SEED-9 / US1.3)
- The T016 post-fix restore `git checkout HEAD -- kitty-specs/<dir>` restores whatever the coordination branch carries.
- A branch cut or fast-forwarded after a target commit (the Gap-1 fast-forward in `doctor coordination --fix`, or `--force-recreate-coordination-branch`) carries root-committed `meta.json` / `spec.md`.
- Restrict the restore pathspec to COORD-kind paths.

### Dead-module gate
- `coord_seed.py` has no `src/` caller until WP04 lands, so `tests/architectural/test_no_dead_modules.py` goes red **in WP03's lane** (it is a separate gate from `test_no_dead_symbols`).
- Either accept a lane-local red with a note, or have WP03 add a trivial production caller. Private-prefix the step helpers: the widened dead-symbol gate covers all public module-level names.

### Value objects
- `@dataclass(frozen=True, kw_only=True)` is needed: adding `checkout_root: Path` (P-M3) after `seed: SeedReport | None = None` is a `TypeError`. The contract signature block omits `checkout_root`.
- `WriteLocation.surface: Literal["primary","coordination"]` duplicates `TopologySurface` (`mission_runtime.artifacts`; glossary surface Sense 2). Prefer the enum, or WP07-WP18 will each translate strings.
- `Establishment.MATERIALIZED` collides by name with `CoordState.MATERIALIZED`.

### Paths and Windows
- Compose temp and target paths from `coord_feature_dir(...)` (`_read_path_resolver.py:218`).
- `os.rename` onto an existing dir raises on Windows.
- `git status --porcelain=v1 -z` returns `/`-separated paths; normalise before comparing with `Path`.

### Cold-import
`decisions.*` sits on the charter cold-import path (`decisions/service.py:497`; `test_cold_import_status_boundary.py`). Keep `coord_seed` module-level imports light.

### Valid guards (stay green)
- `tests/coordination/test_materialize_coord_surface.py`, `test_unmaterialized_remedy_text.py`;
- `tests/specify_cli/coordination/test_coord_topology_states.py`, `test_coord_branch_remote_probe_4979.py`;
- `tests/status/test_locking_key.py`, `test_locking_reentrancy_migration.py`.

### Quick-run
```bash
uv run --frozen pytest -q tests/coordination/test_coord_seed.py tests/coordination/test_event_prefix.py tests/mission_runtime/test_write_location.py tests/coordination/test_materialize_coord_surface.py tests/coordination/test_unmaterialized_remedy_text.py tests/specify_cli/coordination/test_coord_topology_states.py tests/specify_cli/coordination/test_coord_branch_remote_probe_4979.py tests/status/test_locking_key.py tests/status/test_locking_reentrancy_migration.py
uv run --frozen pytest -q tests/architectural/test_mission_runtime_surface.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_modules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_cold_import_status_boundary.py
```

## WP04

### CORRECTION (lazy-import suppression)
- `resolution.py` has **no** `# noqa: PLC0415`. The precedent lazy import at L2356 (`resolve_retrospective_home`) carries none.
- `PLC0415` is not in the selected ruff rules (pyproject.toml:2446-2468), so the prompt's `# noqa: PLC0415` is an unused suppression (NFR-005).
- The pattern comes from `surface_resolver.py:945`, which does carry it.

### CORRECTION (declared surface)
- "Reuse ≈L2518-2525 or extract `_declared_surface`" is unnecessary: L2523 sits inside `_classify_artifact_surface`.
- The public, owned-aware `declared_read_surface(repo_root, slug, kind, *, resolver=None, owned=None)` (`resolution.py:2451`, root-exported) is the decision. Call it with `owned=self.owned`.

### Seam map
- `PlacementSeam` is a frozen dataclass (`resolution.py:2260`) with fields `repo_root, mission_slug, owned`, validated in `__post_init__`.
- `write_target` is at L2304, `read_dir` at L2318, `placement_seam` at L2835.

### Hazards
- **checkout_root re-anchor.** `read_dir` re-anchors through `get_main_repo_root(repo_root)` (L2346-2355). PRIMARY `WriteLocation.checkout_root` must be the main repo root (or `owned.owned_root`), not `self.repo_root` verbatim. Otherwise `path` and `checkout_root` disagree when called from a lane worktree. Pin this in T020.
- **Exception types.** `CoordinationBranchDeleted` and `CoordinationWorktreeUnmaterialized` are `StatusReadPathNotFound` subclasses (surface_resolver.py:191, :292), not `ActionContextError`.
  - `resolve_placement_only` translates them; `write_dir` will not.
  - Document this in the docstring, and tell the WP07+ writers that catch only `ActionContextError`.
- **D4 discriminator: reuse and fix the existing probe** `coord_branch_has_committed_artifact(repo_root, coord_branch, mission_slug, kind)` (surface_resolver.py:786).
  - It composes `kitty-specs/{mission_slug}/`, not `_compose_mission_dir(slug, mid8)`, so it misses a slug without the mid8 suffix.
  - It fails closed to `True`, so a git error would read as post-fix, which means loud.
  - Keep one definition, have WP03 reuse it, and widen WP01's `_empty_coord_surface` signature for `repo_root` / `coord_branch` (ruff ARG blocks pre-adding them in WP01).
- **D4 over-matches.** `tests/coordination/test_surface_resolver_solo_coord_primary.py::_build_solo_pr_bound_coord_mission` (:107-146) commits `kitty-specs/<slug>/meta.json` on the target **before** `git branch <coord>`. Its coordination branch tree therefore carries the dir and reads as post-fix.
  - The file has no `caplog` asserts, so it stays green, but it shows that real pre-fix Missions (branch cut after the first target commit) will warn.
  - Discriminating on a COORD-kind file (`status.events.jsonl`) or on the seed-commit trailer is more robust. This is the mislabelled-fixture case T021 says to "stop and report".
- **Duplicate warnings.** The EMPTY warning is reached from `resolve_placement_only` (`_assemble_core_fragments(for_write=True)`), so post-fix EMPTY will warn on every `write_target` / commit-ref query, and again from `establish`. Consider gating the warning on `not for_write`.
- **Purity probe.** `probe_coord_state`'s DELETED arm may hit the network (`remote_branch_lookup`). The T020 purity snapshot (`for-each-ref` plus `worktree list --porcelain`) needs remote-less fixtures.
- **CommitTarget scan.** `test_no_write_side_rederivation.py` is a whole-tree AST scan of `CommitTarget(...)` / `safe_commit(...)` constructions. `write_dir` must not construct a `CommitTarget`.
- **Layer ledger.** The `coordination` and `missions` edges are already allowed (`test_layer_rules.py:116-140`, cap 10, `_baselines.yaml:21`). The `TYPE_CHECKING` import of `CoordState` adds no edge.

### Valid guards (stay green unchanged)
- `test_surface_resolver_coord_empty_warning.py::test_coord_empty_with_lanes_warns_loudly_and_returns_primary` (:127);
- `::test_coord_empty_solo_no_lanes_stays_quiet_and_returns_primary` (:179). Its coordination branch is cut from an empty init commit, so it is pre-fix under D4.

### Quick-run
```bash
uv run --frozen pytest -q tests/mission_runtime/test_placement_seam_write_dir.py tests/coordination/test_surface_resolver_post_fix_empty_loud.py tests/mission_runtime/test_placement_seam.py tests/mission_runtime/test_placement_seam_owned.py tests/mission_runtime/test_resolve_placement_only.py tests/coordination/test_surface_resolver_coord_empty_warning.py tests/coordination/test_surface_resolver_solo_coord_primary.py tests/coordination/test_surface_resolver_collapse.py tests/specify_cli/coordination/test_status_surface_owned.py tests/specify_cli/coordination/test_owned_status_read_contract.py tests/specify_cli/coordination/test_legacy_warning_classifier.py tests/status/test_aggregate_surface_resolution.py
uv run --frozen pytest -q tests/architectural/test_layer_rules.py tests/architectural/test_mission_runtime_surface.py tests/architectural/test_status_state_read_dir_single_authority.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py
```

## WP05

Cited lines match HEAD: commit_router L166/167/436/457/477/560-561/639/802/991/1038/1302; `test_commit_router.py` L953/L1012.

### CORRECTION (T029 step 3)
- The partition split runs only when `owned is None`. L278 reads `groups = [(kind, files)] if owned is not None else _group_files_by_partition(...)`, so threading `owned` into the split does nothing.
- Owned Missions cannot be coordination-routed today: `core/owned_mission.py:57` `LIFECYCLE_OWNED_TOPOLOGIES == {SINGLE_BRANCH}`. The "owned coordination" edge cases in WP05, WP06 and WP07 are forward guards only, so label them as such.

### CORRECTION (T024 step 2)
- `COORDINATION_BRANCH_DELETED` has no module constant. It is `CoordinationBranchDeleted.error_code` (surface_resolver.py:205), plus a literal at `runtime/next/runtime_bridge.py:468`.
- The status/reason literals are also duplicated in `coordination/surface_authority.py:261-268`, and `_exit_code_for` (L315) calls itself "the canonical exit-code mapping".
- So a new `commit_outcome_exit_code` would be a **second exit-code authority**. Make `commit_outcome` the single owner of the literals and the exit code, and have `surface_authority` import it.

### CORRECTION (T024 step 6, dead symbols)
- "Record the expectation in the activity log" does not satisfy the gate.
- `test_no_dead_symbols` counts only `src/` importers. `render_commit_outcome`, `commit_outcome_payload`, `commit_outcome_exit_code` and the public partition predicate (P-M5) have no `src` caller until WP08, WP10 and WP13-16, so the lane-A tip goes red.
- The allowlist is a **capped ratchet** (`_baselines.yaml:443` `allowlist_entries: 293`). Adding an entry needs a baseline bump plus a justification and a ticket.
- Decide one of:
  - (a) a category-C in-flight allowlist entry plus a +N bump, which WP20 removes;
  - (b) give each new public name one real `src` consumer in WP05 (for example `surface_authority` importing the literals);
  - (c) keep the names private until the consumers land.

### Seam map
- `commit_for_mission` (L218) has a required 4th positional, `policy`. Prompt snippets that omit it will not type-check.
- `_stage_artifacts_in_coord_worktree` takes no `mission_slug` and no `owned`, and T027 needs both for `write_dir`. Add them **keyword-only and optional**.
- That keeps the three-positional unit callers green: `test_commit_router.py:792/833/871/891`, `test_finalize_coord_staging.py` (×5), `test_finalize_clobber_e2e.py:374` and `test_wp06_sc2_paused_mission_blockers.py:658/680/714`. Those tests build fake worktrees with no `meta.json`, so an unconditional `write_dir` would raise.
- Second production caller: `_resolve_commit_worktree_for_kind` (L1230). It is the planning-commit path, re-exported by `agent/mission.py:296` as `_planning_commit_worktree`.
- `_materialise_coord_worktree` (L863) already resolves the worktree via `CoordinationWorkspace.resolve` (L939). Resolve **one** `WriteLocation` per staging call, not per path.
- `_merge_group_results` (L833-835) returns the first error as-is. "Error carries all surfaces" needs `replace(result, surfaces=...)` there.
- `_try_advance_ref` refs: L556/561/1302/1341 and `test_commit_router_fail_loud.py:320`. No test pins the fast-forward advance, so removal is clean.

### Pinning tests
- **#5353 pin at risk:** `test_commit_router.py::test_coord_staging_keeps_a_status_log_already_in_the_coord_worktree` (L812) asserts `coord_files == [coord_log]` with both the worktree log and the root log passed. Translating the root log to the same worktree path produces a **duplicate**. Dedupe while keeping order.
- Valid guard: `test_finalize_clobber_e2e.py::...::test_coord_refinalize_with_only_status_changes_is_noop` (root status dirt on re-finalize gives a no-op with exit 0). It must survive T028's `COORD_RECORD_IN_ROOT_CHECKOUT` skip.
- Mock coupling: `test_commit_router_fail_loud.py` patches `CoordinationWorkspace.resolve` ×5, and `test_commit_router.py` ×2. Keep `write_dir` lazy and patch-compatible.
- No test does `== CommitRouterResult(...)` or `asdict`, so the additive `surfaces` field is safe.

### Hazards
- **Recursion:** the WP03 seed commits via `commit_for_mission` (`contracts/seed.md` step 9), and T027 calls `write_dir`, which can seed. This is safe only while the seed passes in-worktree paths, which hit the IN_PLACE branch first. Add a test.
- **Lock key:** `coord_status_lock` keys on `coord_feature_dir.name` (`status_transition.py:421-423`). The seed lock must key on the same name.
- **Layering:** `test_commit_router_layering.py` forbids `from specify_cli.cli` in `commit_router`. Keep `commit_outcome` free of `cli` console helpers.
- **Windows:** `✓`/`✗` printed raw can raise `UnicodeEncodeError` on cp1252. Print through rich or use an ASCII fallback.
- **C901:** `_commit_partition_group` 8, `_safe_commit_group` 6, `_merge_group_results` 5.

### Quick-run additions
`uv run --frozen pytest -q tests/specify_cli/cli/commands/agent/test_finalize_coord_staging.py tests/specify_cli/cli/commands/agent/test_finalize_clobber_e2e.py tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py tests/specify_cli/cli/commands/agent/test_mission_shim_reexports.py tests/git/test_commit_to_target_scope_guards.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py`

## WP06

### CORRECTION (T031 step 3)
The snippet's `commit_for_mission(...)` omits the required positional `policy`.

### CORRECTION (T033 S9)
- The empirical topology check is unnecessary: `create_mission_core` defaults to `topology=MissionTopology.COORD` (mission_creation.py:770).
- The `origin/HEAD` fallback only affects the CLI default.

### Seam map
- `_scaffold_mission_dir` (L1138) builds `scaffold_paths` and touches the root checkout. `topology` is already a parameter there.
- The seed must run after `write_meta` (L1336, still uncommitted) and before `_commit_create_scaffold` (L1938).
- `_emit_create_events` reads back at L1502 from `feature_dir`. Add a `status_dir` parameter.
- `_build_create_result` L1688/L1697 must point at the coordination log, and hosted fan-out reads `log_path`. Pass the value; do not re-derive it.
- `ensure_coordination_branch` has one caller (`mission_creation.py:1302`). Its tests:
  - `tests/core/test_mission_creation_topology.py`
  - `tests/specify_cli/cli/commands/agent/test_mission_create.py`
  - `tests/migration/test_birth_cutover.py`

### Rollback (top risk)
- `mission_slug_formatted` and `mid8` are minted inside `_create_mission_core_impl` (L1875-1880), so the outer `create_mission_core` (L760) rollback cannot name the worktree. Snapshot the worktree list plus a `{branch: sha}` map in the outer function (it already diffs `_list_coordination_branches`).
- With `--owned-checkout`, `rollback_root` is the owned checkout.
- `CoordinationWorkspace.teardown` (workspace.py:352) refuses a **dirty** worktree (`DestructiveOpRefused` via `guarded_worktree_remove`). A failure between emit and the coordination commit leaves it dirty, so best-effort rollback silently orphans the worktree, and the branch delete then fails. Restore or clean first, or use the `is_residue` hook.
- `force_recreate` moves a pre-existing branch, so the CAS reset needs the pre-create tips.

### Doctor predicate
- `_coord_branch_stale_vs_target_finding` is also reached by finalize's `check_and_warn_coord_staleness` (`tasks_finalize.py:541`).
- Add `mission_dir_name` **keyword-only with a default**: `tests/coordination/test_coord_staleness.py` L141/150/163 call it with 3 positionals, and L189 monkeypatches it with `lambda *a`.
- `git diff-tree` prints nothing for merge commits without `-m`, so reject merges or use `--first-parent -m`.

### Stale pins outside WP06's surface (re-pin deliberately)
- `tests/core/test_mission_creation_decomposition.py::test_status_log_holds_exactly_created_and_specify_started` (L281) reads `feature_dir/status.events.jsonl`.
- `tests/core/test_mission_creation_fanout_commit_boundary.py` L27/L103/L117 pin the root log in `uncommitted_files`.
- `tests/specify_cli/core/test_mission_creation_specify_started.py` L105/131/169/207. It is **not under `tests/core/`**, so the directory run misses it.
- Probable reds to check:
  - `tests/core/test_mission_create_scaffold_rollback.py`
  - `tests/specify_cli/core/test_feature_creation.py`
  - `tests/integration/test_specify_plan_commit_boundary.py`
  - `tests/coordination/test_materialize_coord_surface.py`
  - `test_mission_create_json_remediation.py`
- 51 test files call `create_mission_core`, but `make_mission` defaults to `SINGLE_BRANCH`, which limits the blast radius.

### Gate
- `test_no_write_side_rederivation.py` scans `mission_creation.py` (it is in `_ADOPTED_MODULES`, L87-111) and flags `parent . parent` (`root_walk`, L254). Use `checkout_root`.
- Upstream R1 asserts on the tip tree (`on_target`), not history, so T030 must change the assertion. Upstream has no R1b.

### Quick-run additions
`uv run --frozen pytest -q tests/core/test_mission_creation_fanout_commit_boundary.py tests/specify_cli/core/test_mission_creation_specify_started.py tests/core/test_mission_create_scaffold_rollback.py tests/core/test_mission_create_checkout_restore.py tests/coordination/test_coord_staleness.py tests/specify_cli/core/test_feature_creation.py tests/core/test_mission_creation_topology.py tests/migration/test_birth_cutover.py`

## WP07

### CORRECTION (T038 step 4 vs 5)
`_coord_feature_dir`'s only production caller is `_emit_on_coord_then_commit` (`status_transition.py:492`). Deleting it means editing that function. Its order-of-operations can stay identical; its bytes cannot.

### CORRECTION (objectives/DoD)
- The L489-490 composition is shared by all four `_acquire_locked` arms: legacy lane, coordination-less, `commit_to_primary_target`, coordination.
- Only the coordination arm switches to `write_dir`. Deleting the composition outright breaks the C-008 controls.

### CORRECTION (T039 step 1)
It still permits a `.path.parent.parent` derivation. P-M3 forbids it, and `test_no_write_side_rederivation.py` `root_walk` already flags it in `status_transition.py`.

### CORRECTION (T041)
- `placement_seam` / `MissionArtifactKind` are already module-level imports in `lanes/recovery.py:12`, so no lazy import is needed.
- L785 is the only use of `resolve_feature_dir_for_mission`, so the L15 import becomes unused (F401). Remove it.

### CORRECTION (T040 framing)
- The non-owned mark-status write leg does not use `feature_write_dir`. It uses `resolve_status_surface(...).parent` (`tasks_mark_status.py:231`).
- `feature_write_dir` callers are `tasks_move_task.py:558` and `tasks_mark_status.py:227` (owned arm only). WP07 alone does not fix mark-status.

### Seam map
- `_resolve_fallback_coord_worktree` is used by **unowned** tests:
  - `tests/coordination/test_status_write_authority.py` L130/186-190/236/267, with direct `is None` shape asserts;
  - `tests/specify_cli/coordination/test_plain_door_semantics.py:143-150`, which monkeypatches it.
  - Keep its name and signature, or declare an out-of-map re-pin.
- `_read_contract_from_transaction_target` (L1357-1368) still composes `worktree_path / KITTY_SPECS_DIR / _transaction_dir_name`. Record it as a sanctioned read-side residual, so the reviewer's `KITTY_SPECS_DIR` grep does not bounce the WP.
- **Owned root:** `BookkeepingTransaction.acquire` passes `repo_root=lock_root` = `owned.owned_root` when owned (`transaction.py:291/300`). Inside `_acquire_locked`, build `placement_seam` from `owned.repository_root` plus `owned=`, never from the inner `repo_root`.
- `feature_write_dir`'s result also feeds `check_pre30_layout` (L560) and `_read_transactional_wp_lane` (L571), which now run on the coordination dir.
- **Do not add a `kind` parameter** to the protocol: 14 test fakes implement the 1-argument `feature_write_dir`:
  - `tests/review/test_cycle.py` ×6
  - `test_move_task_*` ×5
  - `test_tasks_ports.py`
  - `test_verdict_save_performance.py`
  - `test_pre_review_gate_integration.py`

### Pinning tests
- **Stale ledger:** `tests/architectural/test_no_read_side_bypass.py` allow-lists `agent_tasks_ports.py::RealCoordCommitRouter.feature_write_dir` and `lanes/recovery.py::reconcile_status`. Its twin guard `test_allow_list_entry_is_still_a_live_finding` goes red once those calls are removed.
  - Delete both entries in WP07.
  - The file is missing from WP07's gate list and owned_files.
- `tests/mission_runtime/test_coord_read_seam_callers.py`:
  - L259 is WP07's re-pin.
  - **L198 is the decision test WP09 needs flipped, and WP07 owns it.** WP07 must re-pin L198 too, or WP09 edits a file it does not own (P-M1 follow-through).
  - L346 is a single-branch guard that stays green.
- `tests/specify_cli/coordination/test_transaction.py` uses `MISSION_SLUG="demo-feature"` (no mid8). That directly exercises the dir-name agreement (T039 step 4). Run it by name.

### Hazards
- C901: `_acquire_locked` is at 9, so extract the coordination arm. `reconcile_status` is at 8.
- `run_recovery` (L902) catches `Exception` per WP, but the per-emit `try/except Exception: break` (L819) swallows refusals raised inside the emit.
- The seed in `_acquire_locked` runs before the in-lock `from_lane` read, which is correct; keep that order.

### Quick-run additions
`uv run --frozen pytest -q tests/architectural/test_no_read_side_bypass.py tests/architectural/test_no_write_side_rederivation.py tests/specify_cli/coordination/test_plain_door_semantics.py tests/coordination/test_status_write_authority.py tests/specify_cli/coordination/test_transaction.py tests/specify_cli/coordination/test_status_transition.py tests/review/test_cycle.py tests/specify_cli/cli/commands/agent/test_tasks_ports.py tests/mission_runtime/test_coord_read_seam_callers.py`

## WP08

### CORRECTION (T044 step 3, blocking)
- The readers do **not** read the coordination copy. All five call `_review_cycle_wp_dir` with the default kind (`WORK_PACKAGE_TASK`, so PRIMARY):
  - `review/cycle.py:520`
  - `review/arbiter.py:415`
  - `tasks_verdict_persistence.py:734` (the safety verdict reader, **unowned**)
  - `workflow_cores.py:419`
  - `workflow_executor.py:1127`
  - The writer is at `cycle.py:1271`.
- Moving only the writer makes rejections invisible to the readers (fail-open), and `tests/coordination/test_verdict_dir_co_resolution.py::test_multi_consumer_co_resolution_under_coord_topology` goes red.
- **Do not re-pin that test.** Flip `_review_cycle_wp_dir`'s default kind to `REVIEW_CYCLE` in `cycle.py` (owned), so all six sites move in lockstep. The AST guard in that test allows `kind=REVIEW_CYCLE` only, with exactly 3 positionals.

### CORRECTION (T046)
- `tasks_mark_status.py:279` is in `_ms_commit`, a dead compat shim that `_do_mark_status` never reaches.
- The live write is `_ms_emit_subtask_state` (L359). Its non-owned arm calls the flat `emit_inner_state_changed(st.status_dir, ...)` (L406-413) and **commits nothing**. Assert on the file, not on the branch tip.

### Missed writers
- The approval leg: `tasks_verdict_persistence.py:880,915` (`create_rejected_review_cycle(verdict="approved")`).
- `workflow.py::review`, L1999-2025, hand-joins `_resolve_workflow_read_dir(kind=WORK_PACKAGE_TASK)/"tasks"/wp_slug`, `mkdir`s it, and numbers feedback with `next_review_feedback_source_path(sub_artifact_dir)`. After the flip:
  - the numbering restarts at 1;
  - an empty PRIMARY dir is created on every review.
  - Route it through `_review_cycle_wp_dir`.

### Evidence ref
- `_evidence_ref` (L803) relativizes against `operation_root` (the repository root checkout). The coordination worktree is nested inside it (`.worktrees/<slug>-coord/`), so this does **not raise**.
- It silently yields `.worktrees/...-coord/kitty-specs/...`. The `git show <coord>:<that>` read-back then misses, giving `destination_readback_missing` / `persistence_failed`.
- Relativize against `write_dir(REVIEW_CYCLE).checkout_root`. This is a textbook P-M3 site.

### Path-dependent internals
`_resolve_review_body`, the provenance guard, `_local_matching_retained_review_cycles` and cycle allocation all take `sub_artifact_dir`. They must all receive the coordination dir.

### Output
`_ms_output` (L441-442) `status_events_path` / `status_snapshot_path` **values** change for coordination Missions. That is not additive-only; say so in the PR.

### C901
- `_mr_emit_output` (`tasks_map_requirements.py:688`) is already at 11; put the `surfaces` payload in a helper.
- `resolve_review_cycle_pointer` is at 10.

### Stale pins (unowned; declare out-of-map)
- `tests/specify_cli/review/test_cycle_kind_flip.py::test_physical_write_home_is_primary_so_rehome_guard_stays_green` (L201-231);
- `tests/specify_cli/test_read_seam_leniency.py::test_review_cycle_wp_dir_preserves_primary_home` (L145);
- `tests/specify_cli/test_owned_history_support.py` (~L318-325);
- `tests/integration/test_review_durability_matrix.py:1605` (by name only).

### Valid guards
- all of `test_verdict_dir_co_resolution.py`;
- `test_cycle_kind_flip.py::test_verdict_reader_authority_is_decoupled_from_write_side_kind` (L159);
- `test_read_seam_leniency.py::test_review_cycle_wp_dir_stays_silent_when_coord_deleted`.

### Hazards
- **E2 gap** (see the cross-cutting section).
- A new `/ "tasks" / wp_slug` join in a new helper is an un-inventoried sink. `test_untrusted_path_containment.py::test_all_discovered_rows_appear_in_inventory` needs a row in `untrusted_path_audit/inventory.md`.
- **Lock ordering:** `create_rejected_review_cycle` runs under the verdict-queue lease, and `write_dir` may take the status lock to seed. Confirm the lease is not the "workspace" lock (I-SEED-2).

### Quick-run
`uv run --frozen pytest -q tests/review/ tests/coordination/test_verdict_dir_co_resolution.py tests/coordination/test_analysis_report_rehome.py tests/specify_cli/review/test_cycle_kind_flip.py tests/specify_cli/test_read_seam_leniency.py tests/specify_cli/test_owned_history_support.py tests/specify_cli/cli/commands/agent/test_tasks_mark_status_seam.py tests/specify_cli/cli/commands/agent/test_mark_status_authored_roster.py tests/specify_cli/cli/commands/agent/test_workflow.py tests/architectural/test_merge_reconciliation_class_guard.py tests/architectural/test_untrusted_path_containment.py tests/architectural/test_write_surface_placement_guard.py tests/architectural/test_no_write_side_rederivation.py` plus the WP's new test files.

## WP09

### CORRECTION (T048)
- Decision rows have no Lamport field. Their keys are `event_id`, `at`, `event_type` (`"DecisionPointOpened"`, not `"DecisionOpened"`) and `payload` (`decisions/emit.py:241-245`).
- The clock is the line-count proxy returned by `_append_raw_event` (`emit.py:140`), surfaced as `event_lamport` in `decision open --json` (`decision.py:162`).
- Assert on that, or on log position.

### CORRECTION (T051 "degrade")
- A coordination-routed non-owned failure today **fails closed**: `except Exception` raises `DecisionGitLogUnavailable` (`runtime_bridge.py:403-408`). Only the coord-less arm falls back to the plain emitter.
- Keep fail-closed.

### Seam map
- **`service._events_path` also serves reads.** `_opened_event_exists` (L303-312, from `_repair_missing_opened_event` L336/L529) reads through it.
  - If `service._mission_dir` returns `write_dir`, that idempotency probe becomes a seed or materialize.
  - Apply the T049 read/write split in `service.py` too, not only in `emit.py`.
- **Unlisted callers of `open_decision`:**
  - `charter/_widen.py`, `charter/interview.py`
  - `missions/plan/{plan,specify}_interview.py`
  - `orchestrator_api/commands.py:144`
- **Exception handling:** `decision.py:217` (`_handle_status_read_path_error`) catches only `StatusReadPathNotFound`, so `CoordSeedForkRefused` (an `ActionContextError`) and the lock timeout surface as raw tracebacks.
  - `decision.py` is **unowned**.
  - Either WP03 makes them `StatusReadPathNotFound`-compatible, or WP09 declares an out-of-map edit.
- **`DecisionGitLog(` constructors:** all are covered by the six owned test files, plus `runtime_bridge.py:375`.
  - `worktree_root` stays needed: it is the commit `cwd` (L252). Take it from `checkout_root`.
  - The coord-less arm must pass `mission_dir = anchor_root/kitty-specs/<slug>`, the owned root for owned coord-less Missions (C-008).
- `materialize_coord_surface_for_write` stays live after WP09 (`_coordination_doctor.py:1424`). Do not delete it.
- `resolve_commit_target` (`runtime_bridge_io.py:1505`) still computes `worktree_root_candidate` by naming convention (the sanctioned residual at `test_no_write_side_rederivation.py:809`). The coordination arm must use `checkout_root` instead.

### Stale pin
- `tests/mission_runtime/test_coord_read_seam_callers.py::test_decisions_emit_mission_dir_fails_loud_sanely` (L198) expects a **raise** on UNMATERIALIZED with a local branch; `write_dir` materializes instead.
- WP07 owns the file and must re-pin it before WP09.

### Valid guards
- `test_read_seam_leniency.py::test_decisions_mission_dir_fails_loud_when_coord_deleted` (`write_dir` must raise `CoordinationBranchDeleted`);
- `::test_decisions_mission_dir_preserves_healthy_status_home`;
- `test_coord_read_seam_callers.py::test_decisions_emit_mission_dir_no_raise_on_single_branch`;
- `test_decision_fresh_coord_5113.py`:
  - `test_materialization_failure_is_byte_identical`;
  - `test_list_and_verify_never_materialize` and `test_dry_run_never_materializes`: list, verify and dry-run must never reach `write_dir`;
  - the remote-only refusals.
- `test_decision_log.py:493`: an unsafe slug raises `ValueError` before placement.

### Hazards
- Status lock key in `emit.py:138` is `feature_dir.name` and must equal the seed lock key (P-M4).
- Keep the `mission_runtime` import function-local in `decisions/*` (cold-import boundary).
- The runtime outbound ledger stays green (`specify_cli.coordination` is already imported at `runtime_bridge.py:1765,3415`). Add no new `specify_cli` subpackage edges from `runtime`.
- **P-M3 gap:** `decisions/*`, `events/decision_log.py` and `runtime_bridge*.py` are **not** in `test_no_write_side_rederivation._ADOPTED_MODULES`. `test_no_worktree_name_guess.py` excludes `.parent.parent` (L474-476). No gate catches a `checkout_root` re-derivation here, so review must catch it.
- C901: `_wrap_with_decision_git_log` 11; `open_decision` 8.

### Quick-run
`uv run --frozen pytest -q tests/specify_cli/decisions/ tests/runtime/test_bridge_decision_log_flush.py tests/runtime/test_bridge_composition.py tests/runtime/test_bridge_io.py tests/specify_cli/events/test_decision_log.py tests/specify_cli/events/test_decision_log_coord.py tests/specify_cli/coordination/test_residual_writer_routing.py tests/specify_cli/regression/test_issue_1615_1616_1617_1618.py tests/git/test_guard_capability_regression.py tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py tests/specify_cli/test_read_seam_leniency.py tests/mission_runtime/test_coord_read_seam_callers.py tests/architectural/test_layer_rules.py tests/architectural/test_cold_import_status_boundary.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_status_events_writes_gate.py`

## WP10

Cited lines confirmed: `write_seam.py` 215/460/548; tracer 199/213/227; `tracer_append.py:135-171`; `issue_matrix` 448/503/505; `matrix.py` 449/469/524/537. Minor drift: `_matrix_read_dir` is at L89, not L87.

### CORRECTION (T057, lost-update)
- The acceptance write goes through `acceptance/matrix.py:546` `locked_reread_splice_and_write` (from `acceptance_verdict.py:319,390` and `gates_core.py:647`).
- Its C-004 contract resolves `matrix_dir` **once, before the lock**, as both the re-read base and the write target, with the lock key `matrix_dir.name` (#4858/#4887).
- A read/write split, or resolving `write_dir` lazily inside `_stage`, reintroduces the lost update on a pre-fix EMPTY Mission (re-read from PRIMARY, write to coordination).
- Resolve `write_dir(ACCEPTANCE_MATRIX)` once before the lock and pass it as `matrix_dir`. The cost is a seed side effect before the lock; decide that explicitly.
- Same twin in `issue_verdict.py:271-285` (`feature_status_lock(repo_root, read_dir.name)` around `write_issue_matrix(read_dir...)`), which is **unowned**.

### Unlisted callers
- `write_issue_matrix`: `issue_verdict.py:285`, `issue_matrix_migration.py:370`.
- `write_and_commit_acceptance_matrix`: `matrix.py:910` (`scaffold_acceptance_matrix`).
- `gates_core._acceptance_matrix_read_dir`: a mirror of `_matrix_read_dir` used as a write dir (WP16 ground).
- `append_tracer_finding` has **no** `owned` parameter, so the prompt's "thread it if present" step does not apply.

### Hazards
- **Tracer read before write:** `_read_current_coord_content` (L155-185) runs before the thunk and raises `CoordinationWorktreeUnmaterialized`, so `write_dir` never gets to materialize. Merge the base content inside `_stage`, after `write_dir`.
- **Stale allow-list entry:** removing `candidate_feature_dir_for_mission` from `_local_staging_path` reds `test_no_read_side_bypass.py::test_allow_list_entry_is_still_a_live_finding` (descriptor L601-619). That file is **unowned** by WP10; declare it.
- **Valid guard:** `test_coord_read_seam_callers.py::test_tracer_append_cli_structured_refusal_on_unmaterialized` (L379). Keep the CLI `except CoordinationWorktreeUnmaterialized` / `except UnicodeDecodeError` arms when switching to the shared renderer.
- **E2** and **two-policies** (see cross-cutting): `write_artifact` already calls `assert_coord_write_materialized` before `stage()`.
- C901: `write_artifact` ≤7; `tracer_append` 8; `_validate_mode_selection` 9.

### Quick-run
`uv run --frozen pytest -q tests/coordination/test_write_seam_surfaces.py tests/coordination/test_write_seam_adoption.py tests/specify_cli/retrospective/test_tracer_writer_coord_e2e.py tests/specify_cli/test_accept_no_commit_readonly.py tests/specify_cli/coordination/test_residual_writer_routing.py tests/mission_runtime/test_coord_read_seam_callers.py tests/integration/test_accept_matrix_coord_partition.py tests/integration/test_issue_2404_acceptance_matrix_write_surface.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_write_surface_placement_guard.py tests/architectural/test_issue_matrix_json_migration_completeness.py tests/architectural/test_status_events_writes_gate.py` plus the WP's new files.

## WP11

### CORRECTION (owned_files incomplete)
- Missing CLI registration: `src/specify_cli/cli/commands/__init__.py:362` (`app.command(name="merge-driver-...", hidden=True)`) and `:656` (`_COMMAND_REGISTRARS`).
- Missing `src/specify_cli/_completion_manifest.json`; otherwise `test_completion_manifest_freshness.py` goes red.
- Missing a golden dir `tests/consolidation/merge_driver_goldens/merge-driver-decision-index/`.

### CORRECTION (T061 spec fields)
- `_MergeDriverSpec` fields are `config_key`, `name` (the label), `command` and `pattern`; `attributes_line` is derived.
- Use `config_key="spec-kitty-decision-index"` and `pattern="kitty-specs/**/decisions/index.json"`.

### CORRECTION (T060 fold reuse)
- `index_fold.apply_terminal` (L144) applies terminal fields to one entry, and `_select_terminal_event` (L215) picks among events. Neither compares two `IndexEntry` versions, so terminal-beats-open must be written.
- `is_allowed_terminal_reopen` (L90) helps.

### Stale count pins (6 → 7)
- `tests/consolidation/test_merge_drivers.py::test_merge_driver_bodies_matches_the_two_other_driver_name_authorities`;
- `tests/consolidation/test_merge_driver_goldens.py::test_golden_cases_are_discovered_and_cover_all_six_commands`;
- `::test_distinct_config_key_count_matches_six_registered_commands`.

### Byte-stability
- The serializer is inline in `decisions/store.py:124-145`: `json.dumps(DecisionIndex(...).model_dump(mode="json"), sort_keys=True, indent=2) + "\n"`, sorted by `(created_at.isoformat(), decision_id)`.
- Round-trip through the `DecisionIndex` model, not raw-JSON sorting: pydantic's datetime JSON form differs from `isoformat()`.

### Valid guards (`test_merge_reconciliation_class_guard.py`)
- `test_declared_merge_drivers_are_registered_in_gitattributes`;
- `test_init_seed_is_superset_of_registry_merge_drivers`;
- `test_migration_seed_is_superset_of_registry_merge_drivers`: the new migration **must subclass `MergeDriverSeedingMigration`** (like `m_3_2_7`);
- `tests/agent/test_init_command.py` L290-345.

### Hazards
- **Dead symbols:** keep `union_decision_index` public but **out of `__all__`** until WP17 imports it. Intra-module use rescues non-`__all__` names only.
- **Wider reach:** `_MERGE_DRIVERS` also feeds `_ensure_info_attributes` (squash activation, `consolidation.py:488`) and `git_probes._resolve_registered_driver_callable` (#5038 squash projection replay). The new driver becomes authoritative in the reconciliation gate's blob attribution the moment it lands. Run `tests/consolidation/` gate tests by name.
- **Migration version:** `target_version="4.0.0rc5"` equals the package version. Projects already at rc5 get it only via `detect()` (`upgrade/registry.py:94-100`), so `detect()` must return true when the line or config is missing.
- **Stale install:** the real `git merge` test shells out to `spec-kitty`. Use the sibling pattern (absolute interpreter, `python -m specify_cli`).

### Quick-run
`uv run --frozen pytest -q tests/consolidation/test_decision_index_merge_driver.py tests/consolidation/test_merge_drivers.py tests/consolidation/test_merge_driver_goldens.py tests/upgrade/migrations/test_m_4_0_0rc5_decision_index_merge_driver.py tests/specify_cli/cli/commands/test_review_cycle_merge_driver.py tests/agent/test_init_command.py tests/architectural/test_merge_reconciliation_class_guard.py tests/architectural/test_completion_manifest_freshness.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py`

## Cross-cutting (synthesis)

### X1. Two write-side authorities (top risk; WP03/WP04/WP08/WP09/WP10)
- `mission_runtime.assert_coord_write_materialized` (`write_target_degrade.py:157`, docstring "the single decision locus for S-C (FR-006/#4970)") **refuses** UNMATERIALIZED-with-a-local-head when the branch already carries the kind.
- `write_dir` / `establish` **materializes** that same state.
- After WP06, every post-fix branch carries content, so `write_artifact` (WP10) and direct writers (WP08/WP09) disagree.
- **Decision needed before WP03:** `establish` subsumes that gate (and its refusal pins are re-pinned deliberately), or `write_dir` calls it.

### X2. E2 post-consolidation gap (WP03/WP04 contract; WP08/WP10 writers)
- `REVIEW_CYCLE`, `TRACER_FILE`, `ISSUE_MATRIX` and `ACCEPTANCE_MATRIX` are `_E2_CONSOLIDATED_ELIGIBLE_KINDS` (`resolution.py:191-199`): after consolidation `write_target` routes to the target branch.
- `contracts/write-location-accessor.md` says nothing about PUBLISHED/E2 (grep: 0 hits).
- If `write_dir` probes coordination state, post-consolidation review, tracer and matrix writes raise `CoordinationBranchDeleted`, or write into a torn-down worktree.
- Add the PUBLISHED row to the WP04 contract: return PRIMARY with `checkout_root` set to the main root.

### X3. P-M3 is not mechanically enforced where it matters
- WP07/WP09/WP03/WP17 name `test_no_worktree_name_guess.py` as the `.path.parent.parent` gate, but that file **explicitly excludes** the class (L474-476, deferred to #2007).
- The `root_walk` rule that does catch it lives in `test_no_write_side_rederivation.py` (L254) and scans only `_ADOPTED_MODULES` (L87-111: `status/*`, `status_transition`, `mission_creation`, `implement*`, `workflow*`, `tasks_move_task`, `mission_record_analysis`).
- `decisions/*`, `events/decision_log.py`, `runtime_bridge*`, `review/cycle.py`, the accept/doctor/consolidation consumers (WP09, WP16, WP17, WP18) and `coordination/commit_router.py` are unscanned.
- WP20 adds no such gate (grep: 0 hits).
- Fold: WP20 (or WP03) extends `_ADOPTED_MODULES` to every `write_dir` consumer, and the prompts cite the right gate.

### X4. Ownership spill into unowned files and gates
- No WP owns `src/mission_runtime/__init__.py` or `_PUBLIC_SURFACE` (`test_mission_runtime_surface.py:50`), and WP03 cannot compile against MR-1/MR-2 without them (blocking).
- WP11 lacks `cli/commands/__init__.py`, `_completion_manifest.json` and its golden dir.
- `test_no_read_side_bypass.py` stale allow-list entries hit WP07 and WP10.
- WP08: `test_cycle_kind_flip`, `test_read_seam_leniency`, `test_owned_history_support`, `tasks_verdict_persistence.py:734`.
- WP09: `decision.py:217` exception arm.
- WP06: `tests/specify_cli/core/test_mission_creation_specify_started.py` + two `tests/core/` files.
- Re-run `finalize-tasks --validate-only` after adding them; several cross lanes (e.g. `test_no_read_side_bypass.py` is touched by WP07 and WP10, `test_coord_read_seam_callers.py` by WP07 for WP09's pin).

### X5. Dead-symbol / dead-module ratchet reds at intermediate lane tips
- `coord_seed.py` is a dead module in WP03's lane until WP04 (`test_no_dead_modules.py`).
- The `commit_outcome` public API has no `src` consumer until WP08+ (`test_no_dead_symbols.py`; the allowlist is capped at 293 by `_baselines.yaml:443`).
- Pick the strategy up front: in-flight allowlist entries plus a baseline bump retired by WP20, or private names until consumers land.

### X6. Lock discipline
- The seed lock must use `owned.owned_root if owned else repo_root` (`transaction.py:290-291`), key on `coord_mission_dir_name` (= `coord_feature_dir.name`, matching `coord_status_lock` `status_transition.py:421-423` and `commit_router._coord_status_locks` :586) and use a bounded timeout (`feature_status_lock` default `-1`, `locking.py:278`; otherwise `STATUS_LOCK_HELD` is unreachable).
- Confirm the WP08 verdict-queue lease is not the "workspace" lock (I-SEED-2).

### X7. D4 discriminator over-matches
- "The coordination branch tree carries `kitty-specs/<dir>`" is true for pre-fix Missions whose branch was cut after the first target commit (fixture `test_surface_resolver_solo_coord_primary.py:107-146`).
- The same breadth makes WP03's whole-dir `git checkout HEAD -- kitty-specs/<dir>` restore copy PRIMARY files (I-SEED-9).
- Fix the existing `coord_branch_has_committed_artifact` (`surface_resolver.py:786`; it composes `kitty-specs/{mission_slug}` not `_compose_mission_dir`, and fails closed to `True`), discriminate on a COORD-kind file, and restrict the restore pathspec to COORD kinds.
