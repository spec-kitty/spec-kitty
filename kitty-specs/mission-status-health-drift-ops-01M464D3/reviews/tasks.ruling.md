# Tasks phase rulings (operator, 2026-10-06)

The tasks squad confirmed 11 findings; three were forks. The operator ruled:

1. **TASKS-COVER-001: remedy A.** The pin test for the sole legacy-shape literal of the drift reader goes into WP07 with one subtask line naming it. The camel-case enum plant is named concretely in WP04 or WP05 (T018/T023) or WP06 (T028). "AC-VERSION e" is dropped from WP06's ownership sentence for the parts WP06 does not carry.
2. **TASKS-SEQ-001: remedy B.** Before each dispatch the orchestrator fast-forwards `kitty/mission-<slug>` and merges the planning branch into the lane workspace, then greps the record (Step 0, J-1, hand-off) inside the lane workspace. WP10 (lane-planning) works in the planning branch itself. Written as an orchestrator step in `tasks.md`. `--refresh-planning-commit` is not used.
3. **TASKS-VERIFY-002: remedy A, strengthened.** The battery legs are named concretely (job names, selection expression, shard split) with a pointer to the Step 0 per-leg main-run durations. The operator wants the full architectural battery run locally on WP03, WP07 and WP08, as on #5625: it is a binding gate in those work packages, not conditional. This replaces the plan's "CI-owned, not run locally" default for those three work packages.

The ruling replaces the acceptance bar for these three findings. No mutating `finalize-tasks` is run after the orchestrator block is in `tasks.md`.

## Orchestrator note 15 (TASKS-FRESH-005, within ruling 3; for the operator to overturn if wished)

The battery legs run locally are compared with the local run of the same legs on the unchanged D-0 tip (Step 0 item 2), not with the main-CI durations. The per-leg main-CI durations (Step 0 item 3) are recorded for information and for sizing the local run, and carry no pass rule. The local legs do not add the CI `collect_universe_prestep`; the Step 0 local baseline and the work package run use the same commands, so they are comparable with each other.

## Orchestrator note 16 (TASKS-FRESH2-004, within ruling 3; for the operator to overturn if wished)

The three remedies named by the finding are compatible and are combined. The battery legs are started as a background command and awaited with the harness's permitted wait primitive (a background run plus an until-loop monitor), never a foreground sleep loop; Step 0 probes once that the primitive is available to a work package worker; if it is not, the orchestrator runs the three legs for that work package on the lane tip and puts the result in the hand-off, binned the same way.

## Orchestrator note 17 (TASKS-FRESH3-001, extends ruling 14; for the operator to overturn if wished)

The Step 0 full-battery baseline run on the unchanged D-0 tip, and the orchestrator-run fallback of note 16, are the same battery gate as ruling 14 applied at the points that make it comparable; they are recorded here as an orchestrator note, not attributed to the ruling's text.

## Orchestrator note 18 (TASKS-FRESH3-004; for the operator to overturn if wished)

The CLI used by the cutover-guard commands is a placeholder `<synced-spec-kitty>`, defined once in Step 0 next to `<synced-python>` (the CLI of the synced environment, checked to resolve into the workspace under test), replacing the literal `.venv/bin/spec-kitty` that a lane workspace does not carry. The bare `spec-kitty` and a path into the primary checkout are not used.

## Orchestrator note 19 (analyze finding C1; for the operator to overturn if wished)

The oracle module of WP09 is the first importer of `src/specify_cli/audit/classifiers/status_json.py`, so by the rule of Registration item 4 ("the commit that first imports the file") WP09 owns the one `ci-router.yml` glob entry for it, in the commit that first imports it. `ci-router.yml` is already in the lane write scope and in `SLICE_ALLOWED`; the plan's declared shared-file exception (3) is read as including WP09 for this one entry. The alternative (adding the glob in WP07 or WP08, before any importer exists) was not taken because it contradicts the same rule.

## Numbering

The rulings of this phase are numbered 12 to 14 in `tracer-design-decisions.md`; "ruling 1/2/3" above are rulings 12/13/14, and the orchestrator notes are 15 to 19.
