---
title: 'ADR: Terminal-Artifact Durable Home + Topology-Aware Teardown Contract'
description: 'Terminal artifacts such as `retrospective.yaml` become PRIMARY-partition kinds with a tracked durable home, and worktree teardown is ordered after they persist.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-06-25'
---

`src/specify_cli/retrospective/*`, `src/specify_cli/cli/commands/{merge,mission_type}.py`
**Tracker**: [#2119](https://github.com/Priivacy-ai/spec-kitty/issues/2119) · **[#2136](https://github.com/Priivacy-ai/spec-kitty/issues/2136)** (handle-canonicalization, folded as FR-011) · parent [#1878](https://github.com/Priivacy-ai/spec-kitty/issues/1878)
**Precedents**: [kind-and-topology-aware artifact placement](2026-06-24-1-kind-and-topology-aware-artifact-placement.md) (#2101/#2090);
[coord-empty surface fallback](2026-06-19-1-coord-empty-surface-fallback.md) (#1716, the read twin)

---

## Context

A coordination-topology mission writes its **terminal artifact** — `retrospective.yaml` — into the
ephemeral coordination worktree, resolved through a coordination-topology-aware resolver
(`resolve_feature_dir_for_slug` / `resolve_feature_dir_for_mission`). On close or merge, that worktree is
torn down and the retrospective is **silently lost**. The CLOSED #1771 moved the home to
`kitty-specs/<slug>/` but kept the coord-aware resolver, so the divergence survived — #2119 is its residual.

This is the **write-surface twin** of a problem the read side already solved: planning-artifact *reads* were
re-pointed to the primary surface via the kind-aware `MissionArtifactKind` partition (#2106/#2101), and the
coord-empty read fallback was made loud (the read-twin ADR above). The terminal-artifact *write* home had no
equivalent authority, and teardown had no ordering guarantee with respect to artifact persistence.

Three structural faults compound it:
0. **Handle-blind PRIMARY entry points (#2136).** `primary_feature_dir_for_mission` (`:1212`) is a
   topology-blind primitive (handle-blind by contract — docstring `:1213`): it does a raw literal compose
   (`:1240`). Its callers on the PRIMARY path — the kind-aware read seam `resolve_planning_read_dir`'s PRIMARY
   leg (`:1306`) and the retrospective write — pass it a *raw* handle, so a bare `mid8`/`slug` handle resolves
   to a *different* dir than the canonical `<slug>-<mid8>`. #2136 names this "the same root behind #2119":
   placement is only as correct as the handle is canonical, and today these entry points do not canonicalize
   before composing. (The primitive cannot self-canonicalize: `_canonicalize_bare_modern_handle:418` calls it
   at `:454` → recursion. The cure is caller-side, mirroring the live exemplars `:1204`/`:1208`/`:820`.)
1. **Six divergent home-resolution sites** (5 coord-aware resolvers + 1 event-payload path string that
   hardcodes `.kittify/missions/<id>/`) — no single authority.
2. **Three duplicated coordination-teardown blocks**, one of which (merge) destroys the worktree *before* the
   retrospective postcondition runs; `close --discard` has no persist step at all.

**Landed-base note (2026-06-25).** PR **#2121 (#2120)** landed the close-path teardown helper
`mission_type.py:_teardown_coordination_worktree` (`:904`, the canonical seam-anchor — a destruction-completeness
verifier `_verify_discard_complete` + a `_flatten_discarded_mission` step, but **NO persistence ordering**), and
PR **#2129 (#2127)** landed the lane exact-set (`_remove_lane_worktrees` exact-name +
`_verify_discard_complete` sibling-safe). The persist-before-destroy gap (binding B) is precisely what #2121
left un-addressed — #2121/#2129 *reinforced* the destruction completeness without adding persistence ordering.
**PR #2133 (#2057) has now MERGED** (along with #2114/#2134/#2135) — its `cli/commands/merge.py` god-module
decomposition RELOCATED the merge-path teardown anchor into **`merge/executor.py:795`**
(`_phase_cleanup_worktrees_and_branches` cleanup phase) but **left the `--abort` teardown in
`cli/commands/merge.py:270`** (it did NOT migrate into `merge/`), and it shipped
`test_phase_cleanup_coord_teardown_failure_is_non_fatal` (`tests/merge/test_executor_coverage.py:616`). With no
open-PR gate remaining, this decision is delivered as **one slice** of one mission — both bindings plan against
the settled base (`upstream/main e36547461`).

## Decision

Adopt a **Terminal-Artifact Durable Home + Topology-Aware Teardown Contract** with two bindings:

### Binding A — Terminal artifacts resolve to a durable, HANDLE-SAFE PRIMARY home via the kind partition

Terminal artifacts (today: `retrospective.yaml`) are PRIMARY-partition artifacts. A `RETROSPECTIVE` member is
added to `_PRIMARY_ARTIFACT_KINDS`, and **all** home-resolution sites route through the single primary-anchored
placement authority — modeled on the **topology-blind `primary_feature_dir_for_mission`**
(`src/specify_cli/missions/_read_path_resolver.py:1212`) gated by **`is_primary_artifact_kind`**
(`src/mission_runtime/artifacts.py:220`). The topology-aware **`resolve_status_surface` is explicitly REJECTED
as the write exemplar** (it would reproduce the coord-routing bug — it is read-side only). The home is the
tracked `kitty-specs/<slug>/` — **not** a gitignored `.kittify/` location — preserving #1771's
tracked/reviewable intent. No bespoke resolver is introduced (unification-not-parity).

**Handle-safety at the PRIMARY entry points (#2136, the foundation of this binding) — caller-canonicalization,
NOT seam-internal.** A bare `mid8`/`slug` handle MUST be canonicalized to the canonical `<slug>-<mid8>` dir
**before** it reaches the topology-blind compose. The placement primitive `primary_feature_dir_for_mission`
(`:1212`) is **deliberately handle-blind by contract** (docstring `:1213`) and **stays so**: it cannot
canonicalize internally, because `_canonicalize_bare_modern_handle` (`:418`) itself calls
`primary_feature_dir_for_mission` at `:454` — folding canonicalization into the primitive is **infinite
recursion**. The cure therefore lives in the **callers**, mirroring the EXISTING live exemplars `:1204`/`:1208`
and `:820`, which canonicalize via `_canonicalize_bare_modern_handle` (`:418` → `_canonicalize_handle` `:467`,
`mission_id`→`mid8`→numeric→`slug`) and pass the *canonical* handle DOWN to the blind compose. Two entry points
are routed through this canonicalization: (1) the kind-aware read seam `resolve_planning_read_dir`'s PRIMARY
leg (`:1306`), and (2) the retrospective WRITE placement (FR-001/FR-003 sites). Both reuse the existing
identity machinery — **no parallel resolver, no silent fallback** (an ambiguous handle raises
`MissionSelectorAmbiguous`, WP07/C-009), and the `meta.json`-present / unresolvable-handle short-circuit legs
stay no-ops. Today the raw read leg (`:1306`) and the raw write composition feed the blind primitive an
un-canonicalized handle, so a bare handle silently diverges from the canonical dir — #2136 identifies this as
"the same root behind #2119." Canonicalizing at both entry points makes the placement authority correct **by
construction** for every PRIMARY read/write, without ever mutating the blind primitive's contract.

### Binding B — Topology teardown is persist-before-destroy (per-path orderings)

Coordination teardown is a single shared seam whose load-bearing invariant is **persist-before-destroy**: the
terminal artifact is persisted to its durable home BEFORE any worktree is destroyed, and **persist runs OUTSIDE
the best-effort `except Exception` swallow** so a persistence failure is never absorbed by the destroy handler.
The exact step order differs by path, because the discard path carries a pre-existing **verify-before-flatten**
invariant the seam MUST NOT break (`_verify_discard_complete` reads `coordination_branch` from `meta.json`,
which `_flatten_discarded_mission` then clears):

- **Merge path:** **persist → destroy** (no verify/flatten step on this path).
- **Discard / close path:** **persist → destroy → verify → flatten** — the persist hook is hoisted ahead of the
  destructive `_discard_mission` call (`mission_type.py:623`, which contains the destroy at `:676`); the
  existing `destroy → verify(:634) → flatten(:639)` sequence is PRESERVED (flatten stays AFTER verify; the seam
  does NOT move flatten ahead of destroy on this path).

In both paths the destroy step never runs before persist completes. WP04 reconciles these orderings; the seam's
docstring records the per-path step order and confirms alignment with this binding.

**Seam-anchor (live, post-#2133).** The "one shared seam" binding unifies the three live
`CoordinationWorkspace.teardown(` sites: **`merge/executor.py:795`** (the `_phase_cleanup_worktrees_and_branches`
cleanup phase), **`cli/commands/merge.py:270`** (the `--abort` helper — #2133 left this in `cli/`, it did NOT
migrate into `merge/`), and **`mission_type._teardown_coordination_worktree`** (`:904`, call `:910`). Because
these span TWO packages plus `mission_type`, the seam lives in **`coordination/`** (near `CoordinationWorkspace`),
not in `merge/`. The *decision* is unchanged; only the *cited anchors* moved when #2133 merged.
Lane-worktree destruction already targets **exact mid8-anchored names** from `lanes.json` (never a slug-prefix
match) — shipped on the base by #2129; this binding inherits that invariant rather than re-implementing it.

## Consequences

- **Positive:** retrospectives survive teardown for all topologies; one owning authority for terminal-artifact
  placement (future terminal artifacts inherit it); the persist-before-destroy invariant is provable
  (destroy-step fault injection) and lives in one seam. The #2123 sibling-deletion data-loss is already closed
  on the base by #2129 (regression-reference, not re-implemented here).
- **Positive (handle-safety at the entry points, #2136):** canonicalizing at the PRIMARY read seam
  (`resolve_planning_read_dir:1306`) and the retrospective WRITE placement makes those entry points handle-safe
  by construction, curing the handle-blind bug class where the handle enters the path resolution — without
  mutating the blind primitive's contract (which recursion forbids anyway). Reuses the existing identity
  machinery (no parallel resolver) and preserves no-silent-fallback. The blind primitive stays the single
  topology-invariant compose; only its callers are made handle-aware.
- **Cost (verification surface):** the read seam feeds planning reads, status, merge, and acceptance, so the
  change is verified against the full `tests/missions/` + `tests/integration/` suites; the `meta.json`-present
  and unresolvable-handle short-circuit legs of `_canonicalize_bare_modern_handle` stay no-ops, so a canonical
  or already-resolvable handle is unaffected.
- **Cost:** the teardown work (binding B) consolidates three live teardown sites that now span two packages
  (`merge/executor.py` + `cli/commands/merge.py`) plus `mission_type.py` — so the shared seam lives in
  `coordination/`. One new enum member + the partition entry (minimal surface).
- **No-persist test (must be UPDATED, not deleted).** #2133 shipped
  `test_phase_cleanup_coord_teardown_failure_is_non_fatal` (`tests/merge/test_executor_coverage.py:616`), which
  asserts teardown-failure is swallowed — i.e. it hard-codes the *absence* of persist-before-destroy. Binding B
  requires that test be **UPDATED** to assert persist-runs-outside-the-swallow (persist before destroy),
  **never deleted to go green** (DIR-041). This pre-empts a future agent deleting it to pass.
- **Single-slice delivery.** With #2133/#2114/#2134/#2135 all merged, both bindings are delivered in **one
  slice** against the settled base — no open-PR gate. Both bindings are UNCHANGED in shape.
- **Verification:** the binding is only credible against a **live coord-topology mission that genuinely
  diverges** from primary (coord surface lacks `meta.json`/`lanes.json`) — a stubbed/flattened fixture
  reproduces the #1771 false-green and is rejected (NFR-002).

## Alternatives considered

- **Gitignored `.kittify/missions/<id>/` home** — rejected: loses #1771's tracked/reviewable intent; the
  retrospective is a reviewable artifact, not transient state.
- **Reorder teardown without consolidating** — rejected: leaves the 3-way duplication, so the invariant
  re-drifts on the next edit (it already drifted once: merge vs discard).
- **A new bespoke terminal-artifact resolver** — rejected: a parallel authority is the split-brain we are removing.
- **Hard-fail retrospect on a torn-down topology** — rejected: that is the #2119 dead-end, not a fix.
- **Canonicalize INSIDE `primary_feature_dir_for_mission` (seam-internal) (#2136)** — rejected as architecturally
  impossible: `_canonicalize_bare_modern_handle` (`:418`) calls `primary_feature_dir_for_mission` (`:454`), so
  folding canonicalization into the primitive is infinite recursion; the primitive is handle-blind by contract
  (`:1213`). The cure is caller-side at the PRIMARY entry points (read seam `:1306` + the retrospective write),
  mirroring the live exemplars `:1204`/`:1208`/`:820`. A new bespoke identity resolver is also rejected — the
  existing `_canonicalize_bare_modern_handle` / `_canonicalize_handle` machinery is reused (unification-not-parity).

## Out-of-scope follow-on (read-surface residual cluster)

Issues #2138 (decision-event payload persists slug as `mission_id`), #2139 (dual `target_branch` reader with a silent
`main` fallback), and #2140 (`is_committed` spec-read coord-unaware post-#2090) are a cohesive SIBLING cluster
of surface-resolution read-surface residuals — **explicitly OUT of this mission's scope.** They are recommended
as their own small follow-on mission, or parked under the #1868/#1716 strangler epic; folding them here would
widen the bounded context past placement + teardown + the handle-safe seam.
