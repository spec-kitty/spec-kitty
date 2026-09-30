---
work_package_id: WP04
title: Placement seam and mission-runtime resolution
dependencies:
- WP02
requirement_refs:
- FR-006
- FR-007
- FR-011
- FR-023
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-owned-checkout-lifecycle-authority-01M3M2ZB
base_commit: 42cf3a08378e484665f9255ce5e763cfa8abb466
created_at: '2026-09-28T20:21:54.077415+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
phase: Phase 2 - Seams
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/
create_intent:
- tests/mission_runtime/test_placement_seam_owned.py
- tests/mission_runtime/test_resolution_owned.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/mission_runtime/resolution.py
- src/mission_runtime/context.py
- src/specify_cli/task_utils/support.py
- tests/mission_runtime/test_placement_seam_owned.py
- tests/mission_runtime/test_resolution_owned.py
- tests/mission_runtime/test_owned_single_branch_ssot.py
- tests/mission_runtime/test_coord_read_seam_callers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Placement seam and mission-runtime resolution

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Close the fall-back to the repository root checkout **at its source**, in the mission-runtime resolution layer (research R-04):

1. `placement_seam(repo_root, slug, *, owned=...)` / `PlacementSeam.owned`: with a fact, every PRIMARY-partition kind reads `owned.mission_dir` and never calls `get_main_repo_root`.
2. `mission_context_for`, `resolve_action_context` and the private `_resolve_wp_bearing_fields` take the fact. The target branch and topology come from the fact.
3. With a fact, the WP-bearing fields resolve the WP file from the owned checkout. A WP absent from the owned checkout is `WORK_PACKAGE_UNRESOLVED`, naming the owned mission directory, even when the repository root checkout has a stale copy that contains it (FR-006, FR-007; spec US2-AS2/AS3).
4. `_require_owned_single_branch` is deleted. Topology is decided once, at minting (FR-023, research R-16).
5. `locate_work_package(..., owned=...)` reads from the owned checkout.
6. The remaining bare owned-root parameters in `resolution.py` are converted, or explicitly recorded as transitional (see T021).

**Staging (plan §Staging Strategy).** `placement_seam`, `mission_context_for`, `resolve_action_context` and `locate_work_package` are four of the six shared **dual-keyword seams**: they accept `owned=` **and** the legacy `effective_root=` until WP18 deletes the legacy keyword. Transitional surfaces are the six shared seams plus every other function marked TRANSITIONAL(WP18): every legacy parameter or field carries `# TRANSITIONAL(WP18): <reason>`, and WP18 deletes exactly what `grep -rn "TRANSITIONAL(WP18)" src tests` finds. Reviewers must not reject a marked legacy keyword in this WP.

**Done means**:
- the red-first tests of T016 went red on base and are green now;
- `tests/mission_runtime/` is green;
- the listed owned regression files are green unchanged (FR-022);
- ruff, format and mypy `--strict` are clean on the touched files;
- complexity is ≤ 15 (target ≤ 11 for touched functions), and `make test-fast` is green.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP04 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **17** markers (amended in review cycle 2: the private helpers keep a self-contained owned branch plus a separate marked legacy branch; WP18 deletes each marked parameter **and** its whole legacy-arm branch body): `src/mission_runtime/resolution.py` 16 (`_refuse_both`, `read_dir_for`, `_resolve_mission_slug`, `_resolve_wp_bearing_fields`, `_resolve_coordination_branch`, `_resolve_topology`, `mission_context_for`, `_resolve_mission_id`, `_resolve_status_surface_dir`, `_assemble_core_fragments`, `resolve_placement_only`, `PlacementSeam.effective_root`, `declared_read_surface`, `resolve_artifact_surface`, `placement_seam(effective_root=)`, `resolve_action_context`) and `src/specify_cli/task_utils/support.py` 1 (`locate_work_package`). Check with `grep -c "TRANSITIONAL(WP18)"` per file.
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

- `spec.md`: US2 (all ACs), §Edge Cases ("Stale copy", "Path aliases"), FR-006, FR-007, FR-011, FR-023.
- `plan.md`: §IC-02, §Staging Strategy, §Test Layout.
- `research.md`: R-04 (the placement fall-back is the root cause of O3/O4/O5), R-12 (the stale-copy channel: detection lives in the CLI helper of WP08, **not here**), R-16 (topology single authority).
- `contracts/owned-checkout-carrier.md` §7: consumers read only under `owned.owned_root` and never call `get_main_repo_root`.
- `occurrence_map.yaml`: `code_symbols` is `rename`; `serialized_keys` is `do_not_change` (the `MissionExecutionContext` payload keys such as `wp_file`, `workspace_path` and `resolution_kind` keep their names).

**Current code (HEAD `df1588860`)**:
- `src/mission_runtime/resolution.py`:
  - `read_dir_for` `:239`;
  - `_resolve_mission_slug` `:472-556`: it uses `effective_root or repo_root` at `:531-534`;
  - `_resolve_wp_bearing_fields` `:682-739`: it calls `locate_work_package(repo_root, …)` at `:706` and `resolve_workspace_for_wp(repo_root, …)` at `:718`, both **without** the owned root. **This is the O3/O4 defect.**
  - `mission_context_for` `:1040-1160`: the owned fold is at `:1094`;
  - `_assemble_core_fragments` `:1377-1484`: fold at `:1428`;
  - `_require_owned_single_branch` `:1505-1519`, called at `:1596` and `:2361`;
  - `resolve_placement_only` `:1522`;
  - `PlacementSeam` `:1946-2051`, with its `effective_root` field at `:1981`;
  - `declared_read_surface` `:2125`;
  - `resolve_artifact_surface` `:2320`: its owned arm at `:2359-2362` stamps `TopologySurface.PRIMARY` unconditionally;
  - `placement_seam` `:2491-2504`;
  - `resolve_action_context` `:2507-2656`: the target-branch fork is at `:2561-2573`, `_resolve_wp_bearing_fields` is called at `:2643`.
- `src/specify_cli/task_utils/support.py:563-623`: `locate_work_package(..., effective_root=)`. It folds `get_main_repo_root(repo_root)` at `:585`, then splats `effective_root_kwargs` at `:587`.
- `src/mission_runtime/context.py`: no `effective_root` today. The `is_single_branch` docstring (`:107-126`) cites the owned-placement arms that T019 removes.

**External callers that still pass `effective_root=`** to functions in `resolution.py`. They are converted later, so these functions must keep accepting it:
- `resolve_placement_only`: `coordination/commit_router.py:301` (WP07), `coordination/status_transition.py:974` (WP07), `agent/tasks_shared.py` (WP16), `coordination/transaction.py` (WP06);
- `resolve_artifact_surface`: `acceptance/execution_context.py:268,338` (WP15), `migration/runtime_state_cutover.py:230` (WP17), `cli/commands/accept.py` (WP14), `missions/_read_path_resolver.py` (WP17);
- `declared_read_surface`: `acceptance/execution_context.py` (WP15);
- `read_dir_for`: `tasks/issue_matrix.py` (WP17).

