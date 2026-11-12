# Code grounding: `next` lifecycle integrity (#7548: #7553, #7582)

updated: 2026-11-12 · base: origin/main (4.0.0rc9) · read-only squad of three grounding agents plus one fresh-context second opinion.
Reader: the implementer and reviewer of this Mission (software-engineer persona).

## 1. #7553: `next --result success` replays the lifecycle after accept

### Entry and what one advance records
- `next_step` (`src/specify_cli/cli/commands/next_cmd.py:297`).
  - Without `--result`, it runs query mode: `_run_query_mode` (`:1250`), then `runtime_bridge.query_current_state`.
  - With `--result`, it runs `_dispatch_advancing_mode` (`:447`) in this order:
    1. pair the previous lifecycle record;
    2. `decide_next`, which reaches `runtime_bridge.decide_next_via_runtime` (`src/runtime/next/runtime_bridge.py:1502`);
    3. `MissionNextInvoked` row, then commit (#5938/#7562);
    4. issuance lifecycle record.
- One advance writes "step rows" to three stores:
  - **Run journal.** `.kittify/runtime/runs/<run>/run.events.jsonl` gets `NextStepAutoCompleted` and `NextStepIssued` (`_internal_runtime/engine.py:481,494,107`, inside `_commit_advance` `:547`).
  - **Invocation lifecycle.** `kitty-ops/lifecycle/` gets `started`/`completed` (`src/runtime/next/next_invocation_lifecycle.py:148,244`). `pair_previous_lifecycle_record` marks the last `started` as `completed` on any `success`.
  - **Mission event row.** `mission-events.jsonl` gets `MissionNextInvoked` (`next_invocation_lifecycle.py:402-445`).

### How the step is decided (`decide_next_via_runtime`)
1. `_merged_mission_short_circuit` (`runtime_bridge_decision_mapping.py:227`) returns `terminal` only when `committed_authority.mission_terminal_verdict` holds, which requires the Mission to have landed (`mission_has_landed`, `src/mission_runtime/landing.py:27`).
2. `_dn_bootstrap` (`runtime_bridge.py:519`, **complexity 15, at the ceiling**) re-checks landed (`_primary_mission_is_completed` `:340`). Then `get_or_start_run` (`runtime_bridge_io.py:834`) starts a fresh run when `feature-runs.json` has no entry.
3. The phases run in this order:
   - `_dn_finalized_board_override` (`:753`)
   - `_dn_dependency_gate` (`:879`)
   - `_dn_composition_dispatch` (`:1140`)
   - `_dn_decision_materialize` (`:1400`)
4. `engine.apply_result` (`engine.py:291-314`) moves the issued step into `completed_steps` on any `success`, with no evidence that it ran.

### Root cause (confirmed by the second opinion; same defect as #5929 / #7565)
- **Nothing on the `next` path reads acceptance.** `accepted_at` (`mission_metadata.record_acceptance` `:1054`) is never read under `src/runtime` or `src/mission_runtime`, and no acceptance status event exists. The only terminal checks key on *landed*.
- **The front phase never moves the run.** `_dn_finalized_board_override` dispatches implement/review from the board, but it never advances or records the persisted run, so the run stays untouched (`issued_step_id=None`, `engine.py:235`) through implement/review.
- **Any fall-through issues `discovery`.** That covers a board decline (all approved/done: `_board_step_action` `:592` maps `accept`/`done` to `_WP_BOARD_DECLINE`), `--result failed|blocked`, and the mid-implementation decline (#5929 comment 2).
  - The engine then records a `raci:discovery` decision. `_run_is_untouched` (`:743`) becomes False for good.
  - Each `--result success` then completes the issued step and issues the next: discovery → specify → plan → tasks → analyze.
  - The artifact guards pass, because those artifacts exist.
- **Query and advance disagree.** Query applies the finalized-board override on every run (`runtime_bridge_query.py:613`). Advance applies it only to an untouched run (`runtime_bridge.py:775`).
  - Query returns `mission_state="accept"` for an all-approved board and `done` only once every WP is `done` (`runtime_bridge_query.py:177-186`).
  - Neither mode reads acceptance.

### Evidence
- **Real false rows.** `kitty-specs/upgrade-seeded-list-hint-01M6BV1A/mission-events.jsonl` has 5 `MissionNextInvoked` rows (`result_input: success`): research, specify, plan, tasks, analyze, all within 3 minutes after accept.
- **Bridge-level reproduction on main.** `research/test_repro_7553.py` (scratch, uses the `_scaffold` fixture from `tests/next/test_finalized_task_routing.py`, all WPs DONE, `accepted_at` set). Output:
  - `QUERY0 query done`
  - `ADV0 step discovery`, `ADV1 specify` (`completed=[discovery]`), `ADV2 plan` …
- **Pinned as intended.** `tests/next/test_next_advance_first_contact_5310.py:106` asserts only "no implement/review is dispatched" for an all-approved board. Its docstring (`:8`) blesses the pre-existing fall-through.

### `kind=query` with a null question
- `kind=query` means *read-only preview* in the documented contract:
  - `Decision.question: str | None` (`src/runtime/next/decision.py:160`);
  - the runtime-next SKILL example shows `"question": null`.
- `question` is set only by `_build_decision_required_query` (`runtime_bridge_query.py:242`).
- On a fresh software-dev Mission the preview is the `discovery` step, so a null question is correct.
- **Latent bug.** `_query_dispatch_decision` (`:593`) sends an untouched run whose first decision is `decision_required` through `_build_initial_query_decision` (`:216-239`). That drops `question`, `decision_id` and `options`. It is reachable only when the first step `requires_inputs` (`_internal_runtime/planner.py:459-475`), which means custom mission types; built-in software-dev declares none.

### Constraints on a fix
- **Acceptance is not on the status read door.** `StatusReadSurface` (`status/read_surface.py:110-131`) has no acceptance fact. Read it from PRIMARY `meta.json` through `load_meta` / `load_meta_or_empty`.
  - A raw `json.loads` trips `tests/architectural/test_inline_meta_read_gate.py`.
  - `mission_metadata` is already allowed for runtime (`test_layer_rules.py:178-200`).
- **`accepted_at` is sticky.** Nothing clears it on reopen, unlike the reopen-aware `is_mission_merged` (`status/lifecycle.py:295`). Reading it as terminal must also require the board to still be finalized.
- **Artifact-only (`plan`) Missions** need a fully completed run to accept (`acceptance/non_wp_runtime.py:82-84`). Boards with no WPs (`total_wps==0`, `decision_mapping.py:118`) and the research/custom families must keep their DAG-only behaviour byte-identical.
- **`MissionRunCompleted` and the retrospective gate** (`before_run_completed`, `runtime_bridge.py:1366-1377`) are reached by the final advance. `_primary_mission_is_completed`'s docstring (`:343-347`) deliberately refuses to short-circuit an unmerged, all-terminal Mission.
- **Docs.** `docs/architecture/runtime-loop.md:196` says "terminal → run acceptance". Its `:236-244` "merged = `mission_number` assigned" has drifted from the code, which keys on `merged_at`.
- **Gates touching these files:**
  - `test_status_read_single_door.py`
  - `test_no_read_side_bypass.py`
  - `test_no_write_side_rederivation.py`
  - `test_event_log_writes_gate.py:170` (the run journal `_append_event` is a frozen single caller)
  - `test_run_index_single_reader.py`
  - `test_bridge_cores_import_boundary.py`
  - `test_inline_meta_read_gate.py`
  - `test_json_contract_enumeration.py`
  - `tests/contract/test_next_no_unknown_state.py`
- **Sizes, at 90-day churn.** Undercounted, because the clone is shallow.

  | File | Lines |
  |---|---|
  | `next_cmd.py` | 1587 |
  | `runtime_bridge.py` | 1583 |
  | `runtime_bridge_decision_mapping.py` | 1129 |
  | `runtime_bridge_query.py` | 760 |
  | `next_invocation_lifecycle.py` | 459 |
  | `engine.py` | 1104 |

- **Test seams.** These four ran 75 passed in 164 s (`-n 4`):
  - `tests/next/test_finalized_task_routing.py` (`_scaffold`)
  - `tests/next/test_next_advance_first_contact_5310.py`
  - `tests/runtime/next/test_merged_mission_terminal.py`
  - `tests/integration/test_owned_lifecycle_acceptance_next.py`

  The red-first CLI location is `tests/next/test_next_command_integration.py` (CliRunner + git helpers).
- **Wedged runs.** An orphaned run that already carries `raci:discovery` stays wedged after a code fix unless the fix overrides stale walked runs too (#5929 comment 1).

## 2. #7582: a rejection or reopen resets every subtask

- **Where subtask state lives.**
  - The authority is the snapshot `subtasks` slot, folded from `InnerStateChanged` annotations (`status/models.py:795,890,910-917`).
  - The roster is the WP frontmatter `subtasks:` (`core/subtask_rows.py:295`).
  - tasks.md checkboxes are no longer the authority.
  - `mark-status` is implemented in `cli/commands/agent/tasks_mark_status.py:567-630`.
- **The only reset path** is `move-task --to planned`, from any source lane: `_mt_execute` → `_mt_emit_runtime_state` (`tasks_move_task_executor.py:520-521`) → `_build_claim_review_override` (`tasks_move_task_hops.py:394-456`) → `_mt_rollback_subtasks_reset` (`executor.py:386-416`).
  - Every roster id is set to `planned`, except `skipped` ones.
  - The reset is written as one `InnerStateChanged`, *after* the lane transition.
- **Routes that do not reset:**
  - the rejection edge `in_review -> in_progress`;
  - the approved reopen `approved -> in_progress` (#4899);
  - `orchestrator-api transition --to planned` (`orchestrator_api/wp_lifecycle.py:837`);
  - `agent status emit`.
- **The reset is deliberate.** Closed #2513 added it: a rollback that kept `[x]` let the `for_review` subtask gate pass with no rework.
- **It is already announced.** Closed #3578 added `_RollbackResetSummary` (`executor.py:330-382`), which prints "↺ Reset N subtask(s) to planned … re-verify" and emits the JSON fields `subtasks_reset_count`, `subtasks_reset_ids`, `subtasks_previously_completed` and `subtasks_never_completed` (`tasks_move_task.py:1872-1940`). Reproduced on main (`research/test_repro_7582.py`).
- **What the event log already records:**
  - The PLANNED transition carries `reason` ("backward rewind: in_review -> planned: review-cycle://…") and `review_ref` (`tasks_verdict_persistence.py:978`).
  - The annotation's `delta.subtasks` lists each reset id.
  - Missing: an explicit link between the two, and *which subtasks had been completed* (`previously_completed`, `executor.py:360-383`).
- **No review names specific subtasks.** `ReviewResult` (`models.py:553`) and the review-cycle frontmatter (`review/artifacts.py:153-174`) carry `affected_files` and nothing per subtask.
- **What protects the reset's purpose:**
  - `_guard_subtasks` (`tasks_transition_core.py:880-897`) and the pipeline guard (`wp_state.py:496-500`) block `for_review`, `approved` and `done` on non-terminal subtasks.
  - Nothing else proves rework happened: implementation evidence is any prior event (`emit.py:549`), and the lane `for_review` gate counts commits from the base to the lane tip with no "since the rejection" check.
  - So keeping subtasks would re-open #2513 on lane topologies.
- **Where a reset record could live.**
  - The transition's `policy_metadata` is a free dict (spec_kitty_events `diary.py:491`); no library release is needed.
  - `WPInnerStateDelta` is a typed library dataclass (`diary.py:618`); a field there needs a spec-kitty-events release. Unknown keys are dropped silently.
  - A new `policy_metadata` key counts as runtime evidence in `cutover_eligibility.py:97-122`. That is harmless, but it must be tested.
  - `test_dossier_sha_provenance.py` only gates SHA-valued keys.
  - The summary must be computed *before* the PLANNED hop.
- **Sizes:**

  | File | Lines | Complexity |
  |---|---|---|
  | `tasks_move_task.py` | 2322 | `_do_move_task` at 15 |
  | `tasks_move_task_executor.py` | 619 | |
  | `tasks_move_task_hops.py` | 456 | |
  | `tasks_transition_core.py` | 1075 | |

- **Gates touching these files:**
  - `test_status_events_writes_gate.py:216`
  - `test_no_write_side_rederivation.py`
  - `test_innerstatechanged_invariants.py`
  - `test_exemption_registry_ratchet.py`
  - `test_2093_authority_invariant.py`
- **Test seams.** `tests/specify_cli/cli/commands/agent/test_tasks_move_task_cli_4899.py` (`_build_in_review_repo`, `_move_task_cli`) and `test_move_task_rollback_signal.py`.
  - Both sit in `tests/specify_cli/cli/commands`, which is out of the per-PR CI matrix, so run them explicitly.

## 3. Evidence register
- `upgrade-seeded-list-hint-01M6BV1A/traces/tooling-friction.md:5`: replay after accept, recorded rows.
- `upgrade-dry-run-sequenced-verdict-01M68J9V/traces/tooling-friction.md:7`: null question on a not-started Mission.
- `runtime-status-read-door-01M73HHB/traces/tooling-friction.md:30`: reopening WP06 reset T029–T034; the reopen message says "re-verify, don't rebuild", but the checklist state contradicts it.
- `startup-assess-cold-concurrency-01M3EQ9S` F-3 is **not** a subtask reset. It is the assignee rebind on `--to planned --agent reviewer` and is out of scope.
- rc7 step register (gist, read as fragments; the raw gist is blocked here):
  - **6.9:** subtask status is set 14 times by the model and 17 by the walker. Verdict: "derive from the completion signal".
  - **6.10:** `move-task --to for_review`. Verdict: "this is `next --result success`".
  - **7.7:** the verdict is judgement, the lane transition is not.
  - **C2:** `next` names a step but not its contract.

  All four are roadmap context. REFS only.
