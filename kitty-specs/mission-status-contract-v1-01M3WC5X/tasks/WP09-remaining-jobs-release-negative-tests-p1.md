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
- T061
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
- tests/architectural/test_ci_corpus_trigger_completeness.py
role: implementer
tags: []
tracker_refs: []
---

# WP09 - Remaining jobs, release workflow, guard tests, negative tests and preview point p1 (IC-08)

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
- **Opening commit, conditional (brace re-sweep).** Read the recorded brace `$ref` spelling (`research.md` R-3, written by the orchestrator after WP02; WP04 already applied it, so a sweep is expected not to be needed). If the `BRACE_REF_SPELLING` in `contract_resolver.py` equals the recorded spelling there is nothing to sweep; the two branches below apply only if the spelling changed after WP04.
  - **Differs from the default**: the red-first re-sweep is the opening of this WP. First commit: plant a non-canonical `$ref` fixture for the `BRACE_REF_SPELLING` rule in `contracts/tools/fixtures/layout_check/` and a test in `tests/contract/test_layout_check.py` that is a **pre-edit red test against the unchanged `BRACE_REF_SPELLING` constant**; the constant edit in `contracts/tools/contract_resolver.py` lands in the same commit and turns it green; the path-file renames and `$ref` rewrites over `contracts/mission-status/**` (path files, root map, every `_index.yaml`, examples) follow in that commit or its immediate successor until `layout_check` is green over the whole tree; also rewrite any literal path-file name or brace `$ref` in tests and fixtures from WP01 to WP07 (acceptance grep: `grep -rn "missions_{\|%7B" tests/contract contracts/tools/fixtures` matches nothing outside `layout_check`'s own planted fixtures). Cause for any re-publication of an already-published preview point: `brace re-sweep` (see close-out below).
  - **Equals the default**: no re-sweep; the WP opens with its own red test, the `tests/ci/test_contracts_workflows.py` guard for the first remaining job, failing before the job exists.
- **Jobs to add** (single authority: the job table in `contracts/tools-and-workflows.md`, which `tests/ci/test_contracts_workflows.py` asserts exactly): `verify-pins` (no needs; guarded; `verify_pins.py` over `pins.json` and both workflow files), `python-checks` (no needs; guarded; the nine content/hygiene checks over the resolved tree then `no_pytest_scan.py`: ten scripts), `negative-tests` (`needs: verify-pins`; installs its own tools via `install_tools.py` because the dangling-reference, tampered-metadata, vacuum and oasdiff cases need the JVM toolchain; runs `fixture_builder.py` for leak-class plants; runs every script and tool against its planted fixtures through the wiring below, asserts the stable failure code, and runs a clean control on the same fixture root; passes only if each check failed **for the expected reason**), `validate-bundle` gains `needs: verify-pins`, the client smoke step loses `continue-on-error` (a generation failure now turns `validate-bundle` and therefore `contracts-gate` red), and `contracts-gate` lists all eight other jobs in `needs` with `if: (<canonical guard>) && always()`, failing unless every needed job is `success`. The fork guard `(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch')` is the first top-level conjunct on every root job and every `always()` job.
- **Negative-test wiring** (new files this WP owns): `contracts/tools/negative_cases.json` (a manifest: script or tool, fixture root, expected stable code, clean-control root) and `contracts/tools/run_negative_cases.py` (a small driver that runs each case, asserts the printed `CONTRACT-CHECK` code and the control, exits 0/1/2 by the same conventions; it prints a `counts:` line and exits 2 on zero cases). It is a `contracts/tools/` script like the others: stdlib only, never imports pytest, covered by `no_pytest_scan`. The planted fixtures it points at are owned by earlier WPs; it adds none except for tools without a fixture, which it records. The generator-failure plant for `client_smoke` is the one recorded in `research.md` R-3 after WP02 (from a pushed run). Leak-class plants are never committed (built at run time).
- **Release workflow** (`contracts-release.yml`, name `Contracts Release`, D-P5): triggers `push` of tags `contract-*-v*.*.*` and `workflow_dispatch` with a `dry_run` input defaulting to true; **no `pull_request`, no branch push**; top-level `permissions: contents: read`, the one job `contents: write`; one root job with `if: (github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'workflow_dispatch')`; same prelude, `install_tools.py`, `bundle.py`, `release_check.py --tag <ref name>`, upload, then publish steps using the runner's `gh release create` (no third-party action) each with `if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')`, always `--latest=false`, `--prerelease` only for a prerelease semver. No Node, no pytest.
- **Guard tests** (`tests/ci/test_contracts_workflows.py`; selected by the module-matrix `ci` row on any workflow edit; each first asserts it parsed at least one workflow file, job, `uses:` line, publish step and CLI release tag; a test that found nothing fails): trigger path set of `contracts.yml` is exactly the three paths and `branches: [main]`; no Node tokens (`node`, `npm`, `npx`, `yarn`, `pnpm`, `setup-node`); no pytest reachable from any step (directly, through `make` or a script); fork guard on every root job and on `contracts-gate` and the release job; every `uses:` pinned to a 40-character SHA; the exact `needs` set of every job; the publish-step condition evaluated for `pull_request`, `workflow_dispatch`, push to `main` and push of `refs/tags/contract-mission-status-v1.0.0` (false, false, false, true); zero publish steps fails; `--latest=false` present; release trigger rules (tag push `contract-*-v*.*.*` and `workflow_dispatch` with `dry_run` default true only); the **namespace guard** implementing GitHub's filter-pattern semantics (`*` does not cross `/`, `**` does), not `fnmatch`: neither trigger matches the other's tags, a tag differing only by a slash (for example one with a slash in the module part) is not matched, an empty CLI tag list fails, and the preview tags `preview/mission-status/p<N>` (including suffixed `-r<N>` forms) are matched by neither the contract release filter nor the CLI's `v*.*.*`. Each rule has a planted violating workflow text (class B evidence). Edit `tests/ci/test_contracts_workflows.py` only; do not edit `ci-module-registry.yml`.
- Workflow-file additions do not need a ledger row or a `WORKFLOW_FILES` row (neither workflow invokes pytest); `contracts/**` matches a tracked path for the coherence gate. If a gate says otherwise, stop and report.
- **Does touch**: a shared CI gate (the new workflows) but no router, fleet or registry file in this WP; **does not touch** the migration chain, runtime-state schema or event contract.
- **Open-PR overlap check (2026-10-02)**: no open PR (#5540, #5326) touches `.github/workflows/`, `tests/ci/` or `contracts/`; #5557 is closed unmerged. Re-run at start and after the rebase.
- Baseline from WP01's hand-off; red-first (C-010): first commit of each deliverable is a failing guard test or planted fixture.
- Registry rows: this WP owns `tests/architectural/test_ci_corpus_trigger_completeness.py` for one purpose, a sorted row for `tests/contract/test_run_negative_cases.py`.

### Test surface, gates and baseline

- Targeted: `tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py tests/ci/test_fork_guard.py tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py tests/contract/test_run_negative_cases.py tests/contract/test_layout_check.py tests/contract/test_mission_status_examples.py tests/contract/test_contract_resolver.py`, and every `contracts/tools/*.py` check run by hand against the real contract with exit codes recorded.
- Named gates: `tests/architectural/test_module_shard_registry.py tests/architectural/test_workflow_coherence.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_ci_corpus_trigger_completeness.py tests/release/test_pinning_inventory_fresh.py`. No directory sweep.

## Subtasks

### Subtask T055: Conditional brace re-sweep (or the first red guard test)

**Purpose**: apply the spike's spelling decision exactly once.
**Steps**: as described above; if no re-sweep, write the first failing guard test for the `verify-pins` job instead.
**Validation**: `layout_check` green over `contracts/` after the sweep; the acceptance grep clean; or the new guard test red for the right reason.

### Subtask T056: Remaining jobs and gate in `contracts.yml`

**Purpose**: FR-017, FR-018, FR-021 job graph.
**Steps**: add the jobs per the job table; wire `needs`; keep SHA pins and comments; `timeout-minutes` on every job; concurrency per ref; prelude everywhere a script runs.
**Validation**: guard tests (T069) green; read-through against the table.

### Subtask T057: Negative-case manifest and driver

**Purpose**: FR-021 class A evidence.
**Steps**: failing tests first for the driver (zero cases exits 2; a case whose check passes unexpectedly fails; wrong code fails; missing control fails); then implement `run_negative_cases.py` and populate `negative_cases.json` with one case per script and per JVM/Go tool (layout, citation, provisional, example, event mapping, enum pin, leak scan via `fixture_builder`, structure, CODEOWNERS, no-pytest, verify-pins, bundle with a dangling reference and a module without a root file, a tampered-metadata copy, client smoke plant, lint rules via vacuum, breaking-change pair, resolver parity divergent-resolver plant, release script plants).
**Files**: driver (~150 lines), manifest (~150 lines), tests (~120 lines).
**Validation**: unit tests green locally; the CI `negative-tests` job is the runner of record.

### Subtask T058: Guard tests

**Purpose**: FR-017, FR-018, FR-022 guards (class B).
**Steps**: red-first tests as listed above, each with a planted violating workflow text and a clean control.
**Files**: `tests/ci/test_contracts_workflows.py` (~500 lines).
**Validation**: file green; `tests/ci/test_fork_guard.py` green over the new jobs.

### Subtask T059: `contracts-release.yml`

**Purpose**: FR-022 release workflow.
**Steps**: write it as specified; confirm it is not a `PR_WORKFLOWS` member and `scripts/ci/fleet_main.py` needs no edit; confirm workflow count 19 and the ceiling test.
**Validation**: guard tests green; ceiling test green.

### Subtask T060: Full local runs and a pushed-run hand-off

**Purpose**: prove the graph.
**Steps**: run every script locally against the real contract and record exit codes; run the targeted tests and gates; hand the orchestrator the list of what only CI can show (first full execution of every job, a green `contracts-gate`).
**Validation**: green locally; the hand-off lists the CI run identifiers once the orchestrator relays them.

### Subtask T061: Record the p1 inputs

**Purpose**: prepare the close-out.
**Steps**: record the candidate last commit and, once relayed, the contracts-workflow run id whose `contracts-gate` succeeded, and the class A failing-run links (one per check) for WP12.
**Validation**: hand-off complete.

## Close-out step: publish preview point `p1` (ORCHESTRATOR action, recorded in this WP)

Agents never push and never create remote tags. **P1, stable marker** is the **first commit whose contracts-workflow run is green on the draft PR**, meaning `contracts-gate` succeeded (so `verify-pins`, `python-checks` with the citation, provisional, example and leak checks over the real contract, `validate-bundle` including the counted client smoke, `lint`, `resolver-parity` with its independent dereference check, `release-dry-run` and `negative-tests` all passed). After this WP is **approved** and that run exists, **the orchestrator publishes the immutable preview tag `preview/mission-status/p1`** as a lightweight tag on that commit, recorded as the commit plus the run id. p1 is when generating a client for development is reasonable; the shape can still change by what WP10 forces. If p0 or p1 had been published before a brace re-sweep landed in this WP, the orchestrator re-publishes each already-published point under the next counter suffix (`-r2`, then `-r3`, independent per point; first re-publication of `p0` is `p0-r2`), each re-publication naming its cause (`brace re-sweep` or `compact history`) on #5528, the old tags staying until the UI team has moved. The tag name (not a hash) is recorded in this WP's hand-off for WP12.

**Orchestrator scheduling note for WP10**: the ratchet's tracker issue (owner, `drain_by`) must exist before WP10 starts; see WP10 "Precondition". Open it while this WP is in review.

## Definition of Done

- All nine jobs and the gate exist with the exact `needs` of the job table; every root and `always()` job has the canonical fork guard; no unpinned `uses:`; no Node; no pytest; `timeout-minutes` everywhere; client smoke is failing, not `continue-on-error`.
- Release workflow exists with the specified triggers, permissions, guard and publish conditions; workflow count 19.
- Guard tests and negative-case driver green, red first; namespace guard covers preview tags.
- Conditional re-sweep done (and acceptance grep clean) or recorded as not needed.
- Every script exits 0 against the real contract; named gates green; no `src/`, router, fleet or registry-file edit in this WP.
- Hand-off lists p1 inputs; the orchestrator step is pending or done with the tag name.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- First full execution is the draft PR; expect iteration; batch pushes.
- A skipped job read as a pass: `contracts-gate` `needs` and `always()` form is mandatory and tested.
- Re-sweep leaving a stale brace literal in an older WP's tests: the acceptance grep is the check.

## Reviewer Guidance

Diff the workflow against the job table line by line (needs, guards, pins). Run the guard tests and confirm the planted bad workflow texts fail for the intended rule. Confirm publication is unreachable from `pull_request` and `workflow_dispatch`, `--latest=false` is present, and no Node or pytest reaches either workflow. If the re-sweep happened, confirm its first commit is red against the unchanged constant.

Implementation command: `spec-kitty agent action implement WP09 --agent claude`
