---
title: Infra-to-logic separation (#2173) — investigation synthesis
description: "Investigation synthesis for the infra-to-logic separation epic (#2173, sub of #1619): three profile-loaded squads' conclusions on injecting infra as ports (2026-06-26)."
doc_status: deprecated
updated: '2026-06-26T00:00:00Z'
kind: Planning
---
# Infra-to-logic separation (#2173) — investigation synthesis

> **Retired (deprecated).** Phase 1 shipped/superseded via merged mission `runtime-bridge-degod-01KX8M1C` (#2173 / #2531; `kitty-specs/runtime-bridge-degod-01KX8M1C/`); Phase 2 (#1619) deferred. Preserved as a historical record.

**Date:** 2026-06-26 · **Branch:** `design/infra-logic-separation-2173` · **Epic:** #2173 (sub-issue of #1619)
**Method:** 3 investigation squads (profile-loaded, read-only) after a prior resolver-port research squad. **Status:** investigation complete; Phase 1 ADR + spec to follow.

This note is the durable record of *why* the design landed where it did. The operator's thesis ("many issues stem from a lack of infra-to-logic separation; a constructor/API-injected resolver would solve a family of issues") was validated **but sharpened** — leaner than the original 6-port vision, with one framing correction.

---

## Coherent view (headline)

1. **The codebase already embodies the pattern.** `resolution.py`'s core is *explicitly* pure ("zero filesystem or git I/O") with I/O threaded in by an imperative shell; `RuntimeEventEmitter(Protocol)` + `NullEmitter` is a shipped port-and-adapters seam; `tracker_client_glue` already does a Clock port by default-param (`sleep or time.sleep`). **#2173 generalizes an existing idiom, not imports a foreign architecture.**

2. **Factual correction (randy + alphonso agree):** the epic's "`context` is a proto-DI container — extend it" is **wrong**. `MissionContext` (`context/models.py:17`) is a frozen value snapshot ("pure identity snapshot"); `context.mission_resolver` is a *module path*, `resolve_mission()` a free function. → Reword to: **"formalize infra ports at the resolution shell/builder seam; ports live on the shell, values stay on the frozen context."** (A frozen value object must NOT carry a mutable I/O collaborator — category error, breaks the immutability invariant.)

3. **Port vs gate resolves to "both, for different problems":**
   - **#2164 canonicalizer divergence → a GATE, not a port** (randy). Canonicalization is already centralized; cure = delegation + an **AST call-site ratchet**. The codebase *already has this exact pattern* — `tests/architectural/test_protection_resolver_call_sites.py` (single-authority free fn + AST gate, no port). Closes the class by construction at ~10% of the churn.
   - **The 3+ parallel `kitty-specs/` walkers + per-call uncached re-walk + TOCTOU → a PORT** (alphonso). A `MissionResolver`/FS adapter owning the *one* walk is the genuine consolidation the gate does nothing for, and the first concrete move on #1619's spine.

4. **DI mechanism is settled, cheap, and dissolves the main objection.** Use the existing idiom: `def fn(..., *, resolver: Port | None = None)` → `resolver = resolver or RealAdapter()` (the `engine.py` emitter pattern, 4 shipped sites). **No framework, no god-object, no constructor-ification.** Because it's *backward-compatible* (an un-ported site still works via the default), randy's "partial-adoption tax / two coexisting conventions" largely evaporates — there is no broken half-state, only "passes a stub or doesn't."

---

## Squad evidence

### Family-port audit (paula) — the family is smaller than it feels

Ranked pain×value/cost. **Genuine cheap extractions:** Clock (14 *byte-identical* `_now_utc` helpers, 68 monkeypatches — textbook "missing concept, copy-pasted"), MissionResolver (#2164, validated), InstalledVersion (the `_CliStatusLike` Protocol *already exists*; just route migrations through it). **Stage carefully:** Renderer (golden-snapshot env-sensitivity, but 99 `Console()` sites). **Do NOT greenfield:** GitOps (highest raw pain — 82 modules, 317 monkeypatches — but the disease is **4 rival seams**, not absence; a port becomes a 5th competitor → *consolidation* work), ProcessEnv (780 monkeypatches is a *test-isolation* artifact; most reads are legitimate config), SaaSQueue/#2170 (already seamed via `fire_saas_fanout`; a gating bug, not a missing port). **Thesis holds where coupling is duplicated-identical; over-generalizes where it's fragmented-incompatible or already-seamed.**

### Red-team (randy) — the gate, not the port

The full injectable Protocol is **not** justified for the resolver; the resolver is already centralized in `resolve_mission()` — it needs *boundary discipline (a gate)*, not *injection*. Cost: full port ≈ 80 call sites + 27 test rewrites + Protocol + adapter + stub + DI seam = **>10× the diff** to close the same class. Cheapest-correct: close #2164 by its own remedy (one-line delegation per write/placement seam) + one parametrized convergence test + one AST arch-gate copied from `test_protection_resolver_call_sites.py`. Reclassify #2169 (env var not even in `src/` anymore — stale), doctor-golden flakiness, and the version cascade as **test-hygiene tickets** (under #1931/#2071), not port extractions. Clock = "enterprise FizzBuzz" (monkeypatch suffices).

### Codebase-fit (alphonso) — idiom + #1619 relationship

DI mechanism = **Protocol (contract) + default-param `x or Default()` (wiring) + one real + one fake adapter**, per-seam. Precedents to match: `RuntimeEventEmitter`/`NullEmitter`/`JsonlEventLog` (events.py:67), `_resolve_wp_bearing_fields` already takes injected `Callable` params (resolution.py:465), tracker-glue clock, the `build_connector` factory. **#2173 is the enabling layer under #1619, but ports inject into the SHELL/builder (`_assemble_core_fragments`, `build_execution_context`), not onto the frozen `MissionExecutionContext`.** The *resolution-of-a-handle* boundary is single; the *enumeration-of-missions* boundary is NOT — multiple parallel `kitty-specs/` walkers (`manifest.py:183`, `core/paths.py:718`, `charter_activate.py:146`, `merge/ordering.py:184`, `mission_resolver._build_index` re-walks every call uncached) — which the MissionResolver/FS port consolidates.

---

## Scoped epic (keep vs drop)

| Keep | Drop / reclassify |
|------|-------------------|
| **#2164 AST gate** (cheap, by-construction) | **GitOps** → 4 rival seams = consolidation, separate effort |
| **MissionResolver port** (enumeration/TOCTOU consolidation + #1619 exemplar) | **Renderer / golden flakiness** → test-hygiene (pin COLUMNS) under #1931 |
| **Clock** → consolidate the 14 identical `_now_utc` into one fn; inject only where determinism is tested | **ProcessEnv** → mostly legitimate config + per-worker HOME isolation exists |
| **Finish InstalledVersion** (route migrations through existing `_CliStatusLike`) | **SaaS #2170** → already seamed; gating bug |

---

## Non-negotiables (all squads)

- Stay OUT of the blind primitive (`primary_feature_dir_for_mission`) — folding canonicalization into it recurses (FR-011). The guard lives at the seam/shell.
- Ambiguity raises `MissionSelectorAmbiguous` (C-009/WP07); never a silent pick.
- Fail-closed-loud on cold-miss (a handle absent from the resolver), never verbatim passthrough.
- One adapter implementation per port (no parallel resolvers); ports on the builder/shell, values on the frozen context.

---

## Recommended phased mission

- **Phase 1 (cheap, ships alone):** close #2164 by its own remedy (delegate every write/placement seam to the full fold) + one parametrized convergence test (read-seam ≡ write-seam for every handle form) + the **AST arch-gate** banning raw `KITTY_SPECS_DIR/<unresolved handle>` composes. This is the single-authority-seam + call-site-gate pattern — generalizes the existing `test_protection_resolver_call_sites.py` precedent — and applies equally to the **#2160 coord-authority class** (mark-status/move-task/safe_commit writing the wrong surface). **This is what we spec: Phase 1 + #2160-class resolution.**
- **Phase 2 (strategic, deferred):** the `MissionResolver` Protocol + `FsMissionResolver` + `FakeMissionResolver`, owning the one `kitty-specs/` walk, threaded into `resolution.py`'s shell via `resolver=None` — kills the multi-walker dup + TOCTOU + per-call re-walk, makes the pure builder FS-free-testable (the #1619 unblock).

## Key file references

`missions/_read_path_resolver.py:1212` (blind primitive), `:1244` (`_canonicalize_primary_read_handle` full fold) · `context/mission_resolver.py:194` (free-fn walker), `:132` (`_build_index` uncached walk) · `context/models.py:17` (frozen `MissionContext`) · `mission_runtime/resolution.py:136/465/825` (pure core / injected-callable / imperative shell) · `runtime/next/_internal_runtime/events.py:67` (Protocol+Null exemplar), `engine.py:191` (default-param idiom) · `tests/architectural/test_protection_resolver_call_sites.py` (the gate precedent to copy), `test_no_raw_mission_spec_paths.py`.
