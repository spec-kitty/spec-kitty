---
work_package_id: WP06
title: Create materializes and seeds the coordination surface; expected-divergence model
dependencies:
- WP05
requirement_refs:
- FR-001
- FR-002
- FR-002a
- FR-002b
- FR-016
- NFR-001
- C-008
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T17:50:52.190841+00:00'
subtasks:
- T030
- T031
- T032
- T033
- T034
- T035
- T036
phase: Phase 2 - Commit router and create
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/mission_creation.py
create_intent:
- tests/core/test_mission_create_coord_status_placement.py
- tests/core/test_mission_create_coord_seed_rollback.py
- tests/missions/test_expected_coordination_divergence.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/core/mission_creation.py
- src/specify_cli/missions/_create.py
- src/specify_cli/cli/commands/_coordination_doctor.py
- tests/core/test_mission_create_coord_status_placement.py
- tests/core/test_mission_creation_decomposition.py
- tests/core/test_mission_create_coord_seed_rollback.py
- tests/missions/test_expected_coordination_divergence.py
- tests/specify_cli/cli/commands/test_coordination_doctor.py
- tests/coordination/test_surface_resolver_coord_empty_warning.py
- tests/core/test_mission_creation_fanout_commit_boundary.py
- tests/specify_cli/core/test_mission_creation_specify_started.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Create materializes and seeds the coordination surface; expected-divergence model

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

