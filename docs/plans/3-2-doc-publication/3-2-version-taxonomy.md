---
title: 3.2 Version Taxonomy
description: Source of truth for how every page under docs/, architecture/, and root README.md is classified by version relevance for the 3.2 documentation refresh.
doc_status: active
updated: '2026-09-30'
---
# 3.2 Version Taxonomy

> **Status note (2026-09-30): pending an operator ruling.** This taxonomy is anchored to 3.2:
> it defines `current` as "pages that describe 3.2 behaviour", while the active cycle is now
> 4.0.0. The generated inventory (`docs/development/3-2-page-inventory.yaml`) still emits a
> `tag` per page from these definitions. The open decision is whether to make this page
> version-neutral (for example, `current` = the latest released line) or to retire it along
> with the `tag` field. Until then, read "3.2" below as "the release line this taxonomy was
> written for".

> Source of truth for how every page under `docs/`, `architecture/`, and the
> root `README.md` is classified for the 3.2 documentation refresh.
>
> **Mission:** `spec-kitty-3-2-docs-01KS4KSZ` · **Requirement:** FR-001 ·
> **Constraint:** C-008 (bulk-edit guardrail required before frontmatter rollout)

This document defines the **five-tag version-relevance taxonomy** that the
3.2 docs rollout uses as its single classification axis. Every docs page
that appears in `docs/development/3-2-page-inventory.yaml` maps to **exactly
one** tag from this list. The taxonomy is the canonical surface for:

- The version-tag frontmatter rollout (workstream A2 / WP02).
- The archive/migration moves for `docs/1x/**` and `docs/2x/**` (workstream
  C / WP09).
- The version-leakage validation check
  (`contracts/version_leakage_check.md`, FR-005 / NFR-002).
- The navigation plan that separates 1.x archive, 2.x archive, 3.1 supported,
  3.2 current, and migration content (FR-004).

The canonical enum lives at `kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/data-model.md`
§"VersionTag (enum)". The taxonomy below is the **operator-facing**
description of that enum.

---

## The five tags

The terms below are reproduced verbatim from
[`spec.md`](../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/spec.md) §"Domain
Language" so that this document and the spec stay in lock-step.

### `current`

**Definition (verbatim from spec.md Domain Language):**
*Version-relevance tag for pages that describe 3.2 behaviour.*

**Avoid:** "latest", "the new docs".

**Adoption rule.** Apply `current` to every page that documents 3.2 surface
area — installed CLI behaviour, charter doctrine as it ships in 3.2, the
3.2 mission workflow, harness pages that match the 3.2 generated tree, and
the 3.2 reference. New pages authored during this mission default to
`current`.

**Banner requirement.** None. `current` pages must **not** carry an archive
or migration banner; the version-leakage check
(`contracts/version_leakage_check.md`, rule `LEAK-CURRENT-LINKS-ARCHIVAL`)
flags `current` pages that link to `archival` pages without a migration
banner on the destination.

**Example pages.**
- `docs/context/charter-overview.md`
- `docs/context/index.md`
- `docs/guides/install-macos.md` (target page set by FR-017 once landed)

### `supported`

**Definition (verbatim from spec.md Domain Language):**
*Version-relevance tag for 3.1-relevant pages still useful but not
3.2-complete.*

**Avoid:** "old current", "previous-but-ok".

**Adoption rule.** Apply `supported` to a 3.1-era page that still describes
behaviour the 3.2 user is likely to invoke unchanged, but which has not yet
been re-audited and rewritten for 3.2 completeness. The plan phase decides
whether 3.1 content gets a separate nav group or folds into 3.2 as migration
notes (deferred decision `01KS4KTGTN4DBE60JFWKEA2FJB`); until that lands,
`supported` is the holding tag for those pages.

**Banner requirement.** None required by the leakage check, but `supported`
pages **should** carry a short header noting "Last audited against 3.1 — see
the 3.2 migration note when behaviour differs." A `current`-tagged page may
link to a `supported`-tagged page without triggering the leakage check.

**Example pages.**
- Any page that today lives under `docs/architecture/` or `docs/api/`
  describing 3.1 surface still in 3.2 without revision (assigned by the
  WP02 page inventory).

### `archival`

**Definition (verbatim from spec.md Domain Language):**
*Version-relevance tag for 1.x or 2.x material kept for historical record.*

**Avoid:** "deprecated docs", "legacy" (without qualification).

**Adoption rule.** Apply `archival` to every page under `docs/1x/**` and
`docs/2x/**`. Per C-004, these directories move to `docs/archive/1x/**` and
`docs/archive/2x/**` as part of WP09; WP01 only declares the mapping in
`occurrence_map.yaml`.

**Banner requirement.** **Mandatory.** Each `archival` page must include an
archive banner within the first 20 non-empty lines that matches the regex
defined in
[`contracts/version_leakage_check.md`](../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/contracts/version_leakage_check.md):

