# Grounding note — #6188 "Move the ~129 `specify_cli → charter` imports onto `charter.offering.api`"

> Read-only pre-spec grounding (SEMI-AUTO, grounding-first doctrine). Author: governed
> orchestrator. Date: 2026-10-13. Branch: `issue-6188-charter-offering-api-import-move`.
> Status: **PAUSED for an operator scope decision** (see §5). No source changed.

## 1. What the issue asks vs. what the code actually enforces

Issue #6188 (child of epic #6099; cites ADR `2026-10-12-2`, `2026-04-25-1`, `2026-08-02-1`)
states the deliverable as:

- "Repoint every `specify_cli` import that reaches a charter internal onto **`charter.offering.api`**."
- Acceptance: "No `specify_cli` module imports a charter internal **except via `charter.offering.api`**."
- Cites the gate **`tests/architectural/test_doctrine_public_surface.py`**.

Three of these do not match the repository as it stands today:

1. **`tests/architectural/test_doctrine_public_surface.py` does not exist.** The live gates are
   `test_charter_offering_public_surface.py` (the offering wheel-surface shape) and
   `test_runtime_charter_doctrine_boundary.py` (the consumer→offering boundary).
2. **`charter.offering.api` is explicitly NOT a runtime door.** Its own module docstring states
   the C-001 layering invariant: *"Runtime code under `src/specify_cli/` must NOT
   `from charter.offering.api import …` directly; the charter facades (WP03) re-export these
   symbols by object identity and are the only sanctioned importers."* The sanctioned reach is
   **`specify_cli / runtime → charter.* facade → charter.offering.*`**, enforced by
   `test_runtime_charter_doctrine_boundary.py` and the identity gate
   `test_charter_facades_reexport_offering.py`.
3. **`charter.offering.api` is a narrow, curated 11-symbol manifest** (`ArtifactKind`, `slug_for`,
   the `Asset*` family, and the model→task-routing `evaluate`/`load`/`RoutingRecommendation`/
   `CatalogLoadResult`). It is the *offering* layer's surface. It cannot host the
   `charter.activation.*` surface (activation is a sibling of `offering`, not inside it), nor the
   facade modules themselves.

The #6188 body reads as written from the ADR's high-level framing. The stale `#645` reference
(an unrelated, now-closed dashboard epic) and the companion PR **#6187** ("point
charter-extraction direction at epic #6099, not closed #645", open 2026-10-13) confirm the
reference set around this work is still being corrected. **#6188 (created 2026-10-13, child of
#6099) is the authoritative handle; its wording needs reconciling with the real topology.**

## 2. Census (authoritative; verified by `rg` + AST line-scan, cross-checked)

Imports of the `charter` package under `src/specify_cli/**` (plus `src/runtime/**` for the
boundary): **127 files, 509 charter import lines**, in three classes:

| Class | What | Lines | Role |
|---|---|---|---|
| **1 — FACADE** | `charter.<topmod>` (drg, missions, bundle, packs, profiles, assets, resolution, model_routing, hasher, pack_paths, mission_steps, spdd_reasons, template_catalog, glossary_packs, primitives, versioning, provenance) + bare `from charter import …` | **177** | Already the **sanctioned public charter door**. NOT a refactor target. |
| **2 — OFFERING-INTERNAL** | `charter.offering.*` | **22** | The gate-defined "charter internal". **All 22 are in-body (lazy/TYPE_CHECKING); zero module-level.** |
| **3 — ACTIVATION** | `charter.activation.*` | **310** | The dominant coupling (`pack_context` 38, `charter_yaml_io` 21, `layer_roots` 21, `compiler` 18, `synthesizer.*` 53…). Activation is **not** the offering layer and has **no** boundary gate forbidding it. |

No dynamic/string (`importlib`/`__import__`) charter imports. No `charter_`-prefixed local
false-positives counted.

### The gate-tracked offering reach is already almost fully drained

`test_runtime_charter_doctrine_boundary.py` forbids `charter.offering.*` imports from
`src/specify_cli` and `src/runtime`:

- **Module-level baseline: EMPTY** — direct offering imports are already fully forbidden/absent.
- **Lazy baseline (`_LAZY_BASELINE_ALLOWLIST`): 11 grandfathered file/module pairs**, each
  ticketed, migrating out:
  - `cli/commands/_charter_pack_collect.py` → `service`, `agent_profiles.operating_procedures`,
    `artifact_kinds`, `drg.loader`, `drg.override_policy`, `pack_paths` (6)
  - `cli/commands/charter/pack_asset.py` → `service` (1)
  - `cli/commands/charter/pack_tooling.py` → `drg.migration.hand_authored_overlay` (1)
  - `tool_surface/bundles/codex.py` → `charter.offering` (`__file__` metadata, not a symbol) (1)
  - `src/runtime/next/runtime_bridge_composition.py` → `missions.step_contracts` (1)
  - `src/runtime/next/runtime_bridge_io.py` → `missions.step_projection` (1)
