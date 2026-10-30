---
work_package_id: WP01
title: Refusal authority and the emit surface
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-005
- FR-006
- FR-007
- FR-008
- FR-010
- NFR-002
- NFR-003
- NFR-005
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6754-migration-actor-cli-spoofing
merge_target_branch: issue-6754-migration-actor-cli-spoofing
branch_strategy: Planning artifacts for this mission were generated on issue-6754-migration-actor-cli-spoofing. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6754-migration-actor-cli-spoofing unless the human explicitly redirects the landing branch.
base_branch: issue-6754-migration-actor-cli-spoofing
base_commit: 7a829c3eb90dd746c1ef52cf4fdfd54a1347e457
created_at: '2026-10-30T17:54:15+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundations
history:
- at: '2026-10-30T17:54:15Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/models.py
create_intent:
- tests/status/test_caller_seed_refusal_6754.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/models.py
- src/specify_cli/status/actor.py
- src/specify_cli/status/__init__.py
- src/specify_cli/cli/commands/agent/status.py
- src/specify_cli/cli/commands/agent/tasks_move_task_hops.py
- src/specify_cli/cli/commands/agent/tasks.py
- tests/status/test_caller_seed_refusal_6754.py
- tests/status/test_status_emit_structured_actor_6400.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Refusal authority and the emit surface

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status` for a `review_ref`. Address every feedback item before your work is complete and record each change with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Resolves spec-kitty/spec-kitty#6754, first half.

- One predicate and one canonical message decide that a caller-supplied identity is seed-shaped, in `status/models.py` beside `MIGRATION_ACTOR_PREFIX` and `is_migration_actor` (FR-001, NFR-005, SC-004).
- `spec-kitty agent status emit WP01 --to claimed --actor migration:backfill` exits 1 with that message and appends nothing — the event log is byte-identical (FR-002, FR-010).
- `actor_from_option` refuses a seed-shaped value unless the caller passes `recorded=True`; the two recorded-identity call sites pass it, so a recorded seed stays a seed (FR-005, FR-006).
- Every allowed form is unchanged: an explicit `--agent migration:x` is still tool `migration` and not a seed; the three migration writers still write seeds (FR-007, FR-008).
- A matrix test module states the refused and allowed arms through their real entry points (FR-009, first half).

## Context & Constraints

- Spec: `kitty-specs/migration-actor-cli-spoofing-01M66YYX/spec.md` (FR-001, FR-002, FR-005–FR-010); plan IC-01/IC-03; research D-1…D-5; `data-model.md` for the identity taxonomy.
- Issue #6754: a `migration:` actor can be spoofed through `--actor`; seeds are exempt from the review-exit note rule (#5446), skip timestamp continuity, and never open a consolidation work window (FR-011, ADR `2026-09-29-1`).
- **Do NOT** touch `is_migration_actor`, the reducer's seed arms, `validate_timestamp_continuity` or the consolidation window rule (C-003). This WP changes what can be *written*, never how a stored row is read.
- **Do NOT** change `build_status_actor` or `parse_agent_boundary_string`: the strict compact parse is the operator's recorded 2026-10-29 ruling for `--agent` (research D-3, D-4) and `tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py::test_explicit_migration_agent_is_parsed_strictly_and_is_not_a_seed` pins it.
- **Do NOT** add an events field or change the wire shape (C-001): `spec_kitty_events`' `diary.decode_actor` accepts exactly 4 keys today.
- The three migration writers bypass the emit shell (`status._unsafe` / their own row builders) and are in the shrink-only `ALLOWED_CALLERS` allowlist, guarded by `tests/architectural/test_status_unsafe_allowlist.py`. Nothing in this WP may add an allowlist entry.
- Charter: single canonical authority (one predicate, six call sites), ATDD-first (red before green), locality of change.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-6754-migration-actor-cli-spoofing`
- **Merge target branch**: `issue-6754-migration-actor-cli-spoofing`

Execution worktrees are allocated per computed lane from `lanes.json`. Run:

```bash
spec-kitty agent action implement WP01 --agent claude --mission migration-actor-cli-spoofing-01M66YYX
```

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: invert the spoof pin, pin the builder and the allowed arms

