---
title: 'ADR: CONSOLIDATED Write-Surface Wiring and `consolidate` as Canonical Lane-Consolidation Terminology'
description: 'Wires `TopologySurface.CONSOLIDATED` to the integrated tree with the phase derived internally, and fixes `consolidate` as the canonical word for the lane-consolidation sense.'
status: Accepted
date: '2026-07-30'
doc_status: active
kind: ADR
updated: '2026-07-30T00:00:00Z'
---

## Context and Problem Statement

PR #3076 shipped the write-side placement seam but deferred the CONSOLIDATED half of it.
ADR [2026-07-23-1](./2026-07-23-1-surface-vocabulary-two-domains-and-topology-surface-rename.md)
declared `TopologySurface.CONSOLIDATED` as a member and gave `translate_surface` a
**total** arm for it — every `TopologySurface` member has a translation entry, asserted
by `assert_surface_totality`. But `SurfaceLocations.consolidated` (the field that arm
reads) has never been populated in production: `translate_surface(CONSOLIDATED, …)`
raises `ValueError` rather than resolving anything, because no caller has ever supplied
the location. `resolve_placement_only` instead resolves PRIMARY-kind writes to the
mission's Target Ref (`target_branch`) unconditionally, regardless of lifecycle phase.

That gap is now load-bearing (issue #3033, P0). After a mission is consolidated
(lane-consolidation, "E1") and then published to trunk ("E2"), the Target Ref branch is
**deleted** — `spec-kitty merge`'s local consolidation only ever *keeps* lane branches
deleted, but the operator-driven publish-to-trunk step (PR + merge to the Primary Branch)
deletes the Target Ref itself. Post-consolidation evidence writes (an acceptance-matrix
verdict, a tracer finding, an issue-matrix update, a retrospective) still resolve against
that deleted ref, so `safe-commit`'s HEAD-vs-ref guard can never be satisfied and the
write fails or is refused. `spec-kitty review --mode post-merge` is the operator-visible
symptom; it performs no commit itself, so the fix is not there.

A second, narrower gap sits underneath the first: the codebase's overloaded `merge` (a
three-sense term already disambiguated by ADR
[2026-07-23-2](./2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md) —
lane consolidation / branch integration / publish-to-origin) has **no single-word
canonical replacement** for the lane-consolidation sense. Every line of new code or prose
that needs to name that sense precisely has to reach for a multi-word disambiguating
phrase ("local lane consolidation") rather than one word, which is exactly the friction
that lets "merge" creep back in for that sense (mission #3080). This mission
(`post-merge-write-authoring-finish-01KYRRM5`) lands only the "do not make it worse"
**foundation** of #3080 — this ADR's terminology decision, a glossary update, and a CI
drift-ratchet guard — sequenced before any of the functional CONSOLIDATED-wiring work.
The full command/code/docs rename (`spec-kitty merge`, `MergeState`,
`baseline_merge_commit`, …) stays #3080; this ADR explicitly does not perform it.

## Decision Drivers

* **Single write resolver** (ADR [2026-06-24-1](./2026-06-24-1-kind-and-topology-aware-artifact-placement.md)
  C-006) — `resolve_placement_only` is the one write authority; the fix must not add a
  parallel/second resolver, and must not thread a phase parameter through
  `PlacementSeam.write_target` or `commit_for_mission` (both must independently
  re-derive the identical phase from the same durable signal).
* **Squash-robustness** — a squash publish-to-trunk rewrites history, so the E1
  consolidation commit is not a commit-ancestor of the Primary Branch tip; any resolution
  keyed on commit ancestry produces a false refusal on the common publish path.
* **Terminology precision, extended** — ADR 2026-07-23-2 already applies "always name
  the sense" discipline to `merge`; this ADR extends that discipline by giving the
  lane-consolidation sense a canonical single word, so future code and prose can comply
  cheaply instead of reaching for a phrase every time.
* **Scope discipline** (C-005, C-012) — land the CONSOLIDATED wiring and the terminology
  foundation without widening into the full #3080 rename or into per-artifact-kind
  branching inside the resolver (which would reintroduce the call-site kind-conditioning
  C-006 forbids).

## Decision Outcome

**Chosen: wire `TopologySurface.CONSOLIDATED` as the phase-resolved integrated-tree
surface, and adopt `consolidate` / `consolidation` as the canonical term for the
lane-consolidation sense.** Two decisions, recorded together because the second becomes
load-bearing exactly where the first makes it real: wiring CONSOLIDATED is the point at
which the codebase needs to say "the tree lane consolidation produced" precisely and
repeatedly, in artifact names, log messages, and error text.

### Decision 1 — CONSOLIDATED surface wiring (design)

`SurfaceLocations.consolidated` is populated so `translate_surface(CONSOLIDATED, …)`
resolves the *integrated tree*, wherever it currently lives:

1. **Phase is derived internally, inside `resolve_placement_only`.** No phase parameter
   is threaded through `PlacementSeam.write_target` or `commit_for_mission` — both
   re-derive the identical phase from the same durable `meta.json` signal
   (`baseline_merge_commit`, landed on the Target Ref at E1) plus the Target Ref's
   existence. This preserves the single-write-resolver invariant: a threaded parameter
   would let the probe and the materializer disagree (probe says "routable", commit
   resolves to the deleted Target Ref — a split-brain that reproduces #3073-shaped
   residue). `resolve_placement_only` is the only resolver that computes phase; it is an
   input the resolver derives, not a second resolver.
2. **E1 (lane-consolidated, Target Ref still exists):** `consolidated` = the Target Ref
   tree — the same tree PRIMARY-kind writes already resolve to today. No behavior change
   on this leg.
3. **E2 (published-to-trunk, Target Ref deleted):** `consolidated` = the
   **repository-root checkout**, gated by a **content-presence** predicate — the
   mission's own committed artifact tree is present at `HEAD` (e.g. via `git cat-file -e
   HEAD:kitty-specs/<mission_slug>/meta.json`, or an equivalent committed marker) —
   **not commit ancestry**. A squash publish-to-trunk rewrites history so the E1
   consolidation commit is not a commit-ancestor of the Primary Branch; content-presence
   succeeds regardless of commit topology (squash, rebase, or merge-commit), and it does
   not hard-code "main" — it accepts any checkout that carries the consolidated content.
4. **E2 disambiguation** — "Target Ref absent" alone does not mean E2: a *pre-
   consolidation* mission whose Target Ref was never materialized also has an absent
   branch. E2 requires `baseline_merge_commit` present **and** the Target Ref absent
   **and** terminal-completion evidence a consolidation produces (all work packages
   `done` in the status event log and/or `mission_number` assigned). The foundation
   reader `get_feature_target_branch` stays unrouted — the branch-existence probe lives
   in the phase reader this wiring adds, not in that reader.
5. **Off-checkout refusal (FR-006).** When the phase signal says "consolidated" but the
   content-presence check fails on the *current* checkout, the write refuses with a
   recovery instruction rather than forcing a checkout (C-004). The named recovery
   branch is **derived, not hard-coded and not a SHA**: it reads the same
   branch-derived default the codebase already uses elsewhere for "the Primary Branch,
   whatever it is called" (`git symbolic-ref refs/remotes/origin/HEAD`, the pattern
   already in production at `src/specify_cli/core/git_ops.py:_origin_head_branch` and
   `src/specify_cli/git/protection_policy.py`) — never a literal `"main"` string and
   never a commit SHA, so the message stays correct on a repository whose default branch
   is not `main`.
6. **E2 routing is scoped, not blanket** (operator HiC decision, recorded here for
   citability). The CONSOLIDATED-surface routing this ADR wires applies to
   PRIMARY-kind writes and to the three coord-partition kinds named in scope —
   `ISSUE_MATRIX`, `TRACER_FILE`, `ACCEPTANCE_MATRIX` — **only**. `STATUS_STATE` and
   `DECISION_LOG` are **not** re-routed to CONSOLIDATED in E2: although both kinds pass
   through the same shared `resolve_placement_only` (per C-005, sharing one resolver is
   the point, not an exception to it), their pre-mission resolution is left unchanged by
   this wiring. This is deliberately non-regressive (C-005): `DECISION_LOG` is
   in-mission and is not an E2 write target by design, and `STATUS_STATE`'s existing
   resolution is out of this mission's scope (`emit.py` placement-routing, #3071, is
   explicitly excluded). Scoping the CONSOLIDATED destination to the four named kinds,
   rather than making every shared-resolver caller inherit E2 routing implicitly, avoids
   the per-kind branching C-006 forbids while still keeping the two untouched kinds
   verifiably unaffected.
7. **No new field.** This is not a ref-swap around CONSOLIDATED and it introduces no new
   `merge_target_branch` field; `translate_surface`'s existing total arm for
   `CONSOLIDATED` already exists (ADR 2026-07-23-1) — this decision is its first
   production wiring.

This decision extends ADR 2026-07-23-2, which named the `post-consolidation` phase and
the `CONSOLIDATED` surface and wired only the acceptance-verification side (negative
invariants deferred to a post-consolidation Op); it did not wire the write-routing side.
It re-affirms ADR 2026-06-24-1's C-006 (single write resolver): CONSOLIDATED is populated
inside the existing resolver, not by a parallel one.

### Decision 2 — `consolidate` / `consolidation` is canonical for the lane-consolidation sense (terminology, #3080 foundation)

`consolidate` / `consolidation` becomes the **canonical term** for `merge` **Sense 1** —
the `spec-kitty merge` local operation that folds completed lane branches into the mission
branch (glossary: [Lane Consolidation](../../context/orchestration.md#lane-consolidation)).
The other two senses are unaffected and keep their existing canonical names:

* `merge` / "branch integration" stays canonical for `git merge`
  ([Branch Integration / Git Merge](../../context/orchestration.md#branch-integration--git-merge)).
* "publish" stays canonical for the operator-only push-to-origin step
  ([Publish to origin/main](../../context/orchestration.md#publish-to-originmain)).

The bare word "merge" for the lane-consolidation sense becomes a **legacy alias**:
existing occurrences are grandfathered (they do not need to be rewritten by this
mission), but new code, new symbols, and touched prose must say "consolidate" /
"consolidation" for this sense (boyscouting, C-012). This is the same disambiguation
discipline ADR 2026-07-23-2 already applied when it named `CONSOLIDATED` instead of
`MERGED` for the surface member — this ADR gives that same choice a canonical prose word.

**Foundation now, full rename in #3080.** This ADR and its accompanying glossary update
(FR-015) and CI drift-ratchet guard (FR-016) are the entire scope landed here. They do
**not** rename `spec-kitty merge`, `MergeState`, `baseline_merge_commit`, or any other
existing public symbol — that full command/code/docs rename is issue #3080's scope.
Landing it here would explode this mission's scope for no P0 benefit; the foundation
exists so the overload cannot get *worse* while #3080 is pending, not so it is fully
resolved today.

## Consequences

### Positive

* #3033 (P0) is fixed at its root: post-consolidation evidence writes resolve through a
  wired CONSOLIDATED surface instead of an unconditionally-resolved, possibly-deleted
  Target Ref.
* The fix is squash-robust: a squash publish-to-trunk does not produce a false refusal,
  because E2 resolution never depends on commit ancestry.
* `STATUS_STATE` / `DECISION_LOG` resolution is unchanged, so the shared-resolver
  consequence (C-005) is non-regressive by construction rather than by incidental luck.
* Future code and prose gain a canonical, single-word way to name the lane-consolidation
  sense, lowering the cost of complying with the terminology canon and making genuine new
  drift ("lane merge", "merge the lanes", …) visible to a CI gate (FR-016) instead of
  silently accumulating.
* No new abort path is introduced into consolidation (consistent with ADR 2026-07-23-2);
  the off-checkout case (Decision 1 §5) is a refusal at write time, not a consolidation-
  time gate.

### Negative / accepted trade-offs

* The lane-consolidation sense of "merge" remains legally present in existing code and
  prose until #3080 lands the full rename — this ADR accepts a grandfathered baseline
  rather than forcing an immediate, scope-exploding rewrite.
* The content-presence predicate (Decision 1 §3) is a git subprocess call, only paid on
  the E2 leg (Target Ref absent) — NFR-004 requires it add no new subprocess on the
  pre-consolidation happy path, which the phase-gating in §1/§4 satisfies by construction
  but which a future change to the predicate must preserve.

### Neutral

* `SurfaceLocations.consolidated` was already declared (a `Path | None` field) ahead of
  this ADR; wiring it does not change its type or its place in the dataclass.

## Alternatives considered

* **Record a new `merge_target_branch` / `consolidation_ref` field at E1 and swap the
  Target Ref for it at E2.** Rejected: unnecessary scope. The content-presence predicate
  needs no new durable field beyond `baseline_merge_commit`, which already exists; a
  ref-swap is also the shape C-002 explicitly forbids ("NOT a ref-swap around
  CONSOLIDATED").
* **Commit-ancestry check (`git merge-base --is-ancestor baseline_merge_commit HEAD`) for
  E2.** Rejected: breaks under a squash publish-to-trunk, the common publish mode — the
  exact false-negative this ADR's Decision 1 §3 exists to avoid.
* **`git branch --contains` to find the checkout.** Rejected: the merge-base is an
  ancestor of every descendant branch, so this is maximally ambiguous and cannot
  distinguish a valid CONSOLIDATED home from an unrelated descendant.
* **Route `STATUS_STATE` / `DECISION_LOG` to CONSOLIDATED in E2 for symmetry with the
  other four kinds.** Rejected: out of scope (C-005 excludes `emit.py` placement-routing,
  #3071) and `DECISION_LOG` is intentionally in-mission-only; routing them would be an
  unrequested behavior change smuggled in under "consistency."
* **Do the full #3080 rename now, alongside the CONSOLIDATED wiring.** Rejected: C-012
  is explicit that this mission lands only the tidy-first foundation; renaming
  `spec-kitty merge` / `MergeState` / `baseline_merge_commit` touches a much larger,
  independently-scoped surface (command help text, CLI flags, serialized state shapes)
  that belongs to #3080, not to a P0 write-routing fix.
* **Pick "integrate" instead of "consolidate" as the canonical word.** Rejected: "branch
  integration" is already the canonical name for `merge` Sense 2 (the `git merge` step);
  reusing "integrate" for Sense 1 would create a new overload instead of resolving one.

## More Information

**Extends:** [2026-07-23-2 — Post-Consolidation Deferral and External Enforcement of
Negative Invariants](./2026-07-23-2-post-consolidation-deferral-and-external-enforcement.md)
(named `post-consolidation` / `CONSOLIDATED` and wired the acceptance-verification side;
this ADR wires the write-routing side and gives the lane-consolidation sense its
canonical word).

**Re-affirms:** [2026-06-24-1 — Kind- and Topology-Aware Artifact Placement](./2026-06-24-1-kind-and-topology-aware-artifact-placement.md)
C-006 (single write resolver — phase is derived inside `resolve_placement_only`, never a
second resolver, never a threaded parameter).

**Cites:** [2026-07-23-1 — Surface Vocabulary: Two Domains and `TopologySurface`
Rename](./2026-07-23-1-surface-vocabulary-two-domains-and-topology-surface-rename.md)
(declared `TopologySurface.CONSOLIDATED` and its total `translate_surface` arm, wired by
this ADR).

**Glossary:** [Lane Consolidation](../../context/orchestration.md#lane-consolidation)
canonicalizes `consolidate` / `consolidation` for this sense (FR-015); [Branch
Integration / Git Merge](../../context/orchestration.md#branch-integration--git-merge)
and [Publish to origin/main](../../context/orchestration.md#publish-to-originmain) are
unchanged.

**Issues:** [#3033](https://github.com/Priivacy-ai/spec-kitty/issues/3033) (P0 — post-
consolidation writes fail against a deleted Target Ref; Decision 1),
[#3073](https://github.com/Priivacy-ai/spec-kitty/issues/3073) (no-residue-on-refusal;
downstream of the CONSOLIDATED wiring, not this ADR's decision),
[#3080](https://github.com/Priivacy-ai/spec-kitty/issues/3080) (the full `consolidate`
rename; this ADR lands only its foundation — Decision 2), [#2653](https://github.com/Priivacy-ai/spec-kitty/issues/2653)
(the original `primary`/`merge` disambiguation this ADR's terminology decision extends).

**Mission:** `kitty-specs/post-merge-write-authoring-finish-01KYRRM5/` (WP01, FR-014/
FR-015/FR-016; the CONSOLIDATED wiring itself is executed by this mission's later work
packages — IC-03 through IC-07 of `plan.md`). Research: `research.md` D1-D5. Contract:
`contracts/authoring-commands.md` (Terminology foundation section).

**Canonical seams:** [`src/mission_runtime/resolution.py`](../../../src/mission_runtime/resolution.py)
(`resolve_placement_only`, `SurfaceLocations`, `translate_surface`,
`resolve_artifact_surface`), [`src/mission_runtime/artifacts.py`](../../../src/mission_runtime/artifacts.py)
(`TopologySurface.CONSOLIDATED`, `MissionArtifactKind`), [`src/specify_cli/coordination/write_seam.py`](../../../src/specify_cli/coordination/write_seam.py)
(post-consolidation write routing), [`src/specify_cli/core/git_ops.py`](../../../src/specify_cli/core/git_ops.py)
(`_origin_head_branch` — the existing `git symbolic-ref refs/remotes/origin/HEAD`
pattern the FR-006 recovery message reuses).
