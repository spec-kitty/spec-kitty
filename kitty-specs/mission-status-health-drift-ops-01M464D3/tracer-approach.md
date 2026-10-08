# Tracer: Approach

Mission: `mission-status-health-drift-ops-01M464D3` (#5776). Seeded at the plan phase (2026-10-06); appended by the orchestrator between dispatches, assessed at close by IC-10 (append-only; work packages report, they do not write this file).

## Plan of attack (spec phase)

1. The last read slice of the Mission Status contract, read-only, in the same unreleased release: five properties on `Project`, a drift read (three kinds), an Ops read; `info.version` stays `1.0.0-SNAPSHOT`; the proof is a reference reader, the reality check over this repository's own `kitty-specs/` and `kitty-ops/`, and the additive proof against `main`.
2. The binding record is the operator rulings OR-1 to OR-10 and rounds 2 to 5 (`tracer-design-decisions.md`); the spec closed after five fix rounds.
3. No file under `src/` changes (C-006); anything the resolver does that changes no observable contract outcome is an assumption (spec R-9), never a rule or a task.

## Plan phase (2026-10-06)

- **A-1 Plan run.** `spec-kitty agent mission setup-plan --mission mission-status-health-drift-ops-01M464D3 --json` was run once (`scaffold_only: true`); `plan.md`, `research.md`, `data-model.md`, `quickstart.md` and `contracts/` were written by hand from the measurements in research R-1 to R-14. The command is not run again (a second call auto-commits and the orchestrator owns commits).
- **A-2 Measure before deciding.** Every decision the plan settles has a command that was run: the corpus counts and the fallback agreement (R-2, R-3), Gate B and the no-op (R-4), the additive proof on a spike with the pinned `oasdiff` (R-5: lowered-major `breaking=4 provisional_changes=1`, same-major `BREAKING_WITHOUT_MAJOR` x4), the baselines of the gate set (R-6), the router placement (R-7), the lanes (a scratch `compute_lanes` run: `lane-b` {IC-02}, `lane-a` {IC-01, IC-03 to IC-09}, `lane-planning` {IC-10}).
- **A-3 Shape.** One pull request, ten concerns in order of risk: re-measure and campsite (IC-01), tool extension (IC-02), the `Project` vertical (IC-03: the only change to an existing response, with its ratchet edits), the drift and ops contract slices (IC-04, IC-05), the contract proof edits (IC-06), then the JVM replay J-1, then the drift reader (IC-07), the ops reader (IC-08), the oracles and the reality extension (IC-09), the close-out (IC-10). Wrap-up W-1 to W-7 is the orchestrator's.
- **A-4 Floors.** Fixed at plan time below the measurement by one rule (95 percent rounded down to two significant figures; counts under 100 at 90 percent rounded down), never re-pinned: Missions 540, Ops served 440, spine-closed 5, evidence none 330 / absolute 28 / free text 50 / relative 25, kind-1 findings 39, kind-2 findings 27. **No kind-3 floor and no fallback floor.**
- **A-5 Two facts the spec did not know.** (1) The two gates that guard a new module's registrations (`test_same_tier_uniqueness.py`, `test_corpus_blocking_home.py`) cannot run in the hand-built checkout `.venv` (`respx` missing), so the registration pairs are unverifiable locally until an environment is synced. (2) `origin/main` has moved 133 commits since the base, including files the reference reader imports; the D-0 sync is the first dispatch step.
- **A-6 Spec edits of this phase (the only ones allowed).** The two AC-REALITY bullets that lacked their own reachability condition now state it (they hold with the remotes reachable and the corpus condition of FR-025; offline they take a named skip and an offline run is not evidence for SC-002 or SC-007); the single-listing wording is reworded in the spec's clarification, in FR-012 step 4, in the AC-DRIFT row and in `tracer-design-decisions.md` ("at most one `git for-each-ref refs/heads` listing, run once when the first Mission with an expected lane needs it"); a grep for the old phrase finds nothing in either file. Six inconsistencies found while planning are in the plan's "Departs from the spec" and are not edited into the spec.

## Record-keeping and write scope

No code work package has a file under `kitty-specs/` in its write scope. What a work package records (a refinement of a contract note, a floor re-measure, a friction observation) goes into its hand-off report; the orchestrator appends it add-only to the right tracer file between dispatches (never while IC-10 is in progress). IC-01's records (the D-0 sync result, the kind-3 re-measurement under the final rule, the Gate B and no-op re-check, the baseline in a synced environment) are appended here under their own headings.

## Re-measurement owed (spec: "Re-measurement owed (reality check)")

To be filled by the orchestrator from IC-01's report: the kind-3 counts under the final rule (non-completed Missions with a current-shaped manifest, with an expected lane, with a missing expected local branch; by lifecycle state; coordination branch versus `mission_branch`; the legacy count), and whether the honest-rule criterion looks reachable. **No kind-3 corpus floor is pinned from it.**

## Wrap-up records to fill (also in `tracer-design-decisions.md`, "Wrap-up records")

- W-1: the strategy of `consolidate`, the resulting `HEAD`, the scope check and add-only outputs.
- W-4: the aggregate squad's verdict and what was folded.
- W-5: measured diff size per group (threshold in the plan).
- W-7: the final evidence list of the plan.

## Close-out assessment (IC-10)

To be written at close: what held, what the plan got wrong, what the next Mission should do differently.

## Plan-round spec edit (2026-10-06, add-only record)

- **A-7 Spec edit by operator ruling (supersedes the "no other spec edit" clause of A-6).** `spec.md` AC-REALITY bullets 2 and 3 and the FR-025 "Corpus outcome" sentence said that offline the whole of bullets 2 and 3 takes a named skip. By operator ruling (plan round, 2026-10-06) they now say that offline only the assertions that depend on the coordination resolver (the project-wide report equality with the oracles, Missions examined-plus-skipped and Missions floors, the kind 1 to 3 oracles, the fallback list, per-Mission equality) take a named skip; the Ops walk, the `skippedCount` equality, the Ops floors and the read-only fingerprints need no network and run in every environment. The named-skip rule and "an offline run is not evidence for SC-002 or SC-007" are kept. The plan's "Departs from the spec" item 5 is reworded as an explicit departure that this edit resolves. The new "Operator rulings (2026-10-06, plan round; binding)" subsection of the spec Clarifications lists rulings 1 to 7.
- **A-8 Plan-round fixes (2026-10-06, add-only).** Records of the plan-round rulings 1 to 7 are in `tracer-design-decisions.md` ("Plan-round operator rulings"). Consequences for record-keeping: the D-0 sync result, the synced environment and the baseline (including the median durations of the two corpus-related test jobs on `main`) are recorded by the orchestrator at Step 0, before any dispatch, under their own heading here (IC-01 no longer takes them); IC-01 keeps the re-measurements and the campsite. One floor was added by the ruling that moved the corpus-sized cases into the reality module: the completion-equality guard of AC-DRIFT 19, `completion_non_coord` 490 (of 518 Missions declaring no coordination branch), beside the floors of A-4. The wrap-up order is the procedure's except that consolidation precedes the squad; the terminal verdict for #5776 follows the squad.
- **A-9 Round 2 plan fixes (2026-10-06, add-only).** The offline classification of the corpus-sized cases (resolver-dependent skip applies to the one-`Project`-build, one-scan and combined timing cases; the AC-DRIFT 19 completion equality and the real `kitty-ops/` listing bound run offline) is stated in `plan.md` (Departs 5, Reality-check design notes, IC-09) and added to the `spec.md` Plan-round 4 clarification, consistent with ruling 1. The `completion_non_coord` 490 floor is added to the `spec.md` FR-025 floors bullet. The spec cross-reference of the Plan-round 1 clarification now cites A-7 (it cited A-6). The plan's timing decision is renamed D-P16 (the spec's D-P15 is the floors rule); `plan.md`, `research.md` and the decision register use the new id.
- **A-10 Plan round 4 fixes (2026-10-06, add-only).** Plan-round rulings 8 to 10 (proxy threshold about 70 s local, cache-the-result in the AC-CROSS 4 row and IC-09, combined case and job gain as different quantities) are recorded in `tracer-design-decisions.md` and in the plan-round Clarifications of `spec.md`; no requirement text changed.
- **A-11 Plan round 5 fixes (2026-10-06, add-only).** Orchestrator note 11 (escalation line stated against the job-gain sum, about 55 s local for the combined case alone) and the D-P5 arithmetic recomputed from its components (55 to 75 s local, 94 to 128 s CI) are recorded in `plan.md`, `tracer-design-decisions.md` item 11 and `reviews/plan.ruling.md` note 11; `spec.md` is unchanged.

