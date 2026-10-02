---
work_package_id: WP10
title: 'Write-seam writers: tracer, issue matrix, acceptance matrix'
dependencies:
- WP05
- WP07
requirement_refs:
- FR-003
- FR-007
- SC-003
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T23:59:21.978019+00:00'
subtasks:
- T053
- T054
- T055
- T056
- T057
- T058
phase: Phase 3 - Writer migration
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/write_seam.py
create_intent:
- tests/coordination/test_write_seam_surfaces.py
- tests/retrospective/test_tracer_writer_write_dir.py
- tests/tasks/test_issue_matrix_write_dir.py
- tests/acceptance/test_acceptance_matrix_write_dir.py
- tests/specify_cli/cli/commands/agent/test_tracer_append_outcome.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/coordination/write_seam.py
- src/specify_cli/retrospective/tracer_writer.py
- src/specify_cli/tasks/issue_matrix.py
- src/specify_cli/cli/commands/agent/acceptance_verdict.py
- src/specify_cli/acceptance/matrix.py
- tests/coordination/test_write_seam_surfaces.py
- tests/retrospective/test_tracer_writer_write_dir.py
- tests/tasks/test_issue_matrix_write_dir.py
- tests/acceptance/test_acceptance_matrix_write_dir.py
- src/specify_cli/cli/commands/agent/tracer_append.py
- tests/specify_cli/cli/commands/agent/test_tracer_append_outcome.py
- src/specify_cli/cli/commands/agent/issue_verdict.py
- src/specify_cli/acceptance/gates_core.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Write-seam writers: tracer, issue matrix, acceptance matrix

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

Migrate the three **stage-and-copy writers** that go through the shared write seam (`coordination/write_seam.write_artifact`) to write COORD-partition records **in place** at `PlacementSeam.write_dir(kind)`. The three writers are the tracer, the issue matrix and the acceptance matrix. Then carry and render the per-surface commit outcome through the seam's result.

Done means:

- On a coordination-routed Mission, the following write directly into the coordination worktree's Mission dir and commit there:
  - a tracer append (`spec-kitty agent tracer-append` / `append_tracer_finding`): `traces/<file>.md`;
  - an issue-matrix scaffold or update: `issue-matrix.json`;
  - an acceptance-matrix write (`spec-kitty agent ... acceptance verdict` path → `write_and_commit_acceptance_matrix`): `acceptance-matrix.json`.

  The repository root checkout keeps **no** copy or residue (spec edge case "Transient staging").
- `WriteSeamResult` carries `surfaces` (and stops dropping `commit_hashes` / `reason`). The three consumer sites render through WP05's `render_commit_outcome` / `commit_outcome_payload`: `tracer_writer.py` ≈L298, `issue_matrix.py` ≈L404, `acceptance/matrix.py` ≈L524. A skipped or refused surface is visible to callers (FR-007, SC-003).
- A refused write (unroutable, remote-only, DELETED, fork) still touches no disk: the #3073 zero-residue `stage=` thunk property is preserved.
- `lanes` / `single_branch` behave as before (C-008).

## Context & Constraints

