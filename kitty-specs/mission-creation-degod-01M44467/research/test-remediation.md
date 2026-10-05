# Test-suite remediation: tests covering `core/mission_creation.py` (#5634)

**Point-cut**: pre-spec / brownfield. **Procedure**: `packs/internal/procedures/test-suite-quality-assessment.procedure.yaml`, toolguide `test-quality-triage`, asset `test-quality-scan.py`. **Lens**: `reviewer-renata`, profile-loaded and read-only. **Base**: `origin/main` 9adc6880.

## Headline numbers

- **Covering set**: 42 files and 461 test functions (515 items). About 180 of them execute the module. 86 files mention it, but 44 of those only use `create_mission_core` as a factory.
- **Baseline**: 513 passed, 2 skipped, 0 failed in 2m13s (`-n 4 --dist loadfile`, no coverage). Under `--cov`, the two `test_mission_creation_fire_once.py` tests fail when co-scheduled on one worker. That is pre-existing and recorded as baseline-red, **#5706**.
- **Patch sites into `specify_cli.core.mission_creation`**: **277 sites, 13 names, 33 files** (an AST count). Before/after is the mission's reported metric.

| Name | Sites | Planned verdict |
|---|---:|---|
| `is_worktree_context` | 72 | (a)+(b): pass `allow_worktree_context=True` or `chdir`; the 3 refusal guards become real-worktree tests |
| `locate_project_root` | 45 | (c) retire ~42 dead sites (coverage contexts show the call site is never reached); (b) the 3 CLI tests use `chdir` |
| `is_git_repo` | 44 | (c) retire; the covering guard `test_not_a_git_repo_raises` is re-proved by a planted break |
| `get_current_branch` | 42 | (b) real repos on `main`; guard `test_detached_head_raises` |
| `_commit_feature_file` | 41 | (b) ~35 become real commits on an unprotected branch; (a) ~6 fault injections move to the commit adapter |
| `ULID` / `now_utc_iso` | 11 / 2 | (a) identity and clock become core inputs; the golden matrix normalises |
| `preflight_commit` / `safe_commit` | 5 / 4 | (a) patch the owning adapter |
| `_commit_create_scaffold` / `_consume_pending_origin_if_present` | 2 / 1 | (a) patch the owning module |
| `subprocess.run` | 1 | (b) adapter fault injection (today this patch replaces the **global** `subprocess.run`) |
| `create_mission_core` | 7 | keep (public façade) |

Target estimate: **277 → about 23** (about 7 on the façade, about 16 on owning adapters).

## Findings disposition

| # | Finding | Disposition | Where |
|---|---|---|---|
| T1 | 82% of patches target imported names and go inert silently when a reader moves | **accepted**: the PR #5679 routing gate plus a patch-liveness check over the `mission_creation*` family with an empty allowlist; the routing rule holds in every extraction WP | spec FR-005, C-004 |
| T2 | About 42 `locate_project_root` patches are already dead | **accepted**: retire them, with coverage-context proof recorded | WP05 |
| T3 | About 33 creates assert on a fake `main` (`git init` defaults to `master`, plus a patched `get_current_branch`) | **accepted**: rewrite onto real `main` repos (boy-scout, touched files only) | WP05 |
| T4 | 10 decision branches have no test (dirty-mint refusal, checkout-b failure, corroboration failure, MissionCreated payload mismatch, coordination commit failure, bootstrap skip, duplicate fail-closed on missing meta, abandoned StoreError, same-prefix neighbour guard, coordination rollback early return) | **accepted**: seam or golden coverage before the move (pure cores pinned directly; effect branches through the golden matrix or adapter fault injection) | WP01/WP02 |
| T5 | Sleeps (1.1s) and 25-create ULID test | **accepted**: identity and clock injected; the sleeps go away | WP02/WP05 |
| T6 | Proposed shrink-only patch-count ratchet test | **changed**: rejected per the operator ruling "no new size or ratchet gates". The count is measured and reported before and after in the PR instead; liveness (not count) is gated by T1 | PR body |
| T7 | Global `subprocess.run` patch in `test_mission_create_scaffold_rollback.py` | **accepted**: move to adapter fault injection | WP05 |
| T8 | `test_selector_resolution.py` marked `fast` but takes 25s | **deferred_with_rationale**: outside the mission's file set (it patches `create_mission_core` only); note in PR | PR body |
| T9 | `test_agent_feature.py` has 34 over-mocking flags | **accepted (partial)**: the create assertions move to the golden CLI smoke tests; the CLI-wiring tests stay | WP05 |
| T10 | Golden matrix design (zero patches, core plus CLI files, normalised snapshot, rollback pre/post equality) | **accepted** as WP01; it pins current behaviour, including the #5704 orphan | WP01 |

