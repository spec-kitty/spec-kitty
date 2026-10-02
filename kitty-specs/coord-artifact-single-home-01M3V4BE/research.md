# Research: coord-artifact-single-home-01M3V4BE

Phase 0 output. Every line reference was re-verified at `ecb5dd914a`; `git diff ecb5dd914a HEAD -- src tests .gitattributes` is empty. **Audience:** the implementer and reviewer of this Mission.

## Grounding corrections

These correct the pre-spec grounding notes. The plan uses the corrected values.

| Claim | Code truth at `ecb5dd914a` |
|-------|----------------------------|
| `mission_finalize.py:2372` is a COORD writer | It is a read inside `_execution_has_begun` (L2325). The finalize writers are `_emit_local_canonical_events` (L2266, writes `WPCreated`/`TasksCompleted` to `planning_dir`) and `_resolve_finalize_commit_candidates` (L3542, primary-only porcelain). |
| `review/cycle.py:298-303` REVIEW_CYCLE fallback is the review-cycle writer path | No production caller passes `kind=REVIEW_CYCLE`. The writers use the default `WORK_PACKAGE_TASK` read dir (PRIMARY, L306) and commit via `commit_artifact(kind=REVIEW_CYCLE)` (L712-718). That is stage-in-root-then-copy. |
| `runtime_bridge` builds the `DecisionGitLog` target via `resolve_write_target_or_degrade` | It builds `CommitTarget(ref=coordination_branch)` in `runtime_bridge_io.py:1552`, and picks the worktree via `CoordinationWorkspace.worktree_path` or `resolve` (`runtime_bridge.py:359-363`). |
| `consolidation/executor.py:4017` and `git_probes.py:237` call the residue predicate | Those lines are `git reset --hard HEAD`. The predicate sites are `executor.py:2036` (`_phase_porcelain_invariant`), `:3273`, `:3500`, and `git_probes.py:183` (`_classify_porcelain_lines`). |
| `bookkeeping_projection._post_checkpoint_mission_paths` L447-488 | `def` is at L418. The PRIMARY-kind exclusion is at L481. |
| `_commit_create_scaffold` L1938 | `def` is at L1564; L1938 is its call site. |
| `accept` calls `commit_for_mission` | It does not. `_commit_coord_residuals` (L405-442) calls `write_seam.write_artifact` with coordination-relative paths joined onto the repository root checkout (L425). That is the live #5513 caller. |
| ~10 `_merge_group_results` consumers | 14 sites; see D8. |
| `is_coord_residue_churn` in `artifacts.py` | It is in `coordination/coherence.py:159`. |
| A `TRACER` kind | The kind is `TRACER_FILE`. |

**Additional writers not in the grounding notes:**
- `BookkeepingTransaction._acquire_locked` composes the coordination Mission dir itself (`transaction.py:490`).
- `accept._coord_status_feature_dir` (`accept.py:154/193`, birth cutover).
- `lanes/recovery.py:785`.
- `materialize`'s all-Missions loop (`materialize.py:103-105`), which iterates the repository-root Mission dirs, so for a coordination Mission it reduces the stale root log and writes `status.json` there.
- `retrospect._canonical_events_path` (`retrospect.py:109`).
- `agent_retrospect._canonical_events_dir` (`agent_retrospect.py:198`).
- `materialize._resolve_selected_dir` (`materialize.py:31`).
- `consolidation/executor.py:825` and `:4183`.

---

## D1. Write-location accessor shape

- **Decision.** Add one method to the existing seam: `PlacementSeam.write_dir(self, kind: MissionArtifactKind) -> WriteLocation`, in `src/mission_runtime/resolution.py`, beside `write_target` (L2304) and `read_dir` (L2318).
  - `WriteLocation` and its `Establishment` enum live in a new small module, `src/mission_runtime/write_location.py`, so `resolution.py` does not grow by a type block.
  - `WriteLocation` carries `checkout_root: Path` (post-tasks P-M3): the root of the checkout that holds `path`. That is the coordination worktree root for `surface="coordination"`, and the repository root checkout for `surface="primary"`. Consumers use it instead of guessing `.path.parent.parent`, and `tests/architectural/test_no_worktree_name_guess.py` is a named gate for them.
  - For PRIMARY kinds, and for any kind in a non-coordination topology, it returns the declared PRIMARY dir. That is today's `read_dir`, which for these cases is the declared-PRIMARY short-circuit at L2523-2525 and involves no fallback.
  - For COORD kinds of a coordination-routed Mission, it delegates through a lazy import to `specify_cli.coordination.coord_seed.establish_coord_write_location(...)`, which materializes, seeds or refuses.
- **Rationale.**
  - C-001 sanctions exactly one accessor on the existing seam.
  - `write_target` already answers "which ref" and `read_dir` "where to read". `write_dir` answers "where to write" and agrees with `write_target` by construction: a COORD kind's dir is inside the coordination worktree, whose branch is the `write_target` ref.
  - **Public surface.** `coord_seed.py`, and every other module outside `mission_runtime`, may import mission_runtime symbols only from the package root. This is enforced by `tests/architectural/test_mission_runtime_surface.py`: MR-1 (pytestarch, L244) and MR-2 (AST scan, L342). So `src/mission_runtime/__init__.py` `__all__` and the test's `_PUBLIC_SURFACE` (L50) gain `WriteLocation` and `Establishment`, owned by the seed/accessor concern.
  - `coordination` is already in `_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI` (`tests/architectural/test_layer_rules.py`, cap 10 in `_baselines.yaml:21`), so the `mission_runtime` outbound ledger does not grow. This is the same delegation pattern as RETROSPECTIVE's `resolve_retrospective_home`.
- **Alternatives rejected.**
  - (a) `resolve_status_surface_with_anchor(for_write=True)` as the authority. Its `for_write` arm gates only the completed-Mission shortcut (L1267). It is called from `resolve_placement_only` via `_assemble_core_fragments(for_write=True)` (`resolution.py:1974-1982`), which must stay side-effect-free, so it cannot materialize or seed.
  - (b) Promote `status_transition._coord_feature_dir`. It is private, status-only and blind to the EMPTY state.
  - (c) A new module-level `write_dir_for` free function. It would be a second entry point beside the seam (DIRECTIVE_044).
  - (d) Return a bare `Path`. The seed report has to reach the CLI renderers, and a bare path drops it.

## D2. Seed lock ordering and atomicity

- **Decision.**
  - The seed runs under `feature_status_lock(lock_root, coord_mission_dir_name(slug, mid8), timeout=<bounded>)`.
    - `lock_root = owned.owned_root if owned else repo_root`, matching `BookkeepingTransaction` (`transaction.py:290-291`).
    - The key is the Mission dir name, the same key as `coord_status_lock` (`status_transition.py:421-423`) and `commit_router._coord_status_locks` (L586). The lock is keyed on the git common dir plus that name (`status/locking.py:147,278`), so the root and coordination surfaces share it, and it is reentrant (`kernel.locks.machine_file_lock(..., reentrant=True)`).
    - The timeout is **bounded**, reusing `BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS` (`status/locking.py:54`, 10 s), the constant `coord_status_lock` already passes (`status_transition.py:424`). `feature_status_lock`'s default `timeout=-1` (L278) waits forever, which would make `STATUS_LOCK_HELD` unreachable.
  - Order: materialize first (`CoordinationWorkspace.resolve` takes its own path-keyed lock and releases it), then take the status lock and seed.
  - When the caller already holds the status lock, as `BookkeepingTransaction.acquire` does (`transaction.py:292` then `:465`), materialization nests under it. That is the order the transaction already uses, and `workspace.py` never takes the status lock, so no cycle is possible.
  - The seed builds `kitty-specs/.<dir>.seed-<pid>-<ulid>/` in the coordination worktree and makes it visible with one `os.rename`.
  - Writers call `write_dir` before `emit_status_transition` reduces the log (`emit.py:947-955`). The reduce therefore reads the seeded coordination log, never the root log.
- **Rationale.** This meets FR-004a and the spec's atomic-seed edge case. Readers never see a partial dir, and a crash leaves only a hidden temp dir that the next seed removes under the lock.
- **Alternatives rejected.**
  - Seeding file by file: readers can observe a log without its tracer files.
  - A new seed lock: a second lock authority, with a new ordering hazard against the status lock.

## D3. Prefix rule and fork refusal

- **Decision.** Apply the rule per log stream (`status.events.jsonl`, `decisions.events.jsonl`) on event-id sequences.
  - The coordination side is the worktree file if present, else the coordination-branch tip blob (`git show <coord>:<path>`).
  - Absent or a prefix: carry the missing tail.
  - Root a prefix of coordination: nothing to carry.
  - Otherwise refuse with `COORD_SEED_FORK_REFUSED`, naming both locations and the reconcile steps.
  - Non-log records are carried only when absent on the coordination side; the coordination copy wins on conflict and the root copy is reported.
