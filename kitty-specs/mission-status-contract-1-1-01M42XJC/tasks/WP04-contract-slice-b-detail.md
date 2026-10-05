---
work_package_id: WP04
title: 'Contract slice B: getWorkPackageDetail'
dependencies:
- WP03
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-013
- FR-015
- FR-018
- FR-019
- C-001
- C-002
- C-004
- SC-001
planning_base_branch: issue-5625-mission-status-contract-1-1
merge_target_branch: issue-5625-mission-status-contract-1-1
branch_strategy: Planning artifacts for this mission were generated on issue-5625-mission-status-contract-1-1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5625-mission-status-contract-1-1 unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
- T020
- T021
- T022
history: []
agent_profile: implementer-ivan
authoritative_surface: contracts/mission-status/
create_intent:
- contracts/mission-status/paths/missions_missionId_work-packages_wpId_detail.yaml
- contracts/mission-status/schemas/WorkPackageDetail.yaml
- contracts/mission-status/schemas/Subtask.yaml
- contracts/mission-status/schemas/DependencyRef.yaml
- contracts/mission-status/schemas/ReviewCycle.yaml
- contracts/mission-status/schemas/Workspace.yaml
- contracts/mission-status/schemas/OwnedFile.yaml
- contracts/mission-status/schemas/ChangeState.yaml
- contracts/mission-status/schemas/ArtifactReferences.yaml
- contracts/mission-status/schemas/ArtifactReference.yaml
- contracts/mission-status/schemas/WorkPackageDetailRefusal.yaml
- contracts/mission-status/schemas/WorkPackageDetailRefusalCode.yaml
- contracts/mission-status/responses/WorkPackageDetailNotFound.yaml
- contracts/mission-status/responses/WorkPackageDetailUnreadable.yaml
- contracts/mission-status/examples/WorkPackageDetail.populated.yaml
- contracts/mission-status/examples/WorkPackageDetail.no-cycles.yaml
- contracts/mission-status/examples/WorkPackageDetail.unknown-change-state.yaml
- contracts/mission-status/examples/WorkPackageDetail.null-workspace.yaml
- contracts/mission-status/examples/WorkPackageDetail.planning-lane.yaml
- contracts/mission-status/examples/WorkPackageDetail.unparseable-cycle.yaml
- contracts/mission-status/examples/WorkPackageDetailRefusal.not-found.yaml
- contracts/mission-status/examples/WorkPackageDetailRefusal.source-unreadable.yaml
execution_mode: code_change
model: ''
owned_files:
- contracts/mission-status/openapi.yaml
- contracts/mission-status/CHANGELOG.md
- contracts/mission-status/schemas/_index.yaml
- contracts/mission-status/parameters/_index.yaml
- contracts/mission-status/responses/_index.yaml
- contracts/mission-status/examples/_index.yaml
- contracts/tools/enum_pins.json
- tests/contract/test_mission_status_examples.py
- tests/contract/test_enum_pin_check.py
- contracts/mission-status/paths/missions_missionId_work-packages_wpId_detail.yaml
- contracts/mission-status/schemas/WorkPackageDetail.yaml
- contracts/mission-status/schemas/Subtask.yaml
- contracts/mission-status/schemas/DependencyRef.yaml
- contracts/mission-status/schemas/ReviewCycle.yaml
- contracts/mission-status/schemas/Workspace.yaml
- contracts/mission-status/schemas/OwnedFile.yaml
- contracts/mission-status/schemas/ChangeState.yaml
- contracts/mission-status/schemas/ArtifactReferences.yaml
- contracts/mission-status/schemas/ArtifactReference.yaml
- contracts/mission-status/schemas/WorkPackageDetailRefusal.yaml
- contracts/mission-status/schemas/WorkPackageDetailRefusalCode.yaml
- contracts/mission-status/responses/WorkPackageDetailNotFound.yaml
- contracts/mission-status/responses/WorkPackageDetailUnreadable.yaml
- contracts/mission-status/examples/WorkPackageDetail.populated.yaml
- contracts/mission-status/examples/WorkPackageDetail.no-cycles.yaml
- contracts/mission-status/examples/WorkPackageDetail.unknown-change-state.yaml
- contracts/mission-status/examples/WorkPackageDetail.null-workspace.yaml
- contracts/mission-status/examples/WorkPackageDetail.planning-lane.yaml
- contracts/mission-status/examples/WorkPackageDetail.unparseable-cycle.yaml
- contracts/mission-status/examples/WorkPackageDetailRefusal.not-found.yaml
- contracts/mission-status/examples/WorkPackageDetailRefusal.source-unreadable.yaml
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP04 – Contract slice B: getWorkPackageDetail

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add the detail half of the 1.1 contract: `getWorkPackageDetail` with its eleven schemas, two responses, path file, eight examples and the two remaining enum pins; then prove the tool extension accepts the whole new tree.

