---
title: Spec Kitty 3.2 — Archive & Migration Plan
description: 'Archive and migration plan for the Spec Kitty 3.2 docs mission (WP09 / FR-013): how legacy and version-tiered pages are archived and redirected in the refresh.'
doc_status: deprecated
updated: '2026-08-12'
related:
- docs/changelog/2x/index.md
- docs/migrations/from-charter-2x.md
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Working note for the 3.2 documentation mission `spec-kitty-3-2-docs-01KS4KSZ` (14/14 WPs done 2026-05-21); the docs are published (now 3.2.6). Content preserved as an audit-trail record.

# Spec Kitty 3.2 — Archive & Migration Plan

**Mission**: `spec-kitty-3-2-docs-01KS4KSZ`
**work package**: WP09 (FR-013)
**Authoring agent**: `curator-carla` (claude:opus-4-7)
**Status**: Planning artifact only. **No live page is moved in this WP.**

## Purpose

This document enumerates the **page-level dispositions** for every page tagged
`archival` or `migration` in `docs/development/3-2-page-inventory.yaml` (the
WP02 inventory). It is the planning surface for the bulk-edit path moves
declared in `kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/occurrence_map.yaml`
under `categories.filesystem_paths.rewrite`.

Execution of the moves is deferred to a future mission per `spec.md` Out of
Scope. This WP only produces the deterministic plan that downstream tooling
and reviewers can audit.

## Inputs

- **Inventory** (WP02): `docs/development/3-2-page-inventory.yaml` — 13
  archival rows (5 under `docs/1x/**`, 8 under `docs/2x/**`) and 12 migration
  rows (11 already in `docs/migration/`, 1 in `docs/guides/`).
- **occurrence map** (WP01): `kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/occurrence_map.yaml`
  — `filesystem_paths.rewrite` rules:
  - `docs/1x/` → `docs/archive/1x/`
  - `docs/2x/` → `docs/archive/2x/`
- **Banner regex** (FR-005 / NFR-002):
  `^>\s*(?:Archive notice|Migration note)\b` from
  `kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/contracts/version_leakage_check.md`.

## Disposition vocabulary

| Disposition | Meaning |
|-------------|---------|
| `move` | Relocate file under `docs/archive/<1x\|2x>/` per the occurrence-map rewrite, prepend Archive notice banner. |
| `banner-only` | Page already lives under `docs/migration/`; only prepend a Migration note banner — no rename. |
| `convert-to-migration-note` | Page lives outside `docs/migration/` but is tagged `migration`; move to `docs/migration/` and prepend Migration note banner. |
| `retire` | (Not used in this round.) Reserved for pages with no successor and no historical value. |

## Banner templates (literal text, banner-regex compliant)

Each banner is exactly one markdown line beginning with `>` followed by a space, matching the
contract regex `^>\s*(?:Archive notice|Migration note)\b`.

- **Archive notice (1.x)**:
  `> Archive notice: This page documents Spec Kitty 1.x and is preserved for historical context. See [`docs/migration/from-charter-2x.md`](../../../migrations/from-charter-2x.md) for current 3.2 guidance.`
- **Archive notice (2.x)**:
  `> Archive notice: This page documents Spec Kitty 2.x and is preserved for historical context. See [`docs/migration/from-charter-2x.md`](../../../migrations/from-charter-2x.md) for current 3.2 guidance.`
- **Migration note (2.x → 3.2)**:
  `> Migration note: This page guides users moving from Spec Kitty 2.x to 3.2.`
- **Migration note (2.1 → 2.x)** (used for the cutover checklist):
  `> Migration note: This page guides users moving from Spec Kitty 2.1 to 2.x (historical cutover).`
- **Migration note (early 3.x → 3.2)** (used for 3.x-era runbooks):
  `> Migration note: This page guides users moving from early Spec Kitty 3.x to 3.2.`

> Each banner is the **first** non-empty line of the rendered body (after
> frontmatter, if any) so the leakage check finds it within its 20-line window.

