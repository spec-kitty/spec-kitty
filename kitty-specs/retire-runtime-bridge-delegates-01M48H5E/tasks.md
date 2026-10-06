# Work Packages: Retire the runtime_bridge compat-delegate layer

**Inputs**: Design documents from `kitty-specs/retire-runtime-bridge-delegates-01M48H5E/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/bridge-surface.md, quickstart.md

**Tests**: required (ATDD red-first per charter C-011; the acceptance gate is WP01).

**Organization**: subtasks (`Txxx`) roll up into six work packages that run in sequence in the
repository root checkout (`single_branch`). One seam per migration WP, behind a static gate whose
per-seam rows start strict-xfail and flip as each seam is migrated.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows, not checkboxes: record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done --mission retire-runtime-bridge-delegates-01M48H5E`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Static acceptance gate (per seam) | WP01 | |
| T002 | Self-mutation (non-vacuity) tests | WP01 | |
| T003 | Characterise `_load_feature_runs` and `_build_run_ref` | WP01 | |
| T004 | Characterise `_parse_requirement_refs_from_tasks_md` | WP01 | |
| T005 | Identity: delete 3 delegates, remove back-edges | WP02 | |
| T006 | Cores: delete 2 delegates, keep the grammar adapter | WP02 | |
| T007 | Engine: delete `_advance_run_state_after_composition` | WP02 | |
| T008 | Repoint tests for the 6 names | WP02 | |
| T009 | Flip the gate rows | WP02 | |
| T010 | Delete the 9 delegates | WP03 | |
| T011 | Remove back-edges | WP03 | |
| T012 | Repoint tests | WP03 | |
| T013 | Flip the gate row | WP03 | |
| T014 | Delete the 8 delegates | WP04 | |
| T015 | Remove back-edges | WP04 | |
| T016 | Repoint tests (call-path review) | WP04 | |
| T017 | Flip the gate row | WP04 | |
| T018 | Delete the 13 delegates; add the two re-exports | WP05 | |
| T019 | Remove io back-edges to io names | WP05 | |
| T020 | Repoint tests for the 11 private names and `MissionRunRef` | WP05 | |
| T021 | Hazard 1: review every patch of a kept re-export by call path | WP05 | |
| T022 | Flip the gate row | WP05 | |
| T023 | `_check_cli_guards` docstring; last xfail | WP06 | |
| T024 | Stale compat comments sweep | WP06 | |
| T025 | Full targeted verification | WP06 | |
| T026 | Final false-green sweep | WP06 | |

---

## Work Package WP01: Acceptance gate and adapter characterisation (Priority: P1)

**Goal**: Make the end state checkable before any code changes, and pin the three adapter behaviours.
**Independent Test**: .venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py tests/runtime/test_bridge_adapter_characterisation.py -q
**Prompt**: `tasks/WP01-acceptance-gate-and-adapter-characterisation.md`
**Requirement Refs**: FR-001, FR-003, FR-005, FR-008, NFR-001

### Included Subtasks

T001 Static acceptance gate (per seam) (WP01)
T002 Self-mutation (non-vacuity) tests (WP01)
T003 Characterise `_load_feature_runs` and `_build_run_ref` (WP01)
T004 Characterise `_parse_requirement_refs_from_tasks_md` (WP01)

### Dependencies

- None (starting package).

### Risks & Mitigations

- **Vacuous gate**: mitigated by the 36-name floor, strict xfail, and the self-mutation tests.
- **Characterisation coupled to removed names**: the file must not touch `runtime_bridge.<removed name>`; otherwise WP05 would have to edit it and the "unchanged characterisation" proof is lost.

---

## Work Package WP02: Identity, cores and engine seams (Priority: P1)

**Goal**: Remove the 6 delegates owned by the identity (3), cores (2) and engine (1) seams, every
**Independent Test**: .venv/bin/python -m pytest tests/integration/test_explicit_checkout_commands.py tests/integration/test_owned_next_runtime.py tests/next/test_mission_run_back_reference.py tests/next/test_runtime_bridge_unit.py tests/runtime/next/test_committed_authority.py tests/runtime/next/test_merged_mission_terminal.py tests/runtime/test_bridge_composition.py tests/runtime/test_bridge_cores.py tests/runtime/test_bridge_decide_next.py tests/runtime/test_bridge_decision_log_flush.py tests/runtime/test_bridge_engine.py tests/runtime/test_bridge_io.py tests/runtime/test_decision_git_log_write_dir.py tests/runtime/test_requirement_grammar_parity.py tests/runtime/test_runtime_bridge_identity.py tests/runtime/test_runtime_identity_resolution.py tests/runtime/test_runtime_identity_seam_wiring.py tests/specify_cli/events/test_decision_log_coord.py tests/specify_cli/next/test_runtime_bridge.py tests/specify_cli/next/test_runtime_bridge_composition.py tests/runtime/test_bridge_adapter_characterisation.py -q -n auto --dist loadfile
**Prompt**: `tasks/WP02-identity-cores-and-engine-seams.md`
**Requirement Refs**: FR-001, FR-003, FR-006, FR-008, FR-010

