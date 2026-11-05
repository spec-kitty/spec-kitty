---
work_package_id: WP03
title: Operator docs and changelog
dependencies:
- WP01
- WP02
requirement_refs:
- FR-003
- SC-004
- C-003
planning_base_branch: issue-7209-skip-lanes-planning-commit
merge_target_branch: issue-7209-skip-lanes-planning-commit
branch_strategy: Planning artifacts for this mission were generated on issue-7209-skip-lanes-planning-commit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7209-skip-lanes-planning-commit unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
phase: Phase 3 - Operator surface
history:
- at: '2026-11-05T15:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/guides/how-to/missions/merge-mission.md
- docs/changelog/unreleased/7209-skip-lanes-evidence-window.fixed.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/guides/how-to/missions/merge-mission.md
- docs/changelog/unreleased/7209-skip-lanes-evidence-window.fixed.md
role: documentarian
tags: []
task_type: docs
tracker_refs:
- '#7209'
---

# Work Package Prompt: WP03 – Operator docs and changelog

## Do This First: Load Agent Profile

Load `scribe-sally` (documentarian) before editing the operator-facing prose.

## Review Feedback

Check the `review_ref` in the status event log; address every item.

## Objectives & Success Criteria

1. `docs/guides/how-to/missions/merge-mission.md` states what `consolidate --skip-lanes` now
   records for a direct-on-target Mission (an evidence-window base resolved from the target
   branch's history, the commit before `kitty-specs/<slug>/` appeared) and what still refuses:
   an approved work package with no change to its `owned_files`, an approval by the implementer,
   and an unresolvable window (with the remedy that applies) (FR-003, C-003).
2. A per-PR changelog fragment under `docs/changelog/unreleased/`, named
   `7209-skip-lanes-evidence-window.fixed.md` for now (rename to the PR number once the PR
   exists), in the exact shape `docs/changelog/unreleased/README.md` requires: no heading, a
   bold impact-first lead with the issue reference, then **Before:** and **After:**, under 1,200
   characters, US spelling.

## Context & Constraints

- Do not edit `docs/changelog/CHANGELOG.md`; the fragment is the entry point since #6988.
- US spelling (`artifacts`, `behavior`); the repo's `check_spelling --pass unreleased` reads the
  fragment.
- Do not promise completion where the evidence axis still (correctly) refuses; describe both
  outcomes.
- No docs-index regeneration: this changes an existing page plus a fragment, not the page
  inventory (`uv run --frozen python -m scripts.docs.check_docs_freshness --ci` stays clean
  because no indexed page is added or removed).

## Branch Strategy

- Planning base and merge target: the branch the CLI reports for this mission; the PR targets
  `spec-kitty/spec-kitty` `main`, which only the operator merges.

## Subtasks

### T007 – `--skip-lanes` note in the merge how-to

Read the page's existing `--skip-lanes` row and the surrounding "direct-on-target" prose, then add
a short subsection (or extend the existing one) covering:

- what the flag now records (the synthesized manifest's evidence-window base: the target commit
  immediately before the Mission's planning artifacts appeared);
- that the #6715 evidence and review-independence gates still apply unchanged, so a work package
  with no owned change, or a self-review, still refuses;
- what to do when the window cannot be resolved (commit the Mission's planning artifacts on the
  target), pointing at the refusal text.

Keep it operator-facing and concrete: name the command and the code.

### T008 – Changelog fragment

Create the fragment with one entry:

- lead: `spec-kitty consolidate --skip-lanes` now completes a direct-on-target Mission instead of
  always refusing;
- **Before:** the synthesized lanes manifest recorded no planning commit, so every approved work
  package hit `EVIDENCE_WINDOW_UNCOMPUTABLE` and the flag was unusable;
- **After:** the manifest records the target commit before the Mission's planning artifacts, the
  evidence window is judged normally (the evidence and review gates still refuse what they
  refused before), and an unresolvable window names the remedy that works for a Mission with no
  `lanes.json`.

Validate:

```bash
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
uv run --frozen python -m scripts.docs.check_docs_freshness --ci
```

## Definition of Done

- The doc note matches the shipped behavior exactly (both the completion and the refusals).
- The fragment passes the style and spelling checks and carries the `(#7209)` reference.
- No `CHANGELOG.md` edit; no page-inventory churn.
