---
work_package_id: WP03
title: Drift gate, docs and evidence
dependencies:
- WP01
requirement_refs:
- FR-007
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6741-step-contract-urn-identity
merge_target_branch: issue-6741-step-contract-urn-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6741-step-contract-urn-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6741-step-contract-urn-identity unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
phase: Phase 3 - Gates and evidence
history:
- at: '2026-10-31T08:52:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: reviewer-renata
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_drg_urn_identity_parity.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_drg_urn_identity_parity.py
- docs/architecture/doctrine-kinds.md
- docs/changelog/CHANGELOG.md
role: reviewer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Drift gate, docs and evidence

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `reviewer-renata`
- **Role**: `reviewer`
- **Agent/tool**: *(the harness running this WP)*

## ⚠️ IMPORTANT: Review Feedback

Read the `review_ref` field in the status event log (`spec-kitty agent tasks status`) before
starting.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- An architectural gate fails when a built-in DRG node's URN and the declared identity of the
  artifact it names disagree — in **both** directions (no orphan node, no missing node).
- The gate is proven non-vacuous by a planted-divergence arm using the same checker function.
- `docs/architecture/doctrine-kinds.md` states the step-contract URN tail rule and where it lives.
- `docs/changelog/CHANGELOG.md` gains one `[Unreleased]` entry for `(#6741)`.
- All targeted tests, `make test-fast`, ruff, mypy and the docs-freshness check pass; the exact
  commands and results are recorded for the PR body.

## Context & Constraints

- Depends on WP01 + WP02.
- The gate must read the **built-in** graph only (`packs/built-in/*.graph.yaml`), because
  `packs/built-in/` is fetched from the pinned open-packs commit and the org pack in this repository
  is an overlay: mixing them would make the gate depend on this repo's local configuration.
- `architectural-gate-non-vacuity` tactic: a gate test must be paired with a test that proves the
  gate can fail.
- Changelog rules (charter, `DIRECTIVE_037`): bold impact-first lead with `(#6741)`, before/after,
  under 1,200 characters, under `[Unreleased]`.

## Branch Strategy

- **Strategy**: `{{branch_strategy}}`
- **Planning base branch**: `issue-6741-step-contract-urn-identity`
- **Merge target branch**: `issue-6741-step-contract-urn-identity`

## Subtasks & Detailed Guidance

### Subtask T011 – The drift gate

- **Purpose**: Make the identity mismatch a red gate, not a silent one.
- **Steps**: Create `tests/architectural/test_drg_urn_identity_parity.py`
  (`pytestmark = [pytest.mark.architectural, pytest.mark.doctrine]`):
  - Load the built-in graph fragments from `packs/built-in/*.graph.yaml` for the activatable kinds —
    do not use `load_validated_graph(repo_root)` (it merges the org pack). Prefer the shipped
    fragment files directly, e.g. via `charter.offering.drg`'s loader per file, or reconstruct the
    graph the way the shipped fragments are produced and compare URN sets.
  - Build an `IdentityIndex` over the built-in layer only (`IdentityIndex(offering_root=<built-in
    pack root>)`, no org roots, no project root — check the constructor's signature in
    `src/charter/activation/identity_index.py`).
  - Checker function (module-level, shared with T012):

    ```python
    def _drifted_urns(nodes: Iterable[DRGNode], identity: IdentityIndex) -> list[str]:
        """Node URNs whose tail is not the canonical tail the identity authority names."""
    ```

    A node drifts when `identity.urn(kind, tail) != node.urn`, where `kind` is the node's
    `ArtifactKind` (skip kinds that are not charter-activatable, and skip nodes whose kind is not an
    `ArtifactKind` at all, e.g. `action`, `mission_type`, `template`, `asset`).
  - Test 1: `_drifted_urns(built_in_nodes, identity) == []`.
  - Test 2 (**both directions, step contracts**): the set of `mission_step_contract` node URNs in the
    shipped graph equals
    `{step_contract_urn(c.mission, c.action) for c in MissionStepContractRepository().list_all()}`
    — a missing node and an extra node both fail.
  - Test 3 (anti-empty-scan): assert the scan actually saw nodes for at least
    `{directive, tactic, styleguide, toolguide, paradigm, procedure, agent_profile,
    mission_step_contract}` — a silently empty scan must not pass.
