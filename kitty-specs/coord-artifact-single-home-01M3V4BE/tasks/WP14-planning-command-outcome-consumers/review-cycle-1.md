---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T20:43:45Z'
reviewer_agent: claude
wp_id: WP14
---

# WP14 review: changes requested (reviewer-renata, opus)

Reviewed lane-l `e7b085d26c..8412dbbaa8`. That is 10 commits touching 10 files.

What holds up:
- T003 extraction and the `_commit_report` exit-code cross-check.
- setup-plan's JSON `surfaces`.
- The retrospect read/write split. Read bodies are byte-identical, and no read path probes or seeds.
- The two T074 retrospect tests. Both were verified red on base and green on HEAD.

Five problems block approval, and one test gap must be closed with them.

## Blocking

### B1. `retrospect create` / `backfill` crash on a consolidated coordination Mission

Locations: `retrospect.py:577` and `retrospect.py:774`.

`_canonical_events_write_path` calls `write_dir(STATUS_STATE)`. For a coord-topology Mission whose coordination branch was torn down by consolidation, that call raises `CoordinationBranchDeleted`. `meta.json` still declares `coordination_branch`, because consolidation does not flatten it. `STATUS_STATE` is not E2-eligible, so `write_dir`'s PUBLISHED short-circuit does not apply.

The call at L577 sits outside every handler. The result is a raw traceback, exit 1, and no JSON envelope, even though `retrospective.yaml` was already written.

Empirical repro:
1. `make_coord_mission(COORD, materialized=True)`.
2. Stamp `merged_at`.
3. `git worktree remove` the coordination worktree, then `git branch -D` the coordination branch.
4. Run `retrospect create --mission <slug> --json`.

| Commit | Exit | Output |
|---|---|---|
| Base `e7b085d26c` | 0 | `{"result":"success",...}` plus the non-fatal "auto-commit failed ..." warning |
| HEAD `8412dbbaa8` | 1 | Uncaught `CoordinationBranchDeleted` traceback from `retrospect.py:577`, no stdout JSON |

Post-merge is the normal time to run retrospect, so this is a regression on the main path.

T077 step 3 requires that write-side errors "surface as the command's actionable error". A traceback does not meet that.

Required:
1. Catch `write_dir`'s named refusals:
   - `CoordinationBranchDeleted`
   - `CoordinationWorktreeUnmaterialized`
   - `CoordSeedForkRefused`
   - `FeatureStatusLockTimeoutError` (`STATUS_LOCK_HELD`)
2. Render them as an actionable error. Keep `--json` stdout parseable. Never fall back to the root checkout.
3. Do the same at L774 (`_auto_commit_backfilled`). The `backfill` emit sites at L935/977/1001 currently mislabel a written record as `generator_exception`.
4. Add a CLI regression test for the consolidated-Mission case.
5. Escalate one design question to the orchestrator/architect, and record the ruling: where should a STATUS_STATE append go for a PUBLISHED coordination Mission? Today `write_dir` has no answer for that case.

### B2. The retrospect auto-commit warning is no longer additive

Location: `retrospect.py:402`.

`_warn_auto_commit_failed` now fires only when `_render_unexplained_surfaces` printed nothing. For an `error` surface with named paths, the renderer prints only `✗ primary (<branch>): refused — <path>: error`. That drops two things:
- git's own failure text (hook rejection, index.lock);
- the remediation "The record is written but not committed; commit it by hand: <paths>".

Proof: I restored the two assertions you removed into `tests/cli/commands/test_retrospect.py::TestAutoCommitFailureIsSurfaced::test_create_warns_on_stderr_and_keeps_json_parseable_when_auto_commit_fails`:
- `assert git_error in warning`
- `assert "commit it by hand" in warning`

Both parametrizations fail at HEAD. The stderr is only the two `✗ ... refused — ...: error` lines.

The assertions were deleted at `test_retrospect.py:925` and `:1048`. That file is not in `owned_files`. Weakening a pin to fit lost information is the delete-the-assertion anti-pattern.

