---
work_package_id: WP02
title: Consumers re-pointed, remedy made truthful
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-002
- NFR-003
- C-002
planning_base_branch: issue-6741-step-contract-urn-identity
merge_target_branch: issue-6741-step-contract-urn-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6741-step-contract-urn-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6741-step-contract-urn-identity unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Consumers
history:
- at: '2026-10-31T08:52:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/activation/test_step_contract_urn_identity.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/drg_activation.py
- src/charter/activation/consistency_check.py
- src/charter/activation/activation_ledger.py
- src/specify_cli/review/gate_bindings.py
- tests/charter/activation/test_step_contract_urn_identity.py
- tests/charter/activation/test_deny_identity_space.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Consumers re-pointed, remedy made truthful

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: *(the harness running this WP)*

## ⚠️ IMPORTANT: Review Feedback

Read the `review_ref` field in the status event log (`spec-kitty agent tasks status`) before
starting. Address every feedback item before marking the WP done.

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

- The four remaining URN constructions in the activation layer delegate to
  `IdentityIndex.urn(kind, token)` / `step_contract_urn(mission, action)`.
- An activated built-in step contract (`documentation-accept`) survives the activation filter and
  produces **no** `graph_kind_gaps` entry.
- Denying a step contract by its declared id (`implement`) removes its node from the filtered graph.
- The parity suggestion distinguishes "artifact absent from the DRG" (regenerate) from "artifact
  present but filtered out by activation" (check the activation keys).
- Nothing about `_node_is_activated`'s decision order changes (C-002).

## Context & Constraints

- Depends on WP01 (`IdentityIndex.urn`, `step_contract_urn`).
- Contract: `kitty-specs/step-contract-urn-identity-01M68JDC/contracts/urn-identity-contract.md`.
- The reproduction lives in `kitty-specs/step-contract-urn-identity-01M68JDC/research.md` and
  `quickstart.md`.
- `charter` may not import `specify_cli` (C-003); `specify_cli` reaches charter through the
  `charter.mission_steps` facade.
- Pre-existing behaviour that must not change: the filter's mission-type ownership rule still returns
  before the per-id gate for mission-scoped step contracts, and the "absent from the DRG" suggestion
  keeps its exact wording (existing tests assert it).

## Branch Strategy

- **Strategy**: `{{branch_strategy}}`
- **Planning base branch**: `issue-6741-step-contract-urn-identity`
- **Merge target branch**: `issue-6741-step-contract-urn-identity`

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first regression tests

- **Purpose**: Prove the defect through the pre-existing entry points before fixing it.
- **Steps**: Create `tests/charter/activation/test_step_contract_urn_identity.py` (`pytestmark =
  [pytest.mark.fast, pytest.mark.doctrine]`), using the real built-in graph and the repo's own
  `PackContext` (`dataclasses.replace` to set `activated_mission_step_contracts` /
  `activated_mission_types`). Cases:
  1. **Filter parity (RED before T007/T008).** With `activated_mission_step_contracts =
     {"documentation-accept"}` and all four mission types active, call
     `consistency_check._check_graph_kind_parity` (or the smallest public surface that reaches
     `_resolve_graph_kind_parity_stem`) with `raw_activated_by_kind = {"mission-step-contract":
     ["documentation-accept"]}` and assert `graph_kind_gaps == []`. On the pre-fix tree it appends
     `mission-step-contract/documentation-accept`.
  2. **Filter survival (characterization).** `filter_graph_by_activation(...)` keeps
     `mission_step_contract:documentation/accept`.
  3. **Deny by declared id (RED before T009).** `deactivated_mission_step_contracts = ["implement"]`
     → `mission_step_contract:software-dev/implement` is absent from the filtered graph, while
     `mission_step_contract:software-dev/plan` is present.
  4. **Truthful suggestion (RED before T008).** The same fixture as case 1 but with
     `activated_mission_types = {"software-dev"}` (so the `documentation` contract is filtered out):
     the gap is reported and its suggestion names the mission-type activation, and does **not**
     contain "resynthesize".
  5. **Non-step kinds untouched.** For a populated `activated_directives` set, the surviving
     `directive:` URN set equals the pre-fix expectation (assert the exact expected URNs).
- **Files**: `tests/charter/activation/test_step_contract_urn_identity.py` (new).
- **Parallel?**: No — write it first and record the failure output.
- **Notes**: Use the real built-in graph (`charter.activation._drg_helpers.load_validated_graph`)
  rather than a hand-built fixture — the defect only exists against the shipped corpus.

### Subtask T007 – Filter token resolution

