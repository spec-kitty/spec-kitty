# Mission Specification: Retire DocFX

**Mission Branch**: `kitty/mission-retire-docfx-01M78FG2` (lands on `issue-6943-retire-docfx`)
**Created**: 2026-11-12
**Status**: Draft
**Input**: Operator brief for #6943: retire DocFX now that the docsite cutover (#6938, PR #7558) is merged and the doc-kitty deploy and smoketest are green on `main`.

## Context

ADR `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` D-13 step 5 retires DocFX after the cutover. The cutover amendment (2026-11-11) removed the DocFX jobs from `docs-pages.yml` and left the DocFX sources in the tree until #6943: `docs/docfx.json`, every `toc.yml`, the template, the DocFX scripts and their tests. No CI job builds DocFX today.

**Waived gate (operator decision, 2026-11-12).** #6943's precondition "one Spec Kitty release shipped with the doc-kitty site live" is waived. The last release, v4.0.0rc8, predates the cutover. The evidence that stands in for it: the production canary (run [43027580608](https://github.com/spec-kitty/spec-kitty/actions/runs/43027580608), report on [#6938](https://github.com/spec-kitty/spec-kitty/issues/6938#issuecomment-6796965517)) and the green post-cutover `docs-pages.yml` runs on `main` (jobs `pages`, `build`, `deploy`, `smoketest`; for example run [43265541140](https://github.com/spec-kitty/spec-kitty/actions/runs/43265541140)).

**Rollback posture after this mission.** Rolling back to DocFX is no longer "revert the cutover pull request". It needs a revert of this mission's pull request and of #7558. Rolling forward is preferred.

**Immutable history** (never edited by this mission): dated ADRs and their earlier amendments, `docs/changelog/`, `CHANGELOG.md`, `docs/plans/`, `docs/reports/`, `docs/archive/`, `kitty-specs/`, and the append-only operation and evidence records `kitty-ops/`, `.kittify/evidence/`, `.kittify/migrations/` and the #4562 bulk-edit record `occurrence_map.yaml`. `docs/assets/spec-kitty-evolution-v1-to-v3.html` is a historical timeline and keeps naming the tool it describes. Generated files (`docs/development/docs-retrieval-index.yaml`, `.github/ci-shard-timings.json`) follow their sources and are regenerated, not hand-edited.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One docs toolchain in the tree (Priority: P1)

A maintainer working on the docs finds one build: the doc-kitty site. The DocFX configuration, navigation files, template and the scripts that only fed the DocFX build are gone, so nobody edits or maintains a second toolchain that no job runs.

**Why this priority**: it is #6943's scope. Dead toolchain code costs review time and misleads readers about how the site is built.

**Independent Test**: the DocFX sources and the dropped scripts are absent, and no live script or test imports a deleted module.

**Acceptance Scenarios**:

1. **Given** the mission landed, **When** a maintainer lists `docs/`, **Then** there is no `docfx.json`, no `toc.yml` and no `templates/` folder.
2. **Given** the mission landed, **When** `tests/docs` runs, **Then** no test imports a deleted `scripts/docs` module and the suite is green.
3. **Given** the mission landed, **When** `make docs-site` runs, **Then** the doc-kitty build still passes: no kept build input was removed.

### User Story 2 - Live invariants keep their protection (Priority: P1)

Some DocFX-era tests guard rules that still hold for the doc-kitty site: which pages are published and must carry a title and a description within the band, and that `docs/reports/` is never published. Those tests are rebased on the doc-kitty contract (`scripts/docs/_dockitty_contract.py`) instead of being deleted.

**Why this priority**: deleting a guard together with the toolchain it read would silently drop a live rule.

**Independent Test**: the rebased tests read the published set from the contract, go red when the contract stops excluding `reports/`, and go red when a published page lacks a description.

**Acceptance Scenarios**:

1. **Given** the contract's published set, **When** the SEO test runs, **Then** every published page has a `title` and a `description` within the contract's band, and the set is non-vacuous.
2. **Given** a contract that no longer excludes `reports/`, **When** the reports guard runs, **Then** it fails.

### User Story 3 - Plumbing, docs and the record match the tree (Priority: P2)

CI no longer provisions tooling for deleted scripts, the developer docs describe the doc-kitty build, the ADR records the retirement, the waived gate and the new rollback posture, and a changelog fragment announces it. A gate keeps DocFX from returning to living files.

**Why this priority**: stale plumbing and docs mislead the next maintainer; the ADR is the decision record the operator reads.

**Independent Test**: `git grep -i docfx` outside immutable history and generated files is empty, the absence test is green, and the CI pin tests pass on the edited workflows.

**Acceptance Scenarios**:

1. **Given** the mission landed, **When** the absence test scans living files, **Then** none names DocFX.
2. **Given** the `tests (docs)` router job, **When** it runs, **Then** it no longer restores or provisions the PlantUML jar.
3. **Given** the ADR, **When** the operator reads it, **Then** `## Amendment 2026-11-12 (DocFX retired)` records the waived gate and its evidence, what was removed, the rollback posture and that D-13 is complete apart from #6939.

### Edge Cases

