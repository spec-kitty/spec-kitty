---
title: 'ADR: MissionResolver Port — One Walk Trunk, Shell-Side DI, No Shared Container'
description: 'One `MissionResolver` Protocol in `mission_runtime` with adapters injected shell-side and a token-keyed AST allowlist — no second Protocol and no shared container.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-07-08'
---

## Context and Problem Statement

The Phase 1 gate ([2026-06-26-1](2026-06-26-1-single-authority-seam-and-call-site-gate.md))
closed the #2164 canonicalization-fold and #2160 coord-authority classes with a
seam-plus-AST-gate, but deliberately deferred the deeper defect this mission (#2173
Phase 2) closes: `kitty-specs/` is walked from **many** independent call sites
(`_build_index` in the canonicalizer, `status/identity_audit.py`,
`merge/ordering.py`, `core/paths.py`, a dashboard scanner, a handful of
`--all`-mode CLI validators, migration scripts, …), each re-implementing the same
`iterdir()` + `meta.json` read, each re-walking on every call with no shared
in-memory index, and each free to silently diverge from the others' notion of
"how to find a mission." Phase 1's gate fences the canonicalization *fold*; it does
not fence *walking* itself, so a new raw `kitty-specs/` enumeration can still be
added anywhere in `src/` without tripping anything.

This mission ships the Phase 2 follow-on recorded as deferred work in the Phase 1
ADR: a `MissionResolver` Protocol port with one real filesystem adapter
(`FsMissionResolver`) and one in-memory test double (`FakeMissionResolver`), a
single free-function trunk (`resolve_mission`) that every identity-resolution
caller is threaded through (WP01–WP03), and — the subject of this ADR — the
structural gate that makes "one walk" a build-time invariant rather than a
reviewer-memory convention (WP04, mirroring the Phase 1 ADR's own closing
argument: a convention "leaks" the moment nobody is looking).

## Decision Drivers

- **Bind the "one walk" invariant by construction (D-06).** Without a structural
  gate, the trunk this mission builds is exactly as durable as the last
  reviewer's attention span — a "walker #7" reappears the next time someone needs
  a quick mission listing and reaches for `Path.iterdir()` instead of the port.
- **Full trunk, not a 7th parallel path (D-08).** The dominant read path reaches
  the walk through the *free function* `resolve_mission`, not through an
  assembler-injected port alone — so the gate must also guard against
  `resolve_mission` callers silently multiplying, not only against raw
  `iterdir()`/`glob()`/`scandir()` calls.
- **Stay inside the existing ledger (D-Q2).** `test_layer_rules.py`'s
  `_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI` ledger does not list `"context"`; this
  mission's charter is to **drain** that ledger, not add to it, so the Protocol
  location and the gate's own imports must not create a new
  `mission_runtime → specify_cli.context` edge.
- **No partial-adoption tax.** Every genuine `kitty-specs/` walker that predates
  this mission must be accounted for on day one — the gate must be green on
  introduction, not a slow-burn migration that reds CI the moment it lands.
- **Preserve the anti-fold carve-outs (C-001/C-002/C-003).** `status/identity_audit.py`,
  `merge/ordering.py`, and `core/paths.py` have deliberately-different semantics
  from the resolver (identity-audit needs the missions the resolver *skips*;
  `merge/ordering.py` needs a caller-supplied non-primary scan root under a merge
  lock; `core/paths.py`'s error-listing helper is a best-effort swallow-and-degrade,
  never fail-closed) — folding them into the resolver would silently change their
  behavior, so the gate must **permit** them, not force them through the trunk.

## Considered Options

1. **Rely on code review alone** to catch new raw walkers (status quo after WP01–WP03).
2. **Fold every walker into the resolver unconditionally**, including the three
   anti-fold sites (C-001/C-002/C-003).
3. **AST call-site gate + token-keyed allowlist**, modeled on
   `test_protection_resolver_call_sites.py` and the Phase 1 gate — **chosen**.
