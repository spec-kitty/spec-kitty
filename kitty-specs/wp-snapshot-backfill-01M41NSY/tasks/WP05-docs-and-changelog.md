---
work_package_id: WP05
title: Docs and CHANGELOG
dependencies:
- WP02
requirement_refs:
- FR-007
planning_base_branch: issue-5579-wp-snapshot-backfill
merge_target_branch: issue-5579-wp-snapshot-backfill
branch_strategy: Planning artifacts for this mission were generated on issue-5579-wp-snapshot-backfill. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5579-wp-snapshot-backfill unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
phase: Phase 5 - Docs
history:
- at: '2026-10-03T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: sonnet
owned_files:
- docs/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Docs and CHANGELOG

## Do This First

Load profile `scribe-sally`. Charter writing doctrine: one Divio quadrant per page, `updated:` frontmatter, audience named.

## Subtasks

- **T017**: document `spec-kitty migrate backfill-wp-status` where sibling `migrate` subcommands are documented (find with `rg -l "backfill-runtime-state" docs/`): purpose, when to use, evidence-manifest format, dry-run, exit codes. Reference ADR 2026-06-07-3 for why the reducer omits event-less WPs. Use "Mission", never "feature".
- **T018**: `docs/changelog/CHANGELOG.md` `[Unreleased]`: bold impact-first lead with `(#5579)`, then before → after (snapshot WP counts disagreed with WP files on 51 Missions → one repair seeds missing events; finished Missions land in `done`; corpus gate keeps parity).
- **T019**: if a page is added, run `.venv/bin/python scripts/docs/docs_index.py --write`; always run `.venv/bin/python scripts/docs/check_docs_freshness.py --ci` (errors=0) and `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.