## Context

Plan IC-04; shapes in `kitty-specs/mission-status-contract-1-1-01M42XJC/contracts/operations-and-schemas.md`. Depends on WP03 (shared contract files, `ArtifactKind` and `ArtifactPath`, which `ArtifactReference` references). The final enum-pin line is `enums=7 values=43`. This WP owns the named integration check of WP02 against WP03 and WP04: the ten strict names and the artifact-path class must accept every new contract file and example.

Decisions honoured (spec.md, Decisions and Traceability; read `kitty-specs/mission-status-contract-1-1-01M42XJC/spec.md` with this prompt; the rows are `tasks.md`, section Coverage): CL-1, CL-2, CL-3, CL-4, CL-5; AD-1, AD-2, AD-3, AD-4, AD-5, AD-6, AD-7, AD-8, AD-9, AD-10, AD-12, AD-13, AD-14, AD-16, AD-17, AD-18, AD-19, AD-20, AD-21; AC-DETAIL, AC-VERSION; OQ-5, OQ-6; OD-2, OD-3, OD-4.

Plan concern: IC-04 (plan section Implementation Concern Map). Requirement refs: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-013, FR-015, FR-018, FR-019, C-001, C-002, C-004, SC-001. Dependencies: WP03. Branch contract: planning base and merge target are `issue-5625-mission-status-contract-1-1`; work runs in the lane workspace `spec-kitty agent action implement` resolves for you (never reconstruct a path by hand).

## Owned files (write scope)

Edit only these paths (declared shared-file exceptions are dependency chains, never concurrent; plan section Lanes):

- `contracts/mission-status/openapi.yaml`
- `contracts/mission-status/CHANGELOG.md`
- `contracts/mission-status/schemas/_index.yaml`
- `contracts/mission-status/parameters/_index.yaml`
- `contracts/mission-status/responses/_index.yaml`
- `contracts/mission-status/examples/_index.yaml`
- `contracts/tools/enum_pins.json`
- `tests/contract/test_mission_status_examples.py`
- `tests/contract/test_enum_pin_check.py`
- `contracts/mission-status/paths/missions_missionId_work-packages_wpId_detail.yaml`
- `contracts/mission-status/schemas/WorkPackageDetail.yaml`
- `contracts/mission-status/schemas/Subtask.yaml`
- `contracts/mission-status/schemas/DependencyRef.yaml`
- `contracts/mission-status/schemas/ReviewCycle.yaml`
- `contracts/mission-status/schemas/Workspace.yaml`
- `contracts/mission-status/schemas/OwnedFile.yaml`
- `contracts/mission-status/schemas/ChangeState.yaml`
- `contracts/mission-status/schemas/ArtifactReferences.yaml`
- `contracts/mission-status/schemas/ArtifactReference.yaml`
- `contracts/mission-status/schemas/WorkPackageDetailRefusal.yaml`
- `contracts/mission-status/schemas/WorkPackageDetailRefusalCode.yaml`
- `contracts/mission-status/responses/WorkPackageDetailNotFound.yaml`
- `contracts/mission-status/responses/WorkPackageDetailUnreadable.yaml`
- `contracts/mission-status/examples/WorkPackageDetail.populated.yaml`
- `contracts/mission-status/examples/WorkPackageDetail.no-cycles.yaml`
- `contracts/mission-status/examples/WorkPackageDetail.unknown-change-state.yaml`
- `contracts/mission-status/examples/WorkPackageDetail.null-workspace.yaml`
- `contracts/mission-status/examples/WorkPackageDetail.planning-lane.yaml`
- `contracts/mission-status/examples/WorkPackageDetail.unparseable-cycle.yaml`
- `contracts/mission-status/examples/WorkPackageDetailRefusal.not-found.yaml`
- `contracts/mission-status/examples/WorkPackageDetailRefusal.source-unreadable.yaml`

