---
work_package_id: WP16
title: Task command conversion
dependencies:
- WP07
- WP08
- WP09
requirement_refs:
- FR-003
- FR-022
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T084
- T085
- T086
- T087
- T088
- T089
phase: Phase 4 - Conversion sweep
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_mark_status.py
- src/specify_cli/cli/commands/agent/tasks_shared.py
- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
- src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py
- src/specify_cli/cli/commands/spec_commit_cmd.py
- src/specify_cli/cli/commands/agent/mission_check_prerequisites.py
- tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py
- tests/integration/test_owned_checkout_mark_status.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP16 – Task command conversion

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`. The charter (`.kittify/charter/charter.md`) is binding.

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

This is IC-10b's task-command half: `move-task`, `mark-status`, the shared task helpers, `spec-commit` and `check-prerequisites` stop validating ownership themselves and stop carrying bare owned roots. It is **behaviour-preserving**: the proof is that the existing owned-command tests pass unchanged (FR-022), plus `mypy --strict`, plus one new exactly-once validation assertion per command (FR-003 / NFR-002).

Done means:

1. The seven owned source files contain **zero** occurrences of the identifier `effective_root`, zero `"effective_root"` string keys, zero `OwnedMission` references, zero direct `resolve_owned_mission` calls, and zero legacy attribute reads on the fact (`.root`, `.primary`, `.directory`, `.slug`, `.target`).
2. No dataclass field or function parameter in these files carries the owned checkout as a path: `_MoveTaskState.owned_checkout` (`tasks_move_task.py:248`), `_MoveTaskArgs.owned_checkout` (`:3380`), `_MarkStatusState.owned_checkout` (`tasks_mark_status.py:114`), `_do_mark_status(owned_checkout=)` (`:554`), `_resolve_commit_inputs(owned_checkout=)` (`spec_commit_cmd.py:105`) are gone (gate G5; these are the G5 floor examples in `contracts/architectural-gate.md`).
3. `spec-commit` and `check-prerequisites` declare `--owned-checkout` through WP08's `OwnedCheckoutOption` (their inline declarations at `spec_commit_cmd.py:166` and `mission_check_prerequisites.py:563` are two of the eight the CLI contract moves).
4. Each of `move-task`, `mark-status`, `spec-commit`, `check-prerequisites` validates ownership **exactly once** per invocation, asserted by a counting test (T089).
5. Every existing owned test for these commands passes; the only edits to the two owned test files are the internal-shape re-point listed in T088 (if still needed) plus the new T089 tests.
6. ruff check, ruff format, `mypy --strict` clean on touched files; `make test-fast` green; no function above complexity 15.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP16 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **0** markers.
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

- **Mission docs**: `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/` → `spec.md` (FR-003, FR-021, FR-022, NFR-002), `plan.md` (Staging Strategy; IC-08 option list; IC-10b; the "renamed-carrier state fields" note naming `tasks_mark_status.py:114` and `tasks_move_task.py:248`), `contracts/cli-owned-checkout-surface.md` (row: `move-task`, `mark-status`, `spec-commit`, `check-prerequisites` — existing flag, single_branch, "unchanged behaviour (FR-022), rewired onto the shared helper"), `contracts/architectural-gate.md` (G2, G4, G5), `data-model.md`, `occurrence_map.yaml`.
- **Landed prerequisites** (read their code before you start; do not trust shapes quoted here):
  - WP01 `mission_runtime.OwnedCheckout` (public import only) with canonical fields `repository_root`, `owned_root`, `mission_dir`, `mission_slug`, `topology`, `target_branch`; transitional legacy properties are deleted in WP18, so never read them.
  - WP02 `owned_mission.require_unstaged_index(fact)`; `LIFECYCLE_OWNED_TOPOLOGIES`.
  - WP07 `TransitionRequest.owned` (dual keyword until WP18: use `owned=` only), `status_transition.emit_inner_state_changed_transactional(..., owned=)`, `status_transition.read_events_transactional(..., owned=)`, `agent_tasks_ports.MissionHandle.owned`, `write_seam`/`commit_router` conversions (the latter is what `spec-commit`'s `commit_for_mission` reaches).
  - WP08 `src/specify_cli/cli/commands/_owned_checkout.py`: `OwnedCheckoutOption`, `resolve_owned_or_adopt(...)`, `emit_owned_refusal(...)`. Read `tests/specify_cli/cli/commands/test_owned_checkout_helper.py` for its contract.
- **Where validation happens (G2 + G5).** Gate G2 allows `resolve_owned_mission` / `adopt_owned_checkout` calls only from `_owned_checkout.py` and `owned_mission.py`; gate G5 forbids a parameter or field that carries the owned checkout as a `Path` under any of the names `owned_root`, `owned_checkout`, `checkout_root`, `effective_root`. The raw `--owned-checkout` value may therefore exist only as the Typer parameter (typed `OwnedCheckoutOption`) and must go straight into `resolve_owned_or_adopt`. **Renaming a field to dodge the scanner (for example `owned_checkout_arg: Path | None`) is a gate evasion and will be rejected in review.**
- **Typer edges you do not own.** `move-task` and `mark-status` are declared in `src/specify_cli/cli/commands/agent/tasks.py` (`:782` / `:851` and `:916` / `:954`), which is **WP09-owned**; WP09 is a dependency of this WP, so it is merged on your lane base. Their wrappers pass `owned_checkout=owned_checkout` into `_do_move_task(_MoveTaskArgs(...))` and `_do_mark_status(...)`. To delete the Path-typed carriers you **change those two call expressions** to pass the fact (unconditional; WP09 is a dependency, so it is merged on your lane base):
  - make the edit in `tasks.py` as an **out-of-map edit** of the two wrapper call expressions (resolve with `resolve_owned_or_adopt`, pass `owned=`), with the rationale "WP16/G5: the task-command internals take the validated fact; the Typer edge is the only place the raw option may live" in the commit message and Activity Log;
  - (WP09 is a dependency, so the not-merged case cannot arise; if `git log` shows otherwise, stop and ask the orchestrator.)
- **Top-down / callee rule.** For every call out of these files: callee takes `owned` → `owned=owned`; callee is one of the six shared dual-keyword seams (`placement_seam`, `mission_context_for`, `resolve_action_context`, `resolve_workspace_for_wp`, `locate_work_package`, `TransitionRequest`) or any other function whose legacy keyword is marked TRANSITIONAL(WP18) → `owned=owned`; callee still takes only `effective_root` → bridging keyword `effective_root=owned.owned_root if owned else None` (plain keyword, never a dict splat), marked `# bridging: WP<n> converts` naming the callee's owner, and log the site. Known cross-WP callees: `review.cycle.create_rejected_review_cycle` (WP17, called at `tasks_verdict_persistence.py:901, 936`), `tasks_finalize_validation._read_transactional_wp_lane` (WP13, called at `tasks_move_task.py:568`).
- **Behaviour preservation.** Error codes (`OWNED_OPTION_UNSUPPORTED`, `OWNED_INPUT_INVALID`, the `OWNED_*` set) are `logs_telemetry: do_not_change`; JSON envelope keys are `serialized_keys: do_not_change`; no flag is renamed or removed (`cli_commands: manual_review`). Flagless runs from the repository root checkout must behave exactly as today (`test_flagless_mark_status_preserves_primary_lookup`, `test_no_opt_in_keeps_primary_resolution`). Flagless adoption from inside an owned checkout (FR-021) comes from the WP08 helper; it is WP08's contract, not a behaviour you add here.
- **Terminology (C-008)**: new prose says "owned checkout" / "repository root checkout"; never "feature". `st.main_repo_root` and `st.repo_root` are existing state names; do not rename them in this WP (out of scope, high churn).
- **Complexity.** Functions at 12+ on the planning base that you will touch: `_mt_resolve_targets` 13, `_do_move_task` 14, `spec_commit_command` 15, `check_prerequisites` 14. Do not let any cross 15; extract small helpers first if a conversion adds a branch (campsite, Standing Order 2).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes must merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Execution lane**: assigned in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json` by `spec-kitty agent mission finalize-tasks`. Start with `spec-kitty implement WP16` and use only the workspace path it prints.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Occurrence census (planning base `df1588860`)

Run at the start and at the end (the end state is empty, apart from logged bridges):

```bash
F="src/specify_cli/cli/commands/agent/tasks_move_task.py src/specify_cli/cli/commands/agent/tasks_mark_status.py \
   src/specify_cli/cli/commands/agent/tasks_shared.py src/specify_cli/cli/commands/agent/tasks_parsing_validation.py \
   src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py src/specify_cli/cli/commands/spec_commit_cmd.py \
   src/specify_cli/cli/commands/agent/mission_check_prerequisites.py"
