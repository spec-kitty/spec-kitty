---
work_package_id: WP01
title: Lane worktree root is not a status surface
dependencies: []
requirement_refs:
- FR-001
- FR-002
- SC-001
- SC-002
- SC-003
created_at: '2026-10-31T08:55:00+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Read-path authority
history:
- at: '2026-10-31T08:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/missions/_read_path_resolver.py
create_intent:
- tests/specify_cli/missions/test_lane_worktree_status_shadow.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/missions/_read_path_resolver.py
- tests/specify_cli/missions/test_lane_worktree_status_shadow.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6466'
---

# WP01 — Lane worktree root is not a status surface

## Goal

Make a lane worktree root unable to answer a status read from its fork-time copy of
`kitty-specs/<slug>/`, so the authority is always the resolved status surface. This removes the
spurious `--force` demand on a routine `for_review` transition (#6466).

## Context

Verified on current main with a real lane worktree (orchestrator-api `start-implementation`):

- `lanes_with_coord` missions keep `status.events.jsonl`/`status.json` **only** on the
  coordination husk; lane worktrees carry neither, so no divergence exists there.
- `lanes` (branch-flat) missions keep them on the primary/mission-branch copy; writes from a
  lane worktree route there. But the lane worktree keeps a **stale tracked copy** of the log
  (fork-time events). `resolve_handle_to_read_path(lane_root, slug)` composes
  `lane_root/kitty-specs/<slug>` and answers from that copy: `wp_snapshot_state` reports
  `planned` while the authority reports `in_progress`. `planned -> for_review` is not a legal
  edge, so the transition refuses and the only escape is `--force`.

The authoritative copy is the resolved status surface. Never a newest-timestamp-wins choice
(C-001), and never the invoking worktree's copy.

## Subtasks

### T001 — Red-first regression test

Author `tests/specify_cli/missions/test_lane_worktree_status_shadow.py`. Build a `lanes` mission
with a real registered lane worktree (git worktree + `lanes.json`), record a
`planned -> in_progress` transition after the worktree exists, then assert that a status read
anchored at the lane worktree root returns `in_progress`. This must fail before T003.

Use `tests/specify_cli/lanes/test_for_review_gate_parity.py` as the fixture blueprint (it builds
the mission, the coordination seed and the lane worktree through the real orchestrator-api
surfaces).

### T002 — Non-vacuity controls

Same fixture, three controls:

1. the authoritative read (root/primary anchor) reports the same lane — proves the assertion is
   not vacuously satisfied by a broken fixture;
2. a `lanes_with_coord` mission anchored at its lane worktree root still resolves the
   coordination husk (FR-002);
3. an independent clone (not a linked worktree) still answers from its own checkout.

### T003 — Re-anchor at the guarded read-side seam

In `src/specify_cli/missions/_read_path_resolver.py`, canonicalize a handed root that classifies
as `WorktreeTopology.LANE_WORKTREE` to the repository's main worktree root before the
primary-meta probe and the surface composition. Key it on the existing classifier
(`classify_worktree_topology`) — never on path shape and never on "is a linked worktree" (the
coordination worktree is a linked worktree and stays the authority). Reuse the existing registry
read; do not add a per-read git shell-out.

### T004 — Changelog

`docs/changelog/CHANGELOG.md`, `[Unreleased]`, bold impact-first lead, before/after under 1,200
characters, `(#6466)`.

## Definition of Done

- The new test fails on the pre-fix tree and passes after T003.
- `pytest tests/specify_cli/missions/test_lane_worktree_status_shadow.py` green.
- Existing read-path / resolver / lane suites still green (targeted files only).
- Changelog entry present.
