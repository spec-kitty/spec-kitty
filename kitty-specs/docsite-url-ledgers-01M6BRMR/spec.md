# Mission Specification: Docsite URL baseline, moves ledger and single index files

**Mission Branch**: `issue-6927-url-baseline-moves-ledger` (single_branch)
**Created**: 2026-11-01
**Status**: Draft
**Input**: Operator dispatch brief for #6927 and #6928 (epic #6100, plan steps S-3 then S-4), governed by ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-1, D-5 and D-7. Absorbs #2358, folds #3914.

## Intent Summary

**Discovery mode.** This is a dispatched, non-interactive session. The operator's dispatch brief, issues #6927, #6928, #2358 and #3914, and the ADR together form a comprehensive brief, so discovery was reduced to brief intake. The one open design choice (how a route is written in the moves ledger) was recorded as Decision Moment `01M6BRRA8VAED9C86WVXDKSKBK` and resolved from the brief's "keep the ledger format neutral" instruction. The grounding is in `research/code-grounding.md`.

- **Primary actor:** a maintainer who moves, renames or deletes a published docs page, and the docs deploy job that must keep every old URL working.
- **Trigger:** a docs page moves (now, or in a later doc-kitty step), or a folder holds two index files.
- **Desired outcome:** the published URLs and every move are recorded in two standing, repository-level ledgers under `site/`. The DocFX redirect map is derived from those ledgers. Each of the four dual-index folders keeps one index file. The live DocFX site keeps every URL it serves today.
- **Invariant:** no URL that the site has published stops resolving. A URL leaves the baseline only through a recorded amendment.
- **Bulk edit:** this Mission repoints the path `docs/architecture/README.md` (and the three `docs/adr/<era>/README.md` paths) to the surviving `index.md` in more than one file, with per-category rules captured in `occurrence_map.yaml` (DIRECTIVE_035). That map classifies this Mission's own edit; it is not a moves ledger and no script reads it.
- **Boundary:** this Mission does not build the doc-kitty site, write doc-kitty configuration, generate `redirects.json` (#6933) or migrate frontmatter (#6929).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record every published URL once (Priority: P1)

A maintainer preparing the doc-kitty site needs one committed list of every URL the docsite has published, so the later redirect layer can prove that none breaks.

**Why this priority**: every later step of #6100 (scaffold, redirects, cutover) checks against this list.

**Independent Test**: read the baseline file and confirm it holds every URL of the old 180-URL manifest, every key of the redirect map and every page the current DocFX build publishes.

**Acceptance Scenarios**:

1. **Given** the old manifest and the current redirect map, **When** the baseline is read, **Then** each of their URLs is in it.
2. **Given** a page the current DocFX build publishes, **When** the baseline is seeded, **Then** the page's URL is in it; a page published later and not appended is reported by the deploy job.
3. **Given** the baseline file, **When** a reader opens it, **Then** its header states where its entries came from and the amendments inherited from the old manifest.

---

### User Story 2 - Record moves in a standing ledger, not a closed Mission (Priority: P1)

A maintainer who moves a docs page appends one `old route -> new route` line to a repository-level ledger. The DocFX redirect map is regenerated from it, with no reference to any Mission's occurrence map.

**Why this priority**: #2358. Today the only home for a move is a closed Mission's artifact, so the next structural move has nowhere to go.

**Independent Test**: append a move to a copy of the ledger, regenerate the redirect map, and see the new redirect. Regenerating from the committed ledger reproduces the committed map byte for byte.

**Acceptance Scenarios**:

1. **Given** the committed ledger, **When** the redirect map is regenerated, **Then** the output equals the committed map.
2. **Given** a ledger where A moved to B and later B moved to C, **When** the map is regenerated, **Then** A and B both redirect straight to C.
3. **Given** any docs tooling script, **When** it runs with its defaults, **Then** it reads no file under `kitty-specs/`.

---

### User Story 3 - Moved pages that never got a redirect get one (Priority: P2)

#3914: the strict reconcile reports 124 file moves whose old URL has no redirect. Each of those old URLs now redirects to the page's current home.

**Why this priority**: it is a reliability debt, and the new ledger is where it is paid.

**Independent Test**: run the forward reconcile (every file move in the ledger has a redirect-map key) and get zero findings.

**Acceptance Scenarios**:

1. **Given** the 124 moves from #3914, **When** the redirect map is read, **Then** each old URL is a key whose target is a live page.
2. **Given** a move whose recorded destination has since moved again, **When** the map is regenerated, **Then** the redirect points at the page's current home, not at a dead address.

---

### User Story 4 - One index file per folder (Priority: P2)

doc-kitty refuses a folder with both `index.md` and `README.md`. Four folders have both: `adr/1.x`, `adr/2.x`, `adr/3.x` and `architecture`. After this Mission each has only `index.md`, and the old `README.html` URLs still resolve on the DocFX site.

**Why this priority**: it blocks the doc-kitty scaffold (#6930).

**Independent Test**: list each folder; check that the `README.html` URLs are redirect-map keys pointing at the folder's index page.

**Acceptance Scenarios**:

1. **Given** the three ADR era folders, **When** listed, **Then** none holds a `README.md`.
2. **Given** `architecture/`, **When** listed, **Then** it holds `index.md` and no `README.md`, and `index.md` carries the landing content the old README held (boundary rule, living and frozen pages, decay rule).
3. **Given** the four old `README.html` URLs, **When** the redirect map is read, **Then** each redirects to its folder's `index.html`.
4. **Given** any live page, link or test that pointed at a removed README, **When** the docs tooling and tests run, **Then** nothing points at it any more (immutable history excepted).

### Edge Cases

- A ledger entry whose `from` is a page that is live again: a stub there would overwrite a live page. This is refused.
- A ledger entry whose final destination is not a live page: refused (the no-404 invariant).
- A cycle in the ledger (A to B, B to A): refused.
- A legacy `dir/index.html` key whose section no longer exists (for example `tutorials/index.html`): it stays an ordinary key.
- DocFX's `toc.html` and the generated `kitty-specs/**` dashboard pages: outside the baseline (ADR D-5, ruling 3).
- A shallow clone without the base commit #3914 names: the forward reconcile runs without git history.

## Domain Language

| Term | Meaning | Avoid |
|---|---|---|
| **URL baseline** | `site/url-baseline.txt`: every URL the site has published. It grows on publish; an entry leaves only with a recorded amendment. | "manifest" for the new file (the old JSON manifest keeps that name) |
| **Moves ledger** | `site/moves.yaml`: append-only `old route -> new route` list at repository level. | "spine", "occurrence map" (those name the Mission-scoped artifact it replaces) |
| **Route** | A site-relative published path in its legacy DocFX form, for example `guides/x.html`. | "URL" when the site prefix is meant |
| **Redirect map** | `scripts/docs/redirect_map.yaml`, which DocFX reads. Derived, never hand-edited. | |
| **Mission** | The canonical product term. | "feature" |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | URL baseline ledger | As a maintainer, I want `site/url-baseline.txt` (one site-relative URL per line, `#` comments, provenance header) seeded from a DocFX site walk unioned with every redirect-map key, so that every published URL is recorded. | High | Open | [build] | no — the file does not exist today; the containment test fails on its absence |
| FR-002 | Baseline containment test | As a reviewer, I want a test asserting that every URL of the old `redirect_baseline_urls.json` manifest and every redirect-map key is in the baseline, so that the ledger cannot shrink silently. | High | Open | [build] | no — paired with a mutant baseline missing one URL on the same fixture |
| FR-003 | Moves ledger | As a maintainer, I want `site/moves.yaml` holding every current redirect-map entry and every occurrence-map file move as `from`/`to` routes, with a header recording the provenance and the three amendments of `redirect_baseline_urls.json`, so that moves have a standing home. | High | Open | [build] | no — the file does not exist today |
| FR-004 | Map derived from the ledger | As a maintainer, I want `redirect_stub_generator.py regenerate-map` and `check-map` to derive `redirect_map.yaml` from `site/moves.yaml` alone, collapsing chains, so that DocFX reads a map built from the standing ledger. | High | Open | [build] | no — a regenerate after appending a move must produce that key; today it cannot |
| FR-005 | Ledger validity | As a maintainer, I want the derivation to refuse a cycle, a `from` that is a live page, and a final target that is not a live page, so that no stub breaks or hides a page. | High | Open | [build] | no — each refusal has a fixture that passes without the defect |
| FR-006 | Reconcile #3914 | As a reader with an old bookmark, I want every one of the 124 file moves #3914 lists to have a redirect to the page's current home, so that the strict forward reconcile is clean. | High | Open | [build] | no — the reconcile reports 124 findings today |
| FR-007 | No Mission-scoped occurrence map | As a maintainer, I want `redirect_stub_generator.py`, `rename_reconcile.py`, `bulk_ref_rewrite.py` and `relative_link_fixer.py` to default to `site/moves.yaml` and to read no file under `kitty-specs/`, so that #2358 is closed. | High | Open | [build] | no — a scan of the scripts' defaults finds the Mission paths today |
| FR-008 | Remove the ADR-era README stubs | As a doc-kitty builder, I want `docs/adr/1.x/README.md`, `docs/adr/2.x/README.md` and `docs/adr/3.x/README.md` deleted, with their `README.html` routes redirected to the era `index.html`, so that each era folder has one index file. | High | Open | [build] | no — the files exist today |
| FR-009 | Fold the architecture landing page | As a reader of `architecture/`, I want the content of `docs/architecture/README.md` folded into `docs/architecture/index.md`, the README deleted, and `architecture/README.html` redirected to `architecture/index.html`, so that the folder has one index file and loses no content. | High | Open | [build] | no — the README exists today; a content check names its sections |
| FR-010 | Repoint live references | As a maintainer, I want every live link, `related` entry, test constant and guidance line that names a removed README to name the surviving `index.md` instead (ADR bodies, plans, reports and the changelog excepted), so that nothing dangles. | Medium | Open | [build] | no — grep finds them today |
| FR-011 | One index per folder test | As a reviewer, I want a test asserting that no folder under `docs/` holds both `index.md` and `README.md`, so that the collision cannot return. | Medium | Open | [build] | no — fails on today's four folders |
| FR-012 | Grow-on-publish report | As a maintainer, I want the DocFX deploy job to walk the built site after the build and warn, without failing the deploy, about every published page missing from the baseline, so that a page added without a baseline line is visible. | Low | Open | [build] | no — a fixture site with an unlisted page produces the warning; a listed one does not |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | DocFX coverage stays green | The DocFX `generate` and `coverage` steps, run against a local DocFX build of the final tree, report 0 dead targets and 0 uncovered URLs over the full baseline. | Reliability | High | Open |
| NFR-002 | Deterministic derivation | Regenerating `redirect_map.yaml` from the committed ledger twice gives byte-identical output equal to the committed file. | Reliability | High | Open |
| NFR-003 | Code quality | New and changed Python passes `ruff check`, `ruff format --check --force-exclude` and `mypy` with zero findings; no function exceeds cyclomatic complexity 15. | Maintainability | High | Open |
| NFR-004 | Fast tests | The new ledger tests run in under 5 seconds in total on a developer machine. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | DocFX stays live | DocFX publishes the site throughout. `docs-pages.yml` keeps reading `scripts/docs/redirect_map.yaml` and its generate and coverage steps keep passing. | Technical | High | Open |
| C-002 | Out of scope | No `site/` build, no doc-kitty configuration, no `redirects.json` generator (#6933), no frontmatter migration (#6929). Frontmatter is touched only where a `related` entry would dangle. | Technical | High | Open |
| C-003 | Immutable history | ADR bodies, plans, reports, the changelog and closed Missions' occurrence maps are not rewritten. | Governance | High | Open |
| C-004 | Generated surfaces | The docs retrieval index, page inventory and ADR era table rows are not edited in this PR; the post-merge `ci/regen-docs-index` bot regenerates them (#6993). | Process | High | Open |
| C-005 | Neutral ledger format | `site/moves.yaml` and `site/url-baseline.txt` record routes in the legacy published form, readable by DocFX tooling and by a later doc-kitty generator. | Technical | High | Open |
| C-006 | Packaging untouched | `site/` is not shipped in the wheel or sdist; no packaging code changes (#6926 owns the sdist include). | Technical | Medium | Open |
| C-007 | Terminology canon | Prose uses Mission, never feature; `test_no_legacy_terminology.py` passes. | Governance | Medium | Open |

### Key Entities

- **Baseline entry**: one site-relative published route. Comes from the site walk or a redirect-map key.
- **Move**: `from` route, `to` route, optional reason and provenance reference. Append-only.
- **Amendment**: date, PR, ground, ruling, added and removed routes. Carried over from the old manifest into the ledger header.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the URLs in the old manifest and the redirect map, and of the pages the DocFX build publishes today, are in the baseline — [build] · no-op passable: no
- **SC-002**: The strict forward reconcile reports 0 findings, down from 124 — [build] · no-op passable: no
- **SC-003**: 0 docs tooling defaults name a path under `kitty-specs/` — [build] · no-op passable: no
- **SC-004**: Each of the 4 folders holds exactly 1 index file — [build] · no-op passable: no
- **SC-005**: 0 baseline URLs are uncovered and 0 redirects point at a missing page in the DocFX coverage run — [ratchet] · no-op passable: no (paired with a mutant redirect to a dead target)

## Assumptions

- A URL from #3914's 124 cannot be proven once live from this shallow history. Redirecting it costs one stub file and breaks nothing, so every such URL is redirected and joins the baseline as a redirect-map key.
- `toc.html` is a DocFX navigation fragment, not a page; it stays outside the baseline (recorded in the header).
- The baseline seed is 835 plus this Mission's additions; the ADR's 831 was measured at its own base.
- The grow-on-publish rule is reported, not gated, in this Mission (FR-012). A blocking per-PR check would make every docs PR that adds a page edit one shared file, the merge-conflict pattern #6993 just removed; the gate belongs with the doc-kitty build gate (#6930, #6933, ADR D-11).
