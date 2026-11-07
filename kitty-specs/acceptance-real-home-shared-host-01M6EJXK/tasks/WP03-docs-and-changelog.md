---
work_package_id: WP03
title: Document the shared-host switch and record the change
dependencies:
- WP02
requirement_refs:
- FR-006
- C-001
- SC-001
planning_base_branch: issue-7026-acceptance-real-home-shared-host
merge_target_branch: issue-7026-acceptance-real-home-shared-host
branch_strategy: Planning artifacts for this mission were generated on issue-7026-acceptance-real-home-shared-host. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7026-acceptance-real-home-shared-host unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-acceptance-real-home-shared-host-01M6EJXK
base_commit:
created_at: '2026-11-02T17:58:20.426321+00:00'
subtasks:
- T008
- T009
phase: Phase 3 - Documentation and changelog
history:
- at: '2026-11-02T17:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/development/testing/
create_intent:
- docs/changelog/unreleased/7026.internal.md
execution_mode: code_change
model: ''
owned_files:
- docs/development/testing/acceptance-scenarios.md
- docs/changelog/unreleased/7026.internal.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7026'
---

# Work Package Prompt: WP03 – Document the shared-host switch and record the change

## ⚡ Do This First: Load Agent Profile

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --include agent-profile:python-pedro
```

## Objective

Make the narrowed guard discoverable and record the change for the release notes.

## Requirements

- **T008 — the how-to page.** `docs/development/testing/acceptance-scenarios.md` already has a
  paragraph ending "The real `~/.spec-kitty` must be left untouched. Lock files are ignored in that
  comparison, because another `spec-kitty` process on your machine may touch them." Extend that
  paragraph (do not add a second, competing explanation elsewhere) to state:
  - the default is the whole-tree comparison;
  - on a host that runs several Missions, export `SPEC_KITTY_ACCEPTANCE_SHARED_HOST=1` (truthy:
    `1`/`true`/`yes`/`on`) and the comparison then also skips `spec-kitty-prompts/` and `gate-locks/`,
    the two per-mission, content-addressed runtime-state subtrees any concurrent `spec-kitty` process
    writes — cite `kitty/acceptance/environment/RealHomeFingerprint.java` as the single owner of that
    list rather than restating a second copy;
  - the switch is **ignored on a GitHub Actions runner**, so the nightly keeps the strict comparison;
  - every scenario runs a built-in control that proves a write outside those subtrees still fails it,
    so the narrowing cannot silently become a no-op.
  Refresh the page's `updated:` frontmatter date.
- **T009 — changelog fragment.** Add `docs/changelog/unreleased/7026.internal.md` (internal: this is
  developer tooling, not user-visible CLI behaviour) in the shape
  `docs/changelog/unreleased/README.md` requires: a bold, impact-first lead with the `(#7026)` reference
  and a **Before:**/**After:** pair, under 1,200 characters, US spelling, no heading. Use the issue
  number as the file id until the PR number is known, then rename the file to the PR number (the
  mission's last step does that).

## Constraints

- Two files only. Do not touch `docs/changelog/CHANGELOG.md` (it is assembled from fragments), the
  docs index, or any other page (C-001).
- Keep the docs page's voice: second person, present tense, no marketing.

## Verification

1. `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` → errors=0.
2. `uv run --frozen python -m scripts.docs.check_changelog_style` → pass.
3. `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased` → pass.
4. Read the paragraph back against `RealHomeFingerprint.java`: variable name, truthy values, the two
   subtree names and the CI refusal must all match the shipped code.

## Definition of done

- The how-to page explains the switch and the CI refusal in one paragraph, and points at the owning class.
- The fragment passes the changelog-style and spelling checks.
- No file outside `owned_files` is modified.
