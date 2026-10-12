# Defect diagnosis — consolidation / done-bookkeeping regressions (#6071, #6073)

Calibration: origin/main @ `8a911083`, spec-kitty 4.0.0rc7, **spec_kitty_events 10.4.4**.
All target tests witnessed RED at this commit (commands + failures below). Integration
resume tests reproduced serially (`-p no:xdist`) per the orchestrator note.

Scope: ONLY the tests that stay RED under events 10.4.4 (confirmed by the latest nightly
re-run 38269302579 comments on #6071/#6073, which list the self-healed tests as "Now
passing" and leave exactly these seven red):

- #6071 (integration, `tests/integration/test_merge_lane_planning_data_loss.py`):
  - `test_bare_slug_coord_mission_consolidates_again_after_the_bookkeeping_commit_failed`
  - `test_a_run_killed_inside_the_fold_gets_advice_that_leads_to_a_successful_consolidation[status-pair-only]`
  - `test_a_run_killed_inside_the_fold_gets_advice_that_leads_to_a_successful_consolidation[every-coordination-kind]`
- #6073 (CLI):
  - `tests/specify_cli/cli/commands/test_merge_coord_topology_1772.py::test_post_merge_validation_reads_in_branch_status_path`
  - `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py::test_skip_lanes_flag_is_what_enables_genuine_completion`
  - `::test_skip_lanes_completion_rolls_back_on_post_mutation_failure`
  - `::test_resume_without_reflagging_skip_lanes_auto_honors_persisted_choice`

## Headline: FOUR distinct root causes, not one (prompt hypothesis refuted)

The prompt's strong hypothesis — "post-merge done-bookkeeping no longer lands WP done-rows
on the target under 10.4.4 (WP01 left at approved), which also explains the coord-teardown
refusal and the resume cases" — is **refuted by evidence**. There are four root causes
across three recent changes. B and D share a theme (composed `<slug>-<mid8>` dir recognition
introduced by #5965/#5966) but A and C are independent. Confirm/refute evidence recorded per
cluster below.

---

## Cluster A — #1772 done-bookkeeping post-merge validation (`test_post_merge_validation_reads_in_branch_status_path`)

RED: `typer.Exit 1` → "Post-merge target validation failed: merged WPs did not reach done in
target branch history. Offending WPs: WP01=approved".

Root cause: `done_bookkeeping._parse_target_lanes_by_wp` (L527) is a **hand-rolled
wall-clock reducer** — it sorts events by `(at, event_id)` ascending and last-wins folds.
The #1772 fixture's committed log has `approved` (from_lane in_review, later `at`) and `done`
(from_lane approved, earlier `at`). Sorting by `at` reorders to `[done, approved]` → folds to
`approved` (WRONG). The **canonical reducer** (`status.get_wp_lane` / `materialize`, Lamport,
causal) correctly folds `approved→done` → `done`.

Evidence (probe_reducers.py): for the #1772 log, `_parse_target_lanes_by_wp`→`approved`;
`get_wp_lane`→`done`; `materialize`→`done`. For a realistic full-envelope #5354 log,
`get_wp_lane`→`done` (handles the migration-seed case too).

Regression window: `063fc818` (2026-10-11, "#5354 post-merge done-check orders target lanes
by (at, event_id), not physical line order") introduced the wall-clock sort to fix the
migration-seed physical-order bug (#5354), but broke the causal case (#1772).

Constraint to preserve: the #5354 UNIT test `tests/consolidation/test_done_bookkeeping_seam.py::
test_parse_target_lanes_by_wp_orders_by_at_not_physical_line_order` (newer-`at` `done` beats
older-`at` migration seed written physically after it). The canonical reducer preserves this
invariant with realistic (full-envelope) data (verified). #5354 minimal events lack `from_lane`
so the canonical reducer cannot consume them → the unit test must be re-pointed to realistic data.

Fix (Slice 2): route `_assert_merged_wps_done_on_target` through the canonical reducer
(single-canonical-authority; CLAUDE.md "the merge gate sources its claim through the Lamport
wrapper"). Retire/replace the hand-rolled wall-clock `_parse_target_lanes_by_wp`
(only consumer is `_assert_merged_wps_done_on_target`). Re-point #5354 unit test to
realistic full-envelope data preserving its invariant. Respect the non-vacuity AST pin that
references `_assert_merged_wps_done_on_target` (`reconciliation.py:22`).

---

## Cluster B — #5651 bare-slug coord resume teardown (`test_bare_slug_coord_mission_consolidates_again_after_the_bookkeeping_commit_failed`)

RED: exit 1 → "coordination teardown incomplete: a commit on coordination branch
'kitty/mission-retention-override-01KX0000' changes files outside kitty-specs/retention-override/
... only Mission-directory files are landed during teardown:
kitty-specs/retention-override-01KX0000/status.events.jsonl, .../status.json".

Mission primary dir = bare slug `kitty-specs/retention-override/`; coordination dir =
composed `kitty-specs/retention-override-01KX0000/` (`<slug>-<mid8>`).

Root cause: `phase_teardown._unlanded_paths_outside_mission_dir` (L335) builds
`own_prefixes = {f"{KITTY_SPECS_DIR}/{name}/" for name in {run.mission_slug, run.target_feature_dir.name}}`
— both are the BARE slug. The composed-dir status pair
`kitty-specs/retention-override-01KX0000/...` fails the prefix match → classified "stranded
outside the Mission directory" → raises. Runs ONLY on resume (`_land_late_coordination_commits`,
`if not run.is_resume: return`), which is why the FRESH-consolidation sibling
`test_bare_slug_coord_mission_consolidates_onto_a_protected_target` passes.

Regression window: #5965/#5966 "context-aware disposability" (2026-10-10, phase_teardown
`6534fda8`; the D4 `_unlanded_paths_outside_mission_dir` comment cites #5965).

Fix (Slice 3): widen `own_prefixes` to include the composed `<slug>-<mid8>` coordination
directory via the canonical authority `missions._read_path_resolver.mission_dir_aliases`
(the ONE authority that pairs a bare-slug primary with its composed coord dir, #5651),
exactly as `interrupted_alias_fold_guidance` already does.

---

## Cluster C — #2745 skip-lanes completion + resume (3 tests) — STALE FIXTURE, not a product bug

RED: `test_skip_lanes_flag_is_what_enables_genuine_completion` and
`...rolls_back_on_post_mutation_failure` → exit 1 "Mission is not merge-ready — WP(s) missing
review approval: WP01"; `...resume_without_reflagging...` → "No interrupted merge to resume".

Root cause: the fixture `_bootstrap_direct_on_target_mission(merge_ready=True)` writes an
INVALID transition chain: `claimed→in_progress` then `in_review→approved`. Under events 10.4.x
the reducer validates `from_lane` against the WP's current reduced lane and DROPS a
mismatched event (only the first event seeds freely). So the `in_review→approved` event
(from_lane=in_review, current=in_progress) is dropped → WP01 stays `in_progress` → the
merge-ready precondition (`phase_claim._assert_mission_terminal_ready` /
`status_lanes.mission_terminal_acceptability`) correctly reports it missing approval. The
2nd/3rd tests cascade from the 1st never completing (no interrupted state persisted).

Evidence (probe_variants.py): fixture chain → `in_progress`; `in_progress→approved` (from_lane
matches) → `approved`; full valid chain → `approved`. **Experiment**: patching the fixture to a
valid chain (`claimed→in_progress→for_review→in_review→approved`) makes ALL 3 tests PASS
(102s) — so the skip-lanes/resume PRODUCT path is correct; only the fixture data is stale.

Regression window: events 10.4.x stricter from_lane-validating reducer (10.4.2 "#5967 fix the
status-diary reducer end-to-end"; the tests were already red under 10.4.2 in run 38201164545).
Prompt says do NOT touch spec_kitty_events/the reducer — correct; the stricter reducer is right.

Fix (Slice 4): re-pin the fixture `_bootstrap_direct_on_target_mission` to a realistic valid
transition chain (Charter Standing Order 4: stale→re-pin, realistic data). This is a TEST-DATA
fix, NOT a product fix — a documented divergence from the prompt's "product fix" framing,
flagged in the PR with this evidence. NOT green-washing: no product bug is hidden (verified the
product path works once WP01 is genuinely approved).

---

## Cluster D — #5748 killed-in-fold resume advice (2 params) — composed-dir deletions wrongly disposable

RED: re-run raises `MergeLockError: Merge lock already held for '__global_merge__'`
(executor.py:889) instead of the expected `MERGE_UNSAFE_PRIMARY_DIRTY` refusal.

Mechanism: a subprocess is SIGKILLed (rc 137) at the bookkeeping door AFTER the one-directory
fold unlinked the composed dir's coordination files, leaving those deletions in the root
checkout and the `__global_merge__` lock held. The re-run's pre-mutation dirty-primary guard
(`entry_preflight._pre_mutation_safety_preflight` L173 `assert_worktree_clean(root,
context=residue_context)`) runs BEFORE the lock (executor L888). The #5748 machinery
(`resume_recovery._report_interrupted_alias_fold` + `preflight.interrupted_alias_fold_guidance`)
only renders its abort-advice when a `MERGE_UNSAFE_PRIMARY_DIRTY` refusal is RAISED.

Root cause: the #5965/#5966 role-based residue classifier
(`coordination/coherence._is_disposable_residue`) treats the composed dir's deleted
coordination-kind files as disposable coord-partition residue (`mission_dir_aliases` includes
the composed dir, so they are "this mission's" coord residue, step 5). So
`assert_worktree_clean` does NOT raise → the preflight passes → the run proceeds to the stale
lock → `MergeLockError`. The #5748 refusal never fires.

Regression window: #5965/#5966 "context-aware disposability and destructive-guard API"
(2026-10-10 `0ff2225f`; `f43599bf` routed consolidation destructive sites through the guard).

Fix (Slice 4): make the interrupted-fold composed-dir deletions trip
`MERGE_UNSAFE_PRIMARY_DIRTY` so the existing #5748 guidance renders. Lowest-risk design: add a
dedicated interrupted-fold detection in the pre-mutation primary-checkout leg (reusing the
existing `interrupted_alias_fold_guidance` / `_is_deleted_coordination_file` predicate) that
refuses BEFORE the residue-based clean check swallows the deletions — without loosening the
shared #5965/#5966 residue classifier. Verify the `--abort` step then reclaims the stale
same-owner lock. CONFIRM exact locus empirically during implementation.

---

## Invariants to preserve (cited)
- CLAUDE.md "Consolidation & Preflight Patterns", "Status Model Patterns" reducer-duality note
  (Lamport `reduce`/`materialize` is the merge-gate authority; `reduce_parsed` is wall-clock LWW).
- Single rollback authority ADR `2026-09-19-1`; AST pin `tests/consolidation/test_single_rollback_authority.py` — re-point, never loosen.
- done-bookkeeping / coord-teardown-integrity ADRs #5571/#5613/#4996; non-vacuity pin referencing `_assert_merged_wps_done_on_target` (reconciliation.py:22).
- Charter Standing Orders 2 (tidy-first enabler commits precede the fix), 4 (red-first, realistic data, never retry-to-green), 5 (gate discipline), 9 (red-main, never green-wash).

## Out of scope (orchestrator-unclassified / self-healing — do NOT touch)
test_charter_pack_collect provenance, test_init_default_preset, test_dogfood_corpus_backfilled,
test_owned_charter_generation[wrong_identity], test_two_partition_preview C-001,
test_owned_lifecycle_acceptance_review, test_mission_close_discard_single_branch,
test_post_merge_index_refresh, test_merge_refresh_and_invariant, test_2646_* (verified green per orchestrator).
