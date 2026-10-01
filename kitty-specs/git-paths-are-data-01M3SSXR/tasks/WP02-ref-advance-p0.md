---
work_package_id: WP02
title: 'Branch advance on the owner (P0 #5392/#5400)'
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-007
- C-002
- C-003
- C-009
- SC-001
planning_base_branch: claude/git-path-remediation-rnrzfz
merge_target_branch: claude/git-path-remediation-rnrzfz
branch_strategy: Planning artifacts for this mission were generated on claude/git-path-remediation-rnrzfz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/git-path-remediation-rnrzfz unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-git-paths-are-data-01M3SSXR
base_commit: b99f6f41b251862ea70c120c90299665579178ab
created_at: '2026-09-30T19:37:48.708809+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
phase: Phase 1 - P0 fix
history:
- at: '2026-09-30T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/ref_advance.py
create_intent:
- tests/git/test_ref_advance_git_paths.py
- tests/terminus/test_repro_5392.py
- tests/git/test_ref_advance_obstructions.py
- tests/terminus/test_repro_5400.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/git/ref_advance.py
- tests/git/test_ref_advance_obstructions.py
- tests/git/test_ref_advance_git_paths.py
- tests/terminus/test_repro_5400.py
- tests/terminus/test_repro_5392.py
- src/specify_cli/git/destructive_guard.py
- src/specify_cli/doctrine/sources/git_source.py
- CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02 – Branch advance on the owner (P0 #5392/#5400)

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

- #5392: an ignored OR untracked local path that git would quote (space, non-ASCII with `core.quotePath=true`, a name containing ` -> `) and that collides with an incoming tracked path makes `advance_branch_ref` refuse with `RefAdvanceDirtyWorktreeError`; ref, HEAD, index and local bytes unchanged (FR-001).
- #5400: an ignored or untracked descendant of a directory the incoming tree replaces with a file makes it refuse; `storehouse` vs `store` does not (FR-002). PR #5437's commit is carried with authorship intact (`git cherry-pick -x`), and its tests stay green (oracle).
- `ref_advance` asks `kernel.git` for status entries and tree paths; the obstruction rule is `GitPath.overlaps`; `ref_advance` still imports zero `specify_cli` (C-002) and keeps its own `_run_git` for `update-ref`/`reset --hard`/`worktree list` (C-007, AC-B3, T018 token lines).
- Red-first (C-003): each regression test is committed BEFORE the fix and shown failing on the base; the commit message of the fix quotes the red output line.
- Half-by-half: reverting only the decode half re-reds #5392's test; reverting only the ancestor half re-reds #5400's (record both runs in the hand-off).

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

> Populated by `spec-kitty agent mission finalize-tasks`. Enter the workspace with `spec-kitty implement WP02 --mission git-paths-are-data-01M3SSXR`; never reconstruct the path.

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first repro for #5392

- New `tests/terminus/test_repro_5392.py` modeled on PR #5437's `tests/terminus/test_repro_5400.py` (real CLI `consolidate`, real git, nothing mocked): ignored `src/local data/notes.txt`, the lane tracks the same path with `git add -f`; assert nonzero exit, path named, target SHA unchanged, WP01 approved, local bytes intact. Mark `pytest.mark.regression`, `integration`, `git_repo`.
- New `tests/git/test_ref_advance_git_paths.py` (fast, through `advance_branch_ref`): parametrize ignored/untracked × {`src/local data/notes.txt`, `src/é/notes.txt` with `core.quotePath=true`, `src/p -> q/notes.txt`}; positive control `src/local-data/notes.txt` refuses too; collapsed `!! .venv/` with incoming `.venv/x` absent locally refuses (conservative, spec US1 scenario 5). Mark the quoted cases `pytest.mark.regression`.
- Commit the tests alone first; run them; paste the failing assertion into the commit body (`Red on base: ...`).

### Subtask T008 – Carry PR #5437

- `git fetch origin pull/5437/head` then `git cherry-pick -x 075dbc6ad8be8ce770269d45372e7a7c4d00e2fd` onto the lane BEFORE T009 (authorship stays Matt Van Horn). If CHANGELOG conflicts, union-resolve keeping both entries.
- Its `test_empty_path_and_empty_target_set_do_not_obstruct` calls the private `_path_obstructs_target_tree(str, set[str])`; T010 changes that signature — adapt that one test in the T010 commit (re-pin a private helper's test, not behaviour).

### Subtask T009 – Campsite: listings through kernel

- Behaviour-preserving step first (standing order 2): replace `_target_tree_paths` body with `kernel.git.tree_paths(repo_root, new_sha, env=env)` and `_dirty_entries`'s `git status --porcelain --ignored` with `kernel.git.status_entries(worktree, ignored=True, env=env)`; delete `_porcelain_path`. Map `GitCommandError` to `RefAdvanceError` with the same message prefixes ("Could not inspect target tree ...", "Could not inspect worktree state at ...") so callers and tests keep working.
- `is_residue(path: str)` and the `meta.json` VCS-lock escape receive `str(entry.path)` (the real path).
- This step alone already fixes #5392 (the decode half).

### Subtask T010 – Obstruction on `GitPath`; typed verdict

- `_path_obstructs_target_tree(path: GitPath, target_paths: frozenset[GitPath]) -> bool` → `any(path.overlaps(t) for t in target_paths)` (empty path never obstructs — root overlaps nothing). This is the ancestor half (#5400) expressed on components.
- `reset_would_obstruct_untracked` currently finds obstructions by searching `_RESET_OBSTRUCTION_MARKER` in rendered strings. Make the verdict typed: have `_dirty_entries` build internal `(entry, reason)` records (reason ∈ tracked-change / obstruction / untracked-removal) and render strings only at the boundary (the `list[str]` it returns and the exception message keep today's shape `"<XY> <path> (would be overwritten by reset --hard to <sha12>)"`, using `StatusEntry.display()`). `reset_would_obstruct_untracked` asks the typed records. Keep `_dirty_entries` the single authority (T019 / INV-3; `destructive_guard` must still call it — check `src/specify_cli/git/destructive_guard.py` and keep its call signature working).
- Complexity ≤ 15: extract a `_classify_entry(...)` helper.

### Subtask T011 – Entry points, half-by-half, conversion

- Add cases through `reset_would_obstruct_untracked` and through `destructive_guard`'s guarded worktree removal with `treat_untracked_as_dirty=True` (find the public guard function in `destructive_guard.py`) for a quoted-path collision.
- Half-by-half proof: temporarily revert T009 only → #5392 tests red, #5400 green; revert T010 only → #5400 ancestor tests red. Do this locally, record the outputs in the hand-off; do not commit the reverts.
- After green: keep the issue-named terminus repros (fold-or-keep verdict happens at closeout); drop `pytest.mark.regression` from the fast `tests/git/` unit cases once they pass (ADR 2026-07-17-1: repros converted to focused tests).

## Test Strategy

- `uv run --frozen pytest tests/git/ tests/specify_cli/git/ tests/kernel/test_git_listing.py -q`
- `uv run --frozen pytest tests/terminus/test_repro_5392.py tests/terminus/test_repro_5400.py -q`
- Named gates: `uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_destructive_op_routing.py tests/architectural/test_merge_pipeline_ratchets.py -q`
- Callers' fast tests: `uv run --frozen pytest tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py tests/specify_cli/cli/commands/test_merge_residue_gate_single_authority_wp13.py tests/specify_cli/cli/commands/test_issue_2795_claim_blocker.py -q`

Always also run: `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check <changed files>`, `uv run --frozen mypy <changed src files>`, and `make test-fast` is NOT required per WP (the orchestrator runs it at closeout).

## Risks & Mitigations

- T018 (`test_destructive_op_routing.py`) pins the `reset --hard` token line inside `_resync_checkouts`; do not touch that line.
- AC-B3: `update-ref` literal stays only in this module.
- `env` must thread to every kernel query (AC-F1).
- Messages are operator-facing; keep the `Dirty entries:` block shape.

## Signature ripple (post-tasks squad)

- `src/specify_cli/git/destructive_guard.py` (lines ~189, 190, 268) and `src/specify_cli/doctrine/sources/git_source.py` (~194, 199) call `_target_tree_paths` and `_dirty_entries(target_paths: set[str])`. Migrate them to the `frozenset[GitPath]` signature in this WP; no `set[str]` adapter survives.
- The cherry-pick of PR #5437 carries a `CHANGELOG.md` hunk; keep it and reword it for the full fix. Adapt PR #5437's `test_empty_path_and_empty_target_set_do_not_obstruct` to `GitPath` arguments.

## Review Guidance

- Red-first evidence present for both issues; PR #5437 commit present with `(cherry picked from commit 075dbc6a...)`.
- `ref_advance` imports only `kernel.*` and stdlib.
- Half-by-half outputs recorded.
- Confirm ruff, format and mypy ran on changed files and were clean.
- Confirm no destructive git literal moved into `src/kernel/git/` (C-007).

## Activity Log

- 2026-09-30T19:20:00Z – system – Prompt created.