Retiring a test is allowed only with its covering guard named and re-proved by a planted break, recorded in the WP's review notes (DIRECTIVE_041, delete-the-assertion-not-the-test).

---

The full lens report follows verbatim.


## #5634 grounding: test-suite remediation analysis for `src/specify_cli/core/mission_creation.py`

Lens: reviewer-renata (read-only, pre-spec brownfield point-cut). Branch `issue-5634-mission-creation-degod` @ `2b7ad857f`. No repo file was edited.

### 0. Profile and doctrine loaded

- `spec-kitty agent profile show reviewer-renata`. Directives 001, 024, 030, 032, 041, 051. Tactics: code-review-incremental, reverse-speccing, test-readability-clarity-check, test-scaffolding-as-design-smell, delete-the-assertion-not-the-test.
- `spec-kitty charter context --action review --json`. Bootstrap load, 244 references.
- Applied:
  - **DIRECTIVE_041**: a green test that stays green on a regression gives no coverage. This drives the vacuous-patch findings.
  - **DIRECTIVE_024 Locality**: blast radius of the move.
  - **test-scaffolding-as-design-smell**: the 5-patch "environment stack" is the design smell that the pure-core split should remove.
  - **delete-the-assertion-not-the-test**: no test is retired without a named guard.
  - **reverse-speccing**: the golden matrix is a reverse specification written first.
- Procedure: `packs/internal/procedures/test-suite-quality-assessment.procedure.yaml`.
- Toolguide: `packs/internal/toolguides/test-quality-triage.toolguide.yaml`.
- Asset: `packs/internal/assets/test-quality-scan.py`.
- Scope: the tests that cover `mission_creation.py`, not one domain. Outputs are under the scratchpad (`tq/`) instead of `work/test-quality/`, because this run is read-only.

Artifacts in this scratchpad:

| File | What it holds |
|---|---|
| `count_patches2.py` | AST patch counter that resolves `_CORE_MODULE` f-strings |
| `patch_lines.json` | Every patch site as `file:line` |
| `primary.txt` | The 42 covering files |
| `baseline*.txt` | Run output |
| `perfile.txt` | Per-file runtime |
| `cov.json` | Line and branch coverage |
| `ctxcov` | Per-test coverage contexts |
| `tq/` | Scan output |
| `probeplug.py` | Read-only probe plugin |

### 1. Inventory

- `grep -rln "mission_creation\|create_mission_core" tests` returns **86 files**.
- Many of them only *use* `create_mission_core` as a factory (`tests/_factories/make_mission`, `coord_mission.make_coord_mission`). Those are consumers, not coverage of the module.
- The **primary covering set** is 42 files: every file that patches into the module, plus every `test_mission_creat*` / `test_mission_create*` file, the topology-flag, retention, idempotency and rollback files, and the CLI default-topology matrix. The list is in `primary.txt`.
- Shares of the 42:
  - 461 test functions (AST), 515 collected items once parametrised.
  - About 180 of them actually execute `mission_creation.py` (per-test coverage contexts).
  - **95% line coverage** of `mission_creation.py` and 86% of `cli/commands/agent/mission_create.py`.
- The problem is coupling, not missing coverage.

Runtime class is taken from the markers. Seconds are summed setup+call+teardown, from `--durations=0` on the non-coverage run.

