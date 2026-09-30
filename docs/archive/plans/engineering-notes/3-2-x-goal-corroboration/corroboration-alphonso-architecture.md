---
title: 3.2.x Goal Corroboration — Architectural POV (Architect Alphonso)
description: Architect Alphonso's architectural corroboration of the 3.2.x goals across the v3.1.10..v3.2.0 range via targeted git queries and the ADRs/audits added in range.
doc_status: deprecated
updated: '2026-06-16'
---
# 3.2.x Goal Corroboration — Architectural POV (Architect Alphonso)

**Author:** Architect Alphonso · **Date:** 2026-06-16 · **Branch:** `design/naming-identity-ssot-alignment` @ 3.2.0 (no commit/switch)
**Range:** `v3.1.10..v3.2.0` (2317 commits) · **Method:** targeted git queries + ADRs/audits added in range; no full-diff read.
**Question:** do the 3.2.x goals (`docs/release-goals/3.2.x.md`) describe **architectural in-flight continuations** of what 3.2.0 already shipped, or net-new direction?

## Directives applied

- **DIRECTIVE_001 (Architectural Integrity).** Verdicts are framed against bounded-context / separation-of-concerns evidence: OHS facades, layer guards, and named domain owners — not feature counts.
- **DIRECTIVE_003 (Decision Documentation).** Every claim cites an ADR, commit, or `file:line`. Where 3.2.0 shipped an ADR *before* code (C-006 pattern), that is recorded as the strongest form of evidence.
- **DIRECTIVE_031 (Context-Aware Design).** I treat "doctrine governs execution" and "core-domain SSOT" as bounded-context translation questions: does a single owner exist, and do consumers cross the boundary through an explicit translation layer (facade/resolver) rather than re-deriving?
- **DIRECTIVE_032 (Conceptual Alignment).** I use the operator's own vocabulary (DRG, `ExecutionContext`, Op, strangler, ratchet) as defined in the in-range ADRs, so the corroboration speaks the same domain language as the goals doc.

---

## Goal-by-goal architectural evidence

### G1 — Deepen Doctrine / Charter / DRG impact on runtime execution

