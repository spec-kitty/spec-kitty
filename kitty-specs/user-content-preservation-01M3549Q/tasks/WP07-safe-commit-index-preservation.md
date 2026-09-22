---
work_package_id: WP07
title: safe_commit never wipes the operator's index (#4888)
dependencies: []
requirement_refs:
- FR-011
- FR-012
planning_base_branch: fix/user-content-preservation
merge_target_branch: fix/user-content-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/user-content-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/user-content-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-user-content-preservation-01M3549Q
base_commit: db88c094abd63e3b63550618bbae780d5ef1c615
created_at: '2026-09-22T18:45:14.270463+00:00'
subtasks:
- T023
- T024
- T025
- T026
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/commit_helpers.py
create_intent:
- tests/regressions/test_issue_4888_safe_commit_index_preservation.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/git/commit_helpers.py
- src/specify_cli/upgrade/autocommit.py
- src/specify_cli/cli/commands/upgrade.py
- tests/regressions/test_issue_4888_safe_commit_index_preservation.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load **python-pedro** via `/ad-hoc-profile-load` (profile YAML), then return. This is the
highest regression-risk WP (hot shared helper, ~28 callers) — proceed carefully.

## Objective

`safe_commit` preserves the operator's unrelated staged changes with
`git stash push --staged` … `git stash pop --index`. That pop deterministically fails whenever
any unrelated tracked file is *partially* staged (an everyday `git add -p` state), stripping the
operator's staged work into an un-poppable stash (#4888). `upgrade` then swallows the typed
signal: exit 0, "please commit manually" (the commit already landed), stash never named. Fix the
root cause so the operator's index is never touched, and make `upgrade` honest.

## Ground truth (verified on main@d57619a900)

- `git/commit_helpers.py:1150-1159` `git stash push --staged -m spec-kitty-safe-commit:<uuid>` removes staged hunks from index AND worktree.
- `:1227-1240` `git stash pop --index <ref>` is refused by git for any stashed path with unstaged modifications; the pop is atomic → ALL stashed paths stay stashed; code raises `SafeCommitRecoveryFailed(orphan_stash_ref, commit_sha)`.
- `safe_commit` is already **path-scoped** (`paths=` param; see `autocommit.py:427`).
- `upgrade/autocommit.py:422-436` `except Exception: return (False, committed_paths, UPGRADE_COMMIT_SKIP_WARNING)` discards the typed error (+ its `commit_sha`/`orphan_stash_ref`); `cli/commands/upgrade.py:1159` renders a plain warning, run exits 0.
- Other callers (mission create/finalize/implement) already surface the typed error.

## Subtasks

### T023 — [RED FIRST] Regression repro
`tests/regressions/test_issue_4888_safe_commit_index_preservation.py` (`@pytest.mark.regression`),
real CLI subprocesses, isolated repos (mirror the issue's portable script):
- Control: unrelated file FULLY staged → `safe-commit` exit 0, `git diff --cached` byte-identical, no stash.
- Case 1: unrelated file PARTIALLY staged (staged hunk + unstaged hunk) + another fully staged → after `safe-commit <new>`: `git diff --cached` and `git stash list` byte-identical before/after (index untouched). (RED on base: index emptied into stash.)
- Assert the same index-preservation for `agent mission create`, `agent mission finalize-tasks`, `agent action implement`, and `upgrade` under the partially-staged state.
- `upgrade` forced-failure path: when a residual restore failure IS forced, the stash ref + landed SHA are surfaced and `upgrade` does not exit 0 with a message that hides the stash / misstates the landed commit.
Capture RED output; commit tests first.

### T024 — Root fix: commit via a temporary index
- Rewrite `safe_commit` to commit exactly the passed `paths` WITHOUT stashing the operator's index — e.g. a temporary `GIT_INDEX_FILE` populated with only `paths`, or `git commit --only -- <paths>` semantics — so the operator's index/worktree is never mutated.
- Remove/retire the `stash push --staged`/`pop --index` dance from the happy path.

### T025 — upgrade propagates the typed signal (defense-in-depth)
- Narrow `upgrade/autocommit.py:422-436` `except Exception` so `SafeCommitRecoveryFailed` (with `orphan_stash_ref` + `commit_sha`) propagates rather than flattening to `UPGRADE_COMMIT_SKIP_WARNING`.
- `cli/commands/upgrade.py` renders the stash ref + landed SHA; upgrade must not exit 0 with a message that hides the stash or misstates whether the commit landed. (This path is now residual — exercised in T023 by forcing the stash branch, so it does not guard dead code.)
- Fix the `implement` "Workspace allocation failed" message so it does not contradict a WP already `in_progress`/committed.

### T026 — Verify caller contract
- Confirm no `safe_commit` caller relies on "commit whatever is staged" beyond the passed `paths` (grep the ~28 call sites). If any does, adapt it to pass explicit `paths`. Record the audit in the tracer.

## Branch strategy

Planning base + merge target `fix/user-content-preservation`; PR later to upstream `main`. Worktree per lane from `lanes.json`.

## Definition of Done

- Regression RED on base, GREEN on fix; index+stash byte-identical across all callers; control green.
- `upgrade` honest on the forced-failure path; `implement` message consistent with status.
- Caller audit recorded; mypy --strict + ruff clean; complexity ≤ 15; no suppression.
- Targeted tests: `PWHEADLESS=1 .venv/bin/python -m pytest tests/regressions/test_issue_4888_*.py tests/git_ops/test_safe_commit_helper_integration.py tests/upgrade/test_upgrade_auto_commit_unit.py -q` — record counts. Extra breadth given the hot surface.

## Reviewer guidance (reviewer-renata, opus)

- The root fix removes index mutation entirely (temp index / --only) — the primary claim.
- It still commits EXACTLY `paths` (no behaviour change for the committed set) — the caller audit is load-bearing.
- FR-012 propagation is genuine defense-in-depth (residual stash path), not dead code.
