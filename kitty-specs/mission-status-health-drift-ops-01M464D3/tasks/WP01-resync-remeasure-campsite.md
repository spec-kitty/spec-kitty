---
work_package_id: WP01
title: Re-measurement and campsite (tidy-first)
dependencies: []
requirement_refs:
- FR-012
- FR-013
- FR-015
- NFR-001
- NFR-002
- NFR-006
- NFR-009
- SC-003
planning_base_branch: issue-5776-mission-status-contract-health-drift-ops
merge_target_branch: issue-5776-mission-status-contract-health-drift-ops
branch_strategy: Planning artifacts for this mission were generated on issue-5776-mission-status-contract-health-drift-ops. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5776-mission-status-contract-health-drift-ops unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-health-drift-ops-01M464D3
base_commit: 316d938483de48d78b2507f447a7614c3a7672c8
created_at: '2026-10-06T10:23:39.395885+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/contract/test_mission_status_contract_1_1.py
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP01 - Re-measurement and campsite (tidy-first)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Start from the orchestrator's Step 0 record, re-measure as the first task the kind-3 counts under the final rule and the other numbers the spec marks as moving, and land the one distinct behaviour-preserving opening campsite commit in the 1.1 proof module (or record that none is owed).

## Context

This WP is the tidy-first opening of the Mission. The D-0 sync, the synced environment and the baseline are NOT this WP: they are the orchestrator's Step 0, recorded in `tracer-approach.md` before any dispatch. This WP only reads that record, never takes it. It runs beside WP02 (the one parallel window; they share no file). The proof module it edits is edited again by WP03 and WP06, so this WP finishes first. Everything it measures is scratch (a script built from public product readers, never committed) and goes into the hand-off; the orchestrator appends it to the tracer files.

Plan concern: IC-01 of `kitty-specs/mission-status-health-drift-ops-01M464D3/plan.md`. Read, in this order, before writing anything: `.kittify/charter/charter.md`, `AGENTS.md` (for conventions only), the Mission's `spec.md` (the requirement ids in the frontmatter), `plan.md` sections named below, `research.md`, `data-model.md`, `quickstart.md` and `contracts/*.md` in `kitty-specs/mission-status-health-drift-ops-01M464D3/`.

