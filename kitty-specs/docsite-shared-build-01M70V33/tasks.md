# Tasks: Docsite shared build definition

**Mission**: `docsite-shared-build-01M70V33` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Commit the failing acceptance tests (red) | WP01 | |
| T002 | Create the reusable workflow `docs-site-build.yml` | WP01 | |
| T003 | Make the router `docs-site` job call it; add the file to the `docs_site` group | WP01 | |
| T004 | Re-point the step checks at the called job, keep their mutants | WP01 | |
| T005 | Sync the scrub copy, changelog fragment, blast-radius tests | WP01 | |

## Phase 1 — Extraction and deploy reuse

### WP01 – Shared docs-site build workflow

- **Goal**: the docsite is built by one reusable workflow; the required gate calls it; the deploy can reuse it (FR-001..FR-006).
- **Priority**: P1. **Independent test**: `uv run --frozen pytest tests/ci/test_docs_site_job.py` (red on the T001 commit, green after T005); the real `docs-site` run on the PR is green and `router gate` passes.
- **Prompt**: [tasks/WP01-shared-docs-site-build-workflow.md](tasks/WP01-shared-docs-site-build-workflow.md)
- **Dependencies**: none.
- **Included subtasks**:

T001 Commit the failing acceptance tests (WP01)
T002 Create the reusable workflow `docs-site-build.yml` (WP01)
T003 Make the router `docs-site` job call it; add the file to the `docs_site` group (WP01)
T004 Re-point the step checks at the called job, keep their mutants (WP01)
T005 Sync the scrub copy, changelog fragment, blast-radius tests (WP01)

- **Risks**: vacuous step checks after extraction (T004 guards with a non-empty-steps assertion and mutants); the jobs-API row name (`docs site (doc-kitty build) / build`) must be pinned as blocking; `ci-router.yml` is hot (114 commits/90 days), rebase before push.
- **Parallel opportunities**: none (one WP, shared files).