- **Purpose**: witness the defect before fixing it, and state the allowed arms so the fix cannot over-reach.
- **Files**: `tests/status/test_status_emit_structured_actor_6400.py` (edit), `tests/status/test_caller_seed_refusal_6754.py` (new).
- **Steps**:
  1. In `test_status_emit_structured_actor_6400.py`, replace `test_migration_actor_is_stored_whole_and_stays_a_reconstruction_seed` with a refusal test: `_emit(...)` must exit 1 (note `_emit` asserts `exit_code == 0`, so invoke `runner.invoke` directly), the message must name the option and the in-process rule, and `read_events_raw(feature_dir)` must be byte-identical to before the call. Keep its `_assert_reconstruction_seed` helper only if it is still used; delete it if not (dead test helper).
  2. Create `tests/status/test_caller_seed_refusal_6754.py` (module docstring: the refusal/allowed matrix for #6754). Reuse the `mission_repo` fixture pattern from the #6400 module and `tests/_support/reconstruction_seed.py` for the behavioural seed probe.
  3. Arms to write (all `pytest.mark.fast`):
     - **Refused**: `actor_from_option("migration:x", "implementer")` raises `ValueError` with the canonical message; `actor_from_option("migration:", ...)` also raises (the prefix alone is enough).
     - **Allowed**: `actor_from_option("migration:x", role, recorded=True) == {"tool": "migration:x", "role": role, "profile": None, "model": None}`.
     - **Allowed**: `actor_from_option("claude:opus:python-pedro", role)` still parses to tool `claude`, model `opus`, profile `python-pedro` (no regression on the lenient compact path).
     - **Allowed**: a bare `"user"` / `"operator"` identity is unaffected.
  4. Run the new module on the base and record the red output (which arms fail and why) in the commit message or a `add-history` note.
- **Commit**: `test(status): a caller-supplied migration actor is refused (#6754)`, alone, before any production change (ATDD-first, C-011).

### Subtask T002 – The refusal predicate and message

- **File**: `src/specify_cli/status/models.py`.
- **Steps**:
  1. Next to `MIGRATION_ACTOR_PREFIX` / `is_migration_actor`, add:
     - `SEED_SHAPED_IDENTITY_REFUSAL` — the one message template. It must name the option passed in, say that an identity starting with `migration:` is written in-process by migrations only, cite `#6754`, and give the remedy ("pass the live identity instead"). Suggested shape: `"a caller-supplied {option} must not start with {MIGRATION_ACTOR_PREFIX!r}: reconstruction seeds are written in-process by migrations only (#6754); pass the live identity of the actor instead"`.
     - `refuse_seed_shaped_identity(value: str | None, *, option: str) -> None` — no-op for `None`; raises `ValueError` with that message when `is_migration_actor(value)` is true. Docstring: refuse, never rewrite (FR-010); mirrors `is_migration_actor` exactly, including the exact case-sensitive prefix.
  2. Do **not** reuse the name `is_migration_actor` for the predicate: the classifier and the refusal are different questions (one reads, one refuses), and the classifier must stay untouched (C-003).
  3. Export both from `src/specify_cli/status/__init__.py`: add the import in the existing alphabetical block and both names to `__all__` in the same alphabetical position (`MIGRATION_ACTOR_PREFIX`, then `SEED_SHAPED_IDENTITY_REFUSAL`, `refuse_seed_shaped_identity`, …). `tests/status/test_status_emit_structured_actor_6400.py::test_status_facade_exports_each_name_once` guards duplicates.
- **Validation**: T001's builder arms go green.

### Subtask T003 – `agent status emit --actor` refuses before any write

- **File**: `src/specify_cli/cli/commands/agent/status.py`.
- **Steps**:
  1. In `emit()`, make the refusal the **first** statement inside the `try:` block, before `locate_project_root` / `_resolve_wp_arg`: call `refuse_seed_shaped_identity(actor, option="--actor")`. The existing `except Exception` handler already renders it through `_output_error` (human text, and the machine envelope under `--json`) and exits 1 — do not add a second handler.
  2. Update `_emit_actor`'s docstring: it no longer "stores a `migration:` value whole"; a seed-shaped `--actor` never reaches it.
  3. Update the `--actor` option help so `--help` states the rule, e.g. `"Who is making this transition (a 'migration:'-prefixed identity is refused: reconstruction seeds are written in-process by migrations only)"`. Keep it one line.
- **Validation**: the emit arms of T001 go green, including "no event appended" (assert the raw log is unchanged, not just the exit code).

### Subtask T004 – `actor_from_option` fails closed; the recorded call sites opt in

- **Files**: `src/specify_cli/status/actor.py`, `src/specify_cli/cli/commands/agent/tasks_move_task_hops.py`, `src/specify_cli/cli/commands/agent/tasks.py`.
- **Steps**:
  1. `actor_from_option(actor: str, role: str, *, binding: ResolvedBinding | None = None, recorded: bool = False)`. When `recorded` is false, call `refuse_seed_shaped_identity(actor, option="--actor")` **before** the current `startswith(MIGRATION_ACTOR_PREFIX)` early return; when `recorded` is true, keep the existing whole-value behaviour. Update the docstring: the two legitimate replays opt in; every other caller fails closed (FR-005).
  2. `tasks_move_task_hops._mt_structured_actor`: the recorded branch (`else`) passes `recorded=True`, with a one-line comment saying the identity came from the log, not from `--agent`.
  3. `tasks._add_history_actor`: the recorded branch passes `recorded=True`, same comment.
  4. Leave `_mt_structured_actor`'s `st.agent` branch (`build_status_actor`) exactly as it is: an explicit `--agent` is strictly parsed and never reaches `actor_from_option`.
- **Validation**: the builder arms and the existing #6400 tests pass; `test_recorded_migration_reviewer_identity_stays_a_reconstruction_seed` stays green.

### Subtask T005 – Ratchets: `--agent` arms, recorded seeds, migration writers

- **Files**: `tests/status/test_caller_seed_refusal_6754.py` (extend).
- **Steps**:
  1. Pin the `--agent` arms: `move-task --agent migration:x` stores `{"tool": "migration", "role": "implementer", "model": "x"}` and `is_migration_actor` is False (drive it through the CLI, or reuse the harness in `tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py`; a duplicate pin here is intentional — it is the matrix).
  2. Pin the migration-writer arm without mocking it: build the seed row through `specify_cli.migration.wp_status_backfill`'s own builder (`_planned_event`/`_done_event`) and assert the actor is `migration:backfill_wp_status` and `reduces_as_reconstruction_seed(...)` is True. Record in the module docstring that the writer bypasses the emit shell (research D-2).
  3. Run the targeted suites and fix only real regressions:
     ```bash
     uv run --frozen pytest tests/status -q
     uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py tests/specify_cli/cli/commands/agent/test_status_emit.py -q
     uv run --frozen pytest tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_status_events_writes_gate.py -q
     ```
     (`tests/specify_cli/cli/commands/agent/test_status_emit.py` may be named differently — pick the module that owns `agent status emit` and run it.)
  4. `uv run --frozen ruff check` + `ruff format --check --force-exclude` on the touched files, and `uv run --frozen mypy` on the touched source modules.

## Test Strategy

```bash
uv run --frozen pytest tests/status/test_caller_seed_refusal_6754.py tests/status/test_status_emit_structured_actor_6400.py -q
uv run --frozen pytest tests/status -q
uv run --frozen pytest tests/specify_cli/cli/commands/agent/ -q
uv run --frozen pytest tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_status_events_writes_gate.py tests/architectural/test_no_dead_symbols.py -q
uv run --frozen ruff check src/specify_cli/status src/specify_cli/cli/commands/agent tests/status
uv run --frozen ruff format --check --force-exclude src/specify_cli/status tests/status
uv run --frozen mypy src/specify_cli/status/models.py src/specify_cli/status/actor.py
```

Do **not** run `make test-full`, a whole-`tests/architectural/` sweep, or any e2e/performance suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Risks & Mitigations

- **A refusal that is not total.** Assert the raw event log is byte-identical, not just the exit code.
- **Over-reach.** `actor_from_option` also serves recorded identities; if `recorded=True` is forgotten at `_mt_structured_actor` or `_add_history_actor`, the #6400 pin test fails (good) — fix the call site, not the predicate.
- **Second authority.** Do not re-implement the prefix check at the surface; call the leaf (NFR-005).
- **Name clash.** The new symbols go through the `status` facade; `test_status_facade_exports_each_name_once` and `tests/architectural/test_no_dead_symbols.py` both read `__all__`.

## Review Guidance

- Confirm the T001 commit precedes the production commits and was genuinely red on the base.
- Confirm `is_migration_actor`, the reducer and the validators are untouched (diff `src/specify_cli/status/` and look for reader-side edits — none should be there).
- Confirm the refusal message is the one authority and every surface calls it.
- Confirm `recorded=True` appears exactly twice, both on a recorded-identity branch.
- Confirm no `noqa`/`type: ignore` was added and every touched function stays at complexity ≤ 15.

## Progress & Status

Record progress with `spec-kitty agent tasks add-history WP01 --note "..."`; mark subtasks with `spec-kitty agent tasks mark-status T001 --status done`.
