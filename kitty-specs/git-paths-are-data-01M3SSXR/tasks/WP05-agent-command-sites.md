---
work_package_id: WP05
title: agent command call sites
dependencies:
- WP01
requirement_refs:
- FR-008
- NFR-001
planning_base_branch: claude/git-path-remediation-rnrzfz
merge_target_branch: claude/git-path-remediation-rnrzfz
branch_strategy: Planning artifacts for this mission were generated on claude/git-path-remediation-rnrzfz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/git-path-remediation-rnrzfz unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-git-paths-are-data-01M3SSXR
base_commit: b99f6f41b251862ea70c120c90299665579178ab
created_at: '2026-09-30T19:38:50.339235+00:00'
subtasks:
- T021
- T022
- T023
- T024
- T025
phase: Phase 2 - Migration
history:
- at: '2026-09-30T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_agent_git_paths.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
- src/specify_cli/cli/commands/agent/tasks_mark_status.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/cli/commands/agent/mission_record_analysis.py
- src/specify_cli/cli/commands/agent/mission_repair.py
- src/specify_cli/cli/commands/agent/workflow.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/cli/commands/agent/tasks_shared.py
- src/specify_cli/cli/commands/agent/tasks.py
- src/specify_cli/review/dirty_classifier.py
- tests/specify_cli/cli/commands/agent/test_agent_git_paths.py
- tests/integration/test_dossier_snapshot_no_self_block.py
- tests/integration/review/test_approve_without_force.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP05 – agent command call sites

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission git-paths-are-data-01M3SSXR`).
- Address every feedback item before handing back.

---

## Objectives & Success Criteria

- All path-listing git calls in the owned agent command modules use `kernel.git` (base census: `tasks_move_task` ~917/1493 + ~688 `.strip('"')` half-decoder; `tasks_parsing_validation` ~320/555 + ~353 split; `tasks_mark_status` ~566; `mission_finalize` ~2653/3572; `mission_setup_plan` ~106; `mission_record_analysis` ~83; `mission_repair` ~145; `workflow` ~797; `workflow_executor` ~1198).
- `tasks_move_task._lane_deliverable_paths` returns real paths for non-ASCII and spaced deliverables (today they are dropped or mangled).
- The whole-stdout `.strip()` leading-space hazard (`mission_finalize:~2653`, `tasks_parsing_validation:~555`) is gone.

## Context & Constraints

- Spec: `kitty-specs/git-paths-are-data-01M3SSXR/spec.md`; plan: `plan.md` (Design §1–10); API contract: `contracts/kernel-git-api.md`; data model: `data-model.md`; research: `research.md` (R1–R9).
- Charter: `.kittify/charter/charter.md` — campsite first (standing order 2), red-first (4), gate discipline (5), no heavy suites in mission (run targeted tests + the named gate files only).
- CLAUDE.md code style: ruff, `ruff format --check`, mypy zero issues on changed files; complexity ≤ 15; no new `# noqa` / `# type: ignore`.
- **C-007**: never move a destructive git command (`reset --hard`, `update-ref`, `worktree remove`, `stash`, `clean`) into `kernel.git`; only path *listings* move.
- **FR-013**: when a site today treats git failure as "no paths" (`check=False` then parse stdout, or a helper returning `()`/`None`), decide: a guard (it protects data or gates a transition) lets `GitCommandError` propagate; an advisory/display site catches `GitCommandError` at the call site with a one-line comment giving the reason. Record every decision in the tracer `kitty-specs/git-paths-are-data-01M3SSXR/research/design-decisions.md` (orchestrator appends; list them in your hand-off).
- **Boolean dirtiness** (`bool(stdout.strip())`) becomes `bool(status_entries(...))`; keep the same `untracked`/`ignored` options and pathspecs as the original argv.
- **Paths**: callers that need `str` use `str(entry.path)` / `p.as_posix()`; never re-parse a rendered line.
- Tests: use real temporary git repos (no git mocks) for at least one quoted-path case per migrated guard. Put new test files where listed in `owned_files`; small edits to existing tests of the migrated module are allowed with a one-line rationale in the hand-off.

