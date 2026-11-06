---
work_package_id: WP13
title: S7 tidy-first, provenance and topic-branch-only create
dependencies:
- WP02
requirement_refs:
- FR-051
- FR-052
- FR-058
- FR-059
- FR-060
- C-012
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T074
- T075
- T076
- T077
- T078
- T079
- T080
- T081
phase: Phase 5 - S7 topology settled at finalize
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/core/
create_intent:
- tests/specify_cli/cli/commands/agent/test_mission_create_provisional_topology.py
- tests/core/test_protected_mint_switch_occupancy.py
- tests/lanes/test_count_code_lanes.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/meta_keys.py
- src/specify_cli/cli/commands/agent/mission_create.py
- src/specify_cli/core/mission_creation.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/core/mission_creation_protected_mint.py
- src/specify_cli/cli/commands/lifecycle.py
- src/specify_cli/orchestrator_api/design_phase.py
- src/specify_cli/mission_metadata.py
- src/specify_cli/lanes/compute_and_persist.py
- src/mission_runtime/context.py
- tests/specify_cli/cli/commands/agent/test_mission_create_provisional_topology.py
- tests/core/test_protected_mint_switch_occupancy.py
- tests/lanes/test_count_code_lanes.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP13 - S7 tidy-first, provenance and topic-branch-only create

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP13 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP13 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

