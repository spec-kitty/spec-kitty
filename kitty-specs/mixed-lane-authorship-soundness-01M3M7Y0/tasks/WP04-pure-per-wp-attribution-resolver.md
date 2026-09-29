---
work_package_id: WP04
title: Pure per-WP attribution resolver
dependencies:
- WP03
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-005
- NFR-002
planning_base_branch: issue-5046-mixed-lane-authorship
merge_target_branch: issue-5046-mixed-lane-authorship
branch_strategy: Planning artifacts for this mission were generated on issue-5046-mixed-lane-authorship. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5046-mixed-lane-authorship unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mixed-lane-authorship-soundness-01M3M7Y0
base_commit: c04d2db37ab7446a9258599f0c340a5a90aeefcf
created_at: '2026-09-28T17:18:43.663004+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
phase: Phase 3 - Gate (#5046)
history:
- at: '2026-09-28T15:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/wp_attribution.py
- tests/consolidation/test_wp_attribution.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/consolidation/wp_attribution.py
- tests/consolidation/test_wp_attribution.py
- src/specify_cli/consolidation/git_probes.py
- tests/consolidation/test_git_probes_seam.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Pure per-WP attribution resolver

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) before reading further.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. All feedback items are your TODO list.

---

## Objectives & Success Criteria

A new, deep, testable module `src/specify_cli/consolidation/wp_attribution.py` that, for one canceled WP in one mixed lane, returns either the WP's **canceled content** (unsuperseded per-path final state + pre-state) or a typed **unattributable** reason. It is the only place the window/supersession rules live; `reconciliation.py` (WP05) only wires it. Tiered rigour: this is core domain logic — exhaustive tests.

## Context & Constraints

- Plan D-2 and D-3 (steps 2–4); data-model.md (`WorkWindow`, `AttributionOutcome`, `CanceledPathState`); research R-5, R-7, R-9 (R1, R3, R5–R8), R-10 (B3, B4).
- Stamp key: `from specify_cli.status import LANE_HEAD_KEY` (facade re-export added by WP03; SR-2 forbids importing `specify_cli.status.lane_head` directly).
- Events: `from specify_cli.status import read_events` (facade; `store.py:736`): returns `StatusEvent` objects (not dicts) — tests build `StatusEvent`s; `[]` when missing; raises `StoreError` on corruption. Iterate in **append order** (never sort by `at`; reducer-duality caveat in CLAUDE.md).
- Git: reuse `src/specify_cli/consolidation/git_probes.py` (owned by this WP) — `first_parent_commits_in_range`, `changed_paths_of`, `blob_id_at`, `GitProbeError`, and `sha_reachable_from` (`:335`, wraps `merge-base --is-ancestor`; returns False on git error, which lands in the fail-closed `stamp_not_ancestor_of_lane_tip` path — acceptable). **Add two new probes** with focused tests in `tests/consolidation/test_git_probes_seam.py`: (1) an absence-aware state reader `path_state_at(repo, ref, path) -> str | None` (blob sha, or `None` when the path is absent at `ref`; any other git failure raises `GitProbeError`) — `blob_id_at` raises for absence and failure alike and `_final_authored_walk` (`reconciliation.py:1255-1258`) treats any error as deletion, which would be fail-open here; (2) `is_merge_commit(repo, sha) -> bool` (parent count ≥ 2, e.g. `rev-list --parents -n1`).
- Bookkeeping predicate: take `is_bookkeeping: Callable[[str], bool]`. `MergeOutcomeVerifier._is_bookkeeping_path(path, claim)` is a staticmethod needing `claim.mission_slug`/`claim.planning_prefix`; WP05 extracts a module-level `(path, mission_slug, planning_prefix)` function and binds it with `functools.partial` — do not duplicate the denylist here.
- **Never** use the tolerant `_lane_first_parent_spine` (`reconciliation.py:1191`), which swallows `GitProbeError` into `[]` (→ vacuous PASS, B3).

## Branch Strategy

