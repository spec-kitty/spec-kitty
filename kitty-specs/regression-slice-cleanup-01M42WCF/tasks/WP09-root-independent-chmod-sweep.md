---
work_package_id: WP09
title: Root-independent sweep of the other chmod-unreadable tests (#5622)
dependencies: []
requirement_refs:
- FR-007
- NFR-003
- C-001
- SC-004
planning_base_branch: issue-5618-regression-slice-cleanup
merge_target_branch: issue-5618-regression-slice-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-5618-regression-slice-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5618-regression-slice-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-regression-slice-cleanup-01M42WCF
base_commit: 2507d92e9b151878b7c30b9780afbd35ae5b0462
created_at: '2026-10-04T08:11:31.872846+00:00'
subtasks:
- T042
- T043
- T044
- T045
phase: Phase 1 - Ledger follow-through (#5622)
history:
- at: '2026-10-04T07:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/dossier/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- tests/specify_cli/upgrade/migrations/test_provision_kitty_env.py
- tests/dossier/test_indexer.py
- tests/specify_cli/dossier/test_integration.py
- tests/dossier/test_hasher.py
- tests/kernel/test_guarded_read.py
- tests/specify_cli/test_mission_brief_missing_vs_corrupt.py
- tests/upgrade/test_migration_robustness.py
- tests/specify_cli/test_meta_read_permission_denied_regression.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP09 – Root-independent sweep of the other chmod-unreadable tests (#5622)

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

- **Goal**: #5622 also asks to 'add the same guard to any other chmod-based unreadable-path test'. A root run of every chmod-touching test file on the base found 16 tests in these 8 files that fail under uid 0 for the same reason (root bypasses mode bits). Make each give the same verdict as root and non-root.
- **Independent test**: Running the 8 files as uid 0 yields 0 failures (base: 16 failed).
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

Implement command: `spec-kitty agent action implement WP09 --agent claude --mission regression-slice-cleanup-01M42WCF`

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

### Subtask T042 – Reproduce the 16 root failures
- As root: `python -m pytest <the 8 owned files> -q -p no:randomly` → record the failing node ids (base run found: test_provision_kitty_env TestClaudeignoreSymlinkSafety::test_permission_denied_still_raised_on_readonly_claudeignore; dossier/test_indexer x3; specify_cli/dossier/test_integration x2; dossier/test_hasher x2; kernel/test_guarded_read x1; test_mission_brief_missing_vs_corrupt x1; upgrade/test_migration_robustness x1; test_meta_read_permission_denied_regression x5).

### Subtask T043 – Inject the failure at the I/O seam (preferred)
- Follow WP08's pattern (commit a95c9725 on lane-h; read `tests/charter/test_pack_manager.py` `[unreadable]` and `tests/cli/commands/test_charter_io.py`): replace `chmod(0)`-style setup with a `monkeypatch` of the exact read/write call the code under test performs (`Path.read_bytes`, `Path.read_text`, `open`, `os.open`, `Path.write_text` …) raising `PermissionError` ONLY for the target path and delegating to the original for every other path. Keep the test's assertions unchanged.
- For a write-side test (read-only file, e.g. `.claudeignore`, `.gitignore`) patch the write seam the same way.

### Subtask T044 – Skip under root only where no single seam exists
- If the code under test reaches the file through several calls or a subprocess, use `pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root bypasses file mode bits (#5622)")` on that test only, and say why in the report. Prefer T043.

### Subtask T045 – Planted breaks and validation
- For each seam-injected test family plant a break that makes the product swallow/ignore the `PermissionError` (e.g. catch-and-return-empty at the read site) and confirm the test goes RED; revert.
- As root, all 8 files: 0 failed. Run the Validation block (ruff, format with --force-exclude, mypy on changed files if feasible; report pre-existing mypy errors without fixing unrelated code).

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
