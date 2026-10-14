---
work_package_id: WP05
title: '[PR A] P3 Resolved Work Package state in the reduction (FR-020, NFR-009)'
dependencies:
- WP03
- WP04
requirement_refs:
- FR-020
- FR-013
- NFR-009
- NFR-005
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T00:57:21.435790+00:00'
subtasks:
- T030
- T031
- T032
- T033
- T034
- T035
- T036
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/WpId.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/WpResolved.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/Assignment.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/ReviewResultRecord.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/ReviewOverrideRecord.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/HistoryRow.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/HistoryOrder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/ProjectionCache.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/derive/HistoryOrderTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/perf/Nfr009CacheGrowthTest.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/StatusEvent.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/StatusSnapshot.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/LedgerLine.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/WpId.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/WpResolved.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/Assignment.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/ReviewResultRecord.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/ReviewOverrideRecord.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/HistoryRow.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/HistoryOrder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/reducer/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/RowClassifier.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/LedgerLineDecoder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/ProjectionCache.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/reducer/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/StatusSnapshot*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/LedgerLine*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/WpId*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/WpResolved*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/Assignment*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/ReviewResultRecord*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/ReviewOverrideRecord*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/HistoryRow*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/derive/HistoryOrderTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/RowClassifier*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/LedgerLineDecoder*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/port/Ac5ReductionTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/perf/Nfr009CacheGrowthTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/perf/MissionCorpus.java
- services/mission-status-api/src/test/resources/portlevel-tests.txt
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/LineKind.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP05 – [PR A] P3 Resolved Work Package state in the reduction (FR-020, NFR-009)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: PR A (draft, stacked on the branch that carries #5529's last slice). **Phase tag**: P3 (plan section 11). WP05 is the first functional change of the mission (D-44): nothing functional lands before it, and P2, P4 and P5 (WP06, WP07, WP09) depend on it.
- **Work package dependencies**: WP04 (P3a), whose `M/data-model.md` is this WP's specification of the FR-020 mapping (read it first; this prompt never restates a mapping row), and WP03 (P1b). WP04 is the only `planning_artifact` WP and runs in the planning lane, whose branch carries no code commit; depending on WP03 directly gives this WP's lane the code lineage WP01 to WP03 (campsite, port seam, generalised gates) through its direct dependency lane, so every later PR A lane (WP06, WP07, WP09 and onward) inherits it transitively (TASKS-ORDER-001; D-44 is enforced by the lane graph, not by prose). Verify with `finalize-tasks --validate-only` that this WP's lane lists both the WP03 lane and the planning lane.
- **Precondition (lane lineage, TASKS-FRESH-005).** `M/data-model.md` is committed by WP04, a `planning_artifact` WP that runs in the planning lane on the target branch, not in a code lane; a code lane is cut from the tips of its code dependencies and receives only the recorded finalize-tasks planning commit, which predates WP04's commit. So before the first edit run `test -f kitty-specs/mission-status-read-api-mission-detail-01M4S6D5/data-model.md` in the lane workspace. If it is absent, STOP and report: the orchestrator must merge the target branch (carrying WP04's committed `data-model.md`) into this lane before work resumes (OO-5). Never create the file here: this WP only reads it, and creating a second copy would give an add/add conflict when the lanes merge.
- **External dependency (not a `dependencies` entry)**: WP01 could not start until the orchestrator merged the re-cut tip of #5529 (the side-first layout) into this branch, and the P0 baseline record (`M/traces/baseline-red.yaml` and the `test_baseline_record_*` tests) is committed. #957 cannot merge before #5529 (C-005). No agent pushes, opens or retargets a pull request; #5533's Java work stacks on PR A.
- **Named edits (out-of-map; not in `owned_files`)**. For each: rebase first, state the edit in the commit message, touch nothing else of the file.
  1. `R/jacoco-class-floor.properties`, the `domain` count line only (owner: WP01). The number is the one the plan section 2 command prints at the commit that adds the domain classes; the `application` line is not touched (WP05 adds no `application` class; `ProjectionCache.java` is expected unchanged).
  2. `M/traces/nfr009-base.md`: a new file, a P3 output under `kitty-specs/` (a `code_change` WP may not own a `kitty-specs/` path, `INVALID_WP_OWNED_FILES_KITTY_SPECS`, hence a named edit).
  3. `M/traces/approach.md`: append-only tracer entry. If T030 needs the alternative control of the plan section 6 item 5, a `M/traces/design-decisions.md` entry is appended the same way. Tracer files are never in `owned_files`.
  (`J/domain/model/LineKind.java` is in `owned_files`: edit it normally, it is not a named edit; see "Plan defects found", item 1.)
- **Write scope**: `owned_files` only, plus the named edits above. Nothing else is touched.
- **Aliases used below**: `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`. Paths of the side-first layout (`J/domain/readmodel/...`, `J/application/query/...`) exist after the #5529 re-cut; they are the right-hand column of the plan section 1.1 mapping table. At this checkout the flat names still exist (`J/domain/reducer/StatusReducer.java`, `J/application/ProjectionCache.java`), and the C-005 pre-flight (T030 step 1) is what proves which layout you are on.

