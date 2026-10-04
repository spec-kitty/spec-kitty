# Research memo: nightly reds 2026-10-03

Newest nightly: <https://github.com/spec-kitty/spec-kitty/actions/runs/37177460494>
(2026-10-04, head `b2c466d7d1`, equal to `main` when this mission started). It supersedes the run
cited in the brief (37094126479, head `a3f76f673a`).

Grounding squad: debugger-debbie (root cause), researcher-robbie (history), paula-patterns
(grouping and fix shape). CodeGraph was available and used to map tests to production symbols.

## Suites

| Suite | Tracker | Newest run | In mission |
|---|---|---|---|
| interpreter-3.13-shard-4 | see #5562 | green; tracker closed by the bot | Dropped. Its only failure was the terminology guard fixed by PR #5586. |
| interpreter-3.13-shard-3 | #5418 | 9 failed, 8693 passed | Yes: groups A to E |
| specify_cli out-of-matrix | #5258 | 9 failed, 12447 passed (same 9) | Yes: groups A to E |
| performance | #5419 | 23 failed, 107 passed | Partly: group F yes, group G awaits a ruling |

Stress, integration+next and the integration marker slice were also red on this run. They have
their own trackers (see #5610, see #5611, see #5612) and are out of scope.

## Failing tests

All nine cases of groups A to E reproduce locally on `b2c466d7d1` (`9 failed, 3 passed`).

| Group | Test id | Assertion | Cause | Classification | File to change |
|---|---|---|---|---|---|
| A | `tests/specify_cli/missions/test_handle_equivalence_matrix.py::test_mission_run_identity_identical_across_handle_forms[083-my-feature-01KTPKST]`, `[01KTPKST]`, `[083]` | exit 2 `MISSION_TYPE_CONFLICT` instead of 0 | Fixture seeds a `software-dev` mission and runs custom key `matrix-custom-run`; `866402daba` (PR #5421) refuses to retype a mission | Pre-existing, stale fixture, in scope | the test file |
| B | `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py::test_registered_command_names_match_frozen_subcommands` | registered set has extra `run-index` | `ac4e8b84a8` (PR #5487) added `doctor run-index` | Pre-existing, stale oracle, in scope | the test file |
| C | `tests/specify_cli/upgrade/migrations/test_hosted_endpoint_session_backfill.py::TestMigrationSequencing::test_delete_then_backfill_ends_backfilled_not_stuck_deleted`, `::test_retired_config_and_retired_issuer_ends_unconfigured_not_resurrected` | `PermissionError '/any'` or `FileNotFoundError '/any/project/.gitattributes'` | Test applies every applicable migration to a fabricated path and skips the `detect()`/`can_apply()` gate; newer migrations write to the project | Pre-existing, test-harness defect, in scope | the test file |
| D | `tests/specify_cli/cli/commands/test_doctor_skills.py::test_doctor_skills_json_error_schema_stable` | `canonical_commands` 14 != 15 | `3d5c85d09c` (PR #5545) removed the dashboard command | Pre-existing, stale oracle, in scope | the test file |
| E | `tests/specify_cli/cli/commands/test_init_hybrid.py::TestHybridInstallOutputShape::test_generate_all_shims_produces_thin_cli_shims`, `::test_hybrid_layout_full_prompts_plus_cli_shims` | 6 shims != 7; 15 files != 16 | same dashboard removal | Pre-existing, stale oracle, in scope | the test file |
| F | `tests/e2e/test_worktree_owned_root_concurrency.py::test_installed_cli_keeps_two_owned_worktrees_isolated[0..19]` | `command failed rc=1` (`COORD_SEED_GIT_PROBE_FAILED`) | The performance job checks out shallow; `default_source_snapshot_builder` fetches without `--update-shallow`, so the snapshot has missing parents and no `.git/shallow`; `5b5699e500` added a history walk that fails on it | Pre-existing, test-support defect, in scope | `tests/_support/shared_build_artifacts.py` |
| G | `tests/performance/test_owned_checkout_perf.py::test_owned_tasks_status_median_stays_inside_its_budget`, `::test_owned_setup_plan_median_stays_inside_its_budget`, `::test_owned_context_resolve_median_stays_inside_its_budget` | about 2.6 s > budget 2.0 s | Interpreter cold start alone is about 1.8 s on a 32-core workstation and has not changed since the budget landed (`75e678bb1e`, PR #5445). The tests passed on 10-02 and 10-03 and failed on 10-01 and 10-04; they follow runner speed | Budget not met by the product; not a regression, not a `regression`-marked red. **Operator ruling needed** | none in this mission |

No failure carries `@pytest.mark.regression`. No merged commit after `a3f76f673a` and no open pull
request addresses any group.

## Why pull-request CI did not catch groups A to F

`tests/specify_cli/**` runs only in the nightly out-of-matrix and interpreter lanes, and the
performance lane is nightly-only. The pull requests that changed the product merged green.

## Pattern notes (paula-patterns)

- B is a deliberate frozen snapshot: update it by hand.
- D and E are duplicate censuses of the command registry. The single literal census to keep is
  `tests/specify_cli/skills/test_command_installer.py` (`== 14`); D and E should derive their counts
  from `CANONICAL_COMMANDS`, `CLI_DRIVEN_COMMANDS` and `PROMPT_DRIVEN_COMMANDS`.
- C must assert the two migration ids are present, or the order check can pass on an empty list.
- F: a genuine shallow clone does not fail the probe. A separate product question remains (the
  post-fix discriminator returns "pre-fix" when the seed commit lies beyond a shallow boundary);
  it is not fixed by this mission and goes to the operator hand-off as a candidate issue.

## Group G options for the operator

1. Leave the three tests red and keep #5419 open, with a dedicated issue for CLI cold start against
   the 2-second charter standard.
2. Reduce start-up import cost in the product (`-X importtime`: `cli.commands.init` about 0.69 s
   cumulative, of which `state.contract` → `runtime.next.run_index` → `_internal_runtime` about
   0.57 s). The saving is unproven and this is product work beyond a test repair.
3. Change what the tests measure (budget relative to the start-up floor, or a higher absolute
   budget). The brief forbids raising budgets, so this needs an explicit ruling.

## Outcome (2026-10-04)

- Operator ruling on group G: align the budget to the 2.5 s of `tests/performance/test_cli_startup_budget_4409.py`. Both files now read one constant, `CLI_COLD_START_BUDGET_SECONDS` in `tests/_perf_helpers.py`. The two red nightlies measured 2.6 to 2.7 s, so the tests can still fail on a slow runner. Follow-up: #5614.
- Group C is red only when the whole migration registry is loaded (a full-suite run); the file alone passes on base. The repaired tests pass in both conditions.
- Tooling friction: `spec-kitty consolidate` (squash) merged all four lanes and then refused with "projected coordination bookkeeping content did not land on the target" and rolled back, twice. The only divergent path was the derived `status.json` snapshot (the target copy was re-materialized without `schema_version` and several fields; `status.events.jsonl` was identical). The branch was assembled from the tool's own squash result, one commit per work package, with the coordination copy of `status.json`.
- Tooling friction: `spec-kitty agent mission create` run from a linked git worktree resolves the primary checkout as the repository root, so `--start-branch` on the worktree's own branch fails. A standalone clone was used instead.
