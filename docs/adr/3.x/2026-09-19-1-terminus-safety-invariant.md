---
title: 'ADR: Terminus-Safety Invariant — gate-then-mutate-with-rollback across merge, accept, and mission close'
description: 'Terminus-safety invariant: completion commands gate-then-mutate with rollback on failure, enforced by one shared terminal-readiness authority.'
status: Accepted
date: '2026-09-19'
updated: '2026-10-04'
---

## Context and Problem Statement

> **Operator-ratified (agentic-framework-core-team, Stijn Dejongh, 2026-09-19)** for the
> milestone-#11 Slice C mission `terminus-safety-invariant` (`01M2XFT756GZDJR08HS1QZ1XJY`),
> parented under epic [#3897](https://github.com/spec-kitty/spec-kitty/issues/3897).
> Decisions D1–D3 were made by the operator via a scope-fork question before the spec;
> D4–D5 are consequent design decisions made under that mandate and flagged for veto.
> Mechanism claims carry `file:line` verified at HEAD `207bbc1307` (v4.0.0rc4); the
> implementing WPs re-verify exact lines as `main` advances.

Spec Kitty's completion commands — `spec-kitty merge`, `spec-kitty accept`, and
`spec-kitty mission close` — share a latent **defect class**, not four independent bugs:

> A completion/terminus command mutates (or destroys) durable mission state **past a
> precondition it never hard-enforced**, and when a later step fails there is **no
> rollback** — leaving the mission wedged, split-brain, or falsely completed.

Four issues are the same shape:

- **#4764 (anchor)** — with the default `policy.merge_gates.mode: warn`, a missing-approval
  gate is emitted as a *non-blocking warning* (`policy/merge_gates.py:121` `is_blocking =
  mode=="block"`; `overall_pass` at `:53-54`), so the stop at `merge/executor.py:380-382`
  never fires. Merge then consolidates the lane (`_phase_merge_lanes`, `executor.py:1816`
  → `consolidate_lane_into_mission` `:443`) and bakes `mission_number` into the coordination
  `meta.json` (`_bake_mission_number_into_mission_branch` `:506` → `ordering.py:463/485`)
  **before** the post-merge backstop discovers no approval and exits 1
  (`done_bookkeeping.py:392`→`:497-503`) with no rollback. The lane is left with 0 commits
  beyond coordination, so the `for_review` gate rejects it forever; coordination vs primary
  `meta.json` split-brain on `mission_number`; unreviewed code is now on the mission branch
  a later squash carries to the mainline.
- **#4765 (anchor)** — `mission close` (non-discard, `mission_type.py:639-645`) tears down
  the coordination worktree and commits a `runtime_post_completion` retrospective to the
  mainline with **no** merged/terminal precondition, contradicting its own `--help`
  (`:514`).
- **#4474 (fold)** — the `mission_number` bake fail-opens on the coordination path (the exact
  bake step #4764 also mutates).
- **#2745 (fold)** — the general statement of terminus half-termination across merge + accept
  + mission-close, including the direct-on-target fallback path.

A point fix on any one reopens the others, and each command today computes "is this mission
terminally ready" a *different* way (an evidence-gate loop, an acceptance matrix, a
reopen-style completion reader, and ~9 hand-inlined `is_acceptable_ending` loops). So this is
one ADR, one invariant, one shared authority — not four patches.

## Decision

### D1 — Scope: one cross-cutting invariant (operator)

Establish a single **terminus-safety invariant**: every completion command must
**gate-then-mutate-with-rollback**. Fold #4764 + #4765 + #4474 + #2745 into one mission
rather than shipping isolated point-fixes. Sibling clusters (merge cleanup/abort
#4753/#4754/#4762; finalize-tasks #4075/#4758/#3874; `next` FSM #4161; view-consistency
#3967) stay separate.

### D2 — `warn` softens evidence-quality only (operator)

`policy.merge_gates.mode: warn` softens **evidence-quality** gates only (review verdict,
risk, hollow-review). The **terminal-lane invariant** — "every non-cancelled work package is
at an acceptable ending (approved/done)" — is enforced **HARD regardless of mode**.
Consequence: merge gets an **unconditional merge-ready precondition** placed *before* lane
consolidation, hoisted out of the mode-softened evidence gate — **not** a rollback-only fix
that would keep the fail-open and merely make it recoverable.

### D3 — Parent under epic #3897 (operator)

Parent the mission under epic #3897 (Mission-lifecycle robustness — preflight +
abandon/clean-partial), whose charter already owns "preflight before mutating" and "failed
attempts left mission in debris". (#2745 keeps its existing epic #1795 lane-mechanics parent;
it is folded for the fix, not reparented.)