4. **Runtime enforcement** (e.g., monkeypatch `Path.iterdir`/`Path.glob` process-wide
   to detect `kitty-specs/` access outside the resolver).

## Decision Outcome

**Chosen option:** "AST call-site gate + token-keyed allowlist" (Option 3).

### Decisions recorded

- **One `MissionResolver` trunk.** `mission_runtime.mission_resolver_port.MissionResolver`
  is the sole Protocol; `specify_cli.context.mission_resolver.FsMissionResolver` /
  `FakeMissionResolver` are the sole adapters. There is no second Protocol, no
  second real adapter.
- **Protocol in `mission_runtime`, adapters in `specify_cli.context`** (D-Q2). The
  shell (`mission_runtime.resolution`) types its `resolver` parameters against the
  local Protocol without importing `specify_cli.context` — no new
  `mission_runtime → specify_cli.context` ledger edge. Adapters import the
  Protocol via the already-allowed `specify_cli → mission_runtime` (package-root)
  direction. `test_layer_rules.py` stays green with **zero new edges**.
- **Per-seam default-param DI (`x or Default()`), no shared container.** Every
  seam in this mission family (`MissionResolver`, Clock, InstalledVersion) injects
  independently at its own call site (`resolver: MissionResolver | None = None`
  → `resolver or FsMissionResolver(repo_root)`). There is **no** DI container or
  registry shared across seams (C-006) — each port is wired where it is consumed,
  not resolved through a central object graph.
- **One adapter per port.** `FsMissionResolver` is the only production adapter;
  `FakeMissionResolver` exists solely to make consumers FS-free-testable
  (NFR-001). Neither is cached at module or process scope (C-005): no
  `@lru_cache`, no singleton — each instance re-walks (or re-reads its in-memory
  list) on every call, so a mission created or merged mid-process is visible to
  the very next `resolve`.
- **No port on the frozen context.** `MissionExecutionContext` (renamed from
  `ExecutionContext` in WP01) remains a plain, frozen, FS-free value object.
  `build_execution_context` takes no resolver and performs no I/O; the port is
  injected at the shell's assembler and at the callers that resolve a handle
  *before* the context exists (`resolve_action_context`, `mission_context_for`,
  `resolve_placement_only`) — never inside the pure builder (D-01).

### Corollaries (scope boundaries)

- **The resolver is handle→mission resolution only.** It is explicitly **not**:
  - the `target_branch` field reader (a separate, sibling concern — FR-008 /
    `#2139`, delivered as its own WP, not folded into this port);
  - the `merge/ordering.py` aggregate (caller-supplied non-primary scan root,
    `mission_number` assignment, under the merge lock — C-002).
- **The blind-primitive non-fold rule is restated (C-007).** `primary_feature_dir_for_mission`
  stays handle-blind, exactly as ADR `2026-06-26-1` established: the
  canonicalizer that calls it also calls the resolver's fold, so folding
  canonicalization *into* the primitive would recurse. The resolver sits at the
  shell, in front of the primitive, never inside it.
- **No new layer-ledger edge (the ledger-dodge).** This is the direct
  continuation of D-Q2 above: #2173's own charter is to **drain**
  `_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI`, not add to it. A design that "solves"
  the Protocol-location question by adding `"context"` to the ledger would be
  self-defeating — it would grow the very debt ledger this mission exists to pay
  down. The chosen split (Protocol in `mission_runtime`, adapters in
  `specify_cli.context`, structural typing instead of inheritance) is what makes
  a zero-new-edge outcome possible; any future variant of this port must clear
  the same bar.
- **No process cache.** Restated from C-005 for emphasis: the resolver is
  request-scoped. A process-level cache would reintroduce the exact staleness
  bug (a mission created mid-process invisible to a stale index) that motivated
  moving off the ad-hoc per-caller walks in the first place.
- **Fail-closed-loud.** Ambiguity raises `AmbiguousHandleError` /
  `MissionSelectorAmbiguous`; a cold-miss raises `MissionNotFoundError` naming
  `spec-kitty migrate backfill-identity`. Neither path silently picks a
  first match or falls back to a verbatim handle (NFR-005, C-009).

