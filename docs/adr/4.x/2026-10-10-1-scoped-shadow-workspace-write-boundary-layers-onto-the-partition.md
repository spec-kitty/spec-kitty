---
title: 'ADR: a scoped workspace handle layers onto the coordination/primary partition (it does not replace it)'
description: 'The #3129 write-boundary class is one shared root cause; the fix is a capability-scoped write handle layered onto the existing partition (Option B), not a foreign shadow topology.'
status: Proposed
date: '2026-10-10'
---

**Status:** Proposed

**Date:** 2026-10-10

**Deciders:** Stijn Dejongh (owner, Option B chosen 2026-10-09), via the governed design-spike mission `scoped-shadow-workspace-write-boundary-01M4H5FQ` (merged in PR [#5986](https://github.com/spec-kitty/spec-kitty/pull/5986)). This ADR formalises and code-grounds that decision; it does not re-open it.

**Technical Story:** [#3129](https://github.com/spec-kitty/spec-kitty/issues/3129) — "scoped shadow workspaces: the shared root behind the worktree/write-path issue class" (design-spike, P1). The decision record and the options analysis live in the merged mission artifacts at `kitty-specs/scoped-shadow-workspace-write-boundary-01M4H5FQ/research.md` and `spec.md`. The first increment of the chosen direction already landed: PR [#5986](https://github.com/spec-kitty/spec-kitty/pull/5986) closed [#2334](https://github.com/spec-kitty/spec-kitty/issues/2334).

---

## Context and Problem Statement

Issue #3129 does not ask for an implementation. It asks the owner to classify a *write-boundary topology*: across fourteen issues framed as separate bugs, is the recurring root cause real, is it still live, and does a **scoped-shadow-workspace-handle boundary** — one where "the canonical tree is not merely off-limits, it is **not reachable** from the handle the agent holds" — **(A)** replace, **(B)** layer onto, or **(C)** prove incompatible with the current coordination/primary partition. ThickTicket's `internal/workspace/shadow.go` is the cited reference implementation of the alternative topology.

Three questions must be answered with code-grounded evidence before the direction can be recorded:

1. **Coherent?** — Is the #3129 cluster one genuine shared root cause, or fourteen unrelated bugs?
2. **Active?** — Is it still a live problem after thirteen of its fourteen point-fixes merged, #3128 shipped the fail-closed mitigation, and #2334 (the last open member) was addressed by #5986?
3. **Solvable by aligning to the existing design?** — Can it be closed by aligning to the enforced module chain and the single-canonical-authority / public-import SSOT seams, rather than by importing a foreign scoped-shadow-handle topology?

**Terminology (the CLAUDE.md footguns, named explicitly throughout).** `primary` here means the **PRIMARY partition** (the artifact-home set that lands on the Mission's `target_branch` for every topology) or the **repository-root checkout** — never the Primary Branch `main` unless stated. `merge` here means **branch integration** or **lane consolidation** — never publish-to-origin. `routing` here means **branch-target routing** (which branch/checkout a write lands on) and **placement** (kind + topology → surface) — never dispatch/model/event routing.

## The three-question verdict (code-grounded)

### 1. Coherent — YES

All fourteen issues share one property: **a command derives its write/read target from ambient location (cwd / the worktree it was invoked from) instead of from the Mission's stored declaration.** The evidence is structural, not anecdotal:

- The artifact-placement seam is *already* a clean, CWD-invariant authority. `PlacementSeam` (`src/mission_runtime/resolution.py`) and its `resolve_artifact_surface` / `resolve_action_context` projections derive the physical surface from `repo_root` + `mission_slug` (the stored topology, read via `meta.json`), "never from the current checkout"; the primary write-dir re-anchors through `get_main_repo_root(self.repo_root)`. `MissionArtifactKind` is partitioned into two home sets (`src/mission_runtime/artifacts.py`): a PRIMARY kind resolves to the Mission's `target_branch` for every topology, a COORD kind to the coordination surface, with `kind_is_coordination_residue` deriving coord-routing solely from the stored `MissionTopology` via `routes_through_coordination`.
- Ambient location enters **upstream of the seam**, not inside it: `repo_root` is seeded from `Path.cwd()` / `locate_project_root() or Path.cwd()` at CLI entry points; the write-side resolvers (`locate_project_root`, `resolve_canonical_root`, `get_main_repo_root` in `src/specify_cli/core/paths.py`) collapse worktree→primary, while the read-side `get_status_read_root` deliberately prefers the current worktree and carries a "READ paths only" contract; and `resolve_primary_branch` (`src/specify_cli/core/git_ops.py`) is biased to the checked-out branch when `meta.json` has no `target_branch`.
- The invariant is already load-bearing folklore: the hand-placed comment "never `Path.cwd()` (C-003/#2647)" is replicated across `coordination/transaction.py`, `status/emit.py`, and more. The invariant exists; it is enforced per-site, not by construction.

The thirteen merged point-fixes collapse into four recurring shapes (collapse-to-primary resolver reached at a read site; placement WRITE mis-routed by ambient cwd; a fail-closed location assertion bolted on; a guard that self-churns). None changed what a lane fundamentally *is* — a checkout sharing the object store and refs with every other checkout. That shared substrate is the permanent supply. **The cluster is one root cause.**

### 2. Active — YES, with reduced but non-zero residual risk

The supply is demonstrably not exhausting: the resolvers were never changed, only call sites; the defect recurred across structurally unrelated command families over quarters (#3051 called itself "the third confirmed command family hitting this exact mechanism"); two agents tripped it independently in one landing pass; and contributors repeatedly noted the point-fixes weren't closing the class.

What changed the risk profile but not the root cause:

- **#3128** added `enforce_checkout_identity` (`src/mission_runtime/checkout_identity.py`), a pure-path refusal. It is scoped to **one** WP-mutation chokepoint — `resolve_workspace_for_wp(write_intent=True)` (`src/specify_cli/workspace/context.py`), which only `implement`/`review` set true. It refuses rather than redirects, and it does not cover the ~20 read call sites or the other mutating commands (`doctor`, `move-task`, `add-history`, `record-analysis`, …).
- **#5986** closed #2334 by retiring the markdown WP Activity Log in favour of `status.events.jsonl`, removing the last known *second writer* for an artifact that already had one authoritative surface.

**Residual risk:** every mutating command outside the `implement`/`review` chokepoint still manufactures its write target from ambient location and is protected only by hand-placed per-site assertions. Any *new* mutating command re-exposes the identical defect by default. The class is quieter, not closed.

### 3. Solvable by aligning to the existing design — YES

The fix does **not** require importing ThickTicket's foreign topology (a shadow workspace living outside the object store, reached only through an `OpenShadowWorkspace` handle). It aligns to what the repository already enforces:

- The placement seam is the **single canonical authority** for read/write surface resolution and is already CWD-invariant. The defect lives strictly *upstream* of it, in the ambient `repo_root`/branch seed.
- The enforced module chain (`kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`) already owns the layers the fix touches: `mission_runtime` owns the placement authority, `specify_cli` owns the command-entry seeds. The write-side handle is the dual of a seam that already exists, reached through public imports — not a new foreign authority.

Aligning to the existing SSOT/modular design beats adopting a shadow-outside-the-store topology, because the latter removes the shared substrate on which the consolidation engine's correctness proofs are *defined*, and would require rebuilding them (see Option A below). This reconciles exactly with the owner's Option B.

## Decision Drivers

- **Single canonical authority** — close the class at the mechanism, not with a fourteenth per-site patch; the placement seam is the one authority to extend, not duplicate.
- **Architectural alignment / locality of change** — keep the fix inside the enforced module chain and the exact layer (command-entry + workspace resolution) the thirteen fixes already churn.
- **Preserve hard-won correctness** — the consolidation/rollback engine (CAS ref advance, approval-stamp bound, blob-attribution/closed-world axes, coordination-teardown CAS, the single rollback authority) carries proven, dearly-earned invariants and must not be rewritten to fix a workspace-resolution problem.
- **Graceful incrementalism** — the direction must land in independently-valuable increments behind the owner's pace, not as a big-bang cutover.

## Considered Options

- **Option A — scoped shadow handles *replace* the partition.** A lane becomes a shadow workspace outside the object store; the canonical tree is unreachable; `ApplyShadowMerge` is the single crossing point. Retires the coordination/primary partition and the whole `routes_through_coordination` machinery.
- **Option B — scoped shadow handles *layer onto* the partition (CHOSEN).** Keep the partition and the consolidation engine untouched. Add a capability-narrowed **write handle** as the only object an execution agent (`implement`/`review`) is given — the write-side dual of the placement seam — through which the canonical tree and sibling lanes are not addressable. Generalises #3128 from "resolve, then refuse on mismatch" to "only ever hand out a handle that cannot address the foreign tree."
- **Option C — incompatible; name reason X and take the cheaper structural step.** If a true shadow-outside-the-store boundary is judged incompatible, reason X is: *the consolidation engine's correctness proofs are defined over a single shared object store and ref namespace.* The cheaper structural step is a single typed, declaration-first `repo_root`/branch resolution entry at the command-entry layer, replacing the scattered `Path.cwd()` seeds.

## Decision Outcome

**Chosen option: Option B (layer a scoped capability handle onto the coordination/primary partition), with Option C's single declaration-first `repo_root`/branch entry as its first, independently-valuable increment.**

Option A is recorded as the deferred **north star** — the highest-value end state and the truest expression of the issue's argument — but it is a multi-mission programme (a new consolidation engine), not a spike follow-on, and is not started until explicitly commissioned. Option C is not a distinct destination: its structural step is subsumed as Increment 1 of Option B.

This is the owner's call, taken on 2026-10-09 and recorded in the merged mission artifacts. This ADR grounds it in current code and confirms the code does **not** contradict it: the placement seam being already CWD-invariant is precisely why the handle is a *layer* (narrowing what the agent can address) and not a *replacement* (which would have to re-home every lane's storage and rebuild the engine's proofs).

### Where the write boundary sits, and which SSOT seam owns it

- **The authority is the placement seam** (`src/mission_runtime/resolution.py` / `artifacts.py`), which already answers "which physical surface does this artifact live on" from the stored declaration. The scoped handle is its **write-side dual**: a capability object (conceptually a `WriteLocation`-like value in `mission_runtime`) that carries the *only* paths/branches an agent may touch, so a bare `git`/path write outside them has no handle to reach.
- **The boundary is installed at the command-entry + workspace-resolution layer** (`src/specify_cli/workspace/context.py` and the CLI entry points), the same layer the thirteen fixes already modify and the layer that today carries the "never `Path.cwd()`" invariant by hand.
- **Lanes stay lanes.** `routes_through_coordination`, lane consolidation, branch integration, rollback, and the approval-stamp bound are untouched. The handle changes *what an agent can address*, not *how lanes integrate* or *where they are stored*.

### Incremental roadmap

1. **Done — #2334 slice (PR #5986).** Retire the markdown WP Activity Log in favour of `status.events.jsonl`, eliminating the last known second writer for an already-authoritative surface. This was the first increment; it changed no write-path seam.
2. **Increment 1 (next, Option C's step, independently valuable).** A single typed "resolve the Mission's write target from its declaration" entry at the command-entry layer, replacing the scattered `Path.cwd()` seeds and folding in the hand-placed "never `Path.cwd()`" assertions. Closes the collapse-to-primary and mis-routed-WRITE shapes by removing the ambient seed; useful even if the full handle is never built.
3. **Increment 2 (design required before any structural step).** The capability-handle design proper — the write-side dual of the placement seam, generalised from #3128's single-chokepoint refusal to the mutating-command surface. A separately-commissioned mission with its own spec/design.
4. **Deferred north star (Option A).** Re-express consolidation over a shadow-outside-the-store model. Not started until explicitly commissioned.
5. **Separate track, any time.** SugarFang-style mirrored-shadow *provenance* (orthogonal to A/B/C) if the replayable-trust story is wanted — a new issue.
6. **Already in flight, non-blocking.** PR #5957 / #3215 binds the Shadow Clone *dev-env shell activation* to the current worktree; it operates at the shell layer, not the `src/**` write-path seam, and neither waits on nor blocks this decision.

### Consequences

#### Positive

- The §class defect converts from a per-call-site patch stream into a constructed boundary — the only thing shown to actually stop the supply.
- The consolidation/rollback engine keeps its proven invariants; none of Option A's engine-rebuild risk is incurred.
- Blast radius stays in the familiar command-entry + workspace-resolution layer, inside the enforced module chain.
- The direction degrades gracefully: Increment 1 is valuable standalone.

#### Negative

- Option B is still real work: every mutating command must be migrated to accept and honour a handle instead of a cwd-derived `repo_root`, and the read-preferring `get_status_read_root` must be kept legitimately read-only.
- It does **not** remove the shared object store (the permanent supply); it makes the foreign tree unaddressable *through the handle*, so a deliberate bare-`git` call outside the handle is still physically possible. Only Option A removes the substrate.
- The physical N-copies of tracked `kitty-specs/` files across worktrees remain (inherent to `git worktree` sharing one object store); the seam makes one surface authoritative but cannot make the other copies not exist.

#### Neutral

- #3128's refusal remains correct and in place; Option B generalises it rather than retiring it.
- `status.events.jsonl` stays an in-repo coordination artifact (an Option A migration would have to re-home it; Option B does not).

### Confirmation

The decision is validated if, after Increment 1, a newly-added mutating command cannot reach the collapse-to-primary / mis-routed-WRITE shapes without going through the single declaration-first entry (enforced by a non-vacuous architectural gate per Standing Order #5), and the per-site "never `Path.cwd()`" assertions can begin to retire. Confidence is high that the direction is correct (it matches the owner's call and the code grounding is consistent); the open design risk is sizing Increment 2's handle, deferred to its own mission.

## Pros and Cons of the Options

### Option A — replace the partition

**Pros:** the defect class becomes *unreachable*, not merely refused; "do not write to someone else's tree" becomes a property of the object graph; the shared-object-store supply is gone.

**Cons:** very high blast radius — consolidation is built entirely on shared refs and one object store; a shadow-outside-the-store model re-expresses CAS ref advance, the approval-stamp bound, blob-attribution/closed-world, the coordination-teardown CAS and the single rollback authority as a cross-repository problem. It is a new consolidation engine, not a seam swap, and also re-homes the in-repo status model. A programme, not a spike follow-on.

### Option B — layer onto the partition (chosen)

**Pros:** preserves the proven consolidation/rollback machinery and per-lane parallelism; converts the class from per-call-site patching into a constructed boundary; blast radius bounded to the layer the thirteen fixes already churn; degrades gracefully into independently-valuable increments.

**Cons:** moderate migration cost across every mutating command; does not remove the shared substrate (a deliberate bare-`git` write outside the handle stays physically possible); physical N-copies persist.

### Option C — incompatible; name reason X

**Pros:** the cheapest structural step (one declaration-first resolution entry) still attacks the supply by removing the ambient seed, and is valuable on its own.

**Cons:** strictly less than B — no capability handle, no unreachability; writes stay *possible*, merely *correctly targeted by default*; the self-churn / ambient-history shapes remain per-site. Chosen only as B's first increment, not as a standalone destination.

## More Information

- Decision record and full options analysis: `kitty-specs/scoped-shadow-workspace-write-boundary-01M4H5FQ/research.md` (code citations in its Appendix) and `spec.md`.
- Issue: [#3129](https://github.com/spec-kitty/spec-kitty/issues/3129). First increment: [#2334](https://github.com/spec-kitty/spec-kitty/issues/2334) via PR [#5986](https://github.com/spec-kitty/spec-kitty/pull/5986).
- The cheap mitigation it generalises: [#3128](https://github.com/spec-kitty/spec-kitty/issues/3128), `src/mission_runtime/checkout_identity.py`.
- Related in-flight dev-env work (non-blocking): PR #5957 / [#3215](https://github.com/spec-kitty/spec-kitty/issues/3215).
- Architecture: [execution-lanes.md](../../architecture/execution-lanes.md), [artifact-placement-seam.md](../../architecture/artifact-placement-seam.md); the `primary`/`merge`/`routing` disambiguations in [orchestration.md](../../context/orchestration.md).
