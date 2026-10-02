---
work_package_id: WP15
title: 'finalize-tasks: write location, coordination dirt, per-surface output, planning-commit refresh'
dependencies:
- WP05
requirement_refs:
- FR-003
- FR-007
- FR-007b
- FR-012
- FR-016
- SC-003
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-artifact-single-home-01M3V4BE
base_commit: c833721eb3c4ac284f1c32443a292e81969d99ae
created_at: '2026-10-01T17:52:28.248866+00:00'
subtasks:
- T004
- T079
- T080
- T081
- T082
- T083
- T084
phase: Phase 5 - Command consumers
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/mission_finalize.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_finalize_extracted_helpers.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/tasks_finalize.py
- tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py
- tests/specify_cli/cli/commands/agent/test_finalize_extracted_helpers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP15 – finalize-tasks: write location, coordination dirt, per-surface output, planning-commit refresh

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

`finalize-tasks` must give the coordination-routed Mission's lifecycle records one home and report every surface honestly. It must also keep `planning_commit_sha` current by default. When this WP is done:

- The finalize lifecycle events (`WPCreated`, `TasksCompleted`, the bootstrap writes) are written through `PlacementSeam.write_dir(STATUS_STATE)`. They land in the same coordination log as `move-task`'s events, never in the repository root checkout (US2.2, FR-003).
- Finalize's pre-commit dirtiness check sees COORD-partition records that are dirty **only** on the coordination surface, and commits them on the coordination branch instead of reporting "no changes" (FR-007b, US3.8, R10).
- Text and JSON output report each surface's outcome through WP05's shared renderer. A skipped or refused surface is never masked, and JSON gains `commit_surfaces` beside `commit_hashes` (FR-007, US3.9, R11).
- With no opt-in flag, `planning_commit_sha` is refreshed whenever the PRIMARY planning artefacts changed since it was recorded. It stays unchanged when nothing changed (FR-012, US5.1/5.2, R17).
- A refused **automatic** refresh warns and continues with the old pin (exit 0). An **explicit** `--refresh-planning-commit` refusal still fails, as today (ruling Q6, US5.3). JSON gains `planning_commit_refresh`.

## Context & Constraints

- **Spec**: FR-003 (finalize bootstrap writer family), FR-007, FR-007b, FR-012, FR-016 (R10, R11, R17), SC-003; US2.2, US3.8, US3.9, US5.1-5.3.
- **Plan**: IC-04 (finalize writer rows), IC-07 (finalize consumer rows), IC-09, IC-13. Shared-file map: `mission_finalize.py` is touched by IC-01/04/07/09/13, so all of those finalize edits live in this one WP.
- **Research**: D10 (finalize sees coordination dirt), D8 (consumer table: `mission_finalize.py:3659` fold `_apply_finalize_commit_router_result` L3585; pin refresh L2874), D16 (refresh trigger plus ruling Q6), grounding correction (L2372 is a read inside `_execution_has_begun`, not a writer).
- **Contracts**: `contracts/commit-outcome.md` (JSON additions for finalize-tasks: `commit_surfaces`, `planning_commit_refresh`; exit-code rule), `contracts/write-location-accessor.md`.
- **Upstream WPs you build on**:
  - WP01 extracted helpers from `finalize_tasks` (L4758) and `_ft_apply_writes` (tasks_finalize.py:250); re-read its activity log for the helper names.
  - WP03/WP04 provide `placement_seam(...).write_dir(kind) -> WriteLocation`.
  - WP05 provides `CommitRouterResult.surfaces`, `render_commit_outcome`, `commit_outcome_payload` and the exit-code helper in `src/specify_cli/coordination/commit_outcome.py`.
  - WP02 provides the fixtures in `tests._factories.coord_mission`.