## Page-level disposition table

### Archival pages (13)

| Source path | Tag | Disposition | Target path | Banner | Notes |
|-------------|-----|-------------|-------------|--------|-------|
| `docs/1x/artifacts-and-commands.md` | archival | move | `docs/archive/1x/artifacts-and-commands.md` | Archive notice (1.x) | Internal anchors within the page remain stable; no external links into this page were found in the current `docs/` tree. |
| `docs/1x/branches-and-workspaces.md` | archival | move | `docs/archive/1x/branches-and-workspaces.md` | Archive notice (1.x) | No incoming links from `current` pages detected. |
| `docs/1x/index.md` | archival | move | `docs/archive/1x/index.md` | Archive notice (1.x) | Referenced by `docs/index.md:43` and `docs/development/3-2-version-taxonomy.md` as a path label (not a link). Path-label references are fine; live links would need redirecting. |
| `docs/1x/orchestration-and-api.md` | archival | move | `docs/archive/1x/orchestration-and-api.md` | Archive notice (1.x) | No incoming links from `current` pages detected. |
| `docs/1x/workflow.md` | archival | move | `docs/archive/1x/workflow.md` | Archive notice (1.x) | No incoming links from `current` pages detected. |
| `docs/2x/adr-coverage.md` | archival | move | `docs/archive/2x/adr-coverage.md` | Archive notice (2.x) | No incoming links from `current` pages detected. |
| `docs/2x/doctrine-and-charter.md` | archival | move | `docs/archive/2x/doctrine-and-charter.md` | Archive notice (2.x) | No incoming links from `current` pages detected. |
| `docs/2x/glossary-system.md` | archival | move | `docs/archive/2x/glossary-system.md` | Archive notice (2.x) | No incoming links from `current` pages detected. |
| `docs/2x/index.md` | archival | move | `docs/archive/2x/index.md` | Archive notice (2.x) | Referenced from `docs/context/index.md:81` as `[\`docs/2x/\`](../../../changelog/2x/index.md)` — **live link**. Execution mission must update this to `../archive/2x/index.md` (relative from `docs/context/index.md`). |
| `docs/2x/model-discipline-routing.md` | archival | move | `docs/archive/2x/model-discipline-routing.md` | Archive notice (2.x) | No incoming links from `current` pages detected. |
| `docs/2x/model-to-task_type.md` | archival | move | `docs/archive/2x/model-to-task_type.md` | Archive notice (2.x) | No incoming links from `current` pages detected. |
| `docs/2x/orchestration-and-api.md` | archival | move | `docs/archive/2x/orchestration-and-api.md` | Archive notice (2.x) | No incoming links from `current` pages detected. |
| `docs/2x/runtime-and-missions.md` | archival | move | `docs/archive/2x/runtime-and-missions.md` | Archive notice (2.x) | No incoming links from `current` pages detected. |

### Migration pages (12)

