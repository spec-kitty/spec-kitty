---
work_package_id: WP01
title: 'Phase 0: campsite-clean the contract-tools filter-group test'
dependencies: []
requirement_refs:
- FR-008
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-overview-01M4EMSA
base_commit: 4bb9af1d2a0c6c826c52f7952d406ca8df704d6f
created_at: '2026-10-10T12:37:06.703558+00:00'
subtasks:
- T001
- T002
- T003
history: []
agent_profile: python-pedro
authoritative_surface: tests/ci/test_contracts_workflows.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/ci/test_contracts_workflows.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 - Phase 0: campsite-clean the contract-tools filter-group test

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Land the single, distinct, behaviour-preserving FIRST commit of the Mission (plan.md section 9, Standing Order 2 "campsite cleaning"): introduce a named, documented, currently empty constant `ROUTER_ONLY_EXTRA_GLOBS` in `tests/ci/test_contracts_workflows.py` and make the filter-group assertion add it to its expectation, so that WP07 can later add the conformance-goldens glob as the constant's first entry without touching the shape of the test.

## Context

- Plan phase 0; write scope is exactly `tests/ci/test_contracts_workflows.py`. This WP has no plan concern (cross-cutting tidy-first enabler); it is traceable to FR-008 because the constant exists to carry the router glob of AC-8e.
- The test to edit is `test_the_contract_tools_filter_group_names_the_paths_the_contracts_workflow_triggers_on_beyond_contracts` (around line 1222). Today it asserts `sorted(group) == sorted(spelled)` where `spelled` is the `contracts.yml` trigger list (`EXPECTED_PATHS`, minus `contracts/**` and `.github/CODEOWNERS`) plus the `**/...` src-import spellings. Any path added to the `contract_tools` group that is not in `contracts.yml` fails it. WP07 must add `services/mission-status-api/src/test/resources/conformance/**` to that group (Reflexivity item 1/2), so the test needs a documented place for "router-only extras" first.
- Exactly one item. Not a grab-bag: the declined candidates (a split of the 1,500-line test file, `test_ci_corpus_trigger_completeness.py`, `ci-router.yml`) are recorded in plan.md section 9 and stay declined.
- The orchestrator records the baseline (plan.md section 6, `research/baseline-red.md`) BEFORE this WP is claimed. Read it first; if it is absent, stop and report (do not create it: it belongs to the orchestrator and `kitty-specs/` paths are not code-WP surface).
- Public repository: no absolute home-directory paths in any committed file, commit message or output you paste (charter C-010).

## Subtask T001: Sonar survey and green baseline of the target test

**Purpose**: Evidence of looking before tidying (Standing Order 2), and a green before-state, so the refactor is provably behaviour-preserving.

**Steps**:
1. From the repository root, confirm the checkout: `git rev-parse --show-toplevel` must print the repository root.
2. Run the token-free, read-only Sonar helper on the one file this WP edits: `scripts/ci/sonarcloud_branch_review.sh issues --file tests/ci/test_contracts_workflows.py`. Record the `total` it reports (plan.md section 9 recorded `total: 0` on 2026-10-10). If the service is unreachable, record that instead; do not retry-loop.
3. Run the file once BEFORE editing and note the pass count: `.venv/bin/python -m pytest tests/ci/test_contracts_workflows.py -q`. Use `.venv/bin/python`, never bare `uv run` (it re-syncs and destroys a hand-built venv).
4. Open the baseline record the orchestrator wrote and confirm this file is not in its failing list; if it is, stop and report.

**Files**: none edited.
**Validation**: the before-run is green; the survey result is captured for the commit message (T003).

## Subtask T002: Introduce `ROUTER_ONLY_EXTRA_GLOBS` and fold it into the assertion

**Purpose**: Give the "router group may carry globs the Contracts workflow does not trigger on" rule a name, a type and a mandatory rationale per entry, with no behaviour change (the tuple is empty).