### Included Subtasks

T005 Identity: delete 3 delegates, remove back-edges (WP02)
T006 Cores: delete 2 delegates, keep the grammar adapter (WP02)
T007 Engine: delete `_advance_run_state_after_composition` (WP02)
T008 Repoint tests for the 6 names (WP02)
T009 Flip the gate rows (WP02)

### Dependencies

- Depends on WP01

### Risks & Mitigations

- **Grammar adapter**: losing `grammar=` changes parsing; the WP01 characterisation test catches it.
- **Import cycles** when replacing deferred `_rb` lookups with seam imports: keep a deferred import of the owning seam where a cycle exists; verify `python -c "import runtime.next.runtime_bridge"` and the architectural boundary tests.

---

## Work Package WP03: Retrospective seam (Priority: P1)

**Goal**: Remove the 9 retrospective delegates (including the `_BufferingRuntimeEmitter` subclass alias),
**Independent Test**: .venv/bin/python -m pytest tests/architectural/test_runtime_emitter_seam.py tests/integration/retrospective/test_default_flow_generator_failure.py tests/integration/retrospective/test_default_flow_healthy.py tests/integration/retrospective/test_opt_out.py tests/integration/retrospective/test_policy_source_attribution.py tests/integration/retrospective/test_strict_flow_block.py tests/integration/retrospective/test_wp04_coverage_branches.py tests/next/test_mission_run_back_reference.py tests/next/test_runtime_bridge_unit.py tests/runtime/test_bridge_decide_next.py tests/runtime/test_bridge_decision_log_flush.py tests/runtime/test_bridge_engine.py tests/runtime/test_bridge_retrospective.py tests/specify_cli/next/test_runtime_bridge_composition.py tests/specify_cli/post_merge/test_retrospective_triggering.py tests/runtime/test_bridge_adapter_characterisation.py -q -n auto --dist loadfile
**Prompt**: `tasks/WP03-retrospective-seam.md`
**Requirement Refs**: FR-001, FR-003, FR-006, FR-009, FR-010, NFR-005

### Included Subtasks

T010 Delete the 9 delegates (WP03)
T011 Remove back-edges (WP03)
T012 Repoint tests (WP03)
T013 Flip the gate row (WP03)

### Dependencies

- Depends on WP02

### Risks & Mitigations

- **Emitter identity**: tests or production code may compare `type(emitter).__module__` or use `isinstance` against the bridge's subclass; check before deleting.
- **Silent false-green**: integration tests that patch the bridge's capture function to force a failure path would pass vacuously if they only assert "no exception"; check each asserts the fake was called or its effect is visible.

---

## Work Package WP04: Composition seam (Priority: P1)