| File | Tests | Class | Wall s | Behaviour family |
|---|---:|---|---:|---|
| core/test_mission_create_protected_single_branch.py | 22 | integration/git | 54.4 | protected mint, commit_to_target, branch exists, CLI checkout-switch output, downstream status/implement |
| cli/.../agent/test_issue_2684_subtask_completion_event_sourced.py | 2 | integration | 40.1 | downstream move-task (incidental create) |
| core/test_mission_creation_decomposition.py | 41 | integration/git | 31.5 (22s is first-worker warm-up) | prior decomposition (FR-026/T051) guard set: input validation, roots, duplicate, meta shape, scaffold commit, coord seed |
| cli/commands/test_selector_resolution.py | 14 | **marked `fast`, actually 25s** | 25.0 | selector; patches `create_mission_core` |
| cli/.../agent/test_mission_create.py | 28 | integration | 22.2 | coord branch mint, idempotent re-run, derived topology via CLI, pr-bound start-branch, resume probe |
| test_specify_topology_flag.py | 7 | git_repo/e2e | 18.9 | `--topology` CLI to consolidation, end to end |
| orchestrator_api/test_specify_plan_tasks_verbs.py | 13 | integration | 17.0 | orchestrator verbs |
| contract/test_mission_id_creation_contract.py | 4 | slow | 16.7 | ULID mint (25 full creates in `test_t004`) |
| integration/test_specify_plan_commit_boundary.py | 13 | integration | 14.4 | commit boundary |
| integration/test_placement_partition_golden_path.py | 11 | integration | 11.5 | placement |
| core/test_mission_create_idempotency_guard.py | 6 | integration | 10.9 | #4033 duplicate guard |
| agent/test_agent_feature.py | 41 | integration | 7.2 | CLI create (patch-heavy) |
| core/test_mission_creation_identity.py | 12 | integration | 6.8 | mission_id, mid8 |
| cli/commands/test_coordination_doctor.py | 20 | integration | 6.5 | doctor (incidental) |
| specify_cli/core/test_feature_creation.py | 22 | integration | 6.0 | programmatic API (patch-heavy) |
| 27 smaller files | ≤5 each | mostly integration | ≤4.6 each | rollback (checkout, scaffold, coord-seed), fan-out, owned charter, unborn HEAD, retention, slug, phases |

- Baseline wall time is **2m13s** under `-n 4 --dist loadfile` without coverage, and 5m49s with `--cov --cov-branch`.
- The slowest single calls are end-to-end tests that create a mission and then run downstream:
  - `test_specify_topology_single_branch_writes_no_coordination_branch` 37.6s
  - `test_status_transition_commits_to_mission_branch_not_target` 33.4s
  - `test_next_step_dual_flag_conflict_fails` 28.5s, marked `fast`

### 2. Monkeypatch targets into `specify_cli.core.mission_creation` (precise AST count)

The method is an AST walk over `setattr` / `patch` / `patch.object` / `patch.multiple` / `delattr`. It resolves:

- string literals;
- `f"{_CORE_MODULE}.X"` with module constants (17 files define `_CORE_MODULE`/`_CORE`);
- object form through `import specify_cli.core.mission_creation as m` or `from specify_cli.core import mission_creation`, including imports inside functions.

**Total: 277 static patch sites, 13 distinct targets, 33 files.**

- 266 use the string form. Only 51 of those are plain literals; 215 use the `_CORE_MODULE` f-string.
- 11 use the object form.
- The issue's figure of **57 is an undercount by about 5x**. It matches a literal-string grep (51 literals plus 6 object-form sites) and misses the dominant `f"{_CORE_MODULE}.X"` idiom.
- Runtime patch applications are higher still, because helper stacks run per test: `_patch_repo_environment` in test_mission_create.py, `_patched_context` in topology and unborn_head, `_patched_mission_creation_context` in identity, and the autouse `_not_a_worktree` in decomposition.

| Target | Sites | Files | Defined where | Move hazard |
|---|---:|---:|---|---|
| `is_worktree_context` | 72 | 24 | imported (`core.paths`) | **silent** |
| `locate_project_root` | 45 | 14 | imported (`core.paths`) | **silent** |
| `is_git_repo` | 44 | 12 | imported (`core.git_ops`) | **silent** |
| `get_current_branch` | 42 | 12 | imported (`core.git_ops`) | **silent** |
| `_commit_feature_file` | 41 | 12 | local | loud if removed; silent if kept as a re-export |
| `ULID` | 11 | 7 | imported (`ulid`) | **silent** |
| `create_mission_core` | 7 | 3 | local (public facade) | none while the facade stays; the CLI imports it lazily at `mission_create.py:647` |
| `preflight_commit` | 5 | 2 | imported (`specify_cli.git`) | **silent** |
| `safe_commit` | 4 | 2 | imported (`specify_cli.git`) | **silent** |
| `_commit_create_scaffold` | 2 | 1 | local | loud or silent, as above |
| `now_utc_iso` | 2 | 2 | imported (`kernel.clock`) | **silent** |
| `_consume_pending_origin_if_present` | 1 | 1 | local | loud or silent, as above |
| `subprocess.run` | 1 | 1 | **global**: it patches `subprocess.run` process-wide | misleading target |

