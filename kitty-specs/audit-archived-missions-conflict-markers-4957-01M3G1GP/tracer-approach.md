# Tracer: Approach

Mission: `audit-archived-missions-conflict-markers-4957-01M3G1GP` (#4957)

## Overall approach

**repair → carve-out registration → guard tests → red-first verification → single PR**

1. **Repair** (FR-001 / User Story 1, P1): resolve the botched-merge block at
   `kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md:758–773`
   to the `HEAD` (`df2dac046`) side — the lineage confirmed an ancestor of `main` — deleting the
   marker lines and the losing (`5eda48f7`, not an ancestor of `main`) side entirely.

2. **Carve-out registration** (FR-002 / User Story 3, P2): in the same commit as the repair (see
   plan.md Section D's landing-order justification), add the corrected path as the fourth,
   explicitly-commented entry in `_OPERATOR_SANCTIONED_CORRECTIONS`
   (`tests/architectural/test_archive_root_byte_identical.py`), following the exact comment
   pattern the three existing entries use, so the always-on `archive-freeze` job passes on this
   mission's own PR.

3. **Guard tests** (FR-003–008 / User Story 2, P1): add five new, separately-failing test
   functions to the same file — the real-tree scan with a ground-truth-tied floor, its
   self-mutation positive control, the shrink-only exemption ratchet, that ratchet's own
   positive control, and the fail-closed-on-enumeration-failure test — closing the defect class
   by construction per Charter Standing Order #5. See plan.md Section B for the full mapping to
   FR-003 through FR-008.

4. **Red-first verification** (Standing Order #4): each of the five test functions is confirmed
   red before the corresponding piece of guard logic exists, then green after — per-function,
   not as one blanket "tests pass" claim. FR-001's own red-first proof is the FR-003 guard test
   run against the *unrepaired* tree (it fails today, live-verified this phase), distinct from
   FR-006's synthetic self-mutation fixture. See plan.md Section D for the full sequencing.

5. **Single PR** (User Story 3 / Section G): one PR targeting `main` from
   `issue-4957-archived-conflict-markers`, carrying both files' changes together, plus the
   FR-009 informational comment posted to issue #4956 as a PR-closing-step tracker action (not
   a file change).

## FR groupings referenced

- **User Story 1 (P1) → FR-001**: the repair itself.
- **User Story 2 (P1) → FR-003, FR-004, FR-005, FR-006, FR-007, FR-008**: the guard and its
  three-legged non-vacuity proof (concrete floor, self-mutation, shrink-only ratchet +
  ratchet's own positive control) plus fail-closed behavior.
- **User Story 3 (P2) → FR-002**: the carve-out registration that lets this mission's own PR
  land at all.
- **Cross-cutting → FR-009 / C-003**: the #4956 informational comment, sequenced after the
  repair lands (its content depends on the final four-entry membership and line reference).

## What this mission does NOT do (explicitly out of scope, per C-002/C-003)

- Does not remove any of the three pre-existing `_OPERATOR_SANCTIONED_CORRECTIONS` entries or
  the carve-out mechanism itself — that is issue #4956's job, once every correction is baseline
  on `main`.
- Does not add a commit-time (pre-commit hook) prevention — the guard is CI-time only, per
  spec.md Clarification (e)'s deliberate-deferral reasoning.
- Does not migrate `_APPEND_ONLY_SPINE_EXCEPTIONS` or the new exemption allowlist into
  `tests/architectural/_baselines.yaml`'s centralized ratchet mechanism — per spec.md
  Clarification (k), this is a reasoned exception (would require editing a third file,
  conflicting with C-002), not a silent bypass.
