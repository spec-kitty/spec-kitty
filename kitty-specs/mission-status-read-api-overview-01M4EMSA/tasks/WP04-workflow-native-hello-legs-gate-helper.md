---
work_package_id: WP04
title: 'Phase 1c: path-filtered workflow, four native hello-route legs, gate helper'
dependencies:
- WP03
requirement_refs:
- FR-015
- FR-014
- C-008
- C-009
- SC-007
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
- T022
history: []
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- .github/workflows/mission-status-api.yml
- scripts/ci/mission_status_gate_checks.py
- tests/ci/test_mission_status_gate_checks.py
- tests/ci/test_mission_status_api_build.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/mission-status-api.yml
- .github/CODEOWNERS
- scripts/ci/mission_status_gate_checks.py
- tests/ci/test_mission_status_gate_checks.py
- tests/ci/test_mission_status_api_build.py
- scripts/ci/fleet_verdict.py
- .github/workflows/ci-fleet-verdict.yml
- tests/ci/test_fleet_verdict.py
- tests/ci/test_fleet_main.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP04 - Phase 1c: path-filtered workflow, four native hello-route legs, gate helper

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Create the Mission's ONE new workflow file `.github/workflows/mission-status-api.yml` (the last of the 20 allowed workflow slots) with the path-filtered JVM job, the four-target native matrix proving a hello route, and the terminal gate job; add the gate helper script with BOTH subcommands and its tests; add the CODEOWNERS line; and pin all of it in `tests/ci/test_mission_status_api_build.py`.

## Context

- Plan phase 1, CI half (plan.md sections 5 "The new workflow itself", 11 phase 1 row, 12 matrix, 13). Spec FR-015 (AC-15a, AC-15c, AC-15d, AC-15f), FR-014 (AC-14f), SC-007, E-5 (one slot), E-9 (not a required check), E-3 (not in `ci-fleet-verdict.yml`).
- **Scope decision recorded in the Tasks Overview**: the plan has `scripts/ci/mission_status_gate_checks.py` created in phase 1 with `native-tag-floor` and extended in phase 5 with `digests`. A script shared by two non-adjacent phases is a write-scope chokepoint, so this WP implements BOTH subcommands and their planted-file tests now; WP12 only wires `digests` into the gate job and produces the digest files it checks. The digest file format is fixed by plan.md section 12: `digest-<os>-<arch>.json` = `{os, arch, requestCount, bodyCount, sha256}` where `sha256` covers the concatenated response bodies only, never the os or arch.
- `tests/ci/test_mission_status_api_build.py` was created by WP03; append your pins in a clearly named section (`# --- WP04: workflow pins ---`) so later appends by WP10, WP20, WP12 to WP15 rebase cleanly. Do not rewrite WP03's section.
- The workflow is NOT a router dependency, and its name must NOT match `contracts*.yml` (the pin tools glob that pattern, AC-15f). **It IS registered in the fleet verdict** (operator ruling 2026-10-11, supersedes E-3): add `mission-status-api.yml` to `PR_WORKFLOWS` in `scripts/ci/fleet_verdict.py`, add its `name:` to `ci-fleet-verdict.yml`'s `workflow_run.workflows`, and update `tests/ci/test_fleet_verdict.py` / `tests/ci/test_fleet_main.py` expectations. Edit no other workflow file.
- The tag trigger and the release job are WP15; the nightly job is WP14. This WP must leave room for them (single `on.push` block, workflow-level `concurrency` written in the final tag-aware form of plan.md section 12 now, so WP15 does not rewrite it).
- Consume the WP02 record for: action SHAs (`gradle/actions` wrapper-validation, `graalvm/setup-graalvm`, `actions/checkout`, `actions/upload-artifact`, `actions/download-artifact`, `astral-sh/setup-uv`), bundling mechanism A/B, native test wiring, leg timeout budgets. Re-verify each SHA with `gh api` immediately before pinning (unset `GITHUB_TOKEN` if `gh` complains of scopes). Pin by 40-char SHA with a trailing version comment, exactly as `contracts.yml` does.
- Public repository: no absolute home-directory paths.
- No local Gradle or JDK is needed here: the workflow is YAML, the helper and the pins are Python, and every Gradle command in this WP runs on the CI legs. (The Java WPs carry the toolchain precondition; this one does not.)
- The hello route stays in the service until WP12 (it is what `nativeSmoke` asserts in the legs below); WP10 must not break these legs, and neither may any WP before WP12.

## Subtask T018: The workflow skeleton and the JVM job

