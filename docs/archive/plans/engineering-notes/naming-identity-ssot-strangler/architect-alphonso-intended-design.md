---
title: Naming / Identity SSOT Strangler — Intended (Target) Architecture
description: "Architect Alphonso's intended (target) architecture for the naming/identity SSOT strangler: the design the strangler converges toward, read-only at 3.2.0."
doc_status: deprecated
updated: '2026-06-26'
---
# Naming / Identity SSOT Strangler — Intended (Target) Architecture

**Author:** Architect Alphonso (design-lens investigation, research squad)
**Branch:** `research/naming-identity-ssot-strangler` @ 3.2.0 (read-only; no commit/switch)
**Date:** 2026-06-16
**Scope:** the 3.2.1 slice of epic **#1868** (canonical seams: bind authority to type/owner)
advancing **#1619** (runtime/state SSOT). Surface issues: #1878, #1888, #1899, #1915, #1971, #1993, #2000.
**Aggregation note:** this is the design-lens artifact only. A later architect-alphonso op
aggregates the whole squad; this document supplies the north star, not the mission spec.

---

## 0. Directives applied (architect-alphonso governance)

- **DIR-001 Architectural Integrity** — every concern on this surface gets ONE owning module
  with a clear boundary; duplicates are seams to strangle, not features to preserve.
- **DIR-003 Decision Documentation** — each SSOT below carries (authority | contract | bounded
  context | intended-vs-current gap | epic linkage); decisions are traceable.
- **DIR-031 Context-Aware Design** — bounded contexts must NOT be collapsed; cross-context
  interaction goes through an *explicit translation layer*, never a leaky duplicate. The
  coord/primary split is the marquee translation seam — it must stay a translation, not a fork.
- **DIR-032 Conceptual Alignment** — terminology confirmed against CLAUDE.md canon
  (Mission Identity Model, Status Model, Execution Workspace Strategy, Shared Package Boundary)
  and the #1619 consolidated domain model (`docs/archive/plans/engineering-notes/runtime_and_state_overhaul/17-consolidated-domain-model.md`).