| Source path | Tag | Disposition | Target path | Banner | Notes |
|-------------|-----|-------------|-------------|--------|-------|
| `docs/guides/2-1-main-cutover-checklist.md` | migration | convert-to-migration-note | `docs/migration/2-1-main-cutover-checklist.md` | Migration note (2.1 → 2.x) | Inventory flag `MANUAL_REVIEW`: page lives in `docs/guides/` but documents a historical cutover and is tagged `migration`. Execution mission must move and update any `how-to` toc entries / cross-links. |
| `docs/migration/charter-ownership-consolidation.md` | migration | banner-only | _(in place)_ | Migration note (early 3.x → 3.2) | Already under `docs/migration/`; only prepend banner. |
| `docs/migration/cross-repo-e2e-gate.md` | migration | banner-only | _(in place)_ | Migration note (early 3.x → 3.2) | Already under `docs/migration/`; only prepend banner. |
| `docs/migration/doctrine-local-overlay-to-org-layer.md` | migration | banner-only | _(in place)_ | Migration note (early 3.x → 3.2) | Already under `docs/migration/`; only prepend banner. |
| `docs/migration/feature-flag-deprecation.md` | migration | banner-only | _(in place)_ | Migration note (early 3.x → 3.2) | Already under `docs/migration/`; only prepend banner. Page title references "feature flag" as a historical term; per Terminology Canon (charter §Terminology Canon) this is a historical migration runbook and may retain legacy wording marked as such. |
| `docs/migration/from-charter-2x.md` | migration | banner-only | _(in place)_ | Migration note (2.x → 3.2) | Already under `docs/migration/`; only prepend banner. This page is the canonical landing target for archive-banner cross-links. |
| `docs/migration/mission-id-canonical-identity.md` | migration | banner-only | _(in place)_ | Migration note (early 3.x → 3.2) | Already under `docs/migration/`; only prepend banner. |
| `docs/migration/mission-type-flag-deprecation.md` | migration | banner-only | _(in place)_ | Migration note (early 3.x → 3.2) | Already under `docs/migration/`; only prepend banner. |
| `docs/migration/retrospective-events-upstream.md` | migration | banner-only | _(in place)_ | Migration note (early 3.x → 3.2) | Already under `docs/migration/`; only prepend banner. |
| `docs/migration/shared-package-boundary-cutover.md` | migration | banner-only | _(in place)_ | Migration note (early 3.x → 3.2) | Already under `docs/migration/`; only prepend banner. |
| `docs/migration/teamspace-mission-state-920-closeout.md` | migration | banner-only | _(in place)_ | Migration note (early 3.x → 3.2) | Already under `docs/migration/`; only prepend banner. |
| `docs/migration/teamspace-mission-state-repair.md` | migration | banner-only | _(in place)_ | Migration note (early 3.x → 3.2) | Already under `docs/migration/`; only prepend banner. |

### Disposition counts

| Disposition | Count |
|-------------|-------|
| `move` | 13 |
| `banner-only` | 11 |
| `convert-to-migration-note` | 1 |
| `retire` | 0 |
| **Total** | **25** |

Coverage: 13 archival + 12 migration = 25 inventory rows, matches the page
table above.

## Known link redirects (collected during T027 grep)

The execution mission must update these live links when moves land. They are
the only live links into `docs/1x/**` or `docs/2x/**` found in the current
`docs/` tree:

| Source file | Line | Current link target | Updated link target |
|-------------|------|---------------------|---------------------|
| `docs/context/index.md` | 81 | `../2x/index.md` | `../archive/2x/index.md` |

Path-label mentions in `docs/index.md` (line 43) and
`docs/development/3-2-version-taxonomy.md` (lines 15, 90–91, 108–110, 281, 285,
307) are inline code labels, not markdown links. They remain accurate as
historical references to the **source** path; updating them would lie about
the inventory state at this snapshot. The execution mission can rewrite them
optionally if it also rewrites the version-taxonomy doc.

The `docs/development/3-2-navigation-plan.md` file references `docs/1x/toc.yml`
and `docs/2x/toc.yml` extensively — those updates are owned by the navigation
WPs, not by the page-disposition plan.

## Coverage cross-check (T028)

Every inventory row with `tag in {archival, migration}` is enumerated below,
each linked to its row in the table above by source path. This list is
generated from `docs/development/3-2-page-inventory.yaml` via:

```bash
python3 -c "
from ruamel.yaml import YAML
y = YAML(typ='safe')
rows = y.load(open('docs/development/3-2-page-inventory.yaml'))
for r in rows:
    if r['tag'] in ('archival','migration'):
        print(r['tag'], r['path'])
"
```

### archival (13)

