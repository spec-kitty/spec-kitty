---
work_package_id: WP02
title: Workflow skeleton, shared-CI edits, toolchain bootstrap and bundler spike (IC-07a)
dependencies:
- WP01
requirement_refs:
- FR-014
- FR-017
- FR-018
- FR-019
- FR-025
- NFR-002
- NFR-003
- NFR-005
- C-003
- C-005
- SC-003
- SC-008
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
- T013
- T014
- T015
history: []
agent_profile: implementer-ivan
authoritative_surface: contracts/tools/
create_intent:
- .github/workflows/contracts.yml
- contracts/tools/install_tools.py
- contracts/tools/bundle.py
- contracts/tools/resolver_parity.py
- contracts/tools/client_smoke.py
- contracts/tools/pins.json
- tests/contract/test_install_tools.py
- tests/contract/test_bundle.py
- tests/contract/test_resolver_parity.py
- tests/contract/test_client_smoke.py
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/contracts.yml
- .github/workflows/ci-fleet-verdict.yml
- scripts/ci/fleet_verdict.py
- tests/ci/test_fleet_verdict.py
- tests/release/pinning_rule_inventory.json
- tests/ci/test_fleet_main.py
- contracts/build.gradle*
- contracts/settings.gradle*
- contracts/gradle/**
- contracts/tools/install_tools.py
- contracts/tools/bundle.py
- contracts/tools/resolver_parity.py
- contracts/tools/client_smoke.py
- contracts/tools/pins.json
- contracts/tools/fixtures/spike/**
- contracts/tools/fixtures/resolver_parity/**
- contracts/tools/fixtures/client_smoke/**
- contracts/tools/fixtures/bundle/**
- contracts/tools/fixtures/install_tools/**
- tests/contract/test_install_tools.py
- tests/contract/test_bundle.py
- tests/contract/test_resolver_parity.py
- tests/contract/test_client_smoke.py
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# WP02 - Workflow skeleton, shared-CI edits, toolchain bootstrap and bundler spike (IC-07a)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Land the minimal `contracts.yml` skeleton that can execute the bundler-fidelity and client-smoke spike on a one-module fixture, the shared-CI edits that skeleton forces (fleet-verdict entry and name), the pinned toolchain bootstrap, and the first cut of `bundle.py`, `resolver_parity.py` and `client_smoke.py`. The spike result is recorded by the orchestrator (record step below) and gates WP03 (brace spelling), WP06 and WP08.

## Context

- Plan concern **IC-07a**. Runs immediately after WP01 and before the contract content WPs (WP03 to WP05), so the CI-only feedback loop starts as early as possible and WP04 can use the recorded brace spelling (all code WPs share one lane and run in dependency order; see WP01 Context). It edits **no contract file and no resolver constant**: it records the canonical brace `$ref` spelling; any re-sweep it implies is WP09's opening commit.
- **Shared-CI gate chokepoint and single-writer order.** `.github/workflows/contracts.yml` is written by WP02, then WP08, then WP09, never in parallel (serialised by dependencies WP02, WP08, WP09). `contracts/tools/pins.json`, `bundle.py` and `install_tools.py` are created here and extended by WP08 under the same order. This WP also touches the **fleet-verdict machinery** (a shared CI gate) and the **hidden byte-for-byte pinning inventory**.
- **Edits to shared CI, complete list for this WP** (C-003): `scripts/ci/fleet_verdict.py` one `PR_WORKFLOWS` entry (`contracts.yml`); `.github/workflows/ci-fleet-verdict.yml` one name (`Contracts`) in the `workflow_run` list; `tests/ci/test_fleet_verdict.py` (also written by WP01 for the campsite commit; WP02 depends on WP01, so the writes are sequential) workflow-id fixture and expected sets; `tests/ci/test_fleet_main.py` only if a test turns red after the `PR_WORKFLOWS` edit (the plan expects no change: run it red-first and edit only if it says so). `scripts/ci/fleet_main.py`, `.github/ci-module-registry.yml` and `pytest.ini` are not edited. The new `pull_request` workflow and its `PR_WORKFLOWS` entry land in **one commit**, because a new `pull_request` workflow without its entry fails the finite inventory check closed. Regenerate `tests/release/pinning_rule_inventory.json` with `python3 scripts/ci/derive_pinning_inventory.py` in that commit (WP01 regenerated it earlier; WP02 owns it sequentially after WP01; regeneration is a hard obligation of every WP that shifts a scanned line) and run `tests/release/test_pinning_inventory_fresh.py` plus the `tests/release` directory.
- **Workflow shape (binding, `contracts/tools-and-workflows.md`, D-P4, D-P12)**: name `Contracts`; `pull_request` and `push` with exactly three paths on both (`contracts/**`, `.github/CODEOWNERS`, `.github/workflows/contracts.yml`); `push` carries `branches: [main]`, `pull_request` carries **no** `branches` key (PRs 2 to 6 of the stack target seam branches, so a `main` filter would never fire for them; D-P7, DD-21); top-level `permissions: contents: read`; concurrency per ref; every job has `timeout-minutes`; every `uses:` pinned to a full 40-character SHA with a version comment, reusing SHAs already vetted in other workflows of this repository (record which in the hand-off); Python only through the prelude (SHA-pinned checkout, SHA-pinned `astral-sh/setup-uv` with `python-version: '3.12'`, `uv sync --frozen --no-install-project`); no bare `pip install`; no Node anywhere (C-005); no pytest on any event; no caching of tool or Gradle directories. Skeleton jobs: `validate-bundle` (a **root job** here, so it carries the canonical fork guard `(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch')` as the first conjunct of its `if:`; WP09 adds `needs: verify-pins`), `resolver-parity` (`needs: validate-bundle`), and an interim `contracts-gate` listing the jobs that exist, with `if: (<canonical guard>) && always()` failing unless every needed job is `success`. The client smoke is a step of `validate-bundle`, `continue-on-error: true` **only while the spike runs**.
- **Workflow-count ceiling**: 17 workflow files at planning, 18 after this WP, 19 after WP09, ceiling 20 (`test_reusable_workflow_ceiling_respected` in `tests/architectural/test_module_shard_registry.py`). Re-verify the live count at start (the plan's reason to expect pressure, #5557, is closed unmerged; still re-count).
- **Provisioning (PQ-1)**: no committed Gradle wrapper jar. The workflow downloads the pinned Gradle distribution over HTTPS, verifies its sha256 from `contracts/tools/pins.json`, unpacks and runs it. The openapi-generator Gradle plugin and its transitive artefacts resolve under **strict Gradle dependency verification** with a committed `contracts/gradle/verification-metadata.xml` produced by `gradle --write-verification-metadata sha256 <task>` (never hand-edited). A tampered-checksum fixture is a copy under `contracts/tools/fixtures/` altered by a test helper at run time, not by hand in the real file. Versions are chosen by the implementer from vendor releases at implement time and recorded in `pins.json` with `name`, `version`, `url` (HTTPS only), `sha256`, `published` (date) and `advisory_feed_checked`; the plan invents no version. Freshness rule: an artefact published less than 14 days before the pin date is adverse and needs maintainer acknowledgement (record it; do not proceed past an adverse result without the orchestrator). Build script DSL (Groovy or Kotlin) is the implementer's choice, recorded in the hand-off.
- Tools here: `install_tools.py` (downloads over HTTPS, verifies sha256 **before** anything executes, refuses an empty manifest; codes `CHECKSUM_MISMATCH`; exit 2 `MANIFEST_EMPTY`, `DOWNLOAD_FAILED`), `bundle.py` (validate every module and bundle with the `openapi-yaml` generator; codes `BUNDLE_EMPTY`, `FEWER_THAN_FIVE_PATHS`, `UNRESOLVED_REFERENCE_LEFT`; exit 2 `NO_MODULE`, `MODULE_WITHOUT_ROOT`, `JVM_MISSING`, `GRADLE_MISSING`, `PLUGIN_RESOLUTION_FAILED`, `DEPENDENCY_VERIFICATION_FAILED`; determinism comparison is WP08), `resolver_parity.py` (first cut: dereference the CI bundle and the resolver's tree, compare ignoring key order after the named normalisations capped at `MAX_NORMALISATIONS = 8`; codes `TREE_DIFFERS` naming the first differing JSON pointer, `UNDOCUMENTED_NORMALISATION`, `NORMALISATION_CAP_EXCEEDED`, `INDEPENDENT_DEREF_DISAGREES`; exit 2 `RESOLVER_IMPORT_FAILED`, `BUNDLE_MISSING_OR_EMPTY`, `BELOW_FLOOR` for fewer than five path items, zero schemas, zero resolved refs; prints the counts), `client_smoke.py` (openapi-generator TypeScript client generation through the pinned Gradle build against the **split** root of every module, generation only, output not compiled; codes `GENERATION_FAILED`; exit 2 `NO_MODULE`, `ZERO_FILES_EMITTED`, `JVM_MISSING`, `GRADLE_MISSING`; prints `modules`, `files_emitted`, `generator_warnings`). Every script follows the conventions: stdlib plus locked dependencies only, never imports pytest, `tests/` or `scripts.`, prints `CONTRACT-CHECK <name>: <CODE>: <detail>` and a final `counts:` line, exit 0/1/2. Checksum code carries a one-line `# noqa: TID251` with a file-integrity rationale.
- **The independent dereference check** (D-P2): validates every committed example against its schema twice, once through the resolver's tree and once through `jsonschema` with a `referencing.Registry` that retrieves the split files itself (library resolution, no code from `contract_resolver.py`), using `schema_formats.FORMAT_CHECKER`; fails when the two verdicts differ for any example, planted invalid ones included. The parity script is a consistency check, never described as an independent proof.
- **CI-only feedback loop (tracer F-7)**: there is no JVM, Gradle, vacuum or oasdiff on the workstation, so the JVM steps are exercised only by pushing to PR 1 (a draft). The agent never pushes; the orchestrator pushes the branch and relays run results, **after the orchestrator pre-step below has opened PR 1 (the draft)** (the workflow triggers only on `pull_request` and on push to `main`, so no spike run can exist before PR 1). Plan for several iterations; keep every Python script locally testable. The spike is time-boxed (see the record step).
- **Python hygiene and S-rules (binding for this WP)**: run `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` before the final commit and record both results (NFR-007). `contracts/tools/*.py` are non-test code, so ruff's bandit rules (`S`) apply there in full: shell out only with argument lists and `shutil.which`-resolved binaries (S603, S607), call `urlopen` only after an explicit `https` scheme check (S310), and make any suppression a one-line `# noqa: S###` with a stated rationale, never a blanket one. Run `mypy --strict` locally over new modules as discipline (no CI job). In `tests/`, never import `datetime` and never call `datetime.now()` or `time.time()` (clock-ban gates, named below): compare ISO-8601 strings or use the kernel clock door.
- **Exit criterion** (what the orchestrator record step below writes into `research.md` R-3): the spike table (named normalisations, canonical brace `$ref` spelling tested against the Python resolver, the Java parser and a generated TypeScript client, client-smoke result), E-1 and E-4 closed or escalated, and, from a pushed run, the exact plant that makes the pinned generator exit non-zero (a dangling `$ref` target is a candidate, not an assumption; if the generator only warns and still emits files, the warning text that `client_smoke.py` counts and fails on). WP06 and WP08 do not start before it is recorded.
- Baseline from WP01's hand-off; overlap check 2026-10-02: #5540 and #5326 touch none of this WP's files (`.github/workflows/`, `scripts/ci/`, `tests/ci/`, `contracts/`); re-run at start.
- Red-first (C-010): first commit per tool is a failing unit test or planted fixture; the skeleton's first commit is the failing `PR_WORKFLOWS`/fleet test edit.
- Does not touch the migration chain, runtime-state schema or event contract.

### Test surface, gates and baseline

- Targeted: `tests/contract/test_install_tools.py tests/contract/test_bundle.py tests/contract/test_resolver_parity.py tests/contract/test_client_smoke.py tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py tests/ci/test_fork_guard.py`.
- Named gates: `tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py` `tests/architectural/test_module_shard_registry.py tests/architectural/test_workflow_coherence.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_ci_corpus_trigger_completeness.py tests/release/test_pinning_inventory_fresh.py` and the `tests/release` directory. No architectural directory sweep. Append sorted registry rows for the four new corpus-marked unit-test modules (declared exception, out-of-map edit).

## Subtasks

### Subtask T009: Fleet-verdict edits, red-first, with the skeleton file

**Purpose**: the one-commit pairing of a new `pull_request` workflow and its inventory entry.

**Steps**:
1. Edit `tests/ci/test_fleet_verdict.py` first (workflow-id fixture gains the contracts entry; the `pyproject.toml` diff expects `PR_WORKFLOWS` minus the contracts workflow; the `docs/example.md` diff keeps its existing exclusions and also excludes the contracts workflow; a `contracts/` path case expects it). Run it: red.
2. In one commit add `scripts/ci/fleet_verdict.py` entry, the `Contracts` name in `ci-fleet-verdict.yml`'s `workflow_run` list, a first `.github/workflows/contracts.yml`, and the regenerated inventory. Run the fleet tests green; run `tests/ci/test_fleet_main.py` and edit it only if a test says so (the plan expects none: record the result either way).
3. Run `tests/ci/test_fork_guard.py` (the discovered-jobs parametrisation covers the new jobs).

**Files**: `tests/ci/test_fleet_verdict.py` (first), `scripts/ci/fleet_verdict.py` (+1 entry), `.github/workflows/ci-fleet-verdict.yml` (+1 name), `.github/workflows/contracts.yml` (new skeleton; first of the writers WP02, WP08, WP09), `tests/release/pinning_rule_inventory.json` (derived), `tests/ci/test_fleet_main.py` (only if a test says so).
**Validation**: all named files green; inventory freshness green.

### Subtask T010: Toolchain bootstrap: `pins.json`, Gradle build, verification metadata, `install_tools.py`

**Purpose**: FR-018 pinned and verified install path for the JDK, Gradle and plugin.

**Steps**:
1. Failing tests first (`test_install_tools.py`): altered checksum, missing checksum, empty manifest, non-HTTPS URL each fail with the right code before any execution; clean control on the same fixture manifest.
2. Implement `install_tools.py`; create `pins.json` (JDK setup action is a `uses:` SHA, not a download; Gradle distribution; plugin entries) with every field populated and the freshness check recorded.
3. Create `contracts/build.gradle*` and `contracts/settings.gradle*` (a build that validates each module and bundles with the `openapi-yaml` generator, and exposes a TypeScript client generation task for the smoke), run `gradle --write-verification-metadata sha256 <task>` in CI (or document why it must be done on a runner) to produce `contracts/gradle/verification-metadata.xml` in strict mode; never hand-edit it. XML is read, if at all, by a narrow regex or a justified suppression (ruff S314 forbids `xml.etree`).

**Files**: `contracts/tools/install_tools.py` (~150 lines), `contracts/tools/pins.json` (created here; WP08 appends), `contracts/build.gradle*`, `contracts/settings.gradle*`, `contracts/gradle/**` (generated), `tests/contract/test_install_tools.py`, `contracts/tools/fixtures/install_tools/**`.
**Validation**: unit tests green; the workflow step fails on a planted tampered metadata copy (the copy is made at run time by a helper).

### Subtask T011: `bundle.py` first cut

**Purpose**: FR-014 validate and bundle.

**Steps**: failing unit tests with fixtures (module without root file, empty output, fewer than five path items in a fixture bundle) then `bundle.py`; discovery per the script conventions (module = direct subdirectory with a root `openapi.yaml`; `_shared`, `fixtures`, `gradle`, `tools` never modules); output staged outside the repository tree (the bundle is never committed; a tracked bundle fails `layout_check`).

**Files**: `contracts/tools/bundle.py` (~200 lines; WP08 extends it with determinism), `tests/contract/test_bundle.py`, `contracts/tools/fixtures/bundle/**`.
**Validation**: unit tests green; on the spike module the CI job produces a non-empty bundle.

### Subtask T012: `resolver_parity.py` and the independent dereference check

**Purpose**: FR-019 first cut, D-P2.

**Steps**: failing tests with a planted divergent resolver (a copy that drops one `$ref` target or alters one schema, under `contracts/tools/fixtures/resolver_parity/`) and a planted resolver defect that both sides share (the independent check disagrees); cap test for `MAX_NORMALISATIONS`; then implement. The normalisation list starts **empty**; entries are added only from the spike's observations, each naming the construct and tool behaviour with a planted unit test; an entry that drops information is an E-1 decision for the maintainers, not a normalisation.

**Files**: `contracts/tools/resolver_parity.py` (~250 lines), `tests/contract/test_resolver_parity.py`, `contracts/tools/fixtures/resolver_parity/**`.
**Validation**: unit tests green; counts printed (`path_items`, `schemas`, `refs_resolved`, `normalisations`, `examples_cross_checked`).

### Subtask T013: `client_smoke.py`

**Purpose**: D-P13 generate-from-split smoke.

**Steps**: failing tests first for the exit-2 conditions and `GENERATION_FAILED`; implement; the actual failing plant is recorded from a pushed run (the orchestrator records it in `research.md`; a fixture under `contracts/tools/fixtures/client_smoke/` captures it with a clean control).

**Files**: `contracts/tools/client_smoke.py` (~150 lines), `tests/contract/test_client_smoke.py`, `contracts/tools/fixtures/client_smoke/**`.
**Validation**: unit tests green; step prints the counted result in CI.

### Subtask T014: The spike module and skeleton jobs

**Purpose**: execute the spike.

**Steps**:
1. Under `contracts/tools/fixtures/spike/` create a one-module fixture (fixture data may hold the candidate brace spellings literally; the tests that run it, `test_resolver_parity.py` and `test_bundle.py`, read candidates from the fixture or derive from `BRACE_REF_SPELLING` and hold no literal: Rule BRACE-1 in WP01) using every construct the contract needs: object-valued `x-source`, structured `x-derived`, `x-provisional` on nested properties; `unevaluatedProperties`; type arrays such as `["string","null"]`; `const`; sibling keywords beside `$ref`; `format: date-time`; `pattern`; a `text/event-stream` response with a schema; `examples`; chained refs through an `_index.yaml`; a ref leaving the module into `../_shared/`; a path-item `$ref` in the root `paths` map; and brace-named files referenced in both the default spelling and, if needed, a candidate alternative.
2. Fill `contracts.yml` with `validate-bundle`, `resolver-parity`, the interim `contracts-gate`, and the smoke step as above, pointing the spike at the fixture root through the `--root` parameter.
3. Hand the exact pushed-run results to the orchestrator for the record step below.

**Files**: `contracts/tools/fixtures/spike/**` (~15 small YAML files), `.github/workflows/contracts.yml` (second write in this WP, still the first writer overall).
**Validation**: workflow guard shape checked locally by reading it against `contracts/tools-and-workflows.md`; the CI result is the spike evidence.

### Subtask T015: Registry rows and final local runs

**Purpose**: keep the completeness gate green.

**Steps**: append sorted registry rows for the four new test modules; run targeted and gate files; run `ruff check .` and `ruff format --check .`; record counts.

**Files**: `tests/architectural/test_ci_corpus_trigger_completeness.py` (+4 rows).
**Validation**: all green.

## Orchestrator pre-step: push the branch and open the draft PR (precondition of the CI-only spike; not an agent action)

Before any spike run (the first push of T014's skeleton), the **orchestrator** pushes the mission branch and opens **PR 1**, a **DRAFT** pull request targeting `main` (the first of the six stacked seam PRs, operator ruling of 2026-10-02, DD-21; see the PR shape paragraph in WP01), and records the PR number in the hand-off and in the WP12 evidence list. PR 1 carries WP01 and WP02; its seam branch is cut at this WP's head. PRs 2 to 6 are opened later, each no later than the end of its seam (PR 4 opens at WP08's first push). All six stay drafts until a maintainer acknowledges the design on #5528 (C-001, SC-010); none is marked ready by an agent or by the orchestrator. Agents never push and never open pull requests. WP08, WP09 and WP12 rely on PR 1 already existing; WP12 only finalises the bodies.

## Orchestrator record step: IC-07a exit criterion (writes `kitty-specs/`, so not an agent action)

**Completion of IC-07a is exactly this record.** After the pushed spike run the orchestrator writes into `research.md`, from this WP's hand-off and the run results it relays: (1) in R-3, the table of named normalisations (construct, tool behaviour, planted test name; cap eight; an entry that drops information is an E-1 decision), the canonical brace `$ref` spelling tested against the Python resolver, the Java parser and the generated TypeScript client (say whether it equals the default `%7B`/`%7D`), the client-smoke counts, and the exact plant that makes the pinned generator exit non-zero (or the warning text `client_smoke.py` fails on); (2) the E-1 and E-4 outcomes, closed or escalated (no workable spelling is escalation E-4: stop the Mission and ask the maintainers); (3) in R-9, the five supply-chain control rows for the JDK, Gradle and plugin (repositories, publication dates against the 14-day rule, advisory feeds consulted, adverse list); (4) the closing sentence "IC-07a complete: IC-05 and IC-07b may start", dated. It commits this with `spec-kitty safe-commit` on the planning surface **before dispatching WP03 and before WP06 and WP08 are claimed**. Those WPs verify the sentence as a precondition (read-only: `git show <target-branch>:kitty-specs/mission-status-contract-v1-01M3WC5X/research.md`). WP12 re-verifies the record.

**Time-box and fallback (the plan's provisional-spelling clause).** The spike must not hold p0 hostage. Limit: 4 pushed spike iterations or 5 calendar days after PR 1 opens, whichever comes first (the orchestrator may adjust the limit and records the figure it chose). If the spike has not produced the record by then, the orchestrator writes into `research.md` R-3, dated, the sentence "IC-07a pending, default spelling provisional" (naming what is still open), commits it with `spec-kitty safe-commit`, and may then release WP03 and WP04 under the plan's provisional-spelling clause: they use the default `BRACE_REF_SPELLING` (percent-encoded `%7B`/`%7D`) provisionally. If the spike later records a different spelling, WP09's opening re-sweep applies it and each already-published preview point is re-published with the cause `brace re-sweep`. The fallback releases **WP03 to WP05 only**: WP06 and WP08 still require the full "IC-07a complete" sentence.

## Definition of Done

- Skeleton workflow, `PR_WORKFLOWS` entry, `workflow_run` name and regenerated inventory landed together; fleet and fork-guard tests green; `fleet_main.py` and the module registry untouched; `test_fleet_main.py` edited only if red.
- `install_tools.py`, `bundle.py`, `resolver_parity.py`, `client_smoke.py`, `pins.json`, Gradle build and verification metadata exist with unit tests (planted violation plus clean control each, asserting the stable code).
- The orchestrator pre-step is recorded (PR 1 number; PR still a draft; seam 1 branch cut at this WP's head).
- A pushed run has executed the spike; its raw results are in the hand-off for the orchestrator record step (or the time-box fallback sentence was recorded).
- Workflow file count recorded (expected 18); ceiling test green.
- `ruff check .` and `ruff format --check .` clean; no S603, S607 or S310 finding left unjustified; the two clock-ban gate files green.
- No `src/` change; no contract file or resolver constant edited.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- Bundler may drop or rewrite 3.1 constructs (P-1, E-1) or no single brace spelling may work (E-4): escalate to the orchestrator; never swap the tool or add a per-tool workaround yourself.
- Supply-chain adverse result (young release or advisory): stop and report.
- Hidden inventory gate: regenerate in the same commit.
- Slow CI-only loop: batch changes per push.

## Reviewer Guidance

Check the commit pairing (entry plus workflow plus inventory), exact `needs`, fork guard on every root and `always()` job, SHA-pinned `uses:` with comments, the prelude as the only Python install form, no Node, no pytest, no caching. Check `pins.json` entries are complete and HTTPS-only, and verification metadata is generated, not hand-written. Verify red-then-green per tool.

Implementation command: `spec-kitty agent action implement WP02 --agent claude`