Required:
- Render the surface lines in addition to the existing warning, the same way setup-plan does. The protected-target de-duplication stays as it is.
- Restore the original assertions, and keep the new `refused` ones as well.

### B3. Diff coverage is 69%; the gate is 90%

Measured with `diff-cover` against `e7b085d26c`, over the blast-radius run:

| File | Coverage | Missing lines |
|---|---|---|
| `mission_record_analysis.py` | 25% | 234-240, 244, 260-297, 309-319, 356-357, 476, 519-520 |
| `orchestrator_api/commands.py` | 93% | 3054 (the `warnings` arm) |
| All other changed files | 100% | |

Mutation testing shows record-analysis and the orchestrator have no tests at all. Mutants M5-M8 below survive the whole record-analysis and orchestrator test sets (58 and 177 tests). The `create_intent` file `tests/orchestrator_api/test_commit_outcome_rendering.py` was never created.

Required: focused tests for each case below, each with a one-surface-refused fixture asserting the surface name, fate and reason:
- `_commit_analysis_report`;
- record-analysis JSON `surfaces`;
- record-analysis text warning;
- the `--report-only` text render;
- `_record_analysis_commit_surfaces_payload`, both `commit_surfaces` and `warnings`.

### B4. record-analysis `--report-only` uses a hand-rolled second outcome shape and drops output

Location: `mission_record_analysis.py:247-320`.

`_print_report_transaction_payload` and `_SurfacesOnly` re-parse `commit_outcome_payload`'s dict back into `SurfaceOutcome`/`PathFate`. Problems:
- It is a second, CLI-local copy of the outcome vocabulary (surface and status literal tuples).
- It silently `continue`s past malformed entries.
- Its C901 is 13.
- It is 0% tested.

This goes against the intent of contract rule 6: one owner of the shape, and nothing formatted by hand.

It also changes text output for every topology. When `surfaces` is present, the raw payload dict (path, verdict, `commit_hash`, `commit_status`) is no longer printed at all, so the change is not additive. That breaks C-008 for lanes and single_branch Missions.

There is also a gap on the failure arm:
- When `_commit_report` raises on a refused surface (`report_transaction.py:187`), the error dict at `:280` carries no `surfaces`.
- The message reads `Report commit did not complete: committed`, which is misleading.
- The rule that requires render lines on every outcome arm is not met here.

Required:
- Carry the typed `CommitRouterResult` out of `record_report_transaction` alongside the payload. For example, return it or attach it to a typed carrier or exception. Render from that object.
- Delete the deserializer.
- Print the payload as before, plus the surface lines.
- Include `commit_outcome_payload(outcome)` on the failure arm too.

### B5. New red: `test_ruff_format_exclude_ratchet::test_every_exclude_entry_still_genuinely_reformats`

This test is green at base and red at HEAD. `retrospect.py` was fully reformatted (commit f9138b1d91, about 350 lines of churn mixed with the behaviour change), but it is still listed in `pyproject.toml:540` under `[tool.ruff.format].exclude`.

Two ways to fix it:
- **Preferred:** revert the formatting churn so the behavioural diff stays reviewable.
- **Alternative:** remove the exclude entry. `pyproject.toml` is not in `owned_files`, so get the orchestrator's OK first, and land the reformat as its own tidy commit.

### B6. setup-plan's render-every-arm has no test

Location: `mission_setup_plan.py:283`.

Mutant M2 replaces the guard with `if False:`. It survives `test_planning_commit_outcome_consumers.py`, `test_mission_planning_entry.py` and `test_agent_mission_commit_to_branch.py`. Every `_commit_to_branch` test runs with `json_output=True`.

Required: a text-mode test asserting the rendered surface lines, at least on the `committed` arm and on a `no_op_wrong_surface` or `error` arm.

## Non-blocking (fix if cheap, otherwise record)

- **N1. Deviation 1 (additive rendering).**
  - Acceptable for setup-plan: the hand-written arm lines carry behaviour and pins.
  - Not acceptable as implemented for retrospect (see B2) or record-analysis (see B4), because neither is additive there.
