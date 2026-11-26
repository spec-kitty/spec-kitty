# Squad 3: pre-accept brownfield (2026-11-26)

Point-cut: before accept. Subject: lane-m b4db082483, which contains every lane.

Lenses and verdicts:
- integrity: claude::debugger-debbie, ACCEPT
- architecture: claude::architect-alphonso, ACCEPT-AFTER-FIXES
- fidelity: claude::reviewer-renata, ACCEPT-AFTER-FIXES

None of the findings lands unreviewed content. Every finding was folded into WP13 cycle 3 (lane-m b6df77436c), and claude::reviewer-renata approved that cycle (red-first: 14 failed and 153 passed against b4db082483 src).

| Finding | Disposition | Evidence |
|---|---|---|
| A1 (MED): two canceled-window rules (incorporate first-parent and raising; reconciliation_bound any-parent and fail-closed) | changed | 3792ef50cb: one public `wp_attribution.merges_in_canceled_windows`, used by both callers. Tests `test_hand_merge_hidden_behind_a_clean_merge_in_a_canceled_window_is_refused` and `test_canceled_window_without_lane_heads_holds_every_merge`. The WP08 probes still refuse |
| A2 (MED): auto-rebase `git merge` ran without the pinned merge config | changed | d9effb445a: runs under `merge_probe_env(make_merge_env())`, the same behaviour as `--incorporate`. Test `tests/lanes/test_auto_rebase_pinned_merge_config.py`: hostile config reds plus a no-change control |
| F1 (MED): FR-003 conflicted-path list not pinned exactly; missing lane checkout gave no halt reason | changed | d9effb445a: `test_conflict_halt_lists_exactly_the_conflicted_paths` (with a non-conflicting control); `NO_LANE_CHECKOUT_HALT` reason; 7755 test updated (leeway) |
| F2 (MED): printed RESOLUTION_MERGE_UNREVIEWED route never followed to a landing | accepted | f3db91c276: `test_printed_recovery_lands_the_mission_on_a_protected_main_coordination_mission[squash,merge]` reaches exit 0 with the verified banner. The behaviour already held, so the test was green on its first run |
| A3 (LOW): private `_is_bookkeeping` imported across modules | changed | 47b8c456b4: public `reconciliation_kernel.is_mission_bookkeeping_path` |
| A4 (LOW): private `_make_merge_env` imported across modules | changed | 47b8c456b4: public `make_merge_env`. The shipped migration m_3_2_7 is left unedited (DIRECTIVE_044) |
| A5 (LOW): second approved-membership derivation | changed | 3792ef50cb and 4b987b2d50: public `reconciliation_authorship.approved_wp_ids`; `_APPROVED_LANES` removed |
| A6 (LOW): "single definition" docstring | changed | 4b987b2d50: two-tier docstring |
| A7 (LOW): advisory probe on a memo miss lost `attributes_source` | changed | 4b987b2d50: `test_advisory_entry_probes_with_the_claims_attributes_source` |
| A8 (LOW): `auto_rebase_record.delete` missing from `__all__` | changed | 47b8c456b4 |
| A9 (LOW): stale `skip_target_branch_commit` docstring clause | changed | 47b8c456b4 |
| I1 / integrity F1 (LOW): a forged auto-rebase record | changed | d13221cd4d: ADR 2026-10-04-5 states the record is clone-local state, not proof. A forged record loses the early refusal and SC-003, never integrity; the gate judges the content |
| I2 / integrity F2 (LOW): a refused `--incorporate` had already claimed the WP and merged the sync point | changed | 3792ef50cb: option (a). `prepare_incorporation` runs the attribute guard before the claim and the sync. Test `test_refusal_has_no_side_effect[INCORPORATE_MERGE_ATTRIBUTES_REFUSED]` |
| F3 (LOW): agreement test's subset half was tautological | changed | 58666307b5: gate side built from `_drop_unreviewed_merges` alone. A mutation turns 4 cells red |
| F4 (LOW): one auto-rebase move per lane per attempt not pinned | accepted | d13221cd4d: comment, test `test_a_second_auto_rebase_of_one_lane_in_one_attempt_is_reported_not_restored[2]`, and a residual in ADR 2026-09-19-1 |
| Integrity "not probed" list (WP03 rollback after an implement re-entry; FR-009 after a halted `--resume`; #7861 write onto protected main; committed union from an unreviewed planning commit; lane-committed `.gitattributes` through the auto-rebase; amended tool merge; three-lane and lanes topologies; `orchestrator-api consolidate-mission`) | deferred_with_rationale | These are coverage gaps the lens disclosed, not findings. They go to the in-session adversarial review of the consolidated tree (the "Independent adversarial review (agent)" PR comment). Any finding from that review is folded before the PR is marked ready |

Process note: 3792ef50cb does not import on its own (`approved_wp_ids` becomes public in 4b987b2d50). The reviewer made this binding at PR preparation: squash it so every PR commit is bisectable.
