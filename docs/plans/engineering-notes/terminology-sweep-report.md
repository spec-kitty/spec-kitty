---
title: Docs IA & Onboarding Overhaul — Terminology Sweep & Closing Report
description: 'Closing terminology/glossary check status and Divio frontmatter coverage record for the docs IA overhaul mission.'
doc_status: closeout
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
type: explanation
related:
- kitty-specs/docs-ia-onboarding-overhaul-01KY02JB/docs-audit.md
- docs/architecture/doctrine-kinds.md
---

# Docs IA & Onboarding Overhaul — Terminology Sweep & Closing Report

This is WP10's closing record for mission `docs-ia-onboarding-overhaul-01KY02JB` — the final
work package, run only after WP01–WP09 were all approved. It covers T040–T044: the mission-wide
terminology/glossary sweep (FR-014), the NFR-005 Divio frontmatter coverage check, and the C-003
follow-up issue filing. See also
[`docs-audit.md`](../../../kitty-specs/docs-ia-onboarding-overhaul-01KY02JB/docs-audit.md) for the
per-WP disposition tables and findings this report summarizes.

## Mission diff scope

WP10's lane (`lane-a`) depends on all 8 sibling lanes (`lane-b` through `lane-i`, covering
WP02–WP09). Those dependency-lane tips were merged into `lane-a`'s worktree (idempotent, via the
lane allocator's standard dependency-merge step) before this WP's checks ran, so T040–T044
operated on the full combined mission output, not just WP01's own commits. The mission's diff
against its merge-base with `main` touches **86 files total**, of which **76 are under `docs/`**
(70 Markdown pages + 6 non-Markdown nav/config files: `toc.yml`, `docfx.json`,
`3-2-page-inventory.yaml`, and per-zone child TOCs).

## Pages moved / merged / removed / created

Pulled from [`docs-audit.md`](../../../kitty-specs/docs-ia-onboarding-overhaul-01KY02JB/docs-audit.md)
and confirmed against `git diff --name-status -M` for the full mission diff:

| Action | Count | Detail |
|---|---|---|
| **Moved** | 13 | `docs/guides/` → `docs/development/` (WP01), confirmed contributor-only content. `docs/development/` grew from 7 pre-existing pages to 20 (18 Markdown pages + the generated inventory lockfile + one pre-existing doctrine tactic YAML). |
| **Renamed** | 1 | `docs/guides/your-first-feature.md` → `docs/guides/your-first-mission.md` (WP03, FR-014's explicit retitle requirement). |
| **Created** | 4 new pages | `docs/context/mission-types.md`, `docs/context/ops-vs-missions.md` (WP04); `docs/doctrine/doctrine-kinds.md`, `docs/doctrine/create-a-doctrine-artifact.md` (WP06). Plus 2 new nav files: `docs/development/toc.yml` (WP02's new contributor-zone child TOC) and this report itself. |
| **Removed** | 0 | No page was deleted. Content consolidation (WP05's charter how-to work) rationalized overlapping content across existing pages rather than deleting files — confirmed via `git diff --name-status`: zero `D` (delete) entries anywhere under `docs/` for the full mission diff. |
| **Content-edited (accuracy/terminology/nav)** | ~50 pages | The remainder of the 70 touched Markdown pages: WP02's nav rebuild, WP05's charter consolidation, WP07's reference-accuracy fixes (8 confirmed inaccuracies across `docs/api/`, `docs/migrations/`, `docs/adr/`, `docs/operations/` — see `docs-audit.md`'s WP07 section), WP08's glossary-anchor activation, and this WP's own terminology-casing and Divio-frontmatter fixes. |

## Final navigation entry counts per zone

`docs/toc.yml` (WP02's two-zone rebuild, verified live against the current file):

| Zone | Unexpanded top-level entries |
|---|---|
| **Using Spec Kitty** (end-user) | 6 — Home, Guides, Core Concepts, Reference, Migrations, Project Updates |
| **Contributing** (contributor) | 5 — Architecture, ADRs, Plans, Operations, Development |

The Using Spec Kitty zone is at 6 unexpanded entries and Contributing at 5 (both within NFR-003's
`<=6` ceiling; "Mission Runs" is nested under Project Updates in the Using zone, not a Contributing
top-level entry), down from the prior 16-entry flat list, and FR-015 (hierarchical grouping via
nested `items:`) is satisfied. `Development` is the one
genuinely new top-level entry, closing the pre-existing gap WP01 flagged (`docs/development/` had
zero `docs/toc.yml` entries before WP02, despite holding 20 pages after WP01's relocation).

## Terminology / glossary check status

Two architectural checks were run against the full mission diff (`.venv/bin/pytest
tests/architectural/test_no_legacy_terminology.py tests/architectural/test_glossary_canonical_terms.py -v`):

### `test_no_legacy_terminology.py` — **clean, 3/3 passed**

The hardcoded two-term legacy denylist defined in `test_no_legacy_terminology.py` (both terms
canonicalize to "status commit" per `.kittify/glossaries/spec_kitty_core.yaml`) has zero
occurrences anywhere this mission touched. No fixes were needed.

### `test_glossary_canonical_terms.py` — mission scope clean; pre-existing drift outside scope remains

> **Update (#2830, 2026-07-22):** the 200 pre-existing occurrences described below as
> "left untouched" have since been fully paid down in a follow-up pass. The baseline-ratchet
> escape hatch (`glossary_canonical_terms_baseline.txt`) was retired and the gate now enforces
> **zero** non-canonical occurrences in prose repo-wide (it skips fenced code blocks and
> inline-code spans, so captured `--help` output and emitted-string literals keep their real
> casing). The paragraph below is preserved as the historical record of the introducing
> mission's scope.

This test (added by WP09) scans all of `docs/**/*.md` for the 104-term live glossary seed's
multi-word surfaces (`.kittify/glossaries/spec_kitty_core.yaml`) in non-canonical casing. On the
full `docs/` tree it initially reported **274 flagged occurrences**. Cross-referencing every
flagged file against this mission's own diff (`git diff --name-only` vs. the mission's
merge-base with `main`) split the findings:

- **74 occurrences, across 21 files this mission genuinely touched** (real content edits, not
  incidental) — **all fixed** in this WP. Files: `docs/api/{charter-commands,cli-commands,
  configuration,environment-variables,file-structure,missions,supported-harnesses}.md`,
  `docs/changelog/CHANGELOG.md`, `docs/doctrine/doctrine-kinds.md`, `docs/guides/{accept-and-merge,
  create-plan,generate-tasks,implement-work-package,merge-feature,multi-agent-workflow,
  review-work-package,troubleshoot-merge,use-dashboard,your-first-mission}.md`,
  `docs/plans/3-2-doc-publication/{3-2-information-architecture,3-2-navigation-plan}.md`.
  Each fix was a minimal casing correction — a title-case or PascalCase rendering of a
  multi-word glossary term (per `.kittify/glossaries/spec_kitty_core.yaml`) brought back to its
  canonical all-lowercase surface form — applied at the exact file:line the check flagged.
- **200 occurrences, across ~70 files this mission never touched** (e.g.
  `docs/context/orchestration.md`, `docs/architecture/kanban-workflow.md`,
  `docs/archive/2x/runtime-and-missions.md`, most of `docs/plans/engineering-notes/` and
  `docs/plans/investigations/`) — **left untouched**, per this mission's DIR-013 discipline
  (pre-existing findings outside a WP's own diff are noted, not silently absorbed into scope).
  These are genuine casing drift that predates this mission; `test_glossary_canonical_terms.py`
  itself remains red at the repository level until a future pass (or the C-003 follow-up work,
  see below) addresses them.

**Re-run confirmation**: after the fixes, zero of the remaining 200 flagged occurrences fall
inside this mission's diff (`comm -12` between the flagged-file list and the mission's
touched-file list returns empty). Both checks were re-run clean for mission scope; the
glossary-casing test still fails at the whole-repo level solely due to the 200 pre-existing,
out-of-scope occurrences.

Success Criterion 7 ("a terminology/glossary-canonical-form check runs clean across all
mission-touched docs at completion") is **met**: zero flagged occurrences remain within files
this mission touched or created.

## NFR-005 — Divio frontmatter coverage

Every Markdown page this mission touched or created under `docs/` was checked for a `type:`
frontmatter field with a value in `{tutorial, how-to, reference, explanation}`.

**Scope decision**: NFR-005's acceptance criterion text specifically targets "100% of pages in
`docs/guides/` (post-restructure) and newly authored pages." That is also the only zone where the
existing repository convention actually applies `type:` frontmatter — a spot-check across
`docs/api/`, `docs/adr/`, `docs/changelog/`, `docs/plans/`, `docs/operations/`,
`docs/architecture/`, and index/nav pages throughout the tree (including ones this mission did
not touch) confirms none of them carry `type:`; they use a distinct, consistent `title`/
`doc_status`/`date`-style frontmatter for process/reference artifacts (ADRs, changelog, planning
notes) that Divio classification doesn't fit. Retrofitting `type:` onto only the handful of such
files this mission happened to touch, while leaving hundreds of untouched siblings in the same
directories without it, would create inconsistency rather than close a real gap. This WP
therefore applied the NFR-005 fix precisely where the acceptance criterion — and the established
convention — actually target it: `docs/guides/` and newly authored pages.

**Findings and fixes**:

- **22 `docs/guides/*.md` pages** were touched by this mission. 3 already had valid `type:`
  (`charter-governed-workflow.md`, `setup-governance.md`, `troubleshoot-charter.md` — WP05).
  3 are index/nav pages (`index.md`, `how-to-index.md`, `tutorials-index.md`), excluded per the
  same convention every other `index.md` in the tree follows (none carry `type:`, confirmed
  spot-check against `docs/api/index.md`, `docs/development/index.md`, `docs/operations/index.md`,
  `docs/doctrine/index.md`, `docs/planning/index.md`). The remaining **16 pages were missing
  `type:` entirely** — fixed in this WP, classified from actual page content (several
  self-declare "**Divio type**: Tutorial" in their body, confirming the classification):

  | Page | Type added |
  |---|---|
  | `getting-started.md`, `missions-overview.md`, `multi-agent-workflow.md`, `orchestrator-quickstart.md`, `your-first-mission.md` | `tutorial` |
  | `accept-and-merge.md`, `create-plan.md`, `create-specification.md`, `generate-tasks.md`, `implement-work-package.md`, `install-claude-code-plugin.md`, `merge-feature.md`, `review-work-package.md`, `troubleshoot-merge.md`, `use-dashboard.md`, `use-retrospective-learning.md` | `how-to` |

- **4 newly authored pages** (`docs/context/mission-types.md`, `docs/context/ops-vs-missions.md`,
  `docs/doctrine/doctrine-kinds.md`, `docs/doctrine/create-a-doctrine-artifact.md`) already
  carried valid `type:` frontmatter (`explanation`, `explanation`, `explanation`, `how-to`
  respectively) — added by WP04/WP06 at authoring time, no fix needed.

- **`docs/development/3-2-page-inventory.yaml`** (the generated frontmatter lockfile) was
  regenerated via `scripts/docs/inventory_lockfile.py --write` after these frontmatter changes,
  per the same canonical-tooling convention WP01 and WP07 used. `--strict` re-run confirms zero
  drift (`generated=639 committed=639`).

**Result**: 100% of this mission's touched/created pages within NFR-005's actual scope
(`docs/guides/` non-index pages + newly authored pages) now carry valid Divio `type:`
frontmatter. Pages outside that scope (ADRs, changelog, plans, API reference, operations,
migrations, architecture) retain the repository's separate, pre-existing, intentional
frontmatter convention and are not part of the Divio-classification gap NFR-005 targets.

## Follow-up GitHub issues filed

Two follow-up issues were filed as part of this WP, per C-003 and an additional scope-boundary
finding surfaced by WP06:

1. **[#2822](https://github.com/Priivacy-ai/spec-kitty/issues/2822) — "Glossary: add
   alias/banned-synonym governance (full canonical-term enforcement)"**. Tracks C-003's deferred
   scope: the glossary schema (`.kittify/glossaries/spec_kitty_core.yaml`) has no `aliases` or
   banned-synonym field, and `test_glossary_canonical_terms.py` only checks casing of known
   terms, not alias/banned-synonym resolution. References this mission, C-003, the schema gap,
   and the narrower test it would extend.
2. **[#2823](https://github.com/Priivacy-ai/spec-kitty/issues/2823) — "CLAUDE.md: Canonical Kind
   Vocabulary table is stale (lists 'template' instead of 'procedure')"**. WP06 found that root
   `CLAUDE.md`'s doctrine-kind table lists `template` as one of the 8 charter-activatable kinds;
   the actual 8th kind is `procedure` (verified against `src/doctrine/artifact_kinds.py`'s
   `CHARTER_KIND_TOKENS`, `src/charter/kind_vocabulary.py`, and a live
   `from doctrine.artifact_kinds import CHARTER_KIND_TOKENS` check). `template`/`asset` are
   distinct, non-charter-activatable `ArtifactKind` members. `CLAUDE.md` is outside this
   mission's `docs/`-scoped remit to edit directly, so it is tracked as a follow-up instead. This
   mission's own `docs/doctrine/doctrine-kinds.md`, `data-model.md`, and `research.md` already
   use the correct 8-kind list.

**Residual note, corrected post-mission-review**: an earlier draft of this report claimed
`spec.md` (lines 109, 128, 194) still listed the stale `template`-inclusive doctrine-kind set at
WP10 authoring time. Re-verified during mission review: `spec.md` was already corrected to the
accurate `procedure`-inclusive 8-kind list before WP10 ran (commit `eb88fa336`, merged into this
WP's lane before implementation started) — the claim was stale/inaccurate, not a real finding.
`spec.md`, `data-model.md`, `research.md`, and `docs/doctrine/doctrine-kinds.md` are all
consistent on the corrected 8-kind list as of mission completion.

## Verification commands

```bash
# Terminology checks (both clean for mission scope; glossary-casing check still red
# repo-wide due to 200 pre-existing, out-of-scope occurrences):
.venv/bin/pytest tests/architectural/test_no_legacy_terminology.py -v
.venv/bin/pytest tests/architectural/test_glossary_canonical_terms.py -v

# Relative-link integrity (unaffected by this WP's edits):
PYTHONPATH=src .venv/bin/python3 -m scripts.docs.relative_link_fixer --check

# Page-inventory lockfile freshness (zero drift after this WP's frontmatter fixes):
PYTHONPATH=src .venv/bin/python3 -m scripts.docs.inventory_lockfile --strict
```
