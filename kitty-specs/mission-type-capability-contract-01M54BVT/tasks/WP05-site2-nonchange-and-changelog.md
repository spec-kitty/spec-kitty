---
work_package_id: WP05
title: Site-2 deliberate non-change witness + changelog
dependencies: []
requirement_refs:
- FR-007
- C-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
phase: Phase 5 - Non-change witness + docs
history:
- timestamp: '2026-10-17T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/changelog/CHANGELOG.md
create_intent:
- tests/runtime/test_site2_nonwp_blocks_via_phase3.py
execution_mode: code_change
owned_files:
- docs/changelog/CHANGELOG.md
tags: []
tracker_refs: []
---

# WP05 – Site-2 deliberate non-change witness + changelog

## Goal
Record, as an executable witness and a changelog note, two deliberate decisions: `runtime_bridge.py:878`
(the non-WP CLI pre-check) stays `software-dev`-literal, and `runtime_bridge_io.py:665` (template precedence)
is out of scope.

## Do
- **T013** — `tests/runtime/test_site2_nonwp_blocks_via_phase3.py`: assert that for a custom (non-software-dev) mission
  type, a non-WP step with a missing blocking artifact BLOCKS via the composition-dispatch (Phase 3) path — a
  `kind=blocked` decision — NOT via the software-dev-only CLI pre-check at `runtime_bridge.py:878`. This witnesses that
  site 2 correctly needs no change (custom families already get the equivalent guard elsewhere). Keep it focused and
  non-vacuous; do not duplicate existing board-authority assertions.
- **T014** — Add a `docs/changelog/CHANGELOG.md` entry under [Unreleased] → Changed/Fixed: custom mission types now
  get the WP-advance guard and the substantive-spec gate via the new capability contract; note that the non-WP CLI
  pre-check stays software-dev-scoped by design and that template precedence (`io.py:665`) and the code-producing gate
  (#6328, needing the #6327 capability) are deliberately out of scope. Match the bold-lead before→after style; ≤1200 chars.

## Constraints
- No `src/` change in this WP. Changelog must pass `tests/docs/test_changelog_style.py` + the terminology guard.

## Done when
`pytest tests/runtime/test_site2_nonwp_blocks_via_phase3.py tests/docs/test_changelog_style.py tests/architectural/test_no_legacy_terminology.py -q` green.
