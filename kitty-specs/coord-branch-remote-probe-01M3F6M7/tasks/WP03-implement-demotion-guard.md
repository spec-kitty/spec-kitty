---
work_package_id: WP03
title: Implement auto-commit topology-demotion REFUSE guard (#4979)
dependencies:
- WP01
requirement_refs:
- FR-005
- NFR-002
planning_base_branch: issue-4979-coord-branch-remote-probe
merge_target_branch: issue-4979-coord-branch-remote-probe
branch_strategy: Planning artifacts for this mission were generated on issue-4979-coord-branch-remote-probe. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4979-coord-branch-remote-probe unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-coord-branch-remote-probe-01M3F6M7
base_commit: 4d083c4012c02c586b81bc7e6f1b9602b6b1546e
created_at: '2026-09-26T17:12:34.403887+00:00'
subtasks:
- T010
- T011
- T012
phase: Phase 2 - implement defense-in-depth
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_implement_demotion_guard_4979.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/implement.py
- tests/specify_cli/cli/commands/test_implement_demotion_guard_4979.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#4979'
---

# Work Package Prompt: WP03 — Implement auto-commit demotion guard

## ⚡ Do This First: Load Agent Profile

Load the `implementer-ivan` profile via `/spk-doctrine-profile-load` before parsing the rest.
Read `.kittify/charter/charter.md` and run `spec-kitty charter context --action implement --json`.

- **Profile**: `implementer-ivan` · **Role**: `implementer` · **Agent/tool**: `claude`

## Objectives & Success Criteria

Stop `implement`'s planning-artifact auto-commit from silently carrying a `meta.json` topology
demotion (a flatten) to the planning/target branch — the final propagation hop in #4979's chain
(`_commit_planning_artifacts_transaction`, `src/specify_cli/cli/commands/implement.py:~746`,
staged by `resolve_planning_artifact_staging` at :724). Defense-in-depth: with WP01 in place the
doctor no longer flattens, but any other source of an uncommitted flatten (hand-edit, future
regression) must not silently propagate a whole-team routing change.

- **SC (#4979, FR-005) — deterministic REFUSE:** when the uncommitted `meta.json` is a topology
  demotion — HEAD `coordination_branch` is non-null AND the working copy drops it to
  absent/null — planning-artifact staging REFUSEs with an actionable message and does NOT commit
  the demotion. Proven RED-first (T010): today the demotion rides into the
  `chore: planning artifacts` commit on the target branch.
- **SC — untracked ALLOW:** a `meta.json` with no HEAD baseline (`git show
  HEAD:kitty-specs/<slug>/meta.json` exit 128 — a legitimate first commit, including a
  genuinely-flat mission) is ALLOWED (fail-open is correct here).
- **SC — corrupt REFUSE:** an unparseable `meta.json` on either the HEAD or working side ⇒
  fail-closed REFUSE with an actionable message.
- **SC — no false refusal:** an ordinary non-demoting `meta.json` edit (e.g. adding
  `source_description`, or a mission that was already flat at HEAD) commits exactly as today.
- New/changed code: complexity ≤ 15, focused tests for each branch, ruff + ruff format + mypy clean.

## Context & Constraints

- **Predicate (robust key):** demotion iff HEAD `coordination_branch` non-null → working
  absent/null. A `topology` coord→lanes demotion corroborates but is NOT required (legacy HEAD
  meta may lack the field). Baseline via `git show HEAD:kitty-specs/<slug>/meta.json`; exit 128
  ⇒ no baseline ⇒ ALLOW.
- **Insertion point:** hook the staging DECISION seam — extend
  `detect_structural_planning_changes` (implement.py:678, already the refuse-before-commit
  pattern via `_print_structural_planning_refusal`) or `resolve_planning_artifact_staging`
  (:724). Do NOT add a parallel commit interceptor / second gate authority. meta.json is
  PRIMARY-partitioned and only matters when it is in the dirty `files_to_commit` set.
- **REFUSE, not withhold** — a single deterministic contract for the ATDD assertion (do not
  leave "refuse OR silently drop the file" as an either/or). Message names the demotion and how
  to recover (restore `coordination_branch`, or intentionally flatten via the sanctioned path).
- ATDD red-first: T010 reproduces the issue's step-3 propagation — a flattened (uncommitted)
  `meta.json` in the planning-artifact source dir rides into the auto-commit (RED). Pin `#4979`,
  `@pytest.mark.regression`.

## Implementation Sketch

1. **T010 (RED):** fixture — a coord mission whose HEAD `meta.json` has `coordination_branch`,
   working copy flattened + uncommitted; run the implement planning-artifact staging/commit path
   and assert the demotion lands in the commit (RED).
2. **T011:** add the demotion predicate helper (reuse a WP01 `meta_json_at_ref` helper if
   exposed) and wire the REFUSE into the staging decision; handle exit-128 ALLOW and
   corrupt-REFUSE.
3. **T012:** blast radius + ruff/format/mypy + tracer append.

## Validation

```
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/cli/commands/test_implement.py \
  tests/specify_cli/cli/commands/test_implement_writeside.py \
  tests/specify_cli/cli/commands/test_implement_placement_routing.py \
  tests/specify_cli/cli/commands/test_implement_coord_idempotency.py \
  tests/specify_cli/cli/commands/test_implement_demotion_guard_4979.py -q
.venv/bin/python -m ruff check <touched> && .venv/bin/python -m ruff format --check <touched>
.venv/bin/python -m mypy <touched>
```
Plus `make test-fast`. Append to `tracers/`.