**Goal**: Remove the 8 composition delegates, every back-edge to them (composition → itself, io →
**Independent Test**: .venv/bin/python -m pytest tests/doctrine/missions/test_referential_integrity.py tests/integration/test_custom_mission_runtime_walk.py tests/integration/test_documentation_runtime_walk.py tests/integration/test_explicit_checkout_commands.py tests/integration/test_owned_next_runtime.py tests/integration/test_research_runtime_walk.py tests/next/test_composition_gate_widening.py tests/next/test_occurrence_gate_next_loop.py tests/next/test_runtime_bridge_unit.py tests/runtime/_next_mission_scaffold.py tests/runtime/next/test_advance_guard_coord_reachability.py tests/runtime/next/test_cli_guard_family.py tests/runtime/next/test_composed_guard_launder.py tests/runtime/next/test_pertype_presence_gate.py tests/runtime/test_artifact_presence_placement.py tests/runtime/test_bridge_composition.py tests/runtime/test_bridge_cores.py tests/runtime/test_bridge_decide_next.py tests/runtime/test_bridge_decision_log_flush.py tests/runtime/test_bridge_io.py tests/runtime/test_next_board_authority.py tests/runtime/test_runtime_seam.py tests/specify_cli/missions/test_mission_template_consistency.py tests/specify_cli/next/test_runtime_bridge_composition.py tests/specify_cli/next/test_runtime_bridge_dispatch.py tests/specify_cli/next/test_runtime_bridge_documentation_composition.py tests/specify_cli/next/test_runtime_bridge_research_composition.py tests/runtime/test_bridge_adapter_characterisation.py -q -n auto --dist loadfile
**Prompt**: `tasks/WP04-composition-seam.md`
**Requirement Refs**: FR-001, FR-003, FR-006, FR-007, FR-010

### Included Subtasks

T014 Delete the 8 delegates (WP04)
T015 Remove back-edges (WP04)
T016 Repoint tests (call-path review) (WP04)
T017 Flip the gate row (WP04)

### Dependencies

- Depends on WP03

### Risks & Mitigations

- **io ↔ composition cycle**: a top-level import from io to composition will fail at import time; keep it deferred and say why in a short comment.
- **`_resolve_step_agent_profile` is read by both io and the bridge**: after this WP both look it up on composition, so a test patching it once covers both.

---

## Work Package WP05: IO seam and the public re-exports (Priority: P1)

**Goal**: Remove the 13 io delegates, make `get_or_start_run` / `build_operational_context_for_claim`
**Independent Test**: .venv/bin/python -m pytest tests/integration/test_custom_mission_runtime_walk.py tests/integration/test_documentation_runtime_walk.py tests/integration/test_identity_coord_read.py tests/integration/test_mission_run_command.py tests/integration/test_owned_next_runtime.py tests/integration/test_research_runtime_walk.py tests/next/test_decision_unit.py tests/next/test_internal_runtime_coverage.py tests/next/test_mission_run_back_reference.py tests/next/test_next_advance_first_contact_5310.py tests/next/test_next_command_integration.py tests/next/test_query_mode_unit.py tests/next/test_runtime_bridge_blocked_paths.py tests/next/test_runtime_bridge_unit.py tests/runtime/_next_mission_scaffold.py tests/runtime/next/test_advance_guard_coord_reachability.py tests/runtime/next/test_cli_guard_family.py tests/runtime/test_bridge_composition.py tests/runtime/test_bridge_decide_next.py tests/runtime/test_bridge_decision_log_flush.py tests/runtime/test_bridge_engine.py tests/runtime/test_bridge_io.py tests/runtime/test_cli_guard_family.py tests/runtime/test_next_board_authority.py tests/runtime/test_run_index_portability_regression.py tests/runtime/test_run_state_hardening.py tests/specify_cli/cli/commands/test_implement_characterization.py tests/specify_cli/cli/commands/test_next_answer_effective_root.py tests/specify_cli/events/test_runtime_moments.py tests/specify_cli/missions/test_handle_equivalence_matrix.py tests/specify_cli/next/test_runtime_bridge_composition.py tests/specify_cli/orchestrator_api/test_answer_decision.py tests/specify_cli/test_documentation_template_resolution.py tests/specify_cli/test_operational_context_wiring.py tests/unit/mission_loader/test_command.py tests/runtime/test_bridge_adapter_characterisation.py tests/architectural/test_no_dead_symbols.py -q -n auto --dist loadfile
**Prompt**: `tasks/WP05-io-seam-and-the-public-re-exports.md`
**Requirement Refs**: FR-001, FR-003, FR-005, FR-006, FR-007, FR-008, FR-010

### Included Subtasks

T018 Delete the 13 delegates; add the two re-exports (WP05)
T019 Remove io back-edges to io names (WP05)
T020 Repoint tests for the 11 private names and `MissionRunRef` (WP05)
T021 Hazard 1: review every patch of a kept re-export by call path (WP05)
T022 Flip the gate row (WP05)

### Dependencies

- Depends on WP04

### Risks & Mitigations

- **Hazard 1 (silent false-green)**: the biggest risk of the mission; T021 is mandatory, not a spot check.
- **Hazard 2 (adapters)**: the characterisation file must stay unchanged and green.
- **`test_no_dead_symbols` pins façade names**: if it lists a deleted private name, update the pin only if the gate's own rules say it should be removed; never weaken the gate.

---

## Work Package WP06: Close-out: docstrings, last xfail, full surface (Priority: P1)

**Goal**: Finish the mission: fix `_check_cli_guards`'s docstring, drop the last xfail, remove remaining
**Independent Test**: .venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py tests/runtime/test_bridge_adapter_characterisation.py -q
**Prompt**: `tasks/WP06-close-out-docstrings-last-xfail-full-surface.md`
**Requirement Refs**: FR-002, FR-004, FR-009, FR-010, NFR-001, NFR-002, NFR-003, NFR-004, NFR-005

### Included Subtasks

T023 `_check_cli_guards` docstring; last xfail (WP06)
T024 Stale compat comments sweep (WP06)
T025 Full targeted verification (WP06)
T026 Final false-green sweep (WP06)

### Dependencies

- Depends on WP05

### Risks & Mitigations

- **A pass-count drop hiding a lost test**: reconcile against the deletion log.
- **Out-of-scope docstring** in `src/specify_cli/mission_loader/command.py` (mentions `runtime_bridge._build_discovery_context`): leave it; it is listed in the spec's Deferred section.
