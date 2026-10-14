---
work_package_id: WP07
title: '[PR A] P4 Oracle extension, goldens and the paired Java census (FR-014 Python half, D-109)'
dependencies:
- WP05
- WP04
requirement_refs:
- FR-014
- FR-006
- FR-021
- NFR-004
- NFR-007
- SC-001
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T03:26:25.281459+00:00'
subtasks:
- T044
- T045
- T046
- T047
- T048
- T049
- T050
- T051
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/DetailManifestCensusTest.java
execution_mode: code_change
model: sonnet
owned_files:
- tests/contract/_mission_status_conformance.py
- tests/contract/test_mission_status_conformance.py
- services/mission-status-api/src/test/resources/conformance/manifest.json
- services/mission-status-api/src/test/resources/conformance/detail-populated/**
- services/mission-status-api/src/test/resources/conformance/detail-early/**
- services/mission-status-api/src/test/resources/conformance/detail-planning-only/**
- services/mission-status-api/src/test/resources/conformance/phases-matrix/**
- services/mission-status-api/src/test/resources/conformance/wp-malformed-frontmatter/**
- services/mission-status-api/src/test/resources/conformance/wp-duplicate-id/**
- services/mission-status-api/src/test/resources/conformance/wp-two-selectors/**
- services/mission-status-api/src/test/resources/conformance/wp-prompt-bytes/**
- services/mission-status-api/src/test/resources/conformance/cycles/**
- services/mission-status-api/src/test/resources/conformance/legacy-lanes-json/**
- services/mission-status-api/src/test/resources/conformance/tasks-md/**
- services/mission-status-api/src/test/resources/conformance/worktree-states/**
- services/mission-status-api/src/test/resources/conformance/artifacts-populated/**
- services/mission-status-api/src/test/resources/conformance/artifacts-sort/**
- services/mission-status-api/src/test/resources/conformance/artifacts-refusals/**
- services/mission-status-api/src/test/resources/conformance/artifacts-links/**
- services/mission-status-api/src/test/resources/conformance/artifacts-redaction/**
- services/mission-status-api/src/test/resources/conformance/lookup-faults/**
- services/mission-status-api/src/test/resources/conformance/projection-nulls/**
- services/mission-status-api/src/test/resources/conformance/projection-refusals/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/ConformanceTree.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/GoldenSuiteTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/DetailManifestCensusTest.java
- .github/workflows/ci-router.yml
- tests/ci/test_contracts_workflows.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP07 – [PR A] P4 Oracle extension, goldens and the paired Java census (FR-014 Python half, D-109)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: PR A (draft, stacked on the branch that carries #5529's last slice). **Phase tag**: P4 (plan section 11). WP07 runs beside WP06 (P2) and WP09 (P5) after WP05; WP08 (P4b) and WP10 (P7) depend on it.
- **Work package dependencies**: WP05 (P3: the resolved-state reduction exists, so the unit tests and the goldens of later WPs have a consumer) and WP04 (P3a: `M/data-model.md` exists and this WP appends to it).
- **Precondition (lane lineage, TASKS-FRESH-005).** `M/data-model.md` is committed by WP04, a `planning_artifact` WP that runs in the planning lane on the target branch, not in a code lane; a code lane is cut from the tips of its code dependencies and receives only the recorded finalize-tasks planning commit, which predates WP04's commit. So before the first edit run `test -f kitty-specs/mission-status-read-api-mission-detail-01M4S6D5/data-model.md` in the lane workspace. If it is absent, STOP and report: the orchestrator must merge the target branch (carrying WP04's committed `data-model.md`) into this lane before work resumes (OO-5). Never create the file here: this WP appends a section to WP04's file, and creating a second copy would give an add/add conflict when the lanes merge.
- **External dependency (not a `dependencies` entry)**: the orchestrator-merged #5529 re-cut tip must be in the branch before WP01 started; the P0 baseline record (`M/traces/baseline-red.yaml`, and the `test_baseline_record_*` tests appended to `tests/contract/test_mission_status_conformance.py` before any WP was claimed) is committed. #957 cannot merge before #5529 (C-005). No agent pushes, opens or retargets a PR.
- **Named edits (out-of-map; not in `owned_files`)**. Rule for each: rebase first, state the edit in the commit message, touch nothing else of the file.
  1. `M/data-model.md`: **append** this phase's section (the manifest classes, the golden file names, `PROVISION_PLAN`, the `knownDivergence` entry format). WP04 owns the file (T050).
  2. `M/traces/approach.md` and `M/traces/design-decisions.md`: append-only tracer entries (never in `owned_files`).
- **Conditionally written owned files (not named edits)**: `.github/workflows/ci-router.yml` and `tests/ci/test_contracts_workflows.py` are in `owned_files` here and are written **only if AC-14.6 demands** (one line each); otherwise untouched. A later WP that needs a `ci-router.yml` change (WP17, plan: one line, only if required) makes it as a named edit of this WP's file.
- **Write scope**: `owned_files` only. `tests/contract/test_mission_status_conformance.py` is owned here **after** P0 appended the baseline-record tests; those tests stay green and **unchanged** (FR-021, T049). `R/conformance/resolved-state/**` is WP08's (a glob cannot exclude it, so the class directories above are enumerated).
- **Aliases used below**: `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `C` = `R/conformance`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`. Every path in this prompt exists at the checkout today (the conformance tree, the generator, `ConformanceTree`, `GoldenSuiteTest`), except the new class directories and `DetailManifestCensusTest`.

## Objective

Extend the existing conformance generator, its test, the committed fixture classes and the manifest with the detail and artifact classes of FR-014 (everything except `resolved-state`), and, in the **same phase**, extend the Java census that enumerates the manifest, so that no tip between this WP and the route phases is red.

## Context

- **Why**: FR-014 / SC-001. The golden conformance of #5529 is **extended, not duplicated**: the generator `tests/contract/_mission_status_conformance.py` composes the detail and artifact oracles (`_mission_status_payloads.build_detail`, `build_work_package`, `read_authored_files`; `_mission_status_detail.index_work_packages`, `build_work_package_detail`, `open_mission`, `HostCapability`; `_mission_status_artifacts.list_artifacts`, `read_content`, `ReaderContext`) and re-implements none of them. Goldens live beside the existing ones under `C` (already inside the router's `contract_tools` path glob; `.gitattributes` has `services/mission-status-api/src/test/resources/conformance/** -text`, so no `.gitattributes` edit is planned).
- **Index-fed oracle (spec FR-014)**: `build_detail` and `build_work_package` are fed from `index_work_packages`: the winning file of each id is re-read with `read_authored_wp_frontmatter` (`src/specify_cli/status/wp_metadata.py`) and passed as `files=` (a list of `AuthoredWorkPackage(path, metadata, body)`), so the malformed, duplicate and two-selector classes have a true oracle golden of the shared index rule (FR-006) and are not self-fulfilling. The oracle's own default path, `read_authored_files` (it lists every `WP*.md` that `is_file` follows and has no handling for a malformed one), is then the **divergence** (V3, V4), not the golden.
- **Green at every tip (D-109, D-111)**: this WP adds manifest classes **and** everything that enumerates the manifest in the same phase. `ConformanceTree.classes()` and `fixtures()` keep returning the **overview surface only**, so every existing consumer (`GoldenSuiteTest`, `ResponseContractValidationTest`, `JacksonContractTest`, `GoldenRoutesTest`, `ProjectAndPagingTest`, `RefusalRowsTest`, `ContractValidatorTest`, `FilesystemFixtureFactoryTest`, `ComparatorCompletenessTest`, `ManifestCouplingTest`) sees what it saw before; `allClasses()`, `detailClasses()` and `detailFixtures()` are added. No Java test compares a detail golden against a route here (no route exists; WP10's `ServedRoutes` registry compares only the fixtures a route provider serves).
- **Red-first form**: the golden and census tests are red on a copy with one golden byte, one fixture, one class or one manifest entry removed (the controls of T047 and T048); the branch is not red between this WP and the route phases because of the surface partition.
- **Spec amendments in force** (plan section 14): S-3 (classes `projection-nulls` 6 and `projection-refusals` 4, V18, V19), S-6 (`worktree-states` Count 7), S-15 (`detail-populated` Count 8, fixture `unicode-subtask-ids`), S-19 (`wp-malformed-frontmatter` Count 28, `wpm-28`, V20 where D-97 needs it), S-20 (`phases-matrix` Count 19, fixture `marker-row-without-event-id`). The spec table (7, 18, 27, 6) is superseded by these numbers.

### Subtask T044: Generator - compose the detail and artifact oracles

**Purpose**: One generator, new documents per fixture, no second oracle.

**Steps**:
1. **C-005 pre-flight, first step of the phase (D-107)**, from the repository root:
   ```bash
   export LC_ALL=C.UTF-8
   .venv/bin/python contracts/tools/bundle.py --root contracts --out "<scratch>/bundle-out" --module mission-status --bundle-only
   export CONTRACT_BUNDLE="<scratch>/bundle-out/bundle/mission-status/openapi.yaml"
   export CONTRACT_BUNDLE_SHA256="$(sha256sum "$CONTRACT_BUNDLE" | cut -d' ' -f1)"
   cd services/mission-status-api && ./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'
   cd ../.. && git log -1 --format=%H refs/remotes/m5529/lane-b      # the ref that carries #5529; record the sha in the first commit message
   grep -rnE '"org\.speckitty\.missionstatus\.(application|domain)' services/mission-status-api/src/test services/mission-status-api/build.gradle.kts
   grep -rnE 'application/port|domain/(overview|reducer|projection|paging|cursor)' tests scripts .github
   ```
   (`<scratch>` is outside the repository.) Read `tests/contract/test_mission_status_conformance.py` first: the `test_baseline_record_*` functions that P0 appended must not move.
2. In `tests/contract/_mission_status_conformance.py` (781 lines, cohesive; plan section 9 says add data rows and per-class helpers, not control flow; SonarCloud reports 0 open issues for it) add helpers that, per fixture class, build the new golden documents next to the existing `missions_document`/`project_document`: a Mission detail document per Mission (`payloads.build_detail(source, projector, files=<index-fed files>)`), a Work Package document per Work Package (`payloads.build_work_package(..., include_prompt=False/True)`), a Work Package detail document (`detail.build_work_package_detail(ctx, mission_id, wp_id, host)` with `HostCapability(git=False, worktrees=True)` for the `worktree-states` class and `NO_WORKTREES` (`HostCapability(git=False, worktrees=False)`) for every other class), an artifact listing (`art.list_artifacts(ctx, mission_id)`) and artifact contents (`art.read_content(ctx, mission_id, [segments])`) for the files of the listing. Wrap each in `_guarded` so an oracle exception becomes a recorded `refusal_of(...)` document, exactly as the existing documents do; an `Outcome(status, body)` is recorded as `{"status": n, "body": {...}}`.
3. **Index-fed files**: add `index_fed_files(ctx, mission_dir)`: call `detail.index_work_packages(ctx, mission_dir)` (first valid file wins, in UTF-8 byte order of the name; skips symlinks, directories, ineligible paths and files whose frontmatter raises `FrontmatterError`, `ValidationError` or `UnicodeDecodeError`), then for each winning name re-read the file with `read_authored_wp_frontmatter` and build `AuthoredWorkPackage(path, metadata, body)`. Pass that list as `files=` to `build_detail`. A file that cannot be read at all raises `SourceUnreadableError` (recorded as a refusal).
4. **`PROVISION_PLAN`** (placed at the fixture top level, never inside a Mission directory: ruling OO-4 under "Plan defects found") generalises `SYMLINK_PLAN` (D-42). Keep reading `SYMLINK_PLAN` exactly as today (the existing `symlink` class fixtures hold it and are not owned here; `NOT_COPIED` keeps it) and add `PROVISION_PLAN` (also in `NOT_COPIED`) with tab-separated, verb-first lines: `link<TAB>path<TAB>target` (same `@outside/` convention as today), `gitentry<TAB>path` (a plain file named `.git`; its content is irrelevant to a stat), `mtime<TAB>path<TAB>epochSeconds`, and `dir<TAB>path` (the lane-worktree directories of `worktree-states`). The generator applies the plan to the temporary copy **before** the oracle runs; the Java harness (WP10 `ProvisionPlan`) applies the same file to its temporary copy. A leg that cannot create a link reports `not run: link unsupported`, never a pass. Document the grammar in `PROVISIONING_NOTES` (it is copied into the manifest's `provisioning` object) and in T050.
5. `GOLDEN_FILES` becomes a **per-class mapping** (`GOLDEN_FILES_OF: Mapping[str, tuple[str, ...]]`) for the new classes while `GOLDEN_FILES` (the tuple) stays for the 14 existing ones; the allowed-set assertion of the test is widened in the same change (T048). **Golden file names**: the spec calls them provisional and the plan does not fix them (see "Plan defects found" item 1). Fix them here, one file per route, named after the operation, holding a canonical-JSON object keyed by the request key (`"-"` for a Mission-level route, the Work Package id, or the artifact path): `get-mission.json`, `get-work-package.json`, `get-work-package-prompt.json`, `get-work-package-detail.json`, `list-artifacts.json`, `get-artifact-content.json`. Names contain none of `: " ? * | { } $` (NFR-007). Record them in T050 so WP10 and the route WPs read them from `M/data-model.md`.
6. Determinism: the same state yields the same bytes across runs, temp roots and git dates (the existing `test_provisioning_is_deterministic...` pattern); `canonical_bytes` is the only writer; no golden holds a temp path, a commit id or a git date (`test_no_golden_holds_a_temp_path_a_commit_id_or_a_git_date`).
7. Imports: only `src` modules that the router's `contract_tools` filter group already names (AC-14.6 derives this by a test; T048).

**Files**: `tests/contract/_mission_status_conformance.py` (edit, about +350 lines in helpers and data rows).

**Validation**: `.venv/bin/python -m tests.contract._mission_status_conformance --check` passes on the unchanged 14 classes before any new fixture exists; ruff check and format clean (`make format-check-files FILES="tests/contract/_mission_status_conformance.py"`).

### Subtask T045: Fixture classes of FR-014 as amended (except resolved-state)

**Purpose**: Commit the trees the oracle and, later, Java run over. Every committed name avoids `: " ? * | { } $` and every committed value is synthetic (NFR-006, NFR-007, C-006): synthetic ULIDs, no host path, no user name, no real address; credential-shaped values are **assembled at test time from fragments** (D-48), never committed whole; a fixture whose name the Windows-filename gate rejects is generated at test time.

**Steps** (the Count column is a floor: `CLASS_FLOORS` pins at least this number, equal to the class's fixture count at the commit that adds it, never lowered):

| Class | Count | Fixtures | Notes |
|---|---|---|---|
| `detail-populated` | 8 | `populated`, `null-workspace`, `planning-lane`, `unknown-change-state`, `dependency-unknown`, `bad-sibling-before`, `bad-sibling-after`, `unicode-subtask-ids` | `unicode-subtask-ids` has subtask ids `U+FF5E...` and `U+1F600...` (S-15): its golden holds the `subtasks` keys in code point order |
| `detail-early` | 1 | `early` | no ledger, no Work Package |
| `detail-planning-only` | 1 | `planning-only` | Work Package files, no events |
| `phases-matrix` | 19 | `ps-file`, `ps-completed`, `ps-started`, `ps-neither`, `ps-file-completed`, `ps-completed-started`, `ps-link-file`, `ps-link-completed`, `ps-link-started`, `ps-link-neither`, `ps-rotated`, `lc-empty`, `lc-planned`, `lc-mix`, `lc-for-review`, `lc-done`, `lc-canceled`, `lc-blocked`, `marker-row-without-event-id` | `ps-link-*` are provisioned symlinks (V1); the last is the D-98 marker row (a string `event_type` and no string `event_id` or `timestamp`) |
| `wp-malformed-frontmatter` | 28 | `wpm-01` .. `wpm-28` | the 28 cases of AC-6.1 in its order; `wpm-28` is `subtasks` written as mappings (SK-353, D-97); a symlinked file case is provisioned (V4) |
| `wp-duplicate-id` | 3 | `duplicate-wp-id`, `duplicate-mission-id`, `duplicate-then-broken` | |
| `wp-two-selectors` | 1 | `two-selectors` | AC-6.3 |
| `wp-prompt-bytes` | 13 | one per body of AC-9.1 | host path, e-mail, near-miss token, CRLF, lone CR, trailing newline, no trailing newline, U+2028, U+0085, supplementary character, quote and backslash, 0 bytes, 200000 bytes |
| `cycles` | 4 | `no-cycles`, `cycle-without-path`, `unparseable-cycle`, `numeric-order` | numeric order 1, 2, 9, 10 |
| `legacy-lanes-json` | 1 | `legacy-lanes-json` | `feature_slug`, no `mission_slug`; the only place the legacy word appears, **marked legacy** (NFR-006) |
| `tasks-md` | 12 | `tasks-md-table-and-checkbox` and the committed cases of AC-3.4 | the two size cases are generated at test time, not committed |
| `worktree-states` | 7 | `dir-and-git-present`, `dir-without-git`, `dir-absent`, `directory-symlink`, `git-entry-symlink`, `planning-lane`, `no-lane` | symlinks, `.git` entries and directories come from `PROVISION_PLAN`, never committed (S-6, FRESH3-006) |
| `artifacts-populated` | 1 | `artifacts-populated` | `mtime` lines for `modifiedAt` |
| `artifacts-sort` | 1 | `artifacts-sort` | non-ASCII names need a UTF-8 file-name locale (Gate G precondition) |
| `artifacts-refusals` | 1 | one fixture, one file per status of AC-5.1 | |
| `artifacts-links` | 3 | symlinked file, symlinked directory, junction | Java-only; links created at test time |
| `artifacts-redaction` | 1 | the corpus of AC-5.7 | credential shapes from fragments |
| `lookup-faults` | 3 | `bad-sibling-unknown-meta`, `bad-sibling-unknown-link`, `bad-sibling-unknown-two-faults` | Java-only (the oracle skips the faulted sibling: V9); the link one is provisioned |
| `projection-nulls` | 6 | `head-dates-nulled`, `merge-target-branch-path`, `planning-branch-too-long`, `override-partial-junk-at`, `lane-id-fails-pattern`, `reviewed-at-junk` | S-3; `head-dates-nulled` is a `knownDivergence` fixture (V19) |
| `projection-refusals` | 4 | `history-at-not-instant`, `history-event-id-leak`, `owned-file-pattern-leak`, `dependency-id-leak` | S-3; Java-only, no golden (V18) |

Permission-denied rows stay **Java-only** (like `projection-refusals`): the generator never provisions an unreadable file with `chmod`, because running it as root would change a golden (D-101).

For every fixture: write the smallest tree that shows the property (a `kitty-specs/<mission-dir>/` with `meta.json` carrying a synthetic ULID, `status.events.jsonl` where the property needs a ledger, `tasks/WPnn-*.md`, `plan.md`/`spec.md`/`tasks.md` where phases need them). Reuse the helpers and shapes of the existing fixtures (`two-missions`, `seven-lifecycle-types`) for ledger rows. Generate the golden with `--write` only after the fixture is final.

**Files**: about 120 fixture trees under `C/<class>/<fixture>/` plus their `golden/*.json` (generated, reviewed by regeneration command, not by line).

**Validation**: each class directory exists, holds at least its Count, and contains no forbidden file-name character; `git ls-files` shows no `.git` entry and no symlink inside `C`.

### Subtask T046: knownDivergence entries V1 to V19 (V20 where D-97 needs it), manifest surface

**Purpose**: Make every place where Java will differ from the oracle a listed, pinned manifest entry (AC-14.4).

**Steps**:
1. Add the divergence entries to the manifest document produced by `manifest_document(...)`: one entry per row V1 to V19 of the spec table as amended (S-3: V18 and V19 as worded in plan section 8 FRESH3-003; S-6: V7 covers the directory and its `.git` entry), plus V20 if `wpm-28` shows the oracle serving a stringified mapping (S-19, D-97). Each entry carries: `id`, `cause`, `fixture` (class/name, or `injected` / `generated at test time` for the Java-only and generated rows V2, V5, V10 to V18), `oracleOutcome`, `javaAssertion`. Today the manifest has only the per-fixture `knownDivergence` tag (`torn-final-line/valid-json-final-line`); keep that mechanism and add a top-level list for the V entries (the key name is this WP's decision; record it in T050 and mirror it in `ConformanceTree`).
2. **V3 and V4** also store the outcome of the oracle's default `read_authored_files` path, which the generator runs on the **same provisioned fixture** (a duplicate id is listed twice; a malformed file raises; a symlinked file is followed). The Python test fails when the live default path does not reproduce the stored outcome.
3. Every entry has two **different** outcomes (a stale entry whose two outcomes are equal is a test failure; T048).
4. **Manifest `surface`**: every new class carries `"surface": "detail"` in its `classes[]` entry. The 14 existing classes carry **no** `surface` key (absent means `overview`), so their manifest entries stay byte-identical. `ClassSpec` gains a `surface` field with default `"overview"`; `manifest_document` writes the key only for `detail`.
5. Row-to-entry map for the Python test (AC-14.4): C3 to C5 to V9, M4a over 1 MiB to V5, M7 to V18, M8 to V2, M9 to V16, M10 to V14, M14 to V19, W2 to V12, W3 over 1 MiB and M11 to V17, A1 walk bound to V10, A5 to V13, A8 and M13 to V15. The test fails when such a row has no entry, when a fixture's Java outcome differs from its oracle outcome with no entry, and when an entry's two outcomes are equal. The fixtures V5, V10, V11, V14 and V17 are generated at test time, so the check also runs over the generated set (the Java side of that is WP10 and PR B; the Python side asserts the entries and their distinct outcomes).

**Files**: `_mission_status_conformance.py` (data rows), `test_mission_status_conformance.py` (tests), `C/manifest.json` (generated).

**Validation**: `--check` green; deleting one entry in a scratch copy turns the divergence test red; making an entry's two outcomes equal turns it red.

### Subtask T047: The paired Java census (D-109)

**Purpose**: The manifest, the Python floors, the Java floors and the fixture trees change in this one phase.

**Steps**:
1. `T/testsupport/ConformanceTree.java` (owned): parse `surface` from each `classes[]` entry (default `overview`). `classes()` and `fixtures()` (and `fixturesOf(tag)`, which derives from them) return **only** `overview` classes. Add `allClasses()` (every class), `detailClasses()` and `detailFixtures()`. `ClassEntry` gains a `surface` component; keep a four-argument constructor or adapt the one call inside `ConformanceTree` (the only `new ClassEntry` in the module). Add the reader of the V entries (`knownDivergences()`), which WP10 and the route WPs use.
2. `T/conformance/golden/GoldenSuiteTest.java` (owned): exactly **one** assertion changes: `everyFixtureTreeOnDiskIsInTheManifestAndEveryGoldenFixtureHasBothGoldens` compares the directories found on disk (it lists `ConformanceTree.root()` children) with `allClasses()` instead of `classes()`, and its "both goldens" check applies to overview fixtures only (a detail fixture's goldens are the per-class files of T044). Its `CLASS_FLOORS` map keeps the 14 overview classes.
3. `T/conformance/golden/DetailManifestCensusTest.java` (new): holds `DETAIL_CLASS_FLOORS` in the same `Map.entry("tag", n)` form as `GoldenSuiteTest.CLASS_FLOORS`, with the Count column above; asserts the detail tags of the manifest equal its keys, every class meets its floor, and every detail fixture has the goldens its parity demands (a `python-golden` fixture holds the per-class files of the golden mapping; a `java-only` fixture holds none). `resolved-state` is **not** in the map yet (WP08 adds its line as a named edit).
4. Python: add `test_the_java_class_floors_mirror_the_python_ones` to `test_mission_status_conformance.py`: parse both Java maps by regular expression (`Map.entry("tag", n)`), assert their union equals `CLASS_FLOORS` (extended with the new classes), and that a named floor makes an empty parse fail (an empty parse is a failure, not a pass). Extend `CLASS_FLOORS` with the Count column.
5. **Repeat the consumer grep and put the result in the commit message**:
   ```bash
   grep -rnE 'ConformanceTree\.(fixtures|classes)\(\)' services/mission-status-api/src
   grep -rnE 'ConformanceTree\.root\(\)' services/mission-status-api/src
   ```
   Every hit must still see the overview surface (the first grep lists the consumers named in the plan; the second lists the code that walks the directories on disk and must be checked individually).

**Files**: `ConformanceTree.java` (about +50 lines), `GoldenSuiteTest.java` (one assertion), `DetailManifestCensusTest.java` (new, about 90 lines), the Python test.

**Validation**: Gate G green with `GoldenSuiteTest`, `DetailManifestCensusTest`, `ManifestCouplingTest`, `ComparatorCompletenessTest` and every consumer above unchanged in behaviour.

### Subtask T048: Determinism, --check, golden honesty, router

**Purpose**: Prove the generator is stable and the gates see the new classes.

**Steps**:
1. Generator determinism: run `--write` twice into **differently named roots** and assert byte equality (add a test in the style of `test_provisioning_is_deterministic_across_temp_roots_and_git_dates`).
2. `--check` fails on a stale golden and `--write` rewrites it; the existing honesty tests (`test_every_generated_file_equals_the_committed_file_byte_for_byte`, `test_editing_one_golden_value_in_a_temp_copy_turns_the_comparison_red`) are extended to a detail golden, a listing golden and a `get-work-package-prompt.json` golden in turn (AC-14.1 control: all three suites go red on a perturbed byte).
3. Widen `test_every_non_java_only_fixture_has_exactly_its_goldens` to the per-class mapping (`GOLDEN_FILES_OF`); widen `test_the_file_set_of_the_conformance_tree_is_exactly_the_classes_and_two_data_files` to `CLASS_TAGS` including the new tags; widen the manifest-listing test (`[entry["tag"] for entry in manifest["classes"]] == list(gen.CLASS_TAGS)`).
4. AC-14.6: a test derives the `src` files the extended generator imports and compares them with the router's `contract_tools` filter group; run `tests/ci/test_contracts_routing.py`, `tests/ci/test_contracts_workflows.py`, `tests/ci/test_mission_status_routing.py` and `tests/architectural/test_ci_corpus_trigger_completeness.py`. Edit `.github/workflows/ci-router.yml` and `tests/ci/test_contracts_workflows.py` **only if** the derived-imports test is red (add the missing `src` file to the group, one line each); otherwise leave both files untouched.
5. **Property checks for the new classes.** The existing test scaffold requires one distinguishing-property check per class: `PROPERTY_CHECKS` (a `Mapping[str, PropertyCheck]`), `test_every_class_has_a_property_check` (`set(PROPERTY_CHECKS) == set(gen.CLASS_TAGS)`), `test_each_class_shows_its_distinguishing_property_in_its_golden_content` and `test_a_trivial_golden_carrying_the_right_tag_fails_its_class` (which plants overview-shaped trivial goldens under the `MISSIONS` and `PROJECT` names). Add a `*_problems` function and a `PROPERTY_CHECKS` entry for every new class (each reads its own golden file names through `goldens_in`, widened to the per-class mapping), give each `ClassSpec` a `property` text, and widen the trivial-golden control to plant a per-class trivial document under that class's golden names so it is red for every `python-golden` detail class. A Java-only class (`artifacts-links`, `lookup-faults`, `projection-refusals`) gets the `java_only_problems` treatment (no golden; the plan file is present for the classes that need one).
6. AC-14.2 perturbation controls that need a Java change are the route WPs'; here the Python side asserts the order of the `phases` array in the `get-mission.json` goldens is the contract order and that the `phases-matrix` classes cover the full cross product (19 fixtures, AC-1.3).

**Files**: `test_mission_status_conformance.py` (edit, about +250 lines).

**Validation**: `PWHEADLESS=1 .venv/bin/python -m pytest tests/contract/test_mission_status_conformance.py -m "corpus and not windows_ci" -q` green; the targeted CI pins green.

### Subtask T049: The baseline-record tests stay green and unchanged (FR-021)

**Purpose**: P0 appended `test_baseline_record_*` to this file; this WP owns the file afterwards and must not disturb them.

**Steps**: do not edit, reorder or rename any `test_baseline_record_*` function or the helpers they use; after the edits above run `PWHEADLESS=1 .venv/bin/python -m pytest tests/contract/test_mission_status_conformance.py -k baseline_record -m "corpus and not windows_ci" -q` and `.venv/bin/python -m pytest tests/architectural/test_ci_corpus_trigger_completeness.py -q`. `git diff` of the file shows no changed line inside those functions. If P0's tests are not present in the checkout you are on, stop and report (the P0 precondition did not hold).

**Validation**: both commands green; the diff check above.

### Subtask T050: Append the manifest-classes and PROVISION_PLAN sections to M/data-model.md (named edit)

**Purpose**: The documented home of the new committed data formats (plan section 3, last row).

**Steps**: append (do not rewrite WP04's text) a section with: the class table and the `surface` rule; the golden file names and the key convention of T044; the `PROVISION_PLAN` grammar and its relation to `SYMLINK_PLAN`; the `knownDivergence` entry format and the V1 to V20 list with the V3/V4 stored default-path outcome; how `CLASS_FLOORS` and `DETAIL_CLASS_FLOORS` relate. Public-hygiene rule: no home path, user name or token. Add a one-line entry to `M/traces/approach.md` and a decision entry to `M/traces/design-decisions.md` for the golden names and the V-entry key.

**Files**: `M/data-model.md` (append, about 80 lines).

**Validation**: the file is add-only relative to WP04's commit (`git diff` shows only appended lines).

### Subtask T051: Gate

**Purpose**: Exit the phase on the plan's P4 gate.

**Steps** (UTF-8 locale, bundle variables exported, new files staged first because the Windows-filename guard reads `git ls-files`):
1. C-005 pre-flight again (T044 step 1) on the final tree.
2. ```bash
   .venv/bin/python -m tests.contract._mission_status_conformance --check
   PWHEADLESS=1 .venv/bin/python -m pytest tests/contract/test_mission_status_conformance.py -m "corpus and not windows_ci" -q
   .venv/bin/python -m pytest tests/ci/test_contracts_workflows.py tests/architectural/test_ci_corpus_trigger_completeness.py -q
   .venv/bin/ruff check . && .venv/bin/ruff format --check .
   make format-check-files FILES="tests/contract/_mission_status_conformance.py tests/contract/test_mission_status_conformance.py"
   .venv/bin/ruff check --select TID251 .
   .venv/bin/python -m pytest tests/architectural/test_no_invalid_windows_filenames.py -q
   .venv/bin/python contracts/tools/layout_check.py && .venv/bin/python contracts/tools/leak_scan.py && .venv/bin/python contracts/tools/structure_check.py
   ```
3. **Gate G**: `cd services/mission-status-api && ./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck` (`GoldenSuiteTest`, `DetailManifestCensusTest`, `ManifestCouplingTest` and every `ConformanceTree` consumer green at this tip).
4. **Gate P**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` (WP07 adds tracked paths under `S/`, so the tracked-path scan and the fixture-name checks run).
5. Generator determinism (T048) and the red-on-a-copy-with-one-golden-byte-removed check, run once in a scratch copy of the tree (never by editing the working tree under review).
6. `.venv/bin/spec-kitty regen --check` and `.venv/bin/python scripts/generate_contextive_glossaries.py check` stay clean (no input changed); run the terminology guard `tests/architectural/test_no_legacy_terminology.py`.

**Validation**: all green; record exact commands and counts.

## Self-contained green

- **Fixtures live with their tests**: every fixture class and its goldens are in this WP; the only Java reader added (`DetailManifestCensusTest`) checks presence, floors and parity, not route output. `resolved-state` is absent here and arrives with its floor in WP08.
- **Floors and counts satisfiable here**: `CLASS_FLOORS` (Python) = the 14 overview floors plus the Count column; `DETAIL_CLASS_FLOORS` (Java) = the Count column; their union equals `CLASS_FLOORS` (checked by `test_the_java_class_floors_mirror_the_python_ones`). Each count is the fixture count at the commit that adds the class. No JaCoCo count changes (test-only Java, no `domain`/`application` class). Native floors (`--floor 3`, `--request-floor 49`) and `requests.json` are untouched.
- **No forward reference**: nothing here names a type of a later WP. In particular `ServedRoute`, `ServedRoutes`, `DetailGoldenSuiteTest`, `DetailFixture`, `ProvisionPlan` and `Utf8Host` are WP10's; this WP's Java is `ConformanceTree`, `GoldenSuiteTest` and `DetailManifestCensusTest` only. No Java test compares a detail golden against a route (the surface partition keeps `classes()`/`fixtures()` on the overview).
- **Pin clauses kept green**: `tests/ci/test_mission_status_api_build.py` tracked-path scan (stage first; fixture names carry no Windows-illegal or shell-expansion character; the 300-path floor rises, never falls); the rest of the file is not touched.
- **Router and registry**: AC-14.6 by the derived-imports test and `tests/ci/test_contracts_workflows.py` and `test_ci_corpus_trigger_completeness.py` green; the conformance module keeps its existing `_CORPUS_MARKED_MODULES` entry and Packs `--deselect` (no `packs.yml` edit, E-2).
- **Mission record**: `M/data-model.md` is append-only; tracer entries are append-only; `M/meta.json` untouched; `M/status.json` stays the materialisation of the committed `status.events.jsonl` (`spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5`), never hand-edited, no untracked CLI state committed blind (compare with the coordination copy first). That keeps `cutover-guard`, `mission-state audit` (`.venv/bin/spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json`, run before a push of an `M/**` change) and `corpus-blocking` green; `M/**` is not on `main` while PR A is open, so archive-freeze is not triggered (plan section 11).

## Baseline precondition check (AC-21.1 to AC-21.3)

Before claiming: `traces/baseline-red.yaml` is present and the `test_baseline_record_*` tests of `tests/contract/test_mission_status_conformance.py` are green on the tip you start from; the first commit of this work package is a descendant of the commit that added the record (`git merge-base --is-ancestor`). If either fails, stop and report.

## Plan defects found

1. **Golden file names are fixed by nobody.** Spec FR-014 says "Golden file names below are provisional (the plan fixes them)"; the plan does not. WP07 fixes them (T044 step 5, one file per route keyed by request key) and records them in `M/data-model.md`; WP10 (`ServedRoute` providers) and WP13 to WP16 read them there. If the orchestrator wants other names, change T044 step 5 before this WP is claimed.
2. **AC-20.1 as folded (S-29).** The new `resolved-state` class (WP08) carries the oracle-generated resolved members, checked by `ResolvedStateGoldenTest` (WP10); the existing ledger classes (`interleaved`, `lifecycle-only`, `crlf-and-listing`, ...) stay byte-identical (AC-20.2), because the Python test forbids extra golden files in them. No owner is needed for the existing classes; the reviewer does not look for it here.
- **RULED: OO-4 (orchestrator ruling 2026-10-13, binding; formerly TASKS-COVER-009 item 4): where `PROVISION_PLAN` sits.** `ProjectHeaderMaterialisation.NOT_COPIED` (a #5529 test-support file no WP of this mission owns) names `SYMLINK_PLAN`, not `PROVISION_PLAN`, so a `PROVISION_PLAN` inside a Mission directory would be copied into the scratch tree and leak into artifact listings and goldens. **Chosen placement: the `PROVISION_PLAN` file sits at the fixture top level (outside any Mission directory); WP10's `ProvisionPlan` reads it from the source fixture directory and removes any stray copy at the scratch root.** No named edit of `NOT_COPIED`. T044 step 4 places the file there and T050 records that this placement is chosen.
3. **`SYMLINK_PLAN` and `PROVISION_PLAN` coexist.** "Generalising" would rename a file inside the existing `symlink` class, which this WP does not own; the generator reads both grammars (T044 step 4).
4. **The property-check scaffold is implied but unstated.** The plan names the generator, `CLASS_FLOORS` and `GOLDEN_FILES` as the extension points but not `PROPERTY_CHECKS`, `goldens_in` or the trivial-golden control, all of which assume the two overview golden names; widening them is part of T048 step 5 and is not optional (`test_every_class_has_a_property_check` is red otherwise).
5. Spec table counts (7, 18, 27, 6) are superseded by plan section 14 (8, 19, 28, 7); the prompt uses the amended numbers.

## Definition of Done

- The generator composes the detail and artifact oracles, index-fed, with `PROVISION_PLAN` and per-class golden files; `--check` is green and deterministic across differently named roots (T044, T048).
- Every class of the table exists with at least its Count; the V entries V1 to V19 (V20 if needed) are in the manifest with distinct oracle and Java outcomes; V3 and V4 store the default-path outcome; every new class carries `surface: detail` and the 14 existing entries are byte-identical (T045, T046).
- `ConformanceTree` partitions by surface; `GoldenSuiteTest` has its one changed assertion; `DetailManifestCensusTest` exists; `test_the_java_class_floors_mirror_the_python_ones` is green; the consumer grep result is in the commit message (T047).
- A property check exists for every new class and the trivial-golden control is red for each `python-golden` detail class (T048 step 5).
- The baseline-record tests are unchanged and green (T049); `M/data-model.md` has the appended section (T050).
- Gate G, Gate P, the Python hygiene set, the contracts smoke scripts and the CI-pin tests are green and recorded (T051). Evidence of subtask completion is `.venv/bin/spec-kitty agent tasks mark-status <Txxx> --status done --mission mission-status-read-api-mission-detail-01M4S6D5` per subtask, not a ticked checkbox.

## Risks

- **Oracle is not total (R-7)**: `build_detail`/`build_work_package` have no malformed-file handling and `workspace_of` calls `resolve_workspace_for_wp`. Mitigation: the index-fed `files=` and `_guarded` refusal documents; the default path is recorded as the divergence.
- **Open PRs change the oracle's Python (R-16)**: #6122 (`frontmatter.py`), #6127 (`ownership/validation.py`, `lanes/compute.py`), #5953 (`status/models.py`, `store.py`). A merge can change a golden. Mitigation: regenerate on the merged tree and review the diff by command.
- **Corpus shapes (R-10)**: SK-351 and SK-353 make part of the archived corpus unreadable; `wpm-28` stores the oracle's outcome, and V20 records any divergence.
- **Public repository**: fixtures must be synthetic and contain no home path, user name or whole credential token; assemble credential shapes from fragments at test time.
- **Windows-filename guard**: passes vacuously before staging; stage first, run after.
- **Size**: about 120 fixture trees; the generator stays under the complexity ceiling (15) per function; split helpers rather than growing one.

## Reviewer Guidance

- Verify the red-first form of this phase: a copy with one golden byte, one fixture, one class or one manifest entry removed turns the Python honesty test or `DetailManifestCensusTest` red.
- The 14 existing manifest entries and goldens are byte-identical (`git diff` shows additions only under `C/` for new classes plus the manifest's new entries); `GoldenSuiteTest` changed by one assertion.
- `ConformanceTree.classes()`/`fixtures()` still return the overview surface; the consumer grep result is in the commit message.
- Counts: each class meets the amended Count (8, 19, 28, 7, 6, 4 where amended); the Java and Python floor maps agree.
- Divergences: every V entry has two different outcomes; V3 and V4 store the default-path outcome; V19 is `head-dates-nulled`.
- No fixture name contains `: " ? * | { } $`; no tracked symlink or `.git` entry; no real address, host path or whole credential token.
- `M/data-model.md` is append-only; `.github/workflows/ci-router.yml` and `tests/ci/test_contracts_workflows.py` are untouched unless the derived-imports test demanded one line each.
- Run the implied gates by name (`GoldenSuiteTest`, `DetailManifestCensusTest`, `ManifestCouplingTest`, the CI pins), not a bare directory.

## Implementation command

```bash
.venv/bin/spec-kitty agent action implement WP07 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
