---
work_package_id: WP05
title: Reader foundation and the artifact reader
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-009
- FR-010
- FR-011
- FR-012
- FR-013
- FR-014
- FR-015
- FR-016
- FR-020
- FR-022
- NFR-002
- NFR-003
- NFR-005
- NFR-006
- C-003
- C-004
- C-005
planning_base_branch: issue-5625-mission-status-contract-1-1
merge_target_branch: issue-5625-mission-status-contract-1-1
branch_strategy: Planning artifacts for this mission were generated on issue-5625-mission-status-contract-1-1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5625-mission-status-contract-1-1 unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
- T027
- T028
- T029
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- tests/contract/_mission_status_artifacts.py
- tests/contract/test_mission_status_artifacts.py
execution_mode: code_change
model: ''
owned_files:
- tests/contract/_mission_status_payloads.py
- tests/contract/_mission_status_artifacts.py
- tests/contract/test_mission_status_artifacts.py
- tests/contract/test_mission_status_payloads.py
- tests/contract/test_mission_status_reality.py
- .github/workflows/packs.yml
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP05 – Reader foundation and the artifact reader

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Extend the payload helper with the shared foundation (wanted titles, artifact-path leak class, fingerprint with directory names, fixture-writer arguments; the `FLOORS` fields and values are WP08's) and write the artifact reader with its full test module, a thin corpus smoke and the module's registration pair.

## Context

Plan IC-06, decisions D-P2, D-P8, D-P9, D-P12; data model sections Eligible file, Content read: the order of decision, Redaction, Classifier, Media type, `modifiedAt`, Listing walk, Host capability and the file-system seam (`kitty-specs/mission-status-contract-1-1-01M42XJC/data-model.md`); reader table in `kitty-specs/mission-status-contract-1-1-01M42XJC/contracts/tool-extension-and-reader.md` section B. **Dispatch precondition (orchestrator-owned, not encoded in `wps.yaml`):** step J-1 of `tasks.md` (Dispatch order) has run on the WP04 lane tip with WP04 approved, and any defect it found is closed through a reopened WP03 or WP04; if the operator accepted the absence of a JVM machine, that acceptance is recorded in the hand-off. Depends on WP01 (the campsite helpers in the payload helper), WP02 (the shared `malformed_artifact_path`, reaching this lane through the dependency-lane merge) and WP03 (the artifact schemas). The helper edit lands as the first implementation sub-step so WP06 starts from it. **Not concurrent** with WP06 or WP08: they share the payload helper and the reality module. Registrations: this WP is the first writer of the single-writer chain for `.github/workflows/packs.yml` (one physical line: the `built-in-corpus-suite` command) and `_CORPUS_MARKED_MODULES` (WP05, then WP06, then WP07). Markers of the new module: `contract`, `fast`, `corpus` (it reads no tag, no history, starts no subprocess). **Registration timing (one rule):** the registration pair (T029) is committed WITH the module-creating red-first commit (T023), so no commit leaves the registry gates red; the red-first content (the failing reader tests) is still first and is the only intended red. **Review slices:** one commit per subtask, subject naming the subtask; the seams are T024 (helper foundation) versus T025 to T029 (reader).

Decisions honoured (spec.md, Decisions and Traceability; read `kitty-specs/mission-status-contract-1-1-01M42XJC/spec.md` with this prompt; the rows are `tasks.md`, section Coverage): CL-1, CL-2, CL-3, CL-4; AD-1, AD-2, AD-4, AD-5, AD-6, AD-7, AD-8, AD-9, AD-10, AD-11, AD-12, AD-14, AD-15, AD-17, AD-18, AD-19, AD-21, AD-22; AC-LIST, AC-CONTENT; OQ-4; OD-1.

Plan concern: IC-06 (plan section Implementation Concern Map). Requirement refs: FR-009, FR-010, FR-011, FR-012, FR-013, FR-014, FR-015, FR-016, FR-020, FR-022, NFR-002, NFR-003, NFR-005, NFR-006, C-003, C-004, C-005. Dependencies: WP01, WP02, WP03. Branch contract: planning base and merge target are `issue-5625-mission-status-contract-1-1`; work runs in the lane workspace `spec-kitty agent action implement` resolves for you (never reconstruct a path by hand).

## Owned files (write scope)

Edit only these paths (declared shared-file exceptions are dependency chains, never concurrent; plan section Lanes):

- `tests/contract/_mission_status_payloads.py`
- `tests/contract/_mission_status_artifacts.py`
- `tests/contract/test_mission_status_artifacts.py`
- `tests/contract/test_mission_status_payloads.py`
- `tests/contract/test_mission_status_reality.py`
- `.github/workflows/packs.yml`
- `tests/architectural/test_ci_corpus_trigger_completeness.py`

2 of these paths do not exist yet on the planning base and are declared in the frontmatter `create_intent` (finalisation refuses a literal path that matches zero files unless it is declared there); you create them.

Nothing under `kitty-specs/` is written by this work package: records you must make (a contract-note refinement, a decision, a friction observation, the baseline) go into your hand-off report; the orchestrator appends them add-only to the tracer files. A small, well-justified out-of-map edit is acceptable only with a one-line rationale in the hand-off report; the no-overlap rule is the real guard against collisions.

### Subtask T023: Red-first: failing artifact-reader tests and the thin corpus smoke

**Purpose**: First commit: failing tests, red on the planning base.

**Steps**:

1. Create `tests/contract/test_mission_status_artifacts.py` with the first tests (eligibility incl. symlink-through-component, root-only status exclusion, malformed-path table, classifier order, listing sort in byte order) and the thin corpus smoke test in `test_mission_status_reality.py` (listing and content over every real Mission; examined equals the independent discovered count, zero exclusions, no thresholds, and both counts are greater than zero: a zero guard is not a threshold).
2. Create a skeleton `tests/contract/_mission_status_artifacts.py` in the same commit: the public functions exist but raise `NotImplementedError` or return empty results, so the tests import cleanly and each test fails on its own assertion, never as one collection error. Record the per-test failure messages.
3. Add the registration pair in the same commit (T029 lists the edits), so the registry gates are green on it and the reader tests are the only intended red.
4. Run against the planning base (extract the base, copy the new test file and the skeleton in): the reader tests fail on their assertions. Commit before any implementation.

**Files**: `tests/contract/test_mission_status_artifacts.py` (new), `tests/contract/_mission_status_artifacts.py` (new, skeleton), `tests/contract/test_mission_status_reality.py` (smoke), `.github/workflows/packs.yml` and `tests/architectural/test_ci_corpus_trigger_completeness.py` (the registration pair, see T029).

**Validation**: Red on the planning base for the stated per-test reasons, recorded in the hand-off report; the nine router and registry gate files green on this commit.

### Subtask T024: Payload helper foundation: wanted titles, leak class, fingerprint directories, fixture writer

**Purpose**: The helper foundation, as the first implementation sub-step.

**Steps**:

1. `_mission_status_payloads.py`: `Contract` wanted titles gain `WorkPackageDetail`, `ArtifactListing`, `ArtifactContent`, `ArtifactRefusal`, `WorkPackageDetailRefusal`; `payload_leaks` gains the artifact-path class by importing `malformed_artifact_path` through the existing loader (tests importing tools is the allowed direction; `contracts/tools/` never imports `tests/`); `tree_fingerprint` gains the directory names under `kitty-specs/` (FR-014, D-P12; this is the one planted control for the fingerprint: a writing reader that only creates an empty directory shows the old fingerprint blind and the new one not; WP08 references it and does not restate it). The `FLOORS` fields and values are NOT added here: WP08 adds them where they are consumed; `write_fixture_mission` gains a `files` mapping (text or bytes), `lanes` and `tasks_md` arguments.
2. Add the direct tests for each new helper branch in `tests/contract/test_mission_status_payloads.py` (Sonar: new branches get tests in the same change).

**Files**: `tests/contract/_mission_status_payloads.py` (about 250 lines added), `tests/contract/test_mission_status_payloads.py` (about 150 lines).

**Validation**: `test_mission_status_payloads.py` and `test_mission_status_reality.py` still green (counts at least those of the WP01 baseline).

### Subtask T025: _mission_status_artifacts.py: file-system seam, eligibility, containment, classifier, media type, modified time

**Purpose**: The reader's seam, eligibility and classification.

**Steps**:

1. New `tests/contract/_mission_status_artifacts.py`: `FileSystem` seam (`scandir`, `lstat`, `open_binary`) and `REAL_FS`; `resolve_mission(repo_root, mission_id)` (reads `MissionSource.own_dir`, the primary planning surface, never `read_dir`; ledger SK-310); `is_eligible` (regular file, no symlink component below the Mission directory by lstat of every component, not the root `status.events.jsonl`/`status.json`, path not malformed); `classify` (the twelve kinds in the documented order); `media_type_of`; `modified_at` (UTC with `Z`, whole seconds, floored; never used for ordering).
2. Public readers only; no private import; the module never calls the writing `materialize`.

**Files**: `tests/contract/_mission_status_artifacts.py` (new, about 450 lines).

**Validation**: T023 tests turn green for eligibility, classifier and listing sort.

### Subtask T026: Content read in the order of decision, redaction, credential check, listing, artifact references

**Purpose**: Content read, redaction, credential check, listing and artifact references.

**Steps**:

1. `read_content(...)` implements the single order of decision: 400 malformed or missing or repeated path; 404 unknown or ill-formed Mission id or not eligible; 500 directory unreadable; open read-only and `fstat` the OPEN handle; size over 262,144 gives 413 without reading; read at most 262,145 bytes; open or read failure 500; a 262,145th byte gives 413; NUL byte then strict UTF-8 decode failure gives 415 (no signature stripping, no replacement characters); `SECRET_PATTERNS` match gives 422 with no content in the body; else 200. Cap is on raw bytes before redaction.
2. `redact` (host path to `[path]`, e-mail to `[email]`, using `leak_patterns`; adds and weakens no pattern) and `has_credential`; `redacted` true when a substitution changed the text.
3. `list_artifacts(...)`: `lstat` walk (no symlink followed or entered), eligible files only, sort by path in byte order of UTF-8, keep 1000, `truncated`, stat and read only the returned entries; `readable` computed by running the same read function over every returned entry; a vanished file is omitted, any other stat failure or unreadable directory is 500 `artifact_listing_unreadable`.
4. `artifact_references(...)`: prompt and spec references from the eligibility rule only (a directory read and lstats; no listing walk, no content open), reused by WP06.
5. `ArtifactOutcome(status, body)`: entry points return an outcome and never raise for a refusal.

**Files**: `tests/contract/_mission_status_artifacts.py` (grows to about 800 lines).

**Validation**: Tests of T027 green.

### Subtask T027: test_mission_status_artifacts.py: the full test matrix with faults and killed mutations

**Purpose**: The full test module for the artifact reader, with faults and killed mutations.

**Steps**:

1. Parametrised containment refusals with status and code, never leaking the target: every malformed form, doubly encoded traversal, symlinks, another Mission, a directory, a symlinked `tasks/`, missing and repeated `path`, ill-formed ids.
2. Boundary and encoding: 262,144 and 262,145 bytes; an oversize non-UTF-8 file gives 413; grow-during-read gives 413 (fault-injected opener); BOM kept; zero-byte file is a 200 with empty content; NUL and invalid byte at the last byte of a 262,144-byte file give `readable: false`; 1,001-file Mission (truncated); nested `status.json` is an artifact; names with an at sign (built at run time), a `home/<x>/` segment, a backslash, a 513-character path.
3. Credentials: each credential kind gives 422 with a clean twin giving 200; a dirty file gives `redacted: true` and its clean twin `false`; reader-level planted pairs: `payload_leaks` over a built `ArtifactContent` with an unredacted body reports `HOST_PATH` and `EMAIL` (fails if the reader stops redacting), clean twin passes.
4. Bounded read: the counting `FileSystem` shows at most 262,145 bytes read and one file opened for a content read; fault-injected `scandir`, `lstat` and `open` each with a positive fired counter (failure text `the injected fault did not fire`); no use of `chmod`.
5. Mutations killed (each applied by the test and the target tests must then fail; failure text `the mutation was not killed: <name>`): wrong order of decision, wrong credential rule, wrong NUL rule, symlink followed, cap off by one, sort by `modifiedAt`.
6. Determinism: two listings and two contents of an unchanged Mission are byte-identical; `modifiedAt` sub-second mtime floored; 404 `not_found` for an unknown Mission; the root and the operations carry no `security`.
7. Markers `contract`, `fast`, `corpus`; no `os.chdir`, `os.environ` or `sys.path` manual mutation (use `monkeypatch` and a scratch HOME).

**Files**: `tests/contract/test_mission_status_artifacts.py` (grows to about 1,000 lines).

**Validation**: `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_artifacts.py` green; the named architectural-fast files green after the module exists.

### Subtask T028: Thin corpus smoke and helper tests: examined equals discovered

**Purpose**: The thin corpus smoke over the real tree (the floors, controls and fixture are WP08's).

**Steps**:

1. Complete the smoke of T023: listing and content over every real Mission, examined equals the independently discovered count and both are greater than zero, zero exclusions, no thresholds, no leak; read-only via the existing autouse fingerprint fixture (now with directory names). Do not call `materialize`.
2. Collect proof: `.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_mission_status_artifacts.py` selects the module (the router marker expression).

**Files**: `tests/contract/test_mission_status_reality.py` (about 60 lines).

**Validation**: Smoke green; module collected by the router expression.

### Subtask T029: Registrations: one --deselect entry and one registry row for the artifacts module

**Purpose**: The two registrations a new corpus-marked module needs (OD-1 X-pure). They are committed with the module-creating red-first commit (T023), not after it; this subtask defines the edits and records the gate results.

**Steps**:

1. `.github/workflows/packs.yml`: add one `--deselect tests/contract/test_mission_status_artifacts.py` to the `built-in-corpus-suite` command (that whole pytest command is ONE physical line: insert in sorted position, edit nothing else on it).
2. `tests/architectural/test_ci_corpus_trigger_completeness.py`: one new row in `_CORPUS_MARKED_MODULES` (one entry per line, sorted position).
3. Run the router and registry gate files (below) on the T023 commit and again at the end: same-tier uniqueness and the corpus trigger gate are red without both registrations, so they are green on the T023 commit because it carries them. Either edit selects the `architectural-heavy` battery on the PR; this work package runs that battery itself (section Validation).
4. Hand-off report: both diffs, the gate runs on the module-creating commit and at the end, and the counts.

**Files**: `.github/workflows/packs.yml` (one line, one entry added), `tests/architectural/test_ci_corpus_trigger_completeness.py` (one row).

**Validation**: The nine router and registry gate files green on the T023 commit and at the end (baseline 368 passed, 1 skipped).

## Validation: gates and targeted test surface

Charter: no full `tests/architectural/`, end-to-end, performance or `make test-full` sweep in mission work (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run exactly the commands below, record each command and its passed/failed counts in the hand-off report. Use the checkout's own environment (`.venv/bin/...`), never a bare `uv run`. `<scratch>` means a scratch directory outside the repository.

**Targeted test surface of this work package**:

- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_artifacts.py tests/contract/test_mission_status_payloads.py tests/contract/test_leak_scan.py`
- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py tests/contract/test_mission_status_payloads.py`
- `.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_mission_status_artifacts.py`

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

**This work package touches the registries and a workflow (`.github/workflows/packs.yml`, `tests/architectural/test_ci_corpus_trigger_completeness.py`).** Either edit selects the CI `architectural-heavy` battery on the pull request, and the `architectural-fast` battery runs on every pull request.

**Operator requirement (recorded add-only in `tracer-design-decisions.md`):** a work package that touches a registry or a workflow must pass BOTH architectural battery parts exactly as `.github/workflows/ci-router.yml` runs them. The charter (`NO_FULL_HEAVY_SUITES_IN_MISSION`) forbids a local architectural sweep except on an explicit operator request; the operator's brief for this Mission is that request, for these two parts and for this work package only. So: **the implementer runs `architectural-fast` and both `architectural-heavy` shards (`1/2` and `2/2`) before requesting approval** and records, per part, the command, the passed, failed and skipped counts, the exit status and the junit path in the hand-off report; **the reviewer re-runs the three legs or verifies the recorded output** (counts and exit status) against the commit under review; both bin any red against the WP01 main-CI record in `tracer-approach.md`. CI keeps the final word: this does not turn any other mission work into a sweep.

**Reference: the CI commands, verbatim** from `.github/workflows/ci-router.yml` (jobs `architectural-fast` and `architectural-heavy`, step `run`). They are the exact invocation CI itself uses and are kept unparaphrased so each line can be confirmed against the workflow. They are not runnable as pasted: the heavy block holds two workflow expressions, and the first two lines are CI's own environment steps.

Battery part `fast` (job `architectural-fast`, `-n 4`):

```text
uv sync --frozen --all-extras
uv run --frozen python -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part fast \
  --junitxml=out/reports/xunit-architectural-fast.xml
```

Battery part `heavy` (job `architectural-heavy`; the matrix `shard` runs `1/2` and `2/2`, the `label` is `1-of-2` and `2-of-2`):

```text
uv sync --frozen --all-extras
uv run --frozen python -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part ${{ matrix.shard }} \
  --junitxml=out/reports/xunit-architectural-heavy-${{ matrix.label }}.xml
```

**Reconciling verbatim-from-CI with "never a bare `uv run`".** The rule bans a bare `uv run` because it can re-sync the environment shared with the lane. CI uses `uv sync --frozen --all-extras` and `uv run --frozen python -m pytest`; that is the invocation of the reference blocks above. Locally the orchestrator runs `uv sync --frozen --all-extras` once when the lane workspace is set up (the baseline rule's stale-venv bin), and each leg then runs the same pytest arguments through the checkout's interpreter: `.venv/bin/python -m pytest` in place of `uv run --frozen python -m pytest`, the matrix placeholders resolved into the three concrete invocations below, and the junit files written to `<scratch>` (a scratch directory outside the repository), never to `out/reports` in the worktree.

Runnable leg 1, battery part `fast`:

```text
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part fast \
  --junitxml=<scratch>/xunit-architectural-fast.xml
```

Runnable leg 2, battery part `heavy`, shard `1/2` (label `1-of-2`):

```text
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part 1/2 \
  --junitxml=<scratch>/xunit-architectural-heavy-1-of-2.xml
```

Runnable leg 3, battery part `heavy`, shard `2/2` (label `2-of-2`):

```text
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural \
  -m "not performance and not stress and not timing" \
  -n 4 --dist loadfile \
  --deselect tests/architectural/test_no_legacy_terminology.py \
  --deselect tests/architectural/test_layer_rules.py \
  --deselect tests/architectural/test_pyproject_shape.py \
  --deselect tests/architectural/test_archive_root_byte_identical.py \
  -p scripts.ci.battery_partition_plugin --battery-part 2/2 \
  --junitxml=<scratch>/xunit-architectural-heavy-2-of-2.xml
```

The three legs are the complete `architectural-fast` plus `architectural-heavy` parts as CI runs them (the shards are disjoint by construction); the four deselected files run in their own CI jobs (`test_archive_root_byte_identical.py` in the `archive-freeze` job) or in the named gate lists above, not in these legs. **Run each leg from the lane workspace root** (the `-p scripts.ci.battery_partition_plugin` import fails from any other directory), **detached, with the output and the exit code written to scratch files, and polled in the foreground**: a heavy shard can run up to the CI budget of 30 minutes (`architectural-fast` 10), longer than a typical foreground command limit. Work-package implementers get no wake-up for background work, so never end the turn waiting for it. Recipe, per leg: launch it detached, e.g. `nohup sh -c '<the leg command>; echo $? > <scratch>/leg-N.exit' > <scratch>/leg-N.log 2>&1 &`, then poll in the foreground with bounded checks, each tool call under about 9 minutes, e.g. `for i in $(seq 1 16); do [ -f <scratch>/leg-N.exit ] && break; sleep 30; done; cat <scratch>/leg-N.exit 2>/dev/null || echo NOT-FINISHED`, repeating the call until the exit-code file exists. A missing exit-code file means not finished, never a pass; a tool timeout is neither a pass nor a fail. Do not hand off or request approval before all three exit-code files exist, and record each leg's exit code from them. Run them after the named gate files above are green and before the approval request, on the final commit of the work package.

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

Commits (hash and subject, in order, first commit marked as the red-first commit), the red evidence (failing ids, reason, how it was verified on the base), every command run with passed/failed counts, baseline bins, any refinement of a contract note or design decision, any friction observation (for `tracer-tooling-friction.md`), the output of the three architectural battery legs (command, passed, failed and skipped counts, exit status, junit path, bins against the WP01 main-CI record), the registration diffs and the registry gate files green on the module-creating commit, anything not done and why. The orchestrator records decisions and friction add-only; you do not write them under `kitty-specs/`.

## Definition of Done

- First commit: failing reader tests against a skeleton module, red on the planning base for per-test reasons (T023), carrying the registration pair; helper foundation lands before the reader.
- Artifact reader implements the single order of decision; listing and content run the same function; every refusal carries its code.
- Every fault-injection test has a positive fired counter; every named mutation is killed; reader-level planted pairs fail when redaction stops.
- Thin corpus smoke green, read-only fingerprint (bytes and directory names) equal before and after.
- One `--deselect` entry and one registry row exist (committed with the module-creating commit); all nine router and registry gate files, the eight architectural-fast files and the layer-rules files are green; ruff and TID251 clean.
- Hand-off report lists any refinement of the contract notes for the orchestrator to record.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Both architectural battery parts (`architectural-fast`, `architectural-heavy` shards `1/2` and `2/2`) were run as CI runs them and are green or binned, with the output recorded in the hand-off report (operator requirement, section Validation).
- Nothing pushed; no pull request; no tracker write.

## Risks

- Real-file fixtures and scratch HOME must satisfy the global-state and home-pin scans (`architectural-fast` runs on every PR): run the named files after the module exists.
- The one-line `packs.yml` command is a merge hazard: only this single-writer chain edits it.
- The independent oracle (WP08) will catch a wrong order of decision applied consistently in listing and content: keep the decision in one function but do not rely on `readable == (content read is 200)` as the oracle.
- Escape hazard: write NUL and backslash with `chr(0)` and `chr(92)`; at-sign names and credentials are built from fragments.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface (every file the change touches), plus the specific named architectural gate files it implicates; never a full sweep.

- Verify red then green: T023 tests fail on the planning base (each on its own assertion, against the skeleton) and pass on the final commit; apply a spot-revert of at least one rule per acceptance row (AC-LIST, AC-CONTENT) on a scratch copy and confirm the matching test fails.
- Re-run the three architectural battery legs or verify the recorded output (operator requirement, section Validation).
- Re-run the named gate files and the CI battery gate files; confirm the registration diffs are exactly one entry and one row and that they are in the first commit.
- Confirm no write mode reaches the file-system seam and `materialize` is never called; confirm no private import.
- Verify the first commit is the red-first commit and that it is red on the planning base; verify green on the final commit; check the baseline bins in the hand-off.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs plan steps W-1 to W-7 in this order: W-1 accept, then lane consolidation (`spec-kitty consolidate`, strategy `rebase` recommended), then registration and wiring check, scripted scope check and issue-matrix rows; W-2 JVM shake-out; W-3 dev-assist cleanup; W-4 aggregate adversarial squad (report-only, pre-rebase tree); W-5 history compaction; W-6 rebase onto upstream including the 1.0.0 release commit; W-7 final evidence. Only then is the draft pull request opened, and it needs the `contract-mission-status-v1.0.0` tag. Evidence recorded earlier is labelled pre-tag or pre-rebase. You do none of this.

## Implementation command

`spec-kitty agent action implement WP05 --agent claude`
