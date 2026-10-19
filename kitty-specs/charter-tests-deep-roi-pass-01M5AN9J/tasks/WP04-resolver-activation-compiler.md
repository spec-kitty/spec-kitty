---
work_package_id: WP04
title: Resolver, cascade, compiler and mission-type suites ROI pass
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
planning_base_branch: feat/6485-charter-tests-deep-roi-pass
merge_target_branch: feat/6485-charter-tests-deep-roi-pass
branch_strategy: Planning artifacts for this mission were generated on feat/6485-charter-tests-deep-roi-pass. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/6485-charter-tests-deep-roi-pass unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-tests-deep-roi-pass-01M5AN9J
base_commit: bf2809833b308c4e8ff296eec80e2e3180bd1e55
created_at: '2026-10-19T18:19:30.301400+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
phase: Phase 1 - ROI pass
history:
- timestamp: '2026-10-19T18:30:00Z'
  agent: claude
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/charter/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- tests/charter/test_resolver.py
- tests/charter/test_resolver_activation_parity.py
- tests/charter/test_cascade.py
- tests/charter/test_compiler.py
- tests/charter/test_mission_type_profiles.py
- tests/charter/test_mission_type_activations_seed_read_parity.py
- tests/charter/activation/test_effective_set.py
- tests/charter/activation/test_effective_set_chain.py
role: implementer
tags: []
tracker_refs: []
---
# WP04 — Resolver, cascade, compiler and mission-type suites ROI pass

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load the `python-pedro` profile with the `/spk-charter-profile-load` skill (load the profile YAML, not a persona name). Then load action doctrine: `spec-kitty charter context --action implement --json`.

## Objective

Review every test function in the files below against the #6485 rubric and remove the ones that do not guard a live contract, recording each verdict in the ledger. Target code under test: src/charter/ resolver, activation cascade and compiler modules. No product code changes.

## Context

- Mission spec: `kitty-specs/charter-tests-deep-roi-pass-01M5AN9J/spec.md`; plan: `plan.md`; ledger format: `data-model.md`; per-file loop: `quickstart.md`.
- Baseline (`research.md`): 8503 passed / 29 skipped; `src/charter` coverage 95.93%. Mission-wide coverage budget: ≤ 1.0 pp drop (NFR-002) — keep this WP's share well under it.
- The branch is stacked on PR #6483, which already removed the obvious low-value tests; what remains needs per-function reading.

## Owned files

- `tests/charter/test_resolver.py`
- `tests/charter/test_resolver_activation_parity.py`
- `tests/charter/test_cascade.py`
- `tests/charter/test_compiler.py`
- `tests/charter/test_mission_type_profiles.py`
- `tests/charter/test_mission_type_activations_seed_read_parity.py`
- `tests/charter/activation/test_effective_set.py`
- `tests/charter/activation/test_effective_set_chain.py`

## Rubric (issue #6485, binding)

- **Delete**: change-detectors (exact strings, counts or ordering of *incidental* output), tautologies (asserts what it just set up), mock-only tests (every collaborator mocked; asserts the mocks), tests of retired paths, and private-helper tests whose branches are already exercised through the public path.
- **Keep**: tests that guard a live contract and have no equivalent elsewhere.
- **Merge / parametrize** (operator ruling): near-duplicates may be folded into one surviving test that asserts the union of their checks. The merge target must be in this WP's owned files.
- **Name the covering test** for every deletion — a full node id (`tests/.../test_x.py::TestY::test_z`). Look in `tests/charter/`, `tests/charter_offering/` and `tests/architectural/`. If no covering test exists and you still remove it (low ROI: clunky, flaky or heavy for a marginal coverage gain), write `none — low ROI` plus the reason and the `src/charter` lines that lose coverage.

**How to confirm a covering test** (do not guess from names): read the covering test and check it reaches the same branch with an assertion on the same outcome. When unsure, run the covering test under `--cov=<module> --cov-report=term-missing` with and without the candidate and compare the missed lines.

**Read-only shared surfaces** (no WP owns them): `tests/charter/conftest.py` (including its autouse fixtures), `tests/charter/synthesizer/conftest.py`, `tests/charter/org_pack_identity_support.py`, `tests/charter/skill_pack_support.py`, `tests/charter/fixtures/`. If a change leaves a helper unused, note it in the ledger — do not delete it.

**Cross-WP citations**: when a covering test sits in a file another WP owns, mark the row `frozen-by-citation` in the Note column. That WP must not delete it; the orchestrator checks every cited node id still exists before consolidation. Prefer covering tests in files no WP owns (`tests/charter_offering/`, `tests/architectural/`, unlisted `tests/charter/` files).