22 of these paths do not exist yet on the planning base and are declared in the frontmatter `create_intent` (finalisation refuses a literal path that matches zero files unless it is declared there); you create them.

Nothing under `kitty-specs/` is written by this work package: records you must make (a contract-note refinement, a decision, a friction observation, the baseline) go into your hand-off report; the orchestrator appends them add-only to the tracer files. A small, well-justified out-of-map edit is acceptable only with a one-line rationale in the hand-off report; the no-overlap rule is the real guard against collisions.

### Subtask T017: Red-first: examples, eight-path map and enum-pin tests for the detail

**Purpose**: First commit: tests that fail until the detail exists.

**Steps**:

1. `test_mission_status_examples.py`: `EXPECTED_PATH_KEYS` becomes the eight paths and the "five paths" test is re-pinned to eight; required cases gain: each `ChangeState` value occurs, a cycle with a null `feedbackReference` and one with a null `reviewedAt` occur, each detail refusal code has an example.
2. `test_enum_pin_check.py`: the counts line becomes `enums=7 values=43`.
3. Run on the planning base of this WP's lane start: the new expectations fail. Commit.

**Files**: `tests/contract/test_mission_status_examples.py`, `tests/contract/test_enum_pin_check.py` (a few lines each plus the cases).

**Validation**: Red for the stated reasons.

### Subtask T018: The eleven detail schemas with provisional markers and citations

**Purpose**: The eleven schemas, closed and cited.

**Steps**:

1. Create `WorkPackageDetail` (required `missionId`, `wpId`, `subtasks`, `dependencies`, `reviewCycles`, `workspace`, `ownedFiles`, `artifactReferences`; every array present, possibly empty; embeds no `WorkPackage`), `Subtask`, `DependencyRef`, `ReviewCycle`, `Workspace`, `OwnedFile`, `ChangeState` (`changed`, `unchanged`, `unknown`), `ArtifactReferences`, `ArtifactReference`, `WorkPackageDetailRefusal`, `WorkPackageDetailRefusalCode` (`not_found`, `source_unreadable`) per the contract note.
2. Provisional (AD-14): `reviewCycles`, `workspace`, `ReviewCycle`, `Workspace`, `WorkPackageDetailRefusal`/`code`, via-`kind`. Environment-dependent descriptions (FR-016, FR-019): `Workspace.worktreePresent`, `OwnedFile.changeState` (x-derived with the full rule and inputs `git_merge_base`, `changed_paths`, `is_glob_pattern`) and `ReviewCycle` (a cycle held only on a coordination surface is not shown; `[]` means none found on the primary planning surface).
3. `Subtask.title` and `DependencyRef.title` are x-derived with the extraction rule; citations name symbols only (research R-12).

**Files**: Eleven files under `schemas/`.

**Validation**: `leak_scan.py`, `citation_check.py`, `layout_check.py`.

### Subtask T019: The detail path file, two responses, third path key and index entries

**Purpose**: Path file, responses, root map key and indexes.

**Steps**:

1. `paths/missions_missionId_work-packages_wpId_detail.yaml` (a new path item, tagged `Missions`; parameters `MissionId`, `WpId`; 200 `WorkPackageDetail`, 404 `WorkPackageDetailNotFound`, 500 `WorkPackageDetailUnreadable`, `default` shared `Problem`).
2. Responses `WorkPackageDetailNotFound` and `WorkPackageDetailUnreadable`. Add the third root path key `/missions/{missionId}/work-packages/{wpId}/detail` to `openapi.yaml` (the only other `openapi.yaml` edit).
3. New entries in the `_index.yaml` files of `schemas/` and `responses/`; append the detail lines to the CHANGELOG `### Added` (WP07 finalises Provisional and Deferred).
4. Document the duplicate-id rule (OD-3, plan D-P6) in the published contract text: the description of the `getWorkPackageDetail` path (and of `WorkPackageDetail` and the `WorkPackageDetailNotFound` response where it fits) states that a work package id held by two files is served by the first regular, non-symlink file in byte order of the file name, and that the work package's prompt file is the first qualifying `tasks/WP[0-9]{2,}-*.md` file in byte order. A consumer of the module must be able to learn the rule from the contract text alone.

**Files**: One path file, two responses, `openapi.yaml`, two index files, `CHANGELOG.md`.

**Validation**: `layout_check.py`, `structure_check.py`; the duplicate-id rule is present in the published path description.

### Subtask T020: The eight detail examples and the examples index

