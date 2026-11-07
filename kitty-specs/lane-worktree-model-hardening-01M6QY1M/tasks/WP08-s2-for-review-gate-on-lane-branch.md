---
work_package_id: WP08
title: S2 - the for_review gate reads the lane branch ref
dependencies: []
requirement_refs:
- FR-010
- FR-011
- FR-012
- FR-013
- FR-014
- SC-003
- C-006
- NFR-008
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-worktree-model-hardening-01M6QY1M
base_commit: a4e342649cfe4936e89b4da0e8599dffc658ace2
created_at: '2026-11-06T09:40:35.763150+00:00'
subtasks:
- T042
- T043
- T044
- T045
- T046
phase: Phase 3 - S2/S3/S6 lanes carry no live status
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/lanes/test_lane_branch_commit_probe.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/_git.py
- src/specify_cli/lanes/for_review_gate.py
- tests/specify_cli/lanes/test_for_review_gate_parity.py
- tests/lanes/test_lane_branch_commit_probe.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 - S2: the for_review gate reads the lane branch ref

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP08 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP08 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

S2 (#7278). The shared `in_progress -> for_review` gate:

- FR-010: counts commits on `refs/heads/<lane>` beyond its base from the repository root (`git -C <repo root> rev-list --count --end-of-options <base>..refs/heads/<lane>`);
- FR-011: passes with the lane checkout absent when the lane branch carries a commit beyond its base;
- FR-012: refuses distinctly (`reason_code=LANE_BRANCH_MISSING`) when the branch ref is missing, naming the branch; never passes vacuously;
- FR-013: `agent status emit`, `orchestrator-api transition` and `move-task` give the same verdict with the checkout absent;
- FR-014: the "no commits" refusal names branch and base without asking to commit in a lane worktree; a ref beginning with `-` is never read as an option.

SC-003: with the checkout absent and a lane commit present, the move succeeds on all 3 surfaces; with the branch missing, it refuses with the distinct reason on all 3.

## Context & Constraints

- Read: spec User Story 2, FR-010 to FR-014, C-006; `research.md` R-3; `data-model.md` §3; `contracts/for-review-gate-refusal.md`; `contracts/error-codes.yaml` (`LANE_BRANCH_MISSING`, `LANE_NO_COMMIT_BEYOND_BASE`).
- Today the gate's only checkout dependency is `worktree.exists() and lane_has_commit_beyond_base(worktree, ...)` (`for_review_gate.py:~280`). With the checkout absent `move-task` passes while the other two refuse, which invites `--force`.
- The branch name comes from `lane_created_branch(manifest, lane)` (the authority `wp_evidence.lane_evidence_window` uses). Careful: `lane_created_branch("lane-planning")` resolves to the target (tracer friction); planning lanes keep today's behaviour.
- **Contract**: orchestrator-api envelope stays `TRANSITION_REJECTED` with the same data keys; the distinct reason is message text plus an internal `GateDecision.reason_code`. No version bump (C-012, SC-012).
- **C-006**: do NOT add a dirty-checkout refusal to the shared gate; `move-task`'s checkout-present checks stay in `move-task`.
- NFR-008: must pass on Linux and Windows CI lanes (no POSIX-only paths or shell features).
- C-011 red-first.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T042 - Red-first tests

Extend `tests/specify_cli/lanes/test_for_review_gate_parity.py` (real git fixture, real CLI and `orchestrator-api` entry points):

- `test_transition_passes_with_checkout_removed` (orchestrator-api transition)
- `test_status_emit_passes_with_checkout_removed`
- `test_move_task_parity_checkout_absent`
- `test_no_commit_refusal_names_branch_not_worktree` (message contains branch and base; no "worktree" / "commit in")
- `test_missing_lane_branch_refuses_distinct_reason` (all three surfaces; `reason_code == LANE_BRANCH_MISSING` internally)
- `test_reads_ref_not_lagging_checkout_head` (branch advanced from another checkout while the predicted checkout lags)
- `test_dash_prefixed_ref_not_option` (put in `tests/lanes/test_lane_branch_commit_probe.py` as a unit test of the probe; a branch/base starting with `-`)

Commit red.

### Subtask T043 - Tidy

- Add `lane_branch_has_commit_beyond_base(repo_root, base_ref, branch) -> bool | None` beside the checkout form in `lanes/_git.py`: `None` (or a typed result) when `refs/heads/<branch>` does not exist; uses `--end-of-options`. Keep the checkout form for its other callers.
- Extract `_code_lane_identity(manifest, lane)` in `for_review_gate.py` (behaviour-preserving).

### Subtask T044 - Gate on the ref

- Resolve the branch via `lane_created_branch`; probe the ref from the repository root; drop `worktree.exists()`.
- `GateDecision` gains `reason_code: str | None` (`LANE_BRANCH_MISSING`, `LANE_NO_COMMIT_BEYOND_BASE`; constants). Existing fields unchanged.

### Subtask T045 - Refusal text

- Reword per `contracts/for-review-gate-refusal.md`: name branch and base; remedy = commit on the lane (via `spec-kitty agent action implement <WP>`), never "commit in the lane worktree". Branch-missing text names the branch and suggests the lane-tip restore (`git branch <b> refs/spec-kitty/lane-tip/<b>`) only if that matches existing `DESTROYED_LANE` guidance.
- Repeated literals -> module constants.

### Subtask T046 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/specify_cli/lanes/test_for_review_gate_parity.py tests/lanes/test_lane_branch_commit_probe.py -q
uv run --frozen pytest tests/specify_cli/lanes tests/lanes tests/orchestrator_api tests/specify_cli/orchestrator_api -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -n auto --dist loadfile -k "status or move_task or for_review"   # out-of-matrix dir
uv run --frozen pytest tests/contract/test_orchestrator_api.py tests/architectural/test_layer_rules.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict src/specify_cli/lanes/_git.py src/specify_cli/lanes/for_review_gate.py
```

Never `make test-full` or a bare `tests/architectural/` sweep.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP08] ...**`, naming the trace file); the orchestrator appends them.

## Risks & Mitigations

- Count includes dependency-fold and planning merges; stale local ref in multi-clone flows: known residuals (R-3), out of scope.
- Envelope drift: `tests/contract/test_orchestrator_api.py` guards it.

## Review Guidance

- Three-surface parity with checkout absent; distinct missing-branch reason; no dirty refusal added to the shared gate; `--end-of-options` used; no contract bump.

## Definition of Done

- T042-T046 done; tests green on Linux; Windows-safe code; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T042 T043 T044 T045 T046 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP08 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
