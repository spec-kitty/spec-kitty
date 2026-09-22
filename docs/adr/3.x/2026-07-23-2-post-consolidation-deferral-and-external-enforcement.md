---
title: Post-Consolidation Deferral and External Enforcement of Negative Invariants
description: 'Negative invariants are verified externally at a named `post-consolidation` phase on the `CONSOLIDATED` surface, never at a step whose integrated tree does not yet exist.'
status: Accepted
date: '2026-07-23'
---

## Context and Problem Statement

ADR [2026-04-03-3](./2026-04-03-3-feature-acceptance-runs-on-the-integrated-mission-branch.md)
decided that *"Feature QA and `accept` MUST happen on the mission integration branch"*, and
specified the negative-invariant verifier model down to its result vocabulary.

**That decision was never enforced in code, and this ADR does not enforce it literally either —
it addresses the narrower failure the gap produces.** `spec-kitty accept` executes each negative
invariant's `verification_command` from the pre-merge **primary repository root**
(`src/specify_cli/acceptance/gates_core.py:298`, passing a bare `repo_root`). Pre-merge, the
primary tree cannot contain the mission's changes — they live on unmerged lane branches. An
honest invariant whose subject is something the mission *adds* therefore evaluates against a tree
where it structurally cannot be true, is recorded `still_present`, and blocks acceptance
(issue #1834).

The operator-visible consequence is documented and measurable:

* The workaround is to declare no invariants at all. The flagship mission merged immediately
  before this one (`coord-commit-integrity-01KY5JS8`) ships `negative_invariants: []`.
* Across the repository: **153 acceptance matrices, 40 non-`pending` negative invariants in 14
  missions, zero carrying any record of which surface established them.**

A partial fix landed in `b918e66df`: a *recorded* non-`pending` result is preserved rather than
re-judged. But `pending` is the scaffolded default, so an invariant nobody hand-recorded during
review still executes against the wrong tree. The failure was renamed, not removed.

Two further problems block a naive fix:

1. **There is no pre-merge integrated tree to run against.** For a multi-lane mission, lanes are
   independent branches; integration materialises only at lane consolidation. Making the
   verification `cwd` "workspace-aware" would require designating one lane's worktree as the
   integrated tree — fabricating exactly the authority this class of defect is about.
2. **`merge` is a three-sense overloaded term here** (lane consolidation / branch integration /
   publish to origin), so "defer it to merge" does not say which event is being waited on.

## Decision Drivers

* **Honour the existing ADR** — 2026-04-03-3 is Accepted; the gap is enforcement, not intent.
* **Never fabricate an evaluation surface** — a gate must judge a real tree or refuse.
* **Do not add abort paths to consolidation** — the merge executor's compensating-transaction
  machinery is being consolidated concurrently; a new abort trigger inside it is unsafe.
* **Terminology precision** — the name must state which event is awaited.
* **Honest enforcement** — an enforcer that cannot fire is worse than an admitted gap, because it
  reads as a guarantee.
* **Downstream truthfulness** — Spec Kitty runs in repositories that do not share this project's
  CI.

## Considered Options

* **Option 1:** Workspace-aware verification `cwd` — resolve an integrated tree pre-merge.
* **Option 2:** Never overwrite a recorded result (the `b918e66df` half-fix), and stop there.
* **Option 3:** Defer unjudgeable invariants to a **post-consolidation** phase, verified on the
  consolidated mission tree, enforced externally in CI and disclosed at assignment time.

## Decision Outcome

**Chosen option: Option 3.**

Option 1 is rejected as a fiction: the tree it depends on does not exist pre-merge for a
multi-lane mission. Option 2 is already landed and demonstrably insufficient — it protects only
invariants a reviewer remembered to record by hand, and a design that requires a discipline
reminder to enforce a constraint is structurally incomplete.

### Core Decision

1. **`post-consolidation` is the canonical name** for the phase, the surface (`CONSOLIDATED`), and
   the verification that runs there. The bare word *merge* is never used for it. This is the same
   disambiguation discipline already applied to `primary` / `main` / `base`, and is why the
   surface member is `CONSOLIDATED` rather than `MERGED` (see ADR
   [2026-07-23-1](./2026-07-23-1-surface-vocabulary-two-domains-and-topology-surface-rename.md)).

2. **A `pending` invariant whose subject cannot exist in the current surface is recorded
   `deferred_to_consolidation`** with a stated reason — never `still_present`. Deferral is a
   scheduled follow-up, not an absence of information.

3. **Every recorded judgement carries provenance** — the ref and the `TopologySurface` it was
   established against. A judgement without provenance is a validation error. This operationalises
   2026-04-03-3's requirement that evidence *"distinguish absence from verifier failure"*: it also
   distinguishes absence-here from absence-anywhere.

4. **`overall_verdict` gains a fourth value, `pass_pending_consolidation`.** The existing three
   have no assignment satisfying both "must not block acceptance" and "must not silently pass":
   allowing the deferred value yields `pass`, disallowing it yields `fail`, and grouping it with
   `pending` reproduces the block being removed.

5. **Verification runs after consolidation completes, as an ordinary governed Op**, and a violation
   fails **that Op** — not the consolidation. No new CLI verb: it is dispatched through the
   canonical surface (`spec-kitty dispatch`, closed via `profile-invocation complete`), single-agent
   or squad-based like any other. What distinguishes it is when it runs and what it checks.

6. **Enforcement is EXTERNAL to the mission loop.** A CI consistency check, at the front of the
   quality run, fails any pull request still carrying a dangling `deferred_to_consolidation`
   element.

7. **The deferral discloses its own contract at assignment time.** When Spec Kitty assigns
   `deferred_to_consolidation` it must state that the mission loop will not verify it and name the
   gate the operator needs.

### Why enforcement cannot live in the loop — measured

`overall_verdict` has exactly **one** consumer in `src/` (`acceptance/gates_core.py:311`), inside
the accept gate. `read_acceptance_matrix` is consumed only by `acceptance/gates_core.py` and
`acceptance/summary_core.py`. Both run **pre-consolidation**. Nothing reads the acceptance matrix
after `spec-kitty merge`.

An earlier candidate enforcer — *"the matrix cannot reach a terminal verdict while deferrals
remain"* — is therefore **circular**: it blocks at the only gate that reads the artifact, which is
the gate that created the deferral and which by design must not block on it. It is withdrawn and
recorded here so it is not re-proposed.

The pull request is the first point at which the consolidated tree and the acceptance artifact are
both present and something automated reads them. That is where the gate belongs.

### Why disclosure is a requirement, not a courtesy

Spec Kitty ships into other people's repositories, where this project's CI check does not exist.
An enforcement model that works only upstream, applied silently, would export the exact failure
this ADR removes: a gate that looks authoritative and verifies nothing. The tool must therefore
state the contract at the moment it assigns the status.

## Consequences

### Positive

* ADR 2026-04-03-3's intent is finally enforceable: acceptance judges the integrated product,
  because unjudgeable invariants wait for the integrated tree instead of failing against the wrong
  one.
* Command-verified negative invariants become usable, removing the incentive to ship
  `negative_invariants: []`.
* Consolidation gains no new abort path, so the concurrent consolidation of the merge executor's
  two compensating transactions is unaffected.
* Every judgement states its surface, so a reader can tell whether it is still meaningful.

### Negative / accepted trade-offs

* **Between assignment and the PR check, a deferred invariant is genuinely unverified**, and a
  repository that never adds the gate never verifies it. This is accepted as honest and visible,
  in preference to a constraint no code can express.
* Feedback arrives later than acceptance. Late-but-honest is preferred to early-but-wrong; the
  blast radius is bounded because the consolidated tree is the mission/PR branch, not the primary
  branch.
* A fourth verdict value and five new invariant fields require a one-time backfill migration
  across 153 existing matrices, plus an archive path for missions whose recorded state cannot
  migrate honestly — a migration that invented provenance for unknowable surfaces would itself be
  fabricating evidence.

### Neutral

* `deferred_to_consolidation` is not in older readers' `NEGATIVE_INVARIANT_RESULTS`, so an older
  Spec Kitty reading a new matrix computes `fail`. `pass_pending_consolidation` does **not** have
  this problem — `overall_verdict` is excluded from deserialisation and recomputed.

## More Information

* Supersedes nothing, and does **not** implement 2026-04-03-3 literally. That ADR's instruction
  is to relocate the whole `accept` step onto the mission integration branch; this ADR keeps
  `accept` where it is and defers only the **subset of judgements that cannot be true** on the
  pre-consolidation surface. It therefore realises 2026-04-03-3's *intent* — that acceptance
  judges the integrated product rather than an isolated slice — by a narrower mechanism, and
  leaves the relocation question open. Relationship: **inherits the intent of** ADR
  [2026-04-03-3](./2026-04-03-3-feature-acceptance-runs-on-the-integrated-mission-branch.md); does
  not discharge it.
* Surface vocabulary: ADR
  [2026-07-23-1](./2026-07-23-1-surface-vocabulary-two-domains-and-topology-surface-rename.md).
* Issues: #1834 (the live leg), #2885, #2795, #2882.
* Mission: `kitty-specs/lifecycle-gate-execution-context-01KY72GQ/`.
* User-facing guide: [accept-and-merge](../../guides/how-to/missions/accept-and-merge.md).

## Amendment (2026-09-22)

The **"do not add abort paths to consolidation"** principle — stated as a Decision Driver
("Do not add abort paths to consolidation", Decision Drivers, above) and reaffirmed under
Consequences ("Consolidation gains no new abort path", Positive Consequences, above) — is
**qualified, not reversed, for gate/verdict artifacts**. It continues to govern the general
consolidation path unchanged.

`kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/contracts/merge-driver-algorithm.md`
originally cited this ADR to justify a "structured conflict result (fail-closed, no
consolidation abort)" behavior for the row-aware matrix merge driver: a both-sides-diverged
field on a keyed row (e.g. `pass_fail`) was embedded as a git-style conflict-marker string
*inside the field value itself*, and the merge proceeded. For a **gate/verdict artifact**
(the acceptance matrix, the issue matrix) this reading was unsafe: an embedded marker string
in `pass_fail` is not human prose to review later, it is a value the artifact's own
verdict-computation logic reads — and it recomputed `overall_verdict` to `fail`, silently
corrupting an already-accepted mission's recorded state. That defect and its fix are tracked
under #4880.

