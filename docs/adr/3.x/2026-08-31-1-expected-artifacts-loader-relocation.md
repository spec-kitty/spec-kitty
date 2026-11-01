---
title: 'ADR: Relocate the expected-artifacts.yaml loader authority into charter, sibling error model'
description: 'The canonical expected-artifacts.yaml loader moves into charter/activation for one shared authority under C-001, keeping MalformedManifestError and ManifestSchemaError as siblings.'
status: Accepted
date: '2026-08-31'
doc_status: active
kind: ADR
updated: '2026-08-31T00:00:00Z'
---

# ADR: Relocate the `expected-artifacts.yaml` loader authority into `charter`, sibling error model

**Status:** Accepted

**Date:** 2026-08-31

**Deciders:** Mission `expected-artifacts-loader-unification-01M1C9VQ`
(mission_id `01M1C9VQZ28CFRW741WRADS6SZ`); closes #3770 and #3412; epic #3410
(charter/doctrine silent-drop). Decision `01M1CBARZBBWVGWBTWRMHPP661`
(operator-selected relocate-into-charter strategy).

**Technical Story:** #3770 (four drifted `expected-artifacts.yaml` loader
reimplementations), #3412 (a YAML-syntax-broken *org* manifest silently
laundered into a green guard for custom mission families). Planning
contracts under `kitty-specs/expected-artifacts-loader-unification-01M1C9VQ/`
— `spec.md` (FR-001/FR-002/FR-003/FR-007/FR-008), `research.md` (D1-D9),
`contracts/arch-gate.md`.

---

## Context and Problem Statement

Four independent modules each re-implemented the same
`expected-artifacts.yaml` org-tier-then-built-in-tier precedence, the same
`ExpectedArtifactManifest.model_validate(...)` call, and the same
`ValidationError` -> `ManifestSchemaError` wrapping:

1. `specify_cli/dossier/manifest.py` (`ManifestRegistry.load_manifest`,
   cached) — the historical canonical loader.
2. `runtime/resolver.py` (`_load_expected_artifact_manifest`) — an uncached
   mirror.
3. `runtime/next/runtime_bridge_io.py` (`_presence_filenames_for`) — another
   uncached mirror, projecting into `frozenset[str]`.
4. `charter/activation/mission_type_profiles.py`
   (`_resolve_expected_artifacts_slot`) — the worst-drifted copy: it read
   the **raw, unvalidated** parsed-YAML mapping straight off
   `MissionTemplateRepository`, bypassing `model_validate` entirely.

A fifth site, `ExpectedArtifactManifest.from_yaml_file`, was a direct-read
orphan with no production caller, constructing via `cls(**data)` — a shape
no `model_validate`-string gate could ever police.

These four had already drifted once inside #3729 (each independently patched
a subset of the org-tier/cache/error-wrap behaviour). The behavioral
consequence of that drift was #3412: `org_expected_artifacts._read_yaml_mapping`
swallowed a real `YAMLError` to `None`
(`org_expected_artifacts.py:109-116`), which two-stage-laundered through
`_resolve_org_manifest_mapping` -> `_expected_artifacts_manifest_resolves` ->
`blocking_artifact_names=None` -> `evaluate_guards_strict` raising
`UnregisteredMissionFamilyError` -> **caught at
`runtime_bridge_composition.py:504` and degraded to `return []`** (silent
green). An operator who hand-edits a custom mission family's org-tier
manifest and introduces a real YAML-syntax error gets no signal at all — the
mission proceeds as if the manifest were absent, not broken.

