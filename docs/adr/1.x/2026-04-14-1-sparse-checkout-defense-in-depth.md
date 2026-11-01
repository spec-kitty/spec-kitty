---
title: 'ADR (2026-04-14): Sparse-Checkout Defence in Depth — Four-Layer Hybrid Preflight
  + Commit-Layer Backstop'
description: Repairs repositories still carrying git state from the retired 0.11-era checkout policy, adding preflight detection at four layers plus a guard against silent file loss.
status: Accepted
date: '2026-04-14'
doc_status: active
kind: ADR
updated: '2026-04-14T00:00:00Z'
---

## Context and Problem Statement

Between spec-kitty 0.11.0 and 2.x, the CLI actively managed git sparse-checkout
state on user repositories. The sparse-checkout pattern was designed to keep
`kitty-specs/` out of execution worktrees so coding agents would not see
planning artifacts as part of their working tree. In 3.0 (PR #347) the
sparse-checkout policy was removed, but **no migration was shipped to unwind
the sparse-checkout state already applied to existing user repositories**.

This produced a latent, fail-silent hazard in the wild. A repository upgraded
from a pre-3.0 CLI continues to carry a sparse-checkout pattern in
`.git/info/sparse-checkout` and `core.sparseCheckout=true` in `.git/config`,
even though the current CLI has no code path that sets them. The CLI also has
no code path that detects or unsets them.

The hazard manifested concretely in Priivacy-ai/spec-kitty#588: during
`spec-kitty mission merge`, the merge driver stashed working-tree changes,
performed the merge, and then restored the stash on top of a sparse-filtered
index. Paths excluded by the sparse pattern appeared "missing" from the index
relative to the stash, so the stash-pop operation **recorded deletions for
files that were never actually removed from the repository**. The subsequent
housekeeping commit captured those phantom deletions, silently reverting
content that the preceding merge commit had just introduced.

Two secondary issues compounded the primary hazard:

1. The lane-worktree review-lock code path required operators to pass `--force`
   to approve or reject a review even when the only uncommitted content was
   the execution lane's own `.spec-kitty/` scratch directory — a false alarm
   that trained operators to pass `--force` reflexively, eroding the guard's
   signal value (Priivacy-ai/spec-kitty#589).
2. The retry guidance emitted by the uncommitted-changes guard hardcoded
   `for_review` as the target lane, which was confusing when the guard fired
   during transitions to other lanes.

The architectural question posed by these findings is not "how do we patch
`mission merge`." The question is **where in the command surface should the
defence against sparse-checkout data loss live, given that the root cause is
legacy persistent git state that no single command can be assumed to own?**

## Decision Drivers

* The regression is silent and destructive — a commit lands with apparent
  success and the data loss is only visible after the fact.
* The cause is **persistent state on the user's disk** (git config +
  `.git/info/sparse-checkout` pattern) inherited from earlier CLI versions;
  any single-command patch is incomplete because the same state will re-enter
  any other command that performs index manipulation (stash, checkout, rebase).
* Spec-kitty 3.x intentionally has no sparse-checkout feature; the current CLI
  has no reason to ever emit or rely on sparse-checkout state.
* A small set of legitimate users may have independently configured
  sparse-checkout for their own reasons; they need an explicit escape hatch
  rather than a blanket block.
* The fix must be deployable without requiring users to run a separate
  migration command first — the next routine spec-kitty invocation should
  either detect and remediate, or at minimum refuse to proceed silently.

## Considered Options

* Option A — Pure merge-only preflight: gate `mission merge` on a sparse-checkout
  detection result.
* Option B — Blanket preflight gate on every state-mutating command.
* Option C — Four-layer hybrid: hard block at the two highest-leverage entry
  points, universal commit-layer backstop, session-scoped warning elsewhere,
  and `spec-kitty doctor` as the primary discovery and remediation surface.
* Option D — Reintroduce sparse-checkout as a supported feature and fix the
  stash-pop flow around it.

## Decision Outcome

**Chosen option: Option C — four-layer hybrid.**

### Decision

The defence is composed of four independent layers. Each layer has a distinct
role, and the composition is deliberate: removing any single layer leaves a
real regression path uncovered.

1. **Layer 1 — Hard block at `mission merge` and `agent action implement`
   (WP05).** These are the two highest-blast-radius entry points: merge
   integrates multiple lanes into the target branch, and implement creates or
   updates the lane worktree that carries per-WP work. Both run a
   sparse-checkout preflight and fail closed on detection unless the operator
   passes `--allow-sparse-checkout`. Merge additionally performs a post-merge
   refresh and invariant check to catch any phantom-deletion commit before it
   leaves the integration branch.

2. **Layer 2 — Universal commit-layer backstop in `safe_commit` (WP01).**
   Independent of any preflight, `safe_commit` inspects the staging area for
   any path outside the expected set (determined from the commit's intended
   scope) and aborts the commit with a diagnostic if a mismatch is found. This
   is the layer that catches the sparse-stash-pop phantom-deletion cascade
   regardless of which command initiated it, and it cannot be bypassed by
   command flags. It is the backstop that makes the mission recoverable even
   if a future command path forgets to call the preflight.

3. **Layer 3 — Session-scoped warning at other state-mutating CLI surfaces
   (WP06).** Review-lock transitions (`approve`, `reject`) and task-command
   sessions emit a one-shot session warning when sparse-checkout state is
   detected. These surfaces do not block (blocking would be redundant with
   Layer 2 at the commit boundary and would degrade UX), but they surface the
   condition early, before the operator wastes a commit cycle. The warning is
   emitted at most once per process.

4. **Layer 4 — `spec-kitty doctor` is the discovery and remediation surface
   (WP04).** The `sparse-checkout` finding is surfaced in `doctor` output with
   a `--fix` action that removes `core.sparseCheckout` from git config, clears
   the `.git/info/sparse-checkout` pattern file, and verifies post-fix state.
   This is the surface operators are pointed at from the other three layers,
   and it is the migration recipe for users on repositories upgraded from
   pre-3.0 spec-kitty.

The `--allow-sparse-checkout` flag emits a `WARNING`-level structured log
record (`spec_kitty.override.sparse_checkout`) at use time but does not
currently emit a durable audit event. Adding a durable audit event requires
coordinated work in `spec-kitty-events` and `spec-kitty-saas`; that follow-up
is tracked as Priivacy-ai/spec-kitty#617.

In addition:

* The review-lock guard no longer requires `--force` to approve or reject a
  lane-worktree review when the only untracked content is the lane's own
  `.spec-kitty/` scratch directory (Priivacy-ai/spec-kitty#589).
* Retry guidance emitted by the uncommitted-changes guard now names the
  actual target lane rather than hardcoded `for_review`.
* Every lane worktree carries a per-worktree git exclude entry for
  `.spec-kitty/` written at worktree creation (WP07), so future scratch
  content stays invisible to the working-tree guard even in worktrees
  initialised before the fix.

### Consequences

#### Positive

* The #588 data-loss regression is closed at the commit layer (Layer 2)
  regardless of which command initiated it, which means the commit-layer
  backstop is a safety net even for future command paths that forget to call
  the merge/implement preflight.
* The #589 reflexive-`--force` training loop is broken: operators stop learning
  to bypass guards, so the guards retain signal value.
* Legitimate sparse-checkout users retain an explicit escape hatch at
  `--allow-sparse-checkout`, with a logged record of its use.
* Repositories upgraded from pre-3.0 spec-kitty have a documented, one-command
  migration via `spec-kitty doctor --fix sparse-checkout`.
* The fix is discovery-biased: Layer 3's session warning surfaces the
  condition early on routine activity, so affected repositories find out
  before hitting a merge.

#### Negative

* `safe_commit` now has a fail-closed assertion that may surface legitimate
  edge cases in existing callers that pass an intentionally broader scope;
  WP01 included an audit of existing callers, but future callers need to be
  aware of the contract.
* The `--allow-sparse-checkout` override emits only a structured log record,
  not a durable audit event. Log collectors and shell redirection cover the
  short-term audit need; durable audit is tracked as #617.
* Four layers is more surface area than a single gate. The trade-off is
  deliberate: a single gate would leave a real hazard uncovered.

#### Neutral

* This ADR does not reintroduce sparse-checkout as a supported CLI feature;
  Option D is explicitly rejected below. The layers exist to defend against
  legacy persistent state, not to support current sparse-checkout workflows.
* The four layers share a common detection primitive (WP02) and a common
  remediation module (WP03); composition, not duplication, drives the layer
  count.

### Confirmation

This ADR is considered implemented when all of the following are true:

1. `safe_commit` aborts commits that stage paths outside the intended scope
   (backstop verified by WP01 tests).
2. `mission merge` and `agent action implement` fail closed on detected
   sparse-checkout state, with `--allow-sparse-checkout` as the documented
   escape hatch (WP05 preflight tests).
3. `spec-kitty doctor` reports a `sparse-checkout` finding when detection
   fires and `--fix sparse-checkout` removes the state and verifies post-fix
   (WP04 tests).
4. Review-lock approve/reject and task-command sessions emit a one-shot
   session warning on detection and do not block (WP06 tests).
5. Lane-worktree approve/reject does not require `--force` when the only
   untracked content is `.spec-kitty/` (WP06 tests mirroring SC-003, SC-004).
6. Retry guidance names the actual target lane rather than hardcoded
   `for_review` (WP06 tests).

## Pros and Cons of the Options

### Option A — Pure merge-only preflight

Add sparse-checkout detection as a precondition on `mission merge` only.

**Pros:**

* Minimal surface change.
* Targets the exact command where the #588 regression manifested.

**Cons:**

* Misses the lane-worktree inheritance hazard: a worktree created by
  `agent action implement` inherits the repository's sparse-checkout state
  and can silently produce the same stash-pop cascade during any index
  manipulation inside that worktree.
* Misses the external-pull cascade: a user pulling a merged branch into a
  clone that still carries legacy sparse-checkout state experiences the same
  class of phantom deletions on subsequent commits.
* Leaves `safe_commit` as an unprotected surface: any future command that
  composes stash + merge + commit without calling the preflight reintroduces
  the hazard.

**Why Rejected:** The hazard is persistent-state-driven, not command-driven.
A per-command gate cannot enumerate all current and future callers.

### Option B — Blanket preflight gate on every state-mutating command

Gate every command that mutates git state on sparse-checkout detection.

**Pros:**

* Broad coverage.
* Single mental model ("every state mutation checks first").

**Cons:**

* Redundant with Layer 2 at the commit boundary; `safe_commit` already runs
  for every commit path.
* Degrades the UX of the escape hatch: legitimate sparse-checkout users must
  pass `--allow-sparse-checkout` at every command, not just the high-blast
  entry points.
* Surfaces the block in contexts where detection does not imply imminent
  harm (e.g., read-only status queries), training operators to bypass
  reflexively — the exact pathology #589 is fixing.

**Why Rejected:** More surface does not mean more safety. The backstop at the
commit layer already covers what a blanket gate would cover, at lower cost.

### Option C — Four-layer hybrid

Hard block at high-leverage entry points (Layer 1), universal commit-layer
backstop (Layer 2), session-scoped warning elsewhere (Layer 3), and `doctor`
as the discovery and remediation surface (Layer 4).

**Pros:**

* Each layer has a distinct role and a distinct failure mode it covers.
* The commit-layer backstop is the true universal defence; it cannot be
  bypassed by command flags and it catches the exact phantom-deletion
  signature regardless of initiator.
* High-leverage commands fail closed with actionable guidance; low-leverage
  commands surface the condition without blocking.
* `doctor` is the single migration entry point, which is the correct surface
  for legacy-state remediation across all spec-kitty projects.

**Cons:**

* More surface area than a single gate.
* Requires operators to understand the layer composition to diagnose edge
  cases — documented in the status-model docs and the recovery recipe in
  `CHANGELOG.md`.

**Why Chosen:** It is the only option that covers the full hazard surface
(merge, implement, lane-worktree inheritance, external-pull cascade, future
command paths) while preserving a clean escape hatch for legitimate use and
a single migration surface for legacy repositories.

### Option D — Reintroduce sparse-checkout as a supported feature

Restore the 0.11.0-era sparse-checkout management code and fix the stash-pop
flow around it.

**Pros:**

* Preserves the original motivation (keep `kitty-specs/` out of execution
  worktrees).

**Cons:**

* Explicitly out of scope per C-001 of the mission spec: spec-kitty 3.x
  intentionally has no sparse-checkout feature; the per-worktree exclude
  mechanism (WP07) covers the original motivation at lower cost.
* Does not help users on repositories that have legacy sparse-checkout state
  from earlier CLI versions — those users are already in the hazardous state,
  and bringing back the feature does not migrate them off it.
* Reintroduces a large failure surface that 3.x intentionally removed.

**Why Rejected:** The goal is not to restore sparse-checkout; the goal is to
defuse the legacy state it left behind.

## More Information

Relevant repository evidence:

* Primary regression: Priivacy-ai/spec-kitty#588 — phantom-deletion cascade
  in `spec-kitty mission merge`.
* Review-lock reflexive-`--force` fix: Priivacy-ai/spec-kitty#589.
* Durable audit event follow-up: Priivacy-ai/spec-kitty#617.
* Mission spec: `kitty-specs/legacy-sparse-and-review-lock-hardening-01KP54ZW/spec.md`.
* Decision Log (spec §12) records the three entries that back this ADR:
  the layered-hybrid decision, the `--allow-sparse-checkout` vs `--force`
  distinction, and the structured-log-instead-of-durable-audit decision.
* Historical context commits:
  * `d0c158f4` (v0.11.0) — introduction of sparse-checkout management.
  * `8f5b56ed` (v0.15.0) — sparse-checkout consolidation into the VCS layer.
  * `5d238657` (v3.0.0, PR #347) — removal of the sparse-checkout policy
    without a migration for existing user repositories (the root cause of
    the persistent-state hazard).

Implementation surfaces (by WP):

* WP01 — `safe_commit` backstop (Layer 2).
* WP02 — sparse-checkout detection primitive, session warning, preflight API
  (shared foundation for Layers 1, 3, 4).
* WP03 — remediation module (shared foundation for Layer 4's `--fix`).
* WP04 — `doctor` finding + `--fix` action (Layer 4).
* WP05 — merge and implement preflights + post-merge refresh (Layer 1).
* WP06 — review-lock approve/reject without `--force`, task-command session
  warning (Layer 3 + #589 fix).
* WP07 — per-worktree `.spec-kitty/` exclude writer + once-per-process
  external session warning (Layer 3 hardening).
* WP09 — this ADR, `CHANGELOG.md` recovery recipe, and the #588 diagnostic
  comment (FR-021, FR-022).
