---
work_package_id: WP03
title: Read-only next names the next command
dependencies: [WP01]
requirement_refs:
- FR-008
- FR-009
- FR-010
- NFR-002
- SC-003
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: 'Phase 2 - #7553 query envelope'
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-11-12T08:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/next/test_query_next_command_7553.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge_query.py
- src/specify_cli/cli/commands/next_cmd.py
- tests/next/test_query_next_command_7553.py
- docs/architecture/runtime-loop.md
- src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md
role: implementer
task_type: implement
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

This WP delivers FR-008, FR-009 and FR-010, plus the query side of FR-007.

`kind=query` stays the read-only mode, and `question` stays nullable. That was the operator ruling of 2026-11-12, after a two-lens research squad. It is recorded as `specify.next.query_question_final` in `decisions/`.

1. **FR-009:** an untouched run whose first runtime decision is `decision_required` keeps `question`, `decision_id`, `input_key` and `options` in the read-only envelope. Today `_build_initial_query_decision` drops them (`runtime_bridge_query.py:216-239`, routed from `_query_dispatch_decision` around `:636`).
2. **FR-010 invariant:** on every read-only envelope, `question is not None` iff `decision_id is not None and options is not None`.
3. **FR-008:** every read-only envelope that carries no pending decision gets `next_command`, unless the Mission has landed (the merged short-circuit query has no `next_command`).

   | Situation (query) | `next_command` |
   |---|---|
   | `not_started` (fresh run preview) | `spec-kitty next --agent <agent> --mission <slug> --result success` |
   | finalized board → implement/review preview | same advance command |
   | finalized board, `blocked:*` | same advance command (it re-surfaces the blocker with its details) |
   | in-flight run, step issued, or blocked | same advance command |
   | finished board, verdict `AWAITING_ACCEPTANCE` | `spec-kitty accept --mission <slug>` |
   | finished board, verdict `ACCEPTED` | `spec-kitty consolidate --mission <slug>` |
   | pending decision (`question` set) | absent; the answer path is `--answer` |
   | landed (merged short-circuit) | absent |

   - When the query `agent` is None (the CLI allows a bare query), use the placeholder `<agent>` in the advance command. Never invent an agent name. Document this.
   - Use the WP01 predicate `runtime_bridge_cores.finished_board_verdict` and `runtime_bridge_io.mission_is_accepted` for the finished-board rows (FR-007: same predicate as advance).
   - Keep `mission_state` values unchanged (`accept` and `done` stay as they are).
4. The human renderer prints a `Next: <command>` line when `next_command` is set.
5. Docs explain the start handshake, the finished-board answers and the invariant.

## Context & Constraints

- Read first:
  - `plan.md` IC-03
  - `research.md` R-5
  - `contracts/next-envelope-additions.md`
  - `research/code-grounding.md` §1 ("kind=query with a null question")
- Consumers that must not break:
  - the built-in specify prompt's replay guard (`packs/built-in/...`, read-only for us), which keys on `kind=="query"`, `mission_state=="not_started"` and `preview_step`, all unchanged;
  - `tests/next/test_query_mode_unit.py`;
  - `tests/contract/test_next_no_implicit_success.py`;
  - `tests/specify_cli/next/test_next_output_preservation.py`.
- If `tests/architectural/test_json_contract_enumeration.py` (or a JSON-contract snapshot) enumerates `next` keys, add `next_command` there via its documented triage mechanism. Never weaken it.
- Do **not** touch `runtime_bridge.py`, `runtime_bridge_decision_mapping.py` (WP02), the cores, `decision.py` or io (WP01), or `packs/built-in/`.
- Single door read per query is preserved (`query_current_state` already reads the board once; reuse it).

## Branch Strategy

- **Planning base / merge target**: `fix/7548-next-lifecycle-integrity`.
- Run `spec-kitty agent action implement WP03 --agent claude --mission next-lifecycle-integrity-01M77BWP`.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first tests (commit first)

- **File**: `tests/next/test_query_next_command_7553.py`.
- **Fixtures**: `_scaffold` from `tests/next/test_finalized_task_routing.py` for board cells. `tests/next/test_next_command_integration.py` helpers (`_scaffold_project`, `_write_runtime_input_mission`, which writes a mission whose first step `requires_inputs`) for fresh and first-decision cells.
- **Cells**:
  1. fresh software-dev Mission → `next_command` = the advance command, `question is None`;
  2. first step requires input → `question`, `decision_id`, `options` present, `next_command` absent;
  3. approved board, not accepted → accept command;
  4. accepted → consolidate command;
  5. landed (set `merged_at` as `tests/runtime/next/test_merged_mission_terminal.py` does) → no `next_command`;
  6. invariant sweep over all cells (FR-010).
