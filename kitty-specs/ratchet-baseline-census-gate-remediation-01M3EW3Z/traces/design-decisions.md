# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-26 · claude · Stale-entry policy split (post-spec divergence renata vs priti/debbie): hand-curated allowlists (join, kernel, os-detect) fail on stale entries; census allowlists keep documented warn-on-stale so unrelated src deletions never fail a census gate. Rationale: epic #5104 goal 'no manual re-pin toll on unrelated changes'.

2026-09-26 · claude · Post-spec squad folded: FR-003 exemption list pinned empty by frozenset equality; FR-011 'enforced' = consumed by a comparison that fails when live exceeds the leaf; exemptions counted per site; 6 os-detect path:line pins added (94 total); #3962 folded into FR-010; widened predicate lives in the ban test module (C-005).

2026-09-26 · claude · CHARTER EXCEPTION (ATDD-First C-011) for WP09, operator-approved 2026-09-26 (stijn-dejongh via AskUserQuestion, analysis finding D1): WP09 deletes tests/status/test_parity.py whose invariants are already enforced by surviving tests; no honest failing-first test exists (a tombstone or a base-green test would be fake). Substitute evidence: a committed, reviewer-re-runnable mutation script proving every invariant of the deleted file is caught by a surviving test. WP05 and WP07 do NOT use the exception: their first commits are honest RED tests (WP05 test_load_baseline_rejects_retired_keys; WP07 import of _surface_resolution_scan in the survivor).

2026-09-26 · claude · WP05 base evidence: failing-first test_load_baseline_rejects_retired_keys (commit e86a715b) RED 4 failed on base -- owner/provisional/code_only_suppressions cases raise "baseline entry -1: 'mission' must be a non-empty string, got None", mission case raises "baseline entry 0: 'owner' must be a non-empty string, got None"; none says 'unknown key'. Symbol grep (MAX_UNASSIGNED_ENTRIES..UNASSIGNED_OWNER over tests/src/scripts excluding _inert_slots.py): 0 callers; unassigned_entries/masking_suppressions read by 0 comparisons in test_ratchet_baselines.py. Stale rows: base run warns 'inert-slot baseline shrank; delete cleared ledger rows: styleguide-references, model' (3 passed, 1 warning). #5117 reproduction recorded (issuecomment-5847419103 + correction 5847421331): code_only_drift -> new=[model @ agent-profile.schema.yaml], stale=[]; actual suppressor is the bare-name collision 'model = schema.model_validate(data)' at src/charter/offering/drg/project_scan.py:207, NOT Field(alias='model') as the WP prompt assumed (kw.arg yields 'alias'). Owner anti-weasel invariant was lost in #3285 when its enforcing tests were removed; formally abandoned here (DM-01M3EW4PB6), not preserved.

2026-09-26 · python-pedro · WP02: built-in join allowlist 6 -> 4 content descriptors (_KNOWN_JOIN_SITES); deleted dead pins src/kernel/paths.py:88 (if is_windows(): in get_kittify_home) and src/specify_cli/runtime/home.py:79 (no join). Matching via new tests/architectural/_content_identity.py (single authority): Counter multiset, rel_path-keyed, because composite_key strips strings and neutrality/lint.py _default_scan_roots L379/L380 share a key (a set match would bless a future join at L380). parse_descriptor_line splits path/qualname from the left and the occurrence from the right (not split('::',3)) so tokens ending in ':' round-trip with an occurrence. Probe mutator climbs elif -> enclosing if and inserts above the first decorator. Known non-adopters for FR-019(d): _sole_door_scan.resolve_exclusion_keys, test_trio_seam_only.py, test_single_mission_surface_resolver.py, test_no_read_side_bypass.py, test_no_write_side_rederivation.py, untrusted_path_audit/audit.py check_undercount/check_overcount. Campsite #2972 (S5778/S5779/S8997) in test_built_in_location_authority.py: 0 before / 0 after.

