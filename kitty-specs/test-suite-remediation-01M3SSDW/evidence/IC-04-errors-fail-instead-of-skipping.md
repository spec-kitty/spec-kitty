# IC-04 — Errors fail instead of skipping (WP04)

Materialized at closeout from WP04's reported evidence (scratchpad `wp04_evidence.md`) and
the reviewer's full approval note (`status.events.jsonl`, `review_ref: auto-approval:WP04:20260930`).

## MG-10/11 — CONVERT: `tests/conftest.py::build_artifacts` / `installed_wheel_venv`

```yaml
id: EV-IC04-01
item: MG-10/MG-11
kind: FIX
planted_break:
  target: "pyproject.toml::[tool.hatch.build.targets.wheel].packages"
  description: 'appended "src/specify_cli/__init__.py" (already covered by the src/specify_cli package entry) — makes hatchling try to add specify_cli/__init__.py to the wheel archive twice'
  reverted: true   # git checkout -- pyproject.toml
command: 'uv run --frozen pytest "tests/doctrine/test_wheel_packaging.py::test_wheel_contains_doctrine_package_data" -n0 -q -rs'
results:
  old_form_under_break: "SKIPPED — Build failed: ValueError: A second file is being added to the wheel archive at the same path ... (1 skipped in 36.04s)"
  new_form_under_break: "ERROR, naming the build stderr — 1 error in 35.10s (wheel/sdist build failed, same ValueError)"
  clean_tree: "PASS — 1 passed in 4.31s"
reviewer_rerun: false
notes: >
  default_wheel_sdist_builder now runs `python -m build --no-isolation --wheel --sdist`,
  confirmed standalone. `tests/architectural/test_home_owner_behaviour.py` -> 14 passed
  (conftest.py definition names unchanged).
```

## MG-12 — DELETE: `tests/doctrine/test_wheel_packaging.py::_build_wheel_fallback`

```yaml
id: EV-IC04-02
item: MG-12
kind: RETIRE
planted_break: {target: null, description: "dead code, no caller; nothing to break", reverted: true}
command: 'git grep -n "_build_wheel_fallback" tests'
results:
  before_delete: "1 hit (the definition itself, tests/doctrine/test_wheel_packaging.py:33)"
  after_delete: "0 hits"
covering_guard:
  node_id: "MG-10/11's build_artifacts conversion (quickstart Break #10)"
  under_break: fail
reviewer_rerun: false
notes: "ruff check tests/doctrine/test_wheel_packaging.py -> All checks passed!"
```

## MG-13 — CONVERT: `tests/cross_cutting/versioning/test_version_detection.py` (11 skip sites)

```yaml
id: EV-IC04-03
item: MG-13
kind: FIX
planted_break:
  target: "tests/cross_cutting/versioning/test_version_detection.py::get_venv_metadata_version (10 call sites)"
  description: "scratch pytest plugin monkeypatches get_installed_version to always return None"
  reverted: true
command: "PYTHONPATH=<scratch> uv run --frozen pytest -p wp04_t017_plant tests/cross_cutting/versioning/test_version_detection.py -n0 -q -rs"
results:
  old_form_under_break: "7 SKIPPED + 2 FAILED (18 collected) -> 2 failed, 9 passed, 7 skipped in 36.74s"
  new_form_under_break: "9 FAILED, 9 passed, 0 skipped -> 9 failed, 9 passed in 3.45s"
  clean_tree: "18 passed, 0 skipped -> 18 passed in 56.07s"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP04:20260930): "get_installed_version->None
  scratch plugin: old 2 failed 9 passed 7 skipped, new 9 failed 9 passed; revert 18 passed,
  diff empty" — exactly this record's planted break, reproduced independently and reverted
  clean. Additional product break per subtask guidance: hardcoded __version__ = "0.4.13" in
  src/specify_cli/__init__.py. RED: AssertionError: Module __version__ (0.4.13) should
  match package metadata (4.0.0rc5) (1 failed). Reverted; re-run 1 passed; git diff --stat
  src/ empty.
```