- At least cells 1 and 2 go through `CliRunner` (`spec-kitty next --agent claude --mission <slug> --json`, no `--result`).
- Commit alone: `test(next): red-first query next_command and first-decision drop (#7553)`.

### Subtask T011 – First `decision_required` keeps its question

- In `_query_dispatch_decision`, the untouched-run branch (`if not snapshot.completed_steps and not snapshot.pending_decisions and not snapshot.decisions:`):
  - when `runtime_decision.kind == DecisionKind.decision_required`, return `_build_decision_required_query(...)`;
  - keep `_build_initial_query_decision` for `kind == step`.
- `_build_decision_required_query` reads `snapshot.issued_step_id or runtime_decision.step_id`. With an untouched snapshot that falls back to the runtime decision's step, which is correct.
- Does `mission_state` then become the step id instead of `not_started`? Decide which is right, given that the specify prompt's replay guard only applies to a `step` preview. Keeping `not_started` plus the decision fields may be safer: check `runtime-loop.md:80` and `test_query_mode_unit.py` and record the choice.

### Subtask T012 – `next_command` on query envelopes

- Add one small helper, `_query_next_command(decision, *, agent, mission_slug, verdict) -> str | None`, applied once at the end of `query_current_state`'s dispatch, via `dataclasses.replace`. Do not touch every builder.
- Compute the verdict from the finalized-override step the dispatch already computed (`_finalized_task_board_override_step`) and `mission_is_accepted(primary dir)`.
- The primary metadata dir is available from `_query_resolve_primary` / the mission context that `query_current_state` already resolves. Reuse it. Do not re-resolve.
- Skip when `decision.question is not None` and on the merged short-circuit return path (it returns before dispatch; confirm).
- Constants: hoist the command templates into module constants (Sonar S1192). The advance command format must match `next_cmd`'s actual flags (`--agent`, `--mission`, `--result`); verify with `spec-kitty next --help`.

### Subtask T013 – Human renderer

- In `next_cmd.py`, `_print_query_details` (around `:1453-1480`): after the Question/Reason lines, print `Next: <command>` when `decision.next_command` is set.
- The advancing human renderer for a `blocked` decision should also print it, since WP02's blocked answer carries `next_command`. Find the blocked printer in `next_cmd.py` and add one line.
- JSON output needs no change: it is `to_dict`.

### Subtask T014 – Docs

- `docs/architecture/runtime-loop.md`:
  - Query Mode section: add `next_command`, the question-iff-decision invariant, and the start handshake.
  - Finished board: blocked `MISSION_AWAITING_ACCEPTANCE` → accept → terminal.
  - Fix the drift at `:236-244`: "merged" is `merged_at` via `mission_has_landed`, not `mission_number`.
  - Update the `updated:` frontmatter date (docs-freshness styleguide).
- `src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md`:
  - envelope table: `next_command`, the new error code, and "terminal → done; finished board → accept first";
  - make sure the "terminal → run acceptance" guidance no longer contradicts the new behaviour.
- Run `pytest tests/architectural/test_no_legacy_terminology.py` (it is required when touching `src/charter/offering/` or user-facing prose). Use "Mission", never "feature".

## Test Strategy

```bash
.venv/bin/python -m pytest tests/next/test_query_next_command_7553.py tests/next/test_query_mode_unit.py tests/next/test_finalized_task_routing.py tests/next/test_next_command_integration.py tests/specify_cli/next tests/contract/test_next_no_implicit_success.py tests/contract/test_next_no_unknown_state.py tests/runtime/next/test_merged_mission_terminal.py -q -n 4 --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_status_read_single_door.py tests/architectural/test_inline_meta_read_gate.py -q
uv run --frozen ruff check <changed py> && uv run --frozen ruff format --check --force-exclude <changed py> && uv run --frozen mypy src/runtime/next/runtime_bridge_query.py src/specify_cli/cli/commands/next_cmd.py
```

## Risks & Mitigations

- **Specify-prompt replay guard.** Keep `kind`, `mission_state` and `preview_step` unchanged on the fresh path.
- **Agent placeholder.** Never fabricate an agent identity.
- **The orchestrator-api passes the envelope through** (`orchestrator_api/runtime_next.py`). An additive key is fine; check its contract tests if one snapshots keys.

## Review Guidance

- Invariant cells pass; red→green is proven.
- No new door read; docs match shipped behaviour; terminology guard is green.

## Activity Log

- 2026-11-12T08:30:00Z – system – Prompt created.
