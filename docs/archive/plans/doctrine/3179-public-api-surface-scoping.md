---
title: '2026-08-10 — #3179 doctrine public API surface — scoping brief'
description: 'Pre-spec scope for the doctrine public-API mission (#3179): reach-through inventory, charter-facade gap map, lazy-import ratchet, and the #3101 wheel-cutover precondition.'
doc_status: deprecated
updated: '2026-08-10'
related:
- docs/plans/doctrine/index.md
- docs/archive/plans/doctrine/next-slice-wheel-mission-types-public-api-research.md
- docs/adr/3.x/2026-08-02-1-charter-wheel-assessment.md
---

# #3179 — Doctrine public API surface — scoping brief

> **Retired (deprecated).** Design shipped via merged mission `doctrine-public-api-surface-01KZPDSR` (#3179; #3101/#3176/#3182). Preserved as a historical record.

**Tier: EVIDENCE / pre-spec.** Squad-gathered scope for a future `/spec-kitty.specify`.
Not an AUTHORITY doc — the citable sequencing statement remains
[`next-slice-wheel-mission-types-public-api-research.md`](next-slice-wheel-mission-types-public-api-research.md)
and ADR [`2026-08-02-1`](../../../adr/3.x/2026-08-02-1-charter-wheel-assessment.md).

Gathered on a detached checkout of `upstream/main` (@ `4ce2e7097`). No files edited
during scoping; every count below is AST- or SonarCloud-derived, not estimated.

## Why this mission, why now

The research doc established the interlock: **(c) public API (#3179) is a precondition
for (a) the atomic `kernel → doctrine → charter` wheel cutover (#3101), not parallel to
it** — "you cannot publish a wheel with a credible external contract if the internal call
sites are already reaching past the declared surface." Unlike #3101, this mission needs no
go-decision; it is the unblocked next increment.

The module-level boundary is already **green**: `test_runtime_charter_doctrine_boundary.py`
holds an *empty* allowlist — all 13 original module-level violators were migrated to
`charter.*` facades. The remaining encapsulation debt is entirely **lazy (in-function)**
reach-through that the current ratchet does not see, plus the absence of a curated public
surface for the dormant `spec-kitty-doctrine` wheel to export.

## The measured reach-through

**26 distinct internal doctrine paths** are reached from runtime (`src/specify_cli/`,
excluding the sanctioned management subpackage `src/specify_cli/doctrine/`). **All are
lazy** — AST-accurate target is **54 runtime-lazy imports across 29 files** (a further 16
`TYPE_CHECKING`-only imports across 11 files are correctly out of scope). Classification:

| Bucket | Count | Meaning |
|---|---|---|
| Facade door already exists (some partial) | ~11 | `charter.*` re-exports it; direct import is migration debt |
| Reach-through debt, **no door at all** | ~13 | needs a new/widened facade before migration is possible |
| Keep **INTERNAL** (hide) | ~6 | `drg.override_policy`, `drg.migration.*`, `missions.mission_step_repository`, `missions.step_projection`, `pack_paths`, bare-`doctrine` introspection |

### The 6 true public-API gaps (charter itself has no door)

Highest priority — these are genuine holes in doctrine's public surface, not just
un-migrated imports:

1. `doctrine.model_task_routing.*` (`evaluator`, `loader`, `RoutingRecommendation`) — charter has zero references. → new `charter.model_routing` facade.
2. `doctrine.assets.repository` / `doctrine.assets.models` — charter never imports `doctrine.assets`. → new `charter.assets` facade.
3. `doctrine.drg.override_policy` — untouched by charter → keep INTERNAL.
4. `doctrine.drg.migration.hand_authored_overlay.write_reference_graph_with_overlay` → keep INTERNAL.
5. `doctrine.missions.repository.MissionsRootNotFound` → pair into a `charter.missions` facade.
6. **Raw `doctrine.service.DoctrineService` bypass** — 5 sites (`_doctrine_asset.py`, `_doctrine_collect.py`) construct it directly, sidestepping the activation-aware sole door (`charter.resolver.DoctrineService`). Governance leak; fix onto `charter.doctrine_service_builder`.

### Cluster map (charter-facade coverage)

- **`doctrine.drg.*`** — largest, most fragmented cluster; `charter.drg` already fronts most of it. **Highest-leverage single fix**: widen `charter.drg` with `DRGLoadError`, `DRGValidationError`, `resolve_org_roots`, `OrgDRGConflict` (already exports `OrgDRGConflictError`), and keep `override_policy`/`migration.*` hidden.
- **`doctrine.missions.*` (non-step-contract)** — `MissionTemplateRepository`, `MissionTypeRepository`, `builtin_mission_type_ids`, `step_projection`; **not** covered by `charter.mission_steps` (which fronts only step-contract types). → one new `charter.missions` facade covers the cluster.
- **`doctrine.agent_profiles.*`** — fully covered by `charter.profiles`; pure mechanical re-import migration.
- **`doctrine.model_task_routing.*`** — small but 100% uncovered → one new `charter.model_routing` facade.
- **`doctrine.missions.step_contracts.GateBinding`** — module is facaded but this symbol isn't re-exported → widen `charter.mission_steps`.

## Proposed mission shape

The load-bearing design decision, reached independently by every scoping lens:
**do not simply widen `doctrine.__all__`.** That would *legitimize* runtime importing
doctrine directly, contradicting the enforced `runtime → charter → doctrine` layering. The
sanctioned consumption path is a `charter.*` facade re-export (identity-checked by
`test_charter_facades_reexport_doctrine.py`). Instead:

- **WP-A — Define the doctrine public surface.** Add a curated `doctrine/api.py` (or explicit
  per-subpackage `__all__`) naming the stable types. This gives *charter* and the dormant
  wheel one real export target instead of 26 deep paths, and lets
  `test_doctrine_wheel_closure.py` pin a real surface.
- **WP-B — Grow the charter facades** to front the PUBLIC + FACADE-ONLY rows: widen
  `charter.drg` and `charter.mission_steps`; add `charter.missions`, `charter.model_routing`,
  `charter.assets`. Each addition stays a pure identity re-export.
- **WP-C — Migrate the ~13 undoored + facade-only importers** file-by-file; fix the 5 raw
  `DoctrineService` sites onto the sole door. First migration to prove the ratchet shrinks:
  `runtime/resolver.py:528` → `charter.template_catalog` (door already exists, one-line change).
- **WP-D — Land the lazy-import ratchet.** Sibling test in
  `test_runtime_charter_doctrine_boundary.py`, `ast.walk` minus `TYPE_CHECKING`, a frozenset
  baseline seeded at the 29 files that only-shrinks (two-direction assertion: no new
  violators, no stale allowlist entries). This is the explicitly-deferred "follow-up ratchet"
  named in that test's own docstring.

**Sequencing constraint:** WP-B must precede WP-C for the facade-blocked files
(`invocation/executor.py` needs `charter.model_routing` + capabilities;
`tool_surface/bundles/claude.py`/`codex.py` need a `pack_paths`/`ArtifactKind` re-export).
The WP-D baseline legitimately keeps those allowlisted until their door lands; the
stale-entry assertion forces removal once it does. Hoisting any blocked import to module
level is a dead end — it just trips the sibling module-level ratchet.

## Design note — OpenAPI does **not** apply to `doctrine/api.py`

Recorded so a later agent does not re-litigate: `doctrine/api.py` **must not** be shaped
around OpenAPI/REST conventions.

OpenAPI describes an **HTTP wire boundary** — paths, verbs, status codes, serialized JSON
schemas. `doctrine/api.py` is an **in-process Python import surface**: consumers reach it
with `import` and receive live rich objects (`BaseDoctrineRepository[T]`, `DoctrineService`,
`DRGGraph`, `ArtifactKind` enums, callables). Nothing is serialized; nothing crosses a
socket. Forcing OpenAPI onto it would (a) describe a transport that does not exist, (b)
destroy the type fidelity and object-identity semantics the boundary exists to protect
(OpenAPI cannot express a generic repository, `X is Y` facade identity, callables, or the
sole-door activation contract), and (c) imply a versioned URL/wire contract where the real
contract is a Python type contract.

OpenAPI's actual goals — explicit contract, versioning, enforced stability — map to Python
analogs the mission should adopt instead:

| OpenAPI concept | `doctrine/api.py` analog |
|---|---|
| Schema document (the contract) | curated `api.py` + explicit `__all__` |
| `info.version` | **semver on the `spec-kitty-doctrine` wheel** (#3101) — the wheel version *is* the API version |
| Typed request/response schemas | `py.typed` marker + full type exports (mypy-checked fidelity) |
| `deprecated: true` | docstring stability tiers + `warnings.warn(DeprecationWarning)` |
| Contract/schema-diff CI | the facade-identity test + the new lazy-import ratchet |

**Where OpenAPI would legitimately apply:** only if doctrine is ever exposed *over the
network* (a hosted pack registry / doctrine service via `orchestrator-api` or the SaaS
layer — the only places the repo's existing `openapi` references live). Even then the
OpenAPI doc describes the thin HTTP handler that *calls into* `doctrine/api.py`; it never
describes `api.py` itself. The Python surface stays a Python contract.

## SonarCloud read (public project `Priivacy-ai_spec-kitty`, analyzed 2026-08-10)

The doctrine tree is one of the **cleaner** areas of the repo: **48 open issues, all code
smells, zero bugs / vulnerabilities / security hotspots**; 94 of 105 files are clean. Debt
concentrates almost entirely in `src/doctrine/drg/migration/` (39 of 48) — precisely the
subtree this mission classifies **INTERNAL / keep-hidden**, so the encapsulation call and
the maintainability call agree.

- `drg/migration/hand_authored_overlay.py` — **36 `S1192`** duplicate DRG-URN literals (same file as gap #4). Mechanical one-pass fix (hoist URNs to constants); fold in as campsite cleanup when touching the file.
- `artifact_kinds.py:118` — **`S7632`**, a *malformed issue-suppression comment*. Worth fixing regardless (charter forbids sloppy suppressions), and this file is on WP-A's path.
- **Out-of-scope refactor candidate (tracker note, not this mission):** `drg/migration/extractor.py:545` at **cognitive complexity 183** (>12× the ≤15 standing order), plus 7 more `S3776` breaches (`versioning.py:316`=65, `agent_profiles/repository.py:365`=36, `base.py:227`=28…). A distinct maintainability slice on `drg/migration/`; do **not** blur it into this boundary mission.
- Quality gate is ERROR but **not doctrine-attributable** — the two failing conditions are project-wide `new_reliability_rating` / `new_security_rating`; doctrine adds zero new bugs/vulns.

## Enforcement files a future spec should cite

- `tests/architectural/test_runtime_charter_doctrine_boundary.py` — ratchet to extend (`_module_imports_doctrine_directly` walks only `tree.body`).
- `tests/architectural/test_charter_facades_reexport_doctrine.py` — `_FACADE_TABLE` to grow (identity re-export gate).
- `tests/architectural/test_layer_rules.py` — layer invariants.
- `tests/architectural/test_doctrine_wheel_closure.py` — dormant wheel shape; gains a real export surface.
- `src/doctrine/__init__.py` — surface to define; `src/charter/{profiles,drg,mission_steps,primitives,resolution,versioning}.py` — facades to extend/add.