## MG-14 — CONVERT (RK-3 option b): `tests/stress/test_concurrent_emits.py` stress/timing split

```yaml
id: EV-IC04-04
item: MG-14
kind: FIX
planted_break: {target: null, description: "no red run performed (RK-3 forbids it without an operator exception); proof is --collect-only only", reverted: true}
command: "uv run --frozen pytest tests/stress/test_concurrent_emits.py --collect-only -q -m timing"
results:
  timing_collect: "1/2 tests collected (1 deselected): test_concurrent_emits_meet_sc12_budget"
  stress_collect: "2 tests collected (both)"
  guard_files: "uv run --frozen pytest tests/architectural/test_timing_coverage_invariant.py tests/architectural/test_performance_marker_guard.py -n0 -q -> 99 passed"
reviewer_rerun: false
notes: >
  The old `if duration > 60.0: pytest.skip(...)` budget block (old :257-262) is DELETED; a
  new test_concurrent_emits_meet_sc12_budget (@pytest.mark.timing, @pytest.mark.timeout(120))
  asserts the SC-12 budget via tests._perf_helpers.assert_timing_budget. All functional
  assertions stay textually inside test_concurrent_emits_produce_valid_event_log. The stress
  mark (inherited from module pytestmark) puts the timing test in the nightly stress job.
```

## MG-15 — CONVERT: `test_real_home_isolation_guard.py::test_no_real_home_mutation_under_xdist`

```yaml
id: EV-IC04-05
item: MG-15
kind: FIX
planted_break:
  target: "tests/conftest.py::_apply_home_env + _isolated_worker_home"
  description: >
    scratch-neutered BOTH HOME-redirect loops (the _HOME_ENV_VARS loop in _apply_home_env,
    originally :134, and the loop in the autouse _isolated_worker_home fixture, originally
    :420) with `for var in []:` — neutering only one loop leaves the probe worker on the
    still-isolated home (a vacuous plant).
  reverted: true
command: 'uv run --frozen pytest "tests/architectural/test_real_home_isolation_guard.py::test_no_real_home_mutation_under_xdist" -n0 -q -rs'
results:
  old_form_under_break: "SKIPPED — 'Per-worker HOME isolation (WP04) is not active on this branch ...' (1 skipped in 34.99s)"
  new_form_under_break: "FAILED, naming the regression — 'at least one xdist worker resolved Path.home() to the real home (PosixPath(\"/home/stijn\"))' (1 failed in 34.15s)"
  clean_tree: "8 passed, 0 skipped (4.00s)"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "home isolation, BOTH _apply_home_env loop (:135) AND
  autouse _isolated_worker_home loop (:421) neutered: old guard 7 passed 1 SKIPPED
  (_SKIP_PRE_WP04), new guard 1 FAILED naming worker homes ['/home/stijn']; revert 8 passed,
  git diff --stat empty" — exactly this record's planted break (both loops), reproduced
  independently and reverted clean. `uv run --frozen pytest
  tests/architectural/test_home_owner_behaviour.py -n0 -q -> 14 passed`.
```

## MG-17 — CONVERT: `test_events_shapes.py::TestRetroEventNames.test_matches_upstream_registry_when_available`

