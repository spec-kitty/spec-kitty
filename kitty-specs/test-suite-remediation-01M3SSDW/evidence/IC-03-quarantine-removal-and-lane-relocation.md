# IC-03 — Quarantine removal and lane relocation (WP03)

Materialized at closeout from WP03's reported evidence (scratchpad `wp03-evidence.md`) and
the reviewer's full approval note (`status.events.jsonl`, `review_ref: auto-approval:WP03:20260930`).

## Baseline (old path, before this WP)

- `SPEC_KITTY_RUN_QUARANTINE=1 uv run --frozen pytest tests/cross_cutting/misc/test_acceptance_support.py -n0 -q -rs` -> `23 passed in 69.86s`
- `uv run --frozen pytest tests/cross_cutting/misc/test_acceptance_support.py -n0 -q -rs` -> `18 passed, 5 skipped in 16.76s` (5 SKIPPED: "quarantine: environmental flake under tracking ... Set SPEC_KITTY_RUN_QUARANTINE=1 to run it.")

## MG-05 — T011 relocation + T012 de-quarantine + result.stdout fix (disposition DE-QUARANTINE + RELOCATE)

```yaml
id: EV-IC03-01
item: MG-05
kind: FIX
planted_break:
  target: "src/specify_cli/cli/commands/accept.py::_exit_early_for_report_modes"
  description: >
    removed the `if diagnose: _report_diagnosis(run, summary); raise typer.Exit(0)`
    early-exit block (lines 974-976). Traced the CLI control flow before planting: this
    function is called and always raises before _perform_and_finalize (the sole consumer
    of commit_required), so breaking commit_required directly would be a dead plant for
    these tests.
  reverted: true   # git checkout -- src/specify_cli/cli/commands/accept.py; git diff --stat src/ empty
command: >
  uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py
  -k "test_accept_diagnose_json_reports_skipped_checks_without_mutation or test_accept_diagnose_does_not_mutate_matrix_metadata_or_events"
  -n0 -q
results:
  old_form_under_break: >
    N/A as a literal "run" (the pre-WP file at the old path no longer exists after the
    T011 rename); documented mechanism: SPEC_KITTY_RUN_QUARANTINE unset => quarantine
    mark skips => zero exercise of the guard, so the regression would have been silently
    hidden.
  new_form_under_break: "FAIL — 2 failed, 21 deselected (assert 1 == 0 on result.exit_code, both named tests)"
  clean_tree: "PASS — 2 passed, 21 deselected"
  full_file_under_break: "5 failed, 18 passed — all 5 former-quarantine test_accept_diagnose_* tests went RED under the plant (honesty per baseline-red gotcha: recording the true scope, not just the 2 named)"
counts:
  executed_before: 18   # old path, quarantine present: 18 executed, 5 skipped
  executed_after: 23    # new path, quarantine removed: 23 executed, 0 skipped
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP03:20260930): "Planted break 1
  accept.py::_exit_early_for_report_modes 'if diagnose:'->'if False:' => 5 failed/18 passed
  (all 5 de-quarantined red)" — exactly this record's planted break and full-file blast
  radius, reproduced independently. The reviewer additionally ran a second plant not in the
  WP's own report: "break 2 accept.py:948 mutate_matrix=not diagnose->True => 2 failed/21
  passed" (both reverted). Re-runs: `-n 2 --dist loadfile` 23 passed; 4 arch gates 35 passed;
  test_issue_4891 2 passed; ruff clean.
  T011 relocation: `git mv tests/cross_cutting/misc/test_acceptance_support.py
  tests/specify_cli/acceptance/test_acceptance_support.py` (commit 0858f2a723, pure rename,
  0/0 diff). ruff.toml F401 per-file key removed (shrink, not relocated — the only unused
  import, `os`, was independently removable after T012's stdout fix). Docstring cross-reference
  in test_issue_4891_accept_missing_lanes.py updated to the new path.
  `git grep -n "cross_cutting/misc/test_acceptance_support" -- ':!kitty-specs' ':!docs/adr'
  ':!docs/reports' ':!.kittify/evidence'` -> 0 hits. T012: removed
  `_ACCEPT_COMMAND_XDIST_QUARANTINE = pytest.mark.quarantine(reason="spec-kitty#171: ...")`
  and its 5 decorator uses; replaced 8 `json.loads(result.output)` with `json.loads(result.stdout)`
  (left `.output` unchanged for 8 exit-code diagnostics + 1 "Traceback not in" assertion, by
  design). Commits: 0858f2a723 (rename), 81f43ecca9 (de-quarantine + stdout fix, 3 files
  changed, 9 insertions, 17 deletions).
```

