# Contract: Birth-cutover fixture evidence parity (for #6801)

**File**: `tests/migration/test_birth_cutover.py`
**WP**: WP01

## Fixture setup contract

The hand-bootstrapped born mission in `_bootstrap_born_mission` (which never runs
`spec-kitty agent mission finalize-tasks`) must record the same evidence shape a
production mission records, so the #6715 consolidation evidence axis
(`src/specify_cli/consolidation/wp_evidence.py`) computes rather than refuses.

### `LanesManifest` written by `_write_single_lane`

```python
planning_commit_sha = capture_branch_tip(repo, "main")   # production helper,
                                                          # specify_cli.core.vcs.git
assert planning_commit_sha is not None, (
    "birth-cutover fixture: no planning commit captured on 'main'; "
    "#6715 EVIDENCE_WINDOW_UNCOMPUTABLE would refuse at claim time"
)
manifest = LanesManifest(..., planning_commit_sha=planning_commit_sha)
```

- The tip is captured with `capture_branch_tip` — the canonical tip-capture
  authority (#4857) — never a hand-rolled `rev-parse`.
- Capture happens where `lanes.json` is written, i.e. **before** the fixture's
  planning-content commit, mirroring `tasks_finalize._finalize_lanes`
  (`capture_branch_tip` of the target-branch tip at finalize time).
- The non-None assertion is the fixture's own guard (DIRECTIVE_041): a stale
  fixture fails loudly at setup instead of producing a misleading claim-time
  refusal.

### Approval transitions written by `_drive_claimed_through_approved`

- Implementing hops (`in_progress`, the forced `for_review` gate hop) are recorded
  with `actor="python-pedro"` — the identity `_claim_real` claims the WP with
  (the implementer of record).
- Review hops (`in_review`, `approved`) are recorded with
  `actor="reviewer-renata"`, matching the `ReviewResult(reviewer=...)` already
  carried in the evidence payload.
- All other transition properties (force flags, reasons, evidence, review
  result) are unchanged.

This mirrors the suite's canonical `_seed_wp_approved`
(`tests/specify_cli/test_specify_topology_flag.py`, #5939/#6370/#6715): a
reviewer distinct from the implementer of record approves, so
`actor_identities_independent` (`src/specify_cli/status/models.py`) confirms
rather than refuses (`REVIEW_NOT_INDEPENDENT`).

## Non-goals

- The gate itself (`wp_evidence.py`) is fail-closed by design and stays
  byte-identical; the four anchor tests' assertions are unchanged.
- The one stale facet of the same class outside this mission
  (`tests/specify_cli/cli/test_accept_birth_cutover.py`, out-of-matrix) is
  tracked by a follow-up issue, not here.
