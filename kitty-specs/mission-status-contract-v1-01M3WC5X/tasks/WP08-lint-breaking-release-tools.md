---
work_package_id: WP08
title: Lint, breaking-change and release-check tools with their workflow jobs (IC-07b)
dependencies:
- WP07
requirement_refs:
- FR-014
- FR-015
- FR-016
- FR-018
- FR-021
- FR-022
- FR-024
- NFR-002
- NFR-003
- SC-003
- SC-006
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T048
- T049
- T050
- T051
- T052
- T053
- T054
history: []
agent_profile: implementer-ivan
authoritative_surface: contracts/tools/
create_intent:
- .github/workflows/contracts.yml
- contracts/tools/breaking_check.py
- contracts/tools/release_check.py
- contracts/tools/bundle.py
- contracts/tools/install_tools.py
- contracts/tools/pins.json
- tests/contract/test_breaking_check.py
- tests/contract/test_release_check.py
- tests/contract/test_lint_ruleset.py
- tests/contract/test_bundle.py
- tests/contract/test_install_tools.py
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/contracts.yml
- contracts/lint/**
- contracts/tools/breaking_check.py
- contracts/tools/release_check.py
- contracts/tools/bundle.py
- contracts/tools/install_tools.py
- contracts/tools/pins.json
- contracts/tools/fixtures/vacuum/**
- contracts/tools/fixtures/breaking_check/**
- contracts/tools/fixtures/release_check/**
- tests/contract/test_breaking_check.py
- tests/contract/test_release_check.py
- tests/contract/test_lint_ruleset.py
- tests/contract/test_bundle.py
- tests/contract/test_install_tools.py
- contracts/tools/fixtures/bundle/**
- contracts/tools/fixtures/install_tools/**
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# WP08 - Lint, breaking-change and release-check tools with their workflow jobs (IC-07b)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add the vacuum lint ruleset and job, `breaking_check.py` (oasdiff) with its job, `release_check.py` with the `release-dry-run` job, the double-build determinism in `bundle.py`, and the remaining `pins.json` entries, extending `contracts.yml` after WP02.

## Context

- Plan concern **IC-07b**. Follows WP07 in the single code lane; builds on **WP02** (the skeleton workflow, `bundle.py`, `install_tools.py` and `pins.json` it extends). **Precondition (verify read-only, stop and report if absent):** the dated sentence "IC-07a complete" is in `research.md` R-3 on the target branch (normalisations, brace spelling, smoke result, generator-failure plant, E-1 and E-4 closed or escalated). The plan allowed a parallel lane; see the lane model in WP01.
- **Shared-CI gate chokepoint, single writer.** `.github/workflows/contracts.yml` order: WP02, then WP08 (this), then WP09, never in parallel. This WP adds the jobs `lint`, `breaking-change` and `release-dry-run`, each `needs: validate-bundle`, and extends the interim `contracts-gate` (the gate's `needs` set gains the three; the gate keeps `if: (<canonical guard>) && always()`). `bundle.py`, `install_tools.py` and `pins.json` are WP02's files extended here (sequential). No edit to the shared repository CI files (router, fleet verdict, module registry) happens here, so the pinning inventory is not shifted; if an edit nevertheless shifts a scanned line, regenerate by script and run the freshness test.
- **CI-only feedback, moved early.** Because this WP owns its three jobs, `lint`, `breaking-change` and `release-dry-run` first execute on the draft PR at this WP's own push, before WP09. The permanent planted proof for vacuum and oasdiff (the `negative-tests` job) first executes at WP09; until then record one pushed planted input per tool and its log excerpt in the hand-off for the orchestrator record step below. The agent never pushes; the orchestrator pushes and relays results.
- Binding tool behaviours (`contracts/tools-and-workflows.md`):
  - **Lint**: Spectral-format ruleset kept under `contracts/` (this WP creates the directory `contracts/lint/`, so the ruleset is not mistaken for a module: no root `openapi.yaml` there; the exact file name is the implementer's choice, recorded in the hand-off), run by vacuum (Go binary) over each bundle. Rules (FR-015): `operationId` present and unique; every operation tagged; every non-2xx response references `Problem`; every schema property described; `x-source` or `x-derived` on resource schema properties; no forbidden property name; enum values in a fixed case convention; closed response schemas. Each rule has a planted-violation fixture under `contracts/tools/fixtures/vacuum/` and the clean fixture passes under the same ruleset. Lint fails when the ruleset is missing or empty, zero rules load, zero files are linted, the binary is missing or its checksum mismatches. A planted path file declaring a non-2xx response with another content type must fail (FR-002).
  - **Breaking-change** (`breaking_check.py`, D-P6): rebuild the baseline from the latest tag matching `contract-<module>-v<semver>` (list tags; fail on a shallow clone via `git rev-parse --is-shallow-repository` or a tag-listing error), extract the module and `_shared/` with `git archive` into a temporary directory, build with the same pinned Gradle build, compare with oasdiff. Breaking (removed path, removed or renamed response property, narrowed enum, newly required parameter, changed type) fails unless `info.version` moves its major (`BREAKING_WITHOUT_MAJOR`); a bundle change with no `info.version` change fails (`BUNDLE_CHANGED_VERSION_SAME`); no baseline and not the initial version fails (`NO_BASELINE_NOT_INITIAL`); the one allowed state prints `NO_BASELINE_INITIAL_VERSION` loudly and writes the job summary, and only when `info.version` is the initial version and the CHANGELOG carries the initial entry. Changes confined to `x-provisional` elements do not fail and are reported in their own section (`provisional_changes` in the `counts:` line, planted and asserted). Until the first release tag exists the job also prints an **informational, never failing** report against the latest tag under `preview/mission-status/` (`PREVIEW_DELTA` lines, `preview_ref=<name>` in `counts:`, `PREVIEW_REF_NONE` when none exists; it never changes an exit status). Exit 2: `SHALLOW_CHECKOUT`, `TAG_LIST_ERROR`, `BASELINE_UNBUILDABLE`, `OASDIFF_MISSING`. Negative proof against a committed baseline-and-candidate fixture pair under `contracts/tools/fixtures/breaking_check/` (outside module discovery) with a clean control: removed property, removed path, newly required parameter, narrowed enum, changed type each fail without a major move and pass with one.
  - **Release script** (`release_check.py`, FR-022, D-17): `--root` and either `--tag <tag>` or none (derive `contract-<module>-v<info.version>` for every discovered module); apply tag rules (`contract-<module>-v<semver>`; module exists; semver equals `info.version`; the module `CHANGELOG.md` has a heading for that version); build through the shared build wrapper; write `openapi.yaml.sha256`; verify with `sha256sum -c` semantics; print the exact `gh release create` argument list it would use (always `--latest=false`, `--prerelease` only for a prerelease semver); never publish. Codes `TAG_FORM`, `MODULE_UNKNOWN`, `VERSION_MISMATCH`, `CHANGELOG_HEADING_MISSING`, `CHECKSUM_MISMATCH`; exit 2 `NO_MODULE`, `MODULE_ROOT_EMPTY`, `BUNDLE_EMPTY`. Planted fixture modules under `contracts/tools/fixtures/release_check/` (version without a CHANGELOG heading; mismatched version) with a clean control module on the same root.
  - **Determinism** (NFR-002): `bundle.py` builds twice and compares sha256 digests (`BUILDS_DIFFER`); the bundle is uploaded as a workflow artifact and never committed.
- Supply chain (DIRECTIVE_051; R-9): vacuum and oasdiff are Go binaries downloaded only from their vendors' official HTTPS release locations, version pinned, sha256 recorded in `pins.json` **verified before the binary executes** by `install_tools.py`, never piped to a shell; record `published` dates (a version published less than 14 days before the pin date is adverse: stop and report) and the advisory feeds consulted. Hand the five-control evidence to the orchestrator record step below. Checksum code carries `# noqa: TID251` with the file-integrity rationale.
- Conventions as in WP06 (scripts: stdlib plus locked dependencies, never pytest/`tests/`/`scripts.`, `CONTRACT-CHECK <name>: <CODE>: <detail>`, `counts:`, exit 0/1/2). Python in the contracts workflow only through the shared prelude (D-P12). The fork guard applies to root jobs and `always()` jobs; the three new jobs have `needs`, so none needs it, `contracts-gate` keeps it.
- Version choices are the implementer's, recorded from vendor releases at implement time; the plan invents none.
- Baseline from WP01's hand-off; overlap check 2026-10-02: no open PR touches `.github/workflows/` or `contracts/`. Re-run at start. Does not touch the migration chain, runtime-state schema or event contract.
- Registry rows: this WP owns `tests/architectural/test_ci_corpus_trigger_completeness.py` for one purpose, sorted rows for the corpus-marked unit-test modules added (`test_breaking_check.py`, `test_release_check.py`, `test_lint_ruleset.py`).

### Test surface, gates and baseline

- Targeted: `tests/contract/test_breaking_check.py tests/contract/test_release_check.py tests/contract/test_lint_ruleset.py tests/contract/test_bundle.py tests/contract/test_install_tools.py`; `tests/ci/test_fork_guard.py tests/ci/test_fleet_verdict.py`.
- Named gates: `tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_workflow_coherence.py tests/architectural/test_no_duplicate_suite_execution.py`. Plus ruff. No directory sweep.

## Subtasks

### Subtask T048: Lint ruleset, fixtures and `lint` job

**Purpose**: FR-015.
**Steps**: failing fixtures first (one planted violation per rule plus a clean control under the same ruleset; empty ruleset; zero rules; zero files linted); then the ruleset in `contracts/lint/`; a unit test module `test_lint_ruleset.py` that parses the ruleset in Python and asserts each rule id the FR requires is present and non-empty (vacuum itself runs only in CI); add the `lint` job (`needs: validate-bundle`, `install_tools.py`, vacuum over each bundle; fails on the empty-input conditions).
**Files**: ruleset (~120 lines), fixtures, test (~80 lines), job (~25 lines).
**Validation**: unit test green; pushed run: planted input fails for the expected reason, clean control passes (log excerpt recorded).

### Subtask T049: `breaking_check.py` and its fixtures

**Purpose**: FR-016.
**Steps**: failing tests first for each breaking class, provisional-only change, no-baseline states, shallow checkout, tag-listing error (use a throw-away git repository in a temp directory for tag and shallow states); implement; wire PREVIEW_DELTA mode against `preview/mission-status/*` tags.
**Files**: ~320 lines plus tests (~300) and fixture pairs.
**Validation**: unit tests green with oasdiff mocked at the process boundary only where it is unavailable locally; real oasdiff exercised in CI.

### Subtask T050: `release_check.py` and its fixtures

**Purpose**: FR-022 script.
**Steps**: failing tests first for each tag rule violation and `NO_MODULE`; implement with the shared build wrapper (call `bundle.py`, do not duplicate its logic); print the `gh release create` argument list in dry-run mode.
**Files**: ~220 lines plus tests and fixture modules.
**Validation**: argument list contains `--latest=false`; prerelease semver adds `--prerelease`.

### Subtask T051: Determinism in `bundle.py`

**Purpose**: NFR-002.
**Steps**: failing test first (two differing builds simulated by fixture outputs) then double-build digest comparison and `BUILDS_DIFFER`; upload step in the job.
**Validation**: unit test green; CI shows equal digests.

### Subtask T052: `pins.json` appends and `install_tools.py` extension

**Purpose**: FR-018 for the Go tools.
**Steps**: failing tests (altered checksum, missing checksum for the new entries) then append vacuum and oasdiff entries with all fields; `install_tools.py` installs them only after verification.
**Validation**: `verify_pins.py` (WP07) accepts the manifest once merged; locally validate the entries by reading them against the shape in `contracts/tools-and-workflows.md`.

### Subtask T053: Jobs `breaking-change` and `release-dry-run`, gate extension

**Purpose**: FR-016, FR-022 jobs.
**Steps**: add `breaking-change` (full-history checkout with tags, `needs: validate-bundle`, job summary for the no-baseline state), `release-dry-run` (`needs: validate-bundle`, uploads `release-dry-run-<module>`), extend `contracts-gate`'s `needs`. SHA-pin every `uses:` with a version comment; no Node; no pytest; every job has `timeout-minutes`.
**Validation**: read against the job table in `contracts/tools-and-workflows.md`; the exact `needs` sets are asserted later by WP09's guard tests.

### Subtask T054: Registry rows, local runs and the pushed-run hand-off

**Purpose**: close.
**Steps**: append sorted registry rows; run the targeted tests, gates and ruff; produce the hand-off for the orchestrator record step: tool versions, publication dates, advisory feeds, one pushed planted input per tool with the log excerpt, and the `lint`/`breaking-change`/`release-dry-run` first-run results.
**Validation**: green; hand-off complete.

## Orchestrator record step: IC-07b tooling and supply-chain evidence (writes `kitty-specs/`, so not an agent action)

After this WP is approved and its pushed run has executed, the orchestrator writes into `research.md`, from this WP's hand-off and the relayed run results: R-2 chosen versions and publication dates for all pinned artefacts (copied from `contracts/tools/pins.json`), the R-9 five-control rows for vacuum and oasdiff (adverse results need explicit maintainer acknowledgement), and, per tool, one pushed planted input with its expected failure reason, a short log excerpt (no tokens or personal data) and run identifier plus the first-run results of `lint`, `breaking-change` and `release-dry-run`. It commits with `spec-kitty safe-commit` on the planning surface. WP12 re-verifies the record and adds the WP09 `negative-tests` results.

## Definition of Done

- Ruleset, three tools' unit tests (planted plus clean control, codes asserted), three workflow jobs and extended gate exist; first commit per tool is red.
- Every Go and JVM download is pinned, HTTPS-only, checksum-verified before execution; no adverse freshness result left unacknowledged.
- Pushed-run evidence (one planted input per tool plus log excerpt) is in the hand-off.
- `contracts.yml` has no unpinned `uses:`, no Node, no pytest, every job has `timeout-minutes`.
- Registry rows appended in sorted order; gates green.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- Go-binary or oasdiff behaviour differs from the fixtures: iterate on CI; keep Python logic locally testable.
- Baseline rebuild needs tags that a shallow checkout hides: the job must fail, not guess.
- A fixture module accidentally discovered as a real module: fixtures live under `contracts/tools/fixtures/` and `contracts/lint/` holds no root `openapi.yaml`.

## Reviewer Guidance

Verify each tool's failure is asserted by code with a clean control on the same root, that the baseline path never silently passes, that provisional changes are reported separately, that the argument list always has `--latest=false`, and that the workflow diff only appends jobs and extends the gate. Check supply-chain evidence is present for each new artefact.

Implementation command: `spec-kitty agent action implement WP08 --agent claude`
