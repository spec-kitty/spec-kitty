---
title: 'ADR: Coordination-Worktree-Empty Surface Policy — Loud Primary Fallback (amended)'
description: 'Reads of an empty coordination worktree fall back loudly to the repository-root checkout; writes establish the coordination surface (amended 2026-10-01).'
status: Superseded
date: '2026-06-19 (original) · **Amended**: 2026-06-21 · **Amended**: 2026-10-01'
---

**loud primary fallback** decision in the Amendment section below.
**Mission**: `single-mission-surface-resolver-01KVGCE8` (WP06, original) ·
`mission-surface-resolver-safety-net-01KVN754` (amendment)
**Requirement**: FR-006 (`#1716`), bound to FR-001/FR-007 (single resolver)
**Module**: `src/specify_cli/coordination/surface_resolver.py`
**Tracker**: [#1716](https://github.com/Priivacy-ai/spec-kitty/issues/1716)

---

## Amendment (2026-10-01 — mission `coord-artifact-single-home-01M3V4BE`)

**Newest amendment first; the 2026-06-21 amendment below is unchanged history.**

### Status of this amendment

This amendment **binds despite the frontmatter `status: Superseded`**. That status marks
the *original* 2026-06-19 hard-fail decision as superseded by the 2026-06-21 amendment in
this same file; it does not retire either amendment. The read-side policy of the
2026-06-21 amendment is current, and so is this one. The read-side raise on
`UNMATERIALIZED` is recorded separately in
[ADR 2026-09-24-2](2026-09-24-2-coord-read-fail-closed.md), and the decision-ledger
reclassification in
[ADR 2026-10-01-3 (4.x)](../4.x/2026-10-01-3-decision-ledger-primary-partition.md).
Do not implement from the original "Decision" section further down.

### Amended decision: writes never substitute the repository root checkout

The 2026-06-21 loud fallback was written as a *read* policy but behaved as a read-and-write
one: a writer that asked the read resolver for a COORD-partition directory and got the
declared PRIMARY-partition fallback wrote a Mission's coordination record into the
repository root checkout, where the coordination branch never saw it. This amendment splits
the policy.

**Single-home rule.** Every COORD-partition artifact of a coordination-routed Mission
(topology `coord` or `lanes_with_coord`, owned checkouts included) has exactly one
writable home: the coordination worktree on the coordination branch. A write obtains its
location only from `PlacementSeam.write_dir(kind)` (`src/mission_runtime/resolution.py`),
the one sanctioned extension of the placement seam. For a COORD kind it delegates to
`specify_cli.coordination.coord_seed.establish_coord_write_location`, which owns
**materialize, seed and refuse**. A writer never substitutes the repository root checkout
for the coordination surface, and `read_dir` is never a write location for a COORD kind.

### Per-state write behaviour

`write_dir` is placement routing (kind plus topology to a directory), not branch-target
routing; the commit ref still comes from `write_target`, and the two agree by construction.
The state is the four-way coordination probe plus the seed marker (the commit trailer
`Spec-Kitty-Coordination-Seed: <mission_id>`, `coord_seed.COORD_SEED_TRAILER`).

| Coordination state of the Mission | `write_dir` result |
|---|---|
| No coordination topology (`lanes`, `single_branch`), or a PRIMARY-partition kind | The declared PRIMARY dir, byte-identical to `read_dir`. No side effects (C-008). |
| Published Mission, an E2-eligible COORD kind (`REVIEW_CYCLE`, `TRACER_FILE`, `ISSUE_MATRIX`, `ACCEPTANCE_MATRIX`) or `STATUS_STATE` | The PRIMARY Mission dir, checked before any coordination probe, so a torn-down coordination branch never raises here. |
| `MATERIALIZED` | The coordination Mission dir. No side effect unless a refused seed commit is pending, in which case the next write re-commits it. |
| `UNMATERIALIZED`, branch present locally | Materialize the worktree first (once), then the `MATERIALIZED` or `EMPTY` row applies. |
| `UNMATERIALIZED`, branch only on a remote | Refuse with `COORDINATION_WORKTREE_UNMATERIALIZED` and a recovery hint (parity with #4970). Nothing is written. |
| `EMPTY`, no seed marker (Mission created before this fix) | Seed once under the status lock: one seed commit on the coordination branch, records restored from the repository root checkout by the prefix rule. A true fork refuses with `COORD_SEED_FORK_REFUSED`; a lock timeout refuses with `STATUS_LOCK_HELD`. |
| `EMPTY`, seed marker present (a Mission created after this fix: a regression) | Loud `WARNING`, restore the COORD-kind paths from the coordination branch tip (never PRIMARY files), then write. |
| `DELETED` | `CoordinationBranchDeleted`, unchanged. |

### Read side (unchanged, C-002)

Reads keep the loud declared PRIMARY fallback for `EMPTY` exactly as the 2026-06-21
amendment states, and `UNMATERIALIZED` keeps the ADR 2026-09-24-2 raise. The one read-side
change: the `EMPTY` warning now fires for post-fix Missions in **both** coordination
topologies, because "post-fix" is discriminated by the seed-marker trailer rather than by
topology. Retiring the read fallback is a follow-up, not part of this amendment.

### Create

`mission create` for a coordination-routed Mission materializes and seeds the coordination
worktree eagerly and commits the creation records on the coordination branch, so the target
branch never receives a COORD record. The expected divergence between the coordination
branch and the target branch is one shared predicate,
`specify_cli.missions._create.is_expected_coordination_divergence`, used by create and by
`doctor coordination`. Residual, named rather than fixed: an `--owned-checkout` create keeps
its status log in the owned checkout's own PRIMARY dir exactly as before (INV-COORD-HOME).

### Other writers

- **`spec-kitty consolidate`.** A real run resolves its status directory through
  `write_dir(STATUS_STATE)` before it takes the merge lock, so it materializes an
  `UNMATERIALIZED` coordination surface (local branch) and proceeds, and seeds a pre-fix
  `EMPTY` one. A remote-only branch, a fork, a deleted branch and a held status lock each
  abort before any state change. **`--dry-run` stays fail-closed and does not
  materialize**: it keeps reading through the read seam and stops on
  `CoordinationBranchDeleted` or `CoordinationWorktreeUnmaterialized`. The asymmetry is
  deliberate; a preview must not create a worktree.
- **`spec-kitty materialize`.** Regenerates derived views; for a coordination-routed Mission
  it resolves the status directory through `write_dir(STATUS_STATE)`, so it creates the
  coordination worktree (once) and seeds a pre-fix `EMPTY` one. A remote-only branch or a
  forked log is reported in the error summary and the remaining Missions are still processed.
- **Commit routing.** `spec-commit` and the other `commit_for_mission` consumers report one
  outcome per surface and exit non-zero when any surface is refused
  (`src/specify_cli/coordination/commit_outcome.py`).

### Enforcement

- `tests/architectural/test_no_write_side_rederivation.py` carries a COORD-writer grammar:
  a census of COORD writer functions must not compose a `KITTY_SPECS_DIR` path onto a
  worktree-named operand, and must not derive a write location from a read resolver. The
  allowlist is empty and its cap in `tests/architectural/_baselines.yaml` is 0.
- **Honest bound of that gate.** It scans only the bodies of the census functions, and it
  flags a `KITTY_SPECS_DIR` join with a worktree-named operand. A future caller that builds
  the Mission dir through `specify_cli.coordination.legacy_resolution._checkout_mission_dir`
  is outside that scan. That helper is documented for non-coordination checkouts only, so
  the gate cannot see a misuse of it. The gate is not weakened for this; the bound is
  recorded so a reviewer knows what the gate does not prove.
- `tests/integration/test_coord_single_home_workflow.py` is the end-to-end invariant: one
  status log, no COORD record on the target branch before consolidation, and the ledger
  committed at its commit points.

### Decision ledger

`DECISION_LEDGER` moved from the COORD to the PRIMARY partition in the same Mission. That
reversal of the #3928 intent has its own record:
[ADR 2026-10-01-3 (4.x)](../4.x/2026-10-01-3-decision-ledger-primary-partition.md). It is
linked, not restated, here. The consequence for this ADR is that `decisions/` is never
coordination residue and is never reset as such.

---

## Amendment (2026-06-21 — mission `mission-surface-resolver-safety-net-01KVN754`)

### Amended decision: coord-empty → **loud primary fallback** (not hard-fail)

A **materialized-but-empty coordination worktree NO LONGER hard-fails.** The
canonical resolver (`resolve_status_surface_with_anchor`) **falls back to the
primary checkout surface and proceeds**, but emits a **clear, structured,
operator-visible warning** at the fallback point. The read keeps working
(liveness); the staleness risk is made **loud and observable** so a human
operator or an orchestrating agent can intervene (flatten or repair) if desired.

### Why the reversal

The original decision (hard-fail, below) rejected primary fallback because it was
**silent** — a silent stale read is the `#1589`/`#1821` split-brain bug. That
rejection rationale is sound *for a silent fallback*. This amendment keeps the
fallback but **removes the silence**: the operator-visible warning names the
stale-surface risk and **both** recovery commands (collapse/flatten **or**
`spec-kitty agent worktree repair --mission <slug>`). The split-brain hazard the
original feared is a *silent* divergence; a *logged* divergence the operator can
see and act on is a different, acceptable trade.

Decisive field evidence: under the strict hard-fail, mission `01KVFTFV` was
forced to **flatten** (drop `coordination_branch`) just to make progress — i.e.
the ADR's own recovery path (a) became the routine workaround. A policy whose
escape hatch is the normal path is too strict for the operational reality;
liveness-with-observability is the better default.

### Scope of the amendment (binding)

- **Applies to the coord-empty state only**, at the canonical resolver seam.
- **Unchanged — still resolve primary (benign):** the create→first-write window
  and the no-coord topology (these were never hard-fails).
- **Unchanged — still HARD-FAIL (do not soften):** the **coord-deleted** state
  (`CoordinationBranchDeleted`, `#1848`). A declared-but-deleted coord branch
  carrying unmerged status is **data loss**, categorically worse than staleness;
  it must keep failing closed. Loud fallback is for *empty*, never for *deleted*.
- The warning is **non-silent and load-bearing**: a test asserts it fires on the
  coord-empty path (the fallback must be observable, not best-effort).

### Consequence for the typed-error surface

Coord-empty stops raising `CoordinationWorktreeEmpty`/`STATUS_READ_PATH_NOT_FOUND`
and instead returns the primary dir + warning. Callers that previously caught the
coord-empty hard-fail now receive a successful (warned) read. The genuinely
unresolvable / ambiguous cases still raise their typed errors (this mission's
typed-error-pass-through requirement is unaffected — coord-empty simply leaves
the error class).

> The original 2026-06-19 decision and its alternatives are retained below as
> historical record. Where they say "hard-fail on coord-empty", read "superseded
> by the loud primary fallback above".

### Stale reference correction (2026-06-21)

The original "Read-CLI residual (#2046)" consequence below is **stale**: #2046 is
**closed and fixed**. The operator read CLIs (`agent tasks status`,
`agent context`, `agent mission`, `decision`) now route through the unified
`missions/_read_path_resolver.resolve_handle_to_read_path`, which consumes the
`resolve_declared_mid8` cascade — so a bare-slug handle against a coord-topology
mission resolves its mid8 instead of silently reading primary. (`acceptance`
deliberately retains the lower `resolve_mission_read_path` with an explicit mid8
— the lenient acceptance-lane carve-out, blessed by the FR-010 selection guard.)
Mission `mission-surface-resolver-safety-net-01KVN754` does not re-do that work;
its differential characterization test **verifies and regression-guards** the
fix (the four `coord-*/bare` cells).

---

## Context

A Spec Kitty mission's status surface (`status.events.jsonl` /
`status.json`) lives in exactly one of two places, decided by topology:

- **primary checkout** — `kitty-specs/<slug>[-mid8]/` — for missions with no
  coordination branch (and during the create→first-write window).
- **coordination worktree** — `.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/`
  — for coord-topology missions, where lane processes write through
  `BookkeepingTransaction` and lanes sparse-exclude the status files.

There is a hazardous intermediate topology state — **coord-empty**: the mission
declares `coordination_branch` in its primary `meta.json`, the coordination
worktree ROOT has been materialized on disk, but it carries **no mission dir**
(no status surface yet). This is distinct from two adjacent, benign states:

- **create→first-write window** — `coordination_branch` declared, coord worktree
  root **not** materialized. The primary checkout legitimately holds the
  bootstrap status events; reading primary is correct.
- **no-coord** — no `coordination_branch` at all. Primary is the sole,
  authoritative, non-divergent surface.

Historically the resolver's coord-empty path either fell back to the primary
checkout (exposing a stale, split-brain status surface — the `#1589`/`#1821`
class) or raised a *bare* `StatusReadPathNotFound` with no operator guidance.

Before this mission the same coord-vs-primary selection was duplicated across
several resolvers (the read-path resolver, the surface resolver, the aggregate,
the mission-runtime boundary, and a 5th path-shape predicate site in
`status_transition.py`, `#1900`). A policy that lived in only one of those
copies would silently diverge.

## Decision

A **materialized-but-empty coordination worktree HARD-FAILS**. The single
canonical resolver (`coordination.surface_resolver.resolve_status_surface_with_anchor`
— FR-001/FR-007's sole selection authority) raises `CoordinationWorktreeEmpty`,
a carve-out of `StatusReadPathNotFound` that:

1. **Carries the same `error_code`** (`STATUS_READ_PATH_NOT_FOUND`) so every
   existing `except StatusReadPathNotFound` fail-closed handler keeps catching
   it and every caller that routes on the stable code keeps working. (This
   mirrors the sibling `CoordinationBranchDeleted` carve-out for the
   coord-deleted state, `#1848`/`#1889` R3.)
2. **Names BOTH operator recovery paths** in its message (NFR-004 — errors are
   actionable):
   - **(a) collapse/flatten** the mission — remove the `coordination_branch`
     key from `meta.json` so the primary checkout becomes authoritative; **OR**
   - **(b) recreate/populate** the coordination worktree — run
     `spec-kitty agent worktree repair --mission <slug>` so it carries the
     mission status surface.
3. **Never silently falls back to the primary checkout.** Reading primary here
   would expose a stale, split-brain status surface — the exact failure class
   the single-resolver mission exists to eliminate (FR-005/FR-006).

The hard-fail fires for **both** mission-handle forms — a bare `--mission <slug>`
and the canonical `--mission <slug>-<mid8>` — so the policy is handle-invariant.

This policy is **bound to the single resolver**: because FR-001/FR-007 collapsed
selection to `resolve_status_surface_with_anchor` (and the `#1900`
`status_transition.py` predicates were migrated to it, draining the C-002
topology-ratchet allowlist entry), there is exactly one place the coord-empty
decision is made, and no parallel resolver can contradict it.

## Distinctions preserved (what does NOT hard-fail)

- **create→first-write window** (coord declared, worktree NOT materialized) →
  the resolver composes the coord path and the aggregate's create-window gate
  keeps the **primary checkout authoritative** until the worktree exists. A
  regression that hard-failed here would break first-write on a freshly created
  coord mission. (Mutation-guarded by the equivalence test's
  `test_create_first_write_window_resolves_primary` and the surface-collapse
  test's `test_create_window_unmaterialized_coord_resolves_primary`.)
- **no-coord** → primary is authoritative; no hard-fail.
- **coord-deleted** (branch declared but deleted from git) → the distinct
  `CoordinationBranchDeleted` carve-out (`#1848`), not coord-empty.

## Consequences

- **Positive.** A genuinely broken coordination topology is surfaced **loudly
  and actionably** rather than silently degrading to a stale primary read. The
  operator is handed two concrete recovery commands. The policy is single-sourced
  on the canonical resolver, so it cannot drift across the (former) duplicate
  selection sites.
- **Bounded backward-compatibility.** `CoordinationWorktreeEmpty` subclasses
  `StatusReadPathNotFound` and reuses its `error_code`, so existing fail-closed
  handlers and code-based routing are unaffected; only the diagnostic is richer.
- **Known scope boundary.** The `MissionStatus` aggregate continues to translate
  the resolver's fail-closed signal to its own single boundary exception
  (`CoordAuthorityUnavailable`, WP04/FR-015–FR-023) for every handle form — a
  separately-tested public contract used by the `agent status` CLI. Converging
  the aggregate's *exception type* with the resolver's is therefore deferred (it
  would regress that boundary), and the corresponding equivalence-matrix cells
  remain documented, allowlisted strict-xfails (see
  `tests/missions/test_surface_resolution_equivalence.py`). The user-facing
  FR-006 two-path message is delivered regardless, at the resolver seam.
- **Read-CLI residual (#2046).** The operator read CLIs (`agent tasks status`,
  `agent context`, `agent mission`) call the lower `resolve_mission_read_path`
  primitive directly and are mid8-blind for a **bare slug**, so a bare-slug
  handle against a coord-topology mission still resolves the primary checkout
  rather than hard-failing here. Closing this needs the `resolve_declared_mid8`
  cascade inside the read path; it is tracked in **#2046** (the earlier deferral
  to the now-closed #1918 was incorrect, found by the post-merge architecture
  review). The four `coord-*/bare` equivalence-matrix cells are its acceptance gate.

## Alternatives considered

1. **Silent primary fallback.** Rejected: it is the split-brain bug
   (`#1589`/`#1821`) this mission exists to kill — a coord-declared mission that
   reads a stale primary surface mis-reports WP lane state.
2. **Bare `StatusReadPathNotFound` with no guidance.** Rejected: dead-ends the
   operator (violates NFR-004). The recovery is non-obvious (collapse vs
   repair), so the message must spell out both.
3. **Auto-repair (silently recreate/populate the worktree).** Rejected: the
   resolver is a read-side authority; mutating topology as a side effect of a
   read would be surprising and could mask a genuine teardown the operator
   intended. The repair path is offered as an explicit command instead.
