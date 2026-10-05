# Code grounding: nightly suites green on main

- **Date:** 2026-10-05
- **Base:** `upstream/main` @ `9adc68803f` (nightly run 37225822329, 53 of 57 jobs green)
- **Method:** baseline re-run by the orchestrator, then a read-only squad of four
  profile-loaded lenses (debugger-debbie, researcher-robbie, paula-patterns,
  architect-alphonso). Nothing in the repository was edited during grounding.
- **Reader:** the planner, implementers and reviewers of this mission.

Claims marked *hypothesis* were read from code and not reproduced.

## 1. Baseline on the mission base

| Red | Command | Result on `9adc68803f` (local, 32 cores) |
|---|---|---|
| Track A | `pytest tests/integration/test_merge_lane_planning_data_loss.py::test_bare_slug_coord_mission_consolidates_onto_a_protected_target -n0` | failed, same `MERGE_UNSAFE_WORKTREE_DIRTY` as the nightly |
| Track C | `pytest tests/specify_cli/cli/commands/test_commit_recipes.py -n0` | 1 failed, 16 passed, same single hit |
| Track B | `SPEC_KITTY_RUN_PERFORMANCE=1 pytest tests/performance/test_owned_checkout_perf.py -n0` | 3 passed, about 1.4 s per invocation; the nightly red is runner-bound |

The four red nightly jobs are: performance, interpreter shard 3 (Python 3.13),
specify_cli out-of-matrix, integration+next.

## 2. Alignment

| Issue | Verdict |
|---|---|
| #5611 (P0) | Real. Rolling nightly tracker. Three of its four original reds were fixed by #5646; the one left is the #5651 reproduction. |
| #5651 (P1) | Real. The product defect behind the remaining #5611 red. No PR or branch. It asked for a design ruling, given on 2026-10-05 (section 3.4). |
| #5419 (P0) | Real. #5617 only aligned the budget to 2.5 s; the latest run measured 2.52 to 2.59 s. |
| #5614 (P2) | Real. The work item for Track B. |
| #5708 (P1) | Real. Cause is `22994ca25` (#5647, landed via #5659). |
| #5699, #5700 | Open auto-trackers for interpreter shard 3 and out-of-matrix. Track C clears both. |
| #5638, #5644 | Real, but a different mechanism from the #5611 red (section 3.5). Cross-reference only. |
| #5652 | Does not own the Track C routing gap (section 5.5). Cross-reference only. |

