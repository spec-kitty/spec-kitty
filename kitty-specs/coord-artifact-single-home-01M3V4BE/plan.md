# Implementation Plan: Coordination artifacts get one durable home

**Branch**: `issue-5440-coord-artifact-single-home` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md) (revision 5)
**Input**: Mission specification from `kitty-specs/coord-artifact-single-home-01M3V4BE/spec.md`

**Note**: Base revision `ecb5dd914a`; product code is unchanged on this branch. Every file:line below was re-verified there. The operator's plan-phase rulings Q1-Q6, the `/spec-kitty.analyze` folds and the WP01-WP11 brownfield-scout decisions are folded in (see `traces/design-decisions.md`). Detail lives in [research.md](research.md) (decisions D1-D23, the NFR-001 baseline, the #2533 verdict, the red-first list), [data-model.md](data-model.md), [contracts/](contracts/) and [quickstart.md](quickstart.md).

## Summary

**The defect.** A coordination-routed Mission's lifecycle records have no single home.
- Create seeds the status log in the repository root checkout and commits it to the target branch (#5440).
- Writers take their write location from read resolvers, which substitute the root checkout while the coordination surface is empty, so the log forks at the first coordination write (#5519, #2533).
- Committers compensate inconsistently and hide per-surface outcomes (#5513, #5501).
- `doctor decisions --repair` drops half of a forked log (#5519, #5023).

**The approach.** Close the defect class at the write side.
1. **One write-location accessor**, `PlacementSeam.write_dir(kind)`, on the existing placement seam (C-001). For COORD kinds of a coordination-routed Mission it owns materialize, seed and refuse. Every COORD writer moves to it; the existing write-side rederivation gate is extended to hold the line (FR-014).
2. **Create materializes and seeds the coordination surface eagerly**, committing the creation records on the coordination branch. A shared predicate redefines the expected coordination-vs-target divergence.
3. **The commit router commits the owning-surface copy**, refusing only for named reasons, and reports a per-surface outcome. One renderer serves its consumers. Accept loses its raw commit; finalize sees coordination dirt; the router's target fast-forward is retired.
4. **The decision ledger moves to the PRIMARY partition.** Every reader that flips is enumerated, and an index merge driver is added. `doctor decisions` gains a ref+worktree fork detector shared with `decision verify` and with teardown.
5. **Smaller fixes:** finalize refreshes `planning_commit_sha` by default; implement receipts carry commit ids.

## Technical Context

**Language/Version**: Python 3.11+ (`pyproject.toml`; the dev venv is 3.11.15)
**Primary Dependencies**: typer, rich, ruamel.yaml (CLI and YAML); pytest, mypy (`--strict` on changed files), ruff (lint, C901 ≤ 15, format); git ≥ 2.38 at runtime
**Storage**: Files in git. Append-only JSONL event logs (`status.events.jsonl`, `decisions.events.jsonl`), JSON and Markdown records under `kitty-specs/<mission>/`, branches and worktrees (target branch, coordination branch `kitty/mission-<slug>-<mid8>`, `.worktrees/`)
**Testing**: Red-first targeted pytest per owning module, through pre-existing entry points (C-005, ADR 2026-07-17-1); research.md lists R1-R24 (plus R1d). Plus the extended architectural gate (`test_no_write_side_rederivation.py`) and the named gate files it implicates, and one end-to-end file (`tests/integration/test_coord_single_home_workflow.py`). No full heavy suites locally (C-006, `NO_FULL_HEAVY_SUITES_IN_MISSION`): never the bare `tests/architectural/`, e2e or `make test-full`. Baseline is `make test-fast` plus each changed module's test directory.
**Target Platform**: Linux, macOS and Windows CLI (POSIX paths in examples; atomic `os.rename` within one filesystem)
**Project Type**: Single project (layered Python packages `kernel ← charter ← {glossary, runtime, mission_runtime} ← specify_cli`)
**Performance Goals**: NFR-001. Baseline at `ecb5dd914a`: median of 5 warm coordination-routed creates = **2.646 s** (`coord`), **2.633 s** (`lanes_with_coord`), **2.641-2.647 s** (pr-bound + start-branch). Budget (ruling Q2, Decision Moment `plan.nfr.create-latency`): at most +1.0 s over the measured base median on the same fixture, so ≤ 3.633-3.647 s per config. There is no absolute bound (CLI start-up alone is ≈ 1.42 s). This is an accepted charter deviation; see the Charter Check and Complexity Tracking.
**Constraints**: C-001 (one sanctioned seam extension, no second classifier or commit mechanism); C-002 (read-side EMPTY fallback kept); C-003 (no automatic log merge); C-004 (fix forward); C-008 (`lanes`/`single_branch` unchanged); `mission_runtime` outbound ledger must not grow (the `coordination` edge already exists); `resolution.py` stays undecomposed (only touched functions are extracted)
**Scale/Scope**: About 37 source files across `mission_runtime`, `specify_cli/{coordination,core,decisions,cli/commands,acceptance,consolidation,review,retrospective,tasks,events}`, `runtime/next`; 25 red-first reproductions (R1-R24 plus R1d); 6 linked issues

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Loaded: `.kittify/charter/charter.md` (v1.4.0), `charter context --action plan`, profile `architect-alphonso`, procedure `mission-tracer-files`.

| Charter rule | Status | How |
|--------------|--------|-----|
| Single canonical authority (DIRECTIVE_044) | PASS | One accessor on the existing `PlacementSeam`. The seed sits behind it. One fork detector (`decisions/fork.py`) serves doctor, verify and teardown. One outcome renderer. One divergence predicate serves create and doctor. Accept's raw commit and `_try_advance_ref` are removed. |
| Architectural alignment (DIRECTIVE_001) | PASS | The accessor delegates over the existing `coordination` ledger edge (`test_layer_rules.py`, cap 10 unchanged). No new layer crossing. |
| DDD + tiered rigour | PASS | Core logic (seed prefix rule, fork detection, outcome contract) gets property-style and fixture tests; CLI glue gets entry-point tests. |
| ATDD / red-first (C-005, Standing Order 4) | PASS | R1-R24 plus R1d through pre-existing entry points. Adopted reds come from PR #5518 and PR #5520; after GREEN they are folded into the owning module test files (R-M8). |
| Campsite cleaning first (Standing Order 2, DIRECTIVE_025) | PASS | IC-01 precedes the functional ICs and extracts helpers from touched functions at C901 ≥ 12. |
| Non-vacuous gate (Standing Order 5, DIRECTIVE_043) | PASS | IC-15 extends the existing gate. Floor ≥ 22 writer functions, red at base on real offenders, self-mutation, shrink-only allowlist. |
| No full heavy suites in mission (Standing Order / internal pack) | PASS | The test policy is in Technical Context and quickstart §Test policy. |
| Terminology canon (Mission; name the sense of "primary") | PASS | Artifacts say "PRIMARY partition", "repository root checkout" and "target branch" explicitly. |
| Reconcile change-scope tensions | PASS | The writer census bounds the file set. Per ruling Q4, the consolidation executor and `materialize` writers are migrated in their own concern (IC-18), so the gate's allowlist starts empty. The extension beyond the planning writers is directly connected to the goal (FR-003, FR-014), with a one-line rationale in research D21. |
| Mission tracer files (Standing Order 3) | PASS | `traces/` seeded. |
| Fix forward, no history rewrite | PASS | Seed restores only uncommitted root copies. Ledger repair is additive. |
| Performance and Scale ("CLI operations must complete in < 2 seconds") | **DEVIATION (accepted)** | NFR-001 bounds coordination create at +1.0 s over the measured base median (≈ 2.64 s, ≤ 3.65 s), with no absolute bound. The base already exceeds 2 s, and CLI start-up alone is ≈ 1.42 s. Accepted by operator ruling Q2 (Decision Moment `plan.nfr.create-latency`). Recorded under Complexity Tracking. |

Post-design re-check: PASS, with one accepted deviation (Performance and Scale), justified under Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/coord-artifact-single-home-01M3V4BE/
├── spec.md, squad-post-spec.md, decisions/   # specify outputs
├── plan.md              # this file
├── research.md          # Phase 0: decisions D1-D23, NFR-001 baseline, #2533 verdict, red-first list (R1-R24, R1d)
├── data-model.md        # Phase 1: value objects, invariants, lifecycle
├── quickstart.md        # Phase 1: reproduce at base / verify after fix
├── contracts/
│   ├── write-location-accessor.md
│   ├── seed.md
│   ├── commit-outcome.md
│   └── doctor-decisions-fork-report.md
├── traces/              # tooling-friction.md, approach.md, design-decisions.md
└── tasks.md             # Phase 2 (/spec-kitty.tasks), not created here
```

### Source Code (repository root)

```
src/mission_runtime/
├── resolution.py                 # PlacementSeam.write_dir (beside write_target L2304 / read_dir L2318)
├── write_location.py             # NEW: WriteLocation (incl. checkout_root), Establishment
├── __init__.py                   # export WriteLocation/Establishment (+ _PUBLIC_SURFACE in test_mission_runtime_surface.py)
├── write_target_degrade.py       # assert_coord_write_materialized becomes a thin delegate to write_dir (research D22)
└── artifacts.py                  # DECISION_LEDGER -> _PRIMARY_ARTIFACT_KINDS; stale #3928 comments
src/specify_cli/coordination/
├── coord_seed.py                 # NEW: establish_coord_write_location, seed_coord_surface, COORD_SEED_TRAILER (the one trailer constant; imports mission_runtime root only)
├── event_prefix.py               # NEW: pure prefix/fork classifier (event_ids_of, classify_prefix); reused by decisions/fork.py
├── coherence.py                  # is_coord_residue_churn: topology=None resolves the stored topology from the slug (research D12, Decision Moment plan.design.topology-less-callers)
├── surface_resolver.py           # materialize_coord_surface_for_write (step 1); loud EMPTY for post-fix (L1430-1450)
├── commit_router.py              # owning-surface commit (L991, L436/457), surfaces, retire _try_advance_ref (L560, L1302)
├── commit_outcome.py             # NEW: PathFate, SurfaceOutcome, render/payload
├── status_transition.py          # _coord_feature_dir (L400) -> write_dir
├── transaction.py                # _acquire_locked feature_dir (L490) -> write_dir
├── write_seam.py                 # WriteSeamResult.surfaces (L548)
└── teardown.py                   # COORDINATION_LEDGER_UNREPAIRED refusal (L222)
src/specify_cli/core/mission_creation.py      # eager seed, scaffold paths, rollback (L683, L1138, L1429, L1564, L1722)
src/specify_cli/missions/_create.py           # expected-divergence predicate; ensure_coordination_branch (L195/L254)
src/specify_cli/decisions/{emit.py,service.py,verify.py,fork.py(NEW),index_fold.py}
src/specify_cli/events/decision_log.py; src/runtime/next/runtime_bridge.py (L283-375)
src/specify_cli/agent_tasks_ports.py (L354-400); src/specify_cli/review/cycle.py (L173-306, L712)
src/specify_cli/retrospective/tracer_writer.py (L199, L298); src/specify_cli/tasks/issue_matrix.py (L448-518)
src/specify_cli/acceptance/{__init__.py (L411/440, L1791), matrix.py (L469-546)}
src/specify_cli/cli/commands/
├── accept.py (L111, L154/193, L369-445)      ├── spec_commit_cmd.py (L70-95, L155, L214-285)
├── agent/mission_finalize.py (L2266, L2874, L3542, L3585-3746, L4758-4794)
├── agent/tasks_finalize.py (L250/444)        ├── agent/tasks_mark_status.py (L209-231, L279)
├── agent/acceptance_verdict.py (L89-98)      ├── agent/workflow.py (L768-813, L837-860)
├── agent/mission_setup_plan.py (L237/892/951) ├── agent/mission_record_analysis.py (L374)
├── retrospect.py (L109, L315), agent_retrospect.py (L198)
├── _decisions_doctor.py (L131-156, L372-404, L529), decision.py (L567)
├── _coordination_doctor.py (L633-680), merge_driver.py, init.py (L67-74, L455)
src/specify_cli/{git/report_transaction.py (L199), orchestrator_api/commands.py (L3018)}
src/specify_cli/lanes/consolidation.py (_MERGE_DRIVERS L59-123); src/specify_cli/consolidation/{drivers.py (+ pure union_decision_index), executor.py (L825, L2036, L3450, L4183), planning_recency.py (skip driver-covered paths)}
src/specify_cli/cli/commands/materialize.py (L26-37, L103-105); src/specify_cli/lanes/recovery.py (L766-807)
src/specify_cli/upgrade/migrations/m_<next>_decision_index_merge_driver.py   # NEW
.gitattributes                                                              # decisions/index.json driver line

tests/  (owning-module homes; NEW marked)
├── core/test_mission_create_coord_status_placement.py (adopted, PR #5518; folded into test_mission_creation_decomposition.py after GREEN, R-M8), test_mission_creation_decomposition.py (re-pin)
├── coordination/test_commit_router_coord_only_dirty_status_log.py (adopted, PR #5520; folded into test_commit_router.py after GREEN, R-M8), test_commit_router.py, test_event_prefix.py (NEW),
│   test_surface_resolver_coord_empty_warning.py, test_projection_teardown.py, test_coord_seed.py (NEW)
├── mission_runtime/test_artifact_partition.py, test_placement_seam_write_dir.py (NEW)
├── decisions/test_decisions_reconciler.py; specify_cli/decisions/{test_verify_integration.py, test_service_coord_single_home.py (NEW)}
├── specify_cli/cli/commands/{test_spec_commit_cmd.py, test_accept_residual_partition.py, test_coordination_doctor.py, test_materialize.py}
├── cli/commands/test_merge_status_commit.py (R23 re-pin); consolidation/{test_done_bookkeeping_seam.py, test_executor_coord_reconcile.py}
├── specify_cli/cli/commands/agent/{test_finalize_tasks_commit_surface.py, test_workflow.py}
├── consolidation/test_decision_index_merge_driver.py (NEW)
├── integration/test_coord_single_home_workflow.py (NEW, FR-015)
└── architectural/{test_no_write_side_rederivation.py (extended), test_write_surface_placement_guard.py,
                  test_merge_reconciliation_class_guard.py}
docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md, 2026-09-24-2-coord-read-fail-closed.md (amend)
docs/adr/4.x/<date>-decision-ledger-primary-partition.md (NEW short ADR: reversal of the #3928 ledger intent)
docs/architecture/artifact-placement-seam.md (write_dir section; stale line citations)
```

**Structure Decision**: Single project. New code goes into existing packages. The new modules (`write_location.py`, `coord_seed.py`, `event_prefix.py`, `commit_outcome.py`, `decisions/fork.py`) keep the large modules from growing: `resolution.py` is 3006 lines, `surface_resolver.py` 1454 and `commit_router.py` 1348.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Coordination create exceeds the charter's "< 2 s" CLI budget (NFR-001: ≤ base median + 1.0 s, ≈ 3.65 s) | The base median already measures ≈ 2.64 s (CLI start-up ≈ 1.42 s). Eager materialization adds one `git worktree add` and one commit (≈ 0.15-0.4 s) to give the coordination surface a home from birth (FR-001/002). Accepted by operator ruling Q2 (Decision Moment `plan.nfr.create-latency`). | Keeping "< 2 s" would require start-up work outside this Mission's scope. Deferring materialization to the first write (lazy seed) reintroduces the empty-surface window this Mission closes, and it was rejected by decision `specify.design.seed-mechanism`. |

## Implementation Concern Map

> **Note**: Implementation concerns are NOT work packages and are NOT executable units.
> `/spec-kitty.tasks` translates these into executable WPs — one concern may become
> multiple WPs; multiple small concerns may merge into one WP. Do not label concerns
> with WP-style IDs or sequencing language.

### IC-01 — Campsite-clean the functions about to change

- **Purpose**: Behaviour-preserving extraction first, so no touched function crosses C901 15 (NFR-004). Measured with `ruff --select C901` at `ecb5dd914a`:

  | Function | Location | C901 | Touched by |
  |----------|----------|------|------------|
  | `spec_commit_command` | `spec_commit_cmd.py:155` | **15** | IC-07 |
  | `record_report_transaction` | `git/report_transaction.py:130` | **15** | IC-07 |
  | `finalize_tasks` | `mission_finalize.py:4758` | **14** | IC-09, IC-13 |
  | `_ft_apply_writes` | `tasks_finalize.py:250` | **14** | IC-04 |
  | `_stage_artifacts_in_coord_worktree` | `commit_router.py:991` | **13** | IC-06 |
  | `record_analysis` | `mission_record_analysis.py:225` | **13** | ~~not touched~~ **touched (scout correction)**: the commit at L374 is inside `record_analysis` itself (L355-391); `_maybe_auto_commit` is in `retrospect.py:294`. Its suppress-and-commit block is extracted first, then rendered (IC-07) |
  | `_commit_planning_pin_refresh_locked` | `mission_finalize.py:2807` | **15** | IC-07, IC-13 (only the result interpretation is extracted; the single commit call stays, per `test_finalize_refresh_pin_authority.py`) |
  | `resolve_status_surface_with_anchor` | `surface_resolver.py:1192` | **12** | IC-03 |
  | `setup_plan` | `mission_setup_plan.py:1225` | 11 | |
  | `_wrap_with_decision_git_log` | `runtime_bridge.py:283` | 11 | |
  | `_build_create_meta` | `mission_creation.py:1233` | 10 | |
  | `verify` | `decisions/verify.py:104` | 10 | |
  | `commit_workflow_change` | `workflow_executor.py:209` | 10 | |

  `resolution.py` has nothing ≥ 10 (`resolve_placement_only` 8, `_classify_artifact_surface` 5), so it needs no extraction.
- **Relevant requirements**: NFR-004, NFR-005, Charter Standing Order 2
- **Affected surfaces**: the functions listed above; their existing tests
- **Sequencing/depends-on**: none
- **Risks**: Extraction must be behaviour-identical: same tests green before and after, with no assertion edits. Keep each extraction inside the file the later IC touches, to limit lane conflicts.

### IC-02 — Red-first reproduction harness and adopted reproductions

- **Purpose**: Land the failing-first reproductions (research R1-R24 plus R1d) through pre-existing entry points. Share one fixture factory for "coordination-routed Mission via the production create path", parametrized over `coord` and `lanes_with_coord`.
- **Relevant requirements**: FR-016, C-005, SC-005
- **Affected surfaces**:
  - adopt `tests/core/test_mission_create_coord_status_placement.py` (`upstream/test/p0-repro-5440` @ `31ea4681f7`) and `tests/coordination/test_commit_router_coord_only_dirty_status_log.py` (`upstream/test/p0-repro-5513` @ `251bea520f`), with `git cherry-pick -x`. Tighten #5520's refusal branch so that commit is required unless a named reason is present.
  - a fixture factory in the nearest `conftest.py` of `tests/coordination/`, reused by the other modules through an importable helper.
- **Sequencing/depends-on**: IC-01
- **Risks**: Each reproduction lands with, or immediately before, the IC that turns it green; never `xfail`.
  - R1c (`test_scaffold_commit_is_single_commit_excluding_spec_md`, L290/299) pins today's defective tree, so it is re-pinned in IC-05.
  - ~~**Implementer check (S9).**~~ **Superseded (scout correction):** the empirical check is unnecessary. `create_mission_core` defaults to `topology=MissionTopology.COORD` (`mission_creation.py:770`); the `origin/HEAD` fallback only affects the CLI default. Re-pin the L299 assertion to "not in the target tree", and add an explicit `lanes` sibling that keeps the original assertion (C-008).
  - R20 is a forward guard, not red at base.

### IC-03 — Write-location accessor on the placement seam (owns materialize + seed)

- **Purpose**: Give every COORD writer one answer to "where do I write". Make that answer the coordination surface in every coordination-worktree state, or a loud refusal.
- **Relevant requirements**: FR-003, FR-003a, FR-004, FR-004a, FR-004b, C-001, C-002
- **Affected surfaces**:
  - `src/mission_runtime/resolution.py`: `PlacementSeam.write_dir(kind) -> WriteLocation`, added at L2304-2376 (contract `contracts/write-location-accessor.md`).
  - `src/mission_runtime/write_location.py` (new). `WriteLocation` includes `checkout_root` (post-tasks P-M3); consumers never guess `.path.parent.parent`.
  - `src/mission_runtime/__init__.py` `__all__` and `_PUBLIC_SURFACE` (`tests/architectural/test_mission_runtime_surface.py:50`) gain the accessor symbols. `coord_seed.py` imports `mission_runtime` only from the package root (MR-1 L244, MR-2 L342).
  - `src/specify_cli/coordination/coord_seed.py` (new). `establish_coord_write_location` calls `materialize_coord_surface_for_write` (`surface_resolver.py:903`) as step 1, then `seed_coord_surface` (contract `contracts/seed.md`).
  - `src/specify_cli/coordination/event_prefix.py` (new): the pure prefix/fork classifier, reused by IC-12 (P-M6).
  - `mission_runtime/write_target_degrade.py::assert_coord_write_materialized` (L157-261) becomes a thin delegate to `write_dir`: one write authority (research D22). Its local-head refusal pins are re-pinned deliberately; the remote-only refusal stays.
  - PUBLISHED (post-consolidation) Missions: E2-eligible kinds resolve PRIMARY before any coordination probe (research D23).
  - Post-fix discriminator: the `Spec-Kitty-Coordination-Seed: <mission_id>` commit trailer (one constant `COORD_SEED_TRAILER` in `coord_seed.py`, written by the seed commit and by create's commit; after a refused seed commit, the next seed attempt re-commits with the trailer, with no router change; Decision Moment `plan.design.seed-trailer-ownership`), with the over-matching pre-fix fixture `test_surface_resolver_solo_coord_primary.py:107-146` as the negative case. The EMPTY restore copies COORD-kind paths only. `coord_branch_has_committed_artifact` (`surface_resolver.py:786`) is fixed to compose the real Mission dir (research D4).
  - `surface_resolver.py:1430-1450`: the `EMPTY` warning goes loud for post-fix Missions in both coordination topologies.
  - Error codes: new `COORD_SEED_FORK_REFUSED`; new `error_code="STATUS_LOCK_HELD"` on `FeatureStatusLockTimeoutError` (`status/locking.py:59`).
  - New tests: `tests/coordination/test_coord_seed.py` and `tests/mission_runtime/test_placement_seam_write_dir.py` (state × kind matrix, prefix and fork, idempotence, atomic rename, root restoration, lock reentrancy, `write_dir`/`write_target` agreement property).
- **How it reconciles with existing seams** (research D1):
  - `resolve_placement_only` and `write_target` stay ref-only and side-effect-free.
  - `read_dir` keeps the read fallback.
  - `resolve_status_surface_with_anchor(for_write=True)` is unchanged and documented as not a write location. It is reached from `resolve_placement_only` (`resolution.py:1974-1982`), so it must stay pure.
  - `status_transition._coord_feature_dir` (L400) and `transaction.py:490` are retired in IC-04.
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**:
  - Lock: the root is `owned.owned_root` when owned, the key is `coord_mission_dir_name`, and the timeout is bounded (`BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS`; the default `-1` makes `STATUS_LOCK_HELD` unreachable; data-model I-SEED-1a).
  - Ordering: the workspace lock may be taken under the status lock, never the reverse (I-SEED-2). The seed commit runs `commit_for_mission`, whose `_coord_status_locks` (`commit_router.py:586`) reuses the same reentrant key.
  - Absorbing the gate changes write-seam behaviour for a local head that already carries content: it now materializes instead of refusing. That is intended (D22) and covered by re-pins.
  - The owned-checkout arm (`_owned_read_dir_for_kind`, `resolution.py:1272`) raises on `EMPTY` today; `write_dir` for owned coordination Missions must use the owned workspace variant (`runtime_bridge.py:363`).
  - A remote-only branch keeps refusing with a recovery hint (research D20, ruling Q1).
  - A post-fix EMPTY surface is restored from the coordination branch tip with a loud warning before the write (research D4, ruling Q3).
  - The pre-fix seed commits once on the coordination branch before the triggering write (research D5, ruling Q5).

### IC-04 — Migrate every COORD writer to the accessor

- **Purpose**: Remove the defect class: no COORD writer derives its write location from a read resolver or composes the coordination dir itself.
- **Relevant requirements**: FR-003, US2.1-2.3, the "Transient staging" edge case
- **Affected surfaces** (census at `ecb5dd914a`):

  | Writer family | Site | Today |
  |---------------|------|-------|
  | Decision events (status log) | `decisions/emit.py:75/88` (`_mission_dir`) | `read_dir(STATUS_STATE)` |
  | | `decisions/service.py:231/246` (`_mission_dir`); drop the direct `materialize_coord_surface_for_write` calls at L501/L696 | |
  | Decision event stream | `runtime/next/runtime_bridge.py:283-375` (`_wrap_with_decision_git_log`; worktree pick L359-363) | — |
  | | `events/decision_log.py:118-120` composes the log path; it takes the dir from `write_dir(DECISION_LOG)` instead | |
  | Status transitions (move-task, mark-status) | `agent_tasks_ports.py:354-362` (`feature_write_dir`) | kind-blind `resolve_feature_dir_for_mission` |
  | | `tasks_mark_status.py::_ms_emit_subtask_state` (L359; non-owned arm L406-413, flat `emit_inner_state_changed(st.status_dir, ...)`, commits nothing) | `resolve_status_surface(...).parent` (`_ms_resolve_read_dir`, L209-231) |
  | Transactional status path | `coordination/status_transition.py:241-286, 400-405` (`_resolve_fallback_coord_worktree`, `_coord_feature_dir`) | composed |
  | | `coordination/transaction.py:490` (`_acquire_locked`) | composed |
  | Finalize bootstrap | `tasks_finalize.py:444`; `mission_finalize.py:2266` (`_emit_local_canonical_events` writes to `planning_dir`) | |
  | Tracer | `retrospective/tracer_writer.py:199-213` (`_local_staging_path`) | `candidate_feature_dir_for_mission`; stage-in-root then copy |
  | Review cycle | `review/cycle.py:173-306` | writers use the PRIMARY `WORK_PACKAGE_TASK` dir then copy at commit (L712); they write at `write_dir(REVIEW_CYCLE)` instead |
  | Issue matrix | `tasks/issue_matrix.py:448-518` | `coord_read_dir_for(...) or feature_dir` |
  | Acceptance matrix | `agent/acceptance_verdict.py:89-98` → `acceptance/matrix.py:469-546` | |
  | Accept birth cutover | `accept.py:154/193` (`_coord_status_feature_dir`) | |
  | Retrospective events | `retrospect.py:109`; `agent_retrospect.py:198` | split: reads keep the resolver, appends use `write_dir` |

  | Lanes recovery | `lanes/recovery.py:766/785` (`reconcile_status`) | kind-blind `resolve_feature_dir_for_mission` feeding `emit_status_transition_transactional` |

  The consolidation executor and `materialize` writers are migrated in IC-18 (ruling Q4), not allowlisted.
- **Sequencing/depends-on**: IC-03
- **Risks**:
  - Stage-and-copy writers (tracer, matrices, review cycle) must leave no root residue (edge case "Transient staging").
  - `DecisionGitLog` composes `<slug>` while the transaction composes `<slug>-<mid8>` (`_transaction_dir_name`); both must agree with `write_dir`.
  - Shares `decisions/` and `review/cycle.py` with IC-07 (consumer render) and IC-11.
  - **Acceptance-matrix lost update (#4858/#4887).** In `locked_reread_splice_and_write` (`acceptance/matrix.py:546`), `write_dir` is resolved **once, before** the lock, and passed in. It is never resolved, or split across surfaces, inside the locked re-read/splice/write, so the read and the write use the same file.
  - **Review-cycle readers move with the writers.** Flip `_review_cycle_wp_dir`'s default `kind` from `WORK_PACKAGE_TASK` to `REVIEW_CYCLE` (`review/cycle.py:173`). Readers (which all read PRIMARY today) and writers then resolve the same location. The read side uses `read_dir(REVIEW_CYCLE)` and the write side `write_dir(REVIEW_CYCLE)`. Existing kind-flip and read-leniency tests are updated deliberately.
  - Consumers take `WriteLocation.checkout_root`; the `root_walk` grammar's `_ADOPTED_MODULES` scope is extended to cover them (research D18).

### IC-05 — Create materializes and seeds; the coordination-vs-target model

- **Purpose**: The coordination branch carries the creation records from birth; the target branch never does.
- **Relevant requirements**: FR-001, FR-002, FR-002a, FR-002b, US1.1-1.6
- **Affected surfaces**:
  - `core/mission_creation.py`, in `_create_mission_core_impl` (L1722):
    - after `_build_create_meta` (L1894, branch cut at L1302) and the re-target (L1923), call `write_dir(STATUS_STATE)`;
    - `_emit_create_events` (L1429; L1484, L1535) emits into the returned dir;
    - commit on the coordination branch via `commit_for_mission(kind=STATUS_STATE)`;
    - drop `status.events.jsonl` from `scaffold_paths` (L1168-1173) and L1201;
    - the seed is outside the `_BOOTSTRAP_META_COMMIT_SKIPS` suppression (L69-73, L1178, L1601, L1642);
    - `_restore_git_state_after_failed_create` (L683) tears down the coordination worktree and branch **this create** made, identified by slug plus mid8. It handles `CoordinationWorkspace.teardown`'s dirty-worktree refusal (`DestructiveOpRefused`, `workspace.py:363-369`) with a path-scoped forced removal of the create-owned worktree, deletes the branch only if this create minted it, and prunes worktree metadata (research D6).
    - The create seed commit carries the `Spec-Kitty-Coordination-Seed: <mission_id>` trailer (D4), written through the one shared constant `COORD_SEED_TRAILER` owned by `coord_seed.py` (Decision Moment `plan.design.seed-trailer-ownership`).
  - `missions/_create.py`: an `is_expected_coordination_divergence(...)` predicate (research D6), used by `ensure_coordination_branch` (L195, raise at L254) and by `_coordination_doctor._coord_branch_stale_vs_target_finding` (L642; code L635).
  - Tests: R1, R1b, R1c, R20; protected-target create and rollback-after-seed tests in `tests/core/`.
- **Sequencing/depends-on**: IC-03 (accessor), IC-06 (the router must commit coordination paths in place), IC-10 (no target fast-forward)
- **Risks**:
  - NFR-001 budget: one extra `git worktree add` plus one commit. Re-measure with `scratchpad/nfr001/bench.sh`.
  - Lane-conflict hotspot: `mission_creation.py` has only this IC; `_coordination_doctor.py` is shared with nothing else.
  - US1 fixtures on the default `--pr-bound --start-branch` path must protect the primary branch; on an unprotected primary it resolves `lanes` (spec rev 4, US1 precondition).

### IC-06 — Commit router commits the owning-surface copy, with named refusals

- **Purpose**: "Unchanged" means unchanged. A COORD record passed by its root path is judged and committed on its coordination copy.
- **Relevant requirements**: FR-006, US3.1-3.2, SC-003
- **Affected surfaces**: `coordination/commit_router.py`:
  - `_stage_artifacts_in_coord_worktree` (L991): the STATUS_STATE skip at L1038-1039 becomes translation via `write_dir`, extended to DECISION_LOG.
  - `_classify_no_commit_paths` (L436): the primary-only dirt check at L457 (`_paths_uncommitted_in_primary`, L1263) becomes an owning-surface dirt check.
  - Lock timeout handling (L639-640) maps to `STATUS_LOCK_HELD`. `COORDINATION_WORKTREE_UNMATERIALIZED` (remote-only) and `COORD_SEED_FORK_REFUSED` from `write_dir` surface as named refusals (spec FR-006, US3.1).
  - Exports the router's per-path partition decision as a public predicate, e.g. `partition_for_mission_path(...)`, which is the same function its grouping uses (P-M5). IC-08's gate calls it.
  - The split path (L314-327) forwards `owned`.
  - Tests: R2, R2b; `tests/coordination/test_commit_router.py`, `tests/specify_cli/coordination/test_commit_router_partition*.py`.
- **Sequencing/depends-on**: IC-03
- **Risks**: Shares `commit_router.py` with IC-07 and IC-10, so the three must run in one lane or strictly in sequence. Never copy a root log over the coordination log.

### IC-07 — Per-surface commit-outcome contract, one renderer, every consumer migrated

- **Purpose**: A skip or refusal on one surface is never masked by the caller-surface fields.
- **Relevant requirements**: FR-007, FR-007a, FR-007b (output half), SC-003
- **Affected surfaces**:
  - `coordination/commit_outcome.py` (new); `CommitRouterResult.surfaces` (`commit_router.py:174-205`); `_merge_group_results` (L802-844) populates it.
  - Wrappers: `WriteSeamResult` (`write_seam.py:548`), `CommitArtifactResult` (`agent_tasks_ports.py:108, 389/400`).
  - Consumers (research D8):

    | Consumer | Site(s) |
    |----------|---------|
    | setup-plan | `mission_setup_plan.py:237, 892, 951` |
    | record-analysis | `mission_record_analysis.py:374` |
    | report transaction | `git/report_transaction.py:199` |
    | orchestrator API | `orchestrator_api/commands.py:3018` |
    | acceptance | `acceptance/__init__.py:1791, 1822`; `acceptance/matrix.py:524` |
    | issue matrix, tracer | `tasks/issue_matrix.py:404`; `retrospective/tracer_writer.py:298` |
    | accept | `accept.py:426` |
    | finalize | `mission_finalize.py:2874, 3585-3746` |
    | retrospect | `retrospect.py:315` |
    | spec-commit | `spec_commit_cmd.py:70-95, 214-285` (with the per-argument `arguments[]` of FR-007a) |
    | tasks ports | `review/cycle.py:712`, `tasks_map_requirements.py:668` (mark-status renders nothing: its live write path commits nothing, and the `tasks_mark_status.py:279` `_ms_commit` shim is dead) |
    | tracer-append CLI | `cli/commands/agent/tracer_append.py:135-163` (hand-rendered today) |

  - Contract: `contracts/commit-outcome.md`. Tests: R5, R11, plus a consumer-list pin test.
- **Sequencing/depends-on**: IC-06
- **Risks**:
  - The widest file fan-out, which conflicts with IC-04, IC-08, IC-09 and IC-13 on `mission_finalize.py`, `accept.py`, `review/cycle.py` and `tracer_writer.py`. Sequence it before them, or give the finalize leg to one lane.
  - JSON changes must be additive only.

### IC-08 — Accept: both residual legs through the router, gate and committer agree

- **Purpose**: Remove accept's raw commit and route both legs by partition.
- **Relevant requirements**: FR-005, US3.5-3.7, FR-009 (accept half)
- **Affected surfaces**:
  - `cli/commands/accept.py`:
    - remove `_commit_primary_residuals` (L369-402);
    - fix `_commit_coord_residuals` (L405-442), including the L425 root-join;
    - `_commit_residual_acceptance_artifacts` (L445) forwards `owned`;
    - one `commit_for_mission` call over both legs' dirty paths.
  - `acceptance/__init__.py::_filter_coordination_residue` (L411, L440) calls the router's public partition predicate (P-M5), with no new classifier.
  - Tests: R7, R8, R9 in `test_accept_residual_partition.py`.
- **Sequencing/depends-on**: IC-06, IC-07, IC-11 (the ledger becomes real work for the gate)
- **Risks**: A behaviour change for operators: uncommitted ledger files now get committed by accept (intended, FR-009). Root-checkout COORD residue is reported, not committed.

### IC-09 — Finalize sees coordination-only dirt

- **Purpose**: Finalize must not judge coordination-only lifecycle records as "no changes".
- **Relevant requirements**: FR-007b, US3.8
- **Affected surfaces**:
  - `mission_finalize.py::_resolve_finalize_commit_candidates` (L3542; porcelain at L3571-3577): add the coordination-worktree porcelain for the COORD candidates, following `_refresh_worktree_status_findings` (L2586).
  - The finalize lifecycle writes from IC-04.
  - Tests: R10, R11.
- **Sequencing/depends-on**: IC-04, IC-07
- **Risks**: Shares `mission_finalize.py` with IC-04, IC-07 and IC-13, so give it one lane.

### IC-10 — Retire the router's target-branch fast-forward

- **Purpose**: Seeding must not let COORD records ride onto the target branch by fast-forward.
- **Relevant requirements**: FR-008
- **Affected surfaces**:
  - `commit_router.py`: delete L560-561 and `_try_advance_ref` (L1302-1342). Keep the `target_branch` parameter (used at L283/L290) and update its docstring (L259).
  - `spec_commit_cmd.py:166-170`: help text.
  - Not touched: consolidation's projection (`bookkeeping_projection.py:487`) and `git/ref_advance.py:493`.
  - Test: R12.
- **Sequencing/depends-on**: none (it can land first in the `commit_router.py` lane)
- **Risks**: Callers that pass `target_branch` (finalize L3667, setup-plan L244/899/958, write seam L556, orchestrator L3025, report transaction L206, spec-commit L225) lose a best-effort side effect that was meant to be inert. `tests/coordination/test_commit_router_fail_loud.py:320` patches `_try_advance_ref` and must drop that patch.

### IC-11 — Decision ledger reclassified to the PRIMARY partition, readers flipped, index merge driver

- **Purpose**: The ledger's classification matches where it is written and read, and lane integration never loses an index entry.
- **Relevant requirements**: FR-009, FR-009a, FR-009b, US4.7-4.9
- **Affected surfaces**:
  - `mission_runtime/artifacts.py`: move `DECISION_LEDGER` from L194-213 to L158-186; rewrite the comments at L108-117, L209-211, L280-287.
  - Every reader in research D12, each with a focused test in its module, including the scout additions: `commit_router.py:697/839/915/1193`, `surface_authority.py:232`, `_read_path_resolver.py:1446`, `resolution.py` sites, `workflow.py:393`, `acceptance/__init__.py:1219/1269`, `consolidation/planning_recency.py`.
  - **C-008 design rule** (research D12; Decision Moment `plan.design.topology-less-callers`): one fix point, the predicate. When `topology is None` and the Mission slug is known, `is_coord_residue_churn` (and `is_toolchain_generated_churn`, which consults it) in `coherence.py` resolves the Mission's stored topology.
    - `lanes` and `single_branch` Missions keep today's verdict at every caller (C-008), pinned by a characterization test.
    - Coordination Missions get the PRIMARY ledger rule at **every** caller, including move-task, implement and auto-rebase: an uncommitted ledger is real work, not residue.
    - A caller that passes neither topology nor slug keeps the base verdict, and is listed.
    - There are no per-caller topology patches and no compatibility set. Every flipped reader gets a coordination fixture and a `lanes`-unchanged control.
  - **Committers** (Decision Moment `plan.scope.ledger-committers`): spec-commit and accept only. setup-plan and finalize-tasks are unchanged.
  - **Merge-driver hazard:** `planning_recency._is_primary_planning_path` skips paths covered by a registered `_MERGE_DRIVERS` pattern, so `lanes/consolidation.py:748-750`'s target-favouring `git merge-file` never overwrites the index driver's union.
  - Pure `union_decision_index(ours, theirs)` in `consolidation/drivers.py`, which the driver wraps and IC-12's repair reuses (P-M6).
  - The merge driver `spec-kitty-decision-index`:
    - `lanes/consolidation.py` `_MERGE_DRIVERS` (L59-123);
    - `consolidation/drivers.py` `MERGE_DRIVER_BODIES` (L1117-1126);
    - `cli/commands/merge_driver.py`;
    - `init.py` (L67-74, L455);
    - `.gitattributes`;
    - a new upgrade migration modelled on `m_3_2_6_decisions_event_log_merge_driver.py`.
  - Gate updates: `test_write_surface_placement_guard.py` (L12, L344-358). In `test_merge_reconciliation_class_guard.py` (Decision Moment `plan.design.merge-class-guard-set`), `decisions` **stays** in `_NON_DIVERGENT_COORD_RESIDUE_DIRS`: the guard hard-asserts `divergent_dirs == {"traces"}`, and `DM-*.md` are ULID-unique one-shot writes. The ruling text at L318-334 is amended (the dir is PRIMARY; `index.json` is covered by the `spec-kitty-decision-index` driver). A new assertion requires the `decisions/index.json` driver pattern to be registered in root `.gitattributes`, discovered via the `_MERGE_DRIVERS` `config_key` (research D13).
  - Tests: R13, R21, the FR-009a ratchet (ledger writes and reads stay PRIMARY: `decisions/service.py:255-279`, `_decisions_doctor.py:146-156`).
- **Sequencing/depends-on**: IC-06 (router grouping); before IC-08 and IC-12
- **Risks**:
  - The broadest behaviour flip (about 20 reader sites). The consolidation dirty gate now refuses uncommitted ledger files instead of resetting them, and its message must name `accept`/`spec-commit`.
  - The pre-fix coordination-only ledger is excluded from the projection (`bookkeeping_projection.py:481`), which is why IC-12's teardown refusal must land in the same release.
  - Editing a migration triggers the migration-registry tests; run `tests/upgrade/` for the new migration.
  - Without the planning-recency skip, consolidation silently drops lane-added index entries whenever the target's `index.json` is newer. A dedicated test covers it.
  - Resolving the stored topology widens coordination-Mission behaviour at move-task, implement and auto-rebase: ledger dirt there is now real work. Each gets a coordination-Mission test (Decision Moment `plan.design.topology-less-callers`).

### IC-12 — `doctor decisions` fork detection, honest verify, non-destructive repair, pre-fix ledger repair, teardown refusal

- **Purpose**: Diagnose forks from refs and worktrees on both decision-event streams, never drop a decision, heal pre-fix coordination-only ledgers, and protect them from teardown.
- **Relevant requirements**: FR-009c, FR-010, FR-010a, FR-011, US4.1-4.6, SC-004, NFR-002
- **Affected surfaces**:
  - `decisions/fork.py` (new): `detect_decision_forks`, `coordination_only_ledger`. It **reuses** `coordination/event_prefix.py` for the prefix/fork classification and `union_decision_index` for the coordination-only-ledger repair, with no second implementation (P-M6).
  - `_decisions_doctor.py`:
    - `_diagnose` (L372; orphan rule L384-401);
    - `_repair` (L404);
    - `run_decisions_reconciliation` (L529; repair gate L572, exit L589).
  - `decisions/verify.py::verify` (L104): `DECISION_LOG_FORKED`.
  - `coordination/teardown.py::teardown_coordination_topology` (L222, before L283): `COORDINATION_LEDGER_UNREPAIRED` via `ProjectionTeardownAbort` (L90).
  - `consolidation/executor.py::_pre_mutation_safety_preflight` (L3450).
  - Contract: `contracts/doctor-decisions-fork-report.md`. Tests: R3, R14, R15, R16 over the four NFR-002 fixtures.
- **Sequencing/depends-on**: IC-11
- **Risks**:
  - The detector must be read-only (no materialization) so it works in a fresh clone.
  - The pre-mutation refusal in `executor.py` is the only edit there (locality); its test is targeted at that preflight.

### IC-13 — Finalize refreshes `planning_commit_sha` by default

- **Purpose**: Drift checks compare against the commit holding the finalized planning artefacts.
- **Relevant requirements**: FR-012, US5
- **Affected surfaces**:
  - The automatic refresh goes through the **no-flag preserve-decision path**, `_resolve_preserve_planning_commit_decision` (L2981), not `refresh = flag or planning_changed`: `refresh_planning_commit=True` is a refresh-only zero-mutation mode that returns before `_run_commit_pipeline`. Per `classify_recorded_pin`:

    | Pin class | Planning changed | Result |
    |-----------|------------------|--------|
    | `ORPHANED` | either | fail closed (#4827, unchanged) |
    | `ADVANCED` | yes | refresh to the tip, riding the normal lanes write and TASKS_INDEX commit |
    | `ADVANCED` | no | preserve |
    | `FOREIGN` / `INDETERMINATE` | yes | warn and continue (ruling Q6) |

    Full table in research D16.
  - `--refresh-planning-commit` keeps its existing semantics and refusals.
  - New JSON field `planning_commit_refresh` (contracts/commit-outcome.md).
  - Tests: R17, the unchanged control, a non-orphan warn-and-continue scenario (US5.3), and `test_issue_4827_repin_orphaned_planning_commit.py::test_plain_finalize_fails_closed_on_orphaned_pin`, which stays green (US5.4).
- **Sequencing/depends-on**: IC-01 (`finalize_tasks` at 14), IC-09 (same file)
- **Risks**: The #4827 orphan fail-closed and the `--allow-orphaned` safety stay. The warn-and-continue arm must never cover an orphaned pin, nor a refusal under an explicit flag.

### IC-14 — Implement receipts name the branch that holds each commit

- **Purpose**: Every receipt line carries a commit id contained in the branch it names.
- **Relevant requirements**: FR-013, US6
- **Affected surfaces**: `cli/commands/agent/workflow.py`:
  - `_commit_via_legacy_safe_commit` (L768): the "already present" receipt (L806-813) names `write_target(STATUS_STATE).ref` and the last commit touching the status log, not `target_branch` with `sha=None`;
  - `_print_commit_summary` (L837, loop L856-860) prints the short id.
  - Tests: R18 plus a target-branch positive control.
- **Sequencing/depends-on**: none (independent file)
- **Risks**: The JSON `commits[]` stays additive.

### IC-15 — Extend the write-side rederivation gate to COORD write locations

- **Purpose**: Close the defect class by construction (FR-014, Standing Order 5).
- **Relevant requirements**: FR-014, SC-005
- **Affected surfaces**: `tests/architectural/test_no_write_side_rederivation.py`:
  - a third grammar scoped to the census writer functions (research D18), including the IC-18 sites and `lanes/recovery.py::reconcile_status`;
  - forbidden read-resolver calls;
  - a floor of at least 22 live functions;
  - a shrink-only `ContentDescriptor` allowlist (pattern at L175) that starts **empty** (ruling Q4), with a new size cap of 0 under a `test_no_write_side_rederivation:` key in `tests/architectural/_baselines.yaml`;
  - a planted-mutation bite test (pattern at L318);
  - a stale-entry twin (pattern at L428);
  - `_ADOPTED_MODULES` (L87-111) is extended to every `write_dir`/`checkout_root` consumer, so grammar 1's `root_walk` rule (L254) catches `.path.parent.parent` guessing. `test_no_worktree_name_guess.py` excludes that class (L474-476), so it is not the P-M3 gate (scout X3).
- **Sequencing/depends-on**: written red early, next to IC-04 (it must be red at base on `decisions/emit.py:88` and `decisions/service.py:246`); green only when IC-04 **and** IC-18 complete
- **Risks**: Prove red at base by running the extended gate against `ecb5dd914a` source (`PYTHONPATH` at a base worktree) and record the output in the PR. A gate-unmask cannot self-validate.

### IC-16 — End-to-end coordination workflow invariant

- **Purpose**: Prove the single-home invariant across the whole lifecycle, including a moved merge base.
- **Relevant requirements**: FR-015, SC-001, SC-002
- **Affected surfaces**: `tests/integration/test_coord_single_home_workflow.py` (new):
  - parametrized over `coord` (`--pr-bound --start-branch`) and `lanes_with_coord` (`--topology`);
  - drives create → decision → tracer → spec-commit → setup-plan → finalize → implement → move-task → accept → consolidate;
  - linear and moved-merge-base variants.
- **Sequencing/depends-on**: IC-03 through IC-12, and IC-18
- **Risks**:
  - This is the only e2e file: run it alone, never the e2e directory (C-006).
  - Integration tests run in CI nightly, not per PR; record the local run in the PR.

### IC-17 — Decision records and seam documentation

- **Purpose**: The architecture documentation states shipped behaviour (FR-017).
- **Relevant requirements**: FR-017
- **Affected surfaces**:
  - `docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md`: a new amendment section stating that writes never substitute the repository root checkout, the reads' `EMPTY` fallback is kept, and post-fix `EMPTY` is loud in both topologies.
  - `docs/adr/3.x/2026-09-24-2-coord-read-fail-closed.md` (L80-85, L117-120): note the write-side accessor.
  - `docs/architecture/artifact-placement-seam.md`:
    - a `write_dir` section beside L88-89;
    - fix the stale line citations (for example `PlacementSeam :1373` should be L2261, and `resolve_placement_only :1241` should be L1827);
    - update the partition table for `DECISION_LEDGER`.
  - The `artifacts.py` comments (done in IC-11), and the stale `PlacementSeam.read_dir`/`resolve_artifact_surface`/`ResolvedSurface` docstrings that still say UNMATERIALIZED resolves to primary (`resolution.py` L2338-2343, L2442-2443, L2672-2673).
  - The `CoordState.EMPTY` contract text (`missions/_read_path_resolver.py:259-260`, "never a silent primary fallback") contradicts the kept non-owned read fallback. Reword it to "read: loud declared PRIMARY fallback (C-002); write: seed via `write_dir`".
  - A **new short ADR in `docs/adr/4.x/`** records the reversal of the #3928 ledger intent: the decision ledger moves to the PRIMARY partition, decision events stay COORD, and the committers are spec-commit and accept. It is its own ADR rather than an amendment buried in an unrelated 3.x ADR (analyze C5).
- **Sequencing/depends-on**: IC-03, IC-11, IC-12
- **Risks**: Docs need `updated:` freshness dates (Divio and freshness doctrine). Run the terminology guard `tests/architectural/test_no_legacy_terminology.py` (pre-push rule).

### IC-18 — Consolidation and `materialize` COORD writers move to the accessor

- **Purpose**: Ruling Q4. The consolidation executor's status writes and `materialize`'s `status.json` stop deriving their write location from read resolvers, so the FR-014 gate needs no allowlist. This is a separate concern because its risk and guard set are the terminus-integrity machinery (#5001), not the planning writers'.
- **Relevant requirements**: FR-003, FR-014, US2.9, NFR-002, C-008
- **Affected surfaces** (research D21):
  - `consolidation/executor.py:4183` (`_run_lane_based_consolidation`, unlocked pre-phase): `read_dir(STATUS_STATE)` becomes `write_dir(STATUS_STATE)`. Keep the "Merge aborted before any state change" arms for a deleted branch and a remote-only branch, and add a `COORD_SEED_FORK_REFUSED` arm. This runs before the merge lock and before both pre-mutation captures (L3748 → L1064, L2519), so a seed is part of the pre-mutation state and never rolled back.
  - `consolidation/executor.py:825` (`_phase_baseline_and_surface`): set `canonical_events_path` from `run.feature_dir` instead of `resolve_status_surface`, except for the completed-Mission `--resume` case. That case keeps today's PRIMARY answer and `done_marked_before_target`, pinned first by characterization test R1d.
  - `cli/commands/materialize.py:26-37` (`--mission`) and L103-105 (all-Missions loop): coordination-routed Missions resolve the Mission dir via `write_dir(STATUS_STATE)`. `lanes`/`single_branch` dirs are unchanged. A remote-only branch is reported per Mission in `errors[]`. The help text states that the command may materialize or seed coordination surfaces.
  - Tests: R22, R23 (re-pin of `tests/cli/commands/test_merge_status_commit.py:271`), R24, R1d.
- **Sequencing/depends-on**: IC-03 (accessor), IC-12 (same file, `executor.py::_pre_mutation_safety_preflight`). It lands before IC-15 turns green and before IC-16.
- **Risks**:
  - **Deliberate behaviour change.** Consolidation on an UNMATERIALIZED surface with a local branch now materializes and proceeds instead of aborting (R23 re-pin). `consolidate --dry-run` must stay side-effect-free: the forecast keeps its `read_dir` calls (`test_dry_run_fails_closed_on_unmaterialized_coord.py`).
  - **`--resume` integrity.** The persisted `pre_mutation_refs`, `pre_mutation_coord_sha`, `pre_interrupt_lane_tips` and `reconciliation_passed_for_tip` must be untouched. A resumed run is MATERIALIZED or completed, so `write_dir` has no side effects there; a pending seed commit (data-model I-SEED-10) would already have been retried by the original run's unlocked pre-phase.
  - **Guards that must stay green** (run each named file, never the directory; full list in research D21):
    - `tests/consolidation/test_single_rollback_authority.py`, `test_rollback_authority.py`
    - `test_reconciliation.py`, `test_reconciliation_divergent.py`, `test_squash_reconcilers_2709.py`
    - `test_bookkeeping_projection_seam.py`, `test_issue_2709_projection_union.py`, `test_projection_source_status_fallback_2709.py`
    - `test_done_bookkeeping_seam.py`, `test_done_bookkeeping_rollback_coherence.py`
    - `test_coord_deleted_degrade_paths.py`, `test_executor_coord_reconcile.py`, `test_coord_teardown_order_3926.py`, `test_issue_4764_terminus_safety.py`
    - `test_canceled_content_residuals.py` (the strict `xfail`s stay `xfail`)
    - `tests/cli/commands/test_merge_status_commit.py`, `tests/coordination/test_projection_teardown.py`, `tests/specify_cli/cli/commands/test_materialize.py`
    - `tests/architectural/test_merge_reconciliation_class_guard.py`
  - **`materialize` all-Missions cost.** The all-Missions loop may now create worktrees for every coordination-routed Mission. Each one is a single `git worktree add`, done once.

### Shared-file (lane-conflict) map

| File | ICs | Advice |
|------|-----|--------|
| `coordination/commit_router.py` | 01, 06, 07, 10 (+ 03 via the seed commit) | one lane, in the order 10 → 06 → 07 |
| `cli/commands/agent/mission_finalize.py` | 04, 07, 09, 13 | one lane, or strict sequence |
| `cli/commands/accept.py`, `acceptance/__init__.py` | 04, 07, 08, 11 | 08 after 07 and 11 |
| `coordination/surface_resolver.py` | 01, 03 | same lane |
| `mission_runtime/resolution.py` | 03, 17 (docstrings) | 17 last |
| `mission_runtime/artifacts.py` | 11 | — |
| `decisions/*`, `review/cycle.py`, `retrospective/tracer_writer.py`, `tasks/issue_matrix.py` | 04, 07, 12 | 04 before 07 |
| `spec_commit_cmd.py` | 01, 07, 10 | 01 → 10 → 07 |
| `consolidation/executor.py` | 11 (test only), 12 (preflight), 18 (L825, L4183) | 12 and 18 in one lane, with 12 first |
| `cli/commands/materialize.py` | 18 | — |
| `tests/architectural/test_no_write_side_rederivation.py` | 15 | green only after 04 and 18 |

### Closeout note: issue-matrix verdicts

The accept/closeout step fills `issue-matrix.json` verdicts for #5440, #5513, #5519, #2533, #5501 and #5023 from research's red-first list (analyze G3). #2533 gets a **split verdict**: its claim leg is fixed by `3599c05990`/`e4644c2342` (verified in research), and its create/empty-surface remainder is covered by this Mission (FR-002, FR-003, R6).
