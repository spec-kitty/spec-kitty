---
work_package_id: WP01
title: Route the changelog WP-acceptance read through the canonical lane authority
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
planning_base_branch: issue-6612-changelog-wp-lane-reducer
merge_target_branch: issue-6612-changelog-wp-lane-reducer
branch_strategy: Planning artifacts for this mission were generated on issue-6612-changelog-wp-lane-reducer. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6612-changelog-wp-lane-reducer unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-10-30T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/release/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/release/changelog.py
- tests/release/test_release_prep.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Route the changelog WP-acceptance read through the canonical lane authority

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
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

`spec-kitty agent release prep`'s changelog block classifies a work package as accepted exactly when the **canonical reducer** puts it in `approved`/`done`, read from the **resolved status surface** (the coordination branch under coordination topology), and a corrupt `status.events.jsonl` fails the build loudly.

Success criteria (from spec.md):

- SC-001: a mission whose log file order disagrees with reducer order is classified by the reducer's lane.
- SC-002: a coordination-topology mission is classified from its coordination-branch log, not the stale primary copy.
- SC-003: a corrupt log line makes `build_changelog_block` raise the canonical store error (`StoreError`).
- SC-004: every pre-existing `tests/release/` test passes unchanged (legacy frontmatter fallback intact).

## Context & Constraints