### D4 — Per-command predicates through one shared authority (agent; flagged for veto)

**Reject** reusing a single `is_mission_completed` predicate across all three commands. It is
semantically wrong in opposite directions: it returns **False** for a normal merge-ready
mission (merge is what bakes `approved`→`done`; pre-merge WPs are `approved`, not `done`) so
it would *false-block every ordinary merge*, and it short-circuits **True** on `merged_at`
(`status/lifecycle.py:344`) so on `--resume` (baseline stamped mid-flight,
`executor.py:960`→`baseline.py:199`) it would *pass vacuously*. Instead:

- **merge** → a **merge-ready** predicate = every non-excluded WP ∈ {approved, done} ∪
  acceptably-cancelled, evaluated **unconditionally** (never routed through the mode-softened
  gate).
- **mission close** (non-discard) → **`is_mission_merged`** (merged baseline present,
  reopen-aware) — *not* `is_mission_completed`. An all-terminal-but-**unmerged** mission (e.g.
  all-cancelled) must be abandoned via `--discard`, not torn down as a completion; this
  matches the command's `--help`.
- **accept** → already gate-then-mutate (`accept.py:991` `if not summary.ok: raise Exit(1)`,
  all mutating writes strictly after) — the **canonical precedent** the other two are brought
  up to.

All three route their terminal-readiness check through **one shared authority** built on the
already-canonical per-lane reader `status_lanes.is_acceptable_ending` (+ `has_operator_provenance`)
and `status_lanes.TERMINAL_LANES`. The missing piece is a single aggregate
("is every non-cancelled WP at an acceptable ending?"), added in the orchestration-free
`status_lanes` module — **not** a 6th divergent definition. Adoption is scoped to
`specify_cli` in this mission; the runtime-side inline loops are **not** rewired here.

*Placement caveat (post-review correction).* `status_lanes` is a pure, I/O-free vocabulary
(stdlib-only imports) that today lives in the top `specify_cli` layer, so `runtime` already
reaches it **upward** (`runtime/next/committed_authority.py`, `runtime_bridge.py`) through the
shrink-only `runtime → specify_cli` ledger. That top-layer placement is the *cause* of the
ledger entry, not a reason to leave it alone: relocating this leaf vocabulary to a lower shared
layer (`kernel`/`mission_runtime`) is the direction that lets both `runtime` and `specify_cli`
depend on it **downward** and would *shrink* the ledger. The relocation is deliberately out of
scope for this safety mission (it touches the `runtime` layer) and is named as future-architecture
debt rather than justified away by an inverted ledger argument.

### D5 — Direct-on-target rollback scoping (agent; flagged for veto)

The invariant has two halves. The **abort-before-mutation precondition** (D2/D4) closes
#4764, #4765, #4474 and the entry points of #2745, and is fully in scope. The
**rollback-after-target-advance on the direct-on-target path** (SINGLE_BRANCH / LANES-without-coord;
done is marked *after* the target ref advanced, `executor.py:971-985`) is a **distinct, harder
seam with no existing machinery** — the rollback scope must include the target ref
(`ordering.py:485`), not just the coordination ref. It is planned as its own work package with
a red-first test; if it proves mission-sized, only that sub-part is deferred as a tracked
#3897 follow-up, with the direct-on-target path still made safe by a *refuse-before-advance*
guard. Because the terminal precondition runs before the target ref advances, the **unsafe**
interim — unreviewed code promoted to target, or a mission falsely recorded complete — is
unreachable. A *benign* under-marked state (an approved mission whose target advanced but whose
`done`/bake bookkeeping did not finish) remains reachable but is resume-recoverable; full
target-ref rollback on this path is exactly the deferred #3897 seam. "Unreachable" is scoped to
the unsafe class, not to all half-completion.

### D6 — Fold #2745's completion affordances (operator, post-spec)

