---
title: 'ADR: Single-Authority Seam + Call-Site Gate for Resolution Boundaries (Phase
  1)'
description: 'Handle canonicalization and surface-authority choices move behind one sanctioned seam policed by an AST call-site gate; the blind primitive stays blind to avoid recursion.'
status: Accepted
date: '2026-06-26'
---

## Context and Problem Statement

Logic in this codebase reaches infrastructure / resolution boundaries **directly**: a
handle (`mission_id` / `mid8` / `slug`) is composed into a directory, and coordination-vs-primary
artifact authority is selected, at the call site. Each boundary today is governed by a
**convention every caller must remember** — "canonicalize the handle before you compose it,"
"read `meta.json` from the primary anchor," "write status to the coord surface but planning to
primary." Nothing enforces the convention; correctness is a property of every caller's memory.

The convention demonstrably leaks:

- **#2164 (write-leg fold divergence).** The "fix" for the canonicalization boundary
  introduced **three different folds** of the same handle→dir canonicalization — the read seam,
  the write placement, and a third site each re-implemented the rule, and they diverged. The
  duplication *is* the defect: a bare `mid8`/`slug` handle resolves to a different dir than the
  canonical `<slug>-<mid8>` wherever a caller forgets (or mis-copies) the fold.
- **The #2160 class (coord-vs-primary authority bypass).** `mark-status`, `move-task`, and
  `safe_commit` each independently decide which surface to write, and each can write the *wrong*
  one (coord when it should be primary, or vice versa). Same shape: an infra/authority decision
  made per-caller, recurring as an N+1 family.

The naive cure — fold the guard into the blind primitive `primary_feature_dir_for_mission` — is
**architecturally impossible**: the canonicalizer `_canonicalize_bare_modern_handle` itself calls
that primitive, so folding canonicalization into the primitive is **infinite recursion**, live-reproduced
and recorded as FR-011. The primitive is handle-blind *by contract* and must stay so. The guard
must therefore live at the **seam** in front of the primitive, not inside it.

This is not a foreign architecture — the repo already lives by the pattern. `resolution.py`'s core
is explicitly pure with I/O threaded in by an imperative shell; `RuntimeEventEmitter(Protocol)` +
`NullEmitter` is a shipped port seam; and — most relevantly — `test_protection_resolver_call_sites.py`
already enforces a single-authority free function (`ProtectionPolicy.resolve`) with an AST
call-site gate and a curated allowlist. #2173 Phase 1 **generalizes that existing idiom** to the
resolution/placement boundaries, rather than importing a new mechanism.

## Decision Drivers

- **Close the bug class by construction**, not by per-caller memory — a forgotten or mis-copied fold must be a CI failure, not a latent runtime divergence.
- **Minimal churn, no partial-adoption tax** — the remedy must not split the codebase into "ported" and "un-ported" halves with two coexisting conventions.
- **Match an idiom the repo already uses** — `test_protection_resolver_call_sites.py` is the proven, shipped precedent; copy it rather than invent.
- **Preserve no-silent-fallback and fail-closed semantics** — ambiguity raises a typed error (`MissionSelectorAmbiguous`, C-009 / WP07); a cold-miss fails loud, never a verbatim passthrough.
- **Stay out of the blind primitive** — folding the guard into `primary_feature_dir_for_mission` recurses (FR-011); the guard lives at the seam.

## Considered Options

1. **Status-quo per-caller canonicalization convention** — every caller remembers to canonicalize / pick the right surface.
2. **Fold the guard into the blind primitive** `primary_feature_dir_for_mission`.
3. **Single sanctioned seam + AST call-site gate** (generalize `test_protection_resolver_call_sites.py`) — **chosen for Phase 1**.
4. **Full injectable DI port** (`MissionResolver` Protocol + real/fake adapters) — **deferred to Phase 2**.

## Decision Outcome

**Chosen option:** "Single sanctioned seam + AST call-site gate" (Option 3), because it closes the #2164 / #2160 bug class **by construction** at roughly a tenth of the churn of a full DI port, with
no partial-adoption tax, by generalizing a pattern the repository already ships and trusts.

Every resolution/placement boundary **delegates to the single canonical fold** rather than
re-implementing it:

