---
title: 'ADR: Terminus-Safety Invariant — gate-then-mutate-with-rollback across merge, accept, and mission close'
description: 'Terminus-safety invariant: completion commands gate-then-mutate with rollback on failure, enforced by one shared terminal-readiness authority.'
status: Accepted
date: '2026-09-19'
updated: '2026-09-19'
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
- Mission: `kitty-specs/terminus-safety-invariant-01M2XFT7/spec.md`; Decision Moments
  `01M2XFVSK8JCCXMXCJNTBB0X5V` (scope), `01M2XFW9B71WKJ4XPCDCH8VYCQ` (warn semantics).
- Related (separate): #3967 (shared integration view, epic #3894), #4161 (`next` FSM),
  #4474-adjacent cleanup cluster #4753/#4754/#4762.
- Charter: DIRECTIVE_040 (structural intervention on recurring bugs), DIRECTIVE_044 /
  canonical-source-unification (single authority), DIRECTIVE_003 (decision documentation),
  DIRECTIVE_043 (close defect classes by construction).
