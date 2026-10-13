# Scope C — `charter.offering.api` public-contract delta (HELD FOR OPERATOR APPROVAL)

> Operator selected **Scope C** (literal api-widening repoint) at the scope fork. Per the
> brief's escalation rule and the Scope-C option contract, **every `charter.offering.api`
> addition must be enumerated and explicitly operator-approved BEFORE it is added — the public
> API is not widened silently.** This document is that enumeration + the charter conflicts it
> surfaces. **No `api.py`, disposition-manifest, or gate change has been made.** Date 2026-10-13.

## 0. Why this is held, not executed

1. **It is a public-contract change.** The brief names this the one escalation that must pause:
   *"adding it to `charter.offering.api` is a public-contract change — PAUSE and surface it …
   for an operator decision; do NOT widen the public API silently."*
2. **It conflicts with the charter-blessed, gate-encoded architecture — and the charter wins
   over the brief.** The disposition manifest (`tests/architectural/test_doctrine_census.py::
   DISPOSITION`) deliberately classifies 21 of 26 charter.offering submodules **FACADE-ONLY**,
   with the explicit rationale *"Doorable → FACADE-ONLY (prefer a clean door over widening [the
   public api])."* `test_charter_offering_public_surface.py` asserts FACADE-ONLY / INTERNAL
   modules are **absent** from `charter.offering.api`. Scope C overturns that stance wholesale.
3. **The scope-C selection arrived under a harness "not genuine user input" flag**, so it is
   treated as *direction to analyse and tee up*, not as blanket approval to widen a governed
   contract. Explicit operator confirmation on the itemised list below is required before any
   `api.py` edit.

## 1. What Scope C actually requires (four coupled changes, none in #6188's current non-goals)

