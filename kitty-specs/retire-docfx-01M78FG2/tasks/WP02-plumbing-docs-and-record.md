---
work_package_id: WP02
title: Plumbing, docs and the record
dependencies:
- WP01
requirement_refs:
- FR-007
- FR-008
- FR-009
- FR-010
- NFR-001
- NFR-002
- C-001
- C-004
- C-005
planning_base_branch: issue-6943-retire-docfx
merge_target_branch: issue-6943-retire-docfx
branch_strategy: Planning artifacts for this mission were generated on issue-6943-retire-docfx. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6943-retire-docfx unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Plumbing and record
history:
- at: '2026-11-12T18:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent:
- tests/architectural/test_legacy_docsite_named_nowhere.py
- docs/changelog/unreleased/6943-retire-docfx.changed.md
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-router.yml
- .github/workflows/docs-pages.yml
- tests/ci/test_nightly_tooling_cache.py
- tests/ci/test_docs_site_job.py
- tests/ci/test_workflow_script_import_guard.py
- src/kernel/site_urls.py
- tests/kernel/test_paths.py
- tests/kernel/test_site_urls.py
- tests/release/test_release_ci_ownership.py
- tests/architectural/test_legacy_docsite_named_nowhere.py
- docs/api/configuration.md
- docs/api/file-structure.md
- docs/architecture/mission-gates.md
- docs/development/**
- site/moves.yaml
- site/url-baseline.txt
- docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md
- docs/changelog/unreleased/6943-retire-docfx.changed.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6943'
---

# Work Package Prompt: WP02 – Plumbing, docs and the record

## Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback; record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

## Objectives & Success Criteria

- `tests (docs)` in `ci-router.yml` no longer restores, provisions or saves the PlantUML jar (FR-007); `docs-pages.yml` comments state the post-retirement rollback.
- Living docs describe the doc-kitty build (FR-008).
- `tests/architectural/test_legacy_docsite_named_nowhere.py` fails on any tracked living file that names DocFX, with a self-test (FR-009).
- ADR amendment and changelog fragment (FR-010).

## Context & Constraints

- Depends on WP01. Do not touch `scripts/docs/` or `tests/docs/`.
- C-001: append to the ADR only; never edit its body or an earlier amendment. C-005: in `site/moves.yaml` and `site/url-baseline.txt` reword header comments only.
- The living-files gate excludes exactly the spec's immutable-history list and generated files (`docs/development/docs-retrieval-index.yaml`, `.github/ci-shard-timings.json`), plus itself.

## Subtasks & Detailed Guidance

### T007 – Red-first

- `tests/architectural/test_legacy_docsite_named_nowhere.py`: scan `git ls-files` minus the excluded prefixes and files for `docfx` (any case); non-vacuous floor; self-test on a planted file in `tmp_path`.
- `tests/ci/test_nightly_tooling_cache.py`: assert the router `tests (docs)` job has no PlantUML-jar cache or provisioning step (replaces the jar-key test).
- Run both against the unchanged tree and record the red count.

### T008 – CI plumbing

- Remove the three PlantUML-jar steps and their comment from `ci-router.yml` `tests-docs`.
- `docs-pages.yml` header: rollback is a revert of this PR and #7558; roll forward is preferred.
- `tests/ci/test_docs_site_job.py`, `tests/release/test_release_ci_ownership.py`: reword comments that say DocFX keeps deploying or that a revert of the cutover restores DocFX.
- Check `.github/ci-module-registry.yml` and `tests/release/ci_retirement_scrub.json` for deleted paths (expected: none).

### T009 – Living docs and ledger headers

- `docs/api/configuration.md`: replace the `docfx.json` section with the doc-kitty site configuration (`site/astro.config.mjs`, `site/package.json`, `docs/_meta/sections.yaml`, `scripts/docs/_dockitty_contract.py`); update the description.
- `docs/api/file-structure.md`, `docs/development/reference/ci-gate-mechanics.md`, `docs/development/reference/terminology-exemptions.md` and any other `docs/development/**` page that names DocFX.
- `site/moves.yaml`, `site/url-baseline.txt`: reword header comments that name DocFX or deleted scripts.

### T010 – ADR amendment

Append `## Amendment 2026-11-12 (DocFX retired)` recording: the waived release gate (operator decision 2026-11-12; v4.0.0rc8 predates the cutover) and the evidence (canary run 43027580608 and its report; green post-cutover deploy and smoketest runs, e.g. 43265541140); what was removed (sources, scripts and why each D-6 "port" script went now); the new rollback posture (revert this PR and #7558; roll forward preferred); D-13 complete apart from #6939; the D-14 shim list unchanged.

### T011 – Changelog

One fragment in `docs/changelog/unreleased/` per its README; passes `check_changelog_style` and `check_spelling --pass unreleased`.

### T012 – Verify

```bash
uv run --frozen pytest tests/architectural/test_legacy_docsite_named_nowhere.py tests/ci/test_nightly_tooling_cache.py tests/ci/test_docs_site_job.py tests/ci/test_fork_guard.py tests/release/test_release_ci_ownership.py --tb=line -q
uv run --frozen pytest tests/architectural/test_retirement_scrub.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_module_shard_registry.py tests/architectural/test_coverage_breadth.py tests/architectural/test_no_legacy_terminology.py --tb=line -q
uv run --frozen pytest tests/docs -n 4 --dist loadfile --tb=line -q
uv run --frozen python -m scripts.docs.check_changelog_style; uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
actionlint .github/workflows/ci-router.yml .github/workflows/docs-pages.yml
make docs-site   # if the toolchain is available
```

## Review Guidance

- The gate's excluded set is the spec's list, not a list of offenders.
- The ADR amendment is appended only; nothing above it changed.
