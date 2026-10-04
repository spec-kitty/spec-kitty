# Close-out record: Mission Status contract v1

Mission `mission-status-contract-v1-01M3WC5X` (issue #5558, part of epic #5528). Written 2026-10-03 by WP12 (IC-10, part b) as the evidence ledger behind the pull-request bodies.

Sections 15 and 16 supersede earlier text where they differ: section 15 records the maintainer landing of slices 1 to 3, and section 16 records the landing of slices 4 and 5 (2026-10-04). Sections 1 to 14 are an evidence ledger of runs on pre-landing heads and are left as written.

How to read this file. Every claim cites a commit (verified with `git cat-file -t`), a CI run id (verified with `gh run view <id> --json conclusion`), a file path or an issue or pull-request number. A figure that could not be obtained is written "not measured" or "not available" with the reason; nothing is estimated. Commit hashes cited as "lane" are on the code lane branch `kitty/mission-mission-status-contract-v1-01M3WC5X-lane-a` (final tip `c02b14852`); the seam branches were rebuilt from that lane after the pull-request CI fixes, so the same content has different hashes there. Seam 6 (`issue-5558-mission-status-contract-v1-seam6`, tip `e38f59e24`) has a tree identical to the lane tip (`git diff` between them is empty).

Terminology: Mission, never feature; a status lane (a work package's workflow state), a code lane (a git worktree lane) and the repository-root checkout are kept apart.

## Planning-text corrections (read this first)

Accepted risk P-10 (operator ruling of 2026-10-02 on PR-BOUNDARY-001 and PR-TESTS-002): a change confined to the status readers or to `tests/contract/**` is not caught on the pull request; the nightly run (shard 4) is the net. `packs.yml` deselects the Mission's corpus-marked modules (DD-22), so the push-to-`main` `built-in-corpus-suite` run is not a net. `plan.md` was corrected on 2026-10-03 (P-10, P-9, Reflexivity items 5, 7 and 8, the gate table and baseline step 5). `spec.md` was deliberately not edited: editing it would have made the recorded analysis stale again, and the spec records the specify-time view. The re-analysis after the plan corrections (commit `c80975b74`, verdict ready) found the following passages that still carry the superseded reading. They are corrected here by statement, not by edit.

| Id | Severity | Where | Superseded statement | Current reading |
|---|---|---|---|---|
| A1 | medium | `spec.md` R-14 | reader drift is caught on the next push to `main` by `built-in-corpus-suite` | the nightly run (shard 4) is the net; this is the operator-accepted risk of 2026-10-02 |
| A2 | low | `spec.md` D-16 item 5, the "every job that selects the corpus marker" bullet, the verification-table row; WP10's constraints | `built-in-corpus-suite` runs the reality check on push | superseded the same way: `packs.yml` deselects the modules (DD-22) |
| A3 | low | WP01 baseline step 2, WP12 T076, plan P-5 | measure that job's duration and apply first-red triage to it | still measured where T076 asks (`research.md` R-8), but that job no longer runs these modules |
| A4, A5 | low | pre-ruling passages in the work package bodies | n/a | history, left unchanged |
| A6 | medium | `spec.md` D-2 (line about 102) and the breaking-change definition (line about 365) | adding a response property is a non-breaking, minor-version change | superseded by the maintainer's closed-response-schema decision of 2026-10-03: an added response property (including one added through an `allOf` or `oneOf` branch), a new response status code, media type or header is breaking and needs a major move. Finding `PR2-CI-RELEASE-003` in `reviews/pr2.confirmed.yaml`; the code and `contracts/README.md` already say so |
| A7 | low | `tracer-design-decisions.md` DD-22 | the router's corpus job lists the contract test modules (a two-module remainder was assumed) | amended by DD-32: the router job keeps `test_mission_status_reality.py`, `test_mission_status_payloads.py` and `test_example_round_trip.py`; the earlier "two-module" list was incomplete because `test_example_round_trip` also stays (it reads the committed Missions). All other corpus-marked tool tests run in the `contract-tool-tests` job of `contracts.yml` |

A reader of the Mission should take the current reading wherever `spec.md` or a work package body says otherwise.

## 1. Base commit and baseline of known-red tests

- Base `08aedf9c0` (the merge of `origin/main` into the planning branch; merge-base with `origin/main` is `a3f76f673`, which is also `origin/main` on 2026-10-03). Measured by WP01 on 2026-10-02 (`research.md` R-8).
- Named gate files: 291 passed, 1 skipped (planning measured 265; `main` grew). Corpus 34, gate-selection 33, prose 75, terminology 96, clock 40, release 248 passed plus 6 skipped. Ruff clean over 2955 files.
- Known-red, binned:
  - `tests/contract/test_terminology_guards.py::test_orchestrator_api_docs_do_not_teach_removed_json_flag_or_unpinned_provider_source` at `docs/guides/how-to/monitoring/index.md:13`: pre-existing red on `main` (inputs byte-identical to `origin/main`), not touched by this Mission.
  - `tests/docs/test_docs_index.py::test_render_index_is_byte_stable_across_hash_seeds`: environment (needs a `.venv` in the lane worktree; passes in the repository-root checkout), tracer friction F-15.
- CI baselines: `tests (corpus-blocking)` 2 min 41 s (run 36922559661) and 2 min 33 s (run 36910183931); `built-in / -m corpus suite (advisory)` 14 min 55 s (run 36968918870, on `main` at `a3f76f673`).
- The pull-request runs of the stack carry no new red of their own: the last runs on each seam head all concluded success (see section 13).

## 2. Class A evidence: planted violations run in CI (FR-021)

Class A means a planted violation run by a CI job, with the clean control passing.

| Check | Evidence | Run |
|---|---|---|
| Negative-case driver, every planted case with its clean control | `counts: cases=85 ran=85 skipped=0 passed=85 failed=0` (seam 4 head `4cc75e38f`); earlier `cases=81 passed=81` at p1 | Contracts 37086155529; 37066885132 |
| Tampered Gradle dependency-verification metadata is refused | `PLANT_DETECTED ... DEPENDENCY_VERIFICATION_FAILED; 237 checksums were altered in the copy` | 37086155529; first seen in 37063316388 |
| Lint: planted violations fail, clean control passes | 8 rule plants plus an other-content-type plant fail; the clean control passes (`violations=0`) | 37063316388 (WP08); loop re-derived from plant headers in lane `eeea63ddc`, after run 37081554305 failed on the old derivation |
| Breaking-change gate | 3 clean controls pass; 5 plants fail without a major-version move and pass with one; a same-version change fails | 37063316388 |
| Release dry run | clean tags pass; 4 planted tags fail; real bundle `sha256 b8f792b1024e3162dfbd16ebf24e31427f83d1f7a060c80a3536f735ae353677`, `GH_RELEASE_ARGS` carries `--latest=false`, `sha256sum -c openapi.yaml.sha256` step ran | 37086155529 (the planted-tag counts are from 37063316388) |
| Client smoke over the real module | `files_emitted=77 generator_warnings=0` | 37086155529; 37066885132 |
| All nine Contracts jobs (verify-pins, python-checks, validate-bundle, negative-tests, resolver-parity, lint, breaking-change, release-dry-run, contracts-gate) | success | 37086155529 |

The bundler-fidelity spike evidence (five pushed iterations, runs 37005254243, 37006059523, 37006676740, 37008298213, 37011456242) is in `research.md` R-3; only the last run is green, the first four are the recorded failures that produced rulings DD-23 and DD-24.

## 3. Class B evidence: planted cases inside unit tests

Class B means a planted case inside a pytest module, collected with `pytest --collect-only -q` on the lane tip (2026-10-03).

- `tests/ci/test_contracts_workflows.py` (workflow guard tests, with planted violating workflow texts) together with `tests/ci/test_contracts_routing.py`: 70 tests collected. The planted-violation tests are: `test_a_planted_missing_fork_guard_is_refused` (4 cases), `test_a_planted_overlapping_or_empty_tag_filter_is_refused`, `test_a_planted_variant_without_a_header_or_with_a_wrong_header_is_refused`, `test_a_planted_wrong_needs_set_and_a_missing_job_are_refused`, `test_a_publish_step_that_derives_its_own_release_arguments_is_refused` (4), `test_a_publish_step_that_does_not_consume_the_checked_arguments_is_refused`, `test_a_release_check_tag_step_that_writes_no_arguments_file_is_refused`, `test_a_tolerant_gate_script_is_refused` (5), `test_planted_node_usage_is_refused` (4), `test_planted_pytest_reachability_is_refused`, `test_planted_release_trigger_violations_are_refused` (4), `test_planted_trigger_violations_are_refused` (3), `test_zero_publish_steps_fail_and_an_unconditional_or_dispatch_reachable_publish_is_refused`, `test_the_node_scan_ignores_a_comment_that_merely_names_node`.
- `tests/contract/test_mission_status_reality.py`: 567 tests collected, of which 541 are the per-Mission parametrised case and 26 are the controls: `test_a_real_payload_validates_and_each_planted_defect_fails`, `test_run_case_reports_a_planted_leak`, `test_run_case_reports_a_planted_schema_defect`, `test_run_case_reports_a_frontmatter_value_that_disagrees_with_the_snapshot`, `test_snapshot_equality_positive_control_projects_the_snapshot_not_the_frontmatter`, `test_snapshot_equality_negative_control_fails_when_the_frontmatter_value_is_patched_in`, `test_discarded_has_a_fixture_built_positive_control`, `test_the_byte_digest_alone_sees_a_rewrite_that_git_status_cannot`, `test_the_hash_proof_sees_a_changed_file_and_refuses_to_hash_nothing`, `test_an_ignored_file_is_part_of_the_fingerprint`, `test_a_check_that_did_not_run_for_every_payload_is_a_failure`, `test_an_empty_case_list_is_a_collection_error`, `test_every_generated_case_executed_and_the_count_is_not_vacuous`, `test_the_floors_are_pinned_below_the_measured_corpus`, `test_the_ceiling_is_not_stale`, `test_the_disagreement_list_does_not_grow_beyond_the_ceiling`, and the ordering, uniqueness, overview-builder and project-count tests.
- The 27 corpus-marked modules under `tests/contract/` (the per-check unit tests plus the examples, payloads and reality modules, listed in the router's `tests-corpus-blocking` job, section 13) carry their own planted fixtures under `contracts/tools/fixtures/`.

## 4. `x-derived` properties, citation counts and reused citations

Printed by `contracts/tools/citation_check.py` run over `contracts/` on the lane tip (exit 0): `counts: properties=143 x_source=118 x_derived=25 inputs_resolved=55`.

The 25 `x-derived` properties, with each rule (verbatim from the schema) and its inputs (a bare name is a contract field, `file#symbol` a code citation):

| Property | Rule | Inputs |
|---|---|---|
| `HistoryEntry.kind` | Always the constant transition, because only status transitions are projected into history. | `models.py#StatusEvent` |
| `LogTruncatedEvent.missionId` | The mission_id of the Mission's meta.json. | `mission_metadata.py#load_meta` |
| `MissionDetail.phases` | For specify, plan and tasks: the planning file exists, then complete by artifact; else the Completed lifecycle event, then complete by lifecycle_event; else the Started event, then in_progress by lifecycle_event; else pending by artifact. For implement: complete when wpTotal is above 0 and every work package is for_review, in_review, approved, done or canceled; else pending when none has left planned or blocked; else in_progress. For review: complete when wpTotal is above 0 and every work package is done or canceled; else pending when none is for_review, in_review, approved or done; else in_progress. Implement is evaluated before review. | `MissionHead.statusLaneCounts`, `MissionHead.wpTotal`, `lifecycle_events.py#SPECIFY_STARTED`, `lifecycle_events.py#SPECIFY_COMPLETED`, `lifecycle_events.py#PLAN_STARTED`, `lifecycle_events.py#PLAN_COMPLETED`, `lifecycle_events.py#TASKS_STARTED`, `lifecycle_events.py#TASKS_COMPLETED` |
| `MissionDetail.workPackages` | One WorkPackageSummary per work package of the Mission, from its planning files and the status snapshot, sorted by wpId ascending as plain strings. | `MissionHead.wpTotal`, `wp_view.py#reconstruct_wp_view` |
| `MissionHead.blockedCount` | Equal to statusLaneCounts.blocked. | `statusLaneCounts.blocked` |
| `MissionHead.lifecycleStatus` | Evaluated in order: discardedAt set gives discarded; wpTotal 0 gives draft; any work package claimed, in_progress, for_review, in_review or approved gives active; any planned or blocked work package gives planned; otherwise active until acceptedAt is set, then done. | `statusLaneCounts`, `wpTotal`, `discardedAt`, `acceptedAt` |
| `MissionHead.lastActivityAt` | The maximum last_transition_at over the work packages of the status snapshot; null when no work package has one. | `models.py#StatusSnapshot` |
| `MissionHead.nextAction` | Null when acceptedAt is set. Otherwise the review-then-accept sentence when the meta.json carries a baseline_merge_commit; otherwise the consolidate sentence when every work package is done or canceled and at least one is done; otherwise null. | `statusLaneCounts`, `acceptedAt`, `baseline.py#record_baseline_merge_commit` |
| `MissionLifecycleEvent.missionId` | The mission_id of the Mission's meta.json, whichever row the event came from; aggregate_id is the Mission ULID only on MissionCreated and is never used. | `mission_metadata.py#load_meta` |
| `MissionLifecycleEvent.eventType` | The event_type of the row when it is one of the seven listed values, which this contract owns (a subset of the lifecycle types the runtime knows); the row is dropped otherwise. | `lifecycle_events.py#MISSION_CREATED`, `lifecycle_events.py#SPECIFY_STARTED`, `lifecycle_events.py#SPECIFY_COMPLETED`, `lifecycle_events.py#PLAN_STARTED`, `lifecycle_events.py#PLAN_COMPLETED`, `lifecycle_events.py#TASKS_STARTED`, `lifecycle_events.py#TASKS_COMPLETED` |
| `MissionOverviewPage.items` | The overview records of the requested page, sorted by createdAt descending then missionId ascending. | `MissionHead.createdAt`, `MissionHead.missionId` |
| `MissionOverviewPage.pageInfo` | Computed by the service from the page size, the incoming page cursor and the number of overview records that follow this page. | `items` |
| `MissionPhase.name` | The fixed list of the five Mission phases, in workflow order; the phase names are not stored anywhere else. | `lifecycle_events.py#SPECIFY_STARTED` |
| `MissionPhase.status` | Specify, plan and tasks: complete when the planning artifact (spec.md, plan.md, tasks.md) exists; else complete when the matching Completed lifecycle event exists; else in_progress when the matching Started event exists; else pending. Implement and review: taken from statusLaneCounts and wpTotal as written on MissionDetail.phases. | `MissionHead.statusLaneCounts`, `MissionHead.wpTotal`, `lifecycle_events.py#SPECIFY_COMPLETED` |
| `MissionPhase.basis` | artifact when the planning artifact exists or nothing exists yet; lifecycle_event when the status comes from a Started or Completed lifecycle event; derived_from_status_lanes for implement and review, always. | `lifecycle_events.py#TASKS_COMPLETED` |
| `Project.missionCount` | The number of overview records, that is of Missions the service lists on GET /missions. | `MissionOverviewPage.items`, `mission_metadata.py#load_meta` |
| `ReviewOverride.complete` | True only when the stored at, actor, wp_id and reason are all non-empty strings, the definition of ReviewOverride.complete; the stored wp_id is read but not shown. | `models.py#ReviewOverride` |
| `StatusTransitionEvent.missionId` | The mission_id of the Mission's meta.json, whichever row the event came from; aggregate_id is never used. | `mission_metadata.py#load_meta` |
| `SubtaskProgress.done` | The count of entries of the resolved subtask map whose value is done. | `WorkPackage.subtasks`, `wp_view.py#ResolvedGroup` |
| `SubtaskProgress.total` | The number of entries of the resolved subtask map. | `WorkPackage.subtasks`, `wp_view.py#ResolvedGroup` |
| `WorkPackage.subtaskProgress` | The counts of the resolved subtask map; the authored roster is not used. | `subtasks`, `wp_view.py#ResolvedGroup` |
| `WorkPackage.readyToStart` | True when statusLane is planned and readiness.satisfied is true; false otherwise, including when statusLane is null. | `statusLane`, `readiness.satisfied`, `dependency_graph.py#dependency_readiness_for_wp` |
| `WorkPackage.history` | The status transition events of the work package from the event log, sorted by at then eventId ascending; annotation, lifecycle and retrospective rows are dropped. | `models.py#StatusEvent` |
| `WorkPackageSummary.readyToStart` | True when statusLane is planned and readiness.satisfied is true; false otherwise, including when statusLane is null. | `statusLane`, `readiness.satisfied`, `dependency_graph.py#dependency_readiness_for_wp` |
| `WorkPackageSummary.subtaskProgress` | The counts of the resolved subtask map, as written on SubtaskProgress. | `wp_view.py#ResolvedGroup` |

Citations used by more than five properties (printed by `citation_check` as informational `CITATION_REUSE` lines, exit status 0): `src/specify_cli/status/wp_view.py#ResolvedGroup` (15 properties), `src/specify_cli/status/wp_metadata.py#WPMetadata` (9), `src/specify_cli/status/wp_view.py#AuthoredGroup` (9) and `src/specify_cli/status/models.py#decode_actor` (6). Each names a record type or decoder that genuinely carries all the fields, so a single citation is the honest source.

## 5. Reality-check floors, disagreement list and ratchet

- Floors as measured and pinned (full-mode CI Router run 37073720061, head `eb4fde0a7`; the same figures were relayed from the orchestrator's final local run at lane tip `c02b14852`, which this WP did not re-run): 541 Missions projected, 3156 work-package payloads validated, 23594 events validated; own-directory pass 2967 snapshot work packages and 3156 work-package files; 0 skips.
- Disagreement list: 52 Missions, ceiling 52 (the check passes while the list does not grow; a separate test, `test_the_ceiling_is_not_stale`, guards the ceiling against going stale).
- Ratchet: issue #5579 ("Mission status: drain the snapshot-versus-files work-package disagreement (reality-check ratchet)", open), owner `@stijn-dejongh`, `drain_by` 2026-12-31, sub-issue of #5528. The owner and date are in the header of `tests/contract/fixtures/mission_status_expected.json`.
- Environment-dependent, never floored: 37 `CoordinationBranchDeleted` coordination fallbacks in the CI run (483 locally).

## 6. Data the reality check reads that the router does not select, and uncovered reader paths

Data files read by the reality check but not matched by any router filter group (a change to one of them does not select `tests-corpus-blocking`): `meta.json`, `status.events.jsonl` and `tasks.md` under every `kitty-specs/*/`, and `.kittify/config.yaml`.

Reader paths the reality check exercises but whose edits select no per-change job (accepted risk P-10, section "Planning-text corrections"): `src/specify_cli/status/**`, `src/specify_cli/mission_metadata.py`, `src/mission_runtime/**`, `src/specify_cli/core/dependency_graph.py` and `tests/contract/**`. Drift there is caught by the nightly run (shard 4), not on the pull request; PR diffs not touching `contracts/**` do not select `tests-corpus-blocking`, so the reality-check evidence for this Mission is the router full-mode dispatch (run 37073720061).

## 7. DEV-1, DEV-2 and the D-P13 additions: confirmation requests (E-2)

- DEV-1 (`spec.md` CL-2): the reality check runs once, in the router's corpus job (`tests-corpus-blocking` on `main`), and the contracts workflow proves resolver parity instead of running a second pytest run. Accepted by a maintainer ruling of 2026-10-01 (OQ-4; `tracer-design-decisions.md` DD-1).
- DEV-2 (`spec.md` CL-4): the PR-green release dry run is the `release-dry-run` job of the contracts workflow, which runs the same release script; the release workflow itself has only a tag push and a `workflow_dispatch` with a dry-run mode that never publishes. Planned as covered by the OQ-4 ruling; E-2 asks for explicit confirmation.
- D-P13 plan-level additions (no spec requirement): the `preview/mission-status/p<n>` tag namespace, the `PREVIEW_DELTA` report, the `Pre-release shape change` CHANGELOG heading and `client_smoke.py`. Rationale: an outside UI team needs a checkable early-start point before any release tag.
- State on 2026-10-03: the confirmation requests are to be asked once, in the body of PR 1 and on #5528 (`plan.md` E-2). The body of PR #5566 as read on 2026-10-03 does not contain them; this is a gap for the orchestrator (section 14), not a confirmation.

## 8. Review is advisory

There is no branch protection and no required review on this repository (charter; tracer friction F-8: read-only probes of the default branch returned 404 for branch protection and an empty list of rulesets). `.github/CODEOWNERS` carries `/contracts/ @stijn-dejongh @MOES-Media` and routes review only. The body of PR #5577 (seam 3, WP07) states this ("review is advisory; there is no enforcement on this repo"), read on 2026-10-03.

## 9. Fleet-verdict observability limit

The contracts workflow is registered with the fleet verdict (`scripts/ci/fleet_verdict.py`, a `workflow_run` consumer). GitHub runs a `workflow_run` workflow from the default branch's copy, so the fleet verdict's treatment of the new workflow cannot be observed from a pull request; it is confirmed only after merge (post-merge step 3 below). This record did not look for the comment on the pull requests, by design.

## 10. Realised six-seam pull-request shape

Operator ruling of 2026-10-02 (DD-21). Heads read from GitHub and `origin` on 2026-10-03.

| PR | Seam | Work packages | Base | Head |
|---|---|---|---|---|
| #5566 | 1 | WP01, WP02 | `main` | `860365d35` |
| #5568 | 2 | WP03, WP04, WP05 | seam 1 branch | `0ffed6acb` |
| #5577 | 3 | WP06, WP07 | seam 2 branch | `f269389d4` |
| #5578 | 4 | WP08, WP09 | seam 3 branch | `4cc75e38f` |
| #5581 | 5 | WP10 | seam 4 branch | `9b590c8d3` |
| not opened | 6 | WP11, WP12 | seam 5 branch | `e38f59e24` (branch exists on `origin`, no pull request) |

Branches are `issue-5558-mission-status-contract-v1-seam1` to `-seam6`. All five open pull requests are drafts. Each seam branch is an ancestor of the next (`git merge-base --is-ancestor`, checked for 1 to 6). The seams were rebuilt in a scratch assembly worktree after the pull-request CI defects (pushed with `--force-with-lease`) and again for the review fold rounds, each round contributing its own seam commits.

## 11. Open-pull-request overlaps; #5557

Computed 2026-10-03 as the intersection of `git diff --name-only origin/main...seam6` with `gh pr diff --name-only`:

- #5540 (open, "feat: optional anonymous in-harness Feedback Survey", 163 files): overlaps on `docs/changelog/CHANGELOG.md` and `docs/development/docs-retrieval-index.yaml`.
- #5326 (open draft, "[#5151] Verify WP handoff planning provenance", 28 files): overlaps on `docs/changelog/CHANGELOG.md`.
- #5557 ("[#5510] Faster, honest CI ...") is **closed, not merged** (closed 2026-10-01T20:19:49Z); its overlaps (router, `packs.yml`, the corpus trigger completeness test, two other gate files) are therefore moot. The gate the Mission had to adapt to, `test_corpus_blocking_home`, arrived with `main` after planning and not through #5557 (DD-22).
- Both open overlaps are in changelog and index files only; whether a textual conflict arises is not verified and is settled by whichever pull request merges second.

## 12. Lane model and tooling limitations

- All code work packages ran in one code lane: `agent mission create --start-branch` on 4.0.0rc5 derived topology `lanes` and the CLI collapsed WP01 to WP11 into one lane because their write scopes overlap (tracer friction F-2, F-23; DD-30). WP12 is the only planning work package and runs in the planning lane on the planning branch, with this record being the only thing it writes.
- `wps.yaml` cites IC-07a and IC-07b as IC-07 because the manifest accepts only `IC-##` (F-38).
- `finalize-tasks` rejects a lane graph where the planning lane is both upstream and downstream of a code lane (`LANE_DEPENDENCY_CYCLE`), which is why this WP is last and the planning records between code work packages were written by the orchestrator (F-38).
- The CLI refuses `for_review` when `kitty-specs/` is committed on a lane branch, so tracer entries were recorded on the planning branch (F-21).
- The tag push and the `contract-mission-status-v1.0.0` release are maintainer steps after merge (below); no tag of any kind exists today (`git ls-remote --tags origin 'preview/*' 'contract-*'` is empty).

## 13. Per-pull-request evidence table

Latest runs per head (all `pull_request` events; a cancelled run is a superseded run that fail-fast or a force-push cancelled, and the same head has a successful twin):

| PR | Head | Latest CI Router | Contracts | Packs | CI Quality / CI Modules |
|---|---|---|---|---|---|
| #5566 (1) | `860365d35` | 37059582197 success | 37059581949 success | 37059581927 success | 37059582016, 37059582437 success |
| #5568 (2) | `0ffed6acb` | 37086157076 success | 37086157102 success | 37086157118 success | 37086157079, 37086157276 success |
| #5577 (3) | `f269389d4` | 37086155820 success | 37086155813 success | 37086155814 success | 37086155823, 37086155993 success |
| #5578 (4) | `4cc75e38f` | 37086155500 success | 37086155529 success | 37086155560 success | 37086155469, 37086155726 success |
| #5581 (5) | `9b590c8d3` | 37086156758 success | no Contracts run on this head | 37086155613 success | 37086155767, 37086155899 success |

Per-row confirmation against the body of each pull request (bodies read with `gh pr view --json body` on 2026-10-03). The five open bodies each say "Draft until the maintainer acks the design on #5528" and each pull request is a draft; none of the bodies carries the baseline of known-red tests (section 1) or a five-section structure in the sense of the repository's PR contract that this WP could verify, and three still say the last work package of their seam is "still to land on this branch" although the seam head contains it. Those are gaps for the orchestrator (section 14).

| PR | Required row content | Evidence in this record | Confirmed against the body |
|---|---|---|---|
| 1 (#5566) | DEV-1 and DEV-2 confirmation requests (also on #5528); spike record pointers; SC-008 assertions against `origin/main`; known-red baseline | section 7; spike runs in section 2 and `research.md` R-3; SC-008 results below (PR 1 line); baseline section 1 | body has none of the first two; baseline absent; it describes WP02 as "still to land" |
| 2 (#5568) | example-test counts; p0 tag name | `tests/contract/test_mission_status_examples.py` collected as part of the 567 and 27 module list (section 3); p0: `preview/mission-status/p0` (section "Preview points") | body states 9 examples (WP03) and 11 (WP04) and names `preview/mission-status/p0`; it describes WP05 as "still to land" |
| 3 (#5577) | CODEOWNERS advisory statement (SC-010); class A and class B evidence | sections 8, 2 and 3 | advisory statement present; class A and B evidence not in the body |
| 4 (#5578) | release dry-run artifact (SC-006: bundle, `openapi.yaml.sha256`, `sha256sum -c`, run id); p1 tag name with the run id; supply-chain record; fleet-verdict observability limit | run 37086155529 (section 2); p1 run 37066885132; `research.md` R-9; section 9 | body has the vacuum and oasdiff pin table; no run id, p1 name or observability limit; it describes WP09 as "still to land" |
| 5 (#5581) | NFR-001 timing and the SC-002 reality check; NFR-007 coverage paste; p2 tag name; ratchet issue | `research.md` R-8 NFR-001 table; section 5; NFR-007: not available (below); `preview/mission-status/p2`; #5579 | body has the 541 / 3,156 / 23,594 figures and #5579; no timing, no p2 name, no coverage paste |
| 6 (not opened) | the ledger, the post-merge list, the acknowledgement link | this file; the acknowledgement does not exist yet (the draft status is the point) | there is no body |

NFR-007 coverage paste: **not available**. No `diff-cover` job appears among the jobs of the final pull-request runs of the stack or of run 37073720061, so there is no coverage output to paste and the empty-critical-diff expectation is unchecked (tracer friction F-20). The only log lines naming the tool are dependency-install lines (`+ diff-cover==10.2.0`, for example in run 37073720061 and in CI Quality run 37086155767), not coverage reports.

### SC-008 and C-002 to C-005 diff constraints, per pull request

Taken read-only on 2026-10-03 against each pull request's own base (PR 1 against `origin/main`, PRs 2 to 6 against the previous seam head, PR 6 against seam 5 with seam 6 as its head; the last row is the whole stack against `origin/main`). Commands as written in the WP12 prompt, run from the repository root with seam branch refs as heads.

| Row | `git diff --stat` over `src`, `contracts/fixtures`, `tests/contract/test_handoff_fixtures.py`, `pytest.ini`, `.github/ci-module-registry.yml`, `scripts/ci/fleet_main.py` | `ci-router.yml` added / removed lines (the `contracts/**` glob line) | trigger-completeness test: removed lines | Node ban part 1 hits | Node ban part 2 hits |
|---|---|---|---|---|---|
| PR 1 | empty | 13 / 1 (glob line present once) | 0 | 0 | 0 |
| PR 2 | empty | 1 / 0 | 0 | 0 | 0 |
| PR 3 | empty | 13 / 2 | 0 | 1 | 0 |
| PR 4 | empty | 5 / 0 | 0 | 3 | 0 |
| PR 5 | empty | 2 / 0 | 0 | 0 | 0 |
| PR 6 | empty | 0 / 0 | 0 | 0 | 0 |
| Stack | empty | 32 / 1 (glob line present once) | 0 | 4 | 0 |

Reading of the router column. The prompt expected exactly one added line and no removed line in PR 1 and none in PRs 2 to 6. That holds for the `contracts/**` glob (one added line, in PR 1). It does not hold for the file as a whole: the router also gained the module list and a comment of the `tests-corpus-blocking` job, and lost one comment line it replaced, because of the DD-22 operator ruling (`tests/ci/test_corpus_blocking_home.py` arrived with `main` after planning). This is a deliberate widening of C-003, recorded in `tracer-design-decisions.md` DD-22 and PR #5577's body; the stack row (32 added, 1 removed) shows the removed line is the one comment line.

`tests/architectural/test_ci_corpus_trigger_completeness.py`: no removed line over the whole stack; only the 27 registry rows were added; `_CORPUS_GLOBS` and `_CORPUS_DATA_ROOTS` are untouched (zero diff lines mention either).

Node ban (C-005). Part 1 hits over the stack, by file: `tests/ci/test_contracts_workflows.py` 3 (`NODE_TOKENS`, the planted `setup-node` workflow text and the parametrised plant list) and `tests/contract/test_structure_check.py` 1. The first file is the one the prompt permits. The second is a negative assertion, `assert "npm" not in text.split()` inside `test_no_node_tooling_is_referenced`, which checks that the structure-check script does not mention npm; it is not a use of Node tooling, but it is a hit in a file the recipe does not permit, so it is reported rather than waved through (tracer friction F-35). Part 2 (a `node` command in workflow YAML) returns empty over the stack with no allow-list. Part 3 (non-vacuity): the same pattern run over `tests/ci/test_contracts_workflows.py` hits at least once, on the planted bare `run: node build.js` step (`PLANTED_BARE_NODE`), so Part 2 can fire on a correct tree.

### C-003 computed shared-CI path set

Output of the prompt's script (owned set computed from `wps.yaml`), per pull request and for the stack:

| Row | Output |
|---|---|
| PR 1 (`origin/main` to seam 1, WP01, WP02) | `owned 7 changed 7 stray ['.github/workflows/packs.yml'] missing []` |
| PR 2 (seam 1 to seam 2, WP03 to WP05) | `owned 0 changed 2 stray ['.github/workflows/ci-router.yml', '.github/workflows/packs.yml'] missing []` |
| PR 3 (seam 2 to seam 3, WP06, WP07) | `owned 0 changed 2 stray ['.github/workflows/ci-router.yml', '.github/workflows/packs.yml'] missing []` |
| PR 4 (seam 3 to seam 4, WP08, WP09) | `owned 3 changed 5 stray ['.github/workflows/ci-router.yml', '.github/workflows/packs.yml'] missing []` |
| PR 5 (seam 4 to seam 5, WP10) | `owned 0 changed 2 stray ['.github/workflows/ci-router.yml', '.github/workflows/packs.yml'] missing []` |
| PR 6 (seam 5 to seam 6, WP11, WP12) | `owned 0 changed 0 stray [] missing []` |
| Stack (`origin/main` to seam 6, all work packages) | `owned 9 changed 9 stray ['.github/workflows/packs.yml'] missing []` |

`missing` is empty in every row. `stray` is not empty, and the cause is a wording and ownership gap, not an unowned edit: the DD-22 widening (ratified by the operator on 2026-10-02) put the module lists in `ci-router.yml` and the `--deselect` lists in `packs.yml`, but no `owned_files` entry in `wps.yaml` names `packs.yml` and only WP01's names `ci-router.yml`, so the computed set flags the later appends as stray. `tests/ci/test_fleet_main.py` does not appear in any row's changed set. `plan.md` and `spec.md` name only the four fleet-verdict files as the other shared-CI edits (C-003, SC-008); `tests/ci/test_contracts_routing.py` is a new routing test WP01 added (a new file, covered by the computed set, not by the spec wording); this deviation is stated on purpose and belongs in the body of PR 1 (gap for the orchestrator). The orchestrator may wish to widen `owned_files` in a later planning pass; this WP does not edit `wps.yaml`.

### Tracer F-3: the scaffold commit subject

`git log --format=%s origin/main..<seam 6>` still contains `Add scaffold for feature mission-status-contract-v1-01M3WC5X` (commit `dcee47338`, legacy wording quoted verbatim; the canonical term is Mission). The compact-history rewrite that the orchestrator planned for PR prep has not run, so the gap is open. Not a failing gate (tracer friction F-3).

### Gates run read-only by this WP (2026-10-03, lane tip `c02b14852`)

| Gate | Result |
|---|---|
| `python contracts/tools/leak_scan.py --root contracts` | exit 0, `counts: files=898 values_strict=315 values_human=7133 values_all=21324` |
| `python contracts/tools/no_pytest_scan.py` | exit 0, `counts: scripts_scanned=24` |
| `python contracts/tools/citation_check.py` | exit 0, counts in section 4 |
| `spec-kitty cutover-guard --base-ref origin/main` | blocks: `mission-status-contract-v1-01M3WC5X: status_phase not flipped despite event-log runtime evidence`; the remedy it names, `spec-kitty migrate backfill-runtime-state --mission mission-status-contract-v1-01M3WC5X`, writes Mission state and was deliberately not run (second record, same as WP01's: tracer friction F-17, F-24) |
| `spec-kitty regen --check` | `--help` shows it is read-only (`Do not write; render into memory and byte-compare`); ran: "All 3 generated fixtures are fresh." |
| `PWHEADLESS=1 pytest -q tests/architectural/test_no_legacy_terminology.py` | 96 passed |
| `uv lock --check` | "Resolved 130 packages", exit 0 |

## Preview points

`p0`, `p1` and `p2` are **prepared and not published**. The operator said on 2026-10-02 not to tag yet; `git ls-remote --tags origin 'preview/*'` returns nothing on 2026-10-03. The names are final; the commits are where each tag will be cut. Because the seams were rebuilt, the hash first prepared for a point no longer exists on a seam branch; the current seam head is the commit a tag would carry today.

| Tag | Work package | Prepared at (first preparation) | Current head of its seam | Cites |
|---|---|---|---|---|
| `preview/mission-status/p0` | WP05 | `ffd050650` on the seam 2 branch (PR #5568), WP05 approved after review cycle 2; a local JVM check of the real module passed on it | `0ffed6acb` | PR #5568 |
| `preview/mission-status/p1` | WP09 | lane `788d3ee19`; PR #5578 head `3ea5213ec`; Contracts run 37066885132, all 9 jobs green | `4cc75e38f` | PR #5578, run 37066885132 |
| `preview/mission-status/p2` | WP10 | lane `c026128a5`; PR #5581 head `eb4fde0a7`; CI Router full-mode run 37073720061 green | `9b590c8d3` | PR #5581 |

`a214f7349` was the pre-fix p0 candidate and is not the p0 point. Re-publication counters (`-r2`, `-r3`): none yet, since nothing is published; a tag is re-published with the next counter after any compact-history of its seam or a seam below it (the stack was rebuilt for the CI fixes and for the review fold rounds before any tag existed).

## Post-merge close-out steps (maintainer-run, SC-009)

These are the close-out record, not follow-up issues.

1. Merge the six pull requests bottom-up (draft status is lifted by a maintainer only after the acknowledgement is linked on #5528).
2. Push the tag `contract-mission-status-v1.0.0`. Verify the release was created with `--latest=false`, that the repository's Latest release is still the CLI's, that it holds exactly the bundle and its sha256, that the downloaded checksum verifies (`sha256sum -c openapi.yaml.sha256`) and equals a locally rebuilt bundle. The dry-run reference value is `b8f792b1024e3162dfbd16ebf24e31427f83d1f7a060c80a3536f735ae353677` for the seam 4 head (run 37086155529); the tag commit's own value governs.
3. Open or inspect the first pull request touching `contracts/` and confirm the fleet-verdict comment lists the contracts workflow (section 9).
4. Read the push-to-`main` `built-in-corpus-suite` run and apply the first-red triage rule if it is red. Note (section "Planning-text corrections"): that job deselects this Mission's modules, so it is a mainline signal, not the safety net for the reality check; the nightly run (shard 4) is.
5. Run `spec-kitty regen --check` once as a no-diff confirmation (it was fresh on the lane tip on 2026-10-03).
6. Publish the preview tags if the UI team asks (names above).

## NFR-001 measurements (T076)

Recorded in full, with run ids and the derivation, in `research.md` R-8 ("NFR-001 measurements, taken 2026-10-03"). Summary:

- Reality-check module: about 115 s against the 120 s limit (derived from log timestamps, run 37073720061; the module prints no duration of its own).
- Slowest reality case: 0.87 s (`owned-checkout-lifecycle-authority-01M3M2ZB`) against 60 s.
- Whole `tests (corpus-blocking)` job: 6 min 37 s against the 10 minute timeout, so headroom is 34 percent and the 50 percent target is **not met** (WP01 baseline on earlier pull requests: 2 min 33 s to 2 min 41 s, runs 36910183931 and 36922559661).
- `built-in-corpus-suite` from a full-mode `packs.yml` dispatch: **not measured**, no such dispatch exists. A pull-request run of that job took 11 min 13 s (Packs run 37086155560) but no longer runs these modules.
- The full-mode dispatch predates the three fold rounds (it ran on `eb4fde0a7`, not on the final head), so the job figures describe the Mission before them.
- Superseded in part by section 15.2: a later full-mode run on the restacked seam-5 head measured 7 min 20 s, and DD-32 acted on it. This section is kept as written.

## Verification of the orchestrator-written records (T074)

| Record | Checked against | Result |
|---|---|---|
| R-8 baseline (WP01) | counts, runs 36922559661, 36910183931, 36968918870 exist and concluded success; base `08aedf9c0` exists | matches; CI durations as quoted; no tracker issue cited for the pre-existing red (it is a known `main` red, not filed by this Mission) |
| R-3 spike table and "IC-07a complete" sentence | runs 37005254243, 37006059523, 37006676740, 37008298213 (failure) and 37011456242 (success) exist as recorded; time-box and rulings DD-23 to DD-25 present | matches; the normalisation table the plan promised was replaced by the DD-24 ruling, so no table within the cap of eight exists, by design |
| R-2 / R-9 versions, dates and checksums | `contracts/tools/pins.json` | matches entry for entry; two transcription errors fixed in `research.md` (the tamper test altered 237 checksums, not one; the vacuum and oasdiff rows still said "no pins yet") |
| R-9 control 5 | `advisory_feed_checked` fields of `pins.json` | result sentence added |
| Brace re-sweep and re-publication tags | none exist | no gap: DD-23 removed the re-sweep, no tag was published |
| R-5 job name | `ci-router.yml` on the stack | note added (the job is `tests-corpus-blocking`) |

## Review trail

Plan, spec and tasks reviews are in `reviews/` (`plan-*`, `spec-*`, `tasks-*`). The pre-merge squad over `origin/main...059efad2c` (boundary, contract and tests lenses): `reviews/pr-boundary.findings.yaml`, `pr-contract.findings.yaml`, `pr-tests.findings.yaml`, merged in `pr.merged.yaml` (17 findings), refuted and confirmed in `pr-refute-1.yaml` to `pr-refute-3.yaml` and `pr.confirmed.yaml` (11 confirmed, 6 refuted). Fix round 1 (lane `059efad2c..8a67418bc`, six seam commits): 31 of 31 items verified resolved (`pr-verify.yaml`); a fresh sweep found 6 findings, 2 introduced by the fixes (`pr-fresh.yaml`). Fix round 2 (`8a67418bc..547f0c86c`, five seam commits): 8 of 8 verified (`pr-verify-r2.yaml`); sweep: 2 severity-2 and 2 severity-1 findings (`pr-fresh-r2.yaml`). Fix round 3 (`547f0c86c..c02b14852`, three seam commits): 4 of 4 verified including one severity-1 residual (`pr-verify-r3.yaml`); no further finding (`pr-fresh-r3.yaml`). Converged in three rounds (the maximum) with no finding at severity 4 or above open.

## 14. Gaps and requests for the orchestrator

1. Draft pull-request bodies do not yet carry what section 13 lists (known-red baseline, DEV-1 and DEV-2 requests, run ids, p-tag names, NFR-001 numbers); three bodies still say a seam's last work package is "still to land". Body edits on a draft are the orchestrator's.
2. PR 6 (seam 6) is not opened.
3. NFR-001: whole-job headroom for `tests (corpus-blocking)` is 34 percent against a 50 percent target (6 min 37 s of 10); no full-mode `packs.yml` dispatch exists; the full-mode run predates the fold rounds. A new full-mode dispatch of both workflows on the final heads would settle all three.
4. NFR-007 coverage paste: not available (no `diff-cover` job observed).
5. `wps.yaml` `owned_files` does not list `packs.yml` or the later `ci-router.yml` appends, so the computed C-003 check reports a stray set (section 13); a stray `npm` string in `tests/contract/test_structure_check.py` is a negative assertion.
6. The scaffold commit subject (tracer F-3) still reads the legacy wording in the stack history.
7. The `cutover-guard` block (F-17, F-24) is unchanged; its remedy writes Mission state and is the orchestrator's to decide.
8. Preview tags: none published, by the operator's decision of 2026-10-02.

## 15. Update after the maintainer landing (2026-10-03)

This section was added after the sections above were written. It records what happened since; sections 1 to 14 are left as written and are read together with it.

### 15.1 Landing and restack

- The maintainer landed slices 1 to 3 on `main` with landing folds: #5566 (slice 1, merged 2026-10-03T08:37:39Z), #5591 (slice 2, merged 2026-10-03T09:19:04Z, superseding #5568, closed 09:00:49Z) and #5594 (slice 3, merged 2026-10-03T10:05:49Z, superseding #5577, closed 09:54:41Z). The landing folds on slice 1 are listed in the maintainer's notes on #5566 (a `$ref` `ESCAPES_ROOT` containment refusal, an `UNREADABLE` refusal code, a corrected scrub note); the Gradle-to-`pins.json` pin parity check was deferred to slice 4.
- Slices 4 to 6 (#5578 and the two after it) were restacked onto `main` after slice 3 merged. The restacked tree is the final tree cited below; hashes in sections 1 to 14 that name pre-landing seam heads are history.

### 15.2 NFR-001 after the fold rounds (DD-32)

- Measured on the full-mode CI Router run 37087659251 (seam-5 head): the `tests (corpus-blocking)` job took 7 min 20 s against its 10 minute timeout, which is 27 percent headroom against the target of at least 50 percent. NFR-001 was **not met**. The same job takes about 2 min 31 s on `main`. Of the added time about 119 s was the reality module and about 160 s the contract tool unit tests.
- Operator ruling 2026-10-03 (DD-32, `tracer-design-decisions.md`; amends DD-22): the router's corpus job keeps only the modules that read the committed corpus (reality, payloads, example round trip); the contract tool tests moved to the Contracts workflow as the new `contract-tool-tests` job; the reality module was made faster without weakening a check (local wall time about 70 s to about 22 s, byte-identical report; `reviews/pr-verify-dd32.yaml` reports 70.5 s to 22.4 s and that the PR-TESTS-001 counters stay decisive).
- Independent verification of the move: every one of the 28 corpus-marked `tests/contract` modules has exactly one home, three planted violations (an unrun module, a twice-run module, pytest in the lint job) fail and were restored, and the tool tests pass in a fresh `--no-install-project` environment (763 passed, 14 skipped for want of vacuum) (`reviews/pr-verify-dd32.yaml`, verdict pass; two sev-2 and one sev-1 observations, of which PR-DD32-001 is closed by the update to `contracts/tools-and-workflows.md` in the same commit as this section).
- Gradle-to-`pins.json` parity (deferred by the maintainer from slice 1 to slice 4, PR #5566 landing note): built as `contracts/tools/gradle_pin_check.py` (codes GRADLE_PIN_MISMATCH exit 1; GRADLE_PIN_UNREADABLE, GRADLE_PIN_UNPARSEABLE, ZERO_COMPARISONS exit 2), run in the Contracts `verify-pins` job, with negative case `gradle-pin-mismatch`; independently verified (reviews/pr2-verify-gradle.yaml).
- NFR-001 after DD-32: **met**. Full-mode run 37131680223 (seam-5 head f2e94b6c7, after the restack onto main and compaction): `tests (corpus-blocking)` took 3m43s against its 10 minute timeout, 63 percent headroom against the 50 percent target (it was 7m20s, 27 percent, on run 37087659251).

### 15.3 Reality numbers on the restacked tree

Reality check (on the restacked, compacted tree at the seam-5 head, on current main's corpus): 544 Missions projected, 3184 work package payloads validated, 23918 events validated; the disagreement list is 52 Missions, at the ceiling of 52 (tracker #5579, owner @stijn-dejongh, drain by 2026-12-31); 27 redactions. (Section 5 holds the earlier figures 541 / 3156 / 23594.)

### 15.4 Maintainer-requested changes folded into slice 4

From the maintainer's note on #5578 (2026-10-03T09:47:36Z), folded into the slice-4 fix commit `5286ffa89` of the restack:

1. `verify_pins` really verifies checksums: the Contracts workflow call fetches each pinned artefact (`--fetch`), and the tool refuses a run that never hashed a pinned checksum (`CHECKSUMS_UNVERIFIED`, exit 2); a negative case with a clean control covers it.
2. `-SNAPSHOT` versions: an unreleased contract version carries a `-SNAPSHOT` suffix (`1.0.0-SNAPSHOT`); `breaking_check.py` and `release_check.py` treat `X-SNAPSHOT` as the work in progress of `X`, and a `-SNAPSHOT` release tag is refused (`SNAPSHOT_RELEASE_REFUSED`); the module CHANGELOG heading matches.
3. Closed response schemas: a change to a response shape ships as a new schema version and a new published release. An added response property (including one added in an `allOf` or `oneOf` branch), a new response status code, a new media type and a new header are breaking and need a major move; the rule is documented in `contracts/README.md`.

### 15.5 Release workflow gate

`contracts-release.yml` publishes only when: the tag is on `main` (the tagged commit is an ancestor of `origin/main`); the last commit touching the Contracts trigger paths (read from `on.push.paths` of `contracts.yml`) has a successful push run of Contracts on `main`, failing closed; and `breaking_check.py --release-tag` runs before `release_check.py` and the publish steps (`reviews/pr2-verify.yaml` PR2-CI-RELEASE-005, `reviews/pr2-verify-r2.yaml` PR2-FRESH-001).

### 15.6 Second pre-PR review squad (seams 4 to 6)

- Lenses: tests, ci-release, integration (`reviews/pr2-tests.findings.yaml`, `pr2-ci-release.findings.yaml`, `pr2-integration.findings.yaml`). Merged: 14 findings (`reviews/pr2.merged.yaml`). Refuters (`pr2-refute-1.yaml`, `pr2-refute-2.yaml`): all 14 confirmed, 4 of them as partial (`reviews/pr2.confirmed.yaml`).
- Fixed in two rounds. Round 1 verified at `17d09989f` (`reviews/pr2-verify.yaml`: all anchored findings resolved); the fresh sweep found two sev-2 (`PR2-FRESH-001`, `PR2-FRESH-002`; `reviews/pr2-fresh.yaml`). Round 2 verified at `f86142ac7` (`reviews/pr2-verify-r2.yaml`: both resolved); the second fresh sweep found 0 (`reviews/pr2-fresh-r2.yaml`). Converged in 2 rounds with no finding open.
- DD-32 verification: `reviews/pr-verify-dd32.yaml`.
- Development-assist test cleanup over the tests added by seams 4 to 6: 26 file-level rows kept, 0 retired, 0 split; 6 mission-label strips and 1 rename on kept tests. `test_the_run_report` was restored as kept and made non-vacuous (it now asserts every required section is present) because the run report is spec-required output.

## 16. Update after slices 4 and 5 landed (2026-10-04)

This section was added after section 15. Sections 1 to 15 are left as written. Where this section and an earlier one disagree, this section is the current reading. Line numbers below refer to this file before the header pointer and this section were added.

### 16.1 Landing history

| Slice | Pull request | What happened |
| --- | --- | --- |
| 1 | #5566 | Merged 2026-10-03 with maintainer landing folds (section 15.1). |
| 2 | #5591 | Merged 2026-10-03. It replaced #5568, which was closed. |
| 3 | #5594 | Merged 2026-10-03. It replaced #5577, which was closed. |
| 4 | #5606 | Merged 2026-10-03 with seven maintainer landing folds (16.3). It replaced #5578, which was closed. |
| 5 | #5581 | Merged 2026-10-04 with maintainer landing folds (16.3). It kept its number. |
| 6 | #5582 | This pull request: documentation and this close-out record. It kept its number. |

The commit heads, CI run ids and bundle checksum quoted in sections 1 to 15 belong to the pre-landing seam branches. Those heads are not on `main`, and the run ids describe runs of those heads. On the landed tree the reality check covered 546 Missions, 3,193 work package payloads and 24,419 events.

### 16.2 Earlier statements that are now false

| Where | Earlier statement | Current reading |
| --- | --- | --- |
| "Planning-text corrections" row A7 (line 20); section 15.2 (line 303) | The contract tool tests run in the `contract-tool-tests` job of `contracts.yml`. | There is no such job. The Contracts workflow has nine jobs and runs no pytest. The tool tests run in the router job `tests (contract tools)` (`tests-contract-tools` in `ci-router.yml`), a required check through `router-gate`. Slice 4 landing moved them there so that a break in them blocks the merge. |
| Section 3 (line 56) | The 27 corpus-marked modules under `tests/contract/` are listed in the router's `tests-corpus-blocking` job. | That job lists the reality check, its payload helper and the example round trip from `tests/contract/`, plus `tests/integration/test_mission_review_contract_gate.py`, `tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py` and one performance class. The other corpus-marked contract modules run in `tests (contract tools)`. Each module has one home. |
| Section 5 (lines 96 and 97); section 15.3 (line 310) | 541 or 544 Missions projected; 52 Missions on the disagreement list, ceiling 52. | 546 Missions, 3,193 work package payloads and 24,419 events on the landed tree. The ratchet is a shrink-only list of Mission names (`header.disagreeing_missions` in `tests/contract/fixtures/mission_status_expected.json`), and the ceiling equals the list length. The #5579 work package status backfill landed, and slice 5 lowered the ceiling from 52 to 8. Tracker #5579 stays open, drain by 2026-12-31. |
| Header paragraph on accepted risk P-10 (line 11); section 6 (line 105) | A change confined to the status readers or to `tests/contract/**` selects no job. | An edit under `tests/contract/**` now selects `tests (contract tools)`, which does not run the reality check. The reality check does not run on a pull request that edits only its own test files, its fixture, the status readers, or a Mission's `meta.json` or `status.events.jsonl`. The nightly interpreter shard 4 catches those. |
| Section 10 (lines 122 to 135) | Six open stacked pull requests; PR 6 "not opened"; "all five open pull requests are drafts". | Slices 1 to 5 are merged (16.1). PR 6 is #5582. #5568, #5577 and #5578 were closed and replaced by #5591, #5594 and #5606. |
| Post-merge steps, item 1 (line 247) | Merge the six pull requests bottom-up. | Five are merged. Only #5582 remains. |
| Section 14, item 2 (line 283) | PR 6 (seam 6) is not opened. | It is open as #5582. |
| Section 15.1 (line 298) | Slices 4 to 6 (#5578 and the two after it) were restacked. | #5578 was closed and replaced by a new pull request, #5606. #5581 and #5582 kept their numbers. |
| Section 15.4 (line 314) | The maintainer's folds on slice 4 are attributed to #5578. | The maintainer's landing folds on slice 4 are recorded on #5606, which replaced #5578. |
| Section 15.5 (line 322) | The release workflow is described as one gate. | `contracts-release.yml` has two jobs. A read-only `build` job runs every check and builds the assets. The `publish` job (`needs: build`) is the only one with a write token. It confirms that the tag still resolves to the built commit before it publishes. |
| Section 15.2 (line 304) | The tool tests were verified in the Contracts workflow with 28 corpus-marked modules, each with one home. | The two homes are now router jobs, `tests (corpus-blocking)` and `tests (contract tools)`. `tests/ci/test_contracts_workflows.py` still fails when a corpus-marked `tests/contract` module has no home or two. |

Section 14 gaps:

| Gap | Status |
| --- | --- |
| 1. Draft pull request bodies lack the section 13 items. | Superseded. The drafts it names were replaced or merged. Not re-verified against the body of #5582. |
| 2. PR 6 is not opened. | Closed: it is #5582. |
| 3. NFR-001 headroom, no full-mode `packs.yml` dispatch, run predates the fold rounds. | Superseded by section 15.2 and 16.4. Not re-measured. |
| 4. NFR-007 coverage paste not available. | Not re-verified. |
| 5. `wps.yaml` `owned_files` does not list the later appends. | Not re-verified. |
| 6. The scaffold commit subject reads the legacy wording. | Not re-verified. |
| 7. The `cutover-guard` block is unchanged. | Not re-verified. |
| 8. No preview tags published. | Not re-verified for the preview tags. No `contract-*` tag is published: the contract version is `1.0.0-SNAPSHOT`. |

### 16.3 Maintainer landing folds on slices 4 and 5

Slice 4 (#5606, merged 2026-10-03, seven folds):

1. The contract tool tests moved into the router job `tests (contract tools)`, a required check.
2. The release workflow split into a read-only `build` job and a `publish` job.
3. `breaking_check.py` also treats a new `default` or range (`4XX`/`5XX`) response (`response-key-added`), a write-only property that becomes readable, and added `patternProperties` as breaking.
4. `verify_pins` refuses a pin that has no `url`.
5. The Contracts workflow trigger paths grew from four to ten.
6. Pushes to `main` no longer cancel each other's Contracts runs (one concurrency group per commit).
7. The breaking-change baseline is the latest release tag reachable from the commit under test, ordered by semver 2.0 precedence, so prerelease versions order correctly.

Slice 5 (#5581, merged 2026-10-04):

1. The disagreement ratchet is pinned by Mission name and was lowered from 52 to 8 after the #5579 work package status backfill landed.
2. Work package history is sorted by parsed instant instead of by timestamp text.
3. Dropped rows are asserted.
4. The corpus floors require only stable values; transient lanes are covered by a fixture-built control.
5. Lane counts must account for `wpTotal`.
6. `tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py` got a merge-blocking home in `tests (corpus-blocking)`.

### 16.4 NFR-001

The 3m43s figure in section 15.2 was measured on the full-mode run 37131680223, before the slice 5 folds. It has not been re-measured on the landed tree. The slice 5 folds also gave `tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py` a home in that job. NFR-001 is met on the measured run and unconfirmed on the landed tree.

### 16.5 Accepted risk as it stands

Status-reader drift is not caught on the pull request. The reality check does not run on a pull request that edits only its own test files, its fixture, the status readers (`src/specify_cli/status/**`), or a Mission's `meta.json` or `status.events.jsonl`. The nightly interpreter shard 4 runs `tests/contract` daily and catches the drift up to a day later. The tracker is #5623. `contracts/README.md` and `docs/development/reference/ci-gate-mechanics.md` state the same risk.

### 16.6 Records not in this repository

The Mission's dossier files that are on `main` (`tracer-design-decisions.md`, `tracer-tooling-friction.md`, `research.md`, `plan.md`, `analysis-report.md`, `contracts/tools-and-workflows.md`) are the slice 1 snapshot. They are frozen: the archive rule allows new files in a Mission directory, not edits to existing ones. Entries that earlier sections of this file cite are therefore not in the repository. Each gap below was checked against the files on this branch:

| Cited record | What the repository holds |
| --- | --- |
| Design decisions DD-22 and later (DD-22 to DD-32 are cited in several earlier sections) | `tracer-design-decisions.md` stops at DD-21. |
| Tooling friction entries F-15 and later (cited in sections 1, 12 and 14) | `tracer-tooling-friction.md` stops at F-14. |
| `research.md` R-8 NFR-001 measurements, taken 2026-10-03 (cited in the NFR-001 section), and the R-5 job-name note (cited in the T074 table) | `research.md` R-8 holds only the baseline, and R-5 does not name `tests-corpus-blocking`. |
| The `plan.md` corrections P-9 and P-10, Reflexivity items 5, 7 and 8, the gate table and baseline step 5 (cited in "Planning-text corrections") | `plan.md` P-9 and P-10 still read "caught on push to `main` by `built-in-corpus-suite`", the reading the close-out calls superseded. |
| The re-analysis at commit `c80975b74` (cited in "Planning-text corrections") | The commit is not an object in this repository, and `analysis-report.md` does not mention it. |
| The update to `contracts/tools-and-workflows.md` that closes PR-DD32-001 (cited in section 15.2) | `contracts/tools-and-workflows.md` has no such update. Its job table lists nine jobs with `contracts-gate` needing eight, with no tool-test job. That now matches the landed workflow, because slice 4 moved the tool tests to the router, so the finding no longer needs an update. |

Section 12 says tracer entries were recorded on the Mission's planning branch; that branch is not in this repository, so where these records are now was not checked. They can be added later as new files in this Mission directory; they cannot be added as edits to the frozen files.

### 16.7 Status surface

`status.events.jsonl` and `status.json` in this Mission directory show every work package at `planned` (12 work packages; `status.json` was last materialized 2026-10-02), and `acceptance-matrix.json` shows `overall_verdict: pending`. The Mission's status surface was never updated after slice 1. The 13 review-cycle files under `tasks/` and this close-out are the record of what was reviewed. This section does not claim that the Mission is accepted in the matrix.
