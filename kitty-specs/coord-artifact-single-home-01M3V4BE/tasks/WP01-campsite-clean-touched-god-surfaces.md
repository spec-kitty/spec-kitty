---
work_package_id: WP01
title: Campsite-clean the functions this Mission changes (IC-01)
dependencies: []
requirement_refs:
- NFR-003
- NFR-004
- NFR-005
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T10:12:14.171418+00:00'
subtasks:
- T001
- T005
- T006
- T007
phase: Phase 0 - Campsite and harness
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/
create_intent:
- tests/coordination/test_surface_resolver_anchor_helpers.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/coordination/commit_router.py
- src/specify_cli/coordination/surface_resolver.py
- tests/coordination/test_commit_router.py
- tests/coordination/test_surface_resolver_anchor_helpers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Campsite-clean the functions this Mission changes (IC-01)

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
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

This is the **tidy-first opening step** of the Mission (charter Standing Order 2, DIRECTIVE_025). It changes **no behaviour**. It makes room for the functional changes later WPs land in the same functions, so that none of them crosses the complexity ceiling (NFR-004: C901 ≤ 15).

Success means:

- Every function in the extraction table below has C901 **≤ 10** after this WP (headroom for the later WPs), measured with `ruff check --select C901`.
- Each extraction is a **behaviour-preserving** move of an existing block into a named, private helper in the **same file**.
- The owning test files pass **before and after**, with **no assertion edits**.
- Every new helper has a focused test that executes it directly (NFR-003: ≥ 90% coverage of new or changed lines).
- `ruff check`, `ruff format --check` and `mypy --strict` are clean on the changed files, with no new suppressions (NFR-005).
- Each extraction leaves a **single seam** that a named later WP will change (this is why the helpers are cut where they are):

| Function | Location (ecb5dd914a) | C901 now | Later WP that changes it |
|----------|-----------------------|----------|--------------------------|
| `spec_commit_command` | `spec_commit_cmd.py:155` | 15 | WP13 (render step, help text) |
| `record_report_transaction` | `git/report_transaction.py:130` | 15 | WP14 (outcome rendering at the `commit_for_mission` call, ≈L199) |
| `finalize_tasks` | `agent/mission_finalize.py:4758` | 14 | WP15 (default planning-pin refresh, options ≈L4779-4794) |
| `_commit_planning_pin_refresh_locked` | `agent/mission_finalize.py:2807` | **15** | WP15 (pin-refresh outcome rendering, ≈L2874) |
| `_ft_apply_writes` | `agent/tasks_finalize.py:250` | 14 | WP15 (`read_dir(STATUS_STATE)` → `write_dir` at ≈L444) |
| `_stage_artifacts_in_coord_worktree` | `coordination/commit_router.py:991` | 13 | WP05 (owning-surface translation at the STATUS_STATE skip, L1038) |
| `resolve_status_surface_with_anchor` | `coordination/surface_resolver.py:1192` | 12 | WP04 (loud EMPTY warning, ≈L1430-1450) |

> **Manifest note:** `_commit_planning_pin_refresh_locked` is not in plan.md's IC-01 table. A re-measure at the base found it at C901 **15**, and WP15 renders its commit outcome (the `commit_for_mission` call at ≈L2874 sits inside it). It is therefore added here. Any branch WP15 added would otherwise break the ceiling.

## Context & Constraints

- **Load the charter**: `.kittify/charter/charter.md`, then `spec-kitty charter context --action implement --json`.
- **Plan**: `kitty-specs/coord-artifact-single-home-01M3V4BE/plan.md` IC-01 (the C901 table and its risks) and the "Shared-file (lane-conflict) map".
- **Spec**: NFR-003, NFR-004, NFR-005; Constraint C-006 (no heavy suites).
- **Research**: none of D1-D23 changes behaviour here. The seams you cut are where D7 (router), D10/D16 (finalize), D8 (renderers) and D4 (EMPTY warning) later land.
- **Locality (DIRECTIVE_024)**: every extraction stays inside the file that holds the function. Do not move code across modules, and do not rename public symbols. `resolution.py` is explicitly *not* touched; it has nothing ≥ 10.
- **Do not touch**:
  - `record_analysis` (`mission_record_analysis.py:225`, C901 13). ~~Plan: its consumer at L374 lives in `_maybe_auto_commit`, so the function itself is not changed.~~ Struck (round 5): the commit is inside `record_analysis` itself (L355-391), and WP14 extracts it. Not this WP's work.
  - The C901 10-11 functions (`setup_plan`, `_wrap_with_decision_git_log`, `_build_create_meta`, `decisions/verify.py::verify`, `commit_workflow_change`). They have enough headroom.
