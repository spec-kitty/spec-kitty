---
work_package_id: WP09
title: Oracles and the reality extension
dependencies:
- WP07
- WP08
requirement_refs:
- FR-025
- FR-024
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- NFR-006
- NFR-009
- SC-002
- SC-004
- SC-005
- SC-007
planning_base_branch: issue-5776-mission-status-contract-health-drift-ops
merge_target_branch: issue-5776-mission-status-contract-health-drift-ops
branch_strategy: Planning artifacts for this mission were generated on issue-5776-mission-status-contract-health-drift-ops. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5776-mission-status-contract-health-drift-ops unless the human explicitly redirects the landing branch.
subtasks:
- T047
- T048
- T049
- T050
- T051
- T052
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- tests/contract/_mission_status_oracles.py
- tests/contract/fixtures/mission_status_health_drift_ops_expected.json
execution_mode: code_change
model: ''
owned_files:
- tests/contract/_mission_status_oracles.py
- tests/contract/test_mission_status_reality.py
- tests/contract/_mission_status_payloads.py
- tests/contract/fixtures/mission_status_health_drift_ops_expected.json
- .github/workflows/ci-router.yml
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP09 - Oracles and the reality extension

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Build the independent oracles, extend the reality check to run the three reads over the real corpus with named lists, floors, a pinned anomaly fixture, the offline named skip and read-only fingerprints, and host the corpus-sized cases moved here (AC-DRIFT 19 completion equality and AC-CROSS 4).

## Context

IC-09 may be split by the orchestrator (oracles, then the corpus run and floors), same lane. The v1 pass and the 8-Mission ratchet header of the reality module must NOT be touched. This module runs in the serial 10-minute `tests (corpus-blocking)` job: the NFR-001 gain bound is the arbiter (D-P5; W-7 measures it). Network flakiness in a required job is a known risk (Reflexivity item 2): the offline path takes a named skip for the resolver-dependent assertions only. No new job and no new registration pair (the reality module already exists); the one exception is the single `ci-router.yml` router glob for `src/specify_cli/audit/classifiers/status_json.py`, which the oracle module is the first to import (owned files; note 19 of `reviews/tasks.ruling.md`). Floors are fixed in D-P13 and never re-pinned; a floor above a re-measure is an escalation.

Plan concern: IC-09 of `kitty-specs/mission-status-health-drift-ops-01M464D3/plan.md`. Read, in this order, before writing anything: `.kittify/charter/charter.md`, `AGENTS.md` (for conventions only), the Mission's `spec.md` (the requirement ids in the frontmatter), `plan.md` sections named below, `research.md`, `data-model.md`, `quickstart.md` and `contracts/*.md` in `kitty-specs/mission-status-health-drift-ops-01M464D3/`.

**Dependencies and order.** Depends on WP07, WP08; the lane workspace already holds their approved commits. No work package is dispatched before the orchestrator's Step 0 record exists in `tracer-approach.md`. **Pre-dispatch (orchestrator Step PD in `tasks.md`, operator ruling 13):** before this dispatch the orchestrator fast-forwards the mission-lane branch `kitty/mission-<slug>` and, once the orchestrator's run of `spec-kitty agent action implement WP09 --agent claude` (the command of your Implementation command section; it creates or resumes the lane workspace) has created this lane workspace and before you are started, merges the planning branch into it and greps inside it for every record this prompt reads: the Step 0 record (heading `## Record: Step 0`) and the hand-off records of WP03, WP07 and WP08 (headings `## Record: Hand-off WP03 (`, `... WP07 (` and `... WP08 (`), all in `tracer-approach.md`; read them from the lane workspace root. If a line the prompt tells you to read is not there, stop and report it; never run `--refresh-planning-commit` and never copy a record in by hand.

## Owned files (write scope; final, explicit, no directory-wide glob)

- `tests/contract/_mission_status_oracles.py` (new: created by this WP, listed in `create_intent`)
- `tests/contract/test_mission_status_reality.py`
- `tests/contract/_mission_status_payloads.py`
- `tests/contract/fixtures/mission_status_health_drift_ops_expected.json` (new: created by this WP, listed in `create_intent`)
- `.github/workflows/ci-router.yml`: ONE `**/specify_cli/audit/classifiers/status_json.py` entry in the `contract_tools` group, in sorted position, in the commit that first imports that `src/` file (the commit that creates `_mission_status_oracles.py`, because its `classify_status_json` call imports it; orchestrator note 19 of `reviews/tasks.ruling.md`, analyze finding C1). No other `ci-router.yml` edit belongs to this work package.

No file under `kitty-specs/` is in this write scope: record what you learn in the hand-off; the orchestrator appends it to the tracer files. An out-of-map edit is acceptable only when small, well-justified and recorded with a one-line rationale in the hand-off. Shared files in this list are declared chokepoints serialised by the dependency chain (plan 'Declared shared-file exceptions'); edit only your own entries in them.

## Implementation concern (plan section IC-09, verbatim)

