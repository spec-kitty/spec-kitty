---
work_package_id: WP01
title: Phantom-only resume recovery + faithful
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-004
- NFR-001
- NFR-002
- C-001
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Defect A (resume recovery)
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent:
- tests/terminus/test_resume_phantom_only.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/merge/preflight.py
- src/specify_cli/merge/executor.py
- tests/terminus/test_repro_4997.py
- tests/terminus/test_resume_phantom_only.py
tags: []
tracker_refs: []
---
# WP01 — Phantom-only resume recovery + faithful #4997 repro

Close the P0 data-integrity path: a `spec-kitty merge --strategy merge --resume` over a
primary checkout that lags its own HEAD (phantom staged deletions of the mission's own
files) must RECOVER and land all approved code — but only when the lag is *provably pure*.

- [ ] T001 Correct `test_repro_4997.py` fixture to the real behind-own-HEAD window (target advanced, `pre_mutation_target_sha` persisted, primary lagging with phantom staged deletions of the mission's own files). Keep name/assertion; confirm RED first.
- [ ] T002 Add `is_pure_behind_head_lag(repo_root, *, base_sha, env)` to `merge/preflight.py` + focused unit tests.
- [ ] T003 Wire recovery at the `except DestructiveOpRefused` resume handler in `executor.py` (BEHIND_OWN_HEAD + phantom-only → `reset --hard HEAD` + re-preflight + continue; else unchanged abort). Complexity ≤15.
- [ ] T004 New safety test `test_resume_phantom_only.py`: genuine coexisting edit → REFUSE, edit survives.
- [ ] T005 Remove xfail from `test_repro_4997.py`; prove it + `test_repro_4982.py` green.
