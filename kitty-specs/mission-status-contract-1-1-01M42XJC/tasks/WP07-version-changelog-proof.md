---
work_package_id: WP07
title: Version, CHANGELOG and the pure 1.1 proof module
dependencies:
- WP04
- WP06
requirement_refs:
- FR-017
- FR-018
- FR-019
- FR-020
- FR-024
- NFR-005
- NFR-006
- NFR-007
- C-001
- C-002
- C-004
- SC-001
- SC-002
- SC-007
- SC-008
planning_base_branch: issue-5625-mission-status-contract-1-1
merge_target_branch: issue-5625-mission-status-contract-1-1
branch_strategy: Planning artifacts for this mission were generated on issue-5625-mission-status-contract-1-1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5625-mission-status-contract-1-1 unless the human explicitly redirects the landing branch.
subtasks:
- T038
- T039
- T040
- T041
- T042
- T043
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- tests/contract/test_mission_status_contract_1_1.py
execution_mode: code_change
model: ''
owned_files:
- contracts/mission-status/CHANGELOG.md
- tests/contract/test_mission_status_contract_1_1.py
- .github/workflows/packs.yml
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP07 – Version, CHANGELOG and the pure 1.1 proof module

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Finalise the 1.1.0 CHANGELOG entry and write the pure 1.1 proof module (version, additive diff, bundle comparison, scope function with its allowed set as data, terminology scan, credential-kind and refusal-example tests, route coverage) with planted mutations, its registration pair and the pre-tag acceptance.

## Context

Plan IC-05, decisions D-P1, D-P10, D-P11; OD-1 X-pure (no live module: ACK-1 is void) and OD-3. Depends on WP04 (the provisional list is final) and, unconditionally, on WP06 (OD-1 X-pure: the registrations form one dependency chain WP05, WP06, WP07; the WP06 edge also keeps the lane graph acyclic, see plan section Lanes). **Registration timing (one rule):** the registration pair (T042) is committed WITH the module-creating red-first commit (T038), after WP06's pair, so no commit leaves the registry gates red. The comparison against the released tag runs once at wrap-up W-7 as a recorded command; no committed live test exists. The assertion that the tree's version is `1.1.0-SNAPSHOT` or `1.1.0` is slice-scoped and its docstring says so. Markers of the module: `contract`, `fast`, `corpus` (it reads no tag, no history, starts no subprocess). The tag matters only from wrap-up W-6; this WP uses the pure functions and the `--baseline-root` recipe.

Decisions honoured (spec.md, Decisions and Traceability; read `kitty-specs/mission-status-contract-1-1-01M42XJC/spec.md` with this prompt; the rows are `tasks.md`, section Coverage): CL-1, CL-2; AD-4, AD-7, AD-14, AD-16, AD-17, AD-18, AD-20, AD-21, AD-22; AC-VERSION; OQ-1; OD-1, OD-2.

Plan concern: IC-05 (plan section Implementation Concern Map). Requirement refs: FR-017, FR-018, FR-019, FR-020, FR-024, NFR-005, NFR-006, NFR-007, C-001, C-002, C-004, SC-001, SC-002, SC-007, SC-008. Dependencies: WP04, WP06. Branch contract: planning base and merge target are `issue-5625-mission-status-contract-1-1`; work runs in the lane workspace `spec-kitty agent action implement` resolves for you (never reconstruct a path by hand).

## Owned files (write scope)

Edit only these paths (declared shared-file exceptions are dependency chains, never concurrent; plan section Lanes):

- `contracts/mission-status/CHANGELOG.md`
- `tests/contract/test_mission_status_contract_1_1.py`
- `.github/workflows/packs.yml`
- `tests/architectural/test_ci_corpus_trigger_completeness.py`
- `tests/architectural/test_ci_corpus_trigger_completeness.py`

1 of these paths do not exist yet on the planning base and are declared in the frontmatter `create_intent` (finalisation refuses a literal path that matches zero files unless it is declared there); you create them.

Nothing under `kitty-specs/` is written by this work package: records you must make (a contract-note refinement, a decision, a friction observation, the baseline) go into your hand-off report; the orchestrator appends them add-only to the tracer files. A small, well-justified out-of-map edit is acceptable only with a one-line rationale in the hand-off report; the no-overlap rule is the real guard against collisions.