## T013 — Lane proof (RK-2)

```yaml
id: EV-IC03-02
item: T013 lane-registry proof
kind: KEEP
command: >
  uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py
  -m "not stress and not timing" --collect-only -q | grep -c accept_diagnose
results:
  collected_count: 5
  nodes:
    - tests/specify_cli/acceptance/test_acceptance_support.py::test_accept_diagnose_json_reports_missing_events_bootstrap_issue
    - tests/specify_cli/acceptance/test_acceptance_support.py::test_accept_diagnose_json_reports_skipped_checks_without_mutation
    - tests/specify_cli/acceptance/test_acceptance_support.py::test_accept_diagnose_json_blocks_corrupt_lanes_json
    - tests/specify_cli/acceptance/test_acceptance_support.py::test_accept_diagnose_does_not_mutate_matrix_metadata_or_events
    - tests/specify_cli/acceptance/test_acceptance_support.py::test_accept_diagnose_does_not_execute_custom_negative_invariants
  registry_check: "claimed: False / out_of_matrix: True — matches expected output exactly"
reviewer_rerun: false
notes: >
  `tests/specify_cli/acceptance` is a "rootless / Deferred-promotion" dir in
  out_of_matrix_test_dirs (spec-kitty#4374 / #4732). The nightly `specify-cli-out-of-matrix`
  job builds its ignore list from `modules[].test_dirs`, not from `out_of_matrix_test_dirs`,
  so this dir IS collected by that job under `-m "not stress and not timing" -n auto --dist loadfile`
  — the exact condition under which the tests originally failed. Gate-file run:
  `uv run --frozen pytest tests/architectural/test_quarantine_marker.py
  tests/architectural/test_out_of_matrix_evidence.py tests/architectural/test_module_shard_registry.py
  tests/architectural/test_ruff_pytest_style_baseline.py -n0 -q` -> 35 passed (after
  `uv sync --frozen --all-extras`; first attempt hit a stale-venv false red, CLAUDE.md-documented).
```

## T014 — xdist parallel proof

```yaml
id: EV-IC03-03
item: T014 parallel stability
kind: KEEP
command: "uv run --frozen pytest tests/specify_cli/acceptance/test_acceptance_support.py -n 2 --dist loadfile -q"
results:
  run_1: "23 passed in 21.84s"
  run_2: "23 passed in 21.63s"
reviewer_rerun: false
```

## Skip hygiene / quality gates / final counts

- NFR-004: `rg -n "pytest\.(skip|xfail)|mark\.(skip|skipif|xfail|quarantine)|importorskip" tests/specify_cli/acceptance/test_acceptance_support.py` -> no matches.
- `ruff check` on the touched files -> All checks passed!
- `ruff format --check` -> 2 files already formatted.
- `uv run --frozen pytest tests/specify_cli/cli/commands/test_issue_4891_accept_missing_lanes.py -n0 -q` -> 2 passed.
- `make test-fast` -> `2169 passed, 5 skipped, 4 warnings in 268.39s (0:04:28)`, exit 0 (5 skips pre-existing/unrelated).
- FR-002 note: the `EXPERIMENTAL#171` citation is fully removed from the file; #171 was closed 2026-08-26.

## Out of scope (RK-5) — confirmed untouched

`scripts/ci/quality_gate_decision.py`, arch-test docstrings, `pytest.ini` marker text, the 3
open-issue quarantines (EXP#1021 x2, EXP#901), `tests/conftest.py:320-338` (WP04's file),
`docs/adr/3.x/2026-08-28-1-...md:177` (immutable, C-006).
