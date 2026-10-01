---
work_package_id: WP04
title: git/, lanes/ and watcher call sites
dependencies:
- WP01
requirement_refs:
- FR-008
- FR-013
- NFR-001
planning_base_branch: claude/git-path-remediation-rnrzfz
merge_target_branch: claude/git-path-remediation-rnrzfz
branch_strategy: Planning artifacts for this mission were generated on claude/git-path-remediation-rnrzfz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/git-path-remediation-rnrzfz unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-git-paths-are-data-01M3SSXR
base_commit: b99f6f41b251862ea70c120c90299665579178ab
created_at: '2026-09-30T19:38:33.641064+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
phase: Phase 2 - Migration
history:
- at: '2026-09-30T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/git/test_git_module_git_paths.py
- tests/lanes/test_lanes_git_paths.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/git/commit_helpers.py
- src/specify_cli/git/report_transaction.py
- src/specify_cli/git/sparse_checkout_remediation.py
- src/specify_cli/lanes/auto_rebase.py
- src/specify_cli/lanes/consolidation.py
- src/specify_cli/lanes/for_review_gate.py
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/lanes/checkout_occupancy.py
- src/specify_cli/live_work/watcher.py
- src/specify_cli/gitignore_manager.py
- tests/git/test_git_module_git_paths.py
- tests/lanes/test_lanes_git_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04 – git/, lanes/ and watcher call sites

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

- All path listings and hand-written `-z` / porcelain parsers in the owned files use `kernel.git` (base census: `commit_helpers` ~701/711; `report_transaction` 4 NUL splits ~69/82/155/212 incl. `ls-files --stage`; `sparse_checkout_remediation` ~147/294; `auto_rebase` ~165/493/562; `lanes/consolidation` ~820/827; `for_review_gate` ~154/162 (`log -z --name-only`); `worktree_allocator` ~1803; `checkout_occupancy` ~157 (` -> ` split); `live_work/watcher` ~134/178; `gitignore_manager` ~205/216).
- One decode rule everywhere (drop `os.fsdecode`, strict utf-8 and `errors="replace"` variants).

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

> Populated by `spec-kitty agent mission finalize-tasks`. Enter the workspace with `spec-kitty implement WP04 --mission git-paths-are-data-01M3SSXR`; never reconstruct the path.

## Subtasks & Detailed Guidance

### Subtask T016 – git/ modules

- `commit_helpers.py`: the `-z` name listing + split → `changed_paths`/`status_entries` as appropriate. Keep its private `_run_git` for non-listing commands (out of scope, follow-up issue).
- `report_transaction.py`: `_dirty_paths` → `status_entries(untracked="all")` (include `orig_path` for renames exactly as today); `ls-files --stage` → `index_entries`; other NUL splits → the matching query. It uses `--literal-pathspecs` already — kernel queries default to literal.
- `sparse_checkout_remediation.py`: `_is_dirty` / `_run_remediation_steps` status probes → `bool(status_entries(...))`.

### Subtask T017 – lanes merge helpers

- `auto_rebase.py`: `diff --name-only --diff-filter=U` → `changed_paths(diff_filter="U")`; `ls-tree -r --name-only` → `tree_paths`; `diff --name-status --cached` → `changed_entries(cached=True)`.
- `lanes/consolidation.py` (~820): keep `env=` on every call (AC-F1 scans `subprocess.run` in this file — a kernel call is not `subprocess.run`, but pass `env` through anyway).
- `for_review_gate.py`: `log -z --name-only` → `log_paths`; keep its quoted-path fix behaviour (it already handled `.kittify/café`).

### Subtask T018 – worktree allocator + occupancy

- `worktree_allocator.py:~1803` `_git_status_porcelain_lines` → return `StatusEntry` tuples; update `checkout_occupancy.py` (~155-157) to consume entries (no ` -> ` split). Do NOT touch `worktree list --porcelain` parsing (out of scope).

### Subtask T019 – watcher + gitignore manager

- `live_work/watcher.py` NUL splits → queries. `gitignore_manager.py` `ls-files` + split → `tracked_paths` / `is_tracked`.

### Subtask T020 – tests

- Real-git quoted/non-ASCII path cases for each guard-like site in the two new test files; update existing tests only where they pinned buggy parsing.

## Test Strategy

- `uv run --frozen pytest tests/git tests/lanes tests/specify_cli/git -q` restricted to files importing the changed modules (`rg -l "<module>" tests`), plus the new files.
- Gates: `uv run --frozen pytest tests/architectural/test_merge_pipeline_ratchets.py tests/architectural/test_destructive_op_routing.py -q`.

Always also run: `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check <changed files>`, `uv run --frozen mypy <changed src files>`, and `make test-fast` is NOT required per WP (the orchestrator runs it at closeout).

## Risks & Mitigations

- `report_transaction` receipts compare paths byte-exactly — keep surrogateescape round trip.
- `checkout_occupancy` decides whether a checkout is occupied: fail-closed semantics must hold.

## Note (post-tasks squad)

- The comment at `live_work/watcher.py` (~137) states the rename record order wrongly; with typed entries the order question disappears, but add a real-git rename test for the watcher.
- `report_transaction.py` uses a positional `_git(root, "status", …)` helper and `ls-files -v` for the `H` tag; use `status_entries` and `index_entries(tags=True)`.

## Review Guidance

- `census(owned_files)` from `tests/architectural/_git_path_listing_census.py` reports 0 hits for this WP's `src/` files.
- No `.split("\0")`, `" -> "` split or listing literal left in owned files.
- AC-F1 still green.
- Confirm ruff, format and mypy ran on changed files and were clean.
- Confirm no destructive git literal moved into `src/kernel/git/` (C-007).

## Activity Log

- 2026-09-30T19:20:00Z – system – Prompt created.
