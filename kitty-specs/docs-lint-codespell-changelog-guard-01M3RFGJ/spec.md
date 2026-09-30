# Mission Specification: Docs lint: codespell and changelog Unreleased guard

**Mission Branch**: `issue-5426-docs-lint` (stacked on PR #5420, base `ffa3035571`)
**Created**: 2026-09-30
**Status**: Draft
**Input**: Issue #5426 — "Docs lint: codespell (typos + US spelling) and a changelog Unreleased style guard". The issue body is the source of truth; the tool choice (codespell) is decided and not re-litigated.

## Intent Summary (confirmed 2026-09-30)

- **Primary actor:** a contributor (human or agent) who edits user-facing docs or the changelog `## [Unreleased]` section and opens a pull request.
- **Trigger:** the pull request runs CI, or the contributor runs the checks locally before pushing.
- **Desired outcome:** a typo, a UK spelling in user-facing prose, or maintainer-only prose in the Unreleased section (internal IDs, ULIDs, evidence paths, boilerplate, the retired `spec-kitty merge` command, over-long entries) fails the check, and the failure names the file/entry and the exact fix.
- **Invariant:** both checks are green on the current text (the PR #5420 rewrite of the Unreleased section), and every rule has a planted-violation test that turns the check red. A check that cannot go red does not count.
- **Boundaries:** released changelog sections are never restyled; only real typos in them are corrected. US spelling is enforced only on user-facing prose (the Unreleased section, `docs/guides/`, `docs/context/`), not repo-wide.

Operator decisions recorded during discovery:
- Glossary headings spelled the UK way (`Organisation Tier`, `communication artefact`, `Trail Behaviour`) are renamed to US spelling, and each keeps its old anchor so existing links still resolve (decision `01M3RFQ90SJVVDQ7C4AV6W13FM`).
- `packs/built-in/**/*.md` (consumer-shipped prose) is added to the typo scope.
- Sequencing: this mission is stacked on PR #5420, and the pull request is rebased onto `main` once PR #5420 merges.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A typo in the docs fails the pull request (Priority: P1)

A contributor edits a page under `docs/`, `README.md` or a consumer-shipped doctrine pack page and introduces a misspelling. CI fails, naming the file, the line, the word and the suggested correction. The contributor either fixes the word or, if the word is legitimate jargon, adds it to the project's ignore list in one line.

**Why this priority**: typo detection covers the largest surface and every docs contributor. Nothing checks this today.

**Independent Test**: plant a misspelling in a scratch copy of an in-scope page, run the check, and see it fail naming that line. Remove the misspelling and see it pass. Add the word to the ignore list and see it pass.

**Acceptance Scenarios**:

1. **Given** the configured scope with no real typos, **When** the typo check runs, **Then** it exits zero.
2. **Given** an in-scope page containing `reding`, **When** the typo check runs, **Then** it exits non-zero and reports the file, the line and a suggested correction.
3. **Given** a misspelling inside a skipped tree (`docs/archive/`, `docs/reports/`, `docs/plans/`) or generated file, **When** the check runs, **Then** it is not reported.
4. **Given** a legitimate word the dictionary flags (e.g. `disjointness`), **When** it is on the ignore list, **Then** it is not reported.

---

### User Story 2 - UK spelling in user-facing prose fails the pull request (Priority: P1)

A contributor writes `behaviour` in a guide, a context/glossary page or a new Unreleased changelog entry. CI fails and suggests `behavior`. The same word in a code span or a fenced code block (a quoted literal such as a CLI message, a status value or a config key) is not flagged.

**Why this priority**: the Unreleased section and the guides/context pages are what CLI users read, and mixed UK/US spelling was one of the defects PR #5420 cleaned up.

**Independent Test**: plant `behaviour` in prose and `` `cancelled` `` in a code span in a scratch copy of the Unreleased section, then run the check. Only the prose word is reported, at the real file line.

**Acceptance Scenarios**:

1. **Given** the current Unreleased section, `docs/guides/` and `docs/context/`, **When** the US-spelling check runs after this mission's fixes, **Then** it exits zero.
2. **Given** a UK spelling in running prose in any of those three places, **When** the check runs, **Then** it fails and names the file, the real line number and the US spelling.
3. **Given** a UK spelling inside a code span or a fenced block, **When** the check runs, **Then** it is not reported.
4. **Given** a UK spelling in a released changelog section, or in a docs page outside `docs/guides/` and `docs/context/`, **When** the check runs, **Then** it is not reported.

---

### User Story 3 - The Unreleased section cannot drift back into maintainer prose (Priority: P1)

A contributor adds or edits an Unreleased entry. The style guard fails the pull request if any of these hold:
- a heading is outside the allowed set, out of order, or duplicated;
- the entry does not follow the headline/refs/Before/After shape;
- the entry contains a banned token;
- the entry exceeds the length cap.

Each failure names the entry (its section and headline) and states the exact fix.

**Why this priority**: PR #5420 fixed the content, but nothing stops it drifting back. The guard is the durable half of that fix.

**Independent Test**: for each rule, plant a single violation into a copy of the current Unreleased text and see the guard fail on that rule alone. Run it on the unmodified text and see it pass.

**Acceptance Scenarios**:

1. **Given** the current Unreleased section, **When** the guard runs, **Then** it passes with no failures. It may emit a length warning for entries between 900 and 1,200 characters.
2. **Given** a second `### Fixed` heading, or `### Added` placed after `### Fixed`, **When** the guard runs, **Then** it fails naming the heading and the required order.
3. **Given** a Fixed entry whose issue reference sits inside the bold headline, **When** the guard runs, **Then** it fails naming the entry and saying to move the refs outside the bold.
4. **Given** an entry containing `FR-011` outside backticks, a 26-character ULID, `.kittify/evidence/`, `planning#`, all-caps `REFUSE` outside backticks, "Bug-fix; no CLI version bump", or `spec-kitty merge --resume`, **When** the guard runs, **Then** it fails naming the entry, the token and the replacement guidance.
5. **Given** an entry over the hard cap, **When** the guard runs, **Then** it fails naming the entry and its length.

---

### User Story 4 - A contributor can run both checks locally and extend the ignore list (Priority: P2)

A contributor reads the development docs, runs one local command that runs both checks, and learns how to add a legitimate word to the ignore list and how to exempt a quoted literal.

**Why this priority**: a blocking check without local reproduction and an escape hatch creates friction and pushes people toward suppression.

**Independent Test**: follow the documented steps on a clean checkout, and see both checks run and pass.

**Acceptance Scenarios**:

1. **Given** the contributor docs, **When** a contributor follows them, **Then** they can run the typo check, the US-spelling check and the changelog guard locally with the documented commands.
2. **Given** the docs, **When** a contributor needs to allow a new word, **Then** the docs name the exact configuration location and format.

### Edge Cases

- **Symlinked changelog.** Root `CHANGELOG.md` and `.github/CHANGELOG.md` are symlinks to `docs/changelog/CHANGELOG.md`. Each finding is reported once, against the canonical path.
- **Changelog with no Unreleased section** (just after a release cut). The guard and the section-scoped spelling check pass trivially and say so. They do not crash.
- **Unreleased heading with a version suffix** (`## [Unreleased] - 4.0.0rc5`). It is recognized as the Unreleased section.
- **Entries with a nested sub-list.** The length is measured on the entry's own prose, and each nested item is measured separately, so a legitimate enumerated Upgrade Note is not penalized for its list.
- **Legitimate uses of banned tokens.** The Breaking rename entry that introduces `spec-kitty consolidate` may mention `spec-kitty merge`, and `merge-driver-*` subcommands are allowed. `DEFAULT`, `REFUSE` and `FAIL` inside backticks are allowed.
- **A word that is both a UK spelling and a quoted CLI or API literal** (e.g. a message the CLI prints). It is exempted by putting it in a code span, not by weakening the dictionary.
- **Preamble prose** before the first `###` heading is in scope for banned tokens and US spelling, but not for heading or entry-shape rules.
- **Empty `###` sections** are allowed. `####` subheadings must be unique within their `###` parent.
- **A `## [` line inside a fenced code block** does not end the Unreleased section.
- **Nested items** deeper than one level are measured as part of their parent nested item.
- **Anchor ids and identifiers**: legacy anchor ids (`<a id="organisation-tier">`) and canonical identifiers such as `behaviour-driven-development` are exempt from the US check, the anchors via the check's configuration and the identifiers by being written in code spans.
- **Skip-tree coverage**: tests of skipped trees run the production entry point with the real configuration over a fixture tree that reproduces the skipped paths, and pair every "not reported" assertion with the same typo reported from an in-scope path.
- **Typo check and code spans**: the code-span exemption applies only to the US-spelling check. Typos inside code spans are still reported by the typo check.
- **Planted-violation tests** must not modify the real changelog or docs. They operate on in-memory or temporary copies.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Typo check over the configured scope | As a contributor, I want a typo check over `docs/**/*.md`, `README.md` and `packs/built-in/**/*.md` (skipping `docs/archive/`, `docs/reports/`, `docs/plans/`, generated references and YAML/JSON/binary files) so that misspellings fail before they land. | High | Open | [build] | no — the planted-misspelling test fails on a do-nothing change |
| FR-002 | Project-resident ignore list | As a contributor, I want the dictionary false positives measured in grounding (`accreting`, `disjointness`, `pre-empt`, `pre-empts`, `pre-emptively`, `re-declared`, `trough`, `unparseable`) in one versioned project configuration, so that adding a legitimate word is a one-line change. | High | Open | [build] | no — paired with FR-001's positive control: the same word is reported when removed from the list |
| FR-003 | Fix the real typos in scope | As a reader, I want the in-scope typos corrected (`reding` → the intended "turning … red" wording, `filesytem`, `migrateable`, `re-using`) so that the check is green without ignoring real errors. | High | Open | [build] | no — the typo check is red on the base before the fixes |
| FR-004 | US-spelling check on guides and context | As a CLI user, I want UK spellings in running prose under `docs/guides/` and `docs/context/` to fail the check, with code spans and fenced blocks exempt, so that user-facing prose is consistently US English. | High | Open | [build] | no — the planted `behaviour` test fails on a do-nothing change |
| FR-005 | US-spelling check on the Unreleased section only | As a CLI user, I want the same US-spelling rule applied to the changelog's Unreleased section only, with findings reported at real file line numbers, so that new entries are US English without touching released sections. | High | Open | [build] | no — a planted UK word in the section is reported; the same word in a released section is not (same fixture) |
| FR-006 | Fix the US-spelling prose hits | As a reader, I want the measured UK-spelling prose hits in `docs/guides/` and `docs/context/` corrected, and any quoted CLI/API literal wrapped in a code span instead, so that the check is green on the current text. | High | Open | [build] | no — the US-spelling check is red on the base before the fixes |
| FR-007 | Rename UK glossary headings with legacy anchors | As a reader following an old link, I want `Organisation Tier`, `communication artefact` and `Trail Behaviour` renamed to US spelling, each keeping its previous anchor, with in-page links moved to the new slug, the UK form kept as a glossary alias (communication artefact is a ratified term), and derived glossary/index files regenerated, so that no inbound link breaks and the term history stays traceable. | Medium | Open | [build] | no — a test resolves each old anchor on the renamed page; the US check exempts the anchor id but still flags the same word in prose (same fixture) |
| FR-008 | Guard: heading set, order and uniqueness | As a changelog reader, I want the Unreleased section to use only the level-3 headings Breaking, Upgrade Notes, Added, Changed, Fixed and Internal, in that order, each at most once, with level-4 subheadings allowed only under Fixed. | High | Open | [build] | no — planted duplicate, out-of-order and unknown headings each fail |
| FR-009 | Guard: entry shape | As a changelog reader, I want entry shapes enforced per section. (a) Breaking, Upgrade Notes, Added, Changed and Fixed entries lead with a bold headline; issue refs are optional, sit outside the bold (a `#<digits>` inside the bold and outside a code span fails; `owner/repo#N` refs are accepted). (b) Breaking, Changed and Fixed entries carry a contrast: `**Before:**`, or `**Why:**` together with `**After:**`, or a body after the refs of at most 2 sentences and 300 characters. (c) Added and Upgrade Notes are exempt from the contrast rule. (d) Internal entries are single-line plain bullets without a `**Before:**` marker. | High | Open | [build] | no — planted refs-inside-bold, a 400-character Fixed entry without contrast, and a multi-line Internal entry each fail; the current text passes after the two C-003 defects are fixed |
| FR-010 | Guard: banned tokens | As a changelog reader, I want the Unreleased section (preamble and entries) free of: "Bug-fix; no CLI version bump"; requirement IDs (`FR-`/`NFR-`/`SC-`/`C-`/`D-` followed by digits) outside code spans; 26-character ULIDs (anywhere); `.kittify/evidence/` and `planning#` (anywhere); all-caps `DEFAULT`/`REFUSE`/`FAIL` as whole words outside code spans; and `spec-kitty merge` as a command, matched in raw text including code spans and allowed only in a paragraph or entry that also names `spec-kitty consolidate` (the rename context). The `merge-driver-*` subcommands are allowed. | High | Open | [build] | no — one planted-violation test per token (the merge plant is backticked, `` `spec-kitty merge --resume` ``); each exemption (code-span IDs, rename context, merge-driver) has its own positive test |
| FR-011 | Guard: entry length | As a changelog reader, I want entries capped at 1,200 characters (hard failure) with a warning above 900, measured in Unicode code points over the entry's own raw lines (markdown included) with each nested sub-item measured separately, so that entries stay readable. The warning is a reported finding of warning severity that does not fail the check. The current longest entries (948 and 972 code points) pass with a warning. | Medium | Open | [build] | no — a planted 1,201-code-point entry fails; a 901 one yields an asserted warning; a nested list totalling over 1,200 with each item under the cap passes while one nested item over 1,200 fails |
| FR-012 | Actionable failure messages | As a contributor, I want every guard failure to name the entry (section + headline excerpt) and the exact fix, so that I can correct it without reading the guard's source. | High | Open | [build] | no — every planted-violation test asserts the entry name and the fix text in the message |
| FR-013 | Blocking in CI on every input | As a maintainer, I want the typo check, the US-spelling checks and the changelog guard to run as a blocking, unmasked CI step that fires on every pull request (not path-routed), because their inputs span `docs/**`, `README.md`, `packs/built-in/**/*.md`, `pyproject.toml`, `uv.lock` and the check sources, and path groups do not cover that set. The planted-violation tests run in the existing docs test job. | High | Open | [build] | no — CI-shape tests assert the step is unconditional, is listed in the router gate, and does not mask the exit code |
| FR-014 | One local command | As a contributor, I want a single documented local command that runs the same entry points CI runs (typo check, US-spelling checks, changelog guard), so that I can reproduce CI before pushing. | Medium | Open | [build] | no — the tests invoke the same entry points and fail on a planted typo |
| FR-015 | Contributor guidance | As a contributor, I want `docs/development/` to explain how to run both checks locally, how to add a word to the ignore list, and how to exempt a quoted literal. | Medium | Open | [build] | no — the page is registered in the docs inventory and the freshness check covers it |
| FR-016 | One canonical Unreleased extractor | As a maintainer, I want the Unreleased section located by one shared parser, built on the existing changelog heading grammar, and used by both the guard and the section-scoped spelling check, so that the two checks can never disagree about where the section starts or ends. | Medium | Open | [build] | no — a test feeds both checks the same changelog with a version-suffixed and a bare `## [Unreleased]` heading, and asserts that both report the same section bounds |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fast checks | The typo and US-spelling checks together complete in under 5 seconds, and the changelog guard's test module in under 2 seconds, on a developer laptop (grounding measured about 0.5 s and 0.2 s). | Performance | High | Open |
| NFR-002 | Reproducible dictionary | The spellchecker version is pinned exactly, and the lockfile agrees with it, so that a dictionary update can never turn CI red without a deliberate version bump. | Reliability | High | Open |
| NFR-003 | Deterministic results | Repeated runs on the same tree produce identical findings in identical order (0 variance across 3 runs). | Reliability | Medium | Open |
| NFR-004 | Code quality | New code passes `ruff check`, `ruff format --check` and `mypy` with zero findings and no new suppressions. Every new function stays at cyclomatic complexity ≤ 15, and new code has ≥ 90% line coverage. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Tool choice is fixed | Use codespell (Python, configured in `pyproject.toml`, with the en-GB→en-US builtin dictionary). Do not introduce typos, Vale or another prose linter. | Technical | High | Open |
| C-002 | Released sections are immutable in style | Do not restyle released changelog sections. Only correct genuine typos there (FR-003). The guard reads only the Unreleased section. | Business | High | Open |
| C-003 | Calibrate to the current text | The guard must pass on the current Unreleased text (the PR #5420 rewrite) by describing its legitimate house-style variants precisely, not by weakening a rule into a no-op. Measured genuine defects are fixed in the text with minimal edits and listed in the PR. Two such defects are known: the Changed entries "`implement` on a `single_branch` mission refuses unsafe checkouts…" and "Creating a `single_branch` mission on a protected branch now switches…", each over 300 characters with no contrast. | Technical | High | Open |
| C-004 | US spelling is scoped | Enforce US spelling only on the Unreleased section, `docs/guides/` and `docs/context/`. Repo-wide enforcement (about 1,490 hits) is out of scope. | Business | High | Open |
| C-005 | No pytest in new always-on CI jobs | A new CI job must not reach pytest (directly or via a make/script chain), per the duplicate-suite-execution ledger. Tests of the checks run in the existing docs test job. | Technical | High | Open |
| C-006 | Frozen trees untouched | Do not modify `kitty-specs/`, `kitty-ops/` or `docs/archive/`. They are archive-frozen. | Technical | High | Open |
| C-007 | Out of scope | Making markdownlint blocking, fixing the generator truncation in `docs/api/cli-commands.md`, and US spelling outside the three user-facing scopes. | Business | Medium | Open |
| C-008 | Targeted test runs only | Validation runs the specific test files and named architectural gate files the change implicates (e.g. `tests/architectural/test_pyproject_shape.py`, the router/CI-shape tests), never a full `tests/architectural/` or `make test-full` sweep. | Technical | High | Open |

### Key Entities

- **Unreleased section**: the part of the canonical changelog between `## [Unreleased]` (optionally suffixed with a version) and the next level-2 release heading.
- **Entry**: a top-level list item in the Unreleased section. Its parts are a bold headline, optional issue refs, and body prose, which may contain `**Before:**`/`**After:**`/`**Why:**` markers and nested sub-items.
- **Typo scope / US-spelling scope**: the two file sets the spellchecker covers. The US-spelling scope is a strict subset of the prose readers see.
- **Ignore list**: the project-resident list of legitimate words the dictionary would otherwise flag.

## Domain Language

- **Unreleased section**: always this term. Do not call it "the changelog head" or "the next release notes".
- **Entry / headline**: an entry is one top-level bullet, and the headline is its bold lead.
- **Mission**: the canonical term. The changelog guard never introduces "feature" wording.
- **consolidate**: the current command name. `spec-kitty merge` is retired and appears only in the rename entry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the delivered tree, the typo check and the US-spelling check report 0 findings on their configured scopes. — [build] · no-op passable: no
- **SC-002**: Every guard rule (FR-008 to FR-011) and every banned token has at least one planted-violation test that fails, 100% of them. The guard passes on the current Unreleased section. As a real-world positive control, the guard fails on the pre-rewrite Unreleased section (before PR #5420), which carries the boilerplate, requirement IDs, all-caps tokens and evidence paths the rules target. — [build] · no-op passable: no
- **SC-003**: A pull request that introduces a typo, a UK spelling in scope, or an Unreleased style violation shows a failed check in CI, with no masking of the exit code. — [build] · no-op passable: no
- **SC-004**: A new contributor can run all checks locally with one documented command in under 1 minute, from reading the doc to seeing the result. — [build] · no-op passable: no
- **SC-005**: No released changelog section is changed except for the typo corrections listed in FR-003. — [ratchet] · no-op passable: yes — paired with SC-001, which fails without the FR-003 fixes

## Assumptions

- PR #5420 merges before or together with this mission's PR. Until then the PR carries PR #5420's commits and is rebased onto `main` afterwards. The guard is calibrated to PR #5420's Unreleased text.
- The issue's list of about 10 typos overstated the in-scope set. Most of those words sit in the skipped `docs/plans/` and `docs/reports/`. Grounding measured four real in-scope typos.
- Fixing a typo in a `packs/built-in/` source requires regenerating the agent copies (`spec-kitty regen`) and the pack manifest (`spec-kitty doctrine regenerate-graph`). Grounding measured 0 typos there today.
- The glossary rename edits derived files (the contextive glossary YAML under `src/`, and the docs retrieval index). The `src/` edit triggers a run-all CI on the PR, and the PR notes this.
- `dialogue` is standard US spelling, so it is allowed in the US-spelling check.
- A quoted CLI message spelled the UK way in a guide (`recognised`, echoing a CLI message) is treated as a literal and wrapped in a code span. Changing the CLI message itself is out of scope.
