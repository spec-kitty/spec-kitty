# Work Packages: Lane Branch Naming Authority

**Inputs**: Design documents from `/kitty-specs/lane-branch-naming-authority-01M3EVC4/`
**Prerequisites**: plan.md (rev 2), spec.md (rev 3), research.md (Part A naming authority, Part B #5113 D1–D7), data-model.md, quickstart.md

**Tests**: Required. The spec mandates red-first regressions (FR-012, charter ATDD-first / DIRECTIVE_034 / DIRECTIVE_041). Each diverging site's test must fail on the pre-change code **through its pre-existing entry point**. Fixtures use real temporary git repositories. Divergent-shape fixtures create lanes through the allocator (`allocate_lane_worktree` / `predict_lane_worktree`). They never compose lane names with a Mission identity.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable.

**Prompt Files**: Each work package has a prompt file in `tasks/`. This file is the high-level checklist; implementation detail lives in the prompt files.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can run in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.
- **Numbering follows execution order across WPs, not WP number.** Wave 1 is {WP01, WP04, WP05, WP06, WP09}. Wave 2 is {WP02, WP10}. Wave 3 is WP03, wave 4 is WP07, wave 5 is WP11 and wave 6 is WP08. WP11 keeps the IDs T052–T055 it inherited from WP07. So WP04's subtasks (T007–T012) come before WP02's (T030–T036).

## Path Conventions

- Single project: `src/specify_cli/`, `src/runtime/`, `src/mission_runtime/`, `tests/`.

## Deviations from plan.md (recorded here; plan intent preserved)

1. **WP09 split into WP09 + WP10** (#5113). The unsplit #5113 slice needed 11 subtasks, and its files collided with WP05 (`_coordination_doctor.py`).
   - **WP09** is materialize-before-write plus the structured CLI errors (FR-013).
   - **WP10** is the `doctor coordination --fix` missing-worktree fixer plus the truthful remedy text at every non-`surface_resolver` emitter (FR-014).
   - WP10 depends on WP09. Neither depends on any naming WP (spec: #5113 is an independent slice).
2. **The signature cutover must be atomic (verified against live code).**
   - Today `worktree_dir_name(mission_slug, *, mission_id, lane_id)` and `worktree_path(repo_root, mission_slug, *, mission_id, lane_id)` take `mission_id` as a **required** keyword. Upstream WPs therefore **cannot drop** it before the cutover: dropping it raises `TypeError`.
   - Upstream WPs fix divergent sites by passing `mission_id=None` (the created form) or by routing through `predict_lane_worktree`, which has no identity parameter. They drop the keyword only on `lane_branch_name`, where it is optional.
   - WP07 removes the parameter and every residual `mission_id=None` in src/tests in one commit, so the tree is never broken.
   - This corrects research.md Part A §7 ("WP01–WP04 each drop the `mission_id=None` kwargs in their own files").
   - The pure kwarg-drop files (`workspace/context.py`, `orchestrator_api/commands.py`, `coordination/status_transition.py`, `cli/commands/agent/tasks_parsing_validation.py`, `cli/commands/mission_type.py`, `lanes/merge.py`, `lanes/implement_support.py`) are therefore owned by **WP07**, not WP04.
3. **Single gate file** (PD-11 supersedes the plan's Structure Decision / quickstart). WP11 extends `tests/architectural/test_no_worktree_name_guess.py`. There is no sibling `test_lane_naming_authority_gate.py`. The quickstart line naming that file is stale: run `test_no_worktree_name_guess.py` instead.
4. **ADR file name.** `docs/adr/3.x/2026-09-26-1-*` already exists (`2026-09-26-1-ci-coverage-honesty.md`), so the ADR from PD-15 is `docs/adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md`.
5. **FR-005 H5 moved from WP03 into WP02.** WP02 is the single owner of `merge/executor.py`.
6. **The `lanes/recovery.py` Mission-branch fallback (PD-13) moved from WP03 into WP04.** WP04 is the single owner of `lanes/recovery.py`.
7. **The `lanes/branch_naming.py` module docstring (PD-15) is updated in WP07** as part of the signature edit. WP08 owns only `docs/`, `CHANGELOG.md`, `CLAUDE.md` and `AGENTS.md`.
8. **WP07 split into WP07 + WP11** (post-tasks squad, orchestrator-adjudicated).
   - **WP07** (T048–T051) is the atomic signature removal in `lanes/branch_naming.py`, every residual caller in src and tests, and the golden re-pins, in **one commit**. It runs the existing `tests/architectural/test_no_worktree_name_guess.py` **unchanged** and green. Its out-of-map clause is an explicit file table (computed at HEAD `8900c2cb`: 14 src files incl. `branch_naming.py`, 19 test files); any scan hit outside it ⇒ STOP and report.
   - **WP11** (T052–T055, IDs kept) is the gate-pinned sites (`core/vcs/detection.py`, the `_coordination_doctor.py` drift matcher, the `lifecycle_sync.py` `-unknown` placeholder), the existing allow-list shrink, the four new gate legs, the self-test and the targeted architectural gate run (operator: never the full `tests/architectural/` suite). Its allow-lists are capped numerically in its prompt (compose 1, match 5, def-use 1); any extra entry ⇒ STOP.
   - WP07 no longer depends on WP10 (the drift matcher moved to WP11). WP08 now depends on WP11.

## Ownership-collision resolutions (every file has exactly one owner in `owned_files`)

| File | Owner | Other editor | Resolution |
|---|---|---|---|
| `src/specify_cli/merge/executor.py` | WP02 | (plan: WP03 H5) | H5 (FR-005) moved into WP02. WP03 only runs executor code through the end-to-end tests. |
| `src/specify_cli/lanes/recovery.py` | WP04 | (plan: WP03 fallback) | The `_resolve_mission_branch` typed refusal (PD-13) moved into WP04. WP04 also routes its three `mission_id=None` worktree sites through `predict_lane_worktree`, so WP07 edits the file only if WP04 logged an import-cycle fallback (then one keyword token per logged site). |
| `src/specify_cli/lanes/branch_naming.py` | WP05 | WP07 | WP05 owns it (additive `_LANE_ID_RE`, parsers, `is_lane_branch`). WP07's signature removal and module docstring there are a **documented out-of-map edit**, serialized by WP07 ← WP05. It cannot move: the removal must be atomic with its callers (deviation 2). |
| `src/specify_cli/cli/commands/_coordination_doctor.py` | WP10 | WP11 | WP10 owns it (#5113 fixer + finding extras). The FR-008 sparse-checkout drift matcher swap (`_check_lane_sparse_checkout_drift`, one line: `startswith(f"{mission_slug}-lane-")` → `lane_id_for_worktree_dir(...)`) moved from WP05 to WP11 as a **documented out-of-map edit**, serialized by WP11 ← WP10. This keeps #5113 free of naming dependencies, and puts the edit in the WP whose gate match leg requires it. |
| `src/specify_cli/coordination/surface_resolver.py` | WP09 | — | WP09 adds the helper and rewrites the `CoordinationWorktreeUnmaterialized.next_step` remedy. WP10 does not touch the file; its end-to-end remedy test parses the text WP09 wrote. |
| `tests/integration/test_merge_lane_planning_data_loss.py` | WP02 | WP01/WP03 only *run* it | WP02 migrates the `TestRetentionConstraintSurvivesCleanup` identity-keyed `worktree_path` calls. **No WP may edit the `TestPlanningArtifactReachesTarget` class** (FR-012). |
| `src/specify_cli/core/vcs/detection.py` | WP11 | (plan: WP05) | Its `parse_mission_slug_from_branch(f"kitty/mission-{worktree_name}")` line is a **content-pinned carve-out** of the existing gate `tests/architectural/test_no_worktree_name_guess.py` (`_NAME_COMPOSE_BASELINE_RAW_MATCHES = 5`). Changing it in WP05 would turn that gate's staleness guard red in WP05's lane, and the gate is WP11's. WP11 owns both, and changes the site and the allow-list in one commit. |
| `src/specify_cli/lanes/lifecycle_sync.py` `-unknown` error-path placeholder | WP04 (file) | WP11 | The same content-pinned-carve-out reason. WP04 deletes the probe but leaves that one line byte-identical. WP11 removes it as a **documented out-of-map edit** together with the allow-list shrink (serialized by WP11 ← WP04). |
| `tests/architectural/test_no_worktree_name_guess.py`, `tests/architectural/_baselines.yaml`, `tests/architectural/test_ratchet_baselines.py` | WP11 | WP07 only *runs* the gate | WP07 must leave the gate unchanged and green. WP11 extends it, registers the three new allow-list baselines, and wires them into the ratchet meta-test. |
| `merge/executor.py`, `acceptance/__init__.py`, `lanes/lifecycle_sync.py`, `lanes/recovery.py` residual `mission_id=None` | WP02 / WP04 | WP07 | Only if the owner logged an import-cycle fallback: WP07 removes that one keyword token per logged site, as a documented out-of-map edit. |

Out-of-map edits allowed:
- WP07 → `lanes/branch_naming.py` (signature removal, internal keyword tokens, module docstring), plus the logged fallback tokens in the table row above. Nothing else: the WP07 prompt lists every file explicitly, and any AST-scan hit outside that list ⇒ STOP and report.
- WP11 → `cli/commands/_coordination_doctor.py` (one-line drift matcher) and `lanes/lifecycle_sync.py` (one-line placeholder).
- Any other out-of-map edit needs a one-line rationale in the WP's Activity Log.

---

## Work Package WP01: Reconciliation claim uses the created lane branch (Priority: P1) 🎯 MVP

**Goal**: The reconciliation claim (approved-commit attribution, canceled-lane exclusion, authored-blob spine) resolves each lane's **created** branch. An approved, non-canceled lane whose created branch is missing refuses with a message naming that branch. This WP also ships the shared real-allocator divergent-shape fixture.
**Independent Test**: `tests/merge/test_reconciliation_divergent.py` covers the 4 shapes, canceled plus survivor, and a missing created branch. It is red on HEAD and green after.
**Prompt**: `/tasks/WP01-reconciliation-claim-created-branch.md` (~322 lines)
**Requirement Refs**: FR-001, FR-003, FR-012

### Included Subtasks

T001 Build shared real-allocator divergent-shape fixture `tests/merge/_divergent_shapes.py` (4 shapes + canceled/missing-branch variants) (WP01)
T002 Red-first claim tests over the 4 shapes, canceled+survivor, and missing created branch in `tests/merge/test_reconciliation_divergent.py` (WP01)
T003 Route `_lane_branch_for` to the created name (drop `mission_id`) (WP01)
T004 Add `_unresolvable_approved_lane_branches` created-branch existence refusal in `build_approved_wp_set` (PD-5); probe `GitProbeError` tolerance unchanged (FOLD-3) (WP01)
T005 Migrate `tests/merge/test_reconciliation.py` (15 identity-passing calls) to allocator-built lanes (WP01)
T006 Quality gates, blast radius, assert `TestPlanningArtifactReachesTarget` green unedited (WP01)

### Implementation Notes

- Fixture first (T001), then red tests (T002), then the fix (T003–T004), then migration (T005).

### Parallel Opportunities

- The whole WP runs in wave 1, parallel with WP04, WP05, WP06 and WP09.

### Dependencies

- None.

### Risks & Mitigations

- The strict refusal could fire on a lane legitimately deleted after consolidation (resume or post-cleanup). Restrict it to approved, non-planning, non-canceled lanes. Assert on the resume path in WP02/WP03.
- The only strict arm is the created-branch existence check. `_lane_tip_commits` / `_lane_first_parent_spine` keep their `GitProbeError` tolerance; `tests/merge/test_reconciliation.py::test_build_claim_tolerates_unresolvable_lane_probe` stays green and unmodified.
- WP01 alone turns `TestPlanningArtifactReachesTarget` green (DoD item); WP03 re-asserts it.

---

## Work Package WP04: Lifecycle probe removal, acceptance roots, recovery Mission-branch refusal (Priority: P1)

**Goal**:
- Delete the dual-name probe in `lanes/lifecycle_sync.py` (FR-007).
- Fix the divergent acceptance lane-source-root site (PD-8).
- Route `lanes/recovery.py` worktree lookups through `predict_lane_worktree`.
- Make `_resolve_mission_branch` refuse with a typed `BranchIdentityUnresolved` instead of crashing on an invalid identity (PD-13).

**Independent Test**: On a divergent shape, lifecycle sync attaches the created branch and acceptance finds the lane source root. A recovery Mission-branch fallback with an identity shorter than 8 characters raises `BranchIdentityUnresolved`.
**Prompt**: `/tasks/WP04-lifecycle-acceptance-recovery.md` (~258 lines)
**Requirement Refs**: FR-006, FR-007, FR-011, FR-012

### Included Subtasks

T007 [P] Red-first lifecycle-sync tests on a divergent shape (created branch attached, no probe/HEAD fallback, invalid identity < 8 chars crashes the probe on HEAD) (WP04)
T008 Delete `_resolve_lane_branch` / `_git_ref_exists` / HEAD fallback; route `sync_lane_after_coordination_commit` through `predict_lane_worktree`; leave the `-unknown` error-path placeholder for WP11 (WP04)
T009 [P] Red-first + fix `acceptance/__init__.py::_approved_lane_source_roots` (created lane root) (WP04)
T010 Route `lanes/recovery.py` worktree lookups (3 sites) through `predict_lane_worktree` (behaviour-preserving) (WP04)
T011 `_resolve_mission_branch` typed refusal on invalid identity (PD-13) + test (WP04)
T012 Migrate owned tests + quality gates + blast radius (WP04)

### Dependencies

- None.

### Risks & Mitigations

- A function-local import of `predict_lane_worktree` could create an import cycle. If it does, pass `mission_id=None` instead and record the site in the Activity Log; WP07 removes that token at cutover.

---

## Work Package WP05: Match sites through the authority's parsers + one lane-id grammar (Priority: P2)

**Goal**:
- Add a single `_LANE_ID_RE` fragment (`lane-[a-z]+`), and rebuild every lane regex from it.
- Add the parsers `parse_lane_worktree_dir` and `lane_id_for_worktree_dir`.
- Make `is_lane_branch` accept the plain-legacy grammar.
- Route five of the seven FR-008 match sites through the parsers: sparse-checkout (plus its hand-rolled compose), status doctor, live-work bindings, commit guard and merge-resolve. The coordination-doctor drift matcher and VCS detection are WP11's (see the ownership table).

**Independent Test**: `tests/specify_cli/lanes/test_lane_naming_parsers.py` shows the parsers recognize all three grammars. `tests/specify_cli/lanes/test_lane_match_sites.py` covers each site: a legacy orphan found, a plain-legacy branch recognized by the commit guard, and `expected_branch_for` on an `NNN-` coordination Mission.
**Prompt**: `/tasks/WP05-match-sites-parsers-grammar.md` (~316 lines)
**Requirement Refs**: FR-008

### Included Subtasks

T013 Add `_LANE_ID_RE` and rebuild `_LEGACY_LANE_RE` / `_PLAIN_LEGACY_LANE_RE` / `_NEW_LANE_RE` from it (byte-identical parse results for existing grammar) (WP05)
T014 Add `parse_lane_worktree_dir` and `lane_id_for_worktree_dir`; fix `is_lane_branch` for plain-legacy; parser unit tests over literal directory names (WP05)
T015 [P] `git/sparse_checkout.py` `_ManagedLanePolicy.matches_path` + `expected_branch_for` (hand-rolled compose → `lane_branch_name`) (WP05)
T016 [P] `status/doctor.py::check_orphan_workspaces` glob → `iterdir` + `lane_id_for_worktree_dir` (WP05)
T017 [P] `live_work/bindings.py` `_WORKTREE_DIR_RE` → `parse_lane_worktree_dir` + recomposition confirm (WP05)
T018 [P] `policy/commit_guard.py` → `is_lane_branch` (red case: multi-letter lane ids); delete the redundant regex in `merge/resolve.py` (WP05)
T019 Site regression tests + quality gates + blast radius (WP05)

### Dependencies

- None. The `_coordination_doctor.py` drift matcher and `core/vcs/detection.py` are **not** in this WP (see the ownership table; WP11 does both).

### Risks & Mitigations

- Behaviour changes hide inside "re-routes" (Risk 2 in plan.md). Each one gets a named test.

---

## Work Package WP06: Re-finalize preserves the recorded Mission branch (Priority: P1)

**Goal**: `compute_and_write_lanes` keeps `previous_lanes.mission_branch` on re-finalize (FR-011, PD-6/13). `status/aggregate.py` prefers the manifest Mission branch before recomposing, and turns an invalid-identity `ValueError` into a typed refusal. FR-010 lane-id stability is re-verified.
**Independent Test**: Finalize, backfill, re-finalize: `mission_branch` is byte-identical. The first finalize is unchanged. `tests/lanes/test_lane_identity.py` stays green, unedited.
**Prompt**: `/tasks/WP06-refinalize-mission-branch.md` (~242 lines)
**Requirement Refs**: FR-010, FR-011, FR-012

### Included Subtasks

T020 [P] Red-first re-finalize test through the real finalize entry point (`compute_and_write_lanes`) (WP06)
T021 Add `_preserved_mission_branch` in `lanes/compute_and_persist.py` (`compute_lanes` untouched) (WP06)
T022 `status/aggregate.py` destination ref prefers the manifest `mission_branch`, with a typed refusal on invalid identity (WP06)
T023 FR-010 re-verification + quality gates + blast radius (WP06)

### Dependencies

- None.

---

## Work Package WP09: #5113 — Materialize the coordination worktree before a decision write (Priority: P2)

**Goal**:
- Add `materialize_coord_surface_for_write` in `coordination/surface_resolver.py`, and call it in `decisions/service.py` (`open_decision`, `_terminal_command`) before any ledger write.
- The CLI decision verbs render `StatusReadPathNotFound` as structured JSON.
- `CoordinationWorktreeUnmaterialized.next_step` names `spec-kitty doctor coordination --mission <slug> --fix`.

**Independent Test**: `tests/specify_cli/cli/commands/test_decision_fresh_coord_5113.py` covers five cases:
- open materializes and returns an id;
- resolve materializes;
- a materialization failure leaves every file, the coordination branch tip and the worktree list byte-identical;
- a remote-only branch refuses before any write;
- structured JSON is emitted with no traceback.

**Prompt**: `/tasks/WP09-decision-materialize-before-write.md` (~290 lines)
**Requirement Refs**: FR-013, FR-014, C-006

### Included Subtasks

T024 [P] Red-first integration tests on a real fresh coordination Mission (`test_decision_fresh_coord_5113.py`) (WP09)
T025 `materialize_coord_surface_for_write` helper + per-arm unit tests (`tests/coordination/test_materialize_coord_surface.py`) (WP09)
T026 Wire the helper into `open_decision` and `_terminal_command` (after dry-run, before the ledger lock); pre-resolve the events path (WP09)
T027 Structured CLI error handler for `StatusReadPathNotFound` in `cli/commands/decision.py` (WP09)
T028 Rewrite the `CoordinationWorktreeUnmaterialized.next_step` remedy; update pinned tests (WP09)
T029 Quality gates + blast radius (cold-import, CLI error surface, layer rules) (WP09)

### Dependencies

- None (independent slice).

---

## Work Package WP02: Executor stages use the created lane name; resume guard armed (Priority: P1)

**Goal**:
- Add executor helpers `_created_lane_branch` / `_created_lane_worktree`, keyed on the manifest slug.
- Pre-interrupt tip capture keys tips by the created branch and skips fully-canceled lanes (FR-004).
- The resume H5 check refuses an unanchored tip record on the coordination topology (FR-005, PD-4).
- The safety preflight inspects created worktrees (FR-006).
- Cleanup is tidied first, then removes the created worktrees and branches.

**Independent Test**: `tests/merge/test_executor_lane_naming.py` asserts, per stage:
- tips are keyed by the created name;
- an unanchored or old-form record refuses, naming `--abort`;
- canceled-only and planning-only Missions are exempt;
- a dirty divergent worktree refuses;
- no lane worktree or branch is orphaned.

**Prompt**: `/tasks/WP02-executor-created-lane-names.md` (~293 lines)
**Requirement Refs**: FR-001, FR-004, FR-005, FR-006, FR-012

### Included Subtasks

T030 `_created_lane_branch(lanes_manifest, lane_id)` / `_created_lane_worktree(main_repo, mission_slug, lane_id)` helpers; route `_phase_merge_lanes` (behaviour-preserving) (WP02)
T031 FR-004 red-first + fix `_capture_pre_interrupt_lane_tips` (created key; skip fully-canceled lanes) (WP02)
T032 FR-005 red-first + H5 `_unanchored_lane_branches` in `_enforce_resume_anchor_integrity` (coord topology + persisted anchor only) (WP02)
T033 FR-006 red-first + fix `_pre_mutation_safety_preflight` (created worktrees; retire the identity parameter if unused) (WP02)
T034 Tidy-first: extract `_remove_lane_worktrees` / `_delete_lane_branches` from `_phase_cleanup_worktrees_and_branches` (no behaviour change) (WP02)
T035 Red-first + fix cleanup to remove created worktrees/branches (retention honoured) (WP02)
T036 Migrate owned executor tests + quality gates (`_run_lane_based_merge` ≤ 15; `"spec-kitty merge --abort"` hoisted to a constant) + blast radius (WP02)

### Dependencies

- Depends on WP01 (shared divergent-shape fixture; claim fix needed for merge-path tests).

---

## Work Package WP10: #5113 — `doctor coordination --fix` materializes; every remedy is truthful (Priority: P2)

**Goal**:
- `spec-kitty doctor coordination --mission <slug> --fix` gains a missing-worktree fixer (`COORDINATION_WORKTREE_MISSING`).
- Every other emitter of the unmaterialized-coordination remedy is first classified as unmaterialized or husk. The unmaterialized ones then name that command: `runtime_bridge`, `write_target_degrade`, `implement_cores`, `implement`, `mission_record_analysis`.
- Help text and goldens are updated.

**Independent Test**: `tests/specify_cli/cli/commands/test_coordination_remedy_5113.py` is parametrized over every emitter classified *unmaterialized*: it triggers each through its real entry point on a fresh coordination Mission, extracts the named command, runs it (the remote-only `write_target_degrade` steps in order), and asserts the coordination worktree exists.
**Prompt**: `/tasks/WP10-doctor-fix-truthful-remedy.md` (~303 lines)
**Requirement Refs**: FR-014

### Included Subtasks

T037 Red-first remedy round-trip test parametrized over every unmaterialized emitter (`test_coordination_remedy_5113.py`) (WP10)
T038 `_apply_missing_worktree_fix` in `_coordination_doctor.py` + finding extras (`mission_slug`, `mid8`) + dispatch registration (WP10)
T039 Missing-worktree `next_step` leads with the doctor command; `--fix` help in `doctor.py`; `run_coordination_health` docstring (WP10)
T040 [P] Classify + rewrite remedy text in `runtime_bridge.py`, `write_target_degrade.py` (WP10)
T041 [P] Classify + rewrite remedy text in `implement_cores.py`, `implement.py`, `agent/mission_record_analysis.py` (WP10)
T042 Update pinned tests + quality gates + blast radius (WP10)

### Dependencies

- Depends on WP09 (the fixer calls `materialize_coord_surface_for_write`; the remedy test parses WP09's text).

---

## Work Package WP03: End-to-end divergent merges + merge preflight Mission-branch fallbacks (Priority: P1)

**Goal**:
- Prove SC-001 (4/4 divergent shapes merge end to end, with no traceback) and SC-002 (no orphans; retention honoured).
- Pin the upgrade-resume refusal (PD-14).
- Make the `merge/preflight.py` Mission-branch fallbacks prefer the recorded value, with a typed refusal (PD-13).
- Re-assert `TestPlanningArtifactReachesTarget` green without editing it (WP01 already made it green; this is a regression guard).

**Independent Test**: `tests/merge/test_merge_divergent_end_to_end.py` plus the unedited `TestPlanningArtifactReachesTarget`.
**Prompt**: `/tasks/WP03-end-to-end-divergent-merge.md` (~246 lines)
**Requirement Refs**: FR-003, FR-005, FR-011, FR-012

### Included Subtasks

T043 End-to-end `spec-kitty merge` over the 4 divergent shapes (SC-001), with a mandatory red run against the mission merge-base (WP03)
T044 Orphan and retention assertions after each merge (SC-002, US1 AS5) (WP03)
T045 Resume upgrade pin: old-form tip record → FR-005 refusal naming `merge --abort`; canceled-only/planning-only exempt end to end (WP03)
T046 `merge/preflight.py` fallbacks (`target_branch_sync_remediation`, `_check_mission_branch`) prefer recorded value + typed refusal; migrate `test_mid8_embedded_preflight.py` (WP03)
T047 `TestPlanningArtifactReachesTarget` re-asserted green unedited + residual-failure triage + quality gates (WP03)

### Dependencies

- Depends on WP01, WP02, WP04.

---

## Work Package WP07: Atomic lane-naming signature cutover (Priority: P1)

**Goal**:
- Remove `mission_id` from `lane_branch_name`, `worktree_dir_name` and `worktree_path` atomically with every residual caller in src and tests, in **one commit** (FR-002, PD-1).
- Re-pin the identity-injected lane/worktree goldens (PD-3), and migrate the residual test calls.
- Leave the existing gate `tests/architectural/test_no_worktree_name_guess.py` **unchanged** and green.
- Out-of-map edits are bounded by an explicit file table in the prompt; any AST-scan hit outside it ⇒ STOP and report.

**Independent Test**:
- The signature test is red before the cutover and green after.
- The alias-aware AST scan reports 0 lane-naming calls with `mission_id` in `src/` and `tests/`.
- The unchanged `test_no_worktree_name_guess.py` is green.

**Prompt**: `/tasks/WP07-signature-cutover-and-gate.md` (~312 lines)
**Requirement Refs**: FR-001, FR-002, NFR-001

### Included Subtasks

T048 Red-first signature test (no `mission_id` on the lane surface) (WP07)
T049 Atomic cutover: remove the parameter in `branch_naming.py` (out-of-map, documented), update the module docstring, then drop every residual `mission_id=None` in src (explicit file list) (WP07)
T050 Re-pin identity-injected lane/worktree goldens (PD-3) + add divergent-shape rows (WP07)
T051 Migrate residual test call sites (AST re-count to 0) (WP07)

### Dependencies

- Depends on WP03, WP04, WP05, WP06. (WP10 is no longer a dependency: the `_coordination_doctor.py` edit moved to WP11.)

---

## Work Package WP11: Gate legs, gate-pinned sites and allow-list shrink (Priority: P1)

**Goal**:
- Route the gate-pinned sites: `core/vcs/detection.py` → `parse_lane_worktree_dir`, the `_coordination_doctor.py` drift matcher → `lane_id_for_worktree_dir` (out-of-map), and remove the `lifecycle_sync.py` `-unknown` placeholder (out-of-map). Shrink the existing allow-list in the same commit.
- Extend `test_no_worktree_name_guess.py` with the signature, compose, match and def-use legs, plus a self-test (FR-009, PD-11).
- Register the new allow-lists in `_baselines.yaml` and wire them into `test_ratchet_baselines.py`. The caps are fixed in the prompt: compose **1** (`_next_free_lane_id`), match **5** (the plan Gate Baseline sites), def-use **1** (`surface_resolver.py::_coord_mid8`). Any extra entry ⇒ STOP and report.
- Run only the targeted architectural tests covering touched files (operator instruction: never the full `tests/architectural/` suite).

**Independent Test**:
- The gate is green at 0 compose sites outside the authority, with allow-list sizes equal to the caps.
- Each injected offender form turns the gate red.

**Prompt**: `/tasks/WP11-gate-legs-and-allowlist-shrink.md` (~257 lines)
**Requirement Refs**: FR-008, FR-009, NFR-003

### Included Subtasks

T052 Gate-pinned sites: `core/vcs/detection.py` → `parse_lane_worktree_dir`; `_coordination_doctor.py` drift matcher → `lane_id_for_worktree_dir` (out-of-map); `lifecycle_sync.py` `-unknown` placeholder removed (out-of-map); shrink the existing allow-list (WP11)
T053 Extend `test_no_worktree_name_guess.py`: signature, compose, match and def-use legs; capped allow-lists in `_baselines.yaml` + `test_ratchet_baselines.py`; docstring rationale rewritten (WP11)
T054 Gate self-test: injected literal / renamed-variable / `"-".join` / `%`-`.format` / constant-held forms all red (WP11)
T055 Targeted architectural gates + quality gates + blast radius (WP11)

### Dependencies

- Depends on WP07 (signature leg), WP04 (`lifecycle_sync.py` out-of-map edit), WP05 (parsers) and WP10 (`_coordination_doctor.py` out-of-map edit).

---

## Work Package WP08: ADR, living docs, CHANGELOG (Priority: P3)

**Goal**:
- Record the decision in ADR `docs/adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md`.
- Update `docs/architecture/execution-lanes.md` §Naming and `docs/architecture/git-worktrees.md`.
- Update the migrations docs, and the Mission-identity naming line in `CLAUDE.md` / `AGENTS.md`.
- Add a CHANGELOG entry.

**Independent Test**: The docs describe the shipped behaviour, links resolve, and `tests/architectural/test_no_legacy_terminology.py` is green.
**Prompt**: `/tasks/WP08-adr-living-docs-changelog.md` (~242 lines)
**Requirement Refs**: FR-001, FR-002, FR-011, FR-014

### Included Subtasks

T056 ADR `2026-09-26-2-lane-naming-keyed-on-creation-input.md` (WP08)
T057 [P] `docs/architecture/execution-lanes.md` §Naming + `docs/architecture/git-worktrees.md` (WP08)
T058 [P] `docs/migrations/mission-id-canonical-identity.md` + `docs/migrations/legacy-to-coordination.md` (WP08)
T059 [P] `CLAUDE.md` / `AGENTS.md` Mission-identity naming line (WP08)
T060 CHANGELOG entry + doc validation (WP08)

### Dependencies

- Depends on WP11 (and, through it, on WP07).

---

## Dependency & Execution Summary

```
wave 1: WP01  WP04  WP05  WP06  WP09      (no deps)
wave 2: WP02 (←WP01)        WP10 (←WP09)
wave 3: WP03 (←WP01, WP02, WP04)
wave 4: WP07 (←WP03, WP04, WP05, WP06)
wave 5: WP11 (←WP07, WP04, WP05, WP10)
wave 6: WP08 (←WP11)
```

- **Critical path**: WP01 → WP02 → WP03 → WP07 → WP11 → WP08.
- **MVP**: WP01 + WP02 + WP03. These give the #5108 fix end to end: a legitimate divergent merge completes and the resume guard is armed.
- **#5113** (WP09 → WP10) is independent of the naming work. It gates WP11 only through the one-line `_coordination_doctor.py` edit.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01, WP02, WP07, WP08 |
| FR-002 | WP07, WP08 |
| FR-003 | WP01, WP03 |
| FR-004 | WP02 |
| FR-005 | WP02, WP03 |
| FR-006 | WP02, WP04 |
| FR-007 | WP04 |
| FR-008 | WP05, WP11 |
| FR-009 | WP11 |
| FR-010 | WP06 |
| FR-011 | WP03, WP04, WP06, WP08 |
| FR-012 | WP01, WP02, WP03, WP04, WP06 |
| FR-013 | WP09 |
| FR-014 | WP09, WP10, WP08 |
| NFR-001 | WP07 |
| NFR-002..005 | every code WP (gates section of each prompt) |
| NFR-003 | WP11 |
| C-006 | WP09 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Divergent-shape fixture builder | WP01 | P1 | No |
| T002 | Red-first claim tests | WP01 | P1 | No |
| T003 | `_lane_branch_for` → created name | WP01 | P1 | No |
| T004 | Missing-created-branch refusal | WP01 | P1 | No |
| T005 | Migrate `test_reconciliation.py` | WP01 | P1 | No |
| T006 | WP01 gates | WP01 | P1 | No |
| T007 | Red-first lifecycle-sync test | WP04 | P1 | Yes |
| T008 | Delete dual-name probe | WP04 | P1 | No |
| T009 | Acceptance lane source roots | WP04 | P1 | Yes |
| T010 | Recovery worktree lookups via authority | WP04 | P1 | No |
| T011 | Recovery Mission-branch typed refusal | WP04 | P1 | No |
| T012 | WP04 tests + gates | WP04 | P1 | No |
| T013 | `_LANE_ID_RE` grammar | WP05 | P2 | No |
| T014 | Parsers + `is_lane_branch` | WP05 | P2 | No |
| T015 | sparse-checkout site | WP05 | P2 | Yes |
| T016 | status doctor orphan scan | WP05 | P2 | Yes |
| T017 | live-work bindings | WP05 | P2 | Yes |
| T018 | commit guard / merge-resolve | WP05 | P2 | Yes |
| T019 | WP05 site tests + gates | WP05 | P2 | No |
| T020 | Red-first re-finalize test | WP06 | P1 | Yes |
| T021 | `_preserved_mission_branch` | WP06 | P1 | No |
| T022 | aggregate destination ref | WP06 | P1 | No |
| T023 | FR-010 re-verify + gates | WP06 | P1 | No |
| T024 | Red-first #5113 integration tests | WP09 | P2 | Yes |
| T025 | Materialize helper + unit tests | WP09 | P2 | No |
| T026 | Wire helper into decision service | WP09 | P2 | No |
| T027 | Structured CLI error handler | WP09 | P2 | No |
| T028 | Unmaterialized remedy text | WP09 | P2 | No |
| T029 | WP09 gates | WP09 | P2 | No |
| T030 | Executor created-name helpers | WP02 | P1 | No |
| T031 | Tip capture keyed by created name | WP02 | P1 | No |
| T032 | Resume H5 refusal | WP02 | P1 | No |
| T033 | Safety preflight created worktrees | WP02 | P1 | No |
| T034 | Tidy-first cleanup extraction | WP02 | P1 | No |
| T035 | Cleanup created names | WP02 | P1 | No |
| T036 | WP02 tests + gates | WP02 | P1 | No |
| T037 | Red-first remedy round-trip | WP10 | P2 | No |
| T038 | Doctor missing-worktree fixer | WP10 | P2 | No |
| T039 | Doctor next_step + help | WP10 | P2 | No |
| T040 | Remedy text: runtime/mission_runtime | WP10 | P2 | Yes |
| T041 | Remedy text: implement/record-analysis | WP10 | P2 | Yes |
| T042 | WP10 pins + gates | WP10 | P2 | No |
| T043 | End-to-end 4/4 divergent merges | WP03 | P1 | No |
| T044 | Orphan + retention assertions | WP03 | P1 | No |
| T045 | Upgrade-resume refusal pin | WP03 | P1 | No |
| T046 | Merge preflight Mission-branch fallbacks | WP03 | P1 | No |
| T047 | Planning-artifact class green + gates | WP03 | P1 | No |
| T048 | Red-first signature test | WP07 | P1 | No |
| T049 | Atomic signature cutover | WP07 | P1 | No |
| T050 | Golden re-pins | WP07 | P1 | No |
| T051 | Residual test migration | WP07 | P1 | No |
| T052 | Gate-pinned sites (detection, drift matcher, placeholder) | WP11 | P1 | No |
| T053 | Gate legs + allow-list | WP11 | P1 | No |
| T054 | Gate self-test | WP11 | P1 | No |
| T055 | Architectural suite + gates | WP11 | P1 | No |
| T056 | ADR | WP08 | P3 | No |
| T057 | Architecture docs | WP08 | P3 | Yes |
| T058 | Migration docs | WP08 | P3 | Yes |
| T059 | CLAUDE.md / AGENTS.md | WP08 | P3 | Yes |
| T060 | CHANGELOG + doc validation | WP08 | P3 | No |

---

## Follow-ups to file at close-out (plan Risk 6; not in scope)

- Recovery enumeration prefix over-match `kitty/mission-{slug}*` (`lanes/recovery.py`), see #5108 discussion.
- Review-workspace second lane-creation path (`cli/commands/agent/workflow.py`, naming-compliant; C-005).
- `migration/mission_state.py` rebuild with no prior manifest recomposes the Mission branch with the identity.
- Lane-id grammar past 26 lanes (`_next_free_lane_id` yields `lane-{`).
- Cleanup reports success when `branch -D` is refused (see #4762).
- Deduplicate the `PlacementResolutionRequired` remedy string between `cli/commands/implement_cores.py` and `cli/commands/implement.py` (WP10 keeps both local; no new shared module in this mission).
