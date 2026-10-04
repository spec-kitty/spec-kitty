---
work_package_id: WP03
title: Stale-lane rules
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- FR-009
- C-004
- SC-005
planning_base_branch: issue-5457-upgrade-project-global-state
merge_target_branch: issue-5457-upgrade-project-global-state
branch_strategy: Planning artifacts for this mission were generated on issue-5457-upgrade-project-global-state. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5457-upgrade-project-global-state unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-project-global-state-01M44538
base_commit: b33766f3b95528e03a4c0a1df73d9fcd159bcc60
created_at: '2026-10-04T20:30:55.731335+00:00'
subtasks:
- T009
- T010
- T011
- T012
phase: 'Phase 3 - Recovery: classification'
history:
- at: '2026-10-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/stale_check.py
create_intent:
- tests/lanes/test_stale_check_primary_owned.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/stale_check.py
- tests/lanes/test_stale_check.py
- tests/lanes/test_stale_check_primary_owned.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Stale-lane rules

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`):
`spec-kitty agent profile show python-pedro` and `spec-kitty charter context --action implement --json`.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Every feedback item is a TODO.

---

## Objectives & Success Criteria

`check_lane_staleness` (`src/specify_cli/lanes/stale_check.py:30ff`), which `consolidate` calls before merging each lane, stops counting two kinds of overlap:

1. **Primary-owned bookkeeping** (FR-005): an overlap on a path where `specify_cli.state.contract.is_primary_owned_path(path)` (WP01) is True.
2. **Content-identical overlaps** (FR-006), on any path: the overlapping path's tree entry (mode and object id, or absent) is identical at the lane tip and at the mission-branch tip. Equal end states make a trivial 3-way merge with no semantic difference.

Every other overlap stays stale, with **byte-identical** `stale_files` ordering, `is_stale` and `remediation` text (FR-009, C-004). The remedy text is **not** changed by this mission (FR-010 / D6 defers it).

Spec refs: FR-005, FR-006, FR-009, C-002, C-004, C-008; Story 4 AS-2, Story 5 AS-1. Read `plan.md` (IC-03), `research.md` D5, and `research/squad-dispositions.md` #3 and #15.

## Context & Constraints

- **No module-level filename list** in `stale_check.py`. `lanes/` modules are scanned by `tests/architectural/test_exemption_registry_ratchet.py`. Call `is_primary_owned_path` and never restate the literal.
- **Content identity must use git tree entries**: `git ls-tree <ref> -- <paths>`, comparing mode **and** object id. A mode change or a deletion on one side is not identical. Both sides absent counts as identical; that is impossible after an overlap, but handle it deterministically.
- **Performance**: run the ls-tree probes only when `overlap` is non-empty. Use at most one `ls-tree` per ref, passing all overlap paths in one call. Reuse `specify_cli.core.vcs.git` helpers if one exists; otherwise add a small private helper here with `capture_output`, and treat a failed probe as "not identical" (fail safe: keep the path stale).
- Keep `check_lane_staleness` at complexity ≤ 15. Extract `_filter_benign_overlaps(...)` (or similar) and test it.

## Branch Strategy

- **Strategy**: lanes · **Planning base branch**: `issue-5457-upgrade-project-global-state` · **Merge target branch**: `issue-5457-upgrade-project-global-state`.

## Subtasks & Detailed Guidance

### Subtask T009 – Red test

- **Purpose**: pin FR-005 and FR-006 through the production function that `consolidate` calls (`consolidate_lane_into_mission` → `check_lane_staleness`).
- **Steps**:
  1. In `tests/lanes/test_stale_check_primary_owned.py`, build with WP01's `commit_broken_upgrade_state`, or with direct git in the shape of grounding Appendix A:
     - a mission branch that has advanced with lane-a's content plus its own `.kittify/metadata.yaml` and the `.gitattributes` line;
     - lane-b, which committed a **different** `metadata.yaml` and the **identical** `.gitattributes` line on top of its own work.
  2. Call `check_lane_staleness(lane, lane_branch, mission_branch, repo_root)`. Today it returns `is_stale=True` with `['.gitattributes', '.kittify/metadata.yaml']` (that is the Path A refusal).
  3. Assert `is_stale is False` after the fix. Commit the red test alone.

### Subtask T010 – Primary-owned exclusion

- Filter `overlap` with `is_primary_owned_path`. Add a unit test where only `metadata.yaml` overlaps.

### Subtask T011 – Content-identical exclusion

- For the remaining overlap paths, compare `ls-tree` entries at `lane_branch` and `mission_branch`, and drop equal entries. Add unit tests for:
  - an identical addition (dropped);
  - different content (kept);
  - the same content with a mode change, `100644` vs `100755` (kept);
  - a deletion on one side and a modification on the other (kept);
  - a probe failure, simulated with a bogus ref (kept, fail safe).

### Subtask T012 – Controls and byte-identical text [P]

- **Story 5 AS-1 control on the same fixture builder**: when lane-b's `.gitattributes` addition differs from the mission branch's, `is_stale` is True, `stale_files == ['.gitattributes']`, and `remediation` is byte-identical to `_stale_remediation(...)` today.
- Re-run the existing `tests/lanes/test_stale_check.py` unchanged; it must stay green. Boy-scout: if any existing test there only asserts truthiness, tighten it to the exact `stale_files`. That stays within this file only.
- **Half-by-half proof**: temporarily revert T010, then T011, and confirm T009's fixture goes red each time. Record the outcome in the Activity Log (the fixture needs both rules: `metadata.yaml` needs T010 and `.gitattributes` needs T011).

## Post-tasks squad folds (binding)

- **The dead-symbol gate goes green here** (WP01 review cycle 1): WP01 introduced `is_primary_owned_path` with no production caller, so `tests/architectural/test_no_dead_symbols.py` is expected red on the WP01 lane. WP03's production call in `stale_check.py` must turn it green. Run it and record the result; it is a WP03 acceptance item.
- **Never run raw `git ls-tree` / `git ls-files` in `lanes/`.** `tests/architectural/test_git_path_listing_owner.py` refuses any such argv outside `src/kernel/git/`, and its allowlist must stay empty. Use `kernel.git.listing.tree_entries(cwd, ref, paths)` / `tree_entry(...)` (they return `TreeEntry`, with mode and object). Compare `(mode, object)`, and treat `None` on both sides as identical. Add `test_git_path_listing_owner.py` to the gates you run.
- **Production-path proof** lives in WP04 (AS-2 through the CLI, with revert legs for T010 and T011). Here, prove the rules through `check_lane_staleness` (which `consolidate` calls) **and** through `consolidate_lane_into_mission` for the Story 5 AS-1 control (a different `.gitattributes` content is still refused with byte-identical text).
- **Gate-file rights**: if a named architectural gate goes red because of a *legitimate* change, you may edit **only** that gate's own pin or allowlist entry. Name the file in the commit body with a one-line justification, and the reviewer re-checks it. Never touch `dead_symbol_allowlist.yaml` or `_git_path_listing_census.py`, and never add a new allowlist (C-007).

## Test Strategy

- `uv run --frozen pytest tests/lanes/test_stale_check.py tests/lanes/test_stale_check_primary_owned.py tests/lanes/test_merge.py -q`
- Gate: `uv run --frozen pytest tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_no_dead_symbols.py -q`
- Run `ruff check`, `ruff format --check --force-exclude` and `mypy` on `stale_check.py` and the tests. `make test-fast`.

## Risks & Mitigations

- **A false "identical" verdict**: compare the full tree entry, never a content hash of the working tree.
- **Over-broad exemption**: the primary-owned set is exactly what WP01 declares (C-008).

## Review Guidance

- Red before green, through `check_lane_staleness`.
- The controls show that genuine overlaps still refuse with the identical text.
- No literal path in `stale_check.py`.

## Activity Log

- 2026-10-04T19:40:00Z – system – Prompt generated via /spec-kitty.tasks