This WP removes the birth of the defect (#5440, P0; #2533). When it is done, creating a coordination-routed Mission (`coord` or `lanes_with_coord`, including `--pr-bound --start-branch`) behaves as follows:

- **FR-001 / US1.1.** No commit between the creation base and the target-branch tip touches a COORD-partition record. `meta.json`, `tasks/README.md` and `tasks/.gitkeep` still land on the target branch; that is the positive control.
- **FR-002 / US1.1–1.3.**
  - The coordination worktree is **materialized** at create.
  - The coordination branch carries `kitty-specs/<dir>/status.events.jsonl` with `MissionCreated` and `SpecifyStarted`.
  - The coordination Mission dir holds COORD records only, never `meta.json` or other planning copies.
  - The production read classifier reports the surface as MATERIALIZED immediately after create.
- **FR-002a / US1.4–1.5.**
  - Seeding happens even when the target-branch scaffold commit is suppressed (a protected primary branch).
  - A create that fails after the seed rolls the seed back (worktree removed, branch deleted or reset).
- **FR-002b / US1.6.**
  - One shared predicate defines the by-design coordination-vs-target divergence.
  - `doctor coordination` stops reporting `COORDINATION_BRANCH_DIVERGED_VS_TARGET` for a freshly seeded Mission, but still reports a genuinely diverged legacy branch.
  - `ensure_coordination_branch` uses the same rule.
- **#2533.** No split-brain fallback warning right after a new coordination create (R6); the legacy-empty control still warns.
- **NFR-001.** Create stays within +1.0 s of the measured baseline median per configuration.
- **C-008.** `lanes` and `single_branch` creates are byte-identical to today.

## Context & Constraints

- **Spec**: US1 (scenarios 1–6); FR-001, FR-002, FR-002a, FR-002b, FR-016 (R1, R1b, R6 reproductions), NFR-001, C-008; Assumptions (eager materialization decided: decision `specify.design.seed-mechanism`).
- **Plan**: IC-05 (IC-02's R1c "S9" implementer check is struck: create defaults to COORD).
- **Research**: D6 (create order, protected target, divergence model), D4 (post-fix discriminator), NFR-001 baseline section; red-first R1, R1b, R1c, R6, R20.
- **Contracts and data model**: `contracts/seed.md` ("Create-time seed" note), `contracts/write-location-accessor.md`, `data-model.md` §6 (lifecycle) and §7 (create atomicity row).
- **Upstream WPs**:
  - WP02: `tests._factories.coord_mission` (factory plus pre-fix builder).
  - WP03/WP04: `placement_seam(...).write_dir(STATUS_STATE)`. On an EMPTY surface with no root records it seeds an empty Mission dir and returns `establishment=SEEDED`.
  - WP05: the router commits coordination-worktree paths in place, and the target fast-forward is gone (FR-008). So seeding cannot ride onto the target branch.
- **Charter**: read `.kittify/charter/charter.md` and run `spec-kitty charter context --action implement`. ATDD-first (C-011): adopted reds are committed before the fix.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology**: Mission, never feature. "Target branch" (`meta.json` `target_branch`), "repository root checkout", "PRIMARY partition": always name the sense of "primary".
- **C-006**: no heavy suites (see the Targeted test surface section).
- **Brownfield scout (binding read)**: before coding, read `## WP06` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp01-11.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- `finalize-tasks` allocates execution worktrees per computed lane, from `lanes.json`. Start with `spec-kitty agent action implement WP06 --agent claude`. Use the workspace path it resolves; never reconstruct it.
- This WP's owned files are disjoint from every other WP, so it gets its own lane. Its lane base includes WP05 (and, through it, WP01–WP04) via dependency stacking.

## Subtasks & Detailed Guidance

### Subtask T030 – Adopt R1/R1b (red-first)

- **Purpose**: The #5440 P0 reproduction (PR #5518) becomes this WP's acceptance contract.
- **Steps**:
  1. Run `git cherry-pick -x 31ea4681f7` (from `upstream/test/p0-repro-5440`). It adds `tests/core/test_mission_create_coord_status_placement.py` (141 lines). Keep the provenance line.
  2. Make sure the file holds both:
     - **R1** `test_coord_create_scaffold_commit_keeps_status_off_target_branch`. A **history** probe: `git log <creation_base>..<target> -- kitty-specs/<dir>/status.events.jsonl` is empty, plus the positive control that `meta.json` is in that range. Assert on history, not the tip tree (squad finding R8).
     - **R1b** `test_coord_create_seeds_coordination_branch_and_reads_materialized`, which checks all of:
       - `git ls-tree <coord> kitty-specs/<dir>/status.events.jsonl` exists, and its content holds `MissionCreated` and `SpecifyStarted`;
       - `placement_seam(...).read_dir(STATUS_STATE)` resolves inside the coordination worktree (the classifier stamp is COORD and MATERIALIZED, not EMPTY);
       - the coordination Mission dir contains no `meta.json`, `spec.md` or `tasks/README.md` (US1.3).
     - Add R1b if the upstream commit lacks it.
  3. Parametrize over `coord` and `lanes_with_coord`, and over the `--pr-bound --start-branch <topic>` CLI path, via WP02's `make_coord_mission(..., via=...)`.
  4. Commit the adopted and extended tests alone. Confirm they are red on the lane base (scaffold commit carries the log; coordination tip = pre-create commit) and record the failure lines.
- **Files**: `tests/core/test_mission_create_coord_status_placement.py` (new via cherry-pick).
- **Edge cases**:
  - the fixture must be on a non-protected topic branch for R1, otherwise the scaffold commit is suppressed (see T032 for the protected variant);
  - the `origin/HEAD`-less primary-detection fallback can make "create on the current branch" resolve `coord`, so always pass the topology explicitly (or use the pr-bound path).
- **Real default path (post-tasks squad R-m4)**: add one parametrization with a **protected primary**, created through `--pr-bound --start-branch <topic>` with **no `--topology`** (WP02 factory: `protected_primary=True`, topology omitted). Assert `meta.json` `topology == "coord"` first, then the US1.1 history probe and the US1.4 seed (coordination branch carries the log although the target scaffold commit is suppressed).

### Subtask T031 – Create flow: materialize, seed, emit into the coordination dir, commit on the coordination branch

- **Purpose**: Research D6, "create order". The coordination branch carries the creation records from birth; the target branch never does.
- **Steps**:
  1. In `_create_mission_core_impl` (`mission_creation.py:1722`), after `_build_create_meta` (call ≈L1894; the coordination branch is cut inside it at ≈L1300-1302 via `ensure_coordination_branch`) and the minted-branch re-target (≈L1908-1923): **for coordination-routed topologies only**, call `placement_seam(resolved_root, mission_slug_formatted, owned=...).write_dir(MissionArtifactKind.STATUS_STATE)`. This materializes the worktree and seeds an empty Mission dir, because there are no root records yet.
  2. Pass the returned `WriteLocation.path` into `_emit_create_events` (≈L1925; definition L1429; it reads back at ≈L1502 and writes at ≈L1484/L1535) as the dir that receives `MissionCreated` and `SpecifyStarted`. Today it receives `scaffold.feature_dir`, the repository root checkout. Add an explicit `status_dir` parameter rather than overloading `feature_dir`; spec.md and other PRIMARY files still use `feature_dir`.
  3. Commit those events on the coordination branch via `commit_for_mission(repo_root, mission_slug, files=(<coord status.events.jsonl>,), message=..., kind=MissionArtifactKind.STATUS_STATE)`. Coordination-worktree paths commit in place (WP05). Assert the result is `committed`; on refusal, raise so rollback runs (T032).
  4. Remove `feature_dir / "status.events.jsonl"` from `scaffold_paths` (≈L1168-1173) and drop the root-checkout `touch` (≈L1201) **for coordination topologies**. `lanes`/`single_branch` keep both exactly as today (C-008), so make the tuple topology-dependent via a small helper.
  5. Update `_build_create_result` (≈L1680-1700): its `skipped_scaffold` list and `log_path = scaffold.feature_dir / "status.events.jsonl"` (≈L1688/L1697, used by `fanout_lifecycle_event_hosted`) must point at the coordination log for coordination topologies. `created_files` should list the coordination path.
  6. Keep `_emit_create_events` C901 ≤ 15; `_build_create_meta` is already 10.
- **Files**: `src/specify_cli/core/mission_creation.py`.
- **Validation**: R1 and R1b green, for both topologies and for pr-bound. A `lanes` control produces the same scaffold tree as base (byte-identical file list in the scaffold commit). The JSON create output (`coordination_branch` and the rest) is unchanged apart from paths.
- **Edge cases**:
  - **Owned checkout.** `roots.owned` / `lifecycle_root`: `write_dir` must be built with the owned binding (WP04 owned arm).
  - **Hosted fan-out** must read the log where it was written.
  - `ensure_coordination_branch` returned `skipped_reason` (target does not resolve, synthetic contexts): then there is no coordination branch. `write_dir` must answer the PRIMARY dir (state NONE) and the old path applies. Test this.
- **Trailer (round 4, `plan.design.seed-trailer-ownership`)**: create's commit on the coordination branch carries `Spec-Kitty-Coordination-Seed: <mission_id>`, built from WP03's shared constant `COORD_SEED_TRAILER` (import it; never a literal). Test it: after create, `git log --format=%(trailers:key=Spec-Kitty-Coordination-Seed,valueonly) <coordination_branch>` contains the `mission_id`.

### Subtask T032 – Protected target and failure-atomic rollback (FR-002a, US1.4/1.5)

- **Purpose**: Seeding must not depend on the target-branch scaffold commit, and a failed create must undo both refs.
- **Steps**:
  1. Keep the seed and the coordination commit **outside** `contextlib.suppress(*_BOOTSTRAP_META_COMMIT_SKIPS)` (`_BOOTSTRAP_META_COMMIT_SKIPS` L69-73; suppression sites ≈L1178, L1601, L1642). They run unconditionally for coordination topologies, even when the target scaffold commit is a disclosed bootstrap skip on a protected primary branch.
  2. Extend `_restore_git_state_after_failed_create` (L683) with a coordination leg, in this order:
     - restore the operator checkout (existing step 1);
     - `CoordinationWorkspace.teardown(repo_root, mission_slug, mid8)` (`coordination/workspace.py:352`; idempotent; git refuses to delete a branch checked out in a worktree, so tear down **before** deleting);
     - delete the coordination branch when this run minted it (the existing `pre_existing_coordination_branches` diff over `_COORDINATION_BRANCH_GLOB`);
     - otherwise CAS-reset it to its pre-create tip. Capture that tip before the seed, and pass it in.
     - Keep the function best-effort and non-raising.
  3. Write `tests/core/test_mission_create_coord_seed_rollback.py`:
     - (a) a protected-primary create still materializes and seeds the coordination surface, and the coordination branch carries the log (US1.4);
     - (b) inject a failure after the seed (patch the step right after the coordination commit, or the scaffold commit, to raise); assert no coordination worktree remains, the minted coordination branch is gone, and the operator is back on the original branch (US1.5);
     - (c) a pre-existing coordination branch is reset, not deleted.
- **Files**: `src/specify_cli/core/mission_creation.py`, `tests/core/test_mission_create_coord_seed_rollback.py` (new).
- **Validation**: all three rollback tests are green, and red at base for (a). Existing create-rollback tests (`grep -rl "_restore_git_state_after_failed_create" tests/`) stay green.
- **Edge cases**: Windows path handling in teardown (use the guarded remove helper teardown already routes through); rollback must not mask the original exception.

### Subtask T033 – R1c re-pin and R6 warning tests (the S9 check is struck; see Binding)

- **Purpose**: `tests/core/test_mission_creation_decomposition.py::test_scaffold_commit_is_single_commit_excluding_spec_md` (L290; assertion L299 `status.events.jsonl in tree_files`) pins today's defective tree. R6 covers #2533's remaining symptom.
- **Steps**:
  1. ~~**The S9 check, first.**~~ **Struck (round 4)**: `create_mission_core` defaults to `topology=COORD` (`mission_creation.py:770`), so `_init_repo`'s fixture is coordination-routed. Go straight to step 2. Step 3 does not apply.
  2. **If it resolves `coord`:** re-pin L299 to `assert f"kitty-specs/{slug}/status.events.jsonl" not in tree_files`. Keep the `meta.json` / tasks assertions as positive controls, and add an assertion that the coordination branch tree carries the log. Also add an explicit `lanes` sibling (`topology=MissionTopology.LANES`) that keeps the original assertion (C-008).
  3. **If it resolves `lanes` (or `single_branch`):** leave the test unchanged as the C-008 control, and add a coordination-routed sibling asserting the new tree.
  4. **R6.** In `tests/coordination/test_surface_resolver_coord_empty_warning.py`, add:
     - `test_no_split_brain_warning_after_new_coord_create`: CLI `agent mission create` (coordination topology), then `spec-kitty spec-commit` of `spec.md`; capture logs (`caplog`) for `_COORD_EMPTY_FALLBACK_WARNING` from `coordination/surface_resolver.py`; assert none. It is red at base: the surface is EMPTY, so `lanes_with_coord` warns.
     - `test_legacy_empty_coord_still_warns`: WP02's pre-fix builder (EMPTY surface); the warning still fires (control).
  5. The existing tests in that file stay green.
- **Files**: `tests/core/test_mission_creation_decomposition.py`, `tests/coordination/test_surface_resolver_coord_empty_warning.py`.
- **Edge cases**: that test module is marked `integration` + `git_repo`. Run it by file name only, never the directory.

### Subtask T034 – Expected-divergence predicate and `ensure_coordination_branch`

- **Purpose**: Research D6, "divergence model". After seeding, the coordination branch is ahead of the target branch **by design**. One predicate, shared by create and doctor, defines "expected".
- **Steps**:
  1. In `src/specify_cli/missions/_create.py`, beside `CoordinationBranchDiverged` (L92), add `is_expected_coordination_divergence(repo_root: Path, *, coordination_branch: str, target_branch: str, mission_dir_name: str) -> bool`. It is true when **all** of these hold:
     - `merge-base(coord, target)` exists and is reachable from the target;
     - every commit in `target..coord` touches only COORD-partition paths of this Mission (classify each changed path with `kind_for_mission_file` from `mission_runtime`, and reject any path outside `kitty-specs/<mission_dir_name>/`);
     - the target's own commits since the merge base (`coord..target`) do not touch those COORD paths.
     - Use `git rev-list` / `git diff-tree --no-commit-id --name-only -r` per commit; keep it ≤ 15 C901 via small helpers.
  2. `ensure_coordination_branch` (L195; raise at ≈L254): when the branch exists, `force_recreate` is false and it is not an ancestor of the target, return the existing branch if `is_expected_coordination_divergence(...)`; raise `CoordinationBranchDiverged` only otherwise.
  3. Write `tests/missions/test_expected_coordination_divergence.py`, table-driven over real temporary repositories:
     - coordination-only COORD commits → expected;
     - a coordination commit touching `spec.md` → not expected;
     - a coordination commit touching another Mission's paths → not expected;
     - a target commit touching this Mission's status log → not expected;
     - target ahead with unrelated commits → still expected;
     - identical tips → expected (trivial).
- **Files**: `src/specify_cli/missions/_create.py`, `tests/missions/test_expected_coordination_divergence.py` (new).
- **Validation**: predicate tests are green; existing `ensure_coordination_branch` tests (`grep -rl ensure_coordination_branch tests/`) stay green.
- **Edge cases**: shallow clones (merge-base missing → not expected, fail toward reporting); renamed paths (use `--no-renames`).
- **`ensure_coordination_branch` driven directly (post-tasks squad R-M7)**: in `tests/missions/test_expected_coordination_divergence.py`, add tests that call `ensure_coordination_branch` against an existing coordination branch:
  - (a) the expected-divergence relation returns the branch and raises no `CoordinationBranchDiverged`;
  - (b) a genuinely diverged branch (a coordination commit touching a PRIMARY path, or a target commit touching the Mission's COORD paths) still raises.

### Subtask T035 – `doctor coordination`: no false divergence finding (R20)

- **Purpose**: FR-002b. Otherwise every new Mission would be reported as `COORDINATION_BRANCH_DIVERGED_VS_TARGET`.
- **Steps**:
  1. In `_coord_branch_stale_vs_target_finding` (`_coordination_doctor.py:642`; code constant L635): after the strict-ancestor `stale` branch and before returning the diverged finding, return `None` when `is_expected_coordination_divergence(...)` holds. The function needs the Mission dir name, so thread it from the caller (check the call site).
  2. The `--fix` fast-forward arm `_fix_one_mission_coord_staleness` (L1743) is unchanged: it still fast-forwards a coordination branch strictly behind the target.
  3. Tests in `tests/specify_cli/cli/commands/test_coordination_doctor.py`:
     - `test_seeded_coord_branch_not_reported_diverged`: create via the CLI, run `spec-kitty doctor coordination --json`, assert no `COORDINATION_BRANCH_DIVERGED_VS_TARGET`;
     - `test_genuinely_diverged_legacy_still_reported`: a coordination commit touching a PRIMARY path such as `spec.md`, so the finding is present.
- **Files**: `src/specify_cli/cli/commands/_coordination_doctor.py`, `tests/specify_cli/cli/commands/test_coordination_doctor.py`.
- **Validation**: R20 is a **forward guard**. It is not red at base (the base coordination branch is not ahead), but it must turn red if T034/T035 are reverted while T031 stays. Demonstrate that once, by locally reverting T035, and note it in the Activity Log.
- **Edge cases**: the `doctor coordination` repair caller of `materialize_coord_surface_for_write` (`_coordination_doctor.py:1424`) stays as is; it repairs a worktree and is not a writer.

### Subtask T036 – NFR-001 re-measurement

- **Purpose**: Eager materialization adds one `git worktree add` and one commit. Prove it stays within budget.
- **Steps**:
  1. Reproduce the research.md "NFR-001 baseline" setup in a throwaway repository: `git init -b main`, an initial commit, `spec-kitty init . --ai claude --non-interactive`, and a commit. Copy the template fresh for each run; discard one warm-up run, then take 5 timed runs.
  2. Measure four configurations:
     - `coord` + topic: `git checkout -b topic; spec-kitty agent mission create bench-m --topology coord --branch-strategy already-confirmed --json`;
     - `coord` + pr-bound: `--topology coord --pr-bound --start-branch topic` from `main` (always pass `--topology`: `--pr-bound` alone resolves `lanes` on an unprotected primary branch, `mission_create.py:372`);
     - `lanes_with_coord` + topic;
     - `lanes_with_coord` + pr-bound: `--topology lanes_with_coord --pr-bound --start-branch topic`.
  3. Use the editable install of this lane's code (`uv sync` / `pip install -e .` in the lane worktree; stale installs give false numbers).
  4. Record the medians against the budgets: coord/topic ≤ 3.646 s, coord/pr-bound ≤ 3.641 s, lanes_with_coord/topic ≤ 3.633 s, lanes_with_coord/pr-bound ≤ 3.647 s (base median + 1.0 s, ruling Q2). Put the medians in the Activity Log for the PR.
- **Notes**: The original bench script lives in the planner's scratchpad, not in the repo; reproduce the documented commands. Do **not** add a performance test (NFR-001 is measured manually). If a budget is exceeded, profile before optimizing and report.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **S9 is unnecessary**: `create_mission_core` defaults to `topology=MissionTopology.COORD` (mission_creation.py:770); the `origin/HEAD` fallback only affects the CLI default. Record this observation and skip the empirical check.
- **`commit_for_mission(...)` needs the required positional `policy`** in every snippet.
- **Seam map**:
  - the seed runs after `write_meta` (L1336) and before `_commit_create_scaffold` (call at L1938);
  - `_emit_create_events` gets a `status_dir` parameter (read-back at L1502);
  - `_build_create_result` (L1688/L1697) receives the coordination log path as a value, so hosted fan-out reads it without re-deriving;
  - `ensure_coordination_branch` has one caller (L1302). Run its tests by name: `tests/core/test_mission_creation_topology.py`, `tests/specify_cli/cli/commands/agent/test_mission_create.py`, `tests/migration/test_birth_cutover.py`.
- **Rollback (operator decision; scout risk 5)**:
  - `mission_slug_formatted` and `mid8` are minted inside `_create_mission_core_impl` (L1875-1880), so snapshot the worktree list plus a `{branch: sha}` map in the outer `create_mission_core` (L760).
  - Tear down the coordination worktree and branch **with the slug+mid8 this create minted**.
  - `CoordinationWorkspace.teardown` (workspace.py:352) **refuses a dirty worktree** (`DestructiveOpRefused` via `guarded_worktree_remove`). Clean the seed's uncommitted files first, or use the `is_residue` hook, before teardown; then delete the branch.
  - `force_recreate` moves a pre-existing branch, so CAS-reset it to the pre-create tip.
  - With `--owned-checkout`, `rollback_root` is the owned checkout.
- The **seed lock** (owned root, `coord_mission_dir_name` key, bounded timeout), the **COORD-only restore** and the **D4 discriminator** are WP03/WP04's; this WP consumes them and must not re-derive them.
- **Doctor predicate**:
  - `_coord_branch_stale_vs_target_finding` is also reached from `tasks_finalize.py:541` (`check_and_warn_coord_staleness`).
  - Add `mission_dir_name` as **keyword-only with a default**: `tests/coordination/test_coord_staleness.py` L141/150/163 pass 3 positionals, and L189 monkeypatches it with `lambda *a`.
  - `git diff-tree` prints nothing for merge commits without `-m`, so use `--first-parent -m` or reject merges.
- **Stale pins, now owned; re-pin with a one-line rationale**:
  - `tests/core/test_mission_creation_decomposition.py::test_status_log_holds_exactly_created_and_specify_started` (L281);
  - `tests/core/test_mission_creation_fanout_commit_boundary.py` L27/L103/L117;
  - `tests/specify_cli/core/test_mission_creation_specify_started.py` L105/131/169/207 (not under `tests/core/`).
- **Probable reds to check by name**: `tests/core/test_mission_create_scaffold_rollback.py`, `tests/specify_cli/core/test_feature_creation.py`, `tests/coordination/test_materialize_coord_surface.py` and `test_mission_create_json_remediation.py`. If stale, re-pin as a declared out-of-map edit with rationale. `tests/integration/test_specify_plan_commit_boundary.py` is CI-owned: run it by name once and record the result.
- **Gate**: `test_no_write_side_rederivation.py` scans `mission_creation.py`, and its `root_walk` flags `parent.parent`; use `checkout_root`.
- **Upstream R1**: it asserts on the tip tree; change it to the history probe. Upstream has no R1b; write it.
- **C3 (analyze)**: update the `agent mission create` help text so a coordination-routed create states that it materializes the coordination worktree. Record the reference-doc delta in the activity log for WP22.
- Quick-run additions: listed in the scout's `## WP06` section; run each by name.

## Targeted test surface

```bash
uv run --frozen pytest tests/core/test_mission_create_coord_status_placement.py \
  tests/core/test_mission_creation_decomposition.py tests/core/test_mission_create_coord_seed_rollback.py -q
uv run --frozen pytest tests/missions/test_expected_coordination_divergence.py \
  tests/specify_cli/cli/commands/test_coordination_doctor.py \
  tests/coordination/test_surface_resolver_coord_empty_warning.py -q
uv run --frozen pytest tests/core/ tests/missions/ -q          # owning subsystem directories
uv run --frozen pytest $(grep -rl "ensure_coordination_branch\|_restore_git_state_after_failed_create" tests --include="test_*.py") -q
make test-fast
uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_write_surface_placement_guard.py -q
```

- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006). Run integration-marked test files by name only.
- Record commands and pass/fail counts in the Activity Log.
- Classify unrelated reds per CLAUDE.md's baseline-red gotcha (pre-existing P0, CI environment, stale install, stale venv).

## Quality gates

- C901 ≤ 15 for every touched function (`_create_mission_core_impl`, `_emit_create_events`, `_restore_git_state_after_failed_create`, `_coord_branch_stale_vs_target_finding`, `ensure_coordination_branch`, and the new predicate). Extract helpers first when near the ceiling (NFR-004).
- `ruff check`, `ruff format --check` and `mypy --strict` on changed files; no new suppressions (NFR-005).
- ≥ 90% coverage of new and changed lines, with a focused test per new branch and helper (NFR-003).
- New public symbol (`is_expected_coordination_divergence`): run `tests/architectural/test_no_dead_symbols.py`.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5440 #2533

## Definition of Done

- R1, R1b, R6 (and its control), R1c (re-pinned or sibling), R20 (and its control), and the rollback and protected-target tests are all green. R1, R1b and R6 were red on the lane base (output in the Activity Log).
- The scaffold commit carries no COORD record for coordination topologies; `lanes`/`single_branch` are byte-identical (C-008).
- The seed runs outside the bootstrap suppression; rollback removes both the worktree and the branch.
- One divergence predicate is shared by create and doctor; the genuine legacy divergence is still reported.
- NFR-001 medians are recorded and within budget. ~~The S9 observed topology is recorded~~ (struck: S9 is unnecessary).
- Gates are green.
- **FR-016 relocation (post-tasks squad R-M8)**: after R1/R1b are GREEN, fold them into the owning create test module (`tests/core/test_mission_creation_decomposition.py`, owned here; keep the test names). Delete the adopted `tests/core/test_mission_create_coord_status_placement.py`, and remove its "stays red on main" docstring and regression marker.
- `ensure_coordination_branch` tests (R-M7) and the protected-primary default-path parametrization (R-m4) are green.

## Risks & Mitigations

- **Order of operations in create.** Seeding before the target scaffold commit means a later scaffold failure must roll back the seed (T032). Keep the coordination commit after `_build_create_meta` and before `_commit_create_scaffold`, and capture the pre-create coordination tip for the CAS reset.
- **Existing create tests asserting the old tree.** Run every create test file (grep `create_mission_core` under `tests/core/`). If a test pins the defective tree, re-pin it with a one-line rationale (Standing Order 4: judge the test; stale → re-pin).
- **Interim doctor noise.** Between T031 and T035, doctor reports divergence. Land both in this WP.
- **Performance.** If the budget is breached, look first at duplicate `git` subprocesses in `write_dir` (one probe per state).

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies red→green: R1, R1b and R6 RED on the WP's lane base before the fix commits, GREEN on the final commit. R20 demonstrated as a forward guard.
- Verify the history probe (not the tip tree) in R1, and that the positive control (`meta.json` on the target) is present.
- Verify the protected-target and rollback-after-seed tests exercise real refs (no mocked git for the assertions).
- Verify C-008 controls exist for `lanes`.
- Check the recorded NFR-001 medians. ~~and the S9 topology note~~ (struck).

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
- 2026-10-01T20:37:37Z – claude – shell_pid=245497 – Follow-up per coordinator: fixed WP06's own integration-test blast radius the coordinator flagged as mine, not another WP's. 7 tests across test_accept_matrix_coord_partition.py (5, incl. WP05 B1 data-loss guard test_matrix_lands_on_coord_via_all_three_write_paths_no_stale_copy) and test_issue_4863_merge_abort_no_state.py (2) -- all classified as stale 'coordination worktree materialized lazily' fixture assumptions T031 retires, re-pinned preserving protective intent (never weakened), proven non-vacuous (red pre-T031 in a scratch worktree, green post-T031). Broader grep -rlE blast radius over tests/integration (-n 3): 151+29 additional tests green. Committed separately from the production fix (86f8387d5e, citing T031). WP06 remains in for_review.
- 2026-10-01T21:38:23Z – unknown – Cycle 2: fixed all 5 reviewer findings (B1-B5). B1: resume probe now resolves status.events.jsonl via placement_seam(...).read_dir(STATUS_STATE) instead of a hard-coded feature_dir path; restored specific deleted-branch assertion in test_mission_created_persistence_failure_is_nonzero_and_probe_recoverable. B2: coord_rollback_holder is now appended BEFORE write_dir() runs, not after it returns; rollback coverage parametrized over all 3 injection points (inside write_dir seed, emit_create_events, commit_coord_create_events). B3: reverted formatting-only hunks in all 5 ruff-format-exempt files (_coordination_doctor.py, missions/_create.py, test_coord_staleness.py, test_surface_resolver_coord_empty_warning.py, test_coordination_doctor.py); pyproject.toml untouched; test_ruff_format_exclude_ratchet.py green. B4: #4863 abort re-pin now also compares the coordination WORKTREE's on-disk status.events.jsonl bytes and asserts the root checkout never regains the file. B5: --owned-checkout + coord/lanes_with_coord topology now refused at create with ActionContextError(OWNED_TOPOLOGY_UNSUPPORTED); fixed the inaccurate byte-identical-fall-through docstring claim. All fixes proven red-first via scratch detached worktrees off 86f8387d5e. Named architectural gates (-n 3): only the 3 inherited WP07-assigned reds remain (census coord_seed, walker coord_seed:420, destructive-op _dirty_paths_in_checkout) -- no new reds. make test-fast: 2172 passed, 5 skipped. NFR-001 medians unchanged (coord/topic 1.545s, coord/pr-bound 1.591s, lanes_with_coord/topic 1.597s, lanes_with_coord/pr-bound 1.605s; same-session lanes control 1.528s). 8 commits, test re-pins separated from production fixes.
- 2026-10-01T22:26:40Z – unknown – Cycle 3: fixed B5' (ruling reversed) — the OWNED_TOPOLOGY_UNSUPPORTED refusal broke the FR-022 ratchet (TestFr022CoordinationTwin x3, test_guard_uses_owned_checkout_head[committed-owned]). Removed the refusal. Made the owned arm byte-identical to pre-WP06 instead: _scaffold_mission_dir and _build_create_result now ALSO gate their coordination-routed branches on owned is None, so an owned lanes_with_coord/coord create scaffolds and commits status.events.jsonl in its own PRIMARY dir exactly as at base (e7b085d26c) -- carrying MissionCreated, committed in the owned checkout's own HEAD. Recorded this as a named residual (INV-COORD-HOME): an owned coordination create's status log is never seeded onto the coordination surface itself, follow-up tracked separately, not fixed here. Removed the refusal's test, replaced with a pin: test_owned_checkout_with_coordination_topology_scaffolds_status_log_at_base_shape, proven red at 6a2c520cf9 via scratch detached worktree. N1: dropped the unused noqa:BLE001 (BLE not enabled, RUF100). N2: documented the UNMATERIALIZED-coordination-worktree resume-probe residual (reports malformed, acceptable). All 4 previously-broken tests now green: TestFr022CoordinationTwin x3 + unborn_head committed-owned. Full verification: tests/core/ + tests/missions/ + tests/coordination/ + test_coordination_doctor.py + tests/integration/ (2685 passed, 11 pre-existing baseline reds unrelated to WP06 confirmed red at 6a2c520cf9 too: test_surface_translation_seam.py x4, test_documentation_runtime_walk.py x4, test_research_runtime_walk.py x3) + test_owned_lifecycle_acceptance_next.py + test_mission_creation_unborn_head.py + #4863 (47 passed). Named architectural gates (-n 3): only the 3 inherited WP07-assigned reds remain (census coord_seed, walker coord_seed:420, destructive-op _dirty_paths_in_checkout). make test-fast: 2172 passed, 5 skipped (unchanged from cycle 2). ruff check/format and mypy --strict clean; pyproject.toml untouched. 3 commits, test re-pin before production fix (red-first), each citing B5'/N1/N2.
