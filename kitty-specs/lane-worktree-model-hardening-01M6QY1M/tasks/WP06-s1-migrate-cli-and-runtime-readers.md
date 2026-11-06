---
work_package_id: WP06
title: S1 migrate status, CLI and mission_runtime readers onto the door
dependencies:
- WP05
requirement_refs:
- FR-005
- FR-043
- SC-001
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
- T034
- T035
phase: Phase 2 - S1 one status read contract
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_status_readers_cross_cwd_parity.py
- tests/specify_cli/cli/commands/agent/test_agent_status_materialize_read_only.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/aggregate.py
- src/specify_cli/cli/commands/agent/status.py
- src/specify_cli/cli/commands/events.py
- src/specify_cli/cli/commands/retrospect.py
- src/specify_cli/cli/commands/agent_retrospect.py
- src/specify_cli/retrospective/gate.py
- src/specify_cli/cli/commands/agent/tasks_shared.py
- src/specify_cli/cli/commands/agent/tasks_mark_status.py
- src/specify_cli/cli/commands/implement_claim.py
- src/specify_cli/cli/commands/implement_phases.py
- src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py
- src/specify_cli/cli/commands/accept.py
- src/specify_cli/cli/commands/agent/issue_verdict.py
- src/specify_cli/task_utils/support.py
- src/specify_cli/migration/wp_status_backfill.py
- src/specify_cli/migration/backfill_runtime_state.py
- src/mission_runtime/resolution.py
- tests/status/test_status_readers_cross_cwd_parity.py
- tests/specify_cli/cli/commands/agent/test_agent_status_materialize_read_only.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 - S1 migrate status, CLI and mission_runtime readers onto the door

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP06 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP06 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

Move every status reader in `status/`, the CLI command modules and `mission_runtime` onto the WP05 door (FR-005, FR-043). SC-001: for one Mission, every status-reading command (`agent tasks status`, `next`, `accept`, `implement`, `retrospect`, `events`, `issue-verdict`) reports identical WP states in each coordination state (worktree present, empty, absent) from each working directory (repository root checkout, lane checkout, coordination worktree): **0 divergent cells**.

Also: `agent status` materialization never writes to a read-only path (a ref-sourced surface has no writable path; `materialize` moves to the write dir).

## Context & Constraints

- Read: WP05's `src/specify_cli/status/read_surface.py`; WP01 ADR; `research.md` R-1; spec FR-005, SC-001; `plan.md` IC-06.
- Scale: about 25 direct resolver calls in 18 files plus 25 `read_dir(STATUS_STATE)` calls repo-wide (AST count, brief A). This WP takes the CLI/status/runtime share; WP07 takes consolidation and adds the gate. Use an AST lister (not grep: docstrings and imports inflate counts) to enumerate your call sites first and list them in your summary.
- `src/mission_runtime/resolution.py`: you own it now. Change only `_resolve_status_surface_dir*` and the `STATUS_STATE` `read_dir` arm. `mission_runtime` cannot import `specify_cli`: if the door is needed there, inject it through the existing resolver port (`mission_resolver_port.py`) rather than importing. WP14 later adds the provisional arm of `single_branch_write_ref` (out-of-map, sequenced after you).
- `mission_finalize_planning_pin.py`: only line ~70. **#7255 (NOT merged)** also edits this file; keep your hunk minimal and rebase when it lands.
- `accept.py`: only `_coord_status_feature_dir`.
- `implement_phases.py`: WP04 already renamed the alias; here migrate the `claim_preflight` call.
- C-011 red-first.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T030 - Red-first parity matrix

- `tests/status/test_status_readers_cross_cwd_parity.py::test_status_readers_agree_across_cwd_and_coord_state`: build a `lanes_with_coord` Mission with three committed coordination events, a stale repository-root copy and a stale lane copy (spec User Story 1 Independent Test). For each coordination state x cwd, invoke each reader through its real entry point (CLI via `CliRunner` or subprocess, Python entries for internal readers) and compare reduced WP lanes. Assert 0 divergent cells; on failure print the matrix.
- `tests/specify_cli/cli/commands/agent/test_agent_status_materialize_read_only.py::test_agent_status_materialize_never_writes_read_only_path`: with the coordination worktree absent, `agent status` (materialize path) writes nothing under any lane checkout or under the repository root's stale copy.
- Commit red.

### Subtask T031 - `status/aggregate.py`

- `MissionStatus` holds a `StatusReadSurface` instead of a bare dir; `load` goes through `resolve_status_read`; `materialize` writes only to the write dir (`WRITE_CHECKOUT` / `COORD_WORKTREE` path) and is a no-op or typed refusal for `COORD_BRANCH_REF` (decide, document in the docstring).

### Subtask T032 - Migrate status / events / retrospect readers [P]

- `cli/commands/agent/status.py` (incl. its own `_resolve_status_surface` at ~139: rename or remove; it must not survive under that clashing name), `cli/commands/events.py`, `cli/commands/retrospect.py`, `cli/commands/agent_retrospect.py`, `retrospective/gate.py`.

### Subtask T033 - Migrate tasks / implement / accept readers [P]

- `agent/tasks_shared.py`, `agent/tasks_mark_status.py`, `implement_claim.py`, `implement_phases.py` (`claim_preflight` call), `agent/mission_finalize_planning_pin.py:70`, `accept.py` (`_coord_status_feature_dir`), `agent/issue_verdict.py`.

### Subtask T034 - Migrate support / migration / runtime readers

- `task_utils/support.py`, `migration/wp_status_backfill.py`, `migration/backfill_runtime_state.py`, `mission_runtime/resolution.py` (`_resolve_status_surface_dir*`, `STATUS_STATE` `read_dir` arm).
- Remove retired names once their last caller is gone (FR-005 "with the retired names removed"); if a name is still used by consolidation, leave it for WP07 and say so.

### Subtask T035 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/status/test_status_readers_cross_cwd_parity.py tests/specify_cli/cli/commands/agent/test_agent_status_materialize_read_only.py -q
uv run --frozen pytest tests/status tests/specify_cli/status tests/mission_runtime tests/migration tests/retrospective tests/next tests/runtime -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -n auto --dist loadfile      # out-of-matrix (nightly-only in CI): must run here
uv run --frozen pytest tests/architectural/test_no_read_side_bypass.py tests/architectural/test_layer_rules.py tests/architectural/test_cold_import_status_boundary.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict <touched src files>
```

Complexity <= 15; no new suppressions; never `make test-full` or a bare `tests/architectural/` sweep. `tests/specify_cli/cli/commands` is out of the CI matrix (`.github/ci-module-registry.yml`): a red there may be real on `main`; check the latest nightly before attributing.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP06] ...**`, naming the target trace file); the orchestrator appends them.

## Risks & Mitigations

- Missed call site: the WP07 gate catches it later; list your AST census in the summary so WP07 can freeze the floor.
- Output shape drift: CLI JSON shapes must not change (contracts/README "Internal-only").

## Review Guidance

- Parity matrix 0 divergent cells; materialize never writes a read-only path; census of migrated call sites provided; no `specify_cli` import added to `mission_runtime`.

## Definition of Done

- T030-T035 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T030 T031 T032 T033 T034 T035 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP06 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
