# IC-02 — Closed-issue markers: re-point, retire, re-cite (WP02)

Materialized at closeout from WP02's reported evidence (scratchpad `WP02-evidence.yaml` /
`wp02_note.txt`, identical content) and the reviewer's full approval note
(`status.events.jsonl`, `review_ref: auto-approval:WP02:20260930`). Mission:
test-suite-remediation-01M3SSDW, lane-b.

## MG-04 (T006) — RE-POINT #3113 -> #5493

```yaml
id: EV-IC02-01
item: MG-04
kind: RE-POINT
planted_break:
  target: "tests/architectural/test_egress_consent_boundary.py::TestGuardBites.test_positional_transport_strict_xfail_landmines_disposition_still_pending"
  description: "reverted the xfail reason string for case (A) from '#5493 case (A) ...' back to '#3113 case (A) ...' (scratch, not committed)"
  reverted: true
command: 'uv run --frozen pytest "tests/architectural/test_egress_consent_boundary.py::TestGuardBites::test_scanner_detects_each_sink_shape" --runxfail -rxX -n0 -q'
results:
  old_form_under_break: "n/a — old form (citing #3113) is the pre-edit baseline itself, not a break against the new form"
  new_form_under_break: "RED — 1 failed: AssertionError: assert '#5493' in \"#3113 case (A) (accepted residual of #3113, closed COMPLETED 2026-08-02): all-positional injected transport ...\""
  clean_tree: "GREEN — 1 passed; full file: 43 passed, 2 xfailed"
counts:
  executed_before: null
  executed_after: null
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP02:20260930): "'#3113' planted back in case
  (A) reason => landmine guard RED, revert GREEN" — exactly this record's planted break,
  reproduced independently and reverted clean. Issue filed: #5493 (open, confirmed via
  `gh issue view 5493` by both the implementer and the reviewer). Both xfail reasons
  re-pointed from closed #3113 to open #5493, `strict=True` kept, provenance text kept.
  Landmine guard literal updated from "#3113" to "#5493". `baseline_runxfail_result`: 2
  FAILED both before and after the edit (reason unchanged: "scanner went blind to
  transport-call"), reconfirmed by the reviewer's own `--runxfail` run (2 FAILED, same
  message). `TestCompletenessLimitsDocstring::test_limit_8_positional_transport_call_is_documented`
  still passes (pins heading text, not the issue number). `new_issue` field required by
  data-model §2 (RE-POINT) is satisfied: #5493 open at mission close (NFR-004).
```

## MG-06 (T007 RETIRE + T008 FIX) — `_has_events_5` dead guards + new coverage test

```yaml
id: EV-IC02-02
item: MG-06
kind: RETIRE
planted_break:
  target: "pyproject.toml::[project.dependencies]"
  description: "spec-kitty-events floor changed from '>=10.4.0,<11' to '>=4.0' (scratch, not committed)"
  reverted: true
command: 'uv run --frozen pytest "tests/architectural/test_pyproject_shape.py::test_shared_dependencies_use_public_pypi_ranges" -n0 -q -rxX'
covering_guard:
  node_id: "tests/architectural/test_pyproject_shape.py::test_shared_dependencies_use_public_pypi_ranges"
  under_break: fail   # AssertionError: differing items {'spec-kitty-events': 'spec-kitty-events>=4.0'} != {'spec-kitty-events': 'spec-kitty-events>=10.4.0,<11'}
results:
  old_form_under_break: "n/a — _has_events_5() and its 6 guard sites are deleted; the dead guards were already unreachable (0/61 fired) prior to deletion, exactly why they were RETIRE candidates"
  new_form_under_break: fail
  clean_tree: "GREEN — the three migration files re-run together: 62 passed, 0 skipped (baseline before this WP: 61 passed, 0 skipped; +1 is the new T008 test)"
counts:
  executed_before: 61
  executed_after: 62
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "pyproject events floor '>=4.0' => test_shared_dependencies_use_public_pypi_ranges
  RED (:118), test_events_dependency_floor_rejects_pre_v10_contract stays green as WP
  predicted" — the same covering-guard plant recorded here, re-run independently with the
  pyproject.toml sha256 restored byte-exact afterward. Deleted: 3 definitions of
  _has_events_5() and its 6 guard sites (skipif x5, if-guard x1) across
  tests/migration/test_teamspace_migration_rehearsal.py, test_mission_state_repair.py,
  tests/integration/migration/test_mission_state_repair_fidelity_e2e.py.
```

## MG-06 part 2 (T008) — new coverage test for the previously-unreachable refusal branch

```yaml
id: EV-IC02-03
item: MG-06 (T008 new test)
kind: FIX
planted_break:
  target: "src/specify_cli/migration/mission_state.py::_load_events_contract"
  description: "replaced 'if package_version < REQUIRED_EVENTS_PACKAGE:' with 'if False:' at lines 1183-1184 (scratch, never committed)"
  reverted: true
command: 'uv run --frozen pytest "tests/migration/test_mission_state_repair.py::test_teamspace_dry_run_refuses_events_package_below_required_floor" -n0 -q -rxX'
results:
  old_form_under_break: >
    n/a — the OLD form of coverage was the unreachable `if not _has_events_5(): pytest.raises(...); return`
    branch inside test_repair_canonicalizes_historical_meta_and_status_events (old :161-164),
    which could never execute on this repo (floor is >=10.4.0, so _has_events_5() is always
    True) — the exact masked-green defect this subtask retires.
  new_form_under_break: "FAIL — Failed: DID NOT RAISE <class 'specify_cli.migration.mission_state.MissionStateDryRunError'>"
  clean_tree: "PASS — 1 passed"
counts:
  executed_before: null
  executed_after: null
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "mission_state.py 'if package_version < REQUIRED_EVENTS_PACKAGE:'
  -> 'if False:' => new test RED 'DID NOT RAISE', revert GREEN 1 passed" — exactly this
  record's planted break, reproduced independently and reverted clean (git diff --stat empty,
  confirmed by the reviewer). No sanctioned FR-005 product fix was needed — the product
  refusal at mission_state.py:1183-1184 was already correct; only the TEST coverage of that
  branch was missing. git diff --stat src/ stayed empty for this WP's real commit; the plant
  above was reverted, never landed.
```

