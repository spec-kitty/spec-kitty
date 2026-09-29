# WP04 review feedback, cycle 2 (reviewer-renata)

**Verdict: changes requested, for one blocking item.** Every cycle-1 item is fixed (see "Verified"). But the fix for cycle-1 Issue 2 over-corrects: it now classifies real legacy code missions as "no code".

## Blocking

**Issue 1: body-inferred code WPs are dropped from "has code", which regresses the acceptance gate and the birth cutover for legacy lanes and coord missions.**

- **Where.** `consolidation/executor.py::_run_has_code_wps` and `acceptance/gates_core.py::_wp_kinds_for_manifest` now keep only entries with `mode_source == "frontmatter"`.
- **Why that loses information.** `workspace/context.py:621` stamps `mode_source = "inferred_legacy"` for every WP without an explicit `execution_mode`. It does so both when `infer_execution_mode` found real code signals (`src/`, `tests/`, source extensions) and when it merely fell through to the bare `CODE_CHANGE` default. The filter therefore discards genuine, body-evidenced code WPs along with the bare defaults.
- **Reproduction (fixture).** A lanes-topology mission with one code lane `lane-a` holding WP01. WP01's frontmatter has no `execution_mode`; its body says "Implement `src/parser.py` and add `tests/test_parser.py`".

  | Check | Result |
  |---|---|
  | `build_normalized_wp_index` | `code_change` / `inferred_legacy` |
  | base (lane-based `not is_planning_artifact_only`) | has code = **True** |
  | HEAD `has_code_wps(m, _wp_kinds_for_manifest(...))` | **False** |
  | HEAD `_run_has_code_wps(run)` | **False** |

- **Consequences for such a mission.**
  - `_evaluate_branch_gate` drops `mission_branch` from the allowed branches, skips the acceptance matrix as "planning_artifact-only missions do not produce acceptance-matrix.json", and returns the `planning_artifact_only` skip reason.
  - `_run_birth_cutover` is skipped at consolidate.

  This repository has no such missions (all 2451 code-lane WP files carry an explicit `execution_mode`), but consumer repos with pre-field legacy missions do.

**Required fix.** The "has code" answer must never be weaker than the base's lane-based answer. Either approach works:

- **(a) Lane floor.** `mission_has_code = has_code_lanes(manifest) or has_code_wps(manifest, kinds)`. A real code lane always means code. The kind-based check only *adds* the single_branch repo-root case. Then an untyped bare-default WP in a planning-only manifest stays "no code", which keeps your cycle-2 regression fix.
- **(b) Distinguish body-signal inference from the bare default.** For example, use `score_execution_mode_signals(...)[1] > 0` to count an `inferred_legacy` entry as code. Keep excluding bare defaults.

Apply the same rule in both `executor._run_has_code_wps` and `gates_core._wp_kinds_for_manifest`, ideally through one shared helper, and add tests:

- a lanes mission whose code-lane WP has no `execution_mode` but body code signals: has code is True in both helpers, and the acceptance gate requires the matrix;
- your existing planning-only untyped-WP test stays green;
- the `test_planning_only_bookkeeping_reaches_target_branch` regression test stays green.

## Verified (cycle-1 items resolved)

**Issue 1 (refusal scope).** Refusals are now gated on the stored single_branch topology.
- My probe of a lanes planning_artifact WP passes for both a clean and a dirty root.
- Mutation M6 (topology gate removed) is caught by `test_lanes_topology_planning_wp_allows_dirty_checkout`.

**Issue 2 (the regression itself).** `test_planning_only_bookkeeping_reaches_target_branch` passes again.
- Mutation M7 (frontmatter filter removed) is caught by `test_run_has_code_wps_false_for_a_legacy_wp_with_no_execution_mode`.
- The over-correction is Issue 1 above.

**Issue 3 (wrong-branch refusal).** Mutation M5 (check disabled) is now caught by 2 tests, including the isolated error-code-and-remedy test.
- CLI check (NFR-004): a real `implement` on a single_branch dirty fixture through CliRunner prints: `The write checkout at <path> has uncommitted changes: uncommitted.py. Commit or stash them before claiming probe-sb-dirty WP01.`
- That output names the blocking object and gives the remedy. The `error_code` is lost by the pre-existing broad except, which is acceptable per the coordinator.

**Issue 4 (missing tests).** The readiness, `--merges`, status-view and `--skip-lanes` tests are present.

**Test counts.** The WP04 new and changed test files, plus `test_tasks_status_view.py`: 73 passed.

**`executor.py`.** The cycle-2 hunk is confined to the `_run_has_code_wps` comprehension plus its docstring, which is minimal.