- **Planning base / merge target**: `issue-5046-mixed-lane-authorship`. Workspace from `spec-kitty agent action implement WP04 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T016 – Window reconstruction

- Input: the lane's WP ids, all events (append order). For each WP, walk its transitions:
  - **implementation states** = `{claimed, in_progress, blocked}`; **review states** = `{for_review, in_review}`.
  - A window opens on a transition INTO a state of a class from outside that class, with `open_head = event.policy_metadata.get(LANE_HEAD_KEY)`; it closes on the transition OUT of the class with `close_head` from that event. `claimed→in_progress` stays in the same implementation window (the batch shares one head).
  - `entered_implementation(wp)` = any transition into `claimed`/`in_progress`.
- Output: `list[WorkWindow(wp_id, kind, open_head, close_head)]` in order.
- A window whose open or close event lacks a stamp → mark the window unstamped (feeds `no_stamp`); a window with no closing event → `open_window`.

### Subtask T017 – Commit resolution

- Lane spine: `first_parent_commits_in_range(repo, coord_base_ref, lane_branch)` (newest-first). `GitProbeError` → `spine_unreadable`.
- **Stamp validity (R8):** a stamp is valid iff it equals the lane tip or `is_ancestor(stamp, lane_tip)`. Never test membership of the `coord_base..lane` range — the first WP's open stamp is the lane fork point, outside that range. Invalid → `stamp_not_ancestor_of_lane_tip`.
- Window commits = `first_parent_commits_in_range(repo, open_head, close_head)` ∩ set(spine), **non-merge only** (a commit with ≥ 2 parents never attributes, R3/B4 — it is a workflow merge such as the lane sync `lanes/lifecycle_sync.py` or coord auto-rebase `workflow_executor.py:887,1764`).

### Subtask T018 – Contested / review rules

- A commit in the canceled WP's **implementation** window that is also in another WP's implementation window → `contested_commit` (R7; message hint "lane WPs ran concurrently").
- A commit in the canceled WP's **review** window is attributed to it only if no other WP of the lane has an implementation or review window containing it (R5); otherwise → `contested_commit`.
- Commits in no window of the canceled WP are not its commits (they keep today's treatment).

### Subtask T019 – Canceled content (single spine walk)

- One newest→oldest walk over the lane spine (NFR-001 — do not walk twice): for each commit, for each changed path (skip merge commits and `is_bookkeeping(path)`), record the **newest non-merge toucher** (first seen). For paths touched by the canceled commit set C, also record the canceled WP's **oldest** commit touching the path (last seen among C).
- For each path P with newest toucher ∈ C:
  - `canceled_state` = `path_state_at(repo, newest_toucher, P)` (new probe; `None` = deleted).
  - `pre_state` = `path_state_at(repo, <first parent of the canceled WP's oldest commit touching P>, P)` (R1 — not `coord_base_ref`).
  - `pre_state_by_survivor` = some non-canceled, non-merge spine commit older than that oldest canceled touch touched P (so the pre-state was produced on the lane by a surviving WP, not inherited from the base) — WP05 uses it to tell "approved work undone" (FAIL) from "target already had it" (no finding).
  - drop P if `canceled_state == pre_state` (net-zero self-revert).
  - else emit `CanceledPathState(wp_id, lane_id, path, canceled_state, pre_state, pre_state_by_survivor)`.

### Subtask T020 – Outcome type and fail-closed errors

- `AttributionOutcome` = `Attributed(commits: frozenset[str], canceled_content: frozenset[CanceledPathState])` | `Unattributable(reason: UnattributableReason, detail: str)`; `UnattributableReason` is a `StrEnum` with `no_stamp`, `open_window`, `stamp_not_ancestor_of_lane_tip`, `contested_commit`, `events_unreadable`, `spine_unreadable`.
- Public entry point (suggested): `resolve_canceled_wp(repo_root, *, events, lane_id, lane_wp_ids, canceled_wp_id, lane_branch, coord_base_ref, is_bookkeeping) -> AttributionOutcome` — pure except for git reads; `events` passed in (WP05 reads them once and catches `StoreError` → `events_unreadable`).
- A canceled WP that never entered implementation should not be passed in (WP05 filters); if it is, return `Attributed(frozenset(), frozenset())`.
- `detail` is operator-facing (NFR-003): name the lane, the WP, and what is missing, e.g. `"WP02 in lane-a entered implementation but its lifecycle events carry no commit attribution (missions created before this change, or a transition made outside the governed workflow)"`.
- Declare `__all__` with only names WP05 uses (dead-symbol gate).

### Subtask T021 – Tests (git-backed)

`tests/consolidation/test_wp_attribution.py`, building throwaway repos in `tmp_path` with real commits and synthetic event dicts (use the canonical event shape; stamps = real SHAs). Cover at least:
- windows: claimed+in_progress same head; rework round (`in_review→in_progress`); `blocked` counted; missing stamp; open window.
- stamp validity: fork-point open stamp of the first WP is valid (R8); a rewritten-history stamp is invalid.
- merges: a merge commit inside the canceled window is not attributed and does not supersede.
- contested: overlapping implementation windows; review-window commit with a queued sibling in review (R5) → contested; uncontested review fix-up → attributed.
- content: add, modify, delete unsuperseded; superseded by a later survivor commit (rewrite and delete); self-revert dropped; survivor-undone shapes (R1: survivor adds → canceled deletes ⇒ entry with `canceled_state=None, pre_state=<blob>`; survivor v1 → canceled v0 ⇒ entry); bookkeeping path ignored.
- errors: `GitProbeError` on the spine → `spine_unreadable`.
Use realistic 40-hex SHAs and realistic paths (`src/pkg/...`).

## Test Strategy

```bash
uv run --frozen pytest tests/consolidation/test_wp_attribution.py tests/consolidation/test_git_probes_seam.py -q
uv run --frozen pytest tests/architectural/test_status_module_boundary.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_merge_pipeline_ratchets.py tests/architectural/test_no_read_side_bypass.py -q
uv run --frozen ruff check src/specify_cli/consolidation/wp_attribution.py tests/consolidation/test_wp_attribution.py && uv run --frozen ruff format --check src/specify_cli/consolidation/wp_attribution.py tests/consolidation/test_wp_attribution.py
uv run --frozen mypy src/specify_cli/consolidation/wp_attribution.py
```

## Risks & Mitigations

- Complexity: split into `_windows`, `_window_commits`, `_resolve_contested`, `_canceled_content_walk`; each ≤ 15.
- Path-absence vs probe error ambiguity in `blob_id_at` (T019) — decide explicitly and test both.

## Review Guidance

- Verify each R1/R3/R5/R7/R8 rule has a named test.
- Verify no tolerant spine helper is used and every git error maps to `Unattributable`.
- Verify a single spine walk computes both newest toucher and oldest canceled toucher.

## Activity Log

- 2026-09-28T15:40:00Z – system – Prompt created.
