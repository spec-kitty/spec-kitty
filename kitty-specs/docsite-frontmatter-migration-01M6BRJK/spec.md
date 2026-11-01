# Mission Specification: Docsite build-blocking frontmatter migration

**Mission Branch**: `issue-6929-docsite-frontmatter-migration`
**Created**: 2026-11-01
**Status**: Draft
**Input**: Issue #6929 build-blocking frontmatter migration (docsite to doc-kitty). Brief: the operator's dispatch for #6929 (epic #6100, plan step S-4b, ADR `2026-10-31-1` D-7 and D-8).

## Intent Summary (brief-intake mode)

The dispatch brief is comprehensive (objective, slices, constraints, non-goals, Done-when), so
discovery ran in brief-intake mode with no open questions to the operator. Two design choices the
brief left open were recorded as resolved Decision Moments and are flagged for the operator in the
pull request (see Assumptions).

- **Primary actor:** the Spec Kitty maintainer who will scaffold the doc-kitty site (#6930) and
  build the real `docs/` tree with it.
- **Trigger:** the doc-kitty build of `docs/` fails on frontmatter that DocFX accepted.
- **Outcome:** one doc-kitty build of the unmodified-in-body `docs/` tree passes, while DocFX keeps
  publishing and `spec-kitty docs query` keeps answering exactly as before.
- **Invariant:** the bodies of ADRs, plans, reports and changelog entries do not change by a single
  byte; only their frontmatter may.
- **Boundary:** this mission changes frontmatter and the core scripts that read the changed fields.
  It adds no site project, no redirects, and no `kind`/`type`/`updated` completion (#6931).

Grounding: [`research/code-grounding.md`](research/code-grounding.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The real docs tree builds on doc-kitty (Priority: P1)

A maintainer points a doc-kitty site at `../docs` (both `README` and `index` as section index,
archive, reports, convergence and the changelog fragment folder left out) and runs the build. It
passes, and every published page is emitted.

**Why this priority**: it is what blocks the site scaffold (#6930) and the whole epic.

**Independent Test**: run the spike's one-off build (recorded commands) against this branch.

**Acceptance Scenarios**:

1. **Given** the migrated tree, **When** the one-off doc-kitty build runs with drafts off, **Then**
   it exits 0 and reports the number of pages built.
2. **Given** the base tree, **When** the same build runs, **Then** it fails on the first `audience`
   string (control).

---

### User Story 2 - History stays byte-identical (Priority: P1)

A reviewer can trust that no immutable record was rewritten: the body of every ADR, plan, report and
changelog file is the same before and after.

**Independent Test**: a test hashes each immutable file's body on the base commit and on the
working tree and finds no difference.

**Acceptance Scenarios**:

1. **Given** the migration applied, **When** the body-hash test runs, **Then** every body hash
   matches the base.
2. **Given** a one-character body edit to one ADR, **When** the test runs, **Then** it fails and
   names that file.

---

### User Story 3 - Existing docs tooling keeps working (Priority: P1)

A maintainer runs `spec-kitty docs query`, the DocFX build and the `scripts/docs` audience and
related checks; each still works and each now understands the new field shapes.

**Independent Test**: the ported checks' own tests, plus `tests/docs/` and `tests/specify_cli/docs/`.

**Acceptance Scenarios**:

1. **Given** a page whose `audience` names a persona that does not exist, **When** the audience
   check runs, **Then** it reports that page as dangling.
2. **Given** a page whose `related` names a slug with no page, **When** the related check runs,
   **Then** it reports that edge as dangling.
3. **Given** the migrated tree, **When** both checks run over `docs/`, **Then** they report zero
   dangling entries.

---

### User Story 4 - The new shape cannot silently regress (Priority: P2)

A contributor who adds a page with an old-style `audience` path or a repository-path `related`
entry gets a failing test, not a broken site build months later.

**Independent Test**: a corpus-shape test over `docs/`.

**Acceptance Scenarios**:

1. **Given** the migrated tree, **When** the shape test runs, **Then** it passes.
2. **Given** one page reverted to a path-string `audience`, **When** the shape test runs, **Then**
   it fails and names the page.

### Edge Cases

- A free-text `audience` value (`end-users`, `internal / pre-launch operators`) has no persona
  page: it keeps its text as the profile and is not reported as dangling (doc-kitty treats it as a
  soft miss).
- A `related` entry whose target file no longer exists (2 today): dropped, and listed in the
  migration report.
- A `related` entry naming a `README.md` or `index.md` folder index: becomes the folder slug.
- An ADR era index (`docs/adr/<era>/index.md` / `README.md`) is a generated surface and is not an ADR:
  never touched.
- `docs/architecture/README.md` and the three ADR-era `README.md` stubs belong to #6928: never touched.
- Changelog fragments (`docs/changelog/unreleased/`) are not pages: never touched, excluded from the build.
- Re-running the migration on an already-migrated tree changes nothing.

## Domain Language

| Term | Meaning here | Avoid |
| --- | --- | --- |
| Published page | A page doc-kitty builds with drafts off: not in an excluded folder and `doc_status` other than `draft` (absent counts as `draft`). | "public page" |
| Excluded folder | A `docs/` folder left out of the build: `archive`, `reports`, `convergence`, `changelog/unreleased`. | "ignored", "hidden" |
| Slug | A page's path under `docs/` without `.md`, a trailing `README`/`index` (any case) removed; the docs root page is the empty slug. | "route", "URL" (different things) |
| Immutable body | Everything after the closing frontmatter fence of an ADR, plan, report or changelog file. | — |
| Mission | Canonical term; never "feature". | "feature" |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Immutable body hash test | As a reviewer, I want a test that hashes the body of every ADR, plan, report and changelog file on the base and on the working tree and fails on any difference, so that history cannot be rewritten by the migration. | High | Open | [build] | no — paired with a mutated-body fixture that must fail |
| FR-002 | `audience` becomes a profile list | As a maintainer, I want every `audience` path string (scalar or list) rewritten to `[{profile, guidance_text}]`, where `profile` is the persona path under `docs/context/audience/` without `.md`, so that doc-kitty's schema accepts it. | High | Open | [build] | no — the shape test fails on the base tree |
| FR-003 | Audience readers ported | As a maintainer, I want `audience_resolver.py` and `touched_set_gates.py` to read the profile list (resolving a profile to `docs/context/audience/<profile>.md` or `<profile>/index.md`), so that the checks keep working on the new shape. | High | Open | [build] | no — a dangling-profile fixture must be reported |
| FR-004 | Excluded folders need no frontmatter edit | As a maintainer, I want archive, reports, convergence and the changelog fragment folder left out of the build by doc-kitty's native folder exclusion, with no title/description backfill, so that immutable reports are not touched for the build's sake. | High | Open | [build] | no — the control build without exclusion fails |
| FR-005 | `related` becomes slugs | As a maintainer, I want every `related` entry that names a published Markdown page rewritten to that page's slug, so that doc-kitty resolves it. | High | Open | [build] | no — the shape test fails on the base tree |
| FR-006 | Unresolvable references move to `external_references` | As a maintainer, I want every `related` entry that doc-kitty would not resolve for its page moved to `external_references` as `{url, title}` with a repository URL — on a published page: anything that is not a published page; on a draft page: anything outside `docs/`, non-Markdown, or in an excluded folder; on an excluded page (never built): only paths that are not docs pages — and every entry whose target no longer exists dropped, so that no build of any page fails on `related`. | High | Open | [build] | no — the shape test fails on the base tree |
| FR-007 | Related reader ported | As a maintainer, I want `related_validator.py` to read slugs (string or `{ref, note}`), resolve them as doc-kitty does, and report an entry naming an unpublished page, so that the check keeps working on the new shape. | High | Open | [build] | no — dangling and unpublished fixtures must be reported |
| FR-008 | ADRs gain `doc_status` and `kind` | As a maintainer, I want every dated ADR to carry `doc_status` (`Accepted`/`Proposed` → `active`, `Superseded` → `superseded`) and `kind: ADR`, keeping `status`, `date` and `superseded_by` unchanged, so that no ADR vanishes from the site as a draft. | High | Open | [build] | no — the shape test fails on the base tree |
| FR-009 | Corpus-shape invariant | As a contributor, I want a test over `docs/` that fails on a path-string `audience`, a `related` entry that is not a slug of an existing page, a published page whose `related` names an unpublished page, a draft page whose `related` names an excluded page, or an ADR missing `doc_status`/`kind` or carrying a mismatched `doc_status`, so that the new shape cannot regress unnoticed. | High | Open | [build] | no — red on the base tree, green after |
| FR-010 | Re-runnable migration | As a maintainer, I want the migration to be a committed script that is idempotent and touches frontmatter only, so that a later conflict with another docs PR is resolved by re-running it. | Medium | Open | [build] | no — a second run must report zero changes |
| FR-011 | One-off doc-kitty build passes | As a maintainer, I want the spike's one-off build of `docs/` (`indexBasename: ['README', 'index']`, native exclusion, drafts off) to pass, with the commands and page count recorded, so that #6930 can start. | High | Open | [build] | no — control build on the base fails |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Frontmatter-only edits | 0 bytes change after the closing frontmatter fence in any file under `docs/` the migration touches (all files, not only immutable ones). | Integrity | High | Open |
| NFR-002 | Docs query unchanged | `spec-kitty docs query` returns identical results for 3 sample queries before and after (titles, abstracts and Divio types are unchanged). | Compatibility | High | Open |
| NFR-003 | Fast checks | The body-hash and corpus-shape tests each finish in under 10 s on the full `docs/` tree. | Performance | Medium | Open |
| NFR-004 | Code quality | New and changed Python passes `ruff check`, `ruff format --check --force-exclude` and `mypy` with zero findings; no function exceeds complexity 15; changed lines meet the 90% diff-coverage gate. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Readers in the same PR | A field's readers are ported in the same pull request as the field change, so DocFX and `docs query` keep working at every merge. | Technical | High | Open |
| C-002 | Non-goals | No `site/` project (#6930), no redirects, no `kind`/`type`/`updated` completion beyond ADR `kind` (#6931), no file moves or renames, no `doc_status` vocabulary normalisation. | Scope | High | Open |
| C-003 | Hands off parallel work | Do not touch `docs/adr/*/README.md`, `docs/architecture/README.md` (#6927/#6928) or the generated surfaces (docs index, page inventory, ADR era index tables). | Coordination | High | Open |
| C-004 | Upstream not patched | doc-kitty is consumed unmodified; a gap is filed upstream, not shimmed in core (ADR D-14). | Technical | High | Open |
| C-005 | Terminology | Mission, never feature; the legacy-terminology gate passes. | Governance | Medium | Open |

### Key Entities

- **Audience entry**: `{profile, guidance_text}`; `profile` names a persona under `docs/context/audience/`.
- **Related entry**: a slug of a published page (or `{ref, note}`).
- **External reference**: `{url, title}` for anything that is not a published page.
- **ADR frontmatter**: `title`, `status`, `date`, optional `superseded_by`, plus `doc_status` and `kind: ADR`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The one-off doc-kitty build of `docs/` passes and emits at least as many pages as the spike's 637. — [build] · no-op passable: no
- **SC-002**: 0 immutable bodies differ from the base. — [build] · no-op passable: no (paired with a mutated fixture)
- **SC-003**: 0 pages carry a path-string `audience` or a non-slug `related` entry; 0 ADRs lack `doc_status`/`kind`. — [build] · no-op passable: no
- **SC-004**: `tests/docs/` and `tests/specify_cli/docs/` pass with no new failures against the base. — [ratchet] · no-op passable: yes (a ratchet; the build criteria above carry the non-vacuity)
- **SC-005**: The audience and related checks report 0 dangling entries over `docs/` after the migration. — [build] · no-op passable: no (dangling fixtures must report)

## Assumptions

- **`guidance_text` (Decision Moment `01M6BRRS43THXH8SZ861AFG8M3`)**: the mechanical migration writes
  `Written for the <persona title> reader.`; page-specific guidance is authoring work for #6931.
- **Which `related` entries leave `related` (Decision Moment `01M6BW2S981SKQWXKCBNQD8RBW`, after WP01 review)**:
  source-aware, mirroring what doc-kitty resolves — see FR-006. Excluded history keeps its slugs.
- **Unpublished `related` targets (Decision Moment `01M6BRRXG0MVX09DH92W1NTEWP`)**: moved to
  `external_references` with a repository URL rather than into the body. The issue's literal options
  were "body link or drop"; most sources are `plans/` pages whose bodies are immutable, and a body
  link into an excluded folder is dead on both sites. Flagged for the operator.
- Excluded trees are migrated to the new shapes too (frontmatter only), so each reader supports one
  shape. They are never built, so this is uniformity, not a build need.
- DocFX does not read `audience`, `related`, `kind`, `doc_status` or `external_references` (it
  renders frontmatter as page metadata only), so DocFX output is unaffected. `dotnet`/`docfx` are
  not installed in this session; the DocFX build is verified by CI's docs workflow, not locally.
- #6932 (publication) will mark engineering-notes, investigations and research as drafts; the
  shape test will then name every published `related` entry into them, which #6932 must move.
