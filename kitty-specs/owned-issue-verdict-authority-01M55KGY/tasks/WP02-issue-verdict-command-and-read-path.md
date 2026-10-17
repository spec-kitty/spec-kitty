---
work_package_id: WP02
title: issue-verdict command wiring, coord-owned read path, and red-first proof
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-003
- FR-004
- FR-006
- NFR-001
- C-001
- C-002
- C-003
planning_base_branch: kitty-base-6320
merge_target_branch: kitty-base-6320
branch_strategy: Planning artifacts for this mission were generated on kitty-base-6320. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty-base-6320 unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
- T013
phase: Phase 2 - Command surface
history:
- at: '2026-10-17T19:20:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/integration/test_owned_issue_verdict_authority_6320.py
- tests/integration/test_p0_repro_6320_owned_issue_verdict.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/agent/issue_verdict.py
- src/mission_runtime/resolution.py
- tests/integration/test_owned_issue_verdict_authority_6320.py
- tests/integration/test_p0_repro_6320_owned_issue_verdict.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – issue-verdict command wiring, coord-owned read path, and red-first proof

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Wire `--owned-checkout` into `agent mission issue-verdict`, resolve ownership once (mirror
#6023), and thread the owned fact through resolution, the write dir, the coord-owned read +
legacy-migration path, and the locked re-read/splice/write — so an owned-only mission records
its verdict. Depends on WP01 (the gate must already be owned-aware).

- **FR-001**: owned verdict recorded via `--owned-checkout`.
- **FR-004**: flagless adoption from inside the owned checkout records the verdict.
- **FR-003**: coord-owned read + migration path carries the fact.
- **NFR-001**: fail-closed preserved for an owned fact that resolves no mission.
- **C-001/C-002/C-003**: mirror #6023 carrier; no format/writer-semantics change; red-first + p0-repro.

## Context & Constraints

Mirror the merged #6023 pattern in `src/specify_cli/cli/commands/agent/acceptance_verdict.py`:
imports from `specify_cli.cli.commands._owned_checkout` (`OwnedCheckoutOption`,
`resolve_owned_or_refuse`, `success_false_envelope`) and `LIFECYCLE_OWNED_TOPOLOGIES` from
`specify_cli.core.owned_mission`; option declared as `owned_checkout: OwnedCheckoutOption = None`;
validate once via `resolve_owned_or_refuse(repo_root, owned_checkout, mission, cwd=Path.cwd(), allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES, json_output=json_mode, envelope=success_false_envelope)`; then `mission_slug = owned.mission_slug if owned else resolve_mission_handle(...).mission_slug`.

Grounding in `src/specify_cli/cli/commands/agent/issue_verdict.py` (verify lines):
- `issue_verdict_command` (~L446) — add the `--owned-checkout` option; thread to `do_issue_verdict`.
- `do_issue_verdict` (~L323/L362) — add `owned_checkout`; resolve owned once; derive `mission_slug`/`feature_dir` from the owned fact when present.
- `resolve_for_write(root, mission_slug, ISSUE_MATRIX)` (~L379) — pass `owned` (WP01 made it accept it).
- `_resolve_write_dir(root, mission_slug)` (~L135) — add `owned`; pass to `placement_seam(..., owned=owned)`.
- `_resolve_read_dir` (~L121) → `coord_read_dir_for(...)` and `_migrate_if_needed` (~L171) → `migrate_issue_matrix_to_json(...)` — thread `owned`.
- `_locked_reread_splice_and_write(...)` (~L266) — forward `owned` into `write_issue_matrix(..., owned=owned)` (writer already accepts it).

`src/mission_runtime/resolution.py::coord_read_dir_for` (~L2963) — add `owned`; for owned coord
topologies resolve the owned read dir. It returns `None` for owned `single_branch` (that falls
back to `feature_dir`) — do NOT regress that fallback.

Constraints: C-001 (no new owned authority), C-002 (no matrix-format/writer-semantics change),
NFR-001 (fail-closed when the owned fact resolves no mission).

## Subtasks

T007 Add `--owned-checkout` option to `issue_verdict_command` and thread it to `do_issue_verdict` (WP02)
T008 In `do_issue_verdict`, resolve ownership once via `resolve_owned_or_refuse` and derive `mission_slug`/`feature_dir` from the owned fact when present; pass `owned` to the `resolve_for_write` gate call (WP02)
T009 Thread `owned` through `_resolve_write_dir` → `placement_seam(..., owned=owned)` (WP02)
T010 Thread `owned` through `_resolve_read_dir`/`coord_read_dir_for` and `_migrate_if_needed`/`migrate_issue_matrix_to_json`; keep the owned `single_branch` fallback to `feature_dir` (WP02)
T011 Forward `owned` from `_locked_reread_splice_and_write` into `write_issue_matrix(..., owned=owned)` (WP02)
T012 Red-first integration test: `issue-verdict --owned-checkout P` records a verdict in an owned-only PR-bound single_branch mission; flagless adoption from inside P also records; an owned fact resolving no mission still refuses (reuse #6023 owned R/P/S fixtures) (WP02)
T013 p0-repro test mirroring `tests/integration/test_p0_repro_6023_owned_acceptance_verdict.py` (`p0_repro` marker) (WP02)

## Test strategy

- Reuse the #6023 owned fixtures (`tests/integration/test_owned_acceptance_authority_6023.py`, `test_explicit_checkout_commands.py::checkouts`, `test_owned_pr_bound_finalization.py::pr_bound_checkouts`).
- T012 is red-first: assert the verdict lands in P's `issue-matrix.json`; confirm it fails at the merge-base (MISSION_NOT_FOUND / fail-closed), then implement to green. Include the flagless-adoption case and the fail-closed negative control (same fixture).
- T013: `p0_repro(issue=6320)` marker, mirroring the #6023 p0-repro.
- Test economy: one positive integration case + the two controls; no duplicate assertions or shape-pins. Declare `pytestmark`.

## Definition of Done

- `issue-verdict --owned-checkout` and flagless adoption record owned verdicts; coord-owned read threads owned; `single_branch` fallback intact; fail-closed preserved.
- `ruff`/`mypy`/format clean on touched files; new test files declare markers and join any completeness baseline.
- `mark-status` the subtasks done.

## Risks & reviewer guidance

- `write_issue_matrix` already accepts `owned` — the bug would be forgetting to actually pass it (T011).
- Reviewer: confirm T012's red-first claim (fails on merge-base), the negative control is non-vacuous, and the owned `single_branch` read still falls back to `feature_dir` (no coord regression).
