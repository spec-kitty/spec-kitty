---
title: Context-Threading Feasibility — Is the fix ADOPTION, not a new seam? (python-pedro lens)
description: "Python Pedro's feasibility lens on context-threading: whether the fix is adoption of an existing seam rather than a new one, with threading cost and tests."
doc_status: deprecated
updated: '2026-06-16'
---
# Context-Threading Feasibility — Is the fix ADOPTION, not a new seam? (python-pedro lens)

**Profile:** python-pedro (implementer — contract reading, call-graphs, threading cost, test scaffolding).
**Branch:** `research/naming-identity-ssot-strangler` @ spec-kitty 3.2.0 (read-only; no commit/switch).
**Date:** 2026-06-16.
**Builds on:** `00-OVERVIEW.md`, `python-pedro-implementation-feasibility.md`, `architect-alphonso-intended-design.md`, the CaaCS forensics.

## Directives applied (python-pedro)

- **DIR-010 Specification Fidelity** — every claim below is grep-verified against the code on this branch; I do NOT carry the operator's claim or issue prose un-checked.
- **DIR-024 Locality of Change** — threading is assessed seam-by-seam; I flag the god-object risk of widening any single context.
- **DIR-030 Test+Typecheck Gate** — each threading WP carries a focused fragment-consumption test; `IdentityFragment.__post_init__` is already a typed invariant to lean on.
- **DIR-034 Test-First** — the adoption tests are assertions that a consumer reads `context.identity.mid8` (not a re-sliced `[:8]`), written before the routing.
- **Tactic test-scaffolding-as-design-smell** — the re-derivation sites are NOT mock-heavy; they re-read `meta.json` inline. The fix is to *consume the already-resolved fragment*, which deletes the re-read, not to add mocks.

---

## OPERATOR'S CLAIM — VALIDATED (with one precision)

> *"The Context objects + consolidated API were built so branches/names thread through method
> chains as a value object, not re-derived per path. The fix is adoption, not a new seam."*

**Verdict: TRUE for the runtime/CLI surface.** The canonical value object —
`mission_runtime.context.ExecutionContext` (alias `ActionContext`) — was explicitly built as a
**doc-09 op-composite** of frozen, domain-owned fragments, and its docstring states the design
intent verbatim (`context.py:24-28`):

> *"`mid8` is derived **exactly once** (in `IdentityFragment`, as `mission_id[:8]`) and
> `target_branch` is resolved **exactly once** (carried on `BranchRefFragment`); no other call
> site recomputes either value."*

The builder `resolve_action_context` (`resolution.py:682`) assembles **all** fragments in a single
pass (`resolution.py:716-745`): `identity` (mid8), `branch_ref` (target_branch + the one
`CommitTarget`), `status_surface`, `workspace`, `artifact_placement`, `prompt_source`. The contract
is essentially complete (§1).

**The precision the operator's claim under-states:** the value object exists and is *built*, but it is
**almost entirely unadopted**. Across the entire codebase, exactly **one** fragment is ever read off a
returned context (`context.artifact_placement.placement_ref`, `implement.py:552`). Every other consumer
reads the **flat substrate fields** (`feature_dir` / `target_branch` / `workspace_path`) and **re-derives
mid8 / the status surface inline** — even when it is holding a context that already carries them. So the
fix is adoption, and the adoption is **~5% done**, not zero and not a missing seam.

---

## 1. The Context contract — COMPLETE, not missing-fields

I read every value object the operator named plus the canonical runtime context. The contract carries
**branch + name + mid8 + feature_dir + surface** — nothing forces re-derivation:

| Fragment (frozen) | Carries | Source |
|---|---|---|
| `IdentityFragment` | `mission_id`, **`mid8`** (single-derived; `__post_init__` enforces `mid8 == mission_id[:8]`), `mission_slug` | `context.py:84-114` |
| `BranchRefFragment` | **`target_branch`** (single-resolved), `coordination_branch`, `destination_ref: CommitTarget` | `context.py:117-130` |
| `WorkspaceFragment` | `primary_root`, `current_cwd`, `coord_worktree`, `execution_workspace`, `allowed_command_cwd` | `context.py:133-148` |
| `StatusSurfaceFragment` | `status_read_dir`, `status_write_dir` (the **surface**, carried per #1737 so consumers don't re-derive) | `context.py:151-162` |
| `ArtifactPlacementFragment` | `placement_ref: CommitTarget` (same ref status resolves to) | `context.py:165-174` |
| `PromptSourceFragment` | `prompt_source_dir` | `context.py:177-181` |
| `ExecutionContext` (flat substrate) | `feature_dir`, `target_branch`, `branch_name`, `workspace_path`, `mission_slug`, `lane`, `lane_id`, `execution_mode`, … + all six fragments attached | `context.py:184-230` |

The two consolidated-API value objects the operator pointed at are **narrower projections** of the same
data, also complete for their job:

- `ResolvedStatusSurface` (`surface_resolver.py:338`) — `surface_path` + `primary_anchor` + `.read_dir`
  property. Built precisely so "neither [consumer] re-derives the path (FR-005/#1821)". Complete for
  the status seam.
- `WorkspaceContext` (`workspace/context.py:148`) — the persisted per-lane JSON: `wp_id`,
  `mission_slug`, `worktree_path`, `branch_name`, `base_branch`, `lane_id`, … Complete for lane state.
  (Note: it carries `mission_slug` + `branch_name` but **not** a standalone `mid8` field — a lane
  consumer needing mid8 must read it off the `IdentityFragment`, not this object. That is a *correct*
  bounded-context boundary, not a gap: `WorkspaceContext` is the *workspace* projection, identity lives
  in `IdentityFragment`.)

**Conclusion: the contract is NOT incomplete.** mid8, branch, name, feature_dir, and surface are all
carried. Consumers re-derive **despite** the data being present, not **because** it is absent. This
flips the usual "incomplete-context-forces-re-derivation" diagnosis: here the seam over-delivers and the
callers ignore it.

## 2. The dashboard case — WHY it re-derives `mid8=mission_id[:8]` (scanner.py:438)

The dashboard is the **one consumer that genuinely cannot thread the runtime context** — for a
legitimate architectural reason, which is exactly why it re-derives:

- `scanner.py:313` imports from `surface_resolver` **only** the topology helpers
  (`classify_worktree_topology`, `read_worktree_registry`) for `gather_feature_paths` — it does **not**
  import `resolve_status_surface` or `resolve_action_context`. Grep confirms **zero** uses of
  `resolve_action_context` / `ExecutionContext` / `IdentityFragment` / `resolve_status_surface` in
  `src/specify_cli/dashboard/`.
- The re-derivation lives in a **different** function, `build_mission_registry` (`scanner.py:410-448`),
  which is a **bulk directory scan**: it walks every mission dir, reads `meta.json` raw via
  `_read_mission_identity` (`scanner.py:370`), and computes `mid8 = mission_id[:8]` at `:438`.
- **Root cause — it is not action-scoped.** `resolve_action_context` resolves **one** mission for **one**
  action (it takes `action=` + `feature=` and raises `ActionContextError` on any unresolvable mission).
  The dashboard enumerates **all** missions, including pseudo-key (legacy/orphan) ones that have no
  `mission_id` at all. There is no per-action context to thread; the registry is the dashboard's own
  read model.

**`mid8` is present in the runtime API (`IdentityFragment.mid8`) but absent from the dashboard's scan
path** — because the scan path never enters the runtime API. So the minimal fix is **not** "thread the
ExecutionContext into the dashboard" (impossible — wrong cardinality, and it would raise on legacy
missions). The minimal fix is:

> **Extract the single mid8 derivation (`mission_id[:8]`) into the `branch_naming` seam's `mid8()` /
> `resolve_mid8()` authority and have `build_mission_registry` call it.** `mid8()` already exists
> (`branch_naming.py:139` returns `mission_id[:8]`). The dashboard's `:438` becomes
> `mid8 = None if is_pseudo else mid8(mission_id)`. This is the **bare-`[:8]` routing** item randy
> flagged (OVERVIEW §2 "extra: bare `mission_id[:8]`") — the dashboard is one of its ~10 sites, NOT a
> context-threading case. **The static-slice fix already covers it.**

## 3. Threading feasibility per consumer class

There are only **7** `resolve_action_context` call sites total (grep-verified):
`implement.py:544`, `agent/context.py:135`, `agent/workflow.py:964`, `agent/mission.py:720`,
`feature_dir_resolver.py:60`, `runtime_bridge.py:3122` & `:3259`. The inline re-derivers cluster around
these. Cost to convert each from "read flat field + re-derive" to "consume the fragment":

