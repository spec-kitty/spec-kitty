---
work_package_id: WP02
title: Door finds owned coordination Missions; ADR amendment
dependencies: []
requirement_refs:
- C-001
- C-002
- FR-007
- FR-012
planning_base_branch: refactor/7310-status-read-door-s5
merge_target_branch: refactor/7310-status-read-door-s5
branch_strategy: Planning artifacts for this mission were generated on refactor/7310-status-read-door-s5. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into refactor/7310-status-read-door-s5 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-runtime-status-read-door-01M73HHB
base_commit: 083ee478e47c45e55428f071e4c37096e4878af9
created_at: '2026-11-11T05:20:16.228587+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Door
history:
- at: '2026-11-11T05:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/read_surface.py
create_intent:
- tests/status/test_read_surface_owned_coordination.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/read_surface.py
- tests/status/test_read_surface_owned_coordination.py
- docs/adr/4.x/2026-11-06-2-one-status-read-contract.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Door finds owned coordination Missions; ADR amendment

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Make the status read door correct for **owned checkouts of coordination Missions**, and record the operator's DM-1 split in the ADR.

Today `resolve_status_read(repo_root, mission, owned=owned)` (`src/specify_cli/status/read_surface.py:180-199`) short-circuits only for owned non-coordination topologies. For a coordination topology it calls `decide_status_read(owned.repository_root, mission)`. That locates the Mission and reads `meta.json` in the **repository root checkout's** `kitty-specs/`, not in `owned.mission_dir`, so a coordination Mission that exists only in the owned checkout fails (`FileNotFoundError` / `StatusReadPathNotFound`). Its landed check and pre-seed fallback also anchor on the repository root.

Done when:
- An owned coordination Mission that exists only in the owned checkout resolves through `resolve_status_read(owned=)` (red-first, FR-007).
- For an owned coordination Mission, the door takes the Mission directory, `meta.json`, the landed check and the pre-seed fallback from `owned.mission_dir`. It still probes coordination state (materialized / empty / unmaterialized / deleted) under `owned.repository_root`, where the coordination worktree lives.
- Non-owned behaviour is byte-identical (the existing door suites pass unchanged).
- ADR `2026-11-06-2` carries an amendment recording DM-1 (FR-012).

## Context & Constraints

- Spec: FR-005, FR-006, FR-007, FR-012; Decision Moment `01M73HKG7WSR4VDRFXG9JWTGM8` (DM-1).
- Plan IC-02; research R-3; data model § state table (owned columns).
- Evidence: `research/code-grounding.md` §3 (legacy owned arm vs the door, table) and `research/architecture-options.md` §0 bullet 3, §1 option (c).
- **This WP changes no `next` behaviour.** The owned arms of `runtime/next` start reading the door in WP04/WP05. Here the door becomes correct for them.
- Keep `resolve_status_read`'s signature. Thread an internal "primary anchor" (the owned Mission directory) into `decide_status_read` / `_decide` as a keyword with default `None`, so `coordination/surface_resolver.py`'s legacy projection (`resolve_status_surface_with_anchor`, which calls `decide_status_read`) is untouched.
- Charter: single canonical authority (the door is the authority; do not add a second owned resolver), ATDD red-first.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> Populated automatically by `spec-kitty agent mission finalize-tasks`. Run `spec-kitty agent action implement WP02 --agent <name> --mission runtime-status-read-door-01M73HHB`.

## Subtasks & Detailed Guidance

### Subtask T006 – Red test: owned-only coordination Mission resolves

- **Purpose**: pin FR-007 before the fix (C-002).
- **Steps**:
  1. New file `tests/status/test_read_surface_owned_coordination.py`.
  2. Build a repository with a `coord` (and parametrize `lanes_with_coord`) Mission. Use the owned-checkout fixtures from `tests/integration/test_owned_next_runtime.py` / `tests/mission_runtime/test_placement_seam_owned.py`; reuse their helpers, do not copy them. Then **remove the Mission directory from the repository root checkout**, so it exists only in the owned checkout P. The coordination branch and worktree stay under R.
  3. Assert that `resolve_status_read(R, slug, owned=owned)` returns a surface (not an exception), and that `materialize_status(surface)` shows the lanes committed on the coordination branch.
  4. Commit this test alone and confirm it is **red** on the base (record the failure text in `add-history`).
