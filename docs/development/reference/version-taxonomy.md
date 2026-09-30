---
title: Version taxonomy
description: The five version-relevance tags every docs page carries, what each means for the active release line, and how the leakage check enforces them.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/development/reference/index.md
- docs/development/page-inventory.yaml
---
# Version taxonomy

Every page in the docs inventory carries exactly one **version tag**. The tag
answers one question for a reader: *does this page describe the Spec Kitty
release line I am running?*

The tags are relative to the **active release line**, the line `main` ships
from. That is currently 4.x. See the charter's Branch and Release Strategy
section. When the active line changes, the tags keep their meaning, and no
page needs renaming.

The enum lives in `scripts/docs/_inventory.py` (`VersionTag`). The generated
inventory is `docs/development/page-inventory.yaml`. The leakage check is
`scripts/docs/version_leakage_check.py`.

## The five tags

| Tag | Use it for | Banner |
| --- | --- | --- |
| `current` | Pages that describe the active release line: installed CLI behaviour, shipped doctrine, the mission workflow, the reference. New pages default here. | None. It must not carry an archive or migration banner. |
| `supported` | Pages written for the previous release line whose behaviour still holds, but that have not been re-audited for the active line. | None required. A short "last audited against X" note is recommended. |
| `archival` | Material from retired lines (1.x, 2.x and so on), kept for the record under `docs/archive/`. | **Required.** |
| `migration` | Pages whose main purpose is to move a reader from an earlier line to the active one (`docs/migration/`). | **Required.** |
| `internal` | Maintainer and contributor material (`docs/development/`, `docs/architecture/`, `docs/plans/`). | None. It is ignored on both sides of a link. |

The required banner is a blockquote within the first 20 non-empty lines
that matches:

```text
^>\s*(?:Archive notice|Migration note)\b
```

## Invariants

- Every inventoried page maps to exactly one tag.
- `archival` implies `current_target: false`.
- `current` implies `current_target: true`.
- `internal` pages are excluded from `current_target` validation.

`scripts/docs/_inventory.py` enforces the invariants when the inventory is
loaded.

## How the leakage check uses the tags

In-file frontmatter is the source of truth for each page. The inventory
is regenerated from it, and the `INVENTORY-LOCKFILE-DRIFT` gate in
`scripts/docs/check_docs_freshness.py` blocks drift between the two. The
leakage check then reports:

- `LEAK-CURRENT-LINKS-ARCHIVAL`: a `current` page links to an `archival`
  page that has no migration banner.
- `LEAK-MISSING-BANNER`: an `archival` or `migration` page has no banner.
- `LEAK-MISSING-INVENTORY`: a markdown file under `docs/` is not in the
  inventory.
- `LEAK-MISSING-FILE`: an inventory row points at a file that does not
  exist.

## History

The taxonomy was introduced by the 3.2 documentation mission
(`spec-kitty-3-2-docs-01KS4KSZ`, FR-001). It was made version-neutral on
2026-09-30, when the 4.x line became active. The mission's `spec.md` and
`data-model.md` keep the original 3.2-anchored wording.