- A kept script imported a helper from a deleted module (`docs_index.py` imports `slugify` from `generate_kitty_specs_docs.py`): the helper moves to the kept module rather than keeping the deleted one alive.
- A kept module carries functions only the deleted DocFX map generator called (`moves_ledger.derive_redirect_map`, `moves_ledger.validate`): they go with it.
- A ratchet lists a deleted file (the formatter-exclude list in `pyproject.toml`, `ruff.toml` per-file ignores, the shard timings): the entry goes with the file; a ratchet never grows.
- A ledger header (`site/moves.yaml`, `site/url-baseline.txt`) names DocFX in its provenance comment: the comment is reworded; no recorded ledger line changes.
- `docs/templates/index.md` describes only the deleted template: it goes with the folder. Its route was never in the URL baseline, so no ledger row is needed.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Remove the DocFX sources | As a maintainer, I want `docs/docfx.json`, every `toc.yml`, `docs/templates/` (incl. `main.js`) and the DocFX-only static files (`docs/CNAME`, `docs/robots.txt`, `docs/.nojekyll`, `docs/.gitignore`) removed so that one toolchain remains; `site/public/` already carries the site's `CNAME` and `robots.txt`. | High | Open | [build] | no — an absence test names each path and is red before the deletion |
| FR-002 | Remove the DocFX-only scripts | As a maintainer, I want the scripts D-6 drops (`plantuml_render.py`, `plantuml_invoke.py`, `plantuml_pins.json`, `generate_kitty_specs_docs.py`) and the ported scripts whose only runner was the DocFX build or whose job doc-kitty now does (`redirect_stub_generator.py`, `capture_baseline_urls.py`, `seo_postprocess.py`, `seo_verify.py`, `glossary_linker.py` with `glossary_page/`, `description_length_check.py`, `_published_pages.py`) removed with their tests, so that no script reads `docfx.json`. | High | Open | [build] | no — the absence test names each module and is red before the deletion |
| FR-003 | Remove the superseded redirect inputs | As a maintainer, I want `scripts/docs/redirect_map.yaml` and `scripts/docs/redirect_baseline_urls.json` removed so that the ledgers (`site/moves.yaml`, `site/url-baseline.txt`, `site/legacy-redirects.json`) are the only redirect authority. | High | Open | [build] | no — the absence test names both files |
| FR-004 | No import of a deleted module | As a maintainer, I want no `scripts/docs` module or test to import a deleted module so that the docs suite collects and runs. | High | Open | [build] | no — the absence test scans imports and is red while one remains |
| FR-005 | Published-page rule rebased on the contract | As a maintainer, I want the "published pages carry a title and a description within the band" test to read the published set from `_dockitty_contract.py` with a non-vacuous floor so that the rule survives DocFX. | High | Open | [build] | no — paired with a mutant tree where a published page lacks a description |
| FR-006 | Reports-unpublished guard rebased on the contract | As a maintainer, I want the shared guard that `docs/reports/` is never published (used by three terminology tests) to read the contract, not `docfx.json`, so that the terminology exemptions stay safe. | High | Open | [build] | no — paired with a contract whose excluded folders omit `reports` |
| FR-007 | CI and config plumbing | As a maintainer, I want the PlantUML-jar steps in `ci-router.yml`'s `tests (docs)` job, the DocFX comments in `docs-pages.yml`, and every pyproject/ruff/registry entry for a deleted file removed so that CI provisions nothing for deleted scripts. | High | Open | [build] | no — the nightly-cache test pins the jar cache's absence |
| FR-008 | Developer docs describe doc-kitty | As a maintainer, I want the living docs that describe DocFX (`docs/api/configuration.md`, `docs/api/file-structure.md`, `docs/development/**`) updated to describe the doc-kitty build so that readers are not sent to a deleted toolchain. | Medium | Open | [build] | no — the absence test covers `docs/` outside immutable history |
| FR-009 | Living files never name DocFX again | As a maintainer, I want a test that fails when a tracked living file names DocFX so that the retirement holds. | High | Open | [build] | no — red before the cleanup; the allowed set is the immutable-history and generated list above |
| FR-010 | ADR amendment and changelog | As the operator, I want `## Amendment 2026-11-12 (DocFX retired)` appended to ADR 2026-10-31-1 and a changelog fragment that passes the style and spelling checks so that the decision record and release notes are complete. | High | Open | [build] | no — `check_changelog_style` and `check_spelling --pass unreleased` run on it |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Targeted suites green | `pytest tests/docs` and every touched test file pass with 0 failures and 0 new skips or xfails. | Reliability | High | Open |
| NFR-002 | Lint and types | `ruff check`, `ruff format --check --force-exclude` and `mypy --strict` report 0 issues on every changed Python file; `actionlint` reports 0 issues on changed workflows. | Maintainability | High | Open |
| NFR-003 | Ratchets only shrink | No ratchet, allowlist or exclude list gains an entry; deleted files leave every list they were on. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Immutable history | Never edit an ADR body or an earlier amendment, `docs/changelog/`, `CHANGELOG.md`, `docs/plans/`, `docs/reports/`, `docs/archive/`, `kitty-specs/`, or the append-only `kitty-ops/` and `.kittify/` records. | Governance | High | Open |
| C-002 | Never edit packs | `packs/` is fetched, never edited. | Governance | High | Open |
| C-003 | Keep the D-6 keep list | Every script D-6 keeps, and every module the doc-kitty build path reads (`_dockitty_contract.py`, `site_*.py`, `moves_ledger.py`, the docs index and inventory), stays. | Technical | High | Open |
| C-004 | Out of scope | The README rename (#6939) and the content pass (#3891) are not started. | Business | High | Open |
| C-005 | Ledgers append-only | No recorded `site/moves.yaml` entry or baseline route changes; only header comments may be reworded. | Technical | High | Open |

### Key Entities

- **DocFX sources**: `docs/docfx.json`, the eight `toc.yml` files, `docs/templates/`, and the static resources the DocFX build copied.
- **Doc-kitty contract**: `scripts/docs/_dockitty_contract.py`, the single core authority for which pages are published and which folders are excluded.
- **Living file**: a tracked file outside the immutable-history and generated lists in Context.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `git grep -i docfx` over living files returns 0 lines — [build] · no-op passable: no
- **SC-002**: 0 `scripts/docs` modules or tests import a deleted module; `pytest tests/docs` passes — [build] · no-op passable: no
- **SC-003**: the published-page and reports guards read `_dockitty_contract.py` and each has a mutant that turns it red — [build] · no-op passable: no
- **SC-004**: the draft PR's CI is green — [build] · no-op passable: no
