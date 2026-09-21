---
work_package_id: WP04
title: Docs & changelog
dependencies:
- WP02
- WP03
requirement_refs:
- FR-003
planning_base_branch: fix/finalize-repin-orphaned-planning-commit
merge_target_branch: fix/finalize-repin-orphaned-planning-commit
branch_strategy: Planning artifacts for this mission were generated on fix/finalize-repin-orphaned-planning-commit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/finalize-repin-orphaned-planning-commit unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
phase: Phase 2 - Polish
history:
- timestamp: '2026-09-21T00:00:00Z'
  agent: system
  action: Prompt generated via tasks phase authoring
agent_profile: curator-carla
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match.

---

## Objective

Document the user-facing fix once WP02 and WP03 have landed. Issue #4827.

## Subtasks

### T018 — CHANGELOG `[Unreleased]` Fixed entry
Add a `### Fixed` entry under `## [Unreleased]` in `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink to it). Impact-first bold lead with the `(#4827)` ref, then before→after. Example shape:

> **`finalize-tasks` now heals a `planning_commit_sha` orphaned by a mid-mission rebase instead of wedging the mission (#4827).** Before: after rebasing a lanes mission onto a moved base, a plain `finalize-tasks` silently preserved the rewritten-away (orphaned) planning commit and `--refresh-planning-commit` refused to re-point it, so lane allocation and the dependency-lane merge dead-ended against a commit no longer on the branch — the only escape was hand-editing `lanes.json`. After: finalize classifies the recorded pin against the target-branch tip (advanced / orphaned / foreign); a plain run fails closed on a proven orphan naming the recovery (still preserving on non-git/foreign/uncapturable), and `finalize-tasks --refresh-planning-commit --allow-orphaned` re-pins to the live planning tip. Every recorded-pin consumer (lane allocation, workspace reconcile, the claim gate, and the owned-review base) now names the stale pin and the re-pin recovery instead of a false merge conflict, a diff against a dead base, or a bare refusal. Bare `--refresh-planning-commit` keeps its advance-only semantics unchanged.

Keep the wording accurate to what WP02/WP03 actually shipped — read the merged code before finalizing the prose (do not describe behavior that changed during implementation).

### T019 — Cross-checks
- Confirm `docs/api/agent-subcommands.md` already reflects `--allow-orphaned` (regenerated in WP02); if the doc-freshness gate flags drift, note it (regen belongs to WP02's surface, not here).
- Optionally mention in the entry that the fix reduces false dependency-lane conflicts (a side effect of #3936's surface) and folds the #4178 drift-WARN correction — only if user-facing.

## Branch Strategy

Planning branch and merge target: `fix/finalize-repin-orphaned-planning-commit`. **Depends on WP02 and WP03.** Per computed lane from `lanes.json`.

## Definition of Done

- `[Unreleased]` Fixed entry present, impact-first, `(#4827)`, before→after, accurate to shipped behavior.
- No terminology-canon violations (run `pytest tests/architectural/test_no_legacy_terminology.py`).

## Risks / reviewer guidance

- Do not describe unshipped behavior — reconcile the prose with the merged WP02/WP03 diff.
- `planning_artifact` WP: every owned file is under `docs/` (no code paths).
