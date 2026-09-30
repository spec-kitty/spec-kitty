---
title: '08 — Architecture Phase 1: Intermediary Summary'
description: Intermediary summary of Phase 1 (grounding and first design reconnaissance) of the runtime and state overhaul (#1619), marked complete (2026-06-03).
doc_status: deprecated
updated: '2026-06-03'
---
# 08 — Architecture Phase 1: Intermediary Summary

**Phase:** 1 (grounding + first design reconnaissance) — **complete.**
**Date:** 2026-06-03 · **Anchor:** [#1619](https://github.com/Priivacy-ai/spec-kitty/issues/1619)
**Next phase:** conceptual modeling of Context (see `09`), then design-option decision + ADRs.

This is a standalone checkpoint. It restates the problem, what we learned, and what is decided vs
open — so anyone can pick up the thread without reading `01`–`07` end to end.

---

## The problem (one paragraph)

Spec Kitty's mission topology is real and coherent — coordination worktree/branch holds
authoritative status, lane worktrees hold code and sparse-exclude status, the main checkout is not
status authority. But **no component owns the resolution of that topology.** ~40 command surfaces
each re-derive "where does this mission's state live, which branch is authoritative, where may this
command run, what do I tell the agent" — independently, from `meta.json` + `lanes.json` + CWD. The
gaps between those independent derivations are the recurring bug class (#1615–#1618, #1602, #1348).
Point-fixes mask symptoms without installing the owner, so the class keeps returning. This is an
architectural defect (a missing bounded context with a shallow interface), not a bug.

## What we learned (the five load-bearing findings)

1. **It's a split-authority problem, not a state-machine problem.** `status/` is already clean,
   event-sourced, and bounded (060-cleanup). The defect is *topology resolution*, which has no owner.
   (`02`, `05`)

2. **The infra-context pattern we need already exists in the codebase.** `DoctrineService` +
   `PackContext` + `ProjectContext` implement "roots-as-data + frozen context snapshot + pure
   assembler + higher-layer builder", with typed precondition guards and the rule that low layers
   never read `.kittify` config (C-005/C-008). We mirror this, we don't invent it. (`07` §1)

3. **`OperationalContext` already exists** (`src/charter/invocation_context.py:155`) — but holds
   *session* facts (model/profile/role/activity/tech_stack), not filesystem aspects. Naming
   collision to resolve before coding (DIRECTIVE_032). (`07` §2)

4. **MissionStatus is a near-free aggregate.** Because `status/` is event-sourced, `reduce` =
   hydration and `validate_transition` = invariant are already pure. `emit_status_transition_transactional`
   already performs the aggregate dance ad-hoc. Cost is a repository over `store.py` + injecting
   path resolution + migrating ~130 read / 14 write call sites. (`07` §4)

5. **MissionFlow is two deliverables, not one.** The pure FSM (`transitions.py` + `wp_state.py`) is
   already built and property-tested. But it is **100% hardcoded and identical across all 4 mission
   types** — `mission_type` is display metadata only. So: (i) *extracting* the pure FSM behind a
   façade is low-risk cleanup #1619 needs; (ii) *making lanes/gates mission-type-configurable* (the
   "driven by doctrine" premise) is net-new capability — a separate, later epic. (`07` §5)

## What is architecturally constrained (the invariants — `05` I-1…I-10, `04`)

- Resolve topology **once per operation**; no surface re-derives raw paths. *(I-1)*
- Expose **distinct** read/write/destination/cwd/prompt outputs — never one fused `feature_dir`. *(I-2)*
- Key identity on **`mission_id`** (ULID), distinct from `mission_run_id`. *(I-3; ADR A4/A6)*
- **One atomicity domain per operation** (`worktree_root == destination_ref`). *(I-4; #1618)*
- **Consume** `status/`; don't re-implement lane logic. *(I-5; ADR A2/A3)*
- Prompts/help **render from** context. *(I-6; #1616)*
- `lanes.json` consumed **fail-closed**, including dependencies. *(I-7; ADR A1, F-02)*
- `done`/acceptance is a **mission-branch** fact, distinct from lane approvals. *(I-8; ADR A5, F-03)*
- **No shared mutable state across boundaries**; one writer per file/aggregate. *(I-9; DIRECTIVE_001/031; #1602)*
- **Strangler-Fig**, test-anchored migration; no big-bang (bus-factor 1, DM-D). *(I-10; DIRECTIVE_024)*
- **Boundaries by ubiquitous language, not runtime stage**; ≤ a few new contexts. *(DIRECTIVE_031; over-split is a failure mode)*
- Preserve `kernel ← doctrine ← charter ← specify_cli`; dataclasses in `charter`, builders in `specify_cli`/`runtime`. *(layer law)*

## Decided so far (working consensus, revisable)

- The fix is a **Mission Run-scoped context owner**, assembled by a **central builder**, living under
  a new `src/specify_cli/mission_runtime/` umbrella (honors the deep-dive moratorium on new
  top-level packages + epic #992).
- We **extend** the existing context family, not replace it. `OperationalContext` stays as
  session/preferences.
- MissionFlow scope is split: **extraction now, config-driven lanes later.**
- The **#1619 e2e regression** (next→implement→move-task→review→status parity from main *and* lane
  CWD) is the migration ratchet, built **first**.

## Open decisions (carried into Phase 2)

| # | Decision | Where |
|---|----------|-------|
| D1 | Resolve the `OperationalContext` naming collision | `07` §7.1 |
| D2 | Does `MissionStatus` own the commit seam (closes #1618) or only in-memory state? | `07` §7.2 |
| D3 | MissionFlow: extraction-only now, config-driven lanes deferred? | `07` §7.3 |
| D4 | Object vs service vs façade for the context (Options A/B/C) | `06` §5 |
| D5 | Model durable **Execution Topology** separately from per-invocation **Operation Context**? | `06` §6.1 |
| D6 | Central builder signature + where `op_kind` lives | `07` §7.5 |
| D7 | Reconcile #1619 with epic #992 explicitly | `07` §7.7 |

## Phase 2 entry point

The next working session (doc `09`) tackles the **conceptual modeling of Context** itself — the
hypothesis that "context" is not one object but a **composition of domain-owned fragments**
(infrastructure, filesystem, version control, execution preferences, execution state) aggregated
into fit-for-purpose composites. That model, if it holds, directly informs D1, D4, D5, and D6.