- **226 of the 277 sites (82%) patch names that `mission_creation` imports from elsewhere.**
- These are the silent breakers. When a caller moves into a new module (for example `mission_creation_git.py`) that does its own `from specify_cli.core.git_ops import get_current_branch`, the stale binding in `mission_creation` still exists. `patch()` therefore succeeds and patches nothing, and the test runs real effects instead of failing. A local name that is deleted fails loudly (`AttributeError`). A local name kept as a re-export shim is silent.

There are also **15 direct imports of private symbols** from the module, across about 14 files. They break loudly (`ImportError`) on a move:

- `_mint_protected_single_branch_mission_branch` (2 files)
- `_protected_mint_applies`
- `_validate_create_inputs`
- `_build_create_meta`
- `_Purpose`
- `_plan_orphan_scaffold_removal`
- `_restore_git_state_after_failed_create`
- `_rollback_coordination_surface`
- `_CoordCreateRollbackContext`
- `_path_is_tracked_by_git`
- `KEBAB_CASE_PATTERN`

### 3. Findings (static scan, plus reading the files, plus runtime probes)

The scan ran over 42 files and 461 tests and flagged 144 (`tq/summary.md`). The ranking was:

1. `agent/test_agent_feature.py`: over-mocking 34, interaction-assert 5
2. `specify_cli/core/test_feature_creation.py`: over-mocking 15
3. `test_coordination_doctor.py`
4. `cli/.../agent/test_mission_create.py`: over-mocking 8
5. `test_mission_create_phases.py`: no-assertion 3

`ruff --select PT` reports 22 issues: 13 PT018 composite asserts, 4 PT019, 2 PT011 raises-too-broad, 2 PT017, 1 PT001. All are cosmetic.

Findings:

- **[HIGH]** `tests/specify_cli/core/test_feature_creation.py:35` (`_init_git_repo` runs `git init` with no `-b`) together with `get_current_branch` patched to `"main"` (14 sites).
  - Issue: the patch stack fakes a repo state that does not exist.
  - Proven with `probeplug.py`, which wraps `_create_mission_core_impl` read-only. In about 33 creates across `test_feature_creation.py`, `core/test_mission_creation_identity.py`, `test_mission_creation_fire_once.py` and `test_mission_creation_specify_started.py`, the real HEAD is `master` but `meta.target_branch == "main"`, a branch that does not exist.
  - The same shape outside pytest raises `MissionCreationError: target branch 'main' has no commit` once single_branch is involved. These tests assert on fiction.
  - Recommendation: do not reuse this harness for the golden matrix. Rewrite with `clone_template` (branch `main`) or `git init -b main`, and drop the `get_current_branch` patch (category b).

- **[HIGH]** `locate_project_root` patched at 45 sites in 14 files.
  - Issue: the patch is vacuous almost everywhere. Per-test coverage contexts (`ctxcov`) show both call sites are reached by only 3 tests, all in `tests/agent/test_agent_feature.py` (CLI path, `repo_root=None`):
    - `mission_creation.py:900` (wrapper)
    - `mission_creation.py:1065` (`_resolve_create_roots`)
  - Every other site passes `repo_root` explicitly, so the patched name is never consulted.
  - Recommendation: retire about 42 sites (category c). The "planted break" here is the coverage-context proof that the line never runs under those tests. No covering guard is needed because no behaviour is being guarded.

- **[HIGH]** `is_worktree_context` patched at 72 sites.
  - Issue: this is ambient-cwd coupling. `_resolve_create_roots` reads `Path.cwd()` (line 1058) and checks it at line 1062, and 162 tests reach that check.
  - The patch exists because developers run pytest from `.worktrees/*-lane-*`. `make_mission` already solves this with `allow_worktree_context=True`.
  - Recommendation (category a): make the pure guard take `cwd` as an input. Tests pass `allow_worktree_context=True` or use `monkeypatch.chdir(repo)`.
  - Keep exactly the refusal guards, as behaviour tests against a real `git worktree add` checkout:
    - `test_mission_creation_decomposition.py::test_worktree_context_without_allow_flag_is_refused`
    - `test_feature_creation.py::test_worktree_context_raises`
    - `_factories/test_make_mission_parity.py::test_create_mission_core_worktree_guard_default_still_blocks`

- **[HIGH]** `is_git_repo` patched at 44 sites, always `True` on a real repo.
  - Issue: redundant. The real function already answers `True`.
  - Recommendation: retire (c). The covering guard for the refusal is `tests/core/test_mission_creation_decomposition.py::test_not_a_git_repo_raises`, which uses a real non-git dir and no patch.
  - Re-prove it with a planted break: make `_resolve_create_roots` skip the `is_git_repo` check. That guard must go red.

