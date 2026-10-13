---
work_package_id: WP14
title: 'Phase 5c: nightly full-corpus comparison job and script'
dependencies:
- WP13
requirement_refs:
- FR-008
- FR-015
- C-006
- SC-002
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T073
- T074
- T075
- T076
history: []
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- .github/workflows/mission-status-api.yml
- tests/ci/test_mission_status_api_build.py
- scripts/ci/mission_status_corpus_compare.py
- tests/ci/test_mission_status_corpus_compare.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/mission-status-api.yml
- tests/ci/test_mission_status_api_build.py
- scripts/ci/mission_status_corpus_compare.py
- tests/ci/test_mission_status_corpus_compare.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP14 - Phase 5c: nightly full-corpus comparison job and script

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add the `schedule`/`workflow_dispatch` job `nightly-corpus` to the workflow and the script `scripts/ci/mission_status_corpus_compare.py` that compares, for every Mission of this repository, the live Python overview with what the running service answers, and exits non-zero on ANY difference with no exemption mechanism (D-Q1, AC-8c, E-10).

## Context

- Plan section 7 ("Nightly comparison contract" and "Nightly job environment (`nightly-corpus`, the complete recipe)" - read both in full), section 1 (`mission_status_corpus_compare.py` paragraph), section 11 (AC-8 (c) row), section 5 (workflow). Spec FR-008 (iv), AC-8c, FR-015 (job conditions, jobs bullet), C-006, SC-002, operator decisions E-10 (no exemptions) and D-Q1.
- Depends on WP13 (serialised workflow edits; WP12 and WP13 appended before) and transitively WP10 and WP20 (the service) and WP07 (the oracle helpers). Concurrent with WP11.
- No exemption mechanism, no committed list of known differences, no ledger. The machine-readable `nightly-report.json` is a workflow artifact, never committed, never read as input; it records outcomes and cannot turn a difference green; the exit code is non-zero while any row is not `equal`.
- The oracle import trap: the script lives in `scripts/ci/`, so run by path the repository root is NOT on `sys.path` - bootstrap it for both `scripts.*` and `tests.*` imports in the form `tests/ci/test_workflow_script_import_guard.py` accepts. The oracle (`tests/contract/_mission_status_payloads.py`) imports `pytest`, `yaml`, `jsonschema` and ten `src` packages, so the job needs the fully synced test environment even though no job step runs `pytest` (the workflow stays out of `test_no_duplicate_suite_execution`'s suite classification). `Projector` needs a `ContractTools` value built by `load_contract_tools(mp, repo_root)` from a `pytest.MonkeyPatch`: create it inside `pytest.MonkeyPatch.context()`, hold it for the whole comparison, do not fork a second copy of the oracle.
- The service is started from the JVM jar (`./gradlew --no-daemon bootJar`; byte equality of native binaries is the legs' job), against the checkout itself: `java -jar build/libs/mission-status-api.jar --mission-status.project-root="$GITHUB_WORKSPACE" --mission-status.port=8787`. The script's HTTP client sends the accepted `Host: 127.0.0.1:8787`.
- Public repo: the script's output names slugs, `mission_id`, difference class and field; never a path.
- `create_intent` note: `finalize-tasks` checks every literal path in `owned_files` once, at planning time, when no later file exists yet, so this frontmatter also lists shared files that an EARLIER WP creates. The workflow and the build test are created by WP04 and WP03, amended here (and the README is created by WP19 for WP16). This WP creates: `scripts/ci/mission_status_corpus_compare.py` and its test.

## Subtask T073: Script core and unit cases (red-first)

**Purpose**: The comparison logic as importable, unit-testable functions.

**Steps**:
1. Write `tests/ci/test_mission_status_corpus_compare.py` first. Cases (all against fakes of the service and oracle): (a) the AC-8c two-Mission planted difference: exits non-zero and prints the slug and the differing field; (b) empty corpus; (c) a compared count below the recorded floor (500; 588 on the planning checkout); (d) a count differing from the script's own independent `git ls-files 'kitty-specs/*/meta.json'` count; (e) unreachable service; (f) a one-sided Mission (present in only one side's listing); (g) the refusal library function: same class, different class, against a fake (the workflow never exercises it); (h) a service 500 and an oracle refusal each exit non-zero NAMING THEIR SIDE (`service` with route and Problem `code`; `python` with Mission slug, `mission_id` and exception class); (i) both sides refusing still fails ("both failed, so equal" is not accepted); (j) a difference of the Q-3 shape (a coordination husk case) still exits non-zero; (k) a planted all-`equal` report beside one differing Mission still exits non-zero (the report cannot flip the exit code); (l) a subprocess import of the script by path from another working directory, and the MonkeyPatch path.
2. Implement: non-vacuity (print and assert the number of Missions compared; fail below the floor, differing from the independent count, or zero); failed start (poll `GET /api/v1/project` every 2 s for at most 60 s, exit non-zero if the service never answers; fail when the service refuses every Mission); one-sided Missions; any difference: field difference, one-sided Mission, service 500, oracle refusal. The failure line names the Mission slug, `mission_id`, the difference class (`field`, `one_sided`, `refusal` with side) and the field; for a whole-read 500, which is not attributable to a Mission over HTTP, the side, the route and the Problem `code`.
3. Comparison scope: the entire response document in canonical form (sorted keys, compact separators, UTF-8 not escaped) with an empty ignore-list constant asserted empty; no normalisation of timestamps, ordering or numbers. Compare the paged `/api/v1/missions` listing (follow `nextPageCursor`) and `/api/v1/project`.
4. Exit codes: 0 pass, 1 difference/refusal, 2 cannot do its job. `nightly-report.json` rows are written for every Mission compared (`equal` or the class).
5. Types, complexity < 15, no literal repeated 3+ times, ruff clean.

**Files**: `scripts/ci/mission_status_corpus_compare.py` (~350 lines), tests (~450).
**Validation**: `.venv/bin/python -m pytest tests/ci/test_mission_status_corpus_compare.py tests/ci/test_workflow_script_import_guard.py -q`; `.venv/bin/ruff check` and `.venv/bin/ruff format --check --force-exclude` on both files.

## Subtask T074: The `nightly-corpus` job

**Purpose**: The complete recipe of plan section 7.

**Steps**:
1. Job `nightly-corpus`: `runs-on: ubuntu-24.04`, `timeout-minutes: 45`, `if:` per FR-015 (c): the canonical fork guard first, then the event conjunct that selects `schedule` and `workflow_dispatch` only (`(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch') && (github.event_name == 'schedule' || github.event_name == 'workflow_dispatch')`; confirm the exact form against `tests/ci/test_fork_guard.py` and AC-15a(iii) before committing). It is NOT a `needs` of the gate and the legs/gate are skipped on `schedule` by their `!= 'schedule'` conjunct.
2. Steps, each action pinned by the SHA WP04 recorded: (1) `actions/checkout` with `fetch-depth: 0` and `persist-credentials: false` (a real `.git` is required: the oracle reads the worktree registry and the corpus is `git ls-files`); (2) `astral-sh/setup-uv` with `python-version: '3.12'`, then `uv sync --frozen --all-extras`; (3) `gradle/actions/wrapper-validation` then `graalvm/setup-graalvm` (same reference as the legs); (4) `./gradlew --no-daemon bootJar` in `services/mission-status-api` (+ the contract bundling step per the WP02 mechanism); (5) start the jar in the background with `> "$RUNNER_TEMP/service.log" 2>&1 &` and record the PID; (6) `uv run --frozen --no-sync python scripts/ci/mission_status_corpus_compare.py --base-url http://127.0.0.1:8787 --repo-root "$GITHUB_WORKSPACE" --report "$RUNNER_TEMP/nightly-report.json"`; (7) an `if: always()` step uploads `nightly-report.json` and `service.log` and stops the process by the recorded PID (a PID kill, never a pattern kill).
3. No step runs `pytest`; the job installs pytest only because the imported oracle module needs it.
4. The cron: one nightly slot offset from `ci-nightly.yml`'s; state it in the PR.

**Files**: workflow (edit, ~80 lines).
**Validation**: YAML parses; pins of T075.

## Subtask T075: Pins, the AC-15d re-run and `workflow_dispatch` evidence

**Purpose**: Structure pinned; the pre-merge exercise stated.

**Steps**:
1. Pins appended to `tests/ci/test_mission_status_api_build.py` (`# --- WP14 ---`): the `nightly-corpus` job exists with `if:` form, `timeout-minutes: 45`, `fetch-depth: 0`, `uv sync --frozen --all-extras`, the `bootJar` step, the exact script invocation arguments, the `if: always()` upload/stop step, no `pytest` step; the gate does not `need` it. Revert rows (observed red once): drop `fetch-depth: 0`; add a `pytest` step; change the cron to a PR trigger.
2. Run `.venv/bin/python -m pytest tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_workflow_coherence.py tests/ci/test_fork_guard.py tests/ci/test_workflow_script_import_guard.py tests/ci/test_mission_status_api_build.py -q` (AC-15d re-run on the edited workflow; targeted files only).
3. `workflow_dispatch` on the PR branch is the pre-merge exercise of exactly this recipe (AC-8c): the orchestrator triggers it; record that the first result is expected to expose real-corpus Python/Java differences (the nightly stays red until the port is fixed or the operator rules; there is no exemption), and list the report artifact to read.

**Files**: pins (~100 lines appended).
**Validation**: pytest above green.

## Subtask T076: First real-corpus run: triage hand-off

**Purpose**: Make the expected first red actionable without weakening the gate.

**Steps**:
1. Locally (the service built from the jar, Linux), run the script against this checkout if a JDK 25 is available; otherwise leave it to the dispatch run. For every difference found: record Mission slug, class and field, whether the Python verdict needs git (Q-3 classification: `same`/`differs`/`unknown`) in a report for the orchestrator (research.md R-9 is orchestrator-owned documentation; this WP does not edit it).
2. NEVER add an exemption, an ignore-list entry, a skip or a known-differences file. A difference is fixed in the port (WP05/WP17/WP06/WP08/WP19 files, not owned here: justified out-of-map edit in its own commit with a golden added through WP07's generator process) or escalated to the operator.
3. Append tracer entries (friction: anything in the recipe that did not run as written; decisions: cron slot).

**Validation**: the report lists every difference with its class, or states the run was not possible locally and why.

## Definition of Done

- The script and its unit tests cover every case of T073 and exit non-zero on any difference; the `nightly-corpus` job follows the recipe; pins green with revert rows observed.
- There is no exemption mechanism anywhere; the report cannot flip the exit code.
- AC-15d targeted re-run green; the `workflow_dispatch` pre-merge exercise is handed to the orchestrator.

## Risks

- The first real-corpus run may be red on a genuine parity gap (PR-1): that is the product working; escalate, do not exempt.
- Oracle imports pull the full test environment (slow `uv sync`): accepted, in the 45-minute budget.
- The job must not make the Mission depend on `tests-corpus-blocking` (#5838): it is standalone.

## Reviewer Guidance

- Verify nothing in the script can turn a difference green (no allowlist, no `--ignore`, no report-as-input).
- Verify non-vacuity floors and the independent count.
- Verify `persist-credentials: false`, SHA pins and the PID-based stop.

## Implementation command

`spec-kitty agent action implement WP14 --agent claude`
