# Architectural Test Suite — 5-Axis Model

The architectural tests in this directory enforce a **5-axis model** of the
spec-kitty architecture. Reading the gates collectively gives a faithful
one-page architecture description:

> *spec-kitty is a strictly layered system (kernel ← doctrine ← charter ← specify_cli)
> with mediated boundaries (charter mediates doctrine access; auth.transport
> mediates HTTP; emitter-adapter mediates cross-cutting events). Surfaces
> declared as facades or schemas must match implementation reality (parity).
> Operator-authored vocabularies are closed and SSOT-pinned. Every shipped
> module has a runtime caller; every released version has a migration path.
> Dependency manifests are exact and exclude retired packages. Process
> artifacts (markers, safety, compat shims) follow uniform conventions.*

## The 5 Axes

| Axis | What it enforces | Representative gates |
|---|---|---|
| **1. Layer direction** | `kernel ← doctrine ← charter ← specify_cli`; no upward imports | `test_layer_rules.py`, `test_runtime_charter_doctrine_boundary.py` |
| **2. Surface completeness** | Schemas/facades match implementation reality; declared surfaces are exhaustive | `test_artifact_selection_completeness.py`, `test_activation_registry_schema.py`, `test_all_declarations_required.py`, `test_charter_facades_reexport_doctrine.py` |
| **3. Closed-vocabulary integrity** | Operator-authored vocabularies are closed and SSOT-pinned; no dead symbols in public APIs | `test_no_dead_symbols.py`, `test_template_governance_payload_contract.py`, `test_trigger_registry_coverage.py` |
| **4. Lifecycle presence** | Every shipped module has a runtime caller; every release has a migration; no dead modules | `test_no_dead_modules.py`, `test_migration_chain_integrity.py` |
| **5. Dependency hygiene** | Manifests are exact; cross-cutting boundaries mediated; no retired packages; lock drift prevented | `test_auth_transport_singleton.py`, `test_compat_shims.py`, `test_shared_package_boundary.py`, `test_pyproject_shape.py`, `test_uv_lock_pin_drift.py`, `test_no_runtime_pypi_dep.py`, `test_events_tracker_public_imports.py` |

## Gate Index

Gates are ordered alphabetically within each axis group.

### Axis 1 — Layer Direction

- **`test_layer_rules.py`** — Enforces import direction: `kernel` must not import from `doctrine`, `doctrine` must not import from `charter`, `charter` must not import from `specify_cli`. Any upward import fails this gate.
- **`test_runtime_charter_doctrine_boundary.py`** — Verifies the internal runtime (`runtime.next._internal_runtime`) accesses doctrine only through the charter facade, never by direct imports from `src/charter/offering/`.

### Axis 2 — Surface Completeness

- **`test_activation_registry_schema.py`** — Confirms the activation registry JSON schema matches every key used in the shipped registry and org-pack extension points.
- **`test_all_declarations_required.py`** — Confirms every artifact declared in doctrine packs has a matching implementation file. No orphaned declarations.
- **`test_artifact_selection_completeness.py`** — Confirms every artifact selection the charter surface offers resolves to a real doctrine artifact. No catalog misses in the shipped selection surface.
- **`test_charter_facades_reexport_doctrine.py`** — Confirms `charter.*` public surfaces re-export every symbol they claim. No facade drift.
- **`test_retrospective_events_boundary.py`** — Confirms retrospective event emission is mediated; no direct event writes from the retrospective runtime.
- **`test_safety_registry_completeness.py`** — Confirms the safety registry lists every file with a declared safety exemption; no undeclared exemptions.
- **`test_shim_registry_schema.py`** — Confirms the shim registry YAML schema matches every shim record used at runtime.
- **`test_template_governance_payload_contract.py`** — Confirms `charter context --json` payload matches the declared governance payload schema (no extra or missing keys).

### Axis 3 — Closed-Vocabulary Integrity

