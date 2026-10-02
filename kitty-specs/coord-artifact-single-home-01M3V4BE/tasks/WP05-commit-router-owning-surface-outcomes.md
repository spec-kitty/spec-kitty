---
work_package_id: WP05
title: 'Commit router: retire the target fast-forward, per-surface outcome contract, owning-surface commits'
dependencies:
- WP01
- WP04
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-016
- SC-003
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
- T027
- T028
- T029
phase: Phase 2 - Commit router and create
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
agent: claude
authoritative_surface: src/specify_cli/coordination/commit_router.py
create_intent:
- src/specify_cli/coordination/commit_outcome.py
- tests/coordination/test_commit_router_coord_only_dirty_status_log.py
- tests/coordination/test_commit_outcome.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/coordination/commit_router.py
- src/specify_cli/coordination/commit_outcome.py
- tests/coordination/test_commit_router.py
- tests/coordination/test_commit_router_fail_loud.py
- tests/coordination/test_commit_router_coord_only_dirty_status_log.py
- tests/coordination/test_commit_outcome.py
- src/specify_cli/coordination/surface_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
assignee: ''
shell_pid: ''
---

# Work Package Prompt: WP05 – Commit router: retire the target fast-forward, per-surface outcome contract, owning-surface commits

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

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

This WP makes the commit router honest. When it is done:

- **FR-008.** `commit_for_mission` no longer fast-forwards the target branch after a coordination commit. `_try_advance_ref` is gone. A target branch that is an ancestor of the coordination tip stays exactly where it was (R12).
- **FR-007 (contract core).** A new module, `src/specify_cli/coordination/commit_outcome.py`, owns the per-surface commit outcome:
  - the types `PathFate` and `SurfaceOutcome`;
  - the reason-code constants;
  - one text renderer, one JSON payload builder and one exit-code helper.
- **FR-007 (populated).** `CommitRouterResult.surfaces` is populated with one entry per partition group, PRIMARY first. The legacy top-level fields keep today's caller-surface meaning.
- **FR-006.** A COORD record passed by its repository-root path is judged and committed on its **owning-surface copy**, the coordination worktree:
  - a dirty coordination copy is `committed`;
  - a clean one is `unchanged`;
  - anything else is `refused` with a named reason.
  - "Unchanged" never again hides a dirty coordination log (R2 green, R2b still green).
- Every refusal carries a named reason (`STATUS_LOCK_HELD`, `PROTECTED_BRANCH_REFUSED`, `COORDINATION_BRANCH_DELETED`, `PATH_UNROUTABLE`, `WRONG_SURFACE`). A router that always refuses fails R2.

Consumers are **not** migrated here. That happens in WP08, WP10, WP13, WP14, WP15 and WP16. This WP only adds and populates the contract.

## Context & Constraints

- **Spec**: FR-006, FR-007, FR-008, FR-016 (R2 adoption), SC-003; US3.1, US3.2, US3.3. Contract: `kitty-specs/coord-artifact-single-home-01M3V4BE/contracts/commit-outcome.md` (types, rules 1–6, reason codes, JSON shape). Data model: `data-model.md` §5.
- **Plan**: IC-10, then IC-07 (contract core only), then IC-06, all in this WP and in that order. This is a **stated deviation** from the plan's shared-file order 10 → 06 → 07 (analyze I5): R2's tightened refusal assertion needs `surfaces` before the owning-surface fix. IC-07's consumer migration still follows IC-06 in WP07–WP16.
- **Research**:
  - D7: owning-surface commit and its outcome table;
  - D8: the contract shape, the exit-code rule and the 14 consumers, which migrate later;
  - D11: retiring `_try_advance_ref`;
  - red-first list R2, R2b, R12.
- **Upstream WPs**:
  - WP01 extracted the per-path classify/translate decision out of `_stage_artifacts_in_coord_worktree` into one helper; change behaviour there.
  - WP04 provides `placement_seam(...).write_dir(kind) -> WriteLocation`.
  - WP03 added `error_code = "STATUS_LOCK_HELD"` on `FeatureStatusLockTimeoutError`.