### Subtask T038: Red-first: the proof module with its failing entry-scoped and version assertions

**Purpose**: First commit: failing proof-module assertions.

**Steps**:

1. Create `tests/contract/test_mission_status_contract_1_1.py` with the entry-scoped CHANGELOG test of D-P11 (the `## 1.1.0*` entry has its five headings, the four gap names in `### Deferred to the next major version`, the two read behaviours under `Added`, the #5533 reference, no route-by-route table; every AD-14 element name and the names `provisional_check` reports sit inside the entry's own `### Provisional` section) and the slice-scoped version assertion. **Only the entry-scoped CHANGELOG assertions are red at this lane's start** (the Provisional and Deferred headings are not final yet). The version assertion is already green there (WP03 sets `1.1.0-SNAPSHOT` before this work package starts, in the same lane); it is a regression control, named as such in the commit message, like the three regression-control kinds of WP02.
2. Add the registration pair in the same commit (T042 lists the edits), so the registry gates are green on it and the CHANGELOG assertions are the only intended red.
3. Run on two trees and name which is which. On the **planning base** (the tree the red-first rule extracts with `git archive <base-commit>`), every assertion in the module is red, the version assertion included, because the planning base still carries the v1 version; this is the red evidence the reviewer extracts. On the **lane start** (the lane-a workspace HEAD at claim time: the tip of the preceding approved work package in lane-a, i.e. the WP06 tip, or the WP08 tip when WP08 is dispatched first; WP03 has set `1.1.0-SNAPSHOT` there, which is why the version assertion is green), only the CHANGELOG assertions are red and the version assertion is the green regression control. Record both runs; the reviewer checks the planning-base run by extraction and the control claim on the lane start. Commit before the CHANGELOG edit.

**Files**: `tests/contract/test_mission_status_contract_1_1.py` (new), `.github/workflows/packs.yml` and `tests/architectural/test_ci_corpus_trigger_completeness.py` (the registration pair, see T042).

**Validation**: Red recorded for the CHANGELOG assertions only, with the version assertion named as a green regression control; the nine router and registry gate files green on this commit.

### Subtask T039: Finalise the CHANGELOG entry: Provisional, Deferred, Added behaviours, the route-family reference

**Purpose**: The CHANGELOG entry, final.

**Steps**:

1. Run `provisional_check.py --root contracts` on the finished tree; the Provisional section names, as whole words, exactly what it reports (expected set: `reviewCycles`, `workspace`, `ReviewCycle`, `Workspace`, `ArtifactKind`, `truncated`, `redacted`, `code`, `ArtifactRefusalCode`, `WorkPackageDetailRefusalCode`, `ArtifactRefusal`, `WorkPackageDetailRefusal`, `kind`): the final list is the output, never a guess.
2. Add `### Deferred to the next major version` (the four v1 gaps with one line of reason each: per-Mission staleness on `MissionOverview`, an actor on `WorkPackageSummary`, the project branch, the lane weights behind `weightedPercentage`; each would add a property to an existing response, which the breaking-change check treats as breaking); `### Added` carries a one-line reference to #5533 naming the five route families covered and stating that the dossier overview and the snapshot export are not covered; no route-by-route table (FR-024).
3. `structure_check.py` and `provisional_check.py` pass (they are file-wide: the entry-scoped test closes the gap, research R-1).

**Files**: `contracts/mission-status/CHANGELOG.md` (about 60 lines).

**Validation**: T038 CHANGELOG test green; `structure_check.py`, `provisional_check.py`, `citation_check.py` exit 0.

### Subtask T040: minor_proof_problems: byte identity, bundle comparison, next-minor version, planted mutations

**Purpose**: The minor-version proof as a pure function with planted mutations.

**Steps**:

1. `minor_proof_problems(baseline_root, candidate_root)`: (a) every baseline file of the module and `_shared` is byte-identical in the candidate except the allowed set (`openapi.yaml`, the four `_index.yaml` files, `CHANGELOG.md`); (b) the candidate bundle tree minus the new path keys, with `info.version` set to the baseline's, equals the baseline tree (compared through `contract_resolver.resolve`); (c) the candidate version is the next minor of the baseline (`1.1.0` or `1.1.0-SNAPSHOT` for a `1.0.x` baseline).
2. Planted mutations on scratch copies: a byte change to an existing schema fails (a); a `409` added to an existing operation fails (b); `1.0.1` and `2.0.0` fail (c); exactly `1.1.0` passes. Two bundle builds are byte-identical (NFR-005).
3. The committed test cannot run `oasdiff` (not installed in the tool job); `breaking_check.py` runs in the Contracts workflow and as PR-time evidence (T043).

**Files**: `tests/contract/test_mission_status_contract_1_1.py` (about 450 lines at this step).

**Validation**: Proof tests and mutations green; zero cases built fails loudly. Revert check: each planted mutation test must fail when the corresponding rule of `minor_proof_problems` ((a), (b) or (c)) is removed from the function; show it on a scratch copy and record one line per rule in the hand-off report.

### Subtask T041: scope_problems with its allowed set as data, terminology scan, credential-kind and refusal-example tests

**Purpose**: The scope function, allowed set as data, and the remaining proofs.

**Steps**:

1. `scope_problems(changes, allowed)` over name-status entries `(status, path)` from `git diff --name-status --no-renames` (a rename is a delete plus an add). `SLICE_ALLOWED` is a list of rules `(match, path, statuses)`: prefix `contracts/mission-status/` admits `A` only; the exact existing files of items 2 and 3 (`openapi.yaml`, the four `_index.yaml` files, `CHANGELOG.md`; `leak_scan.py`, `fixture_builder.py`, `negative_cases.json`, `enum_pins.json`) admit `M` only; prefix `tests/contract/` admits `A` and `M`; no rule admits `D`. `EXTRA_ALLOWED_REGISTRATIONS` names exactly `.github/workflows/packs.yml` and `tests/architectural/test_ci_corpus_trigger_completeness.py`, each `M` only, no wildcard. There is no constant for `required_examples.json`: OD-2 is decided as Y (the example-required guard lives in-test), so that path is not in any allowed set.
2. Planted negatives: a path in neither set (under `src/`, under `docs/`), an `M` entry under `contracts/mission-status/`, an `M` entry for a `contracts/tools/` file that is not one of the four, a `D` entry for a named file, and a case proving that the two registration paths are rejected when `EXTRA_ALLOWED_REGISTRATIONS` is not supplied. The scope function is NOT committed as a test over the live branch diff (it would measure `main` against itself after merge); wrap-up W-1 and W-7 run it over the real diff (quickstart).
3. Terminology scan over the whole module skipping `x-source` and `x-derived` values (zero hits today; a planted "feature" fails, `feature_dir` in a citation passes); credential-kind descriptions compared with `SECRET_PATTERNS` (FR-019); refusal examples satisfy the code-to-status pairing; example-required cases hold; route coverage: grep for the five route families and the two exclusions, no mapping table (FR-024).

**Files**: `tests/contract/test_mission_status_contract_1_1.py` (grows to about 900 lines).

**Validation**: All proof tests green; mutations killed (`the mutation was not killed: <name>`). Revert check: each planted negative of `scope_problems` must fail when its rule is removed (the `M` under the new-files prefix, the unnamed tools file, the `D`, the path in neither set); show it on a scratch copy, one line per rule in the hand-off report.

### Subtask T042: Registration pair for the proof module and its marker set

**Purpose**: Registration pair for the proof module. It is committed with the module-creating red-first commit (T038), not after it; this subtask defines the edits and records the gate results.

**Steps**:

1. `.github/workflows/packs.yml`: one `--deselect tests/contract/test_mission_status_contract_1_1.py` in sorted position of the one-line command; `_CORPUS_MARKED_MODULES`: one row; written after WP06's pair (single-writer chain), in the T038 commit.
2. Run the nine router and registry gate files (green on the T038 commit and at the end) and `--collect-only -q -m "corpus and not windows_ci"` over the module.

**Files**: `.github/workflows/packs.yml`, `tests/architectural/test_ci_corpus_trigger_completeness.py`.

**Validation**: Gate files green.

### Subtask T043: Pre-tag acceptance: pure module green, --baseline-root recipe, shallow-clone run

**Purpose**: Pre-tag acceptance (labelled pre-tag and pre-rebase evidence).

**Steps**:

1. Run the pure module green; run the `--baseline-root` recipe of quickstart section The minor-version proof (extract the baseline to `<scratch>/baseline`, fetch the pinned `oasdiff` with `install_tools.py --only oasdiff` into a scratch directory, run `breaking_check.py --root contracts --baseline-root <scratch>/baseline`: expected exit 0 and `breaking=0`), and the byte-identity `diff -rq` pair.
2. Run the pure modules in a `git clone --depth 1` scratch clone (green; no tag needed).
3. Report every command with counts, labelled pre-tag and pre-rebase (WP09 and the orchestrator carry them to the PR body; only the W-7 output is final evidence). Report the `oasdiff` fetch outcome honestly; if it cannot be fetched say so (never fabricate a result).

**Files**: None.

**Validation**: Recorded in the hand-off report.

## Validation: gates and targeted test surface

Charter: no full `tests/architectural/`, end-to-end, performance or `make test-full` sweep in mission work (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run exactly the commands below, record each command and its passed/failed counts in the hand-off report. Use the checkout's own environment (`.venv/bin/...`), never a bare `uv run`. `<scratch>` means a scratch directory outside the repository.

**Targeted test surface of this work package**:

- The ten Python checks of quickstart section Python checks over the final tree.
- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_contract_1_1.py tests/contract/test_mission_status_examples.py tests/contract/test_enum_pin_check.py`
- `.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_mission_status_contract_1_1.py`

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

- First commit: failing entry-scoped CHANGELOG assertions (T038), red on the planning base (all assertions) and, at the lane start, red for the CHANGELOG assertions only with the version assertion a named green regression control, the registration pair included.
- CHANGELOG entry final: five headings, provisional list equal to `provisional_check` output, four deferred gaps, #5533 reference naming five families and two exclusions.
- `minor_proof_problems` and `scope_problems` proven with every listed mutation killed and the per-rule revert check recorded; allowed data carries statuses; `EXTRA_ALLOWED_REGISTRATIONS` is data, no wildcard.
- No committed live baseline test and no test over the live diff.
- Registration pair added after WP06's, in the module-creating commit; gate files green; ruff and TID251 clean; pre-tag acceptance recorded and labelled.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Both architectural battery parts (`architectural-fast`, `architectural-heavy` shards `1/2` and `2/2`) were run as CI runs them and are green or binned, with the output recorded in the hand-off report (operator requirement, section Validation).
- Nothing pushed; no pull request; no tracker write.

## Risks

- `provisional_check` and `structure_check` are file-wide (friction F-4, F-5): the entry-scoped test is the real guard.
- A scope check over HEAD before lane consolidation sees only the Mission directory: it first runs at wrap-up W-1 (iii).
- The tag does not exist yet: nothing in this WP may read it; use `--baseline-root`.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface (every file the change touches), plus the specific named architectural gate files it implicates; never a full sweep.

- Verify red then green for T038 (CHANGELOG assertions red, version assertion a green regression control); verify each planted mutation fails the target test and apply one revert per rule of `minor_proof_problems` and `scope_problems` on a scratch copy.
- Re-run the three architectural battery legs or verify the recorded output (operator requirement, section Validation).
- Check the CHANGELOG provisional list against a fresh `provisional_check` run; check no route table.
- Check the scope rules carry statuses (an `M` under the new-files prefix is reported, no rule admits `D`).
- Re-run the named and CI-battery gate files; confirm the registration pair is in the first commit.
- Verify the first commit is the red-first commit and that it is red on the planning base; verify green on the final commit; check the baseline bins in the hand-off.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs plan steps W-1 to W-7 in this order: W-1 accept, then lane consolidation (`spec-kitty consolidate`, strategy `rebase` recommended), then registration and wiring check, scripted scope check and issue-matrix rows; W-2 JVM shake-out; W-3 dev-assist cleanup; W-4 aggregate adversarial squad (report-only, pre-rebase tree); W-5 history compaction; W-6 rebase onto upstream including the 1.0.0 release commit; W-7 final evidence. Only then is the draft pull request opened, and it needs the `contract-mission-status-v1.0.0` tag. Evidence recorded earlier is labelled pre-tag or pre-rebase. You do none of this.

## Implementation command

`spec-kitty agent action implement WP07 --agent claude`
