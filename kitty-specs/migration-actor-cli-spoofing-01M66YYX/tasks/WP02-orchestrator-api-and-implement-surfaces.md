---
work_package_id: WP02
title: Orchestrator-api and implement surfaces
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-009
- NFR-001
- SC-001
planning_base_branch: issue-6754-migration-actor-cli-spoofing
merge_target_branch: issue-6754-migration-actor-cli-spoofing
branch_strategy: Planning artifacts for this mission were generated on issue-6754-migration-actor-cli-spoofing. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6754-migration-actor-cli-spoofing unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-migration-actor-cli-spoofing-01M66YYX
base_commit: 0859946639fdbee90d8b695c55a3c690dd504992
created_at: '2026-10-30T19:00:08.303601+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Surfaces
history:
- at: '2026-10-30T17:54:15Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/orchestrator_api/wp_lifecycle.py
create_intent:
- tests/specify_cli/orchestrator_api/test_caller_seed_refusal_6754.py
- tests/specify_cli/cli/commands/test_implement_caller_seed_refusal_6754.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/orchestrator_api/wp_lifecycle.py
- src/specify_cli/cli/commands/implement.py
- tests/specify_cli/orchestrator_api/test_caller_seed_refusal_6754.py
- tests/specify_cli/cli/commands/test_implement_caller_seed_refusal_6754.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Orchestrator-api and implement surfaces

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`. Address every feedback item before your work is complete and record each change with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Resolves spec-kitty/spec-kitty#6754, second half — the two remaining surfaces that record a caller-supplied identity verbatim.

- `orchestrator-api start-implementation`, `start-review`, `transition` and `append-history` refuse a seed-shaped `--actor` with `error_code: USAGE_ERROR`, exit 1, and no state change (FR-003, SC-001).
- `spec-kitty implement WP01 --mission <slug> --actor migration:x` (the hidden compatibility option) exits 1 with the same refusal **before** any workspace allocation or claim (FR-004).
- 0 events appended, 0 snapshots materialized, 0 worktrees created on every refused arm (NFR-001).
- The two new test modules complete the refusal/allowed matrix started in WP01 (FR-009).

## Context & Constraints

- Spec: `kitty-specs/migration-actor-cli-spoofing-01M66YYX/spec.md` (FR-003, FR-004, NFR-001); plan IC-02; research D-3.
- WP01 owns the predicate: `specify_cli.status.refuse_seed_shaped_identity(value, option=...)` (raised `ValueError`, one canonical message). **Call it; do not re-implement the prefix check.**
- **Reuse `USAGE_ERROR`.** It is already in `src/specify_cli/core/upstream_contract.json`'s `allowed_error_codes`, and `wp_lifecycle.py` already uses it for an invalid `--evidence-json`. Adding a new code would be an orchestrator-api contract change and is out of scope (research D-4).
- The orchestrator-api writes go through `start_implementation_status` / `start_review_status` / `emit_status_transition_transactional` / `emit_inner_state_changed`; the refusal must sit before the first of those, and before `_resolve_start_workspace` (which allocates or self-heals a lane workspace) — not merely before the emit.
- `implement` is a compatibility surface (its docstring says so); its `--actor` is `hidden=True` for programmatic callers and reaches `implement_phases.record_claim` as a bare string today, which is why it can seed. Guard it beside the existing `--mission` no-selector guard at the top of the body, before `detect_context`.
- Charter: no new append path (C-002); the refusal removes ways to write; keep the envelope shapes each command already emits.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6754-migration-actor-cli-spoofing`
- **Merge target branch**: `issue-6754-migration-actor-cli-spoofing`

Execution worktrees are allocated per computed lane from `lanes.json`. Run:

```bash
spec-kitty agent action implement WP02 --agent claude --mission migration-actor-cli-spoofing-01M66YYX
```

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first: the four orchestrator-api verbs

- **File**: `tests/specify_cli/orchestrator_api/test_caller_seed_refusal_6754.py` (new).
- **Steps**:
  1. Drive each verb through the real Typer app (see `tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py` / `test_transition_subtask_gate.py` for the invocation pattern; `CliRunner().invoke(app, [...])`).
  2. For each of `start-implementation`, `start-review`, `transition`, `append-history`: invoke with `--actor migration:backfill` (plus whatever that verb otherwise requires, e.g. `--policy`, `--wp`, `--to`) and assert exit 1, `success: false`, `error_code: "USAGE_ERROR"`, and the canonical message.
  3. Assert the refusal precedes resolution/write: on a real fixture Mission (`tests/utils._seed_canonical_wp_state` or the `_build_mission` helper in `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`), capture `status.events.jsonl` before the call and assert it is byte-identical after.
  4. Record the red output on the base before T007.
- **Commit**: `test(orchestrator-api): refuse a caller-supplied migration actor (#6754)`, alone.

### Subtask T007 – Refuse in the four lifecycle verbs