- **Charter**: read `.kittify/charter/charter.md` and run `spec-kitty charter context --action implement`. ATDD-first (C-011): the red tests are committed **before** the fix commits. Single canonical authority: one renderer, no second classifier (C-001).
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology**: Mission, never feature. Name the sense of "primary": the **PRIMARY partition**, the **repository root checkout**, or the **target branch**.
- **C-006**: no heavy suites (see the Targeted test surface section).
- **C-008**: `lanes` and `single_branch` Missions must behave byte-identically.
- **Brownfield scout (binding read)**: before coding, read `## WP05` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp01-11.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- `finalize-tasks` allocates execution worktrees per computed lane, from `lanes.json`. Start with `spec-kitty agent action implement WP05 --agent claude`. Use the workspace path it resolves; never reconstruct it.
- **Lane A (shared).** This WP shares `commit_router.py` and `tests/coordination/test_commit_router.py` with WP01, its dependency, and runs in the same lane after WP01 and WP04. After the post-tasks squad P-m7, WP13/WP14/WP15 have their own lanes based on this WP's tip. WP07 makes a declared out-of-map edit to two tests in `tests/coordination/test_commit_router.py` after this WP (it deletes `status_transition._coord_feature_dir`).

## Subtasks & Detailed Guidance

### Subtask T023 – IC-10: retire the router's target-branch fast-forward (red-first R12)

