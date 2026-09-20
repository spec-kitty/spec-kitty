# Tracer — Design Decisions (terminus-safety-invariant)

Seeded at planning 2026-09-19; append during implementation.

- **D1** Scope = full terminus-safety invariant (merge+accept+close), fold #4764/#4765/#4474/#2745 (operator).
- **D2** `warn` softens evidence-QUALITY only; terminal-lane invariant HARD regardless of mode ⇒ merge gets an unconditional merge-ready precondition, not rollback-only (operator).
- **D3** Parent epic #3897 (operator).
- **D4** Per-command predicates through ONE shared aggregate; REJECT single `is_mission_completed` (false-blocks normal merges, vacuous on --resume). merge=merge-ready; close=`is_mission_merged`; accept=summary.ok rerouted (agent, flagged).
- **D5** #2745 rollback-after-target-advance (direct-on-target) = own WP; defer as tracked #3897 follow-up only if it balloons, with a refuse-before-advance interim guard (agent, flagged).
- **D6** Fold #2745 completion affordances too — `merge --skip-lanes` + mission-close orphan/doubled-slug/--json (operator, post-spec).
- **D7** #4474 gets a delivering FR-011 (topology-aware bake write-back / surfacing), distinct from #4764 (agent, post-spec repair).
- Consolidation: ADD one aggregate `mission_terminal_acceptability` in status_lanes.py; UNIFY the coord-transaction machinery; RETIRE doctor.py terminal-set dup. Adoption scoped to specify_cli (shrink-only runtime ledger).

## Append log (implementation)
- (WPs append here)

- WP01 (25f5f1c/bbe1dfb): `mission_terminal_acceptability` added to status_lanes.py (pure, provenance-aware, iterates is_acceptable_ending over WP snapshots); doctor.py terminal-set dup retired → status_lanes.TERMINAL_LANES. Confirmed accept lane views left untouched (provenance-blind by design). 15 red-first + 10 parity tests green.

- WP02 (fe5457f/c028dd8/967b3f3): T006 de-conflate (missing-approval finding blocking=False unconditionally; quality gates stay mode-gated). T007 `_assert_mission_terminal_ready` precondition in `_phase_gates_and_state` before consolidation, raises typer.Exit(1). T008 unified `_CoordCheckpoint` primitive; pre-mutation rollback wraps ONLY `_phase_merge_lanes` (git revert can't cross a consolidation merge commit — scaled back from whole-span). T021 skip_lanes via `_synthesize_no_lane_manifest` reusing is_planning_artifact_only machinery. **D5: coord rollback SHIPPED; direct-on-target rollback-after-advance DEFERRED → #3897 follow-up (refuse-before-advance interim guard shipped).**

- WP03 (7f21bbb/6b553f9): topology-aware bake — new `_bake_mission_number_on_primary_tree` writes+commits meta.json on main_repo's own checkout (coord branch is lifecycle-only, structurally lacks meta.json); `_surface_unbaked_mission_number` merge-summary line as fallback. path_is_under_worktrees guard preserved (2x). No dead-symbol re-pin (bake helper bodies untouched). Persist is the preferred outcome; fallback only when genuinely unreachable.

- WP04 (ee26662): already-coherent via WP02 — NO done_bookkeeping.py product change. `_durable_done_wps_on_coordination_ref` is cacheless (re-resolves the live coord ref each call) and WP02's `_reset_coord_to_checkpoint` moves ref+worktree bytes in lockstep, so the durable read cannot observe stale post-rollback content. Added a coherence-PINNING regression test with a non-vacuity proof (monkeypatch WP02 reset→no-op ⇒ RED; real reset ⇒ GREEN).

- WP05 (ad370d7/b68d791): `--skip-lanes`/`--no-lanes` CLI option on `merge`, threaded merge()→_run_real_merge→_run_lane_based_merge(skip_lanes=) to WP02's executor capability (executor.py untouched). Tests assert GENUINE completion (merged_at baseline + target ref advance), no-bypass refusal (precondition not MissingLanesError), and transactional rollback on post-mutation failure.

- WP06 (73a4b53/574e2ff): `is_mission_merged` fail-closed guard at close_cmd non-discard else (mission_type.py:674-686), mirrors reopen_cmd #1926; refuse routes _emit_mission_error(code=mission_not_merged)+Exit(1). D4 boundary pinned (all-cancelled-unmerged still refuses). Added `--json` to mission close (was Typer exit-2). Orphan-branch close was ALREADY correct (#4163/#1848) — kept as regression guard. Out-of-map (justified+flagged): regenerated _completion_manifest.json (docstring drift); re-pinned test_mission_close_discard_coord_teardown.py which was asserting the #4765 defect (stamped merged_at to preserve its real teardown-routing intent).

- PRE-PR SQUAD FOLDS (9104beb/e8b0e4f/577ec7d): F1 (HIGH) primary-tree bake advanced the TARGET ref pre-merge, defeating _restore_pre_target_if_at_baseline's exact-SHA guard → coord rollback skipped on _phase_mission_to_target failure (US3-1/SC-003 split-brain reintroduced). Fixed by re-anchoring target_baseline_sha past the bake + _revert_orphan_target_bake_commit (forward-reversing revert, clears mission_number_baked for resume); chose re-anchor over relocate to preserve #4474's merged-content contract. F3 (MED) precondition failed-OPEN on a WP absent from the snapshot → now folds absent WPs into missing (fail-closed). F2 (LOW) skip_lanes now persisted on MergeState so --resume auto-honors it.
