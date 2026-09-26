---
work_package_id: WP10
title: '#5113 - doctor coordination --fix materializes; every remedy is truthful'
dependencies:
- WP09
requirement_refs:
- FR-014
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T037
- T038
- T039
- T040
- T041
- T042
phase: Phase 2 - Truthful coordination remedy (wave 2)
task_type: implement
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/_coordination_doctor.py
- src/specify_cli/cli/commands/doctor.py
- src/runtime/next/runtime_bridge.py
- src/mission_runtime/write_target_degrade.py
- src/specify_cli/cli/commands/implement_cores.py
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/cli/commands/agent/mission_record_analysis.py
- tests/specify_cli/cli/commands/test_coordination_remedy_5113.py
- tests/specify_cli/cli/commands/test_doctor_coordination.py
- tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py
- tests/runtime/test_bridge_parity.py
- tests/specify_cli/cli/commands/test_implement_placement_routing.py
- tests/specify_cli/cli/commands/agent/test_record_analysis_placement.py
- tests/specify_cli/coordination/test_coord_never_created.py
authoritative_surface: src/specify_cli/cli/commands/_coordination_doctor.py
create_intent:
- tests/specify_cli/cli/commands/test_coordination_remedy_5113.py
agent_profile: python-pedro
role: implementer
agent: claude
model: ''
assignee: ''
shell_pid: ''
history:
- at: '2026-09-26T13:17:07Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
---

# Work Package Prompt: WP10 – #5113: `doctor coordination --fix` materializes; every remedy is truthful

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

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
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