- **Charter**: read `.kittify/charter/charter.md`; load `spec-kitty charter context --action implement`. ATDD-first (C-011): the failing tests are committed before any fix.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology**: say Mission, never feature. Name the sense of "primary": the **PRIMARY partition** (planning artefacts), the **repository root checkout**, or the **target branch**. Never write bare "primary".
- **C-006**: no heavy suites locally (see Targeted test surface).
- **C-008**: `lanes` and `single_branch` Missions must behave exactly as today.
- **Fixture semantics across lanes (post-tasks squad P-m5):** pre-fix assertions use WP02's `make_prefix_coord_mission`; `make_coord_mission` carries only shape-agnostic invariants (its shape changes when WP06 lands); use `make_coord_mission(..., materialized=True)` when a test needs a deterministic MATERIALIZED coordination surface in every lane.
- **Brownfield scout (binding read)**: before coding, read `## WP15` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- `finalize-tasks` allocates execution worktrees per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP15 --agent claude`, and use the workspace path it resolves; never reconstruct it.
- **Lane-relevant sharing (updated by the post-tasks squad, P-m7)**: the `finalize_tasks` / `_commit_planning_pin_refresh_locked` / `_ft_apply_writes` extraction moved here from WP01 as this WP's tidy-first first commit, so WP01 no longer owns these files. This WP runs in **its own lane**, based on WP05's tip (lane A), which already contains WP01's router and anchor-resolver extractions.

## Subtasks & Detailed Guidance

### Subtask T004 – Extract from `finalize_tasks`, `_commit_planning_pin_refresh_locked` (mission_finalize.py) and `_ft_apply_writes` (tasks_finalize.py)

- **Moved here from WP01 (post-tasks squad P-m7)**: this is this WP's **tidy-first FIRST commit**. It is a behaviour-preserving extraction with its own focused tests and no assertion edits, committed BEFORE the red-first test. Moving it lets this WP take its own lane after WP05 instead of serializing in lane A. Re-measure C901 for the target function(s) first (`ruff check --select C901 <file>`) and record before/after in the activity log.

- **Purpose**: WP15 adds three things to finalize:
  - a default planning-pin refresh, decided in `finalize_tasks` near the `--refresh-planning-commit` option handling (≈L4779-4794);
  - per-surface rendering for the pin-refresh commit (the `commit_for_mission` call inside `_commit_planning_pin_refresh_locked`, ≈L2874);
  - a `write_dir` swap in `_ft_apply_writes` (the `read_dir(STATUS_STATE)` at ≈L444).

  All three functions sit at 14-15 now.
- **Steps**:
  1. `finalize_tasks` (L4758):
     - Extract the option/flag interpretation block, including how `--refresh-planning-commit` / `--allow-orphaned` turn into a refresh decision, into `_resolve_finalize_options(...)` or a similarly named helper. **WP15 adds `planning_changed` there.**
     - Extract the JSON/text result emission into `_emit_finalize_result(...)` if it is inline.
  2. `_commit_planning_pin_refresh_locked` (L2807):
     - **Superseded (round 3; `test_finalize_refresh_pin_authority.py`)**: extract **only the result interpretation**; the single `commit_for_mission(..., kind=MissionArtifactKind.LANE_STATE)` call stays inside `_commit_planning_pin_refresh_locked`. (Former text: extract the commit call into `_commit_pin_refresh_files(...)`.
     - Extract the `lanes.json` byte-compare guard (`raise RuntimeError("lanes.json changed before the conditional commit; ...")`) into a named guard helper.
     - Preserve compare-and-swap semantics exactly. This is the pin refresh's safety check.
  3. `_ft_apply_writes` (tasks_finalize.py:250): extract the status-event emission leg (the block that resolves the status dir with `read_dir(STATUS_STATE)` near L444 and emits) into `_ft_emit_status_events(...)`. Keep the call order. **WP15 swaps the dir resolution inside this helper**, and WP20's gate will scan whichever function holds that call.
- **Files**:
  - `src/specify_cli/cli/commands/agent/mission_finalize.py`
  - `src/specify_cli/cli/commands/agent/tasks_finalize.py`
  - new `tests/specify_cli/cli/commands/agent/test_finalize_extracted_helpers.py`
- **Validation**:
  - Existing finalize tests stay green unchanged: `tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py`, `tests/regressions/test_issue_4890_legacy_finalize_effective_graph.py`, plus the finalize-related files under `tests/specify_cli/cli/commands/agent/` (use `grep -l finalize`).
  - New tests drive each helper directly: the option resolution matrix (flag × allow-orphaned), the pin-refresh guard raising on changed bytes, and the status-emission helper writing to the dir it was given.
- **Edge cases**:
  - `finalize_tasks` is a Typer command. Do not change option names, defaults, or help text; WP15 owns the help-text change.
  - The pin refresh runs under a lock (the `_locked` suffix). Keep every lock acquisition at its original call depth.

### Subtask T079 – Red-first finalize reproductions (ATDD commit)

- **Purpose**: Pin each finalize defect through the pre-existing CLI entry point (`spec-kitty agent mission finalize-tasks`) before any fix (C-005, FR-016).
- **Steps**:
  1. In `tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py`, reuse the file's existing finalize fixture conventions first, then add coordination-routed Missions from `tests._factories.coord_mission`, parametrized over `coord` and `lanes_with_coord`.
  2. **R10** `test_finalize_sees_coord_only_lifecycle_dirt`:
     - make finalize's lifecycle records (status log rows, for example `TasksCompleted`) dirty only in the coordination worktree;
     - run finalize;
     - assert the coordination branch tip carries `TasksCompleted`, and the output is not "no changes".
     - Red at base: the porcelain check runs only on the repository root checkout (`_resolve_finalize_commit_candidates`, L3571-3577 region).
  3. **R11 (finalize half)** `test_finalize_reports_skipped_surface`:
     - build a batch where one surface's group is skipped or refused (for example, hold the status lock so the coordination group is refused with `STATUS_LOCK_HELD`);
     - assert the text output and the JSON `commit_surfaces` name that surface.
     - Red at base: `_merge_group_results` masks it.
  4. **R17** `test_finalize_refreshes_planning_commit_sha_by_default`:
     - finalize once;
     - make execution begin (claim WP01, or whatever `_execution_has_begun` at L2325 keys on);
     - commit a planning change (for example an edit to `plan.md` on the target branch);
     - re-run finalize **without** `--refresh-planning-commit`;
     - assert `lanes.json.planning_commit_sha` equals the new planning commit. Red at base: it is unchanged.
  5. Control `test_finalize_keeps_planning_commit_sha_when_unchanged`: the same flow with no planning change; the sha is unchanged. Green at base, and must stay green.
  6. US5.3 `test_finalize_warns_and_keeps_pin_when_auto_refresh_refused`:
     - make the recorded sha not an ancestor of the tip (a rebase or orphaned history), so the advance-only decision refuses;
     - run finalize without the flag;
     - assert exit 0, the old pin kept, a warning naming both commits and `--refresh-planning-commit`, and JSON `planning_commit_refresh.status == "refused"`.
     - Also assert that an explicit `--refresh-planning-commit` in the same fixture still exits non-zero (control for "explicit still fails").
  7. US2.2 `test_finalize_lifecycle_events_share_the_move_task_log`:
     - on a coordination-routed Mission, run finalize, then `move-task WP01 --to claimed`;
     - assert both event kinds sit in the single coordination log with increasing lamport;
     - assert the repository root checkout has no new status rows.
  8. Run the new tests on your base, confirm they are red for the stated reason (not a fixture error), and commit them alone: `test(finalize): red-first reproductions for coordination dirt, masking and planning pin (WP15)`.
- **Files**: `tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py`.
- **Validation**: record the red outcome for each test in the activity log. The planning-pin control is green.
- **Edge cases**:
  - Finalize may require a valid `tasks.md`/WP set and `lanes.json`; build them via the CLI where possible (`finalize-tasks` itself writes `lanes.json`).
  - ~~US5.3 orphan recipe (amend + force)~~ **Superseded**: US5.3 uses a **non-orphan** refusal (#4827's orphan fail-closed stays green). See Binding corrections.
  - Never `xfail` a reproduction.
- **Fixture premise at the lane base (post-tasks squad R-M4)**: this WP's lane base is WP01–WP05; WP06's create seeding is NOT present. Build the coordination-routed fixture with WP02's `make_coord_mission(..., materialized=True)`, or `make_prefix_coord_mission` for a pre-fix leg. Before invoking the CLI, **assert the precondition** the red depends on: the coordination state is MATERIALIZED, the coordination copy of the record is dirty, and the root copy is clean (or whatever the scenario requires). A red then cannot come from a wrong fixture. Do NOT add a dependency on WP06.

### Subtask T080 – Finalize writers use `write_dir(STATUS_STATE)`

- **Purpose**: Close the finalize-bootstrap writer family of FR-003. Today the lifecycle events go to the PRIMARY `planning_dir`, so the log forks.
- **Steps**:
  1. `_emit_local_canonical_events` (`mission_finalize.py:2266`) writes `WPCreated`/`TasksCompleted` into `planning_dir`.
     - Resolve the write directory with `placement_seam(repo_root, mission_slug, owned=...).write_dir(MissionArtifactKind.STATUS_STATE).path` and emit there.
     - Keep `planning_dir` for the PRIMARY-partition reads the function also does, if any.
  2. `tasks_finalize._ft_apply_writes` (`tasks_finalize.py:250`; the `read_dir(STATUS_STATE)` at L444, possibly now inside a WP01-extracted helper): replace the read resolver with `write_dir(STATUS_STATE).path` for the write leg. Keep reads on `read_dir`, and keep `primary_feature_dir` for PRIMARY reads (L141).
  3. Leave `_execution_has_begun` (L2325) alone. Its L2372 is a read.
  4. Thread `owned` through so owned coordination Missions use the owned workspace variant. WP04 handles this in `write_dir`.
  5. Call `write_dir` **before** any reduce of the log, so the seed (if any) lands first (research D2).
  6. Surface the seed: if `WriteLocation.establishment` is `SEEDED` or `RESTORED_FROM_BRANCH`, print the seed summary in the text output and add it to JSON (additive key, for example `coordination_seed`). The accessor already logs at WARNING.
- **Files**: `src/specify_cli/cli/commands/agent/mission_finalize.py`, `src/specify_cli/cli/commands/agent/tasks_finalize.py`.
- **Validation**:
  - The US2.2 test goes green.
  - On a `lanes`/`single_branch` Mission the events land exactly where they did before (C-008 control; add one if the existing suite lacks it).
  - WP20's gate will scan `mission_finalize.py::_emit_local_canonical_events` and `tasks_finalize.py::_ft_apply_writes` (or the helper that now holds the write), so no read resolver may remain in the write leg.
- **Edge cases**:
  - Remote-only coordination branch: `write_dir` raises `COORDINATION_WORKTREE_UNMATERIALIZED`. Render it as a clean error with the recovery hint, no traceback, and nothing written.
  - Seed fork (`COORD_SEED_FORK_REFUSED`): same rendering.

### Subtask T081 – Pre-commit dirtiness check includes the coordination surface

- **Purpose**: FR-007b. `_resolve_finalize_commit_candidates` (L3542) runs `git status --porcelain` only in the repository root checkout (≈L3569-3577), so coordination-only dirt reads as "no changes".
- **Steps**:
  1. Split the candidates by partition (`kind_for_mission_file`). PRIMARY candidates keep today's root-checkout porcelain.
  2. For the COORD candidates (the status log, the issue and acceptance matrices, and any other COORD kind finalize writes), resolve each owning path via `write_dir(kind).path`. Run `git status --porcelain` in the coordination worktree on those paths.
  3. Follow the precedent of `_refresh_worktree_status_findings` (L2586), which already inspects both surfaces.
  4. `has_relevant_changes = primary_dirty or coord_dirty`. Pass the owning-surface paths to `commit_for_mission`; WP05's router commits coordination-worktree paths in place.
  5. Keep the meta.json attribution logic (`_meta_json_delta_is_finalize_attributable`) exactly as is.
  6. If adding the coordination leg pushes C901 past 15, extract a `_coord_candidate_dirt(...)` helper with focused tests.
- **Files**: `mission_finalize.py`.
- **Validation**:
  - R10 goes green.
  - A Mission with only PRIMARY dirt behaves as before.
  - A Mission with neither dirt reports "no changes" (control).
- **Edge cases**:
  - The coordination worktree is absent at check time. `write_dir` already materialized or refused it in T080, so the order in the flow must be write first, check second.
  - An owned checkout: use the owned path form (`owned.files(...)` at ≈L3654) consistently.

### Subtask T082 – Per-surface finalize output

- **Purpose**: FR-007 and US3.9. Finalize renders every surface through the shared renderer.
- **Steps**:
  1. In `_apply_finalize_commit_router_result` (L3585) and the call site (≈L3659), keep the existing `commit_hashes` (L3599, emitted at L3746). Add `commit_surfaces = commit_outcome_payload(router_result)["surfaces"]` (or the equivalent field of the payload helper) to the outcome dataclass (≈L3528) and to the JSON emit at ≈L3746.
  2. For text output, print the lines from `render_commit_outcome(router_result)`. Do not hand-format.
  3. Planning-pin refresh consumer at ≈L2874-2897 (`_commit_planning_pin_refresh_locked`): render its router result through the same pair, and add its surfaces to the refresh JSON.
  4. Exit code: use the shared exit-code helper. Any `refused`/`error` surface makes finalize exit non-zero; `skipped`/`unchanged` exit 0.
     - Check whether today's finalize already exits non-zero on router `status="error"`, and preserve that.
     - The new non-zero exit for a refused coordination surface is the intended fix.
- **Files**: `mission_finalize.py`.
- **Validation**:
  - R11 (finalize) goes green.
  - JSON stays additive: assert the old keys are still present and typed the same.
  - Run the existing finalize JSON-shape tests.
- **Edge cases**:
  - A PRIMARY-only batch yields one surface entry.
  - A planning-artifact-only Mission yields no coordination entry.

### Subtask T083 – Refresh `planning_commit_sha` by default when planning changed

- **Purpose**: FR-012, US5.1/5.2. The flag's behaviour becomes the default (research D16).
- **Steps**:
  1. ~~`refresh = refresh_planning_commit or planning_changed`~~ **Superseded (operator decision; see Binding corrections):** thread the refreshed `planning_sha` through the no-flag preserve-decision path (`_preserve_or_capture_planning_commit_sha` → `_resolve_preserve_planning_commit_decision`) when the planning artefacts changed and the pin is not orphaned. Never flip `refresh_planning_commit`, which is a refresh-only, zero-mutation mode.
     - Put the computation in a new helper (for example `_planning_changed_since_pin(repo_root, mission_slug, recorded_sha, target_tip) -> bool`) so `finalize_tasks` stays ≤ 15.
  2. `planning_changed` is true when `git diff --name-only <recorded planning_commit_sha> <target tip> -- <the Mission's PRIMARY planning paths, excluding lanes.json>` is non-empty.
     - Classify each path with `kind_for_mission_file`, keeping only PRIMARY-partition kinds.
     - `lanes.json` is excluded so finalize's own pin commit never re-triggers.
  3. When `refresh` is true, run the existing flow unchanged:
     - `_resolve_refresh_planning_commit_decision` (L2521; advance-only unless `--allow-orphaned`);
     - `_preflight_refresh_planning_commit` (L2682);
     - `_commit_planning_pin_refresh` (L2768) → `_commit_planning_pin_refresh_locked` (L2807).
  4. Follow the existing branches carefully: today `refresh_planning_commit` gates several call paths (≈L4515, L4611, L4939-5026). Keep the explicit flag's path byte-identical; the automatic path reuses it with an `auto=True` marker that only changes the refusal handling (T084).
  5. With no recorded sha (first finalize), there is nothing to refresh; keep today's behaviour.
