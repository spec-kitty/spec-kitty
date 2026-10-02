---
work_package_id: WP07
title: Transactional status writers and the tasks-port write location
dependencies:
- WP05
requirement_refs:
- FR-003
- FR-003a
- FR-007
- C-008
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T17:51:10.342611+00:00'
subtasks:
- T037
- T038
- T039
- T040
- T041
- T042
phase: Phase 3 - Writer migration
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/status_transition.py
create_intent:
- tests/coordination/test_status_transition_write_dir.py
- tests/lanes/test_recovery_write_dir.py
- tests/specify_cli/test_agent_tasks_ports_write_dir.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/coordination/status_transition.py
- src/specify_cli/coordination/transaction.py
- src/specify_cli/lanes/recovery.py
- src/specify_cli/agent_tasks_ports.py
- tests/coordination/test_status_transition_write_dir.py
- tests/lanes/test_recovery_write_dir.py
- tests/specify_cli/test_agent_tasks_ports_write_dir.py
- tests/mission_runtime/test_coord_read_seam_callers.py
- tests/architectural/test_no_read_side_bypass.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Transactional status writers and the tasks-port write location

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Move the **status-transition writer family** (move-task's transactional path, the bookkeeping transaction, lanes crash recovery, and the tasks-port write dir) off read resolvers and private composers, onto the single write-location accessor `PlacementSeam.write_dir(STATUS_STATE)` (delivered by WP03/WP04).

Done means:

- For a coordination-routed Mission (`coord` / `lanes_with_coord`, owned or not), every status event written by `move-task`, `BookkeepingTransaction`, and `lanes/recovery.reconcile_status` lands in **one** status log on the coordination surface, in every reachable coordination-worktree state:
  - UNMATERIALIZED with a local branch: the worktree is materialized first, and the event lands there (US2.3). It never lands in the repository root checkout.
  - EMPTY, pre-fix: the root records are carried over once (the seed), the event is appended after them, and the logical clock continues (US2.4/2.5).
  - Remote-only branch (fresh clone): the write is refused before anything is written, with a recovery hint (US2.3, #4970 parity).
  - DELETED branch: the write is refused loudly with a recovery hint (US2.8).
  - MATERIALIZED but forked (#5519 shape): writes go to the coordination surface with no lockout (US2.6).
- `status_transition._coord_feature_dir` and the inline composition in `transaction.py` (≈L489-490) are gone. No second composer of the coordination Mission dir remains in these files.
- `CommitArtifactResult` carries `surfaces` (passthrough from `CommitRouterResult.surfaces`, WP05). The tasks-port consumers render it in WP08.
- `lanes` / `single_branch` Missions behave byte-identically (C-008).

## Context & Constraints

- **Spec**: FR-003 (one write-location accessor, writer families "status transitions: move-task, mark-status, and the transactional status path's own coordination-directory composition" and "lanes recovery"); FR-003a (establish or refuse loudly); FR-007 (tasks-port commit wrapper carries per-surface outcomes); C-008; US2.2, US2.3, US2.4, US2.5, US2.6, US2.8; edge case "Seeding must be atomic".
- **Plan**: IC-04 (writer census rows "Status transitions", "Transactional status path", "Lanes recovery"), IC-07 (wrapper `CommitArtifactResult`).
- **Research**: D1 (accessor shape), D2 (seed lock ordering: the workspace lock may nest under the status lock; `BookkeepingTransaction.acquire` already takes the status lock at transaction.py:292 before composing at ≈L465-490), D8 (CommitArtifactResult gains `surfaces`).
- **Contracts**: `contracts/write-location-accessor.md` (postconditions table, errors), `contracts/seed.md`, `contracts/commit-outcome.md`.
- **Data model**: §2 (`WriteLocation`, per-`CoordState` handling), §3 (I-SEED-1/2 lock invariants), §7 (status transition atomicity is unchanged).
- **Upstream WPs you build on**: WP03 (`establish_coord_write_location`, `WriteLocation`, seed), WP04 (`PlacementSeam.write_dir`), WP05 (`CommitRouterResult.surfaces`, `SurfaceOutcome`), WP02 (fixture builders in `tests/_factories/coord_mission.py`).
- Load the charter (`.kittify/charter/charter.md`) and `spec-kitty charter context --action implement --json` before you start.
- **Model discipline**: implement with sonnet (`claude-sonnet-5`); review with opus.
- **Terminology**: write "Mission", never "feature", in user-facing text and new docstrings. Name the sense of "primary" you mean: the PRIMARY partition, the repository root checkout, or the target branch.
- **C-006**: run no full heavy suites (see Targeted test surface).
- **Fixture semantics across lanes (post-tasks squad P-m5):** pre-fix assertions use WP02's `make_prefix_coord_mission`; `make_coord_mission` carries only shape-agnostic invariants (its shape changes when WP06 lands); use `make_coord_mission(..., materialized=True)` when a test needs a deterministic MATERIALIZED coordination surface in every lane.
- **Brownfield scout (binding read)**: before coding, read `## WP07` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp01-11.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- `finalize-tasks` allocates execution worktrees per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP07 --agent claude`, and use the workspace path it prints. Never reconstruct the path yourself.
- **Lane notes**: this WP's ownership is disjoint from every other WP, so it gets its own lane. It depends on WP05 (lane A), so your lane base already contains WP01/WP03/WP04/WP05. WP08 depends on this WP and reads `CommitArtifactResult.surfaces`.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T037 – Red-first: move-task status writes across coordination-surface states

- **Purpose**: Pin the user-observable contract through the pre-existing entry point *before* any fix: the `spec-kitty agent tasks move-task` CLI on a coordination-routed Mission (charter ATDD-First, C-005, ADR 2026-07-17-1). Commit these tests as their own commit, before T038.
- **Steps**:
  1. Create `tests/coordination/test_status_transition_write_dir.py`. Build fixtures with WP02's `tests._factories.coord_mission` builders (`make_coord_mission`, `make_prefix_coord_mission(worktree="absent"|"empty", remote_only=..., branch_deleted=...)`, and the fork builders). Parametrize over `coord` and `lanes_with_coord`.
  2. Drive the transition through the CLI (`typer.testing.CliRunner` against the real app, or a subprocess call to `spec-kitty agent tasks move-task WP01 --to claimed --mission <slug> --json`; follow what neighbouring move-task tests do). The Mission needs a WP file and a finalized lane manifest, so reuse the existing move-task fixture helpers (grep `tests/` for `move-task` / `move_task` fixtures; `tests/integration/test_coord_loop_tasks.py` shows a coord-loop flow).
  3. Scenarios and assertions:
     - **UNMATERIALIZED + local branch** (worktree removed): after the call, the coordination worktree exists, `<coord wt>/kitty-specs/<dir>/status.events.jsonl` holds the new event, and the repository root checkout's log did NOT gain it (compare event ids before and after).
     - **Pre-fix EMPTY** (root log holds MissionCreated/SpecifyStarted, coordination branch lacks the Mission dir): the coordination log = root events + the new event. `event_lamport` is strictly greater than every carried event. The coordination branch carries exactly one seed commit (`chore(<mission>): seed coordination surface`). The root copy is restored (`git status --porcelain` clean for that path).
     - **Second move-task** after the seed: nothing is re-carried, and no event id appears twice (`len(ids) == len(set(ids))`).
     - **Remote-only branch**: non-zero exit; the error names `COORDINATION_WORKTREE_UNMATERIALIZED` (or its rendered hint) and a recovery command. No file changed on either surface (snapshot `git status --porcelain` plus the log bytes before and after).
     - **DELETED branch**: non-zero exit with `COORDINATION_BRANCH_DELETED` and a hint. Nothing written.
     - **MATERIALIZED-forked (#5519 shape, fork builder (a))**: the move-task succeeds and the event lands on the coordination log. There is no `COORD_SEED_FORK_REFUSED` lockout (the seed only runs on EMPTY).
  4. Run them on your lane base, before any product change, and confirm they are RED for the right reason. At base the UNMATERIALIZED/EMPTY cases write into the root checkout via `resolve_feature_dir_for_mission` / `_coord_feature_dir`. Record the red output in the Activity Log.
- **Files**: `tests/coordination/test_status_transition_write_dir.py` (new).
- **Validation**: each red assertion fails on the defect, not on fixture plumbing. If the fixture itself errors, fix the fixture first.
- **Edge cases**: the remote-only fixture needs a bare remote with the branch and no local branch. Make sure `origin/HEAD` exists so primary-branch detection doesn't fall back (CLAUDE.md "Create-time topology" caveat). Some cases may already be green at base (DELETED refusal may already refuse); keep them as controls and say so in the log.
- **Post-fix EMPTY row (post-tasks squad R-m3)**: build a **post-fix** Mission through WP03's real seed (round 5, X2): `make_prefix_coord_mission(worktree="empty")`, then `placement_seam(...).write_dir(STATUS_STATE)` → SEEDED with the `Spec-Kitty-Coordination-Seed` trailer. ~~(WP02 `materialized=True`)~~ is struck: it is pre-fix-shaped, with no trailer. Then remove the coordination Mission dir in the worktree, run `move-task`, and assert: a loud WARNING is emitted; the dir is restored from the branch tip (`RESTORED_FROM_BRANCH`); the event lands there; nothing is written to the repository root checkout.

### Subtask T038 – `status_transition.py`: retire the private coordination-dir composer

- **Purpose**: `_coord_feature_dir` (status_transition.py:400) composes `coord_worktree / KITTY_SPECS_DIR / _transaction_dir_name(slug, mid8)`, and `_resolve_fallback_coord_worktree` (L241) materializes via `CoordinationWorkspace.resolve` but is blind to EMPTY (no seed). Contract: "No second composer remains."
- **Steps**:
  1. Read L241-300, L395-410 and `_emit_on_coord_then_commit` (L475-537). Find every caller of `_coord_feature_dir` and `_resolve_fallback_coord_worktree` (`grep -n "_coord_feature_dir\|_resolve_fallback_coord_worktree" -r src/`).
  2. Replace the derivation of the coordination Mission dir with `placement_seam(repo_root, mission_slug, owned=...).write_dir(MissionArtifactKind.STATUS_STATE)`. Use `.path` for the dir, and `.surface == "coordination"` where today's code branches on "coord-routed". Keep the SHAPE decision (`_read_contract_routes_through_coordination`, the stored-topology SSOT): a coord-less topology must still return the PRIMARY write (contract row 8). `write_dir` already returns PRIMARY there, so prefer delegating fully.
  3. Map the accessor's errors onto today's fail-loud surface. `FallbackCoordWorktreeUnresolved` stays the outward exception if callers or tests match on it. Wrap the accessor's `CoordinationWorktreeUnmaterialized` / `CoordinationBranchDeleted` / `CoordSeedForkRefused` / `FeatureStatusLockTimeoutError` into it, or let them propagate where the caller already renders them. Choose the narrower change and document it in the docstring. Never catch broad `Exception`.
  4. Delete `_coord_feature_dir` once it has no callers. If a test imports it (grep `tests/`), re-point that test to the accessor (one-line rationale in the log).
  5. Leave `_emit_on_coord_then_commit` byte-identical (data-model §7).
- **Files**: `src/specify_cli/coordination/status_transition.py`.
- **Validation**: T037's UNMATERIALIZED/EMPTY cases turn green for the transactional path. `tests/specify_cli/coordination/test_status_transition_adoption.py`, `test_coord_dir_seam.py` and `test_coord_fallback_lock_bound.py` stay green (re-pin only a stale assertion that pinned the composer itself, with rationale).
- **Edge cases**: `write_dir` may seed, and seeding takes the reentrant status lock. If this call site already holds the status lock (check the call stack), reentrancy covers it. If it holds the *workspace* lock, you would invert I-SEED-2. Verify that it doesn't.
- **Pinned pre-fix callers (post-tasks squad P-M1)**: `tests/mission_runtime/test_coord_read_seam_callers.py` (≈L198, ≈L259) pins today's pre-fix writer behaviour. Both this WP and WP09 flip it. This WP owns the file and re-pins it, and WP09 depends on this WP, so the two never edit it concurrently. Re-pin with a one-line rationale per assertion.
- **Out-of-map edit, declared (P-M1)**: `tests/coordination/test_commit_router.py` (≈L953, ≈L1012) imports `status_transition._coord_feature_dir`, which this WP deletes. Update those two tests to the `write_dir` successor. Rationale: the symbol this WP removes; the file belongs to WP01/WP05 (lane A), which is complete before this WP starts (dependency WP05), so there is no concurrent edit. Record it in the activity log.
- **`WriteLocation.checkout_root` (post-tasks squad P-M3):** take the checkout root from `write_dir(kind).checkout_root` (WP03/WP04). Never derive it as `.path.parent.parent` or by guessing a worktree name. `test_no_worktree_name_guess.py` does not police `.parent.parent` (#2007); WP20 extends `test_no_write_side_rederivation.py` to enforce this, so until then review checks it.

### Subtask T039 – `transaction.py`: `_acquire_locked` uses `write_dir` under the held status lock

- **Purpose**: `BookkeepingTransaction._acquire_locked` (transaction.py:317) resolves the worktree via `CoordinationWorkspace.resolve` (≈L465) and composes `worktree_root / KITTY_SPECS_DIR / _mission_specs_dir_name(...)` at ≈L489-490. That is the second composer, and it is blind to EMPTY: the first transactional write on an EMPTY pre-fix surface creates the Mission dir and forks the log.
- **Steps**:
  1. `acquire` (L237) takes `feature_status_lock(lock_root, _mission_specs_dir_name(slug, mid8))` at L292 and then calls `_acquire_locked`. Inside it, replace the coord arm's worktree resolution + composition with `write_dir(STATUS_STATE)`. Derive `worktree_root` as the coordination worktree root containing `.path` (do not re-compose `kitty-specs/<dir>`; `.path.parent.parent` is acceptable only if `write_dir` guarantees that shape, so assert it with a clear error), and set `feature_dir = location.path`.
  2. Keep the legacy-lane arm and the coordination-less arm (`worktree_root = repo_root`, the #3371 guard) unchanged. Only the "new topology" coord arm changes.
  3. Lock order (I-SEED-2): the status lock is held, so `write_dir` → materialize takes the workspace lock nested under it. That is the order the transaction already uses, so it is allowed. The seed re-enters the reentrant status lock (`machine_file_lock(..., reentrant=True)`). Add a test that proves no deadlock: run a transaction on an EMPTY pre-fix Mission with a short lock timeout.
  4. Dir-name agreement: `_mission_specs_dir_name(slug, mid8)` / `_transaction_dir_name` (`<slug>-<mid8>` vs `<slug>`) must equal `write_dir(...).path.name`. Add an assertion test for a slug that embeds the mid8 and one that does not.
  5. Keep the `BookkeepingWorktreeMissing` error type for resolution failures callers already handle. Map the accessor's refusal errors into it, or let them propagate per the same rule as T038.
- **Files**: `src/specify_cli/coordination/transaction.py`.
- **Validation**: T037 green via the transactional path. Existing transaction tests stay green (`grep -rl "BookkeepingTransaction" tests/ | head` and run those files).
- **Edge cases**: the comment at ≈L486 says the lock is held "only to serialize first-time coord worktree setup". Keep that intent. `write_dir` on MATERIALIZED must be side-effect-free, so a steady-state transaction adds no git calls beyond the probe. Check the probe cost: no extra `git worktree add`.

### Subtask T040 – `agent_tasks_ports.py`: kind-aware write dir, and `CommitArtifactResult.surfaces`

- **Purpose**: `RealCoordCommitRouter.feature_write_dir` (agent_tasks_ports.py:354-362) returns kind-blind `resolve_feature_dir_for_mission` for non-owned handles. That is the move-task / mark-status write leg. `CommitArtifactResult` (L108) drops `commit_hashes`, `reason`, and now `surfaces`.
- **Steps**:
  1. Change `feature_write_dir` to `placement_seam(mission.repo_root, mission.mission_slug, owned=mission.owned).write_dir(MissionArtifactKind.STATUS_STATE).path` for both owned and non-owned handles. The owned arm today uses `read_dir(STATUS_STATE)` via `_placement_for(mission)`, so reuse that helper and switch it to `write_dir`. If the protocol needs a kind parameter (`feature_write_dir(mission, kind=STATUS_STATE)`), add it with a default so existing callers stay valid. Update the fake/protocol at L164 to match.
  2. Remove the now-unused `resolve_feature_dir_for_mission` import if nothing else in the module uses it (ruff will tell you).
  3. Add `surfaces: tuple[SurfaceOutcome, ...] = ()` to `CommitArtifactResult` (frozen dataclass, additive, last field with a default). In `commit_artifact` (L373-405) pass `surfaces=result.surfaces`. Also carry `commit_hashes` and `reason` if WP05's contract exposes them. Import `SurfaceOutcome` from `specify_cli.coordination.commit_outcome` (WP05).
  4. Do not render anything here. Rendering is WP08's job, at the consumers.
- **Files**: `src/specify_cli/agent_tasks_ports.py`; tests in `tests/specify_cli/test_agent_tasks_ports_write_dir.py` (new).
- **Validation**: a unit test with a fake `commit_fn` returning a `CommitRouterResult` with two surfaces sees both on `CommitArtifactResult.surfaces`. `feature_write_dir` on an EMPTY pre-fix Mission returns the coordination dir and seeds. On `lanes` it returns the same path as before (C-008).
- **Edge cases**: the C-001 byte-parity comments around `_thread_target_branch` / `_owned_kwargs` must keep their call shapes. Don't alter the kwargs passed to `commit_fn`.

### Subtask T041 – `lanes/recovery.py`: `reconcile_status` writes through the accessor

- **Purpose**: `reconcile_status` (recovery.py:766) computes `feature_dir = resolve_feature_dir_for_mission(repo_root, mission_slug)` at L785 and feeds it to `emit_status_transition_transactional` (L807). The "KEEP coord-aware" comment there is the defect class: the resolver substitutes the root checkout on EMPTY.
- **Steps**:
  1. Replace L785 with `placement_seam(repo_root, mission_slug).write_dir(MissionArtifactKind.STATUS_STATE).path`, imported lazily inside the function as the module already does for the status imports.
  2. Rewrite the comment above it: the write location comes from the one accessor, and the read resolver is never a write location (FR-014).
  3. Decide the refusal behaviour. Recovery is best-effort and runs from `implement` crash recovery, so let a remote-only/DELETED refusal propagate with its recovery hint rather than silently skipping. Look at how callers of `reconcile_status` handle exceptions and keep their contract. If they swallow, add a WARNING log naming the code.
  4. Leave the module-level `resolve_feature_dir_for_mission` import (L15) in place if other functions in the file use it for reads.
- **Files**: `src/specify_cli/lanes/recovery.py`; tests in `tests/lanes/test_recovery_write_dir.py` (new).
- **Validation**: a pre-fix EMPTY Mission with a WP branch that has commits (`RecoveryState(has_commits=True)`) → `reconcile_status` returns the emitted count, and the `in_progress` events are on the coordination log. Root restored, exactly one seed commit.
- **Edge cases**: `lanes` topology: the same root path as before (C-008 control).

### Subtask T042 – C-008 controls, lock-reentrancy and no-residue tests

- **Purpose**: Close the WP with the controls that keep the migration honest (DIRECTIVE_041: tests fail exactly when the contract is violated).
- **Steps**:
  1. **C-008**: parametrize T037's happy path over `lanes` and `single_branch`. Assert the event file path and the commit ref are byte-identical to a recording taken at your lane base: compute the expected path the old way in the test and compare.
  2. **Reentrancy**: hold `feature_status_lock(...)` in the test, then call a transactional emit that triggers a seed. It must complete within the timeout, with no `STATUS_LOCK_HELD`.
  3. **Contention**: a different process (or a thread with a non-reentrant hold, if the kernel lock supports it in tests) holds the status lock. The write fails with `STATUS_LOCK_HELD` (WP03's `error_code`), and nothing is written.
  4. **No residue**: after every coord move-task scenario, the repository root checkout's Mission dir has no new untracked or modified COORD file (`git status --porcelain -- kitty-specs/<dir>`).
  5. Move any transitional reproduction assertions into these owning-module files. Do not leave standalone regression-marker files (FR-016).
- **Files**: the three new test files.
- **Validation**: the full WP test set is green, and coverage of the changed lines is ≥ 90%.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **`_coord_feature_dir`**: its only production caller is `_emit_on_coord_then_commit` (`status_transition.py:492`). Editing that function is expected; keep its order of operations identical.
- **`_acquire_locked`**: the L489-490 composition is shared by **four** arms (legacy lane, coordination-less, `commit_to_primary_target`, coordination). Only the **coordination arm** switches to `write_dir`; the other three stay byte-identical (C-008). Do not delete the composition outright. Extract the coordination arm (C901 is 9).
- **No `.path.parent.parent`** (P-M3). `test_no_write_side_rederivation.py`'s `root_walk` already flags it in `status_transition.py`. Use `WriteLocation.checkout_root`.
- **Owned root**: inside `_acquire_locked`, build `placement_seam` from `owned.repository_root` plus `owned=`, never from the inner lock `repo_root` (`transaction.py:291/300`).
- **T040**:
  - do **not** add a `kind` parameter to `feature_write_dir`; 14 test fakes implement the 1-argument protocol. It returns `write_dir(STATUS_STATE).path`.
  - Its callers are `tasks_move_task.py:558` and `tasks_mark_status.py:227` (owned arm only). The non-owned mark-status write uses `resolve_status_surface(...).parent` (`tasks_mark_status.py:231`) and is fixed in WP08.
  - The result also feeds `check_pre30_layout` (L560) and `_read_transactional_wp_lane` (L571).
- **T041**: `placement_seam` and `MissionArtifactKind` are already module-level imports in `lanes/recovery.py:12`. Remove the now-unused `resolve_feature_dir_for_mission` import (F401).
  - The per-emit `try/except Exception: break` (L819) swallows refusals; log them and surface them in the recovery report instead of silently breaking.
- **`_resolve_fallback_coord_worktree`**: keep its name and signature, because unowned tests depend on it (`tests/coordination/test_status_write_authority.py` L130/186-190/236/267; `tests/specify_cli/coordination/test_plain_door_semantics.py:143-150`). Delegate its coordination composition to `write_dir` internally.
- **Sanctioned read-side residual**: `_read_contract_from_transaction_target` (L1357-1368) composes `worktree_path / KITTY_SPECS_DIR / _transaction_dir_name`. Record it in the activity log as sanctioned, so the reviewer's grep does not bounce the WP.
- **Stale allow-list (operator decision; now owned)**: in `tests/architectural/test_no_read_side_bypass.py`, delete the entries for `agent_tasks_ports.py::RealCoordCommitRouter.feature_write_dir` and `lanes/recovery.py::reconcile_status`; otherwise the twin `test_allow_list_entry_is_still_a_live_finding` goes red. This WP is the file's single owner. WP10 depends on this WP and removes its own tracer entry afterwards as a declared out-of-map edit.
- **`test_coord_read_seam_callers.py`**: this WP re-pins L259. WP09 now co-owns the file (it depends on this WP; same lane) and re-pins L198 (the decision test) together with its own fix. **Do not re-pin L198 here**: decisions are not migrated at this WP's tip. L346 (single-branch guard) stays green.
- Run `tests/specify_cli/coordination/test_transaction.py` by name. Its `MISSION_SLUG="demo-feature"` has no mid8, which exercises the dir-name agreement (T039).
- **Gate citation fix**: `test_no_worktree_name_guess.py` is not the P-M3 guard (it excludes `.parent.parent`, deferred #2007); WP20 adds the real one.

## Targeted test surface

- New: `tests/coordination/test_status_transition_write_dir.py`, `tests/lanes/test_recovery_write_dir.py`, `tests/specify_cli/test_agent_tasks_ports_write_dir.py`.
- Owning-module tests (run by file): `tests/specify_cli/coordination/test_status_transition_adoption.py`, `test_coord_dir_seam.py`, `test_coord_fallback_lock_bound.py`, `test_851_acquire_composition.py`, `test_coord_topology_states.py`, `test_status_surface_owned.py`; `tests/coordination/test_status_write_authority.py`, `test_materialize_coord_surface.py`; every file `grep -rl "BookkeepingTransaction\|reconcile_status\|feature_write_dir\|CommitArtifactResult" tests/` returns.
- Subsystem dirs: `tests/specify_cli/coordination/`, `tests/coordination/`, `tests/lanes/`, `tests/status/` (fast tier).
- Baseline: `make test-fast`.
- Named architectural gates only: `tests/architectural/test_no_write_side_rederivation.py` (it must not regress; WP20 extends it later), `tests/architectural/test_status_events_writes_gate.py`, `tests/architectural/test_status_state_read_dir_single_authority.py`, `tests/architectural/test_layer_rules.py`.
- Example: `uv run --frozen pytest tests/coordination/test_status_transition_write_dir.py tests/lanes/test_recovery_write_dir.py tests/specify_cli/test_agent_tasks_ports_write_dir.py -q`.
- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006). Record commands and pass/fail counts in the Activity Log for the PR's *Tests run* section.
- Before you treat a red as yours, classify it with CLAUDE.md's baseline-red gotcha: pre-existing P0, CI-environment, stale install, or stale venv (`uv sync --frozen --all-extras`).
- Post-tasks squad additions, by name: `tests/mission_runtime/test_coord_read_seam_callers.py`, `tests/coordination/test_commit_router.py` (the two re-pointed tests), `tests/architectural/test_no_read_side_bypass.py` (now owned).

## Quality gates

- Keep C901 ≤ 15 for every touched function (NFR-004). `_acquire_locked` is long, so extract the coord-arm resolution into a helper rather than growing the function.
- Run `ruff check` and `ruff format --check` on the changed files, and `mypy --strict` on the changed files, with zero issues and no new `# noqa` / `# type: ignore` (NFR-005).
- Reach ≥ 90% coverage of new and changed lines (diff-cover gate), with a focused test for every new branch or helper (NFR-003).
- If you add public symbols, run `tests/architectural/test_no_dead_symbols.py`.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5519 #2533

## Definition of Done

- T037 tests were committed first and shown RED on the lane base, with the output recorded.
- No caller in the four owned source files derives a status write location from `resolve_feature_dir_for_mission`, `resolve_status_surface*`, `read_dir(STATUS_STATE)` or a hand composition onto a coordination worktree.
- `_coord_feature_dir` is deleted. `transaction.py` no longer composes the coordination Mission dir.
- `CommitArtifactResult.surfaces` is populated.
- Every state row from T037 behaves as specified, for both coordination topologies.
- The C-008 controls are byte-identical.
- The quality gates are green, and test commands and counts are logged.

## Risks & Mitigations

- **Lock inversion or deadlock**: verify every new `write_dir` call site against I-SEED-2, and cover it with the T042 reentrancy and contention tests.
- **Hidden reliance on the old fallback**: callers that expected the root dir on EMPTY now see the coordination dir. Grep for assertions on root-path events in `tests/specify_cli/coordination/`. Re-pin stale ones with rationale (stale → re-pin, per Standing Order 4), and never weaken the contract.
- **Performance**: `write_dir` on MATERIALIZED must be probe-only. If a test shows an extra `git worktree add` per transition, fix it in the accessor's use, not with a cache here.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies red→green: the T037 tests are RED on the WP's base (the lane base before this WP's fix commits) and GREEN on the final commit.
- Confirm there is no second composer (`grep -n "KITTY_SPECS_DIR" src/specify_cli/coordination/status_transition.py src/specify_cli/coordination/transaction.py`). Any remaining hits must not compose a coordination write location.
- Confirm that the remote-only and DELETED refusals write nothing, and that the forked-MATERIALIZED Mission is not locked out.
- Confirm the C-008 controls and the `CommitArtifactResult` additive field (no existing field changed).

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

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-10-01T22:47:01Z – unknown – Cycle 2: addressed all review cycle 1 blocking items (B1-B4) and required non-blocking items (N1-N5) per coordinator's binding feedback. B1: reverted commit_router.py's formatting-only pollution (ratchet gate green). B2: rewrote T037 to drive the real move-task CLI (no --force), added the missing post-fix EMPTY row, Lamport/seed-commit/root-restored assertions. B3: diff coverage 86% -> 98% via focused unit tests on every flagged branch except one documented residual. B4: removed all 14 inert noqa suppressions, promoted local imports to top-level where no cycle existed. N1: narrowed commit_idempotent's zero-staged no-op using the already-tracked _pre_emit_events_existed signal, with tests for both behaviors. N2: moved the seed scratch dir outside kitty-specs/, reverted the walker-gate exemption to its original single entry (zero new exemptions). N3: replaced the census placeholder with the real tracer entry id. N4: added a dirty-root-copy owned seed/restore test. N5: fixed _dirty_paths_in_checkout's porcelain quoting/rename parsing bug with 4 new tests. Also recovered test_transaction.py from an accidental whole-file reformat that had silently dropped 16 _write_modern_meta(repo) calls from an earlier T038/T039 commit -- caught via the ratchet gate, reconstructed from c2fe4d5afd, confirmed purely additive by diff. All gates green except the coordinator-sanctioned COORD_SEED_TRAILER dead-symbol red (owned by WP06). make test-fast: 2173 passed. Broad coordination/status/lanes suite: 2897 passed, 18 skipped.
- 2026-10-01T23:44:03Z – unknown – Cycle 3: fixed exactly R1-R3 per the coordinator's ruling, red-first as separate commits per item. R1: commit_idempotent's zero-staged no-op guard now checks a NEW self._seed_committed_this_txn field (set from write_dir's Establishment == SEEDED/RESTORED_FROM_BRANCH at THIS transaction's own acquire), not _pre_emit_events_existed (true for any mission with history, which still masked an existing-log mission staging nothing new -- the reviewer's own probe, pinned red at tip 60506b314c then fixed). R2: _dirty_paths_in_checkout no longer cuts at the first ' (' before unquoting (which landed inside a C-quoted path containing ' (', e.g. 'Copy (1).md', leaving an unparseable unclosed-quote remainder that matched nothing -- confirmed red at 60506b314c via scratch worktree for both the untracked and tracked-modified shapes). New _strip_dirty_entry_suffix matches the exact known suffix text, gated on ??/!! status codes only. R3: removed the 2 trailing blank lines added to the format-excluded test_transaction.py. All three fixes verified: tests/coordination/ + tests/specify_cli/coordination/ + tests/status/ + tests/lanes/ + test_coord_read_seam_callers.py + test_agent_tasks_ports_write_dir.py (2903 passed, 18 skipped); commit_idempotent callers across implement/workflow (8 files, 53 passed); 40 matching integration files + 3 B1 guards (393 passed); 10 named architectural gates (337 passed); make test-fast (2173 passed). diff-cover against e7b085d26c: 97% (up from the reviewer's measured 93%). ruff/mypy clean (5 pre-existing errors unchanged, confirmed via scratch worktree). No optional items attempted (scope held to exactly R1-R3 per the explicit instruction).
