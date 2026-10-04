---
work_package_id: WP02
title: next meta-corruption shift-left, single-branch e2e split, trio unmark (#5620 part 2)
dependencies: []
requirement_refs:
- FR-003
- FR-008
- NFR-001
- NFR-002
- C-001
- C-005
- NFR-003
planning_base_branch: issue-5618-regression-slice-cleanup
merge_target_branch: issue-5618-regression-slice-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-5618-regression-slice-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5618-regression-slice-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-regression-slice-cleanup-01M42WCF
base_commit: a145d6c1b4e150cdb851b34eb46a112a4805b2d6
created_at: '2026-10-04T07:29:48.567249+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Ledger follow-through (#5620)
history:
- at: '2026-10-04T07:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/next/
create_intent:
- tests/specify_cli/next/test_next_cmd_meta_dispatch.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/specify_cli/next/test_next_meta_corruption.py
- tests/specify_cli/next/test_next_cmd_meta_dispatch.py
- tests/integration/test_single_branch_write_checkout_e2e.py
- tests/characterization/test_trio_pure_cores.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – next meta-corruption shift-left, single-branch e2e split, trio unmark (#5620 part 2)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission regression-slice-cleanup-01M42WCF`). All feedback items must be addressed before the work is complete.

---

## Objectives & Success Criteria

- **Goal**: Move the #4642 meta-corruption pins to stub-level units at the `next_cmd` dispatch seams, split the single-branch write-checkout e2e to its non-redundant core, and unmark a pure truth table.
- **Independent test**: Removing both `except MissionMetaReadError` arms in `src/specify_cli/cli/commands/next_cmd.py` turns the new unit file red.
- **Issue**: #5620 — read the full issue body (ledger + planted-break table) before starting: `https://github.com/spec-kitty/spec-kitty/issues/5620`.
- Every removal (RETIRE, trimmed SHIFT-LEFT test, retired AST pin) has a planted-break record with a RED covering guard.

## Context & Constraints

- Spec: `kitty-specs/regression-slice-cleanup-01M42WCF/spec.md`; plan: `.../plan.md`; research: `.../research.md` (R-02 marker routing, R-03 planted breaks in worktrees).
- Charter: `.kittify/charter/charter.md` — Standing Order #4 (judge the test; red-first; never retry-to-green), `NO_FULL_HEAVY_SUITES_IN_MISSION`.
- Procedure: `packs/internal/procedures/test-suite-quality-assessment.procedure.yaml` (step: verify each fix/retirement with a planted break); built-in `test-desiderata-and-boundaries` and `testing-principles` styleguides; `development-assist-test-cleanup` procedure.
- `tests/regression/README.md` — what `regression` means and the exit rule for green pins.
- Ledger rows may be stale against current `main`: apply the verdict's intent to the file's current shape and record any deviation.

## Branch Strategy

- **Strategy**: lanes (execution worktree per computed lane from `lanes.json`)
- **Planning base branch**: `issue-5618-regression-slice-cleanup`
- **Merge target branch**: `issue-5618-regression-slice-cleanup`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implement command: `spec-kitty agent action implement WP02 --agent claude --mission regression-slice-cleanup-01M42WCF`

## Shared Protocol (binding for every subtask in this WP)

### Planted-break protocol (RETIRE / SHIFT-LEFT / FIX evidence — FR-008, C-005)

1. Work in this WP's lane worktree. Edit the named product file under `src/` to disable
   exactly the behaviour the guard names (the issue ledger names the edit; reproduce it).
2. Run ONLY the named guard files:
   `uv run --frozen pytest <guard files> -q -p no:randomly` — pytest's `pythonpath = src`
   makes the worktree's `src/` win for in-process tests. For tests that shell out to the
   `spec-kitty` CLI or `python -m specify_cli`, prefix `PYTHONPATH=$PWD/src`.
3. Record `N failed / M passed` (RED is required for a removal).
4. Revert: `git checkout -- src/` and confirm `git status --short src/` prints nothing.
   **A planted break is never committed.**
5. If the guard stays GREEN, the verdict flips to KEEP (or FIX): keep the test and say so.
6. Append one row per break to the WP's Activity Log and to the evidence file named in
   the WP (format: `| id | product edit | guard files | result | reverted |`).

### Marker edits

- MARKER-ONLY: remove `regression` (module `pytestmark` entry or decorator). Keep the
  tier markers (`fast`, `unit`, `integration`, `git_repo`, ...). If the test is left with
  no tier marker, add the marker its siblings in the same directory use.
- SPLIT-BY-KIND: move the marker from module level onto only the ledger-named tests
  (decorator), or split those tests into a sibling file — prefer the decorator unless the
  ledger says "split the file".
- Rewrite stale docstrings that call a green test "red-first" / "stays red on main": per
  `tests/regression/README.md` exit rule, say the defect is fixed and the test is a
  permanent guard; keep the issue number as history.
- Never touch `p0_repro` (C-003).

### Validation (run before handing to review)

```bash
uv run --frozen pytest <every file you touched> -q                 # record counts
uv run --frozen pytest <touched files> -q --durations=0 | tail -15  # before and after timing
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen pytest <touched files> -m regression --collect-only -q | tail -1
```

Run the marker gates once at the end of the WP:
`uv run --frozen pytest tests/architectural/test_marker_job_completeness.py tests/architectural/test_fast_tier_marker_completeness.py -q`.
Never run `make test-full` or whole heavy directories (C-002). If a test is red on
`origin/main` too, it is baseline: note it, do not fix it.

### Commits

- Conventional Commits, type `test` (e.g. `test(status): ...`). One logical change per commit;
  seam tests land in a commit BEFORE the commit that trims the slow test.
- Every commit message ends with the trailer
  `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`.
- No AI model identifiers in commit messages.
- Product code under `src/` is never changed (C-001). If a test exposes a real product
  defect, stop and report it; it becomes a filed issue, not a fix here.


## Subtasks & Detailed Guidance

### Subtask T006 – Add dispatch-mode unit tests for meta corruption
- **Purpose**: #5620 item 4 — `tests/specify_cli/next/test_next_meta_corruption.py` (24 s) is the sole guard of #4642: removing both `except MissionMetaReadError` arms in `next_cmd.py` reds only it (4/4).
- **Steps**:
  1. Read `src/specify_cli/cli/commands/next_cmd.py` `_dispatch_query_mode` (~line 276) and `_dispatch_advancing_mode` (~line 315) and how each handles `MissionMetaReadError` (plain vs `--json` output, exit code).
  2. Create `tests/specify_cli/next/test_next_cmd_meta_dispatch.py` (`fast`, `unit` — match siblings). Stub only the collaborator that raises `MissionMetaReadError` (the meta reader / runtime call the function delegates to) with `monkeypatch`; call the dispatch function directly; assert the observable result: exit code and the rendered message for plain and JSON mode (four tests: query×{plain,json}, advancing×{plain,json}).
  3. Planted break **P-5620-4**: delete both `except MissionMetaReadError` arms; the new file must go RED (all four). Revert.
- **Files**: new `tests/specify_cli/next/test_next_cmd_meta_dispatch.py` (~90 lines).
- **Notes**: each test < 1 s (NFR-002). Mock at the boundary the function calls, not internal helpers of the function under test.

### Subtask T007 – Trim `test_next_meta_corruption.py` to one CLI smoke
- **Steps**: after T006 is committed, keep the one CLI test that best exercises the real entry point end to end (prefer the JSON-mode advancing case); remove the rest. Drop `regression` from the kept smoke only if it no longer pins an open issue — #4642 is fixed, so drop it and keep the tier marker. Update the module docstring to name the unit file as the per-mode guard.
- **Evidence**: P-5620-4 run against the trimmed file + unit file: both RED.

### Subtask T008 – SPLIT-BY-KIND `tests/integration/test_single_branch_write_checkout_e2e.py`
- **Purpose**: #5620 item 5 — 10 tests, 67 s; 7 are covered by `tests/lanes/test_compute_lanes_single_branch.py`, `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`, `tests/core/test_mission_create_protected_single_branch.py`.
- **Steps**:
  1. Map each of the 10 tests to its covering guard (read each). Keep the for_review commit-gate trio (tests 4–6 in file order) and the lanes control.
  2. Planted breaks: **P-5620-5** disable the dirty-checkout refusal (`WRITE_CHECKOUT_DIRTY` in `src/specify_cli/lanes/implement_support.py`) → the covering refusal tests go RED; **P-5620-6** drop `commit_to_target` handling (`ProtectionPolicy.resolve_for_mission` or mission-create persistence) → its covering test goes RED. Add further breaks for any of the 7 whose guard is not one of these two behaviours. Revert each.
  3. Remove only tests whose covering guard went RED. Keep `regression` only if a kept test pins an open issue; otherwise drop it (keep `integration`/`git_repo`).
- **Files**: `tests/integration/test_single_branch_write_checkout_e2e.py`.

### Subtask T009 – Unmark `TestIsReviewRejectionEdge` in the trio characterization file
- **Purpose**: #5620 item 6 (optional, cheap) — a pure truth table carries `regression`.
- **Steps**: remove `regression` from `TestIsReviewRejectionEdge` only (class decorator or per-test marks); leave the rest of `tests/characterization/test_trio_pure_cores.py` as is. Confirm the class keeps a tier marker.

### Subtask T010 – Validate and record evidence
- Run the Validation block; record before/after durations for the two trimmed files and P-5620-4..6 rows.

## Risks & Mitigations

- A planted break left in `src/` → C-005 violation: run `git status --short src/` before every commit.
- A covering guard that stays green → the slower test is the last guard: keep it (verdict flips to KEEP).
- Removing a marker can drop a test out of every CI selection only if no tier marker remains: run the marker gates.

## Review Guidance

- Re-run at least one planted break per removal family yourself and confirm RED; confirm `git diff --stat origin/main -- src/` is empty.
- Check each removed test maps to a recorded RED guard; check each MARKER-ONLY file keeps a tier marker.
- Confirm seam tests landed in an earlier commit than the trims.

## Activity Log

- 2026-10-04T07:40:00Z – system – Prompt created.
