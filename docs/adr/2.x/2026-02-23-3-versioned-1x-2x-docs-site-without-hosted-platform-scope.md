---
title: Versioned 1.x/2.x Documentation Site Without Hosted-Platform Scope
description: Splits the documentation site into explicit 1.x and 2.x tracks behind a versioned landing page, while deliberately holding hosted-platform guidance out of scope.
status: Accepted
date: '2026-02-23'
doc_status: active
kind: ADR
updated: '2026-02-23T00:00:00Z'
---

## Context and Problem Statement

The docs site historically served one blended track, making 1.x and 2.x behavior difficult to separate. Meanwhile, 2.x introduced doctrine/glossary architecture that lacked a clear documentation path.

For this release, documentation scope must remain local-first and must not add hosted-platform guidance.

## Decision Drivers

1. Present 1.x and 2.x behavior as distinct, navigable tracks.
2. Document 2.x doctrine/glossary architecture accurately.
3. Prevent accidental reintroduction of out-of-scope hosted-platform docs.
4. Keep docs deployment straightforward through existing GitHub Pages flow.

## Considered Options

1. Keep a single unversioned documentation track.
2. Create explicit `docs/1x/` and `docs/2x/` tracks with a versioned landing page (chosen).
3. Split docs into separate repositories.

## Decision Outcome

**Chosen option:** Create explicit `docs/1x/` and `docs/2x/` tracks with a versioned landing page and docs guardrails.

### Decision Details

1. Documentation navigation is versioned at top level (`1.x`, `2.x`).
2. 2.x track documents doctrine architecture, charter workflow, glossary system, mission/runtime loop, and ADR coverage.
3. 1.x track remains local-first and excludes hosted-platform guidance in this docs path.
4. Docs CI includes versioned-doc checks for link integrity and forbidden out-of-scope terms in versioned pages.
5. GitHub Pages workflow deploys documentation updates from both `main` and `2.x` branches.

### Consequences

#### Positive

1. Users can immediately choose the correct version track.
2. 2.x architecture changes are documented where users expect them.
3. Docs quality gates detect broken links and scope drift early.

#### Negative

1. Documentation maintenance now spans two version tracks.
2. Some legacy unversioned docs may require gradual migration into versioned pages.

#### Neutral

1. Existing source docs can continue to exist while versioned tracks become canonical.

## Confirmation

This decision is validated when:

1. Versioned docs build and link checks pass.
2. 1.x and 2.x top-level docs are both navigable in GitHub Pages.
3. Doctrine/glossary 2.x architecture is documented and cross-referenced to ADRs/code.
4. Versioned docs tests fail on banned out-of-scope hosted-platform terms.

## More Information

Implementation references:

1. `docs/index.md`
2. `docs/toc.yml`
3. `docs/1x/*.md`
4. `docs/2x/*.md`
5. `docs/docfx.json`
6. `.github/workflows/docs-pages.yml`
7. `tests/docs/test_versioned_docs_integrity.py`
