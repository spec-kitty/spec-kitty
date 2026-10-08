---
work_package_id: WP02
title: 'Tool extension: six strict names and plants (FR-027)'
dependencies: []
requirement_refs:
- FR-027
- NFR-004
- NFR-006
- C-003
- SC-005
planning_base_branch: issue-5776-mission-status-contract-health-drift-ops
merge_target_branch: issue-5776-mission-status-contract-health-drift-ops
branch_strategy: Planning artifacts for this mission were generated on issue-5776-mission-status-contract-health-drift-ops. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5776-mission-status-contract-health-drift-ops unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-health-drift-ops-01M464D3
base_commit: 316d938483de48d78b2507f447a7614c3a7672c8
created_at: '2026-10-06T10:23:41.629934+00:00'
subtasks:
- T006
- T007
- T008
- T009
history: []
agent_profile: python-pedro
authoritative_surface: contracts/tools/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- contracts/tools/fixture_builder.py
- contracts/tools/negative_cases.json
- tests/contract/test_fixture_builder.py
- tests/contract/test_leak_scan.py
- tests/contract/test_run_negative_cases.py
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP02 - Tool extension: six strict names and plants (FR-027)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Give the six new strict property names (`specKittyVersion`, `currentBranch`, `profileId`, `action`, `invocationId`, `sourceCode`) their leak class and their planted-violation cases, so the scanner meets every later file with the new classes in force.

## Context

