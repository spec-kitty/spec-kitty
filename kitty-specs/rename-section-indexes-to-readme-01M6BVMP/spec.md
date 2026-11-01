# Mission Specification: Rename the 60 `index.md` section indexes to `README.md`

**Mission Branch**: `issue-6939-rename-section-indexes-to-readme`
**Created**: 2026-11-01
**Status**: Draft
**Input**: Issue #6939 "Rename the 60 `index.md` section indexes to `README.md`"
(part of #6100; implements ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md`
D-1, D-7; plan step S-13). Operator ruling for this dispatch (2026-11-01): the
unlanded doc-kitty chain no longer blocks opening the work, but the PR is opened as a
**draft** and never merged while DocFX is still the live deployer.

## Problem

Every documentation section landing page is named `index.md` (60 of them under
`docs/`). ADR 2026-10-31-1 D-1 makes `README.md` the section landing basename on the
doc-kitty site (`indexBasename: 'README'`), because DocFX maps `README.md` onto the
same `dir/index.html` output URL. The rename has to happen once, as one mechanical
change, or every later doc-kitty step carries a mixed naming surface.

Grounding (2026-11-01, `origin/main` = `287a226cfe`): 60 `docs/**/index.md` still
exist, 8 `toc.yml` files carry 46 `index.md` hrefs, 194 Markdown files link to an
`index.md` target (542 occurrences), 128 files carry 183 frontmatter `related:` paths
that end in `index.md`. Four of the 60 target directories already hold a `README.md`:
`docs/adr/{1.x,2.x,3.x}` (redirect stubs pointing at the sibling `index.md`) and
`docs/architecture` (a second landing page carrying the boundary rule).

## Scope boundary (what this mission does NOT do)