**Purpose**: The eight detail examples.

**Steps**:

1. Create `WorkPackageDetail.populated`, `.no-cycles`, `.unknown-change-state`, `.null-workspace`, `.planning-lane`, `.unparseable-cycle` and the two `WorkPackageDetailRefusal` examples (`not-found`, `source-unreadable`) as the contract note's table specifies.
2. Leak-free, valid against the schemas, paths satisfying `ArtifactPath`; no host path, address or credential. **No committed contract example holds an at-sign path** (the scan's acceptance of such a path is proved by the WP02 run-time-built tests and the reader tests; a YAML file cannot be built at run time); examples may carry a `home/<x>/` directory-segment name, a name with a space and a name with an accented letter (AD-19). OD-4 is decided (scoped text pass); nothing here is conditional on it.
3. Add to `examples/_index.yaml`.

**Files**: Eight files under `examples/`, `examples/_index.yaml`.

**Validation**: `example_check.py`, the extended examples test (T017 now green).

### Subtask T021: Enum pins for ChangeState and WorkPackageDetailRefusalCode

**Purpose**: Pins for the two remaining enums.

**Steps**:

1. `enum_pins.json`: add `ChangeState` (3 values) and `WorkPackageDetailRefusalCode` (2); `enum_pin_check.py` prints `enums=7 values=43`.

**Files**: `contracts/tools/enum_pins.json`.

**Validation**: `enum_pin_check.py --root contracts` exit 0; the pinned counts test passes.

### Subtask T022: Integration acceptance of the tool extension over the tree after slices A and B

**Purpose**: The named integration acceptance of WP02 against WP03 and WP04.

**Steps**:

1. Run `leak_scan.py`, `example_check.py` and `run_negative_cases.py` (three exclusion tags) over the tree after both slices: the ten strict names and the artifact-path class accept every new file and example.
2. Run `provisional_check.py --root contracts`, keep its output in the hand-off report as the draft provisional list for WP07 (WP07 takes the final list from its own run).
3. Run the other Python checks and the targeted tests; check new files for raw NUL bytes.

**Files**: None.

**Validation**: All named commands exit 0, listed with their `counts:` lines in the hand-off report.

## Validation: gates and targeted test surface

Charter: no full `tests/architectural/`, end-to-end, performance or `make test-full` sweep in mission work (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run exactly the commands below, record each command and its passed/failed counts in the hand-off report. Use the checkout's own environment (`.venv/bin/...`), never a bare `uv run`. `<scratch>` means a scratch directory outside the repository.

**Targeted test surface of this work package**:

- The ten Python checks of quickstart section Python checks.
- `PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_examples.py tests/contract/test_enum_pin_check.py tests/contract/test_leak_scan.py tests/contract/test_example_round_trip.py`

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

- First commit: red tests (T017); then 11 schemas, 3rd path file, 2 responses, 8 examples, 2 pins; `enums=7 values=43`.
- Integration check (T022) green and reported; draft provisional list in the hand-off.
- Only additive edits to existing files; no leaking literal; no NUL byte.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- Provisional naming (`kind`, `code`): run `provisional_check` before WP07 finalises the CHANGELOG.
- The unicode-escape hazard and F-4/F-5 (file-wide checks) apply as in WP03.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface (every file the change touches), plus the specific named architectural gate files it implicates; never a full sweep.

- Verify red then green for T017; verify `ChangeState` descriptions state the host dependence and the derivation.
- Check the byte identity of everything existing except the listed edits; the detail embeds no `WorkPackage`.
- Re-run T022 yourself over the tree.
- Verify the first commit is the red-first commit and that it is red on the planning base; verify green on the final commit; check the baseline bins in the hand-off.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs plan steps W-1 to W-7 in this order: W-1 accept, then lane consolidation (`spec-kitty consolidate`, strategy `rebase` recommended), then registration and wiring check, scripted scope check and issue-matrix rows; W-2 JVM shake-out; W-3 dev-assist cleanup; W-4 aggregate adversarial squad (report-only, pre-rebase tree); W-5 history compaction; W-6 rebase onto upstream including the 1.0.0 release commit; W-7 final evidence. Only then is the draft pull request opened, and it needs the `contract-mission-status-v1.0.0` tag. Evidence recorded earlier is labelled pre-tag or pre-rebase. You do none of this.

## Implementation command

`spec-kitty agent action implement WP04 --agent claude`
