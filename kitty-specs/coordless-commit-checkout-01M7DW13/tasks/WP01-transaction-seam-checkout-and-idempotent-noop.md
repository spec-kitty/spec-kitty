---
work_package_id: WP01
title: Bookkeeping transaction takes its checkout from the seam and treats an unchanged tree as a no-op
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-005
- FR-007
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-003
planning_base_branch: fix/7633-7637-7648-coordless-commit-checkout
merge_target_branch: fix/7633-7637-7648-coordless-commit-checkout
branch_strategy: Planning artifacts for this mission were generated on fix/7633-7637-7648-coordless-commit-checkout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7633-7637-7648-coordless-commit-checkout unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Fixes
history:
- at: '2026-11-14T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/coordination/
create_intent:
- tests/coordination/test_coordless_status_commit_checkout.py
- docs/changelog/unreleased/7633-coordless-status-commit-checkout.fixed.md
- docs/changelog/unreleased/7648-idempotent-commit-unchanged-tree.fixed.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/coordination/transaction.py
- src/specify_cli/coordination/types.py
- src/specify_cli/git/commit_helpers.py
- tests/coordination/test_coordless_status_commit_checkout.py
- tests/specify_cli/coordination/test_transaction.py
- tests/architectural/test_no_write_side_rederivation.py
- docs/changelog/unreleased/7633-coordless-status-commit-checkout.fixed.md
- docs/changelog/unreleased/7648-idempotent-commit-unchanged-tree.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Bookkeeping transaction takes its checkout from the seam and treats an unchanged tree as a no-op

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- #7648: `BookkeepingTransaction.commit_idempotent` returns the no-op receipt pinned at HEAD when `safe_commit` raises `SafeCommitStagedTreeUnchanged`, even when `_worktree_has_pending_changes` failed open. No rollback, no `BookkeepingCommitFailed`. The strict `commit()` keeps raising (SC-003).
- #7633: the coordination-less arm of `BookkeepingTransaction._acquire_locked` takes its checkout from `placement_seam(...).write_dir(STATUS_STATE).surface_root` when the destination ref is the seam's `write_target(STATUS_STATE).ref`, else the repository root checkout; when that checkout's HEAD is not the destination ref it raises `BookkeepingPolicyRefused` with `STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH` before any write. All 11 rows of the matrix pass (SC-001).
- No raw holder probe remains in `transaction.py` (FR-003): `_write_branch_holder` is deleted and `_primary_partition_holder` consumes the seam.

## Context & Constraints

- Spec: `kitty-specs/coordless-commit-checkout-01M7DW13/spec.md` (FR-001, FR-002, FR-003, FR-005, FR-007).
- Plan: `kitty-specs/coordless-commit-checkout-01M7DW13/plan.md` (Engineering Alignment).
- Grounding: `docs/plans/engineering-notes/2026-11-14-7633-7637-7648-coordless-commit-checkout.md`.
- Operator ruling Q8 (option a): shape (b) refuses, never falls back to the root checkout (C-003). Shape (a) and the lane-holder row follow the same refusal (Decision Moment `01M7DW21P5D4WNVCGC6ARASAV3`, recommended option).
- C-001: consume `write_target` / `write_dir`; no second resolver. C-002: strict `commit()` unchanged.
- Charter: red first through the pre-existing entry point; no suppressions; ruff, ruff format, mypy clean.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `fix/7633-7637-7648-coordless-commit-checkout`
- **Merge target branch**: `fix/7633-7637-7648-coordless-commit-checkout`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implement with: `spec-kitty agent action implement WP01 --agent claude --mission coordless-commit-checkout-01M7DW13`

## Subtasks & Detailed Guidance

### Subtask T001 – Red #7648 tests

- **Purpose**: witness the fail-open rollback through `commit_idempotent`.
- **Steps**: in `tests/specify_cli/coordination/test_transaction.py` add a helper that commits one claim row through a first transaction, then acquires a second transaction staging the already-committed `status.events.jsonl`. Test 1: monkeypatch `specify_cli.coordination.transaction.status_entries` to raise `GitCommandError`; `commit_idempotent` must return `is_noop=True`, `commit_sha == HEAD`, and leave the log bytes unchanged. Test 2 (control): the strict `commit()` on the same state raises `BookkeepingCommitFailed` matching "nothing to commit".
- **Validation**: test 1 red, test 2 green on the base. Commit as a separate `test(...)` commit.

### Subtask T002 – No-op on the typed unchanged signal