**Cache note (NEWA-001)**: the JVM job runs `./gradlew check`, whose standing `VerificationTamperTest` (WP03) runs a nested `--offline` build against the real Gradle user home; the job must therefore not clear the Gradle cache between the dependency-resolving steps and `check` (the outer build resolves first; do not add a cache-less or `--offline`-hostile step before it).

**Purpose**: The path-filtered build (AC-15a) with its fork guard, permissions and concurrency.

**Steps**:
1. `on`: `push` (`branches: [main]`, `paths`: `services/mission-status-api/**`, `contracts/mission-status/**`, `.github/workflows/mission-status-api.yml`) and `pull_request` (the same three paths); `schedule` (a cron line, no filter) and `workflow_dispatch` (no filter). The `push` block must be a per-change push for `tests/architectural/_workflow_jobs.push_is_per_change` (branch and path filters present). AC-15a pins exactly the three-path list.
2. `permissions: contents: read` at workflow level; `persist-credentials: false` on every checkout.
3. Workflow-level concurrency in the tag-aware form of plan.md section 12: group `mission-status-api-${{ startsWith(github.ref, 'refs/tags/') && github.ref || (github.event_name == 'push' && github.sha || github.ref) }}`, `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`.
4. Job `jvm` (`runs-on: ubuntu-24.04`): `if:` the canonical fork guard first, then `github.event_name != 'schedule'` (so a scheduled run skips it and the gate together): `(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch') && github.event_name != 'schedule'`. Steps: checkout, `gradle/actions/wrapper-validation` BEFORE any Gradle call, `graalvm/setup-graalvm` (JDK 25, Community; sets `JAVA_HOME`, the only JDK source on every leg), contract bundling per mechanism A or B, `./gradlew --no-daemon check` in `services/mission-status-api` (never `test` alone: it skips the JaCoCo rule), upload the JaCoCo HTML and XML report as an artifact on every run (`if: always()`), upload the JUnit XML.
5. No step runs `pytest` (keeps the workflow out of `test_no_duplicate_suite_execution`'s suite classification).
6. Timeouts: state each job's `timeout-minutes` with the doubled native compile in mind.

**Files**: `.github/workflows/mission-status-api.yml` (new, about 150 lines at this stage).
**Validation**: `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/mission-status-api.yml'))"`; the pins of T021.

## Subtask T019: Native matrix (hello route) and the terminal gate

**Purpose**: Prove `nativeCompile` and the hello route on four targets; the gate is the aggregate job (AC-15c).

**Steps**:
1. Job `native` with `strategy.matrix` over exactly four legs: `ubuntu-24.04` (linux-x64), `ubuntu-24.04-arm` (linux-arm64), `macos-15` (macos-arm64), `windows-2025` (windows-x64); `fail-fast: false`. Same `if:` as `jvm`. Steps per leg: checkout, wrapper-validation, `graalvm/setup-graalvm` with the SAME action reference on every leg, bundling, `./gradlew --no-daemon nativeCompile nativeTest` (the tagged native subset only), then `./gradlew --no-daemon nativeSmoke -PnativeBinary=<built binary>` (at this stage the skeleton NativeSmokeTest: binary answers the hello route), then run `python scripts/ci/mission_status_gate_checks.py native-tag-floor ...` over the `nativeTest` JUnit XML directory with `--floor 3`, upload the binary plus `.sha256` as `mission-status-api-<os>-<arch>[.exe]` (30 days), upload the JUnit XML. Windows: call the script with `python`, not `python3`; use `shell: bash` where paths are POSIX.
2. A verify-only step for the three non-Linux-x64 legs: strict dependency verification with no write; on an OS-classified artifact missing from the metadata, the step fails and prints the exact `--write-verification-metadata` command to run on that OS (CI never commits).
3. Job `mission-status-api-gate`: `needs: [jvm, native]`; `if: (github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch') && github.event_name != 'schedule' && always()` (guard first, schedule conjunct second, `always()` last; pinned verbatim by AC-15a(iii)); fails unless every needed job result is `success` (the `contracts-gate` loop shape, so a skipped leg cannot read as green). The `digests` step is added to this job by WP12 (leave a comment-free structure that WP12 can extend).
4. Python on the runner for the helper script: the script is standard-library only; use the runner's `python3`/`python`, or `astral-sh/setup-uv` where the repository's other jobs do (record which).
5. Remember the path filter applies to branch pushes and pull requests only; `schedule` and `workflow_dispatch` carry none.

**Files**: workflow (extended, about 250 lines total).
**Validation**: pins of T021; the first real run (T022).

## Subtask T020: `scripts/ci/mission_status_gate_checks.py` and its tests (red-first)

**Purpose**: The executable home of the two non-Gradle guards (plan.md section 1), tested on planted files.

**Steps**:
1. Write `tests/ci/test_mission_status_gate_checks.py` first (red), then the script. Standard library only; it runs by path, so bootstrap the repository root onto `sys.path` only if it imports `scripts.*` (it should import nothing from the repo), in the form `tests/ci/test_workflow_script_import_guard.py` accepts.
2. Subcommand `native-tag-floor --junit-dir DIR --floor N`: counts executed `<testcase>` entries (not skipped) in the XML under DIR and exits non-zero below N, printing the count and the floor. Cases: XML with fewer tests than the floor (red), an empty directory (red), a directory with zero XML files (red), exactly the floor (green), skipped tests not counted.
3. Subcommand `digests --dir DIR --expected-count 4 --request-floor N`: requires exactly four `digest-*.json` files named for exactly linux-x64, linux-arm64, macos-arm64 and windows-x64; each with a `requestCount` equal to the others and at least the floor, a `bodyCount` greater than zero, and all four `sha256` values equal; prints the four digests on failure. Cases (all planted files): all equal (green); one `sha256` altered (red, prints four digests); one file missing (red on "exactly four"); a wrong os/arch name set, five files, a low `requestCount`, unequal `requestCount`, zero `bodyCount`, malformed JSON (each red).
4. Exit codes: 0 pass, 1 check failed, 2 cannot do its job (missing directory). `main(argv)` is importable; a subprocess test runs the script by path from another working directory.
5. Type annotations throughout; complexity under 15; no repeated literal 3+ times.

**Files**: `scripts/ci/mission_status_gate_checks.py` (new, ~150 lines), `tests/ci/test_mission_status_gate_checks.py` (new, ~220 lines).
**Validation**: `.venv/bin/python -m pytest tests/ci/test_mission_status_gate_checks.py tests/ci/test_workflow_script_import_guard.py -q`; ruff check and format with `--force-exclude`.

## Subtask T021: CODEOWNERS and the workflow pins in `test_mission_status_api_build.py`

**Purpose**: AC-15a/15c/15f/14f pinned, with revert-fails.

**Steps**:
1. `.github/CODEOWNERS`: one line for `services/mission-status-api/` using the owner handle form the file already uses for `contracts/`. Check how `contracts/` is listed and mirror it; `contracts/tools/codeowners_check.py` and the contract workflow's path list name `.github/CODEOWNERS`, so also run the contracts routing tests (T022).
2. Pins appended to `tests/ci/test_mission_status_api_build.py`: (a) `on.push.paths` and `on.pull_request.paths` equal exactly the three-path list; schedule and dispatch carry no filter; (b) every root job and every `always()` job has the canonical fork guard first; the exact `if:` text of `jvm`, `native` and the gate; (c) all `uses:` are 40-hex SHA pinned; the `gradle/actions/wrapper-validation` step precedes every `gradlew` step in each job (AC-14f); every job sets up the same GraalVM action reference; (d) the native matrix has exactly the four targets and `fail-fast: false`; (e) no step contains `pytest`; (f) the file name does not match `contracts*.yml`; `ci-fleet-verdict.yml` lists the workflow's name and `fleet_verdict.PR_WORKFLOWS` contains `mission-status-api.yml` (E-3 superseded 2026-10-11); (g) CODEOWNERS contains the line; (h) the workflow-file count is exactly 20 (`reusable_workflow_ceiling` not raised); (i) the JVM job invokes `check` (the workflow half of the JaCoCo pin of WP03).
3. Revert rows, each observed red once in a scratch copy: remove a path from the filter; drop the fork guard of a job; drop the `!= 'schedule'` conjunct of the gate; add a `pytest` step; unpin one action to a tag; reorder wrapper-validation after a Gradle step.

**Files**: `.github/CODEOWNERS` (+1 line), `tests/ci/test_mission_status_api_build.py` (append ~200 lines).
**Validation**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py tests/ci/test_fork_guard.py -q`.

## Subtask T022: AC-15d wide workflow-test sweep, first CI run and recording

**Purpose**: The plan's Unverified 8 and 7/13: prove the new workflow passes every test that enumerates workflows, and the runner labels exist.

**Steps** (the sweep runs on the first workflow commit; targeted files only, never the bare `tests/architectural/`):
1. Run: `.venv/bin/python -m pytest tests/architectural/test_module_shard_registry.py tests/architectural/test_workflow_coherence.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_dual_mode_contract.py tests/architectural/test_gate_os_tier.py tests/architectural/test_ci_integrity_oracle_nonvacuous.py tests/architectural/test_gate_coverage_composite_path.py tests/architectural/test_gate_coverage_runner_prefix.py tests/architectural/test_ci_corpus_trigger_completeness.py tests/ci/test_fork_guard.py tests/ci/test_workflow_script_import_guard.py tests/ci/test_ci_module_wiring.py tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py tests/release/test_release_ci_ownership.py -q`. A failure you did not cause and cannot explain is classified against the baseline record (CLAUDE.md "baseline-red gotcha"); a failure caused by the new workflow (a `windows`/`macos` runner with no `mode` input, for example) is fixed in the workflow or escalated if a test would have to change (the spec allows only the two named pinning-test edits).
2. If `grep -rln "\.github/workflows" tests/ci tests/architectural tests/release tests/contract` finds a workflow-enumerating test not in the list above, add it to the sweep and record it in `traces/tooling-friction.md` (plan.md "Plan task" of Reflexivity item 2).
3. The four native legs cannot run locally. The orchestrator pushes the branch and babysits CI; record in the spike record (cross-WP append to `research.md`, own commit) the answers a real run gives: runner labels exist, `graalvm/setup-graalvm` works on each, wall-clock of the doubled native compile per leg (set the final `timeout-minutes`), whether `bundle.py --bundle-only` runs on all four legs (WP02 mechanism A) or the pre-job fallback is adopted, OS-classifier verify-only outcomes. Until that run exists, state in the PR notes "four-leg hello evidence pending CI" and do not claim the exit gate.
   The same hand-off carries the two one-time recordings that no earlier WP can observe (spec AC-14b and AC-14c; neither WP03, which has no CI, nor the pins prove them):
   - AC-14b, the negative run: the orchestrator pushes a scratch branch (never merged) whose `gradle/wrapper/gradle-wrapper.jar` differs by one byte; the `wrapper-validation` step of the `jvm` job and of every native leg must fail and the job must be red at that step. Record the run, the failing step and its exit status in the spike record and the PR notes.
   - AC-14c, strict resolution on all four legs: record, per leg, the exit status of the strict dependency-verification step (Linux x64 resolves against the file written by WP03; the three verify-only legs verify it). All four must be 0; a non-zero leg is recorded with the printed `--write-verification-metadata` command (R-4) and returns to WP03 as a reviewed amendment.
   Do not claim AC-14b or AC-14c as met until both recordings exist.
4. Select-check: the services-only diff selects this workflow and no `src`-backed shard: call `scripts.ci.gate_selection.select_gates` with synthetic path lists as the plan did (SC-007, first half; WP07 owns the golden-only half and its routing test).

**Validation**: the sweep is green or every red is classified; the PR note states what is proven locally and what is owed to CI.

## Definition of Done

- `mission-status-api.yml` exists with jobs `jvm`, `native` (4 legs), `mission-status-api-gate`; it is the only new workflow file (count 20); AC-15a/15c/15f/14f pinned and each pin observed red once.
- `scripts/ci/mission_status_gate_checks.py` has `native-tag-floor` and `digests` with the planted-file tests green; both are invoked/ready (`native-tag-floor` wired in each leg; `digests` wired by WP12).
- CODEOWNERS line present; no other workflow file edited; the workflow-enumerating sweep recorded.
- Four-leg evidence (hello route, AC-14b negative run, AC-14c exit statuses) is either attached from a CI run or explicitly owed in the hand-off; none of it is claimed otherwise.

## Risks

- Runner labels `ubuntu-24.04-arm`, `macos-15`, `windows-2025` unverified offline (PR-13): first CI run answers.
- `test_dual_mode_contract.py`/`test_gate_os_tier.py` rejecting `windows`/`macos` runners without a `mode` input (Unverified 8): fix in the workflow if possible; escalate otherwise.
- A path-filtered check is not a router dependency: do not add it to `ci-router.yml` `needs`.

## Reviewer Guidance

- Confirm the gate `if:` text and the fork guards byte-for-byte against plan.md section 5.
- Confirm every action SHA was freshly verified and wrapper-validation precedes Gradle on every leg.
- Confirm the helper script's failure paths all have planted-file tests, including "zero tests selected".
- Confirm no edit outside the five owned paths (one-line CODEOWNERS excepted by ownership).

## Implementation command

`spec-kitty agent action implement WP04 --agent claude`
