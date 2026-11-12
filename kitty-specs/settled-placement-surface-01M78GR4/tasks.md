# Tasks: One placement surface after topology settlement

**Mission**: `settled-placement-surface-01M78GR4` · **Topology**: `single_branch` (WPs run in sequence in
the repository root checkout on `fix/7546-settled-placement-surface`)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [research/](research/)

Every WP is red-first (C-007): commit the failing test through the pre-existing entry point on the
settled fixture (`make_default_mission` + `run_finalize` from
`tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py`, `THREE_LANES`) as its
own commit, then the fix.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red: seam reports the repository root checkout as `surface_root` for a settled Mission's PRIMARY kinds | WP01 | |
| T002 | Hoist the pure "checkout containing a path" walk into `kernel.git_topology` | WP01 | |
| T003 | `_declared_primary_write_dir` returns the checkout containing its `path` | WP01 | |
| T004 | `primary_partition_checkout` delegates to `write_dir(PRIMARY_METADATA).surface_root` | WP01 | |
| T005 | Red: spec-commit of tracer / decision / baseline after settlement (both cwds) + root-only copy + status lock | WP02 | |
| T006 | `_primary_commit_root` delegates to the seam's `surface_root` | WP02 | |
| T007 | Re-anchor absent root-anchored Mission paths through `_translate_to_owning_surface`; refuse a root-only copy naming the holder | WP02 | |
| T008 | Coordination status lock engages when a non-owned group commits in the holder checkout (#7607) | WP02 | |
| T009 | `SafeCommitHeadMismatch` remedy names the worktree that holds the branch | WP02 | |
| T010 | Red: `implement WP01` and `move-task --note` from a protected root on a settled Mission; explicit-topology positive control | WP03 | |
| T011 | Protected status preflight judges `write_target(WORK_PACKAGE_TASK).ref`; drain allow-list entry #2453 | WP03 | |
| T012 | `move-task` feeds the WP file's commit ref to `_skip_target_branch_commit` | WP03 | |
| T013 | Remedy text: no `--no-auto-commit` advice where the command lacks it; name the surface | WP03 | |
| T014 | Red: baseline left untracked after settlement; banner prints `main` (#7595) | WP04 | |
| T015 | Baseline needs-commit probe and commit run in the seam's holder checkout | WP04 | |
| T016 | `resolve_target_branch` / `get_feature_target_branch` read `meta.json` through the seam; re-point bypass sanctions | WP04 | |
| T017 | Red: accept path-convention message names `.worktrees/<slug>-coord/…` (#7602) | WP05 | |
| T018 | Render artifact-tagged misses relative to the checkout that holds them | WP05 | |
| T019 | Regression: build paths keep project-relative rendering; single_branch unchanged | WP05 | |

## WP01 — One checkout authority in the seam (enabler)

**Prompt**: [tasks/WP01-seam-checkout-authority.md](tasks/WP01-seam-checkout-authority.md) · **Priority**: P1 · **Depends on**: none

Goal: `PlacementSeam.write_dir(kind).surface_root` contains `write_dir(kind).path` for every kind.
Independent test: on the settled fixture, `write_dir(SPEC).surface_root` is the coordination worktree;
on a `single_branch` Mission it is the repository root checkout.

T001 Red: seam surface_root for settled PRIMARY kinds (WP01)
T002 Hoist checkout walk into kernel (WP01)
T003 Fix `_declared_primary_write_dir` surface_root (WP01)
T004 `primary_partition_checkout` delegates to the seam (WP01)

Risks: `path` must stay byte-identical to `read_dir(kind)`; owned checkouts keep `owned_root`.

## WP02 — Commit router resolves the holder through the seam (#7551, #7607)

**Prompt**: [tasks/WP02-commit-router-holder.md](tasks/WP02-commit-router-holder.md) · **Priority**: P1 · **Depends on**: WP01

Goal: `spec-commit` lands a settled Mission's tracer, decision and baseline files on the topic branch
from either checkout; a root-only copy refuses naming the holder; status files commit under the lock.

T005 Red: settled spec-commit scenarios (WP02)
T006 `_primary_commit_root` → seam (WP02)
T007 Re-anchor / refuse root-only copy (WP02)
T008 Status lock on the holder checkout (WP02)
T009 HEAD-mismatch remedy names the holder (WP02)

Risks: keep the ref-inequality `use_coord` rule; never copy; refusal codes unchanged.

## WP03 — Protected-branch preflights judge the write surface (#7601)

**Prompt**: [tasks/WP03-protected-preflights.md](tasks/WP03-protected-preflights.md) · **Priority**: P1 · **Depends on**: none

Goal: `agent action implement` and `move-task --note` run from a root checkout on protected `main` for
a settled Mission; an explicit `lanes_with_coord` Mission targeting protected `main` still refuses.

T010 Red: protected-root implement / move-task --note + positive control (WP03)
T011 Preflight judges `write_target(WORK_PACKAGE_TASK).ref`; drain #2453 (WP03)
T012 move-task skip gate fed the WP file's ref (WP03)
T013 Remedy text (WP03)

Risks: accepted message change for flat Missions (decision `01M78GS4H8AAJW5Y4ATZ3TES6B`).

## WP04 — Baseline commit and target banner read through the seam (#7551 baseline, #7595)

**Prompt**: [tasks/WP04-baseline-and-target-banner.md](tasks/WP04-baseline-and-target-banner.md) · **Priority**: P1 · **Depends on**: WP01

T014 Red: baseline untracked; banner `main` (WP04)
T015 Baseline at the holder checkout (WP04)
T016 Target helpers through the seam (WP04)

Risks: 24 helper callers; import layering in `core/paths.py`.

## WP05 — Path-convention message frame (#7602)

**Prompt**: [tasks/WP05-path-convention-frame.md](tasks/WP05-path-convention-frame.md) · **Priority**: P2 · **Depends on**: none

T017 Red: coord path in the message (WP05)
T018 Render relative to the holding checkout (WP05)
T019 Regression for build paths and single_branch (WP05)

## Sequencing

`single_branch`: WP01 → WP02 → WP03 → WP04 → WP05 in order. MVP: WP01 + WP02 (closes the #7551 core).
