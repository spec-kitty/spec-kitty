---
work_package_id: WP08
title: Ops reader and its tests
dependencies:
- WP07
requirement_refs:
- FR-016
- FR-017
- FR-018
- FR-019
- FR-020
- FR-021
- FR-024
- FR-026
- NFR-002
- NFR-003
- NFR-004
- NFR-005
- NFR-006
- NFR-008
- C-009
- SC-004
- SC-010
planning_base_branch: issue-5776-mission-status-contract-health-drift-ops
merge_target_branch: issue-5776-mission-status-contract-health-drift-ops
branch_strategy: Planning artifacts for this mission were generated on issue-5776-mission-status-contract-health-drift-ops. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5776-mission-status-contract-health-drift-ops unless the human explicitly redirects the landing branch.
subtasks:
- T041
- T042
- T043
- T044
- T045
- T046
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- tests/contract/_mission_status_ops.py
- tests/contract/test_mission_status_ops.py
execution_mode: code_change
model: ''
owned_files:
- tests/contract/_mission_status_ops.py
- tests/contract/test_mission_status_ops.py
- .github/workflows/packs.yml
- tests/architectural/test_ci_corpus_trigger_completeness.py
- .github/workflows/ci-router.yml
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP08 - Ops reader and its tests

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Build the Ops reader: candidate set, order, cursor, closure, skipped records, the evidence pipeline and the loud failures, with every fixture of FR-026 that concerns Ops, the timed redaction and listing cases and a mutation catalogue.

## Context

Follows WP07 in the registration chain (no semantic dependency; the shared registration files and router workflow are what serialise them). Fixture-built only; the real-directory listing is WP09's. Credential withholding happens BEFORE redaction (the order is the rule). An `OSError` versus a vanished file are different outcomes. The 0.1-second redaction assertions run under `-n 4` contention: they are timed as the minimum of at least 5 cold in-test repeats (D-P16), measured first, and the measured minimum and margin go in the hand-off (P-7).

Plan concern: IC-08 of `kitty-specs/mission-status-health-drift-ops-01M464D3/plan.md`. Read, in this order, before writing anything: `.kittify/charter/charter.md`, `AGENTS.md` (for conventions only), the Mission's `spec.md` (the requirement ids in the frontmatter), `plan.md` sections named below, `research.md`, `data-model.md`, `quickstart.md` and `contracts/*.md` in `kitty-specs/mission-status-health-drift-ops-01M464D3/`.

**Dependencies and order.** Depends on WP07; the lane workspace already holds their approved commits. No work package is dispatched before the orchestrator's Step 0 record exists in `tracer-approach.md`. **Pre-dispatch (orchestrator Step PD in `tasks.md`, operator ruling 13):** before this dispatch the orchestrator fast-forwards the mission-lane branch `kitty/mission-<slug>` and, once the orchestrator's run of `spec-kitty agent action implement WP08 --agent claude` (the command of your Implementation command section; it creates or resumes the lane workspace) has created this lane workspace and before you are started, merges the planning branch into it and greps inside it for every record this prompt reads: the Step 0 record (heading `## Record: Step 0`) and the hand-off record of WP07 (heading `## Record: Hand-off WP07 (`), both in `tracer-approach.md`; read them from the lane workspace root. If a line the prompt tells you to read is not there, stop and report it; never run `--refresh-planning-commit` and never copy a record in by hand.

## Owned files (write scope; final, explicit, no directory-wide glob)

- `tests/contract/_mission_status_ops.py` (new: created by this WP, listed in `create_intent`)
- `tests/contract/test_mission_status_ops.py` (new: created by this WP, listed in `create_intent`)
- `.github/workflows/packs.yml`
- `tests/architectural/test_ci_corpus_trigger_completeness.py`
- `.github/workflows/ci-router.yml`

No file under `kitty-specs/` is in this write scope: record what you learn in the hand-off; the orchestrator appends it to the tracer files. An out-of-map edit is acceptable only when small, well-justified and recorded with a one-line rationale in the hand-off. Shared files in this list are declared chokepoints serialised by the dependency chain (plan 'Declared shared-file exceptions'); edit only your own entries in them.