- **[HIGH]** Architectural gates pin the file and its function names. These fail open on extraction:
  - `tests/architectural/test_no_write_side_rederivation.py:95` lists `core/mission_creation.py` in the `_PRE_WRITE_DIR_ADOPTED_MODULES` scan scope. New adapter or core modules will **not** be scanned unless they are added.
  - The same file at `:1381` holds the census pair `("…/mission_creation.py", "_emit_create_events")`.
  - `tests/architectural/test_mission_resolver_walker_gate.py:21-22` exempts `_list_mission_scaffolds` in this file only.
  - `tests/architectural/test_single_mission_surface_resolver.py:305,704`.
  - Recommendation: each WP that extracts a module adds it to these scopes in the same WP. Precedent: `workflow_cores.py` and `workflow_executor.py` were added for the workflow de-god. Prove each with the gate's own mutation harness.

- **[MEDIUM]** `_commit_feature_file` patched at 41 sites, as a bare MagicMock.
  - Issue: the scaffold commit is skipped entirely, so these tests never observe commit behaviour. The stub exists mainly to dodge the protected-`main` refusal.
  - Recommendation:
    - **b**: create on an unprotected topic branch (the pattern in `test_mission_create_retention.py:31`) and assert real commits.
    - **a**: keep about 6 failure-injection sites (`test_mission_create_checkout_restore.py` ×3, `test_mission_creation_fanout_commit_boundary.py` ×2, `test_mission_id_creation_contract.py`) and point them at the new committer adapter module, or inject a fake committer.

- **[MEDIUM]** `ULID` (11) and `now_utc_iso` (2) are patched for determinism.
  - Issue: `test_mission_creation_decomposition.py:166,179` and `test_mission_create_idempotency_guard.py` sleep 1.1s to avoid a mid8 millisecond collision. `contract/test_mission_id_creation_contract.py::test_t004` runs 25 full creates (16.6s) to prove a library property.
  - Recommendation (a): put identity and clock minting behind a pure core input, for example `build_create_meta(..., mission_id=, created_at=)` with the facade supplying defaults. This kills the sleeps. `test_t004` becomes a seam unit test over the mint plus one end-to-end create.

- **[MEDIUM]** `tests/core/test_mission_create_scaffold_rollback.py`: patching `"specify_cli.core.mission_creation.subprocess.run"` patches the **global** `subprocess.run`.
  - Recommendation: rewrite (b) as fault injection on the adapter.

- **[MEDIUM]** Missing seam coverage. These branches are uncovered by all 42 files, and no test anywhere asserts their messages:
  - The protected-mint **dirty-checkout refusal** (`:571-581`, "uncommitted changes outside this mission's own scaffold").
  - `git checkout -b` failure (`:605-607`).
  - Topology corroboration failure (`:1491-1492`).
  - MissionCreated persisted-payload mismatch (`:1690`).
  - Coordination commit failure (`:1956-1957`).
  - Bootstrap meta-commit skip (`:1821-1822`).
  - Duplicate-scan fail-closed on missing `meta.json` (`:426`).
  - `_prior_mission_is_abandoned` StoreError (`:378-379`).
  - Orphan-scaffold same-prefix neighbour guard (`:668`, the "task-list" vs "task-list-api" case).
  - `_rollback_coordination_surface` early return (`:765`).
  - Every one of these is a decision the pure cores will own. Each needs a seam unit test **before** the move.

- **[MEDIUM]** No cross-product tests.
  - Retention × topology/protected is untested: retention is only tested on the coord default on an unprotected branch.
  - The `commit_to_target` refusal is tested only at core level.
  - no-origin/HEAD fallback (`resolve_primary_branch` falling back to the current branch) is pinned only by mocks in `test_mission_create_default_topology_matrix.py`, which patches `resolve_primary_branch`, plus one real CLI pin in `test_agent_feature.py::test_owned_checkout_with_no_topology_flag_still_defaults_to_single_branch`.
  - Topology derivation lives in `cli/commands/agent/mission_create.py::_resolve_default_topology_phase`, **not** in `mission_creation.py`. The "topology choice" pure core already half-exists there, so do not duplicate it.