## Objective

Make the Java reduction produce the resolved Work Package state the detail routes need (assignment handles, the subtask map, the latest review result and the review override, the actor of the latest change, the ordered transition history, and the lifecycle types of the ledger), without moving one byte of the overview, and prove with `Nfr009CacheGrowthTest` that caching it stays within NFR-009.

## Context

- **Why**: FR-020. `WpState` keeps `lane`, `lastTransitionAt`, `lastEventId`, `forceCount`, the cancellation provenance and `implementerOfRecord`. The Work Package routes (WP13 to WP16, PR B) need the rest of what `materialize_snapshot` and `reconstruct_wp_view` resolve. The reduction is framework-free `domain`, under the same `(at, event_id)` ordering and the same oracle gate as #5529's reduction (spec FR-020, AC-20.1 to AC-20.5).
- **Shape (plan 1.2, 11, 13)**. New `domain.model` records `WpId`, `WpResolved`, `Assignment`, `ReviewResultRecord`, `ReviewOverrideRecord`, `HistoryRow`; new `domain.readmodel.derive.HistoryOrder`; reducer additions in `domain.readmodel.reducer`; `StatusSnapshot` gains a **parallel** `resolved` map and `lifecycleTypes` (`WpState` is not touched, which is why the overview cannot move); `LedgerLine` gains a nullable `eventType` (D-98). The four-argument `StatusSnapshot` constructor stays. `ProjectionCache.Entry` already holds the whole `StatusSnapshot`, so `ProjectionCache.java` and `OverviewDeriver` are expected unchanged; if a change is needed, the commit message says why.
- **Typed identifiers (E-5, D-150)**. `WpId.parse(String)` returns `Optional<WpId>`, never throws, and is unit-tested in `WpIdTest`. Adapters (PR B) turn an empty result into `not_found`; this WP only provides the factory.
- **D-98 (markers rule)**. `lifecycleTypes` is derived by the oracle's rule from the new nullable `LedgerLine.eventType`, so a phase marker row without a string `event_id` or `timestamp`, which the oracle counts and a classification-based derivation (`RowClassifier.lifecycleOrIgnored` yields `Ignored` for it) would drop, is still counted.
- **Red-first form (plan section 11, P3)**: red on the phase base (the new members are absent), green on the tip. Two honest qualifications are in "Plan defects found" (item 4): the unit tests of T031 to T034 are the red ones; `Nfr009CacheGrowthTest` is committed first with no production line and is green at that commit by design.
- **E-7 is given**: the NFR-009 base-commit figure is taken locally in this WP, with `perfTest` (the plain `test` task excludes the tag `perf`, `S/build.gradle.kts`). CI remains the authority; a miss is classified, never retried.
- **Golden dependence**: the golden-dependent AC-20.1 members (the oracle's resolved-state goldens of WP08 and `ResolvedStateGoldenTest` of WP10) do not exist at this tip. Nothing in WP05 reads `R/conformance/resolved-state/**`; the unit and `Ac5ReductionTest` expectations are hand-written from the `M/data-model.md` mapping.

### Subtask T030: First commit - Nfr009CacheGrowthTest, the MissionCorpus option, the base figure

**Purpose**: Establish the NFR-009 measurement before any production line changes, so the base-commit figure and the same-run floor exist (plan section 6 item 5, D-112, D-127, S-24).

**Steps**:
1. **C-005 pre-flight, first step of the phase (D-107)**, run before writing anything, from the repository root. Stage nothing yet; this is read-only.
   ```bash
   export LC_ALL=C.UTF-8
   .venv/bin/python contracts/tools/bundle.py --root contracts --out "<scratch>/bundle-out" --module mission-status --bundle-only
   export CONTRACT_BUNDLE="<scratch>/bundle-out/bundle/mission-status/openapi.yaml"
   export CONTRACT_BUNDLE_SHA256="$(sha256sum "$CONTRACT_BUNDLE" | cut -d' ' -f1)"
   cd services/mission-status-api && ./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'
   cd ../.. && git log -1 --format=%H refs/remotes/m5529/lane-b      # or the ref that carries the merged #5529 tip; record the sha in the FIRST commit message
   grep -rnE '"org\.speckitty\.missionstatus\.(application|domain)' services/mission-status-api/src/test services/mission-status-api/build.gradle.kts
   grep -rnE 'application/port|domain/(overview|reducer|projection|paging|cursor)' tests scripts .github
   ```
   `<scratch>` is a directory OUTSIDE the repository (`bundle.py` refuses one inside). The `CoupledSymbolsShapeTest` is green on the re-cut tree; a red means the tree is not the re-cut layout, stop and report. Every grep hit must name a class of the right-hand column of the plan section 1.1 table or a JaCoCo wildcard; the second grep is empty from the end of WP01.
2. Add `T/perf/Nfr009CacheGrowthTest.java`: `@Tag("perf")` on the class (the pin `tests/ci/test_mission_status_api_build.py` requires the tag on every class holding a `@Test`, `perf_class_violations`). Model the heap sampling on `Nfr004SseConnectionsTest` (it exposes `HEAP_SAMPLES >= 3` and a `median(long[])`, package-private in the same `perf` package): force a collection, take at least three GC-settled samples, use the median. Name the constants `CEILING_BYTES = 64L * 1024 * 1024` (NFR-009, INITIAL and PROVISIONAL, ADR `2026-10-05-2`).
3. **Same-run floor (D-127)**. In one run, build the corpus twice over public API only: (a) the **real leg**: for each Mission decode the ledger with `LedgerLineDecoder.decode(byte[])` and reduce with `new StatusReducer(<the production EventOrdering>).reduceLines(lines)`, retaining every `StatusSnapshot` in a list; (b) the **history-less leg**: the same snapshots rebuilt through the four-argument `StatusSnapshot(Map, int, String, String)` constructor (that constructor stays, T033), so the retained entries carry no resolved map and no lifecycle types. The asserted quantity is `retained(real) - retained(historyless)`, which must be at most `CEILING_BYTES`. At the first commit the two legs are structurally equal, so the difference is near zero: that is the base shape, and it is why the commit has no production line.
4. **Sensitivity control** (AC-20.5 "Control"): a third leg that retains ten times the resolved history of the real leg (for example ten copies of each snapshot's resolved structure in a plain holder list) must measure strictly more growth than the real leg by a stated factor, so the measurement can see growth. Assert the factor, not the 64 MB figure, because the control's absolute size depends on the corpus; record the measured numbers in the output. At the first commit, before `resolved` exists, write the control over a stand-in structure (a list of strings of a stated size) so it is green and runs, and strengthen it in T033 when `resolved` exists (the strengthening is part of that commit).
5. Add the **additive corpus option** to `T/perf/MissionCorpus.java`: a method such as `nfr009Spec(int missions)` and `writeNfr009(int missions)` generating `missions` Missions, each with **10 Work Packages and 100 transition rows, ten per Work Package**: `planned->claimed`, `claimed->in_progress`, three rework rounds of `in_progress->for_review` then `for_review->in_progress`, then `in_progress->for_review` and `for_review->approved` (2 + 6 + 2 = 10). Timestamps ascending, ids synthetic, seed `SEED`. Existing `spec(int)`, `write(int)`, `ledger(int, Random)` and every caller (`Nfr001OverviewLatencyTest`, `Nfr004*`, `PerfServer`) are untouched. P13 (WP18) later adds the NFR-001 detail shape to this file as its own additive named edit; do not pre-build it.
6. Pin the generated counts with a unit assertion **inside `Nfr009CacheGrowthTest`** (a `@Test` of the same tagged class, so the pin is satisfied): 500 Missions, 10 Work Packages each, 100 rows each, every Work Package's ten rows in the order above. It runs in `perfTest`, not in `test`.
7. Commit this as the first commit of the WP (message prefix `test(perf)`, the #5529 tip sha in the body). **Then take the base figure** at that commit, in a scratch worktree so the working checkout does not move (no checkout, no switch, no stash):
   ```bash
   git worktree add "<scratch>/nfr009-base" <sha of the commit just made>
   cd "<scratch>/nfr009-base/services/mission-status-api" && LC_ALL=C.UTF-8 ./gradlew --no-daemon perfTest --tests 'org.speckitty.missionstatus.perf.Nfr009CacheGrowthTest'
   ```
   (the bundle variables of step 1 are exported). Remove the scratch worktree afterwards by its literal path with `git worktree remove "<scratch>/nfr009-base"`; never with a glob or a variable-built `rm`.
8. Write `M/traces/nfr009-base.md` (new, a named edit): the retained-heap figures of the real leg and the history-less leg, the difference, the command, the date, the commit sha and the JVM version. State that the figure is a corroboration taken once under E-7 (S-24), not a condition of the criterion; the criterion is asserted by CI's `perfTest` through the same-run floor. Append a one-line entry to `M/traces/approach.md`.

**Files**: `T/perf/Nfr009CacheGrowthTest.java` (new, about 150 lines), `T/perf/MissionCorpus.java` (edit, about +60 lines, additive), `M/traces/nfr009-base.md` (new, about 30 lines).

**Validation**: `perfTest --tests ...Nfr009CacheGrowthTest` green at the first commit with a printed difference near zero; the shape assertion green; `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` green (stage the new files first so the tracked-path scan sees them).

### Subtask T031: Domain records WpId, WpResolved, Assignment, ReviewResultRecord, ReviewOverrideRecord, HistoryRow

**Purpose**: The value objects the reducer, the decoders and (PR B) the index and mappers share. They stay in `domain.model` so the codec classes may return them (rule 12a) and the application may consume them (rule 2b).

**Steps** (red-first: write each `*Test` before the record; confirm red, then green):
1. `J/domain/model/WpId.java`: `public record WpId(String value)`; compact constructor rejects null and any value not fully matching `^WP[0-9]{2,}$` (use `Pattern.matcher(...).matches()`, ASCII digits only; contract `schemas/WpId.yaml` is the rule: letters `WP` and at least two digits, `maxLength` 64). `public static Optional<WpId> parse(String raw)`: the **lenient** factory, `Optional.empty()` for null, empty, `WP1`, `wp01`, a trailing newline or space, an Arabic-Indic digit, a value over 64 characters; **never throws**. `WpIdTest` (`T/domain/model/WpIdTest.java`) pins all of these and that `new WpId(...)` throws for an ill-formed value while `parse` does not (revert-fails: make `parse` throw, or accept `WP1` or a lowercase value, and `WpIdTest` goes red; this is the "Typed identifiers (E-5, D-150)" row of the plan revert table).
2. `Assignment`: the seven handles of the contract's `Assignment` (`agent`, `assignee`, `role`, `agentProfile`, `agentProfileVersion`, `model`, `provider`), each nullable text. The **model-absent sentinel** (`__resolved_model_absent__` and its profile, profile-version and provider siblings) is shown as null, never as the sentinel string (AC-20.1); `Actor` already holds the sentinel set for handles, reuse that rule rather than a second list (single canonical authority). Compare the exact field list with the `M/data-model.md` table; the table wins.
3. `ReviewResultRecord`: `reviewer`, `verdict`, `reference` (contract `ReviewResult.yaml`; the verdict vocabulary is `ReviewVerdict.yaml`). `ReviewOverrideRecord`: `complete`, `at`, `actor`, `reason` (contract `ReviewOverride.yaml`: a partial record has `complete=false` and a null `at` or `reason`; a release marker is a complete or partial record per the mapping). `HistoryRow`: one transition (`eventId`, `at`, from lane, to lane, `force` true only for the literal `true`, `reason`, `actor`, and the review verdict the mapping names; contract `HistoryEntry.yaml`). `WpResolved`: the aggregate for one Work Package: `Assignment assignment`, the subtask map (insertion-ordered `Map<String, Lane>` or the type the mapping names), `ReviewResultRecord reviewResult` (nullable), `ReviewOverrideRecord reviewOverride` (nullable), `Actor actor` (the latest change's actor, `Actor.NONE` when none), `List<HistoryRow> history` (unmodifiable). Compact constructors null-check, copy collections unmodifiable, and keep the records framework-free (rule 1: no Spring, no JSON, no file API).
4. One unit test file per record under `T/domain/model/` matching the owned globs (`Assignment*Test`, `ReviewResultRecord*Test`, `ReviewOverrideRecord*Test`, `HistoryRow*Test`, `WpResolved*Test`, `WpId*Test`): construct, null-check, defensive copy, and for `Assignment` the sentinel-to-null rule.

**Files**: six records (about 20 to 60 lines each), six test files.

**Validation**: `cd S && LC_ALL=C.UTF-8 ./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.domain.model.*'` green; each test was seen red first (record the red run in your notes).

### Subtask T032: HistoryOrder and the reducer fold

**Purpose**: Produce the resolved members in the reduction, under the same `(at, event_id)` ordering as the lane fold.

**Steps**:
1. `J/domain/readmodel/derive/HistoryOrder.java` (the first class of the new `derive` package; `HistoryOrderTest` in `T/domain/readmodel/derive/`): a `Comparator<HistoryRow>` (or a static `order(List<HistoryRow>)`) that orders **transitions only** by the **parsed instant** then `eventId`. A stamp that is not an instant sorts last (oracle behaviour, plan 8 FRESH3-003 row T13: "stored text, sorted last when not an instant"); use `domain.readmodel.overview.Instants.parse` (it throws `InvalidInstantException` on junk; catch it inside the comparator's key function, do not let it escape). AC-20.3: a ledger mixing `Z`, fractions and offsets orders by instant, not by text; `force` is true only for the literal `true` (`RowClassifier.truthy` is today's rule; a truthy non-boolean such as `1` or `"yes"` is false for history).
2. Fold in `J/domain/readmodel/reducer/` (checkout name `J/domain/reducer/`): extend `StatusReducer` minimally and put each member that needs more than a few lines in a **small class of the same package** (for example `ResolvedFold`, `HistoryFold`) rather than growing `StatusReducer` (176 lines today; plan section 9 row). The fold sources are exactly the rows of `M/data-model.md`: assignment, subtasks, review result, review override, actor and ordered history, each with the cited source symbol (`spec_kitty_events.diary.reduce_parsed`, `specify_cli.status.reducer.wp_snapshot_state`, `specify_cli.status.wp_view.ResolvedGroup`).
3. Respect the existing structure for the **lane fold and the other resolved members**: dedup by `event_id` (first occurrence in file order for the fold, first in sorted order for the two read-only projections), sort by the injected `EventOrdering`, fold with the rollback-aware `shouldApply`. **`history` is the exception (ruling OO-1: port what Python runs):** it is built from the raw rows, one entry per `to_lane` row of the Work Package, with no `event_id` de-duplication and no rollback arbitration, then ordered by `HistoryOrder`; a unit test pins a duplicated `event_id` (both rows listed) and a row the arbitration drops (listed). The other new members follow the **projection** shape (`project(...)` over the unique sorted events) unless the mapping says a member is set by the fold itself; the mapping decides, you do not.
4. A Work Package known only from annotation rows is held in the non-display `uninitialized` lane today; its resolved members may still come from the annotation `delta` (subtasks, review override). The annotation pass must therefore carry the delta; see T033 for the carrier.
5. Keep `StatusReducer` pure: no clock, no I/O, no framework (AC-20.4, rule 1). A reducer that always returns empty members must be red on the non-empty ledgers (AC-20.1 control): the unit tests include one ledger with none of the members (all empty) and several that set them.
6. Tests in `T/domain/readmodel/reducer/**` (owned glob; the checkout name is `T/domain/reducer/StatusReducerTest.java` and `Events.java`): extend the existing reducer test style; build fixtures in a helper inside this directory (do **not** edit `T/testsupport/Rows.java`, which no WP owns): a transition that sets each member, a later transition that overwrites it, a transition that clears it, the model-absent sentinel, a review result with each verdict, a partial and a release-marker override, annotation rows between transitions, equal `at` with different `event_id`, and a duplicated `event_id`.

**Files**: `HistoryOrder.java` (about 60 lines), one or two fold classes (about 80 to 150 lines), `StatusReducer.java` (small edit), tests (about 300 lines).

**Validation**: `test --tests 'org.speckitty.missionstatus.domain.readmodel.reducer.*' --tests '*HistoryOrderTest'` green; revert row: text-order history makes the AC-20.3 test red; an annotation row in `history` makes it red; `force` true for a truthy non-boolean makes it red.

### Subtask T033: StatusSnapshot, StatusEvent, LedgerLine, RowClassifier, LedgerLineDecoder

**Purpose**: Carry the members from the ledger bytes to the reducer without breaking any existing caller.

**Steps**:
1. `StatusSnapshot` (`J/domain/model/StatusSnapshot.java`, a record of four components today): add the **parallel** components `Map<String, WpResolved> resolved` and `Set<String> lifecycleTypes` (the oracle's `_lifecycle_types` in `tests/contract/_mission_status_payloads.py` is a `frozenset` of the string `event_type`s of the ledger rows, so duplicates collapse; keep insertion order for determinism; the consumer is `PhaseDeriver` in WP13; the mapping and D-98 decide any detail). **Keep the four-argument constructor** `(Map<String, WpState>, int, String, String)` delegating with empty parallel members, because the same-run floor of T030, `StatusSnapshotTest`, the existing reducer tests and `ProjectionCache` fixtures all use it. Compact constructor: unmodifiable copies, insertion order preserved like `workPackages`.
2. `LedgerLine` (`J/domain/model/LedgerLine.java`): add a nullable `String eventType` component; **keep the four-argument constructor** `(long, String, long, LineKind)` (eventType null) so every `new LedgerLine(...)` of the tests compiles unchanged. `LedgerLineDecoder` sets `eventType` from the row's own `event_type` string whenever the document has one, **independently of the classification** (`RowClassifier.lifecycleOrIgnored` yields `Ignored` for a marker row lacking a string `event_id` or `timestamp`; the oracle still counts it). `lifecycleTypes` is then derived by the oracle's rule from the `eventType`s of the decoded lines (D-98), not from `LineKind.Lifecycle`.
3. `StatusEvent` (`J/domain/model/StatusEvent.java`, eleven components, two constructors today): add nullable members for what the status row carries toward the resolved state (the verdict and reviewer of `review_result`, the done-evidence review reference as the mapping names it, the claim assignment handles the mapping names). **Keep both existing constructors** (the ten-argument one defaults `actor` to `Actor.NONE`). Extend the same way as you extend the others: additive, defaulting.
4. `RowClassifier` (`J/adapter/out/filesystem/codec/RowClassifier.java`, 284 lines of small static predicates; plan section 9 row says add one predicate per member in the same style, do not extract): `status(row)` already validates `evidence` and `review_result` (`validEvidence`, `validReviewResult`); read their values into the new `StatusEvent` members. `annotation(row)` validates `delta.subtasks`, `delta.review` and the other delta members but returns `new LineKind.Annotation(wpId)` and drops them; the fold needs them. Carry the decoded delta (subtasks map, review override, and any other delta member the mapping names) on the annotation result. The carrier is `LineKind.Annotation`, see "Plan defects found" item 1: widen that record by additive components with a one-argument compatible constructor (`Annotation(String wpId)` stays) as an ordinary edit of an owned file (`LineKind.java` is in `owned_files`).
5. Keep rule 12a (the codec depends on `domain` only) and rule 12 (no file API in the codec). `LedgerLineDecoder` keeps its own inline strict-UTF-8 helper untouched (D-116: the older copies are left alone by design).
6. Tests (owned globs `RowClassifier*Test`, `LedgerLineDecoder*Test`, `LedgerLine*Test`, `StatusSnapshot*Test`): a status row with a review result yields the new members; an annotation row with a delta yields the carried subtasks and override; a malformed `delta` stays `UNUSABLE_ROW` exactly as today (no existing assertion changes); a marker row without `event_id`/`timestamp` still yields `eventType` and is counted in `lifecycleTypes`; `StatusSnapshot` four-argument constructor yields empty parallel members and equal `laneCounts()`.

**Files**: `StatusSnapshot.java`, `LedgerLine.java`, `StatusEvent.java`, `RowClassifier.java`, `LedgerLineDecoder.java` (each a small additive edit), tests (about 250 lines).

**Validation**: all pre-existing tests of those classes pass **unchanged** (`git diff` of the existing test files shows no changed assertion); `LedgerLineDecoder` and `RowClassifier` tests green; strengthen the T030 sensitivity control now that `resolved` exists and re-run `Nfr009CacheGrowthTest` locally (E-7): the difference stays within `CEILING_BYTES`, record the number.

### Subtask T034: ProjectionCache stays unchanged; Ac5ReductionTest; AC-20.2

**Purpose**: Show the cache and the overview did not move.

**Steps**:
1. Confirm `J/application/query/ProjectionCache.java` (package-private, owned) needs no edit: `ProjectionCache.Entry` already holds the whole `StatusSnapshot`, and `OverviewDeriver` reads `workPackages()` and `laneCounts()` only. If a change turns out to be needed, make it, and state in the commit message exactly why (plan 11 P3 row). Likewise `OverviewDeriver` (not owned) must not change.
2. Extend `T/conformance/port/Ac5ReductionTest.java` (owned; it is in the port-level class set: methods carry `@PortLevelTest("<id>")`; every new id must open its fixture through `PortFixtures`/`PortSourceSelector` exactly as the existing methods do, because `PortSubsetSecondLegTest` runs every listed id on the in-memory and the filesystem source and requires each to open a selector fixture, and `PortLevelClassSetTest` requires the class to depend on the selector or `PortFixtures`: a method that calls the reducer directly is red on both) with port-level methods for the new members, for example `@PortLevelTest("AC-20/resolved-members")`, `@PortLevelTest("AC-20/history-order")`, `@PortLevelTest("AC-20/empty-members-control")`. Keep the three existing methods and `AC-5c` untouched. The tests drive the service/reducer through the same source-neutral port path the file already uses; hand-written ledgers only (no golden file dependency).
3. AC-20.2: run the unchanged overview goldens (`GoldenSuiteTest`, `ProjectAndPagingTest`, `GoldenRoutesTest`) and the reduction tests of #5529 without editing them; they are green on the tip. No overview byte moves.
4. AC-20.4: `ArchitectureRulesTest` (rules 1 and 12) passes with the new members; `StatusReducerTest` runs with no Spring context.

**Files**: `Ac5ReductionTest.java` (edit, about +120 lines).

**Validation**: `test --tests '*Ac5ReductionTest' --tests '*GoldenSuiteTest' --tests '*ArchitectureRulesTest' --tests '*PortLevelClassSetTest' --tests '*PortSubsetSecondLegTest'` green.

### Subtask T035: portlevel-tests.txt and the JaCoCo domain count

**Purpose**: Keep the two count/census files satisfiable at this tip.

**Steps**:
1. `R/portlevel-tests.txt` (owned): add one line per new `@PortLevelTest` id of T034, in the file's grammar (`<id> <ClassName>#<method>`; the class is the simple name of a top-level class in `conformance.port`; comments start with `#`). `PortLevelClassSetTest` compares the annotated methods with the listed lines **as sets**; an id in one and not the other is red. The route phases (WP13 to WP16) append **no** line to this file: their port-level legs live outside `conformance.port` and are not listed (see their prompts; TASKS-GREEN-001).
2. `R/jacoco-class-floor.properties` `domain` line (**named edit**, owner WP01): after the classes exist, run from `S` the section 2 command and write the number it prints for `domain` at the commit that adds the classes:
   ```bash
   cd services/mission-status-api && LC_ALL=C.UTF-8 ./gradlew --no-daemon test jacocoTestReport
   python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"
   ```
   The count includes nested classes and records. Floor semantics (D-65): a stale or understated count is **not** detected by `jacocoScopeCheck`, so recount at the commit that adds the last domain class and again if a fold commit adds one. The `application` line is left as it is. State the edit in the commit message.

**Files**: `R/portlevel-tests.txt` (a few lines), `R/jacoco-class-floor.properties` (one line, named edit).

**Validation**: `PortLevelClassSetTest` and `PortSubsetSecondLegTest` green; `jacocoScopeCheck` green.

### Subtask T036: Gate

**Purpose**: Exit the phase on the plan's gate set.

**Steps** (all under `LC_ALL=C.UTF-8`, bundle variables exported, new files staged first):
1. C-005 pre-flight again (T030 step 1) on the final tree.
2. **Gate G**: `cd services/mission-status-api && ./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`, with `PortLevelClassSetTest` and `PortSubsetSecondLegTest` named explicitly in the run (this WP appends ids to `portlevel-tests.txt`; both gates fail on an id that opens no selector fixture).
3. **Gate P**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` (the new `Nfr009CacheGrowthTest` holds a `@Test`, so `perf_class_violations` requires its `@Tag("perf")`; the tracked-path scan reads `git ls-files` of `S`).
4. `Ac5ReductionTest`, `WpIdTest`, `HistoryOrderTest`, the reducer and codec tests (named in T031 to T034).
5. AC-20.2: the overview goldens unchanged and green.
6. AC-20.5 by the single named class: `./gradlew --no-daemon perfTest --tests 'org.speckitty.missionstatus.perf.Nfr009CacheGrowthTest'` locally (E-7) at the tip; the difference to the base figure in `M/traces/nfr009-base.md` is noted in the PR "Tests run" material. CI's `perfTest` asserts the same-run floor; a local green replaces no CI leg.
7. Python hygiene is not required (no Python file changes); the Windows-filename guard `tests/architectural/test_no_invalid_windows_filenames.py` after staging new files.
8. NFR-006 terminology grep (plan section 5; expect empty): `grep -rnE '(^|[^A-Za-z])[Ff]eatures?([^A-Za-z]|$)|feature_' services/mission-status-api/src/main services/mission-status-api/README.md`.

**Validation**: all of the above green; record exact commands and counts in the hand-off notes.

## Self-contained green

This WP's tip, and PR A's tip with it, must be green on every CI gate alone (plan section 11, "Each PR is self-contained and green at its own tip").

- **Fixtures with their tests**: every ledger used by the new reducer, codec and `Ac5ReductionTest` tests is written inside those tests or a helper under `T/domain/readmodel/reducer/**`; the `Nfr009CacheGrowthTest` corpus is generated at test time by the additive `MissionCorpus` option and committed nowhere. No test reads `R/conformance/resolved-state/**` (WP08) or `ResolvedStateGoldenTest` (WP10): plan section 11 P3/P4b/P7 rows.
- **Floors and counts satisfiable here**: the `domain` count of `R/jacoco-class-floor.properties` is recounted at the adding commit (section 2 command); the `application` count is untouched because no application class is added; the portlevel ids of T034 are listed in `R/portlevel-tests.txt` in the same commit (`PortLevelClassSetTest`). No class floor of the conformance tree changes (WP07 and WP08 own `DETAIL_CLASS_FLOORS`). WP07 raises nothing that WP05 needs.
- **No forward reference**: no test or gate of this WP names a type of a later WP (`MissionDetail`, `WorkPackageView`, `ProjectionRow`, `DetailFixture`, `ServedRoute` and the rest are WP07, WP10 and later). `WpId` is used by WP11 (the index) and the route WPs and exists here first, which is the dependency direction the plan requires (section 11, "Green at every tip").
- **Pin `tests/ci/test_mission_status_api_build.py` clauses kept green**: the `@Tag("perf")` rule (`Nfr009CacheGrowthTest`, `perf_class_violations`; at least two perf classes already exist), the tracked-path scan of `S` (Windows-illegal and shell-expansion characters; floor 300 paths), the probe list (WP01's, not touched), the rule-9 literals and `EventsController` needles (not touched). No `build.gradle.kts` change here, so no models-list clause moves.
- **Mission record**: `M/meta.json` is not touched; `M/status.json` is whatever `spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5` produces from the committed `status.events.jsonl`, never hand-edited, and no untracked CLI state is committed blind (compare with the coordination copy first). `M/traces/nfr009-base.md` and the tracer appends are add-only (archive-freeze: `M/**` is not on `main` while PR A is open). That keeps `cutover-guard` (after the retarget), `mission-state audit` (`.venv/bin/spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json`, run before any push of an `M/**` change) and `corpus-blocking` passing (plan section 11, Mission-record bullet).
- **Native**: no new bean and no resource; nothing for the native legs to miss.

## Plan defects found

1. **Resolved: `LineKind.java` is in `owned_files`.** `RowClassifier.annotation` drops `delta.subtasks` and `delta.review`; the carrier is `LineKind.Annotation` in `J/domain/model/LineKind.java`, which this WP owns (wps.yaml and the frontmatter). Edit it as an ordinary owned file with an additive, constructor-compatible change; no out-of-map rationale is needed.
2. **Resolved: the history-less control uses the public-API variant.** `ProjectionCache` and `Entry` are package-private, so `Nfr009CacheGrowthTest` (package `perf`) retains `StatusSnapshot` instances and rebuilds them through the four-argument constructor, which measures the same payload because `Entry` holds the whole snapshot. No test-tree hook is added and no path outside `owned_files` is needed (TASKS-COVER-010 a). Record the choice in `M/traces/design-decisions.md`.
- **RULED: OO-1 (orchestrator ruling 2026-10-13, binding; see WP04)**: `history` is the oracle's `history_entries`: every `to_lane` row of the Work Package (a duplicate-`event_id` row and a row the rollback arbitration drops included), ordered by `HistoryOrder`; no `event_id` de-duplication, no rollback arbitration for `history`. Implement T032 on this rule; nothing waits for a further ruling.
3. `T/testsupport/Rows.java` is unowned: the resolved-state ledgers are built locally (T032 step 6). Not a defect, a boundary.
4. **Red-first ambiguity.** Plan section 11 says P3 is "red on the phase base". True for T031 to T034 (new members absent). `Nfr009CacheGrowthTest` is the first commit with no production line, so it is green at that commit by design; its job is the base figure and, from T033 on, the same-run floor. A reviewer must not demand a red run of it on the base.

## Definition of Done

- `WpId` with lenient `parse`, `WpResolved`, `Assignment`, `ReviewResultRecord`, `ReviewOverrideRecord`, `HistoryRow` exist with unit tests, each seen red before green (T031).
- `HistoryOrder` and the reducer fold produce assignment, subtasks, review result, review override, actor and ordered history equal to the `M/data-model.md` mapping; text-order history, annotation rows in history, and truthy non-boolean `force` are each red under mutation (T032).
- `StatusSnapshot` carries the parallel `resolved` and `lifecycleTypes` with the four-argument constructor kept; `LedgerLine.eventType` is nullable with the four-argument constructor kept; marker rows are counted (T033).
- `ProjectionCache.java` unchanged (or the reason is in the commit message); `Ac5ReductionTest` extended; overview goldens unchanged (T034).
- `R/portlevel-tests.txt` and the JaCoCo `domain` count updated in the adding commits (T035).
- Gate G (with `PortLevelClassSetTest` and `PortSubsetSecondLegTest` named), Gate P, the NFR-006 terminology grep (empty), `Ac5ReductionTest`, AC-20.2 and the local `Nfr009CacheGrowthTest` run recorded; `M/traces/nfr009-base.md` written (T036).
- Evidence of subtask completion is `.venv/bin/spec-kitty agent tasks mark-status <Txxx> --status done --mission mission-status-read-api-mission-detail-01M4S6D5` per subtask (event-sourced), not a ticked checkbox.

## Risks

- **Overview drift** (AC-20.2): any change to `WpState` or to the overview derivations moves a golden. Mitigation: the resolved state is a parallel map; run the overview goldens after every commit.
- **Understated JaCoCo count**: floor semantics hide it. Mitigation: recount with the section 2 command at the adding commit and after any fold commit; the PR A tip comparison is WP12's gate (T088); the PR B tip comparison is WP17's (T125), re-run by WP18.
- **Heap measurement noise**: a single sample proves nothing. Mitigation: GC-settled median of at least three samples, a ratio-style same-run floor and a sensitivity control; a miss is classified, never retried to green (ADR `2026-10-05-2`).
- **Mapping drift**: if `M/data-model.md` and the contract schema disagree on a member, the mapping (a reviewed WP04 output) is the authority; report the disagreement, do not pick silently.
- **Adjacent coupled files**: `RowClassifier` is a flat table of predicates; keep each new member to one predicate in the existing style.
- **Concurrency**: parallel lanes (WP06 and WP07 run beside WP09) share `R/jacoco-class-floor.properties`; a lane merged second recounts on the merged tree (shared-file table merge rule, D-145).

## Reviewer Guidance

- Verify the red-first form of **this** phase: the new unit tests were red on the base; `Nfr009CacheGrowthTest` is green at its first commit by design (item 4 above); do not sign a vacuous red.
- `git diff` of every pre-existing test file shows no changed assertion, expected value or golden byte (AC-20.2); the overview goldens are untouched.
- The four-argument constructors of `StatusSnapshot` and `LedgerLine` still exist and are used by the floor leg and the old tests.
- Check `RowClassifier` still returns `UNUSABLE_ROW` for exactly the rows it did before; the new members never change which rows are unusable.
- `domain` stays framework-free: ArchUnit rules 1 and 12 pass; no `java.nio` file API, no reflection; `HistoryOrder` lives in `domain.readmodel.derive`.
- The JaCoCo `domain` count in the diff equals the number the section 2 command prints at the adding commit; the `application` line is unchanged.
- The commit messages: the first carries the #5529 tip sha and the `test(perf)` prefix; the JaCoCo and `LineKind` edits are stated as named edits.
- `M/traces/nfr009-base.md` carries figure, command, date, sha; no home path, user name or token appears anywhere in it.
- Run the implied architectural gates by name (`ArchitectureRulesTest`, `ArchitectureControlsTest`, `PortLevelClassSetTest`), not the bare `tests/architectural` directory.

## Implementation command

```bash
.venv/bin/spec-kitty agent action implement WP05 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
