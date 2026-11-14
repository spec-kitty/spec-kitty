---
work_package_id: WP02
title: Claim and legacy follow-up commits never fail on unchanged content
dependencies: []
requirement_refs:
- FR-004
- FR-006
- C-004
- C-005
- SC-002
planning_base_branch: fix/7633-7637-7648-coordless-commit-checkout
merge_target_branch: fix/7633-7637-7648-coordless-commit-checkout
branch_strategy: Planning artifacts for this mission were generated on fix/7633-7637-7648-coordless-commit-checkout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7633-7637-7648-coordless-commit-checkout unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
- T012
phase: Phase 1 - Fixes
history:
- at: '2026-11-14T20:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- docs/changelog/unreleased/7637-review-claim-protected-target.fixed.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/cli/commands/agent/workflow.py
- tests/integration/review/test_review_range_acceptance_action.py
- tests/specify_cli/cli/commands/agent/test_coord_commit_integrity_e2e.py
- docs/changelog/unreleased/7637-review-claim-protected-target.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Claim and legacy follow-up commits never fail on unchanged content

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
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- #7637: `agent action review WP02 --agent <name>` on a `lanes_with_coord` Mission targeting protected `main` exits 0, prints the review prompt and makes no commit attempt on `main` (SC-002, FR-004).
- Legacy-leaf residual (FR-006): `_commit_via_legacy_safe_commit`'s porcelain pre-check runs in the checkout the commit runs in (`repo_root`) and short-cuts only when every path is inside that checkout; `_resolve_legacy_porcelain_root` is deleted.

## Context & Constraints

- Spec: `kitty-specs/coordless-commit-checkout-01M7DW13/spec.md` (FR-004, FR-006).
- Plan: `kitty-specs/coordless-commit-checkout-01M7DW13/plan.md`.
- Grounding: `docs/plans/engineering-notes/2026-11-14-7633-7637-7648-coordless-commit-checkout.md`.
- Precedent: the implement claim commits `claim_status_pair_paths(...)` only (#5673, `workflow_executor.py` ~l.1011).
- #2684 phantom guard: a path in another checkout must never read as already committed.
- The T004 tests in `test_coord_commit_integrity_e2e.py` pin the deleted helper; replacing them is an asserted-expectation edit raised to the operator (recommended option 1).

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `fix/7633-7637-7648-coordless-commit-checkout`
- **Merge target branch**: `fix/7633-7637-7648-coordless-commit-checkout`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implement with: `spec-kitty agent action implement WP02 --agent claude --mission coordless-commit-checkout-01M7DW13`

## Subtasks & Detailed Guidance

### Subtask T008 – Red #7637

- **Steps**: in `tests/integration/review/test_review_range_acceptance_action.py` remove the `lanes_with_coord`-only protection lift from `_review_args` (it cites #7637 and must go when it is fixed). Update the docstring.
- **Validation**: the 8 `lanes_with_coord` cells fail on the base (exit 1, `PROTECTED_BRANCH_REFUSED`). Commit separately.

### Subtask T009 – Status pair only

- **Steps**: in `review_claim_transition` (`workflow_executor.py`), replace `paths=[actual_wp_path, *status_artifacts]` with `paths=claim_status_pair_paths(w._collect_status_artifacts(feature_dir))`; drop `actual_wp_path`. Update the "Atomic commit: WP file + all status artifacts" comment to say the claim writes no WP-file byte (#2816), so only the status pair joins the commit (#5673, #7637).
- **Validation**: T008 green; the other review fixtures stay green.

### Subtask T010 – Legacy-leaf behaviour tests (red first)

- **Steps**: replace the three `_resolve_legacy_porcelain_root` tests in `test_coord_commit_integrity_e2e.py` with tests through `_commit_via_legacy_safe_commit` (or `_legacy_paths_already_committed` plus the leaf): (1) a coordination-less Mission with a leftover `.worktrees/<slug>-coord` directory and status paths already committed in `repo_root` short-cuts to the already-committed receipt without calling `safe_commit` (red on the base: the pre-check runs in the leftover dir); (2) a path inside another registered checkout is never reported as committed (the #2684 phantom guard).
- **Validation**: (1) red, (2) green on the base.

### Subtask T011 – Pre-check in the commit's own checkout

- **Steps**: in `_commit_via_legacy_safe_commit`, set the porcelain root to `repo_root` and short-cut only when every path's containing checkout (`kernel.git_anchor.checkout_root_in_spelling`) resolves to `repo_root`. Delete `_resolve_legacy_porcelain_root` and update the WP01/T004 comment.
- **Validation**: T010 green; `tests/specify_cli/cli/commands/agent/test_workflow*.py` green.

### Subtask T012 – Changelog and blast radius

- **Steps**: add `docs/changelog/unreleased/7637-review-claim-protected-target.fixed.md`. Run `tests/integration/review/test_review_range_acceptance_action.py`, `tests/specify_cli/cli/commands/agent/test_coord_commit_integrity_e2e.py`, `tests/specify_cli/cli/commands/agent/test_workflow*.py`, the review integration tests that mention `review_claim_transition`, and `test_no_dead_symbols.py`.

## Test Strategy

- `uv run --frozen pytest tests/integration/review/test_review_range_acceptance_action.py -n 6`
- `uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_coord_commit_integrity_e2e.py tests/specify_cli/cli/commands/agent/ -k "workflow or review" -n auto --dist loadfile`
- mypy / ruff on changed files.

## Risks & Mitigations

- Another review path may rely on the WP file in the commit; the claim writes no byte to it since #2816, confirm with a grep for writes in the claim path.

## Review Guidance

- Verify red→green for T008 and T010(1) on the base.
- Verify no existence probe of `.worktrees/<slug>-coord` remains in the legacy leaf and nothing can be materialized by the pre-check.

## Progress & Status

- `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- `spec-kitty agent tasks status`
