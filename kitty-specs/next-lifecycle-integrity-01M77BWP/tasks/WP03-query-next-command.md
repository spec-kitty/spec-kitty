---
work_package_id: WP03
title: Read-only next names the next command
dependencies:
- WP01
requirement_refs:
- FR-008
- FR-009
- FR-010
- NFR-002
- SC-003
planning_base_branch: fix/7548-next-lifecycle-integrity
merge_target_branch: fix/7548-next-lifecycle-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/7548-next-lifecycle-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7548-next-lifecycle-integrity unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T014
phase: 'Phase 2 - #7553 query envelope'
history:
- at: '2026-11-12T08:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-11-12T09:30:00Z'
  actor: claude
  action: Revised after the post-tasks adversarial squad and operator rulings
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/next/test_query_next_command_7553.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge_query.py
- tests/next/test_query_next_command_7553.py
- docs/architecture/runtime-loop.md
- src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Read-only next names the next command

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role `implementer`) before reading on.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log and address every item.

---

## Objectives & Success Criteria

This WP delivers FR-008, FR-009 and FR-010 (query side), plus FR-007 (query side).

`kind=query` stays the read-only mode, and `question` stays nullable. The operator ruled on this after a two-lens research squad (`specify.next.query_question_final`, `plan.next.query_invariant`).

1. **FR-009.** An untouched run whose first runtime decision is `decision_required` keeps `decision_id`, `question` and `input_key` (and `options` if any).
   - They are built through WP01's `PendingDecisionPrompt`, so the WP01 construction check holds.
   - The envelope **also** carries `next_command` = the advance command. The decision is not pending yet: an untouched run has nothing pending, and `provide_decision_answer` refuses ids not in `pending_decisions` (`_internal_runtime/engine.py:900-902`). The agent must advance to make it answerable.
   - Keep `mission_state="not_started"`, `kind=query` and `preview_step`, so the built-in specify prompt's replay guard is unchanged. Document this in the docstring.
   - Today `_build_initial_query_decision` drops these fields (`runtime_bridge_query.py:216-239`).
2. **FR-010 (query side).** Every query builder that sets a decision goes through `PendingDecisionPrompt`. `_build_decision_required_query` is one of them.
3. **FR-008.** Every read-only envelope gets `next_command`, except a pending, answerable decision and a landed Mission.

   | Situation (query) | `next_command` |
   |---|---|
   | `not_started` preview (step or first decision) | `spec-kitty next --agent <agent> --mission <slug> --result success` |
   | finalized board → implement/review preview, `blocked:*` | the same advance command |
   | in-flight run (step issued, or blocked) | the same advance command |
   | `task_error` early return (`:377-392`) | the same advance command (it re-surfaces the error with details) |
   | finished software-dev board, `AWAITING_ACCEPTANCE` | `spec-kitty accept --mission <slug>` |
   | finished software-dev board, `ACCEPTED` (fresh) | `spec-kitty consolidate --mission <slug>` |
   | runtime terminal (`mission_state="done"`, e.g. a no-WP Mission whose run completed), not landed | accept if not accepted, else consolidate |
   | pending decision on a touched run (answerable) | absent: the path is `--answer` |
   | landed (merged short-circuit, `terminal_kind=query`) | absent |

   - When the query `agent` is None, use the literal placeholder `<agent>`. Never invent an identity.
   - Use the same verdict as advance (FR-007): WP01's `finished_board_verdict(board_step, accepted_at=mission_accepted_at(primary_dir), latest_transition_at=board_latest_transition_at(board))`.
   - Software-dev only, as in WP02: other families get the advance command for a finalized board.
   - `mission_state` values are unchanged.
4. **Docs** explain the start handshake, the never-rewind answers, the invariant and `next_command`.

## Context & Constraints

- **Read first:** `plan.md` IC-03 (revised), `research.md` R-5 and the Squad dispositions, and `contracts/next-envelope-additions.md`.
- **Fact corrections from the squad:**
  - `_query_resolve_primary` returns `(slug, task_board_dir, mission_type)` with **no** PRIMARY_METADATA dir, and the owned path discards `owned_meta_dir` (`:485-516`). Widen it to also return the metadata dir, and update the caller at `:191`.
  - `finalized_override` is computed inside `_query_dispatch_decision` (`:609-613`) and not returned. Compute it and the verdict **once** in `query_current_state` and pass them in.
  - None of this adds a door read: reuse the board `query_current_state` already read.
- **`next_cmd.py` is owned by WP02.** WP02's T013 renders `Next:` for any decision carrying `next_command`. You do not touch it.
- **Consumers that must not break:**
  - the specify prompt's replay guard (`kind`/`mission_state`/`preview_step`);
  - `tests/next/test_query_mode_unit.py`;
  - `tests/contract/test_next_no_implicit_success.py`;
  - `tests/specify_cli/next/test_next_output_preservation.py`;
  - the orchestrator-api pass-through (an additive key).
- If `tests/architectural/test_json_contract_enumeration.py` enumerates `next` keys, triage `next_command` through its documented mechanism, and never weaken it. Note that this file is not in your `owned_files`: if it needs an edit, make the smallest one and record a one-line rationale (ownership leeway).

## Branch Strategy

