---
work_package_id: WP02
title: Redirect gates in CI and the self-test
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- NFR-001
- C-004
- C-005
- SC-001
- SC-002
planning_base_branch: issue-6933-docsite-redirects
merge_target_branch: issue-6933-docsite-redirects
branch_strategy: Planning artifacts for this mission were generated on issue-6933-docsite-redirects. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6933-docsite-redirects unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Gates
history:
- at: '2026-11-10T16:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent:
- scripts/docs/site_redirects_selftest.py
- tests/docs/test_site_redirects_selftest.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/docs-site-build.yml
- .github/workflows/ci-router.yml
- tests/release/ci_retirement_scrub.json
- Makefile
- scripts/docs/site_redirects_selftest.py
- tests/docs/test_site_redirects_selftest.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Redirect gates in CI and the self-test

## Context & Constraints

- Builds on WP01's generator and map. The grounding is in `research/code-grounding.md` §2 and §4.
- Every `dockitty-*` call carries `--astro-config astro.config.mjs` on the same line; `tests/ci/test_docs_site_job.py` enforces it.
- No YAML-shape tests (#7484). The proof is the real gate in the job plus the self-test.
- #6936 (PR #7508) edits the same workflow. Build on `main`; the later PR rebases.

## Objectives & Success Criteria

- **T006 (red first).** Add `scripts/docs/site_redirects_selftest.py`:
  - hard-link `dist` into a temp directory (`cp -al`, or `os.link`);
  - apply three mutants: (a) the target page of one key removed, (b) one key's stub removed, (c) a draft-excused URL (a page that is a `doc_status` draft, with its stub removed);
  - run the gate command for each mutant, with `--docs` and without;
  - expected exit codes: (a) 1/1, (b) 1/1, (c) 0 with `--docs`, 1 without;
  - exit 1 on any mismatch, naming it.

  The gate command is injectable. The tests drive it with fake commands, so a gate that always passes or always fails makes the self-test fail.
- **T007.** In `docs-site-build.yml` and `make docs-site`:
  - before the build: `python3 -m scripts.docs.site_redirects --check`;
  - after the built-site check, two runs of `pnpm exec dockitty-check-redirect-coverage url-baseline.txt dist`: one with `--docs ../docs --declared-redirects legacy-redirects.json --astro-config astro.config.mjs`, one with `--astro-config astro.config.mjs` only;
  - then the self-test.
- **T008.**
  - `ci-router.yml`: add `scripts/docs/moves_ledger.py` and `scripts/docs/site_redirects*.py` to the `docs-site` filter.
  - Update the scrub copy in `tests/release/ci_retirement_scrub.json` in lockstep.
  - Run `tests/release/test_release_ci_ownership.py`, `tests/ci/test_docs_site_job.py`, `tests/ci/test_fork_guard.py`, `tests/architectural/test_no_duplicate_suite_execution.py`, `tests/docs` and actionlint.

## Progress & Status

- `mark-status`, then `move-task WP02 --to for_review`.
