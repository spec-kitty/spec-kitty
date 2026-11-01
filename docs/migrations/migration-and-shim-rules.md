---
title: Migration and Shim Ownership Rules
description: The migration and shim ownership rulebook governing bundle/runtime migrations and back-compat shims during package extraction, which every extraction mission must cite.
doc_status: active
updated: '2026-11-01'
---
# Migration and Shim Ownership Rules

*`docs/migrations/migration-and-shim-rules.md`*
*Mission: migration-shim-ownership-rules-01KPDYDW (#615)*
*See also: [05_ownership_map.md](../architecture/05_ownership_map.md) (slice inventory)*

---

## 1. Scope and Purpose

This rulebook governs how spec-kitty handles two related but distinct concerns during package extraction: **bundle and runtime migrations** (code that transforms project state when a new spec-kitty version is installed) and **compatibility shims** (thin Python re-export modules that preserve an old import path while the canonical location moves). It exists because mission #615 identified that ad-hoc handling of these concerns had produced undocumented shims, unclear removal timelines, and no CI gate to catch newly introduced shims that bypassed the registry.

Every extraction mission — #612, #613, #614, and any future slice extraction — must cite this document in its implementation plan and follow the rule families described here. The CI enforcement surfaces are `spec-kitty doctor shim-registry` (exit codes 0/1/2) and the architectural pytest suite (`tests/architectural/`).

Doctrine versioning for these artifacts (schema-version extension to doctrine artifacts themselves) is tracked separately under #461 Phase 7 and is **not** implemented by this mission.

---

## 2. Rule Family (a) — Project Schema and Version Gating

Spec-kitty's `.kittify/` artifacts and mission bundles carry a `schema-version` field. The current contract is:

- **`.kittify/` artifacts**: Schema version is defined per-artifact type in `src/specify_cli/missions/*/mission.yaml`. A migration module must check the schema version of the artifact it is upgrading and refuse to apply if the version is outside its supported range, raising a clear error that names the installed spec-kitty version and the artifact's schema version.
- **Mission bundles**: `kitty-specs/<mission>/meta.json` carries a `schema_version` field. Tools that consume mission bundles should reject bundles with an unknown major schema version and warn on unknown minor versions.

The runtime reads the project version from `pyproject.toml` via `tomllib` (`[project].version`). This value is used exclusively for semver comparison against `removal_target_release` entries in the shim registry. Pre-release suffixes (e.g., `3.3.0a1`) are handled by `packaging.version.Version`, which correctly treats `3.3.0a1 < 3.3.0`.

**Cross-reference**: #461 Phase 7 plans to extend schema-version gating to doctrine artifacts (directives, paradigms, procedures). That work is not in scope here; this rule family covers only `.kittify/` artifacts and mission bundles.

---

## 3. Rule Family (b) — Bundle and Runtime Migration Authoring Contract

A migration module lives under `src/specify_cli/upgrade/migrations/` and is named `m_<version_slug>_<slug>.py` (e.g., `m_0_9_1_complete_lane_migration.py`). Each module must export a class that inherits from `BaseMigration` and implements a single `apply(project_path: Path, dry_run: bool = False) -> None` method.

**Idempotency requirement**: `apply()` must be safe to call multiple times on the same project. Use existence checks (`if not target.exists()`) or content-hash comparisons rather than unconditional writes. A failed partial migration followed by a retry must produce the same final state as a successful first run.

**Dry-run contract**: When `dry_run=True`, `apply()` must not write any files, run any shell commands, or emit any git commits. It should report what it *would* do to stdout (using `rich` where appropriate). The dry-run path must be exercised by at least one test.

**Detection reachability**: `MigrationRunner` calls `detect()` before `can_apply()` and
`apply()`, so a write-path safety guard is end-to-end reachable only when the same
unsafe path cannot make `detect()` return `False` first. `Path.exists()` follows
symlinks and returns `False` for a dangling symlink; a `detect()` existence check
can therefore skip the migration before a later `can_apply()`/`apply()` guard runs.
Close unsafe reads in both the detection and write paths, and record that
reachability dependency in the migration PR's blast-radius note.

**Test expectations**: Each migration module must have a corresponding test in `tests/specify_cli/upgrade/migrations/` that:
1. Creates a synthetic project directory via `tmp_path`.
2. Calls `apply(project_path)` once (normal run).
3. Asserts the expected files/changes are present.
4. Calls `apply(project_path)` a second time (idempotency check).
5. Asserts the project state is unchanged after the second call.

**Naming conventions**: The migration class must be named `Migration` (singular). The module-level constant `MIGRATION_ID` must be a string matching the filename without the `.py` extension. The migration registry in `src/specify_cli/upgrade/registry.py` discovers migrations by scanning this constant.

**How a migration entry-point is registered and invoked**: Migrations are discovered automatically by `MigrationRegistry.discover()`, which imports all `m_*.py` modules under the migrations directory and collects their `Migration` classes. The `spec-kitty upgrade` command invokes `MigrationRegistry.run_pending(project_path)`, which filters to migrations with a version greater than the project's last-applied migration version (stored in `.kittify/migration-state.json`).

---

## 4. Rule Family (c) — Compatibility Shim Lifecycle

A compatibility shim is a Python module at the **old** import path that re-exports all public symbols from the **new canonical** package. Its sole purpose is to give downstream callers a deprecation window before the old path is removed.

### When to introduce a shim

A shim is required when all three conditions hold:
1. A package is being relocated (old path `specify_cli.X` → new path `X`).
2. The old path was part of a documented or discoverable public API.
3. At least one external caller (outside the `specify_cli` package itself) imports from the old path.

If condition 3 is not met — that is, if all callers are internal and can be migrated atomically — no shim is needed. The removal of the old path is then a pure refactor with no deprecation window required. The shim registry records this as the "no-shim baseline case" (see Section 7).

### Mandatory shim module shape

Every shim must include these six attributes, with no omissions:

```python
"""Compatibility shim — re-exports from <canonical_package>.

Deprecated: import from <canonical_package> instead. Scheduled for removal in <X.Y.Z>.
"""
from __future__ import annotations

import warnings

from <canonical_package> import *  # noqa: F401, F403
from <canonical_package> import __all__  # if canonical defines __all__

__deprecated__ = True
__canonical_import__ = "<canonical_package>"
__removal_release__ = "<X.Y.Z>"
__deprecation_message__ = (
    "specify_cli.<legacy_name> is deprecated; import from <canonical_package>. "
    "Scheduled for removal in <X.Y.Z>."
)

warnings.warn(__deprecation_message__, DeprecationWarning, stacklevel=2)
```

The `warnings.warn(..., stacklevel=2)` call executes at import time so that any import of the shim module immediately surfaces the deprecation to the calling code's stack frame (not the shim's own frame).