- The remaining offering lines the census found (in `mission.py`, `dossier/manifest.py`,
  `cli/commands/charter/mission_type.py`, `tasks_move_task_gates.py`,
  `mission_step_contracts/executor.py`) are all under `if TYPE_CHECKING:` — erased at runtime,
  explicitly exempt from the boundary gate. Several carry comments that routing through the
  facade would degrade the type to `Any` under `mypy --strict` (the #4188 / #2844
  `follow_imports=skip` problem) — a real constraint on repointing type-only imports.

## 3. The gates that pin this seam (and how each stays honestly green)

- `test_runtime_charter_doctrine_boundary.py` — consumer→offering boundary (module-level EMPTY;
  lazy ratchet shrink-only). Draining a lazy pair **removes** its baseline entry (shrink
  direction); the gate stays green because the import moved to a facade.
- `test_charter_facades_reexport_offering.py` — every facade symbol re-exported from
  `charter.offering` must be the **same object** (identity) and be tabled in `_FACADE_TABLE` +
  the facade's `__all__`. Any new facade door needs a table row + `__all__` entry here.
- `test_charter_offering_public_surface.py` — `charter.offering.api` shape (importable, sorted,
  disposition-coupled to `test_doctrine_census.py::DISPOSITION`, no INTERNAL/FACADE-ONLY leak).
  Adding a symbol to `api.py` requires a `PUBLIC` disposition in the WP01 census.
- `test_layer_rules.py` / `test_pyproject_shape.py` / `test_shared_package_boundary.py` — the
  enforced chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`.
  **A repoint from `charter.offering.*` to `charter.*` keeps the edge `specify_cli → charter`,
  so these stay green unchanged.** No `pyproject.toml` package-set change is in scope.

## 4. The genuinely "doorless"/entangled items (not mechanical)

Several lazy-baseline reaches are deliberately un-fronted and owned by other tickets:
- `charter.offering.service.CharterOfferingService` — governed by its **own zero-allowlist**
  sole-door gate (`test_charter_sole_door_offering_service.py`): raw construction must be wrapped
  by `charter.activation.resolver.ActiveCharterService`. Not a plain facade candidate.
- `charter.offering.drg.override_policy`, `charter.offering.drg.migration.hand_authored_overlay`
  — labelled "doorless … TICKETED-BASELINE" management/DRG-regeneration internals (#3179).
- `agent_profiles.operating_procedures` — "pending facade migration" (#3179).
- `runtime` step-contract/step-projection reaches — "charter.missions migration #2173".

Exposing any of these on a facade is itself a (facade-level) public-surface decision and
overlaps #3179 / #2173 / #3522 ownership.

## 5. The scope fork — operator decision required (the ONE escalation)

The literal acceptance criterion cannot be satisfied as written (specify_cli importing only
`charter.offering.api` contradicts the C-001 invariant and cannot host activation/facade
symbols). Two coherent readings exist, with very different deliverables:

**Scope B — decouple `specify_cli`/`runtime` from `charter.offering` *internals* (recommended).**
Drain the 11 lazy `charter.offering.*` reaches onto the `charter.*` facade door, emptying
`_LAZY_BASELINE_ALLOWLIST`. This is the true "specify_cli no longer reaches a charter internal"
state on the gate-enforced definition. **Does not widen `charter.offering.api`**; grows facade
re-export tables (mostly FACADE-ONLY disposition) and may need ~2 new facade doors for the
doorless internals. Honors #6188's non-goals (no change to charter behavior / offering
internals). ~6 files, but entangled with #3179/#2173/#3522 and with the #4188 mypy-`Any` leak.

**Scope C — the literal "129/509-site" repoint onto `charter.offering.api`.** Route the
`charter.*` facades **and** `charter.activation.*` onto `charter.offering.api` so the
`charter.offering` subtree can physically split. This **requires substantially widening
`charter.offering.api`** (a public-contract change — the exact escalation the brief names),
restructures charter internals (a stated #6188 non-goal), and overlaps epic #6099's own
extraction work. Large, higher-risk.

**Recommendation:** **Scope B**, plus delivering the Scope-C public-API delta enumeration (below)
as a report folded into epic #6099 rather than implemented here. Rationale: B is the piece that
is actually "`specify_cli → charter`", is architecturally correct, keeps `charter.offering.api`
narrow per its C-001 design, and leaves the facade/activation→api restructure (which is charter
internal and belongs to the extraction epic) to #6099.

### Public-contract delta (symbols a consumer needs that are NOT yet on a public door)
- On **`charter.offering.api`** (PUBLIC wheel surface): **none required for Scope B.**
- On the **facade** layer, Scope B would need doors/rows for: `CharterOfferingService` (via the
  sole-door `ActiveCharterService` wrapper pattern, not a raw re-export), `override_policy`,
  `hand_authored_overlay`, `operating_procedures` — each currently doorless by design and
  ticketed elsewhere.
- Scope C's `charter.offering.api` additions would be large and must be enumerated and
  operator-approved before any are added.
