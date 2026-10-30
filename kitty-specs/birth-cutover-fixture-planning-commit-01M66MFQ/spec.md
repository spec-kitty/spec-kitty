# Mission Specification: Record the planning commit in the birth-cutover fixture lanes.json

**Mission Branch**: `issue-6801-birth-cutover-fixture-planning-commit`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6801 — `tests/migration/test_birth_cutover.py`: 4 deterministic failures on main — `EVIDENCE_WINDOW_UNCOMPUTABLE` from #6715's attestation gate. Operator guidance: keep the four tests' assertions exactly as strict as they are; do not skip, xfail or relax any gate; decide between the mechanical fixture fix and a gate change, and if it turns out the gate itself must be weakened, STOP and report instead.

## Grounding (what was verified on main `512567eee7`)

- `uv run --frozen python -m pytest tests/migration/test_birth_cutover.py -q` on a clean checkout of `main@512567eee7` gives exactly the issue's result: **4 failed, 20 passed**, with the four failures being `test_birth_cutover_reconciles_at_merge_no_manual_backfill[coord|lanes]` and `test_birth_cutover_status_phase_is_primary_only[coord|lanes]`, all refusing at claim time with `EVIDENCE_WINDOW_UNCOMPUTABLE` (lane-a: lanes.json records no planning commit).
- The first bad commit is `8c5703e48f` (#6715, "refuse hollow or self-approved work packages on every topology"), which added `src/specify_cli/consolidation/wp_evidence.py`. Its rule 1 refuses every approved work package of a lane whose `lanes.json` records no `planning_commit_sha`.
- `_bootstrap_born_mission` in `tests/migration/test_birth_cutover.py` hand-writes its mission: `_write_single_lane` writes a `LanesManifest` with `computed_from="test-fixture"` and no `planning_commit_sha`, and the fixture never runs `spec-kitty agent mission finalize-tasks`, so no production path ever records a planning commit for it.
- No fix has landed on `main` for this file since the regression (`git log -- tests/migration/test_birth_cutover.py` shows nothing after `7559e4336b`, which predates `8c5703e48f`); no open PR addresses #6801. The red is latent on main because the `tests (events consumers)` job is diff-selected; it currently blocks open PRs #6795 and #6804.
- Same defect class as #6798 (a fixture that bypassed the production path and went stale against a later ruling); #6802 is the parallel fix for that one and fixes the fixture, not the product.

## Decision recorded (the reading this mission takes)

The fixture is wrong, not the product. Reasoning:

1. `EVIDENCE_WINDOW_UNCOMPUTABLE` is a deliberate fail-closed rule of #6715: without a recorded planning commit, the implementation-evidence window `planning_commit_sha..<lane tip>` cannot be computed, so "landed as reviewed" cannot be verified. The gate's own refusal text names the recovery: `run 'spec-kitty agent mission finalize-tasks' to record the planning commit, then re-run`.
2. Every real mission gets its `planning_commit_sha` from the production finalize path (`tasks_finalize._finalize_lanes` and `mission_state._write_rebuilt_lanes` both capture the current target-branch tip via `capture_branch_tip`, the canonical tip-capture authority of #4857). The birth-cutover fixture is the only author of a `LanesManifest` that skips this; it was written before #6715 made the planning commit load-bearing.
3. Weakening the gate for this shape (tolerating a manifest with no planning commit) would re-open exactly the hollow-WP hole #6715 closed, and would be an operator ruling, not a mechanical fix. The mission does not do it.

So the fix is mechanical: the fixture records a planning commit the way `finalize-tasks` does — capturing the current `target_branch` tip with the same production helper, `specify_cli.core.vcs.git.capture_branch_tip`, at the moment `lanes.json` is written — and asserts the capture succeeded, so a fixture that silently loses the planning commit fails loudly instead of regressing. The hand-written lane shape (one `lane-a`, `write_scope=("src/a/**",)`) is deliberate test control and stays.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The birth-cutover file is green on main again (Priority: P1)

A maintainer with a PR whose diff selects the `tests (events consumers)` job (e.g. #6795, #6804) needs that job to reflect their diff, not a latent red on main. The four anchor tests of `tests/migration/test_birth_cutover.py` must pass on a clean checkout of main plus this fix.

**Why this priority**: The red blocks unrelated PRs from ever going green; nothing else in this mission matters if the file is still red.

**Independent Test**: `uv run --frozen python -m pytest tests/migration/test_birth_cutover.py -q` passes 24/24 on the fix branch (was 4 failed, 20 passed on main `512567eee7`).

**Acceptance Scenarios**:

1. **Given** a clean checkout of main plus this change, **When** the four anchor tests run (`test_birth_cutover_reconciles_at_merge_no_manual_backfill[coord|lanes]`, `test_birth_cutover_status_phase_is_primary_only[coord|lanes]`), **Then** all four pass with their existing assertions unchanged.
2. **Given** the fixture mission reaches consolidation, **When** the #6715 evidence axis evaluates approved WP01 of lane-a, **Then** it finds a computable window `planning_commit_sha..<lane tip>` with the `src/a/**` owned change in it, and does not refuse.

### User Story 2 - The fixture cannot silently lose the planning commit again (Priority: P2)

A future contributor changing `_write_single_lane` must not be able to reintroduce this red as a silent `planning_commit_sha=None` — the fixture should fail at setup time with a clear message instead of a confusing claim-time refusal three stages later.

**Why this priority**: This is the #6798 lesson — a fixture that bypasses the production path goes stale silently. An explicit guard makes the dependency on the planning commit visible at the point where it is created.

**Independent Test**: Reading `_write_single_lane`: the captured tip is asserted non-None with a message naming the #6715 evidence-window rule.

**Acceptance Scenarios**:

1. **Given** `_write_single_lane` runs where the target branch tip cannot be captured, **When** the fixture executes, **Then** it fails immediately with an assertion naming the planning-commit requirement, rather than producing a manifest that the consolidation refuses later.

### Edge Cases

- What if the captured tip is `None` (git failure)? The fixture asserts it is not; a git failure in setup is a fixture failure, not a product behavior question.
- Does the recorded window still find the owned change for both topologies (coord: lane branch forks from the re-forked coordination branch; lanes: from `kitty/mission-<slug>`)? Yes — verified by the four tests themselves passing; the window is a tree diff from the captured pre-planning-content target tip to the lane tip, which contains the `feat: WP01 adds src/a/foo.py` change either way.
- Must `computed_from="test-fixture"` change? No — it is an input description, not load-bearing for the evidence axis; the mission changes only what the gate reads.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Record the planning commit in the fixture lanes.json | As a maintainer, I want the birth-cutover fixture's `LanesManifest` to carry the `planning_commit_sha` the production finalize path would have recorded, so the #6715 evidence gate can compute WP01's evidence window. | High | Open | [build] | no |
| FR-002 | Fail loudly when the tip cannot be captured | As a maintainer, I want the fixture to assert the captured planning commit is not None, so a stale fixture fails at setup with a named cause instead of a claim-time refusal. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No gate, assertion or product behavior weakened | The diff touches no `src/` behavior and no test assertion; the four tests' assertions remain byte-identical; `wp_evidence.py` is untouched. | Integrity | High | Open |
| NFR-002 | Production-path fidelity | The planning commit is captured with the same production helper the finalize path uses (`specify_cli.core.vcs.git.capture_branch_tip`), not a hand-rolled `git rev-parse`. | Consistency | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Test-only diff | No `src/` changes except (at most) docstring clarity; no changelog entry unless something user-facing emerges (test-only, mirroring #6802's precedent). | Scope | High | Open |
| C-002 | No xfail, skip or gate relaxation | The fix may not use `pytest.mark.xfail`/`skip`, may not edit `wp_evidence.py` or its refusal rules, and may not loosen any assertion in the four tests. | Governance | High | Open |

### Key Entities

- **`LanesManifest.planning_commit_sha`**: the commit a mission's lanes were planned against (FR-009 / ADR `2026-07-29-1`); the base of every lane's implementation-evidence window.
- **`capture_branch_tip(repo, branch)`**: the canonical target-branch tip-capture authority (#4857); resolves `refs/heads/<branch>` so a tag/branch name collision cannot mislead it.
- **Evidence window**: `planning_commit_sha..<lane branch tip>` tree diff, minus bookkeeping paths; #6715's axis for "approved with owned, reviewed content behind it".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run --frozen python -m pytest tests/migration/test_birth_cutover.py -q` on the fix branch reports 24 passed, 0 failed — [build] · no-op passable: no
- **SC-002**: The four anchor tests' assertion blocks are byte-identical to main (setup-only diff) — [ratchet] · no-op passable: no
- **SC-003**: `git grep -n "xfail\|pytest.mark.skip" -- tests/migration/test_birth_cutover.py` shows no new markers on the four tests — [ratchet] · no-op passable: no