2026-09-26 · python-pedro/WP11 · WP11 split: tests/runtime/test_next_board_authority.py holds 15 functions / 16 nodes (13 P0 #4980/#4975 + 2 fail-closed direct-call); node-ID set (func[param], guard tests excluded) equals the planning-base set from a real 3717c7ea checkout, diff empty (16=16). Oracle tests/runtime/test_bridge_parity.py keeps exactly 8 nodes, diff empty (8=8). Shared scaffolds moved to tests/runtime/_next_mission_scaffold.py (public names + __all__); golden-path aliases (_MissionTopology, _golden_create_mission, _golden_init_git_repo) imported directly in the board-authority module rather than re-exported, keeping P0 bodies verbatim.

2026-09-26 · python-pedro/WP11 · WP11 oracle untouched (C-002): git diff 3717c7ea -- tests/runtime/_bridge_oracle.py is empty; ledger_results + the 8 oracle test functions are byte-identical to base (ast.get_source_segment compare). Only import-only edits and mechanical helper call-site renames in scaffold_research/scaffold_documentation/_build_*; module not reformatted (WP13 owns format-exclude removal).

2026-09-26 · python-pedro/WP11 · WP11 residual coupling: advance_to_step (now tests/runtime/_next_mission_scaffold.py) still imports the private runtime.next._internal_runtime.engine._read_snapshot, moved verbatim; a src/ seam is out of scope (C-005). The stale bridge:NNNN comment anchors in tests/runtime/_bridge_oracle.py (:448, :465, :518) are deferred to the oracle-retirement follow-up #5116 (oracle untouched).

2026-09-26 · python-pedro/WP11 · WP11 NFR-004 duration (recorded, not asserted): pytest tests/runtime/test_next_board_authority.py --durations=0 -q -> 19 passed in 132.01s wall on a 4-CPU box shared with 3 concurrent implementers (first run 140.14s; includes ~28s one-time conftest test_venv setup). Above the <60s target measured by Debbie (48.49s) on an idle box; the module never sets up ledger_results (--setup-plan grep -c = 0), whose setup alone took 500.98s in the same contended window. Re-measure on an idle box.

2026-09-26 · claude · WP07 charter-exception evidence (DM-01M3F3T1G2RYW7P0ZVWQS41GEZ, plan D-OP-4), recorded before any edit on lane base fd9999c3: (1) base 'python tests/architectural/surface_resolution_audit/audit.py' -> 'AUDIT FAILED', exit=1, 8 MISSING rows (undercount tripwire; e.g. 'discovered callsite mission_runtime/resolution.py:1317 (_resolve_status_surface_dir) ... is MISSING from inventory.md (undercount tripwire)') + 8 ghost rows (e.g. 'inventory row mission_runtime/resolution.py:1068 (_resolve_status_surface_dir) ... has NO live discovered callsite (overcount/ghost tripwire)'). (2) 'rekey_inventory.py --check' -> 'inventory.md is STALE — re-run without --check to freshen.' exit=1 (the destructive #3011 instruction; NOT run without --check). (3) consumer grep over tests/.github/scripts/Makefile: no workflow/Makefile/script runs --check and no committed gate imports surface_resolution_audit/inventory.md (only prose hits in the survivor + unrelated inventories). (4) path-qualified token search (excl .venv/.mypy_cache/.pytest_cache/.ruff_cache; kitty-specs, docs/reports, docs/archive, .kittify/evidence, docs/plans/engineering-notes, .worktrees, .git, CHANGELOG, the dir itself) base count = 11 (test_no_worktree_name_guess.py:155, untrusted_path_audit/inventory.md:76, test_single_mission_surface_resolver.py:19,92,163,166,508, _ratchet_keys.py:49,124, pyproject.toml:954,955). docs/plans/engineering-notes excluded: dated doc_status closeout research notes (immutable historical snapshots, not live docs under SC-003); its one hit research-notes-csf-2670.md:29 names the long-deleted test_surface_resolution_audit.py gate as history. (5) survivor test_single_mission_surface_resolver.py: 8 passed on lane; base node-ID set pinned from a real 3717c7ea worktree (8 IDs).

2026-09-26 · claude · WP08 red-first (commit d61d05ba): floor tests land with scan targets unchanged. Verbatim RED: tests/next/test_internal_runtime_parity.py::test_rich_typer_ban_inspects_live_runtime_package -> 'AssertionError: rich/typer ban: missing target <wt>/src/specify_cli/next/_internal_runtime (0 files inspected)'; tests/contract/test_next_no_unknown_state.py::test_runtime_placeholder_scan_inspects_live_source -> 'AssertionError: placeholder scan: missing target <wt>/src/specify_cli/next (0 files inspected)'. 2 failed in 86.81s. Missing/empty/planted helper tests pass on tmp_path (no ImportError/NameError).

2026-09-26 · claude · WP08 T044/T045 retirements (#2620 format, NFR-006). Rich/typer ban converted: _RUNTIME_PACKAGE -> src/runtime/next/_internal_runtime (16 files, floor >=16), AST helper. Load-bearing probes (one-off): planting 'import os, typer' (function-local) into a tmp copy of the live package reds the ban at engine.py:1514; setting _FORBIDDEN_IMPORT_ROOTS=frozenset() reds test_rich_typer_ban_flags_planted_import (offenders == []). RETIREMENTS: (1) test_no_spec_kitty_runtime_imports_in_internal_package - verdict retire; discriminator duplicate ban (DIRECTIVE_044) + vacuous (scanned deleted src/specify_cli/next); survivor tests/architectural/test_shared_package_boundary.py::test_production_never_imports_retired_runtime_package PASSED. (2) test_public_surface_matches_contract and (3) test_submodule_surface_matches_contract - verdict retire; discriminator positive shape pin (__all__/hasattr); behaviour covered by test_internalized_runtime_matches_upstream_snapshot (4 nodes). Mutation: scratch full-tree copy, behaviour-preserving rename engine._read_snapshot -> _read_snapshot_renamed (def + 3 internal call sites): only test_submodule_surface_matches_contract FAILED; golden 4/4 PASSED, public-surface PASSED (1 failed, 5 passed). NOTE: probe must run from a scratch repo root because pytest.ini 'pythonpath = src' overrides PYTHONPATH.

2026-09-26 · claude · WP08 T046: test_next_no_unknown_state runtime scan retargeted to src/runtime/next (31 files, floor >=31), 0 placeholder hits (no src finding, C-005). Follow-up candidate (scope drift, NOT widened): TestNoLegacyQueryPlaceholderInTemplates::test_placeholder_is_absent_from_command_templates still scans src/specify_cli/missions (15 template .md on base) while canonical templates now live in packs/built-in/missions/.

2026-09-26 · claude · WP08 T047/T048 FR-016 removals. (a) test_surface_resolution_equivalence.py: removed _apply_xfail, always-None xfail_reason column, stale RED/GREEN cell table + strict-xfail docstring narrative, drained WP06/WP05 comment block, stale T002 xfail header (campsite); extracted _check_cell(repo_root, topology, slug, mid8, entry_points) used by test_entry_points_agree_per_cell and new test_equivalence_detects_planted_divergence (coord-fresh cell, MissionStatus.load leg rewired to PRIMARY -> AssertionError 'directory divergence'). collect-only diff: identical + 1 new (41->42, all pass). (b) test_execution_context_parity.py: removed xfail->WP map + ATDD xfail narrative + stale ATDD-first comment block; missing_seams arm retired (redundant within test). Probe on scratch copies of the two source files: arm removed + both exempt seams renamed -> kept ban RED at gate.py:218 and agent_retrospect.py:264; planted feature_dir-anchored read_events() -> RED at gate.py:663; pristine copy GREEN. (c) test_transition_gate_parity.py: test_wp09_hook_landmine_disposition_is_documented_accurately retired - self-referential docstring/marker test; docstring L28-29 already states no xfail marker, no invariant lost. (d) test_docs_cli_reference_parity.py: test_retired_check_residual_option_is_absent KEPT. Survivor proof: re-added visible --check-residual on review in a scratch tree; test_visible_paths_match_reference[0/1], test_deprecated_paths_classified, test_reference_paths_are_present_and_generated all PASSED, only the tombstone FAILED. Survivors compare command paths only (walker help_body = docstring, no options), so per the WP rule the tombstone stays; follow-up: option-level help/reference parity would let it retire.

2026-09-26 · claude · WP07 retirement result: path-qualified token search 11 (base) -> 0 (lane head 1122cfd1). T040 sibling-data grep: nothing outside surface_resolution_audit/ read write_candidate_classification.yaml or audited-surfaces.md (tests/scripts/docs/.github/src; the only 'audited-surfaces.md' hit, test_untrusted_path_containment.py:240, is the untrusted_path_audit sibling's own file). Survivor collect-only diff vs a real 3717c7ea worktree: empty (8 node IDs). Deviations: dropped _normalize_token (the |->¦ normalisation only served the retired markdown table; survivor compares raw composite_key_from_file keys, per T039 step 5's conditional); made _RESOLVER_CALLS/_TOPOLOGY_BLIND_CALLS/_SELECTION_READ_CALLS/_ALL_BLESSED_CALLS module-private (no outside reader; T042 step 5). Commits split move (343bea78: git mv + root depth + format + survivor import + pyproject L954) / strip (87d1d03d) / delete (6887a622 + L955) / prose (1122cfd1) so --follow stays clean and every commit keeps the survivor green. Follow-ups (not chased, scope): (a) survivor documents a _MIN_DISCOVERED_ROWS floor (docstring + comment block) but neither base 3717c7ea nor the lane defines the constant or asserts it; only test_discovered_rows_non_empty exists; (b) other test_resolution_authority_gates.py references in docs/ADR/src remain.

2026-09-26 · claude · WP05 green-side: retired-token search (T031 step 5 regex, live paths) = 0 hits; load_baseline() -> 36 entries; test_no_inert_schema_slots.py 9 passed under -W error::UserWarning (no shrink warning); per-walk floors MINIMUM_SCHEMA_SLOT_NAMES=150 / MINIMUM_MODEL_SLOT_NAMES=120 wired via test_live_scan_meets_per_walk_floors + self-mutation test_walk_floors_fail_on_a_collapsed_walk (real scanned_slots on planted tree fails both walks); every public function in _inert_slots.__all__ (find_inert_slots, is_schema_declared, load_baseline, ratchet, scanned_slots) imported by test_no_inert_schema_slots.py, BASELINE_SLOTS read by test_ratchet_baselines.py; _baselines.yaml baseline_entries 38->36, unassigned_entries/masking_suppressions deleted. Commits e86a715b (RED), 4668c259, 09d505f0, 81dcb7d5.

2026-09-26 · claude · WP06 T032 RED (commit cf792c9c, lane-f base includes WP05). Lane RED: pytest tests/architectural/test_ratchet_baselines.py::test_every_baseline_leaf_is_enforced_by_a_size_ratchet -> 1 failed: 'Unenforced leaves [test_example_round_trip.skip_marker_blocks, test_no_dead_modules.category_1_auto_discovered_migrations] ... Missing leaves []'. Planning-base proof (3717c7ea:_baselines.yaml through the same _leaf_drift): (['test_example_round_trip.skip_marker_blocks', 'test_no_dead_modules.category_1_auto_discovered_migrations', 'test_no_inert_schema_slots.masking_suppressions', 'test_no_inert_schema_slots.unassigned_entries'], []). WP05 already removed the two inert-slot leaves, so this lane's RED names the remaining two non-enforcing leaves (category_1, skip_marker_blocks).

2026-09-26 · planner-priti · FR-018 parity verdict catalog: research/parity-verdicts.md (45/45 modules of the #2631 sweep, #2620 format, churn window since 2026-03-26). Completeness: research/parity_catalog_check.py --base 3717c7ea → 45/45 OK. Rows owned by WP08–WP11 are re-confirmed at WP13.

2026-09-26 · claude · WP06 NFR-006 retirements and survivors. (1) category_1_auto_discovered_migrations leaf + _CATEGORY_1_* consts + _category_baseline + test_decorative_category_1_yaml_matches_frozenset + test_category_1_derived_baseline_absorbs_growth/shrink retired (commit 46faba29). Survivor: tests/architectural/test_no_dead_modules.py::test_no_new_dead_modules_under_src. Mutation proof: removing one importer-less migration (specify_cli.upgrade.migrations.m_0_10_0_python_only) from _ALLOWLIST and calling the survivor -> 'SURVIVOR RED for unlisted importer-less migration ... named in failure: True'. (2) skip_marker_blocks leaf + _SKIP_MARKER_*_PROP + _emit_skip_marker_delta + test_skip_marker_growth_is_recorded_not_failed/test_skip_marker_shrink_is_recorded/test_skip_marker_live_count_never_blocks retired (commit 4bcfc71e). Survivor: per-block _SKIP_MARKER_RE gate, node tests/contract/test_example_round_trip.py::test_contract_example_round_trip[<rel>::block-N-MISSING_FRONTMATTER]. Mutation: _collect_strict_blocks('x/contracts/y.md', ['# round-trip: skip:\na: 1\n'], out) -> [('x/contracts/y.md::block-1-MISSING_FRONTMATTER', '<MISSING_FRONTMATTER>', ...)] i.e. an empty-reason skip becomes a failing gate case. (3) _GRANDFATHERED_UNREGISTERED_KEYS + test_no_unregistered_baseline_keys_are_added + test_readding_inert_dead_symbols_key_is_now_rejected retired (commit 724cde4b; no references in tests/ docs/ .kittify/). Survivors: test_every_baseline_leaf_is_enforced_by_a_size_ratchet and test_leaf_drift_detects_planted_unenforced_leaf (re-added test_no_dead_symbols.x arm).

2026-09-26 · claude · WP06 green-side evidence. (a) Load-bearing derivation: monkeypatching _enforced_leaves to return the planted YAML's own leaf set makes _leaf_drift(planted) == ([], []) (planted leaves no longer caught); with the real derivation it returns (['test_layer_rules.planted_leaf', 'test_no_dead_symbols.x'], []). (b) Reviewer spot-mutation: swapping the leaf values of rows 6/7 (test_layer_rules mission_runtime/runtime) reds 18 of 19 lowering ids (the lowering test asserts no OTHER row fails). Honest limit: a swap between two rows whose live sizes both stay <= the other's YAML value (e.g. category_2 live 2/YAML 3 vs category_3 live 0/YAML 2) is invisible to any size comparison; this is inherent to size ratchets, not the table. (c) NFR-003 shrink-only script (3717c7ea vs head): '23 -> 19 leaves; increased: {}'. _baselines.yaml = 19 leaves in 12 sections. (d) Lowering assertion matches the row prefix 'section.leaf (attr)' rather than line indent because pytest assertion rewriting re-indents message lines and repeats them in the 'assert not [...]' repr. Residual (not owned here): tests/architectural/test_no_dead_symbols.py:130,2295 still says its categories are 'introspected by the ratchet-baseline meta-test' -- false since test_no_dead_symbols left _baselines.yaml; also test_no_dead_modules.py:~607 comment says per-category frozensets are 'inspected by the ratchet-baseline meta-test' -- still true for categories 2-7, no longer for category_1.

2026-09-26 · python-pedro · WP09 mutation matrix (T049, ATDD-exception evidence substitute; script research/wp09_mutation_matrix.py @ 8e66f446) — VERBATIM output at planning/lane base d79e2b9a (--workers 1):
# WP09 mutation matrix @ d79e2b9a4b1c (base-root /tmp/claude-0/-home-user-spec-kitty/02e01fd5-f2be-5a67-b92b-8465e3d3b889/scratchpad/wp09-base)
BASELINE: collected=333 failed=0 errored=0 rc=0

M1 | event sort is a no-op (shadow builtin `sorted` in spec_kitty_events.diary)
    target: spec_kitty_events.diary.reduce_parsed (site-packages)
    verdict: OK  (red=2 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestReducerDeterminism::test_event_order_does_not_affect_final_state
    RED     tests/status/test_reducer.py::TestReduceOutOfOrder::test_reduce_out_of_order_events
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestReducerDeterminism::test_event_order_does_not_affect_final_state
      [fail] tests/status/test_reducer.py::TestReduceOutOfOrder::test_reduce_out_of_order_events

M2 | add done -> planned edge (DoneState.allowed_targets) + recompute ALLOWED_TRANSITIONS
    target: wp_state.DoneState + transitions.ALLOWED_TRANSITIONS
    verdict: OK  (red=6 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestTransitionMatrixParity::test_terminal_lanes_have_no_outbound_transitions
    RED     tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count
    RED     tests/status/test_transitions.py::TestIllegalTransitions::test_illegal_transition_rejected[done-planned]
    RED     tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
    RED     tests/status/test_transitions.py::TestTerminalForceExitParity::test_terminal_exit_without_force_is_illegal[done]
    RED     tests/status/test_transitions.py::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestTransitionMatrixParity::test_terminal_lanes_have_no_outbound_transitions
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
      [fail] tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count
      [fail] tests/status/test_transitions.py::TestIllegalTransitions::test_illegal_transition_rejected[done-planned]
      [fail] tests/status/test_transitions.py::TestTerminalForceExitParity::test_terminal_exit_without_force_is_illegal[done]

M3 | add claimed -> claimed self-edge + recompute ALLOWED_TRANSITIONS
    target: wp_state.ClaimedState + transitions.ALLOWED_TRANSITIONS
    verdict: OK  (red=4 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestTransitionMatrixParity::test_no_self_transitions_in_matrix
    RED     tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count
    RED     tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
    RED     tests/status/test_transitions.py::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestTransitionMatrixParity::test_no_self_transitions_in_matrix
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
      [fail] tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count

M4 | add planned -> uninitialized (non-canonical target) + recompute ALLOWED_TRANSITIONS
    target: wp_state.PlannedState + transitions.ALLOWED_TRANSITIONS
    verdict: OK  (red=2 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestTransitionMatrixParity::test_transition_pairs_use_canonical_lanes
    RED     tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestTransitionMatrixParity::test_transition_pairs_use_canonical_lanes
      [fail] tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count

M4b | count-preserving swap: planned -> blocked replaced by planned -> uninitialized + recompute
    target: wp_state.PlannedState + transitions.ALLOWED_TRANSITIONS
    note:   records whether the golden baseline (not the count test) catches a count-preserving swap
    verdict: OK  (red=4 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestTransitionMatrixParity::test_transition_pairs_use_canonical_lanes
    RED     tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestTransitionMatrixParity::test_transition_pairs_use_canonical_lanes
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
      [fail] tests/status/test_transitions.py::TestLegalTransitions::test_legal_transition_accepted[planned-blocked-kwargs12]

M5 | rename CANONICAL_LANES entry "in_review" -> "under_review" (count-preserving)
    target: src/specify_cli/status_lanes.py
    note:   "reviewing" is avoided: test_validate.py::test_non_canonical_to_lane probes that literal, a coincidental (non-survivor) red
    verdict: OK  (red=3 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestTransitionMatrixParity::test_all_canonical_lanes_in_enum
    n/a     tests/status/test_transitions.py::TestConstants::test_all_canonical_lanes_in_enum
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestTransitionMatrixParity::test_all_canonical_lanes_in_enum
      [fail] tests/status/test_parity.py::TestTransitionMatrixParity::test_all_enum_values_in_canonical_lanes
      [fail] tests/status/test_parity.py::TestTransitionMatrixParity::test_transition_pairs_use_canonical_lanes

M6 | append display member Lane.SHADOW='shadow' (not in CANONICAL_LANES; zero-edge factory entry)
    target: src/specify_cli/status/models.py (+ wp_state._STATE_MAP so import succeeds)
    verdict: OK  (red=7 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestTransitionMatrixParity::test_all_enum_values_in_canonical_lanes
    RED     tests/status/test_models.py::TestLaneEnum::test_lane_member_names_exact
    all red node IDs (mutation-induced):
      [fail] tests/status/test_models.py::TestLaneEnum::test_lane_enum_string_values
      [fail] tests/status/test_models.py::TestLaneEnum::test_lane_member_names_exact
      [fail] tests/status/test_models.py::TestStatusSnapshot::test_summary_has_all_lane_keys
      [fail] tests/status/test_parity.py::TestReducerDeterminism::test_empty_events_produce_stable_snapshot
      [fail] tests/status/test_parity.py::TestTransitionMatrixParity::test_all_enum_values_in_canonical_lanes
      [fail] tests/status/test_reducer.py::TestReduceEmpty::test_reduce_empty_events
      [fail] tests/status/test_reducer.py::TestSummaryCounts::test_summary_counts_match_wp_states

M7 | materialize_to_json drops sort_keys=True
    target: src/specify_cli/status/reducer.py::materialize_to_json
    verdict: OK  (red=1 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestReducerDeterminism::test_sorted_keys_in_json_output
    n/a     tests/status/test_reducer.py::TestByteIdenticalOutput::test_sorted_keys_in_json_output
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestReducerDeterminism::test_sorted_keys_in_json_output

M8 | StatusSnapshot.from_dict drops last_event_id
    target: src/specify_cli/status/models.py::StatusSnapshot.from_dict
    verdict: OK  (red=2 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestReducerDeterminism::test_reduce_then_serialize_roundtrip
    RED     tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_json_roundtrip_stable
    n/a     tests/status/test_reducer.py::TestRealisticEventLog::test_realistic_log_json_roundtrip_stable
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_json_roundtrip_stable
      [fail] tests/status/test_parity.py::TestReducerDeterminism::test_reduce_then_serialize_roundtrip

M9 | materialize_to_json injects a per-call random key
    target: src/specify_cli/status/reducer.py::materialize_to_json
    verdict: OK  (red=7 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_identical_across_runs
    RED     tests/status/test_reducer.py::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_identical_across_runs
      [fail] tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_json_roundtrip_stable
      [fail] tests/status/test_parity.py::TestReducerDeterminism::test_json_serialization_byte_identical
      [fail] tests/status/test_reducer.py::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls
      [fail] tests/status/test_reducer.py::TestByteIdenticalOutput::test_byte_identical_output
      [fail] tests/status/test_reducer.py::TestMaterializeGitClean::test_materialize_leaves_clean_git_tree
      [fail] tests/status/test_reducer.py::TestMaterializeIdempotency::test_second_call_with_same_events_does_not_write

M10 | plant top-level `from specify_cli.sync import x` in status/emit.py (+ stub package so imports resolve)
    target: src/specify_cli/status/emit.py
    note:   the stub package also trips test_no_retired_paths_exist; the import scan is the named survivor
    verdict: OK  (red=5 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestBackportReadiness::test_emit_module_has_no_toplevel_sync_import
    RED     tests/status/test_parity.py::TestBackportReadiness::test_no_status_module_directly_imports_sync_at_toplevel
    RED     tests/status/test_parity.py::TestBackportReadiness::test_module_importable_without_sync[specify_cli.status.emit]
    RED     tests/architectural/test_no_retired_subsystems.py::test_no_retired_import_targets_exist
    all red node IDs (mutation-induced):
      [fail] tests/architectural/test_no_retired_subsystems.py::test_no_retired_import_targets_exist
      [fail] tests/architectural/test_no_retired_subsystems.py::test_no_retired_paths_exist
      [fail] tests/status/test_parity.py::TestBackportReadiness::test_emit_module_has_no_toplevel_sync_import
      [fail] tests/status/test_parity.py::TestBackportReadiness::test_module_importable_without_sync[specify_cli.status.emit]
      [fail] tests/status/test_parity.py::TestBackportReadiness::test_no_status_module_directly_imports_sync_at_toplevel

M11 | dedup keeps the LAST occurrence of a duplicated event_id
    target: specify_cli.status.reducer.reduce_parsed binding (wrapper)
    verdict: OK  (red=2 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestReducerDeterminism::test_duplicate_events_deduplicated_deterministically
    RED     tests/status/test_reducer.py::TestReduceDeduplication::test_reduce_deduplication
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestReducerDeterminism::test_duplicate_events_deduplicated_deterministically
      [fail] tests/status/test_reducer.py::TestReduceDeduplication::test_reduce_deduplication

M12 | force_count is never accumulated (zeroed after the fold)
    target: specify_cli.status.reducer.reduce_parsed binding (wrapper)
    verdict: OK  (red=2 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestReducerDeterminism::test_force_events_tracked_in_force_count
    RED     tests/status/test_reducer.py::TestReduceForceCount::test_reduce_force_count_tracked
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestReducerDeterminism::test_force_events_tracked_in_force_count
      [fail] tests/status/test_reducer.py::TestReduceForceCount::test_reduce_force_count_tracked

M13 | invert rollback classification (spec_kitty_events.diary._is_rollback_event)
    target: spec_kitty_events.diary rollback precedence (site-packages)
    note:   precedence REMOVAL (_should_apply_event -> True) is invisible to the parity test (its rollback also sorts last); see M13b
    verdict: OK  (red=3 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestReducerDeterminism::test_concurrent_events_rollback_precedence
    RED     tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestReducerDeterminism::test_concurrent_events_rollback_precedence
      [fail] tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval
      [fail] tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_legacy_for_review_to_in_progress_rollback_still_beats_concurrent_forward_event

M13b | remove rollback precedence entirely (_should_apply_event always applies)
    target: spec_kitty_events.diary._should_apply_event (site-packages)
    note:   expected: survivor RED, parity test GREEN (parity is strictly weaker than the survivor)
    verdict: OK  (red=2 of collected=333, rc=1)
    expected:
    RED     tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval
      [fail] tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_legacy_for_review_to_in_progress_rollback_still_beats_concurrent_forward_event

M14 | reduce() is per-call nondeterministic (random slot in every WP state)
    target: specify_cli.status.reducer.reduce_parsed binding (wrapper)
    verdict: OK  (red=4 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestReducerDeterminism::test_same_events_produce_identical_snapshots
    RED     tests/status/test_reducer.py::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_identical_across_runs
      [fail] tests/status/test_parity.py::TestReducerDeterminism::test_event_order_does_not_affect_final_state
      [fail] tests/status/test_parity.py::TestReducerDeterminism::test_same_events_produce_identical_snapshots
      [fail] tests/status/test_reducer.py::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls

M15 | summary under-counts canceled WPs
    target: specify_cli.status.reducer.reduce_parsed binding (wrapper)
    verdict: OK  (red=1 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_produces_expected_summary
    n/a     tests/status/test_reducer.py::TestRealisticEventLog::test_realistic_log_produces_expected_summary
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_produces_expected_summary

M16 | re-create module specify_cli.status.phase
    target: src/specify_cli/status/phase.py (new file)
    note:   scaffold proof: the tombstone can only fail if a module of that name is re-created; it pins no behaviour
    verdict: OK  (red=1 of collected=333, rc=1)
    expected:
    RED     tests/status/test_parity.py::TestPhaseCap::test_phase_module_deleted
    all red node IDs (mutation-induced):
      [fail] tests/status/test_parity.py::TestPhaseCap::test_phase_module_deleted

EXIT=0

2026-09-26 · python-pedro · WP09 mutation matrix — VERBATIM output at lane head 6329c3db (test_parity.py deleted; relocated tests exercised in their new homes):
# WP09 mutation matrix @ 6329c3dbb290 (base-root /home/user/spec-kitty/.worktrees/ratchet-baseline-census-gate-remediation-01M3EW3Z-lane-i)
BASELINE: collected=308 failed=0 errored=0 rc=0

M1 | event sort is a no-op (shadow builtin `sorted` in spec_kitty_events.diary)
    target: spec_kitty_events.diary.reduce_parsed (site-packages)
    verdict: OK  (red=1 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestReducerDeterminism::test_event_order_does_not_affect_final_state
    RED     tests/status/test_reducer.py::TestReduceOutOfOrder::test_reduce_out_of_order_events
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestReduceOutOfOrder::test_reduce_out_of_order_events

M2 | add done -> planned edge (DoneState.allowed_targets) + recompute ALLOWED_TRANSITIONS
    target: wp_state.DoneState + transitions.ALLOWED_TRANSITIONS
    verdict: OK  (red=5 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestTransitionMatrixParity::test_terminal_lanes_have_no_outbound_transitions
    RED     tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count
    RED     tests/status/test_transitions.py::TestIllegalTransitions::test_illegal_transition_rejected[done-planned]
    RED     tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
    RED     tests/status/test_transitions.py::TestTerminalForceExitParity::test_terminal_exit_without_force_is_illegal[done]
    RED     tests/status/test_transitions.py::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row
    all red node IDs (mutation-induced):
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
      [fail] tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count
      [fail] tests/status/test_transitions.py::TestIllegalTransitions::test_illegal_transition_rejected[done-planned]
      [fail] tests/status/test_transitions.py::TestTerminalForceExitParity::test_terminal_exit_without_force_is_illegal[done]

M3 | add claimed -> claimed self-edge + recompute ALLOWED_TRANSITIONS
    target: wp_state.ClaimedState + transitions.ALLOWED_TRANSITIONS
    verdict: OK  (red=3 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestTransitionMatrixParity::test_no_self_transitions_in_matrix
    RED     tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count
    RED     tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
    RED     tests/status/test_transitions.py::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row
    all red node IDs (mutation-induced):
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
      [fail] tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count

M4 | add planned -> uninitialized (non-canonical target) + recompute ALLOWED_TRANSITIONS
    target: wp_state.PlannedState + transitions.ALLOWED_TRANSITIONS
    verdict: OK  (red=1 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestTransitionMatrixParity::test_transition_pairs_use_canonical_lanes
    RED     tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count
    all red node IDs (mutation-induced):
      [fail] tests/status/test_transitions.py::TestConstants::test_allowed_transitions_count

M4b | count-preserving swap: planned -> blocked replaced by planned -> uninitialized + recompute
    target: wp_state.PlannedState + transitions.ALLOWED_TRANSITIONS
    note:   records whether the golden baseline (not the count test) catches a count-preserving swap
    verdict: OK  (red=3 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestTransitionMatrixParity::test_transition_pairs_use_canonical_lanes
    RED     tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
    all red node IDs (mutation-induced):
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_collapsed_matrix_catches_planted_row
      [fail] tests/status/test_transitions.py::TestBehaviorPreservationParity::test_validate_transition_matches_baseline
      [fail] tests/status/test_transitions.py::TestLegalTransitions::test_legal_transition_accepted[planned-blocked-kwargs12]

M5 | rename CANONICAL_LANES entry "in_review" -> "under_review" (count-preserving)
    target: src/specify_cli/status_lanes.py
    note:   "reviewing" is avoided: test_validate.py::test_non_canonical_to_lane probes that literal, a coincidental (non-survivor) red
    verdict: OK  (red=1 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestTransitionMatrixParity::test_all_canonical_lanes_in_enum
    RED     tests/status/test_transitions.py::TestConstants::test_all_canonical_lanes_in_enum
    all red node IDs (mutation-induced):
      [fail] tests/status/test_transitions.py::TestConstants::test_all_canonical_lanes_in_enum

M6 | append display member Lane.SHADOW='shadow' (not in CANONICAL_LANES; zero-edge factory entry)
    target: src/specify_cli/status/models.py (+ wp_state._STATE_MAP so import succeeds)
    verdict: OK  (red=5 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestTransitionMatrixParity::test_all_enum_values_in_canonical_lanes
    RED     tests/status/test_models.py::TestLaneEnum::test_lane_member_names_exact
    all red node IDs (mutation-induced):
      [fail] tests/status/test_models.py::TestLaneEnum::test_lane_enum_string_values
      [fail] tests/status/test_models.py::TestLaneEnum::test_lane_member_names_exact
      [fail] tests/status/test_models.py::TestStatusSnapshot::test_summary_has_all_lane_keys
      [fail] tests/status/test_reducer.py::TestReduceEmpty::test_reduce_empty_events
      [fail] tests/status/test_reducer.py::TestSummaryCounts::test_summary_counts_match_wp_states

M7 | materialize_to_json drops sort_keys=True
    target: src/specify_cli/status/reducer.py::materialize_to_json
    verdict: OK  (red=1 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestReducerDeterminism::test_sorted_keys_in_json_output
    RED     tests/status/test_reducer.py::TestByteIdenticalOutput::test_sorted_keys_in_json_output
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestByteIdenticalOutput::test_sorted_keys_in_json_output

M8 | StatusSnapshot.from_dict drops last_event_id
    target: src/specify_cli/status/models.py::StatusSnapshot.from_dict
    verdict: OK  (red=1 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestReducerDeterminism::test_reduce_then_serialize_roundtrip
    n/a     tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_json_roundtrip_stable
    RED     tests/status/test_reducer.py::TestRealisticEventLog::test_realistic_log_json_roundtrip_stable
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestRealisticEventLog::test_realistic_log_json_roundtrip_stable

M9 | materialize_to_json injects a per-call random key
    target: src/specify_cli/status/reducer.py::materialize_to_json
    verdict: OK  (red=5 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_identical_across_runs
    RED     tests/status/test_reducer.py::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls
      [fail] tests/status/test_reducer.py::TestByteIdenticalOutput::test_byte_identical_output
      [fail] tests/status/test_reducer.py::TestMaterializeGitClean::test_materialize_leaves_clean_git_tree
      [fail] tests/status/test_reducer.py::TestMaterializeIdempotency::test_second_call_with_same_events_does_not_write
      [fail] tests/status/test_reducer.py::TestRealisticEventLog::test_realistic_log_json_roundtrip_stable

M10 | plant top-level `from specify_cli.sync import x` in status/emit.py (+ stub package so imports resolve)
    target: src/specify_cli/status/emit.py
    note:   the stub package also trips test_no_retired_paths_exist; the import scan is the named survivor
    verdict: OK  (red=2 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestBackportReadiness::test_emit_module_has_no_toplevel_sync_import
    n/a     tests/status/test_parity.py::TestBackportReadiness::test_no_status_module_directly_imports_sync_at_toplevel
    n/a     tests/status/test_parity.py::TestBackportReadiness::test_module_importable_without_sync[specify_cli.status.emit]
    RED     tests/architectural/test_no_retired_subsystems.py::test_no_retired_import_targets_exist
    all red node IDs (mutation-induced):
      [fail] tests/architectural/test_no_retired_subsystems.py::test_no_retired_import_targets_exist
      [fail] tests/architectural/test_no_retired_subsystems.py::test_no_retired_paths_exist

M11 | dedup keeps the LAST occurrence of a duplicated event_id
    target: specify_cli.status.reducer.reduce_parsed binding (wrapper)
    verdict: OK  (red=1 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestReducerDeterminism::test_duplicate_events_deduplicated_deterministically
    RED     tests/status/test_reducer.py::TestReduceDeduplication::test_reduce_deduplication
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestReduceDeduplication::test_reduce_deduplication

M12 | force_count is never accumulated (zeroed after the fold)
    target: specify_cli.status.reducer.reduce_parsed binding (wrapper)
    verdict: OK  (red=1 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestReducerDeterminism::test_force_events_tracked_in_force_count
    RED     tests/status/test_reducer.py::TestReduceForceCount::test_reduce_force_count_tracked
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestReduceForceCount::test_reduce_force_count_tracked

M13 | invert rollback classification (spec_kitty_events.diary._is_rollback_event)
    target: spec_kitty_events.diary rollback precedence (site-packages)
    note:   precedence REMOVAL (_should_apply_event -> True) is invisible to the parity test (its rollback also sorts last); see M13b
    verdict: OK  (red=2 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestReducerDeterminism::test_concurrent_events_rollback_precedence
    RED     tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval
      [fail] tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_legacy_for_review_to_in_progress_rollback_still_beats_concurrent_forward_event

M13b | remove rollback precedence entirely (_should_apply_event always applies)
    target: spec_kitty_events.diary._should_apply_event (site-packages)
    note:   expected: survivor RED, parity test GREEN (parity is strictly weaker than the survivor)
    verdict: OK  (red=2 of collected=308, rc=1)
    expected:
    RED     tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval
      [fail] tests/status/test_reducer.py::TestReduceConcurrentRollbackPrecedence::test_legacy_for_review_to_in_progress_rollback_still_beats_concurrent_forward_event

M14 | reduce() is per-call nondeterministic (random slot in every WP state)
    target: specify_cli.status.reducer.reduce_parsed binding (wrapper)
    verdict: OK  (red=1 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestReducerDeterminism::test_same_events_produce_identical_snapshots
    RED     tests/status/test_reducer.py::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestByteIdenticalOutput::test_byte_identical_across_reduce_calls

M15 | summary under-counts canceled WPs
    target: specify_cli.status.reducer.reduce_parsed binding (wrapper)
    verdict: OK  (red=1 of collected=308, rc=1)
    expected:
    n/a     tests/status/test_parity.py::TestFullEventLogParity::test_realistic_log_produces_expected_summary
    RED     tests/status/test_reducer.py::TestRealisticEventLog::test_realistic_log_produces_expected_summary
    all red node IDs (mutation-induced):
      [fail] tests/status/test_reducer.py::TestRealisticEventLog::test_realistic_log_produces_expected_summary

M16 | re-create module specify_cli.status.phase
    target: src/specify_cli/status/phase.py (new file)
    note:   scaffold proof: the tombstone can only fail if a module of that name is re-created; it pins no behaviour
    verdict: NO-EXPECTED-NODE-PRESENT  (red=0 of collected=308, rc=0)
    expected:
    n/a     tests/status/test_parity.py::TestPhaseCap::test_phase_module_deleted
    all red node IDs (mutation-induced):

EXIT=0

2026-09-26 · python-pedro · WP09 dispositions — RETIRED (duplicate), 13 of 21 functions; each mutation reds parity test AND survivor at base (see matrix):
- test_same_events_produce_identical_snapshots -> TestByteIdenticalOutput::test_byte_identical_across_reduce_calls (M14)
- test_event_order_does_not_affect_final_state -> TestReduceOutOfOrder::test_reduce_out_of_order_events (M1, spec_kitty_events.diary sort)
- test_duplicate_events_deduplicated_deterministically -> TestReduceDeduplication::test_reduce_deduplication (M11)
- test_json_serialization_byte_identical -> TestByteIdenticalOutput::test_byte_identical_output (M9)
- test_reduce_then_serialize_roundtrip -> relocated TestRealisticEventLog::test_realistic_log_json_roundtrip_stable (M8; strict superset: richer log + full byte equality after from_dict; red at head)
- test_empty_events_produce_stable_snapshot -> TestReduceEmpty::test_reduce_empty_events (M6)
- test_force_events_tracked_in_force_count -> TestReduceForceCount::test_reduce_force_count_tracked (M12)
- test_concurrent_events_rollback_precedence -> TestReduceConcurrentRollbackPrecedence::test_in_review_to_in_progress_rollback_beats_concurrent_approval (M13 reds both; M13b shows precedence REMOVAL reds only the survivor: parity test is strictly weaker, its rollback also sorts last)
- test_realistic_log_identical_across_runs -> test_byte_identical_across_reduce_calls (M9)
- test_transition_pairs_use_canonical_lanes -> test_transitions.py TestConstants::test_allowed_transitions_count (M4); count-preserving swap M4b is caught by TestBehaviorPreservationParity::test_validate_transition_matches_baseline (+ test_collapsed_matrix_catches_planted_row, test_legal_transition_accepted[planned-blocked-kwargs12])
- test_no_self_transitions_in_matrix -> test_allowed_transitions_count, test_validate_transition_matches_baseline, test_collapsed_matrix_catches_planted_row (M3, ALLOWED_TRANSITIONS recomputed)
- test_terminal_lanes_have_no_outbound_transitions -> test_allowed_transitions_count, test_illegal_transition_rejected[done-planned], test_validate_transition_matches_baseline, test_terminal_exit_without_force_is_illegal[done], test_collapsed_matrix_catches_planted_row (M2, recomputed)
- test_all_enum_values_in_canonical_lanes -> test_models.py TestLaneEnum::test_lane_member_names_exact (M6; also test_lane_enum_string_values)

2026-09-26 · python-pedro · WP09 dispositions — RETIRED (scaffold), 4 functions / 12 nodes:
- TestBackportReadiness::test_module_importable_without_sync (9 parametrized nodes), ::test_emit_module_has_no_toplevel_sync_import, ::test_no_status_module_directly_imports_sync_at_toplevel: 0.1x cross-branch backport scaffold; src/specify_cli/sync no longer exists and tests/architectural/test_no_retired_subsystems.py is the canonical guard (_RETIRED_PATHS includes src/specify_cli/sync; test_no_retired_import_targets_exist has a planted self-test). M10 (planted top-level import + stub package) reds the architectural survivor test_no_retired_import_targets_exist (and test_no_retired_paths_exist).
- TestPhaseCap::test_phase_module_deleted: tombstone for the deleted specify_cli.status.phase (#3285 class); M16 shows it can only fail if a module of that name is re-created — it pins no behaviour. status/phase.py NOT added to _RETIRED_PATHS (out of scope).

2026-09-26 · python-pedro · WP09 dispositions — RELOCATED, 4 functions (+ fixture builder), each has no survivor at base and its mutation reds the relocated node at lane head:
- test_sorted_keys_in_json_output -> tests/status/test_reducer.py::TestByteIdenticalOutput::test_sorted_keys_in_json_output (M7)
- TestFullEventLogParity._build_realistic_event_log + test_realistic_log_produces_expected_summary -> test_reducer.py::TestRealisticEventLog (M15)
- test_realistic_log_json_roundtrip_stable -> test_reducer.py::TestRealisticEventLog (M8)
- test_all_canonical_lanes_in_enum -> tests/status/test_transitions.py::TestConstants::test_all_canonical_lanes_in_enum (M5, count-preserving rename in_review->under_review; the literal 'reviewing' was avoided because test_validate.py::test_non_canonical_to_lane probes it — a coincidental, non-survivor red)
Accepted consequence: test_reducer.py carries module marks [integration, git_repo], so the 3 relocated reducer tests leave make test-fast (test_parity.py was pytest.mark.fast); a class-level fast mark would not help because the module integration mark still deselects them. test_transitions.py is fast-marked, so the lane test stays in the fast tier.
Counts: tests/status collected 1254 at base (1246 passed + 8 skipped) -> 1229 at head (29 parity nodes removed, 4 relocated added). #4506 had not landed: the pyproject format-exclude line for test_parity.py was present and removed in the deletion commit 6329c3db.

2026-09-26 · python-pedro · WP04 equivalence (lane head b0dc84fa; artefacts 31ed6091): '.venv/bin/python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/census_rekey_equivalence.py --base 3717c7ea --head-root <lane-d>' -> destructive 22 / mutation 56 / overwrite 2 keys; op_ordinal>0: 3; 'EQUIVALENCE OK: 80/80 sites, bijection, rationale hashes equal (base 3717c7ea)'. '--self-test' -> flip one op_ordinal DETECTED, drop one key DETECTED, swap one rationale DETECTED; SELF-TEST OK. git diff 3717c7ea -- src/ is empty (C-005; the script also byte-compares every censused source). D-OP-8 ruling kept: census stale policy stays WARN (content keys make warn-on-stale safe: a dead key cannot re-bind). Accepted weakness: composite_key strips strings, so 7 of the 22 destructive keys have punctuation-only argv token lines ('[ , , ] ,' x5, '[ , , , ] ,' x2) and an argument swap inside the same op is blessed silently; deleting an earlier same-key op shifts ordinals so a rationale can re-attach to its twin (both were exempted anyway). Changed-argument test expressed in all three gates (NAME element/argument inserted on the op's own line), no per-gate exemption needed. Campsite #2972 (S5778/S5779/S8997) in the four owned files: 0 before / 0 after (no pytest.raises or monkeypatch in them).