FR-014: wherever the tool tells an operator how to recover an **unmaterialized** coordination worktree, the command it names must, when run, leave the worktree materialized (US6 AS3, SC-006). Today every such message says `spec-kitty doctor workspaces --fix`, which only removes husks and **cannot create** a worktree (#2240; see the comment in `_coordination_doctor.py` next to `COORDINATION_WORKTREE_MISSING`).

Success means:

1. `spec-kitty doctor coordination --mission <slug> --fix` gains a missing-worktree fixer, `_apply_missing_worktree_fix(findings, repo_root)`, for `COORDINATION_WORKTREE_MISSING` (branch exists, worktree absent). It materializes through WP09's `materialize_coord_surface_for_write` (the canonical materializer). It is idempotent and error-code-scoped, and is registered in `_apply_coordination_fixes`.
2. The `COORDINATION_WORKTREE_MISSING` finding carries `extra["mission_slug"]` and `extra["mid8"]`, keeps `recovery_args` (pinned by `test_doctor_coordination.py`), and its `next_step` **leads** with `spec-kitty doctor coordination --mission <slug> --fix`. The raw `git worktree add` is kept as a fallback.
3. The `--fix` help (`doctor.py::coordination_health`) and the `run_coordination_health` docstring describe the new behaviour. The doctor CLI surface golden is updated.
4. Every other emitter of the unmaterialized remedy is **first classified** as *unmaterialized* (branch present, worktree absent), *deleted / never-created*, *remote-only* or *husk/EMPTY*, and then gets truthful text:
   - `runtime/next/runtime_bridge.py` (`_COORD_UNMATERIALIZED_RECOVERY`);
   - `mission_runtime/write_target_degrade.py` (the remote-only `ActionContextError` text);
   - `cli/commands/implement_cores.py`;
   - `cli/commands/implement.py`;
   - `cli/commands/agent/mission_record_analysis.py`.

   The pinned words "materializ" / "unmaterializ" stay where they are pinned, and "flatten" is never offered for an unmaterialized branch. The husk/EMPTY remedy keeps `doctor workspaces` (PD-10).
5. A round-trip test proves the text and the behaviour cannot drift. It parses the command out of `CoordinationWorktreeUnmaterialized.next_step` (the text WP09 wrote), runs it, and asserts the worktree exists.

## Context & Constraints

- **Spec**: US6 AS3, FR-014, SC-006.
- **Plan**: PD-10, which lists the emitters and pins, and says to classify unmaterialized versus husk first.
- **Research Part B**:
  - D3: the remedy decision and rejected alternatives. Do not extend `doctor workspaces --fix`, and do not add a new top-level command.
  - D4 item 5: the round-trip test.
  - ADJ-6: all emitters are folded in.
- **tasks.md**: the WP09/WP10 split and the ownership table.
  - WP10 is the single owner of `_coordination_doctor.py`.
  - The FR-008 one-line lane-dir matcher in `_check_lane_sparse_checkout_drift` is done **later by WP11** as a documented out-of-map edit. **Do not touch** `_check_lane_sparse_checkout_drift`.
  - Do **not** edit `coordination/surface_resolver.py` (WP09).
- **Layer direction**: `runtime` and `mission_runtime` edits are **string-only**. Add no import from `specify_cli` in those packages; the shrink-only outbound ledgers in `tests/architectural/test_layer_rules.py` must not grow (C-003).
- **Complexity**: `_apply_coordination_fixes` is a small dispatcher, `run_coordination_health` must stay ≤ 15, and do not touch `_fix_one_mission_coord_staleness` (CC11) or `resolve_status_surface_with_anchor` (CC12) (D5).

**Implementation command**: `spec-kitty agent action implement WP10 --agent <name>`. It depends on WP09.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves (it bases on WP09's lane).

## Subtasks & Detailed Guidance

### Subtask T037 – Red-first remedy round-trip test, parametrized over every unmaterialized emitter

- **File**: `tests/specify_cli/cli/commands/test_coordination_remedy_5113.py` (new). Markers: `integration`, `git_repo`.
- **Fixture**: a real fresh coordination Mission, via the helpers WP09 used from `tests/integration/test_placement_partition_golden_path.py` (`_init_git_repo`, `_create_mission(..., MissionTopology.COORD)`). Branch present, worktree absent. A **fresh Mission per parametrized case**.
- **Parametrization (the round trip)**: `test_unmaterialized_remedy_round_trip[emitter]` runs over **every emitter classified as *unmaterialized*** by T040/T041. Write the classification first (T040/T041 "classify" steps), then fill the parameter list from it; an emitter classified *deleted/never-created only* or *husk/EMPTY* is **not** a case, and its classification evidence goes in the Activity Log instead. For each case:
  1. Trigger the emitter **through its real entry point** on the fresh Mission (never by calling the private message builder or reading the constant):
     - `surface_resolver` (`CoordinationWorktreeUnmaterialized.next_step`, WP09's text): a coordination-partition read, the way `tests/mission_runtime/test_coord_read_seam.py::test_unmaterialized_coord_read_raises_instead_of_empty_primary` does.
     - doctor missing-worktree finding (T039 text): `spec-kitty doctor coordination --mission <slug>` without `--fix`, via `CliRunner`, reading the finding's `next_step` from `--json` output.
     - `runtime_bridge` (`_resolve_wp_board_action`'s unmaterialized arm): through the public next/board query path that `tests/runtime/test_bridge_parity.py` uses for its unmaterialized pin (≈L1772), reading `blocked_reason`.
     - `write_target_degrade` (`assert_coord_write_materialized`): through the terminus write entry point its existing tests use, on the arm(s) classified in T040.
     - `implement_cores` / `implement` / `mission_record_analysis`: only if T041 classifies them as reachable in the unmaterialized state; then through `spec-kitty agent action implement` / `record-analysis` on the fresh Mission.
  2. Extract the backticked `spec-kitty …` command from the emitted text with one shared regex, and assert it is `spec-kitty doctor coordination --mission <slug> --fix` with the real slug substituted (no `<mission>` placeholder in any case; see T040).
  3. Run it through `typer.testing.CliRunner` against the real CLI app.
  4. Assert the coordination worktree exists (`CoordinationWorkspace.worktree_path(...)`; do not compose it).
  - **`write_target_degrade` remote-only arm**: the remedy is an ordered list of steps, not one command. Build the case with a bare `origin` remote holding the coordination branch and **no** local branch. Extract every step from the text in order (`git fetch`, `git branch <coord> origin/<coord>`, then the doctor command), run them in that order (git steps via `subprocess.run(..., cwd=repo_root, check=True)`, the doctor step via `CliRunner`), and assert the worktree exists.
  - **Red on HEAD before this WP**: every case fails (the named command is `doctor workspaces --fix`, which cannot create a worktree, or the doctor has no fixer). Record the red run.
- **Other tests** in the same file:
  1. `test_doctor_fix_is_idempotent`: run the fix twice. The second run is a no-op and exits 0.
  2. `test_doctor_fix_remote_only_does_not_materialize`: with the branch deleted locally and only present on `refs/remotes/origin/…`, the fixer leaves no worktree and reports a warning finding naming the fetch-and-checkout step. It does not crash.
  3. `test_missing_worktree_finding_leads_with_doctor_command`: `run_coordination_health` without `--fix` returns the `COORDINATION_WORKTREE_MISSING` finding. Its `next_step` starts with the doctor command, and `extra` has `mission_slug`, `mid8` and `recovery_args`.
- **Validation**: red run recorded; the parameter list equals the set of emitters classified *unmaterialized* in the Activity Log.

### Subtask T038 – `_apply_missing_worktree_fix` + finding extras + dispatch

- **File**: `src/specify_cli/cli/commands/_coordination_doctor.py`.
- **Steps**:
  1. In the finding builder for "branch exists, worktree absent", the function that returns `DoctorFinding(..., error_code="COORDINATION_WORKTREE_MISSING", extra={"recovery_args": _recovery_args})`, add `extra["mission_slug"] = mission_slug` and `extra["mid8"] = <the mid8 already in scope>`. Keep `recovery_args` unchanged.
  2. Add:
     ```python
     def _apply_missing_worktree_fix(findings: list[DoctorFinding], repo_root: Path) -> list[DoctorFinding]:
         """#5113 / FR-014: materialize a missing coordination worktree (branch present).

         Error-code-scoped and idempotent. Materializes through the canonical
         coordination-layer helper (never a raw ``git worktree add``), so stale
         registrations and remote-only refusal behave exactly as for a decision write.
         """
     ```
     For each finding with `error_code == "COORDINATION_WORKTREE_MISSING"`, call `materialize_coord_surface_for_write(repo_root, extra["mission_slug"])`. Use a function-local import if the module keeps imports light; otherwise a module import.
     - On `CoordinationWorktreeUnmaterialized` (remote-only or a resolve failure), append a `warning` DoctorFinding carrying the exception's `next_step`.
     - Return the warnings, matching the `_apply_stranded_revert_fix` return contract.
  3. Register it in `_apply_coordination_fixes`. The docstring says fixers are order-independent and idempotent; keep that true. Merge the returned warning lists:
     ```python
     _apply_never_created_fix(findings, repo_root)
     warnings = _apply_missing_worktree_fix(findings, repo_root)
     return warnings + _apply_stranded_revert_fix(findings, repo_root)
     ```
     (Keep whatever return type `_apply_stranded_revert_fix` has.)
  4. Make sure the fix runs only under `--fix`, and only for the missions in scope (`--mission` filter).
- **Tests**: T037 plus unit tests in `tests/specify_cli/cli/commands/test_doctor_coordination.py` for the extras, and for the fixer on a finding without extras (defensive: skip, no crash).

### Subtask T039 – Missing-worktree `next_step`, `--fix` help, docstring

- **Steps**:
  1. Missing-worktree finding `next_step`: `"Run: `spec-kitty doctor coordination --mission {mission_slug} --fix` (or, manually: `git -C {repo_root} worktree add {worktree} {coord_branch}`)"`.
  2. `doctor.py::coordination_health` `--fix` help: "Repair coordination topology: materialize a missing coordination worktree whose branch exists, remove stale `coordination_branch` keys for never-created branches (then `migrate backfill-topology`), and revert stranded coordination state." Keep the existing clauses; add the materialize clause.
  3. `run_coordination_health` docstring: list the new fixer.
  4. Update `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` if it pins the help text. Regenerate the golden by the documented procedure in that test file, if any; otherwise edit it minimally.
- **Validation**: `tests/specify_cli/cli/commands/test_doctor_coordination.py` and `test_coordination_doctor.py` are green. Re-pin the `next_step` assertion only where it pinned the old leading text.

### Subtask T040 – Classify + rewrite remedy text in `runtime` / `mission_runtime`

- **`src/runtime/next/runtime_bridge.py`**:
  - `_COORD_UNMATERIALIZED_RECOVERY = "spec-kitty doctor workspaces --fix"` is used as CT-4's runnable recovery for the coord-read fail-closed floor. Read its call sites and confirm they fire only for the unmaterialized state.
  - **Decision (read at HEAD `8900c2cb`)**: the constant has exactly one use, `_resolve_wp_board_action(*, mission_slug: str, repo_root: Path)` (≈L3075), where `mission_slug` **is** a parameter. So the slug is always in scope: replace the constant with `_coord_unmaterialized_recovery(mission_slug: str) -> str` returning `f"spec-kitty doctor coordination --mission {mission_slug} --fix"`, next to `_inspect_board_recovery_command(mission_slug)` (same shape). No `<mission>` placeholder, and never a fallback to `doctor workspaces --fix`. If a new use appears without a slug in scope, thread the slug to it; a placeholder is only acceptable where no caller can supply the slug, and that must be recorded.
  - **Split the except arm**: today one `except (CoordinationWorktreeUnmaterialized, CoordinationBranchDeleted)` gives both states the "Materialize it" text. Only `CoordinationWorktreeUnmaterialized` is the unmaterialized state. Give `CoordinationBranchDeleted` its own arm that surfaces the exception's own `next_step` (the deleted-branch remedy already in `surface_resolver.py`, which names `doctor coordination --fix` / flatten) instead of "Materialize it". Keep `_resolve_wp_board_action` ≤ its current CC + 1.
  - Pin: `tests/runtime/test_bridge_parity.py` (≈L1772: `"spec-kitty doctor workspaces --fix" in board.blocked_reason`). Re-pin it to the new command, and keep the `"unmaterializ"` assertion.
- **`src/mission_runtime/write_target_degrade.py`**:
  - Classify **both** arms that reach the `ActionContextError(_COORD_WRITE_UNMATERIALIZED_CODE, …)` raise in `assert_coord_write_materialized`: (a) the coordination branch is not a local head (remote-only / fresh clone), and (b) a local head that already carries committed content (the "STALE head" fall-through in the comment just above the raise). Today the message claims (a) for both. If (b) reaches the raise, give it its own truthful text (branch present, worktree absent → `spec-kitty doctor coordination --mission {mission_slug} --fix`) and add it as a separate T037 case.
  - Arm (a) is the **remote-only** refusal. `doctor coordination --fix` alone would refuse, because a remote-only branch is never auto-materialized.
  - Truthful text: "…Materialize the coordination surface first: `git fetch`, create the local branch (`git branch {coord_branch} origin/{coord_branch}`), then run `spec-kitty doctor coordination --mission {mission_slug} --fix`; or check out {coord_branch!r} locally before retrying."
  - Grep its tests (`grep -rn "_COORD_WRITE_UNMATERIALIZED_CODE\|doctor workspaces" tests/mission_runtime tests/runtime`) and update the pins. If a pin lives in a file not owned by this WP, record an out-of-map test edit with a rationale.
- **String-only edits.** No new imports from `specify_cli` into `runtime` or `mission_runtime`.

### Subtask T041 – Classify + rewrite remedy text in the CLI emitters

- **Sites**:
  - `cli/commands/implement_cores.py`: the `PlacementResolutionRequired` message ≈L703.
  - `cli/commands/implement.py`: ≈L1088, same shape.
  - `cli/commands/agent/mission_record_analysis.py`: `_placement_coord_filter` ≈L148.
- **Classification (required first).** These messages fire when `placement_ref is None`: "the stored topology could not be resolved (e.g. a coordination branch declared in meta.json is missing/torn down in git)". That covers the **deleted/never-created** case, where flattening is a legitimate option, and possibly the **unmaterialized** case. Read the call paths and decide:
  - If both states reach this message, name the single truthful command for both, `spec-kitty doctor coordination --mission <slug> --fix`. Its existing never-created fixer removes the stale `coordination_branch` key, and the new fixer materializes a present branch. Keep "or flatten … if the coordination topology was never used" **only** for the deleted/never-created case, and make that conditional explicit in the prose.
  - If only the deleted state reaches it, replace `doctor workspaces --fix` with `doctor coordination --mission <slug> --fix` (the never-created fixer) and keep the flatten clause.

  Record the classification evidence (call path and state) in the Activity Log for each site.
- **Constants**: if the same remedy fragment appears ≥ 3 times in one module, hoist it (S1192). Across modules, do not create a shared constant in a new place (no new module); keep each site's text local.
- **Known duplication, follow-up only**: the `PlacementResolutionRequired` remedy string is duplicated verbatim between `implement_cores.py::_resolve_claim_commit_target` (≈L703) and `implement.py::_commit_planning_artifacts_transaction` (≈L1088). Keep both local and identical in this WP (no new shared module). Add a line to tasks.md-style follow-ups in your Activity Log ("dedupe the PlacementResolutionRequired remedy between implement_cores.py and implement.py") so the orchestrator files it at close-out.
- **Slug scope**: `_resolve_claim_commit_target(placement_ref)` has no `mission_slug` today. If T041 names the doctor command there, thread `mission_slug` as a keyword-only parameter (mirroring `_require_record_analysis_placement(placement_ref, *, mission_slug)`) and update its callers and the pin in `test_implement_placement_routing.py`; do not emit a `<mission>` placeholder.
- **Pins**:
  - `tests/specify_cli/cli/commands/test_implement_placement_routing.py` (≈L68);
  - `tests/specify_cli/cli/commands/agent/test_record_analysis_placement.py` (≈L48).

  Re-pin both to the new command.

### Subtask T042 – Update pinned tests, quality gates, blast radius

- `tests/specify_cli/coordination/test_coord_never_created.py` pins the NEVER_CREATED `next_step` (≈L128). Confirm it is unaffected; if T039 touched shared text, update it.
- Confirm the husk/EMPTY pins are **unchanged** and green: `tests/coordination/test_surface_resolver_coord_empty_warning.py`, `tests/coordination/test_surface_resolver_solo_coord_primary.py`, `tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py`.
- Final grep: `grep -rn "doctor workspaces --fix" src/` should list only husk/EMPTY emitters. Record the remaining list and each one's classification.
- Run the Test Strategy commands and record the exact commands plus counts.

## Test Strategy

- **Red-first**: every `test_unmaterialized_remedy_round_trip` case fails before T038–T041 (the named command runs, but the worktree stays absent); `test_missing_worktree_finding_leads_with_doctor_command` fails before T039.
- **Real git**: real `create_mission_core`, the real doctor CLI via `CliRunner`, and real worktrees.
- **Commands**:

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_coordination_remedy_5113.py tests/specify_cli/cli/commands/test_doctor_coordination.py tests/specify_cli/cli/commands/test_coordination_doctor.py tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py -q
.venv/bin/python -m pytest tests/runtime/test_bridge_parity.py tests/specify_cli/cli/commands/test_implement_placement_routing.py tests/specify_cli/cli/commands/agent/test_record_analysis_placement.py tests/specify_cli/coordination/test_coord_never_created.py -q
.venv/bin/python -m pytest tests/coordination tests/specify_cli/coordination tests/mission_runtime tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py -q
.venv/bin/python -m pytest $(grep -rl "doctor workspaces --fix\|doctor coordination" tests --include=*.py | tr '\n' ' ') -q
.venv/bin/python -m pytest tests/architectural/test_layer_rules.py tests/architectural/test_cli_error_surface_seam.py tests/architectural/test_no_legacy_terminology.py -q
make test-fast
```

- **NFR gates**:

```bash
FILES="src/specify_cli/cli/commands/_coordination_doctor.py src/specify_cli/cli/commands/doctor.py src/runtime/next/runtime_bridge.py src/mission_runtime/write_target_degrade.py src/specify_cli/cli/commands/implement_cores.py src/specify_cli/cli/commands/implement.py src/specify_cli/cli/commands/agent/mission_record_analysis.py"
.venv/bin/ruff check $FILES tests/specify_cli/cli/commands/test_coordination_remedy_5113.py
.venv/bin/ruff check --select C901 $FILES
.venv/bin/ruff format --check $FILES tests/specify_cli/cli/commands/test_coordination_remedy_5113.py
.venv/bin/mypy $FILES
```

## Definition of Done

- [ ] NFR-004: diff coverage on this WP's changed lines ≥ 90% (e.g. `.venv/bin/python -m pytest <targeted tests> --cov=<touched modules> --cov-report=xml` then `diff-cover coverage.xml --compare-branch=<lane base> --fail-under=90`; record the number in the handoff note).

- [ ] `doctor coordination --mission <slug> --fix` materializes a missing coordination worktree. It is idempotent, refuses remote-only, and warns instead of crashing.
- [ ] The round trip from the error text to the command to the worktree is proven by `test_unmaterialized_remedy_round_trip`, parametrized over **every** emitter classified *unmaterialized* (each triggered through its real entry point on a fresh coordination Mission); the remote-only `write_target_degrade` steps are run in order and end with the worktree present.
- [ ] `runtime_bridge` names the command with the real slug (no placeholder), and `CoordinationBranchDeleted` no longer gets the "Materialize it" text.
- [ ] The `implement_cores.py` / `implement.py` remedy duplication is logged as a follow-up (no new shared module).
- [ ] Every unmaterialized-state emitter names a command that works. The husk/EMPTY text is unchanged, and "flatten" is never offered for an unmaterialized branch.
- [ ] No new `runtime` / `mission_runtime` → `specify_cli` imports.
- [ ] `_check_lane_sparse_checkout_drift` is untouched (WP11 owns that line).
- [ ] Gates are clean; `make test-fast` is green.

## Risks & Mitigations

- **Misclassification of an emitter**: the evidence is recorded per site, and the reviewer checks it.
- **Help-text golden churn**: regenerate the golden by its documented procedure.
- **Remote-only guidance** must not promise auto-materialization.

## Review Guidance

- Check the classification evidence for each rewritten emitter.
- The fixer calls WP09's helper, not a raw `git worktree add`.
- `recovery_args` is preserved.
- No edit to `surface_resolver.py` or `_check_lane_sparse_checkout_drift`.
- mypy was run.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T13:17:07Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-09-26T16:56:42Z – claude – shell_pid=8583 – Implemented FR-014: doctor coordination --fix materializes a missing coordination worktree.

Classification evidence (T040/T041):
- surface_resolver.CoordinationWorktreeUnmaterialized (WP09 text): unmaterialized.
- doctor COORDINATION_WORKTREE_MISSING finding: unmaterialized by construction.
- runtime_bridge._resolve_wp_board_action's CoordinationWorktreeUnmaterialized arm: unmaterialized (split from the sibling CoordinationBranchDeleted arm, which now gets its own flatten-guidance next_step).
- write_target_degrade.assert_coord_write_materialized: TWO arms reach the raise -- (a) remote-only (branch not local head, multi-step remedy: git fetch + git branch + --fix) and (b) STALE local head (branch present, worktree absent, single-command --fix remedy). Both fixed and tested.
- implement_cores.py::_resolve_placement_ref (via resolve_action_context, for_write=False) DOES raise/degrade for unmaterialized -- confirmed by directly running it on a fresh unmaterialized coord Mission (test_coordination_remedy_5113.py::implement_claim_commit_target case). _resolve_claim_commit_target now threads mission_slug as keyword-only.
- implement.py's own inline PlacementResolutionRequired duplicate (SC-002, _commit_planning_artifacts_transaction) raises the byte-identical text; kept local per T041 (dedupe logged as a follow-up).
- mission_record_analysis.py::_resolve_record_analysis_placement_ref uses resolve_placement_only(for_write=True), whose WRITE-shaped status-surface leg composes the coord path DIRECTLY for UNMATERIALIZED instead of raising -- confirmed red-first NOT reachable in the unmaterialized state (only deleted/never-created). Remedy text still corrected for that case.

Final grep (T042): `grep -rn "doctor workspaces --fix" src/` lists only husk/EMPTY-classification emitters (workspace/context.py's WORKSPACE_HUSK_RECOVERY_COMMAND, _workspace_husk_doctor.py, status/doctor_husks.py) plus _coordination_doctor.py's _WORKSPACE_RECOVERY_CMD sites, which are a DIFFERENT classification (materialized-but-drifted: dirty/stale/mismatch/foreign-repo worktree), not unmaterialized -- out of this WP's scope, unchanged.

Tests: new tests/specify_cli/cli/commands/test_coordination_remedy_5113.py (9 cases, red-first proven against the doctor-workspaces-fix baseline), plus re-pinned test_doctor_coordination.py, test_doctor_cli_surface_golden.py, tests/runtime/test_bridge_parity.py, test_implement_placement_routing.py, test_implement_writeside.py, test_implement_cores.py, agent/test_record_analysis_placement.py. All targeted suites green; fast-tier baseline (tests/unit tests/status tests/cli tests/specify_cli/runtime -m "fast or unit") shows only the 4 documented pre-existing reds (3x test_charter_json_error_contract, 1x test_agent_commands OSError fallthrough) plus the grep-sweep run additionally hit the 5th documented pre-existing red (test_audit_tail_readers::test_decision_open_corrupt_events_log_json_envelope_names_the_typed_kind) and the pre-existing test_doctor_cli_surface_golden 'decisions' subcommand drift -- both confirmed red on the lane base before this WP's changes. Diff coverage 100% on the 3 files with executable line changes (write_target_degrade.py, _coordination_doctor.py, implement_cores.py; doctor.py/implement.py/mission_record_analysis.py/core/errors.py changes are docstring/help-text/message-text only). ruff/mypy clean on new code (pre-existing format/mypy drift on 3 already-unformatted files and one pre-existing mypy no-any-return at doctor.py:396 left untouched, confirmed red on lane base).