| Aspect | Key changes / ADRs (in range) | Trajectory | Gap |
|---|---|---|---|
| **Doctrine *shapes* the runtime prompt** | `src/runtime/next/prompt_builder.py:142,165–188` — the `next` loop resolves the WP's **agent profile** `directive_references` + `tactic_references` and **mission-type governance** (`charter.mission_type_profiles.resolve_mission_type_governance`) and *splices them into the prompt the agent actually reads*. Imports `charter.context.build_charter_context`, `charter.resolver.resolve_project_governance`. | **Moved from "resolvable config" → "governs execution."** Doctrine is no longer inert YAML the agent could ignore; it is rendered into the executed instruction stream at each step boundary. | The wiring shapes the *prompt*; it does not yet *gate a runtime decision path* with a test proving a directive change flips a branch (the goals-doc G1 success criterion). Output-shaping, not yet control-flow gating. |
| **Charter activation as a plan/commit seam** | `src/charter/activation_engine.py` (`plan_activation`/`commit_plan`, FR-011/012/021, NFR-003) — pure validation provably precedes the single config write; fail-closed `UnknownActivationIdError`. `src/charter/cascade.py` (WP11 scoped + shared-reference-safe cascade), `src/charter/kind_vocabulary.py` (operator-token → canonical kind at input boundary). | Charter activation became a **structural** seam (validation-before-write is a property of the code shape, not careful ordering) — the substrate G1 deepening builds on. | The activation engine governs *config state*, not yet a live `next` decision. |
| **DRG relocated into doctrine + fail-closed** | `348ef90db` "relocate three-layer DRG merge into doctrine + fail-closed unknown relations"; `fa80fa0f9` "three-layer DRG + monorepo CharterScope + composable workflows." `src/doctrine/drg/{loader,merge,models}.py`. | DRG became a **first-class doctrine resolution graph** with fail-closed semantics — the machine substrate for "doctrine governs," not a doc artifact. | Composable-workflow consumption by `next` is nascent. |
| **Agent-profile lineage is a DRG edge** | `351f277e7`/`dd38aca41`/`16a1970b2` (WP05/06/07) — `specializes_from` retired as a per-profile field and re-authored as a **DRG `specializes_from` edge**; `AgentProfileRepository.resolve_profile` traverses the DRG; per-profile field form rejected at load (zero-loss migration). | Profile resolution **moved onto the graph** — lineage is now governed by the same DRG that governs the rest of doctrine, eliminating a parallel per-profile mechanism. | — |
| **Op = governed execution tier** | ADR `2026-06-11-1-op-as-first-class-execution-artifact.md` — `dispatch` "loads governance context = **the same charter-context surface a Mission step uses**" before the agent acts. Ratifies a governed middle tier between Mission and ad-hoc. | Even ad-hoc work is now **doctrine-governed by construction** (route → load governance context → record → act → close). | Op storage durability (#1804) and lifecycle dispatch (#1802) are post-3.2.0. |

**G1 verdict: SUPPORTED (in-flight continuation).** 3.2.0 demonstrably moved doctrine from "resolvable config" toward "governs execution": the `next` prompt builder *renders* profile directives/tactics into the executed prompt (`prompt_builder.py:165–188`), the DRG is a fail-closed in-doctrine resolution graph, profile lineage rides the DRG, and the Op ADR makes *dispatch itself* governance-loading. The **named residual** is exactly what the goals doc names: cross the last seam from *shaping the prompt* to *gating a decision path with a behaviour-proving test*. The goal is a continuation of a real trajectory, not net-new.

### G2 — Strangle out core domains onto canonical SSOTs

| Domain | Authority extracted (ADR / commit) | Strangler trajectory | Adoption / gap |
|---|---|---|---|
| **Execution context (path/read-path)** | ADR `2026-06-03-1-execution-state-domain-model.md` (4 bounded modules + OHS facades; ~40 surfaces re-derive context — #1619 root cause) → ADR `2026-06-07-1-execution-state-canonical-surface.md` (**net-new top-level `src/mission_runtime/`**, Screaming Architecture, lean `__all__` over `ExecutionContext`, `resolve_action_context` no-silent-fallback, surface test `test_mission_runtime_surface.py`). | **Textbook extract → route → enforce.** Authority extracted to a screaming package; old `core/execution_context.py` becomes a re-export shim; residue surfaces strangled onto `resolve_action_context`. | **Adoption lags (~5%)** per the naming-SSOT research `00-OVERVIEW.md`: consumers hold a context yet re-derive `mission_id[:8]`/paths inline; `dashboard/scanner.py` hand-rolls `mid8`. The contract is **complete**; cutover is the open work (G2 first slice). |
| **Identity / naming** | ADR `2026-04-09-1-mission-identity-uses-ulid-not-sequential-prefix.md` (ULID `mission_id` is canonical machine identity; `mission_number` display-only) — kills the `NNN-` collision class at the *authority* level. | Authority (ULID) extracted; selectors resolve `mission_id → mid8 → slug` with **no silent fallback** (WP07). | Bare `mission_id[:8]` mid8 derivation at ~10 sites is **ratchet-blind** (`00-OVERVIEW.md` randy-2c) — same extract-but-under-adopt shape: the SSOT exists, consumers re-slice by hand. |
| **Status** | ADR `2026-06-03-1` names **Mission Management** as sole status/kanban owner; `status/` is the OHS facade — `test_status_module_boundary.py` forbids `specify_cli.status.<submodule>` imports (~245 bypass imports at filing). Append-only event log is sole authority. | Extract (facade) → route (boundary test) → enforce (ratchet). | Boundary enforced; write-side coordination strangler is explicitly **3.3.x** (goals-doc non-goal). |
| **Lanes / topology** | ADR `2026-06-07-1-wp-lane-fsm-genesis-and-finalize-clobber.md` (State-pattern FSM + `genesis` lane; supersedes the 2.x state-pattern ADR). `test_topology_resolution_boundary.py`. | Lane state extracted into an explicit FSM owner; topology resolution boundary-guarded. | `resolve_lanes_dir` seam (#1993) still inline at `implement.py:974–982` — *next* extraction, per goals doc. |
| **Shared-package boundary** | ADR `2026-04-25-1-shared-package-boundary.md` + `fda13faf3` (internalize runtime; consume events/tracker via PyPI public imports; vendored copies removed). `test_shared_package_boundary.py`, `test_pyproject_shape.py`, clean-install CI job. | Hybrid model **strangled out**; one OHS-style import surface enforced. | — (this domain is *done*, not in-flight). |

**G2 verdict: SUPPORTED (in-flight continuation), with the adoption-lag caveat the goals doc itself names.** Every listed core domain shows the same architectural arc — **extract a named authority (ADR-first, C-006), route consumers through a facade/resolver, ratchet the class shut** — across execution-context, identity, status, lanes, and shared-package. The clear strangler *trajectory* is present and ADR-declared even where *adoption* lags (the naming-SSOT ~5% finding). This is precisely "extract authority → route consumers, even if adoption lags." The goal is a continuation.

### G3 — DevEx & enablers (capacity to strangle safely)

| Enabler | Evidence (in range) | Effect |
|---|---|---|
| **Architectural ratchet suite** | **52** new `tests/architectural/test_*.py` in range, incl. `test_ratchet_baselines.py`, `test_no_dead_symbols.py`, `test_no_dead_modules.py`, `test_no_legacy_terminology.py`, `test_status_module_boundary.py`, `test_mission_runtime_surface.py`, `test_shared_package_boundary.py`, `test_runtime_charter_doctrine_boundary.py`, `test_topology_resolution_boundary.py`, `test_merge_pipeline_ratchets.py`. | Each strangled class gets a **shrinking-allowlist ratchet** as completeness oracle (e.g. runtime→charter→doctrine boundary: "allowlist must shrink, never grow"). A closed domain **stays closed**. |
| **No-op / run-twice stability ratchet** | `b7bf5f9e3` "shared kernel comparison util + run-twice ratchet" (#1912/#1914/#1871). | Determinism is now machine-enforced — the substrate that lets you safely route consumers onto a single resolver without idempotence regressions. |
| **Pure-seam extractions for testability** | `mission_runtime` lean `__all__` over `ExecutionContext`; `activation_engine` pure plan/commit (no FS discovery, no config load — C-008 data-in); `resolve_lanes_dir` (#1993, removes ~12 mocks per goals doc). | Pure seams make the next strangle *cheaper to test*, lowering the cost of the G2 loop. |
| **Layer meta-guard** | `mission_runtime` registered in `_DEFINED_LAYERS` (both `test_layer_rules.py` + conftest) so `test_no_unregistered_src_packages` fails on an unregistered package. | New domain homes are **structurally forced to declare themselves** at the layer level. |
| **Maintainer governance surface** | `docs/release-goals/` convention + `HOW_TO_MAINTAIN.md`; ADR-first (C-006) discipline visible across the in-range ADR set. | The *process* enabler: goals/priorities/types are now a governed, documented surface. |

**G3 verdict: SUPPORTED (in-flight continuation).** The **capacity to strangle safely demonstrably grew**: 52 architectural guards, shrinking-allowlist ratchets as completeness oracles, a run-twice determinism ratchet, pure-seam extractions that cut mock counts, and a layer meta-guard that forces new homes to declare themselves. The enablers G3 names are already *in use* on the very domains G2 extracts.

---

## Trajectory verdict

**All three 3.2.x goals are architecturally evidence-grounded in-flight continuations (SUPPORTED), not net-new direction.** The `v3.1.10..v3.2.0` delta is dominated by the #1619 runtime/state decomposition (ADRs `2026-06-03-1`, `2026-06-07-1`), the doctrine/DRG-into-runtime wiring (`prompt_builder.py`, `activation_engine.py`, DRG-into-doctrine, profile-lineage-as-edge), and a 52-test architectural-guard substrate. 3.2.x does not pivot; it **deepens** each of these.

**Cross-domain extract-vs-adopt pattern (reconciliation with the naming-SSOT verdict).** The naming-SSOT slice found 3.2.0 *built the right SSOT but adoption is ~5%* (`ExecutionContext`/`resolve_action_context` complete, consumers re-derive inline). The broader delta shows **the same shape is not a one-off — it is the systemic 3.2.0 signature**:

- **Execution-context:** authority extracted to `mission_runtime` (ADR-complete); residue surfaces still re-derive (~5% adoption).
- **Identity:** ULID authority extracted; bare `mission_id[:8]` re-slicing at ~10 ratchet-blind sites.
- **Status:** facade extracted; ~245 bypass imports to migrate before the boundary test could even be added.
- **Boundary (runtime→charter→doctrine):** correct layering declared; 13 known violators sit in a shrinking allowlist.

Each domain is **extract-then-under-adopt**: 3.2.0 reliably built the SSOT and declared it in an ADR (often *before* code, C-006), then routed only a fraction of consumers and parked the rest behind a shrinking-allowlist ratchet. This is *healthy* strangler-fig sequencing, not drift — the ratchets guarantee the gap can only close, never widen. It does, however, mean the 3.2.x goals are correctly framed as **adoption/completion + the next extraction**, not construction. The architecture is on the declared trajectory; 3.2.x is the finish-and-extend cycle the delta set up.