- **Planning base / merge target**: `fix/7548-next-lifecycle-integrity`.
- Run `spec-kitty agent action implement WP03 --agent claude --mission next-lifecycle-integrity-01M77BWP`.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first tests (commit first)

- **File**: `tests/next/test_query_next_command_7553.py`.
- **Fixtures**:
  - `_scaffold` (`tests/next/test_finalized_task_routing.py`) for board cells;
  - `tests/next/test_next_command_integration.py`'s `_scaffold_project` + `_write_runtime_input_mission` for fresh and first-decision cells. The squad verified that `_write_runtime_input_mission` yields `decision_required` on advance and `preview_step=collect_input` with the fields dropped on query.
- **Cells:**
  1. A fresh software-dev Mission: `next_command` is the advance command, and `question` is None. Drive it through the CLI: `spec-kitty next --agent claude --mission <slug> --json`.
  2. A first step requiring input: `decision_id`, `question` and `input_key` are present, `next_command` is the advance command, and `mission_state=="not_started"`. Drive it through the CLI.
  3. An approved board, not accepted: the accept command.
  4. Accepted after the latest transition: the consolidate command. Accepted before the latest transition: the accept command.
  5. All-canceled board: the accept command.
  6. Landed (set `merged_at`, as in `tests/runtime/next/test_merged_mission_terminal.py`): no `next_command`.
  7. A touched run with a pending decision: `next_command` is absent.
  8. A `task_error` fixture (a finalized board with a malformed WP file; see how `_wp_task_surface_error` triggers): the advance command.
  9. Agent None (bridge-level `query_current_state(None, ...)`): the `<agent>` placeholder.
  10. Invariant sweep: every envelope from cells 1–9 satisfies question ⇔ decision_id, and options or input_key is present when a question is set.
- Commit alone: `test(next): red-first query next_command and first-decision drop (#7553)`.

### Subtask T011 – The first decision keeps its fields

- In `_query_dispatch_decision`'s untouched-run branch:
  - for `runtime_decision.kind == DecisionKind.decision_required`, build the `not_started` envelope **with** the prompt, via a `PendingDecisionPrompt` from the runtime decision;
  - `kind == step` stays as today.
- Migrate `_build_decision_required_query` to the value object.

### Subtask T012 – `next_command`

- Add one helper, `_query_next_command(decision, *, agent, mission_slug, verdict, family_is_software_dev, accepted_at) -> str | None`. Apply it once to the dispatch result and once to the `task_error` envelope (`decision.next_command = ...`, or `dataclasses.replace`).
- Hoist the command templates into module constants (Sonar S1192). Verify the advance flags with `spec-kitty next --help`, and the accept/consolidate flags with their `--help`.

### Subtask T014 – Docs

- **`docs/architecture/runtime-loop.md`:**
  - Query Mode section: `next_command`; the question ⇔ decision_id invariant; the start handshake (a fresh Mission and a first decision both need `--result success` first).
  - Never-rewind section: a finished board gives blocked `MISSION_AWAITING_ACCEPTANCE`, then accept, then terminal. Acceptance must be newer than the latest WP transition. A non-dispatchable board step gives blocked `BOARD_STEP_NOT_DISPATCHABLE` with a resume command. Software-dev only.
  - Residuals: `MissionRunCompleted` is not reached for a run that is not authoritative; a stale run that was already replayed to analyze or beyond.
  - Fix the drift at `:236-244`: merged means `merged_at` via `mission_has_landed`.
  - Update the `updated:` frontmatter.
- **`src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md`:** the envelope table (`next_command`, the two new error codes) and the "terminal → run acceptance" guidance, which must no longer contradict the code.
- Run `pytest tests/architectural/test_no_legacy_terminology.py`. Use "Mission", never "feature".

## Test Strategy

```bash
.venv/bin/python -m pytest tests/next/test_query_next_command_7553.py tests/next/test_query_mode_unit.py tests/next/test_finalized_task_routing.py tests/next/test_next_command_integration.py tests/specify_cli/next tests/contract/test_next_no_implicit_success.py tests/contract/test_next_no_unknown_state.py tests/runtime/next/test_merged_mission_terminal.py tests/runtime/next -q -n 4 --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_status_read_single_door.py tests/architectural/test_inline_meta_read_gate.py -q
uv run --frozen ruff check src/runtime/next/runtime_bridge_query.py tests/next/test_query_next_command_7553.py
uv run --frozen ruff format --check --force-exclude src/runtime/next/runtime_bridge_query.py tests/next/test_query_next_command_7553.py
uv run --frozen mypy src/runtime/next/runtime_bridge_query.py
```

## Risks & Mitigations

- **The specify-prompt replay guard.** The fresh path keeps `kind`, `mission_state` and `preview_step`.
- **Fabricated agent names.** Use the placeholder.
- **Families.** Gate the verdict use on software-dev.

## Review Guidance

- Red→green.
- The invariant holds by construction.
- No added door read.
- The docs match the shipped behaviour, and the terminology guard is green.

## Activity Log

- 2026-11-12T08:30:00Z – system – Prompt created.
- 2026-11-12T09:30:00Z – claude – Revised: first-decision gets next_command, metadata dir plumbing, task_error row, runtime-terminal row, renderer moved to WP02.
