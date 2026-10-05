---
affected_files: []
cycle_number: 2
mission_slug: frozen-started-lanes-01M444FM
reproduction_command:
reviewed_at: '2026-10-04T22:35:03Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03: pre-consolidate squad feedback (reopened after approval)

Source: the pre-consolidate adversarial squad.
- adversarial breaker (`debugger-debbie`): verdict FOLD FIRST;
- collateral reviewer (`architect-alphonso`): verdict SAFE, with LOW folds.

Reports:
- `/tmp/claude-0/-home-user-spec-kitty/5c1028d1-07a2-51c7-90ef-75a385c234de/scratchpad/precons-breaker/report.md`
- `/tmp/claude-0/-home-user-spec-kitty/5c1028d1-07a2-51c7-90ef-75a385c234de/scratchpad/precons-collateral/report.md`

The breaker's reproduction test is at
`/tmp/claude-0/-home-user-spec-kitty/5c1028d1-07a2-51c7-90ef-75a385c234de/scratchpad/precons-breaker/test_attack_coord.py::test_coord_worktree_absent[wt_removed_tips_deleted]`.

## [HIGH] Silent move when the coordination worktree is not materialized (FR-007, FR-001)

**Location:** `src/specify_cli/cli/commands/agent/mission_finalize_lanes.py:~58-64` (`_read_started_wp_ids`).

**What goes wrong.** For a `lanes_with_coord` mission whose coordination worktree is absent (fresh clone, a removed
worktree, CI), `resolve_status_surface_with_anchor` composes a path to a coordination dir that does not exist
(`coordination/surface_resolver.py:~1276-1278`). `has_event_log(read_dir)` is then False, and the preflight treats
that as "nothing started", even though the local coordination branch carries WP02's
`planned → claimed → in_progress` events.

The lane-work-tip fallback often does not rescue it:
- tips are per-clone;
- tips are cleared once every WP in a lane is done or canceled (`lanes/claim_base.py:~169-176`,
  `consolidation/phase_teardown.py:~659`).

Result: finalize exits 0 with lanes `[('lane-a', ('WP02','WP01'))]`. This is exactly #5573, through a different
evidence gap. It is also the #4959 defect class: a reader acting on the emptiness of an unmaterialized coordination
surface (`CoordinationWorktreeUnmaterialized`, `coordination/surface_resolver.py:~294`).

**Required fix (fail closed, canonical doctrine).** When a previous `lanes.json` exists and the resolved status
read dir does **not exist on disk**, do not treat it as an absent log. Refuse with `LANE_MEMBERSHIP_FROZEN` /
`status_unreadable`, and give a remedy that leads with **materializing the coordination worktree**. Reuse the
canonical guidance from `CoordinationWorktreeUnmaterialized` (its `next_step`, which branches on local vs
remote-only branch) rather than inventing text. Preferably obtain that exception from the canonical fail-closed
probe or resolver, rather than re-deriving coordination state.

Keep these cases unchanged:
- a status dir that **exists** but has no event log → "nothing history-started" (the legacy `tasks_finalize`
  case, US2 AS6);
- no previous `lanes.json` → empty frozen membership, no status read.

**Regression test:** add an end-to-end test for the breaker's scenario (`lanes_with_coord`, coordination worktree
removed, tip refs deleted, collapsing amendment) asserting a refusal with nothing written. Add a positive control:
the coordination worktree present gives a success, and WP02 keeps lane-b.

## [LOW] Surface the underlying cause in `status_unreadable`

**Location:** `mission_finalize_lanes.py:~58-66`.

`status_unreadable` currently renders only a generic message; the chained cause (an unresolvable surface, a deleted
coordination branch, a malformed `meta.json`) is not printed. Include the cause's own message and next step in the
conflict remedy or the error text, so degraded inputs keep their diagnostic (collateral finding, C-003 spirit).

## [LOW] The preflight skips its dry run when lane inputs are empty

**Location:** `mission_finalize_lanes.py:~144`.

When every remaining WP is excluded from the lane inputs, but a started WP was removed from the plan,
`started_wp_removed` only fires in the real lane write, after `_emit_tasks_started`. The #5641 restore still covers
it, but the requirement is refuse-before-first-write. When the frozen membership is non-empty, run the conflict
check even with empty lane inputs. Also verify that `compute_lanes`'s empty-graph early return runs the
removal-conflict collection (WP02 folds required collection before the early returns). If it does not, fix it
minimally, as an out-of-map edit to `lanes/compute.py` with a one-line rationale, and add a test.

## [LOW] A bare `type: ignore`

**Location:** `tests/lanes/test_frozen_lane_membership.py:~320`.

The `# type: ignore[arg-type]` has no inline rationale. Add one, or remove the ignore if it is not needed. This is
an out-of-map one-liner (WP02 file), allowed with a rationale in the commit.
