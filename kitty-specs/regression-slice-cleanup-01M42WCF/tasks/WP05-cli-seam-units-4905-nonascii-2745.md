---
work_package_id: WP05
title: CLI seam units, 4905/non-ASCII shift-left, 2745 oracle fix (#5619 part 2)
dependencies: []
requirement_refs:
- FR-005
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
base_commit: 7bb8af736f7f37b368131205fbe9734ad3a06f15
created_at: '2026-10-04T07:32:02.899989+00:00'
subtasks:
- T022
- T023
- T024
- T025
- T026
- T027
phase: Phase 1 - Ledger follow-through (#5619)
history:
- at: '2026-10-04T07:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/agent/test_partition_paths_by_primary_kind.py
- tests/specify_cli/cli/commands/test_slugify_mission_input.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/specify_cli/cli/commands/agent/test_partition_paths_by_primary_kind.py
- tests/specify_cli/cli/commands/agent/test_issue_4905_coord_staging.py
- tests/specify_cli/cli/commands/test_slugify_mission_input.py
- tests/specify_cli/cli/commands/test_specify_json_nonascii.py
- tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – CLI seam units, 4905/non-ASCII shift-left, 2745 oracle fix (#5619 part 2)

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

- **Goal**: Add the missing seam unit tests for `workflow._partition_paths_by_primary_kind` and `lifecycle._slugify_feature_input`, then trim the 210 s #4905 file and the non-ASCII e2e to their smokes, and tighten the #2745 disjunctive oracle.
- **Independent test**: Planted break D (skip the partition) reds the new partition unit file; a slug break reds the new slug unit file; the tightened #2745 oracle goes red when the MissingLanes refusal is replaced by any other error mentioning 'required'.
- **Issue**: #5619 — read the full issue body (ledger + planted-break table) before starting: `https://github.com/spec-kitty/spec-kitty/issues/5619`.
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

Implement command: `spec-kitty agent action implement WP05 --agent claude --mission regression-slice-cleanup-01M42WCF`

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

### Subtask T022 – Seam units for `_partition_paths_by_primary_kind`
- Read `src/specify_cli/cli/commands/agent/workflow.py::_partition_paths_by_primary_kind` (~line 392) and its caller `_commit_via_coordination_transaction`. Create `tests/specify_cli/cli/commands/agent/test_partition_paths_by_primary_kind.py` (`fast`, `unit`): one test per path kind the 4905 e2e variants exercise (read `test_issue_4905_coord_staging.py`'s 12–13 variants and list the path shapes: status log, WP prompt, spec artifacts, code paths, mixed).
- Planted break **P-5619-D1**: return every path in one partition (or swap the partitions) → new file RED. Revert.
- Commit before T023.

### Subtask T023 – Trim `test_issue_4905_coord_staging.py` to 1–2 e2e
- Keep 1–2 end-to-end tests (the commit-target receipt path and one mixed-kind path); remove variants now pinned by T022 units.
- Planted break **P-5619-D** (ledger D): make `_commit_via_coordination_transaction` skip `_partition_paths_by_primary_kind`; the kept e2e, the T022 file and `tests/specify_cli/cli/commands/agent/test_workflow.py::TestImplementReceiptsNameRealBranch::test_target_branch_receipt_names_the_target_branch_not_coordination` must go RED. Revert.
- The kept e2e keep `regression` only if #4905 is still open (check with the GitHub issue); otherwise drop it and keep tier markers.

### Subtask T024 – Seam units for `_slugify_feature_input`
- `src/specify_cli/cli/commands/lifecycle.py::_slugify_feature_input` (~line 148) has no unit. Create `tests/specify_cli/cli/commands/test_slugify_mission_input.py` (`fast`, `unit`) from the slug cases in `test_specify_json_nonascii.py`; include, per the charter's Identifier Safety Rules, an accented Latin input and an `.isascii()` assertion on the output.
- Planted break **P-5619-S**: drop the ASCII normalisation (e.g. remove the `unicodedata` NFKD/`encode('ascii','ignore')` step or the `re.ASCII` flag) → new file RED. Revert. Commit before T025.

### Subtask T025 – Trim `test_specify_json_nonascii.py` to one `--json` e2e
- Keep one `--json` e2e (non-ASCII description in, valid JSON + ASCII slug out); remove the slug cases now held by T024. Re-run P-5619-S against the kept e2e + unit file (both RED).

### Subtask T026 – FIX the #2745 oracle
- `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py`: the no-flag oracle is `"lanes.json" in output or ... or "required" in output`. Tighten it to the MissingLanes error code/class the command emits (find the code in `src/specify_cli/lanes/persistence.py` `MissingLanesError` and how the merge/consolidate CLI renders it; assert the exact code token and exit code).
- Planted break **P-5619-2745**: make the command raise a different error whose message contains "required" instead of the MissingLanes refusal → old oracle GREEN, new oracle RED. Revert. Record both results.

### Subtask T027 – Validate and record evidence
- Run the Validation block; durations before/after for the two trimmed files; record P-5619-D, D1, S, 2745.

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
