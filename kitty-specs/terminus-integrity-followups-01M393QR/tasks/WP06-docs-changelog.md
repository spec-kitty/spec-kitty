---
work_package_id: WP06
title: Docs and CHANGELOG
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
planning_base_branch: fix/terminus-integrity-followups
merge_target_branch: fix/terminus-integrity-followups
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-integrity-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-integrity-followups unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-integrity-followups-01M393QR
base_commit: 8e9ee7526946c7be444615d1ba08ef6405f3dc72
created_at: '2026-09-24T10:05:21.631118+00:00'
subtasks:
- T024
- T025
phase: Phase 3 - Integration
history:
- at: '2026-09-24T07:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/changelog/CHANGELOG.md
create_intent: []
execution_mode: code_change
owned_files:
- docs/changelog/CHANGELOG.md
- docs/architecture/status-model.md
- AGENTS.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Docs and CHANGELOG

## ⚡ Do This First: Load Agent Profile
Use the `/ad-hoc-profile-load` skill to load `curator-carla` (role `implementer`, agent `claude`) before
reading further. State what you applied, then continue.

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in fenced code blocks.

## Objectives & Success Criteria

Document the shipped behavior honestly (DIRECTIVE_010: code is source of truth, docs mirror shipped behavior).
Depends on WP01–WP05. Success:

- A CHANGELOG entry in the project's Before/After house style covering: default squash now enforces the
  excluded/closed-world content axis (#5013 / #4945 #4977 #4981 on the default flow); resume honors persisted
  strategy + preserves pre-interrupt lane tips (#4982 #4997 #4985 #4991); surface-write refuses stale-local-head
  self-materialization + issue-verdict routes through the fail-closed resolver (#4970).
- Any now-false claim that "squash defers content verification" in `AGENTS.md` / `docs/architecture/status-model.md`
  is corrected to reflect the shipped squash content axis — WITHOUT over-claiming: #4945/#4977/#4981 are closed at
  the **integrity-gate** level (the positional lane re-lettering ROOT is untouched); the 3-way merge-resolution
  content case remains a tracked follow-up.

**Read first**: the existing CHANGELOG Before/After entries (recent ones in `docs/changelog/CHANGELOG.md`), the
merge/reducer notes in `AGENTS.md`, and `docs/architecture/status-model.md`. Confirm what actually shipped by
reading the merged WP diffs — do not document intended-but-unshipped behavior.

## Subtasks

### T024 — CHANGELOG entry (docs/changelog/CHANGELOG.md)
- Add a dated entry in the house Before/After style. Be specific and honest: name the issues closed and the
  ones only partially addressed (e.g. if the 3-way residual stays xfail). Do not claim a child is fully closed
  if it only closes at the integrity-gate level.

### T025 — doc correction (AGENTS.md + docs/architecture/status-model.md)
- Correct any statement that the default squash defers content/reachability verification to reflect the new
  squash-sound blob-attribution axis. Note the honest residual (3-way merge-resolution). Keep the reducer /
  #4990 named-open notes intact (out of scope here). Add/refresh an `updated: YYYY-MM-DD` date if the doc uses
  freshness dates.

## Definition of Done
- CHANGELOG entry present and honest; docs corrected with no over-claim; `updated:` dates refreshed where used.
- No code edits (docs-only WP). Markdown lints clean if a docs linter runs.

## Risks / reviewer guidance
- Reviewer: verify the docs match the ACTUAL shipped behavior (read the WP diffs), and that nothing over-claims
  #4945/#4977/#4981 or the 3-way residual. Confirm the reducer/#4990 notes are untouched.
