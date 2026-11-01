---
title: 'ADR: CORE / INTEGRATION Boundary Model'
description: 'Enforces a one-directional CORE-to-INTEGRATION import rule in place using adapter registries and an AST gate, before any physical extraction to `src/orchestrator/`.'
status: Accepted
date: '2026-06-26'
doc_status: active
kind: ADR
updated: '2026-06-26T00:00:00Z'
---

# CORE / INTEGRATION Boundary Model

**Filename:** `2026-06-26-2-core-integration-boundary.md`

**Status:** Accepted

**Date:** 2026-06-26

**Deciders:** Jeroen Nouws (owner), Spec Kitty planning system (recommendation)

**Technical Story:**
- Mission `integration-boundary-01KW0PBE` — fix and enforce the CORE/INTEGRATION boundary
- ADR `docs/adr/3.x/2026-05-11-1-defer-391-structural-extraction-from-3-2-x.md` — context for deferred physical extraction
- Historical ownership context: [ownership map](../../architecture/05_ownership_map.md) (narrative only; current enforced sources are listed under More Information).

---

## Context and Problem Statement

`src/specify_cli/` contains two conceptually distinct layers: a **CORE** layer that
implements the canonical mission lifecycle and governance logic, and an **INTEGRATION**
layer that connects spec-kitty to external systems (SaaS, issue trackers, orchestrator).

Before this mission, three import leaks allowed CORE modules to depend directly on
INTEGRATION modules, violating the intended separation. These violations:

1. Made the governance engine dependent on external-connector availability and startup
   ordering.
2. Made isolated testing of CORE logic harder (import side effects from INTEGRATION).
3. Prevented future physical extraction of INTEGRATION to `src/orchestrator/`.

This ADR records the boundary model, the one-directional rule, all allowlist exemptions,
and deferred scope items so that contributors can understand the model without reading the
enforcement test.

## Decision Drivers

- CORE governance logic (state machine, mission creation, readiness, invocation lifecycle)
  must remain fast and independently testable without importing outbound connectors.
- INTEGRATION modules (sync, tracker, SaaS, orchestrator client) can legitimately read
  CORE state; the reverse dependency is an architectural inversion.
- The observer/adapter registry pattern (already in use for `status/adapters.py`) is the
  proven mechanism for decoupling CORE events from INTEGRATION consumers.
- Physical extraction to `src/orchestrator/` is a planned future step; the boundary must
  be enforced in-place first so that extraction can proceed safely.

## Considered Options

- **(A) Enforce in-place boundary** — add adapter registries in CORE; move INTEGRATION
  logic into INTEGRATION-owned consumers; enforce with an AST-based test.
- **(B) Defer until physical extraction** — allow the leaks to remain until
  `src/orchestrator/` is ready.
- **(C) Silently allowlist all three leaks** — add three blanket exemptions to the test.

## Decision Outcome

**Chosen option: (A) Enforce in-place boundary**, because CORE governance logic must be
independently testable and the adapter-registry pattern is already proven in the codebase.
Options (B) and (C) preserve structural coupling that makes the governance engine brittle.

---

## Set Definitions

### CORE Set

Modules that implement the canonical mission lifecycle and governance logic.
These modules **MUST NOT** import from the INTEGRATION set.

| Package | Root path | Description |
|---------|-----------|-------------|
| `core` | `src/specify_cli/core/` | Mission creation, contract gate, dependency graph |
| `status` | `src/specify_cli/status/` | State machine, event log, adapter registry |
| `readiness` | `src/specify_cli/readiness/` | Readiness checks and coordinator |
| `invocation` | `src/specify_cli/invocation/` | Op lifecycle propagation and registry |

### INTEGRATION Set

Modules that connect spec-kitty to external systems.
These modules **MAY** import CORE facades (allowed direction).

| Package | Root path | Description |
|---------|-----------|-------------|
| `orchestrator_api` | `src/specify_cli/orchestrator_api/` | Orchestrator HTTP client |
| `sync` | `src/specify_cli/sync/` | Real-time SaaS sync, WebSocket, OfflineQueue |
| `tracker` | `src/specify_cli/tracker/` | Issue-tracker origin binding |
| `saas` | `src/specify_cli/saas/` | SaaS-specific feature flags and rollout |
| `saas_client` | `src/specify_cli/saas_client/` | SaaS REST client |

### Out-of-Scope Modules (C-004)

The following modules are **not classified** in either set for this mission.
Their import patterns are **not checked** by `test_integration_boundary.py`.

| Package | Root path | Reason for exclusion |
|---------|-----------|----------------------|
| `coordination` | `src/specify_cli/coordination/` | Deferred (C-004) |
| `lanes` | `src/specify_cli/lanes/` | Deferred (C-004) |
| `runtime` | `src/specify_cli/runtime/` and `src/runtime/` | Deferred (C-004) |