The downstream doc-kitty chain is unlanded: there is no `site/` tree and no
`site/moves.yaml` (#6927), so link rewriting cannot be driven through the moves
ledger; DocFX is still the live deployer (`docs/docfx.json`,
`.github/workflows/docs-pages.yml`), so the rendered URLs of the renamed pages are
not yet `dir/index.html`; and the docs-structural-lint asset and its Spec Kitty
config live in the external pack (not editable in this repository). This mission
renames and reconciles every in-repo reference; it does not retire DocFX, does not
build `site/`, and does not weaken a gate to hide either gap. Each such gap is named
in the PR body under `## Deferred`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A contributor finds a section landing page by convention (Priority: P1)

A reader browses `docs/guides/how-to/missions/` on GitHub or in an editor. Every
section directory presents its landing page as that directory's `README.md`, the
same way the repository root does, instead of a second convention (`index.md`).

**Why this priority**: This is the change itself; without it nothing else in the
mission matters.

**Independent Test**: `find docs -name index.md` returns nothing, and every one of
the 60 former locations has a `README.md` with the page's previous content.

**Acceptance Scenarios**:

1. **Given** the `main` tree with 60 `index.md` pages under `docs/`, **when** the
   rename lands, **then** no `index.md` remains anywhere under `docs/` and each of
   the 60 directories has a `README.md` carrying that page's content and frontmatter.
2. **Given** a directory that already held a `README.md` (`docs/adr/{1.x,2.x,3.x}`,
   `docs/architecture`), **when** the rename lands, **then** that directory has
   exactly one landing page and no content is lost: the three redirect stubs are
   replaced by the page they pointed at, and the architecture landing page and page
   index are merged into one `README.md`.

### User Story 2 - Every in-repo link to a renamed page still resolves (Priority: P1)

A reader follows a link from any docs page, `toc.yml`, or frontmatter `related:`
entry to a section landing page and lands on the page, because the target was
rewritten in the same change.

**Why this priority**: A rename that leaves dangling links is worse than no rename:
it breaks navigation for every reader and every link gate.

**Independent Test**: For every link target, `toc` href and `related:` path under
`docs/` that names one of the 60 renamed pages, the rewritten target resolves to an
existing file on disk, and the in-tree link/related validators agree.

**Acceptance Scenarios**:

1. **Given** a page containing `[Guides](guides/index.md)`, **when** the rename
   lands, **then** the target reads `guides/README.md` and resolves on disk.
2. **Given** `docs/toc.yml` and the seven section `toc.yml` files, **when** the
   rename lands, **then** every `href` names `README.md` and no `href` names an
   `index.md` that no longer exists.
3. **Given** a page whose frontmatter `related:` list names
   `docs/adr/4.x/index.md`, **when** the rename lands, **then** the entry reads
   `docs/adr/4.x/README.md` and the related validator reports no dangling path.

### User Story 3 - The tooling that owns the landing-page basename agrees with the tree (Priority: P2)

An operator runs the docs generators and the ADR inventory freshener against the
renamed tree and they maintain the same pages, rather than recreating `index.md` or
silently maintaining nothing.

**Why this priority**: `scripts/docs/freshen_adr_inventory.py` prefers `index.md` as
the era landing page; left alone it re-creates or ignores the wrong file, and the ADR
era tables stop being maintained.

**Independent Test**: The ADR era table generator, run against the renamed tree,
maintains `docs/adr/<era>/README.md`, and the regen classifier still recognises the
era landing page after the rename.

**Acceptance Scenarios**:

1. **Given** `freshen_adr_inventory.py` with `_INDEX_NAME = "index.md"`, **when** the
   rename lands, **then** its canonical landing basename is `README.md` and the era
   tables are read from and written to `docs/adr/<era>/README.md`.
2. **Given** the docs index/page-inventory generators, **when** they run over the
   renamed tree, **then** they enumerate the renamed pages and produce no `index.md`
   path.

### Edge Cases

- A directory that already holds `README.md` (the 4 collisions): the rename must not
  fail with "destination exists", and must not strand the old stub content.
- A link written in prose, in a fenced code block, or inside an immutable ADR body:
  only link *targets* are rewritten (ADR 2026-10-31-1 D-7 allows exactly that body
  change); prose that names a path as history is left alone.
- A `related:` path that points at a page outside `docs/` (none today): the rewrite is
  anchored on the rename map, so unrelated `index.md` names are untouched.
- `docs/adr/<era>/index.md` is a generated-surface input (its table rows are owned by
  the regen bot): the file is renamed, but its edited table rows must not be
  hand-changed in this PR beyond the move.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Rename all 60 section indexes | As a reader, I want each section landing page at `README.md` so that one basename convention holds across `docs/`. | High | Open | [build] | no — a no-op leaves 60 `index.md` files, and a test asserts none remain |
| FR-002 | Resolve the four existing-README collisions | As a maintainer, I want each collided directory to keep one landing page with no content lost so that the rename does not silently drop a page. | High | Open | [build] | no — a no-op leaves two landing pages per collided directory |
| FR-003 | Rewrite in-docs link targets | As a reader, I want every relative link to a renamed page to point at the new name so that navigation still works. | High | Open | [build] | no — a no-op leaves dangling targets the link validator reports |
| FR-004 | Rewrite `toc.yml` hrefs | As a site reader, I want the 8 `toc.yml` files to name the renamed pages so that the table of contents still resolves. | High | Open | [build] | no — a no-op leaves dead `href`s |
| FR-005 | Rewrite frontmatter `related:` paths | As a maintainer, I want every `related:` path to resolve after the rename so that the related validator stays green. | High | Open | [build] | no — a no-op leaves 183 dangling related paths |
| FR-006 | Narrow the ADR inventory landing basename | As an operator, I want the era landing basename to be `README.md` so that the ADR era tables are maintained on the renamed pages. | High | Open | [build] | no — a no-op keeps maintaining `index.md` |
| FR-007 | Update the regen surface definitions and readers | As an operator, I want `scripts/ci/regen_docs_index.py` and the `scripts/docs` readers to name `README.md` as the era landing page so that the regenerator does not re-create `index.md`. | High | Open | [build] | no — a no-op leaves the docstrings/constants pointing at a page that no longer exists |
| FR-008 | Guard the invariant with a test | As a maintainer, I want a test that fails when an `index.md` reappears under `docs/` so that the convention cannot silently re-drift. | High | Open | [ratchet] | no — a no-op leaves no guard, proved by a fixture that adds an `index.md` and must fail |
| FR-009 | Keep the docs test suites green | As a maintainer, I want the `tests/docs` suites that assert landing-page basenames to assert the new convention so that the gate is neither skipped nor weakened. | High | Open | [build] | no — a no-op leaves live-tree floors keyed on a basename that no longer exists |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Complete reconciliation | After the change, zero `git grep` hits for an `index.md` *link target*, `toc` `href`, or `related:` path under `docs/` resolve to a path that does not exist. | Reliability | High | Open |
| NFR-002 | Content preservation | The 60 renamed pages keep their body byte-for-byte apart from link targets; the only content merges are the 4 collided directories, each of which keeps every unique section from both files. | Reliability | High | Open |
| NFR-003 | Generated surfaces untouched by the PR | `docs/development/docs-retrieval-index.yaml` and `docs/development/page-inventory.yaml` are not edited by this PR (the `check_generated_docs_untouched` guard); their regeneration is the bot's post-merge job. | Process | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Only link targets change in immutable files | In pages treated as immutable history, only link targets are rewritten (ADR 2026-10-31-1 D-7); prose, code blocks and rationale stay untouched. | Technical | High | Open |
| C-002 | No gate is weakened or skipped | A gate that cannot pass because the doc-kitty chain is unlanded is reported in the PR body, never disabled, xfailed or skipped. | Process | High | Open |
| C-003 | Pack content is not edited in core | The docs-structural-lint asset and the Spec Kitty lint config live in the external pack and are not modified here; the consequence for their basename assumptions is reported. | Technical | High | Open |
| C-004 | Draft PR, never merged | The PR opens as a draft with `pr:pause-ci`; nothing is merged, no auto-merge is armed and `main` is never pushed. | Process | High | Open |

### Key Entities

- **Section landing page**: a page at the root of a docs section directory; today
  `index.md`, afterwards `README.md`.
- **Rename map**: the 60 `(old path, new path)` pairs that drive every rewrite.
- **Generated docs surface**: the retrieval index, the page inventory and the ADR era
  table rows, regenerated on `main` by the `ci/regen-docs-index` bot.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `find docs -name index.md` prints nothing, and `find docs -name README.md` prints 60 more entries than before the change. — [build] · no-op passable: no
- **SC-002**: Every rewritten link target, `toc` `href` and `related:` path resolves to an existing file (0 dangling), verified by script over the whole `docs/` tree. — [build] · no-op passable: no
- **SC-003**: `uv run pytest tests/docs tests/ci/test_regen_docs_index.py tests/ci/test_check_generated_docs_untouched.py` passes, with the deprecated-basename floors updated rather than removed. — [build] · no-op passable: no
- **SC-004**: `scripts.docs.freshen_adr_inventory` over the renamed tree reports the same ADR rows for all four eras and writes to `docs/adr/<era>/README.md`. — [build] · no-op passable: no
- **SC-005**: `python -m scripts.docs.check_docs_freshness --ci` reports errors=0. — [build] · no-op passable: no
- **SC-006**: The PR body names every check that is red for a reason outside this diff, with the issue that unblocks it. — [build] · no-op passable: no
