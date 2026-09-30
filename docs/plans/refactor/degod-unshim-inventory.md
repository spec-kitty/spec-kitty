---
title: Degod / Unshim — 3-Lens Inventory
description: 'The detailed research catalogs behind the degod/unshim roadmap: the shim/dead-code inventory, the god-object decomposition map, and the #1868 seams-in-name-only catalog.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---
# Degod / Unshim — 3-Lens Inventory (research findings)

> **Historical (3.2.x cycle; status checked 2026-09-30).** Kept as a record. The waves this program tracked have executed: the `specify_cli.next` and `specify_cli.glossary` shims were deleted by #2291 (the 3.3.0 shim removals, closed 2026-07-04 via PR #2328), and the dead-symbol burn-down #2293 closed on 2026-09-25. The 3.3.x milestone was retired on 2026-08-23. The follow-on Mission Clarity Layer (#1746) is now milestoned *CLI 4.x stable*. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../4-0-0-milestone-roadmap.md).

*The detailed catalogs behind [the roadmap](degod-unshim-roadmap.md). Produced 2026-07-01 by a 3-lens research pass (shim/dead-code inventory · god-object decomposition map · #1868 seams-in-name-only) against `upstream/main` @ `b5ff365ce`. This is the durable evidence base; the roadmap is the sequenced plan.*

---

## Lens 1 — Unshim catalog (shims + dead code)

Method: caller-tracing rigor (the #2159/`uv_receipt` lesson — a registered shim is NOT necessarily caller-free). Live caller counts via exact-module `git grep`, excluding docstring/`:func:` refs and dead-importing-dead.

### Removable-now batch (first sweep — zero src callers)
> ✅ **EXECUTED — mission `unshim-wave1-01KWKVHB` (2026-07-03), #2289.** All 8 `category_4` shims below deleted (7 in WP01, `tasks_support` in WP02) with the ~35 test-import re-anchors; `_CATEGORY_4_BACKCOMPAT_SHIMS` + `_baselines.yaml:category_4_backcompat_shims` drained 8→0. Category fully drained.

The 8 `category_4` backcompat re-export shims, ~135 LOC, deletable today (re-point ~15 test imports; drain `_CATEGORY_4_BACKCOMPAT_SHIMS` + `_baselines.yaml:category_4_backcompat_shims` 8→0):

| shim | LOC | canonical home |
|---|---|---|
| ~~`specify_cli.acceptance_matrix`~~ ✅ | 13 | `acceptance.matrix` |
| ~~`specify_cli.core.identity_aliases`~~ ✅ | 5 | `identity.aliases` |
| ~~`specify_cli.doc_generators`~~ ✅ | 11 | `doc_analysis.doc_generators` |
| ~~`specify_cli.doc_state`~~ ✅ | 16 | `doc_analysis.doc_state` |
| ~~`specify_cli.gap_analysis`~~ ✅ | 24 | `doc_analysis.gap_analysis` |
| ~~`specify_cli.state_contract`~~ ✅ | 14 | `state.contract` |
| ~~`specify_cli.tasks_support`~~ ✅ | 30 | `task_utils.support` |
| ~~`specify_cli.workspace_context`~~ ✅ | 22 | `workspace.context` |

→ tracked: **#2289** — ✅ executed by `unshim-wave1-01KWKVHB`.

### Version-gated / blocked batch
| item | LOC | waits on |
|---|---|---|
| `specify_cli.next` (deprecation shim) | 75 | **3.3.0 (#612)** + re-point **3 LIVE callers** (`workflow.py:1518`, `implement.py:1285`, `next_cmd.py:56` via `.runtime_bridge`) + 49 test files → `runtime.next.runtime_bridge`. **#2291** |
| `charter_lint` / `charter_freshness` / `charter_preflight` | 107 | C-008 one-cycle + re-point live CLI callers; **no `__deprecated__` marker → invisible to the shim-registry scanner (governance blind spot)**. **#2290** |
| `specify_cli.glossary` | 55 | 3.3.0 (#613); zero callers. **#2291** |
| category_7 orphans (adjudicated by `unshim-wave1-01KWKVHB`, 2026-07-03, #2292): ~~`task_profile`(155)~~ ✅ deleted, ~~`sync.replay`(357)~~ ✅ deleted, ~~`sync.tracker_client_glue`(285)~~ ✅ deleted, ~~`retrospective.lifecycle`(36)~~ ✅ deleted; `policy.audit`(88) KEEP→adopt-as-follow-up; `auth.transport`(532) DOCUMENTED-DELETE deferred to Robert per ADR 2026-05-18-2 (NOT #614/#391 — that attribution was corrected on the issue) | ~1450 | 4 executed → `_CATEGORY_7` 6→2; the 12 category_b symbol rows for the deleted modules drained. **#2292** |
| `category_b_grandfathered_legacy` dead-symbols | ~~237~~ → 216 entries | Partially drained by `unshim-wave1-01KWKVHB` (#2292): the 12 `sync.replay::*`/`tracker_client_glue::*` rows removed with the module deletions, +1 `frontmatter::update_field` cascade-orphan adopted-as-follow-up. Remaining bulk deferred AFTER #2072 CT1 re-key. **#2293** |
| `category_6` frozen runtime reexports (emitter/lifecycle/models) | — | **NEVER — permanent frozen public surface, not debt** |

### "Looks-dead-but-live" traps found
1. **`specify_cli.next`** — registered for 3.3.0 removal yet has 3 live CLI callers (the `uv_receipt` pattern). Re-point before deleting.
2. **`retrospective.lifecycle`** — 4 grep "callers" import the *sibling* `lifecycle_events`, not `lifecycle`. Substring matching would wrongly mark it live.
3. **`sync.replay`** — lone "caller" is a Sphinx `:func:` docstring ref, not an import.
4. **`auth.transport`** — its 1 caller is `sync.tracker_client_glue`, itself a dead orphan (dead-importing-dead).
5. **`charter_lint`/`charter_freshness`** — real shims with live callers but no `__deprecated__` marker → invisible to registry governance.

> **Wave 1 closeout (`unshim-wave1-01KWKVHB`, 2026-07-03).** Executed #2289 (8 category_4 shims) + #2292 (4 of 6 category_7 orphans deleted; `policy.audit` adopt-as-follow-up; `auth.transport` documented-delete deferred to Robert per ADR 2026-05-18-2). Also folded #2258 (pre-mission governed op: `record_merge`/`finalize_merge` prune, −248 LOC — not catalogued in this Lens-1 table, tracked separately). **New cascade found (falsifies D8's "strands no sibling"):** deleting `task_profile` orphaned `frontmatter::update_field` (its sole src/ caller) — adopted-as-follow-up per C-002. Wave 2 remainder: **#2290** (charter_lint/freshness re-point), **#2291** (`specify_cli.next`/glossary), **#2293** (category_b bulk).

---

## Lens 2 — Degod decomposition map (god-commands)

`#2173` port idiom (`def fn(..., *, port: Proto | None = None)`) is **designed but no port code exists** — Wave 1 co-designs the reference port set. Decomposition begins without #2173 landing (default-param DI is backward-compatible).

extractable-pure% = share of module LOC liftable behind a port. Readiness = extractability × existing-scaffold × low-blast-radius.

| # | module | LOC | fix% | pure% | shared seams held inline | WPs | readiness |
|---|---|---|---|---|---|---|---|
| 1 | **agent/tasks.py** | 3617 | 79% | ~40% | blind `primary_feature_dir`, `resolve_planning_read_dir`, `emit_status_transition`, `safe_commit`, coord R/W authority | 6 | **HIGH** |
| 2 | acceptance/__init__.py | 1721 | **87%** | ~35% | `_planning_read_dir`, `_wp_tasks_read_dir`, `_check_lane_gates` | 4 | HIGH |
| 3 | agent/workflow.py | 2830 | 79% | ~30% | `_commit_via_coordination_transaction`, review-context, bulk-edit-diff | 5–6 | MED-HIGH |
| 4 | implement.py | 1582 | 71% | ~30% | `_resolve_placement_ref`, `_resolve_lanes_dir`, planning-artifact commit (#2164 gate) | 4–5 | MED-HIGH |
| 5 | orchestrator_api/commands.py | 1643 | 83% | ~25% | commit routing, `_execute_lane_merge`, `transition` | 4–5 | MED |
| 6 | mission_type.py | 1500 | ~77% | ~30% | `_resolve_mission_handle`/`_slug`, selector | 4 | MED |
| 7 | sync.py | 3382 | 69% | ~20% | thin over `sync/` pkg; boundary + `--json` render | 5–6 | MED (sync cluster) |
| 8 | sync/emitter.py | 2279 | 67% | ~30% | 40+ `emit_*`, `_route_event`, SaaS payload — **ADAPTER** | 4–5 | MED (sync cluster) |
| 9 | sync/queue.py | 1919 | 70% | ~15% | SQLite persistence — **reference ADAPTER** | 3–4 | MED (sync cluster) |
| 10 | mission_finalize.py | 1712 | — | ~35% | lanes compute, ownership manifest | 2–3 | **LOW-urgency** (already #2056-thin) |
| 11 | migration/mission_state.py | 1889 | — | ~55% | migration-only, frozen | 2–3 | **DEFER** |

**Lineage correction:** `tasks.py` was already seam-extracted once (#2058/#2114); the residual is the **OPEN #2116** body-thinning — our 6-WP plan IS that second pass. Template = the *completed* `agent/mission.py` degod (#2056, 9 WPs, golden-CLI-char-test FIRST).

**Wave 1 (tasks.py) 6-WP:** WP01 golden-char harness (incl. coord exit-0 skip arm) → WP02 **TasksPorts protocol co-design** (5 ports; the load-bearing **CoordRead ≠ CoordWrite two-port split**) → WP03 **status/lane decision core (pure) — highest-value first extraction** (unifies #2116 b+c) → WP04 requirement-mapping core → WP05 executor/flow layer → WP06 renderer seam + shim finalization.

**Wave order after tasks.py:** coord-authority trio (workflow + implement + acceptance — share tasks.py's seams; #2160/#2164 class) → orchestrator_api (the port-consumer shell) → **sync cluster as its own slice — an ADAPTER cluster (CLI-split + adapter-consolidation), NOT pure-core degod**. Defer `mission_finalize`, `mission_type`, `mission_state`.

---

## Lens 3 — #1868 seams "in name only"

A seam in name only is a shim in disguise: a named boundary whose authority isn't bound to a type/owner, so every caller re-implements the rule (the source of split-brain + god-object inline decisions).

| Seam | State | Gates |
|---|---|---|
| **Mission identity** (WS2) | **DONE** (frozen `ResolvedMission`, one read primitive, `MissionSelectorAmbiguous` raised not swallowed) — residue **#2138** | unblocks inline-identity extraction |
| **Guard capability** (WS3) | **DONE** (`evaluate()` sole authority; #2286 bound the merge-bookkeeping commit) — residues: dead `RELEASE_FLOW`; no arch-ban on raw `git commit` outside `commit_helpers` | small unshim tail |
| **CI suite map** (WS5) | **IN-PROGRESS, core OPEN** — `_gate_coverage.py` model + orphan ratchet exist, but **no job selects `-m unit`/`-m contract`** (#2034/#2283) | **META-SEAM — gates whether every other guard runs → Wave 0** |
| **Package layering** (WS1) | IN-PROGRESS — `mission_runtime` unruled (43 lazy `specify_cli` imports + a `CommitTarget` cycle) | blocks the `specify_cli.next` shim deletion |
| **Versioned contracts** (WS6) | IN-PROGRESS — pinning + migration-chain bound; no unifying policy ADR; no `SPEC_KITTY_*` env census | enables retired-env/path deletion |
| **Daemon identity** (WS4) | OPEN — reaper bound (#2261) but reuse/kill identity deferred per C-007 | blocks daemon-lifecycle degod |

**Bind-first: the CI suite map (WS5 / #2034).** The whole epic's mechanism is "the next bypass is a test failure" — which only holds if the test runs in CI. Binding five seams whose guards silently don't run is negative work. Small surface (path-filter half already bound); maximal leverage; fails-closed and retroactively protects the already-bound WS2/WS3.

**Epic relationship:** #1868 (static-seam binding, test-time, AST gates) and #2173 (runtime-port binding, builder/shell, Protocol DI) are **PEERS** under **#1619** (execution-context unification); they share mechanism (#2164 generalizes a #1868 artifact; `ResolvedMission` is what `MissionResolver` resolves). **#1797** (sanitization) is the downstream **delivery** consumer — deletions become test-protected only once #1868/#2173 have bound the seam/port each shim/god-object touched.