- **Purpose**: The per-kind activation set must resolve to URNs that exist.
- **Steps**: In `src/charter/activation/drg_activation.py::_resolve_activated_urns_for_kind`, replace

  ```python
  declared = identity.declared_id(kind_enum, token)
  if declared is not None:
      urns.add(f"{kind_enum.value}:{declared}")
  ```

  with a resolution through `identity.urn(kind_enum, token)` (skip `None`). Update the docstring:
  tokens resolve through the identity index's canonical URN, which is `<kind>:<declared id>` for
  ordinary kinds and `<mission>/<action>` for a mission step contract (see #6741).
- **Files**: `src/charter/activation/drg_activation.py`.
- **Parallel?**: Yes, after T006.
- **Notes**: Do **not** reorder `_node_is_activated`; this WP changes only the source of the resolved
  set. `_NO_STEM_RESOLUTION_KINDS` (`anti_pattern`) keeps its bypass.

### Subtask T008 – Parity check + truthful remedy

- **Purpose**: Compare against the URN the authority names, and stop prescribing a resynthesis for a
  node that exists but was filtered out.
- **Steps**: In `src/charter/activation/consistency_check.py`:
  - `_resolve_graph_kind_parity_stem` builds `urn` from `identity.urn(kind_enum, stem)`; `None`
    keeps today's skip.
  - Pass the **unfiltered** graph's URN set alongside `surviving_urns` (compute it once in
    `_check_graph_kind_parity` from `full_drg`).
  - Suggestion split:
    - `urn not in full_urns` → today's text, byte-identical ("... Regenerate graph.yaml / run
      'spec-kitty charter resynthesize' and check 'activated_kinds' in config.yaml.").
    - `urn in full_urns` (filtered out) → name the activation keys that can filter it, e.g.
      "`<cli_kind>/<stem>`: Activated in config.yaml but the activation filter drops it. Check
      `activated_mission_types` (a mission step contract is kept only while its owning mission type
      is active) and `activated_kinds` in config.yaml; regenerating the graph will not change this."
  - Update the function docstring to describe both arms.
- **Files**: `src/charter/activation/consistency_check.py`.
- **Parallel?**: Yes.
- **Notes**: `_check_graph_kind_parity` already loads `full_drg`; do not load it twice
  (`_GateResources` exists for the expensive shared loads — a plain second `load` here would be a
  regression; reuse the local `full_drg` variable).

### Subtask T009 – Deny in URN space

- **Purpose**: `deactivated_mission_step_contracts: [implement]` must actually deny
  `mission_step_contract:software-dev/implement`.
- **Steps**: In `src/charter/activation/activation_ledger.py`:
  - Add `urn` to the `IdentityLookup` protocol (`def urn(self, kind, token) -> str | None: ...`).
  - `_spell`: for a known token use `identity.urn(kind, token)` (falling back to the current
    `f"{kind.value}:{declared}"` only if `urn` returns `None`); the unknown-token arm keeps
    `artifact_to_urn(kind.value, token)` so a mission-scoped deny spelling still resolves.
  - Update both docstrings (protocol + `_spell`) to say the URN comes from the one authority.
  - Update `tests/charter/activation/test_deny_identity_space.py::_FakeIdentity` to implement `urn`
    with the plain `<kind>:<declared id>` rule (its fixtures are ordinary kinds), and add one case
    asserting a known step-contract token's `DenySet.urns` contains the mission-scoped URN.
- **Files**: `src/charter/activation/activation_ledger.py`,
  `tests/charter/activation/test_deny_identity_space.py`.
- **Parallel?**: Yes.
- **Notes**: `DenySet.stems` / `declared_ids` keep their meaning; only the URN spelling changes, and
  only for step contracts.

### Subtask T010 – Gate join delegates

- **Purpose**: The pre-review gate join's URN and the graph's URN come from one function.
- **Steps**: In `src/specify_cli/review/gate_bindings.py::owning_contract_urn`, return
  `step_contract_urn(mission, action)` (imported from `charter.mission_steps`), and update the
  docstring to point at the authority. Keep behaviour identical (the string is unchanged).
- **Files**: `src/specify_cli/review/gate_bindings.py`.
- **Parallel?**: Yes.
- **Notes**: `tests/review/test_gate_bindings.py` and the pre-review gate tests already assert
  `mission_step_contract:software-dev/review`; they must stay green unchanged.

## Test Strategy

```bash
uv run pytest tests/charter/activation/test_step_contract_urn_identity.py -q
uv run pytest tests/charter/activation/test_deny_identity_space.py tests/charter/test_activation_filtered_drg.py -q
uv run pytest tests/charter/test_activation_consumers.py tests/charter_offering/test_activation_parity_guard.py -q
uv run pytest tests/review/test_gate_bindings.py tests/review/test_pre_review_gate_integration.py -q
uv run ruff check src/charter/activation src/specify_cli/review/gate_bindings.py
uv run mypy src/charter/activation/identity_index.py src/charter/activation/consistency_check.py \
  src/charter/activation/activation_ledger.py
```

## Risks & Mitigations

- **Behaviour drift in the filter**: `test_charter_readers_honour_deny.py` and
  `test_activation_filtered_drg.py` pin the current precedence — run them.
- **Message churn**: existing tests assert the "Regenerate graph.yaml" text; the new arm is additive.
- **A second graph load**: reuse `full_drg` in `_check_graph_kind_parity` rather than reloading.

## Review Guidance

- Confirm the suggestion arms are distinguishable and that only the filtered-out arm gained text.
- Confirm `identity.urn` is called once per token (not per node).
- Confirm no non-step kind's deny or activation behaviour changed (see the added per-kind assertion).

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