```
^>\s*(?:Archive notice|Migration note)\b
```

Pages missing the banner produce the `LEAK-MISSING-BANNER` finding at
publication gate.

**Example pages.**
- `docs/1x/index.md`
- `docs/1x/artifacts-and-commands.md`
- `docs/2x/glossary-system.md`

### `migration`

**Definition (verbatim from spec.md Domain Language):**
*Version-relevance tag for pages explaining how to move from an earlier
version to 3.2.*

**Avoid:** "transition guide" (without tag).

**Adoption rule.** Apply `migration` to a page whose primary purpose is to
walk a reader from an earlier-version state to a 3.2 state. Pages in
`docs/migration/**` are the canonical home; a `current` page may also be
re-tagged `migration` if it consists primarily of upgrade instructions.

**Banner requirement.** **Mandatory.** Same banner regex as `archival`:

```
^>\s*(?:Archive notice|Migration note)\b
```

A `current` page **may** link to a `migration` page without triggering
`LEAK-CURRENT-LINKS-ARCHIVAL`; the banner on the migration page is what makes
the cross-link legal.

**Example pages.**
- `docs/migration/from-charter-2x.md`
- `docs/migration/charter-ownership-consolidation.md`
- `docs/migration/feature-flag-deprecation.md`

### `internal`

**Definition (verbatim from spec.md Domain Language):**
*Version-relevance tag for development-only or non-public material.*

**Avoid:** "dev notes", "private".

**Adoption rule.** Apply `internal` to every page under
`docs/development/**` and `architecture/**` — material aimed at maintainers
and contributors, not at end users running Spec Kitty. `internal` pages are
**excluded** from the public 3.2 navigation; they live in the repo and are
discoverable to anyone reading the source, but they are not part of the
published docs site index.

**Banner requirement.** None. The leakage check ignores `internal` pages on
both sides of a link: a `current` page may link to an `internal` page (it
counts as a developer-reference link, not a version leak), and an `internal`
page may link anywhere.

**Example pages.**
- `docs/development/3-2-version-taxonomy.md` (this file)
- `docs/development/local-overrides.md`
- `docs/adr/3.x/2026-04-25-1-shared-package-boundary.md`

---

## Reference: `VersionTag` enum

The canonical Python enum lives in
[`data-model.md`](../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/data-model.md)
§"VersionTag (enum)":

```python
class VersionTag(StrEnum):
    CURRENT = "current"        # 3.2-current
    SUPPORTED = "supported"    # 3.1-relevant, not 3.2-complete
    ARCHIVAL = "archival"      # 1.x or 2.x
    MIGRATION = "migration"    # version transition guidance
    INTERNAL = "internal"      # dev-only / non-public
```

The serialized form (the string value of each enum member) is what appears
in page frontmatter and in `docs/development/3-2-page-inventory.yaml`.

## Reference: `PageInventoryEntry` schema

Each page's tag is recorded in `docs/development/3-2-page-inventory.yaml` as
a `PageInventoryEntry` row — see
[`data-model.md`](../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/data-model.md)
§"PageInventoryEntry". Key invariants relevant to this taxonomy:

- Every inventoried page maps to **exactly one** `VersionTag`.
- `tag == archival` implies `current_target == false`.
- `tag == current` implies `current_target == true`.
- `tag == migration` implies the file body contains the migration banner
  regex from `contracts/version_leakage_check.md`.
- Pages tagged `internal` are excluded from `current_target` validation
  entirely (they do not appear in 3.2-current nav).

These invariants are enforced by the inventory validator that WP02
introduces (per FR-002) and by the leakage check at publication time (per
FR-005 / NFR-002).

---

## How filtering works

Adapted from research note **R-006 — Version-tag mechanism** in
[`research.md`](../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/research.md).

The 3.2 docs apply version filtering through a **two-source cross-check**,
not a single mechanism:

1. **YAML frontmatter on each page** is authoritative for what the page
   claims it is:

   ```yaml
   ---
   version_tag: current
   ---
   ```

   The frontmatter is what the version-leakage check reads at publication
   time to decide whether a link from page A to page B is legal.

2. **The page-inventory manifest** at
   `docs/development/3-2-page-inventory.yaml` is the source of truth for
   what each page *should* be tagged and where it should sit in nav. The
   inventory is one `PageInventoryEntry` row per page.

3. **The leakage check cross-references the two.** If a page's frontmatter
   says `version_tag: current` but the inventory row says `archival`, the
   check fails with `LEAK-FRONTMATTER-INVENTORY-DRIFT`. If a page tagged
   `archival` or `migration` is missing the banner from the leakage-check
   contract, it fails with `LEAK-MISSING-BANNER`. If a `current` page links
   to an `archival` page and the destination has no migration banner, it
   fails with `LEAK-CURRENT-LINKS-ARCHIVAL`.