- **File**: `src/specify_cli/orchestrator_api/wp_lifecycle.py`.
- **Steps**:
  1. Add one small helper next to the other refusals in the module (there is already a `_fail`-based refusal style):
     ```python
     def _refuse_seed_actor_or_fail(cmd: str, actor: str) -> None:
         """Refuse a caller-supplied reconstruction-seed identity before any work (#6754)."""
         try:
             refuse_seed_shaped_identity(actor, option="--actor")
         except ValueError as exc:
             _fail(cmd, "USAGE_ERROR", str(exc))
     ```
     `_fail` is typed `NoReturn`, so no caller needs a sentinel.
  2. Call it as the **first** statement of the four command bodies: `start_implementation` (before `_get_main_repo_root`/policy parsing), `start_review`, `transition`, and the append-history command. Use each command's own `cmd` id so the envelope names the endpoint.
  3. Update the module docstring only if it enumerates the refusals (one line, same style).
- **Validation**: T006 goes green; the existing orchestrator-api suites stay green.

### Subtask T008 – Red-first: the hidden `implement --actor`

- **File**: `tests/specify_cli/cli/commands/test_implement_caller_seed_refusal_6754.py` (new).
- **Steps**:
  1. Reuse the existing implement harness (`tests/specify_cli/cli/commands/_implement_fixtures.py`, used by `test_implement.py`) to build a Mission with one planned WP.
  2. Invoke `spec-kitty implement WP01 --mission <slug> --actor migration:x` through the Typer app; assert exit 1, the canonical message, no claim event appended, and that the lane worktree does not exist (use the fixture's worktree root).
  3. Also assert the ordinary path still works: `implement WP01 --mission <slug>` (no `--actor`) reaches its normal outcome on the same fixture, so the guard is not simply refusing everything.
  4. Record the red output on the base before T009.
- **Commit**: `test(implement): refuse a caller-supplied migration actor (#6754)`, alone.

### Subtask T009 – Guard the hidden `--actor`

- **File**: `src/specify_cli/cli/commands/implement.py`.
- **Steps**:
  1. Immediately after the existing `--mission` no-selector guard (and before `recover`/`detect_context`), add:
     ```python
     if actor is not None:
         try:
             refuse_seed_shaped_identity(actor, option="--actor")
         except ValueError as exc:
             if json_output:
                 console.print(json.dumps({"error": str(exc)}))
             else:
                 console.print(f"[red]Error:[/red] {exc}")
             raise typer.Exit(1) from exc
     ```
     Match the module's existing error style (check whether it imports `json`; adjust if not).
  2. Update the option's help text only if it claims the value is unvalidated.
- **Validation**: T008 goes green.

### Subtask T010 – Blast-radius sweep

- **Steps**: run and record (fix only real regressions):
  ```bash
  uv run --frozen pytest tests/specify_cli/orchestrator_api -q
  uv run --frozen pytest tests/contract/test_orchestrator_api.py -q
  uv run --frozen pytest tests/specify_cli/cli/commands/test_implement.py tests/specify_cli/cli/commands/test_implement_claim.py tests/specify_cli/cli/commands/test_implement_characterization.py -q
  uv run --frozen ruff check src/specify_cli/orchestrator_api src/specify_cli/cli/commands/implement.py tests/specify_cli/orchestrator_api tests/specify_cli/cli/commands
  uv run --frozen mypy src/specify_cli/orchestrator_api/wp_lifecycle.py src/specify_cli/cli/commands/implement.py
  ```
  Watch the outbound contract gate (`tests/specify_cli/core/test_contract_gate.py`, `tests/contract/`): the refusal must pass `validate_outbound_payload` with `USAGE_ERROR`, unchanged.
- **Note**: if the implement fixture is expensive, run only the three implement modules above and the orchestrator-api directory; never the whole `tests/` tree.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/orchestrator_api/test_caller_seed_refusal_6754.py tests/specify_cli/cli/commands/test_implement_caller_seed_refusal_6754.py -q
uv run --frozen pytest tests/specify_cli/orchestrator_api -q
uv run --frozen pytest tests/contract/test_orchestrator_api.py tests/specify_cli/core/test_contract_gate.py -q
```

## Risks & Mitigations

- **Guard too late.** Placing it after policy parsing is fine (read-only), but after `_resolve_start_workspace` or `record_claim` is not: it would leave a lane worktree behind and break NFR-001. Put it at the top.
- **`_fail` return typing.** It is `NoReturn`; do not add `return` after it (mypy would flag unreachable code).
- **Envelope shape.** Keep `command`, `success`, `error_code`, `data.message` exactly as `make_envelope` builds them.
- **Fixture realism.** A test that refuses before mission resolution proves ordering but not the write-free property; assert the log and worktree too.

## Review Guidance

- Confirm each refusal is the first statement in its command body and precedes allocation, lock and emit.
- Confirm the predicate and message are imported from `specify_cli.status`, with no local prefix check.
- Confirm no contract artefact or `allowed_error_codes` entry changed.
- Confirm the ordinary (non-seed) paths still pass on the same fixtures.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP02 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T006 --status done`.
