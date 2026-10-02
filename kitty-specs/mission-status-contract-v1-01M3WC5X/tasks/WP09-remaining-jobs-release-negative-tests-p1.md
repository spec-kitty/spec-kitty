---
work_package_id: WP09
title: Remaining jobs, release workflow, guard tests, negative tests and preview point p1 (IC-08)
dependencies:
- WP05
- WP06
- WP07
- WP08
requirement_refs:
- FR-001
- FR-017
- FR-018
- FR-021
- FR-022
- FR-025
- NFR-003
- NFR-005
- C-005
- SC-003
- SC-006
- SC-007
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T055
- T056
- T057
- T058
- T059
- T060
history: []
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent:
- .github/workflows/contracts.yml
- .github/workflows/contracts-release.yml
- tests/ci/test_contracts_workflows.py
- contracts/tools/run_negative_cases.py
- contracts/tools/negative_cases.json
- contracts/tools/contract_resolver.py
- contracts/tools/layout_check.py
- tests/contract/test_run_negative_cases.py
- tests/contract/test_mission_status_examples.py
- tests/contract/test_layout_check.py
- tests/contract/test_breaking_check.py
- tests/contract/test_bundle.py
- tests/contract/test_citation_check.py
- tests/contract/test_client_smoke.py
- tests/contract/test_codeowners_check.py
- tests/contract/test_contract_resolver.py
- tests/contract/test_enum_pin_check.py
- tests/contract/test_event_mapping_check.py
- tests/contract/test_example_check.py
- tests/contract/test_fixture_builder.py
- tests/contract/test_install_tools.py
- tests/contract/test_leak_patterns.py
- tests/contract/test_leak_scan.py
- tests/contract/test_lint_ruleset.py
- tests/contract/test_no_pytest_scan.py
- tests/contract/test_provisional_check.py
- tests/contract/test_release_check.py
- tests/contract/test_resolver_parity.py
- tests/contract/test_schema_formats.py
- tests/contract/test_structure_check.py
- tests/contract/test_verify_pins.py
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/contracts.yml
- .github/workflows/contracts-release.yml
- tests/ci/test_contracts_workflows.py
- contracts/tools/run_negative_cases.py
- contracts/tools/negative_cases.json
- contracts/tools/contract_resolver.py
- contracts/tools/layout_check.py
- contracts/tools/fixtures/layout_check/**
- contracts/mission-status/**
- tests/contract/test_run_negative_cases.py
- tests/contract/test_mission_status_examples.py
- tests/contract/test_layout_check.py
- contracts/tools/fixtures/breaking_check/**
- contracts/tools/fixtures/bundle/**
- contracts/tools/fixtures/citation_check/**
- contracts/tools/fixtures/client_smoke/**
- contracts/tools/fixtures/codeowners_check/**
- contracts/tools/fixtures/contract_resolver/**
- contracts/tools/fixtures/enum_pin_check/**
- contracts/tools/fixtures/event_mapping_check/**
- contracts/tools/fixtures/example_check/**
- contracts/tools/fixtures/install_tools/**
- contracts/tools/fixtures/leak_scan/**
- contracts/tools/fixtures/no_pytest_scan/**
- contracts/tools/fixtures/provisional_check/**
- contracts/tools/fixtures/release_check/**
- contracts/tools/fixtures/resolver_parity/**
- contracts/tools/fixtures/spike/**
- contracts/tools/fixtures/structure_check/**
- contracts/tools/fixtures/vacuum/**
- contracts/tools/fixtures/verify_pins/**
- tests/contract/test_breaking_check.py
- tests/contract/test_bundle.py
- tests/contract/test_citation_check.py
- tests/contract/test_client_smoke.py
- tests/contract/test_codeowners_check.py
- tests/contract/test_contract_resolver.py
- tests/contract/test_enum_pin_check.py
- tests/contract/test_event_mapping_check.py
- tests/contract/test_example_check.py
- tests/contract/test_fixture_builder.py
- tests/contract/test_install_tools.py
- tests/contract/test_leak_patterns.py
- tests/contract/test_leak_scan.py
- tests/contract/test_lint_ruleset.py
- tests/contract/test_no_pytest_scan.py
- tests/contract/test_provisional_check.py
- tests/contract/test_release_check.py
- tests/contract/test_resolver_parity.py
- tests/contract/test_schema_formats.py
- tests/contract/test_structure_check.py
- tests/contract/test_verify_pins.py
- contracts/tools/fixtures/negative/**
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# WP09 - Remaining jobs, release workflow, guard tests, negative tests and preview point p1 (IC-08)

> Note on `create_intent`: finalize validation requires every literal owned path that does not exist at validation time to be listed; most entries are files earlier WPs (WP01, WP02, WP06 to WP08) create, and only `contracts-release.yml`, `test_contracts_workflows.py`, `run_negative_cases.py`, `negative_cases.json` and `test_run_negative_cases.py` are created by this WP.

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Complete the contracts workflow (`verify-pins`, `python-checks`, `negative-tests`, `needs: verify-pins` on `validate-bundle`, failing client smoke, full `contracts-gate`), add the release workflow, the workflow guard tests and the negative-case wiring, apply the conditional brace re-sweep first if the spike recorded a non-default spelling, and close IC-08 with preview point **p1**.

## Context

- Plan concern **IC-08**. **Shared-CI gate chokepoint**: `.github/workflows/contracts.yml` single-writer order WP02, WP08, WP09 (this is last; both earlier lanes are finished). It is also the first full execution of every job; the draft-PR push is the first possible green `contracts-gate`.
- Depends on WP05 (the real contract exists: with no module under `contracts/mission-status` the content jobs exit 2 by design, `NO_MODULE`/`ZERO_PATH_FILES`, and the gate could not be shown green), WP06 (content checks), WP07 (hygiene checks, pin verifier, CODEOWNERS), WP08 (lint, breaking-change, release-check, which in turn builds on WP02). Needs a rebase on current `main` before and after (orchestrator action); the workflow-count ceiling is re-verified (18 files after WP02, 19 after this WP, ceiling 20).
- **Opening commit, conditional (brace re-sweep).** Read the recorded brace `$ref` spelling (`research.md` R-3, written by the orchestrator after WP02; WP04 already applied it, so a sweep is expected not to be needed). If the spike used the time-box fallback ("IC-07a pending, default spelling provisional") and later recorded its result, compare against that final record. If the `BRACE_REF_SPELLING` in `contract_resolver.py` equals the recorded spelling there is nothing to sweep; the two branches below apply only if the spelling changed after WP04. **The re-sweep edits fixtures and tests written by earlier WPs; this WP owns exactly the earlier WPs' `test_<script>.py` modules and `contracts/tools/fixtures/<script>/**` subtrees listed in its `owned_files` for that purpose (and `contracts/tools/fixtures/negative/**` for new negative-case plants). It never touches `tests/contract/test_handoff_fixtures.py`, `contracts/fixtures/**` (C-004) or any other pre-existing `tests/contract/` module; no blanket `tests/contract/test_*.py` or `contracts/tools/fixtures/**` glob is owned.**
  - **Differs from the default**: the red-first re-sweep is the opening of this WP. First commit: plant a non-canonical `$ref` fixture for the `BRACE_REF_SPELLING` rule in `contracts/tools/fixtures/layout_check/` and a test in `tests/contract/test_layout_check.py` that is a **pre-edit red test against the unchanged `BRACE_REF_SPELLING` constant**; the constant edit in `contracts/tools/contract_resolver.py` lands in the same commit and turns it green; the path-file renames and `$ref` rewrites over `contracts/mission-status/**` (path files, root map, every `_index.yaml`, examples) follow in that commit or its immediate successor until `layout_check` is green over the whole tree; also rewrite any literal path-file name or brace `$ref` in tests and fixtures from WP01 to WP07 (acceptance grep: `grep -rn "missions_{\|%7B" tests/contract contracts/tools/fixtures` matches nothing outside the files that legitimately test the spelling: `tests/contract/test_layout_check.py`, `tests/contract/test_contract_resolver.py`, `contracts/tools/fixtures/layout_check/**` and `contracts/tools/fixtures/contract_resolver/**` (WP04 golden-tree files named with braces or `%7B` live there). Count guard: record the per-file hit counts; hits outside that named set must be zero, and the exempt files must each show at least one hit (a zero there means the test or fixture does not exercise the spelling, which is itself a failure). Same wording applies in WP09; `plan.md` is not edited (out of scope for the tasks phase) and its looser wording is deviated from here on purpose). Cause for any re-publication of an already-published preview point: `brace re-sweep` (see close-out below).
  - **Equals the default**: no re-sweep; the WP opens with its own red test, the `tests/ci/test_contracts_workflows.py` guard for the first remaining job, failing before the job exists.
- **Jobs to add** (single authority: the job table in `contracts/tools-and-workflows.md`, which `tests/ci/test_contracts_workflows.py` asserts exactly): `verify-pins` (no needs; guarded; `verify_pins.py` over `pins.json` and both workflow files), `python-checks` (no needs; guarded; the nine content/hygiene checks over the resolved tree then `no_pytest_scan.py`: ten scripts), `negative-tests` (`needs: verify-pins`; installs its own tools via `install_tools.py` because the dangling-reference, tampered-metadata, vacuum and oasdiff cases need the JVM toolchain; runs `fixture_builder.py` for leak-class plants; runs every script and tool against its planted fixtures through the wiring below, asserts the stable failure code, and runs a clean control on the same fixture root; passes only if each check failed **for the expected reason**), `validate-bundle` gains `needs: verify-pins`, the client smoke step loses `continue-on-error` (a generation failure now turns `validate-bundle` and therefore `contracts-gate` red), and `contracts-gate` lists all eight other jobs in `needs` with `if: (<canonical guard>) && always()`, failing unless every needed job is `success`. The fork guard `(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch')` is the first top-level conjunct on every root job and every `always()` job.
- **Negative-test wiring** (new files this WP owns): `contracts/tools/negative_cases.json` (a manifest: script or tool, fixture root, expected stable code, clean-control root) and `contracts/tools/run_negative_cases.py` (a small driver that runs each case, asserts the printed `CONTRACT-CHECK` code and the control, exits 0/1/2 by the same conventions; it prints a `counts:` line and exits 2 on zero cases). It is a `contracts/tools/` script like the others: stdlib only, never imports pytest, covered by `no_pytest_scan`. The planted fixtures it points at are owned by earlier WPs; it adds none except for tools without a fixture, which it adds under `contracts/tools/fixtures/negative/**` (owned here) and records. The generator-failure plant for `client_smoke` is the one recorded in `research.md` R-3 after WP02 (from a pushed run). Leak-class plants are never committed (built at run time).
- **Enum pin wiring**: the `python-checks` invocation of `enum_pin_check.py` uses the script's default pin path (`contracts/tools/enum_pins.json`, owned by WP06) and the guard tests assert that invocation names no other pin and that the default pin file is non-empty.
- **Release workflow** (`contracts-release.yml`, name `Contracts Release`, D-P5): triggers `push` of tags `contract-*-v*.*.*` and `workflow_dispatch` with a `dry_run` input defaulting to true; **no `pull_request`, no branch push**; top-level `permissions: contents: read`, the one job `contents: write`; one root job with `if: (github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'workflow_dispatch')`; same prelude, `install_tools.py`, `bundle.py`, `release_check.py --tag <ref name>`, upload, then publish steps using the runner's `gh release create` (no third-party action) each with `if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')`, always `--latest=false`, `--prerelease` only for a prerelease semver. No Node, no pytest.
- **Guard tests** (`tests/ci/test_contracts_workflows.py`; selected by the module-matrix `ci` row on any workflow edit; each first asserts it parsed at least one workflow file, job, `uses:` line, publish step and CLI release tag; a test that found nothing fails): trigger path set of `contracts.yml` is exactly the three paths and `branches: [main]`; no Node tokens (`node`, `npm`, `npx`, `yarn`, `pnpm`, `setup-node`); no pytest reachable from any step (directly, through `make` or a script); fork guard on every root job and on `contracts-gate` and the release job; every `uses:` pinned to a 40-character SHA; the exact `needs` set of every job; the publish-step condition evaluated for `pull_request`, `workflow_dispatch`, push to `main` and push of `refs/tags/contract-mission-status-v1.0.0` (false, false, false, true); zero publish steps fails; `--latest=false` present; release trigger rules (tag push `contract-*-v*.*.*` and `workflow_dispatch` with `dry_run` default true only); the **namespace guard** implementing GitHub's filter-pattern semantics (`*` does not cross `/`, `**` does), not `fnmatch`: neither trigger matches the other's tags, a tag differing only by a slash (for example one with a slash in the module part) is not matched, an empty CLI tag list fails, and the preview tags `preview/mission-status/p<N>` (including suffixed `-r<N>` forms) are matched by neither the contract release filter nor the CLI's `v*.*.*`. Each rule has a planted violating workflow text (class B evidence). Edit `tests/ci/test_contracts_workflows.py` only; do not edit `ci-module-registry.yml`.
- Workflow-file additions do not need a ledger row or a `WORKFLOW_FILES` row (neither workflow invokes pytest); `contracts/**` matches a tracked path for the coherence gate. If a gate says otherwise, stop and report.
- **Does touch**: a shared CI gate (the new workflows) but no router, fleet or registry file in this WP; **does not touch** the migration chain, runtime-state schema or event contract.
- **Open-PR overlap check (2026-10-02)**: no open PR (#5540, #5326) touches `.github/workflows/`, `tests/ci/` or `contracts/`; #5557 is closed unmerged. Re-run at start and after the rebase.
- Baseline from WP01's hand-off; red-first (C-010): first commit of each deliverable is a failing guard test or planted fixture.
- **Python hygiene and S-rules (binding for this WP)**: run `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` before the final commit and record both results (NFR-007). `contracts/tools/*.py` are non-test code, so ruff's bandit rules (`S`) apply there in full: shell out only with argument lists and `shutil.which`-resolved binaries (S603, S607), call `urlopen` only after an explicit `https` scheme check (S310), and make any suppression a one-line `# noqa: S###` with a stated rationale, never a blanket one. Run `mypy --strict` locally over new modules as discipline (no CI job). In `tests/`, never import `datetime` and never call `datetime.now()` or `time.time()` (clock-ban gates, named below): compare ISO-8601 strings or use the kernel clock door.
- Registry rows: this WP owns `tests/architectural/test_ci_corpus_trigger_completeness.py` for one purpose, a sorted row for `tests/contract/test_run_negative_cases.py`.

### Test surface, gates and baseline

- Targeted (also run `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`; the largest test file and a subprocess driver are written here): `tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py tests/ci/test_fork_guard.py tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py tests/contract/test_run_negative_cases.py tests/contract/test_layout_check.py tests/contract/test_mission_status_examples.py tests/contract/test_contract_resolver.py`, and every `contracts/tools/*.py` check run by hand against the real contract with exit codes recorded.
- Named gates: `tests/architectural/test_clock_import_ban.py tests/architectural/test_clock_call_ban.py` `tests/architectural/test_module_shard_registry.py tests/architectural/test_workflow_coherence.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_ci_corpus_trigger_completeness.py tests/release/test_pinning_inventory_fresh.py`. No directory sweep.

## Subtasks

### Subtask T055: Conditional brace re-sweep (or the first red guard test)

**Purpose**: apply the spike's spelling decision exactly once.
**Steps**: as described above; if no re-sweep, write the first failing guard test for the `verify-pins` job instead.
**Files**: if the spelling changed: `contracts/tools/contract_resolver.py`, `contracts/tools/fixtures/layout_check/**`, `tests/contract/test_layout_check.py`, `contracts/mission-status/**` (renames and `$ref` rewrites), and the literals in the earlier WPs' owned `tests/contract/test_<script>.py` modules and `contracts/tools/fixtures/<script>/**` subtrees; otherwise the first guard test in `tests/ci/test_contracts_workflows.py`.
**Validation**: `layout_check` green over `contracts/` after the sweep; the acceptance grep clean; or the new guard test red for the right reason.

### Subtask T056: Remaining jobs and gate in `contracts.yml`

**Purpose**: FR-017, FR-018, FR-021 job graph.
**Steps**: add the jobs per the job table; wire `needs`; keep SHA pins and comments; `timeout-minutes` on every job; concurrency per ref; prelude everywhere a script runs.
**Files**: `.github/workflows/contracts.yml` (third and last writer after WP02 and WP08; about 120 lines added).
**Validation**: guard tests (T058) green; read-through against the table.

### Subtask T057: Negative-case manifest and driver

**Purpose**: FR-021 class A evidence.
**Steps**: failing tests first for the driver (zero cases exits 2; a case whose check passes unexpectedly fails; wrong code fails; missing control fails); then implement `run_negative_cases.py` and populate `negative_cases.json` with one case per script and per JVM/Go tool (layout, citation, provisional, example, event mapping, enum pin, leak scan via `fixture_builder`, structure, CODEOWNERS, no-pytest, verify-pins, bundle with a dangling reference and a module without a root file, a fixture module whose schema is invalid under OpenAPI 3.1 (expected `bundle.py` code), a harness that makes the second build differ (a fixture hook that perturbs the output) expecting `BUILDS_DIFFER`, a tampered-metadata copy, client smoke plant, lint rules via vacuum, breaking-change pair, a breaking-change pair where the bundle changes while `info.version` is unchanged expecting `BUNDLE_CHANGED_VERSION_SAME`, resolver parity divergent-resolver plant, release script plants).
The manifest covers every `plan.md` Test strategy row for FR-014, FR-016 and FR-024 (each new plant has a clean control on the same root), and the driver asserts that the number of cases it ran equals the manifest length (a test plants a truncated run).
**Files**: `contracts/tools/run_negative_cases.py` (~150 lines), `contracts/tools/negative_cases.json` (~150 lines), `tests/contract/test_run_negative_cases.py` (~120 lines), `contracts/tools/fixtures/negative/**` for tools without a fixture.
**Validation**: unit tests green locally; the CI `negative-tests` job is the runner of record.

### Subtask T058: Guard tests

**Purpose**: FR-017, FR-018, FR-022 guards (class B).
**Steps**: red-first tests as listed above, each with a planted violating workflow text and a clean control.
**Files**: `tests/ci/test_contracts_workflows.py` (~500 lines), no other file.
**Validation**: file green; `tests/ci/test_fork_guard.py` green over the new jobs.

### Subtask T059: `contracts-release.yml`

**Purpose**: FR-022 release workflow.
**Steps**: write it as specified; confirm it is not a `PR_WORKFLOWS` member and `scripts/ci/fleet_main.py` needs no edit; confirm workflow count 19 and the ceiling test.
**Files**: `.github/workflows/contracts-release.yml` (new, ~80 lines), `tests/ci/test_contracts_workflows.py` (release guards).
**Validation**: guard tests green; ceiling test green.

### Subtask T060: Full local runs and a pushed-run hand-off

**Purpose**: prove the graph.
**Steps**: run every script locally against the real contract and record exit codes; run the targeted tests, gates, `ruff check .` and `ruff format --check .`; hand the orchestrator the list of what only CI can show (first full execution of every job, a green `contracts-gate`). Then record the p1 inputs (formerly a separate subtask, folded here because it produces no file): the hand-off has the fields `candidate_last_commit` (hash), `contracts_gate_run_id` (a contracts-workflow run on the draft PR whose `contracts-gate` succeeded), and `class_a_failing_runs` (one failing-run link or run id per check, for WP12).
**Files**: `tests/architectural/test_ci_corpus_trigger_completeness.py` (+1 row for `test_run_negative_cases.py`); hand-off record only otherwise.
**Validation**: green locally; the hand-off carries the three p1 fields, with the CI run identifiers filled in once the orchestrator relays them.

_Numbering note: T061 was folded into T055 and is retired; WP10 continues at T062. The gap is intentional._

## Close-out step: publish preview point `p1` (ORCHESTRATOR action, recorded in this WP)

Agents never push and never create remote tags (publication rule at the end of this section). **P1, stable marker** is the **first commit whose contracts-workflow run is green on the draft PR**, meaning `contracts-gate` succeeded (so `verify-pins`, `python-checks` with the citation, provisional, example and leak checks over the real contract, `validate-bundle` including the counted client smoke, `lint`, `resolver-parity` with its independent dereference check, `release-dry-run` and `negative-tests` all passed). After this WP is **approved** and that run exists, the immutable preview tag `preview/mission-status/p1` is published as a lightweight tag on that commit, recorded as the commit plus the run id. **Tag publication (plan E-3, identical in WP05, WP09 and WP10).** The push of the tag and the note on #5528 are maintainer acts. After this WP is approved, the orchestrator prepares the lightweight-tag command and the #5528 note and publishes them only acting for a maintainer (with that maintainer's go-ahead); agents never push and never create remote tags. Record "prepared" and "published by <maintainer, or orchestrator acting for them>" separately in the hand-off. Fallback if no maintainer publishes: a `git archive` tarball of the split tree with its sha256, posted on #5528. p1 is when generating a client for development is reasonable; the shape can still change by what WP10 forces. If p0 or p1 had been published before a brace re-sweep landed in this WP, each already-published point is re-published (same publication rule) under the next counter suffix (`-r2`, then `-r3`, independent per point; first re-publication of `p0` is `p0-r2`), each re-publication naming its cause (`brace re-sweep` or `compact history`) on #5528, the old tags staying until the UI team has moved. The tag name (not a hash) and the "prepared" versus "published by" status are recorded in this WP's hand-off for WP12.

**Orchestrator scheduling note for WP10**: the ratchet's tracker issue (owner, `drain_by`) must exist before WP10 starts; see WP10 "Precondition". Open it while this WP is in review.

## Definition of Done

- All eight jobs and `contracts-gate` exist (nine in total) with the exact `needs` of the job table; every root and `always()` job has the canonical fork guard; no unpinned `uses:`; no Node; no pytest; `timeout-minutes` everywhere; client smoke is failing, not `continue-on-error`.
- Release workflow exists with the specified triggers, permissions, guard and publish conditions; workflow count 19.
- Guard tests and negative-case driver green, red first; namespace guard covers preview tags; the negative-case manifest covers every `plan.md` Test strategy row for FR-014, FR-016 and FR-024 (3.1-invalid schema, `BUILDS_DIFFER`, `BUNDLE_CHANGED_VERSION_SAME` each with a clean control) and the driver asserts the run case count equals the manifest length; the guard tests assert the `enum_pin_check` invocation uses the default pin `contracts/tools/enum_pins.json`, non-empty.
- `ruff check .` and `ruff format --check .` clean; no S603, S607 or S310 finding left unjustified (`run_negative_cases.py` shells out); the two clock-ban gate files green.
- Conditional re-sweep done (and acceptance grep clean) or recorded as not needed.
- Every script exits 0 against the real contract; named gates green; no `src/`, router, fleet or registry-file edit in this WP.
- The p1 inputs hand-off (T060) has the fields `candidate_last_commit`, `contracts_gate_run_id` and `class_a_failing_runs`; the orchestrator step is pending or done with the tag name.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- First full execution is the draft PR; expect iteration; batch pushes.
- A skipped job read as a pass: `contracts-gate` `needs` and `always()` form is mandatory and tested.
- Re-sweep leaving a stale brace literal in an older WP's tests: the acceptance grep is the check.

## Reviewer Guidance

Diff the workflow against the job table line by line (needs, guards, pins). Run the guard tests and confirm the planted bad workflow texts fail for the intended rule. Confirm publication is unreachable from `pull_request` and `workflow_dispatch`, `--latest=false` is present, and no Node or pytest reaches either workflow. If the re-sweep happened, confirm its first commit is red against the unchanged constant.

Implementation command: `spec-kitty agent action implement WP09 --agent claude`
