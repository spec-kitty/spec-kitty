---
description: "Work packages for the docsite cutover to doc-kitty"
---

# Work Packages: Docsite cutover to doc-kitty

**Inputs**: Design documents from `kitty-specs/docsite-cutover-01M75N3E/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: requested. The job-graph tests are written red first (#7484: evaluate real `if:` conditions, never restate YAML).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into two work packages. Subtasks are reference rows; completion is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first job-graph tests for the cutover in `tests/release/test_release_ci_ownership.py` | WP01 | |
| T002 | Switch `docs-pages.yml`: `build` calls the shared build, `deploy` publishes it, permissions, path filter | WP01 | |
| T003 | Add the `smoketest` job (`needs: deploy`, main only, read-only, probe the production domain) | WP01 | |
| T004 | Remove the canary jobs and input; refresh comments in `docs-site-build.yml` and `ci-router.yml` | WP01 | |
| T005 | Retire the DocFX deploy-job tests in `tests/ci/test_nightly_tooling_cache.py`; keep the router jar-cache key pinned | WP01 | |
| T006 | Run the targeted tests, ruff, mypy and actionlint for WP01 | WP01 | |
| T007 | Delete `docs/llms.txt`; update `docs/docfx.json`, `tests/docs/test_docs_seo.py`, `tests/docs/test_dockitty_contract.py`, `scripts/docs/_dockitty_contract.py` | WP02 | [P] |
| T008 | Update `docs/development/reference/ci-gate-mechanics.md` (where the docsite deploys from) | WP02 | [P] |
| T009 | ADR 2026-10-31-1: `## Amendment 2026-11-11 (cutover)` | WP02 | |
| T010 | Changelog fragment in `docs/changelog/unreleased/` | WP02 | |
| T011 | Run the docs subsystem tests, changelog style and spelling checks | WP02 | |

---

## Work Package WP01: Deploy the doc-kitty build with a post-deploy smoketest (Priority: P1)

**Goal**: `docs-pages.yml` publishes the shared doc-kitty build from `main` and smoketests the live site; the canary is retired into the smoketest.
**Independent Test**: the job-graph model in `tests/release/test_release_ci_ownership.py` (real `if:` conditions via `tests/ci/_gh_expr.py`).
**Prompt**: `tasks/WP01-deploy-and-smoketest.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, NFR-004, C-002, C-004

### Included Subtasks

T001 Red-first job-graph tests (WP01)
T002 Switch the deploy to the shared build (WP01)
T003 Add the smoketest job (WP01)
T004 Remove the canary; refresh comments (WP01)
T005 Retire DocFX deploy-job tests; keep the jar-cache key pinned (WP01)
T006 Targeted tests and linters (WP01)

### Implementation sketch

Write the tests first and see them fail on the current workflow; then rewrite the jobs; then the comments; then the retired tests.

### Dependencies and risks

- None upstream. Risk: `pages: read` on the probe job (research R-5).

---

## Work Package WP02: One `llms.txt`, and the record (Priority: P2)

**Goal**: delete the hand-written `docs/llms.txt` and its live references; record the cutover in the ADR amendment, the CI reference page and a changelog fragment.
**Independent Test**: `uv run --frozen pytest tests/docs -n 4 --dist loadfile --tb=line -q`, `check_changelog_style`, `check_spelling --pass unreleased`.
**Prompt**: `tasks/WP02-llms-and-record.md`
**Requirement Refs**: FR-007, FR-008, C-001, C-003

### Included Subtasks

T007 Delete `docs/llms.txt` and update its references (WP02)
T008 Update the CI reference page (WP02)
T009 ADR amendment (WP02)
T010 Changelog fragment (WP02)
T011 Docs tests and prose checks (WP02)

### Dependencies and risks

- Depends on WP01: the amendment and the reference page describe the workflow WP01 lands.
