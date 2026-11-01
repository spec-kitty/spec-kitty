---
work_package_id: WP01
title: Frozen census and its gate checks
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-004
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundational
history:
- at: '2026-11-01T15:20:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/charter_offering_public_surface.yaml
execution_mode: code_change
owned_files:
- tests/architectural/charter_offering_public_surface.yaml
- tests/architectural/test_charter_offering_public_surface.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6285'
---

# Work Package Prompt: WP01 – Frozen census and its gate checks

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave
according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: claude

---

## Objectives & Success Criteria

Commit one machine-readable census of the charter offering public contract surface and pin the
live surface to it inside the gate file that already owns importability, sorting, disposition
coupling and facade routing. Nothing under `src/` changes in this WP.

Done when:

- `tests/architectural/charter_offering_public_surface.yaml` exists, parses, and enumerates the
  12 exported symbols in `charter.offering.api.__all__` order, each with origin, disposition,
  facades, contract kind, today's type, signature (callables), DTO target and `dto_status`.
- `tests/architectural/test_charter_offering_public_surface.py` fails when `__all__` gains,
  drops or reorders a name relative to the census, when a row's origin or facade set is wrong,
  and when a row is not fully DTO-forward annotated.
- Every reached offering path is classified, matches `test_doctrine_census.DISPOSITION`, and the
  recomputed `public_contract_delta` equals the committed (empty) list.
- Planted-mutation self-tests prove each new assertion can fail (architectural-gate non-vacuity).
- The four named gate files pass, and the added checks cost under 2.0 s.

## Context & Constraints

Read, in this order:

1. `kitty-specs/charter-offering-surface-freeze-01M6BTTR/plan.md` — design and check table.
2. `kitty-specs/charter-offering-surface-freeze-01M6BTTR/data-model.md` — census field rules.
3. `kitty-specs/charter-offering-surface-freeze-01M6BTTR/contracts/public-surface-census.md` —
   invariants C-001..C-006.
4. `kitty-specs/charter-offering-surface-freeze-01M6BTTR/quickstart.md` — the red proofs.

Rules that bind this WP:

- **No gate weakening** (C-002): only additive assertions. Do not touch the existing tests in
  `test_charter_offering_public_surface.py`, and do not edit
  `test_charter_facades_reexport_offering.py`,
  `test_charter_activation_api_reexport.py` or
  `test_charter_offering_does_not_import_activation.py` at all.
- **No gate duplication** (NFR-004): the new checks live in the existing public-surface gate.
  Do not create a second gate file that could disagree with it.
- **No Python moves** (C-001): nothing under `src/charter/offering/` is created, moved or
  renamed here.
- **No silent widening** (C-003): the delta list must be empty; if the live scan shows a
  symbol some consumer needs that is absent from the surface, record it in
  `public_contract_delta` and report it to the operator — do not add it to `__all__`.
- The census stays a literal-backed pin: `api.__all__` is not generated from it, and the census
  is not shipped (it lives under `tests/`, never under `src/`).

## Branch Strategy

- **Strategy**: single mission branch; planning base and merge target are both
  `kitty/mission-charter-offering-surface-freeze-01M6BTTR`.
- **Planning base branch**: `kitty/mission-charter-offering-surface-freeze-01M6BTTR`
- **Merge target branch**: `kitty/mission-charter-offering-surface-freeze-01M6BTTR`

> These fields are populated by `spec-kitty agent mission finalize-tasks`. Do not change them
> manually unless the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Author the census-pin checks first (red)

- **Purpose**: Red-first proof for the freeze: nothing currently fails when an export is added
  without a record, so write the assertions before the census exists.
