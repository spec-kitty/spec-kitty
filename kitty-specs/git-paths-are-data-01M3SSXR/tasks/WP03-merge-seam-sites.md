---
work_package_id: WP03
title: Merge-seam call sites
dependencies:
- WP01
requirement_refs:
- FR-008
- FR-013
- NFR-001
- NFR-005
planning_base_branch: claude/git-path-remediation-rnrzfz
merge_target_branch: claude/git-path-remediation-rnrzfz
branch_strategy: Planning artifacts for this mission were generated on claude/git-path-remediation-rnrzfz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/git-path-remediation-rnrzfz unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-git-paths-are-data-01M3SSXR
base_commit: b99f6f41b251862ea70c120c90299665579178ab
created_at: '2026-09-30T19:38:15.994167+00:00'
subtasks:
- T012
- T013
- T014
- T015
phase: Phase 2 - Migration
history:
- at: '2026-09-30T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/vcs/
create_intent:
- tests/core/test_vcs_git_paths.py
- tests/consolidation/test_git_probes_git_paths.py
- tests/coordination/test_coordination_git_paths.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/core/vcs/git.py
- src/specify_cli/consolidation/git_probes.py
- src/specify_cli/consolidation/bookkeeping_projection.py
- src/specify_cli/coordination/commit_router.py
- src/specify_cli/coordination/surface_resolver.py
- src/specify_cli/coordination/transaction.py
- tests/core/test_vcs_git_paths.py
- tests/consolidation/test_git_probes_git_paths.py
- tests/coordination/test_coordination_git_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03 – Merge-seam call sites

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

- Every path-listing git call in the owned files goes through `kernel.git` (base census: `core/vcs/git.py` 7 sites — lines ~272, 416, 427, 503, 516, 1071, 1123; `git_probes.py` 5 — ~115, 272, 519, 562, 596; `bookkeeping_projection.py` ~440; `commit_router.py` ~1211; `surface_resolver.py` ~822; `transaction.py` ~893).
- `git_diff_names`, `git_diff_names_checked`, `git_ls_tree_names_checked`, `merge_base_changed_files` keep their public signatures/return types (9 importers) but are implemented on kernel queries; FR-013 classification applied to each caller that depends on their `()`/`None` failure value.
- `git_probes._classify_porcelain_lines` / `_raw_porcelain_status` operate on `StatusEntry` (no line slicing); the leading-space `.strip()` hazard documented at `git_probes.py:~97-110` disappears.

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

> Populated by `spec-kitty agent mission finalize-tasks`. Enter the workspace with `spec-kitty implement WP03 --mission git-paths-are-data-01M3SSXR`; never reconstruct the path.

## Subtasks & Detailed Guidance

### Subtask T012 – `core/vcs/git.py`

- Module helpers (`git_diff_names*`, `git_ls_tree_names_checked`, `merge_base_changed_files`) → `kernel.git.changed_paths` / `tree_paths`; return `str` paths as today (`[str(p) for p in ...]`), preserving order and de-dup semantics exactly (read each docstring).
- `GitVCS` methods (`get_workspace_info` dirtiness, `detect_conflicts`, `has_conflicts`, `--diff-filter=U` listings) → `status_entries` / `changed_paths(diff_filter="U")` / `StatusEntry.is_conflicted`.
- FR-013: grep the importers (`rg -n "git_diff_names|git_ls_tree_names_checked|merge_base_changed_files" src`) and record guard vs advisory per caller in your hand-off. Keep the helper's failure contract where an advisory caller relies on it; implement it as an explicit `except GitCommandError` with a comment.

### Subtask T013 – consolidation

- `git_probes.py`: status probes → `status_entries`; `diff --name-status --no-renames` → `changed_entries`; `show --name-only` → `commit_paths`; `ls-tree` → `tree_paths`. Keep `GitProbeError` as the raised type (wrap `GitCommandError`). The squash content axis must now see real paths (a quoted path no longer causes a false REFUSE).
- `bookkeeping_projection.py:~440` `diff --name-only` → `changed_paths`.

### Subtask T014 – coordination

- `commit_router._paths_uncommitted_in_primary`, `transaction.BookkeepingTransaction._worktree_has_pending_changes` → `status_entries(..., pathspecs=...)`; `surface_resolver` `ls-tree -r --name-only` → `tree_paths`. Thread `env` where the original passed one.
- These function names are in T019's `_KNOWN_DIRTY_PREDICATES`; after migration they no longer contain a porcelain literal — that is expected (T019 stale entries only warn; WP08 folds T019).

### Subtask T015 – tests

- One real-git quoted-path test per migrated guard in the new test files (e.g. a dirty `a b/f` is seen by `_paths_uncommitted_in_primary`; `merge_base_changed_files` returns `"a b/f"` and `"é/g"` unquoted; `git_probes` classifies `?? "a b/"` correctly).

## Test Strategy

- New test files + existing: `uv run --frozen pytest tests/core tests/consolidation tests/coordination -q -m "not slow"` (targeted; if a directory is large, run the files that import the changed modules: `rg -l "git_probes|bookkeeping_projection|commit_router|surface_resolver|coordination.transaction|core.vcs.git" tests`).
- Gates: `uv run --frozen pytest tests/architectural/test_destructive_op_routing.py tests/architectural/test_merge_pipeline_ratchets.py -q`.

Always also run: `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check <changed files>`, `uv run --frozen mypy <changed src files>`, and `make test-fast` is NOT required per WP (the orchestrator runs it at closeout).

## Risks & Mitigations

- AC-F1: `lanes/consolidation.py` not owned here, but `git_probes` callers pass `env`; keep it.
- Order: `changed_paths` returns git order; callers that `sorted()` today keep doing so.

## Review Guidance

- `census(owned_files)` from `tests/architectural/_git_path_listing_census.py` reports 0 hits for this WP's `src/` files.
- No `status --porcelain`/`--name-only`/`--name-status`/`ls-tree` literal left in owned files.
- FR-013 decisions listed and sensible (guards fail closed).
- Confirm ruff, format and mypy ran on changed files and were clean.
- Confirm no destructive git literal moved into `src/kernel/git/` (C-007).

## Activity Log

- 2026-09-30T19:20:00Z – system – Prompt created.
