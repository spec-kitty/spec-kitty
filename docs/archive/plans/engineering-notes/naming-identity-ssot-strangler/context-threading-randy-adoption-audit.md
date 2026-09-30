---
title: Randy Reducer — Context-Threading Adoption Audit (the non-adoption split-brain)
description: "Randy Reducer's empirical context-threading adoption audit: measuring the non-adoption split-brain against one specific operator claim."
doc_status: deprecated
updated: '2026-06-16'
---
# Randy Reducer — Context-Threading Adoption Audit (the non-adoption split-brain)

> **Persona:** I am **Randy Reducer**. Semantic compression: fewer lines, same
> behavior, proven. This audit measures one specific operator claim *empirically*:
> the Context value-objects + consolidated read API were built so that
> branch/name/mid8/feature_dir are **computed once and threaded** through call
> chains — not re-derived at every depth. I map, per surface, which consumers
> **THREAD** the context (good) vs **RE-DERIVE** inline (the split-brain), grep-
> backed and quantified. This is the *adoption* companion to
> `randy-reducer-split-brain-map.md` (static) and
> `caacs-randy-forensic-split-brain.md` (temporal).

## Directives / tactics applied (STEP 0 load)

- **`split-brain-authority-detection`** — the scoped fact is **mid8 / branch /
  mission-dir name / feature_dir / status-surface** per mission. The *authority*
  is the Context object + consolidated resolver (the durable record). The
  *uniqueness invariant*: for one mission, the value is **resolved once** and
  every consumer reads that one copy. A **violation** = the same value re-derived
  at a second site/depth (a second "authority" that may diverge). I probe from
  outside (grep) for "two accepted authorities" — i.e. the same value computed
  twice in one chain.
- **`semantic-compression-semantic-consolidation` / `-redundancy-discovery` /
  `-dead-weight-elimination`** + **DIR-024 Locality of Change**, **DIR-001
  Architectural Integrity** — the reduction is "thread the existing result,"
  not "build a new SSOT," IFF the data shows the SSOT already exists and is
  merely *not consumed*.
