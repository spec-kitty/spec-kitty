# Work Packages: Promote org-pack interview selections on upgrade

**Inputs**: Design documents from `kitty-specs/org-pack-selection-promotion-01M67HVC/`
**Prerequisites**: plan.md, spec.md, research.md

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).

**Prompt Files**: `kitty-specs/org-pack-selection-promotion-01M67HVC/tasks/WP0x-*.md`

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows, not checkboxes. Record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`

---

## Work Package WP01: The shared selection resolver (Priority: P1)

**Goal**: One layer-aware selection resolver exists in `charter.activation`, exported on the
public seam, with unit tests pinning layer lookup, dedupe, unknown ids and ambiguity.
**Independent Test**: `uv run pytest tests/charter/activation/test_selection_resolver.py tests/architectural/test_charter_activation_api_reexport.py -q` passes, and a resolver built on an org-pack project resolves the pack's declared id to its stem.
**Prompt**: `kitty-specs/org-pack-selection-promotion-01M67HVC/tasks/WP01-shared-selection-resolver.md`
**Requirement Refs**: FR-003, NFR-001, C-003

### Included Subtasks

T001 Create `src/charter/activation/selection.py` with `SelectionResolver`, `SelectionResolution`, `UnresolvedSelection` and `__all__`
T002 Export the resolver from `src/charter/activation/api.py`
T003 Write resolver unit tests in `tests/charter/activation/test_selection_resolver.py` (org layer, project layer, dedupe, unknown id, ambiguity both policies, one index build per run)
T004 Add the seam row to `tests/architectural/test_charter_activation_api_reexport.py`

### Dependencies

- None (starting package).

### Risks & Mitigations

- The resolver must not become a second precedence authority: it delegates to `IdentityIndex.build`.
- `tests/architectural/test_no_dead_modules.py` fails an unreachable module — the seam export and both call sites keep it reachable.

---

## Work Package WP02: The upgrade promotion resolves across layers (Priority: P1)

**Goal**: `4.0.0rc8_promote_interview_selections` resolves a selection through the shared
resolver, so an org-pack or project-pack selection is promoted instead of reported unresolved.
**Independent Test**: On an org-pack fixture, the migration appends the org directive's stem to a present `activated_directives` list, and the same fixture's unknown id is still reported in one run.
**Prompt**: `kitty-specs/org-pack-selection-promotion-01M67HVC/tasks/WP02-upgrade-promotion-across-layers.md`
**Requirement Refs**: FR-001, FR-002, FR-004, FR-005, FR-006, C-001, C-002

### Included Subtasks

T005 Write the failing org-pack promotion test through the migration entry point and record the red run
T006 Write the project-pack promotion test and the same-fixture unknown-id control
T007 Replace `_StemResolver`/`_resolve_selections` with the shared resolver in the migration
T008 Update the unrepresentable-directive test to the resolver's ambiguity report and confirm the whole module is green

### Dependencies

- WP01 (the resolver it consumes).

### Risks & Mitigations

- Built-in-only behaviour must not change: the module's existing tests stay green without expectation edits except the ambiguity test that moves to the new report path.
- The doctrine-root failure path must survive the resolver construction.

---

## Work Package WP03: The interview resolves through the same resolver, and the ratchets follow (Priority: P2)

**Goal**: `charter interview` uses the shared resolver instead of its own loop, a CLI test proves
both writers store the same stem, the boundary ratchet loses the two drained rows, and the
user-facing changelog/docs record the fix.
**Independent Test**: `uv run pytest tests/specify_cli/cli/commands/test_charter_interview_promotion.py tests/architectural/test_runtime_charter_activation_boundary.py -q` passes, and the changelog entry names #6686.
**Prompt**: `kitty-specs/org-pack-selection-promotion-01M67HVC/tasks/WP03-interview-parity-and-ratchets.md`
**Requirement Refs**: FR-003, NFR-002, NFR-003, SC-002

### Included Subtasks

T009 Add the CLI parity test: an org-pack selection recorded by `charter interview` stores the same stem the migration promotes
T010 Rewire `_promote_interview_selections` (and `_stem_spelled_config`) onto the shared resolver; drop the local loop and the `catalog`/`layer_roots` imports
T011 Remove the two drained rows from `tests/architectural/charter_activation_boundary_baseline.yaml` and lower `boundary_baseline` in `tests/architectural/_baselines.yaml`
T012 Add the `[Unreleased]` changelog entry and update the charter/activation docs the change touches

### Dependencies

- WP01 (the resolver it consumes).

### Risks & Mitigations

- The collision refusal must stay a refusal: `refuse_ambiguous=True` and the existing CLI collision test unchanged.
- Docs freshness gate: only regenerate the surface the diff touches and verify with `check_docs_freshness --ci`.

---

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Create the selection resolver module | WP01 | |
| T002 | Export it from `charter.activation.api` | WP01 | |
| T003 | Resolver unit tests | WP01 | |
| T004 | Seam identity-gate row | WP01 | |
| T005 | Red org-pack promotion test | WP02 | |
| T006 | Project-pack test + unknown-id control | WP02 | |
| T007 | Rewire the migration onto the resolver | WP02 | |
| T008 | Move the ambiguity test to the shared report | WP02 | |
| T009 | Interview/migration CLI parity test | WP03 | |
| T010 | Rewire the interview onto the resolver | WP03 | |
| T011 | Drain the boundary baseline rows | WP03 | [P] |
| T012 | Changelog and docs | WP03 | [P] |