- Spec: `kitty-specs/changelog-wp-lane-reducer-01M66FMR/spec.md` (issue spec-kitty/spec-kitty#6612, gap G-13).
- Plan: `kitty-specs/changelog-wp-lane-reducer-01M66FMR/plan.md` — the fix shape (D-1) and failure policy (D-2) are decided there; do not re-derive them.
- Research (reproductions, precedents): `kitty-specs/changelog-wp-lane-reducer-01M66FMR/research.md`.
- Read the charter's ATDD-first discipline: the three red tests (T001–T003) are written and demonstrated failing BEFORE the fix (T004).
- **Constraints**: smallest viable diff — touch only `src/specify_cli/release/changelog.py` and `tests/release/test_release_prep.py`. Never modify the reducer, the placement seam, the status store, or their tests. No new dependencies. Late imports for `mission_runtime` and `specify_cli.status` (repo convention: keeps cold-start cost low and avoids import cycles).
- **Seams to use** (never hand-compose a status path — the read-side bypass gate `tests/architectural/test_no_read_side_bypass.py` polices this):
  - `mission_runtime.placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)` — the resolved status-surface directory.
  - `specify_cli.status.get_wp_lane(read_dir, wp_id)` — the canonical lane reader (reducer-backed; raises `CanonicalStatusNotFoundError` when the log is absent; returns `Lane.UNINITIALIZED` when the WP is absent from the snapshot).
- **Failure policy** (plan.md D-2):
  1. Placement unresolvable (legacy mission: missing/malformed `meta.json`) → fall back to the mission dir (today's surface).
  2. `CoordinationWorktreeUnmaterialized` (fresh-clone window; from `specify_cli.coordination.surface_resolver`) → treat as "no readable authoritative surface": return no lane so the frontmatter fallback applies. NEVER fall back to the stale primary copy (the #1735 split-brain class).
  3. No event log on the resolved surface (`CanonicalStatusNotFoundError`) or WP absent (`Lane.UNINITIALIZED`) → no lane; the existing frontmatter fallback in `_is_accepted_wp` applies.
  4. `StoreError` (corrupt log) and `CoordinationBranchDeleted` → propagate unchanged.
- The two private helpers change signature (`repo_root` threaded from `build_changelog_block`); research.md verifies no other importers.

## Branch Strategy

- **Strategy**: stay on the planning branch; this WP's changes land on the mission branch.
- **Planning base branch**: `issue-6612-changelog-wp-lane-reducer`
- **Merge target branch**: `issue-6612-changelog-wp-lane-reducer`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red test: reducer order beats file order

- **Purpose**: Pin the core defect — last-`to_lane`-in-file-order misclassification.
- **Steps**: In `tests/release/test_release_prep.py`, add a test that creates a mission (reuse the `_write_mission` helper pattern) whose `status.events.jsonl` holds a continuous event chain in reducer order (`planned → in_review` at `2026-05-01`, `in_review → approved` at `2026-05-02`) written to disk REVERSED (approval line first). Assert `build_changelog_block` includes the mission/WP.
- **Files**: `tests/release/test_release_prep.py`.
- **Parallel?**: Yes (with T003).
- **Notes**: Use valid `StatusEvent` rows (see `_status_event` in `tests/status/test_agent_status_emit_aggregate_wiring.py` for the required fields: `event_id`, `mission_slug`, `wp_id`, `from_lane`, `to_lane`, `at`, `actor`, `force`, `execution_mode`, `evidence`, `reason`, `review_ref`). `WP frontmatter status` must NOT be accepted (e.g. `in_progress`) so only the event log can make it accepted. Demonstrate the test fails on the pre-fix tree before implementing T004.

### Subtask T002 – Red test: coordination surface beats the stale primary copy

- **Purpose**: Pin the split-brain fix — the changelog must read the coordination branch's log.
- **Steps**: Build a real git fixture (pattern: `tests/status/test_agent_status_emit_aggregate_wiring.py` — `git init -b main`, config user, initial commit): a mission whose `meta.json` declares `mission_id` + `coordination_branch`; a stale primary `status.events.jsonl` with `WP01 → in_review`; the coordination branch checked out in a worktree at `.worktrees/<slug>-<mid8>-coord` carrying the same event plus `in_review → approved`. Assert `build_changelog_block(repo)` includes WP01.
- **Files**: `tests/release/test_release_prep.py`.
- **Parallel?**: No (needs its own git fixture).
- **Notes**: The worktree must be at the registered location `repo/.worktrees/<slug>-<mid8>-coord` (that is where the placement seam probes). Mark with the repo's subprocess-git helper conventions; keep the fixture minimal. Demonstrate failure on the pre-fix tree.

### Subtask T003 – Red test: corrupt log fails loudly

- **Purpose**: Pin FR-003 — a corrupt line is not silently skipped.
- **Steps**: A mission whose `status.events.jsonl` contains one valid event line plus one line of non-JSON garbage. Assert `build_changelog_block` raises `specify_cli.status.store.StoreError` (import from the canonical public surface).
- **Files**: `tests/release/test_release_prep.py`.
- **Parallel?**: Yes (with T001).
- **Notes**: Demonstrate failure on the pre-fix tree (today the line is skipped and no error is raised).

### Subtask T004 – Implement the canonical lane read

- **Purpose**: Make the red tests green through the pre-existing entry point.
- **Steps**: Rewrite `_wp_lane_from_event_log` in `src/specify_cli/release/changelog.py` to (1) resolve the read dir via the placement seam with the failure policy above, (2) call `get_wp_lane`, (3) map `Lane.UNINITIALIZED` to no-lane, (4) return `str(lane)` otherwise. Thread `repo_root` through `_is_accepted_wp` from `build_changelog_block`. Keep the frontmatter fallback arm unchanged. Delete the raw `json.loads` loop (the `import json` may become unused — remove it if so).
- **Files**: `src/specify_cli/release/changelog.py`.
- **Parallel?**: No.
- **Notes**: Update the docstrings to name the authority (reducer + placement seam) and cite #6612/G-13. Do not broaden `_ACCEPTED_LANES`.

### Subtask T005 – Verify

- **Purpose**: Prove no regression inside and beside the change.
- **Steps**: Run `uv run pytest tests/release/ -q`; run the architectural read-side gate `uv run pytest tests/architectural/test_no_read_side_bypass.py -q`; run `uv run ruff check src/specify_cli/release/ tests/release/test_release_prep.py` and `uv run ruff format --check` on them; run mypy on the changed module per the repo's configured command. Never run a full heavy suite.
- **Files**: none (verification only).
- **Parallel?**: No.
- **Notes**: Record results in the WP history via `spec-kitty agent tasks add-history WP01 --note "..."`.

## Test Strategy (include only when tests are required)

- Tests live in `tests/release/test_release_prep.py` (the suite owning the `build_changelog_block` contract).
- Commands: `uv run pytest tests/release/test_release_prep.py -q`.
- Fixtures: `tmp_path` mission dirs (existing `_write_mission` helper); one subprocess-git coordination fixture for T002.
- Compiler check: `uv run mypy src/specify_cli/release/changelog.py` (matching CI's typed-source gate).

## Risks & Mitigations

- Legacy-mission regression → SC-004 keeps every pre-existing test unchanged; the fallback arms are pinned by existing tests.
- Coordination-fixture flakiness → follow the existing wiring-test pattern exactly; no network, no `gh`.
- Read-side bypass gate → only sanctioned seams; run the gate in T005.

## Review Guidance

- Check that no raw parse of `status.events.jsonl` remains in `release/changelog.py`.
- Check the failure policy matches plan.md D-2 arm-for-arm (especially: unmaterialized coord never reads the stale primary copy).
- Check the red tests genuinely failed pre-fix (ask for the red run output).
- Confirm compiler diagnostics passed (typed source changed).

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
