# Implementation Plan: Consolidation claim, rollback and teardown integrity

**Branch**: `issue-5338-consolidation-claim-rollback-integrity` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/spec.md`

## Summary

Make `spec-kitty consolidate` transactional from the operator's point of view (epic #5001 invariant: *a non-zero exit never leaves half-mutated state and never claims nothing moved when something did*). Four cuts, in order:

1. **Claim-time refusal (#5338)** — act on the fail-closed claim integrity verdict right where the claim is built (`_capture_reconciliation_claim`, still inside the pre-mutation fresh-record guard), via ONE shared predicate the gate also uses.
2. **One pre-mutation snapshot + one CAS rollback authority (#5318, #5332)** — persist every branch tip the run may move once, before the first mutation; on any non-zero exit of the reconciliation/projection phase, and on `--abort`, restore every snapshotted branch through one authority that reports per branch.
3. **Planning self-heal skip (#5296)** — when the planning lane's worktree is the repository root checkout on the target branch, the dependency self-heal skips merging code lanes and the claim-ancestry gate waives code-lane ancestry; the claim proceeds and the code arrives through consolidation (DM `01M3PJWGGKTRT9W03MJHFV44Q2`, superseding the refuse decision, which deadlocks).
4. **Truthful refusal text (#5296)** — refusal/failure text is derived from the rollback report, never a hard-coded "no refs/worktrees were mutated".

Operator decisions: DM `01M3PD3NAECRSVPYZ6J5KWDTDW` (scope incl. #5332), DM `01M3PD3VP1YTQ4D17HT96JA0T2` (CAS ref restore; supersede revert-only AC-B3 on the rollback path), DM `01M3PD41NQ6J6EX8V2HYDDRGPZ` (planning self-heal refuses) — superseded by DM `01M3PJWGGKTRT9W03MJHFV44Q2` (skip merge, waive code-lane ancestry) after the post-spec squad showed refusal deadlocks.

## Technical Context

**Language/Version**: Python 3.11+ (repo requires 3.11; mypy strict, ruff incl. C901 ≤ 15)
**Primary Dependencies**: typer, rich, git CLI (subprocess via existing `run_command` / `_run_git` helpers); no new dependency (no supply-chain decision)
**Storage**: `.kittify/runtime/merge/<mission_id>/state.json` (`ConsolidationState`, JSON, additive optional field only); git refs
**Testing**: pytest; red-first real-CLI acceptance repros in `tests/terminus/` via `build_coord_mission` / a new LANES fixture builder + `run_terminus`; focused unit tests in `tests/consolidation/`, `tests/git/`, `tests/lanes/`; `@pytest.mark.integration`/`git_repo` markers
**Target Platform**: Linux/macOS/Windows CLI (git ≥ 2.x)
**Project Type**: single (src/specify_cli)
**Performance Goals**: rollback of a 4-lane snapshot ≤ 2 s (NFR-001) — one `update-ref` + optional resync per moved branch
**Constraints**: do not edit #5359's functions beyond one call-site line (C-001); destructive-op census (`tests/architectural/test_destructive_op_routing.py`) keys its allowlist by (file, qualname, token) — `git/ref_advance.py` is NOT blanket-exempt: extract `_resync_checkouts(...)` from `advance_branch_ref` and re-key its one allowlist entry with rationale in the same WP; frozen phase order (`test_executor_phase_boundary.py::test_locked_driver_calls_phases_in_frozen_order`); `_run_lane_based_consolidation` is at C901=14
**Scale/Scope**: ~6 src files, est. 550–650 src LOC (post-plan re-estimate) + 1,100–1,400 test LOC (post-spec sizing lens); 8–10 real-CLI repros at ~35–40 s each; a new LANES real-CLI fixture builder in a NEW file `tests/terminus/lanes_fixture.py` (not conftest — #5359 edits conftest)

## Charter Check

- **Single canonical authority** — PASS by design: one refusal predicate shared by claim and gate; one rollback authority for gate/projection/abort; ADR amended, not paralleled. Deferred (named, not ticketed): folding the other rollback authorities (`_reset_coord_to_checkpoint` revert path, `_revert_orphan_target_bake_commit`, byte restores) into the new authority; retiring the live `run.pre_mutation_coord_*` twin.
- **ATDD-first / red-first (C-011, SO#4)** — each WP opens with a failing real-CLI repro committed before the fix; reviewer verifies red on the WP base and green at the WP tip.
- **Architectural gate discipline (SO#5)** — new AST pin: every refusal/failure `Exit(1)` in the reconciliation phase is reached through the rollback wrapper (non-vacuous: floor ≥ 1 call site + self-mutation test). Named gates run: `test_destructive_op_routing.py`, `test_executor_phase_boundary.py` (tests/consolidation), `test_merge_pipeline_ratchets.py`, `test_no_legacy_terminology.py`, `test_layer_rules.py` if imports change.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — targeted files only; stated per WP.
- **Terminology canon** — Mission, lane consolidation (never bare "merge"/"publish" in new prose); "repository root checkout", "target branch".
- **Campsite (SO#2)** — WP01 is a behaviour-preserving tidy-first step (constant for the repeated literal, shared refusal predicate, snapshot value type) with focused tests.

No unjustified violations.

## Project Structure

### Documentation (this mission)

```
kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/
├── spec.md
├── plan.md              # this file
├── research.md          # decisions + rejected alternatives
├── data-model.md        # snapshot + rollback report
├── quickstart.md        # how to reproduce/verify each defect
├── contracts/
│   └── rollback-authority.md
├── traces/              # tracer files
└── tasks/               # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/specify_cli/
├── consolidation/
│   ├── reconciliation.py      # + claim_integrity_refusal() (new module fn; verify() NOT rewired until #5359 lands)
│   ├── executor.py            # claim-time exit in _capture_reconciliation_claim; snapshot persist; driver call-site wrapper
│   ├── rollback.py            # NEW: PreMutationSnapshot capture + rollback_to_snapshot() -> RollbackReport
│   └── state.py               # + ConsolidationState.pre_mutation_refs (optional, additive)
├── git/ref_advance.py         # restore_branch_ref(..., resync_checkouts=True) opt-in, reusing the advance resync
├── cli/commands/consolidate.py # _dispatch_abort restores via the authority before clearing state
└── lanes/implement_support.py # planning self-heal refusal guard (caller of _merge_dependency_lane_tips)
tests/
├── terminus/                  # red-first CLI repros (#5338, #5318, #5332, #5296) + LANES fixture builder
├── consolidation/             # unit: predicate, snapshot, rollback authority, report text, AST pin
├── git/                       # restore_branch_ref resync unit tests
└── lanes/                     # planning self-heal refusal + re-pinned test_planning_claim_self_heal
```

**Structure Decision**: single project; new module `consolidation/rollback.py` is the one rollback authority (keeps `executor.py` from growing and gives the AST pin one target).

```mermaid
sequenceDiagram
  participant CLI as consolidate
  participant EX as executor driver
  participant RB as rollback.rollback_to_snapshot
  participant ST as state.json
  CLI->>EX: run
  EX->>EX: _capture_reconciliation_claim
  alt claim_integrity_refusal(claim) and not resume-already-passed
    EX-->>CLI: print guidance, Exit(1) (fresh record cleared, nothing mutated)
  end
  EX->>ST: persist pre_mutation_refs (fresh only; resume reuses)
  EX->>EX: lane consolidation, bake, mission→target, done, commit (post tips recorded after each)
  EX->>EX: _phase_reconcile_before_teardown (#5359-owned body)
  alt non-zero Exit (FAIL / REFUSE / projection refusal)
    EX->>RB: rollback_to_snapshot(run)
    RB->>RB: per ref: CAS restore_branch_ref(resync) | already-at-snapshot | not-restored
    RB->>ST: clear bake/completed/passed markers (only if all restored)
    RB-->>CLI: RollbackReport → truthful text, Exit(1)
  end
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| One-line edit in `_run_lane_based_consolidation_locked` (a #5359-touched function) | The only place every non-zero exit of the gate phase can be caught without editing the gate body #5359 rewrites | Editing `_phase_reconcile_before_teardown` collides with #5359's body rewrite; a decorator on it changes the frozen phase-order pin |
| Supersede the ADR 2026-09-19-1 "unify, don't fork" revert-only rollback rule (and `_reset_coord_to_checkpoint`'s revert-only docstring) on this path; the amendment names `consolidation/rollback.py` the canonical authority and lists the four remaining ref-moving paths (`_reset_coord_to_checkpoint`, `_revert_orphan_target_bake_commit`, `_rollback_target_after_failed_reconciliation`, `repair_coord_strand`) as deprecated with retirement conditions | A forward revert leaves lane tips ancestors of the mission/coordination branch, so the next run's authored range stays empty — #5318 persists | Revert + durable anchor (operator rejected, DM 01M3PD3VP1YTQ4D17HT96JA0T2) |

## Implementation Concern Map

> **Note**: Implementation concerns are NOT work packages and are NOT executable units.

### IC-01 — Tidy-first campsite (behaviour-preserving)

- **Purpose**: give the functional fixes one obvious insertion point each without behaviour change.
- **Relevant requirements**: enables FR-001, FR-009, FR-010; NFR-003
- **Affected surfaces**: `consolidation/reconciliation.py` (new pure `claim_integrity_refusal(claim) -> str | None` = `_refusal_reason` + vacuous-manifest check, module level; `verify()` untouched), `consolidation/executor.py` (hoist the repeated "Nothing was torn down…" literal to a constant at the three executor sites only; extract the claim GitProbeError exit), focused unit tests.
- **Risks**: tests asserting exact message text (grep before changing); do not touch #5359 functions.

### IC-02 — Claim-time refusal (#5338)

- **Purpose**: refuse before the first mutation when the claim already cannot be proven.
- **Relevant requirements**: FR-001, FR-002; SC-001, SC-006
- **Affected surfaces**: `executor._capture_reconciliation_claim` (end of fn, after `build_approved_wp_set`): `if (r := claim_integrity_refusal(run.approved_wp_set)) and not _resume_reconciliation_already_passed(run): print(VerifyResult.refused(r).recovery_guidance()-equivalent claim-time text); raise typer.Exit(1)`. Runs inside `_clear_fresh_record_on_pre_mutation_exit`, so a fresh record is cleared.
- **Scope note**: claim-time refusals are exactly `claim_integrity_refusal` (explicit `claim.refusal`, unresolved surface, vacuous claim). #5359's new REFUSE reasons are evaluated against the post-merge target at the gate and are out of scope here. FR-001's byte-compare excludes the post-fix marker re-stamp and a pre-existing `_heal_pending_coord_reconcile` heal.
- **Red test**: the resume scenario B (fresh gate FAIL → delete an approved lane branch → `--resume`): today the REFUSE claim is ignored and the target moves (squash + done commit, canceled file on target). No fresh-run claim-integrity refusal reaches mutation today (missing lane branches fail earlier in `_phase_merge_lanes`); the "empty authored-blob set" REFUSE is a gate-only squash check and stays at the gate (moving it would wrongly refuse planning-only missions) — it is the cheap fresh red for IC-03/IC-05 instead.
- **Predicate**: `claim_integrity_refusal(c) = MergeOutcomeVerifier._refusal_reason(c) or _vacuous_reason(c)` — calls the existing staticmethod, no copy; rewire `verify()` to it after #5359 lands.
- **Risks**: existing tests that build a refusing claim and expect later phases to run (grep `refusal=` / `surface_resolved=False` in tests/consolidation + tests/terminus) — re-pin as stale assertions with rationale, never soften the fix; the #5021 resume path must stay green.

### IC-03 — Pre-mutation snapshot + single CAS rollback authority (#5318, #5332)

- **Purpose**: one snapshot, one restorer, for gate FAIL/REFUSE, projection refusal and `--abort` (scoped invariant; post-PASS exits and other in-phase exits are out — residual R3).
- **Relevant requirements**: FR-003..FR-007, FR-010, FR-011; SC-002, SC-005, SC-006; NFR-001
- **Affected surfaces**:
  - `state.py`: `pre_mutation_refs: dict[str, str]` and `post_mutation_refs: dict[str, str]` (branch → sha), optional, absent → `{}` (back-compat `from_dict`).
  - `consolidation/rollback.py` (new, the single authority):
    - **Single snapshot writer (post-plan fold, corrected post-tasks)**: `capture_pre_mutation_snapshot` is the only writer of `pre_mutation_refs`; it READS the legacy anchors (`pre_mutation_target_sha`, `pre_mutation_coord_sha/ref`, persisted earlier by `_resolve_pre_mutation_*`) as seeds so the two never disagree. `begin_attempt` computes per-attempt `restore_targets` (snapshot unless someone other than consolidation moved the branch between attempts). Keys are short branch names, deduped explicitly (coord topology: mission_branch == coord ref; LANES: the STATUS_STATE checkpoint and `lane-planning` resolve to the target). Contents: target (seeded from `pre_mutation_target_sha`), `lanes_manifest.mission_branch` (**never persisted today** — finding 6a), coordination ref when present (seeded from `pre_mutation_coord_sha/ref`), and EVERY lane branch in the manifest **including `lane-planning`** and regardless of topology (today's `pre_interrupt_lane_tips` skips planning and non-coord — finding 6b/c). Persisted once on a fresh run, inside the pre-mutation guard, after the claim; a resume reuses the persisted map verbatim; a pre-fix resume with no map seeds from the persisted anchors only.
    - `record_post_mutation_tips(run)` — called at the end of each mutating phase (`_phase_merge_lanes`, `_phase_bake_and_pre_target_done`, `_phase_mission_to_target`, `_phase_record_done_and_project`, `_phase_commit_and_assert` — none #5359-touched) and immediately before the gate; persists the observed tip of every snapshotted branch (the CAS expected value). A branch that differs from its snapshot with NO recorded post tip is NOT_RESTORED (never guessed: the ancestor fallback would overwrite an operator's own later commit on the target).
    - `rollback_to_snapshot(repo, state, *, reason) -> RollbackReport` — FR-011 guard first: if `state.reconciliation_passed_target_sha` equals the current target tip, or any snapshotted branch no longer resolves → REFUSED_VERIFIED_LANDING (retain all). Else per branch: current == snapshot → ALREADY_AT_SNAPSHOT; expected = `post_mutation_refs[b]` if recorded, else require `snapshot` is-ancestor-of `current` and use current; current ≠ expected → NOT_RESTORED(observed, expected); else `restore_branch_ref(..., expected_current_sha=expected, resync_checkouts=True)` → RESTORED, or NOT_RESTORED on `RefRestoreError`/dirty checkout. Only when every branch is RESTORED/ALREADY: clear `mission_number_baked`, `completed_wps`, `reconciliation_passed_target_sha`, `post_mutation_refs`, and `pending_coord_reconcile` when the coordination branch was restored; save state.
    - `render_rollback_report(report) -> str` — the single source of truthful text (FR-009).
  - `git/ref_advance.py`: extract `_resync_checkouts(repo, branch, sha, env, is_residue)` (list worktrees → dirty/obstruction check BEFORE the move → after the CAS move `reset --hard <branch>` per checkout) out of `advance_branch_ref`; both `advance_branch_ref` and `restore_branch_ref(..., resync_checkouts: bool = False, is_residue=None)` call it; re-key the census allowlist entry (qualname moves) with rationale; amend the `restore_branch_ref` docstring. The rollback authority passes `is_residue=is_toolchain_generated_churn` (as lanes/consolidation.py:1234 does) so byte-restored status/meta residue does not make the common case NOT_RESTORED. Live-verified reversible (residual hunt item 4); without resync the checkout shows the reverse diff staged — resync is mandatory on this path.
  - `executor._run_lane_based_consolidation_locked` (#5359-touched — ONE call-site edit): `record_post_mutation_tips(run)` then `try: _phase_reconcile_before_teardown(run) except typer.Exit as e: if e.exit_code: print(render(rollback_to_snapshot(...))); raise`. Covers FAIL, REFUSE (which main leaves un-rolled-back) and the projection refusals raised inside the phase (#5332), incl. the resume short-circuit (where FR-011 keeps the verified landing). Idempotent against the existing/#5359 target-only restore (ALREADY_AT_SNAPSHOT). The gate body `_phase_reconcile_before_teardown` and `_rollback_target_after_failed_reconciliation` are NOT edited; their target-only restore becomes a redundant backstop (retire after #5359 lands — follow-up note). The wrapper does not change the frozen phase-order list (it wraps a call, it adds no phase).
  - `cli/commands/consolidate._dispatch_abort` (C901 13 today and INVISIBLE to local ruff — ruff.toml per-file C901 ignore for consolidate.py; Sonar S3776 still counts): extract `_abort_restore_or_keep_record(...)`; reuse the existing lock API (`release_merge_lock_if_owned` family), no second lock path; acquire the global consolidation lock (refuse while a live lock is held by another run), `rollback_to_snapshot(state)` BEFORE `_teardown_coordination_for_abort`/`clear_state`; any NOT_RESTORED / REFUSED_VERIFIED_LANDING → keep the record, print the report, exit 1; a record without a snapshot → today's behaviour + a notice.
  - Pin: `tests/consolidation/test_single_rollback_authority.py` — AST: the driver wraps `_phase_reconcile_before_teardown` with the authority, `_dispatch_abort` calls it, and no other module calls `restore_branch_ref(..., resync_checkouts=True)`; floor ≥ 2 call sites; self-mutation test.
- **Topology notes (live-verified)**: in LANES the #5318 residue is the mission branch left at the lane-merge + bake commit (the fresh run self-refuses rather than shipping, because the claim base is the target); the #5332 projection refusal is effectively unreachable in LANES (checkpoint = target), so its repro uses coordination topology (`build_coord_mission`). LANES fixture: copy `scratchpad/residual-hunt/lanes_fixture.py` into `tests/terminus/lanes_fixture.py` (unprotected target such as `develop`; WP frontmatter without `agent:`).
- **Risks**: textual rebase conflict with #5359 on the driver lines; coord worktree dirty → NOT_RESTORED (reported); done events on the coordination branch disappear with the ref (intended); tests pinning FOLD-5 "no rollback on projection refusal" must be re-pinned with rationale.

### IC-04 — Planning self-heal skip (#5296)

- **Purpose**: a planning-lane claim never merges code-lane content into the repository root checkout on the target branch, and does not deadlock.
- **Relevant requirements**: FR-008; SC-003
- **Affected surfaces**: ONE place — the approved-dependency predicate `_approved_dependency_lane_refs` in `lanes/implement_support.py` (~:444), which both `check_claim_ancestry` (~:558) and the self-heal (~:372) consume: for a planning lane whose repository root checkout HEAD (`git symbolic-ref --short HEAD`) equals `manifest.target_branch`, code dependency lanes are excluded (waived) — so `check_claim_ancestry` passes first and the self-heal merge (and its `assert_not_protected_branch`, which today already deadlocks a protected target with `ProtectedBranchCommitError`) is never reached. Print a notice ("code lanes reach the target through `spec-kitty consolidate`"). NOTE: every planning lane resolves to `repo_root` regardless of topology (`workspace/context.py:835-848`, `create_planning_workspace`), so the discriminator is the root checkout's HEAD vs the target branch, not placement. Allocator internals untouched (census pin, C-007). Replace `tests/lanes/test_planning_claim_self_heal.py::test_planning_materialization_claim_merges_approved_dependency` (encodes the retired behaviour) with the new contract + a control whose root checkout HEAD is NOT the target branch (old self-heal kept). Live-verified: consolidation after the skip reaches rc 0 with WP code attributed (residual hunt item 3).
- **Risks**: the waiver must be exactly scoped (repository root checkout on the target branch) — a coordination-topology planning lane keeps today's self-heal; consolidation must then pass the gate with the code attributed (SC-003 second half).

### IC-05 — Truthful refusal/failure text (#5296)

- **Purpose**: never print "no refs/worktrees were mutated" when a branch moved.
- **Relevant requirements**: FR-009; SC-004
- **Affected surfaces**: the driver wrapper prints the RollbackReport after the gate's own guidance (restored / already at snapshot / NOT restored with observed vs expected); executor-owned literals (:2312 claim probe error — truthful pre-mutation; :2553/:2576 projection refusals now followed by the report); `coordination/teardown.py:115` wording audit. `reconciliation.recovery_guidance` text is #5359-owned: leave it untouched on main; after rebase onto #5359, reconcile wording in one follow-up commit (noted in PR).
- **Risks**: golden-output tests (`tests/specify_cli/cli/commands/test_merge_cli_golden.py`) — re-pin.

### IC-06 — Governance + docs

- **Purpose**: record the contract.
- **Relevant requirements**: C-005
- **Affected surfaces**: amend `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md` (snapshot + single CAS authority supersedes revert-only on the rollback path; snapshot immutability across resume/abort; ledger-derived refusal text; no dependency self-heal onto the target checkout); `CLAUDE.md` "Consolidation & Preflight Patterns" paragraph; `docs/changelog/CHANGELOG.md` `[Unreleased]`. Done at closeout on the aggregate branch.