- [x] `docs/1x/artifacts-and-commands.md`
- [x] `docs/1x/branches-and-workspaces.md`
- [x] `docs/1x/index.md`
- [x] `docs/1x/orchestration-and-api.md`
- [x] `docs/1x/workflow.md`
- [x] `docs/2x/adr-coverage.md`
- [x] `docs/2x/doctrine-and-charter.md`
- [x] `docs/2x/glossary-system.md`
- [x] `docs/2x/index.md`
- [x] `docs/2x/model-discipline-routing.md`
- [x] `docs/2x/model-to-task_type.md`
- [x] `docs/2x/orchestration-and-api.md`
- [x] `docs/2x/runtime-and-missions.md`

### migration (12)

- [x] `docs/guides/2-1-main-cutover-checklist.md`
- [x] `docs/migration/charter-ownership-consolidation.md`
- [x] `docs/migration/cross-repo-e2e-gate.md`
- [x] `docs/migration/doctrine-local-overlay-to-org-layer.md`
- [x] `docs/migration/feature-flag-deprecation.md`
- [x] `docs/migration/from-charter-2x.md`
- [x] `docs/migration/mission-id-canonical-identity.md`
- [x] `docs/migration/mission-type-flag-deprecation.md`
- [x] `docs/migration/retrospective-events-upstream.md`
- [x] `docs/migration/shared-package-boundary-cutover.md`
- [x] `docs/migration/teamspace-mission-state-920-closeout.md`
- [x] `docs/migration/teamspace-mission-state-repair.md`

Total: **25 / 25** inventory rows covered.

## Bulk-edit compliance

WP09 is an active executor under `occurrence_map.yaml`
(`filesystem_paths.rewrite` declares `executor_wp: WP09` for both the
`docs/1x/**` and `docs/2x/**` rewrites; `user_facing_strings.review` declares
`executor_wp: WP09` for archive banners on `docs/archive/1x/**` and
`docs/archive/2x/**`).

This subsection confirms each guardrail invariant:

1. **Path-rewrite alignment.** Every `move` target in the table above maps
   `docs/1x/<rel>` → `docs/archive/1x/<rel>` or `docs/2x/<rel>` →
   `docs/archive/2x/<rel>`, exactly matching the `from_pattern` →
   `to_pattern` rule in `occurrence_map.yaml`. No move crosses
   versions. No move lands outside `docs/archive/<1x|2x>/`.

2. **Convert-to-migration-note alignment.** The single
   `convert-to-migration-note` row (`docs/guides/2-1-main-cutover-checklist.md`)
   targets `docs/migration/2-1-main-cutover-checklist.md`, satisfying the WP09
   reviewer rule "every `convert-to-migration-note` target lands under
   `docs/migration/`."

3. **Banner regex compliance.** Each banner template above begins with a
   literal `> Archive notice:` or `> Migration note:` and matches the regex
   `^>\s*(?:Archive notice|Migration note)\b` declared in
   `contracts/version_leakage_check.md`. The leakage check scans the first 20
   non-empty lines of the rendered body, so banners will be placed as the
   first body line below frontmatter (where present) or as the first line of
   the page (where no frontmatter exists).

4. **No live filesystem moves performed in this WP.** This file is the only
   file added by WP09. `git status` after this commit shows a single
   added file: `docs/development/3-2-archive-migration-plan.md`. Live moves
   are deferred to a future mission per `spec.md` Out of Scope; this plan is
   the deliverable.

5. **Owned-files boundary.** WP09's `owned_files` lists exactly
   `docs/development/3-2-archive-migration-plan.md`. No other files are
   modified by this WP.

## Out-of-scope (deferred to execution mission)

- Actual `git mv` of `docs/1x/**` and `docs/2x/**` into `docs/archive/`.
- Banner injection into each moved file.
- Toc updates in `docs/toc.yml`, `docs/1x/toc.yml`, `docs/2x/toc.yml` (owned
  by the navigation WPs).
- Link rewrites in `docs/context/index.md` and any path-label updates in
  `docs/index.md` / `docs/development/3-2-version-taxonomy.md`.
- Frontmatter reconciliation between moved pages and the inventory
  manifest (the leakage check `LEAK-FRONTMATTER-MISMATCH` rule will surface
  any drift after the moves land).