4. **Navigation grouping is independent of the tag.** Where the site
   generator does not surface frontmatter natively, the navigation plan
   (FR-004) adds explicit nav groups for "3.2 current", "3.1 supported",
   "Archive (2.x)", "Archive (1.x)", and "Migration". The tag stays the
   single classification axis; the nav grouping is a presentation layer
   over it.

This two-source design means the bulk-edit guardrail for the frontmatter
rollout (WP02) and the bulk move of 1.x/2.x pages (WP09) can run
independently: the inventory rows can be authored before the frontmatter
lands on every page (the `deferred-frontmatter` exception list in the
inventory covers the gap), and the leakage check still gates publication.

---

## Annex: docs/ inventory snapshot (2026-05-21)

Read-only survey of every markdown / YAML / JSON file under `docs/`,
`architecture/`, and the root `README.md` at base commit
`6e81c2b186131633253426a3485ebfeebc343d8b`. Captured by running:

```bash
git ls-files docs/ architecture/ README.md \
  | grep -E '\.(md|yml|yaml|json)$' \
  | sort > /tmp/wp01-docs-survey.txt
```

**Total inventoried files:** 413

**Bucket counts by top-level directory** (sorted by file count, descending):

| Bucket | Count | Notes |
|--------|------:|-------|
| `architecture/2.x/` | 110 | Internal — 2.x architectural intent |
| `docs/adr/3.x/` | 67 | Internal — Architecture Decision Records |
| `docs/guides/` | 39 | Mostly `current` / `supported` (WP02 will tag) |
| `docs/development/` | 32 | Internal — maintainer-facing |
| `architecture/3.x/` | 27 | Internal — 3.x architectural intent |
| `architecture/1.x/` | 18 | Internal — historical architectural intent |
| `docs/api/` | 17 | Mostly `current` (CLI reference + harness reference) |
| `docs/architecture/` | 16 | Mostly `current` / `supported` |
| `docs/context/audience/` | 13 | Internal — audience-targeted architecture notes |
| `docs/migration/` | 12 | All `migration` |
| `docs/2x/` | 9 | All `archival` — move to `docs/archive/2x/` per WP09 |
| `docs/` (root files) | 8 | Mostly index pages and top-level explanation |
| `docs/guides/` | 8 | Mostly `current` (3.2 first-mission tutorial lives here) |
| `docs/plans/engineering-notes/architecture-audits/` | 7 | Internal — audit records |
| `docs/1x/` | 6 | All `archival` — move to `docs/archive/1x/` per WP09 |
| `architecture/` (root files) | 5 | Internal — index pages |
| `docs/architecture/calibration/` | 5 | Internal — calibration notes |
| `docs/architecture/` | 4 | Internal mirror of architecture intent |
| `docs/context/` | 4 | All `current` |
| `docs/doctrine/` | 2 | `current` — doctrine surface |
| `docs/architecture/assessments/` | 1 | Internal |
| `docs/operations/` | 1 | `current` |
| `README.md` (root) | 1 | `current` |

**Sanity totals.** `docs/**` accounts for 159 files;
`architecture/**` accounts for 253 files; the root `README.md` accounts for
1 file. The sum (412) matches the line count of the survey output (less the
`architecture/glossary/` residual reconciled away per mission 01KTNWFC).

**Provisional tag-distribution forecast** (subject to per-page review during
WP02):

| Tag | Expected count | Source |
|-----|---------------:|--------|
| `current` | ~85 | `docs/context/` + `docs/guides/` + `docs/guides/` + `docs/api/` + `docs/doctrine/` + `docs/operations/` + root `README.md` + the 3.2-relevant subset of `docs/architecture/` |
| `supported` | ~25 | Remaining 3.1-era pages in `docs/architecture/` and `docs/api/` pending re-audit |
| `archival` | 15 | `docs/1x/` (6) + `docs/2x/` (9) |
| `migration` | 12 | `docs/migration/` |
| `internal` | 276 | All of `architecture/**` (254) + all of `docs/development/` (32) + `docs/architecture/` (4) — minor double-counting reconciled during inventory |

The exact counts land in `docs/development/3-2-page-inventory.yaml` once
WP02 runs the bulk-edit guardrail gate. The forecast here exists so the
WP02 implementer has a known target order-of-magnitude before they start
classifying.

**No files were modified by this survey.** Verification:

```bash
git status   # working tree clean before survey + after survey
```

---

## See also

- [`spec.md`](../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/spec.md)
  §"Domain Language" — verbatim definitions reproduced in this document.
- [`data-model.md`](../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/data-model.md)
  §"VersionTag (enum)" and §"PageInventoryEntry" — canonical schema.
- [`research.md`](../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/research.md)
  R-006 (version-tag mechanism) and R-008 (bulk-edit blast radius).
- [`contracts/version_leakage_check.md`](../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/contracts/version_leakage_check.md)
  — banner regex and leakage rule definitions.
- [`occurrence_map.yaml`](../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/occurrence_map.yaml)
  — bulk-edit guardrail for the frontmatter rollout and the archive moves.