- **Purpose**: The independent oracles, the corpus run of the three reads, named lists, floors, fixture, offline skip, read-only fingerprints.
- **Relevant requirements**: FR-025, NFR-001, NFR-002 (corpus parts), D-P13, D-P14, SC-002, SC-004, SC-005, SC-007, AC-REALITY 1 to 3; **plus the corpus-sized cases moved here by plan-round ruling 4: AC-DRIFT 19 (equality with `is_mission_completed` over every non-coordination corpus Mission) and AC-CROSS 4 (the real `kitty-ops/` listing at most 5 s, one `Project` build and one scan at most 120 s each, and the single case that times the memoised pass, the Project build and the per-Mission reductions together), each with a discovered-count guard**.
- **Affected surfaces**: new `_mission_status_oracles.py`; edited `test_mission_status_reality.py`, `_mission_status_payloads.py` (`FLOORS`), new `tests/contract/fixtures/mission_status_health_drift_ops_expected.json`.
- **Red-first**: the AST independence test, the floor tests (a floor loosened to one fails), the named-list and stale-entry tests, the offline-skip test (a planted unreachable remote: only the named resolver-dependent assertions skip, including the Project-build, scan and combined timing cases, which count as skipped and not executed; the Ops walk, `skippedCount` equality, the Ops floors, the AC-DRIFT 19 completion equality with its 490 floor, the real `kitty-ops/` listing bound and the fingerprints still run and count as executed; a plant that moves the completion equality or the listing into the skip, or runs the Project build offline, must fail) and the fingerprint tests with a writing reader, the completion-equality case (the guard: compared count equals the independent count of Missions declaring no coordination branch and is at least its floor of 490; a planted zero-Mission directory fails) and the corpus-sized timing cases (a planted over-bound case fails), plus the cache-the-result mutation applied as a context manager in the reality module (a memoising real-directory listing must turn the real 5 s listing case of AC-CROSS 4 red; the mutation is scoped to the module that holds the case, plan-round ruling 9), all against oracle stubs that raise.
- **Sequencing**: after IC-07 and IC-08. **Acceptance (named)**: the corpus run green with the remotes reachable and the named skip offline (both shown); an AST test; planted floors, stale entries, a writing reader and the cache-the-result mutation (a memoising real-directory listing turns the real 5 s case red) fail; the runtime within NFR-001 (measured).
- **Risks**: runtime (D-P5); network flakiness in a required job (Reflexivity item 2); the 8-Mission ratchet header and the v1 pass must not be touched.

## Design decisions that bind this work package (plan, verbatim)

**D-P13 Floors (FR-025, spec D-P15; the completion-equality floor is added by plan-round ruling 4).** Fixed here, never re-pinned, below the plan-time measurement by one stated rule (95 percent rounded down to two significant figures; counts under 100 at 90 percent rounded down; named anomaly classes by a subset check): Missions examined 540 (of 569); Ops served 440 (of 473); spine-closed Ops 5 (of 6); evidence of each kind own-file: none 330, absolute path 28, free text 50, relative reference 25, `url` 0 (fixture-only floors: `url`, a redacted address, a withheld credential); kind-1 findings 39 (of 44: 43 terminal, 1 provenance, 0 plain), kind-2 findings 27 (of 31); completion-equality guard of AC-DRIFT 19: Missions declaring no coordination branch compared 490 (of 518, which is 569 less the 51 declaring one; 95 percent rounded down to two significant figures); **no kind-3 floor** and no fallback floor. IC-01 verifies each floor sits below the re-measure; a floor above a re-measure is an escalation, not a re-pin. A floor loosened to one fails (a test), and `floor_failures` keeps the v1 shape.

**D-P14 The oracles (FR-025, spec D-P14).** `_mission_status_oracles.py` holds the independent oracles: kinds 1 and 2 (file presence plus `classify_status_json` filtered to the four kind-1 codes and the reader's population, with the `UnicodeDecodeError` wrapper unit-tested), kind 3 (D-P6), the fallback derivation (an agreement check on this corpus, not a mirror of the resolver; each resolver arm it does not mirror has a fixture), and the Ops direct scan of every Op file and of the spine. An AST test asserts that the oracle module and the oracle functions of the reality module neither call nor import any reader module (textual guards are bypassable by design and accepted at severity 1 to 2, as in the previous slice's tracer friction F-42).