- **Purity**: `resolve_status_surface_with_anchor` is reached from `resolve_placement_only` (`resolution.py:1974-1982` via `_assemble_core_fragments(for_write=True)`). It must stay side-effect free, and so must any helper you extract from it.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology canon**: say Mission, never feature. Always name the sense of "primary": PRIMARY partition / repository root checkout / target branch.
- **No heavy suites** (C-006, NO_FULL_HEAVY_SUITES_IN_MISSION).
- **Brownfield scout (binding read)**: before coding, read `## WP01` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp01-11.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: `issue-5440-coord-artifact-single-home`
- **Merge target branch**: `issue-5440-coord-artifact-single-home`
- `spec-kitty agent mission finalize-tasks` allocates execution worktrees per computed lane from `lanes.json`.
- Start with `spec-kitty agent action implement WP01 --agent claude`. Work in the workspace path it prints; never reconstruct it.
- **Lane-relevant shared files.** This WP opens **lane A**. It shares owned files with WP04 (`surface_resolver.py`) and WP05 (`commit_router.py`, `tests/coordination/test_commit_router.py`). Both depend on this WP, so they run after it in the same lane.
- **Post-tasks squad P-m7:** the extractions of `spec_commit_command`, `record_report_transaction` and `finalize_tasks` / `_commit_planning_pin_refresh_locked` / `_ft_apply_writes` (former T002/T003/T004) moved into WP13/WP14/WP15 as each WP's tidy-first first commit. Those WPs now run in their own lanes. This WP keeps T001 (baseline over all twelve functions, which is still the reference table), T005, T006 and T007. In the rest of this prompt, ignore guidance that names the moved functions as this WP's work.
  - Keep the extractions minimal and well-named, so those WPs rebase onto clean seams.

## Subtasks & Detailed Guidance

### Subtask T001 – Baseline: complexity numbers and green test counts

- **Purpose**: Establish the "before" picture that proves behaviour preservation, and catch any drift from the plan's table.
- **Steps**:
  1. Run the complexity measurement:
     ```bash
     uv run --frozen ruff check --select C901 --config 'lint.mccabe.max-complexity=9' --output-format concise \
       src/specify_cli/cli/commands/spec_commit_cmd.py src/specify_cli/git/report_transaction.py \
       src/specify_cli/cli/commands/agent/mission_finalize.py src/specify_cli/cli/commands/agent/tasks_finalize.py \
       src/specify_cli/coordination/commit_router.py src/specify_cli/coordination/surface_resolver.py
     ```
     Expected at the base: `spec_commit_command` 15, `record_report_transaction` 15, `finalize_tasks` 14, `_commit_planning_pin_refresh_locked` 15, `_ft_apply_writes` 14, `_stage_artifacts_in_coord_worktree` 13, `resolve_status_surface_with_anchor` 12. Also reported, but out of scope: `_emit_requirement_mapping_report` 13, `_bootstrap_one_wp` 11, `_validate_ownership_manifests` 11, `_compute_and_write_lanes` 10, `_coord_branch_exists` 10.
  2. Run each owning test surface listed under "Targeted test surface". Record passed/failed/skipped counts per file in the Activity Log.
  3. Any failure at the base: classify it with the baseline-red gotcha in `CLAUDE.md` (pre-existing P0 / CI-env / stale install / stale venv) **before** editing. Record it; do not fix unrelated reds here.