S7 (#7282), create half:

- FR-051: `create` without `--topology` mints exactly one Mission topic branch `kitty/mission-<slug>-<mid8>` and nothing else (no lane, no lane or coordination worktree, no coordination branch), whatever the target's protection; records `topology: single_branch`, `mission_branch: <topic>`, `topology_source: default`, `topology_settled: false`, `create_return_branch: <branch the write checkout was on>`. Positive control: explicit `--topology coord` on the same repository still creates its coordination branch.
- FR-052: `--topology` (`topology_source: explicit`) and `--owned-checkout` (`owned_checkout`) behave as today.
- FR-058 (create half): `create --json` reports `topology: single_branch` with `topology_provisional: true`, plus `topology_source`.
- FR-059 (help half): one shared `TOPOLOGY_HELP` constant for `mission_create.py:~866`, `lifecycle.py:~162`, `orchestrator_api/design_phase.py:~173`, describing the size default and the topic branch (never "explicit-only").
- FR-060: `--commit-to-target` still requires explicit `--topology single_branch`.
- `orchestrator-api specify` envelope gains `topology_source` / `topology_provisional` (contract 1.24.0, DM `01M6R0BJQ6Q1MV6492EH6HB66H`; WP15 owns the version bump).
- #5676 fixed: the extracted "switch the write checkout" core refuses `WRITE_CHECKOUT_OCCUPIED` / `WRITE_CHECKOUT_DIRTY`.
- SC-007 create half.

## Context & Constraints

- Read: spec User Story 3, FR-050 to FR-061, A-1 to A-7, Edge Cases (create from another branch); `research.md` R-6 (incl. Risks); `data-model.md` §1; `contracts/mission-create-json.md`; WP02 ADR `2026-11-06-3`; CLAUDE.md "Execution Workspace Strategy" (create-time topology, protected mint).
- **C-010**: this WP's create change must not reach a release before WP12 and WP14. It lands on the topic branch with them; do not cherry-pick it alone to `main`.
- Provisional = `single_branch` representation (DM `01M6R0BDYC29D6XMDY72R22CP9`): it reuses the minted `single_branch` write routing (`single_branch_write_ref`), so specify/plan/tasks land on the topic branch with no new placement code.
- R-6 risk: a second `create` run while the root checkout sits on another provisional Mission's topic branch must not record that topic branch as its target; target resolution resolves the primary branch instead (test below). If you think a refusal is better, raise it in review; do not add a code silently.
- `docs/api/orchestrator-api.md` and `orchestrator_api/envelope.py` are owned by WP15; add your field rows to the doc only if WP15 has landed, otherwise list them in your summary for WP15/WP18.
- `restamp_*` sibling of `flatten_coordination_metadata` (`mission_metadata.py:1156`) must be ratchet-registered wherever `flatten_coordination_metadata` is (grep its registration).
- C-011 red-first.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T074 - Red-first create tests

`tests/specify_cli/cli/commands/agent/test_mission_create_provisional_topology.py` (real git; protected and unprotected targets via `tests/git/protected_target_fixtures.py`):

- `test_create_without_topology_mints_only_topic_branch[protected|unprotected]`: exactly 1 new branch, 0 new worktrees, no coordination branch.
- `test_explicit_topology_coord_still_creates_coord_branch` (positive control).
- `test_owned_checkout_unchanged`.
- `test_commit_to_target_still_requires_explicit_single_branch` (FR-060, paired with an accepting explicit create).
- `test_create_json_marks_provisional`.
- `test_create_records_return_branch` (including create run from a branch that is not the target).
- `test_create_target_never_resolves_to_another_missions_topic_branch`.

`tests/core/test_protected_mint_switch_occupancy.py::test_occupied_write_checkout_refuses_switch` and `test_dirty_write_checkout_refuses_switch` (#5676).

### Subtask T075 - `TOPOLOGY_HELP`

- One module constant (where the three importers can reach it without a layer violation; `specify_cli` level, e.g. in `meta_keys.py` or a small help module you own) used by the three call sites. Text: default = size-settled at the first `finalize-tasks` from one topic branch; explicit values listed; `lanes` and `coord` explicit-only.

### Subtask T076 - Protected-mint switch core

- Extract from `core/mission_creation_protected_mint.py` the "switch the write checkout onto the minted branch" core into a function usable by create (and by WP14's compensation). Add the occupancy (`in_progress` WP in the same write checkout, CLAUDE.md `WRITE_CHECKOUT_OCCUPIED` rules incl. #5550) and dirty refusals. Red-first bug fix commit.

### Subtask T077 - `count_code_lanes` [P]

- Pure `count_code_lanes(manifest_or_lanes) -> int` in `lanes/compute_and_persist.py` (excludes `lane-planning`); `tests/lanes/test_count_code_lanes.py`.

### Subtask T078 - `restamp_*` metadata helper [P]

- In `mission_metadata.py`: a sibling of `flatten_coordination_metadata` that promotes `mission_branch` to `coordination_branch` under the same name (used by WP14), ratchet-registered. Unit test inside the existing mission-metadata test dir only if not owned elsewhere; otherwise cover it in WP14's tests and say so.

### Subtask T079 - Meta keys and the default arm

- `meta_keys.py`: `TOPOLOGY_SOURCE_KEY`, `TOPOLOGY_SETTLED_KEY`, `TOPOLOGY_DECISION_KEY`, `CREATE_RETURN_BRANCH_KEY`.
- `mission_create.py::_resolve_default_topology_phase` (`:377`) returns `(topology, source)`; the default arm mints only the topic branch (always, both targets), switches the write checkout via the T076 core, records the keys. `core/mission_creation.py` / `mission_creation_meta.py` write them. `mission_runtime/context.py`: docstring only (no `specify_cli` imports).
- `--pr-bound`: no coordination-unreachable fallback for default Missions (DM `01M6R0QQM5FCPY736008AD4W6V`).

### Subtask T080 - JSON fields

- `create --json`, `specify --json` (`lifecycle.py`) and `orchestrator-api specify` (`design_phase.py`) add `topology_source`, `topology_provisional` per `contracts/mission-create-json.md`.

### Subtask T081 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_mission_create_provisional_topology.py tests/core/test_protected_mint_switch_occupancy.py tests/lanes/test_count_code_lanes.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -n auto --dist loadfile -k "mission_create or create or specify"   # out-of-matrix dir
uv run --frozen pytest tests/core tests/mission_metadata tests/lanes tests/orchestrator_api tests/specify_cli/orchestrator_api tests/mission_runtime tests/git -q -n auto --dist loadfile
uv run --frozen pytest tests/contract/test_orchestrator_api.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict <touched src files>
```

Never `make test-full` or a bare `tests/architectural/` sweep.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP13] ...**`, naming the trace file); the orchestrator appends them.

## Risks & Mitigations

- Every default create now moves the repository root checkout onto the topic branch: the occupancy/dirty refusals and the other-Mission-target test cover the hazards.
- Release coupling C-010: flag it in the PR description.

## Review Guidance

- 1 branch, 0 worktrees on both targets; explicit paths unchanged; JSON fields per contract; one help constant; #5676 fixed red-first.

## Definition of Done

- T074-T081 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T074 T075 T076 T077 T078 T079 T080 T081 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP13 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
