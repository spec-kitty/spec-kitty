---
work_package_id: WP08
title: Empty-allowlist class gate
dependencies:
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
requirement_refs:
- FR-009
- SC-002
- SC-003
- C-006
planning_base_branch: claude/git-path-remediation-rnrzfz
merge_target_branch: claude/git-path-remediation-rnrzfz
branch_strategy: Planning artifacts for this mission were generated on claude/git-path-remediation-rnrzfz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/git-path-remediation-rnrzfz unless the human explicitly redirects the landing branch.
subtasks:
- T035
- T036
- T037
phase: Phase 3 - Close the class
history:
- at: '2026-09-30T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_git_path_listing_owner.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- tests/architectural/test_git_path_listing_owner.py
- tests/architectural/test_destructive_op_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP08 – Empty-allowlist class gate

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

- `tests/architectural/test_git_path_listing_owner.py` fails on any path-listing git argv or NUL/` -> ` split outside `src/kernel/git/`, with an **empty** allowlist (FR-009, SC-002, SC-003, C-009). No `_baselines.yaml` entry (a gate with no allowlist needs none).
- Non-vacuity (standing order 5): (a) a floor on the number of `src/` files scanned (≥ 1000 or the current count minus a margin — check `len(iter_py_files(SRC_ROOT))`); (b) a planted-hit test: write a temp module with `["git", "status", "--porcelain"]` and one with `out.split("\0")` and assert the scanner reports both; (c) negative control: `["git", "worktree", "list", "--porcelain"]` is NOT reported; (d) positive control: the scanner finds ≥ 1 hit inside `src/kernel/git/` when that exclusion is disabled.
- T019's porcelain-literal scan in `test_destructive_op_routing.py` is folded into the new gate (single authority): delete the duplicated scan, keep T019's function-registry intent only if it still guards something the new gate does not (document the decision in the module docstring).

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

> Populated by `spec-kitty agent mission finalize-tasks`. Enter the workspace with `spec-kitty implement WP08 --mission git-paths-are-data-01M3SSXR`; never reconstruct the path.

## Subtasks & Detailed Guidance

### Subtask T035 – the gate

- Reuse `tests/architectural/_destructive_op_census.py` (`iter_py_files`, `module_string_constants`, `argv_tokens`). Rule (plan Design §6):
  - classify a `List`/`Tuple` literal's resolved tokens: skip if `"worktree"` present; hit if `ls-files`/`ls-tree` present; hit if `status` present with a `--porcelain*` token (except when `-q`/`--quiet`/`--exit-code` present); hit if `--name-only`/`--name-status` present; hit if any of `diff diff-tree diff-index diff-files log show check-ignore grep` present together with `-z`.
  - hit on `Call` whose `func` is an `Attribute` named `split`/`partition`/`rsplit` with first arg constant `"\0"`, `"\x00"`, `b"\0"`, `b"\x00"` or `" -> "`.
- Scope: every `*.py` under `src/` except `src/kernel/git/`.
- Failure message lists `file:line: <kind>` and says "ask kernel.git (status_entries/tree_paths/changed_paths/...) instead; see kitty-specs/git-paths-are-data-01M3SSXR/quickstart.md".
- The prototype used for planning is at the orchestrator's scratchpad; the base census was **85 hits in 47 files** — record the base count in the module docstring.

### Subtask T036 – fold T019

- Remove T019's `status --porcelain` literal scan (`test_destructive_op_routing.py` ~439-490) and its `_KNOWN_DIRTY_PREDICATES` registry if the new gate subsumes it; keep T018 untouched. Explain in the docstring.

### Subtask T037 – run and record

- Run the gate: must be green with empty allowlist on the lane that contains WP02–WP07. If any hit remains in a file no WP owned (the planning census was regex-based), migrate it here as a small out-of-map edit with a one-line rationale, or stop and report it.
- Record in the hand-off: base count (check out the planning base in a scratch worktree and run the gate there → N > 0) and close count (0).

## Test Strategy

- `uv run --frozen pytest tests/architectural/test_git_path_listing_owner.py tests/architectural/test_destructive_op_routing.py tests/architectural/test_no_dead_symbols.py -q`

Always also run: `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check <changed files>`, `uv run --frozen mypy <changed src files>`, and `make test-fast` is NOT required per WP (the orchestrator runs it at closeout).

## Risks & Mitigations

- Vacuity: a scanner that silently matches nothing. The planted-hit and floor tests exist for this.
- Dead-symbol gate: remove any `kernel.git` export that ended up with no `src/` caller.

## Gate rule source

- The gate wraps WP01's `tests/architectural/_git_path_listing_census.py` (list argv AND positional-constant argv, the widened flag set, `" -> "` / `[3:]` tells). Do not fork the rule; extend the census module (it is WP01's file, so a change goes through the orchestrator) and keep one planted-hit test per form here too.
- Known positional-argv sites the first prototype missed: `git/report_transaction.py` (69, 82, 155, 212), `live_work/watcher.py` (125, 128), `review/_dead_code.py` (160), `migration/mission_state.py` (2722). The base count must include them.

## Review Guidance

- Allowlist literally empty; planted-hit test fails when the rule is weakened (try it).
- Confirm ruff, format and mypy ran on changed files and were clean.
- Confirm no destructive git literal moved into `src/kernel/git/` (C-007).

## Activity Log

- 2026-09-30T19:20:00Z – system – Prompt created.
