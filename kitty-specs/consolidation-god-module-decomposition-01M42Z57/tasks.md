# Work Packages: Consolidation god-module decomposition

**Inputs**: `kitty-specs/consolidation-god-module-decomposition-01M42Z57/` — spec.md, plan.md, research.md, research/code-grounding.md, data-model.md, occurrence_map.yaml
**Topology**: `single_branch` — WPs run sequentially in the repository root checkout on `issue-2026-consolidation-decomposition`.

Every WP is a behaviour-preserving move (C-001, C-005): move code first, then adjust callers, with no logic edit while moving. Each WP opens with a failing-first structural test (charter ATDD-first) and ends green on its targeted suites.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; completion is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: mission_number bake cluster leaves ordering.py (Priority: P2)

**Goal**: #2600 — `ordering.py` keeps only merge ordering; the bake cluster lives in `consolidation/mission_number/bake.py`; the stdlib-only predicate becomes `consolidation/mission_number/__init__.py` unchanged.
**Independent Test**: `ordering.py` defines only `MergeOrderError`, `has_dependency_info`, `get_merge_order`; `specify_cli.consolidation.mission_number` imports only the standard library; bake seam tests and the ordering-keyed gates pass against the new module.
**Prompt**: `tasks/WP01-mission-number-bake-cluster.md`
**Requirement Refs**: FR-003, FR-006, FR-007, NFR-001, NFR-003, C-001, C-005, SC-004

### Included Subtasks

T001 Failing-first structural test: ordering holds only merge ordering; mission_number leaf stays stdlib-only; bake module owns the cluster (WP01)
T002 Convert `mission_number.py` into the package (`git mv` to `mission_number/__init__.py`, content unchanged) (WP01)
T003 Move the bake cluster verbatim from `ordering.py` into `mission_number/bake.py`; prune imports (WP01)
T004 Re-point callers: `consolidation/__init__.py`, `forecast.py`, `executor.py`, `cli/commands/consolidate.py` (WP01)
T005 Re-point tests: `test_ordering_bake_seam.py` (incl. its lazy-import AST guard), `test_merge_compat_surface.py`, other importers/patchers of `ordering.<bake name>` (WP01)
T006 Re-point ordering-keyed gates and ledgers (`_load_meta_census.py`, `test_destructive_op_routing.py`, `untrusted_path_audit/inventory.md`, `dead_symbol_allowlist.yaml`, `test_mission_resolver_walker_gate.py`, `test_commit_recipes.py`, `test_meta_fail_closed_full_census_contract.py`, `test_exemption_registry_ratchet.py`, `test_layer_rules.py`, mypy quarantine in `pyproject.toml`) (WP01)
T007 Targeted tests, ruff, format, mypy; tracer entries (WP01)

### Dependencies

- None.

### Risks & Mitigations

- mypy: code leaving the `ordering` quarantine may surface type errors → re-point the quarantine entry to the bake module rather than editing moved logic (behaviour-preserving), and record it.

---

## Work Package WP02: ConsolidateOptions parameter object (Priority: P1)

**Goal**: #3457 — direct callers of the `consolidate` command build one `ConsolidateOptions` with real defaults instead of enumerating 19 keywords; the Typer CLI surface is unchanged.
**Independent Test**: `ConsolidateOptions()` carries no `typer.models.OptionInfo`; the Typer command's parameters are unchanged; the 8 direct-call sites use `run_consolidate(ConsolidateOptions(...))`.
**Prompt**: `tasks/WP02-consolidate-parameter-object.md`
**Requirement Refs**: FR-004, FR-005, C-001, C-006, NFR-003, SC-005

### Included Subtasks

T008 Failing-first test: `ConsolidateOptions` defaults are real values (no `OptionInfo`), its fields mirror the Typer command's parameters (WP02)
T009 Introduce `ConsolidateOptions` + `run_consolidate(options)` holding the command body verbatim; the Typer `consolidate()` builds the object (WP02)
T010 Re-point the 8 direct-call sites (`test_merge_preflight_mission_branch.py` x7, `test_executor_coverage.py` x1) (WP02)
T011 Targeted tests (`tests/consolidation`, `tests/specify_cli/cli/commands/test_merge*`, `test_wrapper_delegation.py`, `test_merge_cli_golden.py`), ruff, format, mypy (WP02)

### Dependencies

- None (independent of WP01; sequential under single_branch).

### Risks & Mitigations

- `inspect.signature` consumers (`test_wrapper_delegation.py`, `test_merge_cli_golden.py`) read the Typer function → its signature stays identical.

---

## Work Package WP03: Split executor.py along phase boundaries (Priority: P1)

**Goal**: #2026 slice 1 — `executor.py` keeps the locked driver (inline rollback door), `_report_rollback`, attestation recording and the locked entry; everything else moves verbatim into ten phase modules; every test patch keeps its interception set; every gate is re-pointed or widened, never loosened.
**Independent Test**: targeted suites match the `origin/main` baseline; `test_single_rollback_authority.py` and the phase-order pins pass unchanged in meaning; moved bodies are byte-identical (source comparison).
**Prompt**: `tasks/WP03-executor-phase-split.md`
**Requirement Refs**: FR-001, FR-002, FR-006, FR-007, NFR-001, NFR-002, NFR-003, NFR-004, C-001, C-003, C-004, C-005, SC-001, SC-002, SC-003

### Included Subtasks

T012 Failing-first gate tightening: the no-revert-argv scan covers every executor-family module (WP03)
T013 Verbatim split into `run_state`, `coord_strand`, `phase_claim`, `phase_advance`, `phase_bookkeeping`, `phase_gate`, `phase_teardown`, `phase_finalize`, `entry_preflight`, `resume_recovery` (AST splitter; ruff-pruned imports; module docstrings) (WP03)
T014 Byte-identity check of every moved top-level definition against `origin/main` (WP03)
T015 Re-point test imports and attribute reads to the defining module (WP03)
T016 Re-point monkeypatch targets to every module that loads the name (AST interception audit) (WP03)
T017 Re-point path/qualname-keyed gates (`test_destructive_op_routing.py`, `test_no_write_side_rederivation.py`, `test_status_events_writes_gate.py`, `_GATE_ARTIFACT_FILENAMES.md`) (WP03)
T018 Widen fixed-scope gates to the receiving modules (`_STATUS_BEARING_MODULES`, `CHURN_SURFACE_MODULES`, `_WRITE_DIR_CONSUMER_MODULES`, `_WP09_OWNED_FILES`, `_SEAM_IMPORT_TARGETS`, `_MERGE_CLI_CONSOLE_IMPORTERS`) (WP03)
T019 Update the module maps (`executor.py` docstring, `cli/commands/consolidate.py` header comment) (WP03)
T020 Targeted suites (`tests/consolidation`, `tests/specify_cli/consolidation`, `tests/terminus`, `tests/lanes`, `tests/orchestrator_api`, `make test-fast`, named gate files), ruff, format, mypy, C901; tracer entries (WP03)

### Dependencies

- Depends on WP01 (executor imports the bake cluster from its new home).
- Depends on WP02 (shares `test_executor_coverage.py`).

### Risks & Mitigations

- Silent patch non-interception → AST audit (T016) is mandatory, not best-effort.
- Textual conflict with PR #5633 → documented mapping in code-grounding §5.