- **[LOW]** `cli/.../agent/test_mission_create_phases.py:48,107,133`: three no-assertion tests. They are actually "does not raise" tests, so they are fine. KEEP, optionally with an explicit `is None`.
- **[LOW]** `tests/specify_cli/cli/commands/test_selector_resolution.py` is marked `fast` but takes 25s, which pollutes `make test-fast` timing.
- **[LOW]** `core/test_mission_creation_topology.py:85` asserts `mint.assert_not_called()` on `ensure_coordination_branch`. This is an interaction assert, but it is backed by the observable `"coordination_branch" not in meta`. KEEP.
- **[LOW]** `tests/agent/test_agent_feature.py`: 34 over-mocking flags. Its create section stacks `preflight_commit`, `ULID` and `_commit_feature_file` on top of the environment stack.
  - Recommendation: SPLIT-BY-KIND. Keep the CLI-wiring tests. Move the create assertions to the golden matrix's CLI smoke tests.

### 4. Baseline

Command (no coverage, repo addopts dropped so the plugins are explicit):

```
PWHEADLESS=1 .venv/bin/python -m pytest $(cat primary.txt) -n 4 --dist loadfile -q -p no:cacheprovider --durations=0 -o addopts=""
```

Result: **513 passed, 2 skipped, 0 failed in 126.4s** (2m13s wall).

The same set with `--cov=specify_cli.core.mission_creation --cov=…mission_create --cov-branch` gave 511 passed, 2 skipped and **2 failed**, in 333.7s:

- `tests/specify_cli/core/test_mission_creation_fire_once.py::test_mission_created_fanout_fires_exactly_once`
- `tests/specify_cli/core/test_mission_creation_fire_once.py::test_mission_created_resume_does_not_double_fire`

Both failed with "fan-out got 0", on worker gw3. They pass in isolation, with or without `--cov`, and alongside `test_feature_creation.py`.

- Classification: **not attributable** (there is no diff). It is a pre-existing order-dependent flake: lifecycle fan-out registry or gating state that leaks between files scheduled on the same xdist worker.
- Per the flakiness policy: file it, do not retry-to-green, and do not chase it in #5634.
- It is a real risk for the refactor, though. `_emit_create_events` and the fan-out will move, so record this baseline-red before any WP starts.

### 5. Remediation plan per target

| Target (sites) | Verdict | Action | Est. sites after (old namespace / new) |
|---|---|---|---|
| `is_worktree_context` (72) | **a + b** | The pure guard takes `cwd`. Tests pass `allow_worktree_context=True` or `monkeypatch.chdir`. 3 refusal guards become real-worktree behaviour tests. | 0 / 0 |
| `locate_project_root` (45) | **c** (about 42 dead; coverage-context proof) + **b** for 3 CLI tests (`monkeypatch.chdir(repo)`) | Retire | 0 / 0 |
| `is_git_repo` (44) | **c** | Guard: `test_mission_creation_decomposition.py::test_not_a_git_repo_raises`, re-proved by a planted break | 0 / 0 |
| `get_current_branch` (42) | **b** | Real `main` repos (`clone_template`). Detached-HEAD guard: `test_mission_creation_decomposition.py::test_detached_head_raises` (real `git checkout --detach`) | 0 / 0 |
| `_commit_feature_file` (41) | **b** (about 35, by creating on an unprotected branch) + **a** (about 6 fault injections against the committer adapter) | Rewrite or move | 0 / ~6 |
| `ULID` (11), `now_utc_iso` (2) | **a** | Identity and clock become pure-core inputs. Golden normalises instead of freezing. Parity test freezes via facade kwargs or the new identity module. | 0 / ~2 |
| `preflight_commit` (5), `safe_commit` (4) | **a** | Patch the new git-effects adapter module, or inject a fake | 0 / ~4 |
| `_commit_create_scaffold` (2), `_consume_pending_origin_if_present` (1) | **a** | Patch the new module | 0 / ~3 |
| `subprocess.run` (1) | **b** | Fault-inject the adapter | 0 / ~1 |
| `create_mission_core` (7) | keep | The facade stays; the CLI imports it lazily | 7 / 0 |

Estimated total: **277 sites into `mission_creation` before, about 7 after** (only the public facade). About 16 targeted patches land on the new adapter modules. Net: about 277 to about 23, a reduction of roughly 90%. Retiring is safe only with the named guards re-proved by a planted break, per the procedure.

Process notes:

- Add a shrink-only ratchet: an AST test that counts patch sites into `specify_cli.core.mission_creation` and fails if the count grows. Reuse `count_patches2.py` logic. This keeps the count going down.
- Forbid patching an *imported* name of the new modules. Test through ports instead. This closes the silent-breaker class for good.