**Steps** (red-first discipline for a refactor: prove the guard bites, then remove the scaffold):
1. Next to `EXPECTED_PATHS` (module level, line ~42) add:
   - `ROUTER_ONLY_EXTRA_GLOBS: tuple[tuple[str, str], ...] = ()` documented as: pairs of (glob, one-line rationale) that the `contract_tools` router group names although `contracts.yml` does not trigger on them; each entry must carry a non-empty rationale; the tuple is empty at this commit and WP07 adds the first entry. Use a tuple of pairs (not bare strings) so the "rationale per entry" rule is structural rather than a comment.
2. In `test_the_contract_tools_filter_group_names_the_paths_the_contracts_workflow_triggers_on_beyond_contracts`, add `spelled += [glob for glob, _why in ROUTER_ONLY_EXTRA_GLOBS]` beside the existing src-import spellings, and assert the constant's shape before use: it is a tuple, every element is a 2-tuple of two non-empty strings, and the globs are unique. Keep the message strings of the existing asserts unchanged.
3. Keep the function under the complexity ceiling (15) and do not rename it: other tools and the plan cite it by name.
4. Revert-fails check (run in a scratch copy of the file, never by leaving the working tree broken): (a) temporarily set `ROUTER_ONLY_EXTRA_GLOBS = (("services/x/**", ""),)` and require the shape assertion to fail on the empty rationale; (b) set it to `(("services/x/**", "why"),)` and require the group-equality assertion to fail because the router group does not name that glob. Both must be red; then restore the empty tuple. Record in the commit message that both mutations were run.
5. Do NOT add any glob to the router, to `ci-router.yml`, or to the constant here. That is WP07 (`ci-router.yml` stays untouched in phase 0).

**Files**: `tests/ci/test_contracts_workflows.py` (edit, about +20 lines).
**Validation**: `.venv/bin/python -m pytest tests/ci/test_contracts_workflows.py -q` is green with the same pass count as T001; `.venv/bin/ruff check tests/ci/test_contracts_workflows.py && .venv/bin/ruff format --check --force-exclude tests/ci/test_contracts_workflows.py`.

## Subtask T003: Targeted run, hygiene checks and the single campsite commit

**Purpose**: Leave one reviewable, distinct preceding commit.

**Steps**:
1. Run, from the repository root, exactly the targeted files that the edited surface implicates (never the bare `tests/architectural/` and never `make test-full`):
   `.venv/bin/python -m pytest tests/ci/test_contracts_workflows.py tests/ci/test_contracts_routing.py -q`
   and `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.
2. Commit with the lane tooling's normal path (`.venv/bin/spec-kitty safe-commit`, or the implement workflow's own commit). The message names the Mission, states "campsite: behaviour-preserving, constant empty", and carries the Sonar survey line from T001 plus the two revert-fails mutations from T002. No version numbers in scope.
3. Confirm the diff touches only `tests/ci/test_contracts_workflows.py`.
4. Append one dated entry to `kitty-specs/mission-status-read-api-overview-01M4EMSA/traces/approach.md` if anything was learned (out-of-map append, append-only; commit it as its own commit, never mixed with the code commit).

**Files**: the one test file.
**Validation**: `git diff --stat main...HEAD` for this WP shows one file; the targeted run is green.

## Definition of Done

- `ROUTER_ONLY_EXTRA_GLOBS` exists, is an empty tuple of (glob, rationale) pairs, is documented, shape-asserted and folded into the filter-group assertion.
- Both revert-fails mutations were observed red; the final file is green with the same pass count as before.
- One distinct commit; only `tests/ci/test_contracts_workflows.py` changed; ruff check and format are clean for the file.
- Evidence recorded per subtask with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- A later reviewer reading the empty constant as dead code: the docstring names WP07 and plan.md section 9 as the reason.
- The test is shared with later WPs (WP07 edits it again): keep the diff minimal so that edit is a one-line addition.

## Reviewer Guidance

- Confirm behaviour preservation: the assertion's expected set is byte-identical with an empty constant.
- Confirm no new Sonar finding (S1192 repeated literals, complexity) and no suppressions.
- Confirm nothing outside the one file changed and no router/workflow edit slipped in.

## Implementation command

`spec-kitty agent action implement WP01 --agent claude`
