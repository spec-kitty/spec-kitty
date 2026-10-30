# Discovery findings — birth-cutover fixture planning commit

Recorded during the discovery step (maintainer-k), from the grounding pass on
`main@512567eee7`. Everything here was verified directly in this clone, not
taken from the issue text.

## Decisions

1. **The fixture is wrong, not the product.** `EVIDENCE_WINDOW_UNCOMPUTABLE`
   is a deliberate fail-closed rule of #6715 (`8c5703e48f`, adds
   `src/specify_cli/consolidation/wp_evidence.py`): without a recorded
   `planning_commit_sha`, the evidence window `planning_commit..lane tip`
   cannot be computed and "landed as reviewed" cannot be verified. The gate's
   own refusal text names the recovery — `spec-kitty agent mission
   finalize-tasks` — so a mission that skips the production finalize path and
   hand-writes `lanes.json` (as this fixture does) is expected to be refused.
   Rationale: every real mission records the planning commit via
   `tasks_finalize._finalize_lanes` or `mission_state._write_rebuilt_lanes`,
   both of which capture the target-branch tip with
   `specify_cli.core.vcs.git.capture_branch_tip` (#4857's canonical
   tip-capture authority). The birth-cutover fixture predates #6715 and was
   never updated. Weakening the gate would be an operator ruling and would
   re-open the hollow-WP hole #6715 closed; the mission brief forbids it.

2. **The fix shape.** `_write_single_lane` in
   `tests/migration/test_birth_cutover.py` gains the captured planning
   commit: `capture_branch_tip(repo, "main")` at `lanes.json`-write time —
   the same "captured target tip" semantics `_finalize_lanes` uses — recorded
   as `LanesManifest.planning_commit_sha`, asserted non-None so the fixture
   fails loudly at setup if the capture ever breaks (the #6798 lesson:
   fixtures that bypass the production path go stale silently). The
   hand-written lane shape stays: it is deliberate test control (one `lane-a`
   with `write_scope=("src/a/**",)`), and `computed_from="test-fixture"` is
   an input description the gate does not read.

## Evidence

- Reproduction on pristine `main@512567eee7`:
  `uv run --frozen python -m pytest tests/migration/test_birth_cutover.py -q`
  → **4 failed, 20 passed**; the four failures are
  `test_birth_cutover_reconciles_at_merge_no_manual_backfill[coord|lanes]` and
  `test_birth_cutover_status_phase_is_primary_only[coord|lanes]`, all with the
  claim-time refusal `EVIDENCE_WINDOW_UNCOMPUTABLE: WP01 has no evidence
  window (lane-a: lanes.json records no planning commit)`.
- Window mechanics, verified by reading `wp_evidence.py` +
  `lanes/compute.py`: for a code lane the window is
  `lanes_manifest.planning_commit_sha .. lane_created_branch(...)`. The
  fixture's lane branch (`kitty/mission-<slug>-lane-a`) forks from the
  mission/coordination branch and carries the
  `feat(<slug>): WP01 adds src/a/foo.py` commit; capturing the `main` tip at
  lanes-write time (before the planning-content commit) yields a base whose
  tree diff to the lane tip contains `src/a/foo.py` — a non-bookkeeping path
  matching WP01's `owned_files: src/a/**` — for both topologies. The
  remaining #6715 verdicts then pass: the window diff is readable, the owned
  change exists, and the approving reviewer (`reviewer-renata`) is
  independent of the implementer (`python-pedro`).
- Not superseded: `git log -- tests/migration/test_birth_cutover.py` shows
  nothing newer than `7559e4336b` (pre-#6715); no open PR targets #6801.
- Blocked consumers: open PRs #6795 and #6804 fail `tests (events
  consumers)` on this file (diff-selected job; the red is latent on main).
- Parallel precedent: #6798 / PR #6802 — same class (fixture bypassed the
  production path, went stale against a later rule), fixed in the fixture
  with assertions unchanged; test-only, no changelog.

## Open questions

- None blocking. The only judgment call — fixture vs gate — is decided above
  on the refusal text's own recovery pointer and the finalize-path parity; if
  review disagrees, the fallback is STOP-and-report, not weakening the gate.
