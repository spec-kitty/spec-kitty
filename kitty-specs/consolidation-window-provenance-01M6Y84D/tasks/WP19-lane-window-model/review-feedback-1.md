# WP19 review feedback, cycle 1 (reviewer-renata, claude-sonnet-5-5)

Verdict: REJECTED for one REQUIRED CHANGE (operator ruling 2026-11-09, binding). Everything else
checked out; the rework is limited to the items below, so the next cycle should be short.

## REQUIRED CHANGE R1: a canceled work package's own commits are exempt from the lane window check (HIGH, blocking)

Operator ruling 2026-11-09 (binding): a CANCELED work package's own commits are EXEMPT from the lane
window check. The existing mixed-lane / canceled-content rules (closed world,
`--attest-canceled-superseded`, the canceled-content gate axis) remain their sole judge.
Data-model WW-5 already says "canceled work packages keep the mixed-lane rules"; WW-2 as implemented
contradicts it, because tier 2 gives a canceled work package no window and so refuses its commit.

Probe (your tracer entry `design-decisions-03233d01045a`, "WP19 OPEN QUESTION"): lane-a, WP02
claimed, commits `src/pkg/canceled.py`, canceled; then WP01 claimed, commits, approved, no stray at
all. Today the claim refuses `LANE_MOVED_AFTER_APPROVAL: commit <C> ... was committed after WP01's
approval`. That text is also false (C predates WP01's claim), and re-approving WP01 never clears it.
Before WP19, WP01's own stamp exempted C and the mixed-lane axis judged it.

Required, all five (this order, red first):

1. **Exempt canceled work packages' own commits from the window check.** In
   `reconciliation_bound._lane_verdict`, collect the canceled work packages' own attributed commits
   for the lane and pass them to `check_lane_windows` as an extra exempt set that is unioned into the
   **tier-2** `exempt` only (`_window_refusals`). Reuse what the mixed-lane resolution already
   computed (`resolve_canceled_wp` -> `Attributed.commits`, built from the canceled work package's
   `lane_head` work windows in `wp_attribution._windows` / `_window_commits`); do not run a second
   spine walk (NFR-007, and the exempt set is still computed once per lane). When the canceled work
   package is `Unattributable` (no stamps, open window, unreadable spine) exempt nothing for it: the
   mixed-lane refusal stands on its own and runs before the bound, so that verdict is unchanged.
   Do **not** change tier 1: `check_lane` keeps refusing a canceled work package's commit made
   AFTER an approval stamp (#5720, `test_approved_bound_residuals.py`); the ruling is about the
   window check (tier 2). Say so in the `check_lane_windows` / `_lane_verdict` docstrings, and add a
   pin test that a canceled work package's commit after the approval stamp still refuses via tier 1.
2. **Red-first test reproducing the probe**, committed red alone before the fix
   (`test(WP19): red-first canceled-commit exemption`), in `tests/consolidation/test_lane_approval_windows.py`,
   built through the production status shell so windows are really recorded (not hand-written events):
   canceled WP02 commits C before WP01's window (WP01 claimed after C), WP01 approved, no stray.
   Two parametrized outcomes, each asserted through `consolidate --yes` and `--dry-run --json` with
   `ref_shas` unchanged on refusal:
   - C superseded by WP01's approved work (same path, WP01 rewrites it): passes (exit 0), no
     `LANE_MOVED_AFTER_APPROVAL`.
   - C not superseded: refused by the **existing mixed-lane / canceled-content outcome**, never by
     `LANE_MOVED_AFTER_APPROVAL`. Establish the expected verdict by running the same fixture on the
     parent of the WP19 fix (`eca56240cd^`, where WP01's own stamp exempts C) and require the
     identical verdict after the rework.
   Record the red SHA and the failure text (`-rf`) in the history note, as for the first red.
3. **Corpus cell built with real window data.** The existing mixed-lane builders write events
   without `wp_window`, so their lanes count as all-gap and never reach tier 2 (this is why no
   corpus cell showed the bug). Add a builder variant that goes through the production status shell
   (you already did this for the mixed-lane row in `test_refusal_precedence_matrix_windows.py`; reuse
   that builder), or use `set_window_states`. Cell key e.g.
   `fresh|mixed_lane_canceled_wp|stamp=present|window=recorded|canceled_commit_before_window` (add a
   forecast twin only if `NAMED_KEYS`/scenario conventions pair them). **Additive only**: regenerate
   with `regenerate_cells([<new keys>])`; afterwards
   `changed_cells('eca56240cd^')` must equal the four existing keys plus the new key(s), and
   `changed_cells('d75a02c454')` must list ONLY the new key(s). Any other changed cell is a STOP.
4. **Seeded-mutation row** that would catch losing the exemption: add a row to
   `tests/consolidation/test_reconciliation_seeded_mutations.py` whose mutation drops the canceled
   exempt set (the canceled commits are not exempted in tier 2), expected red cell = the new corpus
   cell. The mutation target must be defined in exactly one split module
   (`test_every_mutation_target_is_defined_in_exactly_one_split_module`): target the function in
   `reconciliation_bound` that builds the set (the new helper or `_lane_verdict`), and extend the
   module table at the top of the file. Run the harness twice, green both times.
5. **Record the ruling.** `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP19" --entry "..."` with (a) the ruling and its date, (b) that
   it resolves the "OPEN QUESTION" entry (reference it by id `03233d01045a`), (c) the tier-1 /
   tier-2 split above, and (d) a sentence prefixed `ADR note for WP21:` stating "a canceled work
   package's own commits are exempt from the lane window check (tier 2); the mixed-lane and
   canceled-content rules are their sole judge; tier 1 (post-approval, #5720) is unchanged", so
   WP21 can carry it into the Mission ADR (T111) and the data-model WW-2/WW-5 wording. WP21 owns the
   ADR; do not edit the ADR here. Also add the changelog fragment sentence only if the Before/After
   changes (it does not; leave the fragment as is).

## Other findings (all non-blocking; fix in the same pass where cheap)

| # | Severity | Finding | Action |
|---|----------|---------|--------|
| F1 | Low | No seeded-mutation row witnesses tier 2 on its own. The only rows over this code are the whole-function `approved-bound` row (red on `fresh\|single_lane\|stamp=missing`, a tier-1 cell) and the `write-branch` row (single_branch). A mutation that makes `check_lane_windows` return no tier-2 refusals, or restores the own-stamp exemption, stays green. | Add one row, e.g. `lane-window-tier-two` (tier 2 never refuses / own stamps put back into the exemption anchors), expected red on `fresh\|two_wp_lane\|stamp=present\|window=recorded\|commit_between_approvals` and `...rewound`. Same module-table rule as R1.4. |
| F2 | Low | `test_gap_then_recorded_stray_commit_refuses` asserts the fresh run and `--dry-run --json` per the prompt, but the corpus only has the one fresh gap-then-recorded cell; no forecast twin for (a)/(a mixed)/(c). `changed_cells` lists exactly four keys, all `fresh|`. Verify this is the corpus convention (WP02 recorded forecast cells only for named scenarios); if a forecast twin exists for the plain two-WP lane, it did not change, which would be wrong. | Confirm in the history note that no forecast/resume twin applies; I found none that should have flipped. |
| F3 | Info | `_stamps_by_lane` calls `approval_stamp_anchors` once per lane; the concatenated order equals today's single call (checked: same generator order, so the all-gap anchor list is identical to today's). | None. |
| F4 | Info | `_preceding_wp` still does `min()` over a possibly empty `after` list. It cannot be reached after tier 1 passes (every non-exempt content commit is then reachable from an own stamp), and R1's exempt set only removes commits, so the invariant holds. | Add one sentence to the `check_lane_windows` docstring stating the invariant so a later change to tier 1 does not silently break it. |

## Verified, no change needed

- **Red commit** `eca56240cd` (temporary detached worktree in `/tmp/claude-1000/`, removed after):
  `test_lane_approval_windows.py` gives 5 failed, 11 passed. The 5 failures are the five named red
  tests; each fails because `consolidate` succeeds (exit 0, "Reconciliation verified", lane merged),
  i.e. "no refusal", not a fixture error. Guards green.
- **Corpus**: `changed_cells('eca56240cd^')` is exactly the four allowed cells:
  `fresh|two_wp_lane|stamp=present|window=gap_then_recorded|commit_between_approvals`,
  `...|window=recorded|commit_between_approvals`, `...|window=recorded|commit_between_approvals_text`,
  `...|window=recorded|rewound`.
- **Pins** (`-rxX` on `test_reconciliation_intended_verdicts.py`, 11 passed, 2 xfailed): (a),
  (a mixed), (b) and (c)[lanes] pass; only `[single_branch]` rewound and WW-6
  (`test_parallel_claims_window_is_not_over_wide`) remain xfail; no XPASS.
- **WW-2a**: own-lane stamps no longer exempt (`test_own_lane_approval_stamp_does_not_exempt`),
  cross-lane stamps still do, other lanes selected by lane id (`test_dependency_chain_stray_is_exempt`).
  All-gap lane calls `check_lane` with today's anchors and no `exempt` keyword; byte-equal text test passes.
- **Precedence**: `test_refusal_precedence_matrix_windows.py` (6 rows, 9 -> 15) passes; WP03's
  `test_refusal_precedence_matrix.py` and the seeded-mutations file are byte-unchanged.
- **NFR-007** query-count tests pass (5 queries per added work package, budget 8; independent of commit count).
- **Changelog fragment** `7403-lane-approval-window-refusal.changed.md`: one entry, section `changed`,
  style check 0 errors (the 104 warnings are other fragments), spelling check 0 findings.
- **Seeded mutations** green (24 rows). `ruff check` clean, `C901` clean, `ruff format --check` clean on
  all touched files, `mypy` clean on the four source files, no new `# noqa` / `# type: ignore`.
- **Dead symbols**: base `dcb8eab625` lists 9, the lane tip lists 6 (`live_lane_tips`,
  `OpenerSelection`, `WindowGapReason`, `window_opener_events`, `LaneHeadProbe`, `probe_lane_head`);
  `WindowGap`, `WindowOpen`, `window_open_of` are now used; nothing WP19 added is flagged. The two
  `test_no_dead_symbols.py` failures are these six, red on the base too, owned by WP20/closeout.

## Tests run (all in the lane worktree, targeted files only)

- `test_lane_approval_windows.py test_lane_window_query_count.py test_write_branch_bound.py test_approved_bound.py test_approved_bound_residuals.py`: 117 passed, 1 xfailed.
- `test_reconciliation_intended_verdicts.py -rxX`: 11 passed, 2 xfailed.
- characterization, both precedence files, surface pin, family guard, claim-inputs parity, resume frozen anchors, `tests/integration/test_single_branch_approval_windows.py`, the two `tests/orchestrator_api` files: 115 passed, 1 xfailed.
- `test_reconciliation_seeded_mutations.py test_single_rollback_authority.py test_exemption_registry_ratchet.py test_no_legacy_terminology.py` plus `test_no_dead_symbols.py`: 191 passed, 2 failed (the six pre-existing dead symbols above).
- Not run (per policy): `make test-fast`, whole `tests/consolidation/` and `tests/terminus/` directories.

After the rework, re-run the Definition-of-Done commands for the touched files, `changed_cells` as
in R1.3, and hand back to review.
