---
work_package_id: WP03
title: 'Project vertical: contract, memo, builder and ratchet edits'
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-015
- FR-023
- FR-024
- FR-025
- FR-029
- NFR-006
- NFR-009
- SC-001
planning_base_branch: issue-5776-mission-status-contract-health-drift-ops
merge_target_branch: issue-5776-mission-status-contract-health-drift-ops
branch_strategy: Planning artifacts for this mission were generated on issue-5776-mission-status-contract-health-drift-ops. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5776-mission-status-contract-health-drift-ops unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
- T016
- T017
history: []
agent_profile: python-pedro
authoritative_surface: contracts/mission-status/
create_intent:
- contracts/mission-status/schemas/ProjectHealth.yaml
- contracts/mission-status/examples/Project.all-null.yaml
- contracts/mission-status/examples/Project.schema-drift.yaml
- tests/contract/_mission_status_memo.py
- tests/contract/_mission_status_project.py
- tests/contract/test_mission_status_project.py
execution_mode: code_change
model: ''
owned_files:
- contracts/mission-status/schemas/Project.yaml
- contracts/mission-status/schemas/ProjectHealth.yaml
- contracts/mission-status/examples/Project.example.yaml
- contracts/mission-status/examples/Project.all-null.yaml
- contracts/mission-status/examples/Project.schema-drift.yaml
- contracts/mission-status/paths/project.yaml
- contracts/mission-status/schemas/_index.yaml
- contracts/mission-status/examples/_index.yaml
- contracts/mission-status/CHANGELOG.md
- contracts/tools/enum_pins.json
- tests/contract/_mission_status_memo.py
- tests/contract/_mission_status_project.py
- tests/contract/test_mission_status_project.py
- tests/contract/_mission_status_payloads.py
- tests/contract/test_mission_status_payloads.py
- tests/contract/test_mission_status_reality.py
- tests/contract/test_mission_status_examples.py
- tests/contract/test_enum_pin_check.py
- tests/contract/test_mission_status_contract_1_1.py
- .github/workflows/packs.yml
- tests/architectural/test_ci_corpus_trigger_completeness.py
- .github/workflows/ci-router.yml
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP03 - Project vertical: contract, memo, builder and ratchet edits

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Land the only change to an existing response (`Project` gains five properties) together with the code that proves it (the neutral resolver memo, the new Project builder and the ratchet edits of the v1 payload and reality tests), so no tip is red.

## Context

This is the largest vertical of the Mission (P-13) and cannot be split without a red tip: keep ONE work package with three ordered commits: (1) the red tests and raising stubs (and the registration pair, because this commit creates a module); (2) the contract and the ratchet edits; (3) the builder. The two new `Project` examples and the five-property required list make `test_mission_status_examples.py` red until the files exist; the `derive_project` equality of two keys and the reality check's Project build turn v1 tests red against the new schema until the builder is wired, so the ratchet edits are reviewed AS ratchets (spec R-6). The Project description must state the cost and the network behaviour. WP04 to WP06 edit the same contract chokepoint files after this WP (declared shared-file exception 1 and 2: a dependency chain, never concurrent).

Plan concern: IC-03 of `kitty-specs/mission-status-health-drift-ops-01M464D3/plan.md`. Read, in this order, before writing anything: `.kittify/charter/charter.md`, `AGENTS.md` (for conventions only), the Mission's `spec.md` (the requirement ids in the frontmatter), `plan.md` sections named below, `research.md`, `data-model.md`, `quickstart.md` and `contracts/*.md` in `kitty-specs/mission-status-health-drift-ops-01M464D3/`.

**Dependencies and order.** Depends on WP01, WP02; the lane workspace already holds their approved commits. No work package is dispatched before the orchestrator's Step 0 record exists in `tracer-approach.md`. **Pre-dispatch (orchestrator Step PD in `tasks.md`, operator ruling 13):** before this dispatch the orchestrator fast-forwards the mission-lane branch `kitty/mission-<slug>` and, once the orchestrator's run of `spec-kitty agent action implement WP03 --agent claude` (the command of your Implementation command section; it creates or resumes the lane workspace) has created this lane workspace and before you are started, merges the planning branch into it and greps inside it for every record this prompt reads: the Step 0 record (heading `## Record: Step 0`) and the hand-off records of WP01 and WP02 (headings `## Record: Hand-off WP01 (` and `## Record: Hand-off WP02 (`), all in `tracer-approach.md`; read them from the lane workspace root. If a line the prompt tells you to read is not there, stop and report it; never run `--refresh-planning-commit` and never copy a record in by hand.

