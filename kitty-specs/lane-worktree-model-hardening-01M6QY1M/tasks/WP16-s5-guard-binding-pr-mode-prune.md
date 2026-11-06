---
work_package_id: WP16
title: 'S5 binding after #7275 - guard entry, pr-mode cleanup, prune backstop (BLOCKED)'
dependencies:
- WP06
- WP09
- WP15
requirement_refs:
- FR-036
- FR-037
- FR-039
- SC-006
- C-004
- NFR-008
- NFR-005
- NFR-006
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T100
- T101
- T102
- T103
- T104
- T105
- T106
phase: Phase 6 - S5 cleanup as the last consolidation step
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent:
- src/specify_cli/git/destructive_guard.py
- tests/acceptance/test_pr_mode_lane_cleanup.py
- tests/specify_cli/workspace/test_landed_worktrees_mission_lane_prune.py
- tests/consolidation/test_lane_remover_guard_binding.py
- docs/changelog/unreleased/7280-pr-mode-lane-cleanup.changed.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/git/destructive_guard.py
- src/specify_cli/acceptance/__init__.py
- src/specify_cli/workspace/landed_worktrees.py
- src/specify_cli/cli/commands/_landed_worktree_doctor.py
- tests/architectural/test_destructive_op_routing.py
- tests/acceptance/test_pr_mode_lane_cleanup.py
- tests/specify_cli/workspace/test_landed_worktrees_mission_lane_prune.py
- tests/consolidation/test_lane_remover_guard_binding.py
- docs/changelog/unreleased/7280-pr-mode-lane-cleanup.changed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP16 - S5 binding after #7275: guard entry, pr-mode cleanup, prune backstop

> ## ⛔ BLOCKED until PR #7275 merges into `main` and `issue-7276-lane-worktree-hardening` is rebased onto it.
> This WP is OUT of the first PR cut. Do not start it (or stop at T100) while #7275 (`issue-7211-safe-landed-prune`, S4 guard + ADR `2026-11-06-1`) is unmerged. `src/specify_cli/git/destructive_guard.py`'s `guarded_landed_removal` exists only on that branch.
>
> **Exit rule (analysis C2).** WP16 stays `planned`. If #7275 has not merged into `main` by the time every other WP of this Mission is approved, WP16 is **canceled** with a recorded rationale (`spec-kitty agent tasks move-task WP16 --to canceled --force --note "#7275 unmerged at approval of all other WPs; deferred to follow-up #<n>"`), a new follow-up issue is opened for the S5 guard binding, and FR-036, FR-037, FR-039 and SC-006 are recorded **deferred-with-followup** (naming that issue) in `issue-matrix.json`. `accept` and `consolidate` then proceed without WP16.

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP16 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP16 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

- FR-037 / C-004: bind WP15's `LaneRemover` port to the #7264 proof entry `guarded_landed_removal(repo_root, LandedRemoval(worktree, branch, tip, remote, landing_ref), context=, processes_in=, absorbed=)`, with the O3-local landing proof (target at `reconciliation_passed_target_sha`; relaxes `_assert_named_landing_ref`), and update the destructive-op routing pins in `tests/architectural/test_destructive_op_routing.py`.
- FR-036 / SC-006: a committed `accept --mode pr` removes, through the same module, each lane whose tip the pushed PR head absorbs, before the PR merges; unpushed lanes are kept and reported (`NOT_LANDED_ON_NAMED_REMOTE`); no raw `git worktree remove` / `git branch -d` advice is printed.
- FR-039: `doctor workspaces --prune` treats a lane of a consolidated or pr-accepted Mission as a removal candidate under the same proofs when no consolidation record is active and no retention is declared. Positive control: an active record keeps the lane report-only.
- A-11 / NFR-008: "probe unavailable means keep and report" (macOS/Windows keep lanes and report; branch cleanup unaffected).

## Context & Constraints

