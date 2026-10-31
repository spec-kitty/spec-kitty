---
work_package_id: WP01
title: Report a stale lane base at fresh coord allocation
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-002
planning_base_branch: issue-6753-stale-coord-lane-base
merge_target_branch: issue-6753-stale-coord-lane-base
branch_strategy: Planning artifacts for this mission were generated on issue-6753-stale-coord-lane-base. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6753-stale-coord-lane-base unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-stale-coord-lane-base-01M67HRA
base_commit: 8d00acf689f2860f84f35eed2431e3b169ac5315
created_at: '2026-10-30T23:22:54.325760+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Make the gap visible
history:
- timestamp: '2026-10-30T23:40:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/specify_cli/lanes/test_issue_6753_stale_coord_lane_base.py
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/worktree_allocator.py
- tests/specify_cli/lanes/test_issue_6753_stale_coord_lane_base.py
role: implementer
tags: []
tracker_refs:
- '#6753'
wp_code: WP01
---

# Work Package Prompt: WP01 – Report a stale lane base at fresh coord allocation

## ⚡ Do This First: Load Agent Profile

Load your assigned agent profile with the `spk-charter-profile-load` skill, profile id
**`python-pedro`**, and adopt it for the whole work package. Then read
`kitty-specs/stale-coord-lane-base-01M67HRA/spec.md` and `plan.md`.

## Objective