## Implementation concern (plan section IC-08, verbatim)

- **Purpose**: The Ops reader: candidate set, order, cursor, closure, skipped records, evidence pipeline, the loud failures.
- **Relevant requirements**: FR-016 to FR-021, FR-024 (Ops rows), FR-026 (Ops fixtures), NFR-002 (listing bounds), NFR-003, NFR-005, NFR-008; AC-OPS 1 to 14, AC-CROSS 1, 4, 5 (Ops parts: the synthetic 10,000-file case; the real-directory case is IC-09's).
- **Affected surfaces**: new `_mission_status_ops.py`, new `test_mission_status_ops.py` (markers `contract`, `corpus`; module `pytestmark`), the two registration files, `.github/workflows/ci-router.yml`.
- **Red-first**: the AC-OPS rows, each with its control, against a stub `list_ops` that raises; the mutation catalogue of the ops reader; the three timed shapes with their short-value controls, each timed as the minimum of at least 5 cold repeats (D-P16); the cache-the-result mutation joins the catalogue and must fail.
- **Sequencing**: after IC-07 (the registration chain; no semantic dependency). **Acceptance (named)**: as IC-07; the three 256 KiB timed shapes and the 10,000-file listing run with their controls, timed as the minimum of at least 5 repeats, and the planted quadratic mutation still fails; the timed assertions are measured first and the measured minimum and margin recorded in the hand-off (P-7, D-P16).
- **Risks**: a 0.1-second assertion under `-n 4` contention (P-7); credential withholding before redaction (the order is the rule); an `OSError` versus a vanished file.

## Design decisions that bind this work package (plan, verbatim)

**D-P1 Reader architecture.** Five helper modules (PD-1). Entry points return an outcome object (an HTTP status and a body, or a typed refusal), never raise for a refusal, so each of the two operations is testable as the service answers it. An injectable file-system seam (`scandir`, `lstat`, `open_binary`) with counting and fault-injecting wrappers serves the bounded-read assertions (NFR-002); the reader's own code opens only the files the spec lists. No private import except the one `_reset_remote_branch_lookup_cache` of the offline fixture (FR-026) and none in the oracles.

**D-P12 Read-only proof.** `tree_fingerprint` (it already takes a sub-path and hashes bytes and directory names) runs over `kitty-specs` and over `kitty-ops` before and after the run; writers are replaced by ones that raise; a control that writes shows the probe sees writes; the reader's seam records no write mode; the existing autouse fingerprint fixture of the reality module covers the new cases.

**D-P16 Timing method for absolute bounds (plan-round ruling 6; NFR-002, NFR-008; not the spec's D-P15, which is the floors rule).** The 0.1 s redaction bound (three 256 KiB shapes), the 5 s real-directory bound and the 30 s 10,000-file bound are absolute wall-clock assertions in a blocking `-n 4 --dist loadfile` job. Each shape is therefore timed as **the minimum of at least 5 repeated runs inside the test** (the minimum is robust to contention and still falsified by a quadratic matcher, whose long shape stays far over the bound on every repeat); the short-value control is timed **the same way**; the planted quadratic mutation (the pre-fix pattern) must still fail under this method, which the mutation table proves. A fixed repeat count of 5 is the floor, not a retry: no test reruns to green. **Every repeat is cold:** a fresh call of the production entry point on an identical input with no state shared between repeats (new reader state, the per-run memo and the remote-branch lookup cache reset, a fresh opener, and the directory handle rebuilt or re-opened per repeat for the 5 s and 30 s cases); the test asserts that no cache was hit (a counter at zero) or that the call count equals the repeat count, so the minimum is never a cache hit. A second planted mutation, **cache-the-result** (the entry point memoises its result across calls), must turn AC-OPS 14 and the timing cases red, and is also applied as a context manager in the reality module against the real 5 s listing case (plan-round ruling 9); it joins the Ops mutation catalogue beside the quadratic matcher. The work package records the measured minimum and the margin to the bound in its hand-off report (the orchestrator appends it to the tracer file), and a margin under a factor of 2 goes to the operator rather than loosening the bound. The 5 s real-directory case belongs to the reality module (D-P5); the 30 s synthetic case and the 0.1 s cases to the ops module.

## Acceptance rows of this work package (plan 'Test strategy per acceptance criterion', verbatim)

Rule for every row: the test fails when the change is reverted. **Three kinds of revert proof**, named in each row: **B** base-red (the test is red on the work package's base and green on its tip; the first commit carries the test and a stub entry point that raises, so a red is a behaviour failure); **P** planted pair (a control that passes and a plant that fails on the same fixture, so the probe can see the thing); **M** named mutation (a table of reader mutations applied by the test, each of which must turn its rows red: `the mutation was not killed: <name>`; the catalogue is in contracts/tool-extension-and-reader.md). Tests call the reference reader's production entry point, never only a helper. Row numbers are the order of the spec's tables.

| Row | Red-first test (proof kind) |
|---|---|
| 1 newest first, ties by id descending | three Ops with equal `startedAt`; different offsets; control distinct times (B, P, M: ascending) |
| 2 paging once, cursor bound to the filter | an Op written between page reads; cursor of `profile=a` used with `b` and without; forged cursor (each: 400 `invalid_page_cursor`, the FR-024 line) (B, P) |
| 3 filter; `totalCount` equals served count | no-match profile; malformed profile; skipped and filtered records present (B, P) |
| 4 `skippedCount` independent of `profile` | skipped records of several profiles with a filter; control none (B, P) |
| 5 index candidates and lag | lagging index; stale entry (skipped, counted); entry whose profile differs from its file's (the file's value); unreadable index; corrupt line; no index; control index in step (B, P, M: use index profile) |
| 6 closure spine | spine only; own and spine; two spine records; legacy own completion with and without a spine record; control own closure (B, P, M: copy the CLI gap) |
| 7 open and closed invariants | an Op carrying an outcome while open fails validation (B, P) |
| 8 legacy and unreadable skipped; non-Op files not records | legacy started, empty, bad JSON, invalid UTF-8, stem mismatch, bad timestamp, bad `wp_id`, vanished file; the index, spine and `lifecycle.jsonl` in the directory (B, P) |
| 9 empty and failing directory | no `kitty-ops/`; a file named `kitty-ops`; unlistable; unreadable Op file beside readable ones; unreadable spine; spine with invalid UTF-8 (B, P) |
| 10 evidence classes | the table of the spec row, one test per expected (kind, value, redacted); a record with no `evidence_ref` gives `evidence` null (the FR-024 line); controls clean relative path and clean URL (B, P, M: skip step 1(c)) |
| 11 credential withheld before redaction | one `SECRET_PATTERNS` token per shape; the Op stays in `items`, every other field intact, `evidence` null; clean twins (B, P, M: redact first) |
| 12 actor shape | e-mail-shaped actor served with `actor` null (B, P) |
| 13 omitted fields | a reader adding `request_text`; a description lacking one of the five names (B, P) |
| 14 read-only, no agent; linear redaction | writers raising; three 256 KiB shapes, **each timed as the minimum of at least 5 in-test repeats** against 0.1 second, the short-value control timed the same way; the planted quadratic mutation (the pre-fix pattern) still fails; every repeat is cold and the planted cache-the-result mutation turns the row red; the measured minimum and the margin go in the hand-off (D-P16) (B, P, M: quadratic-redaction and cache-the-result) |

AC-CROSS 1, 4 (fixture-built half) and 5 Ops parts:

| AC-CROSS 1 determinism | two reads byte-equal; two bundle builds equal; a clock tick changes `scannedAt` only (B, P) | (the bundle half is carried by the existing `test_two_bundle_builds_of_this_tree_are_byte_identical`, see WP06; no test is written here for it)
| AC-CROSS 4 bounded reads and time | **fixture-built:** counting opener, and subprocess total equals the memo's count plus the listing (drift and ops modules; these are counts, not timings); the synthetic 10,000-file directory at most 30 s (minimum of at least 5 repeats, D-P16) is the Ops module's case only (WP08 T045, plan D-P16 and IC-08), and the drift module has no absolute timing assertion. **Corpus-sized (reality module, IC-09):** real directory at most 5 s (minimum of at least 5 repeats); one Project build and one scan at most 120 s each; one case timing the memoised pass, the Project build and the per-Mission reductions together at most 120 s; each with a discovered-count guard (served plus skipped equals discovered and is non-zero; Missions examined at least the floor); the planted cache-the-result mutation (a memoising listing, applied as a context manager in the reality module) must turn the real 5 s listing case red (B, P, M) |
| AC-CROSS 5 writers | covered by AC-DRIFT 27 and AC-OPS 14 |

### Subtask T041: Red-first commit: AC-OPS rows, raising stub, registration pair

**Purpose**: Commit 1: `tests/contract/test_mission_status_ops.py` with every AC-OPS row, each with its control, against a stub `list_ops` that raises; the mutation catalogue of the ops reader (including the cache-the-result mutation); the three timed shapes with their short-value controls; the registration pair and `pytestmark` in the same commit.

**Steps**:
1. Entry points return an outcome object and never raise for a refusal (D-P1).
2. Host-path, address and credential plants are assembled from fragments at run time; no shared-temp literal.

**Files**: tests/contract/test_mission_status_ops.py (new), _mission_status_ops.py (stub), .github/workflows/packs.yml, tests/architectural/test_ci_corpus_trigger_completeness.py (the registration pair); .github/workflows/ci-router.yml only if the test module or the stub already imports a `src/` file the `contract_tools` group does not name (otherwise the globs land with the helper's real imports)

**Validation**: Red run: behaviour failures, controls red; registry gates green.

### Subtask T042: Candidates, order, cursor, filter, counts

**Purpose**: Candidate set from the Op files with the index as a hint (a lagging index, a stale entry skipped and counted, an entry whose profile differs from its file takes the file's value, unreadable or corrupt index, no index); newest first, ties by id descending, instants not text; paging once with a cursor bound to the filter (bad, forged or mismatched cursor gives 400 `invalid_page_cursor`); the `profile` filter; `totalCount` equals the served count; `skippedCount` independent of `profile`.

**Steps**:
1. AC-OPS 1 to 5 and 8, 9.

**Files**: tests/contract/_mission_status_ops.py

**Validation**: AC-OPS 1-5 green.

### Subtask T043: Closure by the spine and the invariants

**Purpose**: Closure reads the closure spine as well as the Op's own file (spine only; own and spine; two spine records; legacy own completion with and without a spine record); open and closed invariants (an Op carrying an outcome while open fails validation); legacy and unreadable records are skipped and counted; non-Op files (the index, the spine, `lifecycle.jsonl`) are not records.

**Steps**:
1. Mutation: copying the CLI gap must be killed (AC-OPS 6).

**Files**: tests/contract/_mission_status_ops.py

**Validation**: AC-OPS 6-8 green.

### Subtask T044: Directory failures and evidence pipeline

**Purpose**: Empty and failing directory outcomes (no `kitty-ops/` gives 200 empty; a file named `kitty-ops`, unlistable, an unreadable Op file or spine, a spine with invalid UTF-8 give 500 `ops_unreadable`); the evidence pipeline: withhold credentials (one `SECRET_PATTERNS` token per shape) BEFORE redaction, redact paths and addresses, classify `repo_path`, `url`, `text`, `evidence` null when there is no `evidence_ref`; actor shape (an e-mail-shaped actor is served as null); omitted fields never served.

**Steps**:
1. The Op stays in `items` when its evidence is withheld; every other field intact.
2. Mutations: redact first; skip step 1(c); use the index profile.

**Files**: tests/contract/_mission_status_ops.py

**Validation**: AC-OPS 9-13 green.

### Subtask T045: Timed shapes, read-only, bounded reads

**Purpose**: Three 256 KiB shapes each timed as the MINIMUM of at least 5 cold in-test repeats against 0.1 second, the short-value control timed the same way, the planted quadratic mutation (the pre-fix pattern) still failing, the planted cache-the-result mutation turning the row red; read-only (writers raise; no agent started); the synthetic 10,000-file directory at most 30 s (minimum of at least 5 repeats) with a counting opener.

**Steps**:
1. Every repeat is cold: new reader state, a fresh opener, no cache hit (a counter at zero or the call count equals the repeat count).
2. Measure first: Measure each bound on the unchanged fixture (or corpus) before asserting it; a margin under a factor of 2 (bound divided by the measured minimum) is reported to the operator in the hand-off and the bound is not loosened and the case is not skipped. Record the measured minimum and the margin of each bound in the hand-off.

**Files**: tests/contract/test_mission_status_ops.py

**Validation**: AC-OPS 14 and AC-CROSS 4 (fixture-built half) green.

### Subtask T046: Acceptance runs (router-glob derivation check)

**Purpose**: Confirm that the router-glob derivation test (`test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import`, in `tests/ci/test_contracts_workflows.py`) is green. The globs were already added, each in the commit that first imported its `src/` file (Registration item 4); this subtask edits nothing. Run the module under the router marker expression and the negative collection; run the census and registration gates and the tool-job selection and, last, the three battery legs (binding gate below).

**Steps**:
1. Record counts, runtimes and margins.

**Files**: none

**Validation**: Named acceptance green.

## Validation: gates and targeted test surface (concrete; run from the lane workspace root)

Targeted files only, never a directory sweep. Use `PWHEADLESS=1` and the interpreter of the synced environment recorded at Step 0.

### Tool tests, example and proof modules

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_leak_scan.py tests/contract/test_fixture_builder.py tests/contract/test_enum_pin_check.py tests/contract/test_run_negative_cases.py tests/contract/test_mission_status_examples.py tests/contract/test_mission_status_contract_1_1.py
```

The new module of this work package, run on its own after the red commit and on the tip:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_ops.py
```

### The tool job's whole selection

The tool job's whole selection, as the router runs it (plan-time: 1,778 passed, 37 skipped in 176 s locally; re-take against the Step 0 record):

```text
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -m "corpus and not windows_ci" tests/contract --ignore=tests/contract/test_example_round_trip.py --ignore=tests/contract/test_mission_status_payloads.py --ignore=tests/contract/test_mission_status_reality.py -n 4 --dist loadfile -q
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

Named files only, never the directory, never `tests/architectural` as a sweep for these commands (charter rule `NO_FULL_HEAVY_SUITES_IN_MISSION`; the one exception is the binding three-leg battery gate below, by operator ruling). The scans inspect real-git fixtures, a `subprocess` stub, a counting wrapper, git identity setup, any manual `os.chdir`, `os.environ` or `sys.path` change, a shared-temp literal and a wall-clock call in a test module: use `monkeypatch` and a scratch `HOME`, an injected clock, and build host-path-shaped plants from fragments. **No allowlist or baseline entry may be added to make a new module pass.** The two dead-symbol files walk `src/` (no `src/` change here) and run only in the Step 0 baseline.

### Registration of `test_mission_status_ops.py` (NEW test module)

**Registration pair, in the SAME commit that creates the module (and in sorted position; the registry gates must be green on every commit):**

1. `.github/workflows/packs.yml`: one `--deselect tests/contract/test_mission_status_ops.py` entry in the one-line `built-in-corpus-suite` command (it is one physical line; edit it in place, keep it one line, keep alphabetical position among the existing `--deselect tests/contract/...` entries).
2. `tests/architectural/test_ci_corpus_trigger_completeness.py`: one row `"tests/contract/test_mission_status_ops.py",` in the `_CORPUS_MARKED_MODULES` frozenset, in sorted position (the neighbouring detail-reader module is the pattern).
3. `pytestmark` of the module: ONE single-line list holding `pytest.mark.corpus`, exactly the form of `tests/contract/test_mission_status_detail.py`: `pytestmark = [pytest.mark.contract, pytest.mark.corpus]`. The registry gate's `_CORPUS_MARK_APPLICATION_RE` matches `pytestmark = ... pytest.mark.corpus` within one line only; a mark spelled through a shared list or wrapped across lines is reported as in the registry but not marked.
4. Router globs (the `contract_tools` group of `.github/workflows/ci-router.yml`): add the `**/<path>` entries for the `src/` files the new helper(s) import, spelled `**/specify_cli/...` / `**/kernel/...` so the group stays non-src, in sorted position, in the commit that FIRST adds an import of that `src/` file, never in a separate closing commit (the derivation test is in `tests/ci/test_contracts_workflows.py` and scans every `tests/contract/*mission_status*.py` file, stubs included, so it goes red the moment any such file imports a `src/` file the group does not yet name, and the 'registry gates green on every commit' rule then fails). The red-first commit carries the globs only if its test module or its stub imports a `src/` file (a stub that merely raises imports nothing and needs none); otherwise they land in the commit that gives the helper its real body, together with that import. The test `test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import` derives the required list from the imports and stays red until they are present; never write the list by hand, recompute it from that test's output. Expected new entries (recomputed by the test, not typed): `**/specify_cli/invocation/record.py`, `**/specify_cli/invocation/writer.py`, `**/specify_cli/invocation/errors.py`, `**/specify_cli/core/paths.py` and the `__init__` files the import scan adds
5. Proof of selection: `.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_mission_status_ops.py` collects the module; `.venv/bin/python -m pytest --collect-only -q -m "fast or unit" tests/contract/test_mission_status_ops.py` collects nothing (exit 5 and no test ids is the pass condition).
6. Editing `packs.yml` and the registry test selects the `architectural-heavy` battery on this PR (plan PD-2). The operator's ruling 14 makes the three battery legs a BINDING local gate for this work package: see the next section.

### **Architectural battery: BINDING local gate (operator ruling 14, `kitty-specs/mission-status-health-drift-ops-01M464D3/reviews/tasks.ruling.md`, 2026-10-06).** This work package edits registration files (`.github/workflows/packs.yml`, `tests/architectural/test_ci_corpus_trigger_completeness.py`, `.github/workflows/ci-router.yml`), which selects the architectural battery on the pull request. The operator requires the FULL architectural battery to be run locally on this work package, as on #5625 (the previous slice, `kitty-specs/mission-status-contract-1-1-01M42XJC/tracer-design-decisions.md`, section 'Operator request: local architectural battery runs'). This is a binding gate, not a conditional one and not dependent on the dispatch brief. **It overrides, for WP03, WP07 and WP08 only (and, by orchestrator note 17 of `reviews/tasks.ruling.md` extending ruling 14, for the orchestrator's Step 0 baseline run of the same three legs on the unchanged D-0 tip and its note 16 fallback run of them on a lane tip; the ruling's own text names only WP03, WP07 and WP08), the charter rule `NO_FULL_HEAVY_SUITES_IN_MISSION` and the plan's 'CI-owned, not run locally' default** (the ruling replaces that bar); everywhere else in this Mission the rule stands, and the named-files-only rule above still governs every other command of this work package.

**The three legs** are the jobs of `.github/workflows/ci-router.yml` as it runs them: `architectural-fast` (display name `architectural fast gates (ratchet/census, always-on)`, CI timeout 10 minutes) and `architectural-heavy` (one job key, a two-leg matrix, display name `architectural battery (heavy, code-scoped) 1/2` and `2/2`, CI timeout 30 minutes each). Common selection: the directory `tests/architectural`, the marker expression `-m "not performance and not stress and not timing"`, `-n 4 --dist loadfile`, and four `--deselect` entries for files other jobs own (`test_no_legacy_terminology.py` in the `terminology` job, `test_layer_rules.py` and `test_pyproject_shape.py` in the `layer-rules` job, `test_archive_root_byte_identical.py` in the `archive-freeze` job; those four run in this work package's named gate commands above, not in the legs). The shard split is the partition plugin `scripts/ci/battery_partition_plugin.py` (`-p scripts.ci.battery_partition_plugin --battery-part fast`, `1/2` or `2/2`): file-disjoint parts that together cover the base selection, proved statically by `tests/architectural/test_battery_partition_proof.py`. `uv run --frozen python` of the CI commands is replaced here by `<synced-python>`, the interpreter of the synced environment defined once in orchestrator Step 0 (item 2 of `tasks.md`, the `<scratch>/venv/bin/python` recorded in the Step 0 record; never the hand-built checkout `.venv/bin/python`, which lacks respx, and never a bare `uv run`). **Before the first leg**, from this lane workspace root, run `<synced-python> -c "import specify_cli; print(specify_cli.__file__)"`: the path must lie inside this lane workspace's `src/`; if it does not, put `PYTHONPATH=<lane workspace>/src` in front of every leg command and repeat the check (a leg that imported another tree proves nothing), and the junit files go to `<scratch>`, never into the workspace. Collection was checked on the planning base with exactly these commands (`--collect-only`): fast 34 files, 787 tests; heavy 1/2 106 files, 1,651 tests; heavy 2/2 106 files, 1,363 tests; counts move with the tree, so compare against the Step 0 record, not against these figures.

Leg 1, `architectural-fast`:

```text
PWHEADLESS=1 <synced-python> -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part fast \
  --junitxml=<scratch>/xunit-architectural-fast.xml
```

Leg 2, `architectural-heavy` shard `1/2` (label `1-of-2`):

```text
PWHEADLESS=1 <synced-python> -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part 1/2 \
  --junitxml=<scratch>/xunit-architectural-heavy-1-of-2.xml
```

Leg 3, `architectural-heavy` shard `2/2` (label `2-of-2`):

```text
PWHEADLESS=1 <synced-python> -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part 2/2 \
  --junitxml=<scratch>/xunit-architectural-heavy-2-of-2.xml
```

**How to run.** From the lane workspace root (the `-p scripts.ci.battery_partition_plugin` import fails elsewhere), on the final commit of the work package after the named gate files are green and before the approval request. Each leg runs as a **background command** with its output and exit code written to scratch files (a heavy shard can run up to the 30-minute CI budget): `nohup sh -c '<the leg command>; echo $? > <scratch>/leg-N.exit' > <scratch>/leg-N.log 2>&1 &` (with the Bash tool: `run_in_background`). Await each leg with **the harness's permitted wait primitive: a background command awaited with an until-loop monitor** (for example a monitor on `until [ -f <scratch>/leg-N.exit ]; do sleep 20; done`), **never a foreground `sleep` loop** (the harness refuses a foreground sleep, and a denied command means stop). A missing exit-code file means not finished, never a pass; a tool timeout is neither a pass nor a fail. Do not hand off before all three exit-code files exist. **Probe and fallback (orchestrator note 16 of `reviews/tasks.ruling.md`):** the orchestrator probes the primitive once at Step 0 and records `wait-primitive: permitted` or `wait-primitive: not permitted` in the Step 0 record. If the record says `not permitted`, or your first attempt to use the primitive is denied, STOP, do not run the legs and do not retry in another form: state in your hand-off that the three legs are left to the orchestrator, which runs the same three commands itself on your final commit before the review, binned the same way, and appends the result to your hand-off record; the reviewer reads the three exit-code files from there.

**Binning.** Bin every red of a leg against the orchestrator's Step 0 record in `tracer-approach.md`, which carries a per-leg baseline for each of the three legs (the latest `main` run conclusion and duration of each job, and the Step 0 local run of each leg on the unchanged base: counts and exit status). Only a red that is red on your branch and green on the base is yours. The previous slice met two environmental reds in heavy 1/2 on every run (the graph regeneration byte-identity test, which shells out to the user-level installed CLI, and the accept-stamp idempotency test, which resolves the placement port to a stray repository at the system temporary root); treat that as a hint for where to look, never as a pre-binned answer: the Step 0 record of this Mission decides. **Durations:** report the wall time of each leg beside the Step 0 local wall time of the same leg (same commands, same interpreter, no CI `collect_universe_prestep`); the main-CI durations are informational and carry no pass rule (orchestrator note 15, `reviews/tasks.ruling.md`), so a longer or shorter time is reported, not binned. A pre-existing red is reported in the hand-off (command, failure summary, why), never absorbed, and the leg is not retried to green. The hand-off carries, per leg, the command, the passed, failed and skipped counts, the exit status from the exit-code file, the junit path and the bins.

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

- As WP07 (red first, mutations killed, census and registration gates green).
- The three 256 KiB timed shapes and the 10,000-file listing run with their controls, timed as the minimum of at least 5 repeats, and the planted quadratic mutation still fails.
- The timed assertions are measured first and the measured minimum and margin are recorded in the hand-off (P-7, D-P16). A bound whose margin is under a factor of 2 is reported to the operator in the hand-off; it is not loosened and its case is not skipped, and a work package that records such a margin and moves on is not done.
- AC-OPS 1 to 14.
- First commit is the red tests with a raising stub (behaviour failures, controls red), verified on the base; green on the tip.
- `test_mission_status_ops.py`: registration pair and single-line `pytestmark` in the module-creating commit; the router globs in the commit that first imports each `src/` file (the helper commit; the red-first commit only if its stub or test module imports `src/`); registry gates green on every commit; the router-glob derivation test confirmed green in T46, with no separate closing glob commit.
- The three architectural battery legs (`architectural-fast`, `architectural-heavy` 1/2 and 2/2) ran locally on the final commit, as the binding gate of operator ruling 14 requires: three exit-code files read, counts and exit status in the hand-off, every red binned against the Step 0 per-leg baselines. Under the note 16 fallback (the orchestrator ran the legs because the wait primitive was denied to the worker), this is met when the orchestrator ran the three legs and appended the three exit-code results to the hand-off record before review; the worker's hand-off then states that the legs are left to the orchestrator.
- Named gate files and census files green or binned against the Step 0 record; ruff check, ruff format --check and TID251 clean with no suppression added.
- Hand-off carries measured minima, margins and re-measurements; nothing written under `kitty-specs/`.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- A 0.1-second assertion under `-n 4` contention (P-7).
- Credential withholding before redaction (the order is the rule).
- An `OSError` versus a vanished file.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface, plus the named gate files and census files above; never a full sweep, except the three battery legs of the binding gate below (operator ruling 14 makes them binding for WP03, WP07 and WP08 only; every other work package keeps named files only).
- Verify red then green: the first commit is the red-first commit with a raising stub; the red run shows BEHAVIOUR failures, not collection errors; the control tests are red too; green on the tip.
- Re-run the named gate files and the census files; check baseline bins against the Step 0 record in `tracer-approach.md`; check the hand-off carries measured minima, margins and re-measurements.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal; no raw NUL byte.
- Check nothing under `kitty-specs/` was written and no file outside the owned list changed without a recorded rationale.
- Verify every mutation of the catalogue is killed, the registration pair is in the module-creating commit, each router glob is in the commit that first imports its `src/` file, and the module is selected by the router marker expression and not by the nightly's. Verify the hand-off carries the three battery legs (binding gate, operator ruling 14): command, counts, exit status from the exit-code files and bins against the Step 0 per-leg baselines; re-run a leg when the hand-off is thin, and treat a missing leg as a reason to reject (under the note 16 fallback the rejection applies after the orchestrator has appended the three exit-code results to the hand-off record; before that append, a hand-off that says the legs are left to the orchestrator is not rejected for it). Compare each leg with the Step 0 local run of the same leg, not with main-CI durations (informational only, orchestrator note 15).
- Verify the timed assertions are the minimum of at least 5 cold repeats with the short-value control timed the same way, and that the quadratic and cache-the-result mutations still fail.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs W-1 (accept, local lane consolidation, registration and scope check over the real diff), W-2 (J-1 confirmation), W-3 (dev-assist cleanup), W-4 (issue-verdict evidence, aggregate adversarial squad, terminal #5776 verdict), W-5 (history compaction), W-6 (rebase onto upstream `main`) and W-7 (final evidence); then the draft pull request. You do none of this.

## Implementation command

`spec-kitty agent action implement WP08 --agent claude`