- **Spec**: FR-003 (families "tracer", "the issue and acceptance matrices"), FR-007 (consumers "the write seam and its callers: the tracer, the issue and acceptance matrices, and accept's coordination residuals"; accept's residuals move off the seam in WP16), SC-003, edge case "Transient staging", US2.1 (tracer entry in the same lifecycle).
- **Plan**: IC-04 (rows Tracer, Issue matrix, Acceptance matrix), IC-07 (write seam wrapper and its callers).
- **Research**: D1, D8 (consumer table: write seam `write_seam.py:548` "drops hashes/reason"; matrix ≈:524, issue matrix ≈:404, tracer ≈:298; "Discarded-result sites render a warning only when a surface is not committed/unchanged"; exit-code rule).
- **Contracts**: `contracts/commit-outcome.md`, `contracts/write-location-accessor.md`.
- **Verified code facts (at ecb5dd914a)**:
  - `write_seam.py`: `WriteSeamResult` at L215 (fields `status`, `entry_id`, `destination_surface`, `commit_hash`, `diagnostic`); `write_artifact` at L460. It probes routability first, invokes the `stage=` thunk only after the probe succeeds, then calls `commit_for_mission` (≈L548) and builds the result from `status`/`placement_ref`/`commit_hash`/`diagnostic` only.
  - `tracer_writer.py`: `_local_staging_path` at L199 uses `candidate_feature_dir_for_mission` (L213), a read resolver, so the trace is staged in the repository root checkout and copied by the router. The `_stage` thunk + `write_artifact(... kind=TRACER_FILE, primary_paths_created_this_invocation=frozenset({local_path}))` is at ≈L285-310. `append_tracer_finding` is at L227. The CLI is `spec-kitty agent tracer-append` (`cli/commands/agent/__init__.py:33`).
  - `issue_matrix.py`: `scaffold_issue_matrix` at L448. Its dir comes from `coord_read_dir_for(...) or feature_dir` (≈L505), or `placement_seam(...).read_dir(ISSUE_MATRIX)` for owned (≈L503). `write_issue_matrix` → `write_artifact` at ≈L393-415.
  - `acceptance_verdict.py`: `_matrix_read_dir` at L87 uses `placement_seam(...).read_dir(ACCEPTANCE_MATRIX)`. `acceptance/matrix.py`: `write_acceptance_matrix` L449 (raw writer, byte-identical for many fixtures), `write_and_commit_acceptance_matrix` L469 (seam call ≈L524), `read_acceptance_matrix` L537.
- **Upstream**: WP05 (`CommitRouterResult.surfaces`, `commit_outcome.py`), WP03/WP04 (accessor), WP02 (fixtures).
- Load the charter and `spec-kitty charter context --action implement --json`.
- **Model discipline**: implement with sonnet (`claude-sonnet-5`); review with opus.
- **Terminology**: "Mission", never "feature". Name each sense of "primary".
- **Fixture semantics across lanes (post-tasks squad P-m5):** pre-fix assertions use WP02's `make_prefix_coord_mission`; `make_coord_mission` carries only shape-agnostic invariants (its shape changes when WP06 lands); use `make_coord_mission(..., materialized=True)` when a test needs a deterministic MATERIALIZED coordination surface in every lane.
- **Brownfield scout (binding read)**: before coding, read `## WP10` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp01-11.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- `finalize-tasks` allocates execution worktrees per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP10 --agent claude`, and use the printed workspace path.
- **Lane notes**: this WP's ownership is disjoint, so it gets its own lane, based on WP05's tip (lane A). It runs in parallel with WP07/WP09. WP16 (accept) changes accept's residual leg to call the router directly, so do not edit `cli/commands/accept.py` here.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T053 – Red-first: in-place writes with no root residue, unmasked seam outcomes

- **Purpose**: Pin the contract through the pre-existing entry points first (ATDD-First, C-005). Commit separately, before any fix.
- **Steps**:
  1. `tests/retrospective/test_tracer_writer_write_dir.py`: on a coordination Mission (WP02 `make_coord_mission`, parametrized `coord`/`lanes_with_coord`, plus `make_prefix_coord_mission(worktree="empty")`), run `spec-kitty agent tracer-append ...` (check its options in `cli/commands/agent/tracer_append.py`) or `append_tracer_finding(...)`. Assert:
     - the coordination branch tip carries `kitty-specs/<dir>/traces/<file>.md` with the entry;
     - the file exists in the coordination worktree;
     - the repository root checkout has NO `traces/<file>.md` change (`git status --porcelain -- kitty-specs/<dir>` empty) and no untracked copy;
     - for the pre-fix EMPTY variant, the status log was seeded once before the tracer commit (one seed commit on the coordination branch).
  2. `tests/tasks/test_issue_matrix_write_dir.py`: the same for `scaffold_issue_matrix` / `write_issue_matrix` (a spec.md that references `#123`).
  3. `tests/acceptance/test_acceptance_matrix_write_dir.py`: the same for the acceptance-verdict path (`acceptance_verdict.py` command, or `write_and_commit_acceptance_matrix` with the dir from `_matrix_read_dir`).
  4. `tests/coordination/test_write_seam_surfaces.py`: `write_artifact` with a monkeypatched `commit_for_mission` returning a `CommitRouterResult` whose `surfaces` has one committed and one refused (`STATUS_LOCK_HELD`). Assert `WriteSeamResult.surfaces` carries both, and `commit_hashes` / `reason` are present (red at base: dropped).
  5. Run on the lane base. Expected RED: root staging residue or root-located writes, and dropped surfaces. Record the output.
- **Edge cases**: at base, the tracer stages in root and the router copies into the coordination worktree. The coordination tip assertion may already pass, while the residue assertion is the red one. That is fine and expected: say so in the log.

### Subtask T054 – `WriteSeamResult.surfaces` passthrough

- **Purpose**: The write seam is a wrapper consumer. Masking at the wrapper hides refusals from every caller (FR-007).
- **Steps**:
  1. Add `surfaces: tuple[SurfaceOutcome, ...] = ()`, `commit_hashes: tuple[str, ...] = ()` and `reason: str | None = None` to `WriteSeamResult` (frozen dataclass, additive, defaults last; check whether it is frozen/slots and keep that).
  2. In `write_artifact` (≈L548-575) populate them from the `CommitRouterResult`. For the zero-write `"refused"` outcome (no router call), leave `surfaces=()` and keep `status="refused"`. For the post-consolidation direct path (`_commit_post_consolidation_write`), build one `SurfaceOutcome` for the destination it commits to, so consumers render uniformly.
  3. Update the docstring (`status` semantics unchanged; `surfaces` is the per-surface truth).
- **Files**: `src/specify_cli/coordination/write_seam.py`.
- **Validation**: T053 seam test green; `tests/coordination/test_write_seam_adoption.py` green.

### Subtask T055 – Tracer writes in place at `write_dir(TRACER_FILE)`

- **Purpose**: `_local_staging_path` (L199-213) stages the trace in the repository root checkout via `candidate_feature_dir_for_mission`. That is the stage-in-root-then-copy pattern the single-home rule forbids. It is also in WP20's census (`retrospective/tracer_writer.py::_local_staging_path`).
- **Steps**:
  1. Change `_local_staging_path` to resolve `placement_seam(repo_root, mission_slug).write_dir(MissionArtifactKind.TRACER_FILE).path / "traces" / filename` (mirror the existing relative layout). Keep the name if you can, so WP20's census qualname stays valid. If you rename it, record the new qualname in the Activity Log.
  2. **Preserve the zero-residue property.** `write_dir` can materialize and seed (side effects). Today `local_path` is computed eagerly (≈L285), before `write_artifact`'s routability probe. Move the `write_dir` call **inside** the `_stage` thunk so a refused write (probe fails) triggers no materialization or seed. Compute `primary_paths_created_this_invocation` accordingly: it names repository-root paths created this invocation for cleanup. When the write is in place on the coordination surface, pass an empty frozenset (nothing created in the root checkout). Read `write_artifact`'s use of that parameter first to get the semantics right.
  3. `base_content` (merge input for the append, read before ≈L280) must come from the owning surface: read from the coordination copy (worktree, else the coordination ref), not the root. Check how it is read today (L85 comment "resolution failure here degrades to an empty base"). Use the read resolver for READS. That is allowed, because the gate forbids read resolvers only as write locations.
  4. Render at ≈L298: `append_tracer_finding` returns the `WriteSeamResult`, and callers render it. `cli/commands/agent/tracer_append.py` (≈L135-163) hand-renders the caller-surface fields today, which is masking. This WP now owns it (post-tasks squad R-M2). Render JSON through `commit_outcome_payload` (additive: keep the existing keys `ok`, `kind`, `status`, `commit_ref`, `commit_hash`, … and add `surfaces`) and text through `render_commit_outcome`, and apply the shared exit-code rule. Test it in `tests/specify_cli/cli/commands/agent/test_tracer_append_outcome.py` with a one-surface-skipped fixture. WP20 adds it to the consumer-pin floor. Inside `tracer_writer.py`, log a WARNING via `render_commit_outcome` when a surface is not committed/unchanged ("discarded-result" rule, D8).
- **Files**: `src/specify_cli/retrospective/tracer_writer.py`.
- **Validation**: T053 tracer tests green; `tests/retrospective/test_writer*.py`, `test_retrospective_durable_home_coord.py` green.
- **Edge cases**: two appends in a row must merge (the second sees the first's line). An owned checkout uses `placement_seam(..., owned=owned)`. Thread `owned` if `append_tracer_finding` has it.

### Subtask T056 – Issue matrix writes at `write_dir(ISSUE_MATRIX)`

- **Purpose**: `scaffold_issue_matrix` (L448) uses `coord_read_dir_for(...) or feature_dir`, a read resolver with a root fallback, as its write dir (WP20 census `tasks/issue_matrix.py::scaffold_issue_matrix`).
- **Steps**:
  1. Split read and write. The existence check ("respect existing content", ≈L507-510) is a READ: keep `coord_read_dir_for` / `read_dir` for it. The write location becomes `write_dir(ISSUE_MATRIX).path`, resolved lazily inside the `_stage` thunk of `write_issue_matrix` (≈L397-415) to keep zero-write refusals residue-free.
  2. `fold_into_caller_commit` (≈L517): when the write dir equals the caller's `feature_dir` (non-coordination topologies), keep today's direct atomic write. For coordination Missions the write dir is the coordination Mission dir, so this branch must not trigger. Keep the comparison semantics and test both arms.
  3. Render at ≈L404 (`write_issue_matrix` → `write_artifact` result): best-effort semantics stay ("never blocking"), but log a WARNING through `render_commit_outcome` when a surface is not committed/unchanged.
  4. Owned arm: `placement_seam(..., owned=owned).write_dir(ISSUE_MATRIX)`.
- **Files**: `src/specify_cli/tasks/issue_matrix.py`.
- **Validation**: T053 issue-matrix test green; existing issue-matrix tests (`grep -rl "issue_matrix" tests/ | head -20`, run by file) green.

### Subtask T057 – Acceptance matrix writes at `write_dir(ACCEPTANCE_MATRIX)`

- **Purpose**: `acceptance_verdict._matrix_read_dir` (L87) uses `read_dir(ACCEPTANCE_MATRIX)` as the dir passed to `write_and_commit_acceptance_matrix` (WP20 census `agent/acceptance_verdict.py::_matrix_read_dir`).
- **Steps**:
  1. In `acceptance_verdict.py`, keep `_matrix_read_dir` for reading the current matrix. Add the write location from `write_dir(ACCEPTANCE_MATRIX).path` for the write call. Simplest: change `_matrix_read_dir` into two helpers, `_matrix_read_dir` (read) and `_matrix_write_dir` (write). If the census qualname `_matrix_read_dir` must stay the writer's location provider, make sure that function no longer feeds the writer. Record the final qualnames for WP20.
  2. In `acceptance/matrix.py::write_and_commit_acceptance_matrix` (L469): the `matrix_dir` parameter is supplied by callers. Keep the signature (many callers and fixtures). Add a keyword option or a sibling function that resolves `write_dir` lazily inside `_stage`, so a refused write doesn't materialize. Keep `write_acceptance_matrix` (L449) byte-identical (raw writer for fixtures without git). Do not touch the `gates_core._evaluate_acceptance_matrix` no-commit leg (`--no-commit` / `--diagnose` must never commit; `tests/specify_cli/test_accept_no_commit_readonly.py`).
  3. Render at ≈L524: return the `WriteSeamResult` (now with `surfaces`). In `acceptance_verdict.py`, the command output (text + `--json`) renders via `render_commit_outcome` / `commit_outcome_payload` (additive JSON key `surfaces`), with exit code non-zero when any surface is refused/error.
  4. `primary_paths_created_this_invocation`: as in T055, empty when writing in place on the coordination surface.
- **Files**: `src/specify_cli/cli/commands/agent/acceptance_verdict.py`, `src/specify_cli/acceptance/matrix.py`.
- **Validation**: T053 acceptance test green; `tests/acceptance/` (by file), `tests/integration/test_accept_matrix_coord_partition.py` and `tests/integration/test_issue_2404_acceptance_matrix_write_surface.py` (run these two named files only, never the integration directory), `tests/specify_cli/test_accept_no_commit_readonly.py` green.
- **Edge cases**: accept's own residual sweep (WP16) also picks up matrix dirt. After this WP, a coordination Mission's matrix dirt is in the coordination worktree. That's what WP16 expects (US3.6), so no change is needed here.

### Subtask T058 – Transient staging, rendering and C-008 tests

- **Purpose**: Lock in the edge case "Transient staging" and the outcome contract per consumer.
- **Steps**:
  1. For each writer, after the command returns, assert an empty root `git status --porcelain -- kitty-specs/<dir>`, and no file left under the root Mission dir that wasn't there before.
  2. Zero-write refusal: remote-only coordination branch (WP02 `remote_only=True`) → each writer returns `status="refused"` (or raises the documented error), with NO coordination worktree created, no seed, and no file written anywhere.
  3. One-surface-skipped / refused rendering per consumer (text lines from `render_commit_outcome`; JSON `surfaces` for acceptance-verdict).
  4. C-008: `lanes` and `single_branch` → each writer writes at the same path as before and commits to the same ref.
  5. Unit tests for every new helper (`_matrix_write_dir`, lazy-resolution thunks).
- **Files**: the four new test files.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **Lost update (operator decision; #4858/#4887)**: resolve `write_dir(ACCEPTANCE_MATRIX)` **once, before the lock**, in `locked_reread_splice_and_write` (`acceptance/matrix.py:546`), and pass it as `matrix_dir`. That one dir is both the re-read base and the write target, with lock key `matrix_dir.name`.
  - Its callers are `acceptance_verdict.py:319,390` and `acceptance/gates_core.py:647` (`gates_core._acceptance_matrix_read_dir`, a read dir used as a write dir; now owned).
  - **Never** split read and write dirs, or resolve `write_dir` lazily inside `_stage`, within the locked splice.
  - The seed side effect before the lock is an explicit, documented choice; record it in `design-decisions`.
  - The same applies in `src/specify_cli/cli/commands/agent/issue_verdict.py:271-285` (now owned): `feature_status_lock(repo_root, read_dir.name)` around `write_issue_matrix(read_dir...)` must use one `write_dir(ISSUE_MATRIX)` resolved before the lock.
- **Unlisted callers**: `write_issue_matrix` is also called from `issue_matrix_migration.py:370`; `write_and_commit_acceptance_matrix` from `matrix.py:910` (`scaffold_acceptance_matrix`). Cover them, or record them as read-only/unaffected with a reason.
- `append_tracer_finding` has **no** `owned` parameter, so the "thread it if present" step does not apply.
- **Tracer read before write**: `_read_current_coord_content` (L155-185) runs before the stage thunk and raises `CoordinationWorktreeUnmaterialized`, so `write_dir` never gets to materialize. Merge the base content inside `_stage`, after `write_dir`.
- **Stale allow-list entry (declared out-of-map edit)**: removing `candidate_feature_dir_for_mission` from `_local_staging_path` turns `tests/architectural/test_no_read_side_bypass.py::test_allow_list_entry_is_still_a_live_finding` red (descriptor L601-619). WP07 owns that file. This WP now **depends on WP07** and removes only its own entry, with a one-line rationale.
- **Valid guard**: `tests/mission_runtime/test_coord_read_seam_callers.py::test_tracer_append_cli_structured_refusal_on_unmaterialized` (L379). Keep the CLI `except CoordinationWorktreeUnmaterialized` / `except UnicodeDecodeError` arms when switching to the shared renderer; remote-only and DELETED still refuse.
- **PUBLISHED case**: after consolidation, tracer and matrix writes resolve to the target branch (WP04). Add one test.
- **Single write authority**: `write_artifact` calls `assert_coord_write_materialized` before `stage()`, and that is now WP03's delegate. Do not expect the old local-head refusal.
- `_matrix_read_dir` is at L89. C901: `write_artifact` ≤ 7, `tracer_append` 8.
- **Docstring follow-up from WP16**: once WP16 lands, `write_seam.py:55` must stop naming `_commit_coord_residuals` as the canonical consumer. WP16 (which depends on this WP) makes that declared out-of-map docstring edit.
- **I10 (round 4)**: post-consolidation tracer and matrix writes follow **research D23**. `write_artifact`'s gate delegating to the accessor is **D22**.

## Targeted test surface

- New: `tests/coordination/test_write_seam_surfaces.py`, `tests/retrospective/test_tracer_writer_write_dir.py`, `tests/tasks/test_issue_matrix_write_dir.py`, `tests/acceptance/test_acceptance_matrix_write_dir.py`.
- Owning-module tests (by file): `tests/coordination/test_write_seam_adoption.py`, `tests/specify_cli/coordination/test_residual_writer_routing.py`, `tests/retrospective/` (fast tier), every issue-matrix and acceptance-verdict test file (`grep -rl "issue_matrix\|acceptance_verdict\|write_and_commit_acceptance_matrix\|append_tracer_finding" tests/`), `tests/specify_cli/test_accept_no_commit_readonly.py`. Named integration files only: `tests/integration/test_accept_matrix_coord_partition.py`, `tests/integration/test_issue_2404_acceptance_matrix_write_surface.py`.
- Baseline: `make test-fast`.
- Named architectural gates only: `tests/architectural/test_no_write_side_rederivation.py`, `tests/architectural/test_write_surface_placement_guard.py`, `tests/architectural/test_layer_rules.py`.
- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006). Record commands and counts in the Activity Log. Classify unexplained reds with CLAUDE.md's baseline-red gotcha.
- Post-tasks squad addition: `tests/specify_cli/cli/commands/agent/test_tracer_append_outcome.py` and `tests/specify_cli/retrospective/test_tracer_writer_coord_e2e.py`, by name.

## Quality gates

- Keep C901 ≤ 15 for every touched function (NFR-004): `write_artifact`, `scaffold_issue_matrix`, the acceptance-verdict command body. Extract helpers rather than growing them.
- Run `ruff check`, `ruff format --check` and `mypy --strict` on the changed files, with no new suppressions (NFR-005).
- Reach ≥ 90% coverage of new and changed lines, with focused tests per new branch or helper (NFR-003). If you add public symbols, run `tests/architectural/test_no_dead_symbols.py`.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5519 #5513

## Definition of Done

- T053 tests were committed first and RED on the lane base (output recorded); all are green at the end.
- The three writers write in place at `write_dir(kind)`, with no root residue, and zero-write refusals still touch no disk.
- `WriteSeamResult` carries `surfaces` / `commit_hashes` / `reason`, and the consumers render via the shared pair.
- The C-008 controls are green, the quality gates are green, and commands and counts are logged. Final writer qualnames are recorded for WP20.

## Risks & Mitigations

- **Losing the #3073 zero-residue guarantee**: always resolve `write_dir` inside the `stage=` thunk. Test the remote-only refusal for every writer.
- **Wrong merge base for tracer appends**: read the base content from the owning surface. Test two sequential appends.
- **Breaking no-commit accept legs**: leave `write_acceptance_matrix` and `gates_core` untouched, and run `test_accept_no_commit_readonly.py`.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies red→green: the T053 tests are RED on the WP's base and GREEN on the final commit.
- Check that `write_dir` is never called outside a stage thunk in the seam-routed writers, or justify each exception.
- Check that no consumer formats `SurfaceOutcome` by hand, and that the JSON is additive.
- Check the C-008 controls and the no-residue assertions.

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
- 2026-10-02T01:21:28Z – claude – shell_pid=4091464 – Implemented: tracer/issue-matrix writers write in place at write_dir(kind) inside write_artifact's stage= thunk (zero-residue preserved); WriteSeamResult gained surfaces/commit_hashes/reason passthrough; acceptance-verdict's two commit=True legs resolve write_dir(ACCEPTANCE_MATRIX) once before the lock (lost-update fix); tracer-append/acceptance-verdict render via render_commit_outcome/commit_outcome_payload/commit_outcome_exit_code. Removed WP10's test_no_read_side_bypass.py allow-list entry (tracer_writer._local_staging_path). Re-pinned D22 behaviour change in test_tracer_writer_coord_e2e.py. 5 new test files, 13 existing test files updated for the signature/behavior change. Diff coverage 100% (85/85 lines). Pre-existing red (unrelated): mypy no-any-return on issue_matrix_migration.py:254, confirmed on lane base 7afabf4eff. Allowed red confirmed unchanged: COORD_SEED_TRAILER on the two dead-symbol architectural tests.
- 2026-10-02T02:41:29Z – unknown – Cycle 2: addressed reviewer-renata's cycle-1 feedback (review-WP10.md). B1: render_commit_outcome lines + hand-built [red]Error:[/red] lines now markup-safe (markup=False / rich.markup.escape) -- a bracketed surface diagnostic no longer crashes the refusal report. B2: every arm (refused/error/success) of tracer-append and acceptance-verdict now renders every surface and carries the additive surfaces JSON key via shared helpers (_emit_with_surfaces, _emit_outcome_error). B3: added the discriminating post-fix-UNMATERIALIZED-local-head test for acceptance_verdict's _matrix_write_dir (mutation-confirmed: reverting to read_dir raises CoordinationWorktreeUnmaterialized); tightened the remote-only test to that exact exception. B4: scaffold_acceptance_matrix (matrix.py, WP10-owned) now stages at the already-resolved home instead of feature_dir for repo_root-routed calls -- in place for MATERIALIZED, no router copy2 (copy2-spy test added); corrected the cycle-1 mis-attribution to WP15 in both the code comment and the tracer design-decisions log. B5: added PUBLISHED(E2)-D23 coverage for the actual migrated writers (append_tracer_finding/write_issue_matrix), not just the low-level write_artifact entry point. N1: write_issue_matrix gained an optional matrix_dir kwarg so issue_verdict's locked splice reuses its own resolution instead of re-resolving write_dir inside the lock. N2/N3: recorded the acceptance-verdict seed-before-validation side effect in design-decisions; the issue-matrix prefix-empty test now asserts its own 'one seed commit' promise. Also investigated and addressed the coordinator's WP09/lane-o cross-check (SafeCommitPathPolicyError once the coord dir already has content): did not reproduce on lane-h with either write_dir-based or the old candidate_feature_dir_for_mission-based staging -- the router's pre-existing IN_PLACE classification (not WP10's own) is what prevents it; kept the new regression test as a coverage pin and recorded the finding honestly (tooling-friction). 3 new commits (test red-first -> fix -> coverage-closing), red-first verified as a genuinely separate commit this cycle (11289c4c53 red at the right 10/54 assertions, ed2e96ca1e green). Diff coverage 100% (105/105 lines) against mission base 7afabf4eff. make test-fast baseline green (2173 passed, 5 skipped). 478 targeted tests green across the full blast radius + named architectural gates. Same 2 pre-approved COORD_SEED_TRAILER dead-symbol reds, unchanged. One pre-existing mypy red at issue_matrix_migration.py:254, unrelated, confirmed on mission base.