The strict class is where a leading-tilde or bare absolute path is a host path. `STRICT_FIELDS` lives in `fixture_builder.py` and the scanner derives from it (plan PQ-4: `leak_scan.py` changes only if a red-first plant proves the scanner blind, and it is NOT in this WP's write scope; if a plant proves it blind, STOP and report: that is a scope decision for the orchestrator). Runs beside WP01 (no shared file). `negative_cases.json` and `fixture_builder.py` have this one writer. `enum_pins.json` is written by WP03 to WP05, not here.

Plan concern: IC-02 of `kitty-specs/mission-status-health-drift-ops-01M464D3/plan.md`. Read, in this order, before writing anything: `.kittify/charter/charter.md`, `AGENTS.md` (for conventions only), the Mission's `spec.md` (the requirement ids in the frontmatter), `plan.md` sections named below, `research.md`, `data-model.md`, `quickstart.md` and `contracts/*.md` in `kitty-specs/mission-status-health-drift-ops-01M464D3/`.

**Dependencies and order.** No dependency (the orchestrator's Step 0 record is the only prerequisite and it exists before dispatch). No work package is dispatched before the orchestrator's Step 0 record exists in `tracer-approach.md`. **Pre-dispatch (orchestrator Step PD in `tasks.md`, operator ruling 13):** before this dispatch the orchestrator fast-forwards the mission-lane branch `kitty/mission-<slug>` and, once the orchestrator's run of `spec-kitty agent action implement WP02 --agent claude` (the command of your Implementation command section; it creates or resumes the lane workspace) has created this lane workspace and before you are started, merges the planning branch into it and greps inside it for every record this prompt reads: the Step 0 record (heading `## Record: Step 0` in `tracer-approach.md`; no earlier hand-off is read); read them from the lane workspace root. If a line the prompt tells you to read is not there, stop and report it; never run `--refresh-planning-commit` and never copy a record in by hand.

## Owned files (write scope; final, explicit, no directory-wide glob)

- `contracts/tools/fixture_builder.py`
- `contracts/tools/negative_cases.json`
- `tests/contract/test_fixture_builder.py`
- `tests/contract/test_leak_scan.py`
- `tests/contract/test_run_negative_cases.py`

No file under `kitty-specs/` is in this write scope: record what you learn in the hand-off; the orchestrator appends it to the tracer files. An out-of-map edit is acceptable only when small, well-justified and recorded with a one-line rationale in the hand-off. Shared files in this list are declared chokepoints serialised by the dependency chain (plan 'Declared shared-file exceptions'); edit only your own entries in them.

## Implementation concern (plan section IC-02, verbatim)

- **Purpose**: Give the new strict properties their leak class and plants.
- **Relevant requirements**: FR-027, NFR-004, C-003.
- **Affected surfaces**: `contracts/tools/fixture_builder.py` (`STRICT_FIELDS` and the strict-name plants through the `_NEW_STRICT_NAMES` pattern: six names, six new kinds), `contracts/tools/negative_cases.json` (six cases), `tests/contract/test_fixture_builder.py` (the module constant `NEW_STRICT_NAMES`, which gains the six names, and the exact `KINDS` set whose size assertion `len(builder.KINDS) == len(expected) == 34` moves to 40; the eight old kinds still build byte-identically), `tests/contract/test_leak_scan.py` (the module constant `STRICT_NAMES`, which gains the six names and feeds `ALL_KINDS`; each of the six is in `STRICT_FIELDS`; a planted `profileId` example holding a bare absolute path fails the scan, its clean control passes), `tests/contract/test_run_negative_cases.py` (the `strict` name set hard-coded inside `test_the_manifest_holds_one_leak_scan_case_per_planted_kind_with_its_code`, which gains the six names). The three hard-coded strict-name lists are `STRICT_NAMES` (test_leak_scan.py), `NEW_STRICT_NAMES` (test_fixture_builder.py) and that `strict` set (test_run_negative_cases.py); `test_run_negative_cases.py` has no total-length assertion on the manifest (it asserts only `len(lint) == 11` and `len(breaking) == 19` for the tagged tool cases, which this WP does not move, and a dynamic `counts:` line). The previous slice's ten strict kinds stay in all three lists; 'the eight old kinds build byte-identically' is the `OLD_KINDS` digest test only.
- **Write scope**: those five files. `enum_pins.json` is written by IC-03 to IC-05, not here.
- **Sequencing**: depends only on the orchestrator's Step 0 record (a measured base and a synced environment, so its reds can be binned and ruff can run); concurrent with IC-01. Red-first: the six plants are undetected by the unchanged scanner (a leading-tilde path is a host path only in the strict class).
- **Acceptance (named)**: `leak_scan.py --root contracts` exits 0 over the existing tree; the eight old kinds build byte-identically; the named census files run green after the test edits (against the Step 0 baseline).
- **Risks**: `negative_cases.json` and `fixture_builder.py` have this one writer; the unicode-escape hazard (quickstart, last section).

### Subtask T006: Red-first: six plants and the exact KINDS set

**Purpose**: Write the failing tests first: the six strict names are in `STRICT_FIELDS`; the exact `KINDS` set gains six new kinds while the eight old kinds still build byte-identically; each planted example (for instance a `profileId` holding a bare absolute path) fails the scan and its clean control passes; each of the three hard-coded strict-name lists (`STRICT_NAMES` in test_leak_scan.py, `NEW_STRICT_NAMES` in test_fixture_builder.py, the `strict` set in test_run_negative_cases.py) gains the six names, and the `== 34` kinds-size assertion in test_fixture_builder.py becomes 40.

**Steps**:
1. Add the six names to the three hard-coded lists, which are the real edit surfaces: `STRICT_NAMES` in `tests/contract/test_leak_scan.py` (it feeds `ALL_KINDS`, so the six kinds are then expected and planted), `NEW_STRICT_NAMES` in `tests/contract/test_fixture_builder.py` (it feeds `STRICT_KINDS`; move the `== 34` size assertion to 40) and the `strict` name set inside `test_the_manifest_holds_one_leak_scan_case_per_planted_kind_with_its_code` in `tests/contract/test_run_negative_cases.py`. There is no manifest length to bump; do not look for one.
2. A raising stub is not needed for data-only edits, but the first commit must still be red on the base for behaviour reasons (the six plants are undetected by the unchanged scanner).
3. Build host-path-shaped plants from fragments at run time; no shared-temp literal.

**Files**: tests/contract/test_fixture_builder.py, test_leak_scan.py, test_run_negative_cases.py (edit)

**Validation**: Red on the base: behaviour failures, controls red where they exercise a new kind.

### Subtask T007: Strict names and the `_NEW_STRICT_NAMES` plants

**Purpose**: In `contracts/tools/fixture_builder.py` add the six names to `STRICT_FIELDS` and the six plants through the `_NEW_STRICT_NAMES` pattern (six new kinds). The eight old kinds must build byte-identically (digest test).

**Steps**:
1. Follow the existing pattern for the previous slice's names; one new kind per name.
2. Write NUL as `chr(0)`-style or hex escape, never as a typed unicode escape.

**Files**: contracts/tools/fixture_builder.py (edit, about 40 lines)

**Validation**: Old-kind digest test green; six new kinds build.

### Subtask T008: Six planted cases in the negative registry

**Purpose**: Add six cases to `contracts/tools/negative_cases.json` (one per name), with the control that must NOT be flagged (`CONTROL_FLAGGED` fails the registry run).

**Steps**:
1. Keep the JSON stable (sorted as the file's existing convention).
2. Run the manifest with the jvm, vacuum and oasdiff tags excluded; the cases needing those binaries are skipped and counted.

**Files**: contracts/tools/negative_cases.json (edit, six cases)

**Validation**: `run_negative_cases.py` over the manifest exits 0 and the count is the previous count plus six.

### Subtask T009: Scanner acceptance over the existing tree

**Purpose**: Run `leak_scan.py --root contracts` over the existing tree: it must exit 0. Run the tool tests, the census files and the named gate files; bin every red against the Step 0 record.

**Steps**:
1. Record the `counts:` lines.
2. Check every edited file for raw NUL bytes.

**Files**: none

**Validation**: Exit 0 and the lines in the hand-off.

## Validation: gates and targeted test surface (concrete; run from the lane workspace root)

Targeted files only, never a directory sweep. Use `PWHEADLESS=1` and the interpreter of the synced environment recorded at Step 0.

### Python checks over the contract tree and the negative-case runner

```text
.venv/bin/python contracts/tools/layout_check.py --root contracts
.venv/bin/python contracts/tools/citation_check.py --root contracts
.venv/bin/python contracts/tools/provisional_check.py --root contracts
.venv/bin/python contracts/tools/example_check.py --root contracts
.venv/bin/python contracts/tools/event_mapping_check.py --root contracts
.venv/bin/python contracts/tools/enum_pin_check.py --root contracts
.venv/bin/python contracts/tools/leak_scan.py --root contracts
.venv/bin/python contracts/tools/structure_check.py --root contracts
.venv/bin/python contracts/tools/codeowners_check.py
.venv/bin/python contracts/tools/no_pytest_scan.py
.venv/bin/python contracts/tools/run_negative_cases.py --manifest contracts/tools/negative_cases.json --work <scratch>/negative-work --exclude-tag jvm --exclude-tag vacuum --exclude-tag oasdiff
```

Exit codes: 0 pass, 1 violation, 2 the check could not do its job. Each prints a final `counts:` line; record them in the hand-off (plan-time lines: `layout_check` `path_files=8 index_files=7`; `citation_check` `properties=191 x_source=140 x_derived=51 inputs_resolved=93`; `provisional_check` `provisional_elements=22`; `example_check` `examples=75 validated=75`; `enum_pin_check` `enums=7 values=43`; `leak_scan` `files=1062 values_strict=682 values_human=8792 values_all=26219 values_artifact_path=37`; `structure_check` `readme_headings=20 changelog_headings=7`; these move as files are added). `citation_check` and `event_mapping_check` read git and the sources: run them from a checkout.

### Tool tests, example and proof modules

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_leak_scan.py tests/contract/test_fixture_builder.py tests/contract/test_enum_pin_check.py tests/contract/test_run_negative_cases.py tests/contract/test_mission_status_examples.py tests/contract/test_mission_status_contract_1_1.py
```

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

## Hand-off report (your final message)

Commits (hash and subject in order, the first marked as the red-first commit); the red evidence (failing test ids, why they are behaviour failures, that the controls are red, how it was verified on the base); every command run with passed/failed/skipped counts and exit codes; baseline bins against the Step 0 record; **measured minima, margins and re-measurements** (every timed bound: the minimum of the repeats and the margin below the bound; every re-measured count; every floor against its re-measure); any refinement of a contract note or design decision; any friction observation (tooling hazards met); anything not done and why. **Code work packages never write under `kitty-specs/`**: the orchestrator appends decisions, measurements and friction add-only to `tracer-approach.md`, `tracer-design-decisions.md` and `tracer-tooling-friction.md` between dispatches.

## Definition of Done

- `leak_scan.py --root contracts` exits 0 over the existing tree.
- The eight old kinds build byte-identically.
- The named census files run green after the test edits (against the Step 0 baseline).
- Each of the six names is in `STRICT_FIELDS`; a planted `profileId` example holding a bare absolute path fails the scan and its clean control passes; the three hard-coded strict-name lists gained the six names (no manifest-length assertion exists to move).
- First commit is the red tests with a raising stub (behaviour failures, controls red), verified on the base; green on the tip.
- Named gate files and census files green or binned against the Step 0 record; ruff check, ruff format --check and TID251 clean with no suppression added.
- Hand-off carries measured minima, margins and re-measurements; nothing written under `kitty-specs/`.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- `negative_cases.json` and `fixture_builder.py` have this one writer.
- The unicode-escape hazard (quickstart, last section).
- A blind scanner (PQ-4) is a stop-and-report, not an edit of `leak_scan.py`.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface, plus the named gate files and census files above; never a full sweep.
- Verify red then green: the first commit is the red-first commit with a raising stub; the red run shows BEHAVIOUR failures, not collection errors; the control tests are red too; green on the tip.
- Re-run the named gate files and the census files; check baseline bins against the Step 0 record in `tracer-approach.md`; check the hand-off carries measured minima, margins and re-measurements.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal; no raw NUL byte.
- Check nothing under `kitty-specs/` was written and no file outside the owned list changed without a recorded rationale.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs W-1 (accept, local lane consolidation, registration and scope check over the real diff), W-2 (J-1 confirmation), W-3 (dev-assist cleanup), W-4 (issue-verdict evidence, aggregate adversarial squad, terminal #5776 verdict), W-5 (history compaction), W-6 (rebase onto upstream `main`) and W-7 (final evidence); then the draft pull request. You do none of this.

## Implementation command

`spec-kitty agent action implement WP02 --agent claude`
