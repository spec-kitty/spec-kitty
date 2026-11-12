---
type: reference
updated: 2026-11-12
---

# Code grounding: one placement surface after topology settlement (#7546)

Base: `origin/main` @ `89217ac8` (spec-kitty-cli 4.0.0rc9). Read-only research squad: code grounding,
evidence mining, foldable-issue discovery, plus an adversarial second opinion that re-ran every claim
as a live probe. Live reproduction through the real CLI (subprocess `spec-kitty …`) on the real
`make_default_mission` + `run_finalize` fixture
(`tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py`), 3 code WPs, root on
protected `main` and on unprotected `dev`.

## 1. What settlement produces (the state every symptom starts from)

`lanes/topology_settlement.py` (`settle_topology`, :546; plan steps :516-523) for `lanes_with_coord`:

1. commits the Mission dir on the topic branch;
2. switches the repository root checkout back to `create_return_branch`;
3. materializes `.worktrees/<slug>-coord` **on the topic branch**;
4. re-stamps `meta.json` in the coordination copy only
   (`mission_metadata.restamp_topic_branch_as_coordination`, `mission_metadata.py:1319-1359`):
   `coordination_branch = mission_branch = <topic>`, `topology: lanes_with_coord`, `topology_settled: true`;
5. writes `lanes.json` in the coordination copy.

The root checkout keeps only empty, untracked `kitty-specs/<slug>/{checklists,research}` leftovers.

## 2. Topology is NOT read stale (the issue's hypothesis is refuted)

`mission_runtime.resolve_topology` (`resolution.py:1227` → `_resolve_topology` :1168 →
`read_dir_for(PRIMARY_METADATA)` → `missions/_read_path_resolver.py::default_mission_topic_dir`
:2124-2162) already finds the coordination copy's `meta.json` and returns `lanes_with_coord`
after settlement. Every kind (SPEC, TASKS_INDEX, STATUS_STATE, TRACER_FILE, WORK_PACKAGE_TASK,
DECISION_LOG) resolves `ref = <topic>` (probe `test_h2`). `topology_settled` is read only by
`topology_settlement.is_provisional` and `decide_topology_by_size`; no placement code needs it.
**Where settled topology is read: unchanged (stored `meta.json`, through the one locator).** Reading
it from `lanes.json` or a cache would add a second authority and trip
`tests/architectural/test_topology_inference_retired.py`.

**The missing piece is which *checkout* (worktree) holds the resolved ref, not which ref.**

## 3. Root causes, per issue (all reproduced live)

### #7551 — spec-commit / safe-commit after settlement

| Shape | Result | Mechanism |
|---|---|---|
| coord cwd, `spec-commit kitty-specs/<slug>/baseline-tests.json` | `WRONG_SURFACE`: "Artifact(s) not present at resolved placement (kitty/mission-…, worktree=<repo root>)" | `spec_commit_cmd._current_repo_root` (:55) folds cwd to the root via `find_repo_root()`; `kernel/resolution.py:118 resolve_commit_path` joins the relative path to the root; `commit_router._primary_commit_root` (:1160-1174) keeps the root because the files are not inside the holder; `_any_path_absent` (:715-726) → `no_op_wrong_surface` |
| root cwd, file written at the root path | refused: "HEAD is 'main', expected 'kitty/mission-…'. Run `git -C <root> checkout kitty/mission-…` first." | `_primary_commit_root` returns the root; `git/commit_helpers.py:~188 SafeCommitHeadMismatch` remedy cannot work — git refuses to check out a branch another worktree holds |
| absolute coord path (either cwd); `safe-commit --to-branch <topic>` from coord cwd; `tracer-append`; `issue-verdict`; `record-analysis` | commit correctly | `_primary_commit_root` picks the holder when files lie in it |

Seam invariant break (H2, confirmed): `PlacementSeam._declared_primary_write_dir`
(`resolution.py:2651-2659`) returns `path = read_dir(kind)` (the coordination copy) with
`surface_root = <repo root>`. COORD kinds are correct (`establish_coord_write_location`). Every
current `.surface_root` consumer asks for a COORD kind, so it has no live impact today, but it is
why the router keeps its own holder probe (`_primary_commit_root` → raw `checkout_holding_branch`),
the one outlier: `primary_partition_checkout`, `planning_checkout_root`,
`transaction._primary_partition_holder` and `implement_claim._claim_commit_checkout` already
delegate to the seam.