- **Files**: `tests/status/test_read_surface_owned_coordination.py` (new).

### Subtask T007 – Thread the owned anchor through the door

- **Purpose**: the fix for FR-007.
- **Steps**:
  1. In `resolve_status_read`, for an owned coordination topology, call `decide_status_read(owned.repository_root, mission, primary_dir=owned.mission_dir)`. The new keyword defaults to `None`.
  2. In `_decide` (and `_locate_mission`'s caller), when `primary_dir` is given, use it as the PRIMARY directory for `_has_landed`, `_read_meta` (meta from P), the pre-seed `WRITE_CHECKOUT` fallback (`_coord_ref_decision`: fall back to P's directory, not R's), and `_meta_unreadable_decision`. Keep the coordination probe (`_coordination_decision`: `probe_coord_state`, `coord_feature_dir`) on the repository root: the coordination worktree is registered there.
  3. `StatusReadSurface` invariants: a `WRITE_CHECKOUT` fallback path must exist (P's directory does). `repo_root` stays R, so a ref read runs in the right repository.
  4. Keep functions ≤ 15 complexity; extract a small helper if `_decide` grows.
- **Files**: `src/specify_cli/status/read_surface.py`.
- **Notes**: do not touch `normalized_status_read_root` semantics. A lane root still re-anchors to R.

### Subtask T008 – Owned coordination state tests [P]

- **Purpose**: pin each owned coordination cell (data-model owned columns).
- **Steps** (same test file), owned `coord` and `lanes_with_coord`:
  - materialized: source `coord_worktree`; the path is the coordination dir under R;
  - empty (worktree present, Mission dir removed): `coord_branch_ref`, committed lanes;
  - unmaterialized (`git worktree remove --force`): `coord_branch_ref`, committed lanes;
  - deleted coordination branch, not landed: raises `CoordinationBranchDeleted` (unchanged);
  - landed (`merged_at` in P's meta): `consolidated_target` from **P's** directory;
  - owned `single_branch` / `lanes`: unchanged (`WRITE_CHECKOUT` = `owned.mission_dir`).
- **Files**: `tests/status/test_read_surface_owned_coordination.py`.

### Subtask T009 – ADR amendment (DM-1)

- **Purpose**: FR-012; the code and its decision record agree.
- **Steps**:
  1. Append `## Amendment 2026-11-11: owned coordination checkouts, read vs dispatch` to `docs/adr/4.x/2026-11-06-2-one-status-read-contract.md`, after the 2026-11-08 amendment. Do not edit earlier sections.
  2. Content (plain, short):
     - the door locates an owned coordination Mission through the owned checkout and probes coordination state under the repository root;
     - query and progress of an owned coordination Mission read the committed coordination branch when its worktree is empty or unmaterialized (as §2 already says);
     - an **advancing dispatch** of that Mission refuses with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` (operator ruling, Decision Moment `01M73HKG7WSR4VDRFXG9JWTGM8`, Mission `runtime-status-read-door-01M73HHB`), because an agent must not be sent into a missing workspace. That refusal is a dispatch rule, not a read rule.
  3. Update the frontmatter `updated:` date if the file carries one (docs-freshness).
- **Files**: `docs/adr/4.x/2026-11-06-2-one-status-read-contract.md`.

### Subtask T010 – Run the door's suites

- **Steps**: run the commands below and record exact counts in `add-history`.

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest -q -n 4 --dist loadfile tests/status/test_read_surface_owned_coordination.py tests/status/test_read_surface_door.py tests/status/test_status_read_matrix.py tests/status/test_status_read_worktree_resolution.py tests/status/test_status_readers_cross_cwd_parity.py tests/integration/test_owned_next_runtime.py`
- `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/architectural/test_status_read_single_door.py`
- `ruff check`, `ruff format --check --force-exclude`, `mypy src/specify_cli/status/read_surface.py`

## Risks & Mitigations

- **Silent change for non-owned callers.** The keyword defaults to `None`, and the door suites must pass unchanged.
- **The legacy projection shares `decide_status_read`.** Leave its call sites without the new keyword.

## Review Guidance

- T006 was committed red before T007 (check commit order).
- No change in `src/runtime/next/` in this WP.
- The ADR amendment states the DM-1 split exactly and does not rewrite the original decision text.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
