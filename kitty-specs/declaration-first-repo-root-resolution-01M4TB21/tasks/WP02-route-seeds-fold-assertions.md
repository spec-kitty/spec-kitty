---
work_package_id: WP02
title: Route the command-entry seeds and fold the assertions
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- C-004
- SC-001
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-declaration-first-repo-root-resolution-01M4TB21
base_commit: 8ea0b86b94379db5802a09ca77c954763be995c1
created_at: '2026-10-13T10:05:30Z'
subtasks:
- T005
- T006
- T007
phase: Phase 2 - Route + fold (tidy-first enabler)
history:
- at: '2026-10-13T10:05:30Z'
  actor: system
  action: Prompt generated via spec-kitty tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/mission_record_analysis.py
create_intent:
- tests/specify_cli/cli/test_command_target_routing.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/mission_record_analysis.py
- tests/specify_cli/cli/test_command_target_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6142'
---

# Work Package Prompt: WP02 – Route the command-entry seeds + fold the assertions

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` and run `spec-kitty charter context --action implement --json`.

## Objectives & Success Criteria

Make the WP01 entry the producer of a bounded, named set of mission-scoped command-entry
`repo_root`/branch targets, and fold the hand-placed "never `Path.cwd()`" assertions at
those sites into the typed call. **Tidy-first, behaviour-preserving at the routed sites**
(the ambient-disagreement correction is witnessed separately in WP03).

### IC-2 selection criteria (apply per site, after reading it)

Route a site iff: (a) it is **mission-scoped** (operates on a named/stored Mission, not
project-global); (b) it today seeds `repo_root`/branch from ambient location; (c) routing
is behaviour-preserving except in the ambient-disagreement case; (d) it is **NOT** a
consolidation/branch-integration site, **NOT** the `implement_claim` #2453-deferred
ratchet-allowlisted guard, **NOT** create-time, **NOT** an honest-invocation-identity
input.

### Final routed set (after per-site read)

Per-site reading showed the command-entry `locate_project_root() or Path.cwd()`
prologues are mission-AGNOSTIC root discovery resolved BEFORE the mission slug is known
(the slug is resolved from the root), and the branch/placement is already
declaration-first downstream — so those prologues have no ambient-BRANCH defect (their
canonical form is `get_project_root_or_exit`). The genuine declaration-first-branch
consumers are the command-entry callers of `get_feature_target_branch(repo_root, slug)`,
whose fallback carries the ambient-HEAD bias (`resolve_primary_branch(..., bias=True)`).
Routed — `cli/commands/agent/mission_record_analysis.py` (record-analysis, an ADR-named
mutating command), BOTH target-branch sites (`:336`, `:521`). Both pass a FULL canonical
slug (`feature_dir.name`), so the declaration case is byte-identical and ONLY the ambient
fallback is corrected to non-ambient (`resolve_primary_branch(..., bias=False)`). It is one
coherent command, two sites — a tight, provably-safe routing that establishes the entry as
the producer of record-analysis's declaration-first target branch.

Filed-and-linked (NOT routed), with reasons (WP03 T010): `mission_accept_merge.py`
(merge-target — consolidation non-goal, C-001); `mission_create.py` (create-time —
declaration being minted); `mission_branch_context.py` (display recommender, already
`bias=False`); `tasks_parsing_validation.py` (`get_feature_target_branch` is dependency-
injected — higher-risk surface, Increment-2); `tracer_append.py` (passes a fuzzy
`--mission` handle — routing risks a declaration→fallback change without the
canonicalization the entry deliberately omits); `implement_claim.py:81` (#2453-deferred
ratchet-allowlisted guard); the mission-agnostic root-discovery prologues (`verify.py`,
`issue_verdict.py`, `decision.py`, `context.py` — canonical form is
`get_project_root_or_exit`). Record the final set + rationale in the design-decisions
tracer.

## Constraints

- Behaviour-preserving at routed sites; the only behaviour change is the ambient-
  disagreement correction (WP03).
- Each routed site's hand-placed "never `Path.cwd()`" comment is REPLACED by the typed
  call — the invariant moves into the entry's construction (FR-005), it is not duplicated.
- `test_no_write_side_rederivation.py` stays green with no allowlist change.
- ruff + mypy clean; complexity ≤ 15.

## Validation (targeted test surface)

- `tests/specify_cli/cli/test_command_target_routing.py` (T007): for each routed site,
  assert the target comes from the WP01 entry and no ambient `Path.cwd()`/branch seed
  remains.
- The touched commands' existing test files (e.g. `tests/specify_cli/cli/` verify /
  issue-verdict suites) stay green.
- `.venv/bin/python -m pytest tests/specify_cli/cli/test_command_target_routing.py <touched-command-test-files> -q`
- `.venv/bin/python -m pytest tests/architectural/test_no_write_side_rederivation.py -q`
