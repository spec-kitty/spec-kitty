---
work_package_id: WP01
title: Worktree porcelain parser (tidy-first)
dependencies: []
requirement_refs:
- C-003
- FR-001
- FR-012
planning_base_branch: issue-7173-landed-worktree-cleanup
merge_target_branch: issue-7173-landed-worktree-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-7173-landed-worktree-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7173-landed-worktree-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-landed-worktree-cleanup-01M6KZNP
base_commit: 5e094f9b1c3504f46fd384eb8351910cff968447
created_at: '2026-11-04T23:49:06.328315+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 0 - Tidy-first foundation
history:
- at: '2026-11-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/git/
create_intent:
- tests/kernel/git/test_worktree_listing.py
execution_mode: code_change
owned_files:
- src/kernel/git/listing.py
- src/specify_cli/status/doctor_husks.py
- tests/kernel/git/test_worktree_listing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Worktree porcelain parser (tidy-first)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before your work is complete; record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

- A pure, tested parser for `git worktree list --porcelain` lives in `src/kernel/git/listing.py`.
- `specify_cli.status.doctor_husks.registered_worktree_paths` uses it; its behaviour (paths set, error string) is byte-for-byte unchanged.
- This is a **behaviour-preserving** preparatory commit (charter: tidy-first). No new caller other than the reroute.

## Context & Constraints

- Mission: `kitty-specs/landed-worktree-cleanup-01M6KZNP/` (spec.md, plan.md IC-01, data-model.md `WorktreeEntry`).
- Layering: `kernel` is the root layer; it must import nothing from `specify_cli` / `charter`. Follow the style of the existing parsers in `listing.py` (`parse_status_z`, frozen dataclasses, `_git` runner).
- About ten other modules hand-roll this parse (`git/destructive_guard.py:452`, `git/ref_advance.py:332`, `lanes/recovery.py:168`, …). Do **not** migrate them in this WP (scope); they are a campsite note for later.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `issue-7173-landed-worktree-cleanup`
- **Merge target branch**: `issue-7173-landed-worktree-cleanup`

Execution worktrees are allocated per computed lane from `lanes.json`; run `spec-kitty agent action implement WP01 --agent claude --mission landed-worktree-cleanup-01M6KZNP` and work in the workspace it prints.

## Subtasks & Detailed Guidance

### Subtask T001 – `WorktreeEntry` and `parse_worktree_porcelain`

- **Purpose**: Typed view of one porcelain record.
- **Steps**:
  1. Add a frozen dataclass:
     ```python
     @dataclass(frozen=True)
     class WorktreeEntry:
         path: Path
         head: str | None       # None for a bare entry
         branch: str | None     # short name ("refs/heads/" stripped); None when detached or bare
         detached: bool
         bare: bool
         locked: bool
         prunable: bool
     ```
  2. `parse_worktree_porcelain(text: str) -> tuple[WorktreeEntry, ...]`: records are separated by blank lines; lines: `worktree <path>`, `HEAD <sha>`, `branch refs/heads/<name>`, `detached`, `bare`, `locked[ <reason>]`, `prunable[ <reason>]`. Unknown lines are ignored (forward compatible). A record without a `worktree` line is skipped.
  3. Keep ordering as git reports it; the first entry is the main worktree (document this in the docstring).
- **Notes**: Paths may contain spaces; take everything after the first space. Do not `resolve()` paths in the kernel parser (callers decide).

### Subtask T002 – `worktree_entries(cwd, *, env=None, timeout=None)`

- **Purpose**: Runner over the parser, mirroring `status_entries`.
- **Steps**: run `git worktree list --porcelain` via the module's `_git` helper; raise the module's existing error type on non-zero exit (check how `status_entries` reports failure and match it).
- **Notes**: No `-z`: porcelain without `-z` is fine for this record format but document that a path containing a newline is not supported (git itself quotes nothing here).

### Subtask T003 – Reroute `registered_worktree_paths`

- **Purpose**: First real consumer; proves the parser is a drop-in.
- **Steps**: in `src/specify_cli/status/doctor_husks.py`, keep the function signature and its `RegisteredWorktreePaths(error=...)` message for a failed command **exactly** as today. Replace only the line-scanning loop with `parse_worktree_porcelain(result.stdout)` and keep the existing `resolve()`/error handling of each path.
- **Notes**: Keep the subprocess call as it is (same encoding/`errors="replace"`) so the error string is unchanged; only the parse moves.

### Subtask T004 – Tests

- **Files**: `tests/kernel/git/test_worktree_listing.py` (new).
- **Cases**: main + linked worktree with branch; detached; bare; locked with and without reason; prunable; path with spaces; unknown line ignored; empty input → `()`. One integration test building a real repo with `git worktree add` (branch, `--detach`, then `git worktree lock`) and asserting `worktree_entries` output.
- Run unchanged: `tests/status/test_doctor_husks.py`, `tests/specify_cli/cli/commands/test_workspace_husk_doctor.py`, `tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py`.

## Test Strategy

```bash
uv run --frozen pytest tests/kernel/git/test_worktree_listing.py tests/status/test_doctor_husks.py tests/specify_cli/cli/commands/test_workspace_husk_doctor.py tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py -q
uv run --frozen ruff check src/kernel/git/listing.py src/specify_cli/status/doctor_husks.py tests/kernel/git/test_worktree_listing.py
uv run --frozen ruff format --check --force-exclude src/kernel/git/listing.py src/specify_cli/status/doctor_husks.py tests/kernel/git/test_worktree_listing.py
uv run --frozen mypy src/kernel/git/listing.py src/specify_cli/status/doctor_husks.py
uv run --frozen pytest tests/architectural/test_layer_rules.py -q
```

## Risks & Mitigations

- Kernel import direction: the layer-rules gate catches any `specify_cli` import.
- Hidden behaviour change in husk detection: the three husk test files must pass unchanged.

## Review Guidance

- Confirm the reroute is behaviour-preserving (diff of `doctor_husks.py` is the loop only).
- Confirm no other module was migrated (scope).
- Confirm mypy and ruff format ran on touched files.

## Progress & Status

Record notes with `spec-kitty agent tasks add-history WP01 --note "..."`; move status with `spec-kitty agent tasks move-task WP01 --to <status>`.