The post-spec squad found #2745 is a 3-facet bundle: (1) direct-on-target half-termination
(safety); (1-affordance) no way to *complete* a direct-on-target mission with no lane branch;
(2) `accept` guidance (appears already fixed — the protected-primary hard-reject was removed,
`accept.py`); (3) `mission close` chokes on an orphaned `coordination_branch` (doubled slug, no
`--json`). The operator ruled to fold the **completion affordances** too, not just the safety
facet: add `merge --skip-lanes`/`--no-lanes` (a transactional completion path for direct-on-target
missions that still enforces the terminal precondition — no bypass), and fix mission-close orphan
tolerance / doubled-slug / `--json`. This mission therefore **fully closes #2745**; facet-2 is a
liveness confirmation.

### D7 — #4474 gets a delivering requirement (agent, post-spec repair)

#4474 was initially folded in name only: the merge-ready precondition (D2/D4) prevents baking a
*not*-merge-ready mission, but #4474's defect is a *merge-ready* coord mission whose `mission_number`
bake reads meta.json from the mission-branch tree (`merge/ordering.py:398-414`) and **fail-opens**
(`return False`, number lost, `doctor` stuck at `pending`) when it is absent there. That is the
opposite failure mode from #4764 (which bakes too early → split-brain). A distinct delivering
requirement (topology-aware write-back, or operator-visible surfacing of the unbaked field) closes
#4474's real defect so its red-first test is genuinely green-after.

### Transactional rollback: unify, don't fork

The coordination-path rollback **unifies** the existing fragmentary machinery
(`_capture_pre_target_coord_ref_sha` `:553`, `_restore_and_guard_coord_coherence` `:788`,
`_revert_coord_done_commit` `:644`) into one coord-transaction primitive with **named
checkpoints** (a new *pre-mutation* checkpoint captured before consolidation, plus the
existing *pre-done* checkpoint), rather than adding a second capture/restore authority. The
rollback must run before worktree teardown and must keep committed coordination `done`
markers and worktree bytes mutually coherent so `--resume` reads a consistent state.

**Guarantee framing (post-review correction).** The **precondition** (D2/D4), not the rollback,
is the load-bearing guarantee that closes #4764: it runs before the first mutation regardless of
gate mode, so an unapproved mission never consolidates. The rollback is **best-effort
defense-in-depth**, and its strength varies by path — atomic for a single-lane (or first-lane)
consolidation failure and for the mission→target step (coordination ref, target ref, and any
orphan `mission_number` bake all reset), but it **degrades** to abort-and-mark-for-reconcile-heal
on a multi-lane *partial* consolidation (a landed lane-merge commit cannot be `git revert`-ed
across a range without an explicit `-m`), and a consolidation-*success*-then-later-failure leans
on `_phase_merge_lanes` resume-idempotency rather than a rewind. None of these degradations reopen
#4764 — the precondition does the closing — but the rollback should not be read as a peer atomic
transaction across the whole merge.

### Amendment 2026-09-29 — one pre-mutation snapshot, one CAS rollback authority (slice 10)

> **Operator-ratified** in mission `consolidation-claim-rollback-integrity-01M3PD1T`
> (Decision Moments `01M3PD3NAECRSVPYZ6J5KWDTDW` scope, `01M3PD3VP1YTQ4D17HT96JA0T2`
> CAS ref restore, `01M3PJWGGKTRT9W03MJHFV44Q2` planning self-heal). Issues #5338, #5318,
> #5332, #5296 under epic #5001.

The "unify, don't fork" rule above is kept and extended; on the rollback path it is
**superseded** in one respect — rollback is a compare-and-swap ref restore, not a forward
`git revert`:

- **A1 — Refuse before the first mutation.** A claim that fails its integrity check
  (explicit claim refusal, unresolved coordination surface, empty claim against a non-empty
  manifest) exits non-zero in `_capture_reconciliation_claim`, inside the pre-mutation
  fresh-record guard, using the same predicate the gate uses
  (`reconciliation.claim_integrity_refusal`). A resume whose reconciliation already passed for
  the current target tip is exempt (#5021).
- **A2 — One snapshot.** Before the first mutation the run persists
  `ConsolidationState.pre_mutation_refs` (target, mission branch, coordination branch when
  present, every lane branch). `--resume` never recaptures it; a snapshot first captured when an
  older record (no snapshot) was resumed lists its live-captured entries in
  `resume_seeded_refs`, and the report calls them "snapshot taken when this record was resumed",
  not pre-consolidation. **Lane branches are report-only** (`snapshot_lane_branches`):
  consolidation never moves them, so they are snapshotted for the report but never recorded and
  never restored. After every mutating phase the run records `post_mutation_refs` — the
  compare-and-swap expected value — **only for the target/mission/coordination branches whose tip
  changed during that phase** (entry tips captured before the phase), except when the phase
  failed on a compare-and-swap refusal (`RefAdvanceError`/`RefRestoreError`: that tip belongs to
  another actor). A `RefResyncError` (the CAS write succeeded, only a checkout resync failed) IS
  recorded: the ref holds this run's tip. Per attempt, `restore_targets` keeps an operator's own
  change made between attempts.
- **A3 — One rollback authority.** `consolidation/rollback.py::rollback_to_snapshot` restores
  each snapshotted branch only while it is still at this run's recorded post tip, resyncs every
  checkout of it (dirty-checked first, via the shared `ref_advance._resync_checkouts`), reports
  per branch (restored / already at snapshot / lane kept / lane missing / NOT restored with
  observed vs expected), and clears the bake/completed/passed bookkeeping only after a full
  restore. A run-movable branch that moved with **no** recorded post tip (a kill inside a phase
  before its recorder ran) is NOT restored — never reported untouched — so `--abort` keeps the
  record and exits 1. A **missing** snapshotted branch never blocks the rest: a missing lane
  branch is reported with a `git branch <b> <sha>` recreate hint; a missing target/mission/
  coordination branch is NOT restored with the same hint. It is called by the gate/projection
  wrapper in the driver and by `consolidate --abort` (before the record is cleared, under the
  consolidation lock); an AST pin keeps the caller set closed. A landing verified by an earlier
  attempt (anchor == live target tip) is never rolled back.
- **A4 — Truthful text.** Refusal and failure output is followed by the rollback report; no
  message in these paths claims that nothing was mutated when a branch moved.
- **A5 — No dependency self-heal onto the target checkout.** A planning-lane claim whose
  repository root checkout is on the target branch waives code-lane ancestry instead of merging
  code lanes there; the code reaches the target only through consolidation's attribution window.

**Remaining authorities (deprecated, retirement condition: routed through A3).**
`_reset_coord_to_checkpoint`, `_revert_orphan_target_bake_commit`,
`_rollback_target_after_failed_reconciliation` (now a redundant backstop that the authority
reports as already-at-snapshot) and `coordination/coherence.py::repair_coord_strand`, plus the
other in-phase exits between the first mutation and the gate — tracked as #5385. Resume-side
residuals #5371 and #5372 are out of scope.

**Residuals of A2/A3 (pre-PR squad, not closed here).**

- *Same-phase foreign commit.* Recording compares tips at phase entry and exit, so a foreign
  commit that lands on a run-movable branch inside the same phase, after this run's own CAS
  advance of that branch and before the phase's recorder runs, is recorded as this run's and a
  later rollback restores over it. The window is one phase long.
- *Same-mission `--abort` racing a live run (F7).* `--abort` takes the global consolidation lock
  owner-gated by the mission id, which a live run of the SAME mission also holds; an abort issued
  while that run is still mutating is not excluded by the lock. This is the pre-existing
  owner-token scheme, unchanged by this amendment.

### Follow-up 2026-09-30 — every post-mutation exit goes through A3 (#5385)

Mission `single-rollback-authority-01M3RCP4`, issue #5385. The A3 "remaining authorities" list
above is superseded by this follow-up.

- **One door.** One `try` in `_run_lane_based_consolidation_locked` covers every phase from
  `_phase_merge_lanes` through `_phase_reconcile_before_teardown`. A non-zero `typer.Exit`, any
  exception, or an interrupt (`BaseException`) calls `_report_rollback` →
  `rollback_to_snapshot`, then re-raises the original error. `typer.Exit(0)` passes through. If
  the rollback itself fails, or is interrupted by a second Ctrl-C, it prints "Rollback could
  not complete" and the original error still propagates. After a full rollback the merge record
  claims no completed WPs and no bake.
- **Retired.** `_reset_coord_to_checkpoint`, `_revert_coord_done_commit`,
  `_rollback_to_pre_mutation_checkpoint`, `_revert_orphan_target_bake_commit` and
  `_capture_pre_mutation_coord_checkpoint` are deleted. `_heal_pending_coord_reconcile` runs
  only at resume start. Remaining second restore paths: `_rollback_target_after_failed_reconciliation`
  (the gate FAIL/REFUSE target CAS restore) and `coordination/coherence.py::repair_coord_strand`.
- **Pin.** `tests/consolidation/test_single_rollback_authority.py` requires all 11 span phase
  calls inside the door (whose reporting handlers end in a bare `raise`, and whose `typer.Exit`
  handler reports only under an `exit_code` guard), forbids a `revert` argv in `executor.py`, and
  forbids the retired names in `src/`.
- **Protected-target preflight.** Before any branch moves (pre-lock), consolidate refuses a
  mission whose pending done bookkeeping the workflow mutation policy would refuse (for example
  a LANES mission recorded for protected `main`), with the policy's own code
  `PROTECTED_BRANCH_REFUSED`, message and remedy. It reads the recorded meta target, not
  `--target`; it applies only while some WP still needs its done write (an all-done resume is not
  refused); it honours `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`; `--dry-run` reports the same
  code. It reuses the transaction's own gate (`BookkeepingTransaction.preflight_refusal`,
  `status_write_refusal`), so there is no second protected-branch list. A
  `BookkeepingPolicyRefused` that reaches the command layer is printed readably, exit 1. When
  a merge record for the mission already exists (a `--resume`, or a re-run after a crash), the
  refusal does not claim that no branch moved; it names `spec-kitty consolidate --abort` to
  restore what an earlier attempt moved. A mission the probe cannot resolve (unresolvable
  context, unreadable `meta.json`) is an `Error:` line and exit 1, not a traceback.
