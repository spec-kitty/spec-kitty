# IC-07 — FR-007 class: architectural and live-source call-site counts (WP08)

Materialized at closeout from WP08's reported evidence (scratchpad `wp08-evidence.md`), the
reviewer's cycle-1 rejection (`tasks/WP08-.../review-cycle-1.md`, a full write-up — one
blocking issue, F9's docstring still carried the retired counts), and the reviewer's cycle-2
approval note (`status.events.jsonl`, `review_ref: auto-approval:WP08:20260930`), which
states "Cycle-1 plant results stand" and re-lists the same F11/F12a/F3/F8 re-runs quoted
below, plus its own re-run of the fixed F9 docstring and F11 naming (no re-plant of F9's own
scratch-mixture break is described, so `EV-IC07-F9`'s `reviewer_rerun` stays `false`). The
fix for F9 landed in commit `4e2a88a996`.

## F9 — RETIRE: `test_recorded_denominator_matches_docstring_claim`

```yaml
id: EV-IC07-F9
item: F9
kind: RETIRE
planted_break:
  target: "tests/status/test_scratch_plant_f9.py (new scratch file, never committed)"
  description: 'new StatusEvent(at="literal") + StatusEvent(at=datetime.now(UTC)...) mixture in a scanned test file'
  reverted: true
command: "uv run --frozen pytest tests/architectural/test_no_absolute_event_timestamp_mixture.py::test_derived_mixture_matches_recorded_baseline -n0 -q"
results:
  old_form_under_break: "pass (not executed after deletion, but confirmed by inspection: the retired test reads only the two module constants len(_MIXTURE_FILES)==2 / len(_MIXTURE_FUNCTION_PAIRS)==14, blind to tree growth)"
covering_guard:
  node_id: "tests/architectural/test_no_absolute_event_timestamp_mixture.py::test_derived_mixture_matches_recorded_baseline"
  under_break: fail   # AssertionError: new absolute-event-timestamp mixture(s) not yet recorded: [('tests/status/test_scratch_plant_f9.py', 'test_scratch_new_mixture_plant')]
results_clean_tree: "GREEN — 9 passed"
reviewer_rerun: false
notes: >
  Cycle-1 BLOCKING finding (fixed before approval): the retired test's "implicit property"
  (docstring prose vs. the constants) was left uncovered — 3 numeric references ("14",
  "14th") survived in the module docstring after commit 4e2a88a996 stripped only the two
  bullet lines, contradicting the evidence record's own "docstring numbers replaced ... no
  counts" claim. Fixed with a ~3-line reword to count-free prose; reviewer required
  `grep -nE '\b(14|14th|2 files)\b'` to return no docstring hits and the file to re-run at
  9 passed before approving. The reviewer's cycle-1 "Re-verified" section re-ran the
  named-file suite (87 passed) and the quality gates after this fix, but does not record an
  independent re-run of F9's own planted break (the scratch-mixture test); reviewer_rerun
  is left false here per content fidelity — see evidence/README.md for which records the
  reviewer did explicitly rerun (F11, F12a, F3, F8).
```

## F11 — CONVERT (FIX): per-site partition

```yaml
id: EV-IC07-F11
item: F11
kind: FIX
planted_break:
  target: "src/specify_cli/charter_runtime/freshness/computer.py (multiple construction sites) + tests/architectural/test_remediation_effectiveness.py::_EXEMPT_STATES"
  description: >
    4 plants: (1) split-site exploit, _compute_charter_source:525 remediation=None (one of
    two 'missing' sites neutered, the other left emitting); (2) single-site exploit,
    _synthesized_drg_missing_graph_state:723 remediation=None; (3) swap exploit, test-file
    scratch _EXEMPT_STATES member swapped; (4) neutral growth proof, a new dead-branch
    FreshnessSubState(state="fresh", remediation=None) construction site added.
  reverted: true
command: "uv run --frozen pytest tests/architectural/test_remediation_effectiveness.py::test_every_construction_site_is_partitioned -n0 -q"
results:
  plant_1_split_site: "RED — construction site not covered by the partition: line 522 in _compute_charter_source (state='missing') ..."
  plant_2_single_site: "RED — construction site not covered: line 720 in _synthesized_drg_missing_graph_state (state='missing') ..."
  plant_3_swap: "RED on both test_every_construction_site_is_partitioned (line 539, state='invalid') AND test_exemption_set_size_is_pinned (identity check mismatch)"
  plant_4_neutral_growth: "GREEN — 0 test edits under growth (the one collateral red, test_case_table_matches_ast_derived_states, is pre-existing lineno-shift fragility of the unrelated _CASES table, not a defect in the partition invariant)"
  clean_tree: "pass — 19 passed after each revert"
counts: {executed_before: null, executed_after: null}
reviewer_rerun: true
notes: >
  New test: test_every_construction_site_is_partitioned (partition + disjointness), walker
  _discover_freshness_substate_sites. Three == floor pins + one == 9 sum replaced by a
  per-site partition has_remediation or state in _PASS_STATES or (function, state) in
  _EXEMPT_STATES. Reviewer re-run (cycle-1 "Re-verified"): independently reproduced the
  split-site plant (RED at line 522), the fail-closed plant (RED, "no readable state=
  string literal"), the disjointness plant (RED), and the swap plant (RED at line 625) —
  "the partition alone carries it." Tallied as one of the SC-005 FIX re-runs in
  evidence/README.md.
```

## F12a — RETIRE: `EXPECTED_ENCLOSING_COUNT`

```yaml
id: EV-IC07-F12a
item: F12a
kind: RETIRE
planted_break:
  target: "src/specify_cli/cli/commands/tracker.py::_check_sync_readiness"
  description: "tracker_egress_verdict(...) call replaced with a stub SimpleNamespace(refused=False), removing the function from the live enclosing set without deleting it"
  reverted: true
command: "uv run --frozen pytest tests/architectural/test_tracker_egress_guards_3108.py::test_g4_exactly_five_enclosing_functions_and_five_call_expressions -n0 -q"
covering_guard:
  node_id: "tests/architectural/test_tracker_egress_guards_3108.py::test_g4_exactly_five_enclosing_functions_and_five_call_expressions"
  under_break: fail   # symmetric difference: ['_check_sync_readiness']; call expressions: 4 (expected 5)
results:
  clean_tree: "GREEN — 13 passed"
counts: {executed_before: null, executed_after: null}
reviewer_rerun: true
notes: >
  Redundant with the set-equality real.enclosing == EXPECTED_ENCLOSING_FUNCTIONS at
  (renumbered) :1150; both message-text uses replaced with len(EXPECTED_ENCLOSING_FUNCTIONS).
  Reviewer re-run (cycle-1 "Re-verified"): "F12a (stub _check_sync_readiness's
  tracker_egress_verdict( call): set-equality RED, symmetric difference
  ['_check_sync_readiness']." Tallied as the first of two SC-005 RETIRE re-runs in
  evidence/README.md (F8 is the second).
```

## F12b — KEEP (contract): `EXPECTED_CALL_EXPRESSION_COUNT`

```yaml
id: EV-IC07-F12b
item: F12b
kind: KEEP
command: null
results: {}
reviewer_rerun: true
notes: >
  Unchanged value and assertion. keep_reason: audited egress census (#3108/#3030) — each
  extra call expression is a new, reviewed egress point; the count moves only with a real
  audited egress-site change. Comment strengthened in place to record the KEEP reason. No
  plant required (KEEP, not converted); non-vacuity already exercised by the existing G4
  mutation-kill tests (unchanged). Reviewer re-run (cycle-1 "Re-verified"): "F12b:
  EXPECTED_CALL_EXPRESSION_COUNT = 5 unchanged, KEEP reason recorded in the comment —
  justified as an audited egress census."
```

## F3 — CONVERT (FIX): `materialize_calls` floor `>= 1`

```yaml
id: EV-IC07-F3
item: F3
kind: FIX
planted_break:
  target: "src/runtime/next/runtime_bridge.py"
  description: >
    3 plants: neutral (a new dead function with an extra _materialize_decision(...) call);
    violation (a new dead function with a bare Decision(kind=..., agent=..., ...) construction);
    vacuity (sed-renamed every _materialize_decision( call across all 29 call sites to
    _materialize_decision_renamed_scratch(, def name left unchanged).
  reverted: true
command: >
  uv run --frozen pytest
  tests/runtime/test_bridge_decision_builder.py::test_runtime_bridge_materializes_every_former_decision_site
  tests/runtime/test_bridge_decision_builder.py::test_runtime_bridge_has_zero_raw_decision_constructions -n0 -q
results:
  neutral_plant: "GREEN — both tests stayed GREEN (0 test edits); the old == 29 form would have reded (count moved to 30)"
  violation_plant: "RED — test_runtime_bridge_has_zero_raw_decision_constructions: assert [<ast.Call ...>] == []"
  vacuity_plant: "RED — test_runtime_bridge_materializes_every_former_decision_site: assert 0 >= 1, where 0 = len([])"
  clean_tree: "pass — 27 passed each time after revert"
counts: {executed_before: null, executed_after: null}
reviewer_rerun: true
notes: >
  assert len(materialize_calls) == 29 -> assert len(materialize_calls) >= 1; the real
  invariant is the unchanged AST absence scan test_runtime_bridge_has_zero_raw_decision_constructions
  at :442. Per-site changelog docstring (~40 lines of 7 re-pins) replaced with a 6-line
  pointer. runtime_bridge_cores.py:510 len(bare_decision_calls) == 3 left untouched per WP
  instruction (not in the recurring class). Reviewer re-run (cycle-1 "Re-verified"): "F3
  vacuity (alias all 29 _materialize_decision( call sites): floor RED." Tallied as one of
  the SC-005 FIX re-runs in evidence/README.md.
```

## F6 — CONVERT (FIX): drop `expected_sites`; per-row floor `>= 1`

```yaml
id: EV-IC07-F6
item: F6
kind: FIX
planted_break:
  target: "src/specify_cli/cli/commands/agent/mission_finalize.py + tasks_finalize.py"
  description: >
    3 plants: neutral (a new dead function with an extra
    _bootstrap_canonical_state_via_mission(..., capability=GuardCapability.STANDARD) call);
    violation (same, capability=GuardCapability.MERGE_BOOKKEEPING); vacuity
    (tasks_finalize.py:452 the sole call site renamed to an undefined attribute).
  reverted: true
command: 'uv run --frozen pytest "tests/git/test_guard_capability_regression.py::test_status_bookkeeping_call_sites_are_refused_on_protected_destination[...]" -n0 -q'
results:
  neutral_plant: "GREEN — parametrize case stayed GREEN (0 test edits); the old == 3 pin would have reded (count moved to 4)"
  violation_plant: "RED — AssertionError: ... asserts <GuardCapability.MERGE_BOOKKEEPING> ... which evaluate() ALLOWS on a protected ref"
  vacuity_plant: "RED — AssertionError: no bootstrap_canonical_state call site found in cli/commands/agent/tasks_finalize.py — the parity test would pass vacuously"
  clean_tree: "pass — 14 passed each time after revert"
counts: {executed_before: null, executed_after: null}
reviewer_rerun: false
notes: >
  parametrize signature (module_rel, callee, expected_sites) -> (module_rel, callee);
  len(capabilities) == expected_sites -> assert capabilities (non-vacuity). REFUSED-loop
  unchanged.
```

## F8 — RETIRE: `test_member_count`

```yaml
id: EV-IC07-F8
item: F8
kind: RETIRE
planted_break:
  target: "src/specify_cli/cli/commands/review/_diagnostics.py::MissionReviewDiagnostic"
  description: "added member WP08_T038_SCRATCH_UNDOCUMENTED with no ERROR_CODES.md section"
  reverted: true
command: "uv run --frozen pytest tests/specify_cli/cli/commands/review/test_diagnostic_codes_documented.py -n0 -q"
covering_guard:
  node_id: "test_all_diagnostic_members_documented + test_section_count_matches_member_count"
  under_break: fail   # both RED: "have no ## section in ERROR_CODES.md" / "16 code sections but 17 members"
results:
  neutral_plant: "GREEN — added a matching WP08_T038_SCRATCH_DOCUMENTED member + ERROR_CODES.md section: all 5 tests GREEN (the old test_member_count == 16 would have reded here, 17 members now)"
  clean_tree: "GREEN — 5 passed"
counts: {executed_before: null, executed_after: null}
reviewer_rerun: true
notes: >
  test_member_count (== 16) deleted; contract is test_all_diagnostic_members_documented (:31)
  + test_section_count_matches_member_count (:48, relational). Reviewer re-run (cycle-1
  "Re-verified"): "F8 violation (undocumented enum member): :31 and :48 both RED." Tallied as
  the second of two SC-005 RETIRE re-runs in evidence/README.md.
```

## Pin-inventory disposition summary (as reported)

| Row | disposition | invariant_form | neutral_plant | violation_plant | keep_reason |
|---|---|---|---|---|---|
| F9 | RETIRE | `test_derived_mixture_matches_recorded_baseline` set equality | n/a (retire) | new mixture in scanned tests/ tree | — |
| F11 | FIX (partition) | per-site `has_remediation or state in _PASS_STATES or (fn,state) in _EXEMPT_STATES` | new pass-state site | split-site / single-site / swap exploit | — |
| F12a | RETIRE | set-equality `real.enclosing == EXPECTED_ENCLOSING_FUNCTIONS` (`:1150`) | n/a (retire) | drop one enclosing function's call site | — |
| F12b | KEEP | unchanged `== EXPECTED_CALL_EXPRESSION_COUNT` | n/a | n/a | audited egress census (#3108/#3030); moves only with reviewed egress-site change |
| F3 | FIX (floor) | `>= 1`, real invariant is `:442` AST absence scan | new `_materialize_decision` site | bare `Decision(...)` construction | — |
| F6 | FIX (floor) | `assert capabilities` (per-row non-vacuity) + unchanged REFUSED loop | new STANDARD call site | new protected-capability call site | — |
| F8 | RETIRE | `test_all_diagnostic_members_documented` + `test_section_count_matches_member_count` | new documented member | new undocumented member | — |

## Reviewer re-run disclosure (non-blocking items noted, no action required for approval)

- F11 naming drift (`*_is_pinned` names vs. new floor comments) — optional rename, not actioned.
- F11 walker scope (visits only top-level `ast.FunctionDef` / bare-`Name` calls) — pre-existing, not a regression; noted as a tracer-entry candidate.
- F3/F6 accepted residual (`>= 1` floors no longer detect one-of-N call sites becoming invisible, only total vanishing) — WP-prescribed disposition.