Side effect (confirmed, #5353 class): coordination and topic refs share one name, so
`commit_router.py:459` (`use_coord = routes_through_coordination(topology) and placement.ref != primary_target`)
is False for every kind; `_coord_status_locks` (:788-810) is skipped when a coordination
`status.json` / `status.events.jsonl` is committed through `commit_for_mission` (spy: `[False] committed`).

`#5501` (spec-commit dropping decision/trace/status args): not regressed; skipped paths are now
reported per surface (`_fate_for_skip`).

### #7601 — implement from the protected root checkout

`implement_phases.claim_preflight` (:365-368) → `implement_claim._raise_if_status_commit_protected`
(:120-130) judges `_status_commit_destination_branch` = `get_current_branch(repo_root) or fallback`
(:116-117) — the **root checkout's** branch, while the claim commit lands in `_claim_commit_checkout`
(the topic holder, #7372). With that gate patched out, implement on protected `main` succeeds and every
claim commit lands on the topic branch; `main` is untouched. That line is an allow-listed deferred
re-derivation in `tests/architectural/test_no_write_side_rederivation.py` (`_ALLOW_LIST_SEED`, #2453).
The remedy ("rerun with --no-auto-commit") names an option `agent action implement` does not have.

Same class, second gate (new): `agent tasks move-task WP0x --to <lane> --note …` on protected `main`
refuses `WP_METADATA_UNSUPPORTED_ON_PROTECTED_COORD_BRANCH` — `tasks_shared._skip_target_branch_commit`
(fed at `tasks_move_task.py:700`) judges meta `target_branch`, not where the WP file lands.

### #7595 (fold) — target banner falls back to `main`

`core/git_ops.py:455-466 resolve_target_branch` and `core/paths.py:887-898 get_feature_target_branch`
read a literal `kitty-specs/<slug>/meta.json` under the root and fall back to `main` when absent —
bypassing the seam reader every other surface uses.

### Baseline (`baseline-tests.json`, #7551 sentence 2) — silent drop

`workflow_executor.py:~1400 _baseline_artifact_needs_commit(authority_root=main_repo_root, …)` runs
`git status` in the root with a pathspec under the ignored `.worktrees/`; it returns empty, so the
commit is never attempted and no warning prints. `move-task --to for_review` exits 0 and leaves
`tasks/WP01-*/baseline-tests.json` untracked in the coordination worktree.

### #7602 — path-convention message

`acceptance/__init__.py:1587` passes `placement_seam(...).read_dir(SPEC)` (the coordination copy) as
`feature_dir` to `validators/paths.py::validate_mission_paths`; an artifact-tagged miss renders as
`full_path.relative_to(project_root)` (:472) → `.worktrees/<slug>-coord/kitty-specs/<slug>/contracts/`.
Correct file, wrong frame; low severity.

## 4. Gates that bind the fix

| Gate | Forbids |
|---|---|
| `test_no_write_side_rederivation.py` | commit refs / `CommitTarget` from a current-checkout expression; refs come from `placement_seam(...).write_target(kind)`; allow-list lines must still exist (drain #2453 in the same change) |
| `test_topology_inference_retired.py` | topology from `coordination_branch` truthiness / `*coord*.exists()` |
| `test_single_mission_surface_resolver.py` | raw `KITTY_SPECS_DIR / slug` joins (FUNCTIONAL_FS_BYPASS) |
| `test_write_surface_placement_guard.py` | PRIMARY kinds transiting coordination; COORD kinds off the coordination ref (fixture has coord ≠ target, so it does not see the collapse) |
| `test_commit_scope_owner.py` | pathspec-less / sweeping commits |
| `test_safe_commit_import_boundary.py` | new `commit_guard.evaluate` importers, non-seam `CommitTarget` |
| `mission_runtime` outbound ledger (`test_layer_rules.py`, `_baselines.yaml`) | new `mission_runtime → specify_cli.*` edges (shrink-only); `mission_runtime → kernel` is fine |

## 5. Sizes and churn (90 days)

`resolution.py` 3350 / 28; `_read_path_resolver.py` 2277 / 23; `commit_router.py` 2042 / 25;
`surface_resolver.py` 1297 / 28; `implement_support.py` 1163 / 51; `workflow_executor.py` 2681;
`planning_commit.py` 593 / 9; `spec_commit_cmd.py` 568 / 10; `implement_claim.py` 477 / 12;
`summary_core.py` 378 / 11; `validators/paths.py` 495. Recent: `98b9e1fa` settlement (#7282),
`3405af2e` claim in topic holder (#7372), `9a53c861` holder through the seam.

## 6. Designs considered

- **A. Route `use_coord` by topology + kind — rejected.** Does not fix #7551 (coord staging copies
  from the root path; PRIMARY kinds never take the arm) and regresses PUBLISHED/E2 and landed default
  Missions whose coordination worktree is torn down (refs equal → coord staging → fail loud).
- **B. One "which checkout" authority in the seam — chosen.** Fix `_declared_primary_write_dir`'s
  `surface_root` to the checkout that contains `read_dir(kind)` (via `kernel.git_topology`; no new
  outbound edge); make `commit_router._primary_commit_root` delegate to it; re-express an absent
  root-anchored Mission path through `write_dir(kind).path` (never compose `holder/kitty-specs/slug`);
  refuse (no copy) when only a root copy exists.
- **C. Protected checks judge the write surface** — `write_target(WORK_PACKAGE_TASK).ref` for
  implement's status preflight and move-task's metadata guard; drain #2453.
- **D. Baseline** probes and commits at the seam's `surface_root`.
- **E. #7602** renders artifact paths relative to their own checkout.
- Status lock engages when the commit worktree is the coordination worktree (keep the ref-inequality rule).
- Remedies: `SafeCommitHeadMismatch` names the holding worktree; #7601 remedy names a usable option.

## 7. Risks (ranked)

1. Changing the protected-check input turns a #5738 mismatch refusal into a protected refusal for a
   flat Mission whose root HEAD ≠ protected target (both refuse; message changes).
2. Re-anchoring that prefers a stale root leftover → wrong commit; mitigated by refuse-don't-copy.
3. H2 fix changes `surface_root` for every PRIMARY kind of an unlanded default Mission; audit callers.
4. Overlap: open PR #7596 renames `_default_mission_primary_ref` in `resolution.py` (adjacent to
   `_declared_primary_write_dir`); textual conflict risk is low, coordinate on rebase.
## Live reproduction on origin/main @ 89217ac8 (spec-kitty 4.0.0rc9, real CLI subprocesses)

Fixture: `tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py::make_default_mission`
with THREE_LANES (3 code WPs) → real `finalize-tasks` settles `lanes_with_coord`; the root checkout
returns to `create_return_branch` (main / dev), and the coordination worktree
`.worktrees/<slug>-coord` holds the topic branch `kitty/mission-<slug>` (= coordination branch).
Scripts: scratchpad `repro/test_repro_7551.py`, `repro/test_repro_7601.py` (not committed).

| # | Invocation | Result |
|---|---|---|
| R1 | root cwd, `spec-commit <abs coord path>/traces/tooling-friction.md --mission <slug>` | exit 0, committed on topic branch |
| R2 | root cwd, `spec-commit kitty-specs/<slug>/traces/approach.md` (file written at root path) | exit 1: `safe_commit: worktree <root> HEAD is 'main', expected 'kitty/mission-<slug>'. Run git -C <root> checkout kitty/mission-<slug> first.` — the remedy is impossible: the coord worktree holds that branch |
| R3 | coord-worktree cwd, `spec-commit kitty-specs/<slug>/baseline-tests.json` | exit 1 `WRONG_SURFACE`: `Artifact(s) not present at resolved placement (kitty/mission-<slug>, worktree=<repo root>)` — **#7551 exactly** |
| R4 | coord-worktree cwd, `safe-commit kitty-specs/<slug>/traces/design.md --to-branch kitty/mission-<slug>` | exit 0 |
| R5 | root cwd on protected `main`, `agent action implement WP01` | exit 1: `Refusing to start implementation status on protected branch 'main' before mutating status files ... rerun with --no-auto-commit` — **#7601** |
| R6 | same as R5 with root on unprotected `dev` | exit 0; claim commit lands on topic branch `kitty/mission-<slug>` (the coord worktree), proving the protected-branch pre-check guards the wrong destination |

Root-cause pointers found during the repro:
- #7601: `cli/commands/implement_claim.py:117-129` — `_status_commit_destination_branch` returns
  `get_current_branch(repo_root)`, while the claim commit itself runs in `_claim_commit_checkout`
  → `coordination/planning_commit.py::planning_checkout_root` → `primary_partition_checkout`
  (the FR-061 topic holder, resolved through `placement_seam(...).read_dir(PRIMARY_METADATA)`).
- #7551: the commit router's PRIMARY placement resolves `worktree=<repo root>` for a default
  Mission before landing, although the read side (`primary_partition_checkout`) already resolves
  the topic holder through the seam.
