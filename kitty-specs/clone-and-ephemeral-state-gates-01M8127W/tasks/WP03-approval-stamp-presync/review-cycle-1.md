---
affected_files: []
cycle_number: 1
mission_slug: clone-and-ephemeral-state-gates-01M8127W
reproduction_command:
reviewed_at: '2026-11-22T09:09:31Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP03
---

# WP03 review feedback (cycle 1), reviewer claude::reviewer-renata

Review range: 7fbbee86234e..c319e5990b6f (recorded). Red-first verified: b7af01da gives 3 failed
(the failures are the missing behaviour, not import errors). c319e599 gives 19 passed
(test_approval_stamp_presync_7802.py and test_lane_head_presync_7802.py).

The bound is not weakened. Every path I tried either measures from a tip that only merges
separate from `lane_head`, or fails closed. Two issues block approval.

**Issue 1 (blocking, correctness): a second merge-creating sync replaces the pre-sync tip with an unpushed merge.**
`_record_review_presync` writes `HEAD^1` of the newest sync merge every time a sync creates a merge.
Take this sequence: the lane is pushed at X, then a review claim syncs (M1, ref = X), then the
coordination branch moves (another WP's status commit, a concurrent reviewer's push), then the
review claim is run again in the same clone (M2). The ref becomes M1. The approval then stamps
`lane_head = M2` and `lane_head_presync = M1`. Neither is on origin, so an integrator's clone
refuses `APPROVAL_STAMP_NOT_ON_LANE` (absent_from_clone). That is the #7802 failure again, now with
a different remedy text.

I reproduced it with real git and two clones. I copied the WP's own fixture, ran
`attempt_auto_rebase` twice with a coordination commit before each run, approved through
`emit_status_transition` and ran `check_lane` in a fresh clone of origin:
`lane_head=f38f928 presync=bcfe21c (M1) X=d681542` gives `APPROVAL_STAMP_NOT_ON_LANE / ABSENT_FROM_CLONE`.

The code promises more than it does. `LANE_HEAD_PRESYNC_KEY`, `LaneHeadReading`, the
transition-pipeline comment and the `approved_bound` module docstring all say "sync merge(s)",
plural. The ADR amendment only says "each sync that creates a merge overwrites it" and lists no
residual for this case. With five WPs reviewed in parallel on one coordination branch, this case
is common.

Fix (small, inside your owned files): in `_record_review_presync`, keep the existing ref when it
is still the tip the lane sits on through merges only. That is the case when `pre_merge_sha`
equals the recorded ref, or when `pre_merge_sha` sits on it through merge commits alone (the
same test `_presync_of` applies). Overwrite it only otherwise. Add a two-sync case to
`tests/consolidation/test_approval_stamp_presync_7802.py` that is red before the change, and
update the ADR's "The pre-sync record" bullet to match.

**Issue 2 (blocking by CLAUDE.md as written): `src/specify_cli/status/__init__.py` changed with no version bump.**
CLAUDE.md Code Style: "Any changes to `__init__.py` require a version bump in `pyproject.toml` and
a changelog entry". The changelog fragment is present (`7802.fixed.md`). The `pyproject.toml`
bump is missing. I checked the charter for a rule that overrides this. Standing Order 7 and the
Specify bullet ("no version numbers in scope") cover how a Mission is scoped, not package-version
bumps, so I applied the CLAUDE.md rule literally. Either bump `pyproject.toml` in this lane, or
record an operator ruling that the bump happens once at the Mission landing. Several lanes
bumping in parallel would conflict, so the ruling may be the better route. Do not just drop
the rule.

**Non-blocking notes**

- The ADR's "Why the bound keeps its strength" paragraph should say that the existing residual
  "content inside a merge commit" now runs from `lane_head_presync`. In a clone that measures
  from X, any merge commit on the pushed lane after X is dropped, not only merges after M. This
  is the same defect class as before (merges after `lane_head` were already dropped), so it is
  not a weakening, but the residual list should name it.
- Point 1 from the implementer (`reconciliation_bound.approval_stamp_anchors` reads the raw
  `lane_head`): verified that it can only over-refuse. Every consumer of those anchors goes
  through `wp_attribution.lane_exempt_commits`, which skips an anchor git cannot read
  (`GitProbeError`, so it exempts less). The gate re-check (`_bound_anchor_shas`) does not read
  stamps at all. With a present-but-absent-from-lane stamp the raw value exempts no more than
  before. The ADR residual is acceptable as it stands. No fold-in is needed.
- Checklist: dead code PASS (all new symbols have production callers). Synthetic fixture PASS
  (real clones, real reader, real `attempt_auto_rebase`). Silent empty return PASS (the best-effort
  `None` returns of `_presync_of` and `_record_review_presync` are documented). FR coverage
  PASS. Frozen surface PASS (`lifecycle_sync.py` and `status_transition.py` untouched). Locked
  decision PASS (no push, no remote contact). Shared-file ownership PASS. Production fragility
  PASS (no new `raise` on a transient path). The stamp key is in `_PROVENANCE_KEYS` and
  `WINDOW_STAMP_KEYS`, so it is branch-relative like `lane_head`.