- **Files**: `tests/architectural/test_drg_urn_identity_parity.py` (new).
- **Parallel?**: Yes.
- **Notes**: This gate is red on the pre-fix tree for exactly the 21 step-contract nodes — record
  that output as red-first evidence for the PR body.

### Subtask T012 – Non-vacuity arm

- **Purpose**: Prove the gate can fail.
- **Steps**: In the same file, build a synthetic node list containing
  `DRGNode(urn="mission_step_contract:documentation-accept", kind=NodeKind.MISSION_STEP_CONTRACT)`
  (the pre-fix spelling) plus one correct node, and assert `_drifted_urns(...)` reports exactly the
  planted URN. Also plant one for an ordinary kind (e.g. `directive:NOT_A_REAL_ID`) to show the
  general arm bites too.
- **Files**: `tests/architectural/test_drg_urn_identity_parity.py`.
- **Parallel?**: Yes, with T011 (same file — implement together).
- **Notes**: Name the tests so the intent is obvious (`..._bites_on_a_planted_divergence`).

### Subtask T013 – Architecture doc

- **Purpose**: Operators and maintainers read the rule, not the code.
- **Steps**: In `docs/architecture/doctrine-kinds.md`, in the existing `### Mission step contract`
  section, add one short paragraph: the DRG URN is `mission_step_contract:<mission>/<action>` (not
  the declared id, unlike every other kind), the declared id is what activation lists and the CLI
  use, `IdentityIndex.urn` maps one to the other, and
  `charter.offering.missions.step_contracts.step_contract_urn` is the one implementation (with the
  `#6741` reference). Do not restructure the page.
- **Files**: `docs/architecture/doctrine-kinds.md`.
- **Parallel?**: Yes.
- **Notes**: Keep it to 3–5 sentences; the page's prose style is plain and dense.

### Subtask T014 – Changelog

- **Purpose**: A user-facing behaviour change needs a changelog entry.
- **Steps**: Add one bullet at the top of `[Unreleased]` in `docs/changelog/CHANGELOG.md`:
  bold impact-first lead naming the fix and `(#6741)`, then "before" (activating a built-in mission
  step contract reported a graph gap whose only suggested remedy was a resynthesis that could not
  help; deactivating one by its declared id had no effect) and "after" (activation, deny and the
  config↔graph parity check all resolve through one identity authority; a new architectural gate
  fails if the graph URN and the declared identity drift again). Under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: Yes.
- **Notes**: Root `CHANGELOG.md` is a symlink — edit `docs/changelog/CHANGELOG.md`.

### Subtask T015 – Verification sweep

- **Purpose**: Evidence for the PR body and for review.
- **Steps**: Run and record (command + result) each:

  ```bash
  uv run pytest tests/charter/activation/test_identity_index_urn.py -q
  uv run pytest tests/charter/activation/test_step_contract_urn_identity.py -q
  uv run pytest tests/architectural/test_drg_urn_identity_parity.py -q
  uv run pytest tests/charter/activation tests/charter/test_activation_filtered_drg.py \
    tests/charter/test_activation_consumers.py tests/charter_offering/test_activation_parity_guard.py -q
  uv run pytest tests/charter_offering/drg/migration/test_extractor_projection.py \
    tests/review/test_gate_bindings.py -q
  uv run python -m scripts.docs.check_docs_freshness --ci
  make test-fast
  ```

  Do not run a full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- **Files**: none (evidence only; paste results into the WP history note).
- **Parallel?**: No — last.
- **Notes**: Any failure not attributable to this diff must be reproduced on pristine `origin/main`
  in a clean worktree before being reported; cite the existing issue if there is one.

## Test Strategy

See T015. The gate tests carry `pytest.mark.architectural` so they run in the architectural shard;
`make test-fast` must include the activation shard (verify, do not assume).

## Risks & Mitigations

- **Gate reading the wrong graph** (org overlay creeping in) → assert in the test that the built-in
  fragment root is `packs/built-in` and that no org root is passed to the index.
- **Gate passing because it scanned nothing** → T011 test 3.
- **Docs churn** → one section paragraph, one changelog bullet; run the freshness check.

## Review Guidance

- Confirm the gate is red on the pre-fix tree (ask for the failure text) and green now.
- Confirm the non-vacuity arm uses the same checker function as the corpus test.
- Confirm the changelog entry is impact-first, cites `(#6741)` and stays under 1,200 characters.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
