# Post-tasks squad: findings and dispositions

**Question:** will the WPs, executed as written, deliver every requirement with non-fakeable tests, against the real
code and gates?

**Cast:**
- `reviewer-renata` (test plan / slicing anti-laziness)
- `architect-alphonso` (code-truth / gate coverage)

Both returned **READY WITH FOLDS**. Full reports are in the session scratchpad. Each fold landed in the WP prompt's
"Post-tasks squad folds (binding)" section unless noted otherwise.

| # | Sev | Src | Finding | Disposition |
|---|---|---|---|---|
| 1 | HIGH | renata | WP01 fixture: `claimed→in_progress` needs `workspace_context`; a reset needs `reason`; without them the red test is red for harness reasons | accepted: WP01 T004 step 3 + folds; WP03 folds |
| 2 | HIGH | renata | "Refuse before any write" is fakeable: status bytes stay identical on success too, so a late chokepoint raise passes | accepted: WP01 refusal amendment adds WP03 (seed event) + positive control; WP03 spy test that no status writer runs |
| 3 | HIGH | renata | The sweep is satisfiable by "always refuse" | accepted: WP02 folds (independent expected-outcome oracle, `raised == expected`, minted ids ∉ reserved) |
| 4 | HIGH | alphonso | Wrong dead-symbol gate named; the real one is `test_no_dead_symbols.py` | accepted: WP02/WP03 folds, plan test list; remedy constants private; WP03 must turn the gate green |
| 5 | HIGH | alphonso | C901 is baselined off for `compute.py`; `compute_lanes` = 35 | accepted: measure `--isolated`; `compute_lanes` must not grow; helpers ≤ 15 (WP02 folds, plan) |
| 6 | MED | alphonso | Early returns skip the conflict checks | accepted: collect conflicts right after the planning/code split (WP02 folds + tests) |
| 7 | MED | alphonso | Pre-union before Rule 1 erases overlap evidence; independent-collapse count | accepted: frozen union after Rules 1/2; pin the count choice with a test (WP02 T006 step 4 + folds; plan) |
| 8 | MED | alphonso | Fixtures must amend `wps.yaml` when present | accepted: WP01/WP03 folds |
| 9 | MED | alphonso | Phase-module seam test constrains mocks | accepted: WP03 folds (patch on the lanes namespace; out-of-map seam list update allowed with rationale) |
| 10 | MED | alphonso | `finalize_tasks` complexity is 14 | accepted: preflight inside the existing `if not refresh_planning_commit:` block (WP03 T011 step 2) |
| 11 | MED | alphonso | `read_events` raises `StoreError` (it does not skip); non-UTF-8 → `UnicodeDecodeError`; `OSError` | accepted: catch all three as `status_unreadable` (WP03 T010) |
| 12 | MED | renata | US3 AS2 has no named test | accepted: WP02 folds |
| 13 | MED | renata | The FR-008 tip fallback is never tested end to end | accepted: WP03 folds (tip-fallback e2e) |
| 14 | MED | renata | The AS6 absent-log fixture would be frozen by the tip fallback | accepted: WP03 folds (no allocation) |
| 15 | MED | renata | FR-009 preview, and the refresh/single_branch skip, are untested | accepted: WP03 folds |
| 16 | MED | renata | The `started_wp_removed` remedy round-trip is untested; eligibility reads frontmatter `lane` | accepted: WP03 folds (round-trip test with the actual semantics) |
| 17 | MED | renata | WP04 documents WP03 behaviour | accepted: WP04 now depends on WP02 + WP03 (`wps.yaml`, frontmatter) |
| 18 | MED | renata | Wrong entry-point pointer (the root app runs a schema gate) | accepted: WP01 T004 step 2 → the `mission_app` idiom |
| 19 | LOW | renata | Remedy hygiene untested | accepted: WP03 folds |
| 20 | LOW | renata | Cross-run determinism (hash seed) | accepted: WP02 folds (shuffled input orders) |
| 21 | LOW | renata | FR-004 wording vs read-back | accepted: spec FR-004 reworded (minting) |
| 22 | LOW | renata | WP02 ~1,000 lines > 700 heuristic | deferred_with_rationale: cohesive single concern (pure core). Splitting it would put compute and its sweep in different lanes with no parallel gain. |
| 23 | LOW | alphonso | `__all__` / `OSError` in `recorded_tip_branches`; no `lanes/__init__` re-export; ARG001; SINGLE_BRANCH post-check; `stale_repository_root_copy` key; positive started set; CHANGELOG style test; ADR index | accepted: WP02/WP03/WP04 folds; positive `STARTED_LANES` set in WP02 T005 |