**These four also need the dual keyword until WP18.** They are "other functions marked TRANSITIONAL(WP18)" in the plan's convention: mark each legacy parameter `# TRANSITIONAL(WP18): <reason>` so WP18's grep finds them.

**Constraints**:
- **Layer rule.** `resolution.py` imports `OwnedCheckout` only under `TYPE_CHECKING`, or lazily from `mission_runtime.owned_checkout` (it is intra-package, so MR-1/MR-2 do not apply). WP01's `owned_checkout.py` imports `ActionContextError` from `resolution.py`, so a module-level import back would be a cycle.
- **No new git calls** on the owned arm (NFR-002: "0 additional per-read git subprocess calls").
- **Campsite first.** The touched functions in `resolution.py` and `support.py` measure ≤ 8 today (`.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=8' …` flags only `resolve_placement_only` at 9 and `_resolve_review_wp_id` at 9). No pre-extraction is required. **Measure again after each subtask** and extract an `_owned_*` helper whenever a touched function would exceed 11.
- **Terminology.** New docstrings say "owned checkout" and "repository root checkout". Existing local names like `primary_root` may stay (they are not in G4/G5's banned set); do not introduce new ones.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Lane**: assigned in `lanes.json` by `finalize-tasks` (not yet generated). Depends on WP02; use `spec-kitty implement WP04`.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T016 – Red-first seam tests: owned WP fields, missing WP scoped to P, stale copy

- **Purpose**: Reproduce O3 and O4 through the **pre-existing** entry point `resolve_action_context(..., effective_root=P)` before any fix (C-007). This proves the defect lives in `_resolve_wp_bearing_fields`, not only in the CLI.
- **Steps**:
  1. Create `tests/mission_runtime/test_resolution_owned.py` (`pytestmark = [pytest.mark.git_repo]`). Add a local builder `_owned_repo(tmp_path, *, stale_root_wps=None)`. The integration fixtures of WP02 live in `tests/integration/conftest.py` and are **not** reachable from `tests/mission_runtime/`, so build locally. Follow the shape of `tests/integration/test_explicit_checkout_commands.py:52-100`:
     - R: `git init` plus a seed commit;
     - P: `git worktree add -b codex/owned`;
     - in P: a single_branch mission `owned-01M1A900` (`meta.json` with `mission_id`, `target_branch: codex/owned`), `tasks/WP01-a.md` and `tasks/WP02-b.md` with `execution_mode: code_change` frontmatter; committed in P.

     The optional stale copy writes the same mission into `R/kitty-specs/owned-01M1A900` with WP01..WP05 and commits it in R.
  2. **Isolate the WP04 surface from the WP05 surface.** Monkeypatch `specify_cli.workspace.context.resolve_workspace_for_wp` (it is imported lazily inside `resolve_action_context`, `resolution.py:2544`, so the module-attribute patch is observed) with a recording stub. The stub returns an object with `lane_id=None`, `branch_name=None`, `execution_mode="code_change"`, `resolution_kind="stub"`, `worktree_path=P`. WP05 replaces this stub with the real owned arm.
  3. Red tests (commit them **before** T018/T020, and paste the failing assertion lines into the Activity Log):
     - `test_owned_wp_file_under_owned_checkout` (O3): `resolve_action_context(R, action="implement", feature=slug, wp_id="WP01", effective_root=P).wp_file` is under P. On base it fails with "meta.json not found for mission … at R/…" (an R path), so the test is red. Assert on the red commit's observed failure, not on a guessed message.
     - `test_stale_root_copy_never_wins_wp_file` (O4): with the stale copy, `wp_file` is under P, never under R. On base it is R's copy, so the test is red.
     - `test_missing_wp_scoped_to_owned_checkout` (US2-AS2): with the stale copy, `wp_id="WP05"` (present only in R) raises `ActionContextError` with `code == "WORK_PACKAGE_UNRESOLVED"`, and `str(R)` is not in the message while P's mission dir (or `kitty-specs/<slug>/tasks` under P) is. On base it returns R's WP05, so the test is red.
  4. After T017/T018 land, add `owned=` twins of the three tests. They mint the fact through `specify_cli.core.owned_mission.resolve_owned_mission(R, P, slug)`, the real minter, not `_mint`: this proves the seam accepts what the minter produces.
  5. Add mission-level ratchets (green on base; they must stay green): `action="tasks_outline"` with a stale copy gives `feature_dir` under P, both with `effective_root=P` and with `owned=`.
  6. The recording stub, shared by the tests in this file. It stays in this file permanently: WP05 cannot edit this WP's test files, and WP05 proves the real owned workspace leg end to end in `tests/specify_cli/workspace/test_owned_workspace_resolution.py`.
     ```python
     @pytest.fixture
     def workspace_stub(monkeypatch):
         calls = []
         def _stub(repo_root, mission_slug, wp_id, **kwargs):
             calls.append((repo_root, mission_slug, wp_id, kwargs))
             return SimpleNamespace(lane_id=None, branch_name=None, execution_mode="code_change",
                                    resolution_kind="stub", worktree_path=repo_root)
         monkeypatch.setattr("specify_cli.workspace.context.resolve_workspace_for_wp", _stub)
         return calls
     ```
     Assert `len(workspace_stub) == 1` in every WP-bearing test. The `workspace_path` value from the stub is **not** asserted in this WP.
- **Commit sequence**: (1) the builder plus the three red tests (legacy keyword), red; (2) T018/T020 fix commits turn them green; (3) the `owned=` twins, added with T017/T018.
- **Files**: `tests/mission_runtime/test_resolution_owned.py` (new).
- **Parallel?**: No. It comes first.
- **Validation checklist**:
  - [ ] The red run is recorded with test ids and failure reasons.
  - [ ] Non-vacuity: every test asserts both "path under P" **and** "no path under R" (use `Path.is_relative_to`).
  - [ ] The stub records that `_resolve_wp_bearing_fields` called it. This proves the workspace leg is exercised, not skipped.
- **Edge cases**:
  - A symlinked P (`link -> P`): owned identity is canonical (spec §Edge Cases). Add one `owned=` case minted through a symlink and assert that `wp_file` resolves under the real P.
  - Handles: parametrise the `owned=` happy path over slug, mid8 and mission id (the fact carries the canonical slug).

### Subtask T017 – `placement_seam(owned=)` / `PlacementSeam.owned` (dual keyword)

- **Purpose**: Give the one placement authority an owned arm that cannot fold to the repository root checkout (R-04, contract §7).
- **Steps**:
  1. Create `tests/mission_runtime/test_placement_seam_owned.py`:
     - `unit` + `fast` tests on plain `tmp_path` directories (no git): mint through `OwnedCheckout._mint`, and monkeypatch `specify_cli.core.paths.get_main_repo_root` **and** `subprocess.run` to raise. For every `MissionArtifactKind` in the PRIMARY partition, `placement_seam(R, slug, owned=fact).read_dir(kind)` equals `fact.mission_dir`. Assert that the patched functions were never called.
     - `git_repo` tests for the COORD-partition kinds on a `lanes_with_coord` fact (see T019).
     - A ratchet: `placement_seam(R, slug, effective_root=P)` still returns P's dir (legacy keyword).
     - Passing both keywords raises `TypeError`.
  2. Change `PlacementSeam` (`resolution.py:1946`): add `owned: OwnedCheckout | None = None`, and keep `effective_root: Path | None = None` with a comment `# TRANSITIONAL(WP18): legacy field for unconverted callers`. In `__post_init__`, refuse both being set.
  3. `write_target` / `read_dir` (`:1983-2051`) forward `owned=self.owned` (and the legacy `effective_root`) to `resolve_placement_only` / `resolve_artifact_surface`, which gain the same dual keyword (see the External callers list).
  4. `placement_seam(repo_root, mission_slug, *, owned=None, effective_root=None)` (`:2491`) keeps the P-1 partition assertion.
  5. Shape of the dual keyword (use the same pattern for all dual-keyword functions in this WP, so WP18 can delete them mechanically):
     ```python
     def placement_seam(
         repo_root: Path,
         mission_slug: str,
         *,
         owned: OwnedCheckout | None = None,
         effective_root: Path | None = None,  # TRANSITIONAL(WP18): legacy keyword for unconverted callers
     ) -> PlacementSeam:
         _refuse_both(owned, effective_root)
         assert_partition_invariant()
         return PlacementSeam(repo_root=repo_root, mission_slug=mission_slug, owned=owned, effective_root=effective_root)
     ```
     `_refuse_both` is one private helper that raises `TypeError("pass owned= or the transitional effective_root=, not both")`. Every dual-keyword function calls it, so the rule is stated once.
  6. `RETROSPECTIVE` still routes to `resolve_retrospective_home(self.repo_root, …)` (`:2037-2045`). With a fact, pass `owned.owned_root` as the root. Verify `specify_cli/retrospective/writer.py` resolves the retrospective home under that root without a `get_main_repo_root` fold. If it folds, record it as a finding for WP17 (do not edit `writer.py`; it is not in this WP's files).
- **Files**: `src/mission_runtime/resolution.py`, `tests/mission_runtime/test_placement_seam_owned.py` (new).
- **Validation checklist**:
  - [ ] `pytest tests/mission_runtime/test_placement_seam_owned.py tests/mission_runtime/test_placement_seam.py tests/mission_runtime/test_resolve_placement_only.py -q` is green.
  - [ ] The zero-git and zero-`get_main_repo_root` assertions pass for the owned arm.
- **Edge cases**:
  - `PlacementSeam` is frozen and public (`__all__`). Adding a field with a default is backward compatible for keyword construction. Grep for positional `PlacementSeam(` constructions (`grep -rn "PlacementSeam(" src tests`) and keep them working.
  - A fact for mission X used with `mission_slug` Y: refuse with `ActionContextError("FEATURE_CONTEXT_UNRESOLVED", …)` naming both slugs; never silently use either. Compare against `owned.mission_slug` after canonicalising the handle (mid8 or mission id handles canonicalise to the slug).

### Subtask T018 – `mission_context_for` / `resolve_action_context` / `_resolve_wp_bearing_fields` take the fact

- **Purpose**: Carry the fact through mission-context and action-context resolution, including the WP-bearing fields that caused O3/O4. The target branch comes from the fact (plan §IC-02).
- **Steps**:
  1. `mission_context_for(repo_root, mission_handle, topology=None, *, resolver=None, owned=None, effective_root=None)` (`:1040`). With a fact:
     - use `owned.mission_dir` as the PRIMARY read dir;
     - use `owned.target_branch`;
     - use `owned.topology` unless the caller passed `topology`, and if both are given and differ, raise `ActionContextError("OWNED_TOPOLOGY_UNSUPPORTED", …)`;
     - skip the `candidate_feature_dir_for_mission` handle walk (`:1095-1100`), since the fact already resolved the handle.

     Keep the legacy `effective_root` arm byte-identical. `tests/mission_runtime/test_owned_single_branch_ssot.py::test_mission_context_for_owned_arm_is_repo_root_invariant` (`:158`) pins that `repo_root` is vestigial on the owned arm. Extend that pin to `owned=`.
  2. `resolve_action_context(..., owned=None, effective_root=None)` (`:2507`):
     - `_resolve_mission_slug` receives the fact. With a fact, return `(owned.mission_slug, owned.mission_dir)` after checking that the requested `feature` handle canonicalises to `owned.mission_slug`;
     - the target-branch fork (`:2561-2573`) uses `owned.target_branch`;
     - `_resolve_topology` is skipped in favour of `owned.topology`;
     - `_assemble_core_fragments` and `_resolve_wp_bearing_fields` receive `owned`.
  3. `_resolve_wp_bearing_fields(..., owned: OwnedCheckout | None)`:
     - call `locate_work_package(repo_root, mission_slug, normalized_wp_id, owned=owned)` (T020);
     - `_resolve_wp_id(action, feature_dir, wp_id)` already reads `feature_dir`, which is `owned.mission_dir` on the owned arm;
     - on the legacy arm, pass `effective_root=` to `locate_work_package` so legacy callers (`agent/context.py:171`) also stop folding. This is what turns the T016 legacy-keyword red tests green.
  4. **Do not** change the call `resolve_workspace_for_wp(repo_root, mission_slug, normalized_wp_id)` (`:718`) in this WP: `resolve_workspace_for_wp` gains `owned=` only in WP05. WP05 adds `owned=owned` to that one call as a declared one-line out-of-map edit in this file (it is recorded in WP05's prompt). Leave a normal code comment there that says why the fact is not forwarded yet. No `TODO`/`FIXME` tokens (repository lint).
  5. `WORK_PACKAGE_UNRESOLVED` message: with a fact, name `owned.mission_dir / "tasks"`. The message comes from `locate_work_package`'s `TaskCliError` (`support.py:599,620`), so make sure that message names the resolved owned tasks dir.
- **Files**: `src/mission_runtime/resolution.py`.
- **Validation checklist**:
  - [ ] T016's three legacy-keyword tests and their `owned=` twins are green.
  - [ ] `pytest tests/mission_runtime/test_resolution_target_branch.py tests/mission_runtime/test_resolve_action_context_feature_dir.py tests/mission_runtime/test_consolidated_resolution.py tests/mission_runtime/test_resolution_typed_errors.py -q` is green.
  - [ ] The complexity of `resolve_action_context` and `mission_context_for` is ≤ 11 after the change. Extract `_owned_action_identity(owned, feature)` and `_owned_mission_context(owned, topology)` if needed.
- **Edge cases**:
  - Mission-level actions go through `resolve_context_for_mission` (`:2596-2608`). The fact's mission dir must reach `feature_dir=str(feature_dir)`. It does if `_resolve_mission_slug` returns `owned.mission_dir`.
  - `cwd` stays unused (as `# noqa: ARG001` notes at `:476-477`). Do not start using cwd; the fact is the authority.
  - `resolver` injection: with a fact, the resolver is not consulted for the handle walk. Assert this with a `FakeMissionResolver` that raises when called (`tests/mission_runtime/test_builder_fs_free_identity.py` shows how the fake is built and injected).

### Subtask T019 – Delete `_require_owned_single_branch`; topology from the fact

- **Purpose**: Topology has exactly one authority: the minter's `allowed_topologies` (WP02). The placement-layer refusal (`resolution.py:1505-1519`, used at `:1596` and `:2361`) is a second topology authority, and it would refuse `next`'s owned coordination-topology missions once they carry a fact (FR-023, research R-16, decision `01M3M4GM…`).
- **Steps**:
  1. **Red first**, in `tests/mission_runtime/test_placement_seam_owned.py` (`git_repo`): build a `lanes_with_coord` owned mission (with `coordination_branch`) and mint through `resolve_owned_mission(..., allowed_topologies=NEXT_OWNED_TOPOLOGIES)`. Assert that `placement_seam(R, slug, owned=fact).write_target(MissionArtifactKind.SPEC)` returns a `CommitTarget` whose `ref` is the target branch. On base the code path refuses with `OWNED_TOPOLOGY_UNSUPPORTED`, so the test is red. (Commit it with T017's keyword in place; on base, the equivalent `effective_root=` call is the red reproduction.)
  2. Delete `_require_owned_single_branch` and both call sites.
  3. **Fix the surface stamp**: the owned arm of `resolve_artifact_surface` (`:2359-2362`) returns `TopologySurface.PRIMARY` for every kind. For a coordination-routing fact, a COORD-partition kind must be stamped with its real home. Derive the stamp from `artifact_home_for(kind, …).read_surface` (the same helper `mission_context_for` uses at `:1144-1148`), never from a new topology comparison. Add a test that a `lanes_with_coord` fact stamps `STATUS_STATE` as COORD and `SPEC` as PRIMARY.
  4. Update `src/mission_runtime/context.py::is_single_branch`'s docstring (`:107-126`): it is no longer the placement arms' refusal predicate. The minter uses the allowed-set check (WP02).
  5. Rewrite the pinned tests in `tests/mission_runtime/test_owned_single_branch_ssot.py`:
     - `test_placement_owned_arm_refuses_non_single_branch` (`:111`) and `test_artifact_surface_owned_arm_refuses_identically` (`:128`) pin the deleted guard. Replace them with tests pinning the **new** contract: the placement layer does not refuse by topology, and a lifecycle fact cannot be minted for a non-single_branch mission (call `resolve_owned_mission` with the default allowed set and assert `OWNED_TOPOLOGY_UNSUPPORTED`). Keep `test_is_single_branch_predicate` (`:101`).
  6. Behaviour table after the change (put it in the `resolve_artifact_surface` docstring, and assert each row in `test_placement_seam_owned.py`):

     | Fact topology | Kind partition | `read_dir` | `surface_kind` stamp |
     |---|---|---|---|
     | `single_branch` | PRIMARY | `owned.mission_dir` | PRIMARY |
     | `single_branch` | COORD-partition kind | `owned.mission_dir` (AH-2 affirmative home) | PRIMARY |
     | `lanes_with_coord` / `coord` | PRIMARY | `owned.mission_dir` | PRIMARY |
     | `lanes_with_coord` / `coord` | COORD-partition kind | the coordination read dir from `_assemble_core_fragments` | COORD |

     If the fourth row cannot be computed without git (the coordination worktree probe), that is acceptable **only** for coordination topologies, which only `next` mints. Record the git-call count for that row in the Activity Log; NFR-002's zero-extra-calls budget applies to the owned **status** reads of single_branch missions.
  7. **Owned test re-expression** (this WP owns the file): `tests/mission_runtime/test_coord_read_seam_callers.py::test_agent_tasks_ports_feature_write_dir_fails_loud_sanely` (`:234-270`) asserts `OWNED_TOPOLOGY_UNSUPPORTED` from exactly this guard, through `RealCoordCommitRouter.feature_write_dir(MissionHandle(..., effective_root=repo))`. Re-express it so it asserts the new contract: a coordination-topology mission reached through the legacy owned leg fails loud with a **typed** coordination error (for example `CoordinationWorktreeUnmaterialized` or `ActionContextError`), and never silently returns the repository-root dir. First characterise what the arm now does. If it silently returns a PRIMARY path for a COORD kind, stop and escalate: that would be a regression. Rationale line for the commit body: "WP04 deletes the placement-layer topology guard (R-16); this pin asserted that guard."
- **Files**: `src/mission_runtime/resolution.py`, `src/mission_runtime/context.py`, `tests/mission_runtime/test_owned_single_branch_ssot.py`, `tests/mission_runtime/test_placement_seam_owned.py`, `tests/mission_runtime/test_coord_read_seam_callers.py`.
- **Validation checklist**:
  - [ ] `grep -n "_require_owned_single_branch" -r src tests` finds no hits.
  - [ ] `pytest tests/mission_runtime/test_owned_single_branch_ssot.py tests/mission_runtime/test_coord_read_seam_callers.py tests/mission_runtime/test_artifact_surface_backfilled_primary.py tests/mission_runtime/test_status_surface_dir_deleted_arm.py -q` is green.
  - [ ] `pytest tests/integration/test_explicit_checkout_commands.py -k topology -q` is green: the lifecycle commands still refuse non-single_branch, now at the minter (`test_explicit_checkout_commands.py:222,242`).
- **Edge cases**:
  - The FR-023 paired proof spans two layers. The placement layer **accepts** a coordination-topology fact (this subtask), and the minter **refuses** a coordination-topology mission for lifecycle commands (WP02). Reference WP02's test by name in the new `test_owned_single_branch_ssot.py` docstring, so a reader sees both halves.
  - Legacy `effective_root=` callers with a coordination mission (today only `next`, via `next_cmd.py:176`) now pass placement. Run `tests/next/test_runtime_bridge_unit.py`, `tests/specify_cli/next/test_next_invocation_lifecycle_seam.py` and `tests/runtime/test_artifact_presence_placement.py` and record any change in behaviour. The nightly `tests/e2e/test_worktree_owned_root_concurrency.py:405-431` relies on owned coordination-topology `next`; do not run it locally (it is `e2e`), but reason about it in the Activity Log.

### Subtask T020 – `locate_work_package(owned=)` (dual keyword)

- **Purpose**: WP lookup must read from the owned checkout (FR-006), and the status projection for the WP must come from the owned mission's status log.
- **Steps**:
  1. **Red first** in `tests/mission_runtime/test_resolution_owned.py`: `locate_work_package(R, slug, "WP01", effective_root=P)` with a stale copy in R returns a path under P. This is **already green on base** (`support.py:585-595` threads it), so it is a ratchet. The red case is `test_locate_owned_missing_wp_names_owned_dir`: WP05 exists only in R, so `TaskCliError` must name P's tasks dir. On base the message is `kitty-specs/<slug>/tasks` (`support.py:620`) without the root; make it name the resolved owned tasks root, which is red on base.
  2. Change the signature to `locate_work_package(repo_root, feature, wp_id, *, owned: OwnedCheckout | None = None, effective_root: Path | None = None)`, refusing both. With a fact:
     - `feature_path = owned.mission_dir`;
     - `status_dir = placement_seam(repo_root, feature, owned=owned).read_dir(STATUS_STATE)`;
     - no `get_main_repo_root` call.
  3. Keep the `effective_root_kwargs` import (`support.py:15`) only as long as the legacy arm uses it. WP18 deletes both.
  4. Target shape of the body (fact arm first, legacy arm unchanged):
     ```python
     _refuse_both(owned, effective_root)
     if owned is not None:
         placement = placement_seam(repo_root, feature, owned=owned)
         feature_path = owned.mission_dir
         status_dir = placement.read_dir(MissionArtifactKind.STATUS_STATE)
         display_root = owned.owned_root
     else:
         main_root = get_main_repo_root(repo_root)
         ...  # today's lines :585-595, unchanged
         display_root = repo_root
     ```
     Guard `feature` against the fact: if `feature` canonicalises to a different slug than `owned.mission_slug`, raise `TaskCliError` naming both. Callers pass the slug, mid8 or mission id, so compare canonical forms.
  5. The error message for a missing WP names `tasks_root` (the resolved directory) on both arms. Check `tests/specify_cli/cli/commands/agent/test_tasks.py` for message-text assertions and keep them passing: search for `"not found under kitty-specs/"` in `tests/`. If a test pins the old text, that is a `user_facing_strings: rename_if_user_visible` change. Update only tests in this WP's files; for any other pinned text, keep the old substring and append the resolved root.
- **Files**: `src/specify_cli/task_utils/support.py`, `tests/mission_runtime/test_resolution_owned.py`.
- **Parallel?**: Yes with T017 once the fact type is available.
- **Validation checklist**:
  - [ ] `pytest tests/specify_cli/cli/commands/agent/test_tasks.py tests/specify_cli/cli/commands/test_tasks_move_task_cwd.py tests/specify_cli/test_read_seam_migration_core.py tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py -q` is green.
  - [ ] `tests/architectural/test_cold_import_status_boundary.py` is green (`support.py` is on the cold path; keep the new imports function-local).
- **Edge cases**:
  - A duplicate WP-file error lists `path.relative_to(repo_root)` (`support.py:622`). On the owned arm the paths are under P, not R, so use `relative_to(owned.owned_root)`, or `relative_to` would raise `ValueError`.

### Subtask T021 – Convert the remaining bare owned roots in `resolution.py` and `mission_runtime/context.py`

- **Purpose**: Leave `resolution.py` with one internal representation of "owned", so WP18's deletion is mechanical (research R-03: 14 of all bare owned-root parameters (census in plan Scale/Scope) live in `resolution.py`).
- **Steps**:
  1. Run WP01's scanner on the two files (a throwaway local script, not a committed test) to list every G4/G5 hit in `resolution.py` and `context.py`:
     ```bash
     .venv/bin/python - <<'EOF'
     from pathlib import Path
     from tests.architectural import _owned_checkout_scan as s
     from tests.architectural._ast_scan import parse_file
     for rel in ("src/mission_runtime/resolution.py", "src/mission_runtime/context.py"):
         tree = parse_file(Path(rel))
         for o in s.effective_root_identifiers(tree, rel) + s.bare_owned_root_paths(tree, rel):
             print(o)
     EOF
     ```
  2. Classify each hit into a table in the Activity Log with the columns *function*, *reachable from a legacy external caller? (y/n)* and *action*:
     - **not reachable from any legacy caller** (only called from the converted seams): convert fully to `owned: OwnedCheckout | None`, with no legacy parameter;
     - **reachable from a legacy caller** (the dual-keyword public functions plus the private helpers they feed): keep the legacy parameter, but funnel both through **one** private normaliser, for example `_owned_read_root(owned, legacy_root) -> Path | None`, used at the two existing fold points (`:1094` and `:1428`). The owned-vs-legacy fork then exists once.
  3. `src/mission_runtime/context.py` has **no** `effective_root` today (verified). Expect zero hits. The only change there is T019's docstring. If the scanner finds something, convert it.
  4. Mark every legacy parameter or field you keep with `# TRANSITIONAL(WP18): <reason>` on its declaring line (that grep is WP18's inventory). Do not name the gate rule inside production code.
  5. Expected shape of the Activity Log table (fill in every scanner hit; these rows are examples, not the full list):

     | Function | Legacy caller reaches it? | Action |
     |---|---|---|
     | `placement_seam` / `PlacementSeam` | yes (many) | dual keyword |
     | `resolve_placement_only` | yes (`commit_router.py:301`) | dual keyword |
     | `_resolve_wp_bearing_fields` | only via `resolve_action_context` | `owned` plus the normaliser |
     | `_resolve_status_surface_dir` | yes (through `mission_context_for`) | normaliser |
     | `read_dir_for` | yes (`tasks/issue_matrix.py`) | positional legacy plus keyword `owned` |
- **Commit sequence**: one commit per converted function group (seams, private helpers, normaliser), each with `tests/mission_runtime` green, so a reviewer can bisect a regression to a group.
- **Files**: `src/mission_runtime/resolution.py`, `src/mission_runtime/context.py`.
- **Validation checklist**:
  - [ ] The Activity Log table covers every hit the scanner reported.
  - [ ] `mypy --strict src/mission_runtime/resolution.py src/mission_runtime/context.py` is clean.
  - [ ] No behaviour change on the legacy arm: `pytest tests/mission_runtime -q` is fully green.
- **Edge cases**:
  - `read_dir_for(effective_root, primary_root, …)` (`:239`) takes the owned root **positionally**. Its external caller in `tasks/issue_matrix.py` passes it positionally too. Keep the positional shape, and add the keyword-only `owned=`.

## Test Strategy

**Red-first map** (C-007):

| Requirement | Red-first test (committed before the fix) | Entry point | Non-vacuity |
|---|---|---|---|
| FR-006 | `test_owned_wp_file_under_owned_checkout` | `resolve_action_context(effective_root=P)` (pre-existing) | asserts under P **and** not under R; the stub proves the WP leg ran |
| FR-007 | `test_stale_root_copy_never_wins_wp_file`, `test_missing_wp_scoped_to_owned_checkout` | same | the stale copy has *more* WPs than P, so R winning is observable |
| FR-023 (placement half) | `lanes_with_coord` fact places SPEC | `placement_seam` (pre-existing, via `effective_root=` on base) | paired with the minter-refusal test for the lifecycle default |
| FR-011 (seam half) | `locate_work_package` missing-WP message names P | `locate_work_package` (pre-existing) | the message check includes the absolute owned path |

Markers:
- `tests/mission_runtime/test_placement_seam_owned.py`: `unit` + `fast` for the plain-dir tests, `git_repo` for the git-backed ones.
- `tests/mission_runtime/test_resolution_owned.py`: `git_repo`.

Commands:

```bash
uv run --frozen pytest tests/mission_runtime/test_resolution_owned.py tests/mission_runtime/test_placement_seam_owned.py tests/mission_runtime/test_owned_single_branch_ssot.py -q
uv run --frozen pytest tests/mission_runtime -q
uv run --frozen pytest tests/mission_runtime/test_coord_read_seam_callers.py tests/runtime/test_artifact_presence_placement.py tests/next/test_runtime_bridge_unit.py tests/next/test_decision_unit.py tests/specify_cli/next/test_next_invocation_lifecycle_seam.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_tasks.py tests/specify_cli/cli/commands/test_tasks_move_task_cwd.py tests/specify_cli/test_read_seam_migration_core.py tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py -q
uv run --frozen pytest tests/integration/test_explicit_checkout_commands.py tests/integration/test_owned_checkout_mark_status.py tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py -q
uv run --frozen pytest tests/architectural/test_mission_runtime_surface.py tests/architectural/test_layer_rules.py tests/architectural/test_cold_import_status_boundary.py -q
make test-fast
uv run --frozen ruff check src/mission_runtime/resolution.py src/mission_runtime/context.py src/specify_cli/task_utils/support.py tests/mission_runtime/test_placement_seam_owned.py tests/mission_runtime/test_resolution_owned.py tests/mission_runtime/test_owned_single_branch_ssot.py tests/mission_runtime/test_coord_read_seam_callers.py
uv run --frozen ruff format --check src/mission_runtime/resolution.py src/mission_runtime/context.py src/specify_cli/task_utils/support.py tests/mission_runtime/test_placement_seam_owned.py tests/mission_runtime/test_resolution_owned.py tests/mission_runtime/test_owned_single_branch_ssot.py tests/mission_runtime/test_coord_read_seam_callers.py
uv run --frozen mypy --strict src/mission_runtime/resolution.py src/mission_runtime/context.py src/specify_cli/task_utils/support.py
.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' src/mission_runtime/resolution.py src/specify_cli/task_utils/support.py
```

No `make test-full`, and no bare `tests/architectural/`.

## Risks & Mitigations

- **Coordination-topology `next` behaviour shifts when the guard goes.** Mitigation: T019 step 6 characterisation, the surface-stamp fix, and the named `next` regression files. Escalate a silent PRIMARY substitution for a COORD kind.
- **A second topology authority creeps back.** `mission_context_for` must not compare the fact's topology against `meta.json` and refuse, except when a caller passes a contradicting explicit `topology`.
- **An import cycle** between `owned_checkout.py` and `resolution.py`. Use a `TYPE_CHECKING` import in `resolution.py`.
- **More than six dual-keyword seams.** Four more functions need it (listed above). Mitigation: each carries `# TRANSITIONAL(WP18)`, so WP18's grep finds it; the Activity Log inventory is a cross-check.
- **Workspace leg still folds to R until WP05.** This is intentional (staging). T016 stubs it, and WP05 turns the real leg green.

## Review Guidance

- The red-first commits exist and precede the fix commits, and each red test asserts "under P" and "not under R".
- The fact arm makes no git calls and no `get_main_repo_root` calls (the plain-dir unit tests prove it).
- `_require_owned_single_branch` is gone; the owned arm's surface stamp is derived from the artifact home, not hard-coded.
- The legacy keyword is present on exactly the documented functions (six-seam members plus the four extras), each marked `# TRANSITIONAL(WP18)`, and passing both keywords raises `TypeError`.
- The re-expression of `tests/mission_runtime/test_coord_read_seam_callers.py` (owned here) carries its rationale.
- `resolve_workspace_for_wp` is untouched here (WP05).
- mypy `--strict` passed.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-28T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-09-28T21:56:58Z – unknown – Review cycle 1 fix — Activity Log (F6, consolidated per T016/T019/T021).

RED RUN (T016, cycle-1 legacy-keyword tests, commit 7832c5501, prior session):
- test_owned_wp_file_under_owned_checkout: FileNotFoundError "meta.json not
  found for mission 'owned-01M1A900' at .../R/kitty-specs/owned-01M1A900"
  (an R path).
- test_stale_root_copy_never_wins_wp_file: wp_file resolved under R's stale
  copy.
- test_missing_wp_scoped_to_owned_checkout: WP05 (only in R) found via R.

RED RUN (cycle-2 F1-F4 fixes, commit 79f58195c, this session, confirmed via
git-stash revert to the rejected c220d467d tip):
- test_lanes_with_coord_fact_stamps_status_state_coord_and_spec_primary (F2):
  resolved path was under P/.worktrees/<slug>-coord, not R/.worktrees.
- test_single_branch_fact_stamps_status_state_primary_at_mission_dir (F3):
  stamped COORD instead of PRIMARY for a single_branch STATUS_STATE read.
- test_unmaterialized_coord_fails_closed_never_a_predicted_path (F2): DID NOT
  RAISE (silently returned a non-existent predicted path).
- test_owned_handle_forms_all_resolve_the_same_fact[mid8|mission_id] (F4):
  PlacementSeam's exact-string check rejected non-slug handle forms.
Fix commit 639b1defa turned all of the above green; full tests/mission_runtime
(460 passed, 1 skipped) stayed green throughout both cycles.

T021 SCANNER CLASSIFICATION (before/after, `tests/architectural/_owned_checkout_scan.py`):
- Before this cycle's fix (rejected c220d467d): 8 marked TRANSITIONAL(WP18)
  declarations in resolution.py + 1 in support.py = 9 total; reviewer found 87
  G4 + 17 G5 raw hits, of which 7 private-helper `effective_root: Path | None`
  declarations were UNMARKED (_resolve_mission_slug, _resolve_wp_bearing_fields,
  _resolve_coordination_branch, _resolve_topology, _resolve_mission_id,
  _resolve_status_surface_dir, _assemble_core_fragments).
- After this cycle's fix: 15 marked declarations in resolution.py + 1 in
  support.py = 16 total (raw scanner hits: 105 in resolution.py, 0 in
  context.py, 7 in support.py = 112; every G5 param/field declaration hit
  carries the marker except `_refuse_both`'s own two-parameter signature,
  which is normaliser infrastructure, the same class of exemption the
  reviewer already accepted for the prior 2 normaliser signatures).
- Classification table (every converted function; "owned reads" = what the
  owned arm now consults):
  | Function | Owned-arm reads | Legacy arm |
  |---|---|---|
  | read_dir_for | owned.mission_dir (zero I/O) | unchanged (compose_meta_json_path) |
  | _resolve_mission_slug | owned.mission_slug / owned.mission_dir (zero I/O, canonicalised via _owned_handle_matches) | unchanged (resolve_handle_to_read_path walk) |
  | _resolve_wp_bearing_fields | forwards owned to locate_work_package | forwards effective_root to locate_work_package |
  | _resolve_coordination_branch | read_dir_for(owned=) then one meta.json read | unchanged |
  | _resolve_topology | owned.topology (zero I/O, no meta read at all) | unchanged (read_topology + classify_topology fallback) |
  | _resolve_mission_id | read_dir_for(owned=) then one meta.json read | unchanged |
  | _resolve_status_surface_dir | NEW _resolve_status_surface_dir_owned: owned.mission_dir + coord probe under owned.repository_root, UNMATERIALIZED fails closed (F2) | unchanged (effective_root-composed coord probe, kept byte-identical, still reachable for legacy callers) |
  | _assemble_core_fragments | primary_root = owned.repository_root (F2 fix); mission_id/coordination_branch/status_surface all forward owned= | unchanged (get_main_repo_root fold) |
  | mission_context_for | NEW _mission_context_for_owned: zero handle walk, zero resolver use, owned.target_branch/topology/mission_dir direct, explicit-topology conflict raises OWNED_TOPOLOGY_UNSUPPORTED | unchanged (candidate_feature_dir_for_mission walk) |
  | resolve_placement_only / resolve_artifact_surface | route through mission_context_for(owned=); F3 stamp = actual read_dir == owned.mission_dir | unchanged |
  | declared_read_surface | owned.topology directly (zero I/O) | unchanged |
  | PlacementSeam / placement_seam / resolve_action_context | thread owned through unchanged; canonical-identity refusal (F4) | unchanged |
  | locate_work_package (support.py) | owned.mission_dir + placement.read_dir(STATUS_STATE); F4 TaskCliError naming both slugs on mismatch | unchanged |
- WP18 T096 scope: after WP18 deletes every marked line (16 markers) plus
  the two normaliser-signature exemptions, `effective_root` reaches zero
  occurrences in resolution.py/support.py per the scanner.

ROW-4 GIT-CALL COUNT (T019 step 6, materialised lanes_with_coord coord read):
0 subprocess.run calls. `probe_coord_state`'s MATERIALIZED/EMPTY/UNMATERIALIZED
legs are pure `Path.exists()` checks; only the DELETED leg (absent coord dir +
a declared coordination_branch) shells out to one `git rev-parse`. Measured
directly in test_lanes_with_coord_fact_stamps_status_state_coord_and_spec_primary
via a counting subprocess.run monkeypatch (asserts `git_calls == []`).

RETROSPECTIVE writer.py FOLD CHECK (T017 step 6): PlacementSeam.read_dir's
RETROSPECTIVE branch passes `owned.owned_root` (not self.repo_root) as the
root into resolve_retrospective_home when a fact is present (set in the prior
session's commit c220d467d, unchanged by this cycle's fix). That function's
own leaf (_compose_primary_feature_dir) is a pure KITTY_SPECS_DIR join with
no get_main_repo_root fold; its canonicalisation step
(_canonicalize_primary_read_handle) is the SAME proven full-fold the PRIMARY
read leg already uses elsewhere in this module for the owned root. No
regression found; not independently re-audited beyond confirming the leaf
primitive itself does not fold to get_main_repo_root.

NEXT / E2E REASONING (T019 edge case): the placement-layer topology guard's
deletion means a coordination-topology fact reaching `next`'s legacy
effective_root= call sites now passes placement instead of refusing
OWNED_TOPOLOGY_UNSUPPORTED. tests/next/test_runtime_bridge_unit.py,
tests/specify_cli/next/test_next_invocation_lifecycle_seam.py and
tests/runtime/test_artifact_presence_placement.py all stayed green across
both cycles (192 passed, 1 skipped), and none of the three exercises the
owned+coord combination end-to-end. The nightly e2e
tests/e2e/test_worktree_owned_root_concurrency.py (not run locally, per
policy) is the actual owned-coordination-topology proof for `next`; F2's fix
(the coordination worktree composing under owned.repository_root, and
UNMATERIALIZED failing closed rather than returning a phantom path) is a
strict improvement for that path, not a behaviour narrowing, so no new risk
is introduced for it.
- 2026-09-28T22:32:22Z – unknown – Review cycle 2 fix — Activity Log (correcting the cycle-1 Activity Log's false
claim; R1-R5, F3-F5).

CORRECTION to the cycle-1 Activity Log entry: it claimed "after WP18 deletes
every marked line ... effective_root reaches zero occurrences" in
resolution.py/support.py. That is FALSE as stated. The scanner
(tests/architectural/_owned_checkout_scan.py) reports 112 raw G4/G5 hits
across resolution.py (105) + support.py (7); only 17 of those are the marked
legacy PARAMETER/FIELD declarations (16 in resolution.py, 1 in support.py --
see the exact list below). The remaining ~95 hits are `effective_root`
identifier/keyword uses INSIDE the legacy-arm BODIES of those same 17
functions (the `if effective_root is not None: <legacy branch>` code each
marked function keeps, per the orchestrator's accepted ruling that a
self-contained owned arm next to a separate, mechanically-deletable legacy
arm is the correct shape -- reversing course from the cycle-1 "fold to a bare
Path" anti-pattern the operator rejected). The TRUTHFUL statement: WP18 T096
deletes, per marked function, BOTH the marked parameter/field AND its
entire legacy-arm branch body (not merely the one marked line) -- after
which every `effective_root` reference those 95 unmarked-but-legacy-owned
hits represent is deleted along with the branch that contained them, and
the scanner then reports zero hits in both files. This is a mechanical,
per-function deletion (delete the `effective_root` parameter, delete the
`if owned is not None: ... else: <legacy branch>` conditional's `else`
arm, un-indent the `if` body), not a textual "delete every marked line"
operation.

EXACT FINAL MARKER LIST (17 total; per the orchestrator's ruling, this agent
is reporting the list for the orchestrator to amend into WP04's DoD and
WP18 T096 step 9b -- this agent has NOT edited either):

resolution.py (16):
1. `_refuse_both` -- `effective_root` param (NEW this cycle, R5)
2. `read_dir_for` -- `effective_root` param (positional)
3. `_resolve_mission_slug` -- `effective_root` param
4. `_resolve_wp_bearing_fields` -- `effective_root` param
5. `_resolve_coordination_branch` -- `effective_root` param
6. `_resolve_topology` -- `effective_root` param
7. `mission_context_for` -- `effective_root` param
8. `_resolve_mission_id` -- `effective_root` param
9. `_resolve_status_surface_dir` -- `effective_root` param
10. `_assemble_core_fragments` -- `effective_root` param
11. `resolve_placement_only` -- `effective_root` param
12. `PlacementSeam` -- `effective_root` field
13. `declared_read_surface` -- `effective_root` param
14. `resolve_artifact_surface` -- `effective_root` param
15. `placement_seam` -- `effective_root` param
16. `resolve_action_context` -- `effective_root` param

support.py (1):
17. `locate_work_package` -- `effective_root` param

(Count history: 9 at the rejected cycle-1 fix commit c220d467d; 16 after
cycle-1's re-fix commit 639b1defa, per the reviewer's accepted 9->16 ruling;
17 now, after R5 adds `_refuse_both`'s own marker this cycle.)

R2/F3 FIX SUMMARY: resolve_artifact_surface / resolve_placement_only's owned
arms no longer route through the whole-context builder
(_mission_context_for_owned) -- two new lean helpers,
_owned_read_dir_for_kind / _owned_commit_target_for_kind, resolve ONLY the
one requested MissionArtifactKind, so a PRIMARY kind (SPEC/PLAN) never
probes the coordination surface at all (T019 row 3: it can never fail on an
UNMATERIALIZED or EMPTY coordination window). _resolve_status_surface_dir_owned
now fails closed on EVERY non-materialised coordination state for a
COORD-partition kind (EMPTY / UNMATERIALIZED / NONE), not just
UNMATERIALIZED -- closing the #1716 silent-PRIMARY-fallback regression on
EMPTY specifically. The F3 stamp is now `COORD iff routes_through_coordination
(owned.topology) and not is_primary_artifact_kind(kind) else PRIMARY` --
purely topology+partition, never path equality.

F4/R3 FIX SUMMARY: the ONE canonical handle matcher is now
`mission_runtime.identity.handle_names_mission(handle, mission_slug)`,
exported from the mission_runtime root and registered in
tests/architectural/test_mission_runtime_surface.py. Both private
`_owned_handle_matches` duplicates (resolution.py, support.py) are deleted.
Tightened: the mission-id form requires an exact 26-character Crockford
base32 match (not merely `len(handle) >= 8`); the mid8 form requires an
exact 8-character match. `"<mid8>-something-else"` is now refused.

F5 FIX SUMMARY: `mission_finalize.py:3353`'s literal-dict splat into
`placement_seam` is now `owned=owned` (owned is already `OwnedCheckout |
None` there). Declared out-of-map (WP13's file, verified against
kitty-specs/.../tasks/WP13-atomic-finalize-tasks.md) in the commit body.
The 3 mislabelled `# bridging: WP16 converts` markers on
`tasks_move_task.py` sites that already pass `owned=st.owned` in final form
are removed; the 4 genuine bridge sites (calling functions that still only
accept `effective_root`) keep their markers.

TESTS: tests/mission_runtime 470 passed, 1 skipped (was 467 passed at the
reviewed cycle-1 tip -- 3 net new: the row-3/row-4/prefix-refusal pins, plus
several more R1 pins that were already green). Combined blast-radius
(all previously-listed validation files): 549 passed, 3 skipped.
`ruff check` clean; C901 <= 11 on every touched function. `mypy --strict
--explicit-package-bases` over the seams + their direct callers/callees (30
files): 0 new errors versus the confirmed-pre-existing baseline (4
`_EffectiveRootKwargs` assignment errors in accept.py/gates_core.py, plus 4
unrelated `no-any-return` errors in files this WP's diff never touches --
verified via `git diff --stat` showing 1 line changed in mission_finalize.py
total).
- 2026-09-28T22:57:51Z – unknown – Review cycle 3 fix: _mission_context_for_owned now calls _owned_read_dir_for_kind / _owned_commit_target_for_kind per kind (S1 blocker), deleting the duplicated inline branching + coord_ref expression + the ineffective _lazy_status_surface_dir memo. Docstring rewritten: drops the false 'lazy' claim, states honestly that a whole-context build under a coord-routing topology whose worktree is not MATERIALIZED fails closed with OWNED_COORDINATION_WORKSPACE_UNAVAILABLE (IC-05 -> blocked), and notes resolve_artifact_surface/resolve_placement_only bypass this function and keep row-3 success for PRIMARY kinds. Added a spy-based test pinning the CALL (not just the value) and a parametrised topology x coord-state x kind agreement test. Fixed test_owned_resolver_never_consulted to use the MID8 handle (was vacuous with the exact slug); verified non-vacuous against cycle-1 source c220d467d in a scratch worktree. Correction: the cycle-2 commit (66bfb2855) body says '17 in resolution.py + 1 in support.py = 18 markers'; that arithmetic is wrong -- it is 16 + 1 = 17, matching the DoD. History is not rewritten; this entry records the correction. Commits: e81801bf7 (red-first tests), 6ff8178b6 (fix). Tests: test_placement_seam_owned.py x 176, plus test_resolution_owned.py/test_owned_single_branch_ssot.py/test_coord_read_seam_callers.py = 217 passed; full tests/mission_runtime/ + test_mission_runtime_surface.py + test_next_owned_commit_guard.py + test_next_answer_effective_root.py = 636 passed, 1 skipped. ruff check/format clean. mypy --strict --explicit-package-bases on resolution.py: 0 issues, byte-identical pre/post. Marker count unchanged at 17 (16+1).
- 2026-09-28T23:10:55Z – unknown – Review cycle 4 fix (test-only, no src change): widened test_mission_context_for_owned_agrees_with_the_per_kind_resolvers to the full grid the reviewer independently verified -- 4 topologies (single_branch, lanes, coord, lanes_with_coord) x 3 coordination states (materialized, empty, unmaterialized) x 18 kinds (RETROSPECTIVE included) = 216 cells. Added MissionTopology.COORD (previously omitted with no reason). Included RETROSPECTIVE (all three resolvers agree on it). In the refusal branch, added the per-kind COORD-kind check: resolve_artifact_surface raises OWNED_COORDINATION_WORKSPACE_UNAVAILABLE; resolve_placement_only is asserted to return the declared coordination_branch value instead, since R2 (cycle 2) already made placement never probe materialization -- not a regression, the existing contract. Applied the empty/unmaterialized coord-worktree mutation to every topology, not only lanes_with_coord, so single_branch/lanes 'resolves regardless of coord_state' is now actually exercised, not merely asserted against an untouched fixture. All 216 cells pass against the unmodified src. Commit: 50b7de384. Tests: test_placement_seam_owned.py x 239; plus test_resolution_owned.py/test_owned_single_branch_ssot.py/test_coord_read_seam_callers.py = 280 total. ruff check/format clean. Marker count unchanged at 17 (no src touched).