Lazy PEP 562 shims used to avoid eager CLI-startup imports are exempt from the eager re-export and eager `__all__` lines above. They must still expose `__deprecated__`, `__canonical_import__`, `__removal_release__`, and `__deprecation_message__`, and warn on the first import or attribute access.

### Deprecation window

A shim must remain in place for **at least one full minor release** after the canonical path is available. The `removal_target_release` in the registry must be at least one minor version ahead of the release in which the shim was introduced (e.g., introduced in `3.2.0` → removal no earlier than `3.3.0`).

Extension beyond one release is permitted when external consumers have been notified but need additional time. In that case, the registry entry must include `extension_rationale` with a non-empty explanation (e.g., "downstream consumer org X requires migration window per support contract until 2026-Q3"). The `grandfathered: true` flag is reserved for shims that existed before this rulebook and for which a normal removal timeline cannot be applied; all new shims introduced after this mission must set `grandfathered: false`.

---

## 5. Rule Family (d) — Removal Plans and Registry Contract

### Registry schema

The registry at `docs/migrations/shim-registry.yaml` is the authoritative list of all known compatibility shims. Its schema is defined in `kitty-specs/migration-shim-ownership-rules-01KPDYDW/contracts/shim-registry-schema.yaml`. Each entry requires:

| Field | Type | Description |
|-------|------|-------------|
| `legacy_path` | string | Dotted Python import path of the shim (e.g., `specify_cli.charter`) |
| `canonical_import` | string or list | The new canonical import path(s) |
| `introduced_in_release` | semver string | Version when the shim was first introduced |
| `removal_target_release` | semver string | Version when the shim will be removed; must be ≥ introduced_in_release |
| `tracker_issue` | string | GitHub issue reference (`#NNN` or URL) tracking the removal |
| `grandfathered` | boolean | `true` only for pre-rulebook shims; new entries must be `false` |
| `extension_rationale` | string (optional) | Required if removal window extends past one minor release |
| `notes` | string (optional) | Free-form notes for reviewers |

### How to add a new entry

1. Copy the shim template from Section 4 into the appropriate `src/<dotted legacy path>.py` or `src/<dotted legacy path>/__init__.py` (including top-level modules).
2. Add an entry to `docs/migrations/shim-registry.yaml` with all required fields.
3. Open a tracker issue for the removal and record its reference in `tracker_issue`.
4. Run `spec-kitty doctor shim-registry` and confirm it exits 0 with the new entry showing `pending` status.
5. Follow the quickstart at `kitty-specs/migration-shim-ownership-rules-01KPDYDW/quickstart.md` for a step-by-step checklist.

### Removal PR contract

When `removal_target_release` is reached, the removal PR must:

1. **Delete** the shim module file (`src/specify_cli/<legacy_name>.py` or `src/specify_cli/<legacy_name>/__init__.py`).
2. **Update** the registry entry — either remove it entirely or mark it with a `removed_in_release` note (convention TBD by the removing engineer; the entry may be deleted once CI passes).
3. **Add** a changelog fragment, `docs/changelog/unreleased/<pr>.breaking.md`, that names the removal and the release version.
4. **Close** the tracker issue referenced in `tracker_issue`.
5. **Confirm** CI passes: `spec-kitty doctor shim-registry` must exit 0 after the removal.

