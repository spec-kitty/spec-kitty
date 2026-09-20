---
title: 06 — Unified Charter Bundle
description: 'The unified charter bundle architecture: the canonical manifest, its module and JSON Schema, inverted to a single-file authoritative charter.yaml model (#2773).'
doc_status: active
updated: '2026-07-18'
---
# 06 — Unified Charter Bundle

**Status**: v2.0.0 (introduced by mission `unified-charter-bundle-chokepoint-01KP5Q2G`, WP01,
as v1.0.0; inverted to the single-file model by mission
`consolidate-charter-bundle-01KXSYB9`, IC-02).
**Canonical manifest module**: [`src/charter/bundle.py`](../../src/charter/bundle.py)
**v2.0.0 contracts**: [`charter-yaml-schema.md`](../../kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/charter-yaml-schema.md), [`manifest-v2.md`](../../kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/manifest-v2.md)
**v1.0.0 JSON Schema (archived, superseded)**: [`kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/bundle-manifest.schema.yaml`](../../kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/bundle-manifest.schema.yaml)

## Purpose

Spec Kitty's governance surface is a small bundle of files rooted at
`.kittify/charter/`. The **unified charter bundle** contract is a single typed
manifest — `CharterBundleManifest` — that every reader, migration, and CLI
surface consults to know which files the bundle contains and how they relate.

This file is the narrative source of truth. The Pydantic model in
`src/charter/bundle.py` is the machine-readable authority. The two MUST stay
in sync; changes to either REQUIRE a `SCHEMA_VERSION` bump and an
accompanying migration.

## v2.0.0 scope: a single authoritative file

The v1.0.0 manifest (mission `unified-charter-bundle-chokepoint-01KP5Q2G`)
declared `charter.md` as the sole tracked source and three sync-derived files
(`governance.yaml`, `directives.yaml`, `metadata.yaml`) as its content-hash
input set. Mission `consolidate-charter-bundle-01KXSYB9` **inverted** that
model: the git-tracked, authorable, structured charter is now
`.kittify/charter/charter.yaml` — a single file nesting `governance`,
`directives`, `catalog`, activation, and `overrides`. `charter.md` remains
tracked as a curated companion, but nothing is derived from it any more and
it contributes nothing to the content-hash.

| Role              | Path                                     | Notes                                     |
| ----------------- | ----------------------------------------- | ------------------------------------------ |
| tracked            | `.kittify/charter/charter.md`             | Curated companion — human-authored, never parsed for policy |
| tracked + content-hash input | `.kittify/charter/charter.yaml` | The single authoritative structured charter |

`derived_files` is **empty** in v2.0.0 — nothing under `.kittify/charter/`
is generated-and-gitignored any more. `content_hash_files` is a field
**distinct** from `derived_files` (it always was; the historic 4-vs-3
file-count mismatch between `BUNDLE_CONTENT_HASH_FILES` and `derived_files`
made that distinction explicit) and holds exactly `[charter.yaml]`.
`gitignore_required_entries` is also empty — there is nothing left that the
bundle requires a project's `.gitignore` to exclude.

Full field-level guarantees live in the contracts:
[`charter-yaml-schema.md`](../../kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/charter-yaml-schema.md)
(the `charter.yaml` shape) and
[`manifest-v2.md`](../../kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/manifest-v2.md)
(the manifest diff from v1.0.0).

### Out of manifest scope

The following files live under `.kittify/charter/` but are **not** managed
by the manifest. They are produced by separate pipelines with their own
lifecycle and ownership:

- **`.kittify/charter/context-state.json`** — runtime state written by
  [`src/charter/activation/context.py`](../../src/charter/activation/context.py) inside
  `build_charter_context()`. This is lazy, per-invocation runtime
  state; it is not part of any reproducibility contract and is
  intentionally absent from the manifest.
- **`.kittify/charter/interview/answers.yaml`** — optional companion input
  for charter generation, owned by the interview surface.