- **(C-i) Promote ~21 FACADE-ONLY modules (~110 symbols) to PUBLIC on `charter.offering.api`.**
  The authoritative per-symbol source is the live `_FACADE_TABLE` in
  `tests/architectural/test_charter_facades_reexport_offering.py`. Already PUBLIC (on api, no
  action): `ArtifactKind`, `slug_for`, `AssetManifest/Repository/NotFound/PathEscape/Resolution
  Error`, `evaluate`, `load`, `RoutingRecommendation`, `CatalogLoadResult` (11). To be PROMOTED
  FACADE-ONLY→PUBLIC, grouped by current facade (counts approximate, see `_FACADE_TABLE`):
  - `charter.drg` cluster: ~45 (DRG models `DRGEdge/DRGGraph/DRGNode/NodeKind/Relation`,
    merge `EndpointResolutionError/resolve_edge_endpoint/OrgDRGConflict*/UnknownRelationError/
    merge_three_layers/bridge_org_edge_to_drg_edge`, validator `EndpointEdge/EndpointGraph/
    dangling_endpoints`, loader `load_graph*/load_built_in_graph`, org_pack_config `resolve_org_
    roots/resolve_org_dirs/resolve_existing_org_roots/OrgPackConfig/…`, org_pack_loader
    `OrgDRGFragment/OrgPack*Error/load_org_pack`, query `resolve_context/ResolvedContext`,
    migration.extractor `graph_document_to_dict/model_to_graph_dict/FIELDS_WITHHELD_*`,
    project_scan `scan_project_artifacts`, base `ArtifactLayerCollisionWarning`,
    `LAYERED_REPOSITORY_KIND_PLURALS`, `validate_dangling_references`).
  - `charter.packs`: ~30 (pack_manifest, pack_assembler, pack_validator, pack_descriptor,
    presets, retired_fields).
  - `charter.missions`: ~14; `charter.mission_steps`: 5; `charter.versioning`: 6;
    `charter.profiles`: 5; `charter.template_catalog`: 4; `charter.pack_paths`: 3;
    `charter.provenance`: 2; `charter.resolution`: 2; `charter.primitives`: 2;
    `charter.glossary_packs`: 1; `charter.spdd_reasons`: 1.
  - Plus the 4 specify_cli lazy-reach internals with no clean door today: `CharterOffering
    Service` (governed by the zero-allowlist sole-door gate — must stay wrapped by
    `ActiveCharterService`, so it is NOT a plain api export), `drg.override_policy`,
    `agent_profiles.operating_procedures`, `drg.migration.hand_authored_overlay`
    (all "doorless … TICKETED-BASELINE", owned by #3179/#2173).
- **(C-ii) Rewrite the DISPOSITION manifest** (`test_doctrine_census.py`) to reclassify those
  21 modules PUBLIC, and **relax `test_charter_offering_public_surface.py`** (the negative guard
  that currently asserts FACADE-ONLY absence from api). This is editing the gate that pins the
  seam — a charter-architecture change.
- **(C-iii) The `charter.activation.*` surface (310 import lines) cannot route through
  `charter.offering.api`.** Activation is a *sibling* of `offering` under `src/charter/`, not
  inside it; none of its symbols are charter.offering. Scope C's "route activation onto
  charter.offering.api" is undefined. Either activation stays a direct `specify_cli → charter.
  activation` dependency (then #6188's "no charter internal except via api" is unmet for 310
  lines), or activation needs its own separate public door (a new decision, larger than #6188).
- **(C-iv) `specify_cli` importing `charter.offering.api` directly violates C-001** (the api
  docstring's layering invariant) and the premise of `test_runtime_charter_doctrine_boundary.py`
  (which routes specify_cli through facades, not api). Scope C for specify_cli therefore also
  requires overturning that boundary gate — or keeping specify_cli on facades and only moving
  the *facades* onto api (in which case specify_cli's own imports do not change at all, and the
  "~129 specify_cli sites" framing dissolves).

## 2. Overlap with epic #6099 (the extraction) and #6188 non-goals

(C-i)–(C-iv) are the charter-internal restructure that the extraction epic #6099 itself owns
("Grow the import-boundary / layer-rule tests so the enforced chain becomes a real dependency-
resolution boundary"). #6188's stated non-goals exclude "any change to charter behavior,
doctrine content, or the offering's internals beyond exposing already-needed symbols" — Scope C
goes well past "exposing already-needed symbols": it reclassifies the census authority, edits
the disposition-coupling gate, and restructures the facade/activation internals.

## 3. Decision requested (explicit approval needed before any `api.py` edit)

Confirm one of:
- **(C-full)** Approve promoting the ~110 symbols in §1 (C-i) to PUBLIC on `charter.offering.api`
  + the §1 (C-ii) disposition/gate rewrite, AND give direction on the activation surface (C-iii)
  and the C-001/boundary-gate conflict (C-iv). I will then implement, sliced, with each api
  addition landing against its approved line item.
- **(C-facades-only)** Scope C but *keep specify_cli on the facades* and only move the **facades
  and activation** off charter.offering internals onto `charter.offering.api` — i.e. this is the
  extraction precondition for the to-be-split offering subtree, and specify_cli's own imports are
  unchanged. (This is the coherent, charter-consistent reading of "route consumers onto the api".)
- **Reconsider → Scope B** (the architecturally-recommended drain of the 11 specify_cli/runtime
  lazy offering reaches onto facades), with this §1 list filed to #6099 as the extraction's own
  public-API work.

Until one is confirmed by a genuine operator signal, `api.py`, the disposition manifest, and the
seam gates stay untouched.

## 4. DECISION (operator, via the scope-fork follow-up)

**C-facades-only** selected (charter-consistent). Mandate:
- Move the `charter.*` facades AND `charter.activation.*` off `charter.offering` internals onto
  `charter.offering.api`; promote the §1 (C-i) ~110 FACADE-ONLY symbols to PUBLIC and rewrite the
  DISPOSITION manifest + the negative guard accordingly (**approved** as the enumerated api delta).
- `specify_cli` stays on the facades (C-001 + `test_runtime_charter_doctrine_boundary` stay green);
  its only #6188 non-compliance — the 11 lazy `charter.offering.*` reaches — is drained onto facades.
- Activation gets its own door onto the api, enumerated per-slice.
- Sliced by consuming subsystem; each slice independently reviewable; transparent about the
  #6188 / #6099 boundary in the PR.
