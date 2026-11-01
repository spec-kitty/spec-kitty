# Work Packages: charter resynthesize project-directive layer split (#6768)

**Inputs**: Design documents from `kitty-specs/charter-resynth-project-directive-layer-split-01M690W8/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md (grounding + decisions), data-model.md (the two layers)

**Tests**: Required. This is a P0 defect: the failing regression is authored and observed red
before the fix lands (charter, ATDD-First Discipline; DIRECTIVE_034), through the real
`charter activate` → `charter resynthesize` entry points.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Three
packages: the red-first proof, the fix, and the user-facing documentation.

**Prompt Files**: `kitty-specs/charter-resynth-project-directive-layer-split-01M690W8/tasks/WPxx-*.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/charter/`, `src/specify_cli/`, `tests/`, `docs/`.

---

## Work Package WP01: Red-first regression and the additive-only positive control (Priority: P1)

**Goal**: Pin the reported refusal as an executable regression through the real CLI, and pin
the other half of the fix — that the reference universe still resolves project references and
that a genuine built-in URN still refuses — so neither can regress silently.
**Independent Test**: `uv run pytest tests/charter/synthesizer/test_project_directive_layer_split_6768.py -q`
fails on the un-fixed tree on the resynthesize, named-layer and fallback cases, and passes once
WP02 lands; the positive-control and reference cases pass before and after.
**Prompt**: `tasks/WP01-red-first-regression.md`
**Requirement Refs**: FR-001, FR-002, FR-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Author the module skeleton with a module-scoped "synthesized once" fixture (the shape of `test_resynthesis_after_activation_6510.py::_build_template`) plus an authored `PROJECT_007` directive registered through the real `charter activate`
T002 Add `test_resynthesize_activated_project_authored_directive_succeeds`: the reported refusal, red before the fix
T003 Add `test_built_in_urn_still_refuses_and_project_urn_does_not`: the FR-020 / EC-6 positive control on the real shipped DRG, paired on one fixture
T004 Add the named-layer assertions: `_build_synthesis_request` yields a built-in layer without `directive:PROJECT_007` and a reference universe that still holds it
T005 Add the fallback cases: `built_in_snapshot()` with `None`, and `_build_synthesis_request` when `load_built_in_graph` raises `DRGLoadError`
T006 Add the reference-universe pair: the companion tactic's `directive:PROJECT_007` reference resolves, and an undeclared `directive:PROJECT_999` still fails closed at `build_targets`
T007 Record the red run (command and the exact refusal lines) in the WP history and the mission tracer files

### Implementation Notes

- The fixture must reach the defect state the issue reports: a project directive that is
  *activated* but **not** synthesis-owned. `charter activate directive <stem>` is exactly that
  path (`adapter_id: project-direct-write`).
- Keep the positive control on the same fixture as the passing case (tactic
  `acceptance-criteria-non-vacuity`).
- Do not use a `PROJECT_` prefix assertion anywhere (C-001).

---

## Work Package WP02: Split the layers at the request builder (Priority: P1)

**Goal**: Make the built-in layer an explicit, authored input built from the shipped DRG, and
keep `drg_snapshot` as the reference universe, so the additive-only check can never see a
project directive as built-in.
**Independent Test**: WP01's module goes green with no change to its assertions; the existing
`tests/charter/synthesizer` and `tests/charter` suites stay green.
**Prompt**: `tasks/WP02-layer-split.md`
**Requirement Refs**: FR-001, FR-003, FR-004, FR-005, SC-001, SC-004

### Included Subtasks

T001 Add `SynthesisRequest.built_in_drg_snapshot` (optional, last field) and the `built_in_snapshot(request)` helper in `src/charter/activation/synthesizer/request.py`, excluded from `normalize_request_for_hash`
T002 Author the built-in layer in `_build_synthesis_request` from `load_built_in_graph()`, with the `DRGLoadError` fallback
T003 Split the additive-only and reference inputs at the dry-run validation callback and the reconciliation preview in `src/specify_cli/cli/commands/charter/_synthesis.py`
T004 Split them in `orchestrator.synthesize` and `resynthesize_pipeline` (additive check vs validation gate)
T005 Propagate the field through the derived requests in `synthesize_pipeline` (per-target) and `resynthesize_pipeline` (bounded)
T006 [P] Update the `_built_in_drg_from_snapshot` / `_built_in_drg_from_request` docstrings so the single fallback rule is stated once
T007 Record the design decision and any friction in the mission tracer files

### Implementation Notes

- Read the new field through the helper in every consumer; never re-derive a layer from
  `config_roots.directives` (FR-004).
- Do not touch `emit_project_layer`'s invariant, message or exception (C-003).
- Follow `docs/adr/4.x` guidance for the frozen `SynthesisRequest` envelope if a field
  addition needs an ADR note; document the decision in `traces/design-decisions.md` either way.

---

## Work Package WP03: Changelog and charter command reference (Priority: P2)

**Goal**: Tell the operator that a project can amend its own project directives again, and
record the behaviour in the charter command reference.
**Independent Test**: the `[Unreleased]` entry renders with the `(#6768)` reference and the
docs freshness check reports `errors=0`.
**Prompt**: `tasks/WP03-changelog-and-docs.md`
**Requirement Refs**: SC-004

### Included Subtasks

T001 Add the impact-first `[Unreleased] → Fixed` entry with before/after under 1,200 characters
T002 Add the one-sentence behaviour note to the `charter resynthesize` section of `docs/api/charter-commands.md`
T003 Run `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`) and `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`