The branch_naming seam (3.2.0, PR #2001) is the **template shape** every other concern must
generalize to:

> **compose+parse SSOT · emit-don't-guess · canonical-first / legacy-failover-warned ·
> declared-identity-keyed · fail-closed on ambiguity · ratchet-enforced (AST literal-ban).**

Evidence: `src/specify_cli/lanes/branch_naming.py` — `mission_branch_name_required` (fail-closed,
`branch_naming.py:301`), `resolve_mid8` ("name proposes, authority disposes", `:169`),
`resolve_branch_name` (canonical-first + one-shot legacy warning, `:675`),
`worktree_dir_name`/`worktree_path` (emit-don't-guess, `:484`/`:516`),
`parse_mission_slug_from_branch` (dual-era parser, `:771`). Enforced by
`tests/architectural/test_no_worktree_name_guess.py` (the literal-ban ratchet with an
allow-list as a *completeness oracle*).

---

## 1. The five concerns, mapped to SSOTs (target architecture)

Each concern below is one bounded sub-context of the **Shared Kernel** (`#1619` model §2:
"path · identity · status resolvers"). The Shared Kernel is a *code module that builds Contexts*,
not itself a Context — so these resolvers are OHS (Open-Host-Service) facades, not domain logic.

### Concern A — Mission identity / naming  *(ESTABLISHED — the template)*

| Aspect | Target |
|--------|--------|
| **SSOT** | `lanes/branch_naming.py` — the ONE grammar for branch / worktree-dir / coord names + mid8 resolution. |
| **Public contract** | `mission_branch_name_required`, `resolve_branch_name`, `worktree_dir_name`, `worktree_path`, `mission_dir_name`, `coord_*`, `resolve_mid8`, `resolve_transaction_mid8`, `parse_mission_slug_from_branch`. Compose AND parse live together. |
| **Bounded context** | *Identity* (who is this mission?) — distinct from *Path* (where does it live?). Names propose; declared `mission_id` from `meta.json` disposes. |
| **Intended-vs-current gap** | Three pre-#2001 inline composes remain (`core/mission_creation.py:321`, `core/worktree.py:367`, `:370`) — allow-listed in the ratchet, NOT yet routed. This is **#2000** (mechanical, byte-identical via golden table) + **#1899** (worktree DIR-name grammar + a 4th ratchet assertion for `.worktrees/`-shape composes). |
| **Epic** | **#1868** directly (the seam itself). Generalizing its shape to B–E is the 3.2.1 thesis. |

### Concern B — Project-root resolution  *(LANDED — residual wrapper retirement)*

| Aspect | Target |
|--------|--------|
| **SSOT** | `core/paths.py::locate_project_root` — the ONLY authority: honors `SPECIFY_REPO_ROOT` (Tier 1, authoritative even without `.kittify`, #1965), worktree `.git`-pointer following (Tier 2), `.kittify` walk (Tier 3). |
| **Public contract** | `locate_project_root(start=None) -> Path | None`; deterministic 3-tier order; env-var override is fail-into-walk on a non-dir value. |
| **Bounded context** | *Infra/path* — "where is the project root?" Must be answered once, identically, from anywhere (worktree or primary). |
| **Intended-vs-current gap** | **Already consolidated** (#1971 landed: `1a21d6157`). `core/project_resolver.py:8` now *delegates* to the authoritative impl (deferred import, cycle-safe). **Residual:** `core/__init__` re-export + `specify_cli/__init__.py:52` wrapper still exist as a second name for the same authority — a *naming* duplicate (two import paths, one behavior). Target: collapse to a single canonical import (`from specify_cli.core.paths import locate_project_root`) and retire the wrappers, OR keep `project_resolver` purely as a re-export with a ratchet asserting it never re-acquires a walk. The behavior split-brain is closed; the *surface* split-brain (two import sites) is the residual. |
| **Epic** | **#1868** (one authority per concern) — verification + ratchet, not re-implementation. |

### Concern C — Lanes-dir / workspace resolution  *(GAP — extract pure seam)*

| Aspect | Target |
|--------|--------|
| **SSOT** | A pure, topology-aware `_resolve_lanes_dir(repo_root, mission_slug) -> Path` (the **#1993** ask), modeled on the existing `resolve_status_surface_with_anchor`. Prefers the coord worktree (where `finalize-tasks` writes `lanes.json`), falls back to primary on flat/legacy topology. |
| **Public contract** | One function, `tmp_path`-testable with **zero mocks** (vs the 12 mock patches the inline fix needed — `TestImplementCoordTopologyLanesJson`, the test-scaffolding-as-design-smell signal). |
| **Bounded context** | *Path/topology*, lanes family — the THIRD artifact surface. CLAUDE C-LANES-1: `lanes.json` (coord), `meta.json` (primary-anchored), status (status-emitter surface) are **three artifact families → three surfaces**, and the resolver must NOT conflate them. |
| **Intended-vs-current gap** | Today `_lanes_feature_dir` is an inline assignment inside the ~200-line `implement()` orchestration (`cli/commands/implement.py:974`), reaching infrastructure with no pure seam. Blast radius: every caller that needs lanes.json re-derives topology ad-hoc → drift risk (#1991 was exactly this). |
| **Epic** | **#1619** (runtime/state SSOT: the ExecutionContext that owns "where do I read lanes.json?") + **#1868** shape. |

### Concern D — Coordination-vs-primary feature_dir  *(THE MARQUEE SPLIT-BRAIN)*

| Aspect | Target |
|--------|--------|
| **SSOT** | `missions/_read_path_resolver.py::_resolve_mission_read_path` — the internal read primitive (C-005). Public callers cross the boundary through `resolve_handle_to_read_path` / `resolve_feature_dir_for_mission`; all topology priority (coord worktree → primary checkout, fail-closed on stale-primary) lives in that resolver family. `feature_dir_resolver.py` is now a thin re-export shim (C-004 strangler). |
| **Public contract** | `resolve_handle_to_read_path(repo_root, handle, *, require_exists)`; `candidate_feature_dir_for_mission` / `resolve_feature_dir_for_mission` (candidate and existence-gated public helpers); `primary_feature_dir_for_mission` (deliberately topology-BLIND, for meta.json reads); `resolve_status_surface_with_anchor` (status-emitter surface, anchored on meta-derived mid8). Ambiguous handle → `MissionSelectorAmbiguous` (no silent fallback, C-CTX-4/C-009). Stale-primary-under-coord → `StatusReadPathNotFound` (#1718). |
| **Bounded context** | *Coordination topology* — the explicit **translation layer** (DIR-031) between "the operator's CWD / a slug" and "the authoritative on-disk surface for THIS artifact family." This is precisely where a leaky duplicate is catastrophic (the #1784/#1589 split-brain family: primary checkout treated as authority while artifacts live on the coord branch). |
| **Intended-vs-current gap** | The read SSOT is **largely consolidated** (C-004/C-005 strangler done for reads). BUT the *write/entry* side is still scattered — #1878's umbrella enumerates the residual: `is_committed` checks only primary HEAD (`missions/_substantive.py`), setup-plan auto-commit fallback diverges, lifecycle event emission targets protected main, `implement.py` C-004 fallback, single ref-advance helper not rolled out, `_ensure_branch_checked_out` shim not retired. **Four surfaces now answer "where is the mission dir?"** (`_read_path_resolver`, `feature_dir_resolver` shim, `surface_resolver`, `dashboard/scanner`) — convergent but not yet single-authority on the write path. |
| **Epic** | **#1619** (the ExecutionContext / topology resolver is the heart of the runtime/state overhaul) + **#1868** (bind the surface authority to artifact-family OWNER). |

### Concern E — Ownership / path validation  *(LANDED — verify + ratchet)*

| Aspect | Target |
|--------|--------|
| **SSOT** | `ownership/validation.py` — `validate_no_overlap` + `validate_glob_matches` (literal-path zero-match → hard error with nearest-match suggestion; glob zero-match → soft warning; `create_intent` suppresses planned-new-file). |
| **Public contract** | `validate_ownership`, `validate_glob_matches`, `build_wp_manifests` (pure frontmatter→manifest seam, filesystem-free). |
| **Bounded context** | *Mission-management planning* (WP ownership invariants), not path resolution — but it *consumes* `repo_root`, so it sits adjacent to the Shared Kernel. |
| **Intended-vs-current gap** | **Already wired** (`cli/commands/agent/mission.py:3348`, lane-mode at `:3570`) on the SAME `wp_manifests` that feed no-overlap — closing the #1888 hole (phantom `owned_files` path silently validating against a non-existent file, weakening the overlap guard). The literal-existence check landed via #1886. **Residual:** confirm #1888 is a *duplicate* of the shipped #1886 fix, or scope only the missing piece (e.g. a regression test asserting overlap-detection sees the corrected path, and that `--validate-only` exercises the same guard). |
| **Epic** | **#1868** (validation authority bound to the ownership owner) — verification, not re-build. |

---

## 2. Coordination-resolution model — deep dive (DIR-031 translation layer)

The coord/primary split is **not a bug to delete; it is a genuine bounded-context boundary**
that must be preserved as an *explicit translation layer*. Two distinct truths coexist by design:

- **Identity & metadata** live on the **primary checkout** (`meta.json` is never on the coord
  worktree — `_read_path_resolver` docstrings, implement.py:960 comment). `primary_feature_dir_for_mission`
  is *deliberately topology-blind* for exactly this reason.
- **Status / lanes / decisions** live on the **coordination worktree** (sparse-checkout policy
  excludes them from lanes; `BookkeepingTransaction` commits there).

**Intended model — ONE topology-aware resolver family, keyed by artifact-family, not by call site:**

```
                       ┌─────────────────────────────────────────┐
  operator CWD / slug ─► resolve_mission_read_path  (the C-005 primitive)
                       │   priority: coord-worktree → primary      │
                       │   fail-closed: stale-primary-under-coord  │
                       └───────────────┬──────────────────────────┘
            ┌──────────────────────────┼───────────────────────────────┐
            ▼                          ▼                               ▼
   primary_feature_dir_*        resolve_status_surface_*        _resolve_lanes_dir   (#1993)
   (meta.json, topology-BLIND)  (status events, meta-mid8        (lanes.json,
                                 anchored)                         coord-preferred)
```

**The boundary that must NOT be collapsed:** these three are NOT one path. C-LANES-1 is explicit —
*three artifact families, three surfaces*. The failure mode of collapsing them is the planning→implement
window bug (implement.py:1009-1018): a slug-derived empty mid8 read landed on a different surface than
the meta-anchored write and saw genesis ("WP not finalized"). The fix was to route the read through the
SAME anchor authority the write uses — **emit-don't-guess applied to topology**: derive mid8 from
declared identity (`meta`), never from a slug heuristic, on any correctness path.

**The intended end-state for #1878:** every *write/entry* gate (`is_committed`, setup-plan auto-commit,
lifecycle emission, the implement C-004 fallback) routes its "which surface?" question through the
SAME resolver family — replacing the scattered "check primary HEAD" predicates with one topology-aware
authority. The single ref-advance helper + the worktree-naming allocator unification (#1878 items 2-3)
are the write-side analog of the branch_naming compose SSOT: *one allocator, no parallel naming logic*.

**Non-goal (preserve the boundary):** #1878 explicitly forbids a *topology redesign* and a *safe-commit
semantics change*. The strangler completes WITHIN the coord-branch/worktree topology. This is correct
architecture: we are converging duplicate readers/writers onto the existing translation layer, not
re-drawing the bounded contexts.

**Atomicity rider (#1915):** `_merge_dependency_lane_tips` is non-atomic across ≥2 deps — an earlier
clean dep-merge commit survives a later dep's conflict despite a contract promising "never left
half-merged." This is a *ref-advance correctness* defect adjacent to #1878 item 2 (single ref-advance
helper). Target: snapshot HEAD before the loop, `git reset --hard <snapshot>` on any conflict (true
atomic rollback) — the ref-advance helper should own this invariant, not each call site. Belongs in
the write-side seam family, with a ≥2-dependency conflict regression test.

---

## 3. Epic linkage — why this is one coherent step, not a detour

| Issue | SSOT concern | #1868 (canonical seams) | #1619 (runtime/state SSOT) | Status |
|-------|-------------|-------------------------|----------------------------|--------|
| #2000 | A identity | route last 3 composes through seam; tighten ratchet | — | mechanical residual |
| #1899 | A identity | worktree DIR-name grammar + 4th ratchet assertion | — | the filesystem twin of branch seam |
| #1971 | B project-root | one authority; retire wrapper surface + ratchet | InfraContext input | behavior landed; surface residual |
| #1993 | C lanes-dir | pure topology-aware seam (branch_naming shape) | **ExecutionContext owns lanes read** | gap — extract |
| #1878 | D coord/primary | bind surface authority to artifact OWNER | **the ExecutionContext / topology resolver core** | write-side strangler residual |
| #1915 | D ref-advance | one ref-advance helper owns atomicity | ExecutionContext mutation | bug — atomic rollback |
| #1888 | E ownership | validation authority bound to owner | — | landed via #1886; verify/dup |

**Coherence thesis:** #1868 says "bind authority to type/owner for canonical seams"; #1619 says
"the Shared Kernel resolvers (path · identity · status) build the per-domain Contexts." The 3.2.1
slice **generalizes the proven branch_naming seam shape** (compose+parse SSOT, emit-don't-guess,
ratchet-enforced) from *identity-naming* (done) to the other four Shared-Kernel concerns
(project-root, lanes-dir, coord/primary, ownership). Each becomes a single OHS facade with a literal-ban
or behavior ratchet. That is the *runtime/state SSOT* (#1619) being assembled one resolver at a time,
exactly the sequencing the consolidated domain model prescribes (`17-…md` §6: "harden ExecutionContext +
enforce the Status boundary first, Strangler"). **No new shadow paths** — every change either routes a
duplicate onto an existing authority or extracts a pure seam from an inline blob.

---

## 4. Architecturally-correct sequencing (foundation → routing → enforcement)

The ordering principle: **foundation seams before routing before enforcement**, and never widen a
divergence without a ratchet that shrinks the allow-list.

1. **Foundation — finish the identity seam (#2000, #1899).** Lowest risk, byte-identical, mechanical.
   Routing the 3 allow-listed composes + adding the worktree-DIR-name grammar + the 4th ratchet
   assertion *completes the template* the other concerns generalize from. Do this first so the seam
   shape is unambiguous. (Pair with the #1899 surface_resolver R2 dedupe nit — call the classifier,
   don't hand-roll the `.worktrees`-segment test.)

2. **Foundation — verify + ratchet the landed concerns (#1971 surface, #1888 dup-check).** These are
   already behavior-correct; the work is *closing the surface split-brain* (retire the project_resolver/
   `__init__` wrapper duplication, add a ratchet that `project_resolver` never re-acquires a walk) and
   *confirming #1888 is a duplicate of #1886* (or scoping only the missing regression test). Cheap,
   de-risks the mission's claim count.

3. **Routing — extract the lanes-dir seam (#1993).** Pure refactor, zero behavior change, modeled on
   `resolve_status_surface_with_anchor`. Turns a 12-mock test into a zero-mock one. This is the
   *third surface* of the C-LANES-1 triad made explicit — a clean, bounded extraction.

4. **Routing — the coord/primary write-side strangler (#1878).** The deepest and highest-risk work:
   route `is_committed`, setup-plan auto-commit, lifecycle emission, and the implement C-004 fallback
   through the topology-aware resolver family; roll out the single ref-advance helper; unify the
   worktree-naming allocator; retire `_ensure_branch_checked_out`. **Sequence the ref-advance atomicity
   fix (#1915) as the first sub-step** — it hardens the helper that the rest of #1878 item 2 depends on.

5. **Enforcement — widen the ratchet (AC10 / #1878 item 5).** Once the seams exist, expand the
   architectural lint to cover the new placement/identity write-side surfaces. Enforcement comes LAST
   so the allow-list shrinks (completeness oracle) rather than ossifying around un-routed call sites.

**Bounded-context boundaries that must NOT be collapsed during this sequence:**
- *Identity* (branch_naming) ≠ *Path* (read_path_resolver) — names propose, declared identity disposes.
- *meta.json/primary* ≠ *status/coord* ≠ *lanes/coord* — three artifact families, three surfaces (C-LANES-1).
- *Ownership validation* (mission-management planning invariant) ≠ *path resolution* (Shared Kernel).
- *Coord/primary topology* stays a **translation layer**, never a fork (#1878 non-goal: no topology redesign).

---

## 5. Risk register

| Risk | Mitigation |
|------|-----------|
| #1878 write-side strangler touches commit/protected-branch gates → regression in the #1784 catch-22 family | Route through the SAME resolver the reads use; keep safe-commit semantics frozen (#1878 non-goal); regression-test each gate against a coord-topology mission. |
| Collapsing the 3-surface triad (meta/status/lanes) into one resolver "for simplicity" | DIR-031: preserve the boundary. The triad is intentional (C-LANES-1); a single surface reintroduces the planning→implement genesis bug. |
| #1971 wrapper retirement triggers an import cycle | The deferred-import pattern is load-bearing (`project_resolver.py:23` rationale); keep it; ratchet the no-walk invariant rather than inlining. |
| #2000/#1899 composes drift from byte-identical | Shared golden-value table + the literal-ban ratchet as completeness oracle; assert byte-identity in tests. |
| #1888 re-implements a shipped fix (#1886) | Verify first; scope only the residual (regression test / `--validate-only` parity), or close as duplicate. |
