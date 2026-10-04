---
work_package_id: WP08
title: Root-independent unreadable-path tests (#5622)
dependencies: []
requirement_refs:
- FR-007
- C-001
- SC-004
- NFR-003
planning_base_branch: issue-5618-regression-slice-cleanup
merge_target_branch: issue-5618-regression-slice-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-5618-regression-slice-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5618-regression-slice-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-regression-slice-cleanup-01M42WCF
base_commit: 2f2c8108538bba600e6b2d33056d1bc7722aabe7
created_at: '2026-10-04T07:33:54.387062+00:00'
subtasks:
- T038
- T039
- T040
- T041
phase: Phase 1 - Ledger follow-through (#5622)
history:
- at: '2026-10-04T07:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- tests/charter/test_pack_manager.py
- tests/cli/commands/test_charter_io.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Root-independent unreadable-path tests (#5622)

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

- **Goal**: Make the chmod-based unreadable-path tests give the same verdict as root and non-root, and apply the same guard to any other chmod-unreadable test in these files.
- **Independent test**: Run as root (this container is uid 0): `tests/charter/test_pack_manager.py::test_preparation_refuses_broken_required_inputs[unreadable]` and `tests/cli/commands/test_charter_io.py::test_resolve_charter_path_raises_when_directory_not_readable` fail before and do not fail after.
- **Issue**: #5622 — read the full issue body (ledger + planted-break table) before starting: `https://github.com/spec-kitty/spec-kitty/issues/5622`.
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

Implement command: `spec-kitty agent action implement WP08 --agent claude --mission regression-slice-cleanup-01M42WCF`

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

### Subtask T038 – Reproduce as root
- `id -u` (expect 0). Run both node ids on the base; record the failure (red-first evidence).

### Subtask T039 – Fix `test_preparation_refuses_broken_required_inputs[unreadable]`
- Prefer injecting the failure at the I/O seam: monkeypatch the read the preparation code performs (find it in `src/charter/...pack_manager...`) to raise `PermissionError` for that path, so the refusal is exercised for every uid. If the seam is not a single call, skip the `unreadable` param under `os.geteuid() == 0` with `reason="root bypasses file mode bits (#5622)"` (use `pytest.param(..., marks=pytest.mark.skipif(...))`; guard `hasattr(os, "geteuid")` for Windows).

### Subtask T040 – Fix `test_resolve_charter_path_raises_when_directory_not_readable`
- Same approach: patch the directory-read seam to raise `PermissionError`, or skipif root with the same reason.

### Subtask T041 – Sweep the two files for other chmod-unreadable tests and validate
- `grep -n "chmod" tests/charter/test_pack_manager.py tests/cli/commands/test_charter_io.py`; apply the same treatment. List (do not edit) other chmod-unreadable tests elsewhere in `tests/` in the Activity Log for a follow-up issue (`git grep -n "chmod(0o000\|chmod(0o\(0\|2\|3\)00" tests/`).
- Validation: run both files as root (all pass/skip, none fail); run the Validation block.

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