No open PR or branch fixes any track (open PRs checked: #5709, #5694, #5540, #5326).

## 3. Track A: a bare-slug coordination Mission cannot consolidate onto a protected target

### 3.1 Root cause

Consolidate plants the status files itself and then refuses on them.

1. `consolidation/executor.py:487` calls `entry_preflight.py:452 _resolve_run_status_dir`.
2. That resolves the write directory through `mission_runtime/resolution.py:2499 write_dir`,
   `coord_seed.py:1220 establish_coord_write_location` and `:974 _handle_empty_pre_fix`.
3. `coord_seed.py:783 _run_merge_and_commit` writes `status.events.jsonl` and `status.json`
   under the composed directory `kitty-specs/<slug>-<mid8>/` in the coordination worktree.
   `:651 _commit_and_restore` calls `_commit_seed` (`:585-604`) with the bare `mission_slug`.
4. `commit_router.py:1036 _group_files_by_partition` calls `partition_for_mission_path`
   (`:968`), which reaches `mission_runtime/artifacts.py:508-509`. There
   `path_mission_slug != mission_slug`, so the path is not recognised as this Mission's
   status file and is grouped as `SPEC` (PRIMARY partition).
5. The protected-primary refusal at `commit_router.py:476-515` returns `no_op_wrong_surface`.
6. `coord_seed.py:652-656` logs a warning and consolidate continues. The files stay
   untracked and the worktree-removal guard reports `MERGE_UNSAFE_WORKTREE_DIRTY`.

### 3.2 Introducing commit

`5b5699e500` ("give coordination artifacts one durable home"), confirmed by bisect: the
sibling test passes at `5b5699e500^` and fails at `5b5699e500`. The #5650 executor split
(`ea62109a96`) only moved code. The #5664 orchestrator_api split is not on the call chain.

### 3.3 Test verdict

Valid; fix the product. `coordination/transaction.py:131-170` documents the bare-primary
shape as genuine, and the behaviour regressed from green. The sibling
`test_explicit_delete_override_still_reachable` passes today because `c5f1280aeb` re-keyed
its fixture to the canonical slug, so no seed runs; that is a fixture change, not a
product fix.

### 3.4 The red has three layers

Probed with in-memory patches, no repository edits:

| Patch applied | Result |
|---|---|
| Partition classifier only | Seed commits; reconciliation FAILS on `kitty-specs/<slug>-<mid8>/status.events.jsonl` (`reconciliation.py:1166 _is_bookkeeping`, bare-slug anchored) |
| Plus `_is_bookkeeping` | Reconciliation passes; teardown fails with "coordination teardown incomplete: branch still exists" |
| Plus teardown metadata read | Test passes |

The third layer is `consolidation/phase_teardown.py:393`: it loads `meta.json` from the
status directory, which has none, so `mid8` is empty and the worktree is never destroyed.

**Operator ruling (2026-10-05): alias authority.** Keep the composed coordination
directory. Add one exact alias set `{primary directory name, composed <slug>-<mid8> name}`
with `mid8` read from `meta.json`, never prefix-matched. Consumers: the partition
classifier (`commit_router.py:928/968`), the bookkeeping exemption
(`reconciliation.py:1166`), the bookkeeping sites (`phase_bookkeeping.py:567`,
`bookkeeping_projection.py:467`) and the teardown metadata read (`phase_teardown.py:393`,
via the PRIMARY metadata). The rejected alternative was a single directory name keyed on
the primary directory.

Backstop: `entry_preflight._resolve_run_status_dir` should refuse with the real cause when
the seed report says the commit was not applied. Today it proceeds to a misleading
"Commit, stash, or revert" remedy. Removing the uncommitted files is not an option: it
contradicts the documented seed-retry design (I-SEED-10, `coord_seed.py:626-643`).

### 3.5 Related issues

- **#5638, cross-reference.** There the rollback's byte-restore leaves *tracked* status
  files modified against HEAD, after mutation. Here *untracked* files come from a refused
  seed commit before the pre-mutation snapshot, so rollback never runs.
- **#5644, cross-reference.** That guard detects committed events lost from the worktree;
  here nothing was committed. *Hypothesis:* its raw-row writers go through the same
  partition grouping and inherit the misroute on bare-slug Missions.

### 3.6 Sibling hazards (same bare-slug anchor; read only, not reproduced)

`safe_commit_cmd.py:253`, `retrospect.py:443`, `mission_record_analysis.py:195`,
`acceptance/__init__.py:204,451`, `acceptance/ledger_dirt.py:41`, `agent/workflow.py:413`,
`mission_finalize_planning_pin.py:902`, `consolidation/phase_teardown.py:128,502`, and any
`commit_for_mission(..., kind=STATUS_STATE)` writer (`decisions/emit.py`,
`retrospective/events.py`, `retrospective/lifecycle_events.py`). During the probe the
retrospective event was appended to the primary bare directory's event log, a second
status home.

### 3.7 Gates and tests for Track A

Architectural (named files only): `test_write_surface_placement_guard.py`,
`test_no_write_side_rederivation.py`, `test_status_events_writes_gate.py`,
`test_merge_reconciliation_class_guard.py`, `test_wp_integrity_partition_call_shape.py`,
`test_trio_seam_only.py`, `test_mission_runtime_surface.py`,
`test_coord_read_residuals_closeout.py`, `test_no_dead_symbols.py`.

Behavioural: `tests/coordination/test_coord_seed.py`, `tests/coordination/test_commit_router.py`,
`tests/specify_cli/coordination/test_commit_router_partition.py`,
`test_commit_router_partition_authority.py`, `test_partition_authority_characterization.py`,
`tests/coordination/test_ledger_topology_less_callers.py`,
`tests/mission_runtime/test_artifact_partition_mapping.py`,
`tests/mission_runtime/test_placement_seam_write_dir.py`,
`tests/consolidation/test_reconciliation.py`, `test_coord_teardown_order_3926.py`,
`test_coordination_flatten_on_branch_delete.py`,
`tests/integration/test_merge_lane_planning_data_loss.py`.

## 4. Track B: runner-bound start-up budgets

### 4.1 Inventory

131 `performance` tests and 15 `timing` tests collect. The single budget authority is
`CLI_COLD_START_BUDGET_SECONDS = 2.5` at `tests/_perf_helpers.py:37`; the two test files
alias it.

| Location | Timed | Threshold | Kind | Hazard |
|---|---|---|---|---|
| `tests/performance/test_owned_checkout_perf.py:123/129/136` | median of 5 fresh `python -m specify_cli agent ...` | 2.5 s | absolute | yes, red |
| `tests/performance/test_cli_startup_budget_4409.py:300` | one `--help`, single shot | 2.5 s | absolute | yes, 0.55 s margin, no median |
| `tests/performance/test_cli_startup_agent_commands_freshness.py:147` | second (warm) `context list` | 5.0 s (own constant, line 66) | absolute | medium |
| `tests/specify_cli/next/test_next_cold_start_performance.py:71` | 5 rounds of `next` | none | benchmark | asserts nothing in the nightly: the workflow and compare flag its docstring cites do not exist |
| `tests/policy/test_lane_tip_recorder.py:448` | hook against no-hook p95 | delta | relative | robust precedent |
| `tests/consolidation/test_canceled_content_benchmark.py:250` | mixed against baseline | delta | relative | robust precedent |
| about 110 others | in-process work | 0.05 to 30 s | absolute | low; green in all 9 runs |

`performance` tests are skipped unless `SPEC_KITTY_RUN_PERFORMANCE=1`
(`tests/conftest.py:335-348`); only the nightly `performance` job sets it. The `timing`
marker has no CI job (`pytest.ini:82`).

### 4.2 CI data (xunit of 9 nightly runs)

| Run | Head | `--help` | Owned medians | Owned / help |
|---|---|---|---|---|
| 36811585861 | `f4dc26694c` | 1.95 | 2.71 / 2.85 / 2.76 red | 1.46 |
| 36920764277 | `3546f35be7` | 1.83 | 2.65 / 2.72 / 2.62 red | 1.48 |
| 36960774283 | `d79a12928b` | 1.14 | about 1.54 green | about 1.35 |
| 37094126479 | `a3f76f673a` | 1.76 | about 1.88 green | about 1.07 |
| 37177460494 | `b2c466d7d1` | 1.94 | 2.60 / 2.70 / 2.60 red | 1.39 |
| 37225822329 | `9adc68803f` | 1.72 | 2.52 / 2.59 / 2.54 red | 1.51 |

`--help` alone moves 1.14 to 1.95 s (1.7 times) between runs. The ratio is far tighter;
the 1.07 outlier comes from a single-shot denominator. "about" figures are junit time
divided by 5.

### 4.3 v4.0.0rc5 against main: no step regression

Same interpreter, interleaved, 9 runs each, one isolated home per tree.

| Command | main median | rc5 median | Delta |
|---|---|---|---|
| `--version` | 0.978 s | 0.947 s | +0.031 |
| `context list --json` | 1.090 s | 1.033 s | +0.057 |
| `agent tasks status --json` | 1.255 s | 1.211 s | +0.044 |

main imports 1604 modules against 1566 (3 to 5 percent drift over 445 commits). The
standing cost is the chain `specify_cli.cli.commands.init` (0.43 s) to
`specify_cli.state.contract` to `runtime.next.run_index` to `runtime.next._internal_runtime`
(0.36 s, including `spec_kitty_events` 0.13 s), present in both trees. That is product
cost, separate from the test budget.

Measurement trap: two source trees sharing one `SPEC_KITTY_HOME` pushed every
`context list` to 4.3 s. Any calibration run needs one home per tree.

### 4.4 Local probe of the candidate measures (real `owned_mission` fixture, floor = `--version`)

| Condition | Floor | Owned median | Delta | Ratio |
|---|---|---|---|---|
| idle, N=7 | 0.987 s | 1.32 to 1.36 s | +0.33 to 0.37 | 1.34 to 1.37 |
| 40 CPU burners, N=5 | 1.522 s | 2.18 to 2.29 s | +0.66 to 0.77 | 1.43 to 1.51 |
| 0.5 s sleep planted on `agent` commands, N=5 | 1.122 s | 2.04 to 2.10 s | +0.92 to 0.97 | 1.82 to 1.87 |

Git subprocesses per command (one sample each): tasks status 7, setup-plan 14,
context resolve 7, `--version` 0.

- A delta over the floor doubles under load, so it stays runner-bound.
- The ratio drifts only 1.34 to 1.51 under load and matches CI (1.35 to 1.51), and a
  planted 0.5 s regression lands at 1.82 or above.
- The ratio is blind to a regression of the floor itself.
- Open: `--version` loaded more modules (1552) than the owned commands (1282 to 1284) in
  the probe, so it may not be a clean floor. Verify before adopting it.

### 4.5 Binding rules

`docs/development/testing/testing-flakiness.md`: line 49 "Tune the budget, never retry
... Investigate before bumping; the budget is the gate, not the regression"; line 126
"shared-runner wall clock is not accepted as evidence"; lines 145-146 move a timing
concern to a generous Tier-1 budget or remove the wall-clock dependency.

`tests/architectural/test_performance_marker_guard.py` requires every assertion in a
`performance`-marked test to be timing vocabulary, so a count-based proxy cannot carry
that marker. `tests/ci/test_no_blocking_latency_gate.py` forbids a wall-clock ceiling on
the per-PR path.

### 4.6 Gates and tests for Track B

`tests/architectural/test_performance_marker_guard.py`, `test_timing_coverage_invariant.py`,
`test_marker_job_completeness.py`, `test_fast_tier_marker_completeness.py`;
`tests/ci/test_no_blocking_latency_gate.py`, `test_nightly_timeout_headroom.py`.

## 5. Track C: commit-recipe gate

### 5.1 Scanner rules (`tests/specify_cli/cli/commands/test_commit_recipes.py`)

- AST scan of `src/specify_cli/**/*.py` (`_SRC_ROOT` :44).
- A hit is any string constant or f-string literal part containing the bare substring
  `git commit` (`_NEEDLE` :45).
- Exempt: docstrings, and elements of a list or tuple whose first element is `"git"`.
- `_ALLOWED_GIT_COMMIT_HITS` (:55-123) has 14 entries keyed by path and substring. Guards:
  stale entry (:249), substring length at least 16 (:261), five fixture controls (:267-320).
- Defect class: printed copy-paste `git add` / `git commit` recipes that bypass
  `spec-kitty safe-commit` (#5078). Renderer: `_commit_recipes.safe_commit_recipe`.

The hit is `MESSAGE_OPTION_HELP` at `src/specify_cli/cli/commands/_commit_message.py:13`,
consumed only as `typer.Option(help=...)` in `safe_commit_cmd.py:434` and
`spec_commit_cmd.py:476`.

### 5.2 Fix options, measured with a scratch replay

| Option | Current 15 hits | 11 historical true recipes (tree at `3e09226fb4^`) |
|---|---|---|
| Recipe-shape rule: `git commit` followed by a flag, quote, placeholder or `$`, or ending a string, line or backtick span | help text and 12 of 14 allowlist entries stop being hits; 2 stay (`implement.py`, `core/mission_creation.py`) | all 11 still flagged |
| Exempt strings reaching `help=` | only the help text changes | unchanged; a real recipe in help text would pass |
| Reword the help | only the help text changes | unchanged; does not fix the class |

Chosen: the recipe-shape rule. 12 of the 14 allowlist entries are log strings, not
recipes, and the allowlist has grown twice since creation (`c5e0d1ed71`, `25063e4cd8`).
The stale-entry check then forces the allowlist from 14 entries to 2. Known
false-negative shapes to cover in fixtures: flagless imperative prose and an ellipsis
after `git commit` (the #3931 shape), unless the rule also fires on a co-occurring
`git add`.

### 5.3 Boundary with the move-task remedy mission (#3931)

Do not touch `cli/commands/_git_remedies.py`,
`cli/commands/agent/tasks_parsing_validation.py:396,597,634,762-791` or
`cli/commands/agent/tasks_move_task.py:961`. None is a current scanner hit.

### 5.4 Why per-PR CI missed it

- The `cli` registry row has no `test_dirs`, so it runs only `tests/cli`.
- `tests/specify_cli/cli/commands` is recorded in `out_of_matrix_test_dirs`
  (`.github/ci-module-registry.yml:473-484`) as a measured-durations decision (#4374).
- Claiming it is blocked: its child `commands/agent` is claimed by `execution_context`,
  and `test_registry_test_dirs_are_pairwise_non_nested` forbids nested claims. The tree
  collects 2,960 tests.

**Operator ruling (2026-10-05): move the gate.** The scanner and allowlist tests move to
`tests/architectural/` (precedent: `test_completion_manifest_freshness.py`, #4479). The
architectural battery fires on every `src` group. Dry run of the router:

- `src/specify_cli/cli/commands/_commit_message.py` selects module `cli` and the battery,
  so #5659 would have gone red.
- `src/specify_cli/git/commit_helpers.py` is unmatched and selects everything.

The file runs in about 6 s. No registry edit is required and no source lines change, so
diff-cover is unaffected.

### 5.5 Boundary with #5652

#5652 is about the `regression` marker and `tests/regression/` having no lane. It does
not own this gap. The remaining 2,960-test tree belongs to #4374 / #4732; the general
"no test path outside every lane" guard is #4708.

### 5.6 Gates and tests for Track C

`tests/architectural/test_module_shard_registry.py`, `test_out_of_matrix_evidence.py`,
`test_battery_partition_proof.py`, `test_gate_selection_authority.py`,
`test_interpreter_shard_coverage.py`, `test_marker_job_completeness.py`,
`test_no_duplicate_suite_execution.py`, plus the moved gate file. Open: whether a new
architectural file needs a `battery_file_durations` seed, and whether a naming census
constrains the file name (*hypotheses*).

Planted-break proof: `make ci-parity`, or
`python -c "from scripts.ci.gate_selection import select_gates; print(select_gates(['src/specify_cli/<file>.py']).selected_jobs)"`,
then plant a recipe-shaped string and run the moved file.

## 6. Paths owned by running missions (do not edit)

| Mission | Paths |
|---|---|
| #5635 | `cli/commands/implement*.py`, `agent/workflow_executor.py`, `coordination/planning_commit.py`, `core/dependency_graph.py`, `lanes/implement_support.py`, `status/emit.py`, `status/__init__.py`, `workspace/context.py`, `pyproject.toml`, `tests/architectural/test_layer_rules.py`, `test_wp_integrity_partition_call_shape.py`, `dead_symbol_allowlist.yaml` |
| #5634 | `core/mission_creation*.py`, `tests/core/test_mission_create_coord_status_*.py` |
| #5573 | `lanes/compute.py`, `compute_and_persist.py`, `frozen_membership.py`, `lane_tip.py`, `models.py`, `agent/mission_finalize*.py`, `tests/specify_cli/cli/commands/agent/**` |
| #5457 | `upgrade/runner.py`, `lanes/consolidation.py`, `auto_rebase.py`, `stale_check.py`, `worktree_allocator.py`, `state/contract.py`, `tests/architectural/test_destructive_op_routing.py` |
| #4925 (PR #5709) | `cli/commands/upgrade.py`, `upgrade/finalize.py`, `upgrade/outcome.py`, `skills/manifest_store.py`, `tool_surface/repair.py` |
| #5668 | `consolidation/reconciliation.py`: the approved-claim bound (about line 1142). Track A edits `_is_bookkeeping` (line 1166) only, by operator ruling. |
| #3931 | `agent/tasks_move_task*.py`, `_git_remedies.py`, `tasks_parsing_validation.py` |

Two adjacencies for Track A: `core/mission_creation.py:1971` is a second caller of the
seed, and `implement.py::_partition_files_for_commit` consumes the same classifier. Fix on
the callee side only. `CHANGELOG.md` and `docs/adr/4.x/index.md` are contended by every
mission; number new ADRs `2026-10-05-N`.

## 7. Nightly selections to reproduce

| Job | Selection |
|---|---|
| integration+next | `pytest tests/integration tests/next -q -n auto --dist loadfile` (no marker filter) |
| performance | `SPEC_KITTY_RUN_PERFORMANCE=1 pytest -m performance -q` |
| interpreter shard 3 | Python 3.13, `-m "fast or unit"`, path list at `ci-nightly.yml:646` (includes `tests/specify_cli/cli`) |
| out-of-matrix | `pytest tests/specify_cli --ignore=<each registry-claimed dir> -m "not stress and not timing"` (`ci-nightly.yml:1111-1127`) |

`workflow_dispatch` works on any ref. Every escalation step is gated on
`refs/heads/main` (and `scripts/ci/nightly_escalation.py:90,113` enforces it again), so a
branch run cannot open or close a P0 tracker.

## 8. Findings outside this mission (follow-up issues)

- The `next` cold-start benchmark asserts nothing in the nightly (section 4.1).
- The `timing` marker has no CI job.
- `tests/specify_cli/charter_preflight/test_performance.py:49` is a 500 ms absolute
  cold-import budget that no CI job runs.
- The standing 0.36 s cold-start import chain (section 4.3) against the charter's
  "CLI operations under 2 seconds" standard.
- The sibling bare-slug anchors in section 3.6.

## 9. Post-specify squad addendum (2026-10-05)

Two lenses (reviewer-renata, architect-alphonso) reviewed the spec; the Track A debugger
then measured the end state. Findings folded into the spec are listed in the plan. The
facts that correct or extend sections 3 to 5:

### 9.1 `_is_bookkeeping` exempts a subtree, not filenames

Any path with a `kitty-specs/<mission_slug>/` segment pair returns True
(`reconciliation.py:1237-1238`), so `spec.md` under the Mission directory is exempt
today. A plain alias would exempt all of `kitty-specs/<slug>-<mid8>/**`. The alias leg is
therefore restricted to coordination record kinds. Its inputs are
`(path, mission_slug, planning_prefix)` with three call sites (`:1163`, `:1651`, `:1876`);
the composed name can be derived inside the function from `planning_prefix` (the write
accessor's directory relative to the repository, `:2055-2065`, `:1398`) with no signature
change. *Hypothesis:* `feature_dir` there is `run.feature_dir`.

### 9.2 End state on the target (measured)

| Scenario | Directories on the target | Event-log lines |
|---|---|---|
| Bare slug at the base, three-layer probe patch | two: `retention-override/` (all six files) and `retention-override-01KX0000/` (`status.events.jsonl`, `status.json`) | bare 8, composed 6 (a strict subset) |
| Canonical sibling at the base, unpatched | one | 8 |
| Sibling at `5b5699e500^` | one | 8 |

`coordination_branch == mission_branch` is the real shape (48 of 50 coordination Missions
in this repository), so a composed directory on it rides to the target. 0 of those 50
Missions has a bare primary directory; the shape exists in hand-built fixtures and,
*hypothesis*, legacy Missions (see #2463). The fixture mocks the `done` bookkeeping, so
where `done` events land is unmeasured.

**Operator ruling (2026-10-05): alias plus fold to one directory.** The target ends with
one directory, the primary one, holding the complete event log.

### 9.3 Authority location and consumers (design input)

- Extend `src/specify_cli/missions/_read_path_resolver.py` (owns `_compose_mission_dir`
  :194, `coord_feature_dir` :218, `read_primary_meta` :825). Compose only through
  `lanes/branch_naming.py::coord_mission_dir_name` (:645). Not in `mission_runtime`:
  resolving `mid8` there would grow the shrink-only outbound ledger in a gate file this
  mission may not edit.
- `mission_runtime/artifacts.py:508-509` stays untouched. `coordination/coherence.py`
  (`is_coord_residue_churn`, `is_status_state_path`) gains an optional collection of
  directory names; it stays pure, the caller passes names in.
- `commit_router.py`: resolve once in `_group_files_by_partition` (:1036), thread through
  `partition_for_mission_path` (:968) and `_representative_kind_for_bucket` (:928).
- `phase_bookkeeping.py:567` and `bookkeeping_projection.py:424/467/506`: *hypothesis*
  that a bare-slug Mission projects nothing today. Convert only with a red proof.
- `phase_teardown.py:393`: read `run.target_feature_dir`, as `:127`, `:502` and
  `run_state.py:455` already do. No alias needed.
- Second classifier caller `acceptance/__init__.py:451` is left alone (follow-up).

### 9.4 Refused-seed backstop shape

`seam.write_dir(...)` returns a `WriteLocation` whose `.seed` is the `SeedReport`
(`mission_runtime/write_location.py:75-101`); `_resolve_run_status_dir` discards it
(`entry_preflight.py:452`). Today a refusal is visible only as warning text
(`coord_seed.py:657-661`). Add a defaulted structured field to `SeedReport`, set at
`coord_seed.py:655`; refuse with exit 1 and `COORD_SEED_COMMIT_REFUSED`
(`consolidation/_constants.py`). The existing "aborted before any state change" wording
is untrue here because the seeded files exist. I-SEED-10 is not contradicted: nothing is
deleted and the retry on the next coordination write still works.

### 9.5 Track B and C corrections

- Under 40 CPU burners the old absolute test still passes (2.18 to 2.29 s), so that load
  level proves nothing; the control needs a start-up floor of at least 1.9 s.
- A fixed 0.5 s planted sleep gives a ratio of only about 1.65 to 1.77 on a 1.9 s floor
  (arithmetic, not measured); the plant must scale with the machine.
- 15 owned runs cost about 21 s today; interleaved floor samples add 5 to 15 s.
- A count assertion cannot carry the `performance` marker; the existing git-count test is
  in `tests/integration`, which is nightly-only.
- Moving the recipe gate: `select_gates` picks the architectural jobs for every
  `src/specify_cli` path tried; no battery seed is needed (10 of 247 files untimed against
  a 10 percent tolerance). The moved file needs the `architectural` marker and its
  `parents[4]` path anchor changes.
- Recipe shapes the first rule missed: `git commit && git push`, `git commit;`,
  `git commit <path>`, a backslash continuation, `git -C <dir> commit -m`.

## 10. One-directory mechanism probe (2026-10-05)

Design probe by the architect lens after the tasks phase; in-memory patches, no repository
edits.

### 10.1 Phase order of one consolidation (`consolidation/executor.py:362-384`)

1. `entry_preflight._resolve_run_status_dir` (called at `executor.py:487`) seeds
   `kitty-specs/<slug>-<mid8>/{status.events.jsonl,status.json}` and commits them on the
   coordination branch, which is the mission branch.
2. `_phase_merge_lanes`, `_phase_baseline_and_surface`, `_phase_bake_and_pre_target_done`
   (`phase_advance.py:335`); `done` events go to the composed log.
3. `_phase_mission_to_target` (`phase_advance.py:535`) fixes the landed tree: the
   mission-branch tip, squashed in `lanes/consolidation.py` (owned by a running mission).
4. `_phase_capture_and_baseline`, `_phase_record_done_and_project` (union into the primary
   directory, working tree only; `bookkeeping_projection.py:309-353`),
   `_phase_porcelain_invariant`, `_phase_commit_and_assert` (`phase_bookkeeping.py:602`,
   the bookkeeping commit on the target).
5. `_phase_reconcile_before_teardown`, then teardown. The squash gate reads the net diff
   `window_base..target` after step 4 (`reconciliation.py:1083`, `:1122`).

### 10.2 Probe results

| Patch | Strategy | Result |
|---|---|---|
| Fold on (composed status pair removed in the bookkeeping commit) | squash | 1 passed; one directory on the target; 8 event-log lines |
| Fold off | squash | reconciliation FAILED and rolled back |
| Fold on, no alias leg in `_is_bookkeeping` | merge | FAILED (the per-commit axis flags the seed and fold commits) |
| Fold on, with the alias leg | merge | passed |

When the gate failed after the deletion commit, `main` was restored by the existing
rollback.

### 10.3 Notes

- The reproduction mocks `commit_merge_bookkeeping`
  (`tests/integration/test_merge_lane_planning_data_loss.py:410`, inside
  `_real_merge_external_mocks`), so the bookkeeping commit, and with it the fold, never
  runs inside that test. The one-directory end state is pinned by a sibling test that
  restores the real door.
- The existing door stages a tracked-but-missing file as a deletion (`git add --force --
  <path>` then `git commit --only`). The comment at `phase_bookkeeping.py:622-624` says the
  door hard-fails on a missing path; that describes a never-tracked path. The implementer
  confirms this on the tree.
- Not verified by the probe: that the composed paths pass `_capture_merge_snapshots`'
  trusted roots; that unmocked `done` events take the same path; that the porcelain
  invariant is unaffected; whether other coordination-kind files exist under the composed
  name in practice.

## 11. Test-design scrutiny of the reproduction's mocks (2026-10-05)

Measured by the paula-patterns lens on base `9adc68803f` after an operator steer:
"changing a mock is allowed and not considered 'tampering' with a test. I do find it
suspect the helper was mocked to begin with. Best scrutinize the test design." The raw
probe runs are in the session scratch directory (`scratchpad/mocks/`), not in the
repository.

### 11.1 What the shared helper removes

`_real_merge_external_mocks` (`tests/integration/test_merge_lane_planning_data_loss.py:400-446`)
patches 11 names, and the reproduction adds 2 inline. Everything it still patches is
in-process product code and git; the truly external patches were removed in `4fd166f1e1`.

| Removed by the patch | Patched name |
|---|---|
| The `done` record | `done_bookkeeping._mark_wp_merged_done`, `_assert_merged_wps_reached_done` |
| The bookkeeping commit door | `commit_merge_bookkeeping` |
| The porcelain invariant | `phase_bookkeeping._classify_porcelain_lines` |
| Both durability asserts (per test) | `_assert_merged_wps_done_on_target`, `_assert_baseline_merge_commit_on_target` |
| Nothing (0 calls) | `post_merge.stale_assertions.run_check` |

A real-door helper already exists in the same file: `_real_bookkeeping_commit_external_mocks`
(`:911`, #2934). It still short-circuits `_classify_porcelain_lines` (`:931`).

The reproduction as written asserts only exit 0. With its mocks it would go green with two
status homes, zero `done` events and a dirty root checkout.

### 11.2 Bare-slug reproduction variants (partition and teardown fixes applied)

| Variant | Strategy | Result |
|---|---|---|
| Real door, real `done`, fold, no `_is_bookkeeping` change | squash | PASS; one directory on the target; 1 `done` event (9 log lines); clean checkout |
| All 13 patches removed, fold, no `_is_bookkeeping` change | squash | same as above |
| Real door, real `done`, fold, no alias leg | merge | FAIL; three commits flagged by the per-commit axis: the seed, the fold, and `chore(spec-kitty): status transition WP01` (the real `done` event written to the composed directory) |

### 11.3 Canonical siblings and the shared helper

| Change | Result |
|---|---|
| Make the shared helper real | breaks `test_malformed_retention_value_is_treated_as_retaining` (unmocked: `DESTINATION_REF_NOT_FOUND`) and at least 9 tests in `tests/consolidation/test_merge_divergent_end_to_end.py` |

Out of scope here; filed as a follow-up. Only the reproduction switches helper.

### 11.4 Related finding

`_planning_prefix` (`reconciliation.py:2055`) returns a
`.worktrees/...-coord/kitty-specs/<slug>-<mid8>` path that no commit can contain, so the
existing prefix leg (`:1239`) is dead under coordination topology (comment at
`:1227-1236`). Not changed in this mission: fixing it would exempt the whole composed
subtree and touches more than `_is_bookkeeping`. Follow-up.

### 11.5 History of the mocks

| Commit | Date | What it did |
|---|---|---|
| `2628226fb4` | 2026-04-26 | "exercise lane-planning data-loss path with REAL git, not mocks": introduced the helper family |
| `1a15bcf6c1` | 2026-07-26 | #2934: added `_real_bookkeeping_commit_external_mocks`, the real-door helper |
| `4fd166f1e1` | 2026-08-25 | dropped the patches of deleted external seams (dossier push, mission-closed, diff summary) |
| `836451fd3f` | 2026-08-31 | #3131 merge retention: the retention tests that use the shared helper |
| `52d36a1bc2` | 2026-10-04 | kept the bare-slug reproduction in the integration suite |