- **Home.** The rule is a pure classifier in `src/specify_cli/coordination/event_prefix.py` (post-tasks P-M6), for example `event_ids_of(lines)` and `classify_prefix(root_ids, coord_ids) -> PrefixVerdict`. It has no git or lock imports. `coord_seed.py` and the fork detector (D14) both import it.
- **Rationale.** This is the operator ruling (`specify.design.fork-check`). Comparing event ids, not bytes, tolerates re-serialization. Reading the branch blob when the worktree is empty catches the post-fix regression case.
- **Alternatives rejected.**
  - A byte-prefix comparison: brittle across key ordering.
  - Merging forked logs: forbidden by C-003.

## D4. Telling a post-fix Mission's empty surface from a pre-fix one

**Decision.** The discriminator is a **seed marker in the coordination branch history**: a commit trailer `Spec-Kitty-Coordination-Seed: <mission_id>` on every seed commit.
- Two kinds of commit carry it: the create-time commit (IC-05) and a pre-fix Mission's carry-over commit (D5). Both write it through **one shared constant**, `COORD_SEED_TRAILER` in `coordination/coord_seed.py` (Decision Moment `plan.design.seed-trailer-ownership`). If a seed commit is refused, the next seed attempt (the next COORD write, which finds the seed pending: no trailer **and** no COORD-kind blob under the Mission dir at the coordination tip; data-model I-SEED-10) re-commits with the trailer. A never-seeded pre-fix MATERIALIZED Mission (#5519 shape) has committed COORD blobs and is never touched; the commit router itself never adds the trailer.
- A Mission counts as **post-fix** iff `git log --format=%(trailers:key=Spec-Kitty-Coordination-Seed,valueonly) <coordination_branch>` contains its `mission_id`.
- There is no new `meta.json` field.
- **EMPTY on a post-fix Mission** means the Mission dir was deleted in the worktree, a regression.
  - Write side: warn loudly, then restore **COORD-kind paths only** from the branch tip, with an explicit pathspec built from `kind_for_mission_file` over `git ls-tree -r <coord> kitty-specs/<dir>/`. Never restore the whole dir, which would bring PRIMARY files across (I-SEED-9). Then write.
  - Read side: the `EMPTY` warning (`surface_resolver.py:1430-1450`) also fires for solo `coord`.
- **EMPTY without the marker** means a pre-fix Mission: seed (D3, D5). The seed commit adds the marker, so a healed Mission is post-fix from then on.

