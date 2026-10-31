# Tasks: charter consistency-check honours the project layer (#6749)

**Mission**: `charter-consistency-project-layer-01M67J5F`
**Branch**: `issue-6749-charter-consistency-project-layer`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

One work package: the change is a single predicate module plus its tests, and splitting
the fix from the acceptance evidence would break the red-first trace (the CLI test can
only be red before the fix, and only green after it). Completion is recorded via
`spec-kitty agent tasks mark-status Txxx --status done` (event-sourced; no checkboxes).

## Subtask Index (reference only — not a tracking surface)

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first CLI acceptance: project-layer mission type is coherent through `charter consistency-check` | WP01 | |
| T002 | Red-first controls: unknown mission type still refuses; malformed project mission-type fails closed; catalogue unit test for the project layer | WP01 | |
| T003 | Fix: `_collect_all_offering_ids` passes the canonical project layer roots from `resolve_layer_roots` | WP01 | |
| T004 | Fix: `mission-type` membership comes from the layered roster, read lazily and fail-closed | WP01 | |
| T005 | Verify red→green, blast radius (`tests/charter`, `tests/charter_offering`, CLI charter tests), lint + mypy | WP01 | |
| T006 | Changelog `[Unreleased]` entry with before/after and `(#6749)` | WP01 | |

## Work Packages

### WP01 — Project-layer membership for the consistency check (#6749)
- **Goal**: `charter consistency-check` resolves activated-token membership through the
  same layered authorities its readers use — `IdentityIndex` for artefact kinds (already
  the case since #6433) and `resolve_layered_mission_types` for `mission-type` — and its
  known-id catalogue is no longer structurally blind to the project layer. Unknown and
  malformed input still refuse, and an unreadable roster fails closed.
- **Priority**: P1 (correctness: a false red on a charter that is consistent in force).
- **Independent test**: the CLI acceptance test on the project-layer mission-type
  fixture (`charter consistency-check --json` → `coherent: true`, exit 0) plus its
  same-fixture positive control (`charter mission-type list --json` reports the type
  activated from the project layer). RED on the pre-fix tree, GREEN after T003/T004.
- **Subtasks**: T001, T002, T003, T004, T005, T006
- **Dependencies**: none. **Prompt**: [tasks/WP01-project-layer-membership.md](./tasks/WP01-project-layer-membership.md)
- **Risks**: the roster read must stay lazy (implicit-all-active path performs none);
  a malformed mission-type file must surface as `verification_errors`, never a crash or
  a silent pass; the catalogue change must not widen what counts as known for kinds the
  identity index already decides.

## Parallelization

None — one work package, one lane.

## MVP scope

WP01 is the whole mission: the bounded source fix, its red-first acceptance evidence,
the refusal controls and the changelog entry.

## Post-merge / close-out checklist (not a WP — but tracked here so it is not honor-system)

- Issue #6749 carries the claim, the mission slug follow-up comment and a terminal
  `issue-verdict` verdict at wrap-up.
- Follow-up issue filed for the activation writer's project-blind availability scan
  (`charter activate mission-type <project-layer-type>` → `Unknown mission-type ID`),
  named in the PR's `## Deferred` section.
- Development-assist tests retired or kept with a recorded verdict (any
  `test_issue_6749*` / `test_repro_6749*` name folds into the owning suite).
