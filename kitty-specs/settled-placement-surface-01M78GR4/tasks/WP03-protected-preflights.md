---
work_package_id: WP03
title: Protected-branch preflights judge the write surface (#7601)
dependencies: []
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-012
- SC-002
- C-002
- C-003
subtasks: [T010, T011, T012, T013]
agent: claude
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/test_implement_settled_protected_root.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/implement_claim.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_shared.py
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- tests/architectural/test_no_write_side_rederivation.py
- tests/specify_cli/cli/commands/test_implement_settled_protected_root.py
role: implementer
---

# WP03 — Protected-branch preflights judge the write surface (#7601)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

For a settled default Mission, `agent action implement WP01` and `agent tasks move-task … --note …`
succeed from a repository root checkout on protected `main`, because their protected-branch checks
judge the branch the commit lands on (`placement_seam(...).write_target(WORK_PACKAGE_TASK).ref`, the
topic branch) instead of the root checkout's HEAD or the meta `target_branch`. A Mission whose write
target really is protected keeps being refused (FR-006, FR-007, FR-008, FR-012; #7601).

## Context

- Live failure: `implement WP01` on the settled fixture with the root on protected `main` →
  "Refusing to start implementation status on protected branch 'main' before mutating status files …
  rerun with --no-auto-commit" (`cli/commands/implement_claim.py:108-113`). `agent action implement`
  has no `--no-auto-commit` option (exit 2). With the check patched out, implement succeeds and the
  claim commits land on the topic branch (the #5738 HEAD check already judges the holder, #7372).
- The check: `_raise_if_status_commit_protected` → `_status_commit_destination_branch(repo_root,
  fallback)` = `get_current_branch(repo_root) or fallback_branch`. That line is the allow-listed
  deferred re-derivation tracked as #2453 in `tests/architectural/test_no_write_side_rederivation.py`
  (`_ALLOW_LIST_SEED` ≈ line 256–343, plus a staleness twin-guard ≈ line 502 that asserts the
  allow-listed line still exists). Ruling `01M78GS4H8AAJW5Y4ATZ3TES6B`: judge
  `write_target(WORK_PACKAGE_TASK).ref` and drain the entry in the same change. Accepted side effect:
  a flat Mission whose root HEAD differs from a protected target now gets this protected refusal
  instead of the later #5738 mismatch refusal (both refuse; note it in the PR).
- Second gate (same class): `move-task --note` on protected `main` →
  `WP_METADATA_UNSUPPORTED_ON_PROTECTED_COORD_BRANCH` (`tasks_transition_core._guard_unsupported_skip_metadata`),
  because `tasks_move_task.py:≈701` feeds `st.target_branch` (meta, `main`) to
  `tasks_shared._skip_target_branch_commit`, while the WP file commits to the topic branch.

Implement with: `spec-kitty agent action implement WP03 --agent claude --mission settled-placement-surface-01M78GR4`

## Branch Strategy

Base and merge target: `fix/7546-settled-placement-surface`; `single_branch`, sequential.

### Subtask T010: Red — protected root on a settled Mission, plus a positive control

**Steps**:
1. Create `tests/specify_cli/cli/commands/test_implement_settled_protected_root.py` on the real
   fixture (`make_default_mission(tmp_path, THREE_LANES)` — root on protected `main` — plus `plan.md`
   committed before finalize and an analysis report recorded, exactly as
   `scratchpad/repro/test_repro_7601.py` did: write `plan.md`, commit, `run_finalize`, then
   `spec-kitty agent mission record-analysis --mission <slug> --input-file -`). Drive
   `spec-kitty agent action implement WP01 --mission <slug> --agent claude` as a subprocess from the
   root (match how `tests/specify_cli/cli/commands/test_implement_placement_reachability.py` invokes
   it if it has a helper).
   - Assert exit 0, `main`'s tip unchanged, a "Start WP01" claim commit on the topic branch.
2. `move-task WP01 --to <a lane reachable from the current one> --note "…" --mission <slug>` from the
   root on `main` → exit 0, the activity note committed on the topic branch.
3. Positive control (FR-008): an explicit `--topology lanes_with_coord` Mission targeting protected
   `main` (use `make_default_mission(..., explicit="lanes_with_coord")` if it yields a coordination
   branch distinct from `main`; otherwise build it the way `test_implement_placement_reachability.py`
   builds coordination fixtures) → `implement` still refuses on the protected rule.
4. Commit red: `test(implement): pin implement and move-task --note from a protected root on a settled Mission (#7601)`.

### Subtask T011: Preflight judges `write_target(WORK_PACKAGE_TASK).ref`; drain #2453

**Steps**:
1. Replace `_status_commit_destination_branch` with a seam read:
   `placement_seam(repo_root, mission_slug).write_target(MissionArtifactKind.WORK_PACKAGE_TASK).ref`
   (thread `mission_slug`; it is already passed to `_raise_if_status_commit_protected`). If
   `mission_slug` is `None` (legacy path), keep the current behaviour only if the rederivation gate
   allows it — otherwise require the slug (check callers in `implement_phases.py`).
2. Remove the #2453 allow-list entry and its staleness twin-guard expectation for this line in
   `tests/architectural/test_no_write_side_rederivation.py` (shrink only; do not add entries).
3. Run the gate file and `tests/specify_cli/cli/commands/test_implement_claim.py`,
   `test_implement_phases.py`; update tests that pinned the old message only where the ruling's
   accepted message change applies (say so in the commit message).

### Subtask T012: move-task's skip gate gets the WP file's ref

**Steps**: at `tasks_move_task.py:≈701`, pass the WORK_PACKAGE_TASK write target ref instead of
`st.target_branch` to `_skip_target_branch_commit` (keep `st.target_branch` for everything else —
banners, status). Keep `_skip_target_branch_commit`'s short-circuit and its "NOT a routing authority"
contract; update its docstring parameter name/meaning (`commit_ref`). Ensure the message in
`_guard_unsupported_skip_metadata` names the ref it judged.

### Subtask T013: Remedy text

**Steps**:
1. `_protected_branch_status_commit_error`: drop "rerun with --no-auto-commit" for
   `agent action implement` callers (or name it only for the top-level `spec-kitty implement`, which
   has the flag — check which command reaches the function and phrase per caller). Name the branch
   judged and say the Mission's writes land on `<ref>`.
2. `_guard_unsupported_skip_metadata`: same — only suggest options `move-task` accepts (it does accept
   `--no-auto-commit`; verify with `--help`).
3. No refusal code or exit code changes (decision `01M78GS9KQZAMG3Y0YC53ER1KE`).

## Definition of Done

- Red commit first; green after. `main` never moves in any test.
- `pytest tests/specify_cli/cli/commands/test_implement_claim.py tests/specify_cli/cli/commands/test_implement_phases.py tests/specify_cli/cli/commands/test_implement_placement_reachability.py tests/specify_cli/cli/commands/agent -q -k "move_task or skip_target or protected"` green, plus the new module.
- `pytest tests/architectural/test_no_write_side_rederivation.py -q` green with the #2453 entry removed.
- Watch `tests/specify_cli/.../test_protection_config_honoring.py` (#5602 is a known local red — classify, do not chase).
- ruff/format/mypy clean; mark-status T010–T013 done.

## Risks

Message change for flat Missions (accepted); an explicit-topology protected target must still refuse.

## Reviewer Guidance

Confirm the gate entry is drained (not moved), the positive control refuses, and every printed
remedy names an option the invoked command accepts.
