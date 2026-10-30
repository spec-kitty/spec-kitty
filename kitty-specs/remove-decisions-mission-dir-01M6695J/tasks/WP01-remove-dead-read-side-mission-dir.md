---
work_package_id: WP01
title: Remove the dead read-side decisions _mission_dir and pin the write-side-only STATUS_STATE access invariant
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
planning_base_branch: issue-6766-remove-decisions-mission-dir
merge_target_branch: issue-6766-remove-decisions-mission-dir
branch_strategy: Planning artifacts for this mission were generated on issue-6766-remove-decisions-mission-dir. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6766-remove-decisions-mission-dir unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-remove-decisions-mission-dir-01M6695J
base_commit: b0ed912d269fe56174c9a6a2281700eb18f4d0fd
created_at: '2026-10-30T11:35:53.684375+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Dead-code removal
history:
- at: '2026-10-30T12:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent:
- tests/specify_cli/decisions/test_service_status_state_access.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/decisions/service.py
- tests/specify_cli/test_read_seam_leniency.py
- tests/specify_cli/decisions/test_service_status_state_access.py
- docs/changelog/CHANGELOG.md
- docs/development/reference/read-side-seam-classification.md
- tests/decisions/test_decisions_reconciler.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Remove the dead read-side decisions `_mission_dir`

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

- `src/specify_cli/decisions/service.py` no longer defines or mentions
  `_mission_dir`; every STATUS_STATE access in the module is a write-side
  pre-resolution (`_write_mission_dir` / `_write_events_path`).
- The two orphaned pins in `tests/specify_cli/test_read_seam_leniency.py`
  are gone and that file's module-docstring site ledger no longer counts
  `decisions/service.py` as a migrate-fail-loud site.
- A new guard test pins the invariant and was RED on the planning base.
- The changelog carries an `[Unreleased]` entry for #6766.
- All validation commands pass (see Test Strategy).

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6766. PR #6762 (#4848) moved the decisions
  opened-row check onto the pre-resolved write-side `events_path`; the
  read-side `_mission_dir` at `service.py:335` has had no `src/` caller
  since.
- Read the mission artifacts first:
  `kitty-specs/remove-decisions-mission-dir-01M6695J/spec.md` (FR-001..FR-004),
  `plan.md` (IC-01), `research.md` (grounding evidence and gate survey).
- **Out of scope (C-001)**: `src/specify_cli/decisions/emit.py` and its own
  live `_mission_dir` (the COORD writer census entry in
  `tests/architectural/test_no_write_side_rederivation.py`). Do not touch
  that file or that gate file. `_PRE_SPLIT_QUALNAMES` stays as-is: it keys
  off the census pair `("src/specify_cli/decisions/service.py",
  "_write_mission_dir")` for the red-at-base proof only.
- **No gate suppression (C-002)**: no `# noqa`, no allowlist entry, no skip,
  no xfail to make anything green.
- Follow `.kittify/charter/charter.md` and `AGENTS.md` code rules: new code
  passes ruff and mypy with zero issues; formatting gate
  (`ruff format --check --force-exclude <files>`) is separate from lint.
- Never run a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Branch Strategy

- **Strategy**: single branch `issue-6766-remove-decisions-mission-dir`
- **Planning base branch**: `issue-6766-remove-decisions-mission-dir`
- **Merge target branch**: `main` (via pull request; the operator merges)

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first STATUS_STATE-access guard test

- **Purpose**: Pin the standing invariant that all STATUS_STATE access in
  `decisions/service.py` is write-side; prove it red on the planning base
  (charter ATDD-First Discipline, DIRECTIVE_034/041).
- **Steps**:
  1. Create `tests/specify_cli/decisions/test_service_status_state_access.py`.
  2. Parse `src/specify_cli/decisions/service.py` with `ast` and assert that
     no call in the module is `placement_seam(...).read_dir(...)` with the
     argument `MissionArtifactKind.STATUS_STATE` (an attribute access chain
     check). Write it as a focused, non-vacuous guard: name the invariant,
     reference #6766 and #4848 in the docstring, and assert the module still
     DOES resolve `write_dir(STATUS_STATE)` (positive control, so the guard
     cannot pass vacuously if the seam import moves).
  3. Run it: it must FAIL on the planning base (the dead `_mission_dir`
     holds exactly such a `read_dir(STATUS_STATE)` call at service.py:358).
  4. Commit the test alone first (`test(decisions): pin write-side-only
     STATUS_STATE access in the decisions service`).
- **Files**: `tests/specify_cli/decisions/test_service_status_state_access.py` (new).
- **Parallel?**: No.
- **Notes**: The guard is file-scoped by design; a future change that
  legitimately needs a read-side STATUS_STATE read in this module updates the
  guard with rationale in the same PR.

### Subtask T002 – Delete `_mission_dir` from service.py

- **Purpose**: Remove the dead helper (FR-001).
- **Steps**:
  1. Delete the whole `_mission_dir` function (definition + docstring) from
     `src/specify_cli/decisions/service.py`.
  2. Re-run the T001 guard: it must now PASS.
  3. Repo-wide sanity grep: `grep -rn "service\._mission_dir\|from
     specify_cli.decisions.service import.*_mission_dir" src/ tests/`
     returns nothing.
- **Files**: `src/specify_cli/decisions/service.py`.
- **Parallel?**: No (after T001).

### Subtask T003 – Re-point stale docstrings/comments