grep -nw "effective_root\|OwnedMission\|resolve_owned_mission\|owned_checkout" $F
grep -nE "owned\.(root|primary|directory|slug|target)\b" $F
```

Planning-base counts: `tasks_move_task.py` 58 sites, `tasks_mark_status.py` 26, `tasks_verdict_persistence.py` 10, `spec_commit_cmd.py` 9, `mission_check_prerequisites.py` 5, `tasks_shared.py` 5 (+1 read), `tasks_parsing_validation.py` 2 (+1 read). Per-site tables are in the subtasks.

## Subtasks & Detailed Guidance

### Subtask T084 – Convert `tasks_move_task.py`

- **Purpose**: `move-task` is the owned lifecycle's workhorse (claimed → in_progress → for_review in the SC-001 walkthrough). It validates ownership itself today (`:463`) and threads the owned root through 22 hand-built `{"effective_root": st.owned.root}` splats and keywords.
- **Steps**:
  1. Imports (`:124-127`): drop `OwnedMission` and `resolve_owned_mission`; import `OwnedCheckout` from `mission_runtime`.
  2. State (`:240-250`): delete `_MoveTaskState.owned_checkout: Path | None`; retype `owned: OwnedCheckout | None = None`. Args (`:3375-3380`): replace `_MoveTaskArgs.owned_checkout: Path | None` with `owned: OwnedCheckout | None = None`, and copy it into the state in `_do_move_task` (see the Typer-edge rule in Context for how `tasks.py` supplies it).
  3. Resolution (`_mt_resolve_targets`, `:455-490`): delete the `if st.owned_checkout is not None:` block that calls `resolve_owned_mission(get_main_repo_root(repo_root), st.owned_checkout, st.mission)`. Keep `_mt_preflight_owned_request(st)` and run it when `st.owned is not None`. Replace `repo_root = st.owned.root` → `st.owned.owned_root`; `st.owned.slug` → `mission_slug`; `st.owned.primary, st.owned.target` → `repository_root, target_branch` (`:465, 483, 484`). Extract the owned branch into a helper (e.g. `_mt_apply_owned_targets(st)`) so `_mt_resolve_targets` (13) does not grow.
  4. Convert every forward (planning-base lines; each `**({"effective_root": st.owned.root} if st.owned else {})` splat and each `effective_root=st.owned.root if st.owned else None` keyword becomes `owned=st.owned`):

     | Line | Site | Callee |
     |---|---|---|
     | 498-501 | splat | `placement_seam` (dual kw) |
     | 550-553 | keyword | `MissionHandle` (WP07) |
     | 561-565 | splat | `_tasks.locate_work_package` (dual kw) |
     | 568-573 | splat | `_read_transactional_wp_lane` (WP13, callee rule) |
     | 964-969 | splat | `_tasks._check_unchecked_subtasks` (T085) |
     | 984-990 | dict key `"effective_root"` in `validation_options` | `_validate_ready_for_review` (T085/T086) |
     | 1022-1030 | dict key `"effective_root"` in `validation_options` | same |
     | 1113-1116 | keyword | `placement_seam` |
     | 1808-1814 | splat | `placement_seam` |
     | 2458-2462 | splat | `_tasks.read_events_transactional` (WP07) |
     | 2524-2528 | splat | `_tasks.read_events_transactional` |
     | 2809-2828 | `effective_root=` **and** `owned_mission=st.owned` | `TransitionRequest` → one `owned=st.owned` |
     | 2888-2891 | keyword | `MissionHandle` (rollback summary) |
     | 2925-2928 | keyword | `MissionHandle` (rollback subtasks reset) |
     | 3121-3130 | `effective_root=owned.root` + `owned_mission=` | `emit_inner_state_changed_transactional` → `owned=owned` |

     In the two `validation_options` dicts replace the `"effective_root"` key with `"owned": st.owned` only if the callee's parameter is named `owned` after T085/T086 (it will be).
  5. Remaining legacy attribute reads that are **values**, not forwards: `_mt_resolve_owned_review_base` `:726, 738, 762`; `_mt_owned_workspace` `:782-783`; `_mt_require_owned_implementation` `:853`; `_mt_resolve_pre_review_workspace` `:1403`; `_mt_emit_transitions` `:2825`; `_mt_execute` `:3204`. Each `.root` becomes `.owned_root`. `_mt_resolve_gate_baseline` (`:1818`) only tests `st.owned is not None` and reads `st.feature_dir`; it needs no change (its test drives it with a `SimpleNamespace(owned=SimpleNamespace(root=...))` that stays valid).
  6. Commit per logical block (state + resolution; forwards; value reads) so review can follow.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_move_task.py`; the two wrapper call expressions in `src/specify_cli/cli/commands/agent/tasks.py` (declared out-of-map; see Context).