```yaml
id: EV-IC04-06
item: MG-17
kind: FIX
planted_break:
  target: "scratch pytest plugin: sys.modules['spec_kitty_events.retrospective'] = None before collection"
  description: "simulates the upstream package being unimportable"
  reverted: true
command: 'PYTHONPATH=<scratch> uv run --frozen pytest -p wp04_t020_plant_events "tests/retrospective/test_events_shapes.py::TestRetroEventNames::test_matches_upstream_registry_when_available" -n0 -q -rs'
results:
  old_form_under_break: "SKIPPED — 'spec_kitty_events is not importable' (1 skipped in 34.95s)"
  new_form_under_break: "1 collection ERROR — ModuleNotFoundError: import of spec_kitty_events.retrospective halted; None in sys.modules (module-level import now fails the whole file's collection)"
  clean_tree: "pass (covered by the combined 75 passed / 1 skipped run below)"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "sys.modules jsonschema/spec_kitty_events.retrospective=None:
  old SKIP (wps_manifest:393, events_shapes:311), new collection ERROR naming the halted
  import; revert clean" — this reviewer plant covers both MG-17 (this record) and MG-18
  (`EV-IC04-07`) together, since both rely on the same `sys.modules[...] = None` mechanism.
  Campsite addition beyond masked-greens row 17: the version guard at old :318-319 was ALSO
  converted to an assert; declared floor spec-kitty-events>=10.4.0 already ships
  RETROSPECTIVE_EVENT_NAMES (verified directly: hasattr(r, 'RETROSPECTIVE_EVENT_NAMES') -> True).
```

## MG-18 — CONVERT: `jsonschema` `importorskip` sites (2 files, 3 call sites)

```yaml
id: EV-IC04-07
item: MG-18
kind: FIX
planted_break:
  target: "scratch pytest plugin: sys.modules['jsonschema'] = None before collection"
  description: "simulates jsonschema being unimportable, across 2 files / 3 call sites"
  reverted: true
command: >
  PYTHONPATH=<scratch> uv run --frozen pytest -p wp04_t020_plant_jsonschema
  "tests/upgrade/test_unified_bundle_migration.py::test_report_matches_schema"
  "tests/upgrade/test_unified_bundle_migration.py::test_report_matches_schema_for_no_charter"
  "tests/specify_cli/core/test_wps_manifest.py::TestCheckConcernRefsCoverage::test_wps_schema_accepts_plan_concern_fields"
  -n0 -q -rs
results:
  old_form_under_break: "3 SKIPPED — 'could not import jsonschema: import of jsonschema halted; None in sys.modules' (3 skipped in 32.57s)"
  new_form_under_break: "2 collection ERRORs — ModuleNotFoundError in both files (module-level import jsonschema)"
  clean_tree: "pass (covered by the combined 75 passed / 1 skipped run below)"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): the same "sys.modules jsonschema/spec_kitty_events.retrospective=None"
  plant quoted under `EV-IC04-06` covers this record's jsonschema half too ("old SKIP
  (wps_manifest:393, events_shapes:311), new collection ERROR naming the halted import;
  revert clean"). Named-file re-run (9 files): 214 passed, 1 skipped (performance chokepoint,
  exempt).
```

## Combined post-revert run (T020's masked-greens baseline, updated)

`uv run --frozen pytest tests/retrospective/test_events_shapes.py tests/upgrade/test_unified_bundle_migration.py tests/specify_cli/core/test_wps_manifest.py -n0 -q -rs` -> `75 passed, 1 skipped in 36.92s` — the one skip (`tests/upgrade/test_unified_bundle_migration.py:441`) is the performance chokepoint, on the exemption list, with a corrected nightly-harness citation.

## Skip-hygiene sweep (NFR-004) over all 9 owned files

`rg -n 'pytest\.(skip|xfail)|mark\.(skip|skipif|xfail|quarantine)|importorskip' <9 owned files>` -> only `tests/conftest.py:315` (`skip_windows`, platform guard, exemption list) and `tests/conftest.py:330` (`skip_performance`, env-gated chokepoint, exemption list), plus 2 non-executable prose mentions. Every surviving skip is on the exemption list and carries a reason.

## Exemption / scope check

`git diff kitty/mission-test-suite-remediation-01M3SSDW --stat -- tests/` touches exactly the 9 owned files; no platform/tool-guard exemption-list file touched except `tests/conftest.py` (its chokepoint *behaviour* is unchanged — only a stale #3595 citation was corrected). `git diff --stat src/` is empty at every commit.