- **Steps**:
  1. In `tests/architectural/test_charter_offering_public_surface.py`, add a module-level
     constant for the census path:
     `_CENSUS_PATH = Path(__file__).with_name("charter_offering_public_surface.yaml")` and a
     small loader `_load_census() -> dict` using `yaml.safe_load` (the test already imports
     `pytest`; `yaml` is a test dependency used by `test_doctrine_census.py`).
  2. Add the five checks described in plan.md's "Checks added" table with these names:
     `test_census_enumerates_exactly_the_live_surface`,
     `test_census_origin_and_disposition_match_the_module`,
     `test_census_facades_match_the_identity_table`,
     `test_every_surface_row_is_dto_forward_annotated`,
     `test_reached_paths_are_classified_and_delta_is_empty`.
  3. Run the file and capture the red output (census missing → `FileNotFoundError`); record the
     command and the failure in the mission tracer before writing the census.
- **Files**: `tests/architectural/test_charter_offering_public_surface.py`

### Subtask T002 – Author the 12 surface rows

- **Purpose**: The frozen list itself.
- **Steps**:
  1. Write `tests/architectural/charter_offering_public_surface.yaml` with the header fields from
     data-model.md (`schema_version`, `surface` label, `mission`, `issue`, `frozen_at`, `c003`).
  2. Add one row per `charter.offering.api.__all__` name **in the same order**. Derive `origin`
     from the `api.py` import statements, `facades` from
     `_FACADE_TABLE` (`tests/architectural/test_charter_facades_reexport_offering.py`) filtered to
     rows whose source module is `charter.offering.api`, and `contract_kind` / `signature` from
     the runtime object:
     - `ArtifactKind` → enum; `AssetManifest` → model (pydantic);
       `AssetNotFoundError`, `AssetPathEscapeError`, `AssetResolutionError` → exception;
       `AssetRepository` → protocol (abstract class); `CatalogLoadResult`,
       `RoutingRecommendation` → dataclass; `LANGUAGE_TOKENS` → constant;
       `evaluate`, `load`, `slug_for` → function.
     - For every callable (functions **and** classes) record the exact `str(inspect.signature(obj))`
       in `signature`; `null` for `LANGUAGE_TOKENS`.
  3. Fill `today_type` with one consumer-readable line and `dto_target` with the ADR-0004
     direction for that symbol (descriptive, not a promised class name). `dto_status` is
     `transitional` on every row.
- **Files**: `tests/architectural/charter_offering_public_surface.yaml`
- **Notes**: get the signature strings from
  `uv run python -c "import inspect, charter.offering.api as a; [print(n, str(inspect.signature(getattr(a, n)))) for n in a.__all__ if callable(getattr(a, n))]"`
  rather than guessing. Do not include the constant's value in the census; the surface freezes
  names and declared types, not the token vocabulary.

### Subtask T003 – Reached-path classification and delta

- **Purpose**: The whole-picture view the issue asks for, derived from the authoritative manifest
  rather than restated.
- **Steps**:
  1. Add a `reached_classification` section: one row per reached offering path from
     `tests.architectural.test_doctrine_census.reached_offering_paths()` (union of the path sets),
     with `disposition` from `DISPOSITION` (longest-prefix), `on_surface` true iff the path is a
     surface `origin`, sorted `consumers` (the files that reach it), and a `route` for
     non-surface rows (`facade: charter.<name>` / `service` / `ratchet-allowlist` / `metadata`).
  2. Add `public_contract_delta: []` with a comment stating the rule: reached ∧ not on surface ∧
     disposition not in the sanctioned non-public set (`FACADE-ONLY`, `TICKETED-BASELINE`,
     `CONSTRUCTION-ROUTED`, `INTERNAL-METADATA`) is a delta.
  3. Measured on the base commit the reached set is 10 paths over 6 files (see
     `research.md` D-003); re-measure rather than trusting that list, and explain any difference
     in the WP history note.
- **Files**: `tests/architectural/charter_offering_public_surface.yaml`
- **Notes**: the gate must recompute `consumers` from the live scan and compare, so a new
  reaching file is a census change, not a silent drift.

### Subtask T004 – Facade match without a second source of truth

- **Purpose**: Prove the facades against the canonical list using the identity table the facade
  gate already parameterises over.
