# Mission Specification: Docsite publication rules, llms.txt and render parity

**Mission Branch**: `kitty/mission-docsite-publication-llms-parity-01M70Z7A` (lands on `issue-6932-docsite-publication-llms-parity`, based on PR #7486's branch)
**Created**: 2026-11-09
**Status**: Draft
**Input**: Issues #6932 (publication rules), #6934 (`llms.txt`), #6935 (render parity) of epic #6100; ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-6, D-8, D-9, D-11.

## Intent Summary

- **Primary actors:** a reader or an AI agent using `docs.spec-kitty.ai` after cutover; a maintainer changing `docs/**`.
- **Trigger:** every pull request that selects the `docs-site` gate builds the doc-kitty site; DocFX keeps deploying until #6938.
- **Desired outcome:** the doc-kitty site publishes exactly the intended pages; working notes and retired hosted/sync pages appear on no surface (pages, hubs, sitemap, `llms.txt`, agent index, OKF export, search); `llms.txt` and the agent index exist and carry the version stance; every page has the SEO tags and alert rendering DocFX gives today. Each of these is proven on the built site in CI, and the frontmatter and link gates run over the published set.
- **Rules that must always hold:** what is excluded or unpublished is decided in one place (`scripts/docs/_dockitty_contract.py` → `site/dockitty-contract.json`, `docs/_meta/sections.yaml`, page frontmatter); bodies under `plans/`, `reports/`, `changelog/`, `archive/` and ADRs are never rewritten (frontmatter changes and moves only); every moved route gets an append-only `site/moves.yaml` row; bot-regenerated docs surfaces are not edited by hand.
- **Operator decisions (2026-11-09, Decision Moments):** retired hosted/sync single pages move under `docs/archive/` (doc-kitty `exclude` takes folders only); `guides/how-to/collaboration/sync-workspaces.md` joins them; `llms.txt`'s machine-index line resolves by mounting doc-kitty's agent index; `plans/engineering-notes`, `plans/investigations`, `plans/research` become `doc_status: draft` (frontmatter only).
- **Test value (#7484):** acceptance evidence is a check over the built site with mutant fixtures, not restatements of configuration.
- Grounding: `research/code-grounding.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Only intended pages are published (Priority: P1)

A reader or agent browsing or crawling the built site finds no working note (`plans/engineering-notes`, `plans/investigations`, `plans/research`), no excluded folder (`archive/`, `reports/`, `convergence/`) and no retired hosted/sync page on any surface. A maintainer who links a published page to an unpublished one, or breaks a page's frontmatter, gets a red `docs-site` gate.

**Why this priority**: publishing internal notes or retired hosted guidance after cutover misleads readers and agents; #6933 and #6938 depend on the unpublished set.

**Independent Test**: build the site; the built-site check walks `site/dist` and finds none of the unpublished routes on any surface; mutant fixtures (a planted draft page, a planted sitemap entry, a planted `llms.txt` line, a planted search or OKF record) each make it fail.

**Acceptance Scenarios**:

1. **Given** the built site, **When** the built-site check runs, **Then** no page, hub link, sitemap entry, `llms.txt` line, agent-index record, OKF file or search record names an unpublished route.
2. **Given** a published page that links to a draft, **When** the link gate runs in strict mode, **Then** the gate fails.
3. **Given** a retired page moved under `archive/`, **When** the moves ledger is checked, **Then** its old route has a row pointing at its section hub with a note.

---

### User Story 2 - `llms.txt` and the agent index carry the version stance (Priority: P2)

An AI agent reading `/llms.txt` sees the version stance (from `docs/llms.txt`'s "Current Version Stance") and only sections whose feeds include `llms`; its machine-index link resolves to `/api/index.json`.

**Why this priority**: D-9; the hand-written `docs/llms.txt` is deleted at #6938, so the generated file must carry its stance first.

**Independent Test**: the built-site check asserts `/llms.txt` exists, contains the stance block, lists no route from a section without `llms` in its feeds and no unpublished route, and that its machine-index link exists in the built site.

**Acceptance Scenarios**:

1. **Given** the built site, **Then** `llms.txt` holds the stance block and every listed route belongs to an `llms`-feed section.
2. **Given** the built site, **Then** `/api/index.json` exists and `dockitty-assert-no-broken-links` finds no dangling URL in `llms.txt`.

---

### User Story 3 - Pages render as well as on DocFX (Priority: P3)

A reader sees GitHub alert blocks (`> [!NOTE]`) rendered as callouts, and search engines see a description, a self-canonical link and Open Graph tags on every page, as DocFX's `seo_postprocess.py` / `seo_verify.py` ensure today.

**Why this priority**: render parity is a cutover prerequisite (#6935, D-6); it replaces two DocFX scripts at retirement.

**Independent Test**: the built-site check asserts, on every built HTML page, a non-empty description, a canonical link equal to the page's own URL, and `og:title`/`og:description`/`og:url`; it asserts that no built page contains a literal `[!NOTE]`-style alert marker. A parity checklist against DocFX names each DocFX rule and its doc-kitty equivalent or the upstream issue that tracks the gap.

**Acceptance Scenarios**:

1. **Given** the built site, **Then** 100% of HTML pages carry description, self-canonical and the three Open Graph tags.
2. **Given** a page with a `> [!NOTE]` alert, **Then** its built HTML renders a callout and contains no literal `[!NOTE]`.

### Edge Cases

- A draft page still appears in OKF or search because a surface ignores draft status: the built-site check fails (it covers each surface separately).
- `plans/` stays sitemap-only: non-draft `plans/` pages may appear in the sitemap, OKF and search, but not in `llms.txt` or the agent index.
- An immutable `plans/` body links to a page that becomes unpublished: allowed only from unpublished pages; a published immutable body that would break is reported, not rewritten.
- `docs/api/` builds to `dist/api/`; the agent index at `dist/api/index.json` must not collide with a page.
- A future `starlight.head` override would drop the toolkit's head entries (doc-kitty #295): none is added.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Working notes unpublished | As a reader, I want `plans/engineering-notes`, `plans/investigations` and `plans/research` pages to be drafts, so that working notes are never published. | High | Open | [build] | no — 12 such pages build today |
| FR-002 | Retired pages archived | As a reader, I want the retired hosted/sync pages (zeitgeist, teamspace, sync daemon, project-sync consent, the zeitgeist_client plan, sync-workspaces) moved under `docs/archive/` with a moves-ledger row each, so that they are unpublished and their old URLs can redirect to the section hub (#6933). | High | Open | [build] | no — they build today |
| FR-003 | One authority for the unpublished set | As a maintainer, I want the unpublished set (excluded folders, draft folders, archived pages) defined once in the contract module and its JSON projection, so that the gates, the built-site check and #6933's redirect generator read the same list. | High | Open | [build] | no — draft folders are not in the authority today |
| FR-004 | Frontmatter and link gates | As a maintainer, I want `dockitty-validate-frontmatter` and `dockitty-check-links --strict` (each with `--astro-config astro.config.mjs`) to run in the shared build, so that broken frontmatter or a link into an unpublished page fails the gate. | High | Open | [build] | no — no gate runs today |
| FR-005 | Built-site publication check | As a reader, I want a check over the built site that finds no unpublished route on any surface (pages, hubs, sitemap, `llms.txt`, agent index, OKF, search), run in the shared build after the site is built, so that publication is proven, not assumed. | High | Open | [build] | no — mutant fixtures prove it fails on a planted route |
| FR-006 | Generated `llms.txt` with stance | As an AI agent, I want `/llms.txt` generated by doc-kitty with the D-9 version-stance block and only `llms`-feed sections, so that the cutover can drop the hand-written file. | High | Open | [build] | no — no `llms.txt` is built today |
| FR-007 | Agent index | As an AI agent, I want `/api/index.json` mounted, so that `llms.txt`'s machine-index link resolves. | Medium | Open | [build] | no — not built today |
| FR-008 | GitHub alerts render | As a reader, I want `> [!NOTE]`-style alerts rendered as callouts, so that guidance reads as on DocFX. | Medium | Open | [build] | no — they render as literal text today |
| FR-009 | SEO parity proven | As a site owner, I want every built page checked for description, self-canonical and Open Graph tags, and a parity checklist against DocFX's SEO rules, so that `seo_postprocess.py` and `seo_verify.py` can be retired at #6943. | Medium | Open | [build] | no — no check over the doc-kitty build exists |
| FR-010 | No dangling links after unpublishing | As a reader, I want published pages to stop linking to pages this mission unpublishes, so that no link breaks. | High | Open | [build] | yes — paired with FR-004's strict link gate on the same tree |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Gate time | The added gate and check steps add at most 3 minutes to the `docs-site` job on CI. | Performance | Medium | Open |
| NFR-002 | No credential, pinned actions | 0 secrets; every third-party action pinned by commit; checks are Python standard library or the pinned doc-kitty bins. | Security | High | Open |
| NFR-003 | Check fidelity | The built-site check fails on 100% of the mutant fixtures (one per surface). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Immutable bodies | Bodies of `plans/`, `reports/`, `changelog/`, `archive/` pages and ADRs are not rewritten; frontmatter edits, file moves and ADR amendment sections are allowed. | Business | High | Open |
| C-002 | Single authority | No second hand-written list of excluded or unpublished pages; the contract module, `sections.yaml` and frontmatter are the sources. | Technical | High | Open |
| C-003 | DocFX unchanged | `docs-pages.yml`, `seo_postprocess.py`, `seo_verify.py` and the DocFX PlantUML path stay as they are; DocFX keeps deploying. | Business | High | Open |
| C-004 | Bot surfaces | `docs/development/page-inventory.yaml`, `docs/development/docs-retrieval-index.yaml` and ADR index tables are not edited (the `ci/regen-docs-index` bot regenerates them). | Technical | High | Open |
| C-005 | Out of scope | Redirect config generation (#6933), diagrams (#6936), cutover and deleting `docs/llms.txt` (#6938), glossary/hubs/ADR index (#6940–#6942), DocFX retirement (#6943). | Business | High | Open |
| C-006 | No new gates beyond the issues | No size or ratchet gate and no allowlist; any exception is recorded as priced debt. | Technical | High | Open |
| C-007 | Upstream gaps | A doc-kitty gap is filed upstream (spec-kitty/doc-kitty) before any local workaround, and named in the PR. | Technical | High | Open |

### Key Entities

- **Unpublished set**: excluded folders, draft folders, archived pages — the contract module's one definition and its JSON projection.
- **Built-site check**: a standard-library script that walks `site/dist` and its surfaces, with mutant fixtures.
- **Version stance**: the D-9 block carried into the generated `llms.txt`.
- **Parity checklist**: DocFX SEO rule → doc-kitty equivalent or upstream issue.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 unpublished routes on any built surface; 12 working-note pages and the retired pages no longer built. — [build] · no-op passable: no
- **SC-002**: The `docs-site` gate runs the frontmatter gate, the strict link gate and the built-site check and is green on the landing pull request. — [build] · no-op passable: no
- **SC-003**: `llms.txt` exists with the stance block, and its machine-index link resolves. — [build] · no-op passable: no
- **SC-004**: 100% of built pages carry description, self-canonical and Open Graph tags; 0 literal alert markers. — [build] · no-op passable: no
- **SC-005**: Every mutant fixture makes the built-site check fail. — [build] · no-op passable: no

## Assumptions

- doc-kitty v0.7.0 (`5acb83c`, pinned since PR #7480) offers `githubAlerts`, `llmsTxtRoute`, `agentIndexRoute`, folder `exclude`, `DK_PUBLISH_DRAFTS` and the gate bins named in the grounding note; it has no `llms.txt` preamble option (doc-kitty #265), so a thin wrapper inserts the stance.
- The SEO tags are already emitted by Starlight + doc-kitty (650/650 pages in a local build); this mission proves and pins it.
- This branch is based on PR #7486 (shared build workflow); it is rebased onto `main` once #7486 lands.
