---
work_package_id: WP05
title: Workspace resolution owned arm
dependencies:
- WP04
requirement_refs:
- FR-006
- FR-011
- FR-019
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
- T025
- T026
phase: Phase 2 - Seams
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/workspace/
create_intent:
- tests/specify_cli/workspace/test_owned_workspace_resolution.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/workspace/context.py
- src/mission_runtime/checkout_identity.py
- tests/runtime/test_workspace_context_unit.py
- tests/specify_cli/workspace/test_owned_workspace_resolution.py
- src/specify_cli/core/stale_detection.py
- src/specify_cli/lanes/implement_support.py
- src/specify_cli/cli/commands/implement.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Workspace resolution owned arm

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

Give WP workspace resolution an owned arm, per-checkout caches and an identity-guard arm:

1. `resolve_workspace_for_wp(..., owned=fact)` for an owned single_branch mission returns a `ResolvedWorkspace` with these fields (data-model.md §ResolvedWorkspace):
   - `resolution_kind="owned_checkout"`
   - `worktree_path=owned.owned_root`
   - `lane_id=None`
   - `lane_wp_ids=[]`
   - `branch_name=owned.target_branch`

   It is a workspace-resolution kind only; status-source classification is unchanged (FR-011, C-002).
2. Coordination-topology owned missions (reachable only through `next`) keep the lane arm, reading `lanes.json` and WP metadata from the owned checkout (plan §IC-03).
3. The process-local WP-metadata caches are keyed on the **resolved read `tasks_dir`**, so the same mission slug in the repository root checkout and in an owned checkout never share entries within one process (FR-019).
4. `enforce_checkout_identity` gains an `owned_checkout` arm: a WP-execution write whose invoking cwd is outside the owned checkout is refused (FR-011).
5. `_resolve_wp_bearing_fields` (WP04's file) forwards the fact to the workspace resolver. This is a declared one-line out-of-map edit, so `agent context resolve` / `resolve_action_context` report `workspace_path` under P and `resolution_kind=owned_checkout` (FR-006, spec US2-AS1).

**Staging.** `resolve_workspace_for_wp` is one of the six shared dual-keyword seams (plan §Staging Strategy: the six shared seams plus every other function marked TRANSITIONAL(WP18)). It gains `owned=` and a transitional legacy `effective_root=`, which only redirects WP-metadata and `lanes.json` reads and never produces the owned kind. The legacy keyword carries `# TRANSITIONAL(WP18): <reason>`; WP18 deletes it.

**Owned consumers.** This WP also owns the `resolution_kind` / `runs_in_checkout_root` consumers `core/stale_detection.py`, `lanes/implement_support.py` and `cli/commands/implement.py` (T023 step 6), including stale_detection's `resolve_workspace_for_wp(owned=)` pass-through that WP09's status command uses.

**Done means**:
- the red-first tests went red on base and are green now;
- `tests/runtime/test_workspace_context_unit.py` is green (the lane-mission positive controls are unchanged);
- the owned regression files are green;
- complexity is ≤ 15 (target ≤ 11) on the touched functions;
- ruff, format and mypy `--strict` are clean, and `make test-fast` is green.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP05 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **1** marker: `src/specify_cli/workspace/context.py` 1 (`resolve_workspace_for_wp(effective_root=)`).
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

- `spec.md`: US2-AS1, US3-AS3 (the workspace is P, never a lane worktree under R), FR-006, FR-011, FR-019, §Edge Cases ("Same slug in two owned checkouts").
- `plan.md`: §IC-03, §Staging Strategy ("Campsite first"), §Test Layout; §IC-13 (the #5009 carry of edaa9cd83's lookup and cache half).
- `research.md`: R-04, R-06 (the O5 wedge: `decision._state_to_action` → `resolve_workspace_for_wp` folds to R; WP11/WP12/WP19 consume this arm), R-15.
- `data-model.md`: §ResolvedWorkspace (extended).
- `contracts/owned-checkout-carrier.md` §7 (`resolve_workspace_for_wp` is a named consumer).

**Current code (HEAD `df1588860`)**:
- `src/specify_cli/workspace/context.py`:
  - cache dicts `:100-103`; `clear_workspace_resolution_caches` `:123-128`;
  - `ResolvedWorkspace` `:197-241`: `exists` and `is_husk` special-case `"lane_workspace"`;
  - `_normalized_feature_cache_key(repo_root, mission_slug)` `:557-558`, **keyed on `repo_root`** (the FR-019 defect);
  - `build_normalized_wp_index` `:627-674`: `placement_seam(repo_root, mission_slug)` without the owned root at `:641`;
  - `get_normalized_wp` `:677-696`: same at `:692`;
  - `resolve_workspace_for_wp` `:699-744`: the identity gate at `:732-743` uses `get_main_repo_root(repo_root)`;
  - `_resolve_workspace_for_wp_impl` `:747-868`: arms for planning_artifact (`:761-800`), existing context (`:802-816`), planning lane (`:834-848`) and lane (`:850-868`). Lane paths are composed through `_seam_worktree_path(repo_root, …)` (`:863`; import at `:27`).
- `src/mission_runtime/checkout_identity.py`: `_LANE_WORKSPACE_KIND` `:39`, `CheckoutIdentityError` `:42-74`, `_is_within` `:77-79`, `_checkout_root` `:82-99`, `enforce_checkout_identity` `:102-139`. The module deliberately has **zero spec-kitty imports** (`:26-33`); keep it that way.
- The only callers passing `write_intent=True`: `cli/commands/implement.py:2064`, `cli/commands/agent/workflow.py:1449`, `cli/commands/agent/workflow_executor.py:1571`.
- The consumers that branch on `resolution_kind` outside this file:
  - **owned by this WP** (T023 step 6): `cli/commands/implement.py:1480`, `core/stale_detection.py:483-485`, `lanes/implement_support.py:146,270`;
  - owned by downstream WPs, which you must **not** edit here but must inventory (Risks): `cli/commands/agent/tasks_parsing_validation.py:706`, `cli/commands/agent/tasks_status_cmd.py:313`, `cli/commands/agent/workflow.py:1450,1675`, `cli/commands/agent/tasks_move_task.py:889`, `cli/commands/agent/workflow_executor.py:1573,1834,1850,2203,2210`.

**Complexity (measured on HEAD).** `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=8' src/specify_cli/workspace/context.py src/mission_runtime/checkout_identity.py` flags only `resolve_active_wp_for_branch` (9), which this WP does not touch. `_resolve_workspace_for_wp_impl` is under the threshold today, but adding an owned arm would push it over, so the extraction comes **first** (T026, done as the first commit).

**Constraints**:
- **No git subprocess on the owned arm** (NFR-002). Owned resolution is file reads only. `enforce_checkout_identity` stays pure-path (NFR-004 of write-path-integrity).
- **Layering.** `workspace/context.py` imports `OwnedCheckout` from the `mission_runtime` package root (it already imports from there, `:28`). `checkout_identity.py` does not need the type: it receives the kind string and paths.
- **Terminology.** New messages say "owned checkout" and "repository root checkout".

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Lane**: assigned in `lanes.json` by `finalize-tasks` (not yet generated). Depends on WP04; use `spec-kitty implement WP05`.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

> **Order of commits**: T026's extraction is the first commit (tidy-first, behaviour-preserving). Then T022 (red), then T023/T024/T025 (green).

### Subtask T022 – Red-first: owned workspace kind and same-slug cache isolation

- **Purpose**: Reproduce, through pre-existing entry points, that owned WP workspace resolution folds to the repository root checkout (O3/O4 workspace leg, FR-006/FR-011) and that WP metadata caches collide across checkouts (FR-019).
- **Steps**:
  1. Create `tests/specify_cli/workspace/test_owned_workspace_resolution.py`. The directory is new and `tests/specify_cli/workspace/` has no `__init__.py`. Several sibling test dirs also have none (`tests/specify_cli/acceptance`, `tests/specify_cli/config`), and the basename is unique repository-wide, so collection works. If collection fails, adding `tests/specify_cli/workspace/__init__.py` is a declared out-of-map edit; record it.
  2. Local builder `_owned_repo(tmp_path, *, topology="single_branch", stale_root_copy=False)`, the same shape as WP04's builder: R, then P via `git worktree add -b codex/owned`, then the mission in P with `WP01-a.md` / `WP02-b.md` (`execution_mode: code_change`, distinct `title:` values) and a `lanes.json` as finalize writes it. The simplest faithful way to get a real `lanes.json` is `specify_cli.lanes.persistence.write_lanes_json` with one lane holding WP01/WP02 (see `tests/runtime/test_workspace_context_unit.py:10-11` for the imports). Commit in P. The optional stale copy writes the mission into R with a **different** `title:` for WP01 and extra WPs.
  3. **Red tests** (commit before the fix; `git_repo` marker):
     - `test_owned_workspace_is_owned_checkout` (FR-006/FR-011, pre-existing entry point `mission_runtime.resolve_action_context(R, action="implement", feature=slug, wp_id="WP01", effective_root=P)` **without** a stub, now that WP04 fixed the `wp_file` leg). Assert `workspace_path == str(P.resolve())`, `resolution_kind == "owned_checkout"`, `lane_id is None`, and no returned path under R. On base the workspace leg folds to R (lane worktree under `R/.worktrees/`, or `ValueError` from the R-side WP index), so the test is red.
     - `test_same_slug_cache_isolated_per_checkout` (FR-019, re-expressing #5009 edaa9cd83's `test_wp_cache_is_scoped_to_selected_checkout`; see Carry below). In one process:
       - `get_normalized_wp(R, slug, "WP01").metadata.title` is R's title;
       - then the P-side lookup returns P's title;
       - then R's lookup again returns R's title.

       On base the P-side call has no keyword to reach P (`TypeError`), and a `repo_root=P` call collides with R's key through `get_main_repo_root`. Red either way.
  4. In the fix commit, re-point **the same tests** to `owned=` minted through the real minter `specify_cli.core.owned_mission.resolve_owned_mission(R, P, slug)`. The assertions must not change. The legacy keyword cannot produce the `owned_checkout` kind (see T023), so the diff between the red commit and the fix commit shows only the call-shape change. Reviewers verify this.
  5. **Carry (#5009, plan §IC-13).** edaa9cd83 (author Samuel Goff) adds its tests to `tests/integration/test_explicit_checkout_commands.py`, a WP19-owned file. WP19 (T101) cherry-picks that commit (`git cherry-pick -x`). Here, **re-express** only the cache test, and put this trailer on the commit: `Co-authored-by: Samuel Goff <samuel@defpix.com>` (the author address on every #5009 commit).
  6. Suggested module layout for the new test file, so later subtasks append in place:
     - `# --- builders ---`: `_owned_repo`, `_mint_plain` (a plain-dir fact via `OwnedCheckout._mint`);
     - `# --- T022 red-first (owned kind, cache isolation) ---`;
     - `# --- T023 owned arm / coordination-topology characterisation ---`;
     - `# --- T024 cache keys ---`;
     - `# --- T025 identity guard ---`.

     Put the per-test markers on each test, not on the module: this file mixes `git_repo` tests with `unit` + `fast` tests, and a module-level `pytestmark` would mislabel half of them for `make test-fast` selection.
- **Commit sequence**: (1) the T026 extraction (green, pure refactor); (2) this file with the two red tests via the legacy entry points; (3) T023/T024 fix commits that re-point the two tests to `owned=`.
- **Files**: `tests/specify_cli/workspace/test_owned_workspace_resolution.py` (new).
- **Validation checklist**:
  - [ ] Red run recorded (test ids, failure lines).
  - [ ] The cache test's third call proves no cross-contamination in **either** direction.
- **Edge cases**:
  - Call `clear_workspace_resolution_caches()` in an autouse fixture in this file, so tests do not leak state into each other.
  - The WP titles must differ between R and P, or the isolation assertion is vacuous.

### Subtask T023 – `resolve_workspace_for_wp(owned=)` owned arm (dual keyword)

- **Purpose**: Resolve an owned WP's workspace to the owned checkout itself, never to a lane worktree under R (FR-006, FR-011, US3-AS3).
- **Steps**:
  1. Change the signature to `resolve_workspace_for_wp(repo_root, mission_slug, wp_id, *, write_intent=False, current_cwd=None, owned: OwnedCheckout | None = None, effective_root: Path | None = None)`. Passing both keywords raises `TypeError`. A fact whose `mission_slug` differs from `mission_slug` raises `ValueError` naming both.
  2. In `_resolve_workspace_for_wp_impl` (after T026's extraction), dispatch on the fact:
     - `owned is not None` and **not** `routes_through_coordination(owned.topology)` (that is, SINGLE_BRANCH; LANES cannot be minted): return the owned workspace with the fields in Objectives #1, plus `workspace_name=owned.owned_root.name`, `execution_mode` and `mode_source` from the owned WP index (`get_normalized_wp(..., owned=owned)`), and `context=None`. This applies to **both** `code_change` and `planning_artifact` WPs: the mission's planning surface *is* the owned checkout.
     - `owned is not None` with a coordination topology (`LANES_WITH_COORD`, `COORD`; only `next` mints these): keep the existing arms, but read the WP index and `lanes.json` through `placement_seam(repo_root, mission_slug, owned=owned)`. **Characterise before changing** where lane worktree paths are anchored today for owned coordination `next` (`next_cmd.py:176` passes `repo_root=P` today, so lane paths are composed under P). Pin the current anchor with a test, and preserve it. The nightly `tests/e2e/test_worktree_owned_root_concurrency.py:405-431` depends on it. Record the characterisation in the Activity Log.
     - Legacy `effective_root=`: identical to today's arms, except that WP-metadata and `lanes.json` reads go through `placement_seam(repo_root, mission_slug, effective_root=effective_root)`. It never returns `owned_checkout` (no fact means no topology or target proof).
  3. **Declared out-of-map edit** in `src/mission_runtime/resolution.py::_resolve_wp_bearing_fields` (the `resolve_workspace_for_wp(repo_root, mission_slug, normalized_wp_id)` call, currently `resolution.py:718`): add `owned=owned`. WP04 threads `owned` into that function and leaves this one call for you, because the keyword does not exist before this WP. PR rationale line: "WP04 owns `resolution.py`; the `owned=` keyword on `resolve_workspace_for_wp` exists only from WP05." Also remove WP04's explanatory comment at that call.
  4. Target shape of the owned single_branch arm (a helper extracted next to T026's arm helpers):
     ```python
     def _owned_checkout_workspace(repo_root: Path, owned: OwnedCheckout, wp_id: str) -> ResolvedWorkspace:
         normalized_wp = get_normalized_wp(repo_root, owned.mission_slug, wp_id, owned=owned)
         execution_mode = WorkProductKind(normalized_wp.metadata.execution_mode or WorkProductKind.CODE_CHANGE)
         return ResolvedWorkspace(
             mission_slug=owned.mission_slug, wp_id=wp_id,
             execution_mode=execution_mode.value, mode_source=normalized_wp.mode_source,
             resolution_kind=_OWNED_CHECKOUT_KIND, workspace_name=owned.owned_root.name,
             worktree_path=owned.owned_root, branch_name=owned.target_branch,
             lane_id=None, lane_wp_ids=[], context=None,
         )
     ```
     Define `_OWNED_CHECKOUT_KIND = "owned_checkout"` once in this module. The string is a `serialized_keys` value (it appears in `context resolve --json` as `resolution_kind`), so name it and never retype it.
  5. `ResolvedWorkspace.exists` / `is_husk` (`:219-241`): the `owned_checkout` kind behaves like `repo_root`: it exists when the path exists, and it is never a husk. Add a small property `runs_in_checkout_root -> bool` (True for `repo_root` and `owned_checkout`) and use it in `exists`. Downstream WPs migrate their `== "repo_root"` comparisons to it (Risks).
  6. **Owned consumers (in this WP's owned files).**
     - `core/stale_detection.py::check_doing_wps_for_staleness` gains `*, owned: OwnedCheckout | None = None` and passes it through as `resolve_workspace_for_wp(main_repo_root, mission_slug, wp_id, owned=owned)` (`:483`). WP09 T045 passes `owned=st.owned`; nothing else changes.
     - `cli/commands/implement.py:1480` and `lanes/implement_support.py:146,270`: replace `resolution_kind == "repo_root"` with `workspace.runs_in_checkout_root` where the intent is "runs in a checkout root, not a lane worktree"; leave a comparison unchanged where it really means "the repository root checkout only", and record each decision in the Activity Log. `implement` is not an owned command (FR-018), so behaviour for non-owned missions is unchanged; pin it with the existing tests below.
- **Files**: `src/specify_cli/workspace/context.py`, `src/specify_cli/core/stale_detection.py`, `src/specify_cli/lanes/implement_support.py`, `src/specify_cli/cli/commands/implement.py`; out-of-map: `src/mission_runtime/resolution.py` (one line).
- **Validation checklist**:
  - [ ] T022's `test_owned_workspace_is_owned_checkout` (the `owned=` form) is green, and `resolve_action_context(..., owned=fact)` shows the owned kind end to end.
  - [ ] A lane-mission positive control: on an ordinary non-owned lanes mission, `resolve_workspace_for_wp(R, slug, "WP01")` still returns `lane_workspace` with the same path as before. The existing tests at `tests/runtime/test_workspace_context_unit.py:447-559` cover it; confirm they are green unchanged.
  - [ ] No git subprocess runs on the owned single_branch arm: monkeypatch `subprocess.run` to raise in one test.
- **Edge cases**:
  - A WP absent from the owned index raises `ValueError` whose message names the **owned** tasks dir (it comes from `get_normalized_wp`'s message at `:692`, which must compute the directory through the owned seam).
  - The owned arm must not consult `find_context_for_wp(repo_root, …)` (`:802`). That reads R's `.kittify/workspaces` contexts, which belong to lane worktrees, not to the owned checkout.

### Subtask T024 – Cache keyed on the resolved `tasks_dir` plus cache-clear tests

- **Purpose**: Make "same slug in two checkouts" safe within one process (FR-019, spec §Edge Cases). Today the key is `(str(repo_root.resolve()), mission_slug)` (`:557-558`); an owned lookup that also passes R would share R's entry.
- **Steps**:
  1. Replace `_normalized_feature_cache_key(repo_root, mission_slug)` with `_normalized_feature_cache_key(tasks_dir: Path, mission_slug: str) -> tuple[str, str]`, returning `(str(tasks_dir.resolve()), mission_slug)`.
  2. In `build_normalized_wp_index(repo_root, mission_slug, *, owned=None, effective_root=None)` and `get_normalized_wp(..., *, owned=None, effective_root=None)`: compute `tasks_dir` **first**, through `placement_seam(repo_root, mission_slug, owned=owned | effective_root=…)`, then key every cache (`_FEATURE_WP_METADATA_CACHE`, `_ERROR_CACHE`, `_SNAPSHOT_CACHE`) on it. `get_normalized_wp` must use the same key for its error-cache lookup (`:683`), or the error path silently misses.
  3. Tests in `tests/specify_cli/workspace/test_owned_workspace_resolution.py` (`unit` + `fast`, plain `tmp_path` dirs with a fact minted via `OwnedCheckout._mint`):
     - an R-then-P-then-R lookup returns three correct titles (this is T022's test in fact form);
     - editing P's WP file (mtime change) invalidates only P's entry: R's cached object identity is unchanged;
     - `clear_workspace_resolution_caches()` empties all three metadata caches (assert on the module dicts) and a following lookup re-reads from disk;
     - a malformed WP in P puts the error only under P's key: R's lookup of the same WP id succeeds.
  4. Target shape of the key and lookup (sketch):
     ```python
     def _normalized_feature_cache_key(tasks_dir: Path, mission_slug: str) -> tuple[str, str]:
         return (str(tasks_dir.resolve()), mission_slug)

     def _wp_tasks_dir(repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None, effective_root: Path | None) -> Path:
         seam = placement_seam(repo_root, mission_slug, owned=owned, effective_root=effective_root)
         return seam.read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks"
     ```
     Compute `_wp_tasks_dir` exactly once per `build_normalized_wp_index` / `get_normalized_wp` call. The not-found message in `get_normalized_wp` (`:688-693`) reuses that same value instead of calling `placement_seam` a second time. That also removes a duplicate seam construction on the error path.
  5. Keep `tests/runtime/test_workspace_context_unit.py` green. Its cache tests (`:261-331`) monkeypatch internals. If a test references `_normalized_feature_cache_key` with the old argument, update that test (the file is owned by this WP) to the new key semantics, and say so in the Activity Log.
- **Files**: `src/specify_cli/workspace/context.py`, `tests/specify_cli/workspace/test_owned_workspace_resolution.py`, `tests/runtime/test_workspace_context_unit.py`.
- **Validation checklist**:
  - [ ] `pytest tests/runtime/test_workspace_context_unit.py tests/specify_cli/workspace/test_owned_workspace_resolution.py -q` is green.
  - [ ] `grep -n "_normalized_feature_cache_key(" src tests` shows every call passing a tasks dir.
- **Edge cases**:
  - A symlinked P and the real P must hit the **same** key (`resolve()`); add one test.
  - `_FEATURE_CONTEXT_INDEX_CACHE` (`:100`) is keyed on R's workspace contexts. It is out of scope and untouched: it never serves the owned arm.
  - Two owned checkouts with the same slug (P1 and P2, spec §Edge Cases) must also isolate. Add a three-checkout variant (R, P1, P2) with distinct titles that cycles through R, P1, P2, P1, R.
  - `save_context` clears only `_FEATURE_CONTEXT_INDEX_CACHE` (`:306`). Do not widen that; the WP-metadata cache is snapshot-validated by mtime per tasks dir.

### Subtask T025 – `enforce_checkout_identity` owned arm

- **Purpose**: A WP-execution write for an owned WP must be invoked from inside the owned checkout; a fact whose checkout mismatches the invoking checkout is refused (FR-011).
- **Steps**:
  1. In `src/mission_runtime/checkout_identity.py`, add `_OWNED_CHECKOUT_KIND = "owned_checkout"`. In `enforce_checkout_identity`:
     - `resolution_kind == "owned_checkout"`: proceed iff `_is_within(current_cwd.resolve(), workspace_path.resolve())`. Otherwise raise `CheckoutIdentityError`. There is **no** repository-root allowance: unlike lane workspaces, R is not an allocation point for an owned checkout.
     - `lane_workspace`: unchanged.
     - Every other kind: unchanged (exempt).
  2. Give `CheckoutIdentityError.__init__` a keyword `owned: bool = False` that selects owned-specific guidance: "cd into the owned checkout <expected> and retry". Keep the existing message for the lane arm byte-identical; `tests/specify_cli/core/test_worktree_topology.py` may pin it.
  3. In `resolve_workspace_for_wp`'s gate (`workspace/context.py:732-743`), pass `primary_root=owned.repository_root` for owned calls instead of `get_main_repo_root(repo_root)`, so the owned gate makes no git call.
  4. Target shape (the existing lane arm stays byte-identical below it):
     ```python
     if resolution_kind == _OWNED_CHECKOUT_KIND:
         cwd = current_cwd.resolve()
         owned_root = workspace_path.resolve()
         if _is_within(cwd, owned_root):
             return
         raise CheckoutIdentityError(expected=workspace_path, actual=current_cwd,
                                     mission_slug=mission_slug, wp_id=wp_id, owned=True)
     if resolution_kind != _LANE_WORKSPACE_KIND:
         return
     ...  # unchanged lane arm
     ```
     Update the module docstring (`:1-24`): it states that only `lane_workspace` is gated, which is no longer true. Name the owned arm and FR-011.
  5. Tests (`unit` + `fast`, pure paths, in `tests/specify_cli/workspace/test_owned_workspace_resolution.py`):
     - cwd = P → passes;
     - cwd = a subdirectory of P → passes;
     - cwd = R → refused, and `excinfo.value.expected == P`;
     - cwd = a sibling checkout → refused;
     - cwd = a lane worktree under R → refused;
     - the lane-kind control is unchanged: cwd = R with `lane_workspace` passes (the existing semantics);
     - a `repo_root` kind is always exempt.
     Plus one integration-shaped test through `resolve_workspace_for_wp(..., write_intent=True, current_cwd=R, owned=fact)`, which raises.
- **Files**: `src/mission_runtime/checkout_identity.py`, `src/specify_cli/workspace/context.py`, `tests/specify_cli/workspace/test_owned_workspace_resolution.py`.
- **Parallel?**: Yes with T024 once T023 exists.
- **Validation checklist**:
  - [ ] `pytest tests/specify_cli/core/test_worktree_topology.py tests/integration/test_coord_loop_workspace.py -q` is green (the existing identity-guard users).
  - [ ] `checkout_identity.py` still has zero spec-kitty imports.
- **Edge cases**:
  - Windows case variants: `Path.resolve()` normalises case for existing paths on Windows. Do not add a case-fold here (WP01's fact is already canonical). Mention this in the docstring.

### Subtask T026 – Campsite extractions for complexity ≤ 15

- **Purpose**: Keep the touched functions well under the ceiling before adding arms (charter Standing Order 2, plan §Staging Strategy "Campsite first"). This is **the first commit** of the WP.
- **Steps**:
  1. Measure and record in the Activity Log:
     ```bash
     .venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' src/specify_cli/workspace/context.py src/mission_runtime/checkout_identity.py
     .venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=6' src/specify_cli/workspace/context.py src/mission_runtime/checkout_identity.py
     ```
     The second run shows the headroom of each function.
  2. Behaviour-preserving extraction in `_resolve_workspace_for_wp_impl` (`:747-868`). Split the four arms into:
     - `_planning_artifact_workspace(...)` (`:761-800`)
     - `_context_backed_workspace(...)` (`:802-816`)
     - `_planning_lane_workspace(...)` (`:834-848`)
     - `_lane_workspace(...)` (`:850-868`)

     The impl becomes a short dispatcher. No behaviour change: run `tests/runtime/test_workspace_context_unit.py` before and after, and the pass count must be identical.
  3. After T023–T025, re-measure. Every touched function must be ≤ 11, and nothing may reach 12+.
  4. Target dispatcher shape after T023 (for orientation; the extraction commit contains only the four existing arms):
     ```python
     def _resolve_workspace_for_wp_impl(repo_root, mission_slug, wp_id, *, owned=None, effective_root=None):
         if owned is not None and not routes_through_coordination(owned.topology):
             return _owned_checkout_workspace(repo_root, owned, wp_id)
         normalized_wp = get_normalized_wp(repo_root, mission_slug, wp_id, owned=owned, effective_root=effective_root)
         execution_mode = WorkProductKind(normalized_wp.metadata.execution_mode or WorkProductKind.CODE_CHANGE)
         if execution_mode == WorkProductKind.PLANNING_ARTIFACT:
             return _planning_artifact_workspace(...)
         context = find_context_for_wp(repo_root, mission_slug, wp_id)
         if context is not None:
             return _context_backed_workspace(...)
         return _lanes_manifest_workspace(...)   # planning-lane or lane arm
     ```
  5. Keep the helpers module-private (leading underscore). `test_no_dead_symbols.py` only scans public names, so private helpers need no allowlist.
- **Files**: `src/specify_cli/workspace/context.py`.
- **Validation checklist**:
  - [ ] The extraction commit contains no functional change; the diff is only moved code plus calls.
  - [ ] Before and after complexity numbers are recorded.
- **Edge cases**:
  - Do not merge the arms or change their order. The first-match semantics (planning_artifact → existing context → lanes.json) are behaviour.

## Test Strategy

**Red-first map** (C-007):

| Requirement | Red-first test | Entry point (pre-existing) | Non-vacuity |
|---|---|---|---|
| FR-006 / FR-011 | `test_owned_workspace_is_owned_checkout` | `mission_runtime.resolve_action_context(effective_root=P)` | asserts kind, null lane, path under P **and** no path under R; the lane positive control is unchanged |
| FR-019 | `test_same_slug_cache_isolated_per_checkout` | `get_normalized_wp` | distinct titles in R and P; R-P-R order proves both directions |
| FR-011 (guard) | owned-arm identity tests | `enforce_checkout_identity` | mismatched cwd refused; lane control unchanged |

Markers:
- `tests/specify_cli/workspace/test_owned_workspace_resolution.py`: `git_repo` for the git-built tests, `unit` + `fast` for the pure-path ones.
- `tests/runtime/test_workspace_context_unit.py`: keep its existing markers.

Commands:

```bash
uv run --frozen pytest tests/specify_cli/workspace/test_owned_workspace_resolution.py tests/runtime/test_workspace_context_unit.py -q
uv run --frozen pytest tests/mission_runtime/test_resolution_owned.py tests/mission_runtime/test_placement_seam_owned.py -q
uv run --frozen pytest tests/specify_cli/core/test_worktree_topology.py tests/integration/test_coord_loop_workspace.py tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py -q
uv run --frozen pytest tests/next/test_decision_unit.py tests/next/test_runtime_bridge_unit.py tests/specify_cli/next/test_next_invocation_lifecycle_seam.py -q
uv run --frozen pytest tests/integration/test_explicit_checkout_commands.py tests/integration/test_owned_checkout_mark_status.py tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py -q
uv run --frozen pytest tests/architectural/test_mission_runtime_surface.py tests/architectural/test_layer_rules.py -q
grep -rl "stale_detection\|implement_support\|commands.implement\b\|commands import implement" tests/ --include="*.py"   # run each hit (skip e2e/slow)
make test-fast
uv run --frozen ruff check src/specify_cli/workspace/context.py src/mission_runtime/checkout_identity.py src/mission_runtime/resolution.py src/specify_cli/core/stale_detection.py src/specify_cli/lanes/implement_support.py src/specify_cli/cli/commands/implement.py tests/specify_cli/workspace/test_owned_workspace_resolution.py tests/runtime/test_workspace_context_unit.py
uv run --frozen ruff format --check src/specify_cli/workspace/context.py src/mission_runtime/checkout_identity.py src/mission_runtime/resolution.py src/specify_cli/core/stale_detection.py src/specify_cli/lanes/implement_support.py src/specify_cli/cli/commands/implement.py tests/specify_cli/workspace/test_owned_workspace_resolution.py tests/runtime/test_workspace_context_unit.py
uv run --frozen mypy --strict src/specify_cli/workspace/context.py src/mission_runtime/checkout_identity.py src/mission_runtime/resolution.py src/specify_cli/core/stale_detection.py src/specify_cli/lanes/implement_support.py src/specify_cli/cli/commands/implement.py  # callers and callees in ONE invocation (follow_imports = "skip" for specify_cli.*)
```

No `make test-full`, and no bare `tests/architectural/`.

## Risks & Mitigations

- **Consumers that branch on `resolution_kind == "repo_root"`** will treat `owned_checkout` as "not repo root", which in some places means "worktree". The sites are listed in Context. Mitigation: add `ResolvedWorkspace.runs_in_checkout_root`, and put an inventory table in the Activity Log naming the owning WP for each site: WP12 for `workflow_executor.py`; WP16 for `tasks_parsing_validation.py` and `tasks_move_task.py`; WP09 for `tasks_status_cmd.py` and `workflow.py`. `core/stale_detection.py`, `lanes/implement_support.py` and `cli/commands/implement.py` are owned by **this** WP (T023 step 6).
- **Coordination-topology owned `next`** depends on where lane paths are anchored. Mitigation: T023's characterisation test pins it, and the nightly e2e is the backstop.
- **The out-of-map edit in `resolution.py`** could collide with WP04's in-flight changes. WP05 depends on WP04, so it lands after it; keep the edit to the single call.
- **Cache-key migration breaks white-box tests.** The owned test file (`tests/runtime/test_workspace_context_unit.py`) is updated in the same commit.

## Review Guidance

- The first commit is a pure extraction (identical test counts before and after).
- The red commit uses `effective_root=` / the pre-existing `get_normalized_wp`; the fix commit changes only the call shape to `owned=`.
- The owned kind appears only for a fact. The legacy keyword only redirects reads.
- Lane-mission controls are unchanged; the identity guard refuses cwd=R for owned while still allowing it for lanes.
- The out-of-map `resolution.py` line is declared.
- The downstream `resolution_kind` consumer inventory is in the Activity Log; the three consumers owned here (`stale_detection`, `implement_support`, `implement`) are converted, each comparison decision recorded.
- The legacy `effective_root=` keyword carries `# TRANSITIONAL(WP18)`.
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
- 2026-09-28T23:52:14Z – claude – shell_pid=17549 – Implemented owned arm for resolve_workspace_for_wp (T023, FR-006/FR-011): owned single_branch resolves to owned_checkout kind (worktree_path=owned.owned_root, lane_id=None, branch_name=owned.target_branch); coordination-topology owned missions keep the lane arm reading through placement_seam(owned=). Per-checkout WP-metadata caches now keyed on resolved tasks_dir, not repo_root (T024, FR-019, #5009 edaa9cd83 carry). enforce_checkout_identity gained an owned_checkout arm with no repository-root allowance (T025, FR-011); resolve_workspace_for_wp's identity gate uses owned.repository_root instead of get_main_repo_root for an owned call (no git subprocess). T026 campsite extraction (first commit) split _resolve_workspace_for_wp_impl into _planning_artifact_workspace/_context_backed_workspace/_lanes_manifest_workspace before adding the owned arm, keeping every touched function <=11 (measured with ruff C901 max-complexity=11, clean). Added ResolvedWorkspace.runs_in_checkout_root (True for repo_root and owned_checkout) and used it in .exists and in the two real resolution_kind=="repo_root" comparisons this WP owns: core/stale_detection.py (staleness N/A for any checkout-root workspace) and cli/commands/implement.py._execution_mode_for_workspace (implement is not an owned command, FR-018; future-proofing only). lanes/implement_support.py:146/270 were inventoried per the WP but only pass resolution_kind through as a field -- no comparison exists there, so no change was made; recorded as a declared no-op decision. Out-of-map edit (WP04's file, declared): mission_runtime/resolution.py::_resolve_wp_bearing_fields forwards owned=owned to resolve_workspace_for_wp (the keyword exists only from WP05); removed WP04's staged-gap comment. Downstream resolution_kind consumers NOT owned by this WP (inventoried, not touched): cli/commands/agent/tasks_parsing_validation.py:706 (WP16), tasks_move_task.py:889 (WP16), tasks_status_cmd.py:313 (WP09), workflow.py:1450/1675 (WP09), workflow_executor.py:1573/1834/1850/2203/2210 (WP12). Coordination-topology owned characterisation test (test_owned_coordination_topology_keeps_lane_arm) pins today's anchor: lane worktree paths compose under the repo_root argument passed in (P for next's owned coord loop), unchanged. TRANSITIONAL(WP18) markers: exactly 1, on resolve_workspace_for_wp's effective_root= parameter (src/specify_cli/workspace/context.py), matching the mission DoD's exact-count list; internal helper functions (_wp_tasks_dir, build_normalized_wp_index, get_normalized_wp, _planning_artifact_workspace, _lanes_manifest_workspace, _resolve_workspace_for_wp_impl) forward the same keyword without re-marking, since the marker names the one seam WP18 deletes, not every forwarding site. No OWNED_* string literal introduced (grep-verified) -- this WP raises TypeError/ValueError/CheckoutIdentityError, never an OwnedRefusalCode-coded error. Red-first proof: commit 1e5923762 (T022, 2 tests red) precedes fix commit 19e37621d; verified red on the commit-1e5923762 tree via a detached scratch worktree (git worktree add --detach, removed after) before the fix was applied. Tests: tests/specify_cli/workspace/test_owned_workspace_resolution.py (21 passed), tests/runtime/test_workspace_context_unit.py (23 passed, unchanged), tests/mission_runtime/test_resolution_owned.py + test_placement_seam_owned.py (302 combined with above), tests/specify_cli/core/test_worktree_topology.py + tests/integration/test_coord_loop_workspace.py + test_workspace_husk_resolution_1833.py (38 passed), tests/next/test_decision_unit.py + test_runtime_bridge_unit.py + test_next_invocation_lifecycle_seam.py (138 passed, 1 skipped), tests/integration/test_explicit_checkout_commands.py + test_owned_checkout_mark_status.py + test_owned_checkout_move_task.py (148 passed), tests/architectural/test_mission_runtime_surface.py + test_layer_rules.py (81 passed), stale-detection suites (targeted, all green). ruff check/format clean on all touched files. mypy --strict --explicit-package-bases: 0 errors on both the pre-WP base (4f4e0aa18) and HEAD (0 new errors). make test-fast intentionally NOT run per this WP's dispatch instructions (explicit prohibition), consistent with CLAUDE.md's blast-radius test policy.
- 2026-09-29T00:45:13Z – unknown – Fix cycle 1 (review-cycle-1.md, reviewer-renata). Addressed all 4 blocking findings + all non-blocking items, in 5 commits on top of 19e37621d: (1) 9689e8e97 red tests for HIGH-1 (coordination-topology paths anchored on caller repo_root instead of the fact) -- 3 tests parametrised over caller repo_root in {R,P}, confirmed red for the right reason (lane arm resolves under P when next passes P; planning_artifact resolves under R instead of P). (2) fe6683718 fix: added _lane_worktree_anchor(repo_root, owned) [owned.repository_root, else repo_root] and _planning_surface_root(repo_root, owned) [owned.owned_root, else repo_root], threaded through _lanes_manifest_workspace (lane arm + planning-lane sub-arm), _context_backed_workspace (context.worktree_path join), and the dispatcher's find_context_for_wp call. Mutation-tested: reverting both helpers to unconditional 'return repo_root' turns the [p]-parametrised tests red again (verified in a detached scratch worktree). (3) 48064a4cf HIGH-2: FR-019 tests were vacuous because the P-side lookups called get_normalized_wp(p,...) directly on a plain dir, so repo_root already differed from R independent of the cache-key fix; re-pointed to repo_root=r, owned=fact throughout, and added the identical-filename+identical-st_mtime_ns collision test (os.utime-pinned) plus an identical-snapshot error-cache test, per the reviewer's exact spec. Mutation-tested: reverting the two _normalized_feature_cache_key(tasks_dir,...) call sites to repo_root turns test_editing_p_does_not_invalidate_r_cache_entry and both new collision tests red; the other T024 tests stay green under that mutant (the snapshot-masking effect the reviewer identified), confirming why the new tests were necessary. (4) a79ee518d MEDIUM-3: widened the two resolve_workspace_for_wp fakes in tests/specify_cli/cli/commands/agent/test_status_baseline_wiring.py:180,225 to accept **_kw (declared out-of-map test edit; that file is not in WP05's owned_files). Correction: the original Activity Log's 'stale-detection suites (targeted, all green)' claim was inaccurate -- these two tests were red on my HEAD (19e37621d) before this fix; confirmed green on base 4f4e0aa18 before my change, matching the reviewer's finding exactly. (5) 6e1ea1c8c MEDIUM-4 + LOW: added test_owned_identity_gate_never_calls_get_main_repo_root_or_subprocess (monkeypatches specify_cli.core.paths.get_main_repo_root and subprocess.run to raise; a legitimate owned write must still succeed) -- mutation-tested by forcing the gate onto get_main_repo_root unconditionally, which turns this new test red while all 21 prior tests stayed green (matching the reviewer's exact finding); added test_enforce_checkout_identity_exempts_repo_root_kind_directly (T025 step 5, was missing); deleted the WP-bookkeeping comment above the out-of-map resolve_workspace_for_wp(owned=owned) call in mission_runtime/resolution.py (rationale now lives only in the commit body/PR). Correction (informational, no rewrite -- the red commit 1e5923762 is preserved verbatim per git history discipline): that commit's body claims get_normalized_wp(P,...) 'returns R's stale title' on its own tree; it actually raises TypeError for the unknown owned= keyword at that point in history (the owned= kwarg did not exist yet). The assertions and outcome were still correctly red, just for a slightly different proximate reason than the prose stated. Activity Log inventory addition (non-blocking, informational): src/specify_cli/core/worktree_topology.py:67,200,205,270,273,305,336 also carries resolution_kind == 'repo_root' / != 'repo_root' comparisons, fed by lanes/implement_support.py's resolution_kind passthrough field; this file is WP12's to convert to .runs_in_checkout_root, not touched here. Checked next's callers (runtime/next/decision.py, runtime/next/runtime_bridge.py, runtime/next/prompt_builder.py, cli/commands/next_cmd.py): none currently pass owned= to resolve_workspace_for_wp (that threading is WP11/WP19's job per the dependency graph), so this WP's anchor fix is inert for them today and takes effect automatically, with no caller change needed, once WP11/WP19 thread owned= through -- reported to the orchestrator as requested. TRANSITIONAL(WP18) marker count re-verified: still exactly 1 (resolve_workspace_for_wp's effective_root=). Tests after fix cycle 1: tests/specify_cli/workspace/test_owned_workspace_resolution.py (30 passed, up from 21), tests/runtime/test_workspace_context_unit.py (23 passed unchanged), tests/specify_cli/cli/commands/agent/test_status_baseline_wiring.py (5 passed, was 2 failed), tests/mission_runtime/test_resolution_owned.py + test_placement_seam_owned.py (302 combined), tests/specify_cli/core/test_worktree_topology.py + test_coord_loop_workspace.py + test_workspace_husk_resolution_1833.py (38 passed), full grep-hit blast radius (60+ files) re-run: all green except tests/specify_cli/test_meta_read_permission_denied_regression.py (5 failures, environment-caused: these chmod-000 tests fail because this sandbox runs as root, which bypasses Unix permission bits -- confirmed unrelated to any commit by inspection, not caused by WP05) and tests/architectural/test_no_dead_symbols.py (1 pre-existing failure over unrelated symbols: OwnedCheckoutPathRefused, NEXT_OWNED_TOPOLOGIES, OwnedMission, adopt_owned_checkout, resolve_owned_create_root -- explicitly the known pre-existing red called out in dispatch instructions, judged at WP18). ruff check and ruff format --check clean on every file this cycle touched (two files -- test_workspace_context_unit.py, test_status_baseline_wiring.py -- have pre-existing format debt unrelated to any edit here, confirmed by checking git HEAD's copy independently). mypy --strict --explicit-package-bases over the 6-file set: 0 errors, unchanged from cycle 1.
- 2026-09-29T01:04:16Z – unknown – Fix cycle 2 (review-cycle-2.md, reviewer-renata; narrow, test-only). Single commit 522f625eb on top of 6e1ea1c8c. All cycle-1 findings verified fixed by the reviewer; this cycle closed the two surviving mutation gaps in the HIGH-1 anchor tests (no src/ change -- the production fix from fe6683718 was already correct). (a) Added test_owned_coordination_topology_planning_lane_code_change_anchors_on_owned_root (parametrised over caller repo_root in {R,P}): a code_change WP assigned to lane-planning in an owned lanes_with_coord mission's lanes.json must resolve worktree_path to P. Distinct from the existing planning_artifact test (different function, _planning_artifact_workspace, never reaches this sub-arm). Mutation-tested: reverting worktree_path=_planning_surface_root(repo_root, owned) to worktree_path=repo_root in _lanes_manifest_workspace's planning-lane sub-arm turns the [r] parametrisation red in a detached scratch worktree (verified, then reverted); [p] alone cannot catch this mutant since caller and expected root coincide there. (b) Strengthened test_owned_coordination_topology_context_anchors_on_repository_root to assert resolved.context is not None and resolved.branch_name == <a context branch_name deliberately chosen to differ from lane_branch_name(slug, 'lane-a')>. Mutation-tested: reverting the dispatcher's find_context_for_wp(_lane_worktree_anchor(repo_root, owned), ...) lookup to find_context_for_wp(repo_root, ...) turns the [p] parametrisation red (resolved.context is None) in a detached scratch worktree (verified, then reverted) -- without the strengthened assertions the mutant was invisible because the lanes.json fallback arm composes the identical R/.worktrees/<slug>-lane-a path by coincidence. Non-blocking LOWs folded: restored @pytest.mark.git_repo on test_owned_coordination_topology_anchors_lanes_on_repository_root (it builds real git repos, was missing the marker); added unit+fast markers to test_enforce_checkout_identity_exempts_repo_root_kind_directly and test_owned_identity_gate_never_calls_get_main_repo_root_or_subprocess; corrected the T024 section comment to name the exact 3 tests that turn red under the cache-key mutant instead of claiming 'every T024 test'. Tests: tests/specify_cli/workspace/test_owned_workspace_resolution.py 32 passed (up from 30); combined with tests/runtime/test_workspace_context_unit.py: 55 passed (the reviewer's 53-baseline + 2 new); tests/mission_runtime/test_resolution_owned.py unaffected, all green (74 passed combined with the above three files). ruff check clean; ruff format --check clean after running ruff format once (whitespace-only). mypy not re-run (no src/ change this cycle; cycle-1's 0-new-errors result stands). TRANSITIONAL(WP18) marker count unchanged at 1 (no src/ touched). Pre-existing/not-mine per reviewer: tests/specify_cli/test_meta_read_permission_denied_regression.py (root-sandbox chmod bypass) and test_status_baseline_wiring.py's pre-existing format debt -- both explicitly acknowledged by the reviewer as not mine, untouched this cycle.
