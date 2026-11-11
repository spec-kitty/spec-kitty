# Code grounding: coordination-topology closeout recovery (#7544)

Read-only grounding before specification. Every claim below was read in the code on `origin/main`
at `2e9ca559` or reproduced with the CLI installed from that checkout (`spec-kitty-cli 4.0.0rc9`,
editable). Reader: the implementer and reviewer of this Mission.

## 1. P0 probe result (minimal `lanes_with_coord` closeout on `main`)

**Verdict: the closeout fails on `main`. This is a P0 per #7544's rule.** The repro tests carry
`@pytest.mark.p0_repro(issue=7544)` in their red commit; the fix commits remove the marker.

Fixture (scripted, no hand-run git after setup): `git init`, `spec-kitty init`, root checkout on an
unprotected topic branch `work`, `agent mission create --target-branch work` (default topology),
6 independent WPs, `finalize-tasks` (settles `lanes_with_coord`, 6 code lanes, target unprotected),
implement + review claim + approve each WP, `acceptance-verdict --criterion FR-001 --result pass`.
This is the dogfood configuration of `runtime-status-read-door-01M73HHB` (target = the operator's
unprotected topic branch, the repository root checkout on it, the coordination worktree holding the
Mission branch).

| Step | Result on `main` | Issue |
|---|---|---|
| `spec-kitty accept` | **exit 1, raw traceback** `TaskCliError: The following paths are ignored by one of your .gitignore files: .worktrees` at `acceptance/__init__.py:1845`; `meta.json` + `status.events.jsonl` left modified in the coordination worktree | #7550 |
| `consolidate` with a failure injected at any phase boundary (`_phase_mission_to_target`, `_phase_capture_and_baseline`, `_phase_record_done_and_project`, `_phase_porcelain_invariant`, `_phase_commit_and_assert`, `_phase_reconcile_before_teardown`) | rollback restores every branch, coordination worktree clean | (works) |
| `consolidate --abort` after that, then `consolidate` | **exit 1**: "lanes.json is not on the current checkout, but branch 'kitty/mission-...' carries this mission (a protected single_branch mission lives on its mission branch). Run `git checkout kitty/mission-...`" --- the coordination worktree is gone; the remedy cannot work (the branch is the coordination branch) | #5406, #7540 item 3 |
| `consolidate` SIGKILLed at the `git commit` of `status transition WP02` (the #5931 window), then `--resume`, re-run, `--abort`, re-run | **every route exits 1**: resume/re-run refuse `MERGE_UNSAFE_WORKTREE_DIRTY` (the killed write's own staged `status.events.jsonl` / `status.json` in the coordination worktree); `--abort` reports `NOT restored kitty/mission-... observed 540e259, expected 651ee69 -- moved by another actor` (540e259 is the run's own `status transition WP01` commit) and leaves the coordination checkout "as found" because it "holds uncommitted local changes ... (#1826 / NFR-002)" | #5931, #7540 item 2 |

Also observed (out of scope, recorded for the tracker): with the target on a protected `main` and the
root checkout on `main`, `agent action implement` refuses up front ("Refusing to start implementation
status on protected branch 'main'") on a settled `lanes_with_coord` Mission; the #5931 QA fixture
sidesteps it with `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1`. This is sibling-run territory
(#7545 / #7551), not this Mission.

## 2. Root causes (code-truth)

### 2.1 #7550 --- accept's record commit (`src/specify_cli/acceptance/__init__.py`, 2206 lines)

`_commit_acceptance_meta` (`:1787`) has two paths:

- protected current branch → `_commit_acceptance_meta_via_router` → `commit_for_mission(kind=PRIMARY_METADATA)` (placement-aware, correct);
- **unprotected current branch** (`:1844`) → `run_git(["add", meta_rel], cwd=repo_root)` + `git commit -- meta_rel` from the repository root checkout.

`summary.feature_dir` is resolved through the placement seam, so for a settled default Mission it
is the coordination worktree's Mission directory. `meta_rel` is then `.worktrees/<slug>-coord/...`
(git-ignored), and `git add` raises `TaskCliError` that nothing catches → traceback.

`parent_commit` (stored as `accepted_from_commit` by `record_acceptance`) is `rev-parse HEAD` of the
repository root checkout (`:1813`) --- the target branch, not the Mission branch tip that the record
describes.

`status_phase: "1"` is written by `_stamp_birth_cutover_for_accept` → `stamp_accept_cutover`
(`cli/commands/accept.py:331`), deliberately (the accept-time birth cutover, #2917 reopened; the
stamp is swept into the partition-aware residual commit). It is intended; this Mission keeps it and
documents why.

### 2.2 #7540 item 2 --- rollback cannot classify its own coordination residue (`consolidation/rollback.py`, 973 lines)

`rollback_to_snapshot` (`:946`) → `_run_residue_context` (`:740`) →
`ResidueContext.for_mission(repo_root, slug, REPOSITORY_ROOT)` (`coordination/coherence.py:473`),
which reads the stored topology from `repo_root / kitty-specs / <slug> / meta.json` (a raw join).
After topology settlement, a default Mission's `meta.json` lives only on the Mission branch (held by
the coordination worktree); the root checkout has none. `for_mission` raises `FileNotFoundError`
(verified on the probe repo), `_run_residue_context` returns `None` (strictest), and the run's own
status log/snapshot in the coordination checkout --- residue by the classifier's own rule
(`_is_disposable_residue` rule 4, and `_RunResidue.is_disposable`) --- refuses the resync.

The same raw join feeds every `ResidueContext.for_mission` / `residue_context_or_strictest` caller
(`git_probes.mission_residue_context` used by the mission_number bake advance, the lane allocator,
auto-rebase, workspace teardown, entry preflight, phase teardown, orchestrator-api, acceptance), so
the fix belongs in `for_mission` itself (read the stored topology where the placement seam puts
`PRIMARY_METADATA`), not in rollback.

### 2.3 #5931 --- in-span coordination commits leave no advance intent

The door span in `executor._run_lane_based_consolidation_locked` (`:620`) installs
`reporting_advance_intents(_note_advance_intent)`. `advance_branch_ref` and
`advance_branch_ref_for_commit` (`git/ref_advance.py:717`, `:961`) report `(branch, old, new)` to
the sink **before** their CAS `update-ref`, and `rollback.note_advance_intent` (`:585`) persists the
chain. `_effective_post` (`:419`) explains a live tip only when it is in a chain based on the
expected tip.

The mission_number bake advances via `advance_branch_ref` (intent reported). The per-WP done
transitions (`done_bookkeeping._mark_wp_merged_done` → `emit_status_transition_transactional` →
`BookkeepingTransaction.commit` (`coordination/transaction.py:1326`) → `safe_commit`) use
`safe_commit`'s **normal** path: `git add` + `git commit --only` (`git/commit_helpers.py:1022`),
which moves the branch with no intent. Post tips are recorded only at phase exit
(`@_record_post_mutation_tips`, `run_state.py`). A kill inside the phase leaves a tip the record
cannot explain → `NOT_RESTORED ... moved by another actor`, and every later run refuses
`UNEXPLAINED_BRANCH_MOVE` (`executor._refuse_unexplained_branch_moves`). `safe_commit` already has
an expected-parent mode (`_safe_commit_with_expected_parent`) that builds the commit in an isolated
index and advances through `advance_branch_ref_for_commit` (intent first, then CAS).

### 2.4 #5406 --- the next run after `--abort` (`consolidation/entry_preflight.py`, 751 lines; `consolidation/executor.py`, 1150 lines)

`--abort` tears down the coordination triple (`cli/commands/consolidate.py`, kept by the binding
2026-09-30 ruling). The next run (`executor.run_lane_based_consolidation`, `:960`) resolves
`seam.read_dir(LANE_STATE)` → the root checkout (no coordination worktree) →
`_require_lanes_json_naming_mission_branch` (`entry_preflight.py:526`) finds the holder branch with
`branch_holding_path` and prints the single_branch remedy (`git checkout <holder>`).
`materialize_coord_surface_for_write` (`coordination/surface_resolver.py:923`) is the ruled
on-demand materializer, but its default identity read (`read_primary_meta`) reads the root checkout,
which has no `meta.json` after settlement, so it would no-op; the caller must pass the
`coordination_branch` + `mid8` it already resolved (the documented override).

## 3. Size and responsibility map

| File | Lines | Responsibility touched here |
|---|---|---|
| `acceptance/__init__.py` | 2206 | acceptance record stamp + commit (`_commit_acceptance_meta*`) |
| `cli/commands/accept.py` | ~1800 | accept CLI; error rendering (`_report_error`), cutover stamp |
| `consolidation/rollback.py` | 973 | single rollback authority (restore, residue, intents, rebaseline) |
| `coordination/coherence.py` | ~700 | `ResidueContext` (destructive-guard residue rules) |
| `git/ref_advance.py` | 1077 | CAS advance/restore/resync, residue gate, advance-intent sink |
| `git/commit_helpers.py` | ~2000 | `safe_commit` (normal + expected-parent modes) |
| `coordination/transaction.py` | ~1500 | `BookkeepingTransaction` (status writes + commit) |
| `consolidation/done_bookkeeping.py` | ~800 | per-WP done transitions |
| `consolidation/phase_advance.py` | 621 | `_phase_bake_and_pre_target_done` |
| `consolidation/entry_preflight.py` | 751 | pre-mutation refusals, lanes.json holder remedy |
| `consolidation/executor.py` | 1150 | phase driver, rollback door, pre-phase resolution |
| `coordination/surface_resolver.py` | 1297 | `materialize_coord_surface_for_write` |
| `coordination/commit_router.py` | 2042 | `commit_for_mission` (placement-aware commit) |
| `cli/commands/consolidate.py` | 1640 | `--abort` teardown (unchanged by ruling) |

## 4. Invariants that must survive (cited)

- **One rollback authority** (CLAUDE.md "Refusals and failures roll back through one authority";
  ADR `2026-09-19-1` + Amendment 2026-09-29, follow-ups 2026-09-30, 2026-10-05): every restore goes
  through `rollback_to_snapshot`; AST-pinned by `tests/consolidation/test_single_rollback_authority.py`
  (allow-listed callers; no `restore_branch_ref` in the executor family outside `rollback.py`;
  retired helper names). This Mission adds no restore path.
- **#5638 resync rule**: the authority resyncs a kept coordination checkout to its tip, discarding
  only toolchain residue; a non-residue edit refuses. This Mission keeps the rule and fixes the
  residue *context* (it was unbuildable), not the rule.
- **CAS discipline** (#4996): `advance_branch_ref` / `restore_branch_ref` are 3-arg compare-and-swap,
  fail closed. Routing in-span `safe_commit` through the expected-parent mode *adds* CAS to commits
  that had none.
- **Record anchoring** (#5686): `unsettled_refs`, `advance_intents` persisted before the move,
  `UNEXPLAINED_BRANCH_MOVE` for a move the record cannot explain. This Mission makes more of the
  run's own moves explainable; it never widens what counts as explained (a foreign commit still has
  no intent).
- **ADR `2026-11-06-3`** (create-time size default): the coordination branch shares the Mission
  branch's name; PRIMARY artifacts live on the topic branch until the landing.
- **ADR `2026-10-06-3`** (evidence gates check origin freshness): untouched.
- **#5406 binding ruling (2026-09-30)**: `--abort` keeps its coordination teardown; the next run
  rematerializes via `materialize_coord_surface_for_write`.
- **Non-goal**: foreign edits are never residue. Only this Mission's status log/snapshot in its own
  coordination checkout (already the classifier's rule) become resyncable, because the classifier
  can now read the Mission's stored topology.

## 5. Architectural / AST gates referencing these files

| Gate | Pins | How this Mission stays green honestly |
|---|---|---|
| `tests/consolidation/test_single_rollback_authority.py` | one rollback door, callers of `rollback_to_snapshot` / resyncing `restore_branch_ref` | no new restore call; rollback.py's logic is unchanged |
| `tests/architectural/test_commit_scope_owner.py` | raw `git add`/`git commit` shapes | removes a raw `run_git(["add", ...])` from acceptance (shrinks) |
| `tests/architectural/test_destructive_op_routing.py` | destructive git ops route through the guard | no new destructive op |
| `tests/architectural/test_no_write_side_rederivation.py`, `test_write_surface_placement_guard.py`, `test_single_mission_surface_resolver.py`, `test_no_read_side_bypass.py` | placement re-derivation / raw mission-dir joins | the `for_mission` change moves a raw `repo_root/kitty-specs/<slug>` join onto the placement seam (if a ledger lists it, re-point, never loosen) |
| `tests/architectural/test_merge_pipeline_ratchets.py` | consolidation pipeline ratchets | rerun; no new entries |
| `tests/architectural/test_layer_rules.py` | `kernel <- charter <- {...} <- specify_cli` | `git/ref_advance.py` stays free of `specify_cli` imports (C-003) |
| `tests/architectural/test_no_legacy_terminology.py` | retired terms in prose | run before push |

## 6. Test seams and cost

- `tests/consolidation/` (182 files): rollback, residue, resume, intents (`test_rollback_*`,
  `test_unexplained_*`, `test_coord_*`). Unit-to-integration, real git in `tmp_path`; seconds each.
- `tests/coordination/` (`test_disposable_residue.py` for `ResidueContext`).
- `tests/specify_cli/acceptance/` (`test_acceptance_support.py`, `test_commit_acceptance_meta_via_router_rendering.py`, `test_issue_4974_accept_concurrent_verdict.py`).
- `tests/specify_cli/git/` / `tests/git/` for `safe_commit` expected-parent mode.
- End-to-end CLI fixture (this note's probe): about 5 minutes for a 6-lane Mission build (every
  `implement`/`move-task` is a CLI subprocess). The acceptance integration test must build its
  fixture once per module and replay states from it, and carry the slow/e2e marker so the fast tier
  stays fast.

## 7. Interactions

- **PR #7557** (open; `coherence.is_self_bookkeeping_churn` counts `kitty-ops/lifecycle/<ULID>.json`):
  same module as the `for_mission` change, disjoint function. If it lands first, rebase; no
  semantic conflict.
- **#7545** (sibling run: CLI commits its own writes / dirty gates) and **#7551**
  (spec-commit/safe-commit WRONG_SURFACE): overlap with the accept placement fix only in spirit; this
  Mission changes only accept's record commit.
- **#7549** (doctor coordination filter + decisions lock): disjoint.
- **#7310 / S5 status-read-door run**: disjoint files.

## 8. 90-day churn (origin/main, since 2026-08-13)

| File | Commits | of which `fix` |
|---|---|---|
| `consolidation/executor.py` | 75 | 50 |
| `acceptance/__init__.py` | 36 | 18 |
| `git/commit_helpers.py` | 35 | 22 |
| `coordination/transaction.py` | 30 | 17 |
| `coordination/coherence.py` | 27 | 13 |
| `git/ref_advance.py` | 22 | 16 |
| `consolidation/rollback.py` | 16 | 11 |
| `consolidation/done_bookkeeping.py` | 16 | 8 |
| `consolidation/entry_preflight.py` | 11 | 6 |
| `consolidation/mission_number/bake.py` | 6 | 3 |

`executor.py` is the hotspot; this Mission keeps its change there to the pre-phase resolution (no
phase-list change, which the phase-boundary pins index).