**Account for every test** (non-vacuity): record `pytest --collect-only -q <file> | grep -c '::'` before and after for each file; Kept + Deleted + Merged + Rewritten must equal the before count. Every "keep" verdict in a named duplicate cluster needs a one-line reason.

**Do not touch**: anything under `src/` (C-001), `tests/architectural/` (C-002), files owned by another WP. Do not add `# noqa` / `# type: ignore`. Do not run `make test-full` or a whole `tests/architectural/` sweep.

**Edge cases**: a test marked `regression` or naming an issue number pins a known defect — keep unless the issue is closed *and* a functional test covers the behaviour; cite the `unset GITHUB_TOKEN; gh issue view N -R spec-kitty/spec-kitty --json state` result in the ledger row. A test that looks redundant but asserts an error *code* or *exit code* usually guards a contract — keep it.

## Subtasks

### T016 — Review `test_resolver.py` (1021) and `test_resolver_activation_parity.py` (257)

**Purpose**: per-function verdicts for this file set.

**Notes**: Resolver tier precedence is a core contract — keep precedence tests. Parity file may compare a retired resolution path.

**Steps**:
1. Read the file fully; list every test (`grep -n 'def test_' <file>`).
2. Classify each against the rubric; for each non-keep, find and verify the covering test.
3. Edit (delete / merge / rewrite). Keep fixtures that surviving tests still use; delete fixtures that become unused.
4. Run the file plus every covering test you named: `PWHEADLESS=1 .venv/bin/python -m pytest <file> <covering tests> -q -p no:cacheprovider`.
5. Append the file section to the ledger.
6. Commit this file's change on its own (`test(charter): ROI pass on <file> (#6485)`), with the counts in the body.

**Validation**: file's surviving tests green; every deletion has a ledger row.

### T017 — Review `test_cascade.py` (948)

**Purpose**: per-function verdicts for this file set.

**Notes**: Cascade follows DRG edges (CLAUDE.md, Charter Cascade). Keep shared-reference safety (C-005) tests. Delete tests that pin warning text verbatim when another test asserts the recovery command is suggested.

**Steps**:
1. Read the file fully; list every test (`grep -n 'def test_' <file>`).
2. Classify each against the rubric; for each non-keep, find and verify the covering test.
3. Edit (delete / merge / rewrite). Keep fixtures that surviving tests still use; delete fixtures that become unused.
4. Run the file plus every covering test you named: `PWHEADLESS=1 .venv/bin/python -m pytest <file> <covering tests> -q -p no:cacheprovider`.
5. Append the file section to the ledger.
6. Commit this file's change on its own (`test(charter): ROI pass on <file> (#6485)`), with the counts in the body.

**Validation**: file's surviving tests green; every deletion has a ledger row.

### T018 — Review `test_compiler.py` (932; contains a 21 s test)

**Purpose**: per-function verdicts for this file set.

**Notes**: `test_write_compiled_charter_succeeds_without_force_when_existing` takes 21 s. Find why (likely a full `charter generate`); cheapen it with a smaller fixture if it keeps its contract. Note: `test_compiler_charter_yaml.py` belongs to WP06, not this WP.

**Steps**:
1. Read the file fully; list every test (`grep -n 'def test_' <file>`).
2. Classify each against the rubric; for each non-keep, find and verify the covering test.
3. Edit (delete / merge / rewrite). Keep fixtures that surviving tests still use; delete fixtures that become unused.
4. Run the file plus every covering test you named: `PWHEADLESS=1 .venv/bin/python -m pytest <file> <covering tests> -q -p no:cacheprovider`.
5. Append the file section to the ledger.
6. Commit this file's change on its own (`test(charter): ROI pass on <file> (#6485)`), with the counts in the body.

**Validation**: file's surviving tests green; every deletion has a ledger row.

### T019 — Review `test_mission_type_profiles.py` (1249) and `test_mission_type_activations_seed_read_parity.py` (131)

**Purpose**: per-function verdicts for this file set.

**Notes**: Likely per-mission-type repetition: candidates for parametrization (FR-004).

**Steps**:
1. Read the file fully; list every test (`grep -n 'def test_' <file>`).
2. Classify each against the rubric; for each non-keep, find and verify the covering test.
3. Edit (delete / merge / rewrite). Keep fixtures that surviving tests still use; delete fixtures that become unused.
4. Run the file plus every covering test you named: `PWHEADLESS=1 .venv/bin/python -m pytest <file> <covering tests> -q -p no:cacheprovider`.
5. Append the file section to the ledger.
6. Commit this file's change on its own (`test(charter): ROI pass on <file> (#6485)`), with the counts in the body.