- **orchestrator-api.** `orchestrator-api consolidate-mission` has its own lane consolidation
  path (`_execute_lane_merge`). It runs the same preflight before any gate or merge, on both its
  code-lane path and its planning-artifact-only closeout, and puts the policy's code, message
  and next step in its failure envelope.
- **Residuals (named, not closed).**
  - A `BookkeepingPolicyRefused` can still escape unrendered from `_record_operator_attestations`
    (inside the lock, before the snapshot, with `--attest-*`) and from post-gate phases.
  - The orchestrator-api path has no rollback door: a failure the preflight does not foresee
    (for example a legacy mission, which is not probed) still leaves its target advanced.
  - Legacy missions are not probed by the preflight.
  - A coord mission with a missing coord branch still fails closed after squashing (the door
    rolls it back).
  - A stale lane auto-rebased during lane consolidation keeps its merge commit after a rollback
    (lanes are report-only).
  - The resume-start heal is a forward revert that runs before the attempt; a later rollback
    treats it as the restore floor.
  - A checkout whose resync failed after its branch moved looks dirty and is reported NOT
    restored.
  - On a protected `single_branch` landing, the write checkout switched to the target stays there
    after a rollback.
  - Out of scope: #3536, #5371, #5372.

### Follow-up 2026-10-04 — presence axis, status-write guard, wider lag recovery (#5613)

Issue #5613, a hardening follow-up to #5569, #5570, #5571 and #5572. The rollback authority
is unchanged; this follow-up adds two refusals in front of it, widens the resume recovery and
names one teardown refusal.

- **Presence axis.** The reconciliation gate FAILs with `APPROVED_CONTENT_MISSING` and rolls
  back through `rollback_to_snapshot` when an approved code lane's own net change to a path is
  not on the target, the target left that path alone since the lane was cut, and no later
  approved lane built atop it superseded the path
  (`MergeOutcomeVerifier._approved_content_divergence`). It is strategy-independent. The
  typical cause is an operator who committed the staged deletions of a lagging checkout and
  then resumed. It does not judge a path the target also changed.
- **Status-write guard.** A coordination status write refuses before it writes
  (`coordination/status_surface_guard.py`, called by `BookkeepingTransaction`):
  `COORD_STATUS_SURFACE_DIVERGED` when the worktree's `status.events.jsonl` lost events its
  HEAD has committed, `COORD_STATUS_SURFACE_UNREADABLE` when the committed log is malformed,
  repeats an event id or cannot be read. Extra uncommitted lines are tolerated.
- **Lag recovery.** `consolidate --resume` recovers in place a coordination worktree, a mission
  worktree and a lane worktree that provably only lags its own HEAD, as it already did for the
  repository root checkout. Each is proven against its own entry in `pre_mutation_refs`
  (`pre_mutation_coord_sha` for the coordination worktree, `pre_mutation_target_sha` for the
  root). A resume-only preflight leg refuses a dirty worktree on the mission branch only when a
  lane remains to be consolidated or the worktree actually lags. A lag plus an operator edit in
  a non-root worktree is never reset; it gets patch-based advice.