---

## The One-Directional Rule and Its Rationale

```
CORE must NOT import INTEGRATION.
INTEGRATION may import CORE facades.
```

**Rationale:** CORE modules implement the canonical mission lifecycle and governance
logic; coupling them to outbound adapters would make the governance engine depend on the
availability and startup ordering of external connectors. Inversion (CORE fires events;
INTEGRATION registers handlers) keeps the governance path fast, testable, and independent
of connectivity.

The adapter/observer registry pattern is the sanctioned mechanism for this inversion:

- Core → Sync/Tracker/SaaS fan-out: register an observer with `status/adapters.py` or
  `core/adapters.py`; call the fire function.
- Invocation → Sync: register via `invocation/adapters.py`.

---

## Enforcement

`tests/architectural/test_integration_boundary.py` enforces this rule on every CI run.
The test:

1. Uses stdlib `ast.walk` to scan **all** import forms — module-level,
   `if TYPE_CHECKING:` blocks, and lazy function-body imports.
2. Scans every `.py` file in all four CORE-set directories by consuming the
   session-scoped `src_source_tree` fixture (`tests/architectural/conftest.py`) —
   the shared, read-once/parse-once source cache the other boundary gates use —
   filtered to the CORE set, rather than independently re-walking `src/`.
3. Fails with a message identifying: the violating source file, the offending import
   path, and the corrective action (NFR-002: at least 3 diagnostic fields).
4. Carries `pytest.mark.architectural`.
5. Includes a path-existence sanity check for every CORE-set directory so that a
   directory rename causes a loud failure rather than a vacuous pass (C-008).
6. Includes a sanity sub-test that drives a **real on-disk** non-allowlisted
   violation through the *same* enforcement scanner the gate uses, proving the
   allowlist cannot be bypassed silently (and a regression in the enforcement loop
   itself — not just a re-implemented copy — would be caught).
7. Pins `len(ALLOWLIST) == 0` with a count-ratchet so the exemption set can never
   silently grow. Issue #2252 has landed: the last exemption
   (`readiness/coordinator.py` → `specify_cli.saas.rollout`) was resolved when
   `is_saas_sync_enabled` moved to `core/saas_sync_config.py`, so the ratchet now
   holds the allowlist at zero.

Any new `.py` file added to a CORE-set directory is automatically covered without
any test change (FR-001, C-008).

---

## Relationship to #2173 (infra/logic separation via ports)

This boundary and the infra/logic-separation work in #2173 (tracked under #1619)
operate on **orthogonal axes** and land independently:

- **This ADR governs package import *direction*** — CORE must not import the
  INTEGRATION set, enforced by `test_integration_boundary.py`.
- **#2173 injects infra *ports* into pure core** (FS / Clock / Git / Resolver) —
  a dependency-*shape* concern, not a cross-package import-direction concern.

The two reinforce each other: the `core/adapters.py` and `invocation/adapters.py`
registries introduced here reuse the established `status/adapters.py` seam, and
\#2173 explicitly *drops* its SaaS port ("already seamed via `fire_saas_fanout`"),
i.e. it leans on the very inversion seam this boundary hardens. Neither blocks the
other; there is no file-level collision.

---

## Allowlist Exemptions