- **Purpose**: No prose in `service.py` names the deleted symbol (FR-003).
- **Steps**: Update these mentions (keep the historical rationale, drop the
  dangling symbol references):
  1. `_resolve_mission_id`'s comment (~lines 289-299): "Resolving this read
     through ``_mission_dir`` ..." and "stays COORD-routed via
     ``_mission_dir``" — rewrite to name the read/write split without the
     deleted helper.
  2. `_write_mission_dir` docstring: "the write-side counterpart of
     :func:`_mission_dir`" — drop the counterpart clause.
  3. `_ledger_dir` docstring: "Previously this resolved through
     ``_mission_dir`` -> ``STATUS_STATE``" — keep the history, rephrase
     without naming the deleted helper (e.g. "a read-side STATUS_STATE
     resolution that no longer exists").
  4. `open_decision` comment (~line 866): "NOT the COORD-partition
     ``_mission_dir`` used for ``status.events.jsonl`` below" — re-point at
     `_write_events_path`.
  5. Terminal-write comment (~line 1076): same treatment.
  6. Update the WP06 ledger row for `decisions/service.py` in
     `docs/development/reference/read-side-seam-classification.md` (line
     ~793) to record the site's removal — follow the ledger's own
     "(removed, #NNNN)" row convention (see the `dashboard/scanner.py`
     row): mark the file `(removed, #6766)`, zero real sites, and keep a
     one-line rationale (the read-side `_mission_dir` was deleted by #6766,
     caller-less since #6762; all STATUS_STATE access is write-side).
     Spec-squad finding: the ledger row documents the very site being
     deleted and would otherwise go stale.
- **Files**: `src/specify_cli/decisions/service.py`,
  `docs/development/reference/read-side-seam-classification.md`.
- **Parallel?**: No.

### Subtask T004 – Drop the orphaned leniency pins

- **Purpose**: The two tests exercise only the deleted helper (FR-002).
- **Steps**:
  1. Delete `test_decisions_mission_dir_fails_loud_when_coord_deleted` and
     `test_decisions_mission_dir_preserves_healthy_status_home` from
     `tests/specify_cli/test_read_seam_leniency.py`.
  2. Correct the module docstring's migrate-fail-loud ledger: the
     "``decisions/service.py`` (1)" entry leaves with the helper (the other
     two clusters — `coordination/status_transition.py` (3) and
     `review/cycle.py` (1) — stay). Also fix the docstring's ledger path:
     it cites `docs/development/read-side-seam-classification.md`; the file
     lives at `docs/development/reference/read-side-seam-classification.md`
     (spec-squad finding, pre-existing).
  3. If `decisions_service` / `CoordinationBranchDeleted` imports become
     unused in that file, remove them (ruff will flag).
- **Files**: `tests/specify_cli/test_read_seam_leniency.py`.
- **Parallel?**: No.

### Subtask T005 – Changelog entry

- **Purpose**: User-facing dead-code removal is still changelog-worthy
  (issue asks for it; charter changelog discipline).
- **Steps**: Add under `[Unreleased]` in `docs/changelog/CHANGELOG.md`: bold
  impact-first lead with `(#6766)`, then before/after, under 1,200
  characters. Match the existing entry style in that file.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: No.

### Subtask T006 – Validation surface

- **Purpose**: Prove the change (NFR-001) and record evidence.
- **Steps**: Run and record (commands + passed/failed counts) —
  - `uv run --frozen python -m pytest tests/decisions/ -q`
  - `uv run --frozen python -m pytest tests/specify_cli/decisions/ -q`
  - `uv run --frozen python -m pytest tests/specify_cli/test_read_seam_leniency.py -q`
  - `uv run --frozen python -m pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_no_write_side_rederivation.py -q`
  - `uv run --frozen ruff check src/specify_cli/decisions/service.py tests/specify_cli/test_read_seam_leniency.py tests/specify_cli/decisions/test_service_status_state_access.py`
  - `uv run --frozen ruff format --check --force-exclude <the same files>`
  - `uv run --frozen mypy src/specify_cli/decisions/service.py` (match the
    project's mypy invocation; use the repo's configured command)
  - Baseline: `make test-fast` is the shared baseline for ordinary changes —
    run it if time allows and record the result.
- Classify every red against the merge base before touching it
  (AGENTS.md baseline-red gotcha). A pre-existing red with no tracker issue
  gets one filed (Pre-existing Failure Reporting Rule).
- **Parallel?**: No.

## Test Strategy

- The red-first guard (T001) is the ATDD anchor: red on planning base, green
  on WP head; the reviewer verifies both.
- Every test you write or change plus your blast radius must run and be
  recorded (commands + counts) — that is T006.
- No full heavy suites; targeted files and the named gates only.

## Risks & Mitigations

- Guard over-constrains → documented update path (rationale + same-PR guard
  edit).
- Hidden callers → repo-wide grep + full owning-submodule suites.
- Docstring rewrites accidentally changing semantics → comments only; no
  code changes in T003; the module suites prove it.

## Review Guidance

- Verify red→green: the guard test commit precedes the removal commit; run
  the guard on the planning base (red) and on the WP head (green).
- Verify SC-001 (`grep -c "_mission_dir" src/specify_cli/decisions/service.py`
  → 0) and that `decisions/emit.py` is untouched in the diff.
- Confirm no allowlist/baseline/gate file changed (except none should).
- Confirm the changelog entry is under 1,200 characters and carries `(#6766)`.

## Progress & Status

Record with `spec-kitty agent tasks mark-status T001 --status done` (etc.)
and `spec-kitty agent tasks add-history WP01 --note "..."`.