The `bundle validate` CLI surfaces these as **informational warnings**
when present, never as failures. Operators can leave them in place, remove
them, or extend their `.gitignore` to match; the manifest does not forbid
them.

## Tracked vs. content-hash classification

The split exists so tooling can reason about the two classes separately:

- **Tracked files** MUST exist on disk, MUST be committed to git, and MUST
  appear in `git ls-files`. `charter.md` and `charter.yaml` are both tracked.
- **Content-hash files** are the input set for the bundle's freshness hash —
  a strict subset of tracked files (`[charter.yaml]` only). A tracked file
  need not be a content-hash input; `charter.md` is the example: tracked
  (git must have it) but excluded from the hash (it is not read for policy).

The manifest asserts the shape of this split via the Pydantic
`_validate` hook: no path may be in both the tracked and derived sets; every
`derivation_sources` key must be a derived path; every value must be a
tracked path. `charter.yaml` lives only in `tracked_files` (and
`content_hash_files`), never in `derived_files` — that disjointness
invariant is unchanged from v1.0.0 and MUST NOT be relaxed; keeping
"authored ≠ generated" meaningful is the point.

## Canonical-root contract

All readers resolve the canonical project root through a single helper —
`charter.resolution.resolve_canonical_repo_root()` — which correctly maps a
worktree path back to its main-checkout location. See
[`contracts/canonical-root-resolver.contract.md`](../../kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/canonical-root-resolver.contract.md)
for the full contract (unchanged by the v2.0.0 inversion).

## Config pointer resolution

The active `charter.yaml` is located through a single `charter:` pointer in
`.kittify/config.yaml` (default `.kittify/charter/charter.yaml`). The
resolver reads the pointer, then loads that file. The pointer may redirect
to a sibling, shared, or cross-project charter — a swap is a one-line config
change. `config.yaml` no longer carries the flat `activated_*` /
`mission_type_activations` keys itself; those moved to `charter.yaml`'s
root (flat, matching `src/charter/activation/packs/default.yaml`) as part of the same
inversion — `config.yaml` keeps only the pointer plus `org_packs`.

A `charter:` pointer to a missing or unreadable file fails loud; there is no
fallback to a legacy file.

## Content-hash semantics

The bundle's freshness signal is content-hash driven, not sync-driven:

1. `compute_bundle_content_hash` hashes exactly the files in
   `content_hash_files` (`charter.yaml`, declared order) via the unchanged
   per-file recipe (BOM-strip/CRLF normalization).
2. Write-side stampers (`write_pipeline.py`, `resynthesize_pipeline.py`) and
   the freshness reader (`charter_runtime/freshness/computer.py`) all route
   through that single recipe.
3. `charter.md`'s own SHA-256 hash — the v1.0.0 staleness mechanism compared
   against a `charter_hash` field — is retired. A hash of `charter.yaml`
   cannot live *inside* `charter.yaml` (chicken-egg), so `metadata` carries
   no self-referential hash; `metadata.bundle_schema_version` is the only
   field `versioning.py` reads from it.

`charter sync` / `ensure_charter_bundle_fresh()` are retained for
canonical-root resolution and back-compat call sites (the dashboard, the
bundle-migration upgrader, `charter context`), but no longer perform
extraction — every call is a no-op (`synced=False`, `files_written=[]`).

## Gitignore policy: MUST-INCLUDE, not exclusive

`gitignore_required_entries` is a **MUST-INCLUDE** set, currently empty in
v2.0.0 (nothing left under `.kittify/charter/` is required to be ignored).
The `.gitignore` at the project root:

- MUST contain every entry the manifest lists on its own line (none, today).
- MAY carry additional entries, including entries for the out-of-scope
  files enumerated above (`context-state.json`, provenance sidecars,
  synthesis manifests).

`bundle validate` only fails when a **required** entry is missing. It
does not enforce exclusivity and does not warn about additional
`.kittify/charter/*` entries.

