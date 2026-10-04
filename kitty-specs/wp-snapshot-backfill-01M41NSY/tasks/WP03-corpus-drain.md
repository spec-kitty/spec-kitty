---
work_package_id: WP03
title: Corpus drain
dependencies:
- WP02
requirement_refs:
- FR-008
planning_base_branch: issue-5579-wp-snapshot-backfill
merge_target_branch: issue-5579-wp-snapshot-backfill
branch_strategy: Planning artifacts for this mission were generated on issue-5579-wp-snapshot-backfill. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5579-wp-snapshot-backfill unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
phase: Phase 3 - Drain
history:
- at: '2026-10-03T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: kitty-specs/
create_intent:
- kitty-specs/wp-snapshot-backfill-01M41NSY/evidence-manifest.yaml
execution_mode: planning_artifact
model: sonnet
owned_files:
- kitty-specs/wp-snapshot-backfill-01M41NSY/evidence-manifest.yaml
- kitty-specs/*/status.events.jsonl
- kitty-specs/*/status.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Corpus drain

## Do This First

Load profile `implementer-ivan`. Read the spec (Decision Moment 01M41NVK…: finished Missions → seed + forced `done`).

## Subtasks

- **T011 evidence manifest**: for every disagreeing Mission WITHOUT `meta.json` `accepted_at`/`merged_at`, decide whether it is finished using git evidence only: the Mission's dossier landed on `main` via a merged PR (`git log --format='%H %s' -- kitty-specs/<slug>` on `upstream/main` (`origin/main` when no `upstream` remote is configured), look for the `(#NNNN)` PR ref; confirm with `unset GITHUB_TOKEN; gh pr view NNNN -R spec-kitty/spec-kitty --json state,mergedAt`) AND the issue/PR describes the mission's work as landed. Record `reason: "<PR url> merged <date>; <one-line why finished>"`. If unsure, leave it out (it stays `planned`). Never guess.
- **T012**: dry-run first (`spec-kitty migrate backfill-wp-status --dry-run --evidence-manifest … --json`), review, then live run. Verify a second dry-run reports 0 would-seed and that every non-bucket-C Mission's snapshot WP-id set equals its file id set. Do not touch Missions outside the disagreement set.
- **T013**: list in the commit body (and in `traces/design-decisions.md`) every MODIFIED pre-existing frozen file (`git diff --name-status` status `M` under `kitty-specs/`), for WP04's sanctioned-corrections ledger. Added files need no entry.

Commit as one commit: `chore(kitty-specs): backfill missing WP status events (#5579)`.
