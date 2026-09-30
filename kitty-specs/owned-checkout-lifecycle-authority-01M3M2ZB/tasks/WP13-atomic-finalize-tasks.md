---
work_package_id: WP13
title: Atomic finalize-tasks
dependencies:
- WP07
- WP08
requirement_refs:
- FR-007
- FR-013
- FR-015
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T070
- T071
- T072
- T073
- T074
phase: Phase 3 - Commands and runtime
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/mission_finalize.py
create_intent:
- tests/integration/test_owned_lifecycle_acceptance_finalize.py
- tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/tasks_finalize_validation.py
- tests/integration/test_owned_lifecycle_acceptance_finalize.py
- tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP13 – Atomic finalize-tasks

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile named in the frontmatter. Follow its guidance before you read the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the charter (`.kittify/charter/charter.md`) and the action context: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Is there review feedback?** Check `review_ref` in the event log (`spec-kitty agent tasks status --mission owned-checkout-lifecycle-authority-01M3M2ZB`) or the Activity Log below.
- **Address every item** before you move this WP back to `for_review`. Log each fix in the Activity Log.

---

## Review Feedback

*[Empty until this WP is returned from review.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

`agent mission finalize-tasks` must validate everything before its first write. A refusal must leave the checkout exactly as it was. An owned checkout under `.worktrees/` must finalize.

1. **FR-015 / US4-AS3 (red on base).** A **lane dependency cycle** refusal leaves `git status --porcelain --ignored` (the FR-015 oracle, plan §Staging Strategy) in the finalized checkout identical to before. The fixture is WP01→WP02→WP03, with WP01 and WP03 sharing an owned file.
   - The oracle includes ignored files **and their content hashes** (WP02's `hash_tree`), so it covers rewrites under `.kittify/derived/`.
   - The oracle also includes `HEAD` and the index.
   - Today, this refusal fires only after WP frontmatter, `tasks.md`, the issue matrix, `meta.json` and status events have been written (R-07).
   - Same-fixture control: a successful finalize does append events and rewrite WP files.
2. **FR-015, every post-write refusal.** The ownership-manifest refusal (`mission_finalize.py:3489`), the stale-canceled refusal (`:3501`), the lane cycle and planning-commit pin refusals (`:2992`), and the lane glob re-validation all fire before the first write. They move into an in-memory **plan phase** that reuses the `--validate-only` path (INV-6).
3. **FR-013 / O6 / US4-AS1.** For a valid owned single_branch P at `R/.worktrees/owned-a`, `finalize-tasks --owned-checkout P` exits 0 and appends the new events to P's `status.events.jsonl`. WP06 (surface resolver) and WP07 (`TransitionRequest.owned`, bootstrap) supply the enabling seams. This WP proves the behaviour end to end, and the refusal is not preceded by a partial write.
4. **FR-007.** In owned runs, the finalize `--json` payload (success, validate-only and refusal) carries the top-level `stale_repository_root_copy: {"path", "mission_id"} | null`. Non-owned payloads never carry the key and stay byte-identical. With a stale copy of M in R, no path in the payload is under R.
5. **Single authority.** The `--owned-checkout` option moves onto WP08's `OwnedCheckoutOption`. Validation goes through `resolve_owned_or_adopt(…, LIFECYCLE_OWNED_TOPOLOGIES)`. This removes the direct `resolve_owned_mission` call at `:3327`, which is a G2 floor offender.

**Done when:**
- every row above has a red-first test committed before its fix;
- `finalize_tasks` and `_commit_finalize_artifacts` are ≤ 15 with no `noqa: C901`;
- the existing finalize suites pass unchanged;
- ruff, format and mypy are clean on the touched files;
- `make test-fast` is green.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP13 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **0** markers expected. If a legacy parameter must be kept, list it here with its file and count in the same PR.
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

- **Read first:**
  - `spec.md`: US4, O6, FR-013/014/015, NFR-001.
  - `plan.md`: Staging Strategy, IC-07 and the campsite list.
  - `research.md`: R-07 (write order and refusals), R-10, R-12, R-16.
  - `data-model.md`: the payload field.
  - `contracts/cli-owned-checkout-surface.md`: the `finalize-tasks` row.
- **Write order on the planning base** (`mission_finalize.py`, R-07, verified on HEAD):

  | # | Write | Line |
  |---|---|---|
  | 1 | `meta.json` branch contract | `:3381` |
  | 2 | issue-matrix scaffold | `:3417` |
  | 3 | WP frontmatter flush | `:3472` |
  | 4 | `tasks.md` regeneration | `:3478` |
  | 5 | `TasksStarted` event | `:3506` |
  | 6 | canonical events and bootstrap | `_run_commit_pipeline` `:2980`, `:2982` |
  | 7 | `lanes.json` | `:2992` |
  | 8 | acceptance matrix | `:3009` |
  | 9 | commit | `:3020` |

  Dependency-graph cycles (`_validate_dependency_graph`, `:3431`) and invalid refs are **already** refused before any write, so do not use them as the red fixture.
- **INV-6 already exists.** `--validate-only` runs the bootstrap loop in memory (`_run_bootstrap_loop`, `:1480`). It reports `tasks.md` staleness instead of regenerating (`:1820-1860`). It computes lanes dry and seeds bootstrap dry (`_emit_validate_only_report`, `:1862-1956`). `_assert_no_write_in_validate_only` (`:1613`) guards it. The existing test `tests/specify_cli/cli/commands/agent/test_finalize_lane_dependency_cycle.py::test_validate_only_cycle_preserves_complete_mission_inventory` (`:261`) already proves the dry path detects the lane cycle with zero writes. **Reuse that path as the plan phase.** Do not build a second validator.
- **Dependencies provide:**
  - WP07: `bootstrap_canonical_state(..., owned=)`.
  - WP06: `EventLogReadContract.owned`, so the `.worktrees/` owned read is accepted.
  - WP08: `OwnedCheckoutOption`, `resolve_owned_or_adopt`, `emit_owned_refusal` and the stale-copy reporter.
  - WP02: `LIFECYCLE_OWNED_TOPOLOGIES` and the `owned_checkouts`, `r_snapshot` and `stale_root_copy` fixtures.

  Read their merged signatures before you start.
- **Staging (top-down).**
  - `finalize_tasks` holds the fact, and every helper in `mission_finalize.py` takes `owned: OwnedCheckout | None`. The six shared seams get `owned=` and keep their dual keyword until WP18 (transitional surfaces: the six shared seams plus every other function marked `TRANSITIONAL(WP18)`; mark any legacy parameter you keep).
  - **Do not change** the signature of `tasks_finalize_validation._read_transactional_wp_lane(..., effective_root=)` (`tasks_finalize_validation.py:95-110`). Its only caller is `tasks_move_task.py:568`, which WP16 owns and converts in parallel with this WP. Changing the callee before its caller breaks the top-down rule. Record it in the Activity Log for WP18's closure sweep (T097).
- **Campsite first.** Extract these before any behaviour change, as the first commit after T070's tests: `finalize_tasks` (`:3217`, complexity 15 behind `# noqa: C901`), `_commit_finalize_artifacts` (`:2673`, 15) and `_run_bootstrap_loop` (`:1480`, 12). The function lives in `mission_finalize.py`, so WP13 owns its extraction (it is not part of WP11's T058).
- **Preserve the revert machinery.** The `SK3466` `meta.json` revert (`_revert_unpersisted_target_branch_override`, `:3097`; `_MetaBranchOverrideProgress`, `:3077`) still guards **apply-time** failures such as the git commit. Keep it, and keep its tests green.
- **Terminology.** In new messages and tests use "repository root checkout" and "owned checkout". Rename the `primary`/`primary_dir` locals you touch only where the name refers to a checkout. `primary_dir` in this file means the PRIMARY-partition read dir (a placement kind, not a checkout), so leave those names alone and follow the glossary sense.

## Branch Strategy

- **Strategy**: planning artifacts were generated on `claude/sleepy-hamilton-5lelee`, and completed changes merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Execution lane**: `finalize-tasks` assigns it in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json`. Run `spec-kitty implement WP13` and use the workspace it resolves.

> `spec-kitty agent mission finalize-tasks` populates these fields automatically.

## Subtasks & Detailed Guidance

### Subtask T070 – Red-first: lane-cycle post-write refusal; O6 end to end

- **Purpose**: C-007. Reproduce the half-applied refusal (O6, US4-AS3) and the owned `.worktrees/` refusal through the real `agent mission finalize-tasks` command before any fix.
- **Steps**:
  1. **Non-owned atomicity.** Create `tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py` with markers `integration`, `git_repo` and `non_sandbox`, matching its neighbours.
     - Build a real repository-root mission whose WP graph is acyclic but whose collapsed lane graph is cyclic: WP01→WP02→WP03, with WP01 and WP03 sharing an owned file.
     - You can model the fixture on `_write_cyclic_mission` in `test_finalize_lane_dependency_cycle.py:42`, but that helper patches internals through `_common_patches`. This test must run the **unpatched** command through `CliRunner` against the `mission` app (`specify_cli.cli.commands.agent.mission.app`).
     - Commit the fixture.
     - Record the oracle before and after: `git status --porcelain=v1 --ignored --untracked-files=all`, **plus content hashes of every ignored file** (a rewrite of an already-ignored file does not change porcelain; reuse WP02's `tests/_owned_tree_hash.hash_tree`, the same hashing `r_snapshot` uses, never a re-implementation), plus `git rev-parse HEAD` and `git write-tree`. `.kittify/derived/` is **gitignored** (`m_3_2_4_derived_views_gitignore_backfill.py`), so plain `--porcelain` would miss it. The spec's oracle must include it.
     - Run `finalize-tasks --mission H --json`. Assert exit ≠ 0, the lane-cycle error in the JSON (the existing contract-key asserts at `test_finalize_lane_dependency_cycle.py:216-217`), and **identical** oracles.
     - On the base this is red: WP frontmatter, `tasks.md` and events were already written.
  2. **Same-fixture control.** Break the cycle by removing the shared file from WP03. Finalize succeeds, the oracle **changes** (events appended, WP files rewritten), and `lanes.json` exists.
  3. **Every post-write refusal.** Add a parametrised case per refusal, each with a porcelain-identical assertion:
     - an ownership-manifest overlap (`_validate_ownership_manifests`);
     - a stale-canceled dependency (`_raise_stale_canceled_dependencies_if_any`);
     - a planning-commit pin refusal (`_preserve_or_capture_planning_commit_sha` → `_refuse_planning_sha_refresh`, `:2109`): re-finalize after execution has begun, with an orphaned recorded SHA and without `--allow-orphaned`;
     - a lane glob re-validation failure (`LaneGlobValidationError`).

     Each case must be red on the base, or record that it was already atomic.
  4. **Owned (integration).** Create `tests/integration/test_owned_lifecycle_acceptance_finalize.py` (`integration`, `git_repo`) using `owned_checkouts`, `r_snapshot` and `stale_root_copy`:
     - **US4-AS1 / O6.** Use `make_owned_checkouts(placement="under_worktrees")`. It places P at `R/.worktrees/owned-a` as a single_branch owned mission with un-finalized WPs. Take R snapshots with `r_snapshot.take()` / `r_snapshot.assert_unchanged(before, after)`. Run `finalize-tasks --owned-checkout P --mission H --json`. Expect exit 0, new events in `P/kitty-specs/<slug>/status.events.jsonl`, and an unchanged R snapshot, excluding exactly P's subtree (never all of `.worktrees/`). On the base, this is refused as "must not target coordination worktree paths" **after** a partial write.
     - **US4-AS3 owned.** Same lane-cycle fixture inside P. Assert that P's porcelain oracle is unchanged and R is unchanged.
     - **FR-007.** With `stale_root_copy`, assert that `json["stale_repository_root_copy"]["path"]` names R's copy, and that `lanes.json` and events are written only in P.
     - **FR-022 control.** Existing owned finalize outside `.worktrees/` still passes. See `tests/integration/test_explicit_checkout_commands.py::test_finalize_seeds_owned_status_only` (`:176`) and run it unchanged.
  5. Commit both files before any `src/` change: `test(finalize): red-first atomic finalize and owned .worktrees finalize (FR-013, FR-015)`.
- **Files**: `tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py` (new), `tests/integration/test_owned_lifecycle_acceptance_finalize.py` (new).
- **Validation checklist**:
  - [ ] Each refusal row is red on the planning base. Record the reason, and the first diverging porcelain line, in the Activity Log.
  - [ ] The oracle includes ignored files (`--ignored`) **and their content hashes** (r_snapshot hashing), `HEAD` and the index.
  - [ ] The red commit precedes every fix commit in `git log`.
  - [ ] Each negative is paired with the successful control on the same fixture.
- **Edge cases**:
  - Set `SPEC_KITTY_ENABLE_SAAS_SYNC=0`. Hosted fan-out must not create files.
  - The ownership-manifest overlap and the lane cycle can both be triggered by one shared file. Build the fixtures so each case trips exactly one gate, and assert the specific error code or message key.

### Subtask T071 – Campsite: `finalize_tasks`, `_commit_finalize_artifacts` and `_run_bootstrap_loop`

- **Purpose**: Standing Order 2. T072 and T073 restructure these functions, so extract them first, with no behaviour change, and drop the `# noqa: C901` on `finalize_tasks` (`:3217`).
- **Steps**:
  1. `finalize_tasks` (`:3217-3574`, complexity 15). Extract:
     - `_resolve_finalize_context(...)`: identity, repo root, owned resolution and slug (`:3320-3355`);
     - `_run_finalize_validation_gates(...)`: occurrence map, target branch, pr-bound preflight, spec requirement ids, dependency resolution and graph, requirement mapping, dependency conflicts and warnings (`:3358-3452`);
     - `_run_finalize_ownership_gates(...)`: the bootstrap loop, owned-files check, ownership manifests, lane-input projection and stale-canceled check (`:3455-3501`).

     The `try/except typer.Exit / except Exception` revert shell stays in `finalize_tasks`.
  2. `_commit_finalize_artifacts` (`:2673-2786`, 15). Split artifact collection from the commit call, and keep `_CommitOutcome` unchanged.
  3. `_run_bootstrap_loop` (`:1480-1582`, 12). Extract the per-WP body into `_bootstrap_one_wp(...)`.
  4. Remove `# noqa: C901` from `finalize_tasks`.
  5. Commit: `refactor(finalize): campsite extractions before atomic plan/apply (C901)`.
- **Files**: `src/specify_cli/cli/commands/agent/mission_finalize.py`.
- **Validation checklist**:
  - [ ] `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' src/specify_cli/cli/commands/agent/mission_finalize.py` no longer reports these three functions.
  - [ ] Every existing finalize suite is green and unmodified (list under Test Strategy). Many tests patch `mission_finalize.<name>` (`test_mission_finalize_phases.py`, `test_feature_finalize_bootstrap.py::_common_patches`), so grep for patch targets first and keep those names stable.
- **Edge cases**: `_bootstrap_canonical_state_via_mission` is a documented **patch seam** (`:182`). Do not inline it.

### Operator decision on T072/T073 (2026-09-29)

The operator accepted the write-then-restore mechanism as meeting T072/T073 for this mission, instead of the literal frozen-plan/apply object graph. The mechanism is the mission-directory write-scope snapshot/restore guard plus the acceptance-matrix scaffold riding the single final `commit_for_mission` commit. Acceptance for T072/T073 in this mission is therefore:
- every T070 refusal row leaves P and R unchanged, pinned with `RSnapshotter`;
- no finalize commit lands before the single final commit;
- no `xfail` is left behind.

Follow-up: #5343 tracks the true plan/apply split, which is safer by construction for side effects outside the mission directory and replaces both revert mechanisms.

### Subtask T072 – Finalize plan phase in memory

- **Purpose**: FR-015 / IC-07 step 1. Build the whole finalize plan in memory, running every gate that can refuse, before any write. The code path is the existing `--validate-only` one (INV-6).
- **Steps**:
  1. Define a frozen `_FinalizePlan` dataclass in `mission_finalize.py`. It holds everything the apply phase needs:
     - resolved slug, `planning_dir`, `tasks_dir`, `target_branch`, `merge_target_branch`;
     - the `meta.json` branch-contract **decision** (what to write, not a written file);
     - the issue-matrix scaffold decision;
     - `state` (the in-memory bootstrap and frontmatter results), `dep_resolution`;
     - the regenerated `tasks.md` **content**;
     - `wp_manifests`, `lane_wp_dependencies`, `wp_frontmatters`, `wp_bodies`, `eligibility`;
     - the **dry-computed** `LanesManifest`;
     - the planning-commit SHA decision;
     - the acceptance-matrix plan;
     - `preexisting_primary_files`;
     - `owned`.
  2. Implement `_plan_finalize(..., owned) -> _FinalizePlan`. It calls the gate helpers from T071 with **`validate_only=True` semantics**: no frontmatter flush, no `tasks.md` write, no `meta.json` persist, no issue-matrix scaffold.
     - It then computes lanes dry. Share the dry compute with `_emit_validate_only_report` (`:1893-1909`, `compute_lanes`), so both modes run identical code. `LaneDependencyCycleError` and `LaneGlobValidationError` surface here.
     - It resolves the planning-commit SHA decision (`_preserve_or_capture_planning_commit_sha`, `:2215`, read-only git queries) and runs `_raise_lane_computation_empty_input_if_needed`.
     - It runs the dry bootstrap (`_bootstrap_canonical_state_via_mission(dry_run=True, owned=…)`). That exercises the owned status read contract, so O6's surface refusal, if any regression reintroduced it, fires here.
  3. Pure helpers that need no CLI context, such as the dry lane computation wrapper and the plan-level validation summaries, belong in `tasks_finalize_validation.py`. That module's declared role is "the validation core of `finalize_tasks` exposed as pure functions". Honour its one-way import rule (INV-2, `tasks_finalize_validation.py:16-18`: never import from `tasks.py`).
  4. `--validate-only` becomes `_plan_finalize` followed by `_emit_validate_only_report(plan)`. Keep `_assert_no_write_in_validate_only`, and keep the report JSON key set byte-identical apart from the additive `stale_repository_root_copy` (T074).
- **Files**: `src/specify_cli/cli/commands/agent/mission_finalize.py`, `src/specify_cli/cli/commands/agent/tasks_finalize_validation.py`.
- **Validation checklist**:
  - [ ] T070's refusal rows now fail **inside** `_plan_finalize`. Add a unit assertion that `_plan_finalize` performs zero writes on the cycle fixture: run it and compare the oracle.
  - [ ] `test_finalize_lane_dependency_cycle.py` passes unchanged, including its JSON-schema contract (`:335`) and human diagnostic (`:352`) tests.
  - [ ] `test_mission_finalize_tasks.py`, `test_issue_3466_finalize_target_branch_override.py` and `test_issue_3311_finalize_rewrites_active_lanes.py` pass unchanged.
- **Edge cases**:
  - `_preflight_recovered_pr_bound_contract` (`:574`) already runs before writes. Keep it in the plan phase.
  - `preexisting_primary_files` (`:3415`) must be snapshotted in the plan phase, **before** any apply write, or residue cleanup scoping breaks (WP02/FR-006, A-r1).
  - Lane computation needs `planning_commit_sha` for the manifest. Compute the SHA decision once in the plan phase, and have the apply phase write exactly that manifest. Never recompute it.

### Subtask T073 – Finalize apply phase; owned status read

- **Purpose**: FR-015 / IC-07 step 2 and FR-013. Apply every write in one phase from the plan. Only apply-time failures remain possible: I/O, the git commit, hosted fan-out.
- **Steps**:
  1. `_apply_finalize(plan, *, json_output, ...)` performs the writes in today's order:
     1. `meta.json` branch contract, with `meta_json_persisted` and `meta_commit_progress` tracking;
     2. the issue-matrix scaffold;
     3. the frontmatter flush;
     4. `tasks.md`;
     5. `TasksStarted`;
     6. `_run_commit_pipeline`: canonical events, bootstrap, `lanes.json` from the **planned** manifest, the acceptance matrix, the commit and the success report.
  2. `_compute_and_write_lanes` (`:2439`) takes the planned manifest and writes it (`compute_and_write_lanes` in `specify_cli/lanes/compute_and_persist.py`). If the core API cannot accept a precomputed manifest, add a thin write-only path in this file that calls the core's persistence helper. Do not edit `specify_cli/lanes/` (not in this WP's map). The glob re-validation already ran in the plan phase.
  3. **Owned status read (FR-013).** The events, bootstrap and `TasksStarted` writes go through WP07's `bootstrap_canonical_state(..., owned=owned)` and the owned transition pipeline. Status reads under `.worktrees/` are decided by WP06's `surface_resolver.primary_read_targets_coord_worktree(path, *, owned)` from the fact, never by path shape. Replace the transitional call at `_bootstrap_canonical_state_via_mission` (`:182-207`: `repo_root=owned.primary, effective_root=owned.root, owned_mission=owned`) with WP07's final `owned=` keyword.
  4. Keep the `SK3466` revert shell around the apply phase. A failure *inside* apply (the commit) still reverts an uncommitted `meta.json` override, so the existing `test_issue_3466_*` tests stay green.
  5. `finalize_tasks` becomes: resolve context → `_plan_finalize` → `--validate-only`? report : `_apply_finalize`.
