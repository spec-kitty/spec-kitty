---
work_package_id: WP01
title: Anchor Gate D's left boundary
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6096-dead-path-gate-anchor
merge_target_branch: issue-6096-dead-path-gate-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-6096-dead-path-gate-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6096-dead-path-gate-anchor unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Gate precision fix
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/architectural/test_dead_builtin_doc_paths.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_dead_builtin_doc_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Anchor Gate D's left boundary

## ⚡ Do This First: Load Agent Profile

Load `implementer-ivan` (`/spk-charter-profile-load`), role `implementer`, before parsing the rest.

## Objectives & Success Criteria

- Gate D (`test_no_live_doc_names_a_pre_move_builtin_path`) no longer matches a
  `…/src/charter/offering/<kind>/built-in` (or `…/*.graph.yaml`) occurrence that
  is the **tail of a longer path**, while it still matches a genuine **top-level**
  reference (FR-001, FR-002).
- A self-mutation-proven regression test exercises the real `git grep` + the
  module regex against a synthetic `docs/` tree in BOTH directions, RED on the
  base and GREEN on the final commit (NFR-001, C-003, SC-001/SC-002).
- `_GUARD_DOC_EXCLUSIONS` and the two forbidden path shapes are unchanged
  (FR-003, C-001); no suppressions, no new ratchet/allowlist (C-002); changed
  files are ruff/format/mypy clean, complexity ≤ 15 (NFR-002).

## Context & Constraints

- Issue #6096; diagnosis + red-first evidence + sibling audit in
  `kitty-specs/dead-path-docs-gate-anchor-01M4RJTJ/research/diagnosis-6096.md`.
- Charter: Standing Order 4 (red-first, never retry-to-green), Standing Order 5
  (non-vacuous, self-mutation-proven, do not loosen the guard), ATDD-First C-011.
- Fix = left boundary only: prepend `(^|[^A-Za-z0-9_./-])` wrapping the existing
  alternation. Keep `git grep` as the gate mechanism.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first ATDD regression test

- **Purpose**: Pin the user-observable gate behaviour both ways before the fix.
- **Steps**: Add a test that `git init`s a `tmp_path` repo, writes `docs/` files
  (a genuine top-level ref; a nested `packs/.../src/charter/offering/<kind>/built-in`
  tail), `git add`s them, runs the shared gate helper, and asserts the tail is
  NOT reported while the genuine ref IS. Witness RED on the base (over-match).
- **Files**: `tests/architectural/test_dead_builtin_doc_paths.py`.
- **Notes**: `git grep` sees tracked working-tree files, so `git add` the fixtures.

### Subtask T002 – Left-boundary anchor + shared helper

- **Purpose**: Eliminate the over-match without loosening the guard.
- **Steps**: Prepend `(^|[^A-Za-z0-9_./-])` (wrapping the current alternation) to
  `_MOVED_BUILTIN_DOC_RE`; extract a small helper that runs
  `git grep -nE <regex> -- <pathspecs>` against a given `cwd`, used by both the
  live gate and the regression test. Commit GREEN.
- **Files**: `tests/architectural/test_dead_builtin_doc_paths.py`.

### Subtask T003 – Non-vacuity proof + targeted validation

- **Purpose**: Prove the gate is non-vacuous and the change is clean.
- **Steps**: Temporarily revert the anchor, show the regression test RED, record
  the output (do NOT commit the revert). Run the targeted gate, the sibling
  gates, the scanner unit tests, and `make test-fast`; `ruff check`,
  `ruff format --check --force-exclude`, mypy on the changed file.

## Test Strategy

- `.venv/bin/python -m pytest tests/architectural/test_dead_builtin_doc_paths.py -q`
- Sibling gates named in #6096 + scanner: `test_no_dead_cli_paths.py`,
  `test_no_dead_doctrine_paths.py`, `test_no_dead_src_path_literals.py`,
  and any `_dead_path_scan` unit tests (`grep -rl _dead_path_scan tests/`).
- `make test-fast`. Never the bare `tests/architectural/` directory; never `make test-full`.

## Risks & Mitigations

- ERE portability → leading alternation is POSIX-safe.
- Test/gate divergence → one shared helper.

## Review Guidance

- Verify RED-on-base / GREEN-on-final and the self-mutation revert evidence.
- Confirm the forbidden set and exclusions are untouched and no suppression was added.

## Progress & Status

Progress/status live in the status event log — not this file.

- Record a progress note: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- Change WP status: `spec-kitty agent tasks move-task WP01 --to <status>`
- View: `spec-kitty agent tasks status`
