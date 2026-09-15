# Behavioral Contract: blocked-WP recovery (#3937)

Executable-contract intent for the ATDD tests. Each clause maps to an FR and pins observable STATE.

## C1 (FR-001, FR-002, FR-003) — allocation failure leaves WP recoverable
- **Given** a WP in `planned` and a `create_lane_workspace` that raises `DependencyLaneMergeConflictError` (and, separately, `PlanningCommitMergeConflictError`),
- **When** `implement` runs and catches the failure,
- **Then**:
  - the WP's lane after the call is `planned` (assert via the status reducer / event log);
  - NO event with `(from_lane="planned", to_lane="blocked")` is appended for this WP;
  - the printed output contains the exception's `next_step` text (actionable resolution), not merely a generic "re-run".
- **Non-fakeable**: assert the absence of the blocked event and the unchanged lane, not just message text.

## C2 (FR-002) — re-run after resolving the cause is clean
- **Given** the failure above has occurred and the WP is `planned`,
- **When** the underlying conflict is resolved and `implement` is re-run,
- **Then** the command proceeds with NO intermediate unblock step and the WP acquires no `review-cycle://` feedback pointer (Fix mode is not triggered).

## C3 (FR-004, FR-005, FR-006) — honest single-stage refusal out of `blocked`
- **Given** a WP in `blocked`,
- **When** `move-task --to planned` is requested with NO review feedback,
- **Then** the refusal identifies an **illegal transition** and enumerates the legal targets `{in_progress, canceled}`; it does NOT demand `--review-feedback-file`.
- **And When** the same request supplies a `--review-feedback-file`,
- **Then** the verdict is unchanged (still refused as illegal) — a review artifact cannot launder a structurally illegal transition.
- **Non-fakeable**: assert the refusal IDENTITY (illegal-transition) and that feedback presence does not change it — not a message substring.

## C4 (regression) — review-family rollback still requires feedback
- **Given** a WP in a review-family lane (e.g. `in_review`),
- **When** `move-task --to planned` is requested with NO review feedback,
- **Then** the review-feedback requirement still applies exactly as before.

## C5 (FR-007) — start-implementation reject names recovery
- **Given** a WP genuinely in `blocked`,
- **When** starting implementation is refused,
- **Then** the "cannot start implementation" message names the legal recovery command for the current state.

## C6 (NFR-002) — no FSM-core fixture churn
- The machine-readable illegal-transition string asserted by `tests/status/fsm_parity_baseline.jsonl` is unchanged (0 rows differ). Legal-target enumeration appears only on the CLI/emit refusal path.
