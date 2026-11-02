# Research: lane self-heal public seam (#6898)

Recorded during the `discovery` step for `lane-self-heal-public-seam-01M6EJR6`.

## Decisions

### D1 — One seam, inside the allocator, with the policy as a required parameter

**Decision.** Add `adopt_lane_ancestry(repo_root, worktree_path, mission_slug, lane,
lanes_manifest, *, clean_worktree_policy: Literal["refuse-dirty", "allow-dirty"], target_tip=None)`
to `src/specify_cli/lanes/worktree_allocator.py`. It validates under the policy, captures the
planning target tip when the caller supplies none, then runs the two merges in the allocator's
existing order (recorded planning commit → approved dependency lane tips).

**Rationale.** The issue names the shape of the clean fix: "one public seam … with the
clean-worktree policy as an explicit, documented parameter (self-heal is allowed to be less
strict, but the *decision* belongs to the allocator)". A boolean would do, but a two-valued
`Literal` names the policy at every call site (`refuse-dirty` / `allow-dirty`), which is what a
reviewer needs to check; and making it keyword-only and default-less means a new call site
cannot silently inherit the permissive branch.

**Evidence.** `git grep -n "_merge_recorded_planning_commit\|_merge_dependency_lane_tips" src/`:
the two helpers are called at four sites — REUSE (`worktree_allocator.py:1123`), CRASH_RECOVERY
(`:1189`), FRESH (`:1319`), and `implement_support.py:684` — always in that order, with the
recorded pin first. `_validate_worktree_clean` is called at `:1119` (REUSE) and `:1177`
(CRASH_RECOVERY) in the allocator and at `implement_support.py` for the planning lane only.

### D2 — The seam captures the target tip; the caller may still pass one

**Decision.** `target_tip=None` ⇒ the seam calls `capture_branch_tip(repo_root,
lanes_manifest.target_branch)`. The allocator's route sites pass the tip they already captured
once per `allocate_lane_worktree` call.

**Rationale.** The #4827/C-006 invariant is "never a lane worktree HEAD as the target tip" and
today the caller (`implement_support.py:683`) re-derives it by hand. Letting the seam own the
derivation makes the invariant structural; the optional parameter keeps one capture per
allocation (NFR-001) instead of adding a second `git rev-parse`.

### D3 — Behaviour is frozen; only the authority moves

**Decision.** Code lanes keep `allow-dirty`; the planning lane keeps `refuse-dirty` plus its
external `assert_not_protected_branch` guard, its approved-tip filtering
(`replace(lane, depends_on_lanes=…)`) and its `workspace_path.exists()` short-circuit.

**Rationale.** The docstring of `reenter_lane_self_heal` records why the code lane must not
inherit the allocator's clean check: "re-entering self-heal for the SAME in-flight WP must not
hard-fail just because the agent has legitimate uncommitted work-in-progress, and git's own
merge machinery already refuses a merge that would conflict with dirty local changes". The
planning lane, by contrast, reconciles the *shared* repository-root checkout, where a clean and
unprotected tree is required before a merge can mutate it.

### D4 — The gate polices the adoption trio, not every private helper

**Decision.** The new architectural gate flags an import of `_merge_recorded_planning_commit`,
`_merge_dependency_lane_tips` or `_validate_worktree_clean` from any module in `src/` other than
`worktree_allocator.py`, plus a floor on the seam's own call sites. It does not attempt a
repo-wide "no private import of this module" rule.

**Rationale.** `implement_support.py` also imports `_read_coordination_branch` (a read seam),
`checkout_occupancy.py` imports `_git_status_entries`, and `recovery.py` imports
`_recover_lane_worktree`; those are different decisions with their own (documented) reasons, and
folding them into this mission would either need a priced allowlist or a much larger refactor.
The defect class in the issue is precisely "a second entry into allocator internals standing in
for a **seam the allocator does not expose**" for the adoption step; that is what the gate
closes, and it starts empty (no allowlist).

## Evidence gathered

- `src/specify_cli/lanes/implement_support.py:645-649` — the private-name import the issue names.
- `src/specify_cli/lanes/worktree_allocator.py:1104-1130, 1170-1195, 1310-1335` — the three
  inline route bodies that the seam replaces.
- `tests/architectural/test_lane_allocation_single_seam.py` — the AST-guard precedent
  (`resolve_lane_base_or_refuse` seam, route-coverage floor, self-mutation fixtures). The new
  gate mirrors its structure so the two read the same way.
- `tests/lanes/test_planning_claim_self_heal.py` — the behavioural contract to keep green:
  approved-dependency merge into a planning root, protected-root refusal without mutation,
  dirty-root refusal without losing work.
- `tests/lanes/test_lane_tip_record_points.py:231-307` — M4: the code-lane re-entry still records
  the lane tip after the seam runs.
- `docs/adr/3.x/2026-07-29-1-lane-base-recorded-planning-commit.md` — the recorded-planning-commit
  rule the first merge implements (FR-009/#2993), unchanged by this mission.

## Open questions (resolved before tasks)

- **Q1: does removing the local `_validate_worktree_clean` call from the planning-lane branch
  change the order of refusals?** No. The seam validates before either merge, and the
  planning-lane branch reaches the seam only after `create_planning_workspace` and the ancestry
  short-circuit, so the protected-branch guard still runs first and the dirty check still runs
  before any merge.
- **Q2: does the FRESH route pay a new `git status`?** Yes — one probe on a worktree that was
  just created (always clean). Accepted for a uniform policy; recorded in the plan's Risks.
- **Q3: is `Literal` import allowed under mypy strict?** Yes, `typing.Literal`;
  `worktree_allocator.py` already imports `Literal` from `typing` (line 29).