## Branch Strategy

- **Strategy**: lanes (one worktree per computed lane from `lanes.json`)
- **Planning base branch**: `claude/git-path-remediation-rnrzfz`
- **Merge target branch**: `claude/git-path-remediation-rnrzfz`

> Populated by `spec-kitty agent mission finalize-tasks`. Enter the workspace with `spec-kitty implement WP05 --mission git-paths-are-data-01M3SSXR`; never reconstruct the path.

## Subtasks & Detailed Guidance

### Subtask T021 – `tasks_move_task.py`

- Replace both status probes and the `_lane_deliverable_paths` parser (`.strip('"')`) with `status_entries`; include `orig_path` where a rename matters today.
- Keep each function's return type.

### Subtask T022 – `tasks_parsing_validation.py`, `tasks_mark_status.py`

- Dirty probes → `status_entries` with the same pathspecs/untracked flags; any `line[3:]` slicing → `entry.path`.

### Subtask T023 – mission_* commands

- `mission_finalize.py` (`--no-optional-locks status --porcelain=v1 --untracked-files=all` at ~2653: pass `--no-optional-locks`? The kernel runner is command-agnostic: add an `optional_locks: bool = True` keyword to `status_entries` ONLY if needed to preserve behaviour — coordinate by noting it in the hand-off; WP01 owns kernel, so if you need it, implement the keyword in `src/kernel/git/listing.py` as a small out-of-map edit with a one-line rationale and a test in `tests/kernel/test_git_listing.py`).
- `mission_setup_plan`, `mission_record_analysis`, `mission_repair`: boolean dirtiness → `bool(status_entries(...))`.

### Subtask T024 – workflow commands

- `workflow.py` ~797, `workflow_executor.py` ~1198 → `status_entries`.

### Subtask T025 – tests

- `test_agent_git_paths.py`: real-git cases for `_lane_deliverable_paths` with `é/x.md` and `a b/y.md`; one boolean-dirtiness case per changed module where cheap. Existing tests that mocked `subprocess.run` for these probes: update the mock target to the kernel query (or better, use a real repo) — list every edited existing test in the hand-off.

## Test Strategy

- New file + the existing tests that import each changed module (`rg -l "tasks_move_task|tasks_parsing_validation|tasks_mark_status|mission_finalize|mission_setup_plan|mission_record_analysis|mission_repair|agent.workflow|workflow_executor" tests`), run with `-m "not slow"` where the file set is large.

Always also run: `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check <changed files>`, `uv run --frozen mypy <changed src files>`, and `make test-fast` is NOT required per WP (the orchestrator runs it at closeout).

## Risks & Mitigations

- These are god-modules; keep edits local to the listing call and its parser.
- Tests often monkeypatch `subprocess.run`; a migrated site no longer calls it directly — patch `kernel.git.runner` or use real git.

## Additional sites (post-tasks squad)

- `cli/commands/agent/tasks_shared.py` `_filter_runtime_state_paths(porcelain_output: str)` slices `line[3:]`; its callers are `tasks_move_task.py` (~929, ~1503). Change it to take `Iterable[StatusEntry]` and update the re-export in `tasks.py` (~295).
- `review/dirty_classifier.py` (~169) rejects any path containing `" -> "`; with typed entries that guard is wrong for a file literally named `a -> b`. Drop it and add a test for such a file.
- `tests/integration/test_dossier_snapshot_no_self_block.py` and `tests/integration/review/test_approve_without_force.py` pin the old string shape; update them in place (one-line rationale in the hand-off).
- The kernel contract is WP01's; if a query is missing, stop and ask the orchestrator rather than editing `src/kernel/git/`.

## Review Guidance

- `census(owned_files)` from `tests/architectural/_git_path_listing_census.py` reports 0 hits for this WP's `src/` files.
- No listing literal / porcelain slicing left in owned files.
- `_lane_deliverable_paths` non-ASCII case covered.
- Confirm ruff, format and mypy ran on changed files and were clean.
- Confirm no destructive git literal moved into `src/kernel/git/` (C-007).

## Activity Log

- 2026-09-30T19:20:00Z – system – Prompt created.