| Consumer class | What it re-derives today | Threading move | Cost | Risk |
|---|---|---|---|---|
| **implement orchestrator** (`implement.py`) | Already calls `resolve_action_context` and reads `context.artifact_placement` (`:552`); but a **sibling helper** re-slices `mid8` at `:386` from a freshly re-loaded `meta.json` (it holds a `CommitTarget` but not the identity). | Pass `context.identity` (or `context.identity.mid8`) into the `:379-403` helper instead of re-reading meta + re-slicing. | **S** | LOW — same value, `__post_init__` guards equality. |
| **agent/mission orchestrator** (`agent/mission.py`) | `_…coord_target` helper receives `placement: CommitTarget` (`:767`) but then re-loads meta + re-slices `mid8 = raw_mid[:8]` (`:772`) to materialize the coord worktree. | Thread the `IdentityFragment` (or `mid8`) alongside `placement` into the helper signature. | **S/M** | LOW-MED — extra parameter through one call layer; the mid8 is identical. |
| **agent/workflow + agent/context + feature_dir_resolver** | Call the builder, then read flat `feature_dir` / `target_branch` only; do not re-derive mid8 but **discard** `identity`/`branch_ref`/`status_surface`. | Where they later re-derive a surface/branch, read it off the carried fragment. (Mostly already correct — `feature_dir_resolver` is a thin re-export; workflow routes `target_branch` through the context, `:946-964`.) | **S** | LOW — these are the *good* citizens; light touch. |
| **runtime_bridge** (`runtime/next`) | Two call sites; consume flat fields. | Same as above — opportunistic fragment reads. | **S** | LOW. |
| **dashboard** (`scanner.py`) | `mid8 = mission_id[:8]` (`:438`) in a bulk scan that never enters the context API. | **NOT a threading case** — route the `[:8]` through `mid8()` (static slice). | **S** | LOW — pure-function swap. |
| **status/aggregate, git/sparse_checkout, mission_type, doctor** (`aggregate.py:250`, `sparse_checkout.py:286`, `mission_type.py:643`, `doctor.py:3070/3162`) | Bare `mission_id[:8]` re-slices, none holding a context. | **NOT threading** — route through `mid8()` (static slice). | **S each** | LOW. |

**The god-object risk:** the operator's framing ("thread a *single* context everywhere") is the trap.
`ExecutionContext` is action-scoped and **raises** on unresolvable missions — it is the wrong shape for
the bulk/enumeration consumers (dashboard, aggregate). Threading it there would (a) fail on legacy/orphan
missions and (b) inflate the context into a god-object that must serve both single-action and
whole-repo-scan callers. **DIR-031 boundary:** keep the context action-scoped; for the bulk consumers the
fix is the *static* `mid8()` seam, not the context. Only the **4 action-scoped orchestrators** (implement,
agent/mission, agent/workflow, runtime_bridge) are genuine threading candidates — and 3 of them are
already 80%+ correct.

## 4. The reframed WP shape — and how it relates to the static slice

If the fix is threading/adoption, the WPs are:

```
WP-T1  Thread IdentityFragment.mid8 into the 2 action-scoped re-derivers      [adoption / S]
       - implement.py:379-403 helper: accept context.identity (mid8) instead of
         re-loading meta + [:8].
       - agent/mission.py:767-788 coord-target helper: accept the IdentityFragment
         alongside the CommitTarget it already receives.
       - Test: assert the helper consumes context.identity.mid8 (a context whose
         IdentityFragment.mid8 differs from a naive slug-tail slice proves the
         fragment is the source, not a re-derivation).

WP-T2  Consume carried fragments in the remaining action-scoped orchestrators  [adoption / S]
       - agent/workflow, agent/context, runtime_bridge: read branch_ref/status_surface
         off the carried context where they currently re-derive.
       - mostly verification + light routing.
```