Fixing #3412 at the swallow site alone would leave the fix duplicated across
whichever of the four loaders happened to be reachable for a given caller —
the same drift risk that produced the four-way split in the first place.
Unifying the loaders (#3770) is therefore the enabling move: fix the
behavioral gap in exactly one place, and make it structurally impossible for
a fifth copy to appear.

### The C-001 boundary

`mission_type_profiles.py` (site 4 above) lives in `charter.activation`.
Charter must not import `specify_cli` (project-wide constraint C-001,
enforced by `tests/architectural/test_charter_no_specify_cli_import.py`).
The historical canonical loader (site 1) lived in
`specify_cli/dossier/manifest.py`. A charter-tier caller therefore could
**never** reach the specify_cli-resident authority without violating C-001 —
which is exactly why site 4 grew its own third, unvalidated copy instead of
delegating to site 1. Unifying onto a single authority requires that
authority to live somewhere every caller — runtime AND charter-tier — can
import without crossing the boundary in the wrong direction. Only `charter`
satisfies that for both directions (activation may import offering, proven
by existing `mission_type_profiles.py` imports of
`MissionTemplateRepository`; `specify_cli` may import `charter` freely).

## Decision Drivers

* **C-001 (charter must not import specify_cli).** The relocated authority,
  and every error type it raises, must be reachable from `charter.activation`
  without a reverse-direction import.
* **DIRECTIVE_044 (canonical sources, one authority).** The goal is not
  "these four now agree" — it's "there is exactly one implementation the
  other three (or a specify_cli-side delegate) call".
* **DIRECTIVE_043 (close the defect class by construction).** Consolidation
  alone doesn't stop a fifth copy appearing later; a non-vacuous arch-gate
  (a companion artifact to this ADR, not covered here — see
  `tests/architectural/test_expected_artifacts_loader_gate.py`) is required.
* **Message correctness.** `ManifestSchemaError.__str__` says
  "schema-invalid" (`specify_cli/dossier/manifest.py:149-155` pre-move); its
  own docstring pre-move explicitly *excluded* YAML-syntax failures from its
  scope. Routing a parse fault through it would be actively misleading.
* **Minimal blast radius for the stateful registry.** `ManifestRegistry` is
  instantiated four times across specify_cli
  (`dossier_pipeline.py:361`, `reconcile.py:158`, `rebaseline.py:346`, +
  one doc reference) as `Indexer(ManifestRegistry())`; it also owns sibling
  completeness methods (`get_required_artifacts`, `get_blocking_artifacts`,
  `get_optional_artifacts`, `validate_manifest`, `clear_cache`) that are
  genuinely specify_cli-owned (dossier/indexer concerns, not manifest
  resolution). Moving the whole class would drag unrelated
  specify_cli-owned logic into charter.

## Decision Outcome

**Chosen option:** relocate only the *load-and-validate* function (plus its
sibling error type) into `charter.activation`, and keep `ManifestRegistry`
in `specify_cli` as a thin delegate to that function — because it is the
smallest move that satisfies C-001 for every existing caller while leaving
specify_cli-owned state and completeness logic where it already lives.

### (a) The relocated authority

`charter/activation/manifest_loader.py` gains one function,
`load_manifest(mission_type, *, repo_root)`, carrying its own module-level
`_cache` keyed `(mission_type, org_roots)` — the same key shape the
pre-move `ManifestRegistry._cache` used (NFR-002: cache semantics,
cross-root non-shadowing, and declaration-order guarantees are preserved
byte-for-byte). It owns:

* org-tier resolution via `resolve_org_expected_artifacts`
  (`charter/activation/org_expected_artifacts.py`) and
  `resolve_existing_org_roots`
  (`charter/offering/drg/org_pack_config.py`),
* built-in-tier resolution via `MissionTemplateRepository`
  (`charter/offering/missions/repository.py`),
* the `ExpectedArtifactManifest.model_validate(...)` call for both tiers,
  and
* `ValidationError` -> `ManifestSchemaError` wrapping.

This satisfies FR-001. `mission_type_profiles._resolve_expected_artifacts_slot`
(FR-006) now calls this function directly — an intra-`charter.activation`
call, not a boundary crossing — and gains real schema validation as a side
effect (it previously handed callers a raw, unvalidated mapping).

### (b) The sibling error model, not a single canonicalized channel

`MalformedManifestError` (already charter-resident,
`charter/offering/missions/repository.py:38`, shipped in `1763bf2ae3` for
the built-in tier's YAML-syntax case) and `ManifestSchemaError` (relocated
here from `specify_cli/dossier/manifest.py`) are **siblings**, not one
canonicalized onto the other:

* `MalformedManifestError` — present-but-unparseable: YAML-syntax error,
  non-mapping parse result, or present-but-unreadable
  (`OSError`/`UnicodeDecodeError`) — on **both** tiers (FR-007, FR-012).
* `ManifestSchemaError` — schema/`extra="forbid"` violation, i.e. the
  content parses as YAML but fails `ExpectedArtifactManifest.model_validate`
  (FR-008).

Both are distinct from `None` = "not found" — the *only* legitimately
absent case. The post-spec squad's earlier draft (spec FR-008 v1)
canonicalized malformation onto `ManifestSchemaError`; that was corrected
during research (decision D2) for three independent reasons that all point
the same direction: `ManifestSchemaError`'s message and docstring actively
exclude parse faults; the built-in tier already used
`MalformedManifestError` for exactly this case, so re-pointing would break
tier symmetry; and — the load-bearing one for this ADR — a
`ManifestSchemaError`-only design would still need `MalformedManifestError`
to exist somewhere in charter anyway, since the built-in tier already raised
it, so nothing is saved by conflating the two.

`MalformedManifestError` stays where it already lived
(`charter/offering/missions/repository.py`), beside
`MissionTemplateRepository`. `ManifestSchemaError` moves to
`charter/activation/manifest_loader.py`, beside the function that raises it.
They live in **two different charter modules**, not one, because
`charter.offering` (where `MalformedManifestError` sits) must not import
`charter.activation` (where the loader sits) — the same directional
constraint as C-001, one layer down: activation may depend on offering,
never the reverse (confirmed by the only existing offering-side reference to
activation being a `TYPE_CHECKING`-only mention,
`mission_step_repository.py:44`). The loader in `activation` imports
`MalformedManifestError` from `offering` (the allowed direction) to raise
it for the org-tier and widened-built-in-tier parse-fault cases; it does not
need to import anything from `activation` to define
`ManifestSchemaError` locally beside itself.

### (c) The deprecation-shim contract

`specify_cli/dossier/manifest.py` re-exports, with **object identity**
preserved (verified by `tests/dossier/test_manifest.py`'s shim-reexport-surface
tests — `import X as Y; X is Y`, not a re-implementation):

* `ManifestRegistry` — kept in place (see (d)).
* `load_manifest` — the relocated authority function, re-exported directly.
* `ManifestSchemaError` — the relocated sibling error, re-exported directly.
* `MalformedManifestError` — re-exported from its charter home, so a
  specify_cli-side `except MalformedManifestError` catches the same
  exception type the charter-tier authority raises.

This is FR-002. `ManifestSchemaError` is caught at 8+ specify_cli sites
(`sync/namespace.py:102`, `sync/dossier_pipeline.py:363`, six tests as of
this mission); omitting it from the shim would break every one of those
catch sites on import. The shim's removal is a future, separately announced
deprecation — not scheduled by this ADR.

### (d) `ManifestRegistry` stays in `specify_cli`

`ManifestRegistry.load_manifest` becomes a thin delegate to
`charter.activation.manifest_loader.load_manifest`; the class itself, and
its sibling completeness methods (`get_required_artifacts`,
`get_blocking_artifacts`, `get_optional_artifacts`, `validate_manifest`,
`clear_cache`), do **not** move (FR-003, decision D3). The alternative —
moving the whole class into charter — was rejected: it would relocate
dossier/indexer-completeness logic that has nothing to do with the
charter↔specify_cli manifest-resolution seam, purely to keep one class's
methods physically adjacent. `ManifestRegistry` is instantiated four times
in specify_cli as `Indexer(ManifestRegistry())`; none of those call sites
need to change.

### (e) C-006 — a corrupt org override now hard-blocks a registered built-in family

The guard-table short-circuit for a **registered built-in family** (e.g.
`software-dev`) — `runtime_bridge_cores.py:721-723` — decides
`blocking_artifact_names` **before** the composed guard reads the manifest
resolution result, and that short-circuit is explicitly out of this
mission's scope (C-003, owned by #3386/#3397/#3407). Manifest resolution
itself, however, now runs at *gather* time
(`runtime_bridge_composition.py:486`), **before** that short-circuit
decision is consulted. If an operator has authored a **corrupt org-tier
override** for `software-dev` — a family the project has registered and
that therefore has a perfectly good built-in `expected-artifacts.yaml`
available as a fallback — `load_manifest` still raises
`MalformedManifestError` at gather time, because C-006 treats a
present-but-corrupt org file as an operator-authored override that failed,
never as "fall back silently to the good built-in file underneath it."

**This is a deliberate hard-block, not an oversight.** The operator wrote
the org override expecting it to take effect; silently falling back to the
built-in manifest instead would mean the override is inert exactly when it
is broken — the worst possible time to discover that. The consequence is
that a single malformed org file for a registered built-in family now
blocks that *entire* family's guard evaluation, not just the custom-family
case #3412 originally targeted. This is covered by an explicit acceptance
scenario (spec.md Edge Cases, "Corrupt org override, registered built-in
family") and is intentional scope: `C-002` (the `blocking_artifact_names`
None-vs-`frozenset()` tri-state, #3729) and `C-003` (the guard-table
short-circuit itself) are both untouched — the raise happens *before either
is consulted*, so this ADR's change composes with both without mutating
them.

## Considered Options

* **A. Fix #3412 at the swallow site only, leave the four loaders
  unconsolidated.** Rejected: the fix would live in whichever loader the
  swallow site's caller happened to route through; the other three copies
  keep their own independent (and in one case, unvalidated) resolution
  paths, so the drift that caused #3412 in the first place remains
  structurally possible for the next behavioral change.
* **B. Consolidate the four loaders in `specify_cli`, leave the
  charter-tier caller unable to reach the shared authority.** Rejected:
  C-001 forbids charter importing specify_cli, so
  `mission_type_profiles.py` would still need its own copy — #3770 stays
  half-closed, and the worst-drifted (unvalidated) copy survives.
* **C. Relocate the authority into `charter.activation`; keep
  `ManifestRegistry` as a specify_cli-side thin delegate; shim the old
  import path (chosen).** Satisfies C-001 for every caller, leaves the
  smallest possible blast radius on `specify_cli`-owned state, and breaks
  no existing importer.
* **D. Canonicalize malformation onto `ManifestSchemaError` instead of a
  sibling `MalformedManifestError`.** Rejected during research (D2): message
  content is misleading for a parse fault, it would break built-in-tier
  symmetry with the already-shipped `1763bf2ae3` fix, and it does not avoid
  needing `MalformedManifestError` to exist in charter regardless (the
  built-in tier already raises it).

## Consequences

### Positive

* Exactly one production implementation of the org-tier/built-in-tier
  precedence + `model_validate` + error-wrap logic remains (SC-001); the
  three mirrors delegate to it, and the `from_yaml_file` orphan is deleted
  outright rather than routed (FR-013 — `cls(**data)` construction is a
  shape no `model_validate`-string gate can see, so deleting it is the only
  way to keep it dead).
* A YAML-syntax-broken org manifest for a custom mission family now fails
  loud via `MalformedManifestError`, distinct from absence, closing #3412 at
  its one true source instead of at a caller-specific swallow point.
* The charter-tier consumer (`_resolve_expected_artifacts_slot`) gains real
  schema validation it never had before this mission — a schema-invalid
  manifest at that call site now raises `ManifestSchemaError` instead of
  silently handing every downstream reader a bad raw mapping.
* No existing importer of `ManifestRegistry`, `load_manifest`,
  `ManifestSchemaError`, or `MalformedManifestError` from
  `specify_cli/dossier/manifest` breaks (the shim re-exports all four with
  preserved object identity).

### Negative

* A corrupt org-tier override for a *registered* built-in family (C-006)
  now hard-blocks that family's guard evaluation even though a good
  built-in fallback exists on disk — a strictly more blocking behavior than
  before this mission for that specific edge case. This is accepted as the
  honest outcome of fail-loud-on-override; the alternative (silent
  fallback) reopens the exact class of bug #3412 exists to close, one layer
  up.
* `charter.offering` and `charter.activation` now each hold one half of a
  conceptually paired sibling-error model
  (`MalformedManifestError`/`ManifestSchemaError`) rather than both living
  in one module — a direct consequence of the offering-must-not-import-activation
  direction constraint, documented here so a future reader does not "fix"
  the split by moving one beside the other.

### Neutral

* `ManifestRegistry`'s public API (`get_required_artifacts`,
  `get_blocking_artifacts`, `get_optional_artifacts`, `validate_manifest`,
  `clear_cache`, `load_manifest`) is unchanged from every caller's
  perspective; only `load_manifest`'s internals became a delegate call.

