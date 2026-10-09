# Mission Specification: Green the reds — coord review honest-receipt re-pin

**Mission Branch**: `kitty/mission-green-reds-coord-review-repin-01M4H53K`
**Created**: 2026-10-09
**Status**: Draft
**Input**: Milestone 11, Slice 1 — "Green the reds". Fix the release-gating red test(s) so `main` and the nightly go green: #5928 (`TestAgentActionReviewTextEnvelope::test_coord_mission_prompt_skeleton` red on `main`) and its nightly `integration-slice` P0 escalation #5948 (auto-dedup of #5928; one root cause).

## Triage verdict (DIRECTIVE_003 — decision record)

**Verdict: stale/incorrect test expectation — fix test-only, no product change.** Operator-confirmed 2026-10-09.

The `agent action review` text envelope on a coordination Mission whose `for_review` WP has no prior lane commits:
1. records the "Start WP01 review" commit on the coordination branch;
2. fails the subsequent lane auto-rebase/sync (no lane commits to sync) → exits 1 and discloses the failure in prose (`"WP01 claim was committed; the lane sync after the for_review -> in_review commit failed: …"`);
3. the revert of that commit is **refused** because the status rows are already committed at HEAD (`STATUS_ROLLBACK_REFUSED` / `RollbackRefusal.TAIL_ALREADY_COMMITTED`, `mission_write.py:411`), so `_sync_lane_or_revert` (`workflow_executor.py:248-249`) deliberately does **not** mark the receipt refused;
4. the commit summary therefore honestly renders `[ok]` — the commit genuinely is present on the coordination branch.

Reporting a present commit as `[refused]` was precisely the misleading-receipt defect closed by **#5440** (and #5819 / #5804). The current `[ok]` is the honest marker; the command still fails (exit 1) and still names the lane-sync failure in prose, so no operator is misled. The test's `assert "[refused]" in text` encodes pre-#5440 behavior and is stale. This mission re-pins the characterization test to the honest behavior; it introduces **no** `src/` change. Consistent with parent EPIC #5106 ("Test suite friction — red-on-main & stale tests") and the issue's own note that "it could also be that the test's expectation is stale."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Nightly and `main` go green with an honest pin (Priority: P1)

As a Spec Kitty maintainer relying on `red main == no release`, I want the `test_coord_mission_prompt_skeleton` coord case to pin the *honest* current behavior of `agent action review` (committed receipt rendered `[ok]`, lane-sync failure disclosed in prose, exit 1) so that the release gate reflects real defects, not a stale characterization snapshot.

**Why this priority**: It is the sole scope of the mission; #5948 is a P0 nightly escalation of the same root cause, and a red release gate blocks the 4.0.0 line.

**Independent Test**: Run the single characterization case; it is RED on the current (pre-edit) pin and GREEN after the re-pin, with the product unchanged.

**Acceptance Scenarios**:

1. **Given** a coordination Mission with a materialized coord worktree and a `for_review` WP01 with no prior lane commits, **When** `agent action review WP01 --mission <slug> --agent reviewer-renata` runs, **Then** the command exits 1, prints no raw `Error: [Errno 2]`, prints `[review] Commits recorded:`, discloses `claim was committed; the lane sync after …` in prose, and renders the recorded coordination commit with the honest `[ok]` marker (never `[refused]`, because the commit is present).
2. **Given** the re-pinned test, **When** it runs on the mission's final commit, **Then** it passes; **and** when run against the pre-edit expectation it is red — proving the assertion change is non-vacuous.

### Edge Cases

- The Implement variant (`TestAgentActionImplementTextEnvelope::test_coord_mission_prompt_skeleton`) already passes and is untouched — the asymmetry (implement happy-path exit 0 vs review exit 1) is expected and remains pinned.
- No change to `src/`: if a future change makes the revert succeed, the receipt would legitimately flip to `[refused]`; that is a separate behavior change out of this mission's scope.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Re-pin coord review receipt to honest `[ok]` | As a maintainer, I want the coord `test_coord_mission_prompt_skeleton` to assert the honest-receipt behavior (`[ok]` + lane-sync-failure prose + exit 1) so that the release gate stops flagging correct behavior as red. | High | Open | [ratchet] | no — the pre-edit pin (`[refused]`) is red on current `main`, so an empty diff leaves the case failing; the re-pin is red before and green after on the same fixture. |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No production behavior change | The diff touches only `tests/characterization/test_trio_json_envelope.py`; zero lines under `src/` change. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Red-first, no green-washing | The re-pin must be demonstrably red under the old expectation and green under the new one; never skip/disable/xfail/quarantine the test (charter Standing Orders #4, #9). | Technical | High | Open |
| C-002 | Smallest viable diff + locality | Edit only the coord `test_coord_mission_prompt_skeleton` body and its stale docstring; do not touch the Implement variant, other surfaces, or `src/` (DIRECTIVE_024). | Technical | High | Open |

### Key Entities

- **Commit receipt**: the `_WORKFLOW_COMMIT_RECEIPTS` record rendered by `_print_commit_summary`; `outcome == "committed"` → `[ok]`, else `[refused]`.
- **Rollback refusal `TAIL_ALREADY_COMMITTED`**: the fail-closed state where status rows are already committed at HEAD and the revert leaves the commit in place, keeping the receipt `committed`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `test_coord_mission_prompt_skeleton` (review variant) passes locally and in CI; the containing file `tests/characterization/test_trio_json_envelope.py` is fully green. — [ratchet] · no-op passable: no
- **SC-002**: Zero lines under `src/` change in the mission diff (NFR-001 held). — [ratchet] · no-op passable: no
