# Post-tasks adversarial squad: findings and dispositions

- **Procedure:** `adversarial-squad-deployment`, point-cut **post-tasks**.
- **Squad:** two profile-loaded lenses, read-only, against `tasks.md` and the 22 WP prompts, as written before this fold.
  - **reviewer-renata** (fidelity: does the decomposition deliver every FR, US and scenario): verdict **READY-WITH-FOLDS**.
  - **paula-patterns** (sequencing, ownership, boundary leaks): verdict **READY-WITH-FOLDS**.
- **Blockers:** none.
- **Outcome:** every finding was folded into `tasks.md` and the WP prompts; none was deferred.
- **Validation:** after the folds, `spec-kitty agent mission finalize-tasks --validate-only` passes with 18 lanes, no lane cycle and no ownership warnings. `map-requirements` reports 28/28 functional requirements mapped.

## Structural deltas (summary)

| Change | Why |
|---|---|
| T002/T003/T004 moved WP01 → WP13/WP14/WP15 (each WP's tidy-first first commit). WP01 keeps T001/T005/T006/T007 | P-m7: frees WP13/14/15 from lane A. Lanes went from 16 to 18 with no cycle |
| New dependencies: WP08 → WP19, WP09 → WP07, WP17 → WP09, WP19 → WP02 | R-M3, P-M1, P-M4, P-m6 |
| New subtask T119 (WP21) | R-M1 |
| New owned files: WP03 `coordination/event_prefix.py` (+ test); WP07 `test_coord_read_seam_callers.py`; WP08 `workflow.py`, `workflow_cores.py`, `workflow_executor.py`, `test_analysis_report_rehome.py`, a new reject→fix-mode test; WP09 six `DecisionGitLog` caller test files; WP10 `tracer_append.py` (+ test); WP12 `test_artifact_partition_mapping.py`, `test_coherence_integrity.py`; WP15 `test_finalize_extracted_helpers.py` | R-M2, R-M3, P-M1, P-M6, P-m3, R-m5, P-m7 |
| Named post-consolidation fold recorded in `tasks.md`: retire the router's legacy root-staging copy | P-M2 (it cannot be a WP without a lane cycle) |

## reviewer-renata (fidelity)

| ID | Severity | Finding (short) | Disposition | Where |
|----|----------|-----------------|-------------|-------|
| R-M1 | MAJOR | US4.8 / FR-009b fresh-clone durability is not delivered by any WP | accepted. New subtask T119: a post-fix Mission opens a decision, commits it via spec-commit/setup-plan, then `git clone`; `decision verify` and `doctor decisions` must find every decision id. An extra assertion checks that setup-plan or finalize commits an uncommitted ledger on the target. FR-009b mapped to WP21 | WP21 T119, DoD; tasks.md WP21 |
| R-M2 | MAJOR | `tracer_append.py:135-163` hand-renders caller-surface fields (masking) | accepted. WP10 owns it and renders through `commit_outcome_payload` / `render_commit_outcome`, with a new test. WP20 adds it to the consumer-pin floor. "Report rather than edit" removed | WP10 T055, surface; WP20 T110, DoD |
| R-M3 | MAJOR | WP08 reject→fix-mode readers are only "verified or reported" | changed. A CLI-level reject-then-fix-mode test is now a **blocking** DoD item. WP08 owns `workflow.py`, `workflow_cores.py` and `workflow_executor.py`, so it fixes readers there. `workflow.py` is shared with WP19, so WP08 depends on WP19 and runs in its lane | WP08 T044 step 6, DoD, surface; frontmatter |
| R-M4 | MAJOR | The WP13/14/15 red-first fixture premise is false at their lane base (create does not seed yet) | accepted. WP02 gains `make_coord_mission(..., materialized=True)`, built explicitly with git and asserting MATERIALIZED through the production probe (WP02 cannot depend on WP04, which would be a cycle). WP13/14/15 assert their preconditions before invoking the CLI. No WP13 → WP06 edge was added | WP02 T009; WP13 T069, WP14 T074, WP15 T079 |
| R-M5 | MAJOR | No integrated re-run of the Mission's new tests on the post-WP06 tree | accepted. WP20 runs every new test file by name (35 files, plus the two fold destinations), with counts recorded | WP20 surface, DoD |
| R-M6 | MAJOR | WP16 red reasons are not derived from its real lane base | accepted. Per-path red reasons are re-derived on the WP01–05, WP11, WP12 base and recorded first. R9 now targets paths that still disagree on that base (for example `traces/*`), because `decisions/*` already agree after WP12 | WP16 T085 |
| R-M7 | MAJOR | `ensure_coordination_branch` is not driven by any test | accepted. Two tests: an expected-divergence existing branch is returned without raising, and a genuinely diverged branch still raises | WP06 T034, DoD |
| R-M8 | MAJOR | FR-016 relocation of the adopted reproductions is missing | accepted. After GREEN, R2/R2b fold into `tests/coordination/test_commit_router.py` and R1/R1b into `tests/core/test_mission_creation_decomposition.py`. The adopted standalone files and their "stays red on main" markers are removed | WP05 DoD, WP06 DoD, WP20 surface note |
| R-m1 | MINOR | WP17 R14 uses one fork fixture | accepted. Parametrized over fork fixtures (a), (b) and (c) | WP17 T090 |
| R-m2 | MINOR | WP16 does not prove each leg is load-bearing | accepted. A one-time local revert of each half (raw commit makes R7 red; the L425 root-join makes R8 red) is recorded in the activity log | WP16 T086 |
| R-m3 | MINOR | The WP07 move-task matrix lacks a post-fix EMPTY row | accepted. New row: remove the coordination Mission dir, run move-task, assert the warning, the restore from the branch tip and no root write | WP07 T037 |
| R-m4 | MINOR | The real default path (protected primary, `--pr-bound`, no `--topology`) is not exercised | accepted. Added as a parametrization asserting `meta.topology == coord` plus US1.1/US1.4 | WP06 T030 |
| R-m5 | MINOR | The legacy `DecisionGitLog` composer is kept as an optional fallback | changed. `mission_dir` is required, the legacy composer is deleted, and the six test callers are migrated (now owned by WP09) | WP09 T051; frontmatter |
| R-m6 | MINOR | SC-001 history probe could be vacuous | accepted. A planted COORD-path commit on the target in a throwaway run must turn the probe red; recorded | WP21 T114 |
| R-m7 | MINOR | T004 wording omits `_commit_planning_pin_refresh_locked`; `_print_acceptance_result` (C901 13) is unwatched | accepted. T004 wording fixed (now in WP15). WP16 quality gates watch `_print_acceptance_result` | tasks.md T004; WP16 quality gates |
| R-m8 | MINOR | R12 could pass vacuously | accepted. Precondition: a base-shaped advance does move the target (clean checkout, target an ancestor of the coordination tip) | WP05 T023 |

## paula-patterns (sequencing)

| ID | Severity | Finding (short) | Disposition | Where |
|----|----------|-----------------|-------------|-------|
| P-M1 | MAJOR | `test_coord_read_seam_callers.py` is flipped concurrently by WP07 and WP09; `test_commit_router.py` imports `_coord_feature_dir`, which WP07 deletes | accepted. WP07 owns and re-pins the file, and WP09 depends on WP07 (no lane cycle). WP09 also runs `test_decision_fresh_coord_5113.py` by name. WP07 declares the out-of-map edit to `test_commit_router.py` (≈L953, ≈L1012) after WP05, with rationale | WP07 T038, surface; WP09 context, surface; tasks.md lane notes |
| P-M2 | MAJOR | Owning-surface judgement only covers STATUS_STATE/DECISION_LOG; the legacy `shutil.copy2` root-staging copy has no retirement | accepted. The judgement extends to all COORD kinds, including the `COORD_RECORD_IN_ROOT_CHECKOUT` skip, with a test per kind. Retiring the legacy copy is recorded in tasks.md as a named post-consolidation fold, because as a WP it would create a lane cycle. WP20's gate module carries a pointer | WP05 T027, T028; tasks.md; WP20 T110 |
| P-M3 | MAJOR | Consumers derive the checkout root by guessing (`.path.parent.parent`) | accepted. `WriteLocation.checkout_root` added (WP03 defines and populates it, WP04 populates PRIMARY). WP07, WP09, WP16 and WP18 consume it. `test_no_worktree_name_guess.py` becomes a named gate for WP03, WP07, WP09 and WP17 | WP03 T012, surface; WP04 T018; WP07 T038; WP09 T051; WP16 T089; WP18 T099; WP17 T091 |
| P-M4 | MAJOR | `decisions.events.jsonl` dir-name mismatch (`<slug>` vs `coord_mission_dir_name`) | accepted. WP09 either proves no reachable shape differs (pinned test) or folds the legacy stream once under the seed lock with the WP03 classifier. WP17 depends on WP09 and composes names only via `lanes.branch_naming` | WP09 T051; WP17 T091; frontmatter |
| P-M5 | MAJOR | WP16 T088 risks a new `_is_coordination_owned()` classifier | accepted. WP05 exports the router's per-path partition predicate as a public helper, and WP16's gate calls it | WP05 T025, DoD; WP16 T088 |
| P-M6 | MAJOR | WP17 could re-implement the prefix/fork classifier and the index union | accepted. WP03 puts the pure classifier in `coordination/event_prefix.py` (owned, tested), and WP17 must reuse it. WP11 exposes a pure `union_decision_index(ours, theirs)` that the merge driver and WP17's repair both use | WP03 T013; WP11 T060; WP17 T091, T094 |
| P-m1 | MINOR | The WP17 targeted surface misses the consolidation guards; T096 touches unowned callers | accepted. WP18's T102 guard list is copied into WP17's surface. Caller rendering in `consolidate.py`/`mission_type.py` is limited to verification and reporting | WP17 surface, T096 |
| P-m2 | MINOR | The WP05 risk text inverts the I-SEED-2 lock order | accepted. Now reads: status → workspace is permitted; workspace → status is forbidden | WP05 risks |
| P-m3 | MINOR | WP12/WP08 re-pins not declared in owned_files; wrong `test_coherence.py` name | accepted. `test_artifact_partition_mapping.py` and `test_coherence_integrity.py` added to WP12 (the name is fixed), and `test_analysis_report_rehome.py` added to WP08 | WP12 T066, frontmatter; WP08 frontmatter, DoD |
| P-m5 | MINOR | Cross-lane fixture semantics are unstated | accepted. One line in each writer and consumer WP (WP02, WP07–WP10, WP13–WP16, WP18): pre-fix assertions use `make_prefix_coord_mission`, and `make_coord_mission` only for shape-agnostic invariants or `materialized=True` | those WPs' Context & Constraints |
| P-m6 | MINOR | WP19 hand-rolls its fixture | accepted. WP19 depends on WP02 and uses the factory | WP19 T103; frontmatter; tasks.md |
| P-m7 | MINOR | Lane A serializes WP13/14/15 because of WP01's extractions | accepted (condition met). T002/T003/T004 moved to WP13/WP14/WP15 as tidy-first first commits. validate-only shows no new cycle and clean ownership; lanes went from 16 to 18. Subtask ids keep their global numbers, so T002–T004 appear out of numeric order in those WPs, which avoids a global renumber that would risk corrupting quoted foreign T-ids | WP01, WP13, WP14, WP15; tasks.md |

## Tooling friction noted

- `spec-kitty agent tasks map-requirements` rewrites the WP frontmatter and drops the `agent`, `assignee` and `shell_pid` keys. They were restored after this fold. The mutating `finalize-tasks` may drop them again, so re-check `agent: claude` per canonical step 8a after it runs.

## Analyze + brownfield scout folds (round 3)

**Inputs**:
- `analysis-report.md` (verdict BLOCKED: 2 high, 6 medium, 11 low);
- the brownfield scout notes, copied into the Mission as `research/brownfield-scout-wp01-11.md` and `research/brownfield-scout-wp12-22.md`;
- the orchestrator's operator decisions.

**Scope**: tasks.md and the WP prompts only. The architect folds the design docs (spec, plan, research, data-model, contracts) in parallel, so findings that live only there are marked "design docs (architect)".

**Mechanics**:
- Every WP gained a scout pointer in Context & Constraints and a **"Binding corrections — analyze + brownfield scout (round 3)"** section that overrides conflicting text.
- The tracer and failure-reporting duties were added to every WP's Quality gates.
- Direct contradictions were also fixed inline.

**Validation**: `finalize-tasks --validate-only` passes with 16 lanes, no lane cycle, no ownership warnings and 28/28 functional requirements mapped.

### Structural deltas

| Change | Why |
|---|---|
| New dependencies: WP10 → WP07, WP16 → WP10 | single owner of `test_no_read_side_bypass.py` (WP07); single owner of `write_seam.py` (WP10) |
| Lanes 18 → 16: WP07, WP09, WP17 and WP18 now share one lane (WP09 co-owns `test_coord_read_seam_callers.py` with WP07 and `decision.py` with WP17, both dependency-ordered) | scout ownership gaps (L198 re-pin; `decision.py:217` arms) |
| Owned-files additions: WP03 (`mission_runtime/__init__.py`, `test_mission_runtime_surface.py`, `write_target_degrade.py` plus 2 refusal-pin tests); WP05 (`surface_authority.py`); WP06 (2 stale create pins); WP07 (`test_no_read_side_bypass.py`); WP08 (`tasks_verdict_persistence.py`, 3 stale pins, untrusted-path inventory); WP09 (`decision.py`, `test_coord_read_seam_callers.py`); WP10 (`issue_verdict.py`, `gates_core.py`); WP11 (`cli/commands/__init__.py`, `_completion_manifest.json`, golden case, 2 count-pin tests); WP12 (`planning_recency.py` plus test, `coherence.py`, new topology-less-callers test); WP16 (`test_accept_clean_tree.py`, `test_accept_decomposition.py`); WP17 (`mission_type.py`, 2 pins); WP22 (new 4.x ADR, the 4.x index, 3 `docs/api` pages) | operator decisions and scout X4 |
| Requirement refs: FR-017 added to WP04 and WP12; C-008 added to WP12 | analyze G2; the operator's WP12 topology-less audit |
| tasks.md: red-evidence table, scout pointer, Closeout items section | analyze C2, C3, U2, G3 |

### Operator decisions

| ID | Item | Disposition | Where |
|----|------|-------------|-------|
| OD-G1 | FR-009b committers narrowed to spec-commit and accept only | accepted. T119 step 2 now asserts the ledger commit point through spec-commit and accept only; the "setup-plan or finalize" alternative and the owning-WP routing are removed | WP21 T119, Binding; tasks.md T119 row |
| OD-WP15 | Keep #4827 orphan fail-closed; Q6 warn-and-continue only for non-orphan automatic refusals; the automatic refresh goes through the no-flag preserve-decision path; keep `test_finalize_refresh_pin_authority.py` green; design T004 around it | accepted. The superseded text (`refresh = flag or planning_changed`, the orphan amend+force recipe, moving the commit call) is struck through inline; the gate is named in Binding | WP15 T004, T083, T084, Binding |
| OD-WP12 | Own `planning_recency.py` (driver-covered paths skipped); keep `decisions` in the class guard's set, require the index.json driver pattern, amend the ruling text; audit topology-less callers (C-008) with a red-first `lanes` test; take the extended reader list | accepted. Interpretation: the operator's "divergent set" is read as the set that holds `decisions` today (`_NON_DIVERGENT_COORD_RESIDUE_DIRS`), and it stays there. The topology-less fix point is the single predicate in `coherence.py` | WP12 Binding; frontmatter |
| OD-SWA | Single write authority: `assert_coord_write_materialized` becomes a thin delegate of the accessor (materialize and seed for a local head; remote-only still refuses) | accepted and placed in **WP03**, not WP04. That is cleaner: it gives `coord_seed.py` a production caller in WP03, so the dead-module gate stays green with no transitional red. Red-first test plus deliberate re-pins of 2 refusal pins. WP04/WP08/WP09/WP10 note that the old refusal is gone | WP03 Binding; WP04, WP08, WP10 Binding |
| OD-PUB | PUBLISHED/E2 case: `write_dir` follows `resolution.py:191-199` after consolidation | accepted. WP04 adds it to T018 with tests; WP08 and WP10 add a post-consolidation write test | WP04, WP08, WP10 Binding |
| OD-WP03 | WP03 owns `mission_runtime/__init__.py` and `_PUBLIC_SURFACE`; package-root imports only; surface test in the gates | accepted | WP03 Binding, Targeted surface; frontmatter |
| OD-WP08 | Flip `_review_cycle_wp_dir`'s default to REVIEW_CYCLE; do not re-pin `test_verdict_dir_co_resolution`; approval leg; `workflow.py:1999-2025`; `_evidence_ref` uses `checkout_root`; drop the dead L279 shim | accepted. T046 and the objectives struck inline | WP08 Binding; frontmatter |
| OD-WP10 | Resolve `write_dir` once before the lock in `locked_reread_splice_and_write`; the same for `issue_verdict.py` (take ownership) | accepted. `gates_core.py` (the third splice caller) is also owned | WP10 Binding; frontmatter |
| OD-GATE | `test_no_worktree_name_guess.py` is not the P-M3 guard; WP20 extends `test_no_write_side_rederivation.py`'s module list with a `.parent.parent`-from-WriteLocation ban | accepted. The citations in WP03/WP07/WP09/WP17 are replaced; WP20 carries the 23-module list plus the bite test and twin | WP20 Binding; WP03, WP07, WP09, WP17 |
| OD-OWN | Ownership gaps: the `test_no_read_side_bypass.py` single owner; `decision.py:217`; `test_mission_creation_specify_started.py`; WP11 CLI, manifest, goldens and count pins | accepted (see Structural deltas) | frontmatter; Binding sections |
| OD-DEAD | Transitional dead-code gates: an expected red with an activity-log note, accepted by reviewers and turned green by the consumer; prefer zero-red | accepted. WP03 is zero-red (OD-SWA gives a caller). WP05: the literals and exit code are consumed by `surface_authority.py`, and the partition predicate by the grouping; only `render_commit_outcome` and `commit_outcome_payload` remain the protocol's transitional red, unless an in-WP production use exists | WP03, WP05 Binding |
| OD-WP06 | Rollback with the minted slug+mid8 (dirty-worktree refusal handled); the seed lock (owned root, `coord_mission_dir_name` key, bounded timeout); COORD-only restore; slug-vs-dir fix in `coord_branch_has_committed_artifact`; the D4 discriminator plus a negative test | accepted. Split by owner: rollback → WP06; lock and restore → WP03; the D4 discriminator is defined in WP03 and reused by WP04; the naming fix → WP04 (which owns `surface_resolver.py`) | WP03, WP04, WP06 Binding |
| OD-WP03d | Bounded lock timeout; `.code` not `error_code`; public partition predicates; `ProtectionPolicy.resolve_for_mission` | accepted. The CoordSeedForkRefused text is fixed inline | WP03 Binding, T014 |
| OD-WP19 | Reproduce through the CLI first; if that fails, fix the lanes/single_branch `sha=None` path and report; keep the allowlisted `CommitTarget` line verbatim; fix the stale "no dependencies" text | accepted. The stale text is replaced inline | WP19 Binding, Objectives |
| OD-WP16 | Keep the bool return plus a router-result helper; drop the contradictory `_is_coordination_owned`; red reasons re-derived | accepted. T088 is struck inline | WP16 Binding, T088 |
| OD-WP17 | `ProjectionTeardownAbort`: kw-only `error_code`, a remedy override, an optional SHA; `fork.py` must not import the status store module; handle or declare the new raises | accepted. WP17 owns `mission_type.py` and handles the raise; `consolidate.py:408` is verified and reported | WP17 Binding; frontmatter |
| OD-WP18 | Extract before adding arms (C901 14); L799; a bare-remote fixture; the dry-run vs real-run asymmetry noted for the PR | accepted. The `materialize` C901 15 extraction is also added | WP18 Binding |
| OD-C2 | State each WP's red evidence; WP21 red on the planning base is required | accepted | tasks.md red-evidence table; WP02, WP20, WP21, WP22 Binding |
| OD-C3 | Help text in the owning WPs; CHANGELOG at closeout | accepted with one change: the shared `docs/api/*` reference pages (`cli-commands.md`, `agent-subcommands.md`, `finalize-tasks-internals.md`) go to **WP22**, because several code WPs editing one shared page would create concurrent-lane conflicts. Each code WP updates its in-source help text and records its reference delta for WP22 | WP06, WP11, WP13–WP16, WP18 Binding; WP22 Binding; tasks.md Closeout items |
| OD-C4 | Tracer entries and the Pre-existing Failure Reporting Rule in every WP's quality gates | accepted | all WPs, Quality gates |
| OD-LOW | I4, I5, G2, C5, U2 | accepted (see the analyze rows below) | — |
| OD-MISC | Scout misc: WP01 `_StagePlan` fifth outcome and COPY `dst`; WP04 widens `_empty_coord_surface`; WP05 order-preserving dedupe and the canonical literals in `surface_authority.py`; WP06 `policy`; WP07 no `kind` param; WP09 `_events_path` split and decision rows without a Lamport field; WP11 `config_key`/`pattern` and terminal-beats-open; WP13/WP14 stale wording; WP14 `_maybe_auto_commit` location and the `record_analysis` extraction; WP20 T110 list | accepted | each WP's Binding; inline fixes in WP13, WP14, WP20 |

### Analyze findings

| ID | Severity | Finding (short) | Disposition | Where |
|----|----------|-----------------|-------------|-------|
| C1 | HIGH | NFR-001 vs the charter's < 2 s rule is not recorded in the Charter Check | design docs (architect); no task change. WP06 T036 already measures against the ruled budget | plan.md (architect) |
| G1 | HIGH | FR-009b committer list vs T119 | accepted (OD-G1) | WP21 |
| I1 | MEDIUM | Fold results missing from the design docs | design docs (architect) | contracts, data-model, plan |
| I2 | MEDIUM | Remote-only and seed-fork refusals not in the FR-006 list or the contract table | design docs (architect); WP05 already emits them as named refusals | spec, contract |
| U1 | MEDIUM | Refused seed commit path unspecified | accepted at task level: WP03 tests the refused-seed-commit path (warnings, uncommitted dir, the next commit carries it); spec edge case → architect | WP03 Binding |
| C2 | MEDIUM | Red-on-base statement does not fit WP01/WP02/WP20/WP21 | accepted (OD-C2) | tasks.md; WP21 |
| C3 | MEDIUM | No CHANGELOG or docs task | accepted (OD-C3) | tasks.md Closeout; WP22 |
| C4 | MEDIUM | Tracer and failure-issue duties missing | accepted (OD-C4) | all WPs |
| A1 | LOW | Protected-primary precondition for the default create path | design docs (architect); WP06 R-m4 and WP21 already pass `--topology` or a protected primary explicitly | spec |
| A2 | LOW | "Loud" undefined | accepted at task level: WP03 defines it as a WARNING log naming the Mission, the state and the action; spec → architect | WP03 Binding |
| A3 | LOW | FR-003 vs FR-003a wording | design docs (architect) | spec |
| I3 | LOW | Stale counts in plan.md | design docs (architect) | plan |
| I4 | LOW | WP19 described as a root | accepted; fixed in tasks.md, WP02 and WP19 | tasks.md; WP02, WP19 |
| I5 | LOW | WP05 order credited to the plan | accepted; reworded as a stated deviation | tasks.md; WP05 |
| I6 | LOW | Standalone repro files named as permanent homes | design docs (architect); WP05/WP06 already fold them in (R-M8) | research, plan |
| G2 | LOW | FR-017 not mapped to WP04/WP12 | accepted; requirement_refs and the coverage table updated | WP04, WP12; tasks.md |
| C5 | LOW | Ledger reversal hosted in an unrelated 3.x ADR | accepted; WP22 writes a dedicated `docs/adr/4.x/2026-10-01-2-decision-ledger-primary-partition.md`, and ADR 2026-06-19-1 links to it | WP22 |
| U2 | LOW | Legacy-copy retirement untracked | accepted: stated as an **in-mission closeout fold, not deferred**; an issue is filed only if the operator defers it after all | tasks.md Closeout items; WP20 |
| G3 | LOW | No owner for the issue-matrix verdicts (#2533 split) | accepted; added to tasks.md Closeout items | tasks.md |

### Brownfield scout corrections (per WP)

Every `CORRECTION` and relevant hazard in the two scout files is folded into the owning WP's Binding section. The cross-cutting items and where they landed:
- X1 two write authorities → OD-SWA;
- X2 E2/PUBLISHED → OD-PUB;
- X3 P-M3 gate → OD-GATE;
- X4 ownership spill → OD-OWN;
- X5 dead-symbol/module reds → OD-DEAD;
- X6 lock discipline → WP03;
- X7 D4 over-match → WP03/WP04.

Hazards that need no task change are recorded as "run by name" or "keep green" lines in the Binding sections.

### Tooling friction (repeat)

- `map-requirements` dropped the frontmatter keys `agent`, `assignee` and `shell_pid` again; they were restored. Re-check them after the mutating `finalize-tasks`.

## Analyze re-run folds (round 4)

**Input**: `analysis-report.md` re-run, verdict READY (0 high, 3 medium, 10 low). The mediums came from design-doc / WP drift.

**Scope**: this round folds every artifact so that they stay mutually consistent: spec.md (now **revision 5**), plan.md, research.md, data-model.md, contracts/seed.md, traces/design-decisions.md (a dated round-4 entry, with the superseded round-3 bullets struck), tasks.md and the WP prompts.

**Validation**: `finalize-tasks --validate-only` passes with 16 lanes, no lane cycle, no ownership warnings and 28/28 functional requirements mapped. The `agent: claude` key was restored in WP16 after map-requirements.

| ID | Severity | Decision / finding | Disposition | Where |
|----|----------|--------------------|-------------|-------|
| I7 | MEDIUM | `plan.design.merge-class-guard-set`: `decisions` stays in `_NON_DIVERGENT_COORD_RESIDUE_DIRS`; amend the ruling; assert the `index.json` driver pattern is registered | accepted. plan IC-11, research D13 and the traces now match WP12 (round-3 traces bullet struck) | plan.md IC-11; research.md D13; traces; WP12 Binding |
| I8 | MEDIUM | `plan.design.topology-less-callers`: a single fix point in `coherence.py` resolves the stored topology; `lanes`/`single_branch` keep today's verdict; coordination Missions get the PRIMARY ledger rule at every caller | accepted. `_TOPOLOGY_LESS_LEGACY_RESIDUE_KINDS` and the old D12 rule 3 are removed from plan (IC-11 rule, risks, Project Structure), research D12 and the data-model residue table. WP12 gains coordination-Mission tests at move-task, implement and auto-rebase (uncommitted ledger = real work) | plan.md; research.md D12; data-model.md; traces; WP12 Binding |
| U3 | MEDIUM | `plan.design.seed-trailer-ownership`: one constant `COORD_SEED_TRAILER` (WP03) written by WP03 T015 and WP06 T031; the tree-content alternative removed; a refused seed commit is retried with the trailer by the next seed attempt, with no router change | accepted. contracts/seed.md step 9, Postconditions and Errors updated; research D4 and D5 sentences reconciled; spec edge case "Refused seed commit" updated; plan IC-03/IC-05 and the Project Structure name the constant. WP03 T015 and WP06 T031 gain trailer subtasks with tests. The tree-content discriminator is struck in WP03 (Binding, T016 state rows, T014 step 6) and WP04 (T021 probe, Objectives, Context) | spec.md; plan.md; research.md D4/D5; contracts/seed.md; WP03; WP04; WP06 |
| C3 | LOW | WP17 help and reference deltas | accepted. WP17 Binding gains a C3 line; WP22's delta list gains WP17's deltas (`docs/api/cli-commands.md` ≈L1864, `docs/api/agent-subcommands.md` ≈L596) | WP17; WP22 |
| I3 | LOW | Charter Check gate floor | accepted: ≥ 22 | plan.md |
| I4 | LOW | WP19 called a root | accepted. tasks.md WP02 and WP19 parallel lines, plus the Sequence and Parallelization lines | tasks.md |
| I9 | LOW | WP19 fallback vs C-008 | accepted. A spec Edge Case "Implement receipts on non-coordination topologies (C-008 note)" says the change is output-only and additive. WP19 Binding requires recording the reproduction result against FR-013/US6 and the #5440 implement Assumption, plus a `lanes` unchanged-fields control | spec.md Edge Cases; WP19 Binding |
| I10 | LOW | Stale cross-references | accepted. tasks.md header (spec rev 5; research D1-D23); WP01 Context (D1-D23); D22 cited in the WP03/WP04/WP08/WP10 Bindings; D23 cited in WP04/WP08/WP10 | tasks.md; WP01; WP03; WP04; WP08; WP10 |
| I11 | LOW | Unstruck superseded text | accepted, struck inline: WP21 T119 step 1 "(or setup-plan …)" and the Review Guidance "Optionally" (now Required); WP06 T033 title/step 1, Context, DoD and Review S9; plan IC-01 `record_analysis` row (plus the missing `_commit_planning_pin_refresh_locked` row) and IC-02 S9 check; tasks.md T033, WP01 "leave record_analysis alone" and WP14 "do not touch record_analysis" | WP21; WP06; plan.md; tasks.md |
| I12 | LOW | mark-status listed as a commit-outcome consumer; wrong IC-04 site | accepted. mark-status is removed from spec FR-007, plan IC-07, research D8 and tasks.md T046, with a note that it renders nothing; the tracer-append CLI is added as a consumer. plan IC-04's mark-status site is corrected to `_ms_emit_subtask_state` (L359/L406-413). WP08 Context quotes the rev-5 FR-007 wording | spec.md; plan.md; research.md; tasks.md; WP08 |
| I13 | LOW | FR-017 anchor list misses the 4.x ADR | accepted. FR-017 names `docs/adr/4.x/2026-10-01-2-decision-ledger-primary-partition.md`; ADR 2026-06-19-1 links to it (WP22) | spec.md; WP22 |
| I14 | LOW | Lane prose vs lanes.json | accepted. The tasks.md lane notes are rewritten as a lanes.json table (lane ids and lane dependencies). They state that lane-a (WP01/WP04/WP05) starts after lane-c (WP03), that lane-o starts after lane-a and lane-j, and that lane-f starts after lane-b and lane-o. The WP01 dependency note and the Sequence line are updated | tasks.md |
| G4 | LOW | FR-009b missing from WP16 | accepted. `map-requirements --wp WP16 --refs FR-009b`; tasks.md WP16 refs and the coverage row updated | WP16 frontmatter; tasks.md |

**Residual historical wording** (intentionally kept):
- research.md cites "Spec rev 3" where the operator rulings were first stated (Q1, Q2, Q3, Q5). These are historical provenance notes, not stale cross-references.
- The earlier rounds' rows in this file are an append-only log.

## Confirming-analyze folds (round 5)

**Input**: the confirming `/spec-kitty.analyze`, verdict READY, with three follow-on findings from the round-4 trailer fold.

**Scope**: folded consistently across contracts/write-location-accessor.md, contracts/seed.md, data-model.md (§2, the new I-SEED-10, I-SEED-6, §7), spec.md (edge case "Refused seed commit"), research.md (D4, D22), plan.md (IC-18 resume note), and WP01, WP02, WP03, WP04, WP07, WP12, WP14, WP18, WP20 and WP22.

**Validation**: `finalize-tasks --validate-only` passes with 16 lanes and no ownership warnings.

| ID | Severity | Finding | Disposition | Where |
|----|----------|---------|-------------|-------|
| X1 | MEDIUM | The refused-seed retry contradicted "MATERIALIZED: no side effects", and its predicate also matched never-seeded pre-fix MATERIALIZED Missions (#5519 shape) | accepted. (1) **Narrowed predicate** (data-model I-SEED-10): pending ⇔ no `Spec-Kitty-Coordination-Seed: <mission_id>` trailer **and** no COORD-kind blob under the Mission dir at the coordination tip (the dir is wholly untracked, which only a refused seed leaves); the fast path is the porcelain `?? kitty-specs/<dir>/` check. (2) The MATERIALIZED rows now read "no side effects unless a seed commit is pending" (accessor contract, data-model §2, I-SEED-6, seed.md step 2 and the Errors row, research D22, WP03 T016, WP22 table). (3) WP03 T015 step 2, the U1 Binding and data-model §7 now say "the next seed attempt". (4) WP03 T017 gains the negative test: a pre-fix MATERIALIZED Mission with an uncommitted COORD record gets no seed commit and no trailer. The IC-18 `--resume` note is qualified | contracts; data-model; spec; research; plan; WP03; WP18; WP22 |
| X2 | MEDIUM | Post-fix fixtures must come from WP03's real seed | accepted. WP02 states that `materialized=True` is **pre-fix-shaped** (no trailer) and adds a helper note that post-fix fixtures come from WP03's seed (pre-fix EMPTY → `write_dir` → SEEDED with the trailer → delete the dir). WP07 T037's post-fix EMPTY row, WP04 T021 step 4 and its Review line are rebuilt through WP03's seed. WP04's "otherwise define it here" fallback is struck. WP03 Context D4 and WP22 T115's ADR text now name the trailer | WP02; WP03; WP04; WP07; WP22 |
| X3 | LOW | Leftover superseded text | accepted, struck or reworded: WP12 T068 step 2 (decided: `decisions` stays) and its Risk; WP14 Review ("record_analysis untouched" → extracted first); WP01 C901 table note (`_maybe_auto_commit`); WP20 T110 `tasks_mark_status.py ≈L279` | WP12; WP14; WP01; WP20 |