- **Files**: none changed.
- **Validation**: the Activity Log has a before table (function → C901) and before counts (file → pass/fail).
- **Edge cases**: if a number differs from the table, cite the measured value and extract to ≤ 10 anyway.

### Subtask T005 – Extract from `_stage_artifacts_in_coord_worktree` (commit_router.py:991, C901 13)

- **Purpose**: WP05 changes how a COORD-record input is treated:
  - **today**: the STATUS_STATE skip at L1038 (`if kind_for_mission_file(rel) is MissionArtifactKind.STATUS_STATE: continue`);
  - **after WP05**: translation to the owning-surface copy via `write_dir`.

  The per-path decision must live in one helper, so WP05 changes behaviour in one place.
- **Steps**:
  1. Read L991 through the `return coord_files` at the end, about L1090. The per-path loop holds:
     - the already-in-worktree branch (`is_under_worktrees_segment(rel)` at L1026, plus `_is_directly_in_worktree`; comment cites #5353);
     - the STATUS_STATE skip (L1038);
     - the `analysis-report.md` skip (FR-003 re-home);
     - the legacy `copy2` staging into the coordination worktree;
     - after the loop, the residue cleanup over `primary_paths_created_this_invocation` (≈L1069-1088).
  2. Extract a pure per-path classifier, for example `_classify_stage_path(src, rel, coord_worktree) -> _StagePlan`. `_StagePlan` is a small enum or a frozen dataclass naming the action: `IN_PLACE` / `SKIP_STATUS_LOG` / `SKIP_ANALYSIS_REPORT` / `COPY(dst)`.
  3. Extract `_cleanup_staging_residue(staged_sources, primary_paths_created_this_invocation, repo_root)` for the post-loop residue cleanup, with its logging unchanged.
  4. The loop becomes: classify → act. The order of `coord_files` entries must stay identical, because commit staging order can matter in tests.
- **Files**: `src/specify_cli/coordination/commit_router.py`; tests in `tests/coordination/test_commit_router.py`.
- **Validation**:
  - Unchanged and green: `tests/coordination/test_commit_router.py`, `tests/coordination/test_commit_router_fail_loud.py`, `tests/coordination/test_commit_router_layering.py`, and `tests/specify_cli/coordination/test_commit_router_partition*.py`.
  - New tests exercise `_classify_stage_path` for each action: a status log, an `analysis-report.md`, a trace file, an already-in-worktree path, and a root path outside the worktree.
- **Edge cases**:
  - Keep the long rationale comments (#5353, WP13 IC-07c, FR-003) attached to the branch they explain, now inside the classifier.
  - Do not delete `_try_advance_ref` or touch L560-561 here. WP05 does that red-first.

### Subtask T006 – Extract from `resolve_status_surface_with_anchor` (surface_resolver.py:1192, C901 12)

- **Purpose**: WP04 makes the read-side EMPTY warning fire for post-fix Missions in both coordination topologies (today it fires only when `effective_topology is MissionTopology.LANES_WITH_COORD`, ≈L1440). The EMPTY branch should be one helper, and the function must stay pure.
- **Steps**:
  1. Read L1192 to the end of the function (≈L1454). It contains:
     - the completed-Mission shortcut `if not for_write and _primary_mission_is_completed(primary_dir)` (≈L1267);
     - topology disposal;
     - the coordination-state probe;
     - the `if coord_state is CoordState.EMPTY:` branch, which logs `_COORD_EMPTY_FALLBACK_WARNING` and returns the PRIMARY surface (≈L1430-1450);
     - the MATERIALIZED return.
  2. Extract `_empty_coord_surface(feature_dir, composed_coord_dir, mission_slug, effective_topology) -> ResolvedStatusSurface`. It holds the EMPTY branch: the warning decision plus the PRIMARY return. **WP04 adds the post-fix discriminator here.**
  3. Extract the completed-Mission shortcut decision into `_completed_primary_surface(...) -> ResolvedStatusSurface | None` if that block is a complexity source.
  4. No new side effects: no git writes, no directory creation, no materialization.
- **Files**: `src/specify_cli/coordination/surface_resolver.py`; new `tests/coordination/test_surface_resolver_anchor_helpers.py`.
- **Validation**:
  - Unchanged and green: `tests/coordination/test_surface_resolver_coord_empty_warning.py`, `test_surface_resolver_collapse.py`, `test_surface_resolver_solo_coord_primary.py`, `tests/specify_cli/coordination/test_coord_topology_states.py`, `tests/status/test_aggregate_surface_resolution.py`.
  - New tests call `_empty_coord_surface` for both topologies and assert:
    - the warning fires for `lanes_with_coord` only, which is today's behaviour (use `caplog`);
    - the returned surface is the PRIMARY dir.
- **Edge cases**:
  - The module-level warning constant and its `%`-style args dict must stay identical, because tests match the message.
  - `for_write=True` callers must observe identical results.

### Subtask T007 – Behaviour-preservation proof and quality gates

- **Purpose**: Make the tidy-first claim verifiable for the reviewer.
- **Steps**:
  1. Re-run the T001 complexity command. The after-table must show every target ≤ 10, and no new function > 10 created by the extractions.
  2. Re-run every T001 test surface. The counts must be identical to before, plus your new helper tests.
  3. `git diff <base> -- 'tests/**'` must show **no edited assertions** in pre-existing tests. Only new tests or new test classes are appended.
  4. Run the static gates:
     - `uv run --frozen ruff check <changed files>`
     - `uv run --frozen ruff format --check <changed files>`
     - `uv run --frozen mypy --strict <changed src files>`
  5. Run `tests/architectural/test_no_dead_symbols.py` only if you exported new public names. Prefer private `_helpers`, which avoids that.
- **Files**: none new.
- **Validation**: the Activity Log carries the after-table, the test counts, and the static-gate results.
- **Edge cases**: one commit per extraction (T005, T006) is ideal. The reviewer can then bisect a behaviour change to one extraction.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **T005 `_StagePlan` has FIVE outcomes**: IN_PLACE, SKIP_STATUS_LOG, SKIP_ANALYSIS_REPORT, COPY(dst) and **DROP_FOREIGN_WORKTREE**. The last one covers a path under `.worktrees/` that is not this worktree, including an `analysis-report.md` there. `commit_router.py:1026-1029` `continue`s without appending it, as pinned by `test_commit_router.py::test_coord_staging_drops_a_status_log_from_another_worktree` (both params). Never fold DROP into a SKIP that WP05 might later translate.
- **COPY semantics**: L1062-1067 appends `dst` to `coord_files` **even when `src` is absent** (no copy, still listed), and only the copied pairs go into `staged_sources`. Keep both behaviours; a classifier that returns COPY only when `src.exists()` is a silent behaviour change.
- **Propagate and keep as-is**:
  - `src.relative_to(repo_root)` (L1018) raises `ValueError` for a path outside the repo; let it propagate.
  - Keep `.resolve()` inside `_is_directly_in_worktree`, which the symlink pin `test_commit_router.py:876` depends on.
  - Keep the `is_under_worktrees_segment` import function-local; `test_commit_router_layering.py` AST-scans for it.
  - Keep the alias `_stage_finalize_artifacts_in_coord_worktree = …` assigned **after** the def, not as a wrapper. It is re-exported by `agent/mission.py:298` and pinned by `test_mission_shim_reexports.py:91`.
- **T005 validation adds**: `tests/specify_cli/cli/commands/agent/test_finalize_coord_staging.py`, `.../agent/test_finalize_clobber_e2e.py`, `tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py`, `.../agent/test_mission_shim_reexports.py`.
- **T006**:
  - ruff `ARG` is enabled, so do **not** pre-add `repo_root`/`coord_branch` parameters to `_empty_coord_surface`; WP04 widens that private signature itself.
  - Move the `logger.warning(_COORD_EMPTY_FALLBACK_WARNING, {...})` call (L1443-1446, mapping-style args) **verbatim**.
  - Move the `.parent.parent` expressions at L385/L1445 verbatim; do not "fix" them.
  - C901 headroom: extracting only the EMPTY branch gives about 10. Also extract the completed-Mission shortcut or the `meta is None` fallback (L1341-1358). If you extract the latter, check `_load_meta_census.py` for an un-keyed census count.
- Keep every extracted name private (dead-symbol gate scans public names only).
- Run the scout's quick-run commands by name. Baseline: 513 passed / 10 skipped with `-n 4 --dist loadfile`.

## Targeted test surface

- Baseline: `make test-fast`.
- Owning modules (run each by name):
  ```bash
  uv run --frozen pytest tests/coordination/test_commit_router.py tests/coordination/test_commit_router_fail_loud.py tests/coordination/test_commit_router_layering.py tests/specify_cli/coordination/ -q
  uv run --frozen pytest tests/coordination/test_surface_resolver_coord_empty_warning.py tests/coordination/test_surface_resolver_collapse.py tests/coordination/test_surface_resolver_solo_coord_primary.py tests/coordination/test_surface_resolver_anchor_helpers.py tests/status/test_aggregate_surface_resolution.py -q
  ```
- Named architectural gate files only:
  - `tests/architectural/test_layer_rules.py` (sanity; nothing crosses a layer here);
  - `tests/architectural/test_no_dead_symbols.py`, only if public names were added.
  - `test_commit_router_layering.py` lives in `tests/coordination/` and is already in the list above.
- Never run the bare `tests/architectural/`, any e2e/integration directory, performance/stress suites or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record commands plus pass/fail counts in the Activity Log for the PR's *Tests run* section. Classify any red with the CLAUDE.md baseline-red gotcha before attributing it to this WP.

## Quality gates

- C901 ≤ 15 for every touched function (NFR-004). The target here is ≤ 10, for headroom.
- `ruff check` and `ruff format --check` clean on changed files. `mypy --strict` clean on changed `src/` files (NFR-005), with no new `# noqa` / `# type: ignore`.
- ≥ 90% coverage of new or changed lines (NFR-003, diff-cover gate). Each new helper gets a direct test.
- New public symbols: run `tests/architectural/test_no_dead_symbols.py`. Prefer private helpers.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: none owed directly (behaviour-preserving enabler; no issue-matrix row).

## Definition of Done

- All seven target functions are at C901 ≤ 10, with before/after tables in the Activity Log.
- Pre-existing tests are unchanged and green; new helper tests are green.
- Each later-WP seam named in the objectives table exists as one helper:
  - `_render_spec_commit_result`
  - `_commit_report`
  - the finalize options helper
  - `_commit_pin_refresh_files`
  - `_ft_emit_status_events`
  - `_classify_stage_path`
  - `_empty_coord_surface`
- ruff, ruff format and mypy --strict are clean; no new suppressions.
- No behaviour change: CLI output of spec-commit (text and JSON) is byte-identical on a sample run.

## Risks & Mitigations

- **Accidental behaviour change during extraction.** Mitigations: one extraction per commit, no assertion edits, CLI output diffs for spec-commit.
- **Lock or CAS semantics moved** in the pin-refresh path. Mitigation: keep lock acquisition at the same call depth, and keep the byte-compare guard immediately before the commit.
- **Purity of the surface resolver broken.** Mitigation: the extracted helpers take values, not handles that can write. A test asserts no directory is created.
- **Lane-A rebase friction for WP04/05.** Mitigation: minimal, clearly named seams, and no opportunistic renames.

## Review Guidance

- Reviewer: opus, distinct from the implementer.
- This WP has no product red test. The "red→green" check is instead:
  1. The same pre-existing tests pass at the base and at the final commit, with **zero assertion edits** (`git diff <base> -- tests/` shows only additions).
  2. The C901 after-table shows every target ≤ 10.
  3. Each named seam helper exists and is directly tested.
- Spot-check that `resolve_status_surface_with_anchor` and its helpers do no I/O beyond what the base did.
- Confirm `record_analysis` and the C901 10-11 functions are untouched.

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

**Why this matters**: The acceptance system reads the LAST activity log entry as the current state. If entries are out of order, acceptance will fail even when the work is complete.

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
