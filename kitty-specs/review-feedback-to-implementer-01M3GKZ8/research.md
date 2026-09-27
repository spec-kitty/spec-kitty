# Phase 0 Research — Rejection feedback reaches the implementer

All findings verified against `issue-4899-review-feedback-to-implementer` at the current tree (base `46ea5bd7fd`).
No dependency added/removed/upgraded → the supply-chain-install-safety checks are N/A for this mission
(recorded here per the plan's supply-chain section; silence is not compliance — the explicit finding is
"no dependency decision made").

## Decision 1 — Single predicate `is_review_rejection_edge` as the write-side SSOT

- **Decision**: Replace the four `target_lane == Lane.PLANNED` checks with one pure predicate
  `is_review_rejection_edge(old_lane, target_lane)` in `tasks_transition_core.py`, defined as
  `resolve_lane_alias(old) == IN_REVIEW and resolve_lane_alias(target) in (PLANNED, IN_PROGRESS)` unioned
  with `target == PLANNED`.
- **Rationale**: C-003 requires the write-side fix to be ONE coupled behavioral change. Four scattered
  boolean checks can drift; one predicate cannot be half-satisfied. The union preserves the existing
  any-source `→planned` rollback guard (`_planned_rollback_message` Arm A/Arm B) so no current behavior
  regresses while the re-implement edge is added.
- **Alternatives considered**:
  - *Add `== IN_PROGRESS` at each of the four sites independently* — rejected: reintroduces the exact
    four-way coupling-by-discipline C-003 forbids; a future edit can miss a site.
  - *New `Emit.is_review_rejection` flag only, gates unchanged* — rejected: gates 1 (content read, in
    `_mt_resolve_feedback`, before `Emit` is built) and 4 (`_guard_planned_rollback`, a pre-plan guard)
    run before/outside `Emit`, so a flag alone cannot cover all four; the predicate must be callable from
    both the pre-plan guards and the plan builder.
- **Reference oracle**: the `in_review → planned` edge is the parity oracle (Assumptions in spec.md);
  `persist_rejected_review_cycle_for_rollback` (`tasks_verdict_persistence.py:930`) is the shared writer the
  re-implement edge will now reach.

## Decision 2 — F4 / SC-004: coordination-topology render is INDEPENDENTLY red

- **Decision**: The coord render defect is independent of the write-side loss; SC-004's coord half stays a
  red-first defect and WP02 gains a render-path `STATUS_STATE` re-route.
- **Evidence** (traced, not assumed):
  - Render feedback resolution `implement_resolve_feedback_and_gate` (`workflow_executor.py:685`) resolves
    `feature_dir = read_dir(WORK_PACKAGE_TASK)`.
  - `WORK_PACKAGE_TASK ∈ _PRIMARY_ARTIFACT_KINDS` (`mission_runtime/artifacts.py:166`) → PRIMARY partition.
  - The event log is read from that `feature_dir`: `resolve_review_feedback_context` →
    `latest_review_feedback_reference` → `read_wp_events(feature_dir, wp_id)` → `read_events(feature_dir)`
    (`workflow_cores.py:305-337`). `has_prior_rejection` (`workflow_cores.py:421`) reads the same way.
  - But `status.events.jsonl` / `status.json` map to `STATUS_STATE` (`artifacts.py:250-251`), and
    `STATUS_STATE ∈ _PLACEMENT_ARTIFACT_KINDS` (`artifacts.py:198`) → COORD partition.
  - On a coord / lanes-with-coord topology PRIMARY ≠ COORD dir, so the render reads an empty event stream
    and finds no resolvable `review_ref` even with a durable record present. The write side already handles
    this exact hazard: `_resolve_verdict_read_feature_dir` (`tasks_verdict_persistence.py:694`) routes the
    verdict READ through `placement_seam(...).read_dir(STATUS_STATE)` "because under a coordination topology
    the event log lives on the coord worktree."
- **Rationale**: Because the defect reproduces GIVEN a record present, it satisfies the caveat's condition
  for a valid red-first coord defect; reclassifying to parity would under-test FR-007.
- **Alternatives considered**: *treat coord as downstream-only and reclassify to a parity assertion* —
  rejected on the partition-map evidence above.
- **Residual honesty**: the implementer must still demonstrate the red on a real coordination fixture with a
  record present. If it comes back green, reclassify then and note the divergence from this analysis.
- **Spec impact**: none — SC-004 delegated the resolution to plan and this takes the caveat's independently-broken branch.

## Decision 3 — Render fall-through must be operator-visible, not log-only

- **Decision**: `workflow_executor.py:1161-1163` changes from log-only (`logger.warning`) to a visible
  `console.print` red warning (the surface the implementer reads), still returning `None` (no silent
  feedback-less substitution beyond the honest full-prompt fallback, which is now announced).
- **Rationale**: FR-006's explicit bar is visibility on the surface the implementer reads; a log line the
  prompt-consuming surface never shows does not satisfy it. Keeping concrete recovery text in the handler
  also clears the Sonar "effect-free / log-only except" finding.
- **Alternatives considered**: *raise instead of returning None* — rejected: the full prompt is a legitimate
  fallback; the requirement is visibility, not abort. *Leave logger.warning* — rejected: fails FR-006.

## Decision 4 — Conditional #3451 review-cycle counter (FR-008)

- **Decision**: WP01 checks whether `cycle_number` double-increments on the re-implement edge once that edge
  starts persisting. If it reproduces, WP01 carries its OWN red-first count-correctness scenario proving the
  counter increments exactly once; if it does not reproduce, #3451 stays out of scope (C-001).
- **Rationale**: FR-008 is a `[folded]` conditional. The counter is `ReviewCycleArtifact.latest(...).cycle_number`
  consumed at the render site (`workflow_executor.py:1143`); double-increment would surface as a skipped cycle
  number. Determination is cheap and belongs in the write-side WP where the persist path is exercised.
- **Alternatives considered**: *always fold #3451* — rejected: violates C-001 scope unless it reproduces.

## Adversarial evidence

No security-impacting dependency decision is made in this plan, so the mandatory adversarial dependency
challenge is **not applicable**; recorded as `deferred_with_rationale` (no dependency surface to challenge).
The post-spec adversarial findings F1–F4/N1/N3 were already folded into the committed spec (commit
`3ef8043150`); F4 is resolved above.

## Grammar precondition (NFR-001)

The synthetic-marker / resolvable-pointer grammar in `review/cycle.py:63-117`
(`_REVIEW_PREFIX`/`is_synthetic_review_ref`/`is_non_resolvable_review_ref`/`synthetic_review_ref`) is present
and correct (shipped by #4801). This mission reuses it unchanged — zero edits to that grammar. Confirmed by
inspection.