---

## 6. CI Enforcement

### `spec-kitty doctor shim-registry`

This command reads `docs/migrations/shim-registry.yaml`, loads `[project].version` from `pyproject.toml`, and classifies each registered shim:

| Exit code | Meaning |
|-----------|---------|
| 0 | All entries are `pending`, `grandfathered`, or `removed` — no action required |
| 1 | One or more entries are `overdue` (current project version ≥ `removal_target_release` and shim file still present) |
| 2 | Configuration error — `pyproject.toml` or `shim-registry.yaml` is missing or malformed |

Statuses:
- **pending**: `removal_target_release` > current version; shim file exists — normal lifecycle
- **overdue**: `removal_target_release` ≤ current version; shim file still exists — removal is due
- **grandfathered**: `grandfathered: true` — never classified as overdue regardless of version
- **removed**: shim file no longer exists on disk — entry is historical

### `tests/architectural/test_unregistered_shim_scanner.py`

This test walks `src/` using Python's `ast` module, detects any module containing `__deprecated__ = True`, and asserts that every detected path appears in the registry. The test fails if a shim module exists on disk but has no registry entry. This prevents engineers from introducing a shim without registering it.

The scanner detects both `__deprecated__ = True` (assignment) and `__deprecated__: bool = True` (annotated assignment) forms.

### `tests/architectural/test_shim_registry_schema.py`

This test loads the live `docs/migrations/shim-registry.yaml` and runs it through `validate_registry()`. It also exercises the validator against known-bad fixtures (missing required fields, wrong types, bad semver, invalid tracker references, `removal_target_release < introduced_in_release`) to confirm that `RegistrySchemaError` is raised with a field-specific message for each violation.

---

## 7. Worked Example — Charter Mission

Mission `charter-ownership-consolidation-and-neutrality-hardening-01KPD880` (GitHub #611, #653) is the reference case for applying this rulebook.

**Rule family (a) — Schema and version gating**: The charter mission performed a bulk-edit import-path migration from `specify_cli.charter.*` to `charter.*`. Schema version fields in `.kittify/` artifacts were not altered by this mission; the mission used the existing schema version contract without modification.

**Rule family (b) — Migration authoring contract**: The charter mission produced occurrence maps and bulk-edit tooling to migrate callers from `specify_cli.charter.*` to `charter.*`. Internal callers (within `specify_cli`) were migrated atomically as part of the bulk edit. No migration module in `src/specify_cli/upgrade/migrations/` was required for this operation because it was a same-release refactor rather than a schema upgrade.

**Rule family (c) — Compatibility shim lifecycle (no-shim baseline case)**: The `src/specify_cli/charter/` directory was audited before this mission. At mission start (2026-04-19), `src/specify_cli/charter/__init__.py` did not exist — the directory contained only `__pycache__/`. This confirms that the canonical move from `specify_cli.charter.*` to `charter.*` had **no external importers** at extraction time; all callers were internal and were migrated atomically.

Consequently, **no shim was introduced** for the charter migration. This is a valid exception to rule family (c): the shim precondition (external callers) was not met. The registry records this by remaining empty at mission-615 start, with a comment noting the zero-shim baseline.

The charter mission therefore demonstrates rule family (c) by *not* introducing a shim, and documents this decision explicitly rather than silently omitting the step. Any future extraction mission that similarly has no external callers should follow this precedent and add a comment in its implementation notes stating: *"No compatibility shim introduced — all callers were internal and migrated atomically."*

**Rule family (d) — Removal plans and registry contract**: Because no shim was introduced, no registry entry was created for `specify_cli.charter`. The registry baseline remains `shims: []`. Future extraction missions that *do* introduce shims (e.g., if a public-facing package with documented external callers is relocated) will add entries following the schema in Section 5.

---

## 8. Reference Index

| Artifact | Purpose |
|----------|---------|
| `docs/architecture/05_ownership_map.md` | Slice-by-slice ownership map (mission #610) |
| `docs/migrations/shim-registry.yaml` | Machine-readable compatibility shim registry (this mission) |
| `kitty-specs/migration-shim-ownership-rules-01KPDYDW/contracts/shim-registry-schema.yaml` | Authoritative YAML schema for registry entries |
| `kitty-specs/migration-shim-ownership-rules-01KPDYDW/quickstart.md` | 5-step registration recipe for new shims |
| `src/specify_cli/compat/registry.py` | Python loader and validator for `shim-registry.yaml` |
| `src/specify_cli/compat/doctor.py` | Classification engine powering `doctor shim-registry` |
| `tests/architectural/test_shim_registry_schema.py` | Schema validation tests (FR-011) |
| `tests/architectural/test_unregistered_shim_scanner.py` | Unregistered shim detector (FR-010) |
| `tests/doctor/test_shim_registry.py` | CLI integration tests for `doctor shim-registry` (FR-009) |
| #461 Phase 7 | Planned doctrine-versioning extension (cross-ref only, not implemented here) |
| #615 | Tracker issue for this mission |
