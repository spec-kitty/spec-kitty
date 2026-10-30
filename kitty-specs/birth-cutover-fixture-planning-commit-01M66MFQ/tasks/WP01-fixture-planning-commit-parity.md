---
work_package_id: WP01
title: Fixture planning-commit parity for the birth-cutover anchor tests
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
- C-001
- C-002
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6801-birth-cutover-fixture-planning-commit
merge_target_branch: issue-6801-birth-cutover-fixture-planning-commit
branch_strategy: Planning artifacts for this mission were generated on issue-6801-birth-cutover-fixture-planning-commit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6801-birth-cutover-fixture-planning-commit unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Fixture repair
history:
- at: '2026-10-30T14:52:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/migration/
create_intent: []
execution_mode: code_change
owned_files:
- tests/migration/test_birth_cutover.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Fixture planning-commit parity for the birth-cutover anchor tests

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

- The four anchor tests of `tests/migration/test_birth_cutover.py` — `test_birth_cutover_reconciles_at_merge_no_manual_backfill[coord|lanes]` and `test_birth_cutover_status_phase_is_primary_only[coord|lanes]` — pass on this branch (SC-001: the file reports 24 passed, 0 failed; it was 4 failed, 20 passed on `main@512567eee7`).
- The fixture's `LanesManifest` records a real `planning_commit_sha`, captured the way the production finalize path captures it (FR-001, NFR-002).
- A failed capture fails the fixture at setup with a named assertion instead of a claim-time refusal three stages later (FR-002).
- No assertion, gate or marker is changed: the four tests' assertion blocks stay byte-identical (SC-002), no `xfail`/`skip` is introduced (SC-003), and `src/specify_cli/consolidation/wp_evidence.py` is untouched (NFR-001, C-002).

## Context & Constraints

- Issue spec-kitty/spec-kitty#6801; the defect, root cause and the fixture-vs-gate decision are recorded in `kitty-specs/birth-cutover-fixture-planning-commit-01M66MFQ/research.md` — read it before editing.
- The evidence gate (`wp_evidence.py`, #6715) refuses an approved WP whose lane records no planning commit (`EVIDENCE_WINDOW_UNCOMPUTABLE`), and its recovery text names `spec-kitty agent mission finalize-tasks`. Production records the sha by capturing the current `target_branch` tip (`specify_cli.core.vcs.git.capture_branch_tip`) — see `tasks_finalize._finalize_lanes` and `mission_state._write_rebuilt_lanes`.
- The fixture writes `lanes.json` by hand through `_write_single_lane` (deliberate: it controls the single `lane-a` shape and `write_scope=("src/a/**",)`); this WP adds ONLY the planning-commit recording to that hand-written manifest. Do not replace the hand-written manifest with `compute_and_write_lanes`, and do not change `computed_from="test-fixture"`.
- The mission's own lanes.json is computed by `finalize-tasks`; this WP does not touch it.

## Branch Strategy

- **Strategy**: single lane, worktree allocated from the computed lane
- **Planning base branch**: `issue-6801-birth-cutover-fixture-planning-commit`
- **Merge target branch**: `issue-6801-birth-cutover-fixture-planning-commit`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Record the captured planning commit in `_write_single_lane`

- **Purpose**: Give the fixture's manifest the `planning_commit_sha` every production mission carries, so the #6715 evidence window `planning_commit_sha..<lane tip>` is computable.
- **Steps**:
  1. Change `_write_single_lane`'s signature to receive the repo root (e.g. `repo: Path` as the first parameter, mirroring the other fixture helpers); update its single caller in `_bootstrap_born_mission`.
  2. Inside, capture the target tip with the production helper: `from specify_cli.core.vcs.git import capture_branch_tip` (function-local import, matching the module's existing import style) and `planning_commit_sha = capture_branch_tip(repo, "main")`.
  3. Assert the capture succeeded, with a message that names the rule and the recovery path, e.g. `assert planning_commit_sha is not None, "fixture must record a planning commit (#6715 EVIDENCE_WINDOW_UNCOMPUTABLE): capture_branch_tip failed"`.
  4. Pass `planning_commit_sha=planning_commit_sha` to the `LanesManifest(...)` constructor.
  5. Extend the helper's docstring (or add a short comment) stating the parity contract: the sha is captured at lanes-write time exactly as `tasks_finalize._finalize_lanes` does, and the #6715 evidence gate reads it.
- **Files**: `tests/migration/test_birth_cutover.py` (only).
- **Parallel?**: No.
- **Notes**: The capture must happen BEFORE the fixture's `chore(<slug>): finalize WP01` planning-content commit — `_write_single_lane` already runs before it, so capturing inside the helper is the right moment (mirrors production, keeps `src/a/foo.py` inside the window for both topologies).

### Subtask T002 – Run the migration test file and verify strictness is preserved

- **Purpose**: Prove the red is gone without weakening anything.
- **Steps**:
  1. `uv run --frozen python -m pytest tests/migration/test_birth_cutover.py -q` → expect `24 passed`.
  2. Confirm the diff touches no assertion line of the four anchor tests (`git diff` review: only the fixture helper, its caller and the docstring may change).
  3. `git grep -n "xfail\|pytest.mark.skip" -- tests/migration/test_birth_cutover.py` → no new markers.
- **Files**: none (verification).
- **Parallel?**: After T001.
- **Notes**: If the refusal moves past `EVIDENCE_WINDOW_UNCOMPUTABLE` to a different #6715 code (e.g. `IMPLEMENTATION_MISSING`), STOP and report — do not paper over it; that would mean the window shape assumption in research.md is wrong.

### Subtask T003 – Lint, format and type-check the touched file

- **Purpose**: Keep the repo's gates green for the touched surface.
- **Steps**: `uv run ruff check tests/migration/test_birth_cutover.py`, `uv run ruff format --check tests/migration/test_birth_cutover.py`, `uv run mypy tests/migration/test_birth_cutover.py` (if the project type-checks tests — check the CI config; if mypy is not configured for tests, record that in the WP history note and skip).
- **Files**: none (verification).
- **Parallel?**: After T001.

## Test Strategy

- The mandatory test run is T002's file-level run. No new test files: the anchor tests are the pre-existing red, and the capture assertion is the fixture's own guard (DIRECTIVE_041).
- Do NOT run full heavy suites locally (NO_FULL_HEAVY_SUITES_IN_MISSION); CI owns those.

## Risks & Mitigations

- Silent `None` capture recreating the red — the T001 assertion fails loudly instead.
- Wrong capture timing producing an empty window — mitigated by capturing inside `_write_single_lane` (pre-planning-commit, production parity) and verified by T002.
- Temptation to "just run finalize-tasks in the fixture" — rejected in research.md: the fixture's hand-seeded event stream and single-lane shape are deliberate; the parity fix is the planning-commit field only.

## Review Guidance

- Check the diff is setup-only for the four anchor tests: no assertion, marker or gate change (SC-002, SC-003).
- Check the capture uses `capture_branch_tip` (not a hand-rolled rev-parse) and is asserted non-None (FR-002).
- Check the four tests pass and the rest of the file stays at 20 passed (SC-001).

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
