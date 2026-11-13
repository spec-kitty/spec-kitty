# Mission Specification: Rename section indexes to README.md; docs staleness inventory and retired-surface gate

**Mission Branch**: `kitty/mission-readme-rename-and-docs-audit-01M78WZM` (lands on `issue-6939-readme-rename-and-audit`)
**Created**: 2026-11-12
**Status**: Draft
**Input**: Operator brief: deliver #6939 (rename the docs section `index.md` pages to `README.md`) and #7520 (the docs refresh audit: a staleness inventory and a retired-surface gate, first sub-issue of epic #3891) as one Mission, rename first, inventory on the final paths.

## Context

- DocFX is retired (#6943, PR #7609). ADR `2026-10-31-1` D-1 and D-13 step 5 make the rename the next step: every section index becomes `README.md` and the site's `indexBasename` narrows to `README`.
- The issue counts 60 files. Today 59 remain: `docs/templates/index.md` left with the DocFX template in #6943. The 4 folders #6928 resolved (`adr/1.x`, `adr/2.x`, `adr/3.x`, `architecture`) are among the 59 and rename like the rest.
- A first attempt (PR #7040, closed) is reused in part, as the operator's 2026-11-03 comment on #6939 directs: its 60-pair rename map, `tests/docs/test_section_index_basename.py` with its planted control, and the `freshen_adr_inventory.py` basename switch.
- Since #7040: links are rewritten through the standing moves ledger `site/moves.yaml` (#6927), and `related:` frontmatter holds slugs (#6929), which the rename does not change.
- Epic #3891 measured 341 published living pages and 33 files naming a retired surface. Every section pass (#7522–#7528) reads the audit this Mission produces. The section passes themselves are out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Section landing pages are README.md everywhere (Priority: P1)

A maintainer browsing `docs/` on GitHub or in an editor finds each section's landing page as `README.md`, as in the sibling repositories, and the published site serves the same URLs as before.

**Why this priority**: it is the last step of the doc-kitty migration (ADR D-13 step 5) and fixes the page paths every later docs pass keys on.

**Independent Test**: no `index.md` remains under `docs/`; the site builds with `indexBasename: 'README'`; every baseline URL is still covered and the redirect map is unchanged.

**Acceptance Scenarios**:

1. **Given** the 59 `docs/**/index.md` files, **When** the Mission lands, **Then** each is `README.md` in the same folder with its history kept (`git mv`), and a test fails if an `index.md` reappears.
2. **Given** a link anywhere in the repository to a renamed page, **When** the Mission lands, **Then** it points at the `README.md` (living pages: every reference; immutable pages: link targets only, per ADR D-7).
3. **Given** the URL baseline, **When** the redirect generator runs with `--check` and the built site is checked, **Then** every baseline URL resolves and `dir/index.html` is still served by the section page.

### User Story 2 - An inventory tells each section pass what is stale (Priority: P1)

The author of a section pass (#7522–#7528) opens one generated inventory and sees, per published living page, when its content last really changed, which code paths and commands it names and whether they still exist, its named reader, its retired-surface references, its text-drawn diagrams and its Divio type.

**Why this priority**: every section sub-issue reads its page list from this inventory (#7520 "Do this first").

**Independent Test**: one command regenerates the inventory byte for byte from the tree; a test pins the published-living page set and the per-page fields on fixtures.

**Acceptance Scenarios**:

1. **Given** a page whose only recent commits change frontmatter or whitespace, **When** the inventory is generated, **Then** its last real content change is the older commit that changed its body text.
2. **Given** a page that names `src/doctrine/` or `spec-kitty merge`, **When** the inventory is generated, **Then** the page lists that retired surface.
3. **Given** a page naming a code path that does not exist or a `spec-kitty` command the CLI does not have, **When** the inventory is generated, **Then** the page lists it as missing.

### User Story 3 - A page cannot newly name a retired surface (Priority: P2)

A contributor who adds a mention of a retired surface (for example `spec-kitty merge` or `src/doctrine/`) to a published living page gets a red docs-lint check naming the page and the surface. Existing mentions are tracked in a burn-down list that only shrinks.

**Why this priority**: it stops the class from coming back while the section passes drain it.

**Independent Test**: the gate is green on the tree; a planted mention fails it; a burn-down entry with no live hit fails it; growing the list fails the ratchet.

**Acceptance Scenarios**:

1. **Given** the committed burn-down list, **When** the gate runs on the tree, **Then** it passes.
2. **Given** a published living page with a new retired-surface mention, **When** the gate runs, **Then** it fails naming the page and the surface.
3. **Given** a section pass that removes the last mention of a surface from a page, **When** the gate runs, **Then** it fails until the stale burn-down entry is removed.

### Edge Cases

- A folder that moved `README.md` → `index.md` earlier (#3914, #6928) now moves back. The append-only ledger records the return as a new entry; that must not read as a cycle.
- `docs/assets/index.md`, `docs/contracts/index.md` and the 8 archived indexes have no legacy `dir/index.html` in the baseline. An index rename keeps its directory route, so it creates no URL to protect.
- Immutable pages (ADRs, `plans/`, `reports/`, `changelog/`, `archive/`) change only link targets; prose that names a path is history and stays.
- The generated surfaces (`docs/development/docs-retrieval-index.yaml`, `page-inventory.yaml`) are bot-owned and stay untouched in the pull request; the ADR era tables move with their files without counting as new rows.
- A retired word inside a live identifier (`spec-kitty merge-driver-*`, `spec-kitty charter sync`) is not a hit.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Rename every section index | As a maintainer, I want every `docs/**/index.md` renamed to `README.md` with `git mv` so that each section's landing page has one basename. | High | Open | [build] | no |
| FR-002 | Guard the basename | As a maintainer, I want a test that fails when an `index.md` exists under `docs/`, with a planted control that makes it fail, so that the old basename cannot return. | High | Open | [ratchet] | no — the planted `index.md` control fails the same walk |
| FR-003 | Record the rename in the moves ledger | As a docs tool, I want each rename appended to `site/moves.yaml` (`/x/index.html -> /x/README.html`), and the ledger to read a later move back into a route as superseding that route's earlier move away, so that the link rewriters and the redirect generator see one history without a cycle. | High | Open | [build] | no |
| FR-004 | Rewrite links through the ledger | As a reader, I want every link to a renamed page rewritten by the ledger-driven rewriters so that no link breaks; immutable pages change link targets only. | High | Open | [build] | no |
| FR-005 | Narrow indexBasename | As the site build, I want `INDEX_BASENAMES` to be `('README',)` and the generated `site/dockitty-contract.json` to follow so that doc-kitty reads only `README.md` as a section index. | High | Open | [build] | no |
| FR-006 | Every reader names README.md | As a maintainer, I want every script, workflow comment, template and test that names a section `index.md` updated (`freshen_adr_inventory.py`, `regen_docs_index.py`, `generated_docs_surfaces.py`, `check_generated_docs_untouched.py`, `site_redirects.py`, `touched_set_gates.py`, `site_built_check.py`, the docs-index workflow) so that tooling matches the tree. | High | Open | [build] | no |
| FR-007 | Legacy URLs keep resolving | As a visitor with an old link, I want every `site/url-baseline.txt` route to stay covered, with `site/legacy-redirects.json` unchanged by the rename, so that no URL breaks. | High | Open | [ratchet] | yes — paired with FR-001's rename on the same tree |
| FR-008 | ADR era tables move without new rows | As the generated-surface guard, I want an era table that moves from `index.md` to `README.md` in the same era folder not to count as new rows, so that the rename passes `check_generated_docs_untouched`. | Medium | Open | [build] | no |
| FR-009 | Staleness inventory | As a section-pass author, I want one command to generate an inventory of every published living page (published set minus `adr/`, `plans/`, `reports/`, `changelog/`, `archive/`) with: last real content change (frontmatter-only and whitespace-only commits ignored), named code paths and `spec-kitty` commands checked against the tree and the CLI, the named reader from `docs/context/audience/`, retired-surface references, text-drawn diagrams, and the Divio type with a mixed-type flag, so that each section pass starts from evidence. | High | Open | [build] | no |
| FR-010 | One retired-surface authority | As a gate author, I want the retired set read from one source shared with `tests/architectural/test_no_retired_subsystems.py` so that the code gate and the docs gate cannot drift. | High | Open | [build] | no |
| FR-011 | Retired-surface gate | As a contributor, I want docs lint to fail when a published living page newly names a retired surface, naming the page and the surface, so that the class cannot return. | High | Open | [ratchet] | no — a planted mention fails the gate on the same fixture |
| FR-012 | Shrink-only burn-down | As the epic owner, I want existing hits in a tracked burn-down list, each pointing at its section sub-issue (#7522–#7528), with a stale entry failing the gate and the list size ratcheted shrink-only, so that hits are drained and never silently allowed. | High | Open | [ratchet] | no |
| FR-013 | Gate in the docs lint lane | As CI, I want the gate run in the always-on `docs-lint` job of `ci-router.yml`, with the scrub record and the job pins updated, so that every PR runs it. | Medium | Open | [build] | no |
| FR-014 | Per-section page lists | As the operator, I want a per-section page list for #7522–#7528 generated from the inventory into the Mission directory so that it can be posted to the sub-issues. | Medium | Open | [build] | no |
| FR-015 | ADR amendment and changelog | As a reader of the decision record, I want ADR `2026-10-31-1` to gain `## Amendment 2026-11-12 (section indexes renamed)` and the changelog a fragment, so that the change is recorded. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Reproducible inventory | Two runs of the inventory command on the same commit produce byte-identical output. | Reliability | High | Open |
| NFR-002 | Gate cost | The retired-surface gate runs in under 10 s on the docs-lint runner and needs no git history. | Performance | Medium | Open |
| NFR-003 | Strict link check | `dockitty-check-links --strict` reports 0 broken links after the rename. | Reliability | High | Open |
| NFR-004 | Code quality | Every touched Python module passes `ruff check`, `ruff format --check --force-exclude` and `mypy --strict` with no new suppression. | Maintainability | High | Open |
| NFR-005 | Committed-state gates | Every gate is run on committed state before review. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Immutable bodies | ADR, `plans/`, `reports/`, `changelog/` and `archive/` bodies change only in link targets (ADR D-7); ADR bodies and earlier amendments are never edited otherwise. | Technical | High | Open |
| C-002 | Generated surfaces | The pull request does not edit `docs/development/docs-retrieval-index.yaml` or `page-inventory.yaml`; the post-merge bot regenerates them. A gate red only because of them is named in the PR, never weakened. | Technical | High | Open |
| C-003 | No silent allowlist | Existing retired-surface hits live in a visible burn-down list tied to issues; no gate is weakened, skipped or xfailed. | Technical | High | Open |
| C-004 | Out of scope | The section editorial passes (#7522–#7528), the content of any page beyond link targets, and `packs/` are out of scope. | Business | High | Open |
| C-005 | Ledger is append-only | `site/moves.yaml` gains entries; no recorded line is edited or removed. | Technical | High | Open |

### Key Entities

- **Section index**: a folder's landing page; after the Mission, always `README.md`.
- **Move**: a `site/moves.yaml` entry `from -> to` in legacy route form; the rename adds one per section index.
- **Inventory record**: one published living page with its audit fields (FR-009).
- **Retired surface**: a removed path, package or command, with the ref that retired it and the replacement to name.
- **Burn-down entry**: a page and a retired surface it still names, with the section sub-issue that drains it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 `index.md` files under `docs/`; 59 `README.md` section indexes added by rename. — [build] · no-op passable: no
- **SC-002**: `site/legacy-redirects.json` is byte-identical before and after the rename, and every baseline URL is covered. — [ratchet] · no-op passable: yes
- **SC-003**: `dockitty-check-links --strict` reports 0 broken links. — [ratchet] · no-op passable: no
- **SC-004**: The inventory covers every published living page (about 340) and regenerates byte for byte with one command. — [build] · no-op passable: no
- **SC-005**: The retired-surface gate is green on the tree, red on a planted mention, and every burn-down entry names one of #7522–#7528. — [ratchet] · no-op passable: no