- **`COORD_MOVED_AFTER_LANDING`, exit 75.** When the coordination branch (or the mission branch
  of a mission without coordination topology) moved after the landing was verified and the
  compare-and-swap delete kept it, `consolidate` renders the code as a message suffix and exits
  75. The landing is not rolled back. `orchestrator-api consolidate-mission` reports the code in
  `data["teardown_error_code"]` under its unchanged `PREFLIGHT_FAILED` envelope.
- **Remaining second restore paths.** The list of the 2026-09-30 follow-up gains one entry:
  resume recovery still performs a raw `git reset --hard HEAD`
  (`_recover_behind_head_primary_on_resume`), now on four checkout roles: repository root
  checkout, coordination worktree, mission worktree and lane worktree.
- **Residuals (named, not closed).**
  - The rollback's byte-restore leaves the coordination worktree's status files dirty; the
    status-write guard refuses on them, the rollback does not clean them.
  - Lane-branch deletes still use `git branch -D`.
  - A corrupt `state.json` falls back to the generic dirty-checkout advice.
  - The repository root checkout with a lag plus an operator edit keeps the stock "Commit,
    stash, or revert" remedy.
  - The earlier projection-window race (`ProjectionTeardownAbort`,
    `PROJECTION_TEARDOWN_ABORTED`) has no rendered refusal on `consolidate` and keeps exit 1.
  - The presence axis does not judge a path the target also changed since the lane was cut.
  - Out of scope: legacy and foreign strand-marker refusal codes; unwrapped remediation
    printing.

## Consequences

- **Positive.** A default-config command can no longer wedge an in-flight mission or push
  unreviewed code toward the mainline; `mission close` can no longer fabricate a completion
  record; one authority means a future fix in one command cannot silently diverge from the
  others. Closes the class, not the symptoms.
- **Cost / risk.** Merge now imports a status reader (via the `specify_cli.status` facade —
  battery-only `test_status_module_boundary` gate); preconditions must raise `typer.Exit(1)`
  in-executor to stay inside the fixed CLI error-translation chains (`merge.py:545-554`); a
  new pre-merge coord reset interacts with the resume-coherence and split-brain revert tests
  (`test_issue_2711_*`, `test_issue_2786_*`); new helpers/shifted lines may require an
  arch-battery re-pin (os-detect exemption, dead-symbol allowlist) in the same PR.
- **ATDD.** Each defect gets an issue-pinned `@pytest.mark.regression` test that is red
  through the pre-existing CLI entry point before the fix and green after.

## Alternatives Considered

- **Two independent point-fixes for #4764 and #4765 only.** Rejected (D1): leaves #4474/#2745
  and the broader non-transactional-completion tail open, and invites a future 6th "done"
  definition.
- **Rollback-only fix for #4764 (treat warn as intentionally permitting unapproved merges).**
  Rejected (D2): keeps the fail-open; unreviewed code still consolidates onto the mission
  branch. The operator ruled the terminal-lane invariant is hard regardless of mode.
- **Single `is_mission_completed` predicate for all three commands.** Rejected (D4):
  false-blocks normal merges and passes vacuously on `--resume`.

## References

- Issues: #4764, #4765, #4474, #2745; epic #3897 (parent), #1795 (#2745's lane-mechanics epic).
- Amendment 2026-09-29: #5338, #5318, #5332, #5296 (epic #5001); mission `kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/`; residuals #5385, #5371, #5372.
- Follow-up 2026-09-30: #5385; mission `kitty-specs/single-rollback-authority-01M3RCP4/`; out-of-scope follow-ups #3536, #5371, #5372.
- Follow-up 2026-10-04: #5613 (hardening of #5569, #5570, #5571, #5572).
- Mission: `kitty-specs/terminus-safety-invariant-01M2XFT7/spec.md`; Decision Moments
  `01M2XFVSK8JCCXMXCJNTBB0X5V` (scope), `01M2XFW9B71WKJ4XPCDCH8VYCQ` (warn semantics).
- Related (separate): #3967 (shared integration view, epic #3894), #4161 (`next` FSM),
  #4474-adjacent cleanup cluster #4753/#4754/#4762.
- Charter: DIRECTIVE_040 (structural intervention on recurring bugs), DIRECTIVE_044 /
  canonical-source-unification (single authority), DIRECTIVE_003 (decision documentation),
  DIRECTIVE_043 (close defect classes by construction).
