---
work_package_id: WP06
title: other CLI command call sites
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
created_at: '2026-09-30T19:39:06.572629+00:00'
subtasks:
- T026
- T027
- T028
- T029
phase: Phase 2 - Migration
history:
- at: '2026-09-30T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_cli_git_paths.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/safe_commit_cmd.py
- src/specify_cli/cli/commands/implement_cores.py
- src/specify_cli/cli/commands/accept.py
- src/specify_cli/acceptance/__init__.py
- src/specify_cli/cli/commands/mission_type.py
- src/specify_cli/cli/commands/charter_bundle.py
- src/specify_cli/cli/commands/_coordination_doctor.py
- src/specify_cli/cli/commands/review/_dead_code.py
- src/specify_cli/agent_tasks_ports.py
- src/specify_cli/task_utils/support.py
- tests/specify_cli/cli/commands/test_cli_git_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP06 – other CLI command call sites

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

- All path-listing git calls and porcelain parsers in the owned files use `kernel.git` (base census: `safe_commit_cmd` ~147/209 + ~164 split; `implement_cores` ~97 + `_parse_porcelain_entries` ~144/162; `accept` ~389 + ~103 split; `acceptance/__init__` ~1735/1758 + `_porcelain_dirty_path` ~165/169; `mission_type` ~995; `charter_bundle` ~143 (`ls-files --error-unmatch` → `is_tracked`); `_coordination_doctor` ~254 (`ls-files`) / ~357; `review/_dead_code` ~160 (half-fixed with `quotePath=false`); `agent_tasks_ports` ~425; `task_utils/support` ~136/155).
- `safe_commit` and `implement` see real paths for spaced/non-ASCII files (they decide what gets committed / whether a checkout is clean).

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

> Populated by `spec-kitty agent mission finalize-tasks`. Enter the workspace with `spec-kitty implement WP06 --mission git-paths-are-data-01M3SSXR`; never reconstruct the path.

## Subtasks & Detailed Guidance

### Subtask T026 – safe_commit_cmd, implement_cores

- `safe_commit_cmd`: both status probes (with `--untracked-files=all` and pathspecs) → `status_entries(untracked="all", pathspecs=...)`; drop the split parser.
- `implement_cores._parse_porcelain_entries` → consume `StatusEntry`; keep its return shape for callers (read them).

### Subtask T027 – accept/acceptance/mission_type/charter_bundle

- `acceptance/__init__.py`: `diff --cached --name-only` → `changed_paths(cached=True)`; `_porcelain_dirty_path` → `entry.path`.
- `accept.py`: same pattern. `mission_type.py` dirty probe → `status_entries`. `charter_bundle.py` → `is_tracked`.

### Subtask T028 – doctors, dead-code, ports, support

- `_coordination_doctor.py`: `ls-files` → `tracked_paths`; status → `status_entries`. Do NOT touch its `worktree list` or git-version logic.
- `review/_dead_code.py`: replace the `quotePath=false` half-fix with `changed_paths`.
- `agent_tasks_ports.py`, `task_utils/support.py`: status → `status_entries`; remove `line[3:]` slicing.

### Subtask T029 – tests

- `test_cli_git_paths.py`: real-git cases: safe-commit sees `a b/f` and `é/g` as real paths; implement's dirty classification with a spaced path; acceptance staged-path listing non-ASCII. Update existing mocks as needed; list them in the hand-off.

## Test Strategy

- New file + existing tests importing the changed modules (`rg -l "safe_commit_cmd|implement_cores|cli.commands.accept|specify_cli.acceptance|mission_type|charter_bundle|_coordination_doctor|_dead_code|agent_tasks_ports|task_utils.support" tests`), `-m "not slow"` when broad.

Always also run: `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check <changed files>`, `uv run --frozen mypy <changed src files>`, and `make test-fast` is NOT required per WP (the orchestrator runs it at closeout).

## Risks & Mitigations

- `safe_commit` is on the commit-recipe gate path (`tests/specify_cli/cli/commands/test_commit_recipes.py`); run it.

## Review Guidance

- `census(owned_files)` from `tests/architectural/_git_path_listing_census.py` reports 0 hits for this WP's `src/` files.
- No listing literal / parser left in owned files; `is_tracked` exit-code semantics preserved for `charter_bundle`.
- Confirm ruff, format and mypy ran on changed files and were clean.
- Confirm no destructive git literal moved into `src/kernel/git/` (C-007).

## Activity Log

- 2026-09-30T19:20:00Z – system – Prompt created.
