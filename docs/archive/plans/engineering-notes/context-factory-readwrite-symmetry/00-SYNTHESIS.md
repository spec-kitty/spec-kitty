---
title: Execution Context Factory — Read/Write Symmetry & Multi-Mission Approach
description: Design refinement (2026-06-16) on the execution context factory's read/write symmetry and multi-mission approach, informing the read-path-error-fidelity mission.
doc_status: deprecated
updated: '2026-06-17'
---
# Execution Context Factory — Read/Write Symmetry & Multi-Mission Approach

> **Retired (deprecated).** Read-side design shipped/superseded via merged mission `read-path-error-fidelity-adoption-01KV8NPC` (`kitty-specs/read-path-error-fidelity-adoption-01KV8NPC/`); write-side (#1716 / #1878) deferred. Preserved as a historical record.

**Date:** 2026-06-16
**Status:** design refinement (informs the read-path mission `read-path-error-fidelity-adoption-01KV8NPC`
and the deferred write-side follow-on #1716/#1878)
**Basis:** six profile-loaded opus investigations under
`kitty-specs/read-path-error-fidelity-adoption-01KV8NPC/research/investigation-2/` (design-validation)
and `…/investigation-3-readwrite/` (read/write symmetry). This note is the cross-mission synthesis.

---

## 1. The keystone question

> "Assuming we route the read path through the new SSOT (the context-object API), how do we ensure the
> **write path** follows the same logic? The intent was for read/write execution paths to get their
> information through those context objects — built from a **single source/factory** that encapsulates
> the logic (naming, etc.)."

The operator also raised a prior doubt: *are we even going to use the Context passthrough + central API?*
Both are answered below.

## 2. Verdict: KEEP-AND-ADOPT (the API is the intended SSOT, under-consumed — not vestigial)

The central API (`resolve_action_context` → `ExecutionContext`/`IdentityFragment`,
`src/mission_runtime/{resolution.py,context.py}`) is the **designed, triple-ADR-ratified, operator-decreed
single read-path door**:

- ADR `2026-03-09-1` ("Prompts do not discover context. Commands do") — one shared resolver door; reject
  per-prompt rediscovery.
- ADR `2026-06-03-2` Decision 1 — *"the existing OHS entry point is structurally correct; it needs
  consumers, not replacement."*
- ADR `2026-06-07-1` — *"`resolve_action_context` … the single resolution entry point …
  `ActionContextError` — the only error type consumers catch."* Design intent = **verbatim pass-through**:
  resolved once per operation, passed to callees as a value object, no callee re-derives.

Robert's #2007 architecture-alignment rules **corroborate**: *"main expected outcome is adoption of the
existing typed context/read-path authority … do not build a new monolithic resolver … C3 (typed-error
preservation) is the center of mass … #2007 C3 should consume #1619/#1666, not fork them."*

**The operator's "do we intend to use it" worry is not founded — but it is under-consumed.** randy's census:
of the 6 doc-09 fragments, only `artifact_placement` is read on the read path today; adopted:bypassed ≈
**1:6**. The fragments are unread **because the write path (and full read adoption) was never wired** — not
because they are wrong.

## 3. The symmetry insight: construction is already single-sited; naming is already consolidated

- **One constructor.** There is exactly **one** production `ExecutionContext(` call —
  `resolution.py:739`, inside `resolve_action_context` — plus one post-construction mutator (`:800-808`,
  the WP-bearing branch). "One factory" is therefore not something to *build*: it is **naming** that
  existing site (`build_execution_context`), **freezing** the product, and making it the **sole door**.
- **Naming is already the single composer.** `src/specify_cli/lanes/branch_naming.py` (missions 01KV6510 /
  01KV7SFD, the naming-rider) is the consolidated name grammar; coordination, worktree, lanes, and merge
  already route through it. The factory **calls** `branch_naming` as a collaborator — it does **not**
  absorb it (that re-opens #2012's bounded context).
- **The real asymmetry is altitude, not grammar.** The read path consumes identity/topology via *fragment
  assembly* (`_assemble_core_fragments`, resolved once). The write path runs a **second parallel factory**
  (`coordination/status_transition.py::_identity_for_request` + `CoordinationWorkspace`) that re-derives
  identity, root (`feature_dir.parent.parent`), and placement **by hand**. The residual is
  **root-resolution + placement + write-surface selection**, not naming.

## 4. The fragment reversal (corrects the read-only census)

randy's read-side "RETIRE-WIDE" (delete the 5 unread fragments) is **reversed by the write-symmetry goal** —
the unread fragments are precisely the **write-side adoption surface**:

| Fragment | Read-side today | Under write-symmetry |
|----------|-----------------|----------------------|
| `workspace` | unread | **strong reversal** — `primary_root` re-derived via `.parent.parent` at ≥5 write sites (`status/emit.py:392` literally comments it) |
| `status_surface` | only `status_read_dir` read | **decisive reversal** — the `status_write_dir` half is exactly what `status_transition` needs |
| `branch_ref` | silent | **reverses** — `destination_ref = coord_branch or current_branch` is the write-target selector |
| `identity` | partial | **softens** — mid8 funneled through `resolve_mid8` already (function-level single point) |
| `artifact_placement` | read (the 1 of 6) | already load-bearing (#1784/#1816) |
| `prompt_source` | unread | **holds RETIRE** — genuinely vestigial both paths |

**Decision: keep identity/branch_ref/workspace/artifact_placement; retire only `prompt_source` + the dead
`StatusSurfaceFragment surface=` read-param wiring (`status/aggregate.py:262/309`).**

## 5. Multi-mission approach (the strangler, sequenced)

**Mission A — read-path / error-fidelity adoption (`…-01KV8NPC`, in flight):**
- Adopt the read path onto the SSOT; preserve `ActionContextError` end-to-end (closes #12/#14/#15).
- **Re-scope IC-01** from "freeze + assert invariant" → **"establish the single named factory
  (`build_execution_context`) + freeze + assert `target_branch == branch_ref.target_branch` +
  declare the write-projection boundary contract."** Same owned files (`mission_runtime/{context,resolution}.py`),
  ~15–60 LOC, ≤7 subtasks. This lays the seam so the write side later adopts **against a frozen factory —
  no rewrite**.
- Fix the read-path behavioral bugs (#4/#6/#7/#8) + fold the 3 net-new surfaces (§6).
- **Keeps D-1 (DEFER #1716), C-001 (build no new authority), NFR-005 (bounded surface).**

**Mission B — write-side topology adoption (#1716 + #1878, follow-on):**
- Adopt the write path against the frozen factory seam: route the ~10–13 write re-derivation sites
  (~90–130 LOC, concentrated in root-walk + placement) to consume `workspace.primary_root` /
  `branch_ref.destination_ref` / `status_surface.status_write_dir` from the factory-projected context.
- This turns the currently-unread fragments load-bearing — completing the strangler. It is **adoption,
  not construction**, precisely because Mission A froze the seam + declared the boundary contract.
- The bounded now-routable subset randy flagged (`status/emit.py`, `work_package_lifecycle.py`,
  `lifecycle_events.py`, `store.py` root walks + `core/worktree.py` placement join) is the natural first
  slice of Mission B.

**The boundary contract (declared in Mission A's IC-01, enforced in Mission B):** *write surfaces compose
names/paths/identity from a factory-projected `IdentityFragment` + `BranchRefFragment` (+ workspace/surface);
they MUST NOT re-derive `mission_id`/`mid8`/`primary_root` independently. `branch_naming` is the grammar
collaborator; the factory is the identity/topology authority that feeds it.*

## 6. Net-new missed surfaces (debbie, fold into Mission A)

All 5 originally-pinned bugs still reproduce on HEAD (byte-stable lines); #1827 remains test-only. Beyond
the original ~17-site inventory:

| ID | Surface | file:line | Disposition |
|----|---------|-----------|-------------|
| M1 | `context mission-resolve` flattens the typed error into "check the slug" | `context/mission_resolver.py:164` | **fold → IC-02** (same #15 class) |
| M2 | orchestrator-api flattens `StatusReadPathNotFound`→`MISSION_NOT_FOUND` across 8 endpoints | `orchestrator_api/commands.py:263-266` | **fold → IC-02** |
| M3 | orchestrator seeds `resolve_mid8(…, mission_id=None)`→empty mid8, **suppressing the coord-aware fail-closed guard** (external automation reads stale primary status on a coord topology) | orchestrator-api seam | **fold — read-path SAFETY**; ties to the factory identity boundary (callers must not seed empty identity) |

Robert's `merge.py` `primary_feature_dir_for_mission` routing (#1956/#1972) is on a surface **no IC owns** →
**verify-don't-redo, do not touch merge.py.**

## 7. Decisions of record

- **KEEP-AND-ADOPT** the central API (operator worry retired).
- **IC-01 re-scoped** to establish the single factory + freeze + invariant + write-projection boundary
  contract (read/write-symmetry seam laid now; write adoption deferred).
- **D-1 stays** — DEFER #1716 write-side topology (decision `01KV8Q49WEG9RRKCEZ3XYN5DWP`); it becomes
  Mission B = adoption against the frozen seam.
- **Fold M1/M2/M3** into Mission A.
- **Fragment retirement** limited to `prompt_source` + dead `surface=` read-param.
- **Naming stays in `branch_naming.py`** (factory collaborator, not absorbed — #2012 bounded context).