- **Parallel?**: T085/T086 change callee signatures this file calls; land T085/T086 before or together with the forward edits at `:964-1030`.
- **Validation checklist**:
  - [ ] Census for this file prints nothing (or only logged bridges).
  - [ ] `_mt_resolve_targets` and `_do_move_task` still ≤ 15 (`uv run --frozen ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=15' <file>`).
  - [ ] `tests/specify_cli/cli/commands/agent/test_tasks_move_task_degod.py`, `test_tasks_move_task_seam.py`, `test_move_task_durability.py`, `tests/cli/test_move_task_planned_guard.py` pass unchanged.
- **Edge cases**: several `MissionHandle(...)` constructions are in rollback paths that only run after a failed hop — they are exercised by `test_owned_checkout_move_task.py`'s compensation tests (`:733, 794`); run them. `st.owned` is `None` for every non-owned run: every `owned=st.owned` forward must be equivalent to the old omitted keyword.

### Subtask T085 – Convert `tasks_mark_status.py` / `tasks_shared.py`

- **Purpose**: `mark-status` is the second owned write command; `tasks_shared.py` holds the subtask and review-readiness readers that `move-task` calls. Together they carry two G5 floor fields and five forwards.
- **Steps**:
  1. `tasks_mark_status.py` imports (`:87-90`): drop `OwnedMission` and `resolve_owned_mission`; import `OwnedCheckout` from `mission_runtime`.
  2. State (`:110-126`): delete `_MarkStatusState.owned_checkout: Path | None` (`:114`, a G5 floor example); retype `owned: OwnedCheckout | None = None` (`:124`).
  3. Entry: `_do_mark_status(..., owned_checkout: Path | None)` (`:554`) takes `owned: OwnedCheckout | None = None` instead; the Typer edge in `tasks.py:954` supplies it (Typer-edge rule in Context).
  4. `_ms_resolve_context` (`:170-208`):
     - delete the `resolve_owned_mission(primary, st.owned_checkout, st.mission)` call (`:180`);
     - keep `require_unstaged_index(st.owned)` and the `OWNED_OPTION_UNSUPPORTED` auto-commit refusal, in the same order;
     - renames: `:188` `.root` → `.owned_root`; `:202` `.primary` → `.repository_root`; `:203` `.target` → `.target_branch`; `:204` `.slug` → `.mission_slug`.
  5. Forwards:
     - `_ms_resolve_read_dir` `:232-235`: `MissionHandle(effective_root=st.owned.root if st.owned is not None else None)` → `owned=st.owned`;
     - `_ms_emit_subtask_state` `:415-426`: `effective_root=st.owned.root` plus `owned_mission=st.owned` → one `owned=st.owned` (WP07's `emit_inner_state_changed_transactional`).
  6. Value reads: `_ms_output` `:448, 456, 457`; `_reconstruct_applied_events(owned: OwnedMission)` (`:498`) retypes to `OwnedCheckout` and `:514, 517, 525` `.root` → `.owned_root`; `_do_mark_status` `:591` `.directory` → `.mission_dir`, `:610` `.root` → `.owned_root`, `:629` `.target` → `.target_branch`.
  7. `tasks_shared.py`:
     - `_check_unchecked_subtasks(..., effective_root)` (`:507`) → `owned: OwnedCheckout | None = None`;
     - forwards at `:549` and `:565` (`placement_seam(..., effective_root=effective_root)`) → `owned=owned`;
     - `:564` `if effective_root is not None:` → `if owned is not None:`;
     - `_validate_ready_for_review(..., effective_root)` (`:582`) → `owned`; forward at `:601-607` into `_seam_validate_ready_for_review(effective_root=...)` (the `tasks_parsing_validation` function imported as an alias at `:47`) → `owned=owned`. Convert it in the same commit as T086 step 1.
  8. Commit: `refactor(tasks): mark-status and shared readers take the OwnedCheckout fact (WP16/T085)`.
- **Files**:
  - `src/specify_cli/cli/commands/agent/tasks_mark_status.py`
  - `src/specify_cli/cli/commands/agent/tasks_shared.py`
- **Parallel?**: `[P]` with T086, except the `_validate_ready_for_review` pair, which must change together.
- **Validation checklist**:
  - [ ] `tests/specify_cli/cli/commands/agent/test_tasks_mark_status_seam.py`, `test_tasks_mark_status_recovery.py`, `test_mark_status_authored_roster.py`, `test_claim_event_source.py`, `test_issue_2684_subtask_completion_event_sourced.py` pass unchanged.
  - [ ] `test_tasks_shared_seam.py`, `test_check_unchecked_subtasks_snapshot_source.py`, `test_tasks_surface_authority.py`, `test_tasks_compat_surface.py`, `tests/agent/test_mission_handle_json_errors.py` pass unchanged.
  - [ ] `_check_unchecked_subtasks` has other callers (`tasks.py`, `core/subtask_rows.py`; `status/emit.py` mentions it in a docstring): `grep -rn "_check_unchecked_subtasks(" src` confirms none passes the removed keyword.
- **Edge cases**:
  - `_reconstruct_applied_events` runs in the post-commit recovery path (`test_post_commit_recovery_reports_only_exact_commit_events`, `test_concurrent_event_is_not_claimed_in_failure_envelope`); it reconstructs events from P's log and must keep reading only P.
  - Two test files you do **not** own construct the value object directly and call these internals:
    - `tests/specify_cli/cli/commands/agent/test_tasks_mark_status_recovery.py:38-50` (an `OwnedMission(...)` fixture passed to `_reconstruct_applied_events`);
    - `tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_identity_read.py:182` (`st.owned = OwnedMission(root, owned_root, primary, ...)`).
    WP02's transitional `OwnedMission` legacy factory function mints a real `OwnedCheckout`, so those objects expose `owned_root` / `mission_dir` / `target_branch` after your rename. Run both files; they must stay green unedited. If one goes red, report it (do not edit those files); WP18/T097 re-points them when the factory is deleted.
  - `mark-status` requires auto-commit for owned runs; the refusal must still fire before any write, after validation.

### Subtask T086 – Convert `tasks_parsing_validation.py` / `tasks_verdict_persistence.py`

- **Purpose**: the review-readiness reader and the verdict persistence path (review-cycle creation and verdict revert) still thread the owned root. The verdict path runs on every owned review rejection, so a missed site here writes a review cycle into the repository root checkout.
- **Steps**:
  1. `tasks_parsing_validation.py`:
     - `_validate_ready_for_review(..., *, effective_root: Path | None = None, workspace_override=..., review_base_ref=..., check_kitty_specs=..., ...)` (`:777-795`): the parameter at `:784` becomes `owned: OwnedCheckout | None = None`, in the same keyword-only position;
     - `:838` `placement_seam(main_repo_root, mission_slug, effective_root=effective_root).read_dir(MissionArtifactKind.RESEARCH)` → `owned=owned`;
     - import `OwnedCheckout` following the module's existing typing-import style.
  2. `tasks_verdict_persistence.py` has no owned parameters; it reads `st.owned` from the move-task state. Convert:

     | Line | Function | Site |
     |---|---|---|
     | 308 | `_resolve_revert_commit_worktree` | `st.owned.root` → `.owned_root` |
     | 349 | `revert_committed_verdict_write` | `.root` → `.owned_root` |
     | 436-448 | `_revert_committed_verdict_write_held` | `placement_seam(effective_root=st.owned.root if st.owned else None)` → `owned=st.owned`; value read `:448` |
     | 546 | `_persist_review_cycle_with_queue` | `.root` → `.owned_root` |
     | 901-911 | `_create` (initial) | `create_rejected_review_cycle(effective_root=st.owned.root if st.owned else None)` → callee rule; value read `:911` |
     | 936-948 | `_create` (retry) | same call; value read `:948` |

  3. `create_rejected_review_cycle` belongs to WP17 (`review/cycle.py:1125`). If it already takes `owned`, pass `owned=st.owned`; otherwise keep the bridging keyword `effective_root=st.owned.owned_root if st.owned else None` and log both lines for WP18/T097.
  4. The two `validation_options` dicts in `tasks_move_task.py` (T084) feed `_validate_ready_for_review` by keyword; after step 1 their key must be `"owned"`. Change both files in the same commit.
  5. Commit: `refactor(tasks): review readiness and verdict persistence take the OwnedCheckout fact (WP16/T086)`.
- **Files**:
  - `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`
  - `src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py`
- **Parallel?**: `[P]` with T085, except the shared `_validate_ready_for_review` pair.
- **Validation checklist**:
  - [ ] `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py`, `tests/agent/cli/commands/test_tasks_helpers.py`, `tests/specify_cli/cli/commands/agent/test_tasks.py` pass unchanged.
  - [ ] `tests/review/test_verdict_seam_reader_collapse.py`, `tests/review/test_verdict_status_lock_bound.py`, `tests/integration/review/test_verdict_save_topologies.py`, `tests/integration/test_review_durability_matrix.py` pass unchanged.
  - [ ] `tests/specify_cli/review/test_cycle_kind_flip.py`, `tests/coordination/test_verdict_dir_co_resolution.py`, `tests/agent/test_status_state_phantom_degrade.py`, `tests/post_merge/test_review_artifact_consistency.py` pass unchanged.
  - [ ] `grep -nw "effective_root" src/specify_cli/cli/commands/agent/tasks_parsing_validation.py src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py` prints only logged bridges.
- **Edge cases**:
  - `_create` is called twice on the rejection path (initial and retry); both must pass the same `owned`.
  - The verdict revert must keep committing in P only (`test_owned_checkout_move_task.py` compensation tests at `:733` and `:794`).
  - `_validate_ready_for_review` receives `workspace_override` and `review_base_ref` only for owned runs; keep those keyword names unchanged (they are not owned roots).

### Subtask T087 – Convert `spec_commit_cmd.py` / `mission_check_prerequisites.py`; option migration

- **Purpose**: these two commands own their Typer edges, so they complete the whole pattern here: `OwnedCheckoutOption` → `resolve_owned_or_adopt` → the fact, with no local validator call. They are two of the eight inline declarations IC-08 moves onto the shared option (`spec_commit_cmd.py:166`, `mission_check_prerequisites.py:563`).
- **Steps**:
  1. `spec_commit_cmd.py` imports (`:33`): drop `OwnedMission` and `resolve_owned_mission`; import `OwnedCheckout` from `mission_runtime`, and `OwnedCheckoutOption` / `resolve_owned_or_adopt` from `specify_cli.cli.commands._owned_checkout`. Keep `require_unstaged_index`.
  2. Option (`:166`): the inline `owned_checkout: Annotated[Path | None, typer.Option("--owned-checkout", help="Explicit single-branch checkout root.")]` becomes `owned_checkout: OwnedCheckoutOption = None`.
  3. `_resolve_commit_inputs(repo_root, files, mission, owned_checkout: Path | None, target_branch)` (`:103-116`) must stop taking the raw path:
     - resolve the fact in `spec_commit_command` via `resolve_owned_or_adopt(..., target_override=target_branch)` (confirm WP08 forwards `target_override`; `spec-commit` is the only command that uses it today);
     - pass `owned: OwnedCheckout | None` into `_resolve_commit_inputs`;
     - keep `owned.files(files)` (the canonical `OwnedCheckout.files`, whose `OwnedCheckoutPathRefused` maps to `OWNED_MISSION_PATH_REFUSED` at the CLI edge) and then `require_unstaged_index(owned)`, in that order, so the whole batch is validated before any staging (`test_whole_commit_batch_is_validated_before_staging`).
  4. Renames: `:113` `owned.slug` → `owned.mission_slug`; `:195` `commit_for_mission(..., effective_root=owned.root if owned else None)` → `owned=owned` (WP07's commit router; callee rule); `:207` `owned.root` → `owned.owned_root`.
  5. `spec_commit_command` is at complexity 15: extract the owned-input resolution into a helper **first** (campsite commit) so the conversion cannot push it to 16.
  6. `mission_check_prerequisites.py`:
     - option `:563` → `owned_checkout: OwnedCheckoutOption = None`;
     - `:595-602`: replace the local `from specify_cli.core.owned_mission import resolve_owned_mission` and its call with `resolve_owned_or_adopt`;
     - keep the `OWNED_OPTION_UNSUPPORTED` refusal for `--resume-probe` **after** validation, as today;
     - `:602` `repo_root = owned.root` → `owned.owned_root`; `:639` `owned.directory` → `owned.mission_dir`;
     - `check_prerequisites` is at 14: extract the owned block into a helper first.
  7. Refusals keep each command's existing JSON error envelope. Use `emit_owned_refusal` only where its output is byte-identical to the current envelope; otherwise keep the command's own emitter (the golden tests decide).
  8. Commits: one campsite commit per command (extraction only), then `refactor(cli): spec-commit and check-prerequisites resolve through the shared owned helper (WP16/T087)`.
- **Files**:
  - `src/specify_cli/cli/commands/spec_commit_cmd.py`
  - `src/specify_cli/cli/commands/agent/mission_check_prerequisites.py`
- **Parallel?**: Independent of T084–T086.
- **Validation checklist**:
  - [ ] `tests/specify_cli/cli/commands/test_spec_commit_cmd.py`, `tests/specify_cli/cli/commands/test_issue_2739_spec_commit_protected_primary_guard.py`, `tests/specify_cli/coordination/test_commit_router_partition.py`, `tests/coordination/test_commit_router_fail_loud.py` pass unchanged.
  - [ ] `tests/specify_cli/cli/commands/agent/test_mission_check_prerequisites.py`, `tests/agent/test_agent_feature.py`, `tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py`, `tests/specify_cli/test_meta_fail_closed_full_census_contract.py` pass unchanged.
  - [ ] `tests/integration/test_explicit_checkout_commands.py` passes unchanged: every `check-prerequisites` and `spec-commit` parametrisation, including `test_explicit_checkout_is_independent_of_cwd`, `test_resume_probe_cannot_opt_in`, `test_foreign_repository_is_refused`, `test_whole_commit_batch_is_validated_before_staging`.
  - [ ] `tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py` passes (help text).
  - [ ] Both functions ≤ 15 after the change.
- **Edge cases**:
  - `check-prerequisites` validates **before** the resume-probe refusal; keep that, so an invalid checkout reports its ownership code rather than `OWNED_OPTION_UNSUPPORTED`.
  - `spec-commit` derives `mission_slug` from the first file path when `--mission` is absent (`_derive_mission_slug`); the resolver must receive the same handle.
  - `spec-commit` without `--owned-checkout` run from inside P is FR-021 flagless adoption (WP08's behaviour); from R it must stay the non-owned path.

### Subtask T088 – FR-022 ratchet: existing owned `move-task` / `mark-status` / `spec-commit` tests

- **Purpose**: FR-022 / SC-005 — the regression guard for the rewire. Behaviour must not change. The only allowed test edit is an internal-shape re-point in a test file this WP owns.
- **Steps**:
  1. Run the whole list in the Test Strategy **before** changing any test, and again after T084–T087. Anything red on the planning base too is baseline red: classify per CLAUDE.md "Test-run baseline-red gotcha", record it, do not fix it.
  2. Re-point only this internal-shape usage in `tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py`, and only if it is still red:
     - `test_owned_ports_read_and_commit_only_selected_mission` (`:1001-1008`) constructs `MissionHandle(primary, SLUG, effective_root=owned)`. WP07 converts `MissionHandle`; if WP07 already re-pointed this line, leave it. Otherwise build the handle with `owned=<fact>`, minting the fact through the WP02 test helper (preferred; `OwnedCheckout._mint` is allowed in tests because G3 scans `src/` only, but the helper keeps facts realistic). Keep every assertion identical. Record in the Activity Log which WP made the change.
  3. Leave `test_owned_gate_baseline_reads_selected_mission_directory` (`:29-45`) unchanged: it builds `SimpleNamespace(owned=SimpleNamespace(root=tmp_path))`, and `_mt_resolve_gate_baseline` (`tasks_move_task.py:1818`) never reads `.root`. If your conversion makes that function read an attribute of the fact, you changed behaviour; revert that.
  4. `tests/integration/test_owned_checkout_mark_status.py` should need **no** change: it drives the CLI and monkeypatches only `transaction._reducer.materialize` (`:208`) and seams by name (`:279, 340, 392`). If it does need a change, that is a behaviour change: stop and report.
  5. Do not touch `tests/integration/test_explicit_checkout_commands.py` (WP19-owned); it must pass as is.
  6. Run the two unowned alias-constructing files named in T085's edge cases and record their state.
  7. Compare JSON envelopes before and after for the refusal scenarios: capture the `--json` output of one refusal per command on the planning base (for example a foreign repository, `test_foreign_repository_is_refused`) and assert key-for-key equality after the rewire. Keep this as a local check (not a committed test) unless an existing golden already covers it; note the result in the Activity Log.
  8. Record the final command lines and pass counts in the Activity Log for the PR's *Tests run* section.
- **Files**:
  - `tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py` (one internal-shape re-point at most).
- **Parallel?**: No; after T084–T087.
- **Validation checklist**:
  - [ ] `git diff -- tests/` shows only the re-point above (if WP07 had not already made it) plus the T089 additions.
  - [ ] All 20 tests in `test_owned_checkout_move_task.py` and all 7 in `test_owned_checkout_mark_status.py` pass.
  - [ ] The full Test Strategy list passes; exact command and counts are in the Activity Log.
  - [ ] No test was skipped or xfailed to get green.
  - [ ] `uv run --frozen pytest tests/integration/test_owned_checkout_mark_status.py -q` and `uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py -q` both pass on their own (fixture isolation) and in the combined run.
  - [ ] The refusal envelopes compared in step 7 are identical key for key.
- **Edge cases**:
  - The move-task file's compensation tests monkeypatch `tasks_move_task._mt_execute` and `revert_committed_verdict_write` by name, and `status_transition.emit_inner_state_changed_transactional` (`:901, 965`); do not rename those functions during extraction.
  - The refusal tests (`test_owned_preflight_refuses_before_effects`, `test_branch_refusal_has_no_side_effects`, `test_nested_checkout_refused_before_writes`, `test_staged_changes_are_never_stashed_or_committed`) are the tripwire for refusal-order drift caused by moving validation to the Typer edge.
  - `test_multi_wp_failure_reports_committed_prefix` depends on per-WP event emission order in `mark-status`; keep the loop order in `_ms_emit_subtask_state`.
  - `test_flagless_mark_status_preserves_primary_lookup` and `test_no_opt_in_keeps_primary_resolution` pin the flagless path from the repository root checkout; if the WP08 helper's adoption changes what they see, that is a WP08 contract issue — report it, do not adapt the test.
  - `test_explicit_checkout_is_independent_of_cwd` runs the same command from R, P and elsewhere; the Typer-edge resolution must not start depending on cwd.
  - If a baseline-red test blocks the ratchet, link the issue you filed (Pre-existing Failure Reporting Rule) in the Activity Log.

### Subtask T089 – Command-level exactly-one-validation assertions

- **Purpose**: FR-003 / NFR-002: exactly one ownership validation per owned command invocation. WP07/T037 pins it for `move-task`'s transition path; this subtask pins it at the command level for all four commands, so a re-introduced local validator call (the #3866 class) goes red.
- **Steps**:
  1. Write a counting fixture:
     - wrap the real `specify_cli.core.checkout_ownership.resolve_ownership_claim` with a counter (monkeypatch the module attribute; `owned_mission` imports it lazily inside `resolve_owned_mission`, so the module-attribute patch is observed);
     - delegate to the real function and return its result unchanged;
     - call `specify_cli.workspace.context.clear_workspace_resolution_caches()` before each counted invocation.
  2. In `tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py` (it already has the `checkouts` fixture via `__all__`):
     - `move-task WP01 --to claimed --owned-checkout P` → count == 1;
     - a `--to for_review` hop (the review path triggers the most readers) → count == 1.
  3. In `tests/integration/test_owned_checkout_mark_status.py`, in a clearly headed section, reuse the `checkouts`, `invoke`, `git`, `snapshot` helpers it already imports from `tests/integration/test_explicit_checkout_commands.py`:
     - `mark-status <a subtask id present in the fixture's tasks.md> --status done --owned-checkout P` → count == 1;
     - `spec-commit --owned-checkout P ...` → count == 1;
     - `check-prerequisites --owned-checkout P ...` → count == 1.
  4. Parametrise `mark-status` over "flag given" and "flagless from inside P" (FR-021 adoption goes through the same validator once).
  5. Negative: a flagless run from the repository root checkout performs **zero** ownership validations.
  6. Refusal: `move-task` with an invalid owned checkout still validates once and refuses (count == 1, exit ≠ 0, `error_code` present in `--json` output).
  7. Mark all of them `integration` + `git_repo`. Commit: `test(tasks): exactly-one ownership validation per owned task command (WP16/T089, NFR-002)`.
- **Files**:
  - `tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py` (append).
  - `tests/integration/test_owned_checkout_mark_status.py` (append).
- **Parallel?**: No; last.
- **Validation checklist**:
  - [ ] Each count test fails if you temporarily add a second `resolve_owned_mission` call in the command (mutation check; do not commit).
  - [ ] Each count test fails if validation is bypassed (count 0).
  - [ ] The counting wrapper delegates to the real function, so the commands still succeed.
- **Edge cases**:
  - Do not count `get_main_repo_root` or other git probes here; NFR-002's subprocess count for status reads is WP18/T099's.
  - Workspace-resolution caches are process-global; without clearing them a later test in the same worker can observe 0.
  - `spec-commit` is not under `agent tasks`; invoke it through the app `test_explicit_checkout_commands.invoke` already uses for it.

## Test Strategy

Targeted (existing files unchanged except the T088 re-points):

```bash
uv run --frozen pytest -q \
  tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py \
  tests/integration/test_owned_checkout_mark_status.py \
  tests/integration/test_explicit_checkout_commands.py \
  tests/specify_cli/cli/commands/agent/test_tasks_move_task_degod.py \
  tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py \
  tests/specify_cli/cli/commands/agent/test_move_task_durability.py \
  tests/specify_cli/cli/commands/agent/test_tasks_mark_status_seam.py \
  tests/specify_cli/cli/commands/agent/test_tasks_mark_status_recovery.py \
  tests/specify_cli/cli/commands/agent/test_mark_status_authored_roster.py \
  tests/specify_cli/cli/commands/agent/test_claim_event_source.py \
  tests/specify_cli/cli/commands/agent/test_issue_2684_subtask_completion_event_sourced.py \
  tests/specify_cli/cli/commands/agent/test_tasks_shared_seam.py \
  tests/specify_cli/cli/commands/agent/test_check_unchecked_subtasks_snapshot_source.py \
  tests/specify_cli/cli/commands/agent/test_tasks_surface_authority.py \
  tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py \
  tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py \
  tests/specify_cli/cli/commands/agent/test_tasks.py \
  tests/specify_cli/cli/commands/agent/test_mission_check_prerequisites.py \
  tests/specify_cli/cli/commands/agent/test_mission_cli_golden_contract.py \
  tests/specify_cli/cli/commands/test_spec_commit_cmd.py \
  tests/specify_cli/cli/commands/test_issue_2739_spec_commit_protected_primary_guard.py \
  tests/cli/test_move_task_planned_guard.py \
  tests/review/test_verdict_seam_reader_collapse.py tests/review/test_verdict_status_lock_bound.py \
  tests/integration/review/test_verdict_save_topologies.py tests/integration/test_review_durability_matrix.py \
  tests/specify_cli/review/test_cycle_kind_flip.py tests/coordination/test_verdict_dir_co_resolution.py \
  tests/coordination/test_surface_authority_goldens.py \
  tests/agent/test_agent_feature.py tests/agent/test_mission_handle_json_errors.py
```

To find any further test that exercises a touched module: `grep -rl "tasks_move_task\|tasks_mark_status\|tasks_shared\|tasks_parsing_validation\|tasks_verdict_persistence\|spec_commit_cmd\|mission_check_prerequisites" tests --include=*.py` (62 + 9 + 19 + 13 + 15 + 9 + 7 files on the planning base; run the ones outside `tests/architectural/` that the list above misses if your diff touches the code they cover).

Specific architectural gates implicated (files, not the directory):

```bash
uv run --frozen pytest -q \
  tests/architectural/test_owned_checkout_gate_selftest.py \
  tests/architectural/test_cli_error_surface_seam.py \
  tests/architectural/test_ruff_format_enforcement.py
```

Baseline and quality gates:

```bash
make test-fast
uv run --frozen ruff check $F tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py tests/integration/test_owned_checkout_mark_status.py
uv run --frozen ruff format --check $F tests/specify_cli/cli/commands/agent/test_owned_checkout_move_task.py tests/integration/test_owned_checkout_mark_status.py
uv run --frozen mypy --strict $F src/specify_cli/cli/commands/_owned_checkout.py src/specify_cli/cli/commands/agent/tasks.py \
  src/specify_cli/agent_tasks_ports.py src/specify_cli/coordination/status_transition.py src/specify_cli/review/cycle.py
```

(`$F` is the seven-file list from the census section.) Run mypy on callers and callees **together**: `follow_imports = "skip"` for `specify_cli.*` hides cross-module keyword mismatches otherwise. Record commands and counts in the Activity Log and the PR's *Tests run* section.

## Risks & Mitigations

- **Typer-edge ownership with WP09** (`tasks.py`). Mitigation: WP09 is a dependency of this WP; edit only the two wrapper call expressions, declared out-of-map.
- **Order-of-refusal drift.** Moving validation to the Typer edge can change which error an operator sees first (for example "Could not locate project root" vs an ownership code). Mitigation: the existing refusal tests (`test_owned_preflight_refuses_before_effects`, `test_branch_refusal_has_no_side_effects`, `test_nested_checkout_refused_before_writes`) must pass unchanged; if one changes, stop.
- **God-module size** (`tasks_move_task.py`, 3,708 lines). Mitigation: census-driven edits, small commits, complexity check per function.
- **Gate evasion by renaming.** Mitigation: explicit rule in Context; reviewers grep for `: Path | None` fields in the touched state dataclasses.

## Review Guidance

- Run the census; the only survivors may be logged bridges to unconverted callees.
- Confirm no dataclass field or parameter carries the owned checkout as a `Path` under any name in the seven files.
- Confirm the `tasks.py` edit exists and is limited to the two wrapper call expressions.
- Confirm the four exactly-once tests exist and fail under a planted second validation.
- Confirm the test diff is limited to T088/T089.
- Confirm mypy was run over callers and callees together, and passed.

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
- 2026-09-29T10:56:04Z – claude – shell_pid=2331 – WP16 implemented, NOT moved to for_review: T088 blocked on an FR-021 vs FR-022 conflict. Red-first: 440954755 (tests only, verified red: move-task claim 4x, for_review 4x, pin 5x vs ==1, flagless mark-status no adoption). Fix commits: 6c24f2309, 249927883, 2240b5597, bc0a8cd55, f1aa2b03f, + envelope fix. Markers: bridging WP16 = 0 (was 4); bridging WP17 = 2 (tasks_verdict_persistence.py create_rejected_review_cycle); TRANSITIONAL(WP18) added = 0. Out-of-map: _owned_checkout.py (resolve_owned_or_refuse, flat_error_envelope), tasks.py (wrappers, _resolve_task_owned, 3 re-exports), tasks_finalize_validation.py (_read_transactional_wp_lane owned=), test_tasks_compat_surface.py (3 symbols, 189->192), test_tasks_move_task_degod.py (owned_checkout->owned), test_transition_request_owned.py (==5 -> ==1), test_owned_checkout_move_task.py::test_context_error_envelope_is_opt_in (explicit row names --mission), new test_task_command_owned_conversion.py; cherry-pick dce4d02db (WP14 OwnedRefusalCode members, absent from lane base). Open: 3 pre-existing flagless tests now see adoption (cwd is the owned checkout): test_flagless_move_task_preserves_primary_lookup, test_flagless_mark_status_preserves_primary_lookup, test_explicit_checkout_commands::test_no_opt_in_keeps_primary_resolution.
- 2026-09-29T11:02:43Z – claude – shell_pid=2331 – T088 resolved per coordinator ruling: three flagless tests split into FR-022 control (from R) + FR-021 adoption row (from P). Adoption rows red on pre-WP16 base 550b4cb1c (scratch worktree), green on head. Out-of-map: test_explicit_checkout_commands.py (WP19). Final targeted counts recorded in move-task note.
- 2026-09-29T12:37:55Z – claude – Review cycle 1 fixed: typed _refusal_envelope (mypy equal base/head), counted check-prerequisites adoption row (red on base 550b4cb1c), docstring ref. Refusal output change (stderr Error: [CODE], indent=2 JSON) goes in the PR body.