- Read: spec User Story 6 scenario 5, FR-036, FR-037, FR-039, A-11, C-004, C-005; `research.md` R-9; `data-model.md` §6 (`LandingProof`); WP03's `kitty-specs/lane-worktree-model-hardening-01M6QY1M/upstream/adr-2026-11-06-1-amendment-draft.md` (the O3-local proof, scratch exemption, lane-tip/tombstone ops as guarded) and the merged ADR `docs/adr/4.x/2026-11-06-1-a-destructive-git-operation-discharges-named-proof-obligations.md`; design-decisions trace entry "S4 coordination (session for PR #7275)".
- C-005: consume S4's proof list; do not redesign it. The O3-local variant in `destructive_guard.py` is coordinated with the #7275 owner: if they prefer to own it, they land it and you only bind.
- Shared files: `consolidation/lane_cleanup.py` is owned by WP15 - your binding hunk is out-of-map. `workspace/landed_worktrees.py` you own; WP09 already changed the printed recreate command there (keep it).
- `cli/commands/accept.py` belongs to WP06; edit only `acceptance/__init__.py`.
- Changelog: this WP adds its own fragment `docs/changelog/unreleased/7280-pr-mode-lane-cleanup.changed.md` (WP18 covers the rest of #7280); rename to the PR number when known per `docs/changelog/unreleased/README.md`.
- C-011 red-first.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T100 - Precondition check

- `git log origin/main --oneline | grep -i 7275` or check the merged ADR file on `main`; confirm the topic branch contains it (`git merge-base --is-ancestor <7275 merge> HEAD`). If not: stop, move the WP back with a note ("blocked on #7275"), and report. Do not stack on the #7275 branch (research R-9 alternative (a) rejected).

### Subtask T101 - Red-first tests

- `tests/acceptance/test_pr_mode_lane_cleanup.py`: `test_pr_mode_removes_absorbed_lanes_before_pr_merge` (SC-006), `test_pr_mode_keeps_unpushed_lane_reported`, `test_no_raw_worktree_remove_advice`.
- `tests/specify_cli/workspace/test_landed_worktrees_mission_lane_prune.py`: `test_prune_candidates_consolidated_mission_lane`, control `test_active_record_keeps_lane_report_only`.
- `tests/consolidation/test_lane_remover_guard_binding.py`: `test_detached_mid_rebase_lane_kept_worktree_tip_moved`, `test_branch_advanced_after_claim_kept`, `test_never_force_pin`, `test_probe_unavailable_keeps_and_reports` (monkeypatch the process probe to "unavailable").

### Subtask T102 - O3-local proof variant

- In `git/destructive_guard.py`: a landing proof for "the local target is at the gate-passed tip" alongside the named-remote proof. Keep every other proof obligation unchanged.

### Subtask T103 - Bind the port

- `lane_cleanup.py` (out-of-map): `GuardedLaneRemover` implementing `LaneRemover` via `guarded_landed_removal`; consolidate passes `LocalTargetAtPass`, pr-mode passes `RemoteRef`. Guard refusals map to `KEPT` with the guard code.

### Subtask T104 - pr-mode cleanup

- `acceptance/__init__.py`: after a committed pr-mode acceptance, compute lanes absorbed by the pushed PR head and run the module; remove the raw advice strings; print the cleanup report.

### Subtask T105 - Prune backstop and destructive-op routing pins

- `workspace/landed_worktrees.py` + `cli/commands/_landed_worktree_doctor.py`: Mission lanes of consolidated/pr-accepted Missions become candidates (no active record, no retention). `tests/architectural/test_destructive_op_routing.py`: add the new call sites to the destructive-op routing set (empty allowlist preserved).
- NFR-005 (idempotence): `test_prune_second_run_changes_nothing` in `tests/specify_cli/workspace/test_landed_worktrees_mission_lane_prune.py`: a second `doctor workspaces --prune` run on the same fixture removes nothing and reports no candidate.
- NFR-006: the amended `test_destructive_op_routing.py` stays <= 5 s (`--durations` in Validation).

### Subtask T106 - Quality gates, blast radius, changelog

- Write the fragment (Before/After/What to do style per the README).

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/acceptance/test_pr_mode_lane_cleanup.py tests/specify_cli/workspace/test_landed_worktrees_mission_lane_prune.py tests/consolidation/test_lane_remover_guard_binding.py tests/architectural/test_destructive_op_routing.py -q
uv run --frozen pytest tests/acceptance tests/specify_cli/workspace tests/consolidation tests/git -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py -q      # out-of-matrix dir
uv run --frozen pytest tests/specify_cli/cli/commands/test_accept_*.py -q -n auto --dist loadfile   # out-of-matrix: acceptance/__init__.py (pr-mode cleanup step)
uv run --frozen pytest tests/specify_cli/workspace/test_landed_worktrees.py -q
uv run --frozen pytest tests/architectural/test_destructive_op_routing.py -q --durations=5   # NFR-006: the amended gate stays <= 5 s
make test-fast
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict <touched src files>
```

Never `make test-full` or a bare `tests/architectural/` sweep.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP16] ...**`, naming the trace file); the orchestrator appends them.

## Risks & Mitigations

- #7275 API drift: bind against what merged, not the draft.
- Off-Linux removal without a process proof: forbidden (keep and report).

## Review Guidance

- Bound to the S4 entry, O3-local proof, never `--force`; pr-mode removes absorbed lanes before merge; prune control holds; routing pins updated.

## Definition of Done

- T100-T106 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T100 T101 T102 T103 T104 T105 T106 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP16 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
