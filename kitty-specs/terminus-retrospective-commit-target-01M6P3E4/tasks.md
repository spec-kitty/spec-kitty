# Work Packages: Terminus retrospective commit target (#7201)

**Inputs**: Design documents from `kitty-specs/terminus-retrospective-commit-target-01M6P3E4/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: required — this is a defect fix; the acceptance criteria are the red-first tests.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/specify_cli/...`, `tests/...` (this repository).

---

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Write the red-first real-git test: terminus commits onto the resolved target; refuses without one (same fixture, both halves) | WP01 | |
| T002 | Add the keyword-only `destination_ref` parameter to `run_retrospective_postcondition` and forward it to `_commit_captured_retrospective` | WP01 | |
| T003 | Forward `destination_ref` into `commit_merge_bookkeeping(destination_ref_override=...)` in `_commit_captured_retrospective` | WP01 | |
| T004 | Carry `destination_ref` on the teardown seam (`teardown_coordination_topology` → `_persist_retrospective`) | WP01 | |
| T005 | Pass `run.lanes_manifest.target_branch` from `consolidation/phase_teardown.py::_teardown_coord_worktree` | WP01 | |
| T006 | Pass `resolved_target_branch` from `cli/commands/consolidate.py::_run_real_merge` | WP01 | |
| T007 | Make the refusal's recovery command carry the target (`_rerun_command` / `_recovery_guidance`) | WP01 | |
| T008 | Add `mission close --target` and thread it to the teardown persist leg (both close legs) | WP01 | |
| T009 | CLI test: `mission close --target` forwards the destination; no `--target` keeps today's behaviour | WP01 | |
| T010 | Regenerate `docs/api/cli-commands.md` for the new `mission close` option and verify freshness | WP01 | |
| T011 | Run the targeted blast radius: new tests, terminus/teardown/consolidation contracts, the two named architectural ratchets, ruff/mypy | WP01 | |

---

## Work Package WP01: Thread the resolved landing target through the terminus commit (Priority: P1)

**Goal**: The terminus retrospective bookkeeping commit lands on the branch the consolidate run
actually merged into, and the recovery command the refusal prints can be aimed at that branch.

**Independent Test**: On a scratch repo whose `kitty-specs/<slug>/meta.json` names
`target_branch: main` and whose HEAD is `topic/x`, calling the terminus authority
`run_retrospective_postcondition(..., destination_ref="topic/x")` commits both artifacts onto
`topic/x` leaving `main` untouched; on the same fixture with no `destination_ref` it still
refuses and leaves both files uncommitted.

**Prompt**: `tasks/WP01-terminus-commit-target-threading.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003

### Included Subtasks

T001 Write the red-first real-git test: terminus commits onto the resolved target; refuses without one (same fixture, both halves)
T002 Add the keyword-only `destination_ref` parameter to `run_retrospective_postcondition` and forward it to `_commit_captured_retrospective`
T003 Forward `destination_ref` into `commit_merge_bookkeeping(destination_ref_override=...)` in `_commit_captured_retrospective`
T004 Carry `destination_ref` on the teardown seam (`teardown_coordination_topology` → `_persist_retrospective`)
T005 Pass `run.lanes_manifest.target_branch` from `consolidation/phase_teardown.py::_teardown_coord_worktree`
T006 Pass `resolved_target_branch` from `cli/commands/consolidate.py::_run_real_merge`
T007 Make the refusal's recovery command carry the target (`_rerun_command` / `_recovery_guidance`)
T008 Add `mission close --target` and thread it to the teardown persist leg (both close legs)
T009 CLI test: `mission close --target` forwards the destination; no `--target` keeps today's behaviour
T010 Regenerate `docs/api/cli-commands.md` for the new `mission close` option and verify freshness
T011 Run the targeted blast radius: new tests, terminus/teardown/consolidation contracts, the two named architectural ratchets, ruff/mypy

### Implementation Notes

- The one design rule: never touch `safe_commit` / `commit_guard` / the fail-open policy. The
  refusal is correct; only the destination the caller asks for changes.
- `commit_merge_bookkeeping` already takes `destination_ref_override`; the terminus just has to
  pass it. Do not invent a second resolution authority and do not read HEAD.
- `teardown_coordination_topology` is shared with merge cleanup, `mission close --discard` and
  `consolidate --abort`; keep the new parameter keyword-only with a `None` default so every
  other leg keeps today's behaviour byte-for-byte.
- `mission close` cannot recover the resolved target from disk after a successful consolidate
  (`clear_state()` removes `state.json`, and `--target` is never written back to
  `lanes.json`/`meta.json`), which is exactly why the option is explicit rather than derived.

### Parallel Opportunities

- None: the subtasks form one call chain through the same seam, so the work is sequential.
  T010 (docs regeneration) may be run any time after T008.

### Dependencies

- None (single work package).

### Risks & Mitigations

- **Risk**: a caller forgetting the new parameter silently keeps the bug for its path.
  *Mitigation*: T001's test drives the public entry point with and without the parameter, and
  T009 pins the CLI wiring; the red test must go red on the pre-fix tree.
- **Risk**: the change quietly weakens the guard. *Mitigation*: the same-fixture negative
  control (no `destination_ref` → still refused, still fail-open, no ref moved) is part of the
  same test module, and `test_no_write_side_rederivation.py` + `test_guard_capability_call_sites.py`
  are run explicitly.
- **Risk**: regenerating the whole CLI reference churns unrelated sections (other agents' work,
  shared asset caches). *Mitigation*: verify the produced diff is confined to the `mission close`
  section; if the regenerator is non-deterministic, hand-apply the `--target` option row and
  confirm with `check_docs_freshness --ci`.