**How this compares to the static slice (#2000 / #1993 / #1971):**

> **The threading WPs are a SUPERSET-by-completion, NOT a replacement.** The static slice and the
> threading slice attack the **same defect from two ends of the same data flow**, and they are
> **complementary, not competing**:
>
> - **Static slice = the WRITE/COMPOSE end.** `#2000` routes the 3 inline `<slug>-<mid8>` *composes*
>   through `mission_dir_name()`; the bare-`[:8]` rider routes the ~10 *derivation* sites through
>   `mid8()`; `#1993` extracts the lanes-dir *resolver*; `#1971` collapses the project-root resolver.
>   These fix sites that **produce** identity/paths.
> - **Threading slice = the READ/CONSUME end.** The action-scoped orchestrators already *have* a
>   resolved context carrying the answer; threading stops them **re-deriving** it.
>
> The two meet in the middle: once `mid8()` is the single derivation authority (static slice) AND the
> `IdentityFragment.mid8` is threaded into the consumers (threading slice), there is **exactly one**
> `mission_id[:8]` in the codebase — inside `IdentityFragment.derive` (`context.py:108-114`) and
> `branch_naming.mid8` — and the AST ratchet (OVERVIEW §"new guards") can ban every other `[:8]`.
>
> **Concretely:** the bare-`[:8]` rider in the static slice and WP-T1 in the threading slice **converge
> on the same lines** (`implement.py:386`, `agent/mission.py:772`). The static framing says "route the
> `[:8]` through `mid8()`"; the threading framing says "consume the already-resolved `IdentityFragment`."
> **The threading framing is strictly better at these two sites** — the context already carries the value,
> so consuming the fragment *deletes the meta re-read entirely*, whereas routing through `mid8()` keeps
> the re-read and only fixes the slice. **For the 4 action-scoped sites, thread the fragment; for the
> ~6 bulk/standalone sites (dashboard, aggregate, sparse_checkout, mission_type, doctor) that hold no
> context, route through `mid8()`.** Same ratchet closes both.

**Net:** adoption does NOT replace the static slice — it **completes** `#1993`'s spirit (the context is
the lanes-dir's analog) and gives `#2000`'s bare-`[:8]` rider a *better* fix at the 2 context-holding
sites. The mission shape from OVERVIEW §6 is correct; I recommend **annotating WP04 to prefer
fragment-consumption over `mid8()`-routing at the 2 sites that already hold a context**.

## 5. Risk — the byte-identical + C-LANES-1 traps when threading one context

The threading hypothesis's headline risk is **conflating the three artifact surfaces** by collapsing them
onto one context field. The good news: `ExecutionContext` **already separates them correctly**, and the
trap is only re-introduced if a threading WP reads the wrong fragment.

1. **C-LANES-1 (meta/primary ≠ status/coord ≠ lanes/coord) is PRESERVED in the contract, not conflated.**
   The context keeps the three surfaces as **distinct fragments**: `StatusSurfaceFragment.status_read_dir`
   (status/coord), `WorkspaceFragment.execution_workspace`/`coord_worktree` (lanes/coord), and the flat
   `feature_dir` (meta/primary). The `#1993` two-variable dance (`_lanes_feature_dir` stays COORD-aware
   while `feature_dir` falls back to PRIMARY for meta — OVERVIEW trap #2) maps **cleanly** onto two
   different fragments. **Threading risk:** a WP that reads `context.feature_dir` where it should read
   `context.status_surface.status_read_dir` silently re-creates the genesis split-brain
   (`implement.py:1009-1018`). Mitigation: the threading test must assert *which* fragment each consumer
   reads, not just that the value matches — a value match is byte-identical under flattened topology and
   would pass a naive test while masking the wrong-surface bug under coord topology.

2. **Byte-identical mid8 — guarded by construction.** `IdentityFragment.__post_init__` (`context.py:98`)
   **raises** if `mid8 != mission_id[:8]`, so threading `context.identity.mid8` is provably byte-identical
   to the inline `mission_id[:8]` it replaces. The only divergence risk is at the **declared-vs-derived**
   boundary: the inline sites at `agent/mission.py:772` and `implement.py:386` read **`meta.mission_id`**
   and slice, whereas a *correct* identity authority (`resolve_transaction_mid8`, already used at
   `agent/mission.py:395-402`!) prefers `meta.mid8` over the slice. **So the two surfaces inside
   agent/mission.py already disagree about mid8 provenance** — `:397` uses the fail-closed authority,
   `:772` uses a raw `[:8]`. Threading the single `IdentityFragment` (built from the declared
   `mission_id`) *resolves* this internal disagreement, which is a correctness **improvement**, but the
   parity test must pin the `meta.mid8`-present case to prove the threaded value matches the
   authority-resolved one (not just the raw slice).

3. **Action-scoped raise vs bulk tolerance (the cardinality trap, §3).** Threading the context into a
   bulk consumer would convert a tolerant enumeration into a hard failure on the first legacy/orphan
   mission (`resolve_action_context` raises `ActionContextError`). This is the C-LANES-1 boundary in a
   different guise: the context is a *single-action* projection and must not be forced to serve the
   *whole-repo* read model. Keep the dashboard/aggregate on the static `mid8()` seam.

---

## Bottom line

The Context value object exists, its contract is **complete** (mid8 + branch + name + feature_dir +
surface, all single-derived and carried), and the operator's "fix is adoption" hypothesis is **validated**
— with the sharpening that adoption is **~5% done** (one fragment read, at `implement.py:552`) and that
**only the 4 action-scoped orchestrators are threading candidates.** The dashboard and the other ~6 bare-
`[:8]` sites hold no context and must take the **static `mid8()` seam**, not the threaded context (forcing
the context there would create an action-scoped god-object that raises on legacy missions). Threading is a
**superset-by-completion** of the static slice: it does not replace `#2000`/`#1993`/`#1971`, it gives the
2 context-holding `[:8]` sites a *better* fix (delete the meta re-read, consume the fragment) and, together
with the static routing, leaves exactly one `mission_id[:8]` in the tree for the ratchet to enforce. The
sole real risk is reading the *wrong fragment* (meta/primary vs status/coord vs lanes/coord) and masking it
behind byte-identical values under flattened topology — so every threading test must pin **which fragment**
is consumed, not merely the resulting value.