- **Files**: `mission_finalize.py`.
- **Validation**:
  - R17 is green and the unchanged control is green.
  - Existing explicit-flag tests (#4141, #4827 `--allow-orphaned`) still pass unchanged.
- **Edge cases**:
  - Execution not begun: today's re-finalize may already rewrite the pin. Do not double-commit; reuse whatever path already runs.
  - A target tip equal to the recorded sha means no diff, so no refresh.

### Subtask T084 – Refused automatic refresh warns and continues; JSON field; help text

- **Purpose**: Ruling Q6, US5.3. A refused automatic refresh must never block finalize; an explicit one still fails.
- **Steps**:
  1. When the automatic refresh (not the flag) is refused, catch the refusal. Refusal sources:
     - the advance-only decision refuses without `--allow-orphaned`;
     - the preflight reports a dirty-checkout finding;
     - `_refuse_planning_pin_refresh` is raised inside the flow.
  2. On that refusal:
     - keep the old pin;
     - print a warning naming the recorded commit, the candidate (target tip) commit, and the manual route `spec-kitty agent mission finalize-tasks --refresh-planning-commit` (plus `--allow-orphaned` when the reason is non-ancestry);
     - continue finalize and exit 0.
  3. When the flag was passed explicitly, keep today's failure exactly.
  4. Add JSON `planning_commit_refresh: {"status": "refreshed"|"unchanged"|"refused", "recorded": <sha>, "candidate": <sha>, "reason": <code>}`, always present when a pin is recorded.
  5. Update the `--refresh-planning-commit` help text (L4779-4794): finalize now refreshes automatically when planning artefacts changed; the flag forces a refresh, and an explicit refusal fails.
- **Files**: `mission_finalize.py`.
- **Validation**:
  - The US5.3 test (both legs) is green.
  - Grep the help text in a CLI `--help` snapshot test if one exists, and update it.
- **Edge cases**:
  - Do not swallow unrelated exceptions: catch only the refusal types/exits the refresh flow raises, and give each its own reason code.
  - Make sure the warning goes to stderr/console and not into the JSON stream.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **#4827 is kept (operator decision)**: a plain finalize on an **ORPHANED** pin still **fails closed** (`_resolve_preserve_planning_commit_decision`). `tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py::test_plain_finalize_fails_closed_on_orphaned_pin` (L206) stays **green and is not re-pinned**.
  - Q6 "warn and continue" applies **only to non-orphan advance-only refusals of the AUTOMATIC refresh**.
  - US5.3 uses a **non-orphan** refusal fixture: an advance-only refusal that is not an orphan, or a dirty-checkout preflight finding. It must never use the "amend + force the target ref" orphan recipe written earlier in this prompt; that recipe is superseded.
- **Automatic refresh path (operator decision)**: it is **NOT** `refresh = flag or planning_changed`.
  - `refresh_planning_commit=True` is a **refresh-only, zero-mutation** mode (`finalize_tasks` L4939-5026): ownership gates run zero-mutation, `_emit_tasks_started` is skipped, the run returns right after `_commit_planning_pin_refresh`, and `_run_commit_pipeline` never runs.
  - The automatic refresh goes through the **no-flag preserve-decision path**. `_preserve_or_capture_planning_commit_sha` → `_resolve_preserve_planning_commit_decision` resolves the refreshed `planning_sha` when the planning artefacts changed (non-orphan), and that value is threaded through the normal pipeline. The mode flag is never flipped. T083 and T084 follow this design.
- **Gate `tests/architectural/test_finalize_refresh_pin_authority.py` must stay green** (name it in the targeted surface). It AST-pins:
  - `_preserve_or_capture_planning_commit_sha` is called **exactly once, directly in `finalize_tasks`**;
  - `_preflight_refresh_planning_commit` is called once in `finalize_tasks`, inside `if not validate_only:`, lexically before every writer;
  - the `_emit_validate_only_report(planning_sha=)` / `_run_commit_pipeline(planning_sha=)` keywords stay present;
  - `_commit_planning_pin_refresh` holds `lanes_json_lock` and calls `_commit_planning_pin_refresh_locked`, which contains **exactly one** `commit_for_mission(files=plan.files, kind=…LANE_STATE, expected_parent_sha=…)`;
  - `_prepare_primary_pin_refresh_commit` assigns `files = (lanes_path,)` or `owned.files([lanes_path])`;
  - no emit or scaffold calls appear in the refresh path.
  - **T004 design**: from `_commit_planning_pin_refresh_locked`, extract **only the result interpretation**; never move the `commit_for_mission` call. An "options" helper must not absorb the pin-authority or preflight calls.
- **Root-copy leakage**: `_collect_finalize_artifacts` (≈L312) lists the root `status.events.jsonl` / `status.json`. After T080/T081, make sure root copies of COORD records are never staged to the target (R7-style leakage). WP21's SC-001 probe cross-checks this.
- R17 needs execution to have begun; before that, a re-finalize already re-captures.
- Also run, by name: `tests/lanes/test_issue_4827_allocator_orphan_pin.py`, `tests/lanes/test_planning_commit_classify.py`, `tests/specify_cli/cli/commands/agent/test_claim_ancestry_gate.py`, `tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py`.
- **C3**: update the `--refresh-planning-commit` help (now a forcing, refresh-only mode; the default refresh is automatic) and document the `planning_commit_refresh` JSON field. Record the reference-doc delta (`docs/api/finalize-tasks-internals.md`) for WP22.

## Targeted test surface

- Red-first and fix tests: `uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py -q`.
- Finalize neighbours (named files):
  - `uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_finalize_extracted_helpers.py tests/regressions/test_issue_4890_legacy_finalize_effective_graph.py -q`
  - any `tests/specify_cli/cli/commands/agent/test_*finalize*.py` and `tests/agent/test_agent_feature.py`.
- Owning-module directory: `tests/specify_cli/cli/commands/agent/` (fast tier: `-m "fast or unit"` where marked).
- Baseline: `make test-fast`.
- Named architectural gate files only:
  - `tests/architectural/test_status_events_writes_gate.py`
  - `tests/architectural/test_status_state_read_dir_single_authority.py`
  - `tests/architectural/test_no_write_side_rederivation.py` (pre-extension; WP20 extends it)
- Never run the bare `tests/architectural/`, any e2e or integration directory, performance/stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006). `tests/integration/test_accept_matrix_coord_partition.py` and similar integration files belong to CI.
- Record commands and pass/fail counts in the activity log for the PR's *Tests run* section.
- Classify any red you did not cause using CLAUDE.md's baseline-red gotcha (known P0s, CI-env auth, stale install, stale venv) before chasing it.

