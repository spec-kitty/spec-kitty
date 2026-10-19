---
title: Functional Ownership Map (demoted — narrative only)
description: 'Historical functional-ownership narrative. Not authoritative: module boundaries are owned by the enforced pyproject wheel packages plus the test_layer_rules layer chain.'
doc_status: superseded
updated: '2026-10-19'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/architecture/00_landscape/README.md
- pyproject.toml
- tests/architectural/test_layer_rules.py
---
# Functional Ownership Map (demoted — narrative only)

> **⚠️ Not authoritative.** This document is a **historical narrative** of how functional
> ownership was *once* modelled (mission `functional-ownership-map-01KPDY72`, 2026-04). Its
> machine-readable companion `05_ownership_manifest.yaml` and that manifest's schema gate
> (`tests/architecture/test_ownership_manifest_schema.py`) were **deleted** by mission
> `post-convergence-governance-01M1TMPH` (2026-09-06): the manifest had drifted from reality
> (it named the deleted `src/doctrine/`, `src/specify_cli/sync/`, `src/specify_cli/saas/`
> trees and the never-created `src/lifecycle/` / `src/orchestrator/` targets), and its schema
> gate *pinned* that stale vocabulary — so correcting the manifest reddened the gate. Rather
> than perpetuate a self-declared authority that contradicted the code, both were removed.

## The canonical modularity SSOT is the enforced pair

Module boundaries and inventory are owned by two **enforced** sources that agree with each
other and with the code CI actually ships. Treat every other module map (this file, the C4
landscape/implementation-mapping docs, the `AGENTS.md` package lists) as a *derived view* that
must cite them:

| Concern | Canonical source | Enforced by |
|---|---|---|
| Module **inventory** (which top-level packages ship) | `pyproject.toml` `[tool.hatch.build.targets.wheel].packages` | `tests/architectural/test_pyproject_shape.py` |
| Import **direction** (the layer chain) | `tests/architectural/conftest.py` `landscape` fixture + `tests/architectural/test_layer_rules.py` | `test_layer_rules.py` (pytestarch `LayerRule` + `TestLayerCoverage` meta-tests + the `mission_runtime` and `runtime` outbound ledgers) |
| Retired-subsystem **negative** boundary | `pyproject.toml` `[tool.ruff.lint.flake8-tidy-imports.banned-api]` (TID251) | `tests/architectural/test_no_retired_subsystems.py` |

The enforced layer chain is:

```
kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli
```

`charter.offering` holds the doctrine code the former top-level `src/doctrine/` package was
relocated into (Convergence #3881); the `src/doctrine.py` deprecation shim was removed (#805).

> **Direction (2026-10-12):** `charter` is slated to leave this in-tree layer chain and become
> an external contract package **in its own repository**, consumed through `charter.offering.api`
> like `spec-kitty-events` / `spec-kitty-tracker` (ADR
> [`2026-10-12-2`](../adr/4.x/2026-10-12-2-charter-extraction-to-its-own-repository.md);
> precondition #645, now GA-gating). The enforced pair stays the authority; this note changes
> no gate.
>
> **Superseded (2026-10-19):** `charter` stays in this in-tree layer chain. The Python charter
> stays in core until it is retired and nothing Python moves to `spec-kitty-charter`; offering
> reads cut over to the `spec-kitty-charter` service through `charter.offering.api`
> (`spec-kitty-charter` ADR-0008 and ADR-0010, which supersede ADR `2026-10-12-2`; ADR
> [`2026-10-16-1`](../adr/4.x/2026-10-16-1-extract-charter-offering-first-activation-rework-post-ga.md),
> Amendment 2026-10-19).

## Hosted client packages were removed

The former `zeitgeist_client/` and `saas_client/` packages were removed from open-core (#6164; the code is preserved in `spec-kitty/event-router`). See ADR
[`2026-09-06-1-convergence-retirement-and-client-repo-inversion`](../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md)
and the precedent ADR
[`2026-04-25-1-shared-package-boundary`](../adr/3.x/2026-04-25-1-shared-package-boundary.md).

## Historical note

The original slice model (`cli_shell`, `charter_governance`, `doctrine`,
`runtime_mission_execution`, `glossary`, `lifecycle_status`, `orchestrator_sync_tracker_saas`,
`migration_versioning`) framed an extraction roadmap (missions #612–#615). Only glossary
(→ `src/glossary/`) and part of runtime (→ `src/runtime/next/`) were extracted; the
`src/lifecycle/` and `src/orchestrator/` targets were never created, and the sync/saas slice
was retired outright by the Convergence. Consult git history for the pre-2026-09-06 slice
detail; do not treat it as a current statement of ownership.