### The gate (FR-007)

`tests/architectural/test_mission_resolver_walker_gate.py` enforces three
guarantees:

- **G-1 — no unsanctioned raw enumeration.** No `src/` module performs a raw
  `iterdir()` / `glob()` / `scandir()` enumeration of `kitty-specs/` except the
  sanctioned resolver module (`specify_cli/context/mission_resolver.py`) and a
  **token-keyed allowlist** of legacy walkers being strangled. The allowlist was
  seeded from a **live census grep**, not copied from the mission's planning
  estimate: the actual count is **19 legacy runtime walker files** (not the
  planning-time "~16" estimate), plus two migration-package directory prefixes
  (`upgrade/migrations/`, `migration/`) covering 10 migration-only files that must
  never depend on the runtime resolver (C-004). Two files the planning notes
  named as walkers (`retrospective/summary.py`, `cli/commands/retrospect.py`)
  turned out, on inspection, to walk `.kittify/missions/` — a **different**
  scan root — and are correctly *not* in the allowlist; a scan-root-keyed gate
  would never match them regardless.
- **G-2 — token-keyed, not line-pinned.** The allowlist and the taint-detection
  heuristic both key on module paths and identifier/name tokens (a curated
  `KITTY_SPECS_DIR`-derived-variable check plus a small closed vocabulary of
  established parameter names such as `mission_specs_dir`, `scan_root`,
  `wt_specs`), never on line numbers — line numbers drift on every unrelated
  edit and rot the gate silently (the Phase 1 ADR's own maintenance warning).
- **G-3 — scope derives from `src/`.** The gate walks `_SRC_ROOT.rglob("*.py")`
  wholesale; it does not hardcode a subdirectory allowlist that a new package
  could fall outside of. A companion sanity test asserts the scan actually
  reaches known walker files, proving the scope has not silently narrowed.
- **Free-function-caller ceiling.** Because the dominant read path is the free
  function `resolve_mission` (D-08), not only the assembler-injected port, the
  gate separately counts bare-name `resolve_mission(...)` call sites across
  `src/` and asserts the count does not exceed the known ceiling (9, as of this
  mission). A tenth caller must not appear silently; raising the ceiling is a
  deliberate, reviewed edit to this test file, exactly like every other ratchet
  constant in this codebase.

### Consequences

#### Positive

- The "one walk" invariant recorded in D-06/D-08 is now a CI failure, not a
  reviewer-memory convention — a future "quick mission listing" reaching for
  `Path.iterdir()` on `kitty-specs/` fails the gate immediately, and a new
  `resolve_mission` caller past the ceiling fails just as loudly.
- The anti-fold carve-outs (C-001/C-002/C-003) are preserved by construction:
  they are allowlisted, not silently swept into the resolver, so
  `identity_audit`'s "find the missions the resolver skips" and
  `merge/ordering.py`'s caller-supplied scan root keep their distinct semantics.
- The gate generalizes a pattern this codebase already trusts
  (`test_protection_resolver_call_sites.py`, and the Phase 1 seam gate) rather
  than inventing new machinery.

#### Negative

- The taint-detection heuristic (KITTY_SPECS_DIR-derived variable names plus a
  curated parameter-name vocabulary) is a static approximation, not full
  dataflow analysis — it can in principle miss a walker that threads the specs
  directory through an unconventional name with no local `KITTY_SPECS_DIR`
  reference in the same file. This is the same class of limitation the Phase 1
  gate accepted (bare-name-call matching over full call-graph resolution); the
  mitigation is the same: the allowlist and the vocabulary are both
  human-reviewed, deliberately-extended surfaces, not machine-inferred ones.
- The allowlist itself is maintenance surface: 19 legacy files (plus 2 migration
  prefixes) must be revisited if `#2173`'s later phases fold any of them into
  the trunk — each fold is a deliberate allowlist-shrink, mirroring NFR-002's
  shrink-only-ratchet discipline.

#### Neutral

- This ADR does not itself perform any additional folding of the 19 allowlisted
  legacy walkers into the resolver — that is out of scope for WP04 and left to
  future #2173 phases (or explicit non-goals, for the three anti-fold sites).

### Confirmation

The decision is confirmed when: (1) the gate is green against the live
allowlist on introduction (no red-on-day-one migration debt); (2) a deliberately
planted raw `iterdir()`/`glob()`/`scandir()` enumeration of `kitty-specs/`
outside the allowlist fails the gate; (3) the free-function-caller ceiling
assertion fails if a **10th** `resolve_mission` call site is added without a
corresponding, reviewed ceiling bump; and (4) the full
`tests/architectural/` suite remains green, proving no regression against the
Phase 1 gate or any other structural ratchet.

## Pros and Cons of the Options

### Option 1 — Rely on code review alone

**Pros:** zero new infrastructure.

**Cons:** this is exactly the status quo the Phase 1 ADR already showed leaks
(#2164, #2160); nothing stops "walker #7" from reappearing the moment a reviewer
is looking elsewhere.

### Option 2 — Fold every walker into the resolver unconditionally

**Pros:** conceptually simplest — "everything goes through one function."

**Cons:** breaks the three anti-fold sites' deliberately different contracts.
`status/identity_audit.py` exists specifically to find the missions the
resolver's fail-closed contract would skip (`mission_id`-less directories);
folding it in would make the audit blind to the exact defect class it audits
for. `merge/ordering.py` needs a caller-supplied, possibly non-primary scan
root under an active merge lock — the resolver's `repo_root`-bound construction
doesn't fit. `core/paths.py`'s helper is a best-effort, swallow-and-degrade
error-listing aid for CLI messages; the resolver's fail-closed-loud contract
would turn a friendly hint into a hard crash in exactly the CLI-error-message
context where a crash is least welcome.

### Option 3 — AST call-site gate + token-keyed allowlist (CHOSEN)

**Pros:** closes the class by construction; reuses a proven, shipped idiom;
allows explicit, reviewed carve-outs for the three anti-fold sites; scope
derives from `src/` so it can't silently go blind; token-keyed so it doesn't rot
on unrelated line-number drift.

**Cons:** the taint heuristic is a static approximation (see Negative
consequences above); the allowlist is maintenance surface.

### Option 4 — Runtime enforcement (monkeypatch `Path.iterdir`/`Path.glob`)

**Pros:** would catch violations regardless of how cleverly a caller obscures
the raw call syntactically.

**Cons:** process-wide monkeypatching of `Path` methods is invasive, has to be
active during every test run (not just an architectural-gate pass), cannot
distinguish "walking `kitty-specs/`" from "walking any other directory that
happens to share a `Path` instance's method" without also tracking *which path*
was walked at runtime — effectively reimplementing the same
`KITTY_SPECS_DIR`-anchored check, but at runtime cost, in every test process,
instead of once in CI's architectural pass. Static AST analysis is strictly
cheaper for a build-time invariant.

## More Information

- Predecessor: [2026-06-26-1 — Single-Authority Seam + Call-Site Gate for
  Resolution Boundaries (Phase 1)](2026-06-26-1-single-authority-seam-and-call-site-gate.md)
  — this ADR is the "Phase 2 (deferred follow-on)" that ADR's "More Information"
  section named.
- Gate precedent copied: [`tests/architectural/test_protection_resolver_call_sites.py`](../../../tests/architectural/test_protection_resolver_call_sites.py)
- New gate: [`tests/architectural/test_mission_resolver_walker_gate.py`](../../../tests/architectural/test_mission_resolver_walker_gate.py)
- Port contract: [`kitty-specs/mission-resolver-port-01KX1C05/contracts/mission-resolver.md`](../../../kitty-specs/mission-resolver-port-01KX1C05/contracts/mission-resolver.md)
- Cross-references: [#2173](https://github.com/Priivacy-ai/spec-kitty/issues/2173), [#1619](https://github.com/Priivacy-ai/spec-kitty/issues/1619)