## Quality gates

- C901 ≤ 15 for every touched function (NFR-004). `finalize_tasks` was 14 before WP01; add the refresh decision and coordination-dirt checks as new helpers.
- `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check <changed files>`, `uv run --frozen mypy --strict <changed files>`. Zero issues and no new suppressions (NFR-005).
- ≥ 90% coverage of new and changed lines, with a focused test per new helper and branch (NFR-003, diff-cover).
- JSON changes are additive only.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5513 #5023

## Definition of Done

- T079 tests were committed first and shown red on the base, with reasons recorded; all are green on the final commit.
- No finalize write leg uses a read resolver for a COORD kind.
- Coordination-only dirt is committed on the coordination branch.
- `commit_surfaces` and `planning_commit_refresh` are in JSON, and text renders through `render_commit_outcome`.
- Default refresh works; a refused automatic refresh warns and continues; an explicit refusal fails.
- C-008 controls are green; quality gates are clean; the activity log has commands and counts.

## Risks & Mitigations

- **Many entangled flags** (`refresh_planning_commit`, `allow_orphaned`, `validate_only`): add a decision-table test for the refresh trigger and keep the explicit path untouched.
- **Exit-code change** (a refused coordination surface now exits non-zero): this is intended (FR-007). Call it out in the activity log so WP21's e2e expectations match.
- **Write before check ordering**: the seed must run before the porcelain check, or a pre-fix Mission reports "no changes". Covered by R10 on the pre-fix builder.
- **Tidy-first first**: your own T004 extraction is the first commit; build every later change on those helpers and do not re-inline them.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies red→green. The T079 tests are RED on the WP's base (before this WP's fix commits) and GREEN on the final commit. Check that the ATDD commit precedes the fix commits.
- Confirm `_emit_local_canonical_events` and the `_ft_apply_writes` write leg use `write_dir`, and that L2372 was left alone.
- Confirm the explicit `--refresh-planning-commit` path is byte-identical in behaviour (existing #4141/#4827 tests unchanged), and the automatic path only differs in refusal handling.
- Confirm no hand-formatted surface output, and the JSON is additive.

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
- 2026-10-01T21:49:51Z – claude – Cycle 2 (review-WP15.md, B1-B10): fixed all 10 blocking regressions against lane base e7b085d26c. Red-first verified via scratch 'git worktree add --detach' at cycle-1 HEAD a17b88e269 for B1, B2, B3 (remote-only + coord-seed-fork variants), and B6 (stale root acceptance-matrix). B1/B2: tasks_finalize.py no longer conflates write_dir's establishment side effect with the bootstrap read dir; write_dir is skipped entirely under --validate-only (never mutates coordination). B3: write_dir calls moved outside best-effort try/except in mission_finalize.py so named refusals (CoordinationBranchDeleted, CoordSeedForkRefused) now propagate with a non-zero exit instead of being swallowed -- this is the new non-zero exit for a refused coordination surface that WP21 needs. B4: new unit test isolates coord-only dirt detection from bootstrap's incidental root status.json write. B5: reverted formatting-only drift in the two ruff-format-excluded test files. B6: acceptance-matrix write leg now resolves via placement_seam(...).write_dir(...), stale root candidate dropped from candidate collection, new regression test proves a stale root copy never overwrites the owning coordination copy. B7: PlanningCommitResolution gained pin_class/refusal_reason, populated on every branch. B8/B9: corrected the kept_with_warning message and --refresh-planning-commit help text. B10: _commit_planning_pin_refresh_locked now renders shared commit-outcome surfaces on every outcome arm and decides refusal via commit_outcome_exit_code, extracted into _finalize_pin_refresh_commit_outcome to hold C901 <=15. Non-blocking folds: owned-checkout commit-candidate guard against LIFECYCLE_OWNED_TOPOLOGIES widening; bookkeeping-guard subject-match limitation recorded in traces/design-decisions.md. Commands run: PWHEADLESS=1 pytest tests/specify_cli/cli/commands/agent/ -n 3 --dist loadfile -> 2384 passed, 5 skipped, 2 xfailed; combined with named integration + architectural gates -> 2671 passed total; ruff check/format clean; mypy --strict zero new errors (4 pre-existing unchanged vs e7b085d26c). Commit f26a913ca9. Out-of-map files touched (rationale in commit message): test_issue_4141_refresh_planning_commit.py, test_mission_finalize_phases.py, test_tasks_finalize_seam.py, tests/integration/test_coord_loop_tasks.py, traces/design-decisions.md.
- 2026-10-01T22:45:32Z – claude – Cycle 3 (review-WP15-c2.md, LAST cycle before arbitration): fixed all 3 remaining blocking items + 2 cheap folds. Red-first via 2 SEPARATE commits this time: 3e38485957 (tests, confirmed red against 21ae853333 by temporarily checking out that commit's mission_finalize.py -- 3 failed/36 passed), then 0f71489459 (fix, green -- 39/39). C2-1: _resolve_preserve_planning_commit_decision now returns kept_with_warning (reason=indeterminate_tip_uncapturable) for PinClass.INDETERMINATE instead of silent preserved, per orchestrator ruling on contracts/commit-outcome.md; removed the deliberate-deviation docstring; _report_planning_sha_decision prints a distinct INDETERMINATE message (handles both recorded and tip possibly None). C2-2: needed no source change (commit_outcome_exit_code-based decision was already correct from cycle 2); added the missing mutation-sensitive test proving a legacy status=committed with a refused surface still refuses. C2-3: rewrote --refresh-planning-commit help text to stop recommending a doomed remedy for FOREIGN/INDETERMINATE pins; points at manual lanes.json correction instead. Folds: owned-checkout commit-candidate guard in _commit_finalize_artifacts is now a real raise (OwnedCheckoutCandidateOutsidePlanningError) instead of a bare assert (stripped under -O); added 2 direct unit tests (test_emit_local_canonical_events_propagates_a_write_dir_refusal, test_emit_tasks_started_propagates_a_write_dir_refusal) that isolate each B3 write_dir-outside-try fix independently of the other (verified each fails ONLY when its own site is mutated). Verification: tests/specify_cli/cli/commands/agent/ 2391 passed/5 skipped/2 xfailed (-n3); 7 named integration files 89 passed; widened architectural gates all green except the 5 reds review-WP15-c2.md already attributed to lane-a (no_dead_symbols, dead_symbol_allowlist_contract, status_events_writes_gate, mission_resolver_walker_gate, destructive_op_routing -- 1 failure each, none new); ruff check/format clean; mypy --strict 3 pre-existing errors (same set as review's own base evidence); C901 all <=15; diff-cover vs 21ae853333 100% (11/11 lines). No kitty-specs edits made on the lane branch this cycle.