### 6. Golden behaviour-preservation matrix (write FIRST, against unchanged code)

**File A: `tests/core/test_mission_creation_golden_matrix.py`** (core level, `create_mission_core` direct, **zero patches**).

Fixture: per cell, `clone_template(tmp_path/"repo")` (hardlinked; branch `main`; has an `origin`), then `provision_test_charter`, commit `.kittify`. Optionally `git checkout -b topic`. These are the factories behind `tests/_factories/coord_mission.py::_init_repo_with_target`. Each cell uses a unique slug so mid8 never collides, and passes `allow_worktree_context=True`.

Axes:

- **Topology**: single_branch, lanes, coord, lanes_with_coord.
- **Target**:
  - protected primary: `main` with no remote, or with `protection.protected_branches` set via `_write_protected_branches`;
  - unprotected `topic`.
- **Flags**:
  - none;
  - `commit_to_target=True`: only valid with single_branch; other topologies are refusal cells;
  - `retain_branches+retain_worktrees`;
  - `pr_bound=True`;
  - `owned_create_root`: minted via `core.owned_mission.resolve_owned_create_root` on a real `git worktree add`.

That gives about 4×2×5 = 40 cells, with invalid ones becoming refusal rows.

Refusal rows (each also asserts that the post-state equals the pre-state, which pins rollback):

- live duplicate (`MissionAlreadyExistsError`)
- mission branch exists (`MissionBranchExistsError`)
- **dirty checkout under protected mint** (currently untested)
- target without commit
- invalid slug
- empty `friendly_name`
- `commit_to_target` without single_branch
- unborn HEAD
- detached HEAD
- worktree context without the allow flag
- owned-root mismatch
- protected re-create (`_refuse_protected_recreate`)

Captured per cell, as a JSON snapshot in `tests/core/golden/mission_create_matrix.json`, regenerated only under `SPEC_KITTY_REGEN_GOLDEN=1` and committed from the **unchanged** base sha:

- `meta.json`, sort-keyed, with normalisation:
  - `mission_id` becomes `<ULID>`, `mid8` becomes `<MID8>` everywhere (slug, dir name, branch names), `created_at` and other ISO timestamps become `<TS>`;
  - absolute paths become relative.
- `git for-each-ref refs/heads` names, normalised.
- `git worktree list --porcelain` paths, relative to the repo.
- HEAD branch after the create, in both the write checkout and the root.
- Commit count added per branch (target, mission branch, coord branch), plus `git show --name-only` of each new commit.
- `status.events.jsonl` `event_type` sequence, and which branch or checkout holds it.
- `git status --porcelain` after the create.
- For refusals:
  - exception class;
  - normalised message;
  - error code (from `_emit_create_core_error_and_exit` / `MissionCreationError` code attribute where present);
  - the pre/post equality check.

**File B: `tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py`** (CLI level; `CliRunner` against `mission_app`; `monkeypatch.chdir(repo)` instead of patching `locate_project_root`). Contents:

- One smoke test per family: success JSON envelope keys and values (normalised) plus exit code, and refusal JSON `error_code` plus exit code.
- The derived-topology cells, because derivation is the CLI's job:
  - on primary with `origin/HEAD` gives coord;
  - on non-primary gives lanes;
  - `--pr-bound` on primary gives coord;
  - **no-origin fallback** (`git remote remove origin`; the primary falls back to the current branch);
  - `--owned-checkout` with no `--topology` gives single_branch.
- About 10 cells, reusing the `_invoke_mission_create_cli` / `_cli_create_args` / `_set_up_bare_remote` helpers from `tests/_factories/coord_mission.py`, minus their `locate_project_root` and `is_worktree_context` patches.

Existing assets to reuse and extend:

- `test_mission_creation_decomposition.py` (`repo` fixture, `_summary`, `_commit_spec`): the closest analogue, since it was the previous decomposition's guard set.
- `tests/git/protected_target_fixtures.py::build_protected_target_repo`.
- `tests/_factories/__init__.py::make_mission` / `provision_test_charter`.
- `test_mission_create_default_topology_matrix.py`: already the pure-core test shape for topology. Extend it rather than duplicate it.
- `test_mission_cli_golden_contract.py`: pins the flag surface, but has no create behaviour.

Runtime estimate:

