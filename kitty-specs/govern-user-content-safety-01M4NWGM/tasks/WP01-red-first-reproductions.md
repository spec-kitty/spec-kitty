---
work_package_id: WP01
title: 'Red-first reproductions for #5964, #5434, #4796'
dependencies: []
requirement_refs:
- SC-001
- SC-002
- SC-003
- NFR-001
- NFR-002
planning_base_branch: fix/5964-5434-4796-govern-user-content
merge_target_branch: fix/5964-5434-4796-govern-user-content
branch_strategy: Planning artifacts for this mission were generated on fix/5964-5434-4796-govern-user-content. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/5964-5434-4796-govern-user-content unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-govern-user-content-safety-01M4NWGM
base_commit: 712caec82fa7fa265cca177d3b978ecf168806b9
created_at: '2026-10-11T16:41:06.740529+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Red-first
history: []
agent_profile: python-pedro
authoritative_surface: tests/
create_intent:
- tests/upgrade/test_agents_skills_team_content_survives_5964.py
- tests/lanes/test_lane_worktree_spec_kitty_residue_5434.py
- tests/orchestrator_api/test_consolidate_mission_premutation_timing.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/upgrade/test_agents_skills_team_content_survives_5964.py
- tests/lanes/test_lane_worktree_spec_kitty_residue_5434.py
- tests/orchestrator_api/test_consolidate_mission_premutation_timing.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '5964'
- '5434'
- '4796'
---
# Work Package Prompt: WP01 – Red-first reproductions for #5964, #5434, #4796

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (role: implementer) before parsing the rest of this prompt. Then run `spec-kitty charter context --action implement --json` and apply it.

## Goal

Land three failing-first acceptance tests, one per issue, each red for the issue's actual reported reason, asserting on real observable state. These are the ATDD contracts the fix WPs (WP02/03/04) turn green. Do NOT fix anything in this WP.

## Subtasks & exact targets

### T001 — `tests/upgrade/test_agents_skills_team_content_survives_5964.py`
Pins #5964. Build a throwaway git repo (network-free) with a committed, user-authored `.agents/skills/team-review/SKILL.md` owned by NEITHER `.kittify/skills-manifest.json` NOR `.kittify/command-skills-manifest.json`, plus a genuinely spec-kitty-projected `.agents/skills/spec-kitty.implement/SKILL.md`. Import and run `AgentsSkillsGitignoreBackfillMigration().apply(root)` then the autocommit selectors (`migration_index_untracks`, and the upgrade-commit build). Assert (RED today): the team path is still in `git ls-files` and is NOT staged `D`, and does NOT appear in the upgrade commit's deletions (`git log --diff-filter=D`); the projected `spec-kitty.implement` path IS untracked. (Mirror the direct-import approach the grounding repro used; do not depend on an old PyPI CLI.)

### T002 — `tests/lanes/test_lane_worktree_spec_kitty_residue_5434.py`
Pins #5434. Build a consumer-like repo whose tracked `.gitignore` does NOT contain `.spec-kitty/` (this repo's own does — that masks the bug). Allocate a lane worktree via `allocate_lane_worktree`, drop `.spec-kitty/review-lock.json` into it. Assert (RED today): `git -C <wt> status --porcelain` is empty AND re-allocating (reuse route; and a crash-recovery variant where the dir was removed but the branch survives) does not raise `DirtyWorktreeError`.

### T003 — `tests/orchestrator_api/test_consolidate_mission_premutation_timing.py`
Pins #4796. Model the real-repo fixture on `tests/orchestrator_api/test_mission_branch_moved_error_code.py`. Stand up a lanes mission with a target branch, a mission branch, and a real code-lane worktree carrying an approved WP that passes merge-gates/origin/approved-bound, then place ONE untracked non-ignored operator file in the lane worktree. Capture `git rev-parse refs/heads/<target>` before, call the real `consolidate_mission(...)`. Assert (RED today on items 2-4): (1) exit 1 + `PREFLIGHT_FAILED` carrying `MERGE_UNSAFE_WORKTREE_DIRTY`; (2) target ref UNCHANGED; (3) WPs NOT stamped merged/done; (4) no push occurred (bare `origin`, assert its target ref unmoved). Pre-fix the merge completes before the cleanup refusal so (2)-(4) fail; markers `git_repo, non_sandbox, regression`.

### T004 — Prove red for the right reason; mark + commit
Run each new test on the mission base and confirm it fails for the issue's reason (not a fixture/import error). Record the red output in the WP notes. Commit as the first commit of the lane.

## Constraints
- Assertions on real `git ls-files` / `git status --porcelain` / refs — never on "a file was written".
- No skip/xfail/quarantine. No `# noqa`/`# type: ignore`. `ruff` + `mypy --strict` clean on the new files.

## Validation
`PWHEADLESS=1 .venv/bin/python -m pytest tests/upgrade/test_agents_skills_team_content_survives_5964.py tests/lanes/test_lane_worktree_spec_kitty_residue_5434.py tests/orchestrator_api/test_consolidate_mission_premutation_timing.py -q` → all three RED for the right reason. Record commands + counts in WP notes.
