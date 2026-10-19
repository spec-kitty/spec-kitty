---
work_package_id: WP02
title: 'Reach-only by kind: synthesized styleguides follow their directive'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-019
- C-001
- C-002
- C-003
- SC-001
- SC-002
planning_base_branch: issue-6442-charter-synthesis-graph-work
merge_target_branch: issue-6442-charter-synthesis-graph-work
branch_strategy: Planning artifacts for this mission were generated on issue-6442-charter-synthesis-graph-work. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6442-charter-synthesis-graph-work unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Synthesis graph
history: []
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/
create_intent:
- tests/charter/synthesizer/test_styleguide_reach_only.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/activation/action_governance_bundle.py
- src/charter/activation/synthesizer/reach_only.py
- src/charter/activation/synthesizer/reconcile.py
- src/charter/activation/synthesizer/project_drg.py
- src/charter/activation/synthesizer/interview_mapping.py
- src/charter/activation/synthesizer/targets.py
- src/charter/activation/synthesizer/resynthesize_pipeline.py
- src/charter/activation/compiler.py
- src/charter/activation/api.py
- src/specify_cli/cli/commands/charter/synthesize.py
- src/specify_cli/cli/commands/charter/resynthesize.py
- tests/charter/synthesizer/test_styleguide_reach_only.py
- tests/charter/synthesizer/test_reach_only_delivery.py
- tests/charter/synthesizer/test_synthesize_activation_append.py
- tests/charter/synthesizer/test_project_drg.py
- tests/charter/synthesizer/test_synthesize_reconcile.py
- tests/charter/synthesizer/test_edge_wiring.py
- tests/architectural/test_charter_activation_api_reexport.py
- tests/charter/fixtures/synthesizer/styleguide/**
- docs/adr/4.x/2026-10-06-2-charter-offering-active-charter-and-activation-presets.md
- docs/adr/3.x/2026-04-17-1-charter-synthesizer-adapter-seam.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Reach-only by kind: synthesized styleguides follow their directive

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objective

Make synthesized testing, quality-gate and documentation styleguides reach-only: sourced from their directive and delivered only while it is in force. Make an operator's removal stick. Generalise the #6404 tactic model by kind instead of copying it (FR-001..FR-005).

## Context

- Read `spec.md` (User Story 1, scenarios 1-8), `plan.md` (D-01, D-02, D-03, D-10) and the resolved decisions in `decisions/`.
- Settled rules, which must hold:
  - **Removal sticks** (ADR 2026-10-06-2, amendment 2026-10-19).
  - **Synthesis never creates an `activated_*` key.**
  - **Absent-key semantics (#4253, #4400) are unchanged.**
- Current tactic implementation:
  - `reach_only.py`: `CREATED_TACTICS_PATH`, `_read/_write_created_tactics`, `reach_only_tactic_ids`, `append_synthesized_tactic_activations`, `created_tactic_slugs`.
  - `reconcile.py`: `synthesized_tactic_reason`, `is_synthesized_tactic_edge`, `edge_owner`, `_is_legacy_applies` and its users `legacy_applies_edges`, `merge_project_overlay`, `_graph_delta`.
  - `project_drg.py`: `_derived_edge`.
  - Root filters: `compiler.py` `_direct_root_urns` (around lines 297-316) and `action_governance_bundle.py` (around line 401).
- The edge-reason text for tactics must stay byte-identical, because existing overlays carry it.

### Subtask T005: Red-first acceptance tests

- Create `tests/charter/synthesizer/test_styleguide_reach_only.py` (`@pytest.mark.regression`, #6442). It covers spec US1 scenarios 1-8 at the narrowest seam that still runs the production path:
  - **Edge emission:** a `testing_philosophy` answer yields `directive:DIRECTIVE_034 --suggests--> styleguide:<slug>`. `quality_gates` maps to DIRECTIVE_030 and `documentation_policy` to DIRECTIVE_037.
  - **The red-first case: the compiled-references root.** A configured project with an explicit `activated_styleguides` that contains the synthesized styleguide, and `DIRECTIVE_034` not active. The styleguide is not in `_direct_root_urns`, and not in `charter context --action implement` output. Pair it on the same fixture with an unsourced `language_scope` styleguide that IS still rooted.
  - **New delivery:** with `DIRECTIVE_034` in force, the styleguide is delivered to software-dev `implement`. Also cover a configured project with the `activated_styleguides` key absent.
  - **Removal sticks:**
    - first creation appends to an explicit list;
    - after removal, a re-run does not re-append;
    - an absent key stays absent;
    - styleguides that already existed in the manifest before a recording run are not appended;
    - an unreadable record appends nothing for any kind and warns.
  - **Legacy edge:** a `styleguide --applies--> X` overlay edge is stripped and reported.
  - **No dangling URN:** a DRG snapshot without the table directive emits no edge.
  - **Org-required:** a synthesized styleguide whose id an org pack requires stays a compiled-references root.
- Confirm each fails on the current source. Record which ones fail in the WP history.

### Subtask T006: Styleguide source table and per-kind source_urns (FR-001)

- In `interview_mapping.py`, add `_STYLEGUIDE_SOURCE_DIRECTIVES = {"testing_philosophy": "DIRECTIVE_034", "quality_gates": "DIRECTIVE_030", "documentation_policy": "DIRECTIVE_037"}`.
- Emit `source_urns_by_kind = {"styleguide": ("directive:…",)}` statically from the table. `interview_mapping` must not read the DRG (R-9, `targets.py` around lines 207-210).
- The `testing_philosophy` tactic must NOT get this source.
- `_append_language_scope_results` emits no source.
- In `targets.build_targets`, merge `source_urns_by_kind[kind]` into each target's `source_urns` inside the per-kind loop. First filter the table URNs against the snapshot with a small extracted helper over `_known_drg_urns(drg_snapshot)`, so that a missing directive omits the edge instead of tripping `_validate_source_urns` (`ProjectDRGValidationError`). Make the helper standalone: WP03 deletes `_mission_type_evidence_urns`.

### Subtask T007: Generalise reach-only and reconcile by kind (FR-002, FR-004, FR-005)

- **Generalised names:**
  - `REACH_ONLY_KINDS`
  - `synthesized_edge_reason(kind, slug)` (keep the tactic text identical)
  - `is_synthesized_source_edge`
  - `edge_owner`, owned by the target for every reach-only kind
  - `_is_legacy_applies`, for any reach-only source kind (update its docstring, which today calls styleguide `applies` the "current shape")
  - `_derived_edge` → `suggests` for every reach-only kind
  - `reach_only_ids(repo_root, kind)`, with org-required ids excluded per kind
- **Callers:** update every caller. Remove or alias the tactic-only names: keep public names only where `charter.activation.api` must stay stable, and update `tests/architectural/test_charter_activation_api_reexport.py`.
- **Compiled-references filter:** `compiler._direct_root_urns` filters reach-only styleguides from `config_roots.styleguides`, as it does for tactics.
- **Action bundle:** it seeds no styleguide roots; keep it that way and pin it in a test. It imports `reach_only_tactic_ids` (around line 38), so switch that call to `reach_only_ids(root, "tactic")` and remove the tactic-only name. You own this file for that edit only.

### Subtask T008: Per-kind created-artifact record (FR-003, D-01)

- **New record:** `.kittify/charter/synthesized-artifacts.yaml` with keys `created_tactics` and `created_styleguides`, plus a header comment.
- **Reading:**
  - take the union with the legacy `.kittify/charter/synthesized-tactics.yaml` `created_tactics`;
  - never write the legacy file;
  - preserve keys it does not own on write;
  - writes are atomic (`kernel.atomic.atomic_write`).
- **Append rule:** `append_synthesized_activations(repo_root, created_by_kind)` applies the first-time rule per kind into `activated_tactics` and `activated_styleguides`, only when the key exists. It restamps the bundle hash once.
- **Fail closed:** if either file is unreadable, append nothing for any kind and warn.
- **Callers:** wire it into `cli/commands/charter/synthesize.py`, `resynthesize.py` and `resynthesize_pipeline.py` (`created_tactic_slugs` → per kind).

### Subtask T009: Update pinned tests and fixtures

- **Inverted tests:**
  - `tests/charter/synthesizer/test_project_drg.py::test_styleguide_source_urn_keeps_applies_edge` now expects `suggests`;
  - the styleguide case in `test_synthesize_reconcile.py` (around line 960) expects the edge stripped.
- **Updated tests:** `test_reach_only_delivery.py`, `test_synthesize_activation_append.py` (record path) and `test_edge_wiring.py`.
- **Fixtures:** re-key the fixture-adapter styleguide fixtures under `tests/charter/fixtures/synthesizer/styleguide/`, whose request hash changes because `source_urns` changes. No regeneration script exists, so use this procedure:
  1. Run the tests and read `expected_path` from `FixtureAdapterMissingError`.
  2. `git mv` the prior fixture body to that path. Add a new file instead if the old key is still exercised.
  3. Never compute hashes by hand.
- **Report:** list in the WP history every test whose expectation changed, and why.

### Subtask T010: ADR amendment (FR-019 part)

- Amend `docs/adr/4.x/2026-10-06-2-charter-offering-active-charter-and-activation-presets.md` with a dated 2026-10-19 point. Reach-only and removal-sticks now cover synthesized styleguides sourced through the table. The record is the per-kind `synthesized-artifacts.yaml`, which also reads the legacy tactic record.
- Also amend ADR `docs/adr/3.x/2026-04-17-1-charter-synthesizer-adapter-seam.md` (request-hash inputs): styleguide `source_urns` now enter the request hash. WP05 appends its own hash-rule note to the same ADR later.

## Definition of Done

- The T005 tests were red before the fix and are green after it, and the regression markers are converted.
- These pass:
  - `tests/charter/synthesizer/`
  - `tests/charter/test_default_in_force_snapshot.py` (byte-identical)
  - `tests/architectural/test_charter_activation_api_reexport.py`
  - `tests/architectural/test_runtime_charter_activation_boundary.py`
  - `tests/architectural/test_layer_rules.py`
  - `tests/architectural/test_no_dead_symbols.py`
  - `tests/architectural/test_charter_pack_path_authority.py`, `tests/architectural/test_charter_path_literal_authority.py` (spell no `.kittify/charter-packs` literal; use `kernel.charter_pack_paths`)
- ruff, format and `mypy --strict` are clean on changed files; complexity ≤ 15.

## Risks

- **Fixture re-keying churn:** keep it mechanical, and list it.
- **Dead-symbol gate:** do not leave module-internal names in `__all__`.
- **Overlay compatibility:** tactic reason text must not change.

## Reviewer Guidance

- Check that no `activated_*` key is ever created.
- Check that removal sticks across re-runs.
- Check the compiled-references root case is the one that was red.
- Check the new implement/review delivery is pinned.
- Check the single implementation by kind: no copy-pasted styleguide twins.