**Validation**: file's surviving tests green; every deletion has a ledger row.

### T020 — Resolve cluster 3: `activation/test_effective_set.py` ↔ `activation/test_effective_set_chain.py`

**Purpose**: per-function verdicts for this file set.

**Notes**: 329 vs 99 lines; `test_effective_set.py` is 35 s summed. Record the cluster verdict.

**Steps**:
1. Read the file fully; list every test (`grep -n 'def test_' <file>`).
2. Classify each against the rubric; for each non-keep, find and verify the covering test.
3. Edit (delete / merge / rewrite). Keep fixtures that surviving tests still use; delete fixtures that become unused.
4. Run the file plus every covering test you named: `PWHEADLESS=1 .venv/bin/python -m pytest <file> <covering tests> -q -p no:cacheprovider`.
5. Append the file section to the ledger.
6. Commit this file's change on its own (`test(charter): ROI pass on <file> (#6485)`), with the counts in the body.

**Validation**: file's surviving tests green; every deletion has a ledger row.

### T021 — Validate the WP and finish the ledger

1. Run the whole owned set in one go: `PWHEADLESS=1 .venv/bin/python -m pytest tests/charter/test_resolver.py tests/charter/test_resolver_activation_parity.py tests/charter/test_cascade.py ... -q -p no:cacheprovider` (all owned files).
2. Run `tests/charter_offering/` fast: `PWHEADLESS=1 .venv/bin/python -m pytest tests/charter_offering -n auto --dist loadfile -q -p no:cacheprovider` (covering tests must still pass).
3. `ruff check <owned files>` and `ruff format --check --force-exclude <owned files>`; `mypy` is not required for test files unless the repo config includes them.
4. Finish the ledger: cluster sections, coverage note, totals line (`Tests before → after`, `Lines before → after`).
5. Report back: the ledger path, the commit list, and the commands run with pass/fail counts.

## Ledger (FR-002, FR-006)

Write the ledger at `<orchestrator-scratchpad>/ledger-WP04.md` — **not** inside `kitty-specs/` (a code WP may not own mission-dir paths). The orchestrator commits it into the mission dir as `roi-ledger/WP04.md` before review. Format (see `kitty-specs/charter-tests-deep-roi-pass-01M5AN9J/data-model.md`):

```markdown
## tests/charter/<path>.py

Kept: 12 · Deleted: 5 · Merged: 2 · Rewritten: 1 · Lines: 980 → 610

| Test | Verdict | Rubric class | Covering test / merge target | Note |
|------|---------|--------------|------------------------------|------|
| test_renders_header_exactly | delete | change-detector | tests/charter/test_context.py::test_bootstrap_has_header_marker | pins whole header text |
```

Add a `## Cluster N: A ↔ B` section per owned cluster (`Verdict:` merged / A deleted / B deleted / distinct, `Reason:`), and a final `## Coverage note` listing any `src/charter` lines that lost coverage, with the reason (or "none").

## Branch Strategy

Planning base and merge target: `feat/6485-charter-tests-deep-roi-pass`. The execution worktree is allocated per computed lane from `lanes.json`; start with:

```bash
spec-kitty agent action implement WP04 --agent claude --mission charter-tests-deep-roi-pass-01M5AN9J
```

Work only inside the resolved lane workspace path; never reconstruct it.

## Definition of Done

- Every test in every owned file has a verdict (kept tests counted in the ledger header).
- Every deletion/merge has a ledger row with a covering test node id or `none — low ROI` + reason.
- Every owned cluster has a verdict section.
- Owned files and `tests/charter_offering/` pass; ruff check and format clean.
- No `src/` or `tests/architectural/` change; no new suppressions.

## Risks

- **False covering test**: a test with a similar name that does not reach the same branch. Mitigation: confirm by reading or by the coverage comparison.
- **Shared fixtures**: deleting a fixture another file imports. Mitigation: `grep -rn <fixture> tests/` before removing.
- **Over-deletion of contract tests** that assert an error code or a parseable marker. Mitigation: edge-case rule above.

## Reviewer Guidance

Reviewer: `reviewer-renata` (opus). Sample at least 10 deletions (or all, if fewer) and confirm the named covering test really covers them. Check the ledger rows match the diff one to one. Run the owned files and the named covering tests. Reject on any deletion without a verified covering test that is not justified as low ROI.
