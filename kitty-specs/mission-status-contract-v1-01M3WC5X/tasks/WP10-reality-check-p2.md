---
work_package_id: WP10
title: Reality check, payload helper, pinned fixture and preview point p2 (IC-09)
dependencies:
- WP06
- WP09
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-009
- FR-012
- FR-019
- FR-020
- NFR-001
- NFR-004
- NFR-007
- C-002
- C-004
- SC-002
- SC-005
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T062
- T063
- T064
- T065
- T066
- T067
- T068
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- tests/contract/_mission_status_payloads.py
- tests/contract/test_mission_status_payloads.py
- tests/contract/test_mission_status_reality.py
- tests/contract/fixtures/mission_status_expected.json
execution_mode: code_change
model: sonnet
owned_files:
- tests/contract/_mission_status_payloads.py
- tests/contract/test_mission_status_payloads.py
- tests/contract/test_mission_status_reality.py
- tests/contract/fixtures/mission_status_expected.json
- contracts/mission-status/**
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# WP10 - Reality check, payload helper, pinned fixture and preview point p2 (IC-09)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Prove the contract against this repository's own Missions: a read-only test-side helper that builds the overview, detail and work package payloads with today's public status readers, a per-Mission parametrised reality check with floors, controls, snapshot equality and a read-only hash proof, and a pinned expected-output fixture. Fix, in the contract, whatever it proves wrong.

## Context

- Plan concern **IC-09**, the **runtime-state contract** WP: it reads status snapshots **only through public readers** and must never call a writer. **Hard rule from the spec-phase incident (tracer F-1): never call `status.reducer.materialize()` or `rematerialize`, never any command that writes `status.json`, `meta.json`, `status.events.jsonl`, `lanes.json` or WP frontmatter.** `materialize_snapshot` is the read-only function; `materialize` also writes `status.json` into the Mission directory and on this checkout rewrites tracked snapshots. The test proves its own read-only property by hashing every tracked file under `kitty-specs/` before and after.
- Depends on WP06 (`fixture_builder.py` is the single authority for planted leak classes that the payload scan uses; `leak_patterns.py` from WP01) and WP09 (the first possible green `contracts-gate`, which P2 requires). IC-01 to IC-05 and IC-08 are therefore all merged.
- **Precondition (ORCHESTRATOR action, checked and recorded by the implementer before the first commit).** The ratchet over the snapshot-versus-files disagreement list is priced debt (Standing Order 5): a tracker issue must exist **before this WP starts**, with a named owner (a GitHub handle or team; a role is not an owner), the exit condition (a disagreement list of length zero) and a `drain_by` calendar date set by the maintainers on the issue (no release version used as a date, C-008). **Agents never open issues, pull requests or comments**: the orchestrator opens the issue (while WP09 is in review) and tells the implementer the issue number, owner and `drain_by`. If the issue is not provided, stop and report; do not invent values. The pinned fixture header carries the keys `issue`, `owner` and `drain_by`, and a unit test fails when any is missing, empty or malformed: `issue` must match a numeric issue reference (`#<digits>` or `<digits>`, not `TBD`), `owner` must match `^@[A-Za-z0-9][A-Za-z0-9-]*(/[A-Za-z0-9._-]+)?$` (an explicit leading `@` is required, with an optional `org/team` suffix, so a bare role word such as `maintainers` is rejected), and `drain_by` must be an ISO date (`YYYY-MM-DD`, regex-checked and string-compared against a pinned floor date, with no `datetime` import in `tests/`; or read through the kernel clock door).
- The reality check is selected **once** per change, by the router's `tests-corpus` job through the `contracts/**` glob (WP01); on push to `main` and on diffs matching the packs `built_in` filter, `built-in-corpus-suite` runs it too by existing design, without a JVM and with `--cov=src/doctrine`. It must pass in both, never skip, never pass vacuously. An edit confined to `tests/contract/**` selects no job (accepted risk P-10): the README's one-line local command is WP11's.
- No `src/` change (C-002); the helper and test live under `tests/`. `tests/contract/conftest.py` (upstream-contract loader), `tests/contract/test_handoff_fixtures.py` and `contracts/fixtures/` are untouched (C-004).
- **Reader chain (design notes)**: `MissionStatus.load` (`specify_cli.status.aggregate`) for the coordination-aware read directory; on `CoordinationBranchDeleted`, `CoordAuthorityUnavailable` or `MissionMetadataUnavailable`, fall back to the Mission's own directory, list the Mission and print the count (environment-dependent: never floored or ceilinged). All pinned numbers come from a second cheap own-directory pass (`materialize_snapshot` over each Mission directory, no payload built), so the same figures hold in a clone and in CI. Public readers to compose from the test side only: `MissionStatus.load`, `materialize_snapshot` (`specify_cli.status.reducer`), `resolve_mission_identity` (`specify_cli.mission_metadata`), `resolve_mid8` (`mission_runtime.identity`), `compute_weighted_progress` (`specify_cli.status.progress`), `reconstruct_wp_view` (`specify_cli.status.wp_view`), `dependency_readiness_for_wp` (`specify_cli.core.dependency_graph`), the tail reader (`specify_cli.status.tail_reader`), `read_authored_wp_frontmatter` (`specify_cli.status.wp_metadata`). Never rebuild a status path by hand; never open `status.events.jsonl` with a hand-rolled parser where a public reader exists.
- **Derivations without a public reader** (lifecycle status, phases, `readyToStart`, `missionCount`) live in the helper as the executable form of the rules written in the contract's schema descriptions (the description is the single authority); the helper's unit tests cover every branch with planted lane-count fixtures; the pinned fixture keeps it from testing only itself. Rules: `data-model.md` "Derivation rules".
- **Event projection** is an allow-list (FR-007): status transitions and the seven contract-owned lifecycle types only; `missionId` from the Mission's `meta.json` identity, never `aggregate_id`; dropped rows counted per event type; `LIFECYCLE_EVENT_TYPES` minus the allow-list printed on every run. **Actor projection** (D-10) and **leak classes** (D-14) as specified; every redaction printed with Mission and field.
- **Layout (D-P8)**: `tests/contract/_mission_status_payloads.py` (builders, projection and derivation functions, redaction, leak classes; no test collected from it) with unit tests in `test_mission_status_payloads.py`; `test_mission_status_reality.py` with a parametrised per-Mission test (case id = Mission directory name) and a few corpus-level tests, each corpus-level test carrying an explicit `timeout` mark with the rationale beside it; setup lazy per case (a module-scoped fixture would charge the whole build to the first test and break the 60 s per-case budget). Single-line marker `pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]` on both test modules, with sorted registry rows appended to `tests/architectural/test_ci_corpus_trigger_completeness.py` (owned here for that one purpose).
- **Contract loading**: through `contracts/tools/contract_resolver.py` only (imported by file path), validating with `schema_formats.FORMAT_CHECKER`. If the resolver or contract is unavailable the test fails; no skip path exists.
- **Non-vacuity guards**: (a) the per-Mission case list comes from the same enumeration function as the own-directory floors pass; an empty case list is a **collection error** (`pytest.ini` sets no `empty_parameter_set_mark`, so an empty parameter set would otherwise skip silently and stay green); (b) a corpus-level, non-skippable test asserts the number of generated cases equals the Missions-with-`meta.json` count and is at least the floor, and that the number of cases that actually executed (a module-level counter) equals that count; (c) the counting test is the **last test of the file**: under `--dist loadfile` the whole file runs on one worker in definition order, so the counter is complete when it runs.
- **Floors (re-measure at start; WP01's baseline hand-off, recorded in `research.md` R-8, is the cross-check; pin below measured values)**: at least 500 Missions with `meta.json`, at least 3000 file-backed work package payloads, summed own-directory snapshot work packages at least 2800; each of the nine status lanes represented in some `statusLaneCounts`; each of `active`, `planned`, `done`, `draft` occurs; each of the four stamped topology values and `unknown` occurs (evaluated over the own-directory pass); the test fails if a floor is not met and no fixture covers it (`discarded` occurs in zero committed Missions, so a fixture-built payload is its positive control). Planning measurements (indicative only): 539, 3125, 2936, 52 disagreeing Missions (45 fewer, 7 more).
- **Disagreement list**: for every Mission assert `wpTotal == len(snapshot.work_packages)`; list every Mission whose snapshot count differs from its `tasks/WP*.md` count with both numbers; assert the list length at or below a pinned **shrink-only ceiling** (the ratchet; header keys `issue`, `owner`, `drain_by`), and add a test that fails when the measured length is strictly below the ceiling ("stale ceiling: lower it to N"), so the ceiling only ever moves down; each test has a planted violating value and a clean control. A work package present in the snapshot with no file is not representable and is counted here, never dropped silently.
- **Controls on one shared fixture**: a real Mission payload validates; the same payload with a planted e-mail, absolute path, unknown status lane or extra property fails; the snapshot-equality assertion has a positive control (a fixture work package whose frontmatter `lane`, `agent` and `assignee` deliberately differ from its event log must project the snapshot values) and a negative control (the same payload patched with the frontmatter value fails equality). Equality re-reads `materialize_snapshot` independently; it does not reuse the helper's intermediate. Plus: overview builder with reads of `tasks/WP*.md` trapped (patched `open` and `Path.read_text` raising on any matching path); strict ordering of the built list by `createdAt` descending then `missionId` ascending with no ties; `missionCount` equals the number of overview records; duplicate `missionId` fails and duplicate `displayNumber` passes; an e-mail actor projects to all-null and `user`/`finalize-tasks` project to `tool` only.
- **Pinned expected-output fixture (D-P9)**: `tests/contract/fixtures/mission_status_expected.json` holds lifecycle values for a named sample of Missions where file set and snapshot set agree, covering each lifecycle value and each documented quirk (blocked-only reads as planned; all-canceled with `acceptedAt` reads as done). Produced **once** by a throw-away extraction of the two pure derivation functions from the dashboard code at commit `d78aa2345` (`git show d78aa2345:src/specify_cli/dashboard/scanner.py`, read-only, run in a scratch directory); the generator is **not committed** (it would reintroduce removed code). The header records the commit, the two function names, the sample selection rule and the ratchet keys. The test compares the helper's output with it on every run and never skips.
- **Contract-shape changes forced by this WP** (it may force changes to WP03 to WP05 schemas, and owns `contracts/mission-status/**` for that): each change to the shape of a field a client could already have generated against is logged in the module `CHANGELOG.md` under a `Pre-release shape change` heading with the reason; **making a property optional or nullable is itself breaking for generated clients**, so it is announced, never treated as a safe relaxation. A required property absent from real data is a contract defect to fix, never a reason to skip a Mission. The module `CHANGELOG.md` is inside `contracts/mission-status/**` and so is owned here; WP11 (which depends on this WP) writes it afterwards, so the writes are sequential. Append under the heading only.
- **Performance (NFR-001)**: the reality check module at most 120 s on a standard runner and each case at most 60 s, fixture setup included, under `--cov` as well; the whole `tests-corpus` job against its 10 minute timeout with at least 50 percent headroom; `built-in-corpus-suite` (20 minute timeout, `-n auto --dist loadfile --cov=src/doctrine`; the one-file reality check runs serially on one worker). Measured from the CI job log by WP12, not asserted in the test (no timing flake).
- **Python hygiene and S-rules (binding for this WP)**: run `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` before the final commit and record both results (NFR-007). `contracts/tools/*.py` are non-test code, so ruff's bandit rules (`S`) apply there in full: shell out only with argument lists and `shutil.which`-resolved binaries (S603, S607), call `urlopen` only after an explicit `https` scheme check (S310), and make any suppression a one-line `# noqa: S###` with a stated rationale, never a blanket one. Run `mypy --strict` locally over new modules as discipline (no CI job). In `tests/`, never import `datetime` and never call `datetime.now()` or `time.time()` (clock-ban gates, named below): compare ISO-8601 strings or use the kernel clock door.
- **Open-PR overlap check (2026-10-02)**: #5540 and #5326 touch none of this WP's files. Re-run at start.
- Baseline from WP01's hand-off; red-first (C-010): the reality check and each helper function start as failing tests against an empty or wrong contract, then go green.

### Test surface, gates and baseline

- Targeted: `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_mission_status_reality.py tests/contract/test_mission_status_payloads.py`; `.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py` (proves selection by the `tests-corpus` expression; record the output); the NFR-007 non-gating coverage run: `.venv/bin/python -m pytest -q tests/contract/test_mission_status_payloads.py --cov=tests.contract._mission_status_payloads --cov-branch --cov-fail-under=90` (paste output in the hand-off; local discipline only, since `diff-cover` is vacuous for this Mission).
- Named gates: `tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py` (the helper and test parse and order dates, so compare ISO-8601 strings, never import `datetime`) `tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_workflow_coherence.py` and all `contracts/tools/` checks green against the contract after any schema fix. No architectural directory sweep, no `make test-full`.
- Before and after the full reality run: `git status --porcelain` identical; the test's own hash proof passes.

## Subtasks

### Subtask T062: Failing reality-check skeleton and non-vacuity harness

**Purpose**: red-first and FR-025 guards.
**Steps**: create `test_mission_status_reality.py` with the enumeration function, floors, the collection-error guard for an empty case list, the generated-versus-executed counting test (last in file) and the read-only hash proof (hash bytes of every file listed by `git ls-files kitty-specs` before and after the whole build, fail on any difference, fail when zero files hashed; requires `git`, present in both corpus jobs). Include a planted empty-enumeration case. All red on the base.
**Files**: `tests/contract/test_mission_status_reality.py` (new; enumeration, floors, hash proof, counting test last), `tests/architectural/test_ci_corpus_trigger_completeness.py` (row added in T068).
**Validation**: red for the intended reasons.

### Subtask T063: Helper: identity, overview and project builders

**Purpose**: FR-003, FR-004, FR-009.
**Steps**: failing unit tests first, then builders for overview (via the public readers above, never reading `tasks/WP*.md`), `missionCount`, `topology` mapping (`unknown` for unstamped or unrecognised, D-11), `mid8` null when no id, ordering key, derivations for `lifecycleStatus`, `blockedCount`, `lastActivityAt`, `progress`, `streamCursor` from the tail reader.
**Files**: helper (~500 lines across subtasks), unit tests (~400 lines).
**Validation**: unit tests green; trap test green.

### Subtask T064: Helper: detail, phases, work package payloads and actor/redaction logic

**Purpose**: FR-005, FR-006, FR-012.
**Steps**: failing tests first for every phase-rule branch with planted lane-count fixtures (including implement-before-review ordering and zero work packages); work package payload from `reconstruct_wp_view` and snapshot; `readyToStart`; history as transitions only; actor projection (three stored forms); strict-field null-or-error and human-text substring redaction with `[path]`/`[email]` tokens and printed redactions; model sentinel to null; quoted `execution_mode` normalisation; colon-encoded agent strings not split.
**Files**: `tests/contract/_mission_status_payloads.py` (builders and projection, shared with T063 and T065), `tests/contract/test_mission_status_payloads.py`.
**Validation**: every helper function has a direct unit test; branch coverage at least 90 percent in the non-gating local run.

### Subtask T065: Event projection

**Purpose**: FR-007 allow-list on real logs.
**Steps**: failing tests first (status transition row, each of the seven lifecycle types, dropped kinds counted per type including a planted unknown row kind that must be dropped, never forwarded); project every committed log; validate each projected event against the event schemas; assert at least one event of each of the two row-derived kinds; print dropped counts and `LIFECYCLE_EVENT_TYPES` minus the allow-list.
**Files**: `tests/contract/_mission_status_payloads.py` (event projection), `tests/contract/test_mission_status_payloads.py`.
**Validation**: green; the projection never reads raw rows into a payload.

### Subtask T066: Pinned expected-output fixture

**Purpose**: D-P9.
**Steps**: with the orchestrator-provided issue/owner/`drain_by`, run the one-off extraction of the two derivation functions from the dashboard code at `d78aa2345` in a scratch directory (read-only `git show`), produce the JSON for the named sample (each lifecycle value, each quirk), commit only the fixture; unit test: header keys present, non-empty and well formed (numeric issue, `@`-prefixed handle owner, ISO `drain_by`, each with a planted bad value; the owner plants include `maintainers` (a role word without `@`), `@two words`, an empty string and `TBD`, all rejected); reality check compares the helper output with it.
**Files**: `tests/contract/fixtures/mission_status_expected.json` (new, header plus sample), `tests/contract/test_mission_status_payloads.py` (header tests).
**Validation**: the fixture header names commit, functions, sample rule and ratchet keys; mutation check: altering the helper's rule makes the comparison fail.

### Subtask T067: Per-Mission test, controls, snapshot equality, ordering, disagreement ceiling

**Purpose**: FR-019.
**Steps**: implement the parametrised case (builds overview, detail and every work package payload, validates against the contract through the resolver, names Mission, work package and JSON pointer of the first failure), the controls on one shared fixture, snapshot equality with positive and negative controls, the strict-ordering and `missionCount` assertions, the unique-`missionId` assertion, the disagreement list with its ceiling, and the fallback-count print.
**Files**: `tests/contract/test_mission_status_reality.py` (per-Mission case, controls, equality, ordering, ceiling), `tests/contract/_mission_status_payloads.py` as needed.
**Validation**: full local run green with zero exclusions; wall-clock and per-case durations recorded for WP12 (informational, local); hash proof passes.

### Subtask T068: Contract fixes, registry rows, gates and p2 inputs

**Purpose**: close.
**Steps**: apply any schema fix the run forces (log under `Pre-release shape change`, re-run every `contracts/tools/` check and the examples test); append sorted registry rows for the two test modules; run targeted tests, gates, ruff; record the candidate last commit and counts for WP12.
**Files**: `contracts/mission-status/**` (only where the run forces a fix), `contracts/mission-status/CHANGELOG.md` (append under `Pre-release shape change`), `tests/architectural/test_ci_corpus_trigger_completeness.py` (+2 rows).
**Validation**: all green; `git diff --stat` shows nothing under `src/`, `contracts/fixtures/`, `ci-module-registry.yml`, `pytest.ini`.

## Close-out step: publish preview point `p2` (ORCHESTRATOR action, recorded in this WP)

Agents never push and never create remote tags (publication rule at the end of this section). **P2, pin-grade** is the **last commit of this WP**, on which the reality check is green with **zero exclusions** and `contracts-gate` is green. After this WP is **approved** and a green contracts run exists on that commit, the immutable preview tag `preview/mission-status/p2` is published as a lightweight tag on it (the last commit of this WP is the head of seam 5, so the tag is cut at the head of PR 5 and cites PR 5), recorded as the commit plus the run id. **Tag publication (plan E-3, identical in WP05, WP09 and WP10).** The push of the tag and the note on #5528 are maintainer acts. After this WP is approved, the orchestrator prepares the lightweight-tag command and the #5528 note and publishes them only acting for a maintainer (with that maintainer's go-ahead); agents never push and never create remote tags. Record "prepared" and "published by <maintainer, or orchestrator acting for them>" separately in the hand-off. Fallback if no maintainer publishes: a `git archive` tarball of the split tree with its sha256, posted on #5528. This is the point to pin generated clients to; the release `contract-mission-status-v1.0.0` follows merge (a maintainer action, not in this Mission). If history is rewritten (the compact-history step of any seam from seam 1 to seam 5, each of which also rewrites the seams above it) or a brace re-sweep landed after p2 was published, re-publish under the next counter suffix (`p2-r2`, `p2-r3`, ... independent of p0 and p1), naming the cause (`compact history` or `brace re-sweep`) on #5528; the old tag stays until the UI team has moved. Record the tag name (not a hash) and the "prepared" versus "published by" status in this WP's hand-off for WP12.

## Definition of Done

- Reality check, helper, unit tests and pinned fixture exist; floors, controls, snapshot equality, read-only hash proof, ordering, unique ids, disagreement ceiling and non-vacuity guards all pass with zero exclusions, red first; no skip path.
- The tracker-issue precondition is recorded (issue number, owner, `drain_by`) in the fixture header and the hand-off; the header-format tests and the stale-ceiling test pass with planted violations; the issue number is carried to `close-out.md` section 5 by WP12.
- `ruff check .` and `ruff format --check .` clean; new Python passes `mypy --strict` locally; the two clock-ban gate files green.
- `materialize` / `rematerialize` / any writer is never called (reviewer greps); `git status` unchanged by the run.
- Collect-only output recorded; the local coverage output pasted; durations recorded.
- Contract fixes (if any) logged under `Pre-release shape change`; every `contracts/tools/` check still exits 0.
- Registry rows appended; gates green; no `src/` change.
- Hand-off lists p2 inputs; the orchestrator step is pending or done with the tag name.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- A reader that writes: the hash proof catches it; never call writers while investigating.
- Floors copied from the plan instead of measured: measure, pin below.
- Developer-clone versus CI differences (coordination branches): use the own-directory pass for pinned numbers; confirm against the first CI log.
- Timeouts under `--cov` in `built-in-corpus-suite`: keep heavy work inside the per-case budget; WP12 measures.
- A stranger's Mission data defect reddening an unrelated PR: triage per R-4 (contract gap, reader defect, data defect); the pre-approved exclusion path needs an issue, owner and drain date and is not used at delivery.

## Reviewer Guidance

Grep for `materialize(` and `rematerialize` (must be absent; only `materialize_snapshot`). Verify the first commit is red. Verify floors were measured, the counting test is last, the empty-case-list guard exists, controls share one fixture, snapshot equality re-reads the snapshot, and the pinned fixture header is complete and its generator is not committed. Confirm contract changes are logged and no property was made optional without an announcement.

Implementation command: `spec-kitty agent action implement WP10 --agent claude`
