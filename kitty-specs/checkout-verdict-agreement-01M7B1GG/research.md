# Grounding note: one checkout verdict for the planning commands

Read-only grounding at origin/main `1fb3b55f` (2026-11-13), committed before the spec.
Scope agreed with the orchestrator: Mission covers #7594 (slice 1) and #7633 (slice 2);
only slice 1 is delivered now. Slice 2 waits for the operator ruling Q8 on #7633 shape (b).

## Reproduction (live, real CLI)

A default Mission (`agent mission create` without `--topology`), standing on unprotected
`work`, three code lanes, run through the editable `spec-kitty` of this checkout:

| phase | invoking checkout (HEAD) | setup-plan `branch_matches_target` | check-prerequisites `branch_matches_target` |
|---|---|---|---|
| before finalize | root (topic) | true (target shown as the topic) | false (expects `work`) |
| after finalize settled `lanes_with_coord` | root (`work`) | false | true |
| after finalize | coord worktree (topic) | true | true, but it reads the root's HEAD (`work`) |

This matches both phases reported in #7594. The red test is
`tests/specify_cli/cli/commands/agent/test_planning_checkout_verdict.py`. Its two
settlement cases fail on origin/main, and the explicit-topology control passes.

## Root cause

The two commands compare different operands:

- `mission_setup_plan.py:366-397` `_resolve_branch_match_operands` compares the
  **invoking** checkout's HEAD with `read_minted_mission_branch(plan_read_dir)`, falling
  back to `meta.target_branch` (#5100). Its display `target_branch` comes from
  `_show_branch_context` (`mission_setup_plan.py:1301`), which returns the **primary**
  checkout's current branch, not the landing target.
- `mission_check_prerequisites.py:739-748` compares the **primary** checkout's HEAD
  (`get_current_branch(repo_root)` after `locate_project_root`) with `meta.target_branch`.
  It passes `expected_checkout_branch` only for an owned checkout (#5877).

Neither command asks the placement seam. The seam already answers the question:
`placement_seam(repo_root, slug).write_target(<PRIMARY kind>).ref` is the topic branch
for a default Mission before landing, also after settlement
(`resolution.py:1087 default_mission_primary_ref`), and the minted branch for a protected
explicit `single_branch` Mission (`single_branch_write_ref`). Everything else gets the
target branch. Probe results: default before and after settlement → topic; explicit
protected single_branch → minted; explicit `lanes_with_coord` and unprotected
`single_branch` → target.

## Invariants that must survive

- **Seam is the one placement authority** (CLAUDE.md Execution Workspace Strategy; ADR
  `2026-11-06-3` create-time topology; #7615 / #7546 "one checkout authority"). The
  verdict consumes `write_target`; it does not re-derive placement (DIRECTIVE_044, C-001).
- **FR-006 / #3124:** the verdict reads the **invoking** checkout's HEAD. A lane worktree
  on a divergent branch reports false (`test_setup_plan_branch_match.py`).
- **#3786:** the invocation identity is resolved once at the command entry point.
- **#5100 FR-007:** a protected mint expects the minted branch. `target_branch`,
  `planning_base_branch` and `merge_target_branch` stay the landing target.
- **#5877 / owned checkouts (FR-005 of owned-checkout-lifecycle-authority):** owned runs
  expect `owned.write_branch`; unchanged.
- **Unreadable meta degrades to a silent match**, never a spurious disagreement (#3124).
- **Display fields:** `target_branch` is the landing target from `meta.json` (#7594
  expected behaviour). Commit routing does **not** use the display value. setup-plan's
  `_target_branch` argument to `commit_for_mission` is left unchanged in this slice
  (locality).

## Architectural gates touching these files

Each is kept green honestly, with no allowlist growth:

- `test_no_write_side_rederivation.py`: whole-tree AST scan for a `CommitTarget` /
  `safe_commit` ref built from a checkout. Calling `write_target(kind).ref` is the
  sanctioned form, and no `CommitTarget` is constructed.
- `test_mission_resolver_walker_gate.py` (lists `mission_check_prerequisites.py`):
  no new walker is added.
- `_load_meta_census.py`: counts `load_meta*` calls per (file, function). Removing
  `read_minted_mission_branch` callers must keep the census consistent. Run it.
- `test_status_read_single_door.py`, `test_coord_read_residuals_closeout.py`,
  `test_commit_recipe_strings.py`: list these files. Re-run them.
- `test_layer_rules.py`: `specify_cli → mission_runtime` is the allowed direction.
- `test_no_dead_symbols.py`: if `read_minted_mission_branch` loses its last caller, it is
  deleted, not left dead.
- `test_no_legacy_terminology.py`: for any operator prose touched.

## Test seams and cost

- `tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py`:
  `make_default_mission` / `run_finalize` give real Missions (about 40 s per settled case).
- Existing pins: `test_setup_plan_branch_match.py` (FR-006, hand-seeded meta),
  `test_mission_check_prerequisites.py`, `test_mission_branch_context.py`,
  `test_setup_plan_read_surface.py`, `test_mission_setup_plan_phases.py`,
  `tests/fixtures/setup_plan_pre_mission_replay.py` (patches
  `_resolve_branch_match_operands`). Owned pins live under
  `tests/specify_cli/cli/commands/` (`*owned*`).

## 90-day churn (origin/main)

- `mission_setup_plan.py`: 27 commits.
- `mission_check_prerequisites.py`: 19 commits.
- `mission_branch_context.py`: 7 commits.

Last touches: #3933 (setup-plan status commits, 2026-11-11) and the #5100 minted-branch
report (2026-09-30). No open PR touches these files.

## Similar-surfaces squad (dispositions)

| surface | compares | disposition |
|---|---|---|
| check-prerequisites `mission_check_prerequisites.py:739-748` | primary HEAD vs meta target | **in scope** |
| setup-plan match `mission_setup_plan.py:366-397` | invoking HEAD vs minted-or-target | **in scope** |
| setup-plan display target `mission_setup_plan.py:1301` via `_show_branch_context` | primary HEAD reported as target | **in scope** (display only) |
| `mission_create.py:763-771` | minted branch by construction | file-and-link (create path, agrees today) |
| banner helpers `tasks_shared.py:179-212`, `workflow.py:1128-1170` | primary HEAD vs meta target, spurious banner | file-and-link (wider than planning) |
| owned matching `core/owned_mission.py:361-387` | HEAD vs `expected_write_branch` | no action (owned only) |
| landing/write checks `lanes/implement_support.py:290`, `lanes/single_branch_landing.py:206`, `consolidation/preflight.py:309`, `acceptance/__init__.py:2340` | write and landing refs | file-and-link (landing-time, not the planning verdict) |
| `branch-context` command | no Mission | no action |
| already on the seam: `implement_planning_commit.py:554`, `tasks_parsing_validation.py:730` | seam | template |

## Tracked-issues squad (dispositions)

- **Closes:** #7594.
- **Refs:** #7633 (slice 2, Q8 pending), #7615 / #7546 (seam authority), #5877, #5100,
  #4005, #3124, #1878.
- **Unrelated:** #7589 (review-claim empty changeset), #7588 (move-task assignee),
  #7632 (protected `lanes` admission).
- **Duplicates:** none. No open issue or PR covers this fix.
- **Prior attempt (unbacked):** a Mission `checkout-verdicts-01M7AJY6` is referenced on
  #7633, but no branch, PR, commit or `kitty-specs/` directory of it exists. The operator
  confirmed on 2026-11-13 that the reference is unbacked, so there was nothing to resume.
- **Q8 ruling (2026-11-13, relayed):** for #7633 shape (b), where the branch holder has no
  Mission directory, a coordination-less status commit refuses with a named code (option
  a), matching the read door. Slice 2 is left for a later dispatch.
- **Known residual from that attempt (#7633 comment):** a settled Mission whose
  coordination worktree was removed. Under this design the verdict compares branches
  (`write_target(...).ref`) rather than checkouts (`write_dir(...).surface_root`), so that
  shape reports the honest `false`.