## Record: Step 0

Recorded 2026-10-06 by the orchestrator's Step 0 seat. Add-only.

- **D-0 sync.** `git fetch origin`; `origin/main` = `abafc135e353bb44d001c3144f5a8316708ebf1c`, 134 commits ahead of the planning tip `3d119bbbb`. `git merge --no-ff origin/main` (no rebase) into `issue-5776-mission-status-contract-health-drift-ops`: no conflicts. D-0 merge commit (planning-branch tip before this record): `60df1da11fe040c505898bc4f12eeb81b720ac98`. Symbol check of the quickstart: `checked=91 missing=0`.
- **Upstream delta classified (files of R-1).** `contracts/` and `tests/contract/` mission-status files: unchanged (only `test_feature_alias_scope.py`, `test_no_selector_guard.py`, `test_terminology_guards.py` moved, +7 -1 lines, terminology guards). `ci-router.yml`: one `setup-uv` pin; `contract_tools` group unchanged. `surface_resolver.resolve_declared_mid8`: the first two tiers now delegate to the new shared `missions._read_path_resolver._declared_mid8` (#5751; same derivation, `mid8` then `mission_id` through `resolve_mid8`; the third-tier slug-tail guess is kept); new `mission_dir_aliases`, `mission_metadata.recorded_mid8`, `coordination/planning_commit.py`, `ensure_wp_claim_preconditions`, `claim_policy_metadata`, `workspace.context.find_wp_file`/`resolve_lane_state_dir`/`resolve_mission_target_branch`. No observable change of the resolver outcome for a declared identity was found by reading the diff; the corpus tests below are green on the tip. Not reported as an R-9 resolver change.
- **Synced environment.** `UV_PROJECT_ENVIRONMENT=<scratch>/venv uv sync --frozen --all-extras` (uv 0.11.28); `<synced-python>` = `<scratch>/venv/bin/python` (Python 3.11.15), `<synced-ruff>` = `<scratch>/venv/bin/ruff` (0.15.12), `<synced-spec-kitty>` = `<scratch>/venv/bin/spec-kitty`; mypy 1.20.2, respx 0.23.1. Import check: `specify_cli.__file__` is inside the workspace `src/` (no `PYTHONPATH` needed from the planning checkout). `<scratch>` is the session scratchpad; `TMPDIR=<scratch>/tmp` (a stray `.git` directory in the system temporary directory exists).
- **Gates on the D-0 tip, `<synced-python>`.** `ruff check .` pass; `ruff format --check .` 3324 files formatted; `ruff check --select TID251 .` pass. Census roster files + `test_layer_rules.py` + `test_pyproject_shape.py` + `test_archive_root_byte_identical.py` + `test_no_legacy_terminology.py`: 387 passed (100 s). Contract tools: layout 0, citation 0, provisional 0 (22), example 0 (75/75), event_mapping 0, enum_pin 0 (7/43), leak_scan 0, structure 0, codeowners 0, no_pytest_scan 0. Tool/reader tests (quickstart set): 546 passed (149 s). `-m "corpus and not windows_ci"` reality + payloads: 824 passed (110 s). The 17 plan-time registration-gate errors are gone.
- **Battery baseline (ruling 14 extended by notes 15, 17; same commands as WP03, `PWHEADLESS=1`, `-n 4 --dist loadfile`, venv bin first on PATH, run one leg after another, 24 cores).**
  - `architectural-fast`: 786 passed, 1 skipped, 0 failed; exit 0; 80 s wall (pytest 78.9 s).
  - `architectural-heavy 1/2`: 1736 passed, 2 xfailed, 0 failed; exit 0; 187 s wall (pytest 185.2 s).
  - `architectural-heavy 2/2`: 1431 passed, 2 skipped, 1 failed; exit 1; 155 s wall (pytest 155.3 s). Red: `tests/architectural/test_lifted_cli_accept_birth_cutover.py::test_accept_stamp_idempotent_rerun_is_byte_identical`, bin ENVIRONMENT (the placement port resolved the primary home to a `kitty-specs` path under the system temporary directory because of the stray `.git` directory in the system temporary directory; `PlacementMismatchError`, fail-closed). `test_regenerate_graph_check_is_byte_identical` passed (venv spec-kitty first on PATH).
  - Junit files and logs are in `<scratch>` (`xunit-*.xml`, `leg-*.log`, `leg-*.exit`, `leg-*.secs`).
- **Main CI record (item 3; latest successful `ci-router.yml` run on main, 37423121001, informational only, note 15).** `architectural fast gates` success 237 s; `architectural battery (heavy) 1/2` success 766 s; `2/2` success 473 s; `terminology guard` 168 s; `layer rules` 166 s; `archive freeze` 159 s (each success). Median of the last five successful runs of `tests (corpus-blocking)` (305, 317, 362, 364, 402 s): 362 s; of `tests (contract tools)` (289, 304, 414, 453, 471 s): 414 s.
- **wait-primitive: permitted** (a trivial background `sleep 5` with exit-code file, awaited with an until-loop Monitor from this seat, completed and notified; the three battery legs were awaited the same way).
- **Kind-3 re-measure:** not listed in Step 0 (it is IC-01's first task under the final rule); not run here.
- **Ruling 14 extension (orchestrator addition, 2026-10-06).** The local architectural battery (three legs) of ruling 14 is EXTENDED to WP09, because its `ci-router.yml` edit can select the battery; same override of `NO_FULL_HEAVY_SUITES_IN_MISSION` for those runs. WP09's prompt carries the section "Architectural battery: BINDING local gate". Binding set is now WP03, WP07, WP08, WP09.
- **Step PD.** Lane workspaces do not exist yet (they are created by the first `agent action implement`). No lane worktree exists (`git worktree list`: only the planning checkout) and the mission-lane branch `kitty/mission-mission-status-health-drift-ops-01M464D3` did not exist; it is created from the planning branch tip right after this record's commit (item 2). Lane workspaces are created by the first claim (WP01 for lane-a, WP02 for lane-b); the orchestrator then runs items 3 and 4 (merge and grep) before starting the worker.
- **Not done here (outward actions left to the orchestrator):** assign #5776 and post the claim comment.

## Record: IC-01 operator ruling on D-P6 (2026-10-06)

The IC-01 re-measure found 93 kind-3 findings over 574 Missions (146 not completed, 119 with a current-shape `lanes.json`, 94 with an expected lane). Every one is the class "lane branch and Mission-level branch both missing", because this clone holds no local `kitty/*` heads except this Mission's own. T001 step 3 sent the point to the operator.

**Ruling: the honest-rule criterion is met; kind 3 stays as planned** (provisional, no corpus floor, corpus asserted equal to the oracle). Reason: the branch-missing test is independent (one `git rev-parse --verify --quiet` per expected name, asserted equal to the reader's single listing). Only completion and snapshot membership are shared, which D-P6 allows. The dominant class reflects the clone's ref set, not a shared construction.

IC-01 also measured: Project proxy about 37 s to 39 s local, combined sum about 38 s to 39 s (under the 55 s and 70 s lines); every floor below its re-measure. Open for the wrap-up: `spec-kitty cutover-guard --base-ref origin/main` exits 1 on this Mission's own directory (`status_phase` not flipped). It reproduces without any WP diff, so it is classified as pre-existing Mission state, to be resolved before the PR.

## Record: Hand-off WP01 (0ec1e852c)

Approved at review cycle 1. Campsite: four literals hoisted in the 1.1 proof module, 118 test ids identical. The re-measure is in the D-P6 record above: kind-3 93, kind-1 44, kind-2 30, completion equality 523 compared and 0 disagreements, every floor below its re-measure. Timings from the primary checkout: resolver about 34.6 s cold, Project proxy 37.0 s, combined sum about 37.8 s, under the 55 s and 70 s lines. Gate B holds. `cutover-guard --base-ref origin/main` exits 1 on this Mission's own `status_phase` (pre-existing, handled at the wrap-up).

## Record: Hand-off WP02 (89d04044c)

Approved at review cycle 1. Six strict names added to the contract tools (`specKittyVersion`, `currentBranch`, `profileId`, `action`, `invocationId`, `sourceCode`), with six `leak-scan-strict-*` negative cases; the kinds count goes from 34 to 40. Manifest `cases=133 ran=100 skipped=33 failed=0`. `mypy --strict` is clean on the contract tools, and all ten contract tools exit 0. Wrap-up campsite items: a test name still says "ten names", and the `fixture_builder.py` docstring still says "34 kinds" and "ten strict".

## Record: Hand-off WP03 (90ff8a07b)

Approved at review cycle 2. Adds the `Project` schema, `ProjectHealth`, two examples, the memo and the builder (`build_project(repo_root, memo, *, leak)`, whose `ProjectOutcome` carries `fallbacks`). Cycle-1 fixes: `OverflowError` is caught in both version parse paths (with a `.inf` plant), the reality-test timeout is back to 120 s, the redundant shape guard is dropped, and the three deferred gaps are asserted. Five router globs were added. Ten of ten mutants were killed. NFR-009 from the primary checkout: 574 Missions, 37 fallbacks, 35.9 s cold and 16.8 s warm, under the 120 s bound; a lane worktree shows 516 fallbacks, which is a worktree artefact. Breaking check `breaking=4 provisional_changes=1`, as expected. Battery: fast 786 passed, the heavy legs equal to Step 0 (the known environmental red only). Wrap-up campsite item: the builder module docstring still describes the dropped shape check.

## Record: Hand-off WP04 (f5ead414e)

Approved at review cycle 1. Contract-only drift read: `DriftReport`, `DriftFinding`, `DriftRefusal`, `DriftKind` (three values), `LaneComparison`, the path, the 500 and 422 responses, the parameter, six examples and six enum pins. Tool counts: layout `path_files=9 index_files=7`, citation `properties=213 x_source=147 x_derived=66 inputs_resolved=121`, provisional 29, example 97/97, enum_pin `enums=14 values=57`. The negative runner gives 100 passed. The breaking check against abafc135e is unchanged (`breaking=4 provisional_changes=1`). `MIN_EXAMPLES` went from 47 to 64 (58 example files plus 6).
Refinements ruled acceptable at review:
- `DriftFinding.artifactPath` uses `x-derived` like `ArtifactEntry.path`, because `ArtifactPath` carries its own `x-derived` and an `x-source` beside the ref is BOTH_CITATIONS. The spec's field catalogue row is stale on this point (see the design-decisions record).
- `summary` stays a plain string holding the six sentences.
- `derived_view_stale` follows FR-013.
- `truncated` is provisional.
- An out-of-map two-line edit adds `DriftReport`/`DriftRefusal` to the `old_schemas` prefix tuple of the 1.1 proof module, the same kind of edit WP03 made. WP05 needs the same for the Ops schemas.
Carry-forward for WP06: assert the CHANGELOG `info` and non-null statements, and scope the "1000" and "not evaluated" checks to their heading (WP04 checks the whole entry).

## Record: Hand-off WP05 (bb1cc6a43)

Approved at review cycle 1. Contract-only Ops read: ten schemas, `paths/ops_invocations.yaml`, `OpsProfile`, `OpsUnreadable`, 13 examples, six enum pins, the `/ops/invocations` key and the `Ops` tag. Tool counts: layout `path_files=10 index_files=7`, citation `properties=234 x_source=158 x_derived=76 inputs_resolved=143`, provisional 34, example 124/124, enum_pin `enums=20 values=72`. The negative runner in the lane gives `cases=133 ran=100 passed=100`. The breaking check against abafc135e is unchanged (`breaking=4 provisional_changes=1`). `MIN_EXAMPLES` went from 64 to 77. The battery equals Step 0.
Rulings at review:
- `OpsInvocation` has 13 members, all required, 7 of them nullable, per spec FR-017 and data-model.md. "Twelve" in `contracts/operations-and-schemas.md` and in the WP05 T024 text is a miscount (see the design-decisions record).
- The 1.1 proof module gained three prefixes (`OpsInvocationPage`, `OpsInvocation`, `OpsRefusal`), the same kind of edit WP03 and WP04 made.
- The tag list, the drift `[-2]` index, `EXPECTED_PATH_KEYS` and the pin counts were extended, not loosened.
Carry-forward for WP06: `OpsEvidence.kind`, `.value` and `.redacted` cite the bare `OpCompletedEvent`, where the spec table gives `OpCompletedEvent.evidence_ref`; fold the two-token citation fix into WP06's proof edits. The WP04 carry-forward (the CHANGELOG `info` and non-null assertions, and the heading scope) also stands.

## Record: Hand-off WP06 (47c18d11c)

contracts-commit: 47c18d11ca258c065e925e52b859a093ccd8603c

Approved at review cycle 1. Proof edits in the 1.1 module: frozen pre-slice copies of `Project` (cmp-identical to abafc135e), the masked bundle-pair comparison (the title-gated inline mask is the exact D-P10 equivalent, because the resolved tree has no `components`), the four qualified provisional names, `ADDED_STATEMENTS` scoped to Added (`info`, non-null, 1000, not evaluated), the provisional count pinned at 34, `SLICE_ALLOWED` with 15 rules (0 problems and 0 unused rules over the real diff), `dependency_problems`, and the 13-member `OpsInvocation` pin. The contract edit is the `OpsEvidence` citation fix (`OpCompletedEvent.evidence_ref`, three lines). Breaking check: lowered-major gives `breaking=4 provisional_changes=1`; same-major gives BREAKING_WITHOUT_MAJOR naming exactly `currentBranch`, `lastActivityAt`, `schemaVersion` and `specKittyVersion`. The battery equals Step 0.
Notes for the wrap-up: the D-P10 revert-Project control must also remove the new `/drift` and `/ops/invocations` operations (otherwise same-major exits 1 with BUNDLE_CHANGED_VERSION_SAME, not the 0 the plan states). An optional strengthening asserts that `Project` minus its five new properties equals the frozen copy.

## Record: Hand-off WP07 (80744935c)

Approved at review cycle 1. The drift reader is `tests/contract/_mission_status_drift.py`, with 61 tests (38 rows, 14 killed mutations, the T056 pin with its plants) and the registration pair. Five router globs were added (`coordination/workspace.py`, `git/remote_probes.py`, `status/lifecycle.py`, `core/paths.py`, `lanes/models.py`). 49 revert experiments were run; three redundant guards were removed and re-proved. From the primary checkout the corpus answers 200 with 167 findings (kind 3 93, kind 1 44, kind 2 30), 37 fallbacks, one legacy manifest and `truncated` false. That equals the IC-01 re-measure, and the floors are met. Timing: 37.7 s cold and 17.11 s warm, a margin of about 83 s against the 120 s bound owned by WP09. The battery equals Step 0. Row 14 pins the resolver's real offline behaviour (200, no fallback), as the operator ruled; the contract prose is fixed by the WP04 rework.

## Record: Hand-off WP04 (0d070a3a1)

contracts-commit: 0d070a3a10f89ed9df8366f79cb55102cf80b9bb

Rework approved (review cycle 2). The contract prose (`DriftReport.yaml`, `paths/drift.yaml`, CHANGELOG) now states the operator ruling at WP07: an unreachable remote leaves the Mission's own directory (200, no fallback entry), a clean miss on a reachable remote gives the `coordination_branch_deleted` fallback, and other resolver errors are a 500. Descriptions only; the breaking check against abafc135e is unchanged (`breaking=4 provisional_changes=1`). The review verified on real repositories that a branch present only on a remote, or only as a remote-tracking ref, also resolves to the own directory with no fallback. The spec, plan, planning contracts and the WP04, WP07 and WP09 prompts are amended to match. The J-1 replay repeats for this contracts commit.

## Record: Hand-off WP08 (ff07fca15)

Approved at review cycle 2. The Ops reader is `tests/contract/_mission_status_ops.py`, `list_ops(repo_root, *, tools, profile, page_size, cursor, fs)`, returning `OpsOutcome(status, body, skipped_ids, skip_reasons)`. It has 155 tests, 17 mutations all killed, and the registration pair. Three router globs were added (`invocation/errors.py`, `record.py`, `writer.py`). The seam is `stat`, `scandir` and `open_binary`. The cursor is base64url JSON whose digest covers the filter. A bad `pageSize` or `profile` gives a 400 Problem without a code; a bad cursor gives 400 `invalid_page_cursor`.
Cycle 2 applied the operator rulings at WP08: a bad closure instant skips and counts the Op (`SKIP_INSTANT` for the Op's own line, `SKIP_CLOSURE_INSTANT` for the spine); a credential-shaped `profileId`, `action` or `actor` skips the record (`SKIP_FIELD`), and `actor` is never nulled. Judgment calls the review found settled by the spec: an empty `evidence_ref` is served as text "", the index entry's `profile_id` is not read, and an own `completed` line naming another invocation is ignored (CLI parity).

> Superseded 2026-10-07 by the post-squad operator ruling: `actor` is nullable; a credential-shaped `actor` is served null; a third J-1 replay ran (5dc9cc427).

Timed bounds from the primary checkout, minimum of 7 cold repeats: 256 KiB shapes 15.1 to 18.9 ms against 0.1 s (5.3x to 6.6x), and 10,000 files 0.137 to 0.147 s against 30 s. The battery equals Step 0.

## Record: Hand-off WP03 (8b970f977)

Rework found at the WP09 review and approved at review cycle 3. `build_project` no longer raises `UnicodeDecodeError` for a Mission whose `status.json` is not valid UTF-8. `_mission_activity` catches it (`_UNREADABLE`) and returns None, so the Mission still counts in `missionCount` and adds no activity (FR-002/FR-003: the Project read never raises). There is a red-first plant (an undecodable Mission beside a clean one, with a clean twin) and a mutation `unguarded-activity`. The WP09 `dho_repo` workaround (`undecodable=False`) is removed in the same commit; that is WP09 feedback item 2. Gates: project, payloads and reality give 919 passed and 1 skipped from a shared clone of the primary checkout. The battery fast leg equals Step 0.

## Record: Hand-off WP09 (f021fe87b)

Approved at review cycle 2. The independent oracles are in `tests/contract/_mission_status_oracles.py`, with an AST independence test that also flags `importlib` and `__import__` (3 plants). The reality extension covers Project, project-wide and per-Mission drift and the whole Ops walk, plus named lists, D-P13 floors and fingerprints. There is one `ci-router.yml` glob, `audit/classifiers/status_json.py`. The timed block runs the production resolver index walk (`production_index()`), with a plant that refuses a patched timed run.
Re-measured from a shared clone of the primary checkout: 574 Missions, 37 fallbacks (oracle agrees both ways), 1 legacy manifest; kind 1 44 (43 terminal, 1 provenance), kind 2 30, kind 3 equal to the oracle (93 to 94, clone-dependent, unfloored); completion equality 523 compared with 0 disagreements; Ops 481 files (474 served, 7 legacy-completion skips), 6 closed by the spine; evidence none 352, absolute 32, free text 56, relative 28. Every floor sits below its re-measure.
Timed bounds, unpatched: Project about 18 s, scan about 1 s, per-Mission about 6 s, combined about 25 s, against 120 s; the real `kitty-ops` listing takes 0.012 s against 5 s. The reality module gives 721 passed and 1 skipped online, and 710 passed with the 12 named resolver-dependent skips offline (operator ruling at WP07). The battery equals Step 0. Corpus runs need a clone of the primary checkout, because a lane worktree answers 500 on `/drift` (read directory outside the root).

## Record: Hygiene counts

exempt-count: 43
whole-directory-count: 113

Both counts come from the script in "Hygiene scan of the Mission directory" (`tasks/WP10-closeout-evidence.md`), run unmodified from the repository root with `<synced-python>`, and from its W-5 variant without the exemption. The exempt scan gives `problems=0`. Before the counts were taken, two Step 0 lines that named temporary-directory paths were reworded, since this file is new on this branch. The W-5 variant gives `problems=13`:
- 12 EMAIL hits, 4 each in `reviews/spec-complete.findings.yaml`, `reviews/spec.confirmed.yaml` and `reviews/spec.merged.yaml`, review files that quote leak-pattern examples;
- 1 EMAIL hit in `status.events.jsonl` line 1, the no-reply attribution address of the status log.
All 13 are allowed and noted under the W-5 reading rule.

## Close-out assessment (IC-10, pre-rebase)

Written 2026-10-07 by WP10 (planning artifact, work done on the planning branch). Pre-rebase: the final evidence is W-7. Every figure below is copied from a record above, not re-measured.

**What held.**
- The shape held: one pull request, ten concerns in order of risk, nine code packages approved (WP01 to WP09), lane-a carrying the chain and lane-b only IC-02. The parallel window of IC-01 beside IC-02 produced no conflict.
- Measure-before-deciding (A-2) held. The IC-01 re-measure (record "Hand-off WP01", 0ec1e852c) found every floor of D-P13 below the re-measured value, and the WP09 re-measure (f021fe87b) found the same: kind 1 44 against 39, kind 2 30 against 27, evidence none 352 against 330, absolute 32 against 28, free text 56 against 50, relative 28 against 25. No floor was re-pinned.
- The "no kind-3 floor" decision held. Kind 3 measured 93 in IC-01 and 93 to 94 at WP09, because it depends on which `kitty/*` heads the clone holds. A floor would have been a clone-dependent red.
- The independence of the oracles held: WP09 added an AST independence test that also flags dynamic imports, with three plants, and the corpus comparisons (completion equality 523 compared, 0 disagreements; fallbacks 37 both ways) agree between reader and oracle.
- Additivity held. Every contract package left the breaking check at `breaking=4 provisional_changes=1` (lowered major) and same-major names exactly the four new `Project` properties (WP03 90ff8a07b, WP06 47c18d11c). The J-1 replay passed twice with no red (47c18d11c, 0d070a3a1).
- Timing bounds held with margin: Project proxy about 37 s (IC-01) and about 18 s in the WP09 timed block, combined about 25 s, against 120 s; the Ops bounds 5.3x to 6.6x and 0.14 s against 30 s (ff07fca15). The architectural battery equalled Step 0 in every binding package (WP03, WP07, WP08, WP09); the only red is the known environmental one.

**What the plan got wrong.**
1. The premise "an unreachable remote ends the drift scan in a 500" was false (operator ruling at WP07, `tracer-design-decisions.md`). It was stated in the spec, plan, contracts and three work package prompts, and was only found when the WP07 implementer ran a real repository. It cost a rejection of WP04, a repeated J-1 replay and amendments to six documents (spec, plan, planning contracts, and the WP04, WP07 and WP09 prompts). The plan measured corpus counts but never ran the resolver offline.
2. Two miscounts and one stale citation entered the planning contracts and prompts: "twelve" `OpsInvocation` members (thirteen, WP05), the `DriftFinding.artifactPath` citation (`x-derived`, WP04), and the `OpsEvidence` citation that needed the two-token form (WP06). Each was caught at review, none by a gate before review.
3. Out-of-map edits were needed in every contract package: the 1.1 proof module's `old_schemas` prefix tuple (WP03, WP04, WP05). The plan listed the proof edits as one concern (IC-06) and so mis-sized IC-03 to IC-05.
4. The plan did not foresee that a Project build over a Mission with an undecodable `status.json` raised (found at the WP09 review, fixed in WP03 8b970f977, three review cycles). The fixture-built modules had no undecodable plant, and WP09 had worked around it with a flag.
5. The router-glob count per reader package (five for WP07, three for WP08, one for WP09) was found by the failing import scan, not predicted. Operator ruling 7 had approved the widened set in principle at the plan round.
6. The plan said a lane worktree could host corpus runs. A lane worktree answers 500 on the drift read (read directory outside the root) and shows 516 fallbacks for the Project read instead of 37 (WP03, WP09 records). Every corpus gate needed a shared clone of the primary checkout.
7. Wrap-up campsite debts accumulated and are still open at this point: a test name that says "ten names", the fixture builder docstring ("34 kinds", "ten strict"), and the Project builder module docstring that still describes the dropped shape guard (WP02 and WP03 records).

**What the next Mission should do differently.**
- Run every reality-dependent claim of the spec once before the plan accepts it, in each environment class the spec distinguishes (online, offline, worktree, clone). A one-hour spike on the resolver offline would have saved the WP04 rework and the second J-1 replay.
- Give the proof module one explicit concern per slice, with its prefix tuples and `SLICE_ALLOWED` rules listed in each contract package's map, so the out-of-map edit is not repeated three times.
- Put an undecodable and a non-mapping plant into the first fixture-built reader package, with a clean twin, since the "never raises" requirement is cross-cutting.
- Run the registration gates and the router import scan in the first dispatch for every package that creates a module, and list the expected router globs in the package prompt.
- Keep the wrap-up campsite list in one record from the first hand-off, so that docstring debts are not rediscovered at the end.
- State in the plan which gates need a clone of the primary checkout and name the clone recipe once.

**Open at this point (not for this package).** `cutover-guard --base-ref origin/main` exits 1 on this Mission's own `status_phase`; it reproduces without any package diff (IC-01 ruling record) and is handled at the wrap-up. The W-5 variant of the hygiene scan reports 13 allowed hits (Hygiene counts record).
