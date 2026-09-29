---
work_package_id: WP07
title: Every REFUSE restores the target
dependencies: []
requirement_refs:
- FR-010
- FR-005
planning_base_branch: issue-5046-mixed-lane-authorship
merge_target_branch: issue-5046-mixed-lane-authorship
branch_strategy: Planning artifacts for this mission were generated on issue-5046-mixed-lane-authorship. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5046-mixed-lane-authorship unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mixed-lane-authorship-soundness-01M3M7Y0
base_commit: c04d2db37ab7446a9258599f0c340a5a90aeefcf
created_at: '2026-09-28T15:38:41.500275+00:00'
subtasks:
- T033
- T034
- T035
phase: Phase 3 - Gate (#5046)
history:
- at: '2026-09-28T16:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (post-tasks squad fold)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/executor.py
create_intent:
- tests/consolidation/test_refuse_restores_target.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/consolidation/executor.py
- tests/consolidation/test_refuse_restores_target.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Every REFUSE restores the target

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) before reading further.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. All feedback items are your TODO list.

---

## Objectives & Success Criteria

FR-010 (operator decision `01M3MAB8FTDKKVVTXPREK75AEP`, "Rollback on REFUSE only"): a reconciliation **REFUSE** restores the target branch to its pre-consolidation tip exactly as a FAIL does, via the existing compare-and-swap rollback. No new pre-mutation exit; no change to consolidation start ordering (C-004).

## Context & Constraints

- `src/specify_cli/consolidation/executor.py` `_phase_reconcile_before_teardown` (~`:2294-2343`): after `verify()`, `if result.status is VerifyStatus.FAIL: _rollback_target_after_failed_reconciliation(run)`; a REFUSE only raises `typer.Exit(1)`. The comment above claims a REFUSE "never advanced under a materialized claim, so there is nothing to revert" — false: the gate runs after `_phase_commit_and_assert`, and the claim (`_capture_reconciliation_claim`, `:2141`, called at `:3278` before any mutation) only has its `refusal` acted on inside `verify()` after the advance.
- `_rollback_target_after_failed_reconciliation` (`:2371`) is CAS-safe and a no-op when the pre-mutation tip is unknown or the target is already there; its docstring/name say "failed" — generalize wording (rename only if cheap; keep an alias if tests patch the old name: `tests/consolidation/test_merge_state_authority.py:500` covers it directly).
- `VerifyResult.recovery_guidance()` (`reconciliation.py:222-226`) tells the operator on REFUSE that "no refs/worktrees were mutated" — WP05 owns `reconciliation.py`; leave a note in the activity log so WP05 (or the orchestrator at closeout) corrects that sentence to reflect the restore.
- Do not touch `tests/integration/**` or consolidation start ordering / resume-marker logic (sibling slice: see the plan's C-004 note).

## Branch Strategy

- **Planning base / merge target**: `issue-5046-mixed-lane-authorship`. Workspace from `spec-kitty agent action implement WP07 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T033 – Red-first test

- `tests/consolidation/test_refuse_restores_target.py`: drive `_phase_reconcile_before_teardown` (or the smallest real entry that reaches it) with a run state whose target has advanced past `run.target_expected_old_sha` and whose claim yields a REFUSE (e.g. an `ApprovedWpCommitSet(refusal="...")`, or patch `MergeOutcomeVerifier.verify` to return `VerifyResult.refused(...)`). Assert `typer.Exit` with code 1 **and** the target ref equals `target_expected_old_sha` afterwards. Look at how `tests/consolidation/test_merge_state_authority.py` and `test_executor_terminus_integrity.py` build run states / real repos and reuse that style (real git repo in `tmp_path`, realistic SHAs).
- Commit this test first; it must be RED on the base (target stays advanced). Record the failing assertion line in the activity log.

### Subtask T034 – Roll back on REFUSE

- Change the condition to roll back on every non-PASS verdict (`FAIL` or `REFUSE`); rewrite the comment to state the invariant truthfully (after a non-zero exit from the gate, the target is at its pre-mutation tip; branches/worktrees retained; CAS fail-safe if the ref moved).
- Keep the function ≤ complexity 15.

### Subtask T035 – Tests

- REFUSE → restored (T033 now GREEN); FAIL → restored (unchanged behaviour, existing coverage — cite it); PASS → no rollback; REFUSE when the target already moved elsewhere (CAS mismatch) → warned, not overwritten; REFUSE with unknown pre-mutation tip → no-op.
- Run the executor/terminus neighbours that exercise the gate: `tests/consolidation/test_merge_state_authority.py`, `test_executor_terminus_integrity.py`, `test_reconciliation.py`, and `grep -rl "_phase_reconcile_before_teardown\|refused(" tests/consolidation tests/cli/commands` file by file; plus `tests/terminus/test_repro_5038.py` and `test_repro_5022.py` (squash refusal/rollback neighbours) — record counts.

## Test Strategy

```bash
uv run --frozen pytest tests/consolidation/test_refuse_restores_target.py tests/consolidation/test_merge_state_authority.py tests/consolidation/test_executor_terminus_integrity.py tests/consolidation/test_reconciliation.py -q
PWHEADLESS=1 uv run --frozen pytest tests/terminus/test_repro_5038.py tests/terminus/test_repro_5022.py -q
uv run --frozen pytest tests/architectural/test_merge_pipeline_ratchets.py -q
uv run --frozen ruff check src/specify_cli/consolidation/executor.py tests/consolidation/test_refuse_restores_target.py && uv run --frozen ruff format --check src/specify_cli/consolidation/executor.py tests/consolidation/test_refuse_restores_target.py
uv run --frozen mypy src/specify_cli/consolidation/executor.py
```

## Risks & Mitigations

- A test somewhere may assert that a refused target stays advanced (e.g. resume flows): grep `refused` / `Reconciliation refused` in tests and judge each (stale assertion → re-pin with rationale; valid → escalate).

## Review Guidance

- Confirm red→green of T033 and that the rollback is the existing CAS helper (no new ref-writing code).
- Confirm the corrected comment and that no start-ordering / resume-marker code changed.

## Activity Log

- 2026-09-28T16:20:00Z – system – Prompt created.