- **Purpose**: After WP06, create seeds the coordination branch, so the target branch becomes an ancestor of the coordination tip. The best-effort `_try_advance_ref` would then fast-forward COORD records onto the target branch (FR-008, #5440).
- **Steps**:
  1. **Red first.** Add `test_no_target_advance_for_coordination_routed_mission` to `tests/coordination/test_commit_router.py`:
     - build a coordination-routed Mission with WP02's factory (`tests._factories.coord_mission`);
     - make the target branch an ancestor of the coordination tip;
     - dirty a COORD file in the coordination worktree;
     - call `commit_for_mission(..., target_branch=<target>)`;
     - assert `git rev-parse <target>` is unchanged and the coordination tip advanced.
     - Commit the test alone. It is red at base, because `_try_advance_ref` fast-forwards.
  2. Delete the post-commit advance in `_commit_partition_group` (`commit_router.py:560-561`, `if use_coord and target_branch: _try_advance_ref(...)`) and the comment above it that justifies it (≈L555-559).
  3. Delete `_try_advance_ref` (`commit_router.py:1302-1342`), including its residue-predicate use (≈L1337).
  4. Keep the `target_branch` parameter of `commit_for_mission`; it still feeds the owned-placement result (≈L283/L290 `placement_ref=target_branch or ""`). Rewrite its docstring (≈L259, "Short primary branch name for the post-commit ff-advance …") to state its remaining meaning, and name the sense ("target branch").
  5. In `tests/coordination/test_commit_router_fail_loud.py:320`, drop `patch.object(commit_router, "_try_advance_ref")`. The symbol no longer exists, so the test should no longer patch it. Keep the test's own assertion intact.
- **Files**: `src/specify_cli/coordination/commit_router.py`, `tests/coordination/test_commit_router.py`, `tests/coordination/test_commit_router_fail_loud.py`.
- **Validation**: R12 green. `grep -n "_try_advance_ref" -r src tests` returns nothing.
- **Do not touch**: `consolidation/bookkeeping_projection.py:487` or `git/ref_advance.py:493`. They are consolidation's sanctioned projection (the FR-008 exclusion). The `spec-commit --target-branch` help text is WP13's.
- **Edge cases**:
  - callers that pass `target_branch` (finalize ≈L3667, setup-plan L244/899/958, write seam L556, orchestrator L3025, report transaction L206, spec-commit L225) only lose an inert, best-effort side effect;
  - check that none of their tests asserts the advance; if one does, it is stale, so re-pin it and record why.
- **Non-vacuity precondition (post-tasks squad R-m8)**: in R12, first assert that the base-shaped advance actually moves the target when the router fast-forwards. Use a clean checkout with the target an ancestor of the coordination tip, and check `git merge-base --is-ancestor <target> <coord>` before the call. Otherwise the 'target unchanged' assertion could pass vacuously at the base (for example because of a dirty checkout or a non-ancestor target).

### Subtask T024 – `commit_outcome.py`: the per-surface outcome contract

- **Purpose**: Masking lives in the shared result contract, so the fix lives there too (D8). Consumers will render through exactly one pair of functions.
- **Steps**:
  1. Create `src/specify_cli/coordination/commit_outcome.py` with frozen dataclasses exactly per `contracts/commit-outcome.md`:
     - `PathFate(path: str, reason: str, owning_path: str | None = None)`;
     - `SurfaceOutcome(surface: Literal["primary", "coordination"], branch: str, status: Literal["committed", "unchanged", "refused", "error"], commit_hash: str | None, committed: tuple[str, ...] = (), skipped: tuple[PathFate, ...] = (), refused: tuple[PathFate, ...] = (), diagnostic: str | None = None)`.
  2. Add the reason-code constants as `Final` strings:
     - `REASON_ALREADY_COMMITTED = "no_op_already_committed"`. Re-export or reuse the router's `_REASON_ALREADY_COMMITTED` (`commit_router.py:166`). Pick one owner and import from it; never duplicate the literal (S1192).
     - `REASON_NO_CHANGES = "no_op_no_changes"` (L167).
     - `COORD_RECORD_IN_ROOT_CHECKOUT`, `STATUS_LOCK_HELD`, `PATH_UNROUTABLE`, `WRONG_SURFACE` (new).
     - `PROTECTED_BRANCH_REFUSED`: import it from `coordination/types.py:90`.
     - `COORDINATION_BRANCH_DELETED`: reuse the existing code constant. Grep for its definition first.
  3. Add `render_commit_outcome(result) -> list[str]`. Emit one line per surface, then one line per refused or skipped path, in the contract's example format:
     - `✓ primary (topic): committed abc1234 — 2 files`
     - `✗ coordination (kitty/mission-m-01ABCDEF): refused — status.events.jsonl: STATUS_LOCK_HELD`
     - Accept anything exposing a `surfaces` attribute (a `Protocol`), so the wrapper results in WP07 and WP10 can reuse it.
  4. Add `commit_outcome_payload(result) -> dict[str, object]`, the JSON form: `{"surfaces": [...]}` with each `PathFate` as `{"path", "reason", "owning_path"}`.
  5. Add `commit_outcome_exit_code(result) -> int`: non-zero iff any surface status is `refused` or `error`; `skipped`/`unchanged` return 0.
  6. Declare `__all__`. Every public symbol needs a caller in `src/` by the end of the Mission. If `tests/architectural/test_no_dead_symbols.py` flags a symbol that only later consumers will use, wire at least the router's own use now, or record the expectation in the activity log.
- **Files**: `src/specify_cli/coordination/commit_outcome.py` (new), `tests/coordination/test_commit_outcome.py` (new).
- **Validation**: unit tests cover each status glyph, path listing, a JSON round-trip, exit codes (refused → 1, error → 1, skipped/unchanged/committed → 0) and the empty-surfaces legacy case (no lines, exit 0).
- **Edge cases**: a commit hash shortened to 7 characters in text but full in JSON; branch names with slashes; ASCII-safe output. Check how the CLI prints elsewhere (workflow.py uses `[ok]`/`[refused]`). Keep the glyphs consistent with the contract but ensure Windows consoles do not crash: use the repo's ANSI/console helpers if they exist.

### Subtask T025 – `CommitRouterResult.surfaces`, populated by `_merge_group_results`

- **Purpose**: Contract rule 1. `surfaces` has one entry per partition group the request touched, PRIMARY then coordination. Rule 4: the legacy fields are unchanged.
- **Steps**:
  1. Add `surfaces: tuple[SurfaceOutcome, ...] = ()` to `CommitRouterResult` (`commit_router.py:174-205`). It is additive and defaults empty, and the docstring explains it.
  2. In `_commit_partition_group`, build that group's `SurfaceOutcome` where the outcome is decided: committed paths, the commit hash, the branch (`placement.ref`) and the status mapping:
     - `committed` → committed;
     - `unchanged` → unchanged, with skipped `PathFate`s carrying the existing reason;
     - `no_op_wrong_surface` → refused `WRONG_SURFACE`;
     - `error` → error.
     - The surface is `"coordination"` when the group routes through coordination, else `"primary"`.
  3. In `_merge_group_results` (`commit_router.py:802-844`), collect every group's surfaces into the returned result, ordered PRIMARY then coordination. This applies on the error early-return too: an error result must still carry all surfaces, so a caller sees the other group's commit.
  4. Keep the legacy `status`, `placement_ref`, `commit_hash`, `diagnostic` and `reason` caller-surface selection, and the `commit_hashes` union, byte-identical.
- **Files**: `src/specify_cli/coordination/commit_router.py`, `tests/coordination/test_commit_router.py`.
- **Validation**: a mixed batch where the PRIMARY group commits and the coordination group is skipped (clean coordination copy) yields `surfaces == (primary committed, coordination unchanged/skipped)`; the legacy fields are unchanged versus base. Also run `tests/specify_cli/coordination/test_commit_router_partition.py` and `test_commit_router_partition_authority.py`.
- **Edge cases**:
  - single-group batches get exactly one surface;
  - owned placements (L283/L290) get a surface too;
  - early-return error constructions (expected-parent guards ≈L310-321) may carry `surfaces=()`. Document that this is an argument error, not a surface outcome.
- **Public partition predicate (post-tasks squad P-M5)**: export the router's per-path partition decision as one public helper, e.g. `partition_for_mission_path(repo_root, mission_slug, path, *, owned) -> Literal["primary", "coordination"]`. It must be the same function `_merge_group_results`' grouping uses (not a copy), with a focused test. WP16's accept dirty gate calls it instead of adding a new classifier.

### Subtask T026 – Adopt R2/R2b and tighten the refusal branch (red-first)

- **Purpose**: The #5513 P0 reproduction, PR #5520, becomes the acceptance test for FR-006.
- **Steps**:
  1. Run `git cherry-pick -x 251bea520f` (from `upstream/test/p0-repro-5513`). It adds `tests/coordination/test_commit_router_coord_only_dirty_status_log.py` (140 lines). Keep the `-x` provenance line.
  2. Read both tests:
     - R2 `test_router_never_reports_a_coord_only_dirty_status_log_as_unchanged`;
     - R2b `test_clean_coordination_copy_reports_unchanged`.
  3. Tighten R2's refusal branch: an outcome other than `committed` passes only if `result.surfaces` holds a coordination `SurfaceOutcome` whose `refused` lists the status log with a reason in the named set (`PROTECTED_BRANCH_REFUSED`, `STATUS_LOCK_HELD`, `COORDINATION_BRANCH_DELETED`, `PATH_UNROUTABLE`). On the standard fixture, assert `committed` outright and that the coordination tip contains the dirty row.
  4. If the adopted fixture does not use WP02's factory, you may switch it to the factory, as long as R2 stays red at base.
  5. Commit the adopted and tightened tests **before** T027/T028. Confirm R2 is red on the lane base (status `unchanged`, reason `no_op_already_committed`) and R2b is green.
- **Files**: `tests/coordination/test_commit_router_coord_only_dirty_status_log.py` (new via cherry-pick).
- **Validation**: record the red output in the activity log (command + failure line).
- **Edge cases**: if the cherry-pick conflicts, resolve it by keeping the upstream test content. The file is new here, so a conflict means the path already exists, which would be surprising; investigate before continuing.

### Subtask T027 – IC-06: translate a root-path COORD log to its owning-surface path

- **Purpose**: D7. Today a repository-root-path `STATUS_STATE` input is skipped in `_stage_artifacts_in_coord_worktree` (`commit_router.py:991`; the skip is at L1038-1039; WP01 moved it into a helper). The router then reports "unchanged" while the coordination copy is dirty.
- **Steps**:
  1. In the per-path helper WP01 extracted, for a repository-root input whose `kind_for_mission_file(rel)` is `STATUS_STATE` or `DECISION_LOG`:
     - resolve `placement_seam(repo_root, mission_slug, owned=...).write_dir(kind).path`;
     - join the same Mission-relative file path onto it;
     - append that coordination path to `coord_files` instead of `continue`-skipping.
  2. **Never copy** a root log over the coordination log. These are append-only logs; the root copy is ignored for staging. Root dirt is judged in T028.
  3. Leave untouched:
     - the `.worktrees/` in-place branch (≈L1018-1030, #5353: paths already in this coordination worktree commit in place);
     - the `analysis-report.md` PRIMARY skip (≈L1041-1048).
  4. Other COORD kinds (traces, review-cycle, `acceptance-matrix.json`, `issue-matrix.md`) keep today's `shutil.copy2` legacy staging, but only while the coordination copy is absent. Once present, the coordination copy wins and is not overwritten (writers write in place after WP08/WP10). Keep the residue cleanup at ≈L1069-1088.
  5. `write_dir` may materialize or seed (WP03/WP04). That is intended: a commit of a COORD record must land on its single home. Its refusals surface as `refused` in T029.
- **Files**: `src/specify_cli/coordination/commit_router.py`, `tests/coordination/test_commit_router.py`.
- **Validation**: R2 goes green once T028 lands. New focused tests:
  - a `DECISION_LOG` root-path input commits the coordination copy;
  - the root log is never copied (assert the coordination file's bytes are unchanged apart from the dirty row);
  - the legacy copy still happens for an absent coordination trace file.
- **Edge cases**: `lanes` and `single_branch` (no coordination) take the old path untouched (C-008). Owned checkouts pass `owned` to the seam. Fail closed on a path that does not resolve to a known kind (T029 `PATH_UNROUTABLE`).
- **All COORD kinds (post-tasks squad P-M2)**: the owning-surface judgement covers every COORD kind, not only STATUS_STATE / DECISION_LOG: `traces/*.md`, `tasks/<wp>/review-cycle-*.md`, `issue-matrix.md`, `acceptance-matrix.json`, the status log and `decisions.events.jsonl`. A dirty owning (coordination) copy is committed, never reported `unchanged`. A root-only dirty copy is `skipped` with `COORD_RECORD_IN_ROOT_CHECKOUT`. Logs are never copied root → coordination.
- **Legacy root-staging copy (`shutil.copy2`)**: it stays only as the fallback while a non-log COORD record's coordination copy is absent. Its retirement is recorded in tasks.md as a **post-consolidation fold**: "retire the router's legacy root-staging copy once the WP08/WP10 writers are migrated". It cannot be a WP here, because that would create a lane cycle. Do not remove it in this WP.

### Subtask T028 – Owning-surface dirt in `_classify_no_commit_paths`

- **Purpose**: "Unchanged" must mean unchanged on the owning surface.
- **Steps**:
  1. `_classify_no_commit_paths` (`commit_router.py:436`) currently checks only primary dirt (L457, `_paths_uncommitted_in_primary`, L1263). For translated COORD paths, check `git status --porcelain -- <coord path>` in the coordination worktree:
     - dirty → it must reach the commit path. If the commit path is still empty, this is a bug, so raise or report `error`; never `unchanged`.
     - clean on coordination, and the root copy also clean or absent → `unchanged`, reason `no_op_already_committed`.
     - clean on coordination, root copy dirty → the coordination surface is unchanged, and the root path is listed as skipped `COORD_RECORD_IN_ROOT_CHECKOUT` (contract rule 3). It is never committed to the target branch.
  2. Keep today's `no_op_wrong_surface` detection for PRIMARY-partition files absent at placement, now reported as refused `WRONG_SURFACE` inside `surfaces`.
  3. Extract small helpers so C901 stays ≤ 15. This function was a campsite extraction (T035 of an earlier Mission); keep it flat.
- **Files**: `src/specify_cli/coordination/commit_router.py`, `tests/coordination/test_commit_router.py`.
- **Validation**:
  - R2 green and R2b green;
  - a root-only-dirty fixture reports `COORD_RECORD_IN_ROOT_CHECKOUT` with the target branch tip unchanged;
  - the test-name conventions of `test_commit_router.py` are respected.
- **Edge cases**: untracked versus modified coordination files (porcelain covers both); a coordination worktree under a sparse checkout (`tests/specify_cli/coordination/test_sparse_checkout.py` exists, so run it).
- Add one test per COORD kind listed in T027 (dirty owning copy → committed; clean owning copy plus dirty root copy → skipped `COORD_RECORD_IN_ROOT_CHECKOUT`; clean both → unchanged).

### Subtask T029 – Named refusals and `owned` forwarding on the split path

- **Purpose**: A refusal is legitimate only for a named reason (FR-006, US3.1). It is visible per surface, never a bare `error` string.
- **Steps**:
  1. `except FeatureStatusLockTimeoutError` (`commit_router.py:639-640`) returns `status=_STATUS_ERROR` today. Keep the legacy `status`, but the group's `SurfaceOutcome` is `refused` with `PathFate(reason=STATUS_LOCK_HELD)` (use `exc.error_code` from WP03, defaulting to the constant). Decide, and document in the docstring, whether the legacy top-level status stays `error`. Keeping it is the additive-compatibility choice.
  2. Map a protected coordination ref (`ProtectedBranchRefused` or the guard verdict) to `PROTECTED_BRANCH_REFUSED`, a deleted coordination branch (`CoordinationBranchDeleted` raised by `write_dir`) to `COORDINATION_BRANCH_DELETED`, and an unclassifiable or outside-Mission path to `PATH_UNROUTABLE`. Translate `write_dir` errors such as remote-only `COORDINATION_WORKTREE_UNMATERIALIZED` or `COORD_SEED_FORK_REFUSED` to refused, with the error code as the reason and its message as the diagnostic. Never swallow them silently.
  3. The split path (`commit_router.py:314-327`) calls `_commit_partition_group` without `owned`. Thread the caller's `owned` through, so owned coordination Missions route correctly.
  4. One test per reason. For the lock, hold `feature_status_lock` from another thread or process in the test, or patch the lock to raise. Patching is acceptable only if a real-lock variant is impractical, and then explain why in the test docstring.
- **Files**: `src/specify_cli/coordination/commit_router.py`, `tests/coordination/test_commit_router.py`.
- **Validation**: each reason surfaces in `result.surfaces[*].refused` and in `commit_outcome_exit_code(result) == 1`. A router patched to always refuse makes R2 fail (the tightened branch requires `committed` on the standard fixture).
- **Edge cases**: a mixed batch where PRIMARY commits and coordination is refused: the legacy fields show the caller surface, and `surfaces` shows both. That is exactly the masking FR-007 forbids consumers to ignore.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **I5 (analyze): stated deviation from the plan.** The subtask order IC-10 → contract core → IC-06 deviates from plan.md's shared-file order 10 → 06 → 07 because R2's tightened refusal assertion needs `surfaces` before the owning-surface fix lands. IC-07's consumer migration still follows IC-06 (WP07–WP16).
- **T029 step 3 correction**: the partition split runs only when `owned is None` (L278: `groups = [(kind, files)] if owned is not None else _group_files_by_partition(...)`), so threading `owned` into the split is a no-op. Owned Missions cannot be coordination-routed today (`core/owned_mission.py:57`, `LIFECYCLE_OWNED_TOPOLOGIES == {SINGLE_BRANCH}`). Label every owned-coordination case a **forward guard**.
- **Canonical literals and exit code**:
  - `COORDINATION_BRANCH_DELETED` is a **class attribute**, `CoordinationBranchDeleted.error_code` (surface_resolver.py:205), plus a literal at `runtime_bridge.py:468`;
  - status/reason literals are duplicated in `coordination/surface_authority.py:261-268`, and its `_exit_code_for` (L315) is "the canonical exit-code mapping".
  - Make `commit_outcome` the **single owner** of the reason literals and the exit-code rule, reusing the canonical mapping, not a second one. `surface_authority.py` (now owned by this WP) imports them. This also gives `commit_outcome_exit_code` and the literals a `src` consumer.
- **Transitional dead-symbol red (operator protocol)**:
  - `render_commit_outcome` and `commit_outcome_payload` have no `src` consumer until the first consumer WP lands (WP10's tracer_append / WP07–WP08 / WP13–WP16).
  - `tests/architectural/test_no_dead_symbols.py` (allowlist cap 293, `_baselines.yaml:443`) is therefore **EXPECTED red at this WP's tip**. Add an activity-log note naming the consuming WP. Reviewers accept this specific transitional red; the first consuming WP to land must turn it green. Closeout history cleanup folds the gate companions.
  - **Prefer zero-red**: if a natural in-WP production use exists (e.g. the router logging a WARNING through `render_commit_outcome` for internal discarded-result paths), use it and the gate stays green.
  - The public partition predicate (P-M5) is consumed by the router's own grouping, so it is live.
- **Signatures and seams**:
  - `commit_for_mission` has a required positional `policy` (L218); every snippet must pass it.
  - `_stage_artifacts_in_coord_worktree` gains `mission_slug` and `owned` as **keyword-only, optional** parameters. This keeps the three-positional unit callers green: `test_commit_router.py:792/833/871/891`, `test_finalize_coord_staging.py` ×5, `test_finalize_clobber_e2e.py:374` and `test_wp06_sc2_paused_mission_blockers.py:658/680/714`. Their fixtures have no `meta.json`, so call `write_dir` only when `mission_slug` is given.
  - The second production caller is `_resolve_commit_worktree_for_kind` (L1230).
  - Resolve **one** `WriteLocation` per staging call, not one per path.
  - `_merge_group_results` returns the first error as-is (L833-835); attach the surfaces with `dataclasses.replace(result, surfaces=...)`.
- **#5353 pin**: `test_commit_router.py::test_coord_staging_keeps_a_status_log_already_in_the_coord_worktree` (L812) expects `coord_files == [coord_log]` when both logs are passed. Translation produces a duplicate, so use an **order-preserving dedupe**.
- **Valid guard**: `test_finalize_clobber_e2e.py::...::test_coord_refinalize_with_only_status_changes_is_noop` must survive the `COORD_RECORD_IN_ROOT_CHECKOUT` skip.
- **Recursion**: the WP03 seed commits through `commit_for_mission` with in-worktree paths, which hit IN_PLACE first. Add a test proving there is no recursion.
- **Constraints carried over**:
  - the lock key is `coord_feature_dir.name`;
  - `commit_outcome` must not import `specify_cli.cli` (`test_commit_router_layering.py`);
  - print ✓/✗ through rich or an ASCII fallback (cp1252);
  - keep `write_dir` lazy and patch-compatible (tests patch `CoordinationWorkspace.resolve`).
- Run the scout's quick-run additions by name, including `tests/git/test_commit_to_target_scope_guards.py` and `tests/architectural/test_dead_symbol_allowlist_contract.py`.

## Targeted test surface

Run from the lane worktree:

```bash
uv run --frozen pytest tests/coordination/test_commit_router.py tests/coordination/test_commit_router_fail_loud.py \
  tests/coordination/test_commit_router_coord_only_dirty_status_log.py tests/coordination/test_commit_outcome.py -q
uv run --frozen pytest tests/specify_cli/coordination/test_commit_router_partition.py \
  tests/specify_cli/coordination/test_commit_router_partition_authority.py \
  tests/specify_cli/coordination/test_commit_router_placement.py tests/specify_cli/coordination/test_residual_writer_routing.py \
  tests/specify_cli/coordination/test_sparse_checkout.py tests/coordination/test_commit_router_layering.py -q
uv run --frozen pytest tests/coordination/ -q          # owning subsystem directory
make test-fast
uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_write_surface_placement_guard.py -q
```

- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record every command with its pass/fail counts in the Activity Log, for the PR's *Tests run* section.
- Classify any unrelated red with CLAUDE.md's baseline-red gotcha (pre-existing P0, CI-environment, stale install, stale venv) before treating it as yours.

## Quality gates

- C901 ≤ 15 for every touched function (NFR-004); `_stage_artifacts_in_coord_worktree` and `_classify_no_commit_paths` must stay flat, so extract helpers.
- `ruff check` and `ruff format --check` on changed files; `mypy --strict` on changed files; zero new suppressions (NFR-005).
- ≥ 90% coverage of new and changed lines, with a focused test for every new branch and helper (NFR-003, diff-cover gate).
- New public symbols in `commit_outcome.py`: run `tests/architectural/test_no_dead_symbols.py`.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5513 #5501 #5440

## Definition of Done

- R12, R2 (tightened), R2b and every new focused test are green; R12 and R2 were demonstrably red on the lane base (output in the Activity Log).
- `_try_advance_ref` and its call are deleted; `target_branch` keeps its documented remaining meaning; the fail-loud test no longer patches it.
- `commit_outcome.py` exists with types, reason codes, renderer, payload and exit-code helper, all unit-tested.
- `CommitRouterResult.surfaces` is populated PRIMARY → coordination; legacy fields are byte-identical to base on every pre-existing test.
- Root-path `STATUS_STATE`/`DECISION_LOG` inputs commit the coordination copy; a root log never overwrites the coordination log.
- Named refusals are mapped; `owned` is forwarded on the split path.
- Gates are green; the Activity Log records commands and counts.
- **FR-016 relocation (post-tasks squad R-M8)**: after R2/R2b are GREEN, fold them into `tests/coordination/test_commit_router.py` (keep their names). Delete the adopted standalone `tests/coordination/test_commit_router_coord_only_dirty_status_log.py`, and remove its "stays red on main" docstring and regression marker. The transitional reproduction must not stand as a regression marker.
- WP16 can import the public partition predicate (P-M5).

## Risks & Mitigations

- **Hot shared file.** `commit_router.py` is shared with WP01 (done) and the downstream consumer WPs. Keep edits inside the functions named here and inside WP01's helper.
- **`write_dir` side effects inside a commit path.** Materialization or a seed can happen during a commit. That is intended (single home), but rely on WP03's lock ordering (I-SEED-2): taking the workspace lock while holding the status lock (status → workspace) is permitted; acquiring the status lock while holding the workspace lock is forbidden. `_coord_status_locks` (≈L586) reuses the same reentrant key, so verify with a test that commits while holding the status lock.
- **Legacy JSON readers.** Additive fields only; do not change the top-level `status`.
- **Translating DECISION_LOG.** The decision stream lives at `decisions.events.jsonl` (DecisionGitLog). Confirm the file→kind mapping with `kind_for_mission_file` rather than hard-coding filenames.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies red→green: R12 and R2 RED on the WP's lane base before the fix commits, GREEN on the final commit. R2b green throughout.
- Check that no consumer was migrated here (scope), there is one renderer, and no duplicated reason literals.
- Check that the FR-008 exclusion is honoured: no edits to `bookkeeping_projection.py` or `git/ref_advance.py`.
- Check that a commit patched to "always refuse" fails R2.
- Confirm `mypy --strict` and the ruff results in the Activity Log.

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
