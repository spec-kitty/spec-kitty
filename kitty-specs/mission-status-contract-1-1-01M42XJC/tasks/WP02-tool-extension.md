---
work_package_id: WP02
title: 'Tool extension: strict names, artifact-path class, 25 planted kinds'
dependencies: []
requirement_refs:
- FR-015
- FR-023
- NFR-004
- C-004
- C-005
planning_base_branch: issue-5625-mission-status-contract-1-1
merge_target_branch: issue-5625-mission-status-contract-1-1
branch_strategy: Planning artifacts for this mission were generated on issue-5625-mission-status-contract-1-1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5625-mission-status-contract-1-1 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-contract-1-1-01M42XJC
base_commit: aef7cc96777272e8d85c1608345ee56d1bbe8ce7
created_at: '2026-10-04T12:44:13.069460+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
history: []
agent_profile: python-pedro
authoritative_surface: contracts/tools/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- contracts/tools/fixture_builder.py
- contracts/tools/leak_scan.py
- contracts/tools/negative_cases.json
- tests/contract/test_leak_scan.py
- tests/contract/test_fixture_builder.py
- tests/contract/test_run_negative_cases.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – Tool extension: strict names, artifact-path class, 25 planted kinds

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Extend the three contract-tooling files of FR-015 that this work package owns (`fixture_builder.py`, `leak_scan.py`, `negative_cases.json`) and their three test modules (the fourth file of FR-015, `enum_pins.json`, is written by WP03 and WP04) so the new fields get a leak class and the new artifact-path rule has a scanner, a shared predicate and 25 planted kinds.

## Context

Plan IC-02, decisions D-P7 and OD-4 (operator-decided: scope the raw-text pass), contracts note `kitty-specs/mission-status-contract-1-1-01M42XJC/contracts/tool-extension-and-reader.md` section A. This WP runs concurrently with WP01 and owns six files no other work package owns, so it is a computed lane of its own; WP03 depends on it (the extended scan must meet every new contract file as it is written) and WP05 reaches `malformed_artifact_path` through the dependency-lane merge. Chokepoint: `negative_cases.json` and `fixture_builder.py` have this one writer. Hazards: the Unicode-escape hazard (quickstart, last section) and the plant-shape change that moves three test modules.

Decisions honoured (spec.md, Decisions and Traceability; read `kitty-specs/mission-status-contract-1-1-01M42XJC/spec.md` with this prompt; the rows are `tasks.md`, section Coverage): CL-1, CL-2, CL-3, CL-4, CL-5; AD-10, AD-15, AD-17, AD-18, AD-19; OD-4.

Plan concern: IC-02 (plan section Implementation Concern Map). Requirement refs: FR-015, FR-023, NFR-004, C-004, C-005. Dependencies: none. Branch contract: planning base and merge target are `issue-5625-mission-status-contract-1-1`; work runs in the lane workspace `spec-kitty agent action implement` resolves for you (never reconstruct a path by hand).

## Owned files (write scope)

Edit only these paths (declared shared-file exceptions are dependency chains, never concurrent; plan section Lanes):

- `contracts/tools/fixture_builder.py`
- `contracts/tools/leak_scan.py`
- `contracts/tools/negative_cases.json`
- `tests/contract/test_leak_scan.py`
- `tests/contract/test_fixture_builder.py`
- `tests/contract/test_run_negative_cases.py`

Nothing under `kitty-specs/` is written by this work package: records you must make (a contract-note refinement, a decision, a friction observation, the baseline) go into your hand-off report; the orchestrator appends them add-only to the tracer files. A small, well-justified out-of-map edit is acceptable only with a one-line rationale in the hand-off report; the no-overlap rule is the real guard against collisions.

### Subtask T005: Pin the byte digests of the eight existing planted kinds from the unmodified builder

**Purpose**: Pin the starting behaviour of the eight existing planted kinds so the Plant-shape change cannot move them.

**Steps**:

1. Before editing the builder, build each of the eight existing kinds with the unmodified `fixture_builder.build` into a scratch directory and hash the two files of each (planted, control) with `blake2b` (`hashlib.sha256` is banned by TID251).
2. Pin those digests in `tests/contract/test_fixture_builder.py` as a test that the eight old kinds still build byte-identically. This test passes before and after the edit by design; it is NOT claimed as red-first (plan Charter Check).
3. Record the digest source in the hand-off report (the commit of the unmodified builder).

**Files**: `tests/contract/test_fixture_builder.py` (about 30 lines).

**Validation**: The new test passes on the unmodified builder.

### Subtask T006: Red-first tests: kinds set, predicate three-way agreement, artifact-path class, masked text pass

**Purpose**: The first red commit: tests that fail on the planning base.

**Steps**:

1. Commit first (before any implementation): `test_fixture_builder.py` expects the exact `KINDS` set of 33 kinds (the eight existing plus 25: ten `strict-*`, twelve `artifact-path-*`, three content and title regression controls); `test_leak_scan.py` expects `malformed_artifact_path(path) -> str | None` with the eleven stable reasons, the agreement of the function with a literal restatement of the spec predicate in the test over a table of 30 cases (the third leg, the `ArtifactPath` schema pattern, joins in WP03 when the schema exists), the `ARTIFACT_PATH_MALFORMED` finding code, `values_artifact_path=N` after `values_all=N` on the last line, and the OD-4 mask tests: a flow-mapping line holding an at-sign `path` and a `title` with an address reports the title and not the path; an `x-source` path holding an address is reported; a token in a path value is still reported (`SECRET` is never blanked); a contract example holding an at-sign path passes the whole scan; JSON files and unparseable YAML are scanned unmasked.
2. Every leaking value in these tests is assembled from fragments at run time (never a literal host path, address or token; the at-sign file name is built from fragments, never typed). Use `chr(0)` for NUL and `chr(92)` for backslash.
3. Run the new tests against the planning base: they must fail for the stated reason (record the failing ids). The three regression-control kinds are the declared exception: they pass on the base.

**Files**: `tests/contract/test_leak_scan.py` (about 250 lines), `tests/contract/test_fixture_builder.py` (about 120 lines).

**Validation**: Failing tests committed first, red for the stated reasons on the planning base.

### Subtask T007: fixture_builder.py: ten strict names, the Plant shape, 25 kinds (22 red-first, 3 controls)

**Purpose**: Make the builder able to plant nested fragments with per-kind controls.

**Steps**:

1. `STRICT_FIELDS` gains `id`, `laneId`, `laneBranch`, `planningBranch`, `pattern`, `feedbackReference`, `reviewer`, `kind`, `mediaType`, `changeState`; `title` stays out.
2. Plant shape: `_plant(kind)` returns `Plant(fragment, control_fragment, field, codes)`; `build` deep-merges fragments (mappings merge recursively, lists are replaced); `BuiltFixture` keeps its four fields; `run_negative_cases.build_leak` stays unchanged by design.
3. Add the 25 kinds exactly as the contract note table lists them; every control of an artifact-path kind carries the legitimate odd names (a `home/<x>/` segment, a space, an accented letter, and the at-sign name built at run time; OD-4 is decided: scoped text pass).
4. Rewrite the module docstring for the new kinds.

**Files**: `contracts/tools/fixture_builder.py` (about 220 lines added).

**Validation**: `test_fixture_builder.py` green; the T005 digest test still green.

### Subtask T008: leak_scan.py: ARTIFACT_PATH_KEYS class, malformed_artifact_path, OD-4 masked text pass, summary line

**Purpose**: Teach the scanner the artifact-path class and the masked raw-text pass.

**Steps**:

1. `ARTIFACT_PATH_KEYS = frozenset({"path", "artifactPath"})`; in `_Scanner.walk` a string under one of those keys, with no `x-source` or `x-derived` ancestor, is judged by `malformed_artifact_path` instead of the structured-pass host-path and e-mail patterns (AD-19).
2. `malformed_artifact_path(path)` is the one definition of the predicate on the tooling side (reasons: empty, too_long, absolute, tilde, drive_letter, backslash, nul, empty_segment, trailing_slash, dot_segment, dotdot_segment). It lives in `leak_scan.py` (not `leak_patterns.py`, outside the slice file set).
3. OD-4 (decided: the scoped text pass): `scan_text` takes a second argument, the text with artifact-path value spans blanked: `artifact_path_spans(text)` composes the YAML (`yaml.compose`, scalar start and end indexes) and returns the spans of scalar values of a key in `ARTIFACT_PATH_KEYS` reached without an `x-source` or `x-derived` key; `mask_spans` blanks them keeping newlines. Host-path and e-mail findings come from the blanked text, `SECRET` from the original line.
4. New finding code `ARTIFACT_PATH_MALFORMED`; the last output line gains `values_artifact_path=N`; update the module docstring (it no longer says "nothing is exempt" and names the masked span). About 45 added lines for the mask (research R-14).

**Files**: `contracts/tools/leak_scan.py` (about 90 lines added or changed).

**Validation**: `test_leak_scan.py` green; `leak_scan.py --root contracts` exits 0 over the existing tree.

### Subtask T009: negative_cases.json: one case per new kind, and the manifest-length test

**Purpose**: Register the 25 planted kinds for the Contracts workflow.

**Steps**:

1. Append in one block to `contracts/tools/negative_cases.json` one case per new kind in the stated shape (`{"id": "leak-scan-<kind>", "tool": "leak_scan.py", "build": "leak:<kind>", "plant": {"args": ["--root", "{root}"], "code": <code>}, "control": {"args": ["--root", "{root}"]}}`); about 575 lines. No new file under `contracts/tools/fixtures/`.
2. `tests/contract/test_run_negative_cases.py` moves only through the manifest length (101 cases to 126; the planting counts of the run).

