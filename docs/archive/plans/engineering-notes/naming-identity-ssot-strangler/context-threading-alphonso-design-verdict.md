---
title: Context-Threading — Architect Alphonso Design-Intent Verdict (3.2.1)
description: "Architect Alphonso's design-intent verdict on context-threading (3.2.1): adjudicating the operator's claim for the naming/identity SSOT strangler."
doc_status: deprecated
updated: '2026-06-16'
---
# Context-Threading — Architect Alphonso Design-Intent Verdict (3.2.1)

**Author:** Architect Alphonso (design-intent lens — operator-claim adjudication)
**Branch:** `research/naming-identity-ssot-strangler` @ spec-kitty 3.2.0 (read-only; no commit/switch)
**Date:** 2026-06-16
**Question:** is the intended SSOT a *Context-value-object + consolidated-API* design, and is the
operator's framing architecturally correct?

> **Governance (architect-alphonso).** Directives applied: **DIR-001** (Architectural Integrity —
> one owning module per concern; the Context builder is that module; duplicates are seams to
> strangle), **DIR-003** (Decision Documentation — every verdict below carries authority/contract/
> rationale + a code or design-doc citation), **DIR-031** (Context-Aware Design — the coord/primary
> split is a *bounded-context boundary preserved through an explicit translation layer*, never
> collapsed; over-threading a single context across that boundary would re-fork it), **DIR-032**
> (Conceptual Alignment — terms keyed to CLAUDE.md canon: Mission Identity Model, C-LANES-1, the
> #1619 consolidated domain model, doc-09 fragment vocabulary). Builds on:
> `00-OVERVIEW.md`, `architect-alphonso-intended-design.md`, `caacs-alphonso-forensic-synthesis.md`.

---

## 0. The operator's claim, restated for adjudication

> *"We had considered the read paths, and a consolidated API (also consumed by the dashboard). The
> new coordination and ContextObjects were created explicitly for dealing with this → branches and
> names passed through method chains as a context value object, rather than recalculated/re-derived
> in multiple paths."*

**Hypothesis under test:** the SSOT is ALREADY a *compute-once-thread-through Context* design; the
split-brain is **non-adoption** (consumers re-derive instead of threading), not a missing SSOT.

**Verdict (one line): SUPPORTED.** The intended SSOT is *exactly* a Context-value-object +
consolidated-builder design; it is documented, designed, and **substantially implemented in code**;
the residual split-brain is **non-adoption** of that Context by peripheral consumers (the dashboard
chief among them). The operator's mental model is architecturally correct and matches the code's own
in-source comments. Two precise caveats keep this from being unconditional (→ §5).

---

## 1. Is the Context-threading design the INTENDED SSOT? — **YES, and it is in code.**

This is not aspiration in a design doc — it is **written into the running code as the named
contract.** Three independent sources align:

### 1a. The design intent (doc-09 §4, the north star)

The #1619 context-decomposition model states the compute-once-thread-through composite design as the
target verbatim:

> *"The object passed through the API is an operation-specific composite that selects only the
> fragments that operation needs. The composite is a **deep module** (small interface); the fragments
> are its hidden structure."* — `runtime_and_state_overhaul/09-context-decomposition-model.md:143–146`

> *"a fragment is **not a data bag**. It encapsulates its domain's **derivation rules** … That is the
> deep-module discipline applied per domain — the four duplicated path-builders (`02`) collapse into
> the Filesystem fragment's rules."* — `09:46–52`

The dialectic (doc-11) then **refuted the greenfield framing and re-homed the design onto an existing
object**, which is the decisive point for the operator's claim:

> *"composed domain-owned context **already exists**. `ActionContext` composes `action, mission_slug,
> feature_dir, target_branch, wp_id, lane_id, branch_name, execution_mode, workspace_path, commands,
> dependencies` — the fragments we proposed — backed by an accepted ADR (2026-03-09-1: 'Prompts do not
> discover context. Commands do.'). … The `09` 'fragments' become the **internal structure of a
> hardened `ActionContext`**, not six new public objects."* — `11-dialectic-and-revised-claims.md:121–143`

> *"The single biggest correction: the redesign is **consolidation onto `ActionContext`**, not a
> greenfield context family."* — `11:156`

And the consolidated baseline (doc-17 §2) ratifies the names: **ExecutionContext (≈ hardened
ActionContext), built via the Shared Kernel** (path · identity · status resolvers as OHS facades) —
`17-consolidated-domain-model.md:40–48, 116`.

### 1b. The contract, IN CODE (the smoking gun)

`src/mission_runtime/context.py:185` — `ExecutionContext` (aliased back to `ActionContext` at `:262`
for the strangler shim) is precisely the doc-09 op-composite, and its docstring **states the
single-derivation, thread-don't-re-derive rule as the contract**:

> *"The canonical surface is expressed over **this object**, never over loose path fragments:
> consumers receive a resolved context and **never reconstruct** the mission-spec directory from
> `main_repo_root` + the specs dir name + `mission_slug` themselves (FR-009)."* — `context.py:187–192`

It carries the doc-09 fragments as first-class members (`identity`, `branch_ref`, `workspace`,
`status_surface`, `artifact_placement`, `prompt_source` — `context.py:222–227`), each a **frozen
value object** (`@dataclass(frozen=True)` at `:66/:84/:117/:133/:151/:165/:177`).

The identity fragment encodes the **single derivation point** for mid8 — the exact thing the
dashboard re-derives — and *enforces* it with an invariant:

> *"`mid8` is the **single derivation point** for the 8-char branch/worktree disambiguator … `mid8` is
> single-derived (FR-012 / C-CTX-3)."* — `context.py:88, 95–104`; `IdentityFragment.derive(... mid8=mission_id[:8])` `:108–112`; `__post_init__` raises if `mid8 != mission_id[:8]`.

### 1c. The builder, IN CODE (compute-once, thread-through)

`src/mission_runtime/resolution.py:682 resolve_action_context(...) -> ExecutionContext` is the doc-09
§5 central builder (`build_mission_context(selector, *, op_kind, cwd)`), and its in-source comments
**are the operator's claim, verbatim**:

> *"`target_branch` is resolved exactly once here and threaded onto both the flat substrate field and
> the BranchRefFragment; **no downstream surface re-derives it**."* — `resolution.py:712–714` (FR-012 / C-CTX-3)

> *"route the prompt-source dir through the single read primitive's resolved `feature_dir` **so
> consumers never re-derive it** (FR-012)."* — `resolution.py:721–724`

> *"the artifact-placement ref is the SAME CommitTarget status events resolve to (C-PLACE-1) … **so no
> surface re-derives** a parallel primary/coord placement (C-005)."* — `resolution.py:728–731`

**Translation-layer fitness (DIR-031).** This is the *right* pattern for the coord/primary bounded
context. The builder resolves topology **once**, at the boundary, through the C-005 read primitive
(`resolve_mission_read_path`) and the status surface resolver, and hands the consumer a resolved
context. Consumers do not each re-walk the coord→primary fallback ladder — that ladder is the
explicit translation layer, and the Context is its single materialized output. This is exactly
"commands resolve context, prompts consume it" (ADR 2026-03-09-1) generalized to *all* consumers.

**Verdict 1: SUPPORTED.** The intended SSOT *is* a Context value object computed once by a central
builder and threaded through method chains. It is documented (doc-09/11/17), ADR-backed
(2026-03-09-1), and **implemented** (`ExecutionContext` + `resolve_action_context`, with FR-012/
C-CTX-3/C-005/C-PLACE-1 single-derivation invariants written into the code).

---

## 2. Reconcile with the CaaCS finding — **non-adoption IS the precise mechanism.**

The CaaCS forensic synthesis (`caacs-alphonso-forensic-synthesis.md`) established, from churn ×
defect-density × temporal-coupling, that **the authorities are cold and the consumers are infernos**:

- SSOT resolver modules: low churn (4–19), but **`surface_resolver`/`_read_path_resolver` are ~100%
  defect** (every touch is a fix) — `caacs §1a/1b`.
- `implement.py` (the inline-juggling consumer) is a **top-5 repo hotspot (churn 93, 82% defect)** and
  the **temporal-coupling fan-out hub** — `caacs §1a/1c`.
- *"the cost is paid by the consumer, every time, because the boundary leaks … the behavioral
  fingerprint of a **missing seam**"* — `caacs §1a`. Net boundary finding: *"the disease is projection
  scatter on the read/entry side … 38 files re-derive mission surface inline"* — `caacs §2`.

**Reconciliation — the operator's intuition and the forensics are the same fact from two angles:**

| Lens | Statement | Same underlying fact |
|---|---|---|
| Operator (design) | "we built a Context to thread, not re-derive" | the SSOT (the thread-through Context) **exists** |
| CaaCS (forensic) | "authorities cold, consumers re-derive, 38-site projection scatter" | the SSOT exists but is **not adopted** at the call sites |

The forensic phrase *"missing seam"* needs one refinement the design verdict supplies: it is not that
the seam is **absent** — `ExecutionContext` + `resolve_action_context` **is** the seam, with the
single-derivation invariant in code. It is that the seam is **un-adopted**: the cold authority is the
*available* Context; the hot consumers re-derive **instead of consuming it**. That is precisely
"non-adoption of the Context," and it is the exact, named mechanism behind the consumer-side
re-derivation split-brain. The cost lands on the consumer (CaaCS) **because** the consumer re-derives
rather than threads (operator) — one disease, two instruments confirming it.

**The dashboard is the textbook specimen.** `dashboard/scanner.py` **does** consume the consolidated
surface resolver (`from specify_cli.coordination.surface_resolver import …`, `scanner.py:313`) — so it
has *partially* adopted the Context API on the **path/surface** axis — **yet still re-derives identity
inline**: `mid8 = mission_id[:8]` at `scanner.py:438`, bypassing `IdentityFragment.mid8` (the named
single-derivation point at `context.py:88`). It also re-derives `worktree_root = feature_dir.parents[1]`
(`scanner.py:571`) instead of carrying the resolved workspace fragment. The dashboard is half-threaded
(surface ✓, identity ✗) — the cleanest possible illustration that the disease is *non-adoption*, not a
*missing* SSOT: the very file the operator named as a Context consumer adopted the API on one axis and
re-derived on another.

**Verdict 2: SUPPORTED.** Non-adoption of the existing Context is the precise mechanism behind the
consumer-side re-derivation split-brain. The CaaCS "missing seam" sharpens to "**un-adopted seam**" —
the authority is cold *because* it is bypassed; the consumers are infernos *because* they re-derive.

---

## 3. The consolidated API (dashboard too) — **intended single API exists; current pair is necessary but not the whole of it.**

**Is there an intended single consolidated read/identity API both dashboard and CLI consume?**
**Yes** — and it is *layered*, which is the part a naive reading misses:

- **Tier 0 — the Context object (the consolidated API the operator means).** The single thing a
  consumer should accept is the **resolved `ExecutionContext`** from `resolve_action_context`. That is
  the consolidated *identity + path + surface* API: identity via `IdentityFragment` (mid8 single-
  derived), path via `feature_dir`/`status_surface.status_read_dir`, branch via `branch_ref`. Doc-09
  §4 calls these the per-op composites (`ReadContext`/`WriteContext`/…); doc-17 §2 calls it
  ExecutionContext built via the Shared Kernel.
- **Tier 1 — the Shared-Kernel resolvers underneath it.** `resolve_mission_read_path` (C-005 read
  primitive) and `resolve_status_surface[_with_anchor]` are **OHS facades the builder calls** — they
  are the *materials*, not the consumer-facing API. (doc-17 §2 row "Shared Kernel"; `09:46` "Shared
  Kernel is a code module that builds Contexts.")

So the `resolve_mission_read_path` / `resolve_status_surface` pair is **real and consolidated on the
read/surface axis** (this is what `00-OVERVIEW §3 row D` and my intended-design note both call "read
side consolidated"), but it is **deliberately not the whole consolidated API** — it is the kernel the
Context builder consumes. The operator's "consolidated API also consumed by the dashboard" is most
precisely the **Context object**, with these resolvers as its supply chain.

**Is it incomplete for the dashboard?** **Yes — on the identity axis.** The dashboard reaches Tier 1
(it imports `surface_resolver`) but **does not accept a Tier-0 Context**, so it re-mints identity
(`mid8`) and workspace root (`parents[1]`) by hand (`scanner.py:438, 571`). The consolidated API
*exists*; the dashboard's **adoption of it is partial** — it consumes the surface facade but not the
identity fragment / full Context. That is the incompleteness, and it is an adoption gap, not an API
gap.

**Verdict 3: SUPPORTED-with-nuance.** The intended single consolidated API is the **resolved Context
object** (`ExecutionContext` via `resolve_action_context`), supplied by the
`resolve_mission_read_path`/`resolve_status_surface` kernel pair. The pair is consolidated on the
read/surface axis but is the *kernel*, not the consumer API; the dashboard's incompleteness is
**partial adoption** (surface yes, identity no), i.e. it still re-derives mid8.

---

## 4. The reframe — **correct, with two binding guardrails.**

**If the claim holds (it does), the 3.2.1 mission reframes** from *"build a new naming/identity seam"*
to:

> **THREAD the existing Context (`ExecutionContext` from `resolve_action_context`) and CONSUME the
> consolidated kernel everywhere; RETIRE inline re-derivation; RATCHET the re-derivation classes
> shut.**

This is the **correct architectural framing**, and it is already the shape of the squad's recommended
slice — the WPs are adoption/routing/ratchet, *not* greenfield construction:

- WP04/WP-α (route composes + ~20 bare `mission_id[:8]` sites through the seam, shrink+extend the
  ratchet) = **retire identity re-derivation** = adopt `IdentityFragment.mid8`. `00-OVERVIEW §6`.
- WP02/WP-β (#1993 extract `resolve_lanes_dir`) = **the first bounded cut draining the inline-juggling
  hotspot** = make `implement.py` consume a resolved surface instead of re-deriving topology.
- WP03/WP-δ (#1971 + `parents[N]`) = **retire project-root re-derivation** onto `core/paths`.
- The ratchet *is* the adoption oracle: a shrinking allow-list proves consumers have been threaded.

So the reframe does **not** change the slice's *membership* — it changes its *narrative and
justification*: we are not inventing an SSOT, we are **completing the adoption of one that exists and
is partly enforced**. That is a lower-risk, byte-identical, no-shadow-path framing, and it is the one
the spec's risk section should carry (CaaCS §6: "the static squad named the right SSOTs … the
forensics re-order and resize, do not overturn").

### Bounded-context guardrails (DIR-031) — do NOT over-thread

Threading a Context is right; threading **too much** through **one** object is the failure mode that
re-creates the very split-brain. Four guardrails:

1. **Don't make ExecutionContext a god-object.** Doc-09 §4 is explicit: composites are **op-specific
   selectors over fragments** (`ReadContext` ≠ `WriteContext`); a fragment is `None` when the op does
   not consume it (`context.py:223–227`). The deep-module discipline (small interface, hidden
   fragments) is the anti-god-object rule. A single Context carrying *every* field for *every* consumer
   becomes a data-bag that every caller must still partially rebuild — re-leaking the boundary. **Keep
   it a deep module; select fragments per op; never expose the fragments as a sprawling public API**
   (doc-11:143; doc-09 §7 "≤ a few contexts").

2. **Identity ≠ Path — two authorities, threaded separately on one object.** `IdentityFragment`
   (mid8, "name proposes, authority disposes") and the path/surface fragments are **distinct
   authorities on the same composite**. Threading them through one object is fine; **conflating them**
   (letting a path heuristic mint identity, or deriving mid8 from a slug on a correctness path) is the
   genesis bug (`implement.py:1009–1018`, doc-09 §2). The Context must carry *both, distinctly* — never
   collapse them into one "feature_dir-knows-all" field. (CLAUDE.md Mission Identity Model; my
   intended-design §4 boundary list.)

3. **C-LANES-1 — three artifact surfaces stay three fragments, not one threaded path.** meta/primary
   ≠ status/coord ≠ lanes/coord. The Context carries `status_surface` (status), the read primitive's
   `feature_dir` (meta/primary), and (post-#1993) a lanes-dir surface — **three fragments, one
   composite**. Threading "the Context" must NOT mean threading *one fused path*; that re-creates the
   #1991/genesis surface-collision. The composite holds three surfaces; the consumer picks the right
   one. (doc-09 §4 obs 1; `00-OVERVIEW §3 guardrails`.)

4. **Coord/primary stays a translation layer the builder owns — don't thread the topology decision
   into consumers.** The whole point is that the *builder* resolves coord→primary **once** and the
   consumer threads the *result*. The anti-pattern is "thread enough context that each consumer can
   re-decide topology" — that is just re-derivation with extra steps. The Context carries *resolved*
   surfaces, never the *inputs to re-resolve them*. (#1878 non-goal: no topology redesign; the
   translation layer is preserved, its output is threaded.)

**Verdict 4: SUPPORTED.** The reframe ("thread the existing Context + consume the kernel everywhere;
retire re-derivation") is correct and is already the slice's de-facto shape. The over-threading /
god-object guardrail is real and binding: keep ExecutionContext a **deep module of op-selected,
distinctly-authored fragments** (identity≠path; three surfaces; builder-owned topology), never a
single fat path threaded into consumers that still re-decide.

---

## 5. Final verdict — **SUPPORTED** (with two precise caveats)

**The operator's claim is SUPPORTED.** The intended SSOT for branch/name/mid8/feature_dir **is** a
compute-once-thread-through *Context value object* (`ExecutionContext`/`ActionContext`), assembled by
a single central builder (`resolve_action_context`) from Shared-Kernel resolvers, with the
single-derivation rule (FR-012 / C-CTX-3 / C-005 / C-PLACE-1) **written into the code as the
contract** and partly enforced by invariant (`IdentityFragment.__post_init__`). The split-brain is
**non-adoption** — peripheral consumers (the dashboard most visibly) re-derive identity/path inline
instead of threading the Context — exactly as the hypothesis stated and exactly as the CaaCS forensics
independently located it.

**The precise architectural statement (what exists / what's intended / the gap):**

- **EXISTS:** `ExecutionContext` (doc-09 op-composite of frozen fragments; `context.py:185`),
  `resolve_action_context` (central builder; `resolution.py:682`) with in-source "resolved once,
  threaded, no downstream re-derive" comments; the C-005 read primitive + status surface resolver as
  the kernel; ADR 2026-03-09-1 ("commands resolve context, prompts consume it"); the `mid8`
  single-derivation invariant.
- **INTENDED:** *every* consumer — CLI and **dashboard** — accepts the resolved Context (or, for
  surface-only consumers, the kernel facade) and **never re-mints** mid8/feature_dir/branch/worktree
  inline; the ratchet's shrinking allow-list is the adoption oracle.
- **THE GAP:** the Context is **not threaded to the periphery**. Concrete, named non-adoption sites:
  `dashboard/scanner.py:438` (`mid8 = mission_id[:8]`, bypassing `IdentityFragment`),
  `scanner.py:571` (`parents[1]` worktree root), the ~20-site bare-`[:8]` class, the 3 inline composes
  (#2000), the inline `_lanes_feature_dir` in `implement.py:974` (#1993), and the read/entry
  projection scatter (~38 files, CaaCS §1d). The authority is cold; the consumers re-derive.

**Two caveats that keep this from being unconditional:**

1. **The Context is implemented but its ADOPTION + IMMUTABILITY are unfinished.** The flat substrate
   fields are *still present* alongside the fragments (`context.py:201–219`, NFR-001 strangler
   substrate), and `ExecutionContext` is a **mutable `@dataclass` (not frozen)** while its *fragments*
   are frozen. The doc-11 mandate ("make it **immutable**, complete the topology split, **enforce its
   use**") is **partly done** — fragments exist and are frozen, but the composite is still a mutable
   transitional shape with a flat substrate consumers can read instead of the fragments. So the SSOT is
   *real and load-bearing* but **mid-strangler**: the 3.2.1 work is finishing the adoption + freeze, not
   building the object.

2. **"Consolidated API" is layered — the dashboard adopted the kernel but not the Context.** The
   `resolve_mission_read_path`/`resolve_status_surface` pair is the **kernel** (consolidated on the
   read/surface axis), not the consumer-facing Context; the dashboard consumes the kernel facade yet
   still re-derives identity. Calling the *pair* "the consolidated API" understates it — the consumer
   API is the **Context**, and the dashboard's gap is **partial adoption** (surface yes, identity no),
   not a missing API.

**Does this change the 3.2.1 slice? No — it sharpens its framing, not its membership.** The WPs are
already adoption/routing/ratchet, not construction. The reframe the operator's claim mandates is a
**spec-narrative change**: write the mission as *"complete the adoption of the existing thread-through
Context — route the re-derivation classes onto `IdentityFragment.mid8` / the read primitive / the
Shared Kernel, finish the immutability + flat-substrate retirement begun by the strangler, and ratchet
each class shut"*, **not** *"design and build a new naming/identity seam."* The one concrete sizing
rider for the spec: include **`dashboard/scanner.py` in the ratchet's repo-wide reach** (CaaCS §5 —
89% defect, carries both un-routed classes) so the completeness oracle has no hole, even if the
scanner's full refactor stays in the #1878 read-projection follow-on.

---

## 6. Decision-documented summary (for the mission spec's justification section)

> **Ship the 3.2.1 slice as a Context-ADOPTION mission, not a Context-CONSTRUCTION mission, because
> the design says X and the code proves X.** **X = the compute-once-thread-through Context already
> exists and is partly enforced.** Doc-09/11/17 define it; ADR 2026-03-09-1 backs it; `ExecutionContext`
> (`context.py:185`) + `resolve_action_context` (`resolution.py:682`) implement it with in-source
> single-derivation invariants (FR-012/C-CTX-3/C-005/C-PLACE-1) and a `mid8` `__post_init__` guard. The
> split-brain is **non-adoption**: the dashboard (`scanner.py:438`) and ~38 consumers re-derive
> identity/path inline instead of threading the Context — which is *also* what the CaaCS forensics found
> (cold authorities, infernal consumers, projection scatter). Therefore the mission **threads the
> existing Context and consumes the kernel everywhere, retires inline re-derivation, finishes the
> immutability/flat-substrate strangler, and ratchets each re-derivation class shut** — keeping
> `ExecutionContext` a **deep module of op-selected, distinctly-authored fragments** (identity≠path;
> three C-LANES-1 surfaces; builder-owned coord/primary translation), never a fat path threaded into
> consumers that still re-decide topology. The slice's *membership* is unchanged; its *framing and risk
> story* change from "build a seam" to "**finish adopting the seam that exists.**"
