# WP06 review feedback, cycle 1 (reviewer-renata)

Verdict: **changes requested**. This is a **C-007 escalation**: reachable outcomes change between the
base (fc6afbba6, the red-first commit) and HEAD (17b2f87ac). Report to the orchestrator; the
operator decides. Everything else in the WP checks out (see "Passing checks" below).

## Blocking

### 1. The new `PlacementResolutionRequired` raise pre-empts the #1598 structural refusal and changes three double-fault outcomes (C-001 / C-007)

Where: `src/specify_cli/coordination/planning_commit.py:501-510` (`_unresolved_coordination_ref`,
the `raise PlacementResolutionRequired(...)` at :510), called eagerly from
`resolve_planning_placement` (:513) at `src/specify_cli/cli/commands/implement.py:1026`, before
`_ensure_planning_artifacts_committed_git` runs its Squad-B1 (#2464) structural check.

Before: on `ActionContextError`, `_resolve_placement_ref` returned `None` and the adapter read
the meta tuple's `coordination_branch`, which never raised. The structural check ran first. A clean
tree returned early with nothing to commit.

Now: when the WP context is unresolved and `write_target(DECISION_LOG)` raises, implement stops
with `PlacementResolutionRequired`. This happens on a coord mission whose coordination branch is
torn down (merged, `CONSOLIDATED`, so `DECISION_LOG` is not short-circuited). It happens before the
structural check, before the clean-tree early return, and before the PRIMARY leg commit.

Reproduced with the reachability-suite helpers. The fixture is `build("coord")`, then
`project_status_and_mark_merged`, `delete_coordination_branch` and `duplicate_wp_prompt`, plus:

| Row | Base (fc6afbba6) | HEAD (17b2f87ac) |
|---|---|---|
| D1: clean tree | exit 1, `Could not start implementation status: Transition planned -> claimed blocked: unsatisfied dependencies`; status ` M meta.json`, ` M tasks/WP01-demo.md` | exit 1, `PlacementResolutionRequired` remedy text; status clean |
| D2: `make_dirty` | exit 1; **1 commit** (`spec.md` -> `topic`), then `CoordinationBranchDeleted` text; status `?? traces/` | exit 1; **0 commits**; `PlacementResolutionRequired`; status ` M spec.md`, `?? traces/` |
| D3: `plan.md` deleted (structural) | exit 1, **#1598 structural refusal** ("Uncommitted structural planning-artifact changes ...") | exit 1, **`PlacementResolutionRequired`**: the structural refusal is pre-empted (#2464 ordering regression) |
| D4 control: coord + duplicate WP + `plan.md` deleted (seam resolves) | structural refusal | structural refusal (identical) |

The flagged residual is therefore real and reachable. A merged mission with a torn-down
coordination branch is a normal post-consolidation state (FR-015 row 5 already pins it), and a
duplicate WP prompt is the one extra fault.

How to fix (keep B2*, change no outcome):
- Do not resolve the unresolved-context coordination ref eagerly inside
  `resolve_planning_placement`. For example, let `PlanningPlacement` carry the unresolved state,
  plus a lazily-evaluated or deferred coordination-ref query, and have the adapter ask for it only
  after the structural check. Any equivalent works if it keeps the seam owning the decision.
- That deferral alone does not restore D1 and D2. Base never raised there: it used the declared
  branch value, returned early on a clean tree, and on a dirty tree committed the PRIMARY leg before
  the COORD leg hit `CoordinationBranchDeleted`. Two acceptable directions:
  - The unresolved coordination ref comes from a non-probing, seam-level value (the declared
    coordination ref without materialization or existence probing, as the owned-checkout path in
    `resolve_placement_only` already reasons "placement never needs the coordination worktree's
    materialisation state, only the declared branch VALUE"). Then the existing arms and the
    downstream `CoordinationBranchDeleted` refusal behave as before.
  - Or the operator explicitly accepts the outcome change (C-007). That is not an implementer
    decision.
- Add FR-015 rows that pin D1, D2 and D3 at their **base** outcomes. D3 is the "structural refusal
  wins over a placement fault" double-fault pin. Run them on fc6afbba6 + the new rows and on HEAD,
  and log both.

### 2. The topology gate on the unresolved ref changes a stale-key row (C-001 / C-007)

Where: `src/specify_cli/coordination/planning_commit.py:503`
(`if not routes_through_coordination(...)`: return `None`).

Fixture: `build("lanes")`, then create the branch `kitty/mission-<slug>`,
`set_meta(coordination_branch="kitty/mission-<slug>")` (a stale or inconsistent key on a
non-coord topology), `duplicate_wp_prompt` and `make_dirty`.

| | Base | HEAD |
|---|---|---|
| D5 | exit 1; **1 commit** (`spec.md` -> `topic`, arm (c) partition); then `Failed to commit planning artifacts to kitty/mission-<slug>`; status `?? traces/` | exit 1; **0 commits**; arm (a) with the **legacy console line** (`legacy path -- mission has no coordination_branch`); `Failed to commit planning artifacts to topic: ...`; status ` M spec.md`, `?? traces/` |

R-1's 64-state matrix did not include this row: the declared key is present, but the stored
topology does not route through coordination. Either:
- pin it at the base outcome and make the unresolved arm selection reproduce it; or
- escalate it with blocking finding 1 for an operator decision.

Do not silently accept it.

## Passing checks (no action needed)

- FR-015 committed suite: base fc6afbba6 has 18 behavioural rows passing and 8 new-API unit tests
  failing (red-first as claimed). HEAD has 26/26 passing. The committed rows are identical.
- Planted break (`coordination_ref=None` in the unresolved branch): `test_duplicate_wp_on_a_coord_mission_partitions_then_refuses` goes red. Reverted.
- The characterization suite is unedited (`git diff 8cbe74f94` is empty) and green.
- Targeted set: 410 passed, 1 failed (#5699 only, `_commit_message.py`). The set is
  characterization, commit_recipes, no_write_side_rederivation, commit_router_layering,
  checkout_identity, partition_call_shape, 5113, INV-7, test_planning_commit, 2993, writeside,
  precondition_ref_unification, test_implement_command, lane_base_honoring,
  bookkeeping_identifiers, implement_cores, test_implement and placement_routing.
- ruff check and format (with `--force-exclude`) are clean, C901 is clean, and `mypy --strict` on
  `planning_commit.py` and `implement_planning_commit.py` is clean.
- Counter: 111 total, matching the report.
- FR-018: one remedy definition in `src/`. SC-004: no destination is derived from meta (the
  boolean predicate only). The deleted helpers have no callers. The `_SEAM_FOLD_CALLEES`
  removal is a tightening. `coordination/planning_commit.py` is covered by
  `test_commit_router_layering.py`.
- The INV-7 intent is kept. The 5113 docstring names `WORK_PACKAGE_UNRESOLVED`. Arm bodies are
  unchanged apart from the keys, and the raise uses the byte-identical remedy text.
- Commit trailers are correct, with no model identifier.