- **Steps**:
  1. In `test_census_facades_match_the_identity_table`, import
     `_FACADE_TABLE` from `tests.architectural.test_charter_facades_reexport_offering` and build
     `{symbol: {facade, ...}}` for rows whose source module is exactly `charter.offering.api`.
  2. Assert `_FACADE_TABLE` is non-empty and that at least one row maps to `charter.offering.api`
     before comparing — fail with a clear message if the table's shape changed, so the check can
     never compare against an empty set and pass vacuously.
  3. Assert each census row's `facades` equals the computed set, and that the union of all
     facade sets equals the 12 names (the coverage the strict T007 assertion already enforces).
- **Files**: `tests/architectural/test_charter_offering_public_surface.py`
- **Notes**: importing the private table is deliberate — a copy of the mapping is exactly the
  second source of truth this WP exists to prevent. Add a comment saying so.

### Subtask T005 – Planted-mutation self-tests

- **Purpose**: Prove each new assertion can fail (architectural-gate non-vacuity; do not rely on
  the happy path).
- **Steps**: add one test, `test_census_checks_reject_planted_mutations`, that starts from the
  committed census (`copy.deepcopy`), applies each mutation in turn, runs the same helper the
  real check uses, and asserts the helper reports a problem:
  1. drop a surface row → name-set mismatch names the missing symbol;
  2. append a `name: NotExported` row → names the extra symbol;
  3. change one row's `origin` to `charter.offering.nope` → disposition/origin mismatch;
  4. remove a facade from a row that has one → facade-set mismatch;
  5. set one row's `dto_status` to `final` → annotation check fails;
  6. append an unknown path to `reached_classification` with `on_surface: false` and disposition
     `PUBLIC` → delta check reports it.
  Structure the checks as pure helpers taking `(census: dict) -> list[str]` (problem messages) so
  the real tests and the mutation test share one implementation.
- **Files**: `tests/architectural/test_charter_offering_public_surface.py`
- **Notes**: no `pytest.skip`, no `xfail`, no try/except that swallows a failure (C-002).

### Subtask T006 – Green run and timing

- **Purpose**: Evidence for the PR.
- **Steps**:
  1. Run and record output for:
     ```bash
     uv run pytest -q tests/architectural/test_charter_offering_public_surface.py \
       tests/architectural/test_charter_facades_reexport_offering.py \
       tests/architectural/test_charter_activation_api_reexport.py \
       tests/architectural/test_charter_offering_does_not_import_activation.py
     uv run ruff check tests/architectural/test_charter_offering_public_surface.py
     ```
  2. Measure the added cost with `time uv run pytest tests/architectural/test_charter_offering_public_surface.py`
     before/after the change and record both numbers (NFR-001: < 8.0 s added). Cache the reached-path
     scan once per process (`functools.cache`); the scan — not the census parsing — is the added cost,
     and a second, faster scanner would be a forbidden second source of truth.
- **Files**: none (evidence only)

## Test Strategy

- Red proof first: the five checks must be observed failing with the census absent.
- The mutation self-test is the non-vacuity control; it must cover all six mutation classes.
- The existing assertions in the gate file stay untouched and green.

## Risks & Mitigations

- `_FACADE_TABLE` shape change → the check fails loudly instead of comparing to an empty set.
- `inspect.signature()` rendering churn → accepted: the freeze exists to make such changes
  deliberate. Keep signatures in the census, not in Python code.
- The live reached set may differ from `research.md` → re-measure and record the difference
  rather than copying stale numbers.

## Review Guidance

- Confirm no existing assertion in the gate file changed, and no other gate file was edited.
- Confirm the census cannot be bypassed: check that both directions (extra and missing) fail.
- Confirm the delta logic treats `FACADE-ONLY`, `TICKETED-BASELINE`, `CONSTRUCTION-ROUTED` and
  `INTERNAL-METADATA` as sanctioned non-public routes, and that a `PUBLIC` reached path that is
  not on the surface is reported as a delta.
- Confirm the census contains no `src/` path and nothing was added to `__all__`.

## Progress & Status

Record each subtask with `spec-kitty agent tasks mark-status T001 --status done` (and so on),
and append approach notes with
`spec-kitty agent tracer-append --mission charter-offering-surface-freeze-01M6BTTR --category approach --entry "..."`.