- **N2. Deviation 2 (setup-plan status not gated on exit code).** The premise checks out:
  - `_commit_to_branch` commits exactly `(plan_file,)`, with PRIMARY kind and a PRIMARY path, so there is always one partition group. With `owned=`, there is also one group.
  - The gap-analysis and generator-config commits are `(gap file, meta.json)`, and both are PRIMARY.
  - So no coordination surface can be refused, and this is not blocking.

  A refused PRIMARY surface is still reachable, though:
  - `WRONG_SURFACE`, or `PROTECTED_BRANCH_REFUSED`, which maps to legacy `no_op_wrong_surface`.
  - In that case setup-plan exits 0 with `result: success`. That conflicts with contract rule 5 and D8's exit rule.
  - The behaviour is pre-existing and pinned (FR-006/D-5), and retrospect's best-effort exit 0 has the same tension.
  - This needs an orchestrator ruling. It is not WP14's to decide.
- **N3. The "neither committed nor unchanged" predicate is copied four times with a literal tuple.** The copies are in setup-plan, record-analysis, the orchestrator and retrospect. Use `commit_outcome.STATUS_COMMITTED` and `STATUS_UNCHANGED`, as the binding rule requires constants from `commit_outcome`. Ideally there would be one helper in `commit_outcome`, but that module belongs to WP05, so that part is a follow-up.
- **N4. Process.**
  - The record-analysis extraction was not a separate behaviour-preserving commit: af8d6ac422 mixes extraction and rendering. The review guidance requires them to be separate.
  - `record_analysis` C901 went from 13 to 15. That is at the ceiling, and the extraction was meant to create headroom.
  - The setup-plan T074 test (50110c03f5) landed after its fix (1aa12bc042), so it was not red-first.
- **N5. A comment points at code that no longer exists.** `mission_record_analysis.py:347` says "see the original call site's comment for the full rationale", but that call site is gone. Restore the #3678 rationale in the helper.

## Mutation evidence (scratch worktree at HEAD)

| Mutant | Location | Change | Result |
|---|---|---|---|
| M1 | `report_transaction._commit_report` | drop `or commit_outcome_exit_code(outcome) != 0` | killed |
| M2 | `mission_setup_plan.py:283` | render guard to `if False` | **survived** |
| M3 | `_build_setup_plan_result` | drop `surfaces` update | killed |
| M4 | `retrospect._render_unexplained_surfaces` | never render | killed |
| M5 | orchestrator `_record_analysis_commit_surfaces_payload` | always `{}` | **survived** (177 tests) |
| M6 | `_print_report_transaction_payload` | always raw | **survived** (58 tests) |
| M7 | record-analysis payload | drop `surfaces` | **survived** |
| M8 | record-analysis | drop warning | **survived** |
| M9 | retrospect protected de-dup | disabled | killed |

## Verified OK

- **Stash incident.** `git diff e7b085d26c..HEAD` touches only the 6 owned src files, the 3 owned test files, and `tests/cli/commands/test_retrospect.py`. That last file is not owned; see B2. There are no edits to `status_transition.py` or `transaction.py`, and `git status` is clean.
- **T077 redo.** It is complete:
  - All 6 retrospect write sites and the single agent-retrospect write site use the write variant.
  - The read sites (`retrospect.py:205`, `agent_retrospect.py:259`) are unchanged.
  - The `_canonical_events_path` body is byte-identical; only its docstring changed.
- **Orchestrator contract.** Only additive keys were added. `orchestrator_api` has no forbidden fields, and the private `_do_record_analysis_write` / `_run_write_with_timeout` have no external callers. `tests/contract/test_orchestrator_api.py` and `tests/specify_cli/orchestrator_api/` are green.
- **Static checks.** ruff is clean. `ruff format --check --force-exclude` reports 9 files formatted. `mypy --strict` on the 6 src files is clean at both base and HEAD. C901 stays ≤15 throughout.

## Notes for WP20

- Write qualnames: `retrospect.py::_canonical_events_write_path` and `agent_retrospect.py::_canonical_events_write_dir`.
- The read qualnames are unchanged.
