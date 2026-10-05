---
work_package_id: WP08
title: 'Reality-check extension: floors, oracle, controls, fixture'
dependencies:
- WP05
- WP06
requirement_refs:
- FR-016
- FR-021
- FR-023
- NFR-001
- NFR-003
- NFR-004
- NFR-006
- C-004
- SC-003
- SC-004
- SC-005
- SC-006
planning_base_branch: issue-5625-mission-status-contract-1-1
merge_target_branch: issue-5625-mission-status-contract-1-1
branch_strategy: Planning artifacts for this mission were generated on issue-5625-mission-status-contract-1-1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5625-mission-status-contract-1-1 unless the human explicitly redirects the landing branch.
subtasks:
- T044
- T045
- T046
- T047
- T048
- T049
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- tests/contract/fixtures/mission_status_artifacts_expected.json
execution_mode: code_change
model: ''
owned_files:
- tests/contract/test_mission_status_reality.py
- tests/contract/_mission_status_payloads.py
- tests/contract/fixtures/mission_status_artifacts_expected.json
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP08 – Reality-check extension: floors, oracle, controls, fixture

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Turn the two corpus smokes into the full reality check: floors, independent counts, the independent byte-level oracle, controls, leak scans, the extended fingerprint and the pinned anomaly fixture.

## Context

Plan IC-08 and the Reality-check design notes; data model section Floors and the independent counts; contracts note section D (`kitty-specs/mission-status-contract-1-1-01M42XJC/contracts/tool-extension-and-reader.md`); research R-5 (floor rule and measurements). Depends on WP05 and WP06. It shares no file with WP07, so their order is the orchestrator's dispatch order; WP08 is dispatched before WP07 (recommended: it carries the runtime-budget risk NFR-001 / P-2, the independent oracle and the floor measurements, any of which can force a re-plan, so a budget overrun is found early; both orders are legal and no dependency is added). The `FLOORS` fields and their values are added here (T048), where they are consumed; WP05 does not add them. Budget (D-P5, NFR-001): the corpus job stays at or under 8 minutes, re-plan above 6 minutes; the only per-case worst case is the 1000 x 262,144-byte listing (6.2 s planned, 60 s limit); the first case still carries a 19.8 s setup. The 8-Mission ratchet header in the reality module must not be touched.

Decisions honoured (spec.md, Decisions and Traceability; read `kitty-specs/mission-status-contract-1-1-01M42XJC/spec.md` with this prompt; the rows are `tasks.md`, section Coverage): CL-2, CL-4; AD-6, AD-7, AD-12, AD-15, AD-17, AD-18, AD-19, AD-22; AC-LIST, AC-DETAIL, AC-CONTENT; OD-3.

Plan concern: IC-08 (plan section Implementation Concern Map). Requirement refs: FR-016, FR-021, FR-023, NFR-001, NFR-003, NFR-004, NFR-006, C-004, SC-003, SC-004, SC-005, SC-006. Dependencies: WP05, WP06. Branch contract: planning base and merge target are `issue-5625-mission-status-contract-1-1`; work runs in the lane workspace `spec-kitty agent action implement` resolves for you (never reconstruct a path by hand).

## Owned files (write scope)

Edit only these paths (declared shared-file exceptions are dependency chains, never concurrent; plan section Lanes):

- `tests/contract/test_mission_status_reality.py`
- `tests/contract/_mission_status_payloads.py`
- `tests/contract/fixtures/mission_status_artifacts_expected.json`

1 of these paths do not exist yet on the planning base and are declared in the frontmatter `create_intent` (finalisation refuses a literal path that matches zero files unless it is declared there); you create them.

Nothing under `kitty-specs/` is written by this work package: records you must make (a contract-note refinement, a decision, a friction observation, the baseline) go into your hand-off report; the orchestrator appends them add-only to the tracer files. A small, well-justified out-of-map edit is acceptable only with a one-line rationale in the hand-off report; the no-overlap rule is the real guard against collisions.

### Subtask T044: Red-first: the corpus-level tests for floors, independent counts and the pinned fixture

**Purpose**: First commit: failing corpus-level tests.

**Steps**:

1. Add to `test_mission_status_reality.py` the corpus assertions that fail until the pieces exist: the pinned fixture is read and its named entries are checked (the file does not exist yet), new floors are asserted, examined-equals-discovered with zero and shortfall guards.
2. Run against the planning base of this lane start: they fail. Commit.

**Files**: `tests/contract/test_mission_status_reality.py`.

**Validation**: Red recorded.

### Subtask T045: Independent counts and the byte-level oracle for the listing and the content read

**Purpose**: Independent counts and the byte-level oracle.

**Steps**:

1. Independent counts (not from the reader): Missions (a scan of `meta.json`), work package ids (a plain YAML read of the selected files), eligible files (a separate walk), owned-file entries, `tasks.md` rows, cycle files and pointer-equal events; each compared with the examined count (`examined == discovered`) before any numeric floor.
2. The oracle (D-P8): the reality module classifies every eligible file from its raw bytes alone (size over 262,144 gives 413; a NUL byte, then a strict UTF-8 decode failure, gives 415; a `SECRET_PATTERNS` match in the decoded text gives 422; else 200, in that order), derives the expected status and `readable`, and asserts both against the listing entry and against the content read. A wrong order, credential rule or NUL rule applied consistently in both reader places must fail it. `readable == (content read answers 200)` stays only as a labelled wiring guard.
3. Every new assertion states its examined and discovered counts in its failure text and fails when either is zero.

**Files**: `tests/contract/test_mission_status_reality.py` (about 300 lines).

**Validation**: Oracle and counts green on the real tree; planted wrong-order mutation of the reader makes the oracle fail (test applies it).

### Subtask T046: Detail corpus checks: distinct work package ids, v1 controls, duplicate ids pinned by name

**Purpose**: Detail corpus checks.

**Steps**:

1. Detail for every distinct work package id (the independent count of distinct ids, 3,193 at the plan fix; the four duplicate ids of one archived Mission pinned by name; ids present only in the status log counted separately and answered 404); empty skip list.
2. v1 controls: `subtasks[].id` equals `WorkPackage.authored.subtasks`, `dependencies[].wpId` and `ownedFiles[].pattern` compared with the v1 payload built from the SAME authored file; planted mismatch of each fails. Cycles: floors (cycle files, unparseable, verdict non-null by an independent scan, date-only at least 1). Every `changeState` is `unknown` and every `worktreePresent` is `false` (host `NO_WORKTREES`), examined equals the independent count.

**Files**: `tests/contract/test_mission_status_reality.py` (about 250 lines).

**Validation**: Green on the real tree; planted mismatches fail.

### Subtask T047: Controls on the shared fixture Mission, planted 422 coverage, extended wiring guard

**Purpose**: Controls on one shared fixture Mission and planted coverage.

**Steps**:

1. On one shared fixture Mission: a real payload validates; the same payload with a planted host path, e-mail address, credential, unknown lane, extra property or absolute pointer fails; extend the wiring guard (`_wiring_problems`) so a removed check turns every case red.
2. Planted 422 coverage: a fixture Mission built at run time (the corpus holds none); the extended-fingerprint control (a writing reader that only creates an empty directory) is the one planted in WP05 T024; reference it in a test of this work package that runs the same reader over the corpus fingerprint, and do not write a second planted control for the same property.

**Files**: `tests/contract/test_mission_status_reality.py` (about 200 lines).

**Validation**: Controls fail when planted and pass when clean.

### Subtask T048: The pinned anomaly fixture, floor values, fingerprint control and leak scans

**Purpose**: The pinned anomaly fixture, floor values and leak scans.

**Steps**:

1. New `tests/contract/fixtures/mission_status_artifacts_expected.json` (beside `mission_status_expected.json`; authored, no generated values) lists by name the two 413 files, the two not-UTF-8 files, the three NUL files with their codes, the work package with no prompt file and the Mission with duplicate work package ids; a subset check: each named entry must still be present and behave as stated, an unnamed new anomaly is printed, never a failure.
2. `FLOORS` in `_mission_status_payloads.py`: add the new fields (names and values) here, where the reality check consumes them: measure on the merged tree and pin each below the measurement by the research R-5 rule (95 percent rounded down to two significant figures; counts under 100 at 90 percent); the existing three floors (500, 3,000, 2,800) stay. Field names and starting values: contracts note section D.
3. Leak scans over every corpus-built payload `content` and string field: zero host paths, addresses and credentials; the artifact-path class applies.

**Files**: `tests/contract/fixtures/mission_status_artifacts_expected.json` (new), `tests/contract/_mission_status_payloads.py` (`FLOORS` fields and values), `tests/contract/test_mission_status_reality.py`.

**Validation**: Fixture present and subset check green; floors below the fresh measurement.

### Subtask T049: Runtime budget measurement and the final gate runs

**Purpose**: Runtime budget and final gates.

**Steps**:

1. Measure the reality module locally (`--durations=10`) and record: total and slowest cases; report the figure against the 8-minute limit and the 6-minute re-plan trigger (CI measurement happens on the PR).
2. Run the targeted tests, the named architectural-fast and layer-rules files, ruff and TID251; check the new fixture and edited files for raw NUL bytes.

**Files**: None.

