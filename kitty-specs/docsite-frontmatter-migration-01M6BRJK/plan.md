# Implementation Plan: Docsite build-blocking frontmatter migration

**Branch**: `issue-6929-docsite-frontmatter-migration` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/docsite-frontmatter-migration-01M6BRJK/spec.md`

## Summary

Make the real `docs/` tree build on doc-kitty (#6929, ADR `2026-10-31-1` D-7/D-8) by migrating four
frontmatter classes with one committed, idempotent, frontmatter-only script, and porting every core
reader of each changed field in the same change. The fifth class (excluded-tree title/description)
needs no edit: doc-kitty's native `exclude` never reads those files (verified by build, grounding §4).
A body-hash test guards the immutable corpus; a corpus-shape test holds the new shapes, because the
readers are not wired into any workflow.

## Engineering Alignment

- **One owner for the rules.** `scripts/docs/_dockitty_contract.py` owns: the excluded folders, the
  index basenames, `slug_of(path)`, `resolve_slug(slug)`, `is_published(page)`, persona-profile
  resolution and the immutable-file predicate. The migration, the three ported readers and the
  tests import it. No reader re-derives a slug or the excluded list.
- **Frontmatter edits are line-level.** The migration replaces only the `audience:` and `related:`
  top-level blocks and inserts `doc_status`/`kind`/`external_references` lines. Every other
  frontmatter line, and every byte after the closing fence, stays as it is. Each rewritten file is
  re-parsed and compared key by key (only the intended keys may differ); a mismatch aborts.
- **Readers take the new shape only.** The excluded trees are migrated too, so no reader keeps a
  legacy branch (charter: single canonical authority, no-fallback).
- **Not a bulk edit.** This is a schema transformation by one audited script, guarded by the
  body-hash and shape tests, not a rename of one string across files. `change_mode` stays unset; the
  occurrence-classification guardrail (DIRECTIVE_035) is answered by the shape test, which names
  every remaining old-shape occurrence.
- **Excluded folders are named once in core** until #6930 adds `site/astro.config.mjs`; that step
  should read or pin this list rather than copy it.

## Technical Context

**Language/Version**: Python 3.11+ (scripts and tests); YAML frontmatter in Markdown.
**Primary Dependencies**: `ruamel.yaml` (already a dependency; safe load + emit of the rewritten blocks). One-off build only: Node 22, pnpm 10, `@spec-kitty/doc-toolkit` as a pnpm git dependency at doc-kitty `fe835cd`, Astro 7.4, Starlight 0.42 — in `/tmp`, nothing committed.
**Storage**: files (`docs/**/*.md`).
**Testing**: pytest. Red-first per WP: `tests/docs/test_immutable_bodies.py`, `tests/docs/test_dockitty_frontmatter_shape.py`, `tests/docs/test_dockitty_frontmatter_migration.py`, `tests/docs/test_dockitty_contract.py`, and the rewritten `test_audience_resolves.py`, `test_touched_set_gates.py`, `test_related_validator.py`, `test_rulers_blocking.py`. Blast radius: `make test-fast`, `tests/docs/`, `tests/specify_cli/docs/`, `tests/architectural/test_no_legacy_terminology.py`.
**Target Platform**: repository tooling (Linux/macOS/Windows CI).
**Project Type**: single.
**Performance Goals**: body-hash and shape tests under 10 s each over ~930 files (NFR-003).
**Constraints**: frontmatter-only (NFR-001); generated surfaces and #6927/#6928 files untouched (C-003); no `site/` (C-002).
**Scale/Scope**: ~344 audience pages, ~413 related pages (1,267 edges), 228 ADRs.

**Supply chain (DIRECTIVE_051).** The plan adds no committed dependency. The one-off build installs
doc-kitty from its public repository pinned by a 40-character commit, with its own lockfile
resolution, in a throwaway `/tmp` project that is never committed; no install scripts are trusted
beyond pnpm's defaults. The committed dependency decision belongs to #6930 (ADR D-2). No adversarial
squad is required for a dependency decision because none is made here.

## Charter Check

| Rule | Verdict |
| --- | --- |
| Single canonical authority | Pass: one contract module; readers import it. |
| ATDD-first (C-011) | Pass: each WP commits its failing test first. |
| Immutable history | Pass: frontmatter-only; body-hash test. |
| Smallest viable diff / locality | Pass: only fields named in #6929, ADR `kind` per the issue; `doc_status` vocabulary and `type`/`kind` completion left to #6931. |
| Canonical sources | Pass: doc-kitty consumed unmodified; native `exclude` replaces the spike's shim. |
| No heavy suites in mission | Pass: targeted files plus `make test-fast`. |
| Terminology canon | Pass: gate run before push. |
| Tracker hygiene | #6929 claimed (operator assigned, comment naming the Mission). |

Post-design re-check: no new violation. One recorded deviation from the issue's wording
(unpublished `related` targets go to `external_references`, not into the body) is a resolved
Decision Moment flagged for the operator.

## Project Structure

### Documentation (this mission)

```
kitty-specs/docsite-frontmatter-migration-01M6BRJK/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── research/code-grounding.md
├── traces/{tooling-friction,approach,design-decisions}.md
└── tasks/
```

### Source Code (repository root)

```
scripts/docs/
├── _dockitty_contract.py              # NEW: slug, published, excluded folders, personas, immutable set
├── dockitty_frontmatter_migration.py  # NEW: idempotent, frontmatter-only migration (--check/--apply/--verify-against)
├── audience_resolver.py               # PORT: profile list
├── touched_set_gates.py               # PORT: profile list
└── related_validator.py               # PORT: slugs, unpublished targets
tests/docs/
├── test_immutable_bodies.py           # NEW (first commit)
├── test_dockitty_contract.py          # NEW
├── test_dockitty_frontmatter_migration.py  # NEW
├── test_dockitty_frontmatter_shape.py # NEW: corpus invariant
└── test_{audience_resolves,touched_set_gates,related_validator,rulers_blocking}.py  # rewritten fixtures
docs/**/*.md                           # frontmatter only
```

**Structure Decision**: single project; tooling under `scripts/docs/` (not shipped in the wheel), tests under `tests/docs/`.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Immutable-body guard and the frontmatter editor

- **Purpose**: prove no body changes, and give every later concern one body-preserving way to edit frontmatter.
- **Relevant requirements**: FR-001, FR-010, NFR-001, NFR-003.
- **Affected surfaces**: `scripts/docs/_dockitty_contract.py`, `scripts/docs/dockitty_frontmatter_migration.py`, `tests/docs/test_immutable_bodies.py`.
- **Sequencing/depends-on**: none.
- **Risks**: a YAML re-emit that reformats untouched keys; mitigated by line-level block replacement and a key-by-key re-parse check.

### IC-02 — Audience profiles

- **Purpose**: path strings become `[{profile, guidance_text}]`; the two audience readers follow.
- **Relevant requirements**: FR-002, FR-003.
- **Affected surfaces**: `docs/**` frontmatter, `scripts/docs/audience_resolver.py`, `scripts/docs/touched_set_gates.py`, their tests.
- **Sequencing/depends-on**: IC-01.
- **Risks**: `touched_set_gates` resolved page-relative paths; the profile form removes that variant.

### IC-03 — ADR lifecycle metadata

- **Purpose**: every dated ADR gains `doc_status` and `kind: ADR`, so none is a draft on the site.
- **Relevant requirements**: FR-008.
- **Affected surfaces**: `docs/adr/<era>/*.md` frontmatter (not the era index files).
- **Sequencing/depends-on**: IC-01. Must precede IC-04 (publication of ADR targets).
- **Risks**: collision with #6902 on one ADR's frontmatter; resolved by re-running the script.

### IC-04 — Related slugs and external references

- **Purpose**: `related` names published pages by slug only; everything else moves to `external_references`.
- **Relevant requirements**: FR-005, FR-006, FR-007.
- **Affected surfaces**: `docs/**` frontmatter, `scripts/docs/related_validator.py`, its tests and `test_rulers_blocking.py`.
- **Sequencing/depends-on**: IC-01, IC-03.
- **Risks**: `README`/`index` index slugs; case-sensitive lookup; two pre-existing dangling refs are dropped and reported.

### IC-05 — Shape invariant and build evidence

- **Purpose**: hold the shapes with one corpus test, and prove the build with the spike's commands.
- **Relevant requirements**: FR-004, FR-009, FR-011, SC-001..SC-005.
- **Affected surfaces**: `tests/docs/test_dockitty_frontmatter_shape.py`; build evidence in the mission folder.
- **Sequencing/depends-on**: IC-02, IC-03, IC-04.
- **Risks**: the build may surface a blocker the spike did not hit (new pages since); fixed in scope only if it is one of the five classes, else filed.