## Confirmation

* **NFR-001 (byte-compatible resolution) / NFR-002 (cache semantics
  preserved):** `test_configured_artifact_name`, the bridge-parity suites,
  and `TestManifestRegistryOrgTier`'s cache tests pass unchanged, exercised
  through the delegate.
* **FR-011 (non-vacuous arch-gate), companion to this ADR:**
  `tests/architectural/test_expected_artifacts_loader_gate.py` forbids bare
  `ExpectedArtifactManifest.model_validate(`/`ExpectedArtifactManifest(`
  outside `charter/activation/manifest_loader.py` and the model's own
  module; a self-mutation test proves the gate is not vacuous.
* **FR-009/FR-010 (launder-seam closure):** a positive regression asserts a
  malformed org manifest through the composed guard path propagates and is
  never degraded to `[]`.
* **C-006 (hard-block acceptance):** covered by an explicit RED-on-main
  acceptance scenario for the registered-built-in-family + corrupt-org-override
  case (spec.md Edge Cases).

## More Information

* Mission spec:
  `kitty-specs/expected-artifacts-loader-unification-01M1C9VQ/spec.md`
  (FR-001, FR-002, FR-003, FR-007, FR-008, and the full FR-001..FR-014 set).
* Research decisions D1-D9:
  `kitty-specs/expected-artifacts-loader-unification-01M1C9VQ/research.md`.
* Arch-gate contract:
  `kitty-specs/expected-artifacts-loader-unification-01M1C9VQ/contracts/arch-gate.md`.
* Relocated authority:
  [`src/charter/activation/manifest_loader.py`](../../../src/charter/activation/manifest_loader.py).
* Deprecation shim:
  [`src/specify_cli/dossier/manifest.py`](../../../src/specify_cli/dossier/manifest.py).
* `MalformedManifestError` home:
  [`src/charter/offering/missions/repository.py`](../../../src/charter/offering/missions/repository.py).
* Arch-gate enforcement:
  [`tests/architectural/test_expected_artifacts_loader_gate.py`](../../../tests/architectural/test_expected_artifacts_loader_gate.py).
* C-001 boundary enforcement:
  [`tests/architectural/test_charter_no_specify_cli_import.py`](../../../tests/architectural/test_charter_no_specify_cli_import.py).
* Prior built-in-tier fail-loud fix (symmetry baseline): commit `1763bf2ae3`.