**Files**: `contracts/tools/negative_cases.json` (about 575 lines), `tests/contract/test_run_negative_cases.py` (a few lines).

**Validation**: `run_negative_cases.py --manifest contracts/tools/negative_cases.json --work <scratch> --exclude-tag jvm --exclude-tag vacuum --exclude-tag oasdiff` passes (68 ran at planning; the new cases ran too).

### Subtask T010: Acceptance runs: existing contract still clean, old kinds byte-identical, gate files

**Purpose**: Close the concern's named acceptance.

**Steps**:

1. `leak_scan.py --root contracts` exits 0 over the existing tree; the eight old kinds build byte-identically; the architectural-fast files named below run green after the test edits.
2. Run the targeted tests: `test_leak_scan.py`, `test_fixture_builder.py`, `test_run_negative_cases.py`, `test_enum_pin_check.py` (unchanged by this WP, as a neighbour).
3. Check the new files for raw NUL bytes (`grep -c -P '\x00'` over each changed file).

**Files**: None.

**Validation**: All named commands exit 0; hand-off report lists them with counts.

## Validation: gates and targeted test surface

Charter: no full `tests/architectural/`, end-to-end, performance or `make test-full` sweep in mission work (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run exactly the commands below, record each command and its passed/failed counts in the hand-off report. Use the checkout's own environment (`.venv/bin/...`), never a bare `uv run`. `<scratch>` means a scratch directory outside the repository.

**Targeted test surface of this work package**:

- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_leak_scan.py tests/contract/test_fixture_builder.py tests/contract/test_run_negative_cases.py tests/contract/test_enum_pin_check.py`
- `.venv/bin/python contracts/tools/leak_scan.py --root contracts` (exit 0)
- `.venv/bin/python contracts/tools/run_negative_cases.py --manifest contracts/tools/negative_cases.json --work <scratch> --exclude-tag jvm --exclude-tag vacuum --exclude-tag oasdiff`

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

**Comparison base.** WP02 runs beside WP01 and its lane forks from the planning-base commit itself, so your own pre-change run is the Mission baseline for your commands. Record the planning-base commit hash and the counts in the hand-off report, and reconcile them with the WP01 table once the orchestrator has appended it to `tracer-approach.md`.

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

- First commit: the failing tests (T006), red on the planning base for the stated reasons; the digest test (T005) is separate and passes by design.
- 25 kinds registered, 22 red-first and 3 regression controls, each next to a clean control; KINDS has 33 entries.
- `leak_scan.py --root contracts` exits 0 over the existing tree; the eight old kinds are byte-identical.
- OD-4 (decided: scoped text pass) masked text pass delivered with its bounded-mask tests; `SECRET` never blanked.
- Only the six owned files changed; no leaking literal anywhere.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- Editing tools decode unicode escapes: use `chr(0)` and `chr(92)` in tests, the hex escape in contract patterns, and check for NUL bytes.
- A mask that is too wide blinds the human scan: the three regression controls and the bounded-mask tests guard it.
- The plant-shape change breaks `run_negative_cases.build_leak`: it is unchanged by design, verify it still unlinks only the planted file.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface (every file the change touches), plus the specific named architectural gate files it implicates; never a full sweep.

- Success criterion SC-005 (a planted negative that fails and a clean control for each endpoint) is built here by the 25 planted kinds and their controls; WP08 and WP09 only re-measure and record it. Verify it is met by this work package's tests.
- Verify red then green: the T006 tests fail on the planning base and pass on the final commit; the three regression controls are named exceptions.
- Check the old-kind digests were pinned from the unmodified builder, not from the edited one.
- Confirm `malformed_artifact_path` is the single predicate and is not duplicated; `leak_patterns.py` is untouched.
- Run the named architectural-fast files and `--collect-only` is not needed here (no new test module).
- Verify the first commit is the red-first commit and that it is red on the planning base; verify green on the final commit; check the baseline bins in the hand-off.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs plan steps W-1 to W-7 in this order: W-1 accept, then lane consolidation (`spec-kitty consolidate`, strategy `rebase` recommended), then registration and wiring check, scripted scope check and issue-matrix rows; W-2 JVM shake-out; W-3 dev-assist cleanup; W-4 aggregate adversarial squad (report-only, pre-rebase tree); W-5 history compaction; W-6 rebase onto upstream including the 1.0.0 release commit; W-7 final evidence. Only then is the draft pull request opened, and it needs the `contract-mission-status-v1.0.0` tag. Evidence recorded earlier is labelled pre-tag or pre-rebase. You do none of this.

## Implementation command

`spec-kitty agent action implement WP02 --agent claude`