**D-P16 Timing method for absolute bounds (plan-round ruling 6; NFR-002, NFR-008; not the spec's D-P15, which is the floors rule).** The 0.1 s redaction bound (three 256 KiB shapes), the 5 s real-directory bound and the 30 s 10,000-file bound are absolute wall-clock assertions in a blocking `-n 4 --dist loadfile` job. Each shape is therefore timed as **the minimum of at least 5 repeated runs inside the test** (the minimum is robust to contention and still falsified by a quadratic matcher, whose long shape stays far over the bound on every repeat); the short-value control is timed **the same way**; the planted quadratic mutation (the pre-fix pattern) must still fail under this method, which the mutation table proves. A fixed repeat count of 5 is the floor, not a retry: no test reruns to green. **Every repeat is cold:** a fresh call of the production entry point on an identical input with no state shared between repeats (new reader state, the per-run memo and the remote-branch lookup cache reset, a fresh opener, and the directory handle rebuilt or re-opened per repeat for the 5 s and 30 s cases); the test asserts that no cache was hit (a counter at zero) or that the call count equals the repeat count, so the minimum is never a cache hit. A second planted mutation, **cache-the-result** (the entry point memoises its result across calls), must turn AC-OPS 14 and the timing cases red, and is also applied as a context manager in the reality module against the real 5 s listing case (plan-round ruling 9); it joins the Ops mutation catalogue beside the quadratic matcher. The work package records the measured minimum and the margin to the bound in its hand-off report (the orchestrator appends it to the tracer file), and a margin under a factor of 2 goes to the operator rather than loosening the bound. The 5 s real-directory case belongs to the reality module (D-P5); the 30 s synthetic case and the 0.1 s cases to the ops module.

**D-P5 Placement; no new job.** The reality extension stays in `test_mission_status_reality.py` (router job `tests (corpus-blocking)`, serial, 10-minute timeout); the three new reader modules and the proof edits run in `tests (contract tools)` (selected automatically: the job takes the directory minus three `--ignore` modules). **Corpus-reading cases live in the reality module only (plan-round ruling 4):** AC-DRIFT row 19's equality with `is_mission_completed` over the real corpus, and the corpus-sized cases of AC-CROSS 4 (the real `kitty-ops/` listing at most 5 s; one `Project` build and one project-wide scan at most 120 s each), run there with a discovered-count guard (D-P13); `docs/development/reference/ci-gate-mechanics.md` documents the tool job as reading no corpus, and its budget carries no measured corpus time. The three new modules are **fixture-built only** (a temporary repository per case, each plant with its control); no docs edit is needed. **Budget (NFR-001 is a gain bound):** the plan-time local figure of the unchanged corpus job is 108 s and its CI duration about 3 minutes (a remembered figure of the previous slice, not a baseline), a local-to-CI factor of about 1.7. The added work is the second, memoised resolver pass (the v1 pass stays; about 37 s local), the scan's remaining reduction (about 3 to 15 s local) and the Project reduction (about 7 s local): about 45 to 60 s local before the items priced below (about 75 to 100 s in CI by that factor, a derived estimate, not a measure). **Execution sharing (NFR-001 stays honest):** the Project-build bound, the scan bound and the combined case are ONE execution: the combined case builds the `Project` and runs the memoised pass and the per-Mission reductions once and records each duration, and the two separately named bounds assert on those same measured durations (no second Project build, no second scan, so no scan-reduction or Project-reduction time is added twice). The other added work is priced separately, in local seconds: the AC-DRIFT 19 completion equality reads about 518 own directories (an estimate of about 5 to 10 s local, measured by the IC-01 proxy), and the real-directory listing is repeated at least 5 times at its expected cost of well under 1 s each, about 5 s local in all (the 5 s bound is an assertion that a failing run would trip, not a budget input, so a 25 s worst case is not priced). The job-gain-only items therefore total about 10 to 15 s local, and the local estimate is the 45 to 60 s base plus those 10 to 15 s, about 55 to 75 s, which is about 94 to 128 s in CI at the 1.7 factor (a derived estimate, not a measure). The top of that range exceeds the 120 s gain bound and the bottom is not safely inside it, so the arithmetic does not prove the bound; the IC-01 proxy and the W-7 pass rule govern. The control is not this arithmetic: IC-01 measures the proxy first, the first PR run is judged against the recorded baseline, and the 6-minute re-plan threshold below stays the explicit limit. Offline the Project, scan and combined cases are skipped and cost nothing. **Baseline:** the orchestrator's Step 0 records the median duration of the last five successful `main` runs of both `tests (corpus-blocking)` and `tests (contract tools)` (Baseline section). **Pass rule at W-7:** the first PR run's `tests (corpus-blocking)` duration minus the recorded median is at most 120 s, and `tests (contract tools)` stays under its 15-minute timeout with the margin recorded; re-plan if the first run shows more than 6 minutes of corpus job time (about 3 minutes baseline plus the 2 minute bound is 5 minutes; 6 leaves one minute of runner noise). **In-test:** no case over 120 s, and one case in `test_mission_status_reality.py` times the memoised pass, the Project build and the per-Mission reductions together, so the in-test bound and the job gain are different quantities: the combined case is the largest component of the gain, not the whole (the v1 pass is not part of either; the AC-DRIFT 19 completion equality and the repeated real-directory listing sit in the job gain only, about 10 to 15 s local, 17 to 25 s in CI, the same figure as above), and a combined case passing under 120 s does not imply the job gain is; the W-7 pass rule above is the arbiter of the job gain (plan-round ruling 10). IC-01 measures the proxy first, and a local proxy of the job gain above about 70 s (the 120 s bound divided by the 1.7 local-to-CI factor, stated in local seconds) goes to the operator before the bound is set (research R-12; plan-round rulings 8 and 11). The 70 s line is stated against the SUM: the combined case plus the 10 to 15 s of completion equality and listing repeats, so the combined case alone escalates at about 55 s local (70 s minus the upper 15 s); the W-7 pass rule stays the final arbiter. **Markers:** the drift and project modules build real git repositories and the resolver starts git, so they carry `contract`, `corpus` and `git_repo` and **not `fast`** (as the detail module of the previous slice); the ops module carries `contract` and `corpus` and not `fast` (it holds the timed 10,000-file and 256 KiB cases, which are not sub-second); **every new module declares a module-level `pytestmark`** (the class of defect of an unmarked corpus reader that is silently never run), **written as one single-line list that holds `pytest.mark.corpus` on the same physical line as `pytestmark =`**, in the form of `tests/contract/test_mission_status_detail.py` (`pytestmark = [pytest.mark.contract, pytest.mark.corpus, pytest.mark.git_repo]`): `_CORPUS_MARK_APPLICATION_RE` of `tests/architectural/test_ci_corpus_trigger_completeness.py` matches `pytestmark\s*=.*\bpytest\.mark\.corpus\b` within one line, so a mark spelled through a shared list or wrapped across lines escapes the registry gate (the registry row is then reported as in the registry but no longer marked) while the home gate, which collects for real, still sees it. The registry row and the `--deselect` go in the commit that creates the module, in sorted position. The advisory packs corpus suite must not gain these tests: each new module is deselected there (PD-2).

## Acceptance rows of this work package (plan, verbatim)

Not owned here: the AC-VERSION rows (a to f) and AC-CROSS 2 and 3 below are printed because the plan prints one table; WP06 owns AC-VERSION b and d and AC-CROSS 2 and 3, and the orchestrator owns the recorded-command rows (AC-VERSION a, c, f; W-1, W-2, W-7, J-1). The two-bundle-builds half of AC-CROSS 1 is carried by WP06 (see its note). This work package's rows are AC-CROSS 4 (corpus-sized half), AC-REALITY 1 to 3 and AC-DRIFT 19 (corpus half).

Rule for every row: the test fails when the change is reverted. **Three kinds of revert proof**, named in each row: **B** base-red (the test is red on the work package's base and green on its tip; the first commit carries the test and a stub entry point that raises, so a red is a behaviour failure); **P** planted pair (a control that passes and a plant that fails on the same fixture, so the probe can see the thing); **M** named mutation (a table of reader mutations applied by the test, each of which must turn its rows red: `the mutation was not killed: <name>`; the catalogue is in contracts/tool-extension-and-reader.md). Tests call the reference reader's production entry point, never only a helper. Row numbers are the order of the spec's tables.

| Row | Red-first test (proof kind) |
|---|---|
| AC-VERSION a baseline SHA | recorded command asserts `git merge-base --is-ancestor`; planted: a commit on no branch fails (P, wrap-up) |
| AC-VERSION b byte identity; bundle minus new operations | the extended pair with frozen copies (in the source layout) and removed tags; the masking rule of D-P10 (only `components.schemas.Project` and the `/project` operation description are masked); planted byte change, planted `409`, a planted extra response code on `getProject`, a planted changed 200 schema reference on `getProject`, and a planted change to another existing schema (B, P) |
| AC-VERSION c lowered-major and same-major runs | recorded wrap-up commands with counts; controls in D-P10 (P, wrap-up) |
| AC-VERSION d version equals main; provisional names; Deferred section; CHANGELOG statements | section-scoped test with planted entries; qualified-name plants (B, P) |
| AC-VERSION e enums pinned and snake_case; leak scan; terminology | pin check with a planted camel-case value; leak scan with each planted example of FR-027; terminology scan with a planted second `feature` use (B, P) |
| AC-VERSION f J-1 record | recorded commands: commit exists, ancestor, last touching `contracts/mission-status`; one line per job of `contracts.yml`; planted job name absent from the workflow (P, wrap-up) |
| AC-CROSS 1 determinism | two reads byte-equal; two bundle builds equal; a clock tick changes `scannedAt` only (B, P) |
| AC-CROSS 2 scope | `scope_problems` over the real diff plus planted extra file and planted `src/` path (B, P, wrap-up) |
| AC-CROSS 3 dependencies | a pure check that no entry names `pyproject.toml` or `uv.lock`; planted added dependency fails (B, P) |
| AC-CROSS 4 bounded reads and time | **fixture-built:** counting opener, and subprocess total equals the memo's count plus the listing (drift and ops modules; these are counts, not timings); the synthetic 10,000-file directory at most 30 s (minimum of at least 5 repeats, D-P16) is the Ops module's case only (WP08 T045, plan D-P16 and IC-08), and the drift module has no absolute timing assertion. **Corpus-sized (reality module, IC-09):** real directory at most 5 s (minimum of at least 5 repeats); one Project build and one scan at most 120 s each; one case timing the memoised pass, the Project build and the per-Mission reductions together at most 120 s; each with a discovered-count guard (served plus skipped equals discovered and is non-zero; Missions examined at least the floor); the planted cache-the-result mutation (a memoising listing, applied as a context manager in the reality module) must turn the real 5 s listing case red (B, P, M) |
| AC-CROSS 5 writers | covered by AC-DRIFT 27 and AC-OPS 14 |
| AC-REALITY 1 corpus outcome and fallback list | 200 with only `CoordinationBranchDeleted`; fallback list equals the independent derivation both ways; resolver once per Mission; offline named skip (B, P) |
| AC-REALITY 2 examined plus skipped equals discovered; floors; oracles; AST independence | named lists with stale-entry checks; a floor loosened to one fails; AST test (B, P). Offline: the Missions half (identity, Mission floors, kind 1 to 3 oracles, fallback lists) takes a named skip; the Ops half and the AST test run |
| AC-REALITY 3 per-Mission equals filtered; Ops walk equals the oracle; fingerprints; every generated case executed | the last test counts executed cases against generated cases (B, P). Offline: per-Mission equality takes a named skip (a case skipped by name counts as skipped, not executed); the Ops walk, `skippedCount` equality and both fingerprints run |

AC-DRIFT row 19's corpus half (this WP):

| 19 completion reads the own directory | **drift module (fixtures):** `merged_at` in the own copy only versus the coordination copy only (B, P). **Reality module (IC-09, corpus job):** equality with `is_mission_completed` over every corpus Mission declaring no coordination branch, with a discovered-count guard: the compared count equals an independent `meta.json` scan, is above zero and is at least the floor of D-P13 (490); a planted empty directory fails (B, P) |

## Reality-check design notes (plan, verbatim)

- Reader chain per Mission: `load_source` as today (the v1 pass, untouched); the new builders take the memo's outcome; the strict sibling serves drift; the Project builder serves `Project`; the oracles never see the readers.
- The corpus run order: network probe (outside the reader, `git ls-remote --heads` on each configured remote) decides online or offline; online asserts the 200, the fallback list both ways, the floors, equality with the oracles and the examined-plus-skipped identity; offline asserts the 200 with no fallback entries alone (operator ruling at WP07, 2026-10-06; the first text said 500) and takes a named skip for the resolver-dependent assertions only (Departs 5; the plan-phase operator ruling 1 of `reviews/plan.ruling.md`; the spec's AC-REALITY 2, 3 and the FR-025 sentence say the same): the project-wide report equality, the Missions examined-plus-skipped identity and Missions floors, the fallback list, the kind 1 to 3 oracles and per-Mission equality. The Ops walk and its oracle comparison, `skippedCount` equality, the Ops floors, the AST independence test and the `kitty-specs/` and `kitty-ops/` fingerprints run in both, because they need no network. Offline is not evidence for SC-002 or SC-007.
- Independent counts: Missions (a scan for `meta.json`), the fallback list (D-P14), kinds 1 and 2 (file presence plus the classifier), kind 3 (D-P6), Ops (a direct scan of every Op file and of the spine), evidence kinds (a regex classification of the stored strings); each compared with the examined count; numeric floors second.
- Controls on one shared fixture: a real payload validates; the same payload with a planted host path, e-mail address, credential, unknown enum value or extra property fails; the wiring guard is extended so a removed check turns every case red.
- The case budget: one scan 40 to 52 s locally (spec); no new case over 120 s; the Project build once; per-Mission reports are filtered from the project-wide findings, then compared with the per-Mission entry point (cheap); one bounded case times the memoised pass, the Project build and the per-Mission reductions together (D-P5).
- Corpus-sized cases (plan-round ruling 4) live here and nowhere else: AC-DRIFT row 19 (equality with `is_mission_completed` over every Mission declaring no coordination branch, **guarded**: the compared count equals an independent `meta.json` scan, is above zero and is at least the floor of D-P13) and the AC-CROSS 4 cases on the real directories (at most 5 s for the real `kitty-ops/` listing, timed as the minimum of at least 5 repeats, D-P16; at most 120 s for one `Project` build and for one project-wide scan). Their discovered counts appear in the failure text (contracts/tool-extension-and-reader.md, G). Offline classification of the corpus-sized cases (applies the plan-phase ruling 1; derived from whether a case calls the coordination resolver or the network): (a) the AC-DRIFT 19 completion equality with its 490 floor and discovered-count guard RUNS offline (it reads each Mission's own directory for Missions declaring no coordination branch and never calls the resolver); (b) the real `kitty-ops/` listing bound (at most 5 s, minimum of at least 5 cold repeats) RUNS offline (a directory listing, no resolver, no network); (c) the one-`Project`-build bound, (d) the one-project-wide-scan bound and (e) the combined timing case TAKE the named resolver-dependent skip offline (the Project build and the scan reach the resolver, which offline answers each Mission's own directory with no fallback entry (operator ruling at WP07, 2026-10-06), so a bound measured offline does not measure the online path) and count as skipped, not as executed, in the "every generated case executed" tally.
- `kitty-ops/` fingerprint: the same helper as `kitty-specs/`; both before and after.

### Subtask T047: Red-first: oracle stubs and the guard tests

**Purpose**: Commit 1, against oracle stubs that raise: the AST independence test; the floor tests (a floor loosened to one fails); the named-list and stale-entry tests (both ways); the offline-skip test (a planted unreachable remote: ONLY the named resolver-dependent assertions skip, including the Project-build, scan and combined timing cases, which count as skipped and not executed; the Ops walk, `skippedCount` equality, the Ops floors, the AC-DRIFT 19 completion equality with its 490 floor, the real `kitty-ops/` listing bound and the fingerprints still run and count as executed; a plant that moves the completion equality or the listing into the skip, or runs the Project build offline, must fail); the fingerprint tests with a writing reader; the completion-equality case with its guard; the corpus-sized timing cases with a planted over-bound case; the cache-the-result mutation as a context manager in the reality module.

**Steps**:
1. Behaviour failures, not collection errors; controls red.
2. The mutation is scoped to the module that holds the case (plan-round ruling 9): a memoising real-directory listing must turn the real 5 s listing case red.

**Files**: tests/contract/test_mission_status_reality.py (edit), _mission_status_oracles.py (stub), .github/workflows/ci-router.yml (only if the stub already imports `status_json.py`; otherwise the glob lands in the T048 commit that first imports it)

**Validation**: Red run recorded.

### Subtask T048: Oracles (D-P14)

**Purpose**: Implement `_mission_status_oracles.py`: kinds 1 and 2 (file presence plus `classify_status_json` filtered to the four kind-1 codes and the reader's population, with the `UnicodeDecodeError` wrapper unit-tested), kind 3 (D-P6: shares only `is_mission_completed` and `materialize_snapshot` for a Mission whose read directory is its own; reads `meta.json` and the manifest as raw JSON; each expected name tested with its own `git rev-parse --verify --quiet`), the fallback derivation (an agreement check on this corpus, not a mirror of the resolver; each resolver arm it does not mirror has a fixture), and the Ops direct scan of every Op file and the spine.

**Steps**:
1. The oracles never import or call a reader module; they share the memo helper (WP03) only.
2. No wall-clock default; injected clock.

**Router glob (note 19, finding C1):** the oracle module imports `src/specify_cli/audit/classifiers/status_json.py` (`classify_status_json`). In the commit that FIRST adds that import, add `**/specify_cli/audit/classifiers/status_json.py` to the `contract_tools` group of `.github/workflows/ci-router.yml`, in sorted position (Registration item 4 of the reader prompts; spelled `**/<path>` so the group stays non-src). Without it `test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import` (`tests/ci/test_contracts_workflows.py`) goes red, since it scans every `tests/contract/*mission_status*.py` file. That test is in the gate list below; run it in that commit.

**Files**: tests/contract/_mission_status_oracles.py (about 500 lines), .github/workflows/ci-router.yml (one glob entry)

**Validation**: AST independence test green.

### Subtask T049: Corpus run of the three reads

**Purpose**: Extend `test_mission_status_reality.py`: network probe (outside the reader, `git ls-remote --heads` on each configured remote) decides online or offline; online asserts the 200, the fallback list both ways, the floors, equality with the oracles and the examined-plus-skipped identity, per-Mission equals filtered; offline asserts the 200 with no fallback entries alone (operator ruling at WP07, 2026-10-06; the first text said 500) and takes the named skip. The Ops walk, its oracle comparison, `skippedCount` equality, the Ops floors, the AST test and both fingerprints run in both.

**Steps**:
1. Independent counts first (Missions, fallback list, kinds 1 to 3, Ops, evidence kinds), numeric floors second.
2. Controls on one shared fixture: a real payload validates; the same payload with a planted host path, address, credential, unknown enum value or extra property fails; the wiring guard is extended so a removed check turns every case red.

**Files**: tests/contract/test_mission_status_reality.py

**Validation**: AC-REALITY 1 to 3 green online and offline.

### Subtask T050: Floors, named lists and the pinned anomaly fixture

**Purpose**: Add `FLOORS` entries (D-P13) in `_mission_status_payloads.py` (the v1 shape of `floor_failures` kept) and the pinned fixture `tests/contract/fixtures/mission_status_health_drift_ops_expected.json` of named corpus anomalies, with stale-entry checks both ways.

**Steps**:
1. Missions examined 540; Ops served 440; spine-closed 5; evidence none 330, absolute path 28, free text 50, relative reference 25; kind-1 findings 39; kind-2 findings 27; completion-equality compared 490; NO kind-3 floor and no fallback floor.
2. Verify each floor is below its re-measure (WP01's record); never re-pin.

**Files**: tests/contract/_mission_status_payloads.py, fixtures/mission_status_health_drift_ops_expected.json

**Validation**: A floor loosened to one fails.

### Subtask T051: Corpus-sized cases (AC-DRIFT 19, AC-CROSS 4)

**Purpose**: AC-DRIFT 19: equality with `is_mission_completed` over every Mission declaring no coordination branch, guarded (the compared count equals an independent `meta.json` scan, is above zero and at least 490; a planted zero-Mission directory fails). AC-CROSS 4: the real `kitty-ops/` listing at most 5 s (minimum of at least 5 cold repeats), one Project build and one scan at most 120 s each, one case timing the memoised pass, the Project build and the per-Mission reductions together at most 120 s; each with a discovered-count guard (served plus skipped equals discovered and is non-zero; Missions examined at least the floor).

**Steps**:
0. Measure first: Measure each bound on the unchanged fixture (or corpus) before asserting it; a margin under a factor of 2 (bound divided by the measured minimum) is reported to the operator in the hand-off and the bound is not loosened and the case is not skipped. This covers the 5 s real-directory listing (T051) and the 120 s cases (one Project build, one scan, the combined case); record the measured minimum and the margin of each in the hand-off.
1. Offline: the completion equality and the real listing RUN; the Project build, scan and combined cases take the named skip and count as skipped, not executed.
2. The last test counts executed cases against generated cases.

**Files**: tests/contract/test_mission_status_reality.py

**Validation**: Corpus run green with the remotes reachable and the named skip offline (both shown).

### Subtask T052: Runtime and acceptance

**Purpose**: Measure the module's runtime against the NFR-001 gain bound (the Step 0 median of `tests (corpus-blocking)` plus at most 120 s CI; local figures converted with the recorded factor) and record every timing; run the census and registration gates and the tool-job selection.

**Steps**:
1. Report the measured local durations of each new case and of the whole module, and the margin of each timed bound (bound divided by the measured minimum). A margin under a factor of 2 is reported to the operator in the hand-off; the bound is not loosened and the case is not skipped.

**Files**: none

**Validation**: The runtime within NFR-001 (measured), recorded in the hand-off.

## Validation: gates and targeted test surface (concrete; run from the lane workspace root)

Targeted files only, never a directory sweep. Use `PWHEADLESS=1` and the interpreter of the synced environment recorded at Step 0.

### Tool tests, example and proof modules

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_leak_scan.py tests/contract/test_fixture_builder.py tests/contract/test_enum_pin_check.py tests/contract/test_run_negative_cases.py tests/contract/test_mission_status_examples.py tests/contract/test_mission_status_contract_1_1.py
```

### Reality module and payload helper

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py tests/contract/test_mission_status_payloads.py
```

(plan-time: 819 passed in 108 s locally; the resolver's remote probes need the network. Offline, only the named resolver-dependent assertions take a named skip.)

### Named gate files (router, registry, corpus-trigger, terminology, archive-freeze, ruff pair, cutover guard)

Run after every rebase and before hand-off, and in the commit that adds the `status_json.py` router glob (the router-derivation test `test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import` of `tests/ci/test_contracts_workflows.py` is in the first file below):

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py tests/ci/test_corpus_blocking_home.py \
  tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_same_tier_uniqueness.py \
  tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_workflow_coherence.py tests/architectural/test_no_legacy_terminology.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_archive_root_byte_identical.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
<synced-spec-kitty> cutover-guard --base-ref origin/main
```

Environment note: the checkout `.venv` is hand-built and lacks ruff, mypy and respx (a stale-venv red, bin 4). Use the synced environment the orchestrator recorded at Step 0 (its ruff and test extras; never `uv run` in the checkout `.venv`). **Substitution rule for every command of this prompt: each `.venv/bin/python` and `.venv/bin/ruff` written below reads `<synced-python>` and `<synced-ruff>`** (the `<scratch>/venv/bin/python` and `<scratch>/venv/bin/ruff` of the Step 0 record, defined once in item 2 of the Step 0 block of `tasks.md`); the hand-built `.venv/bin/python` is not used for any gate command of this work package (every `.venv/bin/spec-kitty` written below, the `cutover-guard` gate, reads `<synced-spec-kitty>` = `<scratch>/venv/bin/spec-kitty`, the CLI of the same synced environment, because a lane workspace does not carry the checkout `.venv`; orchestrator note 18 of `reviews/tasks.ruling.md`, defined once in item 2 of the Step 0 block of `tasks.md`, same import check and `PYTHONPATH` rule). Per-file format check: `ruff format --check --force-exclude <files>`.

### Census files that read `tests/` (run at implement start, after every new or edited test module, and at hand-off)

The list is derived at Step 0 from the `fast_gate` roster plus the heavy-battery census files, and every path was checked to exist:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/architectural/test_no_manual_global_state_mutation.py tests/architectural/test_no_tmp_paths_in_tests.py \
  tests/architectural/test_issue_named_test_census.py \
  tests/architectural/test_global_state_allowlist_sealed.py \
  tests/architectural/test_spec_kitty_home_pin_census.py tests/architectural/test_spec_kitty_home_pin_guard.py \
  tests/architectural/test_spec_kitty_home_pin_budget.py tests/architectural/test_home_pin_gate_verdict.py \
  tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_layer_rules.py tests/architectural/test_pyproject_shape.py
.venv/bin/ruff check --select TID251 .
```

Named files only, never the directory, never `tests/architectural` as a sweep (charter rule `NO_FULL_HEAVY_SUITES_IN_MISSION`). The scans inspect real-git fixtures, a `subprocess` stub, a counting wrapper, git identity setup, any manual `os.chdir`, `os.environ` or `sys.path` change, a shared-temp literal and a wall-clock call in a test module: use `monkeypatch` and a scratch `HOME`, an injected clock, and build host-path-shaped plants from fragments. **No allowlist or baseline entry may be added to make a new module pass.** The two dead-symbol files walk `src/` (no `src/` change here) and run only in the Step 0 baseline.

## Red-first rule (C-011, charter ATDD-First Discipline)

The FIRST commit of this work package is its failing tests, with a raising stub for each production entry point the tests call, red on the lane base and committed BEFORE any implementation commit (registration pair included where this WP creates a module). The stub raises (for example `NotImplementedError`), so the red run shows **behaviour failures, not collection or import errors**; the reviewer checks that, and that the **control tests are red too** (a control that is green against the stub is not exercising the entry point). Verify the red without `git stash`: extract the base into a scratch directory (`git archive <base-commit> | tar -x -C <scratch>/base`), copy the new test file(s) and stub in, and run pytest from that directory with the checkout's interpreter; record the failing test ids and the reason in the hand-off. The reviewer verifies red then green: red on the base, green on the tip. Tests call the production entry point, never only a helper. Never weaken, skip or retry-to-green a test.

## Dispatch hygiene (binding for this work package)

- **No sub-agents.** You work alone: do not start, fork, brief or message other agents.
- **A denied command means STOP and report it** in the hand-off; never retry a denied command in another form.
- **No pattern kills** (`pkill`, `killall`), **no `git stash`**, **no `rm` with a variable or wildcard glob**, no checkout, switch, restore, reset, clean or rebase of the shared checkout. Work in the lane workspace the orchestrator assigns; do not move HEAD of any other workspace.
- **Repository-relative paths only** in every file, commit message and report; placeholders such as `<repo>`, `<scratch>`, `<tmp>`, `<user>` elsewhere. This repository is PUBLIC: no absolute path under a home directory, no drive path, no user name, e-mail address, private identifier, chat mention or credential in any file, test, fixture, commit message or report. Leaking values a test needs (host paths, addresses, tokens, an at-sign file name) are assembled from fragments at run time and never typed as literals; no shared-temp literal in any plant.
- **Unicode-escape hazard:** editing tools decode a backslash-u sequence typed into a file into the raw character. Write a NUL as `\x00` in a contract pattern, build NUL with `chr(0)` and a backslash with `chr(92)` in tests, and check every new file for raw NUL bytes after writing.
- **Commit locally. NEVER push, never open a pull request, never comment on an issue, never merge.** Conventional commit subjects ending with `(#5776)`; end each commit message with the attribution trailers the dispatch brief supplies. Commit through `spec-kitty safe-commit` where a guarded branch requires it; never bypass a guard.
- **Never hand-edit** `status.events.jsonl`, `meta.json`, `status.json`, `lanes.json`, issue-matrix files or work package frontmatter; never call `materialize`.
- **Baseline-red binning against the Step 0 record.** Before your first change run this work package's targeted commands once on the unchanged lane base and reconcile with the orchestrator's Step 0 record in `tracer-approach.md` (read it; the orchestrator appends it before any dispatch). Bin every red: (1) pre-existing known-P0 (nightly lane only), (2) CI-environment, (3) stale install, (4) stale venv (resync, then retry), (5) introduced. Only a failure red on your branch and green on the base is yours. A pre-existing red: STOP and report it (command, failure summary, why you believe it is pre-existing); the orchestrator owns the tracker issue (Pre-existing Failure Reporting Rule). Do not absorb it, never retry until green. A red on your lane base but green at the Mission baseline came from an earlier work package of this Mission: report it against that work package, do not bin it as pre-existing.
- Terminology: Mission, never feature; say which sense of lane (status lane versus code lane). New code passes `ruff check` and `ruff format --check` with no suppression added; complexity ceiling 15; a literal used three or more times in a module becomes a constant; new code is annotated to pass `mypy --strict` as local discipline.

## Architectural battery: BINDING local gate (operator ruling 14, extended to this work package by the orchestrator)

Ruling 14 (the local architectural battery, three legs, binding on WP03, WP07 and WP08; see `reviews/tasks.ruling.md` and the battery section of `tasks/WP03-project-vertical.md`) is EXTENDED to WP09, because its one `ci-router.yml` edit (the `**/specify_cli/audit/classifiers/status_json.py` entry of the `contract_tools` group) can select the architectural battery on the pull request. Run the three legs exactly as written in WP03 (same commands, `<synced-python>`, from the lane workspace root, background command with exit-code files, awaited with an until-loop monitor), on the final commit, before the hand-off, and bin every red against the per-leg `## Record: Step 0` baselines. The override of the charter rule `NO_FULL_HEAVY_SUITES_IN_MISSION` applies to these runs only. The note 16 fallback applies unchanged.

## Hand-off report (your final message)

Commits (hash and subject in order, the first marked as the red-first commit); the red evidence (failing test ids, why they are behaviour failures, that the controls are red, how it was verified on the base); every command run with passed/failed/skipped counts and exit codes; baseline bins against the Step 0 record; **measured minima, margins and re-measurements** (every timed bound: the minimum of the repeats and the margin below the bound; every re-measured count; every floor against its re-measure); any refinement of a contract note or design decision; any friction observation (tooling hazards met); anything not done and why. **Code work packages never write under `kitty-specs/`**: the orchestrator appends decisions, measurements and friction add-only to `tracer-approach.md`, `tracer-design-decisions.md` and `tracer-tooling-friction.md` between dispatches.

## Definition of Done

- The corpus run green with the remotes reachable and the named skip offline (both shown).
- An AST independence test passes.
- Planted floors, stale entries, a writing reader and the cache-the-result mutation fail.
- The runtime is within NFR-001 (measured).
- AC-REALITY 1 to 3, AC-DRIFT 19 corpus half and AC-CROSS 4 corpus-sized half.
- First commit is the red tests with a raising stub (behaviour failures, controls red), verified on the base; green on the tip.
- Named gate files and census files green or binned against the Step 0 record; ruff check, ruff format --check and TID251 clean with no suppression added.
- Hand-off carries measured minima, margins and re-measurements; nothing written under `kitty-specs/`. Every timed bound (5 s, 120 s) was measured on the unchanged corpus before it was asserted; a margin under a factor of 2 is reported to the operator and the bound is neither loosened nor skipped.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- Runtime (D-P5).
- Network flakiness in a required job (Reflexivity item 2).
- The 8-Mission ratchet header and the v1 pass must not be touched.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface, plus the named gate files and census files above; never a full sweep.
- Verify red then green: the first commit is the red-first commit with a raising stub; the red run shows BEHAVIOUR failures, not collection errors; the control tests are red too; green on the tip.
- Re-run the named gate files and the census files; check baseline bins against the Step 0 record in `tracer-approach.md`; check the hand-off carries measured minima, margins and re-measurements.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal; no raw NUL byte.
- Check nothing under `kitty-specs/` was written and no file outside the owned list changed without a recorded rationale.
- Verify the AST independence test, every floor against D-P13 and its re-measure, the offline classification (which cases skip and which run), and the measured runtime against NFR-001.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs W-1 (accept, local lane consolidation, registration and scope check over the real diff), W-2 (J-1 confirmation), W-3 (dev-assist cleanup), W-4 (issue-verdict evidence, aggregate adversarial squad, terminal #5776 verdict), W-5 (history compaction), W-6 (rebase onto upstream `main`) and W-7 (final evidence); then the draft pull request. You do none of this.

## Implementation command

`spec-kitty agent action implement WP09 --agent claude`