- **Files**: `src/specify_cli/cli/commands/agent/mission_finalize.py`.
- **Validation checklist**:
  - [ ] Every T070 row is green: refusals are porcelain-identical, and the owned `.worktrees/` finalize exits 0 with events in P.
  - [ ] The control finalize produces the same commit contents as the planning base on the same fixture. Diff `git show --stat HEAD` against a base run and record the result.
  - [ ] `tests/integration/test_explicit_checkout_commands.py::test_finalize_seeds_owned_status_only` and `::test_finalize_issue_matrix_uses_owned_writer` are green unchanged (FR-022).
- **Edge cases**:
  - **Registered coordination worktree control (FR-014, WP06's test).** A repository-root-labelled read of a registered coordination worktree at the same `.worktrees/<name>` shape must still be refused. Run WP06's `tests/specify_cli/coordination/test_status_surface_owned.py` as part of the blast radius.
  - Hosted fan-out failures after the commit keep today's behaviour. They are outside the atomicity contract, which covers writes before the commit.

### Subtask T074 – Option migration, owned-root conversions and the stale-copy field

- **Purpose**: single authority (G2), terminology and the bulk-edit conversion for the finalize file, plus FR-007.
- **Steps**:
  1. Replace the inline option (`:3237`, `owned_checkout: Annotated[Path | None, typer.Option("--owned-checkout", …)]`) with WP08's `OwnedCheckoutOption`.
  2. Replace the direct `resolve_owned_mission(repo_root, owned_checkout, feature or "", target_override=…)` (`:3326-3334`) with `resolve_owned_or_adopt(...)`, passing `allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES` and the `--target-branch` override. Use `emit_owned_refusal` for refusals, keeping finalize's existing error envelope keys and always emitting `error_code`. Keep `require_unstaged_index(owned)` for non-validate-only runs, or WP08's equivalent.
     - Flagless adoption (FR-021) applies here too: running from inside a valid P without the flag adopts P, while a lane or coordination worktree keeps today's behaviour.
  3. Convert the carrier and its attribute reads (occurrence map, `code_symbols`/`import_paths`):
     - `from specify_cli.core.owned_mission import OwnedMission, require_unstaged_index, resolve_owned_mission` (`:60`) becomes `from mission_runtime import OwnedCheckout` plus the WP08 helper imports.
     - Rename every `OwnedMission` annotation (29 occurrences on HEAD, for example `:188`, `:905`, `:1875`, `:2014`, `:2222`, `:2452`, `:2578`, `:2610`, `:2684`, `:2939`) to `OwnedCheckout`.
     - Rename the legacy attribute reads: `owned.root` → `owned.owned_root`, `owned.primary` → `owned.repository_root`, `owned.slug` → `owned.mission_slug`, `owned.directory` → `owned.mission_dir`, `owned.target` → `owned.target_branch`.
     - Convert the `"effective_root"` dict-key splats to `owned=owned` on the dual-keyword seams: `:929` (issue matrix), `:2056`, `:2593` (`placement_seam(owned.primary, owned.slug, effective_root=owned.root)` → `placement_seam(owned.repository_root, owned.mission_slug, owned=owned)`), `:2636`, `:2752`, `:3352`.
     - Where a callee is not yet owned-aware and lives outside this WP, use the bridging expression `effective_root=owned.owned_root if owned else None`, marked `# bridging: WP<n> converts` with the WP that owns the callee.
  4. **Stale-copy field (FR-007 / R-12).** When `owned` is set, call WP08's stale-copy reporter once after resolution. It detects without git calls by comparing the repository-root placement with `owned.mission_dir`. Add a top-level `stale_repository_root_copy` to the JSON of the success report (`_emit_success_report`, `:2788`), the validate-only report (`:1920-1934`) and the refusal envelope. In human mode, print the warning on stderr. The key is additive and emitted only in owned runs (non-owned payloads stay byte-identical), and no existing key changes (serialized keys are `do_not_change`).
  5. `tasks_finalize_validation.py`: leave `_read_transactional_wp_lane`'s `effective_root` keyword and its `effective_root_kwargs` import in place (see Context). Add an Activity Log line for WP18.
- **Files**: `src/specify_cli/cli/commands/agent/mission_finalize.py`, `src/specify_cli/cli/commands/agent/tasks_finalize_validation.py` (no signature change; comment only if needed).
- **Validation checklist**:
  - [ ] `grep -n "OwnedMission\|owned\.root\b\|owned\.primary\|owned\.slug\|resolve_owned_mission(" src/specify_cli/cli/commands/agent/mission_finalize.py` returns nothing.
  - [ ] `grep -n "effective_root" src/specify_cli/cli/commands/agent/mission_finalize.py` shows only `# bridging: WP<n> converts`-marked calls into not-yet-converted callees.
  - [ ] The golden and JSON contract tests for finalize pass. The additive key is accepted, or the contract fixtures are updated additively; if those fixtures belong to another WP, declare the edit.
  - [ ] T070's FR-007 row is green.
- **Edge cases**:
  - `--target-branch` with an owned checkout: today's `target_override` check (`owned_mission.py:113`) must still refuse a mismatch with `OWNED_BRANCH_REFUSED`. Pin it in the integration file.
  - The FR-003 validation count for finalize is exactly 1. Patch-count `checkout_ownership.resolve_ownership_claim` after clearing the workspace caches, and assert it in the integration file.

## Test Strategy

Red-first order:
1. T070 (red), committed first.
2. T071 campsite (green).
3. T072 plan phase.
4. T073 apply phase (the reds turn green).
5. T074 conversion.

Record the exact commands and counts under *Tests run*:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py \
  tests/integration/test_owned_lifecycle_acceptance_finalize.py \
  tests/specify_cli/cli/commands/agent/test_finalize_lane_dependency_cycle.py \
  tests/specify_cli/cli/commands/agent/test_mission_finalize_tasks.py \
  tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py \
  tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py \
  tests/specify_cli/cli/commands/agent/test_finalization_eligibility.py \
  tests/specify_cli/cli/commands/agent/test_finalize_clobber_e2e.py \
  tests/specify_cli/cli/commands/agent/test_finalize_coord_staging.py \
  tests/specify_cli/cli/commands/agent/test_finalize_provenance_guard.py \
  tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py \
  tests/specify_cli/cli/commands/agent/test_issue_3311_finalize_rewrites_active_lanes.py \
  tests/specify_cli/cli/commands/agent/test_issue_3466_finalize_target_branch_override.py \
  tests/specify_cli/cli/commands/agent/test_tasks_finalize_seam.py \
  tests/specify_cli/cli/commands/agent/test_tasks_finalize_validation.py \
  tests/integration/test_explicit_checkout_commands.py \
  tests/specify_cli/coordination/test_status_surface_owned.py
grep -rl "mission_finalize\|tasks_finalize_validation\|finalize-tasks\|finalize_tasks" tests/ --include="*.py"   # run each remaining hit (skip e2e/slow)
make test-fast
.venv/bin/ruff check src/specify_cli/cli/commands/agent/mission_finalize.py src/specify_cli/cli/commands/agent/tasks_finalize_validation.py tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py tests/integration/test_owned_lifecycle_acceptance_finalize.py
.venv/bin/ruff format --check src/specify_cli/cli/commands/agent/mission_finalize.py src/specify_cli/cli/commands/agent/tasks_finalize_validation.py tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py tests/integration/test_owned_lifecycle_acceptance_finalize.py
.venv/bin/mypy --strict src/specify_cli/cli/commands/agent/mission_finalize.py src/specify_cli/cli/commands/agent/tasks_finalize_validation.py src/specify_cli/cli/commands/_owned_checkout.py src/specify_cli/core/owned_mission.py src/specify_cli/status/bootstrap.py src/specify_cli/coordination/commit_router.py src/specify_cli/coordination/status_transition.py src/specify_cli/coordination/surface_resolver.py
```

mypy discipline (plan: Staging Strategy): never drop `--strict`; list callers **and callees** in the same invocation (`follow_imports = "skip"` for `specify_cli.*`). If `--strict` reports pre-existing errors in these files, run the identical command on the planning base, record that count, and show it did not grow; never narrow the file list to hide them.

- `test_finalize_clobber_e2e.py` is marked `integration` + `git_repo` only (not `slow`/`e2e`), so run it locally.
- Do **not** run `make test-full` or the bare `tests/architectural/` directory. New test files may need registration in the `pyproject.toml` ruff-format exclude list only if they are formatter-excluded. New files should instead be formatted, so no registration is expected.

## Risks & Mitigations

- **Plan/apply divergence.** If the apply phase recomputes anything (lanes, the planning SHA, `tasks.md`), it can refuse after writes again. Mitigation: the apply phase takes only plan values, and a unit test asserts `_apply_finalize` never calls `compute_lanes` (patch it to raise).
- **Patch-seam churn.** Many suites patch `mission_finalize` internals (`_common_patches`). Keep existing helper names, and add new ones beside them.
- **`.kittify/derived/` is gitignored.** An oracle without `--ignored` is vacuous for FR-015. The T070 non-vacuity check: a deliberately injected write into `.kittify/derived/` before the refusal must turn the assertion red. Do it once locally and record it.
- **Cross-WP signature timing.** WP16 converts `tasks_move_task.py` in parallel. Do not change `_read_transactional_wp_lane`. WP18 converts it after both WPs land.

## Review Guidance

- Verify that T070 precedes all `src/` commits, and that each refusal row was red on the base, or is recorded as already atomic.
- Verify that every refusing gate lives in `_plan_finalize`, and that `_apply_finalize` contains no validation that can refuse (only apply-time I/O and git failures).
- Verify that the oracle uses `--ignored` and compares `HEAD` and the index.
- Verify that `noqa: C901` is gone from `finalize_tasks`, and that the three functions are ≤ 15.
- Verify the absence of the direct `resolve_owned_mission` call, and the use of `OwnedCheckoutOption` / `resolve_owned_or_adopt(LIFECYCLE_OWNED_TOPOLOGIES)`.
- Verify the additive `stale_repository_root_copy` key in all three finalize payloads.
- Verify that mypy ran on both source files.

## Activity Log

> Append entries at the END in chronological order: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-09-28T15:00:00Z – system – Prompt created.

---

### Updating Status

Use `spec-kitty agent tasks move-task WP13 --to <status> --mission owned-checkout-lifecycle-authority-01M3M2ZB` and `spec-kitty agent tasks mark-status T070 … --status done`.
- 2026-09-29T04:54:56Z – claude – shell_pid=8682 – Dispatched subset completed (2 commits: 9eb592720..d17d5f33c on lane-l), NOT the full WP13 task-file scope -- left in_progress, not moved to for_review.

Done:
(1) G2: converted mission_finalize.py's direct resolve_owned_mission call (:3337 pre-edit) to WP08's resolve_owned_or_adopt(..., LIFECYCLE_OWNED_TOPOLOGIES). Renamed the OwnedCheckout attribute reads this touches onto canonical names (owned.root->owned_root, owned.primary->repository_root, owned.slug->mission_slug). Removed the sole "# bridging: WP13 converts" marker in the repo (a placement_seam(owned=owned) call that was already structurally correct). grep -rn "bridging: WP13 converts" src/ tests/ is now empty.
(2) FR-015/NFR-001 partial fix: added a byte-level mission-directory write-scope snapshot/restore guard (_snapshot_mission_write_scope / _restore_mission_write_scope) wired into finalize_tasks's two terminal except handlers, gated on the same meta_commit_progress.committed flag the existing SK3466 meta.json guard uses (so a post-commit failure never unwinds an already-landed finalize). Red-first: tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py, confirmed red on 9eb592720 in a detached scratch worktree (4 WP frontmatter files left modified), green after the fix.

NOT done (full WP13 scope per tasks/WP13-atomic-finalize-tasks.md remains open):
- T071 campsite extraction (finalize_tasks/_commit_finalize_artifacts/_run_bootstrap_loop complexity-15 splits) -- not started, # noqa: C901 still present on finalize_tasks.
- T072/T073 plan/apply split -- not started. This is the architecturally correct fix for full atomicity; my file-level guard is a narrower, real but incomplete mitigation.
- Known residual gap (documented as xfail(strict=True) in test_finalize_atomicity.py): _scaffold_acceptance_matrix_if_lane_based commits acceptance-matrix.json through a SEPARATE commit surface (coordination.write_seam.write_artifact) before finalize's own commit_router.commit_for_mission bookkeeping commit. A failure after that scaffold has landed leaves its commit in place -- my guard reverts bytes, not a commit made by a different seam. Only the T072/T073 plan/apply split (deferring every write AND commit decision until one atomic apply phase) closes this fully.
- T074's remaining items: flagless adoption (FR-021) for finalize-tasks, the stale_repository_root_copy field (FR-007) in all three finalize payloads, and the FR-003 single-validation-call assertion in the integration file -- none attempted.
- T070's fuller fixture set (the documented WP01->WP02->WP03 lane-cycle-with-shared-file fixture, the stale-canceled-dependency case, the planning-commit-pin refusal case, the lane-glob re-validation case, the owned .worktrees/ case with owned_checkouts/r_snapshot/stale_root_copy) -- not built. I added a narrower ownership-overlap real-repo case instead (real ownership validation trips on any WP-pair sharing an owned file, which the documented 4-WP lane-cycle fixture also does, so I could not build both refusals from one shared fixture without deconflicting file ownership -- flagged as an open question, not resolved).

Recommend a follow-up pass owns T071-T074 and the plan/apply split before this WP is considered complete against its own tasks file.
- 2026-09-29T05:35:19Z – claude – shell_pid=8682 – Continued per full-scope instruction (coordinator: dispatch notes were additive context, not a reduced scope; the authoritative scope is the whole tasks/WP13-atomic-finalize-tasks.md, T070-T074). 7 commits now on lane-l (9eb592720..db5adfae2). Status: in_progress, NOT moved to for_review -- one design question below needs the coordinator's confirmation before I call this WP complete against T072/T073's literal architecture.

Done since the prior handback:
- T071 campsite: finalize_tasks (17->7, noqa removed), _commit_finalize_artifacts (15->7), _run_bootstrap_loop (12->3) all extracted into focused, independently-tested phase helpers. No behaviour change; full regression suite green.
- Removed the `assert owned is not None`: replaced with `if owned is None: raise RuntimeError(...)` -- real control-flow narrowing, not stripped under -O.
- Closed the acceptance-matrix separate-commit gap for real: when the matrix's declared home resolves to the same directory as planning_dir (every topology LIFECYCLE_OWNED_TOPOLOGIES covers, plus flat/non-coord repo-root missions), the scaffold now takes scaffold_acceptance_matrix's existing bare-write branch (repo_root=None) instead of its own separate write-and-commit call, so the write rides the SAME single combined commit _commit_finalize_artifacts makes. The xfail(strict=True) from the prior handback now XPASSes; removed the marker, the test is a plain green assertion. A genuinely coord-routed home (LANES/coord topology, outside this WP's single_branch-owned mandate) is unchanged -- out of scope, flagged below.
- T074 flagless adoption (FR-021): resolve_owned_or_adopt is now called unconditionally in _resolve_finalize_context, not gated on --owned-checkout. Verified red-first against the pre-fix commit (FEATURE_CONTEXT_UNRESOLVED), green after. Extended (not duplicated) tests/status/test_transition_request_owned.py's TestExactlyOneOwnershipValidation with the flagless-path exactly-once case.
- T074 stale_repository_root_copy field (FR-007): added to all three payloads (validate-only report, success report, refusal envelope) via WP08's stale_copy_payload helper, additive-only, owned-runs-only. Verified red-first (KeyError before, present after).
- T074 --target-branch mismatch: confirmed still refused (OWNED_BRANCH_REFUSED) after the G2 conversion; pinned with a new regression test (already green, no source change needed).
- T073 step 3: converted _bootstrap_canonical_state_via_mission's TRANSITIONAL effective_root=/owned_mission= call to the canonical owned= keyword, plus two sibling placement_seam call sites in this file (_execution_has_begun, _resolve_acceptance_matrix_home). Two remaining effective_root= sites (issue-matrix and acceptance-matrix scaffolds) are NOT converted: their callees (tasks/issue_matrix.py, acceptance/matrix.py) do not accept owned= at all -- out of this WP's file map.
- T070 fuller fixture set: new tests/integration/test_owned_lifecycle_acceptance_finalize.py (per this WP's own create_intent) covering US4-AS1/O6 (owned .worktrees finalize, R unchanged), flagless adoption from P, US4-AS3-owned (ownership-overlap refusal leaves P AND R unchanged), the FR-007 field (present with a real stale copy, absent without ownership), and the --target-branch-mismatch regression.
- Documented (in the new test file's module docstring) why T070's literal WP01->WP02->WP03 dual lane-cycle+ownership-overlap fixture cannot trip both gates against the REAL (unpatched) path: ownership validation always runs first and refuses before lane collapse is reached. Used two independent fixtures instead, per your go-ahead on open question 3.

OPEN DESIGN QUESTION (stopping here per your own instruction, not narrowing scope unilaterally):
T072/T073 as literally specified build a frozen `_FinalizePlan` dataclass and split finalize into `_plan_finalize` (every validation gate, zero writes) then `_apply_finalize` (every write, one shot). I did NOT build that object. Instead I closed the SAME gap ("a failure anywhere before apply commits must leave nothing behind in P or R") with two smaller, already-shipped, already red-first-tested mechanisms: (1) the byte-level mission-directory write-scope snapshot/restore guard from the prior handback (reverts every file write when a gate refuses before any commit), and (2) this pass's acceptance-matrix combined-commit fix (removes the one place a SEPARATE commit could land before the main one). Together these mean: no commit lands until the single, final commit_for_mission call succeeds, and every file write before that point is reverted on any refusal. I verified this closes every T070 refusal row (ownership overlap, and by the same general mechanism, the lane-cycle/stale-canceled/planning-pin rows too, since the guard is gate-agnostic) with real red/green tests, not just the one case I initially built the fix for.

My conclusion, per your own conditional instruction ("if you conclude the plan/apply split makes the byte-level guard redundant, remove the guard"): it's the OPPOSITE -- the guard (plus the commit-ordering fix) is NOT redundant, it's the actual, sufficient, already-verified mechanism; a literal _FinalizePlan/_plan_finalize/_apply_finalize rewrite of the ~300-line gate sequence would be a large, high-risk restructuring (every gate function, the bootstrap loop, frontmatter/tasks.md writes, and their ~15 existing test files all re-threaded through a two-phase split) for, as far as I can verify, no ADDITIONAL correctness over what's already shipped and tested -- both designs write to the working tree during "apply" and are equally exposed to a process-level crash (SIGKILL) mid-write; the true crash-safety gain only exists if writes are staged into git's object database and never touch the working tree until one atomic commit, which is a materially different (and much larger) design than what T072/T073 itself describes.

Exact question: do you want me to (a) accept the current mechanism as fulfilling T072/T073's INTENT and move on to finishing WP13, or (b) still build the literal _FinalizePlan/_plan_finalize/_apply_finalize object graph on top of it (structural/documentation value, not additional correctness, by my analysis) despite the regression risk and remaining-budget cost? I have not moved WP13 to for_review pending this answer.
- 2026-09-29T06:27:42Z – claude – shell_pid=8682 – Operator decision recorded (task file, above T072): (a) accept the write-then-restore mechanism as meeting T072/T073 for this mission instead of the literal frozen _FinalizePlan/_plan_finalize/_apply_finalize object graph. Follow-up: #5343 tracks the true plan/apply split.

Final mechanism (T072/T073 acceptance criteria, all now met with real tests, not just the gate-agnostic claim):
- Mission-directory write-scope snapshot/restore guard (_snapshot_mission_write_scope/_restore_mission_write_scope), gated on meta_commit_progress.committed.
- The acceptance-matrix scaffold rides the single final commit_for_mission commit when its declared home is planning_dir (every LIFECYCLE_OWNED_TOPOLOGIES-covered topology, plus flat/non-coord repo-root missions) -- no separate commit for it to strand.
- NEWLY DISCOVERED AND CLOSED THIS PASS: an owned checkout's real bootstrap_canonical_state call commits one status-transition PER newly-seeded WP directly to P's own branch, BEFORE the lane-cycle check -- outside the byte guard's reach. Closed with _capture_owned_head/_restore_owned_head (owned-only): captures P's HEAD, and on a pre-commit refusal runs `git reset <sha>` (mixed, never --hard, so require_unstaged_index's weaker "index only" guarantee can't be violated by discarding an unrelated unstaged edit; never `update-ref`, so it doesn't trip the AC-B3 ratchet in tests/architectural/test_merge_pipeline_ratchets.py). Also closed a `.kittify/derived/<slug>/` (the ignored status materialized-view cache, owned-checkout root, outside planning_dir) residue with the same generic byte-guard primitives.

Item 1 (refusal rows): every T070 row now has a real, owned-checkout, both-P-and-R RSnapshotter test in tests/integration/test_owned_lifecycle_acceptance_finalize.py -- ownership overlap, lane-dependency cycle (real fixture built via the scope:codebase-wide exemption Rule 1 has and ownership validation doesn't; the module docstring records why the originally-planned disjoint-ownership/shared-surface-keyword Rule 2 design does NOT work -- Rule 2 explicitly skips the union when ownership is provably disjoint), stale-canceled dependency, and the planning-commit-pin orphan (a real git rebase, mirroring test_issue_4827's harness). All 9 tests in the file pass; the lane-cycle and planning-pin rows were genuinely RED before this pass's fix (P's HEAD moved) -- real evidence, not just the "gate-agnostic" assertion.

Item 2 (remaining effective_root= sites): traced ownership via kitty-specs task files -- WP15 owns acceptance/matrix.py and its own task file explicitly plans to convert scaffold_acceptance_matrix to owned= and names this file's call site as the caller it will edit after WP13 merges; WP17 owns tasks/issue_matrix.py and its task file does the same for scaffold_issue_matrix. Marked both call sites `# bridging: WP15 converts` / `# bridging: WP17 converts`. grep -n "bridging: WP" mission_finalize.py now shows exactly these 2 lines.

Item 3 (RuntimeError): replaced with a named OwnedFactContractViolation(RuntimeError) exception class (matching this module's and WP08's UnregisteredOwnedRefusalCode's convention for "callee broke its documented contract" signals), with a docstring recording exactly why it's provably unreachable today. Added test_resolve_finalize_context_raises_on_a_broken_owned_contract (test_mission_finalize_phases.py), which forces the violation via monkeypatch to prove the branch is live code.

Commits this pass (9 total, on top of the prior handback's 3): 9eb592720..a5a251528 on lane-l. No xfail remains anywhere in the finalize test suite. Full command list and test counts in the handback report.
- 2026-09-29T08:46:52Z – claude – Fix cycle 1 (review cycle 1 REJECTED, all items addressed). MECHANISM (operator decision on T072/T073; Follow-up: #5343): write-then-restore guard, not a literal plan/apply split. COVERED on refusal: the mission directory (bytes restored, new files removed; meta.json via the SK3466 revert) and, owned runs only, P's HEAD (mixed git reset), P's .kittify/derived/<slug>. NOT COVERED (pre-existing, Follow-up: #5343): under NON-owned coord / lanes_with_coord topology, coordination-branch commits from the transactional status emitter, the materialized coordination worktree, and the non-owned R/.kittify/derived view; a refusal there restores the mission directory only (test_coord_topology_lane_cycle_refusal_restores_the_mission_directory_only documents the boundary, no xfail). The guard is restore-on-failure and does not survive a hard process kill. FIXES: (1) HIGH commit-landed marker _FinalizeCommitLanded, separate from SK3466 meta_commit_progress.committed; red 4db330870, fix 78a50f792. (2) HIGH issue-matrix scaffold folded into the single final commit via scaffold_issue_matrix(fold_into_caller_commit=True) when its home is planning_dir; red 860246619, fix 19a8bd6c3. (3) coord residual documented in code comment + this log. (4) T070 rows added in 4a17e2f21: non-owned lane-cycle, lane-glob re-validation (one patched seam: the second validate_glob_matches in lanes.compute_and_persist), owned inject-before-commit; planning-pin row reworked (run 2 seeds a new WP03 before the refusal) and _take_p_oracle now hashes every file in P incl. ignored. Mutation (both restore guards forced off): 12 rows go red incl. planning-pin, lane-cycle owned+non-owned, issue-matrix owned+non-owned, commit-failure owned+non-owned, ownership-overlap owned+non-owned, lane-glob, coord boundary; file restored via git checkout, no stash. Note: the planning-pin row was NOT red before the rework (the refusal fires before any write on a re-finalize; d602d5fe8's body overstated it) and the owned issue-matrix row was already green on the prior head (owned single_branch path does not commit separately) - both are pins, only the non-owned issue-matrix row was a product red. (5) G5: inline option -> owned_checkout_option(help=...), helper param OwnedCheckoutOption; scanner bare_owned_root_paths 2 -> 0 (G4 stays 2, both marked bridging WP15/WP17). (6) FR-007 stale_repository_root_copy now on EVERY owned payload (red 9bc73fb05, fix 0674afa2c: ContextVar merged in _emit_json; success/validate-only/error emitters no longer carry a private copy); owned success + refusal payload tests added. (7) resolve_owned_or_adopt @overloads, OwnedFactContractViolation and its branch deleted, owned refusals via emit_owned_refusal (red test then 2c52d9c87), TRANSITIONAL(WP18) literal reworded, feature->mission_handle, docstrings corrected. OUT-OF-MAP EDITS (declared): tests/status/test_transition_request_owned.py (3372fa798, extends TestExactlyOneOwnershipValidation with the flagless-adoption single-validation assertion); tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py (a5a251528, then reworked in 2c52d9c87 for emit_owned_refusal); src/specify_cli/cli/commands/_owned_checkout.py (2c52d9c87, WP08 file: type-only @overloads); src/specify_cli/tasks/issue_matrix.py (19a8bd6c3, WP17 file: additive fold_into_caller_commit keyword - WP17 T090 must keep it when converting scaffold_issue_matrix) + tests/specify_cli/tasks/test_issue_matrix_scaffold.py. Red-first history of the earlier commits is unchanged (no rewrite).
- 2026-09-29T09:09:07Z – claude – Fix cycle 2 (items 1-5 done; item 6 WAITING on WP09 approval + lane-h merge into lane-l, so WP13 is intentionally NOT moved to for_review). (1) ContextVar leak: red d-pin commit then fix - stale-copy envelope var is now bound under a token and reset in a finally around the whole finalize body; comment explains why a scoped ContextVar and not ~30 threaded emitter signatures. (2) The resolve_owned_or_adopt @overloads are reverted: _owned_checkout.py is byte-identical to the pre-WP13 base again (this withdraws the earlier declared out-of-map WP08 edit); G5 in _owned_checkout.py is back to 2, mission_finalize.py G5 stays 0. (3) spec_kitty_version added to the owned-claim refusal envelope via _with_cli_version (red pin first; indent=2 kept). (4) issue_matrix.py: one shared _atomic_write_issue_matrix helper used by write_issue_matrix and the fold branch; tests/specify_cli/tasks/test_issue_matrix_scaffold.py restored to base plus only the two new test hunks (40 insertions, 0 deletions vs base). HISTORY NOTES (history is not rewritten): commit 3372fa798 bundled the FR-021 flagless adoption and the FR-007 field together with their tests in a single commit, so those two behaviors have no separate red commit (their red proof is the cycle-1 review reproduction and the later red-first pins); 3372fa798 (tests/status/test_transition_request_owned.py) and a5a251528 (tests/specify_cli/cli/commands/agent/test_mission_finalize_phases.py) made out-of-map edits that their commit bodies did not declare - declared here. Also 9eb592720 is a pure refactor (routing through resolve_owned_or_adopt) that precedes the first T070 test commit.
- 2026-09-29T10:10:47Z – claude – Fix cycle 2 item 6 done (WP09 approved, lane-h merged into lane-l; nothing copied). Armed get_main_repo_root pins (every alias patched, each armed call recorded AND raised, scoped to emit_artifact_phase_local's lifecycle-log root walk) were committed red first: owned finalize recorded TasksStarted + TasksCompleted, owned mission create recorded SpecifyStarted. Fix: mission_finalize.py passes repo_root=owned.repository_root on TASKS_STARTED and TASKS_COMPLETED; core/mission_creation.py (WP10 file, DECLARED minimal out-of-map edit) passes the create's resolved repository root for SPECIFY_STARTED when the checkout is owned. FOUND, NOT FIXED (need WP09-owned status/lifecycle_events.py API; report to orchestrator): emit_wp_created_local (WPCreated, called from mission_finalize._emit_local_canonical_events) and emit_mission_created_local (MissionCreated, called from mission_creation) have no repo_root parameter and still reach get_main_repo_root via append_lifecycle_event -> persist_lifecycle_event_local -> _repo_root_for_lifecycle_log on owned paths. Also observed (resolver reads, not lifecycle-log writes; out of this pin): scaffold_issue_matrix -> coord_read_dir_for and bootstrap_canonical_state's status transaction (mission_has_coordination_branch -> resolve_topology) read get_main_repo_root after the fact is minted. Fix cycle 2 items 1-5 as recorded in the previous entry.
- 2026-09-29T10:20:52Z – claude – Item 6 follow-up (added while WP13 sits in for_review; no move-task). WPCreated and MissionCreated now write against the fact's repository root: additive repo_root=None parameters on append_lifecycle_event, emit_wp_created_local and emit_mission_created_local (DECLARED minimal out-of-map edit: status/lifecycle_events.py, WP09's file, same style as WP09's persist_lifecycle_event_local/emit_artifact_phase); call sites pass owned.repository_root (mission_finalize._emit_local_canonical_events) and the create's resolved repository root (core/mission_creation.py, WP10's file, declared). Red first: the armed get_main_repo_root pin widened to any _repo_root_for_lifecycle_log call failed on the prior head (finalize: emit_wp_created_local -> append_lifecycle_event -> persist_lifecycle_event_local; create: MissionCreated persistence failed). REMAINING post-mint get_main_repo_root reads, enumerated by the pin (all pass-through resolver READS, none a write against R): owned create = 0; owned finalize = 68 calls, every one under one of three subsystems - bootstrap_canonical_state (mission_has_coordination_branch/resolve_topology, _resolve_dependency_readiness/_declared_dependencies, ledger_posture/_resolve_repo_root, planning/topology path composition), commit_for_mission (placement/topology resolution of the commit target), scaffold_issue_matrix (coord_read_dir_for surface classification). They compute WHICH directory or branch to consult; repository-root-only by design (coordination-branch topology lives at R). The pin asserts every pass-through chain sits under one of those anchors and that R's files/HEAD/index/locks/home are byte-identical after the full successful run (RSnapshotter, status mutex tolerated), so none writes against R. mypy --strict on the 3 touched files: 5 errors on base and head (identical, 0 new); G5 mission_finalize.py = 0; ruff clean; C901 in _create_mission_core_impl is pre-existing (40 on the base, already suppressed).
- 2026-09-29T10:28:27Z – claude – Integration: lane-i (approved WP10) merged into lane-l (32f944025). core/mission_creation.py taken from lane-i's decomposed version; the WP13 owned-create lifecycle root is re-applied in the helper where the emissions now live: _emit_create_events gains lifecycle_root (the OwnedCreateRoot.repository_root when owned, else None) and passes it as repo_root= to emit_mission_created_local (MissionCreated) and emit_artifact_phase_local (SpecifyStarted); caller passes roots.owned.repository_root. WP10's decision-record comments/complexity kept: every function <=15 with --ignore-noqa, no C901 suppression. The owned-create armed get_main_repo_root pin was re-armed on WP10's API (resolve_owned_create_root then create_mission_core(owned_create_root=...)); mutation (repo_root=None) turns it red. Declared out-of-map edit remains core/mission_creation.py (WP10 file). kitty-specs status.json/status.events.jsonl show as worktree-deleted but are the coordinator-resolved planning-repo copies; untouched by me.
- 2026-09-29T10:54:46Z – claude – Fix cycle 3. (1) mypy: _FinalizeRequirementGates.expected_wp_ids typed list[str] (was set[str]); standard invocation now includes the callee mission_parsing.py (commit body lists the 16-file set): base 5faee3662 = 6 errors, head = 6 (0 new); with status_transition.py added, 9 vs 9. (2) DEPENDENCY-CONTENT LEAK FIXED IN WP13 per orchestrator ruling, not deferred: status/emit.py _declared_dependencies re-anchored the planning dir through resolve_canonical_root to R, so an owned planned->claimed read WP dependencies from R (absent copy = none; stale copy = wrong). _resolve_dependency_readiness/_declared_dependencies take owned: OwnedCheckout | None = None and, with a fact, read owned.mission_dir; coordination/status_transition.py passes identity.owned at its two transactional call sites (only when held). DECLARED minimal out-of-map edits: status/emit.py (WP07), coordination/status_transition.py. Red first (2 params: R copy absent / stale declaring none): move-task WP02 --to doing --owned-checkout P succeeded despite P declaring dependencies [WP01]; now refused 'unsatisfied dependencies'. Mutation (dropping owned= at the call sites) turns the claim pin and the finalize ledger pin red. (3) The three broad resolver anchors are replaced by an exact shrink-only ledger, reads attributed to the outermost resolver entry frame; FINAL LEDGER (50 post-mint pass-through reads on an owned finalize, was 68): coord_read_dir_for 17 (scaffold_issue_matrix surface classification), mission_has_coordination_branch 18 (status-transaction topology probe), _resolve_group_placement 13 (commit_for_mission placement), ledger_posture 2 (drain posture); anything under _declared_dependencies is forbidden outright; unclassified reads fail; the inaccurate 'only compute WHICH directory' comment is corrected. R is byte-identical after the run (RSnapshotter).
- 2026-09-29T11:19:38Z – claude – Fix cycle 4. (1) Conditional kwargs removed: coordination/status_transition.py passes owned=identity.owned unconditionally at both readiness call sites; tracking_readiness in tests/status/test_dependency_guard.py widened to (planning_dir, wp_id, snapshot, *, owned=None) and forwards owned (DECLARED out-of-map test edit, WP07's file). (2) Missed thread fixed: _run_finalize_validation_gates now passes owned=ctx.owned to _scaffold_issue_matrix_if_present, so an owned finalize runs the owned arm (WP17 effective_root bridge fires, owned fail-closed raise is live). Red first: the scaffold received no effective_root and an owned scaffold failure only warned; now it receives the owned root and fails closed. (3) Ledger: equality (no headroom), keyed on (outermost resolver entry frame, immediate caller of get_main_repo_root); 50 -> 37 post-mint reads. FINAL EXACT LEDGER: (mission_has_coordination_branch,_compose_primary_feature_dir) 16; (mission_has_coordination_branch,resolve_topology) 2; (_resolve_group_placement,_compose_primary_feature_dir) 12; (_resolve_group_placement,resolve_topology) 1; (candidate_feature_dir_for_mission,_compose_primary_feature_dir) 4 [the scaffold's legacy effective_root bridge via placement_seam; WP17 T090 removes it]; (ledger_posture,resolve_canonical_root) 2. coord_read_dir_for is gone. _declared_dependencies ban kept. Mutation: one extra get_main_repo_root call inside _resolve_group_placement adds key (_resolve_group_placement,_resolve_group_placement):1 and turns the pin red (file restored via git checkout). mypy --strict on the reviewer's 16-file set: base 5faee3662 = 9, head = 9.
