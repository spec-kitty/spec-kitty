---
work_package_id: WP01
title: Canceled dependency-lane content never counts as approved authorship (#5569)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
planning_base_branch: kitty/rc5-consolidate-regressions
merge_target_branch: kitty/rc5-consolidate-regressions
branch_strategy: Planning artifacts for this mission were generated on kitty/rc5-consolidate-regressions. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/rc5-consolidate-regressions unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rc5-consolidate-regressions-01M4189Z
base_commit: c2f3b261055b5d2165f29a5b66022e98fed49b31
created_at: '2026-10-03T16:27:21.236820+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_canceled_dependency_lane.py
- tests/terminus/test_repro_5569.py
execution_mode: code_change
model: claude-sonnet-5-5-high
owned_files:
- src/specify_cli/consolidation/reconciliation.py
- src/specify_cli/consolidation/wp_attribution.py
- tests/consolidation/test_canceled_content_residuals.py
- tests/consolidation/test_canceled_dependency_lane.py
- tests/terminus/test_repro_5569.py
- tests/terminus/conftest.py
- tests/terminus/lanes_fixture.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – Canceled dependency-lane content never counts as approved authorship (#5569)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP01 --agent claude`

## Objective

`spec-kitty consolidate` must never land a fully-canceled lane's content through a dependent
approved lane that fast-forwarded onto it, under the default squash strategy and under
`--strategy merge`. The command must exit non-zero naming the canceled WP. Closing this also
closes residual 7 in `tests/consolidation/test_canceled_content_residuals.py`.

## Context

Read `research.md` (#5569 section) and `plan.md` (IC-01, including the brownfield fold).

- `lanes/worktree_allocator.py:1613-1625` merges dependency lanes without `--no-ff`, so a fresh
  dependent lane fast-forwards and the canceled WP's commit sits on its first-parent spine.
  **Do not change the allocator** (rejected design: prevents new cases only).
- `consolidation/reconciliation.py`: `_collect_authored` (~1732, spine walk ~1782-1789) claims
  that commit as approved authorship; `_collect_excluded` (~1531, subtraction ~1592) then drops
  it from the excluded set; `_mixed_lanes` (~1224) never selects a lane holding only canceled
  WPs; `_closed_world_anchors` (~1372-1379) exempts dependency-lane tips.
- The lane base for the closed world comes from the first-claim stamp built in
  `consolidation/wp_attribution.py:542-657`.
- The existing fixture `plant_canceled_commit` (`tests/terminus/conftest.py:1170-1225`) always
  builds a true merge — that is why the #4977 repro went green. Do not reuse it for the red test.

Constraints: C-001 (no weakening of CAS or the closed world — this fix only *tightens* the
anchor set and the authored claim), C-002 (other residuals stay strict xfail), C-003 (no
`--attest-canceled-superseded` as the fix), C-004 (single authority: one shared lane-base helper).

### Subtask T001: Red-first entry-point test (separate commit)

> Post-tasks squad: `build_lanes_mission` (`tests/terminus/lanes_fixture.py:118`) wires `depends_on_lanes` only for the planning lane (:74; code lanes get `()` at :61). Extend the fixture (owned) so lane-b depends on lane-a, and drive the real allocator merge (`worktree_allocator.py:1613`) — never hand-merge.

- **Purpose**: reproduce #5569 through the real CLI.
- **Steps**:
  1. Create `tests/terminus/test_repro_5569.py`. Build a `lanes` (or `lanes_with_coord`) mission
     with WP01 owning `src/alpha/**` and WP02 owning `src/beta/**` with `dependencies: [WP01]`,
     using the existing terminus fixtures (look at `tests/terminus/conftest.py` and
     `tests/terminus/lanes_fixture.py` for mission builders that run real `finalize-tasks`).
  2. Implement WP01 via the real implement path, commit `src/alpha/mod.py`, approve.
  3. Implement WP02 via the real implement path **so the allocator itself fast-forwards
     lane-b**; commit `src/beta/mod.py`.
  4. Reopen WP01 (`planned` with review feedback), then cancel it with operator provenance;
     approve WP02.
  5. Run `consolidate` (default) and, parametrised, `consolidate --strategy merge`.
  6. Assert: non-zero exit; output names WP01; `src/alpha/mod.py` absent from the target.
  7. Positive control (same fixture builder): WP01 approved, not canceled → both files land, exit 0.
  8. Mark the reproduction `@pytest.mark.regression`-style only if the repo convention requires
     it for red-first tests outside `tests/regression/`; otherwise a plain test is fine.
- **Validation**: test is RED on the mission base; commit it alone (`test(WP01): red-first #5569`).

### Subtask T002: Shared lane-base helper

- **Purpose**: one authority for "commits a lane authored since its base".
- **Steps**: extract a pure helper (e.g. `lane_base_anchor()` / `lane_own_commits()`) from the
  existing first-claim-stamp logic in `wp_attribution.py` and use it from reconciliation.
  Behaviour-preserving for existing callers; focused unit tests in
  `tests/consolidation/test_canceled_dependency_lane.py`.
- **Validation**: existing `tests/consolidation/` and `tests/terminus/test_repro_5046*.py` stay green.

### Subtask T003: Subtract fully-canceled lane content from the authored claim

- **Purpose**: commits reachable from a fully-canceled lane's tip (after its base) are excluded
  content, never approved authorship.
- **Steps**:
  1. Identify fully-canceled lanes (every WP in `excluded_canceled_wp_ids` / canceled).
  2. Compute their own commits via the T002 helper.
  3. Remove those SHAs / patch-ids / authored blobs from `_collect_authored`'s result before
     `_collect_excluded`'s subtraction, so they stay in the excluded set.
  4. Do not exclude commits that precede the canceled lane's base (shared ancestry).
- **Validation**: unit tests for the helper branches; complexity ≤ 15.

### Subtask T004: Drop fully-canceled dependency tips from closed-world anchors

- **Purpose**: such commits must not be exempt via the dependency-tip anchor.
- **Steps**: in `_closed_world_anchors`, skip a dependency lane whose every WP is canceled (use
  that lane's base instead). Verify the verdict is REFUSE/FAIL, never PASS.
- **Validation**: focused unit test; mixed-lane tests unchanged.

### Subtask T005: Promote residual 7; guard the other residuals

- **Steps**: remove the strict xfail from
  `test_fully_canceled_dependency_lane_content_ideally_does_not_ship`, rename/re-docstring it as a
  regular test of the fixed behaviour, and update the module docstring's residual list. Run the
  whole module: **any XPASS other than residual 7 is a stop signal** — report to the
  orchestrator instead of promoting it.
- **Validation**: `uv run pytest tests/consolidation/test_canceled_content_residuals.py -q`
  shows residual 7 passing and the other strict xfails still xfail.

## Definition of Done

- T001 red on base, green on the WP tip, for both strategies; positive control green.
- Residual 7 promoted; remaining residual xfails unchanged.
- `uv run pytest tests/consolidation tests/terminus -q -m "not slow"` (or the modules touched)
  shows no new failures vs base; `ruff check`, `ruff format --check --force-exclude <files>`,
  `mypy` clean on touched files.
- Subtasks recorded via `spec-kitty agent tasks mark-status <Txxx> --status done`.
- Append a line to the mission tracer files (coord partition) for any friction/decision.

## Risks

- Over-exclusion: an approved WP that legitimately reverted/re-authored the same path. Keep the
  rule SHA/blob-scoped to the canceled lane's own commits.
- XPASS of residuals 5/6 would signal a widened exclusion — stop and report.

## Reviewer Guidance

- Confirm the red test drives the real allocator fast-forward (not a hand-built merge).
- Confirm no CAS/closed-world relaxation; anchors only shrink.
- Confirm a single lane-base authority (no duplicated stamp logic).