## MG-07 (T009) — RETIRE `clean_install_acceptance_deferred()` + helper module

```yaml
id: EV-IC02-04
item: MG-07
kind: RETIRE
planted_break:
  target: "pyproject.toml::[tool.uv.sources]"
  description: >
    appended a new [tool.uv.sources] table with
    spec-kitty-events = { git = "https://github.com/spec-kitty/spec-kitty-events", rev = "deadbeef" }
    (scratch, not committed; no pre-existing [tool.uv.sources] table existed to collide with)
  reverted: true
command: >
  uv run --frozen pytest
  "tests/architectural/test_pyproject_shape.py::test_published_metadata_uses_consumable_shared_dependencies"
  "tests/architectural/test_pyproject_shape.py::test_shared_dependencies_use_public_pypi_ranges"
  -n0 -q -rxX
covering_guard:
  node_id: "tests/architectural/test_pyproject_shape.py (both named tests above)"
  under_break: fail   # 2 failed, both: AssertionError: ["committed local source for spec-kitty-events: {...}"] == []
results:
  old_form_under_break: >
    n/a — clean_install_acceptance_deferred() is deleted; its predicate was always False
    under the live lock (both packages sourced from PyPI), so it never disarmed anything,
    exactly why it was a RETIRE candidate.
  new_form_under_break: fail
  clean_tree: "GREEN — test_clean_venv_install_imports_and_resolves_built_in: 1 passed; test_clean_install_next_runs_without_runtime: 1 passed"
counts:
  executed_before: null
  executed_after: null
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "[tool.uv.sources] git deadbeef => both pyproject-shape
  guards RED 'committed local source'" — exactly this record's planted break and covering
  guard, reproduced independently. Named-file re-run after revert (per the reviewer):
  "test_packaging_parity.py 3 passed; test_clean_install_next node 1 passed". Deleted:
  tests/_support/shared_package_deferral.py, and 2 skipifs in
  tests/doctrine/test_packaging_parity.py / tests/integration/test_clean_install_next.py.
  `rg -n "_has_events_5|clean_install_acceptance_deferred|shared_package_deferral" tests`
  returns nothing (covers T007 and T009 together). Ambiguity note: the cited "#828" is
  EXPERIMENTAL#828 ("de-factory dependency pins -> PyPI ranges", CLOSED 2026-09-01), NOT
  spec-kitty/spec-kitty#828 (an unrelated docs issue) — same ambiguity class as #171.
  Recorded, not resolved by editing the label (helper and skipifs deleted outright).
```

## MG-08 (T010, row 8) — NO-OP: "828" is a line number, not an issue

```yaml
id: EV-IC02-05
item: MG-08
kind: NO-OP
command: 'grep -n "828" tests/architectural/test_charter_sole_door_agent_profile_repository.py'
results:
  finding: >
    Line 80: "81->95, and Gate 2's four _doctrine_collect.py sites 193/283/420/828 ->"
    — "828" is a LINE NUMBER in src/specify_cli/.../_doctrine_collect.py, not an issue
    reference. rg over the file for skip/xfail/quarantine/importorskip markers returns
    nothing — the file carries no skip/xfail marker at all.
  action_taken: "None. File not edited, per instruction."
reviewer_rerun: false
notes: "This is masked-greens.md row 8's documented false positive (research.md 'Masked-green dispositions' row 8: NO-OP)."
```

## MG-09 (T010, sync gate) — KEEP + re-cite

```yaml
id: EV-IC02-06
item: MG-09
kind: KEEP
planted_break:
  target: "tests/unit/test_zz_scratch_sync_flag.py (new scratch file, never committed)"
  description: 'import os; os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0" at module scope'
  reverted: true
command: 'uv run --frozen pytest "tests/architectural/test_saas_sync_gate_selection_invariance.py::test_no_test_module_sets_the_flag_at_import_time" -n0 -q -rxX'
results:
  old_form_under_break: "n/a — KEEP disposition; single live guard re-validated, no old/new form distinction"
  new_form_under_break: "RED — 1 failed: AssertionError: These test modules set SPEC_KITTY_ENABLE_SAAS_SYNC at import time ... - unit/test_zz_scratch_sync_flag.py"
  clean_tree: "GREEN — 1 passed; full file: 3 passed"
counts:
  executed_before: 3
  executed_after: 3
reviewer_rerun: false
notes: >
  keep_reason (data-model §3): module docstring only, premise rewritten from stale #3213
  import-time-skipif-selection-dependence framing (zero such gates remain) to the live
  premise: process-global SPEC_KITTY_ENABLE_SAAS_SYNC opt-out kill-switch pollution
  (post-#3980). #3213 and #3980 kept as history. No test logic changed.
```

## Summary counters (as reported)

- Issue filed: #5493 (OPEN).
- Existing issue-matrix rows confirmed not-applicable: #3113, #3213, #828, #932.
- `git diff --stat src/` — empty at every commit (no product code changes landed).
- `ruff check` on the 7 owned .py files still present -> All checks passed!
- `ruff format --check` on the 4 non-excluded files -> 4 files already formatted.
