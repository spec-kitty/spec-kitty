---
work_package_id: WP01
title: Pin classifier (foundation)
dependencies: []
requirement_refs:
- FR-001
- NFR-005
planning_base_branch: fix/finalize-repin-orphaned-planning-commit
merge_target_branch: fix/finalize-repin-orphaned-planning-commit
branch_strategy: Planning artifacts for this mission were generated on fix/finalize-repin-orphaned-planning-commit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/finalize-repin-orphaned-planning-commit unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Implementation
history:
- timestamp: '2026-09-21T00:00:00Z'
  agent: system
  action: Prompt generated via tasks phase authoring
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- src/specify_cli/lanes/planning_commit_classify.py
- tests/lanes/test_planning_commit_classify.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/planning_commit_classify.py
- tests/lanes/test_planning_commit_classify.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match.

---

## Objective

Create ONE shared authority that classifies the recorded `planning_commit_sha` against the **planning target-branch tip**, so finalize (WP02) and the lane consumers (WP03) stop duplicating ad-hoc `merge-base --is-ancestor` checks and stop collapsing the "orphaned" and "foreign" cases into one refusal (issue #4827; research.md D1/D5, C-006).

## Context

Today the reachability question is asked in at least three places with different, partial logic:
- `mission_finalize.py::_recorded_planning_sha_is_ancestor_of_tip` (~L2148) — `merge-base --is-ancestor recorded tip`, collapses "rewritten" and "unknown object" into `False`.
- `worktree_allocator.py::_merge_recorded_planning_commit` (~L612) — `is-ancestor pin <lane HEAD>` (a DIFFERENT ref — do not conflate; see C-006).
- `implement_support.py` — `_is_git_ancestor(...)` (~L497).

This WP introduces the canonical classifier they will all consume (WP02/WP03 wire it in). **Brownfield note:** confirm the exact home before writing — a new module `src/specify_cli/lanes/planning_commit_classify.py` is the intended home (lanes owns the `planning_commit_sha` concept, and `cli → lanes` is a legal internal dependency). If the brownfield scout finds a better-established home (e.g. an existing git-topology helper in `kernel`), record the deviation with a one-line rationale.

## Subtasks

### T001 — Git predicate helpers
Create `src/specify_cli/lanes/planning_commit_classify.py` with two small, individually-tested subprocess predicates run with `cwd=repo_root`:
- `_object_present(repo_root, sha) -> bool`: `git cat-file -e <sha>^{commit}` → rc == 0 (present in the object store). Absent/foreign/GC'd → False. Never raises.
- `_is_ancestor(repo_root, sha, tip) -> bool`: `git merge-base --is-ancestor <sha> <tip>` → rc == 0. Any nonzero (not-ancestor OR unknown object OR not-a-repo) → False. Never raises. (This is the same primitive as the existing finalize helper — WP02 will retire the duplicate.)

### T002 — `classify_recorded_pin`
Implement `classify_recorded_pin(repo_root, recorded_sha, target_tip) -> PinClass` where `PinClass` is a small `Enum`/`Literal` of `advanced | orphaned | foreign | indeterminate`:
- `target_tip is None` (uncapturable / non-git) → `indeterminate` (caller degrades to preserve — do NOT abort here; research.md D4).
- `recorded_sha is None` → `indeterminate` (caller decides; classifier does not guess).
- `_is_ancestor(recorded, tip)` → `advanced`.
- else `_object_present(recorded)` → `orphaned` (present, unreachable — the rebase shape).
- else → `foreign` (object absent).
- Do NOT compute the pre-execution `captured` case here — that stays in the finalize caller (execution-not-begun short-circuit). Keep the function pure of Typer/console concerns (no printing, no exit) so both call sites can reuse it. Keep complexity ≤ 15.

### T003 — Unit tests
`tests/lanes/test_planning_commit_classify.py` (`pytest.mark.git_repo`), real git repo per the `test_issue_4141_refresh_planning_commit.py` harness idiom:
- `advanced`: recorded == an ancestor of the tip.
- `orphaned`: rebase/rewrite so the recorded SHA is present but not an ancestor of the new tip (create the commit, `git rev-parse` it, then `git commit --amend`/rebase the branch forward so it is orphaned yet still in the object store).
- `foreign`: a syntactically-valid but absent SHA (e.g. `40*"0"` or a `deadbeef…` string).
- `indeterminate`: `target_tip=None`; and a non-git `cwd`.
Assert each predicate (`_object_present`, `_is_ancestor`) directly too.

## Branch Strategy

Planning branch: `fix/finalize-repin-orphaned-planning-commit`. Final merge target: `fix/finalize-repin-orphaned-planning-commit` (the PR then targets upstream `main`). Execution worktrees are allocated per computed lane from `lanes.json`.

## Definition of Done

- The classifier module exists, is import-safe, and never raises on bad input (returns a class / `indeterminate`).
- Unit tests cover all four classes + the two degrade paths and pass.
- `ruff`, `ruff format --check`, `mypy` clean; complexity ≤ 15; no new suppressions.

## Risks / reviewer guidance

- **C-006 trap**: reviewers must confirm the classifier keys off the TARGET-BRANCH TIP, never a lane worktree HEAD. A lane-HEAD-keyed classifier misfires on every healthy fresh coord lane (#2993).
- Ensure the predicates are `cwd`-bound to `repo_root` and use `capture_output=True` (no stray stdout).
