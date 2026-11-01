---
title: 'ADR: Gate execution targets a surface through a kernel selector and the topology placement seam'
description: 'A gate declares an executionTarget from a kernel-owned surface-selector vocabulary; the placement seam gains an execute verb that resolves it to a physical workdir.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-08-13'
related:
- architecture/mission-gates
- architecture/artifact-placement-seam
- adr/3.x/2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts
---
# Gate execution targets a surface through a kernel selector and the topology placement seam

**Filename:** `2026-08-13-3-gate-execution-targets-through-kernel-surface-selector.md`

**Status:** Proposed

**Date:** 2026-08-13

**Deciders:** Operator (ATDD)

**Technical Story:** Depends on [ADR 2026-08-13-2](2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md).
A declarative gate that executes an asset needs a defined **working directory / execution
context**. Rather than a free-form enum, this reuses the existing placement seam.

---

## Post-dialectics revision (2026-08-13)

Hardened after the dialectics pass (`work/gate-design-dialectics/02-...`, `99-COHERENCE.md`). Settled deltas:

- **CHANGE — no kernel elevation.** Doctrine only needs to validate a token **string**, so
  **doctrine owns the surface-selector `frozenset[str]`** (it owns the gate schema anyway),
  **specify_cli owns the resolver map**, and a **parity test** binds them. Layer directionality
  is satisfied with **zero kernel change**. Option C below (ship `MissionTopology` into doctrine)
  and the "elevate a vocabulary into kernel" framing are **superseded** by this.
- **CHANGE — `execute_dir` ≠ `read_dir`.** It must **reuse the existing stamped
  `GateExecutionContext`** (`build_gate_execution_context`, honouring `surface_cannot_hold`),
  never return a bare `Path` — a bare workdir strips the surface stamp and reopens the
  #2885/#1834 pass-by-default-against-empty-tree failure. `lane` additionally needs a `wp_id`
  and the materialization-aware `resolve_workspace_for_wp` (a different resolver from reads).
- **CLARIFY — `repo_root` is a loud, non-default escape hatch** ("judge the ambient checkout"),
  never the default selector.

## Context and Problem Statement

A gate that runs a check needs to know *where* it runs — the repo root, the mission's
primary planning tree, the coord status tree, or a WP lane worktree. Which physical tree each
of those is depends on the mission's **topology**.

That mapping already exists. The **placement seam**
(`docs/architecture/artifact-placement-seam.md`) resolves `(MissionArtifactKind,
MissionTopology, materialization)` → a `TopologySurface` (`src/mission_runtime/artifacts.py:22`)
→ a physical tree, via `PlacementSeam` (`src/mission_runtime/resolution.py:1373`). It answers
**read_dir** and **write_target** today. It does **not** answer "execute in".

`MissionTopology` (`src/mission_runtime/context.py:55`) is the 2×2 coord×lanes grid
(`SINGLE_BRANCH` / `LANES` / `COORD` / `LANES_WITH_COORD`). It lives in `mission_runtime`,
which is **above `doctrine`** in the layer graph (`kernel ← doctrine ← charter ← runtime`).
A doctrine-layer gate schema that referenced it would be an **upward import** — a layering
violation.

## Decision Drivers

- One mechanism for "where to look / write / run" — do not fork a second workdir resolver.
- Respect layer directionality (doctrine must not import upward into `mission_runtime`).
- Keep the doctrine schema's dependency footprint minimal.

## Considered Options

- **A — Free-form workdir enum on the gate** (`repo_root` | `mission_dossier` | `wp_worktree`), resolved by a new gate-local helper.
- **B — Surface selector routed through the placement seam.** The gate declares an
  `executionTarget` from a small **kernel-owned** surface-selector vocabulary; the
  topology-aware seam gains an `execute_dir` verb that resolves it.
- **C — Ship the whole `MissionTopology` enum down into `doctrine`** so the gate schema types the field against it directly.

## Decision Outcome

**Chosen option: "B".**

- A gate carries `executionTarget: <selector>` where the selector comes from a **small
  surface-selector vocabulary elevated into `kernel`** (e.g. `primary` | `coord` | `lane` |
  `repo_root`). Kernel is the root layer, so `doctrine` may import it without violating
  directionality. `src/kernel/` already hosts this class of shared primitive (`paths.py`,
  `clock.py`).
- The placement seam gains a **third verb, `execute_dir`**, over the same
  `(surface, topology, materialization)` inputs it already uses for `read_dir`/`write_target`.
  The topology *math* stays in `mission_runtime`; doctrine only names a selector.
- Option C is rejected — it drags a runtime-shaped enum into the doctrine layer. Option A is
  rejected — it forks a second "where" resolver the placement seam already owns.

This subsumes the gate's working-directory question into the one partition decision every
other mission artifact already routes through: in `SINGLE_BRANCH` all selectors collapse to
primary; in `LANES_WITH_COORD` `coord` and `lane` diverge, exactly as reads/writes do.

### Consequences

#### Positive

- Gate execution location is topology-correct for free, and consistent with read/write placement.
- Elevating the selector strengthens the seam (the placement doc notes callers that still bypass it).

#### Negative

- Elevating a vocabulary into `kernel` + adding a seam verb is cross-cutting (touches kernel,
  the placement seam, and the gate schema) — larger than a gate-local field.
- The selector vocabulary and `MissionTopology`/`TopologySurface` must be kept in sync; a
  contract test is required to prevent drift.

#### Neutral

- Whether the elevated vocabulary is a brand-new selector enum or a subset of the existing
  `TopologySurface` is a design detail (open Q).

### Open questions (for the dialectics squad)

1. New kernel selector enum, or elevate/reuse `TopologySurface` itself?
2. Is `execute_dir` truly the same resolution as `read_dir`, or does execution need a distinct
   materialization rule (e.g. must the lane worktree already exist)?
3. Do gates ever need to run *outside* any mission surface (e.g. repo-root global checks), and
   is `repo_root` a first-class selector or an escape hatch?