Each entry permits one specific `(source_module, imported_module)` pair with a written
rationale. **The allowlist is now empty.** Exactly one exemption existed when this mission
merged (`readiness/coordinator.py` → `specify_cli.saas.rollout`); it was resolved by
[#2252](https://github.com/Priivacy-ai/spec-kitty/issues/2252), which relocated
`is_saas_sync_enabled` to `core/saas_sync_config.py`. The `len(ALLOWLIST) == 0`
count-ratchet in the enforcement test now holds the exemption set at zero.

| Source | Imported | Rationale | Planned resolution |
|--------|----------|-----------|-------------------|
| *(none — the single historical exemption was resolved by #2252)* | | | |

**Adding new exemptions:** Do NOT add an allowlist entry unless the crossing is a
deliberate, time-bounded exception with a written follow-up plan. Edit
`test_integration_boundary.py` directly with a written rationale. Broadening an
existing entry is not permitted.

---

## Adapter Registries Introduced by This Mission

Three adapter registries were introduced or used to eliminate the leaks:

| Registry | Module | Registration site |
|----------|--------|-------------------|
| Pending-origin consumer | `core/adapters.py` | `tracker/__init__.py` startup hook |
| Sync-routing resolver | `invocation/adapters.py` | `sync/__init__.py` startup hook |
| SaaS-client factory | `invocation/adapters.py` | `sync/__init__.py` startup hook |

All registries follow the idempotent, non-raising contract established by
`status/adapters.py`.

---

## Deferred Scope

The following items are **out of scope** for this mission and are explicitly deferred:

- **Physical extraction to `src/orchestrator/`** — deferred per ADR
  `docs/adr/3.x/2026-05-11-1-defer-391-structural-extraction-from-3-2-x.md` and the
  ownership manifest `docs/architecture/05_ownership_manifest.yaml`. The boundary is
  enforced in-place first; the physical move to a separate top-level package is a
  follow-up mission.
- **Bidirectional enforcement** (preventing INTEGRATION from importing CORE in ways that
  violate contract) — out of scope for this mission (C-003); deferred to a follow-up.
- **`coordination/`, `lanes/`, `runtime/`** — not classified in either set; their import
  patterns are not checked by `test_integration_boundary.py` (C-004). Their boundary
  classification is deferred.

---

## Consequences

### Positive

- CORE governance logic is independently testable without importing external connectors.
- A new `.py` file in any CORE-set directory is automatically covered by the enforcement
  test — no test change required.
- The adapter-registry pattern is consistent across the codebase
  (`status/adapters.py`, `core/adapters.py`, `invocation/adapters.py`).
- Physical extraction to `src/orchestrator/` can proceed safely on top of this enforced
  boundary.
- The allowlist is empty: #2252 relocated `is_saas_sync_enabled` to
  `core/saas_sync_config.py`, so CORE no longer imports the INTEGRATION set even for the
  feature-flag read. The enforcement ratchet is pinned at `len(ALLOWLIST) == 0`.
- **Shim-depth trade-off (intentional):** the `tracker`/`sync` `feature_flags` modules
  re-export through `saas/rollout.py` (retained as a re-export shim) rather than pointing
  directly at `core/saas_sync_config.py`. This keeps a two-hop shim chain
  (`feature_flags` → `saas/rollout.py` → `core/saas_sync_config.py`) but avoids churning
  the NFR-001 function-identity tests that assert `is` identity across every shim.

### Negative

- *(Resolved)* The historical allowlist entry (`readiness/coordinator.py` →
  `specify_cli.saas.rollout`) that once left a structural coupling in CORE was
  closed by #2252; the allowlist is now empty. See the Positive section for the
  resolved state and the intentional shim-depth trade-off.

### Neutral

- `coordination/`, `lanes/`, and `runtime/` remain unclassified; their import patterns
  accumulate unchecked until a follow-up mission addresses C-004.

### Confirmation

This decision is correct when:

1. All three original leaks are fixed (WP01–WP03 merged and approved).
2. ✅ `pytest tests/architectural/test_integration_boundary.py` passes with zero
   allowlist entries.
3. ✅ Follow-up issue [#2252](https://github.com/Priivacy-ai/spec-kitty/issues/2252)
   relocated `is_saas_sync_enabled` to `core/saas_sync_config.py` and removed the last
   allowlist entry.

## More Information

- Mission spec: [`kitty-specs/integration-boundary-01KW0PBE/spec.md`](../../../kitty-specs/integration-boundary-01KW0PBE/spec.md)
- Data model (set definitions and allowlist): [`kitty-specs/integration-boundary-01KW0PBE/data-model.md`](../../../kitty-specs/integration-boundary-01KW0PBE/data-model.md)
- Contract: [`kitty-specs/integration-boundary-01KW0PBE/contracts/integration-boundary-rule.md`](../../../kitty-specs/integration-boundary-01KW0PBE/contracts/integration-boundary-rule.md)
- Enforcement test: `tests/architectural/test_integration_boundary.py`
- Physical extraction deferral: [`docs/adr/3.x/2026-05-11-1-defer-391-structural-extraction-from-3-2-x.md`](./2026-05-11-1-defer-391-structural-extraction-from-3-2-x.md)
- Current package inventory: [`pyproject.toml`](../../../pyproject.toml) `[tool.hatch.build.targets.wheel].packages`, enforced by [`test_pyproject_shape.py`](../../../tests/architectural/test_pyproject_shape.py).
- Current import direction: the `landscape` fixture in [`conftest.py`](../../../tests/architectural/conftest.py) and [`test_layer_rules.py`](../../../tests/architectural/test_layer_rules.py).
- Historical ownership narrative: [`05_ownership_map.md`](../../architecture/05_ownership_map.md). Its companion manifest was deleted; the map is narrative only and does not define current package inventory or import direction.
- Shared-package-boundary precedent: [`architecture/3.x/adr/2026-04-25-1-shared-package-boundary.md`](2026-04-25-1-shared-package-boundary.md)

## Amendment 2026-10-22: the seam this ADR cites as `fire_saas_fanout` is renamed (#6607)

The "Relationship to #2173" section above names `fire_saas_fanout` as the established inversion seam. That function is now `fire_status_fanout` in `status/adapters.py`, and the lifecycle counterpart `fire_lifecycle_saas_fanout` is `fire_lifecycle_fanout`, with no alias. The #2173 quotation is historical and is left as written. The decision in this ADR is unchanged.
