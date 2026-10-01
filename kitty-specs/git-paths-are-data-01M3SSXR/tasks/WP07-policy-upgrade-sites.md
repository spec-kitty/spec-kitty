---
work_package_id: WP07
title: policy, post-merge, migration and upgrade call sites
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
created_at: '2026-09-30T19:39:23.815525+00:00'
subtasks:
- T030
- T031
- T032
- T033
- T034
phase: Phase 2 - Migration
history:
- at: '2026-09-30T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/policy/
create_intent:
- tests/policy/test_policy_git_paths.py
- tests/upgrade/test_upgrade_git_paths.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/migration/mission_state.py
- src/specify_cli/policy/commit_guard_hook.py
- src/specify_cli/bulk_edit/gate.py
- src/specify_cli/post_merge/stale_assertions.py
- src/specify_cli/post_merge/retrospective_terminus.py
- src/specify_cli/charter_runtime/preflight/runner.py
- src/specify_cli/core/mission_creation.py
- src/specify_cli/missions/_substantive.py
- src/specify_cli/migration/runner.py
- src/specify_cli/upgrade/autocommit.py
- src/specify_cli/upgrade/migrations/m_3_2_0rc35_sync_state_gitignore.py
- src/specify_cli/upgrade/migrations/m_3_2_5_agents_skills_gitignore_backfill.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_heal_template_set_provenance.py
- tests/policy/test_policy_git_paths.py
- tests/upgrade/test_upgrade_git_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP07 – policy, post-merge, migration and upgrade call sites

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

- All path-listing git calls and NUL parsers in the owned files use `kernel.git` (base census: `commit_guard_hook` ~57; `bulk_edit/gate` ~210; `stale_assertions` ~306 (`'*.py'` glob pathspec → `glob=True`) / ~813; `retrospective_terminus` ~250; `charter_runtime/preflight/runner` ~494/531; `core/mission_creation` ~607 + ~556 split; `missions/_substantive` ~946; `migration/runner` ~349; `upgrade/autocommit` ~206/214 (`errors="replace"` lossy decode); the three migrations).
- `commit_guard_hook`: a quoted protected staged path is now seen (verify whether it was fail-open; add a test either way).
- `bulk_edit/gate` and `stale_assertions`: quoted files are classified (were fail-open).
- Migrations: behaviour identical except correct decoding (they are version-pinned; keep outputs the same for ASCII paths).

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

> Populated by `spec-kitty agent mission finalize-tasks`. Enter the workspace with `spec-kitty implement WP07 --mission git-paths-are-data-01M3SSXR`; never reconstruct the path.

## Subtasks & Detailed Guidance

### Subtask T030 – commit guard + bulk edit gate

- `commit_guard_hook.py:~57` `diff --cached --name-only` → `changed_paths(cached=True)`; feed real paths to `validate_staged_files`. Write a real-git test: stage a protected path containing a space/non-ASCII and assert the guard blocks.
- `bulk_edit/gate.py:~210` → `changed_paths`.

### Subtask T031 – post_merge + charter preflight

- `stale_assertions.py`: `diff --name-only -- '*.py'` → `changed_paths(..., pathspecs=("*.py",), glob=True)`; `ls-files tests/` → `tracked_paths(pathspecs=("tests/",))`.
- `retrospective_terminus.py`, `charter_runtime/preflight/runner.py` status probes → `status_entries` (drop the `:531` parser).

### Subtask T032 – mission creation, substantive, migration runner, autocommit

- `core/mission_creation.py` ~607 `ls-files` + ~556 split → `tracked_paths` / `is_tracked`.
- `missions/_substantive.py` ~946 `ls-files --error-unmatch` → `is_tracked`.
- `migration/runner.py` ~349 → `status_entries`.
- `upgrade/autocommit.py` ~206/214 → `status_entries` (lossless decode replaces `errors="replace"`; keep its rename-order behaviour — see CHANGELOG #2491/#2492).

### Subtask T033 – upgrade migrations

- `m_3_2_0rc35_sync_state_gitignore.py` ~41 and `m_4_0_0rc5_heal_template_set_provenance.py` ~177 (`ls-files --stage --error-unmatch`) → `is_tracked` / `index_entries`; `m_3_2_5_agents_skills_gitignore_backfill.py` ~83/90 → `tracked_paths`. Run each migration's existing tests unchanged.

### Subtask T034 – tests

- New files: the commit-guard quoted-path test; autocommit non-ASCII/rename test from real git; one migration smoke with a spaced path.

## Test Strategy

- New files + existing tests importing the changed modules (`rg -l "commit_guard_hook|bulk_edit.gate|stale_assertions|retrospective_terminus|charter_runtime.preflight|mission_creation|_substantive|migration.runner|upgrade.autocommit|m_3_2_0rc35|m_3_2_5_agents|m_4_0_0rc5_heal_template" tests`), `-m "not slow"`.

Always also run: `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check <changed files>`, `uv run --frozen mypy <changed src files>`, and `make test-fast` is NOT required per WP (the orchestrator runs it at closeout).

## Risks & Mitigations

- `commit_guard_hook` runs inside a git hook: keep it fast (≤ 1 git process, NFR-005).
- Migrations must stay idempotent.

## Additional site (post-tasks squad)

- `src/specify_cli/migration/mission_state.py` `_assert_git_safe` (~2722) builds `status --porcelain` positionally and fails open on git error. It is a guard (it protects data before a migration rewrites files): replace it with `bool(status_entries(worktree, pathspecs=rel_paths))` and let `GitCommandError` propagate (FR-013). Add a real-git test with a quoted path.

## Review Guidance

- `census(owned_files)` from `tests/architectural/_git_path_listing_census.py` reports 0 hits for this WP's `src/` files.
- Commit-guard test proves the quoted protected path is blocked.
- No listing literal / NUL split left in owned files.
- Confirm ruff, format and mypy ran on changed files and were clean.
- Confirm no destructive git literal moved into `src/kernel/git/` (C-007).

## Activity Log

- 2026-09-30T19:20:00Z – system – Prompt created.