**Why not "the branch tree carries `kitty-specs/<dir>`"** (the plan's first draft). That test over-matches. A pre-fix Mission whose coordination branch was cut **after** the first target commit carries the Mission dir, with PRIMARY planning files, without ever having been seeded (fixture `tests/coordination/test_surface_resolver_solo_coord_primary.py:107-146`). That fixture is the required **negative case**: no trailer means pre-fix, so the Mission is seeded, not restored.

**Fix in passing:** `coord_branch_has_committed_artifact` (`surface_resolver.py:786`) composes `kitty-specs/{mission_slug}`, not the mid8-suffixed Mission dir (`coord_mission_dir_name`), and fails closed to `True`. It is corrected to compose the real Mission dir and to probe COORD-kind paths only. Its write-gate role is absorbed by D22.

**Rationale.**
- The trailer is written only by the one seed path, so it cannot drift from a meta stamp (DIRECTIVE_044).
- It survives clones.
- It is per-Mission even when several Missions share history.

**Alternatives rejected.**
- A meta flag such as `coordination_seeded_at`: a second source of truth.
- "Branch tree carries the dir": over-matches, as shown above.

**Operator ruling (plan, Q3).** Restore from the coordination branch tip (COORD-kind paths), warn loudly, then write. Spec rev 3 states this in US2.7 and FR-003a.

## D5. The seed commits on the coordination branch

- **Decision.** The seed commits the carried files as one commit on the coordination branch through the existing coordination commit path, before the triggering write appends. The call is `commit_for_mission(kind=STATUS_STATE, files=<coordination-worktree paths>)`; such paths commit in place per `commit_router.py:1026-1029`.
- **Rationale.** The commit makes the carry-over durable across clones, so a later fresh clone sees MATERIALIZED and never re-seeds (FR-004a, "exactly once"). It also writes D4's seed trailer, so a healed pre-fix Mission counts as post-fix from then on.
- **Alternative rejected.** Leaving the carry-over uncommitted until the next commit. A tracer-only write would leave the status log uncommitted on the coordination surface indefinitely.
- **Operator ruling (plan, Q5).** Confirmed: the pre-fix seed makes one commit on the coordination branch before the triggering write proceeds. Spec rev 3 states this in FR-004 and US2.4.

## D6. Create: eager materialization and the coordination-vs-target model

**Decision (create order).** This is the operator ruling `specify.design.seed-mechanism`. In `_create_mission_core_impl` (`mission_creation.py:1722`), after `_build_create_meta` (L1894, which cuts the branch at L1302) and the re-target (L1923):
1. Call `placement_seam(...).write_dir(STATUS_STATE)`. This materializes the worktree and seeds an empty Mission dir.
2. `_emit_create_events` (L1429) writes `MissionCreated` and `SpecifyStarted` into that dir instead of the root scaffold dir.
3. Commit them on the coordination branch through `commit_for_mission(kind=STATUS_STATE)`.
4. Remove `status.events.jsonl` from `scaffold_paths` (L1168-1173) and from the target scaffold commit (`_commit_create_scaffold`, L1564).

`meta.json`, `tasks/README.md` and `tasks/.gitkeep` stay on the target branch (FR-001 positive control).

**Decision (protected target).**
- The seed is not inside the `_BOOTSTRAP_META_COMMIT_SKIPS` suppression (L69-73, used at L1178/1601/1642). It runs unconditionally for coordination-routed topologies (FR-002a).
- `_restore_git_state_after_failed_create` (L683) gains a coordination leg for the worktree and branch **this create** made, identified by slug plus mid8 (`coord_mission_dir_name`), never by a glob over other Missions:
  - Remove the coordination worktree. `CoordinationWorkspace.teardown` (`workspace.py:352`) refuses a dirty worktree with `DestructiveOpRefused` (L363-369), and a failed create can leave exactly the seeded, uncommitted files behind. So the rollback leg removes the worktree with `git worktree remove --force` scoped to that path, which is sanctioned because every file in it was written by this create. Alternatively it passes an `is_residue` that accepts this Mission's COORD-kind paths.
  - Delete the coordination branch only when this create minted it (`CoordinationBranchResult.created`). The existing sweep of `kitty/mission-*` branches that appeared during the run already covers the branch name; the leg asserts the branch is gone.
  - Prune worktree metadata (`git worktree prune`).
- Rollback covers both refs and the worktree (US1.5). A test fails create after the seed commit and asserts that no coordination branch, no worktree and no target scaffold commit remain.

**Decision (divergence model, FR-002b).** Define an "expected divergence" predicate once, in `missions/_create.py`, beside `CoordinationBranchDiverged` (L92). The relation is expected when all of these hold:
- `merge-base(coord, target)` is reachable from the target;
- every coordination-only commit (`target..coord`) touches only COORD-partition paths of this Mission (classified with `kind_for_mission_file`);
- the target's own commits since the merge base do not touch those paths.

Consumers:
- `ensure_coordination_branch` (`_create.py:195`, raises at L254 when the branch exists, `force_recreate` is false, and it is not an ancestor of the target) accepts the expected relation.
- `_coord_branch_stale_vs_target_finding` (`_coordination_doctor.py:642`) returns no finding for it. `COORDINATION_BRANCH_DIVERGED_VS_TARGET` (L635) stays for genuine divergence, such as a coordination commit touching PRIMARY paths, or a legacy fixture.
- The `--fix` fast-forward arm (`_fix_one_mission_coord_staleness`, L1743) is unchanged: it still fast-forwards a coordination branch that is strictly behind the target.

**Rationale.** One predicate is shared by create and doctor, so neither re-derives it. The genuinely diverged legacy fixture still reports.

**Alternatives rejected.**
- Committing the creation records on the target and cutting the coordination branch afterwards. This reintroduces #5440.
- A direct ref commit. Rejected by the operator ruling, because it leaves the Mission UNMATERIALIZED.

## D7. Commit router: commit the owning-surface copy

**Decision.** In `_stage_artifacts_in_coord_worktree` (`commit_router.py:991`), a root-path COORD log input is no longer skipped (L1038-1039 today, `STATUS_STATE`). It is translated to its owning-surface path via `write_dir(kind)`, keeping the same Mission-relative path. This applies to `STATUS_STATE` and `DECISION_LOG`, whose root copies are append-only logs that must never be copied over the coordination copy.

`_classify_no_commit_paths` (L436; primary-only dirt check at L457 via `_paths_uncommitted_in_primary`, L1263) checks dirt on the owning surface: coordination-worktree porcelain for the translated paths. The outcomes:

| Owning copy | Outcome | Notes |
|-------------|---------|-------|
| Dirty | committed | |
| Clean | unchanged | the positive control |
| — | refused, with a named reason: | |
| | `PROTECTED_BRANCH_REFUSED` | reused from `coordination/types.py:90` |
| | `STATUS_LOCK_HELD` | new; maps `FeatureStatusLockTimeoutError`, `status/locking.py:59`, today turned into `status="error"` at L639-640 |
| | `COORDINATION_BRANCH_DELETED` | reused |
| | `COORDINATION_WORKTREE_UNMATERIALIZED` | reused; remote-only coordination branch (#4970 parity), surfaced from `write_dir` |
| | `COORD_SEED_FORK_REFUSED` | new (contracts/seed.md); surfaced from `write_dir` when establishing the surface hits a fork |
| | `PATH_UNROUTABLE` | new |

Other COORD kinds keep today's copy behaviour only while the coordination copy is absent (legacy staging), with the existing residue cleanup (L1069-1088). Once writers write in place (IC-04), that path is a fallback.

**Rationale.** FR-006: "unchanged" means unchanged. Translation uses the taxonomy (`kind_for_mission_file`) and the accessor, so there is no second classifier.

**Alternative rejected.** Copying the root log over the coordination log. That is exactly the clobber the L1038 skip was added to prevent.

## D8. Commit-outcome contract shape and consumer migration

**Decision.** Extend `CommitRouterResult` (`commit_router.py:174-205`) additively with `surfaces: tuple[SurfaceOutcome, ...] = ()`. A new module, `src/specify_cli/coordination/commit_outcome.py`, holds `SurfaceOutcome`, `PathFate`, and one renderer pair:
- `render_commit_outcome(result) -> list[str]` (text);
- `commit_outcome_payload(result) -> dict` (JSON).

The legacy fields keep the caller-surface selection of `_merge_group_results` (L802-844) for compatibility. Wrapper results gain `surfaces` too:
- `WriteSeamResult` (`write_seam.py`, which today drops `commit_hashes`/`reason`);
- `CommitArtifactResult` (`agent_tasks_ports.py:108`).

Every consumer renders through the shared pair. The consumers, verified:

| Consumer | Site | Today |
|----------|------|-------|
| setup-plan | `mission_setup_plan.py:237` | reads status/ref/hash/diagnostic |
| setup-plan gap analysis, generator config | `:892`, `:951` | result discarded |
| record-analysis | `mission_record_analysis.py:374` | discarded |
| report transaction | `git/report_transaction.py:199` | reads status/hash/diagnostic |
| orchestrator API | `orchestrator_api/commands.py:3018` | discarded |
| acceptance | `acceptance/__init__.py:1791`; `:1822` | reads; discarded |
| write seam | `coordination/write_seam.py:548` | drops hashes/reason |
| ↳ acceptance matrix | `acceptance/matrix.py:524` | via write seam |
| ↳ issue matrix | `tasks/issue_matrix.py:404` | via write seam |
| ↳ tracer | `retrospective/tracer_writer.py:298` | via write seam |
| ↳ accept coord residuals | `cli/commands/accept.py:426` | via write seam |
| finalize | `mission_finalize.py:3659` (fold `_apply_finalize_commit_router_result`, L3585) | reads |
| finalize pin refresh | `mission_finalize.py:2874` | reads |
| retrospect | `retrospect.py:315` | reads |
| spec-commit | `spec_commit_cmd.py:214` (branch L229-285) | reads caller fields only |
| tasks ports | `agent_tasks_ports.py:389/400` → `review/cycle.py:712`, `tasks_map_requirements.py:668` | drops hashes/reason |
| tracer-append CLI | `cli/commands/agent/tracer_append.py:135-163` | hand-renders caller fields |

mark-status is **not** a consumer: its live write path (`_ms_emit_subtask_state`, L359/L406-413) commits nothing, and the `tasks_mark_status.py:279` `_ms_commit` shim is dead code.

Discarded-result sites render a warning only when a surface is not `committed`/`unchanged`.

**Exit-code rule.** A command exits non-zero when any surface is `refused` or `error`. A `skipped` outcome exits 0 and is rendered.

**Rationale.** FR-007: masking lives in the shared contract, so the fix belongs there. An additive field keeps old JSON readers working.

**Alternatives rejected.**
- Changing the top-level `status` to the worst surface. It breaks the 14 consumers' existing branches at once.
- A renderer per consumer: parity drift.

## D9. Accept routes both residual legs through the router

**Decision.**
- Remove `_commit_primary_residuals` (`accept.py:369-402`), the raw `git add`/`git commit`.
- Replace both legs with one call: `commit_for_mission(files=<root-checkout dirty Mission paths> ∪ <coordination-worktree dirty Mission paths, as coordination paths>, kind=ACCEPTANCE_MATRIX)`. The router groups by partition.
  - PRIMARY files go to the target branch.
  - COORD files go to the coordination branch as owning-surface copies (D7).
  - A COORD record dirty only in the repository root checkout is reported as `skipped` with reason `COORD_RECORD_IN_ROOT_CHECKOUT` and never committed to the target branch.
- Fix L425's join: coordination-relative paths must not be joined onto the root.
- The dirty gate `_filter_coordination_residue` (`acceptance/__init__.py:411`, L440) calls the commit router's **public per-path partition predicate** (post-tasks P-M5, e.g. `partition_for_mission_path(repo_root, mission_slug, path, *, owned)`). It is the same function the router's grouping uses, not a copy, and no new `_is_coordination_owned()` classifier is added. A test asserts the gate and the committer agree path for path (US3.7).
- `owned` is forwarded; today `_commit_residual_acceptance_artifacts` (L445) drops it.

**Rationale.** FR-005, and C-001: remove the fifth commit mechanism, add none.

## D10. Finalize sees coordination dirt

**Decision.**
- `_resolve_finalize_commit_candidates` (`mission_finalize.py:3542`; primary-only porcelain at L3571-3577) adds the coordination-worktree porcelain for the COORD candidates. Those are the status log and the matrices, resolved via `write_dir(kind).path`.
- `_emit_local_canonical_events` (L2266) writes through `write_dir(STATUS_STATE)`.
- `tasks_finalize._ft_apply_writes` (L250, `read_dir(STATUS_STATE)` at L444) does the same.
- The finalize output renders per-surface outcomes (D8).

**Rationale.** FR-007b. Finalize's own planning-pin refresh preflight already checks both surfaces (`_refresh_worktree_status_findings`, L2586), so this reuses that precedent.

## D11. Retire `_try_advance_ref`

**Decision.**
- Delete the post-commit advance (`commit_router.py:560-561`) and `_try_advance_ref` (L1302-1342). Its condition `use_coord and target_branch` means it only ever fired for coordination-routed Missions.
- Keep the `target_branch` parameter of `commit_for_mission`; it is still used for the owned-placement result (L283/L290).
- Correct `spec-commit --target-branch`'s help ("post-commit ff-advance", `spec_commit_cmd.py:166-170`).
- Consolidation's bookkeeping projection (`bookkeeping_projection.py:487`) and `advance_branch_ref` (`git/ref_advance.py:493`) are untouched (FR-008 exclusion).

**Rationale.** After D6, the target is an ancestor of the coordination tip right after a protected-target create, so the advance would fast-forward COORD records onto the target. The function was best-effort and swallowed every exception (L1339-1342), so no caller depends on its effect.

**Alternative rejected.** Guarding the advance with a residue check. The residue exclusion is exactly what lets COORD records ride along.

## D12. Ledger reclassification blast radius

**Decision.**
- Move `DECISION_LEDGER` from `_PLACEMENT_ARTIFACT_KINDS` (`artifacts.py:194-213`) to `_PRIMARY_ARTIFACT_KINDS` (L158-186). `_COORD_RESIDUE_DIRS["decisions"]` (L287) keeps mapping the dir to the kind; the kind's partition now makes `kind_is_coordination_residue` (L131-149) false.
- Rewrite the stale #3928 comments at L108-117, L209-211 and L280-287.

Readers that flip (for coordination-routed Missions; `lanes`/`single_branch` keep today's verdict per the design rule below):

| Reader | Site | After |
|--------|------|-------|
| commit router grouping | `commit_router.py:768` | ledger goes to the target branch (intended) |
| accept dirty gate | `acceptance/__init__.py:440` | real work; committed by accept |
| retrospect | `retrospect.py:281` | real work |
| record-analysis preflight | `mission_record_analysis.py:198` | real work |
| implement partition | `implement.py:905/947`, `implement_cores.py:355` | PRIMARY |
| move-task / tasks shared | `tasks_move_task.py:824`, `tasks_shared.py:750` | not dropped as residue |
| consolidation porcelain invariant | `consolidation/executor.py:2036` | ledger dirt blocks (no reset) |
| consolidation lane cleanup / preflight | `executor.py:3273`, `:3500` | real work |
| git probes | `git_probes.py:183` (via injected predicate) | real work |
| auto-rebase | `lanes/auto_rebase.py:225` | not coordination-owned |
| review dirty classifier | `review/dirty_classifier.py:129` | not benign |
| workspace teardown | `coordination/workspace.py:379` | ledger dirt in the coordination worktree blocks removal |
| orchestrator lane cleanup | `orchestrator_api/commands.py:958` | real work |
| rollback | `consolidation/rollback.py:362` | real work |
| ordering | `consolidation/ordering.py:659` | real work |
| bulk-edit diff check | `bulk_edit/diff_check.py:361` | not exempt |
| lane consolidation | `lanes/consolidation.py:1234/1316` | real work |
| bookkeeping projection | `bookkeeping_projection.py:481` | excluded as PRIMARY. A pre-fix coordination-only ledger is NOT projected, so teardown refuses (D15) |
| `_try_advance_ref` residue | `commit_router.py:1337` | deleted (D11) |
| placement guard | `tests/architectural/test_write_surface_placement_guard.py` L12 docstring, L344-358 live set | update |
| merge-class guard | `tests/architectural/test_merge_reconciliation_class_guard.py` `_NON_DIVERGENT_COORD_RESIDUE_DIRS` (L318-334) | update (D13) |
| commit router: partition-kind readers | `commit_router.py:697` (`kind_for_mission_file`), `:839` (`_merge_group_results` caller partition), `:915` (primary-kind-reached-coord guard), `:1193` (`_resolve_commit_worktree_for_kind`), `:1337` (deleted with D11) | ledger is PRIMARY: never staged to the coordination worktree; the L915 guard now raises if a ledger path reaches coordination staging |
| surface authority | `coordination/surface_authority.py:232` (`use_coord = routes_coord and not is_primary_artifact_kind(...)`) | ledger commits route PRIMARY |
| read-path resolver | `missions/_read_path_resolver.py:1446` | ledger reads resolve PRIMARY (already true via `PRIMARY_METADATA`; FR-009a ratchet) |
| placement seam | `resolution.py:1289`, `:1316` (owned read dir / commit target), `:1419` (placement ref), `:2487` (`declared_read_surface`), `:2704` (owned surface stamp) | ledger resolves PRIMARY on every arm, including owned checkouts |
| workflow partition | `cli/commands/agent/workflow.py:393` | ledger paths go to the primary partition group |
| acceptance kind audit | `acceptance/__init__.py:1219` (non-primary kind listing), `:1269` | ledger leaves the non-primary listing; audit the message text |
| planning recency | `consolidation/planning_recency.py:39` (`_is_primary_planning_path`) | **hazard**: see "Merge-driver hazard" below |

**Design rule: non-coordination topologies keep today's ledger handling (C-008)** (Decision Moment `plan.design.topology-less-callers`).

- **The problem.** Several residue readers pass no topology, and `is_coord_residue_churn` then defaults to COORD (`coherence.py:224-226`). They are:
  - the consolidation porcelain invariant (`executor.py:2036`);
  - move-task (`tasks_move_task.py:824`) and `tasks_shared.py:750`;
  - implement (`implement.py:905/947`);
  - auto-rebase (`lanes/auto_rebase.py:225`);
  - the commit router grouping (`commit_router.py:768`).

  So today `decisions/` counts as residue for **every** topology at those sites, and removing `DECISION_LEDGER` from the COORD set would also change `lanes` and `single_branch` behaviour.
- **The rule: one fix point, the predicate.** When `topology is None` and a Mission slug is available, `is_coord_residue_churn` (and therefore `is_toolchain_generated_churn`) in `coherence.py` resolves the Mission's **stored** topology:
  1. **Non-coordination Missions** (`lanes`, `single_branch`) keep exactly today's verdict at every caller (C-008), pinned by a characterization test over each caller path.
  2. **Coordination-routed Missions** get the PRIMARY ledger rule at **every** caller, including move-task, implement and auto-rebase: an uncommitted ledger is real work, not residue.
  3. A caller that passes neither topology nor slug keeps the base verdict, and is listed in the activity log.

  There are no per-caller topology patches and no compatibility set.
- **Tests.**
  - A red-first characterization on `lanes` and `single_branch` Missions: each caller's base verdict for `decisions/*`.
  - Coordination-Mission tests at move-task, implement and auto-rebase (plus the FR-009 readers: the accept gate, the consolidation porcelain invariant, record-analysis and the commit router grouping), asserting that an uncommitted ledger is real work.

**Merge-driver hazard (owned by the ledger-reclassification concern, plan IC-11).**
- **How it breaks.** After the flip, `planning_recency._is_primary_planning_path` (L39-47) classifies `decisions/index.json` as a PRIMARY planning file. `target_newer_primary_artifacts` (called from `lanes/consolidation.py:748-750`) then re-resolves it with a base/target/lane `git merge-file` that favours the target on overlap. That overwrites the `spec-kitty-decision-index` driver's union result, losing lane-added entries.
- **Design rule.** Paths covered by a registered merge driver are skipped by the planning-recency resolver. `_is_primary_planning_path` returns False for any path matching a `_MERGE_DRIVERS` pattern (`lanes/consolidation.py:59-123`), the single registry, read rather than copied.
- **Test.** A target-newer `index.json` plus a lane-added entry: after consolidation both entries are present.

**Rationale.** This is the operator ruling (`decision-ledger-partition`). The reversal of the #3928 intent gets its **own short ADR** in `docs/adr/4.x/` (written with the docs concern, IC-17) rather than an amendment buried in an unrelated 3.x ADR (analyze C5). Writes and reads are already PRIMARY (`decisions/service.py::_ledger_dir` L255-279 → `PRIMARY_METADATA`, #4966), so FR-009a is a ratchet.

**Committers (Decision Moment `plan.scope.ledger-committers`, analyze G1).** The ledger is committed by **spec-commit and accept only**. setup-plan and finalize-tasks keep committing only their own artefacts: at base, `_collect_finalize_artifacts` (`mission_finalize.py:274-356`) does not collect `decisions/`, and setup-plan commits only plan artefacts. No new auto-commit is added.

**Risk.** For coordination-routed Missions, the consolidation dirty gate (`executor.py:2036`) previously reset ledger dirt as residue; now it refuses. That is correct (FR-009), but it is a behaviour change for an operator who left an uncommitted ledger. The refusal message must name `accept` or `spec-commit`.

## D13. Decision index merge driver

**Decision.**
- Add a `spec-kitty-decision-index` driver: a keyed union of `entries` by `decision_id`. A same-id collision resolves with the existing fold precedence (`decisions/index_fold.py` `_select_terminal_event`/`apply_terminal`), so a terminal status beats `open`. The output is deterministic, sorted by `created_at` then `decision_id`.
- Register it in `_MERGE_DRIVERS` (`lanes/consolidation.py:59-123`), `MERGE_DRIVER_BODIES` (`consolidation/drivers.py:1117-1126`), the CLI (`cli/commands/merge_driver.py`, a `merge-driver-decision-index` command), the init seed (`cli/commands/init.py:67-74` constants plus `_ensure_event_log_merge_attributes`, L455), and `.gitattributes`.
- Ship an upgrade migration modelled on `m_3_2_6_decisions_event_log_merge_driver.py`, with its own migration id.
- `DM-*.md` needs no driver: the files are ULID-named, one per decision.

- The union is a pure public function, `union_decision_index(ours, theirs) -> dict` in `consolidation/drivers.py` (post-tasks P-M6). The driver body is a thin IO wrapper around it, and `doctor decisions --repair`'s coordination-only-ledger merge (D14) reuses it. There is no second union implementation.
- **Merge-class guard** (`tests/architectural/test_merge_reconciliation_class_guard.py`; Decision Moment `plan.design.merge-class-guard-set`):
  - Keep `decisions` **in** `_NON_DIVERGENT_COORD_RESIDUE_DIRS` (L318-334). The guard hard-asserts `divergent_dirs == {"traces"}` (L355) and requires a `*.md` driver per divergent dir, and `DM-*.md` are ULID-unique one-shot writes.
  - Amend the ruling comment: the ledger is a PRIMARY record that travels with lane branches, and its `index.json` is covered by the `spec-kitty-decision-index` driver.
  - Add an assertion that the `kitty-specs/**/decisions/index.json` driver pattern is registered in root `.gitattributes`, discovered via the `_MERGE_DRIVERS` `config_key`, not a literal. The guard reads `.gitattributes` (`_gitattributes_merge_drivers()`, L161).
- **Hazard.** The planning-recency resolver must skip driver-covered paths (D12, "Merge-driver hazard").

**Rationale.** FR-009b and US4.9. The class guard ruled the ledger single-writer while it was COORD (L320-333). As a PRIMARY record it travels with lane and Mission branches, so concurrent lane additions conflict on `index.json`. The ruling is amended in the same change, so the guard's completeness check stays green.

**Alternatives rejected.**
- Regenerating `index.json` from events after a merge. The events live on COORD, so a PRIMARY-side merge cannot see them.
- Leaving the index without a driver. US4.9 would lose entries under `-X theirs`.

## D14. How doctor reads refs and worktrees

**Decision.** A new module, `src/specify_cli/decisions/fork.py`, owns `detect_decision_forks(repo_root, mission_slug) -> DecisionsForkReport`. Its inputs:
- PRIMARY side: the repository root checkout's Mission dir when present, else `git show <target_branch>:kitty-specs/<dir>/<stream>`.
- COORD side: the coordination worktree dir when present, else `git show <coordination_branch>:...`.

Locations come from the seam: `read_dir(PRIMARY_METADATA)` for the root, `CoordinationWorkspace.worktree_path` and `meta.json`'s `coordination_branch` for the coordination side. Both streams are compared on event-id prefixes, and decision ids are grouped per surface. The prefix/fork comparison **reuses** the pure classifier in `coordination/event_prefix.py` (owned by the seed concern, post-tasks P-M6), so there is no second classifier. The ledger home is checked the same way: `decisions/` in the PRIMARY dir or at the target ref, versus the coordination ref.

Callers:
- `_decisions_doctor._diagnose` (L372). The orphan rule becomes "absent on both surfaces" (L384-401).
- `_repair` (L404). It refuses to drop any entry and prints the reconcile steps when forked. It copies a coordination-only ledger to the PRIMARY dir (additive, via `union_decision_index`) and leaves committing to spec-commit or accept (no auto-commit, per FR-009b).
- `decisions/verify.py::verify` (L104): a new finding `DECISION_LOG_FORKED`.
- The teardown predicate (D15).

**Rationale.** FR-010, FR-010a, FR-011, FR-009c. One detector, so doctor and verify agree. Refs make a fresh clone work without any worktree.

**Alternative rejected.** Putting detection in `_decisions_doctor.py`. That is a CLI module, so verify and teardown would have to import a CLI module or duplicate the logic.

## D15. Teardown refuses to destroy a coordination-only ledger

**Decision.** At the top of `teardown_coordination_topology` (`coordination/teardown.py:222`), before the gate at L283, call `fork.coordination_only_ledger(repo_root, mission_slug)`.
- If entries exist only on the coordination branch, raise `ProjectionTeardownAbort` (L90) with the new code `COORDINATION_LEDGER_UNREPAIRED`. The hint is `spec-kitty doctor decisions --repair`.
- This covers every caller: consolidate abort (`consolidate.py:408`), close/discard (`mission_type.py:1144`), and consolidation (`executor.py:3126`).
- Consolidation additionally refuses in `_pre_mutation_safety_preflight` (`executor.py:3450`), so it fails before mutating.

**Rationale.** This is the operator ruling (`legacy-ledger`). The projection excludes PRIMARY kinds (`bookkeeping_projection.py:481`), so without the refusal the ledger is lost.

## D16. Trigger for the `planning_commit_sha` refresh

**Code fact (brownfield scout).** `refresh_planning_commit=True` is a refresh-only, zero-mutation mode: it returns before `_run_commit_pipeline`. So the automatic refresh cannot be implemented as `refresh = flag or planning_changed`, because that would turn every default finalize into a refresh-only run that skips the normal commit pipeline.

**Decision.** The automatic refresh goes through the **no-flag preserve-decision path**. In `_resolve_preserve_planning_commit_decision` (`mission_finalize.py:2981`), reached from `_preserve_or_capture_planning_commit_sha` (L3017) once execution has begun, the recorded pin is classified with the shared `classify_recorded_pin` (`lanes/planning_commit_classify.py:45`, `PinClass`). Then:

| Recorded pin | Planning paths changed since the pin? | Result |
|---|---|---|
| `ORPHANED` (present, not an ancestor of the tip; #4827) | either | **fail closed before any write, unchanged**. Pinned by `test_issue_4827_repin_orphaned_planning_commit.py::test_plain_finalize_fails_closed_on_orphaned_pin`. |
| `ADVANCED` (ancestor of the tip) | yes | return a resolution with `sha = tip`, `action = "refreshed"`, `previous_sha = recorded`. The new pin rides the normal `_compute_and_write_lanes` write (L3255/L3307) and the normal TASKS_INDEX commit. No separate pin-refresh commit, no refresh-only mode. |
| `ADVANCED` | no | preserve (`action = "preserved"`; US5.2 positive control) |
| `FOREIGN` or `INDETERMINATE` (cannot prove a safe advance) | yes | **warn and continue** (ruling Q6): keep the old pin |

"Planning paths changed" means `git diff --name-only <recorded> <tip> -- <the Mission's PRIMARY planning paths, excluding lanes.json>` is non-empty; the paths are classified via `kind_for_mission_file`.

`--refresh-planning-commit` (L4779-4794, and with `--allow-orphaned`) keeps its existing refresh-only semantics and its existing refusals, which still fail.

**Rationale.** This is the operator ruling (`planning-commit-refresh`): an advanced refresh becomes the default. Riding the existing lanes write keeps the frozen-SHA contract of ADR `2026-07-29-1` (one write, no second commit). #4827's orphan safety is untouched.

**Alternatives rejected.**
- `refresh = flag or planning_changed`: it would skip the normal commit pipeline.
- Refreshing on every finalize: a needless pin churn when nothing changed.

**Operator ruling (plan, Q6), scoped by the #4827 decision.** "Warn and continue" applies only to non-orphan cases where the **automatic** refresh cannot prove a safe advance (`FOREIGN`, `INDETERMINATE`).
- **Behaviour.** Finalize keeps the old pin and exits 0. It prints a warning naming the recorded commit, the candidate commit, and the manual route `spec-kitty agent mission finalize-tasks --refresh-planning-commit`.
- **Orphaned pin.** Still fails closed (#4827).
- **Explicit flag.** An explicit `--refresh-planning-commit` that is refused still fails, as today.
- **JSON.** Finalize gains `planning_commit_refresh: {"status": "refreshed" | "preserved" | "kept_with_warning", "recorded": <sha>, "candidate": <sha>, "pin_class": <PinClass>, "reason": <code | null>}`. An orphan failure is the existing error envelope, not this field.
- **Spec.** Rev 4: US5.3, US5.4, FR-012.

## D17. Implement receipts

**Decision.**
- In `_commit_via_legacy_safe_commit` (`workflow.py:768`), the "State already present at HEAD" arm (L806) records a receipt against `target_branch` with `sha=None` (L807-813), although the transactional emit committed the record on the coordination branch. Replace it with a receipt naming `write_target(STATUS_STATE).ref` and the id of the latest commit on that ref touching the Mission's status log (`git log -1 --format=%H <ref> -- <path>`).
- Every receipt carries a commit id.
- `_print_commit_summary` (L837, loop L856-860) prints the short id.
- The JSON `commits[]` gains `sha` for every entry (additive).

**Rationale.** FR-013. The positive control is the primary-group receipt at L487, which still names the target branch.

## D18. Extending the write-side rederivation gate

**Decision.** Add a third grammar to `tests/architectural/test_no_write_side_rederivation.py`: "COORD write location from a read resolver". Do not add a new gate file (FR-014, P10).

- **Scan scope (the floor):** the census writer functions, as `(rel_path, qualname)` pairs:
  - `decisions/emit.py::_mission_dir`
  - `decisions/service.py::_mission_dir`
  - `agent_tasks_ports.py::RealCoordCommitRouter.feature_write_dir`
  - `tasks_mark_status.py::_ms_resolve_read_dir`
  - `tasks_finalize.py::_ft_apply_writes`
  - `mission_finalize.py::_emit_local_canonical_events`
  - `review/cycle.py::_review_cycle_wp_dir`
  - `retrospective/tracer_writer.py::_local_staging_path`
  - `tasks/issue_matrix.py::scaffold_issue_matrix`
  - `agent/acceptance_verdict.py::_matrix_read_dir`
  - `coordination/status_transition.py::_coord_feature_dir`
  - `coordination/transaction.py::BookkeepingTransaction._acquire_locked`
  - `runtime_bridge.py::_wrap_with_decision_git_log`
  - `accept.py::_coord_status_feature_dir`
  - `retrospect.py::_canonical_events_path`
  - `agent_retrospect.py::_canonical_events_dir`
  - `core/mission_creation.py::_emit_create_events`
  - `consolidation/executor.py::_phase_baseline_and_surface`, `::_run_lane_based_consolidation` (migrated per D21)
  - `cli/commands/materialize.py::_resolve_selected_dir`, `::materialize` (all-Missions loop; migrated per D21)
  - `lanes/recovery.py::reconcile_status`
- **Forbidden tokens** (AST call names) inside those functions:
  - `read_dir(...)` with a COORD-kind argument;
  - `read_dir_for`;
  - `candidate_feature_dir_for_mission`;
  - `resolve_feature_dir_for_mission`;
  - `resolve_status_surface`, `resolve_status_surface_with_anchor`;
  - `coord_read_dir_for`;
  - composing `KITTY_SPECS_DIR` onto a coordination worktree.
- **Floor assertion:** at least 22 scanned functions (the list above), each resolving to a live definition (no stale qualname).
- **Allowlist:** the shrink-only `ContentDescriptor` mechanism (the existing L175 shape) starts **empty**. It gets an independent size cap of 0 under a new `test_no_write_side_rederivation:` key in `tests/architectural/_baselines.yaml`, following the `test_layer_rules` pattern, so adding any entry reds. The operator ruled (plan Q4) that the consolidation executor and `materialize` sites migrate rather than being allowlisted.
- **Red at base:** on the real offenders, at least `decisions/emit.py:88` and `decisions/service.py:246`.
- **Checkout-root guessing (scout X3).** `tests/architectural/test_no_worktree_name_guess.py` explicitly excludes the `.path.parent.parent` class (L474-476, deferred to #2007). The rule that does catch it is grammar 1's `root_walk` in this file (L254), which scans only `_ADOPTED_MODULES` (L87-111). So `_ADOPTED_MODULES` is extended to every `write_dir`/`checkout_root` consumer: `decisions/*`, `events/decision_log.py`, `runtime/next/runtime_bridge*.py`, `review/cycle.py`, `accept.py`, `_decisions_doctor.py`, `consolidation/executor.py`, `materialize.py` and `coordination/commit_router.py`. The P-M3 gate citation points here, not at `test_no_worktree_name_guess.py`.
- **Self-mutation:** plant `read_dir(MissionArtifactKind.STATUS_STATE)` in a synthetic writer, and assert the scan reds.
- **Twin:** an allowlist entry that no longer matches reds.

**Rationale.** It extends the family the charter's gate discipline requires (`architectural-gate-non-vacuity`). The floor is the census.

## D19. End-to-end test

**Decision.** A new file, `tests/integration/test_coord_single_home_workflow.py` (new).
- It is parametrized over `coord` and `lanes_with_coord`, through the production CLI:
  - `spec-kitty agent mission create ... --pr-bound --start-branch <topic>` for `coord`;
  - `--topology lanes_with_coord` for the other.
- It drives create → `decision open`/`resolve` → tracer append → `spec-commit` → `setup-plan` → `finalize-tasks` → `implement WP01` → `move-task` to approved → `accept` → `consolidate`.
- It asserts:
  - no commit in `creation_base..target` (before consolidation) touches a COORD-partition path;
  - exactly one status log;
  - every decision present;
  - a strictly increasing logical clock (`event_lamport`).
- A moved-merge-base variant commits an unrelated file on the target mid-flight and asserts that consolidation succeeds with no `TARGET_BRANCH_CONTENT_CONFLICT`.
- Markers: `integration` (CI-owned per C-006). Locally, run only this file.

## D20. A remote-only coordination branch (fresh clone)

**Decision.** Keep the existing refusal for a remote-only coordination branch: `materialize_coord_surface_for_write` step 3, #4970 parity, raising `COORDINATION_WORKTREE_UNMATERIALIZED` with a recovery hint. Treat "fresh clone" in US2.3 as "local branch present, worktree absent".

**Rationale.** Reconcile, don't override. #4970 decided against auto-creating local tracking branches before a write.

**Operator ruling (plan, Q1).** Keep the refusal with a recovery hint. Materialize-then-write applies when the local branch exists and only the worktree is missing. Spec rev 3 states this in US2.3 and FR-003a.

## D21. Consolidation and `materialize` COORD writers migrate to the accessor

**Operator ruling (plan, Q4).** Migrate them in this Mission, with no allowlist entries. They get their own concern (plan IC-18), because their guard set is the terminus-integrity machinery (#5001), not the planning writers'.

**Sites (verified at `ecb5dd914a`):**
- `consolidation/executor.py:4183`, in `_run_lane_based_consolidation` (L4114, the **unlocked** pre-phase). `feature_dir = seam.read_dir(STATUS_STATE)` becomes `run.feature_dir` (L4332), which feeds the done bookkeeping (`_record_merged_wps_done_for_merge`, L892 → `done_bookkeeping.py:722`), the birth cutover (`status_feature_dir`, L1744/L1821/L4229), and reads (L592, L3090).
- `consolidation/executor.py:825`, in `_phase_baseline_and_surface` (L799, locked; called at L3775). `resolve_status_surface(...)` becomes `run.canonical_events_path` and `canonical_status_path`. It also decides `run.done_marked_before_target` through `is_under_worktrees_segment(...)`.
- `cli/commands/materialize.py:31` (`_resolve_selected_dir`, the `--mission` path) and L103-105 (the all-Missions loop over repository-root dirs). `reducer.materialize(feature_dir)` (`status/reducer.py:405`) writes `status.json` into the Mission dir it reads.

**Decision.**
1. **At L4183**, call `seam.write_dir(STATUS_STATE)`. Keep the existing two `except` arms and their "Merge aborted before any state change" rendering for `CoordinationBranchDeleted` and the remote-only `CoordinationWorktreeUnmaterialized`. Add an arm for `COORD_SEED_FORK_REFUSED`.
   - This point precedes the global merge lock and both pre-mutation captures: `_capture_pre_mutation_coord_checkpoint` (L1064, called at L3748) and `rollback.capture_pre_mutation_snapshot` (L2519).
   - So a seed commit made here is part of the pre-mutation state. It is never rolled back, which is correct (it is a heal, not part of the landing), and the snapshot's coordination tip includes it.
2. **At L825**, stop re-deriving the surface. Set `run.canonical_events_path = run.feature_dir / "status.events.jsonl"` (one authority per run), with one exception: preserve today's completed-Mission answer.
   - `resolve_status_surface` (`for_write=False`) returns the PRIMARY dir when the primary Mission is completed (`surface_resolver.py:1267`, `_primary_mission_is_completed` L1113). That case is a `--resume` after landing.
   - Make it explicit: when the primary Mission is completed, keep today's PRIMARY path and its `done_marked_before_target` value. This is the consolidation projection's sanctioned exception (FR-008); the read is a read of records already projected to the target.
   - Pin this with a characterization test before the change.
3. **`materialize`**: both the `--mission` path and the per-Mission loop resolve the Mission dir via `write_dir(STATUS_STATE)` for coordination-routed Missions. The loop reads each root dir's `meta.json` topology first; `lanes`/`single_branch` dirs are unchanged (C-008).
   - Behaviour change: `spec-kitty materialize` (all Missions) can now materialize, and for pre-fix Missions seed, each coordination-routed Mission's coordination surface. The command help states this.
   - A remote-only coordination branch is reported per Mission in `errors[]`; it never aborts the loop.

**Rationale.** A writer that keeps a read resolver is the defect class FR-014 closes. At base:
- the executor's EMPTY arm writes the done bookkeeping into the repository root checkout's log of a pre-fix Mission;
- `materialize` (all Missions) writes `status.json` beside a stale root log even when the coordination surface is materialized.

Migration removes both legs, and the gate's allowlist can start empty.

**Risks (terminus and consolidation integrity, #5001 machinery).**
- **UNMATERIALIZED behaviour changes for consolidate.** At base, an UNMATERIALIZED surface with a local branch aborts with "Materialize the coordination worktree, then re-run". After the change it materializes, seeds if the surface is EMPTY, and proceeds. `tests/cli/commands/test_merge_status_commit.py::TestUnmaterializedCoordWorktreeMerge::test_lane_based_merge_exits_cleanly_on_unmaterialized_coord_worktree` (L271) pins the old abort and must be re-pinned:
  - local-branch variant: proceeds past the surface phase and the surface is MATERIALIZED;
  - remote-only variant: still aborts with the same message.

  This is a deliberate behaviour change under the ruling, not a stale test.
- **Lock ordering.** The seed takes the status lock in the unlocked pre-phase, before the merge lock, so no merge-lock/status-lock inversion is possible. The locked driver's own status writes re-enter the reentrant status lock as today.
- **`--resume` integrity.** These must stay unaffected:
  - the persisted `pre_mutation_refs` (never recaptured on resume);
  - `pre_mutation_coord_sha` and `pre_interrupt_lane_tips`;
  - `state.reconciliation_passed_for_tip`.

  `write_dir` on a MATERIALIZED surface is side-effect-free, so a resumed run (always MATERIALIZED, or completed per point 2) performs no seed.
- **`done_marked_before_target`.** For a pre-fix EMPTY Mission, this flag flips to the coordination value, because the surface is now under `.worktrees/`. That is the post-fix behaviour every coordination Mission already has. It is covered by the existing done-bookkeeping tests on MATERIALIZED fixtures plus R23.
- **Dry run must stay side-effect-free.** `consolidate --dry-run` must not call `write_dir` (`tests/consolidation/test_dry_run_fails_closed_on_unmaterialized_coord.py`). The forecast path (`consolidation/forecast.py`) keeps its read-only `read_dir` calls; only the real run calls `write_dir`.

**Guards that must stay green.** Run each named file; never the bare directory.
- `tests/consolidation/test_single_rollback_authority.py` (AST-pinned rollback caller set) and `test_rollback_authority.py`
- `tests/consolidation/test_reconciliation.py`, `test_reconciliation_divergent.py`, `test_squash_reconcilers_2709.py`
- `tests/consolidation/test_bookkeeping_projection_seam.py`, `test_issue_2709_projection_union.py`, `test_projection_source_status_fallback_2709.py`
- `tests/consolidation/test_done_bookkeeping_seam.py`, `test_done_bookkeeping_rollback_coherence.py`
- `tests/consolidation/test_coord_deleted_degrade_paths.py`, `test_dry_run_fails_closed_on_unmaterialized_coord.py`, `test_executor_coord_reconcile.py`, `test_coord_teardown_order_3926.py`, `test_issue_4764_terminus_safety.py`
- `tests/consolidation/test_canceled_content_residuals.py` (the strict `xfail`s must stay `xfail`)
- `tests/cli/commands/test_merge_status_commit.py` (with the re-pin above)
- `tests/coordination/test_projection_teardown.py`
- `tests/specify_cli/cli/commands/test_materialize.py`
- `tests/architectural/test_merge_reconciliation_class_guard.py`

**Red-first.** See R22-R24. The MATERIALIZED path is behaviour-preserving, proven by the guards above plus the FR-014 gate; R22 and R24 cover the pre-fix legs that do change.

## D22. `write_dir` absorbs the coordination write gate (single write authority, C-001)

**Problem (brownfield scout X1).** `mission_runtime.assert_coord_write_materialized` (`write_target_degrade.py:157-261`) describes itself as "the single decision locus for S-C (FR-006/#4970)". It **refuses** an UNMATERIALIZED, local-head coordination branch that already carries a committed artifact of the kind (L220-261). `write_dir` **materializes** that same state. After IC-05 every post-fix coordination branch carries content, so the write seam (which consults the gate) and the direct writers (which call `write_dir`) would disagree.

**Decision.** `establish_coord_write_location` becomes the single write-side decision for coordination-routed COORD kinds. `assert_coord_write_materialized` becomes a thin delegate:
- MATERIALIZED / EMPTY: unchanged no-op, except that a MATERIALIZED Mission with a pending seed commit (data-model I-SEED-10) gets its refused seed re-committed with the trailer.
- UNMATERIALIZED with a local head: delegate to `write_dir(kind)`. This materializes, then restores or seeds per D4 and D3. The old "branch already carries the kind" refusal is deliberately removed: that state is the normal post-fix shape.
- UNMATERIALIZED, remote-only: still refuses with `COORDINATION_WORKTREE_UNMATERIALIZED` (ruling Q1).
- PUBLISHED: per D23.

`resolve_write_target_or_degrade(..., terminus_write=True)` and `write_seam.write_artifact` keep calling the gate name, so call sites are unchanged.

The refusal pins of the old gate are **re-pinned deliberately**, as behaviour changes rather than stale tests, with the remote-only refusal kept as the control. They are the tests that assert `COORD_WRITE_SURFACE_UNMATERIALIZED` for a local head carrying content, under `tests/coordination/test_surface_write_gate.py` and `tests/mission_runtime/`.

**Rationale.** There are two write authorities at base. C-001 and DIRECTIVE_044 require one. The accessor is the sanctioned extension, so the older gate folds into it rather than the reverse.

**Alternative rejected.** `write_dir` calls the gate and inherits its refusal. Every post-fix Mission with a removed worktree would then be refused, which contradicts US2.3.

## D23. PUBLISHED (post-consolidation) kinds follow the existing E2 resolution

**Fact.** `REVIEW_CYCLE`, `TRACER_FILE`, `ISSUE_MATRIX` and `ACCEPTANCE_MATRIX` are in `_E2_CONSOLIDATED_ELIGIBLE_KINDS` (`resolution.py:191-199`). After consolidation, `resolve_placement_only` short-circuits them to the target branch (E2 PUBLISHED, L1961-1963).

**Decision.** `write_dir` checks the same E2 PUBLISHED predicate **before** probing coordination state. For a PUBLISHED Mission and an E2-eligible kind it returns `surface="primary"`, the PRIMARY Mission dir, `checkout_root = repository root checkout`, and `establishment=NONE`. It never probes or materializes the coordination worktree, so it can never raise `CoordinationBranchDeleted` or write into a torn-down worktree.

Non-E2 COORD kinds of a PUBLISHED Mission, such as `STATUS_STATE` and `DECISION_LOG`, keep today's post-consolidation behaviour: the completed-Mission handling in D21 point 2, or the existing refusal.

**Rationale.** It reuses the one existing post-consolidation authority, so `write_dir` agrees with `write_target` by construction.

---

## NFR-001 baseline (measured 2026-10-01)

**Setup.**
- CLI: the installed `spec-kitty` (editable install of `fork/spec-kitty` at `ecb5dd914a`, clean `src/`; `--version` prints 4.0.0rc5).
- Fixture: a throwaway repository under `scratchpad/nfr001/`, set up with `git init -b main`, an initial commit, `spec-kitty init . --ai claude --non-interactive`, and a commit.
- Each run copies the template fresh. One warm-up run is discarded, then 5 timed runs.
- Script: `scratchpad/nfr001/bench.sh <topology> <topic|prbound>`.

**Commands.**
- `topic`: `git checkout -b topic; spec-kitty agent mission create bench-m --topology <T> --branch-strategy already-confirmed --json`
- `prbound`: `spec-kitty agent mission create bench-m --topology <T> --pr-bound --start-branch topic --branch-strategy already-confirmed --json`

| Config | Runs (s) | Median (s) |
|--------|----------|-----------|
| coord, topic | 2.686, 2.635, 2.646, 2.691, 2.615 | **2.646** |
| coord, pr-bound + start-branch | 2.642, 2.601, 2.657, 2.638, 2.641 | **2.641** |
| lanes_with_coord, topic | 2.589, 2.633, 2.623, 2.637, 2.681 | **2.633** |
| lanes_with_coord, pr-bound + start-branch | 2.723, 2.610, 2.666, 2.647, 2.605 | **2.647** |

**Reference points.**
- `spec-kitty --version` alone takes 1.408-1.429 s, which is interpreter and import start-up.
- `--topology lanes` create takes 2.626-2.686 s.

**Consequence.** NFR-001's former absolute bound ("under 2 seconds") was not achievable even at the baseline: the median is about 2.64 s, and start-up alone is about 1.42 s.
- **Operator ruling (plan, Q2).** Drop the absolute bound. Coordination create may add at most +1.0 s over the measured base median on the same fixture. Spec rev 3, NFR-001.
- **Budgets after the change:**

  | Config | Budget (median) |
  |--------|-----------------|
  | coord, topic | ≤ 3.646 s |
  | coord, pr-bound | ≤ 3.641 s |
  | lanes_with_coord, topic | ≤ 3.633 s |
  | lanes_with_coord, pr-bound | ≤ 3.647 s |

- **Expected cost.** Eager materialization adds one `git worktree add` and one commit, an estimated 0.15-0.4 s.

## Verification: #2533's implement-claim leg

**Verdict: fixed at `ecb5dd914a`.**

**Evidence.**
- `3599c05990` (2026-08-23, "fix(FIX-M2-08): stop implement-claim's planning precheck comparing PRIMARY artifacts against the coordination branch") is an ancestor of HEAD (`git merge-base --is-ancestor`, exit 0).
- `e4644c2342` (2026-07-15, "fix(#2533): write-side partition-aware planning-artifact commit") is an ancestor of HEAD.
- The code at HEAD:
  - `implement.py:827-849` no longer threads `placement_ref.ref` in as `verbatim_ref`;
  - `implement_cores.py:588` `resolve_planning_artifact_staging` compares PRIMARY files against `HEAD` and COORD residue against the coordination ref (`resolve_precondition_ref`).
- Regression tests pass at HEAD: `tests/specify_cli/cli/commands/test_implement_cores.py::test_dirty_spec_md_still_staged_against_head_on_coord_mission` (L567), `::test_meta_json_on_coord_mission_resolves_to_head` (L606), and the FIX-M2-08 regression (L631). Command: `-k "...head_on_coord_mission or ...resolves_to_head or FIX or dossier"`, 5 passed.

**Still open in #2533.** The issue itself is still OPEN (labels `workflow`, `domain:git`, `priority:P1`). Its remaining live symptom is the split-brain fallback right after a new coordination create: the empty coordination surface. This Mission covers it with FR-002 and FR-003, and FR-016's spec-commit warning reproduction. The issue matrix should record: claim leg fixed by `3599c05990`/`e4644c2342`; create/empty-surface leg covered by this Mission.

## Red-first reproduction list

Each test fails at `ecb5dd914a` through the named pre-existing entry point. All of them share a fixture factory that creates a coordination-routed Mission through `create_mission_core` or the CLI with an explicit topology (IC-02).

| # | Defect | Test (file::name) | Entry point | Assertion red at base |
|---|--------|-------------------|-------------|------------------------|
| R1 | #5440 create | `tests/core/test_mission_create_coord_status_placement.py::test_coord_create_scaffold_commit_keeps_status_off_target_branch` (adopt from `upstream/test/p0-repro-5440` @ `31ea4681f7`, PR #5518) | `create_mission_core` | `git log <base>..<target> -- kitty-specs/<dir>/status.events.jsonl` is empty. At base the scaffold commit carries it (confirmed by bench probe `ff7ad6e`). |
| R1b | #5440 create, coordination side | same file::`test_coord_create_seeds_coordination_branch_and_reads_materialized` | `create_mission_core` + `placement_seam().read_dir(STATUS_STATE)` | `git ls-tree <coord> kitty-specs/<dir>/status.events.jsonl` exists, and the classifier stamp is COORD. At base the branch tip is the pre-create commit (probe: coord at `9f7ce81`). |
| R1c | re-pin | `tests/core/test_mission_creation_decomposition.py::test_scaffold_commit_is_single_commit_excluding_spec_md` (L290) | `create_mission_core` | Re-pin L299 to assert `status.events.jsonl` is NOT in the target scaffold tree for a coordination-routed fixture. First confirm the fixture resolves `coord`: no `origin/HEAD`, so primary detection falls back to the current branch. A `lanes` variant keeps it (C-008). |
| R2 | #5513 router | `tests/coordination/test_commit_router_coord_only_dirty_status_log.py::test_router_never_reports_a_coord_only_dirty_status_log_as_unchanged` (adopt from `upstream/test/p0-repro-5513` @ `251bea520f`, PR #5520) | `commit_for_mission` | `result.status == "committed"` and the coordination tip contains the row. Tighten the refusal branch to require a named reason in `surfaces[*].refused`. At base: `unchanged`/`no_op_already_committed`. |
| R2b | #5513 positive control | same file::`test_clean_coordination_copy_reports_unchanged` | `commit_for_mission` | `unchanged` (green at base; it pins the control) |
| R3 | #5519 repair drop | `tests/decisions/test_decisions_reconciler.py::test_repair_never_drops_entries_on_forked_log` | `run_decisions_reconciliation(repair=True)` via the CLI `doctor decisions --repair` | The index entry count is unchanged and the output names the fork. At base the coordination-surface decisions are removed as orphans (`_decisions_doctor.py:397`). |
| R4 | #5519 clock restart | `tests/specify_cli/decisions/test_service_coord_single_home.py` (new)::`test_decision_tracer_decision_keeps_one_log_and_monotonic_clock` | CLI `agent decision open` → `retrospect tracer append` (or `append_tracer_finding`) → `decision open` | One status log on the coordination surface holds both `DecisionOpened`, and `lamport2 > lamport1`. At base the second lands on coordination with a restarted clock while the first stays in the root checkout. |
| R5 | #5501 spec-commit drop | `tests/specify_cli/cli/commands/test_spec_commit_cmd.py::test_spec_commit_names_every_argument_fate` | CLI `spec-commit` with `spec.md`, `decisions/*`, `traces/*`, `status.events.jsonl` | The JSON `surfaces` names every argument: the ledger is on the target, traces and status on the coordination branch. At base the status log is silently skipped and the ledger is re-routed to coordination. |
| R6 | #2533 warning | `tests/coordination/test_surface_resolver_coord_empty_warning.py::test_no_split_brain_warning_after_new_coord_create` plus control `::test_legacy_empty_coord_still_warns` | CLI create then `spec-commit` (captures the `_COORD_EMPTY_FALLBACK_WARNING` log) | No warning after a post-fix create. At base the surface is EMPTY, so `lanes_with_coord` warns. The legacy-empty control still warns. |
| R7 | accept, root leg | `tests/specify_cli/cli/commands/test_accept_residual_partition.py::test_accept_never_commits_coord_record_from_root_checkout_to_target` | CLI `accept` | No target commit touches `status.events.jsonl`. At base `_commit_primary_residuals` commits it. |
| R8 | accept, coordination leg | same file::`test_accept_commits_coord_only_dirt_on_coordination_branch` | CLI `accept` | The coordination tip carries the row. At base it is skipped or overwritten (L425 join plus the L1038 skip). |
| R9 | accept gate/committer agreement | same file::`test_accept_gate_and_committer_agree_per_path` | `_filter_coordination_residue` vs the router grouping | The same partition for every path in a mixed fixture. Red at base for `decisions/*` under coord. |
| R10 | finalize coordination dirt | `tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py::test_finalize_sees_coord_only_lifecycle_dirt` | CLI `agent mission finalize-tasks` | The coordination tip carries `TasksCompleted`. At base the result is "no changes". |
| R11 | finalize/retrospect masking | same file::`test_finalize_reports_skipped_surface`; `tests/specify_cli/cli/commands/test_retrospect_doctor_surface_4090.py::test_retrospect_reports_each_surface` | CLI | The output names the skipped surface. At base it is masked by `_merge_group_results`. |
| R12 | FF advance | `tests/coordination/test_commit_router.py::test_no_target_advance_for_coordination_routed_mission` | `commit_for_mission(target_branch=...)` with the target an ancestor of the coordination tip | The target ref is unchanged after the commit. At base `_try_advance_ref` fast-forwards it. |
| R13 | ledger partition | `tests/mission_runtime/test_artifact_partition.py::test_decision_ledger_is_primary` | `artifact_home_for(DECISION_LEDGER)` | PRIMARY; at base COORD |
| R14 | verify on fork | `tests/specify_cli/decisions/test_verify_integration.py::test_verify_not_clean_on_forked_log` | CLI `agent decision verify` | Exit 1 with `DECISION_LOG_FORKED`; at base exit 0 |
| R15 | doctor detects fork from refs | `tests/decisions/test_decisions_reconciler.py::test_doctor_reports_fork_from_refs_only` | CLI `doctor decisions --json` in a clone with no coordination worktree | `forked: true` with per-surface decision ids; at base the field is absent and clean |
| R16 | coordination-only ledger | same file::`test_doctor_reports_and_repairs_coord_only_ledger`; `tests/coordination/test_projection_teardown.py::test_teardown_refuses_coord_only_ledger` | CLI doctor; `teardown_coordination_topology` | Reported plus copied; teardown raises `COORDINATION_LEDGER_UNREPAIRED`. At base: not reported, and teardown proceeds. |
| R17 | planning pin | `tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py::test_finalize_refreshes_planning_commit_sha_by_default` (+ control `::test_finalize_keeps_planning_commit_sha_when_unchanged`) | CLI finalize twice, with a planning commit in between, after execution has begun | `lanes.json.planning_commit_sha` equals the new planning commit; at base it is unchanged |
| R18 | receipts | `tests/specify_cli/cli/commands/agent/test_workflow.py::test_implement_receipts_name_branch_containing_sha` (+ target-branch control) | CLI `agent action implement` | Every receipt has a `sha` with `git branch --contains <sha>` ∋ `destination_ref`. At base the "already present" receipt has `sha: null` on the target branch. |
| R19 | gate | `tests/architectural/test_no_write_side_rederivation.py::test_coord_writers_do_not_derive_write_location_from_read_resolver` | AST scan | Red at base on `decisions/emit.py::_mission_dir` and `decisions/service.py::_mission_dir`, plus the planted mutation |
| R20 | divergence model | `tests/specify_cli/cli/commands/test_coordination_doctor.py::test_seeded_coord_branch_not_reported_diverged` (+ `::test_genuinely_diverged_legacy_still_reported`) | CLI `doctor coordination --json` | No `COORDINATION_BRANCH_DIVERGED_VS_TARGET` after a seeded create. Red only after IC-05 lands; at base the branch is not ahead, so this is a forward guard. |
| R21 | index merge | `tests/consolidation/test_decision_index_merge_driver.py` (new)::`test_two_lanes_adding_decisions_merge_without_loss` | `git merge` with the driver config seeded | Both entries present; at base a conflict or a lost entry |
| R22 | consolidation writes the done bookkeeping into the root log of a pre-fix EMPTY Mission (D21) | `tests/consolidation/test_done_bookkeeping_seam.py::test_pre_fix_empty_coord_mission_records_done_on_coordination_surface` | `_run_lane_based_consolidation` (the same entry point as `test_merge_status_commit.py:289`) on a fixture with a local coordination branch, an EMPTY worktree, and root status events | After the run, the `done` events are in the coordination log, the coordination branch carries one seed commit before the merge commits, and the root checkout's log is restored. At base `run.feature_dir` is the root dir (`read_dir` EMPTY → PRIMARY), so the `done` events land in the root log. |
| R23 | consolidation re-pin (D21, ruling Q4) | `tests/cli/commands/test_merge_status_commit.py::TestUnmaterializedCoordWorktreeMerge`: split L271 into `test_local_branch_unmaterialized_coord_is_materialized_before_merge` and `test_remote_only_coord_branch_still_aborts_before_state_change` | `_run_lane_based_consolidation` | The local-branch variant has the surface MATERIALIZED after the surface phase (red at base: exit 1 with "Merge aborted"). The remote-only variant keeps today's assertions (green at base; control). |
| R24 | `materialize` writes `status.json` beside a stale root log (D21) | `tests/specify_cli/cli/commands/test_materialize.py::test_materialize_all_writes_status_json_on_coordination_surface` (+ control `::test_materialize_lanes_mission_unchanged`) | CLI `spec-kitty materialize` (no `--mission`) on a MATERIALIZED coordination Mission whose root copy is stale | `status.json` is written in the coordination Mission dir and reflects the coordination log. At base the loop reduces the root log and writes the root `status.json`. |
| R1d | characterization pin for D21 point 2 | `tests/consolidation/test_executor_coord_reconcile.py::test_completed_mission_resume_keeps_primary_events_path` | `_phase_baseline_and_surface` on a completed-Mission `--resume` fixture | Green at base and after: it pins the completed-Mission PRIMARY answer that the migration must preserve. |

After GREEN, the adopted standalone reproduction files are **folded into the owning modules' test files** (post-tasks R-M8):
- R2 and R2b go into `tests/coordination/test_commit_router.py`;
- R1 and R1b go into `tests/core/test_mission_creation_decomposition.py`;
- the standalone files and their "stays red on main" markers are removed.

The other reproductions (R4, R5 and the rest) are written directly in the owning files named above. None is kept as a standalone regression marker (FR-016).

**Issue-matrix verdicts (analyze G3).** The accept/closeout step fills `issue-matrix.json` from this list, including #2533's **split verdict**: the claim leg is fixed by `3599c05990`/`e4644c2342` (evidence above), and the create/empty-surface remainder is covered by this Mission (FR-002, FR-003, R6).