- The handle→dir canonicalization boundary (#2164) routes through **one** canonicalizer; no caller composes a raw handle.
- The coord-vs-primary authority boundary (#2160) routes through **one** authority decision; `mark-status` / `move-task` / `safe_commit` do not each pick a surface.

An **AST architectural gate**, modeled directly on `test_protection_resolver_call_sites.py`, makes a
bypass a CI failure: a raw `KITTY_SPECS_DIR / <unresolved handle>` compose, or a coord-vs-primary
authority decision made outside the sanctioned seam, fails the gate. A **curated allowlist** names
the one sanctioned authority per boundary, exactly as the FR-010 gate names
`protection_policy.py` + `commit_helpers.py`.

**Non-negotiables (binding across all squads):**

- The guard lives at the **seam**; the primitive `primary_feature_dir_for_mission` stays **blind** (folding it in recurses — FR-011).
- Ambiguity raises **`MissionSelectorAmbiguous`** (C-009 / WP07) — **never** a silent pick.
- A cold-miss (handle absent from the resolver) is **fail-closed-loud** — never verbatim passthrough.
- **One** sanctioned authority per boundary (no parallel resolvers); the allowlist is the explicit, reviewed record of it.

### Consequences

#### Positive

- **By-construction closure** of the #2164 (canonicalizer) and #2160 (coord-authority) classes: a future caller cannot silently re-introduce a raw compose or a wrong-surface write — the gate fails CI.
- **~10% of the port's churn** — one delegation per seam + one convergence test + one AST gate, versus a Protocol + adapter + stub + DI seam threaded through ~80 call sites with ~27 test rewrites.
- **No partial-adoption tax** — there is no "ported vs un-ported" half-state; a site either delegates to the sanctioned fold or trips the gate.
- **Generalizes a proven in-repo pattern** (`test_protection_resolver_call_sites.py`) — no new mechanism, no framework, no god-object.
- **Applies uniformly** to both instances: the same seam-plus-gate shape fences the canonicalizer (#2164) and the coord-vs-primary authority (#2160).

#### Negative

- **The gate does NOT consolidate the duplicated `kitty-specs/` enumeration** (3+ parallel walkers) or the per-call uncached re-walk / TOCTOU — that genuine consolidation needs the **Phase 2** `MissionResolver` port and is explicitly out of scope here.
- **AST gates carry their own maintenance** — line-pin / allowlist upkeep, and the curated sanctioned-seam allowlist must be deliberately extended (with a rationale comment naming the one flow each entry authorises), per the FR-010 precedent.
- **Forward-only** — the gate fences *new* bypasses; it does not retroactively reconcile a mission already written to the wrong surface (the flatten / manual-recovery flow remains the remedy for legacy splits).

#### Neutral

- Status/coord write destinations are unchanged — this decision governs *how* a boundary is crossed (one sanctioned seam), not *which* surface a given artifact kind targets (the kind partition, settled by the predecessor ADRs).

### Confirmation

The decision is confirmed when: (1) a parametrized convergence test proves the read-seam and
write-seam resolve **identically for every handle form** (`mission_id`, `mid8`, numeric, `slug`);
(2) the AST gate, with a runnable synthetic self-test, **fails** on a deliberately re-introduced raw
compose / wrong-surface write; and (3) #2164 and the #2160 class no longer reproduce against a
**live coordination-topology mission that genuinely diverges** from primary (a stubbed/flattened
fixture reproduces the false-green and is rejected). Confidence: high for bug-class closure — the
pattern is already shipped and trusted for the protected-branch boundary.

## Pros and Cons of the Options

### Option 1 — Status-quo per-caller canonicalization convention

Each caller remembers to canonicalize the handle / select the surface before composing.

**Pros:**

- Zero new infrastructure; the code already works for canonical handles.

**Cons:**

- **#2164 proves it leaks** — the convention propagated **three variant folds** that diverged.
- The #2160 class is the same leak on the authority axis (mark-status / move-task / safe_commit).
- Correctness depends on every caller's memory; the N+1 returns on the next edit.

### Option 2 — Fold the guard into the blind primitive

Make `primary_feature_dir_for_mission` canonicalize internally.

**Pros:**

- Conceptually "one place," if it could work.

**Cons:**

- **Infinite recursion (FR-011), live-reproduced** — `_canonicalize_bare_modern_handle` calls the primitive, so folding canonicalization into it recurses.
- Breaks the primitive's deliberate handle-blind contract.

### Option 3 — Single sanctioned seam + AST call-site gate (CHOSEN)

Every boundary delegates to one canonical fold; an AST gate + curated allowlist make a bypass a CI failure (generalizing `test_protection_resolver_call_sites.py`).

**Pros:**

- Closes the class **by construction**; ~10% of the port's churn; no partial-adoption tax; generalizes a proven idiom; applies uniformly to #2164 and #2160; preserves typed-ambiguity + fail-closed.

**Cons:**

- Does not consolidate enumeration / TOCTOU (Phase 2); AST gate carries line-pin / allowlist maintenance.

### Option 4 — Full injectable DI port (DEFERRED to Phase 2)

A `MissionResolver` Protocol + `FsMissionResolver` + `FakeMissionResolver`, owning the one
`kitty-specs/` walk, threaded into `resolution.py`'s shell via `resolver=None`.

**Pros:**

- Consolidates the 3+ parallel walkers, the per-call re-walk, and the TOCTOU; makes the pure builder FS-free-testable; is the concrete first move on #1619's spine.

**Cons:**

- **Over-built for the #2164 / #2160 bug-closure alone** — >10× the diff (Protocol + adapter + stub + DI seam across ~80 sites + ~27 test rewrites) to close the *same* class the gate closes.
- It is the **enumeration-consolidation / #1619-unblock** layer, a distinct strategic concern — recorded here as the **deferred follow-on**, not this decision.

## More Information

**Ratification (2026-07-29, write-side-seam-matrix-tracer-01KYP3MH WP02, HiC-approved).**
This ADR was `status: Proposed` but de-facto shipped — the coord-authority gate it
governs (`tests/architectural/test_resolution_authority_gates.py`) has been live and
enforced since the sibling `single-authority-resolution-gates-01KW1P0F` mission. WP02
re-pins the gate's census floor (`COORD_AUTHORITY_WRITE_FLOOR` 4 → 3, "Move A" per
[`contracts/coord-authority-gate.md`](../../../kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/contracts/coord-authority-gate.md))
by routing `decisions/emit.py` off the kind-blind resolver onto the kind-aware
`placement_seam(...).read_dir(STATUS_STATE)` seam — the natural site to formally ratify
this ADR to `Accepted`. A future **Move B** — recognizing `write_target(kind=...)` calls
as sanctioned coord-write authority in the gate's predicate — is named here as the
**amendment target** for this ADR: it changes the gate mechanism itself (not merely the
census), so it must amend this ADR (def-use gated, with a preserved non-vacuity proof),
never land as a contract-only predicate widen.

**Amendment (2026-09-28, [#5146](https://github.com/spec-kitty/spec-kitty/issues/5146)):**
`tests/architectural/test_resolution_authority_gates.py` was deleted in #3285 (`177e06269`), and the
coord-authority write floor (`COORD_AUTHORITY_WRITE_FLOOR`, `_COORD_WRITE_BY_DESIGN`) was retired with
it, so the Move B amendment target above no longer has a gate to amend. The call-site guarantee over
`resolve_feature_dir_for_mission` is now enforced by the census in
`tests/architectural/test_no_read_side_bypass.py`; the write side is covered by
`tests/architectural/test_no_write_side_rederivation.py` and
`tests/architectural/test_write_surface_placement_guard.py`. The def-use handle-canonicality check has no
successor: its remaining target, the public `primary_feature_dir_for_mission` wrapper, was itself deleted
(T035).

**Phase 2 (deferred follow-on, under [#1619](https://github.com/Priivacy-ai/spec-kitty/issues/1619)).**
The `MissionResolver` port — Protocol contract + one real FS adapter + one fake, owning the single
`kitty-specs/` walk and threaded into the resolution shell via the existing default-param idiom
(`resolver: Port | None = None` → `resolver or RealAdapter()`) — is the strategic enumeration-consolidation
layer that this Phase 1 gate deliberately does **not** attempt. It kills the multi-walker duplication,
the per-call uncached re-walk, and the TOCTOU, and makes the pure builder FS-free-testable (the #1619
unblock). It is the layer the operator's original resolver-port thesis pointed at, sharpened: ports inject
into the **shell / builder**, never onto the frozen `MissionExecutionContext` value object. It is recorded
here as the next strategic move, not part of this decision.

- Synthesis / investigation record: [`docs/plans/engineering-notes/2173-infra-logic-separation/00-SYNTHESIS.md`](../../../docs/plans/engineering-notes/2173-infra-logic-separation/00-SYNTHESIS.md)
- Cross-references: [#2173](https://github.com/Priivacy-ai/spec-kitty/issues/2173), [#1619](https://github.com/Priivacy-ai/spec-kitty/issues/1619), [#2164](https://github.com/Priivacy-ai/spec-kitty/issues/2164), [#2160](https://github.com/Priivacy-ai/spec-kitty/issues/2160)
- Predecessor ADRs: [2026-06-24-1 — Kind- and Topology-Aware Artifact Placement](2026-06-24-1-kind-and-topology-aware-artifact-placement.md) · [2026-06-22-1 — MissionTopology SSOT](2026-06-22-1-mission-topology-ssot.md) · [2026-06-24-2 — Write-Branch Resolution PRIMARY Anchor](2026-06-24-2-write-branch-resolution-primary-anchor.md)
- Gate precedent to copy: [`tests/architectural/test_protection_resolver_call_sites.py`](../../../tests/architectural/test_protection_resolver_call_sites.py)