## Schema versioning policy

`CANONICAL_MANIFEST.schema_version` carries an independent semver
(`2.0.0` as of the consolidate-charter-bundle inversion). The manifest
version is **not** tied to the `spec-kitty` package version.

- **Major bump** (e.g. `3.0.0`): breaking change to the manifest shape or
  required fields — e.g., adding a required key, renaming an existing
  key, removing the tracked/content-hash split. Requires a new migration
  module under `src/specify_cli/upgrade/migrations/`.
- **Minor bump** (e.g. `2.1.0`): scope expansion or additive optional fields.
  Requires a migration that extends the manifest and updates every
  reader site simultaneously.
- **Patch bump** (e.g. `2.0.1`): narrative or docstring fixes that do not
  change the shape or scope. No migration needed.

Future manifest versions ship with their own migration; there is **no
fallback** for older manifests at runtime (per C-001). A project that
lags a manifest bump must upgrade before it can use the bundle CLI. The
upgrade migration that folds the legacy `governance.yaml` /
`directives.yaml` / `metadata.yaml` / `references.yaml` quartet (plus
`config.yaml`'s `activated_*` keys) into `charter.yaml` and mints the
`charter:` pointer is the v1.0.0 → v2.0.0 migration path.

## charter.yaml precedence over charter.md

The charter has two surfaces with a strict precedence (operator decision, 2026-08-02):

- **`.kittify/charter/charter.yaml`** is the deterministic, schema-guarded **resolution
  authority** — it takes precedence for any resolving decision (governance policy,
  presence gates, activated sets).
- **`.kittify/charter/charter.md`** is a **secondary** read point that carries rationale
  and prose. It stays human-readable but **never overrides** `charter.yaml` and is never
  the authoritative resolving source.

When a surface must decide "does a charter exist / what does it say", resolve from
`charter.yaml` first and treat `charter.md` only as secondary rationale. Route reads
through the charter-layer authority (`charter.bundle` constants + the charter-yaml IO),
not re-derived path joins.

## The charter path-literal authority gate

`tests/architectural/test_charter_path_literal_authority.py` is an AST census gate: it
finds every hardcoded charter-path literal (`"charter.yaml"` / `"charter.md"` in a
`Path`-construction context) across `src/` and asserts the live-site count equals the
allowlist (plus a census ceiling). Adding one new `repo_root / "charter.yaml"`-style
literal reds it.

The correct fix is the **drain procedure, not an allowlist add**: route the path through
the canonical repo-root-relative `charter.bundle.CHARTER_YAML` / `CHARTER_MD` so no new
literal exists (e.g. `if not (repo_root / CHARTER_YAML).exists():`). The allowlist
reserves entries only for sites that genuinely cannot use the repo-root Path — for
example a bundle *writer* materializing into a caller-supplied `output_dir`. This gate
runs only in the full architectural battery, so a per-WP subset run will not surface it.

## Related contracts

- [`charter-yaml-schema.md`](../../kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/charter-yaml-schema.md) — the `charter.yaml` structured shape (v2.0.0).
- [`manifest-v2.md`](../../kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/manifest-v2.md) — the `CharterBundleManifest` v1.0.0 → v2.0.0 diff.
- [`migration-contract.md`](../../kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/migration-contract.md) — the fold migration that retires the legacy quartet.
- [`bundle-manifest.schema.yaml`](../../kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/bundle-manifest.schema.yaml) — archived v1.0.0 JSON Schema, superseded by the contracts above.
- [`bundle-validate-cli.contract.md`](../../kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/bundle-validate-cli.contract.md) — CLI contract for `spec-kitty charter bundle validate`.
- [`canonical-root-resolver.contract.md`](../../kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/canonical-root-resolver.contract.md) — canonical-root resolution (unchanged by the inversion).
- [`chokepoint.contract.md`](../../kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/chokepoint.contract.md) — reader chokepoint contract.
