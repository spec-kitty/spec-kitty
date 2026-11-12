---
work_package_id: WP01
title: 'Foundations: finished-board verdict and additive next_command'
dependencies: []
requirement_refs:
- FR-007
- NFR-002
- NFR-003
- C-001
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundations (tidy-first)
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
- tests/runtime/next/test_finished_board_verdict.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge_cores.py
- src/runtime/next/decision.py
- src/runtime/next/runtime_bridge_io.py
- tests/runtime/next/test_finished_board_verdict.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP01 – Foundations: finished-board verdict and additive next_command

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role `implementer`). Behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission next-lifecycle-integrity-01M77BWP`). Address every feedback item.

---

## Objectives & Success Criteria

These are behaviour-preserving enablers (Charter Standing Order 2, tidy-first). They give WP02 and WP03 one shared predicate, an additive envelope field and an acceptance reader:

1. A pure `finished_board_verdict(board_step, accepted)` in the cores leaf (FR-007).
2. `next_command: str | None = None` on `Decision` and `DecisionEnvelope`. It appears in `to_dict` only when set (NFR-002).
3. A fail-closed I/O helper that says whether a Mission is accepted, read through the canonical metadata loader (C-001).
4. No caller uses any of these yet. Every existing envelope stays byte-identical.

Done when the new unit tests pass and the existing envelope suites (listed under Test Strategy) pass unchanged.

## Context & Constraints

- Read first:
  - `kitty-specs/next-lifecycle-integrity-01M77BWP/plan.md` (IC-01)
  - `data-model.md` (FinishedBoardVerdict table)
  - `contracts/next-envelope-additions.md`
  - `research/code-grounding.md` §1
- `src/runtime/next/runtime_bridge_cores.py` is a **pure leaf**: `tests/architectural/test_bridge_cores_import_boundary.py` forbids new imports there. The predicate takes plain values (a `str | None` board step and a `bool`).
- `Decision.remediation` already means "what `next` materialized" (#7310 WP06). **Do not** reuse it for a command; that is why `next_command` exists.
- Metadata must be read through `specify_cli.mission_metadata.load_meta_or_empty` (or `load_meta`). A raw `json.loads` of `meta.json` trips `tests/architectural/test_inline_meta_read_gate.py`.
- `accepted_at` is sticky: nothing clears it on reopen. The helper only reports the fact. WP02 and WP03 combine it with the board verdict, so it never stands alone.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `fix/7548-next-lifecycle-integrity` (via the Mission branch `kitty/mission-next-lifecycle-integrity-01M77BWP`)
- **Merge target branch**: `fix/7548-next-lifecycle-integrity`
- Execution worktrees are allocated per computed lane from `lanes.json`. Run `spec-kitty agent action implement WP01 --agent claude --mission next-lifecycle-integrity-01M77BWP`; never hand-pick a base.

## Subtasks & Detailed Guidance

### Subtask T001 – Pure `finished_board_verdict`

- **Purpose**: One predicate for "is the board finished, and is the Mission accepted?" that advance (WP02) and query (WP03) both call, so the two modes cannot drift again (FR-007).
- **Steps**:
  1. In `runtime_bridge_cores.py` add a `StrEnum` (or `str, Enum`) `FinishedBoardVerdict` with members `NONE = "none"`, `AWAITING_ACCEPTANCE = "awaiting_acceptance"` and `ACCEPTED = "accepted"`.
  2. Add `def finished_board_verdict(board_step: str | None, *, accepted: bool) -> FinishedBoardVerdict`. It returns:
     - `NONE` unless `board_step in ("accept", "done")`;
     - otherwise `ACCEPTED` if `accepted`, else `AWAITING_ACCEPTANCE`.
     - The `"accept"` / `"done"` literals are the step names `_finalized_task_board_override_step` returns (`runtime_bridge_decision_mapping.py:140-142`). Define a module constant `FINISHED_BOARD_STEPS = frozenset({"accept", "done"})` and use it.
  3. Add `MISSION_AWAITING_ACCEPTANCE_ERROR_CODE = "MISSION_AWAITING_ACCEPTANCE"` beside it (WP02 uses it).
  4. Docstring: cite #7553 / #5929 / #7565, and the invariant that acceptance never counts unless the board is finished.
  5. Add the new public names to the module's `__all__` if it declares one. Check the module. If `test_no_dead_symbols` walks it, WP02/WP03 will supply the callers; keep the names private-prefixed if the gate would fail before then.
- **Files**: `src/runtime/next/runtime_bridge_cores.py`; test `tests/runtime/next/test_finished_board_verdict.py` (new).
- **Tests**: a parametrized truth table over `{None, "implement", "review", "blocked:no_actionable_wp", "accept", "done"} × {True, False}`.

### Subtask T002 – Additive `next_command`

- **Purpose**: A place to name the next CLI command (FR-001, FR-008).
- **Steps**:
  1. `src/runtime/next/decision.py`: add `next_command: str | None = None` to `Decision`, after `remediation`, with a comment citing FR-001/FR-008 and the additive-only rule.
  2. In `Decision.to_dict`, emit `payload["next_command"]` **only when not None**, as `error_code` and `remediation` already do.
  3. In `runtime_bridge_cores.DecisionEnvelope`, add the same field (default None), and have `step_or_blocked` pass it to every `Decision(...)` it constructs. Search that function for each construction site, including the step → blocked degradation path.
  4. Check whether any other builder copies Decision fields field-by-field (e.g. `_with_remediation` in `runtime_bridge.py`, which uses `dataclasses.replace`). Those are fine. Grep `Decision(` across `src/runtime/next/` and confirm nothing reconstructs a Decision and drops unknown fields. Report any you find to WP02/WP03 in your hand-off note rather than editing files you do not own.
- **Files**: `decision.py`, `runtime_bridge_cores.py`.

### Subtask T003 – `mission_is_accepted`

- **Purpose**: Read acceptance in one place (C-001).
- **Steps**:
  1. In `runtime_bridge_io.py` add `def mission_is_accepted(primary_metadata_dir: Path) -> bool`. It returns `bool(load_meta_or_empty(primary_metadata_dir).get("accepted_at"))`.
  2. Make it fail-closed: any metadata read error returns `False`. That fails toward `blocked`, never toward a wrong `terminal`. Check how `load_meta_or_empty` behaves on a corrupt file (`src/specify_cli/mission_metadata.py:771`) and catch only what it can raise (e.g. `MissionMetaReadError`); never use a bare `except Exception` without a reason comment.
  3. Import lazily inside the function if module-level imports from `specify_cli` are not already present there (check the layer rules: `mission_metadata` is in `_RUNTIME_ALLOWED_SPECIFY_CLI`, `tests/architectural/test_layer_rules.py:178-200`).
- **Tests** (in the new test file, using `tmp_path`):
  - meta with `accepted_at` → True;
  - meta without it → False;
  - no meta file → False;
  - corrupt meta → False.

### Subtask T004 – Byte-identity regression

- **Purpose**: Prove nothing changed for existing callers (NFR-002).
- **Steps**:
  1. Add a test asserting that `Decision(...).to_dict()` without `next_command` has no `next_command` key, and with it set has exactly that key added.
  2. Run the existing envelope suites listed below and confirm they pass unchanged.

## Test Strategy

Red-first does not apply to pure enablers: the new behaviour is unused. Tests pin the predicate and the additivity.

```bash
.venv/bin/python -m pytest tests/runtime/next/test_finished_board_verdict.py tests/specify_cli/next/test_next_output_preservation.py tests/next/test_decision_unit.py tests/contract/test_next_no_unknown_state.py tests/architectural/test_bridge_cores_import_boundary.py tests/architectural/test_inline_meta_read_gate.py tests/architectural/test_layer_rules.py -q -p no:cacheprovider
uv run --frozen ruff check src/runtime/next tests/runtime/next/test_finished_board_verdict.py
uv run --frozen ruff format --check --force-exclude src/runtime/next/runtime_bridge_cores.py src/runtime/next/decision.py src/runtime/next/runtime_bridge_io.py tests/runtime/next/test_finished_board_verdict.py
uv run --frozen mypy src/runtime/next/runtime_bridge_cores.py src/runtime/next/decision.py src/runtime/next/runtime_bridge_io.py
```

Record exact pass/fail counts in your hand-off note.

## Risks & Mitigations

- **Dead-symbol gate on unused new names.** Check `tests/architectural/test_no_dead_symbols.py` scope (it covers `src/charter/` and `src/kernel/` only, per the charter). `runtime` should be out of scope; verify.
- **A missed `step_or_blocked` construction site** would drop `next_command`. Cover both the step and blocked branches in a test.

## Review Guidance

- Is the cores leaf still import-free (gate green)?
- Is `next_command` absent from every payload that does not set it?
- Does `mission_is_accepted` use the canonical loader and fail closed?
- Is there no behaviour change anywhere?

## Activity Log

- 2026-11-12T08:30:00Z – system – Prompt created.