- **`test-scaffolding-as-design-smell`** — the 12-mock `resolve_lanes_dir` test
  (#1993) and the per-command fallback-ladder duplication are the oracle that a
  threaded seam is missing at the *callsite*, not in the library.

**Posture:** read-only on `research/naming-identity-ssot-strangler` @ 3.2.0. No
commit/branch switch.

---

## 1. The Context / API surface — what each value-object CARRIES

The mission *built* four identity-carrying value objects + three consolidated
resolver entry points. Enumerated with the fields each is designed to let a
consumer **thread instead of re-derive**:

| # | Carrier (file:line) | Kind | CARRIES (the fields meant to be threaded) | Designed-for |
|---|---|---|---|---|
| C1 | `coordination/surface_resolver.py:338` `ResolvedStatusSurface` | frozen dataclass | `surface_path` (canonical `status.events.jsonl`), `primary_anchor` (CWD-invariant primary feature-dir), `.read_dir` (derived parent) | "Carries both halves consumers need so neither re-derives the path (FR-005/#1821)" — *its own docstring* |
| C2 | `workspace/context.py:147` `WorkspaceContext` | dataclass (JSON-persisted) | `mission_slug`, `worktree_path`, `branch_name`, `base_branch`, `base_commit`, `lane_id`, `lane_wp_ids`, `lane_test_env` | runtime workspace identity for a WP — the *persisted* threaded context |
| C3 | `workspace/context.py:207` `ResolvedWorkspace` | frozen dataclass | `mission_slug`, `wp_id`, `worktree_path`, `branch_name`, `lane_id`, `lane_wp_ids`, `execution_mode`, nested `context` | resolved workspace+branch contract for a WP |
| C4 | `coordination/types.py` `GitChangeSet` / `CommitReceipt` | frozen dataclasses | `destination_ref` (short branch), `repo_root`, `worktree_root` | coordination-commit transaction identity |

Consolidated read/identity API (public entry points), each returns/feeds the above:

| API fn (file:line) | Returns | Carries |
|---|---|---|
| `_read_path_resolver.resolve_mission_read_path:226` | `Path` (feature_dir) | the topology-resolved mission dir; mid8 passed *in* |
| `_read_path_resolver.candidate_feature_dir_for_mission:370` | `Path` | "single read primitive" — derives mid8 once from slug, routes through the above |
| `_read_path_resolver.primary_feature_dir_for_mission:397` | `Path` | topology-blind primary anchor |
| `surface_resolver.resolve_status_surface_with_anchor:433` | **`ResolvedStatusSurface`** | surface_path **+** primary_anchor (one pass, FR-036) |
| `surface_resolver.resolve_status_surface:418` | `Path` | thin wrapper that **discards** the anchor |
| `lanes/branch_naming.mid8 / resolve_mid8 / mission_dir_name / worktree_path` | `str` / `Path` | the name-grammar seam (the compose SSOT) |

**Observation that frames the whole audit:** the richest carrier (C1
`ResolvedStatusSurface`) has a thin sibling `resolve_status_surface()` that
returns *just the path and throws the anchor away*. The mission shipped the
threading object **and** the value-discarding wrapper side-by-side. That wrapper
is the principal non-adoption enabler.

---

## 2. Threaded vs re-derived — the adoption map (quantified per surface)

### 2.1 `ResolvedStatusSurface` (C1) — **near-zero adoption of the carried field**

The object was built to carry `primary_anchor` so callers don't re-derive it.
Empirically:

- **`primary_anchor` is consumed at exactly ONE site:**
  `coordination/status_transition.py:232` (`return resolved.primary_anchor`).
- **`resolve_status_surface_with_anchor` callers that DISCARD the anchor:**
  `implement.py:1018` (`.read_dir` only). Plus `agent/status.py` builds its own
  `ms.read_dir` extraction (5 sites at :164/:222/:297/:346/:514/:632), never the
  anchor.
- **`resolve_status_surface()` (anchor-discarding wrapper) callers — 9 sites:**
  `status/aggregate.py:332`, `retrospective/gate.py:206`, `retrospect.py:108`,
  `agent_retrospect.py:221`, `merge.py:360/529/2404`, plus the implement path.
  Every one of these takes *only* `surface_path`, then **separately** re-derives
  a feature_dir via a *different* resolver to get the read dir / anchor.
- **The object is NEVER passed as a parameter.** Grep for `: ResolvedStatusSurface`
  / `surface=resolve...` across non-test src returns **zero** consumer signatures
  — every occurrence is the class def or a constructor inside `surface_resolver.py`
  itself. It is constructed and immediately decomposed at the callsite.

**Verdict C1: ~1 threaded / ~14 re-derived (≈7% threaded).** The single most
deliberately-built threading object in the mission is the *least adopted*.

### 2.2 `feature_dir` resolution — the headline surface

Counting callsites that **re-resolve** topology from `(repo_root, mission_slug)`
vs functions that **accept a resolved `feature_dir`** as a parameter:

- **Threaded (accept `feature_dir: Path` as a parameter): 180 function sites.**
- **Re-derived (internally call a topology resolver
  `candidate_/resolve_feature_dir_/resolve_status_surface/resolve_mission_read_path/primary_feature_dir`):
  99 callsites across 51 distinct consumer files.**

So the **leaf** layer largely threads (180 functions accept the dir), but the
**entry/orchestration** layer re-derives 99 times. The 99 re-derivations cluster
on the high-traffic commands (matching the CaaCS deg-0.75 coupling):

```
 9 cli/commands/agent/workflow.py
 7 cli/commands/implement.py
 6 workspace/context.py
 5 cli/commands/merge.py
 5 acceptance/__init__.py
 4 cli/commands/next_cmd.py
 3 …  (status_transition, agent/tasks, agent/mission, doctrine_synthesizer,
       retrospective/lifecycle_events, lanes/recovery, tasks_cli)
```

**Top-5 re-derivers = exactly the CaaCS top-5 bug∩churn hotspots** (`workflow`,
`implement`, `merge`, `mission`, plus `acceptance`). The re-derivation map and
the defect map are the same map.

### 2.3 `WorkspaceContext` (C2/C3) — partial; entry re-resolves, leaf threads

- **Threaded (functions accept `: WorkspaceContext`): 2** signatures.
- **Re-derived entry (callers re-enter via `find_context_for_wp` /
  `resolve_workspace_for_wp` / `build_feature_context_index`): 17** callsites.

The persisted context object is read back from disk per-need rather than
resolved once and threaded — and `workspace/context.py` *itself* re-resolves
`feature_dir` 6× internally (`resolve_feature_dir_for_slug` at :470/:666/:714/
:752/:790/:853), so even the context-owner module re-derives the dir it could
have carried on the object.

### 2.4 mid8 / branch / worktree-path compose — the mechanical riders

- **Bare `mission_id[:8]` (re-derive instead of `mid8()`/`resolve_mid8()`): ~10
  non-seam sites** (`status/aggregate.py:250`, `implement.py:386`,
  `agent/workflow.py:292`, `agent/mission.py:772`, `git/sparse_checkout.py:286`,
  `mission_type.py:643`, `context/mission_resolver.py:163`,
  `doctrine_synthesizer/apply.py:745/831`, `dashboard/scanner.py:438`). Already
  fully mapped as surface 2c. These are *plateaued* (CaaCS §4).
- **Inline `kitty/mission-…` branch f-strings: only 2 live** (`lanes/recovery.py:135`
  glob pattern, `core/vcs/detection.py:161`) — the rest are docstrings/comments.
  The branch-compose split-brain is *already mostly strangled*.
- **Inline `.worktrees/` join outside the seam:** the migrations (`upgrade/…`,
  ~14) legitimately walk the literal dir; the live-code offenders are
  `manifest.py:254`, `core/worktree.py:370` (allow-listed), `mission_type.py`,
  `agent/workflow.py:2135`, `agent/mission.py:2410`, `sparse_checkout.py:370`,
  `lanes/lifecycle_sync.py:135`.

---

## 3. The method-chain re-derivation smell — the operator's exact concern

This is where "compute once, thread through" *fails by construction*. Two
canonical chains:

### 3.1 `implement()` — FOUR resolvers, THREE feature_dir variants, one mission

`cli/commands/implement.py:957–1018` derives the same logical "where does this
mission live" answer **three times** into three variables, each via a different
resolver, never threading the first result:

```
957  feature_dir         = resolve_feature_dir_for_mission(repo_root, slug)   # resolver #1
959  feature_dir         = candidate_feature_dir_for_mission(repo_root, slug)  # resolver #2 (fallback)
974  _lanes_feature_dir  = feature_dir                                         # snapshot before re-anchor
980  primary_candidate   = primary_feature_dir_for_mission(repo_root, slug)    # resolver #3 (re-anchor)
1018 _status_feature_dir = resolve_status_surface_with_anchor(repo_root, slug).read_dir  # resolver #4 — AND discards .primary_anchor
1130 require_lanes_json(_lanes_feature_dir)   # the snapshot finally consumed
```

Resolver #4 *returns a `ResolvedStatusSurface` carrying `primary_anchor`* — which
is **exactly** the value `feature_dir`/`primary_candidate` (#3) just computed by
hand — and `implement()` **throws it away** (`.read_dir` only). The object
designed to end this duplication is invoked and discarded in the same function
that duplicates it. This is the textbook split-brain red flag: two accepted
authorities for one scoped fact, in one call chain, that can diverge in the
planning→implement window (the exact #1991/#1718 class).

`implement()` is **CC 57 / F-rank** (CaaCS §5) — the complexity *is* this
re-derivation ladder.

### 3.2 `agent/workflow.py` — a re-resolution helper called 3× (worst chain)

`_canonical_status_feature_dir(main_repo_root, mission_slug)` (:312) is itself a
**3-resolver chain**:

```
314  primary_feature_dir = candidate_feature_dir_for_mission(main_repo_root, slug)  # resolver #1
315  mid8                = _mid8_for_mission_read_path(primary_feature_dir, slug)   # re-derives mid8
319  return resolve_mission_read_path(main_repo_root, slug, mid8)                   # resolver #2
```

…and it is **called three separate times** in the same module
(:1283 `_dependency_feature_dir`, :1387 `_wf_feature_dir`, :2240 `feature_dir`)
plus 5 more bare `candidate_feature_dir_for_mission` calls (:1011/:1878/:2042/
:2043/:2048/:2049). **One mission, one workflow command, ~8 independent
re-resolutions of the same topology** — none threaded. This is the single worst
method-chain re-derivation in the repo: a helper that re-derives 3× internally,
invoked 3× externally = up to 9 redundant topology resolutions per workflow run.

---

## 4. Adoption verdict + reduction delta

### Is the failure non-adoption (B) or missing-SSOT?

**Non-adoption, decisively.** The SSOT exists and is *correct*:

- `ResolvedStatusSurface` already carries `surface_path + primary_anchor` in one
  pass (FR-036) — the threading object is **built**.
- `candidate_feature_dir_for_mission` is already "the single read primitive."
- `branch_naming.*` is already the compose SSOT (mid8 class *plateaued* post-#2001).

What is missing is **consumption**: 99 re-resolution callsites where the resolved
context should be *threaded as a parameter*, and the value-discarding
`resolve_status_surface()` wrapper + the `_canonical_status_feature_dir` re-call
pattern that *enable* re-derivation. The resolver files are individually simple
(CaaCS: A-rank, CC ≤14); the CC-57 complexity lives entirely in the consumers
that re-derive. **Missing-SSOT is falsified; the disease is non-adoption (B) of
an existing SSOT.**

### LOC / site delta to flip (B) → threaded

| Flip target | (B) sites | Delta to thread | Highest-value? |
|---|---|---|---|
| `implement()` 3-variant ladder → consume one `ResolvedStatusSurface` (use its `primary_anchor`, derive `_lanes_feature_dir`/`_status_feature_dir` from it) | 4 resolvers → 1 | −~25 LOC of ladder; pulls `implement()` off CC-57 | **YES — #1** |
| `agent/workflow.py` `_canonical_status_feature_dir` 3-call → resolve once at command entry, thread the dir | 8 re-resolutions → 1 | −helper internal re-derivation; thread a single dir param to :1283/:1387/:2240 | **YES — #2** |
| Promote `ResolvedStatusSurface` (or a `MissionSurfaces` superset carrying feature_dir·lanes_dir·status read_dir) to a **threaded parameter** the commands accept | 14 discard-sites | the projection the static map's surface-4 already proposes | **YES — #3 (the cure)** |
| Retire/deprecate `resolve_status_surface()` thin wrapper; make `_with_anchor` the only entry | 9 wrapper callers | forces anchor-awareness; small per-site | medium |
| mid8 `[:8]` → `mid8()` (2c) | ~10 | 1 line each | low (plateaued) |

**Highest-value flips:** the two method chains in §3 (`implement()` and
`_canonical_status_feature_dir`) — they are the CC-57/F-rank consumers, the
deg-0.75 coupled hotspots, and the *accelerating* defect class. Flipping them to
thread one resolved object deletes the duplicated fallback ladder (~30 LOC ×
top-4 consumers ≈ 120 LOC, CaaCS §5) **and** removes the divergence window.

---

## 5. Reconciliation with my CaaCS finding — is "thread the context" the precise reduction?

**Yes, and this audit sharpens it.** My CaaCS forensic found "the crime scene is
the callsite, not the library" and that `_read_path_resolver ↔ surface_resolver`
co-change (the two resolvers encode the same rule twice). This adoption audit
supplies the *mechanism*: the callsites re-derive because **the threading object
is built but discarded** — `ResolvedStatusSurface.primary_anchor` is consumed
once, the object is never passed as a parameter, and `resolve_status_surface()`
hands back a bare path that *forces* every consumer to re-derive the dir.

The CaaCS deg-0.67 `accept↔implement` and deg-0.75 `surface_resolver↔command`
couplings are precisely the signature of **a sealed authority that callers
refuse to consume**: a resolver that high-couples to its callers has not
encapsulated the decision; the callers re-make it. The reduction is therefore
**not** "build a new SSOT" — it is **"thread the SSOT that exists"**:

1. Make `ResolvedStatusSurface` (or a `MissionSurfaces` superset) the value the
   command resolves **once at entry** and threads as a parameter.
2. Delete the anchor-discarding `resolve_status_surface()` wrapper and the
   `_canonical_status_feature_dir` re-call pattern.
3. The two resolver modules then collapse to one (the CaaCS smoking-gun
   co-change), because there is one threaded result instead of two re-derivers.

**Red flag (split-brain tactic, step 7):** two accepted authorities for "where
this mission lives" in one `implement()` chain (the hand-derived `primary_candidate`
vs the discarded `ResolvedStatusSurface.primary_anchor`). **Fence:** resolve the
context **once at command entry**, thread the object, and make re-derivation
impossible by removing the value-discarding wrapper. "Thread the context" is the
precise, evidence-backed reduction — the data shows the SSOT is built and unused,
not missing.