**Amended rule:** for a gate/verdict artifact only, a both-sides-diverged keyed-row field is
unresolvable by machine and **fails closed** — the driver raises, the CLI invocation exits
non-zero, and `git merge` is left for a human to resolve (`git merge --abort` is available to
the operator; the mission integration path does not silently advance past it). Conflict
markers are never embedded as field values in a gate/verdict artifact.

This qualification is scoped narrowly: it does **not** apply to non-authoritative prose
artifacts (e.g. the review-cycle `.md`, whose verdict authority lives elsewhere), which keep
the original best-effort, no-abort behavior this ADR describes. It also does not reopen or
weaken any Core Decision item (1–7, including item 3's provenance requirement, which is
untouched by this amendment) or the general "no new abort path in the merge executor's
compensating-transaction machinery" principle for any surface other than gate/verdict
artifacts.

The originating contract and unit-gate mission
(`kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/...` and
`kitty-specs/gate-artifact-merge-driver-unit-gate-01KZPG7V/spec.md` FR-004) are **immutable
archived snapshots** and are deliberately NOT edited here — their original wording is
preserved as history. This amendment (a living governance record) is the authoritative
supersession of that "no consolidation abort" reading for gate/verdict artifacts; the new
behavior and the FR-004 supersession are recorded in the #4880 mission's own living
contract: `kitty-specs/acceptance-matrix-merge-fail-closed-01M34HG8/contracts/merge-driver-algorithm-amendment.md`.