- About 0.25s per create (decomposition file: 41 tests in about 9s after warm-up).
- File A: about 52 cells ≈ 13–15s serial. Split it into 2–3 files by topology family so `--dist loadfile` spreads it, for about 5s wall.
- File B: about 10 × 0.6s ≈ 6s.
- Expect about 20s of one-time warm-up per xdist worker (first-test setup at about 22s was observed). That cost is shared, not added.

Order of work:

1. Golden A+B, plus the missing-seam unit tests (section 3 MEDIUM list), land first and green on unchanged code. Record the sha.
2. The ratchet test lands.
3. Extraction WPs re-run the golden byte-for-byte. Only then are patches migrated or retired, with the planted-break evidence in each PR.

### Concessions

- Which pure cores and adapters to cut, and their names, is an architect's call (DDD lens). I only constrain them: topology derivation already lives in the CLI module, and every new module must enter the architectural scan scopes.
- I did not open the 44 "incidental consumer" files beyond the grep. They use `create_mission_core` as a factory, and the facade stays, so they are out of the remediation scope unless they patch something; none of them are in the patch table.
- The fire_once flake root cause was not chased (policy).

### Verdict

**Proceed, conditionally.**

- The suite has high line coverage, but 82% of its 277 module patches target imported names. Those patches silently go inert when the code moves.
- About 42 `locate_project_root` patches are already dead.
- About 33 creates run against a faked `main` on a real `master` repo.
- The refactor must not start until three things are in place:
  - the zero-patch golden matrix (core plus CLI) is committed green on the unchanged base;
  - the 10 uncovered decision branches have seam tests;
  - the architectural scan scopes are planned to follow the extracted modules.
- With those in place, migrating from about 277 patch sites to about 23 (about 7 in the old namespace) is realistic and measurable through a shrink-only ratchet.

## Appendix — covering test set (42 files, `primary.txt`)

```
tests/_factories/test_make_mission_parity.py
tests/agent/test_agent_feature.py
tests/agent/test_create_feature_branch_unit.py
tests/contract/test_mission_id_creation_contract.py
tests/coordination/test_create_rollback_ledger_guard.py
tests/core/test_issue_2693_mission_create_clean_scaffold_guard.py
tests/core/test_issue_pending_origin_meta_commit_guard.py
tests/core/test_mission_create_activation_gate.py
tests/core/test_mission_create_checkout_restore.py
tests/core/test_mission_create_coord_seed_rollback.py
tests/core/test_mission_create_coord_status_placement.py
tests/core/test_mission_create_coord_status_seed.py
tests/core/test_mission_create_idempotency_guard.py
tests/core/test_mission_create_protected_single_branch.py
tests/core/test_mission_create_scaffold_rollback.py
tests/core/test_mission_creation_decomposition.py
tests/core/test_mission_creation_fanout_commit_boundary.py
tests/core/test_mission_creation_identity.py
tests/core/test_mission_creation_owned_charter.py
tests/core/test_mission_creation_topology.py
tests/core/test_mission_creation_unborn_head.py
tests/core/test_mission_number_null_schema.py
tests/core/test_slug_validator_unit.py
tests/integration/test_issue_4863_merge_abort_no_state.py
tests/integration/test_placement_partition_golden_path.py
tests/integration/test_specify_plan_commit_boundary.py
tests/specify_cli/cli/commands/agent/test_coord_topology_no_strand.py
tests/specify_cli/cli/commands/agent/test_issue_2684_subtask_completion_event_sourced.py
tests/specify_cli/cli/commands/agent/test_mission_create.py
tests/specify_cli/cli/commands/agent/test_mission_create_default_topology_matrix.py
tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py
tests/specify_cli/cli/commands/agent/test_mission_create_phases.py
tests/specify_cli/cli/commands/review/test_issue_matrix_partition.py
tests/specify_cli/cli/commands/test_coordination_doctor.py
tests/specify_cli/cli/commands/test_selector_resolution.py
tests/specify_cli/core/test_feature_creation.py
tests/specify_cli/core/test_mission_creation_fire_once.py
tests/specify_cli/core/test_mission_creation_placement.py
tests/specify_cli/core/test_mission_creation_specify_started.py
tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py
tests/specify_cli/test_mission_create_retention.py
tests/specify_cli/test_specify_topology_flag.py
```

The grounding AST scanners are preserved as `research/tools/scan_patches2.py.txt` (gates lens) and `research/tools/count_patches2.py.txt` (test lens). They are saved as `.txt` so the repository-wide lint and format gates do not pick them up. WP04 turns them into the committed `tests/_support/patch_census.py`.