A fresh code lane on a coordination-topology Mission is parented on the
coordination branch by design (`_resolve_lane_parent`, C-005/FR-006). If the target
branch advanced after the coordination branch was minted, the lane is cut behind the
target and today **nothing says so** (#6753). Make the gap visible at the single
point where a lane's parent ref is decided: probe the ref the lane is cut from
against the target tip, and when it does not contain the target tip print exactly
one `WARNING:` that names the base ref, the target branch, the missing target
commit, and the runnable remedy. Stay silent when the base is current, when the
target tip cannot be resolved, or on any route other than a fresh coord cut.

**Do not** change the topology-derived parent, do not add a refusal/`StructuredError`
route, and do not merge, rebase or fast-forward either branch (C-001, C-002, C-005).

## Context & Constraints

- **The seam**: `src/specify_cli/lanes/worktree_allocator.py` —
  `allocate_lane_worktree()`'s `if coordination_branch is not None:` (FRESH_COORD)
  arm. It already computes `decision = resolve_lane_base_or_refuse(...)` and then
  calls `_ensure_branch_exists(...)` / `_create_lane_worktree(...)`. `decision.parent_ref`
  is the ref the lane will actually be cut from (it can be an `origin/<lane-branch>`
  ref thanks to the #4969 origin-preference in `_fresh_lane_parent_ref`).
- **The target tip is already captured**: `target_tip = capture_branch_tip(repo_root,
  lanes_manifest.target_branch)` runs near the top of `allocate_lane_worktree` and is
  `None` when the branch cannot be resolved. Reuse it — do not add a second
  `rev-parse` authority (NFR-001) and do not add a second definition of "the target
  tip". If `target_tip is None`, the probe is `unknown` and prints nothing (NFR-002).
- **Output convention**: the module already reports operator-visible warnings with a
  plain `print("WARNING: ...")` (see `_merge_dependency_lane_tips`'s missing-dep
  branch). Use that, not a logger, not a new channel (C-004). Do **not** use
  `rich`/`console` — this module is CLI-agnostic and imported by the orchestrator API.
- **Probe shape**: `git merge-base --is-ancestor <target_tip> <parent_ref>` in
  `repo_root`, `capture_output=True`. Exit 0 → the base contains the target tip
  (`current`). Exit 1 → `stale`. Anything else (missing ref, git error, non-git
  fixture path) → `unknown`, print nothing.
- **Message content** (NFR-003 — all four, every emission): the base ref name, the
  target branch name, a concrete commit id that is on the target and absent from the
  base (short sha is fine), and a runnable command carrying the WP id, e.g.
  `spec-kitty agent action implement WP02 --agent <name> --base main`. Cite `(#6753)`.
- **Where to emit**: on the FRESH_COORD arm only, after `decision` is resolved and
  before the worktree is created, so the operator reads it before the creation
  output and a later creation failure cannot swallow it. One emission per
  allocation — do not print it again from any helper.
- **Hard non-goals**: legacy topology (`coordination_branch is None`), the REUSE and
  CRASH_RECOVERY arms, dependency-lane merging, and the planning (repository-root)
  lane are all out of scope and must not change behaviour or gain output
  (NFR-001 — no extra subprocess on those routes).
- Follow the repo's code rules in `CLAUDE.md`; keep the new helper private
  (`_`-prefixed), typed, and documented in the module's existing comment style.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: the silence (#6753)

Create `tests/specify_cli/lanes/test_issue_6753_stale_coord_lane_base.py`.
Reuse the fixture shape of `tests/specify_cli/lanes/test_worktree_allocator_coord.py`
(`new_topology_repo`: a tmp git repo, `kitty-specs/<slug>/meta.json` carrying
`coordination_branch`, a minted `kitty/mission-<slug>` branch, `main` as target).
Add the #6753 step: advance `main` past the coordination branch with a real commit
(the issue's "reviewed prerequisite merge"), then call
`allocate_lane_worktree(repo_root=..., mission_slug=..., wp_id="WP01", lanes_manifest=...)`
with no `base` and capture stdout with `capsys`.

Assert the warning is present and carries the four NFR-003 elements. **This test
must fail against the current tree** — run it and record the failure before writing
any production code.

### Subtask T002 – The probe

Add one private helper in `worktree_allocator.py` beside `_ensure_branch_exists`,
e.g. `_stale_base_warning(repo_root, parent_ref, target_branch, target_tip, wp_id) -> str | None`:
returns the warning text when `parent_ref` does not contain `target_tip`, else
`None`. Keep the `unknown` cases (no `target_tip`, non-zero non-1 exit, exception)
as `None`, never a raise (NFR-002). Type hints, a docstring naming #6753 and the
three states, no new imports beyond what the module already has.

### Subtask T003 – Emit it once, on the fresh coord arm

Call the helper from the FRESH_COORD arm of `allocate_lane_worktree` and
`print(...)` its text when it is not `None`, before `_create_lane_worktree`. Add a
short comment saying why this route (only a fresh cut decides a parent) and why it
only warns (C-002).

### Subtask T004 – Positive control on the same fixture

In the same test module, from the **same** fixture builder:

- a case where the coordination branch already contains the target tip → **no**
  warning (this is the control that proves the probe can observe "current");
- a case where the target branch cannot be resolved (e.g. manifest `target_branch`
  set to a name that does not exist) → **no** warning, and allocation still
  succeeds, proving the probe never blocks (NFR-002);
- a case with an explicit `--base` that already contains the target tip
  (`base="main"`) → no warning, even though the topology parent would be stale.

### Subtask T005 – Parentage ratchet

Assert on the stale fixture that the created lane branch still descends from the
coordination branch (`git merge-base --is-ancestor <coord> <lane>` exits 0) and that
the lane does **not** contain the target tip. This is FR-003: the warning must not
have changed what the lane is cut from.

### Subtask T006 – Validate

Run, and record the results:

```
uv run pytest tests/specify_cli/lanes/test_issue_6753_stale_coord_lane_base.py -q
uv run pytest tests/specify_cli/lanes tests/lanes -q
uv run ruff check src/specify_cli/lanes/worktree_allocator.py tests/specify_cli/lanes/test_issue_6753_stale_coord_lane_base.py
uv run ruff format --check src/specify_cli/lanes/worktree_allocator.py tests/specify_cli/lanes/test_issue_6753_stale_coord_lane_base.py
```

Do **not** run `make test-full` or any whole-repo heavy sweep. If an unrelated red
appears, capture the exact test id and reproduce it in a pristine `origin/main`
worktree before attributing it to this WP.

## Definition of Done

- T001's test was red before the fix and is green after (paste both outputs in the
  review hand-off).
- The warning fires on a stale fresh coord cut and is silent on current, unknown,
  legacy, reuse and crash-recovery paths.
- No new refusal route, no new CLI option, no behaviour change to lane parentage.
- `uv run pytest tests/specify_cli/lanes tests/lanes -q` green; ruff clean.
