# Tasks: Docsite publication rules, llms.txt and render parity

**Mission**: `docsite-publication-llms-parity-01M70Z7A` · [spec.md](spec.md) · [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red: built-site check fixtures + mutants (publication surfaces) | WP01 | |
| T002 | Contract: DRAFT_FOLDERS, unpublished_routes, projection | WP01 | |
| T003 | Built-site check script (pages, hubs, sitemap, okf, search) | WP01 | |
| T004 | Wire gates + check into shared workflow and Makefile | WP01 | |
| T005 | Measure the strict link / frontmatter gates on the current tree | WP01 | |
| T006 | Flip working-note pages to draft (frontmatter only) | WP01 | |
| T007 | Archive retired hosted/sync pages + moves.yaml rows | WP01 | |
| T008 | Reword published links into unpublished pages | WP01 | |
| T009 | ADR D-8 amendment section | WP01 | |
| T010 | Prove green: make docs-site + built-site check | WP01 | |
| T011 | Red: llms/agent-index surface fixtures | WP02 | |
| T012 | Wire the stance projection (from WP01) into llms.txt | WP02 | |
| T013 | llms.txt wrapper + agent index pages | WP02 | |
| T014 | assert-no-broken-links step; upstream issue for #265 | WP02 | |
| T015 | Red: render surface fixtures (SEO tags, literal alerts) | WP02 | |
| T016 | githubAlerts: true | WP02 | |
| T017 | Render surface in the check | WP02 | |
| T018 | SEO parity checklist vs DocFX | WP02 | |

## Phase 1 — Publication

### WP01 – Publication rules: unpublished set, built-site check and content
- Goal: FR-001..FR-005, FR-010; prompt [tasks/WP01-publication-rules.md](tasks/WP01-publication-rules.md). Dependencies: none. Part A (authority, check, gates) is committed before Part B (content), so the check proves the content change.

T001 Red: built-site check fixtures + mutants (publication surfaces) (WP01)
T002 Contract: DRAFT_FOLDERS, unpublished_routes, projection (WP01)
T003 Built-site check script (pages, hubs, sitemap, okf, search) (WP01)
T004 Wire gates + check into shared workflow and Makefile (WP01)
T005 Measure the strict link / frontmatter gates on the current tree (WP01)
T006 Flip working-note pages to draft (frontmatter only) (WP01)
T007 Archive retired hosted/sync pages + moves.yaml rows (WP01)
T008 Reword published links into unpublished pages (WP01)
T009 ADR D-8 amendment section (WP01)
T010 Prove green: make docs-site + built-site check (WP01)

## Phase 2 — Surfaces

### WP02 – llms.txt, agent index and render parity
- Goal: FR-006..FR-009; prompt [tasks/WP02-llms-txt-agent-index-render-parity.md](tasks/WP02-llms-txt-agent-index-render-parity.md). Depends on WP01.

T011 Red: llms/agent-index surface fixtures (WP02)
T012 Wire the stance projection (from WP01) into llms.txt (WP02)
T013 llms.txt wrapper + agent index pages (WP02)
T014 assert-no-broken-links step; upstream issue for #265 (WP02)
T015 Red: render surface fixtures (SEO tags, literal alerts) (WP02)
T016 githubAlerts: true (WP02)
T017 Render surface in the check (WP02)
T018 SEO parity checklist vs DocFX (WP02)

Two WPs keep the mission single_branch (topology settles by size); they share the check script registry and run sequentially.