## Owned files (write scope; final, explicit, no directory-wide glob)

- `contracts/mission-status/schemas/Project.yaml`
- `contracts/mission-status/schemas/ProjectHealth.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/examples/Project.example.yaml`
- `contracts/mission-status/examples/Project.all-null.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/examples/Project.schema-drift.yaml` (new: created by this WP, listed in `create_intent`)
- `contracts/mission-status/paths/project.yaml`
- `contracts/mission-status/schemas/_index.yaml`
- `contracts/mission-status/examples/_index.yaml`
- `contracts/mission-status/CHANGELOG.md`
- `contracts/tools/enum_pins.json`
- `tests/contract/_mission_status_memo.py` (new: created by this WP, listed in `create_intent`)
- `tests/contract/_mission_status_project.py` (new: created by this WP, listed in `create_intent`)
- `tests/contract/test_mission_status_project.py` (new: created by this WP, listed in `create_intent`)
- `tests/contract/_mission_status_payloads.py`
- `tests/contract/test_mission_status_payloads.py`
- `tests/contract/test_mission_status_reality.py`
- `tests/contract/test_mission_status_examples.py`
- `tests/contract/test_enum_pin_check.py`
- `tests/contract/test_mission_status_contract_1_1.py`
- `.github/workflows/packs.yml`
- `tests/architectural/test_ci_corpus_trigger_completeness.py`
- `.github/workflows/ci-router.yml`

No file under `kitty-specs/` is in this write scope: record what you learn in the hand-off; the orchestrator appends it to the tracer files. An out-of-map edit is acceptable only when small, well-justified and recorded with a one-line rationale in the hand-off. Shared files in this list are declared chokepoints serialised by the dependency chain (plan 'Declared shared-file exceptions'); edit only your own entries in them.

## Implementation concern (plan section IC-03, verbatim)