- **`test_no_dead_symbols.py`** — Walks every `src/**/*.py` module, over the union of `__all__` and public module-level names (#470); asserts every exported name has at least one external caller (or an auto-exemption). Exemptions are declared by `(module, name)` in `dead_symbol_allowlist.yaml`, enforced by the schema-validating loader (`tests/architectural/_dead_symbol_allowlist.py`). Dead symbols outside both the allowlist and auto-exemptions fail this gate.
- **`test_no_prompt_filtering_added.py`** — Asserts no new prompt-filtering logic has been added outside the declared filter registry; guards the closed-vocabulary contract for prompt behavior.
- **`test_trigger_registry_coverage.py`** — Confirms every trigger key used in workflow sequences is registered in the trigger registry.

### Axis 4 — Lifecycle Presence

- **`test_migration_chain_integrity.py`** — Confirms the migration chain is contiguous (no version gaps), ordered, and that every migration file is referenced from the chain manifest. Forward-staged migrations (see `src/specify_cli/upgrade/migrations/README.md`) are permitted: the chain target may lead `pyproject.toml`'s version.
- **`test_no_dead_modules.py`** — Confirms every Python module under `src/` has at least one live caller. Dead modules (no importers) fail, except entries explicitly listed in `_CATEGORY_7_GRANDFATHERED` (Cat-7 deferral list).

### Axis 5 — Dependency Hygiene

- **`test_auth_transport_singleton.py`** — Confirms `auth.transport.AuthTransport` is used only from files in `_ALLOWED_DIRECT_HTTPX_FILES`. Guards the HTTP mediation boundary. **Note:** as of Slice F (2026-05-18), this module has zero live callers; see ADR 2026-05-18-2 and `docs/adr/3.x/2026-05-18-2-delete-specify-cli-auth-transport.md`.
- **`test_compat_shims.py`** — Confirms every compat shim under `src/specify_cli/` is registered, follows the naming convention, and has a target removal version declared.
- **`test_events_tracker_public_imports.py`** — Confirms `spec-kitty-events` and `spec-kitty-tracker` are consumed only via their public `spec_kitty_events.*` / `spec_kitty_tracker.*` import surfaces. No private-module access.
- **`test_no_runtime_pypi_dep.py`** — Confirms the CLI does not depend on `spec-kitty-runtime` at runtime. The standalone runtime package is retired.
- **`test_pyproject_shape.py`** — Confirms shared-package dependencies and `uv.lock` use exact public git-SHA references and reject path/editable/branch overrides.
- **`test_shared_package_boundary.py`** — Confirms `spec_kitty_events` and `spec_kitty_tracker` are not vendored into `src/specify_cli/`. Boundary enforcement for external contract packages.
- **`test_unregistered_shim_scanner.py`** — Scans for shim-shaped files not registered in the shim registry. Catches unregistered shims that bypass the compat audit.
- **`test_uv_lock_pin_drift.py`** — Detects drift between `pyproject.toml` declared ranges and the `uv.lock` pinned versions; fails if any pinned package falls outside the declared range.

### Process / Convention Gates

These gates enforce cross-cutting conventions not directly tied to a single axis:

- **`test_pytest_marker_convention.py`** — Confirms every test file uses only registered pytest markers (defined in `pytest.ini`). Prevents marker typos from silently excluding tests from CI runs.
- **`test_pytest_marker_correctness.py`** — Confirms marker usage matches the declared scope (e.g. `integration` marker only on integration tests).
- **`test_wp_prompt_build_latency.py`** — Performance gate: `spec-kitty charter context` prompt build must complete within 1.2× the Mission B baseline latency. Non-functional regression guard (NFR-002).
- **`test_ratchet_baselines.py`** — Meta-gate: reads `_baselines.yaml` and confirms every per-category failure count matches the recorded baseline (ratchet enforcement). See "Burn-down policy" below.

## Ratchet Baselines (`_baselines.yaml`)

`_baselines.yaml` records the canonical per-test, per-category failure counts.
A ratchet baseline only moves in the **decreasing** direction during normal
development; any increase fails CI (`test_ratchet_baselines.py`). Shrinkage
produces an informational warning but is non-fatal.

Run `tests/architectural/test_ratchet_baselines.py` by name to inspect the
current state without running the full architectural suite.

## Burn-down Policy

Per charter §"Burn-down policy" (binding per HiC §5a.2 / C-004):

- Every mutable architectural allowlist is governed by a baseline in
  `_baselines.yaml`. Growth above baseline **FAILS CI**; shrinkage WARNS
  (informational, non-fatal).
- `test_no_dead_modules._CATEGORY_7_GRANDFATHERED` (Cat-7) shrinks by ≥2
  entries per major release; **target 0 by 4.0**.
- Pure-shim files (`test_compat_shims._ADAPTER_FILES`) target 0 by 4.0.

See `_baselines.yaml` for the canonical per-test, per-category baselines.
See `test_ratchet_baselines.py` for the meta-test enforcing burn-down.

## Fixtures

`_fixtures/` contains shared test fixtures (org packs, example charters, DRG
fragments) used by tests in this directory and in `tests/integration/`. Do not
modify fixtures without updating the tests that depend on them.