- **Steps**: split the `safe_commit` call in `commit()` so `commit_idempotent` can treat `SafeCommitStagedTreeUnchanged` as its no-op: e.g. a private `_commit(message, *, unchanged_is_noop: bool)` that `commit()` calls with `False` and `commit_idempotent` with `True`. In the `True` case catch `SafeCommitStagedTreeUnchanged` (before the generic `except Exception`), record the no-op receipt exactly as the existing no-op arm does (`_committed`, `_explicit_commit_message`, `_explicit_commit_receipt`) and return it. Catch only the type, never the message text.
- **Validation**: T001 test 1 green; T001 test 2 and every `test_commit_idempotent_still_raises_*` stay green.

### Subtask T003 – Red #7633 matrix

- **Steps**: add `STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH` to `coordination/types.py` beside `DESTINATION_REF_NOT_FOUND`. Add `tests/coordination/test_coordless_status_commit_checkout.py` with the 11 rows of #7633 (builders reuse `tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py`). Each row asserts `(write, seam, read_door)`; write is a checkout label or `refused:<code>`.
- **Validation**: 7 rows green, 4 rows red on the base (lane-holder, both (a), (b)). Commit separately.

### Subtask T004 – Seam-chosen checkout plus hold check

- **Steps**: in the modern coordination-less branch of `_acquire_locked` (the `else` under `if genuinely_legacy:`), replace `_write_branch_holder(...)` with a helper that builds `placement_seam(repo_root, safe_mission_slug, owned=owned)`, compares `write_target(STATUS_STATE).ref` with the normalized destination ref, and returns `write_dir(STATUS_STATE).surface_root` or `repo_root`. Then read the checkout's symbolic HEAD; when it is not the destination ref raise `BookkeepingPolicyRefused(Refused(error_code=STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH, message=..., destination_ref=..., next_step=...))`. The message names the operation, the checkout and the ref; `next_step` tells the operator to check the ref out there (releasing it from the checkout that holds it). Do not probe the holder.
- **Notes**: the check runs before `_preflight_policy_verdict` and before any write (NFR-001). Keep the #2647 caller-contract comment, updated.

### Subtask T005 – PRIMARY arm through the seam

- **Steps**: `_primary_partition_holder(repo_root, slug, ref, owned)` returns `write_dir(WORK_PACKAGE_TASK).surface_root` when `write_target(WORK_PACKAGE_TASK).ref` equals the ref, else `repo_root`. No new refusal here. Delete `_write_branch_holder`. Update the FR-061 comments.
- **Validation**: the #7372 / FR-061 PRIMARY-arm tests stay green (`grep -rln "_primary_partition_holder\|commit_to_primary_target" tests/`).

### Subtask T006 – Docs, gate, changelog

- **Steps**: update the `_head_mismatch_holder` docstring in `git/commit_helpers.py` (it cites the transaction probe). In `tests/architectural/test_no_write_side_rederivation.py` repoint the `checkout_branch_or_fallback` entry from closed #2453 to open #1878. Add `docs/changelog/unreleased/7633-coordless-status-commit-checkout.fixed.md` and `7648-idempotent-commit-unchanged-tree.fixed.md` (Before/After style; run the style and spelling checks named in the fragments README).

### Subtask T007 – Blast radius

- **Steps**: run the matrix, `tests/specify_cli/coordination/`, `tests/coordination/`, `tests/status/`, the files that mention `BookkeepingTransaction`, and the named gates: `test_no_write_side_rederivation.py`, `test_layer_rules.py`, `test_no_dead_symbols.py`, `test_status_read_single_door.py`, `test_no_legacy_terminology.py`. Classify any red per CLAUDE.md before touching an assertion; surface an expectation edit to the operator.

## Test Strategy

- `uv run --frozen pytest tests/coordination/test_coordless_status_commit_checkout.py -n 6`
- `uv run --frozen pytest tests/specify_cli/coordination/ tests/coordination/ tests/status/ -n auto --dist loadfile`
- `uv run --frozen mypy src/specify_cli/coordination/transaction.py src/specify_cli/coordination/types.py`
- `uv run --frozen ruff check` / `ruff format --check --force-exclude` on changed files.

## Risks & Mitigations

- Tests that acquire a coordination-less transaction from a root checkout on a different branch now refuse; each is a stale shape or a real regression — classify, never silently edit.
- `write_dir` on a coordination-less topology is declared PRIMARY (no side effects); confirm no seeding is triggered.

## Review Guidance

- Verify red→green for T001 and T003 on the base (`d7cedd7e`).
- Verify no raw holder probe remains in `transaction.py` and no write happens before a refusal.
- Verify mypy/ruff on changed files.

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks status`