- **Purpose**: Land the only change to an existing response together with the code that proves it, so no tip is red.
- **Relevant requirements**: FR-001 to FR-007, FR-023 (Project examples and the `health` provisional entry), FR-024 (Project rows), FR-029 item 1, FR-015 (Memo, the Project consumer), FR-025 (the reality check's Project build, ratchet), NFR-009, OR-1, OR-8, OR-10, FRESH-005; AC-PROJECT 1 to 8, AC-DRIFT 16.
- **Affected surfaces**: contract: `schemas/Project.yaml`, new `schemas/ProjectHealth.yaml`, `examples/Project.example.yaml`, new `examples/Project.all-null.yaml` and `examples/Project.schema-drift.yaml`, `paths/project.yaml` (description only), `schemas/_index.yaml`, `examples/_index.yaml`, `CHANGELOG.md` (Changed, the `health` provisional token, Deferred three gaps), `contracts/tools/enum_pins.json` (`ProjectHealth`); tests and helpers: new `_mission_status_memo.py`, `_mission_status_project.py`, `test_mission_status_project.py`; edited `_mission_status_payloads.py` (the `derive_project` equality), `test_mission_status_payloads.py` (the two-key assertion), `test_mission_status_reality.py` (the Project build uses the new builder; the v1 pass stays), `test_mission_status_examples.py`, `test_enum_pin_check.py`, `test_mission_status_contract_1_1.py` (FR-029 item 1: `DEFERRED_GAPS` loses "project branch", the gap-outside-section test re-points to "lane weights", the entry test renames to three); registrations: `.github/workflows/packs.yml`, `tests/architectural/test_ci_corpus_trigger_completeness.py`, `.github/workflows/ci-router.yml`.
- **Sequencing**: after IC-01 (same proof module) and IC-02 (the scanner meets every new file as it is written).
- **Red-first**: the two new `Project` examples and the five-property required list as required cases of `test_mission_status_examples.py` (red until the files exist), the `test_enum_pin_check.py` line and the pin (red until `ProjectHealth` exists), the AC-PROJECT rows of `test_mission_status_project.py` against a stub builder that raises, and the ratchet edit of `derive_project` (the v1 tests turn red against the new schema until the builder is wired).
- **Acceptance (named)**: the ten Python checks over the IC-03 tree; the `breaking_check.py` spike of research R-5 repeated on the real files (lowered-major `breaking=4`); the named census files and the registration gates run green; the first task runs the two global-state scan files against the counting wrapper (D-P2).
- **Risks**: this is the largest vertical (P-13); the ratchet edits to v1 tests are reviewed as ratchets (spec R-6); the Project description must state the cost and the network behaviour.

## Design decisions that bind this work package (plan, verbatim)

**D-P2 The resolver memo (FR-015, FRESH2-003, FRESH3-004).** One neutral helper module, `_mission_status_memo.py`: an object `memo` created per run (a reality run or a fixture build), keyed by (resolved repository root, Mission directory name), holding the raw resolver outcome (the directory or the exception) and the number of subprocesses the call started. Consumers: the strict drift sibling (D-P3), the new Project builder (D-P4) and the oracles. A test builds two repositories with the same Mission name and different outcomes and asserts each gets its own result; a control reads one repository twice and asserts one resolver run. **Counting:** the subprocess count wraps `subprocess.Popen.__init__` through a pytest `MonkeyPatch` context (never a manual global mutation, which the architectural scans flag); IC-03's first task runs the two named scan files against a stub module holding this wrapper before the helper is written (risk P-14). The FR-007 stub of `subprocess.run` that raises unless the memo helper's resolver call is on the stack composes with it.

**D-P4 The Project builder (FR-001 to FR-007, FRESH2-002).** In `_mission_status_project.py`: reads `.kittify/metadata.yaml` through `ProjectMetadata.load` and `get_project_schema_version` (never the CLI wrapper), **behind a shape guard (plan-round ruling 2, PQ-7)**: `ProjectMetadata.load` applies `.get` to unvalidated YAML and raises `AttributeError` for a list or scalar at the top level, for `spec_kitty` or `environment` a list or scalar, and `TypeError` for a non-mapping `migrations` entry (only `OSError` and the YAML error are caught inside it). The reader therefore pre-checks the parsed shape (top level a mapping, `spec_kitty` a mapping), calls `load` only when the shape is safe, and treats a residual `AttributeError` or `TypeError` from `load` as null (never as a failure of the read, never a 500); `load` stays the reader of the version, so the spec's "read as load reads it" holds and no `src/` change is needed (C-006). The guard is proved by the raising shapes planted in AC-PROJECT row 1. It applies the FR-002 table, computes `health` from `MIN_SUPPORTED_SCHEMA`/`MAX_SUPPORTED_SCHEMA`, reads `HEAD` as a file (the `.git` file case follows the gitdir; no subprocess) with the FR-005 name rules, and takes `lastActivityAt` as the latest instant over the Missions `GET /missions` lists. It reaches the resolver only through the memo and reproduces all four v1 fallbacks (the three exceptions and a read directory outside the checkout) on the raw outcome; it never calls v1's `load_source`. **Equality control:** on every fixture the new builder equals the v1 build (including the outside-root fixture); that is how the fallbacks are proved the same.

**D-P8 Router globs for the new imports.** The `contract_tools` group of `ci-router.yml` names the `src/` files the helpers import, spelled `**/<path>` so the group stays non-src. Each reader work package adds its own entries in sorted position in the commit that first imports the file (Registration item 4 says which); `test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import` derives the required list from the imports and goes red until they are present. The expected new entries (to be recomputed by that test, never by hand): `status/lifecycle.py`, `lanes/models.py`, `status/validate.py` (one-way drift check only), `upgrade/metadata.py`, `migration/schema_version.py`, `core/paths.py`, `invocation/record.py`, `invocation/writer.py`, `invocation/errors.py`, `git/remote_probes.py` and the `__init__` files the import scan adds. No edit of `docs/development/reference/ci-gate-mechanics.md` is needed: its paragraph on the group already says "the `src/` modules the mission-status reference reader imports".

**D-P9 Contract authoring decisions.** All new enums are snake_case and pinned (PR-2; the vacuum `enum-case` rule is outside every Python gate, hence J-1). Every new property carries exactly one `x-source` or `x-derived` (field catalogue of the spec); every new schema is closed; every new operation keeps the shared `Problem` for `default`. Refusal schemas follow `ArtifactRefusal` (a `Problem` plus `code` and one `if`/`then` per code pinning the status). `DriftFinding.sourceCode` is a string matching `^[A-Z][A-Z0-9_]*$` or null; `OpsEvidence.value` has `maxLength: 512`; `OpsInvocation.profileId` and `action` use `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`. The two query parameter files are new (`DriftMissionId`, `OpsProfile`); `PageSize` and `PageCursor` are the shared ones. The unicode-escape hazard applies to every pattern with a NUL or backslash (write `\x00`, build `chr(0)` and `chr(92)` in tests).

## Acceptance rows of this work package (plan 'Test strategy per acceptance criterion', verbatim)

Rule for every row: the test fails when the change is reverted. **Three kinds of revert proof**, named in each row: **B** base-red (the test is red on the work package's base and green on its tip; the first commit carries the test and a stub entry point that raises, so a red is a behaviour failure); **P** planted pair (a control that passes and a plant that fails on the same fixture, so the probe can see the thing); **M** named mutation (a table of reader mutations applied by the test, each of which must turn its rows red: `the mutation was not killed: <name>`; the catalogue is in contracts/tool-extension-and-reader.md). Tests call the reference reader's production entry point, never only a helper. Row numbers are the order of the spec's tables.

| Row | Red-first test (proof kind) |
|---|---|
| 1 non-mapping and list metadata is null (the shape guard of D-P4; the reader never raises) | the shapes on which `ProjectMetadata.load` raises: a YAML list at the top level, a scalar at the top level, `spec_kitty` a list, `spec_kitty` a scalar, `environment` a list, a non-mapping `migrations` entry (each: `specKittyVersion` null, no exception; the unguarded `load` call is shown to raise `AttributeError` or `TypeError` on the same file, so the plant is real); control a mapping (B, P, M: call `load` unguarded) |
| 2 sentinel never escapes; non-string and non-matching versions null | no `version`; numeric; path-shaped; sentence-shaped; control `4.0.0` (B, P) |
| 3 non-integer schema null and unhealthy; CLI coercion is the contract's | `three`, `"3"` gives 3, `3.9` gives 3, `true` gives 1, compared with `get_project_schema_version` (B, P, M: wrap the CLI call) |
| 4 range boundaries; range not equality | MIN-1, MIN, MAX, MAX+1, null; constants patched to 2 and 4 with schema 3; differential test against `check_compatibility` (B, P, M: one-sided test) |
| 5 branch states | attached, unborn (the name), detached, no repository, unreadable HEAD, bad name, strict host-path name, linked worktree; parity with `get_current_branch` wherever a name is served (B, P, M: null on unborn) |
| 6 activity as instants | offsets where text and instant order differ; zero Missions; all-null; control one active Mission (B, P, M: string maximum) |
| 7 no process of its own, no write | `subprocess.run` raising unless the memo's resolver call is on the stack; writers raising; a plant that starts a subprocess from the reader (fails); builder equals the v1 build on every fixture including outside-root (B, P) |
| 8 description and required list; cost sentence | frozen old schema, short `required`, description without the cost sentence; real file passes (B, P); in `test_mission_status_examples.py` for the three examples |

Plus the memo row, in `test_mission_status_project.py` for this WP:

| 16 memo keyed by root and directory | two repositories, same name, different outcomes; one repository read twice runs the resolver once (in the project module, IC-03) (B, P) |

### Subtask T010: First task: scan files against the counting wrapper

**Purpose**: Before writing the memo helper, run the two global-state scan files (`tests/architectural/test_no_manual_global_state_mutation.py`, `tests/architectural/test_no_tmp_paths_in_tests.py`) against a STUB module holding the subprocess counting wrapper of D-P2 (a `pytest.MonkeyPatch` context around `subprocess.Popen.__init__`, never a manual global mutation) so the wrapper's shape is proven acceptable before the real helper exists (risk P-14).

**Steps**:
1. Write the stub in a scratch location or as the first lines of `tests/contract/_mission_status_memo.py` under a raising entry point; run the two files as named files.
2. Report the result in the hand-off; a red here is binned against the Step 0 record.

**Files**: tests/contract/_mission_status_memo.py (new, stub first)

**Validation**: Both scan files green with the wrapper present.

### Subtask T011: Red-first commit: AC-PROJECT tests, required-case manifest, stubs, registration pair

**Purpose**: Commit 1. Write `tests/contract/test_mission_status_project.py` (every AC-PROJECT row with its control, against a stub builder that raises), extend `test_mission_status_examples.py` (the two new Project examples and the five-property required list as required cases), `test_enum_pin_check.py` (the `ProjectHealth` line and `counts:` line) and the ratchet edit of `derive_project`'s expected shape. Add the registration pair for the new module in this same commit.

**Steps**:
1. Raising stubs: `_mission_status_project.py` builder and `_mission_status_memo.py` entry points raise `NotImplementedError`.
2. Verify the red on the base without `git stash` (see Red-first rule): behaviour failures, controls red.
3. AC-PROJECT row 7 uses a `subprocess.run` that raises unless the memo's resolver call is on the stack, composed with the Popen counting wrapper.
4. **Camel-case plant (AC-VERSION, bullet 5):** in `tests/contract/test_enum_pin_check.py`, with the existing `module_copy` pattern, rewrite the value `schema_drift` of `schemas/ProjectHealth.yaml` in the scratch copy to `schemaDrift` and run `enum_pin_check.py --root <copy> --module mission-status`: exit 1 with `ENUM_VALUE_ADDED: mission-status:ProjectHealth` and `ENUM_VALUE_REMOVED: mission-status:ProjectHealth`; the unmodified copy exits 0. WP04 (`DriftKind`) and WP05 (`OpsClosedBy`) carry the same plant for their enums.

**Files**: tests/contract/test_mission_status_project.py (new, about 500 lines), test_mission_status_examples.py, test_enum_pin_check.py, .github/workflows/packs.yml, tests/architectural/test_ci_corpus_trigger_completeness.py (the registration pair); .github/workflows/ci-router.yml only if the test module or the stubs already import a `src/` file the `contract_tools` group does not name (otherwise the globs land with the builder's real imports)

**Validation**: Red run recorded; registry gates green on this commit.

### Subtask T012: Contract: Project schema, ProjectHealth, examples, path description

**Purpose**: Commit 2a. Edit `schemas/Project.yaml` (description rewritten, `required` extended, five properties added, each with exactly one `x-source` or `x-derived`; `health` carries `x-provisional`), add `schemas/ProjectHealth.yaml` (enum `healthy`, `schema_drift`), update `examples/Project.example.yaml`, add `examples/Project.all-null.yaml` and `examples/Project.schema-drift.yaml`, edit `paths/project.yaml` (description only).

**Steps**:
1. Follow `kitty-specs/mission-status-health-drift-ops-01M464D3/contracts/operations-and-schemas.md` (the Project descriptions that carry rules: the five property names, no longer 'a name and a count only', the cost grows with the Mission count, read directories are resolved through git queries that can include network probes, no drift scan, `schemaVersion` is the CLI's coercion, `health` is the serving build's range and provisional, `currentBranch` null semantics, `lastActivityAt` null semantics).
2. All new enums snake_case; every example leak-free; no at-sign file name.

**Files**: the ten files of the contract family listed above

**Validation**: `example_check.py` validates every example; `leak_scan.py` exits 0.

### Subtask T013: Contract: indexes, CHANGELOG, enum pin

**Purpose**: Commit 2b. Add the new entries to `schemas/_index.yaml` and `examples/_index.yaml`; merge into the existing `## 1.0.0-SNAPSHOT` section of `CHANGELOG.md` (no new heading): `### Changed` (the `Project` pre-release shape change, the four non-provisional additions and why the tooling reports them), the `health` token in `### Provisional`, and the Deferred list reduced to THREE gaps (the line 'The project branch' and the word 'Four' are gone); add the `ProjectHealth` pin to `contracts/tools/enum_pins.json`.

**Steps**:
1. `info.version` stays `1.0.0-SNAPSHOT` (spec PR-1, C-002).
2. Do not touch `openapi.yaml`; this WP adds no path key.

**Files**: indexes, CHANGELOG.md, enum_pins.json

**Validation**: `enum_pin_check.py`, `provisional_check.py`, `structure_check.py` exit 0.

### Subtask T014: Ratchet edits of the v1 tests and the FR-029 item 1 edits

**Purpose**: Commit 2c. Edit `_mission_status_payloads.py` (the `derive_project` equality), `test_mission_status_payloads.py` (the two-key assertion), `test_mission_status_reality.py` (the Project build uses the new builder; the v1 pass and the 8-Mission ratchet header stay untouched) and `test_mission_status_contract_1_1.py` (FR-029 item 1: `DEFERRED_GAPS` loses 'project branch', the gap-outside-section test re-points to 'lane weights', the entry test renames to three).

**Steps**:
1. Review each edit as a RATCHET: no assertion is loosened; the old two-key shape is replaced by the five-property shape and the v1 behaviour of every other payload is unchanged.
2. Report every ratchet edit in the hand-off for the reviewer.

**Files**: the four test files named

**Validation**: v1 payload and reality tests green against the new schema once the builder is wired.

### Subtask T015: Memo helper

**Purpose**: Commit 3a. Implement `_mission_status_memo.py` per D-P2: one neutral object `memo` per run keyed by (resolved repository root, Mission directory name), holding the raw resolver outcome (directory or exception) and the number of subprocesses the call started; the subprocess count wraps `subprocess.Popen.__init__` through a pytest `MonkeyPatch` context.

**Steps**:
1. Two repositories with the same Mission name and different outcomes each get their own result; one repository read twice runs the resolver once (AC-DRIFT 16 lives in the project module here).
2. No private import; consumers are the strict drift sibling (WP07), this WP's Project builder and the oracles (WP09).

**Files**: tests/contract/_mission_status_memo.py (about 150 lines)

**Validation**: AC-DRIFT 16 test green.

### Subtask T016: Project builder

**Purpose**: Commit 3b. Implement `_mission_status_project.py` per D-P4: `ProjectMetadata.load` and `get_project_schema_version` behind the SHAPE GUARD (pre-check the parsed shape, call `load` only when safe, treat a residual `AttributeError` or `TypeError` as null, never a 500), the FR-002 table, `health` from `MIN_SUPPORTED_SCHEMA`/`MAX_SUPPORTED_SCHEMA`, `HEAD` read as a file (the `.git` file case follows the gitdir; no subprocess) with the FR-005 name rules, and `lastActivityAt` as the latest INSTANT (not text) over the Missions `GET /missions` lists. Resolver only through the memo; all four v1 fallbacks reproduced.

**Steps**:
1. The builder equals the v1 build on every fixture including outside-root (AC-PROJECT 7).
2. No process of its own, no write, no clock default.

**Files**: tests/contract/_mission_status_project.py (about 350 lines)

**Validation**: All AC-PROJECT rows green; the unguarded `load` call is shown to raise on the same file (the plant is real).

### Subtask T017: Acceptance runs (router-glob derivation check)

**Purpose**: Confirm that the router-glob derivation test (`test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import`, in `tests/ci/test_contracts_workflows.py`) is green. The globs were already added, each in the commit that first imported its `src/` file (Registration item 4); this subtask edits nothing. Run the acceptance set, and the three battery legs last (binding gate below): the ten Python checks over the WP tree, the lowered-major spike, the named census files and registration gates, the tool tests, the tool-job selection and the reality run.

**Steps**:
1. Record every `counts:` line and the spike's `breaking=4 provisional_changes=<N>`.
2. Hand-off carries the NFR-009 measurement of one Project build (minimum of the repeats).

**Files**: none

**Validation**: All named acceptance items green or binned.

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

The new module of this work package, run on its own after the red commit and on the tip:

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/contract/test_mission_status_project.py
```

### The tool job's whole selection

The tool job's whole selection, as the router runs it (plan-time: 1,778 passed, 37 skipped in 176 s locally; re-take against the Step 0 record):

```text
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -m "corpus and not windows_ci" tests/contract --ignore=tests/contract/test_example_round_trip.py --ignore=tests/contract/test_mission_status_payloads.py --ignore=tests/contract/test_mission_status_reality.py -n 4 --dist loadfile -q
```

### Reality module and payload helper

```text
PWHEADLESS=1 .venv/bin/python -m pytest -q -p no:cacheprovider -m "corpus and not windows_ci" tests/contract/test_mission_status_reality.py tests/contract/test_mission_status_payloads.py
```

(plan-time: 819 passed in 108 s locally; the resolver's remote probes need the network. Offline, only the named resolver-dependent assertions take a named skip.)

### Additive-proof spike

The lowered-major breaking-check spike on the real files (research R-5), run from the checkout with the pinned `oasdiff` fetched into a scratch directory:

```text
.venv/bin/python contracts/tools/install_tools.py --pins contracts/tools/pins.json --dest <scratch>/tools --only oasdiff
mkdir -p <scratch>/base && git archive <baseline sha> contracts/mission-status contracts/_shared | tar -x -C <scratch>/base
# move the two directories up one level so <scratch>/base/mission-status and <scratch>/base/_shared exist;
# copy that directory to <scratch>/lowered and rewrite info.version in its mission-status/openapi.yaml to 0.9.0 (scratch only)
PATH=<scratch>/tools/oasdiff-1.32.1:$PATH .venv/bin/python contracts/tools/breaking_check.py --root contracts --baseline-root <scratch>/lowered
```

`<baseline sha>` is the merge-base of `HEAD` with upstream `main` (`git merge-base HEAD <main>`), recorded by the orchestrator's Step 0. Expected: exit 0 and a final line `counts: modules=1 baselines=1 breaking=4 provisional_changes=<N> no_baseline_initial=0 preview_ref=skipped` (the four breaking entries name `currentBranch`, `lastActivityAt`, `schemaVersion` and `specKittyVersion`; `<N>` is measured on the tree and reported). Adding the new path and tag must not change `breaking=4`.

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

### Registration of `test_mission_status_project.py` (NEW test module)

**Registration pair, in the SAME commit that creates the module (and in sorted position; the registry gates must be green on every commit):**

1. `.github/workflows/packs.yml`: one `--deselect tests/contract/test_mission_status_project.py` entry in the one-line `built-in-corpus-suite` command (it is one physical line; edit it in place, keep it one line, keep alphabetical position among the existing `--deselect tests/contract/...` entries).
2. `tests/architectural/test_ci_corpus_trigger_completeness.py`: one row `"tests/contract/test_mission_status_project.py",` in the `_CORPUS_MARKED_MODULES` frozenset, in sorted position (the neighbouring detail-reader module is the pattern).
3. `pytestmark` of the module: ONE single-line list holding `pytest.mark.corpus`, exactly the form of `tests/contract/test_mission_status_detail.py`: `pytestmark = [pytest.mark.contract, pytest.mark.corpus, pytest.mark.git_repo]`. The registry gate's `_CORPUS_MARK_APPLICATION_RE` matches `pytestmark = ... pytest.mark.corpus` within one line only; a mark spelled through a shared list or wrapped across lines is reported as in the registry but not marked.
4. Router globs (the `contract_tools` group of `.github/workflows/ci-router.yml`): add the `**/<path>` entries for the `src/` files the new helper(s) import, spelled `**/specify_cli/...` / `**/kernel/...` so the group stays non-src, in sorted position, in the commit that FIRST adds an import of that `src/` file, never in a separate closing commit (the derivation test is in `tests/ci/test_contracts_workflows.py` and scans every `tests/contract/*mission_status*.py` file, stubs included, so it goes red the moment any such file imports a `src/` file the group does not yet name, and the 'registry gates green on every commit' rule then fails). The red-first commit carries the globs only if its test module or its stub imports a `src/` file (a stub that merely raises imports nothing and needs none); otherwise they land in the commit that gives the helper its real body, together with that import. The test `test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_and_its_tests_import` derives the required list from the imports and stays red until they are present; never write the list by hand, recompute it from that test's output. Expected new entries (recomputed by the test, not typed): `**/specify_cli/upgrade/metadata.py`, `**/specify_cli/migration/schema_version.py`, `**/specify_cli/core/paths.py` and the `__init__` files the import scan adds
5. Proof of selection: `.venv/bin/python -m pytest --collect-only -q -m "corpus and not windows_ci" tests/contract/test_mission_status_project.py` collects the module; `.venv/bin/python -m pytest --collect-only -q -m "fast or unit" tests/contract/test_mission_status_project.py` collects nothing (exit 5 and no test ids is the pass condition).
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

- The ten Python checks over the WP tree (plus the negative-case runner) exit 0.
- The `breaking_check.py` spike of research R-5 repeated on the real files: lowered-major `breaking=4`.
- The named census files and the registration gates run green.
- The first task ran the two global-state scan files against the counting wrapper (D-P2).
- AC-PROJECT rows 1 to 8 and AC-DRIFT row 16 green; every row's control and plant behave.
- First commit is the red tests with a raising stub (behaviour failures, controls red), verified on the base; green on the tip.
- `test_mission_status_project.py`: registration pair and single-line `pytestmark` in the module-creating commit; the router globs in the commit that first imports each `src/` file (the helper commit; the red-first commit only if its stub or test module imports `src/`); registry gates green on every commit; the router-glob derivation test confirmed green in T17, with no separate closing glob commit.
- The three architectural battery legs (`architectural-fast`, `architectural-heavy` 1/2 and 2/2) ran locally on the final commit, as the binding gate of operator ruling 14 requires: three exit-code files read, counts and exit status in the hand-off, every red binned against the Step 0 per-leg baselines. Under the note 16 fallback (the orchestrator ran the legs because the wait primitive was denied to the worker), this is met when the orchestrator ran the three legs and appended the three exit-code results to the hand-off record before review; the worker's hand-off then states that the legs are left to the orchestrator.
- Named gate files and census files green or binned against the Step 0 record; ruff check, ruff format --check and TID251 clean with no suppression added.
- Hand-off carries measured minima, margins and re-measurements; nothing written under `kitty-specs/`.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- P-13: the largest vertical; keep three ordered commits.
- The ratchet edits to v1 tests are reviewed as ratchets (spec R-6).
- The Project description must state the cost and the network behaviour.
- P-14: the counting wrapper versus the global-state scans.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface, plus the named gate files and census files above; never a full sweep, except the three battery legs of the binding gate below (operator ruling 14 makes them binding for WP03, WP07 and WP08 only; every other work package keeps named files only).
- Verify red then green: the first commit is the red-first commit with a raising stub; the red run shows BEHAVIOUR failures, not collection errors; the control tests are red too; green on the tip.
- Re-run the named gate files and the census files; check baseline bins against the Step 0 record in `tracer-approach.md`; check the hand-off carries measured minima, margins and re-measurements.
- Verify the registration pair is in the module-creating commit, each router glob is in the commit that first imports its `src/` file, and the module is selected by the router marker expression and not by the nightly's. Verify the hand-off carries the three battery legs (binding gate, operator ruling 14): command, counts, exit status from the exit-code files and bins against the Step 0 per-leg baselines; re-run a leg when the hand-off is thin, and treat a missing leg as a reason to reject (under the note 16 fallback the rejection applies after the orchestrator has appended the three exit-code results to the hand-off record; before that append, a hand-off that says the legs are left to the orchestrator is not rejected for it). Compare each leg with the Step 0 local run of the same leg, not with main-CI durations (informational only, orchestrator note 15).
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal; no raw NUL byte.
- Check nothing under `kitty-specs/` was written and no file outside the owned list changed without a recorded rationale.
- Review the ratchet edits of the v1 payload, payload-test and reality tests AS ratchets (no assertion loosened; the 8-Mission header and the v1 pass untouched); check the three commits are ordered red, contract and ratchets, builder.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs W-1 (accept, local lane consolidation, registration and scope check over the real diff), W-2 (J-1 confirmation), W-3 (dev-assist cleanup), W-4 (issue-verdict evidence, aggregate adversarial squad, terminal #5776 verdict), W-5 (history compaction), W-6 (rebase onto upstream `main`) and W-7 (final evidence); then the draft pull request. You do none of this.

## Implementation command

`spec-kitty agent action implement WP03 --agent claude`