**Dependencies and order.** No dependency (the orchestrator's Step 0 record is the only prerequisite and it exists before dispatch). No work package is dispatched before the orchestrator's Step 0 record exists in `tracer-approach.md`. **Pre-dispatch (orchestrator Step PD in `tasks.md`, operator ruling 13):** before this dispatch the orchestrator fast-forwards the mission-lane branch `kitty/mission-<slug>` and, once the orchestrator's run of `spec-kitty agent action implement WP01 --agent claude` (the command of your Implementation command section; it creates or resumes the lane workspace) has created this lane workspace and before you are started, merges the planning branch into it and greps inside it for every record this prompt reads: the Step 0 record (heading `## Record: Step 0` in `tracer-approach.md`; no earlier hand-off is read); read them from the lane workspace root. If a line the prompt tells you to read is not there, stop and report it; never run `--refresh-planning-commit` and never copy a record in by hand.

## Owned files (write scope; final, explicit, no directory-wide glob)

- `tests/contract/test_mission_status_contract_1_1.py`

No file under `kitty-specs/` is in this write scope: record what you learn in the hand-off; the orchestrator appends it to the tracer files. An out-of-map edit is acceptable only when small, well-justified and recorded with a one-line rationale in the hand-off. Shared files in this list are declared chokepoints serialised by the dependency chain (plan 'Declared shared-file exceptions'); edit only your own entries in them.

## Implementation concern (plan section IC-01, verbatim)

- **Purpose**: Start from the orchestrator's Step 0 record (the D-0 sync, the synced environment and the baseline are **not** IC-01's; plan-round ruling 3), **re-measure, as its first task, the kind-3 counts under the final rule** and the other numbers the spec marks as moving, and land the opening campsite commit (or record "none").
- **Relevant requirements**: spec "Re-measurement owed", FR-012 evidence note, FR-013 (Gate B and the no-op re-check), FR-015 (fallback derivation agreement and the corpus condition), NFR-001, NFR-002, NFR-009 (measurements), A-2, Standing Order 2.
- **Steps, in order**: (1) re-measure kind 3 with a scratch script built from public product readers (never committed): Missions not completed, with a current-shaped manifest, with an expected lane, with a missing expected branch, by lifecycle state and by topology (coordination branch versus `mission_branch`), the legacy count; record the result and **pin no corpus floor**; (2) re-check Gate B (no `.kittify/derived/` in the corpus, gitignored, untracked) and that `validate_derived_views` is still a no-op returning an empty list; if either changed, the decision of FR-013 returns to the squad; (3) re-count the corpus facts of research R-2 and the fallback agreement and corpus condition of R-3; (4) time the resolver-included Project proxy, the scan, the real-directory listing repeated at least 5 times, and the AC-DRIFT row 19 completion equality over the real corpus (about 518 own directories), each measured and not estimated, with the remotes reachable, and record the sum (the proxy of D-P5's single bounded case included; the escalation line is about 70 s local, that is 120 s divided by the 1.7 factor, against the sum of the combined case and the 10 to 15 s of completion equality and listing repeats, so about 55 s local for the combined case alone; above it goes to the operator before the bound is set, plan-round rulings 8 and 11; the W-7 pass rule stays the final arbiter); (5) the campsite commit.
- **Affected surfaces**: `tests/contract/test_mission_status_contract_1_1.py` (campsite only). Everything else is scratch and reported to the orchestrator, which appends it to `tracer-approach.md` (Record-keeping).
- **Write scope**: that one file. **Sequencing**: depends only on the orchestrator's Step 0 record; the one parallel window of the Mission is IC-01 beside IC-02 and it stays.
- **Acceptance (named)**: the recorded kind-3 result; the Step 0 record cited and any red met binned against it; the campsite counts identical before and after.
- **Risks**: P-4 (the corpus condition of R-3 must hold), P-5 (kind-3 honesty), P-6 (a moving upstream), P-2 (the blind gates).

## Design decisions that bind this work package (plan, verbatim)

**D-P6 Kind 3 is provisional and honest-rule gated, not floored (FR-012, R-1).** The reader implements the rule exactly as written (completion first; three-way `lanes.json` classification for a non-completed Mission; expected lane and expected Mission-level branch; one local-ref listing, once; one finding per Mission, no branch name). The oracle shares the product's `is_mission_completed` and `materialize_snapshot` for a Mission whose read directory is its own directory and reads the two arms directly otherwise (COMPLETE-012), reads `meta.json` and the manifest as raw JSON, and tests each expected name with its own `git rev-parse --verify --quiet`. **No corpus floor and no assertion rests on the old 93**: the corpus is asserted equal to the oracle, and the synthetic fixtures carry the named plants (a merged marker, an all-terminal Mission, a reopened Mission, an expected and a planned-only lane, the coordination pair). IC-01's first task re-measures the counts under the final rule (research R-3); if the finding population is dominated by a class the oracle shares with the reader by construction, the honest-rule criterion cannot be met and the point goes to the operator, not to a self-ruled change.

**D-P13 Floors (FR-025, spec D-P15; the completion-equality floor is added by plan-round ruling 4).** Fixed here, never re-pinned, below the plan-time measurement by one stated rule (95 percent rounded down to two significant figures; counts under 100 at 90 percent rounded down; named anomaly classes by a subset check): Missions examined 540 (of 569); Ops served 440 (of 473); spine-closed Ops 5 (of 6); evidence of each kind own-file: none 330, absolute path 28, free text 50, relative reference 25, `url` 0 (fixture-only floors: `url`, a redacted address, a withheld credential); kind-1 findings 39 (of 44: 43 terminal, 1 provenance, 0 plain), kind-2 findings 27 (of 31); completion-equality guard of AC-DRIFT 19: Missions declaring no coordination branch compared 490 (of 518, which is 569 less the 51 declaring one; 95 percent rounded down to two significant figures); **no kind-3 floor** and no fallback floor. IC-01 verifies each floor sits below the re-measure; a floor above a re-measure is an escalation, not a re-pin. A floor loosened to one fails (a test), and `floor_failures` keeps the v1 shape.

**D-P5 Placement; no new job.** The reality extension stays in `test_mission_status_reality.py` (router job `tests (corpus-blocking)`, serial, 10-minute timeout); the three new reader modules and the proof edits run in `tests (contract tools)` (selected automatically: the job takes the directory minus three `--ignore` modules). **Corpus-reading cases live in the reality module only (plan-round ruling 4):** AC-DRIFT row 19's equality with `is_mission_completed` over the real corpus, and the corpus-sized cases of AC-CROSS 4 (the real `kitty-ops/` listing at most 5 s; one `Project` build and one project-wide scan at most 120 s each), run there with a discovered-count guard (D-P13); `docs/development/reference/ci-gate-mechanics.md` documents the tool job as reading no corpus, and its budget carries no measured corpus time. The three new modules are **fixture-built only** (a temporary repository per case, each plant with its control); no docs edit is needed. **Budget (NFR-001 is a gain bound):** the plan-time local figure of the unchanged corpus job is 108 s and its CI duration about 3 minutes (a remembered figure of the previous slice, not a baseline), a local-to-CI factor of about 1.7. The added work is the second, memoised resolver pass (the v1 pass stays; about 37 s local), the scan's remaining reduction (about 3 to 15 s local) and the Project reduction (about 7 s local): about 45 to 60 s local before the items priced below (about 75 to 100 s in CI by that factor, a derived estimate, not a measure). **Execution sharing (NFR-001 stays honest):** the Project-build bound, the scan bound and the combined case are ONE execution: the combined case builds the `Project` and runs the memoised pass and the per-Mission reductions once and records each duration, and the two separately named bounds assert on those same measured durations (no second Project build, no second scan, so no scan-reduction or Project-reduction time is added twice). The other added work is priced separately, in local seconds: the AC-DRIFT 19 completion equality reads about 518 own directories (an estimate of about 5 to 10 s local, measured by the IC-01 proxy), and the real-directory listing is repeated at least 5 times at its expected cost of well under 1 s each, about 5 s local in all (the 5 s bound is an assertion that a failing run would trip, not a budget input, so a 25 s worst case is not priced). The job-gain-only items therefore total about 10 to 15 s local, and the local estimate is the 45 to 60 s base plus those 10 to 15 s, about 55 to 75 s, which is about 94 to 128 s in CI at the 1.7 factor (a derived estimate, not a measure). The top of that range exceeds the 120 s gain bound and the bottom is not safely inside it, so the arithmetic does not prove the bound; the IC-01 proxy and the W-7 pass rule govern. The control is not this arithmetic: IC-01 measures the proxy first, the first PR run is judged against the recorded baseline, and the 6-minute re-plan threshold below stays the explicit limit. Offline the Project, scan and combined cases are skipped and cost nothing. **Baseline:** the orchestrator's Step 0 records the median duration of the last five successful `main` runs of both `tests (corpus-blocking)` and `tests (contract tools)` (Baseline section). **Pass rule at W-7:** the first PR run's `tests (corpus-blocking)` duration minus the recorded median is at most 120 s, and `tests (contract tools)` stays under its 15-minute timeout with the margin recorded; re-plan if the first run shows more than 6 minutes of corpus job time (about 3 minutes baseline plus the 2 minute bound is 5 minutes; 6 leaves one minute of runner noise). **In-test:** no case over 120 s, and one case in `test_mission_status_reality.py` times the memoised pass, the Project build and the per-Mission reductions together, so the in-test bound and the job gain are different quantities: the combined case is the largest component of the gain, not the whole (the v1 pass is not part of either; the AC-DRIFT 19 completion equality and the repeated real-directory listing sit in the job gain only, about 10 to 15 s local, 17 to 25 s in CI, the same figure as above), and a combined case passing under 120 s does not imply the job gain is; the W-7 pass rule above is the arbiter of the job gain (plan-round ruling 10). IC-01 measures the proxy first, and a local proxy of the job gain above about 70 s (the 120 s bound divided by the 1.7 local-to-CI factor, stated in local seconds) goes to the operator before the bound is set (research R-12; plan-round rulings 8 and 11). The 70 s line is stated against the SUM: the combined case plus the 10 to 15 s of completion equality and listing repeats, so the combined case alone escalates at about 55 s local (70 s minus the upper 15 s); the W-7 pass rule stays the final arbiter. **Markers:** the drift and project modules build real git repositories and the resolver starts git, so they carry `contract`, `corpus` and `git_repo` and **not `fast`** (as the detail module of the previous slice); the ops module carries `contract` and `corpus` and not `fast` (it holds the timed 10,000-file and 256 KiB cases, which are not sub-second); **every new module declares a module-level `pytestmark`** (the class of defect of an unmarked corpus reader that is silently never run), **written as one single-line list that holds `pytest.mark.corpus` on the same physical line as `pytestmark =`**, in the form of `tests/contract/test_mission_status_detail.py` (`pytestmark = [pytest.mark.contract, pytest.mark.corpus, pytest.mark.git_repo]`): `_CORPUS_MARK_APPLICATION_RE` of `tests/architectural/test_ci_corpus_trigger_completeness.py` matches `pytestmark\s*=.*\bpytest\.mark\.corpus\b` within one line, so a mark spelled through a shared list or wrapped across lines escapes the registry gate (the registry row is then reported as in the registry but no longer marked) while the home gate, which collects for real, still sees it. The registry row and the `--deselect` go in the commit that creates the module, in sorted position. The advisory packs corpus suite must not gain these tests: each new module is deselected there (PD-2).

## Campsite-clean (plan section g, verbatim)

**Opening commit (distinct, behaviour-preserving, tidy-first):** `refactor(tests): name the repeated scope-data literals of the 1.1 proof module once (#5776)`.

- **Surface and debt (counted, not from a Sonar report).** `tests/contract/test_mission_status_contract_1_1.py` (1,073 lines) holds 15 string literals of twelve characters or more used three or more times (the Sonar `S1192` class), among them `"openapi.yaml"` (7 uses), `"byte_identity: "` (5), `"leak_patterns"` (5), `"out_of_scope: "` (4), `"contracts/tools/leak_scan.py"` (4) and `".github/workflows/packs.yml"` (4). FR-029 rewrites exactly this file's scope data (`SLICE_ALLOWED`, `EXTRA_ALLOWED_REGISTRATIONS`, `IN_SCOPE_CHANGES`, `REGISTRATION_CHANGES`, `NEW_PATH_KEYS`, `CHANGED_ALLOWED`), so the duplicates are domain-matched debt in the file about to change.
- **Change.** Hoist the repeated literals that sit in the scope, pair and proof-message data into named module constants, and replace their uses. Nothing else is tidied.
- **Behaviour-preserving proof.** The same test ids pass before and after with identical counts (the module's own count is recorded at IC-01); every assertion is unchanged.
- **Write scope.** That one test file; the re-measurements and the baseline are reported to the orchestrator, which appends them to the tracer files.
- **Drop rule.** After the D-0 sync the literals are re-counted; below three uses each, the opening commit is **none**, and the PR body and the tracer say "no domain-matched debt found in the edit surface".
- **Not a grab-bag.** The 1,365-line payload helper and the 2,099-line reality module are not split here (the new builders live in new modules); no `src/` debt is folded (NFR-007).

### Subtask T001: Re-measure kind 3 under the final rule

**Purpose**: Count, with a scratch script built from public product readers (never committed): Missions not completed, with a current-shaped manifest, with an expected lane, with a missing expected branch, by lifecycle state and by topology (coordination branch versus `mission_branch`), and the legacy-shaped count. Pin NO corpus floor.

**Steps**:
1. Read the Step 0 record first; cite its recorded `HEAD` and bins.
2. Build the scratch script outside the repository (`<scratch>`), run it read-only (never call `materialize`, never write under `kitty-specs/` or `kitty-ops/`).
3. Report the table in the hand-off. If the finding population is dominated by a class the oracle shares with the reader by construction, the honest-rule criterion (D-P6) cannot be met: STOP and report, the point goes to the operator.

**Files**: none committed (scratch only)

**Validation**: The table is in the hand-off with the command used.

### Subtask T002: Re-check Gate B and the no-op

**Purpose**: Confirm that no `.kittify/derived/` exists in the corpus (gitignored, untracked) and that `validate_derived_views` is still a no-op returning an empty list. If either changed, the decision of FR-013 (the fourth kind is not shipped) returns to the squad: STOP and report.

**Steps**:
1. `git ls-files` and `git check-ignore -v` on `.kittify/derived/`.
2. Read `validate_derived_views` in `src/` (read-only) and run it against an empty fixture directory in a scratch script.

**Files**: none committed

**Validation**: Both results in the hand-off.

### Subtask T003: Re-count the corpus facts and check every floor

**Purpose**: Re-count the facts of research R-2 and the fallback agreement and corpus condition of R-3 (P-4: the corpus condition must hold). Verify that each floor of D-P13 sits BELOW its re-measure (Missions 540, Ops served 440, spine-closed 5, evidence none 330 / absolute path 28 / free text 50 / relative reference 25, kind-1 findings 39, kind-2 findings 27, completion-equality 490).

**Steps**:
1. Use the count commands of `quickstart.md` section 'Counts of the corpus' (read-only).
2. A floor above its re-measure is an ESCALATION to the operator, not a re-pin: report it, never change a floor.

**Files**: none committed

**Validation**: A table of floor versus re-measure in the hand-off.

### Subtask T004: Time the proxies

**Purpose**: Time, measured and not estimated, with the remotes reachable: the resolver-included Project proxy, the scan, the real-directory listing repeated at least 5 times, and the AC-DRIFT row 19 completion equality over the real corpus (about 518 own directories). Record the sum, including the proxy of D-P5's single bounded case.

**Steps**:
1. The escalation line is about 70 s local (120 s divided by the 1.7 CI factor) against the sum of the combined case and the 10 to 15 s of completion equality and listing repeats, so about 55 s local for the combined case alone; above it the matter goes to the operator before any bound is set (plan-round rulings 8 and 11). The W-7 pass rule stays the final arbiter.
2. Report each timing with its repeat count and the minimum.

**Files**: none committed

**Validation**: Timings and the comparison with the escalation line are in the hand-off.

### Subtask T005: Campsite commit (or record none)

**Purpose**: In `tests/contract/test_mission_status_contract_1_1.py` name the repeated scope-data literals once. After the D-0 sync re-count the literals first: below three uses each, the commit is NONE and the hand-off says 'no domain-matched debt found in the edit surface'.

**Steps**:
1. Commit subject: `refactor(tests): name the repeated scope-data literals of the 1.1 proof module once (#5776)`.
2. Hoist only literals of twelve characters or more used three or more times that sit in the scope, pair and proof-message data (plan-time: `"openapi.yaml"` x7, `"byte_identity: "` x5, `"leak_patterns"` x5, `"out_of_scope: "` x4, `"contracts/tools/leak_scan.py"` x4, `".github/workflows/packs.yml"` x4). Nothing else is tidied; no other file is edited. Note: in the checkout `"byte_identity: "` and `"out_of_scope: "` occur only inside f-strings (for example `f"byte_identity: {relative} differs from the baseline"`), not as stand-alone literals, so the recount rule above will probably drop them; hoist only what the recount confirms.
3. Record the module's test count and ids before and after: identical ids, identical counts, every assertion unchanged.

**Files**: tests/contract/test_mission_status_contract_1_1.py (edit, constants only)

**Validation**: The same test ids pass before and after with identical counts.

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

Run after every rebase and before hand-off:

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

## Red-first rule (declared exception)

This work package is the declared exception of C-011 (a measurement plus a behaviour-preserving campsite): there is no red test to write. The campsite commit must keep every assertion unchanged and the test ids and counts identical before and after; the reviewer compares the two runs. Never weaken, skip or retry-to-green a test.

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

## Hand-off report (your final message)

Commits (hash and subject in order, the first marked as the red-first commit); the red evidence (failing test ids, why they are behaviour failures, that the controls are red, how it was verified on the base); every command run with passed/failed/skipped counts and exit codes; baseline bins against the Step 0 record; **measured minima, margins and re-measurements** (every timed bound: the minimum of the repeats and the margin below the bound; every re-measured count; every floor against its re-measure); any refinement of a contract note or design decision; any friction observation (tooling hazards met); anything not done and why. **Code work packages never write under `kitty-specs/`**: the orchestrator appends decisions, measurements and friction add-only to `tracer-approach.md`, `tracer-design-decisions.md` and `tracer-tooling-friction.md` between dispatches.

## Definition of Done

- The recorded kind-3 result (no corpus floor pinned).
- The Step 0 record cited and any red met binned against it.
- The campsite counts identical before and after (or 'none' recorded with the re-count).
- The named census files run green after the edit (against the Step 0 baseline).
- Named gate files and census files green or binned against the Step 0 record; ruff check, ruff format --check and TID251 clean with no suppression added.
- Hand-off carries measured minima, margins and re-measurements; nothing written under `kitty-specs/`.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- P-4: the corpus condition of R-3 must hold; P-5: kind-3 honesty; P-6: a moving upstream; P-2: the registration gates are blind in the hand-built `.venv`, so run them in the synced environment the orchestrator recorded.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface, plus the named gate files and census files above; never a full sweep.
- Re-run the named gate files and the census files; check baseline bins against the Step 0 record in `tracer-approach.md`; check the hand-off carries measured minima, margins and re-measurements.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal; no raw NUL byte.
- Check nothing under `kitty-specs/` was written and no file outside the owned list changed without a recorded rationale.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs W-1 (accept, local lane consolidation, registration and scope check over the real diff), W-2 (J-1 confirmation), W-3 (dev-assist cleanup), W-4 (issue-verdict evidence, aggregate adversarial squad, terminal #5776 verdict), W-5 (history compaction), W-6 (rebase onto upstream `main`) and W-7 (final evidence); then the draft pull request. You do none of this.

## Implementation command

`spec-kitty agent action implement WP01 --agent claude`
