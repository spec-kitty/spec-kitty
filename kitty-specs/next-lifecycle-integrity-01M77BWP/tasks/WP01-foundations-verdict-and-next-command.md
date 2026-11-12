---
work_package_id: WP01
title: 'Foundations: board verdict, additive next_command, validated decision prompt'
dependencies: []
requirement_refs:
- C-001
- FR-002
- FR-007
- FR-010
- NFR-002
- NFR-003
planning_base_branch: fix/7548-next-lifecycle-integrity
merge_target_branch: fix/7548-next-lifecycle-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/7548-next-lifecycle-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7548-next-lifecycle-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-next-lifecycle-integrity-01M77BWP
base_commit: 6969bd06a0ec7afcfc94a7009f5bb1a248042d54
created_at: '2026-11-12T09:17:05.200206+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T020
phase: Phase 1 - Foundations (tidy-first)
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
- tests/runtime/next/test_finished_board_verdict.py
- tests/runtime/next/test_pending_decision_prompt.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge_cores.py
- src/runtime/next/decision.py
- src/runtime/next/runtime_bridge_io.py
- tests/runtime/next/test_finished_board_verdict.py
- tests/runtime/next/test_pending_decision_prompt.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Foundations: board verdict, additive next_command, validated decision prompt

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role `implementer`), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission next-lifecycle-integrity-01M77BWP`). Address every feedback item.

---

## Objectives & Success Criteria

This WP adds enablers that WP02 and WP03 build on (Charter Standing Order 2, tidy-first). It changes no behaviour, except one new validation at construction time (FR-010), and every existing envelope must already satisfy it.

1. A pure `finished_board_verdict(board_step, *, accepted_at, latest_transition_at)` in the cores leaf (FR-002 freshness, FR-007).
2. `Decision.next_command: str | None = None`, serialized in `to_dict` only when set (NFR-002).
3. `Decision.suppress_step_pairing: bool = False`, an **internal** flag that is **never** serialized. A gate answer (WP02) sets it so that `next_cmd` does not pair a stale issued step as completed (FR-003).
4. **FR-010, by construction** (operator ruling 2026-11-12: "split off the constructors into separate models, so invalid ones can simply not be created"):
   - A validated frozen value object `PendingDecisionPrompt(decision_id: str, question: str, input_key: str | None, options: list[str] | None)`. Its `__post_init__` requires a non-empty `decision_id` and `question`, and at least one of `options` / `input_key`.
   - `Decision.__post_init__` additionally enforces, for `kind in {query, decision_required}`, that `question is not None` iff `decision_id is not None`, and that when they are set, `options is not None or input_key is not None`.
   - A classmethod or helper on the cores, `DecisionEnvelope.with_prompt(prompt)` (or an envelope field `prompt: PendingDecisionPrompt | None`), lets builders set the four fields only through the value object. WP03 migrates the query builders to it.
5. I/O helpers in `runtime_bridge_io.py`:
   - `mission_accepted_at(primary_metadata_dir) -> str | None`, via `load_meta_or_empty`, which never raises (`mission_metadata.py:771-779`);
   - `board_latest_transition_at(board) -> str | None`, the newest WP transition timestamp in the board snapshot the status door already returned. Investigate the `BoardStatus` shape (`src/runtime/next/` imports it; find its definition), and use the reduced WP snapshots' last-transition `at` field.

**Done when** the new unit tests pass and every existing envelope suite listed under Test Strategy passes unchanged.

## Context & Constraints

- **Read first:**
  - `plan.md` IC-01 (revised);
  - `data-model.md`;
  - `research.md` (R-2, R-5, Squad dispositions);
  - `contracts/next-envelope-additions.md`;
  - the operator rulings in `decisions/` (`plan.next.query_invariant`, `plan.next.acceptance_freshness`).
- **`runtime_bridge_cores.py` is a pure leaf.** `tests/architectural/test_bridge_cores_import_boundary.py` forbids new imports there. The verdict takes plain values: ISO timestamps as `str | None`, compared after parsing with `datetime.fromisoformat`. Put the parsing in the pure function, using only the stdlib (check that the gate allows `datetime`; it is stdlib).
- **`DecisionEnvelope.error_code` already exists** (`runtime_bridge.py:427,442` usage). Do not re-add it.
- **`Decision.remediation`** means the materialization report (#7310 WP06). Never reuse it for a command.
- **`_with_remediation`** (`runtime_bridge.py:405-409`) sets the attribute directly on the decision. Your new fields survive it. Confirm this with a test.

## Branch Strategy

- **Planning base / merge target**: `fix/7548-next-lifecycle-integrity`, via the Mission branch `kitty/mission-next-lifecycle-integrity-01M77BWP`.
- Run `spec-kitty agent action implement WP01 --agent claude --mission next-lifecycle-integrity-01M77BWP`.

## Subtasks & Detailed Guidance

### Subtask T001 – Pure `finished_board_verdict`

- Add `FinishedBoardVerdict(StrEnum)` with the members `NONE`, `AWAITING_ACCEPTANCE` and `ACCEPTED`.
- Add `FINISHED_BOARD_STEPS = frozenset({"accept", "done"})`, the step names `_finalized_task_board_override_step` returns (`runtime_bridge_decision_mapping.py:140-142`). Those steps include canceled WPs as acceptable endings, so an all-canceled board is finished.
- Add `MISSION_AWAITING_ACCEPTANCE_ERROR_CODE = "MISSION_AWAITING_ACCEPTANCE"`.
- Add `finished_board_verdict(board_step, *, accepted_at, latest_transition_at)`. It returns:
  - `NONE` if the step is not finished;
  - `ACCEPTED` iff `accepted_at` parses and is **strictly later** than `latest_transition_at`. A missing `latest_transition_at` counts as fresh. An unparsable `accepted_at` is not accepted (fail toward blocked).
  - Otherwise `AWAITING_ACCEPTANCE`.
- **Tests:** a parametrized truth table, plus the freshness cases: equal timestamps (not accepted), acceptance older than the latest transition, timezone-offset strings, and garbage input.

### Subtask T002 – Additive `next_command` and internal `suppress_step_pairing`

- `decision.py`:
  - Add the two fields.
  - `to_dict` emits `next_command` only when it is set, and **never** emits `suppress_step_pairing`.
  - Mark the flag in a comment as internal-only.
- `runtime_bridge_cores.DecisionEnvelope`: add `next_command` and `suppress_step_pairing`, and thread them through **every** `Decision(...)` construction in `step_or_blocked`, including the step → blocked degradation path.
- Grep `Decision(` and `dataclasses.replace(` across `src/runtime/next/` and `src/specify_cli/orchestrator_api/`. Confirm that no copier drops the new fields, and list any you find in your hand-off note.

### Subtask T003 – Acceptance and transition helpers

- Add `mission_accepted_at(primary_metadata_dir: Path) -> str | None` and `board_latest_transition_at(board) -> str | None` to `runtime_bridge_io.py`, using lazy imports per the layer rules (`tests/architectural/test_layer_rules.py:178-200`). `load_meta_or_empty` never raises, so write **no** dead `except`.
- **Tests** (`tmp_path`):
  - meta with and without `accepted_at`;
  - no meta file;
  - a board fixture with several transitions, where the newest one wins;
  - an empty board returns None.

### Subtask T020 – `PendingDecisionPrompt` and the construction-time invariant

- Add the value object (in `decision.py`, or the cores if it must stay import-free for the cores; place it where both the cores and `decision.py` can use it without a cycle).
- Add the `Decision.__post_init__` check for `query` and `decision_required`. Raise `InvalidStepDecision`, or a sibling `InvalidDecisionPrompt(ValueError)`, with a precise message.
- **Audit every existing construction site** of `decision_required` and `query` decisions:
  - `runtime_bridge_query.py` builders;
  - the advancing `decision_required` mapping (`runtime_bridge_decision_mapping._map_runtime_decision` and friends);
  - `answer_decision_via_runtime`;
  - the orchestrator-api.
- Run the suites listed below. If an existing builder violates the invariant, **stop and report it in your hand-off**. Do not edit files you do not own, and do not weaken the check. The planner's input decisions carry `input_key` (`_internal_runtime/planner.py:465-476`), so they satisfy "options or input_key".
- **Tests** (`tests/runtime/next/test_pending_decision_prompt.py`):
  - the value object rejects an empty id, an empty question, and both options and input_key missing;
  - `Decision(kind=query, question="q", decision_id=None)` raises;
  - `Decision(kind=query, question=None, decision_id=None)` is fine;
  - `Decision(kind=decision_required, question="q", decision_id="d", input_key="k")` is fine.

### Subtask T004 – Byte-identity regression

- Add a test that `to_dict()` without `next_command` has no such key and never has `suppress_step_pairing`, and that with `next_command` set, exactly one key is added.
- Run the existing envelope suites unchanged.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/runtime/next/test_finished_board_verdict.py tests/runtime/next/test_pending_decision_prompt.py tests/specify_cli/next/test_next_output_preservation.py tests/next/test_decision_unit.py tests/next/test_query_mode_unit.py tests/next/test_runtime_bridge_unit.py tests/contract/test_next_no_unknown_state.py tests/contract/test_next_no_implicit_success.py -q -n 4 --dist loadfile -p no:cacheprovider
.venv/bin/python -m pytest tests/runtime/next tests/specify_cli/next -q -n 4 --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_bridge_cores_import_boundary.py tests/architectural/test_inline_meta_read_gate.py tests/architectural/test_layer_rules.py -q
uv run --frozen ruff check src/runtime/next tests/runtime/next/test_finished_board_verdict.py tests/runtime/next/test_pending_decision_prompt.py
uv run --frozen ruff format --check --force-exclude src/runtime/next/runtime_bridge_cores.py src/runtime/next/decision.py src/runtime/next/runtime_bridge_io.py tests/runtime/next/test_finished_board_verdict.py tests/runtime/next/test_pending_decision_prompt.py
uv run --frozen mypy src/runtime/next/runtime_bridge_cores.py src/runtime/next/decision.py src/runtime/next/runtime_bridge_io.py
```

Record exact pass/fail counts in your hand-off note.

## Risks & Mitigations

- **The invariant breaks an existing builder.** That is the point of the check, but do not fix it out of scope. Report it so that WP03 (query) or a new hand-off covers it.
- **A missed `step_or_blocked` site.** Test both branches.

## Review Guidance

- The cores leaf stays import-free.
- `suppress_step_pairing` never appears in JSON.
- An invalid prompt cannot be constructed.
- Freshness is strict and fails closed.
- No behaviour change elsewhere.

## Activity Log

- 2026-11-12T08:30:00Z – system – Prompt created.
- 2026-11-12T09:30:00Z – claude – Revised: freshness, suppress_step_pairing, PendingDecisionPrompt (squad + operator rulings).
