---
work_package_id: WP06
title: Detail reader, matcher parity and the git change-state matrix
dependencies:
- WP04
- WP05
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-016
- FR-020
- FR-022
- NFR-002
- NFR-005
- NFR-006
- NFR-007
- C-004
- C-005
planning_base_branch: issue-5625-mission-status-contract-1-1
merge_target_branch: issue-5625-mission-status-contract-1-1
branch_strategy: Planning artifacts for this mission were generated on issue-5625-mission-status-contract-1-1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5625-mission-status-contract-1-1 unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
- T034
- T035
- T036
- T037
history: []
agent_profile: python-pedro
authoritative_surface: tests/contract/
create_intent:
- tests/contract/_mission_status_detail.py
- tests/contract/test_mission_status_detail.py
execution_mode: code_change
model: ''
owned_files:
- tests/contract/_mission_status_detail.py
- tests/contract/test_mission_status_detail.py
- tests/contract/test_mission_status_reality.py
- .github/workflows/packs.yml
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP06 – Detail reader, matcher parity and the git change-state matrix

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Write the detail reader (work package universe and file identity, subtask titles, dependencies, review cycles, workspace, owned files with the git change-state matrix, artifact references), the matcher parity test, its full test module and the registration pair.

## Context

Plan IC-07, decisions D-P3, D-P4, D-P6, D-P8, D-P9, OD-3; data model sections Detail field sources and `changeState` derivation (`kitty-specs/mission-status-contract-1-1-01M42XJC/data-model.md`). Depends on WP05 (helper foundation and the artifact reader's eligibility) and WP04 (the detail schemas). **Not concurrent** with WP05 or WP08 (shared files, one lane). Second writer of the packs.yml and registry chain. **Registration timing (one rule):** the registration pair (T037) is committed WITH the module-creating red-first commit (T031), so no commit leaves the registry gates red; the failing detail tests are the only intended red. **Review slices:** one commit per subtask, subject naming the subtask; the seams are T030 to T033 (pure file reading: universe, titles, dependencies, cycles, workspace, references) versus T034 to T037 (matcher parity, change states over real git, assembled outcome, git matrix). Markers: `contract`, `corpus` and `git_repo`, NOT `fast` (it drives real git; `pytest.ini` defines `fast` as pure logic with no subprocess or git), so the nightly `fast or unit` run does not select it. Accepted residual (D-P4): `get_current_branch` and `git_merge_base` have no timeout and cannot get one without a `src/` change (NFR-007).

Decisions honoured (spec.md, Decisions and Traceability; read `kitty-specs/mission-status-contract-1-1-01M42XJC/spec.md` with this prompt; the rows are `tasks.md`, section Coverage): CL-1, CL-2, CL-4, CL-5; AD-1, AD-2, AD-3, AD-4, AD-7, AD-8, AD-12, AD-13, AD-14, AD-15, AD-17, AD-18, AD-20, AD-21, AD-22; AC-DETAIL; OQ-2; OD-1, OD-3.

Plan concern: IC-07 (plan section Implementation Concern Map). Requirement refs: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-016, FR-020, FR-022, NFR-002, NFR-005, NFR-006, NFR-007, C-004, C-005. Dependencies: WP04, WP05. Branch contract: planning base and merge target are `issue-5625-mission-status-contract-1-1`; work runs in the lane workspace `spec-kitty agent action implement` resolves for you (never reconstruct a path by hand).

## Owned files (write scope)

Edit only these paths (declared shared-file exceptions are dependency chains, never concurrent; plan section Lanes):

- `tests/contract/_mission_status_detail.py`
- `tests/contract/test_mission_status_detail.py`
- `tests/contract/test_mission_status_reality.py`
- `.github/workflows/packs.yml`
- `tests/architectural/test_ci_corpus_trigger_completeness.py`

2 of these paths do not exist yet on the planning base and are declared in the frontmatter `create_intent` (finalisation refuses a literal path that matches zero files unless it is declared there); you create them.

Nothing under `kitty-specs/` is written by this work package: records you must make (a contract-note refinement, a decision, a friction observation, the baseline) go into your hand-off report; the orchestrator appends them add-only to the tracer files. A small, well-justified out-of-map edit is acceptable only with a one-line rationale in the hand-off report; the no-overlap rule is the real guard against collisions.

### Subtask T030: First task: re-run the matcher import and the 19-case parity table in the tool-job environment

**Purpose**: D-P3 environment proof, before any other detail code.

**Steps**:

1. In a scratch checkout built the way the tool job builds it (`uv sync --frozen --no-install-project`; the project is not installed, `pytest.ini` `pythonpath = src` makes the private functions importable) import `specify_cli.cli.commands.agent.tasks_move_task` (`_mt_matches_owned_file`) and `specify_cli.policy.commit_guard` (`_matches_any_glob`) and run the 19-case FR-022 glob table (17 agree, 2 known path-normalisation divergences).
2. If the import ever fails there: fall back to a source pin (a `blake2b` digest of the normalised syntax-tree dump of each of the two function bodies, failing when either changes) plus the existing compat-surface test; record the decision in the hand-off report (the orchestrator appends it to `tracer-design-decisions.md`).

**Files**: None (scratch only).

**Validation**: Import and table result recorded in the hand-off report.

### Subtask T031: Red-first: failing detail tests (work package identity cases) and the thin corpus smoke

**Purpose**: First commit: failing detail tests, red on the planning base.

**Steps**:

1. Create `tests/contract/test_mission_status_detail.py` with the work package identity cases of D-P6 (an id held by two files: the first regular file in byte order is the authored file, OD-3; a symlinked work package file is skipped and the id is 404 when no other file holds it; a file whose name prefix and frontmatter id disagree is keyed by the frontmatter id; `WP-notes.md` carrying a valid id is a work package with `prompt: null`; a directory named `WP01.md` is skipped, never an `OSError` escaping) plus the thin corpus smoke in `test_mission_status_reality.py` (examined equals the independent count of distinct ids and both are greater than zero, empty skip list, no thresholds: a zero guard is not a threshold).
2. Create a skeleton `tests/contract/_mission_status_detail.py` in the same commit (the public functions exist but raise `NotImplementedError` or return empty results), so each test fails on its own assertion and never as one collection error; record the per-test failure messages.
3. Add the registration pair in the same commit (T037 lists the edits), so the registry gates are green on it.
4. Run against the planning base (extract the base, copy the new test file and the skeleton in): the detail tests fail on their assertions. Commit before any implementation.

**Files**: `tests/contract/test_mission_status_detail.py` (new), `tests/contract/_mission_status_detail.py` (new, skeleton), `tests/contract/test_mission_status_reality.py`, `.github/workflows/packs.yml` and `tests/architectural/test_ci_corpus_trigger_completeness.py` (the registration pair, see T037).

**Validation**: Red on the planning base for the stated per-test reasons, recorded; the nine router and registry gate files green on this commit.

### Subtask T032: Detail core: host capability, work package universe, subtask titles, dependency references

**Purpose**: Detail core: capability, universe, titles, dependencies.

**Steps**:

1. New `tests/contract/_mission_status_detail.py`: `HostCapability(git, worktrees)` (two booleans, explicit, never discovered) and `NO_WORKTREES`; `work_package_universe` (distinct valid `work_package_id` values of the files `wp_task_files` selects after skipping a file raising `FrontmatterError` or a pydantic `ValidationError` or without a valid id, as bootstrap does; skip symlinks and directories like unparseable files; independent scan counts them).
2. `subtask_titles` (both `tasks.md` row formats, `[P]`, bold, empty, missing, duplicate, undecodable gives 500 `source_unreadable`, null state, credential gives `null` title) and `dependency_refs` (title, lane, dangling, no events, whitespace title falls back to the id, credential gives the id).
3. Authored file versus prompt file (D-P6): the authored file supplies frontmatter, titles source and owned files; the prompt file is the spec's name-keyed definition (first qualifying regular non-symlink `tasks/WP[0-9]{2,}-*.md`, byte order) and alone feeds `artifactReferences.prompt` and the `tasks/<wp-slug>/` cycle directory.

**Files**: `tests/contract/_mission_status_detail.py` (new, about 350 lines at this step).

**Validation**: T031 identity tests and the subtask and dependency tests green.

### Subtask T033: Review cycles, workspace and the artifact references of a work package

**Purpose**: Review cycles, workspace and artifact references.

**Steps**:

1. `review_cycles`: cycle files from the primary planning surface (`own_dir`), order, verdict by pointer through `build_review_cycle_pointer` and `validate_review_cycle_pointer` on every value, last wins, renamed Mission, approval reference, unparseable cycle files give null members (AD-13), `review-cycle-0.md`, two prompts, date-only and offset `reviewedAt`; the absolute `feedback_path` event pair; a cycle held only on a coordination surface is not shown (AD-18), a stranded primary record is (SK-348).
2. `workspace_of`: lane matrix (`lanes.json` through `read_lanes_json`, `lane_branch_name`, `lane-planning` is never `worktreePresent`, no `lanes.json`, no lane for the work package, malformed `lanes.json` gives 500 `source_unreadable`); status lanes and verdicts from `read_dir` through `reconstruct_wp_view` (D-P9).
3. Artifact references use the WP05 eligibility function; never build the listing; open no content (a directory read and lstats only; NFR-002).

**Files**: `tests/contract/_mission_status_detail.py` (grows to about 600 lines).

**Validation**: Cycle, workspace and reference tests green.

### Subtask T034: Owned-files matcher, parity test and the change-state derivation over the public git seam

**Purpose**: Matcher, parity test and change-state derivation over the public git seam.

**Steps**:

1. `matches_owned_file(path, pattern)` reproduced once (D-P3): normalise the path as `_mt_matches_owned_file` does (`\` to `/`, strip a leading `./`), `fnmatch.fnmatch` (not `fnmatchcase`), the wildcard-stripped prefix rule, the pattern as authored, a pattern holding `{` is `unknown`. Parity test imports both private copies (the only private names in the test tree) and compares per pattern over every FR-022 glob case and four normalisation cases, wrapping the single pattern as `(pattern,)` for the first and `[pattern]` for the second, with the two known divergences pinned.
2. `change_states` per D-P4: determined only when `host.git` and `host.worktrees` are true, a code lane, `worktreePresent`, `get_current_branch(worktree)` equals `laneBranch`, and `target_branch` passes the strict branch pattern and does not start with `-`; composes `git_merge_base` and `kernel.git.changed_paths(worktree, merge_base, "HEAD", renames=False, timeout=<30 s constant>)`, converts `GitPath` with `as_posix()`; `GitCommandError` and `ValueError` make every entry `unknown`; `OSError`, `subprocess.SubprocessError` and `ValueError` from `get_current_branch` and `git_merge_base` each make every entry `unknown`. No `src/` change.

**Files**: `tests/contract/_mission_status_detail.py` (grows to about 800 lines).

**Validation**: Parity test and change-state tests green.

### Subtask T035: build_work_package_detail: outcome, leak withholding, determinism, absence and unreadable cases

**Purpose**: `build_work_package_detail`: the assembled outcome.

**Steps**:

1. `build_work_package_detail(...)` returns `DetailOutcome(status, body)`: 404 `not_found` for an unknown work package, 500 `source_unreadable` for unreadable sources (never raises for a refusal); leak withholding by field class (a title holding a credential is withheld: subtask title `null`, dependency title the id); two builds byte-identical; with and without a coordination worktree.
2. Invariants asserted on every detail built: `changeState` is `changed` or `unchanged` only when `worktreePresent`; `worktreePresent` only when the workspace does not run in the repository root checkout; in the corpus every `changeState` is `unknown` and every `worktreePresent` is `false` (host `NO_WORKTREES`).

**Files**: `tests/contract/_mission_status_detail.py` (final, about 900 lines).

**Validation**: Detail tests green; reader-level planted pair: `payload_leaks` over a built detail whose subtask or dependency title holds a credential reports `SECRET` (fails if withholding stops), clean twin passes.

### Subtask T036: Test matrix: workspace, real-git change states, fault injection, killed mutations

**Purpose**: The full test matrix with real git, fault injection and killed mutations.

**Steps**:

1. Workspace matrix on real lane worktrees, `lane-planning` (the test fails if `worktreePresent` is true), no `lanes.json`, no lane, malformed `lanes.json` (500); every glob and state case of FR-022 through the reader and both private copies; end-to-end `changed` and `unchanged` through the REAL `kernel.git` seam on real repositories (not through strings).
2. A monkeypatched parse failure and a crafted refused path each give `unknown`. Fault injection, each with a positive fired counter and a "remove the guard" mutation that must be killed: `get_current_branch` raising `PermissionError`, `git_merge_base` raising `NotADirectoryError`, `git_merge_base` raising `FileNotFoundError` (worktree directory removed after the exists check), `changed_paths` raising `GitCommandError` with a timeout cause. A manifest holding an option-like `target_branch` gives `unknown` with no git invocation observed through the counting seam.
3. Mutations killed (failure text `the mutation was not killed: <name>`): every listed mutation of the matcher and of the derivation. Subtask, dependency, cycle, artifact-link cases with the counting `FileSystem` asserting no listing walk and no content open; 1,001-file and symlink fixtures.
4. Real git setup uses `git_init` and `commit_all` from the helper, a scratch HOME and `monkeypatch`: no manual `os.chdir`, `os.environ` or `sys.path` mutation, no git identity written outside the scratch repository (the global-state and home-pin scans census `tests/`).

**Files**: `tests/contract/test_mission_status_detail.py` (grows to about 1,000 lines).

**Validation**: `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_detail.py` green; the eight architectural-fast files green.

### Subtask T037: Thin corpus smoke and the registration pair for the detail module

**Purpose**: Corpus smoke, and the definition of the registration pair (committed with the module-creating commit T031, not after it).

**Steps**:

1. Complete the thin corpus smoke of T031 (detail for every distinct work package id, examined equals the independent count and both are greater than zero, empty skip list, no thresholds); host `NO_WORKTREES`.
2. The registration pair: `packs.yml`: one `--deselect tests/contract/test_mission_status_detail.py` in sorted position of the one-line `built-in-corpus-suite` command; `_CORPUS_MARKED_MODULES`: one row. These follow WP05's pair in the single-writer chain and are made in the T031 commit.
3. Run the nine router and registry gate files (green on the T031 commit and at the end), `--collect-only -m "corpus and not windows_ci"` (the module is selected) and `--collect-only -m "fast or unit"` over the detail module (expect exit code 5 and no test ids: pytest exits 5 when nothing is collected, and that is the pass condition).

**Files**: `tests/contract/test_mission_status_reality.py`, `.github/workflows/packs.yml`, `tests/architectural/test_ci_corpus_trigger_completeness.py`.

**Validation**: Gate files green; the module is not selected by the nightly expression.

## Validation: gates and targeted test surface

Charter: no full `tests/architectural/`, end-to-end, performance or `make test-full` sweep in mission work (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run exactly the commands below, record each command and its passed/failed counts in the hand-off report. Use the checkout's own environment (`.venv/bin/...`), never a bare `uv run`. `<scratch>` means a scratch directory outside the repository.

**Targeted test surface of this work package**:

- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_detail.py tests/contract/test_mission_status_artifacts.py`
- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py tests/contract/test_mission_status_payloads.py`
- `.venv/bin/python -m pytest --collect-only -q -m "fast or unit" tests/contract/test_mission_status_detail.py` (expect exit code 5 and no test ids: pytest exits 5 when nothing is collected, and that is the pass condition)

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

- First commit: failing detail tests against a skeleton module, red on the planning base for per-test reasons (T031), carrying the registration pair; T030 environment proof reported.
- Universe equals the independent count of distinct ids; the four duplicate ids follow the first-in-byte-order rule (OD-3); symlink and directory entries are skipped.
- Parity test over every FR-022 glob case with the two known divergences pinned; every fault guard has a positive fired counter and a killed mutation.
- No `src/` change; only public seams; `get_current_branch` and `git_merge_base` failures give `unknown`, never an escaping exception.
- Registration pair exists (committed with the module-creating commit); both architectural battery parts (`architectural-fast`, `architectural-heavy` shards `1/2` and `2/2`) run as CI runs them with the output recorded in the hand-off report (operator requirement, section Validation); nine router and registry gate files, eight architectural-fast files and the layer-rules files green; the module carries `contract`, `corpus`, `git_repo` and not `fast`.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Both architectural battery parts (`architectural-fast`, `architectural-heavy` shards `1/2` and `2/2`) were run as CI runs them and are green or binned, with the output recorded in the hand-off report (operator requirement, section Validation).
- Nothing pushed; no pull request; no tracker write.

## Risks

- The tool job installs with `--no-install-project`: the parity import is proven there first (T030) with a stated fallback.
- Real git in tests must not touch global git config or HOME: use the scratch repository only.
- Duplicate ids and file-identity rules are easy to apply to the wrong file (authored versus prompt): follow D-P6 exactly.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface (every file the change touches), plus the specific named architectural gate files it implicates; never a full sweep.

- Verify red then green: T031 fails on the planning base (each test on its own assertion, against the skeleton) and passes at the end.
- Re-run T030 in the tool-job environment form; check the parity test calls both private copies per pattern.
- Check each fault-injection test's fired counter and the killed mutation; check the marker set (no `fast`).
- Re-run the named and CI-battery gate files and the three architectural battery legs, or verify the recorded output (operator requirement, section Validation); confirm the registration pair is exactly one entry and one row and that it is in the first commit.
- Success criterion SC-004 (changed, unchanged and unknown each produced by the constructed cause in synthetic repositories, listed mutations killed) is built here by T034 to T036; WP08 and WP09 only re-measure and record it. Apply a spot-revert of at least one rule per acceptance row on a scratch copy and confirm the matching test fails.
- Verify the first commit is the red-first commit and that it is red on the planning base; verify green on the final commit; check the baseline bins in the hand-off.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs plan steps W-1 to W-7 in this order: W-1 accept, then lane consolidation (`spec-kitty consolidate`, strategy `rebase` recommended), then registration and wiring check, scripted scope check and issue-matrix rows; W-2 JVM shake-out; W-3 dev-assist cleanup; W-4 aggregate adversarial squad (report-only, pre-rebase tree); W-5 history compaction; W-6 rebase onto upstream including the 1.0.0 release commit; W-7 final evidence. Only then is the draft pull request opened, and it needs the `contract-mission-status-v1.0.0` tag. Evidence recorded earlier is labelled pre-tag or pre-rebase. You do none of this.

## Implementation command

`spec-kitty agent action implement WP06 --agent claude`