**Validation**: Hand-off report carries the timings and every command with counts.

## Validation: gates and targeted test surface

Charter: no full `tests/architectural/`, end-to-end, performance or `make test-full` sweep in mission work (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run exactly the commands below, record each command and its passed/failed counts in the hand-off report. Use the checkout's own environment (`.venv/bin/...`), never a bare `uv run`. `<scratch>` means a scratch directory outside the repository.

**Targeted test surface of this work package**:

- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider --durations=10 -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py tests/contract/test_mission_status_payloads.py`
- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_artifacts.py tests/contract/test_mission_status_detail.py`

**Tool-job selection (the whole `tests/contract` corpus selection; the router job `tests (contract tools)`, step `Run the contract tool unit tests` of `.github/workflows/ci-router.yml`).** This is the job that runs the new test modules and every neighbour of the contract files this Mission changes, so it is part of the targeted surface (a directory-scoped contract run, not an architectural sweep). Verbatim from the workflow (CI-owned form):

```text
uv run --frozen --no-sync pytest -m "corpus and not windows_ci" tests/contract \
  --ignore=tests/contract/test_example_round_trip.py \
  --ignore=tests/contract/test_mission_status_payloads.py \
  --ignore=tests/contract/test_mission_status_reality.py \
  -n 4 --dist loadfile
```

Runnable as written here (the checkout's interpreter, no `uv run`; the same arguments):

```text
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -m "corpus and not windows_ci" tests/contract \
  --ignore=tests/contract/test_example_round_trip.py \
  --ignore=tests/contract/test_mission_status_payloads.py \
  --ignore=tests/contract/test_mission_status_reality.py \
  -n 4 --dist loadfile -q
```

Record the passed and skipped counts in the hand-off report and compare them with the Mission baseline (1,016 passed and 37 skipped at the plan fix; the WP01 T001 table in `tracer-approach.md` is the authoritative comparison, and the counts rise by the tests this Mission adds).

**Gates every code work package passes before hand-off** (baselines at the plan fix: 368 passed and 1 skipped; 171 passed; 83 passed; ruff clean; TID251 clean):

1. Router, registry and hygiene gate files, ruff and cutover guard:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py tests/ci/test_corpus_blocking_home.py \
  tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_same_tier_uniqueness.py \
  tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_workflow_coherence.py tests/architectural/test_no_legacy_terminology.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/spec-kitty cutover-guard --base-ref origin/main
```

2. Architectural files that census `tests/` (real-git fixtures, worktrees, git identity setup, `os.chdir`/`os.environ`/`sys.path` changes in a new test module are what they inspect; no allowlist or baseline entry may be added to make a module pass: use `monkeypatch` and a scratch HOME). Run after every new or edited test module:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/architectural/test_no_manual_global_state_mutation.py tests/architectural/test_global_state_allowlist_sealed.py \
  tests/architectural/test_spec_kitty_home_pin_census.py tests/architectural/test_spec_kitty_home_pin_guard.py \
  tests/architectural/test_spec_kitty_home_pin_budget.py tests/architectural/test_home_pin_gate_verdict.py \
  tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py
```

3. Layer rules and import boundaries:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/architectural/test_layer_rules.py tests/architectural/test_pyproject_shape.py
.venv/bin/ruff check --select TID251 .
```

4. Per-file format check where useful: `.venv/bin/ruff format --check --force-exclude <files>`.

## Red-first rule (C-011, charter ATDD-First Discipline)

The FIRST commit of this work package is its failing test or planted fixture, red on the planning base (the lane's base before your first commit), committed BEFORE any implementation commit. Verify the red and record the failing test ids and the reason in the hand-off report: run the test file against the base by extracting the base into a scratch directory (`git archive <base-commit> | tar -x -C <scratch>/base`, copy the new test file in, run pytest from that directory with the checkout's interpreter); do not use `git stash`. The reviewer verifies red then green: red on the planning base AND green on the final commit. Declared exceptions are named in the subtasks (the behaviour-preserving campsite commit, the three regression-control leak kinds, the old-kind digest test). Never weaken, skip or retry-to-green a test to pass.

## Baseline rule: pre-existing red versus introduced red

Before your first change, run this work package's targeted commands once on the unchanged lane base. Any red is binned before work continues: (1) pre-existing known-P0 red on `main` (leave it red, never green-wash), (2) CI-environment failure (auth, opt-out variables; passes locally), (3) stale install, (4) stale venv (re-run `uv sync --frozen --all-extras`, then retry), or (5) introduced by you. Only a red that is red on your branch AND green on the base is yours to fix. A pre-existing red: STOP and report to the orchestrator in your hand-off (command, failure summary, why you believe it is pre-existing); the orchestrator owns the tracker issue (Pre-existing Failure Reporting Rule). Do not open an issue or post a comment yourself, do not absorb it, do not retry until green.

**Comparison base.** The Mission baseline is the planning-base commit and the counts recorded by WP01 T001, appended add-only to `tracer-approach.md` by the orchestrator. Your lane base already holds the commits of earlier work packages, so "green on the base" alone does not make a red pre-existing. Reconcile your own pre-change run with the WP01 table for the same command and explain any difference. A red that is red on your lane base but green at the Mission baseline was introduced by an earlier work package of this Mission: report it with the work package it belongs to; do not bin it as pre-existing (bin 1).

## Git, commits and public-repo hygiene

- **Commit locally. NEVER push, never open a pull request, never comment on an issue, never merge.** One pull request per Mission is opened by the orchestrator after the wrap-up sequence.
- Conventional commit subjects ending with `(#5625)`; end each commit message with the attribution trailers the orchestrator supplies. Commit through `spec-kitty safe-commit` where a guarded branch requires it; never bypass a guard with raw git or an environment override.
- **This repository is PUBLIC**: everything you write ships visibly and permanently. No absolute path under a home directory and no drive path, no user name, no e-mail address, no private reference, no credential in any file, test, fixture, commit message or report. Use repo-relative paths and placeholders such as `<repo>`, `<scratch>`, `<user>`. A username-leak is folded before anything leaves the machine; report any you find.
- Leaking values a test needs (host paths, addresses, tokens, an at-sign file name) are assembled from fragments at run time and never typed as literals. Editing tools decode a unicode escape typed into a file into the raw character: write NUL as `chr(0)` and backslash as `chr(92)` in tests, use the hex escape in contract patterns, and check every new file for raw NUL bytes.
- Terminology: Mission, never feature; say which sense of lane (status lane versus code lane); no `--feature` flag text. New code passes `ruff check` and `ruff format --check` with no suppression added; complexity ceiling 15; literals used three or more times in a module become constants.
- `kitty-specs/` is archive-frozen on `main`: this Mission's own files are add-only on the branch. Never hand-edit `meta.json`, `status.events.jsonl`, `lanes.json` or work package frontmatter; never call `materialize`. Never run a pattern kill (`pkill`/`killall`), `git stash`, or `rm` with a variable glob.
- **Subagents dispatch nothing**: you work alone; do not start, fork or brief other agents. A denied command means STOP and report it; never retry a denied command.

## Hand-off report (your final message)

Commits (hash and subject, in order, first commit marked as the red-first commit), the red evidence (failing ids, reason, how it was verified on the base), every command run with passed/failed counts, baseline bins, any refinement of a contract note or design decision, any friction observation (for `tracer-tooling-friction.md`), anything not done and why. The orchestrator records decisions and friction add-only; you do not write them under `kitty-specs/`.

## Definition of Done

- First commit: failing corpus tests (T044), red on the planning base.
- Independent counts compared before floors; oracle independent of the reader and catches a consistently wrong decision order.
- All controls fire when planted; pinned fixture with subset check; floors re-measured and pinned by the rule.
- Fingerprint (bytes and directory names) equal before and after; no `materialize` call; ratchet header untouched.
- Timings recorded; gate files green; ruff and TID251 clean.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- Runtime growth: re-plan above 6 minutes locally-extrapolated CI time; never raise a floor above its measurement.
- Counts drift with this Mission's own files (friction F-14): pin from a fresh measurement on the consolidated tree, not from the plan text.
- A fixture Mission built at run time must obey the global-state scans.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface (every file the change touches), plus the specific named architectural gate files it implicates; never a full sweep.

- Verify red then green for T044; verify the oracle is not the reader's own function by planting a consistently wrong decision order.
- Check floors against a fresh measurement and the stated rule; check the named anomalies exist.
- Check the added test time against the budget.
- Verify the first commit is the red-first commit and that it is red on the planning base; verify green on the final commit; check the baseline bins in the hand-off.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs plan steps W-1 to W-7 in this order: W-1 accept, then lane consolidation (`spec-kitty consolidate`, strategy `rebase` recommended), then registration and wiring check, scripted scope check and issue-matrix rows; W-2 JVM shake-out; W-3 dev-assist cleanup; W-4 aggregate adversarial squad (report-only, pre-rebase tree); W-5 history compaction; W-6 rebase onto upstream including the 1.0.0 release commit; W-7 final evidence. Only then is the draft pull request opened, and it needs the `contract-mission-status-v1.0.0` tag. Evidence recorded earlier is labelled pre-tag or pre-rebase. You do none of this.

## Implementation command

`spec-kitty agent action implement WP08 --agent claude`
